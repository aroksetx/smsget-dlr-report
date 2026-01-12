from smpplib.client import Client
from smpplib import consts
from smpplib.command import DeliverSM

client = Client('52.57.134.177', 2775)

client.connect()
client.bind_transceiver(
    system_id='teamclussender',
    password='xrQrb9iP'
)

pdu = DeliverSM(
    'deliver_sm',          # command — СТРОКА
    client=client,

    service_type=b'',      # 🔴 КЛЮЧЕВО (иначе str → bytes crash)

    source_addr_ton=consts.SMPP_TON_INTL,
    source_addr_npi=consts.SMPP_NPI_ISDN,
    source_addr=b'447700900123',

    dest_addr_ton=consts.SMPP_TON_INTL,
    dest_addr_npi=consts.SMPP_NPI_ISDN,
    destination_addr=b'447700900999',

    esm_class=consts.SMPP_MSGMODE_DEFAULT,   # 0x00
    data_coding=consts.SMPP_ENCODING_DEFAULT,

    short_message=b'Test OTP 1234',
)

client.send_pdu(pdu)
print("✅ deliver_sm (MO) sent")

client.unbind()
client.disconnect()