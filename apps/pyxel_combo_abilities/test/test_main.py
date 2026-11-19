import copy
import random
import sys
import unittest
from unittest.mock import MagicMock, patch
from test.fake_view import FakeView
from src import drawing, screen
from src.field import Field
from src.game import AttackStep, ComboAbilitiesGame
from src.main import App, GameCore, PyxelView
from src.resource import Component, Resource


def seeded_rand():
    """乱数を固定する（定数を返す乱数では、攻撃の繰り返しが終わらないことがある）。"""
    return random.Random(1).random


def bar_fill_width(calls):
    """描画の呼び出しから、残りターンのバーの四角の幅を求める（描かれていなければ 0）。"""
    ix, iy, _, ih = screen.turn_bar_inner_rect()
    widths = [
        c[3]
        for c in calls
        if c[0] == "fill_rect"
        and c[5] == screen.TURN_BAR_FILL_COLOR
        and c[1:3] == (ix, iy)
        and c[4] == ih
    ]
    return widths[0] if widths else 0


def expected_bar_width(turn):
    """ターン turn のときの、バーの四角の幅の期待値（内側の幅 × 残りターン ÷ (最大ターン − 1)）。"""
    iw = screen.turn_bar_inner_rect()[2]
    return (
        iw * (ComboAbilitiesGame.MAX_TURN - turn) // (ComboAbilitiesGame.MAX_TURN - 1)
    )


def outline_calls(pos):
    """アイコンの左上 pos を囲む、赤い 1 ピクセルの枠線（上・下・左・右の辺）の fill_rect。"""
    x, y = pos
    size, color = screen.ICON_SIZE, screen.SELECTOR_COLOR
    return [
        ("fill_rect", x, y, size, 1, color),
        ("fill_rect", x, y + size - 1, size, 1, color),
        ("fill_rect", x, y + 1, 1, size - 2, color),
        ("fill_rect", x + size - 1, y + 1, 1, size - 2, color),
    ]


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = FakeView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        self.patcher_view.stop()


class TestGameCoreDraw(TestParent):
    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())
        self.core.draw()
        self.calls = self.test_view.calls

    def test_draw_table_background_then_table_elements(self):
        """FR7.1: テーブル領域を灰色で塗ってから、テーブルの要素を描く"""
        table_bg = ("fill_rect", 0, 96, 180, 224, 5)  # 画面の下 70%、濃い灰色（5）
        panel = ("fill_rect", *PANEL_RECT, 13)  # パネルは色 13
        self.assertIn(table_bg, self.calls)
        self.assertIn(panel, self.calls)
        self.assertLess(self.calls.index(table_bg), self.calls.index(panel))

    def test_draw_field_elements(self):
        """FR7.1: フィールドの背景・自機・敵を描く"""
        field_bg = ("fill_rect", 0, 0, screen.SCREEN_W, screen.FIELD_H, 1)
        self.assertIn(field_bg, self.calls)
        ship = self.test_view.image_at(screen.SHIP_X, screen.SHIP_Y)
        self.assertIsNotNone(ship)
        for pos in self.core.enemy_positions:
            self.assertIsNotNone(self.test_view.image_at(*pos), pos)

    def test_status_reflects_game_state(self):
        """FR1.1・FR2.2: レベルは文字で描かず、ターン数は残りターンのバーの長さで表示する"""
        game = self.core.game
        self.assertEqual(1, game.turn)
        self.assertEqual(
            screen.turn_bar_inner_rect()[2], bar_fill_width(self.calls)
        )  # 開始時は満タン
        self.assertEqual([], [c for c in self.calls if c[0] == "draw_text"])
        self.assertEqual(expected_bar_width(game.turn), bar_fill_width(self.calls))
        self.test_view.calls.clear()
        game.level = 7
        game.turn = 4
        self.core.draw()
        self.assertEqual([], [c for c in self.test_view.calls if c[0] == "draw_text"])
        self.assertEqual(expected_bar_width(4), bar_fill_width(self.test_view.calls))

    def test_execute_button_is_drawn(self):
        """FR7.1: 決定ボタンを描く"""
        x, y = screen.button_icon_pos()
        u, v = screen.ICON_UV["execute"]
        button = ("blt", x, y, u, v, screen.ICON_CELL, screen.ICON_CELL, 0)
        self.assertIn(button, self.calls)


PANEL_RECT = (screen.PANEL_X, screen.PANEL_Y, screen.PANEL_W, screen.PANEL_H)


class TestGameCoreInput(TestParent):
    """クリックの取得と、判定・操作・選択の描画への接続（FR1・FR3.4）。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())

    def _click(self, x, y):
        """(x, y) のクリックを仕込んで update を 1 フレーム進める。"""
        self.test_view.queue_click(x, y)
        self.core.update()

    def _center(self, pos):
        """アイコンの左上 pos から、領域の中心の座標。"""
        return pos[0] + screen.ICON_SIZE // 2, pos[1] + screen.ICON_SIZE // 2

    def _selector_calls(self):
        """draw したときの、選択を表す赤い枠線（4 辺）の fill_rect の呼び出し。"""
        self.test_view.calls.clear()
        self.core.draw()
        return [
            c
            for c in self.test_view.calls
            if c[0] == "fill_rect" and c[-1] == screen.SELECTOR_COLOR
        ]

    def test_no_click_changes_nothing(self):
        """クリックのないフレームでは、何も起きない（選択も攻撃もない）。"""
        turn = self.core.game.turn
        self.core.update()
        self.assertEqual(self.core.game.turn, turn)
        self.assertEqual(self._selector_calls(), [])

    def test_click_box_draws_selector(self):
        """枠をクリックすると、その枠に赤い四角の枠線が重なる（塗りつぶさない）。"""
        pos = screen.box_pos(Component.ENGINE, 0)
        self._click(*self._center(pos))
        self.assertEqual(self._selector_calls(), outline_calls(pos))
        self.assertFalse([c for c in self.test_view.calls if c[0] == "set_alpha"])

    def test_second_click_swaps_and_clears_selector(self):
        """ストックの枠 → 部品の枠の順にクリックすると、入れ替わり、赤い四角が消える。"""
        garage = self.core.game.garage
        garage.boxes[Component.STOCK] = [Resource.THINGS_BRONZE] + [None] * 4
        self._click(*self._center(screen.stock_pos(0)))
        self._click(*self._center(screen.box_pos(Component.ENGINE, 0)))
        self.assertEqual(garage.boxes[Component.ENGINE][0], Resource.THINGS_BRONZE)
        self.assertEqual(self._selector_calls(), [])

    def test_click_button_advances_turn(self):
        """決定ボタンをクリックすると、ターンが 1 進み、再生が終わった画面のターン表示に反映される。"""
        game = self.core.game
        turn = game.turn
        self._click(screen.BUTTON_X, screen.BUTTON_Y)
        self.assertEqual(game.turn, turn + 1)
        for _ in range(1000):  # 表示は、再生が終わるまで攻撃前のまま（ID-010）
            if not self.core.attacking:
                break
            self.core.update()
        self.test_view.calls.clear()
        self.core.draw()
        self.assertEqual(
            expected_bar_width(turn + 1), bar_fill_width(self.test_view.calls)
        )

    def test_click_empty_area_ignored(self):
        """どれにも当たらない場所のクリックは、何も起こさない。"""
        turn = self.core.game.turn
        self._click(0, 0)
        self.assertEqual(self.core.game.turn, turn)
        self.assertEqual(self._selector_calls(), [])


class TestGameCoreAttack(TestParent):
    """ID-008: 決定ボタンで攻撃の再生が始まり、再生中は操作を受け付けず、発射と爆発を描く。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())

    def _click(self, x, y):
        self.test_view.queue_click(x, y)
        self.core.update()

    def _start_attack(self):
        self._click(screen.BUTTON_X, screen.BUTTON_Y)

    def _tick(self, frames):
        for _ in range(frames):
            self.core.update()

    def _draw_calls(self):
        self.test_view.calls.clear()
        self.core.draw()
        return list(self.test_view.calls)

    def test_button_starts_attack(self):
        """FR2.1: 決定ボタンをクリックすると、攻撃中になる。"""
        self.assertFalse(self.core.attacking)
        self._start_attack()
        self.assertTrue(self.core.attacking)

    def test_clicks_ignored_while_attacking(self):
        """FR5: 攻撃中は、枠もボタンもクリックしても何も起こらず、選択も変わらない。"""
        self._start_attack()
        turn = self.core.game.turn
        box = screen.box_pos(Component.ENGINE, 0)
        self._click(box[0] + 1, box[1] + 1)
        self._click(screen.BUTTON_X, screen.BUTTON_Y)
        self.assertIsNone(self.core.operation.selected)
        self.assertEqual(self.core.game.turn, turn)
        self.assertTrue(self.core.attacking)

    def test_returns_to_adjusting_after_frames(self):
        """FR2.2: 再生が終わると、操作を受け付ける状態に戻る。"""
        self._start_attack()
        for _ in range(1000):
            if not self.core.attacking:
                break
            self.core.update()
        self.assertFalse(self.core.attacking)
        box = screen.box_pos(Component.ENGINE, 0)
        self._click(box[0] + 1, box[1] + 1)
        self.assertEqual(self.core.operation.selected, (Component.ENGINE, 0))

    def test_zero_kill_turn_is_not_animated(self):
        """FR3.2: 破壊数 0 の攻撃だけなら、攻撃中にならない。"""
        self.core.operation.click = lambda target: [AttackStep(0, False)]
        self._start_attack()
        self.assertFalse(self.core.attacking)
        self.assertEqual(len(self.core.enemy_positions), Field.MAX_NPC_NUM)

    def test_laser_drawn_while_launching(self):
        """FR3.3: 発射中は、自機から右へレーザーが描かれる。"""
        self._start_attack()
        calls = self._draw_calls()
        y = screen.SHIP_Y + screen.ENEMY_SIZE // 2
        laser = (
            "draw_line",
            screen.SHIP_X + screen.ENEMY_SIZE,
            y,
            screen.SCREEN_W - 1,
            y,
            screen.LASER_COLOR,
        )
        self.assertIn(laser, calls)

    def test_explosion_drawn_while_exploding(self):
        """FR3.3: 爆発中は、消える敵の位置に爆発が描かれ、レーザーは描かれない。"""
        self._start_attack()
        self._tick(screen.LAUNCH_FRAMES)
        anim = self.core.animation
        self.assertEqual(anim.phase, "explode")
        calls = self._draw_calls()
        for x, y in anim.exploding:
            center = (x + screen.ENEMY_SIZE // 2, y + screen.ENEMY_SIZE // 2)
            expect = ("fill_circ", *center, screen.EXPLOSION_R, screen.EXPLOSION_COLOR)
            self.assertIn(expect, calls)
        self.assertFalse([c for c in calls if c[-1] == screen.LASER_COLOR])

    def test_table_background_drawn_over_explosion(self):
        """要件 4-3: テーブルの背景は爆発の上に描かれ、爆発がテーブルにはみ出さない。"""
        self._start_attack()
        self._tick(screen.LAUNCH_FRAMES)
        calls = self._draw_calls()
        table_bg = (
            "fill_rect",
            0,
            screen.TABLE_Y,
            screen.SCREEN_W,
            screen.TABLE_H,
            screen.TABLE_COLOR,
        )
        explosions = [i for i, c in enumerate(calls) if c[0] == "fill_circ"]
        self.assertTrue(explosions)
        self.assertGreater(calls.index(table_bg), max(explosions))

    def test_field_shows_animated_enemies(self):
        """FR4.1: 再生中のフィールドは、再生中の敵の位置（爆発で減った数）で描かれる。"""
        self._start_attack()
        self._tick(screen.LAUNCH_FRAMES)
        anim = self.core.animation
        self.assertLess(len(anim.positions), Field.MAX_NPC_NUM)
        calls = self._draw_calls()
        for pos in anim.positions:
            self.assertIsNotNone(self.test_view.image_at(*pos), pos)
        self.assertFalse(
            [
                c
                for c in calls
                if c[0] != "fill_circ" and c[-1] == screen.EXPLOSION_COLOR
            ]
        )


class TestGameOver(TestParent):
    """ID-009: ターン数が最大で再生が終わったらゲームオーバー。メニューを描き、操作を受け付けない。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())

    def _draw_texts(self):
        self.test_view.calls.clear()
        self.core.draw()
        return [c[3] for c in self.test_view.calls if c[0] == "draw_text"]

    def test_game_over_only_when_last_turn_and_not_attacking(self):
        """FR1.1: ターン数が最大でも、再生中はゲームオーバーにならない。再生が終われば、なる。"""
        game = self.core.game
        self.assertFalse(self.core.game_over)  # ターン 1
        game.turn = game.MAX_TURN
        self.core.animation = object()  # 再生中
        self.assertFalse(self.core.game_over)
        self.core.animation = None
        self.assertTrue(self.core.game_over)

    def test_game_over_after_playing_the_last_attack(self):
        """FR1.1: 最後のターンの攻撃を再生し終えたときに、ゲームオーバーになる。"""
        game = self.core.game
        game.turn = game.MAX_TURN - 1
        self.test_view.queue_click(screen.BUTTON_X, screen.BUTTON_Y)
        self.core.update()
        for _ in range(1000):
            if not self.core.attacking:
                break
            self.core.update()
        self.assertTrue(game.is_end())
        self.assertTrue(self.core.game_over)

    def test_menu_drawn_only_on_game_over(self):
        """FR2.1: メニューは、ゲームオーバーのときだけ描く。撃破数は合計を表示する。"""
        self.assertNotIn("Game Over", self._draw_texts())
        game = self.core.game
        game.turn = game.MAX_TURN
        game.kills = 42
        texts = self._draw_texts()
        self.assertIn("Game Over", texts)
        self.assertIn("Kills: 42", texts)
        self.assertIn("New Game", texts)

    def test_clicks_ignored_on_game_over(self):
        """FR1.2: ゲームオーバーの間は、枠も決定ボタンもクリックしても何も起こらない。"""
        game = self.core.game
        game.turn = game.MAX_TURN
        box = screen.box_pos(Component.ENGINE, 0)
        for x, y in ((box[0] + 1, box[1] + 1), (screen.BUTTON_X, screen.BUTTON_Y)):
            self.test_view.queue_click(x, y)
            self.core.update()
        self.assertIsNone(self.core.operation.selected)
        self.assertEqual(game.turn, game.MAX_TURN)
        self.assertFalse(self.core.attacking)


class TestTurnEndDisplay(TestParent):
    """ID-010: 攻撃中は、ターンの終わり（再生の終わり）まで、攻撃前の表示のままにする。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())
        game = self.core.game
        self.before = (copy.deepcopy(game.garage), game.turn)

    def _table_calls(self, garage, turn):
        """テーブルを、指定した値で描いたときの描画の呼び出し（期待値）。"""
        view = FakeView()
        drawing.draw_table(view, garage, turn, ComboAbilitiesGame.MAX_TURN)
        return view.calls

    def _drawn(self):
        self.test_view.calls.clear()
        self.core.draw()
        return list(self.test_view.calls)

    def _click_button(self):
        self.test_view.queue_click(screen.BUTTON_X, screen.BUTTON_Y)
        self.core.update()

    def _play_until_done(self):
        for _ in range(1000):
            if not self.core.attacking:
                return
            self.core.update()
        self.fail("攻撃の再生が終わらない")

    def _after(self):
        game = self.core.game
        return self._table_calls(game.garage, game.turn)

    def test_table_keeps_pre_attack_values_while_attacking(self):
        """FR2: 再生中のターン数（バー）・ストック・部品は、攻撃前の値で描かれる。"""
        before_calls = self._table_calls(*self.before)
        self._click_button()
        self.assertTrue(self.core.attacking)
        # この乱数では、攻撃の前後で表示が変わる（変わらなければ、このテストは意味がない）
        self.assertNotEqual(before_calls, self._after())
        drawn = self._drawn()
        for call in before_calls:
            self.assertIn(call, drawn)
        self.assertEqual([], [c for c in drawn if c[0] == "draw_text"])

    def test_table_updates_when_attack_ends(self):
        """FR2: 再生が終わった時点で、更新後の値になる。"""
        self._click_button()
        self._play_until_done()
        drawn = self._drawn()
        for call in self._after():
            self.assertIn(call, drawn)
        self.assertEqual(expected_bar_width(self.before[1] + 1), bar_fill_width(drawn))

    def test_selection_kept_while_attacking_and_cleared_at_the_end(self):
        """FR4: 決定ボタンの後も、再生が終わるまで選択の赤い四角を残す。終わったら解除する。"""
        pos = screen.box_pos(Component.ENGINE, 0)
        self.test_view.queue_click(pos[0] + 1, pos[1] + 1)
        self.core.update()
        selector = outline_calls(pos)[0]
        self._click_button()
        self.assertTrue(self.core.attacking)
        self.assertIn(selector, self._drawn())
        self._play_until_done()
        self.assertNotIn(selector, self._drawn())
        self.assertIsNone(self.core.operation.selected)

    def test_zero_kill_turn_shows_updated_values_at_once(self):
        """FR2.2: 再生のない攻撃（破壊数 0）は、押したフレームで更新後の値になり、選択も解除される。"""
        operation = self.core.operation
        real_click = operation.click
        operation.click = lambda target: (real_click(target), [AttackStep(0, False)])[1]
        pos = screen.box_pos(Component.ENGINE, 0)
        self.test_view.queue_click(pos[0] + 1, pos[1] + 1)
        self.core.update()
        self._click_button()
        self.assertFalse(self.core.attacking)
        drawn = self._drawn()
        for call in self._after():
            self.assertIn(call, drawn)
        self.assertIsNone(operation.selected)

    def test_last_turn_shows_final_values_and_menu_after_playback(self):
        """FR2.3: ターン 10 に達する攻撃も、再生中は攻撃前の値。終わったら更新後の値とメニュー。"""
        game = self.core.game
        game.turn = game.MAX_TURN - 1
        self._click_button()
        self.assertTrue(self.core.attacking)
        drawn = self._drawn()
        self.assertEqual(expected_bar_width(game.MAX_TURN - 1), bar_fill_width(drawn))
        self.assertNotIn("Game Over", [c[3] for c in drawn if c[0] == "draw_text"])
        self._play_until_done()
        drawn = self._drawn()
        self.assertEqual(0, bar_fill_width(drawn))  # ターン 10 で四角の長さは 0
        self.assertIn("Game Over", [c[3] for c in drawn if c[0] == "draw_text"])


class TestEnemyReplace(TestParent):
    """ID-010: ターンの終わりに敵を置き直し、次の攻撃は待機中の敵の位置から始める。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())

    def _click_button(self):
        self.test_view.queue_click(screen.BUTTON_X, screen.BUTTON_Y)
        self.core.update()

    def _play_until_done(self):
        for _ in range(1000):
            if not self.core.attacking:
                return
            self.core.update()
        self.fail("攻撃の再生が終わらない")

    def _drawn_enemies(self, positions):
        """待機中・再生中の draw に、positions の敵の画像がすべてあるか。"""
        self.test_view.calls.clear()
        self.core.draw()
        return all(self.test_view.image_at(*pos) is not None for pos in positions)

    def test_idle_shows_max_enemies_after_the_turn(self):
        """FR3: 再生が終わった待機中は、敵が最大数（10）ある（残りの数ではない）。"""
        self._click_button()
        anim = self.core.animation
        self._play_until_done()
        self.assertLess(len(anim.positions), Field.MAX_NPC_NUM)  # 再生の終わりの残り
        self.assertEqual(len(self.core.enemy_positions), Field.MAX_NPC_NUM)
        self.assertTrue(self._drawn_enemies(self.core.enemy_positions))

    def test_next_attack_starts_from_the_idle_positions(self):
        """FR3.2: 次の攻撃は、待機中に表示していた位置の敵から始まる（開始時に位置が変わらない）。"""
        idle = list(self.core.enemy_positions)
        self._click_button()
        self.assertEqual(self.core.animation.positions, idle)
        self.assertTrue(self._drawn_enemies(idle))

    def test_game_over_keeps_the_remaining_enemies(self):
        """FR3.1: ゲームオーバーになる攻撃の後は、置き直さず、残った敵を表示する。"""
        game = self.core.game
        game.turn = game.MAX_TURN - 1
        self._click_button()
        remaining = self.core.animation
        self._play_until_done()
        self.assertTrue(self.core.game_over)
        self.assertEqual(self.core.enemy_positions, remaining.positions)
        self.assertLess(len(self.core.enemy_positions), Field.MAX_NPC_NUM)

    def test_level_up_turn_also_ends_with_max_enemies(self):
        """FR3: レベルが上がった攻撃でも、再生が終わった待機中は敵が最大数ある。"""
        operation = self.core.operation
        real_click = operation.click
        operation.click = lambda target: (
            real_click(target),
            [AttackStep(Field.MAX_NPC_NUM, True)],
        )[1]
        self._click_button()
        self._play_until_done()
        self.assertEqual(len(self.core.enemy_positions), Field.MAX_NPC_NUM)


class TestNewGame(TestParent):
    """ID-009: ゲームオーバーで New Game をタップすると、すべての状態を初期化して最初から始める。"""

    def setUp(self):
        super().setUp()
        self.core = GameCore(rand=seeded_rand())
        game = self.core.game
        game.turn = game.MAX_TURN
        game.kills = 99
        game.level = 7
        self.core.operation.selected = (Component.ENGINE, 0)
        self.core.enemy_positions = [(0, 0)]

    def _click_new_game(self):
        x, y, w, h = screen.NEW_GAME_RECT
        self.test_view.queue_click(x + w // 2, y + h // 2)
        self.core.update()

    def test_new_game_resets_everything(self):
        """FR3.1・FR3.2: レベル・撃破数・ターンの初期値、選択・敵の位置・再生の初期化。"""
        self._click_new_game()
        game = self.core.game
        self.assertEqual(game.turn, 1)  # 開始時の自動攻撃を 1 回行ったあと
        self.assertNotEqual(game.kills, 99)  # 前のゲームの撃破数を持ち越さない
        self.assertNotEqual(game.level, 7)  # 前のゲームのレベルを持ち越さない
        self.assertIsNone(self.core.operation.selected)
        self.assertIsNone(self.core.animation)
        self.assertEqual(len(self.core.enemy_positions), Field.MAX_NPC_NUM)

    def test_new_game_returns_to_adjusting(self):
        """FR3.3: 初期化後は調整中になり、メニューは出ず、操作を受け付ける。"""
        self._click_new_game()
        self.assertFalse(self.core.game_over)
        self.test_view.calls.clear()
        self.core.draw()
        texts = [c[3] for c in self.test_view.calls if c[0] == "draw_text"]
        self.assertNotIn("Game Over", texts)
        self.test_view.queue_click(screen.BUTTON_X, screen.BUTTON_Y)
        self.core.update()
        self.assertEqual(self.core.game.turn, 2)

    def test_click_outside_button_does_nothing(self):
        """FR4: ボタンの外のタップは、何も起こさない。"""
        x, y, _, _ = screen.NEW_GAME_RECT
        self.test_view.queue_click(x - 1, y - 1)
        self.core.update()
        self.assertEqual(self.core.game.kills, 99)
        self.assertTrue(self.core.game_over)

    def test_button_position_ignored_when_not_game_over(self):
        """FR4: ゲームオーバー以外では、ボタンの位置をタップしても何も起こらない。"""
        self.core.game.turn = 3
        self.core.game.kills = 5
        self._click_new_game()
        self.assertEqual((self.core.game.turn, self.core.game.kills), (3, 5))


class TestPyxelViewMouse(unittest.TestCase):
    """PyxelView.mouse_click は、左ボタンが押されたフレームだけ座標を返す（FR1）。"""

    def _view(self, pressed):
        fake_pyxel = MagicMock()
        fake_pyxel.btnp.return_value = pressed
        fake_pyxel.mouse_x = 12
        fake_pyxel.mouse_y = 34
        with patch.dict(sys.modules, {"pyxel": fake_pyxel}):
            return PyxelView(), fake_pyxel

    def test_pressed_returns_position(self):
        view, fake_pyxel = self._view(True)
        self.assertEqual(view.mouse_click(), (12, 34))
        fake_pyxel.btnp.assert_called_with(fake_pyxel.MOUSE_BUTTON_LEFT)

    def test_not_pressed_returns_none(self):
        view, _ = self._view(False)
        self.assertIsNone(view.mouse_click())


class TestFakeViewImage(unittest.TestCase):
    """FR5: FakeView は blt と pal の呼び出しを記録する。"""

    def test_blt_and_pal_are_recorded(self):
        view = FakeView()
        view.blt(10, 20, 8, 0, 16, 16, 0)
        view.pal(13, 8)
        view.pal()
        self.assertEqual(
            view.calls,
            [("blt", 10, 20, 8, 0, 16, 16, 0), ("pal", 13, 8), ("pal",)],
        )


class TestPyxelViewImage(unittest.TestCase):
    """FR5: PyxelView は blt を画像バンク 0 で pyxel.blt に、pal を pyxel.pal に渡す。"""

    def _view(self):
        fake_pyxel = MagicMock()
        with patch.dict(sys.modules, {"pyxel": fake_pyxel}):
            return PyxelView(), fake_pyxel

    def test_blt_uses_image_bank_0(self):
        view, fake_pyxel = self._view()
        view.blt(10, 20, 8, 0, 16, 16, 0)
        # pyxel.blt(x, y, img, u, v, w, h, colkey): img は 0
        fake_pyxel.blt.assert_called_once_with(10, 20, 0, 8, 0, 16, 16, 0)

    def test_pal_swaps_a_color(self):
        view, fake_pyxel = self._view()
        view.pal(13, 8)
        fake_pyxel.pal.assert_called_once_with(13, 8)

    def test_pal_without_arguments_resets(self):
        view, fake_pyxel = self._view()
        view.pal()
        fake_pyxel.pal.assert_called_once_with()


class TestApp(TestParent):
    def test_loads_icon_resource_after_init_before_run(self):
        """FR4: 起動時に icon.pyxres を、init の後・run の前に読み込む。"""
        fake_pyxel = MagicMock()
        with patch.dict(sys.modules, {"pyxel": fake_pyxel}):
            App()
        names = [c[0] for c in fake_pyxel.method_calls]
        fake_pyxel.load.assert_called_once_with(screen.RESOURCE_FILE)
        self.assertLess(names.index("init"), names.index("load"))
        self.assertLess(names.index("load"), names.index("run"))

    def test_init_uses_screen_size(self):
        """FR7.2: 画面サイズは 180 × 320"""
        fake_pyxel = MagicMock()
        with patch.dict(sys.modules, {"pyxel": fake_pyxel}):
            App()
        args, _ = fake_pyxel.init.call_args
        self.assertEqual((180, 320), args)
        self.assertEqual((screen.SCREEN_W, screen.SCREEN_H), args)
