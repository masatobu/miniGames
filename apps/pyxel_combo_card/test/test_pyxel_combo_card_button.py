import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from button import Button, ButtonIcon  # pylint: disable=C0413
from main import IView  # pylint: disable=C0413


class TestView(IView):
    """テスト用のViewモック"""

    def __init__(self):
        self.call_params = []

    def text(self, x, y, text, color):
        self.call_params.append(("text", x, y, text, color))

    def rectb(self, x, y, w, h, color):
        self.call_params.append(("rectb", x, y, w, h, color))

    def rect(self, x, y, w, h, color):
        self.call_params.append(("rect", x, y, w, h, color))

    def cls(self, color):
        self.call_params.append(("cls", color))

    def circb(self, x, y, r, color):
        self.call_params.append(("circb", x, y, r, color))

    def trib(self, x1, y1, x2, y2, x3, y3, color):
        self.call_params.append(("trib", x1, y1, x2, y2, x3, y3, color))

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("blt", x, y, img, u, v, w, h, colkey))


class TestButtonDraw(unittest.TestCase):
    """Button.draw() のテスト"""

    def test_button_draw(self):
        """ボタンの描画テスト（枠線とテキスト）のパラメータ化"""
        test_cases = [
            ("ラベルあり", "Test", True),
            ("ラベルが空文字列", "", False),
            ("ラベルがNone", None, False),
        ]

        for case_name, label, should_draw_text in test_cases:
            with self.subTest(case=case_name):
                view = TestView()
                button = Button(x=90, y=100, width=60, height=20, label=label, color=7)

                button.draw(view)

                # 枠線は常に描画される
                expected_calls = [("rectb", 90, 100, 60, 20, 7)]

                # ラベルがある場合のみテキストを描画
                if should_draw_text:
                    # TEXT_OFFSET_X = 3, TEXT_OFFSET_Y = 3
                    expected_calls.append(("text", 93, 103, label, 7))

                self.assertEqual(
                    view.call_params,
                    expected_calls,
                    f"{case_name}: 描画呼び出しが期待と異なります",
                )


class TestButtonDrawWithIcon(unittest.TestCase):
    """Button.draw() のアイコン描画テスト"""

    def test_button_draw_with_icon(self):
        """アイコン付きボタンの描画テスト"""
        view = TestView()
        button = Button(
            x=90, y=100, width=30, height=10, label="", color=7, icon=ButtonIcon.EXCHANGE
        )

        button.draw(view)

        # アイコンサイズ: 16x16px
        # ボタンサイズ: 30x10px
        # アイコン中央配置: x + (30 - 16) // 2 = 90 + 7 = 97
        #                   y + (10 - 16) // 2 = 100 + (-3) = 97
        icon_x = 90 + (30 - 16) // 2
        icon_y = 100 + (10 - 16) // 2

        # EXCHANGE アイコンのタイル座標: (1, 0)
        # タイルサイズ: 8px（icon.pyxres の基本タイルサイズ）
        # 画像座標: u = 1 * 8 = 8, v = 0 * 8 = 0
        img_u = 1 * 8
        img_v = 0 * 8

        expected_calls = [
            ("rectb", 90, 100, 30, 10, 7),  # 枠線
            ("blt", icon_x, icon_y, 0, img_u, img_v, 16, 16, 0),  # アイコン
        ]

        self.assertEqual(
            view.call_params,
            expected_calls,
            "アイコン付きボタンの描画呼び出しが期待と異なります",
        )

    def test_button_draw_icon_and_text_exclusive(self):
        """アイコンとテキストは排他的に描画される"""
        view = TestView()
        button = Button(
            x=90, y=100, width=30, height=10, label="Test", color=7, icon=ButtonIcon.SKIP
        )

        button.draw(view)

        # アイコンが指定されている場合、テキストは描画されない
        icon_x = 90 + (30 - 16) // 2
        icon_y = 100 + (10 - 16) // 2

        # SKIP アイコンのタイル座標: (3, 0)
        # タイルサイズ: 8px（icon.pyxres の基本タイルサイズ）
        img_u = 3 * 8
        img_v = 0 * 8

        expected_calls = [
            ("rectb", 90, 100, 30, 10, 7),  # 枠線
            ("blt", icon_x, icon_y, 0, img_u, img_v, 16, 16, 0),  # アイコン（テキストは描画されない）
        ]

        self.assertEqual(
            view.call_params,
            expected_calls,
            "アイコン指定時はテキストが描画されないはずです",
        )


class TestButtonIsClicked(unittest.TestCase):
    """Button.is_clicked() のテスト"""

    def test_button_is_clicked(self):
        """クリック判定のパラメータ化テスト（inside, outside, edge cases）"""
        button = Button(x=90, y=100, width=60, height=20, label="Test", color=7)

        # ボタン領域: 半開区間 [90, 150), [100, 120)
        btn_x = 90
        btn_y = 100
        btn_right = btn_x + 60  # 150（境界外）
        btn_bottom = btn_y + 20  # 120（境界外）

        test_cases = [
            # 矩形内
            ("矩形内（中央）", (120, 110), True),
            # 矩形外
            ("矩形外（左上）", (80, 90), False),
            ("矩形外（右下）", (160, 130), False),
            # ボタンの四隅（クリックされる）
            ("境界（左上）", (btn_x, btn_y), True),
            ("境界（右上）", (btn_right - 1, btn_y), True),
            ("境界（左下）", (btn_x, btn_bottom - 1), True),
            ("境界（右下）", (btn_right - 1, btn_bottom - 1), True),
            # ボタンの四隅の1px外側（クリックされない）
            ("境界外（左上外）", (btn_x - 1, btn_y), False),
            ("境界外（上外）", (btn_x, btn_y - 1), False),
            ("境界外（右上外）", (btn_right, btn_y), False),
            ("境界外（右外）", (btn_right, btn_bottom - 1), False),
            ("境界外（右下外）", (btn_right, btn_bottom), False),
            ("境界外（下外）", (btn_x, btn_bottom), False),
            ("境界外（左下外）", (btn_x - 1, btn_bottom - 1), False),
        ]

        for case_name, (mouse_x, mouse_y), expected in test_cases:
            with self.subTest(case=case_name):
                result = button.is_clicked(mouse_x, mouse_y)
                self.assertEqual(
                    result,
                    expected,
                    f"{case_name}: ({mouse_x}, {mouse_y}) should be {expected}",
                )


if __name__ == "__main__":
    unittest.main()
