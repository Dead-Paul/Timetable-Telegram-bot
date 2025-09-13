import os
import sys
import time
import logging
from threading import Thread
from zoneinfo import ZoneInfo
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from telebot import TeleBot, types
from telebot.apihelper import ApiException
from telebot.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from utils import Utils
from modules.my_sql import MySQL
from modules.json_file import JSON_File
from modules.sql_queries import Queries, TableDicts
from modules.timetable import Timetable, TimetableDicts
from utils import Utils


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

bot.set_my_commands(
    [
        types.BotCommand("start", "Перезапустити бота"),
        types.BotCommand("rings", "Переглянути розклад дзвінків"),
        types.BotCommand("today", "Переглянути розклад на сьогодні"),
        types.BotCommand("tomorrow", "Переглянути розклад на завтра"),
        types.BotCommand("timetable", "Переглянути розклад занять на тиждень"),
        types.BotCommand("current_lesson", "Знайти зайняття яке проходить зараз"),
    ],
    types.BotCommandScopeDefault()
)

try:
    my_sql = MySQL("bot", os.environ["DB_PASSWORD"], os.environ["DB_HOST"], os.environ["DB_NAME"], logger, True)
except KeyError as error:
    logger.critical("Деякі (або всі) параметри для підключення бази даних відсутні, перевірте їх наявність! (перевірте файл .env)")
    sys.exit(1)
except Exception as exception:
    logger.critical(f"Помилка при підключенні до бази даних: \"{exception}\"")
    sys.exit(1)

try:
    json_file = JSON_File(os.environ["JSON_FILENAME"])
except KeyError:
    logger.critical("Відсутня назва файлу JSON! (перевірте файл .env)")
    sys.exit(1)
except FileNotFoundError:
    logger.critical("Файл JSON не був знайден!")
    sys.exit(1)

queries = Queries(my_sql.cursor, logger, json_file)

timetable = Timetable(queries, logger, json_file)

utils = Utils(queries, timetable, json_file, logger)

get_datetime = utils.get_datetime
logger.info(f"Час для бота зараз {get_datetime().isoformat(sep=' ', timespec='seconds')}")

def distribute(text: str, sticker_type: list[str]) -> None:
    subscribed_users: list[TableDicts.UserDict] = queries.get_subscribed_users()
    if len(subscribed_users) < 1:
        logger.warning("Ні у кого з користувачів вімкнена розсилка!")
        return
    logger.info(f"Розсилка вімкнута у {len(subscribed_users)} користувачів.")
    sticker_id: str = queries.get_sticker_id(sticker_type)
    for user in subscribed_users:
        try:
            bot.send_message(user["id"], text)
            bot.send_sticker(user["id"], sticker_id)
        except ApiException:
            logger.warning(f"Знайден чат, в який не вдається відправити інформацію, він буде відписан. ID = {user['id']}!")
            queries.set_subscription(user["id"], False)
    return


def distribution_cycle() -> None:
    while True:
        distribution_timedelta: timedelta = utils.distribution(get_datetime(), distribute)
        logger.info(f"Розсилка була призупинена. Наступна перевірка буде: " + 
                    (get_datetime() + distribution_timedelta).isoformat(sep=' ', timespec="seconds"))
        time.sleep(distribution_timedelta.total_seconds())

distribution_thread = Thread(target=distribution_cycle, daemon=True)
distribution_thread.start()
logging.info("Розсилка працює.")




def subscribtion_act(message: Message):
    def set_subscribtion(message: Message):
        match message.text:
            case "Робити":
                queries.set_subscription(message.chat.id, True)
                bot.reply_to(message, "Добре, <b><i>розсилка увімкнена!</i></b>", reply_markup=ReplyKeyboardRemove())
            case "Не робити":
                queries.set_subscription(message.chat.id, False)
                bot.reply_to(message, "Гаразд, <b><i>розсилка вимкнена...</i></b>", reply_markup=ReplyKeyboardRemove())
            case _:
                bot.reply_to(message, "Я очікувала від тебе іншого повідомлення, <b><i>розсилка не змінена...</i></b>", reply_markup=ReplyKeyboardRemove())

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Робити", "Не робити")
    bot.register_next_step_handler(
        bot.reply_to(message,"<b>Мені робити розсилку в цей чат?</b>\n(☆▽☆)", reply_markup=markup, disable_notification=True),
        set_subscribtion
    )
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["service", "study"]), disable_notification=True)

@bot.message_handler(commands=["start"], chat_types=["private"])
def private_start_msg(message: Message):
    assert message.from_user is not None
    bot.reply_to(message, f"<b><i>Вітаю, {message.from_user.first_name}!</i></b>\n(p≧w≦q)")

    if queries.is_new_user(message.from_user.id):
        bot.send_message(message.chat.id, 
            "Оскільки ти пишеш мені вперше – я хочу розповісти тобі, що таке розсилка <i>(у мене)</i>.\n\n"
            "<b><i>Розсилка – це сповіщення про початок та кінець кожного заняття, яке внесене до розкладу в цей чат.\n\n"
            "Я надсилатиму тобі повідомлення з назвою заняття, посиланням на клас та посиланням на саме заняття.\n"
            "Якщо на занятті має відбутися щось важливе – адміністратори, швидше за все, додадуть нагадування про це.\n"
            "Все це я обов’язково надішлю тобі </i><u>за три хвилини до початку заняття!</u><i>\n"
            "А після завершення одного заняття я надсилатиму тобі назву наступного та час його проведення.</i></b>"
        )

    bot.send_sticker(message.chat.id, queries.get_sticker_id(["happy", "study"]), disable_notification=True)
    subscribtion_act(message)
        
@bot.message_handler(commands=["start"], chat_types=["group", "supergroup"])
def group_start_msg(message: Message):
    bot.reply_to(message, f"<b><i>Вітаю, {bot.get_chat(message.chat.id).title}!</i></b>\n(p≧w≦q)")

    if queries.is_new_user(message.chat.id):
        bot.send_message(message.chat.id, 
            "Оскільки у вашій групі я вперше – хочу розповісти, що таке розсилка <i>(у мене)</i>. \n\n"
            "<b><i>Розсилка – це сповіщення про початок і кінець кожного заняття, яке занесене в розклад цього чату.\n\n"
            "Я буду надсилати тобі повідомлення з назвою заняття, посиланням на клас і посиланням на саме заняття.\n"
            "Якщо на занятті має відбутися щось важливе – адміни, скоріш за все, додадуть нагадування про це.\n"
            "Усе це я обов’язково надішлю </i><u>за три хвилини до початку заняття!</u><i>\n"
            "А після завершення одного заняття я надсилатиму назву наступного та час його проведення.</i></b>"
        )

    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "happy"]), disable_notification=True)
    subscribtion_act(message)


@bot.message_handler(commands=["rings"])
def rings_msg(message: Message):
    rings = queries.get_rings()
    
    bot.reply_to(message, 
        ";\n".join(
            [
                f"{ring['id']} {ring['name'].split(' ')[1]}: <b><i>{ring['start'].strftime('%H:%M')} - {ring['end'].strftime('%H:%M')}</i></b>" 
                for ring in rings
            ]
        ) + '.',
        disable_notification=True
    )
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "lovely"]), disable_notification=True)


@bot.message_handler(commands=["timetable"])
def timetable_msg(message: Message):
    bot.reply_to(message, 
        "\n\n".join(
            ["<b>Розклад:</b>\n"] +
            [timetable.get_timetable(weekday) for weekday in range(7)]
        ),
        disable_notification=True
    )
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "lovely"]), disable_notification=True)

@bot.message_handler(commands=["today"])
def today_msg(message: Message):
    bot.reply_to(message, timetable.get_timetable(get_datetime().date()), disable_notification=True)
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "lovely"]), disable_notification=True)

@bot.message_handler(commands=["tomorrow"])
def tomorrow_msg(message: Message):
    today: date = get_datetime().date()
    next_work_day: TableDicts.WeekdayDict|None = timetable.get_next_workday(today.weekday())
    if next_work_day is not None:
        if (today + timedelta(days=1)).isoweekday() != next_work_day['id']:
            bot.reply_to(message, "Завтра <b>вихідний</b>, наступний <b>день для навчання</b> буде:")
        bot.reply_to(message,
            timetable.get_timetable(today + timedelta(days=((next_work_day["id"] - today.isoweekday()) % 7 or 7))),
            disable_notification=True
        )
    else:
        bot.reply_to(message, "Не знайдено жодного робочого дня, <b>скоріше за все у вас канікули</b>! \n（￣︶￣）", disable_notification=True)
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "lovely"]), disable_notification=True)


@bot.message_handler(commands=["current_lesson"])
def current_lesson_msg(message: Message):
    current_lesson: TimetableDicts.FoundLessonDict|str = timetable.find_lesson(get_datetime())

    if isinstance(current_lesson, str):
        bot.reply_to(message, current_lesson)
        bot.send_sticker(message.chat.id, queries.get_sticker_id(["happy", "lovely", "service"]), disable_notification=True)
    else:
        if current_lesson["lesson"] is None:
            bot.reply_to(message, "Скоріш за все, зараз немає заняття, хоч за розкладом дзвінков воно і має бути \n┗( T﹏T )┛")
        elif current_lesson["lesson"]["lesson_id"] == 1:
            bot.reply_to(message, "Зараз немає заняття, можна відпочити!\n(☆▽☆)") 
            bot.send_sticker(message.chat.id, queries.get_sticker_id(["happy", "lovely", "service"]), disable_notification=True)
        else:
            bot.reply_to(message, 
                f"<b>З {current_lesson['ring']['start'].strftime('%H:%M')} по {current_lesson['ring']['end'].strftime('%H:%M')}:</b> "
                f"{current_lesson['lesson']['name']}{current_lesson['lesson']['link']}" + (current_lesson["lesson"]["remind"] or "")
            ) 
            bot.send_sticker(message.chat.id, queries.get_sticker_id(["sad", "study", "service"]), disable_notification=True)


bot.infinity_polling()