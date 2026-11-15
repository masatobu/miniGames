# title: pyxel merge
# author: masatobu

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, NamedTuple, Optional

from save_store import SaveStore  # pylint: disable=E0401


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, color):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def draw_rect_border(self, x, y, w, h, color):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, color):
        self.pyxel.text(x, y, text, color)

    def draw_rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def draw_rect_border(self, x, y, w, h, color):
        self.pyxel.rectb(x, y, w, h, color)


class IInput(ABC):
    @abstractmethod
    def tapped_position(self):
        pass

    @abstractmethod
    def held_position(self):
        pass

    @abstractmethod
    def released_position(self):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def tapped_position(self):
        """左ボタンを押した瞬間のフレームだけ (x, y) を返し、他は None"""
        import pyxel  # pylint: disable=W0621, C0415

        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            return (pyxel.mouse_x, pyxel.mouse_y)
        return None

    def held_position(self):
        """左ボタンを押している間だけ (x, y) を返し、他は None"""
        import pyxel  # pylint: disable=W0621, C0415

        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            return (pyxel.mouse_x, pyxel.mouse_y)
        return None

    def released_position(self):
        """左ボタンを離した瞬間のフレームだけ (x, y) を返し、他は None"""
        import pyxel  # pylint: disable=W0621, C0415

        if pyxel.btnr(pyxel.MOUSE_BUTTON_LEFT):
            return (pyxel.mouse_x, pyxel.mouse_y)
        return None


def text_width(text):
    """Pyxel の組み込みフォントで描いた文字列の幅（1 文字 4 ピクセル、最後の文字の後の隙間を除く）"""
    return 4 * len(text) - 1


FIELD_SIZE = 10
SCREEN_WIDTH = 150
SCREEN_HEIGHT = 200
CELL_PITCH = 14  # マスの間隔（隣のマスの左上までのピクセル数）
CELL_SIZE = 15  # 1 マスの四角形の大きさ。隣と 1 ピクセル重ねて枠線を 1 ピクセルにする
# 上から クリア枠・メーターの行 → フィールド → スポーンボタンの行 の順に並べる
LAYOUT_MARGIN = 5  # 画面の端と各要素の間の余白、クリア枠・メーター・フィールドの隙間
SPAWN_GAP = (
    6  # フィールドの下端とスポーンボタンの上端の隙間（画面の下端に収めるための導出値）
)
# クリア枠。1 マスの正方形で、左上は画面の左上の余白の内側（領域は離した位置の判定にも使う）
CLEAR_SLOT_X = LAYOUT_MARGIN
CLEAR_SLOT_Y = LAYOUT_MARGIN
CLEAR_SLOT_W = CELL_SIZE
CLEAR_SLOT_H = CELL_SIZE
# フィールド左上。x はクリア枠の左端にそろえ、y はクリア枠の下端 + 隙間
FIELD_ORIGIN_X = CLEAR_SLOT_X
FIELD_ORIGIN_Y = CLEAR_SLOT_Y + CLEAR_SLOT_H + LAYOUT_MARGIN
_FIELD_RIGHT = FIELD_ORIGIN_X + CELL_PITCH * FIELD_SIZE  # フィールドの右端
# フィールドの下端（最後のマスの下端）
_FIELD_BOTTOM = FIELD_ORIGIN_Y + CELL_PITCH * (FIELD_SIZE - 1) + CELL_SIZE
# メーター。クリア枠の右の隙間から、右端はフィールドの右端まで。高さはクリア枠と同じ。
# 離す先ではない（位置の判定には使わない）
METER_X = CLEAR_SLOT_X + CLEAR_SLOT_W + LAYOUT_MARGIN
METER_Y = CLEAR_SLOT_Y
METER_W = _FIELD_RIGHT - METER_X
METER_H = CLEAR_SLOT_H
METER_BORDER = 1  # 枠線の太さ。塗りは枠線の内側に描く
# クリア枠・メーターの色。メーターの塗りは、背景・選択枠の緑 11・赤 8 のどれとも違う色にする
COLOR_CLEAR_BG = 0
COLOR_CLEAR_BORDER = 13
COLOR_METER_BG = 0
COLOR_METER_BORDER = 13
COLOR_METER_FILL = 12
TEXT_OFFSET_X = 6  # マスの左上から数字までのずらし量（枠線 1 ピクセルの分を含む）
TEXT_OFFSET_Y = 5
COLOR_SCREEN_BG = 0
COLOR_OPENED_BG = 0
COLOR_CLOSED_BG = 13
COLOR_BORDER = 1
COLOR_BLUE_TEXT = 5
COLOR_RED_TEXT = 2
COLOR_ACHIEVED_TEXT = 13  # 成長枠の達成済みの項目の数字（グレー。青・赤と見分けられる）
# スポーンボタン。領域（左上と大きさ）は、押した位置の判定にも使う
SPAWN_BUTTON_X = 50
SPAWN_BUTTON_Y = _FIELD_BOTTOM + SPAWN_GAP
SPAWN_BUTTON_W = 50
SPAWN_BUTTON_H = 24
# 削除枠。1 マス（CELL_SIZE）の正方形で、スポーンボタンの左にあり縦は中央にそろえる。
# 横は、フィールドの左端とスポーンボタンの左端の間の中央（左右の空白が同じ）。
# 領域は離した位置の判定にも使う
DELETE_SLOT_W = CELL_SIZE
DELETE_SLOT_H = CELL_SIZE
DELETE_SLOT_X = FIELD_ORIGIN_X + (SPAWN_BUTTON_X - FIELD_ORIGIN_X - DELETE_SLOT_W) // 2
DELETE_SLOT_Y = SPAWN_BUTTON_Y + (SPAWN_BUTTON_H - CELL_SIZE) // 2
# DEL（3 文字、幅 11、高さ 5）を削除枠の中央に置くためのずらし量
DELETE_LABEL_OFFSET_X = (DELETE_SLOT_W - 11) // 2
DELETE_LABEL_OFFSET_Y = (DELETE_SLOT_H - 5) // 2
# 削除枠の色。マス・スポーンボタン・選択枠（緑 11、赤 8）のどれとも違う色にする
COLOR_DELETE_BG = 4
COLOR_DELETE_BORDER = 9
COLOR_DELETE_TEXT = 10
# 成長枠。1 行 2 列（横並びの 2 マス）で、横はスポーンボタンの右端とフィールドの右端の間の中央
# （左右の空白が同じ）、縦はスポーンボタンの中央にそろえる（削除枠と同じ行）。
# 領域は離した位置の判定にも使う
GROWTH_SLOT_COLUMNS = 2
GROWTH_SLOT_ROWS = 1
GROWTH_SLOT_W = CELL_PITCH * (GROWTH_SLOT_COLUMNS - 1) + CELL_SIZE
GROWTH_SLOT_H = CELL_PITCH * (GROWTH_SLOT_ROWS - 1) + CELL_SIZE
_SPAWN_BUTTON_RIGHT = SPAWN_BUTTON_X + SPAWN_BUTTON_W
GROWTH_SLOT_X = (
    _SPAWN_BUTTON_RIGHT + (_FIELD_RIGHT - _SPAWN_BUTTON_RIGHT - GROWTH_SLOT_W) // 2
)
GROWTH_SLOT_Y = SPAWN_BUTTON_Y + (SPAWN_BUTTON_H - GROWTH_SLOT_H) // 2
SPAWN_LABEL_OFFSET_X = 15  # ボタンの左上から SPAWN（5 文字、幅 20）までのずらし量
SPAWN_LABEL_OFFSET_Y = 5
# ボタンの上端から Lv + 数字までのずらし量（横はボタンの左右の中央。桁数で幅が変わる）
SPAWN_LEVEL_OFFSET_Y = 13
COLOR_SPAWN_BG = 3
COLOR_SPAWN_BORDER = 7
COLOR_SPAWN_TEXT = 7
# クリアのポップアップ（画面の中心に重ねる）
POPUP_TITLE = "CLEAR!"
POPUP_GUIDE = "TAP TO RESTART"
POPUP_MARGIN_X = 8  # 最長の行から矩形の左右までの余白
POPUP_MARGIN_Y = 7  # 矩形の上下の余白
POPUP_LINE_GAP = 7  # 2 行の間の隙間
POPUP_TEXT_H = 5  # 組み込みフォントの文字の高さ
POPUP_W = text_width(POPUP_GUIDE) + 2 * POPUP_MARGIN_X  # 最長の行 + 左右の余白
POPUP_H = 2 * POPUP_TEXT_H + POPUP_LINE_GAP + 2 * POPUP_MARGIN_Y
POPUP_X = SCREEN_WIDTH // 2 - POPUP_W // 2  # 画面の中心に置く
POPUP_Y = SCREEN_HEIGHT // 2 - POPUP_H // 2
COLOR_POPUP_BG = 1  # 濃い青
COLOR_POPUP_BORDER = 10  # 黄
COLOR_POPUP_TEXT = 7  # 白
# 選択枠。離したときに実行できる位置は緑、できない位置は赤
COLOR_FRAME_OK = 11
COLOR_FRAME_NG = 8


class Item(NamedTuple):
    """マスに置かれるアイテム（色と数字の値）"""

    color: str
    number: int


@dataclass
class Cell:
    """フィールドの 1 マス"""

    x: int
    y: int
    opened: bool = False
    item: Optional[Item] = None


@dataclass
class Field:
    """size × size のマス目"""

    size: int
    cells: List[Cell]

    def cell(self, x, y):
        """座標 (x, y) のマスを返す（cells は y の行ごと、行の中は x の順）"""
        return self.cells[y * self.size + x]

    def is_mergeable(self, x, y):
        """未開放で、開放済みのマスに上下左右で接するマスか（マージ先にできるか）"""
        if self.cell(x, y).opened:
            return False
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                if self.cell(nx, ny).opened:
                    return True
        return False


def ring_of(x, y):
    """マスの周を返す。中心の 2 × 2 が 0、外へ最大 4"""
    edge = FIELD_SIZE - 1  # 座標を中心からの距離（2 倍値）に直す基準
    return (max(abs(2 * x - edge), abs(2 * y - edge)) - 1) // 2


def cell_at(x, y):
    """画面位置 (x, y) のマスの座標 (cx, cy) を返す。フィールドの外は None

    隣と重なる 1 ピクセルは右・下のマスに属し、右・下の最も外側の枠線は最後のマスに属する
    """
    edge = CELL_PITCH * FIELD_SIZE  # 原点から最も外側の枠線までのピクセル数
    dx, dy = x - FIELD_ORIGIN_X, y - FIELD_ORIGIN_Y
    if not (0 <= dx <= edge and 0 <= dy <= edge):
        return None
    last = FIELD_SIZE - 1
    return (min(dx // CELL_PITCH, last), min(dy // CELL_PITCH, last))


@dataclass(frozen=True)
class GrowthSlotCell:
    """離す先が成長枠のマスであることを表す値（状態を持たない位置の判定の結果）

    index は 0〜1。左上から右へ行ごとの順。項目と達成済みかは GameCore が足す
    """

    index: int


def growth_slot_cell_at(x, y):
    """画面位置 (x, y) の成長枠のマスを GrowthSlotCell で返す。成長枠の外は None

    領域は左上を含み右下の外側は含まない半開区間。隣と重なる 1 ピクセルは右・下のマスに属し、
    最後の列・行は頭打ちにする（cell_at と同じ方式）
    """
    dx, dy = x - GROWTH_SLOT_X, y - GROWTH_SLOT_Y
    if not (0 <= dx < GROWTH_SLOT_W and 0 <= dy < GROWTH_SLOT_H):
        return None
    col = min(dx // CELL_PITCH, GROWTH_SLOT_COLUMNS - 1)
    row = min(dy // CELL_PITCH, GROWTH_SLOT_ROWS - 1)
    return GrowthSlotCell(row * GROWTH_SLOT_COLUMNS + col)


def growth_cell_origin(index):
    """成長枠のマス index（0〜1）の左上の画面位置 (x, y)。growth_slot_cell_at の逆"""
    row, col = divmod(index, GROWTH_SLOT_COLUMNS)
    return GROWTH_SLOT_X + CELL_PITCH * col, GROWTH_SLOT_Y + CELL_PITCH * row


def target_at(x, y):
    """画面位置 (x, y) の離す先を返す。マスなら座標 (cx, cy)、削除枠なら DELETE_SLOT、
    成長枠のマスなら GrowthSlotCell(index)、クリア枠なら CLEAR_SLOT、どれでもなければ None
    （メーターは離す先ではない）

    削除枠・成長枠・クリア枠の領域は、左上を含み右下の外側は含まない半開区間
    """
    if (
        DELETE_SLOT_X <= x < DELETE_SLOT_X + DELETE_SLOT_W
        and DELETE_SLOT_Y <= y < DELETE_SLOT_Y + DELETE_SLOT_H
    ):
        return DELETE_SLOT
    if (
        CLEAR_SLOT_X <= x < CLEAR_SLOT_X + CLEAR_SLOT_W
        and CLEAR_SLOT_Y <= y < CLEAR_SLOT_Y + CLEAR_SLOT_H
    ):
        return CLEAR_SLOT
    slot_cell = growth_slot_cell_at(x, y)
    if slot_cell is not None:
        return slot_cell
    return cell_at(x, y)


def _item_color(item):
    """アイテムの数字の色（青 / 赤）"""
    return COLOR_BLUE_TEXT if item.color == "blue" else COLOR_RED_TEXT


def initial_item_of(ring):
    """n 周目（1 以上）の初期アイテム。数字は n + 1、色は奇数周が青・偶数周が赤"""
    return Item("blue" if ring % 2 == 1 else "red", ring + 1)


def create_initial_field():
    """ゲーム開始時のフィールドを作る。中心の 2 × 2 は開放済みで空き"""
    cells = []
    for y in range(FIELD_SIZE):
        for x in range(FIELD_SIZE):
            ring = ring_of(x, y)
            if ring == 0:
                cells.append(Cell(x, y, opened=True))
            else:
                cells.append(Cell(x, y, item=initial_item_of(ring)))
    return Field(FIELD_SIZE, cells)


DROP_MERGE = "merge"
DROP_MOVE = "move"
DROP_DELETE = "delete"
DELETE_SLOT = object()  # 離す先が削除枠であることを表す印（座標でも None でもない）
DROP_GROW = "grow"
DROP_CLEAR = "clear"
CLEAR_SLOT = object()  # 離す先がクリア枠であることを表す印（座標でも None でもない）
MERGE_MAX_NUMBER = 6  # この数字のアイテムはマージできない（最高の数字）
# クリアに必要な、クリア枠に入れた数（初期の赤5 の 36 個より多くする）
CLEAR_REQUIRED_COUNT = 40
CLEAR_COLOR_START = "red"  # クリア枠に最初に入れる色


@dataclass(frozen=True)
class GrowthTarget:
    """離す先が成長枠のマスであることを表す値

    item はそのマスに表示されている項目（空のセル・最高レベルは None）、
    achieved はその項目が達成済みか
    """

    item: Optional[Item]
    achieved: bool


@dataclass(frozen=True)
class ClearTarget:
    """離す先がクリア枠であることを表す値。color は次にクリア枠へ入れる色"""

    color: str


def drop_action(field, src, dst):
    """src のアイテムを dst で離したときの操作を返す。判定だけで、状態は変えない

    src は座標 (x, y)。dst は座標 (x, y)、削除枠なら DELETE_SLOT、
    成長枠のマスなら GrowthTarget、クリア枠なら ClearTarget、フィールドの外なら None。
    返す値は "merge"、"move"、"delete"、"grow"、"clear"、実行できないときは None
    """
    src_cell = field.cell(*src) if dst is not None and dst != src else None
    if src_cell is None or not src_cell.opened or src_cell.item is None:
        return None
    if dst is DELETE_SLOT:
        return DROP_DELETE  # 色・数字を問わず削除できる
    if isinstance(dst, GrowthTarget):
        # 未達成の項目と、色・数字が同じアイテムだけ置ける
        grows = not dst.achieved and dst.item == src_cell.item
        return DROP_GROW if grows else None
    if isinstance(dst, ClearTarget):
        # 最高の数字で、次に入れる色のアイテムだけ入れられる
        item = src_cell.item
        accepts = item.number == MERGE_MAX_NUMBER and item.color == dst.color
        return DROP_CLEAR if accepts else None
    return _cell_drop_action(field, src_cell.item, dst)


def _cell_drop_action(field, src_item, dst):
    """src_item を座標 dst のマスで離したときの操作（"merge"・"move"・None）"""
    dst_cell = field.cell(*dst)
    if dst_cell.opened and dst_cell.item is None:
        return DROP_MOVE
    if not dst_cell.opened and not field.is_mergeable(*dst):
        return None  # ロック中のマスはマージ先にできない
    item = dst_cell.item
    if (
        item is not None
        and item.color == src_item.color
        and item.number == src_item.number
        and item.number < MERGE_MAX_NUMBER
    ):
        return DROP_MERGE
    return None


def apply_drop(field, src, dst):
    """判定に従って操作を実行し、実行した操作を返す（実行できなければ変更せず None）

    "delete"・"grow"・"clear" は操作元を空きにするだけ。達成の記録（GameCore.achieve）や
    クリア枠に入れた数の記録は呼び出し側が行う
    """
    action = drop_action(field, src, dst)
    if action is None:
        return None
    src_cell = field.cell(*src)
    if action in (DROP_DELETE, DROP_GROW, DROP_CLEAR):
        src_cell.item = None  # 操作元は開放済みのまま空きになる
        return action
    dst_cell = field.cell(*dst)
    item = src_cell.item
    if action == DROP_MERGE:
        item = Item(item.color, item.number + 1)
    dst_cell.item = item
    dst_cell.opened = True
    src_cell.item = None
    return action


SPAWN_LEVEL_START = 1  # ゲーム開始時のスポーンのレベル
SPAWN_LEVEL_MAX = 20  # 最高レベル（成長枠の項目はない。クリアの条件ではない）
_BLUE1 = Item("blue", 1)
_BLUE2 = Item("blue", 2)
_RED1 = Item("red", 1)
_RED2 = Item("red", 2)
_SPAWN_ITEMS = (_BLUE1, _BLUE2, _RED1, _RED2)
# 出現確率の段階（初期値。プレイテストで調整する）。(レベルの範囲, ％) を段階の順に持つ。
# ％は 青1、青2、赤1、赤2 の順で、合計は 100。レベルの範囲は 1〜最高レベルを隙間なく覆う
_SPAWN_RATE_STAGES = (
    (range(1, 3), (100, 0, 0, 0)),
    (range(3, 6), (70, 30, 0, 0)),
    (range(6, 8), (40, 20, 40, 0)),
    (range(8, 11), (30, 20, 30, 20)),
    (range(11, 14), (33, 22, 27, 18)),
    (range(14, 16), (24, 36, 16, 24)),
    (range(16, 19), (26, 39, 14, 21)),
    (range(19, SPAWN_LEVEL_MAX + 1), (27, 40, 13, 20)),
)
# レベルごとの出現確率（％）。(アイテム, ％) を 青1、青2、赤1、赤2 の順に持つ
SPAWN_RATES = {
    level: tuple(zip(_SPAWN_ITEMS, rates))
    for levels, rates in _SPAWN_RATE_STAGES
    for level in levels
}


def _items(*pairs):
    return tuple(Item(color, number) for color, number in pairs)


# レベルごとの成長枠の項目。すべて達成するとレベルが 1 上がる。最高レベルは項目なし
GROWTH_ITEMS = {
    1: _items(("blue", 2)),
    2: _items(("blue", 3)),
    3: _items(("blue", 2), ("blue", 3)),
    4: _items(("blue", 4)),
    5: _items(("blue", 3), ("blue", 4)),
    6: _items(("blue", 2), ("red", 2)),
    7: _items(("blue", 3), ("red", 2)),
    8: _items(("blue", 3), ("red", 3)),
    9: _items(("blue", 4), ("red", 3)),
    10: _items(("blue", 4), ("red", 4)),
    11: _items(("blue", 5)),
    12: _items(("blue", 5), ("red", 3)),
    13: _items(("blue", 5), ("red", 4)),
    14: _items(("blue", 4), ("red", 5)),
    15: _items(("blue", 5), ("red", 5)),
    16: _items(("blue", 5), ("red", 5)),
    17: _items(("blue", 5), ("red", 5)),
    18: _items(("blue", 5), ("red", 5)),
    19: _items(("blue", 5), ("red", 5)),
    SPAWN_LEVEL_MAX: (),
}


def pick_item(level, roll):
    """レベルの出現確率と、0 以上 100 未満の値 roll からアイテムを決める。表がなければ None"""
    total = 0
    for item, rate in SPAWN_RATES.get(level, ()):
        total += rate
        if roll < total:
            return item
    return None


def spawn(field, level, rng):
    """開放済みの空きマスから 1 マスを選び、アイテムを置く。置いたマスを返す（置けなければ None）"""
    if level not in SPAWN_RATES:
        return None
    candidates = [c for c in field.cells if c.opened and c.item is None]
    if not candidates:
        return None
    cell = candidates[rng.randrange(len(candidates))]
    cell.item = pick_item(level, rng.random() * 100)
    return cell


_COLORS = ("red", "blue")


def _is_int(value):
    """真偽値でない整数か（bool は int の子クラスなので除く）"""
    return isinstance(value, int) and not isinstance(value, bool)


def _item_to_list(item):
    """アイテムを [color, number] にする。None は None のまま"""
    return None if item is None else [item.color, item.number]


def _item_from_list(value):
    """[color, number] を Item にする。形・色・数字が正しくなければ ValueError"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("item")
    color, number = value
    if color not in _COLORS or not _is_int(number):
        raise ValueError("item")
    if not 1 <= number <= MERGE_MAX_NUMBER:
        raise ValueError("item")
    return Item(color, number)


def _cell_from_dict(index, value):
    """field の index 番目の辞書を Cell にする。正しくなければ ValueError"""
    if not isinstance(value, dict) or not isinstance(value.get("opened"), bool):
        raise ValueError("cell")
    if "item" not in value:
        raise ValueError("cell")
    item = value["item"]
    item = None if item is None else _item_from_list(item)
    return Cell(index % FIELD_SIZE, index // FIELD_SIZE, value["opened"], item)


def _parse_snapshot(data):
    """辞書を検証して (Field, レベル, 達成済みの集合, クリア枠の数, 次の色) にする。
    正しくなければ None（例外は出さない）"""
    try:
        cells = data["field"]
        level = data["spawn_level"]
        count = data["clear_count"]
        color = data["clear_next_color"]
        if not isinstance(cells, list) or len(cells) != FIELD_SIZE * FIELD_SIZE:
            raise ValueError("field")
        if not _is_int(level) or not SPAWN_LEVEL_START <= level <= SPAWN_LEVEL_MAX:
            raise ValueError("spawn_level")
        if not isinstance(data["achieved"], list):
            raise ValueError("achieved")
        achieved = [_item_from_list(v) for v in data["achieved"]]
        if len(set(achieved)) != len(achieved):
            raise ValueError("achieved")
        if not set(achieved) <= set(GROWTH_ITEMS[level]):
            raise ValueError("achieved")
        if not _is_int(count) or not 0 <= count < CLEAR_REQUIRED_COUNT:
            raise ValueError("clear_count")
        if color not in _COLORS:
            raise ValueError("clear_next_color")
        field = Field(
            FIELD_SIZE, [_cell_from_dict(i, cell) for i, cell in enumerate(cells)]
        )
    except (KeyError, TypeError, ValueError):
        return None
    return field, level, set(achieved), count, color


class GameCore:
    # 状態の属性は _reset_state（__init__ と restart が共有）で定義するため、定義位置の警告を抑止する
    # pylint: disable=attribute-defined-outside-init
    def __init__(self, store=None):
        self._view = PyxelView.create()
        self._input = PyxelInput.create()
        self._store = store if store is not None else SaveStore()
        self._reset_state()
        data = self._store.load()
        if isinstance(data, dict):
            self.restore(data)  # 正しくない・{}（ゲーム無し）なら初期状態のまま

    def restart(self):
        """初期状態に戻して保存する。描画・入力の部品は作り直さない"""
        self._reset_state()
        self._save(self.snapshot())

    def _save(self, data):
        """保存する。失敗しても無視する（次に状態が変わったときにまた保存する）"""
        self._store.save(data)

    def _reset_state(self):
        """ゲームの状態を初期状態にする（__init__ と restart が共有する）"""
        self._field = create_initial_field()
        self._spawn_level = SPAWN_LEVEL_START
        self._achieved = set()  # 現在のレベルで達成済みの項目
        self._clear_count = 0  # クリア枠に入れた数
        self._clear_next_color = CLEAR_COLOR_START  # クリア枠に次に入れる色
        self._selected = None  # 操作元のマス (x, y)
        # ポインタの離す先（マス (x, y)、削除枠なら DELETE_SLOT、成長枠のマスなら GrowthSlotCell）
        self._hovered = None
        self._restart_armed = False  # ポップアップ内で押して離すのを待っているか

    @property
    def spawn_level(self):
        return self._spawn_level

    @property
    def cleared(self):
        """クリア（クリア枠に必要な数を入れた）状態か。clear_count から導出する"""
        return self._clear_count >= CLEAR_REQUIRED_COUNT

    @property
    def clear_count(self):
        """クリア枠に入れた数"""
        return self._clear_count

    @property
    def clear_next_color(self):
        """クリア枠に次に入れる色（開始時は赤。1 つ入れるたびに赤と青が入れ替わる）"""
        return self._clear_next_color

    @property
    def growth_items(self):
        """現在のレベルの成長枠の項目（最高レベルは空）"""
        return GROWTH_ITEMS[self._spawn_level]

    def is_achieved(self, item):
        """項目が現在のレベルで達成済みか"""
        return item in self._achieved

    def achieve(self, item):
        """現在のレベルの未達成の項目を達成として記録する。記録したかを返す。
        すべて達成したらレベルを 1 上げ、達成済みを空に戻す"""
        if item not in self.growth_items or item in self._achieved:
            return False
        self._achieved.add(item)
        if self._achieved.issuperset(self.growth_items):
            self._spawn_level += 1
            self._achieved = set()
        return True

    def snapshot(self):
        """保存するゲームの状態を、JSON で表せる辞書にして返す

        選択中の枠・ポインタの離す先・ポップアップの待機は含めない。achieved は
        現在のレベルの成長枠の項目の並びで持つ
        """
        return {
            "field": [
                {"opened": c.opened, "item": _item_to_list(c.item)}
                for c in self._field.cells
            ],
            "spawn_level": self._spawn_level,
            "achieved": [
                _item_to_list(i) for i in self.growth_items if i in self._achieved
            ],
            "clear_count": self._clear_count,
            "clear_next_color": self._clear_next_color,
        }

    def restore(self, data):
        """辞書から状態を復元して真を返す。正しくなければ初期状態にして偽を返す（例外は出さない）

        検証をすべて終えてから状態を置き換え、選択中の枠・ポインタ・ポップアップの待機は初期値にする
        """
        state = _parse_snapshot(data)
        self._reset_state()
        if state is None:
            return False
        (
            self._field,
            self._spawn_level,
            self._achieved,
            self._clear_count,
            self._clear_next_color,
        ) = state
        return True

    @property
    def selected(self):
        """スライドの操作元のマス (x, y)。選択していなければ None"""
        return self._selected

    @property
    def hovered(self):
        """スライド中のポインタの離す先。マスなら (x, y)、削除枠なら DELETE_SLOT、
        成長枠のマスなら GrowthSlotCell(index)。どれでもない位置・選択なしは None"""
        return self._hovered

    def spawn(self, rng=random):
        """自分のフィールドとレベルでスポーンする。置いたマスを返す（置けなければ None）。
        置けたときは保存する"""
        cell = spawn(self._field, self._spawn_level, rng)
        if cell is not None:
            self._save(self.snapshot())
        return cell

    def update(self):
        # 3 つの入力は毎フレーム 1 回ずつ読む（選択の有無で読む回数を変えない）
        tapped = self._input.tapped_position()
        held = self._input.held_position()
        released = self._input.released_position()
        if self.cleared:  # クリア中は、ポップアップのタップ以外の操作を受け付けない
            self._update_cleared(tapped, released)
            return
        if tapped is not None:
            self._on_tapped(*tapped)
        if self._selected is not None and held is not None:
            self._hovered = target_at(*held)
        if self._selected is not None and released is not None:
            self._on_released(*released)

    def _update_cleared(self, tapped, released):
        """押した位置がポップアップの中なら待機を始め、離したとき、待機中かつ中ならやり直す。
        待機は離したとき常に終える。押す→離すの順に処理する"""
        if tapped is not None and self._is_on_popup(*tapped):
            self._restart_armed = True
        if released is not None:
            armed = self._restart_armed
            self._restart_armed = False
            if armed and self._is_on_popup(*released):
                self.restart()

    @staticmethod
    def _is_on_popup(x, y):
        """ポップアップの領域（左上を含み、右下の外側は含まない半開区間）の中か"""
        return POPUP_X <= x < POPUP_X + POPUP_W and POPUP_Y <= y < POPUP_Y + POPUP_H

    def _on_tapped(self, x, y):
        """押した位置がスポーンボタンならスポーン、開放済みでアイテムのあるマスなら操作元にする"""
        if self._is_on_spawn_button(x, y):
            self.spawn()
            return
        coord = cell_at(x, y)
        if coord is None:
            return
        cell = self._field.cell(*coord)
        if cell.opened and cell.item is not None:
            self._selected = coord

    def _on_released(self, x, y):
        """離した先で操作を実行（できなければキャンセル）し、押下中の状態を消す"""
        self._on_drop(target_at(x, y))

    def _on_drop(self, target):
        """操作元のアイテムを離す先 target で離す。押下中の状態を消す

        成長枠のマス・クリア枠は GrowthTarget・ClearTarget に直して判定する。
        置けたら（"grow"）項目の達成を、入れたら（"clear"）入れた数と次の色を記録する
        """
        dst = self._resolve_target(target)
        action = apply_drop(self._field, self._selected, dst)
        if action == DROP_GROW:
            self.achieve(dst.item)
        elif action == DROP_CLEAR:
            self._clear_count += 1
            self._clear_next_color = "blue" if dst.color == "red" else "red"
        self._selected = None
        self._hovered = None
        if action is not None:
            # クリアしたら「ゲーム無し」（{}）、それ以外は現在の状態を保存する
            self._save({} if self.cleared else self.snapshot())

    def _resolve_target(self, target):
        """GrowthSlotCell を、現在のレベルの項目と達成状況を持つ GrowthTarget に、
        CLEAR_SLOT を、次に入れる色を持つ ClearTarget に直す。それ以外の離す先はそのまま返す"""
        if target is CLEAR_SLOT:
            return ClearTarget(self._clear_next_color)
        if not isinstance(target, GrowthSlotCell):
            return target
        items = self.growth_items
        item = items[target.index] if target.index < len(items) else None
        return GrowthTarget(item, item is not None and self.is_achieved(item))

    @staticmethod
    def _is_on_spawn_button(x, y):
        """スポーンボタンの領域（左上を含み、右下の外側は含まない半開区間）の中か"""
        return (
            SPAWN_BUTTON_X <= x < SPAWN_BUTTON_X + SPAWN_BUTTON_W
            and SPAWN_BUTTON_Y <= y < SPAWN_BUTTON_Y + SPAWN_BUTTON_H
        )

    def draw(self):
        for cell in self._field.cells:
            self._draw_cell(cell)
        self._draw_delete_slot()
        self._draw_growth_slot()
        self._draw_clear_slot()
        self._draw_meter()
        self._draw_selection_frame()
        self._draw_spawn_button()
        if self.cleared:
            self._draw_clear_popup()

    def _draw_clear_popup(self):
        """クリアのポップアップを 背景 → 枠線 → CLEAR! → TAP TO RESTART の順に、中央揃えで描く"""
        self._view.draw_rect(POPUP_X, POPUP_Y, POPUP_W, POPUP_H, COLOR_POPUP_BG)
        self._view.draw_rect_border(
            POPUP_X, POPUP_Y, POPUP_W, POPUP_H, COLOR_POPUP_BORDER
        )
        top = POPUP_Y + POPUP_MARGIN_Y
        for text in (POPUP_TITLE, POPUP_GUIDE):
            left = POPUP_X + (POPUP_W - text_width(text)) // 2
            self._view.draw_text(left, top, text, COLOR_POPUP_TEXT)
            top += POPUP_TEXT_H + POPUP_LINE_GAP

    def _draw_clear_slot(self):
        """クリア枠を 背景 → 枠線 → 次に入れる色の 6 の順に描く（常に描く）"""
        x, y, w, h = CLEAR_SLOT_X, CLEAR_SLOT_Y, CLEAR_SLOT_W, CLEAR_SLOT_H
        self._view.draw_rect(x, y, w, h, COLOR_CLEAR_BG)
        self._view.draw_rect_border(x, y, w, h, COLOR_CLEAR_BORDER)
        color = COLOR_BLUE_TEXT if self._clear_next_color == "blue" else COLOR_RED_TEXT
        self._view.draw_text(
            x + TEXT_OFFSET_X, y + TEXT_OFFSET_Y, str(MERGE_MAX_NUMBER), color
        )

    def _draw_meter(self):
        """メーターを 背景 → 枠線 → 塗り の順に描く。塗りは枠線の内側を左から、
        幅 = 内側の幅 × 入れた数 ÷ 必要な数（切り捨て）。入れた数 0 のときは塗らない"""
        x, y, w, h = METER_X, METER_Y, METER_W, METER_H
        self._view.draw_rect(x, y, w, h, COLOR_METER_BG)
        self._view.draw_rect_border(x, y, w, h, COLOR_METER_BORDER)
        inner_w = w - 2 * METER_BORDER
        fill_w = inner_w * min(self._clear_count, CLEAR_REQUIRED_COUNT)
        fill_w //= CLEAR_REQUIRED_COUNT
        if fill_w > 0:
            self._view.draw_rect(
                x + METER_BORDER,
                y + METER_BORDER,
                fill_w,
                h - 2 * METER_BORDER,
                COLOR_METER_FILL,
            )

    def _draw_growth_slot(self):
        """成長枠の 2 マスを、マスごとに 背景 → 枠線 → 数字 の順に描く（項目の無いマスは枠だけ）"""
        items = self.growth_items
        for index in range(GROWTH_SLOT_COLUMNS * GROWTH_SLOT_ROWS):
            left, top = growth_cell_origin(index)
            self._view.draw_rect(left, top, CELL_SIZE, CELL_SIZE, COLOR_OPENED_BG)
            self._view.draw_rect_border(left, top, CELL_SIZE, CELL_SIZE, COLOR_BORDER)
            if index < len(items):
                item = items[index]
                achieved = self.is_achieved(item)
                color = COLOR_ACHIEVED_TEXT if achieved else _item_color(item)
                self._draw_item_number(left, top, item, color)

    def _draw_delete_slot(self):
        """削除枠を 背景 → 枠線 → DEL の順に描く（選択の有無に関わらず常に描く）"""
        x, y, w, h = DELETE_SLOT_X, DELETE_SLOT_Y, DELETE_SLOT_W, DELETE_SLOT_H
        self._view.draw_rect(x, y, w, h, COLOR_DELETE_BG)
        self._view.draw_rect_border(x, y, w, h, COLOR_DELETE_BORDER)
        self._view.draw_text(
            x + DELETE_LABEL_OFFSET_X,
            y + DELETE_LABEL_OFFSET_Y,
            "DEL",
            COLOR_DELETE_TEXT,
        )

    def _selection_frame(self):
        """選択枠の四角形 (x, y, w, h) と色。押していなければ None

        枠はポインタの下のマス・削除枠・成長枠のマスに置き、どれでもないところ（フィールドの外）
        では操作元のマスに残す。離して実行できる位置は緑、できない位置は赤
        """
        if self._selected is None:
            return None
        hovered = self._resolve_target(self._hovered)
        if hovered is DELETE_SLOT:
            rect = (DELETE_SLOT_X, DELETE_SLOT_Y, DELETE_SLOT_W, DELETE_SLOT_H)
        elif self._hovered is CLEAR_SLOT:
            rect = (CLEAR_SLOT_X, CLEAR_SLOT_Y, CLEAR_SLOT_W, CLEAR_SLOT_H)
        elif isinstance(self._hovered, GrowthSlotCell):
            rect = (*growth_cell_origin(self._hovered.index), CELL_SIZE, CELL_SIZE)
        else:
            x, y = hovered if hovered is not None else self._selected
            rect = (
                FIELD_ORIGIN_X + CELL_PITCH * x,
                FIELD_ORIGIN_Y + CELL_PITCH * y,
                CELL_SIZE,
                CELL_SIZE,
            )
        can_drop = drop_action(self._field, self._selected, hovered) is not None
        return rect, COLOR_FRAME_OK if can_drop else COLOR_FRAME_NG

    def _draw_selection_frame(self):
        """選択枠を二重の枠線（四角形と、1 ピクセル内側）で描く"""
        frame = self._selection_frame()
        if frame is None:
            return
        (x, y, w, h), color = frame
        self._view.draw_rect_border(x, y, w, h, color)
        self._view.draw_rect_border(x + 1, y + 1, w - 2, h - 2, color)

    def _draw_spawn_button(self):
        """スポーンボタンを 背景 → 枠線 → SPAWN → Lv + レベル の順に描く。
        Lv + レベルは、桁数に関わらずボタンの左右の中央に置く"""
        x, y, w, h = SPAWN_BUTTON_X, SPAWN_BUTTON_Y, SPAWN_BUTTON_W, SPAWN_BUTTON_H
        self._view.draw_rect(x, y, w, h, COLOR_SPAWN_BG)
        self._view.draw_rect_border(x, y, w, h, COLOR_SPAWN_BORDER)
        self._view.draw_text(
            x + SPAWN_LABEL_OFFSET_X,
            y + SPAWN_LABEL_OFFSET_Y,
            "SPAWN",
            COLOR_SPAWN_TEXT,
        )
        level_text = f"Lv{self.spawn_level}"
        self._view.draw_text(
            x + (w - text_width(level_text)) // 2,
            y + SPAWN_LEVEL_OFFSET_Y,
            level_text,
            COLOR_SPAWN_TEXT,
        )

    def _is_number_visible(self, cell):
        """数字を描くのは、開放済みのマスと、マージ先にできる未開放マス。ロックされたマスは描かない"""
        return cell.opened or self._field.is_mergeable(cell.x, cell.y)

    def _draw_cell(self, cell):
        """マスを 背景 → 枠線 → 数字 の順に描く"""
        left = FIELD_ORIGIN_X + CELL_PITCH * cell.x
        top = FIELD_ORIGIN_Y + CELL_PITCH * cell.y
        background = COLOR_OPENED_BG if cell.opened else COLOR_CLOSED_BG
        self._view.draw_rect(left, top, CELL_SIZE, CELL_SIZE, background)
        self._view.draw_rect_border(left, top, CELL_SIZE, CELL_SIZE, COLOR_BORDER)
        if cell.item is not None and self._is_number_visible(cell):
            self._draw_item_number(left, top, cell.item, _item_color(cell.item))

    def _draw_item_number(self, left, top, item, color):
        """左上が (left, top) のマスに、アイテムの数字を color で描く"""
        self._view.draw_text(
            left + TEXT_OFFSET_X, top + TEXT_OFFSET_Y, str(item.number), color
        )


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="pyxel merge")
        pyxel.mouse(True)  # カーソルを表示する
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(COLOR_SCREEN_BG)
        self._core.draw()


if __name__ == "__main__":
    App()
