import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from button import Button, UnitButtonIcon  # pylint: disable=C0413


class SimpleView:
    """Button.draw() 呼び出し検証用の軽量モック（IView非継承、duck typing）"""

    def __init__(self):
        self.calls = []

    def draw_rect(self, x, y, w, h, color):
        self.calls.append(("draw_rect", x, y, w, h, color))

    def draw_rectb(self, x, y, w, h, color):
        self.calls.append(("draw_rectb", x, y, w, h, color))

    def draw_image(self, x, y, img, u, v, w, h, colkey=None):
        self.calls.append(("draw_image", x, y, img, u, v, w, h, colkey))


class TestButtonDraw(unittest.TestCase):
    def test_button_draw_with_icon(self):
        """UnitButtonIcon 指定時は draw_image が呼ばれ、draw_text は呼ばれない"""
        view = SimpleView()
        button = Button(x=6, y=168, width=44, height=12, icon=UnitButtonIcon.LOWER)
        button.draw(view)
        u, v = UnitButtonIcon.LOWER.value  # = (8, 32)
        icon_x = 6 + (44 - 8) // 2  # = 24
        icon_y = 168 + (12 - 8) // 2  # = 170
        expected = [
            ("draw_rect", 6, 168, 44, 12, Button.NORMAL_BG_COLOR),
            ("draw_rectb", 6, 168, 44, 12, 7),
            ("draw_image", icon_x, icon_y, 0, u, v, 8, 8, 0),
        ]
        self.assertEqual(view.calls, expected)


class TestButtonIsClicked(unittest.TestCase):
    def setUp(self):
        # テスト用ボタン: x=10, y=20, width=30, height=15
        # クリック有効範囲（半開区間）: 10 <= mx < 40, 20 <= my < 35
        self.button = Button(x=10, y=20, width=30, height=15, icon=UnitButtonIcon.LOWER)

    def test_button_is_clicked_inside(self):
        """矩形内クリック → True"""
        self.assertTrue(self.button.is_clicked(25, 27))  # ボタン中央付近

    def test_button_is_clicked_outside(self):
        """矩形外クリック → False"""
        self.assertFalse(self.button.is_clicked(0, 0))  # 全く外側

    def test_button_is_clicked_edge_cases(self):
        """境界値テスト（11点パターン: 内側4点 + 外側7点）で半開区間を検証

        ボタン: x=10, y=20, width=30, height=15
          → 右端(exclusive)=40, 下端(exclusive)=35
        """
        test_cases = [
            # 内側4点 → True
            ("top-left corner (inclusive)", 10, 20, True),
            ("top-right inside", 39, 20, True),
            ("bottom-left inside", 10, 34, True),
            ("bottom-right inside", 39, 34, True),
            # 外側7点 → False
            ("left of left edge", 9, 20, False),
            ("at right edge (exclusive)", 40, 20, False),
            ("above top edge", 10, 19, False),
            ("at bottom edge (exclusive)", 10, 35, False),
            ("top-left outer corner", 9, 19, False),
            ("bottom-right outer corner", 40, 35, False),
            ("far below", 25, 40, False),
        ]
        for case_name, mx, my, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(self.button.is_clicked(mx, my), expected)


class TestButtonDrawPressedBehavior(unittest.TestCase):
    def setUp(self):
        self.button = Button(x=6, y=168, width=44, height=12, icon=UnitButtonIcon.LOWER)

    def _bg_color(self, view):
        """draw() 呼び出し結果から draw_rect の背景色を取得するヘルパー"""
        draw_rect_call = next(c for c in view.calls if c[0] == "draw_rect")
        return draw_rect_call[5]  # (name, x, y, w, h, color)

    def test_draw_background_color(self):
        """press()/update() の操作シーケンスに応じた draw() 背景色を検証

        do_press: press() を呼ぶか否か
        update_count: その後 update() を呼ぶ回数
        """
        cases = [
            # (case_name,                         do_press, update_count,           expected_color)
            ("press なし（初期状態）", False, 0, Button.NORMAL_BG_COLOR),
            ("press() 直後", True, 0, Button.PRESSED_BG_COLOR),
            (
                "press() 後タイマー満了",
                True,
                Button.PRESS_DURATION,
                Button.NORMAL_BG_COLOR,
            ),
            ("press() 前に update()（安全確認）", False, 1, Button.NORMAL_BG_COLOR),
        ]
        for case_name, do_press, update_count, expected_color in cases:
            with self.subTest(case=case_name):
                button = Button(
                    x=6, y=168, width=44, height=12, icon=UnitButtonIcon.LOWER
                )
                if do_press:
                    button.press()
                for _ in range(update_count):
                    button.update()
                view = SimpleView()
                button.draw(view)
                self.assertEqual(self._bg_color(view), expected_color)

    def test_press_during_active_timer_resets_timer(self):
        """タイマー残り 1 の状態で press() すると PRESS_DURATION にリセットされ、まだ押下中になる"""
        self.button.press()
        # タイマーを残り 1 まで進める
        for _ in range(Button.PRESS_DURATION - 1):
            self.button.update()
        # 再度 press() → タイマーが PRESS_DURATION にリセットされるはず
        self.button.press()
        # さらに PRESS_DURATION - 1 回 update → リセット済みならタイマー残り 1（まだ押下中）
        for _ in range(Button.PRESS_DURATION - 1):
            self.button.update()
        view = SimpleView()
        self.button.draw(view)
        # リセットされていれば PRESSED_BG_COLOR、されていなければ NORMAL_BG_COLOR
        self.assertEqual(self._bg_color(view), Button.PRESSED_BG_COLOR)


if __name__ == "__main__":
    unittest.main()
