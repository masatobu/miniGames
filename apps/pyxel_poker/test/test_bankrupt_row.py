import unittest
from test.recording_view import RecordingView
from src import table_view
from src.card_view import IMAGE_BANK, TRANSPARENT_COLOR
from src.cards import Table
from src.table_view import (
    CHAR_HEIGHT,
    COIN_TEXT_COLOR,
    COIN_X,
    COM_ICON_UV,
    HUMAN_ICON_UV,
    ICON_SIZE,
    ICON_X,
    ROW_PITCH,
    draw_player_row,
    row_top,
)

ICON_UVS = (HUMAN_ICON_UV, COM_ICON_UV)
# 色の置き換えの対象 = パレットの 1〜15（0 は背景の黒で、透明色は blt の colkey が扱う）
REMAPPED_COLORS = range(1, 16)
COM_ROW = 0


def bankrupt_com(table):
    """手札を持ったまま破産した COM（行の描画が bankrupt を読むことを確かめるため）。"""
    player = table.players[COM_ROW]
    player.bankrupt = True
    player.coins = 0
    return player


def draw_row(player, hide_hand=False):
    view = RecordingView()
    draw_player_row(view, COM_ROW, player, hide_hand=hide_hand)
    return view.calls


def icon_blts(calls):
    return [c for c in calls if c[0] == "blt" and (c[4], c[5]) in ICON_UVS]


def coin_texts(calls):
    return [c for c in calls if c[0] == "text" and c[1] == COIN_X]


class TestBankruptRow(unittest.TestCase):
    def setUp(self):
        self.table = Table.deal(0)

    def test_bankrupt_row_draws_no_cards(self):
        """破産した段は、手札を持っていても、カードを 1 枚も描かないこと（BR3.1）"""
        player = bankrupt_com(self.table)
        self.assertTrue(player.hand)
        calls = draw_row(player)
        # カードの呼び出しはアイコンと所持コイン以外の呼び出し（rect・rectb・手札の blt）
        others = [c for c in calls if c[0] in ("rect", "rectb")]
        self.assertEqual([], others)
        self.assertEqual(1, len(icon_blts(calls)))
        self.assertEqual(1, len([c for c in calls if c[0] == "blt"]))

    def test_bankrupt_icon_is_drawn_between_palette_remap_and_reset(self):
        """破産した段のアイコンは、色 1〜15 を暗い色へ置き換え → blt → 元に戻す の順で描かれること（BR3.2、BR3.4）"""
        calls = draw_row(bankrupt_com(self.table))
        pal_calls = [("pal", c, table_view.BANKRUPT_COLOR) for c in REMAPPED_COLORS]
        icon = icon_blts(calls)[0]
        top = row_top(COM_ROW) + (ROW_PITCH - ICON_SIZE) // 2
        expected_blt = (
            "blt",
            ICON_X,
            top,
            IMAGE_BANK,
            COM_ICON_UV[0],
            COM_ICON_UV[1],
            ICON_SIZE,
            ICON_SIZE,
            TRANSPARENT_COLOR,
        )
        self.assertEqual(expected_blt, icon)
        blt_at = calls.index(icon)
        self.assertEqual(pal_calls, calls[blt_at - len(pal_calls) : blt_at])
        self.assertEqual(("pal_reset",), calls[blt_at + 1])

    def test_bankrupt_coin_is_drawn_in_dark_color_with_number_only(self):
        """破産した段の所持コインは、暗い色で、プレイヤーの所持コインの数だけが描かれること（BR3.3）"""
        player = bankrupt_com(self.table)
        calls = draw_row(player)
        center_y = row_top(COM_ROW) + (ROW_PITCH - CHAR_HEIGHT) // 2
        expected = (
            "text",
            COIN_X,
            center_y,
            str(player.coins),
            table_view.BANKRUPT_COLOR,
        )
        self.assertEqual([expected], coin_texts(calls))
        # OUT などの余計な文字は描かない（文字の呼び出しは所持コインの 1 回だけ）
        self.assertEqual(1, len([c for c in calls if c[0] == "text"]))

    def test_normal_row_makes_no_palette_calls(self):
        """破産していない段は、pal／pal_reset を呼ばず、通常の色で描かれること（BR3.5）"""
        player = self.table.players[COM_ROW]
        calls = draw_row(player)
        self.assertEqual([], [c for c in calls if c[0] in ("pal", "pal_reset")])
        expected_coin = (
            "text",
            COIN_X,
            row_top(COM_ROW) + (ROW_PITCH - CHAR_HEIGHT) // 2,
            str(player.coins),
            COIN_TEXT_COLOR,
        )
        self.assertEqual([expected_coin], coin_texts(calls))

    def test_dropped_row_is_distinguishable_from_bankrupt_row(self):
        """ドロップした段（手札なし）は通常の色で描かれ、破産した段と見分けられること（BR3.6）"""
        dropped = draw_row(self.table.players[COM_ROW], hide_hand=True)
        bankrupt = draw_row(bankrupt_com(Table.deal(0)))
        self.assertEqual([], [c for c in dropped if c[0] in ("pal", "pal_reset")])
        self.assertEqual(COIN_TEXT_COLOR, coin_texts(dropped)[0][4])
        self.assertEqual(table_view.BANKRUPT_COLOR, coin_texts(bankrupt)[0][4])
        self.assertNotEqual(coin_texts(dropped)[0][4], coin_texts(bankrupt)[0][4])
        self.assertNotEqual(dropped, bankrupt)

    def test_bankrupt_color_is_a_palette_color_distinct_from_coin_color(self):
        """暗い色は定数で、パレットの範囲内にあり、通常のコインの色と異なること"""
        self.assertIn(table_view.BANKRUPT_COLOR, REMAPPED_COLORS)
        self.assertNotEqual(COIN_TEXT_COLOR, table_view.BANKRUPT_COLOR)


if __name__ == "__main__":
    unittest.main()
