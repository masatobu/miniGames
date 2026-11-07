"""カード 1 枚を表向きに描く（IView 経由。Pyxel を直接呼ばない）。"""

CARD_WIDTH = 14
CARD_HEIGHT = 20
SYMBOL_SIZE = 8
IMAGE_BANK = 0
TRANSPARENT_COLOR = 0
BACKGROUND_COLOR = 7
FRAME_COLOR = 0
# 裏面の塗りの色。Pyxel のパレットの 12（水色）。表向き（7）と区別でき、紺色の背景（1）の上で読める
CARD_BACK_COLOR = 12
TEXT_COLOR = 0
CHAR_WIDTH = 4
TEXT_Y_OFFSET = 2
SYMBOL_Y_OFFSET = 10

SUIT_IMAGE_UV = {
    "spade": (8, 16),
    "club": (16, 16),
    "diamond": (24, 16),
    "heart": (32, 16),
}
FACE_LABELS = {11: "J", 12: "Q", 13: "K", 14: "A"}


def rank_label(rank):
    """数値を表記の文字に変える。"""
    return FACE_LABELS.get(rank, str(rank))


def draw_card(view, x, y, card):
    """x, y を左上として card を表向きに描く。"""
    view.rect(x, y, CARD_WIDTH, CARD_HEIGHT, BACKGROUND_COLOR)
    view.rectb(x, y, CARD_WIDTH, CARD_HEIGHT, FRAME_COLOR)
    u, v = SUIT_IMAGE_UV[card.suit]
    view.blt(
        x + (CARD_WIDTH - SYMBOL_SIZE) // 2,
        y + SYMBOL_Y_OFFSET,
        IMAGE_BANK,
        u,
        v,
        SYMBOL_SIZE,
        SYMBOL_SIZE,
        TRANSPARENT_COLOR,
    )
    label = rank_label(card.rank)
    # 文字幅 = 1 文字 4px、最後の文字の右の隙間 1px を除く。中央に置く
    text_width = CHAR_WIDTH * len(label) - 1
    view.text(x + (CARD_WIDTH - text_width) // 2, y + TEXT_Y_OFFSET, label, TEXT_COLOR)


def draw_card_back(view, x, y):
    """x, y を左上として、カードの裏面を描く。塗り → 枠。図形だけで、画像と文字は使わない。"""
    view.rect(x, y, CARD_WIDTH, CARD_HEIGHT, CARD_BACK_COLOR)
    view.rectb(x, y, CARD_WIDTH, CARD_HEIGHT, FRAME_COLOR)
