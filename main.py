import os
import re
from threading import Lock, Thread
from typing import List
from datetime import datetime
from datetime import timezone
from datetime import timedelta
from time import sleep
from tempfile import gettempdir
import sqlite3
import telebot
import schedule
from dotenv import load_dotenv
from domain.timetable_loader import download_timetable_from_url
from domain.timetable_parser import get_timetable_for_group_from_file
from domain.user import ConversationState, User
from repositories.settings_repository import SettingsRepository
from repositories.users_repository import UsersRepository

telebot.apihelper.ENABLE_MIDDLEWARE = True


class TeleBot(telebot.TeleBot):
    current_user: User | None = None


TIMETABLE_FILE = os.path.join(gettempdir(), "bot-timetable.xlsx")
file_lock = Lock()

db = sqlite3.connect("bot.db", check_same_thread=False)

settings = SettingsRepository(db)
users = UsersRepository(db)

load_dotenv()

bot = TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


class StateFilter(telebot.custom_filters.AdvancedCustomFilter):
    key = "states"

    @staticmethod
    def check(message: telebot.types.Message, states: List[ConversationState]):
        if hasattr(bot, "current_user") and bot.current_user:
            return bot.current_user.conversation_state in states
        print("Could not get field 'current_user' in bot")
        return False


@bot.middleware_handler(update_types=["message"])
def set_current_user(
    bot_instance: telebot.TeleBot, message: telebot.types.Message
):
    bot_instance.current_user = users.get_or_add_user_by_id(
        message.from_user.id
    )


def update_timetable():
    link = settings.get_timetable_link()
    if link:
        with file_lock:
            download_timetable_from_url(link, TIMETABLE_FILE)
    else:
        bot.send_message(
            ADMIN_CHAT_ID,
            "Укажите, пожалуйста, ссылку на расписание. "
            "Для этого напишите /settt.",
        )


def init():
    bot.add_custom_filter(StateFilter())
    bot.delete_my_commands(scope=None, language_code=None)
    bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("week", "расписание на неделю"),
            telebot.types.BotCommand("today", "расписание на сегодня"),
            telebot.types.BotCommand("tomorrow", "расписание на завтра"),
            telebot.types.BotCommand("setgroup", "поменять группу"),
            telebot.types.BotCommand("cancel", "отменить действие"),
        ],
    )


def prompt_group(message: telebot.types.Message, user: User):
    user.conversation_state = ConversationState.SETTING_GROUP
    users.update_user(user)
    bot.reply_to(message, "Напишите, пожалуйста, свою группу.")


@bot.message_handler(commands=["start", "help"])
def send_welcome(message: telebot.types.Message):
    user = users.get_or_add_user_by_id(message.from_user.id)
    bot.reply_to(
        message,
        f"Здрасьте, {message.from_user.full_name}!\n"
        "Я умею только отправлять расписание!\n"
        "Ладно, это шутка.\n\nЯ ничего не умею.",
    )
    prompt_group(message, user)
    if str(message.chat.id) == ADMIN_CHAT_ID:
        bot.send_message(
            ADMIN_CHAT_ID,
            "Здравствуйте. Этот чат был назначен как административный.\n"
            "Помимо обычных команд, вам также доступны:\n"
            "/settt - обновить ссылку на расписание;\n"
            "/update - обновить данные расписания.\n"
            "А еще вы получаете это эксклюзивное сообщение.",
        )


@bot.message_handler(commands=["cancel"])
def exit_settings(message, react=True):
    user = users.get_or_add_user_by_id(message.from_user.id)
    user.conversation_state = ConversationState.IDLE
    users.update_user(user)
    if react:
        bot.set_message_reaction(
            message.chat.id,
            message.id,
            [telebot.types.ReactionTypeEmoji("👌")],
        )


@bot.message_handler(
    func=lambda m: str(m.chat.id) == ADMIN_CHAT_ID, commands=["settt"]
)
def set_timetable(message: telebot.types.Message):
    user = bot.current_user
    user.conversation_state = ConversationState.SETTING_LINK
    users.update_user(user)
    bot.reply_to(message, "Пришлите новую ссылку.")


@bot.message_handler(states=[ConversationState.SETTING_LINK])
def handle_set_timetable(message: telebot.types.Message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.reply_to(
            message, "У вас нет прав на это действие. (Вы как сюда попали?)"
        )
    else:
        link = settings.get_timetable_link()
        try:
            settings.set_timetable_link(message.text)
            update_timetable()
            bot.reply_to(message, "Ссылка была обновлена.")
        except Exception:
            settings.set_timetable_link(link)
            update_timetable()
            bot.reply_to(message, "Не удалось обновить ссылку.")
    exit_settings(message, False)


@bot.message_handler(
    func=lambda m: str(m.chat.id) == ADMIN_CHAT_ID, commands=["update"]
)
def update_timetable_command(message: telebot.types.Message):
    update_timetable()
    bot.reply_to(message, "Расписание было обновлено.")


@bot.message_handler(commands=["setgroup"])
def set_user_group(message):
    user = users.get_or_add_user_by_id(message.from_user.id)
    prompt_group(message, user)


@bot.message_handler(states=[ConversationState.SETTING_GROUP])
def handle_set_group(message: telebot.types.Message):
    user = bot.current_user
    group = message.text
    tt = get_timetable_for_group_from_file(TIMETABLE_FILE, group)
    if not tt:
        bot.reply_to(
            message,
            "Группа не была найдена в расписании. Попробуйте другую.",
        )
        return
    user.conversation_state = ConversationState.IDLE
    user.group = group
    users.update_user(user)
    bot.set_message_reaction(
        message.chat.id,
        message.id,
        [telebot.types.ReactionTypeEmoji("👍")],
    )
    bot.reply_to(message, "Теперь можно получать расписание.")


def timetable_range_starting_from(
    message: telebot.types.Message, start: int, length: int
):
    user = bot.current_user
    if not user.group:
        prompt_group(message, user)
        return
    tt = get_timetable_for_group_from_file(TIMETABLE_FILE, user.group)
    for i in range(length):
        day = tt.timetable[(start + i) % len(tt.timetable)]
        reply = f"<b><u>{day.weekday}:</u></b>\n"
        for row in day.timetable:
            lesson = (row.lessons or "—").replace(
                user.group, "<i><u>" + user.group + "</u></i>"
            )
            reply += f"\n<b><i>{row.time}</i></b>\n{lesson}\n"
        if len(day.timetable) == 0:
            reply += '<span class="tg-spoiler">отдыхать</span>'
        bot.reply_to(message, reply)


def timetable_range(
    message: telebot.types.Message, start_delta_days: int, length: int
):
    now = datetime.now(timezone.utc) + timedelta(
        days=start_delta_days, hours=3
    )
    timetable_range_starting_from(message, now.weekday(), length)


@bot.message_handler(states=[ConversationState.IDLE], commands=["week"])
def timetable_week(message):
    timetable_range(message, 0, 7)


@bot.message_handler(states=[ConversationState.IDLE], commands=["today"])
def timetable_today(message):
    timetable_range(message, 0, 1)


@bot.message_handler(state=[ConversationState.IDLE], commands=["tomorrow"])
def timetable_tomorrow(message):
    timetable_range(message, 1, 1)


@bot.message_handler(states=[ConversationState.IDLE])
def handle_idle(message: telebot.types.Message):
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
    if re.match(r"^[+-]?\d{1,2}$", message.text):
        try:
            if message.text.startswith("+") or message.text.startswith("-"):
                timetable_range(message, int(message.text), 1)
                return
            timetable_range_starting_from(
                message, (int(message.text) - 1) % 7, 1
            )
            return
        except ValueError:
            pass
    date = re.match(r"^(\d{1,2})\.(\d{1,2})?$", message.text)
    if date:
        groups = date.groups()
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        day = int(groups[0]) if len(groups) > 0 and groups[0] else now.day
        month = int(groups[1]) if len(groups) > 1 and groups[1] else now.month
        weekday = datetime(now.year, month, day, now.hour).weekday()
        timetable_range_starting_from(message, weekday, 1)
        return
    for i in range(len(DAYS)):
        if re.search(rf"\b{DAYS[i]}\b", message.text, re.IGNORECASE):
            timetable_range_starting_from(message, i, 1)
            return
    for req, t in REQUESTS_WORDS.items():
        if re.search(rf"\b{req}\b", message.text, re.IGNORECASE):
            timetable_range(message, t[0], t[1])
            return
    user = users.get_or_add_user_by_id(message.from_user.id)
    if not user.group:
        prompt_group(message, user)
        return
    bot.reply_to(
        message,
        "Не удалось распознать, на какой день запрошено расписание.\n"
        "\nВозможные форматы запроса:\n"
        "- День недели числом (1-7), начиная с Понедельника.\n"
        "  Примеры: 4; 1\n"
        "- День недели отдельным словом в любом месте сообщения.\n"
        "  Примеры: на пятницу; среда\n"
        "- Сдвиг дня недели числом, от текущего.\n"
        "  Примеры: +2; -1\n"
        "- Сдвиг отдельным словом в любом месте сообщения.\n"
        "  Примеры: на сегодня; на вчера; послезавтра; на неделю\n"
        "- Дата в <i>текущем</i> году (месяце), в формате день.[месяц].\n"
        "  Примеры: 3.; 03.12; 1.1",
    )


@bot.message_handler(func=lambda m: True)
def unknown_message(message: telebot.types.Message):
    bot.reply_to(message, "Вы нашли ошибку в боте !!!")


def scheduler():
    schedule.every(5).minutes.do(update_timetable)
    while True:
        schedule.run_pending()
        sleep(1)


init()
update_timetable()


Thread(target=scheduler, daemon=True).start()
bot.infinity_polling()
