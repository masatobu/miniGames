# title: pyxel break blocks
# author: masatobu

import math
from abc import ABC, abstractmethod


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_line(self, x1, y1, x2, y2, col):
        pass

    @abstractmethod
    def draw_circ(self, x, y, r, col):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_rect(self, x, y, w, h, col):
        self.pyxel.rect(x, y, w, h, col)

    def draw_line(self, x1, y1, x2, y2, col):
        self.pyxel.line(x1, y1, x2, y2, col)

    def draw_circ(self, x, y, r, col):
        self.pyxel.circ(x, y, r, col)


class IInput(ABC):
    @abstractmethod
    def is_btn_pressed(self) -> bool:
        pass

    @abstractmethod
    def is_btn_down(self) -> bool:
        pass

    @abstractmethod
    def is_btn_released(self) -> bool:
        pass

    @property
    @abstractmethod
    def mouse_x(self) -> int:
        pass

    @property
    @abstractmethod
    def mouse_y(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def is_btn_down(self) -> bool:
        return self.pyxel.btn(self.pyxel.MOUSE_BUTTON_LEFT)

    def is_btn_released(self) -> bool:
        return self.pyxel.btnr(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class Block:
    W = 13
    H = 7

    def __init__(self, x, y):
        self._x = x
        self._y = y

    def rect(self):
        return self._x, self._y, self.W, self.H

    def rise(self, step: int) -> None:
        self._y -= step

    def is_above(self, border_y: int) -> bool:
        return self._y < border_y

    def draw(self, view):
        view.draw_rect(self._x, self._y, self.W, self.H, 8)


class Ball:
    R = 3

    def __init__(self, x, y, vx, vy):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy

    def move(self):
        self.x += self.vx
        self.y += self.vy

    def is_hit(self, rect_x, rect_y, rect_w, rect_h) -> bool:
        return (
            self.x + self.R > rect_x
            and self.x - self.R < rect_x + rect_w
            and self.y + self.R > rect_y
            and self.y - self.R < rect_y + rect_h
        )

    def reflect(self, rect_x, rect_y, rect_w, rect_h) -> None:
        if not self.is_hit(rect_x, rect_y, rect_w, rect_h):
            return
        pen_right = (rect_x + rect_w) - (self.x - self.R)
        pen_left = (self.x + self.R) - rect_x
        pen_bottom = (rect_y + rect_h) - (self.y - self.R)
        pen_top = (self.y + self.R) - rect_y
        min_pen = min(pen_right, pen_left, pen_bottom, pen_top)
        if min_pen == pen_right:
            self.vx = abs(self.vx)
            self.x = 2 * (rect_x + rect_w + self.R) - self.x
        elif min_pen == pen_left:
            self.vx = -abs(self.vx)
            self.x = 2 * (rect_x - self.R) - self.x
        elif min_pen == pen_bottom:
            self.vy = abs(self.vy)
            self.y = 2 * (rect_y + rect_h + self.R) - self.y
        else:
            self.vy = -abs(self.vy)
            self.y = 2 * (rect_y - self.R) - self.y

    def is_below(self, bottom_y) -> bool:
        return self.y + self.R >= bottom_y

    def draw(self, view):
        view.draw_circ(round(self.x), round(self.y), self.R, 7)


class GameCore:
    SCREEN_WIDTH = 150
    SCREEN_HEIGHT = 200
    WALL_WIDTH = 2
    BORDER_Y = 20  # ゲームオーバー判定ライン（上方）
    BLOCK_COLS = 5
    BLOCK_ROWS = 4
    BLOCK_MARGIN_X = 2
    BLOCK_MARGIN_Y = 2
    BLOCK_START_X = (
        SCREEN_WIDTH - BLOCK_COLS * Block.W - (BLOCK_COLS - 1) * BLOCK_MARGIN_X
    ) // 2  # 左右中央揃え
    BLOCK_START_Y = 110  # 下方配置（ターンごとに上昇する）
    BALL_START_X = SCREEN_WIDTH // 2
    BALL_START_Y = BORDER_Y // 2
    ARROW_LENGTH = 20
    BALL_SPEED = 3.0
    POPUP_X = 25
    POPUP_Y = 85
    POPUP_W = 100
    POPUP_H = 30

    @staticmethod
    def _make_dir(dx, dy):
        d = math.sqrt(dx**2 + dy**2)
        return (dx / d, dy / d)

    LEFT_CORNER_DIR = _make_dir(WALL_WIDTH - BALL_START_X, BORDER_Y - BALL_START_Y)
    RIGHT_CORNER_DIR = _make_dir(
        SCREEN_WIDTH - WALL_WIDTH - BALL_START_X, BORDER_Y - BALL_START_Y
    )

    def __init__(self):
        self._view = PyxelView.create()
        self._input = PyxelInput.create()
        self._direction = None
        self._ball = None
        self._game_clear = False
        self._game_over = False
        self._needs_reset = False
        self._blocks = [
            Block(
                x=self.BLOCK_START_X + col * (Block.W + self.BLOCK_MARGIN_X),
                y=self.BLOCK_START_Y + row * (Block.H + self.BLOCK_MARGIN_Y),
            )
            for row in range(self.BLOCK_ROWS)
            for col in range(self.BLOCK_COLS)
        ]

    def _calc_direction(self, mouse_x, mouse_y):
        dx = mouse_x - self.BALL_START_X
        dy = mouse_y - self.BALL_START_Y

        if dy <= 0:
            return (
                self.LEFT_CORNER_DIR
                if mouse_x < self.BALL_START_X
                else self.RIGHT_CORNER_DIR
            )

        x_cross = self.BALL_START_X + dx / dy * (self.BORDER_Y - self.BALL_START_Y)
        if x_cross < self.WALL_WIDTH:
            return self.LEFT_CORNER_DIR
        if x_cross > self.SCREEN_WIDTH - self.WALL_WIDTH:
            return self.RIGHT_CORNER_DIR

        return self._make_dir(dx, dy)

    @property
    def needs_reset(self):
        return self._needs_reset

    def _is_popup_clicked(self) -> bool:
        return (
            self._input.is_btn_released()
            and self.POPUP_X <= self._input.mouse_x < self.POPUP_X + self.POPUP_W
            and self.POPUP_Y <= self._input.mouse_y < self.POPUP_Y + self.POPUP_H
        )

    def update(self):
        if self._game_clear or self._game_over:
            if self._is_popup_clicked():
                self._needs_reset = True
            return
        if self._ball is None:
            self._update_aiming()
        else:
            self._update_flying()

    def _update_flying(self):
        self._ball.move()
        self._reflect_ball()
        self._handle_block_collisions()
        if not self._blocks:
            self._game_clear = True
            return
        if self._ball.is_below(self.SCREEN_HEIGHT):
            self._advance_turn()

    def _advance_turn(self):
        step = Block.H + self.BLOCK_MARGIN_Y
        for block in self._blocks:
            block.rise(step)
            if block.is_above(self.BORDER_Y):
                self._game_over = True
        self._ball = None

    def _update_aiming(self):
        if self._input.is_btn_released() and self._direction is not None:
            self._ball = Ball(
                float(self.BALL_START_X),
                float(self.BALL_START_Y),
                self._direction[0] * self.BALL_SPEED,
                self._direction[1] * self.BALL_SPEED,
            )
            self._direction = None
        elif self._input.is_btn_down():
            self._direction = self._calc_direction(
                self._input.mouse_x, self._input.mouse_y
            )

    def _reflect_ball(self):
        self._ball.reflect(0, 0, self.WALL_WIDTH, self.SCREEN_HEIGHT)
        self._ball.reflect(
            self.SCREEN_WIDTH - self.WALL_WIDTH, 0, self.WALL_WIDTH, self.SCREEN_HEIGHT
        )
        self._ball.reflect(0, 0, self.SCREEN_WIDTH, self.WALL_WIDTH)

    def _handle_block_collisions(self):
        remaining = []
        for b in self._blocks:
            if self._ball.is_hit(*b.rect()):
                self._ball.reflect(*b.rect())
            else:
                remaining.append(b)
        self._blocks = remaining

    def _draw_frame(self):
        self._view.draw_rect(0, 0, self.SCREEN_WIDTH, self.WALL_WIDTH, 7)
        self._view.draw_rect(0, 0, self.WALL_WIDTH, self.SCREEN_HEIGHT, 7)
        self._view.draw_rect(
            self.SCREEN_WIDTH - self.WALL_WIDTH,
            0,
            self.WALL_WIDTH,
            self.SCREEN_HEIGHT,
            7,
        )
        self._view.draw_line(0, self.BORDER_Y, self.SCREEN_WIDTH - 1, self.BORDER_Y, 2)

    def _draw_arrow(self):
        dx, dy = self._direction
        self._view.draw_line(
            self.BALL_START_X,
            self.BALL_START_Y,
            round(self.BALL_START_X + dx * self.ARROW_LENGTH),
            round(self.BALL_START_Y + dy * self.ARROW_LENGTH),
            7,
        )

    def _draw_launch_ball(self):
        self._view.draw_circ(self.BALL_START_X, self.BALL_START_Y, Ball.R, 7)

    def _draw_popup(self, line1):
        self._view.draw_rect(
            self.POPUP_X,
            self.POPUP_Y,
            self.POPUP_W,
            self.POPUP_H,
            1,
        )
        # Pyxel デフォルトフォント: 3px幅 + 1px余白 = 4px/文字スロット、高さ 5px
        # 2行テキストブロック: 5px + 4px gap + 5px = 14px
        center_x = self.POPUP_X + self.POPUP_W // 2
        center_y = self.POPUP_Y + self.POPUP_H // 2
        line1_y = center_y - 14 // 2
        line2_y = line1_y + 5 + 4
        self._view.draw_text(center_x - len(line1) * 4 // 2, line1_y, line1)
        self._view.draw_text(
            center_x - len("Click to restart") * 4 // 2, line2_y, "Click to restart"
        )

    def draw(self):
        self._draw_frame()
        for block in self._blocks:
            block.draw(self._view)
        if self._direction is not None:
            self._draw_arrow()
        if self._ball is not None:
            self._ball.draw(self._view)
        elif not self._game_over:
            self._draw_launch_ball()
        if self._game_clear:
            self._draw_popup("CLEAR")
        if self._game_over:
            self._draw_popup("GAME OVER")


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(
            GameCore.SCREEN_WIDTH, GameCore.SCREEN_HEIGHT, title="pyxel break blocks"
        )
        pyxel.mouse(True)
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        if self._core.needs_reset:
            self._core = GameCore()
        else:
            self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(0)
        self._core.draw()


if __name__ == "__main__":
    App()
