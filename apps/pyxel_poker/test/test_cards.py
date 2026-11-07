import unittest
from src.cards import Deck, Player, Table

SUITS = {"spade", "heart", "diamond", "club"}
RANKS = set(range(2, 15))  # 2..10, 11=J, 12=Q, 13=K, 14=A

PLAYER_COUNT = 4
HAND_SIZE = 5
DECK_SIZE = len(SUITS) * len(RANKS)  # 4 * 13 = 52
DEALT = PLAYER_COUNT * HAND_SIZE  # 4 * 5 = 20
REMAINING = DECK_SIZE - DEALT  # 52 - 20 = 32
INITIAL_COINS = 10


def keys(cards):
    return [(card.rank, card.suit) for card in cards]


class TestDeck(unittest.TestCase):
    def test_deck_has_52_unique_cards(self):
        # FR1.1 / BR1.1: 4 マーク × 13 数字が 1 枚ずつ、重複なし
        deck = Deck.create(seed=0)
        self.assertEqual(len(deck.cards), DECK_SIZE)
        self.assertEqual(len(set(keys(deck.cards))), DECK_SIZE)
        self.assertEqual({c.suit for c in deck.cards}, SUITS)
        self.assertEqual({c.rank for c in deck.cards}, RANKS)

    def test_shuffle_is_reproducible_by_seed(self):
        # FR1.1 / BR1.2: 同じ種なら同じ並び、違う種なら並びが変わる
        same_a = keys(Deck.create(seed=0).cards)
        same_b = keys(Deck.create(seed=0).cards)
        other = keys(Deck.create(seed=1).cards)
        self.assertEqual(same_a, same_b)
        self.assertNotEqual(same_a, other)


class TestDeal(unittest.TestCase):
    def test_player_order_is_com_com_com_human(self):
        # FR1.2 / BR1.3: 画面の上から COM1・COM2・COM3・人間
        table = Table.deal(seed=0)
        kinds = [p.kind for p in table.players]
        self.assertEqual(kinds, ["com", "com", "com", "human"])

    def test_deal_five_cards_each_without_duplicates(self):
        # FR1.2 / BR1.3: 4 人に 5 枚ずつ（20 枚）、重複なし、山の残りは 32 枚
        table = Table.deal(seed=0)
        for player in table.players:
            self.assertEqual(len(player.hand), HAND_SIZE)
        dealt = [c for p in table.players for c in p.hand]
        self.assertEqual(len(dealt), DEALT)
        self.assertEqual(len(set(keys(dealt))), DEALT)
        self.assertEqual(len(table.deck.cards), REMAINING)
        self.assertEqual(len(set(keys(dealt + table.deck.cards))), DECK_SIZE)

    def test_hands_are_public_after_deal(self):
        # FR1.3 / BR1.4: 配札直後は全員の手札が公開
        table = Table.deal(seed=0)
        self.assertEqual(len(table.players), PLAYER_COUNT)
        self.assertTrue(all(p.hand_public for p in table.players))

    def test_initial_coins_are_10(self):
        # FR1.4 / BR1.5: 所持コインの初期値は 10
        table = Table.deal(seed=0)
        self.assertEqual([p.coins for p in table.players], [INITIAL_COINS] * 4)


class TestSelection(unittest.TestCase):
    def setUp(self):
        self.human = Table.deal(seed=0).players[3]

    def test_toggle_selects_then_deselects(self):
        # FR1.1 / BR1.1: 1 回で選択、もう 1 回で解除
        self.human.toggle_selected(2)
        self.assertEqual([2], self.human.selected_indices())
        self.human.toggle_selected(2)
        self.assertEqual([], self.human.selected_indices())

    def test_out_of_range_index_is_ignored(self):
        # FR1.2 / BR1.2: 有効な位置は 0..HAND_SIZE-1。範囲外は状態を変えない
        self.human.toggle_selected(1)
        for index in (-1, HAND_SIZE):
            self.human.toggle_selected(index)
        self.assertEqual([1], self.human.selected_indices())

    def test_com_cannot_select(self):
        # FR1.4 / BR1.3: COM の手札は選択できない
        com = Table.deal(seed=0).players[0]
        com.toggle_selected(0)
        self.assertEqual([], com.selected_indices())

    def test_no_selection_right_after_deal(self):
        # BR1.5: 配札直後は全員が何も選択していない
        table = Table.deal(seed=0)
        self.assertEqual(
            [[]] * PLAYER_COUNT, [p.selected_indices() for p in table.players]
        )

    def test_selected_indices_are_in_hand_order(self):
        # FR1.1: 複数選択でき、位置の昇順で返る
        for index in (4, 0, 2):
            self.human.toggle_selected(index)
        self.assertEqual([0, 2, 4], self.human.selected_indices())


class TestExchange(unittest.TestCase):
    SELECTED = (1, 3)

    def setUp(self):
        self.table = Table.deal(seed=0)
        self.human = self.table.players[3]
        # 引くカード = 配札直後の山札の先頭から k 枚
        self.expected_drawn = list(self.table.deck.cards[: len(self.SELECTED)])
        self.hand_before = list(self.human.hand)

    def select(self, indices):
        for index in indices:
            self.human.toggle_selected(index)

    def test_exchange_replaces_selected_with_deck_top(self):
        # FR2.1 / BR2.1: 選択中の位置に、山札の先頭から引いたカードが昇順に入る
        self.select(self.SELECTED)
        self.table.exchange()
        for n, index in enumerate(self.SELECTED):
            self.assertEqual(self.expected_drawn[n], self.human.hand[index])
        for index in set(range(HAND_SIZE)) - set(self.SELECTED):
            self.assertEqual(self.hand_before[index], self.human.hand[index])
        self.assertEqual(set(self.SELECTED), self.human.new_indices)

    def test_exchange_shrinks_deck_without_duplicates(self):
        # FR2.2 / BR2.2: 山札は k 枚減り、外したカードは戻らず、重複しない
        k = len(self.SELECTED)
        self.select(self.SELECTED)
        self.table.exchange()
        self.assertEqual(DECK_SIZE - DEALT - k, len(self.table.deck.cards))
        in_play = [c for p in self.table.players for c in p.hand]
        self.assertEqual(
            len(set(keys(in_play + self.table.deck.cards))),
            len(in_play) + len(self.table.deck.cards),
        )
        removed = [self.hand_before[i] for i in self.SELECTED]
        for card in removed:
            self.assertNotIn(card, self.table.deck.cards)

    def test_exchange_is_once_per_game_even_with_zero_selected(self):
        # FR2.3 / BR2.3: 0 枚選択でも交換済みになり、山札と手札は変わらない
        self.table.exchange()
        self.assertTrue(self.human.exchanged)
        self.assertEqual(self.hand_before, self.human.hand)
        self.assertEqual(REMAINING, len(self.table.deck.cards))
        self.assertEqual(set(), self.human.new_indices)

    def test_cannot_select_or_exchange_after_exchange(self):
        # FR2.3 / BR2.3: 交換後は選択も 2 回目の交換もできない
        self.select(self.SELECTED)
        self.table.exchange()
        hand_after = list(self.human.hand)
        self.human.toggle_selected(0)
        self.assertEqual([], self.human.selected_indices())
        self.table.exchange()
        self.assertEqual(hand_after, self.human.hand)
        self.assertEqual(set(self.SELECTED), self.human.new_indices)
        self.assertEqual(
            DECK_SIZE - DEALT - len(self.SELECTED), len(self.table.deck.cards)
        )

    def test_exchange_does_not_change_coins(self):
        # FR2.4 / BR2.4: コインは動かない
        self.select(self.SELECTED)
        self.table.exchange()
        self.assertEqual(
            [INITIAL_COINS] * PLAYER_COUNT, [p.coins for p in self.table.players]
        )

    def test_exchange_clears_selection_and_keeps_com(self):
        # FR3.1 / BR2.5: 選択は解除され、COM の手札と公開の状態は変わらない
        coms = self.table.players[:3]
        com_hands = [list(p.hand) for p in coms]
        self.select(self.SELECTED)
        self.table.exchange()
        self.assertEqual([], self.human.selected_indices())
        self.assertEqual(com_hands, [p.hand for p in coms])
        self.assertTrue(all(p.hand_public for p in self.table.players))
        self.assertTrue(all(not p.exchanged and not p.new_indices for p in coms))


class TestNewGame(unittest.TestCase):
    def test_reset_clears_game_state_and_keeps_coins_and_kind(self):
        # FR7.3: 手札・公開・選択・交換の状態は初期状態に戻り、所持コインと kind は保つ
        table = Table.deal(seed=0)
        human = table.players[3]
        human.toggle_selected(1)
        table.exchange()
        human.selected = {2}
        human.coins = 7
        human.reset_for_new_game()
        self.assertEqual([], human.hand)
        self.assertFalse(human.hand_public)
        self.assertEqual(set(), human.selected)
        self.assertFalse(human.exchanged)
        self.assertEqual(set(), human.new_indices)
        self.assertEqual(7, human.coins)
        self.assertEqual("human", human.kind)

    def test_deal_with_players_redeals_and_keeps_coins(self):
        # FR7.2: 渡した人たちに新しい山で配り直し、所持コインを保つ
        old = Table.deal(seed=0)
        for coin, player in enumerate(old.players):
            player.coins = coin + 3  # 3, 4, 5, 6 と人ごとに変えて取り違えを検出する
        old.players[3].toggle_selected(0)
        old.exchange()
        new = Table.deal(seed=1, players=old.players)
        self.assertIs(old.players, new.players)
        self.assertEqual([3, 4, 5, 6], [p.coins for p in new.players])
        self.assertEqual(
            keys(Table.deal(seed=1).players[3].hand), keys(new.players[3].hand)
        )
        self.assertEqual(len(Deck.create(seed=1).cards) - DEALT, len(new.deck.cards))
        for player in new.players:
            self.assertEqual(HAND_SIZE, len(player.hand))
            self.assertTrue(player.hand_public)
            self.assertFalse(player.exchanged)
            self.assertEqual(set(), player.selected)
            self.assertEqual(set(), player.new_indices)

    def test_deal_without_players_creates_fresh_players(self):
        # FR7.2: players なしの Table.deal(seed) は従来どおり新しい 4 人（所持コイン 10）
        table = Table.deal(seed=0)
        self.assertEqual(
            [INITIAL_COINS] * PLAYER_COUNT, [p.coins for p in table.players]
        )
        self.assertTrue(all(isinstance(p, Player) for p in table.players))


if __name__ == "__main__":
    unittest.main()
