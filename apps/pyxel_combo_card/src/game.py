import random
from enum import Enum

try:
    from .hand import Hand  # pylint: disable=C0413
    from .card import Card, Symbol  # pylint: disable=C0413
    from .recipe import Recipe, Combo  # pylint: disable=C0413
except ImportError:
    from hand import Hand  # pylint: disable=C0413
    from card import Card, Symbol  # pylint: disable=C0413
    from recipe import Recipe, Combo  # pylint: disable=C0413


class GameResult(Enum):
    """ゲーム結果を表す列挙型"""

    WIN = "win"  # プレイヤー勝利
    LOSE = "lose"  # プレイヤー敗北（NPC勝利）
    DRAW = "draw"  # 引き分け


class Game:
    # シンボルレシピのカテゴリ定義
    COMBO_CANDIDATES = [
        [Combo.S1, Combo.S2, Combo.S3, Combo.S4, Combo.S5],
        [Combo.H1, Combo.H2, Combo.H3, Combo.H4, Combo.G1, Combo.G2],
    ]

    # NPCの待機状態となる手札で保持されているコンボ一覧
    NPC_IDLE_HAND_COMBOS = [Combo.G1, Combo.G2]

    def __init__(self):
        self._hand = Hand()
        self._npc_hand = Hand()
        self._recipe = Recipe(combo_candidates=self.COMBO_CANDIDATES)
        self._distribute_card_to(self._hand)  # プレイヤー初期カードを1枚配布
        self._distribute_card_to(self._npc_hand)  # NPC初期カードを1枚配布

    @property
    def hand(self):
        """手札を取得"""
        return self._hand

    @property
    def npc_hand(self):
        """NPC手札を取得"""
        return self._npc_hand

    def _is_cleared(self, hand: Hand) -> bool:
        """手札にゴールシンボル（G1, G2）があるかを判定

        プレイヤーとNPCで同じクリア条件を使用することをコードで表現。
        """
        cards = hand.get_cards()
        if not cards:
            return False
        return any(card.has_goal_symbol() for card in cards)

    def get_game_result(self) -> GameResult | None:
        """勝敗判定を行う

        Returns:
            GameResult | None: 勝敗結果
                - GameResult.WIN: プレイヤーのみクリア
                - GameResult.LOSE: NPCのみクリア
                - GameResult.DRAW: 両者クリア
                - None: ゲーム続行（どちらもクリアしていない）
        """
        player_cleared = self._is_cleared(self.hand)
        npc_cleared = self._is_cleared(self.npc_hand)

        if player_cleared and npc_cleared:
            return GameResult.DRAW
        if player_cleared:
            return GameResult.WIN
        if npc_cleared:
            return GameResult.LOSE
        return None

    def is_game_over(self) -> bool:
        """ゲーム終了判定（get_game_resultの薄いラッパー）

        Returns:
            bool: ゲームが終了している場合True
        """
        return self.get_game_result() is not None

    def turn(self) -> None:
        """1ターン進める

        NPCの手札交換を行う
        プレイヤーとNPCの手札が最大枚数未満の場合のみカード配布を行い、レシピをシャッフルする。
        手札が最大枚数に達している場合はカード配布をスキップする。
        プレイヤーとNPCは同じ条件でカード配布を受ける（ゲームの公平性）。
        """
        # NPC：手札交換を行う
        self.execute_npc_recipe()
        # プレイヤー：手札が最大枚数未満の場合のみカード配布
        if len(self._hand.get_cards()) < Hand.MAX_HAND_SIZE:
            self._distribute_card_to(self._hand)
        # NPC：手札が最大枚数未満の場合のみカード配布
        if len(self._npc_hand.get_cards()) < Hand.MAX_HAND_SIZE:
            self._distribute_card_to(self._npc_hand)
        self._recipe.shuffle()

    def _distribute_card_to(self, hand: Hand) -> None:
        """指定された手札に基本シンボル（B1, B2, B3）のカードを1枚配布する

        プレイヤーとNPCは同じ条件でカード配布を受ける（ゲームの公平性）。
        シンボルはB1, B2, B3からランダムに選択される。

        Args:
            hand: カードを配布する手札
        """
        symbol = random.choice([Symbol.B1, Symbol.B2, Symbol.B3])
        hand.add_card(Card(symbol))

    def get_recipe(self) -> list[tuple[list[Card], Card]]:
        """レシピ一覧を取得（source と target のペア）

        Returns:
            list[tuple[list[Card], Card]]: レシピ一覧（source カードリストと target カードのタプル）
        """
        source_list = self._recipe.get_source_list()
        return [
            (source, self._recipe.get_target(i)) for i, source in enumerate(source_list)
        ]

    def _is_recipe_executable_by_hand(self, recipe_index: int, hand: Hand) -> bool:
        """指定された手札でレシピが実行可能かどうかを判定する

        Args:
            recipe_index: レシピのインデックス
            hand: 判定に使用する手札

        Returns:
            bool: 実行可能な場合True、そうでない場合False
        """
        hand_cards = hand.get_cards()
        executable_recipe_ids = self._recipe.get_executable_recipe_ids(hand_cards)
        return recipe_index in executable_recipe_ids

    def is_recipe_executable(self, recipe_index: int) -> bool:
        """指定されたレシピがプレイヤーの手札で実行可能かどうかを判定する

        Args:
            recipe_index: レシピのインデックス

        Returns:
            bool: 実行可能な場合True、そうでない場合False
        """
        return self._is_recipe_executable_by_hand(recipe_index, self.hand)

    def _is_npc_recipe_executable(self, recipe_index: int) -> bool:
        """指定されたレシピがNPCの手札で実行可能かどうかを判定する

        Args:
            recipe_index: レシピのインデックス

        Returns:
            bool: 実行可能な場合True、そうでない場合False
        """
        return self._is_recipe_executable_by_hand(recipe_index, self.npc_hand)

    def _execute_recipe_on_hand(self, recipe_index: int, hand: Hand) -> None:
        """指定された手札に対してレシピに従ったカード交換を行う

        Args:
            recipe_index: レシピのインデックス
            hand: カード交換を行う手札
        """
        source_cards = self._recipe.get_source_list()[recipe_index]
        target_card = self._recipe.get_target(recipe_index)

        # 手札から source カードを削除（シンボルベース比較を使用）
        hand_card_indices = hand.find_card_indices(source_cards)
        # 逆順で削除することでインデックスのずれを防ぐ
        for index in sorted(hand_card_indices, reverse=True):
            hand.remove_card_at_index(index)

        # target カードを手札に追加
        hand.add_card(target_card)

    def execute_recipe(self, recipe_index: int) -> None:
        """指定されたレシピに従ってカード交換を行う

        Args:
            recipe_index: レシピのインデックス

        Raises:
            ValueError: レシピが実行不可能な場合（範囲外のインデックスを含む）
        """
        if not self.is_recipe_executable(recipe_index):
            raise ValueError("指定されたレシピは実行できません")

        self._execute_recipe_on_hand(recipe_index, self.hand)

    def execute_npc_recipe(self) -> None:
        """NPCのカード交換を行う"""
        while True:  # NPCが実行可能なレシピがなくなるまで繰り返す
            available_recipe_indices = self._recipe.get_executable_recipe_ids(
                self.npc_hand.get_cards()
            )
            if not available_recipe_indices:
                return  # 実行可能なレシピがない場合は何もしない

            # 待機対象レシピが実行可能な場合は優先的に実行
            recipe_index = None
            if self._has_npc_idle_recipe():
                for idx in available_recipe_indices:
                    target_card = self._recipe.get_target(idx)
                    if target_card.has_goal_symbol():
                        recipe_index = idx
                        break
                if recipe_index is None:
                    return
            else:
                recipe_index = available_recipe_indices[
                    -1
                ]  # 最後に見つかったレシピを実行

            self._execute_recipe_on_hand(recipe_index, self.npc_hand)

    def _has_npc_idle_recipe(self) -> bool:
        """NPCの手札が待機対象を含むレシピを実行可能かどうかを判定する

        Returns:
            bool: 実行可能な場合True、そうでない場合False
        """
        for combo in self.NPC_IDLE_HAND_COMBOS:
            goal_recipe_cards = [Card(sym) for sym in combo.value[1]]
            ret = Recipe.can_execute(self.npc_hand.get_cards(), goal_recipe_cards)
            if ret:
                return True
        return False
