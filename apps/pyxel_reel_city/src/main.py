# title: pyxel template
# author: masatobu

from abc import ABC, abstractmethod
from report_store import ReportStore
from city import City
from reel import Reel, ReelSymbol


class BetMultiplier:
    STAGES = (10, 100, 1000, 10000)
    GROWTH_STAGES = (1, 8, 64, 512)

    def __init__(self):
        self._index = 0

    @property
    def current(self):
        return self.STAGES[self._index]

    @property
    def growth_multiplier(self):
        return self.GROWTH_STAGES[self._index]

    def next(self):
        self._index = (self._index + 1) % len(self.STAGES)


class IInput(ABC):
    @abstractmethod
    def is_mouse_btn_pressed(self) -> bool: ...

    @property
    @abstractmethod
    def mouse_x(self) -> int: ...

    @property
    @abstractmethod
    def mouse_y(self) -> int: ...

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_mouse_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, col=7):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_circ(self, x, y, r, col):
        pass

    @abstractmethod
    def draw_circb(self, x, y, r, col):
        pass

    @abstractmethod
    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, col=7):
        self.pyxel.text(x, y, text, col)

    def draw_rect(self, x, y, w, h, col):
        self.pyxel.rect(x, y, w, h, col)

    def draw_rectb(self, x, y, w, h, col):
        self.pyxel.rectb(x, y, w, h, col)

    def draw_circ(self, x, y, r, col):
        self.pyxel.circ(x, y, r, col)

    def draw_circb(self, x, y, r, col):
        self.pyxel.circb(x, y, r, col)

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)


class IGridView(ABC):
    @abstractmethod
    def draw(self, col, row, level, variant):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelGridView(IGridView):
    GRID_W = 16
    GRID_H = 15
    IMAGE_U_OFFSET = 8
    VERTICAL_OFFSET = 7  # 三角形の重なり幅（px）

    def __init__(self):
        self.view = self._create_view()

    def _create_view(self):
        return PyxelView.create()

    def draw(self, col, row, level, variant):
        px = col * self.GRID_W
        py = (self.GRID_H - self.VERTICAL_OFFSET) * row
        # 画像座標: u = IMAGE_U_OFFSET + variant * GRID_W（スプライト横並び）
        #           v = level * GRID_W（レベル縦並び、スプライト間隔は16px）
        u = self.IMAGE_U_OFFSET + variant * self.GRID_W
        v = level * self.GRID_W
        # (col+row) が奇数のとき w を負にして水平反転
        w = -self.GRID_W if (col + row) % 2 != 0 else self.GRID_W
        self.view.draw_blt(px, py, 0, u, v, w, self.GRID_H, 0)


class GameCore:

    REEL_CENTER_X = 198
    REEL_CENTER_Y = 269
    REEL_RADIUS = 18
    BET_CENTER_X = 26
    BET_CENTER_Y = 269
    BET_RADIUS = 18
    CHAR_W = 4
    CHAR_H = 5
    SCREEN_W = 224
    SCREEN_H = 295
    FUNDS_Y = 2
    FUNDS_MARGIN = 2
    FUNDS_PAD_X = 3
    FUNDS_PAD_Y = 3
    FUNDS_FRAME_DIGITS = 8
    FUNDS_FRAME_COL = 1
    FUNDS_FRAME_BORDER_COL = 5
    FUNDS_TEXT_COL = 6
    COL_FRAME_ACTIVE = 7  # 操作可能な枠の色（白）
    COL_FRAME_INACTIVE = 5  # 操作不可な枠の色（グレー）
    RESULT_BG_COLORS = {  # 出目シンボルに対応するリール背景色
        ReelSymbol.ZERO: 0,
        ReelSymbol.ONE: 1,
        ReelSymbol.TWO: 3,
        ReelSymbol.THREE: 2,
    }
    POPULATION_X = 2
    POPULATION_Y = 2
    POPUP_W = 120
    POPUP_H = 48
    POPUP_X = (SCREEN_W - POPUP_W) // 2
    POPUP_Y = (SCREEN_H - POPUP_H) // 2
    POPUP_MSG = "Game Over. Reset?"
    POPUP_MSG_X = POPUP_X + (POPUP_W - len(POPUP_MSG) * CHAR_W) // 2
    POPUP_BTN_R = 8  # 円形ボタンの半径
    POPUP_YES_CX = POPUP_X + 24  # YES ボタン円中心 X
    POPUP_YES_CY = POPUP_Y + 33  # YES ボタン円中心 Y
    POPUP_NO_CX = POPUP_X + 96  # NO ボタン円中心 X
    POPUP_NO_CY = POPUP_Y + 33  # NO ボタン円中心 Y
    STREAK_MARK_W = 6
    STREAK_MARK_H = 6
    STREAK_MARK_GAP = 2  # 2マーク表示時のマーク間隔（px）
    STREAK_MARK_Y = REEL_CENTER_Y + REEL_RADIUS + 1  # リール底辺 + 余白
    STREAK_MARK1_X = REEL_CENTER_X - STREAK_MARK_W // 2  # 1個: リール中央揃え
    STREAK_MARK2_X0 = REEL_CENTER_X - STREAK_MARK_W - STREAK_MARK_GAP // 2  # 2個: 左側
    STREAK_MARK2_X1 = REEL_CENTER_X + STREAK_MARK_GAP // 2  # 2個: 右側
    STREAK_GRAY_V = 8  # images.pyxres レイヤー0 灰色マーク v 座標
    STREAK_YELLOW_V = 16  # images.pyxres レイヤー0 黄色マーク v 座標

    def __init__(self, load_data=True):
        self._view = PyxelView.create()
        self._grid_view = PyxelGridView.create()
        self._input = PyxelInput.create()
        self._reel = Reel()
        self._bet_multiplier = BetMultiplier()
        self._report_store = ReportStore()
        self._auto_save_counter = 0
        self._popup_shown = False
        self._needs_reset = False
        self._apply_load_data(self._report_store.load() if load_data else None)
        self._report_store.save(self._get_save_data())

    def _get_save_data(self):
        return {
            "city": self._city.to_dict(),
            "reel_streak": self._reel.to_dict(),
        }

    @property
    def needs_reset(self):
        return self._needs_reset

    def _apply_load_data(self, data):
        if data is None:
            self._city = City()
            return
        self._city = City.from_dict(data["city"])
        self._reel = Reel.from_dict(data["reel_streak"])

    def _is_in_circle(self, mx, my, cx, cy, r):
        dx = mx - cx
        dy = my - cy
        return dx * dx + dy * dy <= r * r

    def _save(self):
        self._report_store.save(self._get_save_data())

    def _can_spin(self):
        return (
            not self._reel.is_spinning
            and self._city.funds >= self._bet_multiplier.current
        )

    def update(self):
        if self._input.is_mouse_btn_pressed():
            mx, my = self._input.mouse_x, self._input.mouse_y
            if self._popup_shown:
                if self._is_in_circle(
                    mx, my, self.POPUP_YES_CX, self.POPUP_YES_CY, self.POPUP_BTN_R
                ):
                    self._needs_reset = True
                elif self._is_in_circle(
                    mx, my, self.POPUP_NO_CX, self.POPUP_NO_CY, self.POPUP_BTN_R
                ):
                    self._popup_shown = False
            elif self._city.is_game_over and self._is_in_circle(
                mx, my, self.REEL_CENTER_X, self.REEL_CENTER_Y, self.REEL_RADIUS
            ):
                self._popup_shown = True
            else:
                if (
                    self._is_in_circle(
                        mx, my, self.REEL_CENTER_X, self.REEL_CENTER_Y, self.REEL_RADIUS
                    )
                    and self._can_spin()
                ):
                    self._city.deduct_funds(self._bet_multiplier.current)
                    self._reel.click()
                elif (
                    self._is_in_circle(
                        mx, my, self.BET_CENTER_X, self.BET_CENTER_Y, self.BET_RADIUS
                    )
                    and not self._reel.is_spinning
                ):
                    self._bet_multiplier.next()
        self._reel.update()
        if self._reel.just_stopped:
            self._city.apply_growth(
                self._reel.result * self._bet_multiplier.growth_multiplier,
                special=self._reel.streak == 3,
            )
            self._save()
        self._city.update()
        self._auto_save_counter += 1
        if self._auto_save_counter >= 600:
            self._save()
            self._auto_save_counter = 0

    def draw(self):
        for col in range(City.COLUMN_NUM):
            for row in range(City.ROW_NUM):
                level = self._city.get_grid_level(col, row)
                variant = self._city.get_grid_variant(col, row)
                self._grid_view.draw(col, row, level, variant)
        if self._city.is_game_over:
            self._draw_reset_button()
        else:
            self._draw_reel()
            self._draw_streak_mark()
        self._draw_funds()
        self._draw_population()
        self._draw_bet_button()
        if self._popup_shown:
            self._draw_popup()

    def _draw_streak_mark(self):
        streak = self._reel.streak
        if streak == 2:
            self._view.draw_blt(
                self.STREAK_MARK1_X,
                self.STREAK_MARK_Y,
                0,
                0,
                self.STREAK_GRAY_V,
                self.STREAK_MARK_W,
                self.STREAK_MARK_H,
                0,
            )
        elif streak == 3:
            self._view.draw_blt(
                self.STREAK_MARK2_X0,
                self.STREAK_MARK_Y,
                0,
                0,
                self.STREAK_YELLOW_V,
                self.STREAK_MARK_W,
                self.STREAK_MARK_H,
                0,
            )
            self._view.draw_blt(
                self.STREAK_MARK2_X1,
                self.STREAK_MARK_Y,
                0,
                0,
                self.STREAK_YELLOW_V,
                self.STREAK_MARK_W,
                self.STREAK_MARK_H,
                0,
            )

    def _draw_popup(self):
        self._view.draw_rect(self.POPUP_X, self.POPUP_Y, self.POPUP_W, self.POPUP_H, 1)
        self._view.draw_rectb(self.POPUP_X, self.POPUP_Y, self.POPUP_W, self.POPUP_H, 7)
        self._view.draw_text(self.POPUP_MSG_X, self.POPUP_Y + 8, self.POPUP_MSG)
        yes_tx = self.POPUP_YES_CX - len("YES") * self.CHAR_W // 2 + 1
        yes_ty = self.POPUP_YES_CY - self.CHAR_H // 2
        self._view.draw_circ(self.POPUP_YES_CX, self.POPUP_YES_CY, self.POPUP_BTN_R, 0)
        self._view.draw_circb(self.POPUP_YES_CX, self.POPUP_YES_CY, self.POPUP_BTN_R, 7)
        self._view.draw_text(yes_tx, yes_ty, "YES")
        no_tx = self.POPUP_NO_CX - len("NO") * self.CHAR_W // 2 + 1
        no_ty = self.POPUP_NO_CY - self.CHAR_H // 2
        self._view.draw_circ(self.POPUP_NO_CX, self.POPUP_NO_CY, self.POPUP_BTN_R, 0)
        self._view.draw_circb(self.POPUP_NO_CX, self.POPUP_NO_CY, self.POPUP_BTN_R, 7)
        self._view.draw_text(no_tx, no_ty, "NO")

    def _draw_funds(self):
        text = str(self._city.funds)
        fw = self.FUNDS_FRAME_DIGITS * self.CHAR_W + self.FUNDS_PAD_X * 2
        fh = self.CHAR_H + self.FUNDS_PAD_Y * 2
        fx = self.SCREEN_W - fw - self.FUNDS_MARGIN
        fy = self.FUNDS_Y
        tx = fx + self.FUNDS_PAD_X
        ty = fy + self.FUNDS_PAD_Y
        self._view.draw_rect(fx, fy, fw, fh, self.FUNDS_FRAME_COL)
        self._view.draw_rectb(fx, fy, fw, fh, self.FUNDS_FRAME_BORDER_COL)
        self._view.draw_text(tx, ty, text, self.FUNDS_TEXT_COL)

    def _draw_population(self):
        text = str(self._city.population)
        fw = self.FUNDS_FRAME_DIGITS * self.CHAR_W + self.FUNDS_PAD_X * 2
        fh = self.CHAR_H + self.FUNDS_PAD_Y * 2
        fx = self.POPULATION_X
        fy = self.POPULATION_Y
        tx = fx + self.FUNDS_PAD_X
        ty = fy + self.FUNDS_PAD_Y
        self._view.draw_rect(fx, fy, fw, fh, self.FUNDS_FRAME_COL)
        self._view.draw_rectb(fx, fy, fw, fh, self.FUNDS_FRAME_BORDER_COL)
        self._view.draw_text(tx, ty, text, self.FUNDS_TEXT_COL)

    def _draw_bet_button(self):
        cx, cy, r = self.BET_CENTER_X, self.BET_CENTER_Y, self.BET_RADIUS
        text = f"x{self._bet_multiplier.current}"
        tx = cx - len(text) * self.CHAR_W // 2
        ty = cy - self.CHAR_H // 2
        col = (
            self.COL_FRAME_INACTIVE if self._reel.is_spinning else self.COL_FRAME_ACTIVE
        )
        self._view.draw_circ(cx, cy, r, 0)
        self._view.draw_circb(cx, cy, r, col)
        self._view.draw_text(tx, ty, text)

    def _draw_reel(self):
        cx, cy, r = self.REEL_CENTER_X, self.REEL_CENTER_Y, self.REEL_RADIUS
        col = self.COL_FRAME_ACTIVE if self._can_spin() else self.COL_FRAME_INACTIVE
        tx = cx - self.CHAR_W // 2
        ty = cy - self.CHAR_H // 2
        bg_col = self.RESULT_BG_COLORS[self._reel.current_symbol]
        self._view.draw_circ(cx, cy, r, bg_col)
        self._view.draw_circb(cx, cy, r, col)
        self._view.draw_text(tx, ty, self._reel.display_text)

    def _draw_reset_button(self):
        cx, cy, r = self.REEL_CENTER_X, self.REEL_CENTER_Y, self.REEL_RADIUS
        label = "RESET"
        tx = cx - len(label) * self.CHAR_W // 2
        ty = cy - self.CHAR_H // 2
        self._view.draw_circ(cx, cy, r, 0)
        self._view.draw_circb(cx, cy, r, self.COL_FRAME_ACTIVE)
        self._view.draw_text(tx, ty, label)


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        # 縦: (GRID_H - VERTICAL_OFFSET) * (ROW_NUM - 1) + GRID_H = 8 * 35 + 15 = 295
        pyxel.init(GameCore.SCREEN_W, GameCore.SCREEN_H, title="pyxel template")
        pyxel.mouse(True)
        pyxel.load("images.pyxres")
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        if self._core.needs_reset:
            self._core = GameCore(load_data=False)
        else:
            self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(0)
        self._core.draw()


if __name__ == "__main__":
    App()
