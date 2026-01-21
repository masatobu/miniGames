import os
import sys
import unittest
from unittest.mock import patch

for p in ["../../src/pyxel_combo_card", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from game import Game, GameResult  # pylint: disable=C0413
from card import Card, Symbol  # pylint: disable=C0413
from hand import Hand  # pylint: disable=C0413
from recipe import Recipe, Combo  # pylint: disable=C0413

class TestGameInitialState(unittest.TestCase):
    def test_game_starts_with_one_card(self):
        """Game初期化時にプレイヤーとNPC両方に初期カードが1枚ずつ配布される"""
        game = Game()

        # プレイヤー手札
        player_cards = game.hand.get_cards()
        self.assertEqual(1, len(player_cards))
        self.assertIn(player_cards[0].symbol, [Symbol.B1, Symbol.B2, Symbol.B3])

        # NPC手札（プレイヤーと同じ条件でカード配布）
        npc_cards = game.npc_hand.get_cards()
        self.assertEqual(1, len(npc_cards))
        self.assertIn(npc_cards[0].symbol, [Symbol.B1, Symbol.B2, Symbol.B3])

    @patch("game.random.choice")
    @patch("recipe.random.choice")
    def test_initial_card_has_symbol(self, mock_recipe_choice, mock_game_choice):
        """初期カード（rank 1）にB1, B2, B3のいずれかのシンボルが設定される"""
        # recipe.random.choice をモック（Comboリストから最初の要素を返す）
        mock_recipe_choice.side_effect = lambda lst: lst[0]
        # game.random.choice()をリストの最初の要素を返すように設定（シンボルとマークの両方に対応）
        mock_game_choice.side_effect = lambda lst: lst[0]

        game = Game()
        cards = game.hand.get_cards()

        self.assertEqual(1, len(cards))
        # Game.COMBO_CANDIDATESの構造上、初期カードはB1, B2, B3のいずれか
        # モックでlst[0]を返すので、Symbol.B1が選択される
        self.assertEqual(Symbol.B1, cards[0].symbol)


class TestGameState(unittest.TestCase):
    def test_is_cleared(self):
        """手札にゴールシンボル（G1, G2）があるかを判定（プレイヤー・NPC共通）"""
        test_cases = [
            ("G1 exists", [Symbol.G1], True),
            ("G2 exists", [Symbol.G2], True),
            ("no goal symbol", [Symbol.S1, Symbol.H1], False),
            ("only basic symbols", [Symbol.B1, Symbol.B2, Symbol.B3], False),
            ("empty hand", [], False),
            ("G1 among other cards", [Symbol.S1, Symbol.G1, Symbol.H2], True),
        ]
        for case_name, card_symbols, expected in test_cases:
            with self.subTest(case=case_name):
                game = Game()
                hand = Hand()
                for symbol in card_symbols:
                    hand.add_card(Card(symbol))

                result = game._is_cleared(hand)  # pylint: disable=W0212
                self.assertEqual(expected, result)

    def test_get_game_result(self):
        """勝敗判定: プレイヤーとNPCのゴールシンボル保有状態に応じた結果を返す"""
        test_cases = [
            # (case_name, player_symbols, npc_symbols, expected_result)
            ("プレイヤーのみクリア → WIN", [Symbol.G1], [Symbol.S1], GameResult.WIN),
            ("NPCのみクリア → LOSE", [Symbol.S1], [Symbol.G1], GameResult.LOSE),
            ("両者クリア → DRAW", [Symbol.G1], [Symbol.G2], GameResult.DRAW),
            ("どちらもクリアしていない → None", [Symbol.S1], [Symbol.H1], None),
            ("プレイヤーG2でクリア", [Symbol.G2], [Symbol.S1], GameResult.WIN),
            ("NPCG2でクリア", [Symbol.S1], [Symbol.G2], GameResult.LOSE),
            ("両者空手札 → None", [], [], None),
        ]
        for case_name, player_symbols, npc_symbols, expected in test_cases:
            with self.subTest(case=case_name):
                game = Game()
                game._hand = Hand()  # pylint: disable=W0212
                game._npc_hand = Hand()  # pylint: disable=W0212
                for symbol in player_symbols:
                    game.hand.add_card(Card(symbol))
                for symbol in npc_symbols:
                    game.npc_hand.add_card(Card(symbol))

                result = game.get_game_result()
                self.assertEqual(expected, result)

    def test_is_game_over(self):
        """ゲーム終了判定: プレイヤーまたはNPCがクリアした場合にTrueを返す"""
        test_cases = [
            # (case_name, player_symbols, npc_symbols, expected)
            ("プレイヤーのみクリア → True", [Symbol.G1], [Symbol.S1], True),
            ("NPCのみクリア → True", [Symbol.S1], [Symbol.G1], True),
            ("両者クリア → True", [Symbol.G1], [Symbol.G2], True),
            ("どちらもクリアしていない → False", [Symbol.S1], [Symbol.H1], False),
            ("両者空手札 → False", [], [], False),
        ]
        for case_name, player_symbols, npc_symbols, expected in test_cases:
            with self.subTest(case=case_name):
                game = Game()
                game._hand = Hand()  # pylint: disable=W0212
                game._npc_hand = Hand()  # pylint: disable=W0212
                for symbol in player_symbols:
                    game.hand.add_card(Card(symbol))
                for symbol in npc_symbols:
                    game.npc_hand.add_card(Card(symbol))

                result = game.is_game_over()
                self.assertEqual(expected, result)


class TestGameDistributeCard(unittest.TestCase):
    """Game._distribute_card_to()のテスト（プレイヤーとNPC共通）"""

    @patch("recipe.random.choice")
    @patch("game.random.choice")
    def test_distribute_card(self, mock_game_choice, mock_recipe_choice):
        """turn()を呼び出すと、プレイヤーとNPC両方にカードが追加される"""
        mock_game_choice.side_effect = lambda lst: lst[0]
        mock_recipe_choice.side_effect = lambda lst: lst[0]
        test_cases = [
            ("1回呼び出し", 1),
            ("3回呼び出し", 3),
        ]

        for case_name, call_count in test_cases:
            with self.subTest(case=case_name):
                game = Game()
                game._hand = Hand()  # pylint: disable=W0212
                game._npc_hand = Hand()  # pylint: disable=W0212

                for _ in range(call_count):
                    game.turn()

                # プレイヤー手札
                player_cards = game.hand.get_cards()
                self.assertEqual(len(player_cards), call_count)
                for card in player_cards:
                    self.assertIn(card.symbol, [Symbol.B1, Symbol.B2, Symbol.B3])

                # NPC手札（プレイヤーと同じ条件でカード配布）
                npc_cards = game.npc_hand.get_cards()
                self.assertEqual(len(npc_cards), call_count)
                for card in npc_cards:
                    self.assertIn(card.symbol, [Symbol.B1, Symbol.B2, Symbol.B3])

    @patch("game.random.choice")
    @patch("recipe.random.choice")
    def test_distribute_card_has_random_symbols(
        self, mock_recipe_choice, mock_game_choice
    ):
        """配布されるカードのシンボルはB1, B2, B3からランダムに決定される"""
        # recipe.random.choice をモック（Comboリストから最初の要素を返す）
        mock_recipe_choice.side_effect = lambda lst: lst[0]
        # game.random.choice()をリストの最初の要素を返すように設定
        mock_game_choice.side_effect = lambda lst: lst[0]

        game = Game()
        game._hand = Hand()  # pylint: disable=W0212
        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=[[Combo.S1, Combo.S2]],
            devolved_flg=False,
        )

        # _distribute_card()を2回呼び出し
        game.turn()
        game.turn()

        # random.choice()がComboリストで呼ばれることを確認
        mock_game_choice.assert_called_with([Combo.S1, Combo.S2])

        # 両方のカードがB1シンボルを持つことを確認
        cards = game.hand.get_cards()
        for card in cards:
            self.assertEqual(Symbol.B1, card.symbol)


class TestMaxHandSizeLimit(unittest.TestCase):
    """手札最大枚数制限のテスト（プレイヤーとNPC共通）

    MAX_HAND_SIZE = 7 の根拠:
    - 画面幅: 300px
    - カード幅: 30px、カード間隔: 10px、左マージン: 10px
    - 1行表示可能枚数: (300 - 10) / (30 + 10) ≈ 7.25 → 7枚
    - プレイテストで7枚が限界と確認
    """

    @patch("game.random.choice")
    def test_max_hand_size_limit(self, mock_game_choice):
        """プレイヤーとNPC両方で、手札が最大枚数に達した場合turn()でカード配布されない"""
        mock_game_choice.side_effect = lambda lst: lst[0]
        game = Game()
        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=[[Combo.S1]],
            devolved_flg=False,
        )

        # プレイヤーとNPC両方の手札を最大枚数-1まで追加（初期カード1枚含めて6枚）
        for _ in range(5):
            game.hand.add_card(Card(Symbol.B1))
            game.npc_hand.add_card(Card(Symbol.B1))

        self.assertEqual(6, len(game.hand.get_cards()), "プレイヤー: 最大枚数-1の状態")
        self.assertEqual(6, len(game.npc_hand.get_cards()), "NPC: 最大枚数-1の状態")

        # turn()でカードが1枚追加される（最大枚数に到達）
        game.turn()
        self.assertEqual(7, len(game.hand.get_cards()), "プレイヤー: turn()で7枚に到達")
        self.assertEqual(7, len(game.npc_hand.get_cards()), "NPC: turn()で7枚に到達")

        # さらにturn()を呼び出してもカードが追加されない
        game.turn()
        self.assertEqual(
            7,
            len(game.hand.get_cards()),
            "プレイヤー: 最大枚数に達したらカード配布されない",
        )
        self.assertEqual(
            7,
            len(game.npc_hand.get_cards()),
            "NPC: 最大枚数に達したらカード配布されない",
        )


class TestGameRecipe(unittest.TestCase):
    @patch("game.random.choice")
    @patch("recipe.random.choice")
    @patch("random.random")
    def test_game_uses_symbol_recipes(
        self, mock_random, mock_recipe_choice, mock_game_choice
    ):
        """Game.__init__() でシンボルレシピが使用される"""
        # recipe.random.choice をモック（Comboリストから最初の要素を返す）
        mock_recipe_choice.side_effect = lambda lst: lst[0]
        # game.random.choice をモック（初期カード配布用）
        mock_game_choice.side_effect = lambda lst: lst[0]
        # 退化レシピを強制的に利用しないように
        mock_random.return_value = 1.0

        # Game インスタンス作成
        game = Game()

        # 期待されるCombo（Game.COMBO_CANDIDATESから最初の要素）
        expected_combo_s = Game.COMBO_CANDIDATES[0][0]  # S1
        expected_combo_h = Game.COMBO_CANDIDATES[1][0]  # H1

        # レシピが2つ生成される
        # source_list = game._recipe.get_source_list()
        recipe = game.get_recipe()
        source_list = [src for src, _ in recipe]
        target_list = [tgt for _, tgt in recipe]
        self.assertEqual(len(source_list), 2)

        # レシピ1: expected_combo_s の検証
        combo_s_result, (combo_s_src1, _) = expected_combo_s.value
        self.assertEqual(len(source_list[0]), 2)
        self.assertTrue(all(card.symbol == combo_s_src1 for card in source_list[0]))
        self.assertEqual(target_list[0].symbol, combo_s_result)

        # レシピ2: expected_combo_h の検証
        combo_h_result, (combo_h_src1, combo_h_src2) = expected_combo_h.value
        self.assertEqual(len(source_list[1]), 2)
        self.assertEqual(source_list[1][0].symbol, combo_h_src1)
        self.assertEqual(source_list[1][1].symbol, combo_h_src2)
        self.assertEqual(target_list[1].symbol, combo_h_result)

    @patch("recipe.random.choice")
    def test_turn_resets_recipe(self, mock_choice):
        """turn()を呼び出すと、レシピがリセットされる"""
        # Game.__init__()用のモック（シンボルレシピ生成とカード配布）
        mock_choice.side_effect = lambda lst: lst[0]

        game = Game()

        # 1回目: Circleマークのレシピ
        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=[[Combo.S1, Combo.S2], [Combo.H1, Combo.H2]],
            devolved_flg=False,
        )
        expected_recipes = [
            ([Card(Symbol.B3), Card(Symbol.B3)], Card(Symbol.S1)),
            ([Card(Symbol.S1), Card(Symbol.S2)], Card(Symbol.H1)),
        ]
        self.assertEqual(expected_recipes, game.get_recipe())

        # 2回目: Triangleマークのレシピ（turn()でシャッフル）
        mock_choice.side_effect = lambda lst: lst[1]
        game.turn()

        expected_recipes = [
            ([Card(Symbol.B1), Card(Symbol.B3)], Card(Symbol.S2)),
            ([Card(Symbol.S4), Card(Symbol.S5)], Card(Symbol.H2)),
        ]
        self.assertEqual(expected_recipes, game.get_recipe())

    def test_is_recipe_executable(self):
        """is_recipe_executable()が正しくレシピの実行可能性を判定する"""
        test_cases = [
            (
                "レシピ0のみ実行可能",
                [Card(Symbol.B3), Card(Symbol.B3)],
                {0: True, 1: False},  # 期待される実行可能性
            ),
            (
                "レシピ1のみ実行可能",
                [Card(Symbol.B1), Card(Symbol.B3)],
                {0: False, 1: True},  # 期待される実行可能性
            ),
            (
                "両方のレシピが実行可能",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B1),
                ],
                {0: True, 1: True},  # 期待される実行可能性
            ),
            (
                "両方のレシピが実行不可能",
                [Card(Symbol.B3)],  # 手札: 2□のみ
                {0: False, 1: False},  # 期待される実行可能性
            ),
        ]

        for case_name, hand_cards, expected_results in test_cases:
            with self.subTest(case=case_name):
                game = Game()

                # 手札を設定
                game._hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.hand.add_card(card)

                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=[[Combo.S1], [Combo.S2]],
                    devolved_flg=False,
                )

                # 各レシピの実行可能性をテスト
                for recipe_index, expected_executable in expected_results.items():
                    actual_executable = game.is_recipe_executable(recipe_index)
                    self.assertEqual(
                        expected_executable,
                        actual_executable,
                        f"{case_name}: レシピ{recipe_index}の実行可能性が期待と異なります",
                    )

    def test_is_npc_recipe_executable(self):
        """is_npc_recipe_executable()が正しくレシピの実行可能性を判定する"""
        test_cases = [
            (
                "レシピ0のみ実行可能",
                [Card(Symbol.B3), Card(Symbol.B3)],
                {0: True, 1: False},  # 期待される実行可能性
            ),
            (
                "レシピ1のみ実行可能",
                [Card(Symbol.B1), Card(Symbol.B3)],
                {0: False, 1: True},  # 期待される実行可能性
            ),
            (
                "両方のレシピが実行可能",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B1),
                ],
                {0: True, 1: True},  # 期待される実行可能性
            ),
            (
                "両方のレシピが実行不可能",
                [Card(Symbol.B3)],  # 手札: 2□のみ
                {0: False, 1: False},  # 期待される実行可能性
            ),
        ]

        for case_name, hand_cards, expected_results in test_cases:
            with self.subTest(case=case_name):
                game = Game()

                # 手札を設定
                game._npc_hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.npc_hand.add_card(card)
                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=[[Combo.S1], [Combo.S2]],
                    devolved_flg=False,
                )

                # 各レシピの実行可能性をテスト
                for recipe_index, expected_executable in expected_results.items():
                    actual_executable = (
                        game._is_npc_recipe_executable(  # pylint: disable=W0212
                            recipe_index
                        )
                    )
                    self.assertEqual(
                        expected_executable,
                        actual_executable,
                        f"{case_name}: レシピ{recipe_index}の実行可能性が期待と異なります",
                    )

    def test_execute_recipe(self):
        """execute_recipe()が正しくレシピに従ったカード交換を行う（三角測量）"""
        test_cases = [
            (
                "レシピ0を実行",
                [Card(Symbol.B3), Card(Symbol.B3)],
                0,  # レシピインデックス
                [Card(Symbol.S1)],
            ),
            (
                "レシピ1を実行",
                [Card(Symbol.B1), Card(Symbol.B3)],
                1,  # レシピインデックス
                [Card(Symbol.S2)],  # 交換後の手札: 3△
            ),
            (
                "手札に複数のカードがある場合（残りのカードは保持される）",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B1),
                ],
                0,  # レシピインデックス
                [Card(Symbol.B1), Card(Symbol.S1)],
            ),
            (
                "手札に同じカードが3枚以上ある場合（2枚だけ消費される）",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                ],
                0,  # レシピインデックス
                [Card(Symbol.B3), Card(Symbol.S1)],
            ),
        ]

        for (
            case_name,
            hand_cards,
            recipe_index,
            expected_results,
        ) in test_cases:
            with self.subTest(case=case_name):
                game = Game()

                # 手札を設定
                game._hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.hand.add_card(card)

                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=[[Combo.S1], [Combo.S2]],
                    devolved_flg=False,
                )

                # レシピを実行
                game.execute_recipe(recipe_index)
                self.assertEqual(
                    expected_results,
                    game.hand.get_cards(),
                    f"{case_name}: レシピ{recipe_index}の実行結果が期待と異なります",
                )

    def test_execute_npc_recipe(self):
        """execute_npc_recipe()が正しくレシピに従ったカード交換を行う（三角測量）"""
        test_cases = [
            (
                "レシピ0を実行",
                [Card(Symbol.B3), Card(Symbol.B3)],
                [Card(Symbol.S1)],
            ),
            (
                "レシピ1を実行",
                [Card(Symbol.B1), Card(Symbol.B3)],
                [Card(Symbol.S2)],
            ),
            (
                "手札に複数のカードがある場合（残りのカードは保持される）",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B1),
                ],
                [Card(Symbol.B3), Card(Symbol.S2)],
            ),
            (
                "手札に同じカードが3枚以上ある場合（2枚だけ消費される）",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                ],
                [Card(Symbol.B3), Card(Symbol.S1)],
            ),
            (
                "実行可能なレシピがない場合は手札が変化しない",
                [Card(Symbol.S1), Card(Symbol.B3)],
                [Card(Symbol.S1), Card(Symbol.B3)],
            ),
            ("手札が空の場合は変化しない", [], []),
            (
                "手札に二つのレシピのカードがあれば、両方実行される",
                [
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                    Card(Symbol.B1),
                ],
                [Card(Symbol.S2), Card(Symbol.S1)],
            ),
        ]

        for (
            case_name,
            hand_cards,
            expected_results,
        ) in test_cases:
            with self.subTest(case=case_name):
                game = Game()

                # 手札を設定
                game._npc_hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.npc_hand.add_card(card)

                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=[[Combo.S1], [Combo.S2]],
                    devolved_flg=False,
                )

                # レシピを実行
                game.execute_npc_recipe()
                self.assertEqual(
                    expected_results,
                    game.npc_hand.get_cards(),
                    f"{case_name}: レシピの実行結果が期待と異なります",
                )

    @patch("recipe.random.choice")
    @patch("recipe.random.random")
    def test_execute_npc_recipe_with_idle_recipe(self, mock_random, mock_choice):
        """execute_npc_recipe()で待機対象レシピが優先的に実行される"""
        mock_choice.side_effect = lambda lst: lst[0]
        test_cases = [
            (
                "G1レシピが実行される",
                [Card(Symbol.H1), Card(Symbol.H3), Card(Symbol.H1)],
                [[Combo.G1, Combo.H1]],
                1,
                [Card(Symbol.H1), Card(Symbol.G1)],
            ),
            (
                "G1レシピ以外が実行されない",
                [Card(Symbol.H1), Card(Symbol.H3), Card(Symbol.H1)],
                [[Combo.G1, Combo.H1]],
                0,
                [Card(Symbol.H1), Card(Symbol.H3), Card(Symbol.H1)],
            ),
            (
                "G2レシピが実行される",
                [
                    Card(Symbol.H4),
                    Card(Symbol.H2),
                    Card(Symbol.H2),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                ],
                [[Combo.S1], [Combo.G2, Combo.H2]],
                1,
                [Card(Symbol.H2), Card(Symbol.G2), Card(Symbol.S1)],
            ),
            (
                "G2レシピ以外が実行されない",
                [
                    Card(Symbol.H4),
                    Card(Symbol.H2),
                    Card(Symbol.H2),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                ],
                [[Combo.S1], [Combo.G2, Combo.H2]],
                0,
                [
                    Card(Symbol.H4),
                    Card(Symbol.H2),
                    Card(Symbol.H2),
                    Card(Symbol.B3),
                    Card(Symbol.B3),
                ],
            ),
        ]
        for (
            case_name,
            hand_cards,
            combo_candidates,
            random_value,
            expected_results,
        ) in test_cases:
            with self.subTest(case=case_name):
                mock_random.return_value = random_value
                game = Game()

                # 手札を設定
                game._npc_hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.npc_hand.add_card(card)

                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=combo_candidates,
                    devolved_flg=True,
                )

                # レシピを実行
                game.execute_npc_recipe()
                self.assertEqual(
                    expected_results,
                    game.npc_hand.get_cards(),
                    f"{case_name}: レシピの実行結果が期待と異なります",
                )

    def test_has_npc_idle_recipe(self):
        """_has_npc_idle_recipe()でNPC手札に待機対象のレシピカードがあるか判定する"""
        test_cases = [
            ("ゴールレシピG1を持つ", [Card(Symbol.H1), Card(Symbol.H3)], True),
            ("ゴールレシピを持たない", [Card(Symbol.H1)], False),
            ("ゴールレシピG2を持つ", [Card(Symbol.H2), Card(Symbol.H4)], True),
            (
                "ゴールレシピG1とほかのカード",
                [Card(Symbol.H2), Card(Symbol.H1), Card(Symbol.H3)],
                True,
            ),
            ("ゴールレシピG2の襦袢違い", [Card(Symbol.H4), Card(Symbol.H2)], True),
            ("空の手札", [], False),
            (
                "ゴールレシピG1, G2の両方を持つ",
                [Card(Symbol.H1), Card(Symbol.H2), Card(Symbol.H3), Card(Symbol.H4)],
                True,
            ),
        ]

        for case_name, hand_cards, expected in test_cases:
            with self.subTest(case=case_name):
                game = Game()

                # 手札を設定
                game._npc_hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.npc_hand.add_card(card)

                # 待機対象レシピカードを持つか判定
                self.assertEqual(
                    expected,
                    game._has_npc_idle_recipe(),  # pylint: disable=W0212
                    f"{case_name}: 待機対象レシピカードの有無判定が期待と異なります",
                )

    def test_execute_recipe_raises_error_when_not_executable(self):
        """execute_recipe()が実行不可能な場合に例外を発生させる"""

        test_cases = [
            (
                "負数のレシピID",
                [Card(Symbol.B3), Card(Symbol.B3)],  # 手札
                -1,  # 無効なレシピID
            ),
            (
                "範囲外のレシピID（上限）",
                [Card(Symbol.B3), Card(Symbol.B3)],
                2,  # レシピは0,1の2個なので範囲外
            ),
            (
                "範囲外のレシピID（大きい値）",
                [Card(Symbol.B3), Card(Symbol.B3)],
                100,
            ),
            (
                "必要なカードが不足",
                [Card(Symbol.B3)],
                0,  # 手札が不足しているため実行不可能
            ),
        ]

        for case_name, hand_cards, recipe_index in test_cases:
            with self.subTest(case=case_name):
                game = Game()
                game._hand = Hand()  # pylint: disable=W0212
                for card in hand_cards:
                    game.hand.add_card(card)

                game._recipe = Recipe(  # pylint: disable=W0212
                    combo_candidates=[[Combo.S1], [Combo.S2]],
                    devolved_flg=False,
                )

                with self.assertRaises(
                    ValueError, msg=f"{case_name}: ValueErrorが発生すべき"
                ):
                    game.execute_recipe(recipe_index)

    def test_execute_recipe_multiple_times(self):
        """execute_recipe()を複数回実行した場合の状態変化を確認"""
        game = Game()
        game._hand = Hand()  # pylint: disable=W0212
        for _ in range(4):
            game.hand.add_card(Card(Symbol.B3))

        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=[[Combo.S1], [Combo.S2]],
            devolved_flg=False,
        )

        # 1回目の実行:
        game.execute_recipe(0)
        self.assertEqual(
            [Card(Symbol.B3), Card(Symbol.B3), Card(Symbol.S1)],
            game.hand.get_cards(),
            "1回目の実行後の手札が期待と異なる",
        )

        # 2回目の実行:
        game.execute_recipe(0)
        self.assertEqual(
            [Card(Symbol.S1), Card(Symbol.S1)],
            game.hand.get_cards(),
            "2回目の実行後の手札が期待と異なる",
        )


class TestGameSymbolRecipe(unittest.TestCase):
    """シンボルベース交換処理のテスト"""

    def test_execute_recipe_with_symbols(self):
        """シンボルベースでレシピ交換が実行される"""
        game = Game()
        game._hand = Hand()  # pylint: disable=W0212

        # シンボルレシピを設定（S1レシピ: B3 + B3 → S1）
        combo_candidates = [[Combo.S1]]
        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=combo_candidates,
            devolved_flg=False,
        )

        # 手札に B3 を 2 枚追加
        game.hand.add_card(Card(Symbol.B3))
        game.hand.add_card(Card(Symbol.B3))

        # 実行可能なレシピIDを取得
        executable_ids = (
            game._recipe.get_executable_recipe_ids(  # pylint: disable=W0212
                game.hand.get_cards()
            )
        )
        self.assertEqual([0], executable_ids, "B3を2枚持つのでレシピ0が実行可能")

        # レシピ実行
        game.execute_recipe(executable_ids[0])

        # 交換後、手札に S1 Symbol を持つカードが追加される
        cards = game.hand.get_cards()
        self.assertTrue(
            any(card.symbol == Symbol.S1 for card in cards),
            "交換後の手札にS1シンボルを持つカードが存在する",
        )

        # 交換後、B3 が 2 枚削除される
        b3_count = sum(1 for card in cards if card.symbol == Symbol.B3)
        self.assertEqual(0, b3_count, "交換後、B3が2枚削除されている")


class TestNPCPlay(unittest.TestCase):
    """NPCのプレイ動作に関するテスト"""

    @patch("game.random.choice")
    def test_npc_auto_exchange(self, mock_game_choice):
        """NPCの手札が自動で交換される"""
        mock_game_choice.side_effect = lambda lst: lst[0]
        game = Game()

        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=[[Combo.S3]],
            devolved_flg=False,
        )

        for _ in range(2):
            game.turn()

        self.assertEqual(
            [Card(Symbol.B1) for _ in range(3)],
            game.hand.get_cards(),
            "プレイヤー: 想定した手札になっていません",
        )
        self.assertEqual(
            [Card(Symbol.S3), Card(Symbol.B1)],
            game.npc_hand.get_cards(),
            "NPC: 想定した手札になっていません",
        )


if __name__ == "__main__":
    unittest.main()
