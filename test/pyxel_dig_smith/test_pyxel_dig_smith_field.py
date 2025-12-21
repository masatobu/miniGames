import os
import sys
import unittest

for p in ["../src/", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from test_pyxel_dig_smith_tools import (  # pylint: disable=C0413
    TestUnitParent,
    _generate_number_plot,
    _get_number_plot_parameters,
    get_expected_draw,
    get_expected_object_draw,
)
from pyxel_dig_smith.main import (  # pylint: disable=C0413
    GameCore,
    Field,
    Direct,
    Ore,
    Furnace,
)
from pyxel_dig_smith.logic import (  # pylint: disable=C0413
    Item,
    Pickaxe,
    IFieldGenerator,
)


class TestField(TestUnitParent):
    def test_draw(self):
        test_cases = [
            (
                "no dig",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                set(),
                (2, 2),
                {},
            ),
            (
                "1 dig",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 0, 1, 1),
                    (2, 2, 1, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                {(2, 2)},
                (2, 2),
                {},
            ),
            (
                "no dig (2, 1) center",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                ),
                set(),
                (2, 1),
                {},
            ),
            (
                "with ore",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (11, 12, 13, 14, 15),
                    (1, 1, 1, 1, 1),
                ),
                {(0, 2), (1, 2), (3, 2), (4, 2)},
                (2, 1),
                {
                    (0, 2): (Item.METAL_1, False),
                    (1, 2): (Item.METAL_2, False),
                    (2, 2): (Item.METAL_3, False),
                    (3, 2): (Item.METAL_4, False),
                    (4, 2): (Item.METAL_5, False),
                },
            ),
            (
                "with ore 2",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (16, 17, 1, 1, 1),
                    (1, 1, 2, 2, 2),
                ),
                {(0, 2), (1, 2)},
                (2, 1),
                {(0, 2): (Item.COAL, False), (1, 2): (Item.JEWEL, False)},
            ),
            (
                "with ore in ground",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 101, 1, 1),
                    (2, 2, 2, 2, 2),
                ),
                set(),
                (2, 1),
                {(2, 2): (Item.METAL_1, True)},
            ),
            (
                "with ore in ground 2",
                (
                    (2, 2, 2, 2, 2),
                    (302, 2, 102, 2, 502),
                    (2, 2, 2, 2, 2),
                    (402, 2, 202, 2, 602),
                    (2, 2, 2, 2, 2),
                ),
                set(),
                (2, 5),
                {
                    (0, 4): (Item.METAL_3, True),
                    (0, 6): (Item.METAL_4, True),
                    (2, 4): (Item.METAL_1, True),
                    (2, 6): (Item.METAL_2, True),
                    (4, 4): (Item.METAL_5, True),
                    (4, 6): (Item.COAL, True),
                },
            ),
            (
                "ground 2 to 3",
                (
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                    (3, 3, 3, 3, 3),
                    (3, 3, 3, 3, 3),
                    (3, 3, 3, 3, 3),
                ),
                set(),
                (2, IFieldGenerator.LAYERS[1][0][0]),
                {},
            ),
            (
                "ground 3 to 4",
                (
                    (3, 3, 3, 3, 3),
                    (3, 3, 3, 3, 3),
                    (4, 4, 4, 4, 4),
                    (4, 4, 4, 4, 4),
                    (4, 4, 4, 4, 4),
                ),
                set(),
                (2, IFieldGenerator.LAYERS[2][0][0]),
                {},
            ),
            (
                "ground 4 to 5",
                (
                    (4, 4, 4, 4, 4),
                    (4, 4, 4, 4, 4),
                    (5, 5, 5, 5, 5),
                    (5, 5, 5, 5, 5),
                    (5, 5, 5, 5, 5),
                ),
                set(),
                (2, IFieldGenerator.LAYERS[3][0][0]),
                {},
            ),
            (
                "ground 5 to 6",
                (
                    (5, 5, 5, 5, 5),
                    (5, 5, 5, 5, 5),
                    (6, 6, 6, 6, 6),
                    (6, 6, 6, 6, 6),
                    (6, 6, 6, 6, 6),
                ),
                set(),
                (2, IFieldGenerator.LAYERS[4][0][0]),
                {},
            ),
            (
                "with furnace",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, 21),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                ),
                {},
                (2, 1),
                {(4, 1): (Furnace, False)},
            ),
        ]
        for case_name, expected, dig_pos_set, center_pos, objects in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                dig_pos_set=dig_pos_set,
                center_pos=center_pos,
                objects=objects,
            ):
                self.reset()
                expected_full = _generate_number_plot(
                    *_get_number_plot_parameters(expected)
                )
                self.test_field_generator.set_item(
                    {
                        k: v[0]
                        for k, v in objects.items()
                        if isinstance(v[0], Item) and v[1]
                    }
                )
                field = self._generate_field(dig_pos_set, center_pos, objects)
                field.draw()
                expected_draw = [("set_clip", GameCore.CAMERA_RECT)]
                expected_draw = expected_draw + get_expected_draw(
                    expected_full, center_pos
                )
                expected_draw = expected_draw + get_expected_object_draw(
                    expected_full, center_pos
                )
                expected_draw.append(("set_clip", None))
                self.assertEqual(
                    expected_draw,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def _generate_field(self, dig_pos_set, center_pos, objects):
        # objectsは、pos: (オブジェクト, 埋まっているか否か)
        field = Field(center_pos)
        field.ores_map = {
            pos: Ore(pos, v[0])
            for pos, v in objects.items()
            if isinstance(v[0], Item) and not v[1]
        }
        field.dig_pos_set = dig_pos_set
        furnace_pos = [k for k, v in objects.items() if v[0] == Furnace]
        field.furnace = None if len(furnace_pos) == 0 else Furnace(furnace_pos[0])

        return field

    def test_convert_to_abs_axis(self):
        tilt = GameCore.TILE_TILT
        test_cases = [
            ("base axis", (2, 2), (2, 2), (tilt, tilt)),
            ("base axis slide", (2, 3), (2, 2), (tilt, tilt + 1)),
            ("x - 1 axis", (1, 2), (1, 2), (tilt, tilt)),
            ("y - 1 axis", (2, 1), (2, 1), (tilt, tilt)),
            ("x + 1 axis", (3, 2), (3, 2), (tilt, tilt)),
            ("y + 1 axis", (2, 3), (2, 3), (tilt, tilt)),
        ]
        for case_name, expected, center_pos, screen_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                center_pos=center_pos,
                screen_pos=screen_pos,
            ):
                self.reset()
                field = Field(center_pos)
                self.assertEqual(
                    expected,
                    field._convert_to_abs_pos(screen_pos),  # pylint: disable=W0212
                )

    def test_is_movable(self):
        test_cases = [
            ("on ground", True, (0, 1), {}),
            ("slide ground", True, (1, 1), {}),
            ("under ground", False, (0, 2), {}),
            ("over sky", False, (0, 0), {}),
            ("furnace", False, (0, 1), {(0, 1): (Furnace, False)}),
            ("out furnace", True, (0, 1), {(1, 1): (Furnace, False)}),
        ]
        for case_name, expected, pos, object_pos_map in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                pos=pos,
                object_pos_map=object_pos_map,
            ):
                self.reset()
                field = self._generate_field(set(), (2, 2), object_pos_map)
                self.assertEqual(expected, field.is_movable(pos))

    def test_is_hit_furnace(self):
        test_cases = [
            ("no hit", False, (-2, 1), Direct.RIGHT),
            ("hit", True, (-1, 1), Direct.RIGHT),
            ("near but not hit", False, (-1, 1), Direct.LEFT),
            ("under hit", True, (0, 2), Direct.UP),
        ]
        for case_name, expected, abs_pos, direct in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, abs_pos=abs_pos, direct=direct
            ):
                self.reset()
                object_pos_map = {(0, 1): (Furnace, False)}
                field = self._generate_field(set(), (2, 2), object_pos_map)
                self.assertEqual(expected, field.is_hit_furnance(abs_pos, direct))

    def test_dig(self):
        test_cases = [
            (
                "no dig",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                [],
                False,
            ),
            (
                "1 dig 1",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 0, 1, 1),
                    (2, 2, 1, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                [(2, 2)],
                False,
            ),
            (
                "1 dig 2",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 0, 2),
                    (2, 2, 2, 1, 2),
                ),
                [(3, 3)],
                False,
            ),
            (
                "2 dig 1",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 0, 1),
                    (2, 2, 2, 0, 2),
                    (2, 2, 2, 1, 2),
                ),
                [(3, 2), (3, 3)],
                False,
            ),
            (
                "dig out",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 11, 1),
                    (2, 2, 2, 1, 2),
                    (2, 2, 2, 2, 2),
                ),
                [(3, 2)],
                True,
            ),
            (
                "cant dig sky",
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                [(2, 0), (2, -1)],
                False,
            ),
        ]
        for case_name, expected, dig_pos_list, is_appeared in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                dig_pos_set=dig_pos_list,
                is_appeared=is_appeared,
            ):
                self.reset()
                expected_full = _generate_number_plot(
                    *_get_number_plot_parameters(expected)
                )
                self.test_field_generator.set_item(
                    {k: Item.METAL_1 for k in dig_pos_list if is_appeared}
                    if is_appeared
                    else {}
                )
                field = self._generate_field(set(), (2, 2), {})
                for pos in dig_pos_list:
                    field.dig(pos, Pickaxe.JEWEL)
                field.draw()
                expected_draw = [("set_clip", GameCore.CAMERA_RECT)]
                expected_draw = expected_draw + get_expected_draw(expected_full, (2, 2))
                expected_draw = expected_draw + get_expected_object_draw(
                    expected_full, (2, 2)
                )
                expected_draw.append(("set_clip", None))
                self.assertEqual(
                    expected_draw,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_dig_stratum(self):
        test_cases = (
            [
                (
                    "dig ground 2",
                    (
                        (-2, -2, -2, -2, -2),
                        (-1, -1, -1, -1, -1),
                        (1, 1, 0, 1, 1),
                        (2, 2, 1, 2, 2),
                        (2, 2, 2, 2, 2),
                    ),
                    (2, 2),
                    True,
                )
            ]
            + [
                (
                    f"dig ground {x} to {y}",
                    (
                        (x, x, x, x, x),
                        (x, x, x, x, x),
                        (y, y, 0, y, y),
                        (y, y, 1, y, y),
                        (y, y, y, y, y),
                    ),
                    (2, IFieldGenerator.LAYERS[x - 1][0][0]),
                    True,
                )
                for x, y in [(2, 3), (3, 4), (4, 5), (5, 6)]
            ]
            + [
                (
                    "cant ground 2",
                    (
                        (-2, -2, -2, -2, -2),
                        (-1, -1, -1, -1, -1),
                        (1, 1, 1, 1, 1),
                        (2, 2, 2, 2, 2),
                        (2, 2, 2, 2, 2),
                    ),
                    (2, 2),
                    False,
                )
            ]
            + [
                (
                    f"cant ground {x} to {y}",
                    (
                        (x, x, x, x, x),
                        (x, x, x, x, x),
                        (y, y, y, y, y),
                        (y, y, y, y, y),
                        (y, y, y, y, y),
                    ),
                    (2, IFieldGenerator.LAYERS[x - 1][0][0]),
                    False,
                )
                for x, y in [(2, 3), (3, 4), (4, 5), (5, 6)]
            ]
        )
        for case_name, expected, center_pos, is_digable in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                center_pos=center_pos,
                is_digable=is_digable,
            ):
                self.reset()
                expected_full = _generate_number_plot(
                    *_get_number_plot_parameters(expected)
                )
                field = self._generate_field(set(), center_pos, {})
                self.test_field_generator.set_digable(is_digable)
                field.dig(center_pos, Pickaxe.JEWEL)
                field.draw()
                expected_draw = [("set_clip", GameCore.CAMERA_RECT)]
                expected_draw = expected_draw + get_expected_draw(
                    expected_full, center_pos
                )
                expected_draw = expected_draw + get_expected_object_draw(
                    expected_full, center_pos
                )
                expected_draw.append(("set_clip", None))
                self.assertEqual(
                    expected_draw,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_get_ore(self):
        test_cases = [
            ("found", Item.METAL_1, (2, 1), (2, 1)),
            ("not found", None, (2, 1), (2, 2)),
        ]
        for case_name, expected, get_pos, set_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, get_pos=get_pos, set_pos=set_pos
            ):
                self.reset()
                dig_pos_set = {set_pos}
                center_pos = (2, 2)
                objects_map = {set_pos: (Item.METAL_1, False)}
                field = self._generate_field(dig_pos_set, center_pos, objects_map)
                self.assertEqual(expected, field.get_ore(get_pos))

    def test_delete_ore(self):
        dig_pos_set = {(2, 1)}
        center_pos = (2, 2)
        objects_map = {(2, 1): (Item.METAL_1, False)}
        field = self._generate_field(dig_pos_set, center_pos, objects_map)
        field.delete_ore((2, 1))
        self.assertEqual({}, field.ores_map)

    def test_get_route(self):
        test_cases = [
            ("left", [Direct.LEFT], (-1, 0), set()),
            ("right", [Direct.RIGHT], (1, 0), set()),
            ("up", [Direct.UP], (0, -1), set()),
            ("down", [Direct.DOWN], (0, 1), set()),
            ("2 left", [Direct.LEFT] * 2, (-2, 0), set()),
            ("2 right", [Direct.RIGHT] * 2, (2, 0), set()),
            ("2 up", [Direct.UP] * 2, (0, -2), set()),
            ("2 down", [Direct.DOWN] * 2, (0, 2), set()),
            ("left up", [Direct.UP, Direct.LEFT], (-1, -1), set()),
            (
                "2 right 2 down",
                [Direct.DOWN, Direct.DOWN, Direct.RIGHT, Direct.RIGHT],
                (2, 2),
                set(),
            ),
            ("out", [], (0, 0), set()),
            ("select dig pos", [Direct.UP, Direct.LEFT], (-1, -1), {(2, 1)}),
        ]
        for case_name, expected, rel_pos, dig_pos_set in test_cases:
            with self.subTest(case_name=case_name, expected=expected, rel_pos=rel_pos):
                self.reset()
                center_pos = (2, 2)
                objects_map = {}
                field = self._generate_field(dig_pos_set, center_pos, objects_map)
                self.assertEqual(field.get_route(rel_pos), expected)


if __name__ == "__main__":
    unittest.main()
