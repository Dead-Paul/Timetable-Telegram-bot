import os
from logging import Logger
from functools import wraps
from typing import Callable, Any

from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import InaccessibleMessage, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, ReplyParameters

from modules.dict_types import TableDicts
from modules.sql_queries import Queries
from utils import Utils

class BotUtils:
    def __init__(self, bot: TeleBot, queries: Queries, utils: Utils, logger: Logger):
        self.bot: TeleBot = bot
        self.queries: Queries = queries
        self.utils: Utils = utils
        self.logger: Logger = logger

        self.member_statuses: list[str] = ["left", "member", "administrator", "creator"]
        self.cancel_commands: list[str] = ["Відміна", "Відміна ⛔", "cancel", "/cancel", f"/cancel@{str(self.bot.get_me().username).lower()}"]

        self.bot_decorators = _BotDecorators(self)


    def distribute(self, text: str, sticker_type: list[str]) -> None:
        subscribed_users: list[TableDicts.UserDict] = self.queries.get_subscribed_users()
        if len(subscribed_users) < 1:
            self.logger.warning("Ні у кого з користувачів вімкнена розсилка!")
            return
        self.logger.info(f"Розсилка вімкнута у {len(subscribed_users)} користувачів.")
        sticker_id: str = self.queries.get_sticker_id(sticker_type)
        for user in subscribed_users:
            try:
                self.bot.send_message(user["id"], text)
                self.bot.send_sticker(user["id"], sticker_id)
            except ApiException:
                self.logger.warning(f"Знайден чат, в який не вдається відправити інформацію, він буде відписан. ID = {user['id']}!")
                self.queries.set_subscription(user["id"], False)
        return

    def get_user_access(self, user_id: int) -> int:
        if os.environ.get("CREATOR_ID") == str(user_id):
            return self.member_statuses.index("creator")
        main_group_id: int|None = self.utils.get_main_group_id()
        if main_group_id is None:
            self.logger.critical("Головна група бота не знайдена! Будь ласка перевірте файл json та наявність бота (с запуском) у головній групі!")
            raise Exception("Main group chat not found!")
        try:
            member_status: str = self.bot.get_chat_member(main_group_id, user_id).status
        except ApiException:
            return 0
        return self.member_statuses.index(member_status)

    def set_timetable_update(self, message: Message, column_name: str, weekday_id: int, ring_id: int, lessons: list[TableDicts.LessonDict]|None) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            assert isinstance(message.text, str)
            if column_name == "remind" and lessons is None:
                self.queries.update_timetable(weekday_id, ring_id, column_name, message.text if message.text.lower() != "видалити 🗑️" else None)
                self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
                self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
            elif isinstance(lessons, list) and column_name != "remind":
                if message.text.lower() != "видалити 🗑️" or column_name == "lesson_id":
                    selected_lesson: TableDicts.LessonDict|None = self.utils.find_dict(message.text, lessons, "name")
                    if selected_lesson is None:
                        self.bot.reply_to(message, "Зайняття з такою назвою не має в базі даних. Будь ласка оберайте варіанти користуючись кнопками! (Ще раз)")
                        self.get_timetable_update(message, column_name, weekday_id, ring_id=ring_id)
                    else:
                        self.queries.update_timetable(weekday_id, ring_id, column_name, selected_lesson["id"])
                        self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
                        self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
                elif column_name != "lesson_id" and message.text.lower() == "видалити 🗑️":
                    self.queries.update_timetable(weekday_id, ring_id, column_name, None)
                    self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
                    self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
                else:
                    raise ValueError
            else:
                raise ValueError
        return local_func(message)

    def get_timetable_update(self, message: Message, column_name: str, weekday_id: int, rings: list[TableDicts.RingDict]|None = None, ring_id: int|None = None) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            assert isinstance(message.text, str)
            if ring_id is None and rings is not None:
                selected_id: str = message.text.split(')', 1)[0]
                selected_ring: TableDicts.RingDict|None = self.utils.find_dict(int(selected_id), rings, "id") if selected_id.isdigit() else None
                if selected_ring is None:
                    self.bot.reply_to(message, "Такого номера зайняття не має в базі даних. Будь ласка оберайте варіанти користуючись кнопками! (Ще раз)")
                    self.select_timetable_row(message, column_name, weekday_id=weekday_id)
                    return
                selected_ring_id: int = selected_ring["id"]
            elif isinstance(ring_id, int):
                selected_ring_id = ring_id
            else:
                raise ValueError

            timetable_row: TableDicts.TimetableDict|None = self.queries.get_timetable_row(weekday_id, selected_ring_id)
            assert isinstance(timetable_row, dict)
            old_value: str|None = None
            markup = ReplyKeyboardMarkup(row_width=1)
            markup.add(self.cancel_commands[1])
            if column_name != "lesson_id":
                markup.add("Видалити 🗑️")
            if column_name == "remind":
                markup.input_field_placeholder = "Нове нагадування..."
                old_value = timetable_row[column_name]
                self.bot.register_next_step_handler(
                    self.bot.reply_to(message, f"<b>Зараз</b> нагадування:\n{old_value or 'Нагадування немає'}\n\nНапішіть <b>нове</b> нагадування:", 
                                      reply_markup=markup),
                    self.set_timetable_update,
                    column_name=column_name, weekday_id=weekday_id, ring_id=selected_ring_id, lessons=None
                )
                return
            else:
                old_value = self.queries.get_lesson(timetable_row[column_name])["name"] if timetable_row[column_name] is not None else None
                lessons: list[TableDicts.LessonDict] = self.queries.get_lessons()
                markup.add(*[lesson["name"] for lesson in lessons])
                self.bot.register_next_step_handler(
                    self.bot.reply_to(message, f"<b>Зараз</b> задано зайняття:\n{old_value or 'Зайняття немає'}\n\n<b>Оберіть нове</b> зайняття:", 
                                      reply_markup=markup),
                    self.set_timetable_update,
                    column_name=column_name, weekday_id=weekday_id, ring_id=selected_ring_id, lessons=lessons
                )
        return local_func(message)

    def select_timetable_row(self, message: Message, column_name: str, weekdays: list[TableDicts.WeekdayDict]|None = None, weekday_id: int|None = None) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            assert isinstance(message.text, str)
            if weekday_id is None and weekdays is not None:
                selected_weekday: TableDicts.WeekdayDict|None = self.utils.find_dict(message.text.split(' ', 1)[0] if column_name == "weekday" else message.text, weekdays, "name")
                if selected_weekday is None:
                    self.bot.reply_to(message, "Такого дня тижня не має в базі даних. Будь ласка оберайте варіанти користуючись кнопками! (Ще раз)")
                    self.edit_timetable(message, column_name)
                    return
                selected_weekday_id: int = selected_weekday["id"]
            elif isinstance(weekday_id, int):
                selected_weekday_id = weekday_id
            else:
                raise ValueError

            if column_name == "weekday":
                if isinstance(weekdays, list):
                    self.queries.update_weekday(selected_weekday_id, bool((weekdays[selected_weekday_id - 1]["is_work_day"] + 1) % 2))
                    self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
                    self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
                else:
                    raise ValueError
            else:
                markup = ReplyKeyboardMarkup(row_width=1)
                markup.add(self.cancel_commands[1])
                rings: list[TableDicts.RingDict] = self.queries.get_rings()
                for ring in rings:
                    timetable_row: TableDicts.TimetableDict|None = self.queries.get_timetable_row(selected_weekday_id, ring["id"])
                    if timetable_row is None:
                        markup.add(f"{ring['id']}) Не знайдено (помилка заповнення бази даних)")
                        continue
                    markup.add(
                        f"{ring['id']}) {self.queries.get_lesson(timetable_row['lesson_id'])['name']} / "
                        f"{self.queries.get_lesson(timetable_row['flasher_id'] or 1)['name']} "
                        f"(заміна: {self.queries.get_lesson(timetable_row['replacement_id'] or 1)['name']})"
                    )
                self.bot.register_next_step_handler(
                    self.bot.reply_to(message, "<b>Оберіть</b> номер зайняття:", reply_markup=markup),
                    self.get_timetable_update,
                    column_name=column_name, weekday_id=selected_weekday_id, rings=rings
                )
        return local_func(message)

    def edit_timetable(self, message: Message|InaccessibleMessage, column_name: str) -> None:
        @self.bot_decorators.cancelable
        def local_func(message: Message|InaccessibleMessage) -> None:
            weekdays: list[TableDicts.WeekdayDict] = self.queries.get_weekdays()
            markup = ReplyKeyboardMarkup(row_width=1)
            markup.add(self.cancel_commands[1])
            if column_name == "weekday":
                markup.add(*[weekday["name"] + (" (Рабочий)" if weekday["is_work_day"] else " (Вихідний)") for weekday in weekdays])
            else:
                markup.add(*[weekday["name"] for weekday in weekdays])
            self.bot.register_next_step_handler(
                self.bot.send_message(message.chat.id, "<b>Оберіть</b> день тиждня:", 
                                      reply_markup=markup, reply_parameters=ReplyParameters(message.id) if message.id else None),
                self.select_timetable_row,
                column_name=column_name, weekdays=weekdays
            )
        return local_func(message)

    def set_lesson_update(self, message: Message, column_name: str, lesson_id: int) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            assert message.text is not None
            new_value: int|str|None = message.text
            if message.text.lower() == "видалити 🗑️":
                if column_name == "name":
                    self.bot.reply_to(message, "<b>Недопустиме значення</b> для назви заняття! (введіть інше значення)")
                    self.get_lesson_update(message, column_name, lesson_id=lesson_id)
                    return
                new_value = None
            elif column_name == "max_grade":
                if not message.text.isdigit():
                    self.bot.reply_to(message, ("Максимальний бал має бути числом!"
                        "<i>(Якщо бал задається текстом або його не треба враховувати в разрахунку середнього значення - максимальний бал має бути 0)</i>"
                        "<i>(Якщо середній бал з цього предмету не виставляється - видаліть середній бал відповідною кнопкою)</i>"))
                    self.get_lesson_update(message, column_name, lesson_id=lesson_id)
                    return
                new_value = int(message.text)

            self.queries.update_lesson(lesson_id, column_name, new_value)
            self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
            self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
        return local_func(message)

    def get_lesson_update(self, message: Message, column_name: str, lessons: list[TableDicts.LessonDict]|None = None, lesson_id: int|None = None) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            if isinstance(lessons, list):
                assert message.text is not None
                selected_lesson: TableDicts.LessonDict|None = self.utils.find_dict(message.text, lessons, "name")
                if selected_lesson is None:
                    self.bot.reply_to(message, "Такого заняття не має в базі даних. Будь ласка оберайте варіанти користуючись кнопками! (Ще раз)")
                    self.edit_lesson(message, column_name)
                    return
                selected_lesson_id: int = selected_lesson["id"]
            elif isinstance(lesson_id, int):
                selected_lesson_id = lesson_id
            else:
                raise ValueError

            if column_name == "delete":
                self.queries.delete_lesson(selected_lesson_id)
                self.bot.reply_to(message, "Редагування <b>завершено</b>!", reply_markup=ReplyKeyboardRemove())
                self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
                return

            old_value: str|int|None = self.queries.get_lesson(selected_lesson_id)[column_name]
            markup = ReplyKeyboardMarkup(row_width=1)
            markup.add(self.cancel_commands[1])
            if column_name != "name":
                markup.add("Видалити 🗑️")
            self.bot.register_next_step_handler(
                self.bot.reply_to(message, f"<b>Зараз</b> задано значення:\n{old_value if old_value is not None else 'Значення не задано'}\n\n<b>Напішіть нове</b> значення:", 
                                    reply_markup=markup),
                self.set_lesson_update,
                column_name=column_name, lesson_id=selected_lesson_id
            )
        return local_func(message)

    def create_lesson(self, message: Message, column_name: str, lessons: list[TableDicts.LessonDict]) -> None:
        @self.bot_decorators.cancelable
        @self.bot_decorators.message_text_required
        def local_func(message: Message) -> None:
            assert message.text is not None
            found_lesson: TableDicts.LessonDict|None = self.utils.find_dict(message.text, lessons, "name")
            if found_lesson is not None:
                self.bot.reply_to(message, "Заняття з даною назвою вже існує! (введіть назву для <b>нового</b> заняття)")
                self.edit_lesson(message, column_name)
                return
            self.queries.create_lesson({"id": 1, "name": message.text, "link": None, "class": None, "max_grade": None})
            self.bot.reply_to(message, "Зараз створен шаблон заняття. <b>Ви зможете видалити або змінти це заняття через редактор.</b>",
                              reply_markup=ReplyKeyboardRemove())
            self.bot.send_sticker(message.chat.id, self.queries.get_sticker_id("happy"))
        return local_func(message)

    def edit_lesson(self, message: Message|InaccessibleMessage, column_name: str) -> None:
        @self.bot_decorators.cancelable
        def local_func(message: Message|InaccessibleMessage) -> None:
            lessons: list[TableDicts.LessonDict] = self.queries.get_lessons()
            if column_name != "name":
                lessons.pop(0)
            markup = ReplyKeyboardMarkup(row_width=1)
            markup.add(self.cancel_commands[1])
            if column_name == "create":
                self.bot.register_next_step_handler(
                self.bot.send_message(message.chat.id, "<b>Введіть назву</b> для <b>нового</b> заняття:", 
                                      reply_parameters=ReplyParameters(message.id) if message.id else None, reply_markup=markup),
                self.create_lesson,
                column_name=column_name, lessons=lessons
                )
                return
            markup.add(*[lesson["name"] for lesson in lessons])
            self.bot.register_next_step_handler(
                self.bot.send_message(message.chat.id, "<b>Оберіть</b> заняття:", 
                                      reply_markup=markup, reply_parameters=ReplyParameters(message.id) if message.id else None),
                self.get_lesson_update,
                column_name=column_name, lessons=lessons
            )
        return local_func(message)

class _BotDecorators:
    def __init__(self, bot_utils: BotUtils):
        self.bot_utils: BotUtils = bot_utils

    def access_required(self, allowed_accesses: list[str|int]):
        def decorator(command_function: Callable[..., Any]):
            @wraps(command_function)
            def wrap(message: Message, *args, **kwargs):
                assert message.from_user is not None
                user_access: int = self.bot_utils.get_user_access(message.from_user.id)

                for access in allowed_accesses:
                    match access:
                        case str() if access == self.bot_utils.member_statuses[user_access]:
                            return command_function(message, *args, *kwargs)
                        case int() if access == user_access:
                            return command_function(message, *args, *kwargs)
                self.bot_utils.bot.reply_to(message, "У вас намає доступу до цієї команди!")
                self.bot_utils.bot.send_sticker(message.chat.id, self.bot_utils.queries.get_sticker_id(["sad", "service"]))
            return wrap
        return decorator

    def cancelable(self, cancelable_function: Callable[..., Any]):
        @wraps(cancelable_function)
        def wrap(message: Message|InaccessibleMessage, *args, **kwargs):
            if message.text is None:
                return cancelable_function(message, *args, **kwargs)
            for cancel_command in self.bot_utils.cancel_commands:
                if message.text.lower() == cancel_command.lower():
                    self.bot_utils.bot.send_message(message.chat.id, "<b>Відмінено</b>!", 
                                                    reply_markup=ReplyKeyboardRemove(), reply_parameters=ReplyParameters(message.id) if message.id else None)
                    self.bot_utils.bot.send_sticker(message.chat.id, self.bot_utils.queries.get_sticker_id(["sad", "service"]))
                    break
            else:
                return cancelable_function(message, *args, **kwargs)
        return wrap

    def message_text_required(self, function_with_message_text_required: Callable[..., Any]):
        @wraps(function_with_message_text_required)
        def wrap(message: Message|InaccessibleMessage, *args, **kwargs):
            if isinstance(message.text, str):
                return function_with_message_text_required(message, *args, **kwargs)
            else:
                self.bot_utils.bot.send_message(message.chat.id, "Для роботи цієї функції необхідно надіслати <b>повідомлення з текстом</b>!", 
                                                reply_markup=ReplyKeyboardRemove(), reply_parameters=ReplyParameters(message.id) if message.id else None)
                self.bot_utils.bot.send_sticker(message.chat.id, self.bot_utils.queries.get_sticker_id(["error", "sad"]))
        return wrap
