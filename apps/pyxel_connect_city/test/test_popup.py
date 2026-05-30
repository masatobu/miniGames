import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from src.main import IView, GameCore, PyxelHexGridView  # pylint: disable=C0413
from node import NodeType, Node, NodeParams  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def draw_rect(self, x, y, w, h, col):
        self.call_params.append(("draw_rect", x, y, w, h, col))

    def draw_rectb(self, x, y, w, h, col):
        self.call_params.append(("draw_rectb", x, y, w, h, col))

    def draw_image(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_image", x, y, img, u, v, w, h, colkey))

    def get_frame(self) -> int:
        return 0

    def get_call_params(self):
        return self.call_params


class TestParentPopup(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.patcher_view.start()
        self.patcher_store = patch("src.main.ReportStore")
        self.mock_store_cls = self.patcher_store.start()
        self.mock_store = self.mock_store_cls.return_value
        self.mock_store.load.return_value = None
        self.patcher_hex_grid_view = patch("src.main.PyxelHexGridView.create")
        self.patcher_hex_grid_view.start()
        self.patcher_input = patch("src.main.PyxelInput.create")
        self.patcher_input.start()
        self.patcher_grid_input = patch("src.main.PyxelGridInput.create")
        self.patcher_grid_input.start()

    def tearDown(self):
        self.patcher_grid_input.stop()
        self.patcher_input.stop()
        self.patcher_hex_grid_view.stop()
        self.patcher_view.stop()
        self.patcher_store.stop()

    def _draw_popup_calls(self, node):
        """_draw_popup() を呼んで記録された IView 呼び出しを返す"""
        self.test_view.call_params.clear()
        self.core._draw_popup(node)  # pylint: disable=W0212
        return self.test_view.call_params[:]

    def _popup_calls(self, node_type, level=0, growth_stock=None):
        """ノード種別・レベルに対応するポップアップ全描画の期待呼び出しリストを返す"""
        if growth_stock is None:
            growth_stock = {}
        G = GameCore
        cx = G.POPUP_X + G.POPUP_PADDING
        cy = G.POPUP_Y + G.POPUP_PADDING
        div_x = G.POPUP_X + G.POPUP_PADDING
        div_w = G.POPUP_W - 2 * G.POPUP_PADDING
        node_v = PyxelHexGridView.NODE_V[node_type]
        node_u = PyxelHexGridView.LEVEL_U[level]
        params = NodeParams.get(node_type, level)
        cw = G.CHAR_W
        sx = G.POPUP_SECTION2_SLASH_X
        tr = G.POPUP_SECTION2_TEXT_RIGHT_X

        calls = [
            ("draw_rect", G.POPUP_X, G.POPUP_Y, G.POPUP_W, G.POPUP_H, G.POPUP_BG_COL),
            (
                "draw_rectb",
                G.POPUP_X,
                G.POPUP_Y,
                G.POPUP_W,
                G.POPUP_H,
                G.POPUP_BORDER_COL,
            ),
            ("draw_blt", cx, cy, 1, node_u, node_v, 16, 16, 0),
            ("draw_text", cx + 20, cy + 4, f"{node_type.value} Lv.{level}"),
            (
                "draw_rect",
                div_x,
                G.POPUP_HEADER_DIVIDER_Y,
                div_w,
                1,
                G.POPUP_BORDER_COL,
            ),
        ]
        y1 = G.POPUP_SECTION1_Y
        for material, rate in params.consumption_rates.items():
            mu, mv = G.MATERIAL_UV[material]
            calls.append(
                (
                    "draw_blt",
                    G.POPUP_SECTION1_CONSUMPTION_X,
                    y1,
                    G.MATERIAL_ICON_LAYER,
                    mu,
                    mv,
                    G.MATERIAL_ICON_W,
                    G.MATERIAL_ICON_H,
                    0,
                )
            )
            calls.append(
                ("draw_text", G.POPUP_SECTION1_CONSUMPTION_X + 10, y1, f"{rate}/s")
            )
        if params.consumption_rates or params.production_rates:
            calls.append(("draw_text", G.POPUP_SECTION1_ARROW_X, y1, "->"))
        for material, rate in params.production_rates.items():
            mu, mv = G.MATERIAL_UV[material]
            calls.append(
                (
                    "draw_blt",
                    G.POPUP_SECTION1_PRODUCTION_X,
                    y1,
                    G.MATERIAL_ICON_LAYER,
                    mu,
                    mv,
                    G.MATERIAL_ICON_W,
                    G.MATERIAL_ICON_H,
                    0,
                )
            )
            calls.append(
                ("draw_text", G.POPUP_SECTION1_PRODUCTION_X + 10, y1, f"{rate}/s")
            )
        calls.append(
            ("draw_rect", div_x, G.POPUP_DIVIDER_Y, div_w, 1, G.POPUP_BORDER_COL)
        )
        for i, material in enumerate(params.growth_stock_cols):
            current = growth_stock.get(material, 0)
            limit = params.growth_limits[material]
            y = G.POPUP_SECTION2_Y + i * G.LINE_H
            mu, mv = G.MATERIAL_UV[material]
            calls.append(
                (
                    "draw_blt",
                    G.POPUP_SECTION2_X,
                    y,
                    G.MATERIAL_ICON_LAYER,
                    mu,
                    mv,
                    G.MATERIAL_ICON_W,
                    G.MATERIAL_ICON_H,
                    0,
                )
            )
            cur_txt = str(current)
            lim_txt = str(limit)
            calls.append(("draw_text", sx - len(cur_txt) * cw - cw, y, cur_txt))
            calls.append(("draw_text", sx, y, "/"))
            calls.append(("draw_text", tr - len(lim_txt) * cw, y, lim_txt))
        return calls


class TestClearPopupClickRange(TestParentPopup):
    """クリアポップアップのクリック範囲制限テスト"""

    def setUp(self):
        super().setUp()
        self.core = GameCore()
        self.core._clear_popup_shown = True  # pylint: disable=W0212

    def _click_at(self, x, y):
        self.core._input.is_mouse_btn_pressed.return_value = (
            True  # pylint: disable=W0212
        )
        self.core._input.mouse_x = x  # pylint: disable=W0212
        self.core._input.mouse_y = y  # pylint: disable=W0212
        self.core.update()

    def test_click_range(self):
        """クリック座標によるリセット可否を検証"""
        G = GameCore
        cx = G.CLEAR_POPUP_X + G.CLEAR_POPUP_W // 2
        cy = G.CLEAR_POPUP_Y + G.CLEAR_POPUP_H // 2
        rx = G.CLEAR_POPUP_X + G.CLEAR_POPUP_W - 1
        by = G.CLEAR_POPUP_Y + G.CLEAR_POPUP_H - 1
        cases = [
            ("内側中央", cx, cy, True),
            ("左上隅（境界）", G.CLEAR_POPUP_X, G.CLEAR_POPUP_Y, True),
            ("右上隅（境界）", rx, G.CLEAR_POPUP_Y, True),
            ("左下隅（境界）", G.CLEAR_POPUP_X, by, True),
            ("右下隅（境界）", rx, by, True),
            ("左外", G.CLEAR_POPUP_X - 1, cy, False),
            ("上外", cx, G.CLEAR_POPUP_Y - 1, False),
        ]
        for label, x, y, expected in cases:
            with self.subTest(label):
                self.core._needs_reset = False  # pylint: disable=W0212
                self._click_at(x, y)
                self.assertEqual(self.core.needs_reset, expected)


class TestDrawPopup(TestParentPopup):
    """ノード種別ごとのポップアップ全描画検証"""

    def setUp(self):
        super().setUp()
        self.core = GameCore()

    def test_popup_draw_by_node_type(self):
        """各ノード種別のポップアップ全描画が正しい"""
        cases = [
            ("FOREST lv0", NodeType.FOREST, 0),
            ("MOUNTAIN lv0", NodeType.MOUNTAIN, 0),
            ("FACTORY lv0", NodeType.FACTORY, 0),
            ("FACTORY lv1", NodeType.FACTORY, 1),
            ("FACTORY lv2", NodeType.FACTORY, 2),
            ("CITY lv0", NodeType.CITY, 0),
            ("CITY lv1", NodeType.CITY, 1),
            ("CITY lv2", NodeType.CITY, 2),
            ("CITY lv3", NodeType.CITY, 3),
        ]
        for label, node_type, level in cases:
            with self.subTest(label):
                node = Node(col=0, row=0, node_type=node_type, level=level)
                self.assertEqual(
                    self._draw_popup_calls(node),
                    self._popup_calls(node_type, level=level),
                )
