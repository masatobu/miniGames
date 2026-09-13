import unittest
from contextlib import contextmanager
from unittest.mock import patch
from src.main import IView, IInput, GameCore, Maze, Direction, GameState, App


# test_maze.py の同名ヘルパーとの重複は意図的（ID-003_subtasks.md「テスト戦略」参照）。
# 共通化は同じヘルパーが3ファイル以上に並んだ時点で検討する方針のため抑制する
@contextmanager
def fixed_maze(cols, rows, grid):
    """迷路のサイズと生成結果を、テストが指定した任意のグリッドに差し替える"""
    # pylint: disable-next=duplicate-code
    with patch.object(Maze, "COLS", cols), patch.object(
        Maze, "ROWS", rows
    ), patch.object(Maze, "GOAL", (cols - 1, rows - 1)), patch.object(
        Maze, "_generate", lambda self: grid
    ):
        yield


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def cls(self, color):
        self.call_params.append(("cls", color))

    def rect(self, x, y, w, h, color):
        self.call_params.append(("rect", x, y, w, h, color))

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("blt", x, y, img, u, v, w, h, colkey))

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def circ(self, x, y, r, color):
        self.call_params.append(("circ", x, y, r, color))

    def circb(self, x, y, r, color):
        self.call_params.append(("circb", x, y, r, color))

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    """`pyxel_break_blocks` の `TestInput` を参照点にする（ID-006_subtasks.md「参考実装」）"""

    def __init__(self):
        self._btn_pressed = False
        self._btn_down = False
        self._btn_released = False
        self._mouse_x = 0
        self._mouse_y = 0

    def set_btn_pressed(self, pressed):
        self._btn_pressed = pressed

    def set_btn_down(self, down):
        self._btn_down = down

    def set_btn_released(self, released):
        self._btn_released = released

    def set_mouse_x(self, x):
        self._mouse_x = x

    def set_mouse_y(self, y):
        self._mouse_y = y

    def is_btn_pressed(self) -> bool:
        return self._btn_pressed

    def is_btn_down(self) -> bool:
        return self._btn_down

    def is_btn_released(self) -> bool:
        return self._btn_released

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.test_input = TestInput()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_view = self.patcher_view.start()
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_input.stop()
        self.patcher_view.stop()


# 初期速度段階(INITIAL_SPEED_INDEX)の移動間隔フレーム数。`MOVE_INTERVAL_FRAMES` は
# `SPEED_STEPS` へ一本化して廃止したため(ID-008-10 Refactor。値の二重管理を避けるため)、
# 初期速度を前提にした既存テストの間隔参照はここから引く
_INITIAL_MOVE_INTERVAL_FRAMES = GameCore.SPEED_STEPS[GameCore.INITIAL_SPEED_INDEX][1]


class _AdvanceOnceMixin:
    """`update()` をキック間隔ぶん進める `_advance_once()` を共通化する。
    3クラス目(`TestGameCoreSpeedButton`)が現れた時点で共通化する
    (`fixed_maze` の「3ファイル目で共通化を検討する」方針と同じ考え方。ID-008-7 Refactor)"""

    def _advance_once(self, core):
        """入力なしで、初期速度段階の間隔ぶん update() を進める"""
        for _ in range(_INITIAL_MOVE_INTERVAL_FRAMES):
            core.update()


class _PressReleaseMixin:
    """ボタンの押下・離しを1フレームだけ発生させる `_press()` / `_release()` を共通化する
    (「教える」・スピード変更のどちらの円を対象にするかは呼び出し側が point で渡す。
    ID-008-7 Refactor。`_AdvanceOnceMixin` と同じ理由で3クラス目を機に共通化した)"""

    def _press(self, core, point):
        """1 フレームだけボタンを押す(押した瞬間の座標を point にする)"""
        x, y = point
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        self.test_input.set_btn_pressed(True)
        self.test_input.set_btn_down(True)
        core.update()
        self.test_input.set_btn_pressed(False)

    def _release(self, core, point):
        """1 フレームだけボタンを離す(離した瞬間の座標を point にする)"""
        x, y = point
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        self.test_input.set_btn_down(False)
        self.test_input.set_btn_released(True)
        core.update()
        self.test_input.set_btn_released(False)


# 期待値は tasks.md「画像リソース仕様」の表から転記する（実装を呼んで作らない）
TILE_CASES = [
    ({Direction.RIGHT, Direction.DOWN}, (8, 0)),  # ┏
    ({Direction.LEFT, Direction.RIGHT, Direction.DOWN}, (12, 0)),  # ┯
    ({Direction.LEFT, Direction.DOWN}, (16, 0)),  # ┓
    ({Direction.DOWN}, (20, 0)),  # ┃（上端）
    ({Direction.UP, Direction.RIGHT, Direction.DOWN}, (8, 4)),  # ┠
    ({Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT}, (12, 4)),  # ╋
    ({Direction.UP, Direction.LEFT, Direction.DOWN}, (16, 4)),  # ┨
    ({Direction.UP, Direction.DOWN}, (20, 4)),  # ┃（中間）
    ({Direction.UP, Direction.RIGHT}, (8, 8)),  # ┗
    ({Direction.UP, Direction.LEFT, Direction.RIGHT}, (12, 8)),  # ┻
    ({Direction.UP, Direction.LEFT}, (16, 8)),  # ┛
    ({Direction.UP}, (20, 8)),  # ┃（下端）
    ({Direction.RIGHT}, (8, 12)),  # ━（左端）
    ({Direction.LEFT, Direction.RIGHT}, (12, 12)),  # ━（中間）
    ({Direction.LEFT}, (16, 12)),  # ━（右端）
    (set(), (20, 12)),  # ・（壁）
]
# 16 通りを 8 x 2 に配置する（非正方 → COLS と ROWS を取り違えた実装を検出できる）
TILE_GRID_COLS = 8
TILE_GRID_ROWS = 2


# 描画テストの期待値組み立てヘルパー。`TestGameCore` と `TestGameCoreButtonInput` の
# 両方から使うため、モジュール関数として共通化する（006-5 Refactor）
def _cell_calls(col, row, tile_origin, color):
    """1 セル分の期待描画(背景矩形 → タイル画像の重ね描き)"""
    x = GameCore.MAZE_X + col * GameCore.CELL_SIZE
    y = GameCore.MAZE_Y + row * GameCore.CELL_SIZE
    size = GameCore.CELL_SIZE
    return [
        ("rect", x, y, size, size, color),
        (
            "blt",
            x,
            y,
            GameCore.TILE_IMAGE_BANK,
            tile_origin[0],
            tile_origin[1],
            size,
            size,
            GameCore.TILE_COLKEY,
        ),
    ]


def _button_calls(color=GameCore.COLOR_BUTTON_NORMAL):
    """「教える」ボタンの期待描画(円の塗り→円の枠→ラベル `STOP`)。
    枠の色は既定で通常色。押下中の色を確認するテストは color を差し替える(ID-006-20)"""
    cx = GameCore.BUTTON_CENTER_X
    cy = GameCore.BUTTON_CENTER_Y
    r = GameCore.BUTTON_RADIUS
    label = GameCore.BUTTON_LABEL
    tx = cx - len(label) * GameCore.TEXT_WIDTH // 2 + GameCore.BUTTON_LABEL_OFFSET
    ty = cy - GameCore.TEXT_HEIGHT // 2 + GameCore.BUTTON_LABEL_OFFSET
    return [
        ("circ", cx, cy, r, 0),
        ("circb", cx, cy, r, color),
        ("draw_text", tx, ty, label),
    ]


def _speed_button_calls(
    label=GameCore.SPEED_STEPS[GameCore.INITIAL_SPEED_INDEX][0],
    color=GameCore.COLOR_BUTTON_NORMAL,
):
    """スピード変更ボタンの期待描画(円の塗り→円の枠→ラベル)。
    枠の色は既定で通常色。押下中の色を確認するテストは color を差し替える
    (「教える」ボタンの _button_calls と同型。ID-008-7 Refactor)"""
    cx = GameCore.SPEED_BUTTON_CENTER_X
    cy = GameCore.SPEED_BUTTON_CENTER_Y
    r = GameCore.SPEED_BUTTON_RADIUS
    tx = cx - len(label) * GameCore.TEXT_WIDTH // 2 + GameCore.BUTTON_LABEL_OFFSET
    ty = cy - GameCore.TEXT_HEIGHT // 2 + GameCore.BUTTON_LABEL_OFFSET
    return [
        ("circ", cx, cy, r, 0),
        ("circb", cx, cy, r, color),
        ("draw_text", tx, ty, label),
    ]


def _pause_button_calls(
    label=GameCore.PAUSE_BUTTON_LABEL,
    color=GameCore.COLOR_BUTTON_NORMAL,
    fill_color=0,
):
    """ポーズボタンの期待描画(円の塗り→円の枠→ラベル)。ラベルは状態によらず
    固定(設計方針2の案C。ID-009-7 Refactor)。ポーズ中であることは塗り色
    (fill_color)で示す(既定は他ボタンと同じ黒 0)。「教える」・スピード変更
    ボタンの *_button_calls と同型。ID-008-7 Refactor で確立した形を踏襲)"""
    cx = GameCore.PAUSE_BUTTON_CENTER_X
    cy = GameCore.PAUSE_BUTTON_CENTER_Y
    r = GameCore.PAUSE_BUTTON_RADIUS
    tx = cx - len(label) * GameCore.TEXT_WIDTH // 2 + GameCore.BUTTON_LABEL_OFFSET
    ty = cy - GameCore.TEXT_HEIGHT // 2 + GameCore.BUTTON_LABEL_OFFSET
    return [
        ("circ", cx, cy, r, fill_color),
        ("circb", cx, cy, r, color),
        ("draw_text", tx, ty, label),
    ]


def _mob_calls(col, row):
    """モブの期待描画(セル中央への黄色2x2の矩形)"""
    offset = (GameCore.CELL_SIZE - GameCore.MOB_SIZE) // 2
    x = GameCore.MAZE_X + col * GameCore.CELL_SIZE + offset
    y = GameCore.MAZE_Y + row * GameCore.CELL_SIZE + offset
    return [("rect", x, y, GameCore.MOB_SIZE, GameCore.MOB_SIZE, GameCore.COLOR_MOB)]


def _block_calls(blocked_cells):
    """ブロックの期待描画(セル中央への赤2x2の矩形)。座標計算はモブと同じ式を使う。
    描画順は列→行の昇順で安定させる(複数ブロックがあるときの呼び出し列を一意にするため)"""
    offset = (GameCore.CELL_SIZE - GameCore.BLOCK_SIZE) // 2
    calls = []
    for col, row in sorted(blocked_cells):
        x = GameCore.MAZE_X + col * GameCore.CELL_SIZE + offset
        y = GameCore.MAZE_Y + row * GameCore.CELL_SIZE + offset
        calls.append(
            (
                "rect",
                x,
                y,
                GameCore.BLOCK_SIZE,
                GameCore.BLOCK_SIZE,
                GameCore.COLOR_BLOCK,
            )
        )
    return calls


def _color_for(cell, visited_cells):
    """cell が visited_cells に含まれるかで、期待する背景色を返す"""
    if cell in visited_cells:
        return GameCore.COLOR_VISITED
    return GameCore.COLOR_UNEXPLORED


def _arrow_calls(cols, rows):
    """入口(スタートの左)・出口(ゴールの右)の矢印の期待描画"""
    arrow_width = len(GameCore.ARROW_TEXT) * GameCore.TEXT_WIDTH
    offset_y = (GameCore.CELL_SIZE - GameCore.TEXT_HEIGHT) // 2
    start_col, start_row = Maze.START
    goal_col, goal_row = (cols - 1, rows - 1)
    return [
        (
            "draw_text",
            GameCore.MAZE_X
            + start_col * GameCore.CELL_SIZE
            - arrow_width
            - GameCore.GATE_ARROW_GAP,
            GameCore.MAZE_Y + start_row * GameCore.CELL_SIZE + offset_y,
            GameCore.ARROW_TEXT,
        ),
        (
            "draw_text",
            GameCore.MAZE_X
            + (goal_col + 1) * GameCore.CELL_SIZE
            + GameCore.GATE_ARROW_GAP,
            GameCore.MAZE_Y + goal_row * GameCore.CELL_SIZE + offset_y,
            GameCore.ARROW_TEXT,
        ),
    ]


def _expected_score(cols, rows, visited_cells, blocked_cells=frozenset()):
    """スコアの期待値。`Maze.score` と同じ算出式を独立して計算する
    (実装インスタンスから期待値を生成しないため、`Maze.score` は呼ばない。
    ID-010_subtasks.md「テストの置き場」)"""
    return (
        cols * rows * Maze.SCORE_PER_CELL
        - (len(visited_cells) - 1) * Maze.SCORE_PER_CELL
        - len(blocked_cells) * Maze.SCORE_PER_BLOCK
    )


def _score_calls(score):
    """画面下部中央のスコア表示の期待描画(数値のみを中央寄せで1回)。
    3つのボタンの後・ポップアップの直前に描かれる(GameCore.draw() の並び)"""
    text = str(score)
    x = GameCore.SCORE_CENTER_X - len(text) * GameCore.TEXT_WIDTH // 2
    return [("draw_text", x, GameCore.SCORE_CENTER_Y, text)]


_POPUP_LINE1_BY_STATE = {
    GameState.CLEARED: GameCore.TEXT_CLEAR,
    GameState.GAME_OVER: GameCore.TEXT_GAME_OVER,
}


def _popup_calls(state, score=None):
    """クリア/ゲームオーバー状態のときのポップアップの期待描画列
    (外枠→内側の背景→中央寄せの文言。探索中は描画なし(空リスト))。
    1行目の文言は状態から導出する(state != CLEARED の一律判定は 007-8 で廃止。
    クリアとゲームオーバーで文字数が違うため x も変わる)。クリアのときだけ、
    「SCORE: 」ラベル付きの最終スコアを3行目として追加する(ID-010_subtasks.md
    「設計方針5」。プレイテスト指摘によりラベルなし(案A)からラベル付き(案B)へ
    変更。ゲームオーバーは2行のまま。score は呼び出し側が用意した期待値であり、
    `Maze.score` は呼ばない)"""
    if state not in _POPUP_LINE1_BY_STATE:
        return []
    border = GameCore.POPUP_BORDER_THICKNESS
    inner_x = GameCore.POPUP_X + border
    inner_y = GameCore.POPUP_Y + border
    inner_w = GameCore.POPUP_W - 2 * border
    inner_h = GameCore.POPUP_H - 2 * border

    lines = [_POPUP_LINE1_BY_STATE[state], GameCore.TEXT_RESTART]
    if state == GameState.CLEARED:
        lines.append(f"{GameCore.POPUP_SCORE_PREFIX}{score}")
    # 行ブロックの高さを行数から求める(2行のときは従来どおりの値になる)
    line_block_height = (
        len(lines) * GameCore.TEXT_HEIGHT + (len(lines) - 1) * GameCore.POPUP_LINE_GAP
    )
    first_line_y = GameCore.POPUP_Y + (GameCore.POPUP_H - line_block_height) // 2

    def text_x(text):
        return (
            GameCore.POPUP_X + (GameCore.POPUP_W - len(text) * GameCore.TEXT_WIDTH) // 2
        )

    calls = [
        (
            "rect",
            GameCore.POPUP_X,
            GameCore.POPUP_Y,
            GameCore.POPUP_W,
            GameCore.POPUP_H,
            GameCore.COLOR_POPUP_BORDER,
        ),
        ("rect", inner_x, inner_y, inner_w, inner_h, GameCore.COLOR_POPUP_BG),
    ]
    for index, line in enumerate(lines):
        line_y = first_line_y + index * (GameCore.TEXT_HEIGHT + GameCore.POPUP_LINE_GAP)
        calls.append(("draw_text", text_x(line), line_y, line))
    return calls


class TestGameCore(TestParent):
    # 2列1行、(0,0)→(1,0) の一本道。モブ位置以外の描画(セル・矢印)は共通のため、
    # 一本道の期待描画列を組む箇所を _one_way_maze_expected_calls() にまとめている
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    def _one_way_maze_expected_calls(
        self, mob_col, mob_row, visited_cells, state=GameState.EXPLORING
    ):
        """_ONE_WAY_GRID を描いた後、モブが (mob_col, mob_row) にいて、
        visited_cells が探索済みで、ゲーム状態が state の場合の期待描画列"""
        # テスト専用の public 昇格は行わず、実装のタイル対応表を直接参照して期待値を導出する
        # （doc/guides/tdd_practices.md「テストコード改善」の例外処置としてインライン抑制する）
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.RIGHT})
            ),
            _color_for((0, 0), visited_cells),
        )
        expected += _cell_calls(
            1,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.LEFT})
            ),
            _color_for((1, 0), visited_cells),
        )
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        score = _expected_score(2, 1, visited_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_draw_every_connection_pattern(self):
        """迷路の全セルが、格子状の座標に、接続方向に対応するタイルで描画されること"""
        grid = {
            (index % TILE_GRID_COLS, index // TILE_GRID_COLS): set(connections)
            for index, (connections, _) in enumerate(TILE_CASES)
        }
        with fixed_maze(TILE_GRID_COLS, TILE_GRID_ROWS, grid):
            core = GameCore()
            core.draw()
        expected = [("cls", 0)]
        for index, (_, tile_origin) in enumerate(TILE_CASES):
            col, row = index % TILE_GRID_COLS, index // TILE_GRID_COLS
            # 生成直後にモブがいるスタートだけが探索済み色になる
            color = _color_for((col, row), {Maze.START})
            expected += _cell_calls(col, row, tile_origin, color)
        expected += _arrow_calls(TILE_GRID_COLS, TILE_GRID_ROWS)
        expected += _mob_calls(*Maze.START)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(
            _expected_score(TILE_GRID_COLS, TILE_GRID_ROWS, {Maze.START})
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_mob_is_drawn_at_the_start_cell(self):
        """迷路の全セルを描いた後に、スタート地点のセル中央へ黄色2x2のモブが重ねて描かれること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            core.draw()
        expected = self._one_way_maze_expected_calls(*Maze.START, {Maze.START})
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_mob_position_unchanged_before_move_interval_elapses(self):
        """移動間隔未満の update() では、描画されるモブの座標が変わらないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            for _ in range(_INITIAL_MOVE_INTERVAL_FRAMES - 1):
                core.update()
            core.draw()
        expected = self._one_way_maze_expected_calls(0, 0, {(0, 0)})
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_mob_moves_one_cell_after_move_interval_elapses(self):
        """移動間隔ぶんの update() で、描画されるモブの座標が隣のセルへ1つだけ変わること。
        2列1行の盤面ではこの1マスの前進がそのままゴール到達になるため、
        クリアポップアップが最後に描かれることも合わせて確認する(ID-007-5)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            for _ in range(_INITIAL_MOVE_INTERVAL_FRAMES):
                core.update()
            core.draw()
        expected = self._one_way_maze_expected_calls(
            1, 0, {(0, 0), (1, 0)}, state=GameState.CLEARED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    # 2列2行、(0,0)→(1,0) の一本道が行き止まりになる盤面。GOAL は fixed_maze により
    # (1,1) になり、行き止まり (1,0) とは別セルになる
    # （test_maze.py の _DEAD_END_GRID と同一盤面。ID-004_subtasks.md「TDD サイクル 004-3」）
    _DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    def test_visited_color_persists_on_cells_behind_the_mob_after_retreating_from_a_dead_end(
        self,
    ):
        """行き止まりから後退した後も、モブが去ったセルの背景が探索済み色のまま描画され続けること。
        後退し切って進める道がなくなるため、ゲームオーバーポップアップが最後に
        描かれることも合わせて確認する(ID-007-8)"""
        with fixed_maze(2, 2, self._DEAD_END_GRID):
            core = GameCore()
            for _ in range(2 * _INITIAL_MOVE_INTERVAL_FRAMES):
                core.update()  # (0,0)->(1,0) へ前進した後、行き止まりで (0,0) へ後退
            core.draw()
        # 後退しても探索済みの記録は消えないため、通過した2セルとも探索済み色のまま
        visited_cells = {(0, 0), (1, 0)}
        expected = [("cls", 0)]
        for row in range(2):
            for col in range(2):
                connections = frozenset(self._DEAD_END_GRID.get((col, row), ()))
                tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                    connections
                )
                expected += _cell_calls(
                    col, row, tile_origin, _color_for((col, row), visited_cells)
                )
        expected += _arrow_calls(2, 2)
        expected += _mob_calls(0, 0)  # 後退後、モブはスタートへ戻っている
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 2, visited_cells))
        expected += _popup_calls(GameState.GAME_OVER)
        self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCoreButtonInput(_AdvanceOnceMixin, _PressReleaseMixin, TestParent):
    """ID-006-14: ボタンの円内で押して円内で離したときだけ「教える」が確定すること

    観測は 006-5 の観測方針どおり、描画されるモブの座標が前進から後退に転じるかで行う
    （ID-006_subtasks.md「006-5 の観測対象がモブの座標である理由」）。
    """

    # 3列1行、(0,0)→(1,0)→(2,0) の一本道。「教える」を確定させなかった場合は
    # (1,0) からさらに (2,0) へ前進し続けるため、確定した場合(後退)との対比が同じ盤面で取れる
    _THREE_CELL_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }

    _INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    # ボタンを囲む矩形の角。矩形判定であれば誤って「内」と判定してしまう座標
    # （ID-006_subtasks.md「矩形ではなく円で判定することをテストで固定する」）
    _OUTSIDE_CORNER_POINT = (
        GameCore.BUTTON_CENTER_X - GameCore.BUTTON_RADIUS,
        GameCore.BUTTON_CENTER_Y - GameCore.BUTTON_RADIUS,
    )

    def _three_cell_maze_expected_calls(
        self,
        mob_col,
        mob_row,
        visited_cells,
        blocked_cells=frozenset(),
        button_color=GameCore.COLOR_BUTTON_NORMAL,
        state=GameState.EXPLORING,
    ):
        """_THREE_CELL_GRID を描いた後、モブが (mob_col, mob_row) にいて、
        visited_cells が探索済み、blocked_cells にブロックがあり、
        ボタンの枠が button_color で描かれ、ゲーム状態が state の場合の期待描画列。
        ブロックはモブより先に描く(重なった場合にモブが上に見えるようにするため。
        ID-006_subtasks.md「重なり順を仕様として固定する理由」)"""
        expected = [("cls", 0)]
        for col in range(3):
            connections = frozenset(self._THREE_CELL_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(
                col, 0, tile_origin, _color_for((col, 0), visited_cells)
            )
        expected += _arrow_calls(3, 1)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls(button_color)
        score = _expected_score(3, 1, visited_cells, blocked_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_mob_retreats_when_pressed_and_released_inside_the_circle(self):
        """円内で押して円内で離すと、「教える」が確定し次のキックで後退すること。
        後退してモブが去った後も、教えた (1,0) にブロックが描かれ続けること(ID-006-17)。
        スタートまで後退し切って進める道がなくなるため、ゲームオーバーポップアップが
        最後に描かれることも合わせて確認する(ID-007-8)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._INSIDE_POINT)
            self._advance_once(core)  # 教えた地点から先へ進まず、(0,0) へ後退する
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            0,
            0,
            {(0, 0), (1, 0)},
            blocked_cells={(1, 0)},
            state=GameState.GAME_OVER,
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_block_is_drawn_with_the_mob_on_top_right_after_teaching(self):
        """「教える」を確定した直後(モブがまだブロックと同じセルにいるフレーム)は、
        ブロックが赤の2x2でセル中央に描かれ、モブが後に描かれて上に見えること"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)
            self._release(
                core, self._INSIDE_POINT
            )  # (1,0) にブロック。モブはまだ (1,0)
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            1, 0, {(0, 0), (1, 0)}, blocked_cells={(1, 0)}
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_exploration_continues_when_released_outside_the_circle(self):
        """円内で押しても、円の外で離すと「教える」は確定せず探索が続くこと。
        3列1行の盤面ではこの前進がそのままゴール到達になるため、
        クリアポップアップが最後に描かれることも合わせて確認する(ID-007-5)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._OUTSIDE_CORNER_POINT)
            self._advance_once(core)  # 教えていないので (1,0) -> (2,0) へ前進を続ける
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            2, 0, {(0, 0), (1, 0), (2, 0)}, state=GameState.CLEARED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_exploration_continues_when_pressed_outside_the_circle(self):
        """円の外で押した場合、円内で離しても「教える」は確定しないこと。
        クリアポップアップが最後に描かれることも合わせて確認する(ID-007-5)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._OUTSIDE_CORNER_POINT)
            self._release(core, self._INSIDE_POINT)
            self._advance_once(core)  # 教えていないので (1,0) -> (2,0) へ前進を続ける
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            2, 0, {(0, 0), (1, 0), (2, 0)}, state=GameState.CLEARED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_exploration_continues_while_pressed_but_not_yet_released(self):
        """押しただけで離していないフレームでは、探索の動きが変わらないこと。
        離していないため、ボタンは押下中の色のまま描かれ続ける(ID-006-20)。
        クリアポップアップが最後に描かれることも合わせて確認する(ID-007-5)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)  # 離さないまま次のキックへ進む
            self._advance_once(core)  # 教えていないので (1,0) -> (2,0) へ前進を続ける
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            2,
            0,
            {(0, 0), (1, 0), (2, 0)},
            button_color=GameCore.COLOR_BUTTON_PRESSED,
            state=GameState.CLEARED,
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_exploration_continues_without_any_button_input(self):
        """ボタンを一切操作しない場合、これまでどおり探索が進むこと。
        クリアポップアップが最後に描かれることも合わせて確認する(ID-007-5)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._advance_once(core)  # (1,0) -> (2,0)
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            2, 0, {(0, 0), (1, 0), (2, 0)}, state=GameState.CLEARED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    # (0,0) から (1,0) への一本道の先に、(2,0)・(1,1) への分岐がある盤面
    # （test_maze.py の _BRANCH_GRID と同型）。異なる2地点で「教える」を確定させ、
    # 両方のブロックが描かれることを確認する（ID-006-17）。
    # test_maze.py との重複は意図的（ID-003_subtasks.md「テスト戦略」参照。
    # 共通化は同じグリッドが3ファイル以上に並んだ時点で検討する）
    # pylint: disable-next=duplicate-code
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    def _branch_maze_expected_calls(
        self, mob_col, mob_row, visited_cells, blocked_cells=frozenset()
    ):
        """_BRANCH_GRID(3列2行)を描いた後の期待描画列"""
        expected = [("cls", 0)]
        for row in range(2):
            for col in range(3):
                connections = frozenset(self._BRANCH_GRID.get((col, row), ()))
                tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                    connections
                )
                expected += _cell_calls(
                    col, row, tile_origin, _color_for((col, row), visited_cells)
                )
        expected += _arrow_calls(3, 2)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(3, 2, visited_cells, blocked_cells))
        return expected

    def test_button_is_drawn_with_normal_color_when_not_pressed(self):
        """押していないとき、ボタンが通常色で描かれること(ID-006-20)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            core.draw()
        expected = self._three_cell_maze_expected_calls(1, 0, {(0, 0), (1, 0)})
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_button_shows_pressed_color_while_held_inside_the_circle(self):
        """円内で押している間、ボタンが押下中の色で描かれること(ID-006-20)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)  # 離さないまま描画する
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            1, 0, {(0, 0), (1, 0)}, button_color=GameCore.COLOR_BUTTON_PRESSED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_button_returns_to_normal_color_after_releasing_inside_the_circle(self):
        """円内で離した後、ボタンが通常色に戻ること(ID-006-20)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._INSIDE_POINT)  # (1,0) にブロック
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            1, 0, {(0, 0), (1, 0)}, blocked_cells={(1, 0)}
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_button_returns_to_normal_color_after_releasing_outside_the_circle(self):
        """円外で離した場合も、ボタンが通常色に戻ること(押下が無効でも見た目は戻る)
        (ID-006-20)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._OUTSIDE_CORNER_POINT)
            core.draw()
        expected = self._three_cell_maze_expected_calls(1, 0, {(0, 0), (1, 0)})
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_all_blocks_are_drawn_when_taught_at_two_different_positions(self):
        """異なる2地点で「教える」を確定させると、両方のブロックが描かれること。
        2つ目は教えた直後(モブと同じセル)、1つ目はモブが去った後という
        2通りの重なり状態を1つのテストで確認する"""
        with fixed_maze(3, 2, self._BRANCH_GRID):
            with patch("src.main.random.choice", return_value=Direction.RIGHT):
                core = GameCore()
                self._advance_once(core)  # (0,0) -> (1,0)
                self._advance_once(core)  # 分岐で乱数の戻り値 RIGHT へ：(1,0) -> (2,0)
                self._press(core, self._INSIDE_POINT)
                self._release(core, self._INSIDE_POINT)  # (2,0) にブロック
                self._advance_once(core)  # 先へ進めず (1,0) へ後退
                self._advance_once(core)  # 残る未探索方向 DOWN へ：(1,0) -> (1,1)
                self._press(core, self._INSIDE_POINT)
                self._release(core, self._INSIDE_POINT)  # (1,1) にもブロック
                core.draw()
        expected = self._branch_maze_expected_calls(
            1,
            1,
            {(0, 0), (1, 0), (2, 0), (1, 1)},
            blocked_cells={(2, 0), (1, 1)},
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_teaching_has_no_effect_while_clear_popup_is_shown(self):
        """クリア状態(ポップアップ表示中)で円内を押して離しても、
        「教える」が確定せずブロックが増えないこと(ID-007-11)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._advance_once(core)  # (1,0) -> (2,0)、GOAL に到達してクリア
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._INSIDE_POINT)
            core.draw()
        expected = self._three_cell_maze_expected_calls(
            2, 0, {(0, 0), (1, 0), (2, 0)}, state=GameState.CLEARED
        )
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_teaching_has_no_effect_while_game_over_popup_is_shown(self):
        """ゲームオーバー状態(ポップアップ表示中)で円内を押して離しても、
        「教える」が確定せずブロックが増えないこと(ID-007-11)"""
        dead_end_grid = {
            (0, 0): {Direction.RIGHT},
            (1, 0): {Direction.LEFT},
        }
        with fixed_maze(2, 2, dead_end_grid):
            core = GameCore()
            for _ in range(2 * _INITIAL_MOVE_INTERVAL_FRAMES):
                core.update()  # (0,0)->(1,0) へ前進した後、行き止まりで (0,0) へ後退
            self._press(core, self._INSIDE_POINT)
            self._release(core, self._INSIDE_POINT)
            core.draw()
        visited_cells = {(0, 0), (1, 0)}
        expected = [("cls", 0)]
        for row in range(2):
            for col in range(2):
                connections = frozenset(dead_end_grid.get((col, row), ()))
                tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                    connections
                )
                expected += _cell_calls(
                    col, row, tile_origin, _color_for((col, row), visited_cells)
                )
        expected += _arrow_calls(2, 2)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 2, visited_cells))
        expected += _popup_calls(GameState.GAME_OVER)
        self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCoreScoreDisplay(_AdvanceOnceMixin, _PressReleaseMixin, TestParent):
    """ID-010-11: 画面下部中央に、スコアの数値のみが中央寄せで描かれること
    (requirements.md「スコア表示」)。呼び出し順(3つのボタンの後・ポップアップの
    直前)は、既存の完全一致テスト(`_score_calls` を組み込んだ各 `_expected_calls`)
    で自然に固定されるため、ここでは数値表示そのものの4点(初期値・盤面依存・
    減算後の値・負値)だけを観測する"""

    # 2列1行の一本道(他クラスの _ONE_WAY_GRID と同一盤面。重複は意図的
    # 〈ID-003_subtasks.md「テスト戦略」参照〉)
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}
    # 3列1行の一本道(他クラスの _THREE_CELL_GRID と同一盤面。重複は意図的)
    # pylint: disable-next=duplicate-code
    _THREE_CELL_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }
    _TEACH_INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)

    def test_score_is_drawn_once_as_the_numeric_value_only_right_after_creation(self):
        """生成直後の draw() で、初期スコアの数値のみが1回描かれること
        (2x1 盤面 → 初期スコア COLS*ROWS*10 = 20)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            core.draw()
        expected_call = _score_calls(_expected_score(2, 1, {Maze.START}))[0]
        self.assertEqual(1, self.test_view.get_call_params().count(expected_call))

    def test_drawn_score_reflects_the_maze_size(self):
        """盤面の大きさが変わると描かれる文字列も変わること(3x1 → 初期スコア 30)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            core.draw()
        expected_call = _score_calls(_expected_score(3, 1, {Maze.START}))[0]
        self.assertEqual(1, self.test_view.get_call_params().count(expected_call))

    def test_drawn_score_decreases_after_the_mob_advances(self):
        """モブが1セル進んだ後は、減算後の値が描かれること(3x1 → 30 から 20 へ)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            core.draw()
        expected_call = _score_calls(_expected_score(3, 1, {(0, 0), (1, 0)}))[0]
        self.assertEqual(1, self.test_view.get_call_params().count(expected_call))

    def test_score_is_drawn_with_minus_sign_without_clamping_to_zero(self):
        """スコアが負値になっても0でクランプせず、マイナス記号を含めて中央寄せが
        崩れずに描かれること(2x1盤面でスタートに「教える」を確定 → 初期20から
        ブロック1個分の-100を引いた-80。左端は `_centered_text_x()` の
        `len(text)` がマイナス記号込みの文字数を数えるため、自然に崩れない)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # (0,0) にブロック
            core.draw()
        expected_call = _score_calls(_expected_score(2, 1, {Maze.START}, {Maze.START}))[
            0
        ]
        self.assertEqual(1, self.test_view.get_call_params().count(expected_call))


class TestGameCorePopupFinalScore(_AdvanceOnceMixin, TestParent):
    """ID-010-15: クリアポップアップの3行目に最終スコアが表示され、
    ゲームオーバーは2行のまま変わらないこと(ID-010_subtasks.md「TDD サイクル
    010-6」)。既存47件(現行54件)の完全一致テストも `_popup_calls()` の更新経由で
    同じ振る舞いを広く確認しているが、ここでは3行目の追加とその回帰(2行のまま)を
    直接の観測対象として固定する"""

    # 2列1行の一本道(他クラスの _ONE_WAY_GRID と同一盤面。重複は意図的
    # 〈ID-003_subtasks.md「テスト戦略」参照〉)。前進1回でゴールに到達しクリアになる
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}
    # 2列2行、行き止まりで後退し切ってゲームオーバーになる盤面(他クラスの
    # _DEAD_END_GRID と同一盤面。重複は意図的)
    # pylint: disable-next=duplicate-code
    _DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    def test_clear_popup_draws_three_lines_with_the_final_score_as_the_third(self):
        """クリア状態の draw() で、ポップアップに CLEAR → TAP TO RESTART →
        最終スコアの3行が中央寄せで描かれ、画面下部のスコアと同じ値であること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)、GOAL に到達してクリア
            core.draw()
        visited_cells = {(0, 0), (1, 0)}
        score = _expected_score(2, 1, visited_cells)
        expected = [("cls", 0)]
        for col in range(2):
            connections = frozenset(self._ONE_WAY_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(
                col, 0, tile_origin, _color_for((col, 0), visited_cells)
            )
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(1, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(score)
        expected += _popup_calls(GameState.CLEARED, score)
        self.assertEqual(expected, self.test_view.get_call_params())
        # ポップアップ最終行(最後の draw_text)が「SCORE: 」ラベル付きで
        # 下部スコアと同じ数値を表すこと
        self.assertEqual(f"{GameCore.POPUP_SCORE_PREFIX}{score}", expected[-1][3])

    def test_game_over_popup_still_has_two_lines_without_a_score_line(self):
        """ゲームオーバー状態では、ポップアップにスコア行が増えず2行のまま
        変わらないこと(回帰。requirements.md はクリアポップアップのみを対象と
        しており、ゲームオーバーは対象外)"""
        with fixed_maze(2, 2, self._DEAD_END_GRID):
            core = GameCore()
            for _ in range(2 * _INITIAL_MOVE_INTERVAL_FRAMES):
                core.update()  # (0,0)->(1,0) へ前進した後、行き止まりで (0,0) へ後退
            core.draw()
        visited_cells = {(0, 0), (1, 0)}
        expected = [("cls", 0)]
        for row in range(2):
            for col in range(2):
                connections = frozenset(self._DEAD_END_GRID.get((col, row), ()))
                tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                    connections
                )
                expected += _cell_calls(
                    col, row, tile_origin, _color_for((col, row), visited_cells)
                )
        expected += _arrow_calls(2, 2)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 2, visited_cells))
        expected += _popup_calls(GameState.GAME_OVER)
        self.assertEqual(expected, self.test_view.get_call_params())
        popup_text_calls = [
            call for call in _popup_calls(GameState.GAME_OVER) if call[0] == "draw_text"
        ]
        self.assertEqual(2, len(popup_text_calls))


class TestGameCoreNeedsReset(_AdvanceOnceMixin, TestParent):
    """ID-007-14: ポップアップ内クリックで `GameCore.needs_reset` が真になること

    test_maze.py / 他クラスとのグリッド重複は意図的（ID-003_subtasks.md「テスト戦略」参照）
    """

    # 2列1行の一本道。前進がそのままゴール到達になる
    # (TestGameCore._ONE_WAY_GRID と同一盤面。重複は意図的)
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    # 2列2行、(0,0)->(1,0) の一本道が行き止まりになる盤面
    # (TestGameCore._DEAD_END_GRID と同一盤面。重複は意図的)
    _DEAD_END_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT},
    }

    _POPUP_CENTER_POINT = (
        GameCore.POPUP_X + GameCore.POPUP_W // 2,
        GameCore.POPUP_Y + GameCore.POPUP_H // 2,
    )

    def _click(self, core, point):
        """1 フレームだけ point でクリックする(押した瞬間の座標を point にする)"""
        x, y = point
        self.test_input.set_mouse_x(x)
        self.test_input.set_mouse_y(y)
        self.test_input.set_btn_pressed(True)
        core.update()
        self.test_input.set_btn_pressed(False)

    def test_needs_reset_is_false_right_after_creation(self):
        """生成直後の GameCore は needs_reset が False であること"""
        core = GameCore()
        self.assertFalse(core.needs_reset)

    def test_needs_reset_becomes_true_when_popup_is_clicked_while_cleared(self):
        """クリア状態でポップアップ内をクリックすると needs_reset が True になること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)、GOAL に到達してクリア
            self._click(core, self._POPUP_CENTER_POINT)
        self.assertTrue(core.needs_reset)

    def test_needs_reset_becomes_true_when_popup_is_clicked_while_game_over(self):
        """ゲームオーバー状態でポップアップ内をクリックすると needs_reset が True になること"""
        with fixed_maze(2, 2, self._DEAD_END_GRID):
            core = GameCore()
            for _ in range(2 * _INITIAL_MOVE_INTERVAL_FRAMES):
                core.update()  # (0,0)->(1,0) へ前進した後、行き止まりで (0,0) へ後退
            self._click(core, self._POPUP_CENTER_POINT)
        self.assertTrue(core.needs_reset)

    def test_needs_reset_stays_false_when_clicked_while_exploring(self):
        """探索中(ポップアップ非表示)のクリックでは needs_reset が True にならないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._click(core, self._POPUP_CENTER_POINT)
        self.assertFalse(core.needs_reset)

    def test_needs_reset_only_when_click_is_inside_popup_rectangle(self):
        """ポップアップ矩形の判定が半開区間 [X, X+W) x [Y, Y+H) であること
        (左上端は内、右下端は外。ID-007-16)"""
        cases = [
            ("top-left corner is inside", (GameCore.POPUP_X, GameCore.POPUP_Y), True),
            (
                "just inside the bottom-right corner",
                (
                    GameCore.POPUP_X + GameCore.POPUP_W - 1,
                    GameCore.POPUP_Y + GameCore.POPUP_H - 1,
                ),
                True,
            ),
            (
                "bottom-right corner is outside",
                (
                    GameCore.POPUP_X + GameCore.POPUP_W,
                    GameCore.POPUP_Y + GameCore.POPUP_H,
                ),
                False,
            ),
            ("far outside the popup", (0, 0), False),
        ]
        for label, point, expect_reset in cases:
            with self.subTest(label):
                with fixed_maze(2, 1, self._ONE_WAY_GRID):
                    core = GameCore()
                    self._advance_once(core)  # (0,0) -> (1,0)、GOAL に到達してクリア
                    self._click(core, point)
                self.assertEqual(expect_reset, core.needs_reset)


class TestAppReset(_AdvanceOnceMixin, _PressReleaseMixin, TestParent):
    """ID-007-14: `App.update()` が needs_reset を見て GameCore を再生成すること

    `pyxel` に依存する `App.__init__` を避けるため、`App.__new__(App)` でインスタンスを
    作り `_core` を差し込んで `update()` だけを検証する
    （ID-007_subtasks.md「参考実装」`App.__new__(App)` パターン）
    """

    # 2列1行の一本道
    # (TestGameCore._ONE_WAY_GRID と同一盤面。重複は意図的)
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}
    # 3列1行の一本道(他クラスの _THREE_CELL_GRID と同一盤面。重複は意図的)
    # pylint: disable-next=duplicate-code
    _THREE_CELL_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }

    _INSIDE_CIRCLE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    _POPUP_CENTER_POINT = (
        GameCore.POPUP_X + GameCore.POPUP_W // 2,
        GameCore.POPUP_Y + GameCore.POPUP_H // 2,
    )

    def test_app_replaces_core_without_updating_old_core_when_needs_reset(self):
        """needs_reset が True のフレームでは、App が新しい GameCore を作り、
        そのフレームでは旧 GameCore の update() を呼ばないこと。再生成後は
        モブがスタートにおり、ブロックが1つも描かれないこと(ID-007-14)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            old_core = GameCore()
            # スタートで「教える」を確定し、ブロックを置いたままゲームオーバーにする
            self._press(old_core, self._INSIDE_CIRCLE_POINT)
            self._release(old_core, self._INSIDE_CIRCLE_POINT)
            # ポップアップ内をクリックして needs_reset を立てる
            self.test_input.set_mouse_x(self._POPUP_CENTER_POINT[0])
            self.test_input.set_mouse_y(self._POPUP_CENTER_POINT[1])
            self.test_input.set_btn_pressed(True)
            old_core.update()
            self.test_input.set_btn_pressed(False)

            app = App.__new__(App)
            app._core = old_core  # pylint: disable=protected-access
            with patch.object(old_core, "update") as mock_update:
                app.update()
            mock_update.assert_not_called()

            self.assertIsNot(old_core, app._core)  # pylint: disable=protected-access
            app._core.draw()  # pylint: disable=protected-access

        expected = [("cls", 0)]
        for col in range(2):
            connections = frozenset(self._ONE_WAY_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(col, 0, tile_origin, _color_for((col, 0), {(0, 0)}))
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(*Maze.START)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 1, {(0, 0)}))
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_score_reinitializes_to_the_new_maze_after_reset(self):
        """ID-010-18: リセット後は、画面下部に描かれるスコアが新しい迷路の
        初期値に戻ること(ID-010_subtasks.md「TDD サイクル 010-7」)。
        `GameCore` 再生成による一括初期化（`Maze` を含めてまるごと作り直す方式。
        ID-007 で確立）で、スコア専用の初期化処理を実装に足していないことを
        確認する特性テスト。リセット前に2回前進してスコアを30(初期値)から
        10まで減らしておき、リセット後は減った値ではなく新しい迷路の初期値
        (30)に戻ることを示す(単なる値の一致ではないことの確認)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            old_core = GameCore()
            self._advance_once(old_core)  # (0,0) -> (1,0)、スコア30->20
            self._advance_once(
                old_core
            )  # (1,0) -> (2,0)、GOAL到達でCLEARに。スコアは10
            # ポップアップ内をクリックして needs_reset を立てる
            self.test_input.set_mouse_x(self._POPUP_CENTER_POINT[0])
            self.test_input.set_mouse_y(self._POPUP_CENTER_POINT[1])
            self.test_input.set_btn_pressed(True)
            old_core.update()
            self.test_input.set_btn_pressed(False)

            app = App.__new__(App)
            app._core = old_core  # pylint: disable=protected-access
            app.update()
            app._core.draw()  # pylint: disable=protected-access

        # 新しい迷路(同じ3列1行の盤面)の初期スコアは、リセット前の最終値(10)
        # ではなく、まっさらな到達済みセル{START}から計算した値(30)になる
        expected_call = _score_calls(_expected_score(3, 1, {Maze.START}))[0]
        self.assertEqual(1, self.test_view.get_call_params().count(expected_call))


class TestGameCoreSpeedButton(_AdvanceOnceMixin, _PressReleaseMixin, TestParent):
    """ID-008-5: 円内で押して円内で離すと、スピード段階のラベルが循環すること

    観測は「教える」ボタンと同様、描画されるラベル・枠色で行う(GameCore 内部の
    `_speed_index` を直接読むテストは作らない。ID-008_subtasks.md「TDD サイクル 008-2」)。
    """

    # 2列1行の一本道(他クラスの _ONE_WAY_GRID と同一盤面。重複は意図的
    # 〈ID-003_subtasks.md「テスト戦略」参照〉)。SPEED_STEPS の移動間隔を setUp で
    # 大きく上書きしているため、このクラスの press/release ではモブが動かない
    # (モブの座標・探索状況をこのクラスの関心事から外すため)
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    _TEACH_INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    _SPEED_INSIDE_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X,
        GameCore.SPEED_BUTTON_CENTER_Y,
    )
    # スピードボタンを囲む矩形の角。矩形判定であれば誤って「内」と判定してしまう座標
    # (「教える」ボタンの _OUTSIDE_CORNER_POINT と同じ考え方)
    _SPEED_OUTSIDE_CORNER_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X - GameCore.SPEED_BUTTON_RADIUS,
        GameCore.SPEED_BUTTON_CENTER_Y - GameCore.SPEED_BUTTON_RADIUS,
    )

    def setUp(self):
        super().setUp()
        # モブの座標をこのクラスの関心事から外すため、press/release の数フレーム程度では
        # キックが発生しないよう、全段階の移動間隔を大きく上書きする(ID-008-3 で段階が
        # 移動間隔へ反映されるようになった後も、このクラスはラベルの循環だけを見る
        # 関心事のまま保つ。ラベルは変えず間隔だけを差し替える)
        huge_steps = tuple((label, 10**6) for label, _ in GameCore.SPEED_STEPS)
        self.patcher_move_interval = patch.object(GameCore, "SPEED_STEPS", huge_steps)
        self.patcher_move_interval.start()

    def tearDown(self):
        self.patcher_move_interval.stop()
        super().tearDown()

    def _expected_calls(
        self,
        speed_label,
        speed_color=GameCore.COLOR_BUTTON_NORMAL,
        teach_color=GameCore.COLOR_BUTTON_NORMAL,
        blocked_cells=frozenset(),
        state=GameState.EXPLORING,
    ):
        """_ONE_WAY_GRID を描いた後、モブがスタートに留まったままの期待描画列"""
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.RIGHT})
            ),
            _color_for((0, 0), {Maze.START}),
        )
        expected += _cell_calls(
            1,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.LEFT})
            ),
            GameCore.COLOR_UNEXPLORED,
        )
        expected += _arrow_calls(2, 1)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(*Maze.START)
        expected += _speed_button_calls(speed_label, speed_color)
        expected += _pause_button_calls()
        expected += _button_calls(teach_color)
        score = _expected_score(2, 1, {Maze.START}, blocked_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_initial_speed_label_right_after_creation(self):
        """生成直後（＝リセット後）のラベルが初期段階(">" )であること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            core.draw()
        self.assertEqual(
            self._expected_calls(speed_label=">"), self.test_view.get_call_params()
        )

    def test_label_advances_one_stage_and_does_not_confirm_teaching(self):
        """円内で押して円内で離すと、ラベルが1段階進んで描かれること(">" -> ">>")。
        このとき「教える」は確定しないこと(ブロックが増えない・教えるボタンの枠が
        通常色のまま。2つのボタンが互いに干渉しないことの確認)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)
            core.draw()
        self.assertEqual(
            self._expected_calls(speed_label=">>"), self.test_view.get_call_params()
        )

    def test_label_cycles_through_all_three_stages_and_wraps_to_slowest(self):
        """押下を繰り返すとラベルが ">" -> ">>" -> ">>>" -> ">" と循環すること
        (最速の次は最低速へ戻る)。1回ごとに描画列を完全一致で確認するため、
        テストが所有する TestView の記録をここで明示的にクリアする"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            for expected_label in (">>", ">>>", ">", ">>"):
                self._press(core, self._SPEED_INSIDE_POINT)
                self._release(core, self._SPEED_INSIDE_POINT)
                self.test_view.call_params.clear()
                core.draw()
                self.assertEqual(
                    self._expected_calls(speed_label=expected_label),
                    self.test_view.get_call_params(),
                )

    def test_label_unchanged_when_released_outside_the_circle(self):
        """円内で押しても、円の外で離すとラベルが変わらないこと
        (完了条件の「円外で離した場合は無効」)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_OUTSIDE_CORNER_POINT)
            core.draw()
        self.assertEqual(
            self._expected_calls(speed_label=">"), self.test_view.get_call_params()
        )

    def test_label_unchanged_when_pressed_outside_the_circle(self):
        """円の外で押した場合、円内で離してもラベルが変わらないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._SPEED_OUTSIDE_CORNER_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)
            core.draw()
        self.assertEqual(
            self._expected_calls(speed_label=">"), self.test_view.get_call_params()
        )

    def test_label_does_not_advance_while_held_without_releasing(self):
        """押しただけで離していないフレームでは、ラベルが進まないこと。
        離していないため、ボタンは押下中の色のまま描かれ続けること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)  # 離さないまま描画する
            core.draw()
        self.assertEqual(
            self._expected_calls(
                speed_label=">", speed_color=GameCore.COLOR_BUTTON_PRESSED
            ),
            self.test_view.get_call_params(),
        )

    def test_pressing_teach_button_does_not_change_speed_label(self):
        """「教える」ボタンの円内での押下・離しでは、ラベルが変わらないこと
        (「教える」は確定するためブロックは増える。2つのボタンが互いに
        干渉しないことの確認・逆方向)。モブがまだ動いていないスタートへ
        ブロックを置くため、以後進める道がなくなりゲームオーバーになる
        (この副作用自体はこのクラスの関心事ではないため期待値へそのまま反映する)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # (0,0) にブロック
            core.draw()
        self.assertEqual(
            self._expected_calls(
                speed_label=">",
                blocked_cells={Maze.START},
                state=GameState.GAME_OVER,
            ),
            self.test_view.get_call_params(),
        )

    def test_label_unchanged_while_clear_popup_is_shown(self):
        """クリア状態(ポップアップ表示中)で円内を押して離しても、
        ラベルが変わらないこと(設計方針7の回帰。「教える」ボタンの ID-007-11 と同型)"""
        # 1列1行 = START と GOAL が同一セルになり、生成直後から CLEARED になる盤面
        with fixed_maze(1, 1, {(0, 0): set()}):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)
            core.draw()
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(frozenset()),  # pylint: disable=W0212
            GameCore.COLOR_VISITED,  # 生成直後のスタート(=ゴール)は探索済み色
        )
        expected += _arrow_calls(1, 1)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        score = _expected_score(1, 1, {(0, 0)})
        expected += _score_calls(score)
        expected += _popup_calls(GameState.CLEARED, score)
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_label_unchanged_while_game_over_popup_is_shown(self):
        """ゲームオーバー状態(ポップアップ表示中)で円内を押して離しても、
        ラベルが変わらないこと(設計方針7の回帰)"""
        # スタートに接続が無く、生成直後から GAME_OVER になる盤面
        dead_end_grid = {(0, 0): set(), (1, 0): set()}
        with fixed_maze(2, 1, dead_end_grid):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)
            core.draw()
        expected = [("cls", 0)]
        for col in range(2):
            connections = frozenset(dead_end_grid.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(col, 0, tile_origin, _color_for((col, 0), {(0, 0)}))
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 1, {(0, 0)}))
        expected += _popup_calls(GameState.GAME_OVER)
        self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCorePauseButton(_PressReleaseMixin, TestParent):
    """ID-009-5: 円内で押して円内で離すと、ポーズ表示がトグルすること

    観測は「教える」・スピード変更ボタンと同様、描画される塗り色・枠色で行う
    (GameCore 内部の `_paused` を直接読むテストは作らない。ID-009_subtasks.md
    「TDD サイクル 009-2」)。ラベルは状態によらず固定であり、ポーズ中であることは
    塗り色(circ の第4引数)で示す(設計方針2の案C。ID-009-7 Refactorでラベルの
    トグルから変更)。モブの移動への反映は次サイクル(009-3)で扱うため、
    このクラスでは移動間隔を上書きしない(押下・離しの数フレームでは
    初期段階(6フレーム間隔)でもキックが起きないため。TestGameCoreSpeedButton
    と異なり、ここでは間隔を巨大化する必要がない)。
    """

    # 2列1行の一本道(TestGameCoreSpeedButton._ONE_WAY_GRID と同一盤面。重複は意図的
    # 〈ID-003_subtasks.md「テスト戦略」参照〉)
    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}

    _TEACH_INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    _SPEED_INSIDE_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X,
        GameCore.SPEED_BUTTON_CENTER_Y,
    )
    _PAUSE_INSIDE_POINT = (
        GameCore.PAUSE_BUTTON_CENTER_X,
        GameCore.PAUSE_BUTTON_CENTER_Y,
    )
    # ポーズボタンを囲む矩形の角。矩形判定であれば誤って「内」と判定してしまう座標
    # (「教える」ボタンの _OUTSIDE_CORNER_POINT と同じ考え方)
    _PAUSE_OUTSIDE_CORNER_POINT = (
        GameCore.PAUSE_BUTTON_CENTER_X - GameCore.PAUSE_BUTTON_RADIUS,
        GameCore.PAUSE_BUTTON_CENTER_Y - GameCore.PAUSE_BUTTON_RADIUS,
    )

    def _expected_calls(
        self,
        pause_fill_color=0,
        pause_border_color=GameCore.COLOR_BUTTON_NORMAL,
        speed_label=GameCore.SPEED_STEPS[GameCore.INITIAL_SPEED_INDEX][0],
        blocked_cells=frozenset(),
        state=GameState.EXPLORING,
    ):
        """_ONE_WAY_GRID を描いた後、モブがスタートに留まったままの期待描画列"""
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.RIGHT})
            ),
            _color_for((0, 0), {Maze.START}),
        )
        expected += _cell_calls(
            1,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.LEFT})
            ),
            GameCore.COLOR_UNEXPLORED,
        )
        expected += _arrow_calls(2, 1)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(*Maze.START)
        expected += _speed_button_calls(speed_label)
        expected += _pause_button_calls(
            color=pause_border_color, fill_color=pause_fill_color
        )
        expected += _button_calls()
        score = _expected_score(2, 1, {Maze.START}, blocked_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_initial_fill_is_normal_right_after_creation(self):
        """生成直後（＝リセット後）はポーズ解除状態の表示(通常の塗り色 0)であること
        (設計方針6の「リセット後は解除状態」を固定する)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            core.draw()
        self.assertEqual(self._expected_calls(), self.test_view.get_call_params())

    def test_fill_changes_to_paused_color_when_pressed_and_released_inside_the_circle(
        self,
    ):
        """円内で押して円内で離すと、ポーズ中の塗り色(COLOR_BUTTON_PAUSED)に
        変わること。ポーズ押下では「教える」が確定せず(ブロックが増えない)、
        スピード段階も変わらないこと(2つのボタンが互いに干渉しないことの確認)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._PAUSE_INSIDE_POINT)
            self._release(core, self._PAUSE_INSIDE_POINT)
            core.draw()
        self.assertEqual(
            self._expected_calls(pause_fill_color=GameCore.COLOR_BUTTON_PAUSED),
            self.test_view.get_call_params(),
        )

    def test_fill_returns_to_normal_after_toggling_twice(self):
        """もう一度同じ操作をすると、ポーズ解除の表示(通常の塗り色)に戻ること"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            for _ in range(2):
                self._press(core, self._PAUSE_INSIDE_POINT)
                self._release(core, self._PAUSE_INSIDE_POINT)
            core.draw()
        self.assertEqual(self._expected_calls(), self.test_view.get_call_params())

    def test_fill_unchanged_when_released_outside_the_circle(self):
        """円内で押しても、円の外で離すと表示が変わらないこと
        (完了条件の「円外で離した場合は無効」)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._PAUSE_INSIDE_POINT)
            self._release(core, self._PAUSE_OUTSIDE_CORNER_POINT)
            core.draw()
        self.assertEqual(self._expected_calls(), self.test_view.get_call_params())

    def test_fill_unchanged_when_pressed_outside_the_circle(self):
        """円の外で押した場合、円内で離しても表示が変わらないこと"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._PAUSE_OUTSIDE_CORNER_POINT)
            self._release(core, self._PAUSE_INSIDE_POINT)
            core.draw()
        self.assertEqual(self._expected_calls(), self.test_view.get_call_params())

    def test_fill_stays_normal_and_border_shows_pressed_color_while_held(self):
        """押しただけで離していないフレームでは、塗り色(ポーズ表示)が変わらないこと。
        離していないため、枠は押下中の色のまま描かれ続けること
        (塗り・枠が別の軸であることの確認)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._PAUSE_INSIDE_POINT)  # 離さないまま描画する
            core.draw()
        self.assertEqual(
            self._expected_calls(pause_border_color=GameCore.COLOR_BUTTON_PRESSED),
            self.test_view.get_call_params(),
        )

    def test_pressing_teach_button_does_not_change_pause_fill(self):
        """「教える」ボタンの円内での押下・離しでは、ポーズ表示が変わらないこと
        (2つのボタンが互いに干渉しないことの確認・逆方向。ID-008 の交差確認と同型)。
        モブがまだ動いていないスタートへブロックを置くため、以後進める道がなくなり
        ゲームオーバーになる(この副作用自体はこのクラスの関心事ではないため
        期待値へそのまま反映する)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # (0,0) にブロック
            core.draw()
        self.assertEqual(
            self._expected_calls(blocked_cells={Maze.START}, state=GameState.GAME_OVER),
            self.test_view.get_call_params(),
        )

    def test_pressing_speed_button_does_not_change_pause_fill(self):
        """スピード変更ボタンの円内での押下・離しでは、ポーズ表示が変わらないこと
        (段階は進むがポーズはトグルされない。交差確認・逆方向)"""
        with fixed_maze(2, 1, self._ONE_WAY_GRID):
            core = GameCore()
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)
            core.draw()
        self.assertEqual(
            self._expected_calls(speed_label=">>"), self.test_view.get_call_params()
        )

    def test_fill_unchanged_while_clear_popup_is_shown(self):
        """クリア状態(ポップアップ表示中)で円内を押して離しても、
        ポーズ表示が変わらないこと(設計方針6の回帰。「教える」ボタンのID-007-11と
        同型)"""
        # 1列1行 = START と GOAL が同一セルになり、生成直後から CLEARED になる盤面
        with fixed_maze(1, 1, {(0, 0): set()}):
            core = GameCore()
            self._press(core, self._PAUSE_INSIDE_POINT)
            self._release(core, self._PAUSE_INSIDE_POINT)
            core.draw()
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(frozenset()),  # pylint: disable=W0212
            GameCore.COLOR_VISITED,  # 生成直後のスタート(=ゴール)は探索済み色
        )
        expected += _arrow_calls(1, 1)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        score = _expected_score(1, 1, {(0, 0)})
        expected += _score_calls(score)
        expected += _popup_calls(GameState.CLEARED, score)
        self.assertEqual(expected, self.test_view.get_call_params())

    def test_fill_unchanged_while_game_over_popup_is_shown(self):
        """ゲームオーバー状態(ポップアップ表示中)で円内を押して離しても、
        ポーズ表示が変わらないこと(設計方針6の回帰)"""
        # スタートに接続が無く、生成直後から GAME_OVER になる盤面
        dead_end_grid = {(0, 0): set(), (1, 0): set()}
        with fixed_maze(2, 1, dead_end_grid):
            core = GameCore()
            self._press(core, self._PAUSE_INSIDE_POINT)
            self._release(core, self._PAUSE_INSIDE_POINT)
            core.draw()
        expected = [("cls", 0)]
        for col in range(2):
            connections = frozenset(dead_end_grid.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(col, 0, tile_origin, _color_for((col, 0), {(0, 0)}))
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(0, 0)
        expected += _speed_button_calls()
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(2, 1, {(0, 0)}))
        expected += _popup_calls(GameState.GAME_OVER)
        self.assertEqual(expected, self.test_view.get_call_params())


class TestGameCoreSpeedAffectsMoveInterval(_PressReleaseMixin, TestParent):
    """ID-008-8: 現在のスピード段階が、モブの移動間隔へ正しく反映されること

    スピードボタンを実際に押して段階を切り替え(0〜3回。3回で初期段階へ一周する)、
    切り替え後の移動間隔がその段階の値(12/6/3フレーム)になっていることを、
    描画されるモブの座標で観測する(段階そのものを直接読むテストは作らない。
    ID-008_subtasks.md「TDD サイクル 008-2」と同方針)。切り替え中はキックが
    起きないよう、全段階の移動間隔を一時的に巨大な値へ上書きする
    (TestGameCoreSpeedButton.setUp と同じ技法)。これにより、
    「初期段階では現行と同じ間隔で動くこと(回帰)」「最速/最低速へ切り替えると
    間隔が短く/長くなり、その間隔に満たないフレーム数では動かないこと」
    「一周して初期段階へ戻すと間隔が元に戻ること」の4項目を確認する
    (ID-008_subtasks.md「TDD サイクル 008-3」)。
    """

    # pylint: disable-next=duplicate-code
    _ONE_WAY_GRID = {(0, 0): {Direction.RIGHT}, (1, 0): {Direction.LEFT}}
    _SPEED_INSIDE_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X,
        GameCore.SPEED_BUTTON_CENTER_Y,
    )

    def _expected_calls(
        self, mob_col, mob_row, visited_cells, speed_label, state=GameState.EXPLORING
    ):
        """_ONE_WAY_GRID を描いた後、モブが (mob_col, mob_row) にいて、
        スピードボタンのラベルが speed_label の場合の期待描画列
        (TestGameCore._one_way_maze_expected_calls と同型。重複は意図的
        〈ID-003_subtasks.md「テスト戦略」参照〉)"""
        # pylint: disable=duplicate-code
        expected = [("cls", 0)]
        expected += _cell_calls(
            0,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.RIGHT})
            ),
            _color_for((0, 0), visited_cells),
        )
        expected += _cell_calls(
            1,
            0,
            GameCore._get_tile_origin(  # pylint: disable=W0212
                frozenset({Direction.LEFT})
            ),
            _color_for((1, 0), visited_cells),
        )
        expected += _arrow_calls(2, 1)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls(speed_label)
        expected += _pause_button_calls()
        expected += _button_calls()
        score = _expected_score(2, 1, visited_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    # press_count とその意味の対応(実装詳細の4項目に対応)。0回は段階を
    # 切り替えていない初期段階(回帰)、1回は最速、2回は最低速、3回は一周して
    # 初期段階へ戻った場合を表す
    _PRESS_COUNT_CASES = (
        (0, "初期段階のまま(回帰。既定の間隔6フレームで動く)"),
        (1, '最速段階(">>>")へ1回切り替え(間隔3フレームへ短縮)'),
        (2, '最低速段階(">")へ2回切り替え(間隔12フレームへ延長)'),
        (3, '一周(3回切り替え)して初期段階(">>")へ復帰(間隔6フレームへ復元)'),
    )

    def test_move_interval_reflects_speed_selected_via_button_presses(self):
        """スピードボタンを press_count 回押して離した後の移動間隔が、
        その段階の値(12/6/3フレーム)になっていることを、_PRESS_COUNT_CASES の
        4パターン(0〜3回切り替え)それぞれで確認する。押している間はキックが
        起きないよう、全段階の移動間隔を一時的に巨大な値へ上書きする
        (TestGameCoreSpeedButton.setUp と同じ技法)"""
        for press_count, case in self._PRESS_COUNT_CASES:
            with self.subTest(press_count=press_count, case=case):
                # setUp() は test メソッドごとに1回しか呼ばれず TestView は
                # subTest の反復間で使い回されるため、ケースの先頭で記録をクリアする
                self.test_view.call_params.clear()
                with fixed_maze(2, 1, self._ONE_WAY_GRID):
                    core = GameCore()
                    huge_steps = tuple(
                        (label, 10**6) for label, _ in GameCore.SPEED_STEPS
                    )
                    with patch.object(GameCore, "SPEED_STEPS", huge_steps):
                        for _ in range(press_count):
                            self._press(core, self._SPEED_INSIDE_POINT)
                            self._release(core, self._SPEED_INSIDE_POINT)

                    # 切り替え直後は _frame_count がリセットされ、切り替えを
                    # 確定させた release() 自体が新しい間隔の1フレーム目にあたる
                    # ため(ID-008-13。設計方針3の案A)、直前に切り替えたかどうかだけで
                    # 経過フレーム数が決まり、切り替え回数(press_count)には依存しない
                    # (GameCore 内部のフレーム数・段階は直接読まない)
                    speed_index = (GameCore.INITIAL_SPEED_INDEX + press_count) % len(
                        GameCore.SPEED_STEPS
                    )
                    speed_label, interval = GameCore.SPEED_STEPS[speed_index]
                    frames_since_switch = 1 if press_count > 0 else 0
                    frames_to_next_kick = interval - frames_since_switch

                    for _ in range(frames_to_next_kick - 1):
                        core.update()
                    core.draw()
                    self.assertEqual(
                        self._expected_calls(0, 0, {(0, 0)}, speed_label),
                        self.test_view.get_call_params(),
                    )

                    self.test_view.call_params.clear()
                    core.update()
                    core.draw()
                    self.assertEqual(
                        self._expected_calls(
                            1,
                            0,
                            {(0, 0), (1, 0)},
                            speed_label,
                            state=GameState.CLEARED,
                        ),
                        self.test_view.get_call_params(),
                    )


class TestGameCoreExplorationResultUnaffectedBySpeed(TestParent):
    """ID-008-8: スピードを変えても、モブの進路・探索結果が変わらないこと(要件3.8)"""

    # 分岐のある盤面(TestGameCoreButtonInput._BRANCH_GRID と同一盤面。重複は意図的
    # 〈ID-003_subtasks.md「テスト戦略」参照〉)
    # pylint: disable-next=duplicate-code
    _BRANCH_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT, Direction.DOWN},
        (2, 0): {Direction.LEFT},
        (1, 1): {Direction.UP},
    }

    def test_exploration_result_is_unaffected_by_speed(self):
        """スピードを変えても、モブの進路・探索結果(到達セル)が変わらないこと
        (要件3.8)。分岐のある同じ盤面・同じ乱数の戻り値で、3段階それぞれの速度で
        最後まで探索させても、同じ最終状態(スタートへ帰還してゲームオーバー)に
        至ることを確認する(段階は INITIAL_SPEED_INDEX を差し替えて設定する。
        探索結果が乱数の戻り値のみで決まり移動間隔に依存しないことの確認が目的のため、
        ボタン操作を介さない直接的な設定で十分とする)"""
        for speed_index, (label, interval) in enumerate(GameCore.SPEED_STEPS):
            with fixed_maze(3, 2, self._BRANCH_GRID), patch.object(
                GameCore, "INITIAL_SPEED_INDEX", speed_index
            ), patch("src.main.random.choice", return_value=Direction.RIGHT):
                core = GameCore()
                # 行き止まりを2回たどってゲームオーバーに至るまで、この速度の間隔で
                # 十分に進める(必要なキック数は速度に依存しないため、間隔の倍数で足りる)
                for _ in range(interval * 20):
                    core.update()
                core.draw()
            visited_cells = {(0, 0), (1, 0), (2, 0), (1, 1)}
            expected = [("cls", 0)]
            for row in range(2):
                for col in range(3):
                    connections = frozenset(self._BRANCH_GRID.get((col, row), ()))
                    tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                        connections
                    )
                    expected += _cell_calls(
                        col, row, tile_origin, _color_for((col, row), visited_cells)
                    )
            expected += _arrow_calls(3, 2)
            expected += _mob_calls(0, 0)
            expected += _speed_button_calls(label)
            expected += _pause_button_calls()
            expected += _button_calls()
            expected += _score_calls(_expected_score(3, 2, visited_cells))
            expected += _popup_calls(GameState.GAME_OVER)
            self.assertEqual(expected, self.test_view.get_call_params())
            self.test_view.call_params.clear()


class TestGameCoreSpeedSwitchDoesNotBreakMovement(_PressReleaseMixin, TestParent):
    """ID-008-11: 移動間隔を切り替えた直後も、モブの移動が破綻しないこと(設計方針3)

    観測は _frame_count を直接読まず、切り替え直後・切り替え後の新しい間隔ちょうどの
    タイミングで描画されるモブの座標から行う(段階そのものを直接読むテストは作らない、
    という本ファイル全体の方針と同型。ID-008_subtasks.md「TDD サイクル 008-4」)。
    ID-008-16のプレイテストでSPEED_STEPSが6/3/1フレームに確定したことに伴い、
    段階は"遅い→速い"の一方向にしか循環しない(6→3→1→6…)。このため両方向の確認には
    最速(1フレーム)から最低速(6フレーム)への一周(wrap)を経由する必要があり、
    遅い→速い(6→3フレーム)・速い→速い(3→1フレーム)・速い→遅い(1→6フレーム、wrap)の
    3回の切り替えを1つの連続したシナリオでまとめて確認する。
    """

    # 8列1行の一本道。ゴール(7,0)まで十分な余裕を持たせ、3回の切り替えと
    # そのすべての移動がゴール到達(ポップアップ表示)前に収まるようにする
    _ONE_WAY_GRID = {
        (col, 0): frozenset(
            d
            for d, cond in (
                (Direction.LEFT, col > 0),
                (Direction.RIGHT, col < 7),
            )
            if cond
        )
        for col in range(8)
    }
    _SPEED_INSIDE_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X,
        GameCore.SPEED_BUTTON_CENTER_Y,
    )

    def _expected_calls(self, mob_col, speed_label):
        """_ONE_WAY_GRID を描いた後、モブが (mob_col, 0) にいる場合の期待描画列
        (探索中のみを扱うシナリオのため state は常に EXPLORING)"""
        visited = {(col, 0) for col in range(mob_col + 1)}
        expected = [("cls", 0)]
        for col in range(8):
            connections = frozenset(self._ONE_WAY_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(col, 0, tile_origin, _color_for((col, 0), visited))
        expected += _arrow_calls(8, 1)
        expected += _mob_calls(mob_col, 0)
        expected += _speed_button_calls(speed_label)
        expected += _pause_button_calls()
        expected += _button_calls()
        expected += _score_calls(_expected_score(8, 1, visited))
        expected += _popup_calls(GameState.EXPLORING)
        return expected

    def _assert_mob_at(self, core, mob_col, speed_label):
        self.test_view.call_params.clear()
        core.draw()
        self.assertEqual(
            self._expected_calls(mob_col, speed_label),
            self.test_view.get_call_params(),
        )

    def test_switch_does_not_cause_abrupt_move_or_stall_in_either_direction(self):
        """遅い→速い・速い→遅いの両方向で、切り替え直後にモブが動かず(急加速しない)、
        切り替え後の新しい間隔ちょうどのフレーム数で最初の移動が起きること
        (止まらない)を確認する。いずれも前回の移動(または生成直後)から数フレーム
        経過した途中で切り替える"""
        with fixed_maze(8, 1, self._ONE_WAY_GRID):
            core = GameCore()

            # 初期段階(">" = 6フレーム)の途中(4フレーム経過。まだ動かない)で
            # 中段(">>" = 3フレーム)へ切り替える(遅い→速い)
            for _ in range(4):
                core.update()
            self._assert_mob_at(core, 0, ">")  # 切り替え前。まだ動いていない

            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)  # ここで切り替えが確定する
            self._assert_mob_at(core, 0, ">>")  # 切り替え直後。急加速していない

            core.update()  # 新しい間隔(3フレーム)のうち2フレーム目
            self._assert_mob_at(core, 0, ">>")  # まだ動かない

            core.update()  # 3フレーム目。新しい間隔ちょうどで最初の移動が起きる
            self._assert_mob_at(core, 1, ">>")

            # 新しい間隔(3フレーム)の途中(1フレーム経過。まだ動かない)で
            # 最速(">>>" = 1フレーム)へ切り替える(速い→さらに速い)
            core.update()
            self._assert_mob_at(core, 1, ">>")

            self._press(core, self._SPEED_INSIDE_POINT)
            # 間隔が1フレームになるため、切り替えを確定させたこのフレーム自体が
            # 新しい間隔のちょうど1フレーム目にあたり、この release() の中で
            # 即座に1回だけ移動が起きる(急加速ではなく、新しい間隔(1フレーム)
            # ちょうどで最初の移動が起きるという同じ仕様の結果。ID-008-12の
            # `_frame_count` リセット→加算の順序どおり)
            self._release(core, self._SPEED_INSIDE_POINT)
            self._assert_mob_at(core, 2, ">>>")

            core.update()  # 間隔1フレームのため、次のフレームでも移動が起きる
            self._assert_mob_at(core, 3, ">>>")

            # 間隔1フレームでは毎フレーム移動するため「途中」は存在しない。
            # 直前の移動と同じフレームでボタンを押し、最低速(">" = 6フレーム)へ
            # 切り替える(速い→遅い。3段階の循環における唯一の減速方向はこの
            # wrap(">>>"→">")のみ)。押した時点ではまだ旧間隔(1フレーム)が
            # 有効なため、press() 自体でもう1回移動が起きる
            self._press(core, self._SPEED_INSIDE_POINT)
            self._release(core, self._SPEED_INSIDE_POINT)  # ここで切り替えが確定する
            self._assert_mob_at(core, 4, ">")  # 切り替え直後。止まったまま動いていない

            for _ in range(4):  # 新しい間隔(6フレーム)のうち2〜5フレーム目
                core.update()
                self._assert_mob_at(core, 4, ">")

            core.update()  # 6フレーム目。新しい間隔ちょうどで最初の移動が起きる
            self._assert_mob_at(core, 5, ">")
            self.test_view.call_params.clear()


class TestGameCorePauseHaltsOnlyMovement(
    _AdvanceOnceMixin, _PressReleaseMixin, TestParent
):
    """ID-009-8: ポーズが止めるのは「モブの移動」だけであること(tasks.md ID-009 完了条件)

    移動の停止と「教える」の継続を同じテストクラスで固定する(ID-009_subtasks.md
    「TDDサイクル009-3」)。`_paused` を直接読むテストは書かず、モブの描画位置と
    ブロックの描画で観測する(振る舞いベーステスト。GUIテスト設計ガイド)。
    """

    # 3列1行、(0,0)→(1,0)→(2,0) の一本道(TestGameCoreButtonInput._THREE_CELL_GRID と
    # 同一盤面。重複は意図的〈ID-003_subtasks.md「テスト戦略」参照〉)
    # pylint: disable-next=duplicate-code
    _THREE_CELL_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }

    _TEACH_INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    _PAUSE_INSIDE_POINT = (
        GameCore.PAUSE_BUTTON_CENTER_X,
        GameCore.PAUSE_BUTTON_CENTER_Y,
    )

    def _toggle_pause(self, core):
        """ポーズボタンを円内で押して円内で離し、ポーズ状態をトグルする"""
        self._press(core, self._PAUSE_INSIDE_POINT)
        self._release(core, self._PAUSE_INSIDE_POINT)

    def _expected_calls(
        self,
        mob_col,
        mob_row,
        visited_cells,
        blocked_cells=frozenset(),
        paused=False,
        state=GameState.EXPLORING,
    ):
        """_THREE_CELL_GRID を描いた後の期待描画列
        (TestGameCoreButtonInput._three_cell_maze_expected_calls と同型。
        paused はポーズボタンの塗り色にのみ反映する)"""
        expected = [("cls", 0)]
        for col in range(3):
            connections = frozenset(self._THREE_CELL_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(
                col, 0, tile_origin, _color_for((col, 0), visited_cells)
            )
        expected += _arrow_calls(3, 1)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls()
        pause_fill_color = GameCore.COLOR_BUTTON_PAUSED if paused else 0
        expected += _pause_button_calls(fill_color=pause_fill_color)
        expected += _button_calls()
        score = _expected_score(3, 1, visited_cells, blocked_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_mob_does_not_move_while_paused_and_moves_again_after_unpausing(self):
        """ポーズ中は、移動間隔ぶん update() を進めてもモブが動かないこと。
        ポーズを解除すると、モブが再び動くこと(完了条件の該当箇所)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._toggle_pause(core)  # ポーズON
            self._advance_once(core)  # 移動間隔ぶん進めても動かないはず
            core.draw()
            self.assertEqual(
                self._expected_calls(1, 0, {(0, 0), (1, 0)}, paused=True),
                self.test_view.get_call_params(),
            )

            self.test_view.call_params.clear()
            self._toggle_pause(core)  # ポーズOFF
            # 解除後、移動間隔ぶん update() を進めれば必ず1回はキックのタイミングを
            # 跨ぐため、ゴール(2,0)へ到達しクリアになる
            self._advance_once(core)
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    2, 0, {(0, 0), (1, 0), (2, 0)}, state=GameState.CLEARED
                ),
                self.test_view.get_call_params(),
            )

    def test_teaching_while_paused_places_block_and_affects_exploration_after_unpausing(
        self,
    ):
        """ポーズ中に「教える」ボタンを押下すると、その場にブロックが置かれること
        (ポーズが「教える」まで止めていないことの検出)。そのブロックが解除後の
        探索に反映され、そのセルから先へ進まず後退することも合わせて確認する"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._toggle_pause(core)  # ポーズON
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # (1,0) にブロック
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    1, 0, {(0, 0), (1, 0)}, blocked_cells={(1, 0)}, paused=True
                ),
                self.test_view.get_call_params(),
            )

            self.test_view.call_params.clear()
            self._toggle_pause(core)  # ポーズOFF
            # 教えた (1,0) から先へ進めないため、解除後は (0,0) へ後退する。
            # 後退し切ると進める道がなくなりゲームオーバーになる
            self._advance_once(core)
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    0,
                    0,
                    {(0, 0), (1, 0)},
                    blocked_cells={(1, 0)},
                    state=GameState.GAME_OVER,
                ),
                self.test_view.get_call_params(),
            )

    def test_pausing_does_not_change_maze_or_existing_block_drawing(self):
        """ポーズしても、迷路・探索済み経路・既存のブロックの描画が変わらないこと
        (ポーズ前に置いたブロックを例に確認する)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # ポーズ前に (1,0) にブロック
            self.test_view.call_params.clear()
            self._toggle_pause(core)  # ポーズON(移動・「教える」は行わない)
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    1, 0, {(0, 0), (1, 0)}, blocked_cells={(1, 0)}, paused=True
                ),
                self.test_view.get_call_params(),
            )


class TestGameCoreSpeedButtonUnpauses(
    _AdvanceOnceMixin, _PressReleaseMixin, TestParent
):
    """ID-009-18: ポーズ中にスピード変更ボタンを押すと、スピード段階は変えずに
    ポーズだけが解除されること(ID-009_subtasks.md「TDD サイクル 009-5」)。

    当初(ID-009-11)は「段階の切り替えとポーズの解除が同時に起きる」仕様で
    実装したが、プレイテスト(ID-009-16)で「切り替えと解除が同時に起きることに
    違和感がある」という指摘を受け、tasks.md ID-009 完了条件を「スピード段階は
    変えずに解除する」へ変更した(ユーザー指示。2026-09-11)。

    観測はこれまでと同様、スピードボタンのラベル・ポーズボタンの塗り色・モブの
    描画位置で行う(`_paused` を直接読むテストは作らない。振る舞いベーステスト)。
    3列1行の一本道(TestGameCorePauseHaltsOnlyMovement._THREE_CELL_GRID と同一盤面。
    重複は意図的〈ID-003_subtasks.md「テスト戦略」参照〉)を使う。
    """

    # pylint: disable-next=duplicate-code
    _THREE_CELL_GRID = {
        (0, 0): {Direction.RIGHT},
        (1, 0): {Direction.LEFT, Direction.RIGHT},
        (2, 0): {Direction.LEFT},
    }

    _TEACH_INSIDE_POINT = (GameCore.BUTTON_CENTER_X, GameCore.BUTTON_CENTER_Y)
    _PAUSE_INSIDE_POINT = (
        GameCore.PAUSE_BUTTON_CENTER_X,
        GameCore.PAUSE_BUTTON_CENTER_Y,
    )
    _SPEED_INSIDE_POINT = (
        GameCore.SPEED_BUTTON_CENTER_X,
        GameCore.SPEED_BUTTON_CENTER_Y,
    )

    def _toggle_pause(self, core):
        """ポーズボタンを円内で押して円内で離し、ポーズ状態をトグルする
        (TestGameCorePauseHaltsOnlyMovement._toggle_pause と同型)"""
        self._press(core, self._PAUSE_INSIDE_POINT)
        self._release(core, self._PAUSE_INSIDE_POINT)

    def _press_speed(self, core):
        """スピード変更ボタンを円内で押して円内で離す"""
        self._press(core, self._SPEED_INSIDE_POINT)
        self._release(core, self._SPEED_INSIDE_POINT)

    def _expected_calls(
        self,
        mob_col,
        mob_row,
        visited_cells,
        blocked_cells=frozenset(),
        speed_label=GameCore.SPEED_STEPS[GameCore.INITIAL_SPEED_INDEX][0],
        paused=False,
        state=GameState.EXPLORING,
    ):
        """_THREE_CELL_GRID を描いた後の期待描画列(TestGameCorePauseHaltsOnlyMovement
        ._expected_calls と同型。speed_label が加わっている)"""
        expected = [("cls", 0)]
        for col in range(3):
            connections = frozenset(self._THREE_CELL_GRID.get((col, 0), ()))
            tile_origin = GameCore._get_tile_origin(  # pylint: disable=W0212
                connections
            )
            expected += _cell_calls(
                col, 0, tile_origin, _color_for((col, 0), visited_cells)
            )
        expected += _arrow_calls(3, 1)
        expected += _block_calls(blocked_cells)
        expected += _mob_calls(mob_col, mob_row)
        expected += _speed_button_calls(speed_label)
        pause_fill_color = GameCore.COLOR_BUTTON_PAUSED if paused else 0
        expected += _pause_button_calls(fill_color=pause_fill_color)
        expected += _button_calls()
        score = _expected_score(3, 1, visited_cells, blocked_cells)
        expected += _score_calls(score)
        expected += _popup_calls(state, score)
        return expected

    def test_speed_button_while_paused_only_unpauses_and_keeps_speed(self):
        """ポーズ中にスピード変更ボタンを円内で押して円内で離すと、スピード段階の
        ラベルは変わらず、ポーズだけが解除される(塗り色が通常へ戻る)こと
        (ID-009-18 Red。tasks.md ID-009 完了条件の変更を反映)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._toggle_pause(core)  # ポーズON
            self._press_speed(
                core
            )  # ポーズ中にスピード変更ボタンを押して離す(解除のみ)
            core.draw()
            self.assertEqual(
                self._expected_calls(1, 0, {(0, 0), (1, 0)}),
                self.test_view.get_call_params(),
            )

    def test_mob_moves_again_at_original_interval_after_speed_unpauses(self):
        """ポーズ中のスピード変更ボタン押下で解除された後、モブが元の(変更前の)
        間隔で動くこと(段階を変えていないため、フレーム位相もポーズ前の続きから
        進む。ポーズボタンでの解除〈ID-009-10〉と同じ位相の扱い)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)。frame_count == I
            self._toggle_pause(core)  # ポーズON。press() 分の1フレームが加算され I+1
            self._press_speed(core)  # ポーズ中にスピード変更ボタンで解除。release()
            # 自体は解除後の1フレームとして加算される(_paused が False になった
            # 後に frame_count の加算判定へ到達するため)ので、ここで I+2 になる。
            # 段階を変えていないため間隔は元の I のままで、次のキックは frame_count
            # が 2*I に達したとき。あと (I - 2) 回の update() が必要になる
            # (GameCore 内部の frame_count は直接読まない)。最後の1回を切り分けて、
            # その手前までは動かないことを確認する
            for _ in range(_INITIAL_MOVE_INTERVAL_FRAMES - 3):
                core.update()
            core.draw()
            self.assertEqual(
                self._expected_calls(1, 0, {(0, 0), (1, 0)}),
                self.test_view.get_call_params(),
            )

            self.test_view.call_params.clear()
            core.update()  # 2*I ちょうど。ゴール(2,0)へ到達しクリアになる
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    2,
                    0,
                    {(0, 0), (1, 0), (2, 0)},
                    state=GameState.CLEARED,
                ),
                self.test_view.get_call_params(),
            )

    def test_pressing_speed_button_while_unpaused_still_only_advances_speed(self):
        """ポーズ解除中のスピード変更ボタン押下は、従来どおり段階が進むだけである
        こと(回帰。ID-008 の振る舞いを壊さない)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._press_speed(core)  # ポーズしていない状態でスピード変更ボタンを押す
            core.draw()
            self.assertEqual(
                self._expected_calls(1, 0, {(0, 0), (1, 0)}, speed_label=">>"),
                self.test_view.get_call_params(),
            )

    def test_pressing_teach_button_while_paused_does_not_unpause(self):
        """ポーズ中に「教える」ボタンを押下しても、ポーズは解除されないこと
        (解除経路は2つだけであり、「教える」は3つ目の解除経路ではない。
        requirements.md 3.8 に列挙が無いため)"""
        with fixed_maze(3, 1, self._THREE_CELL_GRID):
            core = GameCore()
            self._advance_once(core)  # (0,0) -> (1,0)
            self._toggle_pause(core)  # ポーズON
            self._press(core, self._TEACH_INSIDE_POINT)
            self._release(core, self._TEACH_INSIDE_POINT)  # (1,0) にブロック
            core.draw()
            self.assertEqual(
                self._expected_calls(
                    1, 0, {(0, 0), (1, 0)}, blocked_cells={(1, 0)}, paused=True
                ),
                self.test_view.get_call_params(),
            )
