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

    def get_lesson(self, isoweekday: int, lesson_number: int, target_date: date|None = None) -> TimetableDicts.LessonDict|None:
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

        if target_date is not None or isinstance(timetable["replacement_id"], int) or flasher is None:
            if flasher is not None and isinstance(target_date, date):
                try:
                    first_flasher_monday = date.fromisoformat(cast(str, self.json_file.get("first_flasher_monday")))
                except ValueError:
                    self.logger.error("Змінна \"first_flasher_monday\" не була знайдена в JSON файлі! Помилка не оброблена!")
                    raise 
                if ((target_date - timedelta(days=target_date.weekday()) - first_flasher_monday).days // 7) % 2:
                    lesson = flasher            
            return  {
                "name": f"<b><i>{lesson['name']}</i></b>",
                "link": f"\n\n<b>Посилання на заняття:</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}",
                "remind": remind,
                "lesson_id": lesson["id"]
            }

        return {
            "name": f"<b><i>{lesson['name']} / {flasher['name']}</i></b>",
            "link": (f"\n\n<b>Посилання на заняття ({lesson['name']}):</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}"
                        f"\n\n\n<b>Посилання на заняття ({flasher['name']}):</b>\n{flasher['link']} \n\n<b>Посилання на клас:</b> \n{flasher['class']}"),
            "remind": remind,
            "lesson_id": lesson["id"]
        }

    def get_rings(self, target_date: date) -> list[TableDicts.RingDict]:
        rings: list[TableDicts.RingDict] = self.queries.get_rings()
        for ring in rings:
            for key in ["start", "end"]:
                ring[key] = datetime.combine(target_date, ring[key].time())
        return rings


    def find_lesson(self, date_time: datetime) -> TimetableDicts.FoundLessonDict|str:
        date_time = date_time.replace(tzinfo=None)
        rings: list[TableDicts.RingDict] = self.get_rings(date_time.date())
        if not self.queries.get_weekdays()[date_time.weekday()]["is_work_day"]:
            return "Сьогодні вихідний! Відпочиньте\n(p≧w≦q)"
        if (rings[0]["start"] - timedelta(minutes=5)) > date_time:
            return "Ще дуже рано! Відпочиньте\n( *︾▽︾)"
        if rings[-1]["end"] < date_time:
            return "Заняття вже закінчились! Відпочиньте\no(*^▽^*)┛"
        for ring in rings:
            if (ring["start"] - timedelta(minutes=5)) < date_time < ring["end"]:
                break
        else:
            return "Зараз перерва, відпочиньте!\nლ(╹◡╹ლ)"
        return {"lesson": self.get_lesson(date_time.isoweekday(), ring["id"], date_time), "ring": ring}

    def find_next_lesson(self, isoweekday: int, lesson_number: int, target_date: date|None) -> TimetableDicts.FoundLessonDict|None:
        rings: list[TableDicts.RingDict] = self.queries.get_rings() if target_date is None else self.get_rings(target_date)
        for ring_id in range(lesson_number, len(rings) + 1):
            next_lesson: TimetableDicts.LessonDict|None = self.get_lesson(isoweekday, ring_id, target_date)
            if next_lesson is not None and next_lesson["lesson_id"] != 1:
                break
        else:
            return None
        return {"lesson": next_lesson, "ring": rings[ring_id]}
        

    @overload
    def get_timetable(self, target_date: date) -> str:
        ...

    @overload
    def get_timetable(self, weekday: int) -> str:
        ...

    @singledispatchmethod
    def get_timetable(self, _) -> str:
        raise ValueError("Має бути задан тільки один аргумент, або datetime, або int!")

    def __get_timetable(self, weekday: TableDicts.WeekdayDict, target_date: date|None) -> str:
        if not weekday["is_work_day"]:
            return f"{' ' * 2}<b>{weekday['name']}</b>:\n{' ' * 4}<b><i>Вихідний!</i></b> ヾ(≧▽≦*)o"
        else:
            timetable = list()
            rings_count: int = len(self.queries.get_rings())
            for ring_id in range(1, rings_count + 1):
                lesson: TimetableDicts.LessonDict|None = self.get_lesson(weekday["id"], ring_id, target_date)
                if lesson is not None:
                    if lesson["lesson_id"] == 1 and self.find_next_lesson(weekday["id"], ring_id, target_date) is None:
                        break
                    timetable.append(f"{' ' * 4}{ring_id}. {lesson['name']}")
                else:
                    timetable.append(f"{' ' * 4}{ring_id}. Не знайдено! (≧﹏ ≦)")
            return (f"{' ' * 2}<b>{weekday['name']}</b>:\n" +
                    ((";\n".join(timetable) + '.') if len(timetable) > 0 else f"{' ' * 4}<b><i>Вихідний!</i></b> ヾ(≧▽≦*)o"))

    @get_timetable.register
    def _(self, date: date) -> str:
        return self.__get_timetable(self.queries.get_weekdays()[date.weekday()], date)

    @get_timetable.register
    def _(self, weekday: int) -> str:
        return self.__get_timetable(self.queries.get_weekdays()[weekday], None)
