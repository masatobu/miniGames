import sys
import os
import unittest
from unittest.mock import patch

for p in ["../../src/pyxel_combo_card", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from recipe import Recipe, Combo  # pylint: disable=C0413
from card import Card, Symbol  # pylint: disable=C0413


class TestRecipeInitialState(unittest.TestCase):
    @patch("recipe.Recipe._get_devolved_target_set")
    @patch("recipe.Recipe._get_devolved_source_set")
    @patch("recipe.random.choice")
    def test_get(self, mock_choice, mock_devolved_source_set, mock_devolved_target_set):
        # 常に最初のマークを選択するようにモック
        mock_choice.side_effect = lambda x: x[0]
        test_cases = [
            (
                "S1",
                [[Combo.S1]],
                [[Card(Symbol.B3), Card(Symbol.B3)]],
                [Card(Symbol.S1)],
            ),
            (
                "H1",
                [[Combo.H1]],
                [[Card(Symbol.S1), Card(Symbol.S2)]],
                [Card(Symbol.H1)],
            ),
            (
                "S2, G1",
                [[Combo.S2, Combo.S3], [Combo.G1, Combo.G2]],
                [
                    [Card(Symbol.B1), Card(Symbol.B3)],
                    [Card(Symbol.H1), Card(Symbol.H3)],
                ],
                [Card(Symbol.S2), Card(Symbol.G1)],
            ),
        ]
        for case_name, combo_list, expected_source, expected_target in test_cases:
            with self.subTest(
                case_name=case_name,
                combo_list=combo_list,
                expected_source=expected_source,
                expected_target=expected_target,
            ):
                mock_devolved_source_set.return_value = [set() for _ in combo_list]
                mock_devolved_target_set.return_value = [set() for _ in combo_list]
                recipe = Recipe(combo_candidates=combo_list)
                self.assertEqual(recipe.get_source_list(), expected_source)
                for recipe_id, target in enumerate(expected_target):
                    self.assertEqual(recipe.get_target(recipe_id), target)

    def test_empty_recipe_map(self):
        """空のレシピマップを指定した場合、レシピが空になることを確認"""
        recipe = Recipe(combo_candidates=[])
        self.assertEqual(recipe.get_source_list(), [])

    @patch("recipe.Recipe._get_devolved_target_set")
    @patch("recipe.Recipe._get_devolved_source_set")
    @patch("recipe.random.random")
    def test_get_with_devolved(
        self,
        mock_random,
        mock_devolved_source_set,
        mock_devolved_target_set,
    ):
        mock_random.return_value = 0  # 退化レシピを強制的に利用するように
        test_cases = [
            (
                "only S1",
                [[Combo.S1]],
                [{(Card(Symbol.S1), Card(Symbol.S1))}],
                [{Card(Symbol.B3)}],
                [[Card(Symbol.S1), Card(Symbol.S1)]],
                [[Card(Symbol.B3)]],
            ),
            (
                "only S2",
                [[Combo.S2]],
                [{(Card(Symbol.S2), Card(Symbol.S2))}],
                [{Card(Symbol.B1)}],
                [[Card(Symbol.S2), Card(Symbol.S2)]],
                [[Card(Symbol.B1)]],
            ),
            (
                "only H1 and H2",
                [[Combo.H1, Combo.H2]],
                [{(Card(Symbol.H1), Card(Symbol.H1))}],
                [{Card(Symbol.S1)}],
                [[Card(Symbol.H1), Card(Symbol.H1)]],
                [[Card(Symbol.S1)]],
            ),
            (
                "S3 and S4, H3 and H4",
                [[Combo.S3, Combo.S4], [Combo.H3, Combo.H4]],
                [
                    {(Card(Symbol.S3), Card(Symbol.S4))},
                    {(Card(Symbol.H4), Card(Symbol.H4))},
                ],
                [{Card(Symbol.B1)}, {Card(Symbol.S1)}],
                [
                    [Card(Symbol.S3), Card(Symbol.S4)],
                    [Card(Symbol.H4), Card(Symbol.H4)],
                ],
                [[Card(Symbol.B1), Card(Symbol.S1)]],
            ),
        ]
        for (
            case_name,
            combo_candidates,
            devolved_source_set,
            devolved_target_set,
            expected_source,
            expected_target,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                mock_devolved_source_set.return_value = devolved_source_set
                mock_devolved_target_set.return_value = devolved_target_set
                recipe = Recipe(combo_candidates=combo_candidates)
                self.assertEqual(recipe.get_source_list(), expected_source)
                for recipe_id, target_list in enumerate(expected_target):
                    self.assertIn(recipe.get_target(recipe_id), target_list)

    @patch("recipe.Recipe._get_devolved_target_set")
    @patch("recipe.Recipe._get_devolved_source_set")
    @patch("recipe.random.random")
    @patch("recipe.random.choice")
    def test_get_probability(
        self,
        mock_choice,
        mock_random,
        mock_devolved_source_set,
        mock_devolved_target_set,
    ):
        mock_devolved_source_set.return_value = [{(Card(Symbol.S1), Card(Symbol.S1))}]
        mock_devolved_target_set.return_value = [{Card(Symbol.B3)}]
        mock_choice.side_effect = lambda x: x[0]
        test_cases = [
            (
                "select devolved",
                0,
                [[Combo.S1]],
                [[Card(Symbol.S1), Card(Symbol.S1)]],
                [[Card(Symbol.B3)]],
            ),
            (
                "select combo",
                1,
                [[Combo.S1]],
                [[Card(Symbol.B3), Card(Symbol.B3)]],
                [[Card(Symbol.S1)]],
            ),
            (
                "boundary devolved with 1",
                1 / (1 + 1) - 0.0001,
                [[Combo.S1]],
                [[Card(Symbol.S1), Card(Symbol.S1)]],
                [[Card(Symbol.B3)]],
            ),
            (
                "boundary combo with 1",
                1 / (1 + 1),
                [[Combo.S1]],
                [[Card(Symbol.B3), Card(Symbol.B3)]],
                [[Card(Symbol.S1)]],
            ),
            (
                "boundary devolved with 4",
                1 / (4 + 1) - 0.0001,
                [[Combo.S1, Combo.S2, Combo.S3, Combo.S4]],
                [[Card(Symbol.S1), Card(Symbol.S1)]],
                [[Card(Symbol.B3)]],
            ),
            (
                "boundary combo with 4",
                1 / (4 + 1),
                [[Combo.S1, Combo.S2, Combo.S3, Combo.S4]],
                [[Card(Symbol.B3), Card(Symbol.B3)]],
                [[Card(Symbol.S1)]],
            ),
        ]
        for (
            case_name,
            probability,
            combo_candidates,
            expected_source,
            expected_target,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                mock_random.return_value = probability
                recipe = Recipe(combo_candidates=combo_candidates)
                self.assertEqual(recipe.get_source_list(), expected_source)
                for recipe_id, target_list in enumerate(expected_target):
                    self.assertIn(recipe.get_target(recipe_id), target_list)


class TestRecipeShuffle(unittest.TestCase):
    @patch("recipe.random.choice")
    def test_shuffle(self, mock_choice):
        test_cases = [
            (
                "S3, G2",
                [[Combo.S2, Combo.S3], [Combo.G1, Combo.G2]],
                [
                    [Card(Symbol.B1), Card(Symbol.B1)],
                    [Card(Symbol.H2), Card(Symbol.H4)],
                ],
                [Card(Symbol.S3), Card(Symbol.G2)],
            ),
            (
                "S4, H2",
                [[Combo.S3, Combo.S4], [Combo.H1, Combo.H2]],
                [
                    [Card(Symbol.B2), Card(Symbol.B2)],
                    [Card(Symbol.S4), Card(Symbol.S5)],
                ],
                [Card(Symbol.S4), Card(Symbol.H2)],
            ),
        ]
        for case_name, combo_list, expected_source, expected_target in test_cases:
            with self.subTest(
                case_name=case_name,
                combo_list=combo_list,
                expected_source=expected_source,
                expected_target=expected_target,
            ):
                # 常に最初のマークを選択するようにモック
                mock_choice.side_effect = lambda x: x[0]
                recipe = Recipe(combo_candidates=combo_list, devolved_flg=False)
                # 常に2番目のマークを選択するようにモック
                mock_choice.side_effect = lambda x: x[1]
                recipe.shuffle()
                self.assertEqual(recipe.get_source_list(), expected_source)
                for recipe_id, target in enumerate(expected_target):
                    self.assertEqual(recipe.get_target(recipe_id), target)

    @patch("recipe.random.random")
    def test_shuffle_with_devolve(self, mock_random):
        mock_random.return_value = 1  # 退化レシピを強制的に利用しない
        recipe = Recipe(combo_candidates=[[Combo.S1]])
        self.assertEqual(recipe.get_source_list(), [[Card(Symbol.B3), Card(Symbol.B3)]])
        self.assertEqual(recipe.get_target(0), Card(Symbol.S1))
        mock_random.return_value = 0  # 退化レシピを強制的に利用する
        recipe.shuffle()
        self.assertEqual(recipe.get_source_list(), [[Card(Symbol.S1), Card(Symbol.S1)]])
        self.assertEqual(recipe.get_target(0), Card(Symbol.B3))


class TestRecipeGetExecutableIds(unittest.TestCase):
    def test_get_executable_recipeids(self):
        test_cases = [
            (
                "one executable recipe id 0",
                [Card(Symbol.B1), Card(Symbol.B3)],
                [0],
            ),
            (
                "one executable recipe id 1",
                [Card(Symbol.S1), Card(Symbol.S2)],
                [1],
            ),
            (
                "card order independent",
                [Card(Symbol.S2), Card(Symbol.S1)],
                [1],
            ),
            (
                "multiple executable recipes",
                [
                    Card(Symbol.B1),
                    Card(Symbol.B3),
                    Card(Symbol.S1),
                    Card(Symbol.S2),
                ],
                [0, 1],
            ),
            (
                "no executable recipe wrong symbol",
                [Card(Symbol.B2), Card(Symbol.B2)],
                [],
            ),
            ("empty hand", [], []),
            ("insufficient cards one short", [Card(Symbol.S1)], []),
            (
                "insufficient cards partial match",
                [Card(Symbol.B2), Card(Symbol.B3)],
                [],
            ),
            ("duplicate cards in hand", [Card(Symbol.B1), Card(Symbol.B3)] * 2, [0]),
        ]
        for case_name, hand_cards, expected_ids in test_cases:
            with self.subTest(
                case_name=case_name,
                hand_cards=hand_cards,
                expected_ids=expected_ids,
            ):
                recipe = Recipe(combo_candidates=[[Combo.S2], [Combo.H1]])
                recipe._source = [  # pylint: disable=W0212
                    [Card(Symbol.B1), Card(Symbol.B3)],
                    [Card(Symbol.S1), Card(Symbol.S2)],
                ]
                executable_ids = recipe.get_executable_recipe_ids(hand_cards)
                self.assertEqual(executable_ids, expected_ids)


class TestRecipeFromCombo(unittest.TestCase):
    def test_recipe_from_combo(self):
        """Combo から Recipe を生成できる（三角測量）"""
        test_cases = [
            # (Combo, 期待される材料1, 期待される材料2, 期待される結果)
            (Combo.S1, Symbol.B3, Symbol.B3, Symbol.S1),
            (Combo.S2, Symbol.B1, Symbol.B3, Symbol.S2),
            (Combo.S3, Symbol.B1, Symbol.B1, Symbol.S3),
            (Combo.H1, Symbol.S1, Symbol.S2, Symbol.H1),
            (Combo.G1, Symbol.H1, Symbol.H3, Symbol.G1),
        ]

        for combo, expected_source1, expected_source2, expected_result in test_cases:
            with self.subTest(combo=combo):
                # Recipeコンストラクタにcombo_candidatesを渡して生成
                recipe = Recipe(combo_candidates=[[combo]], devolved_flg=False)

                # 必要カードが正しく変換される
                source_list = recipe.get_source_list()
                self.assertEqual(len(source_list), 1)
                self.assertEqual(len(source_list[0]), 2)
                self.assertEqual(source_list[0][0].symbol, expected_source1)
                self.assertEqual(source_list[0][1].symbol, expected_source2)

                # 結果カードが正しい Symbol を持つ
                result_card = recipe.get_target(0)
                self.assertEqual(result_card.symbol, expected_result)

    def test_generate_devolved_recipe(self):
        """退化レシピの生成と動作確認"""
        test_cases = [
            # (Combo候補, 期待される材料候補, 期待される結果候補)
            ([Combo.S1], [[Symbol.S1, Symbol.S1]], [Symbol.B3]),
            ([Combo.S2], [[Symbol.S2, Symbol.S2]], [Symbol.B1, Symbol.B3]),
            (
                [Combo.S1, Combo.S2],
                [
                    [Symbol.S1, Symbol.S1],
                    [Symbol.S2, Symbol.S2],
                    [Symbol.S1, Symbol.S2],
                ],
                [Symbol.B1, Symbol.B3],
            ),
            ([Combo.G1], [], []),
            (
                [Combo.H1, Combo.H2, Combo.G2],
                [
                    [Symbol.H1, Symbol.H1],
                    [Symbol.H2, Symbol.H2],
                    [Symbol.H1, Symbol.H2],
                ],
                [Symbol.S1, Symbol.S2, Symbol.S4, Symbol.S5],
            ),
        ]

        for combo_list, expected_source_list, expected_result_list in test_cases:
            with self.subTest(combo=combo_list):
                # Recipeコンストラクタにcombo_candidatesを渡して生成
                recipe = Recipe(combo_candidates=[combo_list])

                # 必要カードが正しく変換される
                source_set = recipe._get_devolved_source_set()  # pylint: disable=W0212
                self.assertEqual(len(source_set), 1)
                expected_source_set = {
                    tuple(Card(sym) for sym in source_syms)
                    for source_syms in expected_source_list
                }
                self.assertSetEqual(source_set[0], expected_source_set)

                # 結果カードが正しい Symbol を持つ
                result_set = recipe._get_devolved_target_set()  # pylint: disable=W0212
                self.assertEqual(len(result_set), 1)
                expected_result_set = {Card(sym) for sym in expected_result_list}
                self.assertSetEqual(result_set[0], expected_result_set)

    def test_generate_devolved_recipe_with_no_candidates(self):
        # Recipeコンストラクタにcombo_candidatesを渡して生成
        recipe = Recipe(combo_candidates=[])

        # 必要カードが正しく変換される
        source_set = recipe._get_devolved_source_set()  # pylint: disable=W0212
        self.assertEqual(len(source_set), 0)

        # 結果カードが正しい Symbol を持つ
        result_set = recipe._get_devolved_target_set()  # pylint: disable=W0212
        self.assertEqual(len(result_set), 0)
