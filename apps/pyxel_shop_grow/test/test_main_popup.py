"""ポップアップの表示・状態遷移・選択枠

押下によるポップアップの開閉・プレビュー内容・数値・ボタンの状態・モーダル
遷移を検証する。同じ「o押下」を起点にしても、盤面・資金の変化を検証する
ものは shop_action 側に分類される（分類ルール1）。

分類ルール（test/test_main.py の分割時に定めた3条）:
1. 同じ「o押下」が起点でも、検証対象がポップアップの開閉なら popup、
   盤面・資金の変化なら shop_action
2. 保存のテストは「いつ保存するか」と「何が保存されるか」で分ける。
   前者（仕組み）は save、後者のうちタイマー固有の状態遷移を伴うものは clock
3. 描画のテストは、発生契機が時間経過なら clock
   （draw は操作・状態から直接決まる描画のみ）

TestSelectionFrame がこのファイルにある理由: 選択枠は
_is_selection_shown() をポップアップと共有し、「片方だけ描かれる状態を
作れない」ことが設計の要。draw 側へ切り離すと対の関係が2ファイルに
割れるため、popup へ含める。

TestSettlementPopupDisplay がこのファイルにある理由: 決算ポップアップが
現れる契機は時間経過（分類ルール3）で、その契機自体（決算タイマーの満了が
決算ポップアップの表示に結びつくこと）は test_main_clock.py の
TestSettlementInterval が検証する。一方、本クラスが検証するのは決算
ポップアップ**自体**の描画の振る舞い（表示の継続・他のポップアップとの
重なりの上下関係）であり、検証対象がポップアップの描画そのものであるため
popup へ含める（TestSalesFrame と同じ境界の考え方。ID-015 サイクル1
TASK-015-4）。

TestSettlementPopupSettlement がこのファイルにある理由: 決算ポップアップ内
「o」ボタンの押下による精算・非表示（クリックによる開閉）は、TestSettlementPopupValues
（3行の内容）と同じく検証対象がポップアップの内容・開閉であるため popup へ
含める（テスト置き場の確定どおり。ID-015 サイクル5）。凍結の解除・保存の
再開・周期的な再出現は精算という1回の押下操作の結果として確認するもので、
凍結の仕組みそのもの（サイクル4。test_main_clock.py の
TestSettlementPopupFreezesTime）を再検証するものではない。

盤面の店舗を置く区画について（ID-020 案8-A）: 本ファイルのテストが盤面へ
置く店舗は、地域価格倍率（要件 3.10）が等倍（1.0）になる列0・列17へ寄せて
ある。GameCore は費用・資産価値・売上額・税額のいずれも Field から受け取って
そのまま描く relay であり、倍率が金額へ効くことそのものの検証は test_field.py
の TestFieldArea* が担うため、本ファイルは倍率の乗らない区画で「操作・時間
経過の結果、盤面と資金がどう変わるか」に集中する（test_field.py がステップ
020-2 で採った方針の踏襲）。押下位置そのものが検証の対象で区画を選び直せない
テストだけは、TestParent._expected_area_rate() で区画の倍率を求めて期待値へ
織り込む。
"""

import os
import sys
import time
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import (  # pylint: disable=C0413
    GameCore,
    GameEndState,
    PopupState,
    SettlementPopupState,
)
from field import Field, Owner, Shop  # pylint: disable=C0413,E0401
from test_main_tools import TestParent  # pylint: disable=C0413,E0401


class TestPopupOnPress(TestParent):
    """押下中のポップアップ表示（押下位置の区画の特定と追従）の振る舞いテスト

    この時点のポップアップは背景の矩形しか描かないため、描画内容から
    「どの区画が選ばれたか」は区別できない。したがってここでは
    「押下位置が区画内か区画外かでポップアップの有無が変わる」ところまでを検証し、
    押下位置に対する**内容**の追従（選んだ区画の店舗がプレビューに現れること）と、
    区画と区画の境（フィールド内部の 1px 隣）の判定は、プレビューを描く
    次のサイクルの Red で検証を完成させる"""

    # ポップアップの前面性（店舗の後に描かれること）を確認するための店舗の位置
    SHOP_COL = 0
    SHOP_ROW = 2

    def _make_core_with_shop(self):
        """前面性の確認用に店舗を 1 件だけ設置した GameCore を作る"""
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.SHOP_COL, self.SHOP_ROW, Owner.NPC
        )
        return core

    def test_popup_not_drawn_while_not_pressed(self):
        """押下していないとき、ポップアップが描画されないこと
        （ステータス → 道路 → 店舗という既存の呼び出し列のままであること）"""
        core = self._make_core_with_shop()
        self._update_and_draw(core, None)
        expected = self._expected_field_calls(
            [(self.SHOP_COL, self.SHOP_ROW, Owner.NPC)]
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_drawn_in_front_of_shops_while_pressed(self):
        """押下中、押下位置の区画のポップアップ（この時点では背景の矩形のみ）が
        店舗の**後**（最前面）に描画されること。押下位置には店舗を設置し、
        店舗の描画呼び出しの後にポップアップの呼び出しが並ぶことを順序込みで確認する"""
        core = self._make_core_with_shop()
        pos = self._plot_center_pos(self.SHOP_COL, self.SHOP_ROW)
        self._update_and_draw(core, pos)
        expected = self._expected_field_calls(
            [(self.SHOP_COL, self.SHOP_ROW, Owner.NPC)]
        ) + self._expected_selection_and_popup_calls(pos, owner=Owner.NPC)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_follows_press_position(self):
        """押下を保持したまま押下位置を別の区画へ動かしても、その位置の区画の
        ポップアップが描画され続けること（区画をまたぐ移動でポップアップが
        消えないこと）。左上・中央・右下端の区画を順に押していく。
        この時点では背景しか描かないため「描画され続ける」ことまでしか確認できず、
        内容が押下位置の区画へ追従することは次のサイクルで検証する。
        中央の区画は地域価格倍率が最大（AREA_RATE_CENTER）で建設費用が
        BUILD_COST の3倍（300）になり、初期資金（GameCore.INITIAL_MONEY
        = 200。ID-028 のプレイテストで中心を即座に確保できないよう
        引き下げた）では賄えないため、「o」ボタンは無効表示になる
        （o_enabled=False）。左上・右下端はどちらも盤面の端（距離が
        AREA_MAX_DISTANCE で等倍＝倍率1000）で費用は100と初期資金の
        範囲内のため、既定（有効）のままでよい"""
        core = GameCore()
        test_cases = [
            ("左上の区画", 0, 0, True),
            ("中央付近の区画", GameCore.GRID_COLS // 2, GameCore.GRID_ROWS // 2, False),
            ("右下端の区画", GameCore.GRID_COLS - 1, GameCore.GRID_ROWS - 1, True),
        ]
        for case_name, col, row, o_enabled in test_cases:
            with self.subTest(case_name=case_name):
                pos = self._plot_center_pos(col, row)
                self._update_and_draw(core, pos)
                expected = self._expected_field_calls(
                    []
                ) + self._expected_selection_and_popup_calls(pos, o_enabled=o_enabled)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_popup_not_drawn_when_press_is_outside_plots(self):
        """押下位置が区画外（ステータス領域・左右の余白・最下段の閉じの道路）の
        ときはポップアップが描画されないこと。左右の余白は最寄り列へ吸着しない
        （押していない区画が選ばれない）ことの確認でもある"""
        core = GameCore()
        field_right = GameCore.GRID_LEFT + GameCore.GRID_COLS * GameCore.PLOT_SIZE
        field_bottom = GameCore.FIELD_ORIGIN_Y + GameCore.GRID_ROWS * GameCore.PITCH
        test_cases = [
            ("ステータス領域", (GameCore.GRID_LEFT, GameCore.FIELD_ORIGIN_Y - 1)),
            ("左の余白", (GameCore.GRID_LEFT - 1, GameCore.FIELD_ORIGIN_Y)),
            ("右の余白", (field_right, GameCore.FIELD_ORIGIN_Y)),
            ("最下段の閉じの道路", (GameCore.GRID_LEFT, field_bottom)),
        ]
        for case_name, pos in test_cases:
            with self.subTest(case_name=case_name):
                self._update_and_draw(core, pos)
                expected = self._expected_field_calls([])
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_plot_hit_area_is_half_open_interval(self):
        """区画の判定範囲が半開区間 [開始, 開始 + サイズ) であること。
        フィールド全体（左上の区画の左上端 〜 右下の区画の右下端）の外周 11 点
        （内側の四隅 4 点 + その 1px 外側 7 点）で、内側ではポップアップが出て
        外側では出ないことを確認する。座標はすべて定数から計算し、
        右端・下端が「境界の外側」であることを式で明示する"""
        left = GameCore.GRID_LEFT
        top = GameCore.FIELD_ORIGIN_Y
        right = left + GameCore.GRID_COLS * GameCore.PLOT_SIZE  # 右端（境界外）
        bottom = top + GameCore.GRID_ROWS * GameCore.PITCH  # 下端（境界外）
        test_cases = [
            # 判定範囲の内側（四隅）
            ("左上", (left, top), True),
            ("右上", (right - 1, top), True),
            ("左下", (left, bottom - 1), True),
            ("右下", (right - 1, bottom - 1), True),
            # 判定範囲の 1px 外側
            ("左上の左外", (left - 1, top), False),
            ("左上の上外", (left, top - 1), False),
            ("右上の右外", (right, top), False),
            ("右下の右外", (right, bottom - 1), False),
            ("左下の左外", (left - 1, bottom - 1), False),
            ("左下の下外", (left, bottom), False),
            ("右下の下外", (right, bottom), False),
        ]
        core = GameCore()
        for case_name, pos, is_inside in test_cases:
            with self.subTest(case_name=case_name, pos=pos):
                self._update_and_draw(core, pos)
                expected = self._expected_field_calls([])
                if is_inside:
                    expected = expected + self._expected_selection_and_popup_calls(pos)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestPopupPreview(TestParent):
    """ポップアップ内のプレビュー領域（選択位置の店舗画像とその下の道路）の
    振る舞いテスト。道路は区画の状態によらず常に同じ位置へ描画され、
    店舗画像は選択中の区画に店舗があるときだけ道路の後に上乗せで描かれる"""

    PLOT_COL = 0
    PLOT_ROW = 2

    def test_preview_draws_road_and_shop_by_plot_state(self):
        """区画の状態（空き／プレイヤー所有／NPC所有）に応じてプレビューが
        変わること。道路は3ケースとも同じ位置に同じ2枚が描かれ（区画の状態に
        よらず常に同一）、店舗画像は店舗がある場合のみ道路の後に描かれ、
        所有者に応じて転送元 v が切り替わることを1つの検証ロジックで確認する"""
        test_cases = [
            ("空き区画", None),
            ("プレイヤー所有店舗", Owner.PLAYER),
            ("NPC所有店舗", Owner.NPC),
        ]
        for case_name, owner in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                if owner is not None:
                    core._field.set_shop(  # pylint: disable=W0212
                        self.PLOT_COL, self.PLOT_ROW, owner
                    )
                pos = self._plot_center_pos(self.PLOT_COL, self.PLOT_ROW)
                self._update_and_draw(core, pos)
                shops = (
                    [(self.PLOT_COL, self.PLOT_ROW, owner)] if owner is not None else []
                )
                # set_shop() 直後の資産価値は Shop.BUILD_COST。プレイヤー所有の
                # ときだけ税額の表示へ反映される（ID-014 サイクル3）
                player_values = [Shop.BUILD_COST] if owner == Owner.PLAYER else []
                expected = (
                    self._expected_status_calls(
                        shop_count=len(player_values),
                        tax=self._expected_tax(player_values),
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls(shops)
                    + self._expected_selection_and_popup_calls(pos, owner=owner)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_preview_shop_image_matches_scale(self):
        """店舗規模 1〜10 のそれぞれで、プレビューの店舗画像の転送元 x が
        SHOP_U_ORIGIN + SHOP_U_STEP * (規模 - 1) になること（フィールド上の
        店舗画像と同じ計算式で、プレビュー側でも規模ごとに絵柄が変わることを
        確認する）。
        規模は保存データからの復元（load() の戻り値）で与え、Shop の内部状態
        （_scale）を直接書き換えない（ID-020。倍率版の費用・売上額は都度
        導出せず生成・復元・増資の各時点で書き直す持ち回り値になったため、
        _scale だけを差し替えると規模1のときの費用・売上額が残る。復元は
        任意の規模の店舗を作れる正規の経路であり、test_field.py が
        apply_load_data() で同じことをしているのと同じ形）"""
        col, row = self.PLOT_COL, self.PLOT_ROW
        for scale in range(GameCore.SHOP_SCALE_MIN, GameCore.SHOP_SCALE_MAX + 1):
            with self.subTest(scale=scale):
                self.mock_store.load.return_value = {
                    "shops": [[col, row, Owner.NPC.value, scale, Shop.BUILD_COST]],
                    "money": GameCore.INITIAL_MONEY,
                    "settlement_remaining_ms": None,
                    "speed_index": 0,
                }
                core = GameCore()
                pos = self._plot_center_pos(col, row)
                self._update_and_draw(core, pos)
                expected = (
                    self._expected_status_calls()
                    + self._expected_road_calls()
                    + self._expected_shop_calls(
                        [(self.PLOT_COL, self.PLOT_ROW, Owner.NPC)], scale=scale
                    )
                    + self._expected_selection_and_popup_calls(
                        pos, owner=Owner.NPC, scale=scale
                    )
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_preview_follows_press_position_content(self):
        """押下位置を空き区画から店舗のある区画へ動かすと、プレビューの内容が
        追従して変わること（サイクル1で背景しか描けず保留していた、内容面の
        追従の検証をここで完成させる）"""
        empty_col, empty_row = 0, 0
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.PLOT_COL, self.PLOT_ROW, Owner.PLAYER
        )

        # set_shop() 直後の資産価値 Shop.BUILD_COST が税額の表示へ反映される
        # （ID-014 サイクル3。押下位置が変わっても盤面は変わらないため、
        # 2回の draw() を通じて同じ値のまま）
        tax = self._expected_tax([Shop.BUILD_COST])

        # 空き区画を押す
        empty_pos = self._plot_center_pos(empty_col, empty_row)
        self._update_and_draw(core, empty_pos)
        expected_empty = (
            self._expected_status_calls(shop_count=1, tax=tax)
            + self._expected_road_calls()
            + self._expected_shop_calls([(self.PLOT_COL, self.PLOT_ROW, Owner.PLAYER)])
            + self._expected_selection_and_popup_calls(empty_pos)
        )
        self.assertEqual(
            expected_empty,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

        # 店舗のある区画へ移動して押す
        shop_pos = self._plot_center_pos(self.PLOT_COL, self.PLOT_ROW)
        self._update_and_draw(core, shop_pos)
        expected_shop = (
            self._expected_status_calls(shop_count=1, tax=tax)
            + self._expected_road_calls()
            + self._expected_shop_calls([(self.PLOT_COL, self.PLOT_ROW, Owner.PLAYER)])
            + self._expected_selection_and_popup_calls(shop_pos, owner=Owner.PLAYER)
        )
        self.assertEqual(
            expected_shop,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_preview_distinguishes_plots_across_internal_boundary(self):
        """区画と区画の内部境界（フィールド内部の半開区間）でプレビューの内容が
        正しく切り替わること。列境界・行境界それぞれで、境界の内側1pxは店舗の
        ある区画、境界の外側1pxは隣の空き区画の内容になることを確認する
        （サイクル1では背景しか描けず区別できなかった、区画ごとの境界検証を
        ここで完成させる）"""
        col, row = self.PLOT_COL, self.PLOT_ROW
        core = GameCore()
        core._field.set_shop(col, row, Owner.PLAYER)  # pylint: disable=W0212
        # 右隣・下隣の区画は空きのまま

        col_x, col_y = self._plot_center_pos(col, row)
        col_boundary = GameCore.GRID_LEFT + (col + 1) * GameCore.PLOT_SIZE
        row_boundary = GameCore.FIELD_ORIGIN_Y + (row + 1) * GameCore.PITCH

        test_cases = [
            (
                "列境界の内側1px(店舗のある区画)",
                (col_boundary - 1, col_y),
                Owner.PLAYER,
            ),
            ("列境界の外側1px(右隣の空き区画)", (col_boundary, col_y), None),
            (
                "行境界の内側1px(店舗のある区画)",
                (col_x, row_boundary - 1),
                Owner.PLAYER,
            ),
            ("行境界の外側1px(下隣の空き区画)", (col_x, row_boundary), None),
        ]
        for case_name, pos, expected_owner in test_cases:
            with self.subTest(case_name=case_name):
                self._update_and_draw(core, pos)
                expected = (
                    self._expected_status_calls(
                        shop_count=1, tax=self._expected_tax([Shop.BUILD_COST])
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls([(col, row, Owner.PLAYER)])
                    + self._expected_selection_and_popup_calls(
                        pos, owner=expected_owner
                    )
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestPopupValues(TestParent):
    """ポップアップ内の数値3項目（費用・資産価値・売上額）の振る舞いテスト。
    GameCore はこの3つの値を Field からそのまま受け取って描画するだけの
    relay に徹する（区画の状態による値の切り替えという業務ロジックの検証は
    test_field.py 側の TestFieldCostAndSales で行い、ここでは重複させない）。
    「Field/Shop が返す値が、正しい順序・間隔・ラベルなしの数字でそのまま
    描画される」という GameCore 側の振る舞いだけを、任意の値で確認する"""

    PLOT_COL = 0
    PLOT_ROW = 2

    def test_values_draw_from_field_for_empty_plot(self):
        """空き区画では Field.get_cost() の戻り値（建設費用）・0（資産価値）・
        0（売上額）が、プレビューの後にラベルなしの数字のみで POPUP_LINE_H 間隔の
        3行として描画されること。建設費用は Shop.BUILD_COST を任意の値へ
        差し替えて確認する（仮値そのものではなく、Field から受け取った値が
        そのまま描画されることを検証する）。777 は初期資金（GameCore.
        INITIAL_MONEY = 200。ID-028）を上回るため、「o」ボタンは無効表示
        になる（o_enabled=False）"""
        with patch.object(Shop, "BUILD_COST", 777):
            core = GameCore()
            pos = self._plot_center_pos(self.PLOT_COL, self.PLOT_ROW)
            self._update_and_draw(core, pos)
            expected = (
                self._expected_status_calls()
                + self._expected_road_calls()
                + self._expected_selection_and_popup_calls(
                    pos, cost=777, value=0, sales=0, o_enabled=False
                )
            )
            self.assertEqual(
                expected,
                self.test_view.get_call_params(),
                self.test_view.get_call_params(),
            )

    def test_values_draw_from_shop_for_owned_plot(self):
        """店舗のある区画では、その Shop が持つ資産価値（value）と、店舗規模から
        導出される費用・売上額（cost / sales）がそのまま描画されること。
        資産価値・店舗規模はいずれも保存データからの復元（load() の戻り値）で
        与える（ID-020。倍率版の費用・売上額は都度導出せず生成・復元・増資の
        各時点で書き直す持ち回り値になったため、Shop の内部状態を直接
        書き換えると規模1のときの値が残る。復元は任意の規模・資産価値の店舗を
        作れる正規の経路であり、test_field.py が apply_load_data() で同じことを
        しているのと同じ形）。資産価値は式どおりでない任意の値（12,345）を
        与え、Field が保存された値をそのまま返すことを確認する。費用
        （cost、ID-007 以降）・売上額（sales、ID-010 以降）はいずれも所有者・
        店舗規模から導出される値のため任意の値へは書き換えられず、規模を
        任意の値（4）にして導出された値が描画されることで確認する。所有者に
        よる切り替えという業務ロジックの検証は test_field.py 側で行うため、
        ここでは所有者を1通り（PLAYER）に固定する。
        規模4の増資費用（1,200）は初期資金（GameCore.INITIAL_MONEY = 1000）を
        上回るため、「o」は資金不足で無効表示になる（ID-007 サイクル3。この
        テストの主目的は費用・資産価値・売上額の relay であり、無効表示は
        cost が導出する値に伴う副作用としてそのまま期待値へ含める）"""
        col, row = self.PLOT_COL, self.PLOT_ROW
        scale = 4
        cost = Shop.INVEST_COST * 2 ** (scale - 1)
        sales = Shop.SALES_AMOUNT * 2 ** (scale - 1)
        self.mock_store.load.return_value = {
            "shops": [[col, row, Owner.PLAYER.value, scale, 12345]],
            "money": GameCore.INITIAL_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._update_and_draw(core, pos)
        expected = (
            self._expected_status_calls(shop_count=1, tax=self._expected_tax([12345]))
            + self._expected_road_calls()
            + self._expected_shop_calls([(col, row, Owner.PLAYER)], scale=scale)
            + self._expected_selection_and_popup_calls(
                pos,
                owner=Owner.PLAYER,
                scale=scale,
                cost=cost,
                value=12345,
                sales=sales,
                o_enabled=False,
            )
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_cost_draws_as_dash_for_player_shop_at_scale_max(self):
        """店舗規模が上限（GameCore.SHOP_SCALE_MAX）のプレイヤー所有店舗を
        選ぶと、増資できず増資費用が存在しないため、費用の行が数値ではなく
        「-」の1文字で描画されること（要件 3.6・区画選択ポップアップの
        表示内容）。
        店舗規模・資産価値は保存データからの復元（load() の戻り値）で与える
        （test_values_draw_from_shop_for_owned_plot と同じ理由）。資産価値は
        式どおりでない任意の値（12,345）を与え、費用が「-」になっても資産
        価値・売上額の2行は数値のままであることを、同じ1回の全件一致で併せて
        固定する（規模上限で表示形式が変わるのは費用の行だけ）。
        費用の期待値は _expected_selection_and_popup_calls() へ cost= を渡さず
        ヘルパー（_default_shop_cost()）の導出に委ねる——実装側の値を参照せず、
        「規模上限のプレイヤー所有店舗の費用は『-』」という期待をヘルパーが
        Shop.SCALE_MAX から独立に組み立てる形にするため。
        「o」は規模上限のため無効表示になる（o_enabled=False）。「-」と「o」の
        無効表示は併存し、どちらか一方に寄せない（前者は規模上限のときだけ、
        後者は資金不足でも起きるため、併せて読むと増資できない理由が判る）"""
        col, row = self.PLOT_COL, self.PLOT_ROW
        scale = GameCore.SHOP_SCALE_MAX
        sales = Shop.SALES_AMOUNT * 2 ** (scale - 1)
        self.mock_store.load.return_value = {
            "shops": [[col, row, Owner.PLAYER.value, scale, 12345]],
            "money": GameCore.INITIAL_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._update_and_draw(core, pos)
        expected = (
            self._expected_status_calls(shop_count=1, tax=self._expected_tax([12345]))
            + self._expected_road_calls()
            + self._expected_shop_calls([(col, row, Owner.PLAYER)], scale=scale)
            + self._expected_selection_and_popup_calls(
                pos,
                owner=Owner.PLAYER,
                scale=scale,
                value=12345,
                sales=sales,
                o_enabled=False,
            )
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestPopupButtons(TestParent):
    """ポップアップ内の「o」「x」ボタン（描画のみ）の振る舞いテスト。押下判定は
    サイクル 7 で扱うため、本サイクルでは描画内容のみを検証する（GUIテスト設計
    ガイド「ボタン表示とボタン押下処理は別のサイクルに分ける」）。

    区画の状態（空き／プレイヤー所有／NPC所有）によらずボタンの描画が同じである
    ことは、専用のテストを追加せず、他サイクルの全件一致テスト
    （TestPopupPreview.test_preview_draws_road_and_shop_by_plot_state や
    TestPopupValues の各テスト）が owner=None/PLAYER/NPC のそれぞれで
    _expected_popup_calls() との全件一致を確認する際に併せて確認される
    （TestDrawShopsByOwner の「専用のテストは追加しない」という既存方針を踏襲）。
    ボタン矩形がポップアップ領域内に収まっていることも、以下のテストが実装の
    描画呼び出しを _expected_popup_button_calls() という計算式と全件一致で
    比較する時点で座標そのものが確定しているため、境界のみを別途確認する
    専用テストは追加しない"""

    PLOT_COL = 0
    PLOT_ROW = 2

    def test_buttons_draw_after_values_for_empty_plot(self):
        """空き区画で、数値3行の後に「o」「x」ボタン（矩形＋文字）がこの順で
        描画されること"""
        core = GameCore()
        pos = self._plot_center_pos(self.PLOT_COL, self.PLOT_ROW)
        self._update_and_draw(core, pos)
        expected = (
            self._expected_status_calls()
            + self._expected_road_calls()
            + self._expected_selection_and_popup_calls(pos)
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestPopupPosition(TestParent):
    """押下位置に応じたポップアップ表示位置（左下／右下）の切替の振る舞いテスト。
    対象区画の内容（owner）は空き区画の1パターンに固定し、表示位置だけを
    変数にする（サイクル2〜4で検証済みの内容面の追従とは関心事を混ぜない）。
    ポップアップ内の全要素（背景・プレビュー・数値3行・ボタン2つ）は
    _expected_popup_calls() が1つの popup_x から組み立てるため、この
    全件一致の検証で「全要素が同じだけ移動すること」も併せて確認される。
    縦位置（POPUP_Y）はどの押下位置でも定数のまま変わらないため、
    専用のテストを設けない（_expected_popup_calls() が常に GameCore.POPUP_Y
    を使う時点で、縦位置が動けば全件一致が崩れて検出できる）"""

    def _press_at(self, core, x, y=GameCore.FIELD_ORIGIN_Y):
        """画面座標 (x, y) を押した状態で update() → draw() を実行し、
        期待するポップアップ呼び出し列（popup_x はその x から導出）を返す"""
        pos = (x, y)
        self._update_and_draw(core, pos)
        return (
            self._expected_status_calls()
            + self._expected_road_calls()
            + self._expected_selection_and_popup_calls(pos)
        )

    def test_popup_shown_bottom_left_when_press_is_on_right_half(self):
        """押下位置が画面右半分（x >= SCREEN_W // 2）のとき、ポップアップが
        左下（POPUP_LEFT_X, POPUP_Y）へ表示されること。境界そのもの（半開区間の
        開始点）と、フィールド右端に近い内側の2点で確認する"""
        core = GameCore()
        boundary = GameCore.SCREEN_W // 2
        field_right = GameCore.GRID_LEFT + GameCore.GRID_COLS * GameCore.PLOT_SIZE
        test_cases = [
            ("右半分の境界そのもの", boundary),
            ("フィールド右端に近い内側", field_right - 1),
        ]
        for case_name, x in test_cases:
            with self.subTest(case_name=case_name):
                expected = self._press_at(core, x)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_popup_shown_bottom_right_when_press_is_on_left_half(self):
        """押下位置が画面左半分（x < SCREEN_W // 2）のとき、ポップアップが
        右下（SCREEN_W - POPUP_W - POPUP_MARGIN, POPUP_Y）へ表示されること。
        境界の1px内側と、フィールド左端（GRID_LEFT）の2点で確認する。
        右下表示でも画面右端から POPUP_MARGIN だけ空く（左右どちらでも縁からの
        間隔が揃う）ことは、POPUP_RIGHT_X の定義そのものが担保しており、
        _expected_popup_x() がその定義を独立に参照して比較する時点で確認される"""
        core = GameCore()
        boundary = GameCore.SCREEN_W // 2
        test_cases = [
            ("左半分の境界の1px内側", boundary - 1),
            ("フィールド左端", GameCore.GRID_LEFT),
        ]
        for case_name, x in test_cases:
            with self.subTest(case_name=case_name):
                expected = self._press_at(core, x)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_popup_position_follows_press_across_halves(self):
        """押下位置を保持したまま左半分・右半分をまたいで動かすと、ポップアップの
        表示位置がそのたびに追従して切り替わること（片方の表示位置に固定されたり
        1フレーム遅れて追従したりしないこと）"""
        core = GameCore()
        boundary = GameCore.SCREEN_W // 2
        test_cases = [
            ("左半分（フィールド左端）", GameCore.GRID_LEFT),
            ("右半分（境界そのもの）", boundary),
            ("左半分に戻る（境界の1px内側）", boundary - 1),
        ]
        for case_name, x in test_cases:
            with self.subTest(case_name=case_name):
                expected = self._press_at(core, x)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestPopupModal(TestParent):
    """押下解除によるポップアップの固定表示（モーダル）と、固定表示中に
    ポップアップの領域外の区画を押したときの切り替えの振る舞いテスト。

    固定表示中も、ポップアップの領域の外側への押下は通常の押下処理として
    受け付ける。切り替わったことは内部状態（追従へ戻ったこと）ではなく
    「**押した区画のポップアップが描かれる**」という外から見える振る舞いで
    検証する（状態のアサートはしない）。押下によって変わり得るのはポップアップの
    内容と表示位置の2つのため、その2つが押した区画へ追従することをもって
    「押下を受け付けた」とみなす。

    内容の切り替え（左右同じ半分の2区画で確認）と表示位置の切り替え（内容の
    同じ2区画で確認）をそれぞれ別のテストへ分け、片方の検証にもう片方の
    関心事が混ざらないようにしている。

    ポップアップの**領域の内側**への押下を受け付けないこと（遮断）は
    TestPopupAreaBlocksPress が、領域の外側かつ区画外への押下でポップアップが
    閉じることは TestPopupModalPressOutside が担う"""

    # 押下解除の対象にする、NPC 所有の店舗がある区画（画面左半分）
    SHOP_COL = 0
    SHOP_ROW = 2
    # 内容の固定を確認するための、店舗のない区画（画面左半分。上の店舗と
    # 「空き区画 ↔ NPC所有店舗」という状態の異なる組になる）
    EMPTY_COL = 0
    EMPTY_ROW = 0
    # 表示位置の固定を確認するための、画面右半分にある店舗のない区画
    # （EMPTY_COL の区画とは内容が同じで、表示位置だけが異なる組になる）
    RIGHT_COL = 17
    RIGHT_ROW = 0

    def _make_core_with_shop(self):
        """内容の違いを作るために店舗を 1 件だけ設置した GameCore を作る"""
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.SHOP_COL, self.SHOP_ROW, Owner.NPC
        )
        return core

    def test_popup_stays_shown_after_release_on_plot(self):
        """区画上で押下を解除しても、その区画のポップアップが表示されたまま
        残ること（解除の瞬間に消えないこと）。内容・表示位置とも解除前と同じで
        あることを、描画呼び出し列の全件一致で確認する"""
        core = self._make_core_with_shop()
        pos = self._plot_center_pos(self.SHOP_COL, self.SHOP_ROW)
        self._press(core, pos)
        self._release(core)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.SHOP_COL, self.SHOP_ROW, Owner.NPC)]
        ) + self._expected_selection_and_popup_calls(pos, owner=Owner.NPC)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_content_switches_to_pressed_plot(self):
        """押下解除後（固定表示中）に、状態の異なる区画（空き区画 → NPC所有店舗）を
        押すと、ポップアップの内容がその区画へ切り替わること。2つの区画は画面の
        同じ半分にあるため表示位置はそもそも変わらず、内容の切り替えだけが
        検証対象になる"""
        core = self._make_core_with_shop()
        empty_pos = self._plot_center_pos(self.EMPTY_COL, self.EMPTY_ROW)
        shop_pos = self._plot_center_pos(self.SHOP_COL, self.SHOP_ROW)
        # 2つの押下位置が同じ表示位置に対応することを前提として明示する
        # （定数が変わって前提が崩れたとき、検証が無意味になる前に気付けるように）
        self.assertEqual(
            self._expected_popup_x(empty_pos[0]), self._expected_popup_x(shop_pos[0])
        )
        self._press(core, empty_pos)
        self._release(core)
        # 切り替え先の押下位置がポップアップの領域の外側にあること（領域の内側は
        # 遮断されるため、この前提が崩れると切り替えの検証にならない）
        self.assertFalse(
            self._is_in_popup(self._expected_popup_x(empty_pos[0]), shop_pos)
        )
        self._press(core, shop_pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.SHOP_COL, self.SHOP_ROW, Owner.NPC)]
        ) + self._expected_selection_and_popup_calls(shop_pos, owner=Owner.NPC)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_position_switches_to_pressed_plot(self):
        """押下解除後（固定表示中）に、画面の反対の半分の区画を押すと、
        ポップアップの表示位置がその区画に応じて切り替わること。2つの押下位置は
        どちらも空き区画で内容が同じため、表示位置の切り替えだけが検証対象になる"""
        core = GameCore()
        left_pos = self._plot_center_pos(self.EMPTY_COL, self.EMPTY_ROW)
        right_pos = self._plot_center_pos(self.RIGHT_COL, self.RIGHT_ROW)
        # 2つの押下位置が異なる表示位置に対応することを前提として明示する
        self.assertNotEqual(
            self._expected_popup_x(left_pos[0]), self._expected_popup_x(right_pos[0])
        )
        self._press(core, left_pos)
        self._release(core)
        self.assertFalse(
            self._is_in_popup(self._expected_popup_x(left_pos[0]), right_pos)
        )
        self._press(core, right_pos)
        self._draw(core)
        expected = (
            self._expected_field_calls()
            + self._expected_selection_and_popup_calls(right_pos)
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_switched_popup_follows_press_and_fixes_on_release(self):
        """固定表示中の押下で切り替えた後も、押下を保持したまま動かせば
        ポップアップがその押下位置へ追従し、区画上で解除すれば新しい区画で
        固定されること（切り替え先が、初回の選択とまったく同じ追従の状態で
        あること）"""
        core = GameCore()
        first_pos = self._plot_center_pos(self.EMPTY_COL, self.EMPTY_ROW)
        switch_pos = self._plot_center_pos(self.RIGHT_COL, self.RIGHT_ROW)
        # 切り替えた後に、押下を保持したまま移動する先（同じ列の1つ下の区画）
        follow_pos = self._plot_center_pos(self.RIGHT_COL, self.RIGHT_ROW + 1)
        self._press(core, first_pos)
        self._release(core)
        self._press(core, switch_pos)
        self._press(core, follow_pos)
        self._release(core)
        self._draw(core)
        expected = (
            self._expected_field_calls()
            + self._expected_selection_and_popup_calls(follow_pos)
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_not_shown_when_released_outside_plots(self):
        """区画上で押下を始めても、区画外（ステータス領域・左右の余白・最下段の
        閉じの道路）へ移動してから押下を解除した場合はポップアップが表示されない
        こと（取り消しの逃げ道）。あわせて、その解除の後に改めて区画を押せば
        ポップアップが表示されること（取り消しであって、操作が固まって
        しまうのではないこと）を確認する"""
        plot_pos = self._plot_center_pos(self.EMPTY_COL, self.EMPTY_ROW)
        for case_name, outside_pos in self._outside_plot_positions():
            with self.subTest(case_name=case_name):
                core = GameCore()
                self._press(core, plot_pos)
                self._press(core, outside_pos)
                self._release(core)
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self._press(core, plot_pos)
                self._draw(core)
                expected = (
                    self._expected_field_calls()
                    + self._expected_selection_and_popup_calls(plot_pos)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_popup_not_shown_when_released_outside_plots_after_switching(self):
        """固定表示中に別の区画を押して切り替えた後も、区画外へ移動してから
        押下を解除した場合はポップアップが表示されないこと（切り替えの委譲先が
        初回の選択と同じ押下処理であり、取り消しの逃げ道もそのまま働くこと）。
        切り替え先は元の区画と同じ画面左半分の区画にしてあるため、ポップアップは
        右下に出たままで、区画外の3点はいずれもその領域の外側に留まる"""
        plot_pos = self._plot_center_pos(self.EMPTY_COL, self.EMPTY_ROW)
        switch_pos = self._plot_center_pos(self.EMPTY_COL + 1, self.EMPTY_ROW)
        popup_x = self._expected_popup_x(plot_pos[0])
        for case_name, outside_pos in self._outside_plot_positions():
            with self.subTest(case_name=case_name):
                # 切り替え先・区画外の押下位置がともにポップアップの領域の
                # 外側にあること（内側なら遮断され、委譲そのものが起こらない）
                self.assertFalse(self._is_in_popup(popup_x, switch_pos))
                self.assertFalse(self._is_in_popup(popup_x, outside_pos))
                core = GameCore()
                self._press(core, plot_pos)
                self._release(core)
                self._press(core, switch_pos)
                self._press(core, outside_pos)
                self._release(core)
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestPopupModalPressOutside(TestParent):
    """固定表示中に、ポップアップの領域でも区画でもない場所（ステータス領域・
    盤面の余白・最下段の閉じの道路）を押したときの振る舞いテスト。

    ポップアップの領域の外側への押下は通常の押下処理へそのまま委譲されるため、
    区画外を押せばポップアップは閉じ、その押下位置に固有の処理があればそれも
    従来どおり働く（キャンセルボタン以外でも閉じることになる。決定2）。
    「閉じたこと」は draw() の呼び出し列にポップアップの描画が一切含まれない
    ことで検証する（状態そのものはアサートしない）"""

    # 固定表示の対象にする区画（画面左半分 → ポップアップは右下に表示される
    # ため、ステータス領域・盤面左の余白・最下段の閉じの道路のいずれもが
    # ポップアップの矩形の外側になる）
    PLOT_COL = 0
    PLOT_ROW = 0

    def _make_modal_core(self):
        """対象区画を押して離し、固定表示（MODAL）のポップアップを用意する。
        戻り値は (core, ポップアップ原点x)"""
        core = GameCore()
        pos = self._plot_center_pos(self.PLOT_COL, self.PLOT_ROW)
        self._press(core, pos)
        self._release(core)
        return core, self._expected_popup_x(pos[0])

    def test_press_outside_the_popup_and_plots_closes_the_popup(self):
        """固定表示中に、ポップアップの領域でも区画でもない場所を押すと
        ポップアップが閉じること"""
        for case_name, outside_pos in self._outside_plot_positions():
            with self.subTest(case_name=case_name):
                core, popup_x = self._make_modal_core()
                # 押下位置がポップアップの領域の外側にあること（内側なら
                # 遮断され、閉じるかどうかの検証にならない）
                self.assertFalse(self._is_in_popup(popup_x, outside_pos))
                self._press(core, outside_pos)
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_press_on_the_speed_button_closes_the_popup_and_advances_the_speed(self):
        """固定表示中にステータスのスピードボタンを押すと、ポップアップが
        閉じたうえで、押下解除でスピードの段階も1段進むこと（ポップアップの
        領域外の押下がその位置に固有の処理をそのまま通すこと）。
        _update_popup() と _update_status_buttons() は同じ押下・押下解除を
        独立に見るため、2つの結果が同時に起こる"""
        core, popup_x = self._make_modal_core()
        btn_x, btn_y, btn_w, btn_h = self._expected_status_speed_button_rect()
        press_pos = (btn_x + btn_w // 2, btn_y + btn_h // 2)
        self.assertFalse(self._is_in_popup(popup_x, press_pos))
        self._press(core, press_pos)
        self._draw(core)
        # 押下の時点でポップアップは閉じている（スピードはまだ進まない）
        self.assertEqual(
            self._expected_field_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self._release(core)
        self._draw(core)
        calls = self.test_view.get_call_params()
        self.assertIn(self._expected_status_speed_button_label_call(">>"), calls, calls)


class TestPopupAreaBlocksPress(TestParent):
    """固定表示中に、ポップアップの領域の内側への押下が受け付けられないこと
    （遮断）の振る舞いテスト。

    遮断は内部状態ではなく「**元の区画のポップアップが描かれ続ける**」という
    外から見える振る舞いで検証する。覆われる区画は定数から求める（列・行を
    直書きすると、POPUP_W や GRID_LEFT の変更で意味を失ったまま通り続ける）。
    左下・右下の両方の表示位置で確認するのは、覆う区画が表示位置ごとに
    異なるため（左下は盤面の左端、右下は右端の区画を覆う）"""

    # 固定表示の対象にする区画。ポップアップは押下位置と反対の半分へ出るため
    # （_popup_origin_x()）、右半分の区画を押すと左下、左半分の区画を押すと
    # 右下にポップアップが表示される
    RIGHT_HALF_PLOT = (17, 0)
    LEFT_HALF_PLOT = (0, 0)

    def _covered_plot(self, popup_x):
        """ポップアップ（原点 x = popup_x）の矩形に中心が入る区画のうち、
        最も上・左のものを定数から求める。該当が無い場合は遮断を観測できる
        前提そのものが崩れているため、テストを失敗させる"""
        for row in range(GameCore.GRID_ROWS):
            for col in range(GameCore.GRID_COLS):
                if self._is_in_popup(popup_x, self._plot_center_pos(col, row)):
                    return col, row
        self.fail(f"ポップアップ（原点x={popup_x}）に覆われる区画が無い")
        return None

    def _make_modal_core(self, plot):
        """区画 plot を押して離し、固定表示（MODAL）のポップアップを用意する。
        戻り値は (core, 押下位置, ポップアップ原点x)"""
        core = GameCore()
        pos = self._plot_center_pos(*plot)
        self._press(core, pos)
        self._release(core)
        return core, pos, self._expected_popup_x(pos[0])

    def _block_boundary_cases(self, popup_x):
        """ポップアップ矩形の外周のうち**区画の上にある辺**（上辺と、盤面の
        側を向いた側辺）について、(ケース名, 押下位置, 遮断されるか) を返す。
        辺ごとに矩形の内側1点とその1px外側1点を採り、半開区間
        [開始, 開始 + サイズ) であることを確認する。左右どちらの側辺が盤面側かは
        表示位置で決まる（左下表示なら右辺、右下表示なら左辺）——盤面の外を
        向いた側辺の外側は区画ではないため、遮断の有無が観測できない"""
        top_x = popup_x + GameCore.POPUP_W // 2
        side_y = GameCore.POPUP_Y + GameCore.POPUP_H // 2
        if popup_x == GameCore.POPUP_LEFT_X:
            edge_in = popup_x + GameCore.POPUP_W - 1
            edge_out = popup_x + GameCore.POPUP_W
        else:
            edge_in = popup_x
            edge_out = popup_x - 1
        return [
            ("上辺の内側", (top_x, GameCore.POPUP_Y), True),
            ("上辺の1px外側", (top_x, GameCore.POPUP_Y - 1), False),
            ("盤面側の側辺の内側", (edge_in, side_y), True),
            ("盤面側の側辺の1px外側", (edge_out, side_y), False),
        ]

    def test_plot_covered_by_the_popup_is_not_selected(self):
        """固定表示中に、ポップアップに覆われている区画の中心を押しても
        選択されないこと（元の区画のポップアップが描かれ続けること）"""
        for case_name, plot in (
            ("左下表示", self.RIGHT_HALF_PLOT),
            ("右下表示", self.LEFT_HALF_PLOT),
        ):
            with self.subTest(case_name=case_name):
                core, pos, popup_x = self._make_modal_core(plot)
                covered_pos = self._plot_center_pos(*self._covered_plot(popup_x))
                self._press(core, covered_pos)
                self._draw(core)
                expected = (
                    self._expected_field_calls()
                    + self._expected_selection_and_popup_calls(pos)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_covered_plot_becomes_selectable_after_the_popup_moves(self):
        """覆われて押せなかった区画も、別の区画を選んでポップアップが反対側へ
        移った後は選択できること（「永久に押せない区画がある」のではなく、
        そのとき覆われている区画だけが押せないこと）"""
        core, _, popup_x = self._make_modal_core(self.RIGHT_HALF_PLOT)
        covered_pos = self._plot_center_pos(*self._covered_plot(popup_x))
        self._press(core, covered_pos)
        # 覆われていない区画を選び直すと、ポップアップは反対側へ移る
        move_pos = self._plot_center_pos(*self.LEFT_HALF_PLOT)
        self._press(core, move_pos)
        self._release(core)
        moved_popup_x = self._expected_popup_x(move_pos[0])
        self.assertNotEqual(popup_x, moved_popup_x)
        self.assertFalse(self._is_in_popup(moved_popup_x, covered_pos))
        self._press(core, covered_pos)
        self._draw(core)
        expected = (
            self._expected_field_calls()
            + self._expected_selection_and_popup_calls(covered_pos)
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_popup_block_area_is_half_open_interval(self):
        """ポップアップの遮断範囲が半開区間 [開始, 開始 + サイズ) であること。
        表示位置（左下・右下）ごとに、区画の上にある外周の辺（上辺・盤面側の
        側辺）について矩形の内側1点は遮断され、その1px外側1点は通常の押下
        処理として受け付けられる（押した区画へ切り替わる）ことを確認する"""
        for pos_name, plot in (
            ("左下表示", self.RIGHT_HALF_PLOT),
            ("右下表示", self.LEFT_HALF_PLOT),
        ):
            popup_x = self._expected_popup_x(self._plot_center_pos(*plot)[0])
            for case_name, press_pos, is_blocked in self._block_boundary_cases(popup_x):
                with self.subTest(disp=pos_name, case_name=case_name):
                    # 外周の点が区画の上にあること（区画外だと、遮断されても
                    # 委譲されてもポップアップが消えるだけで区別できない）
                    self.assertIsNotNone(self._expected_plot(press_pos))
                    core, pos, _ = self._make_modal_core(plot)
                    self._press(core, press_pos)
                    self._draw(core)
                    shown_pos = pos if is_blocked else press_pos
                    expected = (
                        self._expected_field_calls()
                        + self._expected_selection_and_popup_calls(shown_pos)
                    )
                    self.assertEqual(
                        expected,
                        self.test_view.get_call_params(),
                        self.test_view.get_call_params(),
                    )


class TestPopupButtonPress(TestParent):
    """MODAL 状態での「o」「x」ボタン押下によるポップアップの終了
    （TDD サイクル7）の振る舞いテスト。

    「消えたこと」は draw() の呼び出し列にポップアップの描画（背景・枠線・
    プレビュー・数値・ボタン）が一切含まれないことで検証する（第2部と同じく
    状態そのものはアサートしない）。「o」と「x」は本サイクルの時点では同じ
    結果（閉じる）になっていたが、ID-006 以降で「o」だけが実行に結び付き、
    ID-022 で「o」は実行後も閉じずに残る形へ変わった（TestPopupStaysOpen
    AfterExecution）ため、現在は「x」（常にキャンセルで閉じる）だけを本クラスが
    担う。「o」の判定範囲そのもの（test_button_hit_area_is_half_open_interval）
    は引き続き本クラスに残し、範囲内を押した場合の期待値だけを「閉じない」
    形へ更新している"""

    # 押下解除の対象にする区画（画面右半分 → ポップアップは左下に表示される）
    LEFT_POPUP_COL = 17
    LEFT_POPUP_ROW = 0
    # 押下解除の対象にする区画（画面左半分 → ポップアップは右下に表示される）
    RIGHT_POPUP_COL = 0
    RIGHT_POPUP_ROW = 0

    def _make_modal_core(self, col, row, owner=None):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        戻り値は (core, 押下位置) で、押下位置はそのまま
        _expected_selection_and_popup_calls() へ渡せる（ポップアップ原点x が
        必要な場合は _expected_popup_x() で導く）。
        owner を渡すとその区画へ店舗を設置してから選択する。「o」が空き区画で
        建設に結び付くようになった（ID-006）ため、**ポップアップの開閉そのもの**を
        検証するテストは実行を伴わない「店舗のある区画」を対象にして、開閉と
        建設の関心事を混ぜない（建設を伴う「o」でもポップアップが閉じることは
        TestBuildShop が全件一致で担保している）"""
        core = GameCore()
        if owner is not None:
            core._field.set_shop(col, row, owner)  # pylint: disable=W0212
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def test_x_button_press_closes_popup(self):
        """MODAL 状態で「x」の領域を押下するとポップアップが消えること"""
        core, pos = self._make_modal_core(self.LEFT_POPUP_COL, self.LEFT_POPUP_ROW)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, 1)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_press_inside_the_popup_outside_the_buttons_is_not_accepted(self):
        """MODAL 状態でポップアップの領域のうちボタン以外（プレビュー領域の
        余白）を押下しても何も起きないこと（ポップアップが消えず、内容も
        表示位置も変わらない）。ポップアップの領域の**外側**への押下は通常の
        押下処理へ委譲されるため、別区画への切り替えは TestPopupModal が、
        区画外での閉じるは TestPopupModalPressOutside が担う"""
        core, pos = self._make_modal_core(self.LEFT_POPUP_COL, self.LEFT_POPUP_ROW)
        popup_x = self._expected_popup_x(pos[0])
        press_pos = (
            popup_x + GameCore.POPUP_PAD,
            GameCore.POPUP_Y + GameCore.POPUP_PAD,
        )
        self.assertTrue(self._is_in_popup(popup_x, press_pos))
        self._press(core, press_pos)
        self._draw(core)
        expected = (
            self._expected_field_calls() + self._expected_selection_and_popup_calls(pos)
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_button_hit_area_is_half_open_interval(self):
        """ボタンの矩形判定が半開区間 [開始, 開始 + サイズ) であること。
        表示位置（左下・右下）× ボタン（o・x）の組み合わせごとに、矩形の外周
        11 点（内側の四隅 4 点 + その 1px 外側 7 点）で押下判定を確認する。
        MODAL は一度閉じると同じ core では元に戻せないため、点ごとに新しい
        GameCore を用意する。対象区画には店舗を置き、「o」が実行（建設）を
        伴わない状態にする（判定範囲の内外という関心事だけを見る）"""
        positions = (
            ("左下表示", self.LEFT_POPUP_COL, self.LEFT_POPUP_ROW),
            ("右下表示", self.RIGHT_POPUP_COL, self.RIGHT_POPUP_ROW),
        )
        buttons = (("o", 0), ("x", 1))
        for pos_name, col, row in positions:
            popup_x = self._expected_popup_x(self._plot_center_pos(col, row)[0])
            for btn_name, index in buttons:
                self._assert_button_boundary(
                    (pos_name, col, row), (btn_name, index), popup_x
                )

    def _button_boundary_cases(self, popup_x, index):
        """index 番目のボタン矩形の外周11点（内側の四隅4点＋その1px外側7点）を
        (ケース名, 押下位置, 判定範囲内か) のリストとして返す。矩形は
        _expected_button_rect() から導く"""
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
        right = btn_x + btn_w  # 右端（境界外）
        bottom = btn_y + btn_h  # 下端（境界外）
        return [
            # 判定範囲の内側（四隅）
            ("左上", (btn_x, btn_y), True),
            ("右上", (right - 1, btn_y), True),
            ("左下", (btn_x, bottom - 1), True),
            ("右下", (right - 1, bottom - 1), True),
            # 判定範囲の 1px 外側
            ("左上の左外", (btn_x - 1, btn_y), False),
            ("左上の上外", (btn_x, btn_y - 1), False),
            ("右上の右外", (right, btn_y), False),
            ("右下の右外", (right, bottom - 1), False),
            ("左下の左外", (btn_x - 1, bottom - 1), False),
            ("左下の下外", (btn_x, bottom), False),
            ("右下の下外", (right, bottom), False),
        ]

    def _expected_boundary_result(self, plot, pos, index, is_inside):
        """_assert_button_boundary() の1点ぶんの期待値を組み立てる。plot は
        対象区画 (col, row)。対象は常にNPC所有店舗のため、「o」の判定範囲内
        （is_inside）を押した場合だけ買収 ID-009 が実行され所有者・資金が
        変わる（「x」は範囲内でもキャンセルのため変わらない）。「o」の判定
        範囲内を押した場合は、買収を実行したうえでポップアップが残る
        （ID-022 決定1。買収費用ちょうど＝Shop.BUILD_COST × Shop.BUYOUT_RATE
        で資金が尽きるため、増資費用を賄えず「o」は無効表示になる）。
        ローカル変数を増やさないよう _assert_button_boundary() から
        括り出している"""
        col, row = plot
        if is_inside and index == GameCore.POPUP_BTN_INDEX_O:
            cost = Shop.BUILD_COST * Shop.BUYOUT_RATE
            return self._expected_field_calls(
                [(col, row, Owner.PLAYER)],
                money=GameCore.INITIAL_MONEY - cost,
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ) + self._expected_selection_and_popup_calls(
                pos, owner=Owner.PLAYER, value=Shop.BUILD_COST, o_enabled=False
            )
        expected = self._expected_field_calls([(col, row, Owner.NPC)])
        if not is_inside:
            expected = expected + self._expected_selection_and_popup_calls(
                pos, owner=Owner.NPC
            )
        return expected

    def _assert_button_boundary(self, position, button, popup_x):
        """1つの表示位置×ボタンの組み合わせについて、_button_boundary_cases() の
        11点で押下判定を確認する。position は (表示位置名, col, row)、
        button は (ボタン名, index)。test_button_hit_area_is_half_open_interval()
        から組み合わせごとに呼ばれる（メソッド分割はローカル変数を増やしすぎない
        ための整理であり、検証内容そのものは1つの境界値テストのまま）"""
        pos_name, col, row = position
        btn_name, index = button
        for case_name, press_pos, is_inside in self._button_boundary_cases(
            popup_x, index
        ):
            with self.subTest(disp=pos_name, button=btn_name, case_name=case_name):
                core, pos = self._make_modal_core(col, row, owner=Owner.NPC)
                self._press(core, press_pos)
                self._draw(core)
                expected = self._expected_boundary_result(
                    (col, row), pos, index, is_inside
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestPopupStaysOpenAfterExecution(TestParent):
    """「o」ボタン押下による実行（建設・増資・買収）の後もポップアップが
    閉じずに残り、続けて同じ区画へ実行できることの振る舞いテスト
    （TDD サイクル 022-1。ID-022_subtasks.md 決定1・決定2）。

    「閉じない」は draw() の呼び出し列にポップアップと選択枠の描画が
    含まれ続けることで検証し（ID-005 以来、状態そのものはアサートしない）、
    「連射しない」（決定2の1押下＝1実行）は押下を保持したまま複数フレーム
    進めても資金・盤面が1回ぶんしか変わらないことで検証する。
    NPC所有店舗を対象に「o」で閉じることを検証していた
    test_o_button_press_closes_popup（TestPopupButtonPress・TDD サイクル7）は、
    仕様が反転したため本クラスの test_buyout_keeps_popup_open_after_execution
    へ置き換える。「x」で閉じることは現行のまま
    （TestPopupButtonPress.test_x_button_press_closes_popup が無改修で担う）。

    実行後の表示内容が実行後の状態になることは、増資の1件
    （test_invest_keeps_popup_open_with_updated_content）が全件一致で兼ねる
    （ID-022_subtasks.md「実行後の表示内容のテストを1件に絞る理由」）。
    建設・買収による区画の状態の切り替え（空き区画 → プレイヤー所有店舗、
    NPC所有店舗 → プレイヤー所有店舗）そのものは test_main_shop_action.py の
    TestBuildShop / TestBuyoutShop が担う"""

    # 建設対象の空き区画（画面左半分 → ポップアップは右下に表示される）
    BUILD_COL = 0
    BUILD_ROW = 2
    # 増資・買収対象の区画（BUILD_COL と同じ画面左半分 → ポップアップは
    # 右下に表示される。区画外への押下（ステータス領域・左の余白・
    # 最下段の閉じの道路）がいずれもポップアップの領域の外側になる
    # 組み合わせを、TestPopupModalPressOutside の対象区画と同じ考え方で選ぶ）
    OWNED_COL = 0
    OWNED_ROW = 4

    def _make_modal_core(self, col, row, owner=None):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        owner を渡すとその区画へ店舗を設置してから選択する
        （TestPopupButtonPress._make_modal_core と同じ考え方）"""
        core = GameCore()
        if owner is not None:
            core._field.set_shop(col, row, owner)  # pylint: disable=W0212
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _press_x_button(self, core, pos):
        """MODAL 状態のポップアップの「x」ボタンの中心を押下する"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, 1)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_build_keeps_popup_open_after_execution(self):
        """空き区画で「o」を押して建設した後も、ポップアップと選択枠が
        描かれ続けること"""
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.BUILD_COL, self.BUILD_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.BUILD_COST,
            shop_count=1,
            tax=self._expected_tax([Shop.BUILD_COST]),
        ) + self._expected_selection_and_popup_calls(
            pos, owner=Owner.PLAYER, value=Shop.BUILD_COST, o_enabled=False
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_invest_keeps_popup_open_with_updated_content(self):
        """プレイヤー所有店舗で「o」を押して増資した後も、ポップアップが
        描かれ続けること。あわせて費用・資産価値・売上額・店舗画像の4つとも
        実行後の状態（規模2）へ更新されていることを、この1回の全件一致で
        確認する（「実行後の表示内容」の新規テストは本メソッド1件に絞る。
        ID-022_subtasks.md「実行後の表示内容のテストを1件に絞る理由」）"""
        core, pos = self._make_modal_core(
            self.OWNED_COL, self.OWNED_ROW, owner=Owner.PLAYER
        )
        self._press_o_button(core, pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
            shop_count=1,
            scale=2,
            tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=2,
            value=Shop.BUILD_COST + Shop.INVEST_COST,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_buyout_keeps_popup_open_after_execution(self):
        """NPC所有店舗で「o」を押して買収した後も、ポップアップが描かれ続ける
        こと（旧 test_o_button_press_closes_popup の反転置き換え。TDD サイクル7
        が固定した「閉じる」仕様を、本サイクルで「閉じない」へ改める）"""
        core, pos = self._make_modal_core(
            self.OWNED_COL, self.OWNED_ROW, owner=Owner.NPC
        )
        self._press_o_button(core, pos)
        self._draw(core)
        cost = Shop.BUILD_COST * Shop.BUYOUT_RATE
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - cost,
            shop_count=1,
            tax=self._expected_tax([Shop.BUILD_COST]),
        ) + self._expected_selection_and_popup_calls(
            pos, owner=Owner.PLAYER, value=Shop.BUILD_COST, o_enabled=False
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_releasing_after_execution_returns_to_modal_and_allows_reselecting(self):
        """実行後に指を離しただけでは追加の実行は起きず（増資は1回のまま）、
        ポップアップは MODAL へ戻ること。「戻ったこと」は内部状態ではなく、
        別の区画を押すと選択がその区画へ切り替わるという外から見える振る舞い
        （ID-021 が確立した MODAL の振る舞い。TestPopupModal.
        test_popup_content_switches_to_pressed_plot と同じ考え方）で示す。
        切り替え先は空き区画のため「o」は建設に結び付くが、増資1回で残り
        資金（GameCore.INITIAL_MONEY − Shop.INVEST_COST = 50）は建設費用
        （Shop.BUILD_COST = 100）に満たず、無効表示になる（o_enabled=False）"""
        core, pos = self._make_modal_core(
            self.OWNED_COL, self.OWNED_ROW, owner=Owner.PLAYER
        )
        self._press_o_button(core, pos)
        self._release(core)
        other_pos = self._plot_center_pos(self.BUILD_COL, self.BUILD_ROW)
        self._press(core, other_pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
            shop_count=1,
            scale=2,
            tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
        ) + self._expected_selection_and_popup_calls(other_pos, o_enabled=False)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_execution_still_allows_closing_via_cancel_button(self):
        """実行後のポップアップも、キャンセルボタン（「x」）の押下で閉じられる
        こと"""
        core, pos = self._make_modal_core(
            self.OWNED_COL, self.OWNED_ROW, owner=Owner.PLAYER
        )
        self._press_o_button(core, pos)
        self._release(core)
        self._press_x_button(core, pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
            shop_count=1,
            scale=2,
            tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_execution_still_allows_closing_via_outside_press(self):
        """実行後のポップアップも、ポップアップの領域でも区画でもない場所への
        押下（ID-021）で閉じられること"""
        for case_name, outside_pos in self._outside_plot_positions():
            with self.subTest(case_name=case_name):
                core, pos = self._make_modal_core(
                    self.OWNED_COL, self.OWNED_ROW, owner=Owner.PLAYER
                )
                self._press_o_button(core, pos)
                self._release(core)
                popup_x = self._expected_popup_x(pos[0])
                self.assertFalse(self._is_in_popup(popup_x, outside_pos))
                self._press(core, outside_pos)
                self._draw(core)
                expected = self._expected_field_calls(
                    [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
                    money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
                    shop_count=1,
                    scale=2,
                    tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_holding_the_o_button_executes_only_once(self):
        """押下を保持したまま複数フレーム進めても、実行は1回だけであること
        （決定2の1押下＝1実行。資金が増資費用の1回ぶんしか減らないことで
        確認する）"""
        core, pos = self._make_modal_core(
            self.OWNED_COL, self.OWNED_ROW, owner=Owner.PLAYER
        )
        self._press_o_button(core, pos)
        # 押下を保持したまま（指を離さずに）複数フレーム進める
        for _ in range(3):
            core.update()
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
            shop_count=1,
            scale=2,
            tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=2,
            value=Shop.BUILD_COST + Shop.INVEST_COST,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_release_then_press_again_executes_a_second_time(self):
        """実行 → 解除 → 再押下で2回目が実行されること（連続実行の成立）。
        増資費用ちょうど2回ぶんの資金を保存データから与え、規模が2段
        （1 → 2 → 3）上がることで確認する"""
        cost1 = Shop.INVEST_COST  # 規模1 → 2
        cost2 = Shop.INVEST_COST * 2  # 規模2 → 3
        self.mock_store.load.return_value = {
            "shops": [
                [self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER.value, 1, Shop.BUILD_COST]
            ],
            "money": cost1 + cost2,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(self.OWNED_COL, self.OWNED_ROW)
        self._press(core, pos)
        self._release(core)
        self._press_o_button(core, pos)
        self._release(core)
        self._press_o_button(core, pos)
        self._draw(core)
        value_after = Shop.BUILD_COST + cost1 + cost2
        expected = self._expected_field_calls(
            [(self.OWNED_COL, self.OWNED_ROW, Owner.PLAYER)],
            money=0,
            shop_count=1,
            scale=3,
            tax=self._expected_tax([value_after]),
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=3,
            value=value_after,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestPopupReactivationAfterButtonPress(TestParent):
    """「o」「x」ボタン押下によるポップアップ終了後、フィールド操作が再び
    有効になるタイミング（TDD サイクル8）の振る舞いテスト。

    無効化・再有効化そのものは内部状態（終了待ちかどうか）ではなく、
    「ボタンを押した指を離さない限り新しいポップアップが開かない」
    「解除して初めて次の押下でポップアップが開く」という外から見える
    振る舞いで検証する（第2部と同じく状態そのものはアサートしない）"""

    # ボタン押下によりポップアップを閉じる対象区画（画面右半分 → 左下表示）。
    # 「o」が空き区画で建設に、プレイヤー所有店舗で増資に、NPC所有店舗で買収に
    # 結び付くようになった（ID-006〜ID-009）ため、ここでは「x」（常にキャンセル
    # で実行を伴わない）で閉じる操作を検証する（本クラスの関心事は再有効化の
    # タイミングであり、実行を伴う「o」の後の再有効化は TestBuildShop /
    # TestInvestShop / TestBuyoutShop が担う）
    BUTTON_COL = 17
    BUTTON_ROW = 0
    # ボタンを離した後に改めて押す区画（内容が新しく取得されたことを確認できるよう
    # 店舗を置く）
    REOPEN_COL = 0
    REOPEN_ROW = 2

    def _make_core_with_shops(self):
        """ボタン押下の対象区画と再選択の対象区画の双方へ店舗を設置した
        GameCore を作る"""
        core = GameCore()
        for col, row, _ in self._expected_shops():
            core._field.set_shop(col, row, Owner.NPC)  # pylint: disable=W0212
        return core

    def _expected_shops(self):
        """本クラスのテストが常に持つ2件の店舗を、Field の列挙順
        （行昇順→列昇順）で返す"""
        return [
            (self.BUTTON_COL, self.BUTTON_ROW, Owner.NPC),
            (self.REOPEN_COL, self.REOPEN_ROW, Owner.NPC),
        ]

    def _close_popup_by_button(self, core, col, row, index=1):
        """指定区画を押して離し MODAL にしたうえで、index 番目のボタンを
        押下してポップアップを閉じる（既定は「x」＝常にキャンセルで実行を
        伴わない）。押下は解除せずに返す（呼び出し側が「指を離さないまま」の
        後続フレームを組み立てられるようにするため）"""
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        return popup_x

    def test_field_operation_stays_disabled_while_button_press_is_held(self):
        """「o」ボタン押下でポップアップを閉じた後、指を離さずにフィールド上へ
        移動しても新しいポップアップが表示されないこと。複数フレーム
        （解除しないまま）経過しても有効化されないことをあわせて確認する"""
        core = self._make_core_with_shops()
        self._close_popup_by_button(core, self.BUTTON_COL, self.BUTTON_ROW)
        reopen_pos = self._plot_center_pos(self.REOPEN_COL, self.REOPEN_ROW)
        # 解除せずに複数フレーム、押下位置を区画上に置いたまま経過させる
        for _ in range(3):
            self._press(core, reopen_pos)
            self._draw(core)
            self.assertEqual(
                self._expected_field_calls(self._expected_shops()),
                self.test_view.get_call_params(),
                self.test_view.get_call_params(),
            )

    def test_release_alone_does_not_show_popup(self):
        """ボタン押下を解除した瞬間（まだフィールドを押していない）は
        ポップアップが表示されないこと。再有効化されるのはあくまで
        「解除の後の押下」からであることを確認する"""
        core = self._make_core_with_shops()
        self._close_popup_by_button(core, self.BUTTON_COL, self.BUTTON_ROW)
        self._release(core)
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(self._expected_shops()),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_field_operation_reenabled_after_button_release(self):
        """ボタン押下でポップアップを閉じた後、押下を解除して初めて
        フィールド操作が再有効化され、その後の押下で新しいポップアップが
        表示されること"""
        core = self._make_core_with_shops()
        self._close_popup_by_button(core, self.BUTTON_COL, self.BUTTON_ROW)
        self._release(core)
        reopen_pos = self._plot_center_pos(self.REOPEN_COL, self.REOPEN_ROW)
        self._press(core, reopen_pos)
        self._draw(core)
        expected = self._expected_field_calls(
            self._expected_shops()
        ) + self._expected_selection_and_popup_calls(reopen_pos, owner=Owner.NPC)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestSelectionFrame(TestParent):
    """選択中の区画をフィールド上で示す黄色い枠（TDD サイクル9）の振る舞いテスト。

    ポップアップは画面の左下／右下に固定表示されるため、それだけでは
    「フィールドのどの区画を選んでいるか」が分からない。枠はその区画を
    フィールド上で直接示すもので、店舗画像とその下の道路を合わせた範囲
    （PREVIEW_W × PREVIEW_H。ポップアップのプレビュー領域と同じ範囲）を、
    店舗の後・ポップアップの前に描く。

    **枠の検証の大半は本クラスではなく既存のポップアップの各テストが担う**。
    枠の期待値は _expected_selection_and_popup_calls() がポップアップの期待値と
    まとめて組み立てるため、ポップアップを検証するテストは必ず枠も検証している。
    具体的には、描画順（店舗の後・ポップアップの前）・4状態それぞれの描画有無
    （NONE / TRACKING / MODAL / CLOSING）・押下位置への追従・押下解除後の固定・
    区画外での非表示が、いずれも既存テストの全件一致で確認済みである。
    そのため本クラスでは重複を作らず、**区画座標から枠の矩形を導く経路**
    （実装の _plot_origin() と PREVIEW_W / PREVIEW_H）だけを、多様な区画に
    対して確認する"""

    def test_selection_frame_drawn_for_pressed_plot(self):
        """フィールドの四隅と中央のいずれの区画を押しても、その区画を囲む
        黄色い枠が描画されること。列・行を独立に動かすことで、枠の位置
        （GRID_LEFT + col * PLOT_SIZE, FIELD_ORIGIN_Y + row * PITCH）と
        サイズ（PREVIEW_W × PREVIEW_H）がどちらの軸についても正しく導かれることを
        確認する。最下行のケースは、枠が判定範囲より道路 1 本分だけ縦に長い
        ぶんが画面外へはみ出さない（最下段の閉じの道路までで収まる）ことの
        確認も兼ねる。描画順・状態ごとの有無・ポップアップとの整合は既存の
        ポップアップのテストが担うため、ここでは枠の呼び出しが含まれること
        だけを見る（ポップアップのレイアウト変更に本テストが巻き込まれない
        よう、全件一致では比較しない）"""
        core = GameCore()
        last_col = GameCore.GRID_COLS - 1
        last_row = GameCore.GRID_ROWS - 1
        test_cases = [
            ("左上の区画", 0, 0),
            ("右上の区画", last_col, 0),
            ("左下の区画", 0, last_row),
            ("右下の区画", last_col, last_row),
            ("中央付近の区画", GameCore.GRID_COLS // 2, GameCore.GRID_ROWS // 2),
        ]
        for case_name, col, row in test_cases:
            with self.subTest(case_name=case_name):
                pos = self._plot_center_pos(col, row)
                self._update_and_draw(core, pos)
                # 枠の呼び出しはその区画につき1件だけ組み立てられる
                (expected_frame,) = self._expected_selection_calls(pos)
                self.assertIn(
                    expected_frame,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                # 枠は判定範囲より道路1本分だけ縦に長いため、最下行でも画面内に
                # 収まることをレイアウト定数の水準で確認する（実装の描画が上の
                # 期待値と一致していることは assertIn 側が担保している）
                _, frame_x, frame_y, frame_w, frame_h, _ = expected_frame
                self.assertLessEqual(frame_x + frame_w, GameCore.SCREEN_W)
                self.assertLessEqual(frame_y + frame_h, GameCore.SCREEN_H)


class TestSettlementPopupDisplay(TestParent):
    """決算ポップアップ自体の描画の振る舞い（表示の継続・他のポップアップとの
    重なりの上下関係）に関するテスト（ID-015 サイクル1）。

    決算タイマーの満了が決算ポップアップの表示（self._settlement_popup_shown）
    に結びつくことは test_main_clock.py の TestSettlementInterval が固定済み
    のため、本クラスはその結びつきを実際のタイマー経過で再現しない。
    _core_with_settlement_popup_shown()（TestParent。ID-015 サイクル2で
    test_main_clock.py からも使えるよう移した）で self._settlement_popup_shown
    を直接立てて検証する（_build_player_shop()（test_main_draw.py の
    TestDrawSettlementStatus）が実際の建設操作を経由せず Field への直接操作で
    盤面を作るのと同じ考え方: 対象外の経路を再現するとテストの関心がぼやける）"""

    def test_settlement_popup_stays_shown_across_frames_without_a_new_expiry(self):
        """決算ポップアップが表示された状態で、新たな満了が無いまま update() を
        何度呼んでも出たままであること（満了したフレームだけ描く誤実装・
        毎フレーム表示状態を失う誤実装を弾く）"""
        core = self._core_with_settlement_popup_shown()
        for _ in range(3):
            core.update()
        self._draw(core)
        calls = self.test_view.get_call_params()
        bg_call, border_call = self._expected_settlement_popup_calls()
        self.assertIn(bg_call, calls, calls)
        self.assertIn(border_call, calls, calls)

    def test_settlement_popup_is_drawn_after_the_selection_popup(self):
        """決算ポップアップが出ている間に区画選択ポップアップも表示された
        状態があれば、決算ポップアップはその後（最前面）に描かれること
        （店舗や枠に隠れる誤実装・区画選択ポップアップより先に描く誤実装を
        弾く）。表示中の押下操作の抑止（ID-015 サイクル3）により、決算
        ポップアップ表示中の押下では区画選択ポップアップはもう現れないため、
        本テストは描画順という関心事だけを見るために、区画選択の状態
        （_popup_plot / _popup_x / _popup_state）を押下経由ではなく直接立てる
        （_core_with_settlement_popup_shown() が決算ポップアップの状態を
        直接立てるのと同じ考え方）。実際に両方が同時に出せない（抑止される）
        ことはサイクル3の抑止テスト（test_main_clock.py の
        TestSettlementPopupSuppressesFieldOperations /
        TestSettlementPopupResetsSelectionOnExpiry）が別途担う"""
        core = self._core_with_settlement_popup_shown()
        pos = self._plot_center_pos(0, 0)
        core._popup_plot = self._expected_plot(pos)  # pylint: disable=W0212
        core._popup_x = self._expected_popup_x(pos[0])  # pylint: disable=W0212
        core._popup_state = PopupState.MODAL  # pylint: disable=W0212
        self._draw(core)
        calls = self.test_view.get_call_params()
        # 区画選択の枠・ポップアップが実際に出ていること（両方が同時に描画
        # できることの確認。抑止は update() 側の話であり draw() 自体は
        # 状態さえ立っていれば両方を描く）
        for call in self._expected_selection_and_popup_calls(pos):
            self.assertIn(call, calls, calls)
        # 決算ポップアップの背景・枠・数値3行（筆算。ID-027 サイクル027-3で
        # 横線・「-」の2件が増え9件になった）・「o」ボタンは、描画列の**末尾**
        # （最前面）に来ること（盤面に店舗が無いため税額は0、減算前後とも
        # 初期資金のまま）
        expected_tail = (
            self._expected_settlement_popup_calls()
            + self._expected_settlement_popup_value_calls(
                GameCore.INITIAL_MONEY, 0, GameCore.INITIAL_MONEY
            )
            + self._expected_settlement_popup_button_calls()
        )
        self.assertEqual(expected_tail, calls[-9:], calls)


class TestSettlementPopupValues(TestParent):
    """決算ポップアップ内の数値3行（減算前・税額・減算後）の振る舞いテスト
    （ID-015 サイクル2）。TestPopupValues（区画選択ポップアップの数値3項目）と
    対になるクラス: GameCore はこの3つの値を「盤面と資金から都度導出して
    そのまま描画する」relay に徹し、税額そのものの算出（土地税・資産税の式）は
    test_field.py 側の TestFieldTotalTax が検証するため、ここでは重複させない。

    決算タイマーの満了が決算ポップアップの表示に結びつくことは
    TestSettlementInterval（test_main_clock.py）が固定済みのため、本クラスも
    TestSettlementPopupDisplay と同じく _core_with_settlement_popup_shown()
    （TestParent）で状態を直接立てて検証する。「毎フレーム導出」であることは、
    完全凍結（サイクル4）が入ると時間経過では確認できなくなるため、時間を
    進めるのではなくテストから直接盤面・資金を書き換えて追従を見る
    （TestPopupValues.test_values_draw_from_shop_for_owned_plot と同じ、
    Shop の内部状態を直接書き換える手法）"""

    def _draw_and_get_tail(self, core):
        """draw() を実行し、決算ポップアップぶん（背景・枠線・数値3行・
        横線・「-」・「o」ボタンの9件。ID-027 サイクル027-3で数値3行が
        筆算の形になり横線・「-」の2件が増えた）の描画呼び出しを末尾から
        取り出す（決算ポップアップは常に最前面＝末尾に描かれる。
        TestSettlementPopupDisplay と同じ考え方）"""
        self._draw(core)
        calls = self.test_view.get_call_params()
        return calls[-9:]

    def _core_with_player_shops(self, values):
        """values（各店舗の資産価値の列）ぶんのプレイヤー所有店舗を、列0の
        行0から順に1軒ずつ設置した、決算ポップアップ表示中の GameCore を返す
        （盤面の作り方だけをまとめる共通処理。減算前・税額・減算後の3値は
        呼び出し側が用途ごとに導出する）。
        **行0の横並びではなく列0の縦並びに置く**のは、列0が地域価格倍率の
        等倍（1.0）になる列であるため（ID-020 案8-A）——本クラスの関心は
        「資産価値と資金の組み合わせから3行がどう導かれるか」であり、
        倍率が税額へ効くことは test_field.py の TestFieldAreaTotalTax が
        押さえる。行0の横並びのままだと列ごとに倍率が変わり、渡した資産価値
        そのものを期待値に使えなくなる。
        書き換える資産価値（_value）は地域価格倍率を反映した実額であり
        （ID-020）、列0は等倍のため渡した値がそのまま資産価値になる"""
        core = self._core_with_settlement_popup_shown()
        for row, value in enumerate(values):
            core._field.set_shop(0, row, Owner.PLAYER)  # pylint: disable=W0212
            core._field._shops[(0, row)]._value = value  # pylint: disable=W0212
        return core

    def test_shows_before_tax_after_for_various_boards_and_money(self):
        """減算前・税額・減算後の3行が、盤面（プレイヤー所有店舗の資産価値）・
        資金の組み合わせに応じて正しく導出されて描画されることを、5通りの
        ケースで確認する:
          - 地価0（総資産価値が GRID_PLOT_COUNT 未満）で資産税のみが正
          - 土地税・資産税の両方が正（総資産価値が GRID_PLOT_COUNT 以上。
            税額の算出を Field から取らずに再実装する誤実装を弾く）
          - 資金 < 税額（減算後が0で頭打ちにならず負の数のまま描かれること）
          - 資金 == 税額（減算後が0。境界のずれを弾く）
          - 6桁の資金・税額（桁あふれ（表示位置がずれる・文字列が切り詰め
            られるなど）が無いこと）
        表示中に値が書き換わったときの追従は別の観点（1つの盤面・資金を
        時間軸で2段階変える）のため、
        test_values_follow_the_board_and_money_when_they_change_while_shown
        へ分けたまま本メソッドへは統合しない。
        premise（4番目の要素）は、ケースの前提（地価0になる・6桁になるなど）が
        定数の変更で崩れていないかを、値そのものではなく形（正か・桁数か）で
        確認する（前提が崩れて検証が無意味になる前に気付けるように。
        TestPopupPosition が押下位置の前提を明示するのと同じ考え方）"""
        test_cases = [
            (
                "プレイヤー所有1軒（地価0・資産税のみ）",
                [Shop.BUILD_COST],
                None,
                lambda tax: self.assertGreater(tax, 0, tax),
            ),
            (
                "土地税・資産税とも正（合計300 >= GRID_PLOT_COUNT=270）",
                [Shop.BUILD_COST] * 3,
                None,
                None,
            ),
            (
                "資金 < 税額（減算後が負）",
                [Shop.BUILD_COST],
                lambda tax: tax - 2,
                None,
            ),
            ("資金 == 税額（減算後が0）", [Shop.BUILD_COST], lambda tax: tax, None),
            (
                "6桁の資金・税額",
                [2000000],
                lambda tax: 123456,
                lambda tax: self.assertEqual(6, len(str(tax)), tax),
            ),
        ]
        for case_name, values, money_fn, premise in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_player_shops(values)
                tax = self._expected_tax(values)
                if premise is not None:
                    premise(tax)
                if money_fn is not None:
                    core._money = money_fn(tax)  # pylint: disable=W0212
                before = core._money  # pylint: disable=W0212
                expected_tail = (
                    self._expected_settlement_popup_calls()
                    + self._expected_settlement_popup_value_calls(
                        before, tax, before - tax
                    )
                    + self._expected_settlement_popup_button_calls()
                )
                self.assertEqual(expected_tail, self._draw_and_get_tail(core))

    def test_ones_digit_aligns_across_differently_sized_values(self):
        """減算前・税額・減算後の桁数が互いに異なっていても、筆算の右詰め
        （ID-027 サイクル027-3 決定10）で3つの一の位の x が揃うこと——
        「左詰めのまま横線だけ足した」実装（見た目が筆算にならない）を弾く、
        本サイクルの中心の主張。期待値を _expected_settlement_popup_value_
        calls() 経由で作らず、実際に描画された3つの draw_text の
        (x, 文字列) だけから独立に検証する（ヘルパー自体が誤っていても
        検知できるように）。
        資産価値500の店舗1軒（資産税 500 × 5% = 25、地価 500 // 270 = 1 →
        土地税1、税額計26）に資金1000を組み合わせ、減算前1000（4桁）・
        税額26（2桁）・減算後974（3桁）と3つとも桁数が異なる盤面を作る"""
        core = self._core_with_player_shops([500])
        core._money = 1000  # pylint: disable=W0212
        tax = core._field.total_tax()  # pylint: disable=W0212
        after = core._money - tax  # pylint: disable=W0212
        # 前提: 3値の桁数が互いに異なること（崩れたらこの検証自体が
        # 無意味になる。TestPopupPosition が押下位置の前提を明示するのと
        # 同じ考え方）
        digit_counts = {
            len(str(core._money)),  # pylint: disable=W0212
            len(str(tax)),
            len(str(after)),
        }
        self.assertEqual(
            3, len(digit_counts), (core._money, tax, after)  # pylint: disable=W0212
        )
        tail = self._draw_and_get_tail(core)
        value_calls = [
            call for call in tail if call[0] == "draw_text" and call[3] != "-"
        ]
        self.assertEqual(3, len(value_calls), tail)
        ones_digit_x = {
            call[1] + (len(call[3]) - 1) * GameCore.FONT_CHAR_W for call in value_calls
        }
        self.assertEqual(1, len(ones_digit_x), tail)

    def test_values_follow_the_board_and_money_when_they_change_while_shown(self):
        """表示中に盤面（Field への直接操作）・資金を書き換えると、税額・
        減算後の行がそのフレームの値へ追従すること（満了時点の値を固定して
        持ち回る誤実装を弾く）"""
        core = self._core_with_player_shops([Shop.BUILD_COST])
        tax_before_change = self._expected_tax([Shop.BUILD_COST])
        money = core._money  # pylint: disable=W0212
        expected_tail = (
            self._expected_settlement_popup_calls()
            + self._expected_settlement_popup_value_calls(
                money, tax_before_change, money - tax_before_change
            )
            + self._expected_settlement_popup_button_calls()
        )
        self.assertEqual(expected_tail, self._draw_and_get_tail(core))

        # 表示中に、押下経路を経由せず盤面・資金を直接書き換える（区画選択の
        # 「o」押下は抑止対象になるサイクル3の範囲であり、本テストの関心は
        # 「変われば追従するか」だけのため、押下経路を経由しない直接操作で
        # 変化を作る）
        # 追加する店舗も列0（地域価格倍率が等倍）に取る（_core_with_player_shops()
        # と同じ理由。倍率の乗る区画だと Shop.BUILD_COST をそのまま期待値に
        # 使えない）
        core._field.set_shop(0, 1, Owner.PLAYER)  # pylint: disable=W0212
        core._money -= 50  # pylint: disable=W0212
        tax_after_change = self._expected_tax([Shop.BUILD_COST, Shop.BUILD_COST])
        self.assertNotEqual(tax_before_change, tax_after_change)
        money_after = core._money  # pylint: disable=W0212
        expected_tail_after = (
            self._expected_settlement_popup_calls()
            + self._expected_settlement_popup_value_calls(
                money_after, tax_after_change, money_after - tax_after_change
            )
            + self._expected_settlement_popup_button_calls()
        )
        self.assertEqual(expected_tail_after, self._draw_and_get_tail(core))


class TestSettlementPopupSettlement(TestParent):
    """決算ポップアップ内の「o」ボタンを押すと精算が実行されること（要件4。
    ID-015 サイクル5）に関する振る舞いテスト。「クリック」の定義は未確定
    事項1の結論（候補A: 押下で実行 → 非表示 → 指が離れるまでフィールド
    操作を無効 → 離れて「なし」へ戻る）に従う。押下を受け付ける範囲は
    当初ポップアップの矩形全体としていたが、それでは見た目から「タップして
    閉じる」ことが読み取れないというユーザー指摘を受け、区画選択ポップアップと
    同じ「o」ボタン1つへ絞った（サイクル5 Refactor・再考）。

    決算タイマーを実際に満了させて精算前の状態を作る（`TestSettlementInterval`
    /`TestSettlementPopupFreezesTime`（test_main_clock.py）と同じ、
    time.perf_counter 固定・_advance_ms の与え方）。`_core_with_settlement_
    popup_shown()`（TestParent）の直接状態立てではなく実際の満了を経由する
    理由は2つ: (1) 「表示された税額と引かれた額が一致する」ことを確認するには
    盤面から導出された本物の税額が要る、(2) 「凍結が解ける」ことを確認するには
    実際に凍結（pause()）された4つのタイマーが要る（直接状態を立てるだけでは
    タイマーは止まっていない）"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 決算ポップアップ内「o」ボタンの矩形の中の画面座標（実装の
    # _settlement_popup_button_rect() と同じ式を、期待値ヘルパーと同様に
    # 実装から独立して持つ）。x はボタン中央のまま。y は決算・終了2つの
    # ボタンが重なる範囲の中で、遅く始まる方（値が大きい方）の上端を使う
    # ——後段の test_settling_into_game_over_does_not_immediately_reset が
    # 想定するとおり、この座標は終了ポップアップの「o」ボタンの矩形にも
    # 入っている必要があるため（クラス docstring 参照）。決算ボタンの
    # 中央だった旧実装は、3行目を横線から離す SETTLEMENT_POPUP_RULE_TEXT_GAP
    # の追加（プレイテスト指摘。2026-08-30）でボタンが2px下へ動いた結果、
    # 終了ボタンの矩形からわずかにはみ出すようになったため、max() で常に
    # 両方の矩形へ入る座標を選ぶ形へ改めた
    BUTTON_POS = (
        GameCore.SETTLEMENT_POPUP_X
        + GameCore.SETTLEMENT_POPUP_PAD
        + GameCore.SETTLEMENT_POPUP_BTN_W // 2,
        max(
            GameCore.SETTLEMENT_POPUP_Y
            + GameCore.SETTLEMENT_POPUP_PAD
            + 3 * GameCore.SETTLEMENT_POPUP_LINE_H
            + GameCore.SETTLEMENT_POPUP_RULE_TEXT_GAP
            + GameCore.SETTLEMENT_POPUP_PAD,
            GameCore.GAME_END_POPUP_Y
            + GameCore.GAME_END_POPUP_PAD
            + GameCore.GAME_END_POPUP_LINE_H
            + GameCore.GAME_END_POPUP_PAD,
        ),
    )
    # ポップアップ内だが「o」ボタンの外（数値3行の1行目付近）の画面座標。
    # 「ポップアップの中でもボタン以外は反応しない」ことの確認に使う
    # （ボタンへ絞った本サイクルの再考で追加した観点）
    INSIDE_POPUP_NOT_BUTTON_POS = (
        GameCore.SETTLEMENT_POPUP_X + GameCore.SETTLEMENT_POPUP_W // 2,
        GameCore.SETTLEMENT_POPUP_Y + GameCore.SETTLEMENT_POPUP_PAD,
    )
    # 決算ポップアップの矩形外の画面座標（画面原点。決算ポップアップは画面
    # 中央固定のため、原点は常に矩形の外側にあたる）
    OUTSIDE_POPUP_POS = (0, 0)
    # 精算後、フィールド操作が再び効くことを確認する区画（建設に使う区画とは別）
    REOPEN_COL = 17
    REOPEN_ROW = 0

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔（60秒）の経過中に売上発生間隔（3秒）が必ず満了するため、
        # 抽選先を固定して無関係な失敗を避ける（TestSettlementInterval と同じ）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )
        # 資金不足時の売却（ID-016）の抽選先も固定する。本クラスの盤面には
        # プレイヤー所有店舗が1軒（PLAYER_COL/PLAYER_ROW）しかないため、対象は
        # 常にその1軒のみだが、他の2件（pick_npc_growth_target /
        # pick_sales_shop）と同じく決定的にしておく（targets[0] を選ぶだけの
        # 単純な固定。対象が1件のみのため他の候補との区別は不要）
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _core_with_settlement_popup_expired(self):
        """プレイヤー所有店舗を1軒（実際の建設操作で）設置し、決算タイマーを
        実際に満了させて決算ポップアップを表示状態（凍結済み）にした
        GameCore を返す。建設・満了のいずれも実際の経路を通すため、押下・
        解除を最後まで行い、区画選択ポップアップを NONE へ戻してから返す
        （後続の押下判定が区画選択の残留状態に引きずられないように。
        `TestSettlementPopupFreezesTime._build_player_shop()` と同じ形）"""
        core = GameCore()
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )
        return core

    def _settlement_popup_tax(self, core):
        """決算ポップアップに**いま実際に表示されている**税額を、draw() の
        出力（数値3行の中央の draw_text）から読み取る。_expected_tax() で
        独立に算出しない理由: 本クラスは決算タイマーを実際に満了させるため
        （_core_with_settlement_popup_expired()）、待つ間に他店建設間隔・
        売上発生間隔も満了し得て、盤面（NPC所有店舗の有無）が実行のたびに
        変わり得る。「表示された額と実際に引かれる額が一致するか」を見るのが
        目的のケースでは、その時点の盤面から独立に期待値を組み立てるより、
        画面に実際に出た値をそのまま使うほうが素直で、かつ本クラスの関心
        （精算の振る舞い）とは無関係な盤面の組み立てを増やさずに済む
        （税額そのものの正しさは _expected_tax() を使う TestSettlementPopupValues
        が既に担っている）"""
        self._draw(core)
        # 決算ポップアップぶん9件（ID-027 サイクル027-3で数値3行が筆算の
        # 形になり横線・「-」の2件が増えたが、数値3行の並び自体は動いて
        # いないため、税額（3番目）の添字は変わらない）
        tail = self.test_view.get_call_params()[-9:]
        return int(tail[3][3])

    def test_press_inside_settles_money_and_closes_popup(self):
        """「o」ボタンを押して離すと、表示されていた税額ぶんが資金から引かれ
        （表示と実際の減算が同じ値であること）、決算ポップアップが閉じる
        （draw() の呼び出し列に決算ポップアップが含まれなくなる）こと。
        精算は押下解除（released）で実行される（ID-018 プレイテストで
        見つかった不具合の修正。_update_settlement_popup() の docstring を
        参照）ため、押すだけでなく離すところまで行う。盤面は、減算後の
        資金が負にならない限り変わらない（弾く誤実装: 税の支払いだけで店舗を
        減らす）が、負になる場合は不足額（ID-016）ぶんだけ売却が起き、
        調達額が資金へ足され、盤面（唯一のプレイヤー所有店舗）が NPC 所有へ
        変わることを、資金の3通りの関係（資金が税額を上回る／ちょうど／
        下回る）で確認する。減算後の資金が負のケースの不足額は2で、
        1軒しかないプレイヤー所有店舗の資産価値の半額（Shop.BUILD_COST // 2）
        が2を上回るため、1軒の売却で満たされ切る"""
        test_cases = [
            ("資金 > 税額", None, False),
            ("資金 == 税額", lambda tax: tax, False),
            ("資金 < 税額（負になる。売却が起きる）", lambda tax: tax - 2, True),
        ]
        for case_name, money_fn, expect_sale in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_settlement_popup_expired()
                tax = self._settlement_popup_tax(core)
                if money_fn is not None:
                    core._money = money_fn(tax)  # pylint: disable=W0212
                money_before = core._money  # pylint: disable=W0212
                shops_before = core._field.get_save_data()  # pylint: disable=W0212
                self._press(core, self.BUTTON_POS)
                self._release(core)
                if expect_sale:
                    self.assertEqual(
                        money_before - tax + Shop.BUILD_COST // 2,
                        core._money,  # pylint: disable=W0212
                    )
                    self.assertNotEqual(
                        shops_before,
                        core._field.get_save_data(),  # pylint: disable=W0212
                    )
                else:
                    self.assertEqual(
                        money_before - tax, core._money  # pylint: disable=W0212
                    )
                    self.assertEqual(
                        shops_before,
                        core._field.get_save_data(),  # pylint: disable=W0212
                    )
                self._draw(core)
                calls = self.test_view.get_call_params()
                bg_call, border_call = self._expected_settlement_popup_calls()
                self.assertNotIn(bg_call, calls, calls)
                self.assertNotIn(border_call, calls, calls)

    def test_settling_into_game_over_does_not_immediately_reset(self):
        """決算ポップアップの「o」を押して離した結果ゲームオーバーが成立
        しても、その押下解除だけで終了ポップアップの needs_reset が立たない
        こと（ID-018 プレイテストで見つかった不具合の回帰）。

        修正前は精算の実行そのものが押下（down）の瞬間に起きていたため、
        「決算の『o』を押した」その押下保持が、精算 → ゲームオーバー成立の
        直後に切り替わった終了ポップアップの『o』判定へそのまま流れ込み、
        終了ポップアップが画面に一度も描かれないままリセットされていた。
        精算・終了ポップアップの『o』とも押下解除（released）を契機にした
        ことで、決算の『o』を離した瞬間の released は決算側で使い切られ、
        終了ポップアップ側には渡らない（_update_settlement_popup() /
        _update_game_end_popup() の docstring を参照）。needs_reset は、
        終了ポップアップが現れた**後**にユーザーが改めてその『o』を押して
        離したときにだけ立つことを、同じ座標への2回目の押下解除で確認する
        （決算・終了いずれの『o』も画面中央に横幅・水平位置が同じ固定の
        ボタンとして重なって置かれ、BUTTON_POS の座標はどちらの矩形内にも
        入るため、座標を変えずに再現できる。実際にこの座標の重なりが、
        修正前の不具合——決算の『o』への押下保持がそのまま終了ポップアップ
        側の判定に流れ込んだこと——の直接の原因だった）"""
        core = self._core_with_settlement_popup_expired()
        # 売り尽くしても不足額に届かない資金にして、精算がゲームオーバーを
        # 成立させるようにする（test_nothing_progresses_after_the_game_over
        # と同じ考え方）
        core._money = -10 * GameCore.INITIAL_MONEY  # pylint: disable=W0212
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self.assertEqual(
            GameEndState.GAME_OVER, core._game_end_state  # pylint: disable=W0212
        )
        # ゲームオーバー成立直後の押下解除だけでは needs_reset は立たない
        self.assertFalse(core.needs_reset)
        # 終了ポップアップが現れた後、改めてその「o」を押して離すと初めて
        # needs_reset が立つ（決算・終了の両ポップアップとも画面中央固定の
        # ため、座標は BUTTON_POS のまま流用できる）
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self.assertTrue(core.needs_reset)

    def test_press_outside_the_button_does_not_settle_or_close(self):
        """「o」ボタン以外（決算ポップアップの矩形外・ポップアップ内だが
        ボタン以外の余白）を押しても、精算されず（資金が変わらず）、
        ポップアップも閉じない（表示され続ける）こと（設計判断のとおり。
        「ポップアップの矩形全体をタップ対象にすると分かりにくい」という
        指摘を受けてボタンへ絞ったサイクル5の再考が、実際に矩形全体では
        なくボタンだけに反応することを弾く誤実装で確認する）"""
        test_cases = [
            ("ポップアップ外（画面原点）", self.OUTSIDE_POPUP_POS),
            (
                "ポップアップ内だが「o」ボタンの外（数値3行付近）",
                self.INSIDE_POPUP_NOT_BUTTON_POS,
            ),
        ]
        for case_name, press_pos in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_settlement_popup_expired()
                money_before = core._money  # pylint: disable=W0212
                self._press(core, press_pos)
                self.assertEqual(money_before, core._money)  # pylint: disable=W0212
                self.assertEqual(
                    SettlementPopupState.SHOWN,
                    core._settlement_popup_state,  # pylint: disable=W0212
                )
                self._draw(core)
                calls = self.test_view.get_call_params()
                bg_call, border_call = self._expected_settlement_popup_calls()
                self.assertIn(bg_call, calls, calls)
                self.assertIn(border_call, calls, calls)

    def test_settlement_saves_immediately(self):
        """「o」ボタンを押して離した直後に保存されること（凍結中は定期保存も
        止まっているため、ここで保存しないと精算が保存データへ載らない）。
        精算は押下解除（released）で実行される（_update_settlement_popup()
        の docstring を参照）ため、押すだけでなく離すところまで行う"""
        core = self._core_with_settlement_popup_expired()
        self.mock_store.save.reset_mock()
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self.mock_store.save.assert_called_once()

    def test_frozen_timers_resume_after_settlement(self):
        """精算後は凍結が解け、他店建設・売上・保存の各タイマーが再び進む
        こと（凍結したまま止まる誤実装を弾く）。他店建設の進行は盤面の
        店舗数が増えることで、保存の再開は ReportStore.save が呼ばれる
        ことで確認する（売上の再開はサイクル4で「凍結中は進まない」ことを
        既に確認済みのため、ここでは重複させず他店建設・保存の2点で
        「4つとも同じ一覧（self._freeze_clocks）で再開される」ことを表す）"""
        core = self._core_with_settlement_popup_expired()
        shops_before = core._field.get_save_data()  # pylint: disable=W0212
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self.mock_store.save.reset_mock()
        self._advance_ms(
            max(GameCore.NPC_GROWTH_INTERVAL_MS, GameCore.SAVE_INTERVAL_MS)
        )
        core.update()
        self.assertGreater(
            len(core._field.get_save_data()),  # pylint: disable=W0212
            len(shops_before),
        )
        self.mock_store.save.assert_called()

    def test_field_operations_work_again_after_release(self):
        """精算後、押した指を離すと区画選択ポップアップ・選択枠が再び有効に
        なること（抑止が解除されないままの誤実装を弾く）。決算タイマーを
        実際に満了させて作った状態のため、待つ間の他店建設で盤面が動きうる
        （_core_with_settlement_popup_expired() を参照）。本テストの関心は
        「区画選択が機能を取り戻すか」だけであり盤面の内容ではないため、
        選択枠・ポップアップの呼び出しが**含まれること**を assertIn で
        確認する（呼び出し列全体の一致は求めない）"""
        core = self._core_with_settlement_popup_expired()
        self._press(core, self.BUTTON_POS)
        self._release(core)
        reopen_pos = self._plot_center_pos(self.REOPEN_COL, self.REOPEN_ROW)
        self._press(core, reopen_pos)
        self._draw(core)
        calls = self.test_view.get_call_params()
        for call in self._expected_selection_and_popup_calls(reopen_pos):
            self.assertIn(call, calls, calls)

    def test_field_stays_disabled_while_settlement_press_is_held(self):
        """精算した指を離さずにフィールドへ移動しても、新しい区画選択
        ポップアップ・選択枠が生まれないこと（未確定事項1の結論どおり。
        取りこぼし防止が決算ポップアップにも適用されていることを弾く）。
        上記と同じ理由（盤面が動きうる）で assertNotIn を使う"""
        core = self._core_with_settlement_popup_expired()
        self._press(core, self.BUTTON_POS)
        reopen_pos = self._plot_center_pos(self.REOPEN_COL, self.REOPEN_ROW)
        self._press(core, reopen_pos)
        self._draw(core)
        calls = self.test_view.get_call_params()
        for call in self._expected_selection_and_popup_calls(reopen_pos):
            self.assertNotIn(call, calls, calls)

    def test_no_popup_until_the_next_expiry_after_settlement(self):
        """精算して指を離した後、次の決算間隔が満了するまでは決算ポップアップ
        が現れないこと（閉じた直後に再び開く誤実装を弾く）"""
        core = self._core_with_settlement_popup_expired()
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS - 1)
        core.update()
        self._draw(core)
        calls = self.test_view.get_call_params()
        bg_call, border_call = self._expected_settlement_popup_calls()
        self.assertNotIn(bg_call, calls, calls)
        self.assertNotIn(border_call, calls, calls)

    def test_popup_reappears_periodically_after_settlement(self):
        """精算して指を離した後、決算間隔ぶん進めると決算ポップアップが
        再び現れること（1回で終わらず周期的であることを弾く誤実装:
        精算後に決算タイマーが再開しない）"""
        core = self._core_with_settlement_popup_expired()
        self._press(core, self.BUTTON_POS)
        self._release(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )


class TestSettlementPopupSellsShortfall(TestParent):
    """決算精算で資金不足時に売却（ID-016）が呼び出され、調達額が資金へ
    足されることの振る舞いテスト（要件3.9）。案8のとおり、`GameCore` 側が
    担うのは「不足の判定・呼び出し・資金への加算」の3点のみで、売却の中身
    （何軒売れたか・どの店舗が NPC所有になるか）には関知しない。
    `Field.sell_shops_for_shortfall()` を固定額を返すスタブへ差し替え、
    売却の中身に依存しない形で確認する（具体的な売却の振る舞い・繰り返し・
    停止条件は `test_field.py` の `TestFieldSellShopsForShortfall` が担う）。

    決算タイマーを実際に満了させず（`TestSettlementPopupSettlement` と
    異なり、本クラスの関心は精算の中身であって契機ではない。契機の再現は
    `test_main_clock.py` の `TestSettlementInterval` が担う）、
    `_core_with_settlement_popup_shown()`（`TestParent`）で状態を直接
    立てる。`Field.total_tax()` も固定額へ差し替え、盤面（空のまま）とは
    無関係に税額と資金の関係だけを制御する"""

    # 精算開始時に固定する税額（本クラスの盤面は空のままのため、実際の
    # Field.total_tax() は常に0になる。テストの関心は「税額と資金の関係」
    # であって税額そのものの正しさではないため、スタブで任意の値に固定する）
    TAX = 30

    def _core_with_fixed_tax(self):
        core = self._core_with_settlement_popup_shown()
        patcher_tax = patch.object(
            core._field, "total_tax", return_value=self.TAX  # pylint: disable=W0212
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        return core

    def _press_button(self, core):
        """決算ポップアップの「o」ボタンを押して離す。精算は押下解除
        （released）で実行される（_update_settlement_popup() の docstring を
        参照）ため、押すだけでなく離すところまで行う"""
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def test_calls_sell_shops_for_shortfall_only_when_money_goes_negative(self):
        """精算（税額の減算）後の資金が負になったときだけ、その不足額
        （`-self._money`。正の数）とともに `Field.sell_shops_for_shortfall()`
        が呼ばれ、返った額（調達額）が資金へ足されること。資金が税額を
        上回る場合・ちょうど一致する（減算後が0になる）場合はいずれも
        呼ばれず、資金は減算後の値のまま変わらないこと（要件3.9・案6の
        `self._money += self._field.sell_shops_for_shortfall(-self._money)`
        という形の境界を、資金と税額の3通りの関係で確認する）"""
        test_cases = [
            ("資金 > 税額", self.TAX + 10, False, None),
            ("資金 == 税額（減算後ちょうど0）", self.TAX, False, None),
            ("資金 < 税額（不足5）", self.TAX - 5, True, 5),
        ]
        for case_name, money_before, expect_called, expected_shortfall in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_fixed_tax()
                core._money = money_before  # pylint: disable=W0212
                raised = 12
                with patch.object(
                    core._field,  # pylint: disable=W0212
                    "sell_shops_for_shortfall",
                    return_value=raised,
                ) as mock_sell:
                    self._press_button(core)
                    if expect_called:
                        mock_sell.assert_called_once_with(expected_shortfall)
                        self.assertEqual(
                            money_before - self.TAX + raised,
                            core._money,  # pylint: disable=W0212
                        )
                    else:
                        mock_sell.assert_not_called()
                        self.assertEqual(
                            money_before - self.TAX,
                            core._money,  # pylint: disable=W0212
                        )

    def test_saves_after_the_shortfall_sale(self):
        """不足時の保存（`_settle_tax()` 末尾の `self._save()`）が、売却
        （`sell_shops_for_shortfall()`）の**後**に行われること（弾く誤実装:
        売却前の盤面・資金を保存してしまい、売却結果が保存データへ載らない
        まま次の保存間隔まで取り残される）。呼び出し順序をひとつの
        `Mock` へ束ねて確認する。

        **`Field.min_acquisition_cost()` を固定する（ID-024）**: 本クラスの
        盤面は空のままのため（本テストの関心は保存の順序であって盤面では
        ない）、精算後は必ず0軒になる。調達額12（資金は
        25 − 30 + 12 = 7）は実際の最小取得費用（盤面がほぼ空のため
        Shop.BUILD_COST = 100）を下回り、事業継続の判定（要件 3.15）が
        新たにゲームオーバーを成立させて `self._save()` を呼ばせなくなって
        しまう。`total_tax()` / `sell_shops_for_shortfall()` を固定するのと
        同じ考え方（盤面とは無関係に金額の関係だけを制御する。案8）で、
        最小取得費用も7以下へ固定し、本テストの関心（呼び出し順序）を
        保つ"""
        core = self._core_with_fixed_tax()
        core._money = self.TAX - 5  # pylint: disable=W0212
        patcher_min_cost = patch.object(
            core._field, "min_acquisition_cost", return_value=0  # pylint: disable=W0212
        )
        patcher_min_cost.start()
        self.addCleanup(patcher_min_cost.stop)
        manager = Mock()
        with patch.object(
            core._field,  # pylint: disable=W0212
            "sell_shops_for_shortfall",
            return_value=12,
        ) as mock_sell:
            manager.attach_mock(mock_sell, "sell_shops_for_shortfall")
            manager.attach_mock(self.mock_store.save, "save")
            self._press_button(core)
        self.assertEqual(
            ["sell_shops_for_shortfall", "save"],
            [call[0] for call in manager.mock_calls],
        )


class TestGameEndPopup(TestParent):
    """終了（クリア／ゲームオーバー）ポップアップが画面に現れることに関する
    振る舞いテスト（要件「勝利条件」「敗北条件」「ゲーム終了後」・要件3.9。
    ID-017 サイクル3）。

    終了の判定そのもの（規定店舗数へ到達しているか・売り尽くしても不足額に
    届かなかったか）は `Field` が答える（`test_field.py` の
    `TestFieldClearShopCount` / `TestFieldSellShopsForShortfall` が担う。
    案8）。本クラスが検証するのは、その答えが `GameCore` を経由して実際に
    ポップアップとして画面へ現れることのみであり、判定の中身（何軒到達すれば
    成立するか・何軒売れば足りるか）には立ち入らない。

    終了が成立した操作（建設・買収・精算）は、その操作の直後に通常行って
    いる `self._save()` を呼ばない（サイクル2完了時のユーザー指示。理由は
    `_build_selected_plot()` 等の docstring を参照）。この保存の有無は、
    ポップアップが現れるかどうかとまったく同じ条件（終了が成立したか）で
    決まるため、専用のテスト関数を別に立てず、**その条件を作るテストと
    同じ関数の中で**まとめて確認する（同じ盤面・同じ操作を2つのテスト
    関数で重複して組み立てない）。ただし、既に他のファイルで確認済みの
    「通常の建設・買収・精算は保存される」こと自体（`test_main_save.py` の
    `TestSaveOnDataChange` / `test_main_popup.py` の
    `TestSettlementPopupSettlement.test_settlement_saves_immediately`）は
    本クラスでは重複させない。

    **「終了ポップアップが現れないこと」のテストも、同じ理由で無条件には
    足さない**。本ファイル（`test_main_shop_action.py` 等も含め）の描画
    テストは軒並み `assertEqual` による画面全体の全件一致で検証しており、
    `draw()` に `_draw_game_end_popup()` を足した時点で、**その全件一致を
    崩さずに通っている既存テストすべてが「この場面ではポップアップが
    描かれない」ことを暗黙に証明している**（描かれれば期待値に無い呼び
    出しが混ざり、そのテストは落ちる）。既存の全件一致テストがそのまま
    証明する場面（例えば「終了していない通常の初期盤面」——
    `test_main_save.py` の
    `TestGameCoreSaveLoad.test_draw_shows_shops_and_money_from_save_data_or_initial_values`
    が保存データ無しのケースで既に確認済み）は重複させない。

    さらに、**盤面・操作そのものが既存テストと重ならなくても、その終了
    判定の分岐（`_settle_tax()` の `if self._money < 0:`）を一度も通らない
    シナリオは、判定が誤って書かれても再現できない**（分岐へ入らなければ
    冒頭の `game_over = False` がそのまま効き、常に「正しい」結果になって
    しまう）ため、専用テストとして残す価値が無いと判断した。「税額を資金が
    上回り不足が生じない」ケースがこれに当たり、`TestSettlementPopupSettlement.
    test_press_inside_settles_money_and_closes_popup` の「資金 > 税額」
    「資金 == 税額」サブケースと場面が重なるだけでなく、分岐に入らない以上
    どちらのテストも同程度にしか誤りを検出できないため、本クラスには
    持たない。対照的に「売却で不足額を満たす」ケースは分岐へ実際に入る
    （`game_over = not self._field.shortfall_covered` を書き忘れて常に
    `True` にする、といった現実的な誤りを検出できる）ため、
    `test_press_inside_settles_money_and_closes_popup` の「資金 < 税額」
    サブケースと場面は重なっていても、本クラスに残す"""

    # 精算まわりのテストで固定する税額（本クラスの盤面は基本的に空のため、
    # 実際の Field.total_tax() は常に0になる。TestSettlementPopupSellsShortfall
    # と同じ考え方）
    TAX = 30

    def _core_with_fixed_tax(self, money):
        """決算ポップアップが表示された状態で、税額を self.TAX に固定し、
        資金を money にした GameCore を返す（TestSettlementPopupSellsShortfall
        の `_core_with_fixed_tax()` と同じ考え方）"""
        core = self._core_with_settlement_popup_shown()
        core._money = money  # pylint: disable=W0212
        patcher_tax = patch.object(
            core._field, "total_tax", return_value=self.TAX  # pylint: disable=W0212
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        return core

    def _core_with_fixed_tax_and_shop_count(self, money, shop_count):
        """決算ポップアップが表示された状態で、税額を self.TAX に固定し、
        資金を money、プレイヤー所有店舗を shop_count 軒にした GameCore を
        返す（_core_with_fixed_tax() に、規定店舗数（Field.CLEAR_SHOP_COUNT）
        の境界を盤面へ作る _core_with_player_shops() を足した形。
        「規定店舗数へ到達した状態で決算を通過するとクリアが成立する」
        テストと「決算時の店舗売却で規定数を下回るとクリアにならない」
        テストの両方が共有する（ID-028 サイクル028-2 TASK-028-6）"""
        core = self._core_with_player_shops(shop_count)
        core._settlement_popup_state = (  # pylint: disable=W0212
            SettlementPopupState.SHOWN
        )
        core._money = money  # pylint: disable=W0212
        patcher_tax = patch.object(
            core._field, "total_tax", return_value=self.TAX  # pylint: disable=W0212
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        return core

    def _press_settlement_button(self, core):
        """決算ポップアップの「o」ボタンを押して離す。精算は押下解除
        （released）で実行される（ID-018 プレイテストで見つかった不具合の
        修正。_update_settlement_popup() の docstring を参照）ため、押す
        だけでなく離すところまで行う"""
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _expected_full_game_end_popup_calls(self, message):
        """終了ポップアップ（背景・枠線・文言・「o」ボタン）の呼び出し期待値を
        まとめて返す。個々のテストが3つのヘルパーを毎回連結せずに済む"""
        return (
            self._expected_game_end_popup_calls()
            + [self._expected_game_end_popup_message_call(message)]
            + self._expected_game_end_popup_button_calls()
        )

    def _expected_full_board_tax(self):
        """全区画がプレイヤー所有店舗である盤面の、支払い予定税額の期待値を
        返す。
        **本クラスだけは盤面全体を埋めるため、区画ごとの地域価格倍率を避けて
        通れない**——他のテストのように店舗を等倍の列0・列17へ寄せることが
        できず（ID-020 案8-A の逃げ道が使えない）、設置直後の資産価値は区画
        ごとに `Shop.BUILD_COST × その区画の倍率` になり、土地税も区画ごとの
        倍率で重み付けされる（要件 3.8・3.10）。そのため資産価値の列と倍率の
        列を並べて組み立て、_expected_tax() へ倍率も渡す"""
        values = []
        rates = []
        for row in range(GameCore.GRID_ROWS):
            for col in range(GameCore.GRID_COLS):
                rate = self._expected_area_rate(col, row)
                values.append(Shop.BUILD_COST * rate // Shop.AREA_RATE_BASE)
                rates.append(rate)
        return self._expected_tax(values, player_rates=rates)

    def _expected_full_board_field_calls(self, money, tax):
        """全区画がプレイヤー所有店舗である盤面の、ステータス→道路→店舗の
        描画呼び出し期待値を返す（_expected_field_calls() と同じ構成。
        本クラスのどのテストにも売上の囲みは現れないため含めない。店舗は
        いずれも設置直後の規模のまま——建設・買収のいずれも規模を変えない
        ——のため Shop.INITIAL_SCALE 一律で描く）"""
        shop_calls = []
        for row in range(GameCore.GRID_ROWS):
            for col in range(GameCore.GRID_COLS):
                shop_calls += self._expected_shop_calls(
                    [(col, row, Owner.PLAYER)], scale=Shop.INITIAL_SCALE
                )
        return (
            self._expected_status_calls(
                money=money,
                shop_count=GameCore.GRID_COLS * GameCore.GRID_ROWS,
                tax=tax,
            )
            + self._expected_road_calls()
            + shop_calls
        )

    def test_building_the_last_vacant_plot_does_not_show_the_clear_popup(self):
        """最後の空き区画へ建設すると全区画がプレイヤー所有店舗になるが、
        それだけではクリアは成立しない（要件 3.16。ID-028）——通常どおり
        self._save() が呼ばれ、その結果としての画面全体——ステータス・
        道路・270区画すべての店舗——にクリアポップアップを含まないこと
        （建設されたのは最後の1区画だけであることも、店舗の描画呼び出し
        列の全件一致が担保する。クリアは決算の精算完了直後にのみ判定される
        ——TestGameEndPopup の同名クラスにある決算経由の2テストを参照）。
        実行後も区画選択ポップアップ（クリアポップアップとは別物）は閉じずに
        残る（ID-022 決定1）ため、末尾へその期待値を足す。(0, 0) は地域価格
        倍率が等倍（Field.AREA_RATE_EDGE == Shop.AREA_RATE_BASE）の区画のため、
        建設費用は Shop.BUILD_COST のまま——残り資金（100）は増資費用
        （150）に満たず「o」は無効表示になる"""
        core = self._core_with_one_vacant_plot(0, 0)
        pos = self._plot_center_pos(0, 0)
        popup_x = self._press_plot(core, 0, 0)
        self.mock_store.save.reset_mock()
        self._press_o_button(core, popup_x)
        self.mock_store.save.assert_called_once()
        self._draw(core)
        tax = self._expected_full_board_tax()
        expected = self._expected_full_board_field_calls(
            money=GameCore.INITIAL_MONEY - Shop.BUILD_COST, tax=tax
        ) + self._expected_selection_and_popup_calls(
            pos, owner=Owner.PLAYER, o_enabled=False
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_buying_out_the_last_npc_shop_does_not_show_the_clear_popup(self):
        """最後のNPC所有店舗を買収すると全区画がプレイヤー所有店舗になるが、
        それだけではクリアは成立しない（建設と対になるもう一方の経路。
        要件 3.16。ID-028）——通常どおり self._save() が呼ばれ、その結果
        としての画面全体にクリアポップアップを含まないこと（買収は資産
        価値を変えないため、270区画すべてが設置直後の規模・費用のまま
        描かれる）。実行後も区画選択ポップアップは閉じずに残る（ID-022
        決定1）ため、末尾へその期待値を足す。買収費用ちょうど
        （Shop.BUILD_COST × Shop.BUYOUT_RATE = 200）で資金が尽きるため、
        増資費用を賄えず「o」は無効表示になる"""
        core = self._core_with_one_vacant_plot(0, 0)
        core._field.set_shop(0, 0, Owner.NPC)  # pylint: disable=W0212
        pos = self._plot_center_pos(0, 0)
        popup_x = self._press_plot(core, 0, 0)
        self.mock_store.save.reset_mock()
        self._press_o_button(core, popup_x)
        self.mock_store.save.assert_called_once()
        self._draw(core)
        tax = self._expected_full_board_tax()
        expected = self._expected_full_board_field_calls(
            money=GameCore.INITIAL_MONEY - Shop.BUILD_COST * Shop.BUYOUT_RATE, tax=tax
        ) + self._expected_selection_and_popup_calls(
            pos, owner=Owner.PLAYER, value=Shop.BUILD_COST, o_enabled=False
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_reaching_the_clear_shop_count_and_settling_shows_the_clear_popup(self):
        """規定店舗数（Field.CLEAR_SHOP_COUNT）ちょうどの盤面で決算を通過
        すると、self._save() が呼ばれないまま（クリアを成立させた精算は
        保存を抑止するという申し送り。_settle_tax() の docstring を参照）
        クリアポップアップが現れること（要件3.16。ID-028 サイクル028-2）。
        資金が税額をちょうど賄う（資金 == 税額）ため売却は起きず
        （`self._money < 0` の分岐へ入らない）、規定店舗数はそのまま
        維持される——決算時の売却によって規定数を下回るケースは次の
        テストで扱う"""
        core = self._core_with_fixed_tax_and_shop_count(
            money=self.TAX, shop_count=Field.CLEAR_SHOP_COUNT
        )
        self.mock_store.save.reset_mock()
        self._press_settlement_button(core)
        self.mock_store.save.assert_not_called()
        self._draw(core)
        shops = [
            (col, row, Owner.PLAYER)
            for col, row in self._player_shop_positions(Field.CLEAR_SHOP_COUNT)
        ]
        expected = self._expected_field_calls(
            shops=shops, money=0, shop_count=Field.CLEAR_SHOP_COUNT, tax=self.TAX
        ) + self._expected_full_game_end_popup_calls(GameCore.GAME_END_MESSAGE_CLEAR)
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_settlement_that_sells_a_shop_below_the_clear_shop_count_does_not_show_the_clear_popup(
        self,
    ):
        """規定店舗数（Field.CLEAR_SHOP_COUNT）ちょうどの盤面で決算を迎え、
        不足額を埋めるための売却（ID-016）によってプレイヤー所有店舗が
        規定数を1軒下回った場合、クリアポップアップは現れず self._save() が
        通常どおり（売却が不足額を満たしゲームオーバーにもならない場合と
        同じく）呼ばれること（要件3.16「決算時の店舗売却によって規定店舗数を
        下回った場合はクリアとしない」）。**クリア判定を売却の前に置く
        誤実装**——売却前の規定数ちょうどでクリアと判定してしまう——を
        検出できるのはこのテストだけである（ID-028_subtasks.md「クリアに
        ならない」3つの境界の表。判定位置を売却の後に置く決定3がそのまま
        この境界を満たすかどうかを、ここで確かめる）。
        売却の抽選は行昇順→列昇順の先頭（(0, 0)。地域価格倍率は等倍）を
        選ぶよう固定し、その資産価値（Shop.BUILD_COST = 100）の半額 50 で
        不足額（5）を賄う（TestSettlementPopupSellsShortfall と同じ考え方。
        資金は 25 − 30 + 50 = 45）"""
        core = self._core_with_fixed_tax_and_shop_count(
            money=self.TAX - 5, shop_count=Field.CLEAR_SHOP_COUNT
        )
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]
        self.mock_store.save.reset_mock()
        self._press_settlement_button(core)
        self.mock_store.save.assert_called_once()
        self._draw(core)
        shops = [
            (col, row, Owner.NPC if (col, row) == (0, 0) else Owner.PLAYER)
            for col, row in self._player_shop_positions(Field.CLEAR_SHOP_COUNT)
        ]
        expected = self._expected_field_calls(
            shops=shops,
            money=45,
            shop_count=Field.CLEAR_SHOP_COUNT - 1,
            tax=self.TAX,
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_game_end_popup_drawn_after_settlement_popup(self):
        """終了ポップアップが決算ポップアップより後（最前面）に描かれること
        （要件「ゲーム終了後」）。描画順という関心事だけを見るため、区画
        選択の状態を直接立てる TestSettlementPopupDisplay と同じ考え方で、
        終了・決算いずれの状態も接続の経路を経由せず直接立てる"""
        core = GameCore()
        core._game_end_state = GameEndState.CLEAR  # pylint: disable=W0212
        core._settlement_popup_state = (  # pylint: disable=W0212
            SettlementPopupState.SHOWN
        )
        self._draw(core)
        expected = (
            self._expected_field_calls()
            + self._expected_settlement_popup_calls()
            + self._expected_settlement_popup_value_calls(
                GameCore.INITIAL_MONEY, 0, GameCore.INITIAL_MONEY
            )
            + self._expected_settlement_popup_button_calls()
            + self._expected_full_game_end_popup_calls(GameCore.GAME_END_MESSAGE_CLEAR)
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_settlement_that_cannot_cover_shortfall_shows_the_game_over_popup(self):
        """精算で不足額を売り尽くしても満たせないとき、self._save() が
        呼ばれないまま（ゲームオーバーを成立させた精算は保存を抑止する
        という申し送り）、その結果としての画面全体——ステータス（資金は
        負のまま・税額は固定値のまま）・ゲームオーバーポップアップ——が
        描かれること。盤面が空（プレイヤー所有店舗が無い）ため売る店舗が
        無く、不足額（5）に一切届かない"""
        core = self._core_with_fixed_tax(self.TAX - 5)
        self.mock_store.save.reset_mock()
        self._press_settlement_button(core)
        self.mock_store.save.assert_not_called()
        self._draw(core)
        expected = self._expected_field_calls(
            money=-5, tax=self.TAX
        ) + self._expected_full_game_end_popup_calls(
            GameCore.GAME_END_MESSAGE_GAME_OVER
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_settlement_that_covers_shortfall_does_not_show_the_game_over_popup(self):
        """精算で不足額を売却が満たせたときは、self._save() が従来どおり
        呼ばれ、ゲームオーバーポップアップを含まない画面全体——売却で
        NPC所有へ変わった1軒だけを含むフィールド——が描かれること。
        プレイヤー所有店舗を1軒（資産価値 Shop.BUILD_COST）置いておくだけでは
        **足りない**（ID-024）: 売却額（Shop.BUILD_COST // 2 = 50）は不足額
        （5）こそ上回るが、売却後は0軒になり、資金45は最小取得費用
        （盤面がほぼ空のため Shop.BUILD_COST = 100）を下回るため、事業継続の
        判定（要件 3.15）が新たにゲームオーバーを成立させてしまう。
        売却前に増資しておく（規模2・資産価値 Shop.BUILD_COST +
        Shop.INVEST_COST = 250。列0は地域価格倍率が等倍のためどちらも
        そのままの額）ことで、売却額（250 // 2 = 125）が不足額（5）に加えて
        最小取得費用（100）も上回るようにする（資金は
        25 − 30 + 125 = 120）。売却は所有者を NPC へ変えるだけで店舗規模・
        資産価値は変えない（Shop.sell() の契約）ため、売却後の盤面には
        規模2のNPC所有店舗が1軒残る"""
        core = self._core_with_fixed_tax(self.TAX - 5)
        core._field.set_shop(0, 0, Owner.PLAYER)  # pylint: disable=W0212
        core._field.invest_shop(0, 0)  # pylint: disable=W0212
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]
        self.mock_store.save.reset_mock()
        self._press_settlement_button(core)
        self.mock_store.save.assert_called_once()
        self._draw(core)
        expected = self._expected_field_calls(
            shops=[(0, 0, Owner.NPC)], money=120, scale=2, tax=self.TAX
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )


class TestSettlementTriggersBusinessContinuationCheck(TestParent):
    """決算の精算が完了した直後に、事業継続の判定（プレイヤー所有店舗が
    0軒 かつ 資金 < 最小取得費用。要件 3.15）が行われ、成立すれば
    ゲームオーバーになることに関するテスト（ID-024 サイクル024-3。
    他店建設・増資の直後の契機と対になる、もう一方の契機——
    `test_main_clock.py` の `TestNpcGrowthTriggersBusinessContinuationCheck`
    と同じ考え方）。

    最小取得費用そのものの算出は test_field.py の
    `TestFieldMinAcquisitionCost` が担うため、本クラスは
    `Field.min_acquisition_cost()` を固定値へ差し替え、`GameCore` 側の
    判定の境界・順序だけを見る（`TestGameEndPopup._core_with_fixed_tax()`
    が `Field.total_tax()` を固定するのと同じ考え方）。

    本クラスの盤面は常に空（プレイヤー所有店舗が0軒）のまま——事業継続の
    判定条件の片方（0軒）を常に満たした状態で、もう片方（資金）の境界だけを
    動かす"""

    TAX = 30
    MIN_COST = 100

    def _core_with_fixed_tax_and_min_cost(self, money):
        """決算ポップアップが表示された状態で、税額と最小取得費用を固定し、
        資金を money にした GameCore を返す（`TestGameEndPopup.
        _core_with_fixed_tax()` と同じ考え方に、`min_acquisition_cost()`
        の固定を足した形）"""
        core = self._core_with_settlement_popup_shown()
        core._money = money  # pylint: disable=W0212
        patcher_tax = patch.object(
            core._field, "total_tax", return_value=self.TAX  # pylint: disable=W0212
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        patcher_min_cost = patch.object(
            core._field,  # pylint: disable=W0212
            "min_acquisition_cost",
            return_value=self.MIN_COST,
        )
        patcher_min_cost.start()
        self.addCleanup(patcher_min_cost.stop)
        return core

    def _press_settlement_button(self, core):
        """決算ポップアップの「o」ボタンを押して離す（精算は押下解除で
        実行される。TestGameEndPopup と同じ）"""
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def test_game_over_when_tax_is_paid_in_full_but_money_stays_below_the_min_acquisition_cost(
        self,
    ):
        """税金を不足なく支払い切れた場合（`self._money < 0` の分岐へ入らず、
        売却が一度も起きない場合）でも、0軒かつ資金が最小取得費用未満なら
        ゲームオーバーになること（要件が名指しで定める境界。判定を「不足
        したとき（売却が起きたとき）だけ」行う誤実装は、この分岐に入らない
        本テストだけが弾ける）。税額ちょうど支払った直後の資金
        （MIN_COST - 1）が最小取得費用を1つ下回るようにする"""
        core = self._core_with_fixed_tax_and_min_cost(self.TAX + self.MIN_COST - 1)
        self.mock_store.save.reset_mock()
        self._press_settlement_button(core)
        self.mock_store.save.assert_not_called()
        self._draw(core)
        expected = (
            self._expected_field_calls(money=self.MIN_COST - 1, tax=self.TAX)
            + self._expected_game_end_popup_calls()
            + [
                self._expected_game_end_popup_message_call(
                    GameCore.GAME_END_MESSAGE_GAME_OVER
                )
            ]
            + self._expected_game_end_popup_button_calls()
        )
        self.assertEqual(
            expected, self.test_view.get_call_params(), self.test_view.get_call_params()
        )

    def test_money_boundary_against_the_min_acquisition_cost_after_settlement(self):
        """資金の境界3点（`<` と `<=` の取り違えを弾く）。税金を支払い
        切った直後の資金が、最小取得費用の1つ下では終了し、ちょうど・
        1つ上では終了しないこと"""
        test_cases = [
            ("1つ下（終了）", self.MIN_COST - 1, GameEndState.GAME_OVER),
            ("ちょうど（継続）", self.MIN_COST, GameEndState.NONE),
            ("1つ上（継続）", self.MIN_COST + 1, GameEndState.NONE),
        ]
        for case_name, money_after_tax, expected_state in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_fixed_tax_and_min_cost(
                    self.TAX + money_after_tax
                )
                self._press_settlement_button(core)
                self.assertEqual(
                    expected_state, core._game_end_state  # pylint: disable=W0212
                )

    def test_continues_and_saves_when_the_post_settlement_money_meets_the_min_acquisition_cost(
        self,
    ):
        """精算の結果（売却による調達を含む）、資金が最小取得費用ちょうど
        以上になれば、従来どおりゲームは続き self._save() が呼ばれること
        （要件「1つ以上ある場合は…」の資金側の対——決算精算で0軒に
        なっても、再開できるだけの資金が残っていれば終了しない）。
        `Field.sell_shops_for_shortfall()` を固定額へ差し替え（盤面が空の
        ため実際の売却は起きない。`TestSettlementPopupSellsShortfall` と
        同じ考え方）、調達後の資金がちょうど最小取得費用に一致する境界を作る
        （不足額5 + 最小取得費用100 = 105 を調達額とし、資金は
        25 − 30 + 105 = 100）"""
        core = self._core_with_fixed_tax_and_min_cost(self.TAX - 5)
        with patch.object(
            core._field,  # pylint: disable=W0212
            "sell_shops_for_shortfall",
            return_value=5 + self.MIN_COST,
        ):
            self.mock_store.save.reset_mock()
            self._press_settlement_button(core)
        self.mock_store.save.assert_called_once()
        self.assertEqual(
            GameEndState.NONE, core._game_end_state  # pylint: disable=W0212
        )
        self.assertEqual(self.MIN_COST, core._money)  # pylint: disable=W0212

    def test_existing_game_over_takes_precedence_and_skips_the_min_acquisition_cost_lookup(
        self,
    ):
        """売り尽くしても不足額に届かない場合（ID-017 のゲームオーバー。
        `Field.shortfall_covered` が偽）は、そちらが先に成立し、事業継続の
        判定へは到達しないこと（決定5）。盤面が空のため売る店舗が無く、
        不足額に一切届かない——`sell_shops_for_shortfall()` は実物のまま
        呼ぶ（`_list_sell_targets()` が空を返し `shortfall_covered` が偽に
        なることそのものが本テストの前提のため、固定値へは差し替えない）。
        `Field.min_acquisition_cost()` を実装を保ったまま呼び出しを記録する
        （`wraps`）ことで、**先に成立した ID-017 側のゲームオーバーが
        return し、事業継続の判定（min_acquisition_cost() の呼び出しを
        伴う）へは一度も到達しないこと**を直接確認する（ID-024_subtasks.md
        「包含関係そのものはテストで固定する」を、呼び出しの有無という
        観測可能な形で表す）"""
        core = self._core_with_settlement_popup_shown()
        core._money = -(self.TAX + 100)  # pylint: disable=W0212
        patcher_tax = patch.object(
            core._field, "total_tax", return_value=0  # pylint: disable=W0212
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        with patch.object(
            core._field,  # pylint: disable=W0212
            "min_acquisition_cost",
            wraps=core._field.min_acquisition_cost,  # pylint: disable=W0212
        ) as mock_min_cost:
            self._press_settlement_button(core)
        self.assertEqual(
            GameEndState.GAME_OVER, core._game_end_state  # pylint: disable=W0212
        )
        mock_min_cost.assert_not_called()


class TestGameEndSuppressesFieldOperations(TestParent):
    """終了（クリア／ゲームオーバー）ポップアップの表示中は、フィールドの
    押下操作を一切受け付けないこと（ID-017 案7・サイクル4）に関するテスト。
    決算ポップアップ表示中の抑止（test_main_clock.py の
    `TestSettlementPopupSuppressesFieldOperations`）と同じ形だが、発生
    契機が時間経過ではなく操作（建設・買収・精算）であるため popup 側に
    置く（案8のテストの振り分け）。

    終了の判定・接続（どの操作でどちらの終了が成立するか）は
    `TestGameEndPopup` が固定済みのため、本クラスはそれを実際の操作で
    再現せず、`core._game_end_state` を直接立てて検証する
    （`TestSettlementPopupSuppressesFieldOperations` が
    `_core_with_settlement_popup_shown()` で状態を直接立てるのと同じ
    考え方）。

    抑止の観点は2つ（区画選択ポップアップ・選択枠が現れないこと／「o」の
    押下が建設・増資・買収へ結びつかないこと）あるが、**どちらも同じ1つの
    条件（終了状態が立っていること）から決まり、同じ1回の操作の結果として
    同時に現れる**ため、テスト関数は分けない。画面全体の全件一致で見れば、
    区画選択ポップアップの出現も、建設された店舗・減った資金も、いずれも
    期待値との差として同じ1つの assertEqual が捉える"""

    def test_press_and_o_button_do_nothing_while_the_game_end_popup_is_shown(self):
        """終了ポップアップの表示中に区画を押して離し（MODAL 化を試み）、
        その位置に出るはずの「o」ボタンを押しても、画面がフィールドと終了
        ポップアップのみのまま変わらない（区画選択ポップアップも選択枠も
        現れず、建設も起きないため資金も盤面も動かない）こと。
        クリア・ゲームオーバーのどちらの終了状態でも同じであること
        （分岐が片方の状態だけを見る誤実装を弾く）を subTest で確かめる"""
        test_cases = [
            (GameEndState.CLEAR, GameCore.GAME_END_MESSAGE_CLEAR),
            (GameEndState.GAME_OVER, GameCore.GAME_END_MESSAGE_GAME_OVER),
        ]
        for state, message in test_cases:
            with self.subTest(state=state):
                core = GameCore()
                core._game_end_state = state  # pylint: disable=W0212
                self._press_plot_and_o_button(core, 0, 0)
                self._draw(core)
                expected = (
                    self._expected_field_calls()
                    + self._expected_game_end_popup_calls()
                    + [self._expected_game_end_popup_message_call(message)]
                    + self._expected_game_end_popup_button_calls()
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestGameEndPopupReset(TestParent):
    """終了（クリア／ゲームオーバー）ポップアップの「o」ボタン押下で
    `needs_reset` が立つこと（ID-018 サイクル2）に関するテスト。

    `needs_reset` が実際に GameCore の差し替えへ結びつくことは
    test_main_save.py 側（ID-018 サイクル3）が確認する。本クラスが見るのは
    GameCore 単体の振る舞い（押下位置と終了状態の組み合わせから
    needs_reset が導かれること）のみ"""

    def test_needs_reset_stays_false_without_the_game_ending(self):
        """終了していない通常の GameCore は needs_reset が False であり、
        終了ポップアップの「o」ボタンと同じ座標を押しても（終了状態が
        NONE のままなら）needs_reset は False のままであること（終了して
        いないときに同じ座標へ何かが起きないことの回帰）。生成直後と
        押下後の2つの観点を、同じ core に対する確認としてまとめる"""
        core = GameCore()
        self.assertFalse(core.needs_reset)
        btn_x, btn_y, btn_w, btn_h = self._expected_game_end_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self.assertFalse(core.needs_reset)

    def test_pressing_the_button_sets_needs_reset_when_the_game_ends(self):
        """終了状態（クリア／ゲームオーバーの両方を subTest で）が立って
        いるとき、終了ポップアップの「o」ボタン矩形内を押して離すと
        needs_reset が True になること（分岐が片方の状態だけを見る誤実装を
        弾く）。needs_reset は押下解除（released）で立つ（ID-018 プレイ
        テストで見つかった不具合の修正。_update_game_end_popup() の
        docstring を参照）ため、押すだけでなく離すところまで行う"""
        for state in (GameEndState.CLEAR, GameEndState.GAME_OVER):
            with self.subTest(state=state):
                core = GameCore()
                core._game_end_state = state  # pylint: disable=W0212
                btn_x, btn_y, btn_w, btn_h = self._expected_game_end_popup_button_rect()
                self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
                self._release(core)
                self.assertTrue(core.needs_reset)

    def test_pressing_outside_the_button_does_not_set_needs_reset(self):
        """終了状態が立っていても、「o」ボタン矩形外（フィールド上の区画
        など）を押しても needs_reset は False のままであること
        （TestGameEndSuppressesFieldOperations が確認する「フィールド
        操作が起きないこと」とは別に、needs_reset という新しい観点として
        確認する）"""
        for state in (GameEndState.CLEAR, GameEndState.GAME_OVER):
            with self.subTest(state=state):
                core = GameCore()
                core._game_end_state = state  # pylint: disable=W0212
                self._press(core, self._plot_center_pos(0, 0))
                self.assertFalse(core.needs_reset)


class TestStatusSpeedButtonCycle(TestParent):
    """ステータス右のスピードボタン「>」系の押下による段階の循環表示に
    関するテスト（ID-019 サイクル4）。段階（GAME_SPEED_STEPS の添字）
    そのものを直接読むテストは作らず、押下のたびにラベルが「>」→「>>」→
    「>>>」→「>」と循環して描かれることだけを確認する（設計方針1・
    ID-019_subtasks.md）。各タイマーへの反映は次サイクル 019-5 が別に
    確認する"""

    def _speed_button_center(self):
        """スピードボタンの矩形の中心座標を返す（押下位置として使う）"""
        x, y, w, h = self._expected_status_speed_button_rect()
        return x + w // 2, y + h // 2

    def _assert_speed_label(self, core, label):
        self._draw(core)
        calls = self.test_view.get_call_params()
        self.assertIn(
            self._expected_status_speed_button_label_call(label), calls, calls
        )

    def test_pressing_the_speed_button_advances_the_label_one_step(self):
        """スピードボタンの矩形内で押下解除すると、ラベルが「>」から
        「>>」へ1段階進んで描かれること"""
        core = GameCore()
        self._press(core, self._speed_button_center())
        self._release(core)
        self._assert_speed_label(core, ">>")

    def test_pressing_repeatedly_cycles_through_the_labels(self):
        """押下を繰り返すとラベルが「>」→「>>」→「>>>」→「>」と循環する
        こと（最高速の次は最低速へ戻る）"""
        core = GameCore()
        pos = self._speed_button_center()
        for label in (">>", ">>>", ">"):
            self._press(core, pos)
            self._release(core)
            self._assert_speed_label(core, label)

    def test_pressing_outside_the_button_does_not_change_the_label(self):
        """矩形外（ステータスの他の場所・フィールド上）での押下解除では
        ラベルが変わらないこと"""
        core = GameCore()
        for pos in (
            (GameCore.STATUS_X + GameCore.STATUS_PAD, GameCore.STATUS_Y),
            self._plot_center_pos(0, 0),
        ):
            with self.subTest(pos=pos):
                self._press(core, pos)
                self._release(core)
        self._assert_speed_label(core, ">")

    def test_holding_the_button_down_does_not_advance_the_label(self):
        """押しっぱなし（押下解除しない）ではラベルが進み続けないこと"""
        core = GameCore()
        pos = self._speed_button_center()
        for _ in range(3):
            self._press(core, pos)
        self._assert_speed_label(core, ">")

    def test_no_reaction_while_the_settlement_popup_is_shown(self):
        """決算ポップアップ表示中はスピードボタンの押下解除に反応しない
        こと"""
        core = self._core_with_settlement_popup_shown()
        self._press(core, self._speed_button_center())
        self._release(core)
        self._assert_speed_label(core, ">")

    def test_no_reaction_while_the_game_end_popup_is_shown(self):
        """ゲーム終了中（クリア／ゲームオーバーの両方を subTest で）は
        スピードボタンの押下解除に反応しないこと"""
        for state in (GameEndState.CLEAR, GameEndState.GAME_OVER):
            with self.subTest(state=state):
                core = GameCore()
                core._game_end_state = state  # pylint: disable=W0212
                self._press(core, self._speed_button_center())
                self._release(core)
                self._assert_speed_label(core, ">")

    def test_pressing_the_status_area_does_not_select_a_plot(self):
        """ステータス領域の押下（スピードボタンを含む）で区画が選択
        されないこと（回帰。_screen_to_plot() は y < FIELD_ORIGIN_Y の
        押下を区画外として None を返すため、押下位置は TRACKING へ進まず
        NONE のまま留まる）"""
        core = GameCore()
        self._press(core, self._speed_button_center())
        self.assertEqual(PopupState.NONE, core._popup_state)  # pylint: disable=W0212


class TestStatusPauseButtonToggle(TestParent):
    """ステータス右のポーズボタン「||」の押下による、ポーズの開始・解除に
    関するテスト（ID-019 サイクル6）。ポーズ状態を持つ状態と切り替えの
    入口は、本サイクルでは**2つのボタンの配色として観測できる形**で導入
    する（サイクル4→5と同じ分け方。設計方針6-1）。タイマーへの反映は次
    サイクル 019-7 で足すため、ここではまだ時間を止めない。押下判定その
    ものの型（矩形内／外・押しっぱなし・モーダル中の無反応）は
    TestStatusSpeedButtonCycle と同じ形をなぞる（分類ルール4件目）"""

    def _pause_button_center(self):
        """ポーズボタンの矩形の中心座標を返す（押下位置として使う）"""
        x, y, w, h = self._expected_status_pause_button_rect()
        return x + w // 2, y + h // 2

    def _speed_button_center(self):
        """スピードボタンの矩形の中心座標を返す（押下位置として使う）"""
        x, y, w, h = self._expected_status_speed_button_rect()
        return x + w // 2, y + h // 2

    def _assert_button_colors(self, core, paused):
        """draw() を実行し、ポーズ・スピード両ボタンの矩形・ラベルが
        paused の状態どおりの配色で描かれていることを確認する
        （_expected_status_button_calls(paused=...) を鏡として使う）"""
        self._draw(core)
        calls = self.test_view.get_call_params()
        for call in self._expected_status_button_calls(paused=paused):
            self.assertIn(call, calls, calls)

    def test_pressing_the_pause_button_enters_pause_and_swaps_the_colors(self):
        """ポーズボタンの矩形内で押下解除すると、ポーズボタンが通常表示・
        スピードボタンが無効表示へ入れ替わること"""
        core = GameCore()
        self._press(core, self._pause_button_center())
        self._release(core)
        self._assert_button_colors(core, paused=True)

    def test_pressing_the_speed_button_while_paused_exits_pause_and_keeps_the_speed_label(
        self,
    ):
        """ポーズ中にスピードボタンを押下解除すると、ポーズが解除され
        （無効表示が元へ戻り）、スピードのラベルは変わらないこと（設計
        方針6-1の表。TestStatusSpeedButtonCycle の「押すたびに循環する」
        がポーズ中は起きないことの確認でもある）"""
        core = GameCore()
        self._press(core, self._pause_button_center())
        self._release(core)
        self._press(core, self._speed_button_center())
        self._release(core)
        self._assert_button_colors(core, paused=False)
        self._draw(core)
        self.assertIn(
            self._expected_status_speed_button_label_call(">"),
            self.test_view.get_call_params(),
        )

    def test_pressing_the_pause_button_again_while_paused_exits_pause_and_keeps_the_speed_label(
        self,
    ):
        """ポーズ中にポーズボタンを押下解除しても同じくポーズが解除され、
        スピードのラベルが変わらないこと（ポーズ前の段階がそのまま
        保たれる）"""
        core = GameCore()
        self._press(core, self._pause_button_center())
        self._release(core)
        self._press(core, self._pause_button_center())
        self._release(core)
        self._assert_button_colors(core, paused=False)
        self._draw(core)
        self.assertIn(
            self._expected_status_speed_button_label_call(">"),
            self.test_view.get_call_params(),
        )

    def test_pressing_outside_the_buttons_does_not_toggle_pause(self):
        """矩形外（ステータスの他の場所・フィールド上）での押下解除では
        入れ替わらないこと"""
        core = GameCore()
        for pos in (
            (GameCore.STATUS_X + GameCore.STATUS_PAD, GameCore.STATUS_Y),
            self._plot_center_pos(0, 0),
        ):
            with self.subTest(pos=pos):
                self._press(core, pos)
                self._release(core)
        self._assert_button_colors(core, paused=False)

    def test_holding_the_pause_button_down_does_not_toggle_pause(self):
        """押しっぱなし（押下解除しない）では入れ替わり続けないこと"""
        core = GameCore()
        pos = self._pause_button_center()
        for _ in range(3):
            self._press(core, pos)
        self._assert_button_colors(core, paused=False)

    def test_no_reaction_while_the_settlement_popup_is_shown(self):
        """決算ポップアップ表示中はポーズボタンの押下解除に反応しない
        こと"""
        core = self._core_with_settlement_popup_shown()
        self._press(core, self._pause_button_center())
        self._release(core)
        self._assert_button_colors(core, paused=False)

    def test_no_reaction_while_the_game_end_popup_is_shown(self):
        """ゲーム終了中（クリア／ゲームオーバーの両方を subTest で）は
        ポーズボタンの押下解除に反応しないこと"""
        for state in (GameEndState.CLEAR, GameEndState.GAME_OVER):
            with self.subTest(state=state):
                core = GameCore()
                core._game_end_state = state  # pylint: disable=W0212
                self._press(core, self._pause_button_center())
                self._release(core)
                self._assert_button_colors(core, paused=False)


class TestPauseCoexistsWithFieldOperationsAndSettlement(TestParent):
    """ポーズ中もフィールド操作（区画選択・建設）が可能であること、および
    決算ポップアップの精算（`_settle_tax()`）での再開がポーズ中には効かない
    ことに関するテスト（ID-019 サイクル7）。タイマーへの一時停止・再開
    そのものは test_main_clock.py の `TestPauseHaltsAndResumesTimers` が
    担うため、ここでは押下判定・ポップアップの状態遷移を伴う2点だけを見る
    （分類ルール1・4）。

    **「精算での再開がポーズ中には効かない」経路の作り方**: 決算ポップアップ
    表示中はステータスのボタン（`_update_status_buttons()`）が呼ばれない
    ため（`TestStatusPauseButtonToggle.test_no_reaction_while_the_
    settlement_popup_is_shown`）、通常の押下操作だけでは「表示中に新たに
    ポーズへ入る」経路は無い。設計方針4が挙げる懸念——決算の精算が
    `resume()` を呼ぶと、ユーザーがポーズ中でも動き出してしまう——を
    確かめるため、`_close_settlement_popup()`（test_main_clock.py の
    `TestSettlementPopupFreezesTime`）が凍結解除を直接模すのと同じ考え方で、
    `core._paused` を直接立てて「決算の表示と同時にポーズが効いている」
    状態を作る（実際の押下だけでは辿り着けない組み合わせを、実装の不変
    条件として確かめる防御的なテスト）"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 決算ポップアップ内「o」ボタンの中央の画面座標
    # （TestSettlementPopupSettlement.BUTTON_POS と同じ式）
    BUTTON_POS = (
        GameCore.SETTLEMENT_POPUP_X
        + GameCore.SETTLEMENT_POPUP_PAD
        + GameCore.SETTLEMENT_POPUP_BTN_W // 2,
        GameCore.SETTLEMENT_POPUP_Y
        + GameCore.SETTLEMENT_POPUP_PAD
        + 3 * GameCore.SETTLEMENT_POPUP_LINE_H
        + GameCore.SETTLEMENT_POPUP_RULE_TEXT_GAP
        + GameCore.SETTLEMENT_POPUP_PAD
        + GameCore.SETTLEMENT_POPUP_BTN_H // 2,
    )

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔の経過中に売上発生間隔が満了し得るため、抽選先を固定して
        # 無関係な失敗を避ける（TestSettlementPopupSettlement と同じ理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )
        # 資金不足時の売却（ID-016）の抽選先も固定する
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _press_pause_button(self, core):
        """ポーズボタンの矩形の中心を1回押して離す"""
        x, y, w, h = self._expected_status_pause_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def _core_with_settlement_popup_expired_while_paused(self):
        """プレイヤー所有店舗を1軒（実際の建設操作で）設置し、決算タイマーを
        実際に満了させて決算ポップアップを表示状態（凍結済み）にしたうえで、
        `core._paused` を直接立てて返す（クラス docstring の「作り方」を
        参照）"""
        core = GameCore()
        self._press_plot_and_o_button(core, self.PLAYER_COL, self.PLAYER_ROW)
        self._release(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )
        core._paused = True  # pylint: disable=W0212
        return core

    def test_field_operations_are_possible_while_paused(self):
        """ポーズ中でも区画選択ポップアップの表示・建設が実行できること
        （設計方針・要件どおり。ポーズが止めるのは時間経過のみで、
        フィールド操作は抑止しない）"""
        core = GameCore()
        self._press_pause_button(core)
        money_before = core._money  # pylint: disable=W0212
        self._press_plot_and_o_button(core, self.PLAYER_COL, self.PLAYER_ROW)
        self._release(core)
        self.assertEqual(
            [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
            [
                (col, row, Owner(owner))
                for col, row, owner, _, _ in core._field.get_save_data()  # pylint: disable=W0212
            ],
        )
        self.assertEqual(
            money_before - Shop.BUILD_COST, core._money  # pylint: disable=W0212
        )

    def test_settling_the_tax_does_not_resume_the_timers_while_paused(self):
        """決算ポップアップの精算（`_settle_tax()`）を実行しても、ポーズ中
        （`core._paused` が真）であれば凍結が解けないこと。精算そのもの
        （税額の減算・資金不足時の売却）は通常どおり実行されるが、その後
        いくら時間を進めても保存・他店建設・売上・決算のいずれも進まない
        ことで確認する（精算が成立するケース・資金不足でゲームオーバーに
        なるケースの両方を subTest で確認する）"""
        test_cases = [
            ("資金が足りる", None),
            ("資金が足りずゲームオーバーになる", -10 * GameCore.INITIAL_MONEY),
        ]
        for case_name, money_override in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_settlement_popup_expired_while_paused()
                if money_override is not None:
                    core._money = money_override  # pylint: disable=W0212
                self._press(core, self.BUTTON_POS)
                self._release(core)
                shops_after_settle = (
                    core._field.get_save_data()  # pylint: disable=W0212
                )
                money_after_settle = core._money  # pylint: disable=W0212
                self.mock_store.save.reset_mock()
                self._advance_ms(
                    max(
                        GameCore.NPC_GROWTH_INTERVAL_MS,
                        GameCore.SALES_INTERVAL_MS,
                        GameCore.SAVE_INTERVAL_MS,
                        GameCore.SETTLEMENT_INTERVAL_MS,
                    )
                    * 3
                )
                core.update()
                self.assertEqual(
                    shops_after_settle,
                    core._field.get_save_data(),  # pylint: disable=W0212
                )
                self.assertEqual(
                    money_after_settle, core._money  # pylint: disable=W0212
                )
                self.mock_store.save.assert_not_called()
                self.assertEqual(
                    SettlementPopupState.NONE,
                    core._settlement_popup_state,  # pylint: disable=W0212
                )
