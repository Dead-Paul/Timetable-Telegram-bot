from typing import TypedDict
from datetime import datetime


class TableDicts:
    class RingDict(TypedDict):
        id: int
        name: str
        start: datetime
        end: datetime

    class StickerDict(TypedDict):
        id: str
        type: str

    class WeekdayDict(TypedDict):
        id: int
        name: str
        is_work_day: bool

    LessonDict = TypedDict("LessonDict", {"id": int, "name": str, "link": str, "class": str, "max_grade": int})

    class TimetableDict(TypedDict):
        id: int
        weekday_id: int
        ring_id: int
        lesson_id: int
        flasher_id: int|None
        replacement_id: int|None
        remind: str|None

class TimetableDicts:
    class LessonDict(TypedDict):
        name: str
        link: str
        remind: str|None
