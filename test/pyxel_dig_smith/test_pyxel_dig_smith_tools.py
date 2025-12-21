import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from pyxel_dig_smith.main import (  # pylint: disable=C0413
    IView,
    IInput,
    IUnitView,
    GameObject,
    Color,
    Furnace,
)
from pyxel_dig_smith.logic import (  # pylint: disable=C0413
    IFieldGenerator,
    Item,
)


class TestView(IView):
    def __init__(self):
        self.frame = 0
        self.call_params = []

    def draw_text(self, x, y, text, color):
        self.call_params.append(("draw_text", x, y, text, color))

    def draw_image(self, x, y, src_x, src_y, is_dither, offset=(0, 0), is_revert=False):
        self.call_params.append(
            ("draw_image", x, y, src_x, src_y, is_dither, offset, is_revert)
        )

    def draw_rect(self, x, y, width, height, color, is_fill):
        self.call_params.append(("draw_rect", x, y, width, height, color, is_fill))

    def set_clip(self, rect):
        self.call_params.append(("set_clip", rect))

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
        self.mouse_pos = None

    def is_click(self):
        return self.b_is_click

    def get_mouse_x(self):
        return self.mouse_pos[0]

    def get_mouse_y(self):
        return self.mouse_pos[1]

    def set_is_click(self, b_is_click):
        self.b_is_click = b_is_click

    def set_mouse_pos(self, x, y):
        self.mouse_pos = (x, y)

    def reset(self):
        self.b_is_click = False
        self.mouse_pos = None


class TestUnitView(IUnitView):
    def __init__(self):
        self.call_params = []

    def draw_unit(self, x, y, image_x, image_y, face, direct, offset):
        self.call_params.append(
            ("draw_unit", x, y, image_x, image_y, face, direct, offset)
        )

    def get_call_params(self):
        return self.call_params

    def reset(self):
        self.call_params = []


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "pyxel_dig_smith.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "pyxel_dig_smith.main.PyxelInput.create", return_value=self.test_input
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
            "pyxel_dig_smith.main.PyxelUnitView.create",
            return_value=self.test_unit_view,
        )
        self.mock_unit_view = self.patcher_unit_view.start()
        self.test_field_generator = TestFieldGenerator()
        self.patcher_field_generator = patch(
            "pyxel_dig_smith.logic.FieldGenerator.create",
            return_value=self.test_field_generator,
        )
        self.mock_field_generator = self.patcher_field_generator.start()
        self.patcher_gamecore_is_game_over = patch(
            "pyxel_dig_smith.main.GameCore.is_game_over", return_value=False
        )
        self.mock_bag_is_game_over = self.patcher_gamecore_is_game_over.start()

    def tearDown(self):
        super().tearDown()
        self.patcher_unit_view.stop()
        self.patcher_field_generator.stop()
        self.patcher_gamecore_is_game_over.stop()

    def reset(self):
        super().reset()
        self.test_unit_view.reset()
        self.test_field_generator.reset()


def _generate_number_plot(horizon_pos, obj_rel_pos_map, size=GameObject.TILE_SIZE):
    number_plot = []
    for y in range(size):
        row = []
        abs_y = y + horizon_pos - (size // 2)
        for x in range(size):
            rel_pos = tuple(p - (size // 2) for p in (x, y))
            if rel_pos in obj_rel_pos_map:
                row.append(obj_rel_pos_map[rel_pos])
            elif abs_y <= -2:
                row.append(-3)  # sky
            elif abs_y == -1:
                row.append(-2)  # ground surface
            elif abs_y == 0:
                row.append(-1)  # ground
            elif abs_y == 1:
                row.append(1)  # layer 1
            elif 2 <= abs_y:
                for l, (y_range, _) in enumerate(IFieldGenerator.LAYERS):
                    if y_range[1] is None or abs_y < y_range[1]:
                        row.append(l + 2)
                        break
        number_plot.append(tuple(row))
    return tuple(number_plot)


def _get_number_plot_parameters(number_plot):
    obj_rel_pos_map = {}
    size = len(number_plot)
    horizon_pos = _get_horizon_pos([number_plot[i][0] for i in range(size)])
    base_rel_pos_map = _generate_number_plot(horizon_pos, {}, size=size)
    for y in range(size):
        for x in range(size):
            val = number_plot[y][x]
            base = base_rel_pos_map[y][x]
            if val != base:
                rel_pos = tuple(p - (size // 2) for p in (x, y))
                obj_rel_pos_map[rel_pos] = val
    return horizon_pos, obj_rel_pos_map


def _get_horizon_pos(layer_list):
    horizon_pos_map = {-3: -2, -2: -1, -1: 0, 1: 1, 2: 2} | {
        l + 2: y_range[0]
        for l, (y_range, _) in enumerate(IFieldGenerator.LAYERS)
        if l >= 1
    }
    size = len(layer_list)
    up_pos = horizon_pos_map[layer_list[0]] + (size // 2)
    down_pos = horizon_pos_map[layer_list[-1]] - (size // 2)
    ret = max(up_pos, down_pos)
    if layer_list[-1] >= 3 and layer_list[0] != layer_list[-1]:
        for i in range(size - 1):
            if layer_list[-2 - i] == layer_list[-1]:
                ret += 1
    return ret


class TestGenerateNumberPlot(unittest.TestCase):
    def test_generate(self):
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
                1,
                {},
            ),
            (
                "no dig (3x3)",
                (
                    (-1, -1, -1),
                    (1, 1, 1),
                    (2, 2, 2),
                ),
                1,
                {},
            ),
            (
                "no dig (7x7)",
                (
                    (-3, -3, -3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                ),
                1,
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
                1,
                {(0, 0): 0, (0, 1): 1},
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
                0,
                {},
            ),
            (
                "with ore",
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 11, 1, 1),
                    (2, 2, 1, 2, 2),
                ),
                0,
                {(0, 1): 11, (0, 2): 1},
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
                0,
                {(0, 1): 101},
            ),
            (
                "with ore in ground 2",
                (
                    (2, 2, 2, 2, 2),
                    (2, 2, 102, 2, 2),
                    (2, 2, 2, 2, 2),
                    (2, 2, 102, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
                4,
                {(0, -1): 102, (0, 1): 102},
            ),
            (
                "with ore in ground 2 (3x3)",
                (
                    (2, 102, 2),
                    (2, 2, 2),
                    (2, 102, 2),
                ),
                3,
                {(0, -1): 102, (0, 1): 102},
            ),
            (
                "with ore in ground 2 (7x7)",
                (
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 102, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 102, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                ),
                5,
                {(0, -1): 102, (0, 1): 102},
            ),
        ]
        for case_name, expected, horizon_pos, obj_rel_pos_map in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                horizon_pos=horizon_pos,
                obj_rel_pos_map=obj_rel_pos_map,
            ):
                ret = _generate_number_plot(
                    horizon_pos, obj_rel_pos_map, size=len(expected)
                )
                self.assertEqual(
                    expected,
                    ret,
                    ret,
                )

    def test_get_parameters(self):
        test_cases = [
            (
                "no dig",
                1,
                {},
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
            ),
            (
                "no dig 3x3",
                1,
                {},
                (
                    (-1, -1, -1),
                    (1, 1, 1),
                    (2, 2, 2),
                ),
            ),
            (
                "no dig 7x7",
                1,
                {},
                (
                    (-3, -3, -3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                ),
            ),
            (
                "1 dig",
                1,
                {(0, 0): 0, (0, 1): 1},
                (
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 0, 1, 1),
                    (2, 2, 1, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
            ),
            (
                "no dig (2, 1) center",
                0,
                {},
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 1, 1, 1),
                    (2, 2, 2, 2, 2),
                ),
            ),
            (
                "with ore",
                0,
                {(0, 1): 11, (0, 2): 1},
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 11, 1, 1),
                    (2, 2, 1, 2, 2),
                ),
            ),
            (
                "with ore in ground",
                0,
                {(0, 1): 101},
                (
                    (-3, -3, -3, -3, -3),
                    (-2, -2, -2, -2, -2),
                    (-1, -1, -1, -1, -1),
                    (1, 1, 101, 1, 1),
                    (2, 2, 2, 2, 2),
                ),
            ),
            (
                "with ore in ground 2",
                4,
                {(0, -1): 102, (0, 1): 102},
                (
                    (2, 2, 2, 2, 2),
                    (2, 2, 102, 2, 2),
                    (2, 2, 2, 2, 2),
                    (2, 2, 102, 2, 2),
                    (2, 2, 2, 2, 2),
                ),
            ),
            (
                "with ore in ground 2 (3x3)",
                3,
                {(0, -1): 102, (0, 1): 102},
                (
                    (2, 102, 2),
                    (2, 2, 2),
                    (2, 102, 2),
                ),
            ),
            (
                "with ore in ground 2 (7x7)",
                5,
                {(0, -1): 102, (0, 1): 102},
                (
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 102, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 102, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2, 2, 2),
                ),
            ),
            (
                "ground 2 -> 3",
                12,
                {},
                (
                    (2, 2, 2, 2, 2),
                    (2, 2, 2, 2, 2),
                    (3, 3, 3, 3, 3),
                    (3, 3, 3, 3, 3),
                    (3, 3, 3, 3, 3),
                ),
            ),
        ]
        for (
            case_name,
            expected_horizon_pos,
            expected_obj_rel_pos_map,
            number_plot,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_horizon_pos=expected_horizon_pos,
                expected_obj_rel_pos_map=expected_obj_rel_pos_map,
                number_plot=number_plot,
            ):
                horizon_pos, obj_rel_pos_map = _get_number_plot_parameters(number_plot)
                self.assertEqual(expected_horizon_pos, horizon_pos)
                self.assertEqual(expected_obj_rel_pos_map, obj_rel_pos_map)


ORE_MAP = {
    1: Item.METAL_1,
    2: Item.METAL_2,
    3: Item.METAL_3,
    4: Item.METAL_4,
    5: Item.METAL_5,
    6: Item.COAL,
    7: Item.JEWEL,
}


def get_expected_draw(number_plot, center_pos):
    # x*yの配列を渡して、想定される描画内容を作り出す。
    # 配列には、描画されるMapTipのIDが書かれる。
    # n * 100は鉱石を指す。地層をmとして、n*100 + mでIDが表現される。
    expected_draw = []
    obj_id_map = {
        -2: (4, 3),
        1: (3, 3),
        2: (1, 2),
        3: (2, 2),
        4: (3, 2),
        5: (4, 2),
        6: (5, 2),
    }
    for rel_x in range(GameObject.TILE_SIZE):
        for rel_y in range(GameObject.TILE_SIZE):
            abs_x, abs_y = tuple(
                pos + center - GameObject.TILE_TILT
                for pos, center in zip((rel_x, rel_y), center_pos)
            )
            obj_id = (
                number_plot[rel_y][rel_x]
                if number_plot[rel_y][rel_x] < 100
                else number_plot[rel_y][rel_x] % 100
            )
            upper_id = number_plot[rel_y][rel_x] // 100
            if obj_id == -3:
                expected_draw.append(
                    ("draw_rect", abs_x * 8, abs_y * 8, 8, 8, Color.BLUE, True)
                )
                continue
            elif obj_id in [-1, 21, 22]:
                expected_draw.append(
                    ("draw_rect", abs_x * 8, abs_y * 8, 8, 8, Color.SKY_BLUE, True)
                )
                continue
            elif obj_id == 0:
                continue
            elif obj_id in obj_id_map:
                image_pos = obj_id_map[obj_id]
            else:
                continue
            expected_draw.append(
                ("draw_image", abs_x, abs_y, *image_pos, False, (0, 0), False)
            )
            if upper_id in ORE_MAP:
                # 埋まっている鉱石
                expected_draw.append(
                    (
                        "draw_image",
                        abs_x,
                        abs_y,
                        *ORE_MAP[upper_id].value,
                        True,
                        (0, 0),
                        False,
                    )
                )
    return expected_draw


def get_expected_object_draw(number_plot, center_pos):
    expected_draw = []
    ores_pos_map = {}
    furnace_pos = None
    for rel_x in range(GameObject.TILE_SIZE):
        for rel_y in range(GameObject.TILE_SIZE):
            abs_x, abs_y = tuple(
                abs + senter - GameObject.TILE_TILT
                for abs, senter in zip((rel_x, rel_y), center_pos)
            )
            obj_id = (
                number_plot[rel_y][rel_x]
                if number_plot[rel_y][rel_x] < 100
                else number_plot[rel_y][rel_x] % 100
            )
            # 掘り起こした鉱石
            ore_id = obj_id - 10
            if ore_id in ORE_MAP:
                ores_pos_map[(abs_x, abs_y)] = ORE_MAP[ore_id]
            elif obj_id == 21:
                furnace_pos = (abs_x, abs_y)
    for pos, item in ores_pos_map.items():
        expected_draw.append(("draw_image", *pos, *item.value, False, (0, 0), False))
    if furnace_pos is not None:
        expected_draw.append(
            ("draw_image", *furnace_pos, *Furnace.IMAGE_POS, False, (0, 0), False)
        )
    return expected_draw


class TestFieldGenerator(IFieldGenerator):
    def __init__(self):
        super().__init__()
        self.response_map = {}
        self.b_is_digable = True
        self.is_digable_params = None

    def get_item(self, axis_x, axis_y):
        return self.response_map.get((axis_x, axis_y), None)

    def is_digable(self, axis_x, axis_y, pickaxe):  # pylint: disable=W0613
        self.is_digable_params = (axis_x, axis_y, pickaxe)
        return self.b_is_digable

    def set_item(self, target_map):
        self.response_map = target_map

    def set_digable(self, flag):
        self.b_is_digable = flag

    def get_is_digable_params(self):
        return self.is_digable_params

    def reset(self):
        self.response_map = {}


if __name__ == "__main__":
    unittest.main()
