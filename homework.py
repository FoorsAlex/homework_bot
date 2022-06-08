import logging
import os
import time
from http import HTTPStatus
from json import JSONDecodeError
import datetime as dt
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

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
TOKENS = (
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s, %(levelname)s, %(message)s',
                    filename='logger.log')


def send_message(bot, message):
    """Отправляет смс."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info('Сообщение успешно отправлено')
        return True
    except Exception as error:
        logging.error(error, exc_info=True)
        return False


def get_api_answer(current_timestamp):
    """Делает запрос к API."""
    timestamp = current_timestamp or int(time.time())
    time_delta = dt.timedelta(days=7)
    time_delta_seconds = int(time_delta.total_seconds())
    params = {'from_date': timestamp-time_delta_seconds}
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
        message = 'JSON conversion error'
        logging.error(message)
        raise Exception(message)
    except Exception as error:
        message = f'API error: {error}'
        logging.error(message)
        raise Exception(message)
    finally:
        logging.info('Запрос к API прошел успешно')


def check_response(response):
    """Проверяет полученный ответ API."""
    key = 'homeworks'
    if not response[key]:
        message = 'Ключик homeworks отсутсвует в словарике :('
        raise KeyError(message)
    if ((not isinstance(response, dict))
            or (not isinstance(response[key], list))):
        message = 'Ответ API не является словарем'
        raise TypeError(message)

    return response[key]


def parse_status(homework):
    """Извлекает статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if (homework_status or homework_name) is None:
        message = ('''Ошибочка с ключем (не получилось достать'''
                   '''имя или статус работы)''')
        logging.error(message)
        raise KeyError(message)
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
    else:
        message = 'Неожиданный статус'
        logging.error(message)
        raise KeyError(message)
    return (f'Изменился статус проверки работы "'
            f'{homework_name}". {verdict}')


def check_tokens():
    """Проверяет наличие токенов."""
    for name in TOKENS:
        token = globals()[name]
        if token is None or token == '':
            logging.critical(f'Отсутсвует токен: {name}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    old_error_message = ''
    old_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if len(response['homeworks']) == 0:
                error_message = 'Список работ пуст'
                logging.error(error_message)
                raise KeyError(error_message)
            homework = check_response(response)
            message = parse_status(homework[0])
            if message != old_message:
                if send_message(bot, message):
                    old_message = message
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            logging.error(error, exc_info=True)
            error_message = f'Сбой в работе программы: {error}'
            if error_message != old_error_message and error != 'Список работ пуст':
                if send_message(bot, error_message):
                    old_error_message = error_message
            time.sleep(RETRY_TIME)
        else:
            time.sleep(1000)


if __name__ == '__main__':
    main()
