import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from fish import FishSize  # pylint: disable=C0413
from main import (  # pylint: disable=C0413
    PyxelFishView,
)


class TestView:
    """IView のテスト用モック。get_frame() の制御が可能。"""

    def __init__(self):
        self._frame = 0
        self.blt_calls = []

    def get_frame(self):
        return self._frame

    def set_frame(self, frame):
        self._frame = frame

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.blt_calls.append(
            dict(x=x, y=y, img=img, u=u, v=v, w=w, h=h, colkey=colkey)
        )

    def draw_text(self, x, y, text):
        pass

    def draw_line(self, x1, y1, x2, y2, color):
        pass

    def draw_rectb(self, x, y, w, h, color):
        pass

    def draw_rect(self, x, y, w, h, color):
        pass


class TestPyxelFishViewAnimationPattern(unittest.TestCase):
    """PyxelFishView のアニメーションフレームパターンテスト。

    u = [8, 16, 8, 24] の 4 コマループを ANIM_INTERVAL フレームごとに切り替える。
    """

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.get_frame.side_effect = self.test_view.get_frame
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelFishView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.fish_view = PyxelFishView()

    def tearDown(self):
        self.patcher.stop()

    def test_animation_frame_pattern(self):
        """ANIM_INTERVAL フレームごとに u が [8, 16, 8, 24] で切り替わること。"""
        interval = PyxelFishView.ANIM_INTERVAL
        # (コマ番号, 期待 u 値)
        expected_u_per_frame = [8, 16, 8, 24]
        for frame_index, expected_u in enumerate(expected_u_per_frame):
            for offset in [0, 1]:
                frame_count = frame_index * interval + offset
                with self.subTest(frame_index=frame_index, frame_count=frame_count):
                    self.test_view.set_frame(frame_count)
                    self.test_view.blt_calls.clear()
                    self.fish_view.draw_fish(0, 0, FishSize.SMALL, 1.0, False)
                    self.assertEqual(len(self.test_view.blt_calls), 1)
                    actual_u = self.test_view.blt_calls[0]["u"]
                    self.assertEqual(
                        expected_u,
                        actual_u,
                        f"frame_count={frame_count}: u={actual_u}, expected={expected_u}",
                    )


class TestPyxelFishViewTileRow(unittest.TestCase):
    """FishSize ごとに v（タイル行）が正しく決まること。"""

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.get_frame.return_value = 0
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelFishView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.fish_view = PyxelFishView()

    def tearDown(self):
        self.patcher.stop()

    def test_fish_size_determines_tile_row(self):
        """各 FishSize に対応する v 値: SMALL=0, MEDIUM_S=8, MEDIUM_L=16, LARGE=24。"""
        cases = [
            (FishSize.SMALL, 0),
            (FishSize.MEDIUM_S, 8),
            (FishSize.MEDIUM_L, 16),
            (FishSize.LARGE, 24),
        ]
        for fish_size, expected_v in cases:
            with self.subTest(fish_size=fish_size):
                self.test_view.blt_calls.clear()
                self.fish_view.draw_fish(0, 0, fish_size, 1.0, False)
                self.assertEqual(len(self.test_view.blt_calls), 1)
                actual_v = self.test_view.blt_calls[0]["v"]
                self.assertEqual(
                    expected_v,
                    actual_v,
                    f"{fish_size}: v={actual_v}, expected={expected_v}",
                )


class TestPyxelFishViewDirection(unittest.TestCase):
    """vx の符号によって描画の左右反転（w の符号）が決まること。"""

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.get_frame.return_value = 0
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelFishView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.fish_view = PyxelFishView()

    def tearDown(self):
        self.patcher.stop()

    def test_fish_facing_direction(self):
        """vx > 0（右向き）→ w が正（反転なし）、vx < 0（左向き）→ w が負（左右反転）。"""
        tile_size = PyxelFishView.TILE_SIZE
        cases = [
            ("right", 1.0, tile_size),  # 右向き移動 → 反転なし（画像が右向き基準）
            ("left", -1.0, -tile_size),  # 左向き移動 → 左右反転して左向きに見せる
        ]
        for direction, vx, expected_w in cases:
            with self.subTest(direction=direction):
                self.test_view.blt_calls.clear()
                self.fish_view.draw_fish(0, 0, FishSize.SMALL, vx, False)
                self.assertEqual(len(self.test_view.blt_calls), 1)
                actual_w = self.test_view.blt_calls[0]["w"]
                self.assertEqual(
                    expected_w,
                    actual_w,
                    f"vx={vx}: w={actual_w}, expected={expected_w}",
                )


class TestPyxelFishViewEscapeAnim(unittest.TestCase):
    """逃げ状態（is_hit=True）のアニメーション高速化テスト。"""

    def setUp(self):
        self.test_view = TestView()
        self.mock_pyxel_view = MagicMock()
        self.mock_pyxel_view.get_frame.side_effect = self.test_view.get_frame
        self.mock_pyxel_view.draw_blt.side_effect = self.test_view.draw_blt
        self.patcher = patch.object(
            PyxelFishView, "_create_view", return_value=self.mock_pyxel_view
        )
        self.patcher.start()
        self.fish_view = PyxelFishView()

    def tearDown(self):
        self.patcher.stop()

    def test_escape_anim_uses_faster_interval(self):
        """is_hit の値によって異なるアニメーション間隔が使われること。

        通常（is_hit=False）: ANIM_INTERVAL=8 でコマ切替
        逃げ（is_hit=True）:  ESCAPE_ANIM_INTERVAL=3 でコマ切替
        """
        cases = [
            # (frame, is_hit, expected_u)
            (0, False, 8),  # 通常: 0//8%4=0 → ANIM_PATTERN[0]=0 → u=(1+0)*8=8
            (24, False, 24),  # 通常: 24//8%4=3 → ANIM_PATTERN[3]=2 → u=(1+2)*8=24
            (0, True, 8),  # 逃げ: 0//3%4=0 → ANIM_PATTERN[0]=0 → u=(1+0)*8=8
            (3, True, 16),  # 逃げ: 3//3%4=1 → ANIM_PATTERN[1]=1 → u=(1+1)*8=16
            (
                24,
                True,
                8,
            ),  # 逃げ: 24//3%4=0 → ANIM_PATTERN[0]=0 → u=(1+0)*8=8（通常と異なる）
        ]
        for frame, is_hit, expected_u in cases:
            with self.subTest(frame=frame, is_hit=is_hit):
                self.test_view.set_frame(frame)
                self.test_view.blt_calls.clear()
                self.fish_view.draw_fish(0, 0, FishSize.SMALL, -1, is_hit=is_hit)
                self.assertEqual(len(self.test_view.blt_calls), 1)
                self.assertEqual(self.test_view.blt_calls[0]["u"], expected_u)


if __name__ == "__main__":
    unittest.main()
