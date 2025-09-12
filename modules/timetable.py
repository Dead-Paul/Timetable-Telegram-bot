from logging import Logger
from typing import overload, cast
from datetime import date, datetime, timedelta
from functools import singledispatchmethod

from .json_file import JSON_File
from .sql_queries import Queries
from .dict_types import TableDicts, TimetableDicts

class Timetable:
    def __init__(self, queries: Queries, logger: Logger, json_file: JSON_File):
        self.queries = queries
        self.logger = logger
        self.json_file = json_file


    def get_next_workday(self, weekday: int) -> TableDicts.WeekdayDict|None:
        weekdays: list[TableDicts.WeekdayDict] = self.queries.get_weekdays()
        for day in range(1, 8):
            day_index = (weekday + day) % 7
            if weekdays[day_index]["is_work_day"]:
                return weekdays[day_index]
        return None

    def get_lesson(self, isoweekday: int, lesson_number: int, date: datetime|None = None) -> TimetableDicts.LessonDict|None:
        timetable: TableDicts.TimetableDict|None = cast(TableDicts.TimetableDict, self.queries.get_timetable_row(isoweekday, lesson_number))
        if timetable is None:
            return None

        remind: str|None = None if timetable["remind"] is None else f"\n\nНагадування:\n{timetable['remind']}"

        if isinstance(timetable["replacement_id"], int):
            lesson: TableDicts.LessonDict = self.queries.get_lesson(timetable["replacement_id"])
            lesson["name"] += " (заміна)"
            flasher = None
        else:
            lesson: TableDicts.LessonDict = self.queries.get_lesson(timetable["lesson_id"])
            flasher: TableDicts.LessonDict|None = self.queries.get_lesson(timetable["flasher_id"]) if timetable["flasher_id"] is not None else None

        if date is not None or isinstance(timetable["replacement_id"], int) or flasher is None:
            if flasher is not None and isinstance(date, datetime):
                try:
                    first_flasher_monday = datetime.fromisoformat(cast(str, self.json_file.get("first_flasher_monday")))
                except ValueError:
                    self.logger.error("Змінна \"first_flasher_monday\" не була знайдена в JSON файлі! Помилка не оброблена!")
                    raise 
                if ((date.replace(tzinfo=None) - timedelta(days=date.weekday()) - first_flasher_monday).days // 7) % 2:
                    lesson = flasher            
            return  {
                "name": f"<b><i>{lesson['name']}</i></b>",
                "link": f"\n\n<b>Посилання на заняття:</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}",
                "remind": remind
            }

        return {
            "name": f"<b><i>{lesson['name']} / {flasher['name']}</i></b>",
            "link": (f"\n\n<b>Посилання на заняття ({lesson['name']}):</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}"
                        f"\n\n\n<b>Посилання на заняття ({flasher['name']}):</b>\n{flasher['link']} \n\n<b>Посилання на клас:</b> \n{flasher['class']}"),
            "remind": remind
        }

    def get_rings(self, target_date: date) -> list[TableDicts.RingDict]:
        rings: list[TableDicts.RingDict] = self.queries.get_rings()
        for ring in rings:
            for key in ["start", "end"]:
                ring[key] = datetime.combine(target_date, ring[key].time())
        return rings


    def find_lesson(self, date_time: datetime) -> TimetableDicts.FoundLessonDict:
        date_time = date_time.replace(tzinfo=None)
        rings: list[TableDicts.RingDict] = self.get_rings(date_time.date())
        if not self.queries.get_weekdays()[date_time.weekday()]["is_work_day"]:
            return {"lesson": "Сьогодні вихідний! Відпочиньте (p≧w≦q)", "ring": None}
        if (rings[0]["start"] - timedelta(minutes=5)) > date_time:
            return {"lesson": "Ще дуже рано! Відпочиньте ( *︾▽︾)", "ring": None}
        if rings[-1]["end"] < date_time:
            return {"lesson": "Заняття вже закінчились! Відпочиньте o(*^▽^*)┛", "ring": None}
        for ring in rings:
            if (ring["start"] - timedelta(minutes=5)) < date_time < ring["end"]:
                break
        else:
            return {"lesson": "Зараз перерва, відпочиньте! ლ(╹◡╹ლ)", "ring": None}
        return {"lesson": self.get_lesson(date_time.isoweekday(), ring["id"], date_time), "ring": ring}


    @overload
    def get_timetable(self, date: datetime) -> str:
        ...

    @overload
    def get_timetable(self, weekday: int) -> str:
        ...

    @singledispatchmethod
    def get_timetable(self, _) -> str:
        raise ValueError("Має бути задан тільки один аргумент, або datetime, або int!")

    def __get_timetable(self, weekday: TableDicts.WeekdayDict, date: datetime|None) -> str:
        if not weekday["is_work_day"]:
            return f"{' ' * 2}<b>{weekday['name']}</b>:\n{' ' * 4}<b><i>Вихідний!</i></b> ヾ(≧▽≦*)o"
        else:
            timetable = list()
            for ring_id in range(1, len(self.queries.get_rings()) + 1):
                lesson = self.get_lesson(weekday['id'], ring_id, date)
                timetable.append(f"{' ' * 4}{ring_id}. {lesson['name'] if lesson is not None else 'Не знайдено! (≧﹏ ≦)'}")
            return f"{' ' * 2}<b>{weekday['name']}</b>:\n" + ";\n".join(timetable) + '.'

    @get_timetable.register
    def _(self, date: datetime) -> str:
        return self.__get_timetable(self.queries.get_weekdays()[date.weekday()], date)

    @get_timetable.register
    def _(self, weekday: int) -> str:
        return self.__get_timetable(self.queries.get_weekdays()[weekday], None)
