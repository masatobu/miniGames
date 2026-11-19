"""Field（攻撃の判定）のテスト。乱数は rand 引数で固定する。"""

import math
import unittest

from src.binom_dist import BinomDist
from src.field import Field
from src.norm_dist import NormDist
from src.resource import Resource


def fixed(*values):
    """呼ぶたびに values を順に返す乱数の供給元（呼び出し回数も数える）。"""
    queue = list(values)
    calls = []

    def rand():
        calls.append(1)
        return queue.pop(0)

    rand.calls = calls
    return rand


class TestFieldInit(unittest.TestCase):
    """FR1: フィールドの状態。"""

    def test_init(self):
        """レベルを指定でき、敵の残数は最大数（10）から始まる。"""
        field = Field(level=2)
        self.assertEqual(field.level, 2)
        self.assertEqual(field.npc, field.MAX_NPC_NUM)

    def test_init_default_level(self):
        """レベルの既定は 1。"""
        self.assertEqual(Field().level, 1)

    def test_constants(self):
        """敵の最大数と、ENGINE・GUN の最大レベル。"""
        self.assertEqual(Field.MAX_NPC_NUM, 10)
        self.assertEqual(Field.MAX_ENGINE_LEVEL, 4)
        self.assertEqual(Field.MAX_GUN_LEVEL, 4)


class TestJudgeTarget(unittest.TestCase):
    """FR2: 対象数の判定。"""

    def expect_target(self, power, rand_value):
        """期待値: ceil(逆算した点)。平均 = power ÷ (最大レベル + 1) × 敵の最大数。"""
        mu = power / (Field.MAX_ENGINE_LEVEL + 1) * Field.MAX_NPC_NUM
        dist = NormDist(mu=mu, sigma=1)
        point = dist.inv_normal_pdf(rand_value * dist.point0)
        return min(math.ceil(point), Field.MAX_NPC_NUM)

    def test_peak(self):
        """乱数が 1 のとき（確率密度が最大）、結果は ceil(平均)。power=1 なら 2。"""
        field = Field(level=2, rand=fixed(1.0))
        self.assertEqual(field.judge_target(power=1), math.ceil(1 / 5 * 10))

    def test_formula(self):
        """power ごとに、乱数 0.5 での結果が計算式と一致する。"""
        for power in range(1, Field.MAX_ENGINE_LEVEL + 1):
            field = Field(rand=fixed(0.5))
            self.assertEqual(
                field.judge_target(power=power), self.expect_target(power, 0.5)
            )

    def test_upper_limit(self):
        """結果が敵の最大数を超えるときは、敵の最大数にする。乱数 0 は無限遠側。"""
        field = Field(rand=fixed(0.0))
        self.assertEqual(field.judge_target(power=1), Field.MAX_NPC_NUM)

    def test_uses_rand_once(self):
        """乱数の供給元を 1 回だけ呼ぶ。"""
        rand = fixed(0.3)
        Field(rand=rand).judge_target(power=1)
        self.assertEqual(len(rand.calls), 1)

    def test_default_rand_range(self):
        """既定の乱数でも、結果は敵の最大数以下。"""
        field = Field(level=2)
        ret = field.judge_target(power=1)
        self.assertTrue(0 < ret <= Field.MAX_NPC_NUM)


class TestJudgeKill(unittest.TestCase):
    """FR3: 破壊数の判定。"""

    def expect_kill(self, level, power, npc, rand_value):
        """期待値: 二項分布（p = power ÷ 5 × (1/2)^(level ÷ 10)、n = npc）の逆算。最低 1。"""
        prob = power / (Field.MAX_GUN_LEVEL + 1) * (1 / 2) ** (level / 10)
        dist = BinomDist(p=prob, n=npc)
        return max(1, dist.inv_binom_pdf(rand_value))

    def test_zero_npc(self):
        """対象が 0 体なら 0。乱数は使わない。"""
        rand = fixed()
        self.assertEqual(Field(rand=rand).judge_kill(power=4, npc=0), 0)
        self.assertEqual(len(rand.calls), 0)

    def test_at_least_one(self):
        """対象が 1 体以上なら、乱数が 0 でも最低 1 体は破壊する。"""
        field = Field(level=1, rand=fixed(0.0))
        self.assertEqual(field.judge_kill(power=1, npc=5), 1)

    def test_formula(self):
        """レベル・power・npc・乱数の組み合わせで、計算式と一致する。"""
        for level in (1, 2, 10):
            for power in range(1, Field.MAX_GUN_LEVEL + 1):
                for rand_value in (0.1, 0.5, 0.99):
                    field = Field(level=level, rand=fixed(rand_value))
                    self.assertEqual(
                        field.judge_kill(power=power, npc=5),
                        self.expect_kill(level, power, 5, rand_value),
                    )

    def test_upper_limit(self):
        """乱数が 1 に近いとき、結果は対象数（npc）を超えない。"""
        field = Field(level=1, rand=fixed(0.999999))
        self.assertLessEqual(field.judge_kill(power=4, npc=5), 5)

    def test_default_rand_range(self):
        """既定の乱数でも、1 以上 npc 以下（移植元のテストと同じ）。"""
        field = Field(level=2)
        ret = field.judge_kill(power=1, npc=5)
        self.assertTrue(0 < ret <= 5)


class TestLvup(unittest.TestCase):
    """FR5: レベルアップ。"""

    def test_lvup(self):
        """敵の残数が 0 のとき、レベルが 1 上がり、敵が最大数に戻り、True を返す。"""
        field = Field(level=2)
        field.npc = 0
        self.assertTrue(field.lvup())
        self.assertEqual(field.level, 2 + 1)
        self.assertEqual(field.npc, Field.MAX_NPC_NUM)

    def test_lvup_false(self):
        """敵が残っているときは、何も変えず False を返す。"""
        field = Field(level=2)
        field.npc = 1
        self.assertFalse(field.lvup())
        self.assertEqual(field.level, 2)
        self.assertEqual(field.npc, 1)


class TestGetResources(unittest.TestCase):
    """FR4: リソースの獲得（抽選）。"""

    @staticmethod
    def weights(level):
        """出現の重み「基本 + 加算 × レベル」を、出現するリソースの順に返す。"""
        return [(r, r.value[1] + r.value[2] * level) for r in Resource.avails()]

    def pick_rand(self, level, target):
        """target が選ばれる区間の中央に当たる乱数値（区間は累積の重みで決まる）。"""
        total = sum(w for _, w in self.weights(level))
        low = 0
        for res, weight in self.weights(level):
            if res is target:
                return (low + weight / 2) / total
            low += weight
        raise AssertionError("target not found")

    def test_each_resource_is_reachable(self):
        """レベルごとに、9 種類のすべてが、累積の重みの区間どおりに選ばれる。"""
        for level in (1, 5):
            for target in Resource.avails():
                field = Field(level=level, rand=fixed(self.pick_rand(level, target)))
                self.assertEqual(field.get_resources(npc=1, max=1), [target])

    def test_interval_boundary(self):
        """乱数が最初の区間の境界（重みの合計に対する比）のとき、次のリソースになる。"""
        level = 1
        (first, first_weight), (second, _) = self.weights(level)[:2]
        total = sum(w for _, w in self.weights(level))
        just_below = (first_weight - 0.5) / total
        at_boundary = first_weight / total
        self.assertEqual(
            Field(level=level, rand=fixed(just_below)).get_resources(1, 1), [first]
        )
        self.assertEqual(
            Field(level=level, rand=fixed(at_boundary)).get_resources(1, 1), [second]
        )

    def test_sorted_by_rank(self):
        """獲得したリソースは、ランクの高い順（GOLD、SILVER、BRONZE）に並ぶ。"""
        level = 1
        bronze, silver, gold = (
            Resource.THINGS_BRONZE,
            Resource.STAR_SILVER,
            Resource.BOLT_GOLD,
        )
        rand = fixed(*[self.pick_rand(level, r) for r in (bronze, gold, silver)])
        ret = Field(level=level, rand=rand).get_resources(npc=3, max=3)
        self.assertEqual(ret, [gold, silver, bronze])

    def test_max_limits_count(self):
        """返す個数は min(max, npc)。max が小さければ、ランクの高い側から残す。"""
        level = 1
        picks = [Resource.THINGS_BRONZE, Resource.BOLT_GOLD, Resource.STAR_SILVER]
        rands = [self.pick_rand(level, r) for r in picks]
        ret = Field(level=level, rand=fixed(*rands)).get_resources(npc=3, max=2)
        self.assertEqual(ret, [Resource.BOLT_GOLD, Resource.STAR_SILVER])
        ret = Field(level=level, rand=fixed(*rands)).get_resources(npc=3, max=5)
        self.assertEqual(len(ret), min(5, 3))

    def test_default_rand(self):
        """既定の乱数でも、npc 個がすべて出現するリソースで、ランクが増えない並びになる。"""
        field = Field(level=1)
        ret = field.get_resources(npc=3, max=3)
        self.assertEqual(len(ret), 3)
        for res in ret:
            self.assertIn(res, Resource.avails())
        for i in range(len(ret) - 1):
            self.assertGreaterEqual(
                Resource.get_rank(ret[i]), Resource.get_rank(ret[i + 1])
            )


class TestAttack(unittest.TestCase):
    """FR6: 攻撃 1 回分。"""

    def test_default_rand(self):
        """既定の乱数でも、敵の残数 + 破壊数 = 攻撃の前の残数（最大数）になる。"""
        field = Field(level=1)
        killed = field.attack(engine=1, gun=1)
        self.assertTrue(0 <= field.npc <= Field.MAX_NPC_NUM)
        self.assertTrue(0 <= killed <= Field.MAX_NPC_NUM)
        self.assertEqual(field.npc + killed, Field.MAX_NPC_NUM)

    def test_formula(self):
        """対象数 = min(敵の残数, 対象数の判定)、破壊数 = その対象数での破壊数の判定。"""
        for npc in (10, 3, 1):
            rand_target, rand_kill = 0.4, 0.7
            field = Field(level=2, rand=fixed(rand_target, rand_kill))
            field.npc = npc
            ref = Field(level=2, rand=fixed(rand_target, rand_kill))
            target = min(npc, ref.judge_target(power=2))
            expect = ref.judge_kill(power=3, npc=target)
            killed = field.attack(engine=2, gun=3)
            self.assertEqual(killed, expect)
            self.assertEqual(field.npc, npc - expect)

    def test_target_limited_by_remaining(self):
        """敵の残数が対象数の判定より少ないとき、破壊数は残数を超えない。"""
        field = Field(level=1, rand=fixed(0.0, 0.999999))
        field.npc = 1
        killed = field.attack(engine=4, gun=4)
        self.assertEqual(killed, 1)
        self.assertEqual(field.npc, 0)

    def test_no_enemy(self):
        """敵が 0 体なら、対象数が 0 になり、破壊数は 0 で、乱数は 1 回しか使わない。"""
        rand = fixed(0.5)
        field = Field(level=1, rand=rand)
        field.npc = 0
        self.assertEqual(field.attack(engine=4, gun=4), 0)
        self.assertEqual(field.npc, 0)
        self.assertEqual(len(rand.calls), 1)


class TestJudgeRepeat(unittest.TestCase):
    """FR7: 繰り返しの判定。"""

    def test_default_rand(self):
        """既定の乱数でも、True か False を返す。"""
        self.assertIn(Field().judge_repeat(power=1), [True, False])

    def test_boundary(self):
        """繰り返さない確率は 0.5^power。乱数がそれより小さければ False、境界以上なら True。"""
        for power in range(1, 5):
            stop = 0.5**power
            below = Field(rand=fixed(stop - 1e-9)).judge_repeat(power=power)
            at = Field(rand=fixed(stop)).judge_repeat(power=power)
            self.assertFalse(below)
            self.assertTrue(at)

    def test_high_level_repeats_more(self):
        """BODY のレベルが高いほど、繰り返しやすい。同じ乱数 0.3 で、レベル 1（0.5 未満）は終え、レベル 2（0.25 以上）は繰り返す。"""
        self.assertFalse(Field(rand=fixed(0.3)).judge_repeat(power=1))
        self.assertTrue(Field(rand=fixed(0.3)).judge_repeat(power=2))


if __name__ == "__main__":
    unittest.main()
