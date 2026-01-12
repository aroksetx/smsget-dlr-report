import pika
import pickle
from datetime import datetime

from smpplib.command import DeliverSM
from smpplib.consts import SMPP_TON_INTL, SMPP_NPI_ISDN

# =====================
# RabbitMQ config
# =====================
RABBITMQ_HOST = '52.57.134.177'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'

SUBMIT_QUEUE = 'submit.sm.default_dummy'
DLR_QUEUE = 'deliver_sm_thrower'

DLR_STATUS = 'DELIVRD'
DLR_ERROR = 0

# =====================
# DLR builder
# =====================



def get_attr(obj, *names):
    for name in names:
        if hasattr(obj, name):
            val = getattr(obj, name)
            if val is not None:
                return val
    return None


def resolve_msgid(submit_sm):
    return (
        get_attr(
            submit_sm,
            'msgid',
            'message_id',
            'receipted_message_id',
            'id',
            'sequence',
        )
        or f"gen-{int(datetime.now().timestamp())}"
    )


def resolve_addresses(submit_sm):
    src = get_attr(
        submit_sm,
        'destination_addr',
        'dest_addr',
        'dst_addr',
        'to'
    )

    dst = get_attr(
        submit_sm,
        'source_addr',
        'src_addr',
        'from_addr',
        'from_'
    )

    return src, dst


def build_dlr(submit_sm, status='DELIVRD', error=0):
    msgid = str(resolve_msgid(submit_sm))
    src, dst = resolve_addresses(submit_sm)

    text = get_attr(submit_sm, 'short_message', 'message', 'text') or b''

    ts = datetime.now().strftime('%y%m%d%H%M')

    dlr_text = (
        f"id:{msgid} sub:001 dlvrd:001 "
        f"submit date:{ts} done date:{ts} "
        f"stat:{status} err:{error:03d} "
        f"text:{text[:20].decode(errors='ignore')}"
    )

    return DeliverSM(
        'deliver_sm',
        sequence=int(get_attr(submit_sm, 'sequence') or 1),

        # 🔴 REQUIRED BY JASMIN
        receipted_message_id=msgid,

        source_addr=src or b'',
        destination_addr=dst or b'',
        short_message=dlr_text.encode(),

        source_addr_ton=SMPP_TON_INTL,
        source_addr_npi=SMPP_NPI_ISDN,
        dest_addr_ton=SMPP_TON_INTL,
        dest_addr_npi=SMPP_NPI_ISDN,

        esm_class=0x04,        # DLR
        message_state=2,       # DELIVERED (SMPP enum)
    )
# =====================
# Publish DLR
# =====================
def publish_dlr(channel, dlr_pdu):
    payload = {
        'pdu': dlr_pdu,
        'uid': 'dlr-worker',
        'route_type': 'dlr',
    }

    channel.basic_publish(
        exchange='',
        routing_key=DLR_QUEUE,
        body=pickle.dumps(payload),
        properties=pika.BasicProperties(delivery_mode=2),
    )

# =====================
# Callback
# =====================
def on_message(ch, method, properties, body):
    try:
        submit_sm = pickle.loads(body)

        dlr = build_dlr(submit_sm)
        publish_dlr(ch, dlr)

        ch.basic_ack(method.delivery_tag)

    except Exception as e:
        print('DLR ERROR:', e)
        ch.basic_nack(method.delivery_tag, requeue=False)

# =====================
# Main
# =====================
def main():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                RABBITMQ_USER, RABBITMQ_PASS
            ),
            heartbeat=600,
        )
    )

    channel = connection.channel()
    channel.basic_qos(prefetch_count=50)

    channel.basic_consume(
        queue=SUBMIT_QUEUE,
        on_message_callback=on_message,
        auto_ack=False,
    )

    print('🚀 DLR worker started')
    channel.start_consuming()

if __name__ == '__main__':
    main()