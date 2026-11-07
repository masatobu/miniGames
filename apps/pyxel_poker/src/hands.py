"""役の判定（Pyxel に依存しないゲームのロジック）。"""

from collections import Counter
from enum import IntEnum

try:
    from .cards import HAND_SIZE, SUITS  # pylint: disable=C0413
except ImportError:
    from cards import HAND_SIZE, SUITS  # pylint: disable=C0413

# ストレートは 5 枚の最大 - 最小 = 4。A を 1 として使えるのは A-2-3-4-5 のときだけ
STRAIGHT_SPAN = HAND_SIZE - 1
ACE_LOW_RANKS = frozenset({14, 2, 3, 4, 5})
ROYAL_RANKS = frozenset({10, 11, 12, 13, 14})


class HandCategory(IntEnum):
    """役の種類。値が大きいほど強い。"""

    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_STRAIGHT_FLUSH = 10


# 数字ごとの枚数（多い順）から決まる役。ストレートとフラッシュは別に調べる
_COUNT_PATTERNS = {
    (4, 1): HandCategory.FOUR_OF_A_KIND,
    (3, 2): HandCategory.FULL_HOUSE,
    (3, 1, 1): HandCategory.THREE_OF_A_KIND,
    (2, 2, 1): HandCategory.TWO_PAIR,
    (2, 1, 1, 1): HandCategory.ONE_PAIR,
    (1, 1, 1, 1, 1): HandCategory.HIGH_CARD,
}


def is_flush(hand):
    """5 枚のマークがすべて同じなら True。"""
    return len({card.suit for card in hand}) == 1


def is_straight(hand):
    """5 枚の数字が連続していれば True。A は 14 のほか、A-2-3-4-5 のときだけ 1。"""
    ranks = {card.rank for card in hand}
    if len(ranks) != HAND_SIZE:
        return False
    return max(ranks) - min(ranks) == STRAIGHT_SPAN or ranks == ACE_LOW_RANKS


def evaluate_hand(hand):
    """5 枚の手札の役の種類を返す。5 枚でなければ ValueError。手札は変更しない。"""
    if len(hand) != HAND_SIZE:
        raise ValueError(f"hand must have exactly {HAND_SIZE} cards")
    flush = is_flush(hand)
    straight = is_straight(hand)
    if straight and flush:
        if {card.rank for card in hand} == ROYAL_RANKS:
            return HandCategory.ROYAL_STRAIGHT_FLUSH
        return HandCategory.STRAIGHT_FLUSH
    counts = tuple(sorted(Counter(card.rank for card in hand).values(), reverse=True))
    category = _COUNT_PATTERNS[counts]
    if category in (HandCategory.FOUR_OF_A_KIND, HandCategory.FULL_HOUSE):
        return category
    if flush:
        return HandCategory.FLUSH
    if straight:
        return HandCategory.STRAIGHT
    return category


def _suit_power(suit):
    """マークの強さ。SUITS の先頭（spade）が最も大きい。"""
    return len(SUITS) - SUITS.index(suit)


def _comparison_ranks(hand, category):
    """役ごとの比較順に並べた数字。組は枚数の多い順、同じ枚数なら大きい数字が先。"""
    counts = Counter(card.rank for card in hand)
    ranks = sorted(counts, key=lambda rank: (counts[rank], rank), reverse=True)
    if category in (HandCategory.STRAIGHT, HandCategory.STRAIGHT_FLUSH):
        # 最も強い数字だけで比べる。A-2-3-4-5 は A を 1 として扱うので 5
        return [5 if set(ranks) == ACE_LOW_RANKS else ranks[0]]
    return ranks


def hand_strength(hand):
    """5 枚の手札の強さ (category, rank_key, suit_key) を返す。大きいほど強い。

    rank_key は役を構成する数字を役ごとの比較順に並べたもの（ロイヤルは空）。
    suit_key は rank_key と同じ順に並べた各数字のマークの強さ（組は最も強いマーク）。
    5 枚でなければ ValueError。手札は変更しない。
    """
    category = evaluate_hand(hand)
    ranks = _comparison_ranks(hand, category)
    suit_key = tuple(
        max(_suit_power(card.suit) for card in hand if card.rank == rank)
        for rank in ranks
    )
    # ロイヤルは全員が同じ数字なので、数字は比べずマークだけで比べる
    rank_key = () if category == HandCategory.ROYAL_STRAIGHT_FLUSH else tuple(ranks)
    return (category, rank_key, suit_key)


def find_winner(hands):
    """手札のリストから、最も強い手札の位置（0 始まり）を返す。空なら ValueError。"""
    if not hands:
        raise ValueError("hands must not be empty")
    strengths = [hand_strength(hand) for hand in hands]
    return strengths.index(max(strengths))


def winner_index(players):
    """4 人の手札を比べ、勝者の位置（0 始まり）を返す。"""
    return find_winner([player.hand for player in players])


def human_result(players):
    """4 人の手札を比べ、人間が勝者なら "win"、そうでなければ "lose" を返す。"""
    winner = players[winner_index(players)]
    return "win" if winner.kind == "human" else "lose"
