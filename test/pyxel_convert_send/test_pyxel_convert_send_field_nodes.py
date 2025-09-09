import os
import sys
import unittest

for p in ["../src/", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from test_pyxel_convert_send_framework import TestFieldParent  # pylint: disable=C0413
from pyxel_convert_send.framework import (  # pylint: disable=C0413
    Node,
    Image,
    Direct,
    Color,
)
from pyxel_convert_send.field_nodes import (  # pylint: disable=C0413
    UnitPlayer,
    BulletPlayer,
    Curve,
    UnitEnemy,
    BulletEnemy,
    Convert,
    Split,
    Merge,
)


class TestBullet(TestFieldParent):
    def test_draw(self):
        bullet = BulletPlayer(0, 7, Direct.RIGHT)
        bullet.draw()
        expected = [
            (
                "draw_object",
                BulletPlayer.get_start_pos(1),
                7 * 8 + BulletPlayer.get_start_pos(0),
                Image.PLAYER_BULLET,
                Color.NODE_BLUE,
            )
        ]
        self.assertEqual(
            expected,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )

    def test_update(self):
        test_cases = [
            ("right", Direct.RIGHT),
            ("up", Direct.UP),
            ("down", Direct.DOWN),
            ("left", Direct.LEFT),
        ]
        for case_name, d in test_cases:
            with self.subTest(case_name=case_name, direct=d):
                self.setUp()
                bullet = BulletPlayer(0, 7, d)
                bullet.draw()
                bullet.update()
                bullet.draw()
                expected = [
                    (
                        "draw_object",
                        BulletPlayer.get_start_pos(d.value[0]) + i * d.value[0],
                        7 * 8 + BulletPlayer.get_start_pos(d.value[1]) + i * d.value[1],
                        Image.PLAYER_BULLET,
                        Color.NODE_BLUE,
                    )
                    for i in range(2)
                ]
                self.assertEqual(
                    expected,
                    self.test_field_view.get_call_params(),
                    self.test_field_view.get_call_params(),
                )
                self.tearDown()


class TestUnit(TestFieldParent):
    def test_draw(self):
        test_cases = [
            ("player", (Node.UNIT_PLAYER, Direct.RIGHT), UnitPlayer),
            ("enemy", (Node.UNIT_ENEMY, Direct.LEFT), UnitEnemy),
        ]
        for case_name, expected_param, cls in test_cases:
            with self.subTest(
                case_name=case_name, expected_param=expected_param, cls=cls
            ):
                self.setUp()
                param = (7, 7) if cls == UnitPlayer else (7, 7, Color.BLUE)
                unit = cls(*param)
                unit.draw()
                expected = [("draw_node", 7, 7, *expected_param, Color.NODE_BLUE)]
                self.assertEqual(
                    expected,
                    self.test_field_view.get_call_params(),
                    self.test_field_view.get_call_params(),
                )
                self.tearDown()

    def test_shot(self):
        test_cases = [
            ("player", Direct.RIGHT, BulletPlayer, UnitPlayer),
            ("enemy", Direct.LEFT, BulletEnemy, UnitEnemy),
        ]
        for case_name, ed, ec, cls in test_cases:
            with self.subTest(
                case_name=case_name, expected_direct=ed, expected_class=ec, cls=cls
            ):
                unit = cls(7, 7)
                for _ in range(cls.SHOT_INTERVAL):
                    self.assertEqual(None, unit.shot())
                bullet = unit.shot()
                self.assertTrue(isinstance(bullet, ec))
                self.assertEqual(
                    (
                        (7 + ed.value[0]) * 8 + BulletPlayer.get_start_pos(ed.value[0]),
                        (7 + ed.value[1]) * 8 + BulletPlayer.get_start_pos(ed.value[1]),
                    ),
                    bullet.get_pos(),
                )
                self.assertEqual(ed, bullet.direct)
                self.assertEqual(None, unit.shot())

    def test_hit(self):
        test_cases = [
            ("player", True, UnitPlayer, BulletEnemy),
            ("enemy", True, UnitEnemy, BulletPlayer),
            ("player by me", False, UnitPlayer, BulletPlayer),
            ("enemy by me", False, UnitEnemy, BulletEnemy),
        ]
        for case_name, eid, cls, bc in test_cases:
            with self.subTest(
                case_name=case_name, expected_is_death=eid, cls=cls, bullet_class=bc
            ):
                param = (7, 7) if cls == UnitPlayer else (7, 7, Color.BLUE)
                unit = cls(*param)
                bullet = bc(7, 7, Direct.RIGHT)
                for _ in range(unit.MAX_HP):
                    self.assertEqual(False, unit.is_death())
                    unit.hit(bullet)
                self.assertEqual(eid, unit.is_death())

    def test_set_color(self):
        test_cases = [
            ("player", Color.NODE_BLUE, UnitPlayer, (7, 6)),
            ("enemy red", Color.NODE_RED, UnitEnemy, (7, 4, Color.NODE_RED)),
            ("enemy blue", Color.NODE_BLUE, UnitEnemy, (7, 6, Color.NODE_BLUE)),
        ]
        for case_name, expected, cls, cls_params in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, cls=cls, cls_params=cls_params
            ):
                self.setUp()
                unit = cls(*cls_params)
                self.assertEqual(expected, unit.color)
                self.tearDown()


class TestCurve(TestFieldParent):
    def test_draw(self):
        test_cases = [
            ("no rev", Node.UNIT_CURVE, False),
            ("rev", Node.UNIT_CURVE_REV, True),
        ]
        for case_name, expected, is_rev in test_cases:
            with self.subTest(case_name=case_name, expected=expected, is_rev=is_rev):
                self.setUp()
                curve = Curve(0, 7, is_rev)
                curve.draw()
                expected = [("draw_node", 0, 7, expected, Direct.RIGHT, None)]
                self.assertEqual(
                    expected,
                    self.test_field_view.get_call_params(),
                    self.test_field_view.get_call_params(),
                )
                self.tearDown()

    def test_reshot(self):
        dc = Direct
        test_cases = [
            ("shot right", dc.RIGHT, dc.UP, 0, False, BulletPlayer),
            ("cant shot right from left", None, dc.LEFT, 0, False, BulletPlayer),
            ("cant shot right from down", None, dc.DOWN, 0, False, BulletPlayer),
            ("cant shot right from right", None, dc.RIGHT, 0, False, BulletPlayer),
            ("shot down", dc.DOWN, dc.RIGHT, 1, False, BulletPlayer),
            ("cant shot down from up", None, dc.UP, 1, False, BulletPlayer),
            ("shot left", dc.LEFT, dc.DOWN, 2, False, BulletPlayer),
            ("cant shot left from left", None, dc.LEFT, 2, False, BulletPlayer),
            ("shot up", dc.UP, dc.LEFT, 3, False, BulletPlayer),
            ("cant shot up from down", None, dc.DOWN, 3, False, BulletPlayer),
            ("shot turn right", dc.RIGHT, dc.UP, 4, False, BulletPlayer),
            ("cant shot turn right from right", None, dc.RIGHT, 4, False, BulletPlayer),
            ("[rev] shot right", dc.RIGHT, dc.DOWN, 0, True, BulletPlayer),
            ("[rev] cant shot right from left", None, dc.RIGHT, 0, True, BulletPlayer),
            ("[rev] cant shot right from down", None, dc.UP, 0, True, BulletPlayer),
            ("[rev] cant shot right from right", None, dc.LEFT, 0, True, BulletPlayer),
            ("[rev] shot down", Direct.DOWN, Direct.LEFT, 1, True, BulletPlayer),
            ("[rev] cant shot down from up", None, Direct.DOWN, 1, True, BulletPlayer),
            ("[rev] shot left", Direct.LEFT, Direct.UP, 2, True, BulletPlayer),
            ("[rev] cant shot left from left", None, dc.RIGHT, 2, True, BulletPlayer),
            ("[rev] shot up", Direct.UP, Direct.RIGHT, 3, True, BulletPlayer),
            ("[rev] cant shot up from down", None, Direct.UP, 3, True, BulletPlayer),
            ("[rev] shot turn right", Direct.RIGHT, Direct.DOWN, 4, True, BulletPlayer),
            (
                "[rev] cant shot turn right from right",
                None,
                dc.LEFT,
                4,
                True,
                BulletPlayer,
            ),
            ("[enemy] cant shot shot right", None, dc.UP, 0, False, BulletEnemy),
            ("[enemy] cant shot right from left", None, dc.LEFT, 0, False, BulletEnemy),
            ("[enemy] cant shot shot down", None, dc.RIGHT, 1, False, BulletEnemy),
            ("[enemy] cant shot down from up", None, dc.UP, 1, False, BulletEnemy),
            ("[enemy] cant shot shot left", None, dc.DOWN, 2, False, BulletEnemy),
            ("[enemy] cant shot left from left", None, dc.LEFT, 2, False, BulletEnemy),
            ("[enemy] cant shot shot up", None, dc.LEFT, 3, False, BulletEnemy),
            ("[enemy] cant shot up from down", None, dc.DOWN, 3, False, BulletEnemy),
            ("[enemy] cant shot shot turn right", None, dc.UP, 4, False, BulletEnemy),
            (
                "[enemy] cant shot turn right from right",
                None,
                dc.RIGHT,
                4,
                False,
                BulletPlayer,
            ),
        ]
        for case_name, ed, sd, tn, is_rev, bc in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=ed,
                shot_direct=sd,
                turn_num=tn,
                bullet_class=bc,
            ):
                self.setUp()
                curve = Curve(0, 7, is_rev)
                bullet = bc(0, 7, sd)
                for _ in range(tn):
                    curve.mainte()
                bullet_list = curve.reshot(bullet)
                if ed is not None:
                    self.assertEqual(
                        (
                            ed.value[0] * 8 + BulletPlayer.get_start_pos(ed.value[0]),
                            ed.value[1] * 8
                            + 7 * 8
                            + BulletPlayer.get_start_pos(ed.value[1]),
                        ),
                        bullet_list[0].get_pos(),
                    )
                    self.assertEqual(ed, bullet_list[0].direct)
                else:
                    self.assertEqual(0, len(bullet_list))
                self.tearDown()


class TestConvert(TestFieldParent):
    def test_draw(self):
        curve = Convert(0, 7)
        curve.draw()
        expected = [
            ("draw_node", 0, 7, Node.UNIT_CONVERT, Direct.RIGHT, Color.NODE_BLUE)
        ]
        self.assertEqual(
            expected,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )


class TestSplit(TestFieldParent):
    def test_draw(self):
        split = Split(0, 7)
        split.draw()
        expected = [("draw_node", 0, 7, Node.UNIT_SPLIT, Direct.RIGHT, None)]
        self.assertEqual(
            expected,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )

    def test_reshot(self):
        dc = Direct
        test_cases = [
            ("shot right up", [dc.RIGHT, dc.UP], dc.UP, 0, BulletPlayer),
            ("cant shot right from left", [], dc.LEFT, 0, BulletPlayer),
            ("cant shot right from down", [], dc.DOWN, 0, BulletPlayer),
            ("cant shot right from right", [], dc.RIGHT, 0, BulletPlayer),
            ("shot down", [dc.DOWN, dc.RIGHT], dc.RIGHT, 1, BulletPlayer),
            ("cant shot down from up", [], dc.UP, 1, BulletPlayer),
            ("shot left", [dc.LEFT, dc.DOWN], dc.DOWN, 2, BulletPlayer),
            ("cant shot left from left", [], dc.LEFT, 2, BulletPlayer),
            ("shot up", [dc.UP, dc.LEFT], dc.LEFT, 3, BulletPlayer),
            ("cant shot up from down", [], dc.DOWN, 3, BulletPlayer),
            ("shot turn right", [dc.RIGHT, dc.UP], dc.UP, 4, BulletPlayer),
            ("cant shot turn right from right", [], dc.RIGHT, 4, BulletPlayer),
            ("[enemy] cant shot shot right", [], dc.UP, 0, BulletEnemy),
            ("[enemy] cant shot right from left", [], dc.LEFT, 0, BulletEnemy),
            ("[enemy] cant shot shot down", [], dc.RIGHT, 1, BulletEnemy),
            ("[enemy] cant shot down from up", [], dc.UP, 1, BulletEnemy),
            ("[enemy] cant shot shot left", [], dc.DOWN, 2, BulletEnemy),
            ("[enemy] cant shot left from left", [], dc.LEFT, 2, BulletEnemy),
            ("[enemy] cant shot shot up", [], dc.LEFT, 3, BulletEnemy),
            ("[enemy] cant shot up from down", [], dc.DOWN, 3, BulletEnemy),
            ("[enemy] cant shot shot turn right", [], dc.UP, 4, BulletEnemy),
            (
                "[enemy] cant shot turn right from right",
                [],
                dc.RIGHT,
                4,
                BulletPlayer,
            ),
        ]
        for case_name, ed_list, sd, tn, bc in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct_list=ed_list,
                shot_direct=sd,
                turn_num=tn,
                bullet_class=bc,
            ):
                self.setUp()
                split = Split(0, 7)
                bullet = bc(0, 7, sd)
                for _ in range(tn):
                    split.mainte()
                bullet_list = split.reshot(bullet)
                self.assertEqual(len(ed_list), len(bullet_list))
                for i, ed in enumerate(ed_list):
                    self.assertEqual(
                        (
                            ed.value[0] * 8 + BulletPlayer.get_start_pos(ed.value[0]),
                            ed.value[1] * 8
                            + 7 * 8
                            + BulletPlayer.get_start_pos(ed.value[1]),
                        ),
                        bullet_list[i].get_pos(),
                    )
                    self.assertEqual(ed, bullet_list[i].direct)
                self.tearDown()


class TestMerge(TestFieldParent):
    def test_draw(self):
        merge = Merge(0, 7)
        merge.draw()
        expected = [("draw_node", 0, 7, Node.UNIT_MERGE, Direct.RIGHT, None)]
        self.assertEqual(
            expected,
            self.test_field_view.get_call_params(),
            self.test_field_view.get_call_params(),
        )

    def test_reshot(self):
        dc = Direct
        test_cases = [
            ("shot right from up 2", [None, dc.RIGHT], [dc.UP] * 2, 0, BulletPlayer),
            (
                "shot right from up down",
                [None, dc.RIGHT],
                [dc.UP, dc.DOWN],
                0,
                BulletPlayer,
            ),
            (
                "shot right from down 4",
                [None, dc.RIGHT, None, dc.RIGHT],
                [dc.DOWN] * 4,
                0,
                BulletPlayer,
            ),
            ("cant shot right from left", [None, None], [dc.LEFT] * 2, 0, BulletPlayer),
            (
                "cant shot right from right",
                [None, None],
                [dc.RIGHT] * 2,
                0,
                BulletPlayer,
            ),
            (
                "shot down from right 2",
                [None, dc.DOWN],
                [dc.RIGHT] * 2,
                1,
                BulletPlayer,
            ),
            (
                "shot down from right left",
                [None, dc.DOWN],
                [dc.RIGHT, dc.LEFT],
                1,
                BulletPlayer,
            ),
            (
                "shot down from left 4",
                [None, dc.DOWN, None, dc.DOWN],
                [dc.LEFT] * 4,
                1,
                BulletPlayer,
            ),
            ("cant shot down from up", [None, None], [dc.UP] * 2, 1, BulletPlayer),
            (
                "shot left from down 2",
                [None, dc.LEFT],
                [dc.DOWN] * 2,
                2,
                BulletPlayer,
            ),
            (
                "shot left from down up",
                [None, dc.LEFT],
                [dc.DOWN, dc.UP],
                2,
                BulletPlayer,
            ),
            (
                "shot left from up 4",
                [None, dc.LEFT, None, dc.LEFT],
                [dc.UP] * 4,
                2,
                BulletPlayer,
            ),
            (
                "cant shot left from right",
                [None, None],
                [dc.RIGHT] * 2,
                2,
                BulletPlayer,
            ),
            (
                "shot up from left 2",
                [None, dc.UP],
                [dc.LEFT] * 2,
                3,
                BulletPlayer,
            ),
            (
                "shot up from left right",
                [None, dc.UP],
                [dc.LEFT, dc.RIGHT],
                3,
                BulletPlayer,
            ),
            (
                "shot up from right 4",
                [None, dc.UP, None, dc.UP],
                [dc.RIGHT] * 4,
                3,
                BulletPlayer,
            ),
            (
                "cant shot up from down",
                [None, None],
                [dc.DOWN] * 2,
                3,
                BulletPlayer,
            ),
            (
                "[enemy] cant shot right from up 2",
                [None] * 2,
                [dc.UP] * 2,
                0,
                BulletEnemy,
            ),
            (
                "[enemy] cant shot right from left",
                [None] * 2,
                [dc.LEFT] * 2,
                0,
                BulletEnemy,
            ),
            (
                "[enemy] cant shot down from right 2",
                [None] * 2,
                [dc.RIGHT] * 2,
                1,
                BulletEnemy,
            ),
            ("[enemy] cant shot down from up", [None] * 2, [dc.UP] * 2, 1, BulletEnemy),
            (
                "cant shot left from down 2",
                [None] * 2,
                [dc.DOWN] * 2,
                2,
                BulletEnemy,
            ),
            (
                "[enemy] cant shot left from right",
                [None] * 2,
                [dc.RIGHT] * 2,
                2,
                BulletEnemy,
            ),
            (
                "[enemy] cant shot up from left 2",
                [None] * 2,
                [dc.LEFT] * 2,
                3,
                BulletEnemy,
            ),
            (
                "[enemy] cant shot up from down",
                [None] * 2,
                [dc.DOWN] * 2,
                3,
                BulletEnemy,
            ),
        ]
        for case_name, ed_list, sd_list, tn, bc in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct_list=ed_list,
                shot_direct_list=sd_list,
                turn_num=tn,
                bullet_class=bc,
            ):
                self.setUp()
                merge = Merge(0, 7)
                for _ in range(tn):
                    merge.mainte()
                for i, ed in enumerate(ed_list):
                    bullet = bc(0, 7, sd_list[i])
                    bullet_list = merge.reshot(bullet)
                    if ed is None:
                        self.assertEqual([], bullet_list)
                        continue
                    self.assertEqual(1, len(bullet_list))
                    self.assertEqual(
                        (
                            ed.value[0] * 8 + BulletPlayer.get_start_pos(ed.value[0]),
                            ed.value[1] * 8
                            + 7 * 8
                            + BulletPlayer.get_start_pos(ed.value[1]),
                        ),
                        bullet_list[0].get_pos(),
                    )
                    self.assertEqual(ed, bullet_list[0].direct)
                self.tearDown()

    def test_reshot_merge_color(self):
        test_cases = [
            (
                f"shot {color} from {color} 2",
                [None, color],
                [color] * 2,
            )
            for color in [
                Color.NODE_BLUE,
                Color.NODE_RED,
                Color.NODE_GREEN,
                Color.NODE_YELLOW,
                Color.NODE_CYAN,
                Color.NODE_PURPLE,
                Color.NODE_ORANGE,
                Color.NODE_BROWN,
                Color.NODE_NAVY,
                Color.NODE_DEEP_BLUE,
                Color.NODE_GRAY,
            ]
        ]
        test_cases += [
            (
                f"shot {color} from {conv_color[0]} {conv_color[1]}",
                [None, color],
                conv_color,
            )
            for color, merge_color in [
                (Color.NODE_YELLOW, [Color.NODE_RED, Color.NODE_GREEN]),
                (Color.NODE_CYAN, [Color.NODE_GREEN, Color.NODE_BLUE]),
                (Color.NODE_PURPLE, [Color.NODE_RED, Color.NODE_BLUE]),
                (Color.NODE_ORANGE, [Color.NODE_RED, Color.NODE_YELLOW]),
                (Color.NODE_BROWN, [Color.NODE_YELLOW, Color.NODE_BLUE]),
                (Color.NODE_NAVY, [Color.NODE_PURPLE, Color.NODE_BLUE]),
                (Color.NODE_DEEP_BLUE, [Color.NODE_BLUE, Color.NODE_CYAN]),
                (Color.NODE_GRAY, [Color.NODE_ORANGE, Color.NODE_BROWN]),
            ]
            for conv_color in [merge_color, merge_color[::-1]]
        ]
        for case_name, ec_list, sc_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_color_list=ec_list,
                shot_color_list=sc_list,
            ):
                self.setUp()
                merge = Merge(0, 7)
                for i, ec in enumerate(ec_list):
                    bullet = BulletPlayer(0, 7, Direct.UP, color=sc_list[i])
                    bullet_list = merge.reshot(bullet)
                    if ec is None:
                        self.assertEqual([], bullet_list)
                        continue
                    self.assertEqual(1, len(bullet_list))
                    self.assertEqual(
                        (
                            1 * 8 + BulletPlayer.get_start_pos(1),
                            7 * 8 + BulletPlayer.get_start_pos(0),
                        ),
                        bullet_list[0].get_pos(),
                    )
                    self.assertEqual(ec, bullet_list[0].color)
                self.tearDown()


if __name__ == "__main__":
    unittest.main()
