import os
import sys
import logging
from zoneinfo import ZoneInfo
from datetime import datetime

from dotenv import load_dotenv
from telebot import TeleBot
from telebot.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from JSON import JSON
from MySql import MySql



logger = logging.getLogger(__name__)
logger.addHandler(logging.FileHandler("bot_log.log", 'w', encoding="UTF-8"))
logging.basicConfig(level=logging.INFO, format="|%(asctime)s| %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


load_dotenv(override=True)
try:
    bot = TeleBot(os.environ["BOT_TOKEN"], parse_mode="HTML")
except KeyError:
    logger.critical("Відсутній токен боту! (перевірте файл .env)")
    sys.exit(1)
except ValueError:
    logger.critical("Токен бота не валідний!")
    sys.exit(1)
logger.info("Бот почав роботу!")

try:
    my_sql = MySql("bot", os.environ["DB_PASSWORD"], os.environ["DB_HOST"], os.environ["DB_NAME"], logger, True)
except KeyError as error:
    logger.critical("Деякі (або всі) параметри для підключення бази даних відсутні, перевірте їх наявність! (перевірте файл .env)")
    sys.exit(1)
except Exception as exception:
    logger.critical(f"Помилка при підключенні до бази даних: \"{exception}\"")
    sys.exit(1)


try:
    json = JSON(os.environ["JSON_FILENAME"])
except KeyError:
    logger.critical("Відсутня назва файлу JSON! (перевірте файл .env)")
    sys.exit(1)
except FileNotFoundError:
    logger.critical("Файл JSON не був знайден!")
    sys.exit(1)

def get_datetime() -> datetime:
    bot_timezone = json.get("timezone")
    if not isinstance(bot_timezone, str):
        logger.info(f"В файлі JSON не знайдено значення ключа timezone. (перевірте файл {os.environ['JSON_FILENAME']})")
        return datetime.now()
    return datetime.now(ZoneInfo("UTC")).astimezone(ZoneInfo(bot_timezone))
logger.info(f"Час для бота зараз {get_datetime().isoformat(sep=' ', timespec='seconds')}")






bot.infinity_polling()