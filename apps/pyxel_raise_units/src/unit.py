from dataclasses import dataclass
from movable import Movable, Side, Direct, UnitType
from attack import Attack


@dataclass(frozen=True)
class UnitParams:
    hp: int
    speed: float
    range: int
    interval: int


class Unit(Movable):
    TYPE_PARAMS = {
        UnitType.MIDDLE: UnitParams(hp=3, speed=0.5, range=15, interval=30),
        UnitType.LOWER: UnitParams(hp=1, speed=0.8, range=12, interval=20),
        UnitType.UPPER: UnitParams(hp=10, speed=0.3, range=25, interval=60),
        UnitType.BASE: UnitParams(hp=20, speed=0.0, range=30, interval=40),
    }
    DAMAGED_FRAMES = 10

    SPAWN_X_PLAYER = 0
    SPAWN_X_ENEMY = Movable.SCREEN_WIDTH - Movable.TILE_SIZE  # 画面内に収まる位置 = 142

    def __init__(
        self,
        side: Side,
        unit_type: UnitType,
        x: int = None,
    ) -> None:
        start_pos = (
            x
            if x is not None
            else (Unit.SPAWN_X_PLAYER if side == Side.PLAYER else Unit.SPAWN_X_ENEMY)
        )
        params = Unit.TYPE_PARAMS[unit_type]
        super().__init__(start_pos, side, params.speed, unit_type)
        self._hp = params.hp
        self._speed = params.speed
        self._range = params.range
        self._interval = params.interval
        self._damaged_frames = 0
        self._opponent_head_x = None
        self._cooldown = 0

    @property
    def hp(self) -> int:
        """現在のHPを取得"""
        return self._hp

    @property
    def is_alive(self) -> bool:
        """生存しているかどうか"""
        return self._hp > 0

    @property
    def is_damaged(self) -> bool:
        """被弾中かどうかを取得"""
        return self._damaged_frames > 0

    def take_damage(self) -> None:
        """被弾状態にし、HPを1減少させる"""
        self._hp -= 1
        self._damaged_frames = Unit.DAMAGED_FRAMES

    def set_opponent_head_x(self, x: int) -> None:
        """相手の最前列の位置を把握する"""
        self._opponent_head_x = x

    def _is_in_combat(self) -> bool:
        """戦闘状態かどうかを判定"""
        return self._direct == Direct.NEUTRAL

    @property
    def can_attack(self) -> bool:
        """攻撃可能かどうかを判定"""
        return self._is_in_combat() and self._cooldown == 0

    def create_attack(self) -> Attack:
        """攻撃エフェクトを生成し、クールダウンをリセット"""
        attack_x = self.x + self._face.value * self.TILE_SIZE
        self._cooldown = self._interval
        attack_range = self._range - self.TILE_SIZE + 1
        return Attack(attack_x, self._side, self.unit_type, attack_range)

    def _update_direct(self) -> None:
        """移動するか否かを更新"""
        if self._side == Side.PLAYER and (
            self._opponent_head_x is None
            or self._x + self._range < self._opponent_head_x
        ):
            self.set_direct(Direct.RIGHT)
        elif self._side == Side.ENEMY and (
            self._opponent_head_x is None
            or self._x - self._range > self._opponent_head_x
        ):
            self.set_direct(Direct.LEFT)
        else:
            self.set_direct(Direct.NEUTRAL)

    def update(self) -> None:
        """ユニットの状態を更新（移動、被弾フレーム減少）"""
        self._update_direct()
        super().update()
        if self._damaged_frames > 0:
            self._damaged_frames -= 1
        if self._cooldown > 0:
            self._cooldown -= 1

    def __repr__(self) -> str:
        return f"Unit(x={self.x}, side={self._side})"
