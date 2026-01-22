import os
import sys
import unittest
from unittest.mock import patch
import math

for p in ["../src/"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from logic import (  # pylint: disable=C0413
    FieldGenerator,
    Item,
    Pickaxe,
    PickaxeGenerator,
)


class TestFieldGenerator(unittest.TestCase):
    @patch("logic.FieldGenerator._is_appear")
    def test_get_item(self, mock):
        test_cases = [
            ("metal 1", Item.METAL_1, 0),
            ("metal 2", Item.METAL_2, 1),
            ("metal 3", Item.METAL_3, 2),
            ("metal 4", Item.METAL_4, 3),
            ("metal 5", Item.METAL_5, 4),
            ("jewel", Item.JEWEL, 5),
            ("coal", Item.COAL, 6),
            ("none", None, -1),
        ]
        for case_name, expected, ret_ture_order in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                ret_ture_order=ret_ture_order,
            ):
                mock.side_effect = [i == ret_ture_order for i in range(len(Item))]
                field_generator = FieldGenerator.create()
                self.assertEqual(
                    expected,
                    field_generator.get_item(2, 3),
                )

    @patch("logic.FieldGenerator.get_hash")
    def test_is_appeear(self, mock):
        test_cases = [
            ("metal 1 peak appear", True, 0.18 * 10000, 7, Item.METAL_1),
            ("metal 1 peak not appear", False, 0.35 * 10000, 7, Item.METAL_1),
            ("metal 1 no peak not appear", False, 0.26 * 10000, 6, Item.METAL_1),
            ("metal 2 peak appear", True, 0.18 * 10000, 14, Item.METAL_2),
            ("metal 2 peak not appear", False, 0.35 * 10000, 14, Item.METAL_2),
            ("metal 2 no peak not appear", False, 0.26 * 10000, 13, Item.METAL_2),
            ("metal 3 peak appear", True, 0.18 * 10000, 24, Item.METAL_3),
            ("metal 3 peak not appear", False, 0.35 * 10000, 24, Item.METAL_3),
            ("metal 3 no peak not appear", False, 0.26 * 10000, 23, Item.METAL_3),
            ("metal 4 peak appear", True, 0.18 * 10000, 34, Item.METAL_4),
            ("metal 4 peak not appear", False, 0.35 * 10000, 34, Item.METAL_4),
            ("metal 4 no peak not appear", False, 0.26 * 10000, 33, Item.METAL_4),
            ("metal 5 peak appear", True, 0.18 * 10000, 45, Item.METAL_5),
            ("metal 5 peak not appear", False, 0.40 * 10000, 45, Item.METAL_5),
            ("metal 5 no peak not appear", False, 0.26 * 10000, 44, Item.METAL_5),
            # ID-034: JEWEL フラット化テスト（ID-034-10.5.1で確率再調整: 0.05→0.01）
            # Y < 48: 出現しない（確率0）
            ("jewel Y47 not appear", False, 10000, 47, Item.JEWEL),
            # Y >= 48: フラット化で確率 0.01（ID-034-10.5.1で確率再調整）
            ("jewel Y48 appear (flat)", True, (0.01 - 0.001) * 10000, 48, Item.JEWEL),
            (
                "jewel Y48 not appear (flat)",
                False,
                (0.01 + 0.001) * 10000,
                48,
                Item.JEWEL,
            ),
            ("jewel Y49 appear (flat)", True, (0.01 - 0.001) * 10000, 49, Item.JEWEL),
            ("jewel Y56 appear (flat)", True, (0.01 - 0.001) * 10000, 56, Item.JEWEL),
            (
                "jewel Y56 not appear (flat)",
                False,
                (0.01 + 0.001) * 10000,
                56,
                Item.JEWEL,
            ),
            ("coal peak appear", True, (0.15 - 0.01) * 10000, 50, Item.COAL),
            ("coal peak not appear", False, (0.15 + 0.01) * 10000, 50, Item.COAL),
            ("coal peak not appear", True, (0.15 - 0.01) * 10000, 49, Item.COAL),
        ]
        for case_name, expected, mock_value, pos_y, item in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                mock_value=mock_value,
                pos_y=pos_y,
                item=item,
            ):
                mock.return_value = mock_value
                field_generator = FieldGenerator.create()
                result = field_generator._is_appear(  # pylint: disable=W0212
                    10, pos_y, item
                )
                self.assertEqual(expected, result)

    def test_normal_pdf(self):
        field_generator = FieldGenerator.create()
        ret = field_generator._normal_pdf(0)  # pylint: disable=W0212
        self.assertEqual(ret, min(1.0, 1 / math.sqrt(2 * math.pi * 9) * 1.4))

    def test_is_digable(self):
        layer_pos_list = [layer[0][0] for layer in FieldGenerator.LAYERS]
        pickaxe_list = sorted(Pickaxe, key=lambda e: e.value[0])
        test_cases = [
            ("layer 1 digable", True, 2, Pickaxe.METAL_1),
            ("layer 1 not digable", False, 2, None),
            ("layer 1 digable over", True, 2, Pickaxe.METAL_2),
            ("cant use item", False, 2, Item.METAL_2),
        ]
        for i in range(len(layer_pos_list) - 1):
            test_cases += [
                (
                    f"layer {i + 2} digable",
                    True,
                    layer_pos_list[i + 1],
                    pickaxe_list[i + 1],
                ),
                (f"layer {i + 2} not digable", False, layer_pos_list[i + 1], None),
                (
                    f"layer {i + 2} digable over",
                    True,
                    layer_pos_list[i + 1],
                    pickaxe_list[i + 2],
                ),
                (
                    f"layer {i + 2} cant digable less",
                    False,
                    layer_pos_list[i + 1],
                    pickaxe_list[i],
                ),
            ]
        for case_name, expected, y_pos, pickaxe in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                y_pos=y_pos,
                pickaxe=pickaxe,
            ):
                field_generator = FieldGenerator.create()
                self.assertEqual(
                    expected, field_generator.is_digable(2, y_pos, pickaxe)
                )

    def test_get_lightest_path(self):
        test_cases = [
            ("same pos", [(2, 2)], (2, 2), (0, 0), set()),
            ("neighbor no dig", [(2, 2), (3, 2)], (2, 2), (1, 0), set()),
            (
                "multi move no dig",
                [(2, 2), (2, 3), (2, 4), (1, 4), (0, 4)],
                (2, 2),
                (-2, 2),
                set(),
            ),
            (
                "multi move with y dig",
                [(2, 2), (2, 3), (2, 4), (1, 4), (0, 4)],
                (2, 2),
                (-2, 2),
                {(2, 3)},
            ),
            (
                "y<=1 corridor ignored due to longer distance",
                [(2, 2), (1, 2), (0, 2)],
                (2, 2),
                (-2, 0),
                set(),
            ),
            (
                "same distance choose lower cost (no alternative)",
                [(2, 2), (1, 2), (0, 2)],
                (2, 2),
                (-2, 0),
                {(2, 1)},
            ),
            (
                "same distance, y<=1 path has lower cost",
                [(0, 2), (0, 1), (1, 1), (1, 0)],
                (0, 2),
                (1, -2),
                set(),
            ),
        ]

        for case_name, expected, start_pos, rel_pos, dig_pos_set in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                start_pos=start_pos,
                rel_pos=rel_pos,
                dig_pos_set=dig_pos_set,
            ):
                field_generator = FieldGenerator.create()
                self.assertEqual(
                    expected,
                    field_generator.get_lightest_path(start_pos, rel_pos, dig_pos_set),
                )


class TestPickaxeGenerator(unittest.TestCase):
    def test_get_recipe(self):
        test_cases = [
            ("metal 1", [Item.METAL_1, None, Pickaxe.METAL_1], Item.METAL_1),
            ("metal 2", [Item.METAL_2, Pickaxe.METAL_1, Pickaxe.METAL_2], Item.METAL_2),
            ("metal 3", [Item.METAL_3, Pickaxe.METAL_2, Pickaxe.METAL_3], Item.METAL_3),
            ("metal 4", [Item.METAL_4, Pickaxe.METAL_3, Pickaxe.METAL_4], Item.METAL_4),
            ("metal 5", [Item.METAL_5, Pickaxe.METAL_4, Pickaxe.METAL_5], Item.METAL_5),
            ("jewel", [Item.JEWEL, Pickaxe.METAL_5, Pickaxe.JEWEL], Item.JEWEL),
        ]
        for case_name, expected, item in test_cases:
            with self.subTest(case_name=case_name, expected=expected, item=item):
                self.assertEqual(PickaxeGenerator.get_recipe(item), expected)

    def test_is_generatable(self):
        test_cases = [
            ("cant", False, set()),
            ("cant with item", False, {Item.COAL}),
            ("metal 1", True, {Item.METAL_1, Item.COAL}),
            ("metal 1 over", True, {Item.METAL_1, Item.COAL, Item.METAL_2}),
            ("pickaxe", True, {Pickaxe.METAL_1}),
            ("pickaxe over", True, {Pickaxe.METAL_1, Pickaxe.JEWEL}),
            ("pickaxe and material", True, {Pickaxe.METAL_1, Item.METAL_1, Item.COAL}),
        ]
        for case_name, expected, item_set in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, item_set=item_set
            ):
                self.assertEqual(PickaxeGenerator.is_generatable(item_set), expected)


if __name__ == "__main__":
    unittest.main()
