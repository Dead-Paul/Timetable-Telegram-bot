import os
from logging import Logger
from typing import Callable, Any

from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import Message

from modules.dict_types import TableDicts
from modules.sql_queries import Queries
from utils import Utils

class BotUtils:
    def __init__(self, bot: TeleBot, queries: Queries, utils: Utils, logger: Logger):
        self._member_statuses: list[str] = ["left", "member", "administrator", "creator"]

        self.bot: TeleBot = bot
        self.queries: Queries = queries
        self.utils: Utils = utils
        self.logger: Logger = logger


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
            return self._member_statuses.index("creator")
        main_group_id: int|None = self.utils.get_main_group_id()
        if main_group_id is None:
            self.logger.critical("Головна група бота не знайдена! Будь ласка перевірте файл json та наявність бота (с запуском) у головній групі!")
            raise Exception("Main group chat not found!")
        try:
            member_status: str = self.bot.get_chat_member(main_group_id, user_id).status
        except ApiException:
            return 0
        return self._member_statuses.index(member_status)

    def access_required(self, allowed_accesses: list[str|int]):
        def decorator(command_function: Callable[[Message], Any]):
            def wrap(message: Message):
                assert message.from_user is not None
                user_access: int = self.get_user_access(message.from_user.id)

                for access in allowed_accesses:
                    match access:
                        case str() if access == self._member_statuses[user_access]:
                            return command_function(message)
                        case int() if access == user_access:
                            return command_function(message)
            return wrap
        return decorator
