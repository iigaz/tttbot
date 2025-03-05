from enum import IntEnum


class ConversationState(IntEnum):
    # User states
    IDLE = 1
    SETTING_GROUP = 2

    # Administration states
    SETTING_LINK = 32


class User:
    def __init__(self, id: int):
        self.__id = id
        self.__conversation_state = ConversationState.IDLE
        self.__group = ""

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
    def id(self) -> int:
        return self.__id
