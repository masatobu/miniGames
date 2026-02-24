from movable import Movable, Side, UnitType


class Attack(Movable):
    SPEED = 2.0  # ユニットの4倍の速度

    def __init__(
        self,
        x: int,
        side: Side,
        unit_type: UnitType,
        range_num: int,
        speed: float = SPEED,
    ) -> None:
        super().__init__(x, side, speed, unit_type)
        self._is_alive = True
        self._moved = 0
        self._range = range_num

    @property
    def is_alive(self) -> bool:
        return self._is_alive

    @property
    def range(self) -> int:
        return self._range

    @property
    def is_visible(self) -> bool:
        return self._moved < self._range

    @property
    def progress(self) -> float:
        """消失までの進捗割合（0.0〜1.0）"""
        return self._moved / self._range

    def is_hitting(self, unit) -> bool:
        """当たり判定: 対抗陣営 + 距離がTILE_SIZE未満 + 未無効化 + 対象の未被弾"""
        if not self._is_alive or not self.is_visible:
            return False
        if self._side == unit.side:
            return False
        if unit.is_damaged:
            return False
        return abs(self.x - unit.x) < self._range

    def deactivate(self) -> None:
        """命中後に攻撃を無効化"""
        self._is_alive = False

    def update(self) -> None:
        super().update()
        self._moved += self.SPEED
        if self._x < 0 or self._x >= self.SCREEN_WIDTH:
            self._is_alive = False

    def __repr__(self) -> str:
        return f"Attack(x={self.x}, side={self._side})"
