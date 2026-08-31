"""建設・増資・買収

押下を起点に、盤面・資金が実際に変化することを検証する（建設・増資・
買収と、それぞれの資金不足・規模上限による失敗）。同じ「o押下」を起点に
しても、ポップアップの開閉そのものを検証するものは popup 側に分類される
（分類ルール1）。

分類ルール（test/test_main.py の分割時に定めた3条）:
1. 同じ「o押下」が起点でも、検証対象がポップアップの開閉なら popup、
   盤面・資金の変化なら shop_action
2. 保存のテストは「いつ保存するか」と「何が保存されるか」で分ける。
   前者（仕組み）は save、後者のうちタイマー固有の状態遷移を伴うものは clock
3. 描画のテストは、発生契機が時間経過なら clock
   （draw は操作・状態から直接決まる描画のみ）

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

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import GameCore  # pylint: disable=C0413
from field import Owner, Shop  # pylint: disable=C0413,E0401
from test_main_tools import TestParent  # pylint: disable=C0413,E0401


class TestBuildShop(TestParent):
    """空き区画の「o」押下による建設（TDD サイクル2）の振る舞いテスト。

    建設の結果は内部変数ではなく**画面に出るもの**で確認する。
      ・区画がプレイヤー所有・最小規模の店舗になった → フィールドの店舗画像
      ・資金が設置費用ぶん減った → ステータス領域の資金テキスト
      ・資産価値が設置費用になった → 建設した区画を**再選択**したポップアップの
        資産価値の行（あわせて費用の行が増資費用へ、売上額の行が売上額へ
        変わることも、_expected_popup_calls() の既定値が owner から導かれる
        ことで同じ1回の描画で確認される）
    「建設されたのは選択中の1区画だけ」であることは、描画呼び出し列の
    全件一致（他の区画の店舗画像が1件も現れない）が担保する"""

    # 建設の対象にする空き区画（画面左半分 → ポップアップは右下に表示される）
    BUILD_COL = 0
    BUILD_ROW = 2
    # 2軒目を建てる区画（1軒目とは別の区画であることだけが条件）
    SECOND_COL = 0
    SECOND_ROW = 4

    def _make_modal_core(self, col, row, core=None):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        戻り値は (core, 押下位置)。core を渡すと既存の core に対して選択だけを
        行う（続けて2軒目を建てるフレーム列を組み立てるため）"""
        if core is None:
            core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_popup_button(self, core, pos, index):
        """MODAL 状態のポップアップの index 番目のボタン（0: 「o」, 1: 「x」）の
        中心を押下する。ポップアップ原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _build_at(self, core, col, row):
        """区画 (col, row) を選択して「o」を押し、建設まで進めたうえで押下を
        解除する（次の操作を始められる状態にする）。戻り値は選択に使った押下位置"""
        core, pos = self._make_modal_core(col, row, core=core)
        self._press_popup_button(core, pos, 0)
        self._release(core)
        return pos

    def test_o_button_press_builds_player_shop_and_spends_money(self):
        """空き区画を選んで「o」を押すと、その区画にプレイヤー所有・最小規模の
        店舗が描かれ、資金が設置費用ぶん減ること（建設されるのは選択中の1
        区画だけであることは全件一致が担保する）。実行後もポップアップは
        閉じずに残り（ID-022 決定1）、残り資金（100）は増資費用（150）に
        満たないため「o」は無効表示になる"""
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, 0)
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

    def test_built_shop_shows_installation_cost_as_value_when_reselected(self):
        """建設した区画を再度選択すると、ポップアップの資産価値の行が設置費用
        （Shop.BUILD_COST）になること。あわせて費用の行が増資費用
        （Shop.INVEST_COST）へ、売上額の行が設置直後（規模1）の売上額
        （Shop.SALES_AMOUNT × 2^0 = Shop.SALES_AMOUNT。ID-010 以降は規模から
        導出される値だが、規模1ではこの値と一致する）へ変わること
        （_expected_popup_calls() が owner=PLAYER から導く既定値）も
        同じ1回の描画で確認する。建設直後の残り資金（GameCore.INITIAL_MONEY
        = 200。ID-028 で引き下げ後 − Shop.BUILD_COST = 100 → 100）では
        増資費用（Shop.INVEST_COST = 150）を賄えないため、「o」ボタンは
        無効表示になる（o_enabled=False）"""
        core = GameCore()
        pos = self._build_at(core, self.BUILD_COL, self.BUILD_ROW)
        self._press(core, pos)
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

    def test_x_button_press_does_not_build(self):
        """空き区画を選んで「x」を押した場合は建設されず、資金も変わらないこと
        （「x」はキャンセルであり、実行に結び付かない）"""
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, 1)
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_second_build_adds_another_shop_and_spends_money_again(self):
        """続けて別の空き区画へ建設すると、2軒とも描かれ、資金が設置費用の
        2軒ぶん減ること（建設が1回きりで止まらず、既に建てた区画が
        上書きされないこと）。実行後もポップアップは閉じずに残るため
        （ID-022 決定1）、`_build_at()` を2回呼んだ後も2軒目のポップアップが
        開いたまま——`_build_at()` 内の押下・押下解除が新しい区画への
        選択の切り替え（ID-021）としてそのまま働くため、1軒目のポップアップの
        「閉じ忘れ」を気にする必要はない。残り資金（0）は増資費用（150）に
        満たないため「o」は無効表示になる"""
        core = GameCore()
        self._build_at(core, self.BUILD_COL, self.BUILD_ROW)
        second_pos = self._build_at(core, self.SECOND_COL, self.SECOND_ROW)
        self._draw(core)
        expected = self._expected_field_calls(
            [
                (self.BUILD_COL, self.BUILD_ROW, Owner.PLAYER),
                (self.SECOND_COL, self.SECOND_ROW, Owner.PLAYER),
            ],
            money=GameCore.INITIAL_MONEY - 2 * Shop.BUILD_COST,
            shop_count=2,
            tax=self._expected_tax([Shop.BUILD_COST, Shop.BUILD_COST]),
        ) + self._expected_selection_and_popup_calls(
            second_pos, owner=Owner.PLAYER, value=Shop.BUILD_COST, o_enabled=False
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestBuildShopInsufficientFunds(TestParent):
    """資金不足時に「o」が無効になること（押下判定＝TDD サイクル3／表示＝サイクル4）の
    振る舞いテスト。

    無効なのは選択中の区画が**空き区画かつ資金が設置費用未満**のときだけで、
    押下判定そのものを通さないためポップアップは MODAL のまま残る（CLOSING へ
    遷移しない）。そのとき「o」は塗りつぶされず（draw_rect を呼ばず）、
    ポップアップ外周と同じ色（POPUP_BTN_DISABLED_COL）の枠線だけで描かれる。
    **押下判定と表示は同じ述語から導かれる**ため、両者は同じ資金・同じ区画の
    1 つのシナリオで併せて検証する（描画呼び出し列の全件一致が、無効表示・
    「x」が常に塗りつぶしであること・文字とボタン矩形が有効無効で変わらない
    ことを同時に担保する）。
    資金の与え方は保存データからの復元（load() の戻り値の
    money）を使い、内部変数を直接書き換えない。
    「x」（index 1）は _update_popup() の資金判定（index ==
    POPUP_BTN_INDEX_O のときだけ働く）の対象外で、資金によらず常に有効で
    あることは TestPopupButtonPress.test_x_button_press_closes_popup が
    既に固定しているため、本クラスでは重ねて検証しない（下位／既存のテストで
    検証済みのケースを再テストしない。doc/guides/tdd_practices.md
    「テストの冗長性を排除する」）。
    NPC所有店舗（買収の対象）が資金不足で無効になることは TestBuyoutShopInsufficientFunds
    が検証するため、本クラスでは扱わない（ID-009 まで NPC所有店舗の「o」は
    買収の可否判定が未定義で常に有効だったが、本タスクからは資金不足の
    区画状態の1つとして統一される）"""

    # 建設の対象にする空き区画（画面左半分 → ポップアップは右下に表示される）
    BUILD_COL = 0
    BUILD_ROW = 2

    def _make_modal_core(self, col, row):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        戻り値は (core, 押下位置)"""
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する。ポップアップ
        原点 x は選択を決めた押下位置 pos から導く。本クラスは「o」しか
        押下しない（「x」は TestPopupButtonPress が担うため index を引数に
        取る一般形にしない）"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_o_button_press_with_insufficient_funds_does_not_build(self):
        """資金が設置費用未満のとき、空き区画を選んで「o」の領域を押しても
        店舗は描かれず、資金も変わらず、ポップアップは MODAL のまま（選択枠・
        ポップアップとも描かれ続ける）こと"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": Shop.BUILD_COST - 1,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = self._expected_field_calls(
            money=Shop.BUILD_COST - 1
        ) + self._expected_selection_and_popup_calls(pos, o_enabled=False)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_o_button_press_with_exact_funds_builds_shop(self):
        """境界: 資金がちょうど設置費用のときは建設できること（資金は 0 になる）。
        実行後もポップアップは閉じずに残り（ID-022 決定1）、資金が尽きたため
        「o」は無効表示になる"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": Shop.BUILD_COST,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.BUILD_COL, self.BUILD_ROW, Owner.PLAYER)],
            money=0,
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


class TestInvestShop(TestParent):
    """プレイヤー所有店舗の「o」押下による増資（TDD サイクル2）の振る舞いテスト。

    増資の結果は内部変数ではなく**画面に出るもの**で確認する（TestBuildShop と
    同じ考え方）。
      ・店舗規模が1段階上がった → フィールドの店舗画像の転送元（規模+1）
      ・資金が増資費用ぶん減った → ステータス領域の資金テキスト
      ・資産価値へ増資費用が加算された → 増資した区画を**再選択**したポップアップの
        資産価値の行（あわせて費用の行が次の規模の増資費用へ変わることも、
        _expected_popup_calls() の既定値が owner・scale から導かれることで
        同じ1回の描画で確認される）
    「増資されたのは選択中の1区画だけ」であることは、描画呼び出し列の
    全件一致（他の区画の店舗規模が変わっていない）が担保する"""

    # 増資の対象にする区画（画面左半分 → ポップアップは右下に表示される）
    INVEST_COL = 0
    INVEST_ROW = 2
    # 増資しない別の店舗を置く区画（1軒目とは別の区画であることだけが条件）
    OTHER_COL = 0
    OTHER_ROW = 4

    def _make_modal_core(self, col, row, core=None):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        戻り値は (core, 押下位置)。core を渡すと既存の core に対して選択だけを
        行う"""
        if core is None:
            core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_popup_button(self, core, pos, index):
        """MODAL 状態のポップアップの index 番目のボタン（0: 「o」, 1: 「x」）の
        中心を押下する。ポップアップ原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_invested_shop_shows_updated_cost_and_value_when_reselected(self):
        """増資した区画を再度選択すると、ポップアップの資産価値の行が
        Shop.BUILD_COST + Shop.INVEST_COST になり、費用の行が次の規模の増資費用
        （Shop.INVEST_COST × 2）になること（_expected_popup_calls() が
        owner=PLAYER・scale=2 から導く既定値）。増資直後の残り資金
        （GameCore.INITIAL_MONEY = 200。ID-028 で引き下げ後 − Shop.INVEST_COST
        = 150 → 50）では次の規模の増資費用（300）を賄えないため、「o」ボタンは
        無効表示になる（o_enabled=False）"""
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER
        )
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, core=core)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self._release(core)
        self._press(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)], scale=2
            )
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

    def test_invest_does_not_affect_other_shops(self):
        """プレイヤー所有・規模1の店舗を選んで「o」を押すと、その区画が規模2の
        店舗画像で描かれ、資金が増資費用（Shop.INVEST_COST）ぶん減ること。
        増資は選択中の区画だけに作用し、他の区画にあるプレイヤー所有店舗の
        規模・資産価値は変わらないこと（1区画だけの検証では「増資した」のか
        「たまたま1軒しかない場を全部描いた」のか区別できないため、2軒目を
        置いて確認する）。実行後もポップアップは閉じずに残り（ID-022 決定1）、
        残り資金（50）は次の規模の増資費用（300）に満たないため「o」は
        無効表示になる"""
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER
        )
        core._field.set_shop(  # pylint: disable=W0212
            self.OTHER_COL, self.OTHER_ROW, Owner.PLAYER
        )
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, core=core)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self._release(core)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=GameCore.INITIAL_MONEY - Shop.INVEST_COST,
                shop_count=2,
                tax=self._expected_tax(
                    [Shop.BUILD_COST + Shop.INVEST_COST, Shop.BUILD_COST]
                ),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)], scale=2
            )
            + self._expected_shop_calls(
                [(self.OTHER_COL, self.OTHER_ROW, Owner.PLAYER)], scale=1
            )
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

    def test_x_button_press_does_not_invest(self):
        """プレイヤー所有店舗を選んで「x」を押した場合は増資されず、資金も
        変わらないこと（「x」はキャンセルであり、実行に結び付かない）"""
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER
        )
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, core=core)
        self._press_popup_button(core, pos, 1)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                shop_count=1, tax=self._expected_tax([Shop.BUILD_COST])
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)]
            )
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestInvestShopInsufficientFunds(TestParent):
    """資金不足時に増資の「o」が無効になること（押下判定＝TDD サイクル3／表示＝
    同じサイクルで固定する。理由は TestBuildShopInsufficientFunds のクラス
    docstring と同じ）の振る舞いテスト。

    無効なのは選択中の区画が**プレイヤー所有店舗かつ資金が増資費用未満**の
    ときだけで、押下判定そのものを通さないためポップアップは MODAL のまま
    残る（CLOSING へ遷移しない）。そのとき「o」は塗りつぶされず、ポップアップ
    外周と同じ色（POPUP_BTN_DISABLED_COL）の枠線だけで描かれる。
    増資費用は店舗規模に応じて指数的に増加する（Shop.INVEST_COST ×
    2^(規模-1)）ため、規模1（費用150）・規模5（費用2,400）の2通りで確認し、
    判定が固定値ではなく規模由来の費用を読んでいることを固定する。
    資金・店舗規模はいずれも保存データからの復元（load() の戻り値）で与え、
    内部変数を直接書き換えない。
    NPC所有店舗の「o」が資金不足で無効になることは TestBuyoutShopInsufficientFunds
    が固定するため、本クラスでは重ねて検証しない。「x」が資金によらず常に
    有効であることは TestPopupButtonPress.test_x_button_press_closes_popup が
    固定済みのため、同じく重ねて検証しない"""

    INVEST_COL = 0
    INVEST_ROW = 2

    def _make_modal_core(self, col, row, scale, money, value=Shop.BUILD_COST):
        """保存データから、指定した店舗規模・資産価値のプレイヤー所有店舗と
        資金を持つ core を作り、区画を押して離し、MODAL 状態のポップアップを
        用意する。戻り値は (core, 押下位置)。資金・店舗規模・資産価値は
        いずれも保存データからの復元（load() の戻り値）で与え、内部変数を
        直接書き換えない"""
        self.mock_store.load.return_value = {
            "shops": [[col, row, Owner.PLAYER.value, scale, value]],
            "money": money,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する。ポップアップ
        原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_o_button_press_with_insufficient_funds_does_not_invest(self):
        """資金が増資費用未満のとき、プレイヤー所有店舗を選んで「o」の領域を
        押しても店舗規模・資産価値は変わらず、資金も変わらず、ポップアップは
        MODAL のまま（選択枠・ポップアップとも描かれ続ける）こと。規模1
        （費用150）・規模5（費用2,400）の2通りで確認する"""
        for scale in (1, 5):
            with self.subTest(scale=scale):
                cost = Shop.INVEST_COST * 2 ** (scale - 1)
                value = Shop.BUILD_COST + cost
                money = cost - 1
                core, pos = self._make_modal_core(
                    self.INVEST_COL, self.INVEST_ROW, scale, money, value=value
                )
                self._press_o_button(core, pos)
                self._draw(core)
                expected = (
                    self._expected_status_calls(
                        money=money, shop_count=1, tax=self._expected_tax([value])
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls(
                        [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)],
                        scale=scale,
                    )
                ) + self._expected_selection_and_popup_calls(
                    pos,
                    owner=Owner.PLAYER,
                    scale=scale,
                    value=value,
                    o_enabled=False,
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_o_button_press_with_exact_funds_invests_shop(self):
        """境界: 資金がちょうど増資費用のときは増資できること（資金は0になる）。
        実行後もポップアップは閉じずに残り（ID-022 決定1）、資金が尽きたため
        「o」は無効表示になる"""
        money = Shop.INVEST_COST
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, 1, money)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=0,
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST]),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)], scale=2
            )
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


class TestInvestShopScaleLimit(TestParent):
    """店舗規模が上限（GameCore.SHOP_SCALE_MAX）に達した店舗の「o」が無効に
    なること（TDD サイクル4）の振る舞いテスト。

    無効なのは選択中の区画が**プレイヤー所有店舗かつ店舗規模が上限**の
    ときだけで、押下判定そのものを通さないためポップアップは MODAL のまま
    残る（CLOSING へ遷移しない）。TestInvestShopInsufficientFunds と区別する
    ため、いずれのケースも資金は増資費用ちょうど（資金は足りている）を与え、
    増資できない/できるの結果が規模の条件だけに由来することを切り分ける。
    境界として規模9（上限の1つ手前）では増資でき規模10になることもあわせて
    確認する。
    押下判定・無効表示が同じ述語（_is_popup_button_enabled() 経由）を読む
    ことは TestInvestShopInsufficientFunds が既に固定しているため、本クラス
    では規模による分岐が加わったことだけを確認する"""

    INVEST_COL = 0
    INVEST_ROW = 2

    def _make_modal_core(self, col, row, scale):
        """保存データから、指定した店舗規模のプレイヤー所有店舗と、その規模の
        増資費用ちょうどの資金を持つ core を作り、区画を押して離し、MODAL
        状態のポップアップを用意する。戻り値は (core, 押下位置)。資金・
        店舗規模・資産価値はいずれも保存データからの復元（load() の戻り値）で
        与え、内部変数を直接書き換えない"""
        cost = Shop.INVEST_COST * 2 ** (scale - 1)
        value = Shop.BUILD_COST + cost
        self.mock_store.load.return_value = {
            "shops": [[col, row, Owner.PLAYER.value, scale, value]],
            "money": cost,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する。ポップアップ
        原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_o_button_press_at_scale_max_does_not_invest(self):
        """店舗規模が上限（10）のとき、増資費用ちょうどの資金があっても「o」の
        領域を押しても店舗規模・資産価値は変わらず、資金も変わらず、ポップアップは
        MODAL のまま（選択枠・ポップアップとも描かれ続ける）こと"""
        scale = GameCore.SHOP_SCALE_MAX
        cost = Shop.INVEST_COST * 2 ** (scale - 1)
        value = Shop.BUILD_COST + cost
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, scale)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=cost, shop_count=1, tax=self._expected_tax([value])
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)], scale=scale
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=scale,
            value=value,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_o_button_press_at_scale_just_below_max_invests_shop(self):
        """境界: 規模が上限の1つ手前（9）のときは、資金が増資費用ちょうどでも
        増資でき、規模が10になること。実行後もポップアップは閉じずに残り
        （ID-022 決定1）、規模が上限に達したため「o」は無効表示になる"""
        scale = GameCore.SHOP_SCALE_MAX - 1
        cost = Shop.INVEST_COST * 2 ** (scale - 1)
        value_before_invest = Shop.BUILD_COST + cost
        # 増資後の資産価値は、規模10の店舗を最初から復元したときの値
        # （TestInvestShopScaleLimit.test_o_button_press_at_scale_max_does_not_invest
        # の value）と一致する（増資費用の積み上げ方が同じ式のため）
        value_after_invest = value_before_invest + cost
        core, pos = self._make_modal_core(self.INVEST_COL, self.INVEST_ROW, scale)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=0, shop_count=1, tax=self._expected_tax([value_after_invest])
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.INVEST_COL, self.INVEST_ROW, Owner.PLAYER)], scale=scale + 1
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=scale + 1,
            value=value_after_invest,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestBuyoutShop(TestParent):
    """NPC所有店舗の「o」押下による買収（TDD サイクル2）の振る舞いテスト。

    買収の結果は内部変数ではなく**画面に出るもの**で確認する（TestBuildShop /
    TestInvestShop と同じ考え方）。
      ・所有者がプレイヤーへ変わった → フィールドの店舗画像がプレイヤー所有の段で描かれる
      ・店舗規模が維持された → 転送元 u（規模由来）が買収前と同じ
      ・資金が買収費用（資産価値 × Shop.BUYOUT_RATE）ぶん減った → ステータス
        領域の資金テキスト
      ・資産価値が維持された → 買収した区画を**再選択**したポップアップの
        資産価値の行が買収前と同じ（あわせて費用の行が増資費用へ変わることも、
        _expected_popup_calls() の既定値が owner=PLAYER・scale から導かれる
        ことで同じ1回の描画で確認される）
    「買収されたのは選択中の1区画だけ」であることは、描画呼び出し列の
    全件一致（他の区画の所有者・規模・資産価値が変わっていない）が担保する。

    規模・資産価値は保存データからの復元（load() の戻り値）で与える
    （建設・増資を積み重ねると、失敗時に「買収処理が悪いのか、その前段が
    悪いのか」が切り分けられなくなるため。ID-007 と同じ理由）。
    資産価値は規模1（100）とは異なる規模3相当（550）を使う（買収費用が
    偶然 200 になり、資産価値ベースの式へ変えなくても通ってしまう罠を
    避けるため）。

    空き区画の「o」が引き続き建設に結び付くことは TestBuildShop が、
    プレイヤー所有店舗の「o」が引き続き増資に結び付くことは TestInvestShop が
    それぞれ固定済みのため、本クラスでは重ねて検証しない。
    「x」を押した場合に買収されないことも、本クラスでは検証しない。「x」の
    処理（_update_popup()）は区画の状態を一切読まず（index ==
    POPUP_BTN_INDEX_O の分岐にすら入らない）、区画の所有者・規模・資産価値・
    資金のいずれにも依存しない1本のコードパスのため、NPC所有店舗を対象に
    別の数値で再検証しても新しい経路を捕まえない。NPC所有店舗を対象にした
    「x」の判定範囲内の押下で所有者・資金が変わらないことは
    TestPopupButtonPress.test_button_hit_area_is_half_open_interval が
    境界値（8ケース）で既に固定している"""

    BUYOUT_COL = 0
    BUYOUT_ROW = 2
    BUYOUT_SCALE = 3
    # BUILD_COST + INVEST_COST * (2^(3-1) - 1) = 100 + 150 * 3
    BUYOUT_VALUE = 550
    # 買収の影響を受けない別のNPC所有店舗を置く区画
    OTHER_COL = 0
    OTHER_ROW = 4
    OTHER_SCALE = 2
    # BUILD_COST + INVEST_COST * (2^(2-1) - 1) = 100 + 150 * 1
    OTHER_VALUE = 250
    # 買収費用（550 * 2 = 1,100）を賄い、買収後もなお増資費用（600）を賄える
    # だけの資金。GameCore.INITIAL_MONEY（1,000）では買収費用を賄えないため
    # 使わない
    BUYOUT_MONEY = 5000

    def _make_modal_core(self, scale, value, extra_shops=()):
        """保存データから、BUYOUT_COL・BUYOUT_ROW に指定した店舗規模・資産価値の
        NPC所有店舗と BUYOUT_MONEY（買収費用と買収後の増資費用の双方を賄える
        資金）を持つ core を作り、区画を押して離し、MODAL 状態のポップアップを
        用意する。戻り値は (core, 押下位置)。資金・店舗規模・資産価値はいずれも
        保存データからの復元（load() の戻り値）で与え、内部変数を直接書き換え
        ない。extra_shops は他の区画にも店舗を置く場合の
        [col, row, owner_value, scale, value] のリスト。本クラスは常に
        BUYOUT_COL・BUYOUT_ROW を対象にするため、区画を引数に取らない
        （現れない呼び手のための一般化はしない）"""
        self.mock_store.load.return_value = {
            "shops": [[self.BUYOUT_COL, self.BUYOUT_ROW, Owner.NPC.value, scale, value]]
            + list(extra_shops),
            "money": self.BUYOUT_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(self.BUYOUT_COL, self.BUYOUT_ROW)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する。ポップアップ
        原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_bought_out_shop_shows_same_value_and_invest_cost_when_reselected(self):
        """買収した区画を再度選択すると、ポップアップの資産価値の行が買収前と
        同じ（550）、費用の行が増資費用（Shop.INVEST_COST × 2^2 = 600）へ
        変わること（_expected_popup_calls() が owner=PLAYER・scale から導く
        既定値）"""
        cost = self.BUYOUT_VALUE * Shop.BUYOUT_RATE
        core, pos = self._make_modal_core(self.BUYOUT_SCALE, self.BUYOUT_VALUE)
        self._press_o_button(core, pos)
        self._release(core)
        self._press(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=self.BUYOUT_MONEY - cost,
                shop_count=1,
                tax=self._expected_tax([self.BUYOUT_VALUE]),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.BUYOUT_COL, self.BUYOUT_ROW, Owner.PLAYER)],
                scale=self.BUYOUT_SCALE,
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=self.BUYOUT_SCALE,
            value=self.BUYOUT_VALUE,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_buyout_does_not_affect_other_shops(self):
        """NPC所有店舗を選んで「o」を押すと、その区画がプレイヤー所有・同じ
        規模の店舗画像で描かれ、資金が買収費用（資産価値 × Shop.BUYOUT_RATE）
        ぶん減ること。買収は選択中の区画だけに作用し、他区画のNPC所有店舗の
        所有者・規模・資産価値は変わらないこと（1区画だけの検証では「買収した」
        のか「たまたま1軒しかない場を全部描いた」のか区別できないため、2軒目を
        置いて確認する）。実行後もポップアップは閉じずに残り（ID-022 決定1）、
        BUYOUT_MONEY（5000）は買収費用（1,100）と買収後の増資費用（規模3 →
        4。Shop.INVEST_COST × 2^2 = 600）の両方を賄えるため「o」は有効表示の
        まま"""
        cost = self.BUYOUT_VALUE * Shop.BUYOUT_RATE
        core, pos = self._make_modal_core(
            self.BUYOUT_SCALE,
            self.BUYOUT_VALUE,
            extra_shops=[
                [
                    self.OTHER_COL,
                    self.OTHER_ROW,
                    Owner.NPC.value,
                    self.OTHER_SCALE,
                    self.OTHER_VALUE,
                ]
            ],
        )
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=self.BUYOUT_MONEY - cost,
                shop_count=1,
                tax=self._expected_tax(
                    [self.BUYOUT_VALUE], other_values=[self.OTHER_VALUE]
                ),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.BUYOUT_COL, self.BUYOUT_ROW, Owner.PLAYER)],
                scale=self.BUYOUT_SCALE,
            )
            + self._expected_shop_calls(
                [(self.OTHER_COL, self.OTHER_ROW, Owner.NPC)], scale=self.OTHER_SCALE
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=self.BUYOUT_SCALE,
            value=self.BUYOUT_VALUE,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestBuyoutShopInsufficientFunds(TestParent):
    """資金不足時に買収の「o」が無効になること（TDD サイクル3）の振る舞いテスト。

    無効なのは選択中の区画が**NPC所有店舗かつ資金が買収費用未満**の
    ときだけで、押下判定そのものを通さないためポップアップは MODAL のまま
    残る（CLOSING へ遷移しない）。そのとき「o」は塗りつぶされず、ポップアップ
    外周と同じ色（POPUP_BTN_DISABLED_COL）の枠線だけで描かれる（理由は
    TestBuildShopInsufficientFunds のクラス docstring と同じ）。
    買収費用は資産価値の Shop.BUYOUT_RATE 倍のため、規模1（資産価値
    Shop.BUILD_COST）とは異なる規模3・資産価値550の店舗で確認する（買収費用が
    偶然 200 になり、資産価値ベースの式へ変えなくても通ってしまう罠を避ける
    ため。TestBuyoutShop と同じ理由）。
    資金・店舗規模・資産価値はいずれも保存データからの復元（load() の
    戻り値）で与え、内部変数を直接書き換えない。
    空き区画・プレイヤー所有店舗の「o」が資金不足で無効になることは
    TestBuildShopInsufficientFunds / TestInvestShopInsufficientFunds が
    固定済みのため、本クラスでは重ねて検証しない。「x」が資金によらず常に
    有効であることは TestPopupButtonPress.test_x_button_press_closes_popup が
    固定済みのため、同じく重ねて検証しない"""

    BUYOUT_COL = 0
    BUYOUT_ROW = 2
    BUYOUT_SCALE = 3
    # BUILD_COST + INVEST_COST * (2^(3-1) - 1) = 100 + 150 * 3
    BUYOUT_VALUE = 550

    def _make_modal_core(self, money):
        """保存データから、BUYOUT_COL・BUYOUT_ROW に規模3・資産価値550の
        NPC所有店舗と指定した資金を持つ core を作り、区画を押して離し、
        MODAL 状態のポップアップを用意する。戻り値は (core, 押下位置)。
        資金・店舗規模・資産価値はいずれも保存データからの復元（load() の
        戻り値）で与え、内部変数を直接書き換えない"""
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.BUYOUT_COL,
                    self.BUYOUT_ROW,
                    Owner.NPC.value,
                    self.BUYOUT_SCALE,
                    self.BUYOUT_VALUE,
                ]
            ],
            "money": money,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        pos = self._plot_center_pos(self.BUYOUT_COL, self.BUYOUT_ROW)
        self._press(core, pos)
        self._release(core)
        return core, pos

    def _press_o_button(self, core, pos):
        """MODAL 状態のポップアップの「o」ボタンの中心を押下する。ポップアップ
        原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_o_button_press_with_insufficient_funds_does_not_buyout(self):
        """資金が買収費用未満のとき、NPC所有店舗を選んで「o」の領域を押しても
        店舗の所有者・規模・資産価値は変わらず、資金も変わらず、ポップアップは
        MODAL のまま（選択枠・ポップアップとも描かれ続ける）こと"""
        cost = self.BUYOUT_VALUE * Shop.BUYOUT_RATE
        money = cost - 1
        core, pos = self._make_modal_core(money)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(money=money)
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.BUYOUT_COL, self.BUYOUT_ROW, Owner.NPC)],
                scale=self.BUYOUT_SCALE,
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.NPC,
            scale=self.BUYOUT_SCALE,
            value=self.BUYOUT_VALUE,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_o_button_press_with_exact_funds_buys_out_shop(self):
        """境界: 資金がちょうど買収費用のときは買収できること（資金は0になる）。
        実行後もポップアップは閉じずに残り（ID-022 決定1）、資金が尽きたため
        「o」は無効表示になる"""
        cost = self.BUYOUT_VALUE * Shop.BUYOUT_RATE
        core, pos = self._make_modal_core(cost)
        self._press_o_button(core, pos)
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=0, shop_count=1, tax=self._expected_tax([self.BUYOUT_VALUE])
            )
            + self._expected_road_calls()
            + self._expected_shop_calls(
                [(self.BUYOUT_COL, self.BUYOUT_ROW, Owner.PLAYER)],
                scale=self.BUYOUT_SCALE,
            )
        ) + self._expected_selection_and_popup_calls(
            pos,
            owner=Owner.PLAYER,
            scale=self.BUYOUT_SCALE,
            value=self.BUYOUT_VALUE,
            o_enabled=False,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
