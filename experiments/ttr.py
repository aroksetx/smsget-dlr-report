from smpplib.client import Client
from smpplib.command import DeliverSM
from smpplib.consts import (
    SMPP_TON_INTL,
    SMPP_NPI_ISDN,
    CMD_DELIVER_SM,
)

client = Client('52.57.134.177', 2775)
client.connect()

client.bind_transceiver(
    system_id='teamclussender',
    password='xrQrb9iP'
)

print("BIND OK")

# 🔥 КЛЮЧЕВОЕ: command передаётся ЯВНО
pdu = DeliverSM(
    command=CMD_DELIVER_SM,
    source_addr_ton=SMPP_TON_INTL,
    source_addr_npi=SMPP_NPI_ISDN,
    source_addr='8801710322203',
    dest_addr_ton=SMPP_TON_INTL,
    dest_addr_npi=SMPP_NPI_ISDN,
    destination_addr='12345',
    esm_class=0x00,  # MO (НЕ DLR)
    short_message=b'Hello MO message - trigger webhook',
)

client.send_pdu(pdu)

print("DELIVER_SM sent → webhook SHOULD fire")

client.unbind()
client.disconnect()