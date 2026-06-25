# title: pyxel sort water
# author: masatobu

import random
from abc import ABC, abstractmethod
from enum import IntEnum

# スクリーン寸法（Pyxel 初期化サイズ）
SCREEN_W = 150
SCREEN_H = 200


class Color(IntEnum):
    BLACK = 0
    DARK_RED = 2
    DARK_GREEN = 3
    WHITE = 7
    RED = 8
    GREEN = 11
    GRAY = 13


class WaterColor(IntEnum):
    A = Color.RED
    B = Color.GREEN
    C = Color.DARK_GREEN


class Cup:
    CAPACITY = 3

    def __init__(self):
        self._layers = []

    @property
    def layers(self):
        return self._layers

    def add_layer(self, color):
        self._layers.append(color)

    def pop_layer(self):
        return self._layers.pop()

    @property
    def is_empty(self):
        return len(self.layers) == 0

    @property
    def is_full(self):
        return len(self.layers) >= self.CAPACITY

    @property
    def is_completed(self):
        return self.is_full and len(set(self.layers)) == 1


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_line(self, x1, y1, x2, y2, col):
        pass

    @abstractmethod
    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, col):
        pass

    @classmethod
    def create(cls):
        return cls()


class ISound(ABC):
    @abstractmethod
    def play_move_success(self):
        pass

    @abstractmethod
    def play_move_failure(self):
        pass

    @abstractmethod
    def play_clear(self):
        pass

    @abstractmethod
    def enable(self, enabled: bool):
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        pass

    @classmethod
    def create(cls):
        return cls()


class IInput(ABC):
    @abstractmethod
    def is_btn_pressed(self) -> bool:
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

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, Color.WHITE)

    def draw_line(self, x1, y1, x2, y2, col):
        self.pyxel.line(x1, y1, x2, y2, col)

    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        self.pyxel.tri(x1, y1, x2, y2, x3, y3, col)

    def draw_rect(self, x, y, w, h, col):
        self.pyxel.rect(x, y, w, h, col)

    def draw_rectb(self, x, y, w, h, col):
        self.pyxel.rectb(x, y, w, h, col)


class PyxelSound(ISound):
    MML_MOVE_SUCCESS = "t190 @0 o4 l32 c d e d"
    MML_MOVE_FAILURE = "t220 @0 o4 l32 g e"
    MML_CLEAR = "t160 @0 o4 l16 c e g >c"
    
    SLOT_MOVE_SUCCESS = 0
    SLOT_MOVE_FAILURE = 1
    SLOT_CLEAR = 2
    CHANNEL = 0

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel
        self._enabled = True
        pyxel.sounds[self.SLOT_MOVE_SUCCESS].mml(self.MML_MOVE_SUCCESS)
        pyxel.sounds[self.SLOT_MOVE_FAILURE].mml(self.MML_MOVE_FAILURE)
        pyxel.sounds[self.SLOT_CLEAR].mml(self.MML_CLEAR)

    def enable(self, enabled: bool):
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def play_move_success(self):
        if self._enabled:
            self.pyxel.play(self.CHANNEL, self.SLOT_MOVE_SUCCESS)

    def play_move_failure(self):
        if self._enabled:
            self.pyxel.play(self.CHANNEL, self.SLOT_MOVE_FAILURE)

    def play_clear(self):
        if self._enabled:
            self.pyxel.play(self.CHANNEL, self.SLOT_CLEAR)


class ICupView(ABC):
    @abstractmethod
    def draw(
        self,
        layers,
        col,
        row,
        selected,
        anim_shrink_top=1.0,
        anim_extra_color=None,
        anim_extra_scale=0.0,
    ):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelCupView(ICupView):
    CUP_W = 30
    CUP_H = 40
    MARGIN_X = 6
    MARGIN_Y = 16  # サウンドボタン（上端 y=2〜14）と重ならないよう下げる
    LAYER_H = 12
    COL_STEP = CUP_W + 6  # 列間ステップ (px)
    ROW_STEP = CUP_H + 4  # 行間ステップ (px)。上部余白確保のため縦に少し詰める
    SEL_PAD = 2  # 選択背景のコップ外側へのパディング (px)

    def __init__(self):
        self.view = self._create_view()

    def _create_view(self):
        return PyxelView.create()

    @staticmethod
    def _layer_y(cup_y, i):
        """コップ上端 Y 座標と層インデックスから水層の描画 Y 座標を返す（layer 0 が最下層）"""
        return cup_y + PyxelCupView.CUP_H - 1 - PyxelCupView.LAYER_H * (i + 1)

    @classmethod
    def pixel_to_cup_pos(cls, x, y):
        rel_x = x - cls.MARGIN_X
        rel_y = y - cls.MARGIN_Y
        if rel_x < 0 or rel_y < 0:
            return None
        col = rel_x // cls.COL_STEP
        row = rel_y // cls.ROW_STEP
        if col >= Board.COLS or row >= Board.ROWS:
            return None
        if rel_x % cls.COL_STEP >= cls.CUP_W:
            return None
        if rel_y % cls.ROW_STEP >= cls.CUP_H:
            return None
        return (int(col), int(row))

    def draw(
        self,
        layers,
        col,
        row,
        selected,
        anim_shrink_top=1.0,
        anim_extra_color=None,
        anim_extra_scale=0.0,
    ):
        x = self.MARGIN_X + col * self.COL_STEP
        y = self.MARGIN_Y + row * self.ROW_STEP
        bx = x + self.CUP_W - 1
        by = y + self.CUP_H - 1
        if selected:
            self.view.draw_rect(
                x - self.SEL_PAD,
                y - self.SEL_PAD,
                self.CUP_W + 2 * self.SEL_PAD,
                self.CUP_H + 2 * self.SEL_PAD,
                Color.DARK_RED,
            )
        self.view.draw_line(x, y, x, by, Color.WHITE)  # 左辺
        self.view.draw_line(bx, y, bx, by, Color.WHITE)  # 右辺
        self.view.draw_line(x, by, bx, by, Color.WHITE)  # 底辺
        for i, color in enumerate(layers):
            scale = anim_shrink_top if i == len(layers) - 1 else 1.0
            h = round(self.LAYER_H * scale)
            if h <= 0:
                continue
            layer_y = self._layer_y(y, i)
            self.view.draw_rect(
                x + 1, layer_y + (self.LAYER_H - h), self.CUP_W - 2, h, color
            )
        if anim_extra_color is not None:
            h = round(self.LAYER_H * anim_extra_scale)
            if h > 0:
                layer_y = self._layer_y(y, len(layers))
                self.view.draw_rect(
                    x + 1,
                    layer_y + (self.LAYER_H - h),
                    self.CUP_W - 2,
                    h,
                    anim_extra_color,
                )


class Board:
    COLS = 4
    ROWS = 4
    COLORS = [WaterColor.A, WaterColor.B, WaterColor.C]

    def __init__(self):
        self._grid = [[Cup() for _ in range(self.COLS)] for _ in range(self.ROWS)]
        self._selected = None
        self._is_clear = False
        self._generate()

    @property
    def selected(self):
        return self._selected

    @property
    def is_clear(self):
        return self._is_clear

    def _update_is_clear(self):
        for row in range(self.ROWS):
            for col in range(self.COLS):
                cup = self.get_cup(col, row)
                if not cup.is_empty and not cup.is_completed:
                    self._is_clear = False
                    return
        self._is_clear = True

    def select(self, col, row):
        # 移動は GameCore がアニメーション経由で move_to() を呼ぶため、
        # select() は第1クリックの選択と、選択中クリックでの選択解除のみを担う
        if self._selected is not None:
            self._selected = None
        else:
            cup = self.get_cup(col, row)
            if not cup.is_empty and not cup.is_completed:
                self._selected = (col, row)

    def can_move_from_selected(self, dst_col, dst_row) -> bool:
        if self._selected is None:
            return False
        if (dst_col, dst_row) == self._selected:
            return False
        return not self.get_cup(dst_col, dst_row).is_full

    def move_to(self, dst_col, dst_row):
        src_cup = self.get_cup(*self._selected)
        dst_cup = self.get_cup(dst_col, dst_row)
        dst_cup.add_layer(src_cup.pop_layer())
        self._selected = None
        self._update_is_clear()

    def _generate(self):
        # 各コップに A・B・C を 1 層ずつランダムな順で配置し、コップ自体の順序もシャッフル
        cups_data = [
            random.sample(list(self.COLORS), len(self.COLORS)) for _ in range(15)
        ]
        empty_pos = random.randint(0, self.COLS * self.ROWS - 1)
        idx = 0
        for row in range(self.ROWS):
            for col in range(self.COLS):
                if row * self.COLS + col == empty_pos:
                    continue
                cup = self._grid[row][col]
                for color in cups_data[idx]:
                    cup.add_layer(color)
                idx += 1

    def get_cup(self, col, row):
        return self._grid[row][col]


class GameCore:
    # クリアポップアップ定数（150×200 スクリーン）
    CLEAR_POPUP_X = 25
    CLEAR_POPUP_Y = 85
    CLEAR_POPUP_W = 100
    CLEAR_POPUP_H = 30
    CLEAR_POPUP_BG_COLOR = 1  # ダークブルー

    # Pyxel デフォルトフォントの寸法と行レイアウト
    CHAR_W = 4  # 1 文字幅（グリフ 3px + 余白 1px）
    CHAR_H = 5  # 文字高
    LINE_GAP = 4  # 行間の余白
    CLEAR_TEXT = "CLEAR"
    RESTART_TEXT = "CLICK TO RESTART"

    # 水移動アニメーションの総フレーム数
    ANIM_DURATION_FRAMES = 10

    # サウンドボタン定数（スクリーン右上）
    BTN_SOUND_W = 8
    BTN_SOUND_H = 6
    BTN_SOUND_Y = 2  # 画面上端からの余白
    BTN_SOUND_MARGIN = 2  # 画面右端からの余白
    BTN_SOUND_X = SCREEN_W - BTN_SOUND_W - BTN_SOUND_MARGIN  # 右端から内側へ = 140
    SOUND_ICON_COLOR = Color.GRAY
    SOUND_TRI_OFFSET_X = 1  # 三角形を音波から離すための左方向のずらし幅 (px)

    # 音波（縦線）の描画パラメータ
    SOUND_WAVE_COUNT = 2  # 音波の本数
    SOUND_WAVE_GAP = 1  # 三角形右辺から最初の音波までの間隔 (px)
    SOUND_WAVE_STEP = 2  # 音波どうしの間隔 (px)
    SOUND_WAVE_INSET = 1  # 三角形上下端から音波の上下端までの余白 (px)

    def __init__(self, sound: ISound):
        self._cup_view = PyxelCupView.create()
        self._input = PyxelInput.create()
        self._view = PyxelView.create()
        self._sound = sound
        self._board = Board()
        self._needs_reset = False
        self._anim_dst_pos = None
        self._anim_color = None
        self._anim_frame = 0

    def _calc_anim_progress(self):
        """整数フレームカウンタから算出する進捗（0.0〜1.0）。浮動小数を累積しないため完了判定が堅牢"""
        return self._anim_frame / self.ANIM_DURATION_FRAMES

    def _is_animating(self):
        return self._anim_dst_pos is not None

    @property
    def needs_reset(self):
        return self._needs_reset

    def _is_popup_clicked(self):
        """クリックがクリアポップアップ矩形内かを返す"""
        return (
            self._input.is_btn_pressed()
            and self.CLEAR_POPUP_X
            <= self._input.mouse_x
            < self.CLEAR_POPUP_X + self.CLEAR_POPUP_W
            and self.CLEAR_POPUP_Y
            <= self._input.mouse_y
            < self.CLEAR_POPUP_Y + self.CLEAR_POPUP_H
        )

    def _is_sound_button_clicked(self):
        """クリックがサウンドボタン矩形内かを返す"""
        return (
            self._input.is_btn_pressed()
            and self.BTN_SOUND_X
            <= self._input.mouse_x
            < self.BTN_SOUND_X + self.BTN_SOUND_W
            and self.BTN_SOUND_Y
            <= self._input.mouse_y
            < self.BTN_SOUND_Y + self.BTN_SOUND_H
        )

    def update(self):
        if self._board.is_clear:
            if self._is_popup_clicked():
                self._needs_reset = True
            return
        if self._is_animating():
            self._advance_animation()
            return  # アニメーション中は入力処理しない
        self._handle_input()

    def _start_animation(self, dst_pos):
        """移動確定時に呼ぶ。Board はまだ動かさず、アニメーション状態を開始する（遅延モデル更新）"""
        self._anim_dst_pos = dst_pos
        self._anim_color = self._board.get_cup(*self._board.selected).layers[-1]
        self._anim_frame = 0
        self._sound.play_move_success()

    def _advance_animation(self):
        """フレームを進め、所定フレーム数に達したら移動を確定する"""
        self._anim_frame += 1
        if self._anim_frame >= self.ANIM_DURATION_FRAMES:
            self._finish_animation()

    def _finish_animation(self):
        """遅延していた水移動と選択解除を確定し、アニメーション状態を解除する"""
        self._board.move_to(*self._anim_dst_pos)
        self._anim_dst_pos = None
        self._anim_color = None
        self._anim_frame = 0
        if self._board.is_clear:
            self._sound.play_clear()

    def _handle_input(self):
        """クリック入力を処理する。サウンドボタンのトグル、カップ選択・移動を担う"""
        if not self._input.is_btn_pressed():
            return
        if self._is_sound_button_clicked():
            self._sound.enable(not self._sound.enabled)
            return
        pos = PyxelCupView.pixel_to_cup_pos(self._input.mouse_x, self._input.mouse_y)
        if pos is None:
            return
        if self._board.can_move_from_selected(*pos):
            self._start_animation(pos)
        else:
            if (
                self._board.selected is not None
                and pos != self._board.selected
                and self._board.get_cup(*pos).is_full
            ):
                self._sound.play_move_failure()
            self._board.select(*pos)

    def draw(self):
        self._draw_board()
        self._draw_sound_button()
        if self._board.is_clear:
            self._draw_clear_popup()

    def _draw_sound_button(self):
        """画面右上にサウンドアイコンを描画する

        スピーカー本体を塗りつぶし三角形で描き、
        サウンド有効時は右隣に音波の縦線 2 本を加える。
        """
        cx = self.BTN_SOUND_X + self.BTN_SOUND_W // 2
        cy = self.BTN_SOUND_Y + self.BTN_SOUND_H // 2
        top = self.BTN_SOUND_Y
        bottom = self.BTN_SOUND_Y + self.BTN_SOUND_H
        c = self.SOUND_ICON_COLOR
        tri_left = self.BTN_SOUND_X - self.SOUND_TRI_OFFSET_X
        tri_right = cx - self.SOUND_TRI_OFFSET_X
        self._view.draw_tri(
            tri_left,
            cy,  # 左頂点
            tri_right,
            top,  # 右上
            tri_right,
            bottom,  # 右下
            c,
        )
        if self._sound.enabled:
            wave_top = self.BTN_SOUND_Y + self.SOUND_WAVE_INSET
            wave_bottom = self.BTN_SOUND_Y + self.BTN_SOUND_H - self.SOUND_WAVE_INSET
            for i in range(self.SOUND_WAVE_COUNT):
                x = cx + self.SOUND_WAVE_GAP + i * self.SOUND_WAVE_STEP
                self._view.draw_line(x, wave_top, x, wave_bottom, c)

    def _centered_text_x(self, text):
        """ポップアップ幅の中央にテキストを水平センタリングした左端 X を返す"""
        return (
            self.CLEAR_POPUP_X
            + self.CLEAR_POPUP_W // 2
            - (len(text) * self.CHAR_W) // 2
        )

    def _draw_clear_popup(self):
        self._view.draw_rect(
            self.CLEAR_POPUP_X,
            self.CLEAR_POPUP_Y,
            self.CLEAR_POPUP_W,
            self.CLEAR_POPUP_H,
            self.CLEAR_POPUP_BG_COLOR,
        )
        # 全行（CLEAR / 再起動案内）をブロックとしてポップアップ中央に垂直センタリング
        lines = [self.CLEAR_TEXT, self.RESTART_TEXT]
        block_h = len(lines) * self.CHAR_H + (len(lines) - 1) * self.LINE_GAP
        top_y = self.CLEAR_POPUP_Y + self.CLEAR_POPUP_H // 2 - block_h // 2
        for i, text in enumerate(lines):
            y = top_y + i * (self.CHAR_H + self.LINE_GAP)
            self._view.draw_text(self._centered_text_x(text), y, text)

    def _calc_anim_draw_args(self, col, row):
        """(col, row) のコップに渡すアニメーション描画引数を返す（非アニメーション時はデフォルト）"""
        if self._is_animating():
            if (col, row) == self._board.selected:
                # 移動元: 最上層が progress に応じて縮小（selected が移動元）
                return {"anim_shrink_top": 1.0 - self._calc_anim_progress()}
            if (col, row) == self._anim_dst_pos:
                # 移動先: 追加層が progress に応じて拡大
                return {
                    "anim_extra_color": self._anim_color,
                    "anim_extra_scale": self._calc_anim_progress(),
                }
        return {}

    def _draw_board(self):
        for row in range(Board.ROWS):
            for col in range(Board.COLS):
                cup = self._board.get_cup(col, row)
                if cup.is_completed:
                    continue
                selected = self._board.selected == (col, row)
                self._cup_view.draw(
                    cup.layers,
                    col,
                    row,
                    selected,
                    **self._calc_anim_draw_args(col, row),
                )


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(SCREEN_W, SCREEN_H, title="pyxel sort water")
        pyxel.mouse(True)
        self._sound = PyxelSound.create()
        self._core = GameCore(self._sound)
        pyxel.run(self.update, self.draw)

    def update(self):
        if self._core.needs_reset:
            self._core = GameCore(self._sound)
        else:
            self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(Color.BLACK)
        self._core.draw()


if __name__ == "__main__":
    App()
