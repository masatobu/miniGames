"""操作（クリック座標の判定と、選択・入れ替え・攻撃の状態遷移）。Pyxel に依存しない。"""

try:
    from . import screen  # pylint: disable=C0413
    from .resource import Component  # pylint: disable=C0413
except ImportError:
    import screen  # pylint: disable=C0413
    from resource import Component  # pylint: disable=C0413

BUTTON = "button"


def _in_icon(x, y, left, top):
    """(x, y) が、左上 (left, top)・ICON_SIZE 四方の領域の内側（端を含む）か。"""
    return left <= x < left + screen.ICON_SIZE and top <= y < top + screen.ICON_SIZE


def _in_button(x, y):
    """(x, y) が、決定ボタンの枠の四角（screen.button_frame_rect。端を含む）の内側か。"""
    left, top, width, height = screen.button_frame_rect()
    return left <= x < left + width and top <= y < top + height


def in_new_game(x, y):
    """(x, y) が、ゲームオーバーのメニューの New Game ボタンの矩形の内側（端を含む）か。"""
    left, top, width, height = screen.NEW_GAME_RECT
    return left <= x < left + width and top <= y < top + height


class Operation:
    """選択状態を持ち、クリックされた対象に応じて、入れ替えと攻撃を行う。

    selected は選択中の枠 (Component, 枠の番号)。何も選択していなければ None。
    選択はゲームのルールではなく画面の操作の状態なので、game 側には持たせない。
    """

    def __init__(self, game):
        self.game = game
        self.selected = None

    def click(self, target):
        """対象（hit_test の結果）をクリックしたときの動作。

        ターン数が最大に達していれば何もしない。対象なしも何もしない。
        決定ボタンのときだけ、攻撃 1 回ごとの結果の列（AttackStep）を返す。それ以外は None。
        決定ボタンでは選択を解除しない（移植元は、ターンの終わりまで選択の表示を残す。
        解除は、攻撃の再生が終わったときに呼び出し側が行う）。
        """
        if self.game.is_end() or target is None:
            return None
        if target == BUTTON:
            return self.game.play_turn()
        if self.selected is None:
            self.selected = target
        else:
            self.game.garage.change(self.selected, target)
            self.selected = None
        return None


def hit_test(garage, x, y):
    """座標 (x, y) でクリックできる対象を返す。

    部品の枠かリソースの入ったストックの枠なら (Component, 枠の番号)、
    決定ボタンなら BUTTON、どれにも当たらなければ None。
    """
    for comp in Component.tuned():
        for idx in range(len(comp.value)):
            if _in_icon(x, y, *screen.box_pos(comp, idx)):
                return comp, idx
    stock = garage.get_box_resources(Component.STOCK)
    for idx, resource in enumerate(stock):
        if resource is not None and _in_icon(x, y, *screen.stock_pos(idx)):
            return Component.STOCK, idx
    if _in_button(x, y):
        return BUTTON
    return None
