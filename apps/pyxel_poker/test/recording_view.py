"""描画の呼び出しを順に記録するテスト用 View（Pyxel を初期化しない）。"""

from src.main import IView


class RecordingView(IView):
    """IView の描画メソッドの呼び出しを、引数とともに calls に記録する。"""

    def __init__(self):
        self.calls = []

    def draw_text(self, x, y, text):
        self.calls.append(("draw_text", x, y, text))

    def rect(self, x, y, w, h, color):
        self.calls.append(("rect", x, y, w, h, color))

    def rectb(self, x, y, w, h, color):
        self.calls.append(("rectb", x, y, w, h, color))

    def text(self, x, y, text, color):
        self.calls.append(("text", x, y, text, color))

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.calls.append(("blt", x, y, img, u, v, w, h, colkey))

    def cls(self, color):
        self.calls.append(("cls", color))

    def pal(self, src, dst):
        self.calls.append(("pal", src, dst))

    def pal_reset(self):
        self.calls.append(("pal_reset",))
