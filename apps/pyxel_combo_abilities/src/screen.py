"""画面のサイズ・位置・色の定義（Pyxel に依存しない）。

位置は、移植元の画面（750 × 1334）を 180 × 320 に縮めた値（約 0.24 倍）。
"""

try:
    from .resource import Component  # pylint: disable=C0413
except ImportError:
    from resource import Component  # pylint: disable=C0413

SCREEN_W = 180
SCREEN_H = 320

FIELD_RATE = 0.3
FIELD_H = int(SCREEN_H * FIELD_RATE)
TABLE_Y = FIELD_H
TABLE_H = SCREEN_H - TABLE_Y

# 枠の大きさ。アイコンの画像（ICON_CELL = 16）と同じ大きさにして、アイコンが枠の中心に来るようにする
ICON_SIZE = 16

# Pyxel の既定パレットの色番号
COLOR_BLACK = 0
COLOR_NAVY = 1
COLOR_BROWN = 4
COLOR_DARK_GRAY = 5
COLOR_LIGHT_GRAY = 6
COLOR_LAVENDER = 13
COLOR_WHITE = 7
COLOR_RED = 8
COLOR_ORANGE = 9
COLOR_YELLOW = 10
COLOR_GREEN = 11
COLOR_BLUE = 12

FIELD_COLOR = COLOR_NAVY
TABLE_COLOR = COLOR_DARK_GRAY
TEXT_COLOR = COLOR_WHITE
EMPTY_COLOR = COLOR_BLACK
PANEL_COLOR = COLOR_LAVENDER
SLOT_BG_COLOR = COLOR_LAVENDER  # 部品の枠の背景（ストックのパネルと同じ色）
SELECTOR_COLOR = COLOR_RED

# 画像リソース（icon.pyxres の画像バンク 0）。セルの左上 (u, v) と、透過色
RESOURCE_FILE = "icon.pyxres"
IMAGE_COLKEY = COLOR_BLACK
ICON_CELL = 16
ICON_UV = {
    "engine": (8, 0),
    "gun": (24, 0),
    "body": (40, 0),
    "things": (8, 16),
    "star": (24, 16),
    "bolt": (40, 16),
    "execute": (8, 32),
}
FIELD_CELL = 8
FIELD_UV = {
    "ship": (8, 48),
    "spare": (16, 48),
    "rock": (24, 48),
    "fighter": (32, 48),
    "ufo": (40, 48),
}

# 部品のレベル 1〜4 の色
LEVEL_COLORS = [COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE, COLOR_RED]
# リソースのランク値（1=BRONZE、2=SILVER、3=GOLD）の色
RANK_COLORS = {1: COLOR_BROWN, 2: COLOR_WHITE, 3: COLOR_YELLOW}

# フィールドの自機と敵（同じ大きさの正方形の中に描く）
ENEMY_SIZE = FIELD_CELL  # 画像のセルの大きさに揃える
SHIP_X = 17
SHIP_Y = FIELD_H // 2 - ENEMY_SIZE // 2
ENEMY_X_MIN = SCREEN_W // 2

# 攻撃のアニメーション（Pyxel の既定の 30 fps で、約 0.1 秒 = 3 フレーム）
LAUNCH_FRAMES = 3
EXPLODE_FRAMES = 3
LASER_COLOR = COLOR_YELLOW
EXPLOSION_COLOR = COLOR_ORANGE
EXPLOSION_R = ENEMY_SIZE // 2 + 2

# 部品の枠: 列（アイコン・枠 1・枠 2）と行（ENGINE・GUN・BODY）
COL_X = [17, 50, 83]
# 最上位の行の上端は、ストックのパネルの上端（TABLE_Y + 22）と揃える
ROW_Y = [TABLE_Y + 22 + 31 * i for i in range(3)]

# ストックのパネルと、その中のリソースの並び
PANEL_X = 128
PANEL_Y = TABLE_Y + 22
PANEL_W = 35
PANEL_H = 180
STOCK_X = PANEL_X + (PANEL_W - ICON_SIZE) // 2
STOCK_Y = PANEL_Y + 9
STOCK_STEP = 31

# 左下の残りターンのバーと決定ボタン。バーは、枠（全体 = 最大ターン分）の中を、残りターンに比例する長さの四角で塗る
TURN_BAR_X = 13  # 画面の左端からの余白。右隣のストックのパネルとの余白も同じ幅にする
TURN_BAR_Y = TABLE_Y + 153
TURN_BAR_W = PANEL_X - 2 * TURN_BAR_X
TURN_BAR_H = 8
TURN_BAR_BORDER = 1
TURN_BAR_FRAME_COLOR = COLOR_WHITE
TURN_BAR_BACK_COLOR = COLOR_DARK_GRAY
TURN_BAR_FILL_COLOR = COLOR_GREEN
BUTTON_X = TURN_BAR_X + TURN_BAR_W // 2  # 残りターンのバーの横方向の中心に揃える
# 決定ボタンの枠（高さ BUTTON_FRAME_SIZE = 24）の下端を、ストックのパネルの下端に揃える
BUTTON_Y = PANEL_Y + PANEL_H - 12
# 決定ボタン: 画像（BUTTON_ICON_COLOR）を、枠（BUTTON_BORDER_COLOR）と面（BUTTON_COLOR）の四角が囲む。
# 当たり判定も、この枠の四角（button_frame_rect）
BUTTON_ICON_COLOR = COLOR_WHITE
BUTTON_COLOR = COLOR_BLUE
BUTTON_BORDER_COLOR = COLOR_NAVY
BUTTON_BORDER = 1
BUTTON_FRAME_SIZE = 24

# ゲームオーバーのメニュー: 画面の中央に重ねる枠。背後は半透明の黒で暗くする
DIM_COLOR = COLOR_BLACK
DIM_ALPHA = 0.5
MENU_W = 120
MENU_H = 90
MENU_X = (SCREEN_W - MENU_W) // 2
MENU_Y = (SCREEN_H - MENU_H) // 2
MENU_RECT = (MENU_X, MENU_Y, MENU_W, MENU_H)
MENU_COLOR = COLOR_DARK_GRAY
MENU_TITLE = "Game Over"
MENU_TITLE_Y = MENU_Y + 14
MENU_KILLS_Y = MENU_Y + 34
NEW_GAME_LABEL = "New Game"
NEW_GAME_W = 80
NEW_GAME_H = 20
NEW_GAME_X = MENU_X + (MENU_W - NEW_GAME_W) // 2
NEW_GAME_Y = MENU_Y + 56
NEW_GAME_RECT = (NEW_GAME_X, NEW_GAME_Y, NEW_GAME_W, NEW_GAME_H)
NEW_GAME_COLOR = COLOR_BLUE
# Pyxel の既定フォントの文字の大きさ
CHAR_W = 4
CHAR_H = 6


def icon_pos(component):
    """部品のアイコンの左上。"""
    return COL_X[0], ROW_Y[_row(component)]


def turn_bar_inner_rect():
    """バーの内側（枠線を除いた四角）(x, y, w, h)。"""
    b = TURN_BAR_BORDER
    return TURN_BAR_X + b, TURN_BAR_Y + b, TURN_BAR_W - 2 * b, TURN_BAR_H - 2 * b


def turn_bar_fill_width(turn, max_turn):
    """バーの四角の長さ。残りターン（max_turn − turn）に比例し、0〜内側の幅に収める。

    開始時（ターン 1）で満タン、最大ターン（ゲームオーバー）で 0。
    """
    inner_w = turn_bar_inner_rect()[2]
    steps = max_turn - 1
    remaining = min(max(max_turn - turn, 0), steps)
    return inner_w * remaining // steps


def button_icon_pos():
    """決定ボタンの画像（ICON_CELL × ICON_CELL）の左上。BUTTON_X・BUTTON_Y が中心になる位置。"""
    return BUTTON_X - ICON_CELL // 2, BUTTON_Y - ICON_CELL // 2


def button_frame_rect():
    """決定ボタンの枠の四角 (x, y, w, h)。BUTTON_X・BUTTON_Y が中心になる。"""
    half = BUTTON_FRAME_SIZE // 2
    return BUTTON_X - half, BUTTON_Y - half, BUTTON_FRAME_SIZE, BUTTON_FRAME_SIZE


def box_pos(component, index):
    """部品の枠 index（0 か 1）の左上。"""
    return COL_X[1 + index], ROW_Y[_row(component)]


def stock_pos(index):
    """ストックの枠 index の左上。"""
    return STOCK_X, STOCK_Y + STOCK_STEP * index


def _row(component):
    return Component.tuned().index(component)
