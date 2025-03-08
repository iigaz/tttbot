import os
from datetime import date
from threading import Thread
from typing import List, Iterator
from time import sleep
from tempfile import gettempdir
from hashlib import md5
import sqlite3
import telebot
import schedule
from dotenv import load_dotenv
from domain.user import ConversationState, User
from repositories.settings_repository import SettingsRepository
from repositories.users_repository import UsersRepository
from services.timetable_service import TimetableService, GroupNotFoundException
from services.timetable_updater_service import TimetableUpdaterService
import services.types

telebot.apihelper.ENABLE_MIDDLEWARE = True


class TeleBot(telebot.TeleBot):
    current_user: User | None = None


TIMETABLE_FILE = os.path.join(gettempdir(), "bot-timetable.xlsx")

db = sqlite3.connect("bot.db", check_same_thread=False)

users = UsersRepository(db)
settings = SettingsRepository(db)
service = TimetableService(
    TIMETABLE_FILE, users, settings.get_week_count_start
)
updater = TimetableUpdaterService(TIMETABLE_FILE, settings)

load_dotenv()

# region Bot Initialization

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


TIMETABLE_COMMANDS = [
    telebot.types.BotCommand("week", "расписание на неделю"),
    telebot.types.BotCommand("today", "расписание на сегодня"),
    telebot.types.BotCommand("tomorrow", "расписание на завтра"),
    telebot.types.BotCommand("setgroup", "поменять группу"),
    telebot.types.BotCommand("sethl", "изменить фразы для выделения"),
    telebot.types.BotCommand("cancel", "отменить действие"),
]
ADMIN_COMMANDS = TIMETABLE_COMMANDS + [
    telebot.types.BotCommand("settt", "Обновить ссылку на расписание."),
    telebot.types.BotCommand("setwcs", "Обновить дату начала отсчета недель."),
    telebot.types.BotCommand("update", "Обновить расписание."),
]
bot.add_custom_filter(StateFilter())
bot.set_my_commands(
    commands=ADMIN_COMMANDS,
    scope=telebot.types.BotCommandScopeChat(ADMIN_CHAT_ID),
)
bot.set_my_commands(
    commands=TIMETABLE_COMMANDS,
)

# endregion

# region Helper Functions


def reply_to_message(
    request: telebot.types.Message, response: services.types.Message
):
    if response.to == services.types.Recipient.SENDER:
        bot.reply_to(request, response.text)
    elif response.to == services.types.Recipient.ADMIN:
        bot.send_message(ADMIN_CHAT_ID, response.text)
    else:
        raise Exception("Not all recipients were handled")


def send_messages_as_reply_to(
    message: telebot.types.Message, from_iter: Iterator[services.types.Message]
):
    try:
        for response in from_iter:
            reply_to_message(message, response)
    except GroupNotFoundException:
        # When setting group, we guarantee that it won't throw
        # GroupNotFoundException
        send_messages_as_reply_to(
            message, service.prompt_group(bot.current_user)
        )


def update_timetable():
    try:
        for message in updater.update_timetable():
            bot.send_message(ADMIN_CHAT_ID, message.text)
    except Exception as e:
        bot.send_message(
            ADMIN_CHAT_ID,
            f"Не удалось отправить сообщение об обновлении. Причина: {e}",
        )
        raise e


# endregion


# region Handlers


@bot.message_handler(commands=["start", "help"])
def send_welcome(message: telebot.types.Message):
    bot.reply_to(
        message,
        f"Здрасьте, {message.from_user.full_name}!\n"
        "Я умею <s>только</s> отправлять расписание!\n"
        "Для того чтобы начать, мне нужна ваша группа.",
    )
    send_messages_as_reply_to(message, service.prompt_group(bot.current_user))


@bot.message_handler(commands=["cancel"])
def exit_settings(message, react=True):
    bot.current_user.conversation_state = ConversationState.IDLE
    users.update_user(bot.current_user)
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
    bot.current_user.conversation_state = ConversationState.SETTING_LINK
    users.update_user(bot.current_user)
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
        except Exception as e:
            settings.set_timetable_link(link)
            update_timetable()
            bot.reply_to(message, f"Не удалось обновить ссылку. Причина: {e}")
    exit_settings(message, False)


@bot.message_handler(
    func=lambda m: str(m.chat.id) == ADMIN_CHAT_ID, commands=["setwcs"]
)
def set_week_count_start(message: telebot.types.Message):
    bot.current_user.conversation_state = (
        ConversationState.SETTING_WEEK_COUNT_START
    )
    users.update_user(bot.current_user)
    bot.reply_to(message, "Пришлите дату начала отсчета недель.")


@bot.message_handler(states=[ConversationState.SETTING_WEEK_COUNT_START])
def handle_set_week_count_start(message: telebot.types.Message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.reply_to(
            message, "У вас нет прав на это действие. (Вы как сюда попали?)"
        )
    else:
        try:
            nd = date.fromisoformat(message.text)
            settings.set_week_count_start(nd)
            bot.set_message_reaction(
                message.chat.id,
                message.id,
                [telebot.types.ReactionTypeEmoji("👌")],
            )
        except Exception:
            bot.reply_to(message, "Это не дата.")

    exit_settings(message, False)


@bot.message_handler(
    func=lambda m: str(m.chat.id) == ADMIN_CHAT_ID, commands=["update"]
)
def update_timetable_command(message: telebot.types.Message):
    send_messages_as_reply_to(message, updater.update_timetable(force=True))
    bot.set_message_reaction(
        message.chat.id,
        message.id,
        [telebot.types.ReactionTypeEmoji("👌")],
    )


@bot.message_handler(commands=["setgroup"])
def set_user_group(message):
    send_messages_as_reply_to(message, service.prompt_group(bot.current_user))


@bot.message_handler(states=[ConversationState.SETTING_GROUP])
def handle_set_group(message: telebot.types.Message):
    user = bot.current_user
    group = message.text
    tt = service.try_group(group)
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


@bot.message_handler(commands=["sethl"])
def set_hl(message):
    bot.reply_to(
        message,
        "Пришлите фразы, "
        "которые нужно выделить в расписании, "
        "по одной на строке.\n\n"
        f"Ваша группа ({bot.current_user.group}) выделяется всегда, "
        "вне зависимости от заданных фраз.\n"
        + (
            "Кроме нее, также выделяются следующие фразы:"
            if len(bot.current_user.highlight_phrases) > 0
            else ""
        ),
    )
    if len(bot.current_user.highlight_phrases) > 0:
        bot.reply_to(message, bot.current_user.highlight_phrases)
    bot.current_user.conversation_state = (
        ConversationState.SETTING_HIGHLIGHT_PHRASES
    )
    users.update_user(bot.current_user)


@bot.message_handler(states=[ConversationState.SETTING_HIGHLIGHT_PHRASES])
def handle_set_hl(message: telebot.types.Message):
    success = bot.current_user.try_set_highlight_phrases(message.text)
    if success:
        bot.current_user.conversation_state = ConversationState.IDLE
        users.update_user(bot.current_user)
        bot.reply_to(message, "Фразы сохранены.")
    else:
        bot.reply_to(
            message,
            "К сожалению, фраз слишком много и/или они слишком длинные. "
            "Попробуйте задать меньше фраз или уменьшить их длину.",
        )


@bot.message_handler(states=[ConversationState.IDLE], commands=["week"])
def timetable_week(message):
    send_messages_as_reply_to(
        message,
        service.timetable_range(
            bot.current_user.group, 0, 7, bot.current_user.highlight_phrases
        ),
    )


@bot.message_handler(states=[ConversationState.IDLE], commands=["today"])
def timetable_today(message):
    send_messages_as_reply_to(
        message,
        service.timetable_range(
            bot.current_user.group, 0, 1, bot.current_user.highlight_phrases
        ),
    )


@bot.message_handler(state=[ConversationState.IDLE], commands=["tomorrow"])
def timetable_tomorrow(message):
    send_messages_as_reply_to(
        message,
        service.timetable_range(
            bot.current_user.group, 1, 1, bot.current_user.highlight_phrases
        ),
    )


@bot.message_handler(states=[ConversationState.IDLE])
def handle_idle(message: telebot.types.Message):
    send_messages_as_reply_to(
        message,
        service.guess_request(
            bot.current_user.group,
            message.text,
            bot.current_user.highlight_phrases,
        ),
    )


@bot.message_handler(func=lambda m: True)
def unknown_message(message: telebot.types.Message):
    bot.reply_to(message, "Вы нашли ошибку в боте !!!")
    bot.send_message(ADMIN_CHAT_ID, "Кто-то нашел ошибку в боте !!!")


@bot.inline_handler(func=lambda q: True)
def inline_request(inline_query: telebot.types.InlineQuery):
    user = users.get_user_by_id(inline_query.from_user.id)
    group = user.group if user is not None else None
    hp = user.highlight_phrases if user is not None else None
    results = []
    try:
        for message in service.guess_everything(inline_query.query, group, hp):
            if message.to == services.types.Recipient.ADMIN:
                bot.send_message(ADMIN_CHAT_ID, message.text)
                continue
            if message.is_error:
                results = []
                break
            mid = md5(message.text.encode("utf-8")).hexdigest()
            group = message.get_meta("group") or "?"
            day = message.get_meta("day")
            title = message.get_meta("weekday") or "???"
            results.append(
                telebot.types.InlineQueryResultArticle(
                    mid,
                    title,
                    telebot.types.InputTextMessageContent(
                        message.text, parse_mode="HTML"
                    ),
                    description=f"Расписание группы {group}"
                    + (f" на {day}" if day else ""),
                    hide_url=True,
                )
            )
    except GroupNotFoundException:
        results = []
    bot.answer_inline_query(
        inline_query.id,
        results,
        cache_time=60,
        is_personal=(user is not None),
    )


# endregion


def scheduler():
    schedule.every(5).minutes.do(update_timetable)
    while True:
        schedule.run_pending()
        sleep(60)


update_timetable()


Thread(target=scheduler, daemon=True).start()
bot.infinity_polling()
