from smpplib.client import Client
from smpplib.consts import (
    SMPP_TON_ALNUM,
    SMPP_NPI_UNK,
    SMPP_TON_INTL,
    SMPP_NPI_ISDN,
)

JASMIN_HOST = "52.57.134.177"
JASMIN_PORT = 2775

SYSTEM_ID = "teamclussender"
PASSWORD = "xrQrb9iP"


def message_sent_handler(pdu):
    print("📨 submit_sm_resp received")
    print("REAL message_id:", pdu.message_id)

def main():
    client = Client(JASMIN_HOST, JASMIN_PORT)
    client.set_message_sent_handler(message_sent_handler)

    # connect + bind
    client.connect()
    client.bind_transceiver(
        system_id=SYSTEM_ID,
        password=PASSWORD,
    )

    print("✅ BIND OK")

    # send MT (submit_sm)
    pdu = client.send_message(
        source_addr_ton=SMPP_TON_ALNUM,
        source_addr_npi=SMPP_NPI_UNK,
        source_addr="TEST",

        dest_addr_ton=SMPP_TON_INTL,
        dest_addr_npi=SMPP_NPI_ISDN,
        destination_addr="1231",

        short_message=b"Hello from submit_sm test",
        registered_delivery=True,
    )

    client.unbind()
    client.disconnect()

    print("🔌 disconnected")


if __name__ == "__main__":
    main()