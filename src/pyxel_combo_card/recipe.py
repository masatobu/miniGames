from enum import Enum
import random
from card import Card, Symbol


class Combo(Enum):
    S1 = (Symbol.S1, (Symbol.B3, Symbol.B3))
    S2 = (Symbol.S2, (Symbol.B1, Symbol.B3))
    S3 = (Symbol.S3, (Symbol.B1, Symbol.B1))
    S4 = (Symbol.S4, (Symbol.B2, Symbol.B2))
    S5 = (Symbol.S5, (Symbol.B2, Symbol.B3))
    H1 = (Symbol.H1, (Symbol.S1, Symbol.S2))
    H2 = (Symbol.H2, (Symbol.S4, Symbol.S5))
    H3 = (Symbol.H3, (Symbol.S2, Symbol.S3))
    H4 = (Symbol.H4, (Symbol.S1, Symbol.S4))
    G1 = (Symbol.G1, (Symbol.H1, Symbol.H3))
    G2 = (Symbol.G2, (Symbol.H2, Symbol.H4))


class Recipe:
    def __init__(
        self,
        combo_candidates: list[list[Combo]] | None = None,
        devolved_flg: bool = True,
    ) -> None:
        self._combo_candidates = combo_candidates
        self._source = []
        self._target = []
        self._devolved_flg = devolved_flg
        self.shuffle()

    def shuffle(self) -> None:
        self._source = []
        self._target = []
        devolved_source_set = self._get_devolved_source_set()
        devolved_target_set = self._get_devolved_target_set()
        for i, combo_list in enumerate(self._combo_candidates):
            if (
                self._devolved_flg
                and random.random() < 1 / (len(combo_list) + 1)
                and devolved_source_set[i]
                and devolved_target_set[i]
            ):
                self._add_devolved_recipe(devolved_source_set, devolved_target_set, i)
                continue
            combo = random.choice(combo_list)
            self._add_combo_recipe(combo)

    def _add_devolved_recipe(self, developed_source_set, developed_target_set, i):
        source_cards = list(random.choice(list(developed_source_set[i])))
        target_card = random.choice(list(developed_target_set[i]))
        self._source.append(source_cards)
        self._target.append(target_card)

    def get_source_list(self) -> list[list[Card]]:
        return self._source

    def get_target(self, recipe_id: int) -> Card:
        return self._target[recipe_id]

    def _get_devolved_source_set(self) -> list[set[tuple[Card]]]:
        result = []
        for combo_list in self._combo_candidates:
            source_seed_set = {
                combo.value[0]
                for combo in combo_list
                if not Symbol.is_goal(combo.value[0])
            }
            source_symbol_set = set()
            sorted_source_seed_list = sorted(source_seed_set, key=lambda s: s.value)
            for source_seed_1 in sorted_source_seed_list:
                for source_seed_2 in sorted_source_seed_list:
                    if source_symbol_set.isdisjoint(
                        {(source_seed_1, source_seed_2), (source_seed_2, source_seed_1)}
                    ):
                        source_symbol_set.add((source_seed_1, source_seed_2))
            source_set = {
                tuple(Card(sym) for sym in source_syms)
                for source_syms in source_symbol_set
            }
            result.append(source_set)
        return result

    def _get_devolved_target_set(self) -> list[set[Card]]:
        result = []
        for combo_list in self._combo_candidates:
            target_symbols_list = [
                list(combo.value[1])
                for combo in combo_list
                if not Symbol.is_goal(combo.value[0])
            ]
            target_symbols = [
                item for sublist in target_symbols_list for item in sublist
            ]
            result.append({Card(sym) for sym in target_symbols})
        return result

    def _add_combo_recipe(self, combo: Combo) -> None:
        """Combo から source と target を生成して追加する（内部ヘルパー関数）"""
        result_symbol, (source1, source2) = combo.value
        # シンボルでCardを作成
        source_cards = [Card(source1), Card(source2)]
        target_card = Card(result_symbol)
        # self._source と self._target に直接追加
        self._source.append(source_cards)
        self._target.append(target_card)

    def get_executable_recipe_ids(self, hand_cards: list[Card]) -> list[int]:
        executable_ids = []
        for recipe_id, source_cards in enumerate(self._source):
            if self.can_execute(hand_cards, source_cards):
                executable_ids.append(recipe_id)
        return executable_ids

    @classmethod
    def can_execute(cls, hand_cards: list[Card], required_cards: list[Card]) -> bool:
        """シンボルベースでカード照合"""
        hand_card_counts = {}
        for card in hand_cards:
            key = card.symbol
            hand_card_counts[key] = hand_card_counts.get(key, 0) + 1

        for req_card in required_cards:
            key = req_card.symbol
            if hand_card_counts.get(key, 0) <= 0:
                return False
            hand_card_counts[key] -= 1

        return True

    def __repr__(self) -> str:
        return f"Recipe(source={self._source}, target={self._target})"
