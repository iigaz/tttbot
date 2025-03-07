from enum import Enum


class Recipient(Enum):
    SENDER = 1
    ADMIN = 128


class Message:
    def __init__(self, text: str, to: Recipient = Recipient.SENDER):
        self.__to = to
        self.__text = text

    @property
    def to(self):
        return self.__to

    @property
    def text(self):
        return self.__text
