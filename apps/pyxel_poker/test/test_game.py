"""ゲームの段階の遷移（src/game.py）のテスト。"""

import unittest

from src.cards import HAND_SIZE, INITIAL_COINS, PLAYER_KINDS, Card
from src.game import Action, Game, Phase, com_decision, com_exchange_indices
from src.hands import HandCategory, evaluate_hand
from src.pot import ENTRY_FEE, raise_cost

PLAYER_COUNT = len(PLAYER_KINDS)  # 4
HUMAN = PLAYER_COUNT - 1  # 人間は最後（3）


class TestStart(unittest.TestCase):
    """FR1.1、FR1.3: 開始時の参加費・配札・段階。"""

    def test_everyone_pays_entry_fee_into_pot(self):
        game = Game.start(seed=0)
        # ポット = 参加費 1 × 4 人 = 4
        self.assertEqual(game.pot.amount, ENTRY_FEE * PLAYER_COUNT)
        for player in game.table.players:
            self.assertEqual(player.coins, INITIAL_COINS - ENTRY_FEE)

    def test_hands_are_dealt_and_public(self):
        game = Game.start(seed=0)
        for player in game.table.players:
            self.assertEqual(len(player.hand), HAND_SIZE)
            self.assertTrue(player.hand_public)

    def test_starts_in_first_decision_with_everyone_active(self):
        game = Game.start(seed=0)
        self.assertEqual(game.phase, Phase.FIRST_DECISION)
        self.assertEqual(game.active, list(range(PLAYER_COUNT)))
        self.assertEqual(game.dropped, set())
        self.assertIsNone(game.winner)


def com_drops(*positions):
    """指定した位置の COM だけがドロップし、残りはレイズする選択の差し替え。"""
    return lambda index: "drop" if index in positions else "raise"


class TestFirstDecision(unittest.TestCase):
    """FR2.1〜FR2.3、FR2.5、FR2.6: 1 回目の判断。"""

    def test_human_raise_charges_everyone_and_goes_to_second(self):
        game = Game.start(seed=0)
        game.decide("raise")
        # COM は必ずレイズするので、全員が 1 回目の追加額を払う
        # 各自 = 参加費 1 + 1 回目の追加額 1 = 2、ポット = 2 × 4 = 8
        paid = ENTRY_FEE + raise_cost(1)
        self.assertEqual(game.pot.amount, paid * PLAYER_COUNT)
        for player in game.table.players:
            self.assertEqual(player.coins, INITIAL_COINS - paid)
        self.assertEqual(game.phase, Phase.SECOND_DECISION)
        self.assertEqual(game.active, list(range(PLAYER_COUNT)))
        self.assertEqual(game.dropped, set())

    def test_human_drop_pays_nothing_and_is_dropped(self):
        game = Game.start(seed=0)
        game.decide("drop")
        # 人間は追加で払わない: 参加費の分だけ減った所持コインのまま
        human = game.table.players[HUMAN]
        self.assertEqual(human.coins, INITIAL_COINS - ENTRY_FEE)
        self.assertEqual(game.dropped, {HUMAN})
        # 人間が外れても COM の 3 人は 2 回目まで同じ decide で進み、勝者が決まる（BR2.11）
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertIn(game.winner, range(HUMAN))

    def test_single_raiser_wins_whole_pot_without_second_round(self):
        game = Game.start(seed=0)
        game.com_action = com_drops(0, 1, 2)
        game.decide("raise")
        # ポット = 参加費 4 + 人間の追加額 1 = 5。レイズが 1 人なので 2 回目に進まない
        pot_total = ENTRY_FEE * PLAYER_COUNT + raise_cost(1)
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, HUMAN)
        self.assertEqual(game.pot.amount, 0)
        # 勝者の所持 = 初期 - 参加費 - 追加額 + ポット全額
        self.assertEqual(
            game.table.players[HUMAN].coins,
            INITIAL_COINS - ENTRY_FEE - raise_cost(1) + pot_total,
        )

    def test_no_raiser_means_no_winner_and_pot_stays(self):
        game = Game.start(seed=0)
        game.com_action = com_drops(0, 1, 2)
        game.decide("drop")
        # 全員ドロップ: 勝者なし、ポットは参加費 4 のまま残る
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertIsNone(game.winner)
        self.assertEqual(game.pot.amount, ENTRY_FEE * PLAYER_COUNT)
        self.assertEqual(game.dropped, set(range(PLAYER_COUNT)))
        # 勝者がいないので、誰も受け取っていない
        self.assertEqual(game.awarded, 0)
        for player in game.table.players:
            self.assertEqual(player.coins, INITIAL_COINS - ENTRY_FEE)


# 役の強さが明確に異なる手札（HIGH_CARD < ONE_PAIR < TWO_PAIR）。配札の乱数に頼らない
WEAK = [
    Card(2, "club"),
    Card(4, "diamond"),
    Card(6, "heart"),
    Card(8, "club"),
    Card(10, "diamond"),
]
PAIR = [
    Card(14, "spade"),
    Card(14, "heart"),
    Card(3, "club"),
    Card(7, "diamond"),
    Card(9, "heart"),
]
TWO_PAIR = [
    Card(13, "spade"),
    Card(13, "heart"),
    Card(5, "club"),
    Card(5, "diamond"),
    Card(9, "heart"),
]


def set_hands(game, strong):
    """全員の手札を弱い手札にし、strong（位置 -> 手札）の人だけ差し替える。"""
    for index, player in enumerate(game.table.players):
        player.hand = list(strong.get(index, WEAK))


# ワンペアより強い各役の手札（com_decision は役の区分だけで決める）
STRONGER_HANDS = {
    HandCategory.TWO_PAIR: TWO_PAIR,
    HandCategory.THREE_OF_A_KIND: [
        Card(9, "spade"),
        Card(9, "heart"),
        Card(9, "club"),
        Card(2, "diamond"),
        Card(5, "heart"),
    ],
    HandCategory.STRAIGHT: [
        Card(5, "club"),
        Card(6, "diamond"),
        Card(7, "heart"),
        Card(8, "spade"),
        Card(9, "club"),
    ],
    HandCategory.FLUSH: [
        Card(2, "heart"),
        Card(5, "heart"),
        Card(7, "heart"),
        Card(9, "heart"),
        Card(13, "heart"),
    ],
    HandCategory.FULL_HOUSE: [
        Card(3, "spade"),
        Card(3, "heart"),
        Card(3, "club"),
        Card(8, "diamond"),
        Card(8, "heart"),
    ],
    HandCategory.FOUR_OF_A_KIND: [
        Card(4, "spade"),
        Card(4, "heart"),
        Card(4, "club"),
        Card(4, "diamond"),
        Card(13, "heart"),
    ],
    HandCategory.STRAIGHT_FLUSH: [
        Card(5, "heart"),
        Card(6, "heart"),
        Card(7, "heart"),
        Card(8, "heart"),
        Card(9, "heart"),
    ],
    HandCategory.ROYAL_STRAIGHT_FLUSH: [
        Card(10, "spade"),
        Card(11, "spade"),
        Card(12, "spade"),
        Card(13, "spade"),
        Card(14, "spade"),
    ],
}


class TestComDecision(unittest.TestCase):
    """FR1.2、FR2.2、FR4.1: COM は手札の役の区分だけでレイズかドロップを決める（BR1.2、BR1.3、BR1.5）。"""

    def test_high_card_drops(self):
        self.assertEqual(evaluate_hand(WEAK), HandCategory.HIGH_CARD)
        self.assertEqual(com_decision(WEAK), Action.DROP)

    def test_one_pair_raises(self):
        # ワンペアがレイズの境目（しきい値）
        self.assertEqual(evaluate_hand(PAIR), HandCategory.ONE_PAIR)
        self.assertEqual(com_decision(PAIR), Action.RAISE)

    def test_every_category_above_one_pair_raises(self):
        for category, hand in STRONGER_HANDS.items():
            with self.subTest(category=category.name):
                self.assertEqual(evaluate_hand(hand), category)
                self.assertEqual(com_decision(hand), Action.RAISE)

    def test_same_hand_gives_same_decision(self):
        # 乱数を使わない: 何度呼んでも同じ結果
        for hand in (WEAK, PAIR):
            self.assertEqual(
                {com_decision(hand) for _ in range(20)}, {com_decision(hand)}
            )

    def test_decision_does_not_change_hand(self):
        hand = list(PAIR)
        com_decision(hand)
        self.assertEqual(hand, PAIR)


class TestComExchangeIndices(unittest.TestCase):
    """FR3.2〜FR3.4、FR4.1: 役の区分ごとの COM の交換する位置（BR2.2〜BR2.4、BR2.8）。"""

    def test_high_card_exchanges_all_five(self):
        self.assertEqual(com_exchange_indices(WEAK), list(range(HAND_SIZE)))

    def test_one_pair_exchanges_the_three_non_pair_cards(self):
        # PAIR = A が位置 0・1。ペア以外は 2・3・4
        self.assertEqual(com_exchange_indices(PAIR), [2, 3, 4])

    def test_two_pair_exchanges_the_odd_card(self):
        # TWO_PAIR = K が 0・1、5 が 2・3。余りは位置 4
        self.assertEqual(com_exchange_indices(TWO_PAIR), [4])

    def test_three_of_a_kind_exchanges_the_two_others(self):
        # 9 が位置 0〜2。ほかは 3・4
        hand = STRONGER_HANDS[HandCategory.THREE_OF_A_KIND]
        self.assertEqual(com_exchange_indices(hand), [3, 4])

    def test_four_of_a_kind_exchanges_the_one_other(self):
        # 4 が位置 0〜3。ほかは 4
        hand = STRONGER_HANDS[HandCategory.FOUR_OF_A_KIND]
        self.assertEqual(com_exchange_indices(hand), [4])

    def test_complete_hands_exchange_nothing(self):
        # ワンペアより強い役のうち、組を残して交換する 3 つ（ツーペア・スリーカード・フォーカード）以外
        partial = {
            HandCategory.TWO_PAIR,
            HandCategory.THREE_OF_A_KIND,
            HandCategory.FOUR_OF_A_KIND,
        }
        for category, hand in STRONGER_HANDS.items():
            if category in partial:
                continue
            with self.subTest(category=category):
                self.assertEqual(com_exchange_indices(hand), [])

    def test_indices_are_ascending_wherever_the_cards_sit(self):
        # ペア（9）が位置 1・3 に散らばる手札。ペア以外は 0・2・4 で昇順
        hand = [
            Card(2, "club"),
            Card(9, "spade"),
            Card(5, "heart"),
            Card(9, "heart"),
            Card(12, "diamond"),
        ]
        self.assertEqual(com_exchange_indices(hand), [0, 2, 4])

    def test_same_hand_gives_same_indices_and_hand_is_unchanged(self):
        hand = list(PAIR)
        first = com_exchange_indices(hand)
        self.assertEqual(com_exchange_indices(hand), first)
        self.assertEqual(hand, PAIR)


class TestComAction(unittest.TestCase):
    """FR1.1、FR1.3: Game.com_action は位置 index の COM 自身の手札で決める（BR1.1）。"""

    def test_each_com_decides_by_its_own_hand(self):
        game = Game.start(seed=0)
        set_hands(game, {0: PAIR, 2: TWO_PAIR})
        # 位置 0・2 は強い手札でレイズ、位置 1 は弱い手札でドロップ
        self.assertEqual(game.com_action(0), Action.RAISE)
        self.assertEqual(game.com_action(1), Action.DROP)
        self.assertEqual(game.com_action(2), Action.RAISE)

    def test_decision_follows_current_hand(self):
        game = Game.start(seed=0)
        set_hands(game, {0: WEAK})
        self.assertEqual(game.com_action(0), Action.DROP)
        game.table.players[0].hand = list(PAIR)
        self.assertEqual(game.com_action(0), Action.RAISE)

    def test_weak_coms_drop_in_decide(self):
        game = Game.start(seed=0)
        set_hands(game, {HUMAN: PAIR})
        game.decide("raise")
        # COM 3 人は弱い手札でドロップ。レイズは人間 1 人なので 2 回目に進まず人間が勝つ
        self.assertEqual(game.dropped, set(range(HUMAN)))
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, HUMAN)


class TestSecondDecision(unittest.TestCase):
    """FR3.1〜FR3.3、FR4.1、FR4.2: 2 回目の判断と勝敗決定。"""

    def test_everyone_raises_twice_and_best_hand_takes_pot(self):
        game = Game.start(seed=0)
        set_hands(game, {1: PAIR})
        game.com_action = com_drops()  # COM は全員レイズ
        game.decide("raise")
        self.assertEqual(game.phase, Phase.SECOND_DECISION)
        game.decide("raise")
        # 各自 = 参加費 1 + 1 回目 1 + 2 回目 2 = 4、ポット = 4 × 4 = 16
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        pot_total = paid * PLAYER_COUNT
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, 1)
        self.assertEqual(game.pot.amount, 0)
        # 勝者 = 初期 - 支払い + ポット全額 = 10 - 4 + 16、ほかは 10 - 4
        self.assertEqual(game.table.players[1].coins, INITIAL_COINS - paid + pot_total)
        for index in (0, 2, HUMAN):
            self.assertEqual(game.table.players[index].coins, INITIAL_COINS - paid)

    def test_awarded_is_the_pot_paid_out_to_the_winner(self):
        """勝者が受け取ったポットの額が awarded に残る（ポット自体は 0 に戻る）"""
        game = Game.start(seed=0)
        self.assertEqual(game.awarded, 0)
        game.decide("raise")
        game.decide("raise")
        # 4 人が参加費 1 + 1 回目 1 + 2 回目 2 = 4 ずつ払う → ポット = 4 * 4 = 16
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(game.awarded, paid * PLAYER_COUNT)
        self.assertEqual(game.pot.amount, 0)

    def test_awarded_includes_carried_over_pot(self):
        """持ち越しのポットがあるときの awarded は、持ち越し分を含む全額"""
        first = Game.start(seed=0)
        first.com_action = com_drops(0, 1, 2)
        first.decide("drop")  # 全員ドロップ: ポット 4 が持ち越し
        game = first.next_game(seed=1)
        game.com_action = com_drops()  # COM は全員レイズ
        game.decide("raise")
        game.decide("raise")
        # 持ち越し 4 + 次の参加費 4 + 1 回目 1 * 4 + 2 回目 2 * 4 = 4 + 16 = 20
        carried = ENTRY_FEE * PLAYER_COUNT
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(game.awarded, carried + paid * PLAYER_COUNT)

    def test_second_round_deciders_are_first_round_raisers_only(self):
        game = Game.start(seed=0)
        game.com_action = com_drops(0)
        game.decide("raise")
        # 1 回目に COM 0 がドロップ: 2 回目の決める人は 1・2・人間
        self.assertEqual(game.phase, Phase.SECOND_DECISION)
        self.assertEqual(game.active, [1, 2, HUMAN])
        self.assertEqual(game.dropped, {0})
        self.assertTrue(game.human_decides())

    def test_dropped_player_never_wins_even_with_best_hand(self):
        game = Game.start(seed=0)
        # 位置 0 が最強だが 1 回目にドロップ、人間は次に強いが 2 回目にドロップ
        # COM 1・2 は同じ強さの完成した役（交換で引かない）にして、山札の並びに頼らない
        flush = STRONGER_HANDS[HandCategory.FLUSH]
        set_hands(game, {0: TWO_PAIR, 1: flush, 2: flush, HUMAN: PAIR})
        game.com_action = com_drops(0)
        game.decide("raise")
        game.decide("drop")
        # 残ったレイズは COM 1・2（同じ強さの手札）。同じ強さなら先の位置が勝つ
        self.assertEqual(game.dropped, {0, HUMAN})
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, 1)
        # ポット = 参加費 4 + 1 回目 1 × 3 + 2 回目 2 × 2 = 11。ドロップ者は追加で払わない
        pot_total = ENTRY_FEE * PLAYER_COUNT + raise_cost(1) * 3 + raise_cost(2) * 2
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(game.table.players[1].coins, INITIAL_COINS - paid + pot_total)
        self.assertEqual(
            game.table.players[HUMAN].coins, INITIAL_COINS - ENTRY_FEE - raise_cost(1)
        )

    def test_winner_index_maps_back_to_player_position(self):
        game = Game.start(seed=0)
        # 位置 0 が 1 回目にドロップ。レイズ組は [1, 2, 人間] で、人間が最強
        # find_winner が返すのはこのリスト内の位置 2 だが、プレイヤーの位置 3 に直る
        set_hands(game, {HUMAN: PAIR})
        game.com_action = com_drops(0)
        game.decide("raise")
        game.decide("raise")
        self.assertEqual(game.winner, HUMAN)

    def test_human_drop_in_first_round_finishes_in_same_decide(self):
        game = Game.start(seed=0)
        set_hands(game, {2: PAIR})
        game.com_action = com_drops()  # COM は全員レイズ
        game.decide("drop")
        # 人間は選択を待たれず、COM 3 人の 2 回目まで進む
        # ポット = 参加費 4 + 1 回目 1 × 3 + 2 回目 2 × 3 = 13
        pot_total = ENTRY_FEE * PLAYER_COUNT + (raise_cost(1) + raise_cost(2)) * 3
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, 2)
        self.assertEqual(game.table.players[2].coins, INITIAL_COINS - paid + pot_total)

    def test_second_round_decides_without_human_when_human_is_out(self):
        game = Game.start(seed=0)
        game.decide("raise")
        # 人間が決める人でない 2 回目の状況を作る（人間を外す）
        game.active = [0, 1, 2]
        game.dropped = {HUMAN}
        self.assertFalse(game.human_decides())
        game.decide()
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertIn(game.winner, range(HUMAN))

    def test_second_round_single_raiser_wins(self):
        game = Game.start(seed=0)
        game.decide("raise")
        game.com_action = com_drops(0, 1, 2)
        game.decide("raise")
        # ポット = (参加費 1 + 1 回目 1) × 4 + 人間の 2 回目 2 = 10。人間だけがレイズ
        pot_total = (ENTRY_FEE + raise_cost(1)) * PLAYER_COUNT + raise_cost(2)
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(game.winner, HUMAN)
        self.assertEqual(
            game.table.players[HUMAN].coins, INITIAL_COINS - paid + pot_total
        )

    def test_second_round_no_raiser_leaves_pot(self):
        game = Game.start(seed=0)
        game.decide("raise")
        game.com_action = com_drops(0, 1, 2)
        game.decide("drop")
        # 2 回目は全員ドロップ: 勝者なし、ポットは 1 回目までの (1 + 1) × 4 = 8 が残る
        self.assertIsNone(game.winner)
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.pot.amount, (ENTRY_FEE + raise_cost(1)) * PLAYER_COUNT)

    def test_choices_are_applied_simultaneously(self):
        game = Game.start(seed=0)
        # 人間の選択に関係なく COM の選択は同じ: 先に選んだ人の結果が後の人に影響しない
        game.com_action = lambda index: "raise" if game.pot.amount == 4 else "drop"
        game.decide("raise")
        # 支払いの反映前に全員の選択を集めるので、COM は全員レイズになる
        self.assertEqual(game.active, list(range(PLAYER_COUNT)))


class TestComExchange(unittest.TestCase):
    """FR3.1、FR3.5、FR2.1: 1 回目にレイズした COM の、2 回目の前の交換（BR2.1、BR2.5〜BR2.7）。"""

    def setUp(self):
        self.game = Game.start(seed=0)
        self.game.com_action = com_drops()  # COM は全員レイズ（配札の偶然に頼らない）
        self.deck_before = list(self.game.table.deck.cards)

    def test_raised_coms_draw_from_deck_head_in_ascending_position(self):
        game = self.game
        set_hands(game, {0: PAIR, 2: TWO_PAIR})  # 位置 1 は WEAK
        game.decide("raise")
        players = game.table.players
        # 位置 0（PAIR）は [2, 3, 4] の 3 枚、位置 1（WEAK）は 5 枚、位置 2（TWO_PAIR）は [4] の 1 枚
        # 山札の先頭から、位置の昇順に 3 + 5 + 1 = 9 枚を引く
        drawn = self.deck_before
        self.assertEqual(players[0].hand, PAIR[:2] + drawn[0:3])
        self.assertEqual(players[1].hand, drawn[3:8])
        self.assertEqual(players[2].hand, TWO_PAIR[:4] + drawn[8:9])
        self.assertEqual(game.table.deck.cards, drawn[9:])
        self.assertEqual(game.phase, Phase.SECOND_DECISION)

    def test_exchange_hides_com_hand_without_new_indices(self):
        game = self.game
        game.decide("raise")
        for player in game.table.players[:HUMAN]:
            self.assertEqual(len(player.hand), HAND_SIZE)
            self.assertTrue(player.exchanged)
            # new_indices は更新しない。交換した COM の手札は伏せる（hand_public が False）
            self.assertEqual(player.new_indices, set())
            self.assertFalse(player.hand_public)
        # 人間の手札は常に表（Game は変えない）
        self.assertTrue(game.table.players[HUMAN].hand_public)

    def test_com_that_did_not_exchange_stays_public(self):
        game = self.game
        game.com_action = com_drops(0)
        game.decide("raise")
        players = game.table.players
        self.assertTrue(players[0].hand_public)
        self.assertFalse(players[0].exchanged)
        for player in players[1:HUMAN]:
            self.assertFalse(player.hand_public)

    def test_complete_hand_is_marked_exchanged_without_drawing(self):
        game = self.game
        set_hands(game, {0: STRONGER_HANDS[HandCategory.FLUSH]})
        game.decide("raise")
        player = game.table.players[0]
        self.assertEqual(player.hand, STRONGER_HANDS[HandCategory.FLUSH])
        self.assertTrue(player.exchanged)
        # 位置 0 は引かない。位置 1・2 の WEAK が 5 + 5 枚
        self.assertEqual(game.table.deck.cards, self.deck_before[10:])

    def test_dropped_com_and_human_are_not_exchanged(self):
        game = self.game
        game.com_action = com_drops(0)
        set_hands(game, {})
        human_hand = list(game.table.players[HUMAN].hand)
        game.decide("raise")
        players = game.table.players
        self.assertEqual(players[0].hand, WEAK)
        self.assertFalse(players[0].exchanged)
        # 人間の交換は Game では行わない（Table.exchange の役目）
        self.assertEqual(players[HUMAN].hand, human_hand)
        self.assertFalse(players[HUMAN].exchanged)
        # 交換したのは位置 1・2 の WEAK が 5 + 5 枚
        self.assertEqual(game.table.deck.cards, self.deck_before[10:])

    def test_single_raiser_means_no_exchange(self):
        game = self.game
        game.com_action = com_drops(0, 1, 2)
        game.decide("raise")
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.table.deck.cards, self.deck_before)
        for player in game.table.players[:HUMAN]:
            self.assertFalse(player.exchanged)

    def test_second_round_decision_uses_exchanged_hand(self):
        game = self.game
        # 位置 0 は WEAK（交換前の既定の選択ならドロップ）。山札の先頭 5 枚をロイヤルにして引かせる
        game.table.deck.cards[:5] = ROYAL
        set_hands(game, {})
        game.decide("raise")
        del game.com_action  # 既定の選択（その COM の今の手札で決める）に戻す
        self.assertEqual(game.table.players[0].hand, ROYAL)
        self.assertEqual(game.com_action(0), Action.RAISE)

    def test_flow_first_exchange_second_and_winner(self):
        game = self.game
        game.com_action = com_drops(1, 2)
        game.table.deck.cards[:5] = ROYAL
        set_hands(game, {HUMAN: PAIR})
        game.decide("raise")
        # 位置 0 だけが交換する COM。ロイヤルを引いて 2 回目へ
        self.assertEqual(game.phase, Phase.SECOND_DECISION)
        self.assertEqual(game.active, [0, HUMAN])
        game.decide("raise")
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.pot.amount, 0)


# 山札の先頭に積んで COM に引かせる、役が最も強い手札
ROYAL = STRONGER_HANDS[HandCategory.ROYAL_STRAIGHT_FLUSH]


class TestComHandVisibility(unittest.TestCase):
    """COM の手札の公開: 交換で伏せ、勝敗決定（2 回目の後）に残った COM だけ公開する。"""

    def setUp(self):
        self.game = Game.start(seed=0)
        set_hands(self.game, {})
        # COM の選択を乱数や手札に任せず、全員レイズに固定する
        self.game.com_action = com_drops()

    def publics(self):
        return [p.hand_public for p in self.game.table.players]

    def test_showdown_reveals_only_round_two_raisers(self):
        game = self.game
        game.decide("raise")
        # 2 回目に COM 0 だけドロップ。残る COM 1・2 と人間がレイズ
        game.com_action = com_drops(0)
        game.decide("raise")
        self.assertEqual(game.phase, Phase.FINISHED)
        # COM 0 は伏せたまま（段は dropped で非表示）、COM 1・2 は公開、人間は常に公開
        self.assertEqual(self.publics(), [False, True, True, True])

    def test_showdown_reveals_all_when_everyone_raises(self):
        game = self.game
        game.decide("raise")
        game.decide("raise")
        self.assertEqual(self.publics(), [True] * PLAYER_COUNT)

    def test_hands_stay_hidden_during_second_decision(self):
        game = self.game
        game.decide("raise")
        self.assertEqual(game.phase, Phase.SECOND_DECISION)
        self.assertEqual(self.publics(), [False, False, False, True])

    def test_sole_raiser_in_round_one_changes_nothing(self):
        game = self.game
        game.com_action = com_drops(0, 1, 2)
        game.decide("raise")
        self.assertEqual(game.phase, Phase.FINISHED)
        self.assertEqual(self.publics(), [True] * PLAYER_COUNT)


class TestInvalidOperations(unittest.TestCase):
    """BR2.12: 不正な操作は ValueError。"""

    def test_decide_after_finished_raises(self):
        game = Game.start(seed=0)
        game.com_action = com_drops(0, 1, 2)
        game.decide("drop")
        with self.assertRaises(ValueError):
            game.decide("raise")

    def test_missing_human_action_raises(self):
        game = Game.start(seed=0)
        with self.assertRaises(ValueError):
            game.decide()
        self.assertEqual(game.phase, Phase.FIRST_DECISION)

    def test_unknown_human_action_raises(self):
        game = Game.start(seed=0)
        with self.assertRaises(ValueError):
            game.decide("fold")

    def test_unneeded_human_action_raises(self):
        game = Game.start(seed=0)
        game.decide("raise")
        game.active = [0, 1, 2]
        with self.assertRaises(ValueError):
            game.decide("raise")


class TestNextGame(unittest.TestCase):
    """FR6.1、FR7.2、FR7.3: 次のゲーム（人たちとポットを引き継ぐ）。"""

    def finished_game(self):
        """全員が 2 回レイズして位置 1 が勝った 1 ゲーム目。"""
        game = Game.start(seed=0)
        set_hands(game, {1: PAIR})
        game.com_action = com_drops()  # COM は全員レイズ
        game.decide("raise")
        game.decide("raise")
        return game

    def test_start_with_players_keeps_them_and_their_coins(self):
        previous = self.finished_game()
        game = Game.start(seed=1, players=previous.table.players)
        # 渡した人たち（同じオブジェクト）に配り直し、参加費だけ減る
        self.assertIs(previous.table.players, game.table.players)
        # 勝者の所持 = 10 - 4 + 16 = 22 から参加費を払う
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        winner_coins = INITIAL_COINS - paid + paid * PLAYER_COUNT
        self.assertEqual(game.table.players[1].coins, winner_coins - ENTRY_FEE)

    def test_next_game_carries_players_coins_and_pot(self):
        game = self.finished_game()
        # 各自の支払い = 参加費 1 + 1 回目 1 + 2 回目 2 = 4、ポット = 4 × 4 = 16
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        pot_total = paid * PLAYER_COUNT
        winner_coins = INITIAL_COINS - paid + pot_total
        other_coins = INITIAL_COINS - paid
        pot = game.pot
        nxt = game.next_game(seed=1)
        # 勝者がポットを受け取った後は 0 なので、ポット = 次の参加費 1 × 4
        self.assertIsNot(game, nxt)
        self.assertIs(pot, nxt.pot)
        self.assertEqual(nxt.pot.amount, ENTRY_FEE * PLAYER_COUNT)
        # 所持コイン = 前のゲームの所持コイン - 参加費
        coins = [p.coins for p in nxt.table.players]
        expected = [other_coins - ENTRY_FEE] * PLAYER_COUNT
        expected[1] = winner_coins - ENTRY_FEE
        self.assertEqual(coins, expected)
        self.assertIs(game.table.players, nxt.table.players)

    def test_next_game_uses_new_shuffled_deck(self):
        game = self.finished_game()
        nxt = game.next_game(seed=1)
        # 同じ種の新規ゲームと同じ配札（山を作り直している）
        fresh = Game.start(seed=1)
        self.assertEqual(
            [p.hand for p in fresh.table.players], [p.hand for p in nxt.table.players]
        )

    def test_next_game_resets_phase_winner_and_dropped(self):
        game = self.finished_game()
        nxt = game.next_game(seed=1)
        self.assertEqual(nxt.phase, Phase.FIRST_DECISION)
        self.assertEqual(nxt.active, list(range(PLAYER_COUNT)))
        self.assertEqual(nxt.dropped, set())
        self.assertIsNone(nxt.winner)
        self.assertEqual(nxt.awarded, 0)
        for player in nxt.table.players:
            self.assertTrue(player.hand_public)
            self.assertFalse(player.exchanged)
            self.assertEqual(player.selected, set())

    def test_all_drop_carries_pot_over(self):
        game = Game.start(seed=0)
        game.com_action = com_drops(0, 1, 2)
        game.decide("drop")
        # 全員ドロップ: ポット = 参加費 4 が残り、次の参加費 4 が加わって 8
        nxt = game.next_game(seed=1)
        self.assertEqual(nxt.pot.amount, ENTRY_FEE * PLAYER_COUNT * 2)
        for player in nxt.table.players:
            self.assertEqual(player.coins, INITIAL_COINS - ENTRY_FEE * 2)

    def test_next_game_before_finished_raises(self):
        game = Game.start(seed=0)
        with self.assertRaises(ValueError):
            game.next_game(seed=1)
        self.assertEqual(game.phase, Phase.FIRST_DECISION)


if __name__ == "__main__":
    unittest.main()
