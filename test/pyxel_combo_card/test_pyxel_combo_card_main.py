import os
import sys
import unittest
from unittest.mock import patch

for p in ["../../src/pyxel_combo_card", "./"]:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), p)))
from main import IView, IInput, GameController  # pylint: disable=C0413
from game import Game, GameResult  # pylint: disable=C0413
from card import Card, Symbol  # pylint: disable=C0413
from hand import Hand  # pylint: disable=C0413
from recipe import Recipe, Combo  # pylint: disable=C0413
from button import ButtonIcon  # pylint: disable=C0413


class TestInput(IInput):
    def __init__(self):
        self.b_is_click = False
        self.mouse_pos = (0, 0)

    def is_click(self):
        return self.b_is_click

    def get_mouse_x(self):
        return self.mouse_pos[0]

    def get_mouse_y(self):
        return self.mouse_pos[1]

    def set_is_click(self, b_is_click):
        self.b_is_click = b_is_click

    def set_mouse_pos(self, x, y):
        self.mouse_pos = (x, y)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def text(self, x, y, text, color):
        self.call_params.append(("text", x, y, text, color))

    def rectb(self, x, y, w, h, color):
        self.call_params.append(("rectb", x, y, w, h, color))

    def rect(self, x, y, w, h, color):
        self.call_params.append(("rect", x, y, w, h, color))

    def cls(self, color):
        self.call_params.append(("cls", color))

    def circb(self, x, y, r, color):
        self.call_params.append(("circb", x, y, r, color))

    def trib(self, x1, y1, x2, y2, x3, y3, color):
        self.call_params.append(("trib", x1, y1, x2, y2, x3, y3, color))

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("blt", x, y, img, u, v, w, h, colkey))

    def get_call_params(self):
        return self.call_params


class TestParent(unittest.TestCase):
    """共通テストセットアップ: IInputとIViewのmock差し替え"""

    # カード表示定数
    CARD_X = 5
    CARD_Y = 25
    CARD_WIDTH = 14
    CARD_HEIGHT = 20
    CARD_GAP = 5
    # Pyxel 色定数
    PYXEL_BLACK = 0  # 背景色、透過色
    PYXEL_WHITE = 7  # 強調テキスト、レシピ選択枠
    PYXEL_DARK_GRAY = 13  # 枠線、シンボル、アイコン

    # 二重枠定数（ゴールシンボル用）
    DOUBLE_FRAME_OFFSET = 2  # 内枠のオフセット（2px内側）
    DOUBLE_FRAME_SIZE_REDUCTION = 4  # 内枠のサイズ縮小量（両側で4px）

    # シンボル画像描画定数
    SYMBOL_IMAGE_BANK = 0  # 画像バンク番号
    CARD_SYMBOL_SIZE = 8  # カード用シンボルサイズ（8x8ピクセル）
    BUTTON_ICON_SIZE = 16  # ボタン用アイコンサイズ（16x16ピクセル）
    SYMBOL_COLKEY = 0  # 透過色（黒）

    # レシピ描画色定数
    RECIPE_EXECUTABLE_COLOR = 5  # 実行可能カードの色（DARK_BLUE）
    RECIPE_NOT_EXECUTABLE_COLOR = 13  # 実行不可能カードの色（DARK_GRAY）

    # 交換ボタン定数
    # 中央配置: レシピ中心(75) - ボタン群幅(65)/2 = 42
    EXCHANGE_BUTTON_X = 42
    EXCHANGE_BUTTON_Y = 50
    EXCHANGE_BUTTON_W = 30
    EXCHANGE_BUTTON_H = 16

    # スキップボタン定数
    # 中央配置: Exchange右端(72) + ギャップ(5) = 77
    SKIP_BUTTON_X = 77
    SKIP_BUTTON_Y = 50
    SKIP_BUTTON_W = 30
    SKIP_BUTTON_H = 16

    # ゲームクリアポップアップ定数
    GAME_CLEAR_POPUP_X = 10
    GAME_CLEAR_POPUP_Y = 55
    GAME_CLEAR_POPUP_W = 130
    GAME_CLEAR_POPUP_H = 30
    GAME_CLEAR_POPUP_TEXT_OFFSET_X = 10
    GAME_CLEAR_POPUP_TEXT_OFFSET_Y = 10

    # ボタンテキストオフセット定数
    TEXT_OFFSET_X = 3  # ボタンの左上からのX方向オフセット
    TEXT_OFFSET_Y = 3  # ボタンの左上からのY方向オフセット

    # レシピ表示定数
    # 中央配置: (画面幅150 - コンテンツ幅58) // 2 = 46
    RECIPE_LIST_X = 46
    RECIPE_LIST_Y = 80
    RECIPE_CARD_GAP = 5
    RECIPE_ARROW_X_OFFSET = 2
    RECIPE_ARROW_Y_OFFSET = 7
    RECIPE_LINE_HEIGHT = 25

    # NPC手札描画定数
    NPC_CARD_Y = 150  # NPC手札のY座標
    NPC_CARD_COLOR = 13  # DARK_GRAY

    # プレイヤーアイコン描画定数
    ICON_SIZE = 8  # アイコンサイズ（8x8ピクセル）
    ICON_IMAGE_BANK = 0  # 画像バンク番号
    ICON_COLKEY = 0  # 透過色（黒）
    PLAYER_ICON_TILE = (5, 0)  # プレイヤーアイコンのタイル座標
    PLAYER_ICON_X = 5  # CARD_X と同じ
    PLAYER_ICON_Y = 15  # CARD_Y - ICON_SIZE - 2

    # NPCアイコン描画定数
    NPC_ICON_TILE = (6, 0)  # NPCアイコンのタイル座標
    NPC_ICON_X = 5  # CARD_X と同じ
    NPC_ICON_Y = 140  # NPC_CARD_Y - ICON_SIZE - 2

    def setUp(self):
        self.test_input = TestInput()
        self.test_view = TestView()
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.mock_input = self.patcher_input.start()
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        self.patcher_input.stop()
        self.patcher_view.stop()

    def build_single_card_draw_calls(self, x, y, card, color):
        """単一カードの描画呼び出しリストを生成

        Args:
            x: カードのX座標
            y: カードのY座標
            card: Cardオブジェクト
            color: カード枠線とテキストの色

        Returns:
            描画呼び出しのリスト
        """
        calls = []

        # カード枠線を描画（外枠）
        calls.append(("rectb", x, y, self.CARD_WIDTH, self.CARD_HEIGHT, color))

        # ゴールシンボルの場合、内枠を追加描画（二重枠）
        if card.has_goal_symbol():
            inner_x = x + self.DOUBLE_FRAME_OFFSET
            inner_y = y + self.DOUBLE_FRAME_OFFSET
            inner_w = self.CARD_WIDTH - self.DOUBLE_FRAME_SIZE_REDUCTION
            inner_h = self.CARD_HEIGHT - self.DOUBLE_FRAME_SIZE_REDUCTION
            calls.append(("rectb", inner_x, inner_y, inner_w, inner_h, color))

        # シンボル画像を描画（カード枠内の中央配置）
        if card.symbol:
            # シンボル座標を取得 (u, v) -> (img_u, img_v)
            # pyxresのタイル座標系（8x8グリッド）からピクセル座標系に変換
            u, v = card.symbol.value
            img_u = u * self.CARD_SYMBOL_SIZE
            img_v = v * self.CARD_SYMBOL_SIZE

            # カード枠内の中央に配置
            symbol_x = x + (self.CARD_WIDTH - self.CARD_SYMBOL_SIZE) // 2
            symbol_y = y + (self.CARD_HEIGHT - self.CARD_SYMBOL_SIZE) // 2

            # シンボル画像を描画（8x8サイズ）
            calls.append(
                (
                    "blt",
                    symbol_x,
                    symbol_y,
                    self.SYMBOL_IMAGE_BANK,
                    img_u,
                    img_v,
                    self.CARD_SYMBOL_SIZE,
                    self.CARD_SYMBOL_SIZE,
                    self.SYMBOL_COLKEY,
                )
            )

        return calls

    # ゲーム結果メッセージ定数
    GAME_RESULT_MESSAGES = {
        GameResult.WIN: "You Win! Click to Restart.",
        GameResult.LOSE: "You Lose! Click to Restart.",
        GameResult.DRAW: "Draw! Click to Restart.",
    }

    def build_expected_draw_calls(
        self,
        cards,
        npc_cards=None,
        recipe_list=None,
        executable_recipe_ids=None,
        selected_recipe_id=None,
        game_result=None,
    ):
        """期待される描画呼び出しを構築するヘルパー関数

        Args:
            cards: カードのリスト（Card オブジェクト）
            npc_cards: NPC手札カードのリスト（デフォルト: None = NPC手札描画なし）
            recipe_list: レシピリスト [(source_cards, target_card), ...]（デフォルト: None = レシピ描画なし）
            executable_recipe_ids: 実行可能なレシピIDのリスト（Noneの場合は全て実行可能扱い）
            selected_recipe_id: 選択中のレシピID（Noneの場合は未選択）
            game_result: ゲーム結果（GameResult enum、Noneの場合はポップアップ非表示）
        Returns:
            期待される描画呼び出しのリスト
        """
        expected_calls = [("cls", self.PYXEL_BLACK)]

        # プレイヤーアイコンを描画（手札の前に描画）
        tile_x, tile_y = self.PLAYER_ICON_TILE
        img_u = tile_x * self.ICON_SIZE
        img_v = tile_y * self.ICON_SIZE
        expected_calls.append(
            (
                "blt",
                self.PLAYER_ICON_X,
                self.PLAYER_ICON_Y,
                self.ICON_IMAGE_BANK,
                img_u,
                img_v,
                self.ICON_SIZE,
                self.ICON_SIZE,
                self.ICON_COLKEY,
            )
        )

        for i, card in enumerate(cards):
            # カード位置を計算
            card_x = self.CARD_X + i * (self.CARD_WIDTH + self.CARD_GAP)

            # 単一カードの描画呼び出しを生成
            card_calls = self.build_single_card_draw_calls(
                card_x,
                self.CARD_Y,
                card,
                self.PYXEL_DARK_GRAY,
            )
            expected_calls.extend(card_calls)

        # 交換ボタンを描画
        expected_calls.append(
            (
                "rectb",
                self.EXCHANGE_BUTTON_X,
                self.EXCHANGE_BUTTON_Y,
                self.EXCHANGE_BUTTON_W,
                self.EXCHANGE_BUTTON_H,
                self.PYXEL_DARK_GRAY,
            )
        )

        # アイコン描画（ButtonIcon.EXCHANGE）
        # アイコン座標を取得（8x8pxタイル座標からピクセル座標へ変換）
        u, v = ButtonIcon.EXCHANGE.value
        img_u = u * self.CARD_SYMBOL_SIZE  # 8x8pxタイルサイズ
        img_v = v * self.CARD_SYMBOL_SIZE

        # ボタン枠内の中央に配置
        icon_x = (
            self.EXCHANGE_BUTTON_X
            + (self.EXCHANGE_BUTTON_W - self.BUTTON_ICON_SIZE) // 2
        )
        icon_y = (
            self.EXCHANGE_BUTTON_Y
            + (self.EXCHANGE_BUTTON_H - self.BUTTON_ICON_SIZE) // 2
        )

        expected_calls.append(
            (
                "blt",
                icon_x,
                icon_y,
                self.SYMBOL_IMAGE_BANK,
                img_u,
                img_v,
                self.BUTTON_ICON_SIZE,
                self.BUTTON_ICON_SIZE,
                self.SYMBOL_COLKEY,
            )
        )

        # スキップボタンを描画
        expected_calls.append(
            (
                "rectb",
                self.SKIP_BUTTON_X,
                self.SKIP_BUTTON_Y,
                self.SKIP_BUTTON_W,
                self.SKIP_BUTTON_H,
                self.PYXEL_DARK_GRAY,
            )
        )

        # アイコン描画（ButtonIcon.SKIP）
        # アイコン座標を取得（8x8pxタイル座標からピクセル座標へ変換）
        u, v = ButtonIcon.SKIP.value
        img_u = u * self.CARD_SYMBOL_SIZE  # 8x8pxタイルサイズ
        img_v = v * self.CARD_SYMBOL_SIZE

        # ボタン枠内の中央に配置
        icon_x = self.SKIP_BUTTON_X + (self.SKIP_BUTTON_W - self.BUTTON_ICON_SIZE) // 2
        icon_y = self.SKIP_BUTTON_Y + (self.SKIP_BUTTON_H - self.BUTTON_ICON_SIZE) // 2

        expected_calls.append(
            (
                "blt",
                icon_x,
                icon_y,
                self.SYMBOL_IMAGE_BANK,
                img_u,
                img_v,
                self.BUTTON_ICON_SIZE,
                self.BUTTON_ICON_SIZE,
                self.SYMBOL_COLKEY,
            )
        )

        # レシピ一覧を含める場合（NPCアイコンの前に描画）
        if recipe_list is not None:
            recipe_calls = self.build_recipe_list_draw_calls(
                recipe_list,
                executable_recipe_ids=executable_recipe_ids,
                selected_recipe_id=selected_recipe_id,
            )
            expected_calls.extend(recipe_calls)

        # NPCアイコンを描画（NPC手札の前に描画）
        npc_tile_x, npc_tile_y = self.NPC_ICON_TILE
        npc_img_u = npc_tile_x * self.ICON_SIZE
        npc_img_v = npc_tile_y * self.ICON_SIZE
        expected_calls.append(
            (
                "blt",
                self.NPC_ICON_X,
                self.NPC_ICON_Y,
                self.ICON_IMAGE_BANK,
                npc_img_u,
                npc_img_v,
                self.ICON_SIZE,
                self.ICON_SIZE,
                self.ICON_COLKEY,
            )
        )

        # NPC手札描画を含める場合（ポップアップより前に描画）
        if npc_cards is not None:
            for i, card in enumerate(npc_cards):
                card_x = self.CARD_X + i * (self.CARD_WIDTH + self.CARD_GAP)
                card_calls = self.build_single_card_draw_calls(
                    card_x, self.NPC_CARD_Y, card, self.NPC_CARD_COLOR
                )
                expected_calls.extend(card_calls)

        # ゲーム結果ポップアップを含める場合（最前面に描画）
        if game_result is not None:
            expected_calls.append(
                (
                    "rect",
                    self.GAME_CLEAR_POPUP_X,
                    self.GAME_CLEAR_POPUP_Y,
                    self.GAME_CLEAR_POPUP_W,
                    self.GAME_CLEAR_POPUP_H,
                    self.PYXEL_BLACK,
                )
            )
            expected_calls.append(
                (
                    "rectb",
                    self.GAME_CLEAR_POPUP_X,
                    self.GAME_CLEAR_POPUP_Y,
                    self.GAME_CLEAR_POPUP_W,
                    self.GAME_CLEAR_POPUP_H,
                    self.PYXEL_DARK_GRAY,
                )
            )
            game_clear_popup_text_x = (
                self.GAME_CLEAR_POPUP_X + self.GAME_CLEAR_POPUP_TEXT_OFFSET_X
            )
            game_clear_popup_text_y = (
                self.GAME_CLEAR_POPUP_Y + self.GAME_CLEAR_POPUP_TEXT_OFFSET_Y
            )
            popup_message = self.GAME_RESULT_MESSAGES[game_result]
            expected_calls.append(
                (
                    "text",
                    game_clear_popup_text_x,
                    game_clear_popup_text_y,
                    popup_message,
                    self.PYXEL_WHITE,
                )
            )

        return expected_calls

    def setup_game_with_recipes(self, combo_list, hand_cards, npc_hand_cards=None):
        """ゲームとコントローラーを指定レシピ・手札で初期化

        Args:
            combo_list: コンボリスト定義
            hand_cards: 手札カードリスト
            npc_hand_cards: NPC手札カードリスト（デフォルト: None = NPC手札を空にする）

        Returns:
            初期化されたGameController
        """
        game = Game()

        game._recipe = Recipe(  # pylint: disable=W0212
            combo_candidates=combo_list, devolved_flg=False
        )

        game._hand = Hand()  # pylint: disable=W0212
        for card in hand_cards:
            game.hand.add_card(card)

        # NPC手札を設定（指定がない場合は空）
        game._npc_hand = Hand()  # pylint: disable=W0212
        if npc_hand_cards is not None:
            for card in npc_hand_cards:
                game._npc_hand.add_card(card)  # pylint: disable=W0212

        controller = GameController()
        controller.game = game
        return controller

    def get_recipe_button_center(self, recipe_index):
        """レシピボタンの中央座標を取得

        Args:
            recipe_index: レシピのインデックス（0から始まる）

        Returns:
            (center_x, center_y): ボタン中央座標のタプル
        """
        selection_margin = 1
        recipe_content_width = 56
        recipe_button_width = recipe_content_width + (selection_margin * 2)  # 58px
        recipe_button_height = self.CARD_HEIGHT + (selection_margin * 2)  # 22px

        # ボタンの起点（マージン分左上にずれる）
        button_x = self.RECIPE_LIST_X - selection_margin
        recipe_y = (
            self.RECIPE_LIST_Y
            + (recipe_index * self.RECIPE_LINE_HEIGHT)
            - selection_margin
        )

        center_x = button_x + recipe_button_width // 2
        center_y = recipe_y + recipe_button_height // 2

        return (center_x, center_y)

    def build_recipe_list_draw_calls(
        self, recipe_list, executable_recipe_ids=None, selected_recipe_id=None
    ):
        """レシピ一覧の描画呼び出しを構築するヘルパー関数

        Args:
            recipe_list: レシピリスト [(source_cards, target_card), ...]
            executable_recipe_ids: 実行可能なレシピIDのリスト（Noneの場合は全て実行可能扱い）
            selected_recipe_id: 選択中のレシピID（Noneの場合は未選択）

        Returns:
            レシピ一覧の描画呼び出しのリスト
        """
        calls = []
        # Noneの場合は全レシピを実行可能扱い
        if executable_recipe_ids is None:
            executable_recipe_ids = list(range(len(recipe_list)))

        for recipe_index, (source_cards, target_card) in enumerate(recipe_list):
            # レシピのY座標を計算（レシピ番号 * RECIPE_LINE_HEIGHT）
            recipe_y = self.RECIPE_LIST_Y + recipe_index * self.RECIPE_LINE_HEIGHT

            # 実行可能/不可能に応じて色を決定
            is_executable = recipe_index in executable_recipe_ids
            color = (
                self.RECIPE_EXECUTABLE_COLOR
                if is_executable
                else self.RECIPE_NOT_EXECUTABLE_COLOR
            )

            # 必要カード1枚目
            card1_x = self.RECIPE_LIST_X
            card1_calls = self.build_single_card_draw_calls(
                card1_x, recipe_y, source_cards[0], color
            )
            calls.extend(card1_calls)

            # 必要カード2枚目
            card2_x = card1_x + self.CARD_WIDTH + self.RECIPE_CARD_GAP
            card2_calls = self.build_single_card_draw_calls(
                card2_x, recipe_y, source_cards[1], color
            )
            calls.extend(card2_calls)

            # 矢印（カード2とカード3の間）
            arrow_x = card2_x + self.CARD_WIDTH + self.RECIPE_ARROW_X_OFFSET
            arrow_y = recipe_y + self.RECIPE_ARROW_Y_OFFSET
            calls.append(("text", arrow_x, arrow_y, "->", color))

            # 獲得カード（矢印との間に9pxの余白）
            card3_x = card2_x + self.CARD_WIDTH + self.RECIPE_ARROW_X_OFFSET * 2 + 7
            card3_calls = self.build_single_card_draw_calls(
                card3_x, recipe_y, target_card, color
            )
            calls.extend(card3_calls)

            # 選択中のレシピのみボタン枠線を描画（マージン付き）
            if selected_recipe_id is not None and recipe_index == selected_recipe_id:
                selection_margin = 1

                # カード群の実際の幅: カード3枚(14px×3) + カード間隔(5px) + 矢印周辺(11px) = 58px
                recipe_content_width = 58

                # 選択枠の位置とサイズ（カード群 + マージン）
                selection_x = self.RECIPE_LIST_X - selection_margin
                selection_y = recipe_y - selection_margin
                selection_width = recipe_content_width + (
                    selection_margin * 2
                )  # 56 + 2 = 58px
                selection_height = self.CARD_HEIGHT + (
                    selection_margin * 2
                )  # 20 + 2 = 22px

                # ボタン枠線のみ描画（ラベルなし）
                calls.append(
                    (
                        "rectb",
                        selection_x,
                        selection_y,
                        selection_width,
                        selection_height,
                        self.PYXEL_WHITE,
                    )
                )

        return calls


class TestCardFrameDisplay(TestParent):
    """カード枠描画のテスト（複数枚対応）"""

    def test_multiple_cards_display_order(self):
        """複数枚のカードが横に並んで描画されること"""
        test_cases = [
            ("2枚", 2),
            ("3枚", 3),
        ]

        for case_name, num_cards in test_cases:
            with self.subTest(case=case_name):
                # 各テストケース前に呼び出し履歴をクリア
                self.test_view.call_params = []

                # カードリストを作成
                cards = [Card(Symbol.B1) for _ in range(num_cards)]

                # GameController を作成（共通ヘルパーメソッドを使用）
                controller = self.setup_game_with_recipes(
                    combo_list=[],
                    hand_cards=cards,
                )
                controller.draw()

                call_params = self.test_view.get_call_params()
                expected_calls = self.build_expected_draw_calls(cards)

                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"描画順序が一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )


class TestSkipButtonClick(TestParent):
    """スキップボタン押下処理のテスト"""

    def test_skip_button_click(self):
        """スキップボタンクリック時の動作テスト

        プレイヤーとNPCの対称性を検証:
        - プレイヤー: 2枚 → 3枚（カード配布で+1枚）
        - NPC: 0枚 → 1枚（カード配布で+1枚）
        """
        # 初期手札: プレイヤー2枚、NPC0枚
        initial_player_cards = [Card(Symbol.B1), Card(Symbol.B1)]
        initial_npc_cards = []  # 明示的に空

        # GameController を作成（共通ヘルパーメソッドを使用）
        controller = self.setup_game_with_recipes(
            combo_list=[],
            hand_cards=initial_player_cards,
            npc_hand_cards=initial_npc_cards,
        )

        # スキップボタンをクリック (1/2スケール: ボタン中央座標を計算式で算出)
        skip_button_pos = (
            self.SKIP_BUTTON_X + self.SKIP_BUTTON_W // 2,
            self.SKIP_BUTTON_Y + self.SKIP_BUTTON_H // 2,
        )
        self.test_input.set_mouse_pos(*skip_button_pos)
        self.test_input.set_is_click(True)
        controller.update()

        # プレイヤー手札枚数の検証（2枚 → 3枚）
        actual_player_cards = controller.game.hand.get_cards()
        self.assertEqual(
            len(actual_player_cards),
            3,
            "プレイヤー: カード配布後、3枚になるべきです",
        )

        # NPC手札枚数の検証（0枚 → 1枚）
        actual_npc_cards = controller.game.npc_hand.get_cards()
        self.assertEqual(
            len(actual_npc_cards),
            1,
            "NPC: カード配布後、1枚になるべきです",
        )

        # 描画を実行して結果を確認
        self.test_view.call_params = []
        controller.draw()

        expected_calls = self.build_expected_draw_calls(
            actual_player_cards, npc_cards=actual_npc_cards
        )

        self.assertEqual(
            self.test_view.call_params,
            expected_calls,
            "スキップボタンクリック後、カード配布が正しく行われていません",
        )


class TestGameStateRendering(TestParent):
    """ゲーム状態に応じた描画の総合テスト（ゲーム状態表示 + リセットボタン表示）"""

    def test_game_state_rendering(self):
        """ゲーム状態（Playing/Clear）に応じた完全な描画内容のパラメータ化テスト"""
        test_cases = [
            (
                "Playing状態",
                Symbol.B1,
                None,  # game_result（ポップアップ非表示）
                "Playing状態の描画が期待と異なります",
            ),
            (
                "Clear状態",
                Symbol.G1,
                GameResult.WIN,  # game_result（プレイヤーのみゴールシンボル）
                "Clear状態の描画が期待と異なります",
            ),
        ]

        for case_name, card_symbol, game_result, error_message in test_cases:
            with self.subTest(case=case_name):
                # GameController を作成（共通ヘルパーメソッドを使用）
                controller = self.setup_game_with_recipes(
                    combo_list=[],
                    hand_cards=[Card(card_symbol)],
                )

                # 描画を実行
                self.test_view.call_params = []
                controller.draw()

                # 期待される描画呼び出しを構築
                expected_calls = self.build_expected_draw_calls(
                    [Card(card_symbol)],
                    game_result=game_result,
                )

                self.assertEqual(
                    self.test_view.call_params, expected_calls, error_message
                )


class TestOperationRestrictionWhenCleared(TestParent):
    """クリア後の操作制限のテスト"""

    def test_operation_restriction_when_cleared(self):
        """クリア後の操作制限のテスト（スキップボタン）"""
        # クリア状態を作る（ランク3カード）
        # GameController を作成（共通ヘルパーメソッドを使用）
        controller = self.setup_game_with_recipes(
            combo_list=[],
            hand_cards=[Card(Symbol.G1)],
        )

        # ゲームがクリア状態であることを確認
        self.assertTrue(
            controller.game.is_game_over(), "ゲームがクリア状態になっていません"
        )

        # 操作前の状態を保存
        hand_before = controller.game.hand.get_cards().copy()

        # スキップボタンをクリック (1/2スケール: ボタン中央座標を計算式で算出)
        skip_button_pos = (
            self.SKIP_BUTTON_X + self.SKIP_BUTTON_W // 2,
            self.SKIP_BUTTON_Y + self.SKIP_BUTTON_H // 2,
        )
        self.test_input.set_mouse_pos(*skip_button_pos)
        self.test_input.set_is_click(True)
        controller.update()

        # 状態が変化していないことを確認
        self.assertEqual(
            controller.game.hand.get_cards(),
            hand_before,
            "クリア後は手札が変化してはいけません",
        )


class TestCardAndRecipeDisplay(TestParent):
    """カードとレシピ一覧の統合描画テスト"""

    def test_single_card_display(self):
        """各カードが正しく描画されること"""
        test_cases = [
            ("B1", Symbol.B1, None),
            ("B2", Symbol.B2, None),
            ("B3", Symbol.B3, None),
            ("S1", Symbol.S1, None),
            ("S2", Symbol.S2, None),
            ("S3", Symbol.S3, None),
            ("S4", Symbol.S4, None),
            ("S5", Symbol.S5, None),
            ("H1", Symbol.H1, None),
            ("H2", Symbol.H2, None),
            ("H3", Symbol.H3, None),
            ("H4", Symbol.H4, None),
            ("G1", Symbol.G1, GameResult.WIN),
            ("G2", Symbol.G2, GameResult.WIN),
        ]

        for mark_name, symbol, game_result in test_cases:
            with self.subTest(mark=mark_name):
                # カードを作成
                card = Card(symbol)

                # GameController を作成（共通ヘルパーメソッドを使用）
                controller = self.setup_game_with_recipes(
                    combo_list=[],
                    hand_cards=[card],
                )
                self.test_view.call_params = []
                controller.draw()

                # 期待される描画呼び出しを構築
                expected_calls = self.build_expected_draw_calls(
                    [card], game_result=game_result
                )

                # 実際の描画呼び出しと比較
                call_params = self.test_view.get_call_params()
                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"{mark_name} の描画が一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )

    def test_draw_recipe_list(self):
        """レシピ一覧描画のテスト（単一レシピと複数レシピ）"""
        test_cases = [
            (
                "1レシピ",
                [[Combo.S1]],
            ),
            (
                "2レシピ",
                [[Combo.S1], [Combo.S1]],
            ),
        ]

        for case_name, combo_list in test_cases:
            with self.subTest(case=case_name):
                # 手札を設定（全レシピが実行可能になるように十分なカードを追加）
                hand_cards = []
                for symbol in [Symbol.B1, Symbol.B3, Symbol.B3]:
                    hand_cards.append(Card(symbol))

                # GameController を作成（共通ヘルパーメソッドを使用）
                controller = self.setup_game_with_recipes(
                    combo_list=combo_list,
                    hand_cards=hand_cards,
                )
                self.test_view.call_params = []

                # レシピ一覧描画メソッドを呼び出し
                controller._draw_recipe_list()  # pylint: disable=W0212

                # 期待される描画呼び出しを構築（ヘルパーメソッドを活用）
                recipe_list = controller.game.get_recipe()
                expected_calls = self.build_recipe_list_draw_calls(recipe_list)

                # 実際の描画呼び出しと比較
                call_params = self.test_view.get_call_params()
                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"{case_name}: レシピ一覧の描画が一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )

    def test_full_draw_with_recipe_list(self):
        """controller.draw()がレシピ一覧を含む完全な画面を描画すること"""
        test_cases = [
            (
                "1レシピ",
                [[Combo.S1]],
            ),
            (
                "2レシピ",
                [[Combo.S1], [Combo.S1]],
            ),
        ]

        for case_name, combo_list in test_cases:
            with self.subTest(case=case_name):
                # 手札にカードを追加（画面表示用 + レシピ実行可能用）
                hand_cards = [Card(Symbol.H1), Card(Symbol.H2)]
                for symbol in [Symbol.B1, Symbol.B3, Symbol.B3]:
                    hand_cards.append(Card(symbol))

                # GameController を作成（共通ヘルパーメソッドを使用）
                controller = self.setup_game_with_recipes(
                    combo_list=combo_list,
                    hand_cards=hand_cards,
                )
                self.test_view.call_params = []

                # draw()メソッドを呼び出し（レシピ一覧を含む完全な描画）
                controller.draw()

                # 期待される描画呼び出しを構築
                all_cards = controller.game.hand.get_cards()
                recipe_list = controller.game.get_recipe()
                expected_calls = self.build_expected_draw_calls(
                    all_cards,
                    recipe_list=recipe_list,
                )

                # 実際の描画呼び出しと比較
                call_params = self.test_view.get_call_params()
                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"{case_name}: 完全な描画が一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )

    def test_recipe_executable_color_distinction(self):
        """実行可能/不可能レシピの色分けテスト（パラメータ化）"""
        test_cases = [
            (
                "レシピ0のみ実行可能",
                [Card(Symbol.B3), Card(Symbol.B3)],  # hand_cards
                [0],  # expected_executable_recipe_ids
            ),
            (
                "全レシピ実行不可能",
                [],  # hand_cards（手札なし）
                [],  # expected_executable_recipe_ids
            ),
        ]

        for case_name, hand_cards, expected_executable_ids in test_cases:
            with self.subTest(case=case_name):
                # GameController を作成（共通ヘルパーメソッドを使用）
                combo_list = [[Combo.S1], [Combo.S2]]
                controller = self.setup_game_with_recipes(
                    combo_list=combo_list,
                    hand_cards=hand_cards,
                )
                self.test_view.call_params = []

                # レシピ一覧描画メソッドを呼び出し
                controller._draw_recipe_list()  # pylint: disable=W0212

                # 期待値を構築
                recipe_list = controller.game.get_recipe()
                expected_calls = self.build_recipe_list_draw_calls(
                    recipe_list, expected_executable_ids
                )

                # 実際の描画呼び出しと比較
                call_params = self.test_view.get_call_params()
                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"{case_name}: 色分けが一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )


class TestRecipeSelection(TestParent):
    """レシピ選択機能のテスト（クリック → 視覚的フィードバック）"""

    def test_recipe_button_click_and_highlight(self):
        """レシピボタンクリック時の視覚的フィードバックのパラメータ化テスト

        実装詳細（selected_recipe_id）ではなく、振る舞い（クリック→描画）をテスト
        """
        # ヘルパーメソッドでボタン座標を取得
        recipe0_center = self.get_recipe_button_center(0)
        recipe1_center = self.get_recipe_button_center(1)

        # 領域外座標（レシピボタンエリアの右側）
        selection_margin = 1
        recipe_content_width = 56
        recipe_button_width = recipe_content_width + (selection_margin * 2)
        button_x = self.RECIPE_LIST_X - selection_margin
        recipe0_y = self.RECIPE_LIST_Y - selection_margin
        outside_x = button_x + recipe_button_width + 5
        outside_y = recipe0_y + 10

        test_cases = [
            (
                "レシピ0のボタンをクリック",
                recipe0_center[0],  # クリックX座標
                recipe0_center[1],  # クリックY座標
                0,  # 期待されるハイライトレシピID（描画確認用）
            ),
            (
                "レシピ1のボタンをクリック",
                recipe1_center[0],  # クリックX座標
                recipe1_center[1],  # クリックY座標
                1,  # 期待されるハイライトレシピID（描画確認用）
            ),
            (
                "領域外をクリック",
                outside_x,  # クリックX座標
                outside_y,  # クリックY座標
                None,  # 期待されるハイライトレシピID（ハイライトなし）
            ),
        ]

        for case_name, click_x, click_y, expected_highlight_id in test_cases:
            with self.subTest(case=case_name):
                controller = self.setup_game_with_recipes(
                    combo_list=[[Combo.S1], [Combo.S2]],
                    hand_cards=[
                        Card(Symbol.B1),
                        Card(Symbol.B3),
                        Card(Symbol.B3),
                    ],
                )

                # クリック位置を設定
                self.test_input.set_mouse_pos(click_x, click_y)
                self.test_input.set_is_click(True)
                controller.update()

                # 描画を実行
                self.test_view.call_params = []
                controller.draw()

                # 期待される描画呼び出しを構築
                all_cards = controller.game.hand.get_cards()
                recipe_list = controller.game.get_recipe()
                expected_calls = self.build_expected_draw_calls(
                    all_cards,
                    recipe_list=recipe_list,
                    executable_recipe_ids=None,  # 全レシピが実行可能
                    selected_recipe_id=expected_highlight_id,  # ハイライト状態
                )

                # 実際の描画呼び出しと比較（描画順序を含む完全検証）
                actual_calls = self.test_view.get_call_params()
                self.assertEqual(
                    actual_calls,
                    expected_calls,
                    f"{case_name}: クリック後の描画が期待と異なります（描画順序含む）",
                )

    def test_recipe_deselection_after_operations(self):
        """レシピ選択解除のパラメータ化テスト

        各操作後にレシピ選択が解除されることを検証（クリック位置でパラメータ化）
        """

        # クリック位置計算（ヘルパーメソッドを使用）
        recipe0_center = self.get_recipe_button_center(0)
        exchange_center = (
            self.EXCHANGE_BUTTON_X + self.EXCHANGE_BUTTON_W // 2,
            self.EXCHANGE_BUTTON_Y + self.EXCHANGE_BUTTON_H // 2,
        )
        skip_center = (
            self.SKIP_BUTTON_X + self.SKIP_BUTTON_W // 2,
            self.SKIP_BUTTON_Y + self.SKIP_BUTTON_H // 2,
        )

        # テストケース定義（クリック位置の配列のみ）
        test_cases = [
            (
                "選択中のレシピを再度クリック（トグル動作）",
                [recipe0_center, recipe0_center],
            ),
            ("レシピ選択後、交換ボタンをクリック", [recipe0_center, exchange_center]),
            ("レシピ選択後、スキップボタンをクリック", [recipe0_center, skip_center]),
        ]

        for case_name, click_positions in test_cases:
            with self.subTest(scenario=case_name):
                controller = self.setup_game_with_recipes(
                    combo_list=[[Combo.S1]],
                    hand_cards=[Card(Symbol.B3), Card(Symbol.B3)],
                )

                # クリック位置を順番に処理
                for x, y in click_positions:
                    self.test_input.set_mouse_pos(x, y)
                    self.test_input.set_is_click(True)
                    controller.update()

                # 選択が解除されていることを検証
                self.assertIsNone(
                    controller.selected_recipe_id,
                    f"{case_name}: 操作後にレシピ選択が解除されるはず",
                )

    def test_recipe_not_executable_button_click_ignored(self):
        """実行不可能なレシピボタンクリック時は選択されないことを検証

        シナリオ:
        - レシピ1（1△ + 1△ → 2△）が実行不可能な状態（手札なし）
        - レシピ1のボタン中央をクリック
        - 期待値: selected_recipe_id = None（選択されない）
        """
        controller = self.setup_game_with_recipes(
            combo_list=[[Combo.S1], [Combo.S2]],
            hand_cards=[
                Card(Symbol.B2),
                Card(Symbol.B2),
            ],
        )

        # レシピ1のボタン中央座標を取得（ヘルパーメソッドを使用）
        recipe1_center = self.get_recipe_button_center(1)

        # レシピ1のボタン中央をクリック
        self.test_input.set_mouse_pos(recipe1_center[0], recipe1_center[1])
        self.test_input.set_is_click(True)
        controller.update()

        # 実行不可能なレシピはクリックを無視し、選択されないことを検証
        self.assertIsNone(
            controller.selected_recipe_id,
            "実行不可能なレシピをクリックしても選択されないはず",
        )

    def test_exchange_button_with_recipe(self):
        """レシピ選択後のExchangeボタンクリックで交換実行されることを検証

        シナリオ:
        - 手札: [1○, 1○, 2△]
        - レシピ0: [1○, 1○] → 2○（実行可能）
        - レシピ0を選択 → Exchange ボタンクリック
        - 期待値: 手札が [2△, 2○] に変化（1○2枚削除、2○追加）
        - 期待値: selected_recipe_id が None（選択状態クリア）

        設計意図:
        - 2段階確認による誤操作防止（レシピ選択 → Exchange ボタン）
        - ダブルクリック確認と同等の効果
        """
        # レシピ定義
        controller = self.setup_game_with_recipes(
            combo_list=[[Combo.S1]],
            hand_cards=[
                Card(Symbol.B3),
                Card(Symbol.B3),
                Card(Symbol.S2),
            ],
        )

        # レシピ0のボタン中央座標を取得
        recipe0_center = self.get_recipe_button_center(0)

        # レシピ0をクリック
        self.test_input.set_mouse_pos(recipe0_center[0], recipe0_center[1])
        self.test_input.set_is_click(True)
        controller.update()

        # レシピ0が選択されていることを確認
        self.assertEqual(
            controller.selected_recipe_id, 0, "レシピ0が選択されているはず"
        )

        # Exchangeボタン中央座標
        exchange_button_center = (
            self.EXCHANGE_BUTTON_X + self.EXCHANGE_BUTTON_W // 2,
            self.EXCHANGE_BUTTON_Y + self.EXCHANGE_BUTTON_H // 2,
        )

        # Exchangeボタンをクリック
        self.test_input.set_mouse_pos(
            exchange_button_center[0], exchange_button_center[1]
        )
        self.test_input.set_is_click(True)
        controller.update()

        # 手札が期待通りに変化したことを検証
        actual_cards = controller.game.hand.get_cards()
        # 期待値: [2△, 2○]（1○2枚削除、2○追加、順序は手札の実装に依存）
        self.assertEqual(len(actual_cards), 2, "手札は2枚になるはず")

        # カードの内容を検証（順序に依存しない検証）
        expected_card_list = [Card(Symbol.S2), Card(Symbol.S1)]
        self.assertEqual(
            actual_cards,
            expected_card_list,
            "手札が期待通りになるか",
        )

        # 選択状態がクリアされていることを検証
        self.assertIsNone(
            controller.selected_recipe_id,
            "Exchange実行後、selected_recipe_idはNoneになるはず",
        )


class TestExchangeButtonNpcTurn(TestParent):
    """交換ボタン押下後のNPCレシピ実行テスト

    背景: 交換ボタン押下後、プレイヤーがクリアした場合、
    NPCにもレシピ実行の機会を与えて引き分け判定を正しく行う
    """

    def test_exchange_button_npc_recipe_execution(self):
        """交換ボタン押下後のNPCレシピ実行（パラメータ化テスト）

        プレイヤーがクリアした場合のみNPCもレシピを実行する:
        - クリア時: NPCもゴールシンボル取得 → 引き分け
        - 非クリア時: NPC手札は変化しない
        """
        test_cases = [
            (
                "プレイヤークリア時、NPCもレシピ実行",
                [[Combo.G1], [Combo.G2]],  # combo_list
                [Card(Symbol.H1), Card(Symbol.H3)],  # player_cards（G1取得可能）
                [Card(Symbol.H2), Card(Symbol.H4)],  # npc_cards（G2取得可能）
                True,  # expected_player_cleared
                True,  # expected_npc_changed
            ),
            (
                "プレイヤー非クリア時、NPCはレシピ実行しない",
                [[Combo.S1], [Combo.G2]],  # combo_list
                [Card(Symbol.B3), Card(Symbol.B3)],  # player_cards（S1取得、非クリア）
                [
                    Card(Symbol.H2),
                    Card(Symbol.H4),
                ],  # npc_cards（G2取得可能だが実行されない）
                False,  # expected_player_cleared
                False,  # expected_npc_changed
            ),
        ]

        for (
            case_name,
            combo_list,
            player_cards,
            npc_cards,
            expected_player_cleared,
            expected_npc_changed,
        ) in test_cases:
            with self.subTest(case=case_name):
                controller = self.setup_game_with_recipes(
                    combo_list=combo_list,
                    hand_cards=player_cards,
                    npc_hand_cards=npc_cards,
                )

                # NPC手札を記録
                npc_symbols_before = [
                    c.symbol for c in controller.game.npc_hand.get_cards()
                ]

                # レシピ0を選択
                recipe0_center = self.get_recipe_button_center(0)
                self.test_input.set_mouse_pos(recipe0_center[0], recipe0_center[1])
                self.test_input.set_is_click(True)
                controller.update()

                # 交換ボタンをクリック
                exchange_center = (
                    self.EXCHANGE_BUTTON_X + self.EXCHANGE_BUTTON_W // 2,
                    self.EXCHANGE_BUTTON_Y + self.EXCHANGE_BUTTON_H // 2,
                )
                self.test_input.set_mouse_pos(exchange_center[0], exchange_center[1])
                self.test_input.set_is_click(True)
                controller.update()

                # プレイヤーのクリア状態を検証
                player_has_goal = any(
                    c.has_goal_symbol() for c in controller.game.hand.get_cards()
                )
                self.assertEqual(
                    player_has_goal,
                    expected_player_cleared,
                    f"{case_name}: プレイヤーのクリア状態が期待と異なる",
                )

                # NPC手札の変化を検証
                npc_symbols_after = [
                    c.symbol for c in controller.game.npc_hand.get_cards()
                ]
                npc_changed = npc_symbols_after != npc_symbols_before
                self.assertEqual(
                    npc_changed,
                    expected_npc_changed,
                    f"{case_name}: NPC手札の変化状態が期待と異なる",
                )

                # クリア時は引き分け判定を追加検証
                if expected_player_cleared and expected_npc_changed:
                    result = controller.game.get_game_result()
                    self.assertEqual(
                        result,
                        GameResult.DRAW,
                        f"{case_name}: 両者クリア時は引き分けになるはず",
                    )


class TestNpcHandDisplay(TestParent):
    """NPC手札描画のテスト（複数枚対応）

    TestCardFrameDisplayと対称的なテスト構造:
    - NPC手札はY=150の位置にDARK_GRAY色で描画される
    - カード配置はプレイヤー手札と同じX座標・間隔
    """

    def test_npc_hand_display_order(self):
        """NPC手札が横に並んで描画されること（パラメータ化テスト）"""
        test_cases = [
            ("1枚", 1),
            ("2枚", 2),
            ("3枚", 3),
        ]

        # シンボルリスト（テストケースで使用）
        symbols = [Symbol.B1, Symbol.B2, Symbol.B3]

        for case_name, num_cards in test_cases:
            with self.subTest(case=case_name):
                # 各テストケース前に呼び出し履歴をクリア
                self.test_view.call_params = []

                # プレイヤー手札（固定1枚）とNPC手札を作成
                player_cards = [Card(Symbol.B1)]
                npc_cards = [Card(symbols[i]) for i in range(num_cards)]

                # GameController を作成
                controller = self.setup_game_with_recipes(
                    combo_list=[],
                    hand_cards=player_cards,
                    npc_hand_cards=npc_cards,
                )
                controller.draw()

                call_params = self.test_view.get_call_params()
                expected_calls = self.build_expected_draw_calls(
                    player_cards, npc_cards=npc_cards
                )

                self.assertEqual(
                    call_params,
                    expected_calls,
                    f"NPC手札{case_name}の描画順序が一致していません\n期待: {expected_calls}\n実際: {call_params}",
                )


class TestGameResultPopup(TestParent):
    """勝敗結果ポップアップ表示のテスト"""

    def test_game_result_popup_messages(self):
        """勝敗に応じたポップアップメッセージ表示（パラメータ化テスト）

        シナリオ:
        - プレイヤー勝利時: "You Win! Click to Restart."
        - プレイヤー敗北時: "You Lose! Click to Restart."
        - 引き分け時: "Draw! Click to Restart."
        """
        test_cases = [
            (
                "プレイヤー勝利",
                [Card(Symbol.G1)],  # player_cards（ゴールシンボル保有）
                [Card(Symbol.B1)],  # npc_cards（ゴールシンボルなし）
                GameResult.WIN,
            ),
            (
                "プレイヤー敗北",
                [Card(Symbol.B1)],  # player_cards（ゴールシンボルなし）
                [Card(Symbol.G1)],  # npc_cards（ゴールシンボル保有）
                GameResult.LOSE,
            ),
            (
                "引き分け",
                [Card(Symbol.G1)],  # player_cards（ゴールシンボル保有）
                [Card(Symbol.G2)],  # npc_cards（ゴールシンボル保有）
                GameResult.DRAW,
            ),
        ]

        for case_name, player_cards, npc_cards, expected_result in test_cases:
            with self.subTest(case=case_name):
                controller = self.setup_game_with_recipes(
                    combo_list=[],
                    hand_cards=player_cards,
                    npc_hand_cards=npc_cards,
                )

                # ゲーム結果を確認
                actual_result = controller.game.get_game_result()
                self.assertEqual(
                    actual_result,
                    expected_result,
                    f"{case_name}: ゲーム結果が期待と異なる",
                )

                # 描画を実行
                self.test_view.call_params = []
                controller.draw()

                # 期待される描画呼び出しを構築
                expected_calls = self.build_expected_draw_calls(
                    player_cards,
                    npc_cards=npc_cards,
                    game_result=expected_result,
                )

                # 実際の描画呼び出しと比較
                actual_calls = self.test_view.get_call_params()
                self.assertEqual(
                    actual_calls,
                    expected_calls,
                    f"{case_name}: ポップアップメッセージの描画が期待と異なる",
                )

    def test_popup_click_sets_reset_flag(self):
        """ポップアップクリックでリセットフラグが立つ"""
        controller = self.setup_game_with_recipes(
            combo_list=[],
            hand_cards=[Card(Symbol.G1)],
            npc_hand_cards=[Card(Symbol.B1)],
        )

        # リセット前はリセットフラグが立っていないことを確認
        self.assertFalse(
            controller.needs_reset(),
            "リセット前はリセットフラグが立っていてはいけません",
        )

        # ポップアップをクリック（ポップアップ中央付近）
        popup_center_x = self.GAME_CLEAR_POPUP_X + self.GAME_CLEAR_POPUP_W // 2
        popup_center_y = self.GAME_CLEAR_POPUP_Y + self.GAME_CLEAR_POPUP_H // 2
        self.test_input.set_mouse_pos(popup_center_x, popup_center_y)
        self.test_input.set_is_click(True)
        controller.update()

        # リセットフラグが立っていることを確認
        self.assertTrue(
            controller.needs_reset(),
            "ポップアップクリック後はリセットフラグが立つべきです",
        )


if __name__ == "__main__":
    unittest.main()
