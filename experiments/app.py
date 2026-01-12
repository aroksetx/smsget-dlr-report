import time

from smpplib.client import Client
from smpplib.consts import SMPP_TON_ALNUM, SMPP_NPI_UNK

def send_dlr(message_id, status):
    client = Client('52.57.134.177', 2775)
    client.connect()
    client.bind_transceiver(system_id='smsc_dlr', password='c75BgBnH')

    stat = 'DELIVRD'
    err = '000'
    dlvrd = '001'

    if status != 'ok':
        stat = 'UNDELIV'
        err = '001'
        dlvrd = '000'

    short_message = (
        f"id:{message_id} sub:001 dlvrd:{dlvrd} "
        f"submit date:260102161444 done date:260102161447 "
        f"stat:{stat} err:{err} text:test"
    )

    client.send_message(
        source_addr_ton=SMPP_TON_ALNUM,
        source_addr_npi=SMPP_NPI_UNK,
        source_addr='SMSC',
        dest_addr_ton=1,
        dest_addr_npi=1,
        destination_addr='8801766571244',
        esm_class=0x04,  # 🔥 DLR
        short_message=short_message.encode()
    )

    print("DLR sent:", stat)
    client.unbind()
    time.sleep(0.2)
    client.disconnect()

# ok | fail
send_dlr("7d167676-fc5f-40cc-9d79-0fb85148050f", "ok")
# send_dlr("7d167676-fc5f-40cc-9d79-0fb85148050f", "fail")