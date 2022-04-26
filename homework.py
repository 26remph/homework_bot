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
NONAME_HOMEWORK = "NO_NAME_HOMEWORK"
SENDING_ERRORS_MSG = set()

logging.basicConfig(
    format='%(asctime)s | %(name)s | %(levelname)s | '
           '%(funcName)s | %(message)s',
    level=logging.DEBUG,
)


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    # except BadRequest as e:
    except Exception as e:
        raise SendMessageError(e) from e


def get_api_answer(current_timestamp):
    """Получает ответ от сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    # except ConnectionError as e:
    except Exception as e:
        raise APIResponseError(e) from e


    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(f'Неожиданный статус ответа: {response}')

    return response.json()


def check_response(response):
    """Проверят корректность ответа сервиса, и отдает список домашних работ."""
    #
    # import json
    # with open('data_debug.json') as f:
    #     data = json.load(f)
    # 
    # data = response.json()
    # if type(response) != dict:
    #     raise JSONDataStructureError(
    #         f'Принят неожиданный тип данных {type(response)}, ожидается {dict}'
    #     )
    if type(response) == list:
        response = response[0]

    try:
        homeworks = response['homeworks']
    except TypeError as e:
        raise JSONDataStructureError(f'Данные не содержат ключа: {e}')

    if type(homeworks) != list:
        raise JSONDataStructureError(
            f'Неожиданный тип данных для ключа: `homeworks`, ожидается {list}'
            f'принят {type(homeworks)}'
        )

    if not response:
        raise JSONDataStructureError('Список домашних работ пуст')
    #
    # import json
    # with open('data_debug.json', 'w', encoding='utf-8') as f:
    #     json.dump(data, f, ensure_ascii=False, indent=4)
    # logging.debug('json data save')
    #
    return homeworks


def parse_status(homework):
    """Извлекает статус проверки домашней работы и возвращает его."""
    # homework_id = homework.get('id')
    try:
        homework_status = homework['status']
    except Exception as e:
        raise UndocumentedStatusError(f'Отсутствует ключ {e}') from e

    # if not(homework_status in HOMEWORK_STATUSES.keys()):
    #     raise UndocumentedStatusError(homework_status)
    try:
        HOMEWORK_STATUSES[homework_status]
    except KeyError as e:
        raise KeyError(homework_status) from e
        # raise UndocumentedStatusError(homework_status) from e

    homework_name = homework.get('homework_name')
    if homework_name is None:
        homework_name = NONAME_HOMEWORK

    # try:
    #     homework_name = homework['homework_name']
    # except Exception as e:
    #     raise UndocumentedStatusError(f'Отсутствует ключ {e}') from e

    # last_status_hw = HOMEWORK_STATES.get(homework_name)
    # if not last_status_hw:
    #     HOMEWORK_STATES[homework_name] = homework_status
    #     logging.debug(f'Первоначальный статус `{homework_name}` сохранен.')
    #     return

    if HOMEWORK_STATES.get(homework_name) == homework_status:
        logging.debug(f'Статус проверки `{homework_name}` не изменился.')
        return

    # ...

    verdict = HOMEWORK_STATUSES[homework_status]
    HOMEWORK_STATES[homework_name] = homework_status
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


def get_hw_date_update(homework):
    """Преобразуем дату в формат timestamp"""
    try:
        date_updated = homework['date_updated']
        logging.debug(f'date_updated={date_updated}')
    except Exception:
        raise JSONDataStructureError(
            'Отсутствует ключ словаря `date_updated`'
        )
    try:
        struct_time = time.strptime(date_updated, "%Y-%m-%dT%H:%M:%SZ")
        logging.debug(f'struct_time={int(time.mktime(struct_time))}')
    except Exception:
        raise JSONDataStructureError(
            f'Значение даты: {date_updated} не соответствует'
            f'формату `%Y-%m-%dT%H:%M:%SZ`'
        )

    return int(time.mktime(struct_time))

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
            error_msg = ''
            response = get_api_answer(current_timestamp)
            logging.debug(f'response time = {current_timestamp}')
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                if message:
                    current_timestamp = get_hw_date_update(homework)
                    logging.debug(f'message time = {current_timestamp}')
                    # HOMEWORK_STATES.clear()
                    send_message(bot, message)
                    logging.info(f'Сообщение: `{message}` успешно отправлено.')

               # time.sleep(RETRY_TIME)
        except APIResponseError as e:
            error_msg = f'Ошибка ответа от сервиса: {e}'
            logging.error(error_msg)
        except SendMessageError as e:
            error_msg = f'Ошибка отправки сообщения боту: {e}'
            logging.error(error_msg)
        except JSONDataStructureError as e:
            error_msg = f'Ошибка данных JSON: {e}'
            logging.error(error_msg)
        except UndocumentedStatusError as e:
            error_msg = f'Недокументированный статус домашней работы {e}'
            logging.error(error_msg)
        # except StateStatusException as e:
        # #     logging.debug(e)
        except Exception as e:
            error_msg = f'Сбой в работе программы: {e}'
            # logging.error(error_msg, exc_info=True)
            logging.error(error_msg)
            # ...
            # time.sleep(RETRY_TIME)
        # else:
        #     logging.info(f'Сообщение: `{message}` успешно отправлено.')
        # break

        if not (error_msg in SENDING_ERRORS_MSG) and error_msg:
            try:
                send_message(bot, error_msg)
                SENDING_ERRORS_MSG.add(error_msg)
            except SendMessageError:
                error_msg = f'Ошибка отправки сообщения боту: `{error_msg}`'
                logging.error(error_msg)

        time.sleep(RETRY_TIME)

# Exception on control breake


if __name__ == '__main__':
    main()
