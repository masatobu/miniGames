import os
import sys
import traceback
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import (  # pylint: disable=C0413
    IView,
    GameCore,
    Controller,
    IInput,
    Direct,
    Player,
    Unit,
    IUnitView,
    Area,
    Color,
    Field,
    PyxelUnitView,
    Fee,
    GameObject,
    Enemy,
    Status,
    Mob,
    Console,
    Coin,
    Weapon,
    Spawner,
    Boss,
)
from map_generator import IMapGenerator  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        super().__init__(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        self.frame = 0
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_circ(self, x, y, r, col, is_fill):
        self.call_params.append(("draw_circ", x, y, r, col, is_fill))

    def draw_rect(self, x, y, w, h, col, is_fill):
        self.call_params.append(("draw_rect", x, y, w, h, col, is_fill))

    def draw_image(self, x, y, src_x, src_y, revert, is_trans):
        self.call_params.append(("draw_image", x, y, src_x, src_y, revert, is_trans))

    def clear(self, x, y):
        self.call_params.append(("clear", x, y))

    def get_frame(self):
        return self.frame

    def get_call_params(self):
        return self.call_params

    def increment_frame(self):
        self.frame += 1

    def reset(self):
        self.frame = 0
        self.call_params = []


class TestInput(IInput):
    def __init__(self):
        self.b_is_click = False
        self.b_is_release = False
        self.mouse_pos = None

    def is_click(self):
        return self.b_is_click

    def is_release(self):
        return self.b_is_release

    def get_mouse_x(self):
        return self.mouse_pos[0]

    def get_mouse_y(self):
        return self.mouse_pos[1]

    def set_is_click(self, b_is_click):
        self.b_is_click = b_is_click

    def set_is_release(self, b_is_release):
        self.b_is_release = b_is_release

    def set_mouse_pos(self, x, y):
        self.mouse_pos = (x, y)

    def reset(self):
        self.b_is_click = False
        self.b_is_release = False
        self.mouse_pos = None


class TestUnitView(IUnitView):
    def __init__(self):
        self.call_params = []

    def draw_unit(self, x, y, image_x, image_y, face, direct, is_damaged):
        self.call_params.append(
            ("draw_unit", x, y, image_x, image_y, face, direct, is_damaged)
        )

    def get_call_params(self):
        return self.call_params

    def reset(self):
        self.call_params = []


class TestMapGenerator(IMapGenerator):
    POWER_WEIGHT = 2
    COIN_WEIGHT = 3
    BOSS_POWER_WEIGHT = 4

    def __init__(self):
        self.enemy_zero_flg = False
        self.weapon_zero_flg = True
        self.spawner_zero_flg = True
        self.fee_zero_flg = False
        self.start_pos = (2, 2)
        self.boss_pos = (100, 100)

    @classmethod
    def calc_area_level(cls, area_axis_x, area_axis_y):
        return max(1, 10 * (max(abs(p) for p in (area_axis_x, area_axis_y)) // 5))

    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        return (
            0 if self.fee_zero_flg else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        return (
            0
            if self.enemy_zero_flg
            else self.calc_area_level(area_axis_x, area_axis_y) * self.POWER_WEIGHT
        )

    def get_boss_power(self) -> int:
        return self.BOSS_POWER_WEIGHT

    def get_coin_num(self, area_axis_x, area_axis_y) -> int:
        return self.calc_area_level(area_axis_x, area_axis_y) * self.COIN_WEIGHT

    def get_weapon_power(self, area_axis_x, area_axis_y) -> int:
        return (
            0
            if self.weapon_zero_flg
            else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        return (
            0
            if self.spawner_zero_flg
            else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_start_pos(self) -> tuple[int, int]:
        return self.start_pos

    def get_boss_pos(self) -> tuple[int, int]:
        return self.boss_pos

    def set_enemy_ret_zero(self, flg):
        self.enemy_zero_flg = flg

    def set_weapon_ret_zero(self, flg):
        self.weapon_zero_flg = flg

    def set_spawner_ret_zero(self, flg):
        self.spawner_zero_flg = flg

    def set_fee_ret_zero(self, flg):
        self.fee_zero_flg = flg

    def set_start_pos(self, pos):
        self.start_pos = pos

    def set_boss_pos(self, pos):
        self.boss_pos = pos

    def reset(self):
        self.enemy_zero_flg = False
        self.weapon_zero_flg = True
        self.spawner_zero_flg = True
        self.fee_zero_flg = False
        self.start_pos = (2, 2)
        self.boss_pos = (100, 100)


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()

    def reset(self):
        self.test_view.reset()
        self.test_input.reset()


class TestUnitParent(TestParent):
    def setUp(self):
        super().setUp()
        self.test_unit_view = TestUnitView()
        self.patcher_unit_view = patch(
            "main.PyxelUnitView.create",
            return_value=self.test_unit_view,
        )
        self.mock_unit_view = self.patcher_unit_view.start()
        self.test_map_generator = TestMapGenerator()
        self.patcher_map_generator = patch(
            "main.AreaBlockAlgorithmGenerator.create",
            return_value=self.test_map_generator,
        )
        self.mock_map_generator = self.patcher_map_generator.start()

    def tearDown(self):
        super().tearDown()
        self.patcher_unit_view.stop()
        self.patcher_map_generator.stop()

    def reset(self):
        super().reset()
        self.test_unit_view.reset()
        self.test_map_generator.reset()


class TestUnit(TestParent):
    def test_draw(self):
        d = Direct
        test_cases = [
            ("no move", [1, 1, 3, 3], False, [(d.NUTRAL, False)]),
            ("right walk", [1, 2, 1, 4], False, [(d.RIGHT, False)]),
            ("left walk", [1, 2, 1, 4], True, [(d.LEFT, False)]),
            ("up walk", [1, 2, 1, 4], False, [(d.UP, False)]),
            ("down walk", [1, 2, 1, 4], False, [(d.DOWN, False)]),
            ("right up walk", [1, 2, 1, 4], False, [(d.RIGHT, False), (d.UP, False)]),
            ("left down walk", [1, 2, 1, 4], True, [(d.LEFT, False), (d.DOWN, False)]),
            ("turn left", [1, 1, 3, 3], True, [(d.LEFT, False), (d.NUTRAL, False)]),
            ("no move blocked", [1, 1, 3, 3], False, [(d.NUTRAL, True)]),
            ("right walk blocked", [1, 2, 1, 4], False, [(d.RIGHT, True)]),
            ("left walk blocked", [1, 2, 1, 4], True, [(d.LEFT, True)]),
            ("up walk blocked", [1, 2, 1, 4], False, [(d.UP, True)]),
            ("down walk blocked", [1, 2, 1, 4], False, [(d.DOWN, True)]),
            (
                "left blocked down walk",
                [1, 2, 1, 4],
                True,
                [(d.LEFT, True), (d.DOWN, False)],
            ),
        ]
        for case_name, expected_pattern, expected_rev, move_direct in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pattern=expected_pattern,
                expected_face=expected_rev,
                move_direct=move_direct,
            ):
                self.reset()
                unit = Unit(100, 100, 1, 0)
                for direct, is_blocked in move_direct:
                    unit.move(direct, is_blocked)
                expected = []
                size = PyxelUnitView.SIZE
                pos = [100 - size // 2, 100 - size // 2]
                for _ in range(3):
                    for image_x in expected_pattern:
                        unit.update()
                        unit.draw()
                        if not move_direct[-1][1]:
                            pos = [p + d for p, d in zip(pos, move_direct[-1][0].value)]
                        expected.append(
                            ("draw_image", *pos, image_x, 0, expected_rev, False)
                        )
                        for _ in range(5):
                            self.test_view.increment_frame()
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestMob(TestParent):
    def test_damaged(self):
        test_cases = [
            ("kill", [True], (0, 1, 0), [True], 1),
            ("stay kill", [False, True], (0, 1, 0), [False, True], 1),
            ("no kill", [False, False, False], (1, 2, 0), [False, True, False], 2),
            ("kill hp 3", [False, False, True], (0, 3, 0), [True, True, True], 3),
        ]
        for (
            case_name,
            expected_killed_pattern,
            expected_stat,
            damage_pattern,
            hp,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_killed_pattern=expected_killed_pattern,
                expected_stat=expected_stat,
                damage_pattern=damage_pattern,
                hp=hp,
            ):
                self.reset()
                mob = Mob(100, 100, 1, 0)
                mob.hp = mob.max_hp = hp
                expected = []
                pad = PyxelUnitView.SIZE // 2
                for flg_expected, flg_damaged in zip(
                    expected_killed_pattern, damage_pattern
                ):
                    if flg_damaged:
                        mob.set_damaged()
                    for _ in range(2):
                        for i, image_x in enumerate([1, 1, 3, 3]):
                            self.assertEqual(False, mob.is_killed())
                            mob.draw()
                            for _ in range(5):
                                mob.update()
                                self.test_view.increment_frame()
                            if flg_damaged and i % 2 == 1:
                                continue
                            expected.append(
                                (
                                    "draw_image",
                                    100 - pad,
                                    100 - pad,
                                    image_x,
                                    0,
                                    False,
                                    False,
                                )
                            )
                    self.assertEqual(flg_expected, mob.is_killed())
                self.assertEqual(expected_stat, mob.get_status())
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def _check_battle_result(
        self, mob, player, mob_status, is_mob_killed, player_status, is_player_killed
    ):
        self.assertEqual(mob_status, mob.get_status())
        self.assertEqual(is_mob_killed, mob.is_killed())
        self.assertEqual(player_status, player.get_status())
        self.assertEqual(is_player_killed, player.is_killed())

    def test_battle(self):
        test_cases = [
            ("mob kill", True, 1, 2),
            ("player kill", False, 3, 2),
            ("mob kill with draw", True, 2, 2),
            ("zero draw", True, 0, 0),
            ("over kill", False, 100, 0),
        ]
        for (
            case_name,
            expected_mob_killed,
            mob_power,
            player_power,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_mob_killed=expected_mob_killed,
                mob_power=mob_power,
                player_power=player_power,
            ):
                self.reset()
                mob = Mob(100, 100, 1, 1)
                mob.set_power(mob_power)
                player = Mob(100, 100, 1, 0)
                player.set_power(player_power)
                player.set_hp(3)
                self._check_battle_result(
                    mob, player, (1, 1, mob_power), False, (3, 3, player_power), False
                )
                mob.battle(player)
                m_hp, p_hp = (0, 3) if expected_mob_killed else (1, 2)
                self._check_battle_result(
                    mob,
                    player,
                    (m_hp, 1, mob_power),
                    False,
                    (p_hp, 3, player_power),
                    False,
                )
                for _ in range(Unit.I_FRAMES):
                    mob.update()
                    player.update()
                self._check_battle_result(
                    mob,
                    player,
                    (m_hp, 1, mob_power),
                    expected_mob_killed,
                    (p_hp, 3, player_power),
                    False,
                )


class TestPlayer(TestUnitParent):
    def test_draw(self):
        player = Player(100, 100)
        player.draw()
        expected = [("draw_unit", 100, 100, 1, 0, Direct.RIGHT, Direct.NUTRAL, False)]
        self.assertEqual(
            expected,
            self.test_unit_view.get_call_params(),
            self.test_unit_view.get_call_params(),
        )


class TestFee(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("default", (100 - 2, 50 - PyxelUnitView.SIZE - 2), 1, (100, 50)),
            ("pos chg", (-50 - 2, 200 - PyxelUnitView.SIZE - 2), 1, (-50, 200)),
            ("num chg", (100 - 2, 50 - PyxelUnitView.SIZE - 2), 5, (100, 50)),
            (
                "num 2 letter",
                (100 - 2 * 2, 50 - PyxelUnitView.SIZE - 2),
                10,
                (100, 50),
            ),
            (
                "num 3 letter",
                (100 - 2 * 3, 50 - PyxelUnitView.SIZE - 2),
                100,
                (100, 50),
            ),
        ]
        for (
            case_name,
            expected_pos,
            num,
            pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                num=num,
                pos=pos,
            ):
                self.reset()
                fee = Fee(*pos)
                fee.set_num(num)
                fee.draw()
                expected_unit = [
                    ("draw_unit", *pos, 1, 3, Direct.RIGHT, Direct.NUTRAL, False)
                ]
                self.assertEqual(
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                expected_view = [("draw_text", *expected_pos, str(num))]
                self.assertEqual(
                    expected_view,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_set_num(self):
        test_cases = [
            ("num 1", 1, (2, 2)),
            ("num 1 edge left", 1, (-4, 2)),
            ("num 1 edge down", 1, (2, 4)),
            ("num 1 edge up", 1, (2, -4)),
            ("num 1 edge right", 1, (4, 2)),
            ("num 10 inner edge left", 10, (-5, 2)),
            ("num 10 inner edge down", 10, (2, 5)),
            ("num 10 inner edge up", 10, (2, -5)),
            ("num 10 inner edge right", 10, (5, 2)),
            ("num 10 outer edge left", 10, (-9, 2)),
            ("num 10 outer edge down", 10, (2, 9)),
            ("num 10 outer edge up", 10, (2, -9)),
            ("num 10 outer edge right", 10, (9, 2)),
            ("num 20 inner edge left", 20, (-10, 2)),
            ("num 20 inner edge down", 20, (2, 10)),
            ("num 20 inner edge up", 20, (2, -10)),
            ("num 20 inner edge right", 20, (10, 2)),
            ("num 20 outer edge left", 20, (-14, 2)),
            ("num 20 outer edge down", 20, (2, 14)),
            ("num 20 outer edge up", 20, (2, -14)),
            ("num 20 outer edge right", 20, (14, 2)),
        ]
        for (
            case_name,
            expected,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
            ):
                self.reset()
                fee = Fee(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis))
                self.assertEqual(expected, fee.get_num())
                self.assertEqual(expected, TestMapGenerator.calc_area_level(*area_axis))


class TestCoin(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("num 1", 1, (2, 2)),
            ("num 1 edge left", 1, (-4, 2)),
            ("num 1 edge down", 1, (2, 4)),
            ("num 1 edge up", 1, (2, -4)),
            ("num 1 edge right", 1, (4, 2)),
            ("num 10 inner edge left", 10, (-5, 2)),
            ("num 10 inner edge down", 10, (2, 5)),
            ("num 10 inner edge up", 10, (2, -5)),
            ("num 10 inner edge right", 10, (5, 2)),
            ("num 10 outer edge left", 10, (-9, 2)),
            ("num 10 outer edge down", 10, (2, 9)),
            ("num 10 outer edge up", 10, (2, -9)),
            ("num 10 outer edge right", 10, (9, 2)),
            ("num 20 inner edge left", 20, (-10, 2)),
            ("num 20 inner edge down", 20, (2, 10)),
            ("num 20 inner edge up", 20, (2, -10)),
            ("num 20 inner edge right", 20, (10, 2)),
            ("num 20 outer edge left", 20, (-14, 2)),
            ("num 20 outer edge down", 20, (2, 14)),
            ("num 20 outer edge up", 20, (2, -14)),
            ("num 20 outer edge right", 20, (14, 2)),
        ]
        for (
            case_name,
            expected_coin,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_coin=expected_coin,
                area_axis=area_axis,
            ):
                self.reset()
                s = Area.SIZE
                pos = tuple(p * s + s // 2 for p in area_axis)
                coin = Coin(*pos)
                coin.draw()
                expected = [
                    ("draw_unit", *pos, 1, 4, Direct.RIGHT, Direct.NUTRAL, False)
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                self.assertEqual(
                    expected_coin * TestMapGenerator.COIN_WEIGHT,
                    coin.get_num(),
                )
                self.assertEqual(
                    expected_coin, TestMapGenerator.calc_area_level(*area_axis)
                )


class TestWeapon(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("no drop", 0, True, (2, 2)),
            ("no drop 2", 0, True, (5, 5)),
            ("drop", 1, False, (2, 2)),
            ("drop 2", 10, False, (5, 5)),
        ]
        for (
            case_name,
            expected_weapon,
            zero_flg,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_weapon=expected_weapon,
                zero_flg=zero_flg,
                area_axis=area_axis,
            ):
                self.reset()
                self.test_map_generator.set_weapon_ret_zero(zero_flg)
                s = Area.SIZE
                pos = tuple(p * s + s // 2 for p in area_axis)
                weapon = Weapon(*pos)
                weapon.draw()
                expected = [
                    ("draw_unit", *pos, 1, 5, Direct.RIGHT, Direct.NUTRAL, False)
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                self.assertEqual(expected_weapon, weapon.get_num())


class TestEnemy(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("default", (100 - 2, 50 - PyxelUnitView.SIZE - 2), 1, (100, 50)),
            ("pos chg", (-50 - 2, 200 - PyxelUnitView.SIZE - 2), 1, (-50, 200)),
            ("power chg", (100 - 2, 50 - PyxelUnitView.SIZE - 2), 5, (100, 50)),
            (
                "power 2 letter",
                (100 - 2 * 2, 50 - PyxelUnitView.SIZE - 2),
                10,
                (100, 50),
            ),
            (
                "power 3 letter",
                (100 - 2 * 3, 50 - PyxelUnitView.SIZE - 2),
                100,
                (100, 50),
            ),
        ]
        for (
            case_name,
            expected_pos,
            power,
            pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                power=power,
                pos=pos,
            ):
                self.reset()
                enemy = Enemy(*pos)
                enemy.set_power(power)
                enemy.draw()
                expected_unit = [
                    ("draw_unit", *pos, 1, 1, Direct.RIGHT, Direct.NUTRAL, False)
                ]
                self.assertEqual(
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                expected_view = [("draw_text", *expected_pos, str(power))]
                self.assertEqual(
                    expected_view,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_spot(self):
        test_cases = [
            ("to left", (99, 50), (Direct.LEFT, Direct.LEFT), (100, 50), (50, 50)),
            ("to right", (101, 50), (Direct.RIGHT, Direct.RIGHT), (100, 50), (150, 50)),
            ("to down", (100, 51), (Direct.RIGHT, Direct.DOWN), (100, 50), (100, 150)),
            ("to up", (100, 49), (Direct.RIGHT, Direct.UP), (100, 50), (100, 0)),
            (
                "to left over down",
                (99, 50),
                (Direct.LEFT, Direct.LEFT),
                (100, 50),
                (50, 75),
            ),
            (
                "to right over up",
                (101, 50),
                (Direct.RIGHT, Direct.RIGHT),
                (100, 50),
                (150, 25),
            ),
            (
                "to down over right",
                (100, 51),
                (Direct.RIGHT, Direct.DOWN),
                (100, 50),
                (125, 150),
            ),
            (
                "to up over left",
                (100, 49),
                (Direct.RIGHT, Direct.UP),
                (100, 50),
                (75, 0),
            ),
            (
                "stop from left",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (-20, 50),
            ),
            (
                "far from left",
                (99, 50),
                (Direct.LEFT, Direct.LEFT),
                (100, 50),
                (-19, 50),
            ),
            (
                "stay from left",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (-60, 50),
            ),
            (
                "stop from down",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (100, 170),
            ),
            (
                "far from down",
                (100, 51),
                (Direct.RIGHT, Direct.DOWN),
                (100, 50),
                (100, 169),
            ),
            (
                "stay from down",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (100, 220),
            ),
            (
                "stop from right",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (220, 50),
            ),
            (
                "far from right",
                (101, 50),
                (Direct.RIGHT, Direct.RIGHT),
                (100, 50),
                (219, 50),
            ),
            (
                "stay from right",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (260, 50),
            ),
            (
                "stop from up",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (100, -70),
            ),
            (
                "far from up",
                (100, 49),
                (Direct.RIGHT, Direct.UP),
                (100, 50),
                (100, -69),
            ),
            (
                "stay from up",
                (100, 50),
                (Direct.RIGHT, Direct.NUTRAL),
                (100, 50),
                (100, -110),
            ),
        ]
        for (
            case_name,
            expected_pos,
            expected_direct,
            enemy_pos,
            player_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                expected_direct=expected_direct,
                enemy_pos=enemy_pos,
                player_pos=player_pos,
            ):
                self.reset()
                enemy = Enemy(*enemy_pos)
                enemy.spot(*player_pos)
                enemy.update()
                enemy.draw()
                expected = [("draw_unit", *expected_pos, 1, 1, *expected_direct, False)]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_block_area_edge(self):
        test_cases = [
            ("to right", (120 - 1, 100), (Direct.RIGHT, Direct.RIGHT), (140, 100)),
            ("to down", (100, 120 - 1), (Direct.RIGHT, Direct.DOWN), (100, 140)),
            ("to left", (80, 100), (Direct.LEFT, Direct.LEFT), (60, 100)),
            ("to up", (100, 80), (Direct.RIGHT, Direct.UP), (100, 60)),
        ]
        for (
            case_name,
            expected_pos,
            expected_direct,
            player_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                expected_direct=expected_direct,
                player_pos=player_pos,
            ):
                self.reset()
                enemy = Enemy(100, 100)
                for _ in range(Area.SIZE):
                    enemy.spot(*player_pos)
                    enemy.update()
                enemy.draw()
                expected = [("draw_unit", *expected_pos, 1, 1, *expected_direct, False)]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_set_power(self):
        test_cases = [
            ("power 1", 1, (2, 2)),
            ("power 1 edge left", 1, (-4, 2)),
            ("power 1 edge down", 1, (2, 4)),
            ("power 1 edge up", 1, (2, -4)),
            ("power 1 edge right", 1, (4, 2)),
            ("power 10 inner edge left", 10, (-5, 2)),
            ("power 10 inner edge down", 10, (2, 5)),
            ("power 10 inner edge up", 10, (2, -5)),
            ("power 10 inner edge right", 10, (5, 2)),
            ("power 10 outer edge left", 10, (-9, 2)),
            ("power 10 outer edge down", 10, (2, 9)),
            ("power 10 outer edge up", 10, (2, -9)),
            ("power 10 outer edge right", 10, (9, 2)),
            ("power 20 inner edge left", 20, (-10, 2)),
            ("power 20 inner edge down", 20, (2, 10)),
            ("power 20 inner edge up", 20, (2, -10)),
            ("power 20 inner edge right", 20, (10, 2)),
            ("power 20 outer edge left", 20, (-14, 2)),
            ("power 20 outer edge down", 20, (2, 14)),
            ("power 20 outer edge up", 20, (2, -14)),
            ("power 20 outer edge right", 20, (14, 2)),
        ]
        for (
            case_name,
            expected,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
            ):
                self.reset()
                enemy = Enemy(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis))
                self.assertEqual(
                    expected * TestMapGenerator.POWER_WEIGHT, enemy.get_power()
                )
                self.assertEqual(
                    expected,
                    TestMapGenerator.calc_area_level(*area_axis),
                )


class TestBoss(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("default", (100 - 2, 50 - PyxelUnitView.SIZE - 2), 1, (100, 50)),
            ("pos chg", (-50 - 2, 200 - PyxelUnitView.SIZE - 2), 1, (-50, 200)),
        ]
        for (
            case_name,
            expected_pos,
            power,
            pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                power=power,
                pos=pos,
            ):
                self.reset()
                boss = Boss(*pos)
                boss.set_power(power)
                boss.draw()
                expected_unit = [
                    ("draw_unit", *pos, 1, 2, Direct.RIGHT, Direct.NUTRAL, False)
                ]
                self.assertEqual(
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                expected_view = [("draw_text", *expected_pos, str(power))]
                self.assertEqual(
                    expected_view,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_set_power(self):
        test_cases = [
            ("case 1", (2, 2)),
            ("case 2", (-5, 2)),
            ("case 3", (-10, 2)),
        ]
        for case_name, area_axis in test_cases:
            with self.subTest(case_name=case_name, area_axis=area_axis):
                self.reset()
                boss = Boss(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis))
                self.assertEqual(TestMapGenerator.BOSS_POWER_WEIGHT, boss.get_power())


class TestSpawner(TestUnitParent):
    def test_draw(self):
        spawner = Spawner(100, 100)
        spawner.draw()
        expected = [("draw_unit", 100, 100, 1, 6, Direct.RIGHT, Direct.NUTRAL, False)]
        self.assertEqual(
            expected,
            self.test_unit_view.get_call_params(),
            self.test_unit_view.get_call_params(),
        )

    def test_set_power(self):
        test_cases = [
            ("no power", 0, True, (2, 2)),
            ("no power 2", 0, True, (5, 5)),
            ("power", 1, False, (2, 2)),
            ("power 2", 10, False, (5, 5)),
        ]
        for (
            case_name,
            expected_power,
            zero_flg,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_power=expected_power,
                zero_flg=zero_flg,
                area_axis=area_axis,
            ):
                self.reset()
                self.test_map_generator.set_spawner_ret_zero(zero_flg)
                s = Area.SIZE
                pos = tuple(p * s + s // 2 for p in area_axis)
                spawner = Spawner(*pos)
                self.assertEqual(expected_power, spawner.get_power())

    def test_spawn(self):
        test_cases = [
            ("just spawn", [1], [Spawner.START_SPAWN_INTERVAL]),
            ("not spawn yet", [None], [Spawner.START_SPAWN_INTERVAL - 1]),
            ("over interval", [1], [Spawner.START_SPAWN_INTERVAL + 1]),
            (
                "not spawn second",
                [1, None],
                [Spawner.START_SPAWN_INTERVAL, Spawner.START_SPAWN_INTERVAL - 1],
            ),
            (
                "over interval first",
                [1, None],
                [Spawner.START_SPAWN_INTERVAL + 1, Spawner.START_SPAWN_INTERVAL - 1],
            ),
        ]
        for (
            case_name,
            expected_power,
            intervals,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_power=expected_power,
                intervals=intervals,
            ):
                self.reset()
                self.test_map_generator.set_spawner_ret_zero(False)
                spawner = Spawner(100, 100)
                for power, interval in zip(expected_power, intervals):
                    for _ in range(interval):
                        spawner.update()
                    ret = spawner.spawn()
                    if power is not None:
                        self.assertEqual(True, isinstance(ret, Enemy))
                        self.assertEqual(1, ret.get_power())
                    else:
                        self.assertEqual(None, ret)


class TestArea(TestParent):
    def test_draw(self):
        s = Area.SIZE
        test_cases = [
            ("default", (s * 2, s * 2), (2, 2), True),
            ("case 1", (0, 0), (0, 0), True),
            ("case 2", (s * -1, s * -1), (-1, -1), True),
            ("case 3", (s, s * -1), (1, -1), True),
            ("not unveiled", (s * 2, s * 2), (2, 2), False),
        ]
        for case_name, expected, area_axis, unveiled in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
                unveiled=unveiled,
            ):
                self.reset()
                area = Area(*area_axis)
                if unveiled:
                    area.unveil()
                area.draw()
                expected = [
                    (
                        "draw_rect",
                        *expected,
                        s,
                        s,
                        Color.GREEN if unveiled else Color.DARK_BLUE,
                        False,
                    ),
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_contains(self):
        s = Area.SIZE
        test_cases = [
            ("default", True, (2, 2), (100, 100)),
            ("in edge left up", True, (2, 2), (s * 2, s * 2)),
            ("in edge right up", True, (2, 2), (s * 3 - 1, s * 2)),
            ("in edge right down", True, (2, 2), (s * 3 - 1, s * 3 - 1)),
            ("in edge left down", True, (2, 2), (s * 2, s * 3 - 1)),
            ("out edge right", False, (2, 2), (s * 3, s * 2)),
            ("out edge left", False, (2, 2), (s * 2 - 1, s * 3 - 1)),
            ("out edge down", False, (2, 2), (s * 2, s * 3)),
            ("out edge up", False, (2, 2), (s * 3 - 1, s * 2 - 1)),
            ("negative pos in edge left down", True, (-2, -2), (s * -2, s * -1 - 1)),
            ("negative pos out edge left", False, (-2, -2), (s * -2 - 1, s * -2)),
        ]
        for case_name, expected, area_axis, check_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
                check_pos=check_pos,
            ):
                self.reset()
                area = Area(*area_axis)
                self.assertEqual(expected, area.contains(*check_pos))


class TestField(TestUnitParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.field = Field()

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.field = Field()

    def check(self):
        self.assertEqual(
            self.expect_view_call,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.assertEqual(
            self.expect_unit_view_call,
            self.test_unit_view.get_call_params(),
            self.test_unit_view.get_call_params(),
        )

    def put_draw_result(self, draw_action_list):
        try:
            for draw_action in draw_action_list:
                if draw_action[0] == "area":
                    s = Area.SIZE
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                s * x,
                                s * y,
                                s,
                                s,
                                (
                                    Color.GREEN
                                    if (x, y) in draw_action[2]
                                    else Color.DARK_BLUE
                                ),
                                False,
                            )
                            for x, y in draw_action[1]
                        ]
                    )
                if draw_action[0] in ["enemy_power", "fee_num", "boss_power"]:
                    stat = str(draw_action[3])
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_text",
                                *tuple(
                                    p - d - l
                                    for p, d, l in zip(
                                        draw_action[1:3],
                                        Unit.STAT_PADDING,
                                        (len(stat) * Unit.LETTER_SIZE, 0),
                                    )
                                ),
                                stat,
                            )
                        ]
                    )
        except Exception as e:  # pylint: disable=W0718
            print(e)
            traceback.print_exc()

    def put_unit_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            image_pos = None
            if draw_action[0] == "player":
                image_pos = Player.IMAGE_POS
            elif draw_action[0] == "fee":
                image_pos = Fee.IMAGE_POS
            elif draw_action[0] == "enemy":
                image_pos = Enemy.IMAGE_POS
            elif draw_action[0] == "coin":
                image_pos = Coin.IMAGE_POS
            elif draw_action[0] == "weapon":
                image_pos = Weapon.IMAGE_POS
            elif draw_action[0] == "spawner":
                image_pos = Spawner.IMAGE_POS
            elif draw_action[0] == "boss":
                image_pos = Boss.IMAGE_POS
            self.expect_unit_view_call.append(
                ("draw_unit", *draw_action[1:3], *image_pos, *draw_action[3:6])
            )

    def test_walk_to_edge(self):
        s = Area.SIZE
        test_cases = [
            ("to right", (s * 3 - 1, 100), Direct.RIGHT, Direct.RIGHT, False),
            ("to left", (s * 2, 100), Direct.LEFT, Direct.LEFT, False),
            ("to down", (100, s * 3 - 1), Direct.RIGHT, Direct.DOWN, False),
            ("to up", (100, s * 2), Direct.RIGHT, Direct.UP, False),
            ("over right", (s * 4 - 1, 100), Direct.RIGHT, Direct.RIGHT, True),
            ("over left", (s * 1, 100), Direct.LEFT, Direct.LEFT, True),
            ("over down", (100, s * 4 - 1), Direct.RIGHT, Direct.DOWN, True),
            ("over up", (100, s * 1), Direct.RIGHT, Direct.UP, True),
        ]
        for (
            case_name,
            expected_pos,
            expected_face,
            to_direct,
            expand_area,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                expected_face=expected_face,
                to_direct=to_direct,
                expand_area=expand_area,
            ):
                self.reset()
                areas = [(2, 2)]
                self.field.area_map = {p: Area(*p) for p in areas}
                self.field.unit_map = {}
                if expand_area:
                    new_area = tuple(p + d for p, d in zip((2, 2), to_direct.value))
                    self.field.area_map[new_area] = Area(*new_area)
                    areas.append(new_area)
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                for _ in range(s * 2 + 1):
                    self.field.operate(to_direct)
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [("player", *expected_pos, expected_face, to_direct, False)]
                )
                self.check()

    def test_unveil_area(self):
        s = Area.SIZE
        test_cases = [
            (
                "default",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [],
                False,
            ),
            (
                "again",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [(2, 2)],
                False,
            ),
            (
                "neighbor",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3), (1, 1), (0, 2), (1, 3)],
                [],
                {(2, 2), (1, 2)},
                [(1, 2)],
                False,
            ),
            (
                "cant unveil",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [(1, 1)],
                False,
            ),
            (
                "over monitor left",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [1, 0, -1]
                    for (x, y) in [(p, 1), (p - 1, 2), (p, 3)]
                ]
                + [(-2, 1), (-2, 3)],
                [],
                {(p, 2) for p in [2, 1, 0, -1, -2]},
                [(p, 2) for p in [1, 0, -1, -2]],
                False,
            ),
            (
                "over monitor right",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [(x, y) for p in [3, 4, 5] for (x, y) in [(p + 1, 2), (p, 1), (p, 3)]]
                + [(6, 1), (6, 3)],
                [],
                {(p, 2) for p in [2, 3, 4, 5, 6]},
                [(p, 2) for p in [3, 4, 5, 6]],
                False,
            ),
            (
                "over monitor up",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [1, 0, -1, -2]
                    for (x, y) in [(3, p), (2, p - 1), (1, p)]
                ]
                + [(3, -3), (1, -3)],
                [],
                {(2, p) for p in [2, 1, 0, -1, -2, -3]},
                [(2, p) for p in [1, 0, -1, -2, -3]],
                False,
            ),
            (
                "over monitor down",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [3, 4, 5, 6]
                    for (x, y) in [(3, p), (1, p), (2, p + 1)]
                ]
                + [(3, 7), (1, 7)],
                [],
                {(2, p) for p in [2, 3, 4, 5, 6, 7]},
                [(2, p) for p in [3, 4, 5, 6, 7]],
                False,
            ),
            (
                "unveil void",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [(1, 1), (0, 2), (1, 3)],
                {(2, 2), (1, 2)},
                [(1, 2)],
                True,
            ),
        ]
        for (
            case_name,
            expected_list_with_fee,
            expected_list_without_fee,
            expected_unveiled_set,
            unveil_list,
            void_flg,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list_with_fee=expected_list_with_fee,
                expected_list_without_fee=expected_list_without_fee,
                expected_unveiled_set=expected_unveiled_set,
                unveil_list=unveil_list,
                void_flg=void_flg,
            ):
                self.reset()
                self.test_map_generator.set_fee_ret_zero(void_flg)
                for pos in unveil_list:
                    self.field._unveil(*pos)  # pylint: disable=W0212
                self.field.draw()
                self.put_draw_result(
                    [
                        (
                            "area",
                            expected_list_with_fee + expected_list_without_fee,
                            expected_unveiled_set,
                        )
                    ]
                )
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(s * p + s // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for pos in expected_list_with_fee
                        if pos != (2, 2)
                    ]
                )
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(s * p + s // 2 for p in pos),
                            TestMapGenerator.calc_area_level(*pos),
                        )
                        for pos in expected_list_with_fee
                        if pos != (2, 2)
                    ]
                )
                self.check()

    def test_walk_to_fee(self):
        s = Area.SIZE
        test_cases = [
            (
                "to up",
                [(2, 1)],
                Direct.UP,
                [(3, 1), (2, 0), (1, 1)],
                Direct.RIGHT,
                (2, 2),
                1,
                True,
                True,
            ),
            (
                "to down",
                [(2, 3)],
                Direct.DOWN,
                [(3, 3), (1, 3), (2, 4)],
                Direct.RIGHT,
                (2, 2),
                1,
                True,
                True,
            ),
            (
                "to right",
                [(3, 2)],
                Direct.RIGHT,
                [(4, 2), (3, 1), (3, 3)],
                Direct.RIGHT,
                (2, 2),
                1,
                True,
                True,
            ),
            (
                "to left",
                [(1, 2)],
                Direct.LEFT,
                [(1, 1), (0, 2), (1, 3)],
                Direct.LEFT,
                (2, 2),
                1,
                True,
                True,
            ),
            (
                "with areas",
                [(2, 1)] + [(2, 3 + p) for p in range(4)],
                Direct.UP,
                [(3, 1), (2, 0), (1, 1)],
                Direct.RIGHT,
                (2, 2),
                1,
                True,
                True,
            ),
            (
                "to down far",
                [(2, 5)],
                Direct.DOWN,
                [(3, 5), (1, 5), (2, 6)],
                Direct.RIGHT,
                (2, 4),
                10,
                True,
                True,
            ),
            (
                "cant unveil with no coin",
                [(2, 1)],
                Direct.UP,
                [],
                Direct.RIGHT,
                (2, 2),
                0,
                False,
                True,
            ),
            (
                "cant unveil without full coin",
                [(2, 5)],
                Direct.DOWN,
                [],
                Direct.RIGHT,
                (2, 4),
                10 - 1,
                False,
                True,
            ),
            (
                "no enemy spawn and gameover",
                [(2, 1)],
                Direct.UP,
                [(3, 1), (2, 0), (1, 1)],
                Direct.RIGHT,
                (2, 2),
                1,
                True,
                False,
            ),
        ]
        for (
            case_name,
            first_area_list,
            to_direct,
            extend_pos_list,
            expected_face,
            start_pos,
            coin,
            expected_is_unveil,
            is_enemy_spawn,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                first_area_list=first_area_list,
                to_direct=to_direct,
                extend_pos_list=extend_pos_list,
                expected_face=expected_face,
                start_pos=start_pos,
                coin=coin,
                expected_is_unveil=expected_is_unveil,
                is_enemy_spawn=is_enemy_spawn,
            ):
                self.reset()
                self.test_map_generator.set_enemy_ret_zero(not is_enemy_spawn)
                self.field.player.coin_num = coin
                areas = [start_pos] + first_area_list
                self.field.player.pos = tuple(p * s + s // 2 for p in start_pos)
                self.field.area_map = {p: Area(*p) for p in areas}
                self.field.unit_map = {
                    pos: Fee(*tuple(p * s + s // 2 for p in pos))
                    for pos in first_area_list
                }
                for _ in range(s - PyxelUnitView.SIZE):
                    self.field.operate(to_direct)
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in first_area_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(
                                p * s + s // 2 + d * (s - PyxelUnitView.SIZE)
                                for d, p in zip(to_direct.value, start_pos)
                            ),
                            expected_face,
                            to_direct,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(p * s + s // 2 for p in axis),
                            TestMapGenerator.calc_area_level(*axis),
                        )
                        for axis in first_area_list
                    ]
                )
                self.assertEqual(coin, self.field.player.get_coin_num())
                self.assertEqual(False, self.field.is_no_coin())
                self.field.update()
                self.field.draw()
                areas.extend(extend_pos_list)
                append_pos = tuple(p + d for p, d in zip(start_pos, to_direct.value))
                self.put_draw_result(
                    [("area", areas, {append_pos} if expected_is_unveil else set())]
                )
                enemy_pos = tuple(
                    p * s + s // 2 + d * 7 for p, d in zip(append_pos, to_direct.value)
                )
                fee_appended_pos_list = first_area_list
                rest_coin = coin
                if expected_is_unveil:
                    fee_appended_pos_list = [
                        pos
                        for pos in first_area_list + extend_pos_list
                        if pos != append_pos
                    ]
                    if is_enemy_spawn:
                        self.put_unit_draw_result(
                            [
                                (
                                    "enemy",
                                    *enemy_pos,
                                    Direct.RIGHT,
                                    Direct.NUTRAL,
                                    False,
                                )
                            ]
                        )
                        self.put_draw_result(
                            [
                                (
                                    "enemy_power",
                                    *enemy_pos,
                                    TestMapGenerator.calc_area_level(*append_pos)
                                    * TestMapGenerator.POWER_WEIGHT,
                                )
                            ]
                        )
                    rest_coin -= TestMapGenerator.calc_area_level(*append_pos)
                self.assertEqual(
                    rest_coin,
                    self.field.player.get_coin_num(),
                )
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in fee_appended_pos_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(
                                p * s + s // 2 + d * (s - PyxelUnitView.SIZE + 1)
                                for d, p in zip(to_direct.value, start_pos)
                            ),
                            expected_face,
                            to_direct,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(p * s + s // 2 for p in axis),
                            TestMapGenerator.calc_area_level(*axis),
                        )
                        for axis in fee_appended_pos_list
                    ]
                )
                self.check()
                self.assertEqual(not is_enemy_spawn, self.field.is_no_coin())

    def test_spawn(self):
        s = Area.SIZE
        test_cases = [
            ("enemy from down", (100, 93), (100, 107), (2, 2), False, "enemy"),
            ("enemy from left", (93, 100), (107, 100), (2, 2), False, "enemy"),
            ("enemy from up", (100, 107), (100, 93), (2, 2), False, "enemy"),
            ("enemy from right", (107, 100), (93, 100), (2, 2), False, "enemy"),
            (
                "enemy neg area from down left",
                (-53, -67),
                (-67, -53),
                (-2, -2),
                False,
                "enemy",
            ),
            (
                "enemy neg area from left up",
                (-53, -53),
                (-67, -67),
                (-2, -2),
                False,
                "enemy",
            ),
            (
                "enemy neg area from up right",
                (-67, -53),
                (-53, -67),
                (-2, -2),
                False,
                "enemy",
            ),
            (
                "enemy neg area from right down",
                (-67, -67),
                (-53, -53),
                (-2, -2),
                False,
                "enemy",
            ),
            ("enemy not spawn", None, (100, 107), (2, 2), True, "enemy"),
            ("weapon spawn", (100, 93), (100, 107), (2, 2), True, "weapon"),
            ("spawner spawn", (100, 100), (100, 107), (2, 2), True, "spawner"),
        ]
        for (
            case_name,
            expected_pos,
            player_pos,
            area_axis,
            enemy_power_zero_flg,
            unit_kind,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                player_pos=player_pos,
                area_axis=area_axis,
                enemy_power_zero_flg=enemy_power_zero_flg,
                unit_kind=unit_kind,
            ):
                self.reset()
                self.test_map_generator.set_enemy_ret_zero(enemy_power_zero_flg)
                self.test_map_generator.set_weapon_ret_zero(unit_kind != "weapon")
                self.test_map_generator.set_spawner_ret_zero(unit_kind != "spawner")
                self.field.player.add_coin(10)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {
                    area_axis: Fee(*tuple(p * s + s // 2 for p in area_axis))
                }
                self.field.player.pos = player_pos
                self.field.update()
                self.field.draw()
                extend_area = [
                    tuple(p + d for p, d in zip(area_axis, direct.value))
                    for direct in Direct
                    if direct != Direct.NUTRAL
                ]
                self.put_draw_result([("area", [area_axis] + extend_area, {area_axis})])
                if not enemy_power_zero_flg or unit_kind in ["weapon", "spawner"]:
                    self.put_unit_draw_result(
                        [
                            (
                                unit_kind,
                                *expected_pos,
                                Direct.RIGHT,
                                Direct.NUTRAL,
                                False,
                            )
                        ]
                    )
                    if unit_kind == "enemy":
                        self.put_draw_result(
                            [
                                (
                                    "enemy_power",
                                    *expected_pos,
                                    TestMapGenerator.POWER_WEIGHT,
                                )
                            ]
                        )
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in extend_area
                    ]
                    + [
                        (
                            "player",
                            *player_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        ("fee_num", *tuple(p * s + s // 2 for p in axis), 1)
                        for axis in extend_area
                    ]
                )
                self.check()

    def test_enemy_move(self):
        s = Area.SIZE
        test_cases = [
            ("next to", [(100, 60 + 1, Direct.RIGHT, Direct.DOWN)], [(2, 1)], []),
            (
                "near 2",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                    (100, 140 - 1, Direct.RIGHT, Direct.UP),
                ],
                [(2, 1), (2, 3)],
                [],
            ),
            (
                "near and stop",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                    (100, -20, Direct.RIGHT, Direct.NUTRAL),
                    (100, -60, Direct.RIGHT, Direct.NUTRAL),
                ],
                [(2, 1), (2, -1), (2, -2)],
                [],
            ),
            (
                "near and stay",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                ],
                [(2, 1)],
                [(2, -4), (2, 8), (7, 2), (-3, 2)],
            ),
        ]
        for case_name, expected, near_area_axis_list, far_area_axis_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                near_area_axis_list=near_area_axis_list,
                far_area_axis_list=far_area_axis_list,
            ):
                self.reset()
                first_area_axis = (2, 2)
                self.field.area_map = {
                    area_axis: Area(*area_axis)
                    for area_axis in [first_area_axis]
                    + near_area_axis_list
                    + far_area_axis_list
                }
                self.field.unit_map = {
                    area_axis: Enemy(*tuple(p * s + s // 2 for p in area_axis))
                    for area_axis in near_area_axis_list + far_area_axis_list
                }
                self.field.player.pos = (100, 100)
                self.field.update()
                self.field.draw()
                self.put_draw_result(
                    [("area", [first_area_axis] + near_area_axis_list, set())]
                )
                self.put_unit_draw_result(
                    [("enemy", *stat, False) for stat in expected]
                    + [
                        (
                            "player",
                            100,
                            100,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        ("enemy_power", *stat[0:2], TestMapGenerator.POWER_WEIGHT)
                        for stat in expected
                    ]
                )
                self.check()

    def test_spawner_spawn(self):
        self.reset()
        self.test_map_generator.set_spawner_ret_zero(False)
        first_area_axis = (2, 2)
        self.field.area_map = {first_area_axis: Area(*first_area_axis)}
        self.field.unit_map = {}
        self.field.spawner_map = {first_area_axis: Spawner(100, 100)}
        self.field.player.pos = (80, 100)
        self.field.player.power = 0
        self.field.draw()
        self.put_draw_result([("area", [first_area_axis], set())])
        self.put_unit_draw_result(
            [
                ("spawner", 100, 100, Direct.RIGHT, Direct.NUTRAL, False),
                (
                    "player",
                    80,
                    100,
                    Direct.RIGHT,
                    Direct.NUTRAL,
                    False,
                ),
            ]
        )
        for enemy_stat, player_stat in [
            ((100, 100, Direct.RIGHT, Direct.NUTRAL, False), False),
            ((80, 100, Direct.LEFT, Direct.LEFT, False), True),
        ]:
            for _ in range(Spawner.START_SPAWN_INTERVAL):
                self.field.update()
            self.field.draw()
            self.put_draw_result([("area", [first_area_axis], set())])
            self.put_unit_draw_result(
                [
                    ("spawner", 100, 100, Direct.RIGHT, Direct.NUTRAL, False),
                    ("enemy", *enemy_stat),
                    (
                        "player",
                        80,
                        100,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        player_stat,
                    ),
                ]
            )
            self.put_draw_result([("enemy_power", *enemy_stat[0:2], 1)])
        self.check()

    def test_hit_mob(self):
        s = Area.SIZE
        test_cases = [
            ("enemy from down", Direct.DOWN, True, (100, 107), 2, "enemy", 5),
            ("enemy from left", Direct.LEFT, True, (93, 100), 3, "enemy", 5),
            ("enemy from up", Direct.UP, True, (100, 93), 4, "enemy", 5),
            ("enemy from right", Direct.RIGHT, True, (107, 100), 5, "enemy", 5),
            ("player damaged by enemy", Direct.DOWN, False, (100, 107), 0, "enemy", 5),
            ("boss from right", Direct.NUTRAL, True, (107, 100), 5, "boss", 5),
            ("player damaged by boss", Direct.NUTRAL, False, (100, 107), 0, "boss", 5),
            ("game over by no coin", Direct.DOWN, True, (100, 107), 2, "enemy", 0),
        ]
        for (
            case_name,
            expected_direct,
            expected_unit_killed,
            player_pos,
            player_power,
            target,
            player_coin,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                expected_unit_killed=expected_unit_killed,
                player_pos=player_pos,
                player_power=player_power,
                target=target,
                player_coin=player_coin,
            ):
                area_axis = (2, 2)
                fee_axis = (2, 1)
                self.reset()
                self.field.area_map = {
                    axis: Area(*axis) for axis in (area_axis, fee_axis)
                }
                target_cls = Enemy if target == "enemy" else Boss
                fee_pos = tuple(p * s + s // 2 for p in fee_axis)
                fee = Fee(*fee_pos)
                fee.set_num(5)
                self.field.unit_map = {
                    area_axis: target_cls(*tuple(p * s + s // 2 for p in area_axis)),
                    fee_axis: fee,
                }
                self.field.player.pos = player_pos
                self.field.player.coin_num = player_coin
                self.field.player.set_power(player_power)
                for _ in range(2):
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis, fee_axis], set())])
                steps = 1 if expected_unit_killed else 2
                next_pos = tuple(
                    p * s + s // 2 + d * steps
                    for p, d in zip(area_axis, expected_direct.value)
                )
                default_result = [
                    (
                        "fee",
                        *fee_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    ),
                    (
                        "player",
                        *player_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        not expected_unit_killed,
                    ),
                ]
                self.put_unit_draw_result(
                    [
                        (
                            target,
                            *next_pos,
                            (
                                Direct.RIGHT
                                if expected_direct != Direct.LEFT
                                else Direct.LEFT
                            ),
                            (
                                expected_direct
                                if not expected_unit_killed
                                else Direct.NUTRAL
                            ),
                            expected_unit_killed,
                        )
                    ]
                    + default_result
                )
                self.put_draw_result(
                    [
                        (
                            target + "_power",
                            *next_pos,
                            (
                                TestMapGenerator.POWER_WEIGHT
                                if target == "enemy"
                                else TestMapGenerator.BOSS_POWER_WEIGHT
                            ),
                        )
                    ]
                    + [("fee_num", *fee_pos, 5)]
                )
                self.assertEqual(False, self.field.is_clear())
                self.assertEqual(False, self.field.is_no_coin())
                for _ in range(Unit.I_FRAMES - 1):
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis, fee_axis], set())])
                result = []
                if not expected_unit_killed:
                    result += [
                        (
                            target,
                            *(player_pos if target == "enemy" else next_pos),
                            (
                                Direct.RIGHT
                                if expected_direct != Direct.LEFT
                                else Direct.LEFT
                            ),
                            Direct.RIGHT if target == "enemy" else Direct.NUTRAL,
                            expected_unit_killed,
                        )
                    ]
                    self.put_draw_result(
                        [
                            (
                                target + "_power",
                                *(player_pos if target == "enemy" else next_pos),
                                (
                                    TestMapGenerator.POWER_WEIGHT
                                    if target == "enemy"
                                    else TestMapGenerator.BOSS_POWER_WEIGHT
                                ),
                            )
                        ]
                    )
                self.put_draw_result([("fee_num", *fee_pos, 5)])
                result += default_result
                self.put_unit_draw_result(result)
                self.check()
                self.assertEqual(
                    (3 if expected_unit_killed else 1, 3, player_power),
                    self.field.player.get_status(),
                )
                self.assertEqual(
                    target == "boss" and expected_unit_killed, self.field.is_clear()
                )
                self.assertEqual(player_coin == 0, self.field.is_no_coin())

    def test_get_item(self):
        s = Area.SIZE
        test_cases = [
            ("coin from down", Direct.DOWN, 1, (100, 107), "coin"),
            ("coin from left", Direct.LEFT, 1, (93, 100), "coin"),
            ("coin from up", Direct.UP, 1, (100, 93), "coin"),
            ("coin from right", Direct.RIGHT, 1, (107, 100), "coin"),
            ("coin get 2 coins", Direct.DOWN, 2, (100, 107), "coin"),
            ("weapon", Direct.RIGHT, 1, (107, 100), "weapon"),
            ("weapon get 2 power", Direct.DOWN, 2, (100, 107), "weapon"),
        ]
        for (
            case_name,
            expected_direct,
            expected_gain,
            player_pos,
            item_kind,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                expected_gain=expected_gain,
                player_pos=player_pos,
                item_kind=item_kind,
            ):
                area_axis = (2, 2)
                self.reset()
                self.field.area_map = {area_axis: Area(*area_axis)}
                item_pos = tuple(p * s + s // 2 for p in area_axis)
                item_cls = Coin if item_kind == "coin" else Weapon
                item = item_cls(*item_pos)
                item.set_num(expected_gain)
                self.field.unit_map = {area_axis: item}
                self.field.player.pos = (0, 0)
                self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            item_kind,
                            *item_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                        (
                            "player",
                            0,
                            0,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.assertEqual(
                    (3, 3, 1, Player.START_COIN_NUM),
                    self.field.get_player_status(),
                )
                self.field.player.pos = player_pos
                self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            "player",
                            *player_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                result_param = tuple(
                    g + d
                    for g, d in zip(
                        (
                            expected_gain if kind == item_kind else 0
                            for kind in ["weapon", "coin"]
                        ),
                        (1, Player.START_COIN_NUM),
                    )
                )
                self.assertEqual(
                    (3, 3, *result_param),
                    self.field.get_player_status(),
                )
                self.check()

    def test_drop_coin(self):
        s = Area.SIZE
        test_cases = [
            ("power 1", 1, (2, 2)),
            ("power 10", 10, (2 + 5, 2)),
            ("power 100", 100, (2 + 5 * 10, 2)),
        ]
        for (
            case_name,
            expected,
            pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                pos=pos,
            ):
                area_axis = pos
                self.reset()
                self.field.area_map = {area_axis: Area(*area_axis)}
                target_pos = tuple(p * s + s // 2 for p in area_axis)
                self.field.unit_map = {area_axis: Enemy(*target_pos)}
                self.field.player.pos = target_pos
                self.field.player.set_power(expected * TestMapGenerator.POWER_WEIGHT)
                self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                next_pos = tuple(
                    p * s + s // 2 + d for p, d in zip(area_axis, Direct.LEFT.value)
                )
                self.put_unit_draw_result(
                    [
                        (
                            "enemy",
                            *next_pos,
                            Direct.LEFT,
                            Direct.LEFT,
                            True,
                        ),
                        (
                            "player",
                            *target_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "enemy_power",
                            *next_pos,
                            TestMapGenerator.calc_area_level(*area_axis)
                            * TestMapGenerator.POWER_WEIGHT,
                        )
                    ]
                )
                for _ in range(Unit.I_FRAMES - 1):
                    self.field.update()
                # ドロップしたコインとかぶらないように、位置を一つずらす。
                new_player_pos = tuple((p + 1) * s + s // 2 for p in area_axis)
                self.field.player.pos = new_player_pos
                self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                result = [
                    (
                        "coin",
                        *next_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    ),
                    (
                        "player",
                        *new_player_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    ),
                ]
                self.put_unit_draw_result(result)
                self.check()
                self.assertEqual(
                    expected * TestMapGenerator.COIN_WEIGHT,
                    self.field.unit_map[area_axis].get_num(),
                )

    def test_player_start_pos(self):
        test_cases = [
            ("pos 1", (2, 2)),
            ("pos 2", (5, 5)),
        ]
        for case_name, pos in test_cases:
            with self.subTest(case_name=case_name, pos=pos):
                self.reset()
                self.test_map_generator.set_start_pos(pos)
                self.field = Field()
                self.field.area_map = {pos: Area(*pos)}
                self.field.unit_map = {}
                self.field.draw()
                self.put_draw_result([("area", [pos], set())])
                self.put_unit_draw_result(
                    [
                        (
                            "player",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.check()

    def test_set_boss(self):
        test_cases = [
            ("pos 1", (2, 2)),
            ("pos 2", (5, 5)),
        ]
        for case_name, pos in test_cases:
            with self.subTest(case_name=case_name, pos=pos):
                self.reset()
                player_pos = (pos[0] - 1, pos[1])
                self.test_map_generator.set_start_pos(player_pos)
                self.test_map_generator.set_boss_pos(pos)
                self.field = Field()
                self.field.draw()
                areas = [
                    tuple(p + d for p, d in zip(player_pos, direct.value))
                    for direct in Direct
                ]
                self.put_draw_result([("area", areas, {player_pos, pos})])
                fee_pos_list = [
                    tuple(
                        (p + d) * Area.SIZE + Area.SIZE // 2
                        for p, d in zip(player_pos, direct.value)
                    )
                    for direct in Direct
                    if direct not in [Direct.NUTRAL, Direct.RIGHT]
                ]
                self.put_unit_draw_result(
                    [
                        (
                            "boss",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                    + [
                        (
                            "fee",
                            *pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for pos in fee_pos_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in player_pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "boss_power",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            TestMapGenerator.BOSS_POWER_WEIGHT,
                        )
                    ]
                    + [
                        (
                            "fee_num",
                            *pos,
                            TestMapGenerator.calc_area_level(
                                *tuple(p // Area.SIZE for p in pos)
                            ),
                        )
                        for pos in fee_pos_list
                    ]
                )
                self.check()

    def test_is_no_coin(self):
        test_cases = [
            ("true by no coin", True, 0, [(1, 2), (2, 3)], (10, 10), False),
            ("true by less coin", True, 4, [(1, 2)], (10, 10), False),
            (
                "false by no fee",
                False,
                5,
                [],
                (10, 10),
                False,
            ),  # feeがないときは必ずbossと接続できる
            ("false by coin num", False, 5, [(1, 2)], (10, 10), False),
            ("false by enemy exists", False, 0, [(1, 2), (2, 2)], (10, 10), False),
            ("false by coin exists", False, 0, [(1, 2), (2, 1)], (10, 10), False),
            ("false by boss unveil", False, 0, [(1, 2)], (1, 1), False),
            ("false by spawner", False, 0, [(1, 2)], (10, 10), True),
        ]
        for (
            case_name,
            expected,
            coin_num,
            unit_pos_list,
            boss_poss,
            set_spawner,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                coin_num=coin_num,
                unit_pos_list=unit_pos_list,
                set_spawner=set_spawner,
            ):
                self.reset()
                fee = Fee(60, 100)
                fee.set_num(5)
                self.field.unit_map = {
                    (2, 2): Enemy(100, 100),
                    (2, 1): Coin(100, 60),
                    (2, 3): Weapon(100, 140),
                    boss_poss: Boss(
                        *tuple(p * Area.SIZE + Area.SIZE // 2 for p in boss_poss)
                    ),
                    (1, 2): fee,
                }
                self.field.spawner_map = (
                    {(3, 2): Spawner(140, 100)} if set_spawner else {}
                )
                self.field.boss_pos = boss_poss
                self.assertEqual(False, self.field.is_no_coin())
                self.field.player.coin_num = coin_num
                self.field.unit_map = {p: self.field.unit_map[p] for p in unit_pos_list}
                self.field.set_no_coin_flg()
                self.assertEqual(expected, self.field.is_no_coin())


class TestStatus(TestParent):
    def test_draw(self):
        m_ctr = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        ctr_list = [
            ("left", (-GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)),
            ("right", (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT // 2)),
            ("up", (GameObject.SCREEN_WIDTH // 2, -GameObject.SCREEN_HEIGHT // 2)),
            ("down", (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT)),
        ]
        test_cases = [
            ("default", 0, 1, 1, 0, (1, 1, 1, 0), m_ctr),
            ("stat pattern 2", 3, 0, 5, 2, (0, 3, 5, 2), m_ctr),
        ] + [
            (f"center {mess}", 0, 1, 1, 1, (1, 1, 1, 1), ctr) for mess, ctr in ctr_list
        ]
        for (
            case_name,
            expected_loss_heart,
            expected_rest_heart,
            expected_power,
            expected_coin,
            stat,
            center,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_loss_heart=expected_loss_heart,
                expected_rest_heart=expected_rest_heart,
                expected_power=expected_power,
                expected_coin=expected_coin,
                stat=stat,
                center=center,
            ):
                self.reset()
                status = Status()
                status.set_stat(*stat)
                status.set_center(*center)
                status.draw()
                draw_image_pos = tuple(
                    c - l // 2 + 1
                    for c, l in zip(
                        center,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                expected = (
                    [
                        (
                            "draw_image",
                            draw_image_pos[0] + i * 9,
                            draw_image_pos[1] + 1,
                            *Status.LOSS_HAERT_IMAGE_POS,
                            False,
                            False,
                        )
                        for i in range(expected_loss_heart)
                    ]
                    + [
                        (
                            "draw_image",
                            draw_image_pos[0] + (expected_loss_heart + i) * 9,
                            draw_image_pos[1] + 1,
                            *Status.HAERT_IMAGE_POS,
                            False,
                            False,
                        )
                        for i in range(expected_rest_heart)
                    ]
                    + [
                        (
                            "draw_image",
                            draw_image_pos[0] + Status.POWER_PADDING,
                            draw_image_pos[1],
                            *Weapon.IMAGE_POS,
                            False,
                            False,
                        ),
                        (
                            "draw_text",
                            draw_image_pos[0] + Status.POWER_PADDING + 9,
                            draw_image_pos[1] + 2,
                            str(expected_power),
                        ),
                        (
                            "draw_image",
                            draw_image_pos[0] + Status.COIN_PADDING,
                            draw_image_pos[1],
                            *Coin.IMAGE_POS,
                            False,
                            False,
                        ),
                        (
                            "draw_text",
                            draw_image_pos[0] + Status.COIN_PADDING + 9,
                            draw_image_pos[1] + 2,
                            str(expected_coin),
                        ),
                    ]
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestController(TestParent):
    def test_stick_move(self):
        d = Direct
        m_ctr = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        ctr_list = [
            ("left", (-GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)),
            ("right", (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT // 2)),
            ("up", (GameObject.SCREEN_WIDTH // 2, -GameObject.SCREEN_HEIGHT // 2)),
            ("down", (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT)),
        ]
        test_cases = [
            ("no hover", d.NUTRAL, (None, None), (100, 100), m_ctr),
            ("no move", d.NUTRAL, (100, 100), (100, 100), m_ctr),
            ("no move edge up", d.NUTRAL, (100, 80), (100, 100), m_ctr),
            ("no move edge down", d.NUTRAL, (100, 120), (100, 100), m_ctr),
            ("no move edge left", d.NUTRAL, (80, 100), (100, 100), m_ctr),
            ("no move edge right", d.NUTRAL, (120, 100), (100, 100), m_ctr),
            ("up move", d.UP, (100, 79), (100, 100), m_ctr),
            ("down move", d.DOWN, (100, 121), (100, 100), m_ctr),
            ("left move", d.LEFT, (79, 100), (100, 100), m_ctr),
            ("right move", d.RIGHT, (121, 100), (100, 100), m_ctr),
            ("right up move", d.RIGHT, (121, 121), (100, 100), m_ctr),
            ("right more up move", d.DOWN, (121, 122), (100, 100), m_ctr),
            ("left down move", d.LEFT, (79, 79), (100, 100), m_ctr),
            ("left more down move", d.UP, (79, 78), (100, 100), m_ctr),
        ] + [
            l
            for mess, ctr in ctr_list
            for l in [
                (f"{mess} center no hover", d.NUTRAL, (None, None), (100, 100), ctr),
                (f"{mess} center no move", d.NUTRAL, (100, 100), (100, 100), ctr),
                (
                    f"{mess} center no move edge up",
                    d.NUTRAL,
                    (100, 80),
                    (100, 100),
                    ctr,
                ),
                (f"{mess} center down move", d.DOWN, (100, 121), (100, 100), ctr),
                (f"{mess} center left down move", d.LEFT, (79, 79), (100, 100), ctr),
            ]
        ]
        for case_name, expected_direct, mouse_pos, start_pos, center_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                mouse_pos=mouse_pos,
                start_pos=start_pos,
                center_pos=center_pos,
            ):
                self.reset()
                controller = Controller()
                controller.update()
                controller.set_center(*center_pos)
                controller.draw()
                self.test_input.set_is_click(True)
                self.test_input.set_mouse_pos(start_pos[0], start_pos[1])
                controller.update()
                controller.draw()
                self.test_input.set_is_click(False)
                self.test_input.set_mouse_pos(mouse_pos[0], mouse_pos[1])
                controller.update()
                controller.draw()
                draw_pos = tuple(
                    s + c - l // 2
                    for s, c, l in zip(
                        start_pos,
                        center_pos,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                expected = [
                    ("draw_circ", *draw_pos, 20, Color.BLACK, True),
                    ("draw_circ", *draw_pos, 20, Color.WHITE, False),
                    (
                        "draw_circ",
                        *draw_pos,
                        10,
                        Color.WHITE,
                        True,
                    ),
                    ("draw_circ", *draw_pos, 20, Color.BLACK, True),
                    ("draw_circ", *draw_pos, 20, Color.WHITE, False),
                    (
                        "draw_circ",
                        *(i * 10 + s for i, s in zip(expected_direct.value, draw_pos)),
                        10,
                        Color.WHITE,
                        True,
                    ),
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.assertEqual(expected_direct, controller.get_direct())

    def test_stick_on_off(self):
        d = Direct
        test_cases = [
            (
                "tap on",
                [d.NUTRAL, d.NUTRAL],
                [(True, False, (100, 100)), (False, False, (100, 100))],
            ),
            (
                "tap move",
                [d.NUTRAL, d.RIGHT],
                [(True, False, (100, 100)), (False, False, (121, 100))],
            ),
            ("no tap move", [None], [(False, False, (121, 100))]),
            (
                "tap move and release",
                [d.NUTRAL, d.RIGHT, None],
                [
                    (True, False, (100, 100)),
                    (False, False, (121, 100)),
                    (False, True, (121, 100)),
                ],
            ),
            (
                "tap 3 move",
                [d.NUTRAL, d.NUTRAL, d.RIGHT, d.LEFT],
                [
                    (True, False, (100, 100)),
                    (False, False, (120, 100)),
                    (False, False, (121, 100)),
                    (False, False, (79, 100)),
                ],
            ),
            (
                "tap release move and tap",
                [d.NUTRAL, None, None, d.NUTRAL],
                [
                    (True, False, (100, 100)),
                    (False, True, (121, 100)),
                    (False, False, (121, 100)),
                    (True, False, (79, 100)),
                ],
            ),
            ("tap", [d.NUTRAL], [(True, False, (100, 100))]),
            ("tap2", [d.NUTRAL], [(True, False, (121, 100))]),
            (
                "tap and release",
                [d.NUTRAL, None],
                [(True, False, (121, 100)), (False, True, (121, 100))],
            ),
            (
                "tap 2 move",
                [d.NUTRAL, d.NUTRAL, d.LEFT],
                [
                    (True, False, (120, 100)),
                    (False, False, (121, 100)),
                    (False, False, (79, 100)),
                ],
            ),
            (
                "release move and tap",
                [None, None, d.NUTRAL],
                [
                    (False, True, (121, 100)),
                    (False, False, (121, 100)),
                    (True, False, (79, 100)),
                ],
            ),
        ]
        for (
            case_name,
            expected_direct_list,
            mouse_action_list,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct_list=expected_direct_list,
                mouse_action_list=mouse_action_list,
            ):
                self.reset()
                expected_list = []
                controller = Controller()
                start_pos = None
                for expected_direct, (is_click, is_release, mouse_pos) in zip(
                    expected_direct_list, mouse_action_list
                ):
                    if is_click:
                        start_pos = mouse_pos
                    self.test_input.set_is_click(is_click)
                    self.test_input.set_is_release(is_release)
                    self.test_input.set_mouse_pos(mouse_pos[0], mouse_pos[1])
                    controller.update()
                    controller.draw()
                    if expected_direct is not None:
                        expected_pos = (
                            i * 10 + s for s, i in zip(start_pos, expected_direct.value)
                        )
                        expected_list.extend(
                            [
                                ("draw_circ", *start_pos, 20, Color.BLACK, True),
                                ("draw_circ", *start_pos, 20, Color.WHITE, False),
                                ("draw_circ", *expected_pos, 10, Color.WHITE, True),
                            ]
                        )
                        self.assertEqual(expected_direct, controller.get_direct())
                    else:
                        self.assertEqual(d.NUTRAL, controller.get_direct())
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestGameCore(TestUnitParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.core = GameCore()

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.core = GameCore()

    def check(self):
        self.assertEqual(
            self.expect_view_call,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.assertEqual(
            self.expect_unit_view_call,
            self.test_unit_view.get_call_params(),
            self.test_unit_view.get_call_params(),
        )

    def put_draw_result(self, draw_action_list):
        try:
            for draw_action in draw_action_list:
                if draw_action[0] == "clear":
                    self.expect_view_call.append(draw_action)
                elif draw_action[0] == "controller":
                    expected_center = tuple(
                        s + c - l // 2
                        for s, c, l in zip(
                            draw_action[1:3],
                            draw_action[3:5],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                        )
                    )
                    expected_stick = tuple(
                        d * 10 + s
                        for s, d in zip(
                            expected_center,
                            draw_action[5].value,
                        )
                    )
                    self.expect_view_call.extend(
                        [
                            ("draw_circ", *expected_center, 20, Color.BLACK, True),
                            ("draw_circ", *expected_center, 20, Color.WHITE, False),
                            ("draw_circ", *expected_stick, 10, Color.WHITE, True),
                        ]
                    )
                elif draw_action[0] == "area":
                    s = Area.SIZE
                    self.expect_view_call.extend(
                        [
                            ("draw_rect", s * x, s * y, s, s, Color.GREEN, False)
                            for x, y in draw_action[1]
                        ]
                    )
                    self.expect_view_call.extend(
                        [
                            ("draw_rect", s * x, s * y, s, s, Color.DARK_BLUE, False)
                            for x, y in draw_action[2]
                        ]
                    )
                elif draw_action[0] == "status":
                    expected_image_center = tuple(
                        c - l // 2 + 1
                        for c, l in zip(
                            draw_action[1:3],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                        )
                    )
                    expected_loss_heart = draw_action[3][1] - draw_action[3][0]
                    expected_rest_heart = draw_action[3][0]
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_image",
                                expected_image_center[0] + i * 9,
                                expected_image_center[1] + 1,
                                *Status.LOSS_HAERT_IMAGE_POS,
                                False,
                                False,
                            )
                            for i in range(expected_loss_heart)
                        ]
                    )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_image",
                                expected_image_center[0]
                                + (expected_loss_heart + i) * 9,
                                expected_image_center[1] + 1,
                                *Status.HAERT_IMAGE_POS,
                                False,
                                False,
                            )
                            for i in range(expected_rest_heart)
                        ]
                    )
                    for pad, image_pos, num in [
                        (Status.POWER_PADDING, Weapon.IMAGE_POS, draw_action[3][2]),
                        (Status.COIN_PADDING, Coin.IMAGE_POS, draw_action[3][3]),
                    ]:
                        self.expect_view_call.extend(
                            [
                                (
                                    "draw_image",
                                    expected_image_center[0] + pad,
                                    expected_image_center[1],
                                    *image_pos,
                                    False,
                                    False,
                                ),
                                (
                                    "draw_text",
                                    expected_image_center[0] + pad + 9,
                                    expected_image_center[1] + 2,
                                    str(num),
                                ),
                            ]
                        )
                elif draw_action[0] == "console":
                    expected_pos = tuple(
                        c - l // 2 + r
                        for c, l, r in zip(
                            draw_action[1:3],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                            Console.CONSOLE_RECT[0:2],
                        )
                    )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                *expected_pos,
                                *Console.CONSOLE_RECT[2:4],
                                Color.GREEN,
                                True,
                            ),
                            (
                                "draw_rect",
                                *expected_pos,
                                *Console.CONSOLE_RECT[2:4],
                                Color.WHITE,
                                False,
                            ),
                            (
                                "draw_text",
                                expected_pos[0] + 10,
                                expected_pos[1] + 5,
                                draw_action[3],
                            ),
                            (
                                "draw_text",
                                expected_pos[0] + 10,
                                expected_pos[1] + 20,
                                "Tap to Continue",
                            ),
                        ]
                    )
                elif draw_action[0] in ["enemy_power", "fee_num"]:
                    stat = str(draw_action[3])
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_text",
                                *tuple(
                                    p - d - l
                                    for p, d, l in zip(
                                        draw_action[1:3],
                                        Unit.STAT_PADDING,
                                        (len(stat) * Unit.LETTER_SIZE, 0),
                                    )
                                ),
                                stat,
                            )
                        ]
                    )
        except Exception as e:  # pylint: disable=W0718
            print(e)
            traceback.print_exc()

    def put_unit_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "player":
                self.expect_unit_view_call.append(
                    ("draw_unit", *draw_action[1:3], 1, 0, *draw_action[3:6])
                )
            elif draw_action[0] == "fee":
                self.expect_unit_view_call.append(
                    ("draw_unit", *draw_action[1:3], 1, 3, *draw_action[3:6])
                )

    def _put_result_default_fee(self):
        for axis in [(3, 2), (2, 1), (1, 2), (2, 3)]:
            pos = tuple(p * Area.SIZE + Area.SIZE // 2 for p in axis)
            self.put_unit_draw_result(
                [
                    (
                        "fee",
                        *pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    )
                ]
            )
            self.put_draw_result([("fee_num", *pos, 1)])

    def test_draw(self):
        self.core.draw()
        self.put_draw_result(
            [
                ("clear", 100, 100),
                ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
            ]
        )
        self._put_result_default_fee()
        self.put_draw_result(
            [
                ("status", 100, 100, (3, 3, 1, Player.START_COIN_NUM)),
            ]
        )
        self.put_unit_draw_result(
            [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
        )
        self.check()

    def test_player_walk(self):
        self.test_input.set_is_click(True)
        self.test_input.set_mouse_pos(100, 100)
        self.core.update()
        self.test_input.set_is_click(False)
        self.test_input.set_mouse_pos(50, 100)
        self.core.update()

        self.core.draw()
        self.put_draw_result(
            [
                ("clear", 99, 100),
                ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
            ]
        )
        self._put_result_default_fee()
        self.put_draw_result(
            [
                ("status", 99, 100, (3, 3, 1, Player.START_COIN_NUM)),
                ("controller", 100, 100, 99, 100, Direct.LEFT),
            ]
        )
        self.put_unit_draw_result(
            [("player", 99, 100, Direct.LEFT, Direct.LEFT, False)]
        )
        self.check()

    def test_game_over(self):
        test_cases = [
            ("game over by no hp", 0, "Game Over", False, False),
            ("game over by no coin", 3, "Game Over", False, True),
            ("game clear", 3, "Game Clear", True, False),
        ]
        for case_name, hp, message, is_clear, is_no_coin in test_cases:
            with self.subTest(
                case_name=case_name,
                hp=hp,
                message=message,
                is_clear=is_clear,
                is_no_coin=is_no_coin,
            ):
                self.reset()
                self.core.field.player.hp = hp
                self.core.field.flg_clear = is_clear
                self.core.field.flg_no_coin = is_no_coin
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ("clear", 100, 100),
                        ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
                    ]
                )
                self._put_result_default_fee()
                self.put_draw_result(
                    [
                        ("status", 100, 100, (hp, 3, 1, Player.START_COIN_NUM)),
                        ("console", 100, 100, message),
                    ]
                )
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                self.assertEqual(False, self.core.is_reset())
                self.test_input.set_is_click(True)
                self.test_input.set_mouse_pos(*Console.CONSOLE_RECT[0:2])
                self.core.update()
                self.assertEqual(True, self.core.is_reset())
                self.check()


if __name__ == "__main__":
    unittest.main()
