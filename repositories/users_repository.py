from domain.user import User, ConversationState
from domain.limits import USER_HIGHLIGHT_PHRASES_LEN
from sqlite3 import Connection


class UsersRepository:
    def __init__(self, db: Connection, remove_db=False):
        self.__db = db
        cur = db.cursor()
        if remove_db:
            cur.execute('DROP TABLE IF EXISTS "users"')
        cur.execute(
            f"""
CREATE TABLE IF NOT EXISTS "users" (
    "id" BIGINT PRIMARY KEY,
    "group" VARCHAR(10) NOT NULL DEFAULT '',
    "conversation_state" INTEGER NOT NULL DEFAULT 1,
    "highlight_phrases" VARCHAR({USER_HIGHLIGHT_PHRASES_LEN})
                        NOT NULL DEFAULT ''
)"""
        )
        db.commit()

    def get_user_by_id(self, user_id: int) -> User | None:
        cur = self.__db.cursor()
        res = cur.execute('SELECT * FROM "users" WHERE "id"=?', (user_id,))
        user_row = res.fetchone()
        if user_row is None:
            return None
        (uid, group, state, phrases) = user_row
        user = User(uid)
        user.group = group
        user.conversation_state = ConversationState(state)
        user.try_set_highlight_phrases(phrases)
        return user

    def get_or_add_user_by_id(self, user_id: int) -> User:
        user = self.get_user_by_id(user_id)
        if user is None:
            cur = self.__db.cursor()
            res = cur.execute(
                'INSERT INTO "users"("id") VALUES (?) RETURNING *', (user_id,)
            )
            user_row = res.fetchone()
            self.__db.commit()
            if user_row:
                (uid, group, state, phrases) = user_row
                user = User(uid)
                user.group = group
                user.conversation_state = ConversationState(state)
                user.try_set_highlight_phrases(phrases)
                return user
            print("Could not save user.")
            return User(user_id)
        return user

    def update_user(self, user: User) -> None:
        cur = self.__db.cursor()
        cur.execute(
            'UPDATE OR IGNORE "users"'
            'SET "group" = ?, '
            '"conversation_state" = ?, '
            '"highlight_phrases" = ? '
            'WHERE "id" = ?',
            (
                user.group,
                int(user.conversation_state),
                user.highlight_phrases,
                user.id,
            ),
        )
        self.__db.commit()
