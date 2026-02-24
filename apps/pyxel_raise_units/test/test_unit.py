import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from unit import Unit  # pylint: disable=C0413
from attack import Attack  # pylint: disable=C0413
from movable import Direct, Movable, Side, UnitType  # pylint: disable=C0413


class TestUnit(unittest.TestCase):
    def test_unit_with_direct_and_position(self):
        """ユニットは所属に応じた向きと位置を持つ"""
        test_cases = [
            ("player", Side.PLAYER, Direct.RIGHT, 0),
            (
                "enemy",
                Side.ENEMY,
                Direct.LEFT,
                150 - 8,
            ),  # SPAWN_X_ENEMY = 画面幅 - ユニット幅
        ]
        for case_name, side, direct, start_x in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                self.assertEqual(unit._side, side)  # pylint: disable=W0212
                self.assertEqual(unit._direct, direct)  # pylint: disable=W0212
                self.assertEqual(unit.hp, 3)
                self.assertEqual(unit._speed, 0.5)  # pylint: disable=W0212
                self.assertEqual(unit._range, 15)  # pylint: disable=W0212
                self.assertEqual(unit._interval, 30)  # pylint: disable=W0212
                self.assertEqual(unit.x, start_x)
                self.assertEqual(unit.unit_type, UnitType.MIDDLE)

    def test_unit_with_parameters(self):
        """ユニットはタイプに応じた各属性を持つ"""
        test_cases = [
            ("middle", UnitType.MIDDLE, 3, 0.5, 15, 30),
            ("lower", UnitType.LOWER, 1, 0.8, 12, 20),
            ("upper", UnitType.UPPER, 10, 0.3, 25, 60),
            ("base", UnitType.BASE, 20, 0.0, 30, 40),
        ]
        for case_name, unit_type, hp, speed, range_, interval in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(Side.PLAYER, unit_type=unit_type)
                self.assertEqual(unit._side, Side.PLAYER)  # pylint: disable=W0212
                self.assertEqual(unit._direct, Direct.RIGHT)  # pylint: disable=W0212
                self.assertEqual(unit.hp, hp)
                self.assertEqual(unit._speed, speed)  # pylint: disable=W0212
                self.assertEqual(unit._interval, interval)  # pylint: disable=W0212
                self.assertEqual(unit._range, range_)  # pylint: disable=W0212
                self.assertEqual(unit.x, 0)
                self.assertEqual(unit.unit_type, unit_type)

    def test_unit_move(self):
        """ユニットは前進できる"""
        test_cases = [
            ("player 1 time", Side.PLAYER, 1, 0),
            ("enemy 1 time", Side.ENEMY, 1, 141),  # 142 - 0.5 = 141.5 → 141
            ("player 2 times", Side.PLAYER, 2, 1),
            ("enemy 2 times", Side.ENEMY, 2, 141),  # 142 - 1.0 = 141.0 → 141
            ("player 10 times", Side.PLAYER, 10, 5),
            ("enemy 10 times", Side.ENEMY, 10, 137),  # 142 - 5.0 = 137.0 → 137
            ("player 0 time", Side.PLAYER, 0, 0),
            ("enemy 0 time", Side.ENEMY, 0, 142),  # SPAWN_X_ENEMY = 画面幅 - ユニット幅
        ]
        for case_name, side, time, end_x in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                for _ in range(time):
                    unit.update()
                self.assertEqual(unit.x, end_x)

    def test_base_unit_does_not_move(self):
        """拠点ユニット(speed=0)は update() を複数回実行しても位置が変わらない"""
        test_cases = [
            ("player base at x=0", Side.PLAYER, 0, None),
            ("enemy base at x=142", Side.ENEMY, 142, 142),
        ]
        for case_name, side, expected_x, init_x in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.BASE, x=init_x)
                for _ in range(10):
                    unit.update()
                self.assertEqual(unit.x, expected_x)

    def test_unit_face(self):
        """ユニットの顔の向きを取得できる（自軍は右向き、敵軍は左向き）"""
        test_cases = [
            ("player faces right", Side.PLAYER, Direct.RIGHT),
            ("enemy faces left", Side.ENEMY, Direct.LEFT),
        ]
        for case_name, side, expected_face in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                self.assertEqual(unit.face, expected_face)

    def test_unit_direct_when_moving(self):
        """移動中のユニットは移動方向を返す"""
        test_cases = [
            ("player moving right", Side.PLAYER, Direct.RIGHT),
            ("enemy moving left", Side.ENEMY, Direct.LEFT),
        ]
        for case_name, side, expected_direct in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                self.assertEqual(unit.direct, expected_direct)

    def test_unit_direct_by_opponent(self):
        """敵の最前列の位置によってユニットの移動方向が変わる"""
        test_cases = [
            ("player move", Side.PLAYER, 50, 100, Direct.RIGHT),
            ("player edge move", Side.PLAYER, 50, 66, Direct.RIGHT),
            ("player edge stop", Side.PLAYER, 50, 65, Direct.NEUTRAL),
            ("enemy move", Side.ENEMY, 100, 50, Direct.LEFT),
            ("enemy edge move", Side.ENEMY, 66, 50, Direct.LEFT),
            ("enemy edge stop", Side.ENEMY, 65, 50, Direct.NEUTRAL),
        ]
        for case_name, side, self_x, opponent_x, expected_direct in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                unit._x = self_x  # pylint: disable=W0212
                unit.set_opponent_head_x(opponent_x)
                unit.update()
                self.assertEqual(unit.direct, expected_direct)

    def test_unit_direct_reset(self):
        """敵の最前列の状態が変わるとユニットの移動方向も変わる"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        unit._x = 50  # pylint: disable=W0212
        unit.set_opponent_head_x(60)
        unit.update()
        self.assertEqual(unit.direct, Direct.NEUTRAL)
        unit.set_opponent_head_x(100)
        unit.update()
        self.assertEqual(unit.direct, Direct.RIGHT)

    def test_unit_direct_uses_range(self):
        """停止距離はユニットのrangeに基づく（ハードコードではない）"""
        # _rangeを変更した場合、停止距離もそれに応じて変わることを検証
        test_cases = [
            # (case_name, side, self_x, range_value, opponent_x, expected_direct)
            # 距離 > range なら移動、距離 <= range なら停止
            ("player range20 stop", Side.PLAYER, 50, 20, 70, Direct.NEUTRAL),  # 距離20
            ("player range20 move", Side.PLAYER, 50, 20, 71, Direct.RIGHT),  # 距離21
            ("enemy range20 stop", Side.ENEMY, 70, 20, 50, Direct.NEUTRAL),  # 距離20
            ("enemy range20 move", Side.ENEMY, 71, 20, 50, Direct.LEFT),  # 距離21
        ]
        for (
            case_name,
            side,
            self_x,
            range_value,
            opponent_x,
            expected_direct,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                unit._x = self_x  # pylint: disable=W0212
                unit._range = range_value  # pylint: disable=W0212
                unit.set_opponent_head_x(opponent_x)
                unit.update()
                self.assertEqual(unit.direct, expected_direct)

    def test_damaged_state(self):
        """被弾状態はフレーム数に応じて変化する"""
        test_cases = [
            # (case_name, side, take_damage, update_count, expected_is_damaged)
            ("initial_player", Side.PLAYER, False, 0, False),
            ("initial_enemy", Side.ENEMY, False, 0, False),
            ("after_take_damage", Side.PLAYER, True, 0, True),
            ("after_9_updates", Side.PLAYER, True, 9, True),
            ("after_10_updates", Side.PLAYER, True, 10, False),
        ]
        for case_name, side, take_damage, update_count, expected in test_cases:
            with self.subTest(case_name=case_name):
                unit = Unit(side, UnitType.MIDDLE)
                if take_damage:
                    unit.take_damage()
                for _ in range(update_count):
                    unit.update()
                self.assertEqual(unit.is_damaged, expected)

    def test_retake_damage_resets_counter(self):
        """被弾中に再被弾すると、そこから10フレーム被弾状態が続く"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        unit.take_damage()

        # 5フレーム経過（残り5フレーム）
        for _ in range(5):
            unit.update()
        self.assertTrue(unit.is_damaged)

        # 再被弾（カウンターが10にリセット）
        unit.take_damage()

        # 9フレーム経過してもまだ被弾中
        for _ in range(9):
            unit.update()
        self.assertTrue(unit.is_damaged)

        # 10フレーム目で被弾解除
        unit.update()
        self.assertFalse(unit.is_damaged)


class TestUnitAttackGeneration(unittest.TestCase):
    """Unit からの攻撃生成テスト（TDDサイクル2）"""

    def _make_combat_unit(self, side=Side.PLAYER):
        """戦闘状態のユニットを生成するヘルパー"""
        unit = Unit(side, UnitType.MIDDLE, x=50)
        if side == Side.PLAYER:
            unit.set_opponent_head_x(60)  # 距離10 < RANGE(15) → 戦闘状態
        else:
            unit.set_opponent_head_x(40)  # 距離10 < RANGE(15) → 戦闘状態
        unit.update()  # _update_direct() で NEUTRAL に
        return unit

    def test_unit_can_attack_when_in_combat(self):
        """戦闘状態で攻撃可能（初回は即座に攻撃可能）"""
        test_cases = [
            (Side.PLAYER, "自軍ユニット"),
            (Side.ENEMY, "敵軍ユニット"),
        ]
        for side, desc in test_cases:
            with self.subTest(desc=desc):
                unit = self._make_combat_unit(side)
                self.assertEqual(unit.direct, Direct.NEUTRAL)
                self.assertTrue(unit.can_attack)

    def test_unit_cannot_attack_when_moving(self):
        """移動中は攻撃不可"""
        test_cases = [
            (Side.PLAYER, "自軍ユニット"),
            (Side.ENEMY, "敵軍ユニット"),
        ]
        for side, desc in test_cases:
            with self.subTest(desc=desc):
                unit = Unit(side, UnitType.MIDDLE)  # opponent未設定→移動中
                unit.update()
                self.assertNotEqual(unit.direct, Direct.NEUTRAL)
                self.assertFalse(unit.can_attack)

    def test_unit_attack_cooldown_resets(self):
        """攻撃後にクールダウンがリセットされ、INTERVAL経過後に再攻撃可能"""
        unit = self._make_combat_unit()
        self.assertTrue(unit.can_attack)

        # 攻撃生成 → クールダウン開始
        unit.create_attack()
        self.assertFalse(unit.can_attack)

        # INTERVAL - 1 回更新してもまだ攻撃不可
        interval = Unit.TYPE_PARAMS[UnitType.MIDDLE].interval
        for _ in range(interval - 1):
            unit.update()
        self.assertFalse(unit.can_attack)

        # INTERVAL 回目の更新で攻撃可能に
        unit.update()
        self.assertTrue(unit.can_attack)

    def test_unit_create_attack_returns_attack(self):
        """create_attack() が正しい位置と所属の Attack インスタンスを返す"""
        tile_size = 8  # ユニット幅（8x8px）
        test_cases = [
            # (side, expected_offset, description)
            (Side.PLAYER, tile_size, "自軍: 右方向にタイル幅分オフセット"),
            (Side.ENEMY, -tile_size, "敵軍: 左方向にタイル幅分オフセット"),
        ]
        for side, offset, desc in test_cases:
            with self.subTest(desc=desc):
                unit = self._make_combat_unit(side)
                attack = unit.create_attack()
                self.assertIsInstance(attack, Attack)
                self.assertEqual(attack.x, unit.x + offset)
                self.assertEqual(attack.side, side)

    def test_unit_create_attack_returns_attack_with_unit_type(self):
        """create_attack() が正しいユニットタイプの Attack インスタンスを返す"""
        test_cases = [
            # (side, expected_offset, description)
            (UnitType.MIDDLE, "中位"),
            (UnitType.LOWER, "下位"),
            (UnitType.UPPER, "上位"),
            (UnitType.BASE, "拠点"),
        ]
        for unit_type, desc in test_cases:
            with self.subTest(desc=desc):
                unit = Unit(Side.PLAYER, unit_type=unit_type)
                attack = unit.create_attack()
                self.assertIsInstance(attack, Attack)
                self.assertEqual(attack.unit_type, unit_type)

    def test_create_attack_uses_attack_range_formula(self):
        """create_attack() が Unit._range - TILE_SIZE + 1 を Attack.range に使用する"""
        test_cases = [
            (UnitType.MIDDLE, "中位ユニット"),
            (UnitType.LOWER, "下位ユニット"),
            (UnitType.UPPER, "上位ユニット"),
            (UnitType.BASE, "拠点ユニット"),
        ]
        for unit_type, desc in test_cases:
            with self.subTest(desc=desc):
                unit_range = Unit.TYPE_PARAMS[unit_type].range
                expected_attack_range = unit_range - Movable.TILE_SIZE + 1
                unit = Unit(Side.PLAYER, unit_type)
                # 戦闘状態にする（Unit._range - 1 だけ離れた位置に相手を設置）
                unit.set_opponent_head_x(unit.x + unit_range - 1)
                unit.update()
                attack = unit.create_attack()
                self.assertEqual(attack.range, expected_attack_range)


class TestUnitDamage(unittest.TestCase):
    """Unit のダメージ処理テスト（TDDサイクル3）"""

    def test_unit_take_damage_reduces_hp(self):
        """take_damage() で HP が 1 減少する"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        max_hp = Unit.TYPE_PARAMS[UnitType.MIDDLE].hp
        unit.take_damage()
        self.assertEqual(unit.hp, max_hp - 1)  # 3 → 2

    def test_unit_take_damage_multiple(self):
        """複数回のダメージで HP が段階的に減少する"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        max_hp = Unit.TYPE_PARAMS[UnitType.MIDDLE].hp
        for i in range(1, max_hp + 1):
            unit.take_damage()
            self.assertEqual(unit.hp, max_hp - i)

    def test_unit_is_alive_initial(self):
        """ユニットは生成時に生存している"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        self.assertTrue(unit.is_alive)

    def test_unit_dies_when_hp_zero(self):
        """HP が 0 になると is_alive が False"""
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        max_hp = Unit.TYPE_PARAMS[UnitType.MIDDLE].hp
        for _ in range(max_hp):
            self.assertTrue(unit.is_alive)
            unit.take_damage()
        self.assertFalse(unit.is_alive)
