import os
import sys
import unittest

for p in ["../src/", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from test_pyxel_dig_smith_tools import (  # pylint: disable=C0413
    TestUnitParent,
)
from main import (  # pylint: disable=C0413
    GameCore,
    Direct,
    Color,
    Ore,
    Bag,
    Cursor,
    Furnace,
    Forge,
    Icon,
    Console,
    Position,
)
from logic import (  # pylint: disable=C0413
    Item,
    Pickaxe,
)


class TestGameCore(TestUnitParent):
    def setUp(self):
        super().setUp()
        self.reset()

    def reset(self):
        super().reset()
        self.core = GameCore()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.core.player.pos = (2, 1)
        self.core.field.set_center((2, 1))
        self.core.field.dig_pos_set = set()
        self.core.field.ores_map = {}
        self.core.field.furnace = None
        self.core.bag.item_map = {}

    def check(self):
        self.assertEqual(
            self.test_view.get_call_params(),
            self.expect_view_call,
            self.test_view.get_call_params(),
        )
        self.assertEqual(
            self.test_unit_view.get_call_params(),
            self.expect_unit_view_call,
            self.test_unit_view.get_call_params(),
        )

    def put_draw_result(self, draw_action_list, center_pos, move_dir=None, move_len=0):
        offset = (
            tuple(p * move_len for p in move_dir.value)
            if move_dir is not None
            else (0, 0)
        )
        bef_center = tuple(
            p - d
            for p, d in zip(
                center_pos, move_dir.value if move_dir is not None else (0, 0)
            )
        )
        for draw_action in draw_action_list:
            if draw_action[0] == "clear":
                tilt = tuple(
                    b * 8 + o - m // 2 + 4
                    for b, o, m in zip(
                        bef_center,
                        offset,
                        (GameCore.MONITOR_WIDTH, GameCore.MONITOR_WIDTH),
                    )
                )
                self.expect_view_call.append(("clear", *tilt))
            elif draw_action[0] == "clip start":
                clip_rect = GameCore.CAMERA_RECT
                self.expect_view_call.append(("set_clip", clip_rect))
            elif draw_action[0] == "clip end":
                self.expect_view_call.append(("set_clip", None))
            elif draw_action[0] == "field":
                self._put_draw_result_field(draw_action[1], center_pos)
            elif draw_action[0] == "player":
                self.expect_unit_view_call.append(
                    ("draw_unit", *bef_center, 1, 0, *draw_action[1:3], offset)
                )
            elif draw_action[0] in ["ore", "furnace"]:
                image_pos = None
                if draw_action[0] == "ore":
                    image_pos = draw_action[2].value
                elif draw_action[0] == "furnace":
                    image_pos = Furnace.IMAGE_POS
                self.expect_view_call.append(
                    (
                        "draw_image",
                        *draw_action[1],
                        *image_pos,
                        False,
                        (0, 0),
                        False,
                    )
                )
            elif draw_action[0] == "bag":
                self._put_draw_result_bag(
                    offset,
                    bef_center,
                    draw_action[1],
                    draw_action[2],
                    draw_action[3],
                    draw_action[4],
                )
            elif draw_action[0] == "forge":
                self._put_draw_result_forge(offset, bef_center, draw_action[1])
            elif draw_action[0] == "cursor":
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        (center_pos[0] + draw_action[1][0] - GameCore.TILE_TILT) * 8,
                        (center_pos[1] + draw_action[1][1] - GameCore.TILE_TILT) * 8,
                        8,
                        8,
                        Color.RED,
                        False,
                    )
                )
            elif draw_action[0] == "console":
                self._put_draw_result_console(offset, bef_center, draw_action[1])
            elif draw_action[0] == "position":
                draw_pos = tuple(
                    (ct - GameCore.TILE_TILT + dp) * 8 + to + o
                    for ct, dp, to, o in zip(
                        bef_center, Position.TILE_POS, Position.TEXT_OFFSET, offset
                    )
                )
                text = f"({bef_center[0] - 2},{bef_center[1] - 1})"
                self.expect_view_call.append(
                    (
                        "draw_text",
                        *draw_pos,
                        text,
                        Color.WHITE,
                    )
                )

    def _put_draw_result_bag(
        self, offset, bef_center, item_map, select_item, equip_item, strength
    ):
        draw_pos = tuple(
            ct - GameCore.TILE_TILT + dp for ct, dp in zip(bef_center, Bag.TILE_POS)
        )
        self.expect_view_call.append(
            (
                "draw_rect",
                draw_pos[0] * 8 + offset[0] - 1,
                draw_pos[1] * 8 + offset[1] - 1,
                8 * len(Bag.ITEM_POS_MAP[0]) + 2,
                8 * len(Bag.ITEM_POS_MAP) + 2,
                Color.WHITE,
                False,
            )
        )
        for y, item_list in enumerate(Bag.ITEM_POS_MAP):
            for x, item in enumerate(item_list):
                color = Color.DARK_BLUE if (x + y) % 2 == 1 else Color.BLACK
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        (draw_pos[0] + x) * 8 + offset[0],
                        (draw_pos[1] + y) * 8 + offset[1],
                        8,
                        8,
                        color,
                        True,
                    )
                )
                if item in item_map:
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            draw_pos[0] + x,
                            draw_pos[1] + y,
                            *item.value,
                            False,
                            offset,
                            False,
                        )
                    )
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            *tuple(
                                (p + i) * 8 + no + do
                                for p, i, no, do in zip(
                                    draw_pos,
                                    (x, y),
                                    Bag.NUM_OFFSET,
                                    offset,
                                )
                            ),
                            str(item_map[item]),
                            Color.WHITE,
                        )
                    )
                    if item == select_item:
                        self.expect_view_call.append(
                            (
                                "draw_rect",
                                (draw_pos[0] + x) * 8 + offset[0],
                                (draw_pos[1] + y) * 8 + offset[1],
                                8,
                                8,
                                Color.YELLOW,
                                False,
                            )
                        )
        draw_pos = tuple(
            ct - GameCore.TILE_TILT + dp
            for ct, dp in zip(bef_center, Bag.EQUIP_TILE_POS)
        )
        self.expect_view_call.extend(
            [
                (
                    "draw_rect",
                    draw_pos[0] * 8 + offset[0] - 1,
                    draw_pos[1] * 8 + offset[1] - 1,
                    8 * 2 + 2,
                    8 * 2 + 2,
                    Color.WHITE,
                    False,
                )
            ]
        )
        for y in range(2):
            for x in range(2):
                color = Color.DARK_BLUE if (x + y) % 2 == 1 else Color.BLACK
                if (x, y) == (1, 0) and equip_item is not None:
                    color = Color.BLACK
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        (draw_pos[0] + x) * 8 + offset[0],
                        (draw_pos[1] + y) * 8 + offset[1],
                        8,
                        8,
                        color,
                        True,
                    )
                )
                if (x, y) == (0, 0):
                    params = (
                        (equip_item.value, False)
                        if equip_item is not None
                        else (
                            Icon.PICKAXE_SHADE.value,
                            True,
                        )
                    )
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            draw_pos[0] + x,
                            draw_pos[1] + y,
                            *params[0],
                            params[1],
                            offset,
                            False,
                        )
                    )
                if (x, y) == (1, 0) and equip_item is not None:
                    current_max_strength = int(
                        Bag.MAX_STRENGTH
                        * Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                    )
                    self.expect_view_call.append(
                        (
                            "draw_rect",
                            (draw_pos[0] + x) * 8 + offset[0],
                            (draw_pos[1] + y) * 8 + offset[1],
                            1 + int(5 * strength / current_max_strength),
                            8,
                            Color.YELLOW,
                            True,
                        )
                    )
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            draw_pos[0] + x,
                            draw_pos[1] + y,
                            *Icon.STRENGTH.value,
                            False,
                            offset,
                            False,
                        )
                    )
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            *tuple(
                                (p + t) * 8 + o + do
                                for p, t, o, do in zip(
                                    draw_pos,
                                    (x, y),
                                    Bag.NUM_OFFSET,
                                    offset,
                                )
                            ),
                            str((strength * 9) // current_max_strength),
                            Color.WHITE,
                        )
                    )
                if (x, y) == (0, 1):
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            draw_pos[0] + x,
                            draw_pos[1] + y,
                            *Item.JEWEL.value,
                            False,
                            offset,
                            False,
                        )
                    )
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            *tuple(
                                (p + t) * 8 + o + do
                                for p, t, o, do in zip(
                                    draw_pos,
                                    (x, y),
                                    Bag.NUM_OFFSET,
                                    offset,
                                )
                            ),
                            str(item_map.get(Item.JEWEL, 0)),
                            Color.WHITE,
                        )
                    )
                if (x, y) == (1, 1):
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            *tuple(
                                (p + t) * 8 + o + do + to
                                for p, t, o, do, to in zip(
                                    draw_pos,
                                    (x, y),
                                    Bag.NUM_OFFSET,
                                    offset,
                                    (-4, 0),
                                )
                            ),
                            "/3",
                            Color.WHITE,
                        )
                    )

    def _put_draw_result_forge(self, offset, bef_center, item_set):
        draw_pos = tuple(
            ct - GameCore.TILE_TILT + dp for ct, dp in zip(bef_center, Forge.TILE_POS)
        )
        for (x, y), item in Forge._get_box_item(  # pylint: disable=W0212
            Item.METAL_1
        ).items():
            frame_pos = tuple(p + e for p, e in zip((x, y), draw_pos))
            self.expect_view_call.append(
                (
                    "draw_rect",
                    frame_pos[0] * 8 + offset[0] - 1,
                    frame_pos[1] * 8 + offset[1] - 1,
                    10,
                    10,
                    Color.WHITE,
                    False,
                )
            )
            self.expect_view_call.append(
                (
                    "draw_rect",
                    frame_pos[0] * 8 + offset[0],
                    frame_pos[1] * 8 + offset[1],
                    8,
                    8,
                    Color.BLACK,
                    True,
                )
            )
            params = None
            if item in item_set:
                params = (item.value, False)
            elif (x, y) in Forge.SHADOW_MAP:
                shadow = Forge.SHADOW_MAP[(x, y)]
                box_item = item
                if shadow is not None:
                    params = (Forge.SHADOW_MAP[(x, y)].value, True)
                elif box_item is not None:
                    params = (box_item.value, True)
            if params is not None:
                self.expect_view_call.append(
                    (
                        "draw_image",
                        frame_pos[0],
                        frame_pos[1],
                        *params[0],
                        params[1],
                        offset,
                        False,
                    )
                )
                if (x, y) == (1, 2) and item in item_set:
                    self.expect_unit_view_call.append(
                        (
                            "draw_unit",
                            frame_pos[0],
                            frame_pos[1] - 1,
                            1,
                            1,
                            Direct.RIGHT,
                            Direct.RIGHT,
                            offset,
                        )
                    )
        for x, y, text in ((1, 0, "+"), (3, 0, "=")):
            frame_pos = tuple(p + dp for p, dp in zip((x, y), draw_pos))
            self.expect_view_call.append(
                (
                    "draw_text",
                    frame_pos[0] * 8 + 2,
                    frame_pos[1] * 8 + 1,
                    text,
                    Color.WHITE,
                )
            )

    def _put_draw_result_console(self, offset, bef_center, message_list):
        draw_pos = tuple(
            ct - GameCore.TILE_TILT + dp for ct, dp in zip(bef_center, Console.TILE_POS)
        )
        self.expect_view_call.append(
            (
                "draw_rect",
                draw_pos[0] * 8 + offset[0] - 1,
                draw_pos[1] * 8 + offset[1] - 1,
                8 * len(Console.FRAME_SIZE_MAP[0]) + 2,
                8 * len(Console.FRAME_SIZE_MAP) + 2,
                Color.WHITE,
                False,
            )
        )
        for y, item_list in enumerate(Console.FRAME_SIZE_MAP):
            for x in range(len(item_list)):
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        (draw_pos[0] + x) * 8 + offset[0],
                        (draw_pos[1] + y) * 8 + offset[1],
                        8,
                        8,
                        Color.BLACK,
                        True,
                    )
                )
        for i, text in enumerate(message_list):
            self.expect_view_call.append(
                (
                    "draw_text",
                    draw_pos[0] * 8 + 9,
                    (draw_pos[1] + i) * 8 + 1,
                    text,
                    Color.WHITE,
                )
            )

    def _put_draw_result_field(self, dig_pos_map, center_pos):
        for rel_x in range(GameCore.TILE_SIZE):
            for rel_y in range(GameCore.TILE_SIZE):
                abs_x, abs_y = tuple(
                    abs + senter - GameCore.TILE_TILT
                    for abs, senter in zip((rel_x, rel_y), center_pos)
                )
                if abs_y < 0:
                    self.expect_view_call.append(
                        ("draw_rect", abs_x * 8, abs_y * 8, 8, 8, Color.BLUE, True)
                    )
                    continue
                elif abs_y == 1:
                    self.expect_view_call.append(
                        ("draw_rect", abs_x * 8, abs_y * 8, 8, 8, Color.SKY_BLUE, True)
                    )
                    continue
                if (abs_x, abs_y) in dig_pos_map:
                    continue
                if abs_y == 0:
                    image_pos = (4, 3)
                elif abs_y == 2 or (abs_x, abs_y - 1) in dig_pos_map:
                    image_pos = (3, 3)
                elif abs_y > 2:
                    image_pos = (1, 2)
                else:
                    continue
                self.expect_view_call.append(
                    ("draw_image", abs_x, abs_y, *image_pos, False, (0, 0), False)
                )

    def test_draw(self):
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["clip start"],
                ["field", {}],
                ["clip end"],
                ["position"],
                ["player", Direct.RIGHT, Direct.NUTRAL],
                ["bag", {}, None, None, None],
            ],
            (2, 1),
        )
        self.check()

    def test_click(self):
        test_cases = [
            ("field", (1, 1), GameCore.CAMERA_RECT[:2]),
            ("bag", Bag.TILE_POS, tuple(p * 8 for p in Bag.TILE_POS)),
        ]
        for case_name, expected_pos, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                mouse_pos=mouse_pos,
            ):
                self.reset()
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", {}],
                        ["clip end"],
                        ["position"],
                        ["player", Direct.RIGHT, Direct.NUTRAL],
                        ["bag", {}, None, None, None],
                        ["cursor", expected_pos],
                    ],
                    (2, 1),
                )
                self.check()

    def test_dig(self):
        test_cases = [
            ("cant", False, None),
            ("digable with pickaxe", True, Pickaxe.METAL_1),
            ("cant with pickaxe", False, Pickaxe.JEWEL),
        ]
        for case_name, is_digable, equip_item in test_cases:
            with self.subTest(case_name=case_name, is_digable=is_digable):
                self.reset()
                if is_digable:
                    self.test_field_generator.set_item({(2, 2): Item.METAL_1})
                self.test_field_generator.set_digable(is_digable)
                mouse_pos = tuple(
                    p * 8 - t
                    for p, t in zip(
                        (GameCore.TILE_TILT, GameCore.TILE_TILT + 1), Cursor.TILT
                    )
                )
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                if equip_item is not None:
                    self.core.bag.push(equip_item)
                    self.core.bag.equip(Bag.EQUIP_TILE_POS, equip_item)
                for _ in range(2):
                    self.core.update()
                self.assertEqual(
                    self.test_field_generator.get_is_digable_params()[:2], (2, 2)
                )
                self.assertEqual(
                    self.test_field_generator.get_is_digable_params()[2], equip_item
                )
                self.core.draw()
                diged_set = {(2, 2)} if is_digable else set()
                expected_list = [["clear"], ["clip start"], ["field", diged_set]]
                if is_digable:
                    expected_list.append(["ore", (2, 2), Item.METAL_1])
                item_set = {equip_item: 1} if equip_item is not None else {}
                weight = (
                    Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                    if equip_item is not None
                    else 1.0
                )
                current_max_strength = int(Bag.MAX_STRENGTH * weight)
                strength = (
                    current_max_strength - 1 if is_digable else current_max_strength
                )
                expected_list.extend(
                    [
                        ["clip end"],
                        ["position"],
                        ["player", Direct.RIGHT, Direct.NUTRAL],
                        ["bag", item_set, None, equip_item, strength],
                    ]
                )
                self.put_draw_result(expected_list, (2, 1))
                self.check()
                self.assertEqual(
                    self.core.avail_item_map,
                    {Pickaxe.METAL_1: 1} | ({Item.METAL_1: 1} if is_digable else {}),
                )

    def test_get_ore(self):
        test_cases = [
            (
                "empty",
                [
                    ["clear"],
                    ["clip start"],
                    ["field", {(2, 2)}],
                    ["clip end"],
                    ["position"],
                    ["player", Direct.RIGHT, Direct.NUTRAL],
                    ["bag", {Item.METAL_1: 1}, None, None, None],
                ],
                {},
                (2, 2),
            ),
            (
                "over",
                [
                    ["clear"],
                    ["clip start"],
                    ["field", {(2, 2)}],
                    ["ore", (2, 2), Item.METAL_1],
                    ["clip end"],
                    ["position"],
                    ["player", Direct.RIGHT, Direct.NUTRAL],
                    ["bag", {Item.METAL_1: Bag.MAX_NUM}, None, None, None],
                ],
                {Item.METAL_1: Bag.MAX_NUM},
                (2, 2),
            ),
        ]
        for case_name, expected, items, center_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                items=items,
                center_pos=center_pos,
            ):
                self.reset()
                self.core.field.dig_pos_set = {(2, 2)}
                self.core.field.ores_map = {(2, 2): Ore((2, 2), Item.METAL_1)}
                self.core.bag.item_map = items
                mouse_pos = tuple(
                    p * 8 - t
                    for p, t in zip(
                        (GameCore.TILE_TILT, GameCore.TILE_TILT + 1), Cursor.TILT
                    )
                )
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                for _ in range(2):
                    self.core.update()
                for _ in range(8):
                    self.core.update()
                self.core.draw()

                self.assertEqual(
                    self.core.avail_item_map,
                    {Pickaxe.METAL_1: 1},
                )
                self.put_draw_result(expected, center_pos)
                self.check()

    def test_player_click_move(self):
        D = Direct
        test_cases = [
            ("walk ground to right", [(3, 1, False, D.RIGHT)], (1, 0), {(3, 2)}),
            ("walk ground to left", [(1, 1, False, D.LEFT)], (-1, 0), {(3, 2)}),
            ("hit groud", [(2, 2, True, D.RIGHT)], (0, 1), {(3, 2)}),
            ("walk hole", [(2, 2, False, D.RIGHT)], (0, 1), {(2, 2)}),
            (
                "walk ground to 2 right",
                [(3, 1, False, D.RIGHT), (4, 1, False, D.RIGHT)],
                (2, 0),
                {(3, 2)},
            ),
            ("cant jump", [(2, 1, False, D.RIGHT)], (0, -1), {(3, 2)}),
            (
                "dig 2 groud",
                [(2, 2, True, D.RIGHT), (2, 3, True, D.RIGHT)],
                (0, 2),
                {(3, 2)},
            ),
            (
                "dig right down groud",
                [(3, 1, False, D.RIGHT), (3, 2, True, D.RIGHT)],
                (1, 1),
                {(1, 2)},
            ),
            ("stop move", [(2, 1, False, D.RIGHT)], (0, -2), {(3, 2)}),
            ("forge pos", [(1, 1, False, D.LEFT)], (-1, -1), {(3, 2)}),
        ]
        for case_name, expected_list, click_rel_pos, dig_pos_set in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected_list,
                click_rel_pos=click_rel_pos,
                dig_pos_set=dig_pos_set,
            ):
                self.reset()
                self.core.field.dig_pos_set = dig_pos_set
                click_pos = tuple(p + GameCore.TILE_TILT for p in click_rel_pos)
                mouse_pos = tuple(p * 8 - t for p, t in zip(click_pos, Cursor.TILT))
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                bef_pos = (2, 1)
                for _ in range(2):
                    self.core.update()
                for expected in expected_list:
                    expected_pos = expected[:2]
                    if expected[2]:
                        self.core.update()
                    if expected_pos != bef_pos:
                        for _ in range(8):
                            self.core.update()
                    self.assertEqual(expected_pos, self.core.player.get_pos(None))
                    bef_pos = expected_pos
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", dig_pos_set],
                        ["clip end"],
                        ["position"],
                        ["player", expected[3], D.NUTRAL],
                        ["bag", {}, None, None, None],
                    ],
                    bef_pos,
                )
                self.check()

    def test_player_moving(self):
        test_cases = [
            ("walk to right", Direct.RIGHT, (1, 0), 1),
            ("walk to left", Direct.LEFT, (-1, 0), 1),
            ("walk to down", Direct.DOWN, (0, 1), 1),
            ("walk to up", Direct.UP, (0, -1), 1),
            ("walk to 2 down", Direct.DOWN, (0, 2), 2),
        ]
        for case_name, expected_direct, click_rel_pos, walk_steps in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                click_rel_pos=click_rel_pos,
                walk_steps=walk_steps,
            ):
                self.reset()
                self.core.field.dig_pos_set = {(2, 2), (1, 2), (3, 2), (2, 3), (2, 4)}
                mouse_pos = tuple(
                    p * 8 - t
                    for p, t in zip(
                        (GameCore.TILE_TILT, GameCore.TILE_TILT + 1), Cursor.TILT
                    )
                )
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                for _ in range(2):
                    self.core.update()
                for _ in range(8):
                    self.core.update()
                click_pos = tuple(p + GameCore.TILE_TILT for p in click_rel_pos)
                mouse_pos = tuple(p * 8 - t for p, t in zip(click_pos, Cursor.TILT))
                self.test_input.set_mouse_pos(*mouse_pos)
                for _ in range(2):
                    self.core.update()
                expected = (2, 2)
                face = Direct.RIGHT
                for _ in range(walk_steps):
                    expected = tuple(
                        p + d for p, d in zip(expected, expected_direct.value)
                    )
                    for i in range(8):
                        self.core.draw()
                        face = (
                            expected_direct
                            if expected_direct in (Direct.LEFT, Direct.RIGHT)
                            else Direct.RIGHT
                        )
                        self.put_draw_result(
                            [
                                ["clear"],
                                ["clip start"],
                                ["field", self.core.field.dig_pos_set],
                                ["clip end"],
                                ["position"],
                                ["player", face, expected_direct],
                                ["bag", {}, None, None, None],
                            ],
                            expected,
                            move_dir=expected_direct,
                            move_len=i,
                        )
                        self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", self.core.field.dig_pos_set],
                        ["clip end"],
                        ["position"],
                        ["player", face, Direct.NUTRAL],
                        ["bag", {}, None, None, None],
                    ],
                    expected,
                )
                self.check()

    def test_forge(self):
        D = Direct
        test_cases = [
            ("walk to", None, [(3, 1, D.RIGHT)], [D.RIGHT], set(), (5, 1)),
            ("hit to", set(), [(3, 1, D.RIGHT)], [D.RIGHT], set(), (4, 1)),
            ("left hit to", set(), [(2, 1, D.LEFT)], [D.LEFT], set(), (1, 1)),
            (
                "walk under",
                None,
                [(2, 2, D.RIGHT), (1, 2, D.LEFT)],
                [D.DOWN, D.LEFT],
                {(2, 2), (1, 2)},
                (1, 1),
            ),
            ("against", None, [(3, 1, D.RIGHT)], [D.RIGHT], set(), (1, 1)),
        ]
        for (
            case_name,
            expected_forge_set,
            expected_list,
            click_rel_direct_list,
            dig_pos_set,
            furnace_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_forge_set=expected_forge_set,
                expected=expected_list,
                click_rel_direct_list=click_rel_direct_list,
                dig_pos_set=dig_pos_set,
                furnace_pos=furnace_pos,
            ):
                self.reset()
                self.core.field.furnace = Furnace(furnace_pos)
                self.core.field.dig_pos_set = dig_pos_set
                bef_pos = (2, 1)
                for i, click_rel_direct in enumerate(click_rel_direct_list):
                    click_pos = tuple(
                        p + GameCore.TILE_TILT for p in click_rel_direct.value
                    )
                    mouse_pos = tuple(p * 8 - t for p, t in zip(click_pos, Cursor.TILT))
                    self.test_input.set_mouse_pos(*mouse_pos)
                    self.test_input.set_is_click(True)
                    for _ in range(2):
                        self.core.update()
                    expected_pos = expected_list[i][:2]
                    if expected_pos != bef_pos:
                        for _ in range(8):
                            self.core.update()
                    self.assertEqual(expected_pos, self.core.player.get_pos(None))
                    bef_pos = expected_pos
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", dig_pos_set],
                        ["furnace", furnace_pos],
                        ["clip end"],
                        ["position"],
                        ["player", expected_list[-1][2], D.NUTRAL],
                        ["bag", {}, None, None, None],
                    ],
                    bef_pos,
                )
                if expected_forge_set is not None:
                    self.put_draw_result([["forge", expected_forge_set]], bef_pos)
                self.check()

    def test_forge_with_moving(self):
        D = Direct
        test_cases = [
            ("walk to against", D.LEFT, (-1, 0), set()),
            ("walk to down", D.DOWN, (0, 1), {(2, 2)}),
        ]
        for (
            case_name,
            expected_direct,
            click_rel_pos,
            dig_pos_set,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                click_rel_pos=click_rel_pos,
                dig_pos_set=dig_pos_set,
            ):
                self.reset()
                self.core.field.furnace = Furnace((3, 1))
                self.core.field.dig_pos_set = dig_pos_set
                click_pos = tuple(p + GameCore.TILE_TILT for p in click_rel_pos)
                mouse_pos = tuple(p * 8 - t for p, t in zip(click_pos, Cursor.TILT))
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                for _ in range(3):
                    self.core.update()
                self.core.draw()
                face = D.LEFT if expected_direct == D.LEFT else D.RIGHT
                expected_pos = tuple(
                    p + d for p, d in zip((2, 1), expected_direct.value)
                )
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", dig_pos_set],
                        ["furnace", (3, 1)],
                        ["clip end"],
                        ["position"],
                        ["player", face, expected_direct],
                        ["bag", {}, None, None, None],
                    ],
                    expected_pos,
                    move_dir=expected_direct,
                    move_len=1,
                )
                self.check()

    @staticmethod
    def _get_mouse_pos(d):
        return tuple(
            p * 8 - t
            for p, t in zip(
                tuple(p + GameCore.TILE_TILT for p in d.value),
                Cursor.TILT,
            )
        )

    def _get_smith_scenario_params(
        self,
        bag_pos,
        forge_pos,
        have_items,
        smith_items,
        is_clear,
        after_items,
        is_set_forge,
    ):
        return (
            [
                (  # かまどの横に移動
                    self._get_mouse_pos(Direct.LEFT),
                    None,
                    set(),
                    None,
                    Direct.LEFT,
                    have_items,
                )
            ]
            + [
                elm
                for i in range(len(bag_pos))
                for elm in [
                    (  # 鞄を選択
                        tuple((p + t) * 8 for p, t in zip(Bag.TILE_POS, bag_pos[i])),
                        Bag.ITEM_POS_MAP[bag_pos[i][1]][bag_pos[i][0]],
                        set(
                            Bag.ITEM_POS_MAP[bag_pos[j][1]][bag_pos[j][0]]
                            for j in range(i)
                        ),
                        None,
                        Direct.LEFT,
                        have_items,
                    ),
                    (  # かまどを選択
                        tuple(
                            (p + t) * 8 for p, t in zip(Forge.TILE_POS, forge_pos[i])
                        ),
                        None,
                        (
                            (
                                set(
                                    Bag.ITEM_POS_MAP[bag_pos[j][1]][bag_pos[j][0]]
                                    for j in range(i + 1)
                                )
                                | (
                                    set()
                                    if i < len(forge_pos) - 1
                                    else set(smith_items)
                                )
                            )
                            if is_set_forge
                            else set()
                        ),
                        None,
                        Direct.LEFT,
                        have_items,
                    ),
                ]
            ]
            + [
                (  # 鍛冶(次できなければ、いったん全部解除)
                    tuple(
                        (p + t) * 8
                        for p, t in zip(Forge.TILE_POS, Forge.Tags.SMITH.value)
                    ),
                    None,
                    (
                        (
                            (
                                set(
                                    Bag.ITEM_POS_MAP[bag_pos[i][1]][bag_pos[i][0]]
                                    for i in range(len(bag_pos))
                                )
                                | set(smith_items)
                            )
                            if not is_clear
                            else set()
                        )
                        if is_set_forge
                        else set()
                    ),
                    None,
                    Direct.LEFT,
                    after_items,
                ),
                (  # かまどから遠ざかって移動
                    self._get_mouse_pos(Direct.RIGHT),
                    None,
                    None,
                    (3, 1),
                    Direct.RIGHT,
                    after_items,
                ),
                (  # かまどの横にまた移動
                    self._get_mouse_pos(Direct.LEFT),
                    None,
                    set(),
                    (2, 1),
                    Direct.LEFT,
                    after_items,
                ),
            ]
        )

    def test_smith(self):
        test_cases = [
            (
                "metal 1",
                {Pickaxe.METAL_1: 1},
                [Pickaxe.METAL_1],
                {Item.METAL_1: 1, Item.COAL: 1},
                [(0, 0), (5, 0)],
                [(0, 0), (1, 2)],
                True,
                True,
            ),
            (
                "metal 1 rest material",
                {Pickaxe.METAL_1: 1, Item.METAL_1: 1, Item.COAL: 1},
                [Pickaxe.METAL_1],
                {Item.METAL_1: 2, Item.COAL: 2},
                [(0, 0), (5, 0)],
                [(0, 0), (1, 2)],
                False,
                True,
            ),
            (
                "bag full fail",
                {Pickaxe.METAL_1: 9, Item.METAL_1: 1, Item.COAL: 1},
                [Pickaxe.METAL_1],
                {Pickaxe.METAL_1: 9, Item.METAL_1: 1, Item.COAL: 1},
                [(0, 0), (5, 0)],
                [(0, 0), (1, 2)],
                False,
                True,
            ),
            ("none", {}, [], {}, [], [], False, False),
            (
                "metal 1 set fail",
                {Item.METAL_1: 1, Item.COAL: 1},
                [],
                {Item.METAL_1: 1, Item.COAL: 1},
                [(5, 0)],
                [(0, 0)],
                False,
                False,
            ),
        ]
        for (
            case_name,
            expected_items,
            smith_items,
            have_items,
            bag_pos,
            forge_pos,
            is_clear,
            is_set_forge,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_items=expected_items,
                smith_items=smith_items,
                have_items=have_items,
                bag_pos=bag_pos,
                forge_pos=forge_pos,
                is_clear=is_clear,
                is_set_forge=is_set_forge,
            ):
                self.reset()
                self.core.bag.item_map = have_items
                self.core.avail_item_map = have_items.copy()
                self.core.field.furnace = Furnace((1, 1))
                bef_pos = (2, 1)
                expected_avail_item_map = {}
                for (
                    mouse_pos,
                    bag_selected,
                    forge_items,
                    move_to,
                    face,
                    bag_items,
                ) in self._get_smith_scenario_params(
                    bag_pos,
                    forge_pos,
                    have_items,
                    smith_items,
                    is_clear,
                    expected_items,
                    is_set_forge,
                ) + [
                    (  # かまどから遠ざかって移動
                        self._get_mouse_pos(Direct.RIGHT),
                        None,
                        None,
                        (3, 1),
                        Direct.RIGHT,
                        expected_items,
                    ),
                    (  # かまどの横にまた移動
                        self._get_mouse_pos(Direct.LEFT),
                        None,
                        set(),
                        (2, 1),
                        Direct.LEFT,
                        expected_items,
                    ),
                ]:
                    self.test_input.set_mouse_pos(*mouse_pos)
                    self.test_input.set_is_click(True)
                    for _ in range(2):
                        self.core.update()
                    if move_to is not None:
                        for _ in range(8):
                            self.core.update()
                    self.core.draw()

                    bef_pos = bef_pos if move_to is None else move_to
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["clip start"],
                            ["field", set()],
                            ["furnace", (1, 1)],
                            ["clip end"],
                            ["position"],
                            ["player", face, Direct.NUTRAL],
                            ["bag", bag_items, bag_selected, None, None],
                        ],
                        bef_pos,
                    )
                    if forge_items is not None:
                        self.put_draw_result([["forge", forge_items]], bef_pos)
                    expected_avail_item_map = {
                        k: 0 for k in expected_avail_item_map
                    } | bag_items
                    self.assertEqual(self.core.avail_item_map, expected_avail_item_map)
                self.check()

    def test_equip(self):
        self.core.bag.item_map = {Item.METAL_1: 1, Item.COAL: 1}
        self.core.field.furnace = Furnace((1, 1))

        bef_pos = (2, 1)
        for (
            mouse_pos,
            bag_selected,
            forge_items,
            move_to,
            face,
            bag_items,
            equip_item,
        ) in [
            (*p, None)
            for p in self._get_smith_scenario_params(
                [(0, 0), (5, 0)],
                [(0, 0), (1, 2)],
                {Item.METAL_1: 1, Item.COAL: 1},
                [Pickaxe.METAL_1],
                True,
                {Pickaxe.METAL_1: 1},
                True,
            )
        ] + [
            (  # 鞄を選択
                tuple((p + t) * 8 for p, t in zip(Bag.TILE_POS, (0, 1))),
                Bag.ITEM_POS_MAP[1][0],
                set(),
                None,
                Direct.LEFT,
                {Pickaxe.METAL_1: 1},
                None,
            ),
            (  # 装備
                tuple(p * 8 for p in Bag.EQUIP_TILE_POS),
                None,
                set(),
                None,
                Direct.LEFT,
                {Pickaxe.METAL_1: 1},
                Pickaxe.METAL_1,
            ),
            (  # 装備を外す
                tuple(p * 8 for p in Bag.EQUIP_TILE_POS),
                None,
                set(),
                None,
                Direct.LEFT,
                {Pickaxe.METAL_1: 1},
                None,
            ),
        ]:
            self.test_input.set_mouse_pos(*mouse_pos)
            self.test_input.set_is_click(True)
            for _ in range(2):
                self.core.update()
            if move_to is not None:
                for _ in range(8):
                    self.core.update()
            self.core.draw()

            bef_pos = bef_pos if move_to is None else move_to
            weight = (
                Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                if equip_item is not None
                else 1.0
            )
            expected_strength = int(Bag.MAX_STRENGTH * weight)
            self.put_draw_result(
                [
                    ["clear"],
                    ["clip start"],
                    ["field", set()],
                    ["furnace", (1, 1)],
                    ["clip end"],
                    ["position"],
                    ["player", face, Direct.NUTRAL],
                    ["bag", bag_items, bag_selected, equip_item, expected_strength],
                ],
                bef_pos,
            )
            if forge_items is not None:
                self.put_draw_result([["forge", forge_items]], bef_pos)

        self.check()

    def test_game_over(self):
        self.patcher_gamecore_is_game_over.stop()
        test_cases = [
            ("game over", ["Game Over", "Click here"], {}),
            (
                "game clear",
                ["Game Clear", "Click here"],
                {Item.JEWEL: GameCore.TARGET_NUM},
            ),
        ]
        for case_name, message_list, items in test_cases:
            with self.subTest(
                case_name=case_name,
                message_list=message_list,
                items=items,
            ):
                self.reset()
                self.core.bag.item_map = items
                self.core.avail_item_map = items
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["clip start"],
                        ["field", {}],
                        ["clip end"],
                        ["position"],
                        ["player", Direct.RIGHT, Direct.NUTRAL],
                        ["bag", items, None, None, None],
                        ["console", message_list],
                    ],
                    (2, 1),
                )
                self.assertEqual(False, self.core.is_reset())
                self.test_input.set_is_click(True)
                mouse_pos = tuple(p * 8 for p in Console.TILE_POS)
                self.test_input.set_mouse_pos(*mouse_pos)
                self.core.update()
                self.assertEqual(True, self.core.is_reset())
                self.check()

    def test_game_over_move(self):
        self.patcher_gamecore_is_game_over.stop()
        self.core.field.dig_pos_set = {(3, 2)}
        self.core.avail_item_map = {}
        click_pos = tuple(p + GameCore.TILE_TILT for p in (1, 0))
        mouse_pos = tuple(p * 8 - t for p, t in zip(click_pos, Cursor.TILT))
        self.test_input.set_mouse_pos(*mouse_pos)
        self.test_input.set_is_click(True)
        self.core._set_avail_item({Pickaxe.METAL_1}, 1)  # pylint: disable=W0212
        move_to_pos = (3, 1)
        for _ in range(2):
            self.core.update()
        for _ in range(8):
            self.core.update()
        self.assertEqual(move_to_pos, self.core.player.get_pos(None))
        self.core._set_avail_item({Pickaxe.METAL_1}, -1)  # pylint: disable=W0212
        self.test_input.set_is_click(False)
        self.core.update()
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["clip start"],
                ["field", {(3, 2)}],
                ["clip end"],
                ["position"],
                ["player", Direct.RIGHT, Direct.NUTRAL],
                ["bag", {}, None, None, None],
                ["console", ["Game Over", "Click here"]],
            ],
            move_to_pos,
        )
        self.check()


if __name__ == "__main__":
    unittest.main()
