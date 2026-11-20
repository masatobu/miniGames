import unittest

from test.fake_view import FakeView

from src import drawing, screen
from src.garage import Garage
from src.resource import Component, Resource

PANEL_RECT = (screen.PANEL_X, screen.PANEL_Y, screen.PANEL_W, screen.PANEL_H)


def draw(garage=None, turn=1, max_turn=10):
    """garage の状態でテーブルを描き、記録した View を返す。"""
    view = FakeView()
    drawing.draw_table(view, garage or Garage(), turn, max_turn)
    return view


# 画像（icon.pyxres）の単色の色番号（透過色 0 の上に、この色で描かれている）
IMAGE_COLOR = screen.COLOR_LAVENDER
COMPONENT_IMAGES = {
    Component.ENGINE: "engine",
    Component.GUN: "gun",
    Component.BODY: "body",
}
KIND_IMAGES = {1: "things", 2: "star", 3: "bolt"}


def icon_at(view, x, y):
    """位置 (x, y) に描かれたアイコンの (u, v, 色) を返す。

    pal(画像の色, 色) → blt → pal() の並びで描かれていることも検証する。
    アイコンが描かれていなければ None。
    """
    for i, call in enumerate(view.calls):
        if call[:3] == ("blt", x, y):
            _, _, _, u, v, w, h, colkey = call
            assert (w, h, colkey) == (
                screen.ICON_CELL,
                screen.ICON_CELL,
                screen.IMAGE_COLKEY,
            ), call
            assert view.calls[i - 1][:2] == ("pal", IMAGE_COLOR), view.calls[i - 1]
            assert view.calls[i + 1] == ("pal",), view.calls[i + 1]
            return u, v, view.calls[i - 1][2]
    return None


def resource_icon(resource):
    """リソースを 1 つだけ ENGINE の枠 1 に置いたときの、そのセルのアイコン。"""
    garage = Garage()
    garage.boxes[Component.ENGINE][0] = resource
    x, y = screen.box_pos(Component.ENGINE, 0)
    return icon_at(draw(garage), x, y)


class TestTableLayout(unittest.TestCase):
    def test_table_is_below_field(self):
        """FR1.1: テーブルの図形・画像はフィールド（上 30%）に食い込まない"""
        view = draw()
        field_h = screen.SCREEN_H * 3 // 10
        self.assertEqual(field_h, screen.TABLE_Y)
        for call in view.calls:
            for _, py in FakeView.points(call) or []:
                self.assertGreaterEqual(py, screen.TABLE_Y, call)
            if call[0] == "blt":
                self.assertGreaterEqual(call[2], screen.TABLE_Y, call)


class TestComponentIcons(unittest.TestCase):
    def test_rows_are_engine_gun_body(self):
        """FR3.1: 部品のアイコンは上から ENGINE、GUN、BODY の 3 行で、同じ列に並ぶ"""
        garage = Garage()
        garage.lv[Component.ENGINE] = 1
        garage.lv[Component.GUN] = 2
        garage.lv[Component.BODY] = 3
        view = draw(garage)
        for comp, lv in zip(Component.tuned(), (1, 2, 3)):
            u, v = screen.ICON_UV[COMPONENT_IMAGES[comp]]
            expected = (u, v, screen.LEVEL_COLORS[lv - 1])
            self.assertEqual(expected, icon_at(view, *screen.icon_pos(comp)), comp)
        ys = [screen.icon_pos(c)[1] for c in Component.tuned()]
        self.assertEqual(sorted(ys), ys)
        self.assertEqual(3, len(set(ys)))
        self.assertEqual(1, len({screen.icon_pos(c)[0] for c in Component.tuned()}))

    def test_icon_color_by_level(self):
        """FR1.2: 部品のレベル 1〜4 で、アイコンの色が変わる"""
        for lv in range(1, 5):
            with self.subTest(lv=lv):
                garage = Garage()
                garage.lv[Component.GUN] = lv
                icon = icon_at(draw(garage), *screen.icon_pos(Component.GUN))
                self.assertEqual(screen.LEVEL_COLORS[lv - 1], icon[2])

    def test_icon_image_by_component(self):
        """FR1.1: 部品の種類で、アイコンの画像（engine・gun・body）が変わる"""
        view = draw()
        images = [icon_at(view, *screen.icon_pos(c))[:2] for c in Component.tuned()]
        self.assertEqual(3, len(set(images)))

    def test_palette_is_restored_after_each_icon(self):
        """NFR4: 色の入れ替えは、アイコンごとに元へ戻し、他の描画へ漏らさない"""
        calls = draw().calls
        pal_sets = [c for c in calls if c[0] == "pal" and len(c) == 3]
        pal_resets = [c for c in calls if c == ("pal",)]
        blts = [c for c in calls if c[0] == "blt"]
        self.assertTrue(blts)
        self.assertEqual(len(blts), len(pal_sets))
        self.assertEqual(len(blts), len(pal_resets))


class TestResourceIcons(unittest.TestCase):
    def test_resource_color_by_rank(self):
        """FR2.1: リソースは、ランクの色（BRONZE=銅、SILVER=銀、GOLD=金）で描かれる"""
        for res in Resource.avails():
            with self.subTest(res=res):
                rank = Resource.get_rank(res)
                self.assertEqual(screen.RANK_COLORS[rank], resource_icon(res)[2])

    def test_resource_image_by_kind(self):
        """FR2.1: 種類（THINGS・STAR・BOLT）ごとの画像で描かれる"""
        for res in Resource.avails():
            with self.subTest(res=res):
                uv = screen.ICON_UV[KIND_IMAGES[res.value[0] // 10]]
                self.assertEqual(uv, resource_icon(res)[:2])

    def test_empty_box_draws_dark_mask_image(self):
        """FR2.2: 空の枠は、その枠が受け入れる種類の画像を、暗い色で描く"""
        view = draw()
        for comp in Component.tuned():
            for idx, mask in enumerate(comp.value):
                with self.subTest(comp=comp, idx=idx):
                    uv = screen.ICON_UV[KIND_IMAGES[mask.value // 10]]
                    expected = (*uv, screen.EMPTY_COLOR)
                    self.assertEqual(
                        expected, icon_at(view, *screen.box_pos(comp, idx))
                    )

    def test_no_shape_is_left_in_icon_cells(self):
        """FR3: アイコンのセルに、図形（矩形・三角形・線）は描かれない（枠の背景の四角を除く）"""
        garage = Garage()
        garage.boxes[Component.ENGINE][0] = Resource.STAR_GOLD
        view = draw(garage)
        cells = [screen.icon_pos(c) for c in Component.tuned()]
        cells += [screen.box_pos(c, i) for c in Component.tuned() for i in range(2)]
        for x, y in cells:
            bg = ("fill_rect", x, y, screen.ICON_SIZE, screen.ICON_SIZE, 13)
            shapes = [s for s in view.shapes_in(x, y, screen.ICON_SIZE) if s != bg]
            self.assertEqual([], shapes, (x, y))


class TestSlotBackground(unittest.TestCase):
    def test_each_box_has_color_13_background_before_icon(self):
        """FR1.3: 部品の枠 6 個それぞれに、ICON_SIZE 四方の色 13 の四角を、アイコンより先に描く"""
        garage = Garage()
        garage.boxes[Component.ENGINE][0] = Resource.STAR_GOLD
        view = draw(garage)
        size = screen.ICON_SIZE
        for comp in Component.tuned():
            for idx in range(2):
                x, y = screen.box_pos(comp, idx)
                with self.subTest(comp=comp, idx=idx):
                    bg = ("fill_rect", x, y, size, size, 13)
                    self.assertIn(bg, view.calls)
                    icon = next(
                        i for i, c in enumerate(view.calls) if c[:3] == ("blt", x, y)
                    )
                    self.assertLess(view.calls.index(bg), icon)


class TestSlotCentering(unittest.TestCase):
    def test_icon_is_centered_in_the_box(self):
        """枠の大きさはアイコンの画像と同じ大きさなので、アイコンは枠の中心に来る（左上にずれない）"""
        self.assertEqual(screen.ICON_CELL, screen.ICON_SIZE)
        garage = Garage()
        garage.boxes[Component.ENGINE][0] = Resource.STAR_GOLD
        view = draw(garage)
        x, y = screen.box_pos(Component.ENGINE, 0)
        bg = ("fill_rect", x, y, screen.ICON_SIZE, screen.ICON_SIZE, 13)
        self.assertIn(bg, view.calls)
        self.assertIsNotNone(icon_at(view, x, y))


class TestTopAlignment(unittest.TestCase):
    def test_top_box_row_top_aligns_with_stock_panel_top(self):
        """最上位の部品枠の上端は、ストックのパネルの上端と揃う"""
        top_row = min(screen.box_pos(comp, 0)[1] for comp in Component.tuned())
        self.assertEqual(screen.PANEL_Y, top_row)
        view = draw()
        panel = ("fill_rect", *PANEL_RECT, screen.PANEL_COLOR)
        bg = ("fill_rect", *screen.box_pos(Component.ENGINE, 0), 16, 16, 13)
        self.assertEqual(panel[2], bg[2])
        self.assertIn(panel, view.calls)
        self.assertIn(bg, view.calls)


class TestButtonCentering(unittest.TestCase):
    def test_button_is_horizontally_centered_on_the_turn_bar(self):
        """決定ボタンの横方向の中心は、残りターンのバーの横方向の中心と同じ"""
        bar_center = screen.TURN_BAR_X + screen.TURN_BAR_W // 2
        x, _, w, _ = screen.button_frame_rect()
        self.assertEqual(bar_center, x + w // 2)
        view = draw()
        frame = ("fill_rect", *screen.button_frame_rect(), screen.BUTTON_BORDER_COLOR)
        self.assertIn(frame, view.calls)


class TestBottomAlignment(unittest.TestCase):
    def test_button_bottom_aligns_with_stock_panel_bottom(self):
        """決定ボタンの下端は、ストックのパネルの下端と揃う"""
        _, y, _, h = screen.button_frame_rect()
        self.assertEqual(screen.PANEL_Y + screen.PANEL_H, y + h)

    def test_turn_bar_keeps_its_gap_above_the_button(self):
        """バーとボタンは一緒に上へずらすので、バーの下端とボタンの上端の間隔は変わらない（17 ピクセル）"""
        _, y, _, _ = screen.button_frame_rect()
        self.assertEqual(17, y - (screen.TURN_BAR_Y + screen.TURN_BAR_H))


class TestStock(unittest.TestCase):
    def test_panel_is_drawn(self):
        """FR4.1: テーブルの右側に、濃い灰色の縦長のパネルを描く"""
        view = draw()
        panel = (
            "fill_rect",
            *PANEL_RECT,
            13,
        )  # パネルは色 13（テーブルの背景と入れ替え）
        self.assertIn(panel, view.calls)
        self.assertGreater(screen.PANEL_H, screen.PANEL_W)

    def test_stock_resources_top_down_and_empty_slots_blank(self):
        """FR4.2: ストックのリソースを上から順に並べ、空の枠には何も描かない"""
        garage = Garage()
        garage.set_stock([Resource.STAR_GOLD, Resource.BOLT_BRONZE])
        view = draw(garage)
        for idx in range(len(Component.STOCK.value)):
            x, y = screen.stock_pos(idx)
            icon = icon_at(view, x, y)
            with self.subTest(idx=idx):
                if idx < 2:
                    res = garage.boxes[Component.STOCK][idx]
                    uv = screen.ICON_UV[KIND_IMAGES[res.value[0] // 10]]
                    rank = Resource.get_rank(res)
                    self.assertEqual((*uv, screen.RANK_COLORS[rank]), icon)
                else:
                    self.assertIsNone(icon)
        ys = [screen.stock_pos(i)[1] for i in range(5)]
        self.assertEqual(sorted(ys), ys)


class TestStatus(unittest.TestCase):
    def test_no_status_text(self):
        """FR1.1・FR2.1: `Lv:N` も `N/10` も、文字では描かない"""
        view = draw(turn=4, max_turn=10)
        self.assertEqual([], [c for c in view.calls if c[0] == "draw_text"])

    def test_turn_bar_frame_and_fill(self):
        """FR2.1: 枠（全体）→ 内側 → 四角（残りターン分）の順に、左下へ描く"""
        view = draw(turn=4, max_turn=10)
        x, y, w, h = (
            screen.TURN_BAR_X,
            screen.TURN_BAR_Y,
            screen.TURN_BAR_W,
            screen.TURN_BAR_H,
        )
        ix, iy, iw, ih = screen.turn_bar_inner_rect()
        fill_w = (
            iw * (10 - 4) // 9
        )  # 残り 6 ターン（開始のターン 1 で満タン、ターン 10 で空）
        frame = ("fill_rect", x, y, w, h, screen.TURN_BAR_FRAME_COLOR)
        inner = ("fill_rect", ix, iy, iw, ih, screen.TURN_BAR_BACK_COLOR)
        fill = ("fill_rect", ix, iy, fill_w, ih, screen.TURN_BAR_FILL_COLOR)
        for call in (frame, inner, fill):
            self.assertIn(call, view.calls)
        self.assertLess(view.calls.index(frame), view.calls.index(inner))
        self.assertLess(view.calls.index(inner), view.calls.index(fill))

    def test_turn_bar_shrinks_from_right_to_left(self):
        """FR2.2・FR2.3: 開始（ターン 1）で内側いっぱい、進むほど左端を固定して短くなり、10 で四角を描かない"""
        ix, iy, iw, ih = screen.turn_bar_inner_rect()

        def fills(turn):
            view = draw(turn=turn, max_turn=10)
            return [
                c
                for c in view.calls
                if c[0] == "fill_rect"
                and c[5] == screen.TURN_BAR_FILL_COLOR
                and c[1] == ix
                and c[2] == iy
                and c[4] == ih
            ]

        self.assertEqual(
            [("fill_rect", ix, iy, iw, ih, screen.TURN_BAR_FILL_COLOR)], fills(1)
        )
        self.assertEqual(
            [("fill_rect", ix, iy, iw * 5 // 9, ih, screen.TURN_BAR_FILL_COLOR)],
            fills(5),
        )
        self.assertEqual([], fills(10))

    def test_execute_button_has_filled_frame_around_icon(self):
        """FR1.4: 決定ボタンの画像を、枠と塗りつぶしの四角が囲む（枠 → 面 → 画像の順）"""
        view = draw()
        x, y, w, h = screen.button_frame_rect()
        b = screen.BUTTON_BORDER
        outer = ("fill_rect", x, y, w, h, screen.BUTTON_BORDER_COLOR)
        face = ("fill_rect", x + b, y + b, w - 2 * b, h - 2 * b, screen.BUTTON_COLOR)
        self.assertIn(outer, view.calls)
        self.assertIn(face, view.calls)
        icon_x, icon_y = screen.button_icon_pos()
        icon = next(
            i for i, c in enumerate(view.calls) if c[:3] == ("blt", icon_x, icon_y)
        )
        self.assertLess(view.calls.index(outer), view.calls.index(face))
        self.assertLess(view.calls.index(face), icon)

    def test_execute_button_frame_is_centered_and_contains_icon(self):
        """FR1.4: 枠は BUTTON_X・BUTTON_Y を中心にし、画像（16 × 16）を余白つきで囲む"""
        x, y, w, h = screen.button_frame_rect()
        self.assertEqual((screen.BUTTON_X, screen.BUTTON_Y), (x + w // 2, y + h // 2))
        icon_x, icon_y = screen.button_icon_pos()
        self.assertLess(x + screen.BUTTON_BORDER, icon_x)
        self.assertLess(y + screen.BUTTON_BORDER, icon_y)
        self.assertGreater(x + w - screen.BUTTON_BORDER, icon_x + screen.ICON_CELL)
        self.assertGreater(y + h - screen.BUTTON_BORDER, icon_y + screen.ICON_CELL)

    def test_execute_button_face_differs_from_background(self):
        """FR1.4: 枠の中の塗りつぶしは、テーブルの背景・ストックのパネルと違う色（ボタンだとわかる）"""
        self.assertNotEqual(screen.TABLE_COLOR, screen.BUTTON_COLOR)
        self.assertNotEqual(screen.TABLE_COLOR, screen.BUTTON_BORDER_COLOR)
        self.assertNotEqual(screen.BUTTON_BORDER_COLOR, screen.BUTTON_COLOR)
        # 画像（色 BUTTON_ICON_COLOR）は、面の色の上で見える
        self.assertNotEqual(screen.BUTTON_ICON_COLOR, screen.BUTTON_COLOR)

    def test_execute_button_is_image_centered_on_button(self):
        """FR1.1・FR1.2: 決定ボタンは、画像 execute を BUTTON_X・BUTTON_Y を中心に、白で描く"""
        view = draw()
        # 16 × 16 の画像の左上 = 中心 - セルの大きさの半分
        x = screen.BUTTON_X - screen.ICON_CELL // 2
        y = screen.BUTTON_Y - screen.ICON_CELL // 2
        u, v = screen.ICON_UV["execute"]
        self.assertEqual((u, v, screen.BUTTON_ICON_COLOR), icon_at(view, x, y))
        self.assertEqual((x, y), screen.button_icon_pos())

    def test_execute_button_draws_no_shapes(self):
        """FR4: 図形による決定ボタン（円・チェックの線）は、画像と二重に描かない"""
        view = draw()
        x, y = screen.button_icon_pos()
        shapes = view.shapes_in(x, y, screen.ICON_CELL)
        self.assertEqual([], [c for c in shapes if c[0] != "fill_rect"])

    def test_execute_button_image_size_is_a_parameter(self):
        """FR5: 画像のセルの大きさは引数で受け、8 × 8 の画像も同じ関数で描ける"""
        view = FakeView()
        u, v = screen.FIELD_UV["ship"]
        drawing.draw_image(view, u, v, 10, 20, screen.FIELD_CELL, screen.COLOR_RED)
        self.assertEqual(
            [
                ("pal", drawing.IMAGE_COLOR, screen.COLOR_RED),
                ("blt", 10, 20, u, v, screen.FIELD_CELL, screen.FIELD_CELL, 0),
                ("pal",),
            ],
            view.calls,
        )


class TestSelector(unittest.TestCase):
    def test_selector_draws_red_square_outline(self):
        """FR1.1, FR1.2: 選択中の枠に、アイコンの 16 × 16 の外周に沿う赤い 1 ピクセルの枠線を描く"""
        size, color = screen.ICON_SIZE, screen.SELECTOR_COLOR
        for point in ((Component.GUN, 1), (Component.STOCK, 2)):
            with self.subTest(point=point):
                view = FakeView()
                drawing.draw_selector(view, point)
                x, y = (
                    screen.stock_pos(point[1])
                    if point[0] == Component.STOCK
                    else screen.box_pos(*point)
                )
                self.assertEqual(
                    [
                        ("fill_rect", x, y, size, 1, color),  # 上の辺
                        ("fill_rect", x, y + size - 1, size, 1, color),  # 下の辺
                        ("fill_rect", x, y + 1, 1, size - 2, color),  # 左の辺
                        ("fill_rect", x + size - 1, y + 1, 1, size - 2, color),  # 右
                    ],
                    view.calls,
                )

    def test_selector_leaves_the_inside_untouched(self):
        """FR1.3: 枠の内側を塗らず、半透明も使わない（アイコンが元の色で見える）"""
        view = FakeView()
        drawing.draw_selector(view, (Component.ENGINE, 0))
        x, y = screen.box_pos(Component.ENGINE, 0)
        self.assertFalse([c for c in view.calls if c[0] == "set_alpha"])
        for call in view.calls:
            _, cx, cy, w, h, _ = call
            self.assertTrue(w == 1 or h == 1, call)  # どれも 1 ピクセル幅の線
            self.assertTrue(x <= cx and cx + w <= x + screen.ICON_SIZE, call)
            self.assertTrue(y <= cy and cy + h <= y + screen.ICON_SIZE, call)

    def test_no_selection_draws_nothing(self):
        """FR1.4: 選択が無い（None）ときは何も描かない"""
        view = FakeView()
        drawing.draw_selector(view, None)
        self.assertEqual([], view.calls)


class TestGameOverMenu(unittest.TestCase):
    """ID-009: ゲームオーバーのメニュー（暗転・枠・タイトル・撃破数・New Game）。"""

    def setUp(self):
        self.kills = 37
        self.view = FakeView()
        drawing.draw_game_over_menu(self.view, self.kills)
        self.calls = self.view.calls

    def test_background_is_dimmed_with_alpha_restored(self):
        """FR2: 背後の画面を、半透明の黒で暗くし、描いたあとは半透明を戻す"""
        dim = ("fill_rect", 0, 0, screen.SCREEN_W, screen.SCREEN_H, screen.DIM_COLOR)
        self.assertEqual(("set_alpha", screen.DIM_ALPHA), self.calls[0])
        self.assertEqual(dim, self.calls[1])
        self.assertEqual(("set_alpha", 1.0), self.calls[2])

    def test_frame_is_centered_on_screen(self):
        """FR2: メニューの枠は、画面の中央に重なる（暗転のあとに描く）"""
        frame = ("fill_rect", *screen.MENU_RECT, screen.MENU_COLOR)
        self.assertIn(frame, self.calls)
        x, y, w, h = screen.MENU_RECT
        self.assertEqual(screen.SCREEN_W, 2 * x + w)  # 左右の余白が等しい
        self.assertEqual(screen.SCREEN_H, 2 * y + h)  # 上下の余白が等しい

    def test_title_kills_and_button_text(self):
        """FR2.2: タイトル・撃破数・ボタンの文字列を、ASCII だけで描く"""
        texts = [c[3] for c in self.calls if c[0] == "draw_text"]
        self.assertEqual(["Game Over", f"Kills: {self.kills}", "New Game"], texts)
        self.assertTrue(all(t.isascii() for t in texts))

    def test_new_game_button_is_inside_frame(self):
        """FR2: New Game のボタンを、枠の内側に描く"""
        button = ("fill_rect", *screen.NEW_GAME_RECT, screen.NEW_GAME_COLOR)
        self.assertIn(button, self.calls)
        fx, fy, fw, fh = screen.MENU_RECT
        bx, by, bw, bh = screen.NEW_GAME_RECT
        self.assertTrue(fx <= bx and bx + bw <= fx + fw)
        self.assertTrue(fy <= by and by + bh <= fy + fh)


if __name__ == "__main__":
    unittest.main()
