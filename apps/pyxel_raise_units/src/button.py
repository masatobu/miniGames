from enum import Enum


class UnitButtonIcon(Enum):
    """スポーンボタン用ユニットアイコンのタイル座標定義

    タイル座標は images.pyxres のタイルシートに対応（自軍・idle フレーム）:
    - u = 8  (base_tile_x=1, anim_frame=0)
    - v = base_tile_y * 8  (player 側)

    アイコンサイズ: 8×8px、向き: 右向き (w=8)、カラーキー: 0 (黒透過)
    """

    LOWER = (8, 32)  # LOWER:  unit_type.value=3 → base_tile_y=4 → v=32
    MIDDLE = (8, 0)  # MIDDLE: unit_type.value=1 → base_tile_y=0 → v=0
    UPPER = (8, 16)  # UPPER:  unit_type.value=2 → base_tile_y=2 → v=16


class Button:
    ICON_SIZE = 8  # アイコンサイズ (px)
    PRESS_DURATION = 6  # 押下フィードバック継続フレーム数（30fps で約 0.2 秒）
    PRESSED_BG_COLOR = 13  # 押下中の背景色（グレー）
    NORMAL_BG_COLOR = 0  # 通常時の背景色（黒）

    def __init__(self, x, y, width, height, icon):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.icon = icon
        self._press_timer = 0

    def press(self):
        """押下タイマーをセット（継続時間は PRESS_DURATION で決定）"""
        self._press_timer = self.PRESS_DURATION

    def update(self):
        """フレームごとにタイマーを減算"""
        if self._press_timer > 0:
            self._press_timer -= 1

    def _is_pressed(self):
        """押下中（タイマー > 0）なら True — draw() 内部専用"""
        return self._press_timer > 0

    def draw(self, view):
        bg_color = self.PRESSED_BG_COLOR if self._is_pressed() else self.NORMAL_BG_COLOR
        view.draw_rect(self.x, self.y, self.width, self.height, bg_color)
        view.draw_rectb(self.x, self.y, self.width, self.height, 7)
        u, v = self.icon.value
        icon_x = self.x + (self.width - self.ICON_SIZE) // 2
        icon_y = self.y + (self.height - self.ICON_SIZE) // 2
        view.draw_image(icon_x, icon_y, 0, u, v, self.ICON_SIZE, self.ICON_SIZE, 0)

    def is_clicked(self, mouse_x, mouse_y):
        return (
            self.x <= mouse_x < self.x + self.width
            and self.y <= mouse_y < self.y + self.height
        )
