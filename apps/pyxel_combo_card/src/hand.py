"""手札管理モジュール"""

from typing import List

try:
    from .card import Card  # pylint: disable=C0413
except ImportError:
    from card import Card  # pylint: disable=C0413


class Hand:
    """手札を管理するクラス

    定数:
        MAX_HAND_SIZE: 手札の最大枚数（画面表示可能枚数を考慮して7枚に設定）
                       画面幅300px、カード幅30px、カード間隔10px の場合、
                       1行に表示可能な枚数は約7枚（プレイテストで確認済み）
    """

    MAX_HAND_SIZE = 7

    def __init__(self) -> None:
        self._cards: List[Card] = []

    def get_cards(self) -> List[Card]:
        return self._cards

    def add_card(self, card: Card) -> None:
        self._cards.append(card)

    def find_card_indices(self, target_cards: List[Card]) -> List[int]:
        """指定されたカードのインデックスを検索する

        Args:
            target_cards: 検索対象のカードリスト

        Returns:
            カードのインデックスリスト

        Raises:
            ValueError: 指定されたカードが手札に存在しない場合
        """
        index_list = []
        for target_card in target_cards:
            found = False
            for index, card in enumerate(self._cards):
                if card == target_card and index not in index_list:
                    index_list.append(index)
                    found = True
                    break
            if not found:
                raise ValueError("指定されたカードは手札に存在しません")
        return index_list

    def remove_card_at_index(self, index: int) -> None:
        """指定されたインデックスのカードを削除する

        Args:
            index: 削除するカードのインデックス

        Raises:
            IndexError: インデックスが範囲外の場合
        """
        self._cards.pop(index)
