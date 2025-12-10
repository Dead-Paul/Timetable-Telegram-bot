import os
import sys
import time
import logging
from threading import Thread
from datetime import date, timedelta

from dotenv import load_dotenv
from telebot import TeleBot, types
from telebot.types import BotCommand, CallbackQuery, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

from bot_utils import BotUtils
from utils import Utils
from modules.my_sql import MySQL
from modules.json_file import JSON_File
from modules.sql_queries import Queries, TableDicts
from modules.timetable import Timetable, TimetableDicts


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

bot_commands: list[BotCommand] = [
    BotCommand("start", "Перезапустити бота"),
    BotCommand("subscription", "Керувати підпискою на розсилку"),
    BotCommand("rings", "Переглянути розклад дзвінків"),
    BotCommand("today", "Переглянути розклад на сьогодні"),
    BotCommand("tomorrow", "Переглянути розклад на завтра"),
    BotCommand("timetable", "Переглянути розклад занять на тиждень"),
    BotCommand("current_lesson", "Знайти зайняття яке проходить зараз"),
    BotCommand("get_lesson", "Отримати посилання на заняття"),
    BotCommand("cancel", "Відмінити дію"),
]
bot.set_my_commands(bot_commands, types.BotCommandScopeDefault())
bot.set_my_commands(bot_commands + 
                    [
                        BotCommand("editor", "Відредагувати розклад")
                    ], types.BotCommandScopeAllPrivateChats())

try:
    my_sql = MySQL(
        {
            "user": os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"],
            "host": os.environ["DB_HOST"], 
            "database": os.environ["DB_NAME"], 
            "autocommit": True
        },
       logger
    )
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

queries = Queries(my_sql.cursor, logger)

timetable = Timetable(queries, logger, json_file)

utils = Utils(queries, timetable, json_file, logger)

bot_utils = BotUtils(bot, queries, utils, logger)

get_datetime = utils.get_datetime
logger.info(f"Час для бота зараз {get_datetime().isoformat(sep=' ', timespec='seconds')}")


def distribution_cycle() -> None:
    while True:
        distribution_timedelta: timedelta = utils.distribution(get_datetime(), bot_utils.distribute)
        logger.info(f"Розсилка була призупинена. Наступна перевірка буде: " + 
                    (get_datetime() + distribution_timedelta).isoformat(sep=' ', timespec="seconds"))
        time.sleep(distribution_timedelta.total_seconds())

distribution_thread = Thread(target=distribution_cycle, daemon=True)
distribution_thread.start()
logging.info("Розсилка працює.")

@bot.message_handler(commands=["subscription"])
def subscription_msg(message: Message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔔 Підписатися", callback_data="subscription /subscribe"), InlineKeyboardButton("🔕 Відписатися", callback_data="subscription /unsubscribe"))
    bot.reply_to(message,
        "<b>Підписка на розсилку</b>\n\nЦя команда керує розсилкою сповіщень у цьому чаті.\n\n"
        "<b><i>Розсилка – це повідомлення про початок та кінець кожного заняття, яке є в розкладі.</i></b>\n\n"
        "Я надсилатиму тобі:\n• назву заняття;\n• посилання на клас;\n• посилання на саме заняття.\n\n"
        "Якщо на занятті заплановане щось важливе, адміністратори можуть додати нагадування — і я теж його надішлю.\n\n"
        "<i>Сповіщення приходять за три хвилини до початку заняття.\nА після завершення я одразу повідомлю назву наступного та час його проведення.</i>",
        reply_markup=markup
    )

@bot.message_handler(commands=["subscribe", "unsubscribe"])
def set_subscription_msg(message: Message) -> str:
    subscription: bool = True if message.text == "/subscribe" else False
    try:
        queries.set_subscription(message.chat.id, subscription)
        reply_text: str = "Ви підписані на розсилку! ლ(╹◡╹ლ)" if subscription else "Ви відписані від розсилки! ┗( T﹏T )┛"
        bot.reply_to(message, reply_text)
        return reply_text
    except:
        bot.reply_to(message, "Не вдалося змінити значення підписки в БД.")
        return "Помилка в БД, не вдалося змінити значення підписки"

@bot.message_handler(commands=["start"], chat_types=["private"])
def private_start_msg(message: Message):
    assert message.from_user is not None
    bot.reply_to(message, f"<b><i>Вітаю, {message.from_user.first_name}!</i></b>\n(p≧w≦q)")
    if queries.is_new_user(message.from_user.id):
        subscription_msg(message)
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["happy", "study"]), disable_notification=True)
        
@bot.message_handler(commands=["start"], chat_types=["group", "supergroup"])
def group_start_msg(message: Message):
    bot.reply_to(message, f"<b><i>Вітаю, {bot.get_chat(message.chat.id).title}!</i></b>\n(p≧w≦q)")
    if queries.is_new_user(message.chat.id):
        subscription_msg(message)
    if utils.is_main_group(bot.get_chat(message.chat.id).title, message.chat.id):
        bot.send_message(message.chat.id, "Ви моя основна група! Усі адміни цієї групи одразу є моїми адмінами (´▽`ʃ♡ƪ)")
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "happy"]), disable_notification=True)


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
    bot.reply_to(message, timetable.get_timetable(get_datetime().date(), True), disable_notification=True)
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["study", "lovely"]), disable_notification=True)

@bot.message_handler(commands=["tomorrow"])
def tomorrow_msg(message: Message):
    today: date = get_datetime().date()
    next_work_day: TableDicts.WeekdayDict|None = timetable.get_next_workday(today.weekday())
    if next_work_day is not None:
        if (today + timedelta(days=1)).isoweekday() != next_work_day['id']:
            bot.reply_to(message, "Завтра <b>вихідний</b>, наступний <b>день для навчання</b> буде:")
        bot.reply_to(message,
            timetable.get_timetable(today + timedelta(days=((next_work_day["id"] - today.isoweekday()) % 7 or 7)), True),
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


@bot_utils.bot_decorators.cancelable
@bot_utils.bot_decorators.message_text_required
def get_lesson(message: Message, lessons: list[TableDicts.LessonDict]) -> None:
    selected_lesson: TableDicts.LessonDict|None = utils.find_dict(message.text, lessons, "name")
    if selected_lesson is None:
        bot.reply_to(message, "Такого заняття немає в базі даних!", reply_markup=ReplyKeyboardRemove())
        return
    lesson: TimetableDicts.LessonDict = timetable.get_normilized_lesson(lesson=selected_lesson, flasher=None)
    bot.reply_to(message, f"{lesson['name']}{lesson['link']}", reply_markup=ReplyKeyboardRemove())
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["sad", "study", "service"]), disable_notification=True)

@bot.message_handler(commands=["get_lesson"])
def get_lesson_msg(message: Message):
    markup = ReplyKeyboardMarkup(row_width=1, input_field_placeholder="Оберіть назву заняття...", selective=True)
    markup.add(bot_utils.cancel_commands[1])
    lessons: list[TableDicts.LessonDict] = queries.get_lessons()[1:]
    markup.add(*[lesson["name"] for lesson in lessons])
    msg: Message = bot.reply_to(message, "Оберіть назву заняття:", reply_markup=markup)
    if message.chat.type == "private":
        bot.register_next_step_handler(msg, get_lesson, lessons=lessons)
    else:
        bot.register_for_reply_by_message_id(msg.message_id, get_lesson, lessons=lessons)

@bot.message_handler(commands=["cancel"])
@bot_utils.bot_decorators.cancelable
def cancel_msg(_: Message):
    ...

@bot.message_handler(commands=["editor"], chat_types=["private"])
@bot_utils.bot_decorators.access_required(["administrator", "creator"])
def editor_msg(message: Message):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.row(InlineKeyboardButton("ℹ️ Розклад ⬇️", callback_data="None"))
    markup.row(
        InlineKeyboardButton("Основні заняття", callback_data="editor timetable lesson_id"), 
        InlineKeyboardButton("Мігалки", callback_data="editor timetable flasher_id"), 
        InlineKeyboardButton("Заміни", callback_data="editor timetable replacement_id")
    )
    markup.add(InlineKeyboardButton("Нагадування", callback_data="editor timetable remind"))
    markup.add(InlineKeyboardButton("Зробити день робочим/вихідним", callback_data="editor timetable weekday"))
    
    markup.add(InlineKeyboardButton("ℹ️ Заняття ⬇️", callback_data="None"))
    markup.add(InlineKeyboardButton("Назву", callback_data="editor lesson name"))
    markup.row(
        InlineKeyboardButton("Посилання на заняття", callback_data="editor lesson link"),
        InlineKeyboardButton("Посилання на клас", callback_data="editor lesson class")
    )
    markup.add(InlineKeyboardButton("Максимальний бал", callback_data="editor lesson max_grade"))
    markup.row(
        InlineKeyboardButton("Створити нове", callback_data="editor lesson create"),
        InlineKeyboardButton("Видалити існуюче", callback_data="editor lesson delete")
    )

    bot.reply_to(message, "Що будемо редагувати?", reply_markup=markup)
    bot.send_sticker(message.chat.id, queries.get_sticker_id(["lovely", "service", "happy"]))

@bot.callback_query_handler(lambda _: True)
def callback_handler(callback: CallbackQuery):
    if callback.data is None: 
        return
    if callback.data == "None":
        bot.answer_callback_query(callback.id, text="Ці кнопки для відображення тексту, вони не виконують ніяких функцій!", show_alert=True)
        return
    command, options = callback.data.split(' ', 1)
    match command:
        case "editor":
            request_type, target = options.split(' ', 1)
            match request_type:
                case "timetable":
                    bot_utils.edit_timetable(callback.message, target)
                    bot.answer_callback_query(callback.id, text="Віддано на обробку!\nОчікуйте повідомлення з інструкціями!", show_alert=False)
                case "lesson":
                    bot_utils.edit_lesson(callback.message, target)
                    bot.answer_callback_query(callback.id, text="Віддано на обробку!\nОчікуйте повідомлення з інструкціями!", show_alert=False)
                case _:
                    bot.answer_callback_query(callback.id, text="Кнопка не знайдена Помилка!", show_alert=True)
                    return
        case "subscription":
            callback.message.text = options
            bot.answer_callback_query(callback.id, text=set_subscription_msg(callback.message), show_alert=False)
            return
        case _:
            bot.answer_callback_query(callback.id, text="Кнопка не знайдена Помилка!", show_alert=True)
            return


bot.infinity_polling()