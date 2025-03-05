from sqlite3 import Connection


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
        cur.execute(
            'INSERT OR IGNORE INTO "settings" VALUES (?, ?)', ("link", "")
        )
        db.commit()

    def get_timetable_link(self) -> str:
        cur = self.__db.cursor()
        res = cur.execute(
            'SELECT "value" FROM "settings" WHERE "name" = ?',
            ("link",),
        )
        link_row = res.fetchone()
        if link_row is None:
            print("Could not find link in DB.")
            return ""
        return link_row[0]

    def set_timetable_link(self, new_link: str) -> None:
        cur = self.__db.cursor()
        cur.execute(
            'UPDATE "settings" SET "value" = ? WHERE "name" = ?',
            (new_link, "link"),
        )
        self.__db.commit()
