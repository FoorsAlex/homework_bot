import logging
import os
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s, %(levelname)s, %(message)s',
                    filename='logger.log')


def send_message(bot, message):
    """Отправляет смс."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправлено')
    except Exception as error:
        logging.error(error, exc_info=True)
        raise error


def get_api_answer(current_timestamp):
    """Делает запрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Код ответа не равен 200'
            logging.error(message)
            raise Exception(message)
        return response.json()
    except requests.exceptions.RequestException:
        message = 'Endpoint не доступен'
        logging.error(message)
        raise Exception(message)
    except JSONDecodeError:
        logging.error('JSON conversion error')
        raise Exception('JSON conversion error')
    except Exception as error:
        message = f'API error: {error}'
        logging.error(message)
        raise Exception(message)
    finally:
        logging.info('Запрос к API прошел успешно')


def check_response(response):
    """
    Проверяет полученный ответ API
    на соответствие ожидаемому типу данных.
     """
    if ((not isinstance(response, dict))
            or (not isinstance(response['homeworks'], list))):
        message = 'Ответ API не является словарем'
        raise TypeError(message)

    return response['homeworks']


def parse_status(homework):
    """Извлекает статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    elif homework_status is None:
        logging.error('Отсутсвует статус')
        raise KeyError('Отсутсвует статус')
    else:
        logging.error('Неожиданный статус')
        raise KeyError('Неожиданный статус')
    return (f'Изменился статус проверки работы "'
            f'{homework_name}". {verdict}')


def check_tokens():
    """Проверяет наличие токенов."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        message = 'Отсутствует обязательная переменная окружения:'
        if not PRACTICUM_TOKEN:
            logging.critical(f'{message} "PRACTICUM_TOKEN"')
        if not TELEGRAM_TOKEN:
            logging.critical(f'{message} "TELEGRAM_TOKEN"')
        if not TELEGRAM_CHAT_ID:
            logging.critical(f'{message} "TELEGRAM_CHAT_ID"')

        return False


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    old_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if len(response['homeworks']) == 0:
                message = 'Список работ пуст'
                logging.error(message)
                raise KeyError(message)
            homework = check_response(response)
            message = parse_status(homework)
            if message != old_message:
                send_message(bot, message)
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(error, exc_info=True)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(1000)


if __name__ == '__main__':
    main()
