import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import PyxelGridView  # pylint: disable=C0413


class TestView:
    def __init__(self):
        self._blt_calls = []

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self._blt_calls.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def get_blt_calls(self):
        return self._blt_calls


class TestPyxelGridView(unittest.TestCase):
    GRID_W = 16
    GRID_H = 15
    VERTICAL_OFFSET = 7  # 三角形の重なり幅（px）

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.get_frame.return_value = 0
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelGridView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.grid_view = PyxelGridView()

    def tearDown(self):
        self.patcher.stop()

    def test_draw_calls_draw_blt_with_correct_params(self):
        cases = [
            ("correct_uv", 0, 0, 8, 0),
            ("variant_changes_u", 3, 0, 56, 0),
            ("level_changes_v", 0, 2, 8, 32),
        ]
        for case, variant, level, expected_u, expected_v in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw(0, 0, level, variant)
                expected_call = (
                    "draw_blt",
                    0,
                    0,
                    0,
                    expected_u,
                    expected_v,
                    self.GRID_W,
                    self.GRID_H,
                    0,
                )
                self.assertEqual(
                    [expected_call],
                    self.test_view.get_blt_calls(),
                    f"{case}: actual={self.test_view.get_blt_calls()}, expected=[{expected_call}]",
                )

    def test_draw_calculates_pixel_position(self):
        """col/row からピクセル座標が計算されること"""
        ROW_STEP = self.GRID_H - self.VERTICAL_OFFSET  # 行間 = 15 - 7 = 8px
        cases = [
            # (case, col, row, expected_px, expected_py)
            # 全列共通: py = (GRID_H - VERTICAL_OFFSET) * row
            ("col_1_row_0", 1, 0, 1 * self.GRID_W, ROW_STEP * 0),
            ("col_0_row_1", 0, 1, 0 * self.GRID_W, ROW_STEP * 1),
            ("col_3_row_2", 3, 2, 3 * self.GRID_W, ROW_STEP * 2),
        ]
        for case, col, row, expected_px, expected_py in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw(col, row, 0, 0)
                actual_call = self.test_view.get_blt_calls()[0]
                # ("draw_blt", x, y, img, u, v, w, h, colkey)
                actual_x, actual_y = actual_call[1], actual_call[2]
                self.assertEqual(expected_px, actual_x, f"{case}: x")
                self.assertEqual(expected_py, actual_y, f"{case}: y")

    def test_draw_flips_horizontally_for_odd_col_row_sum(self):
        """(col+row) が奇数のとき w が負になること（水平反転）"""
        cases = [
            # (case, col, row, expected_w)
            ("even_sum_col0_row0", 0, 0, self.GRID_W),  # 0+0=0 偶数 → 正方向
            ("odd_sum_col1_row0", 1, 0, -self.GRID_W),  # 1+0=1 奇数 → 反転
            ("odd_sum_col0_row1", 0, 1, -self.GRID_W),  # 0+1=1 奇数 → 反転
            ("even_sum_col1_row1", 1, 1, self.GRID_W),  # 1+1=2 偶数 → 正方向
        ]
        for case, col, row, expected_w in cases:
            with self.subTest(case=case):
                self.test_view.get_blt_calls().clear()
                self.grid_view.draw(col, row, 0, 0)
                actual_call = self.test_view.get_blt_calls()[0]
                # ("draw_blt", x, y, img, u, v, w, h, colkey)
                actual_w = actual_call[6]
                self.assertEqual(expected_w, actual_w, f"{case}: w")


if __name__ == "__main__":
    unittest.main()
