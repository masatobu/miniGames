import unittest
from test.recording_view import RecordingView
from src.card_view import (
    BACKGROUND_COLOR,
    CARD_HEIGHT,
    CARD_WIDTH,
    CHAR_WIDTH,
    FRAME_COLOR,
    IMAGE_BANK,
    SYMBOL_SIZE,
    SYMBOL_Y_OFFSET,
    TEXT_Y_OFFSET,
    TRANSPARENT_COLOR,
    CARD_BACK_COLOR,
    draw_card,
    draw_card_back,
)
from src.cards import Card


class TestDrawCard(unittest.TestCase):
    def test_draw_order(self):
        """カード 1 枚で 背景(rect)・枠(rectb)・マーク(blt)・数字(text) が順に描かれること"""
        view = RecordingView()
        draw_card(view, 10, 20, Card(14, "spade"))
        kinds = [call[0] for call in view.calls]
        self.assertEqual(["rect", "rectb", "blt", "text"], kinds, view.calls)

    def test_frame_and_background(self):
        """背景と枠が、指定位置を左上とするカードの大きさで描かれること"""
        view = RecordingView()
        draw_card(view, 10, 20, Card(5, "club"))
        self.assertEqual(
            ("rect", 10, 20, CARD_WIDTH, CARD_HEIGHT, BACKGROUND_COLOR), view.calls[0]
        )
        self.assertEqual(
            ("rectb", 10, 20, CARD_WIDTH, CARD_HEIGHT, FRAME_COLOR), view.calls[1]
        )

    def test_suit_image_coordinates(self):
        """4 つのマークが、それぞれ別の画像座標 (u, v) で枠の内側に描かれること"""
        expected_uv = {
            "spade": (8, 16),
            "club": (16, 16),
            "diamond": (24, 16),
            "heart": (32, 16),
        }
        # マークは横方向に中央（(14 - 8) // 2 = 3）、縦は定数の位置
        symbol_x = 10 + (CARD_WIDTH - SYMBOL_SIZE) // 2
        symbol_y = 20 + SYMBOL_Y_OFFSET
        for suit, (u, v) in expected_uv.items():
            with self.subTest(suit=suit):
                view = RecordingView()
                draw_card(view, 10, 20, Card(5, suit))
                blt = [c for c in view.calls if c[0] == "blt"][0]
                size = (SYMBOL_SIZE, SYMBOL_SIZE)
                expected = ("blt", symbol_x, symbol_y, IMAGE_BANK, u, v, *size)
                self.assertEqual(expected + (TRANSPARENT_COLOR,), blt)
                self.assertLessEqual(symbol_y + SYMBOL_SIZE, 20 + CARD_HEIGHT)

    def test_rank_labels(self):
        """数字が 2〜10 は数字、11〜14 は J・Q・K・A で描かれること"""
        expected = {2: "2", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"}
        for rank, label in expected.items():
            with self.subTest(rank=rank):
                view = RecordingView()
                draw_card(view, 0, 0, Card(rank, "heart"))
                texts = [c[3] for c in view.calls if c[0] == "text"]
                self.assertEqual([label], texts)

    def test_rank_ten_stays_inside_frame(self):
        """10 は 2 文字ぶんの幅が、枠の内側に収まること"""
        view = RecordingView()
        draw_card(view, 10, 20, Card(10, "diamond"))
        text = [c for c in view.calls if c[0] == "text"][0]
        _, text_x, text_y, label, _ = text
        # 文字幅 = 1 文字 4px、最後の文字の右の隙間 1px を除く
        width = CHAR_WIDTH * len(label) - 1
        self.assertEqual(2, len(label))
        self.assertGreaterEqual(text_x, 10)
        self.assertLessEqual(text_x + width, 10 + CARD_WIDTH)
        self.assertEqual(20 + TEXT_Y_OFFSET, text_y)

    def test_text_is_ascii_only(self):
        """描く文字がすべて ASCII であること（Pyxel の標準フォントの制約）"""
        for rank in range(2, 15):
            for suit in ("spade", "heart", "diamond", "club"):
                with self.subTest(rank=rank, suit=suit):
                    view = RecordingView()
                    draw_card(view, 0, 0, Card(rank, suit))
                    texts = [c[3] for c in view.calls if c[0] == "text"]
                    self.assertEqual(1, len(texts), view.calls)
                    self.assertTrue(all(t.isascii() for t in texts), texts)


if __name__ == "__main__":
    unittest.main()


class TestDrawCardBack(unittest.TestCase):
    def test_back_is_filled_and_framed_without_image_or_text(self):
        """裏面は、塗り（色 12）→ 枠（色 0）の図形だけで、カードと同じ大きさに描かれること"""
        view = RecordingView()
        draw_card_back(view, 10, 20)
        self.assertEqual(
            [
                ("rect", 10, 20, CARD_WIDTH, CARD_HEIGHT, 12),
                ("rectb", 10, 20, CARD_WIDTH, CARD_HEIGHT, 0),
            ],
            view.calls,
        )

    def test_back_color_differs_from_face(self):
        """裏面の塗りの色が、表向きの背景の色と違うこと"""
        self.assertNotEqual(BACKGROUND_COLOR, CARD_BACK_COLOR)
