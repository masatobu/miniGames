"""攻撃のアニメーション（攻撃の列をフレームごとに再生する状態。Pyxel に依存しない）。"""

import random

try:
    from . import screen  # pylint: disable=C0413
    from .drawing import enemy_positions  # pylint: disable=C0413
except ImportError:
    import screen  # pylint: disable=C0413
    from drawing import enemy_positions  # pylint: disable=C0413

LAUNCH = "launch"
EXPLODE = "explode"


class AttackAnimation:
    """攻撃 1 回ごとの結果（AttackStep）の列を、1 フレームずつ再生する。

    破壊数が 1 以上の攻撃ごとに、発射（LAUNCH_FRAMES）→ 爆発（EXPLODE_FRAMES）と進む。
    破壊数 0 の攻撃は時間を使わない。爆発の始まりで、破壊数ぶんの敵（ランダム）が
    positions から exploding に移り、爆発の終わりで消える。レベルアップした攻撃の
    爆発が終わったら、level を 1 上げて、敵を最大数、置き直す。

    positions は、攻撃の前に（待機中に）表示していた敵の位置。そこから始める。

    読み取り用: phase（LAUNCH・EXPLODE・再生していなければ None）、positions（敵の位置）、
    exploding（爆発中の敵の位置）、level（敵の見た目のレベル）、done（再生し終えたか）。
    """

    def __init__(self, steps, level, positions, rand=random.random):
        self.level = level
        self.rand = rand
        self.positions = list(positions)
        self.exploding = []
        self.phase = None
        self.frame = 0
        self._steps = list(steps)
        self._step = None
        self._next_step()

    @property
    def done(self):
        """再生し終えたか。"""
        return self.phase is None

    def tick(self):
        """1 フレーム進める。再生し終えていれば何もしない。"""
        if self.done:
            return
        self.frame += 1
        if self.phase == LAUNCH and self.frame >= screen.LAUNCH_FRAMES:
            self._explode()
        elif self.phase == EXPLODE and self.frame >= screen.EXPLODE_FRAMES:
            self._finish_step()

    def _next_step(self):
        """破壊数が 1 以上の次の攻撃から発射を始める。無ければ再生を終える。"""
        self._step = None
        while self._steps and self._step is None:
            step = self._steps.pop(0)
            if step.killed > 0:
                self._step = step
        self.phase = LAUNCH if self._step else None
        self.frame = 0

    def _explode(self):
        """爆発を始める。破壊数ぶんの敵をランダムに選んで exploding に移す。"""
        self.phase = EXPLODE
        self.frame = 0
        for _ in range(self._step.killed):
            index = int(self.rand() * len(self.positions))
            self.exploding.append(self.positions.pop(index))

    def _finish_step(self):
        """爆発を終える。レベルアップしていれば、敵を置き直して次の攻撃へ進む。"""
        self.exploding = []
        if self._step.leveled_up:
            self.level += 1
            self.positions = enemy_positions(self.rand)
        self._next_step()
