import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from src.main import (  # pylint: disable=C0413
    PyxelHexGridView,
    GridType,
    EdgeFlow,
    _TILE_W,
    _TILE_H,
    _ROW_Y_STEP,
    _ODD_ROW_X_OFFSET,
    PyxelGridInput,
)
from node import NodeType, NodeManager  # pylint: disable=C0413
from grid_path import GridDirect  # pylint: disable=C0413


class TestView:
    def __init__(self):
        self._blt_calls = []
        self._frame = 0

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self._blt_calls.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def get_blt_calls(self):
        return self._blt_calls

    def get_frame(self):
        return self._frame

    def set_frame(self, n):
        self._frame = n


class TestPyxelHexGridView(unittest.TestCase):
    TILE_U = 8
    TILE_V = 0

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelHexGridView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.grid_view = PyxelHexGridView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_uv_and_size_by_grid_type(self):
        """draw_grid が GridType に応じた UV でタイルを描画すること（サイズは共通）"""
        cases = [
            # (grid_type, expected_u, expected_v)
            (GridType.NORMAL, self.TILE_U, self.TILE_V),
            (GridType.HIGHLIGHTED, 40, 0),
            (GridType.SELECTED, 72, 0),
        ]
        for grid_type, expected_u, expected_v in cases:
            with self.subTest(grid_type=grid_type):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw_grid(0, 0, grid_type)
                self.assertEqual(
                    [
                        (
                            "draw_blt",
                            0,
                            0,
                            0,
                            expected_u,
                            expected_v,
                            _TILE_W,
                            _TILE_H,
                            0,
                        )
                    ],
                    self.test_view.get_blt_calls(),
                )

    def test_draw_calculates_pixel_position(self):
        """col/row からピクセル座標が計算されること（千鳥配置・GridType によらず同一位置）"""
        cases = [
            # (case, col, row, expected_px, expected_py)
            # 偶数行（row % 2 == 0）: x_offset = 0
            ("col_0_row_0", 0, 0, 0, 0),
            ("col_1_row_0", 1, 0, _TILE_W, 0),
            ("col_2_row_2", 2, 2, 2 * _TILE_W, 2 * _ROW_Y_STEP),
            # 奇数行（row % 2 == 1）: x_offset = _ODD_ROW_X_OFFSET
            ("col_0_row_1", 0, 1, _ODD_ROW_X_OFFSET, _ROW_Y_STEP),
            ("col_1_row_1", 1, 1, _TILE_W + _ODD_ROW_X_OFFSET, _ROW_Y_STEP),
            ("col_0_row_3", 0, 3, _ODD_ROW_X_OFFSET, 3 * _ROW_Y_STEP),
        ]
        for grid_type in GridType:
            for case, col, row, expected_px, expected_py in cases:
                with self.subTest(grid_type=grid_type, case=case):
                    self.test_view.get_blt_calls().clear()
                    self.grid_view.draw_grid(col, row, grid_type)
                    actual_call = self.test_view.get_blt_calls()[0]
                    # ("draw_blt", x, y, img, u, v, w, h, colkey)
                    actual_x, actual_y = actual_call[1], actual_call[2]
                    self.assertEqual(expected_px, actual_x, f"{case}: x")
                    self.assertEqual(expected_py, actual_y, f"{case}: y")


class TestPyxelHexGridViewDrawNode(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelHexGridView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.grid_view = PyxelHexGridView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_node(self):
        """draw_node が各ノード種別・行列位置で正しい座標・UV で draw_blt されること"""
        cases = [
            # (case, col, row, node_type, px, py, v)
            # 偶数行（row % 2 == 0）: x_offset = 0
            ("forest_even_row", 1, 0, NodeType.FOREST, 40, 9, 32),
            ("city_even_row", 0, 0, NodeType.CITY, 8, 9, 0),
            ("factory_even_row", 0, 0, NodeType.FACTORY, 8, 9, 16),
            # 奇数行（row % 2 == 1）: x_offset = 16
            ("mountain_odd_row", 0, 1, NodeType.MOUNTAIN, 24, 33, 48),
        ]
        for case, col, row, node_type, px, py, v in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw_node(col=col, row=row, node_type=node_type)
                self.assertEqual(
                    [("draw_blt", px, py, 1, 8, v, 16, 16, 0)],
                    self.test_view.get_blt_calls(),
                )

    def test_draw_node_level_uv(self):
        """draw_node が CITY/FACTORY でレベルに応じた UV を使うこと"""
        # col=0, row=0（偶数行）: px=8, py=9
        cases = [
            # (case, node_type, level, u, v)
            ("city_level0", NodeType.CITY, 0, 8, 0),
            ("city_level1", NodeType.CITY, 1, 24, 0),
            ("city_level2", NodeType.CITY, 2, 40, 0),
            ("city_level3", NodeType.CITY, 3, 56, 0),
            ("city_level4", NodeType.CITY, 4, 72, 0),
            ("factory_level0", NodeType.FACTORY, 0, 8, 16),
            ("factory_level1", NodeType.FACTORY, 1, 24, 16),
            ("factory_level2", NodeType.FACTORY, 2, 40, 16),
            ("forest_level0", NodeType.FOREST, 0, 8, 32),
            ("mountain_level0", NodeType.MOUNTAIN, 0, 8, 48),
        ]
        for case, node_type, level, u, v in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw_node(col=0, row=0, node_type=node_type, level=level)
                self.assertEqual(
                    [("draw_blt", 8, 9, 1, u, v, 16, 16, 0)],
                    self.test_view.get_blt_calls(),
                )


class TestPyxelHexGridViewDrawEdge(unittest.TestCase):
    EDGE_UV = {
        GridDirect.UL: (8, 32),
        GridDirect.UR: (40, 32),
        GridDirect.R: (72, 32),
        GridDirect.DR: (104, 32),
        GridDirect.DL: (136, 32),
        GridDirect.L: (168, 32),
    }

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelHexGridView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.grid_view = PyxelHexGridView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_edge_uv_by_direction(self):
        """draw_edge が GridDirect に応じた UV で draw_blt されること"""
        for direct, (expected_u, expected_v) in self.EDGE_UV.items():
            with self.subTest(direct=direct):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw_edge(0, 0, direct, None)
                self.assertEqual(
                    [
                        (
                            "draw_blt",
                            0,
                            0,
                            0,
                            expected_u,
                            expected_v,
                            _TILE_W,
                            _TILE_H,
                            0,
                        )
                    ],
                    self.test_view.get_blt_calls(),
                )

    def test_draw_edge_calculates_pixel_position(self):
        """draw_edge が col/row から draw_grid と同一のピクセル座標を計算すること（千鳥配置）"""
        cases = [
            # (case, col, row, expected_px, expected_py)
            # 偶数行（row % 2 == 0）: x_offset = 0
            ("even_row_0_0", 0, 0, 0, 0),
            ("even_row_1_0", 1, 0, _TILE_W, 0),
            ("even_row_2_2", 2, 2, 2 * _TILE_W, 2 * _ROW_Y_STEP),
            # 奇数行（row % 2 == 1）: x_offset = _ODD_ROW_X_OFFSET
            ("odd_row_0_1", 0, 1, _ODD_ROW_X_OFFSET, _ROW_Y_STEP),
            ("odd_row_1_1", 1, 1, _TILE_W + _ODD_ROW_X_OFFSET, _ROW_Y_STEP),
        ]
        for case, col, row, expected_px, expected_py in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw_edge(col, row, GridDirect.R, None)
                actual_call = self.test_view.get_blt_calls()[0]
                actual_x, actual_y = actual_call[1], actual_call[2]
                self.assertEqual(expected_px, actual_x, f"{case}: x")
                self.assertEqual(expected_py, actual_y, f"{case}: y")


class TestPyxelHexGridViewDrawEdgeAnimation(unittest.TestCase):
    ANIM_INTERVAL = 8  # テスト独立性のためハードコード（実装定数から生成しない）

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.mock_pyxel_view.get_frame.side_effect = self.test_view.get_frame
        self.patcher = patch.object(
            PyxelHexGridView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.grid_view = PyxelHexGridView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_edge_outward_animation_v_sequence(self):
        """EdgeFlow.OUTWARD でフレームに応じて v=64→96→128→160→64 のサイクルになること"""
        anim_interval = self.ANIM_INTERVAL
        cases = [
            (0, 64),
            (anim_interval, 96),
            (2 * anim_interval, 128),
            (3 * anim_interval, 160),
            (4 * anim_interval, 64),
        ]
        for frame, expected_v in cases:
            with self.subTest(frame=frame):
                self.test_view.get_blt_calls().clear()
                self.test_view.set_frame(frame)
                self.grid_view.draw_edge(0, 0, GridDirect.R, EdgeFlow.OUTWARD)
                self.assertEqual(
                    [("draw_blt", 0, 0, 0, 72, expected_v, _TILE_W, _TILE_H, 0)],
                    self.test_view.get_blt_calls(),
                )

    def test_draw_edge_inward_animation_v_sequence(self):
        """EdgeFlow.INWARD でフレームに応じて v=160→128→96→64→160 の逆順サイクルになること"""
        anim_interval = self.ANIM_INTERVAL
        cases = [
            (0, 160),
            (anim_interval, 128),
            (2 * anim_interval, 96),
            (3 * anim_interval, 64),
            (4 * anim_interval, 160),
        ]
        for frame, expected_v in cases:
            with self.subTest(frame=frame):
                self.test_view.get_blt_calls().clear()
                self.test_view.set_frame(frame)
                self.grid_view.draw_edge(0, 0, GridDirect.R, EdgeFlow.INWARD)
                self.assertEqual(
                    [("draw_blt", 0, 0, 0, 72, expected_v, _TILE_W, _TILE_H, 0)],
                    self.test_view.get_blt_calls(),
                )


class TestInput:
    """PyxelInput のテスト用スタブ"""

    def __init__(self):
        self._pressed = False
        self._x = 0
        self._y = 0

    def is_mouse_btn_pressed(self):
        return self._pressed

    @property
    def mouse_x(self):
        return self._x

    @property
    def mouse_y(self):
        return self._y

    def set_click(self, x, y):
        self._pressed = True
        self._x = x
        self._y = y

    def release(self):
        self._pressed = False


class TestPyxelGridInput(unittest.TestCase):
    def setUp(self):
        self.test_input = TestInput()
        self.patcher = patch("src.main.PyxelInput.create", return_value=self.test_input)
        self.patcher.start()
        self.grid_input = PyxelGridInput()

    def tearDown(self):
        self.patcher.stop()

    def test_no_click_returns_none(self):
        """クリックなしは None を返すこと"""
        self.assertIsNone(self.grid_input.get_clicked_grid())

    def test_click_returns_grid_coords(self):
        """クリック位置のピクセル座標が正しいグリッド座標に変換されること（Y オフセット +4px 後）"""
        cases = [
            # (case, px, py, expected_col, expected_row)
            # --- タイル中心（Y オフセット +4px 後）: 偶数行 py=row*24+16 / 奇数行 py=row*24+16 ---
            ("center_0_0", 16, 16, 0, 0),
            ("center_1_0", 48, 16, 1, 0),
            ("center_2_2", 80, 64, 2, 2),
            ("center_0_1", 32, 40, 0, 1),
            ("center_1_1", 64, 40, 1, 1),
            ("center_0_3", 32, 88, 0, 3),
            # --- 偶数行 col 境界 (x_offset=0): col = px // 32 ---
            ("even_left_col0", 0, 4, 0, 0),  # col=0 左端
            ("even_right_col0", 31, 4, 0, 0),  # col=0 右端
            ("even_left_col1", 32, 4, 1, 0),  # col=1 左端
            # --- 奇数行 col 境界 (x_offset=16): col = (px - 16) // 32 ---
            ("odd_left_col0", 16, 28, 0, 1),  # col=0 左端
            ("odd_right_col0", 47, 28, 0, 1),  # col=0 右端
            ("odd_left_col1", 48, 28, 1, 1),  # col=1 左端
            # --- 行境界（Y オフセット +4px 後）: row = (py - 4) // 24 ---
            ("row_last_of_0", 0, 27, 0, 0),  # row=0 最終ピクセル
            (
                "row_first_of_1",
                16,
                28,
                0,
                1,
            ),  # row=1 先頭ピクセル（奇数行, x_offset=16）
            ("row_last_of_1", 16, 51, 0, 1),  # row=1 最終ピクセル
            ("row_first_of_2", 0, 52, 0, 2),  # row=2 先頭ピクセル（偶数行）
        ]
        for case, px, py, expected_col, expected_row in cases:
            with self.subTest(case=case):
                self.test_input.set_click(px, py)
                col, row = self.grid_input.get_clicked_grid()
                self.assertEqual(expected_col, col, f"{case}: col")
                self.assertEqual(expected_row, row, f"{case}: row")

    def test_release_returns_none(self):
        """クリック解放後は None を返すこと"""
        self.test_input.set_click(16, 12)
        self.assertIsNotNone(self.grid_input.get_clicked_grid())
        self.test_input.release()
        self.assertIsNone(self.grid_input.get_clicked_grid())

    def test_out_of_bounds_returns_none(self):
        """境界チェック: 範囲外グリッドは None を返すこと"""
        cases = [
            # col < 0: 奇数行左マージン (0-16)//32 = -1
            ("col_negative", 0, 28),
            # col >= HEX_COLUMN_NUM: 偶数行, px = HEX_COLUMN_NUM * _TILE_W
            ("col_ge_max", NodeManager.HEX_COLUMN_NUM * _TILE_W, 4),
            # row < 0: py < 4 → (py-4)//24 = -1
            ("row_negative", 16, 0),
            # row >= HEX_ROW_NUM: py = 4 + HEX_ROW_NUM * _ROW_Y_STEP
            ("row_ge_max", 0, 4 + NodeManager.HEX_ROW_NUM * _ROW_Y_STEP),
        ]
        for case, px, py in cases:
            with self.subTest(case=case):
                self.test_input.set_click(px, py)
                self.assertIsNone(
                    self.grid_input.get_clicked_grid(), f"{case}: expected None"
                )
