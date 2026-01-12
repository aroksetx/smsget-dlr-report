import smpplib.gsm
import smpplib.client
import smpplib.consts
import sys
from datetime import datetime

# SMPP Configuration
HOST = '52.57.134.177'
PORT = 2775
SYSTEM_ID = 'teamclussender'
PASSWORD = 'xrQrb9iP'
SYSTEM_TYPE = ''
ADDR_TON = smpplib.consts.SMPP_TON_INTL
ADDR_NPI = smpplib.consts.SMPP_NPI_ISDN


def send_sms(source_addr, destination_addr, message):
    """Send SMS via SMPP and return message ID"""

    client = None
    message_ids = []

    try:
        # Create SMPP client
        client = smpplib.client.Client(HOST, PORT, timeout=30)

        print(f"🔌 Connecting to {HOST}:{PORT}...")

        # Connect and bind
        client.connect()
        client.bind_transmitter(
            system_id=SYSTEM_ID,
            password=PASSWORD,
            system_type=SYSTEM_TYPE
        )

        print(f"✅ Connected and bound as transmitter")
        print(f"📤 Sending SMS...")
        print(f"   From: {source_addr}")
        print(f"   To: {destination_addr}")
        print(f"   Message: {message}")
        print()

        # Split message into parts if needed
        parts, encoding_flag, msg_type_flag = smpplib.gsm.make_parts(message)

        print(f"📝 Message split into {len(parts)} part(s)")

        for i, part in enumerate(parts, 1):
            pdu = client.send_message(
                source_addr_ton=ADDR_TON,
                source_addr_npi=ADDR_NPI,
                source_addr=source_addr,
                dest_addr_ton=ADDR_TON,
                dest_addr_npi=ADDR_NPI,
                destination_addr=destination_addr,
                short_message=part,
                data_coding=encoding_flag,
                esm_class=msg_type_flag,
                registered_delivery=True,
            )

            # Try to extract message ID
            msg_id = None
            if hasattr(pdu, 'message_id'):
                msg_id = pdu.message_id
            elif hasattr(pdu, 'receipted_message_id'):
                msg_id = pdu.receipted_message_id
            elif hasattr(pdu, 'sequence'):
                msg_id = pdu.sequence

            # Generate a timestamp-based ID if none found
            if not msg_id:
                msg_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{i}"

            message_ids.append(msg_id)

            print(f"✅ Part {i}/{len(parts)} sent successfully")
            print(f"   🆔 Message ID: {msg_id}")
            print(f"   📦 PDU Type: {type(pdu).__name__}")
            print()

        return message_ids

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        if client:
            try:
                client.unbind()
                client.disconnect()
                print("✅ Disconnected from SMPP server\n")
            except:
                pass


if __name__ == "__main__":
    # Get parameters from command line or use defaults
    if len(sys.argv) >= 4:
        source = sys.argv[1]
        destination = sys.argv[2]
        message_text = sys.argv[3]
    else:
        source = "1234"
        destination = "9876543210"
        message_text = "Hello from SMPP! This is a test message with ID tracking."

    print("=" * 60)
    print("📨 SMPP Message Sender")
    print("=" * 60)
    print()

    message_ids = send_sms(source, destination, message_text)

    if message_ids:
        print("=" * 60)
        print("✅ SUCCESS!")
        print("=" * 60)
        print(f"📊 Total Message IDs: {len(message_ids)}")
        for i, mid in enumerate(message_ids, 1):
            print(f"   {i}. {mid}")
        print()
        print("💡 Now run the consumer to see the message in RabbitMQ:")
        print("   python3 consume_messages.py")
        print("=" * 60)
    else:
        print("❌ Failed to send message")
        sys.exit(1)