# title: pyxel combo card
# author: masatobu

from abc import ABC, abstractmethod

try:
    from .game import Game, GameResult  # pylint: disable=C0413
    from .button import Button, ButtonIcon  # pylint: disable=C0413
except ImportError:
    from game import Game, GameResult  # pylint: disable=C0413
    from button import Button, ButtonIcon  # pylint: disable=C0413


class IView(ABC):
    @abstractmethod
    def cls(self, color):
        pass

    @abstractmethod
    def rectb(self, x, y, w, h, color):
        pass

    @abstractmethod
    def rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def text(self, x, y, text, color):
        pass

    @abstractmethod
    def circb(self, x, y, r, color):
        pass

    @abstractmethod
    def trib(self, x1, y1, x2, y2, x3, y3, color):
        pass

    @abstractmethod
    def blt(self, x, y, img, u, v, w, h, colkey):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def cls(self, color):
        self.pyxel.cls(color)

    def rectb(self, x, y, w, h, color):
        self.pyxel.rectb(x, y, w, h, color)

    def rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def text(self, x, y, text, color):
        self.pyxel.text(x, y, text, color)

    def circb(self, x, y, r, color):
        self.pyxel.circb(x, y, r, color)

    def trib(self, x1, y1, x2, y2, x3, y3, color):
        self.pyxel.trib(x1, y1, x2, y2, x3, y3, color)

    def blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)


class IInput(ABC):
    @abstractmethod
    def is_click(self):
        pass

    @abstractmethod
    def get_mouse_x(self):
        pass

    @abstractmethod
    def get_mouse_y(self):
        pass


# PyxelInput: 実装用入力デバイス（テストでpatch対象）
class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    @classmethod
    def create(cls):
        return cls()

    def is_click(self):
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_x(self):
        return self.pyxel.mouse_x

    def get_mouse_y(self):
        return self.pyxel.mouse_y


class GameController:
    # カード表示定数
    CARD_X = 5
    CARD_Y = 25
    CARD_WIDTH = 14  # シンボル左右余白の均等化（(14-8)//2 = 3px 左右均等）
    CARD_HEIGHT = 20
    CARD_GAP = 5

    # シンボル画像描画定数
    SYMBOL_IMAGE_BANK = 0  # 画像バンク番号
    CARD_SYMBOL_SIZE = 8  # カード用シンボルサイズ（8x8ピクセル）
    BUTTON_ICON_SIZE = 16  # ボタン用アイコンサイズ（16x16ピクセル）
    SYMBOL_COLKEY = 0  # 透過色（黒）

    # 二重枠定数（ゴールシンボル用）
    DOUBLE_FRAME_OFFSET = 2  # 内枠のオフセット（2px内側）
    DOUBLE_FRAME_SIZE_REDUCTION = 4  # 内枠のサイズ縮小量（両側で4px）

    # Pyxel 色定数
    # 基本色
    PYXEL_BLACK = 0  # 背景色、透過色
    PYXEL_WHITE = 7  # 強調テキスト、レシピ選択枠
    PYXEL_DARK_GRAY = 13  # 枠線、シンボル、アイコン（目に優しい配色）
    # レシピ描画色
    RECIPE_EXECUTABLE_COLOR = 5  # 実行可能レシピ（DARK_BLUE）
    RECIPE_NOT_EXECUTABLE_COLOR = 13  # 実行不可能レシピ（DARK_GRAY）

    # レシピ表示エリア定数
    # 中央配置: (画面幅150 - コンテンツ幅58) // 2 = 46
    RECIPE_LIST_X = 46
    RECIPE_LIST_Y = 80
    RECIPE_LINE_HEIGHT = 25
    RECIPE_CARD_GAP = 5
    RECIPE_ARROW_X_OFFSET = 2
    RECIPE_ARROW_Y_OFFSET = 7

    # レシピ選択枠定数
    RECIPE_SELECTION_MARGIN = 1
    # レシピコンテンツ幅: カード1 + ギャップ + カード2 + 矢印余白*2 + 矢印幅 + 矢印後余白 + カード3
    # = 14 + 5 + 14 + 4 + 5 + 2 + 14 = 58px
    RECIPE_CONTENT_WIDTH = 58

    # ゲームクリアポップアップ定数
    GAME_CLEAR_POPUP_X = 10
    GAME_CLEAR_POPUP_Y = 55
    GAME_CLEAR_POPUP_W = 130
    GAME_CLEAR_POPUP_H = 30
    GAME_CLEAR_POPUP_TEXT_OFFSET_X = 10
    GAME_CLEAR_POPUP_TEXT_OFFSET_Y = 10

    # NPC手札描画定数
    NPC_CARD_Y = 150  # NPC手札のY座標

    # プレイヤーアイコン描画定数
    ICON_SIZE = 8  # アイコンサイズ（8x8ピクセル）
    PLAYER_ICON_TILE = (5, 0)  # プレイヤーアイコンのタイル座標
    PLAYER_ICON_X = 5  # CARD_X と同じ
    PLAYER_ICON_Y = 15  # CARD_Y - ICON_SIZE - 2

    # NPCアイコン描画定数
    NPC_ICON_TILE = (6, 0)  # NPCアイコンのタイル座標
    NPC_ICON_X = 5  # CARD_X と同じ
    NPC_ICON_Y = 140  # NPC_CARD_Y - ICON_SIZE - 2

    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()
        self.game = Game()
        self._needs_reset = False  # リセットフラグ
        self.selected_recipe_id = None  # 選択中レシピID
        self.recipe_buttons = []  # レシピボタンリスト

        # Exchange ボタンのインスタンスを作成
        # 中央配置: レシピ中心(75) - ボタン群幅(65)/2 = 42
        self.exchange_button = Button(
            x=42,
            y=50,
            width=30,
            height=16,
            label="",
            color=self.PYXEL_DARK_GRAY,
            icon=ButtonIcon.EXCHANGE,
        )

        # Skip ボタンのインスタンスを作成
        # 中央配置: Exchange右端(72) + ギャップ(5) = 77
        self.skip_button = Button(
            x=77,
            y=50,
            width=30,
            height=16,
            label="",
            color=self.PYXEL_DARK_GRAY,
            icon=ButtonIcon.SKIP,
        )

        # ゲームクリアポップアップのボタンインスタンスを作成
        self.game_clear_popup_button = Button(
            x=self.GAME_CLEAR_POPUP_X,
            y=self.GAME_CLEAR_POPUP_Y,
            width=self.GAME_CLEAR_POPUP_W,
            height=self.GAME_CLEAR_POPUP_H,
            label="",
            color=self.PYXEL_DARK_GRAY,
        )

        # レシピボタンの初期化
        self._init_recipe_buttons()

    def needs_reset(self):
        """リセットが必要かどうかを返す"""
        return self._needs_reset

    def _init_recipe_buttons(self):
        """レシピボタンの初期化（マージン付き選択枠）

        選択枠の設計:
        - カード群（120px幅）の周囲にマージン3pxを追加
        - カード境界との視覚的区別を実現
        - 幅126px（120 + 3×2）、高さ46px（40 + 3×2）
        """
        recipe_list = self.game.get_recipe()
        self.recipe_buttons = []
        for recipe_index in range(len(recipe_list)):
            recipe_y = self.RECIPE_LIST_Y + recipe_index * self.RECIPE_LINE_HEIGHT

            # 選択枠の位置: カード群の左上からマージン分外側
            button_x = self.RECIPE_LIST_X - self.RECIPE_SELECTION_MARGIN
            button_y = recipe_y - self.RECIPE_SELECTION_MARGIN

            # 選択枠のサイズ: カード群の実際の範囲 + 両側マージン
            button_width = self.RECIPE_CONTENT_WIDTH + (
                self.RECIPE_SELECTION_MARGIN * 2
            )  # 120 + 6 = 126
            button_height = self.CARD_HEIGHT + (
                self.RECIPE_SELECTION_MARGIN * 2
            )  # 40 + 6 = 46

            button = Button(
                x=button_x,
                y=button_y,
                width=button_width,
                height=button_height,
                label="",  # レシピボタンはラベルなし（カード描画のみ）
                color=self.PYXEL_WHITE,
            )
            self.recipe_buttons.append(button)

    def update(self):
        if not self.input.is_click():
            return

        mouse_x = self.input.get_mouse_x()
        mouse_y = self.input.get_mouse_y()

        # ゲーム終了時はポップアップクリックのみ受け付ける
        if self.game.is_game_over():
            if self.game_clear_popup_button.is_clicked(mouse_x, mouse_y):
                self._handle_reset_button_click()
            return

        # 交換ボタンのクリック処理
        if self.exchange_button.is_clicked(mouse_x, mouse_y):
            self._handle_exchange_button_click()
            return

        # スキップボタンのクリック処理
        if self.skip_button.is_clicked(mouse_x, mouse_y):
            self._handle_skip_button_click()
            return

        # レシピボタンのクリック処理
        for recipe_index, button in enumerate(self.recipe_buttons):
            if button.is_clicked(mouse_x, mouse_y):
                # 実行不可能なレシピはクリックを無視
                if not self.game.is_recipe_executable(recipe_index):
                    return

                # トグル動作: 選択中のレシピを再度クリックした場合は選択解除
                if self.selected_recipe_id == recipe_index:
                    self.selected_recipe_id = None
                else:
                    self.selected_recipe_id = recipe_index
                return

    def _handle_exchange_button_click(self):
        """交換ボタンがクリックされたときの処理

        レシピが選択されている場合、そのレシピを実行します。
        プレイヤーがクリアした場合、NPCにもレシピ実行の機会を与えます。
        実行後は選択状態をクリアします。
        """
        if self.selected_recipe_id is not None:
            # レシピが選択されている場合、そのレシピを実行
            self.game.execute_recipe(self.selected_recipe_id)
            self.selected_recipe_id = None

            # プレイヤーがクリアした場合、NPCにもレシピ実行の機会を与える
            # （引き分け判定を正しく行うため）
            if self.game.is_game_over():
                self.game.execute_npc_recipe()

    def _handle_skip_button_click(self):
        """スキップボタンがクリックされたときの処理"""
        # 選択状態を解除
        self.selected_recipe_id = None
        # 1ターン進める
        self.game.turn()

    def _handle_reset_button_click(self):
        """リセットボタンがクリックされたときの処理"""
        self._needs_reset = True

    def draw(self):
        # 背景クリア
        self.view.cls(self.PYXEL_BLACK)

        # プレイヤーアイコンを描画
        self._draw_icon(self.PLAYER_ICON_X, self.PLAYER_ICON_Y, self.PLAYER_ICON_TILE)

        # プレイヤー手札を描画
        self._draw_hand(self.game.hand, self.CARD_Y, self.PYXEL_DARK_GRAY)

        # 交換ボタンを描画
        self.exchange_button.draw(self.view)

        # スキップボタンを描画
        self.skip_button.draw(self.view)

        # レシピ一覧を描画
        self._draw_recipe_list()

        # NPCアイコンを描画
        self._draw_icon(self.NPC_ICON_X, self.NPC_ICON_Y, self.NPC_ICON_TILE)

        # NPC手札を描画
        self._draw_hand(self.game.npc_hand, self.NPC_CARD_Y, self.PYXEL_DARK_GRAY)

        # ゲーム結果ポップアップを描画
        self._draw_game_result_popup()

    def _draw_icon(self, x, y, tile):
        """アイコンを描画（プレイヤー・NPC共通処理）

        Args:
            x: アイコンのX座標
            y: アイコンのY座標
            tile: タイル座標 (tile_x, tile_y)
        """
        tile_x, tile_y = tile
        img_u = tile_x * self.ICON_SIZE
        img_v = tile_y * self.ICON_SIZE
        self.view.blt(
            x,
            y,
            self.SYMBOL_IMAGE_BANK,
            img_u,
            img_v,
            self.ICON_SIZE,
            self.ICON_SIZE,
            self.SYMBOL_COLKEY,
        )

    def _draw_hand(self, hand, y, color):
        """手札を描画（プレイヤー・NPC共通処理）

        Args:
            hand: Hand オブジェクト
            y: 手札のY座標
            color: カード枠線の色
        """
        cards = hand.get_cards()
        for i, card in enumerate(cards):
            card_x = self.CARD_X + i * (self.CARD_WIDTH + self.CARD_GAP)
            self._draw_card_base(card_x, y, card, color)

    # ゲーム結果メッセージ定数
    GAME_RESULT_MESSAGES = {
        GameResult.WIN: "You Win! Click to Restart.",
        GameResult.LOSE: "You Lose! Click to Restart.",
        GameResult.DRAW: "Draw! Click to Restart.",
    }

    def _draw_game_result_popup(self):
        """ゲーム結果ポップアップを描画（勝敗に応じたメッセージ表示）

        ゲーム終了時のみポップアップを描画する。
        ゲーム続行中（get_game_result() が None）の場合は何もしない。
        """
        game_result = self.game.get_game_result()
        if game_result is None:
            return

        self.view.rect(
            self.GAME_CLEAR_POPUP_X,
            self.GAME_CLEAR_POPUP_Y,
            self.GAME_CLEAR_POPUP_W,
            self.GAME_CLEAR_POPUP_H,
            self.PYXEL_BLACK,
        )
        self.game_clear_popup_button.draw(self.view)
        # ゲーム結果に応じたメッセージを取得
        popup_message = self.GAME_RESULT_MESSAGES[game_result]
        # ゲーム結果ポップアップテキストを描画
        game_result_popup_text_x = (
            self.GAME_CLEAR_POPUP_X + self.GAME_CLEAR_POPUP_TEXT_OFFSET_X
        )
        game_result_popup_text_y = (
            self.GAME_CLEAR_POPUP_Y + self.GAME_CLEAR_POPUP_TEXT_OFFSET_Y
        )
        self.view.text(
            game_result_popup_text_x,
            game_result_popup_text_y,
            popup_message,
            self.PYXEL_WHITE,
        )

    def _draw_card_base(self, x, y, card, color):
        """カードの基本描画（枠線、シンボル画像）

        Args:
            x: カードのX座標
            y: カードのY座標
            card: Card オブジェクト
            color: 描画色
        """
        # カード枠を描画（外枠）
        self.view.rectb(x, y, self.CARD_WIDTH, self.CARD_HEIGHT, color)

        # ゴールシンボルの場合、内枠を追加描画（二重枠）
        if card.has_goal_symbol():
            inner_x = x + self.DOUBLE_FRAME_OFFSET
            inner_y = y + self.DOUBLE_FRAME_OFFSET
            inner_w = self.CARD_WIDTH - self.DOUBLE_FRAME_SIZE_REDUCTION
            inner_h = self.CARD_HEIGHT - self.DOUBLE_FRAME_SIZE_REDUCTION
            self.view.rectb(inner_x, inner_y, inner_w, inner_h, color)

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
            self.view.blt(
                symbol_x,
                symbol_y,
                self.SYMBOL_IMAGE_BANK,
                img_u,
                img_v,
                self.CARD_SYMBOL_SIZE,
                self.CARD_SYMBOL_SIZE,
                self.SYMBOL_COLKEY,
            )

    def _draw_recipe_list(self):
        """レシピ一覧を描画

        描画順序:
        1. カード（必要カード2枚 + 矢印 + 獲得カード1枚）
        2. 選択中レシピのみボタン枠線
        """
        recipe_list = self.game.get_recipe()

        for recipe_index, (source_cards, target_card) in enumerate(recipe_list):
            # レシピのY座標を計算（レシピ番号 * RECIPE_LINE_HEIGHT）
            recipe_y = self.RECIPE_LIST_Y + recipe_index * self.RECIPE_LINE_HEIGHT

            # このレシピが実行可能かどうかを判定
            is_executable = self.game.is_recipe_executable(recipe_index)

            # 実行可能/不可能に応じて色を決定
            color = (
                self.RECIPE_EXECUTABLE_COLOR
                if is_executable
                else self.RECIPE_NOT_EXECUTABLE_COLOR
            )

            # 必要カード1枚目を描画
            card1_x = self.RECIPE_LIST_X
            self._draw_card_base(card1_x, recipe_y, source_cards[0], color)

            # 必要カード2枚目を描画
            card2_x = card1_x + self.CARD_WIDTH + self.RECIPE_CARD_GAP
            self._draw_card_base(card2_x, recipe_y, source_cards[1], color)

            # 矢印を描画（カード2と獲得カードの間）
            arrow_x = card2_x + self.CARD_WIDTH + self.RECIPE_ARROW_X_OFFSET
            arrow_y = recipe_y + self.RECIPE_ARROW_Y_OFFSET
            self.view.text(arrow_x, arrow_y, "->", color)

            # 獲得カードを描画（矢印の右側）
            # 計算: カード2のX座標 + カード幅 + 矢印とカードの余白(RECIPE_ARROW_X_OFFSET * 2 + 7)
            # 矢印後に2pxの余白を追加 (+5 → +7)
            card3_x = card2_x + self.CARD_WIDTH + self.RECIPE_ARROW_X_OFFSET * 2 + 7
            self._draw_card_base(card3_x, recipe_y, target_card, color)

            # 選択中のレシピのみボタン枠線を描画（最前面）
            if recipe_index == self.selected_recipe_id:
                self.recipe_buttons[recipe_index].draw(self.view)


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        self.game_controller = GameController()

        pyxel.init(150, 200, title="Pyxel Combo Card")
        pyxel.load("icon.pyxres")
        pyxel.mouse(True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if self.game_controller.needs_reset():
            self.game_controller = GameController()
        else:
            self.game_controller.update()

    def draw(self):
        self.game_controller.draw()


if __name__ == "__main__":
    PyxelController()
