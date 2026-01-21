"""カード関連のモジュール

要件:
- カードはシンボルを持つ
"""

from enum import Enum


class Symbol(Enum):
    """カードのシンボル"""

    B1 = (1, 2)
    B2 = (2, 2)
    B3 = (3, 2)
    S1 = (1, 3)
    S2 = (2, 3)
    S3 = (3, 3)
    S4 = (4, 3)
    S5 = (5, 3)
    H1 = (1, 4)
    H2 = (2, 4)
    H3 = (3, 4)
    H4 = (4, 4)
    G1 = (1, 5)
    G2 = (2, 5)

    @classmethod
    def is_goal(cls, symbol) -> bool:
        """シンボルがゴールシンボル（G1, G2）かどうかを判定"""
        return symbol in (cls.G1, cls.G2)


class Card:
    """カードを表すクラス

    カードはシンボル（Symbol enum）を持つ。
    """

    def __init__(self, symbol: Symbol) -> None:
        self._symbol = symbol

    @property
    def symbol(self) -> Symbol:
        """カードのシンボルを取得"""
        return self._symbol

    def __repr__(self) -> str:
        return f"Card(symbol={self._symbol.name})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self._symbol == other._symbol

    def __hash__(self) -> int:
        return hash(self._symbol)

    def has_goal_symbol(self) -> bool:
        """カードがゴールシンボル（G1, G2）を持つかどうかを判定"""
        return Symbol.is_goal(self._symbol)
