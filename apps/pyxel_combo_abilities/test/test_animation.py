"""AttackAnimation（攻撃の列を、フレームごとに再生する状態）のテスト。Pyxel は使わない。"""

import random
import unittest

from src import screen
from src.animation import AttackAnimation
from src.drawing import enemy_positions
from src.field import Field
from src.game import AttackStep

ATTACK_FRAMES = (
    screen.LAUNCH_FRAMES + screen.EXPLODE_FRAMES
)  # 破壊のある攻撃 1 回の所要


def make(steps, level=1):
    """固定の乱数で、待機中の敵の位置から始まる再生を作る。"""
    rand = random.Random(1).random
    return AttackAnimation(steps, level, enemy_positions(rand), rand=rand)


def tick_all(anim, limit=1000):
    """終わるまで進めて、進めたフレーム数を返す。"""
    frames = 0
    while not anim.done:
        anim.tick()
        frames += 1
        if frames >= limit:
            raise AssertionError("再生が終わらない")
    return frames


class TestStart(unittest.TestCase):
    """FR4.1: 開始時は、開始時のレベルの見た目で敵が最大数いる。"""

    def test_start_has_max_enemies_at_start_level(self):
        anim = make([AttackStep(1, False)], level=3)
        self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM)
        self.assertEqual(anim.level, 3)
        self.assertFalse(anim.done)
        self.assertEqual(anim.phase, "launch")

    def test_start_uses_given_positions(self):
        """ID-010 FR3.2: 開始時の敵の位置は、渡された位置（待機中に表示していたもの）のまま。"""
        positions = [(100 + i, 10 + i) for i in range(Field.MAX_NPC_NUM)]
        anim = AttackAnimation([AttackStep(1, False)], 1, positions)
        self.assertEqual(anim.positions, positions)
        self.assertIsNot(anim.positions, positions)  # 渡した列は書き換えない


class TestTiming(unittest.TestCase):
    """FR3.1・FR3.2: 発射と爆発のフレーム数。破壊数 0 は時間を使わない。"""

    def test_phases_per_attack(self):
        """破壊のある攻撃 1 回は、発射 → 爆発の順に、定数のフレーム数ずつ進む。"""
        anim = make([AttackStep(2, False)])
        phases = []
        while not anim.done:
            phases.append(anim.phase)
            anim.tick()
        self.assertEqual(
            phases,
            ["launch"] * screen.LAUNCH_FRAMES + ["explode"] * screen.EXPLODE_FRAMES,
        )
        self.assertIsNone(anim.phase)

    def test_zero_kill_takes_no_time(self):
        """破壊数 0 の攻撃だけなら、アニメーションなしで、最初から完了している。"""
        anim = make([AttackStep(0, False), AttackStep(0, False)])
        self.assertTrue(anim.done)
        self.assertIsNone(anim.phase)
        self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM)

    def test_total_frames_skip_zero_kill(self):
        """所要フレーム数は、破壊のある攻撃の数 × 1 回の所要（破壊数 0 は数えない）。"""
        steps = [AttackStep(1, False), AttackStep(0, False), AttackStep(1, False)]
        self.assertEqual(tick_all(make(steps)), 2 * ATTACK_FRAMES)


class TestEnemies(unittest.TestCase):
    """FR3.1・FR4.1: 爆発の始まりで、破壊数ぶんの敵が消える。"""

    def test_killed_enemies_disappear_at_explosion(self):
        killed = 3
        anim = make([AttackStep(killed, False)])
        for _ in range(screen.LAUNCH_FRAMES):
            self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM)  # 発射中は減らない
            self.assertEqual(anim.exploding, [])
            anim.tick()
        self.assertEqual(anim.phase, "explode")
        self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM - killed)
        self.assertEqual(len(anim.exploding), killed)  # 爆発の位置
        tick_all(anim)
        self.assertEqual(anim.exploding, [])

    def test_remaining_matches_field(self):
        """レベルアップなしで終えたとき、画面の敵の数は、フィールドの残数と一致する。"""
        steps = [AttackStep(4, False), AttackStep(3, False)]
        anim = make(steps)
        tick_all(anim)
        self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM - 4 - 3)

    def test_level_up_replaces_enemies(self):
        """全滅してレベルが上がったら、新しいレベルの見た目で敵を最大数、置き直す。"""
        anim = make(
            [AttackStep(Field.MAX_NPC_NUM, True), AttackStep(1, False)], level=1
        )
        for _ in range(ATTACK_FRAMES - 1):
            anim.tick()
        self.assertEqual(anim.level, 1)  # 爆発の終わりまでは、元のレベルの見た目
        anim.tick()
        self.assertEqual(anim.level, 2)
        self.assertEqual(len(anim.positions), Field.MAX_NPC_NUM)
        tick_all(anim)
        self.assertEqual(
            len(anim.positions), Field.MAX_NPC_NUM - 1
        )  # 新しい敵に 1 回攻撃


class TestAfterDone(unittest.TestCase):
    def test_tick_after_done_is_inert(self):
        anim = make([AttackStep(1, False)])
        tick_all(anim)
        positions = list(anim.positions)
        anim.tick()
        self.assertTrue(anim.done)
        self.assertEqual(anim.positions, positions)


if __name__ == "__main__":
    unittest.main()
