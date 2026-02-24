# title: pyxel raise units
# author: masatobu

from abc import ABC, abstractmethod
from button import Button, UnitButtonIcon
from force import Force, EnemyStrategy
from movable import Direct, Side, UnitType


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, color):
        pass

    @abstractmethod
    def clear(self, color):
        pass

    @abstractmethod
    def get_frame(self):
        pass

    @abstractmethod
    def draw_image(self, x, y, img, u, v, w, h, colkey=None):
        pass

    @classmethod
    def create(cls):
        return cls()


class IInput(ABC):
    @abstractmethod
    def is_click(self):
        pass

    @property
    @abstractmethod
    def mouse_x(self):
        pass

    @property
    @abstractmethod
    def mouse_y(self):
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

    @property
    def mouse_x(self):
        return self.pyxel.mouse_x

    @property
    def mouse_y(self):
        return self.pyxel.mouse_y


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def draw_rectb(self, x, y, w, h, color):
        self.pyxel.rectb(x, y, w, h, color)

    def clear(self, color):
        self.pyxel.cls(color)

    def get_frame(self):
        return self.pyxel.frame_count

    def draw_image(self, x, y, img, u, v, w, h, colkey=None):
        if colkey is not None:
            self.pyxel.blt(x, y, img, u, v, w, h, colkey)
        else:
            self.pyxel.blt(x, y, img, u, v, w, h)


class IMovableView(ABC):
    """Movableオブジェクト（ユニット・攻撃エフェクト）描画の抽象インターフェース"""

    @abstractmethod
    def draw_unit(self, x, y, side, face, direct, is_damaged, unit_type):
        """ユニットを描画する

        Args:
            x: 描画X座標
            y: 描画Y座標
            side: 自軍/敵軍 (Side.PLAYER or Side.ENEMY)
            face: 顔の向き (Direct.RIGHT or Direct.LEFT)
            direct: 移動方向 (Direct.RIGHT, Direct.LEFT, or Direct.NEUTRAL)
            is_damaged: 被弾中かどうか（Trueの場合、点滅表示）
            unit_type: ユニット種別 (UnitType)
        """

    @abstractmethod
    def draw_attack(self, x, y, side, progress, unit_type):
        """攻撃エフェクトを描画する

        Args:
            x: 描画X座標
            y: 描画Y座標
            side: 自軍/敵軍 (Side.PLAYER or Side.ENEMY)
            progress: 消失までの進捗割合（0.0〜1.0）
            unit_type: ユニット種別 (UnitType)
        """

    @classmethod
    def create(cls):
        return cls()


class PyxelMovableView(IMovableView):
    """Pyxel用Movableオブジェクト描画実装"""

    def __init__(self):
        self.view = PyxelView.create()
        # ユニットアニメーションパターン定数
        self._moving_pattern = [0, 1, 0, 3]
        self._moving_interval = 5
        self._idle_interval = 10
        self._blink_interval = 5
        # 攻撃アニメーション定数
        self._attack_anim_frames = 3  # アニメーションフレーム数（タイル5,6,7）

    @staticmethod
    def _calc_base_tile_y(unit_type, side):
        """ユニット種別と陣営からタイルシートの基準行インデックスを計算する"""
        return (unit_type.value - 1) * 2 + (1 if side == Side.ENEMY else 0)

    def draw_unit(self, x, y, side, face, direct, is_damaged, unit_type):
        frame = self.view.get_frame()

        # 被弾中は5フレームごとに表示/非表示を切替（点滅）
        if is_damaged and (frame // self._blink_interval) % 2 == 0:
            return  # 描画スキップ

        # 基準タイル座標の決定
        base_tile_x = 1
        base_tile_y = self._calc_base_tile_y(unit_type, side)

        # アニメーションフレーム計算
        if direct == Direct.NEUTRAL:
            # 待機中: 0→2（10フレームごと）
            anim_frame = 0 if (frame // self._idle_interval) % 2 == 0 else 2
        else:
            # 移動中: 0→1→0→3（5フレームごと）
            anim_index = (frame // self._moving_interval) % 4
            anim_frame = self._moving_pattern[anim_index]

        # ピクセル座標計算
        u = (base_tile_x + anim_frame) * 8
        v = base_tile_y * 8

        # 向きの決定
        w = -8 if face == Direct.LEFT else 8

        self.view.draw_image(x, y, 0, u, v, w, 8, 0)

    def draw_attack(self, x, y, side, progress, unit_type):
        base_tile_x = 5
        base_tile_y = self._calc_base_tile_y(unit_type, side)
        anim_frame = int(progress * self._attack_anim_frames)
        u = (base_tile_x + anim_frame) * 8
        v = base_tile_y * 8
        w = -8 if side == Side.ENEMY else 8
        self.view.draw_image(x, y, 0, u, v, w, 8, 0)


class GameCore:
    POPUP_W = 130
    POPUP_H = 30
    POPUP_X = (150 - POPUP_W) // 2  # = 10
    POPUP_Y = (200 - POPUP_H) // 2  # = 85
    UNIT_Y = 90  # ユニット描画 Y 座標
    COIN_SIZE = 4
    COIN_GAP = 1
    COIN_STEP = 5  # = COIN_SIZE + COIN_GAP（コイン描画ピクセル間隔）
    FUND_PER_COIN = 5  # 5資金 = 1コイン/シンボル（変換レート）
    COIN_MAX_PER_COL = 12
    COIN_MAX_COLS = 2
    COIN_MAX = 24  # = COIN_MAX_PER_COL * COIN_MAX_COLS
    COIN_BOTTOM_Y = 162  # = BUTTON_Y(168) - COIN_SIZE(4) - COIN_GAP(1) - 1px gap
    SYMBOL_U = 0
    SYMBOL_V = 16  # タイル座標 (0,2) → v = 2*8 = 16
    SYMBOL_SIZE = 4
    SYMBOL_STEP = SYMBOL_SIZE + COIN_GAP  # = 5
    TILE_SIZE = 8  # Movable.TILE_SIZE と同値
    SCREEN_W = 150  # 画面横幅（px）
    HP_BAR_W = 2  # HPバー幅（px）
    HP_BAR_MAX_H = 60  # HPバー最大高さ（px）
    HP_BAR_MARGIN = 4  # HPバー下端とユニット上端の間隔（px）
    HP_BAR_BG_COLOR = 13  # 背景色
    HP_BAR_PLAYER_COLOR = 5  # 自軍HPバー色
    HP_BAR_ENEMY_COLOR = 2  # 敵軍HPバー色
    HP_BAR_PLAYER_X = 1  # 自軍HPバーX座標（左端近く）
    HP_BAR_ENEMY_X = SCREEN_W - HP_BAR_W - 1  # 敵軍HPバーX座標（右端近く）= 147

    def __init__(self, enemy_strategy=None):
        self.view = PyxelView.create()
        self.movable_view = PyxelMovableView.create()
        self.input = PyxelInput.create()
        self._needs_reset = False
        self.force = {
            Side.PLAYER: Force(Side.PLAYER),
            Side.ENEMY: Force(Side.ENEMY, strategy=enemy_strategy),
        }
        self.low_button = Button(
            x=9, y=168, width=42, height=12, icon=UnitButtonIcon.LOWER
        )
        self.mid_button = Button(
            x=54, y=168, width=42, height=12, icon=UnitButtonIcon.MIDDLE
        )
        self.upp_button = Button(
            x=99, y=168, width=42, height=12, icon=UnitButtonIcon.UPPER
        )
        self._spawn_buttons = [
            (self.low_button, UnitType.LOWER),
            (self.mid_button, UnitType.MIDDLE),
            (self.upp_button, UnitType.UPPER),
        ]

    @property
    def enemy_strategy(self) -> EnemyStrategy | None:
        return self.force[Side.ENEMY].strategy

    @property
    def player_lost(self) -> bool:
        return self.force[Side.PLAYER].is_base_destroyed

    def is_game_over(self) -> bool:
        """いずれかの軍の拠点が撃破されればゲーム終了"""
        return any(force.is_base_destroyed for force in self.force.values())

    def needs_reset(self) -> bool:
        """リセットが必要かどうかを返す"""
        return self._needs_reset

    @staticmethod
    def _is_in_rect(mx, my, rx, ry, rw, rh):
        return rx <= mx < rx + rw and ry <= my < ry + rh

    def update(self):
        if self.is_game_over():
            if self.input.is_click() and self._is_in_rect(
                self.input.mouse_x,
                self.input.mouse_y,
                self.POPUP_X,
                self.POPUP_Y,
                self.POPUP_W,
                self.POPUP_H,
            ):
                self._needs_reset = True
            return
        if self.input.is_click():
            mx, my = self.input.mouse_x, self.input.mouse_y
            for button, unit_type in self._spawn_buttons:
                if button.is_clicked(mx, my):
                    button.press()
                    self.force[Side.PLAYER].put_unit(unit_type)
                    break
        for side, opposite in [(Side.PLAYER, Side.ENEMY), (Side.ENEMY, Side.PLAYER)]:
            self.force[side].set_opponent_head_x(self.force[opposite].get_head_x())
            self.force[side].take_damage(self.force[opposite].attacks)
        for button, _ in self._spawn_buttons:
            button.update()
        for force in self.force.values():
            force.update()

    def draw(self):
        self.view.clear(0)
        for force in self.force.values():
            # _units は [BASE, ...] の順で登録されるため、逆順で BASE が最後（最前面）に描画される
            for unit in reversed(force.units):
                self._draw_unit(unit)
            for attack in force.attacks:
                self._draw_attack(attack)
        self._draw_base_hp_bars()
        self._draw_funds()
        self._draw_spawn_button()
        if self.is_game_over():
            self._draw_game_result_popup()

    def _draw_base_hp_bars(self):
        """各拠点ユニットの残HPバーを描画する"""
        bar_xs = {
            Side.PLAYER: self.HP_BAR_PLAYER_X,
            Side.ENEMY: self.HP_BAR_ENEMY_X,
        }
        fg_colors = {
            Side.PLAYER: self.HP_BAR_PLAYER_COLOR,
            Side.ENEMY: self.HP_BAR_ENEMY_COLOR,
        }
        for side, force in self.force.items():
            ratio = force.base_hp_ratio
            bar_x = bar_xs[side]
            bar_bottom_y = self.UNIT_Y - self.HP_BAR_MARGIN
            self.view.draw_rect(
                bar_x,
                bar_bottom_y - self.HP_BAR_MAX_H,
                self.HP_BAR_W,
                self.HP_BAR_MAX_H,
                self.HP_BAR_BG_COLOR,
            )
            fill_h = round(self.HP_BAR_MAX_H * ratio)
            self.view.draw_rect(
                bar_x,
                bar_bottom_y - fill_h,
                self.HP_BAR_W,
                fill_h,
                fg_colors[side],
            )

    def _draw_funds(self):
        for side, is_player in [(Side.PLAYER, True), (Side.ENEMY, False)]:
            fund = self.force[side].fund
            coin_count = min(fund // self.FUND_PER_COIN, self.COIN_MAX)
            for i in range(coin_count):
                col = i // self.COIN_MAX_PER_COL
                row = i % self.COIN_MAX_PER_COL
                y = self.COIN_BOTTOM_Y - row * self.COIN_STEP
                if is_player:
                    x = col * self.COIN_STEP
                else:
                    x = 150 - self.COIN_SIZE - col * self.COIN_STEP
                self.view.draw_image(x, y, 0, 0, 8, self.COIN_SIZE, self.COIN_SIZE)

    def _draw_spawn_button(self):
        for button, unit_type in self._spawn_buttons:
            button.draw(self.view)
            count = Force.SPAWN_COST[unit_type] // self.FUND_PER_COIN
            symbol_x = button.x + (button.width - self.SYMBOL_SIZE) // 2
            for i in range(count):
                y = button.y - self.SYMBOL_SIZE - 1 - i * self.SYMBOL_STEP
                self.view.draw_image(
                    symbol_x,
                    y,
                    0,
                    self.SYMBOL_U,
                    self.SYMBOL_V,
                    self.SYMBOL_SIZE,
                    self.SYMBOL_SIZE,
                )

    def _draw_game_result_popup(self):
        self.view.draw_rect(self.POPUP_X, self.POPUP_Y, self.POPUP_W, self.POPUP_H, 0)
        self.view.draw_rectb(self.POPUP_X, self.POPUP_Y, self.POPUP_W, self.POPUP_H, 7)
        if self.force[Side.ENEMY].is_base_destroyed:
            message = "You Win! Click to Restart."
        else:
            message = "You Lose! Click to Restart."
        self.view.draw_text(self.POPUP_X + 10, self.POPUP_Y + 10, message)

    def _draw_unit(self, unit):
        self.movable_view.draw_unit(
            unit.x,
            self.UNIT_Y,
            unit.side,
            unit.face,
            unit.direct,
            unit.is_damaged,
            unit.unit_type,
        )

    def _draw_attack(self, attack):
        self.movable_view.draw_attack(
            attack.x, self.UNIT_Y, attack.side, attack.progress, attack.unit_type
        )


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        self.game_core = GameCore()

        pyxel.init(150, 200, title="Pyxel Raise Units")
        pyxel.load("images.pyxres")
        pyxel.mouse(True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if self.game_core.needs_reset():
            strategy = (
                self.game_core.enemy_strategy if self.game_core.player_lost else None
            )
            self.game_core = GameCore(enemy_strategy=strategy)
        else:
            self.game_core.update()

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
