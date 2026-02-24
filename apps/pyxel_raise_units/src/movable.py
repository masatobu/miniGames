from enum import Enum


class Side(Enum):
    PLAYER = 0
    ENEMY = 1


class Direct(Enum):
    LEFT = -1
    RIGHT = 1
    NEUTRAL = 0


class UnitType(Enum):
    # 値はimages.pyxresのユニット画像の行位置に対応
    BASE = 4
    LOWER = 3
    MIDDLE = 1
    UPPER = 2


class Movable:
    SCREEN_WIDTH = 150  # 画面幅
    TILE_SIZE = 8  # タイルサイズ（8x8px）

    def __init__(self, x: int, side: Side, speed: float, unit_type: UnitType) -> None:
        self._x = float(x)
        self._side = side
        self._face = Direct.RIGHT if side == Side.PLAYER else Direct.LEFT
        self._direct = self._face
        self._speed = speed
        self._unit_type = unit_type

    @property
    def x(self) -> int:
        return int(self._x)

    @property
    def side(self) -> Side:
        return self._side

    @property
    def direct(self) -> Direct:
        return self._direct

    @property
    def face(self) -> Direct:
        """顔の向きを取得"""
        return self._face

    @property
    def unit_type(self) -> UnitType:
        """ユニットのタイプを取得"""
        return self._unit_type

    def set_direct(self, direct: Direct) -> None:
        """移動方向を設定"""
        self._direct = direct

    def update(self) -> None:
        self._x += self._direct.value * self._speed

    def __repr__(self) -> str:
        return f"Movable(x={self.x}, side={self._side})"
