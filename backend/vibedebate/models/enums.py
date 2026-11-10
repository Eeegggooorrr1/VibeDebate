from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    BANNED = "banned"
    DELETED = "deleted"


class AdminAction(StrEnum):
    BAN_USER = "ban"
    UNBAN_USER = "unban"


class ChatSide(StrEnum):
    ATTACK = "attack"
    DEFENSE = "defense"
