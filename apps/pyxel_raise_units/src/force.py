import random
from enum import Enum

from unit import Unit  # pylint: disable=C0413
from movable import Side, UnitType  # pylint: disable=C0413
from attack import Attack  # pylint: disable=C0413


class EnemyStrategy(Enum):
    LOWER_ONLY = "lower_only"
    MIDDLE_ONLY = "middle_only"
    UPPER_ONLY = "upper_only"
    CYCLE = "cycle"


class Force:

    AUTO_PUT_INTERVAL = 30  # 資金不足時はスポーンしないため短いインターバルで問題ない
    FUND_INTERVAL = 5
    FUND_ADD = 1
    # FUND_ADD(1)/FUND_INTERVAL(5f) ≒ 6資金/秒。
    # AUTO_PUT_INTERVAL(30f) ごとにスポーン試行。戦略により候補を選択。
    # fund 不足でスポーン失敗した場合もインデックスは進め、次サイクルに繰り越す。
    SPAWN_COST = {
        UnitType.LOWER: 10,
        UnitType.MIDDLE: 25,
        UnitType.UPPER: 60,
    }
    STRATEGY_SPAWN_TYPES = {
        EnemyStrategy.LOWER_ONLY: [UnitType.LOWER],
        EnemyStrategy.MIDDLE_ONLY: [UnitType.MIDDLE],
        EnemyStrategy.UPPER_ONLY: [UnitType.UPPER],
        EnemyStrategy.CYCLE: [UnitType.LOWER, UnitType.MIDDLE, UnitType.UPPER],
    }

    BASE_X_ENEMY = Unit.SPAWN_X_ENEMY  # 画面内に表示 = 142

    def __init__(self, side: Side, strategy: EnemyStrategy = None) -> None:
        self._side = side
        base_x = self.BASE_X_ENEMY if side == Side.ENEMY else None
        self._units = [Unit(side, UnitType.BASE, x=base_x)]
        self._attacks = []
        self._is_auto_put_unit = side == Side.ENEMY
        self._auto_put_cooldown = self.AUTO_PUT_INTERVAL
        self._auto_spawn_index = 0
        self._fund = 0
        self._fund_cooldown = self.FUND_INTERVAL
        if side == Side.ENEMY:
            self._strategy = (
                strategy if strategy is not None else random.choice(list(EnemyStrategy))
            )
        else:
            self._strategy = None

    @property
    def units(self):
        return self._units

    @property
    def attacks(self):
        return self._attacks

    @property
    def is_base_destroyed(self) -> bool:
        """拠点ユニットが撃破されたか"""
        return not any(unit.unit_type == UnitType.BASE for unit in self._units)

    @property
    def base_hp_ratio(self) -> float:
        """拠点ユニットの残HP割合（残HP / 最大HP）を返す。拠点破壊済みなら 0.0"""
        base = next((u for u in self._units if u.unit_type == UnitType.BASE), None)
        if base is None:
            return 0.0
        return base.hp / Unit.TYPE_PARAMS[UnitType.BASE].hp

    @property
    def fund(self) -> int:
        return self._fund

    @property
    def strategy(self) -> "EnemyStrategy | None":
        return self._strategy

    def get_head_x(self) -> int:
        """最前列のx座標を取得"""
        if not self._units:
            return None
        if self._side == Side.PLAYER:
            return max(unit.x for unit in self._units)
        return min(unit.x for unit in self._units)

    def set_opponent_head_x(self, x: int) -> None:
        """敵軍の先頭位置を各ユニットに設定"""
        for unit in self._units:
            unit.set_opponent_head_x(x)

    def put_unit(self, unit_type: UnitType = UnitType.MIDDLE) -> bool:
        """軍資金を消費してユニットをスポーンする。
        LOWER/MIDDLE/UPPER は fund チェックあり。BASE はコスト不要。
        """
        if unit_type in self.SPAWN_COST:
            cost = self.SPAWN_COST[unit_type]
            if self._fund < cost:
                return False
            self._fund -= cost
        self._units.append(Unit(self._side, unit_type))
        return True

    def take_damage(self, attacks: list[Attack]) -> None:
        """各ユニットが攻撃を受ける"""
        for attack in attacks:
            for unit in self._units:
                if attack.is_hitting(unit):
                    unit.take_damage()
                    attack.deactivate()
                    break

    def update(self) -> None:
        """軍に所属するユニットと攻撃を更新"""
        for attack in self._attacks:
            attack.update()
        self._attacks = [attack for attack in self._attacks if attack.is_visible]
        for unit in self._units:
            unit.update()
        self._attacks.extend(
            unit.create_attack() for unit in self._units if unit.can_attack
        )
        self._units = [unit for unit in self._units if unit.is_alive or unit.is_damaged]
        self._update_fund()  # fund を先に更新
        self._auto_put()  # 更新後の fund で spawn 判定

    def _auto_put(self) -> None:
        """自動スポーンのクールダウン管理。STRATEGY_SPAWN_TYPES に従い選択してスポーンする。
        fund 不足でスポーン失敗した場合はインデックスを進めない（次回同じユニットを再試行）。"""
        if not self._is_auto_put_unit:
            return
        self._auto_put_cooldown -= 1
        if self._auto_put_cooldown <= 0:
            spawn_types = self.STRATEGY_SPAWN_TYPES[self._strategy]
            unit_type = spawn_types[self._auto_spawn_index % len(spawn_types)]
            if self.put_unit(unit_type):
                self._auto_spawn_index += 1
            self._auto_put_cooldown = self.AUTO_PUT_INTERVAL

    def _update_fund(self) -> None:
        """軍資金クールダウン管理"""
        self._fund_cooldown -= 1
        if self._fund_cooldown <= 0:
            self._fund += self.FUND_ADD
            self._fund_cooldown = self.FUND_INTERVAL

    def __repr__(self) -> str:
        return (
            f"Force(side={self._side}, strategy={self._strategy}, units={self._units})"
        )
