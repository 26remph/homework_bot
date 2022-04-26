import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import BadRequest

from exceptions import (APIResponseError, JSONDataStructureError,
                        LoadEnvironmentError, SendMessageError,
                        UndocumentedStatusError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# RETRY_TIME = 600
RETRY_TIME = 30

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
# ENDPOINT = 'https://api.thecatapi.com/v1/images/search'

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
HOMEWORK_STATES = {}

logging.basicConfig(
    format='%(asctime)s | %(name)s | %(levelname)s | '
           '%(funcName)s | %(message)s',
    level=logging.DEBUG,
)


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except BadRequest as e:
        raise SendMessageError(e) from e


def get_api_answer(current_timestamp):
    """Получает ответ от сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except ConnectionError as e:
        raise APIResponseError(e) from e

    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(f'Неожиданный статус ответа: {response}')

    return response


def check_response(response):
    """Проверят корректность ответа сервиса, и отдает список домашних работ."""
    data = response.json()
    if type(data) != dict:
        raise JSONDataStructureError(
            f'Принят неожиданный тип данных {type(data)}, ожидается {dict}'
        )

    try:
        homeworks = data['homeworks']
        current_date = ['current_date']
    except TypeError as e:
        raise JSONDataStructureError(f'Данные не содержат ключа: {e}')

    return homeworks, current_date


def parse_status(homework):
    """Извлекает статус проверки домашней работы и возвращает его."""
    # homework_id = homework.get('id')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if not(homework_status in HOMEWORK_STATUSES.keys()):
        raise UndocumentedStatusError(homework_status)
        # return None

    last_status_hw = HOMEWORK_STATES.get(homework_name)
    if not last_status_hw:
        HOMEWORK_STATES[homework_name] = homework_status
        logging.debug(f'Первоначальный статус `{homework_name}` сохранен.')
        return None

    if last_status_hw == homework_status:
        logging.debug(f'Статус проверки `{homework_name}` не изменился.')
        return None

    # ...

    verdict = homework_status

    # ...

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность идентификационных переменных."""
    is_pass = True if (PRACTICUM_TOKEN
                       and TELEGRAM_TOKEN
                       and TELEGRAM_CHAT_ID
                       ) else False

    if not is_pass:
        id_vars = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

        [logging.critical(f'Переменная `{id_var}` не определена')
         for id_var in id_vars if not os.getenv(id_var)]

    return is_pass


# flake8: noqa: C901
def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise LoadEnvironmentError('Ошибка загрузки переменных окружения')

    # ...
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # current_timestamp = int(time.time())
    current_timestamp = 1
    # ...

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks, query_time = check_response(response)

            for homework in homeworks:
                message = parse_status(homework)
                if message:
                    current_timestamp = query_time
                    HOMEWORK_STATES.clear()
                    send_message(bot, message)
                    logging.info(f'Сообщение: `{message}` успешно отправлено.')

               # time.sleep(RETRY_TIME)
        except APIResponseError as e:
            logging.error(f'Ошибка ответа от сервиса: {e}')
        except SendMessageError as e:
            logging.error(f'Ошибка отправки сообщения: {e}')
        except JSONDataStructureError as e:
            logging.error(f'Ошибка данных JSON: {e}')
        except UndocumentedStatusError as e:
            logging.error(f'Недокументированный статус домашней работы {e}')
        # except StateStatusException as e:
        # #     logging.debug(e)
        except Exception as e:
            logging.error(f'Сбой в работе программы: {e}', exc_info=True)
            # ...
            # time.sleep(RETRY_TIME)
        # else:
        #     logging.info(f'Сообщение: `{message}` успешно отправлено.')
        # break
        time.sleep(RETRY_TIME)

# Exception on control breake


if __name__ == '__main__':
    main()
