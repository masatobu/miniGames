"""描画呼び出しを記録するテスト用の View。"""

from src.main import IView


class FakeView(IView):
    """IView の呼び出しを (メソッド名, 引数...) のタプルで記録する。Pyxel は使わない。"""

    def __init__(self):
        self.calls = []
        self.clicks = []

    def queue_click(self, x, y):
        """次の mouse_click() で返すクリックの座標を、1 件仕込む。"""
        self.clicks.append((x, y))

    def mouse_click(self):
        return self.clicks.pop(0) if self.clicks else None

    def fill_rect(self, x, y, w, h, color):
        self.calls.append(("fill_rect", x, y, w, h, color))

    def fill_circ(self, x, y, r, color):
        self.calls.append(("fill_circ", x, y, r, color))

    def draw_line(self, x1, y1, x2, y2, color):
        self.calls.append(("draw_line", x1, y1, x2, y2, color))

    def fill_tri(self, x1, y1, x2, y2, x3, y3, color):
        self.calls.append(("fill_tri", x1, y1, x2, y2, x3, y3, color))

    def draw_text(self, x, y, text, color=7):
        self.calls.append(("draw_text", x, y, text, color))

    def set_alpha(self, alpha):
        self.calls.append(("set_alpha", alpha))

    def blt(self, x, y, u, v, w, h, colkey):
        self.calls.append(("blt", x, y, u, v, w, h, colkey))

    def pal(self, src=None, dst=None):
        if src is None:
            self.calls.append(("pal",))
        else:
            self.calls.append(("pal", src, dst))

    def image_at(self, x, y):
        """位置 (x, y) に blt で描かれた画像の (u, v, 大きさ, 色) を返す。描かれていなければ None。

        pal(画像の色, 色) → blt → pal() の並びで描かれていることも検証する。
        """
        for i, call in enumerate(self.calls):
            if call[:3] == ("blt", x, y):
                _, _, _, u, v, w, h, _ = call
                assert w == h, call
                before, after = self.calls[i - 1], self.calls[i + 1]
                assert before[0] == "pal" and len(before) == 3, before
                assert after == ("pal",), after
                return u, v, w, before[2]
        return None

    @staticmethod
    def points(call):
        """図形の呼び出しが触れる画素の範囲を (左上, 右下) の座標で返す。文字などは None。"""
        name = call[0]
        if name == "fill_rect":
            _, x, y, w, h, _ = call
            return [(x, y), (x + w - 1, y + h - 1)]
        if name == "fill_circ":
            _, x, y, r, _ = call
            return [(x - r, y - r), (x + r, y + r)]
        if name == "draw_line":
            return [(call[1], call[2]), (call[3], call[4])]
        if name == "fill_tri":
            return [(call[1], call[2]), (call[3], call[4]), (call[5], call[6])]
        return None

    def shapes_in(self, x, y, size):
        """正方形の領域 (x, y, size) の中に収まる図形の呼び出しだけを返す。"""
        found = []
        for call in self.calls:
            pts = self.points(call)
            if pts and all(x <= px < x + size and y <= py < y + size for px, py in pts):
                found.append(call)
        return found
