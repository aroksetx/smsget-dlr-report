import pika
import json
import sys
import pickle
from datetime import datetime

# Configuration
RABBITMQ_HOST = '52.57.134.177'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'guest'
RABBITMQ_PASS = 'guest'
QUEUE_NAME = 'submit.sm.dummy_smpp'


class MessageConsumer:
    def __init__(self):
        self.message_counter = 0
        self.connection = None
        self.channel = None

    def extract_message_id(self, data):
        """Extract message ID from various formats"""
        message_id = None

        # Try different attribute names
        id_fields = ['id', 'message_id', 'msgid', 'msg_id', 'sequence', 'sequence_number']

        if hasattr(data, '__dict__'):
            for field in id_fields:
                if hasattr(data, field):
                    message_id = getattr(data, field)
                    if message_id:
                        return message_id

        if isinstance(data, dict):
            for field in id_fields:
                if field in data:
                    message_id = data[field]
                    if message_id:
                        return message_id

        return message_id

    def parse_message(self, body):
        """Parse message from different formats"""
        message_data = {
            'id': None,
            'from': None,
            'to': None,
            'content': None,
            'raw': None
        }

        # Try pickle first (Jasmin format)
        try:
            data = pickle.loads(body)
            message_data['raw'] = data
            message_data['id'] = self.extract_message_id(data)

            # Try to extract common fields
            if hasattr(data, 'source_addr'):
                message_data['from'] = data.source_addr
            if hasattr(data, 'destination_addr'):
                message_data['to'] = data.destination_addr
            if hasattr(data, 'short_message'):
                message_data['content'] = data.short_message

            return message_data, 'pickle'

        except:
            pass

        # Try JSON
        try:
            text = body.decode('utf-8')
            data = json.loads(text)
            message_data['raw'] = data
            message_data['id'] = self.extract_message_id(data)

            message_data['from'] = data.get('from') or data.get('source')
            message_data['to'] = data.get('to') or data.get('destination')
            message_data['content'] = data.get('content') or data.get('message')

            return message_data, 'json'

        except:
            pass

        # Plain text
        try:
            text = body.decode('utf-8')
            message_data['raw'] = text
            message_data['content'] = text
            return message_data, 'text'
        except:
            pass

        # Binary
        message_data['raw'] = body
        return message_data, 'binary'

    def callback(self, ch, method, properties, body):
        """Process incoming message"""
        self.message_counter += 1

        try:
            # Parse message
            msg_data, msg_format = self.parse_message(body)

            # Display message
            print("\n" + "=" * 70)
            print(f"📨 MESSAGE #{self.message_counter} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 70)

            # Message ID (most important)
            if msg_data['id']:
                print(f"🆔 MESSAGE ID: {msg_data['id']}")
            else:
                print(f"⚠️  MESSAGE ID: Not found")

            # Content
            if msg_data['from']:
                print(f"📤 FROM: {msg_data['from']}")
            if msg_data['to']:
                print(f"📥 TO: {msg_data['to']}")
            if msg_data['content']:
                print(f"💬 CONTENT: {msg_data['content']}")

            # Metadata
            print(f"\n📋 METADATA:")
            print(f"   Format: {msg_format}")
            print(f"   Delivery Tag: {method.delivery_tag}")
            print(f"   Routing Key: {method.routing_key}")
            print(f"   Exchange: {method.exchange or '(default)'}")

            # Properties
            if properties.message_id:
                print(f"   Property Message ID: {properties.message_id}")
            if properties.correlation_id:
                print(f"   Correlation ID: {properties.correlation_id}")
            if properties.content_type:
                print(f"   Content Type: {properties.content_type}")

            # Raw data (verbose)
            print(f"\n🔍 RAW DATA:")
            if hasattr(msg_data['raw'], '__dict__'):
                for key, value in msg_data['raw'].__dict__.items():
                    print(f"   {key}: {value}")
            elif isinstance(msg_data['raw'], dict):
                for key, value in msg_data['raw'].items():
                    print(f"   {key}: {value}")
            else:
                print(f"   {msg_data['raw']}")

            print("=" * 70)

            # Acknowledge and remove
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print("✅ Message acknowledged and removed from queue\n")

        except Exception as e:
            print(f"\n❌ Error processing message: {e}")
            import traceback
            traceback.print_exc()
            # Remove even on error
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            print("❌ Message rejected and removed\n")

    def start(self):
        """Start consuming messages"""
        try:
            # Connect
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )

            print("=" * 70)
            print("🐰 RabbitMQ Message Consumer")
            print("=" * 70)
            print(f"🔌 Connecting to {RABBITMQ_HOST}:{RABBITMQ_PORT}...")

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # Check queue
            try:
                result = self.channel.queue_declare(queue=QUEUE_NAME, passive=True)
                message_count = result.method.message_count

                print(f"✅ Connected successfully!")
                print(f"📬 Queue: {QUEUE_NAME}")
                print(f"📊 Messages waiting: {message_count}")
                print(f"🗑️  Mode: Consume and remove")
                print("\n👂 Listening for new messages... (Press Ctrl+C to stop)\n")

            except pika.exceptions.ChannelClosedByBroker:
                print(f"❌ Queue '{QUEUE_NAME}' does not exist!")
                print("\n💡 Available queues:")
                print("   docker-compose exec rabbit-mq rabbitmqctl list_queues")
                sys.exit(1)

            # Start consuming
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=self.callback,
                auto_ack=False
            )

            self.channel.start_consuming()

        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("👋 Stopping consumer...")
            print(f"📊 Total messages processed: {self.message_counter}")
            print("=" * 70)
            self.stop()
            sys.exit(0)

        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
            self.stop()
            sys.exit(1)

    def stop(self):
        """Stop and cleanup"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("✅ Disconnected from RabbitMQ")


if __name__ == "__main__":
    consumer = MessageConsumer()
    consumer.start()