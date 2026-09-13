# title: pyxel_maze_guide
# author: masatobu

import random
from abc import ABC, abstractmethod
from enum import Enum


class IView(ABC):
    @abstractmethod
    def cls(self, color):
        pass

    @abstractmethod
    def rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def blt(self, x, y, img, u, v, w, h, colkey):
        pass

    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def circ(self, x, y, r, color):
        pass

    @abstractmethod
    def circb(self, x, y, r, color):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def cls(self, color):
        self.pyxel.cls(color)

    def rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def circ(self, x, y, r, color):
        self.pyxel.circ(x, y, r, color)

    def circb(self, x, y, r, color):
        self.pyxel.circb(x, y, r, color)


class IInput(ABC):
    """`pyxel_break_blocks` の `IInput` を参照点にする（ID-006_subtasks.md「参考実装」）"""

    @abstractmethod
    def is_btn_pressed(self) -> bool:
        pass

    @abstractmethod
    def is_btn_down(self) -> bool:
        pass

    @abstractmethod
    def is_btn_released(self) -> bool:
        pass

    @property
    @abstractmethod
    def mouse_x(self) -> int:
        pass

    @property
    @abstractmethod
    def mouse_y(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def is_btn_down(self) -> bool:
        return self.pyxel.btn(self.pyxel.MOUSE_BUTTON_LEFT)

    def is_btn_released(self) -> bool:
        return self.pyxel.btnr(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


class GameState(Enum):
    """探索中/クリア/ゲームオーバーの3値。`Maze` の外へは持ち出さず、
    モブの位置と探索状況から毎回導出する（フラグとして持たない。ID-007-1 未決事項1）"""

    EXPLORING = "exploring"
    CLEARED = "cleared"
    GAME_OVER = "game_over"


class Maze:
    # (200 - 10 x 2) / 4。左右マージン 10px = 矢印 `->`（8px 幅）+ 内外 1px ずつの余白
    COLS = 45
    ROWS = 60
    START = (0, 0)
    GOAL = (COLS - 1, ROWS - 1)
    # スコアの初期値の係数（道1セルあたり）。ゲームルールのため Maze のクラス変数に置く
    SCORE_PER_CELL = 10
    # スコアの減算係数（ブロック1個あたり）。ゲームルールのため Maze のクラス変数に置く
    SCORE_PER_BLOCK = 100

    _NEIGHBOR_OFFSET = {
        Direction.UP: (0, -1),
        Direction.DOWN: (0, 1),
        Direction.LEFT: (-1, 0),
        Direction.RIGHT: (1, 0),
    }
    _OPPOSITE = {
        Direction.UP: Direction.DOWN,
        Direction.DOWN: Direction.UP,
        Direction.LEFT: Direction.RIGHT,
        Direction.RIGHT: Direction.LEFT,
    }

    def __init__(self):
        # `_generate()` が返す各セルの接続集合は、この時点（`_open_gates()` までの
        # 書き換えが終わった後）で不変になるため、ここで一度だけ `frozenset` にし、
        # `get_connections()` での毎回の防御的コピーを不要にする（ID-011 方針A-ii）。
        self._connections = {
            position: frozenset(directions)
            for position, directions in self._generate().items()
        }
        self._mob_position = self.START
        self._visited_positions = {self.START}
        self._path = [self.START]
        self._blocked_positions = set()

    def get_connections(self, col, row):
        return self._connections.get((col, row), frozenset())

    def get_mob_position(self):
        return self._mob_position

    def is_visited(self, col, row):
        return (col, row) in self._visited_positions

    @property
    def score(self):
        """探索の効率を表すスコア。道の全セル数のうち、まだ新しく到達して
        いないセルの数に応じて決まる（スタート分は最初から到達済みとして
        数えない）。新しく置かれたブロックの数に応じてさらに減る"""
        total_cells = self.COLS * self.ROWS
        reached_cells = len(self._visited_positions) - 1  # スタートの分を除く
        unreached_score = (total_cells - reached_cells) * self.SCORE_PER_CELL
        block_penalty = len(self._blocked_positions) * self.SCORE_PER_BLOCK
        return unreached_score - block_penalty

    def teach(self):
        """その時点でモブがいるセルにブロックを置く"""
        self._blocked_positions.add(self._mob_position)

    @property
    def state(self):
        """モブの位置と探索状況から一意に決まるゲーム状態（新しい状態変数は持たない）"""
        if self._mob_position == self.GOAL:
            return GameState.CLEARED
        col, row = self._mob_position
        if self._mob_position == self.START and not list(
            self._unexplored_directions(col, row)
        ):
            return GameState.GAME_OVER
        return GameState.EXPLORING

    def _is_blocked(self, col, row):
        return (col, row) in self._blocked_positions

    def get_blocked_positions(self):
        """ブロックのある全セルを列→行の昇順で返す(描画順を安定させるため)"""
        return sorted(self._blocked_positions)

    def kick(self):
        """探索中でなくなった（クリア／ゲームオーバー）時点でキックは何もしない。
        `state` と同じ「位置と探索状況」から導出されるため、停止条件を
        別々に持たない（ID-007-4 Refactor。停止条件と状態判定の重複を解消）"""
        if self.state != GameState.EXPLORING:
            return
        col, row = self._mob_position
        candidates = list(self._unexplored_directions(col, row))
        direction = self._choose_direction(candidates)
        if direction is not None:
            self._advance(col, row, direction)
        else:
            # 探索中かつ未探索方向がない = 行き止まり。スタートでの行き止まりは
            # 上の state チェックで GAME_OVER として弾かれているため、
            # ここに到達する時点で必ず後退できる（`_path` は長さ 2 以上）
            self._retreat()

    def _advance(self, col, row, direction):
        """未探索の道へ 1 セル進み、訪問済みとして記録する"""
        self._mob_position = self._neighbor(col, row, direction)
        self._visited_positions.add(self._mob_position)
        self._path.append(self._mob_position)

    def _retreat(self):
        """行き止まりで、来た道を 1 セル戻る"""
        self._path.pop()
        self._mob_position = self._path[-1]

    def _reachable_directions(self, col, row):
        """現在セルの道から、迷路の外へ出る道（入口）を除いた方向"""
        return (
            direction
            for direction in self.get_connections(col, row)
            if self._in_range(*self._neighbor(col, row, direction))
        )

    def _unexplored_directions(self, col, row):
        """`_reachable_directions` から、探索済みのセルへ向かう方向を除いた方向。
        現在セルにブロックが置かれている場合は、そこから先へ進まないため
        候補なしとする（戻るモードは、この空の候補から `kick()` が導出する）"""
        if self._is_blocked(col, row):
            return iter(())
        return (
            direction
            for direction in self._reachable_directions(col, row)
            if not self.is_visited(*self._neighbor(col, row, direction))
        )

    @staticmethod
    def _choose_direction(candidates):
        """候補が複数あるときだけ乱数で選ぶ（分岐でのみ乱数を消費する）"""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        return random.choice(candidates)

    def _neighbor(self, col, row, direction):
        dcol, drow = self._NEIGHBOR_OFFSET[direction]
        return (col + dcol, row + drow)

    def _in_range(self, col, row):
        return 0 <= col < self.COLS and 0 <= row < self.ROWS

    def _unvisited_neighbors(self, col, row, visited):
        for direction in Direction:
            neighbor = self._neighbor(col, row, direction)
            if self._in_range(*neighbor) and neighbor not in visited:
                yield direction, neighbor

    def _generate(self):
        connections = {
            (col, row): set() for col in range(self.COLS) for row in range(self.ROWS)
        }
        visited = {self.START}
        stack = [self.START]
        while stack:
            col, row = stack[-1]
            candidates = list(self._unvisited_neighbors(col, row, visited))
            if not candidates:
                stack.pop()
                continue
            direction, next_cell = random.choice(candidates)
            connections[(col, row)].add(direction)
            connections[next_cell].add(self._OPPOSITE[direction])
            visited.add(next_cell)
            stack.append(next_cell)
        self._open_gates(connections)
        return connections

    def _open_gates(self, connections):
        connections[self.START].add(Direction.LEFT)
        connections[self.GOAL].add(Direction.RIGHT)


class GameCore:
    CELL_SIZE = 4
    MAZE_X = 10  # 左マージン 10px（矢印 8px + 迷路との余白 2px、外側の余白は 0px）
    MAZE_Y = 4
    TILE_IMAGE_BANK = 0
    TILE_COLKEY = 0
    COLOR_UNEXPLORED = 1
    COLOR_VISITED = 3  # ID-004-13 のプレイテストで確定した値
    MOB_SIZE = 2
    COLOR_MOB = 10  # 黄色
    BLOCK_SIZE = 2  # ユーザー指定。モブ(MOB_SIZE)と同じ大きさ
    COLOR_BLOCK = 8  # 赤。ID-006-25 のプレイテストで確定する
    TEXT_WIDTH = 4  # Pyxel 標準フォントの 1 文字の幅
    TEXT_HEIGHT = 6  # Pyxel 標準フォントの 1 文字の高さ
    ARROW_TEXT = "->"
    GATE_ARROW_GAP = 2  # 矢印と迷路画像の間に空ける余白(px)

    # 「教える」ボタン（ID-006_subtasks.md「ボタンとブロックの見た目」の仮値。
    # ID-006-25 のプレイテストで確定する）
    BUTTON_CENTER_X = 176
    BUTTON_CENTER_Y = 272
    BUTTON_RADIUS = 18
    BUTTON_LABEL = "STOP"
    COLOR_BUTTON_NORMAL = 7  # 白(矢印・ラベルの既定色と同系統)
    COLOR_BUTTON_PRESSED = 12  # 水色。ID-006-25 のプレイテストで確定する
    # Pyxel標準フォントの見た目上の重心が左上寄りに見えるため、ラベルを右下へ1px補正する
    # ID-006-4のXvfb目視確認で調整
    BUTTON_LABEL_OFFSET = 1

    # スピード変更ボタン（ID-008_subtasks.md「設計方針6」の仮値。ID-008-16のプレイテストで
    # 確定する）。中央 x=100 はスコア表示に譲り、サブボタンとして「教える」ボタンより
    # 小さい半径にする（中間ビルドのプレイテストでのユーザー指示。2026-09-09）
    # 「教える」ボタン(BUTTON_RADIUS=18)の2/3。サブボタン的な位置付けを大きさで示す
    SPEED_BUTTON_RADIUS = 12
    # 画面の左端・下端に、「教える」ボタンと画面右端・下端との隙間(6px / 10px。
    # App.SCREEN_WIDTH=200・SCREEN_HEIGHT=300 に対する BUTTON_CENTER_X/Y ± BUTTON_RADIUS の
    # 差)と同じ幅の余白を残して配置する(2回目のプレイテストでのユーザー指示。2026-09-09)。
    # ポーズボタン(ID-009)はこのボタンの右隣に置く想定
    SPEED_BUTTON_CENTER_X = SPEED_BUTTON_RADIUS + 6  # 6px = 200 - (176 + 18)
    SPEED_BUTTON_CENTER_Y = 300 - 10 - SPEED_BUTTON_RADIUS  # 10px = 300 - (272 + 18)
    # 占有範囲 x 6..30 / y 266..290 は、迷路(y<=243)・出口の矢印(x 192..199)・
    # 「教える」ボタン(x 158..194)・スコア表示予定地(中央 x=100)のいずれとも重ならない
    # スピード段階の(ラベル, 移動間隔フレーム数)の並び(設計方針1)。添字が現在の段階を
    # 表す(_speed_index)。循環は (index + 1) % len(...) の1行(pyxel_shop_grow ID-019 と
    # 同型の書き方)。移動間隔をここへ一本化し、`MOVE_INTERVAL_FRAMES` は廃止した
    # (同じ値を指す定数の二重管理を避けるため。ID-008-3 Refactor/ID-008-10 で決着)。
    # フレーム数(6/3/1)はID-008-16のプレイテストで確定した値
    # (仮値12/6/3では最低速が間延びして見えたため、全体を1段階ずつ詰めた)
    SPEED_STEPS = ((">", 6), (">>", 3), (">>>", 1))
    # 初期段階は現行の見え方(6フレーム間隔)を保つ段階(">")から始める（設計方針2。
    # ID-003-34 のプレイテストで確定した体感を、ゲーム開始時の既定として保つため。
    # ID-008-16 の値見直しで6フレームが段階0(">")の位置へ移ったため、初期段階も
    # あわせて0へ変更した）
    INITIAL_SPEED_INDEX = 0

    # ポーズボタン（ID-009_subtasks.md「設計方針5」の仮値。ID-009-16のプレイテストで
    # 確定する）。スピード変更ボタンのすぐ右に、中心線を揃えて配置する
    # （ユーザー指示。2026-09-09。ID-008からの申し送り）。半径はスピード変更ボタンと
    # 同じ12とし、サブボタンとしての位置付けを揃える
    PAUSE_BUTTON_RADIUS = 12
    PAUSE_BUTTON_CENTER_Y = SPEED_BUTTON_CENTER_Y  # 中心線をスピード変更ボタンと揃える
    # 隙間6pxは、SPEED_BUTTON_CENTER_X の導出根拠(画面端との隙間6px)をそのまま
    # 横へ延長した値(設計方針5の候補のうち根拠が最も強いもの。プレイテストで見直す)
    PAUSE_BUTTON_GAP = 6
    PAUSE_BUTTON_CENTER_X = (
        SPEED_BUTTON_CENTER_X
        + SPEED_BUTTON_RADIUS
        + PAUSE_BUTTON_GAP
        + PAUSE_BUTTON_RADIUS
    )
    # 占有範囲 x 36..60 / y 266..290 は、迷路(y<=243)・出口の矢印(x 192..199)・
    # スピード変更ボタン(x 6..30)・「教える」ボタン(x 158..194)・
    # スコア表示予定地(中央 x=100)のいずれとも重ならない
    # ラベルは状態によらず"||"で固定する(設計方針2の案C。ユーザー指示により
    # 案Aのラベルトグルから変更。ID-009-7 Refactor)
    PAUSE_BUTTON_LABEL = "||"
    # ポーズ中の塗り色(ユーザー指示。2026-09-11。プレイテストで5へ変更)
    COLOR_BUTTON_PAUSED = 5

    # スコア表示(ID-010_subtasks.md「設計方針3」の仮値だったが、プレイテストの
    # ユーザー指示により「迷路に付随する表現」へ変更。2026-09-13)。
    # 迷路のすぐ下(サブボタン列より上)へ、迷路の中央線と同じ x で描く
    SCORE_CENTER_X = 100  # 画面幅200の中央(迷路の中央線とも一致)
    SCORE_MAZE_GAP = 2  # 迷路の下端との余白。矢印と迷路の間(GATE_ARROW_GAP)と同じ値
    SCORE_CENTER_Y = MAZE_Y + Maze.ROWS * CELL_SIZE + SCORE_MAZE_GAP

    # クリア/ゲームオーバーのポップアップ(ID-007_subtasks.md「ポップアップの見た目」の仮値。
    # ID-007-19 のプレイテストで確定する)。ID-010(設計方針5)でクリア時に3行目
    # (最終スコア)を追加するため、上下の余白(8pxずつ)を保ったまま3行が収まる
    # 高さへ広げた。クリア/ゲームオーバーで同じ箱を使う(行数はポップアップの
    # 描画時に行の並びから決める。ID-010-16)
    POPUP_W = 100
    POPUP_H = 38  # 3 * TEXT_HEIGHT + 2 * POPUP_LINE_GAP + 16(上下の余白8pxずつ)
    POPUP_X = 50  # (200 - POPUP_W) // 2。画面中央
    POPUP_Y = 105  # MAZE_Y + (ROWS * CELL_SIZE - POPUP_H) // 2。迷路領域の中央
    POPUP_BORDER_THICKNESS = 2
    POPUP_LINE_GAP = 2
    COLOR_POPUP_BG = 0  # 黒。迷路と重なっても文言が読めること
    COLOR_POPUP_BORDER = 7  # 白。矢印・ボタン枠と同系統
    TEXT_CLEAR = "CLEAR"
    TEXT_GAME_OVER = "GAME OVER"
    TEXT_RESTART = "TAP TO RESTART"
    # クリアポップアップ3行目のラベル(設計方針5の案A〈数値のみ〉から、
    # プレイテストの指摘「SCORE: と書いて数字を出してほしい」を受けて
    # 案B〈ラベル付き〉へ変更。2026-09-13)。画面下部の表示(ラベルなし。
    # requirements.md「スコア表示」)とは別の文言のため専用の定数にする
    POPUP_SCORE_PREFIX = "SCORE: "
    # 状態→1行目の文言の対応表。state が Enum であるため、分岐ではなく
    # 辞書のキーとして対応をそのまま書ける（ID-007-4 で Enum を選んだ理由と同じ。
    # ID-007-10 Refactor）。矩形・中央寄せの描画経路はクリア/ゲームオーバーで
    # 分岐させず、1行目の文言だけをここから引く
    _POPUP_LINE1_BY_STATE = {
        GameState.CLEARED: TEXT_CLEAR,
        GameState.GAME_OVER: TEXT_GAME_OVER,
    }

    # タイル画像内の描画起点の導出規則（tasks.md「画像リソース仕様」）:
    # 行 = 縦方向の接続、列 = 横方向の接続で決まり、(8 + 列 x 4, 行 x 4) が描画起点になる。
    # `_TILE_SIZE` は画像内のタイルサイズであり、画面上のセルサイズ `CELL_SIZE` とは
    # 値が同じ 4 でも指す対象が異なるため、共有せず別に保つ。
    _TILE_SHEET_X = 8
    _TILE_SIZE = 4
    # `_get_tile_origin()` が毎呼び出しで集合リテラルを再生成しないよう、縦方向・横方向の
    # 接続を判定するための集合をクラス定数として保持する（ID-011 方針A-i）。
    _VERTICAL_DIRECTIONS = frozenset({Direction.UP, Direction.DOWN})
    _HORIZONTAL_DIRECTIONS = frozenset({Direction.LEFT, Direction.RIGHT})
    _TILE_ROW = {
        frozenset({Direction.DOWN}): 0,
        frozenset({Direction.UP, Direction.DOWN}): 1,
        frozenset({Direction.UP}): 2,
        frozenset(): 3,
    }
    _TILE_COL = {
        frozenset({Direction.RIGHT}): 0,
        frozenset({Direction.LEFT, Direction.RIGHT}): 1,
        frozenset({Direction.LEFT}): 2,
        frozenset(): 3,
    }

    # 押下対象を表す3つの値。「教える」・スピード変更・ポーズのどの円で押下が
    # 始まったかを _armed_button 1つで記録するために使う（設計方針4。文字列比較の
    # 誤りを防ぐためリテラルをここへ集約する。ポーズの追加はID-009-6 Green。
    # 3つ目を足しても分岐が1つ増えるだけで済んだため、設計方針3の一般化は
    # 見送った〈ID-009-7 Refactorで決着〉）
    _BUTTON_TEACH = "teach"
    _BUTTON_SPEED = "speed"
    _BUTTON_PAUSE = "pause"

    def __init__(self):
        self._view = PyxelView.create()
        self._input = PyxelInput.create()
        self._maze = Maze()
        # セルごとの背景描画起点(`_cell_origin()`)・タイル画像の参照位置
        # (`_get_tile_origin()`)は、迷路生成後は変化しない値であるにもかかわらず
        # 毎フレーム・全セル分（`_draw_maze()` から2,700セル）再計算されていたため、
        # ここで1度だけ表にしておく（ID-011 方針A-iii）
        self._cell_render_table = {
            (col, row): (
                *self._cell_origin(col, row),
                *self._get_tile_origin(self._maze.get_connections(col, row)),
            )
            for col in range(self._maze.COLS)
            for row in range(self._maze.ROWS)
        }
        # 3つのボタンラベルはいずれも文字列が定数（スピード変更ボタンだけ
        # `SPEED_STEPS` の3パターンを段階に応じて切り替える）であり、中心座標も
        # 定数のため、`_centered_text_x()` の結果は毎フレーム再計算せずここで
        # 1度だけ求めておく（ID-011 方針A-iv）
        self._button_label_x = (
            self._centered_text_x(self.BUTTON_CENTER_X, self.BUTTON_LABEL)
            + self.BUTTON_LABEL_OFFSET
        )
        self._pause_button_label_x = (
            self._centered_text_x(self.PAUSE_BUTTON_CENTER_X, self.PAUSE_BUTTON_LABEL)
            + self.BUTTON_LABEL_OFFSET
        )
        self._speed_button_label_x = tuple(
            self._centered_text_x(self.SPEED_BUTTON_CENTER_X, label)
            + self.BUTTON_LABEL_OFFSET
            for label, _ in self.SPEED_STEPS
        )
        # 入口(スタートの左)・出口(ゴールの右)の矢印2本の描画座標は、スタート・
        # ゴール地点が迷路サイズから決まる定数であるため、同様に1度だけ求める
        # （ID-011 方針A-iv）
        arrow_width = len(self.ARROW_TEXT) * self.TEXT_WIDTH
        gate_offset_y = (self.CELL_SIZE - self.TEXT_HEIGHT) // 2
        start_col, start_row = Maze.START
        goal_col, goal_row = Maze.GOAL
        self._gate_positions = (
            (
                self.MAZE_X
                + start_col * self.CELL_SIZE
                - arrow_width
                - self.GATE_ARROW_GAP,
                self.MAZE_Y + start_row * self.CELL_SIZE + gate_offset_y,
            ),
            (
                self.MAZE_X + (goal_col + 1) * self.CELL_SIZE + self.GATE_ARROW_GAP,
                self.MAZE_Y + goal_row * self.CELL_SIZE + gate_offset_y,
            ),
        )
        self._frame_count = 0
        # 押した瞬間にどちらのボタンの円の内側だったか（_BUTTON_TEACH / _BUTTON_SPEED /
        # 円外なら None）。離した瞬間も同じボタンの円の内側ならそのボタンを確定する
        # （ID-006_subtasks.md「離した瞬間に確定する理由」を2ボタンへ一般化。ID-008-7
        # Refactor。2つのボタンが同時にアームされることはない、という排他性を
        # 単一の値で表す。押下中の色（_draw_button / _draw_speed_button）もここから導出する）
        self._armed_button = None
        self._speed_index = self.INITIAL_SPEED_INDEX
        # ポーズ状態(押下でトグルされる真偽値。ID-009_subtasks.md「設計方針1」により
        # GameCore側に持つ。Maze.state のように位置から導出できる値ではないため、
        # `_needs_reset` と同じ扱いにする)
        self._paused = False
        # ポップアップ内クリックで真になる一過性の入力の記録（ID-007-14）。
        # 状態(GameState)から導出できないため、Maze 側には持たせず GameCore に持つ
        self._needs_reset = False

    @property
    def needs_reset(self):
        """ポップアップ内がクリックされ、`App` が `GameCore` を再生成すべきか"""
        return self._needs_reset

    def update(self):
        """探索中のときだけ、入力を確定させ探索を1ステップ進める。
        ポップアップ表示中(クリア/ゲームオーバー)は「教える」を確定させず、
        探索も止まったまま(ID-007-12。`kick()` 自身も同じ条件で自己停止するが、
        呼び出し側にも同じガードを置くことで意図を1箇所にまとめる)。
        `_frame_count` もガードの内側で加算する。停止中は参照されない値であり、
        加算し続ける理由がないため(ID-007-13 Refactor)。
        ポップアップ表示中は、代わりにポップアップ内クリックを検知する
        (ID-007-14。矩形外のクリックでは反応しない。ID-007-16 Refactor)。
        `_update_button_input()` を `_frame_count` の加算より先に呼ぶ(ID-008-12
        Green)。スピード切り替えが確定すると `_frame_count` が0へリセットされる
        (設計方針3の案A)ため、加算をその後に置くことで、切り替えが確定した
        このフレーム自体が新しい間隔の1フレーム目になる(0フレーム目のまま
        比較すると `0 % 間隔 == 0` で即座にキックしてしまうため、先にリセットして
        から1加算することで、切り替え直後のフレームでは動かないことを保証する)。
        ポーズ中は `_frame_count` を加算せずモブの移動だけを止める(設計方針4の
        案A)。このガードは必ず `_update_button_input()` より後ろに置く。前に置くと
        「教える」やポーズボタン自身の押下も届かなくなり、ポーズから抜けられなく
        なるため(tasks.md ID-009 備考が警告している経路。ID-009-10 Refactor)"""
        if self._maze.state != GameState.EXPLORING:
            if self._input.is_btn_pressed() and self._is_in_popup(
                self._input.mouse_x, self._input.mouse_y
            ):
                self._needs_reset = True
            return
        self._update_button_input()
        if self._paused:
            return
        self._frame_count += 1
        if self._frame_count % self._current_move_interval() == 0:
            self._maze.kick()

    def _current_move_interval(self):
        """現在のスピード段階に対応する移動間隔フレーム数(SPEED_STEPS の2要素目)"""
        return self.SPEED_STEPS[self._speed_index][1]

    def _update_button_input(self):
        """押した瞬間にどちらのボタンの円の内側だったかを _armed_button へ記録し、
        離した瞬間に同じボタンの円の内側であれば、そのボタンの動作を確定する
        （「教える」・スピード変更で共通。ID-006 で確立した「離した瞬間に確定する」
        判定を、円内判定の引数化(_is_in_circle)と _armed_button の単一化で
        2つのボタンへ一般化した。ID-008-7 Refactor）"""
        if self._input.is_btn_pressed():
            self._armed_button = self._button_at(
                self._input.mouse_x, self._input.mouse_y
            )
        elif self._input.is_btn_released():
            released_button = self._button_at(self._input.mouse_x, self._input.mouse_y)
            if self._armed_button is not None and self._armed_button == released_button:
                self._confirm(self._armed_button)
            self._armed_button = None

    def _button_at(self, x, y):
        """点 (x, y) が「教える」・スピード変更・ポーズのいずれかの円の内側にあれば、
        そのボタンを表す値を返す。どの円の内側でもなければ None"""
        if self._is_in_circle(
            x, y, self.BUTTON_CENTER_X, self.BUTTON_CENTER_Y, self.BUTTON_RADIUS
        ):
            return self._BUTTON_TEACH
        if self._is_in_circle(
            x,
            y,
            self.SPEED_BUTTON_CENTER_X,
            self.SPEED_BUTTON_CENTER_Y,
            self.SPEED_BUTTON_RADIUS,
        ):
            return self._BUTTON_SPEED
        if self._is_in_circle(
            x,
            y,
            self.PAUSE_BUTTON_CENTER_X,
            self.PAUSE_BUTTON_CENTER_Y,
            self.PAUSE_BUTTON_RADIUS,
        ):
            return self._BUTTON_PAUSE
        return None

    def _confirm(self, button):
        """円内で押して円内で離したボタンの動作を確定する。スピード切り替えでは
        `_frame_count` を0へリセットし、切り替え前の間隔での経過フレーム数(位相)を
        次の間隔へ持ち越さない(設計方針3の案A。ID-008-12 Green)。リセットしない
        場合、切り替え直後に急加速(新間隔に対しすでに満たしている剰余)や、
        一瞬の停止(旧間隔基準の位相が新間隔に対しずれる)が起こり得る。
        ポーズはトグルするだけで、`_frame_count` はここでは操作しない
        (ポーズ中のフレーム位相の扱いはID-009-10 Refactorで決着する。ID-009-6 Green)。
        スピード変更ボタンをポーズ中に押した場合は、段階を変えずポーズの解除だけを
        行う(プレイテストで「切り替えと解除が同時に起きることに違和感がある」
        という指摘を受け、tasks.md ID-009 完了条件を変更。ID-009-18〜19。当初の
        ID-009-12 Green は「段階を進めるのと同時に解除する」だったが撤回した)。
        段階を変えないため `_frame_count` のリセットも行わない
        (ポーズボタンでの解除〈トグルのみで `_frame_count` を操作しない〉と
        同じ扱いに揃う)。
        ポーズの解除経路は2つあるが、書き方は統一しない(`_paused = not self._paused`
        と `_paused = False` のまま。ID-009-13 Refactor)。ポーズボタン側は
        「押すたびに反転する」1つの入力に対する応答であり、トグルが自然な表現。
        スピードボタン側は「ポーズ中かどうかに関わらず必ず解除された状態にする」
        という副作用であり、現在値を読まない代入が意図を最も直接に表す
        (`not self._paused` にすると、まだポーズしていないときに誤って読める)。
        1行の代入を共有ヘルパーへ抽出しても行数は減らず、2箇所の意図の違いが
        かえって読み取りにくくなるため、抽出は見送る(設計方針3と同じ
        「無理に抽象化しない」の判断)"""
        if button == self._BUTTON_TEACH:
            self._maze.teach()
        elif button == self._BUTTON_PAUSE:
            self._paused = not self._paused
        elif self._paused:
            # スピード変更ボタンをポーズ中に押した場合: 段階は変えず解除のみ
            self._paused = False
        else:
            # スピード変更ボタンをポーズ解除中に押した場合: 従来どおり段階を進める
            self._speed_index = (self._speed_index + 1) % len(self.SPEED_STEPS)
            self._frame_count = 0

    @staticmethod
    def _is_in_circle(x, y, cx, cy, r):
        """点 (x, y) が中心 (cx, cy)・半径 r の円の内側にあるか（矩形ではなく
        中心からの距離で判定する）。「教える」・スピード変更のどちらの円かは
        呼び出し側が引数で渡す（ID-008-7 Refactor でボタンごとの専用判定を1本化した）"""
        dx = x - cx
        dy = y - cy
        return dx * dx + dy * dy <= r**2

    def _is_in_popup(self, x, y):
        """点 (x, y) がポップアップの矩形内にあるか。半開区間
        `[POPUP_X, POPUP_X+POPUP_W) x [POPUP_Y, POPUP_Y+POPUP_H)`
        （左上端は内・右下端は外）で判定する。ボタンの `_is_in_circle()` と対になる
        クリック判定(ID-007-16 Refactor)"""
        return (
            self.POPUP_X <= x < self.POPUP_X + self.POPUP_W
            and self.POPUP_Y <= y < self.POPUP_Y + self.POPUP_H
        )

    def draw(self):
        self._view.cls(0)
        self._draw_maze()
        self._draw_gates()
        self._draw_blocks()
        self._draw_mob()
        self._draw_speed_button()
        self._draw_pause_button()
        self._draw_button()
        self._draw_score()
        self._draw_popup()

    def _draw_score(self):
        """画面下部中央へ、スコアの数値のみを中央寄せで描く(requirements.md
        「スコア表示」。ラベル文字は付けない)"""
        text = str(self._maze.score)
        self._view.draw_text(
            self._centered_text_x(self.SCORE_CENTER_X, text),
            self.SCORE_CENTER_Y,
            text,
        )

    def _popup_lines(self, state):
        """状態ごとのポップアップの行の並び。クリアのときだけ、既存2行の下に
        「SCORE: 」ラベル付きの最終スコアを3行目として追加する(requirements.md
        「スコア表示」/tasks.md ID-010 完了条件。ゲームオーバーは2行のまま。
        ID-010-16。ラベルの追加はプレイテスト指摘によるID-010-21での変更)"""
        lines = [self._POPUP_LINE1_BY_STATE[state], self.TEXT_RESTART]
        if state == GameState.CLEARED:
            lines.append(f"{self.POPUP_SCORE_PREFIX}{self._maze.score}")
        return lines

    def _draw_popup(self):
        """クリア/ゲームオーバー状態のとき、迷路領域の中央へポップアップを最前面に描く。
        矩形・中央寄せの描画経路は状態で分岐させず、行の文言だけを
        `_popup_lines()` から引く(ID-007-10 Refactor。ID-010-17 で行数を
        2固定から一般化した)"""
        state = self._maze.state
        if state not in self._POPUP_LINE1_BY_STATE:
            return
        lines = self._popup_lines(state)
        self._view.rect(
            self.POPUP_X,
            self.POPUP_Y,
            self.POPUP_W,
            self.POPUP_H,
            self.COLOR_POPUP_BORDER,
        )
        border = self.POPUP_BORDER_THICKNESS
        self._view.rect(
            self.POPUP_X + border,
            self.POPUP_Y + border,
            self.POPUP_W - 2 * border,
            self.POPUP_H - 2 * border,
            self.COLOR_POPUP_BG,
        )
        # 行ブロックの高さを行数から求める(2行直書きの一般化。ID-010-17)。
        # 行数が2のときは従来の式 `2 * TEXT_HEIGHT + POPUP_LINE_GAP` と一致する
        line_block_height = (
            len(lines) * self.TEXT_HEIGHT + (len(lines) - 1) * self.POPUP_LINE_GAP
        )
        first_line_y = self.POPUP_Y + (self.POPUP_H - line_block_height) // 2
        popup_center_x = self.POPUP_X + self.POPUP_W // 2
        for index, line in enumerate(lines):
            line_y = first_line_y + index * (self.TEXT_HEIGHT + self.POPUP_LINE_GAP)
            self._view.draw_text(
                self._centered_text_x(popup_center_x, line),
                line_y,
                line,
            )

    def _centered_text_x(self, center_x, text):
        """x 座標 center_x に text の中心が来る左端の x 座標。
        「教える」ボタンのラベル・ポップアップの文言はどちらも 1 点を中心とした
        文字列の中央寄せであり、計算式を共通化する（ID-007-7 Refactor）"""
        return center_x - len(text) * self.TEXT_WIDTH // 2

    def _draw_blocks(self):
        """ブロックのある全セルを、モブより先に赤 2x2 で中央へ描く。
        モブと同じセルに重なった場合、後に描く方が上に見えるため、
        先に描くことでモブが上に見える(ID-006_subtasks.md「重なり順を仕様として固定する理由」)"""
        for col, row in self._maze.get_blocked_positions():
            self._draw_centered_square(col, row, self.BLOCK_SIZE, self.COLOR_BLOCK)

    def _draw_mob(self):
        """モブの現在位置を、セル中央の黄色 2x2 の四角として重ねて描く"""
        self._draw_centered_square(
            *self._maze.get_mob_position(), self.MOB_SIZE, self.COLOR_MOB
        )

    def _draw_centered_square(self, col, row, size, color):
        """セルの中央へ size x size の正方形を重ねて描く。
        モブ・ブロックはどちらも「セル中央寄せの正方形」であり、計算式を共通化する
        （ID-006_subtasks.md「未決事項」で Refactor 時に決定）"""
        origin_x, origin_y = self._cell_origin(col, row)
        offset = (self.CELL_SIZE - size) // 2
        self._view.rect(origin_x + offset, origin_y + offset, size, size, color)

    def _draw_circle_button(self, cx, cy, r, label, tx, border_color, fill_color=0):
        """丸ボタンを塗り→枠→ラベル中央寄せの順で描く(「教える」・スピード変更で
        共通の3手順。ID-008-4 Refactor で共通化。中心・半径・ラベル・枠色は
        呼び出し側がボタンごとに渡す)。塗り色は既定で黒(0)。ポーズボタンだけが
        状態を示すために差し替える(設計方針2の案C。ID-009-7 Refactor)。
        ラベルの中央寄せx座標(`tx`)は3ボタンとも呼び出し側で `__init__` 時に
        1度だけ計算済みのものを渡す(ID-011 方針A-iv。ラベル文字列・中心座標が
        いずれも定数のため)"""
        ty = cy - self.TEXT_HEIGHT // 2 + self.BUTTON_LABEL_OFFSET
        self._view.circ(cx, cy, r, fill_color)
        self._view.circb(cx, cy, r, border_color)
        self._view.draw_text(tx, ty, label)

    def _draw_speed_button(self):
        """スピード変更ボタンを画面左下端へ、サブボタンとして「教える」ボタンより
        小さい丸ボタンで描く。ラベルは現在の段階(_speed_index)から引き、枠の色は
        円内で押した瞬間から離すまで保持される `_armed_button` が _BUTTON_SPEED の
        間だけ押下中の色にする(「教える」ボタンと同型。ID-008-7 Refactor)"""
        border_color = (
            self.COLOR_BUTTON_PRESSED
            if self._armed_button == self._BUTTON_SPEED
            else self.COLOR_BUTTON_NORMAL
        )
        self._draw_circle_button(
            self.SPEED_BUTTON_CENTER_X,
            self.SPEED_BUTTON_CENTER_Y,
            self.SPEED_BUTTON_RADIUS,
            self.SPEED_STEPS[self._speed_index][0],
            self._speed_button_label_x[self._speed_index],
            border_color,
        )

    def _draw_pause_button(self):
        """ポーズボタンをスピード変更ボタンのすぐ右へ、中心線を揃えた丸ボタンで描く。
        ラベルは常に `PAUSE_BUTTON_LABEL` で固定し、ポーズ状態(_paused)は塗り色で
        示す(設計方針2の案C。ユーザー指示によりラベルのトグルから変更。ID-009-7
        Refactor)。枠の色は円内で押した瞬間から離すまで保持される `_armed_button`
        が _BUTTON_PAUSE の間だけ押下中の色にする(「教える」・スピード変更ボタンと
        同型。ID-008-7 Refactorで確立した書き方を踏襲)"""
        fill_color = self.COLOR_BUTTON_PAUSED if self._paused else 0
        border_color = (
            self.COLOR_BUTTON_PRESSED
            if self._armed_button == self._BUTTON_PAUSE
            else self.COLOR_BUTTON_NORMAL
        )
        self._draw_circle_button(
            self.PAUSE_BUTTON_CENTER_X,
            self.PAUSE_BUTTON_CENTER_Y,
            self.PAUSE_BUTTON_RADIUS,
            self.PAUSE_BUTTON_LABEL,
            self._pause_button_label_x,
            border_color,
            fill_color,
        )

    def _draw_button(self):
        """「教える」ボタンを画面右下へ丸ボタンとして描く(ラベル `STOP`)。
        枠の色は、円内で押した瞬間から離すまで保持される `_armed_button` が
        _BUTTON_TEACH の間だけ押下中の色にする(新たな状態は持たず、006-5 で
        導入済みの考え方を _armed_button へ一般化した。ID-006_subtasks.md「006-7」・
        ID-008-7 Refactor)"""
        border_color = (
            self.COLOR_BUTTON_PRESSED
            if self._armed_button == self._BUTTON_TEACH
            else self.COLOR_BUTTON_NORMAL
        )
        self._draw_circle_button(
            self.BUTTON_CENTER_X,
            self.BUTTON_CENTER_Y,
            self.BUTTON_RADIUS,
            self.BUTTON_LABEL,
            self._button_label_x,
            border_color,
        )

    def _draw_maze(self):
        for row in range(self._maze.ROWS):
            for col in range(self._maze.COLS):
                self._draw_cell(col, row)

    def _draw_gates(self):
        """入口(スタートの左)・出口(ゴールの右)に `->` を描く。座標は
        `__init__` で1度だけ計算済みの `_gate_positions` を参照する
        (ID-011 方針A-iv。スタート・ゴール地点は迷路サイズから決まる定数のため)"""
        for x, y in self._gate_positions:
            self._view.draw_text(x, y, self.ARROW_TEXT)

    def _cell_origin(self, col, row):
        """セルの左上ピクセル座標"""
        return (self.MAZE_X + col * self.CELL_SIZE, self.MAZE_Y + row * self.CELL_SIZE)

    def _draw_cell(self, col, row):
        x, y, u, v = self._cell_render_table[(col, row)]
        self._view.rect(
            x, y, self.CELL_SIZE, self.CELL_SIZE, self._cell_color(col, row)
        )
        self._view.blt(
            x,
            y,
            self.TILE_IMAGE_BANK,
            u,
            v,
            self.CELL_SIZE,
            self.CELL_SIZE,
            self.TILE_COLKEY,
        )

    def _cell_color(self, col, row):
        """探索済みかどうかで背景色を選ぶ"""
        if self._maze.is_visited(col, row):
            return self.COLOR_VISITED
        return self.COLOR_UNEXPLORED

    @classmethod
    def _get_tile_origin(cls, connections):
        row = cls._TILE_ROW[connections & cls._VERTICAL_DIRECTIONS]
        col = cls._TILE_COL[connections & cls._HORIZONTAL_DIRECTIONS]
        return (cls._TILE_SHEET_X + col * cls._TILE_SIZE, row * cls._TILE_SIZE)


class App:
    SCREEN_WIDTH = 200
    SCREEN_HEIGHT = 300

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(self.SCREEN_WIDTH, self.SCREEN_HEIGHT, title="pyxel_maze_guide")
        pyxel.load("images.pyxres")
        pyxel.mouse(True)
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        """needs_reset が真のフレームでは、旧 GameCore の update() を呼ばずに
        GameCore を作り直す(個別の状態初期化処理は持たない。ID-007-14)"""
        if self._core.needs_reset:
            self._core = GameCore()
        else:
            self._core.update()

    def draw(self):
        self._core.draw()


if __name__ == "__main__":
    App()
