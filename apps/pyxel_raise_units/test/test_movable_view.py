"""PyxelMovableViewの描画テスト（アニメーション処理）

GameCoreからアニメーション処理の責任を分離した結果、
PyxelMovableViewがアニメーションフレーム計算を担当する。
このファイルでユニット・攻撃エフェクトのアニメーション詳細をテストする。
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import IView, PyxelMovableView  # pylint: disable=C0413
from movable import Direct, Side, UnitType  # pylint: disable=C0413


class TestView(IView):
    """IViewのモック実装（テスト用）"""

    def __init__(self):
        self.call_params = []
        self._frame_count = 0

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_rect(self, x, y, w, h, color):
        self.call_params.append(("draw_rect", x, y, w, h, color))

    def draw_rectb(self, x, y, w, h, color):
        self.call_params.append(("draw_rectb", x, y, w, h, color))

    def draw_image(self, x, y, img, u, v, w, h, colkey=None):
        self.call_params.append(("draw_image", x, y, img, u, v, w, h, colkey))

    def clear(self, color):
        self.call_params.append(("clear", color))

    def get_frame(self):
        return self._frame_count

    def set_frame(self, frame):
        """テスト用: フレームカウントを設定"""
        self._frame_count = frame

    def get_call_params(self):
        return self.call_params


class TestPyxelMovableViewAnimation(unittest.TestCase):
    """PyxelMovableViewのアニメーション処理テスト"""

    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        self.patcher_view.stop()

    def test_animation_frame_pattern(self):
        """アニメーションフレームパターンのテスト（移動中/待機中）"""
        unit_view = PyxelMovableView()

        # パラメータ: (direct, frame_cases, description)
        # frame_cases: [(frame, expected_u), ...]
        patterns = [
            # 移動中: 0→1→0→3（5フレームごと）
            (
                Direct.RIGHT,
                [
                    (0, 8),  # frame 0-4: アニメフレーム0 → タイル1 → u=8
                    (5, 16),  # frame 5-9: アニメフレーム1 → タイル2 → u=16
                    (10, 8),  # frame 10-14: アニメフレーム2(=0) → タイル1 → u=8
                    (15, 32),  # frame 15-19: アニメフレーム3 → タイル4 → u=32
                    (20, 8),  # frame 20-24: ループして → タイル1 → u=8
                ],
                "moving",
            ),
            # 待機中: 0→2（10フレームごと）
            (
                Direct.NEUTRAL,
                [
                    (0, 8),  # frame 0-9: アニメフレーム0 → タイル1 → u=8
                    (10, 24),  # frame 10-19: アニメフレーム2 → タイル3 → u=24
                    (20, 8),  # frame 20-29: ループして → タイル1 → u=8
                ],
                "idle",
            ),
        ]

        for direct, frame_cases, desc in patterns:
            for frame, expected_u in frame_cases:
                with self.subTest(pattern=desc, direct=direct, frame=frame):
                    self.test_view.call_params = []
                    self.test_view.set_frame(frame)
                    unit_view.draw_unit(
                        50,
                        100,
                        Side.PLAYER,
                        Direct.RIGHT,
                        direct,
                        False,
                        UnitType.MIDDLE,
                    )

                    expected = [("draw_image", 50, 100, 0, expected_u, 0, 8, 8, 0)]
                    self.assertEqual(self.test_view.get_call_params(), expected)

    def test_unit_appearance(self):
        """ユニットの外観テスト（タイル行: unit_type/side依存、反転: side依存）"""
        unit_view = PyxelMovableView()
        self.test_view.set_frame(0)

        # v = ((unit_type.value - 1) * 2 + (1 if side == ENEMY else 0)) * 8
        # w: PLAYER→+8（face=RIGHT）、ENEMY→-8（face=LEFT）
        type_side_cases = [
            (UnitType.MIDDLE, Side.PLAYER, 0, "middle_player"),
            (UnitType.MIDDLE, Side.ENEMY, 8, "middle_enemy"),
            (UnitType.UPPER, Side.PLAYER, 16, "upper_player"),
            (UnitType.UPPER, Side.ENEMY, 24, "upper_enemy"),
            (UnitType.LOWER, Side.PLAYER, 32, "lower_player"),
            (UnitType.LOWER, Side.ENEMY, 40, "lower_enemy"),
            (UnitType.BASE, Side.PLAYER, 48, "base_player"),
            (UnitType.BASE, Side.ENEMY, 56, "base_enemy"),
        ]

        for unit_type, side, expected_v, desc in type_side_cases:
            with self.subTest(case=desc, unit_type=unit_type, side=side):
                self.test_view.call_params = []
                face = Direct.LEFT if side == Side.ENEMY else Direct.RIGHT
                unit_view.draw_unit(
                    50, 100, side, face, Direct.NEUTRAL, False, unit_type
                )

                expected_w = -8 if side == Side.ENEMY else 8
                expected = [("draw_image", 50, 100, 0, 8, expected_v, expected_w, 8, 0)]
                self.assertEqual(self.test_view.get_call_params(), expected)

    def test_damaged_blink_pattern(self):
        """被弾中は5フレームごとに表示/非表示を切替（点滅）"""
        unit_view = PyxelMovableView()

        # パラメータ: (frame, is_visible, description)
        # 5フレームごとに表示/非表示を切替
        # frame 0-4: 非表示（消えているフェーズ）
        # frame 5-9: 表示
        # frame 10-14: 非表示
        # frame 15-19: 表示
        cases = [
            (0, False, "frame 0-4: hidden"),
            (4, False, "frame 4: still hidden"),
            (5, True, "frame 5-9: visible"),
            (9, True, "frame 9: still visible"),
            (10, False, "frame 10-14: hidden again"),
            (15, True, "frame 15-19: visible again"),
        ]

        for frame, is_visible, desc in cases:
            with self.subTest(frame=frame, expected_visible=is_visible, desc=desc):
                self.test_view.call_params = []
                self.test_view.set_frame(frame)
                # is_damaged=True で呼び出し
                unit_view.draw_unit(
                    50,
                    100,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.RIGHT,
                    True,
                    UnitType.MIDDLE,
                )

                if is_visible:
                    # 表示フレーム: draw_imageが呼ばれる
                    self.assertEqual(len(self.test_view.get_call_params()), 1)
                else:
                    # 非表示フレーム: draw_imageが呼ばれない（描画スキップ）
                    self.assertEqual(len(self.test_view.get_call_params()), 0)

    def test_not_damaged_always_visible(self):
        """被弾していない場合は常に表示"""
        unit_view = PyxelMovableView()

        # 被弾していない場合、どのフレームでも表示される
        for frame in [0, 5, 10, 15]:
            with self.subTest(frame=frame):
                self.test_view.call_params = []
                self.test_view.set_frame(frame)
                # is_damaged=False で呼び出し
                unit_view.draw_unit(
                    50,
                    100,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.RIGHT,
                    False,
                    UnitType.MIDDLE,
                )

                # 常にdraw_imageが呼ばれる
                self.assertEqual(len(self.test_view.get_call_params()), 1)


class TestPyxelMovableViewAttackAnimation(unittest.TestCase):
    """PyxelMovableViewの攻撃エフェクト描画テスト"""

    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        self.patcher_view.stop()

    def test_attack_animation_frame_pattern(self):
        """攻撃アニメーションフレームパターンのテスト（progress依存）"""
        movable_view = PyxelMovableView()

        # パラメータ: (progress, expected_u, description)
        # int(progress * 3) でフレームインデックスを決定、タイルx = 5 + index
        cases = [
            (0.0, 5 * 8, "progress=0.0: タイル5 (u=40)"),
            (0.25, 5 * 8, "progress=0.25: int(0.75)=0 → タイル5 (u=40)"),
            (0.5, 6 * 8, "progress=0.5: int(1.5)=1 → タイル6 (u=48)"),
            (0.75, 7 * 8, "progress=0.75: int(2.25)=2 → タイル7 (u=56)"),
        ]

        for progress, expected_u, desc in cases:
            with self.subTest(progress=progress, desc=desc):
                self.test_view.call_params = []
                movable_view.draw_attack(
                    50, 100, Side.PLAYER, progress, UnitType.MIDDLE
                )

                expected = [("draw_image", 50, 100, 0, expected_u, 0, 8, 8, 0)]
                self.assertEqual(self.test_view.get_call_params(), expected)

    def test_attack_appearance(self):
        """攻撃エフェクトの外観テスト（タイル行: unit_type/side依存、反転: side依存）"""
        movable_view = PyxelMovableView()

        # unit_type と side の組み合わせで expected_v（ピクセル値）を検証
        # v = ((unit_type.value - 1) * 2 + (1 if side == ENEMY else 0)) * 8
        type_side_cases = [
            (UnitType.MIDDLE, Side.PLAYER, 0, "middle_player"),
            (UnitType.MIDDLE, Side.ENEMY, 8, "middle_enemy"),
            (UnitType.UPPER, Side.PLAYER, 16, "upper_player"),
            (UnitType.UPPER, Side.ENEMY, 24, "upper_enemy"),
            (UnitType.LOWER, Side.PLAYER, 32, "lower_player"),
            (UnitType.LOWER, Side.ENEMY, 40, "lower_enemy"),
            (UnitType.BASE, Side.PLAYER, 48, "base_player"),
            (UnitType.BASE, Side.ENEMY, 56, "base_enemy"),
        ]

        for unit_type, side, expected_v, desc in type_side_cases:
            with self.subTest(case=desc, unit_type=unit_type, side=side):
                self.test_view.call_params = []
                movable_view.draw_attack(50, 100, side, 0.0, unit_type)

                # progress=0.0 → u = 5 * 8 = 40
                expected_w = -8 if side == Side.ENEMY else 8
                expected = [
                    ("draw_image", 50, 100, 0, 40, expected_v, expected_w, 8, 0)
                ]
                self.assertEqual(self.test_view.get_call_params(), expected)


if __name__ == "__main__":
    unittest.main()
