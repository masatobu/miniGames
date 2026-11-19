import unittest

from test.fake_view import FakeView

from src import drawing, screen
from src.field import Field

# 敵の見た目（レベルの境界ごとの色）。要件 FR2.3 の表を (レベル, 色) で並べたもの
ENEMY_COLORS = [
    (1, screen.COLOR_BROWN),
    (4, screen.COLOR_BROWN),
    (5, screen.COLOR_LIGHT_GRAY),
    (9, screen.COLOR_LIGHT_GRAY),
    (10, screen.COLOR_BLUE),
    (14, screen.COLOR_BLUE),
    (15, screen.COLOR_GREEN),
    (19, screen.COLOR_GREEN),
    (20, screen.COLOR_RED),
    (24, screen.COLOR_RED),
    (25, screen.COLOR_BLACK),
    (29, screen.COLOR_BLACK),
    (30, screen.COLOR_BLUE),
    (34, screen.COLOR_BLUE),
    (35, screen.COLOR_GREEN),
    (39, screen.COLOR_GREEN),
    (40, screen.COLOR_YELLOW),
    (44, screen.COLOR_YELLOW),
    (45, screen.COLOR_RED),
    (54, screen.COLOR_RED),
    (55, screen.COLOR_DARK_GRAY),
    (99, screen.COLOR_DARK_GRAY),
]
ENEMY_POS = (screen.SCREEN_W - 40, 20)


def draw_field(level=1, body_level=1, positions=None):
    """フィールドを描き、記録した View を返す。"""
    view = FakeView()
    drawing.draw_field(view, level, body_level, positions or [])
    return view


def enemy_image(level):
    """1 体だけの敵を ENEMY_POS に描いたときの、その敵の (u, v, 大きさ, 色)。"""
    return draw_field(level=level, positions=[ENEMY_POS]).image_at(*ENEMY_POS)


# 敵の見た目の種別（レベルの範囲）と、画像の位置 FIELD_UV の名前。要件 FR3.2 の表
ENEMY_KINDS = [
    (1, "rock"),
    (9, "rock"),
    (10, "fighter"),
    (29, "fighter"),
    (30, "ufo"),
    (99, "ufo"),
]


class TestFieldBackground(unittest.TestCase):
    def test_background_is_navy_over_top_30_percent(self):
        """FR2.1: フィールドの領域（画面の上 30%）を暗い紺色で塗る"""
        view = draw_field()
        self.assertEqual(
            ("fill_rect", 0, 0, screen.SCREEN_W, screen.FIELD_H, screen.COLOR_NAVY),
            view.calls[0],
        )
        self.assertEqual(screen.SCREEN_H * 3 // 10, screen.FIELD_H)


class TestShip(unittest.TestCase):
    def test_ship_image_and_color_by_body_level(self):
        """FR2: 自機は画像 ship (8, 48) を、BODY のレベルの色（1: 青、2: 緑、3: 橙、4: 赤）で描く"""
        u, v = screen.FIELD_UV["ship"]
        for lv, color in zip(range(1, 5), (12, 11, 9, 8)):
            with self.subTest(body_level=lv):
                view = draw_field(body_level=lv)
                self.assertEqual(
                    (u, v, screen.FIELD_CELL, color),
                    view.image_at(screen.SHIP_X, screen.SHIP_Y),
                )
                self.assertEqual(color, screen.LEVEL_COLORS[lv - 1])

    def test_ship_is_at_left_middle(self):
        """FR2: 自機は左端の中段にある（画像の中心が、フィールドの高さの中央）"""
        center_y = screen.SHIP_Y + screen.FIELD_CELL // 2
        self.assertLess(screen.SHIP_X, screen.SCREEN_W // 4)
        self.assertAlmostEqual(screen.FIELD_H / 2, center_y, delta=2)

    def test_ship_draws_no_shapes(self):
        """FR4: 図形による自機は、画像と二重に描かない"""
        view = draw_field()
        self.assertEqual(
            [], view.shapes_in(screen.SHIP_X, screen.SHIP_Y, screen.FIELD_CELL)
        )

    def test_display_size_matches_image_cell(self):
        """FR3.3: 自機・敵の表示の大きさは、画像のセルの大きさ（8）に揃える"""
        self.assertEqual(screen.FIELD_CELL, screen.ENEMY_SIZE)


class TestEnemies(unittest.TestCase):
    def test_enemy_count_and_positions_are_random_in_right_half(self):
        """FR2.3: 敵は最大数（10）ぶん、右半分のフィールド内に、乱数で置く"""
        for rand, (x, y) in (
            (lambda: 0.0, (screen.SCREEN_W // 2, 0)),
            (
                lambda: 0.999999,
                (
                    screen.SCREEN_W - screen.ENEMY_SIZE,
                    screen.FIELD_H - screen.ENEMY_SIZE,
                ),
            ),
        ):
            with self.subTest(x=x):
                positions = drawing.enemy_positions(rand)
                self.assertEqual(Field.MAX_NPC_NUM, len(positions))
                self.assertEqual([(x, y)] * Field.MAX_NPC_NUM, positions)

    def test_every_position_is_drawn(self):
        """FR3: 渡した位置のぶんだけ敵を描く"""
        positions = [(100, 10), (120, 40), (150, 70)]
        view = draw_field(positions=positions)
        for pos in positions:
            self.assertIsNotNone(view.image_at(*pos), pos)

    def test_enemy_color_by_level(self):
        """FR3.2: 敵の色はレベルの境界ごとに変わる"""
        for level, color in ENEMY_COLORS:
            with self.subTest(level=level):
                self.assertEqual(color, enemy_image(level)[3])

    def test_enemy_image_by_level_kind(self):
        """FR3.1: 隕石（1〜9）・敵機（10〜29）・UFO（30 以上）で画像が違う"""
        for level, kind in ENEMY_KINDS:
            with self.subTest(level=level):
                u, v = screen.FIELD_UV[kind]
                self.assertEqual((u, v, screen.FIELD_CELL), enemy_image(level)[:3])

    def test_spare_image_is_never_used(self):
        """FR3.1: 「空き」(16, 48) の画像は、どのレベルでも使わない"""
        for level, _ in ENEMY_COLORS:
            self.assertNotEqual(screen.FIELD_UV["spare"], enemy_image(level)[:2])

    def test_enemies_draw_no_shapes(self):
        """FR4: 図形による敵は、画像と二重に描かない"""
        for level, _ in ENEMY_COLORS:
            view = draw_field(level=level, positions=[ENEMY_POS])
            self.assertEqual([], view.shapes_in(*ENEMY_POS, screen.FIELD_CELL))


if __name__ == "__main__":
    unittest.main()
