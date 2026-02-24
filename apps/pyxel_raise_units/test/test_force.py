import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from unit import Unit  # pylint: disable=C0413
from movable import Direct, Movable, Side, UnitType  # pylint: disable=C0413
from force import Force, EnemyStrategy  # pylint: disable=C0413
from attack import Attack  # pylint: disable=C0413


class TestForce(unittest.TestCase):
    def test_get_head_x(self):
        """軍の先頭位置を取得"""
        test_cases = [
            ("player unit set 100", Side.PLAYER, [100], 100),
            ("player unit set 50", Side.PLAYER, [50], 50),
            ("player 2 units", Side.PLAYER, [100, 50], 100),
            ("enemy 2 units", Side.ENEMY, [100, 50], 50),
            ("player 0 units", Side.PLAYER, [], None),
            ("enemy 0 units", Side.ENEMY, [], None),
        ]
        for case_name, side, x_list, head_x in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                units = []
                for x in x_list:
                    unit = Unit(side, UnitType.MIDDLE)
                    unit._x = x  # pylint: disable=W0212
                    units.append(unit)
                force._units = units  # pylint: disable=W0212
                self.assertEqual(force.get_head_x(), head_x)

    def test_set_opponent_head_x(self):
        """敵軍の先頭位置を設定"""
        test_cases = [
            ("player force encount", Side.PLAYER, {100: Direct.NEUTRAL}, 108),
            ("enemy force encount", Side.ENEMY, {108: Direct.NEUTRAL}, 100),
            (
                "player 2 units",
                Side.PLAYER,
                {100: Direct.NEUTRAL, 50: Direct.RIGHT},
                108,
            ),
            ("enemy 2 units", Side.ENEMY, {108: Direct.NEUTRAL, 120: Direct.LEFT}, 100),
            ("player 0 units", Side.PLAYER, [], 100),
            ("enemy 0 units", Side.ENEMY, [], 100),
        ]
        for case_name, side, direct_map, head_x in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                units = []
                for x in direct_map:
                    unit = Unit(side, UnitType.MIDDLE)
                    unit._x = x  # pylint: disable=W0212
                    units.append(unit)
                force._units = units  # pylint: disable=W0212
                force.set_opponent_head_x(head_x)
                force.update()
                for unit in force.units:
                    unit_x = (
                        unit.x + 1
                        if side == Side.ENEMY and unit.direct == Direct.LEFT
                        else unit.x
                    )
                    self.assertEqual(unit.direct, direct_map[unit_x])

    def test_get_attacks(self):
        """攻撃リストを取得"""
        test_cases = [
            ("2 player units", Side.PLAYER, 2, 65, 2),
            ("2 enemy units", Side.ENEMY, 2, 35, 2),
            ("1 player unit", Side.PLAYER, 1, 65, 1),
            ("no units", Side.PLAYER, 0, 65, 0),
            ("far units", Side.PLAYER, 3, 66, 0),
        ]
        for case_name, side, num, head_x, expected_attacks in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                units = []
                for _ in range(num):
                    unit = Unit(side, UnitType.MIDDLE)
                    unit._x = 50  # pylint: disable=W0212
                    units.append(unit)
                force._units = units  # pylint: disable=W0212
                force.set_opponent_head_x(head_x)
                self.assertEqual(len(force.attacks), 0)
                force.update()
                self.assertEqual(len(force.attacks), expected_attacks)

    def test_update_attacks_deletion(self):
        """不可視攻撃がリストから削除される"""
        force = Force(Side.PLAYER)
        units = []
        for _ in range(2):
            unit = Unit(Side.PLAYER, UnitType.MIDDLE)
            unit._x = 50  # pylint: disable=W0212
            units.append(unit)
        force._units = units  # pylint: disable=W0212
        force.set_opponent_head_x(65)
        self.assertEqual(len(force.attacks), 0)
        force.update()
        self.assertEqual(len(force.attacks), 2)
        # MIDDLE の attack_range = unit_range - TILE_SIZE + 1 = 15 - 8 + 1 = 8
        # 攻撃は生成後の次updateから移動開始: speed=2.0 → 5回更新で _moved=8 >= 8 となり不可視
        for _ in range(3):
            force.update()
        self.assertEqual(len(force.attacks), 2)
        force.update()
        self.assertEqual(len(force.attacks), 0)

    def test_take_damage(self):
        """軍のユニットが攻撃を受ける"""
        test_cases = [
            ("1 player unit by 1 attack", Side.PLAYER, [50], [57], [0], [0]),
            ("1 enemy unit by 1 attack", Side.ENEMY, [50], [43], [0], [0]),
            ("2 player units by 1 attack", Side.PLAYER, [50, 50], [57], [0], [0]),
            (
                "2 player units by 2 attack",
                Side.PLAYER,
                [50, 50],
                [57, 57],
                [0, 1],
                [0, 1],
            ),
            ("1 player units by 2 attack", Side.PLAYER, [50], [57, 57], [0], [0]),
            ("no units by no attack", Side.PLAYER, [], [], [], []),
        ]
        for (
            case_name,
            side,
            unit_x_list,
            attack_x_list,
            expected_damaged_unit_ids,
            expected_disable_attack_ids,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                units = []
                for x in unit_x_list:
                    unit = Unit(side, UnitType.MIDDLE)
                    unit._x = x  # pylint: disable=W0212
                    units.append(unit)
                force._units = units  # pylint: disable=W0212
                opposite = Side.ENEMY if side == Side.PLAYER else Side.PLAYER
                attacks = []
                for x in attack_x_list:
                    attack = Attack(x, opposite, UnitType.MIDDLE, Movable.TILE_SIZE)
                    attacks.append(attack)

                max_hp = Unit.TYPE_PARAMS[UnitType.MIDDLE].hp
                for unit in units:
                    self.assertEqual(unit.hp, max_hp)
                for attack in attacks:
                    self.assertTrue(attack.is_alive)
                force.take_damage(attacks)
                for i, unit in enumerate(units):
                    expected_hp = (
                        (max_hp - 1) if i in expected_damaged_unit_ids else max_hp
                    )
                    self.assertEqual(unit.hp, expected_hp)
                for i, attack in enumerate(attacks):
                    expected_is_alive = i not in expected_disable_attack_ids
                    self.assertEqual(attack.is_alive, expected_is_alive)

    def test_update_unit_killed(self):
        """軍のユニットが攻撃を受けて死亡する"""
        force = Force(Side.PLAYER)
        units = []
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        unit._x = 50  # pylint: disable=W0212
        units.append(unit)
        force._units = units  # pylint: disable=W0212

        # DAMAGED_FRAMES=10, speed=0.5 → 1区間で5px移動
        # 各攻撃を7px先（TILE_SIZE=8未満）に配置して確実にヒットさせる
        for i, attack_x in enumerate([57, 62, 67]):
            attacks = []
            attack = Attack(attack_x, Side.ENEMY, UnitType.MIDDLE, Movable.TILE_SIZE)
            attacks.append(attack)
            force.take_damage(attacks)
            self.assertEqual(
                len(force.units), 1, f"after {i+1} attack(s), unit should be alive"
            )
            for _ in range(Unit.DAMAGED_FRAMES):
                force.update()
        self.assertEqual(len(force.units), 0)

    def test_auto_put_unit(self):
        """自動スポーンはSideとフレーム数に応じてユニットを追加する"""
        interval = Force.AUTO_PUT_INTERVAL
        test_cases = [
            ("enemy after interval", Side.ENEMY, interval, 1),
            ("enemy before interval", Side.ENEMY, interval - 1, 0),
            ("enemy multiple spawns", Side.ENEMY, interval * 2, 2),
            ("player no spawn", Side.PLAYER, interval, 0),
        ]
        for case_name, side, update_count, expected_added in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                # auto-spawn が fund 不足で失敗しないよう十分な fund を設定
                # UPPER コスト60: 2回スポーンには初期200以上必要（資金+6/cycle）
                force._fund = 200  # pylint: disable=W0212
                initial_count = len(force.units)
                for _ in range(update_count):
                    force.update()
                self.assertEqual(len(force.units), initial_count + expected_added)

    def test_base_unit_placed_at_init(self):
        """Force初期化時に拠点ユニットのみが自動配置される"""
        test_cases = [
            ("player base at x=0", Side.PLAYER, 0),
            ("enemy base at x=142", Side.ENEMY, 150 - 8),  # 画面幅 - ユニット幅
        ]
        for case_name, side, expected_x in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                self.assertEqual(len(force.units), 1)
                self.assertEqual(force.units[0].unit_type, UnitType.BASE)
                self.assertEqual(force.units[0].x, expected_x)

    def test_is_base_destroyed(self):
        """拠点ユニット撃破の検知（生存拠点ユニット数が1以上かどうかで判定）"""
        test_cases = [
            ("alive base 1", 1, False),
            ("alive base 0", 0, True),
        ]
        for case_name, alive_base_count, expected in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(Side.PLAYER)
                force._units = [  # pylint: disable=W0212
                    Unit(Side.PLAYER, UnitType.BASE) for _ in range(alive_base_count)
                ]
                self.assertEqual(force.is_base_destroyed, expected)

    def test_put_unit(self):
        """put_unit() で fund が充分なときユニットが追加される"""
        test_cases = [
            ("player put middle", Side.PLAYER, UnitType.MIDDLE),
            ("enemy put middle", Side.ENEMY, UnitType.MIDDLE),
            ("put lower", Side.PLAYER, UnitType.LOWER),
            ("put upper", Side.PLAYER, UnitType.UPPER),
            ("put base", Side.PLAYER, UnitType.BASE),
        ]
        for case_name, side, unit_type in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(side)
                # fund を十分に設定（BASE は不要だが harm なし）
                force._fund = 100  # pylint: disable=W0212
                initial_count = len(force.units)
                force.put_unit(unit_type=unit_type)
                self.assertEqual(len(force.units), initial_count + 1)
                self.assertEqual(force.units[-1].unit_type, unit_type)
                self.assertEqual(force.units[-1].side, side)

    def test_put_unit_with_fund(self):
        """put_unit(): fund 充分なら消費してスポーン(True)、不足なら何もしない(False)"""
        test_cases = [
            # (ケース名, unit_type, 初期 fund, 期待スポーン数増加, 期待 fund 後, 期待戻り値)
            (
                "sufficient: LOWER",
                UnitType.LOWER,
                Force.SPAWN_COST[UnitType.LOWER],
                1,
                0,
                True,
            ),
            (
                "sufficient: MIDDLE",
                UnitType.MIDDLE,
                Force.SPAWN_COST[UnitType.MIDDLE],
                1,
                0,
                True,
            ),
            (
                "sufficient: UPPER",
                UnitType.UPPER,
                Force.SPAWN_COST[UnitType.UPPER],
                1,
                0,
                True,
            ),
            (
                "surplus: MIDDLE",
                UnitType.MIDDLE,
                Force.SPAWN_COST[UnitType.MIDDLE] + 3,
                1,
                3,
                True,
            ),
            (
                "insufficient: LOWER by 1",
                UnitType.LOWER,
                Force.SPAWN_COST[UnitType.LOWER] - 1,
                0,
                Force.SPAWN_COST[UnitType.LOWER] - 1,
                False,
            ),
            (
                "insufficient: zero fund",
                UnitType.MIDDLE,
                0,
                0,
                0,
                False,
            ),
            (
                "BASE: no cost",
                UnitType.BASE,
                0,
                1,
                0,
                True,
            ),
        ]
        for (
            case_name,
            unit_type,
            initial_fund,
            expected_delta,
            expected_fund,
            expected_result,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(Side.PLAYER)
                initial_count = len(force.units)
                force._fund = initial_fund  # pylint: disable=W0212
                result = force.put_unit(unit_type)
                self.assertEqual(result, expected_result, case_name)
                self.assertEqual(
                    len(force.units), initial_count + expected_delta, case_name
                )
                self.assertEqual(force.fund, expected_fund, case_name)

    def test_auto_spawn_sequence_until_all_types(self):
        """CYCLE 戦略: 資金不足スキップと全ユニットタイプのスポーンを検証（UPPER 成功まで）

        スポーン失敗時はインデックスを進めず同じユニットを再試行するため、
        資金が積み上がれば UPPER も自然にスポーンできる。
        FUND_INTERVAL=5, FUND_ADD=1, AUTO_PUT_INTERVAL=30 → 1サイクルで資金+6
        スポーン試行順: LOWER(10)→MIDDLE(25)→UPPER(60)→LOWER→...（成功時のみ進む）
        """
        force = Force(Side.ENEMY, strategy=EnemyStrategy.CYCLE)
        interval = Force.AUTO_PUT_INTERVAL
        # (累積スポーン数, スポーンされた種別 or None=スキップ)
        expected = [
            (0, None),  # cycle  1: fund  0+6=6,   LOWER(10) 失敗, fund=6
            (1, UnitType.LOWER),  # cycle  2: fund  6+6=12,  LOWER(10) 成功, fund=2
            (1, None),  # cycle  3: fund  2+6=8,   MIDDLE(25) 失敗, fund=8
            (1, None),  # cycle  4: fund  8+6=14,  MIDDLE(25) 失敗, fund=14
            (1, None),  # cycle  5: fund 14+6=20,  MIDDLE(25) 失敗, fund=20
            (2, UnitType.MIDDLE),  # cycle  6: fund 20+6=26,  MIDDLE(25) 成功, fund=1
            (2, None),  # cycle  7: fund  1+6=7,   UPPER(60) 失敗, fund=7
            (2, None),  # cycle  8: fund  7+6=13,  UPPER(60) 失敗, fund=13
            (2, None),  # cycle  9: fund 13+6=19,  UPPER(60) 失敗, fund=19
            (2, None),  # cycle 10: fund 19+6=25,  UPPER(60) 失敗, fund=25
            (2, None),  # cycle 11: fund 25+6=31,  UPPER(60) 失敗, fund=31
            (2, None),  # cycle 12: fund 31+6=37,  UPPER(60) 失敗, fund=37
            (2, None),  # cycle 13: fund 37+6=43,  UPPER(60) 失敗, fund=43
            (2, None),  # cycle 14: fund 43+6=49,  UPPER(60) 失敗, fund=49
            (2, None),  # cycle 15: fund 49+6=55,  UPPER(60) 失敗, fund=55
            (3, UnitType.UPPER),  # cycle 16: fund 55+6=61,  UPPER(60) 成功, fund=1
        ]
        for cycle, (expected_count, expected_type) in enumerate(expected, 1):
            with self.subTest(cycle=cycle):
                for _ in range(interval):
                    force.update()
                spawned = [u for u in force.units if u.unit_type != UnitType.BASE]
                self.assertEqual(
                    len(spawned), expected_count, f"cycle {cycle}: spawn count"
                )
                if expected_type is not None:
                    self.assertEqual(
                        spawned[-1].unit_type,
                        expected_type,
                        f"cycle {cycle}: unit type",
                    )

    def test_strategy_spawns_correct_unit_types(self):
        """各戦略に従ったユニットタイプのみスポーンされる（3サイクル分）"""
        # (ケース名, 戦略, 初期fund, 期待スポーン順)
        # UPPER コスト60: 3サイクル(各+18資金)で3体スポーンするには初期200が必要
        # 200+18-60=158, 158+18-60=116, 116+18-60=74 → 3体成功
        test_cases = [
            (
                "LOWER_ONLY",
                EnemyStrategy.LOWER_ONLY,
                100,
                [UnitType.LOWER, UnitType.LOWER, UnitType.LOWER],
            ),
            (
                "MIDDLE_ONLY",
                EnemyStrategy.MIDDLE_ONLY,
                100,
                [UnitType.MIDDLE, UnitType.MIDDLE, UnitType.MIDDLE],
            ),
            (
                "UPPER_ONLY",
                EnemyStrategy.UPPER_ONLY,
                200,
                [UnitType.UPPER, UnitType.UPPER, UnitType.UPPER],
            ),
            (
                "CYCLE: LOWER→MIDDLE→UPPER順",
                EnemyStrategy.CYCLE,
                100,
                [UnitType.LOWER, UnitType.MIDDLE, UnitType.UPPER],
            ),
        ]
        for case_name, strategy, initial_fund, expected_types in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(Side.ENEMY, strategy=strategy)
                force._fund = initial_fund  # pylint: disable=W0212
                for _ in range(Force.AUTO_PUT_INTERVAL * 3):
                    force.update()
                spawned = [u for u in force.units if u.unit_type != UnitType.BASE]
                self.assertEqual(len(spawned), len(expected_types), case_name)
                for i, (unit, expected) in enumerate(zip(spawned, expected_types)):
                    self.assertEqual(
                        unit.unit_type, expected, f"{case_name}: unit[{i}]"
                    )

    def test_strategy_when_not_specified(self):
        """戦略未指定時の strategy: ENEMY は random.choice の結果、PLAYER は None"""
        from unittest.mock import patch  # pylint: disable=C0415

        # (ケース名, side, patchの戻り値, 期待strategy)
        # PLAYER は random.choice を呼ばないため patch_return は無関係
        test_cases = [
            (
                "ENEMY: LOWER_ONLY",
                Side.ENEMY,
                EnemyStrategy.LOWER_ONLY,
                EnemyStrategy.LOWER_ONLY,
            ),
            (
                "ENEMY: UPPER_ONLY",
                Side.ENEMY,
                EnemyStrategy.UPPER_ONLY,
                EnemyStrategy.UPPER_ONLY,
            ),
            ("PLAYER", Side.PLAYER, EnemyStrategy.LOWER_ONLY, None),
        ]
        for case_name, side, patch_return, expected_strategy in test_cases:
            with self.subTest(case_name=case_name):
                with patch("force.random.choice", return_value=patch_return):
                    force = Force(side)
                self.assertEqual(force.strategy, expected_strategy, case_name)

    def test_fund(self):
        """フレーム数に応じて軍資金が増加する"""
        interval = Force.FUND_INTERVAL
        test_cases = [
            ("initial value is zero", 0, 0),
            ("increases after interval", interval, Force.FUND_ADD),
            ("does not increase before interval", interval - 1, 0),
            ("increases multiple times", interval * 3, Force.FUND_ADD * 3),
        ]
        for case_name, update_count, expected_fund in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(Side.PLAYER)
                for _ in range(update_count):
                    force.update()
                self.assertEqual(force.fund, expected_fund)

    def test_base_hp_ratio(self):
        """残HP割合が正しく計算されること"""
        test_cases = [
            ("満HP（0ダメージ）", 0, 20 / 20),
            ("1ダメージ後", 1, 19 / 20),
        ]
        for case_name, damage_count, expected_ratio in test_cases:
            with self.subTest(case_name=case_name):
                force = Force(Side.PLAYER)
                base_unit = next(u for u in force.units if u.unit_type == UnitType.BASE)
                for _ in range(damage_count):
                    base_unit.take_damage()
                self.assertAlmostEqual(force.base_hp_ratio, expected_ratio)

    def test_base_hp_ratio_destroyed(self):
        """拠点が破壊済みのとき、割合が 0.0 であること"""
        force = Force(Side.PLAYER)
        # 拠点を全滅させる
        base_unit = next(u for u in force.units if u.unit_type == UnitType.BASE)
        for _ in range(20):  # 最大HP=20 回ダメージ
            base_unit.take_damage()
        # is_alive=False かつ is_damaged=False になるまで update
        for _ in range(Unit.DAMAGED_FRAMES + 1):
            force.update()
        self.assertAlmostEqual(force.base_hp_ratio, 0.0)
