from logging import Logger
from datetime import datetime
from zoneinfo import ZoneInfo

from modules.json_file import JSON_File

class Utils:
    def __init__(self, json_file: JSON_File, logger: Logger):
        self.json_file = json_file
        self.logger = logger

    def get_datetime(self) -> datetime:
        bot_timezone = self.json_file.get("timezone")
        if not isinstance(bot_timezone, str):
            self.logger.info(f"В файлі JSON не знайдено значення ключа timezone.")
            return datetime.now()
        return datetime.now().astimezone(ZoneInfo(bot_timezone))
