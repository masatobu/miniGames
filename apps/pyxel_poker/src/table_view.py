"""4 人分の段とボタンのアイコンを画面に配置して描く（IView 経由）。"""

try:
    from .card_view import (  # pylint: disable=C0413
        CARD_HEIGHT,
        CARD_WIDTH,
        CHAR_WIDTH,
        IMAGE_BANK,
        TRANSPARENT_COLOR,
        draw_card,
        draw_card_back,
    )
except ImportError:
    from card_view import (  # pylint: disable=C0413
        CARD_HEIGHT,
        CARD_WIDTH,
        CHAR_WIDTH,
        IMAGE_BANK,
        TRANSPARENT_COLOR,
        draw_card,
        draw_card_back,
    )

SCREEN_WIDTH = 150
SCREEN_HEIGHT = 200
# 画面の背景色。Pyxel のパレットの 1（紺色）。灰色のアイコンが読み取りやすく、
# 白いカード（7）と黒い枠・数字（0）、白いコインの文字（7）のどれも読める
SCREEN_COLOR = 1
ROW_TOP = 6
ROW_PITCH = 40
# COM の 3 段の最初の段の上端と、段の間隔。人間の段（最下段）は ROW_TOP と ROW_PITCH で決まる
COM_ROW_TOP = 26
COM_ROW_PITCH = 32
COM_ROW_COUNT = 3
ICON_SIZE = 8
# 横方向の配置（タップしやすいよう余白を空ける）。アイコンの左 = 8、アイコンの右端 = 16 から
# 最初のカードまで 8、カードの間 = CARD_PITCH - CARD_WIDTH = 6、最後のカードの右端 =
# 24 + 4 * 20 + 14 = 118 から数字まで 8、3 桁の数字の右端 = 126 + 11 = 137 から画面の右端まで 13
ICON_X = 8
HUMAN_ICON_UV = (40, 0)
COM_ICON_UV = (48, 0)
HAND_X = 24
CARD_PITCH = 20
COIN_X = 126
COIN_TEXT_COLOR = 7
# 破産した段のアイコンと所持コインの色。Pyxel のパレットの 5（暗い青灰）。
# 背景（1、紺色）の上で読め、通常の白（7）より明らかに暗い
BANKRUPT_COLOR = 5
# パレットの色数。色 1〜15 を置き換える（0 は黒、透明色は blt の colkey が扱う）
PALETTE_SIZE = 16
# Pyxel の標準フォントの文字の高さ（縦の中央に置くために使う）
CHAR_HEIGHT = 5
# 選択中のカードを選択していないカードより上にずらす量（ピクセル）
SELECTED_OFFSET = 4
# 新しく引いたカードの枠の色。Pyxel のパレットの 10（黄）。外側 1 ピクセルに描く
NEW_CARD_FRAME_COLOR = 10
BUTTON_SIZE = 16
# ボタンの枠（アイコンの外側 2 ピクセル）の上端 = 168。最下段の手札の下端 = 156 から 12、
# 枠の下端 = 188 から画面の下端 = 200 まで 12 空く
BUTTON_Y = 170
DROP_BUTTON_X = 40
RAISE_BUTTON_X = 94
DROP_BUTTON_UV = (8, 0)
RAISE_BUTTON_UV = (24, 0)
# ボタンのアイコンの周りの枠（アイコンの外側の余白と色）
BUTTON_FRAME_PADDING = 2
BUTTON_FRAME_COLOR = 7
# 結果のポップアップ（画面の一番上の帯。段と重ならない）。左右は中央、上端は 8。
# 左上 = ((150 - 100) // 2, 8) = (25, 8)、下端 = 8 + 24 = 32。最初の COM のカードの上端 = 26 + 10 = 36
POPUP_WIDTH = 100
POPUP_HEIGHT = 24
POPUP_X = (SCREEN_WIDTH - POPUP_WIDTH) // 2
POPUP_Y = 8
POPUP_FILL_COLOR = 0
POPUP_FRAME_COLOR = 7
POPUP_TEXT_COLOR = 7
POPUP_MESSAGES = {"win": "WIN", "lose": "LOSE"}


# 複数行のときの行の間の隙間。行の送り = CHAR_HEIGHT + 3 = 8
POPUP_LINE_GAP = 3


def draw_centered_lines(
    view,
    lines,
    color,
    left=POPUP_X,
    top=POPUP_Y,
    width=POPUP_WIDTH,
    height=POPUP_HEIGHT,
):
    """矩形（既定は帯）の中央に lines を上から順に描く。各行は水平に、全体は垂直に中央寄せ。"""
    block_height = len(lines) * CHAR_HEIGHT + (len(lines) - 1) * POPUP_LINE_GAP
    block_top = top + (height - block_height) // 2
    for n, line in enumerate(lines):
        # 文字の幅 = 文字数 * CHAR_WIDTH - 1（最後の文字の右の隙間は含めない）
        text_width = CHAR_WIDTH * len(line) - 1
        view.text(
            left + (width - text_width) // 2,
            block_top + n * (CHAR_HEIGHT + POPUP_LINE_GAP),
            line,
            color,
        )


def draw_popup_box(view, left, top, width, height):
    """ポップアップの塗りと、その内側 1 ピクセルの枠を描く。"""
    view.rect(left, top, width, height, POPUP_FILL_COLOR)
    view.rectb(left + 1, top + 1, width - 2, height - 2, POPUP_FRAME_COLOR)


def draw_result_popup(view, result, amount=None):
    """結果のポップアップを描く。塗り → 枠 → 中央の文字。None なら何も描かない。

    win で amount（受け取ったポットの額）があれば、WIN と GOT N の 2 行にする。
    """
    if result is None:
        return
    if result not in POPUP_MESSAGES:
        raise ValueError(f"unknown result: {result!r}")
    lines = [POPUP_MESSAGES[result]]
    if result == "win" and amount is not None:
        lines.append(f"GOT {amount}")
    draw_popup_box(view, POPUP_X, POPUP_Y, POPUP_WIDTH, POPUP_HEIGHT)
    draw_centered_lines(view, lines, POPUP_TEXT_COLOR)


# セッション終了のポップアップ（画面の中央。結果ごとの 1 行目と、共通の 2 行目）。
# 余白は枠（内側 1 ピクセル）の外側を含む。幅 = 14 * 4 - 1 + 2 * 8 = 71（水平の範囲 39〜110 は
# アイコン〜16 と所持コイン 126〜の間）、高さ = 13 + 2 * 6 = 25（垂直の範囲 87〜112 は帯〜32 とボタン 168〜の間）
SESSION_POPUP_MESSAGES = {"win": "YOU WIN", "lose": "GAME OVER"}
SESSION_POPUP_RESTART = "TAP TO RESTART"
SESSION_POPUP_MARGIN_X = 8
SESSION_POPUP_MARGIN_Y = 6


def draw_session_popup(view, outcome):
    """セッション終了のポップアップを画面の中央に描く。None なら何も描かない。

    outcome は "win"（YOU WIN）か "lose"（GAME OVER）。2 行目は共通の TAP TO RESTART。
    """
    if outcome is None:
        return
    if outcome not in SESSION_POPUP_MESSAGES:
        raise ValueError(f"unknown outcome: {outcome!r}")
    lines = [SESSION_POPUP_MESSAGES[outcome], SESSION_POPUP_RESTART]
    text_width = max(CHAR_WIDTH * len(line) - 1 for line in lines)
    width = text_width + 2 * SESSION_POPUP_MARGIN_X
    height = (
        len(lines) * CHAR_HEIGHT
        + (len(lines) - 1) * POPUP_LINE_GAP
        + 2 * SESSION_POPUP_MARGIN_Y
    )
    left = (SCREEN_WIDTH - width) // 2
    top = (SCREEN_HEIGHT - height) // 2
    draw_popup_box(view, left, top, width, height)
    draw_centered_lines(view, lines, POPUP_TEXT_COLOR, left, top, width, height)


# 勝者のアイコンの周りの赤い枠（Pyxel の色 8）。アイコンの外側 2 ピクセルの余白、線の太さは 1
WINNER_FRAME_COLOR = 8
WINNER_FRAME_PADDING = 2


def draw_winner_frame(view, row_index):
    """勝者の段 row_index のアイコンの周りに赤い枠を描く。None なら何も描かない。"""
    if row_index is None:
        return
    size = ICON_SIZE + 2 * WINNER_FRAME_PADDING
    view.rectb(
        ICON_X - WINNER_FRAME_PADDING,
        row_top(row_index) + (ROW_PITCH - ICON_SIZE) // 2 - WINNER_FRAME_PADDING,
        size,
        size,
        WINNER_FRAME_COLOR,
    )


def row_top(row_index):
    """段 row_index（0 始まり。最後が人間）の上端 y。人間の段は COM の段とは別に決まる。"""
    if row_index < COM_ROW_COUNT:
        return COM_ROW_TOP + row_index * COM_ROW_PITCH
    return ROW_TOP + row_index * ROW_PITCH


# ポットの額 "POT n" の色。位置は結果のポップアップと同じ帯の中央（draw_centered_lines）
POT_TEXT_COLOR = 7


def draw_pot(view, amount):
    """ポットの額を "POT n" の形で、画面の一番上の帯の中央に描く。"""
    draw_centered_lines(view, [f"POT {amount}"], POT_TEXT_COLOR)


def draw_table(view, table, dropped=()):
    """画面全体を描く。背景 → 4 人分の段（上から順。dropped の段は手札を描かない）→ ボタンのアイコン。"""
    view.cls(SCREEN_COLOR)
    for row_index, player in enumerate(table.players):
        draw_player_row(view, row_index, player, hide_hand=row_index in dropped)
    draw_buttons(view)


def _draw_icon(view, top, icon_u, icon_v, dark):
    """段の上端 top にアイコンを描く。dark なら色 1〜15 を暗い色へ置き換えて描き、すぐ元に戻す。"""
    if dark:
        for color in range(1, PALETTE_SIZE):
            view.pal(color, BANKRUPT_COLOR)
    view.blt(
        ICON_X,
        top + (ROW_PITCH - ICON_SIZE) // 2,
        IMAGE_BANK,
        icon_u,
        icon_v,
        ICON_SIZE,
        ICON_SIZE,
        TRANSPARENT_COLOR,
    )
    if dark:
        view.pal_reset()


def draw_player_row(view, row_index, player, hide_hand=False):
    """1 段を描く。アイコン → 手札 → 所持コイン。hide_hand なら手札を描かない（ドロップした段）。

    COM の手札は、非公開（hand_public が False）なら裏面で描く。人間の手札は常に表。
    """
    top = row_top(row_index)
    icon_u, icon_v = HUMAN_ICON_UV if player.kind == "human" else COM_ICON_UV
    _draw_icon(view, top, icon_u, icon_v, player.bankrupt)
    hand = () if hide_hand or player.bankrupt else player.hand
    for n, card in enumerate(hand):
        x, y = card_position(row_index, n, player)
        if n in player.new_indices:
            view.rectb(
                x - 1, y - 1, CARD_WIDTH + 2, CARD_HEIGHT + 2, NEW_CARD_FRAME_COLOR
            )
        if player.kind == "com" and not player.hand_public:
            draw_card_back(view, x, y)
        else:
            draw_card(view, x, y, card)
    view.text(
        COIN_X,
        top + (ROW_PITCH - CHAR_HEIGHT) // 2,
        str(player.coins),
        BANKRUPT_COLOR if player.bankrupt else COIN_TEXT_COLOR,
    )


def hit_card(table, x, y):
    """人間の手札でクリックされたカードの位置（0 始まり）。当たらなければ None。"""
    human_row = len(table.players) - 1
    player = table.players[human_row]
    for n in range(len(player.hand)):
        card_x, card_y = card_position(human_row, n, player)
        if _inside(x, y, card_x, card_y, CARD_WIDTH, CARD_HEIGHT):
            return n
    return None


def hit_button(x, y):
    """クリックされたボタン（"drop"、"raise"）。当たらなければ None。枠の内側も押せる。"""
    framed_size = BUTTON_SIZE + 2 * BUTTON_FRAME_PADDING
    for name, button_x in (("drop", DROP_BUTTON_X), ("raise", RAISE_BUTTON_X)):
        if _inside(
            x,
            y,
            button_x - BUTTON_FRAME_PADDING,
            BUTTON_Y - BUTTON_FRAME_PADDING,
            framed_size,
            framed_size,
        ):
            return name
    return None


def card_position(row_index, n, player):
    """段 row_index の位置 n のカードの左上 (x, y)。描画と判定で共有する。"""
    top = row_top(row_index)
    card_y = top + (ROW_PITCH - CARD_HEIGHT) // 2
    if n in player.selected:
        card_y -= SELECTED_OFFSET
    return HAND_X + n * CARD_PITCH, card_y


def _inside(x, y, left, top, width, height):
    """半開区間 [left, left + width) × [top, top + height) に (x, y) が入るか。"""
    return left <= x < left + width and top <= y < top + height


def draw_buttons(view):
    """drop と Raise のボタンのアイコンを描く（表示のみ）。"""
    framed_size = BUTTON_SIZE + 2 * BUTTON_FRAME_PADDING
    for x, (u, v) in (
        (DROP_BUTTON_X, DROP_BUTTON_UV),
        (RAISE_BUTTON_X, RAISE_BUTTON_UV),
    ):
        view.rectb(
            x - BUTTON_FRAME_PADDING,
            BUTTON_Y - BUTTON_FRAME_PADDING,
            framed_size,
            framed_size,
            BUTTON_FRAME_COLOR,
        )
        view.blt(
            x,
            BUTTON_Y,
            IMAGE_BANK,
            u,
            v,
            BUTTON_SIZE,
            BUTTON_SIZE,
            TRANSPARENT_COLOR,
        )
