from datetime import datetime
from typing import cast

from Sql_Queries import Queries, DictTypes 


class Timetable_Functions:
    def __init__(self, queries: Queries):
        self.queries = queries

    def get_next_workday(self, weekday: int) -> DictTypes.WeekdayDict|None:
        weekdays: list[DictTypes.WeekdayDict] = self.queries.get_weekdays()
        for day in range(1, 8):
            day_index = (weekday + day) % 7
            if weekdays[day_index]["is_work_day"]:
                return weekdays[day_index]
        return None

    def get_timetable(self, *, date: datetime|None = None, weekday: int|None = None) -> str:
        if (date is None) == (weekday is None):
            raise ValueError("Має бути задан тільки один аргумент, або date, або weekday!")

        weekday_dict: DictTypes.WeekdayDict = self.queries.get_weekdays()[cast(datetime, date).weekday() if date is not None else cast(int, weekday)]
        if not weekday_dict["is_work_day"]:
            return f"{' ' * 2}<b>{weekday_dict['name']}</b>:\n{' ' * 4}<b><i>Вихідний!</i></b> ヾ(≧▽≦*)o"
        else:
            timetable = list()
            for ring_id in range(1, len(self.queries.get_rings_schedule()) + 1):
                lesson = self.queries.compose_lesson(weekday_dict['id'], ring_id, date)
                timetable.append(f"{' ' * 4}{ring_id}. {lesson['name'] if lesson is not None else 'Не знайдено! (≧﹏ ≦)'}")
            return f"{' ' * 2}<b>{weekday_dict['name']}</b>:\n" + ";\n".join(timetable) + '.'
