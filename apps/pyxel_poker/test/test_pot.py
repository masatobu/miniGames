"""コインの支払いとポット（src/pot.py）のテスト。"""

import unittest

from src.cards import INITIAL_COINS, Player
from src.pot import ENTRY_FEE, Pot, raise_cost


class TestPaymentSchedule(unittest.TestCase):
    """参加費とレイズの追加額、累積支払いの表。"""

    def test_entry_fee_is_one(self):
        self.assertEqual(ENTRY_FEE, 1)

    def test_raise_cost_per_round(self):
        # 1 回目のレイズは 1 コイン、2 回目は 2 コイン（回の番号と同じ）
        self.assertEqual(raise_cost(1), 1)
        self.assertEqual(raise_cost(2), 2)

    def test_raise_cost_rejects_other_rounds(self):
        # 1・2 回目以外の額は決められないので、黙って誤った額を返さない
        for round_number in (0, 3, -1):
            with self.subTest(round_number=round_number):
                with self.assertRaises(ValueError):
                    raise_cost(round_number)

    def test_cumulative_payment_table(self):
        # 累積 = 参加費 + レイズした回の追加額の合計。ドロップは追加が 0
        join = ENTRY_FEE
        drop_first = ENTRY_FEE
        raise_first = ENTRY_FEE + raise_cost(1)
        drop_second = raise_first
        raise_second = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(
            [join, drop_first, raise_first, drop_second, raise_second],
            [1, 1, 2, 2, 4],
        )


class TestPotPay(unittest.TestCase):
    """Pot.pay が所持コインからポットへ移すこと。"""

    def setUp(self):
        self.pot = Pot()
        self.player = Player("human")

    def test_initial_amount_is_zero(self):
        self.assertEqual(self.pot.amount, 0)

    def test_pay_moves_coins_to_pot(self):
        paid = self.pot.pay(self.player, ENTRY_FEE)
        self.assertEqual(paid, ENTRY_FEE)
        self.assertEqual(self.pot.amount, ENTRY_FEE)
        self.assertEqual(self.player.coins, INITIAL_COINS - ENTRY_FEE)

    def test_four_players_pay_into_pot(self):
        # 4 人が最大の累積支払い 4 を払うと、ポットは 4 人分 = 4 * 4
        max_payment = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        players = [Player("com") for _ in range(3)] + [self.player]
        for player in players:
            self.pot.pay(player, max_payment)
        self.assertEqual(self.pot.amount, len(players) * max_payment)

    def test_pay_is_capped_by_coins(self):
        # 所持コインを超える額は、所持コインの分だけ払い、0 を下回らない
        self.player.coins = 1
        paid = self.pot.pay(self.player, 3)
        self.assertEqual(paid, 1)
        self.assertEqual(self.pot.amount, 1)
        self.assertEqual(self.player.coins, 0)

    def test_pay_zero_changes_nothing(self):
        paid = self.pot.pay(self.player, 0)
        self.assertEqual(paid, 0)
        self.assertEqual(self.pot.amount, 0)
        self.assertEqual(self.player.coins, INITIAL_COINS)

    def test_pay_negative_raises(self):
        with self.assertRaises(ValueError):
            self.pot.pay(self.player, -1)
        self.assertEqual(self.pot.amount, 0)
        self.assertEqual(self.player.coins, INITIAL_COINS)


class TestPotAward(unittest.TestCase):
    """Pot.award が勝者へ全額を渡し、持ち越しで累積すること。"""

    def setUp(self):
        self.pot = Pot()
        self.winner = Player("com")
        self.loser = Player("human")

    def test_award_gives_whole_pot_to_winner(self):
        self.pot.pay(self.winner, 2)
        self.pot.pay(self.loser, 3)
        pot_before = self.pot.amount
        received = self.pot.award(self.winner)
        self.assertEqual(received, pot_before)
        self.assertEqual(self.winner.coins, INITIAL_COINS - 2 + pot_before)
        self.assertEqual(self.pot.amount, 0)

    def test_award_empty_pot_changes_nothing(self):
        received = self.pot.award(self.winner)
        self.assertEqual(received, 0)
        self.assertEqual(self.winner.coins, INITIAL_COINS)
        self.assertEqual(self.pot.amount, 0)

    def test_pot_carries_over_without_award(self):
        # 全員ドロップで award を呼ばないと、ポットは残り次の支払いが加わる
        first_game = ENTRY_FEE
        second_game = ENTRY_FEE + raise_cost(1)
        self.pot.pay(self.loser, first_game)
        self.pot.pay(self.loser, second_game)
        self.assertEqual(self.pot.amount, first_game + second_game)
