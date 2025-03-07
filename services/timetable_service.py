from typing import Iterator
from services.types import Message
from repositories.users_repository import UsersRepository
from domain.user import User, ConversationState
from domain.timetable_parser import get_timetable_for_group_from_file
import re
from datetime import datetime, timedelta, timezone


class GroupNotFoundException(Exception):
    def __init__(self):
        super(GroupNotFoundException, self).__init__("Could not find group.")


class TimetableService:
    def __init__(self, timetable_file: str, users_repository: UsersRepository):
        self.__timetable_file = timetable_file
        self.__users = users_repository

    def prompt_group(self, user: User) -> Iterator[Message]:
        user.conversation_state = ConversationState.SETTING_GROUP
        self.__users.update_user(user)
        yield Message("Напишите, пожалуйста, свою группу.")

    def timetable_range_starting_from(
        self, group: str, start: int, length: int, highlight_phrases: str = ""
    ) -> Iterator[Message]:
        tt = get_timetable_for_group_from_file(self.__timetable_file, group)
        if tt is None:
            raise GroupNotFoundException()
        for i in range(length):
            day = tt.timetable[(start + i) % len(tt.timetable)]
            reply = f"<b><u>{day.weekday}:</u></b>\n"
            for row in day.timetable:
                lesson = row.lessons or "—"
                highlights = [group] + highlight_phrases.splitlines()
                for highlight in highlights:
                    lesson = re.sub(
                        re.escape(highlight),
                        r"<i><u>\g<0></u></i>",
                        lesson,
                        flags=re.IGNORECASE,
                    )
                reply += f"\n<b><i>{row.time}</i></b>\n{lesson}\n"
            if len(day.timetable) == 0:
                reply += '<span class="tg-spoiler">отдыхать</span>'
            yield Message(reply)

    def timetable_range(
        self,
        group: str,
        start_delta_days: int,
        length: int,
        highlight_phrases: str = "",
    ) -> Iterator[Message]:
        now = datetime.now(timezone.utc) + timedelta(
            days=start_delta_days, hours=3
        )
        return self.timetable_range_starting_from(
            group, now.weekday(), length, highlight_phrases
        )

    def guess_request(
        self, group: str, text: str, highlight_phrases: str = ""
    ) -> Iterator[Message]:
        DAYS = [
            "понедельник",
            "вторник",
            "сред[ау]",
            "четверг",
            "пятниц[ау]",
            "суббот[ау]",
            "воскресенье",
        ]
        REQUESTS_WORDS = {
            "сегодня": (0, 1),
            "завтра": (1, 1),
            "послезавтра": (2, 1),
            "вчера": (-1, 1),
            "позавчера": (-2, 1),
            "недел[яю]": (0, 7),
        }
        if re.match(r"^[+-]?\d{1,2}$", text):
            try:
                if text.startswith("+") or text.startswith("-"):
                    return self.timetable_range(
                        group, int(text), 1, highlight_phrases
                    )

                return self.timetable_range_starting_from(
                    group, (int(text) - 1) % 7, 1, highlight_phrases
                )
            except ValueError:
                pass
        date = re.match(r"^(\d{1,2})\.(\d{1,2})?$", text)
        if date:
            groups = date.groups()
            now = datetime.now(timezone.utc) + timedelta(hours=3)
            day = int(groups[0]) if len(groups) > 0 and groups[0] else now.day
            month = (
                int(groups[1]) if len(groups) > 1 and groups[1] else now.month
            )
            weekday = datetime(now.year, month, day, now.hour).weekday()
            return self.timetable_range_starting_from(
                group, weekday, 1, highlight_phrases
            )
        for i in range(len(DAYS)):
            if re.search(rf"\b{DAYS[i]}\b", text, re.IGNORECASE):
                return self.timetable_range_starting_from(
                    group, i, 1, highlight_phrases
                )
        for req, t in REQUESTS_WORDS.items():
            if re.search(rf"\b{req}\b", text, re.IGNORECASE):
                return self.timetable_range(
                    group, t[0], t[1], highlight_phrases
                )
        return iter(
            [
                Message(
                    "Не удалось распознать, на какой день запрошено "
                    "расписание.\n"
                    "\nВозможные форматы запроса:\n"
                    "- День недели числом (1-7), начиная с Понедельника.\n"
                    "  Примеры: 4; 1\n"
                    "- День недели отдельным словом в любом месте сообщения.\n"
                    "  Примеры: на пятницу; среда\n"
                    "- Сдвиг дня недели числом, от текущего.\n"
                    "  Примеры: +2; -1\n"
                    "- Сдвиг отдельным словом в любом месте сообщения.\n"
                    "  Примеры: на сегодня; на вчера; послезавтра; на неделю\n"
                    "- Дата в <i>текущем</i> году (месяце), в формате "
                    "<code>день.[месяц]</code>.\n"
                    "  Примеры: 3.; 03.12; 1.1"
                )
            ]
        )

    def guess_everything(
        self,
        text: str,
        user_group: str | None = None,
        user_highlight_phrases: str | None = None,
    ) -> Iterator[Message]:
        res = re.search(r"\b(\d{1,2}-\d{2,3}\w{,2})\b(.*)", text)
        if res and len(res.groups()) >= 2:
            groups = res.groups()
            group = groups[0]
            rest = groups[1].strip()
            if group and rest:
                return self.guess_request(group, rest, user_highlight_phrases)
        if user_group is not None:
            return self.guess_request(user_group, text, user_highlight_phrases)
        raise GroupNotFoundException()

    def try_group(self, group: str) -> bool:
        try:
            self.timetable_range_starting_from(group, 0, 0)
            return True
        except GroupNotFoundException:
            return False
