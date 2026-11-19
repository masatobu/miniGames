"""フィールド（敵の残数とレベルを持ち、攻撃を判定する）。"""

import math
import random

try:
    from .binom_dist import BinomDist  # pylint: disable=C0413
    from .norm_dist import NormDist  # pylint: disable=C0413
    from .resource import Resource  # pylint: disable=C0413
except ImportError:
    from binom_dist import BinomDist  # pylint: disable=C0413
    from norm_dist import NormDist  # pylint: disable=C0413
    from resource import Resource  # pylint: disable=C0413


class Field:
    """ゲームのレベルと敵の残数を持ち、攻撃 1 回分の判定を行う。

    rand は、0 以上 1 未満の一様乱数を返す関数。テストで固定するために差し替えられる。
    """

    MAX_NPC_NUM = 10
    MAX_ENGINE_LEVEL = 4
    MAX_GUN_LEVEL = 4

    def __init__(self, level=1, rand=random.random):
        self.level = level
        self.npc = self.MAX_NPC_NUM
        self.rand = rand

    def judge_target(self, power=1):
        """ENGINE のレベル power から、攻撃の対象数を決める（最大は敵の最大数）。"""
        mu = power / (self.MAX_ENGINE_LEVEL + 1) * self.MAX_NPC_NUM
        dist = NormDist(sigma=1, mu=mu)
        ret = math.ceil(dist.inv_normal_pdf(self.rand() * dist.point0))
        return min(ret, self.MAX_NPC_NUM)

    def judge_kill(self, power=1, npc=1):
        """GUN のレベル power と対象数 npc から、破壊数を決める（対象がいれば最低 1）。"""
        if npc == 0:
            return 0
        prob = power / (self.MAX_GUN_LEVEL + 1) * (1 / 2) ** (self.level / 10)
        dist = BinomDist(p=prob, n=npc)
        return max(1, dist.inv_binom_pdf(self.rand()))

    def get_resources(self, npc=1, max=1):  # pylint: disable=redefined-builtin
        """npc 個のリソースを抽選し、ランクの高い順に並べて先頭の min(max, npc) 個を返す。

        出現の重みは「基本 + 加算 × レベル」。
        """
        base = 0
        cand = {}
        for res in Resource.avails():
            base += res.value[1] + res.value[2] * self.level
            cand[base] = res
        ret = []
        for _ in range(npc):
            choice = base * self.rand()
            for limit in sorted(cand.keys()):
                if choice < limit:
                    ret.append(cand[limit])
                    break
        return sorted(ret, key=lambda c: c.value[1])[0 : min(max, npc)]

    def attack(self, engine=1, gun=1):
        """攻撃 1 回分。ENGINE と GUN のレベルから破壊数を決め、敵の残数から引いて返す。"""
        target = min(self.npc, self.judge_target(power=engine))
        killed = self.judge_kill(power=gun, npc=target)
        self.npc -= killed
        return killed

    def judge_repeat(self, power=1):
        """BODY のレベル power から、攻撃を繰り返すか決める。止まる確率は 0.5^power。"""
        stop = BinomDist(p=0.5, n=power).binom_pdf(0)
        return self.rand() >= stop

    def lvup(self):
        """敵が残っていなければ、レベルを 1 上げて敵を最大数に戻し、True を返す。"""
        if self.npc != 0:
            return False
        self.level += 1
        self.npc = self.MAX_NPC_NUM
        return True
