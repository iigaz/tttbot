from domain.user import User, ConversationState
from sqlite3 import Connection


class UsersRepository:
    def __init__(self, db: Connection, remove_db=False):
        self.__db = db
        cur = db.cursor()
        if remove_db:
            cur.execute('DROP TABLE IF EXISTS "users"')
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGINT PRIMARY KEY,
    "group" VARCHAR(10) NOT NULL DEFAULT '',
    "conversation_state" INTEGER NOT NULL DEFAULT 1
)"""
        )
        db.commit()

    def get_or_add_user_by_id(self, user_id: int) -> User:
        cur = self.__db.cursor()
        res = cur.execute('SELECT * FROM "users" WHERE "id"=?', (user_id,))
        user_row = res.fetchone()
        if user_row is None:
            res = cur.execute(
                'INSERT INTO "users"("id") VALUES (?) RETURNING *', (user_id,)
            )
            user_row = res.fetchone()
            self.__db.commit()
        if user_row:
            (uid, group, state) = user_row
            user = User(uid)
            user.group = group
            user.conversation_state = ConversationState(state)
            return user
        else:
            print("Could not save user.")
            return User(user_id)

    def update_user(self, user: User) -> None:
        cur = self.__db.cursor()
        cur.execute(
            'UPDATE OR IGNORE "users"'
            'SET "group" = ?, "conversation_state" = ?'
            'WHERE "id" = ?',
            (user.group, int(user.conversation_state), user.id),
        )
        self.__db.commit()
