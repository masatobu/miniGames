import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from hand import Hand  # pylint: disable=C0413
from card import Card, Symbol  # pylint: disable=C0413


class TestHandInitialState(unittest.TestCase):
    def test_hand_starts_empty(self):
        """Hand初期化時は空の手札が作成される"""
        hand = Hand()
        cards = hand.get_cards()
        self.assertEqual(0, len(cards))


class TestHandCardDistribution(unittest.TestCase):
    def test_hand_can_receive_card_from_stack(self):
        """手札にカードを追加できる"""
        test_cases = [
            ("symbol B1 single", Symbol.B1, 1),
            ("symbol B2 single", Symbol.B2, 1),
            ("symbol B3 single", Symbol.B3, 1),
            ("symbol B1 multiple", Symbol.B1, 3),
            ("symbol B2 multiple", Symbol.B2, 2),
        ]
        for case_name, card_symbol, add_count in test_cases:
            with self.subTest(case=case_name, symbol=card_symbol, count=add_count):
                hand = Hand()

                for _ in range(add_count):
                    card = Card(card_symbol)
                    hand.add_card(card)

                cards = hand.get_cards()
                self.assertEqual(add_count, len(cards))
                self.assertEqual(card_symbol, cards[-1].symbol)


class TestFindCardIndices(unittest.TestCase):
    def test_find_card_indices(self):
        """手札のカードのインデックスを検索できる"""
        test_cases = [
            ("single", [Card(Symbol.B1)], [Card(Symbol.B1)], [0]),
            (
                "double",
                [Card(Symbol.B1), Card(Symbol.B1)],
                [Card(Symbol.B1), Card(Symbol.B1)],
                [0, 1],
            ),
            (
                "mixed",
                [
                    Card(Symbol.B1),
                    Card(Symbol.B2),
                    Card(Symbol.B1),
                    Card(Symbol.B3),
                ],
                [Card(Symbol.B1), Card(Symbol.B3)],
                [0, 3],
            ),
        ]
        for case_name, hand_cards, target_cards, expected_result in test_cases:
            with self.subTest(
                case=case_name,
                hand_cards=hand_cards,
                target_cards=target_cards,
                expected_result=expected_result,
            ):
                hand = Hand()

                for card in hand_cards:
                    hand.add_card(card)

                index = hand.find_card_indices(target_cards)
                self.assertEqual(expected_result, index)

    def test_find_card_indices_raises_value_error_when_card_not_in_hand(self):
        """手札に存在しないカードのインデックスを検索するとValueErrorが発生する"""
        hand = Hand()
        hand.add_card(Card(Symbol.B1))
        hand.add_card(Card(Symbol.B2))

        target_cards = [Card(Symbol.B3)]  # 手札に存在しないカード

        with self.assertRaises(ValueError):
            hand.find_card_indices(target_cards)


class TestRemoveCardAtIndex(unittest.TestCase):
    def test_remove_card_at_index(self):
        """指定されたインデックスのカードが削除される"""
        test_cases = [
            (
                "remove first",
                [Card(Symbol.B1), Card(Symbol.B2)],
                0,
                [Card(Symbol.B2)],
            ),
            (
                "remove last",
                [Card(Symbol.B1), Card(Symbol.B2)],
                1,
                [Card(Symbol.B1)],
            ),
            (
                "remove middle",
                [Card(Symbol.B1), Card(Symbol.B2), Card(Symbol.B3)],
                1,
                [Card(Symbol.B1), Card(Symbol.B3)],
            ),
        ]
        for case_name, hand_cards, remove_index, expected_result in test_cases:
            with self.subTest(case=case_name):
                hand = Hand()
                for card in hand_cards:
                    hand.add_card(card)

                hand.remove_card_at_index(remove_index)
                self.assertEqual(expected_result, hand.get_cards())

    def test_remove_card_at_index_raises_index_error_when_out_of_range(self):
        """範囲外のインデックスを指定するとIndexErrorが発生する"""
        hand = Hand()
        hand.add_card(Card(Symbol.B1))

        with self.assertRaises(IndexError):
            hand.remove_card_at_index(1)


if __name__ == "__main__":
    unittest.main()
