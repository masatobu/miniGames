import unittest
from test.recording_view import RecordingView
from src import table_view
from src.table_view import (
    BUTTON_FRAME_PADDING,
    BUTTON_Y,
    CHAR_HEIGHT,
    CHAR_WIDTH,
    COIN_X,
    ICON_SIZE,
    ICON_X,
    POPUP_FILL_COLOR,
    POPUP_FRAME_COLOR,
    POPUP_HEIGHT,
    POPUP_TEXT_COLOR,
    POPUP_Y,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

LINES = {
    "win": ["YOU WIN", "TAP TO RESTART"],
    "lose": ["GAME OVER", "TAP TO RESTART"],
}


def draw(outcome):
    """ポップアップを描き、記録された呼び出しを返す（関数は呼び出し時に引く）。"""
    view = RecordingView()
    table_view.draw_session_popup(view, outcome)
    return view.calls


def texts(calls):
    """text の呼び出しだけを取り出す。"""
    return [c for c in calls if c[0] == "text"]


def fill_rect(calls):
    """塗り（rect）の呼び出しを 1 件取り出す。"""
    rects = [c for c in calls if c[0] == "rect"]
    assert len(rects) == 1
    return rects[0]


class SessionPopupTest(unittest.TestCase):
    def test_none_draws_nothing(self):
        """BR4.1: 結果が無い（継続）ときは何も描かない。"""
        self.assertEqual(draw(None), [])

    def test_win_lines(self):
        """BR4.2: 勝利は YOU WIN と TAP TO RESTART の 2 行を、上から順に描く。"""
        self.assertEqual([c[3] for c in texts(draw("win"))], LINES["win"])

    def test_lose_lines(self):
        """BR4.2: 敗北は GAME OVER と TAP TO RESTART の 2 行を、上から順に描く。"""
        self.assertEqual([c[3] for c in texts(draw("lose"))], LINES["lose"])

    def test_unknown_outcome_raises_without_drawing(self):
        """BR4.3: 未知の値は何も描かずに ValueError にする。"""
        view = RecordingView()
        with self.assertRaises(ValueError):
            table_view.draw_session_popup(view, "draw")
        self.assertEqual(view.calls, [])

    def test_fill_is_centered_on_screen(self):
        """BR4.4: 塗りは画面の水平・垂直の中央にある。"""
        for outcome in LINES:
            _, x, y, w, h, color = fill_rect(draw(outcome))
            self.assertEqual(x, (SCREEN_WIDTH - w) // 2)
            self.assertEqual(y, (SCREEN_HEIGHT - h) // 2)
            self.assertEqual(color, POPUP_FILL_COLOR)

    def test_frame_is_inset_by_one_pixel(self):
        """BR4.4: 枠は塗りの内側 1 ピクセルにある。"""
        calls = draw("win")
        _, x, y, w, h, _ = fill_rect(calls)
        frames = [c for c in calls if c[0] == "rectb"]
        self.assertEqual(
            frames, [("rectb", x + 1, y + 1, w - 2, h - 2, POPUP_FRAME_COLOR)]
        )

    def test_text_is_centered_in_the_popup(self):
        """BR4.4: 各行は塗りの中で水平に、2 行のまとまりは垂直に中央寄せする。"""
        for outcome, lines in LINES.items():
            calls = draw(outcome)
            _, x, y, w, h, _ = fill_rect(calls)
            line_pitch = texts(calls)[1][2] - texts(calls)[0][2]
            block_height = CHAR_HEIGHT + line_pitch
            self.assertEqual(texts(calls)[0][2], y + (h - block_height) // 2)
            for call, line in zip(texts(calls), lines):
                text_width = CHAR_WIDTH * len(line) - 1
                self.assertEqual(call[1], x + (w - text_width) // 2)
                self.assertEqual(call[4], POPUP_TEXT_COLOR)
                # 文字は塗りの枠（内側 1 ピクセル）に収まる
                self.assertGreaterEqual(call[1], x + 2)
                self.assertLessEqual(call[1] + text_width, x + w - 2)

    def test_draw_order_fill_frame_lines(self):
        """BR4.4: 塗り → 枠 → 1 行目 → 2 行目の順に描く。"""
        calls = draw("lose")
        self.assertEqual([c[0] for c in calls], ["rect", "rectb", "text", "text"])

    def test_does_not_cover_icons_coins_buttons_or_top_band(self):
        """BR4.5: アイコンの列・所持コインの列・ボタン・上の帯を隠さない。"""
        for outcome in LINES:
            _, x, y, w, h, _ = fill_rect(draw(outcome))
            self.assertGreater(x, ICON_X + ICON_SIZE)
            self.assertLess(x + w, COIN_X)
            self.assertGreater(y, POPUP_Y + POPUP_HEIGHT)
            self.assertLess(y + h, BUTTON_Y - BUTTON_FRAME_PADDING)

    def test_text_is_uppercase_ascii(self):
        """BR4.6: 文字は大文字の ASCII だけ。"""
        for outcome in LINES:
            for call in texts(draw(outcome)):
                self.assertTrue(call[3].isascii())
                self.assertEqual(call[3], call[3].upper())


if __name__ == "__main__":
    unittest.main()
