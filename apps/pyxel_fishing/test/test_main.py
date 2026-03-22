import math
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import (  # pylint: disable=C0413
    IView,
    IInput,
    IFishView,
    GameCore,
    GameOverPopup,
    FishCatchPopup,
    PyxelController,
)
from fish import Fish, FishSize, FishRarity  # pylint: disable=C0413
from hook import Hook, HookState, BaitType  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_line(self, x1, y1, x2, y2, color):
        self.call_params.append(("draw_line", x1, y1, x2, y2, color))

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def draw_rectb(self, x, y, w, h, color):
        self.call_params.append(("draw_rectb", x, y, w, h, color))

    def draw_rect(self, x, y, w, h, color):
        self.call_params.append(("draw_rect", x, y, w, h, color))

    def get_frame(self) -> int:
        return 0

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    def __init__(self):
        self._mouse_pressed = False
        self._mouse_held = False
        self._mouse_x = 0
        self._mouse_y = 0

    def is_mouse_btn_pressed(self) -> bool:
        return self._mouse_pressed

    def is_mouse_btn_held(self) -> bool:
        return self._mouse_held

    def set_mouse_pressed(self, val: bool):
        self._mouse_pressed = val

    def set_mouse_held(self, val: bool):
        self._mouse_held = val

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y

    def set_mouse_pos(self, x: int, y: int):
        self._mouse_x = x
        self._mouse_y = y


class TestFishView(IFishView):
    def __init__(self):
        self.draw_calls = []

    def draw_fish(self, x, y, fish_size, vx, is_hit: bool):
        self.draw_calls.append(("draw_fish", x, y, fish_size, vx, is_hit))


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.test_input = TestInput()
        self.test_fish_view = TestFishView()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.patcher_fish_view = patch(
            "main.PyxelFishView.create", return_value=self.test_fish_view
        )
        self.mock_view = self.patcher_view.start()
        self.mock_input = self.patcher_input.start()
        self.mock_fish_view = self.patcher_fish_view.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()
        self.patcher_fish_view.stop()


class TestPyxelController(TestParent):
    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def test_screen_size(self):
        """画面サイズは幅240×高さ320px（縦長ポートレート）"""
        PyxelController()

        self.mock_pyxel.init.assert_called_once()
        call_args = self.mock_pyxel.init.call_args
        self.assertEqual(call_args[0][0], GameCore.SCREEN_WIDTH)
        self.assertEqual(call_args[0][1], GameCore.SCREEN_HEIGHT)


def _build_full_expected_calls(
    hook_pos=None,
    bait_type=BaitType.FLOAT_BAIT,
    charge_ratio=0.0,
    score=0,
    fatigue=GameCore.MAX_FATIGUE,
):
    """GameCore.draw() の完全な期待呼び出し列（描画順序込み）を構築する

    hook_pos: (x, y) - hook が描画される位置。None の場合（idle）は draw_line なし
    bait_type: 選択中えさ種類（強調枠の位置決定に使用）
    charge_ratio: 充電進捗割合（0.0〜1.0）。0.0 の場合はゲージ描画なし。1.0 で強調表示
    fatigue: 疲労値（デフォルト: MAX_FATIGUE）
    """
    tile_w, tile_h = 48, 96
    sprite_h = 8
    expected = []
    # 水上レイヤー（奥→手前: 背景→中景→前景）
    for u, x_offset in [(112, -32), (64, -16), (16, 0)]:
        col_count = math.ceil((GameCore.SCREEN_WIDTH - x_offset) / tile_w)
        for i in range(col_count):
            expected.append(
                ("draw_blt", x_offset + i * tile_w, 0, 0, u, 0, tile_w, tile_h, 0)
            )
    # 水面スプライト (u=16, v=96, w=48, h=8): y=WATER_Y、横 ceil(240/48)=5 枚
    ws_count = math.ceil(GameCore.SCREEN_WIDTH / 48)
    for i in range(ws_count):
        expected.append(
            ("draw_blt", i * 48, GameCore.WATER_Y, 0, 16, 96, 48, sprite_h, 0)
        )
    # 水中スプライト (u=16, v=104, w=48, h=8): y=WATER_Y+8 から 5列×27行
    col_count = math.ceil(GameCore.SCREEN_WIDTH / 48)  # = 5
    row_count = (
        GameCore.SCREEN_HEIGHT - GameCore.WATER_Y - sprite_h
    ) // sprite_h  # = 27
    for row in range(row_count):
        for col in range(col_count):
            expected.append(
                (
                    "draw_blt",
                    col * 48,
                    GameCore.WATER_Y + sprite_h * (row + 1),
                    0,
                    16,
                    104,
                    48,
                    sprite_h,
                    0,
                )
            )
    # 投擲地点スプライト: タイル座標(1,0)、THROW_Y=WATER_Y-TILE_SIZE（水面直上）
    expected.append(
        (
            "draw_blt",
            GameCore.THROW_X,
            GameCore.THROW_Y,
            0,
            GameCore.TILE_SIZE,
            0,
            GameCore.TILE_SIZE,
            GameCore.TILE_SIZE,
            0,
        )
    )
    # えさ種類ボタン（スプライト + 選択中のみ強調枠）
    for btn_bait_type, bx, by, sprite in [
        (
            BaitType.FLOAT_BAIT,
            GameCore.FLOAT_BAIT_BTN_X,
            GameCore.FLOAT_BAIT_BTN_Y,
            GameCore.FLOAT_BAIT_SPRITE,
        ),
        (BaitType.LURE, GameCore.LURE_BTN_X, GameCore.LURE_BTN_Y, GameCore.LURE_SPRITE),
    ]:
        expected.append(("draw_blt", bx, by, 0, *sprite, 0))
        if bait_type == btn_bait_type:
            expected.append(
                (
                    "draw_rectb",
                    bx,
                    by,
                    GameCore.BTN_SIZE,
                    GameCore.BTN_SIZE,
                    GameCore.SELECTED_BTN_COLOR,
                )
            )
    # スコア表示（背景・ボタン描画後）
    expected.append(("draw_text", GameCore.SCORE_X, GameCore.SCORE_Y, str(score)))
    # 釣り針線（hook_pos 指定時のみ: 待機以外の状態）投擲地点から釣り針位置への線
    if hook_pos is not None:
        expected.append(
            (
                "draw_line",
                GameCore.LINE_ORIGIN_X,
                GameCore.LINE_ORIGIN_Y,
                hook_pos[0],
                hook_pos[1],
                GameCore.HOOK_COLOR,
            )
        )
    # パワーゲージ（charge_ratio > 0.0 のみ: 背景 → 充填 → 枠の順）
    # 期待値: 背景=1（暗い青）、充填・枠=13（灰色）
    if charge_ratio > 0.0:
        gauge_h = max(1, int(charge_ratio * GameCore.GAUGE_MAX_H))
        gauge_top_y = GameCore.GAUGE_BOTTOM_Y - gauge_h
        gauge_full_top_y = GameCore.GAUGE_BOTTOM_Y - GameCore.GAUGE_MAX_H
        gauge_color = (
            GameCore.MAX_GAUGE_COLOR if charge_ratio >= 1.0 else GameCore.GAUGE_COLOR
        )
        # 背景（最大領域全体を暗い青=GAUGE_BG_COLOR で塗りつぶし）
        expected.append(
            (
                "draw_rect",
                GameCore.GAUGE_X,
                gauge_full_top_y,
                GameCore.GAUGE_W,
                GameCore.GAUGE_MAX_H,
                GameCore.GAUGE_BG_COLOR,
            )
        )
        # 充填（現在の充電量分を gauge_color で描画）
        expected.append(
            (
                "draw_rect",
                GameCore.GAUGE_X,
                gauge_top_y,
                GameCore.GAUGE_W,
                gauge_h,
                gauge_color,
            )
        )
        # 枠（最大領域を gauge_color で描画）
        expected.append(
            (
                "draw_rectb",
                GameCore.GAUGE_X,
                gauge_full_top_y,
                GameCore.GAUGE_W,
                GameCore.GAUGE_MAX_H,
                gauge_color,
            )
        )
    # 疲労ゲージ（外枠 → 内側の順）
    inner_w = int(fatigue / GameCore.MAX_FATIGUE * GameCore.FATIGUE_GAUGE_W)
    inner_x = GameCore.FATIGUE_GAUGE_X + GameCore.FATIGUE_GAUGE_W - inner_w
    expected.append(
        (
            "draw_rectb",
            GameCore.FATIGUE_GAUGE_X,
            GameCore.FATIGUE_GAUGE_Y,
            GameCore.FATIGUE_GAUGE_W,
            GameCore.FATIGUE_GAUGE_H,
            GameCore.FATIGUE_GAUGE_BG_COLOR,
        )
    )
    expected.append(
        (
            "draw_rect",
            inner_x,
            GameCore.FATIGUE_GAUGE_Y,
            inner_w,
            GameCore.FATIGUE_GAUGE_H,
            GameCore.FATIGUE_GAUGE_COLOR,
        )
    )
    return expected


def _append_fish(core, fish_size=FishSize.SMALL, n=1):
    """GameCore.fish_list に指定サイズの魚を n 匹追加する。"""
    for _ in range(n):
        core.fish_list.append(
            Fish(
                GameCore.WATER_Y + 20,
                GameCore.FISH_SPEED,
                fish_size,
                x_min=0,
                x_max=GameCore.SCREEN_WIDTH,
            )
        )


def _build_full_expected_fish_calls(fish_list):
    """GameCore.draw() の完全な期待魚描画呼び出し列を構築する

    fish_list: 描画対象の魚リスト（GameCore.fish_list）
    """
    return [
        ("draw_fish", fish.draw_x, fish.draw_y, fish.fish_size, fish.vx, fish.is_hit)
        for fish in fish_list
    ]


def _build_popup_expected_calls(rarity, fish_size, score):
    """FishCatchPopup.draw() の期待描画呼び出し列（描画順序込み）を構築する

    rarity: FishRarity - レア度（u 座標の決定に使用）
    fish_size: FishSize - サイズ（v 座標の決定に使用）
    score: int - ポップアップに表示するスコア
    """
    u = FishCatchPopup.RARITY_U[rarity]
    v = fish_size.value * FishCatchPopup.TILE_SIZE
    score_text = f"+{score}"
    # スコアテキストの水平中央座標（Pyxel フォント: 1文字=4px幅）
    score_x = FishCatchPopup.X + (FishCatchPopup.W - len(score_text) * 4) // 2
    return [
        (
            "draw_rect",
            FishCatchPopup.X,
            FishCatchPopup.Y,
            FishCatchPopup.W,
            FishCatchPopup.H,
            FishCatchPopup.BG_COLOR,
        ),
        (
            "draw_rectb",
            FishCatchPopup.X,
            FishCatchPopup.Y,
            FishCatchPopup.W,
            FishCatchPopup.H,
            FishCatchPopup.BORDER_COLOR,
        ),
        (
            "draw_blt",
            FishCatchPopup.FISH_X,
            FishCatchPopup.FISH_Y,
            1,
            u,
            v,
            FishCatchPopup.TILE_SIZE,
            FishCatchPopup.TILE_SIZE,
            0,
        ),
        (
            "draw_text",
            score_x,
            FishCatchPopup.SCORE_Y,
            score_text,
        ),
    ]


def _build_game_over_popup_expected_calls(score):
    """GameOverPopup.draw() の期待描画呼び出し列（描画順序込み）を構築する

    score: int - ゲームオーバー時の最終スコア
    """
    # タイトルテキストの水平中央座標（Pyxel フォント: 1文字=4px幅）
    title_x = (
        GameOverPopup.X + (GameOverPopup.W - len(GameOverPopup.TITLE_TEXT) * 4) // 2
    )
    score_text = f"Score: {score}"
    score_x = GameOverPopup.X + (GameOverPopup.W - len(score_text) * 4) // 2
    restart_x = (
        GameOverPopup.X + (GameOverPopup.W - len(GameOverPopup.RESTART_TEXT) * 4) // 2
    )
    return [
        (
            "draw_rect",
            GameOverPopup.X,
            GameOverPopup.Y,
            GameOverPopup.W,
            GameOverPopup.H,
            GameOverPopup.BG_COLOR,
        ),
        (
            "draw_rectb",
            GameOverPopup.X,
            GameOverPopup.Y,
            GameOverPopup.W,
            GameOverPopup.H,
            GameOverPopup.BORDER_COLOR,
        ),
        (
            "draw_text",
            title_x,
            GameOverPopup.TITLE_Y,
            GameOverPopup.TITLE_TEXT,
        ),
        (
            "draw_text",
            score_x,
            GameOverPopup.SCORE_Y,
            score_text,
        ),
        (
            "draw_text",
            restart_x,
            GameOverPopup.RESTART_Y,
            GameOverPopup.RESTART_TEXT,
        ),
    ]


class TestGameCore(TestParent):
    def test_hold_and_release_starts_throwing(self):
        """MIN_CHARGE_FRAMES 以上長押しして離すと、状態が「投擲中」になり初速度が設定される"""
        core = GameCore()
        self.test_input.set_mouse_held(True)
        for _ in range(Hook.MIN_CHARGE_FRAMES):
            core.update()
        self.test_input.set_mouse_held(False)
        core.update()
        self.assertEqual(core.hook.state, HookState.THROWING)
        self.assertNotEqual(core.hook._vx, 0)  # pylint: disable=W0212

    def test_draw(self):
        core = GameCore()
        core.draw()
        self.assertEqual(_build_full_expected_calls(), self.test_view.get_call_params())

    def test_click_bait_button_switches_bait_type(self):
        """えさ種類ボタン領域クリックでえさ種類が切り替わる"""
        cases = [
            (
                "ルアーボタン→ルアー",
                BaitType.FLOAT_BAIT,
                GameCore.LURE_BTN_X + 1,
                GameCore.LURE_BTN_Y + 1,
                BaitType.LURE,
            ),
            (
                "浮餌ボタン→浮餌",
                BaitType.LURE,
                GameCore.FLOAT_BAIT_BTN_X + 1,
                GameCore.FLOAT_BAIT_BTN_Y + 1,
                BaitType.FLOAT_BAIT,
            ),
        ]
        for desc, initial, click_x, click_y, expected in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                core.hook.set_bait_type(initial)
                self.test_input.set_mouse_pos(click_x, click_y)
                self.test_input.set_mouse_pressed(True)
                core.update()
                self.assertEqual(core.hook.bait_type, expected)

    def test_bait_button_boundary(self):
        """えさ種類ボタン境界値テスト（4隅の内側・外側クリック）"""
        # 座標エイリアス（テーブル整形のため）
        fbx = GameCore.FLOAT_BAIT_BTN_X  # = 8
        fby = GameCore.FLOAT_BAIT_BTN_Y  # = 296
        lbx = GameCore.LURE_BTN_X  # = 8
        lby = GameCore.LURE_BTN_Y  # = 276
        s = GameCore.BTN_SIZE  # = 16
        f = BaitType.FLOAT_BAIT
        l = BaitType.LURE
        # (説明, 初期えさ, クリックX, クリックY, 期待えさ)
        cases = [
            # 浮餌ボタン: 4隅の内側（→ FLOAT_BAIT に切り替わる）
            ("浮餌:左上隅内", l, fbx, fby, f),
            ("浮餌:右上隅内", l, fbx + s - 1, fby, f),
            ("浮餌:左下隅内", l, fbx, fby + s - 1, f),
            ("浮餌:右下隅内", l, fbx + s - 1, fby + s - 1, f),
            # 浮餌ボタン: 各隅に隣接する外側（→ えさ種類は変わらない）
            ("浮餌:左上隅の左外", l, fbx - 1, fby, l),
            ("浮餌:左上隅の上外", l, fbx, fby - 1, l),
            ("浮餌:右上隅の右外", l, fbx + s, fby, l),
            ("浮餌:左下隅の下外", l, fbx, fby + s, l),
            # ルアーボタン: 4隅の内側（→ LURE に切り替わる）
            ("ルアー:左上隅内", f, lbx, lby, l),
            ("ルアー:右上隅内", f, lbx + s - 1, lby, l),
            ("ルアー:左下隅内", f, lbx, lby + s - 1, l),
            ("ルアー:右下隅内", f, lbx + s - 1, lby + s - 1, l),
            # ルアーボタン: 各隅に隣接する外側（→ えさ種類は変わらない）
            ("ルアー:左上隅の左外", f, lbx - 1, lby, f),
            ("ルアー:左上隅の上外", f, lbx, lby - 1, f),
            ("ルアー:右上隅の右外", f, lbx + s, lby, f),
            ("ルアー:左下隅の下外", f, lbx, lby + s, f),
        ]
        for desc, initial, click_x, click_y, expected in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                core.hook.set_bait_type(initial)
                self.test_input.set_mouse_pos(click_x, click_y)
                self.test_input.set_mouse_pressed(True)
                core.update()
                self.assertEqual(core.hook.bait_type, expected)

    def test_draw_shows_selected_bait_highlighted(self):
        """選択中えさ種類ボタンに選択枠（draw_rectb）が描画される（描画順序込み）"""
        cases = [
            ("浮餌選択中", BaitType.FLOAT_BAIT),
            ("ルアー選択中", BaitType.LURE),
        ]
        for desc, bait_type in cases:
            with self.subTest(desc=desc):
                self.test_view.call_params.clear()
                core = GameCore()
                core.hook.set_bait_type(bait_type)
                core.draw()
                self.assertEqual(
                    _build_full_expected_calls(bait_type=bait_type),
                    self.test_view.get_call_params(),
                )

    def test_bait_button_ignored_when_hook_not_idle(self):
        """フック非IDLE状態ではえさボタンクリックを無視する"""
        cases = [HookState.THROWING, HookState.SURFACE]
        for state in cases:
            with self.subTest(state=state):
                core = GameCore()
                core.hook._state = state  # pylint: disable=W0212
                self.test_input.set_mouse_pos(
                    GameCore.LURE_BTN_X + 1, GameCore.LURE_BTN_Y + 1
                )
                self.test_input.set_mouse_pressed(True)
                core.update()
                self.assertEqual(core.hook.bait_type, BaitType.FLOAT_BAIT)

    def test_finished_hook_is_replaced_with_new_hook(self):
        """FINISHED 検出後、新 Hook は初期状態・初期位置で生成され、旧 bait_type を引き継ぐ"""
        cases = [BaitType.FLOAT_BAIT, BaitType.LURE]
        for bait_type in cases:
            with self.subTest(bait_type=bait_type):
                core = GameCore()
                core.hook.set_bait_type(bait_type)
                old_hook = core.hook
                core.hook._state = HookState.FINISHED_FAIL  # pylint: disable=W0212
                core.update()
                self.assertIsNot(core.hook, old_hook)
                self.assertEqual(core.hook.state, HookState.IDLE)
                self.assertEqual(core.hook.x, GameCore.LINE_ORIGIN_X)
                self.assertEqual(core.hook.y, GameCore.LINE_ORIGIN_Y)
                self.assertEqual(core.hook.bait_type, bait_type)

    def test_hook_drawn_when_not_idle(self):
        """待機以外の状態では hook ピクセルが全スプライトの後に描画される（描画順序込み）"""
        # 水面停止: throw() の vy=-6 のまま1フレーム更新。
        # init_y = WATER_Y - THROW_VY = 96-(-6)=102 → y=102+(-6)=96=WATER_Y で停止
        cases = [
            # (説明, 初期x, 初期y, update回数, 期待hook位置)
            ("投擲中", 150, 50, 0, (150, 50)),
            (
                "水面停止",
                100,
                GameCore.WATER_Y - Hook.MAX_VY,
                1,
                (int(100 + Hook.MAX_VX), GameCore.WATER_Y),
            ),
        ]
        for desc, init_x, init_y, updates, hook_pos in cases:
            with self.subTest(desc=desc):
                self.test_view.call_params.clear()
                core = GameCore()
                core.hook._charging_frames = (  # pylint: disable=W0212
                    Hook.MAX_CHARGE_FRAMES
                )
                core.hook.throw_charged()
                core.hook._charging_frames = 0  # stop_charge() 相当（実フローでは必ず呼ばれる）  # pylint: disable=W0212
                core.hook._x = init_x  # pylint: disable=W0212
                core.hook._y = init_y  # pylint: disable=W0212
                for _ in range(updates):
                    core.update()
                core.draw()
                expected = _build_full_expected_calls(hook_pos=hook_pos)
                self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCoreHold(TestParent):
    def test_hold_transitions_reeling(self):
        """長押し中: SINKING/SURFACE → REELING、それ以外の状態は変化しない（代表: IDLE）"""
        cases = [
            # (説明, 初期状態, hook._y, 期待状態)
            (
                "SINKING 中に長押し",
                HookState.SINKING,
                GameCore.WATER_Y + 40,
                HookState.REELING,
            ),
            (
                "SURFACE 中に長押し",
                HookState.SURFACE,
                GameCore.WATER_Y,
                HookState.REELING,
            ),
            (
                "IDLE 中に長押し → 変化なし",
                HookState.IDLE,
                GameCore.LINE_ORIGIN_Y,
                HookState.IDLE,
            ),
        ]
        for desc, initial_state, hook_y, expected_state in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                core.hook._state = initial_state  # pylint: disable=W0212
                core.hook._x = GameCore.LINE_ORIGIN_X - 50  # pylint: disable=W0212
                core.hook._y = hook_y  # pylint: disable=W0212
                self.test_input.set_mouse_held(True)
                core.update()
                self.assertEqual(core.hook.state, expected_state)

    def test_release_transitions_reeling(self):
        """長押し解除: REELING → SINKING/SURFACE、それ以外の状態は変化しない（代表: 水中深部 SINKING）"""
        cases = [
            # (説明, 初期状態, hook._y, 期待状態)
            (
                "水中 REELING → SINKING",
                HookState.REELING,
                GameCore.WATER_Y + 1,
                HookState.SINKING,
            ),
            (
                "水面 REELING → SURFACE",
                HookState.REELING,
                GameCore.WATER_Y,
                HookState.SURFACE,
            ),
            (
                "水中深部 SINKING → 変化なし",
                HookState.SINKING,
                GameCore.WATER_Y + 100,
                HookState.SINKING,
            ),
        ]
        for desc, initial_state, hook_y, expected_state in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                core.hook._state = initial_state  # pylint: disable=W0212
                core.hook._y = hook_y  # pylint: disable=W0212
                self.test_input.set_mouse_held(False)
                core.update()
                self.assertEqual(core.hook.state, expected_state)


class TestGameCoreCharging(TestParent):
    def test_charging_count_not_incremented_when_not_idle(self):
        """IDLE 以外の状態では GameCore が start_charge() を呼ばない（充電されない）"""
        core = GameCore()
        core.hook._state = HookState.THROWING  # pylint: disable=W0212
        self.test_input.set_mouse_held(True)
        core.update()
        self.assertEqual(core.hook._charging_frames, 0)  # pylint: disable=W0212

    def test_gamecore_calls_throw_charged_on_release(self):
        """マウス離放時に hook.throw_charged() が呼ばれ THROWING に遷移する"""
        core = GameCore()
        self.test_input.set_mouse_held(True)
        for _ in range(Hook.MIN_CHARGE_FRAMES):
            core.update()
        self.test_input.set_mouse_held(False)
        core.update()  # 離放フレーム
        self.assertEqual(core.hook.state, HookState.THROWING)

    def test_throw_velocity_reflects_charged_frames_on_release(self):
        """リリースフレームで throw_charged() が stop_charge() より先に実行され、充電フレーム数が速度に反映される"""
        core = GameCore()
        self.test_input.set_mouse_held(True)
        for _ in range(Hook.MAX_CHARGE_FRAMES):
            core.update()
        self.test_input.set_mouse_held(False)
        core.update()  # 離放フレーム: throw_charged() が先に実行されなければ _charging_frames=0 になる
        # 最大充電 → MAX_VX に相当する速度でなければならない（最弱の場合は失敗）
        self.assertAlmostEqual(
            abs(core.hook._vx), abs(Hook.MAX_VX)  # pylint: disable=W0212
        )

    def test_throw_state_transition_by_min_charge_boundary(self):
        """MIN_CHARGE_FRAMES の境界値で投擲の成否が正しく切り替わる"""
        cases = [
            (Hook.MIN_CHARGE_FRAMES - 1, HookState.IDLE, "MIN未満 → 投擲されない"),
            (Hook.MIN_CHARGE_FRAMES, HookState.THROWING, "MIN到達 → THROWING"),
        ]
        for charge_frames, expected_state, desc in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                self.test_input.set_mouse_held(True)
                for _ in range(charge_frames):
                    core.update()
                self.test_input.set_mouse_held(False)
                core.update()  # 離放フレーム
                self.assertEqual(core.hook.state, expected_state)

    def test_no_throw_after_reel_in_completes(self):
        """引き上げ完了直後にボタンを離しても即投擲されない（_prev_held リセット確認）

        バグの再現シナリオ:
          フレームN: ボタン押しっぱなし中に hook.update() が FINISHED を検出
                     → _handle_power_charge() 実行後に FINISHED 判定のため _prev_held=True のまま新 Hook 生成
          フレームN+1: ボタンを離す → released=True かつ state=IDLE → 即投擲されるバグ
        """
        core = GameCore()
        # フックを起点位置で REELING 状態にする（dist=0 < REEL_FINISH_DIST → hook.update() で即 FINISHED）
        core.hook._state = HookState.REELING  # pylint: disable=W0212
        # フレームN: ボタン押しっぱなしで hook.update() が FINISHED を検出
        self.test_input.set_mouse_held(True)
        core.update()  # _prev_held=True, hook → FINISHED → 新しい IDLE hook 生成
        # フレームN+1: ボタンを離す
        self.test_input.set_mouse_held(False)
        core.update()
        # 即投擲されずに IDLE のまま
        self.assertEqual(core.hook.state, HookState.IDLE)


class TestGameCorePowerGauge(TestParent):
    def setUp(self):
        super().setUp()
        self.core = GameCore()

    def test_power_gauge_draw_by_charge_state(self):
        """充電フレーム数に応じてゲージが正しい座標・色・順序で描画（または非描画）される

        MIN_CHARGE_FRAMES 未満（タップ相当）は charge_ratio が非ゼロでも非表示。
        境界値: MIN_CHARGE_FRAMES - 1 → 非表示、MIN_CHARGE_FRAMES → 表示。
        """
        cases = [
            (0, 0.0, "非充電（frames=0）→ ゲージなし"),
            (
                Hook.MIN_CHARGE_FRAMES - 1,
                0.0,
                "タップ相当（frames=MIN-1）→ charge_ratio 非ゼロだがゲージなし",
            ),
            (
                Hook.MIN_CHARGE_FRAMES,
                Hook.MIN_CHARGE_FRAMES / Hook.MAX_CHARGE_FRAMES,
                "充電中（frames=MIN）→ 通常色ゲージあり",
            ),
            (Hook.MAX_CHARGE_FRAMES, 1.0, "MAX 到達（frames=MAX）→ 強調色ゲージあり"),
        ]
        for frames, ratio, desc in cases:
            with self.subTest(desc=desc):
                core = GameCore()
                core.hook._charging_frames = frames  # pylint: disable=W0212
                self.test_view.call_params.clear()
                core.draw()
                expected = _build_full_expected_calls(charge_ratio=ratio)
                self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCoreFishIntegration(TestParent):
    def test_game_core_draw_draws_fish(self):
        """draw() が fish_list の各魚に is_hit を含む正しいパラメータで draw_fish() を呼ぶこと"""
        cases = [
            ("通常（is_hit=False）", False),
            ("ヒット済み（is_hit=True）", True),
        ]
        for desc, hit in cases:
            with self.subTest(desc):
                core = GameCore()
                _append_fish(core)
                core.fish_list[0]._is_hit = hit  # pylint: disable=W0212
                self.test_fish_view.draw_calls.clear()
                core.draw()
                self.assertEqual(
                    self.test_fish_view.draw_calls,
                    _build_full_expected_fish_calls(core.fish_list),
                )


class TestGameCoreHitDetection(TestParent):
    def test_no_second_hit_when_following_fish_set(self):
        """_following_fish 設定済みの場合: 別の魚がオーバーラップしても _following_fish は変わらない"""
        core = GameCore()
        _append_fish(core, n=2)
        fish_a = core.fish_list[0]
        fish_b = core.fish_list[1]

        # 魚Aをヒット済み・静止状態にして _following_fish に設定
        fish_a._is_hit = True  # pylint: disable=W0212
        fish_a._vx = (  # pylint: disable=W0212
            0.0  # update() 中に移動しないよう静止させる
        )
        fish_a._x = 50.0  # 画面内に配置  # pylint: disable=W0212
        core._following_fish = fish_a  # pylint: disable=W0212

        # 魚Bをフック位置にオーバーラップするよう配置（vx=0: offset_x=0 → head_x = int(_x)）
        fish_b._vx = 0.0  # update() 中に移動しない  # pylint: disable=W0212
        fish_b._x = float(  # pylint: disable=W0212
            core.hook.x
        )  # head_x = int(_x) = hook.x
        fish_b._y = float(  # head_y = int(_y) + HEAD_OFFSET_Y(3) = hook.y  # pylint: disable=W0212
            core.hook.y - Fish._HEAD_OFFSET_Y  # pylint: disable=W0212
        )

        with patch(
            "fish.random.random", return_value=0.0
        ):  # try_hit() が True を返す設定
            core.update()

        # _following_fish が魚Bに入れ替わっていないこと（魚Aのまま）
        self.assertIs(core._following_fish, fish_a)  # pylint: disable=W0212
        # 魚Bがヒット処理されていないこと
        self.assertFalse(fish_b.is_hit)

    def test_hit_detection_by_overlap(self):
        """オーバーラップの有無で fish.is_hit と vx が変わることを確認する（確率は 0.0 に固定）"""
        # (説明, フックのx方向オフセット, 期待する is_hit, 期待する vx<0)
        cases = [
            ("オーバーラップあり", 0, True, True),  # is_hit=True かつ逃げ移動（vx<0）
            (
                "オーバーラップなし",
                100,
                False,
                False,
            ),  # is_hit=False かつ vx は変化しない
        ]
        for desc, hook_x_offset, expected_is_hit, expected_vx_negative in cases:
            with self.subTest(desc):
                core = GameCore()
                # fish_list を既知の値で上書き（vx > 0 の右向き、x 位置を固定）
                test_fish = Fish(
                    GameCore.WATER_Y + 20,
                    GameCore.FISH_SPEED,
                    FishSize.SMALL,
                    x_min=0,
                    x_max=GameCore.SCREEN_WIDTH,
                )
                test_fish._x = 100.0  # pylint: disable=W0212
                core.fish_list = [test_fish]
                fish = core.fish_list[0]
                head_x, head_y = fish.get_head_pos()
                core.hook._x = float(head_x) + hook_x_offset  # pylint: disable=W0212
                core.hook._y = float(head_y)  # pylint: disable=W0212
                with patch("fish.random.random", return_value=0.0):
                    core.update()
                self.assertEqual(fish.is_hit, expected_is_hit)
                self.assertEqual(
                    fish.vx < 0, expected_vx_negative
                )  # ヒット時は逃げ移動（vx < 0）


class TestGameCoreHookFollowing(TestParent):
    def test_hook_follows_hit_fish_position(self):
        """フックがオーバーラップしてヒットした魚の頭位置に追従すること"""
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        # hook を fish[0] の頭位置に配置してオーバーラップを作る
        head_x, head_y = fish.get_head_pos()
        core.hook._x = float(head_x)  # pylint: disable=W0212
        core.hook._y = float(head_y)  # pylint: disable=W0212
        # 1回目 update(): オーバーラップ検出 → ヒット確定（random=0.0）
        with patch("fish.random.random", return_value=0.0):
            core.update()
        self.assertTrue(fish.is_hit)
        # 2回目 update(): フックがヒットした魚の頭位置に追従するはず
        core.update()
        head_x2, head_y2 = fish.get_head_pos()
        self.assertEqual(core.hook.x, head_x2)
        self.assertEqual(core.hook.y, head_y2)

    def test_fish_head_follows_hook_during_reeling(self):
        """REELING 中かつ魚がヒット済み: 魚の頭位置がフック位置に追従する。

        現在の実装では hook.move_to(fish_head) によりフックが魚位置に引き戻されてしまい、
        リーリングの移動が無効化される（巻き上げが効かないバグ）。
        正しい動作では fish.set_head_position(hook.x, hook.y) により魚がフックに追従する。
        """
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        fish._is_hit = True  # pylint: disable=W0212
        fish._vx = 0.0  # fish.update() で移動しないよう静止させる。head_offset_x=0（左向き扱い）  # pylint: disable=W0212

        # 魚をフックから大きく離れた左端付近に設定（左向き: head_x = int(_x) + 0）
        fish._x = 10.0  # head_x = 10 # pylint: disable=W0212
        fish._y = float(GameCore.WATER_Y + 80)  # pylint: disable=W0212

        # フックを REELING 状態・投擲起点（LINE_ORIGIN_X=203）から左 50px の位置に設定
        # _update_reeling() で右方向（LINE_ORIGIN_X 方向）へ移動する
        core.hook._state = HookState.REELING  # pylint: disable=W0212
        core.hook._x = float(  # pylint: disable=W0212
            GameCore.LINE_ORIGIN_X - 50  # = 153.0
        )
        core.hook._y = float(GameCore.WATER_Y + 40)  # = 136.0  # pylint: disable=W0212
        core._following_fish = fish  # pylint: disable=W0212
        self.test_input.set_mouse_held(
            True
        )  # REELING 状態を維持（stop_reeling() を呼ばない）

        # 魚の元の頭位置を記録（フックが引き戻されていないことの確認に使用）
        original_fish_head_x = int(fish._x)  # = 10  # pylint: disable=W0212

        core.update()

        # 正しい動作: 魚の頭がフック位置に追従する
        head_x, head_y = fish.get_head_pos()
        self.assertEqual(head_x, core.hook.x)
        self.assertEqual(head_y, core.hook.y)
        # フックがリーリングで移動した位置（> 魚の元の頭位置 10）にあること
        # 現在の実装では hook.move_to(fish_head) で hook.x=10 になり、この assertion が失敗する
        self.assertGreater(core.hook.x, original_fish_head_x)

    def test_hook_finishes_when_following_fish_goes_offscreen(self):
        """フックが追従した魚が画面外に出るとフックが FINISHED 状態になること

        is_hit=True の魚は update() で壁バウンドしないため、ヒット済み状態を直接セットアップする。
        fish._x=0.0 の場合の追跡:
          vx<0（左向き）→ フリップ → offset_x=0 → head_x = int(0.0) + 0 = 0
          update(): fish.update() → _x=-1.5（is_hit=True なので壁バウンドなし）
                    head_x=int(-1.5)+0=-1<0 → hook.x<0 → FINISHED
        """
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        # ヒット済み・逃げ中の魚をセットアップ
        fish._is_hit = True  #  (is_hit=True なら update() で壁バウンドしない) # pylint: disable=W0212
        fish._vx = -1.5  #  (逃げ速度) # pylint: disable=W0212
        fish._x = 0.0  # (1回 update() で head_x<0 になる位置) # pylint: disable=W0212
        head_x, head_y = fish.get_head_pos()
        core.hook._x = float(head_x)  # pylint: disable=W0212
        core.hook._y = float(head_y)  # pylint: disable=W0212
        core._following_fish = (  # (hook が fish を追従中であることを直接セット) # pylint: disable=W0212
            fish
        )
        # update(): 魚が画面外へ → フックも追従して FINISHED_FAIL になるはず
        core.update()
        self.assertEqual(core.hook.state, HookState.FINISHED_FAIL)
        # FINISHED_FAIL（画面外逃げ）後も追従していた魚は描画を継続する
        self.test_fish_view.draw_calls.clear()
        core.draw()
        self.assertEqual(
            self.test_fish_view.draw_calls,
            _build_full_expected_fish_calls(core.fish_list),
        )


class TestGameCoreHookFishNotification(TestParent):
    def test_hook_has_fish_set_when_fish_hooked(self):
        """魚がヒットしてフックに追従した時: hook._has_fish が True になる"""
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        # フックを魚の頭位置に配置してオーバーラップを作る
        head_x, head_y = fish.get_head_pos()
        core.hook._x = float(head_x)  # pylint: disable=W0212
        core.hook._y = float(head_y)  # pylint: disable=W0212
        # hook.hook_fish() が呼ばれていなければ _has_fish は False のまま
        self.assertFalse(core.hook._has_fish)  # pylint: disable=W0212
        with patch(
            "fish.random.random", return_value=0.0
        ):  # try_hit() が True を返す設定
            core.update()
        # ヒット確定後: hook._has_fish が True になること
        self.assertTrue(core.hook._has_fish)  # pylint: disable=W0212

    def test_reel_speed_reduced_after_fish_hooked(self):
        """魚ヒット後の巻き上げ: 魚サイズに応じた速度で移動する（2フレーム統合テスト）

        フレーム1: 魚をオーバーラップさせてヒット判定を発火 → hook.hook_fish(fish_size) が呼ばれ _has_fish=True。
        フレーム2: SURFACE → REELING 遷移後の水平移動量が REEL_SPEED_WITH_FISH_MAP[fish.fish_size] と一致すること。
        """
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]

        # フレーム1の設定: フックを SURFACE 位置に固定し、魚頭をフック位置と一致させる
        hook_start_x = 100
        core.hook._state = HookState.SURFACE  # pylint: disable=W0212
        core.hook._x = float(hook_start_x)  # pylint: disable=W0212
        core.hook._y = float(GameCore.WATER_Y)  # pylint: disable=W0212

        # 魚: 左向き（vx=0 → offset_x=0）、頭が (hook_start_x, WATER_Y) になる位置に配置
        # get_head_pos() → head_x = int(_x)+0, head_y = int(_y)+_HEAD_OFFSET_Y(3)
        fish._vx = 0.0  # pylint: disable=W0212
        fish._x = float(hook_start_x)  # pylint: disable=W0212
        fish._y = float(GameCore.WATER_Y - Fish._HEAD_OFFSET_Y)  # pylint: disable=W0212

        # フレーム1: hit_detection → 魚ヒット、_following_fish 設定、hook.hook_fish() 呼び出し
        with patch("fish.random.random", return_value=0.0):  # try_hit() = True
            core.update()

        self.assertIs(
            core._following_fish, fish  # pylint: disable=W0212
        )  # 前提: ヒット確定

        # フレーム2: 巻き上げ開始 → hook が REEL_SPEED_WITH_FISH_MAP[fish.fish_size] で移動するはず
        self.test_input.set_mouse_held(True)
        core.update()

        # SURFACE から巻き上げ: 水平移動 _x += speed（float で比較して int 切り捨て誤差を防ぐ）
        x_moved = core.hook._x - hook_start_x  # pylint: disable=W0212
        self.assertAlmostEqual(x_moved, Hook.REEL_SPEED_WITH_FISH_MAP[fish.fish_size])


class TestGameCoreFishOffscreen(TestParent):
    def _make_stationary_hit_fish(self, core, x):
        """位置固定のヒット済み魚を返す（_vx=0 で update() 中に移動しない）。"""
        _append_fish(core)
        fish = core.fish_list[-1]
        fish._is_hit = True  # pylint: disable=W0212  (壁バウンドを無効化)
        fish._vx = 0.0  #  (update() 中の位置変化を防ぐ) # pylint: disable=W0212
        fish._x = float(x)  # pylint: disable=W0212
        return fish

    def test_offscreen_fish_removed_from_fish_list(self):
        """画面外の魚が update() 後に fish_list から削除されること"""
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        fish._is_hit = True  # (is_hit=True で壁バウンドなし)  # pylint: disable=W0212
        fish._x = (  # pylint: disable=W0212
            -200.0  # (draw_x=-200, draw_x+TILE_SIZE=-192<0 → 画面外)
        )
        core.update()
        self.assertNotIn(fish, core.fish_list)

    def test_fish_at_screen_edge_not_removed(self):
        """画面端ぴったり（境界値）の魚は fish_list から削除されないこと。

        左端: draw_x=-8 → draw_x + TILE_SIZE(8) = 0, 0 < 0 は False → 画面内
        右端: draw_x=240 → 240 > SCREEN_WIDTH(240) は False → 画面内
        """
        cases = [
            ("左端 draw_x=-8", -8),
            ("右端 draw_x=240", 240),
        ]
        for label, x in cases:
            with self.subTest(label):
                core = GameCore()
                fish = self._make_stationary_hit_fish(core, x)
                core.update()
                self.assertIn(fish, core.fish_list)

    def test_fish_just_outside_screen_removed(self):
        """画面端の1px外（境界値+1）の魚は fish_list から削除されること。

        左端外: draw_x=-9 → draw_x + TILE_SIZE(8) = -1 < 0 → 画面外
        右端外: draw_x=241 → 241 > SCREEN_WIDTH(240) → 画面外
        """
        cases = [
            ("左端外 draw_x=-9", -9),
            ("右端外 draw_x=241", 241),
        ]
        for label, x in cases:
            with self.subTest(label):
                core = GameCore()
                fish = self._make_stationary_hit_fish(core, x)
                core.update()
                self.assertNotIn(fish, core.fish_list)


class TestGameCoreCaughtFish(TestParent):
    def _setup_hooked_fish_near_origin(self, core):
        """魚をヒット済み・フック追従状態にし、フックを投擲地点直近に配置するヘルパー。

        フックが REELING 状態から _update_reeling() を経て自然に FINISHED_SUCCESS に遷移するよう設定する。
        dist = 1 < REEL_FINISH_DIST(6) → 次フレームで即 FINISHED_SUCCESS 遷移。
        マウスを押し続け中（held=True）にしないと _handle_hold() が stop_reeling() を呼び
        SURFACE に戻ってしまうため、set_mouse_held(True) が必要。
        """
        _append_fish(core)
        fish = core.fish_list[0]
        fish._is_hit = True  # pylint: disable=W0212
        fish._vx = 0.0  # update() 中に移動しないよう静止させる  # pylint: disable=W0212
        # フックを REELING 状態・投擲起点直近（dist=1 < REEL_FINISH_DIST）に配置
        core.hook._state = HookState.REELING  # pylint: disable=W0212
        core.hook._x = float(GameCore.LINE_ORIGIN_X - 1)  # pylint: disable=W0212
        core.hook._y = float(GameCore.LINE_ORIGIN_Y)  # pylint: disable=W0212
        core.hook.hook_fish(fish.fish_size)
        core._following_fish = fish  # pylint: disable=W0212
        self.test_input.set_mouse_held(
            True
        )  # REELING 維持（False だと stop_reeling() → SURFACE になる）
        return fish

    def test_caught_fish_not_drawn_after_reel_to_origin(self):
        """魚ヒット後、フックが投擲地点に到達すると釣った魚が描画されない。

        REELING → FINISHED_SUCCESS 遷移を自然に発生させ、
        draw_fish の呼び出し数が1減ることを確認する。
        """
        core = GameCore()
        self._setup_hooked_fish_near_origin(core)

        core.update()  # REELING → FINISHED_SUCCESS が自然に発生

        self.test_fish_view.draw_calls.clear()
        core.draw()
        self.assertEqual(
            self.test_fish_view.draw_calls,
            _build_full_expected_fish_calls(core.fish_list),
        )

    def test_hit_fish_still_drawn_after_line_break(self):
        """糸切れ（FINISHED_FAIL）後も、ヒット済みの魚は描画を継続する。

        糸切れは釣り上げ成功ではないため、追従していた魚を fish_list から除去しない。
        hook.update() 内で FINISHED_FAIL が発生するため FINISHED チェックが走るが、
        set_caught() は FINISHED_SUCCESS の時のみ呼ぶべき設計。
        """
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        fish._is_hit = True  # pylint: disable=W0212
        fish._vx = 0.0  # update() 中に移動しないよう静止  # pylint: disable=W0212
        fish._x = 50.0  # 画面内に配置  # pylint: disable=W0212
        # フックを REELING 状態・糸切れ直前に設定（次フレームで FINISHED_FAIL に遷移）
        core.hook._state = HookState.REELING  # pylint: disable=W0212
        core.hook._x = float(  # pylint: disable=W0212
            GameCore.LINE_ORIGIN_X - 50
        )  # 投擲起点から十分遠い位置
        core.hook._y = float(GameCore.WATER_Y + 40)  # pylint: disable=W0212
        core.hook.hook_fish(fish.fish_size)
        core.hook._reel_with_fish_frames = (  # pylint: disable=W0212
            Hook.REEL_LINE_BREAK_FRAMES_MAP[fish.fish_size] - 1
        )  # あと1フレームで糸切れ
        core._following_fish = fish  # pylint: disable=W0212
        self.test_input.set_mouse_held(
            True
        )  # REELING 維持（False だと stop_reeling() → SURFACE になる）

        # update(): reel_with_fish_frames が上限に達して糸切れ → FINISHED_FAIL
        core.update()

        # 糸切れ後も追従していた魚は描画される
        self.test_fish_view.draw_calls.clear()
        core.draw()
        self.assertEqual(
            self.test_fish_view.draw_calls,
            _build_full_expected_fish_calls(core.fish_list),
        )

    def test_hook_not_drawn_after_reel_to_origin(self):
        """魚ヒット後、フックが投擲地点に到達すると釣り針線が描画されない。

        REELING → FINISHED_SUCCESS 遷移後はフックが IDLE に戻るため draw_line が呼ばれない。
        ポップアップが表示されるため、描画期待値にポップアップ呼び出しも含む。
        """
        core = GameCore()
        self._setup_hooked_fish_near_origin(core)

        core.update()  # REELING → FINISHED_SUCCESS が自然に発生

        self.test_view.call_params.clear()
        core.draw()
        popup = core._popup  # pylint: disable=W0212
        self.assertEqual(
            _build_full_expected_calls(score=core._score)  # pylint: disable=W0212
            + _build_popup_expected_calls(
                popup.fish_rarity, popup.fish_size, popup.score
            ),
            self.test_view.call_params,
        )

    def test_score_added_on_finished_success(self):
        """REELING → FINISHED_SUCCESS 遷移時に fish.get_score() 分のスコアが加算されること。"""
        core = GameCore()
        fish = self._setup_hooked_fish_near_origin(core)
        expected_score = fish.get_score()  # = Fish.SCORE_BY_SIZE[FishSize.SMALL]

        core.update()  # REELING → FINISHED_SUCCESS → _score += fish.get_score()

        self.assertEqual(core._score, expected_score)  # pylint: disable=W0212

    def test_score_not_added_on_finished_fail(self):
        """糸切れ（FINISHED_FAIL）ではスコアが加算されないこと。"""
        core = GameCore()
        _append_fish(core)
        fish = core.fish_list[0]
        fish._is_hit = True  # pylint: disable=W0212
        fish._vx = 0.0  # pylint: disable=W0212
        fish._x = 50.0  # pylint: disable=W0212
        core.hook._state = HookState.REELING  # pylint: disable=W0212
        core.hook._x = float(GameCore.LINE_ORIGIN_X - 50)  # pylint: disable=W0212
        core.hook._y = float(GameCore.WATER_Y + 40)  # pylint: disable=W0212
        core.hook.hook_fish(fish.fish_size)
        core.hook._reel_with_fish_frames = (  # pylint: disable=W0212
            Hook.REEL_LINE_BREAK_FRAMES_MAP[fish.fish_size] - 1
        )  # あと1フレームで糸切れ
        core._following_fish = fish  # pylint: disable=W0212
        self.test_input.set_mouse_held(True)

        core.update()  # 糸切れ → FINISHED_FAIL

        self.assertEqual(core._score, 0)  # pylint: disable=W0212


class TestGameCoreCreateFish(TestParent):
    """TDD サイクル 1: 深度別の魚サイズ定義 - Red フェーズ"""

    def test_create_fish_properties(self):
        """_create_fish(fish_size) が正しいサイズ・Y 範囲の魚を返すこと"""
        game_core = GameCore()
        for fish_size in FishSize:
            with self.subTest(fish_size=fish_size):
                fish = game_core._create_fish(fish_size)  # pylint: disable=W0212
                self.assertEqual(fish.fish_size, fish_size)
                y_min, y_max = GameCore.FISH_Y_RANGE_BY_SIZE[fish_size]
                self.assertGreaterEqual(fish.draw_y, y_min)
                self.assertLessEqual(fish.draw_y, y_max)


class TestGameCoreFishSizeIntegration(TestParent):
    """TDD サイクル 4: GameCore 統合 - fish_size 連携テスト

    _update_hit_detection() が hook.hook_fish(fish.fish_size) を呼び出すことで、
    フックの巻き上げ速度と糸切れフレームが魚サイズに応じて設定されることを検証する。
    """

    def _make_fish_at_hook(self, core, fish_size):
        """指定サイズの魚をフック位置に配置するヘルパー（オーバーラップ確定）。

        Y 位置は SMALL の出現範囲内の固定値（WATER_Y+20）を使用する。
        この Y は MEDIUM_L/LARGE の出現範囲外だが、オーバーラップ判定はフックと魚の
        頭位置の一致で行われるため、魚の Y は fish_size に対応した出現範囲でなくてよい。
        """
        test_fish = Fish(
            GameCore.WATER_Y + 20,
            GameCore.FISH_SPEED,
            fish_size,
            x_min=0,
            x_max=GameCore.SCREEN_WIDTH,
        )
        test_fish._x = 100.0  # pylint: disable=W0212
        core.fish_list = [test_fish]
        head_x, head_y = test_fish.get_head_pos()
        core.hook._x = float(head_x)  # pylint: disable=W0212
        core.hook._y = float(head_y)  # pylint: disable=W0212
        return test_fish

    def test_hook_params_reflect_fish_size_after_hit(self):
        """魚ヒット後: hook の巻き上げ速度・糸切れフレームが fish.fish_size に対応した値になること。

        サイズ別の速度・フレーム値は test_hook.py（TestReelingSpeedByFishSize, TestLineBreakByFishSize）
        で全4サイズを検証済み。ここでは GameCore が fish.fish_size を hook.hook_fish() に
        正しく渡しているかの配線確認として MEDIUM_L の1ケースのみ検証する。
        """
        core = GameCore()
        self._make_fish_at_hook(core, FishSize.MEDIUM_L)
        with patch("fish.random.random", return_value=0.0):
            core._update_hit_detection()  # pylint: disable=W0212
        self.assertAlmostEqual(
            core.hook._reel_speed_with_fish,  # pylint: disable=W0212
            Hook.REEL_SPEED_WITH_FISH_MAP[FishSize.MEDIUM_L],
        )
        self.assertEqual(
            core.hook._reel_line_break_frames,  # pylint: disable=W0212
            Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.MEDIUM_L],
        )


class TestFishSpawnTimer(TestParent):
    """TDD サイクル 5: スポーンタイマーと上限管理のテスト"""

    def _make_game_core(self):
        """テスト用 GameCore（fish_list 空、スポーンタイマー初期化済み）"""
        core = GameCore()
        core.fish_list = []
        core._spawn_timer = 0  # pylint: disable=W0212
        core._next_spawn_interval = GameCore.SPAWN_INTERVAL_MIN  # pylint: disable=W0212
        return core

    def test_spawn_timer_threshold(self):
        """_spawn_timer が閾値に達するかどうかでスポーンの有無が切り替わること

        実装はインクリメントしてからチェック（+= 1 → if >= interval）。
        (説明, 初期 _spawn_timer, update 後の期待魚数) のペアで境界値を検証する。
        """
        cases = [
            (
                "閾値1つ前 → スポーンなし",
                GameCore.SPAWN_INTERVAL_MIN - 2,
                0,
            ),  # +1 → INTERVAL-1 → 閾値未満
            (
                "閾値到達 → スポーンあり",
                GameCore.SPAWN_INTERVAL_MIN - 1,
                1,
            ),  # +1 → INTERVAL  → 閾値到達
        ]
        for desc, initial_timer, expected_count in cases:
            with self.subTest(desc=desc):
                core = self._make_game_core()
                core._spawn_timer = initial_timer  # pylint: disable=W0212
                core.update()
                self.assertEqual(len(core.fish_list), expected_count)

    def test_respawn_after_next_interval(self):
        """スポーン後、次の間隔が経過すると再度スポーンすること

        _next_spawn_interval は SPAWN_INTERVAL_MIN〜SPAWN_INTERVAL_MAX のランダム値。
        最長 SPAWN_INTERVAL_MAX フレーム待てば、次のインターバルが何であれ再スポーンが発生する。
        """
        core = self._make_game_core()
        # SPAWN_INTERVAL_MIN フレーム経過で1回目のスポーン（初期インターバルは SPAWN_INTERVAL_MIN）
        for _ in range(GameCore.SPAWN_INTERVAL_MIN):
            core.update()
        self.assertEqual(len(core.fish_list), 1)  # 前提: 1回目スポーン済み

        # さらに最長 SPAWN_INTERVAL_MAX フレーム経過で2回目のスポーンが必ず発生する
        for _ in range(GameCore.SPAWN_INTERVAL_MAX):
            core.update()
        self.assertGreaterEqual(len(core.fish_list), 2)

    def test_max_fish_by_size_not_exceeded(self):
        """各 FishSize の上限を超えてスポーンしないこと

        SMALL の魚を MAX_FISH_BY_SIZE[SMALL] 匹まで追加した状態でスポーン試行。
        SMALL は上限に達しているため新たに追加されず、代わりに他サイズが1匹追加される。
        """
        core = self._make_game_core()
        max_small = GameCore.MAX_FISH_BY_SIZE[FishSize.SMALL]
        for _ in range(max_small):
            core.fish_list.append(
                Fish(
                    GameCore.WATER_Y + 20,
                    GameCore.FISH_SPEED,
                    FishSize.SMALL,
                    x_min=0,
                    x_max=GameCore.SCREEN_WIDTH,
                )
            )
        small_count_before = sum(
            1 for f in core.fish_list if f.fish_size == FishSize.SMALL
        )
        total_count_before = len(core.fish_list)
        core._spawn_timer = core._next_spawn_interval - 1  # pylint: disable=W0212
        core.update()
        small_count_after = sum(
            1 for f in core.fish_list if f.fish_size == FishSize.SMALL
        )
        self.assertEqual(small_count_after, small_count_before)  # SMALL は増えない
        self.assertEqual(
            len(core.fish_list), total_count_before + 1
        )  # 他サイズが1匹追加される

    def test_no_spawn_when_all_sizes_at_max(self):
        """全サイズが上限に達している場合はスポーンしないこと"""
        core = self._make_game_core()
        for fish_size in FishSize:
            for _ in range(GameCore.MAX_FISH_BY_SIZE[fish_size]):
                core.fish_list.append(
                    Fish(
                        GameCore.WATER_Y + 20,
                        GameCore.FISH_SPEED,
                        fish_size,
                        x_min=0,
                        x_max=GameCore.SCREEN_WIDTH,
                    )
                )
        total_before = len(core.fish_list)
        core._spawn_timer = core._next_spawn_interval - 1  # pylint: disable=W0212
        core.update()
        self.assertEqual(len(core.fish_list), total_before)


class TestGameCorePopup(TestParent):
    def setUp(self):
        super().setUp()
        self.game_core = GameCore()
        self.fish = Fish(
            GameCore.WATER_Y + 20,
            GameCore.FISH_SPEED,
            FishSize.SMALL,
            x_min=0,
            x_max=GameCore.SCREEN_WIDTH,
        )

    def test_no_popup_drawn_when_fish_not_caught(self):
        """釣り上げ失敗では draw でポップアップが描画されない"""
        self.game_core.hook._state = HookState.FINISHED_FAIL  # pylint: disable=W0212
        self.game_core._following_fish = None  # pylint: disable=W0212

        self.game_core.update()
        self.game_core.draw()

        self.assertEqual(self.test_view.get_call_params(), _build_full_expected_calls())

    def test_throw_disabled_while_popup_visible(self):
        """ポップアップ表示中は投擲操作を受け付けない"""
        self.game_core._popup = FishCatchPopup(  # pylint: disable=W0212
            0, FishSize.SMALL, FishRarity.LOW
        )
        self.test_input.set_mouse_held(True)  # マウス長押し中

        self.game_core.update()

        # 充電が行われていない（charge_ratio が 0.0 のまま）
        self.assertEqual(self.game_core.hook.charge_ratio, 0.0)

    def test_bait_change_disabled_while_popup_visible(self):
        """ポップアップ表示中は餌変更操作を受け付けない"""
        self.game_core._popup = FishCatchPopup(  # pylint: disable=W0212
            0, FishSize.SMALL, FishRarity.LOW
        )
        self.game_core.hook.set_bait_type(BaitType.LURE)  # 現在がルアー設定
        self.test_input.set_mouse_pressed(True)
        self.test_input.set_mouse_pos(
            GameCore.FLOAT_BAIT_BTN_X + 1,
            GameCore.FLOAT_BAIT_BTN_Y + 1,
        )  # 浮餌ボタンをクリック

        self.game_core.update()

        # 餌種類が変更されない
        self.assertEqual(self.game_core.hook.bait_type, BaitType.LURE)

    def test_tap_popup_dismiss_by_position(self):
        """タップ位置（矩形内外）によってポップアップ解除状態が変わる"""
        px, py = FishCatchPopup.X, FishCatchPopup.Y
        pw, ph = FishCatchPopup.W, FishCatchPopup.H
        cases = [
            # 矩形内
            ("矩形内（中央）", px + pw // 2, py + ph // 2, False),
            ("矩形内（左端）", px, py + ph // 2, False),
            ("矩形内（右端）", px + pw - 1, py + ph // 2, False),
            ("矩形内（上端）", px + pw // 2, py, False),
            ("矩形内（下端）", px + pw // 2, py + ph - 1, False),
            # 矩形外（境界の1つ外）
            ("矩形外（左端の外）", px - 1, py + ph // 2, True),
            ("矩形外（右端の外）", px + pw, py + ph // 2, True),
            ("矩形外（上端の外）", px + pw // 2, py - 1, True),
            ("矩形外（下端の外）", px + pw // 2, py + ph, True),
        ]
        for label, x, y, expected_visible in cases:
            with self.subTest(label):
                self.game_core._popup = FishCatchPopup(  # pylint: disable=W0212
                    0, FishSize.SMALL, FishRarity.LOW
                )
                self.test_input.set_mouse_pressed(True)
                self.test_input.set_mouse_pos(x, y)

                self.game_core.update()

                self.assertEqual(
                    self.game_core._popup is not None,  # pylint: disable=W0212
                    expected_visible,
                )

    def test_no_tap_does_not_dismiss_popup(self):
        """タップなしではポップアップが解除されない"""
        self.game_core._popup = FishCatchPopup(  # pylint: disable=W0212
            0, FishSize.SMALL, FishRarity.LOW
        )
        self.test_input.set_mouse_pressed(False)

        self.game_core.update()

        self.assertIsNotNone(self.game_core._popup)  # pylint: disable=W0212

    def test_popup_drawn_when_fish_caught(self):
        """魚を釣り上げると次の draw でポップアップが描画される"""
        self.game_core.hook._state = HookState.FINISHED_SUCCESS  # pylint: disable=W0212
        self.game_core._following_fish = self.fish  # pylint: disable=W0212
        expected_score = self.fish.get_score()

        self.game_core.update()
        self.game_core.draw()

        expected_view_calls = _build_full_expected_calls(
            score=expected_score
        ) + _build_popup_expected_calls(
            self.fish.fish_rarity, self.fish.fish_size, expected_score
        )
        self.assertEqual(self.test_view.get_call_params(), expected_view_calls)

    def test_draw_popup_fish_u_and_v_for_all_rarity_size_combinations(self):
        """ポップアップの魚画像はレア度×サイズの全組み合わせで u・v が正しく選択される"""
        popup_score = 1
        for rarity in FishCatchPopup.RARITY_U:
            for fish_size in FishSize:
                with self.subTest(rarity=rarity, fish_size=fish_size):
                    self.test_view.call_params = []
                    self.game_core._popup = FishCatchPopup(  # pylint: disable=W0212
                        popup_score, fish_size, rarity
                    )

                    self.game_core.draw()

                    expected_calls = _build_full_expected_calls(
                        score=0
                    ) + _build_popup_expected_calls(rarity, fish_size, popup_score)
                    self.assertEqual(
                        self.test_view.get_call_params(),
                        expected_calls,
                    )


class TestGameCoreFatigue(TestParent):
    """疲労値の管理と疲労ゲージの描画"""

    def setUp(self):
        super().setUp()
        self.game_core = GameCore()

    def _set_hook_reeling_far(self):
        """フックを巻き上げ中（REELING）かつ到達しない距離に設定する。

        REEL_SPEED=2 のため REEL_FINISH_DIST=6 より十分遠い位置（x=0, 水面）を使用。
        1フレームで FINISHED にならないことが保証される。
        is_mouse_btn_held=True: _handle_hold() による stop_reeling() を防ぐ。
        """
        self.game_core.hook._x = 0  # pylint: disable=W0212
        self.game_core.hook._y = GameCore.WATER_Y  # pylint: disable=W0212
        self.game_core.hook.start_reeling()
        self.test_input.set_mouse_held(True)

    def _set_following_fish(self):
        """魚を1匹追加してヒット済み・追従中（_following_fish）の状態にする。

        魚ヒット時のみ疲労を消費する仕様のテストに共通して使用するセットアップ。
        """
        _append_fish(self.game_core)
        fish = self.game_core.fish_list[-1]
        fish._is_hit = True  # pylint: disable=W0212
        self.game_core._following_fish = fish  # pylint: disable=W0212

    def test_draw_renders_fatigue_gauge_for_each_fatigue_value(self):
        """疲労値に応じて外枠→内側（幅=比例値）の順に描画される"""
        cases = [
            ("疲労値 MAX: 内側の幅が FATIGUE_GAUGE_W", GameCore.MAX_FATIGUE),
            ("疲労値 MAX/2: 内側の幅が FATIGUE_GAUGE_W/2", GameCore.MAX_FATIGUE // 2),
            ("疲労値 0: 内側の幅が 0", 0),
        ]
        for desc, fatigue in cases:
            with self.subTest(desc=desc):
                self.game_core._fatigue = fatigue  # pylint: disable=W0212
                self.test_view.call_params = []

                self.game_core.draw()

                self.assertEqual(
                    self.test_view.get_call_params(),
                    _build_full_expected_calls(fatigue=fatigue),
                )

    def test_reeling_with_fish_decreases_fatigue_gauge_rendered_width(self):
        """魚ヒット中の REELING フレームで疲労ゲージ幅が疲労値に応じて変化する"""
        # x=0, y=WATER_Y から1フレームで水面を REEL_SPEED=2 だけ水平移動する
        expected_hook_pos = (Hook.REEL_SPEED, GameCore.WATER_Y)
        cases = [
            (
                "疲労値 MAX → MAX-1: 内側の幅が1減る",
                GameCore.MAX_FATIGUE,
                GameCore.MAX_FATIGUE - 1,
            ),
            ("疲労値 0 → 0: 下限クランプで内側の幅は変わらない", 0, 0),
        ]
        for desc, initial_fatigue, expected_fatigue in cases:
            with self.subTest(desc=desc):
                self.game_core._fatigue = initial_fatigue  # pylint: disable=W0212
                self._set_hook_reeling_far()
                self._set_following_fish()
                self.test_view.call_params = []

                self.game_core.update()
                self.game_core.draw()

                self.assertEqual(
                    self.test_view.get_call_params(),
                    _build_full_expected_calls(
                        hook_pos=expected_hook_pos,
                        fatigue=expected_fatigue,
                    ),
                )

    def test_reeling_without_fish_does_not_decrease_fatigue_gauge_rendered_width(self):
        """魚がヒットしていない REELING フレームでは疲労ゲージ幅が変化しない。

        遠投のメリットを成立させるため、魚が掛かっていない巻き上げ中は
        疲労を消費しない仕様を描画で検証する。
        """
        # x=0, y=WATER_Y から1フレームで水面を REEL_SPEED=2 だけ水平移動する
        expected_hook_pos = (Hook.REEL_SPEED, GameCore.WATER_Y)
        self.game_core._fatigue = GameCore.MAX_FATIGUE  # pylint: disable=W0212
        # _following_fish = None（デフォルト）の状態で REELING に設定
        self._set_hook_reeling_far()
        self.test_view.call_params = []

        self.game_core.update()
        self.game_core.draw()

        # 魚なし REELING ではゲージ幅が MAX のまま変化しないこと
        self.assertEqual(
            self.test_view.get_call_params(),
            _build_full_expected_calls(
                hook_pos=expected_hook_pos,
                fatigue=GameCore.MAX_FATIGUE,
            ),
        )

    def test_throw_decreases_fatigue_by_min_charge_frames(self):
        """投擲時に疲労値が Hook.MIN_CHARGE_FRAMES 分減少する"""
        initial_fatigue = GameCore.MAX_FATIGUE
        self.game_core._fatigue = initial_fatigue  # pylint: disable=W0212
        # MIN_CHARGE_FRAMES 分充電してから離放 → 投擲成立
        self.test_input.set_mouse_held(True)
        for _ in range(Hook.MIN_CHARGE_FRAMES):
            self.game_core.update()
        self.test_input.set_mouse_held(False)
        self.game_core.update()  # 離放フレーム: throw_charged() が呼ばれる
        expected = initial_fatigue - Hook.MIN_CHARGE_FRAMES
        self.assertEqual(
            self.game_core._fatigue,  # pylint: disable=W0212
            expected,
            f"投擲後の疲労値は {expected} であるべき（初期値 {initial_fatigue} - MIN_CHARGE_FRAMES {Hook.MIN_CHARGE_FRAMES}）",
        )


class TestGameCoreGameOverPopup(TestParent):
    """ゲームオーバー遷移とポップアップ表示の振る舞いテスト"""

    def setUp(self):
        super().setUp()
        self.game_core = GameCore()

    def _do_finish_and_idle(self):
        """フックを FINISHED_FAIL 状態にして update() で IDLE に復帰させる"""
        self.game_core.hook._state = HookState.FINISHED_FAIL  # pylint: disable=W0212
        self.game_core.update()

    def test_no_game_over_popup_after_idle_restoration_with_remaining_fatigue(self):
        """疲労値が 1 以上のとき、IDLE 復帰後の draw() でゲームオーバーポップアップが描画されない"""
        self.game_core._fatigue = 1  # pylint: disable=W0212
        self._do_finish_and_idle()
        self.test_view.call_params = []

        self.game_core.draw()

        self.assertEqual(
            self.test_view.get_call_params(), _build_full_expected_calls(fatigue=1)
        )

    def test_game_over_popup_draw_renders_correctly_after_zero_fatigue_idle(self):
        """疲労値 0 での IDLE 復帰後、draw() でスコアを含むゲームオーバーポップアップが正しい順序で描画される"""
        self.game_core._score = 42  # pylint: disable=W0212
        self.game_core._fatigue = 0  # pylint: disable=W0212
        self._do_finish_and_idle()  # → _is_game_over = True
        self.game_core.update()  # → _game_over_popup 生成（score=42 で初期化）
        self.test_view.call_params = []

        self.game_core.draw()

        expected = _build_full_expected_calls(
            fatigue=0, score=42
        ) + _build_game_over_popup_expected_calls(42)
        self.assertEqual(self.test_view.get_call_params(), expected)

    def _tap_game_over_popup(self):
        """ゲームオーバーポップアップ内をタップする"""
        self.test_input.set_mouse_pos(GameOverPopup.X, GameOverPopup.Y)
        self.test_input.set_mouse_pressed(True)

    def test_game_over_update_skips_hook_logic(self):
        """ゲームオーバー中は update() でフックの更新がスキップされる"""
        self.game_core._fatigue = 0  # pylint: disable=W0212
        self._do_finish_and_idle()  # → _is_game_over = True
        self.game_core.hook._state = HookState.THROWING  # pylint: disable=W0212
        self.game_core.hook._vx = 3  # pylint: disable=W0212
        self.game_core.hook._x = 100  # pylint: disable=W0212
        before_x = self.game_core.hook.x

        self.game_core.update()

        self.assertEqual(self.game_core.hook.x, before_x)

    def test_needs_reset_becomes_true_after_game_over_popup_tapped(self):
        """ゲームオーバーポップアップをタップすると needs_reset() が True になる"""
        self.game_core._fatigue = 0  # pylint: disable=W0212
        self._do_finish_and_idle()  # → _is_game_over = True
        self.game_core.update()  # → _game_over_popup 生成
        self._tap_game_over_popup()

        self.game_core.update()

        self.assertTrue(self.game_core.needs_reset())


class TestGameCorePendingGameOver(TestParent):
    """疲労値 0 時の釣り上げ→ゲームオーバーポップアップ順次表示のテスト"""

    def setUp(self):
        super().setUp()
        self.game_core = GameCore()
        self.game_core._fatigue = 0  # pylint: disable=W0212
        # 魚をセットし FINISHED_SUCCESS 状態を直接設定
        _append_fish(self.game_core)
        self.fish = self.game_core.fish_list[0]
        self.fish._is_hit = True  # pylint: disable=W0212
        self.game_core._following_fish = self.fish  # pylint: disable=W0212
        self.game_core.hook._state = HookState.FINISHED_SUCCESS  # pylint: disable=W0212

    def _do_finished_success_update(self):
        """疲労値 0 で FINISHED_SUCCESS を update() で処理する"""
        self.game_core.update()

    def test_draw_shows_fish_catch_popup_not_game_over_popup_immediately_after_zero_fatigue_success(
        self,
    ):
        """疲労値 0 + FINISHED_SUCCESS 直後の draw() で釣り上げポップアップが描画され、ゲームオーバーポップアップは描画されないこと"""
        fish_score = self.fish.get_score()
        self._do_finished_success_update()
        self.test_view.call_params = []

        self.game_core.draw()

        expected = _build_full_expected_calls(
            fatigue=0, score=fish_score
        ) + _build_popup_expected_calls(
            self.fish.fish_rarity, self.fish.fish_size, fish_score
        )
        self.assertEqual(self.test_view.get_call_params(), expected)

    def test_draw_shows_game_over_popup_after_fish_catch_popup_dismissed_with_zero_fatigue(
        self,
    ):
        """疲労値 0 + 釣り上げポップアップ解除後の draw() でゲームオーバーポップアップが描画されること"""
        fish_score = self.fish.get_score()
        self._do_finished_success_update()  # _popup 生成、_pending_game_over = True
        # 釣り上げポップアップをタップして解除（→ _is_game_over = True）
        px = FishCatchPopup.X + FishCatchPopup.W // 2
        py = FishCatchPopup.Y + FishCatchPopup.H // 2
        self.test_input.set_mouse_pressed(True)
        self.test_input.set_mouse_pos(px, py)
        self.game_core.update()  # _popup 解除 → _is_game_over = True
        self.test_input.set_mouse_pressed(
            False
        )  # タップ解除（game_over_popup を即時解除しない）
        self.game_core.update()  # _game_over_popup 生成
        self.test_view.call_params = []

        self.game_core.draw()

        expected = _build_full_expected_calls(
            fatigue=0, score=fish_score
        ) + _build_game_over_popup_expected_calls(fish_score)
        self.assertEqual(self.test_view.get_call_params(), expected)


class TestPyxelControllerReset(TestParent):
    """PyxelController によるゲームリセット動作のテスト"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def test_pyxel_controller_replaces_game_core_when_needs_reset(self):
        """PyxelController.update() で needs_reset() が True のとき GameCore が新しいインスタンスに置き換えられる"""
        controller = PyxelController()
        original_game_core = controller.game_core
        original_game_core._needs_reset = True  # pylint: disable=W0212

        controller.update()

        self.assertIsNot(controller.game_core, original_game_core)

    def test_replaced_game_core_has_false_needs_reset(self):
        """リセット後の新しい GameCore の needs_reset() は False である"""
        controller = PyxelController()
        controller.game_core._needs_reset = True  # pylint: disable=W0212

        controller.update()

        self.assertFalse(controller.game_core.needs_reset())


if __name__ == "__main__":
    unittest.main()
