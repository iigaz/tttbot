from enum import Enum


class Recipient(Enum):
    SENDER = 1
    ADMIN = 128


class Message:
    def __init__(
        self,
        text: str,
        to: Recipient = Recipient.SENDER,
        is_error: bool = False,
        title: str = None,
    ):
        self.__to = to
        self.__text = text
        self.__is_error = is_error
        self.__title = (
            title if title is not None else text.splitlines()[0][:64]
        )

    @property
    def to(self):
        return self.__to

    @property
    def text(self):
        return self.__text

    @property
    def is_error(self):
        return self.__is_error

    @property
    def title(self):
        return self.__title
