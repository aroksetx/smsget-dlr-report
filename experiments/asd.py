import logging
import smpplib.gsm
import smpplib.client
import smpplib.consts

# Настройки подключения к Jasmin SMPP
HOST = '52.57.134.177'  # IP вашего сервера Jasmin
PORT = 2775  # Стандартный SMPP порт Jasmin
SYSTEM_ID = 'fulluser'  # Ваш smppcid (username)
PASSWORD = 'xrQrb9iP'  # Ваш password
SOURCE_TON = smpplib.consts.SMPP_TON_ALNUM
SOURCE_NPI = smpplib.consts.SMPP_NPI_UNK
DEST_TON = smpplib.consts.SMPP_TON_INTL
DEST_NPI = smpplib.consts.SMPP_NPI_ISDN
DEST_NUMBER = '79123456789'

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def send_smpp_test():
    client = smpplib.client.Client(HOST, PORT)

    # 1. Обработка SubmitSMResp (Ответ сервера на нашу отправку)
    # Здесь мы получаем ID сообщения, который присвоил Jasmin
    def handle_sent_sm(pdu):
        if pdu.status == smpplib.consts.SMPP_ESME_ROK:
            # message_id в ответе — это байты
            msg_id = pdu.message_id.decode() if pdu.message_id else "unknown"
            print(f"\n[OK] Сообщение принято сервером. Jasmin Message ID: {msg_id}")
        else:
            print(f"\n[ERROR] Ошибка отправки! Статус: {pdu.status}")

    # 2. Обработка DeliverSM (Delivery Report / DLR)
    def handle_deliver_sm(pdu):
        print(f"\n[+] ПОЛУЧЕН DELIVERY REPORT (DLR):")
        try:
            # Текст отчета (содержит статус DELIVRD, EXPIRED и т.д.)
            content = pdu.short_message.decode('utf-8', errors='ignore')
            print(f"Данные DLR: {content}")
        except Exception as e:
            print(f"Ошибка декодирования DLR: {e}")

    # Регистрируем обработчики
    client.set_message_sent_handler(handle_sent_sm)
    client.set_message_received_handler(handle_deliver_sm)

    try:
        # Подключение
        print(f"Подключение к {HOST}:{PORT}...")
        client.connect()
        client.bind_transceiver(system_id=SYSTEM_ID, password=PASSWORD)

        # Подготовка текста
        text = 'Test DLR Jasmin 2026'
        parts, encoding, esm_class = smpplib.gsm.make_parts(text)

        for part in parts:
            # Отправка
            # registered_delivery=1 запрашивает отчет о доставке
            client.send_message(
                source_addr_ton=SOURCE_TON,
                source_addr_npi=SOURCE_NPI,
                source_addr='TEST_SENDER',
                dest_addr_ton=DEST_TON,
                dest_addr_npi=DEST_NPI,
                destination_addr=DEST_NUMBER,
                short_message=part,
                data_coding=encoding,
                esm_class=esm_class,
                registered_delivery=1,
            )

        print("\n[*] Ожидание ответов и DLR. Нажмите Ctrl+C для выхода.")
        # Бесконечный цикл прослушивания сокета
        client.listen()

    except KeyboardInterrupt:
        print("\n[!] Остановка пользователем...")
    except Exception as e:
        print(f"\n[FATAL] Произошла ошибка: {e}")
    finally:
        if client.state != smpplib.consts.SMPP_CLIENT_STATE_CLOSED:
            client.disconnect()
            print("[*] Соединение закрыто.")


if __name__ == '__main__':
    send_smpp_test()