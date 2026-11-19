# title: pyxel combo abilities
# author: masatobu

import copy
import random
from abc import ABC, abstractmethod
from collections import namedtuple

try:
    from . import drawing, screen  # pylint: disable=C0413
    from .animation import AttackAnimation, EXPLODE, LAUNCH  # pylint: disable=C0413
    from .game import ComboAbilitiesGame  # pylint: disable=C0413
    from .operation import (
        BUTTON,
        Operation,
        hit_test,
        in_new_game,
    )  # pylint: disable=C0413
    from .resource import Component  # pylint: disable=C0413
except ImportError:
    import drawing  # pylint: disable=C0413
    import screen  # pylint: disable=C0413
    from animation import AttackAnimation, EXPLODE, LAUNCH  # pylint: disable=C0413
    from game import ComboAbilitiesGame  # pylint: disable=C0413
    from operation import (
        BUTTON,
        Operation,
        hit_test,
        in_new_game,
    )  # pylint: disable=C0413
    from resource import Component  # pylint: disable=C0413

# 攻撃の再生中に表示しておく、攻撃前のテーブルの値（ゲームの状態は攻撃の開始時に先に進む）
Shown = namedtuple("Shown", ["garage", "turn"])


class IView(ABC):
    @abstractmethod
    def fill_rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def fill_circ(self, x, y, r, color):
        pass

    @abstractmethod
    def draw_line(self, x1, y1, x2, y2, color):
        pass

    @abstractmethod
    def fill_tri(self, x1, y1, x2, y2, x3, y3, color):
        pass

    @abstractmethod
    def draw_text(self, x, y, text, color=7):
        pass

    @abstractmethod
    def set_alpha(self, alpha):
        pass

    @abstractmethod
    def blt(self, x, y, u, v, w, h, colkey):
        """画像バンク 0 の (u, v) から w × h を (x, y) に描く。colkey の色は透過する。"""

    @abstractmethod
    def pal(self, src=None, dst=None):
        """描画色 src を dst に置き換える。引数なしでは、すべての置き換えを戻す。"""

    @abstractmethod
    def mouse_click(self):
        """左クリックが押されたフレームでは (x, y)、それ以外は None。"""

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def fill_rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def fill_circ(self, x, y, r, color):
        self.pyxel.circ(x, y, r, color)

    def draw_line(self, x1, y1, x2, y2, color):
        self.pyxel.line(x1, y1, x2, y2, color)

    def fill_tri(self, x1, y1, x2, y2, x3, y3, color):
        self.pyxel.tri(x1, y1, x2, y2, x3, y3, color)

    def draw_text(self, x, y, text, color=7):
        self.pyxel.text(x, y, text, color)

    def set_alpha(self, alpha):
        self.pyxel.dither(alpha)

    def blt(self, x, y, u, v, w, h, colkey):
        self.pyxel.blt(x, y, 0, u, v, w, h, colkey)

    def pal(self, src=None, dst=None):
        if src is None:
            self.pyxel.pal()
        else:
            self.pyxel.pal(src, dst)

    def mouse_click(self):
        if self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT):
            return self.pyxel.mouse_x, self.pyxel.mouse_y
        return None


class GameCore:
    def __init__(self, rand=random.random):
        self._view = PyxelView.create()
        self._rand = rand
        self.game = ComboAbilitiesGame(rand=rand)
        self.enemy_positions = drawing.enemy_positions(rand)
        self.operation = Operation(self.game)
        self.animation = None
        self._shown = None

    @property
    def attacking(self):
        """攻撃のアニメーション中か。"""
        return self.animation is not None

    @property
    def game_over(self):
        """ターン数が最大で、最後の攻撃の再生も終わったか（メニューを出す状態）。"""
        return self.game.is_end() and not self.attacking

    def update(self):
        if self.attacking:
            self._tick_animation()
            return
        click = self._view.mouse_click()
        if click is None:
            return
        if self.game_over:
            if in_new_game(*click):
                self.new_game()
            return
        target = hit_test(self.game.garage, *click)
        shown = self._snapshot() if target == BUTTON else None
        steps = self.operation.click(target)
        if steps:
            self._start_animation(steps, shown)

    def new_game(self):
        """すべての状態（ゲーム・選択・敵の位置・再生）を初期化して、最初から始める。"""
        self.game.new_game()
        self.enemy_positions = drawing.enemy_positions(self._rand)
        self.operation.selected = None
        self.animation = None
        self._shown = None

    def _snapshot(self):
        """攻撃の前の、テーブルの表示用の値を保持する。"""
        game = self.game
        return Shown(copy.deepcopy(game.garage), game.turn)

    def _start_animation(self, steps, shown):
        """攻撃の列の再生を始める。見た目のレベルは、そのターンの開始時のもの。

        テーブルは、再生が終わるまで、攻撃前の値（shown）のままにする。
        """
        self._shown = shown
        start_level = self.game.level - sum(s.leveled_up for s in steps)
        self.animation = AttackAnimation(
            steps, start_level, self.enemy_positions, self._rand
        )
        self._finish_if_done()

    def _tick_animation(self):
        self.animation.tick()
        self._finish_if_done()

    def _finish_if_done(self):
        """再生し終えたら、残った敵の位置を引き継いで、操作を受け付ける状態に戻る。"""
        if self.animation.done:
            # ゲームオーバーでなければ、敵を最大数、置き直す（移植元はターンの終わりに置き直す）
            if self.game.is_end():
                self.enemy_positions = self.animation.positions
            else:
                self.enemy_positions = drawing.enemy_positions(self._rand)
            self.animation = None
            self._shown = None
            self.operation.selected = None

    def draw(self):
        game = self.game
        anim = self.animation
        shown = self._shown or Shown(game.garage, game.turn)
        drawing.draw_field(
            self._view,
            anim.level if anim else game.level,
            shown.garage.get_lv(Component.BODY),
            anim.positions if anim else self.enemy_positions,
        )
        if anim and anim.phase == LAUNCH:
            drawing.draw_laser(self._view)
        elif anim and anim.phase == EXPLODE:
            drawing.draw_explosion(self._view, anim.exploding)
        # テーブルの背景は爆発の上に重ね、爆発がフィールドの外にはみ出さないようにする
        self._view.fill_rect(
            0, screen.TABLE_Y, screen.SCREEN_W, screen.TABLE_H, screen.TABLE_COLOR
        )
        drawing.draw_table(self._view, shown.garage, shown.turn, game.MAX_TURN)
        drawing.draw_selector(self._view, self.operation.selected)
        if self.game_over:
            drawing.draw_game_over_menu(self._view, game.kills)


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(screen.SCREEN_W, screen.SCREEN_H, title="pyxel combo abilities")
        pyxel.load(screen.RESOURCE_FILE)  # 画像リソースは init の後に読み込む
        pyxel.mouse(True)
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(0)
        self._core.draw()


if __name__ == "__main__":
    App()
