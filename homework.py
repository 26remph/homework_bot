import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (APIResponseError, JSONDataStructureError,
                        LoadEnvironmentError, SendMessageError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# RETRY_TIME = 600
RETRY_TIME = 30

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
HOMEWORK_STATES = {}
NO_NAME_HOME_WORK = "NO_NAME_HOME_WORK"
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
    except Exception as e:
        raise SendMessageError(e) from e


def get_api_answer(current_timestamp):
    """Получает ответ от сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as e:
        raise APIResponseError(e) from e

    if response.status_code != HTTPStatus.OK:
        raise APIResponseError(f'Неожиданный статус ответа: {response}')

    return response.json()


def check_response(response):
    """Проверят корректность ответа сервиса, и отдает список домашних работ."""
    if type(response) == list:
        response = response[0]

    if type(response) != dict:
        raise JSONDataStructureError(
            f'Принят неожиданный тип данных {type(response)}, ожидается {dict}'
        )

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
    return homeworks


def parse_status(homework):
    """Извлекает статус проверки домашней работы и возвращает его."""
    try:
        homework_status = homework['status']
        HOMEWORK_STATUSES[homework_status]
    except KeyError as e:
        raise KeyError(f'Отсутствует ключ {e}') from e

    homework_name = homework.get('homework_name')
    if homework_name is None:
        homework_name = NO_NAME_HOME_WORK

    if HOMEWORK_STATES.get(homework_name) == homework_status:
        logging.debug(f'Статус проверки `{homework_name}` не изменился.')
        return

    verdict = HOMEWORK_STATUSES[homework_status]
    HOMEWORK_STATES[homework_name] = homework_status

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
    except Exception:
        raise JSONDataStructureError('Отсутствует ключ словаря `date_updated`')

    try:
        struct_time = time.strptime(date_updated, "%Y-%m-%dT%H:%M:%SZ")
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

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # current_timestamp = int(time.time())
    current_timestamp = 1

    pending_messages = []

    while True:
        try:
            except_msg = ""
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for hw in homeworks:
                message = parse_status(hw)
                if message:
                    current_timestamp = get_hw_date_update(hw)
                    pending_messages.append(message)

        except APIResponseError as e:
            except_msg = f'Ошибка ответа от сервиса: {e}'
            logging.error(except_msg)
        except JSONDataStructureError as e:
            except_msg = f'Ошибка данных JSON: {e}'
            logging.error(e)
        except KeyError as e:
            except_msg = f'Ошибка ключей словаря: {e}'
            logging.error(except_msg)
        except Exception as e:
            except_msg = f'Сбой в работе программы: {e}'
            logging.error(except_msg, exc_info=True)

        if not (except_msg in SENDING_ERRORS_MSG) and except_msg:
            pending_messages.append(except_msg)
            SENDING_ERRORS_MSG.add(except_msg)

        _pending_messages = pending_messages[:]
        for msg in pending_messages:
            try:
                send_message(bot, msg)
                logging.info(f'Сообщение: `{msg}` успешно отправлено.')
                _pending_messages.remove(msg)
            except SendMessageError:
                logging.error(f'Ошибка отправки сообщения боту: `{msg}`')

        pending_messages = _pending_messages[:]

        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    print('\nStarting https://t.me/vidim_assistant_yashabot'
          '\n(Quit the bot with CONTROL-C.)')
    try:
        main()
    except KeyboardInterrupt:
        print('\nShutdown yashabot ...')
        os._exit(0)
