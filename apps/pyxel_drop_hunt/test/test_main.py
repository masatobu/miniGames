import math
import unittest
from unittest.mock import patch, MagicMock
from src.main import (
    IView,
    IInput,
    GameCore,
    App,
    Drop,
    Field,
    Mob,
    Player,
    Bullet,
    MoveMode,
)


class TestView(IView):
    def __init__(self):
        self.call_params = []
        # get_frame() が返すフレーム数（テストから set_frame() で注入する。
        # 既定値 0 はフレーム数に依存しない既存テストへ影響しない）
        self._frame = 0

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_rect(self, x, y, w, h, color):
        self.call_params.append(("draw_rect", x, y, w, h, color))

    def draw_circ(self, x, y, r, color):
        self.call_params.append(("draw_circ", x, y, r, color))

    def draw_circb(self, x, y, r, color):
        self.call_params.append(("draw_circb", x, y, r, color))

    def draw_blt(self, x, y, img, u, v, w, h, colkey, rotate=0):
        self.call_params.append(("draw_blt", x, y, img, u, v, w, h, colkey, rotate))

    def clear(self, x, y):
        self.call_params.append(("clear", x, y))

    def set_frame(self, frame):
        self._frame = frame

    def get_frame(self):
        return self._frame

    def get_call_params(self):
        return self.call_params

    def reset(self):
        self.call_params = []


class TestInput(IInput):
    """タップ（マウス）入力の状態注入スタブ（pyxel_break_blocks の TestInput と
    同一パターン）"""

    def __init__(self):
        self._btn_pressed = False
        self._mouse_x = 0
        self._mouse_y = 0

    def set_btn_pressed(self, pressed):
        self._btn_pressed = pressed

    def set_mouse_x(self, x):
        self._mouse_x = x

    def set_mouse_y(self, y):
        self._mouse_y = y

    def is_btn_pressed(self) -> bool:
        return self._btn_pressed

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y


class TestParent(unittest.TestCase):
    """操作（タップ入力）・描画 IF の結線を検証する e2e スタイルテストの共通
    土台。actor がどう動くか（追尾・出現・消滅・目的地状態遷移の詳細）は
    Field の公開 IF に対するテスト（test_field.py）で固定済みのため対象外"""

    INITIAL_PLAYER_X = (GameCore.SCREEN_WIDTH - GameCore.PLAYER_W) // 2
    INITIAL_PLAYER_Y = (GameCore.SCREEN_HEIGHT - GameCore.PLAYER_H) // 2
    # プレイヤーの登録座標（スプライト左上）から画像中心点までのオフセット。
    # turn_to は画像中心点を基準に方向を計算する（test_actor.py の
    # TestActorTurnTo で固定した仕様）ため、タップ位置（目的地）の期待値は
    # このオフセットを介して「プレイヤー中心点 + 差分」で計算する
    PLAYER_CENTER_OFFSET_X = GameCore.PLAYER_W // 2
    PLAYER_CENTER_OFFSET_Y = GameCore.PLAYER_H // 2
    # ゲーム開始時に出現するモブの位置・回転（setUp が乱数をプレイヤー真上の
    # x へ固定するため、出現位置はプレイヤー真上の画面外、出現時の
    # turn_to(player.x, player.y) による回転は真下＝180度の自明値になる）。
    # update() を呼ぶとモブが MOB_SPEED で移動するため、モブの移動を検証対象と
    # しないテストでは、GameCore() 生成後に core._field._mobs = [] としてモブ自体を
    # 除去した上で _assert_field_and_player_drawn(..., mobs=()) を用いる
    INITIAL_MOB_X = INITIAL_PLAYER_X
    INITIAL_MOB_Y = -Field.MOB_SPAWN_OFFSET
    INITIAL_MOB_ROTATE = 180
    INITIAL_MOB = (INITIAL_MOB_X, INITIAL_MOB_Y, INITIAL_MOB_ROTATE)

    # --- ステータス HUD の表示仕様（ID-012-8 の Red で決定した具体値を
    # 2026-07-12 のプレイテスト指摘（背景色・横並び・すき間なし・矩形幅を
    # 画面いっぱいに）に基づき改訂）。ステータスは毎フレーム必ず描画される
    # ため、期待値の計算（_expected_status_calls）とともに全描画結線
    # テストの共通土台に置く ---
    # 表示位置は画面左上: プレイヤーは常に画面中央付近に描画されるため、
    # 画面の縁は行動の観測を妨げにくく、中でも左上は HUD の慣習的な位置。
    # HP・通常ドロップ数・レアドロップ数の3項目は縦1列ではなく横1行に並べる
    # （requirements.md §4 の列挙順のまま左から順に配置）。背景はスクリーン
    # 左端（x=0）にぴったりくっつけて描画する単一の矩形とし、項目間・矩形の
    # 内部にすき間を作らないことで、項目間にフィールドタイルの描画が
    # ちらついて見える問題を解消する
    # Pyxel 標準フォントはグリフ 5px 高・4px 送りのため、上下パディング
    # 2px で矩形高さ 9 とする
    STATUS_RECT_H = 9
    # 背景矩形の横幅は画面全体（右端まで隙間なく覆う）: 項目分の幅だけに
    # 留めると右側だけ空いて不自然に見える、というプレイテスト指摘を反映し、
    # 表示領域のサイズを単一の情報源として持つ既存の GameCore.SCREEN_WIDTH
    # をそのまま使う
    STATUS_RECT_W = GameCore.SCREEN_WIDTH
    # 矩形は色1（濃い青、Pyxel 標準パレット）: プレイテスト指摘により黒
    # （色0）から変更。テキストは PyxelView が色7（白）固定のため、
    # 濃い青の背景でも視認性を確保できる
    STATUS_RECT_COLOR = 1
    # テキストの矩形内パディング（左・上とも 2px。上下対称になる）
    STATUS_TEXT_OFFSET = 2
    # 項目間の余白（2026-07-19 人間プレイテスト指摘により ID-016-18 で
    # 追加。旧 STATUS_SLOT_W〔均一60px×3項目=180px〕は SCREEN_WIDTH
    # （150px）を超えており、3項目目〔RARE〕が画面右端で見切れる不具合が
    # あった。HP/DROP間の隙間が広すぎるという指摘も合わせ、各項目を
    # 想定最大文字数ぶんの幅で左詰めし、項目間はこの最小限の余白のみで
    # 区切る設計へ変更する）。初回の値（4px）は HP/DROP 間の隙間が
    # DROP/RARE 間（実際の表示文字数が短い序盤ほど、予約幅の余りにより
    # 見かけ上広く見える）に比べて狭すぎるという再指摘を受け、
    # 全項目のペア間で一貫した見た目の余白になるよう12pxへ拡大した
    # （RARE:20/20到達時でも描画終端135pxとなりSCREEN_WIDTH=150pxに
    # 収まる最大値19pxより余裕を持たせた値）
    STATUS_ITEM_GAP = 12
    # DROP・RARE表示をまとめて右へずらす追加オフセット（2026-07-20
    # 人間プレイテスト指摘: HP-DROP間の余白〔STATUS_ITEM_GAP=12px〕に
    # 比べ、RARE表示の右側の余白〔画面幅150px−RARE終端109px＝41px〕が
    # 広く感じられるという指摘を受け、DROP・RARE表示をまとめて右へ
    # 約10pxずらす〔HP-DROP間の余白は12→22pxに広がるが、RARE右側の
    # 余白は41→31pxに縮み、指摘された余白の偏りが緩和される〕。HPの
    # 位置・DROP-RARE間の余白〔STATUS_ITEM_GAP〕はそのまま変更しない）
    STATUS_DROP_GROUP_OFFSET = 10
    # RARE の想定最大文字数（位置を固定するための基準。カウント増加の
    # たびに幅が変わって表示がちらつくのを避けるため、実際の現在値ではなく
    # 想定最大文字数を基準にする設計思想は旧 STATUS_SLOT_W から踏襲する）。
    # ラベル文字（"RARE:"）は ID-019 サイクル2（ID-019-5〜）でアイコンへ
    # 置き換えたため、DROP と同じくラベルを除いた数値部分のみを基準にする。
    # クリア必要数 Field.RARE_DROP_CLEAR_TARGET が分子・分母の最大値になる
    # ため "{クリア必要数}/{クリア必要数}" の長さを使う
    RARE_NUMBER_MAX_CHARS = len(
        f"{Field.RARE_DROP_CLEAR_TARGET}/{Field.RARE_DROP_CLEAR_TARGET}"
    )
    # --- HP のハートアイコン表示仕様（requirements.md §4「HPはハート
    # アイコンを3つ並べて表示する」。ID-018-2 の Red で決定した具体値）---
    # 画像アセットは登録済みの layer0（既存の PLAYER_IMG などと同じ
    # バンク0）の赤ハート画像（起点 (32,8)、5×4）を使う
    HEART_IMG = 0
    HEART_U = 32
    HEART_V = 8
    HEART_W = 5
    HEART_H = 4
    # ハート同士のすき間: ハート画像は中段の横一列が 5px 幅の左右端まで
    # 達する形状のため、すき間なしで並べると隣接ハートと繋がって見える。
    # 1px のすき間で区切る
    HEART_GAP = 1
    # HP 項目の表示幅（ハート Player.INITIAL_HP 個分 + 間のすき間。
    # HP 上限は常に Player.INITIAL_HP＝3 固定〔可変上限は考慮不要〕の
    # ため、並べる個数・表示幅も固定でよい）
    HEART_ITEM_W = Player.INITIAL_HP * HEART_W + (Player.INITIAL_HP - 1) * HEART_GAP
    # HP 減少分（灰色）のハート画像。バンク・サイズは赤ハートと同じで、
    # 起点のみ異なる（ID-018-1 で確認済みの画像アセット座標）
    HEART_GRAY_U = 40
    HEART_GRAY_V = 8
    # ハートの縦位置（人間プレイテスト指摘により2026-07-20改訂）:
    # STATUS_TEXT_OFFSET（=2）のままだとハート（高さ4px）は矩形（高さ9px）
    # の中で上2px・下3pxとなり、テキスト（高さ5px、上下2px対称で中央）に
    # 比べて上寄りに見える。1px下げて上3px・下2pxにする方が中央寄りに
    # 見えるという指摘を反映し、STATUS_TEXT_OFFSET + 1 とする（テキストの
    # y座標自体は変更しない）
    HEART_Y_OFFSET = STATUS_TEXT_OFFSET + 1
    # --- 通常ドロップ数のアイコン表示仕様（requirements.md §4「ドロップ数の
    # ラベルをドロップ画像のアイコンで表示できる」。ID-019-2 の Red で決定
    # した具体値）---
    # アイコン画像は登録済みの layer0（既存の PLAYER_IMG 等と同じバンク0）の
    # 通常ドロップ画像を流用する。座標・サイズは ID-019-1 で確認済みの
    # フィールド描画と同じ GameCore.DROP_IMG/DROP_U/DROP_V/DROP_W/DROP_H
    # をそのまま使うため、テスト側にも重複定義しない
    # アイコンと数値テキストの間のすき間: HEART_GAP（1px、隣接ハート同士の
    # すき間）よりも一回り広く取り、アイコン（4px高）と数値テキスト
    # （グリフ5px高）の境界を判別しやすくする
    DROP_ICON_GAP = 2
    # DROP 項目の想定最大文字数はラベルを除いた数値部分のみ（成長上限直前の
    # "2549/2550" の9文字。旧 DROP_TEXT_MAX_CHARS から "DROP:" の5文字を
    # 除いた値。ID-016-17 と同じしきい値の系列が根拠）
    DROP_NUMBER_MAX_CHARS = len("2549/2550")
    # アイコンの縦位置: ハートと同じ考え方（アイコン高4px はテキストの
    # グリフ高5pxより1px低いため、STATUS_TEXT_OFFSET+1で中央寄せに揃える。
    # ドロップアイコンもハートと同じ4px高のため同じオフセット値を用いる）
    DROP_ICON_Y_OFFSET = STATUS_TEXT_OFFSET + 1
    # --- レアドロップ数のアイコン表示仕様（requirements.md §4「ドロップ数の
    # ラベルをドロップ画像のアイコンで表示できる」。ID-019-5 の Red で決定
    # した具体値）---
    # アイコン画像は通常ドロップと同じ layer0・GameCore.DROP_IMG/DROP_W/
    # DROP_H（サイズ4×4は共通）で、起点座標のみ ID-019-1 で確認済みの
    # GameCore.RARE_DROP_U/RARE_DROP_V を使う。すき間・縦位置は、通常/レア
    # どちらのドロップアイコンでも同じ4×4サイズ・同じ「アイコン高4pxは
    # テキストのグリフ高5pxより1px低い」という根拠が成り立つため、
    # 通常ドロップ用の DROP_ICON_GAP/DROP_ICON_Y_OFFSET をそのまま再利用し、
    # レア専用の定数は新設しない
    # RARE 項目の想定最大文字数はラベルを除いた数値部分のみ（クリア必要数
    # RARE_DROP_CLEAR_TARGET が分子・分母の最大値になるため
    # "20/20" の5文字。RARE_NUMBER_MAX_CHARS として上で定義済み）

    @classmethod
    def _status_item_x(cls):
        """各項目（HP/DROP/RARE）の描画開始x（カメラオフセットからの
        相対値）を返す。左詰めで、直前の項目の表示幅 + STATUS_ITEM_GAP
        ぶんだけ右へ積み上げる。HP はハートアイコン列の表示幅
        （HEART_ITEM_W）、DROP・RARE はいずれもアイコン幅+すき間+数値部分の
        想定最大幅（GameCore.DROP_W + DROP_ICON_GAP + (DROP|RARE)_NUMBER_
        MAX_CHARS×TEXT_CHAR_W−1px）を項目の表示幅とする（末尾の送り分は
        実際の描画幅に含まれないため−1px）。HP→DROP間の余白のみ
        STATUS_DROP_GROUP_OFFSET ぶん追加で広げ、DROP・RARE表示をまとめて
        右へずらす（プレイテスト指摘対応）。3項目合計でも SCREEN_WIDTH
        （150px）に収まる（HP:2px開始、DROP:41px開始、RARE:94px開始+
        最大想定幅25px=119px で画面内に収まる）"""
        widths = (
            cls.HEART_ITEM_W,
            GameCore.DROP_W
            + cls.DROP_ICON_GAP
            + cls.DROP_NUMBER_MAX_CHARS * cls.TEXT_CHAR_W
            - 1,
            GameCore.DROP_W
            + cls.DROP_ICON_GAP
            + cls.RARE_NUMBER_MAX_CHARS * cls.TEXT_CHAR_W
            - 1,
        )
        gaps = (
            cls.STATUS_ITEM_GAP + cls.STATUS_DROP_GROUP_OFFSET,
            cls.STATUS_ITEM_GAP,
        )
        positions = []
        x = cls.STATUS_TEXT_OFFSET
        for i, width in enumerate(widths):
            positions.append(x)
            if i < len(gaps):
                x += width + gaps[i]
        return positions

    # --- 終了ポップアップ（"CLEAR"／"GAME OVER"）の表示仕様（ID-016-9 の
    # Red で決定した具体値。ID-016-12 で "GAME OVER" ケースを追加する際、
    # "CLEAR" 専用だった TestGameClearPopupDraw から2クラス共通の土台へ
    # 移動した。位置・大きさは参考実装 pyxel_sort_water ID-005 のポップアップ
    # 定数を同じ画面サイズ 150×200 のため流用し、背景色はステータス HUD と
    # 同じ色1（濃い青。テキストの白と視認性を確保できることを確認済みの
    # 組み合わせ）とする ---
    END_POPUP_X = 25
    END_POPUP_Y = 85
    END_POPUP_W = 100
    END_POPUP_H = 30
    END_POPUP_COLOR = 1
    # Pyxel 標準フォントの文字送り幅・グリフ高（テキスト中央寄せの計算に使う）
    TEXT_CHAR_W = 4
    TEXT_GLYPH_H = 5
    # 終了ポップアップ2行目（再起動案内）の行間・文言。参考実装
    # pyxel_sort_water/ID-005 の RESTART_TEXT／LINE_GAP と同じ値を流用する
    END_POPUP_LINE_GAP = 4
    RESTART_TEXT = "CLICK TO RESTART"

    # --- 移動モード切り替えボタンの表示仕様（requirements.md §3.1「画面
    # 右下に移動モード切り替えボタンを表示する」。ID-020-2 の Red で決定
    # した具体値。サイクル1では移動モードの状態を導入せず、常に自動戦闘
    # モードのアイコンを固定描画していたが、サイクル2（ID-020-5）で状態に
    # 応じたアイコン切替を導入する）---
    # 画像アセットは登録済みの layer0（他スプライトと同じバンク0）の
    # 自動攻撃モードアイコン（起点 (16,16)、6×8。tasks.md 描画アセット表・
    # ID-020-1 で確認済み）
    MODE_BUTTON_IMG = 0
    MODE_BUTTON_ATTACK_U = 16
    MODE_BUTTON_ATTACK_V = 16
    # 自動収集モードアイコン（起点 (24,16)、6×8。自動攻撃モードアイコンと
    # 同じバンク・サイズで、起点のみ異なる。tasks.md 描画アセット表・
    # ID-020-1 で確認済み。ID-020-5 の Red で決定）
    MODE_BUTTON_COLLECT_U = 24
    MODE_BUTTON_COLLECT_V = 16
    # 目的地移動モードアイコンは新規アセットを追加せず、既存の目的地の旗
    # （layer0 起点 (8, 16)、6×8。GameCore.FLAG_U/V と同じ座標）を流用する
    # （ユーザー決定 2026-07-25、ID-022 サイクル5）
    MODE_BUTTON_DESTINATION_U = 8
    MODE_BUTTON_DESTINATION_V = 16
    MODE_BUTTON_ICON_W = 6
    MODE_BUTTON_ICON_H = 8
    # ボタンの円形背景の半径・色。自動戦闘モードの色はステータス HUD・
    # 終了ポップアップの色1（濃い青）とは別の色2（濃い赤）とし、他の HUD
    # 要素と見分けやすくする（2026-07-22 ユーザー指示）。自動収集モードの
    # 色は色3（緑）とする（2026-07-23 ユーザー指示、ID-020-7追加対応）。
    # 目的地移動モードの色は青（色5）とする（ユーザー決定 2026-07-25、
    # ID-022 サイクル5）
    MODE_BUTTON_RADIUS = 12
    MODE_BUTTON_COLOR_ATTACK = 2
    MODE_BUTTON_COLOR_COLLECT = 3
    MODE_BUTTON_COLOR_DESTINATION = 5
    # 円の外周に重ねる白枠の色（2026-07-22 ユーザー指示: フィールドと
    # ボタンの境界を見やすくするため）。テキストの色7（白・PyxelView 固定）
    # と同じ色を使い、既存の白系配色と統一する
    MODE_BUTTON_BORDER_COLOR = 7
    # 円の外周と画面右端・下端の間に空ける余白。ステータス HUD が画面左端に
    # ぴったりくっつくのに対し、円形のボタンは縁が画面端に接すると窮屈に
    # 見えるため余白を設ける
    MODE_BUTTON_MARGIN = 10
    # 円の中心座標（画面右下）＝ 画面端 − 余白 − 半径
    MODE_BUTTON_CENTER_X = (
        GameCore.SCREEN_WIDTH - MODE_BUTTON_MARGIN - MODE_BUTTON_RADIUS
    )
    MODE_BUTTON_CENTER_Y = (
        GameCore.SCREEN_HEIGHT - MODE_BUTTON_MARGIN - MODE_BUTTON_RADIUS
    )
    # アイコンは重心が円の中心と一致するよう、中心からアイコン幅・高さの
    # 半分だけ左上へずらした位置に描画する。X はさらに +1px
    # （2026-07-23 プレイテストでアイコンがわずかに左寄りに見えると指摘され、
    # 見た目の中央寄せを補正するための微調整。境界条件ではなく見た目の
    # 微調整のため式の意味は変えず定数のみ補正する）
    MODE_BUTTON_ICON_X = MODE_BUTTON_CENTER_X - MODE_BUTTON_ICON_W // 2 + 1
    MODE_BUTTON_ICON_Y = MODE_BUTTON_CENTER_Y - MODE_BUTTON_ICON_H // 2
    # ボタンの当たり判定矩形（ID-020-5 の Red で決定）: 円周ちょうどの判定は
    # プレイ中に体感できる差ではなく境界条件をテストで固定する意義が薄い
    # ため、既存の _is_end_popup_clicked() と同型の矩形判定
    # （X<=mouse_x<X+W かつ Y<=mouse_y<Y+H の半開区間）を採用し、判定対象は
    # 円の外接矩形とする
    MODE_BUTTON_RECT_X = MODE_BUTTON_CENTER_X - MODE_BUTTON_RADIUS
    MODE_BUTTON_RECT_Y = MODE_BUTTON_CENTER_Y - MODE_BUTTON_RADIUS
    MODE_BUTTON_RECT_W = MODE_BUTTON_RADIUS * 2
    MODE_BUTTON_RECT_H = MODE_BUTTON_RADIUS * 2

    def _mode_button_draw_calls(self, camera=(0, 0), mode="attack"):
        """カメラオフセット camera の下で、移動モード切り替えボタン
        （画面右下の円形背景 → フィールドとの境界を見やすくする白枠 →
        中心に重ねたアイコンの順）がスクリーン固定位置へ描画される場合の
        期待呼び出しリストを返す（ステータス HUD・終了ポップアップと同様、
        スクリーン固定表示のためワールド座標＝カメラオフセット + スクリーン
        座標で描画される）。mode は "attack"（自動戦闘。既定値）／
        "collect"（自動収集）／"destination"（目的地移動、ID-022 サイクル5で
        追加）で、状態に応じて中心に重ねるアイコンの起点座標が切り替わる
        （ID-020-5 の Red で導入）。円形背景の色もモードに応じて切り替わる
        （自動戦闘=色2/自動収集=色3/目的地移動=色5、ID-020-7・ID-022で追加。
        白枠はモードによらず共通のまま）"""
        if mode == "collect":
            icon_u, icon_v = self.MODE_BUTTON_COLLECT_U, self.MODE_BUTTON_COLLECT_V
            button_color = self.MODE_BUTTON_COLOR_COLLECT
        elif mode == "destination":
            icon_u, icon_v = (
                self.MODE_BUTTON_DESTINATION_U,
                self.MODE_BUTTON_DESTINATION_V,
            )
            button_color = self.MODE_BUTTON_COLOR_DESTINATION
        else:
            icon_u, icon_v = self.MODE_BUTTON_ATTACK_U, self.MODE_BUTTON_ATTACK_V
            button_color = self.MODE_BUTTON_COLOR_ATTACK
        return [
            (
                "draw_circ",
                camera[0] + self.MODE_BUTTON_CENTER_X,
                camera[1] + self.MODE_BUTTON_CENTER_Y,
                self.MODE_BUTTON_RADIUS,
                button_color,
            ),
            (
                "draw_circb",
                camera[0] + self.MODE_BUTTON_CENTER_X,
                camera[1] + self.MODE_BUTTON_CENTER_Y,
                self.MODE_BUTTON_RADIUS,
                self.MODE_BUTTON_BORDER_COLOR,
            ),
            (
                "draw_blt",
                camera[0] + self.MODE_BUTTON_ICON_X,
                camera[1] + self.MODE_BUTTON_ICON_Y,
                self.MODE_BUTTON_IMG,
                icon_u,
                icon_v,
                self.MODE_BUTTON_ICON_W,
                self.MODE_BUTTON_ICON_H,
                0,
                0,
            ),
        ]

    def _expected_end_popup_calls(self, text, camera=(0, 0)):
        """カメラオフセット camera の下で、終了ポップアップ（背景矩形 →
        中央寄せの text → 中央寄せの再起動案内）がスクリーン固定位置へ
        描画される場合の期待呼び出しリストを返す（スクリーン固定表示のため
        ワールド座標＝カメラオフセット + スクリーン座標で描画される。
        ステータス HUD と同じ考え方）。2行（text／RESTART_TEXT）はブロック
        としてポップアップ縦中央に配置される（pyxel_sort_water/ID-005 の
        _draw_clear_popup と同じレイアウト計算）"""
        lines = (text, self.RESTART_TEXT)
        block_h = len(lines) * self.TEXT_GLYPH_H + (len(lines) - 1) * (
            self.END_POPUP_LINE_GAP
        )
        top_y = self.END_POPUP_Y + self.END_POPUP_H // 2 - block_h // 2
        expected = [
            (
                "draw_rect",
                camera[0] + self.END_POPUP_X,
                camera[1] + self.END_POPUP_Y,
                self.END_POPUP_W,
                self.END_POPUP_H,
                self.END_POPUP_COLOR,
            ),
        ]
        for i, line in enumerate(lines):
            line_w = len(line) * self.TEXT_CHAR_W
            line_x = self.END_POPUP_X + self.END_POPUP_W // 2 - line_w // 2
            line_y = top_y + i * (self.TEXT_GLYPH_H + self.END_POPUP_LINE_GAP)
            expected.append(("draw_text", camera[0] + line_x, camera[1] + line_y, line))
        return expected

    def _assert_drawn_last(self, expected_calls):
        """描画呼び出し全体の末尾が期待する呼び出し列と一致することを検証
        する（TestStatusDraw の末尾検証と同じ考え方。末尾以外のワールド
        要素の描画は既存の描画結線テストで固定済みのためここでは扱わない）"""
        actual_tail = self.test_view.get_call_params()[-len(expected_calls) :]
        message = (
            f"描画呼び出し（末尾）が期待値と異なる:\n"
            f"期待: {expected_calls}\n実際: {actual_tail}"
        )
        self.assertEqual(expected_calls, actual_tail, message)

    def setUp(self):
        self.test_view = TestView()
        self.test_input = TestInput()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        # ゲーム開始時のモブ出現位置の乱数を決定的な値（プレイヤー真上の x）に
        # 固定する（モブ出現仕様自体の検証は test_field.py の
        # TestMobSpawnAtStart で実施）
        self.patcher_uniform = patch(
            "src.main.random.uniform", return_value=float(self.INITIAL_MOB_X)
        )
        self.mock_view = self.patcher_view.start()
        self.mock_input = self.patcher_input.start()
        self.mock_uniform = self.patcher_uniform.start()

    def tearDown(self):
        self.patcher_uniform.stop()
        self.patcher_input.stop()
        self.patcher_view.stop()

    def _expected_calls_for_player_at(self, player_x, player_y, player_rotate=0):
        """clear によるフレーム初期化（カメラ設定＋画面クリア）後、カメラで見えている
        範囲を隙間なく覆うフィールドタイルを敷き詰め、プレイヤーをワールド座標
        (player_x, player_y) へ回転角度 player_rotate（rotate 引数。0＝回転なし）で
        描画する場合のビュー呼び出しリスト（順序含む）を返す。フィールドタイルは
        常に回転なしで描画される"""
        # カメラオフセット = プレイヤーのワールド座標 - 画面中央のスクリーン座標。
        # これによりプレイヤーはワールド座標によらず常に画面中央付近に描画され続ける
        camera_x = player_x - (GameCore.SCREEN_WIDTH - GameCore.PLAYER_W) // 2
        camera_y = player_y - (GameCore.SCREEN_HEIGHT - GameCore.PLAYER_H) // 2
        # フィールドタイルはワールド座標のタイル格子（FIELD_TILE_W/H の倍数座標）に
        # 沿って敷き詰められ、カメラで見えている範囲
        # [camera, camera + SCREEN) を覆うのに必要な格子範囲（可視範囲の両端の
        # 画素を含むタイルまで）だけ繰り返し描画される
        first_col = camera_x // GameCore.FIELD_TILE_W
        last_col = (camera_x + GameCore.SCREEN_WIDTH - 1) // GameCore.FIELD_TILE_W
        first_row = camera_y // GameCore.FIELD_TILE_H
        last_row = (camera_y + GameCore.SCREEN_HEIGHT - 1) // GameCore.FIELD_TILE_H
        expected_calls = [("clear", camera_x, camera_y)]
        expected_calls += [
            (
                "draw_blt",
                col * GameCore.FIELD_TILE_W,
                row * GameCore.FIELD_TILE_H,
                GameCore.FIELD_IMG,
                GameCore.FIELD_TILE_U,
                GameCore.FIELD_TILE_V,
                GameCore.FIELD_TILE_W,
                GameCore.FIELD_TILE_H,
                0,
                0,
            )
            for row in range(first_row, last_row + 1)
            for col in range(first_col, last_col + 1)
        ]
        expected_calls.append(
            (
                "draw_blt",
                player_x,
                player_y,
                GameCore.PLAYER_IMG,
                GameCore.PLAYER_U,
                GameCore.PLAYER_V,
                GameCore.PLAYER_W,
                GameCore.PLAYER_H,
                0,
                player_rotate,
            )
        )
        return expected_calls

    def _mob_draw_call(self, mob_x, mob_y, mob_rotate):
        return (
            "draw_blt",
            mob_x,
            mob_y,
            GameCore.MOB_IMG,
            GameCore.MOB_U,
            GameCore.MOB_V,
            GameCore.MOB_W,
            GameCore.MOB_H,
            0,
            mob_rotate,
        )

    def _bullet_draw_call(self, bullet_x, bullet_y):
        """弾の期待描画呼び出しを返す（弾は進行方向を内部に持つが、小さい
        スプライトを回転させると画像が歪むため、向きによらず回転なしで
        描画される）"""
        return (
            "draw_blt",
            bullet_x,
            bullet_y,
            GameCore.BULLET_IMG,
            GameCore.BULLET_U,
            GameCore.BULLET_V,
            GameCore.BULLET_W,
            GameCore.BULLET_H,
            0,
            0,
        )

    def _drop_draw_call(self, drop_x, drop_y, is_rare):
        """ドロップの登録座標 (drop_x, drop_y)（撃破されたモブと画像中心を
        揃えた位置）に描画されるドロップの期待描画呼び出しを返す（地面に
        落ちている拾い物のため回転なし。レアは同じ画像バンク・サイズのまま
        U/V のみ異なるアセットで描画される）"""
        return (
            "draw_blt",
            drop_x,
            drop_y,
            GameCore.DROP_IMG,
            GameCore.RARE_DROP_U if is_rare else GameCore.DROP_U,
            GameCore.RARE_DROP_V if is_rare else GameCore.DROP_V,
            GameCore.DROP_W,
            GameCore.DROP_H,
            0,
            0,
        )

    def _flag_draw_call(self, dest_x, dest_y):
        """目的地（タップ位置）のワールド座標 (dest_x, dest_y) に根本
        （ローカル座標 (GameCore.FLAG_BASE_X, GameCore.FLAG_BASE_Y)）が一致
        するよう描画される目的地の旗の期待描画呼び出しを返す（向きを持たない
        地面の目印のため回転なし。プレイヤーは画像中心点が目的地へ向かって
        移動するため、到着時に中心点が旗の根本と一致する）"""
        return (
            "draw_blt",
            dest_x - GameCore.FLAG_BASE_X,
            dest_y - GameCore.FLAG_BASE_Y,
            GameCore.FLAG_IMG,
            GameCore.FLAG_U,
            GameCore.FLAG_V,
            GameCore.FLAG_W,
            GameCore.FLAG_H,
            0,
            0,
        )

    @staticmethod
    def _next_normal_drop_threshold(normal):
        """累計取得数 normal に対する「次のレベルの累計しきい値」を返す
        （しきい値の系列 10×(2^level−1)、level=1..8。Field.
        next_normal_drop_threshold の期待値と同じ計算式。成長上限
        （レベル8＝累計2550個）到達後は次のしきい値が存在しないため
        None を返す）"""
        thresholds = (10 * (2**level - 1) for level in range(1, 9))
        return next((t for t in thresholds if normal < t), None)

    def _expected_status_calls(self, camera=(0, 0), hp=None, normal=0, rare=0):
        """カメラオフセット camera の下で、ステータス3項目（HP・通常ドロップ数・
        レアドロップ数）が画面左上の固定スクリーン位置へ、画面幅いっぱいの
        単一の背景矩形（項目間・内部にすき間なし。右側だけ空いて不自然に
        見えないよう画面右端まで覆う）→ HP のハートアイコン → 通常ドロップ
        アイコン＋数値テキスト → レアドロップアイコン＋数値テキストの順で
        横1行に並んで描画される場合の期待呼び出しリストを返す。clear() が
        カメラを設定するため、スクリーン座標に固定表示するにはワールド座標＝
        カメラオフセット + スクリーン座標で描画される。hp の既定値は
        Player.INITIAL_HP（HP は Player が保持し Field は委譲するのみ
        （ID-013-20）のため、具体値はゲームバランスの詳細として
        test_field.py と同様に定数参照で表す）"""
        if hp is None:
            hp = Player.INITIAL_HP
        # DROP は「累計取得数/次のレベルの累計しきい値」形式（ID-013
        # サイクル7）。ラベル文字（"DROP:"）は ID-019 でアイコンに置き
        # 換えたため、数値部分のみの文字列にする（requirements.md §4）。
        # 次のしきい値が存在しない（成長上限到達後）場合は「次がない」ことを
        # 表す文字として "-" を使う。RARE も ID-019 サイクル2（ID-019-5）で
        # 同様にラベル文字（"RARE:"）をアイコンへ置き換えたため、数値部分の
        # みの文字列にする。右側はレベルのしきい値ではなくゲームクリアに
        # 必要な累計数固定 Field.RARE_DROP_CLEAR_TARGET（ID-016-15）
        threshold = self._next_normal_drop_threshold(normal)
        threshold_text = "-" if threshold is None else str(threshold)
        drop_number_text = f"{normal}/{threshold_text}"
        rare_number_text = f"{rare}/{Field.RARE_DROP_CLEAR_TARGET}"
        # 背景は画面幅いっぱいの単一の矩形（項目間にすき間を作らないことで
        # フィールドタイルの描画がちらついて見える問題を避け、右端まで
        # 覆うことで右側だけ空く不自然さを避ける）
        calls = [
            (
                "draw_rect",
                camera[0],
                camera[1],
                self.STATUS_RECT_W,
                self.STATUS_RECT_H,
                self.STATUS_RECT_COLOR,
            )
        ]
        item_x = self._status_item_x()
        # HP はテキストではなくハートアイコンで表示する（requirements.md
        # §4）。左から hp 個ぶん赤ハート、残りは灰色ハートへ切り替えて
        # 横に並べる。HP 項目の開始xから左詰めで HEART_GAP のすき間を
        # あけて並べる。縦位置は HEART_Y_OFFSET を使う（テキストと同じ
        # STATUS_TEXT_OFFSET だと矩形内で上寄りに見えるという人間
        # プレイテスト指摘により、テキストとは別のy座標に改訂）
        calls += [
            (
                "draw_blt",
                camera[0] + item_x[0] + i * (self.HEART_W + self.HEART_GAP),
                camera[1] + self.HEART_Y_OFFSET,
                self.HEART_IMG,
                self.HEART_GRAY_U if i >= hp else self.HEART_U,
                self.HEART_GRAY_V if i >= hp else self.HEART_V,
                self.HEART_W,
                self.HEART_H,
                0,
                0,
            )
            for i in range(Player.INITIAL_HP)
        ]
        # 通常ドロップ数・レアドロップ数はいずれもアイコン（フィールド描画と
        # 同じ GameCore.DROP_IMG/DROP_W/DROP_H、起点座標のみ通常は DROP_U/
        # DROP_V、レアは RARE_DROP_U/RARE_DROP_V）＋数値のみのテキストで
        # 表示する。アイコンは各項目の開始xへ、数値テキストはアイコン幅 +
        # DROP_ICON_GAP ぶん右へずらして続けて描画する（すき間・縦位置は
        # 両者共通の DROP_ICON_GAP/DROP_ICON_Y_OFFSET を使う。実装
        # `_draw_status()` 側も同じ考え方でDROP/RAREを1ループへ統合して
        # いるため、期待値生成もそれに揃えて1ループにまとめる）
        for pos, drop_u, drop_v, number_text in (
            (item_x[1], GameCore.DROP_U, GameCore.DROP_V, drop_number_text),
            (item_x[2], GameCore.RARE_DROP_U, GameCore.RARE_DROP_V, rare_number_text),
        ):
            calls.append(
                (
                    "draw_blt",
                    camera[0] + pos,
                    camera[1] + self.DROP_ICON_Y_OFFSET,
                    GameCore.DROP_IMG,
                    drop_u,
                    drop_v,
                    GameCore.DROP_W,
                    GameCore.DROP_H,
                    0,
                    0,
                )
            )
            calls.append(
                (
                    "draw_text",
                    camera[0] + pos + GameCore.DROP_W + self.DROP_ICON_GAP,
                    camera[1] + self.STATUS_TEXT_OFFSET,
                    number_text,
                )
            )
        return calls

    def _assert_field_and_player_drawn(
        self,
        player_x,
        player_y,
        player_rotate=0,
        mobs=(),
        flag=None,
        bullets=(),
        drops=(),
        player_drawn=True,
        mode="attack",
    ):
        """clear・フィールド・(flag で指定した目的地の旗)・(drops で指定した
        各ドロップ)・(bullets で指定した各弾)・(mobs で指定した各モブ)・
        プレイヤーの順で描画されることを検証する。mobs は
        (mob_x, mob_y, mob_rotate) のリストで、モブが存在しない場合
        （例: 移動検証の対象外としたい場合）は空のまま呼び出す。bullets は
        (bullet_x, bullet_y) のリスト（弾は回転なしで描画されるため回転は
        指定しない）で、弾が存在しない場合は空のまま呼び出す。drops は
        (drop_x, drop_y, is_rare) のリストで、ドロップは地面に落ちている
        拾い物のため旗と同じく actor（弾・モブ・プレイヤー）より奥に描画
        される。flag は目的地のワールド座標 (dest_x, dest_y) で、目的地
        移動中でない場合は None のまま呼び出す。player_drawn=False は
        無敵時間中の点滅の非表示フレームでプレイヤーの描画のみが省略される
        ことを検証する場合に指定する（player_x/player_y はカメラオフセット・
        フィールドタイル範囲・ステータス HUD 位置の期待値計算に引き続き
        使われる）。mode は移動モード切り替えボタンのアイコン・色の期待値
        （"attack"／"collect"／"destination"、_mode_button_draw_calls へ
        そのまま渡す）で、自動収集モード・目的地移動モードへ切り替えた
        状態の描画を検証する場合に指定する"""
        expected_calls = self._expected_calls_for_player_at(
            player_x, player_y, player_rotate
        )
        player_call = expected_calls.pop()
        if flag is not None:
            expected_calls.append(self._flag_draw_call(*flag))
        expected_calls += [self._drop_draw_call(*drop) for drop in drops]
        expected_calls += [self._bullet_draw_call(*bullet) for bullet in bullets]
        expected_calls += [self._mob_draw_call(*mob) for mob in mobs]
        if player_drawn:
            expected_calls.append(player_call)
        # ステータス HUD は全ワールド要素の後（最前面）に、スクリーン固定
        # 位置（カメラオフセット + スクリーン座標）へ描画される。値は既定
        # （HP 初期値・カウント 0）を期待する（値の追従・カメラ追従の観点は
        # TestStatusDraw が担う）
        expected_calls += self._expected_status_calls(
            camera=self._camera_offset_at((player_x, player_y))
        )
        # 移動モード切り替えボタンはステータス HUD の直後に描画される
        # 常時表示の HUD 要素（ID-020-2）
        expected_calls += self._mode_button_draw_calls(
            camera=self._camera_offset_at((player_x, player_y)), mode=mode
        )
        actual_calls = self.test_view.get_call_params()
        message = (
            f"描画呼び出しの順序・パラメータが期待値と異なる:\n"
            f"期待: {expected_calls}\n実際: {actual_calls}"
        )
        # rotate は GameCore が ROTATE_SNAP_STEP（22.5度）の倍数へスナップした
        # 値で draw_blt へ渡される（22.5 の倍数は 2 進浮動小数点で正確に表現
        # できる）ため、期待値側も同じ丸めをすれば浮動小数点の角度計算を経ても
        # 完全一致で比較できる
        self.assertEqual(expected_calls, actual_calls, message)

    def _camera_offset_at(self, player_pos):
        # カメラオフセット = プレイヤーのワールド座標 - 初期座標（画面中央固定のため）
        return (
            player_pos[0] - self.INITIAL_PLAYER_X,
            player_pos[1] - self.INITIAL_PLAYER_Y,
        )

    # タップ前に前進してカメラオフセットを 0 以外にするフレーム数
    # （スクリーン→ワールド変換が恒等変換にならない状態を作るため。
    # PLAYER_SPEED（0.5）との積が整数になる値を選び、少数の蓄積誤差なく
    # 期待値を計算できるようにする）
    PRE_TAP_FRAMES = 10

    def _expected_pos(self, start, diff, frames):
        # 進行方向は目的地ワールド座標とプレイヤー中心点の差分ベクトル diff を
        # 正規化した単位ベクトル。期待値（登録座標）は「開始座標 + フレーム数 ×
        # 速度 × 単位ベクトル」を丸めて求める
        # （Actor 単体テスト test_actor.py と同一の計算式）
        dist = math.hypot(*diff)
        return (
            round(start[0] + frames * Field.PLAYER_SPEED * diff[0] / dist),
            round(start[1] + frames * Field.PLAYER_SPEED * diff[1] / dist),
        )

    def _expected_rotate(self, diff):
        # 進行方向（差分の正規化単位ベクトル）に対応する描画時の回転角度
        # （0度=上方向・時計回りが正、GameCore が最も近い22.5度の倍数へ
        # 丸めた値）。角度規約自体は Actor 単体テスト（test_actor.py の
        # TestActorRotateAngle）で、丸め方法自体は GameCore の結線検証
        # （TestPlayerRotateDraw）で自明値によりそれぞれ検証済みのため、
        # ここでは期待値の表現として単位ベクトルからの変換式を用いる
        dist = math.hypot(*diff)
        raw_angle = math.degrees(math.atan2(diff[0] / dist, -diff[1] / dist))
        return round(raw_angle / 22.5) * 22.5

    def _tapped_dest(self, player_pos, diff):
        """プレイヤー（登録座標 player_pos）の画像中心点から差分 diff の
        目的地ワールド座標（タップ位置）を返す（turn_to の方向基準点が
        画像中心点のため、目的地・旗の期待値は中心点基準で計算する）"""
        return (
            player_pos[0] + self.PLAYER_CENTER_OFFSET_X + diff[0],
            player_pos[1] + self.PLAYER_CENTER_OFFSET_Y + diff[1],
        )

    def _tap_at_world(self, player_pos, diff):
        """プレイヤーの画像中心点から差分 diff のワールド座標を目的地として、
        そのスクリーン座標（world - camera_offset）をタップ状態として注入する"""
        camera = self._camera_offset_at(player_pos)
        dest = self._tapped_dest(player_pos, diff)
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(dest[0] - camera[0])
        self.test_input.set_mouse_y(dest[1] - camera[1])

    def _release_tap(self):
        self.test_input.set_btn_pressed(False)

    def _press_button_center(self):
        """移動モード切り替えボタンの中心（当たり判定矩形の明確な内側）を
        タップ状態として注入する（スクリーン固定表示のため、カメラオフセットに
        よらずスクリーン座標をそのまま指定する）"""
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(self.MODE_BUTTON_CENTER_X)
        self.test_input.set_mouse_y(self.MODE_BUTTON_CENTER_Y)


class TestFieldTileDraw(TestParent):
    def test_field_and_player_are_drawn_in_order(self):
        """GameCore.draw() が clear でフレームを初期化した後、フィールドを敷き詰め、
        プレイヤーを画面中央付近に描画すること（順序含む）"""
        core = GameCore()
        core.draw()
        self._assert_field_and_player_drawn(
            (GameCore.SCREEN_WIDTH - GameCore.PLAYER_W) // 2,
            (GameCore.SCREEN_HEIGHT - GameCore.PLAYER_H) // 2,
            mobs=[self.INITIAL_MOB],
        )

    def test_flag_drop_and_bullet_are_drawn_between_field_and_mobs(self):
        """タップで目的地が設定され、ドロップ・発射済みの弾が存在する状態の
        draw() で、clear によるフレーム初期化の後、フィールド → 旗 →
        ドロップ → 弾 → モブ → プレイヤーの順で描画されること
        （旗・ドロップ・弾・モブがそろった全描画要素の順序をこのテストで
        固定する。ドロップは地面に落ちている拾い物のため、地面の目印である
        旗の直後＝弾・モブ・プレイヤーより奥）"""
        # テストデータの前提: 1回の方向転換（最大 MAX_TURN_ANGLE）がスナップ
        # 単位の半分未満で、注入モブの描画回転が 0.0 のままであること
        self.assertLess(Mob.MAX_TURN_ANGLE, GameCore.ROTATE_SNAP_STEP / 2)
        core = GameCore()
        # モブの移動を期待値へ持ち込まないよう、開始時の1匹に代えて速度 0 の
        # モブを画面内（プレイヤーの右）へ注入する
        mob_pos = (self.INITIAL_PLAYER_X + 20, self.INITIAL_PLAYER_Y)
        # Mob のコンストラクタは中心点を受け取るため、mob_pos（登録座標）から
        # 画像サイズの半分を足して変換する
        core._field._mobs = [  # pylint: disable=W0212
            Mob(mob_pos[0] + Mob.WIDTH / 2, mob_pos[1] + Mob.HEIGHT / 2, 0)
        ]
        # 発射契機（発射間隔の経過）を待たずに描画順序のみを検証するため、
        # 速度 0 の弾を画面内（プレイヤーの左）へ注入する（発射された弾の
        # 描画自体は TestBulletDraw で検証する）。コンストラクタの座標変換は
        # モブと同様
        bullet_pos = (self.INITIAL_PLAYER_X - 20, self.INITIAL_PLAYER_Y)
        core._field._bullets = [  # pylint: disable=W0212
            Bullet(
                bullet_pos[0] + Bullet.WIDTH / 2, bullet_pos[1] + Bullet.HEIGHT / 2, 0
            )
        ]
        # 撃破の契機（弾・モブの重なり）を待たずに描画順序のみを検証するため、
        # ドロップ（通常）を画面内（プレイヤーの下）へ直接注入する（撃破に
        # よる生成契機・種別ごとのアセットの検証はそれぞれ test_field.py /
        # TestDropDraw が担う）。ドロップは移動しないため位置はそのまま保たれる
        drop_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y + 30)
        core._field._drops = [  # pylint: disable=W0212
            Drop(drop_pos[0] + Drop.WIDTH / 2, drop_pos[1] + Drop.HEIGHT / 2, 0, False)
        ]
        # 目的地はプレイヤーの進行方向（上）の真上とし、タップの前後で進行
        # 方向が変わらない（期待座標が上方向への直進のままになる）ようにする
        initial_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
        diff = (0, -60)
        self._tap_at_world(initial_pos, diff)
        core.update()  # タップを検知したフレーム（目的地の記録と前進）
        self._release_tap()

        core.draw()

        self._assert_field_and_player_drawn(
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - Field.PLAYER_SPEED),
            mobs=[(*mob_pos, 0.0)],
            flag=self._tapped_dest(initial_pos, diff),
            bullets=[bullet_pos],
            drops=[(*drop_pos, False)],
            mode="destination",
        )


class TestMobDraw(TestParent):
    """自然に出現したモブの描画の e2e スタイルテスト（IF: フレーム経過による
    自動出現・描画呼び出し。`TestBulletDraw` と同じ構成: 手動注入ではなく
    出現間隔の経過という自然な契機でモブを用意する）

    仕様（このテストで固定する）:
    - 出現間隔（Field.MOB_SPAWN_INTERVAL 回の update()）の経過で自動出現
      したモブが、出現時点の位置・向き（GameCore がスナップした値）で
      描画される

    出現位置・出現辺選択のロジックそのものは test_field.py
    （TestMobPeriodicSpawn/TestMobSpawnEdgeByPlayerDirection）で固定済みの
    ため、ここでは扱わない。スナップ処理自体の境界ケース網羅は
    TestPlayerRotateDraw で担保済みのため、ここでは `_draw_mobs()` も同じ
    `_draw_actor()` を経由してスナップされることを確認するに留める"""

    def test_naturally_spawned_mob_is_drawn_with_snapped_rotate_angle(self):
        """出現間隔ぶんのフレーム経過で自動出現したモブが、出現時点の
        出現位置・向きに対応する回転角度で描画されること"""
        test_cases = [
            # (名前, 出現前のタップ差分。None はタップなし＝初期の真上への
            # 直進のまま上辺から出現し、出現位置がプレイヤーの真上のため
            # 回転は自明な180度になる)
            ("タップなしでは上辺出現・回転180度で描画される", None),
            # 出現位置のランダム座標は setUp で INITIAL_MOB_X に固定されて
            # いる（TestParent.patcher_uniform）ため、右辺出現となる斜め
            # 方向のタップ後は、出現時点のプレイヤー位置と出現位置がずれ、
            # 22.5度単位ではない生の角度（約-112.46度）で出現する
            ("斜め方向のタップ後は右辺出現・スナップされた回転で描画される", (40, 30)),
        ]
        for name, tap_diff in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                # 開始時の1匹は本テストの検証対象外のため除去する（出現
                # タイマーは Field 自身が持つため、除去してもタイマーには
                # 影響しない）
                core._field._mobs = []  # pylint: disable=W0212
                initial_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                if tap_diff is not None:
                    self._tap_at_world(initial_pos, tap_diff)
                core.update()  # 最初のフレーム（タップ時は方向転換して前進）
                self._release_tap()
                # 出現間隔の経過まで（最初のフレームを含め interval 回）
                # 進める（出現は process_frame() 末尾のため、出現フレームの
                # モブはまだ移動していない状態のまま描画される）
                for _ in range(Field.MOB_SPAWN_INTERVAL - 1):
                    core.update()
                # 弾の描画は本テストの検証対象外のため、update() ループが
                # 発射間隔（Player.BULLET_SHOOT_INTERVAL）をまたいで自然
                # 発射された弾を draw() 直前に除去する（モブの除去と同じ扱い）
                core._field._bullets = []  # pylint: disable=W0212

                core.draw()

                diff = tap_diff if tap_diff is not None else (0, -1)
                player_pos = self._expected_pos(
                    initial_pos, diff, Field.MOB_SPAWN_INTERVAL
                )
                camera = self._camera_offset_at(player_pos)
                if tap_diff is None:
                    # 上辺出現: 出現時のランダムX座標は INITIAL_MOB_X に
                    # 固定される
                    mob_pos = (self.INITIAL_MOB_X, camera[1] - Field.MOB_SPAWN_OFFSET)
                else:
                    # 右辺出現: 出現時のランダムY座標も同じ固定値
                    # （INITIAL_MOB_X）になる（乱数モックは呼び出し文脈に
                    # よらず単一の固定値を返すため）
                    mob_pos = (
                        camera[0]
                        + Field.SCREEN_WIDTH
                        - Mob.WIDTH
                        + Field.MOB_SPAWN_OFFSET_SIDE,
                        self.INITIAL_MOB_X,
                    )
                # モブの向きは出現時点でプレイヤーの中心点を瞬時に向く
                # （_spawn_mob() の turn_to()）ため、期待回転は出現位置の
                # 中心点からプレイヤーの中心点への差分で計算する
                mob_center = (mob_pos[0] + Mob.WIDTH / 2, mob_pos[1] + Mob.HEIGHT / 2)
                player_center = (
                    player_pos[0] + self.PLAYER_CENTER_OFFSET_X,
                    player_pos[1] + self.PLAYER_CENTER_OFFSET_Y,
                )
                mob_diff = (
                    player_center[0] - mob_center[0],
                    player_center[1] - mob_center[1],
                )
                self._assert_field_and_player_drawn(
                    *player_pos,
                    player_rotate=self._expected_rotate(diff),
                    mobs=[(*mob_pos, self._expected_rotate(mob_diff))],
                    flag=(
                        self._tapped_dest(initial_pos, tap_diff)
                        if tap_diff is not None
                        else None
                    ),
                    mode="destination" if tap_diff is not None else "attack",
                )


class TestPlayerRotateDraw(TestParent):
    """描画時に Field から取得した回転角度を GameCore がスナップした上で
    IView.draw_blt の rotate 引数へ指定してプレイヤーを描画することの結線を
    検証する e2e スタイルテスト（IF: TestInput によるタップ入力の注入と
    描画呼び出し）

    角度の値自体の規約（0度=上方向・時計回りが正・対角方向の計算を含む）は
    Actor 単体テスト（test_actor.py の TestActorRotateAngle）で検証済みの
    ため、ここでは結線の検証として、期待角度を自明値で表現できる軸沿い方向
    に加え、GameCore 側のスナップ処理が丸め結果を -180度ではなく 180度へ
    読み替える境界（下方向よりわずかに左寄り）を扱う"""

    def test_player_is_drawn_with_rotate_angle_following_direction(self):
        """タップで方向転換した後の draw() で、プレイヤーが進行方向に対応する
        回転角度を rotate 引数へ指定して描画されること（フィールドタイルは
        回転なしのまま）"""
        test_cases = [
            # (名前, 目的地への差分, 期待角度)
            # 期待角度は規約（0度=上方向・時計回りが正）を直接表す自明値
            ("右方向は +90 度", (30, 0), 90.0),
            ("下方向は 180 度", (0, 40), 180.0),
            ("左方向は -90 度", (-30, 0), -90.0),
            # 生の角度は約-177.14度で、単純にスナップ単位へ丸めると規約の
            # 範囲外である -180度になってしまう境界。GameCore 側のスナップ
            # 処理が 180度（同じ向きを表す規約範囲内の値）へ読み替えることを
            # 検証する
            (
                "下方向よりわずかに左寄りは -180 度ではなく 180 度で描画される",
                (-10, 200),
                180.0,
            ),
        ]
        for name, diff, expected_angle in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                # モブの移動は本テストの検証対象外のため除去する
                core._field._mobs = []  # pylint: disable=W0212
                # 初期状態はカメラオフセット 0 のため、スクリーン座標＝ワールド座標
                initial_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                self._tap_at_world(initial_pos, diff)
                core.update()  # タップを検知したフレーム（方向転換して前進）

                core.draw()

                # 期待座標は「開始座標 + フレーム数 × 速度 × 単位ベクトル
                # （中心点からの差分の正規化）」の計算式で表現（軸沿い方向の
                # ため整数移動）。タップにより目的地が設定されるため、目的地の
                # 旗も描画される（ID-007 サイクル2で導入された仕様）
                dist = math.hypot(*diff)
                self._assert_field_and_player_drawn(
                    round(self.INITIAL_PLAYER_X + Field.PLAYER_SPEED * diff[0] / dist),
                    round(self.INITIAL_PLAYER_Y + Field.PLAYER_SPEED * diff[1] / dist),
                    player_rotate=expected_angle,
                    flag=self._tapped_dest(initial_pos, diff),
                    mode="destination",
                )


class TestDestinationFlagDraw(TestParent):
    """タップによる目的地の記録と、目的地の旗の描画の e2e スタイルテスト
    （IF: TestInput によるタップ入力の注入と描画呼び出し）

    仕様（このテストで固定する）:
    - タップ位置（スクリーン座標）をカメラオフセットでワールド座標へ変換した
      位置が目的地として記録され、タップを検知したフレーム以降の draw() で
      目的地の旗が描画される（タップ解除後にプレイヤーが前進してカメラ
      オフセットが変化しても、旗は目的地のワールド座標に固定されたまま）
    - 旗は、根本（画像内ローカル座標 (0, 7)）が目的地のワールド座標と一致
      する位置へ、回転なしで描画される（向きを持たない地面の目印のため）
    - 旗はフィールドの直後（モブ・プレイヤーより奥）に描画される
    - タップ前（目的地未設定の間）は旗は描画されない
    - 目的地移動中に再度タップすると、旗はその新しい目的地（タップ位置を
      ワールド座標へ変換した位置）へ移る（解除はされない。仕様全体は
      test_field.py の TestSecondClickChangesDestination で固定済み）
    - 目的地移動中の自動追尾の抑止・目的地到着による解除は本テストでは固定
      しない（いずれも test_field.py で固定済み。敵なしの状態で検証し、目的地は
      検証フレーム数の前進では到着し得ない十分遠い距離に置く）"""

    def test_no_flag_is_drawn_before_tap(self):
        """タップ（目的地の設定）前のフレームでは目的地の旗が描画されない
        こと（現状の実装でも合格するが、Green の実装が目的地未設定の状態で
        旗を描画してしまわないことを縛る回帰ガードとして置く）"""
        core = GameCore()
        # モブは本テストの検証対象外のため除去する
        core._field._mobs = []  # pylint: disable=W0212
        for _ in range(self.PRE_TAP_FRAMES):
            core.update()

        core.draw()

        self._assert_field_and_player_drawn(
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - self.PRE_TAP_FRAMES * Field.PLAYER_SPEED),
        )

    def test_flag_is_drawn_with_base_at_tapped_world_position(self):
        """タップを検知したフレーム以降の draw() で、タップ位置をワールド座標へ
        変換した目的地に根本（ローカル座標 (0, 7)）が一致するよう、旗が
        フィールドの直後（プレイヤーより奥）に回転なしで描画されること。
        タップ解除後にプレイヤーが前進してカメラオフセットが変化しても、旗は
        目的地のワールド座標に固定されたまま描画され続けること"""
        test_cases = [
            ("タップを検知したフレーム", 1),
            ("タップ解除後の前進でカメラオフセットが変化したフレーム", 10),
        ]
        for name, post_tap_frames in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                # モブは本テストの検証対象外のため除去する
                core._field._mobs = []  # pylint: disable=W0212
                for _ in range(self.PRE_TAP_FRAMES):
                    core.update()
                start = (
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y - self.PRE_TAP_FRAMES * Field.PLAYER_SPEED,
                )
                # 目的地は中心点からの差分が 3:4:5 の直角三角形になるワールド
                # 座標（距離 50。検証フレーム数の前進（最大 5）では到着し得ない
                # 遠さ）
                diff = (30, 40)
                dest = self._tapped_dest(start, diff)
                self._tap_at_world(start, diff)
                core.update()  # タップを検知したフレーム（目的地の記録と方向転換）
                self._release_tap()
                for _ in range(post_tap_frames - 1):
                    core.update()

                core.draw()

                self._assert_field_and_player_drawn(
                    *self._expected_pos(start, diff, post_tap_frames),
                    player_rotate=self._expected_rotate(diff),
                    flag=dest,
                    mode="destination",
                )

    def test_second_tap_moves_flag_to_new_destination(self):
        """目的地移動中に再度タップすると、旗が解除されずその新しい目的地
        （タップ位置をその時点のカメラオフセットでワールド座標へ変換した
        位置）へ移って描画され続けること（3回目のタップでも同様に移ることを
        含める。仕様全体は test_field.py の TestSecondClickChangesDestination
        で固定済み）"""
        first_start = (
            self.INITIAL_PLAYER_X,
            self.INITIAL_PLAYER_Y - self.PRE_TAP_FRAMES * Field.PLAYER_SPEED,
        )
        # 1回目のタップ: 右下 3:4 方向へ 10 フレーム前進し、内部の少数位置が
        # ちょうど整数（＝描画座標と一致）となる地点まで移動しておく
        first_diff = (30, 40)
        second_start = self._expected_pos(first_start, first_diff, 10)
        # 2回目のタップの差分。1回目とは異なる左上方向とし、旗の位置が
        # 更新されたことを期待値との差として観測できるようにする
        second_diff = (-40, -30)
        third_start = self._expected_pos(second_start, second_diff, 10)
        # 3回目のタップ: 右上 4:3 方向のさらに新しい目的地
        third_diff = (40, -30)
        # 1〜3回目のタップ位置・差分（タップ回数分だけ先頭から順に使う）
        taps = [
            (first_start, first_diff),
            (second_start, second_diff),
            (third_start, third_diff),
        ]

        # click_count 回タップした時点の期待値。タップのたびに旗はその
        # タップ位置（新しい目的地）へ移り、向きもその方向へ転換する
        test_cases = [
            (
                "1回目のタップで旗が目的地に描画される",
                1,
                self._expected_pos(first_start, first_diff, 10),
                self._expected_rotate(first_diff),
                self._tapped_dest(first_start, first_diff),
            ),
            (
                "2回目のタップで旗が新しい目的地へ移る",
                2,
                self._expected_pos(second_start, second_diff, 10),
                self._expected_rotate(second_diff),
                self._tapped_dest(second_start, second_diff),
            ),
            (
                "3回目のタップでも旗が新しい目的地へ移る",
                3,
                self._expected_pos(third_start, third_diff, 10),
                self._expected_rotate(third_diff),
                self._tapped_dest(third_start, third_diff),
            ),
        ]
        for name, click_count, expected_pos, expected_rotate, flag in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                # モブは本テストの検証対象外のため除去する
                core._field._mobs = []  # pylint: disable=W0212
                for _ in range(self.PRE_TAP_FRAMES):
                    core.update()
                # click_count 回分のタップを毎回先頭から再現し、他のケースの
                # 実行結果に依存しない独立した状態を作る
                for tap_start, tap_diff in taps[:click_count]:
                    self._tap_at_world(tap_start, tap_diff)
                    core.update()
                    self._release_tap()
                    for _ in range(9):
                        core.update()
                # 弾の描画は本テストの検証対象外のため、update() ループが発射
                # 間隔（BULLET_SHOOT_INTERVAL）をまたいで自然発射された弾を
                # draw() 直前に除去する（モブの除去と同じ扱い）
                core._field._bullets = []  # pylint: disable=W0212
                core.draw()
                self._assert_field_and_player_drawn(
                    *expected_pos,
                    player_rotate=expected_rotate,
                    flag=flag,
                    mode="destination",
                )


class TestFieldTileScroll(TestParent):
    def test_field_tiles_cover_screen_while_scrolling(self):
        """前進によりカメラオフセットが変化しても、フィールドタイルがタイル格子に
        沿って繰り返し描画され、画面全体を隙間なく覆い続けること（タイル1枚分を
        超えるスクロールで描画対象の格子範囲が折り返して進むことを含む・順序含む）"""
        # タイル1枚分（FIELD_TILE_H）を超えて前進するのに必要なフレーム数
        frames_over_one_tile = int(GameCore.FIELD_TILE_H // Field.PLAYER_SPEED) + 1
        test_cases = [
            ("タイル1枚分未満のスクロール", 1),
            ("タイル1枚分を超えるスクロール", frames_over_one_tile),
        ]
        for name, update_count in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                for _ in range(update_count):
                    core.update()
                # モブの出現・移動と弾の発射・撃破で生成されたドロップは
                # 本テストの検証対象外のため、update() ループが出現間隔
                # （MOB_SPAWN_INTERVAL）・発射間隔（BULLET_SHOOT_INTERVAL）を
                # またいでも（自然な命中による撃破・ドロップ生成を含めて）
                # 影響しないよう draw() 直前に除去する
                core._field._mobs = []  # pylint: disable=W0212
                core._field._bullets = []  # pylint: disable=W0212
                core._field._drops = []  # pylint: disable=W0212
                core.draw()

                self._assert_field_and_player_drawn(
                    self.INITIAL_PLAYER_X,
                    round(self.INITIAL_PLAYER_Y - update_count * Field.PLAYER_SPEED),
                )


class TestBulletDraw(TestParent):
    """発射された弾の描画の e2e スタイルテスト（IF: TestInput によるタップ
    入力の注入と、フレーム経過による自動発射・描画呼び出し）

    仕様（このテストで固定する）:
    - 発射間隔（Player.BULLET_SHOOT_INTERVAL 回の update()）の経過で自動
      発射された弾が、発射時点のプレイヤーの画像中心点に弾の画像中心点が
      一致する位置へ描画される
    - 弾は進行方向を内部に持つが、小さいスプライトを回転させると画像が
      歪むため、向きによらず回転なし（回転 0）で描画される
    - 弾の描画アセットは BULLET_IMG/BULLET_U/BULLET_V/BULLET_W/BULLET_H

    全描画要素の順序は TestFieldTileDraw で、発射のタイミング・弾の直進・
    領域外消滅は test_actor.py（TestPlayerShoot）/test_field.py で固定済みの
    ため、ここでは扱わない"""

    def test_fired_bullet_is_drawn_at_shooting_player_center(self):
        """発射間隔ぶんのフレーム経過で自動発射された弾が、発射時点の
        プレイヤー位置（画像中心点同士が一致）へ、発射時点の向きに
        よらず回転なしで描画されること（プレイヤー自身は向きに応じて
        回転して描画されるのと対照的に、弾の描画呼び出しの回転が常に 0 の
        ままであることを確認する）"""
        test_cases = [
            # (名前, 発射前のタップ差分。None はタップなし＝初期の真上のまま
            # 発射され、旗なしの自明な期待値になる)
            ("タップなしでは初期の真上の向きのまま回転なしで描画される", None),
            ("右へ方向転換後も回転なしで描画される", (30, 0)),
            # 3:4:5 の直角三角形方向（距離 50。生の角度は約143.13度）。
            # 非自明な向きでも描画回転が 0 のままであることの確認になる。
            # 観測期間中の移動距離（15）は目的地距離（50）未満のため
            # 到着・解除されない
            ("斜め方向へ発射された弾も回転なしで描画される", (30, 40)),
        ]
        for name, tap_diff in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = GameCore()
                # モブの移動・追尾は本テストの検証対象外のため除去する
                core._field._mobs = []  # pylint: disable=W0212
                # 発射までの経過（発射間隔）フレーム中に新たなモブが出現
                # しないことを、値の大小関係ではなくインスタンス変数への
                # 直接指定で保証する（開始時のモブは除去済みのため、これで
                # 自動追尾は働かずプレイヤーは発射時点の向きのまま直進し続ける）
                # pylint: disable=W0212
                core._field._mob_spawn_interval = (
                    core._field._player._bullet_shoot_interval + 1
                )
                # pylint: enable=W0212
                # 初期状態はカメラオフセット 0 のため、スクリーン座標＝ワールド座標
                initial_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                if tap_diff is not None:
                    self._tap_at_world(initial_pos, tap_diff)
                core.update()  # 最初のフレーム（タップ時は方向転換して前進）
                self._release_tap()
                # 発射間隔の経過まで（最初のフレームを含め interval 回）進める。
                # 発射は process_frame() 末尾（前進の後）のため、発射フレームの
                # 弾は前進せず、発射時点のプレイヤーの画像中心点に位置したまま
                # 描画される
                for _ in range(Player.BULLET_SHOOT_INTERVAL - 1):
                    core.update()

                core.draw()

                # 期待値の計算にのみ使う進行方向の差分（タップなしの場合は
                # 初期の進行方向＝真上の単位ベクトル）
                diff = tap_diff if tap_diff is not None else (0, -1)
                player_pos = self._expected_pos(
                    initial_pos, diff, Player.BULLET_SHOOT_INTERVAL
                )
                # 弾の画像中心点は発射時点のプレイヤーの画像中心点と一致する
                # ため、弾の登録座標は「プレイヤーの登録座標 + プレイヤーの
                # 中心点オフセット − 弾の画像サイズの半分」で計算する
                bullet_pos = (
                    player_pos[0]
                    + self.PLAYER_CENTER_OFFSET_X
                    - GameCore.BULLET_W // 2,
                    player_pos[1]
                    + self.PLAYER_CENTER_OFFSET_Y
                    - GameCore.BULLET_H // 2,
                )
                self._assert_field_and_player_drawn(
                    *player_pos,
                    player_rotate=self._expected_rotate(diff),
                    bullets=[bullet_pos],
                    flag=(
                        self._tapped_dest(initial_pos, tap_diff)
                        if tap_diff is not None
                        else None
                    ),
                    mode="destination" if tap_diff is not None else "attack",
                )


class TestDropDraw(TestParent):
    """モブ撃破時に生成されたドロップの描画の e2e スタイルテスト（IF:
    撃破配置の注入によるドロップ生成と描画呼び出し。TestMobDraw/
    TestBulletDraw と同じく TestView の呼び出し引数で検証する）

    仕様（このテストで固定する）:
    - drop_states() の各ドロップが、その座標（撃破されたモブと画像中心を
      揃えたドロップの登録座標。ドロップはモブとサイズが異なるため、
      モブの登録座標の流用では中心がずれる）へ回転なしで描画される
    - 通常ドロップの描画アセットは DROP_IMG/DROP_U/DROP_V/DROP_W/DROP_H、
      レアドロップは同じ画像バンク・サイズのまま RARE_DROP_U/RARE_DROP_V
      （命名は Field.RARE_DROP_RATE の RARE_DROP 接頭辞にならう）

    全描画要素の順序（ドロップは旗の直後＝弾・モブ・プレイヤーより奥）は
    TestFieldTileDraw で固定済みのため、ここでは扱わない（このテストの
    シーンは撃破により弾・モブが描画時点で存在せず、他要素との順序を
    観測できない）。ドロップの生成条件・撃破位置・レア化確率のロジック
    自体は test_field.py（TestDropSpawnOnMobDestroyed/
    TestRareDropSpawnByChance）で固定済みのため、同じく扱わない。撃破の
    契機は同テストの注入ヘルパーと同型の speed 0 注入で用意する
    （TestMobDraw/TestBulletDraw のような自然な契機〈発射された弾の弾道上の
    命中〉は命中までの数十フレーム中に検証と無関係なモブ出現・弾発射が
    混ざり、期待値の計算が撃破以外の要素に依存するため）"""

    def _draw_after_mob_destroy(self, rarity_random):
        """弾・モブ（いずれも登録座標・speed 0）を中心を揃えて重ねた組を
        互いに離れた位置に2組注入し、レア化判定の乱数を rarity_random に
        固定して update() を1回（撃破とドロップ生成）実行してから draw() を
        呼ぶ。注入したモブの登録座標（期待するドロップの描画座標の計算元）の
        リストを返す（2体撃破で「生成されたドロップすべてが描画される」
        ことの観測を兼ねる）"""
        core = GameCore()
        # 位置はすべて開始時の表示領域の明確な内側とし、領域外除去の判定と
        # 干渉させない（speed 0 のため1フレームでの移動もない）。2組は
        # 互いに明確に離し、弾とモブの組み合わせを1対1に保つ
        # （test_field.py の TestRareDropSpawnByChance と同じ配置）
        bullet_positions = [
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y - 40),
            (self.INITIAL_PLAYER_X + 40, self.INITIAL_PLAYER_Y - 40),
        ]
        mob_positions = [
            (
                x + Bullet.WIDTH // 2 - Mob.WIDTH // 2,
                y + Bullet.HEIGHT // 2 - Mob.HEIGHT // 2,
            )
            for x, y in bullet_positions
        ]
        # 開始時の1匹は検証対象外のため、注入したモブ・弾のみへ置き換える
        # pylint: disable=W0212
        core._field._mobs = [
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in mob_positions
        ]
        core._field._bullets = [
            Bullet(x + Bullet.WIDTH / 2, y + Bullet.HEIGHT / 2, 0)
            for x, y in bullet_positions
        ]
        # pylint: enable=W0212
        with patch("src.main.random.random", return_value=rarity_random):
            core.update()
        core.draw()
        return mob_positions

    def test_drops_are_drawn_with_asset_matching_rarity(self):
        """撃破位置に生成された全ドロップが、種別（通常/レア）に対応する
        アセットの U/V・回転なしで描画されること（種別の決まり方自体は
        test_field.py で固定済みのため、乱数値は境界から明確に離れた
        代表値のみを使う）"""
        test_cases = [
            (
                "確率を明確に下回る乱数値ではレアのアセットで描画される",
                Field.RARE_DROP_RATE / 2,
                True,
            ),
            (
                "確率を明確に上回る乱数値では通常のアセットで描画される",
                (Field.RARE_DROP_RATE + 1) / 2,
                False,
            ),
        ]
        for name, rarity_random, is_rare in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                mob_positions = self._draw_after_mob_destroy(rarity_random)

                # 撃破フレーム（update() 1回）の前進ぶんの期待プレイヤー
                # 位置・回転。進行方向は自動追尾により、撃破前のフレーム
                # 冒頭で最も近い注入モブ（1組目）の中心を向く
                nearest_diff = (
                    mob_positions[0][0]
                    + Mob.WIDTH / 2
                    - (self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X),
                    mob_positions[0][1]
                    + Mob.HEIGHT / 2
                    - (self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y),
                )
                player_pos = self._expected_pos(
                    (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), nearest_diff, 1
                )
                # ドロップの期待登録座標 = 撃破されたモブの中心（登録座標 +
                # モブサイズの半分）− ドロップサイズの半分（撃破されたモブと
                # 画像中心を一致させる仕様）
                expected_drop_positions = [
                    (
                        x + GameCore.MOB_W // 2 - GameCore.DROP_W // 2,
                        y + GameCore.MOB_H // 2 - GameCore.DROP_H // 2,
                    )
                    for x, y in mob_positions
                ]
                self._assert_field_and_player_drawn(
                    *player_pos,
                    player_rotate=self._expected_rotate(nearest_diff),
                    drops=[(*pos, is_rare) for pos in expected_drop_positions],
                )


class TestStatusDraw(TestParent):
    """ステータス（HP・通常ドロップ数・レアドロップ数）の UI 表示の e2e
    スタイルテスト（ID-012 サイクル3。IF: GameCore.draw() による
    IView.draw_rect()／draw_blt()／draw_text() の呼び出し）

    仕様（このテストで固定する。表示位置・矩形の大きさ・色・文字列書式は
    2026-07-12 のユーザー指示（Red での決定）およびプレイテスト指摘
    （背景色・横並び・すき間なしへの改訂）により具体値として決定した。
    HP はテキスト表示からハートアイコン表示へ ID-018 で置き換えた
    （requirements.md §4）。通常ドロップ数はラベル文字（"DROP:"）を
    ドロップ画像のアイコンへ ID-019 で置き換えた（レアドロップ数は
    サイクル2で置き換え予定）。決定理由は下の各定数のコメントに残す）:
    - HP・通常ドロップ数・レアドロップ数の3項目が横1行に並び、3項目分の
      幅を持つ単一の背景矩形（項目間・内部にすき間なし） → HP のハート
      アイコン → 通常ドロップのアイコン＋数値テキスト → レアドロップ項目の
      テキストの順で描画される（矩形が数値の背景として機能し、項目間の
      すき間からフィールドタイルの描画がちらついて見えないようにするため）
    - ステータスは全ワールド要素（フィールド・旗・ドロップ・弾・モブ・
      プレイヤー）より後＝最前面に HUD として描画される
    - clear() がカメラをオフセットするため、スクリーン上の固定位置に
      表示し続けるにはワールド座標＝カメラオフセット + スクリーン座標で
      描画される（前進でスクロールしても画面上の位置が変わらない）
    - 表示される数値は Field の現在のステータス値に追従する

    値の変化の仕方（回収での加算・初期値）は test_field.py
    （TestPlayerHpInitialValue／TestDropCountIncrementsOnCollect）で固定済みの
    ため扱わない。表示仕様の具体値（Red で決定した位置・矩形の大きさ・色・
    書式）と期待値の計算は、全描画結線テストが共通で参照するため TestParent
    （STATUS_* 定数・_expected_status_calls）に置く。「初期状態で3項目が
    単一矩形→テキストの順・最前面に描画される」ことは
    `_assert_field_and_player_drawn()` の全量一致検証（末尾にステータス
    期待値を含む）を使う全描画結線テストで既に検証されているため、ここでは
    その観点でカバーできない「値の追従」「カメラ追従」の2点のみを扱う"""

    def _assert_status_drawn_last(self, expected_calls):
        """描画呼び出し全体の末尾が期待するステータス呼び出し列と一致する
        （＝ステータスが全ワールド要素より後・矩形→テキストの順で描画
        される）ことを検証する。末尾以外のワールド要素の描画は既存の
        描画結線テストで固定済みのためここでは扱わない"""
        actual_tail = self.test_view.get_call_params()[-len(expected_calls) :]
        message = (
            f"ステータス描画呼び出し（末尾）が期待値と異なる:\n"
            f"期待: {expected_calls}\n実際: {actual_tail}"
        )
        self.assertEqual(expected_calls, actual_tail, message)

    def test_status_text_reflects_current_field_state(self):
        """表示される内容（HP はハートの個数、ドロップ数はテキストの数値）が
        Field の現在のステータス値に追従すること（初期値の描画に対する
        固定表示の誤実装との判別。値の変化の仕方は test_field.py で固定済みの
        ため、状態を直接注入して表示のみを観測する。2桁のカウントでも書式が
        崩れないことの確認を兼ねる）"""
        core = GameCore()
        # pylint: disable=W0212
        core._field._player._hp = 1
        core._field._player._normal_drop_count = 12
        core._field._player._rare_drop_count = 3
        # pylint: enable=W0212
        core.draw()
        self._assert_status_drawn_last(
            self._expected_status_calls(hp=1, normal=12, rare=3)
            + self._mode_button_draw_calls()
        )

    def test_status_draws_gray_hearts_for_lost_hp(self):
        """HP が減少した分は、左から player_hp 個の赤ハートに続けて
        残りが灰色ハートとして描画されること（requirements.md §4「減少
        したHPを灰色のハートアイコンで表示できる」）。HP=0（全損）・
        HP=Player.INITIAL_HP（無傷、灰色0個）を含む全境界値を subTest で
        検証する。HP=0 は既存仕様（TestGameEndPopupDraw）によりゲーム
        オーバー状態でもあり、ステータス HUD・移動モードボタンの直後に
        終了ポップアップが続けて描画されるため、その分の期待値を追加する"""
        for hp in range(Player.INITIAL_HP + 1):
            with self.subTest(hp=hp):
                core = GameCore()
                core._field._player._hp = hp  # pylint: disable=W0212
                core.draw()
                expected = (
                    self._expected_status_calls(hp=hp) + self._mode_button_draw_calls()
                )
                if hp == 0:
                    expected = expected + self._expected_end_popup_calls("GAME OVER")
                self._assert_drawn_last(expected)

    def test_status_stays_at_screen_position_while_scrolling(self):
        """前進によりカメラオフセットが変化しても、ステータスが同じ
        スクリーン位置（ワールド座標 = カメラオフセット + スクリーン座標）
        へ描画され続けること（カメラ 0 の初期状態だけではワールド座標へ
        固定する誤実装と判別できないため）"""
        core = GameCore()
        # PLAYER_SPEED（0.5）との積が整数になるフレーム数だけ前進し、
        # 小数の蓄積誤差なくカメラオフセットの期待値を計算する
        # （TestFieldTileScroll と同じ考え方。タップなしでは初期の進行方向
        # ＝真上へ直進するため、カメラは y 方向へのみ移動する）
        for _ in range(self.PRE_TAP_FRAMES):
            core.update()
        core.draw()
        camera = (0, -round(self.PRE_TAP_FRAMES * Field.PLAYER_SPEED))
        self._assert_status_drawn_last(
            self._expected_status_calls(camera=camera)
            + self._mode_button_draw_calls(camera=camera)
        )


class TestPlayerBlinkDrawDuringInvincibility(TestParent):
    """無敵時間中のプレイヤー点滅描画の e2e スタイルテスト（ID-015 サイクル4。
    IF: TestView の set_frame() によるフレーム数の注入と描画呼び出し。
    フレーム数の取得メソッドの名称・シグネチャ（IView.get_frame()）は
    ここで決定する）

    仕様（このテストで固定する）:
    - 無敵時間中は、IView.get_frame() のフレーム数を4で割った余りが 0・1 の
      フレームでプレイヤーの draw_blt が省略され、余りが 2・3 のフレームでは
      描画される（2フレームごとに描画の有無が切り替わる点滅。
      2026-07-17 ユーザー指示。参考実装: pyxel_connect_city の
      PyxelView.get_frame() とフレーム数剰余による描画分岐）
    - 無敵時間中でない通常時は、フレーム数によらず毎フレーム描画される
      （既存の描画結線テストはフレーム数 0（TestView の既定値）のまま
      成立し続ける）
    - 点滅の対象はプレイヤーの描画のみで、他の描画要素（フィールド・
      ステータス HUD）は非表示フレームでも描画され続ける

    無敵状態の開始・継続・終了のロジック自体は test_field.py
    （TestPlayerInvincibleAfterMobContact）・test_actor.py
    （TestPlayerInvincibility）で固定済みのため扱わず、TestStatusDraw の
    状態注入と同様に Player の公開メソッド start_invincibility() で
    無敵状態を直接注入して描画のみを観測する。モブとの接触という自然な
    契機を使わないのは、接触に必要なモブの注入・毎フレーム再配置が
    期待値の計算に無関係な要素を持ち込むため"""

    def _draw_at_frame(self, frame, invincible):
        """フレーム数 frame を注入し、invincible が真ならプレイヤーを
        無敵状態にしてから draw() を1回実行する"""
        core = GameCore()
        # モブの移動・描画は本テストの検証対象外のため除去する
        core._field._mobs = []  # pylint: disable=W0212
        if invincible:
            core._field._player.start_invincibility()  # pylint: disable=W0212
        self.test_view.set_frame(frame)
        core.draw()

    def test_player_draw_is_omitted_on_hidden_blink_frames_while_invincible(self):
        """無敵時間中、フレーム数を4で割った余りが 0・1 のフレームでは
        プレイヤーの draw_blt のみが省略される（フィールド・ステータス HUD
        は描画され続ける）こと。剰余の周期が繰り返されることも確認する"""
        # フレーム数を4で割った余りが 0・1 になる値（4・5 は周期の2巡目）
        test_cases = [0, 1, 4, 5]
        for frame in test_cases:
            with self.subTest(frame=frame):
                self.test_view.reset()
                self._draw_at_frame(frame, invincible=True)
                self._assert_field_and_player_drawn(
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y,
                    player_drawn=False,
                )

    def test_player_is_drawn_on_visible_blink_frames_while_invincible(self):
        """無敵時間中でも、フレーム数を4で割った余りが 2・3 のフレームでは
        プレイヤーが通常どおり描画されること。剰余の周期が繰り返されることも
        確認する"""
        # フレーム数を4で割った余りが 2・3 になる値（6・7 は周期の2巡目）
        test_cases = [2, 3, 6, 7]
        for frame in test_cases:
            with self.subTest(frame=frame):
                self.test_view.reset()
                self._draw_at_frame(frame, invincible=True)
                self._assert_field_and_player_drawn(
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y,
                )

    def test_player_is_drawn_every_frame_when_not_invincible(self):
        """無敵時間中でない通常時は、点滅の非表示フレームに相当する
        フレーム数（4で割った余りが 0・1）を含め、フレーム数によらず
        毎フレーム描画されること（既存の描画結線テストの前提を崩さない）"""
        # 4で割った余りの全種類（0〜3）を網羅する
        test_cases = [0, 1, 2, 3]
        for frame in test_cases:
            with self.subTest(frame=frame):
                self.test_view.reset()
                self._draw_at_frame(frame, invincible=False)
                self._assert_field_and_player_drawn(
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y,
                )


class TestGameEndPopupDraw(TestParent):
    """ゲーム終了（クリア／オーバー）時の終了ポップアップ描画の e2e
    スタイルテスト（ID-016 サイクル3・4。IF: GameCore.draw() による
    IView.draw_rect()／draw_text() の呼び出し）

    仕様（このテストで固定する。位置・大きさは参考実装 pyxel_sort_water
    ID-005 のポップアップ定数を同じ画面サイズ 150×200 のため流用し、
    背景色はステータス HUD と同じ色1〔濃い青。テキストの白と視認性を
    確保できることを確認済みの組み合わせ〕とする）:
    - 終了状態（クリア／オーバー）のとき、全描画要素（ステータス HUD 含む）
      より後＝最前面に、ポップアップの背景矩形 → テキスト（クリアは
      "CLEAR"、オーバーは "GAME OVER"）の順で描画される
    - ポップアップはスクリーン上の固定位置（左上 (25, 85)・幅 100・高さ 30）
      に表示される。clear() がカメラをオフセットするため、ワールド座標＝
      カメラオフセット + スクリーン座標で描画される（ステータス HUD と
      同じ考え方）
    - テキストは矩形の中央に配置する（Pyxel 標準フォントの 1 文字 4px 送り・
      グリフ 5px 高から幅・高さを計算して中央寄せ）
    - 非終了状態（終了目前の境界値〔クリアは RARE_DROP_CLEAR_TARGET - 1、
      オーバーは HP=1〕を含む）では描画されない

    クリアとゲームオーバーが同時に真になり得る場合の優先順位は、プレイ中に
    意図的に作りにくい境界条件のため要件・テストとして固定しない
    （ID-016_subtasks.md ID-016-12 の記載どおり）。

    クリア・ゲームオーバー判定の条件自体は test_field.py の
    TestGameClearAndGameOverState で固定済みのため、TestStatusDraw と同様に
    レアドロップ累計・HP の直接注入で終了状態を作り、描画のみを観測する。

    クリア・オーバーの2ケースは「終了状態を作る注入方法」「表示テキスト」
    「ステータス HUD 期待値のキーワード引数」のみが異なり、検証内容
    （最前面描画・カメラ追従・非表示）は完全に同型のため、サブテストで
    まとめて検証する（当初 ID-016-9〜11 でクリアのみを対象に
    TestGameClearPopupDraw として実装し、ID-016-12〜13 でゲームオーバーの
    ケースを同型のまま TestGameOverPopupDraw として追加した2クラスを、
    ID-016-14 の Refactor で人間レビュー指摘により本クラスへ統合した。
    test_field.py の TestFieldStopsWhenGameEnd と同じ統合方針）"""

    def _make_game_clear(self, core):
        core._field._player._rare_drop_count = (  # pylint: disable=W0212
            Field.RARE_DROP_CLEAR_TARGET
        )

    def _make_game_clear_boundary(self, core):
        core._field._player._rare_drop_count = (  # pylint: disable=W0212
            Field.RARE_DROP_CLEAR_TARGET - 1
        )

    def _make_game_over(self, core):
        core._field._player._hp = 0  # pylint: disable=W0212

    def _make_game_over_boundary(self, core):
        core._field._player._hp = 1  # pylint: disable=W0212

    def _game_end_popup_cases(self):
        """終了ケース（クリア／オーバー）ごとの
        (ラベル, ポップアップテキスト, 終了状態の注入関数,
        終了状態のステータス期待値キーワード引数, 境界値〔終了目前〕の
        注入関数, 境界値のステータス期待値キーワード引数) を返す。
        状態の直接注入は TestStatusDraw と同じ考え方で行う"""
        return [
            (
                "game_clear",
                "CLEAR",
                self._make_game_clear,
                {"rare": Field.RARE_DROP_CLEAR_TARGET},
                self._make_game_clear_boundary,
                {"rare": Field.RARE_DROP_CLEAR_TARGET - 1},
            ),
            (
                "game_over",
                "GAME OVER",
                self._make_game_over,
                {"hp": 0},
                self._make_game_over_boundary,
                {"hp": 1},
            ),
        ]

    def test_end_popup_is_drawn_over_status_when_game_end(self):
        """終了状態（クリア／オーバーそれぞれ）の draw() で、ステータス
        HUD・移動モードボタンの直後＝全描画要素の最前面に終了ポップアップ
        （背景矩形 → 中央寄せテキストの順）が描画されること"""
        for label, text, make_end, status_kwargs, _, _ in self._game_end_popup_cases():
            with self.subTest(state=label):
                core = GameCore()
                make_end(core)
                core.draw()
                self._assert_drawn_last(
                    self._expected_status_calls(**status_kwargs)
                    + self._mode_button_draw_calls()
                    + self._expected_end_popup_calls(text)
                )

    def test_end_popup_stays_at_screen_position_while_scrolled(self):
        """前進によりカメラオフセットが変化した後に終了状態（クリア／
        オーバーそれぞれ）へ到達した場合も、ポップアップが同じスクリーン
        位置（ワールド座標 = カメラオフセット + スクリーン座標）へ描画
        されること（カメラ 0 の初期状態だけではワールド座標へ固定する
        誤実装と判別できないため。TestStatusDraw のカメラ追従検証と
        同じ考え方）"""
        for label, text, make_end, status_kwargs, _, _ in self._game_end_popup_cases():
            with self.subTest(state=label):
                core = GameCore()
                # 終了到達前に PLAYER_SPEED との積が整数になるフレーム数
                # だけ前進し、少数の蓄積誤差なくカメラオフセットの期待値を
                # 計算する（タップなしでは初期の進行方向＝真上へ直進する
                # ため、カメラは y 方向へのみ移動する）
                for _ in range(self.PRE_TAP_FRAMES):
                    core.update()
                make_end(core)
                core.draw()
                camera = (0, -round(self.PRE_TAP_FRAMES * Field.PLAYER_SPEED))
                self._assert_drawn_last(
                    self._expected_status_calls(camera=camera, **status_kwargs)
                    + self._mode_button_draw_calls(camera=camera)
                    + self._expected_end_popup_calls(text, camera=camera)
                )

    def test_end_popup_is_not_drawn_when_not_game_end(self):
        """非終了状態（クリア／オーバーそれぞれの境界値）では draw() で
        ポップアップが描画されないこと。境界値は終了目前の値
        （クリアは RARE_DROP_CLEAR_TARGET - 1、オーバーは HP=1）を注入し、
        「わずかでも近づいていれば表示」のような誤った発動条件と判別
        できるようにする。ステータス HUD・移動モードボタンが描画の末尾
        （＝ポップアップが後続しない）であることと、ポップアップの矩形・
        テキストの呼び出しがフレーム全体のどこにも現れないことの両方を
        確認する"""
        for (
            label,
            text,
            _,
            _,
            make_boundary,
            boundary_status_kwargs,
        ) in self._game_end_popup_cases():
            with self.subTest(state=label):
                core = GameCore()
                make_boundary(core)
                core.draw()
                self._assert_drawn_last(
                    self._expected_status_calls(**boundary_status_kwargs)
                    + self._mode_button_draw_calls()
                )
                actual_calls = self.test_view.get_call_params()
                for popup_call in self._expected_end_popup_calls(text):
                    self.assertNotIn(
                        popup_call,
                        actual_calls,
                        f"非終了状態（{label}）でポップアップの描画呼び出しが行われた",
                    )


class TestGameResetOnPopupClick(TestParent):
    """終了状態（クリア／オーバー）でのポップアップクリックによる
    GameCore.needs_reset 遷移の e2e スタイルテスト（ID-017 サイクル1。
    IF: GameCore.update() 呼び出し後の needs_reset プロパティ）。

    実際に GameCore が新しいインスタンスへ総入れ替えされる挙動（App 側の
    再生成）は ID-017 サイクル2（TestAppReset）で別途検証する。

    仕様（このテストで固定する）:
    - GameCore の初期状態では needs_reset は False
    - 終了状態（クリア／オーバー）でポップアップ矩形内をクリックすると
      needs_reset が True になる
    - 終了状態でポップアップ矩形外をクリックしても needs_reset は False の
      まま（Refactor で _is_end_popup_clicked() を抽出した後の仕様として
      先に固定する。ID-017_subtasks.md 参照）
    - 終了状態でのクリック（矩形内外いずれも）は Field の目的地を変化させ
      ない（set_click() を呼んでいないことの間接検証）
    - 非終了状態でのクリックは needs_reset に影響しない

    クリア／オーバーの2ケースは「終了状態を作る注入方法」のみが異なり
    検証内容は同型のため、TestGameEndPopupDraw._game_end_popup_cases() と
    同様にサブテストでまとめて検証する"""

    def _make_game_clear(self, core):
        core._field._player._rare_drop_count = (  # pylint: disable=W0212
            Field.RARE_DROP_CLEAR_TARGET
        )

    def _make_game_over(self, core):
        core._field._player._hp = 0  # pylint: disable=W0212

    def _game_end_cases(self):
        return [
            ("game_clear", self._make_game_clear),
            ("game_over", self._make_game_over),
        ]

    def _tap_popup_inside(self):
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(self.END_POPUP_X + self.END_POPUP_W // 2)
        self.test_input.set_mouse_y(self.END_POPUP_Y + self.END_POPUP_H // 2)

    def _tap_popup_outside(self):
        # ポップアップ矩形（x:25-124, y:85-114）の明確に外側となる原点
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(0)
        self.test_input.set_mouse_y(0)

    def test_needs_reset_is_false_initially(self):
        core = GameCore()
        self.assertFalse(core.needs_reset)

    def test_needs_reset_becomes_true_when_popup_clicked_on_game_end(self):
        for label, make_end in self._game_end_cases():
            with self.subTest(state=label):
                core = GameCore()
                make_end(core)
                self._tap_popup_inside()
                core.update()
                self.assertTrue(core.needs_reset)

    def test_needs_reset_stays_false_when_click_outside_popup_on_game_end(self):
        for label, make_end in self._game_end_cases():
            with self.subTest(state=label):
                core = GameCore()
                make_end(core)
                self._tap_popup_outside()
                core.update()
                self.assertFalse(core.needs_reset)

    def test_field_state_is_unchanged_by_click_on_game_end(self):
        """終了状態でのクリック（ポップアップ内外いずれも）が Field の
        目的地を変化させないこと（set_click() を呼んでいないことの間接
        検証。既存の TestFieldStopsWhenGameEnd と重複しない範囲で最小限に
        確認する）"""
        for label, make_end in self._game_end_cases():
            for tap_label, tap in (
                ("inside", self._tap_popup_inside),
                ("outside", self._tap_popup_outside),
            ):
                with self.subTest(state=label, click=tap_label):
                    core = GameCore()
                    make_end(core)
                    dest_before = core._field.destination  # pylint: disable=W0212
                    tap()
                    core.update()
                    self.assertEqual(
                        dest_before,
                        core._field.destination,  # pylint: disable=W0212
                    )

    def test_needs_reset_is_not_affected_by_click_when_not_game_end(self):
        core = GameCore()
        self._tap_popup_inside()
        core.update()
        self.assertFalse(core.needs_reset)

    def _popup_boundary_cases(self):
        """ポップアップ矩形（x:[X, X+W)・y:[Y, Y+H) の半開区間）の境界値
        （辺上＝矩形内の最終位置／辺外＝そのすぐ外側）の
        (ラベル, (mouse_x, mouse_y), 期待する needs_reset) を返す"""
        left, top = self.END_POPUP_X, self.END_POPUP_Y
        right_in = self.END_POPUP_X + self.END_POPUP_W - 1
        bottom_in = self.END_POPUP_Y + self.END_POPUP_H - 1
        right_out = self.END_POPUP_X + self.END_POPUP_W
        bottom_out = self.END_POPUP_Y + self.END_POPUP_H
        return [
            ("top_left_on_edge", (left, top), True),
            ("bottom_right_on_edge", (right_in, bottom_in), True),
            ("right_just_outside", (right_out, top), False),
            ("bottom_just_outside", (left, bottom_out), False),
        ]

    def test_needs_reset_at_popup_rect_boundaries(self):
        for state_label, make_end in self._game_end_cases():
            for (
                boundary_label,
                (mouse_x, mouse_y),
                expected,
            ) in self._popup_boundary_cases():
                with self.subTest(state=state_label, boundary=boundary_label):
                    core = GameCore()
                    make_end(core)
                    self.test_input.set_btn_pressed(True)
                    self.test_input.set_mouse_x(mouse_x)
                    self.test_input.set_mouse_y(mouse_y)
                    core.update()
                    self.assertEqual(expected, core.needs_reset)


class TestModeButtonToggle(TestParent):
    """移動モード切り替えボタン押下によるモード切替の e2e スタイルテスト
    （ID-020 サイクル2、requirements.md §3.1）。

    状態の置き場所は ID-020 では GameCore 単独の内部状態としていたが、
    ID-021 サイクル6 で Field（Player）が保持するモード情報
    （Field.player_move_mode／toggle_player_move_mode()）へ一本化した
    （モードに応じた実際の挙動＝攻撃停止・追尾先の切替を Field 側が
    担うため）。本クラスは引き続き「ボタン押下でモードが切り替わる」
    ことのみを、描画結果（アイコンの切替）とフィールドタップとの区別
    （Field への目的地指定を発火させない＝destination 不変）という
    観測可能な振る舞いで検証する（GUI テスト設計ガイドの「振る舞い
    ベーステスト」の原則）。切り替わったモードが実際の挙動（攻撃停止・
    最も近いドロップの追尾）へ結線されていることは
    TestModeButtonSwitchesFieldBehavior の関心。

    仕様（このテストで固定する）:
    - 初期状態は自動戦闘モード（サイクル1で固定描画済みのアイコンと
      一致。ID-020-2〜4 の既存テストで検証済みのためここでは再掲しない）
    - ボタン（画面右下の円の外接矩形。判定方法は _mode_button_draw_calls
      直上のコメント参照）を1回押下すると自動収集モードへ切り替わり、
      次の draw() でアイコンが自動収集モードアイコンに変わる
    - 自動収集モード中にボタンを再度押下すると自動戦闘モードへ戻る
    - ボタンの外接矩形の外側の押下はボタン押下として扱われず、通常の
      フィールドタップ（Field.set_click() による目的地の指定）になる
      （その結果、押下後のモードはトグルされず目的地移動モードになる。
      ID-022 サイクル4 で目的地の有無から実効モードを導出するように
      なったため、「モードが切り替わらない」から改めた）
    - 目的地移動モード中にボタンを押下すると自動戦闘モードへ戻り、目的地も
      解除されるため次の draw() ではアイコンが自動戦闘モードアイコンに戻り、
      目的地の旗も描画されなくなる（ID-022 サイクル6、requirements.md
      §3.1）。起点が自動収集モードでも自動収集モードへは戻らないことは
      Field の IF で固定済みのため（test_field.py の
      TestFieldTogglesPlayerMoveMode）、e2e である本クラスでは自動戦闘
      モード起点の1ケースで結線のみを扱う
    - ボタン押下（矩形内）は Field への目的地指定（Field.set_click()）を
      発火させない（_assert_mode_after_draw の flag=None による全描画
      完全一致検証で間接検証する。誤って発火した場合、旗の描画・プレイヤー
      の移動先のいずれかが期待値と食い違い検出される。判定〔query〕と
      モード切替〔command〕の分離は Green での実装詳細のため、ここでは
      呼び出し結果のみを検証する）
    """

    def _press_outside_button(self):
        # ボタン外接矩形の明確に外側となる画面上端かつ、x 座標をプレイヤー
        # 中心と揃えることで、プレイヤーの初期進行方向（真上）と同じ方向を
        # タップする（_assert_mode_after_draw 側の注記参照）
        self.test_input.set_btn_pressed(True)
        self.test_input.set_mouse_x(self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X)
        self.test_input.set_mouse_y(0)

    def _make_core_without_mobs(self):
        # モブが存在すると自動追尾による向き変化・撃破によるドロップ生成・
        # 出現間隔経過による追加出現など、この検証対象（モードアイコンの
        # 切替）と無関係な不確定要素を期待値に持ち込むことになる。モブを
        # 除去すればタップなし・追尾対象なしで進行方向は初期値（真上）の
        # まま変わらず、毎フレーム PLAYER_SPEED ぶん直進する自明値になる
        # （モブ追尾は画面内にモブがなければ向きを変えない）
        core = GameCore()
        core._field._mobs = []  # pylint: disable=W0212
        return core

    def _assert_mode_after_draw(self, core, expected_mode, frames, flag=None):
        """draw() 呼び出し全体（フィールド・(タップ時のみ)旗・プレイヤー・
        ステータス HUD・移動モードボタン）を自明値の期待値と完全一致で検証
        する。モブを除去しているため弾・ドロップ・追尾による向き変化は
        一切発生せず、振る舞いベースで純粋にモードアイコンの切替のみを
        観測できる。呼び出し元はいずれも、タップ後もプレイヤーの進行方向が
        初期値（真上）から変わらない状況のみを扱う（ボタン矩形内の押下は
        Field へ転送されず、ボタン矩形外の押下も _press_outside_button が
        真上と同じ方向をタップするため）。したがってプレイヤー位置・向きは
        tap の有無によらず毎フレーム PLAYER_SPEED ぶん直進する共通の期待値
        になり（TestFieldTileScroll の PRE_TAP_FRAMES と同じ考え方）、
        Field への転送があったかどうかは目的地の旗が描画されたか（flag
        引数、ワールド座標）でのみ区別する"""
        self.test_view.reset()
        core.draw()
        player_pos = (
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - frames * Field.PLAYER_SPEED),
        )
        player_rotate = 0
        camera = self._camera_offset_at(player_pos)
        expected_calls = self._expected_calls_for_player_at(
            player_pos[0], player_pos[1], player_rotate
        )
        player_call = expected_calls.pop()
        if flag is not None:
            expected_calls.append(self._flag_draw_call(*flag))
        expected_calls.append(player_call)
        expected_calls += self._expected_status_calls(camera=camera)
        expected_calls += self._mode_button_draw_calls(
            camera=camera, mode=expected_mode
        )
        actual_calls = self.test_view.get_call_params()
        message = f"描画呼び出しが期待値と異なる:\n期待: {expected_calls}\n実際: {actual_calls}"
        self.assertEqual(expected_calls, actual_calls, message)

    def test_mode_switches_to_collect_after_button_press(self):
        core = self._make_core_without_mobs()
        self._press_button_center()
        core.update()
        self._release_tap()
        self._assert_mode_after_draw(core, "collect", frames=1)

    def test_mode_returns_to_attack_after_second_button_press(self):
        core = self._make_core_without_mobs()
        self._press_button_center()
        core.update()
        self._release_tap()
        self._press_button_center()
        core.update()
        self._release_tap()
        self._assert_mode_after_draw(core, "attack", frames=2)

    def test_mode_unchanged_when_pressed_outside_button(self):
        # ボタン外接矩形の明確に外側となる画面上端への押下は、ボタン押下
        # ではなく通常のフィールドタップとして Field.set_click() へ転送
        # される（既存仕様。ID-007 サイクル2）。_press_outside_button は
        # プレイヤーの初期進行方向（真上）と同じ方向をタップするため、旗の
        # 描画位置（タップ時点でカメラオフセットが (0, 0) のためタップ
        # 座標そのまま）以外の期待値は _assert_mode_after_draw 側の共通
        # 直進計算式のみで足りる。押下がフィールドタップとして扱われた
        # 結果、目的地が設定され実効モードは目的地移動モードになるため、
        # ボタン表示も目的地の旗・青背景になる（ID-022 サイクル4で目的地の
        # 有無から実効モードを導出するようになったことに伴う、ID-022
        # サイクル5での期待値の改訂。メソッド名の「モードが変わらない」は
        # 「ボタン押下によるトグル（自動戦闘⇔自動収集）が起きない」ことを
        # 指し、目的地移動モードへの遷移自体は起きる）
        core = self._make_core_without_mobs()
        outside_x = self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X
        outside_y = 0
        self._press_outside_button()
        core.update()
        self._release_tap()
        self._assert_mode_after_draw(
            core, "destination", frames=1, flag=(outside_x, outside_y)
        )

    def test_mode_returns_to_attack_and_flag_is_removed_by_press_during_destination(
        self,
    ):
        # ボタン矩形外への押下でまず目的地移動モードへ入り（直前の
        # test_mode_unchanged_when_pressed_outside_button で固定済みの経路）、
        # 続けてボタンを押下する。押下位置はプレイヤーの初期進行方向（真上）と
        # 同じ方向のため、目的地移動中も目的地の解除後も進行方向は変わらず、
        # プレイヤーの期待位置は共通の直進計算式のままでよい。flag を省く
        # （=None）ことで、目的地の解除により旗の描画呼び出しが1つも含まれなく
        # なることを全描画の完全一致で検証する
        core = self._make_core_without_mobs()
        self._press_outside_button()
        core.update()
        self._release_tap()
        self._press_button_center()
        core.update()
        self._release_tap()
        self._assert_mode_after_draw(core, "attack", frames=2)

    def _button_boundary_cases(self):
        """ボタン当たり判定矩形（半開区間 [X, X+W)×[Y, Y+H)）の境界値
        （辺上＝矩形内の最終位置／辺外＝そのすぐ外側）の
        (ラベル, (mouse_x, mouse_y), 押下後に期待するモード) を返す
        （_popup_boundary_cases と同じ考え方）。

        矩形内はボタン押下としてトグルされ自動収集モードになる。矩形外は
        ボタン押下ではなく通常のフィールドタップ（Field.set_click()）へ
        転送されるため、目的地が設定され目的地移動モードになる（ID-022
        サイクル4。目的地の有無から実効モードを導出するようになったことで、
        矩形外の押下でも player_move_mode の値は自動戦闘モードのままでは
        なくなった。トグル自体が起きていないこと〔＝矩形外の押下がボタン
        押下として扱われていないこと〕は、自動収集モードにならないことで
        引き続き判別できる）"""
        left = self.MODE_BUTTON_RECT_X
        top = self.MODE_BUTTON_RECT_Y
        right_in = self.MODE_BUTTON_RECT_X + self.MODE_BUTTON_RECT_W - 1
        bottom_in = self.MODE_BUTTON_RECT_Y + self.MODE_BUTTON_RECT_H - 1
        right_out = self.MODE_BUTTON_RECT_X + self.MODE_BUTTON_RECT_W
        bottom_out = self.MODE_BUTTON_RECT_Y + self.MODE_BUTTON_RECT_H
        return [
            ("top_left_on_edge", (left, top), MoveMode.COLLECT),
            (
                "bottom_right_on_edge",
                (right_in, bottom_in),
                MoveMode.COLLECT,
            ),
            ("right_just_outside", (right_out, top), MoveMode.DESTINATION),
            ("bottom_just_outside", (left, bottom_out), MoveMode.DESTINATION),
        ]

    def test_mode_toggle_at_button_rect_boundaries(self):
        """境界値でのモード切替結果（Field が保持するモード情報
        Field.player_move_mode）のみを検証する。描画結果への反映は
        test_mode_switches_to_collect_after_button_press 等の既存テストで
        別途検証済みのため、ここでは test_needs_reset_at_popup_rect_boundaries
        と同様に描画を介さず直接確認する（参照先は ID-021 サイクル6 で
        GameCore 単独の内部状態から Field のモード情報へ移した）"""
        for (
            label,
            (mouse_x, mouse_y),
            expected_mode,
        ) in self._button_boundary_cases():
            with self.subTest(boundary=label):
                core = GameCore()
                self.test_input.set_btn_pressed(True)
                self.test_input.set_mouse_x(mouse_x)
                self.test_input.set_mouse_y(mouse_y)
                core.update()
                self._release_tap()
                self.assertEqual(
                    expected_mode, core._field.player_move_mode  # pylint: disable=W0212
                )


class TestModeButtonSwitchesFieldBehavior(TestParent):
    """移動モード切り替えボタンの押下が、Field（Player）の実際の挙動へ
    結線されていることの e2e スタイルテスト（ID-021 サイクル6 Red、
    requirements.md §3.1）。

    仕様（このテストで固定する）:
    - ボタンを1回押下すると、その押下フレームから自動収集モードの挙動に
      なる: 画面内にモブがいてもモブの方向へは向かわず、最も近いドロップの
      方向を向いて進み、発射間隔が経過しても弾を発射しない
    - ボタンを押さなければ従来どおり自動戦闘モードの挙動（画面内にドロップが
      あってもモブを追尾し、発射間隔の経過で弾を発射する）が続く

    自動戦闘のケースは、同じ配置のモブ・ドロップが本来なら追尾対象・
    発射契機になり得ることを示す対照でもある（自動収集のケースだけでは、
    たまたま追尾対象が画面外だった・発射契機に届かなかった場合にも通って
    しまう）。

    モードの保持・トグル自体は test_field.py の
    TestFieldTogglesPlayerMoveMode、モードごとの追尾先・発射の有無は同
    TestCollectModeTracksNearestDrop・test_actor.py の
    TestPlayerShootInMoveMode で個別に固定済みのため、本クラスはそれらが
    ボタン押下（GameCore の入力判定）から実際に駆動されることのみを扱う
    （アイコン・色の切替そのものは TestModeButtonToggle の関心だが、
    描画呼び出し全体の完全一致で検証する都合上、期待値には含まれる）。

    各ケースは (ボタン押下の有無, 期待するモード, 向き続ける方向, 弾の
    有無) の自己完結した組であり、ケースごとに期待値の系統が変わるわけでは
    ないため、1つの subTest ループへまとめる"""

    # 画面内モブのプレイヤーからの x 差分（左、同じ y）。自動戦闘モードでの
    # 追尾対象であり、自動収集モードでは「画面内にいても追尾されない」対照に
    # なる（test_field.py の TestCollectModeTracksNearestDrop と同じ配置）
    MOB_DX = -30
    # ドロップのプレイヤー画像中心点からの差分。最近傍（右、距離 30）と
    # それより遠いもの（下、距離 50）を別方向に置き、自動収集モードで
    # 「最も近いドロップ」の方向を向くことを向きの違いで観測する
    NEAR_DROP_DIFF = (30, 0)
    FAR_DROP_DIFF = (0, 50)
    # 観測フレーム数は発射間隔ちょうど（自動戦闘モードでは最後のフレームで
    # 発射された弾が、前進せずプレイヤーの画像中心点に位置したまま描画
    # される。TestBulletDraw と同型）。この間の前進は
    # BULLET_SHOOT_INTERVAL × PLAYER_SPEED = 15px で、モブ（30px）・
    # 最近傍ドロップ（30px）のいずれとも重ならないため、接触ダメージ・
    # ドロップ回収は期待値へ混ざらない
    FRAMES = Player.BULLET_SHOOT_INTERVAL

    def _make_mob_facing_initial_player(self, x, y):
        """速度 0 のモブを登録座標（スプライト左上）(x, y) へ生成し、初期
        プレイヤーの画像中心点の方向へ向けて返す（test_field.py の同名
        ヘルパーと同じ考え方）。モブとプレイヤーは同サイズのため中心点同士の
        方向は登録座標同士の方向と一致し、期待描画回転は軸沿いの自明値に
        なる。速度 0 のため観測期間中に位置は変わらず、プレイヤーがモブと
        同じ y 上を左右に動く配置のため向き（真右）も変わらない"""
        mob = Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0)
        mob.turn_to(
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y,
        )
        return mob

    def _drop_at(self, diff):
        """プレイヤー（開始時の位置）の画像中心点から差分 diff の位置へ
        画像中心が来るドロップ（登録座標・通常種別）のタプルを返す
        （test_field.py の TestCollectModeTracksNearestDrop と同じ計算式。
        DROP_W/DROP_H はともに偶数のため丸め誤差は生じない）"""
        return (
            self.INITIAL_PLAYER_X
            + self.PLAYER_CENTER_OFFSET_X
            + diff[0]
            - GameCore.DROP_W // 2,
            self.INITIAL_PLAYER_Y
            + self.PLAYER_CENTER_OFFSET_Y
            + diff[1]
            - GameCore.DROP_H // 2,
            False,
        )

    def _make_core_with_mob_and_drops(self, drops):
        """開始時のモブを、追尾対象として明確な位置にある速度 0 のモブ1体へ
        置き換え、ドロップ drops を注入した GameCore を返す。観測期間中に
        新たなモブが出現しないことは、値の大小関係ではなくインスタンス変数
        への直接指定で保証する（TestBulletDraw と同型）"""
        core = GameCore()
        # pylint: disable=W0212
        core._field._mobs = [
            self._make_mob_facing_initial_player(
                self.INITIAL_PLAYER_X + self.MOB_DX, self.INITIAL_PLAYER_Y
            )
        ]
        core._field._drops = [
            Drop(x + Drop.WIDTH / 2, y + Drop.HEIGHT / 2, 0, is_rare)
            for x, y, is_rare in drops
        ]
        core._field._mob_spawn_interval = self.FRAMES + 1
        # pylint: enable=W0212
        return core

    def test_behavior_per_mode_button_press_with_onscreen_mob_and_drops(self):
        # 前提ガード: 自動収集モードで最近傍ドロップへ FRAMES フレーム進んだ
        # 後の距離（30 − 15 = 15px）が引き寄せ範囲の外にあること。本テストは
        # 「ドロップは位置を変えず drops 引数どおり描画される」ことを検証する
        # ため、範囲内だと引き寄せによってこの前提が崩れる（ID-024 で追加。
        # 最小距離のケース）。引き寄せ範囲はプレイヤーの成長レベルに応じて
        # 広がるが、本テストのプレイヤーは累計取得数0（レベル0）のままのため、
        # レベル0の範囲（Field.DROP_ATTRACT_RANGE）と比較すればよい
        self.assertGreater(
            math.hypot(*self.NEAR_DROP_DIFF) - self.FRAMES * Field.PLAYER_SPEED,
            Field.DROP_ATTRACT_RANGE,
        )
        test_cases = [
            # (名前, ボタン押下の有無, 期待するモードアイコン, 向き続ける
            #  方向の差分ベクトル, 発射された弾の有無)
            (
                "押下しなければ自動戦闘のままモブを追尾し発射する",
                False,
                "attack",
                (self.MOB_DX, 0),
                True,
            ),
            (
                "押下すると自動収集へ切り替わり最も近いドロップを追尾し発射しない",
                True,
                "collect",
                self.NEAR_DROP_DIFF,
                False,
            ),
        ]
        drops = [self._drop_at(self.FAR_DROP_DIFF), self._drop_at(self.NEAR_DROP_DIFF)]
        for name, presses_button, mode, direction, is_fired in test_cases:
            with self.subTest(name):
                self.test_view.reset()
                core = self._make_core_with_mob_and_drops(drops)
                if presses_button:
                    self._press_button_center()
                # 押下フレームでもモード切替後に Field のフレーム処理が
                # 走るため、切り替わった挙動は最初のフレームから適用される
                core.update()
                self._release_tap()
                for _ in range(self.FRAMES - 1):
                    core.update()

                core.draw()

                player_pos = self._expected_pos(
                    (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                    direction,
                    self.FRAMES,
                )
                # 弾の画像中心点は発射時点（最終フレーム）のプレイヤーの
                # 画像中心点と一致する（TestBulletDraw と同じ計算式）
                bullet_pos = (
                    player_pos[0]
                    + self.PLAYER_CENTER_OFFSET_X
                    - GameCore.BULLET_W // 2,
                    player_pos[1]
                    + self.PLAYER_CENTER_OFFSET_Y
                    - GameCore.BULLET_H // 2,
                )
                self._assert_field_and_player_drawn(
                    *player_pos,
                    player_rotate=self._expected_rotate(direction),
                    mobs=[
                        (
                            self.INITIAL_PLAYER_X + self.MOB_DX,
                            self.INITIAL_PLAYER_Y,
                            self._expected_rotate((1, 0)),
                        )
                    ],
                    bullets=[bullet_pos] if is_fired else [],
                    drops=drops,
                    mode=mode,
                )


class TestAppReset(unittest.TestCase):
    """App によるゲームリセット動作のテスト"""

    def setUp(self):
        self.mock_pyxel = MagicMock()
        # btnp() が MagicMock（truthy）のままだと GameCore.update() 内の
        # タップ処理が誤発火し、MagicMock 座標で set_click() が呼ばれて
        # ゲーム状態が破壊されるため、未クリック相当の False に固定する
        self.mock_pyxel.btnp.return_value = False
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()

    def tearDown(self):
        self.patcher_pyxel.stop()

    def test_app_replaces_core_when_needs_reset(self):
        app = App()
        original = app._core  # pylint: disable=W0212
        original._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertIsNot(app._core, original)  # pylint: disable=W0212

    def test_replaced_core_has_false_needs_reset(self):
        app = App()
        app._core._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertFalse(app._core.needs_reset)  # pylint: disable=W0212

    def test_app_does_not_replace_core_when_not_needs_reset(self):
        app = App()
        original = app._core  # pylint: disable=W0212
        app.update()
        self.assertIs(app._core, original)  # pylint: disable=W0212
