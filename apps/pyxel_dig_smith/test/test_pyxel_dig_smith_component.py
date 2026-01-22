import os
import sys
import unittest

for p in ["../src/", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from test_pyxel_dig_smith_tools import (  # pylint: disable=C0413
    TestParent,
    TestUnitParent,
)
from main import (  # pylint: disable=C0413
    GameCore,
    Player,
    Direct,
    Color,
    Ore,
    Bag,
    Cursor,
    Unit,
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


class TestUnit(TestParent):
    def test_draw(self):
        d = Direct
        test_cases = [
            ("no move", [[1, 1], [3, 3]], False, [(d.NUTRAL, False)] * 2),
            ("right walk", [[1, 2], [1, 4]], False, [(d.RIGHT, False)] * 2),
            ("left walk", [[1, 2], [1, 4]], True, [(d.LEFT, False)] * 2),
            ("up walk", [[1, 2], [1, 4]], False, [(d.UP, False)] * 2),
            ("down walk", [[1, 2], [1, 4]], False, [(d.DOWN, False)] * 2),
            (
                "right up walk",
                [[1, 2], [1, 4]] * 2,
                False,
                [(d.RIGHT, False)] * 2 + [(d.UP, False)] * 2,
            ),
            (
                "left down walk",
                [[1, 2], [1, 4]] * 2,
                True,
                [(d.LEFT, False)] * 2 + [(d.DOWN, False)] * 2,
            ),
            (
                "turn left",
                [[1, 1], [3, 3]] * 2,
                True,
                [(d.LEFT, True)] * 2 + [(d.NUTRAL, False)] * 2,
            ),
            ("no move blocked", [[1, 1], [3, 3]] * 2, False, [(d.NUTRAL, True)] * 2),
            ("right walk blocked", [[1, 1], [3, 3]] * 2, False, [(d.RIGHT, True)] * 2),
            ("left walk blocked", [[1, 1], [3, 3]] * 2, True, [(d.LEFT, True)] * 2),
            ("up walk blocked", [[1, 1], [3, 3]] * 2, False, [(d.UP, True)] * 2),
            ("down walk blocked", [[1, 1], [3, 3]] * 2, False, [(d.DOWN, True)] * 2),
            (
                "left blocked down walk",
                [[1, 1], [3, 3], [1, 2], [1, 4]],
                True,
                [(d.LEFT, True)] * 2 + [(d.DOWN, False)] * 2,
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
                unit = Unit(0, 0, 1, 0)
                expected = []
                axis_pos = (0, 0)
                for i, (direct, is_blocked) in enumerate(move_direct):
                    next_pos = (
                        tuple(p + d for p, d in zip(axis_pos, direct.value))
                        if not is_blocked
                        else axis_pos
                    )
                    unit.move(next_pos, direct, is_blocked)
                    pos = (0, 0)
                    for j in range(2):
                        image_x = expected_pattern[i][j]
                        unit.draw()
                        expected.append(
                            (
                                "draw_image",
                                *axis_pos,
                                image_x,
                                0,
                                False,
                                pos,
                                expected_rev,
                            )
                        )
                        for _ in range(4):
                            unit.update()
                            self.test_view.increment_frame()
                            if not is_blocked:
                                pos = tuple(p + d for p, d in zip(pos, direct.value))
                    axis_pos = next_pos
                unit.draw()
                expected.append(
                    (
                        "draw_image",
                        *axis_pos,
                        expected_pattern[0][0],
                        0,
                        False,
                        (0, 0),
                        expected_rev,
                    )
                )
                self.assertEqual(
                    self.test_view.get_call_params(),
                    expected,
                    self.test_view.get_call_params(),
                )


class TestOre(TestParent):
    def test_draw(self):
        test_cases = [
            ("base axis", (2, 2), (2, 2)),
            ("base axis slide", (2, 2), (2, 3)),
            ("x - 1 axis", (1, 2), (2, 2)),
            ("y - 1 axis", (2, 1), (2, 2)),
            ("x + 1 axis", (3, 2), (2, 2)),
            ("y + 1 axis", (2, 3), (2, 2)),
        ]
        for case_name, center_pos, abs_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                center_pos=center_pos,
                abs_pos=abs_pos,
            ):
                self.reset()
                ore = Ore(abs_pos, Item.METAL_1)
                ore.draw_abs(center_pos)
                expected = [
                    ("draw_image", *abs_pos, *Item.METAL_1.value, False, (0, 0), False)
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestFurnace(TestParent):
    def test_draw(self):
        chest = Furnace((4, 1))
        chest.draw_abs((2, 1))
        expected = [("draw_image", 4, 1, 2, 6, False, (0, 0), False)]
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )


class TestBag(TestParent):
    def test_draw(self):
        test_cases = [
            ("1 metal", {Item.METAL_1: 1}, [Item.METAL_1], None, 0),
            ("2 metal", {Item.METAL_1: 2}, [Item.METAL_1] * 2, None, 0),
            (
                "10 metal",
                {Item.METAL_1: Bag.MAX_NUM},
                [Item.METAL_1] * (Bag.MAX_NUM + 1),
                None,
                0,
            ),
            ("metal_2", {Item.METAL_2: 1}, [Item.METAL_2], None, 0),
            ("metal_3", {Item.METAL_3: 2}, [Item.METAL_3] * 2, None, 0),
            ("metal_4", {Item.METAL_4: 3}, [Item.METAL_4] * 3, None, 0),
            ("metal_5", {Item.METAL_5: 4}, [Item.METAL_5] * 4, None, 0),
            ("coal", {Item.COAL: 5}, [Item.COAL] * 5, None, 0),
            ("jewel", {Item.JEWEL: 6}, [Item.JEWEL] * 6, None, 0),
            (
                "metal 1, metal 2",
                {Item.METAL_1: 1, Item.METAL_2: 1},
                [Item.METAL_2, Item.METAL_1],
                None,
                0,
            ),
            ("equip", {Pickaxe.METAL_1: 1}, [Pickaxe.METAL_1], Pickaxe.METAL_1, 0),
            ("equip chip", {Pickaxe.METAL_1: 1}, [Pickaxe.METAL_1], Pickaxe.METAL_1, 5),
            ("equip jewel", {Pickaxe.JEWEL: 1}, [Pickaxe.JEWEL], Pickaxe.JEWEL, 0),
            ("equip jewel chip", {Pickaxe.JEWEL: 1}, [Pickaxe.JEWEL], Pickaxe.JEWEL, 5),
        ]
        for case_name, expected_map, push_items, equip_item, chip_count in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_map=expected_map,
                push_items=push_items,
                equip_item=equip_item,
            ):
                self.reset()
                bag = Bag((2, 2))
                for item in push_items:
                    bag.push(item)
                bag.equip(Bag.EQUIP_TILE_POS, equip_item)
                for _i in range(chip_count):
                    bag.chip_equipment()
                bag.draw()
                expected_pos = tuple(
                    ct - GameCore.TILE_TILT + p for ct, p in zip((2, 2), Bag.TILE_POS)
                )
                expected = []

                # 鞄
                expected.extend(
                    [
                        (
                            "draw_rect",
                            expected_pos[0] * 8 - 1,
                            expected_pos[1] * 8 - 1,
                            8 * len(Bag.ITEM_POS_MAP[0]) + 2,
                            8 * len(Bag.ITEM_POS_MAP) + 2,
                            Color.WHITE,
                            False,
                        )
                    ]
                )
                for y, item_list in enumerate(Bag.ITEM_POS_MAP):
                    for x, item in enumerate(item_list):
                        color = Color.DARK_BLUE if (x + y) % 2 == 1 else Color.BLACK
                        expected.append(
                            (
                                "draw_rect",
                                (expected_pos[0] + x) * 8,
                                (expected_pos[1] + y) * 8,
                                8,
                                8,
                                color,
                                True,
                            )
                        )
                        if item in expected_map:
                            expected.append(
                                (
                                    "draw_image",
                                    expected_pos[0] + x,
                                    expected_pos[1] + y,
                                    *item.value,
                                    False,
                                    (0, 0),
                                    False,
                                )
                            )
                            expected.append(
                                (
                                    "draw_text",
                                    *tuple(
                                        (p + t) * 8 + o
                                        for p, t, o in zip(
                                            expected_pos,
                                            (x, y),
                                            Bag.NUM_OFFSET,
                                        )
                                    ),
                                    str(expected_map[item]),
                                    Color.WHITE,
                                )
                            )

                # 装備と宝石
                expected_pos = tuple(
                    ct - GameCore.TILE_TILT + p
                    for ct, p in zip((2, 2), Bag.EQUIP_TILE_POS)
                )
                expected.extend(
                    [
                        (
                            "draw_rect",
                            expected_pos[0] * 8 - 1,
                            expected_pos[1] * 8 - 1,
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
                        expected.append(
                            (
                                "draw_rect",
                                (expected_pos[0] + x) * 8,
                                (expected_pos[1] + y) * 8,
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
                            expected.append(
                                (
                                    "draw_image",
                                    expected_pos[0] + x,
                                    expected_pos[1] + y,
                                    *params[0],
                                    params[1],
                                    (0, 0),
                                    False,
                                )
                            )
                        if (x, y) == (1, 0) and equip_item is not None:
                            current_max_strength = int(
                                Bag.MAX_STRENGTH
                                * Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                            )
                            expected_strength = current_max_strength - chip_count
                            expected_draw_num = (
                                expected_strength * 9
                            ) // current_max_strength
                            expected.append(
                                (
                                    "draw_rect",
                                    (expected_pos[0] + x) * 8,
                                    (expected_pos[1] + y) * 8,
                                    1 + int(5 * expected_strength / current_max_strength),
                                    8,
                                    Color.YELLOW,
                                    True,
                                )
                            )
                            expected.append(
                                (
                                    "draw_image",
                                    expected_pos[0] + x,
                                    expected_pos[1] + y,
                                    *Icon.STRENGTH.value,
                                    False,
                                    (0, 0),
                                    False,
                                )
                            )
                            expected.append(
                                (
                                    "draw_text",
                                    *tuple(
                                        (p + t) * 8 + o
                                        for p, t, o in zip(
                                            expected_pos,
                                            (x, y),
                                            Bag.NUM_OFFSET,
                                        )
                                    ),
                                    str(expected_draw_num),
                                    Color.WHITE,
                                )
                            )
                        if (x, y) == (0, 1):
                            expected.append(
                                (
                                    "draw_image",
                                    expected_pos[0] + x,
                                    expected_pos[1] + y,
                                    *Item.JEWEL.value,
                                    False,
                                    (0, 0),
                                    False,
                                )
                            )
                            expected.append(
                                (
                                    "draw_text",
                                    *tuple(
                                        (p + t) * 8 + o
                                        for p, t, o in zip(
                                            expected_pos,
                                            (x, y),
                                            Bag.NUM_OFFSET,
                                        )
                                    ),
                                    str(expected_map.get(Item.JEWEL, 0)),
                                    Color.WHITE,
                                )
                            )
                        if (x, y) == (1, 1):
                            expected.append(
                                (
                                    "draw_text",
                                    *tuple(
                                        (p + t) * 8 + o + to
                                        for p, t, o, to in zip(
                                            expected_pos,
                                            (x, y),
                                            Bag.NUM_OFFSET,
                                            (-4, 0),
                                        )
                                    ),
                                    "/3",
                                    Color.WHITE,
                                )
                            )

                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_equip(self):
        test_cases = [
            ("success", True, Pickaxe.METAL_1, [Pickaxe.METAL_1], Bag.EQUIP_TILE_POS),
            ("not have", False, Pickaxe.METAL_1, [], Bag.EQUIP_TILE_POS),
            ("cant", False, Item.METAL_1, [Item.METAL_1], Bag.EQUIP_TILE_POS),
            ("out pos", False, Pickaxe.METAL_1, [Pickaxe.METAL_1], (0, 0)),
        ]
        for case_name, expected, equip_item, push_times, pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                equip_item=equip_item,
                push_times=push_times,
            ):
                self.reset()
                bag = Bag((2, 2))
                for item in push_times:
                    bag.push(item)
                bag.equip(pos, equip_item)
                expected_equip = equip_item if expected else None
                self.assertEqual(expected_equip, bag.get_equiped())

    def test_equip_get_off(self):
        bag = Bag((2, 2))
        bag.push(Pickaxe.METAL_1)
        bag.equip(Bag.EQUIP_TILE_POS, Pickaxe.METAL_1)
        self.assertEqual(Pickaxe.METAL_1, bag.get_equiped())
        bag.equip(Bag.EQUIP_TILE_POS, None)
        self.assertEqual(None, bag.get_equiped())

    def test_push(self):
        test_cases = [
            ("1 time", False, 1, 1),
            ("8 time", False, Bag.MAX_NUM - 1, Bag.MAX_NUM - 1),
            ("9 time", True, Bag.MAX_NUM, Bag.MAX_NUM),
            ("10 time", True, Bag.MAX_NUM, Bag.MAX_NUM + 1),
        ]
        for case_name, expected, expected_count, push_times in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                expected_count=expected_count,
                push_times=push_times,
            ):
                self.reset()
                bag = Bag((2, 2))
                for _ in range(push_times):
                    bag.push(Item.METAL_1)
                self.assertEqual(expected_count, bag.item_map[Item.METAL_1])
                self.assertEqual(expected, bag.is_full(Item.METAL_1))
                self.assertEqual(False, bag.is_full(Item.METAL_2))

    def test_pull(self):
        I = Item
        test_cases = [
            ("all one pull", True, {}, None, {I.METAL_1}, {I.METAL_1: 1}, False, None),
            (
                "partial one pull",
                True,
                {I.METAL_2: 1},
                None,
                {I.METAL_1},
                {I.METAL_1: 1, I.METAL_2: 1},
                False,
                None,
            ),
            (
                "degreese one",
                True,
                {I.METAL_1: 1},
                None,
                {I.METAL_1},
                {I.METAL_1: 2},
                False,
                None,
            ),
            (
                "all two pull",
                True,
                {},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 1, I.METAL_2: 1},
                False,
                None,
            ),
            (
                "partial two pull",
                True,
                {I.METAL_3: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 1, I.METAL_2: 1, I.METAL_3: 1},
                False,
                None,
            ),
            (
                "degreese two",
                True,
                {I.METAL_1: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 2, I.METAL_2: 1},
                False,
                None,
            ),
            (
                "all pikeaxe pull",
                True,
                {},
                None,
                {Pickaxe.METAL_1},
                {Pickaxe.METAL_1: 1},
                False,
                None,
            ),
            (
                "partial pikeaxe pull",
                True,
                {Pickaxe.METAL_1: 1},
                None,
                {Pickaxe.METAL_1},
                {Pickaxe.METAL_1: 2},
                False,
                None,
            ),
            (
                "fail all two pull",
                False,
                {I.METAL_1: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 1},
                False,
                None,
            ),
            (
                "fail partial two pull",
                False,
                {I.METAL_3: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_3: 1},
                False,
                None,
            ),
            (
                "fail degreese two",
                False,
                {I.METAL_1: 2},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 2},
                False,
                None,
            ),
            (
                "all two pull with dryrun",
                True,
                {I.METAL_1: 1, I.METAL_2: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 1, I.METAL_2: 1},
                True,
                None,
            ),
            (
                "fail all two pull with dryrun",
                False,
                {I.METAL_1: 1},
                None,
                {I.METAL_1, I.METAL_2},
                {I.METAL_1: 1},
                True,
                None,
            ),
            (
                "equiped item pull",
                True,
                {Pickaxe.METAL_1: 1},
                Pickaxe.METAL_1,
                {Pickaxe.METAL_1},
                {Pickaxe.METAL_1: 2},
                False,
                Pickaxe.METAL_1,
            ),
            (
                "equiped item pull and empty",
                True,
                {},
                None,
                {Pickaxe.METAL_1},
                {Pickaxe.METAL_1: 1},
                False,
                Pickaxe.METAL_1,
            ),
        ]
        for (
            case_name,
            expected_ret,
            expected_count_map,
            expected_equip_item,
            pull_items,
            push_times,
            is_dryrun,
            equip_item,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_equip_item=expected_equip_item,
                expected_ret=expected_ret,
                expected_count_map=expected_count_map,
                pull_items=pull_items,
                push_times=push_times,
                is_dryrun=is_dryrun,
                equip_item=equip_item,
            ):
                self.reset()
                bag = Bag((2, 2))
                for k, v in push_times.items():
                    for _ in range(v):
                        bag.push(k)
                bag.equip(Bag.EQUIP_TILE_POS, equip_item)
                self.assertEqual(
                    expected_ret, bag.pull(pull_items, is_dryrun=is_dryrun)
                )
                self.assertEqual(expected_count_map, bag.item_map)
                self.assertEqual(expected_equip_item, bag.get_equiped())

    def test_select(self):
        test_cases = [
            ("select metal 1", (Item.METAL_1, None), (Bag.TILE_POS, (0, 0)), None),
            (
                "select pickaxe 1",
                (Pickaxe.METAL_1, None),
                ((Bag.TILE_POS[0], Bag.TILE_POS[1] + 1), (0, 0)),
                None,
            ),
            ("select field", (None, None), (Bag.FIELD_TILE_RECT[:2], (0, 0)), None),
            (
                "select equiped",
                (Pickaxe.METAL_1, None),
                ((Bag.TILE_POS[0], Bag.TILE_POS[1] + 1), (0, 0)),
                Pickaxe.METAL_1,
            ),
            (
                "select jewel",
                (Item.JEWEL, None),
                ((Bag.EQUIP_TILE_POS[0], Bag.EQUIP_TILE_POS[1] + 1), (0, 0)),
                None,
            ),
        ]
        for case_name, expected_select, select_pos_list, equip_item in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_select=expected_select,
                select_pos_list=select_pos_list,
                equip_item=equip_item,
            ):
                self.reset()
                bag = Bag((2, 2))
                for item in list(Item) + list(Pickaxe):
                    bag.push(item)
                bag.equip(Bag.EQUIP_TILE_POS, equip_item)
                for select_pos, expected_item in zip(select_pos_list, expected_select):
                    bag.select_pos(*select_pos)
                    self.assertEqual(bag.get_selected(), expected_item)
                    bag.draw()
                expected_pos = tuple(
                    ct - GameCore.TILE_TILT + p for ct, p in zip((2, 2), Bag.TILE_POS)
                )
                expected_equip_pos = tuple(
                    ct - GameCore.TILE_TILT + p
                    for ct, p in zip((2, 2), Bag.EQUIP_TILE_POS)
                )
                expected = []
                for select_item in expected_select:
                    expected.extend(
                        [
                            (
                                "draw_rect",
                                expected_pos[0] * 8 - 1,
                                expected_pos[1] * 8 - 1,
                                8 * len(Bag.ITEM_POS_MAP[0]) + 2,
                                8 * len(Bag.ITEM_POS_MAP) + 2,
                                Color.WHITE,
                                False,
                            )
                        ]
                    )
                    for y, item_list in enumerate(Bag.ITEM_POS_MAP):
                        for x, item in enumerate(item_list):
                            color = Color.DARK_BLUE if (x + y) % 2 == 1 else Color.BLACK
                            expected.append(
                                (
                                    "draw_rect",
                                    (expected_pos[0] + x) * 8,
                                    (expected_pos[1] + y) * 8,
                                    8,
                                    8,
                                    color,
                                    True,
                                )
                            )
                            expected.append(
                                (
                                    "draw_image",
                                    expected_pos[0] + x,
                                    expected_pos[1] + y,
                                    *item.value,
                                    False,
                                    (0, 0),
                                    False,
                                )
                            )
                            expected.append(
                                (
                                    "draw_text",
                                    *tuple(
                                        (p + t) * 8 + o
                                        for p, t, o in zip(
                                            expected_pos,
                                            (x, y),
                                            Bag.NUM_OFFSET,
                                        )
                                    ),
                                    str(1),
                                    Color.WHITE,
                                )
                            )
                            if item == select_item:
                                expected.append(
                                    (
                                        "draw_rect",
                                        (expected_pos[0] + x) * 8,
                                        (expected_pos[1] + y) * 8,
                                        8,
                                        8,
                                        Color.YELLOW,
                                        False,
                                    )
                                )
                    expected.extend(
                        [
                            (
                                "draw_rect",
                                expected_equip_pos[0] * 8 - 1,
                                expected_equip_pos[1] * 8 - 1,
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
                            expected.append(
                                (
                                    "draw_rect",
                                    (expected_equip_pos[0] + x) * 8,
                                    (expected_equip_pos[1] + y) * 8,
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
                                expected.append(
                                    (
                                        "draw_image",
                                        expected_equip_pos[0] + x,
                                        expected_equip_pos[1] + y,
                                        *params[0],
                                        params[1],
                                        (0, 0),
                                        False,
                                    )
                                )
                            if (x, y) == (1, 0) and equip_item is not None:
                                current_max_strength = int(
                                    Bag.MAX_STRENGTH
                                    * Bag.MAX_STRENGTH_WEIGHT_MAP.get(
                                        equip_item, 1.0
                                    )
                                )
                                expected.append(
                                    (
                                        "draw_rect",
                                        (expected_equip_pos[0] + x) * 8,
                                        (expected_equip_pos[1] + y) * 8,
                                        1 + 5,
                                        8,
                                        Color.YELLOW,
                                        True,
                                    )
                                )
                                expected.append(
                                    (
                                        "draw_image",
                                        expected_equip_pos[0] + x,
                                        expected_equip_pos[1] + y,
                                        *Icon.STRENGTH.value,
                                        False,
                                        (0, 0),
                                        False,
                                    )
                                )
                                expected.append(
                                    (
                                        "draw_text",
                                        *tuple(
                                            (p + t) * 8 + o
                                            for p, t, o in zip(
                                                expected_equip_pos,
                                                (x, y),
                                                Bag.NUM_OFFSET,
                                            )
                                        ),
                                        str(
                                            (
                                                current_max_strength * 9
                                            ) // current_max_strength
                                        ),
                                        Color.WHITE,
                                    )
                                )
                            if (x, y) == (0, 1):
                                expected.append(
                                    (
                                        "draw_image",
                                        expected_equip_pos[0] + x,
                                        expected_equip_pos[1] + y,
                                        *Item.JEWEL.value,
                                        False,
                                        (0, 0),
                                        False,
                                    )
                                )
                                expected.append(
                                    (
                                        "draw_text",
                                        *tuple(
                                            (p + t) * 8 + o
                                            for p, t, o in zip(
                                                expected_equip_pos,
                                                (x, y),
                                                Bag.NUM_OFFSET,
                                            )
                                        ),
                                        str(1),
                                        Color.WHITE,
                                    )
                                )
                                if select_item == Item.JEWEL:
                                    expected.append(
                                        (
                                            "draw_rect",
                                            (expected_equip_pos[0] + x) * 8,
                                            (expected_equip_pos[1] + y) * 8,
                                            8,
                                            8,
                                            Color.YELLOW,
                                            False,
                                        )
                                    )
                            if (x, y) == (1, 1):
                                expected.append(
                                    (
                                        "draw_text",
                                        *tuple(
                                            (p + t) * 8 + o + to
                                            for p, t, o, to in zip(
                                                expected_equip_pos,
                                                (x, y),
                                                Bag.NUM_OFFSET,
                                                (-4, 0),
                                            )
                                        ),
                                        "/3",
                                        Color.WHITE,
                                    )
                                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_chip_equipment(self):
        test_cases = [
            ("break all", None, {}, Pickaxe.METAL_1, {Pickaxe.METAL_1: 1}, False),
            (
                "break one",
                None,
                {Pickaxe.METAL_1: 1},
                Pickaxe.METAL_1,
                {Pickaxe.METAL_1: 2},
                False,
            ),
            (
                "pull",
                Pickaxe.METAL_1,
                {Pickaxe.METAL_1: 1},
                Pickaxe.METAL_1,
                {Pickaxe.METAL_1: 2},
                True,
            ),
            (
                "two",
                None,
                {Pickaxe.METAL_2: 1},
                Pickaxe.METAL_1,
                {Pickaxe.METAL_1: 1, Pickaxe.METAL_2: 1},
                False,
            ),
        ]
        for (
            case_name,
            expected_equied,
            expected_item,
            equip_item,
            start_items,
            is_pull,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_equied=expected_equied,
                expected_item=expected_item,
                equip_item=equip_item,
                start_items=start_items,
                is_pull=is_pull,
            ):
                self.reset()
                bag = Bag((2, 2))
                for k, v in start_items.items():
                    for _ in range(v):
                        bag.push(k)
                self.assertEqual(start_items, bag.item_map)
                for item in start_items:
                    bag.equip(Bag.EQUIP_TILE_POS, item)
                    current_max_strength = int(
                        Bag.MAX_STRENGTH
                        * Bag.MAX_STRENGTH_WEIGHT_MAP.get(item, 1.0)
                    )
                    self.assertEqual(current_max_strength, bag.get_strength())
                    for i in range(current_max_strength - 1):
                        bag.chip_equipment()
                        self.assertEqual(item, bag.get_equiped())
                        self.assertEqual(
                            (current_max_strength - 1) - i, bag.get_strength()
                        )
                bag.equip(Bag.EQUIP_TILE_POS, equip_item)
                expected_strength = (
                    int(
                        Bag.MAX_STRENGTH
                        * Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                    )
                    if expected_equied is not None
                    else None
                )
                if is_pull:
                    bag.pull({equip_item})
                    expected_strength = int(
                        Bag.MAX_STRENGTH
                        * Bag.MAX_STRENGTH_WEIGHT_MAP.get(equip_item, 1.0)
                    ) - 1
                bag.chip_equipment()
                self.assertEqual(expected_strength, bag.get_strength())
                self.assertEqual(expected_equied, bag.get_equiped())
                self.assertEqual(expected_item, bag.item_map)


class TestForge(TestUnitParent):
    def test_draw(self):
        test_cases = [
            ("no push", set(), [], None),
            ("metal_1", {(0, 0)}, [((0, 0), Item.METAL_1)], Item.METAL_1),
            ("coal", {(1, 2)}, [((1, 2), Item.COAL)], None),
            ("coal wrong", {}, [((1, 2), Item.METAL_1)], None),
            ("cant push smith", {}, [((4, 0), Pickaxe.METAL_1)], None),
            (
                "metal_1 all push",
                {(0, 0), (4, 0), (1, 2)},
                [((0, 0), Item.METAL_1), ((1, 2), Item.COAL)],
                Item.METAL_1,
            ),
            ("metal_2", {(0, 0)}, [((0, 0), Item.METAL_2)], Item.METAL_2),
            (
                "metal_2 all push",
                {(0, 0), (4, 0), (1, 2), (2, 0)},
                [
                    ((0, 0), Item.METAL_2),
                    ((1, 2), Item.COAL),
                    ((2, 0), Pickaxe.METAL_1),
                ],
                Item.METAL_2,
            ),
            (
                "metal 2 with coal first",
                {(0, 0), (4, 0), (1, 2), (2, 0)},
                [
                    ((1, 2), Item.COAL),
                    ((0, 0), Item.METAL_2),
                    ((2, 0), Pickaxe.METAL_1),
                ],
                Item.METAL_2,
            ),
            (
                "recipe change",
                {(0, 0), (4, 0), (1, 2), (2, 0)},
                [
                    ((0, 0), Item.METAL_1),
                    ((1, 2), Item.COAL),
                    ((2, 0), Pickaxe.METAL_1),
                    ((0, 0), Item.METAL_2),
                    ((1, 2), Item.COAL),
                    ((2, 0), Pickaxe.METAL_1),
                ],
                Item.METAL_2,
            ),
            (
                "recipe change with coal",
                {(0, 0), (4, 0), (1, 2), (2, 0)},
                [
                    ((0, 0), Item.METAL_3),
                    ((1, 2), Item.COAL),
                    ((0, 0), Item.METAL_2),
                    ((2, 0), Pickaxe.METAL_1),
                ],
                Item.METAL_2,
            ),
        ]
        for case_name, expected_pos_set, push_list, recipe_key in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos_set=expected_pos_set,
                push_list=push_list,
                recipe_key=recipe_key,
            ):
                self.reset()
                forge = Forge((2, 2))
                for pos, item in push_list:
                    abs_pos = tuple(p + t for p, t in zip(pos, Forge.TILE_POS))
                    forge.push(abs_pos, item)
                forge.draw()
                expected_pos = tuple(
                    ct - GameCore.TILE_TILT + p for ct, p in zip((2, 2), Forge.TILE_POS)
                )
                box_map = Forge._get_box_item(recipe_key)  # pylint: disable=W0212
                expected = []
                expected_unit = []
                for x, y in ((0, 0), (2, 0), (4, 0), (1, 2)):
                    frame_pos = tuple(p + e for p, e in zip((x, y), expected_pos))
                    expected.extend(
                        [
                            (
                                "draw_rect",
                                frame_pos[0] * 8 - 1,
                                frame_pos[1] * 8 - 1,
                                10,
                                10,
                                Color.WHITE,
                                False,
                            )
                        ]
                    )
                    expected.append(
                        (
                            "draw_rect",
                            frame_pos[0] * 8,
                            frame_pos[1] * 8,
                            8,
                            8,
                            Color.BLACK,
                            True,
                        )
                    )
                    params = None
                    if (x, y) in expected_pos_set:
                        params = (box_map[(x, y)].value, False)
                    elif (x, y) in Forge.SHADOW_MAP:
                        shadow = Forge.SHADOW_MAP[(x, y)]
                        box_item = box_map.get((x, y))
                        if shadow is not None:
                            params = (Forge.SHADOW_MAP[(x, y)].value, True)
                        elif box_item is not None:
                            params = (box_item.value, True)
                    if params is not None:
                        expected.append(
                            (
                                "draw_image",
                                frame_pos[0],
                                frame_pos[1],
                                *params[0],
                                params[1],
                                (0, 0),
                                False,
                            )
                        )
                        if (x, y) == (1, 2) and (x, y) in expected_pos_set:
                            expected_unit = [
                                (
                                    "draw_unit",
                                    frame_pos[0],
                                    frame_pos[1] - 1,
                                    1,
                                    1,
                                    Direct.RIGHT,
                                    Direct.RIGHT,
                                    (0, 0),
                                )
                            ]
                for x, y, text in ((1, 0, "+"), (3, 0, "=")):
                    frame_pos = tuple(p + e for p, e in zip((x, y), expected_pos))
                    expected.extend(
                        [
                            (
                                "draw_text",
                                frame_pos[0] * 8 + 2,
                                frame_pos[1] * 8 + 1,
                                text,
                                Color.WHITE,
                            )
                        ]
                    )
                self.assertEqual(
                    self.test_view.get_call_params(),
                    expected,
                    self.test_view.get_call_params(),
                )
                self.assertEqual(
                    self.test_unit_view.get_call_params(),
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                )

    def test_clear(self):
        test_cases = [
            (
                "metal 1",
                Item.METAL_1,
                {(0, 0), (1, 2), (4, 0)},
                {(0, 0): Item.METAL_1, (1, 2): Item.COAL},
            ),
            (
                "metal 2",
                Item.METAL_2,
                {(0, 0), (1, 2), (4, 0), (2, 0)},
                {(0, 0): Item.METAL_2, (1, 2): Item.COAL, (2, 0): Pickaxe.METAL_1},
            ),
        ]
        for case_name, expected_box_base, expected_pos_set, forge_items in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_box_base=expected_box_base,
                expected_pos_set=expected_pos_set,
                forge_items=forge_items,
            ):
                self.reset()
                forge = Forge((2, 2))
                for pos, item in forge_items.items():
                    abs_pos = tuple(p + t for p, t in zip(pos, Forge.TILE_POS))
                    forge.push(abs_pos, item)
                forge.draw()
                forge.clear()
                forge.draw()
                expected_pos = tuple(
                    ct - GameCore.TILE_TILT + p for ct, p in zip((2, 2), Forge.TILE_POS)
                )
                expected = []
                expected_unit = []
                for box_base, pos_set in (
                    (expected_box_base, expected_pos_set),
                    (None, set()),
                ):
                    box_map = Forge._get_box_item(box_base)  # pylint: disable=W0212
                    for x, y in ((0, 0), (2, 0), (4, 0), (1, 2)):
                        frame_pos = tuple(p + e for p, e in zip((x, y), expected_pos))
                        expected.extend(
                            [
                                (
                                    "draw_rect",
                                    frame_pos[0] * 8 - 1,
                                    frame_pos[1] * 8 - 1,
                                    10,
                                    10,
                                    Color.WHITE,
                                    False,
                                )
                            ]
                        )
                        expected.append(
                            (
                                "draw_rect",
                                frame_pos[0] * 8,
                                frame_pos[1] * 8,
                                8,
                                8,
                                Color.BLACK,
                                True,
                            )
                        )
                        params = None
                        if (x, y) in pos_set:
                            params = (box_map[(x, y)].value, False)
                        elif (x, y) in Forge.SHADOW_MAP:
                            shadow = Forge.SHADOW_MAP[(x, y)]
                            box_item = box_map.get((x, y))
                            if shadow is not None:
                                params = (Forge.SHADOW_MAP[(x, y)].value, True)
                            elif box_item is not None:
                                params = (box_item.value, True)
                        if params is not None:
                            expected.append(
                                (
                                    "draw_image",
                                    frame_pos[0],
                                    frame_pos[1],
                                    *params[0],
                                    params[1],
                                    (0, 0),
                                    False,
                                )
                            )
                            if (x, y) == (1, 2) and (x, y) in pos_set:
                                expected_unit = [
                                    (
                                        "draw_unit",
                                        frame_pos[0],
                                        frame_pos[1] - 1,
                                        1,
                                        1,
                                        Direct.RIGHT,
                                        Direct.RIGHT,
                                        (0, 0),
                                    )
                                ]
                    for x, y, text in ((1, 0, "+"), (3, 0, "=")):
                        frame_pos = tuple(p + e for p, e in zip((x, y), expected_pos))
                        expected.extend(
                            [
                                (
                                    "draw_text",
                                    frame_pos[0] * 8 + 2,
                                    frame_pos[1] * 8 + 1,
                                    text,
                                    Color.WHITE,
                                )
                            ]
                        )
                self.assertEqual(
                    self.test_view.get_call_params(),
                    expected,
                    self.test_view.get_call_params(),
                )
                self.assertEqual(
                    self.test_unit_view.get_call_params(),
                    expected_unit,
                    self.test_unit_view.get_call_params(),
                )

    def test_smith(self):
        test_cases = [
            (
                "metal 1",
                Pickaxe.METAL_1,
                {(0, 0): Item.METAL_1, (1, 2): Item.COAL},
                (4, 0),
            ),
            ("no material", None, {}, (4, 0)),
            (
                "wrong pos",
                None,
                {(0, 0): Item.METAL_1, (1, 2): Item.COAL},
                (3, 0),
            ),
            ("less material metal 1", None, {(0, 0): Item.METAL_1}, (4, 0)),
            (
                "metal 2",
                Pickaxe.METAL_2,
                {(0, 0): Item.METAL_2, (1, 2): Item.COAL, (2, 0): Pickaxe.METAL_1},
                (4, 0),
            ),
            (
                "less material metal2",
                None,
                {(0, 0): Item.METAL_2, (2, 0): Pickaxe.METAL_1},
                (4, 0),
            ),
        ]
        for case_name, expected, pushed_map, smith_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                pushed_map=pushed_map,
                smith_pos=smith_pos,
            ):
                self.reset()
                forge = Forge((2, 2))
                for pos, item in pushed_map.items():
                    abs_pos = tuple(p + t for p, t in zip(pos, Forge.TILE_POS))
                    forge.push(abs_pos, item)
                abs_pos = tuple(p + t for p, t in zip(smith_pos, Forge.TILE_POS))
                self.assertEqual(forge.smith(abs_pos), expected)
                self.assertEqual(forge.get_material(), set(pushed_map.values()))


class TestConsole(TestParent):
    def test_draw(self):
        messages = ["test", "console"]
        console = Console((2, 2))
        console.set_message(messages)
        console.draw()
        expected_pos = tuple(
            ct - GameCore.TILE_TILT + p for ct, p in zip((2, 2), Console.TILE_POS)
        )
        expected = []
        expected.extend(
            [
                (
                    "draw_rect",
                    expected_pos[0] * 8 - 1,
                    expected_pos[1] * 8 - 1,
                    8 * 7 + 2,
                    8 * 2 + 2,
                    Color.WHITE,
                    False,
                )
            ]
        )
        for y, item_list in enumerate(Console.FRAME_SIZE_MAP):
            for x in range(len(item_list)):
                expected.append(
                    (
                        "draw_rect",
                        (expected_pos[0] + x) * 8,
                        (expected_pos[1] + y) * 8,
                        8,
                        8,
                        Color.BLACK,
                        True,
                    )
                )
        for i, text in enumerate(messages):
            expected.append(
                (
                    "draw_text",
                    expected_pos[0] * 8 + 9,
                    (expected_pos[1] + i) * 8 + 1,
                    text,
                    Color.WHITE,
                )
            )
        self.assertEqual(
            self.test_view.get_call_params(),
            expected,
            self.test_view.get_call_params(),
        )

    def test_get_select_pos(self):
        console_rect = list(p * 8 for p in Console.TILE_POS) + list(
            p * 8 for p in (len(Console.FRAME_SIZE_MAP[0]), len(Console.FRAME_SIZE_MAP))
        )
        test_cases = [
            ("out", False, (0, 0)),
            ("left up", True, console_rect[:2]),
            (
                "right down",
                True,
                tuple(p + l - 1 for p, l in zip(console_rect[:2], console_rect[2:])),
            ),
            ("left up out", False, tuple(p - 1 for p in console_rect[:2])),
            (
                "right down out",
                False,
                tuple(
                    p + l - 1 + 1 for p, l in zip(console_rect[:2], console_rect[2:])
                ),
            ),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, mouse_pos=mouse_pos
            ):
                self.reset()
                console = Console((2, 2))
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                console.update()
                self.assertEqual(expected, console.is_tap())


class TestPlayer(TestUnitParent):
    def test_draw(self):
        player = Player()
        player.draw()
        expected = [("draw_unit", 2, 1, 1, 0, Direct.RIGHT, Direct.NUTRAL, (0, 0))]
        self.assertEqual(
            self.test_unit_view.get_call_params(),
            expected,
            self.test_unit_view.get_call_params(),
        )

    def test_move(self):
        player = Player()
        player.pos = (2, 2)
        next_pos = (2, 3)
        self.assertEqual((2, 2), player.get_pos(None))
        expected = []
        player.move(next_pos, Direct.RIGHT, False)
        player.draw()
        for i in range(8):
            self.assertEqual(True, player.is_moving())
            expected.append(
                ("draw_unit", 2, 2, 1, 0, Direct.RIGHT, Direct.RIGHT, (i, 0))
            )
            player.update()
            player.draw()
        expected.append(("draw_unit", 2, 3, 1, 0, Direct.RIGHT, Direct.NUTRAL, (0, 0)))
        self.assertEqual(False, player.is_moving())
        self.assertEqual(
            self.test_unit_view.get_call_params(),
            expected,
            self.test_unit_view.get_call_params(),
        )
        self.assertEqual((2, 3), player.get_pos(None))

    def test_get_pos(self):
        test_cases = [
            ("right", (3, 2), Direct.RIGHT),
            ("up", (2, 1), Direct.UP),
            ("left", (1, 2), Direct.LEFT),
            ("down", (2, 3), Direct.DOWN),
            ("stay", (2, 2), None),
        ]
        for case_name, expected, direct in test_cases:
            with self.subTest(case_name=case_name, expected=expected, direct=direct):
                self.reset()
                player = Player()
                player.pos = (2, 2)
                self.assertEqual(expected, player.get_pos(direct))


class TestCursor(TestParent):
    def test_draw_update(self):
        edge = tuple(
            [
                GameCore.CAMERA_RECT[0] // 8,
                GameCore.CAMERA_RECT[1] // 8,
                (GameCore.CAMERA_RECT[0] + GameCore.CAMERA_RECT[2]) // 8,
                (GameCore.CAMERA_RECT[1] + GameCore.CAMERA_RECT[3]) // 8,
            ]
        )
        (bag_edge, equip_edge) = tuple(
            tuple(
                [
                    rect[0] // 8,
                    rect[1] // 8,
                    (rect[0] + rect[2]) // 8,
                    (rect[1] + rect[3]) // 8,
                ]
            )
            for rect in (Cursor.BAG_RECT, Cursor.EQUIP_RECT)
        )
        test_cases = [
            case
            for name, rect, is_single in (
                ("field", edge, False),
                ("bag", bag_edge, False),
                ("equip", equip_edge, True),
            )
            for case in [
                (f"${name} (0, 0)", [rect[:2]], [(rect[0] * 8, rect[1] * 8)]),
                (
                    f"${name} (1, 1)",
                    [(rect[0] + 1, rect[1] + 1)] if not is_single else [None],
                    [(rect[0] * 8 + 8, rect[1] * 8 + 8)],
                ),
                (
                    f"${name} edge",
                    [(rect[2] - 1, rect[3] - 1)],
                    [(rect[2] * 8 - 1, rect[3] * 8 - 1)],
                ),
            ]
        ] + [
            ("less x", [None], [(edge[0] * 8 - 1, edge[1] * 8 + 8)]),
            ("less y", [None], [(edge[0] * 8 + 8, edge[1] * 8 - 1)]),
            ("over x", [None], [(edge[2] * 8, edge[1] * 8 + 8)]),
            ("over y", [None], [(edge[0] * 8 + 8, edge[3] * 8)]),
            ("double", [edge[:2], None], [(edge[0] * 8, edge[1] * 8)] * 2),
            ("hold", [edge[:2]] * 2, [(edge[0] * 8, edge[1] * 8), None]),
            (
                "double there",
                [edge[:2], (edge[0] + 1, edge[1] + 1)],
                [(edge[0] * 8, edge[1] * 8), (edge[0] * 8 + 8, edge[1] * 8 + 8)],
            ),
            (
                "double over",
                [edge[:2], None],
                [(edge[0] * 8, edge[1] * 8), (edge[0] * 8 - 1, edge[1] * 8 + 8)],
            ),
            ("triple", [edge[:2], None, edge[:2]], [(edge[0] * 8, edge[1] * 8)] * 3),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, mouse_pos=mouse_pos
            ):
                self.reset()
                cursor = Cursor((2, 2))
                cursor.update()
                cursor.draw()
                for pos in mouse_pos:
                    if pos is not None:
                        self.test_input.set_mouse_pos(
                            pos[0] - Cursor.TILT[0], pos[1] - Cursor.TILT[1]
                        )
                        self.test_input.set_is_click(True)
                    else:
                        self.test_input.set_mouse_pos(None, None)
                        self.test_input.set_is_click(False)
                    cursor.update()
                    cursor.draw()
                expected_list = []
                for e_pos in expected:
                    if e_pos is not None:
                        expected_list.append(
                            (
                                "draw_rect",
                                2 * 8 + (e_pos[0] - GameCore.TILE_TILT) * 8,
                                2 * 8 + (e_pos[1] - GameCore.TILE_TILT) * 8,
                                8,
                                8,
                                Color.RED,
                                False,
                            )
                        )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_get_select_pos(self):
        test_cases = [
            ("field", (1, 1), GameCore.CAMERA_RECT[:2]),
            ("bag", Bag.TILE_POS, Cursor.BAG_RECT[:2]),
            ("equip", Bag.EQUIP_TILE_POS, Cursor.EQUIP_RECT[:2]),
        ]
        for case_name, expected_pos, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected_pos=expected_pos, mouse_pos=mouse_pos
            ):
                self.reset()
                cursor = Cursor((GameCore.TILE_TILT, GameCore.TILE_TILT))
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                self.assertEqual(None, cursor.get_select_pos())
                cursor.update()
                cursor.draw()
                self.assertEqual(None, cursor.get_select_pos())
                cursor.update()
                cursor.draw()
                self.assertEqual(expected_pos, cursor.get_select_pos())
                cursor.update()
                cursor.draw()
                self.assertEqual(None, cursor.get_select_pos())
                draw_pos = tuple(p * 8 for p in expected_pos)
                self.assertEqual(
                    [("draw_rect", *draw_pos, 8, 8, Color.RED, False)] * 2,
                    self.test_view.get_call_params(),
                )

    def test_get_select_rel_pos(self):
        tilt = GameCore.TILE_TILT
        test_cases = [
            ("left", (-1, 0), ((tilt - 1) * 8, tilt * 8)),
            ("right", (1, 0), ((tilt + 1) * 8, tilt * 8)),
            ("up", (0, -1), (tilt * 8, (tilt - 1) * 8)),
            ("down", (0, 1), (tilt * 8, (tilt + 1) * 8)),
            ("2 left", (-2, 0), ((tilt - 2) * 8, tilt * 8)),
            ("2 right", (2, 0), ((tilt + 2) * 8, tilt * 8)),
            ("2 up", (0, -2), (tilt * 8, (tilt - 2) * 8)),
            ("2 down", (0, 2), (tilt * 8, (tilt + 2) * 8)),
            ("left up", (-1, -1), ((tilt - 1) * 8, (tilt - 1) * 8)),
            ("2 right 2 down", (2, 2), ((tilt + 2) * 8, (tilt + 2) * 8)),
            ("out", (0, 0), (GameCore.CAMERA_RECT[0] - 1, GameCore.CAMERA_RECT[1] - 1)),
            ("bag", (0, 0), (Bag.TILE_POS[0] * 8, Bag.TILE_POS[1] * 8)),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, mouse_pos=mouse_pos
            ):
                self.reset()
                cursor = Cursor((2, 1))
                if mouse_pos is not None:
                    self.test_input.set_mouse_pos(
                        mouse_pos[0] - Cursor.TILT[0], mouse_pos[1] - Cursor.TILT[1]
                    )
                    self.test_input.set_is_click(True)
                else:
                    self.test_input.set_mouse_pos(None, None)
                    self.test_input.set_is_click(False)
                for _ in range(2):
                    cursor.update()
                self.assertEqual(cursor.get_select_rel_pos(), expected)


class TestPosition(TestParent):
    def test_draw(self):
        position = Position((2, 2))
        position.draw()
        expected_pos = tuple(
            (ct - GameCore.TILE_TILT + p) * 8 + o
            for ct, p, o in zip((2, 2), Position.TILE_POS, Position.TEXT_OFFSET)
        )
        expected = [("draw_text", *expected_pos, "(0,1)", Color.WHITE)]
        self.assertEqual(
            self.test_view.get_call_params(),
            expected,
            self.test_view.get_call_params(),
        )


if __name__ == "__main__":
    unittest.main()
