import unittest
from unittest.mock import patch

from test.recording_view import RecordingView
from src.card_view import CARD_BACK_COLOR, CHAR_WIDTH
from src.cards import INITIAL_COINS, Card
from src.game import Action, Game, Phase
from src.main import GameCore, IInput
from src.pot import ENTRY_FEE, raise_cost
from src.table_view import (
    BUTTON_FRAME_PADDING,
    BUTTON_SIZE,
    BUTTON_Y,
    CARD_HEIGHT,
    CARD_PITCH,
    CARD_WIDTH,
    CHAR_HEIGHT,
    COM_ROW_PITCH,
    COM_ROW_TOP,
    DROP_BUTTON_X,
    HAND_X,
    POPUP_HEIGHT,
    POPUP_WIDTH,
    POPUP_X,
    POPUP_Y,
    RAISE_BUTTON_X,
    ROW_PITCH,
    ROW_TOP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    draw_pot,
    draw_result_popup,
    draw_table,
    draw_winner_frame,
)


def row_top(index):
    """段 index（0 始まり。最後が人間）の上端 y。COM の 3 段は人間の段と間隔が違う。"""
    if index < 3:
        return COM_ROW_TOP + index * COM_ROW_PITCH
    return ROW_TOP + index * ROW_PITCH


# 人間の段（4 段目）のカードの上端 y
HUMAN_CARD_Y = ROW_TOP + 3 * ROW_PITCH + (ROW_PITCH - CARD_HEIGHT) // 2


class FakeInput(IInput):
    """テスト用の入力。click_at で次のフレームのクリック位置を指定する。"""

    def __init__(self):
        self.clicked = False
        self.x = 0
        self.y = 0

    def click_at(self, x, y):
        self.clicked = True
        self.x = x
        self.y = y

    def is_click(self):
        return self.clicked

    def get_mouse_x(self):
        return self.x

    def get_mouse_y(self):
        return self.y


def card_center_x(n):
    """位置 n のカードの中央の x"""
    return HAND_X + n * CARD_PITCH + CARD_WIDTH // 2


def button_center(button_x):
    """ボタンのアイコンの中央 (x, y)"""
    return button_x + BUTTON_SIZE // 2, BUTTON_Y + BUTTON_SIZE // 2


def screen_calls(game):
    """game の盤面を、ポットの額も含めて描いた呼び出し（勝者の枠もポップアップも無い）。
    ドロップした段は手札を描かない。ポップアップが出る間（勝者がいる）はポットの額を描かない。"""
    expected_view = RecordingView()
    draw_table(expected_view, game.table, game.dropped)
    if game.winner is None:
        draw_pot(expected_view, game.pot.amount)
    return expected_view.calls


def table_only_calls(core):
    """core の現在のゲームを、勝者の枠もポップアップも無しで描いた呼び出し"""
    return screen_calls(core._game)  # pylint: disable=W0212


class TestParent(unittest.TestCase):
    def setUp(self):
        self.view = RecordingView()
        patcher = patch("src.main.PyxelView.create", return_value=self.view)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 入力を渡さない GameCore() が、Pyxel を初期化せずに済むようにする
        input_patcher = patch("src.main.PyxelInput.create", return_value=FakeInput())
        input_patcher.start()
        self.addCleanup(input_patcher.stop)

    def expected_calls(self, seed):
        """同じ種で開始した（参加費を払った）Table を draw_table で描いたときの呼び出し"""
        return screen_calls(Game.start(seed))


class TestGameCore(TestParent):
    def test_draw_shows_dealt_table(self):
        """FR3.1: draw() が、配札した Table を draw_table で描くこと"""
        core = GameCore(seed=0)
        core.draw()
        self.assertEqual(self.expected_calls(0), self.view.calls)

    def test_draw_does_not_redeal(self):
        """FR3.1: draw() を何度呼んでも、配り直さず同じ描画になること"""
        core = GameCore(seed=0)
        core.draw()
        first = list(self.view.calls)
        self.view.calls.clear()
        core.draw()
        self.assertEqual(first, self.view.calls)

    def test_same_seed_same_deal(self):
        """FR3.1: 種を固定すると同じ配札になること"""
        core_a = GameCore(seed=1)
        core_a.draw()
        calls_a = list(self.view.calls)
        self.view.calls.clear()
        GameCore(seed=1).draw()
        self.assertEqual(calls_a, self.view.calls)

    def test_update_does_not_change_state(self):
        """FR3.2: クリックが無ければ update() を呼んでも状態が変わらないこと（開始時は全員が参加費を払い済み）"""
        core = GameCore(seed=0)

        # pylint: disable=W0212
        def snapshot():
            return [(p.kind, list(p.hand), p.coins) for p in core._table.players]

        before = snapshot()
        # 起動直後の所持コイン = 初期コイン - 参加費（FR1.2）
        self.assertEqual(
            [INITIAL_COINS - ENTRY_FEE] * 4, [coins for _, _, coins in before]
        )
        core.update()
        self.assertEqual(before, snapshot())


class TestClickInput(TestParent):
    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.core = GameCore(input=self.input, view=self.view, seed=0)
        # pylint: disable=W0212
        self.table = self.core._table
        self.human = self.table.players[3]

    def click_card(self, n):
        self.input.click_at(card_center_x(n), HUMAN_CARD_Y + CARD_HEIGHT // 2)
        self.core.update()

    def click_button(self, button_x):
        self.input.click_at(*button_center(button_x))
        self.core.update()

    def test_click_card_toggles_selection(self):
        """FR1.1: カードのクリックで選択され、もう一度のクリックで解除されること"""
        self.click_card(1)
        self.assertEqual([1], self.human.selected_indices())
        self.click_card(1)
        self.assertEqual([], self.human.selected_indices())

    def test_click_raise_exchanges_selected(self):
        """FR2.1: 「Raise」のクリックで、選択したカードが交換されること"""
        self.click_card(0)
        self.click_card(3)
        before = list(self.human.hand)
        self.click_button(RAISE_BUTTON_X)
        self.assertTrue(self.human.exchanged)
        self.assertEqual([0, 3], sorted(self.human.new_indices))
        for n in (1, 2, 4):
            self.assertEqual(before[n], self.human.hand[n])

    def test_click_after_exchange_changes_nothing(self):
        """FR2.3: 交換済みでは、カード・「Raise」のクリックで状態が変わらないこと"""
        self.click_card(2)
        self.click_button(RAISE_BUTTON_X)
        hand = list(self.human.hand)
        selected = list(self.human.selected_indices())
        self.click_card(0)
        self.click_button(RAISE_BUTTON_X)
        self.assertEqual(hand, self.human.hand)
        self.assertEqual(selected, self.human.selected_indices())

    def test_click_drop_ends_game_without_exchange(self):
        """FR4.3: 1 回目の「drop」は、選択中でも交換せずにゲームを終えること（人間は参加費だけを払う）"""
        self.click_card(4)
        hand = list(self.human.hand)
        self.click_button(DROP_BUTTON_X)
        self.assertFalse(self.human.exchanged)
        self.assertEqual(hand, self.human.hand)
        self.assertEqual([4], self.human.selected_indices())
        # 人間は追加で払わない: 参加費だけ払った所持コイン
        self.assertEqual(INITIAL_COINS - ENTRY_FEE, self.human.coins)

    def test_no_click_does_nothing(self):
        """クリックが無いフレームでは、座標がカードの上でも何も起きないこと"""
        self.input.x = card_center_x(0)
        self.input.y = HUMAN_CARD_Y + CARD_HEIGHT // 2
        self.core.update()
        self.assertEqual([], self.human.selected_indices())
        self.assertFalse(self.human.exchanged)

    def test_click_outside_does_nothing(self):
        """カードにもボタンにも当たらないクリックでは何も起きないこと"""
        pad = BUTTON_FRAME_PADDING
        self.input.click_at(0, BUTTON_Y - pad - 1)
        self.core.update()
        self.assertEqual([], self.human.selected_indices())
        self.assertFalse(self.human.exchanged)


# 0 枚を選んで Raise しても判定される（手札は配札のまま）。種ごとの勝敗は
# Table.deal(seed) と human_result で探した: seed=0 は COM が勝つ（lose）、seed=6 は人間が勝つ（win）
LOSE_SEED = 0
WIN_SEED = 6
# 勝者の位置（0 始まり。最後が人間）。find_winner で探した: seed=0 は 1 人目の COM、seed=6 は人間
LOSE_WINNER_ROW = 0
WIN_WINNER_ROW = 3
HUMAN_ROW = 3
# 人間が必ず勝つ手札（ロイヤルストレートフラッシュ。マークは spade）
ROYAL_HAND = [Card(rank, "spade") for rank in range(10, 15)]


class TestRaiseJudgment(TestParent):
    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.table = None
        self.core = None

    def make_core(self, seed):
        core = GameCore(input=self.input, view=self.view, seed=seed)
        # pylint: disable=W0212
        self.table = core._table
        self.core = core
        return core

    def click_button(self, core, button_x):
        self.input.click_at(*button_center(button_x))
        core.update()

    def drawn(self, core):
        """core.draw() の呼び出しだけを返す（以前の記録は捨てる）。"""
        self.view.calls.clear()
        core.draw()
        return list(self.view.calls)

    def drawn_table_only(self):
        """現在のゲームを、帯とポットの額も含めて描いた呼び出し（勝者の枠もポップアップも無い）"""
        return screen_calls(self.core._game)  # pylint: disable=W0212

    def expected_with_popup(self, result, winner_row):
        """現在のゲームの盤面の後に、勝者の枠とポップアップを重ねた呼び出し。
        ポップアップがポットの額に置き換わるのでポットは描かず、win は受け取った額（GOT N）も描く。"""
        expected_view = RecordingView()
        game = self.core._game  # pylint: disable=W0212
        draw_table(expected_view, game.table, game.dropped)
        draw_winner_frame(expected_view, winner_row)
        draw_result_popup(
            expected_view, result, game.awarded if result == "win" else None
        )
        return expected_view.calls

    def raise_twice(self, core):
        """1 回目（交換）と 2 回目の Raise を押して、ゲームを終える。"""
        self.click_button(core, RAISE_BUTTON_X)
        self.click_button(core, RAISE_BUTTON_X)

    def test_second_raise_draws_lose_popup_when_com_wins(self):
        """FR4.3: COM が勝者なら、2 回目の Raise の後に lose のポップアップが描かれること"""
        core = self.make_core(LOSE_SEED)
        self.raise_twice(core)
        self.assertEqual(
            self.expected_with_popup("lose", LOSE_WINNER_ROW), self.drawn(core)
        )

    def test_second_raise_draws_win_popup_when_human_wins(self):
        """FR4.3: 人間が勝者なら、2 回目の Raise の後に win のポップアップが描かれること"""
        core = self.make_core(WIN_SEED)
        self.raise_twice(core)
        self.assertEqual(
            self.expected_with_popup("win", WIN_WINNER_ROW), self.drawn(core)
        )

    def test_first_raise_advances_without_result(self):
        """FR2.4: 1 回目の Raise は全員が追加で払って 2 回目に進み、結果は未決であること"""
        core = self.make_core(LOSE_SEED)
        self.click_button(core, RAISE_BUTTON_X)
        # 全員の所持コイン = 初期コイン - (参加費 + 1 回目のレイズ追加額)
        self.assertEqual(
            [INITIAL_COINS - ENTRY_FEE - raise_cost(1)] * 4,
            [p.coins for p in self.table.players],
        )
        # 結果が未決: 勝者の枠もポップアップも無い従来の描画
        self.assertEqual(self.drawn_table_only(), self.drawn(core))

    def test_second_raise_pays_and_winner_takes_pot(self):
        """FR4.3: 2 回目の Raise の後、全員が最大額を払い、勝者がポットを受け取ること"""
        for seed, winner_row in (
            (LOSE_SEED, LOSE_WINNER_ROW),
            (WIN_SEED, WIN_WINNER_ROW),
        ):
            with self.subTest(seed=seed):
                core = self.make_core(seed)
                # pylint: disable-next=W0212
                core._game.com_action = lambda index: Action.RAISE
                if winner_row == HUMAN_ROW:
                    # COM は交換で引くので、人間が勝つ手札を固定する（山札の並びに頼らない）
                    # pylint: disable-next=W0212
                    core._game.table.players[HUMAN_ROW].hand = list(ROYAL_HAND)
                self.raise_twice(core)
                # 各自の累積支払い = 参加費 + 1 回目 + 2 回目のレイズ追加額（= 4）
                paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
                pot = paid * 4
                expected = [INITIAL_COINS - paid] * 4
                expected[winner_row] += pot
                self.assertEqual(expected, [p.coins for p in self.table.players])

    def test_first_drop_loses_without_exchange(self):
        """FR4.3: 1 回目の drop は交換せず、COM が勝ち、lose のポップアップが描かれること"""
        core = self.make_core(WIN_SEED)
        core._game.com_action = lambda index: Action.RAISE  # pylint: disable=W0212
        self.click_button(core, DROP_BUTTON_X)
        human = self.table.players[3]
        self.assertFalse(human.exchanged)
        # 人間は参加費だけ、COM 3 人は参加費 + 1 回目 + 2 回目のレイズ追加額を払う
        com_paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        # ポット = 人間の参加費 + COM 3 人の支払い
        pot = ENTRY_FEE + 3 * com_paid
        coins = [p.coins for p in self.table.players]
        self.assertEqual(INITIAL_COINS - ENTRY_FEE, coins[3])
        winner_row = next(
            i for i in range(3) if coins[i] == INITIAL_COINS - com_paid + pot
        )
        self.assertEqual(self.expected_with_popup("lose", winner_row), self.drawn(core))

    def test_second_drop_loses(self):
        """FR4.3: 2 回目の drop で、人間は追加で払わず、lose のポップアップが描かれること"""
        core = self.make_core(WIN_SEED)
        self.click_button(core, RAISE_BUTTON_X)
        self.click_button(core, DROP_BUTTON_X)
        human = self.table.players[3]
        # 人間は参加費 + 1 回目のレイズ追加額だけ払い、2 回目は払わない
        self.assertEqual(INITIAL_COINS - ENTRY_FEE - raise_cost(1), human.coins)
        calls = self.drawn(core)
        popup_view = RecordingView()
        draw_result_popup(popup_view, "lose")
        self.assertEqual(popup_view.calls, calls[-len(popup_view.calls) :])

    def test_clicks_after_finish_only_start_next_game(self):
        """FR7.1: 終了後の Raise・drop・カードのクリックは、どれも次のゲームを始めるだけで、そのゲームを操作しないこと"""
        targets = (
            button_center(RAISE_BUTTON_X),
            button_center(DROP_BUTTON_X),
            (card_center_x(1), HUMAN_CARD_Y + CARD_HEIGHT // 2),
        )
        for target in targets:
            # 所持コインが尽きて支払いが減らないよう、クリックの対象ごとに新しく始める
            core = self.make_core(LOSE_SEED)
            # pylint: disable=W0212
            core._game.decide(Action.RAISE)
            core._game.decide(Action.RAISE)
            self.assertEqual(Phase.FINISHED, core._game.phase)
            self.input.click_at(*target)
            core.update()
            # 新しいゲームは 1 回目の判断のまま: 交換も選択も支払いもされず、人間も外れていない
            human = core._table.players[3]
            self.assertEqual(Phase.FIRST_DECISION, core._game.phase)
            self.assertFalse(human.exchanged)
            self.assertEqual([], human.selected_indices())
            self.assertEqual(set(), core._game.dropped)
            self.assertEqual(ENTRY_FEE * 4, core._game.pot.amount)

    def test_winner_frame_only_after_finish_and_only_one(self):
        """FR4.4: 終了の前は赤い枠が無く、後は勝者の 1 人にだけ描かれること（勝つ側と負ける側の両方）"""
        for seed, winner_row in (
            (LOSE_SEED, LOSE_WINNER_ROW),
            (WIN_SEED, WIN_WINNER_ROW),
        ):
            with self.subTest(seed=seed):
                core = self.make_core(seed)
                before = [c for c in self.drawn(core) if c[0] == "rectb" and c[-1] == 8]
                self.assertEqual([], before)
                # 1 回目の Raise の後（未決）もまだ枠は無い
                self.click_button(core, RAISE_BUTTON_X)
                mid = [c for c in self.drawn(core) if c[0] == "rectb" and c[-1] == 8]
                self.assertEqual([], mid)
                self.click_button(core, RAISE_BUTTON_X)
                frame_view = RecordingView()
                draw_winner_frame(frame_view, winner_row)
                frames = [c for c in self.drawn(core) if c in frame_view.calls]
                self.assertEqual(frame_view.calls, frames)

    def test_no_popup_before_raise(self):
        """NFR3: Raise の前は、ポップアップが描かれず従来と同じ描画であること"""
        core = self.make_core(LOSE_SEED)
        self.assertEqual(self.expected_calls(LOSE_SEED), self.drawn(core))

    def test_popup_stays_on_every_frame(self):
        """FR4.3: ポップアップは、以降のフレームでも出たままであること"""
        core = self.make_core(LOSE_SEED)
        self.raise_twice(core)
        first = self.drawn(core)
        self.assertEqual(first, self.drawn(core))

    def test_third_raise_starts_next_game_without_reexchange(self):
        """FR7.1: 3 回目の Raise（終了後）は次のゲームを配り直すだけで、再交換も再判定もしないこと"""
        core = self.make_core(LOSE_SEED)
        self.input.click_at(card_center_x(1), HUMAN_CARD_Y + CARD_HEIGHT // 2)
        core.update()
        self.raise_twice(core)
        self.click_button(core, RAISE_BUTTON_X)
        # 手札は次の種（LOSE_SEED + 1）の配札のまま（交換されていない）
        # pylint: disable=W0212
        self.assertEqual(
            [p.hand for p in Game.start(LOSE_SEED + 1).table.players],
            [p.hand for p in core._table.players],
        )
        self.assertEqual(table_only_calls(core), self.drawn(core))

    def test_drop_ends_game_and_later_click_starts_next_game(self):
        """FR4.3、FR7.1: drop でゲームが終わり、終了後の drop のクリックは次のゲームを始めるだけであること"""
        core = self.make_core(WIN_SEED)
        self.click_button(core, DROP_BUTTON_X)
        judged = self.drawn(core)
        self.assertNotEqual(self.drawn_table_only(), judged)
        # 1 回のクリックで次のゲームへ進み、勝敗の表示は消える。そのクリックでは drop されない
        self.click_button(core, DROP_BUTTON_X)
        # pylint: disable=W0212
        self.assertEqual(Phase.FIRST_DECISION, core._game.phase)
        self.assertEqual(table_only_calls(core), self.drawn(core))

    def test_com_hands_do_not_change(self):
        """FR3.2: レイズが人間 1 人だけのとき、COM の手札が交換されないこと"""
        core = self.make_core(LOSE_SEED)
        # COM は全員ドロップ（人間だけがレイズ）。COM の交換はレイズが 2 人以上のときだけ
        core._game.com_action = lambda index: Action.DROP  # pylint: disable=W0212
        com_hands = [list(p.hand) for p in self.table.players[:3]]
        self.input.click_at(card_center_x(0), HUMAN_CARD_Y + CARD_HEIGHT // 2)
        core.update()
        self.click_button(core, RAISE_BUTTON_X)
        self.assertEqual(com_hands, [list(p.hand) for p in self.table.players[:3]])


class TestComHandBackFlow(TestParent):
    """交換した COM の手札は、勝敗決定まで裏面で、勝敗決定で表に公開される。"""

    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.core = GameCore(input=self.input, view=self.view, seed=LOSE_SEED)
        self.core._game.com_action = lambda index: Action.RAISE  # pylint: disable=W0212

    def click_raise(self):
        self.input.click_at(*button_center(RAISE_BUTTON_X))
        self.core.update()

    def drawn(self):
        self.view.calls.clear()
        self.core.draw()
        return list(self.view.calls)

    def row_cards(self, calls, row):
        """段 row のカードの背景（rect 14x20）。塗りの色も含めて返す。"""
        top = row_top(row) + (ROW_PITCH - CARD_HEIGHT) // 2
        return [
            c
            for c in calls
            if c[0] == "rect" and c[3:5] == (CARD_WIDTH, CARD_HEIGHT) and c[2] == top
        ]

    def test_backs_after_first_raise_and_faces_at_showdown(self):
        self.click_raise()
        calls = self.drawn()
        for row in range(3):
            with self.subTest(row=row):
                cards = self.row_cards(calls, row)
                self.assertEqual(5, len(cards))
                self.assertTrue(all(c[5] == CARD_BACK_COLOR for c in cards))
        human = self.row_cards(calls, 3)
        self.assertEqual(5, len(human))
        self.assertTrue(all(c[5] != CARD_BACK_COLOR for c in human))
        self.click_raise()
        calls = self.drawn()
        self.assertTrue(any(c[0] == "text" and c[3] in ("WIN", "LOSE") for c in calls))
        for row in range(4):
            with self.subTest(row=row):
                cards = self.row_cards(calls, row)
                self.assertEqual(5, len(cards))
                self.assertTrue(all(c[5] != CARD_BACK_COLOR for c in cards))


class TestNextGameClick(TestParent):
    """FR6.1、FR7.1〜FR7.3: 終了後のクリックで、コインとポットを引き継いで次のゲームが始まる。"""

    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.core = GameCore(input=self.input, view=self.view, seed=LOSE_SEED)

    def click_button(self, button_x):
        self.input.click_at(*button_center(button_x))
        self.core.update()

    def click_anywhere(self):
        """ボタンにもカードにも当たらない所をクリックする。"""
        self.input.click_at(0, 0)
        self.core.update()

    def raise_twice(self):
        self.click_button(RAISE_BUTTON_X)
        self.click_button(RAISE_BUTTON_X)

    def drawn(self):
        self.view.calls.clear()
        self.core.draw()
        return list(self.view.calls)

    def coins(self):
        # pylint: disable=W0212
        return [p.coins for p in self.core._table.players]

    def test_click_after_finish_starts_next_game_carrying_coins_and_pot(self):
        """FR7.2: 終了後のクリックで次のゲームが始まり、所持コインとポットが引き継がれること"""
        self.raise_twice()
        # 各自の支払い = 参加費 1 + 1 回目 1 + 2 回目 2 = 4、ポット = 4 × 4 = 16
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        winner_coins = INITIAL_COINS - paid + paid * 4  # 10 - 4 + 16 = 22
        other_coins = INITIAL_COINS - paid  # 10 - 4 = 6
        expected = [other_coins] * 4
        expected[LOSE_WINNER_ROW] = winner_coins
        self.assertEqual(expected, self.coins())
        self.click_anywhere()
        # クリック直後 = 前のゲームの所持コイン - 次の参加費
        expected = [other_coins - ENTRY_FEE] * 4
        expected[LOSE_WINNER_ROW] = winner_coins - ENTRY_FEE
        self.assertEqual(expected, self.coins())
        # pylint: disable=W0212
        game = self.core._game
        # 勝者がポットを受け取った後は 0 なので、ポット = 次の参加費 1 × 4
        self.assertEqual(ENTRY_FEE * 4, game.pot.amount)
        self.assertEqual(Phase.FIRST_DECISION, game.phase)

    def test_click_after_finish_deals_new_hands_and_clears_marks(self):
        """FR7.3: 手札が変わり、ポップアップと勝者の枠が消え、選択と交換の状態が初期化されること"""
        # pylint: disable=W0212
        self.input.click_at(card_center_x(1), HUMAN_CARD_Y + CARD_HEIGHT // 2)
        self.core.update()
        self.raise_twice()
        old_hands = [list(p.hand) for p in self.core._table.players]
        self.assertTrue(self.core._table.players[3].exchanged)
        self.click_anywhere()
        players = self.core._table.players
        self.assertNotEqual(old_hands, [p.hand for p in players])
        self.assertEqual(
            [p.hand for p in Game.start(LOSE_SEED + 1).table.players],
            [p.hand for p in players],
        )
        human = players[3]
        self.assertFalse(human.exchanged)
        self.assertEqual([], human.selected_indices())
        self.assertEqual(set(), human.new_indices)
        # 勝者の枠もポップアップも無い、配札直後と同じ描画
        self.assertEqual(table_only_calls(self.core), self.drawn())

    def test_click_in_middle_of_game_does_not_advance(self):
        """FR7.1: ゲームの途中（1 回目・2 回目）のクリックでは次のゲームに進まないこと"""
        # pylint: disable=W0212
        game = self.core._game
        self.click_anywhere()
        self.assertIs(game, self.core._game)
        self.click_button(RAISE_BUTTON_X)
        self.click_anywhere()
        self.assertIs(game, self.core._game)
        self.assertEqual(Phase.SECOND_DECISION, game.phase)

    def test_one_click_advances_only_one_game(self):
        """FR7.1: 終了後の 1 回のクリックは次のゲームを始めるだけで、そのゲームのボタンを押さないこと"""
        # pylint: disable=W0212
        self.raise_twice()
        self.click_button(RAISE_BUTTON_X)
        game = self.core._game
        # Raise の上のクリックでも、新しいゲームは 1 回目の判断のまま（交換も支払いもしない）
        self.assertEqual(Phase.FIRST_DECISION, game.phase)
        self.assertFalse(self.core._table.players[3].exchanged)
        self.assertEqual(ENTRY_FEE * 4, game.pot.amount)

    def test_all_drop_has_no_popup_and_click_carries_pot_over(self):
        """FR6.1: 全員ドロップではポップアップが出ず、クリックで次へ進み、ポットが累積すること"""
        # pylint: disable=W0212
        self.core._game.com_action = lambda index: Action.DROP
        self.click_button(DROP_BUTTON_X)
        self.assertEqual(Phase.FINISHED, self.core._game.phase)
        # 全員ドロップ: 4 段すべてに帯があり、ポップアップは無く、ポットは持ち越しの 4（= 参加費 1 × 4）
        self.assertEqual(table_only_calls(self.core), self.drawn())
        self.click_anywhere()
        game = self.core._game
        # ポット = 持ち越し 参加費 4 + 次の参加費 4 = 8、各自の所持コイン = 10 - 1 - 1
        self.assertEqual(ENTRY_FEE * 4 * 2, game.pot.amount)
        self.assertEqual([INITIAL_COINS - ENTRY_FEE * 2] * 4, self.coins())

    def test_seed_increments_each_game(self):
        """FR7.2: 種が 1 ゲームごとに 1 ずつ増えること（最初のゲームは seed のまま）"""
        # pylint: disable=W0212
        for step in (1, 2):
            # 全員ドロップでゲームを終えてから、クリックで次のゲームへ進む
            self.core._game.com_action = lambda index: Action.DROP
            self.click_button(DROP_BUTTON_X)
            self.click_anywhere()
            self.assertEqual(
                [p.hand for p in Game.start(LOSE_SEED + step).table.players],
                [p.hand for p in self.core._table.players],
            )

    def test_seed_none_stays_none(self):
        """FR7.2: seed が None のときは、次のゲームの種も None であること"""
        # pylint: disable=W0212
        core = GameCore(input=self.input, view=self.view)
        core._game.com_action = lambda index: Action.DROP
        self.input.click_at(*button_center(DROP_BUTTON_X))
        core.update()
        finished = core._game
        with patch.object(
            Game, "next_game", autospec=True, side_effect=Game.next_game
        ) as mock_next:
            self.input.click_at(0, 0)
            core.update()
        mock_next.assert_called_once_with(finished, None)


class TestPotDisplay(TestParent):
    """FR8.1、FR8.2: 画面にポットの額（POT n）と、ドロップした段の帯が出る（期待値は計算式で出す）。"""

    def setUp(self):
        super().setUp()
        self.input = FakeInput()
        self.core = GameCore(input=self.input, view=self.view, seed=LOSE_SEED)

    def click_button(self, button_x):
        self.input.click_at(*button_center(button_x))
        self.core.update()

    def drawn(self):
        self.view.calls.clear()
        self.core.draw()
        return list(self.view.calls)

    def pot_texts(self):
        """描画の中の "POT n" の文字だけ"""
        return [c[3] for c in self.drawn() if c[0] == "text" and c[3].startswith("POT")]

    def hand_rows(self):
        """カードを描いた段の位置（0 始まり）。カードの背景（rect 14x20）の上端から段を引き当てる。"""
        offset = (ROW_PITCH - CARD_HEIGHT) // 2
        tops = {
            c[2]
            for c in self.drawn()
            if c[0] == "rect" and c[3:5] == (CARD_WIDTH, CARD_HEIGHT)
        }
        return [i for i in range(4) if row_top(i) + offset in tops]

    def hidden_rows(self):
        """手札を描かない段（ドロップした段）の位置。"""
        shown = self.hand_rows()
        return [i for i in range(4) if i not in shown]

    def pot_call(self):
        """描画の中の "POT n" の text 呼び出し（無ければ None）。"""
        return next(
            (c for c in self.drawn() if c[0] == "text" and c[3].startswith("POT")),
            None,
        )

    def popup_texts(self):
        """ポップアップの文字（位置 x, y と内容）。ポップアップの塗り（黒の rect）の後に描かれる text。"""
        calls = self.drawn()
        fill_at = next(
            (
                i
                for i, c in enumerate(calls)
                if c[0] == "rect" and c[5] == 0 and c[3] == POPUP_WIDTH
            ),
            None,
        )
        if fill_at is None:
            return []
        return [c[3] for c in calls[fill_at:] if c[0] == "text"]

    def test_pot_shown_right_after_start(self):
        """FR8.1: 起動直後は参加費 ENTRY_FEE × 4 のポットが出る"""
        # ポット = 参加費 1 × 4 人 = 4
        self.assertEqual([f"POT {ENTRY_FEE * 4}"], self.pot_texts())

    def test_pot_grows_after_everyone_raises(self):
        """FR8.1: 1 回目に全員がレイズすると、ポットの表示が追加額の分だけ増える"""
        self.click_button(RAISE_BUTTON_X)
        # ポット = 4 + raise_cost(1) × 4 人 = 4 + 1 × 4 = 8
        self.assertEqual([f"POT {ENTRY_FEE * 4 + raise_cost(1) * 4}"], self.pot_texts())

    def test_pot_text_is_centered_in_top_band(self):
        """FR8.1: ポットの額は帯の水平・垂直の中央に描かれる"""
        # "POT 4" = 5 文字 * 4 - 1 = 19 → x = 25 + (100 - 19) // 2 = 65、y = 8 + (24 - 5) // 2 = 17
        message = f"POT {ENTRY_FEE * 4}"
        text_width = CHAR_WIDTH * len(message) - 1
        expected = (
            "text",
            POPUP_X + (POPUP_WIDTH - text_width) // 2,
            POPUP_Y + (POPUP_HEIGHT - CHAR_HEIGHT) // 2,
            message,
            7,
        )
        self.assertEqual(expected, self.pot_call())

    def test_pot_not_drawn_while_popup_is_shown(self):
        """FR8.3: ポップアップが出ている間は、ポットの額を描かない（ポップアップに置き換わる）"""
        for seed in (LOSE_SEED, WIN_SEED):
            with self.subTest(seed=seed):
                core = GameCore(input=self.input, view=self.view, seed=seed)
                self.core = core
                self.click_button(RAISE_BUTTON_X)
                self.click_button(RAISE_BUTTON_X)
                self.assertIsNone(self.pot_call())
                self.assertNotEqual([], self.popup_texts())

    def test_pot_text_drawn_after_table(self):
        """FR8.1: 描画の順は 盤面 → ポットの額（ポップアップが無いとき）"""
        calls = self.drawn()
        pot_at = next(
            i for i, c in enumerate(calls) if c[0] == "text" and c[3][:3] == "POT"
        )
        buttons_end = max(i for i, c in enumerate(calls) if c[0] == "blt")
        self.assertLess(buttons_end, pot_at)

    def test_pot_drawn_when_finished_without_winner(self):
        """FR8.1: 全員ドロップ（勝者なし、ポップアップなし）で終了したときも、ポットの額を描く"""
        self.core._game.com_action = lambda index: Action.DROP  # pylint: disable=W0212
        self.click_button(DROP_BUTTON_X)
        self.assertEqual(Phase.FINISHED, self.core._game.phase)  # pylint: disable=W0212
        self.assertEqual([f"POT {ENTRY_FEE * 4}"], self.pot_texts())
        self.assertEqual([], self.popup_texts())

    def test_win_popup_shows_win_and_got_pot_amount(self):
        """FR4.1: 人間が勝つと、ポップアップに WIN と GOT N（N = 受け取ったポット）が出る"""
        core = GameCore(input=self.input, view=self.view, seed=WIN_SEED)
        self.core = core
        core._game.com_action = lambda index: Action.RAISE  # pylint: disable=W0212
        # COM は交換で引くので、人間が勝つ手札を固定する（山札の並びに頼らない）
        # pylint: disable-next=W0212
        core._game.table.players[HUMAN_ROW].hand = list(ROYAL_HAND)
        self.click_button(RAISE_BUTTON_X)
        self.click_button(RAISE_BUTTON_X)
        # 全員が参加費 1 + 1 回目 1 + 2 回目 2 = 4 を払う → ポット = 4 * 4 = 16
        paid = ENTRY_FEE + raise_cost(1) + raise_cost(2)
        self.assertEqual(["WIN", f"GOT {paid * 4}"], self.popup_texts())
        self.assertEqual("GOT 16", self.popup_texts()[1])

    def test_lose_popup_shows_only_lose(self):
        """FR4.1: COM が勝つと、ポップアップは LOSE だけ"""
        self.click_button(RAISE_BUTTON_X)
        self.click_button(RAISE_BUTTON_X)
        self.assertEqual(["LOSE"], self.popup_texts())

    def test_dropped_rows_hide_cards_in_game(self):
        """FR8.2: ドロップした段は手札が描かれず、残りの段は描かれる。次のゲームで戻る"""
        self.assertEqual([], self.hidden_rows())
        # 人間が 1 回目にドロップ: COM の既定の判断はレイズなので、人間の段（位置 3）だけ
        self.click_button(DROP_BUTTON_X)
        self.assertEqual([3], self.hidden_rows())
        self.input.click_at(0, 0)
        self.core.update()
        self.assertEqual([], self.hidden_rows())

    def test_all_drop_hides_all_cards_and_carries_pot_over(self):
        """FR8.1、FR8.2: 全員ドロップで手札が全段で消え、次のゲームでは手札が戻りポットが持ち越される"""
        self.core._game.com_action = lambda index: Action.DROP  # pylint: disable=W0212
        self.click_button(DROP_BUTTON_X)
        self.assertEqual([0, 1, 2, 3], self.hidden_rows())
        # 勝者がいないのでポットは受け取られず、4（= 参加費 1 × 4）のまま
        self.assertEqual([f"POT {ENTRY_FEE * 4}"], self.pot_texts())
        self.input.click_at(0, 0)
        self.core.update()
        self.assertEqual([], self.hidden_rows())
        # ポット = 持ち越し 4 + 次の参加費 4 = 8
        self.assertEqual([f"POT {ENTRY_FEE * 4 * 2}"], self.pot_texts())


class TestScreenSize(unittest.TestCase):
    def test_screen_size(self):
        """FR2.1: 画面の大きさが幅 150 × 高さ 200 であること"""
        self.assertEqual((150, 200), (SCREEN_WIDTH, SCREEN_HEIGHT))
