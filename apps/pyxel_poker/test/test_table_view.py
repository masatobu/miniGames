import unittest
from test.recording_view import RecordingView
from src.card_view import (
    CARD_BACK_COLOR,
    CARD_HEIGHT,
    CARD_WIDTH,
    CHAR_WIDTH,
    IMAGE_BANK,
    TRANSPARENT_COLOR,
)
from src.cards import HAND_SIZE, INITIAL_COINS, Table
from src.table_view import (
    WINNER_FRAME_COLOR,
    WINNER_FRAME_PADDING,
    draw_winner_frame,
    COM_ROW_PITCH,
    COM_ROW_TOP,
    BUTTON_FRAME_COLOR,
    BUTTON_FRAME_PADDING,
    BUTTON_SIZE,
    BUTTON_Y,
    CARD_PITCH,
    CHAR_HEIGHT,
    COIN_TEXT_COLOR,
    COIN_X,
    COM_ICON_UV,
    DROP_BUTTON_UV,
    DROP_BUTTON_X,
    HAND_X,
    HUMAN_ICON_UV,
    ICON_SIZE,
    ICON_X,
    NEW_CARD_FRAME_COLOR,
    POPUP_FILL_COLOR,
    POPUP_FRAME_COLOR,
    POPUP_HEIGHT,
    POPUP_MESSAGES,
    POPUP_TEXT_COLOR,
    POPUP_WIDTH,
    POPUP_X,
    POPUP_Y,
    POT_TEXT_COLOR,
    RAISE_BUTTON_UV,
    RAISE_BUTTON_X,
    ROW_PITCH,
    ROW_TOP,
    SCREEN_COLOR,
    SELECTED_OFFSET,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    draw_buttons,
    draw_player_row,
    draw_pot,
    draw_result_popup,
    draw_table,
    hit_button,
    hit_card,
)

ICON_UVS = (HUMAN_ICON_UV, COM_ICON_UV)
BUTTON_UVS = (DROP_BUTTON_UV, RAISE_BUTTON_UV)


COM_ROWS = 3
# 段の間（カードの下端から次のカードの上端まで）に最低限空ける余白（ピクセル）
MIN_ROW_GAP = 8


def row_top(index):
    """段 index（0 始まり。最後が人間）の上端 y。COM の段は帯の分だけ下にずらして詰める。"""
    if index < COM_ROWS:
        return COM_ROW_TOP + index * COM_ROW_PITCH
    return ROW_TOP + index * ROW_PITCH


def card_frames(calls):
    """カードの背景（rect）の呼び出しだけを取り出す。"""
    return [c for c in calls if c[0] == "rect" and c[3:5] == (CARD_WIDTH, CARD_HEIGHT)]


def blts_with(calls, uvs):
    """画像座標 (u, v) が uvs のどれかである blt だけを取り出す。"""
    return [c for c in calls if c[0] == "blt" and (c[4], c[5]) in uvs]


def extents(call):
    """呼び出しが描く範囲 (左, 上, 右の外, 下の外)。cls は全画面なので None。"""
    kind = call[0]
    if kind in ("rect", "rectb"):
        return call[1], call[2], call[1] + call[3], call[2] + call[4]
    if kind == "blt":
        return call[1], call[2], call[1] + call[6], call[2] + call[7]
    if kind == "text":
        width = CHAR_WIDTH * len(call[3]) - 1
        return call[1], call[2], call[1] + width, call[2] + CHAR_HEIGHT
    return None


class TestDrawTable(unittest.TestCase):
    def setUp(self):
        self.table = Table.deal(0)
        self.view = RecordingView()
        draw_table(self.view, self.table)

    def test_background_then_four_rows_in_order(self):
        """背景を塗ってから、4 人分の段が上から COM・COM・COM・人間の順に描かれること"""
        self.assertEqual(("cls", SCREEN_COLOR), self.view.calls[0])
        icons = blts_with(self.view.calls, ICON_UVS)
        self.assertEqual(4, len(icons), self.view.calls)
        # アイコンの順 = COM, COM, COM, 人間（段の上端が上から下へ増える）
        kinds = [(c[4], c[5]) for c in icons]
        self.assertEqual([COM_ICON_UV] * 3 + [HUMAN_ICON_UV], kinds)
        # 手札の最初のカードの上端 = 段の上端 + 段の中央（(40 - 20) // 2 = 10）
        offset = (ROW_PITCH - CARD_HEIGHT) // 2
        frames = card_frames(self.view.calls)
        for i in range(4):
            with self.subTest(row=i):
                self.assertEqual(row_top(i) + offset, frames[i * HAND_SIZE][2])

    def test_row_has_icon_five_cards_and_coin_text(self):
        """1 段に、アイコン 1 枚・手札 5 枚（左から等間隔）・所持コインの文字があること"""
        player = self.table.players[3]
        view = RecordingView()
        draw_player_row(view, 3, player)
        self.assertEqual(1, len(blts_with(view.calls, ICON_UVS)))
        frames = card_frames(view.calls)
        self.assertEqual(HAND_SIZE, len(frames))
        self.assertEqual(
            [HAND_X + n * CARD_PITCH for n in range(HAND_SIZE)], [c[1] for c in frames]
        )
        # 所持コインの文字 = 数だけ（例: 10。「coin」などの文字は付けない）。縦は段の中央
        coin_text = [c for c in view.calls if c[0] == "text" and c[1] == COIN_X]
        center_y = row_top(3) + (ROW_PITCH - CHAR_HEIGHT) // 2
        expected = ("text", COIN_X, center_y, str(INITIAL_COINS), COIN_TEXT_COLOR)
        self.assertEqual([expected], coin_text)

    def test_row_has_horizontal_room_for_tapping(self):
        """段の横方向に余白があること（カード間 4・アイコンの左と右 8・コインの左 8・画面の右 8 以上）"""
        card_gap_min, margin_min = 4, 8  # 要件 5.1 の指定値
        view = RecordingView()
        draw_player_row(view, 3, self.table.players[3])
        icon = blts_with(view.calls, ICON_UVS)[0]
        frames = card_frames(view.calls)
        xs = [c[1] for c in frames]
        coin = [c for c in view.calls if c[0] == "text" and c[1] == COIN_X][0]
        # 3 桁のコイン（例: 100）でも右に収まる幅 = 4 * 3 - 1 = 11
        three_digits = CHAR_WIDTH * 3 - 1
        icon_right = icon[1] + ICON_SIZE
        last_card_right = xs[-1] + CARD_WIDTH
        checks = {
            "カード間": min(b - a - CARD_WIDTH for a, b in zip(xs, xs[1:]))
            - card_gap_min,
            "アイコンの左": icon[1] - margin_min,
            "アイコンと最初のカードの間": xs[0] - icon_right - margin_min,
            "最後のカードとコインの間": coin[1] - last_card_right - margin_min,
            "画面の右": SCREEN_WIDTH - (coin[1] + three_digits) - margin_min,
        }
        for name, surplus in checks.items():
            with self.subTest(name):
                self.assertGreaterEqual(surplus, 0, checks)

    def test_icon_coordinates(self):
        """COM の段は COM のアイコン、最下段は人間のアイコンが、段の中央に描かれること"""
        icon_offset = (ROW_PITCH - ICON_SIZE) // 2
        for index, uv in enumerate(
            (COM_ICON_UV, COM_ICON_UV, COM_ICON_UV, HUMAN_ICON_UV)
        ):
            with self.subTest(row=index):
                view = RecordingView()
                draw_player_row(view, index, self.table.players[index])
                icon = blts_with(view.calls, ICON_UVS)[0]
                size = (ICON_SIZE, ICON_SIZE)
                expected = ("blt", ICON_X, row_top(index) + icon_offset, IMAGE_BANK)
                self.assertEqual(
                    expected + uv + size + (TRANSPARENT_COLOR,),
                    icon,
                )

    def test_screen_background_is_navy(self):
        """画面の背景色が紺色（Pyxel の色 1）であること（要件 5.1）"""
        # 色番号 1 は要件の指定値（紺色）。定数と、実際の塗りの両方で確認する
        navy = 1
        self.assertEqual(navy, SCREEN_COLOR)
        self.assertEqual(("cls", navy), self.view.calls[0])

    def test_button_icons_have_frame(self):
        """各ボタンのアイコンの周りに、四角形の枠（矩形）が、アイコンより先に描かれること"""
        view = RecordingView()
        draw_buttons(view)
        pad = BUTTON_FRAME_PADDING
        framed = BUTTON_SIZE + 2 * pad  # 枠の一辺 = アイコン 16 + 左右の余白 2 * 2 = 20
        for x, uv in (
            (DROP_BUTTON_X, DROP_BUTTON_UV),
            (RAISE_BUTTON_X, RAISE_BUTTON_UV),
        ):
            with self.subTest(button_x=x):
                frame = ("rectb", x - pad, BUTTON_Y - pad, framed, framed)
                frame += (BUTTON_FRAME_COLOR,)
                icon_index = next(
                    i
                    for i, c in enumerate(view.calls)
                    if c[0] == "blt" and (c[4], c[5]) == uv
                )
                frame_index = view.calls.index(frame)
                self.assertLess(frame_index, icon_index)
        self.assertEqual(2, len([c for c in view.calls if c[0] == "rectb"]))

    def test_button_frame_has_room_below_last_hand(self):
        """ボタンの枠の上端が、最下段の手札の下端から 10 ピクセル以上離れ、画面内に収まること"""
        min_gap = 10  # 要件 5.1 の指定値（窮屈にならない余白）
        view = RecordingView()
        draw_buttons(view)
        frames = [c for c in view.calls if c[0] == "rectb"]
        last_card_bottom = row_top(3) + (ROW_PITCH - CARD_HEIGHT) // 2 + CARD_HEIGHT
        for frame in frames:
            with self.subTest(frame=frame):
                self.assertGreaterEqual(frame[2] - last_card_bottom, min_gap)
                self.assertLessEqual(frame[2] + frame[4], SCREEN_HEIGHT)

    def test_button_icons_at_bottom(self):
        """drop と Raise のボタンのアイコン（16x16）が、画面の下部に並ぶこと"""
        view = RecordingView()
        draw_buttons(view)
        size = (BUTTON_SIZE, BUTTON_SIZE)
        self.assertEqual(
            [
                ("blt", DROP_BUTTON_X, BUTTON_Y, IMAGE_BANK, *DROP_BUTTON_UV)
                + size
                + (TRANSPARENT_COLOR,),
                ("blt", RAISE_BUTTON_X, BUTTON_Y, IMAGE_BANK, *RAISE_BUTTON_UV)
                + size
                + (TRANSPARENT_COLOR,),
            ],
            [c for c in view.calls if c[0] == "blt"],
        )
        # 画面全体にも、ボタンが 2 つとも含まれる
        self.assertEqual(2, len(blts_with(self.view.calls, BUTTON_UVS)))
        # 最後の段（人間）のカードの下端（段の上端 + 10 + 20）より下にある
        last_card_bottom = row_top(3) + (ROW_PITCH - CARD_HEIGHT) // 2 + CARD_HEIGHT
        self.assertGreaterEqual(BUTTON_Y, last_card_bottom)

    def test_cards_do_not_overlap_and_fit_screen(self):
        """5 枚の手札が重ならず、すべての描画が画面（150x200）の内側に収まること"""
        self.assertGreaterEqual(CARD_PITCH, CARD_WIDTH)
        boxes = [extents(c) for c in self.view.calls if extents(c)]
        self.assertTrue(boxes)
        for left, top, right, bottom in boxes:
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(right, SCREEN_WIDTH)
            self.assertLessEqual(bottom, SCREEN_HEIGHT)

    def test_text_is_ascii_only(self):
        """描く文字がすべて ASCII であること（Pyxel の標準フォントの制約）"""
        texts = [c[3] for c in self.view.calls if c[0] == "text"]
        # 文字は 4 段 × (カードの数字 5 + コイン 1)
        self.assertEqual(4 * (HAND_SIZE + 1), len(texts))
        self.assertTrue(all(t.isascii() for t in texts), texts)


class TestSelectedCardOffset(unittest.TestCase):
    def setUp(self):
        self.table = Table.deal(0)
        self.human = self.table.players[3]
        self.card_y = row_top(3) + (ROW_PITCH - CARD_HEIGHT) // 2

    def frame_ys(self, player, row_index):
        view = RecordingView()
        draw_player_row(view, row_index, player)
        return [c[2] for c in card_frames(view.calls)]

    def test_selected_card_is_drawn_higher_by_offset(self):
        """選択中のカードだけが、選択していないカードより SELECTED_OFFSET だけ上に描かれること"""
        self.human.toggle_selected(1)
        self.human.toggle_selected(4)
        expected = [
            self.card_y - SELECTED_OFFSET if n in (1, 4) else self.card_y
            for n in range(HAND_SIZE)
        ]
        self.assertEqual(expected, self.frame_ys(self.human, 3))

    def test_unselected_hand_is_drawn_at_normal_y(self):
        """何も選択していないとき、全カードが通常の y に描かれること"""
        self.assertEqual([self.card_y] * HAND_SIZE, self.frame_ys(self.human, 3))

    def test_com_row_is_unchanged(self):
        """COM の段は選択の操作に影響されず、通常の y に描かれること"""
        com = self.table.players[0]
        com.toggle_selected(0)
        expected = row_top(0) + (ROW_PITCH - CARD_HEIGHT) // 2
        self.assertEqual([expected] * HAND_SIZE, self.frame_ys(com, 0))


class TestNewCardFrame(unittest.TestCase):
    def setUp(self):
        self.table = Table.deal(0)
        self.human = self.table.players[3]
        self.card_y = row_top(3) + (ROW_PITCH - CARD_HEIGHT) // 2

    def new_card_frames(self):
        view = RecordingView()
        draw_player_row(view, 3, self.human)
        return [
            c for c in view.calls if c[0] == "rectb" and c[5] == NEW_CARD_FRAME_COLOR
        ]

    def test_new_cards_have_frame_one_pixel_outside(self):
        """新しく引いたカードの外側 1 ピクセルに、NEW_CARD_FRAME_COLOR の枠が描かれること"""
        for index in (0, 2):
            self.human.toggle_selected(index)
        self.table.exchange()
        expected = [
            (
                "rectb",
                HAND_X + n * CARD_PITCH - 1,
                self.card_y - 1,
                CARD_WIDTH + 2,
                CARD_HEIGHT + 2,
                NEW_CARD_FRAME_COLOR,
            )
            for n in (0, 2)
        ]
        self.assertEqual(expected, self.new_card_frames())

    def test_other_cards_have_no_frame(self):
        """交換前と、新しく引いていないカードと COM の段には、枠が描かれないこと"""
        self.assertEqual([], self.new_card_frames())
        self.human.toggle_selected(1)
        self.table.exchange()
        self.assertEqual(1, len(self.new_card_frames()))
        view = RecordingView()
        draw_player_row(view, 0, self.table.players[0])
        self.assertEqual([], [c for c in view.calls if c[-1] == NEW_CARD_FRAME_COLOR])


class TestHitCard(unittest.TestCase):
    def setUp(self):
        self.table = Table.deal(0)
        self.card_y = row_top(3) + (ROW_PITCH - CARD_HEIGHT) // 2

    def test_left_edge_hits_and_right_edge_does_not(self):
        """FR1.1: カードの左端は当たり、右端（x + CARD_WIDTH）は当たらないこと（半開区間）"""
        for n in range(HAND_SIZE):
            left = HAND_X + n * CARD_PITCH
            with self.subTest(n=n):
                self.assertEqual(n, hit_card(self.table, left, self.card_y))
                self.assertEqual(
                    n, hit_card(self.table, left + CARD_WIDTH - 1, self.card_y)
                )
                self.assertIsNone(hit_card(self.table, left + CARD_WIDTH, self.card_y))

    def test_gap_between_cards_does_not_hit(self):
        """FR1.1: カードの隙間（CARD_PITCH - CARD_WIDTH）は当たらないこと"""
        gap_x = HAND_X + CARD_WIDTH + (CARD_PITCH - CARD_WIDTH) // 2
        self.assertIsNone(hit_card(self.table, gap_x, self.card_y))

    def test_selected_card_top_edge_hits(self):
        """FR1.1: 選択中のカードは SELECTED_OFFSET だけ上にずれた矩形で判定されること"""
        self.table.players[3].toggle_selected(2)
        x = HAND_X + 2 * CARD_PITCH + CARD_WIDTH // 2
        top = self.card_y - SELECTED_OFFSET
        self.assertEqual(2, hit_card(self.table, x, top))
        self.assertIsNone(hit_card(self.table, x, top - 1))
        # 選択中は下端も SELECTED_OFFSET だけ上がる
        self.assertEqual(2, hit_card(self.table, x, top + CARD_HEIGHT - 1))
        self.assertIsNone(hit_card(self.table, x, top + CARD_HEIGHT))

    def test_com_rows_do_not_hit(self):
        """FR1.4: COM の段のカードは判定の対象にならないこと"""
        for index in range(3):
            y = row_top(index) + (ROW_PITCH - CARD_HEIGHT) // 2
            with self.subTest(row=index):
                self.assertIsNone(hit_card(self.table, HAND_X, y))


class TestHitButton(unittest.TestCase):
    def test_button_rects_and_outside(self):
        """FR2.1/FR2.5: ボタンの枠を含めた矩形で drop／raise を返し、外は None であること"""
        pad = BUTTON_FRAME_PADDING
        framed = BUTTON_SIZE + 2 * pad
        for name, x in (("drop", DROP_BUTTON_X), ("raise", RAISE_BUTTON_X)):
            left, top = x - pad, BUTTON_Y - pad
            with self.subTest(name=name):
                self.assertEqual(name, hit_button(left, top))
                self.assertEqual(name, hit_button(left + framed - 1, top + framed - 1))
                self.assertIsNone(hit_button(left + framed, top))
                self.assertIsNone(hit_button(left, top + framed))
                self.assertIsNone(hit_button(left - 1, top))
                self.assertIsNone(hit_button(left, top - 1))


def expected_popup_calls(*messages):
    """行 messages のポップアップが描く呼び出し（塗り → 枠 → 各行の文字）。"""
    # 文字の幅 = 文字数 * CHAR_WIDTH - 1（最後の文字の右の隙間は含めない）。
    # 例: WIN = 3 * 4 - 1 = 11、LOSE = 4 * 4 - 1 = 15。中央寄せで左端 = 中央 - 幅 // 2
    # 複数行は、行の間を 3 ピクセル空け（行の送り = 5 + 3 = 8）、全体を縦の中央に置く。
    # 2 行: 全体の高さ = 2 * 5 + 3 = 13、先頭の上端 = 8 + (24 - 13) // 2 = 13（2 行目 21、下端 26）
    line_gap = 3
    block_height = len(messages) * CHAR_HEIGHT + (len(messages) - 1) * line_gap
    top = POPUP_Y + (POPUP_HEIGHT - block_height) // 2
    texts = []
    for n, message in enumerate(messages):
        text_width = len(message) * CHAR_WIDTH - 1
        texts.append(
            (
                "text",
                POPUP_X + (POPUP_WIDTH - text_width) // 2,
                top + n * (CHAR_HEIGHT + line_gap),
                message,
                POPUP_TEXT_COLOR,
            )
        )
    inset = 1
    return [
        ("rect", POPUP_X, POPUP_Y, POPUP_WIDTH, POPUP_HEIGHT, POPUP_FILL_COLOR),
        # 枠は塗りの内側 1 ピクセル（幅と高さは 2 * inset 小さい）。例: (26, 86, 98, 28)
        (
            "rectb",
            POPUP_X + inset,
            POPUP_Y + inset,
            POPUP_WIDTH - 2 * inset,
            POPUP_HEIGHT - 2 * inset,
            POPUP_FRAME_COLOR,
        ),
        *texts,
    ]


class TestDrawResultPopup(unittest.TestCase):
    def test_win_draws_fill_frame_and_centered_text(self):
        """FR4.1/FR4.2: 額なしの win で黒い塗り・白い枠・中央の白い WIN がこの順に描かれること"""
        view = RecordingView()
        draw_result_popup(view, "win")
        self.assertEqual(expected_popup_calls("WIN"), view.calls)

    def test_win_with_amount_draws_win_and_got_lines(self):
        """FR4.1: 額つきの win は 1 行目 WIN、2 行目 GOT N の 2 行が中央に描かれること"""
        for amount in (0, 4, 16, 999):
            with self.subTest(amount=amount):
                view = RecordingView()
                draw_result_popup(view, "win", amount)
                self.assertEqual(
                    expected_popup_calls("WIN", f"GOT {amount}"), view.calls
                )

    def test_win_two_lines_stay_inside_frame(self):
        """NFR2: 2 行の文字は、どちらも枠の内側（上下左右）に収まること"""
        for amount in (0, 16, 999):
            with self.subTest(amount=amount):
                view = RecordingView()
                draw_result_popup(view, "win", amount)
                frame = extents(view.calls[1])
                lines = [extents(c) for c in view.calls if c[0] == "text"]
                self.assertEqual(2, len(lines))
                for left, top, right, bottom in lines:
                    self.assertGreater(left, frame[0])
                    self.assertGreater(top, frame[1])
                    self.assertLess(right, frame[2])
                    self.assertLess(bottom, frame[3])
                # 1 行目が 2 行目より上で、重ならない
                self.assertLessEqual(lines[0][3], lines[1][1])

    def test_lose_ignores_amount_and_draws_only_lose(self):
        """FR4.1: lose は額があっても LOSE の 1 行だけ"""
        view = RecordingView()
        draw_result_popup(view, "lose", 16)
        self.assertEqual(expected_popup_calls("LOSE"), view.calls)

    def test_lose_draws_lose_text(self):
        """FR4.1: lose で LOSE の文字が中央に描かれること（WIN は描かれない）"""
        view = RecordingView()
        draw_result_popup(view, "lose")
        self.assertEqual(expected_popup_calls("LOSE"), view.calls)
        self.assertEqual(
            ["LOSE"], [c[3] for c in view.calls if c[0] == "text"], view.calls
        )

    def test_none_draws_nothing(self):
        """結果が無い（None）とき、何も描かれないこと"""
        view = RecordingView()
        draw_result_popup(view, None)
        self.assertEqual([], view.calls)

    def test_unknown_result_raises_value_error(self):
        """win / lose / None 以外の値は ValueError になり、何も描かれないこと"""
        for bad in ("draw", "WIN", ""):
            with self.subTest(result=bad):
                view = RecordingView()
                with self.assertRaises(ValueError):
                    draw_result_popup(view, bad)
                self.assertEqual([], view.calls)

    def test_popup_fits_screen_and_text_inside_frame(self):
        """NFR2: ポップアップと文字が画面（150x200）の内側に収まり、文字は枠の内側にあること"""
        for result in POPUP_MESSAGES:
            with self.subTest(result=result):
                view = RecordingView()
                draw_result_popup(view, result)
                fill, frame, text = (extents(c) for c in view.calls)
                for left, top, right, bottom in (fill, frame, text):
                    self.assertGreaterEqual(left, 0)
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(right, SCREEN_WIDTH)
                    self.assertLessEqual(bottom, SCREEN_HEIGHT)
                self.assertGreater(text[0], frame[0])
                self.assertGreater(text[1], frame[1])
                self.assertLess(text[2], frame[2])
                self.assertLess(text[3], frame[3])

    def test_messages_are_ascii_only(self):
        """NFR2: 描く文字が ASCII のみであること（Pyxel の標準フォントの制約）"""
        for result in POPUP_MESSAGES:
            with self.subTest(result=result):
                view = RecordingView()
                draw_result_popup(view, result)
                texts = [c[3] for c in view.calls if c[0] == "text"]
                self.assertEqual(1, len(texts))
                self.assertTrue(texts[0].isascii(), texts)


def drawn_tops(calls):
    """draw_table が描いたもの（背景の cls を除く）の上端 y を、すべて返す。"""
    return [c[2] for c in calls if c[0] in ("rect", "rectb", "blt", "text")]


class TestResultPopupBand(unittest.TestCase):
    """5.1: 勝敗のポップアップの帯が一番上に常に空いていて、段と重ならないこと"""

    def test_popup_is_above_everything_draw_table_draws(self):
        """ポップアップの下端が、draw_table の描くどの上端よりも上にある（重ならない）"""
        view = RecordingView()
        draw_table(view, Table.deal(0))
        popup_bottom = POPUP_Y + POPUP_HEIGHT
        self.assertGreaterEqual(POPUP_Y, 0)
        self.assertLess(popup_bottom, min(drawn_tops(view.calls)))

    def test_popup_does_not_cover_any_card(self):
        """ポップアップを重ねて描いても、どのカードの枠（rect）とも領域が重ならない"""
        view = RecordingView()
        draw_table(view, Table.deal(0))
        popup_bottom = POPUP_Y + POPUP_HEIGHT
        for frame in card_frames(view.calls):
            with self.subTest(card_y=frame[2]):
                self.assertGreaterEqual(frame[2], popup_bottom)

    def test_com_rows_keep_a_gap_between_cards(self):
        """帯の分だけ COM の段を詰めても、カードの間（縦）に MIN_ROW_GAP 以上空いている"""
        for index in range(COM_ROWS):
            card_bottom = row_top(index) + (ROW_PITCH - CARD_HEIGHT) // 2 + CARD_HEIGHT
            next_top = row_top(index + 1) + (ROW_PITCH - CARD_HEIGHT) // 2
            with self.subTest(row=index):
                self.assertGreaterEqual(next_top - card_bottom, MIN_ROW_GAP)

    def test_com_rows_are_drawn_where_the_layout_says(self):
        """COM の 3 段のカードが、COM_ROW_TOP と COM_ROW_PITCH で決まる位置に描かれる"""
        view = RecordingView()
        draw_table(view, Table.deal(0))
        frames = card_frames(view.calls)
        offset = (ROW_PITCH - CARD_HEIGHT) // 2
        for index in range(COM_ROWS):
            with self.subTest(row=index):
                self.assertEqual(
                    COM_ROW_TOP + index * COM_ROW_PITCH + offset,
                    frames[index * HAND_SIZE][2],
                )

    def test_human_row_and_buttons_keep_their_position(self):
        """人間の段とボタンの位置は変わらない（人間の最初のカードの上端 136、ボタン 170）"""
        view = RecordingView()
        draw_table(view, Table.deal(0))
        frames = card_frames(view.calls)
        human_card_y = ROW_TOP + 3 * ROW_PITCH + (ROW_PITCH - CARD_HEIGHT) // 2
        self.assertEqual(136, human_card_y)  # 6 + 3 * 40 + (40 - 20) // 2
        self.assertEqual(human_card_y, frames[3 * HAND_SIZE][2])
        self.assertEqual(170, BUTTON_Y)


def icon_top(index):
    """段 index のアイコンの上端 y（描画と同じ: 段の上端 + (ROW_PITCH - ICON_SIZE) // 2）。"""
    return row_top(index) + (ROW_PITCH - ICON_SIZE) // 2


class TestDrawWinnerFrame(unittest.TestCase):
    """勝者のアイコンの周りの赤い枠（外側 2 ピクセルの余白、12×12、線の太さ 1）"""

    def test_frame_surrounds_the_winner_icon(self):
        """各段の勝者の枠が、アイコンの外側 2 ピクセルの 12×12 の赤い rectb で描かれる"""
        size = ICON_SIZE + 2 * WINNER_FRAME_PADDING  # 8 + 2 * 2 = 12
        for index in range(4):
            with self.subTest(row=index):
                view = RecordingView()
                draw_winner_frame(view, index)
                self.assertEqual(
                    [
                        (
                            "rectb",
                            ICON_X - WINNER_FRAME_PADDING,
                            icon_top(index) - WINNER_FRAME_PADDING,
                            size,
                            size,
                            WINNER_FRAME_COLOR,
                        )
                    ],
                    view.calls,
                )

    def test_color_is_red(self):
        """枠の色は Pyxel の赤（色 8）"""
        self.assertEqual(8, WINNER_FRAME_COLOR)

    def test_none_draws_nothing(self):
        """勝者がまだ決まっていない（None）とき、何も描かれない"""
        view = RecordingView()
        draw_winner_frame(view, None)
        self.assertEqual([], view.calls)

    def test_frame_does_not_touch_hand_or_other_rows(self):
        """枠は手札（HAND_X から）と重ならず、自分の段（次の段の上端まで）に収まる"""
        for index in range(4):
            with self.subTest(row=index):
                view = RecordingView()
                draw_winner_frame(view, index)
                _, x, y, w, h, _ = view.calls[0]
                row_pitch = COM_ROW_PITCH if index < COM_ROWS else ROW_PITCH
                self.assertGreaterEqual(x, 0)
                self.assertLess(x + w, HAND_X)
                self.assertGreaterEqual(y, row_top(index))
                self.assertLessEqual(y + h, row_top(index) + row_pitch)


class TestDrawPot(unittest.TestCase):
    """ポットの額 "POT n"（画面の一番上の帯の中央、白）"""

    def test_draws_pot_text_centered_in_band_in_white(self):
        """FR8.1: "POT n" の文字が帯の水平・垂直の中央に、白（7）で 1 回だけ描かれる"""
        for amount in (0, 12, 999):
            with self.subTest(amount=amount):
                view = RecordingView()
                draw_pot(view, amount)
                message = f"POT {amount}"
                # 文字の幅 = 文字数 * 4 - 1。例: "POT 12" = 6 * 4 - 1 = 23 → x = 25 + (100 - 23) // 2 = 63
                text_width = CHAR_WIDTH * len(message) - 1
                x = POPUP_X + (POPUP_WIDTH - text_width) // 2
                # y = 8 + (24 - 5) // 2 = 17
                y = POPUP_Y + (POPUP_HEIGHT - CHAR_HEIGHT) // 2
                self.assertEqual([("text", x, y, message, 7)], view.calls)
        self.assertEqual(7, POT_TEXT_COLOR)

    def test_text_follows_amount(self):
        """FR8.1: 額が変わると文字も変わる（0 も "POT 0" と描く）"""
        for amount in (0, 4, 8, 999):
            with self.subTest(amount=amount):
                view = RecordingView()
                draw_pot(view, amount)
                self.assertEqual(f"POT {amount}", view.calls[0][3])

    def test_text_is_inside_band(self):
        """FR8.3: 3 桁の額でも文字が帯（y 8..32、ポップアップの幅）の内側に収まる"""
        view = RecordingView()
        draw_pot(view, 999)
        left, top, right, bottom = extents(view.calls[0])
        self.assertGreaterEqual(left, POPUP_X)
        self.assertLessEqual(right, POPUP_X + POPUP_WIDTH)
        self.assertGreaterEqual(top, POPUP_Y)
        self.assertLessEqual(bottom, POPUP_Y + POPUP_HEIGHT)


def row_calls(calls, index):
    """段 index の縦の範囲 [row_top, row_top + 段の高さ) に収まる呼び出しだけを取り出す。"""
    pitch = COM_ROW_PITCH if index < COM_ROWS else ROW_PITCH
    top = row_top(index)
    return [c for c in calls if extents(c) and top <= c[2] < top + pitch]


class TestDroppedRow(unittest.TestCase):
    """ドロップした段は、手札を描かない（アイコンと所持コインは残す。裏面も描かない）"""

    def setUp(self):
        self.table = Table.deal(0)

    def test_dropped_row_has_no_card_draws(self):
        """FR8.2: dropped の段には、カード（表も裏も）を描く呼び出しが一切ない"""
        for index in range(4):
            with self.subTest(row=index):
                full = RecordingView()
                draw_table(full, self.table)
                view = RecordingView()
                draw_table(view, self.table, {index})
                # 描画の差 = その段の手札だけ（5 枚分）
                removed = [c for c in full.calls if c not in view.calls]
                self.assertTrue(removed)
                self.assertEqual([], card_frames(row_calls(view.calls, index)))
                # 段の中に残るのはアイコンの blt とコインの text の 2 つだけ
                self.assertEqual(
                    ["blt", "text"], [c[0] for c in row_calls(view.calls, index)]
                )

    def test_dropped_row_keeps_icon_and_coins(self):
        """FR8.2: dropped の段でも、アイコンと所持コインは通常どおりの位置に描かれる"""
        view = RecordingView()
        draw_table(view, self.table, {3})
        top = row_top(3)
        icon = (
            "blt",
            ICON_X,
            top + (ROW_PITCH - ICON_SIZE) // 2,
            IMAGE_BANK,
            *HUMAN_ICON_UV,
            ICON_SIZE,
            ICON_SIZE,
            TRANSPARENT_COLOR,
        )
        coins = (
            "text",
            COIN_X,
            top + (ROW_PITCH - CHAR_HEIGHT) // 2,
            str(INITIAL_COINS),
            COIN_TEXT_COLOR,
        )
        self.assertIn(icon, view.calls)
        self.assertIn(coins, view.calls)

    def test_other_rows_are_unchanged(self):
        """FR8.2: dropped でない段の描画は、省略時と同じ（手札などは変わらない）"""
        plain = RecordingView()
        draw_table(plain, self.table)
        dropped = RecordingView()
        draw_table(dropped, self.table, {1, 3})
        for index in (0, 2):
            with self.subTest(row=index):
                self.assertEqual(
                    row_calls(plain.calls, index), row_calls(dropped.calls, index)
                )
        # 全体では、ドロップした 2 段の手札（5 枚分の描画）が減るだけ
        self.assertLess(len(dropped.calls), len(plain.calls))

    def test_all_rows_dropped_draws_no_cards(self):
        """FR8.2: 全員がドロップした場合は、どの段にもカードがなく、背景・アイコン・コイン・ボタンだけ"""
        view = RecordingView()
        draw_table(view, self.table, {0, 1, 2, 3})
        self.assertEqual([], card_frames(view.calls))
        # cls 1 + アイコン 4 + コイン 4 + ボタンの枠 2 + ボタンのアイコン 2 = 13
        self.assertEqual(1 + 4 + 4 + 2 + 2, len(view.calls))

    def test_omitted_or_empty_dropped_draws_as_before(self):
        """NFR3: dropped を省略しても、空でも、今までと同じ描画になる"""
        plain = RecordingView()
        draw_table(plain, self.table)
        empty = RecordingView()
        draw_table(empty, self.table, set())
        self.assertEqual(plain.calls, empty.calls)


if __name__ == "__main__":
    unittest.main()


class TestComHandBack(unittest.TestCase):
    """伏せた COM の手札は 5 枚とも裏面で描く。人間の手札は常に表。"""

    def setUp(self):
        self.table = Table.deal(0)

    def back_frames(self, calls):
        return [c for c in card_frames(calls) if c[5] == CARD_BACK_COLOR]

    def test_hidden_com_row_draws_five_backs(self):
        player = self.table.players[0]
        player.hand_public = False
        view = RecordingView()
        draw_player_row(view, 0, player)
        backs = self.back_frames(view.calls)
        self.assertEqual(
            [HAND_X + n * CARD_PITCH for n in range(HAND_SIZE)], [c[1] for c in backs]
        )
        # 裏面は図形だけ。数字の text もマークの blt（アイコン以外）も描かない
        self.assertEqual(
            [], blts_with(view.calls, [(8, 16), (16, 16), (24, 16), (32, 16)])
        )
        self.assertEqual([COIN_X], [c[1] for c in view.calls if c[0] == "text"])

    def test_public_com_row_draws_faces(self):
        player = self.table.players[0]
        player.hand_public = True
        view = RecordingView()
        draw_player_row(view, 0, player)
        self.assertEqual([], self.back_frames(view.calls))
        self.assertEqual(HAND_SIZE, len(card_frames(view.calls)))

    def test_human_row_is_always_face_up(self):
        player = self.table.players[3]
        player.hand_public = False
        view = RecordingView()
        draw_player_row(view, 3, player)
        self.assertEqual([], self.back_frames(view.calls))
        self.assertEqual(HAND_SIZE, len(card_frames(view.calls)))

    def test_dropped_and_bankrupt_rows_draw_no_cards_even_if_hidden(self):
        player = self.table.players[0]
        player.hand_public = False
        view = RecordingView()
        draw_player_row(view, 0, player, hide_hand=True)
        self.assertEqual([], card_frames(view.calls))
        player.bankrupt = True
        view = RecordingView()
        draw_player_row(view, 0, player)
        self.assertEqual([], card_frames(view.calls))
