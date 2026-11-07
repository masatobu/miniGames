# title: pyxel poker
# author: masatobu

from abc import ABC, abstractmethod

try:
    from .game import Action, Game, Phase  # pylint: disable=C0413
    from .table_view import (
        SCREEN_HEIGHT,
        SCREEN_WIDTH,
        draw_pot,
        draw_result_popup,
        draw_session_popup,
        draw_table,
        draw_winner_frame,
        hit_button,
        hit_card,
    )  # pylint: disable=C0413
except ImportError:
    from game import Action, Game, Phase  # pylint: disable=C0413
    from table_view import (
        SCREEN_HEIGHT,
        SCREEN_WIDTH,
        draw_pot,
        draw_result_popup,
        draw_session_popup,
        draw_table,
        draw_winner_frame,
        hit_button,
        hit_card,
    )  # pylint: disable=C0413


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    # 以下の描画メソッドは抽象にしない（draw_text だけを実装する既存のテスト用 View を壊さないため）
    def rect(self, x, y, w, h, color):
        raise NotImplementedError

    def rectb(self, x, y, w, h, color):
        raise NotImplementedError

    def text(self, x, y, text, color):
        raise NotImplementedError

    def blt(self, x, y, img, u, v, w, h, colkey):
        raise NotImplementedError

    def cls(self, color):
        raise NotImplementedError

    def pal(self, src, dst):
        raise NotImplementedError

    def pal_reset(self):
        raise NotImplementedError

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def rectb(self, x, y, w, h, color):
        self.pyxel.rectb(x, y, w, h, color)

    def text(self, x, y, text, color):
        self.pyxel.text(x, y, text, color)

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def cls(self, color):
        self.pyxel.cls(color)

    def pal(self, src, dst):
        self.pyxel.pal(src, dst)

    def pal_reset(self):
        self.pyxel.pal()


class IInput(ABC):
    @abstractmethod
    def is_click(self):
        pass

    @abstractmethod
    def get_mouse_x(self):
        pass

    @abstractmethod
    def get_mouse_y(self):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_click(self):
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_x(self):
        return self.pyxel.mouse_x

    def get_mouse_y(self):
        return self.pyxel.mouse_y


class GameCore:
    """1 ゲームの進行（Game）を持ち、クリックを drop／Raise／カードの選択に振り分けて、毎フレーム描く。"""

    def __init__(self, input=None, view=None, seed=None):  # pylint: disable=W0622
        self._input = input if input is not None else PyxelInput.create()
        self._view = view if view is not None else PyxelView.create()
        # 今のゲームの種。次のゲームごとに 1 ずつ増やす（None は毎回 None = 乱数）
        self._seed = seed
        # 配札と参加費の支払いを済ませた 1 ゲーム。段階・勝者・ポットは Game が持つ
        self._game = Game.start(seed)

    @property
    def _table(self):
        """今のゲームの Table。次のゲームで Game が替わるため、Game から取り出す。"""
        return self._game.table

    @property
    def _winner(self):
        """勝者の段の位置（0 始まり）。未決は None。Game の勝者をそのまま使う。"""
        return self._game.winner

    @property
    def _result(self):
        """勝敗。None（未決）/ "win" / "lose"。Game の勝者が人間なら win、それ以外は lose。"""
        if self._game.winner is None:
            return None
        return "win" if self._game.winner == self._game.human_index else "lose"

    def update(self):
        if not self._input.is_click():
            return
        if self._game.session_result() is not None:
            # セッションの終了中は、どこをクリックしても新しいセッションを始めるだけ（ほかの操作は受けない）
            self._start_new_session()
            return
        if self._game.phase == Phase.FINISHED:
            # 終了後は画面のどこをクリックしても次のゲームへ進む（その 1 回で新しいゲームは操作しない）
            self._start_next_game()
            return
        x, y = self._input.get_mouse_x(), self._input.get_mouse_y()
        button = hit_button(x, y)
        if button is not None:
            self._press(button)
            return
        index = hit_card(self._table, x, y)
        if index is not None:
            self._table.players[self._game.human_index].toggle_selected(index)

    def _start_next_game(self):
        """人たちとポットを引き継いだ次のゲームに切り替える。種は 1 つ進める（None は None のまま）。"""
        if self._seed is not None:
            self._seed += 1
        self._game = self._game.next_game(self._seed)

    def _start_new_session(self):
        """人もポットも引き継がない新しいセッションに切り替える。種は 1 つ進める（None は None のまま）。"""
        if self._seed is not None:
            self._seed += 1
        self._game = Game.new_session(self._seed)

    def _press(self, button):
        """ボタンの操作を Game の判断に反映する。終了後は何もしない（decide は ValueError になる）。"""
        if button == "raise":
            if self._game.phase == Phase.FIRST_DECISION:
                self._table.exchange()
            if self._game.human_decides():
                self._game.decide(Action.RAISE)
        elif button == "drop" and self._game.human_decides():
            self._game.decide(Action.DROP)

    def draw(self):
        draw_table(self._view, self._table, self._game.dropped)
        result = self._result
        if result is None:
            # 帯のポップアップが出ていない間だけ、ポットの額を帯に描く
            draw_pot(self._view, self._game.pot.amount)
        draw_winner_frame(self._view, self._winner)
        draw_result_popup(
            self._view, result, self._game.awarded if result == "win" else None
        )
        # セッション終了のポップアップは最後に重ねる（なければ何も描かない）
        draw_session_popup(self._view, self._game.session_result())


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="pyxel poker")
        pyxel.load("icon.pyxres")
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self._core.update()

    def draw(self):
        # 画面の消去は draw_table が行う
        self._core.draw()


if __name__ == "__main__":
    App()
