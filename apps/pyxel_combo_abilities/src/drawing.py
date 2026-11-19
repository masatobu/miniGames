"""テーブル側の図形描画（Pyxel に依存しない。View 経由で描く）。"""

try:
    from . import screen  # pylint: disable=C0413
    from .field import Field  # pylint: disable=C0413
    from .resource import Component, Resource  # pylint: disable=C0413
except ImportError:
    import screen  # pylint: disable=C0413
    from field import Field  # pylint: disable=C0413
    from resource import Component, Resource  # pylint: disable=C0413


# 画像（icon.pyxres）は透過色 0 の上に単色（ラベンダー）で描かれている
IMAGE_COLOR = screen.COLOR_LAVENDER

# リソースの種類（Resource の ID の十の位）ごとの画像の名前
KIND_IMAGES = {1: "things", 2: "star", 3: "bolt"}
COMPONENT_IMAGES = {
    Component.ENGINE: "engine",
    Component.GUN: "gun",
    Component.BODY: "body",
}


def draw_image(view, u, v, x, y, size, color):
    """画像（バンク 0 の (u, v) から size × size）を、色 color で (x, y) に描く。

    単色の画像なので、pal で画像の色だけを color に置き換えて描き、すぐ元に戻す。
    """
    view.pal(IMAGE_COLOR, color)
    view.blt(x, y, u, v, size, size, screen.IMAGE_COLKEY)
    view.pal()


def _draw_icon(view, name, x, y, color):
    """アイコンの画像 name（16 × 16）を、色 color で枠の左上 (x, y) に合わせて描く。"""
    u, v = screen.ICON_UV[name]
    draw_image(view, u, v, x, y, screen.ICON_CELL, color)


def _draw_resource(view, resource, x, y):
    """リソースを、種類の画像・ランクの色で描く。"""
    name = KIND_IMAGES[resource.value[0] // 10]
    _draw_icon(view, name, x, y, screen.RANK_COLORS[Resource.get_rank(resource)])


def _draw_empty(view, mask, x, y):
    """空の枠を、受け入れる種類の画像・暗い色で描く。"""
    _draw_icon(view, KIND_IMAGES[mask.value // 10], x, y, screen.EMPTY_COLOR)


def _draw_slot(view, resource, mask, x, y):
    if resource is not None:
        _draw_resource(view, resource, x, y)
    elif mask is not None:
        _draw_empty(view, mask, x, y)


def _draw_garage(view, garage):
    for comp in Component.tuned():
        x, y = screen.icon_pos(comp)
        color = screen.LEVEL_COLORS[garage.get_lv(comp) - 1]
        _draw_icon(view, COMPONENT_IMAGES[comp], x, y, color)
        for idx, mask in enumerate(comp.value):
            bx, by = screen.box_pos(comp, idx)
            size = screen.ICON_SIZE
            view.fill_rect(bx, by, size, size, screen.SLOT_BG_COLOR)
            _draw_slot(view, garage.get_box_resources(comp)[idx], mask, bx, by)


def _draw_stock(view, garage):
    view.fill_rect(
        screen.PANEL_X,
        screen.PANEL_Y,
        screen.PANEL_W,
        screen.PANEL_H,
        screen.PANEL_COLOR,
    )
    for idx, resource in enumerate(garage.get_box_resources(Component.STOCK)):
        if resource is not None:
            _draw_resource(view, resource, *screen.stock_pos(idx))


def _draw_turn_bar(view, turn, max_turn):
    """残りターンのバー: 枠 → 内側 → 残りターン分の四角（左端を固定して右端が左へ寄る）。"""
    view.fill_rect(
        screen.TURN_BAR_X,
        screen.TURN_BAR_Y,
        screen.TURN_BAR_W,
        screen.TURN_BAR_H,
        screen.TURN_BAR_FRAME_COLOR,
    )
    x, y, w, h = screen.turn_bar_inner_rect()
    view.fill_rect(x, y, w, h, screen.TURN_BAR_BACK_COLOR)
    fill_w = screen.turn_bar_fill_width(turn, max_turn)
    if fill_w > 0:
        view.fill_rect(x, y, fill_w, h, screen.TURN_BAR_FILL_COLOR)


def _draw_execute_button(view):
    """決定ボタン: 枠と塗りつぶしの四角の上に、画像 execute を描く（BUTTON_X・BUTTON_Y が中心）。"""
    x, y, w, h = screen.button_frame_rect()
    border = screen.BUTTON_BORDER
    view.fill_rect(x, y, w, h, screen.BUTTON_BORDER_COLOR)
    view.fill_rect(
        x + border, y + border, w - 2 * border, h - 2 * border, screen.BUTTON_COLOR
    )
    _draw_icon(view, "execute", *screen.button_icon_pos(), screen.BUTTON_ICON_COLOR)


def draw_table(view, garage, turn, max_turn):
    """テーブル（部品と枠、ストック、残りターンのバー、決定ボタン）を描く。"""
    _draw_garage(view, garage)
    _draw_stock(view, garage)
    _draw_turn_bar(view, turn, max_turn)
    _draw_execute_button(view)


def draw_selector(view, point):
    """選択中の枠 point（(Component, 枠の番号)。None なら何もしない）に、赤い四角の枠線を描く。

    枠線はアイコンの範囲 ICON_SIZE の外周に沿う 1 ピクセルの線で、中は塗らない（アイコンが見える）。
    """
    if point is None:
        return
    comp, idx = point
    x, y = (
        screen.stock_pos(idx) if comp == Component.STOCK else screen.box_pos(comp, idx)
    )
    size, color = screen.ICON_SIZE, screen.SELECTOR_COLOR
    view.fill_rect(x, y, size, 1, color)  # 上の辺
    view.fill_rect(x, y + size - 1, size, 1, color)  # 下の辺
    view.fill_rect(x, y + 1, 1, size - 2, color)  # 左の辺
    view.fill_rect(x + size - 1, y + 1, 1, size - 2, color)  # 右の辺


# 敵の見た目: (レベルの上限（この値は含まない）, 画像の名前, 色)。上から順に最初に当てはまるもの
ENEMY_STYLES = [
    (5, "rock", screen.COLOR_BROWN),
    (10, "rock", screen.COLOR_LIGHT_GRAY),
    (15, "fighter", screen.COLOR_BLUE),
    (20, "fighter", screen.COLOR_GREEN),
    (25, "fighter", screen.COLOR_RED),
    (30, "fighter", screen.COLOR_BLACK),
    (35, "ufo", screen.COLOR_BLUE),
    (40, "ufo", screen.COLOR_GREEN),
    (45, "ufo", screen.COLOR_YELLOW),
    (55, "ufo", screen.COLOR_RED),
]
LAST_ENEMY_STYLE = ("ufo", screen.COLOR_DARK_GRAY)


def enemy_style(level):
    """レベルに応じた敵の (画像の名前, 色)。"""
    for limit, name, color in ENEMY_STYLES:
        if level < limit:
            return name, color
    return LAST_ENEMY_STYLE


def _draw_field_image(view, name, x, y, color):
    """フィールドの画像 name（8 × 8）を、色 color で左上 (x, y) に描く。"""
    u, v = screen.FIELD_UV[name]
    draw_image(view, u, v, x, y, screen.FIELD_CELL, color)


def draw_field(view, level, body_level, positions):
    """フィールド（背景・自機・敵）を描く。positions は敵の左上の位置のリスト。"""
    view.fill_rect(0, 0, screen.SCREEN_W, screen.FIELD_H, screen.FIELD_COLOR)
    ship_color = screen.LEVEL_COLORS[body_level - 1]
    _draw_field_image(view, "ship", screen.SHIP_X, screen.SHIP_Y, ship_color)
    name, color = enemy_style(level)
    for x, y in positions:
        _draw_field_image(view, name, x, y, color)


def enemy_positions(rand):
    """敵の位置（右半分・フィールド内の乱数の位置）を、敵の最大数ぶん返す。

    rand は 0 以上 1 未満の乱数を返す関数。
    """
    x_range = screen.SCREEN_W - screen.ENEMY_SIZE - screen.ENEMY_X_MIN + 1
    y_range = screen.FIELD_H - screen.ENEMY_SIZE + 1
    return [
        (screen.ENEMY_X_MIN + int(rand() * x_range), int(rand() * y_range))
        for _ in range(Field.MAX_NPC_NUM)
    ]


def draw_laser(view):
    """発射中のレーザー: 自機の先端から画面の右端まで、自機の高さの中央に引く。"""
    y = screen.SHIP_Y + screen.ENEMY_SIZE // 2
    view.draw_line(
        screen.SHIP_X + screen.ENEMY_SIZE, y, screen.SCREEN_W - 1, y, screen.LASER_COLOR
    )


def draw_explosion(view, positions):
    """爆発中の敵の位置（左上）の中心に、爆発の円を描く。"""
    half = screen.ENEMY_SIZE // 2
    for x, y in positions:
        view.fill_circ(x + half, y + half, screen.EXPLOSION_R, screen.EXPLOSION_COLOR)


def _draw_centered_text(view, center_x, y, text, color):
    """center_x を中心にして、文字列を描く（Pyxel の既定フォントの幅で左端を決める）。"""
    view.draw_text(center_x - screen.CHAR_W * len(text) // 2, y, text, color)


def draw_game_over_menu(view, kills):
    """ゲームオーバーのメニュー: 背後を暗くし、中央の枠に Game Over・Kills・New Game を描く。"""
    view.set_alpha(screen.DIM_ALPHA)
    view.fill_rect(0, 0, screen.SCREEN_W, screen.SCREEN_H, screen.DIM_COLOR)
    view.set_alpha(1.0)
    view.fill_rect(*screen.MENU_RECT, screen.MENU_COLOR)
    center_x = screen.MENU_X + screen.MENU_W // 2
    _draw_centered_text(
        view, center_x, screen.MENU_TITLE_Y, screen.MENU_TITLE, screen.TEXT_COLOR
    )
    _draw_centered_text(
        view, center_x, screen.MENU_KILLS_Y, f"Kills: {kills}", screen.TEXT_COLOR
    )
    view.fill_rect(*screen.NEW_GAME_RECT, screen.NEW_GAME_COLOR)
    button_x, button_y, button_w, button_h = screen.NEW_GAME_RECT
    _draw_centered_text(
        view,
        button_x + button_w // 2,
        button_y + (button_h - screen.CHAR_H) // 2,
        screen.NEW_GAME_LABEL,
        screen.TEXT_COLOR,
    )
