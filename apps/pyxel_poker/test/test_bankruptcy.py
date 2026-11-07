"""破産の判定と脱落（src/cards.py・src/pot.py・src/game.py）のテスト。"""

import unittest

from src import pot
from src.cards import HAND_SIZE, PLAYER_KINDS, Player
from src.game import Game, Phase
from src.pot import ENTRY_FEE, raise_cost

PLAYER_COUNT = len(PLAYER_KINDS)  # 4
HUMAN = PLAYER_COUNT - 1  # 人間は最後（3）
# 1 ゲームの累積支払いの最大 = 参加費 + 1 回目のレイズ + 2 回目のレイズ
THRESHOLD = ENTRY_FEE + raise_cost(1) + raise_cost(2)


def make_players(coins_by_position):
    """位置 → 所持コインの対応を反映した、4 人のプレイヤーを作る。"""
    players = [Player(kind) for kind in PLAYER_KINDS]
    for position, coins in coins_by_position.items():
        players[position].coins = coins
    return players


class TestMaxPayment(unittest.TestCase):
    """FR1.1: 参加資格の基準額。"""

    def test_max_payment_is_entry_fee_plus_both_raises(self):
        self.assertEqual(pot.MAX_PAYMENT, THRESHOLD)


class TestJudgement(unittest.TestCase):
    """FR1.1: 開始時に所持コインが基準額に満たない人は破産になる。"""

    def test_player_is_not_bankrupt_by_default(self):
        self.assertFalse(Player("com").bankrupt)

    def test_threshold_coins_is_not_bankrupt(self):
        # 境界: 基準額ちょうどは参加できる
        players = make_players({0: THRESHOLD})
        Game.start(seed=0, players=players)
        self.assertFalse(players[0].bankrupt)

    def test_below_threshold_is_bankrupt(self):
        # 境界: 基準額 - 1 は破産
        players = make_players({0: THRESHOLD - 1})
        Game.start(seed=0, players=players)
        self.assertTrue(players[0].bankrupt)

    def test_zero_coins_is_bankrupt(self):
        players = make_players({0: 0})
        Game.start(seed=0, players=players)
        self.assertTrue(players[0].bankrupt)

    def test_bankruptcy_keeps_coins_unchanged(self):
        # BR1.6: 破産しても所持コインは変えない
        coins = THRESHOLD - 1
        players = make_players({0: coins})
        Game.start(seed=0, players=players)
        self.assertEqual(players[0].coins, coins)


class TestExclusion(unittest.TestCase):
    """FR1.2: 破産者は参加費を払わず、配札されず、勝負に残らない。"""

    def setUp(self):
        self.coins = THRESHOLD - 1
        self.players = make_players({0: self.coins})
        self.game = Game.start(seed=0, players=self.players)

    def test_bankrupt_player_pays_no_entry_fee(self):
        # ポット = 参加費 × 参加者（破産者を除く）
        self.assertEqual(self.players[0].coins, self.coins)
        self.assertEqual(self.game.pot.amount, ENTRY_FEE * (PLAYER_COUNT - 1))

    def test_bankrupt_player_gets_no_cards(self):
        self.assertEqual(self.players[0].hand, [])
        self.assertFalse(self.players[0].hand_public)
        for player in self.players[1:]:
            self.assertEqual(len(player.hand), HAND_SIZE)

    def test_bankrupt_player_is_neither_active_nor_dropped(self):
        self.assertEqual(self.game.active, list(range(1, PLAYER_COUNT)))
        self.assertNotIn(0, self.game.dropped)
        self.assertEqual(self.game.phase, Phase.FIRST_DECISION)

    def test_bankrupt_stays_after_coins_increase(self):
        # BR1.2: 所持コインが基準額以上に増えても、破産は戻らない
        self.game.decide("drop")
        self.players[0].coins = THRESHOLD + 5
        next_game = self.game.next_game(seed=1)
        self.assertTrue(self.players[0].bankrupt)
        self.assertEqual(self.players[0].coins, THRESHOLD + 5)
        self.assertEqual(self.players[0].hand, [])
        self.assertNotIn(0, next_game.active)


class TestParticipantsNeverShort(unittest.TestCase):
    """FR1.3: 参加者は、ゲームの最後まで進んでもコインが不足しない。"""

    def test_boundary_participant_pays_in_full(self):
        # 基準額ちょうどの人は、全部レイズしても所持コインが 0 になるだけで不足しない
        players = make_players({0: THRESHOLD, 1: THRESHOLD})
        game = Game.start(seed=0, players=players)
        game.decide("raise")
        game.decide("raise")
        self.assertEqual(game.phase, Phase.FINISHED)
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        # 勝者でない人は THRESHOLD - paid = 0 のまま。勝者はポットを受け取って増える
        for position in (0, 1):
            self.assertGreaterEqual(players[position].coins, THRESHOLD - paid)


class TestJudgementTiming(unittest.TestCase):
    """FR1.4: 判定は参加費の支払いより前、最初のゲームと次のゲームの両方で行う。"""

    def test_judged_before_entry_fee(self):
        # 参加費を先に払うと、3 コインの人は 2 コインに減ってから判定されてしまう
        players = make_players({0: THRESHOLD - 1})
        game = Game.start(seed=0, players=players)
        self.assertTrue(players[0].bankrupt)
        self.assertEqual(players[0].coins, THRESHOLD - 1)
        self.assertEqual(game.pot.amount, ENTRY_FEE * (PLAYER_COUNT - 1))

    def test_next_game_judges_bankruptcy(self):
        game = Game.start(seed=0)
        game.decide("drop")
        self.assertEqual(game.phase, Phase.FINISHED)
        # 1 ゲーム目の後に所持コインが不足した人は、次のゲームの開始で破産になる
        player = game.table.players[1]
        player.coins = THRESHOLD - 1
        next_game = game.next_game(seed=1)
        self.assertTrue(player.bankrupt)
        self.assertEqual(player.coins, THRESHOLD - 1)
        self.assertEqual(player.hand, [])
        self.assertNotIn(1, next_game.active)
        self.assertNotIn(1, next_game.dropped)


if __name__ == "__main__":
    unittest.main()
