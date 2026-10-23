from enum import Enum
from typing import Optional


def enum_name(member: Optional[Enum]) -> Optional[str]:
    """Enum のメンバーを JSON にできる名前へ変換する（None はそのまま）"""
    return None if member is None else member.name


def enum_from_name(enum_class, name: Optional[str]):
    """enum_name で変換した名前を Enum のメンバーへ戻す（None はそのまま）"""
    return None if name is None else enum_class[name]
