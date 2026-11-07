import unittest
from unittest.mock import patch

from test.recording_view import RecordingView
from test.test_main import (
    DROP_BUTTON_X,
    RAISE_BUTTON_X,
    FakeInput,
    TestParent,
    button_center,
    screen_calls,
)
from src.cards import INITIAL_COINS
from src.game import Game, Phase
from src.main import GameCore
from src.pot import ENTRY_FEE, MAX_PAYMENT
from src.table_view import (
    draw_result_popup,
    draw_session_popup,
    draw_winner_frame,
)

SEED = 5
SESSION_TEXTS = ("YOU WIN", "GAME OVER", "TAP TO RESTART")
# 破産の境目: 所持コインが MAX_PAYMENT 未満なら次のゲームの開始時に破産する
BANKRUPT_COINS = MAX_PAYMENT - 1


def popup_calls(outcome):
    """セッション終了のポップアップだけを描いた呼び出し"""
    view = RecordingView()
    draw_session_popup(view, outcome)
    return view.calls


class TestSessionFlow(TestParent):
    """FR1.4、FR4.1〜FR4.3、FR5.1: 勝敗の表示 → 継続判定 → 終了のポップアップ → 新しいセッション。"""

    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.core = GameCore(input=self.input, view=self.view, seed=SEED)

    # pylint: disable=W0212
    @property
    def game(self):
        return self.core._game

    def click_button(self, button_x):
        self.input.click_at(*button_center(button_x))
        self.core.update()

    def click_anywhere(self):
        self.input.click_at(0, 0)
        self.core.update()

    def finish_game(self):
        """人間がドロップして 1 ゲームを終える（勝者がポットを受け取る）。"""
        self.click_button(DROP_BUTTON_X)
        self.assertEqual(Phase.FINISHED, self.game.phase)

    def set_coins(self, human=None, com=None):
        for player in self.game.table.players:
            coins = human if player.kind == "human" else com
            if coins is not None:
                player.coins = coins

    def drawn(self):
        self.view.calls.clear()
        self.core.draw()
        return list(self.view.calls)

    def drawn_texts(self):
        return [call[3] for call in self.drawn() if call[0] == "text"]

    def end_session(self, human=None, com=None):
        """ゲームを終え、コインを設定し、次のゲームを始めるクリックまで進める。"""
        self.finish_game()
        self.set_coins(human, com)
        self.click_anywhere()

    def test_continuing_session_draws_no_session_popup(self):
        """BR5.1: 破産がなければ、次のゲームを始めてもセッション終了のポップアップは出ない"""
        self.end_session()
        self.assertIsNone(self.game.session_result())
        self.assertEqual(Phase.FIRST_DECISION, self.game.phase)
        texts = self.drawn_texts()
        for message in SESSION_TEXTS:
            self.assertNotIn(message, texts)

    def test_human_bankrupt_draws_game_over_last(self):
        """BR5.2、BR5.6: 人間が破産すると GAME OVER と TAP TO RESTART が最後に描かれる"""
        self.end_session(human=BANKRUPT_COINS)
        self.assertEqual("lose", self.game.session_result())
        calls = self.drawn()
        expected_tail = popup_calls("lose")
        self.assertIn("GAME OVER", [c[3] for c in expected_tail if c[0] == "text"])
        self.assertIn("TAP TO RESTART", [c[3] for c in expected_tail if c[0] == "text"])
        # ポップアップは盤面（段・ポット）より後 = 最後。それ以前は従来の描画のまま
        self.assertEqual(screen_calls(self.game) + expected_tail, calls)

    def test_all_com_bankrupt_draws_you_win(self):
        """BR5.2: COM が全員破産し人間が残ると YOU WIN と TAP TO RESTART が最後に描かれる"""
        self.end_session(com=BANKRUPT_COINS)
        self.assertEqual("win", self.game.session_result())
        calls = self.drawn()
        expected_tail = popup_calls("win")
        texts = [c[3] for c in expected_tail if c[0] == "text"]
        self.assertIn("YOU WIN", texts)
        self.assertIn("TAP TO RESTART", texts)
        self.assertEqual(screen_calls(self.game) + expected_tail, calls)

    def test_click_during_ended_session_does_not_decide(self):
        """BR5.3: 終了中のボタンのクリックは判断を進めない（decide を呼ばず、終了したゲームも変えない）"""
        # COM が全員破産 = 人間は勝負に残っている（セッション中なら Raise で decide が呼ばれる状況）
        self.end_session(com=BANKRUPT_COINS)
        ended = self.game
        pot_before = ended.pot.amount
        coins_before = [p.coins for p in ended.table.players]
        hands_before = [list(p.hand) for p in ended.table.players]
        with patch.object(Game, "decide") as decide:
            self.click_button(RAISE_BUTTON_X)
            decide.assert_not_called()
        self.assertEqual(pot_before, ended.pot.amount)
        self.assertEqual(coins_before, [p.coins for p in ended.table.players])
        self.assertEqual(hands_before, [list(p.hand) for p in ended.table.players])
        self.assertEqual(Phase.FIRST_DECISION, ended.phase)

    def test_click_during_ended_session_starts_new_session(self):
        """BR5.4: 終了中のクリックで新しいセッションが始まり、全員が初期状態になり、ポップアップが消える"""
        self.end_session(human=BANKRUPT_COINS)
        seed_before = self.core._seed
        self.click_anywhere()
        players = self.game.table.players
        self.assertEqual(
            [INITIAL_COINS - ENTRY_FEE] * len(players), [p.coins for p in players]
        )
        self.assertEqual(ENTRY_FEE * len(players), self.game.pot.amount)
        self.assertFalse(any(p.bankrupt for p in players))
        self.assertIsNone(self.game.session_result())
        self.assertEqual(Phase.FIRST_DECISION, self.game.phase)
        self.assertEqual(seed_before + 1, self.core._seed)
        texts = self.drawn_texts()
        for message in SESSION_TEXTS:
            self.assertNotIn(message, texts)

    def test_one_click_advances_one_step(self):
        """BR5.5: 次のゲームを始めたクリックで、同時に新しいセッションにはならない"""
        self.finish_game()
        self.set_coins(human=BANKRUPT_COINS)
        seed_before = self.core._seed
        self.click_anywhere()
        # このクリックはポップアップを出しただけ。種は次のゲーム分の 1 だけ進み、破産は残る
        self.assertEqual(seed_before + 1, self.core._seed)
        self.assertEqual("lose", self.game.session_result())
        self.assertTrue(self.game.table.players[self.game.human_index].bankrupt)

    def test_result_banner_still_drawn_during_play(self):
        """BR5.6、FR4.1: ゲーム中の勝敗の帯（WIN／LOSE）はこれまでどおり出て、終了のポップアップは出ない"""
        self.finish_game()
        game = self.game
        expected = RecordingView()
        expected.calls.extend(screen_calls(game))
        draw_winner_frame(expected, game.winner)
        result = self.core._result
        draw_result_popup(expected, result, game.awarded if result == "win" else None)
        calls = self.drawn()
        self.assertEqual(expected.calls, calls)
        for message in SESSION_TEXTS:
            self.assertNotIn(message, [c[3] for c in calls if c[0] == "text"])


if __name__ == "__main__":
    unittest.main()
