import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from button import Button  # pylint: disable=C0413


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

    def draw_text(self, x, y, text):
        self.calls.append(("draw_text", x, y, text))


class TestButtonDraw(unittest.TestCase):
    def test_button_draw_calls_view_in_order(self):
        """Button.draw(view) が draw_rect → draw_rectb → draw_image の順で view を呼ぶこと"""
        view = SimpleView()
        u, v = 8, 0
        button = Button(x=4, y=292, width=24, height=24, icon=(u, v))
        button.draw(view)
        # icon は width/height に対して (24-16)//2 = 4px の padding で中央寄せ
        icon_x = 4 + (24 - 16) // 2  # = 8
        icon_y = 292 + (24 - 16) // 2  # = 296
        expected = [
            ("draw_rect", 4, 292, 24, 24, Button.NORMAL_BG_COLOR),
            ("draw_rectb", 4, 292, 24, 24, 7),
            ("draw_image", icon_x, icon_y, 1, u, v, 16, 16, 0),
        ]
        self.assertEqual(view.calls, expected)


class TestButtonIsClicked(unittest.TestCase):
    def setUp(self):
        # テスト用ボタン: x=10, y=20, width=30, height=15
        # クリック有効範囲（半開区間）: 10 <= mx < 40, 20 <= my < 35
        self.button = Button(x=10, y=20, width=30, height=15, icon=(8, 0))

    def test_button_is_clicked_inside(self):
        """矩形内クリック → True"""
        self.assertTrue(self.button.is_clicked(25, 27))

    def test_button_is_clicked_outside(self):
        """矩形外クリック → False"""
        self.assertFalse(self.button.is_clicked(0, 0))

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


class TestButtonActive(unittest.TestCase):
    def test_is_active(self):
        """set_active 呼び出し列ごとに is_active が期待値と一致すること"""
        cases = [
            # (label, set_active_calls, expected)
            ("初期値は False", [], False),
            ("set_active(True) → True", [True], True),
            ("set_active(True, False) → False に戻る", [True, False], False),
        ]
        for label, calls, expected in cases:
            with self.subTest(label):
                button = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
                for value in calls:
                    button.set_active(value)
                self.assertEqual(expected, button.is_active)


class TestButtonDrawActive(unittest.TestCase):
    """Button.draw() が is_active に応じて背景色を切り替えること"""

    def _draw_bg_color(self, button):
        """button.draw() で最初の draw_rect に渡された color を返す"""
        view = SimpleView()
        button.draw(view)
        _, _, _, _, _, color = view.calls[0]
        return color

    def test_draw_inactive_uses_normal_bg_color(self):
        """inactive 時は NORMAL_BG_COLOR を使うこと"""
        button = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        self.assertEqual(Button.NORMAL_BG_COLOR, self._draw_bg_color(button))

    def test_draw_active_uses_active_bg_color(self):
        """set_active(True) 後は ACTIVE_BG_COLOR を使うこと"""
        button = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        button.set_active(True)
        self.assertEqual(Button.ACTIVE_BG_COLOR, self._draw_bg_color(button))

    def test_draw_deactivated_reverts_to_normal_bg_color(self):
        """set_active(True) 後に set_active(False) すると NORMAL_BG_COLOR に戻ること"""
        button = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        button.set_active(True)
        button.set_active(False)
        self.assertEqual(Button.NORMAL_BG_COLOR, self._draw_bg_color(button))


class TestButtonDrawCount(unittest.TestCase):
    """Button.draw(view, count) の全描画呼び出しを検証"""

    def _expected_calls(self, btn, bg_color, count_label=None):
        """期待される view.calls 列を組み立てる"""
        u, v = btn.icon
        icon_x = btn.x + (btn.width - Button.ICON_SIZE) // 2
        icon_y = btn.y + (btn.height - Button.ICON_SIZE) // 2
        calls = [
            ("draw_rect", btn.x, btn.y, btn.width, btn.height, bg_color),
            ("draw_rectb", btn.x, btn.y, btn.width, btn.height, 7),
            (
                "draw_image",
                icon_x,
                icon_y,
                1,
                u,
                v,
                Button.ICON_SIZE,
                Button.ICON_SIZE,
                0,
            ),
        ]
        if count_label is not None:
            text_x = btn.x + btn.width - 8
            text_y = btn.y + btn.height - 8
            calls.append(("draw_text", text_x, text_y, count_label))
        return calls

    def test_draw_without_count(self):
        """count=None → draw_text なし、NORMAL_BG_COLOR"""
        btn = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        view = SimpleView()
        btn.draw(view)
        self.assertEqual(view.calls, self._expected_calls(btn, Button.NORMAL_BG_COLOR))

    def test_draw_with_count_zero(self):
        """count=0 → DISABLED_BG_COLOR、"0" テキスト描画"""
        btn = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        view = SimpleView()
        btn.draw(view, count=0)
        self.assertEqual(
            view.calls, self._expected_calls(btn, Button.DISABLED_BG_COLOR, "0")
        )

    def test_draw_with_count_single_digit(self):
        """count=3 → NORMAL_BG_COLOR、"3" テキスト描画"""
        btn = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
        view = SimpleView()
        btn.draw(view, count=3)
        self.assertEqual(
            view.calls, self._expected_calls(btn, Button.NORMAL_BG_COLOR, "3")
        )

    def test_draw_with_count_10_or_more_shows_9plus(self):
        """count >= 10 → NORMAL_BG_COLOR、"9+" テキスト描画"""
        for count in [10, 99]:
            with self.subTest(count=count):
                btn = Button(x=4, y=292, width=24, height=24, icon=(8, 0))
                view = SimpleView()
                btn.draw(view, count=count)
                self.assertEqual(
                    view.calls, self._expected_calls(btn, Button.NORMAL_BG_COLOR, "9+")
                )


if __name__ == "__main__":
    unittest.main()
