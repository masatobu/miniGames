import copy
import json
import os
import sys
import unittest
from collections import namedtuple
from unittest.mock import MagicMock, PropertyMock, patch

# main.py が `from save_store import ...` で読み込めるよう、src を検索パスに足す
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src import main  # pylint: disable=C0413
from src.main import (  # pylint: disable=C0413
    IView,
    IInput,
    GameCore,
    Item,
    ring_of,
    create_initial_field,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FIELD_SIZE,
    CELL_SIZE,
    CELL_PITCH,
    COLOR_OPENED_BG,
    COLOR_CLOSED_BG,
    COLOR_BORDER,
    COLOR_BLUE_TEXT,
    COLOR_RED_TEXT,
    SPAWN_BUTTON_X,
    SPAWN_BUTTON_Y,
    SPAWN_BUTTON_W,
    SPAWN_BUTTON_H,
    SPAWN_LABEL_OFFSET_X,
    SPAWN_LABEL_OFFSET_Y,
    SPAWN_LEVEL_OFFSET_Y,
    COLOR_SPAWN_BG,
    COLOR_SPAWN_BORDER,
    COLOR_SPAWN_TEXT,
    COLOR_FRAME_OK,
    COLOR_FRAME_NG,
    DELETE_SLOT_X,
    DELETE_SLOT_Y,
    DELETE_SLOT_W,
    DELETE_SLOT_H,
    DELETE_LABEL_OFFSET_X,
    DELETE_LABEL_OFFSET_Y,
    COLOR_DELETE_BG,
    COLOR_DELETE_BORDER,
    COLOR_DELETE_TEXT,
)

# 成長枠の形（要件）。1 行 2 列の横並び。実装の定数ではなく、期待値の根拠として持つ
GROWTH_COLUMNS = 2
GROWTH_ROWS = 1
GROWTH_CELLS = GROWTH_COLUMNS * GROWTH_ROWS  # マスの数 = 列数 × 行数


def fill_clear_slot(core, count):
    """クリア枠に入れた数が count になるまで、次の色の最高の数字のアイテムを入れる

    状態を直接書き換えず、投入を繰り返す。投入に使うマス (5, 4)（開放済み）の元のアイテムは戻す
    """
    # pylint: disable=W0212
    cell = core._field.cell(5, 4)
    original = cell.item
    while core.clear_count < count:
        cell.item = Item(core.clear_next_color, main.MERGE_MAX_NUMBER)
        core._selected = (5, 4)
        core._on_drop(main.CLEAR_SLOT)
    cell.item = original
    return core


def make_cleared(core):
    """クリア枠に必要な数を入れて、core をクリア状態にする"""
    return fill_clear_slot(core, main.CLEAR_REQUIRED_COUNT)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text, color):
        self.call_params.append(("draw_text", x, y, text, color))

    def draw_rect(self, x, y, w, h, color):
        self.call_params.append(("draw_rect", x, y, w, h, color))

    def draw_rect_border(self, x, y, w, h, color):
        self.call_params.append(("draw_rect_border", x, y, w, h, color))

    def get_call_params(self):
        return self.call_params


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        self.patcher_view.stop()

    def draw_core(self, core=None):
        """GameCore を 1 回描いて、そのときの呼び出しだけを返す"""
        core = core or GameCore()
        start = len(self.test_view.get_call_params())
        core.draw()
        return list(self.test_view.get_call_params()[start:])


class TestFieldState(unittest.TestCase):
    def test_ring_of(self):
        """周は中心の 2 × 2 が 0、外へ 4 まで数えること（BR1.4）"""
        self.assertEqual(0, ring_of(4, 4))  # 中心
        self.assertEqual(1, ring_of(3, 3))  # 中心を囲む輪
        self.assertEqual(4, ring_of(0, 0))  # 最外周（左上）
        self.assertEqual(4, ring_of(9, 9))  # 最外周（右下）

    def test_field_size(self):
        """フィールドは 10 × 10 の 100 マスで、座標が 0 から 9 であること（BR1.1）"""
        field = create_initial_field()
        size = 10
        self.assertEqual(size, field.size)
        self.assertEqual(size * size, len(field.cells))
        coords = {(c.x, c.y) for c in field.cells}
        expected = {(x, y) for x in range(size) for y in range(size)}
        self.assertEqual(expected, coords)

    def test_center_opened_empty(self):
        """開放済みのマスは中心の 2 × 2 だけで、アイテムがないこと（BR1.2）"""
        field = create_initial_field()
        opened = {(c.x, c.y) for c in field.cells if c.opened}
        self.assertEqual({(4, 4), (5, 4), (4, 5), (5, 5)}, opened)
        for cell in field.cells:
            if cell.opened:
                self.assertIsNone(cell.item)

    def test_closed_cells_have_item(self):
        """未開放は 96 マスで、すべてアイテムを持つこと（BR1.3）"""
        field = create_initial_field()
        closed = [c for c in field.cells if not c.opened]
        self.assertEqual(10 * 10 - 4, len(closed))  # 100 - 中心 4 マス
        for cell in closed:
            self.assertIsNotNone(cell.item)

    def test_ring_cell_count(self):
        """n 周目のマス数は 8n + 4 であること（BR1.4）"""
        field = create_initial_field()
        for n in range(1, 5):
            count = len([c for c in field.cells if ring_of(c.x, c.y) == n])
            self.assertEqual(8 * n + 4, count)  # 12, 20, 28, 36

    def test_initial_item_per_ring(self):
        """周ごとの初期アイテムが青2・赤3・青4・赤5で、同じ周は同一であること（BR1.5）"""
        field = create_initial_field()
        expected = {
            1: Item("blue", 2),
            2: Item("red", 3),
            3: Item("blue", 4),
            4: Item("red", 5),
        }
        for cell in field.cells:
            if not cell.opened:
                self.assertEqual(expected[ring_of(cell.x, cell.y)], cell.item)


class TestFieldMergeable(unittest.TestCase):
    def test_mergeable_cells(self):
        """マージ先にできるのは、開放済みのマスに上下左右で接する未開放のマスだけであること（FR2.2）"""
        field = create_initial_field()
        mergeable = {(c.x, c.y) for c in field.cells if field.is_mergeable(c.x, c.y)}
        # 中心の 2 × 2 の外側に接する 4 辺 × 2 マス = 8 マス（輪の角は上下左右で接さない）
        expected = {
            (4, 3),
            (5, 3),  # 上
            (4, 6),
            (5, 6),  # 下
            (3, 4),
            (3, 5),  # 左
            (6, 4),
            (6, 5),  # 右
        }
        self.assertEqual(expected, mergeable)
        self.assertEqual(4 * 2, len(mergeable))

    def test_opened_is_not_mergeable(self):
        """開放済みのマスは、マージ先の未開放のマスではないこと"""
        field = create_initial_field()
        self.assertFalse(field.is_mergeable(4, 4))


PITCH = 14  # マスの間隔（隣のマスの左上までのピクセル数）
CELL = 15  # 1 マスの四角形の大きさ。隣と 1 ピクセル重ねて、枠線を 1 ピクセルにする
# 画面上部のレイアウト（要件 FR5.1）。期待値の根拠として、実装の定数とは別に式で持つ
MARGIN = 5  # 画面の端と各要素の間の余白、要素どうしの隙間
ORIGIN_X = MARGIN  # フィールドの左上の x（クリア枠の左端にそろえる）
CLEAR_X = MARGIN  # クリア枠の左上
CLEAR_Y = MARGIN
ORIGIN_Y = CLEAR_Y + CELL + MARGIN  # フィールドの上端 = クリア枠の下端 + 隙間
FIELD_RIGHT = ORIGIN_X + PITCH * 10  # フィールドの右端（マス 10 個分の間隔）
FIELD_BOTTOM = ORIGIN_Y + PITCH * 9 + CELL  # フィールドの下端（最後のマスの下端）
METER_X = CLEAR_X + CELL + MARGIN  # メーターの左端 = クリア枠の右端 + 隙間
METER_Y = CLEAR_Y
METER_W = FIELD_RIGHT - METER_X  # 右端はフィールドの右端にそろえる
METER_H = CELL  # 高さはクリア枠と同じ
SPAWN_GAP = (
    6  # フィールドの下端とスポーンボタンの上端の隙間（画面に収めるための導出値）
)


def button_background():
    """スポーンボタンの背景の呼び出し（領域の定数から作る）"""
    return (
        "draw_rect",
        SPAWN_BUTTON_X,
        SPAWN_BUTTON_Y,
        SPAWN_BUTTON_W,
        SPAWN_BUTTON_H,
        COLOR_SPAWN_BG,
    )


def text_width(text):
    """Pyxel の組み込みフォントの幅: 1 文字 4 ピクセル、文字の間の隙間の分だけ 1 を引く"""
    return 4 * len(text) - 1


def spawn_level_text(level):
    """スポーンボタンの Lv + レベルの呼び出し。左右の中央（左の空白 = (ボタンの幅 - 文字の幅) // 2）"""
    text = f"Lv{level}"
    return (
        "draw_text",
        SPAWN_BUTTON_X + (SPAWN_BUTTON_W - text_width(text)) // 2,
        SPAWN_BUTTON_Y + SPAWN_LEVEL_OFFSET_Y,  # ボタンの上端 + 13
        text,
        COLOR_SPAWN_TEXT,
    )


CLEAR_SLOT_CALLS = 3  # クリア枠: 背景 + 枠線 + 数字 6
METER_BASE_CALLS = 2  # メーター: 背景 + 枠線（塗りは入れた数が 1 以上のときだけ足す）
METER_BORDER = 1  # メーターの枠線の太さ（ピクセル）


def meter_fill_width(count):
    """メーターの塗りの幅 = 内側の幅 × 入れた数 ÷ 必要な数（切り捨て）"""
    inner_w = METER_W - 2 * METER_BORDER
    return inner_w * count // main.CLEAR_REQUIRED_COUNT


def clear_slot_calls(color):
    """クリア枠の描画: 背景 → 枠線 → 次に入れる色の数字 6"""
    return [
        ("draw_rect", CLEAR_X, CLEAR_Y, CELL, CELL, main.COLOR_CLEAR_BG),
        ("draw_rect_border", CLEAR_X, CLEAR_Y, CELL, CELL, main.COLOR_CLEAR_BORDER),
        (
            "draw_text",
            CLEAR_X + main.TEXT_OFFSET_X,
            CLEAR_Y + main.TEXT_OFFSET_Y,
            str(main.MERGE_MAX_NUMBER),
            COLOR_BLUE_TEXT if color == "blue" else COLOR_RED_TEXT,
        ),
    ]


def meter_calls(count):
    """メーターの描画: 背景 → 枠線 → 塗り（入れた数が 0 のときは塗らない）"""
    calls = [
        ("draw_rect", METER_X, METER_Y, METER_W, METER_H, main.COLOR_METER_BG),
        (
            "draw_rect_border",
            METER_X,
            METER_Y,
            METER_W,
            METER_H,
            main.COLOR_METER_BORDER,
        ),
    ]
    fill_w = meter_fill_width(count)
    if fill_w > 0:
        calls.append(
            (
                "draw_rect",
                METER_X + METER_BORDER,
                METER_Y + METER_BORDER,
                fill_w,
                METER_H - 2 * METER_BORDER,
                main.COLOR_METER_FILL,
            )
        )
    return calls


def button_start(calls):
    """呼び出しの列の中で、スポーンボタンの背景が始まる位置（これより前がフィールド）"""
    return calls.index(button_background())


def field_calls_end(calls):
    """呼び出しの列の中で、削除枠の背景が始まる位置（これより前がフィールド。削除枠はマスの後に描く）"""
    return calls.index(delete_slot_background())


class TestFieldView(TestParent):
    def draw_all(self):
        """フィールドの呼び出しだけを返す（削除枠とスポーンボタンの呼び出しは含めない）"""
        calls = self.draw_core()
        return calls[: field_calls_end(calls)]

    def test_screen_size(self):
        """画面サイズは 150 × 200 であること（BR2.1、FR1.1）"""
        self.assertEqual(150, SCREEN_WIDTH)
        self.assertEqual(200, SCREEN_HEIGHT)

    def test_palette(self):
        """プレイテストで決めた色（Pyxel のパレット番号）であること（FR3.1、FR3.2、FR3.3）"""
        self.assertEqual(1, COLOR_BORDER)  # 枠線
        self.assertEqual(13, COLOR_CLOSED_BG)  # 未開放マスの背景
        self.assertEqual(5, COLOR_BLUE_TEXT)  # 青いアイテムの文字
        self.assertEqual(2, COLOR_RED_TEXT)  # 赤いアイテムの文字

    def test_border_overlaps_one_pixel(self):
        """隣のマスと 1 ピクセル重ねて、枠線が 1 ピクセルになること（FR3.3）"""
        self.assertEqual(CELL_PITCH, PITCH)
        self.assertEqual(CELL_SIZE, CELL)
        self.assertEqual(1, CELL - PITCH)
        calls = self.draw_all()
        borders = [c for c in calls if c[0] == "draw_rect_border"]
        by_pos = {c[1:3]: c for c in borders}
        left = ORIGIN_X + PITCH * 3
        top = ORIGIN_Y + PITCH * 3
        right = ORIGIN_X + PITCH * 4  # 右隣のマス
        self.assertEqual(CELL, by_pos[(left, top)][3])
        # 右隣の左端 = このマスの右端 (left + CELL - 1)。枠線が同じ列に重なる
        self.assertEqual(left + CELL - 1, right)

    def test_cell_positions(self):
        """マス (x, y) の左上は (原点 x + 14x, 原点 y + 14y) で、フィールドが画面に収まること（BR2.2、BR2.3、FR1.2、FR5.1）"""
        calls = self.draw_all()
        # 左上 (0,0) は closed なので背景色 COLOR_CLOSED_BG
        self.assertEqual(
            ("draw_rect", ORIGIN_X, ORIGIN_Y, CELL, CELL, COLOR_CLOSED_BG), calls[0]
        )
        # 右下 (9,9) の背景: 原点 + 14 * 9
        pos_x = ORIGIN_X + PITCH * 9
        pos_y = ORIGIN_Y + PITCH * 9
        self.assertIn(("draw_rect", pos_x, pos_y, CELL, CELL, COLOR_CLOSED_BG), calls)
        field_end_x = ORIGIN_X + PITCH * 9 + CELL
        field_end_y = ORIGIN_Y + PITCH * 9 + CELL
        for name, x, y, w, h, _ in (c for c in calls if c[0] != "draw_text"):
            self.assertLessEqual(x + w, field_end_x, name)  # 右端
            self.assertLessEqual(y + h, field_end_y, name)  # 下端
        self.assertLessEqual(field_end_x, SCREEN_WIDTH)
        self.assertLessEqual(field_end_y, SCREEN_HEIGHT)

    def test_background_colors(self):
        """開放済みと未開放で背景の色が違うこと（BR2.4、FR3.2）"""
        calls = self.draw_all()
        opened = (ORIGIN_X + PITCH * 4, ORIGIN_Y + PITCH * 4)  # (4,4) は開放済み
        closed = (ORIGIN_X + PITCH * 3, ORIGIN_Y + PITCH * 3)  # (3,3) は未開放
        self.assertIn(("draw_rect", *opened, CELL, CELL, COLOR_OPENED_BG), calls)
        self.assertIn(("draw_rect", *closed, CELL, CELL, COLOR_CLOSED_BG), calls)
        self.assertNotEqual(COLOR_OPENED_BG, COLOR_CLOSED_BG)

    def test_borders_and_call_counts(self):
        """全マスに枠線を描き、呼び出し数が 100 + 100 + 8 であること（BR2.5、BR2.9、FR3.3）"""
        calls = self.draw_all()
        kinds = [c[0] for c in calls]
        self.assertEqual(10 * 10, kinds.count("draw_rect"))
        self.assertEqual(10 * 10, kinds.count("draw_rect_border"))
        self.assertEqual(
            4 * 2, kinds.count("draw_text")
        )  # 文字はマージ先にできる 8 マスだけ
        borders = {c[1:3] for c in calls if c[0] == "draw_rect_border"}
        expected = {
            (ORIGIN_X + PITCH * x, ORIGIN_Y + PITCH * y)
            for x in range(10)
            for y in range(10)
        }
        self.assertEqual(expected, borders)
        self.assertTrue(
            all(c[5] == COLOR_BORDER for c in calls if c[0] == "draw_rect_border")
        )

    def test_number_text(self):
        """マージ先にできる未開放マスだけに数字を色つきで描くこと（BR2.6、FR3.1）"""
        calls = self.draw_all()
        # 1 周目でマージ先にできる (4,3) は青2
        x = ORIGIN_X + PITCH * 4 + 6  # マスの左上 + TEXT_OFFSET_X（中央にする）
        y = ORIGIN_Y + PITCH * 3 + 5  # マスの左上 + TEXT_OFFSET_Y
        self.assertIn(("draw_text", x, y, "2", COLOR_BLUE_TEXT), calls)

    def test_locked_and_empty_cells_have_no_text(self):
        """ロックされた未開放マスと開放済みの空きマスには数字を描かないこと（BR2.6、FR3.1）"""
        calls = self.draw_all()

        def texts_in(cx, cy):
            left = ORIGIN_X + PITCH * cx
            top = ORIGIN_Y + PITCH * cy
            return [
                c
                for c in calls
                if c[0] == "draw_text"
                and left <= c[1] < left + CELL
                and top <= c[2] < top + CELL
            ]

        self.assertEqual([], texts_in(3, 3))  # 1 周目の角（上下左右で接しない）
        self.assertEqual([], texts_in(2, 2))  # 2 周目
        self.assertEqual([], texts_in(0, 0))  # 4 周目
        self.assertEqual([], texts_in(4, 4))  # 開放済みの空きマス

    def test_text_is_ascii(self):
        """描く文字はすべて ASCII 1 文字であること（BR2.7、FR3.4）"""
        texts = [c[3] for c in self.draw_all() if c[0] == "draw_text"]
        self.assertTrue(texts)
        for text in texts:
            self.assertEqual(1, len(text))
            self.assertTrue(text.isascii())

    def test_draw_order_per_cell(self):
        """マスごとに 背景 → 枠線 → 文字 の順に描くこと（BR2.4、BR2.5、BR2.6）"""
        calls = self.draw_all()
        # (4,3) は文字のあるマス。その背景から 3 つが 背景 → 枠線 → 文字
        left = ORIGIN_X + PITCH * 4
        top = ORIGIN_Y + PITCH * 3
        start = next(
            i
            for i, c in enumerate(calls)
            if c[0] == "draw_rect" and c[1:3] == (left, top)
        )
        self.assertEqual(
            ["draw_rect", "draw_rect_border", "draw_text"],
            [c[0] for c in calls[start : start + 3]],
        )


class TestSpawnButtonView(TestParent):
    def button_calls(self, core=None):
        calls = self.draw_core(core)
        return calls[button_start(calls) :]

    def core_at_level(self, level):
        core = GameCore()
        patcher = patch.object(
            GameCore, "spawn_level", new_callable=PropertyMock, return_value=level
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return core

    def test_background_at_initial_state(self):
        """初期の状態で、背景の四角形がスポーンボタンの領域に描かれ、上端はフィールドの下端 + 隙間であること（BR2.1、FR5.1）"""
        self.assertEqual(
            (
                "draw_rect",
                SPAWN_BUTTON_X,
                FIELD_BOTTOM + SPAWN_GAP,
                SPAWN_BUTTON_W,
                SPAWN_BUTTON_H,
                COLOR_SPAWN_BG,
            ),
            button_background(),
        )
        self.assertIn(button_background(), self.draw_core())

    def test_area_is_centered_and_clear_of_neighbors(self):
        """領域は画面の中央にあり、削除枠・成長枠・フィールドと重ならず、その位置に何も描かないこと（BR2.1、FR1.1）"""
        center_x = SPAWN_BUTTON_X + SPAWN_BUTTON_W // 2
        self.assertEqual(SCREEN_WIDTH // 2, center_x)  # 75
        # 左の削除枠は、フィールドの左端とスポーンボタンの間の中央（左右の空白が同じ）
        # 空白の合計 = ボタンの左端 - フィールドの左端 - 枠の幅 = 50 - 5 - 15 = 30、片側 15。x = 5 + 15 = 20
        delete_left = ORIGIN_X + (SPAWN_BUTTON_X - ORIGIN_X - CELL) // 2
        delete_right = delete_left + CELL - 1  # 枠の右端のピクセル
        # 右の成長枠は、スポーンボタンの右端とフィールドの右端の間の中央（左右の空白が同じ）
        # 空白の合計 = 145 - 100 - 29 = 16、片側 8。x = 100 + 8 = 108
        growth_w = PITCH * (GROWTH_COLUMNS - 1) + CELL
        button_right = SPAWN_BUTTON_X + SPAWN_BUTTON_W
        growth_left = button_right + (FIELD_RIGHT - button_right - growth_w) // 2
        self.assertGreater(SPAWN_BUTTON_X, delete_right)
        self.assertLess(SPAWN_BUTTON_X + SPAWN_BUTTON_W, growth_left)
        self.assertGreater(SPAWN_BUTTON_Y, FIELD_BOTTOM)
        self.assertLessEqual(SPAWN_BUTTON_Y + SPAWN_BUTTON_H, SCREEN_HEIGHT)
        # 削除枠は、スポーンボタンの左で重ならない（右端のピクセル < ボタンの左端 50）
        self.assertLess(DELETE_SLOT_X + DELETE_SLOT_W - 1, SPAWN_BUTTON_X)
        self.assertEqual(delete_left, DELETE_SLOT_X)
        self.assertEqual(delete_right, DELETE_SLOT_X + DELETE_SLOT_W - 1)
        self.assertEqual(growth_left, main.GROWTH_SLOT_X)
        # 下部で描かれるものは、すべてボタン・削除枠・成長枠のどれかの領域の内側（枠の位置は空き）。
        # 成長枠は常に描くようになったので、領域に加える
        for call in self.draw_core():
            if call[0] == "draw_text":
                _, x, y, _, _ = call
                w = 0
            else:
                _, x, y, w, _, _ = call
            if y > FIELD_BOTTOM:
                in_button = (
                    x >= SPAWN_BUTTON_X and x + w <= SPAWN_BUTTON_X + SPAWN_BUTTON_W
                )
                in_delete = (
                    x >= DELETE_SLOT_X and x + w <= DELETE_SLOT_X + DELETE_SLOT_W
                )
                in_growth = (
                    x >= main.GROWTH_SLOT_X
                    and x + w <= main.GROWTH_SLOT_X + main.GROWTH_SLOT_W
                )
                self.assertTrue(in_button or in_delete or in_growth, call)

    def test_draw_sequence_at_level_1(self):
        """背景、枠線、SPAWN、Lv1 の順に、領域の定数から計算した位置に描かれること（BR2.2、BR2.3、FR1.2）"""
        expected = [
            button_background(),
            (
                "draw_rect_border",
                SPAWN_BUTTON_X,
                SPAWN_BUTTON_Y,
                SPAWN_BUTTON_W,
                SPAWN_BUTTON_H,
                COLOR_SPAWN_BORDER,
            ),
            (
                "draw_text",
                SPAWN_BUTTON_X + SPAWN_LABEL_OFFSET_X,  # 50 + 15 = 65
                SPAWN_BUTTON_Y + SPAWN_LABEL_OFFSET_Y,  # ボタンの上端 + 5
                "SPAWN",
                COLOR_SPAWN_TEXT,
            ),
            # Lv1 は幅 4 × 3 - 1 = 11。x = 50 + (50 - 11) // 2 = 69
            spawn_level_text(1),
        ]
        self.assertEqual(expected, self.button_calls())

    def test_level_text_is_centered_for_one_and_two_digits(self):
        """Lv の文字は、1 桁・2 桁のどちらでも、ボタンの左右の空白の差が 1 ピクセル以下であること（FR4.1）"""
        for level in (9, 10, main.SPAWN_LEVEL_MAX):
            with self.subTest(level=level):
                _, x, _, text, _ = self.button_calls(self.core_at_level(level))[3]
                self.assertEqual(f"Lv{level}", text)
                left_gap = x - SPAWN_BUTTON_X
                right_gap = SPAWN_BUTTON_X + SPAWN_BUTTON_W - (x + text_width(text))
                self.assertLessEqual(
                    abs(left_gap - right_gap), 1, (left_gap, right_gap)
                )

    def test_button_is_drawn_after_field(self):
        """ボタンはフィールドの 100 マスの描画のあとに描かれること（BR2.2）"""
        calls = self.draw_core()
        self.assertEqual(100 + 100 + 4 * 2, field_calls_end(calls))  # 先頭はフィールド
        # 削除枠(3)の次に成長枠(マスごとの背景と枠線 + 項目の数字 1)が入る
        delete_slot = 3
        growth_slot = GROWTH_CELLS * 2 + 1  # レベル 1 は 青2 の 1 項目
        # 成長枠の次にクリア枠とメーター（入れた数 0 なので塗りは無い）が入る
        upper = CLEAR_SLOT_CALLS + METER_BASE_CALLS
        self.assertEqual(
            delete_slot + growth_slot + upper,
            button_start(calls) - field_calls_end(calls),
        )
        self.assertEqual(4, len(calls) - button_start(calls))  # 残りはボタンの 4 回

    def test_level_text_follows_spawn_level(self):
        """Lv の数字がスポーンのレベルに従って変わること（BR2.4、FR1.2）"""
        for level in (1, 5, main.SPAWN_LEVEL_MAX):
            texts = [c[3] for c in self.button_calls(self.core_at_level(level))[2:]]
            self.assertEqual(["SPAWN", f"Lv{level}"], texts)

    def test_all_text_is_ascii(self):
        """画面上の文字はすべて ASCII であること（BR2.4、FR1.2）"""
        texts = [c[3] for c in self.draw_core() if c[0] == "draw_text"]
        # 8（マス）+ 1（DEL）+ 1（成長枠のレベル 1 の項目）+ 1（クリア枠の 6）+ 2（ボタン）
        self.assertEqual(8 + 1 + 1 + 1 + 2, len(texts))
        for text in texts:
            self.assertTrue(text.isascii(), text)

    def test_opened_cell_item_number_is_drawn(self):
        """開放済みのマスにアイテムがあると、その色で数字が描かれること（BR2.5、FR4.1）"""
        core = GameCore()
        core.spawn(StubRandom(index=0, value=0.0))  # (4, 4) に青1
        core._field.cell(5, 4).item = Item("red", 2)  # pylint: disable=W0212
        calls = self.draw_core(core)
        x = ORIGIN_X + PITCH * 4 + 6  # マスの左上 + TEXT_OFFSET_X
        y = ORIGIN_Y + PITCH * 4 + 5  # マスの左上 + TEXT_OFFSET_Y
        self.assertIn(("draw_text", x, y, "1", COLOR_BLUE_TEXT), calls)
        self.assertIn(("draw_text", x + PITCH, y, "2", COLOR_RED_TEXT), calls)
        # 空きのままの (4, 5) には数字がない
        empty_top = ORIGIN_Y + PITCH * 5
        texts = [
            c
            for c in calls
            if c[0] == "draw_text"
            and x <= c[1] < x + CELL
            and empty_top <= c[2] < empty_top + CELL
        ]
        self.assertEqual([], texts)
        # 文字の数は 8 + 1（DEL）+ 1（成長枠のレベル 1 の項目）+ 1（クリア枠の 6）
        # + 2（ボタン）+ 2（置いたアイテム）
        self.assertEqual(
            8 + 1 + 1 + 1 + 2 + 2, len([c for c in calls if c[0] == "draw_text"])
        )

    def test_closed_cells_unchanged(self):
        """未開放のマスは、マージ先にできるマスだけ数字を描くこと（BR2.6、FR4.2）"""
        core = GameCore()
        core.spawn(StubRandom(index=0, value=0.0))  # 開放済みのマスにアイテムを置く
        calls = self.draw_core(core)
        field_texts = [
            c for c in calls[: field_calls_end(calls)] if c[0] == "draw_text"
        ]
        # マージ先にできる 8 マス + アイテムを置いた開放済みの 1 マス
        self.assertEqual(8 + 1, len(field_texts))
        locked_x = ORIGIN_X + PITCH * 3 + 6  # ロックされた (3, 3) の数字の位置
        locked_y = ORIGIN_Y + PITCH * 3 + 5
        self.assertNotIn((locked_x, locked_y), {(c[1], c[2]) for c in field_texts})


BLUE1 = Item("blue", 1)
BLUE2 = Item("blue", 2)
RED1 = Item("red", 1)
RED2 = Item("red", 2)
# 出現確率の段階の数と、スポーンのレベルの数（要件 FR1.1、FR2.1）
RATE_STAGES = 8
SPAWN_LEVELS = 20
# 段階ごとの出現確率（％、要件 FR2.4）。順序は 青1、青2、赤1、赤2
STAGE_RATES = {
    1: (100, 0, 0, 0),
    2: (70, 30, 0, 0),
    3: (40, 20, 40, 0),
    4: (30, 20, 30, 20),
    5: (33, 22, 27, 18),
    6: (24, 36, 16, 24),
    7: (26, 39, 14, 21),
    8: (27, 40, 13, 20),
}
# 段階ごとの数字 2 の割合（％）。今の 8 段階の表の 青2 + 赤2 と同じ（要件 FR2.2）
STAGE_NUMBER2_SHARE = (0, 30, 20, 40, 40, 60, 60, 60)
# 段階ごとの赤の割合（％）。赤が半分になる段階 4 までは今と同じで、そこから青を増やし、
# 最後の段階で 赤 1:青 2 の整数の近似 33:67 にする（要件 FR2.3）
STAGE_RED_SHARE = (0, 0, 40, 50, 45, 40, 35, 33)
# 段階ごとの新しいレベルの範囲（要件 FR2.4 の表の「新レベル」の列）
STAGE_LEVEL_RANGES = {
    1: range(1, 3),
    2: range(3, 6),
    3: range(6, 8),
    4: range(8, 11),
    5: range(11, 14),
    6: range(14, 16),
    7: range(16, 19),
    8: range(19, 21),
}


def stage_of(level):
    """新しいレベル L の段階 = 1 + (L-1) × 7/19 の四捨五入（要件 FR2.1）

    .5 になるのは L = 20（ちょうど 8）だけなので、+0.5 の切り捨てで四捨五入する
    """
    return int(1 + (level - 1) * (RATE_STAGES - 1) / (SPAWN_LEVELS - 1) + 0.5)


# レベルごとの出現確率（％）。レベル → そのレベルの段階の行
RATE_TABLE = {
    level: STAGE_RATES[stage_of(level)] for level in range(1, SPAWN_LEVELS + 1)
}
SPAWN_ITEMS = (BLUE1, BLUE2, RED1, RED2)


class StubRandom:
    """決まった値を返す乱数の元。呼び出しを記録する"""

    def __init__(self, index=0, value=0.0):
        self.index = index  # randrange(n) の返す値
        self.value = value  # random() の返す値（0 以上 1 未満）
        self.calls = []

    def randrange(self, n):
        self.calls.append(("randrange", n))
        return self.index

    def random(self):
        self.calls.append(("random",))
        return self.value


class TestSpawnRates(unittest.TestCase):
    def test_level1_is_always_blue1(self):
        """レベル 1 のアイテムは、乱数の値が何でも青1であること（BR1.3、FR2.2）"""
        for roll in (0, 50, 99.9):
            self.assertEqual(Item("blue", 1), main.pick_item(1, roll))

    def test_spawn_level_constants(self):
        """スポーンのレベルは 1 から始まり、最高は 20 であること（FR1.1）"""
        self.assertEqual(1, main.SPAWN_LEVEL_START)
        self.assertEqual(SPAWN_LEVELS, main.SPAWN_LEVEL_MAX)

    def test_merge_max_number_constant(self):
        """マージできない最高の数字は 6 であること（FR1.1、FR1.2）"""
        self.assertEqual(6, main.MERGE_MAX_NUMBER)

    def test_stage_of_level_matches_requirement_ranges(self):
        """四捨五入の式で決まる段階が、要件の表の新レベルの範囲と一致すること（FR2.1）"""
        for stage, levels in STAGE_LEVEL_RANGES.items():
            for level in levels:
                self.assertEqual(stage, stage_of(level), level)
        covered = [level for levels in STAGE_LEVEL_RANGES.values() for level in levels]
        self.assertEqual(list(range(1, SPAWN_LEVELS + 1)), covered)

    def test_rate_table(self):
        """レベル 1 から 20 の出現確率が表のとおりで、合計が 100 であること（FR2.4）"""
        self.assertEqual(set(RATE_TABLE), set(main.SPAWN_RATES))
        for level, rates in RATE_TABLE.items():
            expected = tuple(zip(SPAWN_ITEMS, rates))
            self.assertEqual(expected, tuple(main.SPAWN_RATES.get(level, ())), level)
            self.assertEqual(100, sum(rates), level)

    def test_number2_share_per_stage_is_unchanged(self):
        """各レベルの数字 2（青2 + 赤2）の割合が、段階ごとに今と同じであること（FR2.2）"""
        for level in range(1, SPAWN_LEVELS + 1):
            rates = dict(main.SPAWN_RATES.get(level, ()))
            share = rates.get(BLUE2, 0) + rates.get(RED2, 0)
            self.assertEqual(STAGE_NUMBER2_SHARE[stage_of(level) - 1], share, level)

    def test_red_share_shifts_to_one_to_two(self):
        """赤の割合は段階 4 までは今と同じで、そこから下がり、最後の段階で 赤33:青67 であること（FR2.3）"""
        for level in range(1, SPAWN_LEVELS + 1):
            rates = dict(main.SPAWN_RATES.get(level, ()))
            red = rates.get(RED1, 0) + rates.get(RED2, 0)
            self.assertEqual(STAGE_RED_SHARE[stage_of(level) - 1], red, level)
        last = dict(main.SPAWN_RATES.get(SPAWN_LEVELS, ()))
        red = last.get(RED1, 0) + last.get(RED2, 0)
        blue = last.get(BLUE1, 0) + last.get(BLUE2, 0)
        self.assertEqual((33, 67), (red, blue))  # 赤 1:青 2 の整数の％の近似

    def test_pick_item_boundaries(self):
        """累積の割合の境目でアイテムが切り替わること（BR1.3、FR2.2、FR3.2）"""
        for level, rates in RATE_TABLE.items():
            start = 0
            for item, rate in zip(SPAWN_ITEMS, rates):
                end = start + rate  # このアイテムの範囲は start 以上 end 未満
                if rate > 0:
                    self.assertEqual(item, main.pick_item(level, start), level)
                    self.assertEqual(item, main.pick_item(level, end - 0.01), level)
                start = end

    def test_pick_item_examples(self):
        """段階 2・3・4 の先頭のレベル 3、6、8 の境目が 70、40・60、30・50・80 であること（FR2.4）"""
        self.assertEqual(BLUE1, main.pick_item(3, 69.99))
        self.assertEqual(BLUE2, main.pick_item(3, 70))
        self.assertEqual(BLUE1, main.pick_item(6, 39.99))
        self.assertEqual(BLUE2, main.pick_item(6, 40))
        self.assertEqual(BLUE2, main.pick_item(6, 59.99))
        self.assertEqual(RED1, main.pick_item(6, 60))
        self.assertEqual(RED1, main.pick_item(8, 79.99))
        self.assertEqual(RED2, main.pick_item(8, 80))

    def test_zero_rate_items_are_never_picked(self):
        """確率 0 のアイテムは、どの乱数の値でも選ばれないこと（BR1.3、FR3.2）"""
        for level, rates in RATE_TABLE.items():
            allowed = {i for i, r in zip(SPAWN_ITEMS, rates) if r > 0}
            picked = {main.pick_item(level, roll / 10) for roll in range(1000)}
            self.assertEqual(allowed, picked, level)

    def test_no_table_level_picks_nothing(self):
        """出現確率の表がないレベル（最高レベルの次）では、アイテムを決めないこと（BR1.6）"""
        self.assertIsNone(main.pick_item(main.SPAWN_LEVEL_MAX + 1, 0))


def opened_empty(field):
    return [c for c in field.cells if c.opened and c.item is None]


class TestSpawn(TestParent):
    def test_places_item_on_chosen_cell_only(self):
        """開放済みの空きマス 4 つのうち、乱数で選んだ 1 マスだけにアイテムを置くこと（BR1.4、FR2.1）"""
        field = create_initial_field()
        before = copy.deepcopy(field)
        candidates = opened_empty(field)
        self.assertEqual(4, len(candidates))  # 中心の 2 × 2
        rng = StubRandom(index=2, value=0.0)
        placed = main.spawn(field, 1, rng)
        self.assertIs(candidates[2], placed)
        self.assertEqual(BLUE1, placed.item)
        changed = [(a.x, a.y) for a, b in zip(field.cells, before.cells) if a != b]
        self.assertEqual([(placed.x, placed.y)], changed)
        # マスを決めてから、アイテムを決める
        self.assertEqual([("randrange", len(candidates)), ("random",)], rng.calls)

    def test_item_follows_roll_times_100(self):
        """random() の値を 100 倍して抽選に使うこと（BR1.3、FR2.2）"""
        field = create_initial_field()
        # レベル 3（段階 2）は 青1 70％・青2 30％。0.7 × 100 = 70 は 青2 の範囲の先頭
        placed = main.spawn(field, 3, StubRandom(index=0, value=0.7))
        self.assertEqual(BLUE2, placed.item)

    def test_skips_closed_and_occupied_cells(self):
        """未開放のマスと、アイテムのあるマスには置かないこと（BR1.4、FR2.1）"""
        field = create_initial_field()
        field.cell(4, 4).item = RED2  # 開放済みでも、アイテムのあるマス
        before = copy.deepcopy(field)
        candidates = [(5, 4), (4, 5), (5, 5)]
        for index, (x, y) in enumerate(candidates):
            trial = copy.deepcopy(field)
            rng = StubRandom(index=index)
            placed = main.spawn(trial, 1, rng)
            self.assertEqual((x, y), (placed.x, placed.y))
            self.assertEqual(len(candidates), rng.calls[0][1])
            self.assertEqual(RED2, trial.cell(4, 4).item)
            closed = [c for c in trial.cells if not c.opened]
            self.assertEqual([c for c in before.cells if not c.opened], closed)

    def test_no_candidate_does_nothing(self):
        """開放済みの空きマスがないとき、フィールドは変わらず、結果は「なし」で、乱数は使われないこと（BR1.5、FR2.3）"""
        field = create_initial_field()
        for cell in opened_empty(field):
            cell.item = BLUE1
        before = copy.deepcopy(field)
        rng = StubRandom()
        self.assertIsNone(main.spawn(field, 1, rng))
        self.assertEqual(before, field)
        self.assertEqual([], rng.calls)

    def test_no_table_level_does_nothing(self):
        """出現確率の表がないレベル（最高レベルの次）では、フィールドは変わらないこと（BR1.6）"""
        field = create_initial_field()
        before = copy.deepcopy(field)
        rng = StubRandom()
        self.assertIsNone(main.spawn(field, main.SPAWN_LEVEL_MAX + 1, rng))
        self.assertEqual(before, field)
        self.assertEqual([], rng.calls)

    def test_game_core_starts_at_level_1(self):
        """GameCore のスポーンのレベルは、開始時 1 であること（BR1.1、FR1.3）"""
        self.assertEqual(1, GameCore().spawn_level)

    def test_game_core_spawn_uses_own_field_and_level(self):
        """GameCore のスポーンは、自分のフィールドとレベルを使うこと（FR3.2）"""
        core = GameCore()
        rng = StubRandom(index=0, value=0.99)  # レベル 1 は何でも青1
        first = core.spawn(rng)
        self.assertEqual((4, 4), (first.x, first.y))
        self.assertEqual(BLUE1, first.item)
        # 置いたマスは埋まるので、次の候補は 3 マス
        second = core.spawn(rng)
        self.assertEqual((5, 4), (second.x, second.y))
        self.assertEqual(("randrange", 3), rng.calls[2])


class TestInput(IInput):
    """フレームごとに決めた位置を返す入力。使い切ったら「なし」を返す

    押した（positions）・押している間（held）・離した（released）の 3 つは
    別々の列で持ち、メソッドが呼ばれるたびに 1 フレーム分を取り出す
    """

    def __init__(self):
        self.positions = []
        self.held = []
        self.released = []

    def tapped_position(self):
        return self.positions.pop(0) if self.positions else None

    def held_position(self):
        return self.held.pop(0) if self.held else None

    def released_position(self):
        return self.released.pop(0) if self.released else None


def placed_cells(core):
    """アイテムが置かれた開放済みのマス"""
    # pylint: disable=W0212
    return [c for c in core._field.cells if c.opened and c.item is not None]


class TestSpawnInput(TestParent):
    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)
        # GameCore.spawn() の既定の乱数の元（random モジュール）を決めた値にする
        self.mock_randrange = self.patch_random("randrange", 0)
        self.mock_random = self.patch_random("random", 0.0)

    def patch_random(self, name, value):
        patcher = patch(f"random.{name}", return_value=value)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def tap_frame(self, core, position):
        """位置を押したフレームを 1 回進める"""
        self.test_input.positions.append(position)
        core.update()

    def test_tap_inside_button_spawns_one(self):
        """ボタンの領域の中を押すと、アイテムが 1 つ置かれること（BR3.2、FR2.1）"""
        core = GameCore()
        center = (
            SPAWN_BUTTON_X + SPAWN_BUTTON_W // 2,
            SPAWN_BUTTON_Y + SPAWN_BUTTON_H // 2,
        )
        self.tap_frame(core, center)
        self.assertEqual(1, len(placed_cells(core)))

    def test_region_boundaries(self):
        """領域は半開区間で、角の内側は中、1 ピクセル外は外であること（BR3.4、FR2.1、FR2.4）"""
        left, top = SPAWN_BUTTON_X, SPAWN_BUTTON_Y
        right = SPAWN_BUTTON_X + SPAWN_BUTTON_W  # 外（100）
        bottom = SPAWN_BUTTON_Y + SPAWN_BUTTON_H  # 外（下端の 1 ピクセル下）
        inside = [(left, top), (right - 1, bottom - 1)]
        outside = [(right, top), (left - 1, top), (left, bottom), (left, top - 1)]
        for position in inside:
            core = GameCore()
            self.tap_frame(core, position)
            self.assertEqual(1, len(placed_cells(core)), position)
        for position in outside:
            core = GameCore()
            self.tap_frame(core, position)
            self.assertEqual([], placed_cells(core), position)

    def test_tap_on_other_areas_does_not_spawn(self):
        """フィールドの上、削除枠、成長枠を押してもスポーンしないこと（BR3.3、FR2.4）"""
        core = GameCore()
        field_x = ORIGIN_X + PITCH * 4 + 5  # マス (4, 4) の中
        field_y = ORIGIN_Y + PITCH * 4 + 5
        for position in ((field_x, field_y), (10, 170), (110, 170)):
            self.tap_frame(core, position)
        self.assertEqual([], placed_cells(core))

    def test_no_tap_does_not_spawn(self):
        """押していないフレーム（位置が「なし」）では、スポーンしないこと（BR3.1、BR3.3）"""
        core = GameCore()
        for _ in range(3):
            core.update()
        self.assertEqual([], placed_cells(core))

    def test_spawns_on_randomly_chosen_cell_and_is_drawn(self):
        """乱数で選んだ 1 マスに置かれ、次の描画で数字として見えること（BR3.2、FR2.1）"""
        self.mock_randrange.return_value = 2  # 候補 4 マスのうち 3 番目 = (4, 5)
        core = GameCore()
        self.tap_frame(core, (SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.mock_randrange.assert_called_once_with(4)
        self.assertEqual([(4, 5)], [(c.x, c.y) for c in placed_cells(core)])
        calls = self.draw_core(core)
        x = ORIGIN_X + PITCH * 4 + 6  # マスの左上 + TEXT_OFFSET_X
        y = ORIGIN_Y + PITCH * 5 + 5  # マスの左上 + TEXT_OFFSET_Y
        self.assertIn(("draw_text", x, y, "1", COLOR_BLUE_TEXT), calls)

    def test_no_empty_opened_cell_does_nothing(self):
        """開放済みの空きマスがないとき、押しても何も起こらないこと（BR3.5）"""
        core = GameCore()
        for _ in range(4):
            self.tap_frame(core, (SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertEqual(4, len(placed_cells(core)))
        before = copy.deepcopy(core._field)  # pylint: disable=W0212
        self.tap_frame(core, (SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertEqual(before, core._field)  # pylint: disable=W0212

    def test_one_spawn_per_tap_frame(self):
        """位置を返したフレームの回数だけスポーンし、1 回の押下で 1 つであること（BR3.1）"""
        core = GameCore()
        taps = 3
        for _ in range(taps):
            self.tap_frame(core, (SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
            core.update()  # 押していないフレームでは増えない
        self.assertEqual(taps, len(placed_cells(core)))


def cell_center(x, y):
    """マス (x, y) の中心の画面位置（枠線の重なりを避けるため、左上から半分進める）"""
    return (
        ORIGIN_X + CELL_PITCH * x + CELL_PITCH // 2,
        ORIGIN_Y + CELL_PITCH * y + CELL_PITCH // 2,
    )


class TestSlideInput(TestParent):
    """押す・動かす・離すの入力と、操作元・ポインタの下のマスの状態"""

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    def test_press_opened_cell_with_item_selects_it(self):
        """アイテムのある開放済みのマスを押すと、操作元になること（FR1.1）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.assertEqual((4, 4), core.selected)

    def test_press_without_item_or_unopened_or_outside_does_not_select(self):
        """空きマス・未開放のマス・フィールドの外を押しても、操作元にならないこと（FR1.2）"""
        core = GameCore()
        outside = (ORIGIN_X - 1, ORIGIN_Y - 1)  # フィールドの左上の外
        targets = [
            cell_center(4, 4),  # 開放済みの空きマス
            cell_center(0, 0),  # 未開放のマス（アイテムはある）
            outside,
        ]
        for position in targets:
            self.frame(core, tapped=position)
            self.assertIsNone(core.selected, position)

    def test_spawn_button_spawns_and_is_not_selectable(self):
        """スポーンボタンを押すとスポーンし、操作元にはならないこと（FR1.3）"""
        core = GameCore()
        self.frame(core, tapped=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertEqual(1, len(placed_cells(core)))
        self.assertIsNone(core.selected)

    def test_held_updates_hovered_cell(self):
        """押している間、ポインタの下のマスが更新されること（FR2.1）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=cell_center(4, 4))
        self.assertEqual((4, 4), core.hovered)
        self.frame(core, held=cell_center(3, 4))
        self.assertEqual((3, 4), core.hovered)

    def test_hovered_is_none_outside_field_and_recovers(self):
        """フィールドの外に出ると「なし」になり、戻ると更新されること（FR2.3）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))  # フィールドの下
        self.assertIsNone(core.hovered)
        self.assertEqual((4, 4), core.selected)  # 選択は保たれる
        self.frame(core, held=cell_center(5, 4))
        self.assertEqual((5, 4), core.hovered)

    def test_held_without_selection_does_not_hover(self):
        """選択していないとき、押している間の位置は無視されること"""
        core = GameCore()
        self.frame(core, held=cell_center(3, 4))
        self.assertIsNone(core.hovered)

    def test_release_merges(self):
        """同じ色・同じ数字のマスで離すと、マージされること（FR3.1）"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("blue", 2)
        # (3, 4) は 1 周目の青 2。開放済みの (4, 4) に接するのでマージ先にできる
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=cell_center(3, 4))
        self.frame(core, released=cell_center(3, 4))
        self.assertIsNone(field.cell(4, 4).item)
        self.assertEqual(Item("blue", 3), field.cell(3, 4).item)
        self.assertTrue(field.cell(3, 4).opened)

    def test_release_moves_to_opened_empty_cell(self):
        """開放済みの空きマスで離すと、移動すること（FR3.2）"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("red", 1)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, released=cell_center(5, 5))
        self.assertIsNone(field.cell(4, 4).item)
        self.assertEqual(Item("red", 1), field.cell(5, 5).item)

    def test_release_cancels_when_not_executable(self):
        """色違い・フィールドの外・操作元自身で離すと、フィールドが変わらないこと（FR3.3、FR3.4、FR2.3）"""
        outside = (ORIGIN_X - 1, ORIGIN_Y - 1)
        # (3, 4) は青 2 なので、赤 2 とは色違い
        for released in (cell_center(3, 4), outside, cell_center(4, 4)):
            core = GameCore()
            field = core._field  # pylint: disable=W0212
            field.cell(4, 4).item = Item("red", 2)
            before = copy.deepcopy(field)
            self.frame(core, tapped=cell_center(4, 4))
            self.frame(core, released=released)
            self.assertEqual(before, field, released)

    def test_release_clears_state(self):
        """離した後は、操作元とポインタの下のマスが「なし」になること（FR2.4）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("red", 1)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=cell_center(4, 4))
        self.frame(core, released=cell_center(5, 5))
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)
        # 離した後の位置は無視される（次の押下まで操作は始まらない）
        self.frame(core, held=cell_center(5, 5))
        self.assertIsNone(core.hovered)

    def test_press_and_release_in_same_frame_cancels(self):
        """押した位置と離した位置が同じフレームでも壊れず、キャンセルになること"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("blue", 2)
        before = copy.deepcopy(field)
        self.frame(core, tapped=cell_center(4, 4), released=cell_center(4, 4))
        self.assertEqual(before, field)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)


def frame_outer(x, y, color):
    """マス (x, y) の選択枠の外側の枠線: マスの四角形と同じ位置と大きさ"""
    left = ORIGIN_X + CELL_PITCH * x
    top = ORIGIN_Y + CELL_PITCH * y
    return ("draw_rect_border", left, top, CELL_SIZE, CELL_SIZE, color)


def frame_inner(x, y, color):
    """マス (x, y) の選択枠の内側の枠線: 外側より 1 ピクセル内側（左上 +1、幅と高さ -2）"""
    left = ORIGIN_X + CELL_PITCH * x + 1
    top = ORIGIN_Y + CELL_PITCH * y + 1
    return ("draw_rect_border", left, top, CELL_SIZE - 2, CELL_SIZE - 2, color)


class TestSelectionFrameView(TestParent):
    """押している間の選択枠の描画"""

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    def test_no_frame_while_nothing_selected(self):
        """操作元が無いとき（押していない、離した後）は、枠が描かれないこと（FR2.4）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("red", 1)  # pylint: disable=W0212
        self.assertEqual([], self.frame_calls(self.draw_core(core)))
        self.frame(core, tapped=cell_center(4, 4), held=cell_center(4, 4))
        self.frame(core, released=cell_center(5, 5))  # 空きマスへ移動して離す
        self.assertEqual([], self.frame_calls(self.draw_core(core)))
        # 実行できなかった（キャンセル）場合も同じ
        core = GameCore()
        core._field.cell(4, 4).item = Item("red", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, released=cell_center(3, 4))  # 色違いの上で離す
        self.assertEqual([], self.frame_calls(self.draw_core(core)))

    def test_frame_is_drawn_at_pressed_cell_in_ng_color(self):
        """操作元を押すと、そのマスに二重の枠が描かれ、操作元自身の上なので赤であること（FR1.1、FR2.2）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.assertEqual(
            [frame_outer(4, 4, COLOR_FRAME_NG), frame_inner(4, 4, COLOR_FRAME_NG)],
            self.frame_calls(self.draw_core(core)),
        )

    def test_frame_follows_pointer_ok_on_executable_cells(self):
        """実行できるマス（空きマス、同じアイテム）の上では、そのマスに緑の枠が描かれること（FR2.1、FR2.2）"""
        # (5, 5) は開放済みの空きマス、(3, 4) は青 2（開放済みの (4, 4) に接するのでマージ先にできる）
        for target in ((5, 5), (3, 4)):
            core = GameCore()
            core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
            self.frame(core, tapped=cell_center(4, 4))
            self.frame(core, held=cell_center(*target))
            self.assertEqual(
                [
                    frame_outer(*target, COLOR_FRAME_OK),
                    frame_inner(*target, COLOR_FRAME_OK),
                ],
                self.frame_calls(self.draw_core(core)),
                target,
            )

    def test_frame_is_ng_color_on_non_executable_cells(self):
        """色違い・ロック中のマスの上では、そのマスに赤の枠が描かれること（FR2.2）"""
        # (3, 4) は青 2 なので赤 2 とは色違い、(0, 0) はマージ先にできない未開放のマス
        for target in ((3, 4), (0, 0)):
            core = GameCore()
            core._field.cell(4, 4).item = Item("red", 2)  # pylint: disable=W0212
            self.frame(core, tapped=cell_center(4, 4))
            self.frame(core, held=cell_center(*target))
            self.assertEqual(
                [
                    frame_outer(*target, COLOR_FRAME_NG),
                    frame_inner(*target, COLOR_FRAME_NG),
                ],
                self.frame_calls(self.draw_core(core)),
                target,
            )

    def test_frame_stays_on_source_cell_outside_field(self):
        """フィールドの外では、枠は操作元のマスに赤で残り、戻ると追従すること（FR2.3）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=cell_center(5, 5))  # 実行できるマスへ（緑）
        self.frame(core, held=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))  # フィールドの外
        self.assertEqual(
            [frame_outer(4, 4, COLOR_FRAME_NG), frame_inner(4, 4, COLOR_FRAME_NG)],
            self.frame_calls(self.draw_core(core)),
        )
        self.frame(core, held=cell_center(5, 5))
        self.assertEqual(
            [frame_outer(5, 5, COLOR_FRAME_OK), frame_inner(5, 5, COLOR_FRAME_OK)],
            self.frame_calls(self.draw_core(core)),
        )

    def test_frame_is_outline_drawn_after_cells_before_button(self):
        """枠は線だけで、マスと数字の後、スポーンボタンの前に描かれ、数字を隠さないこと"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        base = self.draw_core(core)  # 枠なしの描画
        button = 4  # スポーンボタンの描画: 背景 + 枠線 + SPAWN + Lv
        self.frame(core, tapped=cell_center(4, 4), held=cell_center(5, 5))
        self.assertEqual(
            base[:-button]
            + [frame_outer(5, 5, COLOR_FRAME_OK), frame_inner(5, 5, COLOR_FRAME_OK)]
            + base[-button:],
            self.draw_core(core),
        )

    @staticmethod
    def frame_calls(calls):
        """描画の呼び出しのうち、選択枠の色の枠線だけ"""
        return [
            c
            for c in calls
            if c[0] == "draw_rect_border" and c[5] in (COLOR_FRAME_OK, COLOR_FRAME_NG)
        ]


class TestPyxelInputSlide(unittest.TestCase):
    """PyxelInput の押している間・離した瞬間の位置（pyxel を差し替えて確かめる）"""

    def setUp(self):
        self.mock_pyxel = MagicMock()
        self.mock_pyxel.MOUSE_BUTTON_LEFT = 1
        self.mock_pyxel.mouse_x = 30
        self.mock_pyxel.mouse_y = 40
        patcher = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pyxel_input = main.PyxelInput()

    def test_held_position_while_left_button_held(self):
        """左ボタンを押している間は (mouse_x, mouse_y)、押していなければ「なし」"""
        self.mock_pyxel.btn.return_value = True
        self.assertEqual((30, 40), self.pyxel_input.held_position())
        self.mock_pyxel.btn.assert_called_with(1)
        self.mock_pyxel.btn.return_value = False
        self.assertIsNone(self.pyxel_input.held_position())

    def test_released_position_only_on_release_frame(self):
        """左ボタンを離したフレームだけ (mouse_x, mouse_y)、他は「なし」"""
        self.mock_pyxel.btnr.return_value = True
        self.assertEqual((30, 40), self.pyxel_input.released_position())
        self.mock_pyxel.btnr.assert_called_with(1)
        self.mock_pyxel.btnr.return_value = False
        self.assertIsNone(self.pyxel_input.released_position())


class TestGameCore(TestParent):
    def test_draw(self):
        """GameCore.draw() が View 経由で 100 マス分の描画をすること（BR2.8、BR2.9、FR4.1）"""
        core = GameCore()
        core.draw()
        calls = list(self.test_view.get_call_params())
        field = 100 + 100 + 4 * 2  # 背景 + 枠線 + マージ先にできる 8 マスの数字
        button = 1 + 1 + 2  # 背景 + 枠線 + SPAWN と Lv の文字
        delete_slot = 1 + 1 + 1  # 削除枠: 背景 + 枠線 + DEL の文字（常に描く）
        # 成長枠: マスごとの背景 + 枠線 + レベル 1 の項目 1 つ（青2）の数字（常に描く）
        growth_slot = GROWTH_CELLS + GROWTH_CELLS + 1
        clear_slot = CLEAR_SLOT_CALLS  # 背景 + 枠線 + 数字 6（常に描く）
        meter = METER_BASE_CALLS  # 背景 + 枠線（入れた数 0 なので塗りは無い）
        self.assertEqual(
            field + delete_slot + growth_slot + clear_slot + meter + button,
            len(calls),
        )
        # 状態は書き換えない: 2 回描いても同じ呼び出しになる
        core.draw()
        self.assertEqual(calls * 2, self.test_view.get_call_params())


class TestDropRules(unittest.TestCase):
    """離した先の判定（drop_action）と実行（apply_drop）のルール

    初期フィールドでは、中心の 2 × 2（(4,4)(5,4)(4,5)(5,5)）が開放済みの空き、
    (3,4) は 1 周目の未開放マス（開放済みの (4,4) に接するのでマージ先にできる）、
    (3,3) は 1 周目の未開放マスで、開放済みのマスに接しない（ロック中）
    """

    SRC = (4, 4)  # 操作元（開放済み）
    OPENED_DST = (5, 4)  # 開放済みの離した先
    CLOSED_DST = (3, 4)  # 未開放だがマージ先にできる離した先
    LOCKED_DST = (3, 3)  # 未開放でロック中の離した先

    def setUp(self):
        self.field = create_initial_field()

    def put(self, pos, item):
        """座標 pos のマスにアイテムを直接置く"""
        self.field.cell(*pos).item = item

    # --- 判定 ---

    def test_move_to_opened_empty_cell(self):
        # 開放済みの空きマスの上で離すと move
        self.put(self.SRC, Item("blue", 3))
        self.assertEqual("move", main.drop_action(self.field, self.SRC, (5, 4)))

    def test_merge_on_opened_cell(self):
        # 開放済みで、同色・同数字のアイテムがあるマスは merge（青と赤の両方）
        for color in ("blue", "red"):
            self.put(self.SRC, Item(color, 3))
            self.put(self.OPENED_DST, Item(color, 3))
            self.assertEqual(
                "merge", main.drop_action(self.field, self.SRC, self.OPENED_DST)
            )

    def test_merge_on_closed_unlocked_cell(self):
        # 未開放で、開放済みのマスに接するマス（ロック中でない）へも merge できる
        for color in ("blue", "red"):
            self.put(self.SRC, Item(color, 2))
            self.put(self.CLOSED_DST, Item(color, 2))
            self.assertEqual(
                "merge", main.drop_action(self.field, self.SRC, self.CLOSED_DST)
            )

    def test_none_when_color_differs(self):
        # 数字が同じでも、色が違えば実行できない
        self.put(self.SRC, Item("blue", 3))
        self.put(self.OPENED_DST, Item("red", 3))
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.OPENED_DST))

    def test_none_when_number_differs(self):
        # 色が同じでも、数字が違えば実行できない
        self.put(self.SRC, Item("blue", 3))
        self.put(self.OPENED_DST, Item("blue", 4))
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.OPENED_DST))

    def test_merge_reaches_max_number(self):
        # 最高の数字の 1 つ手前の同色同士をマージすると、最高の数字になる（FR1.1）
        below = main.MERGE_MAX_NUMBER - 1
        for color in ("blue", "red"):
            self.put(self.SRC, Item(color, below))
            self.put(self.OPENED_DST, Item(color, below))
            self.assertEqual(
                "merge", main.apply_drop(self.field, self.SRC, self.OPENED_DST)
            )
            self.assertEqual(
                Item(color, main.MERGE_MAX_NUMBER),
                self.field.cell(*self.OPENED_DST).item,
            )

    def test_none_when_number_is_max(self):
        # 同色・同数字でも、最高の数字（FR1.2）ならマージできない
        top = main.MERGE_MAX_NUMBER
        self.put(self.SRC, Item("blue", top))
        self.put(self.OPENED_DST, Item("blue", top))
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.OPENED_DST))

    def test_none_when_dst_is_locked(self):
        # 同色・同数字でも、ロック中の未開放マスはマージ先にできない
        locked_item = self.field.cell(*self.LOCKED_DST).item
        self.put(self.SRC, locked_item)
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.LOCKED_DST))

    def test_none_when_dst_is_src(self):
        # 離した先が操作元自身のときは実行できない
        self.put(self.SRC, Item("blue", 3))
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.SRC))

    def test_none_when_dst_is_outside(self):
        # 離した先がフィールドの外（None）のときは実行できない
        self.put(self.SRC, Item("blue", 3))
        self.assertIsNone(main.drop_action(self.field, self.SRC, None))

    def test_none_when_src_is_empty(self):
        # 操作元にアイテムが無いときは、開放済みの空きマスへでも実行できない
        self.assertIsNone(main.drop_action(self.field, self.SRC, self.OPENED_DST))

    def test_none_when_src_is_closed(self):
        # 操作元が未開放のときは、アイテムがあっても実行できない
        self.assertFalse(self.field.cell(*self.CLOSED_DST).opened)
        self.assertIsNotNone(self.field.cell(*self.CLOSED_DST).item)
        self.assertIsNone(main.drop_action(self.field, self.CLOSED_DST, self.SRC))

    def test_drop_action_does_not_change_field(self):
        # 判定は状態を変えない（merge・move・none のどの判定でも、呼ぶ前後でフィールドが同じ）
        self.put(self.SRC, Item("blue", 3))
        self.put(self.OPENED_DST, Item("blue", 3))
        before = copy.deepcopy(self.field)
        for dst in (self.OPENED_DST, (4, 5), self.LOCKED_DST, None):
            main.drop_action(self.field, self.SRC, dst)
            self.assertEqual(before, self.field)

    # --- 実行 ---

    def test_apply_move(self):
        # move: アイテムが離した先へ移り、操作元は空きマスになる
        item = Item("red", 4)
        self.put(self.SRC, item)
        result = main.apply_drop(self.field, self.SRC, self.OPENED_DST)
        self.assertEqual("move", result)
        self.assertEqual(item, self.field.cell(*self.OPENED_DST).item)
        self.assertIsNone(self.field.cell(*self.SRC).item)

    def test_apply_merge(self):
        # merge: 離した先に、同じ色で数字が 1 大きいアイテムが置かれ、操作元は空きマスになる
        for color in ("blue", "red"):
            number = 3
            self.put(self.SRC, Item(color, number))
            self.put(self.OPENED_DST, Item(color, number))
            result = main.apply_drop(self.field, self.SRC, self.OPENED_DST)
            self.assertEqual("merge", result)
            merged = Item(color, number + 1)  # マージ後の数字 = 元の数字 + 1
            self.assertEqual(merged, self.field.cell(*self.OPENED_DST).item)
            self.assertIsNone(self.field.cell(*self.SRC).item)

    def test_apply_merge_opens_closed_cell(self):
        # 未開放マスへのマージで、そのマスが開放済みになり、外側のマスが新たにマージ先になる
        outer = (
            2,
            4,
        )  # (3,4) の外側のマス。(3,4) が未開放の間は開放済みのマスに接しない
        self.assertFalse(self.field.is_mergeable(*outer))
        self.put(self.SRC, Item("blue", 2))
        self.put(self.CLOSED_DST, Item("blue", 2))
        result = main.apply_drop(self.field, self.SRC, self.CLOSED_DST)
        self.assertEqual("merge", result)
        self.assertTrue(self.field.cell(*self.CLOSED_DST).opened)
        self.assertEqual(Item("blue", 2 + 1), self.field.cell(*self.CLOSED_DST).item)
        self.assertTrue(self.field.is_mergeable(*outer))

    def test_apply_none_does_not_change_field(self):
        # 実行できないとき（色違い）は None を返し、フィールドは変わらない
        self.put(self.SRC, Item("blue", 3))
        self.put(self.OPENED_DST, Item("red", 3))
        before = copy.deepcopy(self.field)
        self.assertIsNone(main.apply_drop(self.field, self.SRC, self.OPENED_DST))
        self.assertEqual(before, self.field)


class TestDropDeleteRules(unittest.TestCase):
    """削除枠に離したときの判定（drop_action）と実行（apply_drop）のルール

    初期フィールドでは、(4,4) が開放済みの空き、(3,4) が未開放でアイテムありのマス
    """

    SRC = (4, 4)  # 操作元（開放済み）
    CLOSED = (3, 4)  # 未開放でアイテムがあるマス

    def setUp(self):
        self.field = create_initial_field()

    def put(self, pos, item):
        """座標 pos のマスにアイテムを直接置く"""
        self.field.cell(*pos).item = item

    def test_delete_on_delete_slot(self):
        # 削除枠に離すと delete（青 1）
        self.put(self.SRC, Item("blue", 1))
        self.assertEqual(
            main.DROP_DELETE, main.drop_action(self.field, self.SRC, main.DELETE_SLOT)
        )

    def test_delete_ignores_color_and_number(self):
        # 色・数字を問わず delete（赤、数字 5、最高の数字を含む）
        for color, number in (
            ("red", 1),
            ("blue", 5),
            ("red", 5),
            ("blue", main.MERGE_MAX_NUMBER),
            ("red", main.MERGE_MAX_NUMBER),
        ):
            self.put(self.SRC, Item(color, number))
            self.assertEqual(
                main.DROP_DELETE,
                main.drop_action(self.field, self.SRC, main.DELETE_SLOT),
            )

    def test_none_when_src_is_empty_or_closed(self):
        # 操作元が空き・未開放のときは、削除枠へでも実行できない
        self.assertIsNone(main.drop_action(self.field, self.SRC, main.DELETE_SLOT))
        self.assertIsNone(main.drop_action(self.field, self.CLOSED, main.DELETE_SLOT))

    def test_apply_delete(self):
        # delete: 操作元だけが空き（開放済みのまま）になり、他のマスは変わらない
        self.put(self.SRC, Item("blue", 3))
        expected = copy.deepcopy(self.field)
        expected.cell(*self.SRC).item = None  # 期待: 操作元以外は呼ぶ前と同じ
        result = main.apply_drop(self.field, self.SRC, main.DELETE_SLOT)
        self.assertEqual(main.DROP_DELETE, result)
        self.assertTrue(self.field.cell(*self.SRC).opened)
        self.assertEqual(expected, self.field)

    def test_apply_none_does_not_change_field(self):
        # 操作元が空き・未開放のとき、削除枠への実行は None を返し、フィールドは変わらない
        before = copy.deepcopy(self.field)
        for src in (self.SRC, self.CLOSED):
            self.assertIsNone(main.apply_drop(self.field, src, main.DELETE_SLOT))
            self.assertEqual(before, self.field)


class TestDropGrowthRules(unittest.TestCase):
    """成長枠のマスに離したときの判定（drop_action）と実行（apply_drop）のルール

    初期フィールドでは、(4,4) が開放済みの空き、(3,4) が未開放でアイテムありのマス
    """

    SRC = (4, 4)  # 操作元（開放済み）
    CLOSED = (3, 4)  # 未開放でアイテムがあるマス

    def setUp(self):
        self.field = create_initial_field()

    def put(self, pos, item):
        """座標 pos のマスにアイテムを直接置く"""
        self.field.cell(*pos).item = item

    def test_grow_when_same_item_not_achieved(self):
        # 成長枠の項目（青 2、未達成）と同じ色・数字のアイテムを離すと grow
        item = main.GROWTH_ITEMS[1][0]
        self.put(self.SRC, item)
        target = main.GrowthTarget(item, False)
        self.assertEqual(main.DROP_GROW, main.drop_action(self.field, self.SRC, target))

    def test_grow_for_every_item_of_level_6(self):
        # レベル 6 の 2 項目（青 2・赤 2）それぞれが、同じ項目の成長枠に grow できる
        items = main.GROWTH_ITEMS[6]
        self.assertEqual(2, len(items))  # 前提: 2 項目ある
        for item in items:
            self.put(self.SRC, item)
            target = main.GrowthTarget(item, False)
            self.assertEqual(
                main.DROP_GROW, main.drop_action(self.field, self.SRC, target)
            )

    def test_none_when_achieved(self):
        # 達成済みの項目には、同じ色・数字でも実行できない
        item = main.GROWTH_ITEMS[1][0]
        self.put(self.SRC, item)
        target = main.GrowthTarget(item, True)
        self.assertIsNone(main.drop_action(self.field, self.SRC, target))

    def test_none_when_color_or_number_differs(self):
        # 色違い・数字違いのアイテムは、項目に実行できない
        item = main.GROWTH_ITEMS[1][0]
        other_color = "red" if item.color == "blue" else "blue"
        target = main.GrowthTarget(item, False)
        for src_item in (
            Item(other_color, item.number),  # 色違い
            Item(item.color, item.number + 1),  # 数字違い
        ):
            self.put(self.SRC, src_item)
            self.assertIsNone(main.drop_action(self.field, self.SRC, target))

    def test_none_when_target_has_no_item(self):
        # 項目なし（空のセル、最高レベル）の成長枠には置けない
        self.put(self.SRC, Item("blue", 2))
        target = main.GrowthTarget(None, False)
        self.assertIsNone(main.drop_action(self.field, self.SRC, target))
        self.assertEqual(0, len(main.GROWTH_ITEMS[main.SPAWN_LEVEL_MAX]))  # 最高レベル

    def test_none_when_src_is_empty_or_closed(self):
        # 操作元が空き・未開放のときは、成長枠へでも実行できない
        item = main.GROWTH_ITEMS[1][0]
        target = main.GrowthTarget(item, False)
        self.assertIsNone(main.drop_action(self.field, self.SRC, target))  # 空き
        self.put(self.CLOSED, item)
        self.assertIsNone(main.drop_action(self.field, self.CLOSED, target))  # 未開放

    def test_apply_grow_empties_only_src(self):
        # grow: 操作元だけが空き（開放済みのまま）になり、他の全マスは変わらない
        item = main.GROWTH_ITEMS[1][0]
        self.put(self.SRC, item)
        expected = copy.deepcopy(self.field)
        expected.cell(*self.SRC).item = None  # 期待: 操作元以外は呼ぶ前と同じ
        target = main.GrowthTarget(item, False)
        result = main.apply_drop(self.field, self.SRC, target)
        self.assertEqual(main.DROP_GROW, result)
        self.assertTrue(self.field.cell(*self.SRC).opened)
        self.assertEqual(expected, self.field)

    def test_apply_none_does_not_change_field(self):
        # 実行できない成長枠（達成済み）への実行は None を返し、フィールドは変わらない
        item = main.GROWTH_ITEMS[1][0]
        self.put(self.SRC, item)
        before = copy.deepcopy(self.field)
        target = main.GrowthTarget(item, True)
        self.assertIsNone(main.apply_drop(self.field, self.SRC, target))
        self.assertEqual(before, self.field)

    def test_existing_destinations_unchanged(self):
        # 成長枠の追加後も、座標・削除枠・None への結果は変わらない
        self.put(self.SRC, Item("blue", 1))
        self.assertEqual(
            main.DROP_DELETE, main.drop_action(self.field, self.SRC, main.DELETE_SLOT)
        )
        self.assertEqual(main.DROP_MOVE, main.drop_action(self.field, self.SRC, (5, 4)))
        self.assertIsNone(main.drop_action(self.field, self.SRC, None))


class TestDropClearRules(unittest.TestCase):
    """クリア枠に離したときの判定（drop_action）と実行（apply_drop）のルール（BR3.1、BR3.2）

    初期フィールドでは、(4,4) が開放済みの空き、(3,4) が未開放でアイテムありのマス
    """

    SRC = (4, 4)  # 操作元（開放済み）
    CLOSED = (3, 4)  # 未開放でアイテムがあるマス
    COLORS = ("red", "blue")

    def setUp(self):
        self.field = create_initial_field()

    def put(self, pos, item):
        """座標 pos のマスにアイテムを直接置く"""
        self.field.cell(*pos).item = item

    def test_clear_when_max_number_and_color_matches(self):
        # 最高の数字で、指定の色のアイテムは、どちらの色でもクリア枠に入れられる（FR3.3）
        for color in self.COLORS:
            self.put(self.SRC, Item(color, main.MERGE_MAX_NUMBER))
            target = main.ClearTarget(color)
            self.assertEqual(
                main.DROP_CLEAR, main.drop_action(self.field, self.SRC, target), color
            )

    def test_none_when_color_differs(self):
        # 最高の数字でも、指定の色と違う色は入れられない（FR3.3）
        for color, other in (("red", "blue"), ("blue", "red")):
            self.put(self.SRC, Item(other, main.MERGE_MAX_NUMBER))
            target = main.ClearTarget(color)
            self.assertIsNone(main.drop_action(self.field, self.SRC, target), color)

    def test_none_when_number_is_not_max(self):
        # 最高の数字（MERGE_MAX_NUMBER）でなければ、指定の色でも入れられない（FR3.3）
        for number in (1, main.MERGE_MAX_NUMBER - 1):
            self.put(self.SRC, Item("red", number))
            target = main.ClearTarget("red")
            self.assertIsNone(main.drop_action(self.field, self.SRC, target), number)

    def test_none_when_src_is_empty_or_closed(self):
        # 操作元が空き・未開放のときは、クリア枠へでも実行できない
        item = Item("red", main.MERGE_MAX_NUMBER)
        target = main.ClearTarget("red")
        self.assertIsNone(main.drop_action(self.field, self.SRC, target))  # 空き
        self.put(self.CLOSED, item)
        self.assertIsNone(main.drop_action(self.field, self.CLOSED, target))  # 未開放

    def test_apply_clear_empties_only_src(self):
        # clear: 操作元だけが空き（開放済みのまま）になり、他の全マスは変わらない（BR3.2）
        self.put(self.SRC, Item("red", main.MERGE_MAX_NUMBER))
        expected = copy.deepcopy(self.field)
        expected.cell(*self.SRC).item = None  # 期待: 操作元以外は呼ぶ前と同じ
        result = main.apply_drop(self.field, self.SRC, main.ClearTarget("red"))
        self.assertEqual(main.DROP_CLEAR, result)
        self.assertTrue(self.field.cell(*self.SRC).opened)
        self.assertEqual(expected, self.field)

    def test_apply_none_does_not_change_field(self):
        # 実行できないクリア枠（違う色）への実行は None を返し、フィールドは変わらない
        self.put(self.SRC, Item("blue", main.MERGE_MAX_NUMBER))
        before = copy.deepcopy(self.field)
        self.assertIsNone(
            main.apply_drop(self.field, self.SRC, main.ClearTarget("red"))
        )
        self.assertEqual(before, self.field)


class TestClearSlotState(TestParent):
    """クリア枠の状態（入れた数・次の色）と、投入・クリアの判定・やり直し（BR3.2、BR4.1〜BR4.3）"""

    SRC = (4, 4)  # 操作元（開放済み）

    def drop_max(self, core, color=None):
        """マス SRC に、最高の数字のアイテム（color の既定は次の色）を置き、クリア枠に離す"""
        # pylint: disable=W0212
        color = color or core.clear_next_color
        core._field.cell(*self.SRC).item = Item(color, main.MERGE_MAX_NUMBER)
        core._selected = self.SRC
        core._on_drop(main.CLEAR_SLOT)

    def test_initial_state_is_zero_and_red(self):
        """開始時は、入れた数が 0、次に入れる色が赤であること（BR3.2）"""
        core = GameCore()
        self.assertEqual(0, core.clear_count)
        self.assertEqual("red", core.clear_next_color)

    def test_drop_inserts_item_and_counts(self):
        """投入すると、アイテムが消え（マスは開放済みの空き）、入れた数が 1 増えること（FR3.2）"""
        # pylint: disable=W0212
        core = GameCore()
        self.drop_max(core)
        self.assertEqual(0 + 1, core.clear_count)
        cell = core._field.cell(*self.SRC)
        self.assertIsNone(cell.item)
        self.assertTrue(cell.opened)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)

    def test_next_color_alternates_red_blue(self):
        """入れるたびに、次に入れる色が赤→青→赤と入れ替わること（FR3.2）"""
        core = GameCore()
        colors = []
        for _ in range(3):
            colors.append(core.clear_next_color)
            self.drop_max(core)
        self.assertEqual(["red", "blue", "red"], colors)
        self.assertEqual("blue", core.clear_next_color)

    def test_wrong_color_is_cancelled(self):
        """次の色と違う色の 6 は入れられず、数も色も変わらず、アイテムは元のマスのままであること（FR3.3）"""
        # pylint: disable=W0212
        core = GameCore()
        self.drop_max(core, "blue")  # 開始時の次の色は赤
        self.assertEqual(0, core.clear_count)
        self.assertEqual("red", core.clear_next_color)
        self.assertEqual(
            Item("blue", main.MERGE_MAX_NUMBER), core._field.cell(*self.SRC).item
        )

    def test_drop_keeps_spawn_level_and_achievements(self):
        """投入しても、スポーンのレベルと成長枠の達成状況は変わらないこと（BR3.2）"""
        # pylint: disable=W0212
        core = GameCore()
        core.achieve(main.GROWTH_ITEMS[1][0])  # レベル 2 へ
        level = core.spawn_level
        self.drop_max(core)
        self.assertEqual(level, core.spawn_level)
        self.assertEqual(set(), core._achieved)

    def test_resolve_target_gives_clear_target_with_next_color(self):
        """クリア枠の印を、次に入れる色を持つ ClearTarget に直すこと。他の離す先はそのまま（BR3.1）"""
        # pylint: disable=W0212
        core = GameCore()
        resolve = core._resolve_target
        self.assertEqual(main.ClearTarget("red"), resolve(main.CLEAR_SLOT))
        self.drop_max(core)
        self.assertEqual(main.ClearTarget("blue"), resolve(main.CLEAR_SLOT))
        self.assertIsNone(resolve(None))
        self.assertIs(main.DELETE_SLOT, resolve(main.DELETE_SLOT))

    def test_required_count_exceeds_initial_red5(self):
        """クリアに必要な数が、初期の赤5 の数（4 周目）より大きいこと（FR4.2）"""
        red5 = main.initial_item_of(4)
        self.assertEqual(Item("red", 5), red5)  # 前提: 4 周目は 赤5
        initial = [c.item for c in create_initial_field().cells]
        self.assertGreater(main.CLEAR_REQUIRED_COUNT, initial.count(red5))

    def test_playing_just_below_required_and_cleared_at_required(self):
        """必要な数 - 1 まではプレイ中で、必要な数に達した瞬間にクリアになること（FR4.3）"""
        core = GameCore()
        for _ in range(main.CLEAR_REQUIRED_COUNT - 1):
            self.drop_max(core)
        self.assertEqual(main.CLEAR_REQUIRED_COUNT - 1, core.clear_count)
        self.assertFalse(core.cleared)
        self.drop_max(core)
        self.assertEqual(main.CLEAR_REQUIRED_COUNT, core.clear_count)
        self.assertTrue(core.cleared)

    def test_max_level_does_not_clear(self):
        """最高レベルに達しても、クリアにならないこと。投入を続けられること（FR4.3）"""
        # pylint: disable=W0212
        core = GameCore()
        core._spawn_level = main.SPAWN_LEVEL_MAX
        self.assertFalse(core.cleared)
        self.drop_max(core)
        self.assertEqual(1, core.clear_count)

    def test_restart_resets_count_and_color(self):
        """やり直しで、入れた数が 0、次に入れる色が赤に戻り、プレイ中になること（FR4.4）"""
        core = GameCore()
        for _ in range(main.CLEAR_REQUIRED_COUNT - 1):  # 奇数個: 次の色は青
            self.drop_max(core)
        self.assertEqual("blue", core.clear_next_color)
        self.drop_max(core)
        self.assertTrue(core.cleared)
        core.restart()
        self.assertEqual(0, core.clear_count)
        self.assertEqual("red", core.clear_next_color)
        self.assertFalse(core.cleared)


class TestCellAt(unittest.TestCase):
    """画面位置からマスの座標を求める（フィールドの外は None）"""

    def test_inside_top_left_cell(self):
        # 左上のマスの内側（原点から 1 ピクセル内側）は (0, 0)
        self.assertEqual((0, 0), main.cell_at(ORIGIN_X + 1, ORIGIN_Y + 1))

    def test_inside_bottom_right_cell(self):
        # 右下のマスの内側（最後のマスの左上から 1 ピクセル内側）は (size-1, size-1)
        last = FIELD_SIZE - 1
        pos_x = ORIGIN_X + CELL_PITCH * last + 1
        pos_y = ORIGIN_Y + CELL_PITCH * last + 1
        self.assertEqual((last, last), main.cell_at(pos_x, pos_y))

    def test_inside_middle_cell(self):
        # 中央付近のマス (3, 6) の中ほど。x と y を取り違えないよう別の値にする
        cx, cy = 3, 6
        x = ORIGIN_X + CELL_PITCH * cx + CELL_PITCH // 2
        y = ORIGIN_Y + CELL_PITCH * cy + CELL_PITCH // 2
        self.assertEqual((cx, cy), main.cell_at(x, y))

    def test_overlap_pixel_x_belongs_to_right_cell(self):
        # 隣と重なる 1 ピクセル（左上から pitch 離れた x）は、右のマス (1, 0) に属する
        x = ORIGIN_X + CELL_PITCH
        self.assertEqual((1, 0), main.cell_at(x, ORIGIN_Y + 1))
        # その 1 つ手前のピクセルは左のマス (0, 0)
        self.assertEqual((0, 0), main.cell_at(x - 1, ORIGIN_Y + 1))

    def test_overlap_pixel_y_belongs_to_lower_cell(self):
        # 隣と重なる 1 ピクセル（左上から pitch 離れた y）は、下のマス (0, 1) に属する
        y = ORIGIN_Y + CELL_PITCH
        self.assertEqual((0, 1), main.cell_at(ORIGIN_X + 1, y))
        # その 1 つ手前のピクセルは上のマス (0, 0)
        self.assertEqual((0, 0), main.cell_at(ORIGIN_X + 1, y - 1))

    def test_outermost_border_belongs_to_last_cell(self):
        # 右・下の最も外側の枠線（origin + pitch * size）は、最後のマスに属する
        last = FIELD_SIZE - 1
        edge_x = ORIGIN_X + CELL_PITCH * FIELD_SIZE
        edge_y = ORIGIN_Y + CELL_PITCH * FIELD_SIZE
        self.assertEqual((last, last), main.cell_at(edge_x, edge_y))
        # 左上の枠線（origin）は最初のマスに属する
        self.assertEqual((0, 0), main.cell_at(ORIGIN_X, ORIGIN_Y))

    def test_outside_field_is_none(self):
        # フィールドの外（左・上・右・下）は None。もう 1 ピクセル外側で確かめる
        inside_x, inside_y = ORIGIN_X + 1, ORIGIN_Y + 1
        edge_x = ORIGIN_X + CELL_PITCH * FIELD_SIZE
        edge_y = ORIGIN_Y + CELL_PITCH * FIELD_SIZE
        self.assertIsNone(main.cell_at(ORIGIN_X - 1, inside_y))  # 左
        self.assertIsNone(main.cell_at(inside_x, ORIGIN_Y - 1))  # 上
        self.assertIsNone(main.cell_at(edge_x + 1, inside_y))  # 右
        self.assertIsNone(main.cell_at(inside_x, edge_y + 1))  # 下

    def test_clear_slot_and_meter_rows_are_outside_field(self):
        # フィールドの上（クリア枠・メーターの行）は、マスではない（FR5.1）
        self.assertIsNone(main.cell_at(ORIGIN_X + 1, CLEAR_Y))
        self.assertIsNone(main.cell_at(METER_X + 1, METER_Y))

    def test_spawn_button_and_screen_bottom_are_none(self):
        # スポーンボタンの中央と画面下部の隅は、フィールドの外なので None
        button_x = SPAWN_BUTTON_X + SPAWN_BUTTON_W // 2
        button_y = SPAWN_BUTTON_Y + SPAWN_BUTTON_H // 2
        self.assertIsNone(main.cell_at(button_x, button_y))
        self.assertIsNone(main.cell_at(SCREEN_WIDTH - 1, SCREEN_HEIGHT - 1))


class TestDeleteSlotInput(TestParent):
    """削除枠の当たり判定と、削除枠で離したときの流れ（入力）"""

    # 削除枠の内側の中心（領域は定数から計算する）
    CENTER = (
        main.DELETE_SLOT_X + main.DELETE_SLOT_W // 2,
        main.DELETE_SLOT_Y + main.DELETE_SLOT_H // 2,
    )

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    def test_target_at_inside_delete_slot(self):
        """削除枠の左上（含む）と右下の内側の端は DELETE_SLOT になること（FR1.1）"""
        left, top = main.DELETE_SLOT_X, main.DELETE_SLOT_Y
        right = left + main.DELETE_SLOT_W - 1  # 右下の内側の端（半開区間）
        bottom = top + main.DELETE_SLOT_H - 1
        self.assertIs(main.DELETE_SLOT, main.target_at(left, top))
        self.assertIs(main.DELETE_SLOT, main.target_at(right, bottom))

    def test_target_at_outside_delete_slot_is_none(self):
        """削除枠の外（左・上・右・下の 1 ピクセル外）はマスでも削除枠でもないこと（FR1.1）"""
        left, top = main.DELETE_SLOT_X, main.DELETE_SLOT_Y
        right = left + main.DELETE_SLOT_W  # 右下の外側
        bottom = top + main.DELETE_SLOT_H
        inside_y, inside_x = top + 1, left + 1
        self.assertIsNone(main.target_at(left - 1, inside_y))
        self.assertIsNone(main.target_at(inside_x, top - 1))
        self.assertIsNone(main.target_at(right, inside_y))
        self.assertIsNone(main.target_at(inside_x, bottom))

    def test_target_at_field_cell_returns_coord(self):
        """フィールドのマスの上は、そのマスの座標を返すこと（FR3.1）"""
        self.assertEqual((3, 6), main.target_at(*cell_center(3, 6)))

    def test_hovered_is_delete_slot_when_held_over_it(self):
        """押したまま削除枠の上へ動かすと、離す先が DELETE_SLOT になること（FR2.1）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.CENTER)
        self.assertIs(main.DELETE_SLOT, core.hovered)
        self.assertEqual((4, 4), core.selected)  # 選択は保たれる

    def test_release_on_delete_slot_deletes(self):
        """削除枠で離すと、アイテムが消え、操作元は開放済みの空きになり、状態が消えること（FR2.3）"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("blue", 2)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.CENTER)
        self.frame(core, released=self.CENTER)
        self.assertIsNone(field.cell(4, 4).item)
        self.assertTrue(field.cell(4, 4).opened)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)

    def test_release_outside_cancels(self):
        """スポーンボタンの上で離すと、アイテムは操作元のままで、状態が消えること（FR2.4）"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("blue", 2)
        outside = (SPAWN_BUTTON_X, SPAWN_BUTTON_Y)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=outside)
        self.frame(core, released=outside)
        self.assertEqual(Item("blue", 2), field.cell(4, 4).item)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)
        self.assertEqual(1, len(placed_cells(core)))  # スポーンもしていない

    def test_round_trip_via_delete_slot_then_merge(self):
        """削除枠を経由してフィールドへ戻り、同じ数字のマスで離すとマージされること（FR2.4）"""
        core = GameCore()
        field = core._field  # pylint: disable=W0212
        field.cell(4, 4).item = Item("blue", 2)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.CENTER)
        self.assertIs(main.DELETE_SLOT, core.hovered)
        self.frame(core, held=cell_center(3, 4))
        self.assertEqual((3, 4), core.hovered)
        self.frame(core, released=cell_center(3, 4))
        self.assertIsNone(field.cell(4, 4).item)
        self.assertEqual(Item("blue", 3), field.cell(3, 4).item)

    def test_press_on_delete_slot_does_not_select(self):
        """削除枠を押しても、操作元にならず、スポーンもしないこと（FR3.1）"""
        core = GameCore()
        self.frame(core, tapped=self.CENTER)
        self.assertIsNone(core.selected)
        self.assertEqual([], placed_cells(core))


class GrowthSlotInputTestBase(TestParent):
    """成長枠の入力のテストが共有する準備（テストは持たない）"""

    COLUMNS = GROWTH_COLUMNS  # 成長枠は 1 行 2 列のマス目
    ROWS = GROWTH_ROWS
    CELLS = GROWTH_CELLS

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    @staticmethod
    def slot_cell_left_top(index):
        """成長枠のマス index（左上から右へ行ごと）の左上の画面位置"""
        row, col = divmod(index, GrowthSlotInputTestBase.COLUMNS)
        return (
            main.GROWTH_SLOT_X + CELL_PITCH * col,
            main.GROWTH_SLOT_Y + CELL_PITCH * row,
        )

    def slot_center(self, index):
        """成長枠のマス index の中心の画面位置（枠線の重なりを避けるため半分進める）"""
        left, top = self.slot_cell_left_top(index)
        return (left + CELL_PITCH // 2, top + CELL_PITCH // 2)

    @staticmethod
    def core_at_level(level, item):
        """レベルを level にし、フィールドのマス (4, 4) に item を置いたゲーム"""
        core = GameCore()
        core._spawn_level = level  # pylint: disable=W0212
        core._field.cell(4, 4).item = item  # pylint: disable=W0212
        return core

    def drag_to_slot(self, core, index):
        """マス (4, 4) を押し、成長枠のマス index へ動かして離す"""
        target = self.slot_center(index)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=target)
        self.frame(core, released=target)


class TestGrowthSlotInputHitTest(GrowthSlotInputTestBase):
    """成長枠の位置と当たり判定"""

    def test_target_at_cell0_inside(self):
        """成長枠のマス 0（左上）の内側の位置は GrowthSlotCell(0) になること（FR1.1）"""
        x = main.GROWTH_SLOT_X + 1
        y = main.GROWTH_SLOT_Y + 1
        self.assertEqual(main.GrowthSlotCell(0), main.target_at(x, y))

    def test_target_at_every_cell_center(self):
        """どのマス（0〜1）も、中心の位置は自分の番号の GrowthSlotCell になること（FR1.1）"""
        for index in range(self.CELLS):
            self.assertEqual(
                main.GrowthSlotCell(index),
                main.target_at(*self.slot_center(index)),
                index,
            )

    def test_target_at_overlap_pixel_belongs_to_later_cell(self):
        """隣のマスと重なる 1 ピクセルは右・下のマスに属し、その手前は前のマスに属すること（FR1.1）"""
        for index in range(self.CELLS):
            left, top = self.slot_cell_left_top(index)
            self.assertEqual(
                main.GrowthSlotCell(index),
                main.target_at(left, top),
                index,
            )
        left1, top0 = self.slot_cell_left_top(1)
        self.assertEqual(
            main.GrowthSlotCell(0), main.target_at(left1 - 1, top0 + 1)
        )  # 列 1 の左の 1 ピクセル手前は列 0

    def test_target_at_last_edge_belongs_to_last_cell(self):
        """右下の最も内側の端（領域の右下）は最後のマス 1 になること（FR1.1）"""
        x = main.GROWTH_SLOT_X + main.GROWTH_SLOT_W - 1
        y = main.GROWTH_SLOT_Y + main.GROWTH_SLOT_H - 1
        self.assertEqual(main.GrowthSlotCell(self.CELLS - 1), main.target_at(x, y))

    def test_slot_has_two_columns_and_one_row(self):
        """成長枠の形は 1 行 2 列で、番号 0〜1 の 2 マスだけであること（FR1.1）"""
        self.assertEqual(GROWTH_COLUMNS, main.GROWTH_SLOT_COLUMNS)
        self.assertEqual(GROWTH_ROWS, main.GROWTH_SLOT_ROWS)
        indexes = set()
        for y in range(main.GROWTH_SLOT_Y, main.GROWTH_SLOT_Y + main.GROWTH_SLOT_H):
            for x in range(main.GROWTH_SLOT_X, main.GROWTH_SLOT_X + main.GROWTH_SLOT_W):
                indexes.add(main.target_at(x, y))
        self.assertEqual({main.GrowthSlotCell(i) for i in range(self.CELLS)}, indexes)

    def test_target_at_outside_slot_is_none(self):
        """成長枠の外（左・上・右・下の 1 ピクセル外、右下の外側）は何でもないこと（FR1.1）"""
        left, top = main.GROWTH_SLOT_X, main.GROWTH_SLOT_Y
        right = left + main.GROWTH_SLOT_W  # 右下の外側（半開区間）
        bottom = top + main.GROWTH_SLOT_H
        inside_x, inside_y = left + 1, top + 1
        self.assertIsNone(main.target_at(left - 1, inside_y))
        self.assertIsNone(main.target_at(inside_x, top - 1))
        self.assertIsNone(main.target_at(right, inside_y))
        self.assertIsNone(main.target_at(inside_x, bottom))
        self.assertIsNone(main.target_at(right, bottom))

    def test_area_size_and_alignment(self):
        """幅は 2 マスぶん、高さは 1 マスぶん、縦は削除枠と同じ行にそろい、画面に収まること（FR4）"""
        width = CELL_PITCH * (self.COLUMNS - 1) + CELL_SIZE  # 14 * 1 + 15 = 29
        height = CELL_PITCH * (self.ROWS - 1) + CELL_SIZE  # 14 * 0 + 15 = 15
        self.assertEqual(width, main.GROWTH_SLOT_W)
        self.assertEqual(height, main.GROWTH_SLOT_H)
        self.assertEqual(DELETE_SLOT_Y, main.GROWTH_SLOT_Y)  # 削除枠と同じ行
        self.assertLessEqual(
            main.GROWTH_SLOT_Y + main.GROWTH_SLOT_H, main.SCREEN_HEIGHT
        )
        self.assertLessEqual(main.GROWTH_SLOT_X + main.GROWTH_SLOT_W, SCREEN_WIDTH)

    def test_growth_slot_has_equal_margins_on_both_sides(self):
        """成長枠の左右の空白が同じこと（スポーンボタンの右端とフィールドの右端の間の中央）（FR4）"""
        button_right = SPAWN_BUTTON_X + SPAWN_BUTTON_W
        field_right = ORIGIN_X + CELL_PITCH * main.FIELD_SIZE
        left_margin = main.GROWTH_SLOT_X - button_right
        right_margin = field_right - (main.GROWTH_SLOT_X + main.GROWTH_SLOT_W)
        self.assertEqual(left_margin, right_margin)

    def test_delete_slot_has_equal_margins_on_both_sides(self):
        """削除枠の左右の空白が同じこと（フィールドの左端とスポーンボタンの左端の間の中央）（FR4）"""
        left_margin = DELETE_SLOT_X - ORIGIN_X
        right_margin = SPAWN_BUTTON_X - (DELETE_SLOT_X + main.DELETE_SLOT_W)
        self.assertEqual(left_margin, right_margin)

    def test_spawn_button_position_follows_field(self):
        """スポーンボタンは画面の中央で、上端はフィールドの下端 + 隙間であること（FR4、FR5.1）"""
        self.assertEqual(FIELD_BOTTOM + SPAWN_GAP, SPAWN_BUTTON_Y)
        self.assertEqual(SCREEN_WIDTH // 2, SPAWN_BUTTON_X + main.SPAWN_BUTTON_W // 2)

    def test_area_is_clear_of_neighbors(self):
        """スポーンボタン・削除枠・フィールドと重ならないこと（FR1.1）"""
        slot_left, slot_top = main.GROWTH_SLOT_X, main.GROWTH_SLOT_Y
        self.assertGreaterEqual(slot_left, SPAWN_BUTTON_X + main.SPAWN_BUTTON_W)
        self.assertGreater(slot_left, main.DELETE_SLOT_X + main.DELETE_SLOT_W)
        field_bottom = ORIGIN_Y + CELL_PITCH * main.FIELD_SIZE
        self.assertGreater(slot_top, field_bottom)

    def test_existing_destinations_unchanged(self):
        """マス・削除枠・スポーンボタンの上の離す先は変わらないこと（FR2.4）"""
        self.assertEqual((3, 6), main.target_at(*cell_center(3, 6)))
        delete_center = (
            main.DELETE_SLOT_X + main.DELETE_SLOT_W // 2,
            main.DELETE_SLOT_Y + main.DELETE_SLOT_H // 2,
        )
        self.assertIs(main.DELETE_SLOT, main.target_at(*delete_center))
        self.assertIsNone(main.target_at(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))


class TestGrowthSlotInput(GrowthSlotInputTestBase):
    """成長枠で押す・動かす・離すときの流れ（入力）"""

    def test_hovered_follows_slot_cell_and_clears_outside(self):
        """押したまま成長枠の上で hovered が GrowthSlotCell(index)、外に出ると None になること（FR2.1）"""
        core = self.core_at_level(6, Item("blue", 2))
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.slot_center(1))
        self.assertEqual(main.GrowthSlotCell(1), core.hovered)
        self.assertEqual((4, 4), core.selected)  # 選択は保たれる
        self.frame(core, held=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertIsNone(core.hovered)

    def test_release_on_item_places_and_levels_up(self):
        """レベル 1 で 青2 を項目のマス 0 で離すと、操作元が空き、レベル 2 になること（FR2.2、FR3.1）"""
        core = self.core_at_level(1, Item("blue", 2))
        self.drag_to_slot(core, 0)
        self.assertIsNone(core._field.cell(4, 4).item)  # pylint: disable=W0212
        self.assertTrue(core._field.cell(4, 4).opened)  # pylint: disable=W0212
        self.assertEqual(1 + 1, core.spawn_level)
        self.assertEqual(growth_items_of(2), core.growth_items)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)

    def test_release_cancels_on_wrong_item(self):
        """項目と違うアイテム（青3）を離すと、アイテムは元のマスのままレベルも変わらないこと（FR2.3）"""
        core = self.core_at_level(1, Item("blue", 3))
        self.drag_to_slot(core, 0)
        self.assertEqual(
            Item("blue", 3), core._field.cell(4, 4).item  # pylint: disable=W0212
        )
        self.assertEqual(1, core.spawn_level)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)

    def test_release_cancels_on_cell_without_item(self):
        """レベル 1 の項目なしのマス（項目数以上の番号）で離すと、キャンセルされること（FR2.3）"""
        level = 1
        empty_index = len(
            growth_items_of(level)
        )  # 最初の項目なしのマス（= 最後のマス 1）
        self.assertEqual(self.CELLS - 1, empty_index)
        core = self.core_at_level(level, Item("blue", 2))
        self.drag_to_slot(core, empty_index)
        self.assertEqual(
            Item("blue", 2), core._field.cell(4, 4).item  # pylint: disable=W0212
        )
        self.assertEqual(level, core.spawn_level)

    def test_release_cancels_at_max_level(self):
        """最高レベル（項目なし）では、どのマスで離してもキャンセルされること（FR2.3）"""
        core = self.core_at_level(main.SPAWN_LEVEL_MAX, Item("blue", 2))
        for index in range(self.CELLS):
            self.drag_to_slot(core, index)
            self.assertEqual(
                Item("blue", 2),
                core._field.cell(4, 4).item,  # pylint: disable=W0212
                index,
            )
        self.assertEqual(main.SPAWN_LEVEL_MAX, core.spawn_level)

    def test_release_cancels_on_achieved_item(self):
        """達成済みの項目のマスで離すと、キャンセルされること（FR2.3）"""
        level = 6
        first, _ = growth_items_of(level)
        core = self.core_at_level(level, first)
        core.achieve(first)  # 片方だけ達成済み（レベルは 6 のまま）
        self.drag_to_slot(core, 0)
        self.assertEqual(first, core._field.cell(4, 4).item)  # pylint: disable=W0212
        self.assertEqual(level, core.spawn_level)

    def test_two_items_level_needs_both_placed(self):
        """レベル 6 は片方だけではレベルが変わらず、もう片方を置くと 7 になること（FR3.1）"""
        level = 6
        for order in (range(2), reversed(range(2))):
            core = self.core_at_level(level, None)
            order = list(order)
            self.place_item_on_slot(core, order[0], level)
            self.assertEqual(level, core.spawn_level, order)
            self.place_item_on_slot(core, order[1], level)
            self.assertEqual(level + 1, core.spawn_level, order)

    def place_item_on_slot(self, core, index, level):
        """成長枠のマス index の項目をマス (4, 4) に置いて、そのマスへ動かして離す"""
        item = growth_items_of(level)[index]
        core._field.cell(4, 4).item = item  # pylint: disable=W0212
        self.drag_to_slot(core, index)

    def test_round_trip_through_slot_and_back(self):
        """成長枠から外に出て戻ってから離しても、実行されること（FR2.1、FR2.2）"""
        core = self.core_at_level(1, Item("blue", 2))
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.slot_center(0))
        self.assertEqual(main.GrowthSlotCell(0), core.hovered)
        self.frame(core, held=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertIsNone(core.hovered)
        self.frame(core, held=self.slot_center(0))
        self.assertEqual(main.GrowthSlotCell(0), core.hovered)
        self.frame(core, released=self.slot_center(0))
        self.assertEqual(1 + 1, core.spawn_level)

    def test_press_on_slot_does_not_spawn_or_select(self):
        """成長枠の位置を押しても、操作元にならず、スポーンもしないこと（FR2.4）"""
        core = GameCore()
        before = len(placed_cells(core))
        self.frame(core, tapped=self.slot_center(0))
        self.assertIsNone(core.selected)
        self.assertEqual(before, len(placed_cells(core)))

    def test_selection_frame_does_not_crash_over_slot(self):
        """成長枠の上でも選択枠の計算が落ちないこと（描画は別の Unit）"""
        core = self.core_at_level(1, Item("blue", 2))
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.slot_center(0))
        core.draw()


def delete_slot_background():
    """削除枠の背景の呼び出し（領域の定数から作る）"""
    return (
        "draw_rect",
        DELETE_SLOT_X,
        DELETE_SLOT_Y,
        DELETE_SLOT_W,
        DELETE_SLOT_H,
        COLOR_DELETE_BG,
    )


def delete_slot_border():
    """削除枠の枠線の呼び出し"""
    return (
        "draw_rect_border",
        DELETE_SLOT_X,
        DELETE_SLOT_Y,
        DELETE_SLOT_W,
        DELETE_SLOT_H,
        COLOR_DELETE_BORDER,
    )


def delete_slot_label():
    """削除枠の DEL の呼び出し（文字位置の定数から作る）"""
    return (
        "draw_text",
        DELETE_SLOT_X + DELETE_LABEL_OFFSET_X,
        DELETE_SLOT_Y + DELETE_LABEL_OFFSET_Y,
        "DEL",
        COLOR_DELETE_TEXT,
    )


class TestDeleteSlotView(TestParent):
    """削除枠の常時描画と、スライド中に削除枠の上へ出る選択枠"""

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    def test_background_is_drawn_when_nothing_selected(self):
        """選択していないとき、削除枠の背景が領域の定数どおりに描かれること（FR1.1）"""
        self.assertIn(delete_slot_background(), self.draw_core())

    def test_border_and_label_are_always_drawn_in_order(self):
        """背景 → 枠線 → DEL が、定数から計算した位置と色で連続して描かれ、選択の有無で変わらないこと（FR1.2）"""
        expected = [delete_slot_background(), delete_slot_border(), delete_slot_label()]
        idle = self.draw_core()
        start = idle.index(delete_slot_background())
        self.assertEqual(expected, idle[start : start + 3])
        # DEL（3 文字 × 幅 4 - 1 = 11、高さ 5）が削除枠の中央に来る位置であること
        text_w, text_h = 3 * 4 - 1, 5
        _, x, y, _, _ = delete_slot_label()
        self.assertEqual(
            (
                DELETE_SLOT_X + (DELETE_SLOT_W - text_w) // 2,
                DELETE_SLOT_Y + (DELETE_SLOT_H - text_h) // 2,
            ),
            (x, y),
        )
        # アイテムを選択して削除枠の上にいても、削除枠自体の描画は同じ
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=self.slot_center())
        selected = self.draw_core(core)
        for call in expected:
            self.assertIn(call, selected)

    def test_draw_order_cells_slot_frame_button(self):
        """描画の順序は マス → 削除枠 → 成長枠 → クリア枠 → メーター → 選択枠 → スポーンボタン であること（FR2.1、FR5.3）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        base = self.draw_core(core)
        slot = [delete_slot_background(), delete_slot_border(), delete_slot_label()]
        button = 4  # スポーンボタンの描画: 背景 + 枠線 + SPAWN + Lv
        growth = GROWTH_CELLS * 2 + 1  # 成長枠は削除枠の後（レベル 1 は項目 1 つ）
        upper = CLEAR_SLOT_CALLS + METER_BASE_CALLS  # クリア枠とメーターは成長枠の後
        # 削除枠は成長枠の直前
        tail = growth + upper + button
        self.assertEqual(slot, base[-tail - 3 : -tail])
        self.frame(core, tapped=cell_center(4, 4), held=self.slot_center())
        frame = self.frame_calls_on_slot(COLOR_FRAME_OK)
        self.assertEqual(base[:-button] + frame + base[-button:], self.draw_core(core))

    def test_frame_is_green_on_delete_slot(self):
        """削除枠の上では、選択枠が削除枠の領域に二重の枠線で緑で描かれること（FR2.1）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=self.slot_center())
        self.assertEqual(
            self.frame_calls_on_slot(COLOR_FRAME_OK),
            TestSelectionFrameView.frame_calls(self.draw_core(core)),
        )

    def test_frame_stays_red_on_source_cell_outside(self):
        """削除枠の外（スポーンボタンの上）では、選択枠は操作元のマスに赤で残ること（従来どおり）"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=self.slot_center())
        self.frame(core, held=(SPAWN_BUTTON_X, SPAWN_BUTTON_Y))
        self.assertEqual(
            [frame_outer(4, 4, COLOR_FRAME_NG), frame_inner(4, 4, COLOR_FRAME_NG)],
            TestSelectionFrameView.frame_calls(self.draw_core(core)),
        )

    def test_no_frame_after_release_on_delete_slot(self):
        """削除枠で離した後（削除の実行後）は、選択枠が描かれないこと"""
        core = GameCore()
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4), held=self.slot_center())
        self.frame(core, released=self.slot_center())
        self.assertEqual([], TestSelectionFrameView.frame_calls(self.draw_core(core)))

    @staticmethod
    def slot_center():
        """削除枠の内側の中心の画面位置"""
        return (
            DELETE_SLOT_X + DELETE_SLOT_W // 2,
            DELETE_SLOT_Y + DELETE_SLOT_H // 2,
        )

    @staticmethod
    def frame_calls_on_slot(color):
        """削除枠の領域に描かれる選択枠の期待値: 外側は領域と同じ、内側は 1 ピクセル内側"""
        return [
            (
                "draw_rect_border",
                DELETE_SLOT_X,
                DELETE_SLOT_Y,
                DELETE_SLOT_W,
                DELETE_SLOT_H,
                color,
            ),
            (
                "draw_rect_border",
                DELETE_SLOT_X + 1,
                DELETE_SLOT_Y + 1,
                DELETE_SLOT_W - 2,
                DELETE_SLOT_H - 2,
                color,
            ),
        ]


# 成長枠の項目の表（要件 FR3.1）。レベル → (色, 数字) の並び
GROWTH_TABLE = {
    1: (("blue", 2),),
    2: (("blue", 3),),
    3: (("blue", 2), ("blue", 3)),
    4: (("blue", 4),),
    5: (("blue", 3), ("blue", 4)),
    6: (("blue", 2), ("red", 2)),
    7: (("blue", 3), ("red", 2)),
    8: (("blue", 3), ("red", 3)),
    9: (("blue", 4), ("red", 3)),
    10: (("blue", 4), ("red", 4)),
    11: (("blue", 5),),
    12: (("blue", 5), ("red", 3)),
    13: (("blue", 5), ("red", 4)),
    14: (("blue", 4), ("red", 5)),
    15: (("blue", 5), ("red", 5)),
    16: (("blue", 5), ("red", 5)),
    17: (("blue", 5), ("red", 5)),
    18: (("blue", 5), ("red", 5)),
    19: (("blue", 5), ("red", 5)),
    20: (),  # 最高レベルは項目なし（FR1.2）
}
# 赤が出始めるレベル（出現確率の段階 3 の先頭。要件 FR3.3）
FIRST_RED_LEVEL = min(STAGE_LEVEL_RANGES[3])


def growth_items_of(level):
    return tuple(Item(color, number) for color, number in GROWTH_TABLE[level])


def growth_cell_left_top(index):
    """成長枠のマス index（左上から右へ行ごと、2 列）の左上の画面位置（定数から計算）"""
    row, col = divmod(index, GROWTH_COLUMNS)
    return (
        main.GROWTH_SLOT_X + CELL_PITCH * col,
        main.GROWTH_SLOT_Y + CELL_PITCH * row,
    )


def growth_background(index):
    """成長枠のマス index の背景の呼び出し（フィールドの開放済みのマスと同じ見た目）"""
    left, top = growth_cell_left_top(index)
    return ("draw_rect", left, top, CELL_SIZE, CELL_SIZE, COLOR_OPENED_BG)


def growth_border(index):
    """成長枠のマス index の枠線の呼び出し"""
    left, top = growth_cell_left_top(index)
    return ("draw_rect_border", left, top, CELL_SIZE, CELL_SIZE, COLOR_BORDER)


def growth_number(index, number, color):
    """成長枠のマス index の数字の呼び出し（フィールドのアイテムと同じずらし量）"""
    left, top = growth_cell_left_top(index)
    return (
        "draw_text",
        left + main.TEXT_OFFSET_X,
        top + main.TEXT_OFFSET_Y,
        str(number),
        color,
    )


def growth_frame(index, color):
    """成長枠のマス index に置く選択枠の二重の枠線（外側はマスと同じ、内側は 1 ピクセル内側）"""
    left, top = growth_cell_left_top(index)
    return [
        ("draw_rect_border", left, top, CELL_SIZE, CELL_SIZE, color),
        ("draw_rect_border", left + 1, top + 1, CELL_SIZE - 2, CELL_SIZE - 2, color),
    ]


class TestGrowthSlotView(TestParent):
    """成長枠の常時描画（背景 → 枠線 → 数字）、成長枠の上の選択枠、Lv の追従"""

    def setUp(self):
        super().setUp()
        self.test_input = TestInput()
        patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        patcher_input.start()
        self.addCleanup(patcher_input.stop)

    def frame(self, core, tapped=None, held=None, released=None):
        """押した・押している間・離したの位置を指定して、1 フレーム進める"""
        self.test_input.positions.append(tapped)
        self.test_input.held.append(held)
        self.test_input.released.append(released)
        core.update()

    @staticmethod
    def core_at_level(level):
        core = GameCore()
        core._spawn_level = level  # pylint: disable=W0212
        return core

    def growth_section(self, core, length):
        """描画の呼び出しのうち、成長枠のマス 0 の背景から length 個"""
        calls = self.draw_core(core)
        start = calls.index(growth_background(0))
        return calls[start : start + length]

    def slide_to_growth(self, level, item, index):
        """レベル level で、マス (4, 4) の item を押して成長枠のマス index の上へ動かしたゲーム"""
        core = self.core_at_level(level)
        core._field.cell(4, 4).item = item  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        left, top = growth_cell_left_top(index)
        self.frame(core, held=(left + CELL_PITCH // 2, top + CELL_PITCH // 2))
        return core

    def test_cell0_background_at_start(self):
        """開始直後（レベル 1）に、成長枠のマス 0 の背景が期待の位置・大きさ・色で描かれること（FR1.1）"""
        left, top = growth_cell_left_top(0)
        expected = ("draw_rect", left, top, CELL_SIZE, CELL_SIZE, COLOR_OPENED_BG)
        self.assertIn(expected, self.draw_core())

    def test_two_cells_drawn_background_border_number_in_order(self):
        """レベル 1 は、マス 0 から 1 の順に 背景 → 枠線（→ 項目があれば数字）で描かれ、項目はマス 0 の 青2 だけで、マス 1 は枠だけであること（FR2.1、FR2.2）"""
        expected = [
            growth_background(0),
            growth_border(0),
            growth_number(0, 2, COLOR_BLUE_TEXT),
        ]
        for index in range(1, GROWTH_CELLS):  # 項目の無いマスは枠だけ
            expected += [growth_background(index), growth_border(index)]
        self.assertEqual(expected, self.growth_section(GameCore(), len(expected)))

    def test_achieved_item_is_gray_and_unachieved_is_colored(self):
        """レベル 6 で 青2 だけ達成済みのとき、マス 0 の 青2 がグレー、マス 1 の 赤2 が色つきで描かれること（FR1.2、FR1.3）"""
        core = self.core_at_level(6)
        core.achieve(Item("blue", 2))
        expected = [
            growth_background(0),
            growth_border(0),
            growth_number(0, 2, main.COLOR_ACHIEVED_TEXT),
            growth_background(1),
            growth_border(1),
            growth_number(1, 2, COLOR_RED_TEXT),
        ]
        self.assertEqual(expected, self.growth_section(core, len(expected)))
        colors = {COLOR_BLUE_TEXT, COLOR_RED_TEXT, main.COLOR_ACHIEVED_TEXT}
        self.assertEqual(3, len(colors))  # グレーは青・赤と見分けられる

    def test_max_level_draws_frames_only(self):
        """最高レベルは、2 マスとも枠だけで数字が描かれないこと（FR2.2）"""
        expected = []
        for index in range(GROWTH_CELLS):
            expected += [growth_background(index), growth_border(index)]
        core = self.core_at_level(main.SPAWN_LEVEL_MAX)
        self.assertEqual(expected, self.growth_section(core, len(expected)))
        calls = self.draw_core(core)
        start = calls.index(growth_background(0)) + len(expected)
        # 成長枠の直後はクリア枠、その後にメーター、スポーンボタン
        self.assertEqual(clear_slot_calls("red"), calls[start : start + 3])
        self.assertEqual(button_background(), calls[start + 3 + len(meter_calls(0))])

    def test_frame_is_green_on_matching_unachieved_item_cell(self):
        """赤2 を持って、赤2（未達成）のマス 1 の上では、そのマスに緑の選択枠が置かれること（FR2.1）"""
        core = self.slide_to_growth(6, Item("red", 2), 1)
        self.assertEqual(
            growth_frame(1, COLOR_FRAME_OK),
            TestSelectionFrameView.frame_calls(self.draw_core(core)),
        )

    def test_frame_is_red_on_mismatching_empty_and_achieved_cells(self):
        """合わない項目のマス・項目の無いマス・達成済みのマスの上では、そのマスに赤の選択枠が置かれること（FR2.3）"""
        cases = (
            (6, Item("blue", 2), 1, False),  # 色違い（マス 1 は 赤2）
            (1, Item("blue", 2), 1, False),  # 項目の無いマス（レベル 1 のマス 1）
            (6, Item("blue", 2), 0, True),  # 青2 は達成済み
        )
        for level, item, index, achieved in cases:
            core = self.slide_to_growth(level, item, index)
            if achieved:
                core.achieve(Item("blue", 2))
            self.assertEqual(
                growth_frame(index, COLOR_FRAME_NG),
                TestSelectionFrameView.frame_calls(self.draw_core(core)),
                (level, item, index, achieved),
            )

    def test_lv_follows_level_2_and_max(self):
        """スポーンボタンの文字が、レベル 2 と最高レベルでそれぞれ Lv2、Lv20 になること（FR1.2）"""
        for level in (2, main.SPAWN_LEVEL_MAX):
            calls = self.draw_core(self.core_at_level(level))
            self.assertIn(spawn_level_text(level), calls)

    def test_draw_order_cells_delete_growth_frame_button(self):
        """描く順は マス → 削除枠 → 成長枠 → 選択枠 → スポーンボタンであること"""
        core = self.slide_to_growth(6, Item("red", 2), 1)
        calls = self.draw_core(core)
        delete = [delete_slot_background(), delete_slot_border(), delete_slot_label()]
        growth = []
        for index in range(2):  # レベル 6: マス 0・1 に数字、他は枠だけ
            growth += [growth_background(index), growth_border(index)]
            growth.append(
                growth_number(
                    index, 2, COLOR_BLUE_TEXT if index == 0 else COLOR_RED_TEXT
                )
            )
        for index in range(
            2, GROWTH_CELLS
        ):  # 2 マスとも項目があるので、枠だけのマスは無い
            growth += [growth_background(index), growth_border(index)]
        button = 4  # スポーンボタン: 背景 + 枠線 + SPAWN + Lv
        upper = clear_slot_calls("red") + meter_calls(0)
        tail = delete + growth + upper + growth_frame(1, COLOR_FRAME_OK)
        self.assertEqual(tail, calls[-button - len(tail) : -button])
        self.assertEqual(button_background(), calls[-button])
        self.assertEqual(field_calls_end(calls), calls.index(delete_slot_background()))

    def test_all_text_is_ascii(self):
        """成長枠を含む画面上の文字がすべて ASCII であること（NFR1）"""
        for level in range(1, main.SPAWN_LEVEL_MAX + 1):
            texts = [
                c[3]
                for c in self.draw_core(self.core_at_level(level))
                if c[0] == "draw_text"
            ]
            self.assertTrue(all(text.isascii() for text in texts), level)


class TestGrowthLevel(TestParent):
    def test_starts_at_level_1_with_blue2_unachieved(self):
        """開始時はレベル 1 で、成長枠の項目は 青2 のみ・未達成であること（BR1.1、FR3.2）"""
        core = GameCore()
        self.assertEqual(main.SPAWN_LEVEL_START, core.spawn_level)
        self.assertEqual(growth_items_of(1), core.growth_items)
        self.assertFalse(core.is_achieved(Item("blue", 2)))

    def test_items_follow_table_per_level(self):
        """各レベルの項目が表のとおりで、最高レベルは空であること（FR1.2、FR3.1）"""
        self.assertEqual(set(range(1, SPAWN_LEVELS + 1)), set(GROWTH_TABLE))
        self.assertEqual(set(GROWTH_TABLE), set(main.GROWTH_ITEMS))
        for level in GROWTH_TABLE:
            self.assertEqual(
                growth_items_of(level), main.GROWTH_ITEMS.get(level), level
            )

    def test_items_have_no_red_before_red_spawns(self):
        """赤が出始めるレベル 6 より前（レベル 1〜5）の項目は青だけであること（FR3.3）"""
        for level in range(1, FIRST_RED_LEVEL):
            colors = {item.color for item in main.GROWTH_ITEMS.get(level, ())}
            self.assertEqual(set(), colors - {"blue"}, level)
        # 赤が出始める段階は、出現確率で赤が 0 より大きくなる最初のレベル
        first_red = min(
            level
            for level, rates in main.SPAWN_RATES.items()
            if dict(rates).get(RED1, 0) + dict(rates).get(RED2, 0) > 0
        )
        self.assertEqual(FIRST_RED_LEVEL, first_red)

    def test_items_fit_slot_without_duplicates(self):
        """どのレベルも、項目は成長枠のマスの数以下・重複なし・数字は最高の数字未満であること（FR3.2）"""
        for level in range(1, SPAWN_LEVELS + 1):
            self.assertIn(level, main.GROWTH_ITEMS)
            items = main.GROWTH_ITEMS[level]
            self.assertLessEqual(len(items), GROWTH_CELLS, level)
            self.assertEqual(len(items), len(set(items)), level)
            for item in items:
                # 数字 6（MERGE_MAX_NUMBER）はクリア枠のため、最大 5
                self.assertLessEqual(item.number, main.MERGE_MAX_NUMBER - 1, level)

    def test_achieving_only_item_levels_up(self):
        """レベル 1 で 青2 を達成すると記録され、レベルが 1 上がり、項目が 青3（未達成）になること（BR1.2、BR1.3、FR3.1）"""
        core = GameCore()
        self.assertTrue(core.achieve(Item("blue", 2)))
        self.assertEqual(1 + 1, core.spawn_level)
        self.assertEqual(growth_items_of(2), core.growth_items)
        self.assertFalse(core.is_achieved(Item("blue", 3)))

    def test_two_items_level_needs_both_in_either_order(self):
        """レベル 6 は片方だけではレベルが上がらず、どちらを先にしても両方でレベル 7 になること（FR3.1）"""
        level = 6
        first_second = growth_items_of(level)
        for order in (first_second, first_second[::-1]):
            core = GameCore()
            core._spawn_level = level  # pylint: disable=W0212
            self.assertTrue(core.achieve(order[0]))
            self.assertEqual(level, core.spawn_level)
            self.assertTrue(core.is_achieved(order[0]))
            self.assertFalse(core.is_achieved(order[1]))
            self.assertTrue(core.achieve(order[1]))
            self.assertEqual(level + 1, core.spawn_level)
            self.assertEqual(growth_items_of(level + 1), core.growth_items)
            for item in growth_items_of(level + 1):
                self.assertFalse(core.is_achieved(item))

    def test_achieved_or_foreign_item_changes_nothing(self):
        """達成済みの項目と現在のレベルに無い項目は記録されず、状態もレベルも変わらないこと（BR1.2）"""
        level = 6
        core = GameCore()
        core._spawn_level = level  # pylint: disable=W0212
        blue2, red2 = growth_items_of(level)
        core.achieve(blue2)
        self.assertFalse(core.achieve(blue2))  # 達成済み
        self.assertFalse(core.achieve(Item("blue", 3)))  # 他のレベルの項目
        self.assertFalse(core.achieve(Item("red", 1)))  # どのレベルにも無い
        self.assertEqual(level, core.spawn_level)
        self.assertTrue(core.is_achieved(blue2))
        self.assertFalse(core.is_achieved(red2))

    def test_level_stops_at_max(self):
        """最高レベルの 1 つ前（19）の両方で最高レベルになり、そこでは何を渡しても記録されず変わらないこと（FR1.2）"""
        core = GameCore()
        core._spawn_level = main.SPAWN_LEVEL_MAX - 1  # pylint: disable=W0212
        for item in growth_items_of(main.SPAWN_LEVEL_MAX - 1):
            self.assertTrue(core.achieve(item))
        self.assertEqual(main.SPAWN_LEVEL_MAX, core.spawn_level)
        self.assertEqual((), core.growth_items)
        for level in GROWTH_TABLE:
            for item in growth_items_of(level):
                self.assertFalse(core.achieve(item))
        self.assertEqual(main.SPAWN_LEVEL_MAX, core.spawn_level)

    def test_spawn_after_level_up_uses_new_level_rates(self):
        """レベル 3 に上げたあとのスポーンが、レベル 3 の出現確率で決まること（FR2.4）"""
        core = GameCore()
        core._spawn_level = 2  # pylint: disable=W0212
        core.achieve(Item("blue", 3))  # レベル 2 の項目は 青3 だけ
        self.assertEqual(3, core.spawn_level)
        # レベル 3 は 青1 が 70％、青2 が 30％。70 は青2 の範囲の先頭（レベル 2 なら 青1）
        roll = STAGE_RATES[stage_of(3)][0] / 100
        placed = core.spawn(StubRandom(index=0, value=roll))
        self.assertEqual(Item("blue", 2), placed.item)

    def test_reaching_max_level_does_not_clear(self):
        """最高レベルの 1 つ前（19）の項目をすべて達成して最高レベルになっても、クリアにならないこと（FR1.2）"""
        core = GameCore()
        core._spawn_level = main.SPAWN_LEVEL_MAX - 1  # pylint: disable=W0212
        for item in growth_items_of(main.SPAWN_LEVEL_MAX - 1):
            core.achieve(item)
        self.assertEqual(main.SPAWN_LEVEL_MAX, core.spawn_level)
        self.assertFalse(core.cleared)


class TestClearState(TestParent):
    """クリア状態（クリア枠に必要な数を入れた状態）。clear_count から導出する"""

    def test_cleared_follows_clear_count(self):
        """入れた数が必要な数に達するまでクリアでなく、達した瞬間にクリアになること（FR4.3）"""
        core = GameCore()
        for count in range(main.CLEAR_REQUIRED_COUNT + 1):
            self.assertEqual(count, core.clear_count)
            self.assertEqual(count >= main.CLEAR_REQUIRED_COUNT, core.cleared, count)
            fill_clear_slot(core, count + 1)

    def test_spawn_level_is_not_a_clear_condition(self):
        """どのレベルでも、入れた数が 0 のうちはクリアでないこと（BR4.2）"""
        for level in range(1, main.SPAWN_LEVEL_MAX + 1):
            core = GameCore()
            core._spawn_level = level  # pylint: disable=W0212
            self.assertFalse(core.cleared, level)

    def test_cleared_is_read_only(self):
        """cleared は読み取り専用で、代入できないこと（BR1.1）"""
        core = GameCore()
        with self.assertRaises(AttributeError):
            core.cleared = True


class TestRestart(TestParent):
    """GameCore.restart(): 初期状態に戻す（FR4.2、FR4.3、BR3.3、BR3.4）"""

    @staticmethod
    def state_of(core):
        """初期状態の対象: フィールドの全マス・レベル・成長枠・達成済み・選択・離す先・クリア"""
        # pylint: disable=W0212
        return (
            [(c.opened, c.item) for c in core._field.cells],
            core.spawn_level,
            core.growth_items,
            set(core._achieved),
            core.selected,
            core.hovered,
            core.cleared,
            core.clear_count,
            core.clear_next_color,
        )

    @staticmethod
    def dirty_core(clear_count=main.CLEAR_REQUIRED_COUNT):
        """クリア枠に入れた数（既定は必要な数）・最高レベル・達成済み・選択・ホバー・フィールドを、初期状態から変えたゲーム"""
        # pylint: disable=W0212
        core = fill_clear_slot(GameCore(), clear_count)
        core._spawn_level = main.SPAWN_LEVEL_MAX
        core._achieved = {Item("blue", 5)}
        core._selected = (4, 4)
        core._hovered = main.DELETE_SLOT
        core._field.cell(4, 4).item = Item("red", 3)
        core._field.cell(0, 0).item = Item("blue", 2)
        return core

    def test_restart_returns_to_initial_state_when_cleared(self):
        """クリア中の変更済みのゲームで restart() すると、新規の GameCore と同じ状態になること（FR4.2、FR4.3、BR3.3、BR3.4）"""
        core = self.dirty_core()
        self.assertTrue(core.cleared)
        core.restart()
        self.assertEqual(self.state_of(GameCore()), self.state_of(core))
        self.assertFalse(core.cleared)

    def test_restart_keeps_view_and_input(self):
        """やり直しで、描画・入力の部品を作り直さず、同じものを使い続けること（BR3.4）"""
        # pylint: disable=W0212
        core = self.dirty_core()
        view, input_ = core._view, core._input
        core.restart()
        self.assertIs(view, core._view)
        self.assertIs(input_, core._input)

    def test_restart_while_playing_returns_to_initial_state(self):
        """プレイ中（入れた数が必要な数 - 1）の restart() でも、新規の GameCore と同じ状態になること（BR3.3）"""
        core = self.dirty_core(main.CLEAR_REQUIRED_COUNT - 1)
        self.assertFalse(core.cleared)
        core.restart()
        self.assertEqual(self.state_of(GameCore()), self.state_of(core))


class TestClearInput(GrowthSlotInputTestBase):
    """クリア中の入力の無効化と、プレイ中の入力が従来どおり動くこと"""

    # 押す位置: スポーンボタン・フィールドのアイテム・削除枠・成長枠のマス 0
    SPAWN_BUTTON = (SPAWN_BUTTON_X + 1, main.SPAWN_BUTTON_Y + 1)
    DELETE_SLOT_CENTER = (
        main.DELETE_SLOT_X + main.DELETE_SLOT_W // 2,
        main.DELETE_SLOT_Y + main.DELETE_SLOT_H // 2,
    )

    @staticmethod
    def snapshot(core):
        """フィールド・レベル・達成済み・選択・離す先の状態"""
        # pylint: disable=W0212
        return (
            [(c.opened, c.item) for c in core._field.cells],
            core.spawn_level,
            set(core._achieved),
            core.selected,
            core.hovered,
        )

    def cleared_core(self):
        """クリア中で、フィールドのマス (4, 4) に 青5 があるゲーム"""
        core = make_cleared(self.core_at_level(main.SPAWN_LEVEL_START, Item("blue", 5)))
        self.assertTrue(core.cleared)
        return core

    def test_press_anywhere_changes_nothing_when_cleared(self):
        """クリア中は、スポーンボタン・フィールドのアイテム・削除枠・成長枠を押しても何も変わらないこと（FR3.1、BR1.2）"""
        positions = (
            self.SPAWN_BUTTON,
            cell_center(4, 4),
            self.DELETE_SLOT_CENTER,
            self.slot_center(0),
        )
        for position in positions:
            core = self.cleared_core()
            before = self.snapshot(core)
            self.frame(core, tapped=position)
            self.assertEqual(before, self.snapshot(core), position)

    def test_press_move_release_does_nothing_when_cleared(self):
        """クリア中は、押して動かして離しても何も起きず、selected と hovered は None のままであること（FR3.1）"""
        # フィールドの中は、ポップアップ（画面の中心）の外のマスにする。ポップアップの上で離すと、やり直しになる
        outside_popup = cell_center(5, 2)
        self.assertLess(outside_popup[1], main.POPUP_Y)
        for target in (self.DELETE_SLOT_CENTER, self.slot_center(0), outside_popup):
            core = self.cleared_core()
            before = self.snapshot(core)
            self.frame(core, tapped=cell_center(4, 4))
            self.frame(core, held=target)
            self.frame(core, released=target)
            self.assertEqual(before, self.snapshot(core), target)
            self.assertIsNone(core.selected)
            self.assertIsNone(core.hovered)

    def test_clearing_drop_leaves_no_selection_and_ignores_next_press(self):
        """最後の 1 個をクリア枠に入れてクリアした直後は、selected と hovered が None で、次のフレームの押下は無視されること（BR1.3）"""
        # pylint: disable=W0212
        core = fill_clear_slot(GameCore(), main.CLEAR_REQUIRED_COUNT - 1)
        self.assertFalse(core.cleared)
        core._field.cell(4, 4).item = Item(core.clear_next_color, main.MERGE_MAX_NUMBER)
        core._field.cell(5, 5).item = Item("red", 1)
        self.frame(core, tapped=cell_center(4, 4))
        core._on_drop(main.CLEAR_SLOT)  # クリア枠の位置の判定は別の Unit。印を直接渡す
        self.assertTrue(core.cleared)
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)
        self.frame(core, tapped=cell_center(5, 5))
        self.assertIsNone(core.selected)

    def test_inputs_are_read_every_frame_when_cleared(self):
        """クリア中も、3 つの入力を毎フレーム 1 回ずつ読み、次のフレームに持ち越さないこと（BR1.5）"""
        core = self.cleared_core()
        self.frame(core, tapped=cell_center(4, 4), held=(0, 0), released=(1, 1))
        self.assertEqual(([], [], []), self.remaining_inputs())

    def remaining_inputs(self):
        """読まれずに残った 押した・押している間・離した の列"""
        test_input = self.test_input
        return (test_input.positions, test_input.held, test_input.released)

    def test_play_below_max_works_as_before(self):
        """最高レベル未満（レベル 19 以下）では、押す・動かす・離すの操作が従来どおり動くこと（BR1.4）"""
        level = main.SPAWN_LEVEL_MAX - 1
        core = self.core_at_level(level, Item("blue", 5))
        self.frame(core, tapped=cell_center(4, 4))
        self.assertEqual((4, 4), core.selected)
        self.frame(core, held=self.DELETE_SLOT_CENTER)
        self.assertIs(main.DELETE_SLOT, core.hovered)
        self.frame(core, released=self.DELETE_SLOT_CENTER)
        self.assertIsNone(core._field.cell(4, 4).item)  # pylint: disable=W0212
        self.assertIsNone(core.selected)
        before_items = len(placed_cells(core))
        self.frame(core, tapped=self.SPAWN_BUTTON)
        self.assertEqual(before_items + 1, len(placed_cells(core)))


class TestRestartInput(GrowthSlotInputTestBase):
    """クリア中のポップアップのタップ（押した位置と離した位置の両方が中）によるやり直し（FR4.1、BR3.1、BR3.2）"""

    # ポップアップの左上の画素（中）と、右下の外側の画素（外）。半開区間
    INSIDE_TOP_LEFT = (main.POPUP_X, main.POPUP_Y)
    INSIDE_BOTTOM_RIGHT = (
        main.POPUP_X + main.POPUP_W - 1,
        main.POPUP_Y + main.POPUP_H - 1,
    )
    OUTSIDE_RIGHT = (main.POPUP_X + main.POPUP_W, main.POPUP_Y)
    OUTSIDE_BELOW = (main.POPUP_X, main.POPUP_Y + main.POPUP_H)
    OUTSIDE_LEFT = (main.POPUP_X - 1, main.POPUP_Y)
    OUTSIDE_ABOVE = (main.POPUP_X, main.POPUP_Y - 1)
    CENTER = (main.POPUP_X + main.POPUP_W // 2, main.POPUP_Y + main.POPUP_H // 2)
    OUTSIDE = cell_center(0, 0)  # ポップアップの外のフィールドのマス

    def cleared_core(self):
        """クリア中で、フィールドのマス (4, 4) に 青5 があるゲーム"""
        core = make_cleared(self.core_at_level(main.SPAWN_LEVEL_START, Item("blue", 5)))
        self.assertTrue(core.cleared)
        return core

    def test_press_and_release_inside_popup_restarts(self):
        """クリア中、ポップアップの中で押して、中で離すと、やり直すこと（FR4.1、BR3.1、BR3.2）"""
        core = self.cleared_core()
        self.frame(core, tapped=self.CENTER)
        self.assertTrue(core.cleared)  # 押しただけではやり直さない
        self.frame(core, released=self.CENTER)
        self.assertFalse(core.cleared)
        self.assertEqual(main.SPAWN_LEVEL_START, core.spawn_level)

    def test_release_outside_after_press_inside_cancels_and_disarms(self):
        """中で押して外で離すとやり直さず、待機も終わること。その後に中で離しても、やり直さない（BR3.2）"""
        core = self.cleared_core()
        self.frame(core, tapped=self.CENTER)
        self.frame(core, released=self.OUTSIDE)
        self.assertTrue(core.cleared)
        self.frame(core, released=self.CENTER)  # 押しなしの離すだけ
        self.assertTrue(core.cleared)

    def test_press_outside_release_inside_does_not_restart(self):
        """外で押して、中で離しても、やり直さないこと（BR3.2）"""
        core = self.cleared_core()
        self.frame(core, tapped=self.OUTSIDE)
        self.frame(core, released=self.CENTER)
        self.assertTrue(core.cleared)

    def test_press_outside_popup_changes_nothing(self):
        """クリア中、ポップアップの外（フィールド・スポーンボタン・削除枠・成長枠）の押す・離すで、やり直さず何も起きないこと（FR3.1、BR3.1）"""
        # pylint: disable=W0212
        positions = (
            self.OUTSIDE,
            TestClearInput.SPAWN_BUTTON,
            TestClearInput.DELETE_SLOT_CENTER,
            self.slot_center(0),
        )
        for position in positions:
            core = self.cleared_core()
            self.frame(core, tapped=position)
            self.frame(core, released=position)
            self.assertTrue(core.cleared, position)
            self.assertEqual(Item("blue", 5), core._field.cell(4, 4).item, position)

    def test_popup_edge_is_half_open(self):
        """ポップアップの左上の画素と右下の画素は中、右・下・左・上の外側の画素は外であること（半開区間。BR3.1、BR3.2）"""
        inside = (self.INSIDE_TOP_LEFT, self.INSIDE_BOTTOM_RIGHT)
        outside = (
            self.OUTSIDE_RIGHT,
            self.OUTSIDE_BELOW,
            self.OUTSIDE_LEFT,
            self.OUTSIDE_ABOVE,
        )
        for position in inside:
            core = self.cleared_core()
            self.frame(core, tapped=position)
            self.frame(core, released=position)
            self.assertFalse(core.cleared, position)
        for position in outside:
            core = self.cleared_core()
            self.frame(core, tapped=position)
            self.frame(core, released=position)
            self.assertTrue(core.cleared, position)

    def test_press_and_release_in_same_frame_restarts(self):
        """同じフレームに押す・離すが届いたとき、どちらも中ならやり直すこと。押す→離すの順に処理する（BR3.2）"""
        core = self.cleared_core()
        self.frame(core, tapped=self.CENTER, released=self.CENTER)
        self.assertFalse(core.cleared)

    def test_popup_position_while_playing_does_not_restart(self):
        """プレイ中（レベル 19 以下）は、ポップアップの位置を押して離しても、やり直さないこと（BR3.5）"""
        # pylint: disable=W0212
        level = main.SPAWN_LEVEL_MAX - 1
        core = self.core_at_level(level, Item("blue", 5))
        self.frame(core, tapped=self.CENTER)
        self.frame(core, released=self.CENTER)
        self.assertEqual(level, core.spawn_level)
        self.assertEqual(Item("blue", 5), core._field.cell(4, 4).item)

    def test_normal_operations_work_after_restart(self):
        """やり直した直後、通常の操作（スポーン）が従来どおり動くこと（BR3.3）"""
        core = self.cleared_core()
        self.frame(core, tapped=self.CENTER)
        self.frame(core, released=self.CENTER)
        before_items = len(placed_cells(core))
        self.frame(core, tapped=TestClearInput.SPAWN_BUTTON)
        self.assertEqual(before_items + 1, len(placed_cells(core)))


def rect_of(x, y, w, h):
    """領域の左上と大きさ。半開区間 [x, x + w) × [y, y + h) を表す"""
    return (x, y, w, h)


def overlaps(a, b):
    """2 つの領域（rect_of）が重なるか。半開区間なので、接するだけなら重ならない"""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


class TestClearSlotLayout(unittest.TestCase):
    """クリア枠・メーターのレイアウトと、位置の判定（FR3.3、FR5.1、FR5.2）"""

    def test_clear_slot_and_meter_rects(self):
        """クリア枠は左上の 1 マス、メーターはその右からフィールドの右端まで、高さは同じ。フィールドはその下に始まり、マスの大きさは変わらないこと（FR5.1）"""
        self.assertEqual(
            (ORIGIN_X, ORIGIN_Y), (main.FIELD_ORIGIN_X, main.FIELD_ORIGIN_Y)
        )
        self.assertEqual((PITCH, CELL), (CELL_PITCH, CELL_SIZE))
        self.assertEqual(
            rect_of(CLEAR_X, CLEAR_Y, CELL, CELL),
            rect_of(
                main.CLEAR_SLOT_X,
                main.CLEAR_SLOT_Y,
                main.CLEAR_SLOT_W,
                main.CLEAR_SLOT_H,
            ),
        )
        self.assertEqual(
            rect_of(METER_X, METER_Y, METER_W, METER_H),
            rect_of(main.METER_X, main.METER_Y, main.METER_W, main.METER_H),
        )
        # メーターの右端はフィールドの右端にそろう
        self.assertEqual(FIELD_RIGHT, main.METER_X + main.METER_W)

    def test_spawn_button_and_slots_follow_field(self):
        """スポーンボタンの上端はフィールドの下端 + 隙間で、削除枠・成長枠はボタンの縦の中央にそろうこと（FR5.1）"""
        self.assertEqual(FIELD_BOTTOM + SPAWN_GAP, SPAWN_BUTTON_Y)
        center_y = SPAWN_BUTTON_Y + (SPAWN_BUTTON_H - CELL) // 2
        self.assertEqual(center_y, DELETE_SLOT_Y)
        growth_y = SPAWN_BUTTON_Y + (SPAWN_BUTTON_H - main.GROWTH_SLOT_H) // 2
        self.assertEqual(growth_y, main.GROWTH_SLOT_Y)

    def test_no_overlap_and_fits_screen(self):
        """クリア枠・メーター・フィールド・スポーンボタン・削除枠・成長枠が重ならず、画面に収まること（FR5.1、FR5.2）"""
        field = rect_of(
            main.FIELD_ORIGIN_X,
            main.FIELD_ORIGIN_Y,
            CELL_PITCH * (FIELD_SIZE - 1) + CELL_SIZE,
            CELL_PITCH * (FIELD_SIZE - 1) + CELL_SIZE,
        )
        rects = {
            "clear": rect_of(
                main.CLEAR_SLOT_X,
                main.CLEAR_SLOT_Y,
                main.CLEAR_SLOT_W,
                main.CLEAR_SLOT_H,
            ),
            "meter": rect_of(main.METER_X, main.METER_Y, main.METER_W, main.METER_H),
            "field": field,
            "spawn": rect_of(
                SPAWN_BUTTON_X, SPAWN_BUTTON_Y, SPAWN_BUTTON_W, SPAWN_BUTTON_H
            ),
            "delete": rect_of(
                DELETE_SLOT_X, DELETE_SLOT_Y, DELETE_SLOT_W, DELETE_SLOT_H
            ),
            "growth": rect_of(
                main.GROWTH_SLOT_X,
                main.GROWTH_SLOT_Y,
                main.GROWTH_SLOT_W,
                main.GROWTH_SLOT_H,
            ),
        }
        names = list(rects)
        for i, first in enumerate(names):
            x, y, w, h = rects[first]
            self.assertGreaterEqual(x, 0, first)
            self.assertGreaterEqual(y, 0, first)
            self.assertLessEqual(x + w, SCREEN_WIDTH, first)
            self.assertLessEqual(y + h, SCREEN_HEIGHT, first)
            for second in names[i + 1 :]:
                # 隣のマスと重なる枠線 1 ピクセルは、枠線どうしの重なりとして許す（同じ要素の内部のみ）
                self.assertFalse(overlaps(rects[first], rects[second]), (first, second))

    def test_clear_slot_region_is_half_open(self):
        """クリア枠の領域は左上を含み、右・下の外側を含まない。中は CLEAR_SLOT を返すこと（FR3.3）"""
        left, top = main.CLEAR_SLOT_X, main.CLEAR_SLOT_Y
        right, bottom = left + main.CLEAR_SLOT_W, top + main.CLEAR_SLOT_H
        self.assertIs(main.CLEAR_SLOT, main.target_at(left, top))
        self.assertIs(main.CLEAR_SLOT, main.target_at(right - 1, bottom - 1))
        for x, y in ((right, top), (left, bottom), (left - 1, top), (left, top - 1)):
            self.assertIsNot(main.CLEAR_SLOT, main.target_at(x, y), (x, y))

    def test_meter_is_not_a_drop_target(self):
        """メーターの上は離す先ではない（None。フィールドの外としてキャンセルになる）こと（FR3.3）"""
        x = main.METER_X + main.METER_W // 2
        y = main.METER_Y + main.METER_H // 2
        self.assertIsNone(main.target_at(x, y))

    def test_other_targets_are_unchanged(self):
        """マス・削除枠の離す先は新しい位置でも変わらないこと（FR3.3）"""
        self.assertEqual((3, 6), main.target_at(*cell_center(3, 6)))
        delete_center = (DELETE_SLOT_X + CELL // 2, DELETE_SLOT_Y + CELL // 2)
        self.assertIs(main.DELETE_SLOT, main.target_at(*delete_center))


class TestClearSlotView(TestParent):
    """クリア枠とメーターの描画（FR3.1、FR4.1、FR5.3）"""

    def test_clear_slot_shows_next_color_six(self):
        """クリア枠に、次に入れる色の数字 6 が表示され、入れるたびに赤と青が入れ替わること（FR3.1、FR5.3）"""
        core = GameCore()
        self.assertEqual("red", core.clear_next_color)
        calls = self.draw_core(core)
        for expected in clear_slot_calls("red"):
            self.assertIn(expected, calls)
        core = fill_clear_slot(GameCore(), 1)
        self.assertEqual("blue", core.clear_next_color)
        calls = self.draw_core(core)
        for expected in clear_slot_calls("blue"):
            self.assertIn(expected, calls)

    def test_meter_is_empty_at_zero(self):
        """入れた数 0 では、メーターは背景と枠線だけで、塗りは描かれないこと（FR4.1）"""
        calls = self.draw_core(GameCore())
        self.assertEqual(0, meter_fill_width(0))
        for expected in meter_calls(0):
            self.assertIn(expected, calls)
        fills = [c for c in calls if c[-1] == main.COLOR_METER_FILL]
        self.assertEqual([], fills)

    def test_meter_fill_width_is_proportional(self):
        """塗りの幅が、内側の幅 × 入れた数 ÷ 必要な数（切り捨て）であること（FR4.1）"""
        for count in (1, main.CLEAR_REQUIRED_COUNT // 2, main.CLEAR_REQUIRED_COUNT - 1):
            core = fill_clear_slot(GameCore(), count)
            calls = self.draw_core(core)
            fills = [c for c in calls if c[-1] == main.COLOR_METER_FILL]
            self.assertEqual(1, len(fills), count)
            self.assertEqual(meter_calls(count)[-1], fills[0], count)
            self.assertEqual(meter_fill_width(count), fills[0][3], count)

    def test_meter_is_full_at_required_count(self):
        """必要な数に達すると、塗りが内側の全幅になること（FR4.1）"""
        core = make_cleared(GameCore())
        fills = [c for c in self.draw_core(core) if c[-1] == main.COLOR_METER_FILL]
        self.assertEqual(1, len(fills))
        self.assertEqual(METER_W - 2 * METER_BORDER, fills[0][3])

    def test_meter_has_no_number_text(self):
        """メーターに数字（12/40 など）は表示しないこと。文字は 6 だけが増える（FR4.1）"""
        calls = self.draw_core(fill_clear_slot(GameCore(), 12))
        texts = [c[3] for c in calls if c[0] == "draw_text"]
        self.assertFalse([t for t in texts if "/" in t])
        # クリア枠の 6 以外に、メーターの範囲へ描かれた文字は無い
        in_meter = [
            c
            for c in calls
            if c[0] == "draw_text"
            and METER_X <= c[1] < METER_X + METER_W
            and METER_Y <= c[2] < METER_Y + METER_H
        ]
        self.assertEqual([], in_meter)

    def test_colors_are_distinguishable(self):
        """メーターの塗りの色は、背景・選択枠の緑と赤のどれとも違うこと（FR4.1）"""
        fill = main.COLOR_METER_FILL
        self.assertNotIn(fill, (main.COLOR_METER_BG, COLOR_FRAME_OK, COLOR_FRAME_NG))

    def test_draw_order(self):
        """マス → 削除枠 → 成長枠 → クリア枠 → メーター → スポーンボタンの順に描かれること（FR5.3）"""
        calls = self.draw_core(fill_clear_slot(GameCore(), 5))
        order = [
            calls.index(delete_slot_background()),
            calls.index(clear_slot_calls("blue")[0]),
            calls.index(meter_calls(5)[0]),
            calls.index(button_background()),
        ]
        self.assertEqual(sorted(order), order)
        self.assertEqual(field_calls_end(calls), order[0])  # 削除枠はマスの直後
        # 成長枠の 1 マス目の背景は、削除枠とクリア枠の間
        growth = calls.index(
            (
                "draw_rect",
                main.GROWTH_SLOT_X,
                main.GROWTH_SLOT_Y,
                CELL,
                CELL,
                COLOR_OPENED_BG,
            )
        )
        self.assertLess(order[0], growth)
        self.assertLess(growth, order[1])

    def test_clear_slot_is_drawn_while_cleared_under_popup(self):
        """クリア中も、クリア枠とメーターは満タンのまま描かれ、ポップアップが最後に重なること（FR4.1）"""
        calls = self.draw_core(make_cleared(GameCore()))
        for expected in meter_calls(main.CLEAR_REQUIRED_COUNT):
            self.assertIn(expected, calls)
        popup_start = calls.index(
            (
                "draw_rect",
                main.POPUP_X,
                main.POPUP_Y,
                main.POPUP_W,
                main.POPUP_H,
                main.COLOR_POPUP_BG,
            )
        )
        self.assertLess(calls.index(meter_calls(0)[0]), popup_start)


class TestClearSlotSelectionFrame(GrowthSlotInputTestBase):
    """クリア枠の上の選択枠の位置と色、離したときの実行とキャンセル（FR3.3、FR5.3）"""

    CLEAR_CENTER = (CLEAR_X + CELL // 2, CLEAR_Y + CELL // 2)

    @staticmethod
    def clear_frame(color):
        """クリア枠の位置（クリア枠の矩形）に置く二重の選択枠"""
        return [
            ("draw_rect_border", CLEAR_X, CLEAR_Y, CELL, CELL, color),
            ("draw_rect_border", CLEAR_X + 1, CLEAR_Y + 1, CELL - 2, CELL - 2, color),
        ]

    def hover_clear_slot(self, item):
        """マス (4, 4) の item を押して、クリア枠へ動かした状態のゲーム"""
        core = self.core_at_level(main.SPAWN_LEVEL_START, item)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.CLEAR_CENTER)
        return core

    def test_hover_resolves_to_clear_slot(self):
        """クリア枠の上に動かすと、離す先が CLEAR_SLOT になること（FR3.3）"""
        core = self.hover_clear_slot(Item("red", main.MERGE_MAX_NUMBER))
        self.assertIs(main.CLEAR_SLOT, core.hovered)

    def test_frame_is_green_for_next_color_six(self):
        """数字 6 で次に入れる色（初期は赤）なら、クリア枠の位置に緑の枠が描かれること（FR5.3）"""
        core = self.hover_clear_slot(Item("red", main.MERGE_MAX_NUMBER))
        calls = self.draw_core(core)
        self.assertEqual(
            self.clear_frame(COLOR_FRAME_OK),
            [c for c in calls if c[-1] == COLOR_FRAME_OK],
        )

    def test_frame_is_red_for_wrong_color_or_number(self):
        """違う色の 6・6 以外の数字なら、クリア枠の位置に赤の枠が描かれること（FR5.3）"""
        for item in (Item("blue", main.MERGE_MAX_NUMBER), Item("red", 5)):
            core = self.hover_clear_slot(item)
            calls = self.draw_core(core)
            self.assertEqual(
                self.clear_frame(COLOR_FRAME_NG),
                [c for c in calls if c[-1] == COLOR_FRAME_NG],
                item,
            )

    def test_frame_follows_next_color_after_drop(self):
        """1 つ入れた後は次に入れる色が青になり、赤の 6 では赤の枠、青の 6 では緑の枠になること（FR5.3）"""
        core = fill_clear_slot(
            self.core_at_level(
                main.SPAWN_LEVEL_START, Item("blue", main.MERGE_MAX_NUMBER)
            ),
            1,
        )
        self.assertEqual("blue", core.clear_next_color)
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=self.CLEAR_CENTER)
        calls = self.draw_core(core)
        self.assertEqual(
            self.clear_frame(COLOR_FRAME_OK),
            [c for c in calls if c[-1] == COLOR_FRAME_OK],
        )

    def test_frame_is_drawn_over_clear_slot_and_meter_before_button(self):
        """選択枠は、クリア枠とメーターの後（上に重なる）、スポーンボタンの前に描かれること（FR5.3）"""
        core = self.hover_clear_slot(Item("red", main.MERGE_MAX_NUMBER))
        calls = self.draw_core(core)
        frame_at = calls.index(self.clear_frame(COLOR_FRAME_OK)[0])
        self.assertGreater(frame_at, calls.index(meter_calls(0)[1]))
        self.assertLess(frame_at, calls.index(button_background()))

    def test_release_on_green_puts_item_into_clear_slot(self):
        """緑で離すと投入が実行され、入れた数が 1 増え、選択枠が消えること（FR3.3）"""
        core = self.hover_clear_slot(Item("red", main.MERGE_MAX_NUMBER))
        self.frame(core, released=self.CLEAR_CENTER)
        self.assertEqual(1, core.clear_count)
        self.assertEqual("blue", core.clear_next_color)
        self.assertIsNone(core._field.cell(4, 4).item)  # pylint: disable=W0212
        self.assertIsNone(core.selected)
        self.assertEqual(
            [],
            [
                c
                for c in self.draw_core(core)
                if c[-1] in (COLOR_FRAME_OK, COLOR_FRAME_NG)
            ],
        )

    def test_release_on_red_cancels(self):
        """赤で離すとキャンセルになり、入れた数もアイテムも変わらず、選択枠が消えること（FR3.3）"""
        item = Item("blue", main.MERGE_MAX_NUMBER)
        core = self.hover_clear_slot(item)
        self.frame(core, released=self.CLEAR_CENTER)
        self.assertEqual(0, core.clear_count)
        self.assertEqual(item, core._field.cell(4, 4).item)  # pylint: disable=W0212
        self.assertIsNone(core.selected)

    def test_release_on_meter_cancels(self):
        """メーターの上で離すと、フィールドの外としてキャンセルになること（FR3.3）"""
        item = Item("red", main.MERGE_MAX_NUMBER)
        core = self.core_at_level(main.SPAWN_LEVEL_START, item)
        meter_center = (
            main.METER_X + main.METER_W // 2,
            main.METER_Y + main.METER_H // 2,
        )
        self.frame(core, tapped=cell_center(4, 4))
        self.frame(core, held=meter_center)
        self.frame(core, released=meter_center)
        self.assertEqual(0, core.clear_count)
        self.assertEqual(item, core._field.cell(4, 4).item)  # pylint: disable=W0212


class TestSpawnLevelAtMax(TestParent):
    """最高レベルでも Lv の表示のままプレイが続くこと（FR5.3）"""

    def test_lv_text_stays_at_max_and_game_continues(self):
        """最高レベル 20 でも、スポーンボタンは Lv20 を表示し、クリアにならないこと（FR1.2）"""
        core = GameCore()
        core._spawn_level = main.SPAWN_LEVEL_MAX  # pylint: disable=W0212
        calls = self.draw_core(core)
        self.assertIn(spawn_level_text(main.SPAWN_LEVEL_MAX), calls)
        self.assertFalse(core.cleared)


PopupCalls = namedtuple("PopupCalls", ["background", "border", "title", "guide"])


class TestClearPopupView(TestParent):
    """クリア中だけ、画面の中心に重ねて描くポップアップ（FR2.1〜FR2.3）"""

    TITLE = "CLEAR!"
    GUIDE = "TAP TO RESTART"
    POPUP_CALLS = 4  # 背景 + 枠線 + 2 行の文字

    def cleared_core(self):
        """クリア枠に必要な数を入れた（クリア中の）ゲーム"""
        core = make_cleared(GameCore())
        self.assertTrue(core.cleared)
        return core

    def popup_calls(self):
        """クリア中の描画の、最後に描かれるポップアップの呼び出し"""
        calls = self.draw_core(self.cleared_core())[-self.POPUP_CALLS :]
        return PopupCalls(*calls)

    def test_rect_is_centered_on_screen(self):
        """ポップアップの矩形が、画面の中心 (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2) を中心にした定数であること（FR2.1）"""
        # 幅 = 最長の行 TAP TO RESTART の幅 + 左右の余白 8 ずつ
        self.assertEqual(text_width(self.GUIDE) + 2 * 8, main.POPUP_W)
        # 高さ = 2 行（高さ 5 ずつ）+ 行間 7 + 上下の余白 7 ずつ + 枠線
        self.assertEqual(5 * 2 + 7 + 7 * 2, main.POPUP_H)
        self.assertEqual(SCREEN_WIDTH // 2 - main.POPUP_W // 2, main.POPUP_X)
        self.assertEqual(SCREEN_HEIGHT // 2 - main.POPUP_H // 2, main.POPUP_Y)

    def test_drawn_last_in_order_when_cleared(self):
        """クリア中は、最後に 背景 → 枠線 → CLEAR! → TAP TO RESTART の順で描かれること（FR2.1）"""
        bg, border, title, guide = self.popup_calls()
        rect = (main.POPUP_X, main.POPUP_Y, main.POPUP_W, main.POPUP_H)
        self.assertEqual(("draw_rect", *rect), bg[:5])
        self.assertEqual(("draw_rect_border", *rect), border[:5])
        self.assertEqual((self.TITLE, self.GUIDE), (title[3], guide[3]))
        self.assertEqual(("draw_text", "draw_text"), (title[0], guide[0]))

    def test_texts_are_centered_inside_rect(self):
        """2 行とも ASCII で、水平方向に中央に寄り、矩形の内側に収まること（FR2.2）"""
        _, _, title, guide = self.popup_calls()
        for call in (title, guide):
            _, x, y, text, _ = call
            self.assertTrue(text.isascii(), text)
            self.assertEqual(main.POPUP_X + (main.POPUP_W - text_width(text)) // 2, x)
            self.assertGreaterEqual(x, main.POPUP_X)
            self.assertLessEqual(x + text_width(text), main.POPUP_X + main.POPUP_W)
            self.assertGreaterEqual(y, main.POPUP_Y)
            self.assertLessEqual(y + 5, main.POPUP_Y + main.POPUP_H)  # 文字の高さ 5
        self.assertLess(title[2], guide[2])  # CLEAR! が上、TAP TO RESTART が下

    def test_colors_are_distinct(self):
        """背景・枠線・文字の色が互いに別であること（FR2.1）"""
        bg, border, title, guide = self.popup_calls()
        self.assertEqual(title[4], guide[4])  # 2 行の文字は同じ色
        colors = [bg[5], border[5], title[4]]
        self.assertEqual(3, len(set(colors)), colors)

    def test_no_popup_while_playing(self):
        """プレイ中（レベル 1〜最高レベル。最高レベルでもクリアでない）は、ポップアップの描画が 1 つも呼ばれないこと（FR2.3）"""
        for level in range(1, main.SPAWN_LEVEL_MAX + 1):
            core = GameCore()
            core._spawn_level = level  # pylint: disable=W0212
            calls = self.draw_core(core)
            self.assertNotIn(self.TITLE, [c[3] for c in calls if c[0] == "draw_text"])
            self.assertNotIn(self.GUIDE, [c[3] for c in calls if c[0] == "draw_text"])
            self.assertFalse(
                [
                    c
                    for c in calls
                    if c[1:5]
                    == (main.POPUP_X, main.POPUP_Y, main.POPUP_W, main.POPUP_H)
                ],
                level,
            )

    def test_popup_is_drawn_after_spawn_button_when_cleared(self):
        """クリア中も従来の描画は残り、スポーンボタンの直後（ポップアップの直前）まで描かれること（FR2.1）"""
        calls = self.draw_core(self.cleared_core())
        button = 4  # スポーンボタンの描画: 背景 + 枠線 + SPAWN + Lv
        spawn_button = calls[-self.POPUP_CALLS - button : -self.POPUP_CALLS]
        self.assertEqual(
            (SPAWN_BUTTON_X, SPAWN_BUTTON_Y, SPAWN_BUTTON_W, SPAWN_BUTTON_H),
            spawn_button[0][1:5],
        )
        self.assertEqual("SPAWN", spawn_button[2][3])


class TestGameCoreSnapshot(TestParent):
    """GameCore.snapshot()/restore(): 状態の保存と復元（FR1.1〜FR1.5、FR3.1、FR3.2、BR2.1〜BR2.6）"""

    def test_initial_snapshot_represents_new_game(self):
        """初期状態の snapshot が、初期のフィールド・最初のレベル・達成なし・クリア枠 0・最初の色であること（BR2.1、BR2.6）"""
        initial = create_initial_field()
        expected = {
            "field": [
                {
                    "opened": c.opened,
                    "item": None if c.item is None else [c.item.color, c.item.number],
                }
                for c in initial.cells
            ],
            "spawn_level": main.SPAWN_LEVEL_START,
            "achieved": [],
            "clear_count": 0,
            "clear_next_color": main.CLEAR_COLOR_START,
        }
        self.assertEqual(expected, GameCore().snapshot())

    @staticmethod
    def played_core():
        """フィールド・レベル・達成済み・クリア枠の数と色を、初期状態から変えたゲーム（プレイ中）"""
        # pylint: disable=W0212
        core = fill_clear_slot(GameCore(), main.CLEAR_REQUIRED_COUNT - 3)
        core._field.cell(4, 4).item = Item("red", 3)
        core._field.cell(0, 0).opened = True
        core._field.cell(0, 0).item = Item("blue", 2)
        core._spawn_level = 6
        core._achieved = {main.GROWTH_ITEMS[6][1]}  # 赤2（レベル 6 は 青2・赤2）
        return core

    @staticmethod
    def state_of(core):
        """復元の対象の状態（保存しない状態も含む）"""
        # pylint: disable=W0212
        return (
            [(c.opened, c.item) for c in core._field.cells],
            core.spawn_level,
            set(core._achieved),
            core.clear_count,
            core.clear_next_color,
            core.selected,
            core.hovered,
            core._restart_armed,
        )

    def test_snapshot_reflects_changed_state(self):
        """変更後の snapshot が、レベル・達成済み・クリア枠の数と色・マスの内容を表すこと（BR2.1）"""
        core = self.played_core()
        data = core.snapshot()
        self.assertEqual(6, data["spawn_level"])
        self.assertEqual([list(main.GROWTH_ITEMS[6][1])], data["achieved"])
        self.assertEqual(main.CLEAR_REQUIRED_COUNT - 3, data["clear_count"])
        self.assertEqual(core.clear_next_color, data["clear_next_color"])
        self.assertEqual(
            {"opened": True, "item": ["red", 3]}, data["field"][4 * 10 + 4]
        )
        self.assertEqual({"opened": True, "item": ["blue", 2]}, data["field"][0])
        self.assertEqual(FIELD_SIZE * FIELD_SIZE, len(data["field"]))

    def test_snapshot_is_json_serializable(self):
        """snapshot が JSON で表せる値だけで、往復しても同じであること（BR2.1）"""
        data = self.played_core().snapshot()
        self.assertEqual(data, json.loads(json.dumps(data)))

    def test_snapshot_excludes_transient_state(self):
        """snapshot が、選択中・ポインタ・ポップアップ待機・クリア状態のキーを含まないこと（BR2.2）"""
        data = self.played_core().snapshot()
        self.assertEqual(
            {"field", "spawn_level", "achieved", "clear_count", "clear_next_color"},
            set(data),
        )

    def test_restore_round_trip_returns_same_state(self):
        """snapshot を別の新しい GameCore に restore すると、同じ状態になり真を返すこと（BR2.3）"""
        source = self.played_core()
        target = GameCore()
        self.assertTrue(target.restore(source.snapshot()))
        expected = self.state_of(source)
        # 保存しない状態は初期値になる（選択中・ポインタ・ポップアップ待機）
        expected = expected[:5] + (None, None, False)
        self.assertEqual(expected, self.state_of(target))
        self.assertEqual(source.snapshot(), target.snapshot())

    def test_restore_resets_transient_state(self):
        """restore が、選択中・ポインタ・ポップアップ待機を初期値に戻すこと（BR2.2、BR2.3）"""
        # pylint: disable=W0212
        core = self.played_core()
        data = core.snapshot()
        core._selected = (4, 4)
        core._hovered = main.DELETE_SLOT
        core._restart_armed = True
        self.assertTrue(core.restore(data))
        self.assertIsNone(core.selected)
        self.assertIsNone(core.hovered)
        self.assertFalse(core._restart_armed)

    def test_restore_gives_independent_state(self):
        """restore 後の状態を変えても、渡した辞書が変わらないこと（BR2.3）"""
        data = self.played_core().snapshot()
        before = copy.deepcopy(data)
        core = GameCore()
        core.restore(data)
        core.achieve(main.GROWTH_ITEMS[6][0])
        # pylint: disable=W0212
        core._field.cell(0, 0).item = None
        self.assertEqual(before, data)

    def test_restore_max_level_with_no_achieved(self):
        """最高レベル（成長枠の項目なし）の往復ができること（BR2.5）"""
        # pylint: disable=W0212
        source = GameCore()
        source._spawn_level = main.SPAWN_LEVEL_MAX
        target = GameCore()
        self.assertTrue(target.restore(source.snapshot()))
        self.assertEqual(main.SPAWN_LEVEL_MAX, target.spawn_level)

    @staticmethod
    def old_save(level, achieved):
        """表を変える前の保存データ（形式は同じ。レベルと達成済みの項目だけを持つ）"""
        data = GameCore().snapshot()
        data["spawn_level"] = level
        data["achieved"] = [list(item) for item in achieved]
        return data

    def test_old_save_matching_new_items_resumes_at_same_level(self):
        """古い保存データの達成済みが新しい項目に含まれるとき、同じレベル番号で再開すること（FR5.1）"""
        cases = (
            (3, [Item("blue", 2)]),  # 今のレベル 3（青2・赤2）で 青2 を達成済み
            (8, []),  # 今の最高レベル 8（項目なし）
            (SPAWN_LEVELS, []),  # 新しい最高レベル 20
        )
        for level, achieved in cases:
            with self.subTest(level=level):
                core = GameCore()
                self.assertTrue(core.restore(self.old_save(level, achieved)))
                self.assertEqual(level, core.spawn_level)
                for item in achieved:
                    self.assertTrue(core.is_achieved(item))

    def test_old_save_not_matching_new_items_starts_new_game(self):
        """古い保存データの達成済みが新しい項目に含まれないとき、新しいゲームとして始めること（FR5.1）"""
        # 今のレベル 3（青2・赤2）で 赤2 を達成済み。新しいレベル 3 は 青2・青3 で 赤2 が無い
        data = self.old_save(3, [Item("red", 2)])
        core = self.played_core()
        self.assertFalse(core.restore(data))
        self.assertEqual(self.state_of(GameCore()), self.state_of(core))

    def invalid_variants(self):
        """正しい辞書から 1 か所だけ壊した（説明, 辞書）の一覧"""
        base = GameCore().snapshot()
        level6 = self.played_core().snapshot()

        def changed(source, **kwargs):
            data = copy.deepcopy(source)
            data.update(kwargs)
            return data

        def with_cell(cell):
            data = copy.deepcopy(base)
            data["field"][0] = cell
            return data

        variants = [
            ("not a dict", [1, 2]),
            ("none", None),
            ("empty dict", {}),
            ("short field", changed(base, field=base["field"][:-1])),
            ("long field", changed(base, field=base["field"] + base["field"][:1])),
            ("field not list", changed(base, field="x")),
            ("cell not dict", with_cell(5)),
            ("cell missing item", with_cell({"opened": True})),
            ("opened not bool", with_cell({"opened": 1, "item": None})),
            ("item bad color", with_cell({"opened": True, "item": ["green", 1]})),
            ("item number zero", with_cell({"opened": True, "item": ["red", 0]})),
            (
                "item number over max",
                with_cell({"opened": True, "item": ["red", main.MERGE_MAX_NUMBER + 1]}),
            ),
            ("item number bool", with_cell({"opened": True, "item": ["red", True]})),
            ("item number float", with_cell({"opened": True, "item": ["red", 1.0]})),
            ("item wrong length", with_cell({"opened": True, "item": ["red"]})),
            ("item not list", with_cell({"opened": True, "item": "red1"})),
            (
                "level below range",
                changed(base, spawn_level=main.SPAWN_LEVEL_START - 1),
            ),
            ("level above range", changed(base, spawn_level=main.SPAWN_LEVEL_MAX + 1)),
            ("level bool", changed(base, spawn_level=True)),
            ("level string", changed(base, spawn_level="1")),
            ("achieved not in level", changed(base, achieved=[["red", 5]])),
            ("achieved duplicate", changed(level6, achieved=[["red", 2], ["red", 2]])),
            ("achieved not list", changed(base, achieved="x")),
            ("achieved bad item", changed(base, achieved=[["blue"]])),
            ("clear_count negative", changed(base, clear_count=-1)),
            (
                "clear_count cleared",
                changed(base, clear_count=main.CLEAR_REQUIRED_COUNT),
            ),
            ("clear_count bool", changed(base, clear_count=False)),
            ("clear_count float", changed(base, clear_count=1.5)),
            ("clear_next_color bad", changed(base, clear_next_color="green")),
            ("clear_next_color int", changed(base, clear_next_color=1)),
        ]
        for key in base:
            data = copy.deepcopy(base)
            del data[key]
            variants.append((f"missing {key}", data))
        return variants

    def test_restore_invalid_returns_false_and_initial_state(self):
        """正しくない辞書は、偽を返し、状態を初期状態にして、例外を出さないこと（BR2.4、BR2.5）"""
        initial = self.state_of(GameCore())
        for name, data in self.invalid_variants():
            with self.subTest(name):
                core = self.played_core()
                self.assertFalse(core.restore(data))
                self.assertEqual(initial, self.state_of(core))

    def test_restore_invalid_is_validated_before_mutation(self):
        """後ろの項目だけが壊れた辞書でも、前の項目が一部だけ反映されないこと（BR2.4）"""
        data = self.played_core().snapshot()
        data["clear_next_color"] = "green"
        core = GameCore()
        self.assertFalse(core.restore(data))
        self.assertEqual(main.SPAWN_LEVEL_START, core.spawn_level)
        self.assertEqual(self.state_of(GameCore()), self.state_of(core))


def mock_store(loaded=None, saved=True):
    """load が loaded を、save が saved を返す保存の仕組みの代役"""
    store = MagicMock()
    store.load.return_value = loaded
    store.save.return_value = saved
    return store


class TestGameCoreSaveTiming(GrowthSlotInputTestBase):
    """GameCore の保存のタイミング（FR2.1〜FR2.4、FR3.1、FR3.2、FR6.2、BR3.1〜BR3.11）"""

    def core_with(self, store):
        """store を渡した GameCore（起動時の load の呼び出しは記録から外す）"""
        core = GameCore(store=store)
        store.save.reset_mock()
        return core

    def test_start_restores_loaded_snapshot(self):
        """load が辞書を返すと、restore された状態で始まり、起動では save を呼ばないこと（BR3.1、BR3.10）"""
        data = TestGameCoreSnapshot.played_core().snapshot()
        store = mock_store(loaded=data)
        core = GameCore(store=store)
        self.assertEqual(data, core.snapshot())
        store.load.assert_called_once_with()
        store.save.assert_not_called()

    def test_start_without_data_is_new_game(self):
        """load が None だと、新しいゲームの初期状態で始まり、save を呼ばないこと（BR3.2）"""
        store = mock_store(loaded=None)
        core = GameCore(store=store)
        self.assertEqual(GameCore(store=mock_store()).snapshot(), core.snapshot())
        store.save.assert_not_called()

    def test_start_with_empty_or_invalid_data_is_new_game(self):
        """load が {}（ゲーム無し）や形式の合わない辞書だと、初期状態で始まり、save を呼ばないこと（BR3.2）"""
        initial = GameCore(store=mock_store()).snapshot()
        broken = dict(initial, spawn_level="x")
        for loaded in ({}, broken):
            with self.subTest(loaded=loaded):
                store = mock_store(loaded=loaded)
                core = GameCore(store=store)
                self.assertEqual(initial, core.snapshot())
                store.save.assert_not_called()

    def test_spawn_saves_snapshot_when_placed(self):
        """スポーンで置けたとき、置いたあとの snapshot で save が 1 回呼ばれること（BR3.3）"""
        store = mock_store()
        core = self.core_with(store)
        self.assertIsNotNone(core.spawn())
        store.save.assert_called_once_with(core.snapshot())

    def test_spawn_without_room_does_not_save(self):
        """空きマスがなくスポーンで置けないとき、save を呼ばないこと（BR3.4）"""
        store = mock_store()
        core = self.core_with(store)
        for cell in core._field.cells:  # pylint: disable=W0212
            if cell.opened:
                cell.item = Item("blue", 1)
        self.assertIsNone(core.spawn())
        store.save.assert_not_called()

    def test_drop_actions_save_snapshot(self):
        """マージ・移動・削除・成長枠・クリア枠の操作が実行されると、snapshot で save が 1 回呼ばれること（BR3.5）"""
        # pylint: disable=W0212
        cases = {
            "merge": (Item("blue", 2), (5, 5)),
            "move": (Item("blue", 2), (5, 5)),
            "delete": (Item("blue", 2), main.DELETE_SLOT),
            "grow": (main.GROWTH_ITEMS[1][0], main.GrowthSlotCell(0)),
            "clear": (
                Item(main.CLEAR_COLOR_START, main.MERGE_MAX_NUMBER),
                main.CLEAR_SLOT,
            ),
        }
        for name, (item, target) in cases.items():
            with self.subTest(name=name):
                store = mock_store()
                core = self.core_with(store)
                core._field.cell(4, 4).item = item
                if name == "merge":
                    core._field.cell(5, 5).item = item  # 同じ色・数字のマスへ
                    core._field.cell(5, 5).opened = True
                core._selected = (4, 4)
                core._on_drop(target)
                store.save.assert_called_once_with(core.snapshot())

    def test_cancelled_drop_does_not_save(self):
        """操作が実行できない（キャンセル）とき、save を呼ばないこと（BR3.6）"""
        # pylint: disable=W0212
        store = mock_store()
        core = self.core_with(store)
        core._field.cell(4, 4).item = Item("blue", 2)
        core._selected = (4, 4)
        core._on_drop(main.CLEAR_SLOT)  # 最高の数字ではないので入れられない
        store.save.assert_not_called()

    def test_clear_saves_no_game(self):
        """クリアに達した操作では、save({}) だけが呼ばれ、snapshot は保存されないこと（BR3.7）"""
        # pylint: disable=W0212
        store = mock_store()
        core = self.core_with(store)
        fill_clear_slot(core, main.CLEAR_REQUIRED_COUNT - 1)
        store.save.reset_mock()
        self.assertFalse(core.cleared)
        fill_clear_slot(core, main.CLEAR_REQUIRED_COUNT)
        self.assertTrue(core.cleared)
        store.save.assert_called_once_with({})

    def test_restart_saves_initial_snapshot(self):
        """restart() で、初期状態の snapshot が 1 回保存されること（BR3.8）"""
        store = mock_store()
        core = self.core_with(store)
        make_cleared(core)
        store.save.reset_mock()
        core.restart()
        store.save.assert_called_once_with(GameCore(store=mock_store()).snapshot())

    def test_popup_tap_restart_saves_initial_snapshot(self):
        """ポップアップのタップでやり直すと、初期状態の snapshot が保存されること（BR3.8）"""
        store = mock_store()
        core = self.core_with(store)
        make_cleared(core)
        store.save.reset_mock()
        center = (main.POPUP_X + main.POPUP_W // 2, main.POPUP_Y + main.POPUP_H // 2)
        self.frame(core, tapped=center)
        store.save.assert_not_called()  # 押しただけ（待機）では保存しない
        self.frame(core, released=center)
        store.save.assert_called_once_with(GameCore(store=mock_store()).snapshot())

    def test_save_failure_is_ignored_and_retried_on_next_change(self):
        """save が偽を返しても例外が出ず、次の変化でまた save が呼ばれること（BR3.9）"""
        store = mock_store(saved=False)
        core = self.core_with(store)
        core.spawn()
        core.spawn()
        self.assertEqual(2, store.save.call_count)

    def test_non_changing_input_does_not_save(self):
        """選択・ポインタの移動・キャンセルの離すでは、save を呼ばないこと（BR3.10）"""
        store = mock_store()
        core = self.core_with(store)
        core._field.cell(4, 4).item = Item("blue", 2)  # pylint: disable=W0212
        self.frame(core, tapped=cell_center(4, 4))
        self.assertIsNotNone(core.selected)
        self.frame(core, held=cell_center(3, 4))
        self.frame(core, released=(0, SCREEN_HEIGHT - 1))  # 何もない位置
        store.save.assert_not_called()

    def test_default_store_is_save_store(self):
        """store を渡さないと SaveStore() を作って使うこと（BR3.11）"""
        with patch("src.main.SaveStore") as save_store_class:
            save_store_class.return_value = mock_store()
            core = GameCore()
            save_store_class.assert_called_once_with()
            save_store_class.return_value.load.assert_called_once_with()
            core.spawn()
            save_store_class.return_value.save.assert_called_once()
