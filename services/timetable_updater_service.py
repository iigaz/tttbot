from repositories.settings_repository import SettingsRepository
from threading import Lock
from datetime import datetime, timezone, timedelta
from domain.timetable_loader import download_timetable_from_url
from services.types import Message, Recipient
from typing import Iterator


class TimetableUpdaterService:
    def __init__(
        self, timetable_file: str, settings_repository: SettingsRepository
    ):
        self.__timetable_file = timetable_file
        self.__settings = settings_repository
        self.__lock = Lock()
        self.__last_update = datetime.fromtimestamp(0, timezone.utc)

    def really_update_timetable(self) -> bool:
        now = datetime.now(timezone.utc)
        passed = now - self.__last_update
        now += timedelta(hours=3)
        if now.hour in range(0, 7):
            # Night time, no need to update so frequently
            # Update will happen every ~3 hours
            return passed.seconds >= 3 * 60 * 60
        elif now.hour in range(7, 18):
            # Work time, modifications are likely to be made in this time range
            # Update will happen every ~5 minutes
            return passed.seconds >= 5 * 60
        else:  # 18 - 24
            # Evening, modifications can happen but not as likely
            # Update will happen every ~30 minutes
            return passed.seconds >= 30 * 60

    def update_timetable(self, force=False) -> Iterator[Message]:
        if not (force or self.really_update_timetable()):
            return
        link = self.__settings.get_timetable_link()
        if link:
            try:
                with self.__lock:
                    download_timetable_from_url(link, self.__timetable_file)
                    self.__last_update = datetime.now(timezone.utc)
            except Exception as e:
                yield Message(
                    "Не удалось обновить расписание. Причина: " + str(e),
                    Recipient.ADMIN,
                )
        else:
            yield Message(
                "Укажите, пожалуйста, ссылку на расписание. "
                "Для этого напишите /settt.",
                Recipient.ADMIN,
            )
