import os
import random
import sys
import unittest
from unittest.mock import patch

for p in ["../src/", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from test_pyxel_convert_send_framework import (  # pylint: disable=C0413
    TestParent,
    TestFieldParent,
)
from framework import (  # pylint: disable=C0413
    Node,
    Image,
    Direct,
    Color,
    PyxelFieldView,
)
from main import (  # pylint: disable=C0413
    GameCore,
    Field,
    Action,
    Cursor,
    Scout,
    GameParameter,
)
from field_nodes import (  # pylint: disable=C0413
    UnitPlayer,
    UnitEnemy,
    BulletPlayer,
    BulletEnemy,
    Convert,
    Split,
    Curve,
    Merge,
)


class TestPyxelFieldView(TestParent):
    def setUp(self):
        self.expected = []
        return super().setUp()

    def tearDown(self):
        self.assertEqual(
            self.expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        return super().tearDown()

    def append_expected(self, params, set_col):
        if set_col is not None:
            self.expected.append(
                (
                    "set_pal",
                    [Color.WHITE, set_col],
                )
            )
        self.expected.append(params)
        if set_col is not None:
            self.expected.append(
                (
                    "set_pal",
                    [],
                )
            )

    def test_draw_node(self):
        test_cases = [
            ("no change", None),
            ("red", Color.NODE_RED),
            ("blue", Color.NODE_BLUE),
            ("green", Color.NODE_GREEN),
        ]
        for case_name, set_col in test_cases:
            with self.subTest(case_name=case_name, set_col=set_col):
                self.setUp()
                view = PyxelFieldView()
                view.draw_node(1, 1, Node.UNIT_PLAYER, Direct.RIGHT, set_col)
                self.append_expected(
                    (
                        "draw_image",
                        8 * 1 + PyxelFieldView.FIELD_OFFSET_X,
                        8 * 1 + PyxelFieldView.FIELD_OFFSET_Y,
                        4,
                        1,
                        Direct.RIGHT,
                    ),
                    set_col,
                )
                self.tearDown()

    def test_draw_object(self):
        test_cases = [
            ("no change", None),
            ("red", Color.NODE_RED),
            ("blue", Color.NODE_BLUE),
            ("green", Color.NODE_GREEN),
        ]
        for case_name, set_col in test_cases:
            with self.subTest(case_name=case_name, set_col=set_col):
                self.setUp()
                view = PyxelFieldView()
                view.draw_object(1, 1, Image.PLAYER_BULLET, set_col)
                self.append_expected(
                    (
                        "draw_image",
                        1 - 8 // 2 + PyxelFieldView.FIELD_OFFSET_X,
                        1 - 8 // 2 + PyxelFieldView.FIELD_OFFSET_Y,
                        5,
                        0,
                        Direct.RIGHT,
                    ),
                    set_col,
                )
                self.tearDown()


class TestField(TestFieldParent):
    def setUp(self):
        super().setUp()
        self.field = field = Field(2, [Color.NODE_BLUE] * 6)
        unit = UnitPlayer(0, 6)
        field.unit_list = [unit]
        field.node_map = {(0, 6): unit}

    @patch.object(Field, "_get_random_new_player_y_pos")
    @patch.object(Field, "_get_random_new_enemy_y_pos")
    def test_initial_unit(self, mock_func_enemy, mock_func_player):
        mock_func_player.return_value = 3
        mock_func_enemy.return_value = [2, 1]
        self.field = Field(2, [Color.NODE_BLUE])
        self.assertEqual(3, self.field.unit_list[0].tile_y)
        self.assertEqual(2, self.field.unit_list[1].tile_y)

    def test_bullet_out_of_field(self):
        test_cases = [
            (
                "right",
                lambda x: x < PyxelFieldView.FIELD_WIDTH + 8,
                lambda y: True,
                Direct.RIGHT,
                UnitPlayer,
            ),
            (
                "down",
                lambda x: True,
                lambda y: y < PyxelFieldView.FIELD_HEIGHT + 8,
                Direct.DOWN,
                UnitPlayer,
            ),
            (
                "left",
                lambda x: x > -8,
                lambda y: True,
                Direct.LEFT,
                UnitPlayer,
            ),
            (
                "up",
                lambda x: True,
                lambda y: y > -8,
                Direct.UP,
                UnitPlayer,
            ),
            (
                "enemy",
                lambda x: x > -8,
                lambda y: True,
                Direct.LEFT,
                UnitEnemy,
            ),
        ]
        for case_name, fcx, fcy, d, cls in test_cases:
            with self.subTest(case_name=case_name, check_x=fcx, check_y=fcy, direct=d):
                self.setUp()
                unit = cls(0, 6)
                self.field.unit_list = [unit]
                self.field.node_map = {(0, 6): unit}
                unit.tile_x, unit.tile_y = (
                    PyxelFieldView.FIELD_TILE_WIDTH // 2,
                    PyxelFieldView.FIELD_TILE_HEIGHT // 2,
                )
                unit.interval = cls.SHOT_INTERVAL
                unit.direct = d
                self.field.update()
                self.assertEqual(1, len(self.field.bullet_map))
                unit.interval = -10000000
                bullet = next(iter(self.field.bullet_map.values()))
                while (
                    len(self.field.bullet_map) > 0 and fcx(bullet.x) and fcy(bullet.y)
                ):
                    last_x, last_y = bullet.x, bullet.y
                    self.field.update()
                self.assertEqual(0, len(self.field.bullet_map))
                self.assertEqual(True, fcx(last_x) and fcy(last_y))
                self.tearDown()

    def test_build(self):
        test_cases = (
            [
                (
                    "no build",
                    [],
                    [],
                    [],
                ),
                (
                    "build curve",
                    [(1, 0, Node.UNIT_CURVE, Direct.RIGHT, None)],
                    [True],
                    [(Action.CURVE, (1, 0))],
                ),
                (
                    "build curve rev",
                    [(1, 0, Node.UNIT_CURVE_REV, Direct.RIGHT, None)],
                    [True],
                    [(Action.CURVE_REV, (1, 0))],
                ),
                (
                    "build convert",
                    [(1, 0, Node.UNIT_CONVERT, Direct.RIGHT, Color.NODE_BLUE)],
                    [True],
                    [(Action.CONVERT, (1, 0))],
                ),
                (
                    "build split",
                    [(1, 0, Node.UNIT_SPLIT, Direct.RIGHT, None)],
                    [True],
                    [(Action.SPLIT, (1, 0))],
                ),
                (
                    "build merge",
                    [(1, 0, Node.UNIT_MERGE, Direct.RIGHT, None)],
                    [True],
                    [(Action.MERGE, (1, 0))],
                ),
                (
                    "build 2",
                    [
                        (1, 0, Node.UNIT_CURVE, Direct.RIGHT, None),
                        (3, 0, Node.UNIT_CONVERT, Direct.RIGHT, Color.NODE_BLUE),
                    ],
                    [True, True],
                    [(Action.CURVE, (1, 0)), (Action.CONVERT, (3, 0))],
                ),
                (
                    "cant build same place",
                    [(1, 0, Node.UNIT_CURVE, Direct.RIGHT, None)],
                    [True, False],
                    [(Action.CURVE, (1, 0)), (Action.CURVE, (1, 0))],
                ),
            ]
            + [
                (
                    f"cant build by {d} of place",
                    [(1, 0, Node.UNIT_CURVE, Direct.RIGHT, None)],
                    [True, False],
                    [
                        (Action.CURVE, (1, 0)),
                        (Action.CURVE, (1 + d.value[0], 0 + d.value[1])),
                    ],
                )
                for d in Direct
            ]
            + [
                (
                    f"cant build edge place: {pos}",
                    [],
                    [False],
                    [
                        (Action.CURVE, pos),
                    ],
                )
                for pos in [
                    (PyxelFieldView.FIELD_TILE_WIDTH - 2, 0),
                    (PyxelFieldView.FIELD_TILE_WIDTH - 1, 0),
                    (PyxelFieldView.FIELD_TILE_WIDTH - 2, 1),
                    (
                        PyxelFieldView.FIELD_TILE_WIDTH - 1,
                        PyxelFieldView.FIELD_TILE_HEIGHT - 1,
                    ),
                ]
            ]
            + [
                (
                    f"cant build by {d} of player",
                    [],
                    [False],
                    [
                        (Action.CURVE, (d.value[0], 6 + d.value[1])),
                    ],
                )
                for d in [Direct.UP, Direct.DOWN, Direct.LEFT]
            ]
        )
        for (
            case_name,
            expected_nodes,
            expected_ret,
            actions,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_nodes=expected_nodes,
                expected_ret=expected_ret,
                actions=actions,
            ):
                self.setUp()
                for i, dat in enumerate(actions):
                    self.assertEqual(expected_ret[i], self.field.build(dat[0], *dat[1]))
                self.field.draw()
                expected = [
                    "draw_tilemap",
                    ("set_clip", PyxelFieldView.get_rect()),
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                expected_field = [
                    (
                        "draw_node",
                        0,
                        6,
                        Node.UNIT_PLAYER,
                        Direct.RIGHT,
                        Color.NODE_BLUE,
                    ),
                    *[("draw_node", *param) for param in expected_nodes],
                ]
                self.assertEqual(
                    expected_field,
                    self.test_field_view.get_call_params(),
                    self.test_field_view.get_call_params(),
                )
                self.tearDown()

    def test_bullet_hit_node(self):
        test_cases = [
            [
                (
                    f"{enemy_color}: " + "right",
                    Direct.RIGHT,
                    (0, 2),
                    lambda x: x < 2 * 8 + 8 // 2,
                    lambda y: True,
                    enemy_color,
                ),
                (
                    f"{enemy_color}: " + "down",
                    Direct.DOWN,
                    (2, 0),
                    lambda x: True,
                    lambda y: y < 2 * 8 + 8 // 2,
                    enemy_color,
                ),
                (
                    f"{enemy_color}: " + "left",
                    Direct.LEFT,
                    (4, 2),
                    lambda x: x > 2 * 8 + 8 // 2,
                    lambda y: True,
                    enemy_color,
                ),
                (
                    f"{enemy_color}: " + "up",
                    Direct.UP,
                    (2, 4),
                    lambda x: True,
                    lambda y: y > 2 * 8 + 8 // 2,
                    enemy_color,
                ),
            ]
            for enemy_color in [None, Color.NODE_BLUE, Color.NODE_RED, Color.NODE_GREEN]
        ]
        for case_name, d, s_pos, fcx, fcy, enemy_color in sum(test_cases, []):
            with self.subTest(
                case_name=case_name,
                direct=d,
                start_pos=s_pos,
                check_x=fcx,
                check_y=fcy,
                enemy_color=enemy_color,
            ):
                self.setUp()
                unit = self.field.unit_list[0]
                unit.tile_x, unit.tile_y = s_pos
                unit.interval = UnitPlayer.SHOT_INTERVAL
                unit.direct = d
                if enemy_color is not None:
                    enemy = UnitEnemy(2, 2)
                    enemy.color = enemy_color
                    self.field.unit_list.append(enemy)
                    self.field.node_map[(2, 2)] = enemy
                    enemy.interval = -10000000
                else:
                    self.field.build(Action.CONVERT, 2, 2)
                self.field.update()
                self.assertEqual(1, len(self.field.bullet_map))
                unit.interval = -10000000
                bullet = next(iter(self.field.bullet_map.values()))
                while (
                    len(self.field.bullet_map) > 0 and fcx(bullet.x) and fcy(bullet.y)
                ):
                    last_x = bullet.x
                    last_y = bullet.y
                    self.field.update()
                self.assertEqual(0, len(self.field.bullet_map))
                self.assertEqual(True, fcx(last_x) and fcy(last_y))
                if enemy_color is not None:
                    if enemy_color == Color.NODE_BLUE:
                        self.assertEqual(enemy.MAX_HP - 1, enemy.hp)
                    else:
                        self.assertEqual(enemy.MAX_HP, enemy.hp)
                self.tearDown()

    def _get_player_bullet(self, bullet_map):
        return len(
            [
                bullet
                for bullet in bullet_map.values()
                if isinstance(bullet, BulletPlayer)
            ]
        )

    def test_get_random_new_player_y_pos(self):
        hgt = PyxelFieldView.FIELD_TILE_HEIGHT
        ret = self.field._get_random_new_player_y_pos()  # pylint: disable=W0212
        self.assertEqual(True, 0 <= ret < hgt)

    def test_get_random_new_enemy_y_pos(self):
        hgt = PyxelFieldView.FIELD_TILE_HEIGHT
        f_get_num_list = lambda num_min, num_max, split_num: [  # pylint: disable=C3001
            i for i in range(num_min, num_max) if i % split_num == 0
        ]
        test_cases = [
            ("all", f_get_num_list(0, hgt, 2), set(), 2),
            (
                "rest 2",
                f_get_num_list(hgt - 4, hgt, 2),
                set(f_get_num_list(0, hgt - 4, 2)),
                2,
            ),
            (
                "rest 1",
                f_get_num_list(hgt - 2, hgt, 2),
                set(f_get_num_list(0, hgt - 2, 2)),
                2,
            ),
            (
                "rest 0",
                [],
                set(f_get_num_list(0, hgt, 2)),
                2,
            ),
            ("3 split", f_get_num_list(0, hgt, 3), set(), 3),
            (
                "3 split rest 1",
                f_get_num_list(hgt - 3, hgt, 3),
                set(f_get_num_list(0, hgt - 3, 3)),
                3,
            ),
        ]
        for case_name, expected_list, input_set, split_num in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                input_set=input_set,
                split_num=split_num,
            ):
                self.setUp()
                self.field.enemy_split_num = split_num
                ret = self.field._get_random_new_enemy_y_pos(  # pylint: disable=W0212
                    input_set
                )
                if len(expected_list) >= 2:
                    self.assertEqual(2, len(ret))
                    self.assertEqual(True, all(i in expected_list for i in ret))
                    self.assertEqual(True, ret[0] != ret[1])
                elif len(expected_list) == 1:
                    self.assertEqual(list(expected_list), ret)
                else:
                    self.assertEqual(0, len(ret))
                self.tearDown()

    @patch.object(Field, "_get_random_new_enemy_y_pos")
    def test_unit_kill(self, mock_random_choices):
        test_cases = [
            ("1st kill case 1", [2, 4], [2, 4], [6]),
            ("1st kill case 2", [8, 10], [8, 10], [6]),
            ("2nd kill", [8, 0, 2], [0, 2], [6, 8]),
            ("3rd kill", [8, 10, 0, 2], [0, 2], [6, 8, 10]),
            (
                "kill in full",
                [
                    i
                    for i in range(PyxelFieldView.FIELD_TILE_HEIGHT)
                    if i % 2 == 0 and i != 6
                ],
                [PyxelFieldView.FIELD_TILE_HEIGHT - 2],
                [i for i in range(PyxelFieldView.FIELD_TILE_HEIGHT - 2) if i % 2 == 0],
            ),
        ]
        for case_name, expected_enemies_y, ret_pos_list, first_enemies_y in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_enemies_y=expected_enemies_y,
                ret_pos_list=ret_pos_list,
                first_enemies_y=first_enemies_y,
            ):
                mock_random_choices.return_value = ret_pos_list
                self.setUp()
                enemy_list = [
                    UnitEnemy(11, y, Color.NODE_BLUE) for y in first_enemies_y
                ]
                self.field.unit_list.extend(enemy_list)
                for enemy in enemy_list:
                    self.field.node_map[(11, enemy.tile_y)] = enemy
                    enemy.interval = -10000000
                while self._get_player_bullet(self.field.bullet_map) < enemy_list[0].hp:
                    self.field.update()
                self.field.unit_list[0].interval = -10000000
                self.assertEqual(len(enemy_list) + 1, len(self.field.unit_list))
                self.assertEqual(len(enemy_list) + 1, len(self.field.node_map))
                while self._get_player_bullet(self.field.bullet_map) > 0:
                    self.field.update()
                self.assertEqual(len(expected_enemies_y) + 1, len(self.field.unit_list))
                self.assertEqual(len(expected_enemies_y) + 1, len(self.field.node_map))
                self.assertEqual(
                    expected_enemies_y,
                    [
                        unit.tile_y
                        for unit in self.field.unit_list
                        if isinstance(unit, UnitEnemy)
                    ],
                )
                mock_random_choices.assert_called_with(set(first_enemies_y))
                self.tearDown()

    @patch.object(Field, "_get_random_new_enemy_y_pos")
    def test_unit_kill_exception(self, mock_random_choices):
        mock_random_choices.return_value = [1, 2]
        enemy_list = [UnitEnemy(11, 6, Color.NODE_BLUE)]
        self.field.unit_list.extend(enemy_list)
        for enemy in enemy_list:
            self.field.node_map[(11, enemy.tile_y)] = enemy
            enemy.interval = -10000000
        self.field.node_map[(11, 1)] = Convert(11, 1)
        while self._get_player_bullet(self.field.bullet_map) < enemy_list[0].hp:
            self.field.update()
        self.field.unit_list[0].interval = -10000000
        self.assertEqual(len(enemy_list) + 1, len(self.field.unit_list))
        self.assertEqual(len(enemy_list) + 2, len(self.field.node_map))
        with self.assertRaises(KeyError):
            while self._get_player_bullet(self.field.bullet_map) > 0:
                self.field.update()

    @patch.object(Field, "_get_random_new_enemy_y_pos")
    def test_enemy_generate(self, mock_random_choices):
        test_cases = [
            (
                "basic",
                [[(4, Color.NODE_RED), (6, Color.NODE_GREEN)]],
                [2, 4, 6],
                [Color.NODE_BLUE, Color.NODE_RED, Color.NODE_GREEN],
                1,
            ),
            (
                "color list less than candidate",
                [[(4, Color.NODE_RED)]],
                [2, 4, 6],
                [Color.NODE_BLUE, Color.NODE_RED],
                1,
            ),
            ("no candidate", [[]], [2, 4, 6], [Color.NODE_BLUE], 1),
            (
                "second times",
                [
                    [(4, Color.NODE_RED), (6, Color.NODE_GREEN)],
                    [(6, Color.NODE_GREEN), (2, Color.NODE_BLUE)],
                ],
                [2, 4, 6],
                [Color.NODE_BLUE, Color.NODE_RED, Color.NODE_GREEN],
                2,
            ),
        ]
        for case_name, expected, ret_pos_list, color, times in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                ret_pos_list=ret_pos_list,
                color=color,
                times=times,
            ):
                mock_random_choices.side_effect = [
                    ret_pos_list[0:2],
                    ret_pos_list[0:2],
                    ret_pos_list[1:],
                    ret_pos_list[0:1],
                ]
                self.setUp()
                self.field = Field(2, color)
                enemy = self.field.unit_list[1]
                self.assertEqual(color[0], enemy.color)
                self.assertEqual(ret_pos_list[0], enemy.tile_y)
                for i in range(times):
                    enemy = self.field.unit_list[1]
                    enemy.hp = 0
                    del self.field.node_map[enemy.get_tile_pos()]
                    self.field.update()
                    self.assertEqual(
                        expected[i],
                        [
                            (unit.tile_y, unit.color)
                            for unit in self.field.unit_list
                            if isinstance(unit, UnitEnemy)
                        ],
                    )
                self.tearDown()

    def _bullet_hit_node(
        self, unit_cls, unit_status, bullet_list, action, mainte_times
    ):
        unit = unit_cls(*unit_status[0:2])
        self.field.unit_list = [unit]
        self.field.node_map = {(unit_status[0], unit_status[1]): unit}
        unit.direct = unit_status[2]
        unit.interval = unit.SHOT_INTERVAL
        self.field.bullet_map = {}
        for bullet in bullet_list:
            self.field.bullet_map[bullet.get_tile_pos()] = bullet
        self.field.build(action, 2, 2)
        for _ in range(mainte_times):
            self.field.node_map[(2, 2)].mainte()
        self.field.update()
        self.assertEqual(1 + len(bullet_list), len(self.field.bullet_map))
        unit.interval = -10000000
        unit_bullet = self.field.bullet_map[
            tuple(x + y for x, y in zip(unit_status[0:2], unit_status[2].value))
        ]
        while unit_bullet.get_tile_pos() != (2, 2):
            self.field.update()
        self.field.draw()

    def _check_result(
        self, expected_list, unit_status, unit_cls, field_node, node_color
    ):
        expected_field = []
        self.assertEqual(len(expected_list), len(self.field.bullet_map))
        for expected in expected_list:
            bullet = self.field.bullet_map[tuple(expected[2:4])]
            self.assertEqual(expected[0:2], bullet.get_pos())
            self.assertEqual(expected[4], bullet.direct)
            self.assertEqual(expected[5], bullet.color)
            expected_field.append(
                (
                    "draw_object",
                    *expected[0:2],
                    Image.PLAYER_BULLET,
                    expected[5],
                )
            )
        expected_field.extend(
            [
                (
                    "draw_node",
                    *unit_status[0:2],
                    Node.UNIT_PLAYER if unit_cls is UnitPlayer else Node.UNIT_ENEMY,
                    unit_status[2],
                    unit_status[3],
                ),
                (
                    "draw_node",
                    2,
                    2,
                    field_node,
                    Direct.RIGHT,
                    node_color,
                ),
            ]
        )
        self.assertEqual(
            expected_field,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )

    def test_bullet_hit_curve(self):
        test_cases = [
            (
                "hit curve",
                [
                    (
                        1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(1),
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        3,
                        2,
                        Direct.RIGHT,
                        Color.NODE_BLUE,
                    )
                ],
                [],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "hit bullet",
                [],
                [BulletPlayer(3, 1, Direct.DOWN)],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "miss curve",
                [],
                [],
                UnitPlayer,
                (0, 2, Direct.RIGHT, Color.NODE_BLUE),
            ),
            (
                "[enemy] hit curve",
                [],
                [],
                UnitEnemy,
                (2, 4, Direct.UP, Color.NODE_RED),
            ),
            (
                "[enemy] miss curve",
                [],
                [],
                UnitEnemy,
                (0, 2, Direct.RIGHT, Color.NODE_RED),
            ),
        ]
        for case_name, expected_list, bullet_list, unit_cls, unit_status in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                bullet_list=bullet_list,
                unit_cls=unit_cls,
                unit_status=unit_status,
            ):
                self.setUp()
                self._bullet_hit_node(
                    unit_cls,
                    unit_status,
                    bullet_list,
                    Action.CURVE,
                    0,
                )
                self._check_result(
                    expected_list,
                    unit_status,
                    unit_cls,
                    Node.UNIT_CURVE,
                    None,
                )
                self.tearDown()

    def test_bullet_hit_convert(self):
        test_cases = [
            (
                "hit convert from up",
                [
                    (
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        -1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(-1),
                        2,
                        1,
                        Direct.UP,
                        Color.NODE_BLUE,
                    )
                ],
                Color.NODE_BLUE,
                [],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
                0,
            ),
            (
                "hit convert from down",
                [
                    (
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(1),
                        2,
                        3,
                        Direct.DOWN,
                        Color.NODE_BLUE,
                    )
                ],
                Color.NODE_BLUE,
                [],
                UnitPlayer,
                (2, 0, Direct.DOWN, Color.NODE_BLUE),
                0,
            ),
            (
                "hit convert from right",
                [
                    (
                        1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(1),
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        3,
                        2,
                        Direct.RIGHT,
                        Color.NODE_BLUE,
                    )
                ],
                Color.NODE_BLUE,
                [],
                UnitPlayer,
                (0, 2, Direct.RIGHT, Color.NODE_BLUE),
                0,
            ),
            (
                "hit convert from left",
                [
                    (
                        -1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(-1),
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        1,
                        2,
                        Direct.LEFT,
                        Color.NODE_BLUE,
                    )
                ],
                Color.NODE_BLUE,
                [],
                UnitPlayer,
                (4, 2, Direct.LEFT, Color.NODE_BLUE),
                0,
            ),
            (
                "hit bullet",
                [],
                Color.NODE_BLUE,
                [BulletPlayer(1, 1, Direct.RIGHT)],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
                0,
            ),
            (
                "[enemy] hit convert",
                [],
                Color.NODE_BLUE,
                [],
                UnitEnemy,
                (2, 4, Direct.UP, Color.NODE_RED),
                0,
            ),
        ] + [
            (
                f"hit convert {color} with {count} times",
                [
                    (
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        -1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(-1),
                        2,
                        1,
                        Direct.UP,
                        color,
                    )
                ],
                color,
                [],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
                count,
            )
            for count, color in [
                (1, Color.NODE_RED),
                (2, Color.NODE_GREEN),
                (3, Color.NODE_BLUE),
            ]
        ]
        for (
            case_name,
            expected_list,
            expected_unit_color,
            bullet_list,
            unit_cls,
            unit_status,
            mainte_times,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                expected_unit_color=expected_unit_color,
                bullet_list=bullet_list,
                unit_cls=unit_cls,
                unit_status=unit_status,
            ):
                self.setUp()
                self._bullet_hit_node(
                    unit_cls,
                    unit_status,
                    bullet_list,
                    Action.CONVERT,
                    mainte_times,
                )
                self._check_result(
                    expected_list,
                    unit_status,
                    unit_cls,
                    Node.UNIT_CONVERT,
                    expected_unit_color,
                )
                self.tearDown()

    def test_bullet_hit_split(self):
        test_cases = [
            (
                "hit split",
                [Direct.RIGHT, Direct.UP],
                [],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "hit bullet",
                [Direct.UP],
                [BulletPlayer(3, 1, Direct.DOWN)],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "miss split",
                [],
                [],
                UnitPlayer,
                (0, 2, Direct.RIGHT, Color.NODE_BLUE),
            ),
            (
                "[enemy] hit split",
                [],
                [],
                UnitEnemy,
                (2, 4, Direct.UP, Color.NODE_RED),
            ),
            (
                "[enemy] miss split",
                [],
                [],
                UnitEnemy,
                (0, 2, Direct.RIGHT, Color.NODE_RED),
            ),
        ]
        for (
            case_name,
            expected_direct_list,
            bullet_list,
            unit_cls,
            unit_status,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct_list=expected_direct_list,
                bullet_list=bullet_list,
                unit_cls=unit_cls,
                unit_status=unit_status,
            ):
                self.setUp()
                expected_list = [
                    (
                        x * 8 + 2 * 8 + BulletPlayer.get_start_pos(x),
                        y * 8 + 2 * 8 + BulletPlayer.get_start_pos(y),
                        x + 2,
                        y + 2,
                        d,
                        Color.NODE_BLUE,
                    )
                    for x, y, d in [
                        (*direct.value, direct) for direct in expected_direct_list
                    ]
                ]
                self._bullet_hit_node(
                    unit_cls,
                    unit_status,
                    bullet_list,
                    Action.SPLIT,
                    0,
                )
                self._check_result(
                    expected_list,
                    unit_status,
                    unit_cls,
                    Node.UNIT_SPLIT,
                    None,
                )
                self.tearDown()

    def test_bullet_hit_merge(self):
        test_cases = [
            (
                "hit merge",
                [
                    (
                        1 * 8 + 2 * 8 + BulletPlayer.get_start_pos(1),
                        2 * 8 + BulletPlayer.get_start_pos(0),
                        3,
                        2,
                        Direct.RIGHT,
                        Color.NODE_BLUE,
                    )
                ],
                [BulletPlayer(2, 1, Direct.DOWN)],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "hit bullet",
                [],
                [BulletPlayer(3, 1, Direct.DOWN), BulletPlayer(2, 1, Direct.DOWN)],
                UnitPlayer,
                (2, 4, Direct.UP, Color.NODE_BLUE),
            ),
            (
                "miss curve",
                [],
                [BulletPlayer(2, 1, Direct.DOWN)],
                UnitPlayer,
                (0, 2, Direct.RIGHT, Color.NODE_BLUE),
            ),
            (
                "[enemy] hit merge",
                [],
                [],
                UnitEnemy,
                (2, 4, Direct.UP, Color.NODE_RED),
            ),
            (
                "[enemy] miss merge",
                [],
                [],
                UnitEnemy,
                (0, 2, Direct.RIGHT, Color.NODE_RED),
            ),
        ]
        for case_name, expected_list, bullet_list, unit_cls, unit_status in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                bullet_list=bullet_list,
                unit_cls=unit_cls,
                unit_status=unit_status,
            ):
                self.setUp()
                self._bullet_hit_node(
                    unit_cls,
                    unit_status,
                    bullet_list,
                    Action.MERGE,
                    0,
                )
                self._check_result(
                    expected_list,
                    unit_status,
                    unit_cls,
                    Node.UNIT_MERGE,
                    None,
                )
                self.tearDown()

    def test_bullet_hit_bullet(self):
        test_cases = [
            (
                "hit front",
                [],
                BulletPlayer(2, 1, Direct.DOWN),
                (2, 4, Direct.UP),
                8,
                Color.NODE_BLUE,
            ),
            (
                "hit right",
                [],
                BulletPlayer(1, 2, Direct.RIGHT),
                (2, 4, Direct.UP),
                8,
                Color.NODE_BLUE,
            ),
            (
                "hit front 2dist",
                [],
                BulletPlayer(2, 0, Direct.DOWN),
                (2, 4, Direct.UP),
                16,
                Color.NODE_BLUE,
            ),
            (
                "hit enemy",
                [],
                BulletEnemy(2, 1, Direct.DOWN),
                (2, 4, Direct.UP),
                8,
                Color.NODE_BLUE,
            ),
            (
                "against different enemy bullet",
                [BulletEnemy],
                BulletEnemy(2, 1, Direct.DOWN),
                (2, 4, Direct.UP),
                8,
                Color.NODE_RED,
            ),
            (
                "against different enemy bullet from 2dist",
                [BulletEnemy],
                BulletEnemy(2, 0, Direct.DOWN),
                (2, 4, Direct.UP),
                16,
                Color.NODE_RED,
            ),
        ]
        for case_name, expected, bullet, unit_status, turn, bullet_color in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                bullet=bullet,
                unit_status=unit_status,
                turn=turn,
                bullet_color=bullet_color,
            ):
                self.setUp()
                unit = self.field.unit_list[0]
                unit.tile_x, unit.tile_y, unit.direct = unit_status
                unit.interval = UnitPlayer.SHOT_INTERVAL
                self.field.update()
                if bullet is not None:
                    self.field.bullet_map[bullet.get_tile_pos()] = bullet
                    bullet.color = bullet_color
                self.assertEqual(2, len(self.field.bullet_map))
                unit.interval = -10000000
                bullet = self.field.bullet_map[
                    tuple(x + y for x, y in zip(unit_status[0:2], unit_status[2].value))
                ]
                for _ in range(turn):
                    self.field.update()
                self.assertEqual(
                    expected,
                    [type(bullet) for bullet in self.field.bullet_map.values()],
                )
                self.tearDown()

    def test_mainte(self):
        test_cases = [
            ("curve", Direct.DOWN, None, Action.CURVE, None, 1),
            ("curve 2times", Direct.LEFT, None, Action.CURVE, None, 2),
            ("curve rev", Direct.DOWN, None, Action.CURVE_REV, None, 1),
            ("curve rev 2times", Direct.LEFT, None, Action.CURVE_REV, None, 2),
            (
                "convert",
                Direct.RIGHT,
                Color.NODE_RED,
                Action.CONVERT,
                Color.NODE_BLUE,
                1,
            ),
            (
                "convert 2times",
                Direct.RIGHT,
                Color.NODE_GREEN,
                Action.CONVERT,
                Color.NODE_BLUE,
                2,
            ),
            (
                "convert 3times",
                Direct.RIGHT,
                Color.NODE_BLUE,
                Action.CONVERT,
                Color.NODE_BLUE,
                3,
            ),
            ("split", Direct.DOWN, None, Action.SPLIT, None, 1),
            ("split 2times", Direct.LEFT, None, Action.SPLIT, None, 2),
            ("merge", Direct.DOWN, None, Action.MERGE, None, 1),
            ("merge 2times", Direct.LEFT, None, Action.MERGE, None, 2),
        ]
        for (
            case_name,
            expected_direct,
            expected_color,
            action,
            color,
            times,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                expected_color=expected_color,
                action=action,
                color=color,
                times=times,
            ):
                self.setUp()
                self.field.build(action, 2, 2)
                node = self.field.node_map[(2, 2)]
                self.assertEqual(node.color, color)
                self.assertEqual(node.direct, Direct.RIGHT)
                for _ in range(times):
                    self.field.mainte(2, 2)
                self.assertEqual(node.color, expected_color)
                self.assertEqual(node.direct, expected_direct)
                self.tearDown()

    def test_delete(self):
        test_cases = [
            ("convert", False, Convert, Action.CONVERT, (2, 2)),
            ("split", False, Split, Action.SPLIT, (2, 2)),
            ("curve", False, Curve, Action.CURVE, (2, 2)),
            ("curve rev", False, Curve, Action.CURVE_REV, (2, 2)),
            ("merge", False, Merge, Action.MERGE, (2, 2)),
            ("unit", True, UnitPlayer, None, (0, 6)),
        ]
        for case_name, expected, node_cls, action, pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                node_cls=node_cls,
                action=action,
                pos=pos,
            ):
                self.setUp()
                if action is not None:
                    self.field.build(action, *pos)
                self.assertEqual(True, isinstance(self.field.node_map[pos], node_cls))
                self.field.delete(*pos)
                self.assertEqual(expected, pos in self.field.node_map)
                self.tearDown()

    def test_get_enemy_color(self):
        test_cases = [
            ("enemy", UnitEnemy, None, (0, 6), Color.NODE_RED),
            ("player", UnitPlayer, None, (0, 6), None),
            ("convert", Convert, Action.CONVERT, (2, 2), None),
        ]
        for case_name, node_cls, action, pos, enemy_color in test_cases:
            with self.subTest(
                case_name=case_name,
                node_cls=node_cls,
                action=action,
                pos=pos,
                enemy_color=enemy_color,
            ):
                self.setUp()
                if action is not None:
                    self.field.build(action, *pos)
                if node_cls is UnitEnemy:
                    enemy = UnitEnemy(*pos, enemy_color)
                    self.field.unit_list.append(enemy)
                    self.field.node_map[pos] = enemy
                self.assertEqual(True, isinstance(self.field.node_map[pos], node_cls))
                self.field.delete(*pos)
                self.assertEqual(enemy_color, self.field.get_enemy_color(*pos))
                self.tearDown()


class TestCursor(TestParent):
    def test_draw_update(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("(0, 0)", [(0, 0)], [(ox, oy)], False),
            ("(1, 1)", [(1, 1)], [(ox + 8, oy + 8)], False),
            (
                "(11, 11)",
                [
                    (
                        PyxelFieldView.FIELD_TILE_WIDTH - 1,
                        PyxelFieldView.FIELD_TILE_HEIGHT - 1,
                    )
                ],
                [
                    (
                        ox + PyxelFieldView.FIELD_WIDTH - 1,
                        oy + PyxelFieldView.FIELD_HEIGHT - 1,
                    )
                ],
                False,
            ),
            (
                "curve left up",
                [Action.CURVE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy)],
                False,
            ),
            (
                "curve right down",
                [Action.CURVE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 - 1)],
                False,
            ),
            (
                "convert rev left up",
                [Action.CURVE_REV.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 2)],
                False,
            ),
            (
                "convert rev right down",
                [Action.CURVE_REV.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 3 - 1)],
                False,
            ),
            (
                "convert left up",
                [Action.CONVERT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 4)],
                False,
            ),
            (
                "convert right down",
                [Action.CONVERT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 5 - 1)],
                False,
            ),
            (
                "split left up",
                [Action.SPLIT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 6)],
                False,
            ),
            (
                "split right down",
                [Action.SPLIT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 7 - 1)],
                False,
            ),
            (
                "merge left up",
                [Action.MERGE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 8)],
                False,
            ),
            (
                "merge right down",
                [Action.MERGE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 9 - 1)],
                False,
            ),
            (
                "delete left up",
                [Action.DELETE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 11)],
                False,
            ),
            (
                "delete right down",
                [Action.DELETE.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 12 - 1)],
                False,
            ),
            (
                "next left up",
                [Action.NEXT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 13)],
                True,
            ),
            (
                "next right down",
                [Action.NEXT.value],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 14 - 1)],
                True,
            ),
            (
                "disable next left up",
                [None],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy + 8 * 13)],
                False,
            ),
            (
                "disable next right down",
                [None],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 * 14 - 1)],
                False,
            ),
            ("less x", [None], [(ox - 1, oy + 8)], False),
            ("less y", [None], [(ox + 8, oy - 1)], False),
            ("over x", [None], [(ox + PyxelFieldView.FIELD_WIDTH, oy + 8)], False),
            ("over y", [None], [(ox + 8, oy + PyxelFieldView.FIELD_HEIGHT)], False),
            ("double", [(0, 0), None], [(ox, oy), (ox, oy)], False),
            ("hold", [(0, 0), (0, 0)], [(ox, oy), None], False),
            ("double there", [(0, 0), (1, 1)], [(ox, oy), (ox + 8, oy + 8)], False),
            ("double over", [(0, 0), None], [(ox, oy), (ox - 1, oy + 8)], False),
            ("triple", [(0, 0), None, (0, 0)], [(ox, oy), (ox, oy), (ox, oy)], False),
        ]
        for case_name, expected, mouse_pos, is_clear in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                mouse_pos=mouse_pos,
                is_clear=is_clear,
            ):
                self.setUp()
                cursor = Cursor()
                cursor.set_stage_clear(is_clear)
                cursor.update()
                cursor.draw()
                for pos in mouse_pos:
                    if pos is not None:
                        self.test_input.set_mouse_pos(pos[0], pos[1])
                        self.test_input.set_is_click(True)
                    else:
                        self.test_input.set_mouse_pos(None, None)
                        self.test_input.set_is_click(False)
                    cursor.update()
                    cursor.draw()
                expected_list = []
                if not is_clear:
                    expected_list.append(("set_clip", None))
                    expected_list.append(
                        (
                            "draw_rect",
                            ox + PyxelFieldView.FIELD_WIDTH + 8,
                            oy + 8 * 13,
                            8,
                            8,
                            Color.BLACK,
                            True,
                        )
                    )
                for e_pos in expected:
                    if e_pos is not None or not is_clear:
                        expected_list.append(("set_clip", None))
                    if e_pos is not None:
                        expected_list.append(
                            (
                                "draw_rect",
                                e_pos[0] * 8 + ox,
                                e_pos[1] * 8 + oy,
                                8,
                                8,
                                Color.RED,
                                False,
                            )
                        )
                    if not is_clear:
                        expected_list.append(
                            (
                                "draw_rect",
                                ox + PyxelFieldView.FIELD_WIDTH + 8,
                                oy + 8 * 13,
                                8,
                                8,
                                Color.BLACK,
                                True,
                            )
                        )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_get_action(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("field", [(0, 0)], [Action.FIELD], [(ox, oy)]),
            (
                "2 field",
                [(0, 0), (1, 0)],
                [Action.FIELD, Action.FIELD],
                [(ox, oy), (ox + 8, oy)],
            ),
            (
                "curve and cancel",
                [Action.CURVE.value, (Action.CURVE.value)],
                [Action.CURVE, None],
                [
                    (ox + PyxelFieldView.FIELD_WIDTH + 8, oy),
                    (ox + PyxelFieldView.FIELD_WIDTH + 8 * 2 - 1, oy + 8 - 1),
                ],
            ),
            (
                "curve field",
                [Action.CURVE.value, (0, 0)],
                [Action.CURVE, Action.FIELD],
                [(ox + PyxelFieldView.FIELD_WIDTH + 8, oy), (ox, oy)],
            ),
            (
                "curve field 2",
                [(0, 1), Action.CURVE.value, (0, 0)],
                [Action.FIELD, Action.CURVE, Action.FIELD],
                [(ox, oy + 8), (ox + PyxelFieldView.FIELD_WIDTH + 8, oy), (ox, oy)],
            ),
        ]
        for case_name, expected_list, expected_action_list, click_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                expected_action_list=expected_action_list,
                click_list=click_list,
            ):
                self.setUp()
                cursor = Cursor()
                self.assertEqual(None, cursor.get_select_pos(), case_name)
                self.assertEqual(None, cursor.get_action(), case_name)
                for i, click in enumerate(click_list):
                    self.test_input.set_mouse_pos(*click)
                    self.test_input.set_is_click(True)
                    cursor.update()
                    cursor.draw()
                    self.assertEqual(None, cursor.get_select_pos(), case_name)
                    self.assertEqual(
                        expected_action_list[i - 1] if i > 0 else None,
                        cursor.get_action(),
                        case_name,
                    )
                    cursor.update()
                    cursor.draw()
                    self.assertEqual(
                        expected_list[i], cursor.get_select_pos(), case_name
                    )
                    self.assertEqual(
                        expected_action_list[i], cursor.get_action(), case_name
                    )
                expected_draw_list = []
                for i, expected in enumerate(expected_list):
                    expected_draw_list.append(("set_clip", None))
                    if i > 0 and expected_action_list[i - 1] not in [
                        None,
                        Action.FIELD,
                    ]:
                        expected_draw_list.append(
                            (
                                "draw_rect",
                                *Cursor.AVAIL_POS_MAP[expected_action_list[i - 1]][0:2],
                                8,
                                8,
                                Color.BLUE,
                                False,
                            )
                        )
                    expected_cursor = (j * 8 + o for j, o in zip(expected, (ox, oy)))
                    expected_draw_list.append(
                        ("draw_rect", *expected_cursor, 8, 8, Color.RED, False)
                    )
                    expected_draw_list.append(
                        (
                            "draw_rect",
                            *Cursor.AVAIL_POS_MAP[Action.NEXT][0:2],
                            8,
                            8,
                            Color.BLACK,
                            True,
                        )
                    )
                    expected_draw_list.append(("set_clip", None))
                    if expected_action_list[i] not in [None, Action.FIELD]:
                        expected_draw_list.append(
                            (
                                "draw_rect",
                                *Cursor.AVAIL_POS_MAP[expected_action_list[i]][0:2],
                                8,
                                8,
                                Color.BLUE,
                                False,
                            )
                        )
                    expected_draw_list.append(
                        (
                            "draw_rect",
                            *Cursor.AVAIL_POS_MAP[Action.NEXT][0:2],
                            8,
                            8,
                            Color.BLACK,
                            True,
                        )
                    )
                self.assertEqual(
                    expected_draw_list, self.test_view.get_call_params(), case_name
                )
                self.tearDown()


class TestScout(TestParent):
    @staticmethod
    def _get_expected_list(kind: str, pos_list: list[int], opt) -> list:
        ret = []
        draw_pos = tuple(
            pos + padding + line_pos for pos, padding, line_pos in zip(*pos_list)
        )
        if kind == "draw_image":
            ret.extend(
                [
                    ("set_pal", [Color.WHITE, opt]),
                    (
                        "draw_image",
                        *draw_pos,
                        *Image.PLAYER_BULLET.value,
                        Direct.RIGHT,
                    ),
                    ("set_pal", []),
                ]
            )
        elif kind == "draw_text":
            ret.append(
                (
                    "draw_text",
                    *draw_pos,
                    opt,
                )
            )
        return ret

    def test_draw(self):
        test_cases = [
            ("default", 6, Color.NODE_BLUE, []),
            ("pos chg", 8, Color.NODE_BLUE, []),
            ("color chg", 6, Color.NODE_RED, []),
            ("yellow", 6, Color.NODE_YELLOW, [Color.NODE_RED, Color.NODE_GREEN]),
            ("orange", 6, Color.NODE_ORANGE, [Color.NODE_RED, Color.NODE_YELLOW]),
        ]
        for case_name, y_pos, color, merge_colors in test_cases:
            with self.subTest(
                case_name=case_name, y_pos=y_pos, color=color, merge_colors=merge_colors
            ):
                self.setUp()
                scout = Scout(y_pos, color)
                scout.draw()
                x_pos = (
                    PyxelFieldView.FIELD_OFFSET_X
                    + PyxelFieldView.FIELD_WIDTH
                    - Scout.FRAME_RECT[2]
                    + Scout.FRAME_RECT[0]
                )
                y_pos = 8 * y_pos + PyxelFieldView.FIELD_OFFSET_Y + Scout.FRAME_RECT[1]
                expected = [("set_clip", None)]
                expected += [
                    (
                        "draw_rect",
                        x_pos,
                        y_pos,
                        *Scout.FRAME_RECT[2:4],
                        color,
                        is_fill,
                    )
                    for color, is_fill in [(Color.BLACK, True), (Color.GREEN, False)]
                ]
                if len(merge_colors) > 0:
                    for kind, padding, line_pos, opt in [
                        ("draw_image", Scout.PADDING_UP, (0, 0), color),
                        ("draw_text", Scout.PADDING_UP, (7, 2), "="),
                        ("draw_image", Scout.PADDING_DOWN, (0, 0), merge_colors[0]),
                        ("draw_text", Scout.PADDING_DOWN, (7, 1), "+"),
                        ("draw_image", Scout.PADDING_DOWN, (9, 0), merge_colors[1]),
                    ]:
                        expected += self._get_expected_list(
                            kind, [(x_pos, y_pos), padding, line_pos], opt
                        )
                else:
                    expected += self._get_expected_list(
                        "draw_image",
                        [(x_pos, y_pos), Scout.PADDING_CENTER, (0, 0)],
                        color,
                    )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()


class TestGameParameter(unittest.TestCase):
    @patch.object(random, "randint")
    def test_get(self, mock):
        test_cases = [
            ("base", 2, [Color.NODE_RED, Color.NODE_GREEN, Color.NODE_BLUE] * 2, 0),
            ("yellow", 4, [Color.NODE_YELLOW, Color.NODE_RED, Color.NODE_GREEN], 1),
            ("cyan", 4, [Color.NODE_CYAN, Color.NODE_GREEN, Color.NODE_BLUE], 2),
            ("purple", 4, [Color.NODE_PURPLE, Color.NODE_RED, Color.NODE_BLUE], 3),
            ("orange", 2, [Color.NODE_YELLOW, Color.NODE_ORANGE], 4),
            ("brown", 2, [Color.NODE_YELLOW, Color.NODE_BROWN], 5),
            ("navy", 2, [Color.NODE_PURPLE, Color.NODE_NAVY], 6),
            ("deep blue", 2, [Color.NODE_CYAN, Color.NODE_DEEP_BLUE], 7),
        ]
        for case_name, sep, color_list, rand in test_cases:
            with self.subTest(
                case_name=case_name, color_list=color_list, sep=sep, rand=rand
            ):
                mock.return_value = rand
                param = GameParameter()
                ret = param.get()
                self.assertEqual((sep, color_list), ret, ret)


class TestGameCore(TestFieldParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.expect_field_view_call = []
        self.patcher_player_init_func = patch(
            "main.Field._get_random_new_player_y_pos",
            return_value=6,
        )
        self.patcher_player_init_func.start()
        self.patcher_enemy_init_func = patch(
            "main.Field._get_random_new_enemy_y_pos",
            return_value=[6],
        )
        self.patcher_enemy_init_func.start()
        self.patcher_game_prameter_get = patch(
            "main.GameCore._get_game_parameter",
            return_value=(2, [Color.NODE_BLUE, Color.NODE_RED, Color.NODE_GREEN] * 2),
        )
        self.patcher_game_prameter_get.start()
        self.core = GameCore()

    def tearDown(self):
        self.patcher_player_init_func.stop()
        self.patcher_enemy_init_func.stop()
        self.patcher_game_prameter_get.stop()
        self.assertEqual(
            self.expect_view_call,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.assertEqual(
            self.expect_field_view_call,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )
        return super().tearDown()

    def put_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "clear":
                self.expect_view_call.extend(
                    [
                        "clear",
                        ("set_clip", None),
                    ]
                )
            elif draw_action[0] == "tilemap":
                self.expect_view_call.extend(
                    [
                        "draw_tilemap",
                        ("set_clip", PyxelFieldView.get_rect()),
                    ]
                )
            elif draw_action[0] == "cursor":
                self.expect_view_call.extend([("set_clip", None)])
                if draw_action[1] is not None:
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                draw_action[1][0] * 8 + PyxelFieldView.FIELD_OFFSET_X,
                                draw_action[1][1] * 8 + PyxelFieldView.FIELD_OFFSET_Y,
                                8,
                                8,
                                draw_action[1][2],
                                False,
                            )
                        ]
                    )
                if not draw_action[2]:
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                *Cursor.AVAIL_POS_MAP[Action.NEXT][0:2],
                                8,
                                8,
                                Color.BLACK,
                                True,
                            ),
                        ]
                    )
            elif draw_action[0] == "graph":
                if draw_action[1] + draw_action[2] == 0:
                    player_rate = 0.5
                else:
                    player_rate = draw_action[1] / (draw_action[1] + draw_action[2])
                self.expect_view_call.extend(
                    [
                        ("set_clip", None),
                        (
                            "draw_rect",
                            PyxelFieldView.FIELD_OFFSET_X,
                            1 * 8
                            + PyxelFieldView.FIELD_OFFSET_Y
                            + PyxelFieldView.FIELD_HEIGHT,
                            int(PyxelFieldView.FIELD_HEIGHT * player_rate),
                            2,
                            Color.PLAYER,
                            True,
                        ),
                        (
                            "draw_rect",
                            PyxelFieldView.FIELD_OFFSET_X
                            + int(PyxelFieldView.FIELD_HEIGHT * player_rate),
                            1 * 8
                            + PyxelFieldView.FIELD_OFFSET_Y
                            + PyxelFieldView.FIELD_HEIGHT,
                            PyxelFieldView.FIELD_HEIGHT
                            - int(PyxelFieldView.FIELD_HEIGHT * player_rate),
                            2,
                            Color.ENEMY,
                            True,
                        ),
                    ]
                )
            elif draw_action[0] == "scout":
                x_pos = (
                    PyxelFieldView.FIELD_OFFSET_X
                    + PyxelFieldView.FIELD_WIDTH
                    - Scout.FRAME_RECT[2]
                    + Scout.FRAME_RECT[0]
                )
                y_pos = 8 * 6 + PyxelFieldView.FIELD_OFFSET_Y + Scout.FRAME_RECT[1]
                self.expect_view_call.extend(
                    [
                        ("set_clip", None),
                        (
                            "draw_rect",
                            x_pos,
                            y_pos,
                            *Scout.FRAME_RECT[2:4],
                            Color.BLACK,
                            True,
                        ),
                        (
                            "draw_rect",
                            x_pos,
                            y_pos,
                            *Scout.FRAME_RECT[2:4],
                            Color.GREEN,
                            False,
                        ),
                        ("set_pal", [Color.WHITE, Color.NODE_BLUE]),
                        (
                            "draw_image",
                            *tuple(
                                pos + padding
                                for pos, padding in zip(
                                    (x_pos, y_pos), Scout.PADDING_CENTER
                                )
                            ),
                            *Image.PLAYER_BULLET.value,
                            Direct.RIGHT,
                        ),
                        ("set_pal", []),
                    ]
                )

    def put_field_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "player_node":
                self.expect_field_view_call.append(
                    ("draw_node", 0, 6, Node.UNIT_PLAYER, Direct.RIGHT, Color.NODE_BLUE)
                )
            elif draw_action[0] == "player_bullet":
                self.expect_field_view_call.append(
                    (
                        "draw_object",
                        *draw_action[1],
                        Image.PLAYER_BULLET,
                        Color.NODE_BLUE,
                    )
                )
            elif draw_action[0] == "enemy_node":
                self.expect_field_view_call.append(
                    ("draw_node", 11, 6, Node.UNIT_ENEMY, Direct.LEFT, Color.NODE_BLUE)
                )
            elif draw_action[0] == "enemy_bullet":
                self.expect_field_view_call.append(
                    (
                        "draw_object",
                        *draw_action[1],
                        Image.ENEMY_BULLET,
                        Color.NODE_BLUE,
                    )
                )
            elif draw_action[0] == "field_node":
                self.expect_field_view_call.append(
                    ("draw_node", *draw_action[1], draw_action[2], draw_action[3], None)
                )

    def test_draw(self):
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["tilemap"],
                ["cursor", None, False],
                ["graph", 0, 0],
            ]
        )
        self.put_field_draw_result([["player_node"], ["enemy_node"]])

    def test_shot(self):
        test_cases = [
            ("two shot", (1, 1), UnitPlayer.SHOT_INTERVAL, UnitPlayer.SHOT_INTERVAL),
            (
                "no shot",
                (0, 0),
                UnitPlayer.SHOT_INTERVAL * 2,
                UnitPlayer.SHOT_INTERVAL * 2,
            ),
            (
                "player shot",
                (1, 0),
                UnitPlayer.SHOT_INTERVAL,
                UnitPlayer.SHOT_INTERVAL * 2,
            ),
            (
                "enemy shot",
                (0, 1),
                UnitPlayer.SHOT_INTERVAL * 2,
                UnitPlayer.SHOT_INTERVAL,
            ),
        ]
        for (
            case_name,
            expected_count_list,
            player_interval,
            enemy_interval,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_count_list=expected_count_list,
                player_interval=player_interval,
                enemy_interval=enemy_interval,
            ):
                self.setUp()
                self.core.field.unit_list[0].max_interval = player_interval
                self.core.field.unit_list[1].max_interval = enemy_interval
                for _ in range(UnitPlayer.SHOT_INTERVAL):
                    self.core.update()
                    self.core.draw()
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["tilemap"],
                            ["cursor", None, False],
                            ["graph", 0, 0],
                        ]
                    )
                    self.put_field_draw_result([["player_node"], ["enemy_node"]])
                for i in range(2):
                    self.core.update()
                    self.core.draw()
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["tilemap"],
                            ["cursor", None, False],
                            ["graph", *expected_count_list],
                        ]
                    )
                    if expected_count_list[0] == 1:
                        self.put_field_draw_result(
                            [
                                [
                                    "player_bullet",
                                    (
                                        1 * 8 + BulletPlayer.get_start_pos(1) + i,
                                        6 * 8 + BulletPlayer.get_start_pos(0),
                                    ),
                                ]
                            ]
                        )
                    if expected_count_list[1] == 1:
                        self.put_field_draw_result(
                            [
                                [
                                    "enemy_bullet",
                                    (
                                        10 * 8 + BulletPlayer.get_start_pos(-1) - i,
                                        6 * 8 + BulletPlayer.get_start_pos(0),
                                    ),
                                ],
                            ]
                        )
                    self.put_field_draw_result(
                        [
                            ["player_node"],
                            ["enemy_node"],
                        ]
                    )
                self.tearDown()

    def test_mouse_click(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("one click", [(0, 0)], [(ox, oy)]),
            ("two click", [(0, 0), None], [(ox, oy), (ox, oy)]),
            ("hold", [(0, 0), (0, 0)], [(ox, oy), None]),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, mouse_pos=mouse_pos
            ):
                self.setUp()
                self.core.update()
                self.core.draw()
                for pos in mouse_pos:
                    if pos is not None:
                        self.test_input.set_mouse_pos(pos[0], pos[1])
                        self.test_input.set_is_click(True)
                    else:
                        self.test_input.set_mouse_pos(None, None)
                        self.test_input.set_is_click(False)
                    self.core.update()
                    self.core.draw()
                self.put_draw_result(
                    [["clear"], ["tilemap"], ["cursor", None, False], ["graph", 0, 0]]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                for e_pos in expected:
                    self.put_draw_result([["clear"], ["tilemap"]])
                    self.put_field_draw_result([["player_node"], ["enemy_node"]])
                    if e_pos is not None:
                        self.put_draw_result([["cursor", [*e_pos, Color.RED], False]])
                    else:
                        self.put_draw_result([["cursor", None, False]])
                    self.put_draw_result([["graph", 0, 0]])
                self.tearDown()

    def test_build(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("build", ((0, 0), Node.UNIT_CURVE, Direct.RIGHT), (ox, oy)),
            ("build fail", None, (ox + PyxelFieldView.FIELD_WIDTH - 1, oy)),
        ]
        for case_name, expected, pos in test_cases:
            with self.subTest(case_name=case_name, expected=expected, pos=pos):
                self.setUp()
                self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.CURVE][0:2])
                self.test_input.set_is_click(True)
                self.core.update()
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["tilemap"],
                        ["cursor", [*Action.CURVE.value, Color.BLUE], False],
                        ["graph", 0, 0],
                    ]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                self.test_input.set_mouse_pos(*pos)
                self.core.update()
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [["clear"], ["tilemap"], ["cursor", None, False], ["graph", 0, 0]]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                if expected is not None:
                    self.put_field_draw_result([["field_node", *expected]])
                self.test_input.set_is_click(False)
                self.core.update()
                self.tearDown()

    def test_mainte(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("curve", ((0, 0), Node.UNIT_CURVE, Direct.LEFT), (ox, oy)),
        ]
        for case_name, expected, pos in test_cases:
            with self.subTest(case_name=case_name, expected=expected, pos=pos):
                self.setUp()
                self.core.field.build(Action.CURVE, 0, 0)
                self.test_input.set_mouse_pos(*pos)
                self.test_input.set_is_click(True)
                for _ in range(2):
                    self.core.update()
                    self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [["clear"], ["tilemap"], ["cursor", None, False], ["graph", 0, 0]]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                if expected is not None:
                    self.put_field_draw_result([["field_node", *expected]])
                self.tearDown()

    def test_delete(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        test_cases = [
            ("succcess", False, (ox, oy)),
            ("fail", True, (ox + PyxelFieldView.FIELD_WIDTH - 1, oy)),
        ]
        for case_name, expected_exist, pos in test_cases:
            with self.subTest(
                case_name=case_name, expected_exist=expected_exist, pos=pos
            ):
                self.setUp()
                self.core.field.build(Action.CURVE, 0, 0)
                self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.DELETE][0:2])
                self.test_input.set_is_click(True)
                self.core.update()
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["tilemap"],
                        ["cursor", [*Action.DELETE.value, Color.BLUE], False],
                        ["graph", 0, 0],
                    ]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                self.put_field_draw_result(
                    [["field_node", (0, 0), Node.UNIT_CURVE, Direct.RIGHT]]
                )
                self.test_input.set_mouse_pos(*pos)
                self.core.update()
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [["clear"], ["tilemap"], ["cursor", None, False], ["graph", 0, 0]]
                )
                self.put_field_draw_result([["player_node"], ["enemy_node"]])
                if expected_exist:
                    self.put_field_draw_result(
                        [["field_node", (0, 0), Node.UNIT_CURVE, Direct.RIGHT]]
                    )
                self.tearDown()

    def test_scout(self):
        ox, oy = PyxelFieldView.FIELD_OFFSET_X, PyxelFieldView.FIELD_OFFSET_Y
        enemy_pos = (ox + 8 * 11, oy + 8 * 6)
        test_cases = [
            ("and click field", None, (ox, oy)),
            (
                "and click icon",
                [*Action.CURVE.value, Color.BLUE],
                Cursor.AVAIL_POS_MAP[Action.CURVE][0:2],
            ),
        ]
        for case_name, expected_cursol, second_click_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_cursol=expected_cursol,
                second_click_pos=second_click_pos,
            ):
                self.setUp()
                for click_pos, is_draw_scout, cursol_pos in [
                    (enemy_pos, True, None),
                    (None, True, None),
                    (second_click_pos, False, expected_cursol),
                ]:
                    if click_pos is not None:
                        self.test_input.set_is_click(True)
                        self.test_input.set_mouse_pos(*click_pos)
                    else:
                        self.test_input.set_is_click(False)
                    for _ in range(1):
                        self.core.update()
                        self.core.update()
                    self.core.draw()
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["tilemap"],
                            ["cursor", cursol_pos, False],
                            ["graph", 0, 0],
                        ]
                    )
                    if is_draw_scout:
                        self.put_draw_result([["scout"]])
                    self.put_field_draw_result([["player_node"], ["enemy_node"]])
                self.tearDown()

    @patch.object(Field, "get_bullet_count")
    def test_next(self, mock_get_bullet_count):
        for unit in self.core.field.unit_list:
            unit.interval = -10000000
        mock_get_bullet_count.return_value = (1, 0)
        self.core.field.build(Action.CURVE, 0, 0)
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["tilemap"],
                ["cursor", None, False],
                ["graph", 1, 0],
            ]
        )
        self.put_field_draw_result([["player_node"], ["enemy_node"]])
        self.put_field_draw_result(
            [["field_node", (0, 0), Node.UNIT_CURVE, Direct.RIGHT]]
        )
        for _ in range(GameCore.WAIT_ENABLE_NEXT_TERN + 1):
            self.core.update()
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["tilemap"],
                ["graph", 1, 0],
            ]
        )
        self.put_field_draw_result([["player_node"], ["enemy_node"]])
        self.put_field_draw_result(
            [["field_node", (0, 0), Node.UNIT_CURVE, Direct.RIGHT]]
        )
        self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
        self.test_input.set_is_click(True)
        self.core.update()
        self.core.update()
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["tilemap"],
                ["cursor", None, False],
                ["graph", 1, 0],
            ]
        )
        self.put_field_draw_result([["player_node"], ["enemy_node"]])


if __name__ == "__main__":
    unittest.main()
