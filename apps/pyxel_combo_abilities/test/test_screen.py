import unittest
from src import screen


class TestImagePositions(unittest.TestCase):
    """FR4: icon.pyxres の画像バンク 0 の中の、各セルの左上 (u, v) を 1 か所で定義する。"""

    def test_icon_cells_are_16_square(self):
        """アイコンのセルは 16 × 16。"""
        self.assertEqual(screen.ICON_CELL, 16)

    def test_icon_positions(self):
        """部品・リソース・決定ボタンのアイコンの位置。"""
        # 画像は、左に 8 画素の余白を空け、16 × 16 のセルを 1 列目から順に並べている
        origin = 8
        cell = 16
        rows = [("engine", "gun", "body"), ("things", "star", "bolt"), ("execute",)]
        expect = {
            name: (origin + cell * col, cell * row)
            for row, names in enumerate(rows)
            for col, name in enumerate(names)
        }
        self.assertEqual(screen.ICON_UV, expect)

    def test_field_cells_are_8_square(self):
        """フィールドのキャラクターのセルは 8 × 8。"""
        self.assertEqual(screen.FIELD_CELL, 8)

    def test_field_positions(self):
        """自機・予備・岩・戦闘機・UFO の位置。"""
        # 4 列目（v = 16 × 3 = 48）に、8 × 8 のセルを 8 画素の余白の右から順に並べている
        origin = 8
        cell = 8
        names = ("ship", "spare", "rock", "fighter", "ufo")
        expect = {name: (origin + cell * col, 48) for col, name in enumerate(names)}
        self.assertEqual(screen.FIELD_UV, expect)

    def test_transparent_color_is_black(self):
        """icon.pyxres の透過色は、色番号 0（アイコンの絵は色 13、背景は 0）。"""
        self.assertEqual(screen.IMAGE_COLKEY, screen.COLOR_BLACK)

    def test_resource_file_name(self):
        """読み込む画像リソースのファイル名。"""
        self.assertEqual(screen.RESOURCE_FILE, "icon.pyxres")


class TestTurnBar(unittest.TestCase):
    """FR2.2・NFR3: 残りターンのバーの寸法（Pyxel に依存しない）。"""

    def test_inner_rect_is_inside_frame_by_border(self):
        """内側の四角は、枠から枠線の太さだけ内側にある。"""
        b = screen.TURN_BAR_BORDER
        x, y, w, h = screen.turn_bar_inner_rect()
        self.assertEqual(
            (
                screen.TURN_BAR_X + b,
                screen.TURN_BAR_Y + b,
                screen.TURN_BAR_W - 2 * b,
                screen.TURN_BAR_H - 2 * b,
            ),
            (x, y, w, h),
        )

    def test_fill_width_is_proportional_to_remaining_turns(self):
        """FR2.2: 長さ = 内側の幅 × (最大ターン − ターン) ÷ (最大ターン − 1)。開始時（ターン 1）で満タン、10 で 0。"""
        inner_w = screen.turn_bar_inner_rect()[2]
        self.assertEqual(inner_w, screen.turn_bar_fill_width(1, 10))
        self.assertEqual(inner_w * 5 // 9, screen.turn_bar_fill_width(5, 10))
        self.assertEqual(0, screen.turn_bar_fill_width(10, 10))
        widths = [screen.turn_bar_fill_width(t, 10) for t in range(1, 11)]
        self.assertEqual(sorted(widths, reverse=True), widths)

    def test_fill_width_stays_in_range(self):
        """範囲外のターン数でも、0〜内側の幅に収める。"""
        inner_w = screen.turn_bar_inner_rect()[2]
        self.assertEqual(0, screen.turn_bar_fill_width(11, 10))
        self.assertEqual(inner_w, screen.turn_bar_fill_width(0, 10))

    def test_bar_margins_are_equal(self):
        """FR2.4: 画面の左端からの余白と、右隣のストックのパネルとの余白が同じ幅。"""
        left = screen.TURN_BAR_X
        right = screen.PANEL_X - (screen.TURN_BAR_X + screen.TURN_BAR_W)
        self.assertEqual(left, right)

    def test_fill_color_is_green(self):
        """FR2.5: 四角は緑、枠は白（重なっても区別できる）。"""
        self.assertEqual(screen.COLOR_GREEN, screen.TURN_BAR_FILL_COLOR)
        self.assertEqual(screen.COLOR_WHITE, screen.TURN_BAR_FRAME_COLOR)

    def test_bar_fits_above_button_and_inside_screen(self):
        """NFR3: バーは決定ボタンの枠より上で、画面と部品の枠・ストックのパネルに重ならない。"""
        self.assertLess(
            screen.TURN_BAR_Y + screen.TURN_BAR_H, screen.button_frame_rect()[1]
        )
        self.assertLess(screen.TURN_BAR_X + screen.TURN_BAR_W, screen.PANEL_X)
        self.assertGreater(screen.TURN_BAR_Y, screen.ROW_Y[2] + screen.ICON_SIZE)
