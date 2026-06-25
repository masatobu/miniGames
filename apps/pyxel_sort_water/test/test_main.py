import unittest
from unittest.mock import patch
from src.main import (
    App,
    GameCore,
    Cup,
    WaterColor,
    ICupView,
    IInput,
    ISound,
    IView,
    PyxelCupView,
    Board,
)


class TestCupView(ICupView):
    def __init__(self):
        self._calls = []

    def draw(
        self,
        layers,
        col,
        row,
        selected=False,
        anim_shrink_top=1.0,
        anim_extra_color=None,
        anim_extra_scale=0.0,
    ):
        # ICupView.draw のシグネチャに合わせる。GameCore が明示的に渡した
        # （＝デフォルトと異なる）アニメーション引数のみ kwargs に記録し、
        # 非アニメーション時は kwargs={} となるようにする。
        kwargs = {}
        if anim_shrink_top != 1.0:
            kwargs["anim_shrink_top"] = anim_shrink_top
        if anim_extra_color is not None:
            kwargs["anim_extra_color"] = anim_extra_color
        if anim_extra_scale != 0.0:
            kwargs["anim_extra_scale"] = anim_extra_scale
        self._calls.append((layers, col, row, selected, kwargs))

    def get_calls(self):
        return self._calls


class TestInput(IInput):
    def __init__(self):
        self._btn_pressed = False
        self._mouse_x = 0
        self._mouse_y = 0

    def set_btn_pressed(self, pressed):
        self._btn_pressed = pressed

    def set_mouse_x(self, x):
        self._mouse_x = x

    def set_mouse_y(self, y):
        self._mouse_y = y

    def is_btn_pressed(self) -> bool:
        return self._btn_pressed

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_line(self, x1, y1, x2, y2, col):
        self.call_params.append(("draw_line", x1, y1, x2, y2, col))

    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        self.call_params.append(("draw_tri", x1, y1, x2, y2, x3, y3, col))

    def draw_rect(self, x, y, w, h, col):
        self.call_params.append(("draw_rect", x, y, w, h, col))

    def draw_rectb(self, x, y, w, h, col):
        self.call_params.append(("draw_rectb", x, y, w, h, col))


class TestSound(ISound):
    def __init__(self):
        self.call_params = []

    def play_move_success(self):
        self.call_params.append(("play_move_success",))

    def play_move_failure(self):
        self.call_params.append(("play_move_failure",))

    def play_clear(self):
        self.call_params.append(("play_clear",))

    def enable(self, enabled):
        self.call_params.append(("enable", enabled))

    @property
    def enabled(self) -> bool:
        enable_calls = [c for c in self.call_params if c[0] == "enable"]
        return enable_calls[-1][1] if enable_calls else True


class TestParent(unittest.TestCase):
    # main.py のサウンドボタン定数をミラーする（右上・8×6・色 7=白）
    BTN_SOUND_W = 8
    BTN_SOUND_H = 6
    BTN_SOUND_Y = 2
    BTN_SOUND_MARGIN = 2  # 画面右端からの余白
    BTN_SOUND_X = (
        150 - BTN_SOUND_W - BTN_SOUND_MARGIN
    )  # 画面幅 150 の右端から内側 = 140
    SOUND_ICON_COLOR = 13  # 灰色
    SOUND_TRI_OFFSET_X = 1  # 三角形を音波から離すための左方向のずらし幅 (px)
    SOUND_WAVE_COUNT = 2  # 音波の本数
    SOUND_WAVE_GAP = 1  # 三角形右辺から最初の音波までの間隔 (px)
    SOUND_WAVE_STEP = 2  # 音波どうしの間隔 (px)
    SOUND_WAVE_INSET = 1  # 三角形上下端から音波の上下端までの余白 (px)

    def _expected_sound_button_calls(self, enabled):
        """サウンドアイコンの全描画呼び出しを描画順で返す

        スピーカー本体を塗りつぶし三角形で描き、
        enabled のときは右隣に音波の縦線 2 本を加える。
        サウンドボタンは常に描画されるため、全描画テスト共通の前提となる。
        """
        cx = self.BTN_SOUND_X + self.BTN_SOUND_W // 2  # = 144
        cy = self.BTN_SOUND_Y + self.BTN_SOUND_H // 2  # = 5
        top = self.BTN_SOUND_Y  # = 2
        bottom = self.BTN_SOUND_Y + self.BTN_SOUND_H  # = 8
        c = self.SOUND_ICON_COLOR
        tri_left = self.BTN_SOUND_X - self.SOUND_TRI_OFFSET_X  # = 139
        tri_right = cx - self.SOUND_TRI_OFFSET_X  # = 143
        calls = [
            (
                "draw_tri",
                tri_left,
                cy,  # 左頂点
                tri_right,
                top,  # 右上
                tri_right,
                bottom,  # 右下
                c,
            ),
        ]
        if enabled:
            wave_top = self.BTN_SOUND_Y + self.SOUND_WAVE_INSET  # = 3
            wave_bottom = (
                self.BTN_SOUND_Y + self.BTN_SOUND_H - self.SOUND_WAVE_INSET
            )  # = 7
            for i in range(self.SOUND_WAVE_COUNT):
                x = cx + self.SOUND_WAVE_GAP + i * self.SOUND_WAVE_STEP  # = 145, 147
                calls.append(("draw_line", x, wave_top, x, wave_bottom, c))
        return calls

    def setUp(self):
        self.cup_view = TestCupView()
        self.test_input = TestInput()
        self.test_view = TestView()
        self.patcher_cup_view = patch(
            "src.main.PyxelCupView.create", return_value=self.cup_view
        )
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.test_sound = TestSound()
        self.patcher_cup_view.start()
        self.patcher_input.start()
        self.patcher_view.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()
        self.patcher_cup_view.stop()


class TestCup(unittest.TestCase):
    def test_cup_new_has_no_layers(self):
        """新規 Cup は layers が空であること"""
        self.assertEqual(Cup().layers, [])

    def test_cup_add_layer_appends_to_layers(self):
        """add_layer で layers に色が追加されること"""
        cup = Cup()
        cup.add_layer(WaterColor.A)
        cup.add_layer(WaterColor.B)
        self.assertEqual(cup.layers, [WaterColor.A, WaterColor.B])

    def test_pop_layer(self):
        """pop_layer() は最上層の色を返し、layers から削除すること"""
        cup = Cup()
        cup.add_layer(WaterColor.A)
        cup.add_layer(WaterColor.B)
        self.assertEqual(WaterColor.B, cup.pop_layer())
        self.assertEqual([WaterColor.A], cup.layers)

    def test_cup_is_full(self):
        """層数ごとの is_full を確認する"""
        cases = [
            ("空", 0, False),
            ("1層", 1, False),
            ("容量-1層", Cup.CAPACITY - 1, False),
            ("容量ちょうど", Cup.CAPACITY, True),
        ]
        for label, n_layers, expected in cases:
            with self.subTest(label=label):
                cup = Cup()
                for _ in range(n_layers):
                    cup.add_layer(WaterColor.A)
                self.assertEqual(expected, cup.is_full)

    def test_is_completed(self):
        """is_completed の各条件を確認する"""
        cases = [
            ("空コップ", [], False),
            ("2層同色（容量未満）", [WaterColor.A, WaterColor.A], False),
            ("3層混色（色混在）", [WaterColor.A, WaterColor.B, WaterColor.C], False),
            ("3層同色A", [WaterColor.A] * Cup.CAPACITY, True),
            ("3層同色B", [WaterColor.B] * Cup.CAPACITY, True),
            ("3層同色C", [WaterColor.C] * Cup.CAPACITY, True),
        ]
        for label, layers, expected in cases:
            with self.subTest(label=label):
                cup = Cup()
                for color in layers:
                    cup.add_layer(color)
                self.assertEqual(expected, cup.is_completed)


class TestGridDraw(TestParent):
    def test_all_cups_drawn(self):
        """GameCore.draw() が全 16 コップを正しい layers・位置で描画すること"""
        fixed_cup = list(Board.COLORS)  # [A, B, C]
        fixed_empty = 15  # col=3, row=3 を空コップに固定

        with patch("src.main.random.sample", return_value=fixed_cup), patch(
            "src.main.random.randint", return_value=fixed_empty
        ):
            core = GameCore(self.test_sound)

        core.draw()

        expected_calls = []
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                pos = row * Board.COLS + col
                if pos == fixed_empty:
                    layers = []
                else:
                    layers = list(fixed_cup)
                expected_calls.append((layers, col, row, False, {}))

        self.assertEqual(expected_calls, self.cup_view.get_calls())


class TestCupSelection(TestParent):
    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    def _make_core(self):
        """固定ランダムシードで GameCore を生成する"""
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _click_cup(self, core, click_pos):
        """指定 (col, row) のコップ中央をクリック操作で模擬する（col が None なら何もしない）"""
        col, row = click_pos
        if col is None:
            return
        x = (
            PyxelCupView.MARGIN_X
            + col * PyxelCupView.COL_STEP
            + PyxelCupView.CUP_W // 2
        )
        y = (
            PyxelCupView.MARGIN_Y
            + row * PyxelCupView.ROW_STEP
            + PyxelCupView.CUP_H // 2
        )
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def _expected_draw_calls(self, selected_col=None, selected_row=None):
        """全コップの期待描画呼び出しリストを返す（selected 位置のみ selected=True）"""
        calls = []
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                pos = row * Board.COLS + col
                layers = [] if pos == self.FIXED_EMPTY else list(self.FIXED_CUP)
                selected = col == selected_col and row == selected_row
                calls.append((layers, col, row, selected, {}))
        return calls

    def test_draw_selection_state(self):
        """クリック操作後の全描画が選択状態を正しく反映すること"""
        cases = [
            ("初期状態", (None, None), (None, None)),
            ("(0,0) クリック", (0, 0), (0, 0)),
            ("(2,1) クリック", (2, 1), (2, 1)),
            ("空コップ(3,3) クリック", (3, 3), (None, None)),
        ]
        for label, click_pos, expected_selected in cases:
            with self.subTest(case=label):
                core = self._make_core()
                self.cup_view.get_calls().clear()
                self._click_cup(core, click_pos)
                core.draw()
                self.assertEqual(
                    self._expected_draw_calls(*expected_selected),
                    self.cup_view.get_calls(),
                )

    def test_draw_no_selection_after_deselect(self):
        """選択解除後（同コップ再クリック・別コップクリック）、全コップが selected=False で描画されること"""
        cases = [
            ("同コップ再クリック", (0, 0), (0, 0)),
            ("別コップクリック", (0, 0), (1, 0)),
        ]
        for label, first_click, second_click in cases:
            with self.subTest(case=label):
                core = self._make_core()
                self._click_cup(core, first_click)
                self._click_cup(core, second_click)
                self.cup_view.get_calls().clear()
                core.draw()
                self.assertEqual(self._expected_draw_calls(), self.cup_view.get_calls())


class TestBoard(unittest.TestCase):
    def test_board_generation(self):
        """空コップ 1 個、残り 15 コップは 3 層、各色計 15 個、選択なし、未クリアであること"""
        board = Board()
        all_cups = [
            board.get_cup(col, row)
            for row in range(Board.ROWS)
            for col in range(Board.COLS)
        ]

        self.assertEqual(1, sum(1 for cup in all_cups if cup.is_empty))
        for cup in all_cups:
            if not cup.is_empty:
                self.assertEqual(3, len(cup.layers))
        all_layers = [c for cup in all_cups for c in cup.layers]
        for color in Board.COLORS:
            self.assertEqual(15, all_layers.count(color))
        self.assertIsNone(board.selected)
        self.assertFalse(board.is_clear)

    def test_no_cup_starts_already_solved(self):
        """開始時に全層が同色のコップが存在しないこと（100回生成で確認）"""
        for _ in range(100):
            board = Board()
            all_cups = [
                board.get_cup(col, row)
                for row in range(Board.ROWS)
                for col in range(Board.COLS)
            ]
            for cup in all_cups:
                if not cup.is_empty:
                    self.assertGreater(
                        len(set(cup.layers)), 1, f"Cup has all same color: {cup.layers}"
                    )

    def test_select_cup(self):
        cases = [
            (False, True),  # 非空コップ → 選択される
            (True, False),  # 空コップ   → 選択されない
        ]
        for cup_is_empty, should_select in cases:
            with self.subTest(cup_is_empty=cup_is_empty):
                board = Board()
                pos = next(
                    (col, row)
                    for row in range(Board.ROWS)
                    for col in range(Board.COLS)
                    if board.get_cup(col, row).is_empty == cup_is_empty
                )
                board.select(*pos)
                expected = pos if should_select else None
                self.assertEqual(expected, board.selected)


class TestBoardTransfer(unittest.TestCase):
    """Board の水移動ロジックテスト（固定レイアウト使用）

    FIXED_CUP = [A, B, C]、FIXED_EMPTY = 15（col=3, row=3 が空）
    非空コップはすべて layers=[A, B, C]（満杯）
    移動成功: (0,0)[A,B,C] → (3,3)[空]  → (0,0)=[A,B], (3,3)=[C]
    移動拒否: (0,0)[A,B,C] → (1,0)[A,B,C]（満杯）
    """

    FIXED_CUP = list(Board.COLORS)  # [WaterColor.A, WaterColor.B, WaterColor.C]
    FIXED_EMPTY = 15  # col=3, row=3 が空

    def _make_board(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return Board()

    def test_can_move_from_selected(self):
        """can_move_from_selected() の各ケースを確認する"""
        cases = [
            ("空コップへの移動", (0, 0), (3, 3), True),
            ("満杯コップへの移動", (0, 0), (1, 0), False),
            ("選択なし", None, (3, 3), False),
            ("同一コップ", (0, 0), (0, 0), False),
        ]
        for label, src, dst, expected in cases:
            with self.subTest(label=label):
                board = self._make_board()
                if src is not None:
                    board.select(*src)
                self.assertEqual(expected, board.can_move_from_selected(*dst))

    def test_move_to(self):
        """move_to() で最上層が dst に移り、selected が解除されること"""
        board = self._make_board()
        board.select(0, 0)
        src_color = board.get_cup(0, 0).layers[-1]
        board.move_to(3, 3)
        self.assertEqual(src_color, board.get_cup(3, 3).layers[-1])
        self.assertEqual(2, len(board.get_cup(0, 0).layers))
        self.assertIsNone(board.selected)

    def test_transfer_success(self):
        """(0,0)[A,B,C] から空 (3,3) へ移動: C が移動し (0,0)=[A,B]、(3,3)=[C]、選択が解除されること"""
        board = self._make_board()
        board.select(0, 0)
        board.move_to(3, 3)
        self.assertEqual([WaterColor.A, WaterColor.B], board.get_cup(0, 0).layers)
        self.assertEqual([WaterColor.C], board.get_cup(3, 3).layers)
        self.assertIsNone(board.selected)

    def test_transfer_rejected_when_destination_full(self):
        """満杯 (1,0) への移動は不可と判定され、双方のレイヤーが変化しないこと"""
        board = self._make_board()
        board.select(0, 0)
        self.assertFalse(board.can_move_from_selected(1, 0))  # 満杯（3層）
        self.assertEqual(
            [WaterColor.A, WaterColor.B, WaterColor.C], board.get_cup(0, 0).layers
        )
        self.assertEqual(
            [WaterColor.A, WaterColor.B, WaterColor.C], board.get_cup(1, 0).layers
        )

    def test_self_click_cancels_selection(self):
        """選択中のコップを再クリックすると水は移動せず選択がキャンセルされること"""
        board = self._make_board()
        board.select(0, 0)
        before_layers = list(board.get_cup(0, 0).layers)  # [A, B, C]
        board.select(0, 0)  # 自己クリック（選択解除）
        self.assertEqual(before_layers, board.get_cup(0, 0).layers)
        self.assertIsNone(board.selected)


class TestBoardCompleted(unittest.TestCase):
    """完成コップが選択・移動の対象から除外されることを確認するテスト"""

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 が空

    def _make_board(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return Board()

    def _complete_cup(self, cup):
        """cup を同色 3 層（WaterColor.A × 3）の完成状態にする"""
        while not cup.is_empty:
            cup.pop_layer()
        for _ in range(Cup.CAPACITY):
            cup.add_layer(WaterColor.A)

    def test_completed_cup_cannot_be_selected(self):
        """完成コップをクリックしても選択されないこと"""
        board = self._make_board()
        self._complete_cup(board.get_cup(0, 0))
        board.select(0, 0)
        self.assertIsNone(board.selected)

    def test_completed_cup_cannot_be_transfer_destination(self):
        """完成コップへの水移動が不可と判定され、移動元の layers が変化しないこと（is_full で既に除外済みの回帰確認）"""
        board = self._make_board()
        self._complete_cup(board.get_cup(0, 0))
        board.select(1, 0)  # 非完成・非空の (1,0) を選択
        layers_before = list(board.get_cup(1, 0).layers)
        self.assertFalse(board.can_move_from_selected(0, 0))  # 完成コップは移動先不可
        self.assertEqual(layers_before, board.get_cup(1, 0).layers)


class TestBoardClear(unittest.TestCase):
    """水移動（move_to）を通じた is_clear プロパティの振る舞いテスト"""

    def _fill_cup(self, cup, color=WaterColor.A):
        while not cup.is_empty:
            cup.pop_layer()
        for _ in range(Cup.CAPACITY):
            cup.add_layer(color)

    def _empty_cup(self, cup):
        while not cup.is_empty:
            cup.pop_layer()

    def _all_cups(self, board):
        return [
            board.get_cup(col, row)
            for row in range(Board.ROWS)
            for col in range(Board.COLS)
        ]

    def test_not_clear_when_incomplete_cup_exists(self):
        """転送後も非完成コップが残るとき is_clear が False を返すこと"""
        board = Board()
        for cup in self._all_cups(board):
            self._fill_cup(cup)
        # (0, 0): A+B の混色 2 層（非完成・転送元）
        # (0, 1): 空（転送先）
        incomplete = board.get_cup(0, 0)
        self._empty_cup(incomplete)
        incomplete.add_layer(WaterColor.A)
        incomplete.add_layer(WaterColor.B)
        self._empty_cup(board.get_cup(0, 1))
        # 上層 B を (0,1) へ転送 → (0,0) は A×1 層のまま非完成
        board.select(0, 0)
        board.move_to(0, 1)
        self.assertFalse(board.is_clear)

    def test_clear_when_all_nonempty_cups_completed(self):
        """最後の転送で全非空コップが完成状態になったとき is_clear が True を返すこと"""
        board = Board()
        for cup in self._all_cups(board):
            self._fill_cup(cup)
        # (0, 0): A×2 層（転送先・あと 1 層で完成）
        # (1, 0): A×1 層（転送元・転送後に空になる）
        cup_dst = board.get_cup(0, 0)
        self._empty_cup(cup_dst)
        cup_dst.add_layer(WaterColor.A)
        cup_dst.add_layer(WaterColor.A)
        cup_src = board.get_cup(1, 0)
        self._empty_cup(cup_src)
        cup_src.add_layer(WaterColor.A)
        # A を (0,0) へ転送 → 全非空コップが完成
        board.select(1, 0)
        board.move_to(0, 0)
        self.assertTrue(board.is_clear)


class TestCompletedCupDraw(TestParent):
    """完成コップが描画されないことを確認するテスト"""

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 が空

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _complete_cup(self, cup):
        """cup を同色 3 層（WaterColor.A × 3）の完成状態にする"""
        while not cup.is_empty:
            cup.pop_layer()
        for _ in range(Cup.CAPACITY):
            cup.add_layer(WaterColor.A)

    def _expected_draw_calls(self, completed_positions=None):
        """完成コップを除いた期待描画呼び出しリストを返す"""
        if completed_positions is None:
            completed_positions = set()
        calls = []
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                if (col, row) in completed_positions:
                    continue
                pos = row * Board.COLS + col
                layers = [] if pos == self.FIXED_EMPTY else list(self.FIXED_CUP)
                calls.append((layers, col, row, False, {}))
        return calls

    def test_draw_with_completed_cup(self):
        """完成コップのみスキップして全コップを正しい layers・位置・selected 状態で描画すること"""
        cases = [
            ("1 完成（15 コップ描画）", {(0, 0)}),
            ("2 完成（14 コップ描画）", {(0, 0), (1, 0)}),
            ("3 完成（13 コップ描画）", {(0, 0), (1, 0), (2, 0)}),
        ]
        for label, completed_positions in cases:
            with self.subTest(case=label):
                core = self._make_core()
                for col, row in completed_positions:
                    # テスト用の盤面セットアップのため内部 _board に直接アクセスする
                    self._complete_cup(
                        core._board.get_cup(col, row)  # pylint: disable=W0212
                    )
                self.cup_view.get_calls().clear()
                core.draw()
                self.assertEqual(
                    self._expected_draw_calls(completed_positions=completed_positions),
                    self.cup_view.get_calls(),
                )


class TestGameClear(TestParent):
    """クリア状態での GameCore のポップアップ描画と update() ガードの振る舞いテスト"""

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    # ポップアップ定数（150×200 スクリーン）: 設計方針の値と一致させる
    POPUP_X = 25
    POPUP_Y = 85
    POPUP_W = 100
    POPUP_H = 30
    POPUP_BG_COLOR = 1

    # Pyxel デフォルトフォントの寸法と行レイアウト
    CHAR_W = 4  # 1 文字幅（グリフ 3px + 余白 1px）
    CHAR_H = 5  # 文字高
    LINE_GAP = 4  # 行間の余白
    CLEAR_TEXT = "CLEAR"
    RESTART_TEXT = "CLICK TO RESTART"

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _fill_cup(self, cup, color=WaterColor.A):
        while not cup.is_empty:
            cup.pop_layer()
        for _ in range(Cup.CAPACITY):
            cup.add_layer(color)

    def _empty_cup(self, cup):
        while not cup.is_empty:
            cup.pop_layer()

    def _make_cleared_core(self):
        """最後の転送で全非空コップが完成し is_clear が True になる core を返す"""
        core = self._make_core()
        # テスト用の盤面セットアップのため内部 _board に直接アクセスする
        board = core._board  # pylint: disable=W0212
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                self._fill_cup(board.get_cup(col, row))
        # (0,0): A×2 層（転送先・あと 1 層で完成）、(1,0): A×1 層（転送元・転送後に空）
        cup_dst = board.get_cup(0, 0)
        self._empty_cup(cup_dst)
        cup_dst.add_layer(WaterColor.A)
        cup_dst.add_layer(WaterColor.A)
        cup_src = board.get_cup(1, 0)
        self._empty_cup(cup_src)
        cup_src.add_layer(WaterColor.A)
        # A を (0,0) へ転送 → 全非空コップが完成しクリア状態になる
        board.select(1, 0)
        board.move_to(0, 0)
        return core

    def _centered_text_x(self, text):
        """ポップアップ幅の中央にテキストを水平センタリングした左端 X を返す"""
        return self.POPUP_X + self.POPUP_W // 2 - (len(text) * self.CHAR_W) // 2

    def _expected_popup_calls(self):
        """クリア時に PyxelView へ描画される全呼び出しを描画順で返す

        2 行（CLEAR / 再起動案内）をブロックとしてポップアップ中央に垂直センタリングする。
        """
        block_h = 2 * self.CHAR_H + self.LINE_GAP  # 2 行分 + 行間 = 14
        top_y = self.POPUP_Y + self.POPUP_H // 2 - block_h // 2  # = 93
        clear_y = top_y  # = 93
        restart_y = top_y + self.CHAR_H + self.LINE_GAP  # = 102
        return [
            (
                "draw_rect",
                self.POPUP_X,
                self.POPUP_Y,
                self.POPUP_W,
                self.POPUP_H,
                self.POPUP_BG_COLOR,
            ),
            (
                "draw_text",
                self._centered_text_x(self.CLEAR_TEXT),
                clear_y,
                self.CLEAR_TEXT,
            ),
            (
                "draw_text",
                self._centered_text_x(self.RESTART_TEXT),
                restart_y,
                self.RESTART_TEXT,
            ),
        ]

    def test_clear_popup_full_draw(self):
        """クリア状態の draw() でサウンドボタンに続きポップアップの全要素（背景・CLEAR・再起動案内）が描画順どおりに描画されること"""
        core = self._make_cleared_core()
        self.test_view.call_params.clear()
        core.draw()
        # サウンドボタンは常に描画され、その後にクリアポップアップが重なる
        expected = (
            self._expected_sound_button_calls(enabled=True)
            + self._expected_popup_calls()
        )
        self.assertEqual(expected, self.test_view.call_params)

    def test_no_popup_when_not_clear(self):
        """非クリア状態の draw() ではサウンドボタンのみが描画され、ポップアップ関連の描画が行われないこと"""
        core = self._make_core()  # 初期盤面（未クリア）
        self.test_view.call_params.clear()
        core.draw()
        self.assertEqual(
            self._expected_sound_button_calls(enabled=True), self.test_view.call_params
        )

    def test_update_does_not_select_when_clear(self):
        """クリア状態で update() を呼んでも選択状態が変化しないこと（ガードの確認）"""
        core = self._make_cleared_core()
        # 任意のコップ中央をクリックしても選択されないこと
        x = PyxelCupView.MARGIN_X + 2 * PyxelCupView.COL_STEP + PyxelCupView.CUP_W // 2
        y = PyxelCupView.MARGIN_Y + 2 * PyxelCupView.ROW_STEP + PyxelCupView.CUP_H // 2
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        # ガードの効果（選択不変）を内部 _board の状態で直接検証する
        self.assertIsNone(core._board.selected)  # pylint: disable=W0212


class TestGameAnimation(TestParent):
    """移動操作後のアニメーション（ウェイト）状態と操作ブロックの振る舞いテスト

    FIXED_CUP = [A, B, C]、FIXED_EMPTY = 15（col=3, row=3 が空）
    SRC=(0,0)[A,B,C] → DST=(3,3)[空] への移動でアニメーションを開始する。
    アニメーション完了時に SRC の最上層 C が DST へ移動する（遅延モデル更新）。
    """

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    SRC = (0, 0)  # [A, B, C]（移動元）
    DST = (3, 3)  # 空コップ（移動先）
    OTHER = (1, 0)  # アニメーション中にクリックする別コップ
    NEW_SRC = (2, 0)  # アニメーション完了後に選択する別コップ

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _click_cup(self, core, pos):
        """指定 (col, row) のコップ中央をクリック操作で模擬し update() を 1 回呼ぶ"""
        col, row = pos
        x = (
            PyxelCupView.MARGIN_X
            + col * PyxelCupView.COL_STEP
            + PyxelCupView.CUP_W // 2
        )
        y = (
            PyxelCupView.MARGIN_Y
            + row * PyxelCupView.ROW_STEP
            + PyxelCupView.CUP_H // 2
        )
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def _start_animation(self, core):
        """SRC を選択し DST をクリックしてアニメーションを開始する"""
        self._click_cup(core, self.SRC)
        self._click_cup(core, self.DST)

    def _advance_to_completion(self, core):
        """ANIM_DURATION_FRAMES 回 update() を呼びアニメーションを完了させる"""
        for _ in range(GameCore.ANIM_DURATION_FRAMES):
            core.update()

    def _board(self, core):
        return core._board  # pylint: disable=W0212

    def test_click_ignored_during_animation(self):
        """アニメーション中の別コップクリックは無視され、選択（移動元）が保持されること"""
        core = self._make_core()
        self._start_animation(core)
        # アニメーション中に別コップをクリック
        self._click_cup(core, self.OTHER)
        # クリックは無視され、選択（移動元）が保持される
        self.assertEqual(self.SRC, self._board(core).selected)

    def test_board_updated_after_animation_completes(self):
        """アニメーション完了後、移動元の最上層が移動先に移っていること"""
        core = self._make_core()
        expected_color = self._board(core).get_cup(*self.SRC).layers[-1]
        self._start_animation(core)
        self._advance_to_completion(core)
        self.assertEqual(
            expected_color, self._board(core).get_cup(*self.DST).layers[-1]
        )
        self.assertIsNone(self._board(core).selected)

    def test_input_accepted_after_animation(self):
        """アニメーション完了後、新たな選択クリックが Board に届くこと"""
        core = self._make_core()
        self._start_animation(core)
        self._advance_to_completion(core)
        self._click_cup(core, self.NEW_SRC)
        self.assertEqual(self.NEW_SRC, self._board(core).selected)


class TestGameAnimationDraw(TestParent):
    """アニメーション中の draw() が全コップへ正しい引数を渡すことの振る舞いテスト

    FIXED_CUP = [A, B, C]、FIXED_EMPTY = 15（col=3, row=3 が空）
    SRC=(0,0)[A,B,C] → DST=(3,3)[空] への移動でアニメーションを開始する。
    アニメーション中（progress=0.5）の draw() で全 16 コップが:
      - SRC（移動元・選択中）: selected=True、anim_shrink_top = 1.0 - progress = 0.5
      - DST（移動先）: anim_extra_scale = progress = 0.5、anim_extra_color = 移動色
      - それ以外: 追加引数なし（kwargs={}）
    で描画されること。
    """

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    SRC = (0, 0)  # [A, B, C]（移動元）
    DST = (3, 3)  # 空コップ（移動先）
    ANIM_COLOR = WaterColor.C  # SRC の最上層（移動する色）

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _click_cup(self, core, pos):
        """指定 (col, row) のコップ中央をクリック操作で模擬し update() を 1 回呼ぶ"""
        col, row = pos
        x = (
            PyxelCupView.MARGIN_X
            + col * PyxelCupView.COL_STEP
            + PyxelCupView.CUP_W // 2
        )
        y = (
            PyxelCupView.MARGIN_Y
            + row * PyxelCupView.ROW_STEP
            + PyxelCupView.CUP_H // 2
        )
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def _start_animation(self, core):
        """SRC を選択し DST をクリックしてアニメーションを開始する"""
        self._click_cup(core, self.SRC)
        self._click_cup(core, self.DST)

    def _progress_after(self, frames):
        """アニメーション開始後 frames 回 update() した時点の進捗を返す

        GameCore は整数フレームカウンタから進捗を算出する（frame / ANIM_DURATION_FRAMES）。
        同じ計算で期待値を再現する。
        """
        return frames / GameCore.ANIM_DURATION_FRAMES

    def _expected_draw_calls(self, frames):
        """アニメーション開始後 frames 回 update() した時点の全コップ期待描画呼び出しリストを返す

        SRC（移動元・選択中）には anim_shrink_top、DST（移動先）には
        anim_extra_* が入り、それ以外のコップは追加引数なし（kwargs={}）。
        非アニメーション時のデフォルト描画は TestGridDraw で網羅済みのため対象外。
        """
        progress = self._progress_after(frames)
        calls = []
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                pos = row * Board.COLS + col
                layers = [] if pos == self.FIXED_EMPTY else list(self.FIXED_CUP)
                selected = False
                kwargs = {}
                if (col, row) == self.SRC:
                    selected = True
                    kwargs = {"anim_shrink_top": 1.0 - progress}
                elif (col, row) == self.DST:
                    kwargs = {
                        "anim_extra_color": self.ANIM_COLOR,
                        "anim_extra_scale": progress,
                    }
                calls.append((layers, col, row, selected, kwargs))
        return calls

    def test_draw_all_cups_during_animation(self):
        """アニメーション中の各進捗時点で全コップが正しい layers・選択・アニメーション引数で描画されること（3 点測量）

        序盤・中間・終盤の 3 点で進捗（anim_shrink_top / anim_extra_scale）が
        フレーム数に比例して変化することを確認する。各 frames は完了（progress>=1.0）
        前に収まるよう ANIM_DURATION_FRAMES 未満に保つ。
        """
        cases = [
            ("序盤（1 フレーム）", 1),
            ("中間（半分）", GameCore.ANIM_DURATION_FRAMES // 2),
            ("終盤（完了直前）", GameCore.ANIM_DURATION_FRAMES - 1),
        ]
        for label, frames in cases:
            with self.subTest(case=label):
                core = self._make_core()
                self._start_animation(core)
                # 内部状態を直接操作せず、update() の実行回数で進捗を進める
                for _ in range(frames):
                    core.update()
                self.cup_view.get_calls().clear()
                core.draw()
                self.assertEqual(
                    self._expected_draw_calls(frames), self.cup_view.get_calls()
                )


class TestGameClearReset(TestParent):
    """クリア状態でのポップアップクリックによるリセット要求の振る舞いテスト"""

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    # ポップアップ定数（150×200 スクリーン）: 設計方針の値と一致させる
    POPUP_X = 25
    POPUP_Y = 85
    POPUP_W = 100
    POPUP_H = 30

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _fill_cup(self, cup, color=WaterColor.A):
        while not cup.is_empty:
            cup.pop_layer()
        for _ in range(Cup.CAPACITY):
            cup.add_layer(color)

    def _empty_cup(self, cup):
        while not cup.is_empty:
            cup.pop_layer()

    def _make_cleared_core(self):
        """最後の転送で全非空コップが完成し is_clear が True になる core を返す"""
        core = self._make_core()
        # テスト用の盤面セットアップのため内部 _board に直接アクセスする
        board = core._board  # pylint: disable=W0212
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                self._fill_cup(board.get_cup(col, row))
        # (0,0): A×2 層（転送先・あと 1 層で完成）、(1,0): A×1 層（転送元・転送後に空）
        cup_dst = board.get_cup(0, 0)
        self._empty_cup(cup_dst)
        cup_dst.add_layer(WaterColor.A)
        cup_dst.add_layer(WaterColor.A)
        cup_src = board.get_cup(1, 0)
        self._empty_cup(cup_src)
        cup_src.add_layer(WaterColor.A)
        # A を (0,0) へ転送 → 全非空コップが完成しクリア状態になる
        board.select(1, 0)
        board.move_to(0, 0)
        return core

    def _click(self, core, x, y):
        """指定座標のクリック操作を模擬する"""
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def _click_popup_center(self, core):
        """ポップアップ中央のクリック操作を模擬する"""
        self._click(
            core, self.POPUP_X + self.POPUP_W // 2, self.POPUP_Y + self.POPUP_H // 2
        )

    def test_initial_needs_reset_is_false(self):
        """GameCore の初期状態で needs_reset が False を返すこと"""
        core = self._make_core()
        self.assertFalse(core.needs_reset)

    def test_needs_reset_respects_popup_bounds(self):
        """クリア状態のクリックは、ポップアップ矩形内のみ needs_reset を True にすること

        矩形は [X, X+W) × [Y, Y+H) の半開区間（左上端は内・右下端は外）。
        """
        left = self.POPUP_X
        top = self.POPUP_Y
        right = self.POPUP_X + self.POPUP_W  # 排他境界
        bottom = self.POPUP_Y + self.POPUP_H  # 排他境界
        cases = [
            ("中央（内）", left + self.POPUP_W // 2, top + self.POPUP_H // 2, True),
            ("左上端（内・包含）", left, top, True),
            ("右下端の直前（内）", right - 1, bottom - 1, True),
            ("右辺（外・排他）", right, top, False),
            ("下辺（外・排他）", left, bottom, False),
            ("左外", left - 1, top, False),
            ("上外", left, top - 1, False),
        ]
        for label, x, y, expected in cases:
            with self.subTest(case=label):
                core = self._make_cleared_core()
                self._click(core, x, y)
                self.assertEqual(expected, core.needs_reset)

    def test_app_recreates_core_when_needs_reset(self):
        """App は needs_reset が True のとき GameCore を新規生成し、sound を引き継ぐこと"""
        core = self._make_cleared_core()
        self._click_popup_center(core)
        # pyxel に依存する App.__init__ を回避して update() のみを検証する
        app = App.__new__(App)
        app._core = core  # pylint: disable=W0212
        app._sound = self.test_sound  # pylint: disable=W0212
        app.update()
        new_core = app._core  # pylint: disable=W0212
        self.assertIsNot(core, new_core)
        self.assertFalse(new_core.needs_reset)
        self.assertIs(self.test_sound, new_core._sound)  # pylint: disable=W0212


class TestGameCoreSound(TestParent):
    """GameCore が正しいタイミングで効果音を鳴らすことを検証する"""

    FIXED_CUP = list(Board.COLORS)  # [A, B, C]
    FIXED_EMPTY = 15  # col=3, row=3 を空コップに固定

    def _make_core_with_sound(self):
        """固定ランダムシードで GameCore を生成する（TestParent のパッチで test_sound が自動注入）"""
        with patch("src.main.random.sample", return_value=list(self.FIXED_CUP)), patch(
            "src.main.random.randint", return_value=self.FIXED_EMPTY
        ):
            return GameCore(self.test_sound)

    def _click_cup(self, core, col, row):
        """(col, row) のコップ中央ピクセルをクリックして update() を呼ぶ"""
        x = (
            PyxelCupView.MARGIN_X
            + col * PyxelCupView.COL_STEP
            + PyxelCupView.CUP_W // 2
        )
        y = (
            PyxelCupView.MARGIN_Y
            + row * PyxelCupView.ROW_STEP
            + PyxelCupView.CUP_H // 2
        )
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def test_sound_on_two_click_sequence(self):
        """コップ選択後の2回目クリックで正しい効果音が鳴ること（初回選択では音なし）"""
        cases = [
            ("空コップへ移動（成功）", 3, 3, [("play_move_success",)]),
            ("満杯コップへ移動（失敗）", 1, 0, [("play_move_failure",)]),
            ("選択解除（同コップ再クリック）", 0, 0, []),
        ]
        for label, col2, row2, expected in cases:
            with self.subTest(case=label):
                self.test_sound.call_params.clear()
                core = self._make_core_with_sound()
                self._click_cup(core, 0, 0)  # (0,0) を選択
                self.assertEqual([], self.test_sound.call_params)  # 初回選択では音なし
                self._click_cup(core, col2, row2)  # 2回目の操作
                self.assertEqual(expected, self.test_sound.call_params)

    def test_play_clear_when_animation_finishes_on_cleared_board(self):
        """移動アニメーション完了後にボードがクリアなら play_clear() が呼ばれること"""
        core = self._make_core_with_sound()
        board = core._board  # pylint: disable=W0212
        # 移動確定（move_to）まではクリア扱いしない stateful な is_clear。
        # これにより update() の公開フローでアニメーションを開始・完走できる。
        cleared = {"value": False}

        def fake_move_to(*_args):
            cleared["value"] = True

        with patch.object(board, "move_to", side_effect=fake_move_to), patch.object(
            type(board),
            "is_clear",
            new_callable=lambda: property(lambda _: cleared["value"]),
        ):
            self._click_cup(core, 0, 0)  # (0,0) を選択
            self._click_cup(
                core, 3, 3
            )  # 空コップ (3,3) へ移動開始（アニメーション開始）
            self.test_sound.call_params.clear()  # 開始時の play_move_success を除外
            for _ in range(GameCore.ANIM_DURATION_FRAMES):
                core.update()  # アニメーションを完了まで進める
        self.assertEqual([("play_clear",)], self.test_sound.call_params)


class TestSoundButton(TestParent):
    """サウンドボタンの描画ふるまいをテストする"""

    def _make_core(self):
        with patch("src.main.random.sample", return_value=list(Board.COLORS)), patch(
            "src.main.random.randint", return_value=15
        ):
            return GameCore(self.test_sound)

    def _click_sound_button(self, core):
        """サウンドボタン領域の中央をクリックして update() を呼ぶ"""
        x = GameCore.BTN_SOUND_X + GameCore.BTN_SOUND_W // 2
        y = GameCore.BTN_SOUND_Y + GameCore.BTN_SOUND_H // 2
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        core.update()
        self.test_input.set_btn_pressed(False)

    def test_sound_button_draw_by_toggle_count(self):
        """クリック回数に応じてサウンドアイコンの縦線が切り替わり、enable が呼ばれること"""
        cases = [
            (0, True, None),  # 初期状態: on → 縦線あり、sound 呼び出しなし
            (1, False, False),  # 1回クリック: off → 縦線なし、enable(False)
            (2, True, True),  # 2回クリック: on に戻る → 縦線あり、enable(True)
        ]
        for clicks, enabled, expected_enable in cases:
            with self.subTest(clicks=clicks, enabled=enabled):
                core = self._make_core()
                self.test_sound.call_params.clear()
                for _ in range(clicks):
                    self._click_sound_button(core)
                self.test_view.call_params.clear()
                core.draw()
                self.assertEqual(
                    self._expected_sound_button_calls(enabled=enabled),
                    self.test_view.call_params,
                )
                self.assertEqual(clicks, len(self.test_sound.call_params))
                if expected_enable is not None:
                    self.assertEqual(
                        ("enable", expected_enable), self.test_sound.call_params[-1]
                    )

    def test_sound_button_boundary_click(self):
        """サウンドボタンのクリック境界値テスト（内側でトグル、外側でトグルなし）"""
        x0 = GameCore.BTN_SOUND_X  # = 140
        y0 = GameCore.BTN_SOUND_Y  # = 2
        w = GameCore.BTN_SOUND_W  # = 8
        h = GameCore.BTN_SOUND_H  # = 6
        cx = x0 + w // 2  # = 144
        cy = y0 + h // 2  # = 5
        cases = [
            (x0, cy, False, "左辺内側"),
            (x0 - 1, cy, True, "左辺外側"),
            (x0 + w - 1, cy, False, "右辺内側"),
            (x0 + w, cy, True, "右辺外側"),
            (cx, y0, False, "上辺内側"),
            (cx, y0 - 1, True, "上辺外側"),
            (cx, y0 + h - 1, False, "下辺内側"),
            (cx, y0 + h, True, "下辺外側"),
        ]
        for x, y, enabled_after, label in cases:
            with self.subTest(label=label, x=x, y=y):
                core = self._make_core()
                self.test_sound.call_params.clear()
                self.test_input.set_btn_pressed(True)
                self.test_input.set_mouse_x(x)
                self.test_input.set_mouse_y(y)
                core.update()
                self.test_input.set_btn_pressed(False)
                self.test_view.call_params.clear()
                core.draw()
                self.assertEqual(
                    self._expected_sound_button_calls(enabled=enabled_after),
                    self.test_view.call_params,
                )
