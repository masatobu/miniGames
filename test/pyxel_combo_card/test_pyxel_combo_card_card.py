"""カードのテスト

要件:
- カードはランク（1, 2, 3）を持つ
- カードはマーク（Mark型）を持つ
"""

import sys
import os
import unittest

for p in ["../../src/pyxel_combo_card", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from card import Card, Symbol  # pylint: disable=C0413


class TestCard(unittest.TestCase):
    def test_card_with_symbol(self):
        """カードはシンボル属性を持つ"""
        test_cases = [
            ("B1", Symbol.B1),
            ("S1", Symbol.S1),
            ("H1", Symbol.H1),
            ("G1", Symbol.G1),
        ]
        for case_name, symbol in test_cases:
            with self.subTest(case_name=case_name, symbol=symbol):
                card = Card(symbol)
                self.assertEqual(card.symbol, symbol)


class TestCardHasGoalSymbol(unittest.TestCase):
    """Card.has_goal_symbol()のテスト（ID-029: TASK-029-4 リファクタリング）"""

    def test_has_goal_symbol_returns_true_for_g1(self):
        """G1シンボルのカードはゴールシンボルを持つ"""
        card = Card(Symbol.G1)
        self.assertTrue(card.has_goal_symbol())

    def test_has_goal_symbol_returns_true_for_g2(self):
        """G2シンボルのカードはゴールシンボルを持つ"""
        card = Card(Symbol.G2)
        self.assertTrue(card.has_goal_symbol())

    def test_has_goal_symbol_returns_false_for_non_goal_symbols(self):
        """非ゴールシンボル（B1, S1, H1など）はFalseを返す"""
        non_goal_symbols = [
            Symbol.B1, Symbol.B2, Symbol.B3,
            Symbol.S1, Symbol.S2, Symbol.S3, Symbol.S4, Symbol.S5,
            Symbol.H1, Symbol.H2, Symbol.H3, Symbol.H4,
        ]
        for symbol in non_goal_symbols:
            with self.subTest(symbol=symbol.name):
                card = Card(symbol)
                self.assertFalse(
                    card.has_goal_symbol(),
                    f"{symbol.name}はゴールシンボルではないのでFalseを返すべき"
                )
