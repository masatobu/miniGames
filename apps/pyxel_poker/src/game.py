"""ゲームの段階の遷移（Pyxel に依存しないゲームのロジック。乱数は配札の種だけで決まる）。"""

from collections import Counter

try:
    from .cards import Table  # pylint: disable=C0413
    from .hands import HandCategory, evaluate_hand, find_winner  # pylint: disable=C0413
    from .pot import ENTRY_FEE, MAX_PAYMENT, Pot, raise_cost  # pylint: disable=C0413
except ImportError:
    from cards import Table  # pylint: disable=C0413
    from hands import HandCategory, evaluate_hand, find_winner  # pylint: disable=C0413
    from pot import ENTRY_FEE, MAX_PAYMENT, Pot, raise_cost  # pylint: disable=C0413


class Phase:
    """1 ゲームの段階。順に進み、戻らない。"""

    FIRST_DECISION = "first"
    SECOND_DECISION = "second"
    FINISHED = "finished"


class Action:
    """判断の選択。"""

    DROP = "drop"
    RAISE = "raise"


# COM がレイズする役の下限。これ以上の役ならレイズし、これより弱い（ハイカード）ならドロップする
RAISE_THRESHOLD = HandCategory.ONE_PAIR


def com_decision(hand):
    """手札の役の区分だけで COM の選択（Action）を決める。乱数は使わず、同じ手札なら同じ結果。"""
    if evaluate_hand(hand) >= RAISE_THRESHOLD:
        return Action.RAISE
    return Action.DROP


# 役が完成しているので、COM が交換しない役の区分
COMPLETE_CATEGORIES = frozenset(
    {
        HandCategory.STRAIGHT,
        HandCategory.FLUSH,
        HandCategory.FULL_HOUSE,
        HandCategory.STRAIGHT_FLUSH,
        HandCategory.ROYAL_STRAIGHT_FLUSH,
    }
)


def com_exchange_indices(hand):
    """COM が交換する手札の位置を昇順で返す。役の区分と手札だけで決まり、乱数は使わない。

    完成した役（ストレート以上のうちフォーカードを除く）は交換しない。ペア・スリーカード・
    フォーカードの組は残し、それ以外を交換する（ハイカードは全 5 枚）。
    """
    if evaluate_hand(hand) in COMPLETE_CATEGORIES:
        return []
    counts = Counter(card.rank for card in hand)
    return [i for i, card in enumerate(hand) if counts[card.rank] == 1]


# 段階ごとの判断の回の番号。レイズの追加額（raise_cost）の引数になる
ROUND_NUMBERS = {Phase.FIRST_DECISION: 1, Phase.SECOND_DECISION: 2}


class Game:
    """1 ゲームの進行。配札済みの Table とゲームをまたぐ Pot を使い、段階と各プレイヤーの状態を持つ。

    位置はすべて table.players の添字（0 始まり）。人間は kind == "human" の 1 人。
    手札の交換（Table.exchange）は呼ばない。
    """

    def __init__(self, table, pot):
        self.table = table
        self.pot = pot
        self.phase = Phase.FIRST_DECISION
        # 勝負に残っている位置。開始時は破産者以外の全員、2 回目へ進むときは 1 回目にレイズした人だけ
        self.active = list(range(len(table.players)))
        self.dropped = set()
        # 勝者の位置。全員ドロップで勝者がいないときは None のまま
        self.winner = None
        # 勝者が受け取ったポットの額。勝者が決まるまで（全員ドロップを含む）は 0
        self.awarded = 0

    @classmethod
    def start(cls, seed=None, pot=None, players=None):
        """破産を判定し、配札し、参加者が参加費を払って 1 回目の判断を始める。

        pot を渡すと前のゲームから引き継いだポットを使う。players を渡すと新しい人を作らず、
        その人たちに配り直す（所持コインを保つ）。開始時に所持コインが MAX_PAYMENT 未満の人は
        参加費より前に破産とし、以降は戻さない。破産者は参加費を払わず、配札されず、
        勝負に残る位置（active）にもドロップ（dropped）にも含まれない。
        """
        if players is not None:
            # 判定は参加費の前。一度破産した人は戻らない（所持コインは変えない）
            for player in players:
                player.bankrupt = player.bankrupt or player.coins < MAX_PAYMENT
        game = cls(Table.deal(seed, players), pot if pot is not None else Pot())
        game.active = [i for i, p in enumerate(game.table.players) if not p.bankrupt]
        for index in game.active:
            game.pot.pay(game.table.players[index], ENTRY_FEE)
        return game

    def next_game(self, seed=None):
        """今のゲームの人たちとポットを引き継いで、新しい山で次のゲームを始める（参加費を払う）。

        勝者がポットを受け取った後のポットは 0、全員ドロップのときは残った額が次のゲームに加わる。
        終了していないゲームでは ValueError にする。
        """
        if self.phase != Phase.FINISHED:
            raise ValueError("ゲームは終了していない")
        return self.start(seed, self.pot, self.table.players)

    @classmethod
    def new_session(cls, seed=None):
        """新しいセッションの 1 ゲーム目を始める。前のセッションの人・ポットは引き継がない。

        全員が初期の所持コイン・破産なしの新しいプレイヤーで、ポットも新しい（参加費を払った後の状態）。
        """
        return cls.start(seed)

    def session_result(self):
        """セッションの結果。"lose"（人間が破産）、"win"（COM が全員破産）、続くなら None。

        破産の状態だけから決め、ゲームの段階には依存しない。全員が破産のときは人間の破産を優先する。
        """
        players = self.table.players
        if players[self.human_index].bankrupt:
            return "lose"
        if all(p.bankrupt for p in players if p.kind != "human"):
            return "win"
        return None

    @property
    def human_index(self):
        """人間の位置。"""
        return next(i for i, p in enumerate(self.table.players) if p.kind == "human")

    def com_action(self, index):
        """位置 index の COM の選択。その COM 自身の今の手札で com_decision が決める。

        テストが COM の選択を固定できるよう、サブクラスや属性の差し替えで上書きできる。
        """
        return com_decision(self.table.players[index].hand)

    def human_decides(self):
        """今の回の決める人に人間が含まれるか。終了後は含まれない。"""
        return self.phase != Phase.FINISHED and self.human_index in self.active

    def decide(self, human_action=None):
        """今の回の判断を反映する。人間が決める人なら human_action（drop／raise）が要る。

        決める人の選択を先にすべて集めてから、一斉に支払いとドロップを反映する。
        反映後の次の回に人間が決める人として含まれなければ、選択を待たずに同じ呼び出しの中で
        続けて進める（人間がドロップした後など）。不正な操作は何も変えずに ValueError にする。
        """
        self._validate(human_action)
        while self.phase != Phase.FINISHED:
            self._apply_round(human_action)
            human_action = None
            if self.human_decides():
                break

    def _validate(self, human_action):
        """決める人と人間の選択の組み合わせが正しいか確かめ、誤りなら ValueError にする。"""
        if self.phase == Phase.FINISHED:
            raise ValueError("ゲームは終了している")
        if self.human_decides():
            if human_action not in (Action.DROP, Action.RAISE):
                raise ValueError(f"人間の選択は drop か raise: {human_action}")
        elif human_action is not None:
            raise ValueError("人間は今の回の決める人ではない")

    def _apply_round(self, human_action):
        """今の回の選択を集め、一斉に反映して、次の段階または勝敗へ進める。"""
        round_number = ROUND_NUMBERS[self.phase]
        human_index = self.human_index
        choices = {
            index: human_action if index == human_index else self.com_action(index)
            for index in self.active
        }
        raisers = []
        for index, action in choices.items():
            if action == Action.RAISE:
                self.pot.pay(self.table.players[index], raise_cost(round_number))
                raisers.append(index)
            else:
                self.dropped.add(index)
        self.active = raisers
        if len(raisers) >= 2 and round_number == 1:
            self._exchange_coms()
            self.phase = Phase.SECOND_DECISION
            return
        self.phase = Phase.FINISHED
        if round_number == 2:
            # 勝敗決定: 2 回目にレイズして勝負に残った人の手札を公開する
            for index in self.active:
                self.table.players[index].hand_public = True
        self._decide_winner()

    def _exchange_coms(self):
        """1 回目にレイズした COM を、位置の昇順に交換する（0 枚でも交換済みにする）。

        山札の先頭から交換する枚数を引き、昇順の位置に順に入れる。新しいカードの位置
        （new_indices）は変えず、交換した COM の手札は伏せる（hand_public を False にする。
        公開は勝敗決定で行う）。人間の交換はここでは行わない。
        """
        for index in self.active:
            player = self.table.players[index]
            if player.kind == "human":
                continue
            indices = com_exchange_indices(player.hand)
            for position, card in zip(indices, self.table.deck.draw(len(indices))):
                player.hand[position] = card
            player.exchanged = True
            player.hand_public = False

    def _decide_winner(self):
        """残ったレイズした人から勝者を決めてポットを渡す。0 人なら勝者なしでポットが残る。"""
        if not self.active:
            return
        hands = [self.table.players[index].hand for index in self.active]
        # find_winner が返すのは hands 内の位置。プレイヤーの位置に対応づけ直す
        self.winner = self.active[find_winner(hands)]
        self.awarded = self.pot.award(self.table.players[self.winner])
