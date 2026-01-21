# title: Button class for pyxel combo card
# author: masatobu

from enum import Enum


class ButtonIcon(Enum):
    """ボタンアイコンの座標管理

    責務:
    - ボタンアイコンのタイル座標を管理
    - icon.pyxres のタイル座標と対応

    値:
    - tuple[int, int]: (タイルx座標, タイルy座標)
    """

    EXCHANGE = (1, 0)  # Exchangeアイコンのタイル座標
    SKIP = (3, 0)  # Skipアイコンのタイル座標


class Button:
    """ボタンの描画とクリック判定を管理するクラス

    責務:
    - 位置・サイズ・ラベルの管理
    - 描画処理（枠線、テキスト、アイコン）
    - クリック判定（矩形判定、半開区間）
    """

    # テキスト描画のオフセット（ボタンの左上からの距離）
    TEXT_OFFSET_X = 3
    TEXT_OFFSET_Y = 3

    # アイコン描画の定数
    ICON_SIZE = 16  # アイコンサイズ（16x16px）
    TILE_SIZE = 8  # タイルサイズ（8x8px）
    IMAGE_BANK = 0  # 画像バンク番号
    COLKEY = 0  # 透過色（黒）

    def __init__(self, x, y, width, height, label, color, icon=None):
        """ボタンを初期化

        Args:
            x: ボタンのx座標
            y: ボタンのy座標
            width: ボタンの幅
            height: ボタンの高さ
            label: ボタンのラベル文字列
            color: 描画色
            icon: ButtonIcon Enum または None（アイコン表示する場合）
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.color = color
        self.icon = icon

    def draw(self, view):
        """ボタンを描画

        Args:
            view: IView インターフェースを実装した描画オブジェクト
        """
        # 枠線を描画
        view.rectb(self.x, self.y, self.width, self.height, self.color)

        # アイコンまたはテキストを描画（排他的）
        if self.icon is not None:
            # アイコンを中央配置
            icon_x = self.x + (self.width - self.ICON_SIZE) // 2
            icon_y = self.y + (self.height - self.ICON_SIZE) // 2

            # タイル座標をピクセル座標に変換（8x8pxタイル）
            tile_x, tile_y = self.icon.value
            img_u = tile_x * self.TILE_SIZE
            img_v = tile_y * self.TILE_SIZE

            # アイコンを描画
            view.blt(
                icon_x,
                icon_y,
                self.IMAGE_BANK,
                img_u,
                img_v,
                self.ICON_SIZE,
                self.ICON_SIZE,
                self.COLKEY,
            )
        elif self.label:
            # テキストを描画（ラベルが空でない場合のみ）
            text_x = self.x + self.TEXT_OFFSET_X
            text_y = self.y + self.TEXT_OFFSET_Y
            view.text(text_x, text_y, self.label, self.color)

    def is_clicked(self, mouse_x, mouse_y):
        """クリック判定（矩形内かどうか）

        Args:
            mouse_x: マウスのx座標
            mouse_y: マウスのy座標

        Returns:
            bool: 矩形内であれば True、それ以外は False
        """
        return (
            self.x <= mouse_x < self.x + self.width
            and self.y <= mouse_y < self.y + self.height
        )
