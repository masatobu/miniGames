"""共通フィクスチャと期待値ヘルパー

TestView / TestInput（IView / IInput のテスト用実装）と、全テストファイルが
継承する TestParent（setUp/tearDown の共通化と `_expected_*` 系の期待値
ヘルパー）を集約する。TestParent はテストメソッドを持たない（ヘルパーは
すべて `_expected_*` / `_default_*` / `_press` などの非公開メソッド）ため、
unittest discover / run_tests.py のいずれの収集経路でも0件として拾われる
（test_ 接頭辞を外さず test_main_tools.py の命名で進められる理由）。

test/test_main.py（3,998行・テストクラス30個）を「何の要件を検証しているか」
という機能の軸で6ファイルへ分割した際の共通基盤ファイル。分割は移動のみに
限定し（TestParent 内部のヘルパーの仕分けは対象外）、振る舞いは1つも
変えていない。
"""

import math
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import (  # pylint: disable=C0413
    IView,
    IInput,
    GameCore,
    Clock,
    SettlementPopupState,
)
from field import Field, Owner, Shop  # pylint: disable=C0413,E0401
from random_source import IRandomSource  # pylint: disable=C0413,E0401


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_image(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_image", x, y, img, u, v, w, h, colkey))

    def draw_rect(self, x, y, w, h, col):
        self.call_params.append(("draw_rect", x, y, w, h, col))

    def draw_rectb(self, x, y, w, h, col):
        self.call_params.append(("draw_rectb", x, y, w, h, col))

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    def __init__(self):
        self._down = False
        self._pos = (0, 0)

    def is_mouse_btn_down(self) -> bool:
        return self._down

    def get_mouse_pos(self):
        return self._pos

    def set_down(self, down):
        self._down = down

    def set_pos(self, x, y):
        self._pos = (x, y)


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.patcher_store = patch("src.main.ReportStore")
        self.mock_store_cls = self.patcher_store.start()
        self.mock_store = self.mock_store_cls.return_value
        self.mock_store.load.return_value = None
        self.test_input = TestInput()
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.patcher_input.start()
        # Field が生成する乱数源を、抽選対象の先頭を常に選ぶ決定的な実装へ
        # 差し替える（差し替えないと本番実装が pyxel を取り込む）。どの対象が
        # 選ばれるかに関心があるのは Field 層のテスト（test_field.py）で、
        # test_main.py 側の関心は「満了で成長が起きたか」にあるため、テスト用の
        # クラスは起こさず ReportStore と同じ MagicMock で用意する（spec で
        # インタフェース外のメソッドを呼べないようにしておく）
        self.test_random_source = MagicMock(spec=IRandomSource)
        self.test_random_source.pick_npc_growth_target.side_effect = (
            lambda targets: targets[0]
        )
        self.patcher_random_source = patch(
            "field.PyxelRandomSource.create", return_value=self.test_random_source
        )
        self.patcher_random_source.start()
        self.patcher_clock = patch.object(Clock, "is_up", return_value=False)
        self.patcher_clock.start()
        # 既定のテスト用マップは常に空（保存データがなければ空マップから始まるため）。
        # 店舗を必要とするテストは core._field へ Field の API で直接店舗を設置する

    def tearDown(self):
        self.patcher_clock.stop()
        self.patcher_random_source.stop()
        self.patcher_input.stop()
        self.patcher_store.stop()
        self.patcher_view.stop()

    def _expected_road_calls(self):
        """道路の draw_image 呼び出し期待値を定数から計算する
        縦方向: y = FIELD_ORIGIN_Y + row * PITCH （row = 0..GRID_ROWS、道路本数 = GRID_ROWS + 1）
        横方向: x = 0 から SCREEN_W まで ROAD_SIZE 刻み（画面幅で切り上げ: -(-SCREEN_W // ROAD_SIZE)）
        """
        road_cols = -(-GameCore.SCREEN_W // GameCore.ROAD_SIZE)
        return [
            (
                "draw_image",
                col * GameCore.ROAD_SIZE,
                GameCore.FIELD_ORIGIN_Y + row * GameCore.PITCH,
                GameCore.ROAD_IMG,
                GameCore.ROAD_U,
                GameCore.ROAD_V,
                GameCore.ROAD_SIZE,
                GameCore.ROAD_SIZE,
                GameCore.ROAD_COLKEY,
            )
            for row in range(GameCore.GRID_ROWS + 1)
            for col in range(road_cols)
        ]

    def _expected_icon_calls(self, x, y, u, v):
        """アイコン1つだけの draw_image 呼び出し期待値を、位置 (x, y)・
        転送元 (u, v) から計算する（ID-026 決定1。GameCore._draw_icon()
        相当）。数値を伴う _expected_icon_value_calls() /
        _expected_icon_value_right_calls() とは別に持つ——数値を伴わず
        アイコン単体を置く箇所（4つのポップアップのボタン。サイクル
        026-3）が使う"""
        return [
            (
                "draw_image",
                x,
                y,
                GameCore.ICON_IMG,
                u,
                v,
                GameCore.ICON_W,
                GameCore.ICON_H,
                GameCore.ICON_COLKEY,
            )
        ]

    def _expected_icon_button_calls(self, btn_x, btn_y, btn_w, btn_h, u, v):
        """ボタン矩形 (btn_x, btn_y, btn_w, btn_h) の中央へ描くアイコン1つの
        draw_image 呼び出し期待値を計算する（ID-026 サイクル026-3）。
        区画選択ポップアップの○×、決算・ゲームクリア・ゲームオーバーの
        ○、4つのポップアップのボタンが共有する。アイコンは矩形の中央
        （(矩形の大きさ − ICON_W/H) // 2 だけ内側）へ描く——従来の文字の
        中央寄せ（フォント1文字ぶんのオフセット btn_w // 2 - 2 での近似）
        とは異なり、アイコンの大きさ（ICON_W/H）が分かっているため正確に
        中央揃えできる"""
        icon_x = btn_x + (btn_w - GameCore.ICON_W) // 2
        icon_y = btn_y + (btn_h - GameCore.ICON_H) // 2
        return self._expected_icon_calls(icon_x, icon_y, u, v)

    def _expected_icon_value_calls(self, x, y, u, v, text):
        """アイコン1つと数値（または文字列）1つの組の draw_image（アイコン）・
        draw_text（数値）呼び出し期待値を、位置 (x, y)・転送元 (u, v)・
        描く文字列 text から計算する（ID-026 決定1）。ステータス3項目・
        ポップアップ数値3行・4つのポップアップのボタンが共有する描画
        （実装側の共通処理。GameCore._draw_icon_value() 相当）の期待値を、
        実装から独立した式としてテスト側にも1箇所へ持つ。アイコンは
        (x, y) へ、数値はアイコンの右（ICON_W + ICON_GAP ぶん空けた位置）
        の同じ y へ描く"""
        return [
            (
                "draw_image",
                x,
                y,
                GameCore.ICON_IMG,
                u,
                v,
                GameCore.ICON_W,
                GameCore.ICON_H,
                GameCore.ICON_COLKEY,
            ),
            (
                "draw_text",
                x + GameCore.ICON_W + GameCore.ICON_GAP,
                y,
                text,
            ),
        ]

    def _expected_icon_value_right_calls(self, x, y, u, v, value, max_digits):
        """アイコン1つと、右詰めにした数値 value の組の draw_image
        （アイコン）・draw_text（数値）呼び出し期待値を計算する（ID-026
        サイクル026-4 決定9。_expected_icon_value_calls() とは別の処理として
        持つ——右詰めの要否は呼び出し元で決まっており、_draw_icon_value()
        へ「桁数」引数を足すと決定1の差し戻し条件（呼び出し元を伝える引数が
        増える）に触れるため）。アイコンは (x, y) に固定で描き、数値は
        アイコンの右（ICON_W + ICON_GAP ぶん空けた位置）から始まる幅
        FONT_CHAR_W × max_digits の領域の中で右詰めにする——描画 x は
        数値領域の左端 + (max_digits − 桁数) × FONT_CHAR_W。max_digits を
        超える桁数の値は右詰め計算のとおり左へはみ出す（キャップしない）"""
        text = f"{value}"
        number_area_x = x + GameCore.ICON_W + GameCore.ICON_GAP
        number_x = number_area_x + (max_digits - len(text)) * GameCore.FONT_CHAR_W
        return [
            (
                "draw_image",
                x,
                y,
                GameCore.ICON_IMG,
                u,
                v,
                GameCore.ICON_W,
                GameCore.ICON_H,
                GameCore.ICON_COLKEY,
            ),
            (
                "draw_text",
                number_x,
                y,
                text,
            ),
        ]

    def _expected_status_calls(
        self,
        money=None,
        shop_count=None,
        remaining_sec=None,
        tax=None,
        paused=False,
    ):
        """ステータス領域の draw_rect（背景）・draw_image／draw_text（資金・
        店舗数・決算情報）呼び出し期待値を定数から計算する（ID-014 サイクル3で
        2行構成へ拡張、ID-028 サイクル028-4で1行目へ店舗数を追加、ID-026
        サイクル026-1で資金・店舗数・税額をアイコン＋数値の組へ置き換え、
        サイクル026-4でプレイテスト指示により2列2行のレイアウト・右詰めへ
        変更した）。
        money を省略すると初期資金（GameCore.INITIAL_MONEY）を使う。
        shop_count（プレイヤー所有店舗数）を省略すると 0 を使う（店舗を
        1つも置かないテストの大半はこの既定値のままで済む）。
        remaining_sec（決算までの残り時間・秒）を省略すると、決算タイマーが
        未開始のときの表示（間隔そのもの。SETTLEMENT_INTERVAL_MS // 1000）を
        使う。プレイヤー所有店舗を1つも置かない大半のテストは決算タイマーが
        起動しないため、この既定値のままで済む（設計判断: 未開始の残り時間は
        間隔そのものを表示する）。
        tax（支払い予定税額）を省略すると 0 を使う（店舗が無ければ税額も0）。
        paused（ポーズ中かどうか）を省略すると False（ポーズ解除）を使う。
        そのまま _expected_status_button_calls() へ渡し、2つのボタンの
        配色（設計方針 6-1）を切り替える（ID-019 サイクル6）。
        建設・増資・買収でプレイヤー所有店舗を作る・変えるテストは、その盤面に
        応じた tax を明示的に渡す（land_price は Field.GRID_PLOT_COUNT ==
        18 * 15 == 270 未満の資産価値総額では0になるため、規模の小さい盤面では
        資産税だけが表示されることが多い）。建設・買収でプレイヤー所有店舗数が
        変わるテストは、同じ盤面に応じた shop_count もあわせて明示的に渡す
        （tax・shop_count はどちらも盤面から求まる値だが、更新経路が異なる
        ため独立して渡す——増資は tax は変えても shop_count は変えない）。
        背景: 位置 (STATUS_X, STATUS_Y)、サイズ STATUS_W × STATUS_H、色 STATUS_BG_COL
        2列2行のレイアウト（ID-026 サイクル026-4。プレイテスト指示1）:
        左列（x = STATUS_X + STATUS_PAD）に資金（1行目）・税額（2行目）、
        右列1行目（x = STATUS_SHOP_COUNT_X）に店舗数を置く。y は既存のまま
        （1行目 = STATUS_Y + STATUS_PAD、2行目 = 1行目 + STATUS_LINE_H）。
        左列（資金・税額）: 資金アイコン（ICON_MONEY）・税額アイコン
              （ICON_TAX）とも同じ左列 x に置き、数値は最大
              STATUS_VALUE_MAX_DIGITS 桁ぶんの幅で右詰めにする（プレイテスト
              指示3。_expected_icon_value_right_calls()）——資金・税額の
              一の位が縦に揃う
        右列1行目（店舗数）: アイコン（ICON_SHOP_COUNT）＋
              f"{shop_count}/{Field.CLEAR_SHOP_COUNT}"（「SHOP」ラベルは
              アイコン化し、「/」と規定店舗数は文字のまま残す。ID-026
              決定4）。左詰めのまま（決定8。`n/m` 形式は桁を比べる対象では
              ないため右詰めの必要が無い）
        2行目（残り時間）: プログレスバー（残り時間ぶんの中身 draw_rect +
              枠 draw_rectb。ID-027 決定5。旧 f"T {秒}" の draw_text は
              置き換えにより消える——ID-026 決定6が申し送っていた置き換え
              そのもの）。**枠を中身より後（前面）に描く**のは、満杯
              （割合1.0）のとき中身が枠と完全に重なり、枠を先に描くと
              隠れて見えなくなる（時間経過につれて枠が現れるように見える）
              ため（プレイテスト指摘・2026-08-30）。**バーの原点 x は
              GameCore.STATUS_BAR_X であり、右列1行目（店舗数）の
              STATUS_SHOP_COUNT_X とはもう共有しない**——同日のプレイテスト
              指示により、位置を左列の税額の数値に近づけ（数値領域の右端
              から5px）、幅をポーズボタンの左端まで伸ばす形へ改めたため
              （ID-027_subtasks.md「プレイテスト指摘」参照）
        バーの中身の幅: 決算間隔に対する残り時間の割合
              （remaining_sec ÷ 決算間隔の秒数。秒粒度で量子化済み——
              決定3-A・GameCore._settlement_remaining_ratio()）に
              STATUS_BAR_W を掛けて求める。remaining_sec は呼び出し側が
              渡す秒単位の値であり、割合自体は本ヘルパーの外で計算しない
              （実装側 _draw_status() が呼ぶ _settlement_remaining_ratio()
              と同じ入力〈remaining_ms〉から同じ量子化〈math.ceil〉で
              導かれる値を、テスト側は remaining_sec からの比として
              独立に再現する）。
        2行の後に、右側のポーズ・スピードボタン2つの描画（_expected_status_
        button_calls()）を続ける（ID-019 サイクル3。ボタン2つぶんの増分を
        ここで足すことで、既存の draw 系テストがすべて変更なしにボタンの
        回帰確認を兼ねる）"""
        if money is None:
            money = GameCore.INITIAL_MONEY
        if shop_count is None:
            shop_count = 0
        interval_sec = GameCore.SETTLEMENT_INTERVAL_MS // 1000
        if remaining_sec is None:
            remaining_sec = interval_sec
        if tax is None:
            tax = 0
        left_x = GameCore.STATUS_X + GameCore.STATUS_PAD
        line1_y = GameCore.STATUS_Y + GameCore.STATUS_PAD
        line2_y = line1_y + GameCore.STATUS_LINE_H
        bar_x = GameCore.STATUS_BAR_X
        bar_ratio = remaining_sec / interval_sec
        bar_fill_w = round(GameCore.STATUS_BAR_W * bar_ratio)
        return (
            [
                (
                    "draw_rect",
                    GameCore.STATUS_X,
                    GameCore.STATUS_Y,
                    GameCore.STATUS_W,
                    GameCore.STATUS_H,
                    GameCore.STATUS_BG_COL,
                ),
            ]
            + self._expected_icon_value_right_calls(
                left_x,
                line1_y,
                *GameCore.ICON_MONEY,
                money,
                GameCore.STATUS_VALUE_MAX_DIGITS,
            )
            + self._expected_icon_value_calls(
                GameCore.STATUS_SHOP_COUNT_X,
                line1_y,
                *GameCore.ICON_SHOP_COUNT,
                f"{shop_count}/{Field.CLEAR_SHOP_COUNT}",
            )
            + self._expected_icon_value_right_calls(
                left_x,
                line2_y,
                *GameCore.ICON_TAX,
                tax,
                GameCore.STATUS_VALUE_MAX_DIGITS,
            )
            + [
                (
                    "draw_rect",
                    bar_x,
                    line2_y,
                    bar_fill_w,
                    GameCore.STATUS_BAR_H,
                    GameCore.STATUS_BAR_FILL_COL,
                ),
                (
                    "draw_rectb",
                    bar_x,
                    line2_y,
                    GameCore.STATUS_BAR_W,
                    GameCore.STATUS_BAR_H,
                    GameCore.STATUS_BAR_FRAME_COL,
                ),
            ]
            + self._expected_status_button_calls(paused=paused)
        )

    def _expected_status_button_calls(self, paused=False):
        """ステータス領域右のポーズ「||」・スピード「>」の2つのボタンの
        draw_rect（矩形）・draw_text（ラベル）呼び出し期待値を定数から
        計算する（ID-019 サイクル3）。段階の保持はまだ無い（次サイクル
        019-4 で足す）ため、スピードのラベルは常に「>」（最低速）固定の
        まま返す。ポーズ状態（paused）は呼び出し側から受け取り、2つの
        ボタンの配色（設計方針 6-1）へ反映する（ID-019 サイクル6。
        サイクル3時点の docstring が申し送っていた拡張そのもの）——
        ポーズ解除中（既定の paused=False）はポーズが無効表示（背景
        STATUS_BTN_DISABLED_COL）・スピードが通常表示（背景
        STATUS_BTN_COL）、ポーズ中（paused=True）はその逆になる。
        位置: 2つのボタンは幅・高さを共通にし（STATUS_BTN_W / _H）、
        ステータス領域の右端（内側余白 STATUS_PAD ぶんを残す）から
        左向きに、ポーズ → スピードの順で STATUS_BTN_GAP を空けて並び、
        縦位置はステータス領域の高さ（STATUS_H）の中央に揃える
        （実装 _draw_status_buttons() と同じ式を、実装から独立して
        ここに持つ）。
        ラベルの中央寄せ: 単一文字（「o」「x」など）を前提にした既存
        ボタンの "-2" 固定値を、文字数（FONT_CHAR_W）から求める形へ
        一般化する（「||」2文字・「>」〜「>>>」1〜3文字に対応するため）。
        矩形そのものは _expected_status_pause_button_rect() /
        _expected_status_speed_button_rect() と同じ式を共有する（ID-019
        サイクル6。片方だけレイアウト変更に追従し損なうことを防ぐ、
        実装の _status_speed_button_rect() と同じ考え方）"""
        pause_x, btn_y, _, _ = self._expected_status_pause_button_rect()
        speed_x, _, _, _ = self._expected_status_speed_button_rect()

        def button_calls(x, label, col):
            text_x = (
                x + (GameCore.STATUS_BTN_W - len(label) * GameCore.FONT_CHAR_W) // 2
            )
            text_y = btn_y + GameCore.STATUS_BTN_H // 2 - 2
            return [
                (
                    "draw_rect",
                    x,
                    btn_y,
                    GameCore.STATUS_BTN_W,
                    GameCore.STATUS_BTN_H,
                    col,
                ),
                ("draw_text", text_x, text_y, label),
            ]

        pause_col = (
            GameCore.STATUS_BTN_COL if paused else GameCore.STATUS_BTN_DISABLED_COL
        )
        speed_col = (
            GameCore.STATUS_BTN_DISABLED_COL if paused else GameCore.STATUS_BTN_COL
        )
        return button_calls(
            pause_x, GameCore.PAUSE_BTN_LABEL, pause_col
        ) + button_calls(speed_x, ">", speed_col)

    def _expected_status_speed_button_rect(self):
        """ステータス右のスピードボタン「>」系の矩形 (x, y, w, h) を、実装の
        _status_speed_button_rect() と同じ式として、実装から独立して持つ
        （_expected_settlement_popup_button_rect() と同じ、期待値を実装
        インスタンスから生成しないための鏡。ID-019 サイクル4）"""
        speed_x = (
            GameCore.STATUS_X
            + GameCore.STATUS_W
            - GameCore.STATUS_PAD
            - GameCore.STATUS_BTN_W
        )
        btn_y = GameCore.STATUS_Y + (GameCore.STATUS_H - GameCore.STATUS_BTN_H) // 2
        return speed_x, btn_y, GameCore.STATUS_BTN_W, GameCore.STATUS_BTN_H

    def _expected_status_pause_button_rect(self):
        """ステータス右のポーズボタン「||」の矩形 (x, y, w, h) を、実装の
        _status_pause_button_rect() と同じ式（スピードボタンの矩形から
        STATUS_BTN_GAP・STATUS_BTN_W ぶん左）として、実装から独立して持つ
        （_expected_status_speed_button_rect() と対になる鏡。ID-019
        サイクル6）"""
        speed_x, btn_y, btn_w, btn_h = self._expected_status_speed_button_rect()
        pause_x = speed_x - GameCore.STATUS_BTN_GAP - GameCore.STATUS_BTN_W
        return pause_x, btn_y, btn_w, btn_h

    def _expected_status_speed_button_label_call(self, label):
        """ステータス右のスピードボタンのラベル（draw_text）の呼び出し
        期待値を label から計算する（ID-019 サイクル4。押下を繰り返した
        ときにラベルが循環表示されることを確認するテストが使う）。位置は
        _expected_status_speed_button_rect() の矩形から、既存ボタンと同じ
        中央寄せの式で求める"""
        x, y, w, h = self._expected_status_speed_button_rect()
        text_x = x + (w - len(label) * GameCore.FONT_CHAR_W) // 2
        text_y = y + h // 2 - 2
        return ("draw_text", text_x, text_y, label)

    def _expected_settlement_remaining_sec(self, elapsed_ms):
        """決算タイマー起動（プレイヤー所有店舗の建設・復元）からの経過
        elapsed_ms に対する、残り時間の表示（秒への切り上げ）の期待値を返す。
        elapsed_ms < GameCore.SETTLEMENT_INTERVAL_MS の範囲でのみ有効
        （満了して巻き戻る境界そのものは、この単純な式では求まらない。
        GameCore.update() 経由で is_up() を呼んだときだけ起こる特別な遷移の
        ため、そちらは個々のテストが直接 60 を期待値に書く）。
        決算タイマーは他店建設・売上発生の各タイマーと同時（同じ
        _start_shop_clocks() 呼び出し）に起動するため、他の2つの
        タイマーのテストで使う elapsed_ms をそのまま渡せる"""
        return math.ceil((GameCore.SETTLEMENT_INTERVAL_MS - elapsed_ms) / 1000)

    def _expected_area_rate(self, col, row):
        """区画 (col, row) の地域価格倍率（千分率の整数。要件 3.10）を、
        Field._area_rate() を呼ばずに独立した式で求める（_expected_plot() /
        _expected_popup_x() と同じ、期待値を実装インスタンスから生成しない
        ための鏡）。距離はチェビシェフ距離（列方向は2つの中心列への最小距離、
        行方向は中心行との差、そのうち大きい方）で、倍率は中心地
        （距離0）が Field.AREA_RATE_CENTER、盤面上の最大距離の区画が
        Field.AREA_RATE_EDGE になるよう距離で線形に補間する（ID-020 決定1〜4）。
        **本ファイルのテストの大半はこの鏡を必要としない**——盤面の店舗は
        地域価格倍率が等倍（1.0）になる列0・列17へ寄せてあり（ID-020 案8-A。
        test_field.py がステップ 020-2 で採った方針の踏襲）、倍率が金額へ効く
        ことそのものの検証は test_field.py の TestFieldArea* が担うためである。
        鏡が要るのは**押下位置そのものが検証の対象で、区画を選び直せない**
        テスト（TestPopupPosition・TestPopupOnPress のように画面の左右半分や
        盤面の四隅・中央を名指しで押すもの、TestPopupPreview の区画境界、
        盤面全体を埋めるもの）に限られる"""
        col_distance = min(
            abs(col - (Field.GRID_COLS - 1) // 2), abs(col - Field.GRID_COLS // 2)
        )
        row_distance = abs(row - Field.GRID_ROWS // 2)
        distance = max(col_distance, row_distance)
        return (
            Field.AREA_RATE_CENTER
            - (Field.AREA_RATE_CENTER - Field.AREA_RATE_EDGE)
            * distance
            // Field.AREA_MAX_DISTANCE
        )

    def _expected_tax(self, player_values, other_values=(), player_rates=None):
        """支払い予定税額の期待値を、Field.total_tax() を呼ばずに独立した式で
        求める（_expected_shop_calls() などと同じ、実装から独立した鏡の
        書き方）。player_values はプレイヤー所有店舗の資産価値の列、
        other_values は同じ盤面にある NPC 所有店舗の資産価値の列（地価には
        加わるが、土地税の軒数にも資産税の対象にも数えない）。
        player_rates はプレイヤー所有店舗の**区画ごとの地域価格倍率**の列で、
        土地税が `Σ(地価 × その区画の倍率 // Shop.AREA_RATE_BASE)`（区画ごとに
        丸めてから合計。要件 3.8）であることを式で表す。省略すると全区画が
        等倍（1.0）とみなす——本ファイルのテストの盤面は列0・列17へ寄せてあり
        （ID-020 案8-A）、そのとき `地価 × 1000 // 1000 = 地価` となって
        「プレイヤー所有店舗数 × 地価」という従来式と厳密に一致するため、
        既存の呼び出し側は倍率を渡さずに済む。倍率の乗る区画を避けられない
        盤面（盤面全体を埋めるテスト）だけが明示的に渡す。
        盤面の副次的な結果として税額が要るだけの既存の描画テスト（建設・増資・
        買収・復元で作った盤面に対して、税額そのものではなく建設等の結果を
        検証する）向けの組み立てで、式の形は Field.total_tax() と同じになる
        （盤面から独立した数値ではなく式を共有する）。税の算出そのものを
        検証する test_field.py の TestFieldTotalTax・本ファイルの
        TestDrawSettlementStatus は、実装と同じ式を書かず期待値を数値で
        書き下ろす別の原則に従う（打ち消し合いが起きない盤面を選び、Field 側
        の式の誤りを検知できる形を保つ）"""
        if player_rates is None:
            player_rates = [Shop.AREA_RATE_BASE] * len(player_values)
        assert len(player_rates) == len(player_values)
        total_value = sum(player_values) + sum(other_values)
        land_price = total_value // Field.GRID_PLOT_COUNT
        land_tax = sum(
            land_price * rate // Shop.AREA_RATE_BASE for rate in player_rates
        )
        asset_tax = sum(player_values) * Field.ASSET_TAX_RATE_PERCENT // 100
        return land_tax + asset_tax

    def _expected_shop_calls(self, shops, scale=Shop.INITIAL_SCALE):
        """店舗の draw_image 呼び出し期待値を定数から計算する。`shops` は
        (col, row, owner) のリスト。`scale` は店舗規模（既定は設置直後の初期値。
        全店舗が同じ規模であることを前提とする）
        画面座標: shop_x = GRID_LEFT + col * PLOT_SIZE
                  shop_y = FIELD_ORIGIN_Y + row * PITCH
                  （区画上部 = FIELD_ORIGIN_Y + row*PITCH + ROAD_SIZE より ROAD_SIZE 分だけ上）
        転送元:   u = SHOP_U_ORIGIN + SHOP_U_STEP * (規模 - 1)
                  v = SHOP_V_NPC（NPC所有） / SHOP_V_PLAYER（プレイヤー所有）
        """
        return [
            (
                "draw_image",
                GameCore.GRID_LEFT + col * GameCore.PLOT_SIZE,
                GameCore.FIELD_ORIGIN_Y + row * GameCore.PITCH,
                GameCore.SHOP_IMG,
                GameCore.SHOP_U_ORIGIN + GameCore.SHOP_U_STEP * (scale - 1),
                (
                    GameCore.SHOP_V_PLAYER
                    if owner == Owner.PLAYER
                    else GameCore.SHOP_V_NPC
                ),
                GameCore.SHOP_W,
                GameCore.SHOP_H,
                GameCore.SHOP_COLKEY,
            )
            for col, row, owner in shops
        ]

    def _expected_popup_x(self, x):
        """押下位置（画面座標）x から、期待するポップアップ原点 x を計算する。
        実装の _popup_origin_x() と同じ規則（画面右半分 x >= SCREEN_W // 2 は
        左下 POPUP_LEFT_X、左半分は右下 POPUP_RIGHT_X）を、実装から独立した
        式として持つ（期待値は実装インスタンスから生成しない）"""
        return (
            GameCore.POPUP_LEFT_X
            if x >= GameCore.SCREEN_W // 2
            else GameCore.POPUP_RIGHT_X
        )

    def _outside_plot_positions(self):
        """どの区画にも属さない押下位置を (ケース名, 押下位置) の並びで返す。
        盤面の三方向（上のステータス領域・左の余白・最下段の閉じの道路）から
        1点ずつ選んであり、いずれも _expected_plot() が None を返す。
        「区画外での押下・解除」を扱うテストが共有する（同じ3点を複数の
        テストが直書きすると、盤面のレイアウトが変わったときに片方だけ
        追従し損なう）"""
        return [
            ("ステータス領域", (GameCore.GRID_LEFT, GameCore.FIELD_ORIGIN_Y - 1)),
            ("左の余白", (GameCore.GRID_LEFT - 1, GameCore.FIELD_ORIGIN_Y)),
            (
                "最下段の閉じの道路",
                (
                    GameCore.GRID_LEFT,
                    GameCore.FIELD_ORIGIN_Y + GameCore.GRID_ROWS * GameCore.PITCH,
                ),
            ),
        ]

    def _is_in_popup(self, popup_x, pos):
        """押下位置（画面座標）pos が、原点 x = popup_x のポップアップの矩形の
        内側かを計算する。実装の遮断判定（_point_in_rect() へ POPUP_W /
        POPUP_H / POPUP_Y を渡す形）と同じ半開区間の規則を、実装から独立した
        式として持つ（_expected_popup_x() / _expected_plot() と同じ鏡）。
        固定表示中の押下を扱うテストが「その押下位置がポップアップの内側か
        外側か」という前提を明示するために使う——座標を直書きすると、
        POPUP_W や POPUP_Y の変更で前提が崩れたまま通り続けてしまう"""
        x, y = pos
        return (
            popup_x <= x < popup_x + GameCore.POPUP_W
            and GameCore.POPUP_Y <= y < GameCore.POPUP_Y + GameCore.POPUP_H
        )

    def _expected_plot(self, pos):
        """押下位置（画面座標）pos から、期待する区画 (col, row) を計算する
        （区画外は None）。実装の _screen_to_plot() と同じ規則（原点 GRID_LEFT /
        FIELD_ORIGIN_Y、刻み PLOT_SIZE / PITCH、半開区間）を、実装から独立した
        式として持つ（_expected_popup_x() と同じく、期待値を実装インスタンスから
        生成しないための鏡）"""
        x, y = pos
        col = (x - GameCore.GRID_LEFT) // GameCore.PLOT_SIZE
        row = (y - GameCore.FIELD_ORIGIN_Y) // GameCore.PITCH
        if not (0 <= col < GameCore.GRID_COLS and 0 <= row < GameCore.GRID_ROWS):
            return None
        return col, row

    def _expected_selection_calls(self, pos):
        """選択中の区画をフィールド上で示す黄色い枠（draw_rectb）の呼び出し期待値を
        定数から計算する。pos はその選択を決めた押下位置（TRACKING なら現在の
        押下位置、MODAL なら解除した時点の押下位置）で、区画外なら枠は描かれない
        （空リスト）。
        位置   = (GRID_LEFT + col * PLOT_SIZE, FIELD_ORIGIN_Y + row * PITCH)
        サイズ = PREVIEW_W × PREVIEW_H（店舗画像とその下の道路を合わせた範囲。
                 ポップアップのプレビュー領域と同じ大きさ）
        位置の式は _expected_shop_calls()（店舗画像の描画位置）と同一で、
        サイズはポップアップのプレビュー領域（_expected_popup_calls() が
        下の道路を置く範囲）と同一である。**枠は判定範囲（高さ PITCH = 24）より
        道路 1 本分だけ縦に長い**（中間プレイテストでの指示による変更。枠の中に
        見えるものとプレビューに描かれるものを一致させることを優先した）"""
        plot = self._expected_plot(pos)
        if plot is None:
            return []
        col, row = plot
        return [
            (
                "draw_rectb",
                GameCore.GRID_LEFT + col * GameCore.PLOT_SIZE,
                GameCore.FIELD_ORIGIN_Y + row * GameCore.PITCH,
                GameCore.PREVIEW_W,
                GameCore.PREVIEW_H,
                GameCore.SELECTION_COL,
            )
        ]

    def _expected_sales_frame_calls(self, plot):
        """売上の抽選が起きた店舗を囲む枠（draw_rectb）の呼び出し期待値を定数から
        計算する。plot は抽選された区画 (col, row) で、まだ1度も抽選が起きて
        いなければ None（囲みは描かれない＝空リスト）。
        位置   = (GRID_LEFT + col * PLOT_SIZE, FIELD_ORIGIN_Y + row * PITCH)
        サイズ = PREVIEW_W × PREVIEW_H（**選択枠と同じ、店舗画像とその下の
                 道路を合わせた範囲**）
        位置・サイズの式は _expected_selection_calls(pos) と同一（**選択枠と
        原点・幅・高さのすべてが一致する**）。そのため同じ区画で両方の期待値が
        並ぶとき、色（SALES_FRAME_COL / SELECTION_COL）だけが異なる2件の
        draw_rectb になる。実際の描画では後に描く選択枠が同じ範囲を上書きし、
        画面上は選択枠の色だけが見える（_draw_sales_frame() の docstring）。
        引数が**押下位置ではなく区画そのもの**である点が
        _expected_selection_calls(pos) と異なる（売上の囲みは押下と無関係に、
        抽選の結果だけで決まる）"""
        if plot is None:
            return []
        col, row = plot
        return [
            (
                "draw_rectb",
                GameCore.GRID_LEFT + col * GameCore.PLOT_SIZE,
                GameCore.FIELD_ORIGIN_Y + row * GameCore.PITCH,
                GameCore.PREVIEW_W,
                GameCore.PREVIEW_H,
                GameCore.SALES_FRAME_COL,
            )
        ]

    def _expected_selection_and_popup_calls(self, pos, **popup_kwargs):
        """選択中の区画に対する描画（フィールド上の黄色い枠 → ポップアップ）の
        期待値を、その選択を決めた押下位置 pos ひとつから組み立てる。
        枠とポップアップはどちらも同じ「選択中の区画」から導かれ、描画の有無が
        常に一致する（設計判断「枠の描画有無はポップアップの描画有無と完全に
        一致する」）。期待値も1つのメソッドから同時に組み立てることで、
        **片方だけを期待する書き方ができない**ようにしている。
        描画順は「店舗 → 選択枠 → ポップアップ」のため、枠の呼び出しを
        ポップアップの前に置く。popup_kwargs はポップアップ側の内容
        （owner / scale / cost / value / sales）で、そのまま
        _expected_popup_calls() へ渡す（表示位置 popup_x は pos から導く）。
        地域価格倍率（area_rate。ID-020）も pos が指す区画から
        _expected_area_rate() で導いて渡す——ポップアップの費用・資産価値・
        売上額はいずれも選択中の区画の倍率を反映した値であり（要件 3.10）、
        その倍率は表示位置と同じく押下位置ひとつから決まるためである。
        呼び出し側が area_rate を明示した場合はそちらを優先する（区画の
        外を押したときのように pos から区画が定まらない場合も等倍を使う）"""
        plot = self._expected_plot(pos)
        if "area_rate" not in popup_kwargs and plot is not None:
            popup_kwargs["area_rate"] = self._expected_area_rate(*plot)
        return self._expected_selection_calls(pos) + self._expected_popup_calls(
            popup_x=self._expected_popup_x(pos[0]), **popup_kwargs
        )

    def _expected_popup_calls(
        self,
        owner=None,
        scale=Shop.INITIAL_SCALE,
        cost=None,
        value=None,
        sales=None,
        popup_x=GameCore.POPUP_LEFT_X,
        o_enabled=True,
        area_rate=Shop.AREA_RATE_BASE,
    ):
        """ポップアップ描画の呼び出し期待値を定数から計算する。
        背景の塗りつぶし・枠線に続き、プレビュー領域（下の道路 → 店舗画像）、
        数値3行（費用・資産価値・売上額）を積み上げる（「o」「x」ボタンは
        以降のサイクルで本メソッドへ積み上げる）。
        道路は区画の状態によらず常に同じ位置・同じ2枚が描かれ、店舗画像は
        owner を渡したときだけ道路の後に描かれる（省略時は空き区画として扱う）。
        popup_x はその回のポップアップ原点 x（POPUP_LEFT_X / POPUP_RIGHT_X の
        いずれか。呼び出し側が押下位置から _expected_popup_x() で求めて渡す）。
        ポップアップ内の全要素をこの1つの原点からの相対で組み立てることで、
        実装側の原点の一元化が破れていれば必ず検出できるようにする。
        背景: 位置 (popup_x, POPUP_Y)、サイズ POPUP_W × POPUP_H、色 POPUP_BG_COL
        枠線: 背景と同じ位置・同じサイズで、色は POPUP_BORDER_COL。塗りつぶしの
              後に描くことで、背景に上書きされず枠が残る
        プレビュー原点: (popup_x + POPUP_PAD, POPUP_Y + POPUP_PAD)。領域全体の
              大きさは PREVIEW_W × PREVIEW_H で、フィールド上の選択枠と同一
        下の道路: プレビュー原点から y = SHOP_H だけ下、ROAD_SIZE 幅で2枚横に並ぶ
        店舗画像: プレビュー原点そのもの（rel y = 0）、16×24、道路の後に描かれる
        数値3行: 費用→資産価値（value）→売上額の順。アイコン（ICON_COST /
                ICON_VALUE / ICON_SALES）と、最大 POPUP_VALUE_MAX_DIGITS 桁ぶんの
                幅で右詰めにした数値の組（_expected_icon_value_right_calls()。
                ID-026 サイクル026-1で新設・026-5 で本メソッドへ採用）を、
                x = プレビュー原点 + PLOT_SIZE + POPUP_GAP、
                y = POPUP_Y + POPUP_PAD + POPUP_VALUES_TOP_PAD + 行 i *
                POPUP_LINE_H へ描画する。POPUP_VALUES_TOP_PAD は3行のブロックを
                プレビュー領域（PREVIEW_H）に対して縦方向中央へ揃えるための
                上余白（ID-026 サイクル026-5。中間プレイテスト指示——3行が
                プレビュー画像に対して上に詰まって見えるため）。
                費用アイコンは区画の状態（owner）によらず常に ICON_COST の
                1種（ID-026 決定3。建設・増資・買収のいずれも同じ転送元）で、
                増資費用が「-」（POPUP_NO_COST_TEXT）のときもアイコンは描かれる
                （決定5-A。項目そのものは存在し、値だけが存在しないため）
        cost / value / sales は GameCore が Field からそのまま relay する値のため、
        省略時は Field/Shop の設置直後の既定値（owner と area_rate から導かれる
        値）を使う。area_rate は選択中の区画の地域価格倍率（千分率。ID-020）で、
        省略すると等倍（Shop.AREA_RATE_BASE）——本ファイルのテストの盤面は
        倍率が等倍になる列0・列17へ寄せてあるため（ID-020 案8-A）、大半の
        呼び出し側はこの既定値のままで済む。押下位置そのものが検証の対象で
        区画を選び直せないテストだけが、_expected_selection_and_popup_calls()
        経由（押下位置から自動で導かれる）または明示で倍率を渡す。
        費用・売上額を区画の状態で切り替える業務ロジックそのものは Field/Shop の
        責務であり、その検証は test_field.py 側（TestFieldCostAndSales）で行う。
        数値3行の後に「o」「x」ボタン（矩形＋文字）を積み上げる。o_enabled は
        「o」ボタンを有効な見た目（塗りつぶし）で描くかで、そのまま
        _expected_popup_button_calls() へ渡す（区画の状態と資金から決まるため、
        呼び出し側が明示する）"""
        preview_x = popup_x + GameCore.POPUP_PAD
        preview_y = GameCore.POPUP_Y + GameCore.POPUP_PAD
        road_y = preview_y + GameCore.SHOP_H
        calls = [
            (
                "draw_rect",
                popup_x,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                GameCore.POPUP_BG_COL,
            ),
            (
                "draw_rectb",
                popup_x,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                GameCore.POPUP_BORDER_COL,
            ),
        ]
        calls += [
            (
                "draw_image",
                preview_x + i * GameCore.ROAD_SIZE,
                road_y,
                GameCore.ROAD_IMG,
                GameCore.ROAD_U,
                GameCore.ROAD_V,
                GameCore.ROAD_SIZE,
                GameCore.ROAD_SIZE,
                GameCore.ROAD_COLKEY,
            )
            for i in range(GameCore.PREVIEW_W // GameCore.ROAD_SIZE)
        ]
        if owner is not None:
            calls.append(
                (
                    "draw_image",
                    preview_x,
                    preview_y,
                    GameCore.SHOP_IMG,
                    GameCore.SHOP_U_ORIGIN + GameCore.SHOP_U_STEP * (scale - 1),
                    (
                        GameCore.SHOP_V_PLAYER
                        if owner == Owner.PLAYER
                        else GameCore.SHOP_V_NPC
                    ),
                    GameCore.SHOP_W,
                    GameCore.SHOP_H,
                    GameCore.SHOP_COLKEY,
                )
            )
        if value is None:
            value = self._default_shop_value(owner, area_rate=area_rate)
        if cost is None:
            cost = self._default_shop_cost(owner, scale, value, area_rate=area_rate)
        if sales is None:
            sales = self._default_shop_sales(owner, scale, area_rate=area_rate)
        text_x = preview_x + GameCore.PLOT_SIZE + GameCore.POPUP_GAP
        values_top_y = (
            GameCore.POPUP_Y + GameCore.POPUP_PAD + GameCore.POPUP_VALUES_TOP_PAD
        )
        icons = (GameCore.ICON_COST, GameCore.ICON_VALUE, GameCore.ICON_SALES)
        for i, (num, (u, v)) in enumerate(zip((cost, value, sales), icons)):
            calls += self._expected_icon_value_right_calls(
                text_x,
                values_top_y + i * GameCore.POPUP_LINE_H,
                u,
                v,
                num,
                GameCore.POPUP_VALUE_MAX_DIGITS,
            )
        calls += self._expected_popup_button_calls(popup_x, o_enabled=o_enabled)
        return calls

    def _expected_button_rect(self, popup_x, index):
        """ポップアップ原点 x（popup_x）と定数 POPUP_Y から、index 番目のボタン
        （0: 「o」（上）, 1: 「x」（下））の矩形 (x, y, w, h) を、実装
        （_popup_button_rect()）とは独立した式で計算する。矩形はポップアップ幅
        いっぱい（左右に内側余白 POPUP_PAD ぶんを残す）に広げ、o（上）・x（下）の
        2つを POPUP_BTN_GAP 空けて縦に並べ、ブロック全体をポップアップ下端から
        内側余白ぶん上を起点に置く。_expected_popup_button_calls()（描画の期待値）と
        TestPopupButtonPress（押下判定の期待値）の両方から使われる共通の計算式"""
        block_h = 2 * GameCore.POPUP_BTN_H + GameCore.POPUP_BTN_GAP
        block_top = GameCore.POPUP_Y + GameCore.POPUP_H - GameCore.POPUP_PAD - block_h
        btn_x = popup_x + GameCore.POPUP_PAD
        btn_y = block_top + index * (GameCore.POPUP_BTN_H + GameCore.POPUP_BTN_GAP)
        return btn_x, btn_y, GameCore.POPUP_BTN_W, GameCore.POPUP_BTN_H

    def _expected_popup_button_calls(
        self, popup_x=GameCore.POPUP_LEFT_X, o_enabled=True
    ):
        """ポップアップ内の「o」「x」ボタンの矩形・アイコン（draw_image）呼び出し
        期待値を定数から計算する（ID-026 サイクル026-3。文字からアイコンへ
        置き換えた）。この順（o の矩形→アイコン→x の矩形→アイコン）で
        描画される。矩形は _expected_button_rect() から導く。アイコンは矩形の
        中央へ置く（_expected_icon_button_calls()）——実行ボタン「o」は
        ICON_OK、キャンセルボタン「x」は ICON_CANCEL。
        popup_x はその回のポップアップ原点 x（POPUP_LEFT_X / POPUP_RIGHT_X の
        いずれか）。
        o_enabled=False（資金不足で「o」を押せない状態）のときだけ、「o」の矩形が
        塗りつぶし（draw_rect・POPUP_BTN_COL）から枠線のみ（draw_rectb・
        POPUP_BTN_DISABLED_COL）へ変わる。矩形の位置・大きさとアイコンの
        転送元・位置は有効・無効で変わらず（決定5と同じく「見た目は押せそう
        なのに押せない」を作らない）、「x」は常に塗りつぶしで描かれる"""
        icons = (GameCore.ICON_OK, GameCore.ICON_CANCEL)
        calls = []
        for index, (u, v) in enumerate(icons):
            btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
            if index == GameCore.POPUP_BTN_INDEX_O and not o_enabled:
                calls.append(
                    (
                        "draw_rectb",
                        btn_x,
                        btn_y,
                        btn_w,
                        btn_h,
                        GameCore.POPUP_BTN_DISABLED_COL,
                    )
                )
            else:
                calls.append(
                    ("draw_rect", btn_x, btn_y, btn_w, btn_h, GameCore.POPUP_BTN_COL)
                )
            calls += self._expected_icon_button_calls(btn_x, btn_y, btn_w, btn_h, u, v)
        return calls

    def _default_shop_cost(
        self,
        owner,
        scale=Shop.INITIAL_SCALE,
        value=None,
        area_rate=Shop.AREA_RATE_BASE,
    ):
        """費用を求める。空き区画（owner が None）は建設費用（Shop.BUILD_COST ×
        地域価格倍率）、プレイヤー所有店舗は店舗規模に応じた増資費用
        （Shop.INVEST_COST × 2^(規模-1) × 地域価格倍率。ID-007 以降、cost は
        設置時の既定値ではなく所有者と規模から都度導出される値のため、scale を
        受け取れる形にしている）、NPC所有店舗は資産価値の Shop.BUYOUT_RATE 倍
        （ID-009 以降、cost は資産価値から都度導出される値のため、value を
        受け取れる形にしている。既定値は _default_shop_value() と同じ設置直後の
        資産価値で、そちらが既に倍率を反映しているため**ここで倍率を重ねて
        掛けない**——買収費用は資産価値経由で倍率が乗る。ID-020 決定4）。
        area_rate（千分率。省略すると等倍 Shop.AREA_RATE_BASE）は呼び出し側が
        区画から _expected_area_rate() で求めて渡す。丸め（切り捨て）は金額を
        得るこの箇所で1回だけ行う。
        ただしプレイヤー所有店舗の規模が上限（Shop.SCALE_MAX）のときは増資
        できず**増資費用が存在しない**ため、表示上の既定値は数値ではなく
        「-」の1文字になる（要件 3.6）。この分岐は実装側の戻り値を参照せず
        Shop.SCALE_MAX から独立に導く（ヘルパーが実装とは独立した式で期待値を
        組み立てるという本メソッドの位置づけをそのまま保つ）。規模が上限でも
        NPC所有店舗は買収できるため買収費用は数値のままで、分岐は
        プレイヤー所有の内側に置く。cost を明示的に渡さない呼び出し側のための
        デフォルト値であり、区画の状態・店舗規模・資産価値・地域価格倍率に
        よる費用の切り替えという業務ロジックそのものの検証は test_field.py 側
        （TestFieldCostAndSales / TestFieldAreaCost）で行う"""
        if value is None:
            value = self._default_shop_value(owner, area_rate=area_rate)
        if owner is None:
            return Shop.BUILD_COST * area_rate // Shop.AREA_RATE_BASE
        if owner == Owner.PLAYER:
            if scale >= Shop.SCALE_MAX:
                return "-"
            return (
                Shop.INVEST_COST * 2 ** (scale - 1) * area_rate // Shop.AREA_RATE_BASE
            )
        return value * Shop.BUYOUT_RATE

    def _default_shop_value(self, owner, area_rate=Shop.AREA_RATE_BASE):
        """設置直後の資産価値を求める。空き区画（owner が None）は 0、店舗が
        あれば地域価格倍率を反映した設置費用（Shop.BUILD_COST × 倍率。
        要件 3.11 の増資 0 回の状態）。
        _default_shop_cost() と同じく、value を明示的に渡さない呼び出し側
        （設置直後の状態のまま検証するテスト）のためのデフォルト値であり、
        「設置すると資産価値が設置費用になる」という業務ロジックそのものの
        検証は test_field.py 側（TestFieldShop / TestFieldAreaValue）で行う"""
        if owner is None:
            return 0
        return Shop.BUILD_COST * area_rate // Shop.AREA_RATE_BASE

    def _default_shop_sales(
        self, owner, scale=Shop.INITIAL_SCALE, area_rate=Shop.AREA_RATE_BASE
    ):
        """売上額を求める。空き区画（owner が None）は 0、店舗があれば店舗規模に
        応じた基準額（Shop.SALES_AMOUNT × 2^(規模-1)。ID-010 以降、sales は
        設置時の既定値ではなく規模から都度導出される値のため、scale を受け取れる
        形にしている。所有者では値は変わらない）へ**中心売上倍率**（地域価格
        倍率の Shop.CENTER_SALES_EXPONENT 乗。要件 3.10）を掛けた額。
        中間の倍率は丸めず、指数乗した分母で1回だけ割る（先に千分率へ丸めて
        から指数乗すると値がずれる。ID-020 決定4）。sales を明示的に渡さない
        呼び出し側のためのデフォルト値であり、店舗規模・中心売上倍率による
        売上額の切り替えという業務ロジックそのものの検証は test_field.py 側
        （TestFieldCostAndSales / TestFieldAreaSales）で行う"""
        if owner is None:
            return 0
        return (
            Shop.SALES_AMOUNT
            * 2 ** (scale - 1)
            * area_rate**Shop.CENTER_SALES_EXPONENT
            // Shop.AREA_RATE_BASE**Shop.CENTER_SALES_EXPONENT
        )

    def _plot_center_pos(self, col, row):
        """区画 (col, row) の判定範囲の中心の画面座標を返す。判定範囲は
        x が [GRID_LEFT + col * PLOT_SIZE, + PLOT_SIZE)、
        y が [FIELD_ORIGIN_Y + row * PITCH, + PITCH)（縦は道路 + 区画の 1 ピッチ全体）
        """
        return (
            GameCore.GRID_LEFT + col * GameCore.PLOT_SIZE + GameCore.PLOT_SIZE // 2,
            GameCore.FIELD_ORIGIN_Y + row * GameCore.PITCH + GameCore.PITCH // 2,
        )

    def _press(self, core, pos):
        """押下位置 pos を押した状態で update() を 1 フレーム進める（描画はしない）。
        押下 → 移動 → 解除 のようなフレーム列を組み立てるための最小単位"""
        self.test_input.set_down(True)
        self.test_input.set_pos(*pos)
        core.update()

    def _release(self, core):
        """押下を解除して update() を 1 フレーム進める（描画はしない）。
        押下位置は解除の直前の値のまま保持する（実際のマウスと同じく、
        ボタンを離しただけではカーソルは動かない）"""
        self.test_input.set_down(False)
        core.update()

    def _draw(self, core):
        """draw() を実行する。描画呼び出しの記録は draw() の直前にリセットし、
        前のフレームの記録が混ざらないようにする"""
        self.test_view.call_params = []
        core.draw()

    def _press_plot(self, core, col, row):
        """区画 (col, row) を押し、解除して選択を固定する（TRACKING →
        MODAL）。区画選択ポップアップのその回の原点 x を返す（続く
        「o」ボタン押下の位置計算に使う）"""
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return self._expected_popup_x(pos[0])

    def _press_o_button(self, core, popup_x):
        """区画選択ポップアップ（原点 x = popup_x）の「o」ボタンを押す。
        選択中の区画の所有者に応じて建設・増資・買収のいずれかが実行される
        （_update_popup() の分岐）"""
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _press_plot_and_o_button(self, core, col, row):
        """区画 (col, row) を選択し、その「o」ボタンを押す（押下 → 解除 →
        「o」ボタン押下の3フレーム）。建設・買収・増資のいずれも同じ
        _update_popup() の分岐を通るため、これ1つで3つの操作すべてに使える。
        押下したままで終わるため、続けて別の操作を行うテストは呼び出し側で
        _release() まで行う（ID-017 サイクル4で2ファイル目の呼び手が現れた
        ため、test_main_popup.py の TestGameEndPopup から TestParent へ
        移した。_core_with_settlement_popup_shown() を移したときと同じ判断）"""
        self._press_o_button(core, self._press_plot(core, col, row))

    def _update_and_draw(self, core, pos):
        """押下位置 pos（None なら押下なし）を入力へ与えて update() → draw() を実行する。
        ポップアップの有無は押下の状態から決まるため、描画の前に必ず update() を通す"""
        if pos is None:
            self._release(core)
        else:
            self._press(core, pos)
        self._draw(core)

    def _expected_settlement_popup_calls(self):
        """決算ポップアップの背景・枠線（draw_rect・draw_rectb）の呼び出し期待値を
        定数から計算する（ID-015 サイクル1）。決算ポップアップは区画選択の
        枠・ポップアップより後（最前面）に描かれるため、呼び出し側は自分の
        期待値リストの末尾へ足す形で使う（_expected_selection_and_popup_calls()
        などの後ろに連結する）。
        位置・大きさ・配色（SETTLEMENT_POPUP_*）はいずれも仮値で、
        プレイテストで確定する。数値3行の表示は
        _expected_settlement_popup_value_calls() が別に持つ（背景・枠線と
        3行とで呼び手が異なるため。サイクル1のテストは3行を持たない盤面
        （self._settlement_popup_state を SHOWN へ直接立てるだけ）を前提に
        本メソッドを単独で使い続けている）"""
        return [
            (
                "draw_rect",
                GameCore.SETTLEMENT_POPUP_X,
                GameCore.SETTLEMENT_POPUP_Y,
                GameCore.SETTLEMENT_POPUP_W,
                GameCore.SETTLEMENT_POPUP_H,
                GameCore.SETTLEMENT_POPUP_BG_COL,
            ),
            (
                "draw_rectb",
                GameCore.SETTLEMENT_POPUP_X,
                GameCore.SETTLEMENT_POPUP_Y,
                GameCore.SETTLEMENT_POPUP_W,
                GameCore.SETTLEMENT_POPUP_H,
                GameCore.SETTLEMENT_POPUP_BORDER_COL,
            ),
        ]

    def _expected_settlement_popup_value_calls(self, before, tax, after):
        """決算ポップアップ内の数値3行（減算前・税額・減算後）を筆算の形
        （ID-027 サイクル027-3。決定8〜決定12）にした呼び出し期待値を定数から
        計算する。3つの値は呼び出し側が計算して渡す（本メソッドは
        Field.total_tax() を呼ばず、受け取った3値をそのまま並べるだけの
        relay。実装から期待値を生成しない原則は _expected_tax() と同じ）。
        呼び出し側は _expected_settlement_popup_calls()（背景・枠線）の後ろへ
        本メソッドの戻り値を連結する形で使う。
        描画順は「数値3行 → 横線 → `-`」で1つに固定する（決定8）——
        数値3行の並び自体は ID-015 サイクル2時点から変えていないため、
        既存の呼び出し元（8箇所）が読む添字（例: 税額の draw_text が
        3番目）は本サイクルでも動かない。
        数値: 幅 FONT_CHAR_W × STATUS_VALUE_MAX_DIGITS の領域（右端 =
        SETTLEMENT_POPUP_X + SETTLEMENT_POPUP_W − SETTLEMENT_POPUP_VALUE_
        RIGHT_GAP）の中で右詰めにする（決定10。想定桁数はプレイヤー
        ステータスの資金・税額と同じ STATUS_VALUE_MAX_DIGITS を流用する
        ——専用定数は新設しない〈ユーザー指示による改訂〉。max_digits を
        超える桁はキャップせずそのまま左へはみ出す。右端をポップアップ右
        枠から SETTLEMENT_POPUP_VALUE_RIGHT_GAP ぶん空ける形は、プレイ
        テスト指摘〈2026-08-30〉による改訂——罫線の長さに対して数字が中央
        寄りに見えていたのを、右寄りへ変更した）。
        横線: 2行目・3行目の行間へ高さ1で描く（決定9）。左端・幅は数値
        領域の全幅（決定11）。
        `-`: 横線の左端の真上・2行目（税額）の行に、独立した draw_text として
        描く（決定12。税額の数値へ連結すると右詰め計算に1文字食い込み、
        3行の桁の縦の揃いが崩れるため）。
        3行目（減算後）の y は、横線との間に SETTLEMENT_POPUP_RULE_TEXT_GAP
        ぶんの余白を挟んで下へずらす（プレイテスト指摘。2026-08-30。当初は
        横線の直下に数字が接していた）。1・2行目と横線・`-` の y は動かさない"""
        text_x = GameCore.SETTLEMENT_POPUP_X + GameCore.SETTLEMENT_POPUP_PAD
        text_y = GameCore.SETTLEMENT_POPUP_Y + GameCore.SETTLEMENT_POPUP_PAD
        max_digits = GameCore.STATUS_VALUE_MAX_DIGITS
        value_area_x = (
            GameCore.SETTLEMENT_POPUP_X
            + GameCore.SETTLEMENT_POPUP_W
            - GameCore.SETTLEMENT_POPUP_VALUE_RIGHT_GAP
            - max_digits * GameCore.FONT_CHAR_W
        )
        row_y_offsets = (0, 0, GameCore.SETTLEMENT_POPUP_RULE_TEXT_GAP)
        calls = []
        for i, num in enumerate((before, tax, after)):
            text = str(num)
            number_x = value_area_x + (max_digits - len(text)) * GameCore.FONT_CHAR_W
            row_y = text_y + i * GameCore.SETTLEMENT_POPUP_LINE_H + row_y_offsets[i]
            calls.append(("draw_text", number_x, row_y, text))
        rule_y = text_y + 2 * GameCore.SETTLEMENT_POPUP_LINE_H - 1
        rule_w = GameCore.SETTLEMENT_POPUP_W - 2 * GameCore.SETTLEMENT_POPUP_PAD
        calls.append(
            ("draw_rect", text_x, rule_y, rule_w, 1, GameCore.SETTLEMENT_POPUP_RULE_COL)
        )
        calls.append(
            ("draw_text", text_x, text_y + GameCore.SETTLEMENT_POPUP_LINE_H, "-")
        )
        return calls

    def _expected_settlement_popup_button_rect(self):
        """決算ポップアップ内の「o」ボタンの矩形 (x, y, w, h) を、実装の
        _settlement_popup_button_rect() と同じ式（数値3行の直後に内側余白
        SETTLEMENT_POPUP_PAD を挟んで置く）を、実装から独立した式として持つ
        （_expected_button_rect() と同じく、期待値を実装インスタンスから
        生成しないための鏡）"""
        btn_x = GameCore.SETTLEMENT_POPUP_X + GameCore.SETTLEMENT_POPUP_PAD
        btn_y = (
            GameCore.SETTLEMENT_POPUP_Y
            + GameCore.SETTLEMENT_POPUP_PAD
            + 3 * GameCore.SETTLEMENT_POPUP_LINE_H
            + GameCore.SETTLEMENT_POPUP_RULE_TEXT_GAP
            + GameCore.SETTLEMENT_POPUP_PAD
        )
        return (
            btn_x,
            btn_y,
            GameCore.SETTLEMENT_POPUP_BTN_W,
            GameCore.SETTLEMENT_POPUP_BTN_H,
        )

    def _expected_settlement_popup_button_calls(self):
        """決算ポップアップ内の「o」ボタンの矩形・アイコン（draw_image）呼び出し
        期待値を定数から計算する（ID-015 サイクル5 Refactor・再考。ポップアップ
        全体をタップ対象にしていた当初の形から、区画選択ポップアップと同じ
        「押せるボタン」の形へ変更した。ID-026 サイクル026-3で文字から
        ICON_OK アイコンへ置き換えた）。区画選択ポップアップの「o」と異なり
        無効表示（draw_rectb）を持たない——精算には可否条件が無いため、常に
        塗りつぶし（draw_rect・SETTLEMENT_POPUP_BTN_COL）で描かれる。アイコンは
        矩形の中央へ置く（_expected_icon_button_calls()）。
        呼び出し側は _expected_settlement_popup_calls()（背景・枠線）+
        _expected_settlement_popup_value_calls()（数値3行）の後ろへ本メソッドの
        戻り値を連結する形で使う（決算ポップアップの描画順は背景 → 枠線 →
        3行 → ボタン）"""
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        return [
            (
                "draw_rect",
                btn_x,
                btn_y,
                btn_w,
                btn_h,
                GameCore.SETTLEMENT_POPUP_BTN_COL,
            ),
        ] + self._expected_icon_button_calls(
            btn_x, btn_y, btn_w, btn_h, *GameCore.ICON_OK
        )

    def _expected_game_end_popup_calls(self):
        """終了（クリア／ゲームオーバー）ポップアップの背景・枠線
        （draw_rect・draw_rectb）の呼び出し期待値を定数から計算する
        （ID-017 サイクル3）。決算ポップアップの
        _expected_settlement_popup_calls() と同じ形（背景・枠線のみを
        返し、文言・ボタンは別のヘルパーが持つ）。呼び出し側は本メソッドの
        戻り値の後ろへ _expected_game_end_popup_message_call() /
        _expected_game_end_popup_button_calls() を連結する形で使う"""
        return [
            (
                "draw_rect",
                GameCore.GAME_END_POPUP_X,
                GameCore.GAME_END_POPUP_Y,
                GameCore.GAME_END_POPUP_W,
                GameCore.GAME_END_POPUP_H,
                GameCore.GAME_END_POPUP_BG_COL,
            ),
            (
                "draw_rectb",
                GameCore.GAME_END_POPUP_X,
                GameCore.GAME_END_POPUP_Y,
                GameCore.GAME_END_POPUP_W,
                GameCore.GAME_END_POPUP_H,
                GameCore.GAME_END_POPUP_BORDER_COL,
            ),
        ]

    def _expected_game_end_popup_message_call(self, message):
        """終了ポップアップ内の文言（1行）の draw_text 呼び出し期待値を返す。
        message は GameCore.GAME_END_MESSAGE_CLEAR /
        GAME_END_MESSAGE_GAME_OVER のいずれかを呼び出し側が渡す（クリア・
        ゲームオーバーで文言だけが切り替わることを、この引数の違いだけで
        確認できるようにする）"""
        return (
            "draw_text",
            GameCore.GAME_END_POPUP_X + GameCore.GAME_END_POPUP_PAD,
            GameCore.GAME_END_POPUP_Y + GameCore.GAME_END_POPUP_PAD,
            message,
        )

    def _expected_game_end_popup_button_rect(self):
        """終了ポップアップ内の「o」ボタンの矩形 (x, y, w, h) を、実装の
        _game_end_popup_button_rect() と同じ式（文言1行の直後に内側余白
        GAME_END_POPUP_PAD を挟んで置く）を、実装から独立した式として持つ
        （_expected_settlement_popup_button_rect() と同じく、期待値を
        実装インスタンスから生成しないための鏡）"""
        btn_x = GameCore.GAME_END_POPUP_X + GameCore.GAME_END_POPUP_PAD
        btn_y = (
            GameCore.GAME_END_POPUP_Y
            + GameCore.GAME_END_POPUP_PAD
            + GameCore.GAME_END_POPUP_LINE_H
            + GameCore.GAME_END_POPUP_PAD
        )
        return (
            btn_x,
            btn_y,
            GameCore.GAME_END_POPUP_BTN_W,
            GameCore.GAME_END_POPUP_BTN_H,
        )

    def _expected_game_end_popup_button_calls(self):
        """終了ポップアップ内の「o」ボタンの矩形・アイコン（draw_image）呼び出し
        期待値を定数から計算する（ID-026 サイクル026-3で文字から ICON_OK
        アイコンへ置き換えた）。決算ポップアップの
        _expected_settlement_popup_button_calls() と同じく無効表示を持たない
        （終了ポップアップのボタンは押下を受け付けない見た目だけの存在だが、
        押せなさそうな見た目にする理由も要件も無いため、常に塗りつぶしで
        描く）。アイコンは矩形の中央へ置く（_expected_icon_button_calls()）。
        呼び出し側は _expected_game_end_popup_calls() +
        _expected_game_end_popup_message_call() の後ろへ本メソッドの戻り値を
        連結する形で使う（終了ポップアップの描画順は背景 → 枠線 → 文言 →
        ボタン）"""
        btn_x, btn_y, btn_w, btn_h = self._expected_game_end_popup_button_rect()
        return [
            (
                "draw_rect",
                btn_x,
                btn_y,
                btn_w,
                btn_h,
                GameCore.GAME_END_POPUP_BTN_COL,
            ),
        ] + self._expected_icon_button_calls(
            btn_x, btn_y, btn_w, btn_h, *GameCore.ICON_OK
        )

    def _core_with_one_vacant_plot(self, col, row):
        """(col, row) の1区画だけを空きのまま残し、残り269区画をプレイヤー
        所有店舗（Field.set_shop() 経由）で埋めた GameCore を返す。
        最後の1区画へ建設・買収しても（全区画がプレイヤー所有になっても）
        クリアが成立しないことを確かめるための共通の盤面組み立て
        （ID-017 サイクル4で全区画を埋める盤面が必要になった際に導入し、
        ID-028 で「建設・買収だけではクリアが成立しない」ことの確認用へ
        用途を改めた。test_main_popup.py の TestGameEndPopup から移した
        経緯は変わらない）"""
        core = GameCore()
        for row_ in range(GameCore.GRID_ROWS):
            for col_ in range(GameCore.GRID_COLS):
                if (col_, row_) == (col, row):
                    continue
                core._field.set_shop(col_, row_, Owner.PLAYER)  # pylint: disable=W0212
        return core

    def _player_shop_positions(self, count):
        """行昇順→列昇順で先頭から count 個ぶんの座標を返す
        （Field.iter_shop_pos() / Field._list_sell_targets() と同じ順序）。
        規定店舗数（Field.CLEAR_SHOP_COUNT）のような軒数の境界を盤面上に
        作るときの共通の座標源（test_field.py の
        TestFieldClearShopCount._player_shop_positions() と同じ考え方だが、
        test_main_*.py 側の複数ファイルからも使うため TestParent へ置く。
        ID-028 サイクル028-2）"""
        return [
            (col, row)
            for row in range(GameCore.GRID_ROWS)
            for col in range(GameCore.GRID_COLS)
        ][:count]

    def _core_with_player_shops(self, count):
        """_player_shop_positions(count) の座標を Field.set_shop() 経由で
        プレイヤー所有店舗にした GameCore を返す。_core_with_one_vacant_plot()
        が「270区画から1区画だけ欠けた盤面」を作るのに対し、本ヘルパーは
        「先頭から任意の軒数だけ埋めた盤面」を作る——規定店舗数の境界
        （1つ手前・ちょうど・超過）を盤面で表すのに使う（ID-028
        サイクル028-2）"""
        core = GameCore()
        for col, row in self._player_shop_positions(count):
            core._field.set_shop(col, row, Owner.PLAYER)  # pylint: disable=W0212
        return core

    def _core_with_settlement_popup_shown(self):
        """決算ポップアップが表示された（SettlementPopupState.SHOWN）状態の
        GameCore を返す（ID-015 サイクル1）。決算タイマーの満了が
        self._settlement_popup_state を SHOWN へ進めることは test_main_clock.py
        の TestSettlementInterval が固定済みのため、ここでは実際のタイマー
        経過を再現せず状態を直接立てる（_build_player_shop()
        （test_main_draw.py の TestDrawSettlementStatus）が実際の建設操作を
        経由せず Field への直接操作で盤面を作るのと同じ考え方: 対象外の経路を
        再現するとテストの関心がぼやける）。
        決算ポップアップに関するテストは test_main_popup.py（表示の振る舞い・
        3行の内容・クリック精算）と test_main_clock.py（抑止・凍結）の両方に
        またがる見込みのため、ファイルをまたいで使えるよう TestParent に置く
        （ID-015 サイクル2 Refactor で test_main_popup.py 内から移した）"""
        core = GameCore()
        core._settlement_popup_state = (  # pylint: disable=W0212
            SettlementPopupState.SHOWN
        )
        return core

    def _expected_field_calls(
        self,
        shops=(),
        money=None,
        shop_count=None,
        scale=Shop.INITIAL_SCALE,
        sales_plot=None,
        remaining_sec=None,
        tax=None,
    ):
        """ポップアップを除いた既存の描画（ステータス → 道路 → 店舗 →
        売上の囲み）の期待値。ポップアップの有無を検証するテストは、この列に
        ポップアップの期待値を足すか足さないかだけで期待値を組み立てる。
        money を省略すると初期資金（GameCore.INITIAL_MONEY）を使う（資金が
        変わる操作を検証するテストだけが明示的に渡す）。scale は盤面の店舗の
        規模で、_expected_shop_calls() へそのまま渡す（設置直後以外の規模の
        店舗を盤面に置くテストだけが明示的に渡す。全店舗が同じ規模であることを
        前提とする点も同メソッドと同じ）。
        shop_count・remaining_sec・tax は _expected_status_calls() へそのまま
        渡す（省略時の既定値もそちらに委ねる。ID-014 サイクル3・ID-028
        サイクル028-4）。
        sales_plot は売上の抽選が起きた区画で、省略（None）すると囲みは列に
        現れない（まだ1度も抽選が起きていない状態）。**売上が満了する経過を
        含むテストだけが明示的に渡す**。囲みは店舗の後・選択枠の前に来るため、
        この列の末尾へ足すことで「_expected_field_calls() の後ろに選択枠・
        ポップアップを繋ぐ」という既存の組み立て方がそのまま保たれる"""
        return (
            self._expected_status_calls(
                money=money,
                shop_count=shop_count,
                remaining_sec=remaining_sec,
                tax=tax,
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(shops, scale=scale)
            + self._expected_sales_frame_calls(sales_plot)
        )
