"""役の判定（src/hands.py）のテスト。"""

import unittest

from src.cards import PLAYER_KINDS, Card, Player, Table
from src.hands import (
    HandCategory,
    evaluate_hand,
    find_winner,
    hand_strength,
    human_result,
    winner_index,
)


def make_hand(*specs):
    """(数字, マークの頭文字 s/h/d/c) の並びから手札を作る。"""
    suits = {"s": "spade", "h": "heart", "d": "diamond", "c": "club"}
    return [Card(rank, suits[suit]) for rank, suit in specs]


class TestEvaluateHand(unittest.TestCase):
    """evaluate_hand が 5 枚の手札から役の種類を返すこと。"""

    def test_four_of_a_kind(self):
        # 9 が 4 枚 + K（数字の枚数 [4, 1]）
        hand = make_hand((9, "s"), (9, "h"), (9, "d"), (9, "c"), (13, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.FOUR_OF_A_KIND)

    def test_full_house(self):
        # 8 が 3 枚 + 4 が 2 枚（[3, 2]）
        hand = make_hand((8, "s"), (8, "h"), (8, "d"), (4, "c"), (4, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.FULL_HOUSE)

    def test_three_of_a_kind(self):
        # 7 が 3 枚 + 2 + J（[3, 1, 1]）
        hand = make_hand((7, "s"), (7, "h"), (7, "d"), (2, "c"), (11, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.THREE_OF_A_KIND)

    def test_two_pair(self):
        # 5 が 2 枚 + Q が 2 枚 + 9（[2, 2, 1]）
        hand = make_hand((5, "s"), (5, "h"), (12, "d"), (12, "c"), (9, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.TWO_PAIR)

    def test_one_pair(self):
        # 10 が 2 枚 + 3 + 6 + K（[2, 1, 1, 1]）
        hand = make_hand((10, "s"), (10, "h"), (3, "d"), (6, "c"), (13, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.ONE_PAIR)

    def test_high_card(self):
        # 数字がばらばらで連続せず、マークも揃わない
        hand = make_hand((2, "s"), (5, "h"), (7, "d"), (9, "c"), (13, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.HIGH_CARD)

    def test_flush(self):
        # 同じマーク（heart）で、数字は連続しない
        hand = make_hand((2, "h"), (5, "h"), (7, "h"), (9, "h"), (13, "h"))
        self.assertEqual(evaluate_hand(hand), HandCategory.FLUSH)

    def test_straight(self):
        # 5-6-7-8-9 でマークはばらばら
        hand = make_hand((5, "s"), (6, "h"), (7, "d"), (8, "c"), (9, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.STRAIGHT)

    def test_straight_flush(self):
        # 5-6-7-8-9 で全部 diamond
        hand = make_hand((5, "d"), (6, "d"), (7, "d"), (8, "d"), (9, "d"))
        self.assertEqual(evaluate_hand(hand), HandCategory.STRAIGHT_FLUSH)

    def test_royal_straight_flush(self):
        # 10-J-Q-K-A で全部 spade
        hand = make_hand((10, "s"), (11, "s"), (12, "s"), (13, "s"), (14, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.ROYAL_STRAIGHT_FLUSH)

    def test_ace_low_straight(self):
        # A-2-3-4-5 は A=1 のストレート（マークはばらばら）
        hand = make_hand((14, "s"), (2, "h"), (3, "d"), (4, "c"), (5, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.STRAIGHT)

    def test_ace_low_straight_flush_is_not_royal(self):
        # A-2-3-4-5 で全部 club は、ロイヤルではなくストレートフラッシュ
        hand = make_hand((14, "c"), (2, "c"), (3, "c"), (4, "c"), (5, "c"))
        self.assertEqual(evaluate_hand(hand), HandCategory.STRAIGHT_FLUSH)

    def test_ace_high_straight_with_mixed_suits_is_straight(self):
        # 10-J-Q-K-A でマークがばらばらなら、ロイヤルではなくストレート
        hand = make_hand((10, "s"), (11, "h"), (12, "d"), (13, "c"), (14, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.STRAIGHT)

    def test_wraparound_is_not_straight(self):
        # Q-K-A-2-3 は K から A を越えて 2 に戻るので連続とみなさない
        hand = make_hand((12, "s"), (13, "h"), (14, "d"), (2, "c"), (3, "s"))
        self.assertEqual(evaluate_hand(hand), HandCategory.HIGH_CARD)

    def test_wrong_size_raises_value_error(self):
        # 4 枚と 6 枚は判定せず ValueError
        four = make_hand((2, "s"), (3, "s"), (4, "s"), (5, "s"))
        six = make_hand((2, "s"), (3, "s"), (4, "s"), (5, "s"), (6, "s"), (7, "s"))
        for hand in (four, six, []):
            with self.assertRaises(ValueError):
                evaluate_hand(hand)

    def test_is_pure_and_does_not_modify_hand(self):
        # 同じ入力で同じ結果になり、手札の内容と順番は変わらない
        hand = make_hand((14, "s"), (5, "h"), (3, "d"), (4, "c"), (2, "s"))
        before = list(hand)
        first = evaluate_hand(hand)
        second = evaluate_hand(hand)
        self.assertEqual(first, second)
        self.assertEqual(hand, before)


class StrengthTestCase(unittest.TestCase):
    """強さの比較テストの共通の検証。"""

    def assert_stronger(self, stronger, weaker):
        """stronger の手札が weaker の手札より強い（逆は成り立たない）。"""
        self.assertGreater(hand_strength(stronger), hand_strength(weaker))
        self.assertLess(hand_strength(weaker), hand_strength(stronger))


class TestHandStrengthRank(StrengthTestCase):
    """hand_strength が役の種類と数字で大小を比べられる値を返すこと（大きいほど強い）。"""

    def test_stronger_category_wins(self):
        # フラッシュ（6）> ストレート（5）。数字はストレートの方が大きくても役が優先
        flush = make_hand((2, "h"), (5, "h"), (7, "h"), (9, "h"), (11, "h"))
        straight = make_hand((10, "s"), (11, "h"), (12, "d"), (13, "c"), (14, "s"))
        self.assert_stronger(flush, straight)

    def test_straight_flush_compares_highest_rank(self):
        # 5-9（最も強い数字 9）< 6-10（最も強い数字 10）。どちらも diamond
        low = make_hand((5, "d"), (6, "d"), (7, "d"), (8, "d"), (9, "d"))
        high = make_hand((6, "d"), (7, "d"), (8, "d"), (9, "d"), (10, "d"))
        self.assert_stronger(high, low)

    def test_four_of_a_kind_compares_quad_then_kicker(self):
        # 4 枚組の数字が先: 10x4 + 2 > 9x4 + A
        quad_ten = make_hand((10, "s"), (10, "h"), (10, "d"), (10, "c"), (2, "s"))
        quad_nine = make_hand((9, "s"), (9, "h"), (9, "d"), (9, "c"), (14, "s"))
        self.assert_stronger(quad_ten, quad_nine)
        # 4 枚組が同じなら残り 1 枚: 9x4 + K > 9x4 + Q
        kicker_k = make_hand((9, "s"), (9, "h"), (9, "d"), (9, "c"), (13, "s"))
        kicker_q = make_hand((9, "s"), (9, "h"), (9, "d"), (9, "c"), (12, "s"))
        self.assert_stronger(kicker_k, kicker_q)

    def test_full_house_compares_triple_then_pair(self):
        # 3 枚組が先: 8x3 + 2x2 > 7x3 + Ax2
        triple_eight = make_hand((8, "s"), (8, "h"), (8, "d"), (2, "c"), (2, "s"))
        triple_seven = make_hand((7, "s"), (7, "h"), (7, "d"), (14, "c"), (14, "s"))
        self.assert_stronger(triple_eight, triple_seven)
        # 3 枚組が同じなら 2 枚組: 8x3 + 4x2 > 8x3 + 3x2
        pair_four = make_hand((8, "s"), (8, "h"), (8, "d"), (4, "c"), (4, "s"))
        pair_three = make_hand((8, "s"), (8, "h"), (8, "d"), (3, "c"), (3, "s"))
        self.assert_stronger(pair_four, pair_three)

    def test_flush_compares_ranks_in_descending_order(self):
        # 最も大きい数字が先: A-high > K-high（2 枚目以降は K-high の方が大きくても無関係）
        ace_high = make_hand((14, "h"), (2, "h"), (3, "h"), (4, "h"), (7, "h"))
        king_high = make_hand((13, "h"), (12, "h"), (11, "h"), (9, "h"), (8, "h"))
        self.assert_stronger(ace_high, king_high)
        # 最大が同じなら次に大きい数字: K-Q-... > K-J-...
        second_q = make_hand((13, "h"), (12, "h"), (3, "h"), (4, "h"), (7, "h"))
        second_j = make_hand((13, "h"), (11, "h"), (10, "h"), (9, "h"), (7, "h"))
        self.assert_stronger(second_q, second_j)

    def test_straight_compares_highest_rank(self):
        # 6-10（最も強い数字 10）> 5-9（9）
        high = make_hand((6, "s"), (7, "h"), (8, "d"), (9, "c"), (10, "s"))
        low = make_hand((5, "s"), (6, "h"), (7, "d"), (8, "c"), (9, "s"))
        self.assert_stronger(high, low)

    def test_three_of_a_kind_compares_triple_then_kickers(self):
        # 3 枚組が先: 9x3 + 2 + 3 > 8x3 + A + K
        triple_nine = make_hand((9, "s"), (9, "h"), (9, "d"), (2, "c"), (3, "s"))
        triple_eight = make_hand((8, "s"), (8, "h"), (8, "d"), (14, "c"), (13, "s"))
        self.assert_stronger(triple_nine, triple_eight)
        # 3 枚組が同じなら残り 2 枚を大きい順: 9x3 + K + 2 > 9x3 + Q + J
        kicker_k = make_hand((9, "s"), (9, "h"), (9, "d"), (13, "c"), (2, "s"))
        kicker_q = make_hand((9, "s"), (9, "h"), (9, "d"), (12, "c"), (11, "s"))
        self.assert_stronger(kicker_k, kicker_q)

    def test_two_pair_compares_high_pair_low_pair_then_kicker(self):
        # 大きいペアが先: Kx2 + 2x2 > Qx2 + Jx2
        high_pair = make_hand((13, "s"), (13, "h"), (2, "d"), (2, "c"), (3, "s"))
        low_pairs = make_hand((12, "s"), (12, "h"), (11, "d"), (11, "c"), (14, "s"))
        self.assert_stronger(high_pair, low_pairs)
        # 大きいペアが同じなら小さいペア: Kx2 + 5x2 > Kx2 + 4x2
        small_five = make_hand((13, "s"), (13, "h"), (5, "d"), (5, "c"), (2, "s"))
        small_four = make_hand((13, "s"), (13, "h"), (4, "d"), (4, "c"), (14, "s"))
        self.assert_stronger(small_five, small_four)
        # ペアが両方同じなら残り 1 枚: Kx2 + 5x2 + 9 > Kx2 + 5x2 + 8
        kicker_nine = make_hand((13, "s"), (13, "h"), (5, "d"), (5, "c"), (9, "s"))
        kicker_eight = make_hand((13, "s"), (13, "h"), (5, "d"), (5, "c"), (8, "s"))
        self.assert_stronger(kicker_nine, kicker_eight)

    def test_one_pair_compares_pair_then_kickers_descending(self):
        # ペアが先: 6x2 + 2 + 3 + 4 > 5x2 + A + K + Q
        pair_six = make_hand((6, "s"), (6, "h"), (2, "d"), (3, "c"), (4, "s"))
        pair_five = make_hand((5, "s"), (5, "h"), (14, "d"), (13, "c"), (12, "s"))
        self.assert_stronger(pair_six, pair_five)
        # ペアが同じなら残り 3 枚を大きい順: 6x2 + A + 3 + 2 > 6x2 + K + Q + J
        kicker_a = make_hand((6, "s"), (6, "h"), (14, "d"), (3, "c"), (2, "s"))
        kicker_k = make_hand((6, "s"), (6, "h"), (13, "d"), (12, "c"), (11, "s"))
        self.assert_stronger(kicker_a, kicker_k)

    def test_high_card_compares_ranks_in_descending_order(self):
        # 最も大きい数字が先: A-... > K-...
        ace_high = make_hand((14, "s"), (2, "h"), (3, "d"), (4, "c"), (7, "s"))
        king_high = make_hand((13, "s"), (11, "h"), (9, "d"), (8, "c"), (6, "s"))
        self.assert_stronger(ace_high, king_high)
        # 最大が同じなら次: K-9-... > K-8-...
        second_nine = make_hand((13, "s"), (9, "h"), (5, "d"), (3, "c"), (2, "s"))
        second_eight = make_hand((13, "s"), (8, "h"), (7, "d"), (6, "c"), (4, "s"))
        self.assert_stronger(second_nine, second_eight)


class TestHandStrengthSuit(StrengthTestCase):
    """数字が同じ手札をマークで比べること、ロイヤル、同じ入力で同じ結果になること。"""

    def test_same_ranks_are_compared_by_suit(self):
        # 数字がすべて同じ（2, 5, 7, 9, K）で、最も大きい K のマーク: spade > heart
        spade_king = make_hand((2, "h"), (5, "h"), (7, "d"), (9, "c"), (13, "s"))
        heart_king = make_hand((2, "s"), (5, "s"), (7, "s"), (9, "s"), (13, "h"))
        self.assert_stronger(spade_king, heart_king)
        # マークの強さ: heart > diamond > club（同じ位置のカードだけが違う）
        diamond_king = make_hand((2, "h"), (5, "h"), (7, "d"), (9, "c"), (13, "d"))
        club_king = make_hand((2, "h"), (5, "h"), (7, "d"), (9, "c"), (13, "c"))
        self.assert_stronger(heart_king, diamond_king)
        self.assert_stronger(diamond_king, club_king)

    def test_suit_is_compared_in_rank_order_not_by_best_suit(self):
        # K のマークが先に比べられる: K=heart の手札は、他のカードが spade でも K=diamond に勝つ
        king_heart = make_hand((2, "c"), (5, "c"), (7, "c"), (9, "d"), (13, "h"))
        king_diamond = make_hand((2, "s"), (5, "s"), (7, "s"), (9, "s"), (13, "d"))
        self.assert_stronger(king_heart, king_diamond)

    def test_pair_suit_uses_strongest_suit_of_the_pair(self):
        # 5 のペア（残りは同じ A, 9, 2 で同じマーク）: 組のうち最も強いマークで比べる
        # heart+club（最も強いのは heart）> diamond+club（diamond）
        pair_heart = make_hand((5, "h"), (5, "c"), (14, "s"), (9, "s"), (2, "s"))
        pair_diamond = make_hand((5, "d"), (5, "c"), (14, "s"), (9, "s"), (2, "s"))
        self.assert_stronger(pair_heart, pair_diamond)

    def test_straight_suit_uses_highest_card(self):
        # 5-9 のストレート。最も強い数字 9 のマークで比べる（他のカードは無関係）
        nine_spade = make_hand((5, "c"), (6, "c"), (7, "c"), (8, "c"), (9, "s"))
        nine_heart = make_hand((5, "s"), (6, "s"), (7, "s"), (8, "s"), (9, "h"))
        self.assert_stronger(nine_spade, nine_heart)

    def test_straight_flush_suit_breaks_tie(self):
        # 5-9 のストレートフラッシュ: spade > club
        spade = make_hand((5, "s"), (6, "s"), (7, "s"), (8, "s"), (9, "s"))
        club = make_hand((5, "c"), (6, "c"), (7, "c"), (8, "c"), (9, "c"))
        self.assert_stronger(spade, club)

    def test_ace_low_straight_is_the_weakest_straight(self):
        # A-2-3-4-5 の最も強い数字は 5 なので、2-3-4-5-6（6）より弱い
        ace_low = make_hand((14, "s"), (2, "s"), (3, "h"), (4, "h"), (5, "s"))
        two_to_six = make_hand((2, "c"), (3, "d"), (4, "c"), (5, "c"), (6, "c"))
        self.assert_stronger(two_to_six, ace_low)

    def test_ace_low_straight_flush_is_weaker_than_two_to_six(self):
        # A-2-3-4-5 のストレートフラッシュ（spade）< 2-3-4-5-6 のストレートフラッシュ（club）
        ace_low = make_hand((14, "s"), (2, "s"), (3, "s"), (4, "s"), (5, "s"))
        two_to_six = make_hand((2, "c"), (3, "c"), (4, "c"), (5, "c"), (6, "c"))
        self.assert_stronger(two_to_six, ace_low)

    def test_royal_straight_flush_is_compared_by_suit_only(self):
        # ロイヤルどうしは数字が同じなので、マークだけで比べる: spade > heart > diamond > club
        royals = [
            make_hand(*[(rank, suit) for rank in range(10, 15)])
            for suit in ("s", "h", "d", "c")
        ]
        for stronger, weaker in zip(royals, royals[1:]):
            self.assert_stronger(stronger, weaker)

    def test_royal_beats_straight_flush(self):
        # ロイヤル（club）> ストレートフラッシュ（9-K の spade）。役の種類が先
        royal = make_hand(*[(rank, "c") for rank in range(10, 15)])
        straight_flush = make_hand(*[(rank, "s") for rank in range(9, 14)])
        self.assert_stronger(royal, straight_flush)

    def test_strength_is_pure_and_does_not_modify_hand(self):
        # 同じ入力で同じ結果になり、手札の内容と順番は変わらない
        hand = make_hand((14, "s"), (5, "h"), (3, "d"), (4, "c"), (2, "s"))
        before = list(hand)
        self.assertEqual(hand_strength(hand), hand_strength(hand))
        self.assertEqual(hand, before)

    def test_strength_ignores_card_order(self):
        # 並びが違っても同じ手札なら同じ強さ
        hand = make_hand((9, "s"), (9, "h"), (5, "d"), (5, "c"), (13, "s"))
        shuffled = [hand[4], hand[2], hand[0], hand[3], hand[1]]
        self.assertEqual(hand_strength(hand), hand_strength(shuffled))

    def test_no_ties_between_different_hands_of_one_deal(self):
        # 同じ山から配った 4 人の手札（カードはすべて異なる）の強さは、すべて異なる
        for seed in range(200):
            table = Table.deal(seed)
            strengths = [hand_strength(p.hand) for p in table.players]
            self.assertEqual(len(set(strengths)), len(strengths), f"seed={seed}")


class TestFindWinner(unittest.TestCase):
    """find_winner が最も強い手札の位置を返すこと。"""

    def test_returns_index_of_strongest_hand(self):
        # 位置 2 のフルハウスが最強（0: ワンペア、1: ストレート、3: フラッシュ）
        hands = [
            make_hand((6, "s"), (6, "h"), (2, "d"), (3, "c"), (4, "s")),
            make_hand((5, "s"), (6, "h"), (7, "d"), (8, "c"), (9, "s")),
            make_hand((8, "s"), (8, "h"), (8, "d"), (4, "c"), (4, "s")),
            make_hand((2, "h"), (5, "h"), (7, "h"), (9, "h"), (13, "h")),
        ]
        self.assertEqual(find_winner(hands), 2)

    def test_winner_decided_by_suit_when_ranks_equal(self):
        # 数字がすべて同じ 2 手札: K が spade の手札（位置 1）が勝つ
        hands = [
            make_hand((2, "s"), (5, "s"), (7, "s"), (9, "s"), (13, "h")),
            make_hand((2, "h"), (5, "h"), (7, "d"), (9, "c"), (13, "s")),
        ]
        self.assertEqual(find_winner(hands), 1)

    def test_single_hand_wins(self):
        hand = make_hand((2, "s"), (5, "h"), (7, "d"), (9, "c"), (13, "s"))
        self.assertEqual(find_winner([hand]), 0)

    def test_empty_raises_value_error(self):
        with self.assertRaises(ValueError):
            find_winner([])

    def test_does_not_modify_hands(self):
        # 渡したリストと各手札は変わらず、同じ入力で同じ結果になる
        hands = [
            make_hand((6, "s"), (6, "h"), (2, "d"), (3, "c"), (4, "s")),
            make_hand((14, "s"), (5, "h"), (3, "d"), (4, "c"), (2, "s")),
        ]
        before = [list(hand) for hand in hands]
        first = find_winner(hands)
        second = find_winner(hands)
        self.assertEqual(first, second)
        self.assertEqual(hands, before)


def make_players(*hands):
    """手札のリストから、PLAYER_KINDS の順（com, com, com, human）のプレイヤーを作る。"""
    players = [Player(kind) for kind in PLAYER_KINDS]
    for player, hand in zip(players, hands):
        player.hand = hand
    return players


class TestHumanResult(unittest.TestCase):
    """human_result が、人間が勝者なら "win"、そうでなければ "lose" を返すこと。"""

    # 5 枚の手札（強い順: フルハウス > フラッシュ > ストレート > ワンペア）
    FULL_HOUSE = [(8, "s"), (8, "h"), (8, "d"), (4, "c"), (4, "s")]
    FLUSH = [(2, "h"), (5, "h"), (7, "h"), (9, "h"), (13, "h")]
    STRAIGHT = [(5, "s"), (6, "h"), (7, "d"), (8, "c"), (9, "s")]
    ONE_PAIR = [(6, "s"), (6, "h"), (2, "d"), (3, "c"), (4, "s")]

    def test_human_strongest_is_win(self):
        # 人間（4 人目）のフルハウスが最強
        players = make_players(
            make_hand(*self.ONE_PAIR),
            make_hand(*self.STRAIGHT),
            make_hand(*self.FLUSH),
            make_hand(*self.FULL_HOUSE),
        )
        self.assertEqual(human_result(players), "win")

    def test_com_strongest_is_lose(self):
        # COM（2 人目）のフルハウスが最強で、人間はストレート
        players = make_players(
            make_hand(*self.ONE_PAIR),
            make_hand(*self.FULL_HOUSE),
            make_hand(*self.FLUSH),
            make_hand(*self.STRAIGHT),
        )
        self.assertEqual(human_result(players), "lose")


class TestWinnerIndex(unittest.TestCase):
    """winner_index が、最も強い手札のプレイヤーの位置（0 始まり）を返すこと。"""

    FULL_HOUSE = TestHumanResult.FULL_HOUSE
    FLUSH = TestHumanResult.FLUSH
    STRAIGHT = TestHumanResult.STRAIGHT
    ONE_PAIR = TestHumanResult.ONE_PAIR

    def test_returns_position_of_the_strongest_hand(self):
        # 位置 i の手札だけがフルハウスで最強のとき、winner_index は i
        weaker = [self.ONE_PAIR, self.STRAIGHT, self.FLUSH]
        for index in range(len(PLAYER_KINDS)):
            with self.subTest(winner=index):
                hands = list(weaker)
                hands.insert(index, self.FULL_HOUSE)
                players = make_players(*(make_hand(*hand) for hand in hands))
                self.assertEqual(winner_index(players), index)

    def test_human_result_agrees_with_winner_index(self):
        # 勝者が人間（最後の位置）のときだけ "win"
        players = make_players(
            make_hand(*self.FULL_HOUSE),
            make_hand(*self.ONE_PAIR),
            make_hand(*self.STRAIGHT),
            make_hand(*self.FLUSH),
        )
        self.assertEqual(winner_index(players), 0)
        self.assertEqual(human_result(players), "lose")


if __name__ == "__main__":
    unittest.main()
