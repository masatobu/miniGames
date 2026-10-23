from test.test_support import TestMapGenerator, TestParent, TestUnitParent

from src.main import (
    Area,
    Boss,
    Color,
    Direct,
    Enemy,
    Fee,
    Material,
    Mob,
    Player,
    PyxelUnitView,
    Resource,
    Spawner,
    Unit,
)
from src.map_generator import MaterialType, ResourceType


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
                unit = Unit(100, 100, (1, 0))
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
                            ("draw_image", *pos, image_x, 0, expected_rev, True)
                        )
                        for _ in range(5):
                            self.test_view.increment_frame()
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_set_pos(self):
        """set_pos で位置を差し替えると get_pos が新しい位置を返す。移動量（move）とは
        独立に、生成後の資材の出現位置を外から決めるために使う。"""
        self.reset()
        unit = Unit(100, 100, (1, 0))
        unit.set_pos(20, 30)
        self.assertEqual((20, 30), unit.get_pos())


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
                mob = Mob(100, 100, (1, 0))
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
                                    True,
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
                mob = Mob(100, 100, (1, 1))
                mob.set_power(mob_power)
                player = Mob(100, 100, (1, 0))
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

    def test_get_materials(self):
        """所持資材の一覧を MaterialType の定義順（木材→石→板材→レンガ）で返し、
        所持数が0の種類は含まれないことを確認する（ID-018-9 のリファクタ。
        Player.materials の非公開化に伴い Player.get_materials() を新設）。定義順とは
        逆順に拾っても返却順は定義順のままであることをあわせて確認する。Plank・Brick を
        末尾に追加しても定義順が保たれることをあわせて確認する（サイクル024-1）。Hammer を
        加えても、定義順の末尾に並ぶことをあわせて確認する（サイクル025-1）。"""
        test_cases = [
            ("no materials", [], []),
            ("single type", [(MaterialType.WOOD, 3)], [(MaterialType.WOOD, 3)]),
            (
                "definition order regardless of pickup order",
                [(MaterialType.STONE, 5), (MaterialType.WOOD, 2)],
                [(MaterialType.WOOD, 2), (MaterialType.STONE, 5)],
            ),
            (
                "zero count excluded",
                [(MaterialType.WOOD, 3), (MaterialType.STONE, 0)],
                [(MaterialType.WOOD, 3)],
            ),
            (
                "plank and brick in definition order regardless of pickup order",
                [
                    (MaterialType.BRICK, 4),
                    (MaterialType.PLANK, 2),
                    (MaterialType.STONE, 6),
                    (MaterialType.WOOD, 1),
                ],
                [
                    (MaterialType.WOOD, 1),
                    (MaterialType.STONE, 6),
                    (MaterialType.PLANK, 2),
                    (MaterialType.BRICK, 4),
                ],
            ),
            (
                "hammer last in definition order regardless of pickup order",
                [
                    (MaterialType.HAMMER, 1),
                    (MaterialType.BRICK, 4),
                    (MaterialType.PLANK, 2),
                    (MaterialType.STONE, 6),
                    (MaterialType.WOOD, 1),
                ],
                [
                    (MaterialType.WOOD, 1),
                    (MaterialType.STONE, 6),
                    (MaterialType.PLANK, 2),
                    (MaterialType.BRICK, 4),
                    (MaterialType.HAMMER, 1),
                ],
            ),
        ]
        for case_name, adds, expected in test_cases:
            with self.subTest(case_name=case_name, adds=adds, expected=expected):
                self.reset()
                player = Player(100, 100)
                for material_type, num in adds:
                    player.add_material(material_type, num)
                self.assertEqual(expected, player.get_materials())


class TestFee(TestUnitParent):
    def test_draw(self):
        test_cases = [
            (
                "default",
                MaterialType.WOOD,
                (100 - 2, 50 - PyxelUnitView.SIZE - 2),
                1,
                (100, 50),
            ),
            (
                "pos chg",
                MaterialType.WOOD,
                (-50 - 2, 200 - PyxelUnitView.SIZE - 2),
                1,
                (-50, 200),
            ),
            (
                "num chg",
                MaterialType.WOOD,
                (100 - 2, 50 - PyxelUnitView.SIZE - 2),
                5,
                (100, 50),
            ),
            (
                "num 2 letter",
                MaterialType.WOOD,
                (100 - 2 * 2, 50 - PyxelUnitView.SIZE - 2),
                10,
                (100, 50),
            ),
            (
                "num 3 letter",
                MaterialType.WOOD,
                (100 - 2 * 3, 50 - PyxelUnitView.SIZE - 2),
                100,
                (100, 50),
            ),
            (
                "stone type",
                MaterialType.STONE,
                (100 - 2, 50 - PyxelUnitView.SIZE - 2),
                1,
                (100, 50),
            ),
        ]
        for (
            case_name,
            fee_type,
            expected_pos,
            num,
            pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                fee_type=fee_type,
                expected_pos=expected_pos,
                num=num,
                pos=pos,
            ):
                self.reset()
                self.test_map_generator.set_fee_type(fee_type)
                fee = Fee(*pos)
                fee.set_num(num)
                fee.draw()
                expected_unit = [
                    (
                        "draw_unit",
                        *pos,
                        *Fee.IMAGE_POS_MAP[fee_type],
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    )
                ]
                self.assertEqual(
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )
                expected_view = [("draw_text", *expected_pos, str(num), Color.WHITE)]
                self.assertEqual(
                    expected_view,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_draw_image_by_type(self):
        # 開放対象アイコンは資材の絵柄（Material.IMAGE_POS_MAP）の 1 つ右の絵柄
        test_cases = [
            ("wood", MaterialType.WOOD, (1, 11)),
            ("stone", MaterialType.STONE, (1, 15)),
            ("plank", MaterialType.PLANK, (1, 17)),
            ("brick", MaterialType.BRICK, (1, 19)),
            ("hammer", MaterialType.HAMMER, (1, 21)),
        ]
        for case_name, fee_type, expected_image_pos in test_cases:
            with self.subTest(case_name=case_name, fee_type=fee_type):
                self.reset()
                self.test_map_generator.set_fee_type(fee_type)
                fee = Fee(100, 50)
                fee.set_num(1)
                fee.draw()
                expected_unit = [
                    (
                        "draw_unit",
                        100,
                        50,
                        *expected_image_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    )
                ]
                self.assertEqual(
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_create_and_draw_in_void_area(self):
        self.reset()
        self.test_map_generator.set_fee_ret_zero(True)
        fee = Fee(100, 50)
        self.assertEqual(0, fee.get_num())
        self.assertIsNone(fee.get_type())
        with self.assertRaises(TypeError):
            fee.draw()

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
                expected_view = [("draw_text", *expected_pos, str(power), Color.WHITE)]
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
                expected_view = [("draw_text", *expected_pos, str(power), Color.WHITE)]
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


class TestResource(TestUnitParent):
    def test_spot(self):
        """接触を継続した場合（毎フレーム hit() を呼ぶ）の基本遷移（点滅 → 採取済み）を確認する。
        中断（サイクル 016-4）の境界値・再開時の進行保持は test_suspend で個別に確認する。"""
        tree_pos, tree_harvested_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE]
        h = Resource.HARVEST_FRAMES
        test_cases = [
            ("not hit yet", 0, False, False, tree_pos),
            ("hit", 0, True, True, tree_pos),
            ("not harvested yet", h - 1, False, True, tree_pos),
            ("harvested", h, False, False, tree_harvested_pos),
            (
                "hit again after harvested",
                h,
                True,
                False,
                tree_harvested_pos,
            ),
        ]
        for (
            case_name,
            touches,
            extra_hit,
            expected_blink,
            expected_image_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                touches=touches,
                extra_hit=extra_hit,
                expected_blink=expected_blink,
                expected_image_pos=expected_image_pos,
            ):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                resource = Resource(100, 50)
                for _ in range(touches):
                    resource.hit()
                    resource.update()
                if extra_hit:
                    resource.hit()
                resource.draw()
                expected = [
                    (
                        "draw_unit",
                        100,
                        50,
                        *expected_image_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        expected_blink,
                    )
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_draw_by_resource_type(self):
        """資源の種類（Tree / Rock）によって、採取可能・採取済みの絵柄が変わることを
        確認する（サイクル 023-5）。Tree は従来どおり Resource.IMAGE_POS_MAP の
        ResourceType.TREE の値、Rock は専用の絵柄 (1, 12) / (1, 13)
        （ResourceType.ROCK の値）で描画される。点滅・進行の遷移自体は test_spot で
        検証済みのため、ここでは種類ごとの絵柄の違いのみを確認する。"""
        tree_pos, tree_harvested_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE]
        rock_pos, rock_harvested_pos = Resource.IMAGE_POS_MAP[ResourceType.ROCK]
        h = Resource.HARVEST_FRAMES
        test_cases = [
            ("tree not harvested", MaterialType.WOOD, 0, tree_pos),
            ("tree harvested", MaterialType.WOOD, h, tree_harvested_pos),
            ("rock not harvested", MaterialType.STONE, 0, rock_pos),
            ("rock harvested", MaterialType.STONE, h, rock_harvested_pos),
        ]
        for case_name, material_type, touches, expected_image_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                material_type=material_type,
                touches=touches,
                expected_image_pos=expected_image_pos,
            ):
                self.reset()
                self.test_map_generator.set_material_type(material_type)
                resource = Resource(100, 50)
                for _ in range(touches):
                    resource.hit()
                    resource.update()
                resource.draw()
                expected = [
                    (
                        "draw_unit",
                        100,
                        50,
                        *expected_image_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    )
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_regenerate(self):
        """採取済みから再生フレーム数 (Resource.REGEN_FRAMES) の経過で採取可能な絵柄に戻り、
        再び hit() すると採取が再始動すること（一巡）を確認する。再生は接触の有無によらず
        進む（中断・サイクル016-4の SUSPEND_FRAMES とは独立）ため、更新はすべて hit() を
        伴わない update() のみで進める"""
        tree_pos, tree_harvested_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE]
        h = Resource.HARVEST_FRAMES
        r = Resource.REGEN_FRAMES
        test_cases = [
            (
                "not regenerated yet",
                r - 1,
                0,
                False,
                tree_harvested_pos,
            ),
            (
                "regenerated",
                r,
                0,
                False,
                tree_pos,
            ),
            (
                "hit again after regenerate",
                r,
                1,
                True,
                tree_pos,
            ),
            (
                "harvested again after regenerate",
                r,
                h,
                False,
                tree_harvested_pos,
            ),
        ]
        for (
            case_name,
            regen_waits,
            retouches,
            expected_blink,
            expected_image_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                regen_waits=regen_waits,
                retouches=retouches,
                expected_blink=expected_blink,
                expected_image_pos=expected_image_pos,
            ):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                resource = Resource(100, 50)
                for _ in range(h):
                    resource.hit()
                    resource.update()
                for _ in range(regen_waits):
                    resource.update()
                for _ in range(retouches):
                    resource.hit()
                    resource.update()
                resource.draw()
                expected = [
                    (
                        "draw_unit",
                        100,
                        50,
                        *expected_image_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        expected_blink,
                    )
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_suspend(self):
        """重なりが途切れて猶予フレームを超えると採取の進行と点滅が止まり（中断）、
        中断中は待っても採取済みにならないこと、再び接触すると中断前の進行を保持した
        まま続きから進むことを確認する。猶予フレーム数 (Resource.SUSPEND_FRAMES) は
        「最後に hit() が呼ばれてからの経過フレーム数」で判定される"""
        tree_pos, tree_harvested_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE]
        h = Resource.HARVEST_FRAMES
        g = Resource.SUSPEND_FRAMES
        test_cases = [
            (
                "within grace after last touch",
                [True] + [False] * (g - 1),
                True,
                tree_pos,
            ),
            (
                "beyond grace after last touch",
                [True] + [False] * g,
                False,
                tree_pos,
            ),
            (
                "progress frozen while suspended",
                [True] + [False] * g + [False] * h,
                False,
                tree_pos,
            ),
            (
                "resumes and retains progress after suspend",
                [True] + [False] * g + [True] * (h - g),
                False,
                tree_harvested_pos,
            ),
        ]
        for case_name, hit_flags, expected_blink, expected_image_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_blink=expected_blink,
                expected_image_pos=expected_image_pos,
            ):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                resource = Resource(100, 50)
                for do_hit in hit_flags:
                    if do_hit:
                        resource.hit()
                    resource.update()
                resource.draw()
                expected = [
                    (
                        "draw_unit",
                        100,
                        50,
                        *expected_image_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        expected_blink,
                    )
                ]
                self.assertEqual(
                    expected,
                    self.test_unit_view.get_call_params(),
                    self.test_unit_view.get_call_params(),
                )

    def test_spawn_materials(self):
        """採取完了の瞬間だけ資源と同じ位置に資材が1つ生成され、それ以外のフレームや
        再生の途中では生成されないことを確認する（サイクル 017-5）。あわせて、資源・資材が
        自エリアに対応する種類（木→木材 / 岩→石。資源の無いエリアは None）を保持し、
        資源から出る資材の種類が資源のエリアの種類と一致することを確認する（サイクル 017-4）。
        さらに、資材が持つ個数が資源のエリアの material_num と一致することを確認する
        （サイクル 017-11）。
        """
        h = Resource.HARVEST_FRAMES
        r = Resource.REGEN_FRAMES
        test_cases = [
            ("not harvested yet", [True] * (h - 1), False, MaterialType.WOOD),
            ("just harvested", [True] * h, True, MaterialType.WOOD),
            ("harvested continues", [True] * h + [False], False, MaterialType.WOOD),
            (
                "harvested again after regenerate",
                [True] * h + [False] * r + [True] * h,
                True,
                MaterialType.WOOD,
            ),
            ("stone area", [True] * h, True, MaterialType.STONE),
            ("no resource area", [True] * h, True, None),
        ]
        resource_type_map = {
            MaterialType.WOOD: ResourceType.TREE,
            MaterialType.STONE: ResourceType.ROCK,
            None: None,
        }
        for case_name, hit_flags, expected_spawn, material_type in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_spawn=expected_spawn,
                material_type=material_type,
            ):
                self.reset()
                self.test_map_generator.set_material_type(material_type)
                self.test_map_generator.set_material_ret_zero(False)
                resource = Resource(100, 50)
                self.assertEqual(resource_type_map[material_type], resource.get_type())
                for do_hit in hit_flags:
                    if do_hit:
                        resource.hit()
                    resource.update()
                material = resource.spawn_materials()
                if not expected_spawn:
                    self.assertIsNone(material)
                    continue
                self.assertEqual(True, isinstance(material, Material))
                self.assertEqual(
                    Material.IMAGE_POS_MAP.get(material_type), material.image_pos
                )
                self.assertEqual(resource.get_pos(), material.get_pos())
                self.assertEqual(material_type, material.get_type())
                area_axis = tuple(p // Area.SIZE for p in resource.get_pos())
                self.assertEqual(
                    TestMapGenerator.calc_area_level(*area_axis), material.get_num()
                )


class TestMaterial(TestUnitParent):
    def test_get_num(self):
        """生成したエリアに対応する資材の個数（material_num）を `get_num()` で保持し、
        生成後に位置を変えても個数は変わらないことを確認する（`test_get_type` と同じく
        生成時に確定させる。サイクル 017-11）。"""
        s = Area.SIZE
        test_cases = [
            ("resource area", 1, False, (2, 2), None),
            ("resource area lv10", 10, False, (5, 5), None),
            ("no resource area", 0, True, (2, 2), None),
            ("num fixed after move", 1, False, (2, 2), (5, 5)),
        ]
        for (
            case_name,
            expected_num,
            zero_flg,
            area_axis,
            moved_area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_num=expected_num,
                zero_flg=zero_flg,
                area_axis=area_axis,
                moved_area_axis=moved_area_axis,
            ):
                self.reset()
                self.test_map_generator.set_material_ret_zero(zero_flg)
                pos = tuple(p * s + s // 2 for p in area_axis)
                material = Material(*pos)
                if moved_area_axis is not None:
                    self.test_map_generator.set_material_ret_zero(not zero_flg)
                    material.set_pos(*(p * s + s // 2 for p in moved_area_axis))
                self.assertEqual(expected_num, material.get_num())

    def test_get_type(self):
        """生成したエリアに対応する資材の種類を保持し、生成後に位置を変えても
        種類は変わらないことを確認する（`Enemy.area_axis_pos` と同じく生成時に確定させる。
        サイクル 017-4）。"""
        s = Area.SIZE
        test_cases = [
            ("wood area", MaterialType.WOOD, (2, 2), None),
            ("stone area", MaterialType.STONE, (5, 5), None),
            ("no resource area", None, (0, 0), None),
            ("type fixed after move", MaterialType.WOOD, (2, 2), (5, 5)),
        ]
        for (
            case_name,
            material_type,
            area_axis,
            moved_area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                material_type=material_type,
                area_axis=area_axis,
                moved_area_axis=moved_area_axis,
            ):
                self.reset()
                self.test_map_generator.set_material_type(material_type)
                pos = tuple(p * s + s // 2 for p in area_axis)
                material = Material(*pos)
                if moved_area_axis is not None:
                    other_type = (
                        MaterialType.STONE
                        if material_type == MaterialType.WOOD
                        else MaterialType.WOOD
                    )
                    self.test_map_generator.set_material_type(other_type)
                    material.set_pos(*(p * s + s // 2 for p in moved_area_axis))
                self.assertEqual(material_type, material.get_type())
