"""ゲーム全体（レベル・撃破数・ターン数・Garage を持ち、ターンを進める）。"""

import random
from collections import namedtuple

try:
    from .field import Field  # pylint: disable=C0413
    from .garage import Garage  # pylint: disable=C0413
    from .resource import Component  # pylint: disable=C0413
except ImportError:
    from field import Field  # pylint: disable=C0413
    from garage import Garage  # pylint: disable=C0413
    from resource import Component  # pylint: disable=C0413

# 攻撃 1 回の結果。killed は破壊数、leveled_up はその攻撃で敵を全滅させてレベルが上がったか。
AttackStep = namedtuple("AttackStep", ["killed", "leveled_up"])


class ComboAbilitiesGame:
    """ゲームの状態と、1 ターン分の攻撃・ストックの更新・終了判定を持つ。

    rand は、0 以上 1 未満の一様乱数を返す関数。Field に渡され、テストで固定できる。
    作った直後に、開始時の自動攻撃を 1 回行う（ターン数は 1 になる）。
    """

    MAX_TURN = 10

    def __init__(self, rand=random.random):
        self.rand = rand
        self.garage = Garage()
        self.level = 1
        self.kills = 0
        self.turn = 0
        self.new_game()

    def new_game(self):
        """全状態を初期化して、開始時の自動攻撃を 1 回行う。"""
        self.garage = Garage()
        self.level = 1
        self.kills = 0
        self.turn = 0
        self.play_turn()

    def is_end(self):
        """ターン数が最大ターン数以上なら終了。"""
        return self.turn >= self.MAX_TURN

    def turn_destroy(self):
        """1 ターン分の攻撃。繰り返しが止まるまで続け、獲得をランクの高い順に最大 5 個返す。"""
        return self._attack_turn()[0]

    def _attack_turn(self):
        """1 ターン分の攻撃を行い、(獲得, 攻撃 1 回ごとの結果の列) を返す。"""
        field = Field(level=self.level, rand=self.rand)
        stock_size = len(Component.STOCK.value)
        gain = []
        steps = []
        while True:
            killed = field.attack(
                engine=self.garage.get_lv(Component.ENGINE),
                gun=self.garage.get_lv(Component.GUN),
            )
            self.kills += killed
            gain.extend(field.get_resources(npc=killed, max=stock_size))
            # 敵を全滅させたらレベルを上げて必ず繰り返す。そうでなければ BODY のレベルで判定する
            leveled_up = field.lvup()
            if leveled_up:
                self.level += 1
            steps.append(AttackStep(killed, leveled_up))
            body = self.garage.get_lv(Component.BODY)
            if not (leveled_up or field.judge_repeat(power=body)):
                break
        return sorted(gain, key=lambda c: c.value[1])[:stock_size], steps

    def play_turn(self):
        """ターンの攻撃を行い、ターン数を進めてストックを置き換える。

        攻撃 1 回ごとの結果（AttackStep）の列を返す。終了後は何もせず、空の列を返す。
        """
        if self.is_end():
            return []
        gain, steps = self._attack_turn()
        self.turn += 1
        self.garage.set_stock(gain)
        return steps
