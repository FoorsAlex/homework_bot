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

HOMEWORK_VERDICTS = {
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
    tokens_value = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    message = 'Отсутствует обязательная переменная окружения:'
    for token in tokens_value:
        if not tokens_value[token]:
            logging.critical(f'{message} {token}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    old_error_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if len(response['homeworks']) == 0:
                error_message = 'Список работ пуст'
                logging.error(error_message)
                raise KeyError(error_message)
            homework = check_response(response)
            message = parse_status(homework[0])
            send_message(bot, message)
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            logging.error(error, exc_info=True)
            error_message = f'Сбой в работе программы: {error}'
            if error_message != old_error_message:
                old_error_message = error_message
                send_message(bot, error_message)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(1000)


if __name__ == '__main__':
    main()
