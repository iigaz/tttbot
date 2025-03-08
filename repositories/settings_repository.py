from sqlite3 import Connection
from datetime import date


class SettingsRepository:
    def __init__(self, db: Connection, remove_db=False):
        self.__db = db
        cur = db.cursor()
        if remove_db:
            cur.execute('DROP TABLE IF EXISTS "settings"')
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS "settings" (
    "name" VARCHAR(20) PRIMARY KEY,
    "value" VARCHAR(2048) NOT NULL
)"""
        )
        cur.executemany(
            'INSERT OR IGNORE INTO "settings" VALUES (?, ?)',
            [("link", ""), ("week_count_start", "")],
        )
        db.commit()

    def __get_value(self, name: str) -> str | None:
        cur = self.__db.cursor()
        res = cur.execute(
            'SELECT "value" FROM "settings" WHERE "name" = ?',
            (name,),
        )
        row = res.fetchone()
        return row[0] if row else None

    def __set_value(self, name: str, value: str) -> None:
        cur = self.__db.cursor()
        cur.execute(
            'UPDATE "settings" SET "value" = ? WHERE "name" = ?',
            (value, name),
        )
        self.__db.commit()

    def get_timetable_link(self) -> str:
        link = self.__get_value("link")
        if link is None:
            print("Could not find link in DB.")
            return ""
        return link

    def set_timetable_link(self, new_link: str) -> None:
        self.__set_value("link", new_link)

    def get_week_count_start(self) -> date:
        date_str = self.__get_value("week_count_start")
        return date.fromisoformat(date_str) if date_str else None

    def set_week_count_start(self, start: date) -> None:
        self.__set_value("week_count_start", start.isoformat())
