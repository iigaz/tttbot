from enum import Enum
from typing import Dict


class Recipient(Enum):
    SENDER = 1
    ADMIN = 128


class Message:
    def __init__(
        self,
        text: str,
        to: Recipient = Recipient.SENDER,
        is_error: bool = False,
        meta: Dict[str, str] = {},
    ):
        self.__to = to
        self.__text = text
        self.__is_error = is_error
        self.__meta = meta

    @property
    def to(self):
        return self.__to

    @property
    def text(self):
        return self.__text

    @property
    def is_error(self):
        return self.__is_error

    def get_meta(self, key: str):
        return self.__meta.get(key)
