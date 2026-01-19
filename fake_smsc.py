#!/usr/bin/env python3
"""
Fake SMSC Server for testing Jasmin
Accepts submit_sm, responds with submit_sm_resp, sends DLR after N seconds
"""

import asyncio
import struct
import time
import uuid
import logging
import signal
import sys
import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger('fake_smsc')

# SMPP Command IDs
GENERIC_NACK = 0x80000000
BIND_RECEIVER = 0x00000001
BIND_RECEIVER_RESP = 0x80000001
BIND_TRANSMITTER = 0x00000002
BIND_TRANSMITTER_RESP = 0x80000002
BIND_TRANSCEIVER = 0x00000009
BIND_TRANSCEIVER_RESP = 0x80000009
SUBMIT_SM = 0x00000004
SUBMIT_SM_RESP = 0x80000004
DELIVER_SM = 0x00000005
DELIVER_SM_RESP = 0x80000005
UNBIND = 0x00000006
UNBIND_RESP = 0x80000006
ENQUIRE_LINK = 0x00000015
ENQUIRE_LINK_RESP = 0x80000015
ESME_RINVSRCADR = 0x0000000A  # Invalid Source Address

TLV_MESSAGE_STATE = 0x0427
STATE_DELIVERED = 0x02
STATE_REJECTED  = 0x08

# SMPP Status
ESME_ROK = 0x00000000

rc_client = redis.Redis(host='52.57.134.177', port=6379, db=0, password='OAJUHyc1cLJwZ1nd8Ha8qM', username='default')


class SMPPSession:
    def __init__(self, reader, writer, dlr_delay=5):
        self.reader = reader
        self.writer = writer
        self.dlr_delay = dlr_delay
        self.sequence_number = 0
        self.bound = False
        self.system_id = None
        
    def next_sequence(self):
        self.sequence_number += 1
        return self.sequence_number

    async def read_pdu(self):
        """Read PDU from socket"""
        header = await self.reader.readexactly(16)
        command_length, command_id, command_status, sequence_number = struct.unpack('>IIII', header)
        
        body = b''
        if command_length > 16:
            body = await self.reader.readexactly(command_length - 16)
        
        return {
            'command_length': command_length,
            'command_id': command_id,
            'command_status': command_status,
            'sequence_number': sequence_number,
            'body': body
        }

    def write_pdu(self, command_id, sequence_number, status=ESME_ROK, body=b''):
        """Send PDU"""
        command_length = 16 + len(body)
        header = struct.pack('>IIII', command_length, command_id, status, sequence_number)
        self.writer.write(header + body)

    def parse_cstring(self, data, offset):
        """Parse C-string (null-terminated)"""
        end = data.index(b'\x00', offset)
        return data[offset:end].decode('latin-1'), end + 1

    def parse_bind(self, body):
        """Parse bind PDU"""
        offset = 0
        system_id, offset = self.parse_cstring(body, offset)
        password, offset = self.parse_cstring(body, offset)
        system_type, offset = self.parse_cstring(body, offset)
        interface_version = body[offset]
        addr_ton = body[offset + 1]
        addr_npi = body[offset + 2]
        address_range, _ = self.parse_cstring(body, offset + 3)
        
        return {
            'system_id': system_id,
            'password': password,
            'system_type': system_type,
            'interface_version': interface_version
        }

    def parse_submit_sm(self, body):
        """Parse submit_sm PDU"""
        offset = 0
        
        service_type, offset = self.parse_cstring(body, offset)
        source_addr_ton = body[offset]
        source_addr_npi = body[offset + 1]
        offset += 2
        source_addr, offset = self.parse_cstring(body, offset)
        
        dest_addr_ton = body[offset]
        dest_addr_npi = body[offset + 1]
        offset += 2
        destination_addr, offset = self.parse_cstring(body, offset)
        
        esm_class = body[offset]
        protocol_id = body[offset + 1]
        priority_flag = body[offset + 2]
        offset += 3
        
        schedule_delivery_time, offset = self.parse_cstring(body, offset)
        validity_period, offset = self.parse_cstring(body, offset)
        
        registered_delivery = body[offset]
        replace_if_present_flag = body[offset + 1]
        data_coding = body[offset + 2]
        sm_default_msg_id = body[offset + 3]
        sm_length = body[offset + 4]
        offset += 5
        
        short_message = body[offset:offset + sm_length]
        
        return {
            'source_addr': source_addr,
            'destination_addr': destination_addr,
            'short_message': short_message,
            'registered_delivery': registered_delivery,
            'data_coding': data_coding,
            'esm_class': esm_class
        }

    def make_cstring(self, s):
        """Create C-string"""
        if isinstance(s, str):
            s = s.encode('latin-1')
        return s + b'\x00'

    def make_deliver_sm(self, source_addr, dest_addr, short_message, esm_class=0x04, message_state=None):
        """Create deliver_sm PDU body"""
        body = b''
        body += self.make_cstring('')  # service_type
        body += struct.pack('BB', 0, 0)  # source_addr_ton, source_addr_npi
        body += self.make_cstring(source_addr)
        body += struct.pack('BB', 0, 0)  # dest_addr_ton, dest_addr_npi
        body += self.make_cstring(dest_addr)
        body += struct.pack('BBB', esm_class, 0, 0)  # esm_class, protocol_id, priority_flag
        body += self.make_cstring('')  # schedule_delivery_time
        body += self.make_cstring('')  # validity_period
        body += struct.pack('BBBBB', 0, 0, 0, 0, len(short_message))  # registered_delivery, replace_if_present, data_coding, sm_default_msg_id, sm_length
        body += short_message if isinstance(short_message, bytes) else short_message.encode('latin-1')

        # ---- optional TLV: message_state ----
        if message_state is not None:
            body += struct.pack(
                '>HHB',
                TLV_MESSAGE_STATE,  # 0x0427
                1,                  # length
                message_state       # 2 or 8
            )
        return body

    async def send_dlr(self, source_addr, dest_addr, message_id, stat='DELIVRD', err='000', message_state=None):
        """Send DLR after dlr_delay seconds"""
        await asyncio.sleep(self.dlr_delay)
        
        dlr_text = (
            f"id:{message_id} "
            f"sub:001 dlvrd:001 "
            f"submit date:{time.strftime('%y%m%d%H%M')} "
            f"done date:{time.strftime('%y%m%d%H%M')} "
            f"stat:{stat} err:{err} text:"
        )
        
        body = self.make_deliver_sm(
            source_addr=dest_addr,  # swap: DLR comes from recipient
            dest_addr=source_addr,
            short_message=dlr_text,
            esm_class=0x04,  # DLR flag,
            message_state=message_state
        )
        
        seq = self.next_sequence()
        self.write_pdu(DELIVER_SM, seq, body=body)
        await self.writer.drain()
        
        logger.info(f"[DLR SENT] msg_id={message_id} stat={stat}")

    async def handle(self):
        """Main processing loop"""
        addr = self.writer.get_extra_info('peername')
        logger.info(f"[CONNECT] {addr}")
        
        try:
            while True:
                pdu = await self.read_pdu()
                cmd = pdu['command_id']
                seq = pdu['sequence_number']
                
                if cmd in (BIND_TRANSCEIVER, BIND_TRANSMITTER, BIND_RECEIVER):
                    bind_data = self.parse_bind(pdu['body'])
                    self.system_id = bind_data['system_id']
                    self.bound = True
                    
                    resp_cmd = {
                        BIND_TRANSCEIVER: BIND_TRANSCEIVER_RESP,
                        BIND_TRANSMITTER: BIND_TRANSMITTER_RESP,
                        BIND_RECEIVER: BIND_RECEIVER_RESP
                    }[cmd]
                    
                    body = self.make_cstring('FAKESMSC')
                    self.write_pdu(resp_cmd, seq, body=body)
                    await self.writer.drain()
                    
                    logger.info(f"[BIND] system_id={self.system_id}")
                
                elif cmd == SUBMIT_SM:
                    sm = self.parse_submit_sm(pdu['body'])
                    message_id = uuid.uuid4().hex[:8]
                    
                    logger.info(f"[SUBMIT_SM] {sm['source_addr']} -> {sm['destination_addr']} msg_id={message_id}")
                    reserved_key = f'dlr:block:{sm["source_addr"]}'
                    is_reserved = rc_client.get(reserved_key)

                    if is_reserved:
                        logger.info(f"[RESERVED] {sm['source_addr']}")
                        # submit_sm_resp
                        body = self.make_cstring(message_id)
                        self.write_pdu(SUBMIT_SM_RESP, seq, body=body)
                        await self.writer.drain()
                        
                        # Schedule DLR if requested
                        if sm['registered_delivery'] & 0x01:
                            asyncio.create_task(self.send_dlr(
                                source_addr=sm['source_addr'],
                                dest_addr=sm['destination_addr'],
                                message_id=message_id,
                                message_state=STATE_DELIVERED
                            ))
                    else:
                        # Source is not reserved: reject message with invalid source address error
                        body = self.make_cstring('')
                        self.write_pdu(SUBMIT_SM_RESP, seq, body=body)  
                        asyncio.create_task(self.send_dlr(
                            source_addr=sm['source_addr'],
                            dest_addr=sm['destination_addr'],
                            message_id=message_id,
                            stat='REJECTD',
                            message_state=STATE_REJECTED
                        ))
                        await self.writer.drain()
                        logger.warning(f"[SUBMIT_SM REJECTED] source={sm['source_addr']} (not reserved) - ESME_RINVSRCADR")
                    
                
                elif cmd == ENQUIRE_LINK:
                    self.write_pdu(ENQUIRE_LINK_RESP, seq)
                    await self.writer.drain()
                    logger.debug("[ENQUIRE_LINK]")
                
                elif cmd == UNBIND:
                    self.write_pdu(UNBIND_RESP, seq)
                    await self.writer.drain()
                    logger.info("[UNBIND]")
                    break
                
                elif cmd == DELIVER_SM_RESP:
                    # Jasmin acknowledged DLR receipt
                    logger.debug(f"[DELIVER_SM_RESP] seq={seq}")
                
                else:
                    logger.warning(f"[UNKNOWN CMD] {hex(cmd)}")
                    self.write_pdu(GENERIC_NACK, seq)
                    await self.writer.drain()
                    
        except asyncio.IncompleteReadError:
            logger.info(f"[DISCONNECT] {addr}")
        except Exception as e:
            logger.error(f"[ERROR] {e}")
        finally:
            self.writer.close()
            await self.writer.wait_closed()


class FakeSMSC:
    def __init__(self, host='0.0.0.0', port=2776, dlr_delay=5):
        self.host = host
        self.port = port
        self.dlr_delay = dlr_delay
        self.server = None
        self._shutdown_event = None
    
    async def handle_client(self, reader, writer):
        session = SMPPSession(reader, writer, self.dlr_delay)
        await session.handle()
    
    async def run(self):
        # Create shutdown event in the current event loop
        self._shutdown_event = asyncio.Event()
        
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        
        logger.info(f"Fake SMSC listening on {self.host}:{self.port}")
        logger.info(f"DLR delay: {self.dlr_delay} seconds")
        
        # Set up signal handlers for graceful shutdown (Unix only)
        if sys.platform != 'win32':
            try:
                loop = asyncio.get_event_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, self._signal_handler)
            except (NotImplementedError, ValueError):
                # Signal handlers not available on this platform
                pass
        
        try:
            async with self.server:
                await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("Server cancelled, shutting down...")
        finally:
            logger.info("Shutting down server...")
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            logger.info("Server stopped.")
    
    def _signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, shutting down gracefully...")
        if self._shutdown_event:
            self._shutdown_event.set()


if __name__ == '__main__':
    import argparse

    #
    # smpplib -- SMPP Library for Python
    # Copyright (c) 2005 Martynas Jocius <mjoc@akl.lt>
    #
    # This library is free software; you can redistribute it and/or
    # modify it under the terms of the GNU Lesser General Public
    # License as published by the Free Software Foundation; either
    # version 2.1 of the License, or (at your option) any later version.
    #
    # This library is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    # Lesser General Public License for more details.
    #
    # You should have received a copy of the GNU Lesser General Public
    # License along with this library; if not, write to the Free Software
    # Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

    """SMPP Commands module"""

    import logging
    import struct

    import six

    try:
        from smpplib import consts, exceptions, pdu
        from smpplib.ptypes import flag, ostr
    except ImportError:
        # smpplib not installed - this embedded code is not used by the main SMSC server
        # Define minimal stubs to prevent errors
        class consts:
            SMPP_ESME_ROK = 0x00000000
            EMPTY_STRING = ''
            NULL_STRING = b'\x00'
            OPTIONAL_PARAMS = {}
            INT_PACK_FORMATS = {1: 'B', 2: 'H', 4: 'I'}
        
        class exceptions:
            class UnknownCommandError(Exception):
                pass
        
        class pdu:
            class PDU:
                pass
        
        class flag:
            pass
        
        class ostr:
            pass

    logger = logging.getLogger('smpplib.command')


    def factory(command_name, **kwargs):
        """Return instance of a specific command class"""

        try:
            return {
                'bind_transmitter': BindTransmitter,
                'bind_transmitter_resp': BindTransmitterResp,
                'bind_receiver': BindReceiver,
                'bind_receiver_resp': BindReceiverResp,
                'bind_transceiver': BindTransceiver,
                'bind_transceiver_resp': BindTransceiverResp,
                'data_sm': DataSM,
                'data_sm_resp': DataSMResp,
                'generic_nack': GenericNAck,
                'submit_sm': SubmitSM,
                'submit_sm_resp': SubmitSMResp,
                'deliver_sm': DeliverSM,
                'deliver_sm_resp': DeliverSMResp,
                'query_sm': QuerySM,
                'query_sm_resp': QuerySMResp,
                'unbind': Unbind,
                'unbind_resp': UnbindResp,
                'enquire_link': EnquireLink,
                'enquire_link_resp': EnquireLinkResp,
                'alert_notification': AlertNotification,
            }[command_name](command_name, **kwargs)
        except KeyError:
            raise exceptions.UnknownCommandError('Command "%s" is not supported' % command_name)


    def get_optional_name(code):
        """Return optional_params name by given code. If code is unknown, raise
        UnkownCommandError exception"""

        for key, value in six.iteritems(consts.OPTIONAL_PARAMS):
            if value == code:
                return key

        raise exceptions.UnknownCommandError('Unknown SMPP command code "0x%x"' % code)


    def get_optional_code(name):
        """Return optional_params code by given command name. If name is unknown,
        raise UnknownCommandError exception"""

        try:
            return consts.OPTIONAL_PARAMS[name]
        except KeyError:
            raise exceptions.UnknownCommandError('Unknown SMPP command name "%s"' % name)


    def unpack_short(data, pos):
        return struct.unpack('>H', data[pos:pos + 2])[0], pos + 2


    class Command(pdu.PDU):
        """SMPP PDU Command class"""

        params = {}

        def __init__(self, command, need_sequence=True, allow_unknown_opt_params=False, **kwargs):
            super(Command, self).__init__(**kwargs)

            self.allow_unknown_opt_params = allow_unknown_opt_params

            self.command = command
            if need_sequence and (kwargs.get('sequence') is None):
                self.sequence = self._next_seq()

            if kwargs.get('status') is None:
                self.status = consts.SMPP_ESME_ROK

            self._set_vars(**kwargs)

        def _set_vars(self, **kwargs):
            """set attributes accordingly to kwargs"""
            for key, value in six.iteritems(kwargs):
                if not hasattr(self, key) or getattr(self, key) is None:
                    setattr(self, key, value)

        def generate_params(self):
            """Generate binary data from the object"""

            if hasattr(self, 'prep') and callable(self.prep):
                self.prep()

            body = consts.EMPTY_STRING

            for field in self.params_order:
                param = self.params[field]
                if self.field_is_optional(field):
                    if param.type is int:
                        value = self._generate_int_tlv(field)
                        if value:
                            body += value
                    elif param.type is str:
                        value = self._generate_string_tlv(field)
                        if value:
                            body += value
                    elif param.type is ostr:
                        value = self._generate_ostring_tlv(field)
                        if value:
                            body += value
                else:
                    if param.type is int:
                        value = self._generate_int(field)
                        body += value
                    elif param.type is str:
                        value = self._generate_string(field)
                        body += value
                    elif param.type is ostr:
                        value = self._generate_ostring(field)
                        if value:
                            body += value
            return body

        def _generate_opt_header(self, field):
            """Generate a header for an optional parameter"""

            raise NotImplementedError('Vendors not supported')

        def _generate_int(self, field):
            """Generate integer value"""

            fmt = self._int_pack_format(field)
            data = getattr(self, field)
            if data:
                return struct.pack(">" + fmt, data)
            else:
                return consts.NULL_STRING

        def _generate_string(self, field):
            """Generate string value"""

            field_value = getattr(self, field)

            if hasattr(self.params[field], 'size'):
                size = self.params[field].size
                value = field_value.ljust(size, chr(0))
            elif hasattr(self.params[field], 'max'):
                if len(field_value or '') >= self.params[field].max:
                    field_value = field_value[0:self.params[field].max - 1]

                if field_value:
                    value = field_value + chr(0)
                else:
                    value = chr(0)

            setattr(self, field, field_value)
            return six.b(value)

        def _generate_ostring(self, field):
            """Generate octet string value (no null terminator)"""

            value = getattr(self, field)
            if value:
                return value
            else:
                return None  # chr(0)

        def _generate_int_tlv(self, field):
            """Generate integer value"""
            fmt = self._int_pack_format(field)
            data = getattr(self, field)
            field_code = get_optional_code(field)
            field_length = self.params[field].size
            value = None
            if data is not None:
                value = struct.pack(">HH" + fmt, field_code, field_length, data)
            return value

        def _generate_string_tlv(self, field):
            """Generate string value"""

            field_value = getattr(self, field)
            field_code = get_optional_code(field)

            if hasattr(self.params[field], 'size'):
                size = self.params[field].size
                fvalue = field_value.ljust(size, chr(0))
                value = struct.pack(">HH", field_code, size) + fvalue
            elif hasattr(self.params[field], 'max'):
                if len(field_value or '') > self.params[field].max:
                    field_value = field_value[0:self.params[field].max - 1]

                if field_value:
                    fvalue = field_value + chr(0)
                    field_length = len(fvalue)
                    value = struct.pack(">HH", field_code, field_length) + fvalue.encode()
                else:
                    value = None  # chr(0)
            return value

        def _generate_ostring_tlv(self, field):
            """Generate octet string value (no null terminator)"""
            try:
                field_value = getattr(self, field)
            except:
                return None
            field_code = get_optional_code(field)

            value = None
            if field_value:
                field_length = len(field_value)
                value = struct.pack(">HH", field_code, field_length) + field_value
            return value

        def _int_pack_format(self, field):
            """Return format type"""
            return consts.INT_PACK_FORMATS[self.params[field].size]

        def _parse_int(self, field, data, pos):
            """
            Parse fixed-length chunk from a PDU.
            Return (data, pos) tuple.
            """

            size = self.params[field].size
            fmt = self._int_pack_format(field)
            field_value, = struct.unpack(">" + fmt, data[pos:pos + size])
            setattr(self, field, field_value)
            pos += size

            return data, pos

        def _parse_string(self, field, data, pos, length=None):
            """
            Parse variable-length string from a PDU.
            Return (data, pos) tuple.
            """

            if length is None:
                end = data.find(consts.NULL_STRING, pos)
                length = end - pos
            else:
                length -= 1  # length includes trailing NULL character

            setattr(self, field, data[pos:pos + length])
            pos += length + 1

            return data, pos

        def _parse_ostring(self, field, data, pos, length=None):
            """
            Parse an octet string from a PDU.
            Return (data, pos) tuple.
            """

            if length is None:
                length_field = self.params[field].len_field
                length = int(getattr(self, length_field))

            setattr(self, field, data[pos:pos + length])
            pos += length

            return data, pos

        def is_fixed(self, field):
            """Return True if field has fixed length, False otherwise"""

            if hasattr(self.params[field], 'size'):
                return True
            return False

        def parse_params(self, data):
            """Parse data into the object structure"""

            pos = 0
            dlen = len(data)

            for field in self.params_order:
                param = self.params[field]
                if pos == dlen or self.field_is_optional(field):
                    break

                if param.type is int:
                    data, pos = self._parse_int(field, data, pos)
                elif param.type is str:
                    data, pos = self._parse_string(field, data, pos)
                elif param.type is ostr:
                    data, pos = self._parse_ostring(field, data, pos)
            if pos < dlen:
                self.parse_optional_params(data[pos:])

        def parse_optional_params(self, data):
            """Parse optional parameters.

            Optional parameters have the following format:
                * type (2 bytes)
                * length (2 bytes)
                * value (variable, <length> bytes)
            """
            dlen = len(data)
            pos = 0

            while pos < dlen:
                type_code, pos = unpack_short(data, pos)
                length, pos = unpack_short(data, pos)

                try:
                    field = get_optional_name(type_code)
                except exceptions.UnknownCommandError as e:
                    if self.allow_unknown_opt_params:
                        logger.warning("Unknown optional parameter type 0x%x, skipping", type_code)
                        pos += length
                        continue
                    raise

                param = self.params[field]
                if param.type is int:
                    data, pos = self._parse_int(field, data, pos)
                elif param.type is str:
                    data, pos = self._parse_string(field, data, pos, length)
                elif param.type is ostr:
                    data, pos = self._parse_ostring(field, data, pos, length)

        def field_exists(self, field):
            """Return True if field exists, False otherwise"""
            return hasattr(self.params, field)

        def field_is_optional(self, field):
            """Return True if field is optional, False otherwise"""

            if hasattr(self, 'mandatory_fields') and field in self.mandatory_fields:
                return False
            elif field in consts.OPTIONAL_PARAMS:
                return True
            elif self.is_vendor():
                # FIXME: No vendor support yet
                return False

            return False


    class Param(object):
        """Command parameter info class"""

        def __init__(self, **kwargs):
            if 'type' not in kwargs:
                raise KeyError('Parameter Type not defined')

            if kwargs.get('type') not in (int, str, ostr, flag):
                raise ValueError("Invalid parameter type: %s" % kwargs.get('type'))

            valid_keys = ('type', 'size', 'min', 'max', 'len_field')
            for k in kwargs:
                if k not in valid_keys:
                    raise KeyError("Key '%s' not allowed here" % k)

            self.type = kwargs.get('type')

            for param in ('size', 'min', 'max', 'len_field'):
                if param in kwargs:
                    setattr(self, param, kwargs[param])

        def __repr__(self):
            """Shows type of Param in console"""
            return ''.join(('<Param of ', str(self.type), '>'))


    class BindTransmitter(Command):
        """Bind as a transmitter command"""

        params = {
            'system_id': Param(type=str, max=16),
            'password': Param(type=str, max=9),
            'system_type': Param(type=str, max=13),
            'interface_version': Param(type=int, size=1),
            'addr_ton': Param(type=int, size=1),
            'addr_npi': Param(type=int, size=1),
            'address_range': Param(type=str, max=41),
        }

        # Order is important, but params dictionary is unordered
        params_order = (
            'system_id', 'password', 'system_type',
            'interface_version', 'addr_ton', 'addr_npi', 'address_range',
        )

        def __init__(self, command, **kwargs):
            super(BindTransmitter, self).__init__(command, **kwargs)

            self._set_vars(**(dict.fromkeys(self.params)))
            self.interface_version = consts.SMPP_VERSION_34


    class BindReceiver(BindTransmitter):
        """Bind as a receiver command"""

        def __init__(self, command, **kwargs):
            super(BindReceiver, self).__init__(command, **kwargs)


    class BindTransceiver(BindTransmitter):
        """Bind as receiver and transmitter command"""

        def __init__(self, command, **kwargs):
            super(BindTransceiver, self).__init__(command, **kwargs)


    class BindTransmitterResp(Command):
        """Response for bind as a transmitter command"""

        params = {
            'system_id': Param(type=str, max=16),
            'sc_interface_version': Param(type=int, size=1),
        }

        params_order = ('system_id', 'sc_interface_version')

        def __init__(self, command, **kwargs):
            super(BindTransmitterResp, self).__init__(command, need_sequence=False,
                                                      **kwargs)

            self._set_vars(**(dict.fromkeys(self.params)))


    class BindReceiverResp(BindTransmitterResp):
        """Response for bind as a reciever command"""

        def __init__(self, command, **kwargs):
            super(BindReceiverResp, self).__init__(command, **kwargs)


    class BindTransceiverResp(BindTransmitterResp):
        """Response for bind as a transceiver command"""

        def __init__(self, command, **kwargs):
            super(BindTransceiverResp, self).__init__(command, **kwargs)


    class DataSM(Command):
        """data_sm command is used to transfer data between SMSC and the ESME"""

        params = {
            'service_type': Param(type=str, max=6),
            'source_addr_ton': Param(type=int, size=1),
            'source_addr_npi': Param(type=int, size=1),
            'source_addr': Param(type=str, max=21),
            'dest_addr_ton': Param(type=int, size=1),
            'dest_addr_npi': Param(type=int, size=1),
            'destination_addr': Param(type=str, max=21),
            'esm_class': Param(type=int, size=1),
            'registered_delivery': Param(type=int, size=1),
            'data_coding': Param(type=int, size=1),

            # Optional params:
            'source_port': Param(type=int, size=2),
            'source_addr_subunit': Param(type=int, size=1),
            'source_network_type': Param(type=int, size=1),
            'source_bearer_type': Param(type=int, size=1),
            'source_telematics_id': Param(type=int, size=2),
            'destination_port': Param(type=int, size=2),
            'dest_addr_subunit': Param(type=int, size=1),
            'dest_network_type': Param(type=int, size=1),
            'dest_bearer_type': Param(type=int, size=1),
            'dest_telematics_id': Param(type=int, size=2),
            'sar_msg_ref_num': Param(type=int, size=2),
            'sar_total_segments': Param(type=int, size=1),
            'sar_segment_seqnum': Param(type=int, size=1),
            'more_messages_to_send': Param(type=int, size=1),
            'qos_time_to_live': Param(type=int, size=4),
            'payload_type': Param(type=int, size=1),
            'message_payload': Param(type=ostr, max=260),
            'receipted_message_id': Param(type=str, max=65),
            'message_state': Param(type=int, size=1),
            'network_error_code': Param(type=ostr, size=3),
            'user_message_reference': Param(type=int, size=2),
            'privacy_indicator': Param(type=int, size=1),
            'callback_num': Param(type=ostr, min=4, max=19),
            'callback_num_pres_ind': Param(type=int, size=1),
            'callback_num_atag': Param(type=str, max=65),
            'source_subaddress': Param(type=str, min=2, max=23),
            'dest_subaddress': Param(type=str, min=2, max=23),
            'user_response_code': Param(type=int, size=1),
            'display_time': Param(type=int, size=1),
            'sms_signal': Param(type=int, size=2),
            'ms_validity': Param(type=int, size=1),
            'ms_msg_wait_facilities': Param(type=int, size=1),
            'number_of_messages': Param(type=int, size=1),
            'alert_on_message_delivery': Param(type=flag),
            'language_indicator': Param(type=int, size=1),
            'its_reply_type': Param(type=int, size=1),
            'its_session_info': Param(type=int, size=2),
        }

        params_order = (
            'service_type', 'source_addr_ton', 'source_addr_npi',
            'source_addr', 'dest_addr_ton', 'dest_addr_npi', 'destination_addr',
            'esm_class', 'registered_delivery', 'data_coding',

            # Optional params:
            'source_port', 'source_addr_subunit', 'source_network_type',
            'source_bearer_type', 'source_telematics_id', 'destination_port',
            'dest_addr_subunit', 'dest_network_type', 'dest_bearer_type',
            'dest_telematics_id', 'sar_msg_ref_num', 'sar_total_segments',
            'sar_segment_seqnum', 'more_messages_to_send', 'qos_time_to_live',
            'payload_type', 'message_payload', 'receipted_message_id',
            'message_state', 'network_error_code', 'user_message_reference',
            'privacy_indicator', 'callback_num', 'callback_num_pres_ind',
            'callback_num_atag', 'source_subaddress', 'dest_subaddress',
            'user_response_code', 'display_time', 'sms_signal',
            'ms_validity', 'ms_msg_wait_facilities', 'number_of_messages',
            'alert_on_message_delivery', 'language_indicator', 'its_reply_type',
            'its_session_info',
        )

        def __init__(self, command, **kwargs):
            super(DataSM, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    class DataSMResp(Command):
        """Reponse command for data_sm"""
        params = {
            'message_id': Param(type=str, max=65),

            # Optional params:
            # type size is implementation specific.
            'delivery_failure_reason': Param(type=str, max=256),
            'network_error_code': Param(type=str, max=3),
            'additional_status_info_text': Param(type=str, max=256),
            'dpf_result': Param(type=int, size=1),
        }

        params_order = (
            'message_id',

            # Optional params:
            'delivery_failure_reason', 'network_error_code', 'additional_status_info_text',
            'dpf_result',
        )

        def __init__(self, command, **kwargs):
            super(DataSMResp, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    class GenericNAck(Command):
        """General Negative Acknowledgement class"""

        params = {}
        params_order = ()
        _defs = []

        def __init__(self, command, **kwargs):
            super(GenericNAck, self).__init__(command, need_sequence=False, **kwargs)


    class SubmitSM(Command):
        """submit_sm command class

        This command is used by an ESME to submit short message to the SMSC.
        submit_sm PDU does not support the transaction mode."""

        #
        # Service type
        # The following generic service types are defined:
        #   '' -- default
        #   'CMT' -- Cellural Messaging
        #   'CPT' -- Cellural Paging
        #   'VMN' -- Voice Mail Notification
        #   'VMA' -- Voice Mail Alerting
        #   'WAP' -- Wireless Application Protocol
        #   'USSD' -- Unstructured Supplementary Services Data
        service_type = None

        # Type of Number for source address
        source_addr_ton = None

        # Numbering Plan Indicator for source address
        source_addr_npi = None

        # Address of SME which originated this message
        source_addr = None

        # TON for destination
        dest_addr_ton = None

        # NPI for destination
        dest_addr_npi = None

        # Destination address for this message
        destination_addr = None

        # Message mode and message type
        esm_class = None  # SMPP_MSGMODE_DEFAULT

        # Protocol Identifier
        protocol_id = None

        # Priority level of this message
        priority_flag = None

        # Message is to be scheduled by the SMSC for delivery
        schedule_delivery_time = None

        # Validity period of this message
        validity_period = None

        # Indicator to signify if an SMSC delivery receipt or and SME
        # acknowledgement is required.
        registered_delivery = None

        # This flag indicates if submitted message should replace an existing
        # message
        replace_if_present_flag = None

        # Encoding scheme of the short messaege data
        data_coding = None  # SMPP_ENCODING_DEFAULT#ISO10646

        # Indicates the short message to send from a list of predefined
        # ('canned') short messages stored on the SMSC
        sm_default_msg_id = None

        # Message length in octets
        sm_length = 0

        # Up to 254 octets of short message user data
        short_message = None

        # Optional are taken from params list and are set dynamically when
        # __init__ is called.
        params = {
            'service_type': Param(type=str, max=6),
            'source_addr_ton': Param(type=int, size=1),
            'source_addr_npi': Param(type=int, size=1),
            'source_addr': Param(type=str, max=21),
            'dest_addr_ton': Param(type=int, size=1),
            'dest_addr_npi': Param(type=int, size=1),
            'destination_addr': Param(type=str, max=21),
            'esm_class': Param(type=int, size=1),
            'protocol_id': Param(type=int, size=1),
            'priority_flag': Param(type=int, size=1),
            'schedule_delivery_time': Param(type=str, max=17),
            'validity_period': Param(type=str, max=17),
            'registered_delivery': Param(type=int, size=1),
            'replace_if_present_flag': Param(type=int, size=1),
            'data_coding': Param(type=int, size=1),
            'sm_default_msg_id': Param(type=int, size=1),
            'sm_length': Param(type=int, size=1),
            'short_message': Param(type=ostr, max=254, len_field='sm_length'),

            # Optional params
            'user_message_reference': Param(type=int, size=2),
            'source_port': Param(type=int, size=2),
            'source_addr_subunit': Param(type=int, size=2),
            'destination_port': Param(type=int, size=2),
            'dest_addr_subunit': Param(type=int, size=1),
            'sar_msg_ref_num': Param(type=int, size=2),
            'sar_total_segments': Param(type=int, size=1),
            'sar_segment_seqnum': Param(type=int, size=1),
            'more_messages_to_send': Param(type=int, size=1),
            'payload_type': Param(type=int, size=1),
            'message_payload': Param(type=ostr, max=260),
            'privacy_indicator': Param(type=int, size=1),
            'callback_num': Param(type=ostr, min=4, max=19),
            'callback_num_pres_ind': Param(type=int, size=1),
            'source_subaddress': Param(type=str, min=2, max=23),
            'dest_subaddress': Param(type=str, min=2, max=23),
            'user_response_code': Param(type=int, size=1),
            'display_time': Param(type=int, size=1),
            'sms_signal': Param(type=int, size=2),
            'ms_validity': Param(type=int, size=1),
            'ms_msg_wait_facilities': Param(type=int, size=1),
            'number_of_messages': Param(type=int, size=1),
            'alert_on_message_delivery': Param(type=flag),
            'language_indicator': Param(type=int, size=1),
            'its_reply_type': Param(type=int, size=1),
            'its_session_info': Param(type=int, size=2),
            'ussd_service_op': Param(type=int, size=1),
        }

        params_order = (
            'service_type', 'source_addr_ton', 'source_addr_npi',
            'source_addr', 'dest_addr_ton', 'dest_addr_npi',
            'destination_addr', 'esm_class', 'protocol_id', 'priority_flag',
            'schedule_delivery_time', 'validity_period', 'registered_delivery',
            'replace_if_present_flag', 'data_coding', 'sm_default_msg_id',
            'sm_length', 'short_message',

            # Optional params
            'user_message_reference', 'source_port', 'source_addr_subunit',
            'destination_port', 'dest_addr_subunit', 'sar_msg_ref_num',
            'sar_total_segments', 'sar_segment_seqnum', 'more_messages_to_send',
            'payload_type', 'message_payload', 'privacy_indicator',
            'callback_num', 'callback_num_pres_ind', 'source_subaddress',
            'dest_subaddress', 'user_response_code', 'display_time',
            'sms_signal', 'ms_validity', 'ms_msg_wait_facilities',
            'number_of_messages', 'alert_on_message_delivery',
            'language_indicator', 'its_reply_type', 'its_session_info',
            'ussd_service_op',
        )

        def __init__(self, command, **kwargs):
            super(SubmitSM, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))

        def prep(self):
            """Prepare to generate binary data"""

            if self.short_message:
                if getattr(self, 'message_payload', None):
                    raise ValueError('`message_payload` can not be used with `short_message`')
                self.sm_length = len(self.short_message)
            else:
                self.sm_length = 0


    class SubmitSMResp(Command):
        """Response command for submit_sm"""

        params = {
            'message_id': Param(type=str, max=65),
        }

        params_order = ('message_id',)

        def __init__(self, command, **kwargs):
            super(SubmitSMResp, self).__init__(command, need_sequence=False, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    class DeliverSM(SubmitSM):
        """deliver_sm command class, similar to submit_sm
        but has different optional params"""

        params = {
            'service_type': Param(type=str, max=6),
            'source_addr_ton': Param(type=int, size=1),
            'source_addr_npi': Param(type=int, size=1),
            'source_addr': Param(type=str, max=21),
            'dest_addr_ton': Param(type=int, size=1),
            'dest_addr_npi': Param(type=int, size=1),
            'destination_addr': Param(type=str, max=21),
            'esm_class': Param(type=int, size=1),
            'protocol_id': Param(type=int, size=1),
            'priority_flag': Param(type=int, size=1),
            'schedule_delivery_time': Param(type=str, max=17),
            'validity_period': Param(type=str, max=17),
            'registered_delivery': Param(type=int, size=1),
            'replace_if_present_flag': Param(type=int, size=1),
            'data_coding': Param(type=int, size=1),
            'sm_default_msg_id': Param(type=int, size=1),
            'sm_length': Param(type=int, size=1),
            'short_message': Param(type=ostr, max=254, len_field='sm_length'),

            # Optional params
            'user_message_reference': Param(type=int, size=2),
            'source_port': Param(type=int, size=2),
            'destination_port': Param(type=int, size=2),
            'sar_msg_ref_num': Param(type=int, size=2),
            'sar_total_segments': Param(type=int, size=1),
            'sar_segment_seqnum': Param(type=int, size=1),
            'user_response_code': Param(type=int, size=1),
            'privacy_indicator': Param(type=int, size=1),
            'payload_type': Param(type=int, size=1),
            'message_payload': Param(type=ostr, max=260),
            'callback_num': Param(type=ostr, min=4, max=19),
            'source_subaddress': Param(type=str, min=2, max=23),
            'dest_subaddress': Param(type=str, min=2, max=23),
            'language_indicator': Param(type=int, size=1),
            'its_session_info': Param(type=int, size=2),
            'network_error_code': Param(type=ostr, size=3),
            'message_state': Param(type=int, size=1),
            'receipted_message_id': Param(type=str, max=65),
            'source_network_type': Param(type=int, size=1),
            'dest_network_type': Param(type=int, size=1),
            'more_messages_to_send': Param(type=int, size=1),
        }

        params_order = (
            'service_type', 'source_addr_ton', 'source_addr_npi',
            'source_addr', 'dest_addr_ton', 'dest_addr_npi',
            'destination_addr', 'esm_class', 'protocol_id', 'priority_flag',
            'schedule_delivery_time', 'validity_period', 'registered_delivery',
            'replace_if_present_flag', 'data_coding', 'sm_default_msg_id',
            'sm_length', 'short_message',

            # Optional params
            'user_message_reference', 'source_port', 'destination_port',
            'sar_msg_ref_num', 'sar_total_segments', 'sar_segment_seqnum',
            'user_response_code', 'privacy_indicator',
            'payload_type', 'message_payload',
            'callback_num', 'source_subaddress',
            'dest_subaddress', 'language_indicator', 'its_session_info',
            'network_error_code', 'message_state', 'receipted_message_id',
            'source_network_type', 'dest_network_type', 'more_messages_to_send',
        )

        def __init__(self, command, **kwargs):
            super(DeliverSM, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    class DeliverSMResp(SubmitSMResp):
        """deliver_sm_response response class, same as submit_sm"""
        message_id = None

        def __init__(self, command, **kwargs):
            super(DeliverSMResp, self).__init__(command, **kwargs)


    class QuerySM(Command):
        """query_sm command class

        This command is used by an ESME to query the state of a short message to the SMSC.
        source_addr* values must match those supplied when the message was submitted."""

        # Message ID of the message whose state is to be queried.
        message_id = None

        # Type of Number for source address
        source_addr_ton = None

        # Numbering Plan Indicator for source address
        source_addr_npi = None

        # Address of SME which originated this message
        source_addr = None

        # Optional are taken from params list and are set dynamically when
        # __init__ is called.
        params = {
            'message_id': Param(type=str, max=65),
            'source_addr_ton': Param(type=int, size=1),
            'source_addr_npi': Param(type=int, size=1),
            'source_addr': Param(type=str, max=21),
        }

        params_order = (
            'message_id', 'source_addr_ton', 'source_addr_npi',
            'source_addr',
        )

        def __init__(self, command, **kwargs):
            super(QuerySM, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))

        def prep(self):
            """Prepare to generate binary data"""

            if not self.message_id:
                raise ValueError('`message_id` is mandatory')


    class QuerySMResp(Command):
        """Response command for query_sm"""

        mandatory_fields = ('message_state')

        params = {
            'message_id': Param(type=str, max=65),
            'final_date': Param(type=str, max=17),
            'message_state': Param(type=int, size=1),
            'error_code': Param(type=int, size=1),
        }

        params_order = (
            'message_id', 'final_date', 'message_state',
            'error_code',
        )

        def __init__(self, command, **kwargs):
            super(QuerySMResp, self).__init__(command, need_sequence=False, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    class Unbind(Command):
        """Unbind command"""

        params = {}
        params_order = ()

        def __init__(self, command, **kwargs):
            super(Unbind, self).__init__(command, **kwargs)


    class UnbindResp(Command):
        """Unbind response command"""

        params = {}
        params_order = ()

        def __init__(self, command, **kwargs):
            super(UnbindResp, self).__init__(command, need_sequence=False, **kwargs)


    class EnquireLink(Command):
        """Enquire link command"""
        params = {}
        params_order = ()

        def __init__(self, command, **kwargs):
            super(EnquireLink, self).__init__(command, **kwargs)


    class EnquireLinkResp(Command):
        """Enquire link command response"""
        params = {}
        params_order = ()

        def __init__(self, command, **kwargs):
            super(EnquireLinkResp, self).__init__(command, need_sequence=False, **kwargs)


    class AlertNotification(Command):
        """`alert_notification` command class"""

        # Type of Number for source address
        source_addr_ton = None

        # Numbering Plan Indicator for source address
        source_addr_npi = None

        # Address of SME which originated this message
        source_addr = None

        # TON for destination
        esme_addr_ton = None

        # NPI for destination
        esme_addr_npi = None

        # Destination address for this message
        esme_addr = None

        # Optional are taken from params list and are set dynamically when
        # __init__ is called.
        params = {
            'source_addr_ton': Param(type=int, size=1),
            'source_addr_npi': Param(type=int, size=1),
            'source_addr': Param(type=str, max=21),
            'esme_addr_ton': Param(type=int, size=1),
            'esme_addr_npi': Param(type=int, size=1),
            'esme_addr': Param(type=str, max=21),

            # Optional params
            'ms_availability_status': Param(type=int, size=1),
        }

        params_order = (
            'source_addr_ton', 'source_addr_npi',
            'source_addr', 'esme_addr_ton', 'esme_addr_npi',
            'esme_addr',

            # Optional params
            'ms_availability_status',
        )

        def __init__(self, command, **kwargs):
            super(AlertNotification, self).__init__(command, **kwargs)
            self._set_vars(**(dict.fromkeys(self.params)))


    parser = argparse.ArgumentParser(description='Fake SMSC Server')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    parser.add_argument('--port', type=int, default=2776, help='Bind port')
    parser.add_argument('--dlr-delay', type=int, default=5, help='DLR delay in seconds')
    args = parser.parse_args()
    
    smsc = FakeSMSC(
        host=args.host,
        port=args.port,
        dlr_delay=args.dlr_delay
    )
    
    try:
        asyncio.run(smsc.run())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)