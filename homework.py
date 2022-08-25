import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (APIResponseError, JSONDataStructureError,
                        LoadEnvironmentError, SendMessageError)
from settings import (ENDPOINT, HOMEWORK_STATES, HOMEWORK_STATUSES,
                      NO_NAME_HOME_WORK, RETRY_TIME)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(
    format='%(asctime)s | %(name)s | %(levelname)s | '
           '%(funcName)s | %(message)s',
    level=logging.INFO,
)


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as e:
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

    try:
        response = response.json()
    except Exception as e:
        raise APIResponseError(f'неожиданный формат данных {e}') from e

    return response


def check_response(response):
    """Проверят корректность ответа сервиса, и отдает список домашних работ."""
    if type(response) != dict:
        raise TypeError(
            f'Неожиданный тип данных {type(response)}, ожидается {dict}'
        )
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise JSONDataStructureError('Данные не содержат ключа: `homeworks`')

    if type(homeworks) != list:
        raise JSONDataStructureError(
            f'Неожиданный тип данных для ключа: `homeworks`, ожидается {list}'
            f'принят {type(homeworks)}'
        )

    if not homeworks:
        raise JSONDataStructureError('Список домашних работ пуст')

    return homeworks


def parse_status(homework):
    """Извлекает статус проверки домашней работы и возвращает его."""
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('Отсутствует ключ `status`')

    if HOMEWORK_STATUSES.get(homework_status) is None:
        raise KeyError('Неожиданный статус домашней работы')

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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_hw_date_update(homework):
    """Преобразуем дату в формат timestamp."""
    date_updated = homework.get('date_updated')
    if date_updated is None:
        raise JSONDataStructureError('Отсутствует ключ словаря `date_updated`')

    try:
        struct_time = time.strptime(date_updated, "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        raise JSONDataStructureError(
            f'Значение даты: {date_updated} не соответствует'
            f'формату `%Y-%m-%dT%H:%M:%SZ`'
        )

    return int(time.mktime(struct_time))


def main():  # noqa: C901
    """Основная логика работы бота."""
    if not check_tokens():
        raise LoadEnvironmentError('Ошибка загрузки переменных окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    pending_messages = []
    sending_errors_msg = []

    while True:
        try:
            except_msg = ""
            response = get_api_answer(current_timestamp)
            logging.debug(f'Время запроса: {response}')
            logging.debug(f'Получен ответ от сервиса: {response}')
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
        except TypeError as e:
            except_msg = f'Ошибка типа данных: {e}'
            logging.error(except_msg)
        except Exception as e:
            except_msg = f'Сбой в работе программы: {e}'
            logging.error(except_msg, exc_info=True)

        if not (except_msg in sending_errors_msg) and except_msg:
            pending_messages.append(except_msg)

        _pending_messages = pending_messages[:]
        for msg in pending_messages:
            try:
                send_message(bot, msg)
                logging.info(f'Сообщение: `{msg}` успешно отправлено.')
                _pending_messages.remove(msg)
                if msg == except_msg:
                    sending_errors_msg.append(except_msg)
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
