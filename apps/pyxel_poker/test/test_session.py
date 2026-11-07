"""セッションの結果の判定と新しいセッションの開始（src/game.py）のテスト。"""

import unittest

from src.cards import HAND_SIZE, INITIAL_COINS, PLAYER_KINDS, Player
from src.game import Game, Phase
from src.pot import ENTRY_FEE

PLAYER_COUNT = len(PLAYER_KINDS)  # 4
HUMAN = PLAYER_KINDS.index("human")  # 人間の位置
COMS = [i for i, kind in enumerate(PLAYER_KINDS) if kind != "human"]  # COM の位置
COM_COUNT = len(COMS)  # 3


def make_game(bankrupt_positions):
    """指定した位置のプレイヤーを破産にした Game を作る（結果の判定は破産の状態だけを見る）。"""
    game = Game.start(seed=0)
    for position in bankrupt_positions:
        game.table.players[position].bankrupt = True
    return game


class TestSessionResult(unittest.TestCase):
    """FR2.1〜FR2.4: 破産の状態からセッションの結果を決める。"""

    def test_human_bankrupt_is_lose(self):
        # FR2.1
        self.assertEqual(make_game([HUMAN]).session_result(), "lose")

    def test_all_com_bankrupt_is_win(self):
        # FR2.2: COM 全員が破産で、人間は破産なし
        self.assertEqual(make_game(COMS).session_result(), "win")

    def test_everyone_bankrupt_is_lose(self):
        # FR2.3: 全員破産は人間の破産を優先して敗北
        self.assertEqual(make_game(range(PLAYER_COUNT)).session_result(), "lose")

    def test_partial_com_bankrupt_is_none(self):
        # FR2.4: COM の破産が 0〜(COM 数 - 1) 人なら継続
        for count in range(COM_COUNT):
            with self.subTest(bankrupt_com_count=count):
                self.assertIsNone(make_game(COMS[:count]).session_result())

    def test_result_does_not_depend_on_phase(self):
        # BR2.5: ゲームの段階が違っても、破産の状態が同じなら結果も同じ
        for bankrupt, expected in (([], None), (COMS, "win"), ([HUMAN], "lose")):
            for phase in (Phase.FIRST_DECISION, Phase.SECOND_DECISION, Phase.FINISHED):
                with self.subTest(bankrupt=bankrupt, phase=phase):
                    game = make_game(bankrupt)
                    game.phase = phase
                    self.assertEqual(game.session_result(), expected)


class TestNewSession(unittest.TestCase):
    """FR5.2、FR5.3: 新しいセッションは何も引き継がずに 1 ゲーム目から始める。"""

    def test_everyone_starts_with_initial_coins_minus_entry_fee(self):
        game = Game.new_session(seed=0)
        for player in game.table.players:
            self.assertEqual(player.coins, INITIAL_COINS - ENTRY_FEE)

    def test_nobody_is_bankrupt(self):
        game = Game.new_session(seed=0)
        self.assertFalse(any(p.bankrupt for p in game.table.players))
        self.assertIsNone(game.session_result())

    def test_pot_is_entry_fees_of_all_players(self):
        game = Game.new_session(seed=0)
        self.assertEqual(game.pot.amount, ENTRY_FEE * PLAYER_COUNT)

    def test_starts_at_first_decision_with_dealt_hands(self):
        game = Game.new_session(seed=0)
        self.assertEqual(game.phase, Phase.FIRST_DECISION)
        self.assertEqual(game.active, list(range(PLAYER_COUNT)))
        for player in game.table.players:
            self.assertEqual(len(player.hand), HAND_SIZE)

    def test_does_not_inherit_previous_session(self):
        # FR5.3: 破産・コイン 0・ポット持ち越しがあった Game の後でも、全員が参加する
        old = Game.start(seed=0)
        for player in old.table.players:
            player.bankrupt = True
            player.coins = 0
        old.pot.amount += 100
        game = Game.new_session(seed=0)
        self.assertIsNot(game.table.players[0], old.table.players[0])
        self.assertIsNot(game.pot, old.pot)
        self.assertEqual(game.pot.amount, ENTRY_FEE * PLAYER_COUNT)
        self.assertEqual(game.active, list(range(PLAYER_COUNT)))
        for player in game.table.players:
            self.assertIsInstance(player, Player)
            self.assertFalse(player.bankrupt)
            self.assertEqual(player.coins, INITIAL_COINS - ENTRY_FEE)

    def test_same_seed_gives_same_deal(self):
        # 乱数は配札の種だけで決まる
        first = Game.new_session(seed=1)
        second = Game.new_session(seed=1)
        self.assertEqual(
            [p.hand for p in first.table.players],
            [p.hand for p in second.table.players],
        )


if __name__ == "__main__":
    unittest.main()
