import time
from smpplib.client import Client
from smpplib.consts import (
    SMPP_TON_INTL,
    SMPP_NPI_ISDN,
    SMPP_ESM_CLASS_SMSC_DELIVERY_RECEIPT,
    SMPP_MESSAGE_STATE_DELIVERED,
)
from smpplib.command import DeliverSM
from smpplib.consts import SMPP_CMD_DELIVER_SM

JASMIN_HOST = "52.57.134.177"
JASMIN_PORT = 2775

SYSTEM_ID = "teamclussender"
PASSWORD = "xrQrb9iP"

MESSAGE_ID = "f5d11919-e448-417a-9e76-38fd8b9cd8ca"

client = Client(JASMIN_HOST, JASMIN_PORT)
client.connect()
client.bind_transceiver(system_id=SYSTEM_ID, password=PASSWORD)

dlr_text = (
    f"id:{MESSAGE_ID} "
    f"sub:001 dlvrd:001 "
    f"submit date:{time.strftime('%y%m%d%H%M')} "
    f"done date:{time.strftime('%y%m%d%H%M')} "
    f"stat:DELIVRD err:000 text:"
)

# ⚠️ КЛЮЧЕВОЙ МОМЕНТ
pdu = DeliverSM(
    SMPP_CMD_DELIVER_SM,   # command_id ОБЯЗАТЕЛЕН
    client=client,        # <-- БЕЗ ЭТОГО ВСЁ ЛОМАЕТСЯ
    source_addr_ton=SMPP_TON_INTL,
    source_addr_npi=SMPP_NPI_ISDN,
    source_addr=b"SMSC",
    dest_addr_ton=SMPP_TON_INTL,
    dest_addr_npi=SMPP_NPI_ISDN,
    destination_addr=SYSTEM_ID.encode(),
    short_message=dlr_text.encode(),
    esm_class=SMPP_ESM_CLASS_SMSC_DELIVERY_RECEIPT,
)

# TLV — ОБЯЗАТЕЛЬНО
pdu.params["receipted_message_id"] = MESSAGE_ID.encode()
pdu.params["message_state"] = SMPP_MESSAGE_STATE_DELIVERED

client.send_pdu(pdu)

print("✅ DLR sent & matched:", MESSAGE_ID)

client.unbind()
client.disconnect()