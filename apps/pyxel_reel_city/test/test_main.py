import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import (  # pylint: disable=C0413
    IView,
    IGridView,
    IInput,
    GameCore,
    BetMultiplier,
)
from reel import Reel, ReelSymbol  # pylint: disable=C0413
from city import City, CityGrid  # pylint: disable=C0413


def make_reel_draw_calls(text="0", frame_col=7, bg_col=None):
    if bg_col is None:
        bg_col = GameCore.RESULT_BG_COLORS[ReelSymbol(int(text))]
    cx, cy, r = GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y, GameCore.REEL_RADIUS
    tx = cx - GameCore.CHAR_W // 2
    ty = cy - GameCore.CHAR_H // 2
    return [
        ("draw_circ", cx, cy, r, bg_col),
        ("draw_circb", cx, cy, r, frame_col),
        ("draw_text", tx, ty, text),
    ]


def make_funds_draw_calls(text="0"):
    pad_x = GameCore.FUNDS_PAD_X
    pad_y = GameCore.FUNDS_PAD_Y
    fw = GameCore.ICON_SIZE + GameCore.ICON_GAP + GameCore.FUNDS_FRAME_DIGITS * GameCore.CHAR_W + pad_x * 2
    fh = GameCore.CHAR_H + pad_y * 2
    fx = GameCore.SCREEN_W - fw - GameCore.FUNDS_MARGIN
    fy = GameCore.FUNDS_Y
    icon_x = fx + 2
    icon_y = fy + 2
    tx = fx + GameCore.ICON_SIZE + GameCore.ICON_GAP + pad_x
    ty = fy + pad_y
    return [
        ("draw_rect", fx, fy, fw, fh, GameCore.FUNDS_FRAME_COL),
        ("draw_blt", icon_x, icon_y, 0, GameCore.FUNDS_ICON_U, GameCore.FUNDS_ICON_V, GameCore.ICON_SIZE, GameCore.ICON_SIZE, 0),
        ("draw_rectb", fx, fy, fw, fh, GameCore.FUNDS_FRAME_BORDER_COL),
        ("draw_text", tx, ty, text),
    ]


def make_population_draw_calls(text="1"):
    icon_x = GameCore.POPULATION_X + 2
    icon_y = GameCore.POPULATION_Y + 2
    pad_x = GameCore.FUNDS_PAD_X
    pad_y = GameCore.FUNDS_PAD_Y
    fw = GameCore.ICON_SIZE + GameCore.ICON_GAP + GameCore.FUNDS_FRAME_DIGITS * GameCore.CHAR_W + pad_x * 2
    fh = GameCore.CHAR_H + pad_y * 2
    fx = GameCore.POPULATION_X
    fy = GameCore.POPULATION_Y
    tx = fx + GameCore.ICON_SIZE + GameCore.ICON_GAP + pad_x
    ty = fy + pad_y
    return [
        ("draw_rect", fx, fy, fw, fh, GameCore.FUNDS_FRAME_COL),
        ("draw_blt", icon_x, icon_y, 0, GameCore.POPULATION_ICON_U, GameCore.POPULATION_ICON_V, GameCore.ICON_SIZE, GameCore.ICON_SIZE, 0),
        ("draw_rectb", fx, fy, fw, fh, GameCore.FUNDS_FRAME_BORDER_COL),
        ("draw_text", tx, ty, text),
    ]


def make_bet_button_draw_calls(text="x10", frame_col=7):
    cx, cy, r = GameCore.BET_CENTER_X, GameCore.BET_CENTER_Y, GameCore.BET_RADIUS
    tx = cx - len(text) * GameCore.CHAR_W // 2
    ty = cy - GameCore.CHAR_H // 2
    return [
        ("draw_circ", cx, cy, r, 0),
        ("draw_circb", cx, cy, r, frame_col),
        ("draw_text", tx, ty, text),
    ]


def make_reset_button_draw_calls():
    cx, cy, r = GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y, GameCore.REEL_RADIUS
    label = "RESET"
    tx = cx - len(label) * GameCore.CHAR_W // 2
    ty = cy - GameCore.CHAR_H // 2
    return [
        ("draw_circ", cx, cy, r, 0),
        ("draw_circb", cx, cy, r, GameCore.COL_FRAME_ACTIVE),
        ("draw_text", tx, ty, label),
    ]


def make_streak_mark_draw_calls(streak):
    """streak 状態に応じたマーク draw_blt 呼び出しリストを返す（描画順序を保証）"""
    w, h, y = GameCore.STREAK_MARK_W, GameCore.STREAK_MARK_H, GameCore.STREAK_MARK_Y
    if streak == 2:
        return [
            (
                "draw_blt",
                GameCore.STREAK_MARK1_X,
                y,
                0,
                0,
                GameCore.STREAK_GRAY_V,
                w,
                h,
                0,
            )
        ]
    if streak == 3:
        return [
            (
                "draw_blt",
                GameCore.STREAK_MARK2_X0,
                y,
                0,
                0,
                GameCore.STREAK_YELLOW_V,
                w,
                h,
                0,
            ),
            (
                "draw_blt",
                GameCore.STREAK_MARK2_X1,
                y,
                0,
                0,
                GameCore.STREAK_YELLOW_V,
                w,
                h,
                0,
            ),
        ]
    return []


def make_popup_draw_calls():
    yes_tx = GameCore.POPUP_YES_CX - len("YES") * GameCore.CHAR_W // 2 + 1
    yes_ty = GameCore.POPUP_YES_CY - GameCore.CHAR_H // 2
    no_tx = GameCore.POPUP_NO_CX - len("NO") * GameCore.CHAR_W // 2 + 1
    no_ty = GameCore.POPUP_NO_CY - GameCore.CHAR_H // 2
    return [
        (
            "draw_rect",
            GameCore.POPUP_X,
            GameCore.POPUP_Y,
            GameCore.POPUP_W,
            GameCore.POPUP_H,
            1,
        ),
        (
            "draw_rectb",
            GameCore.POPUP_X,
            GameCore.POPUP_Y,
            GameCore.POPUP_W,
            GameCore.POPUP_H,
            7,
        ),
        ("draw_text", GameCore.POPUP_MSG_X, GameCore.POPUP_Y + 8, GameCore.POPUP_MSG),
        (
            "draw_circ",
            GameCore.POPUP_YES_CX,
            GameCore.POPUP_YES_CY,
            GameCore.POPUP_BTN_R,
            0,
        ),
        (
            "draw_circb",
            GameCore.POPUP_YES_CX,
            GameCore.POPUP_YES_CY,
            GameCore.POPUP_BTN_R,
            7,
        ),
        ("draw_text", yes_tx, yes_ty, "YES"),
        (
            "draw_circ",
            GameCore.POPUP_NO_CX,
            GameCore.POPUP_NO_CY,
            GameCore.POPUP_BTN_R,
            0,
        ),
        (
            "draw_circb",
            GameCore.POPUP_NO_CX,
            GameCore.POPUP_NO_CY,
            GameCore.POPUP_BTN_R,
            7,
        ),
        ("draw_text", no_tx, no_ty, "NO"),
    ]


def make_grid_draw_calls(level_map, variant):
    return [
        ("draw", col, row, level_map.get((col, row), 0), variant)
        for col in range(City.COLUMN_NUM)
        for row in range(City.ROW_NUM)
    ]


def make_city_dict(level_map, variant, rest_growth=0, funds=0):
    return {
        "column_num": City.COLUMN_NUM,
        "row_num": City.ROW_NUM,
        "rest_growth": rest_growth,
        "funds": funds,
        "grid_states": [
            [
                {"level": level_map.get((col, row), 0), "variant": variant}
                for row in range(City.ROW_NUM)
            ]
            for col in range(City.COLUMN_NUM)
        ],
    }


class TestInput(IInput):
    def __init__(self):
        self._mouse_pressed = False
        self._mouse_x = 0
        self._mouse_y = 0

    def is_mouse_btn_pressed(self) -> bool:
        return self._mouse_pressed

    def set_mouse_pressed(self, val: bool):
        self._mouse_pressed = val

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y

    def set_mouse_pos(self, x: int, y: int):
        self._mouse_x = x
        self._mouse_y = y


class TestView(IView):
    def __init__(self):
        self._call_params = []

    def draw_text(self, x, y, text, col=7):
        self._call_params.append(("draw_text", x, y, text))

    def draw_rect(self, x, y, w, h, col):
        self._call_params.append(("draw_rect", x, y, w, h, col))

    def draw_rectb(self, x, y, w, h, col):
        self._call_params.append(("draw_rectb", x, y, w, h, col))

    def draw_circ(self, x, y, r, col):
        self._call_params.append(("draw_circ", x, y, r, col))

    def draw_circb(self, x, y, r, col):
        self._call_params.append(("draw_circb", x, y, r, col))

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self._call_params.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def get_call_params(self):
        return self._call_params


class TestGridView(IGridView):
    def __init__(self):
        self._draw_calls = []

    def draw(self, col, row, level, variant):
        self._draw_calls.append(("draw", col, row, level, variant))

    def get_draw_calls(self):
        return self._draw_calls


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.test_grid_view = TestGridView()
        self.test_input = TestInput()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.mock_view = self.patcher_view.start()
        self.patcher_grid_view = patch(
            "main.PyxelGridView.create", return_value=self.test_grid_view
        )
        self.mock_grid_view = self.patcher_grid_view.start()
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_input = self.patcher_input.start()
        self.patcher_store = patch("main.ReportStore")
        self.mock_store_class = self.patcher_store.start()
        self.mock_store_class.return_value.load.return_value = None

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_grid_view.stop()
        self.patcher_input.stop()
        self.patcher_store.stop()

    def _run_full_spin(self, core, choice_fn):
        """資金セット → reel クリック → SPIN_DURATION フレーム完走のヘルパー"""
        threshold = core._bet_multiplier.current  # pylint: disable=W0212
        core._city._funds = threshold  # pylint: disable=W0212
        self.test_input.set_mouse_pos(GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        with patch("reel.random.choice", side_effect=choice_fn):
            core.update()
        self.test_input.set_mouse_pressed(False)
        with patch("reel.random.choice", side_effect=choice_fn):
            for _ in range(Reel.SPIN_DURATION - 1):
                core.update()


class TestGameCore(TestParent):
    def test_draw_covers_all_positions(self):
        """全 (col, row) が正しい順序・level/variant で描画されること"""
        core = GameCore()
        core.draw()
        expected_calls = [
            (
                "draw",
                col,
                row,
                core._city.get_grid_level(col, row),  # pylint: disable=W0212
                core._city.get_grid_variant(col, row),  # pylint: disable=W0212
            )
            for col in range(City.COLUMN_NUM)
            for row in range(City.ROW_NUM)
        ]
        self.assertEqual(expected_calls, self.test_grid_view.get_draw_calls())

    def test_draw_ui_calls_in_order(self):
        """GameCore.draw() がリール・資金・人口・掛金ボタンのUI描画を正しい順序で出力すること"""
        core = GameCore()
        core.draw()
        self.assertEqual(
            make_reel_draw_calls(frame_col=5)
            + make_funds_draw_calls()
            + make_population_draw_calls()
            + make_bet_button_draw_calls(),
            self.test_view.get_call_params(),
        )

    def test_needs_reset_initial_value_is_false(self):
        """needs_reset() の初期値が False であること"""
        core = GameCore()
        self.assertFalse(core.needs_reset)


class TestGameCoreSaveLoad(TestParent):
    def test_save_includes_city(self):
        """初回起動時に City のデータが ReportStore.save() に含まれること"""
        core = GameCore()
        mock_store = self.mock_store_class.return_value
        saved = mock_store.save.call_args[0][0]
        self.assertIn("city", saved)
        self.assertEqual(core._city.to_dict(), saved["city"])  # pylint: disable=W0212

    def test_load_on_init(self):
        """load_data フラグと保存データの有無に応じて City の grid が正しく描画されること"""
        center_col = City.COLUMN_NUM // 2
        center_row = City.ROW_NUM // 2

        # (saved_level_map, load_data, expected_variant, expected_level_map)
        cases = [
            (
                {(center_col, center_row): 2},
                True,
                3,
                {(center_col, center_row): 2},
            ),  # 保存データから復元
            (None, True, 5, {(center_col, center_row): 1}),  # 保存データなし → 新規作成
            (
                {(center_col, center_row): 2},
                False,
                5,
                {(center_col, center_row): 1},
            ),  # 保存データあり・load_data=False → 初期状態
        ]
        for saved_level_map, load_data, expected_variant, expected_level_map in cases:
            with self.subTest(saved_level_map=saved_level_map, load_data=load_data):
                store_data = (
                    {
                        "city": make_city_dict(saved_level_map, variant=3),
                        "reel_streak": {"last_result": None, "streak": 0},
                    }
                    if saved_level_map
                    else None
                )
                self.mock_store_class.return_value.load.return_value = store_data
                self.test_grid_view.get_draw_calls().clear()
                with patch("city.random.randint", return_value=5):
                    core = GameCore(load_data=load_data)
                core.draw()
                self.assertEqual(
                    make_grid_draw_calls(expected_level_map, expected_variant),
                    self.test_grid_view.get_draw_calls(),
                )


class TestGameCoreFundsDynamic(TestParent):
    def test_funds_increase_shown_after_60_updates(self):
        """60フレーム経過後に city.funds が 1 増加し、draw() がその実値を正しい順序で描画すること

        初期状態: 中央グリッドのみ level=1 → グリッドレベル合計=1
        → 60フレーム後に funds=1 となり、draw() が "1" を表示する
        """
        core = GameCore()
        for _ in range(60):
            core.update()
        # 初期グリッドレベル合計=1 なので 60 フレーム後の期待値は 1
        self.assertEqual(core._city.funds, 1)  # pylint: disable=W0212
        core.draw()
        expected_calls = (
            make_reel_draw_calls(frame_col=5)
            + make_funds_draw_calls("1")
            + make_population_draw_calls("1")
            + make_bet_button_draw_calls()
        )
        self.assertEqual(expected_calls, self.test_view.get_call_params())


class TestGameCoreAutoSave(TestParent):
    def test_auto_save_every_600_frames(self):
        """update() が 600 フレームごとに自動保存（_save()）を実行すること"""
        core = GameCore()
        mock_store = self.mock_store_class.return_value
        save_count_after_init = mock_store.save.call_count

        # 599 フレーム時点では自動保存されない
        for _ in range(599):
            core.update()
        self.assertEqual(mock_store.save.call_count, save_count_after_init)

        # 600 フレーム目に自動保存が実行される
        core.update()  # 600 回目
        self.assertEqual(mock_store.save.call_count, save_count_after_init + 1)

        # さらに 600 フレーム後に再び保存される
        for _ in range(600):
            core.update()
        self.assertEqual(mock_store.save.call_count, save_count_after_init + 2)


class TestGameCoreReelClick(TestParent):
    def test_update_clicks_reel_when_mouse_in_reel_area(self):
        """update() でリール枠内をクリック→スピン停止後に City が成長し描画に反映されること

        side_effect=lambda lst: lst[3] により決定的に制御:
          - Reel.update() 停止時: random.choice((0,1,2,3)) → RESULT_VALUES[3] = 3
          - City.apply_growth(3): random.choice(candidate_map[2]) → lst[3] = (8, 18)
            ※ candidate_map[2] = [(6,18),(7,17),(7,19),(8,18)]（生成順序より）
            ※ _rest_growth = 3 - 2 = 1 < 2 のためループ終了、(8,18) のみレベルアップ
        """
        with patch("city.random.randint", return_value=5):
            core = GameCore()

        # クリック → スピン完了（SPIN_DURATION フレーム）
        # side_effect=lst[3]: Reel停止時→出目3、City成長時→(8,18)を選択
        self._run_full_spin(core, lambda lst: lst[3])

        core.draw()

        # グリッド描画: center(7,18)=level1、(8,18)=level1、他=level0、variant=5
        center_x, center_y = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        expected_level_map = {
            (center_x, center_y): 1,  # 初期センター
            (center_x + 1, center_y): 1,  # クリックでレベルアップ
        }
        self.assertEqual(
            make_grid_draw_calls(expected_level_map, 5),
            self.test_grid_view.get_draw_calls(),
        )

        # リール描画: 出目 "3" が表示されること
        # 合計 90 フレーム経過（1 + 89）→ 60 フレーム時点で funds += 初期グリッドレベル合計(=1)
        # 人口: center(lv=1) + (8,18)(lv=1) = 2
        # funds=1, threshold=10 → ACCUMULATING → col=5
        self.assertEqual(
            make_reel_draw_calls("3", frame_col=5)
            + make_funds_draw_calls("1")
            + make_population_draw_calls("2")
            + make_bet_button_draw_calls(),
            self.test_view.get_call_params(),
        )

        # 保存: クリック後の city が正しく保存されること
        # rest_growth = apply_growth(3) 後: 3 - 2(min_required) = 1
        # funds = 1（90フレーム経過、60フレーム時点で初期グリッドレベル合計=1が加算）
        saved = self.mock_store_class.return_value.save.call_args[0][0]
        expected_city = make_city_dict(
            level_map=expected_level_map,
            variant=5,
            rest_growth=1,
            funds=1,
        )
        self.assertEqual(expected_city, saved["city"])

    def test_update_reel_spinning_immediately_after_click(self):
        """update() でリール枠内をクリックした直後はリール表示が "0"・City 未成長・保存なしであること"""
        with patch("city.random.randint", return_value=5):
            core = GameCore()

        mock_store = self.mock_store_class.return_value
        save_count_before = mock_store.save.call_count

        core._city._funds = BetMultiplier.STAGES[  # pylint: disable=W0212
            0
        ]  # bet=10, threshold=10
        self.test_input.set_mouse_pos(GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()

        core.draw()

        # グリッド描画: City 未成長（初期状態と同じ）
        center_x, center_y = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        self.assertEqual(
            make_grid_draw_calls({(center_x, center_y): 1}, 5),
            self.test_grid_view.get_draw_calls(),
        )

        # リール描画: スピン中 1 フレーム後（elapsed=1, interval=1, idx=1）→ "1"、SPINNING → col=5
        # bet 枠: スピン中 → グレー（col=5）
        self.assertEqual(
            make_reel_draw_calls("1", frame_col=5)
            + make_funds_draw_calls()
            + make_population_draw_calls("1")
            + make_bet_button_draw_calls(frame_col=5),
            self.test_view.get_call_params(),
        )

        # 保存: クリック直後は save が呼ばれていないこと
        self.assertEqual(mock_store.save.call_count, save_count_before)

    def test_reel_click_boundary(self):
        """リール円の境界値でクリック判定が正しく動作すること"""
        cx = GameCore.REEL_CENTER_X
        cy = GameCore.REEL_CENTER_Y
        r = GameCore.REEL_RADIUS
        # (mx, my, expect_clicked, label)
        cases = [
            (cx, cy, True, "中心"),
            (cx + r, cy, True, "右境界（内側）"),
            (cx - r, cy, True, "左境界（内側）"),
            (cx, cy + r, True, "下境界（内側）"),
            (cx, cy - r, True, "上境界（内側）"),
            (cx + r + 1, cy, False, "右境界外"),
            (cx - r - 1, cy, False, "左境界外"),
            (cx, cy + r + 1, False, "下境界外"),
            (cx, cy - r - 1, False, "上境界外"),
        ]
        for mx, my, expect_clicked, label in cases:
            with self.subTest(label):
                core = GameCore()
                core._city._funds = BetMultiplier.STAGES[  # pylint: disable=W0212
                    0
                ]  # bet=10, threshold=10
                self.test_input.set_mouse_pos(mx, my)
                self.test_input.set_mouse_pressed(True)
                with patch("reel.random.choice", return_value=1):
                    core.update()
                if expect_clicked:
                    self.assertTrue(core._reel.is_spinning)  # pylint: disable=W0212
                else:
                    self.assertFalse(core._reel.is_spinning)  # pylint: disable=W0212


class TestBetMultiplier(unittest.TestCase):
    def test_next_cycles_through_stages(self):
        """初期倍率は 10 で、next() を呼ぶたびに 10 → 100 → 1000 → 10000 → 10 と循環すること"""
        bet = BetMultiplier()
        self.assertEqual(bet.current, 10)
        bet.next()
        self.assertEqual(bet.current, 100)
        bet.next()
        self.assertEqual(bet.current, 1000)
        bet.next()
        self.assertEqual(bet.current, 10000)
        bet.next()
        self.assertEqual(bet.current, 10)


class TestGameCoreGrowthWithBet(TestParent):
    def test_growth_with_multiplier_100(self):
        """掛金倍率100のとき、出目×成長倍率の成長量が City に適用され描画に反映されること

        side_effect=lambda lst: lst[min(1, len(lst)-1)] により決定的に制御:
          - Reel.update() 停止時: random.choice((0,1,2,3)) → RESULT_VALUES[1] = 1
          - City.apply_growth(8): 出目1 × 成長倍率8
            ※ candidate_map[2] = [(6,18),(7,17),(7,19),(8,18)]（中心隣接4グリッド）
            ※ 1回目 → (7,17), 2回目 → (7,19), 3回目 → (8,18), 4回目 → (6,18)
            ※ rest_growth = 8 - 2*4 = 0、candidate_map[2] 消滅後 min=5, 0<5 でループ終了
        """
        with patch("city.random.randint", return_value=5):
            core = GameCore()

        # 掛金倍率を 100 に設定（next() 1回: 10→100）
        core._bet_multiplier.next()  # pylint: disable=W0212

        # クリック → スピン完了（SPIN_DURATION フレーム）
        # side_effect=lst[min(1,len-1)]: Reel停止時→出目1、City成長時→候補リスト先頭側を選択
        self._run_full_spin(core, lambda lst: lst[min(1, len(lst) - 1)])

        core.draw()

        # グリッド描画: center(7,18)=level1 + 隣接4グリッドがレベルアップ
        center_x, center_y = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        expected_level_map = {
            (center_x, center_y): 1,  # 初期センター
            (center_x, center_y - 1): 1,  # (7,17)
            (center_x, center_y + 1): 1,  # (7,19)
            (center_x + 1, center_y): 1,  # (8,18)
            (center_x - 1, center_y): 1,  # (6,18)
        }
        self.assertEqual(
            make_grid_draw_calls(expected_level_map, 5),
            self.test_grid_view.get_draw_calls(),
        )

        # UI描画: 出目 "1"、funds=1（60フレーム時点で人口1が加算）、
        # population=5（center + 隣接4）、bet="x100"
        # funds=1, threshold=100(bet=100) → ACCUMULATING → col=5
        self.assertEqual(
            make_reel_draw_calls("1", frame_col=5)
            + make_funds_draw_calls("1")
            + make_population_draw_calls("5")
            + make_bet_button_draw_calls("x100"),
            self.test_view.get_call_params(),
        )

        # 保存: rest_growth = 8 - 2*4 = 0, funds=1
        saved = self.mock_store_class.return_value.save.call_args[0][0]
        expected_city = make_city_dict(
            level_map=expected_level_map,
            variant=5,
            rest_growth=0,
            funds=1,
        )
        self.assertEqual(expected_city, saved["city"])

    @patch("city.random.choice")
    def test_rest_growth_for_each_multiplier(self, mock_city_choice):
        """各掛金倍率でリールを回したとき GameCore._city._rest_growth が正しく蓄積されること

        すべてのグリッドをレベル3（MAX_LEVEL-1）にすると次レベルアップコスト最小 = 5^3 = 125。
        出目 1（main.random.choice → lst[min(1,len-1)] = RESULT_VALUES[1] = 1）で確認する。

        x10/x100/x1000: growth（1,8,64）< 125 → レベルアップなし → _rest_growth == growth
        x10000: growth=512 → 512 - 125(center lv3→4) - 126×3(隣接3グリッド lv3→4) = 9
        """
        mock_city_choice.side_effect = lambda lst: lst[0]
        cases = [
            ("x10", 0, 1),
            ("x100", 1, 8),
            ("x1000", 2, 64),
            ("x10000", 3, 512 - 125 - 126 * 3),
        ]
        for label, num_next, expected_rest_growth in cases:
            with self.subTest(label=label):
                core = GameCore()
                for _ in range(num_next):
                    core._bet_multiplier.next()  # pylint: disable=W0212
                for col in core._city._grid_table:  # pylint: disable=W0212
                    for grid in col:
                        while grid.level < CityGrid.MAX_LEVEL - 1:
                            grid.level_up()
                self._run_full_spin(core, lambda lst: lst[min(1, len(lst) - 1)])
                self.assertEqual(
                    expected_rest_growth,
                    core._city._rest_growth,  # pylint: disable=W0212
                )


class TestGameCoreSpinCost(TestParent):
    # (label, initial_funds, expected_spinning, expected_funds_after)
    _T = BetMultiplier.STAGES[0]  # threshold (初期 bet=10)
    CASES = [
        ("資金不足 (funds=0 < threshold)", 0, False, 0),
        ("資金ちょうど閾値 (funds=threshold)", _T, True, 0),
        ("資金が閾値超過 (funds=threshold+5)", _T + 5, True, 5),
    ]

    def test_reel_click_spin_and_funds(self):
        """初期資金に応じてリール操作の可否と資金消費が正しく動作すること"""
        for label, initial_funds, expected_spinning, expected_funds in self.CASES:
            with self.subTest(label):
                core = GameCore()
                core._city._funds = initial_funds  # pylint: disable=W0212
                self.test_input.set_mouse_pos(
                    GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y
                )
                self.test_input.set_mouse_pressed(True)
                core.update()
                self.assertEqual(
                    expected_spinning, core._reel.is_spinning  # pylint: disable=W0212
                )
                self.assertEqual(
                    expected_funds, core._city.funds  # pylint: disable=W0212
                )

    # (label, initial_funds, do_bet_next, do_reel_click,
    #  expected_frame_col, expected_reel_text, expected_funds_text, expected_bet_text, expected_spinning)
    # draw チェックはクリック後の最終状態で実施（クリック失敗時は資金そのまま）
    # スピン中 1 update 後: elapsed=1, interval=1, idx=1 → display_text="1"
    REEL_STATE_CASES = [
        ("資金不足: グレー枠・スピン不可", 0, False, False, 5, "0", "0", "x10", False),
        (
            "資金十分・クリックなし: 白枠・スピン不可",
            _T,
            False,
            False,
            7,
            "0",
            str(_T),
            "x10",
            False,
        ),
        (
            "資金十分・クリック: スピン中（グレー枠・資金消費後）",
            _T,
            False,
            True,
            5,
            "1",
            "0",
            "x10",
            True,
        ),
        (
            "bet増加で閾値超過・クリック試行: グレー枠・スピン不可（資金消費なし）",
            _T,
            True,
            True,
            5,
            "0",
            str(_T),
            "x100",
            False,
        ),
        (
            "bet増加後も閾値以内・クリック: スピン中（グレー枠・資金消費後）",
            _T * 10,
            True,
            True,
            5,
            "1",
            "0",
            "x100",
            True,
        ),
    ]

    def test_reel_state_draw_and_spin(self):
        """資金・bet・クリック状態に応じてreel枠色とスピン状態が正しく連動すること"""
        for (
            label,
            initial_funds,
            do_bet_next,
            do_reel_click,
            expected_frame_col,
            expected_reel_text,
            expected_funds_text,
            expected_bet_text,
            expected_spinning,
        ) in self.REEL_STATE_CASES:
            with self.subTest(label):
                core = GameCore()
                core._city._funds = initial_funds  # pylint: disable=W0212
                if do_bet_next:
                    core._bet_multiplier.next()  # pylint: disable=W0212
                if do_reel_click:
                    self.test_input.set_mouse_pos(
                        GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y
                    )
                    self.test_input.set_mouse_pressed(True)
                    core.update()
                    self.test_input.set_mouse_pressed(False)
                self.test_view.get_call_params().clear()  # subTest間の蓄積を防ぐ
                core.draw()
                expected_bet_frame_col = 5 if expected_spinning else 7
                self.assertEqual(
                    make_reel_draw_calls(
                        expected_reel_text, frame_col=expected_frame_col
                    )
                    + make_funds_draw_calls(expected_funds_text)
                    + make_population_draw_calls()
                    + make_bet_button_draw_calls(
                        expected_bet_text, frame_col=expected_bet_frame_col
                    ),
                    self.test_view.get_call_params(),
                )
                self.assertEqual(
                    expected_spinning, core._reel.is_spinning  # pylint: disable=W0212
                )


class TestGameCoreBetButton(TestParent):
    def test_bet_button_position(self):
        """別途ボタンが左と下に8pxの余白になる位置にあること"""
        margin = 8
        self.assertEqual(GameCore.BET_CENTER_X, margin + GameCore.BET_RADIUS)
        self.assertEqual(
            GameCore.BET_CENTER_Y, GameCore.SCREEN_H - margin - GameCore.BET_RADIUS
        )

    def test_click_bet_boundary(self):
        """掛金ボタンの円形境界値クリック判定が正しく動作すること"""
        cx = GameCore.BET_CENTER_X
        cy = GameCore.BET_CENTER_Y
        r = GameCore.BET_RADIUS
        # (mx, my, expect_changed, label)
        cases = [
            (cx, cy, True, "中心"),
            (cx + r, cy, True, "右端（境界内）"),
            (cx - r, cy, True, "左端（境界内）"),
            (cx, cy + r, True, "下端（境界内）"),
            (cx, cy - r, True, "上端（境界内）"),
            (cx + r + 1, cy, False, "右端外"),
            (cx - r - 1, cy, False, "左端外"),
            (cx, cy + r + 1, False, "下端外"),
            (cx, cy - r - 1, False, "上端外"),
            (cx + r, cy + r, False, "斜め角（円外）"),
            (
                GameCore.REEL_CENTER_X,
                GameCore.REEL_CENTER_Y,
                False,
                "リール領域内",
            ),
        ]
        for mx, my, expect_changed, label in cases:
            with self.subTest(label):
                core = GameCore()
                self.test_input.set_mouse_pos(mx, my)
                self.test_input.set_mouse_pressed(True)
                core.update()
                if expect_changed:
                    self.assertEqual(
                        core._bet_multiplier.current, 100  # pylint: disable=W0212
                    )
                else:
                    self.assertEqual(
                        core._bet_multiplier.current, 10  # pylint: disable=W0212
                    )

    def test_bet_click_ignored_during_spinning(self):
        """SPINNING 中に bet クリック → 倍率変更されない"""
        core = GameCore()
        threshold = core._bet_multiplier.current  # pylint: disable=W0212
        core._city._funds = threshold  # pylint: disable=W0212
        # reel クリック → SPINNING
        self.test_input.set_mouse_pos(GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertTrue(core._reel.is_spinning)  # pylint: disable=W0212
        self.test_input.set_mouse_pressed(False)
        # bet クリック → 無視されるべき
        self.test_input.set_mouse_pos(GameCore.BET_CENTER_X, GameCore.BET_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertEqual(
            core._bet_multiplier.current, 10  # pylint: disable=W0212
        )  # 変化なし

    # (label, initial_funds, do_spin, expected_reel_col, expected_reel_text, expected_funds_text, expected_bet_frame_col)
    # スピン中 1 update 後: elapsed=1, interval=1, idx=1 → display_text="1"
    BET_FRAME_CASES = [
        ("非スピン中: 白枠（col=7）", 0, False, 5, "0", "0", 7),
        (
            "SPINNING 中: グレー枠（col=5）",
            BetMultiplier.STAGES[0],
            True,
            5,
            "1",
            "0",
            5,
        ),
    ]

    def test_bet_frame_color(self):
        """スピン状態に応じてbet枠色が正しく切り替わること"""
        for (
            label,
            initial_funds,
            do_spin,
            expected_reel_col,
            expected_reel_text,
            expected_funds_text,
            expected_bet_frame_col,
        ) in self.BET_FRAME_CASES:
            with self.subTest(label):
                core = GameCore()
                core._city._funds = initial_funds  # pylint: disable=W0212
                if do_spin:
                    self.test_input.set_mouse_pos(
                        GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y
                    )
                    self.test_input.set_mouse_pressed(True)
                    core.update()
                    self.test_input.set_mouse_pressed(False)
                self.test_view.get_call_params().clear()
                core.draw()
                self.assertEqual(
                    make_reel_draw_calls(
                        expected_reel_text, frame_col=expected_reel_col
                    )
                    + make_funds_draw_calls(expected_funds_text)
                    + make_population_draw_calls()
                    + make_bet_button_draw_calls(frame_col=expected_bet_frame_col),
                    self.test_view.get_call_params(),
                )


class TestReelBgColor(TestParent):
    """current_symbol に応じてリール背景色が変化すること"""

    # 出目シンボル → 背景色のマッピング
    RESULT_BG_COLORS = {
        ReelSymbol.ZERO: 0,
        ReelSymbol.ONE: 1,
        ReelSymbol.TWO: 3,
        ReelSymbol.THREE: 2,
    }

    def test_reel_bg_color_matches_result(self):
        """停止後の出目に応じてリール背景色（draw_rect の col）が切り替わること

        資金=0 のため _can_spin()=False → frame_col = COL_FRAME_INACTIVE = 5
        スピン停止後は is_spinning=False → bet 枠 = COL_FRAME_ACTIVE = 7
        """
        for symbol, expected_bg_col in self.RESULT_BG_COLORS.items():
            result_val = symbol.value
            with self.subTest(result_val=result_val):
                core = GameCore()
                with patch("reel.random.choice", return_value=result_val):
                    core._reel.click()  # pylint: disable=W0212
                    for _ in range(Reel.SPIN_DURATION):
                        core._reel.update()  # pylint: disable=W0212
                self.assertFalse(core._reel.is_spinning)  # pylint: disable=W0212
                self.assertEqual(core._reel.result, result_val)  # pylint: disable=W0212
                self.test_view.get_call_params().clear()
                core.draw()
                self.assertEqual(
                    make_reel_draw_calls(
                        str(result_val),
                        bg_col=expected_bg_col,
                        frame_col=GameCore.COL_FRAME_INACTIVE,
                    )
                    + make_funds_draw_calls()
                    + make_population_draw_calls()
                    + make_bet_button_draw_calls(),
                    self.test_view.get_call_params(),
                )

    def test_reel_bg_color_during_spinning(self):
        """スピン中も display_text に対応する背景色で描画されること

        速度漸減アルゴリズムにより display_text が変化するたびに背景色も連動して変わる。
        スピン中: is_spinning=True → reel/bet 枠ともに COL_FRAME_INACTIVE = 5

        期待値は TestReelDisplayText の速度漸減ケースと対応:
          elapsed=0  → text="0" → bg_col=0
          elapsed=1  → text="1" → bg_col=1
          elapsed=4  → text="0" → bg_col=0
          elapsed=45 → text="3" → bg_col=2
          elapsed=89 → text="0" → bg_col=0
        """
        # (updates_after_click, expected_display_text)
        cases = [
            (0, "0"),
            (1, "1"),
            (4, "0"),
            (45, "3"),
            (89, "0"),
        ]
        for updates, expected_text in cases:
            with self.subTest(updates=updates):
                core = GameCore()
                core._reel.click()  # pylint: disable=W0212
                for _ in range(updates):
                    core._reel.update()  # pylint: disable=W0212
                self.assertTrue(core._reel.is_spinning)  # pylint: disable=W0212
                self.assertEqual(
                    core._reel.display_text, expected_text  # pylint: disable=W0212
                )
                expected_bg_col = self.RESULT_BG_COLORS[ReelSymbol(int(expected_text))]
                self.test_view.get_call_params().clear()
                core.draw()
                self.assertEqual(
                    make_reel_draw_calls(
                        expected_text,
                        bg_col=expected_bg_col,
                        frame_col=GameCore.COL_FRAME_INACTIVE,
                    )
                    + make_funds_draw_calls()
                    + make_population_draw_calls()
                    + make_bet_button_draw_calls(frame_col=GameCore.COL_FRAME_INACTIVE),
                    self.test_view.get_call_params(),
                )


class TestGameCorePopup(TestParent):
    def _make_game_over_core(self):
        """全グリッドを MAX_LEVEL にし is_game_over を True にした GameCore を生成"""
        core = GameCore()
        for col in core._city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()
        core._city.apply_growth(9999)  # pylint: disable=W0212
        return core

    def test_popup_drawn_when_reset_button_clicked_in_game_over(self):
        """ゲームオーバー時にリセットボタンをクリックするとポップアップが最前面に描画されること"""
        core = self._make_game_over_core()
        self.test_input.set_mouse_pos(GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()
        core.draw()
        self.assertEqual(
            make_reset_button_draw_calls()
            + make_funds_draw_calls()
            + make_population_draw_calls()
            + make_bet_button_draw_calls()
            + make_popup_draw_calls(),
            self.test_view.get_call_params(),
        )

    def test_reel_click_ignored_during_popup(self):
        """ポップアップ中はリール領域クリックを無視すること"""
        core = GameCore()
        core._city._funds = BetMultiplier.STAGES[0]  # pylint: disable=W0212
        core._popup_shown = True  # pylint: disable=W0212
        self.test_input.set_mouse_pos(GameCore.REEL_CENTER_X, GameCore.REEL_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertTrue(core._popup_shown)  # pylint: disable=W0212
        self.assertFalse(core._reel.is_spinning)  # pylint: disable=W0212

    def test_bet_click_ignored_during_popup(self):
        """ポップアップ中は掛金領域クリックを無視すること"""
        core = GameCore()
        core._popup_shown = True  # pylint: disable=W0212
        before = core._bet_multiplier.current  # pylint: disable=W0212
        self.test_input.set_mouse_pos(GameCore.BET_CENTER_X, GameCore.BET_CENTER_Y)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertEqual(core._bet_multiplier.current, before)  # pylint: disable=W0212

    def test_no_button_closes_popup_and_preserves_city_state(self):
        """NO ボタンクリックでポップアップが閉じ、city の状態が変化しないこと"""
        core = GameCore()
        core._popup_shown = True  # pylint: disable=W0212
        core._city._funds = 9999  # pylint: disable=W0212
        funds_before = core._city.funds  # pylint: disable=W0212
        self.test_input.set_mouse_pos(GameCore.POPUP_NO_CX, GameCore.POPUP_NO_CY)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertFalse(core._popup_shown)  # pylint: disable=W0212
        self.assertEqual(core._city.funds, funds_before)  # pylint: disable=W0212

    def test_yes_button_sets_needs_reset(self):
        """ポップアップ中に YES ボタンをクリックすると needs_reset が True になること"""
        core = GameCore()
        core._popup_shown = True  # pylint: disable=W0212
        self.test_input.set_mouse_pos(GameCore.POPUP_YES_CX, GameCore.POPUP_YES_CY)
        self.test_input.set_mouse_pressed(True)
        core.update()
        self.assertTrue(core.needs_reset)


class TestGameCoreResetButton(TestParent):
    def _make_game_over_core(self):
        """全グリッドを MAX_LEVEL にし apply_growth で is_game_over を True にした GameCore を生成"""
        core = GameCore()
        for col in core._city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()
        core._city.apply_growth(9999)  # pylint: disable=W0212
        return core

    def test_draw_reel_shows_reset_button_when_game_over(self):
        """ゲームオーバー状態では draw() がリセットボタン・資金・人口・掛金を正しい順序で描画すること"""
        core = self._make_game_over_core()
        core.draw()
        self.assertEqual(
            make_reset_button_draw_calls()
            + make_funds_draw_calls()
            + make_population_draw_calls()
            + make_bet_button_draw_calls(),
            self.test_view.get_call_params(),
        )


class TestAppReset(TestParent):
    """App によるゲームリセット動作のテスト"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()
        from main import App as _App  # pylint: disable=C0415

        self.app_class = _App

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def test_app_replaces_core_when_needs_reset(self):
        """App.update() で needs_reset が True のとき _core が新しいインスタンスに置き換えられる"""
        app = self.app_class()
        original = app._core  # pylint: disable=W0212
        original._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertIsNot(app._core, original)  # pylint: disable=W0212

    def test_replaced_core_has_false_needs_reset(self):
        """リセット後の新しい _core の needs_reset は False である"""
        app = self.app_class()
        app._core._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertFalse(app._core.needs_reset)  # pylint: disable=W0212


class TestReelStreakDraw(TestParent):
    """連番状態に応じてリール下にマークが正しい順序で描画されること"""

    def _setup_reel_with_streak(self, core, result_value, streak):
        """リール出目・streak を直接設定（描画テスト用の決定的状態設定）"""
        core._reel._result = result_value  # pylint: disable=W0212
        core._reel._last_result = result_value  # pylint: disable=W0212
        core._reel._streak = streak  # pylint: disable=W0212

    def _expected_draw_calls(self, result_value, streak):
        # funds=0 < bet(10) → _can_spin()=False → reel 枠はグレー、is_spinning=False → bet 枠は白
        return (
            make_reel_draw_calls(
                str(result_value), frame_col=GameCore.COL_FRAME_INACTIVE
            )
            + make_streak_mark_draw_calls(streak)
            + make_funds_draw_calls("0")
            + make_population_draw_calls("1")
            + make_bet_button_draw_calls()
        )

    def test_draw_streak_mark(self):
        """streak 状態に応じて正しい描画順序で全コールが一致すること"""
        cases = [
            # (result_value, streak, ラベル)
            (2, 1, "初回（streak=1）: マークなし"),
            (2, 2, "2連続（streak=2）: 灰色マーク1個"),
            (2, 3, "3連続（streak=3）: 黄色マーク2個（左→右順）"),
            (2, 1, "4連続後リセット（streak=1）: マークなし"),
        ]
        for result_value, streak, label in cases:
            with self.subTest(label):
                core = GameCore()
                self._setup_reel_with_streak(core, result_value, streak)
                self.test_view.get_call_params().clear()  # subTest 間の蓄積を防ぐ
                core.draw()
                self.assertEqual(
                    self._expected_draw_calls(result_value, streak),
                    self.test_view.get_call_params(),
                )


class TestReelStreakSpecialGrid(TestParent):
    """streak==3 が City の特殊グリッド指定につながること（ID-014-5 Red）"""

    def _count_level5_grids(self, city):
        return sum(
            1
            for col in range(City.COLUMN_NUM)
            for row in range(City.ROW_NUM)
            if city.get_grid_level(col, row) == 5
        )

    def _spin_n_times(self, core, n):
        """同出目(2)を n 回成立させるヘルパー（city 候補リストの短縮に対応した安全な選択）"""
        for _ in range(n):
            self._run_full_spin(core, lambda lst: lst[min(2, len(lst) - 1)])

    # (num_spins, expected_level5_count, label)
    STREAK_LEVEL5_CASES = [
        (1, 0, "1 連続（streak=1）: レベル 5 グリッドなし"),
        (2, 0, "2 連続（streak=2）: レベル 5 グリッドなし"),
        (3, 1, "3 連続（streak=3）: レベル 5 グリッドが 1 箇所"),
        (4, 1, "4 連続リセット後（streak=1）: 3 回転目の 1 個のまま増えない"),
    ]

    def test_level5_grid_count_by_streak(self):
        """streak 数に応じてレベル 5 グリッドの個数が正しく制御されること"""
        for num_spins, expected_count, label in self.STREAK_LEVEL5_CASES:
            with self.subTest(label):
                core = GameCore()
                self._spin_n_times(core, num_spins)
                self.assertEqual(expected_count, self._count_level5_grids(core._city))  # pylint: disable=W0212


class TestReelStreakPersist(TestParent):
    """連番状態が保存・復元を通じて維持されること"""

    def _spin_twice_with_same_result(self, core):
        """同出目(2)を 2 回成立させて streak=2 にするヘルパー"""
        # lst[2] → RESULT_VALUES[2] == 2 (Reel)、City 成長対象選択にも同じ lambda を使用
        self._run_full_spin(core, lambda lst: lst[2])  # 1回目: streak=1
        self._run_full_spin(core, lambda lst: lst[2])  # 2回目: streak=2

    def test_streak_mark_drawn_after_load(self):
        """streak=2 で保存・復元した GameCore が正しい描画順序で灰色マークを描画すること"""
        core_a = GameCore()
        self._spin_twice_with_same_result(core_a)

        mock_store = self.mock_store_class.return_value
        saved_data = mock_store.save.call_args[0][0]
        mock_store.load.return_value = saved_data
        core_b = GameCore(load_data=True)

        self.test_view.get_call_params().clear()
        core_b.draw()

        # core_b: from_dict で生成したリールは result=None → "0" 表示・非スピン
        funds = core_b._city.funds  # pylint: disable=W0212
        can_spin = funds >= BetMultiplier.STAGES[0]
        frame_col = (
            GameCore.COL_FRAME_ACTIVE if can_spin else GameCore.COL_FRAME_INACTIVE
        )
        expected = (
            make_reel_draw_calls(
                core_b._reel.display_text, frame_col=frame_col  # pylint: disable=W0212
            )
            + make_streak_mark_draw_calls(2)
            + make_funds_draw_calls(str(funds))
            + make_population_draw_calls(
                str(core_b._city.population)  # pylint: disable=W0212
            )
            + make_bet_button_draw_calls()
        )
        self.assertEqual(expected, self.test_view.get_call_params())
