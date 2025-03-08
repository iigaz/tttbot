from enum import IntEnum
from typing import List

from domain.limits import USER_HIGHLIGHT_PHRASES_LEN


class ConversationState(IntEnum):
    # User states
    IDLE = 1
    SETTING_GROUP = 2
    SETTING_HIGHLIGHT_PHRASES = 3

    # Administration states
    SETTING_LINK = 256
    SETTING_WEEK_COUNT_START = 257


class User:
    def __init__(self, id: int):
        self.__id = id
        self.__conversation_state = ConversationState.IDLE
        self.__group = ""
        self.__highlight_phrases = []

    @property
    def group(self) -> str:
        return self.__group

    @group.setter
    def group(self, gr: str):
        self.__group = gr

    @property
    def conversation_state(self) -> ConversationState:
        return self.__conversation_state

    @conversation_state.setter
    def conversation_state(self, state: ConversationState):
        self.__conversation_state = state

    @property
    def highlight_phrases(self) -> str:
        return "\n".join(self.__highlight_phrases)

    def try_set_highlight_phrases(self, phrase: str) -> bool:
        if len(phrase) + 1 > USER_HIGHLIGHT_PHRASES_LEN:
            return False
        self.__highlight_phrases = phrase.splitlines()
        return True

    @property
    def id(self) -> int:
        return self.__id
