import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from attack import Attack  # pylint: disable=C0413
from unit import Unit  # pylint: disable=C0413
from movable import Side, Direct, Movable, UnitType  # pylint: disable=C0413


class TestAttack(unittest.TestCase):
    """Attack クラスのテスト（TDDサイクル1: 基本実装）"""

    def test_attack_init(self):
        """攻撃の初期化: 位置、方向、所属、生存状態が正しいこと"""
        test_cases = [
            # (x, side, expected_direct, description)
            (50, Side.PLAYER, Direct.RIGHT, UnitType.MIDDLE, "自軍攻撃(中位)"),
            (100, Side.ENEMY, Direct.LEFT, UnitType.MIDDLE, "敵軍攻撃"),
            (10, Side.PLAYER, Direct.RIGHT, UnitType.LOWER, "自軍攻撃(下位)"),
            (20, Side.PLAYER, Direct.RIGHT, UnitType.UPPER, "自軍攻撃(上位)"),
            (30, Side.PLAYER, Direct.RIGHT, UnitType.BASE, "自軍攻撃(拠点)"),
        ]
        for x, side, expected_direct, unit_type, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(x, side, unit_type, Movable.TILE_SIZE)
                self.assertEqual(attack.x, x)
                self.assertEqual(attack.side, side)
                self.assertEqual(attack.direct, expected_direct)
                self.assertTrue(attack.is_alive)
                self.assertEqual(attack.unit_type, unit_type)

    def test_attack_update(self):
        """攻撃の update 後: 移動と生存状態が正しいこと"""
        test_cases = [
            # (初期x, side, 期待x, 期待is_alive, description)
            (50, Side.PLAYER, 52, True, "自軍攻撃が右に移動"),
            (100, Side.ENEMY, 98, True, "敵軍攻撃が左に移動"),
            (148, Side.PLAYER, 150, False, "自軍攻撃が右端を超えて消滅"),
            (1, Side.ENEMY, -1, False, "敵軍攻撃が左端を超えて消滅"),
        ]
        for init_x, side, expected_x, expected_alive, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(init_x, side, UnitType.MIDDLE, Movable.TILE_SIZE)
                attack.update()
                self.assertEqual(attack.x, expected_x)
                self.assertEqual(attack.is_alive, expected_alive)

    def test_attack_visible(self):
        """攻撃移動距離がユニット幅より小さい時には表示される"""
        attack = Attack(0, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        self.assertTrue(attack.is_visible)
        for _ in range(int(Unit.TILE_SIZE // Attack.SPEED) - 1):
            attack.update()
        self.assertTrue(attack.is_visible)
        attack.update()
        self.assertFalse(attack.is_visible)

    def test_attack_init_with_range(self):
        """range を指定した値がそのまま保持されること"""
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, 15)
        self.assertEqual(attack.range, 15)

        attack_tile = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        self.assertEqual(attack_tile.range, Movable.TILE_SIZE)

    def test_attack_visible_with_range(self):
        """range=12 の場合、_moved >= 12 で is_visible が False になること"""
        attack = Attack(0, Side.PLAYER, UnitType.MIDDLE, 12)
        for _ in range(5):
            attack.update()
        self.assertTrue(attack.is_visible)   # _moved=10 < 12
        attack.update()
        self.assertFalse(attack.is_visible)  # _moved=12 >= 12


class TestAttackCollision(unittest.TestCase):
    """Attack と Unit の当たり判定テスト（TDDサイクル3）"""

    def test_attack_hits_enemy_unit(self):
        """攻撃が敵ユニットに当たる（同じ位置で対抗陣営）"""
        test_cases = [
            (Side.PLAYER, Side.ENEMY, "自軍攻撃→敵ユニット"),
            (Side.ENEMY, Side.PLAYER, "敵軍攻撃→自軍ユニット"),
        ]
        for attack_side, unit_side, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(50, attack_side, UnitType.MIDDLE, Movable.TILE_SIZE)
                unit = Unit(unit_side, UnitType.MIDDLE, x=50)
                self.assertTrue(attack.is_hitting(unit))

    def test_attack_does_not_hit_ally(self):
        """攻撃は味方ユニットに当たらない"""
        test_cases = [
            (Side.PLAYER, "自軍攻撃→自軍ユニット"),
            (Side.ENEMY, "敵軍攻撃→敵軍ユニット"),
        ]
        for side, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(50, side, UnitType.MIDDLE, Movable.TILE_SIZE)
                unit = Unit(side, UnitType.MIDDLE, x=50)
                self.assertFalse(attack.is_hitting(unit))

    def test_attack_hit_range(self):
        """当たり判定の範囲: タイルサイズ未満なら命中、以上なら外れ"""
        tile_size = Movable.TILE_SIZE  # 8
        test_cases = [
            # (attack_x, unit_x, expected_hit, description)
            (50, 50, True, "距離0: 完全に重なる"),
            (50, 50 + tile_size - 1, True, "距離7: 境界（命中）"),
            (50, 50 + tile_size, False, "距離8: 境界（外れ）"),
            (50, 50 - tile_size + 1, True, "距離-7: 逆方向境界（命中）"),
            (50, 50 - tile_size, False, "距離-8: 逆方向境界（外れ）"),
        ]
        for attack_x, unit_x, expected_hit, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(attack_x, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
                unit = Unit(Side.ENEMY, UnitType.MIDDLE, x=unit_x)
                self.assertEqual(attack.is_hitting(unit), expected_hit)

    def test_attack_hit_range_with_range(self):
        """当たり判定が range に基づくこと: range=15 で距離14は命中、距離15は外れ"""
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, 15)
        unit_near = Unit(Side.ENEMY, UnitType.MIDDLE, x=50 + 14)
        unit_far = Unit(Side.ENEMY, UnitType.MIDDLE, x=50 + 15)
        self.assertTrue(attack.is_hitting(unit_near))   # 距離14 < 15
        self.assertFalse(attack.is_hitting(unit_far))   # 距離15 >= 15

    def test_attack_no_hit_after_deactivate(self):
        """無効化済みの攻撃は当たり判定の対象外"""
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        unit = Unit(Side.ENEMY, UnitType.MIDDLE, x=50)
        attack.deactivate()
        self.assertFalse(attack.is_hitting(unit))

    def test_attack_no_hit_after_damaged(self):
        """被弾中のユニットへの攻撃は当たり判定の対象外"""
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        unit = Unit(Side.ENEMY, UnitType.MIDDLE, x=50)
        unit.take_damage()
        self.assertFalse(attack.is_hitting(unit))

    def test_attack_no_hit_after_invisible(self):
        """不可視攻撃は当たり判定の対象外"""
        tile_size = Movable.TILE_SIZE  # 8
        test_cases = [
            # (times, unit_x, expected_hit, description)
            (0, 50, True, "移動なし: あたる"),
            (0, 50 + tile_size - 1, True, "移動なし、リーチ内: あたる"),
            (
                0,
                50 + tile_size - 1 + int(Attack.SPEED * 3),
                False,
                "移動なし、リーチ外: あたらない",
            ),
            (
                3,
                50 + tile_size - 1 + int(Attack.SPEED * 3),
                True,
                "移動あり、リーチ内: あたる",
            ),
            (
                4,
                50 + tile_size - 1 + int(Attack.SPEED * 3),
                False,
                "移動あり、消失、リーチ内: あたらない",
            ),
        ]
        for times, unit_x, expected_hit, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
                unit = Unit(Side.ENEMY, UnitType.MIDDLE, x=unit_x)
                for _ in range(times):
                    attack.update()
                self.assertEqual(attack.is_hitting(unit), expected_hit)

    def test_attack_deactivate_kills_attack(self):
        """deactivate() で攻撃は消滅する（is_alive が False）"""
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        self.assertTrue(attack.is_alive)
        attack.deactivate()
        self.assertFalse(attack.is_alive)


class TestAttackProgress(unittest.TestCase):
    """Attack の progress プロパティテスト（TDDサイクル5: 描画用）"""

    def test_attack_progress(self):
        """progressは移動距離 / range で消失までの進捗割合を返す（デフォルトrange=TILE_SIZE）"""
        default_range = Movable.TILE_SIZE
        test_cases = [
            # (update回数, 期待progress, description)
            (0, 0.0, "初期状態: 0.0"),
            (1, Attack.SPEED / default_range, "1回更新: 0.25"),
            (2, Attack.SPEED * 2 / default_range, "2回更新: 0.5"),
            (3, Attack.SPEED * 3 / default_range, "3回更新: 0.75"),
        ]
        for updates, expected_progress, desc in test_cases:
            with self.subTest(desc=desc):
                attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
                for _ in range(updates):
                    attack.update()
                self.assertAlmostEqual(attack.progress, expected_progress)


if __name__ == "__main__":
    unittest.main()
