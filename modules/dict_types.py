from types import NoneType
from typing import TypedDict
from datetime import datetime

class MySQLConnectionDict(TypedDict):
    user: str
    password: str
    host: str
    database: str
    autocommit: bool

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

    class UserDict(TypedDict):
        id: int
        is_subscriber: bool

    class TimetableDict(TypedDict):
        id: int
        weekday_id: int
        ring_id: int
        lesson_id: int
        flasher_id: int|None
        replacement_id: int|None
        remind: str|None

    LessonDict = TypedDict("LessonDict", {"id": int, "name": str, "link": str|None, "class": str|None, "max_grade": int|None})

class TimetableDicts:
    class LessonDict(TypedDict):
        name: str
        link: str
        remind: str|None
        lesson_id: int

    class FoundLessonDict(TypedDict):
        lesson: "TimetableDicts.LessonDict|NoneType"
        ring: TableDicts.RingDict
