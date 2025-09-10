import random
import logging
from typing import TypedDict, cast
from datetime import datetime, timedelta

from mysql.connector.cursor import MySQLCursorDict

from JSON import JSON

class DictTypes:

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
        flasher_id: int | None
        replacement_id: int | None
        remind: str | None

    class ComposedLessonDict(TypedDict):
        name: str
        link: str
        remind: str | None



class Queries:
    def __init__(self, cursor: MySQLCursorDict, logger: logging.Logger, json_file: JSON):
        self.cursor = cursor
        self.logger = logger
        self.json_file = json_file

    def is_new_user(self, user_id: int) -> bool:
        self.cursor.execute("SELECT 1 FROM `user` WHERE id = %s", [user_id])
        if self.cursor.fetchone() is None:
            self.cursor.execute("INSERT INTO `user` VALUES (%s, %s)", [user_id, False])
            return True
        return False

    def set_subscription(self, user_id: int, is_subscriber: bool) -> None:
        if self.is_new_user(user_id):
            self.logger.info("Якись користувач не був зареєстрований але змінив підписку. (Зараз зареєстрован)")
        self.cursor.execute("UPDATE `user` SET is_subscriber = %s WHERE id = %s", [is_subscriber, user_id])

    def get_sticker_id(self, sticker_type: list[str] | str) -> str:
        selected_type: str = random.choice(sticker_type) if isinstance(sticker_type, list) else sticker_type
        self.cursor.execute("SELECT id FROM `sticker` WHERE type = %s", [selected_type])
        selected_stickers: list[DictTypes.StickerDict] = cast(list[DictTypes.StickerDict], self.cursor.fetchall())
        if len(selected_stickers) < 1:
            self.logger.error(f"Жодного стикеру типу {selected_type} не було знайдена в базі даних!")
            if isinstance(sticker_type, list) and len(sticker_type) > 1:
                sticker_type.remove(selected_type)
                return self.get_sticker_id(sticker_type)
            raise ValueError
        return cast(str, random.choice(selected_stickers)["id"])

    def get_rings_schedule(self) -> list[DictTypes.RingDict]:
        self.cursor.execute("SELECT * FROM `ring`")
        return cast(list[DictTypes.RingDict], self.cursor.fetchall())

    def get_weekdays(self) -> list[DictTypes.WeekdayDict]:
        self.cursor.execute("SELECT * FROM `weekday`")
        return cast(list[DictTypes.WeekdayDict], self.cursor.fetchall())

    def get_lesson(self, lesson_id: int) -> DictTypes.LessonDict:
        self.cursor.execute("SELECT * FROM `lesson` WHERE id = %s", [lesson_id])
        lesson: DictTypes.LessonDict | None = cast(DictTypes.LessonDict, self.cursor.fetchone())
        if lesson is None:
            self.logger.error(f"Заняття з айді {lesson_id} не було знайдено в базі даних!")
            raise ValueError
        return lesson
        

    def compose_lesson(self, isoweekday: int, ring_id: int, date: datetime, enable_flasher_replacement: bool = False) -> DictTypes.ComposedLessonDict | None:
        self.cursor.execute("SELECT * FROM `timetable` WHERE weekday_id = %s AND ring_id = %s", [isoweekday, ring_id])
        timetable: DictTypes.TimetableDict | None = cast(DictTypes.TimetableDict, self.cursor.fetchone())
        if timetable is None:
            return None

        if isinstance(timetable["replacement_id"], int):
            lesson: DictTypes.LessonDict = self.get_lesson(timetable["replacement_id"])
            lesson["name"] += " (заміна)"
            flasher = None
        else:
            lesson: DictTypes.LessonDict = self.get_lesson(timetable["lesson_id"])
            flasher: DictTypes.LessonDict | None = self.get_lesson(timetable["flasher_id"]) if timetable["flasher_id"] is not None else None

        if enable_flasher_replacement or isinstance(timetable["replacement_id"], int) or flasher is None:
            try:
                first_flasher_monday = datetime.fromisoformat(cast(str, self.json_file.get("first_flasher_monday")))
            except ValueError:
                self.logger.error("Змінна \"first_flasher_monday\" не була знайдена в JSON файлі! Помилка не оброблена!")
                raise 

            if flasher is not None and not ((date.replace(tzinfo=None) - timedelta(days=date.weekday()) - first_flasher_monday).days // 7) % 2:
                lesson = flasher
            composed_lesson: DictTypes.ComposedLessonDict = {
                "name": f"<b><i>{lesson['name']}</i></b>",
                "link": f"\n\n<b>Посилання на заняття:</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}",
                "remind": timetable["remind"]
                }
            return composed_lesson

        composed_lesson: DictTypes.ComposedLessonDict = {
            "name": f"<b><i>{lesson['name']} / {flasher['name']}</i></b>",
            "link": (f"\n\n<b>Посилання на заняття ({lesson['name']}):</b>\n{lesson['link']}\n\n<b>Посилання на клас:</b>\n{lesson['class']}"
                     f"\n\n\n<b>Посилання на заняття ({flasher['name']}):</b>\n{flasher['link']} \n\n<b>Посилання на клас:</b> \n{flasher['class']}"),
            "remind": timetable["remind"]
            }
        return composed_lesson
