from logging import Logger
from zoneinfo import ZoneInfo
from typing import Any, Callable, Mapping, TypeVar, cast
from datetime import datetime, timedelta

from modules.json_file import JSON_File
from modules.sql_queries import Queries, TableDicts
from modules.timetable import Timetable, TimetableDicts


class Utils:
    def __init__(self, queries: Queries, timetable: Timetable, json_file: JSON_File, logger: Logger):
        self.queries = queries
        self.timetable = timetable
        self.json_file = json_file
        self.logger = logger

    def get_datetime(self) -> datetime:
        bot_timezone = self.json_file.get("timezone")
        if not isinstance(bot_timezone, str):
            self.logger.info(f"В файлі JSON не знайдено значення ключа timezone.")
            return datetime.now()
        return datetime.now().astimezone(ZoneInfo(bot_timezone))

    def is_main_group(self, name: str|None, id: int) -> bool:
        main_group: dict[str, Any]|None = cast(dict|None, self.json_file.get("main_group"))
        if main_group is None:
            self.logger.critical("В файлі JSON не знайдено значення ключа main_group!")
            raise KeyError
        elif isinstance(main_group, dict):
            if (main_group.get("id") is not None) and main_group.get("id") == id:
                return True
            elif (main_group.get("name") is not None) and main_group.get("name") == name:
                main_group["id"] = id
                self.json_file.set({"main_group": main_group})
                return True
        return False

    def get_main_group_id(self) -> int|None:
        main_group: dict[str, Any]|None = cast(dict|None, self.json_file.get("main_group"))
        if main_group is None:
            self.logger.critical("В файлі JSON не знайдено значення ключа main_group!")
            raise KeyError
        return main_group.get("id")

    __dictType = TypeVar("__dictType", bound=Mapping[str, Any])
    def find_dict(self, value: Any, list_of_dicts: list[__dictType], key: str) -> __dictType|None:
        return next((dictionary for dictionary in list_of_dicts if dictionary[key] == value), None)


    def distribution(self, date_time: datetime, distribute: Callable[[str, list[str]], Any]) -> timedelta:
        rings: list[TableDicts.RingDict] = self.timetable.get_rings(date_time.date())
        weekday: TableDicts.WeekdayDict = self.queries.get_weekdays()[date_time.weekday()]

        next_distribution: datetime|None = None
        next_lesson: TimetableDicts.FoundLessonDict|None = None
        date_time = date_time.replace(tzinfo=None)

        if not weekday["is_work_day"] or rings[-1]["end"] < date_time:
            next_distribution = rings[0]["start"] + timedelta(days=1) - timedelta(minutes=3)
            for ring_id in range(1, len(rings)):
                self.queries.clean_replacement_and_remind(weekday["id"], ring_id)
        else:
            if rings[0]["start"] - timedelta(minutes=3) > date_time:
                next_distribution = rings[0]["start"] - timedelta(minutes=3)
            else:
                for ring_i in range(len(rings)):
                    if abs((rings[ring_i]["start"] - timedelta(minutes=3)) - date_time) < timedelta(minutes=1):
                        lesson: TimetableDicts.FoundLessonDict|str = self.timetable.find_lesson(date_time)
                        if isinstance(lesson, str):
                            next_lesson = self.timetable.find_next_lesson(weekday["id"], ring_i + 1, date_time.date())
                            if next_lesson is not None and next_lesson["lesson"] is not None:
                                distribute(
                                    f"Далі буде {next_lesson['lesson']['name']}\n<i>В {next_lesson['ring']['start'].strftime("%H:%M")}.</i>", 
                                    ["study", "sad"]
                                )
                                next_distribution = next_lesson["ring"]["start"] - timedelta(minutes=3)
                                break
                            next_distribution = rings[0]["start"] + timedelta(days=1) - timedelta(minutes=3)
                            break
                        elif isinstance(lesson["lesson"], dict) and lesson["lesson"]["lesson_id"] != 1:
                            distribute(
                                f"{lesson['lesson']['name']} {lesson['lesson']['link']}" + (lesson["lesson"]["remind"] or ""), 
                                ["study", "sad"]
                            )
                            next_distribution = rings[ring_i]["end"]
                            break
                    elif abs(rings[ring_i]["end"] - date_time) < timedelta(minutes=1):
                        self.queries.clean_replacement_and_remind(weekday["id"], ring_i + 1)
                        next_lesson = self.timetable.find_next_lesson(weekday["id"], ring_i + 1, date_time.date())
                        if next_lesson is not None and next_lesson["lesson"] is not None:
                            distribute(
                                f"Далі буде {next_lesson['lesson']['name']}\n<i>В {next_lesson['ring']['start'].strftime("%H:%M")}.</i>", 
                                ["study", "sad"]
                            )
                            next_distribution = next_lesson["ring"]["start"] - timedelta(minutes=3)
                            break
                        next_distribution = rings[0]["start"] + timedelta(days=1) - timedelta(minutes=3)
                        distribute(f"На <b>сьогодні</b> зайняття <b>закінчились</b>!\nლ(╹◡╹ლ)", ["happy", "lovely"])
                        break

        if isinstance(next_distribution, datetime):
            return next_distribution - date_time
        else:
            return timedelta(seconds=30)
