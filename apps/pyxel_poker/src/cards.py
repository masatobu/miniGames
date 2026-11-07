"""カード・山・プレイヤー・配札（Pyxel に依存しないゲームのロジック）。"""

import random
from dataclasses import dataclass

# 強さの順は spade > heart > diamond > club（役の比較で使う）
SUITS = ("spade", "heart", "diamond", "club")
# 数字は 2..10、11=J、12=Q、13=K、14=A。数値の大小が強さの順と一致する
RANKS = tuple(range(2, 15))
# プレイヤーの順（画面の上から下）
PLAYER_KINDS = ("com", "com", "com", "human")
HAND_SIZE = 5
INITIAL_COINS = 10


@dataclass(frozen=True)
class Card:
    """52 枚のうちの 1 枚。数字とマークの組で一意に決まる値。"""

    rank: int
    suit: str


class Deck:
    """ゲームごとに作る山。先頭から引く。"""

    def __init__(self, cards):
        self.cards = cards

    @classmethod
    def create(cls, seed=None):
        """52 枚の山を作ってシャッフルする。seed を指定すると並びを再現できる。"""
        cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        random.Random(seed).shuffle(cards)
        return cls(cards)

    def draw(self, count=1):
        """先頭から count 枚を引いて返す（山は減る）。"""
        drawn = self.cards[:count]
        del self.cards[:count]
        return drawn


class Player:
    """ゲームの参加者（human または com）。"""

    def __init__(self, kind):
        self.kind = kind
        self.coins = INITIAL_COINS
        # 破産したら True。新しいセッションまで戻らない（reset_for_new_game でも保つ）
        self.bankrupt = False
        self.hand = []
        self.hand_public = False
        self.selected = set()
        # 交換は 1 ゲームに 1 回。new_indices は直前の交換で新しく引いた手札の位置
        self.exchanged = False
        self.new_indices = set()

    def reset_for_new_game(self):
        """次のゲームのために、手札・公開・選択・交換の状態を初期化する。所持コイン・kind・破産は保つ。"""
        self.hand = []
        self.hand_public = False
        self.selected = set()
        self.exchanged = False
        self.new_indices = set()

    def toggle_selected(self, index):
        """手札の位置 index の選択と解除を切り替える。COM・交換済み・範囲外の位置は無視する。"""
        if self.kind != "human" or self.exchanged or not 0 <= index < HAND_SIZE:
            return
        self.selected ^= {index}

    def selected_indices(self):
        """選択中の位置を昇順で返す。"""
        return sorted(self.selected)


class Table:
    """1 ゲームの配札の状態。4 人のプレイヤーと山をまとめる。"""

    def __init__(self, players, deck):
        self.players = players
        self.deck = deck

    @classmethod
    def deal(cls, seed=None, players=None):
        """山を作り、プレイヤーの順に 5 枚ずつ配って全員の手札を公開する。

        players を渡すと新しい人を作らず、その人たちの状態を初期化して配り直す（所持コインは保つ）。
        破産者には配らず、手札は空で非公開のままにする。
        """
        deck = Deck.create(seed)
        if players is None:
            players = [Player(kind) for kind in PLAYER_KINDS]
        for player in players:
            player.reset_for_new_game()
            if player.bankrupt:
                continue
            player.hand = deck.draw(HAND_SIZE)
            player.hand_public = True
        return cls(players, deck)

    def exchange(self):
        """人間の選択中のカードを、山札の先頭から引いたカードと入れ替える（1 ゲームに 1 回）。

        0 枚選択でも交換済みになる。引いた位置は new_indices に残り、選択は解除される。
        """
        human = next(p for p in self.players if p.kind == "human")
        if human.exchanged:
            return
        indices = human.selected_indices()
        for index, card in zip(indices, self.deck.draw(len(indices))):
            human.hand[index] = card
        human.new_indices = set(indices)
        human.selected = set()
        human.exchanged = True
