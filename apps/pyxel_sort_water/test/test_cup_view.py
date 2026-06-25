import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from src.main import PyxelCupView, Color, WaterColor, IView  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        self._calls = []

    def draw_text(self, x, y, text):
        self._calls.append(("draw_text", x, y, text))

    def draw_line(self, x1, y1, x2, y2, col):
        self._calls.append(("draw_line", x1, y1, x2, y2, col))

    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        self._calls.append(("draw_tri", x1, y1, x2, y2, x3, y3, col))

    def draw_rectb(self, x, y, w, h, col):
        self._calls.append(("draw_rectb", x, y, w, h, col))

    def draw_rect(self, x, y, w, h, col):
        self._calls.append(("draw_rect", x, y, w, h, col))

    def get_calls(self):
        return self._calls


class TestPyxelCupViewCoordinate(unittest.TestCase):
    def test_pixel_to_cup_pos(self):
        """ピクセル座標が (col, row) または None に変換されること（グリッド4隅の内外を網羅）"""
        cases = [
            # --- 左上コーナー (col=0, row=0): グリッド最左上のコップ ---
            (6, 16, (0, 0)),  # 内: 左上ピクセル (MARGIN_X, MARGIN_Y)
            (35, 55, (0, 0)),  # 内: 右下ピクセル (MARGIN_Y + CUP_H - 1 = 55)
            (5, 16, None),  # 外: 左辺の1px外
            (6, 15, None),  # 外: 上辺の1px外
            # --- 右上コーナー (col=3, row=0): グリッド最右上のコップ ---
            (114, 16, (3, 0)),  # 内: 左上ピクセル
            (143, 16, (3, 0)),  # 内: 右上ピクセル (グリッド右端)
            (144, 16, None),  # 外: 右辺の1px外 (コップ間すき間)
            (143, 15, None),  # 外: 上辺の1px外
            # --- 左下コーナー (col=0, row=3): グリッド最左下のコップ ---
            (6, 148, (0, 3)),  # 内: 左上ピクセル
            (6, 187, (0, 3)),  # 内: 左下ピクセル (グリッド下端)
            (5, 187, None),  # 外: 左辺の1px外
            (6, 188, None),  # 外: 下辺の1px外 (コップ間すき間)
            # --- 右下コーナー (col=3, row=3): グリッド最右下のコップ ---
            (114, 148, (3, 3)),  # 内: 左上ピクセル
            (143, 187, (3, 3)),  # 内: 右下ピクセル (グリッド最右下端)
            (144, 187, None),  # 外: 右辺の1px外 (コップ間すき間)
            (143, 188, None),  # 外: 下辺の1px外 (コップ間すき間)
        ]
        for x, y, expected in cases:
            with self.subTest(x=x, y=y):
                self.assertEqual(expected, PyxelCupView.pixel_to_cup_pos(x, y))


class TestPyxelCupView(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher = patch.object(
            PyxelCupView, "_create_view", return_value=self.test_view
        )
        self.patcher.start()
        self.cup_view = PyxelCupView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_with_selected_true_renders_background(self):
        """selected=True のとき、選択背景 draw_rect がコップ枠より先に描画されること"""
        # col=0, row=0 → x=6, y=16; 右辺x=35, 底辺y=55
        # 選択背景はコップより SEL_PAD px 広く描画される
        self.cup_view.draw([], 0, 0, selected=True)
        pad = PyxelCupView.SEL_PAD
        expected = [
            (
                "draw_rect",
                6 - pad,
                16 - pad,
                PyxelCupView.CUP_W + 2 * pad,
                PyxelCupView.CUP_H + 2 * pad,
                Color.DARK_RED,
            ),  # 選択背景（コップより pad px 広い）
            ("draw_line", 6, 16, 6, 55, Color.WHITE),  # 左辺
            ("draw_line", 35, 16, 35, 55, Color.WHITE),  # 右辺
            ("draw_line", 6, 55, 35, 55, Color.WHITE),  # 底辺
        ]
        self.assertEqual(expected, self.test_view.get_calls())

    def test_draw_layers_correct_sequence(self):
        """コップ枠が先に描画され、水層が正しい座標・色で描画されること（0〜3層すべて含む）"""
        # col=0, row=0 → x=MARGIN_X=6, y=MARGIN_Y=16
        # _layer_y(y=16, i) = 16 + 40 - 1 - 12*(i+1)
        # col=0, row=0 → x=6, y=16; 右辺x=35, 底辺y=55
        cup_border = [
            ("draw_line", 6, 16, 6, 55, Color.WHITE),  # 左辺
            ("draw_line", 35, 16, 35, 55, Color.WHITE),  # 右辺
            ("draw_line", 6, 55, 35, 55, Color.WHITE),  # 底辺
        ]
        cases = [
            (
                [],
                cup_border,
            ),
            (
                [WaterColor.A],
                cup_border
                + [
                    ("draw_rect", 7, 43, 28, 12, WaterColor.A),  # layer=0 最下層 wy=43
                ],
            ),
            (
                [WaterColor.A, WaterColor.B],
                cup_border
                + [
                    ("draw_rect", 7, 43, 28, 12, WaterColor.A),  # layer=0 最下層 wy=43
                    ("draw_rect", 7, 31, 28, 12, WaterColor.B),  # layer=1 中層   wy=31
                ],
            ),
            (
                [WaterColor.A, WaterColor.B, WaterColor.C],
                cup_border
                + [
                    ("draw_rect", 7, 43, 28, 12, WaterColor.A),  # layer=0 最下層 wy=43
                    ("draw_rect", 7, 31, 28, 12, WaterColor.B),  # layer=1 中層   wy=31
                    ("draw_rect", 7, 19, 28, 12, WaterColor.C),  # layer=2 最上層 wy=19
                ],
            ),
        ]
        for layers, expected in cases:
            with self.subTest(layers=layers):
                self.test_view.get_calls().clear()
                self.cup_view.draw(layers, 0, 0, False)
                self.assertEqual(expected, self.test_view.get_calls())

    def test_draw_calculates_pixel_position(self):
        """col/row からピクセル座標が計算されること（描画順序を含む）"""
        cases = [
            # (col, row, expected_px, expected_py)
            (0, 0, PyxelCupView.MARGIN_X, PyxelCupView.MARGIN_Y),
            (
                1,
                0,
                PyxelCupView.MARGIN_X + PyxelCupView.COL_STEP,
                PyxelCupView.MARGIN_Y,
            ),
            (
                0,
                1,
                PyxelCupView.MARGIN_X,
                PyxelCupView.MARGIN_Y + PyxelCupView.ROW_STEP,
            ),
            (
                3,
                2,
                PyxelCupView.MARGIN_X + 3 * PyxelCupView.COL_STEP,
                PyxelCupView.MARGIN_Y + 2 * PyxelCupView.ROW_STEP,
            ),
        ]
        for col, row, expected_px, expected_py in cases:
            with self.subTest(col=col, row=row):
                self.test_view.get_calls().clear()
                self.cup_view.draw([], col, row, False)
                bx = expected_px + PyxelCupView.CUP_W - 1
                by = expected_py + PyxelCupView.CUP_H - 1
                expected = [
                    (
                        "draw_line",
                        expected_px,
                        expected_py,
                        expected_px,
                        by,
                        Color.WHITE,
                    ),  # 左辺
                    ("draw_line", bx, expected_py, bx, by, Color.WHITE),  # 右辺
                    ("draw_line", expected_px, by, bx, by, Color.WHITE),  # 底辺
                ]
                self.assertEqual(expected, self.test_view.get_calls())


class TestPyxelCupViewAnimation(unittest.TestCase):
    # col=0, row=0 固定で全テストを実施
    # x=6, y=16, bx=35, by=55
    # layer_y: i=0→43, i=1→31, i=2→19, i=3→7

    def setUp(self):
        self.test_view = TestView()
        self.patcher = patch.object(
            PyxelCupView, "_create_view", return_value=self.test_view
        )
        self.patcher.start()
        self.cup_view = PyxelCupView()

    def tearDown(self):
        self.patcher.stop()

    def _cup_border(self):
        """col=0, row=0 のコップ枠3辺"""
        x, y = PyxelCupView.MARGIN_X, PyxelCupView.MARGIN_Y
        bx = x + PyxelCupView.CUP_W - 1
        by = y + PyxelCupView.CUP_H - 1
        return [
            ("draw_line", x, y, x, by, Color.WHITE),
            ("draw_line", bx, y, bx, by, Color.WHITE),
            ("draw_line", x, by, bx, by, Color.WHITE),
        ]

    def _water_rect(self, layer_i, color, scale=1.0):
        """layer_i 番目の位置に scale 倍の高さで水層を描画したときの draw_rect タプル（下端固定）"""
        x = PyxelCupView.MARGIN_X
        y = PyxelCupView.MARGIN_Y
        lh = PyxelCupView.LAYER_H
        h = round(lh * scale)
        # 水層 Y 座標（layer 0 が最下層）: コップ下端から layer_i+1 層分積み上げた位置
        layer_y = y + PyxelCupView.CUP_H - 1 - lh * (layer_i + 1)
        draw_y = layer_y + (lh - h)
        return ("draw_rect", x + 1, draw_y, PyxelCupView.CUP_W - 2, h, color)

    def test_draw_animation_args(self):
        """アニメーション引数の組み合わせごとに全描画シーケンスを検証する"""
        cases = [
            (
                "デフォルト(3層): 全層が通常の LAYER_H・正しい座標で描画",
                [WaterColor.A, WaterColor.B, WaterColor.C],
                {},
                [
                    self._water_rect(0, WaterColor.A),  # (7, 43, 28, 12, A)
                    self._water_rect(1, WaterColor.B),  # (7, 31, 28, 12, B)
                    self._water_rect(2, WaterColor.C),  # (7, 19, 28, 12, C)
                ],
            ),
            (
                "anim_shrink_top=0.5: 最上層のみ縮小・y 下端固定、下層は変わらない",
                [WaterColor.A, WaterColor.B, WaterColor.C],
                {"anim_shrink_top": 0.5},
                [
                    self._water_rect(0, WaterColor.A),  # (7, 43, 28, 12, A)
                    self._water_rect(1, WaterColor.B),  # (7, 31, 28, 12, B)
                    self._water_rect(2, WaterColor.C, scale=0.5),  # (7, 25, 28,  6, C)
                ],
            ),
            (
                "anim_shrink_top=0.0: 最上層は描画されず、下層は変わらない",
                [WaterColor.A, WaterColor.B, WaterColor.C],
                {"anim_shrink_top": 0.0},
                [
                    self._water_rect(0, WaterColor.A),  # (7, 43, 28, 12, A)
                    self._water_rect(1, WaterColor.B),  # (7, 31, 28, 12, B)
                    # C は h=0 のため描画なし
                ],
            ),
            (
                "anim_extra_color+scale=0.5: 追加層が layer_i=2 に半分の高さで描画",
                [WaterColor.A, WaterColor.B],
                {"anim_extra_color": WaterColor.C, "anim_extra_scale": 0.5},
                [
                    self._water_rect(0, WaterColor.A),  # (7, 43, 28, 12, A)
                    self._water_rect(1, WaterColor.B),  # (7, 31, 28, 12, B)
                    self._water_rect(2, WaterColor.C, scale=0.5),  # (7, 25, 28,  6, C)
                ],
            ),
            (
                "デフォルト(2層): 追加層は描画されない",
                [WaterColor.A, WaterColor.B],
                {},
                [
                    self._water_rect(0, WaterColor.A),  # (7, 43, 28, 12, A)
                    self._water_rect(1, WaterColor.B),  # (7, 31, 28, 12, B)
                ],
            ),
        ]
        for label, layers, draw_kwargs, expected_water in cases:
            with self.subTest(label):
                self.test_view.get_calls().clear()
                self.cup_view.draw(layers, 0, 0, False, **draw_kwargs)
                self.assertEqual(
                    self._cup_border() + expected_water, self.test_view.get_calls()
                )
