"""時間契機（他店建設・売上・囲み・各タイマーの残り時間の保存）

時間経過を契機とする振る舞い（他店建設・売上発生の各間隔タイマーと、
発生契機が時間経過の描画である売上の囲み）、およびタイマー固有の状態
遷移を伴う保存・復元（未開始なら None で保存し、復元後は続きから経過
する）を検証する。

分類ルール（test/test_main.py の分割時に定めた3条）:
1. 同じ「o押下」が起点でも、検証対象がポップアップの開閉なら popup、
   盤面・資金の変化なら shop_action
2. 保存のテストは「いつ保存するか」と「何が保存されるか」で分ける。
   前者（仕組み）は save、後者のうちタイマー固有の状態遷移を伴うものは clock
3. 描画のテストは、発生契機が時間経過なら clock
   （draw は操作・状態から直接決まる描画のみ）

境界に立つクラスがこのファイルにある理由:
- TestSalesFrame: 囲みが付く契機が売上の抽選そのもので、「囲みが3秒
  ごとに移動する」「NPC所有が当たると囲みだけ付く」の検証が
  TestSalesInterval と地続きのため、draw ではなく clock へ含める
  （分類ルール3）
- TestNpcGrowthClockSaveLoad / TestSalesClockSaveLoad / TestSettlementClockSaveLoad:
  検証しているのは「未開始なら None で保存し、復元後は続きから経過する」
  というタイマー固有の状態遷移であり、ShopClock の振る舞いテストと
  一体のため、save ではなく clock へ含める（分類ルール2）

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
from unittest.mock import patch, MagicMock

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


class TestNpcGrowthInterval(TestParent):
    """他店建設間隔（GameCore.NPC_GROWTH_INTERVAL_MS）の満了によるNPCの成長と、
    その起点（最初のプレイヤー所有店舗が建設された時点。要件 3.2）に関する
    振る舞いのテスト。

    **検証はすべて draw() の描画呼び出し列で行う**（save() へ渡ったデータは
    見ない）。他店建設間隔で起きるのは盤面そのものの変化であり、プレイヤーに
    見えているものと同じ列で確認する。

    **タイマーの発火は Clock.is_up の差し替えではなく、time.perf_counter() を
    固定して時刻そのものを進める形で与える**（test_clock.py と同じ与え方）。
    「起点がどこか」は満了する時刻の違いとしてしか現れず、is_up を差し替えると
    起動を起点にした実装と建設を起点にした実装が区別できなくなるため
    （どちらも「満了させれば成長する」で一致してしまう）。TestParent が既定で
    掛けている Clock.is_up の無効化は、本クラスの間だけ外す。

    本クラスの経過では**売上発生間隔（3秒。他店建設間隔 10 秒より短い）も
    必ず満了する**ため、資金は売上のぶんだけ増える。本クラスの関心は盤面の
    変化であり、資金は「他店建設そのものでは変わらない」ことの確認に留めたい
    ので、売上の抽選は常にプレイヤー所有店舗（規模1）を選ばせ、その売上額を
    期待値へ織り込む（どの店舗が選ばれるかで額が揺れないようにする）。2つの
    間隔が同じ update() で満了しても、抽選が乱数源の別々のメソッドに分かれて
    いるため呼び出し順を数える必要がないことが、ここで実際に効いている"""

    # 起点にするプレイヤー所有店舗の区画（画面左半分 → ポップアップは右下）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    # NPC所有店舗が建つ区画。抽選対象（プレイヤー所有店舗に上下左右で隣接する
    # 空き区画）を Field の列挙順（行昇順→列昇順）に並べた先頭が真上の区画であり、
    # TestParent の乱数源は常にその先頭を選ぶ
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1
    # 保存データから復元する資金（初期資金と区別できる値）
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500
    # 売上の抽選が常に選ぶ区画（setUp で起点のプレイヤー所有店舗に固定する）。
    # 売上が満了したケースでは必ずこの区画が囲まれる
    SALES_PLOT = (PLAYER_COL, PLAYER_ROW)

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる（上記の理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _restored_player_shop_data(self):
        """プレイヤー所有店舗が1軒だけある保存データ。店舗規模・資産価値は
        設置直後と同じ値にして、建設で作った盤面と同じ状態から始める"""
        return {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押して離し、
        「x」で閉じる）で最初の店舗を建設する。**タイマーの起点は「建設された
        時点」のため、Field へ直接店舗を置くのではなく実際の建設の経路を通す**。
        実行後もポップアップは閉じずに残るため（ID-022 決定1）、本ヘルパーの
        関心事（タイマーの起点）にポップアップの内容を混ぜないよう、続けて
        「x」を押して閉じる（TestPopupStaysOpenAfterExecution が確認済みの、
        実行後もキャンセルボタンで閉じられる振る舞い）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        o_x, o_y, o_w, o_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (o_x + o_w // 2, o_y + o_h // 2))
        self._release(core)
        x_x, x_y, x_w, x_h = self._expected_button_rect(popup_x, 1)
        self._press(core, (x_x + x_w // 2, x_y + x_h // 2))
        self._release(core)

    def test_npc_does_not_grow_before_the_first_player_shop_is_built(self):
        """店舗が1軒もない起動直後は、他店建設間隔ぶんの時間が何度過ぎても
        盤面が静止していること（要件 3.2「それ以前は経過しない」）"""
        core = GameCore()
        for _ in range(3):
            self._advance_ms(GameCore.NPC_GROWTH_INTERVAL_MS)
            core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_npc_grows_when_the_interval_elapses_from_the_first_player_shop(self):
        """最初のプレイヤー所有店舗を起点として他店建設間隔が満了したときだけ、
        NPC所有店舗が1軒建つこと。

        起点は「建設された時点」であり、それ以前の経過は持ち越されない
        （建設した直後は満了しておらず、建設から間隔に満たない経過でも建たない）。
        保存データから復元してプレイヤー所有店舗が既にある場合は、起動の時点が
        起点になる（リロードで街の成長が止まったままにならない）"""
        npc_shop = (self.NPC_COL, self.NPC_ROW, Owner.NPC)
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        built_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST
        interval = GameCore.NPC_GROWTH_INTERVAL_MS
        # 経過が売上発生間隔（3秒）に達したケースでは、他店建設とは独立に
        # 売上（規模1のプレイヤー所有店舗）が1回ぶん入る
        sales = Shop.SALES_AMOUNT * 2**0
        # 起動から「プレイヤーが最初の店舗を建設する」までの経過。**間隔より短い
        # 値**にすることが重要で、ここに間隔ぶん以上を置くと、起動を起点にした
        # 実装でも建設の時点でタイマーが一度満了して起点が建設時刻へ揃ってしまい、
        # 正しい実装と区別が付かなくなる。間隔未満にしておけば、起動を起点にした
        # 実装は「建設から間隔に満たない経過」で満了してしまい必ず検出される
        boot_to_build_ms = interval // 2
        # 売上が1度も満了していないケース（経過 0）だけ囲みが無い
        test_cases = [
            (
                "建設した直後は満了していない（建設前の経過は持ち越されない）",
                False,
                0,
                [player_shop],
                built_money,
                None,
            ),
            (
                "建設から間隔に満たない経過では建たない",
                False,
                interval - 1,
                [player_shop],
                built_money + sales,
                self.SALES_PLOT,
            ),
            (
                "建設から間隔ぶん経つとNPC所有店舗が1軒建つ",
                False,
                interval,
                [npc_shop, player_shop],
                built_money + sales,
                self.SALES_PLOT,
            ),
            (
                "復元した店舗があるとき、起動から間隔に満たない経過では建たない",
                True,
                interval - 1,
                [player_shop],
                self.RESTORED_MONEY + sales,
                self.SALES_PLOT,
            ),
            (
                "復元した店舗があるとき、起動から間隔ぶん経つと1軒建つ",
                True,
                interval,
                [npc_shop, player_shop],
                self.RESTORED_MONEY + sales,
                self.SALES_PLOT,
            ),
        ]
        for (
            case_name,
            restored,
            elapsed_ms,
            expected_shops,
            money,
            expected_sales_plot,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                # サブテストをまたいで押下の状態・経過時間が残らないよう、
                # ケースごとに入力を未押下へ戻す（前のケースの建設操作の押下が
                # 残っていると、次のケースでポップアップが追従してしまう）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = (
                    self._restored_player_shop_data() if restored else None
                )
                core = GameCore()
                if not restored:
                    self._advance_ms(boot_to_build_ms)
                    self._build_player_shop(core)
                self._advance_ms(elapsed_ms)
                core.update()
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(
                        expected_shops,
                        money=money,
                        sales_plot=expected_sales_plot,
                        # 決算タイマーは他店建設間隔と同時に起動するため、
                        # 建設・復元からの経過は同じ elapsed_ms（ID-014
                        # サイクル3）。税額は建てたプレイヤー所有店舗
                        # （Shop.BUILD_COST）ぶんのみで、NPC所有店舗が
                        # 育っても変わらない（総額が地価の境界270に届かない）
                        remaining_sec=self._expected_settlement_remaining_sec(
                            elapsed_ms
                        ),
                        shop_count=1,
                        tax=self._expected_tax([Shop.BUILD_COST]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestNpcGrowthTriggersBusinessContinuationCheck(TestParent):
    """他店建設間隔（NPC_GROWTH_INTERVAL_MS）の満了で `grow_npc()` が走った
    直後に、事業継続の判定（プレイヤー所有店舗が0軒 かつ 資金 <
    最小取得費用。要件 3.15）が行われ、成立すればゲームオーバーになる
    ことに関するテスト（ID-024 サイクル024-2）。

    最小取得費用そのものの算出（`Field.min_acquisition_cost()`）は
    test_field.py の `TestFieldMinAcquisitionCost` が担うため、本クラスは
    それを固定値へ差し替え（`TestGameEndPopup._core_with_fixed_tax()` と
    同じ考え方——`Field.total_tax()` を固定するのと対称）、`GameCore` 側の
    判定の境界（決定2）だけを見る（AGENTS.md サブタスクの「テスト設計の
    注意」6）。

    他店建設間隔の発火そのものは `Clock.is_up` を差し替える既存の型
    （`test_main_save.py` の `TestPeriodicSave._make_core()` と同じ）で
    与える。タイマーの起点・周期は `TestNpcGrowthInterval` が確認済みの
    ため、本クラスは「満了したら判定が走る」ことだけに関心を絞る（ただし
    末尾の1件（同じフレームで売上・決算が起きないこと）だけは、`Clock`
    自身の一時停止の仕組みを検証したいため is_up を差し替えず実時間で
    与える——`TestNpcGrowthInterval` と同じ与え方）"""

    # Field.min_acquisition_cost() の固定値（境界を作りやすい値なら何でもよい）
    MIN_COST = 100

    def _make_core(self, money, has_player_shop, npc_growth_up=True):
        """他店建設間隔が満了した直後の GameCore を返す。
        `has_player_shop` が True なら (0, 0)（地域価格倍率は無関係。
        min_acquisition_cost() を固定するため）へプレイヤー所有店舗を
        1軒置く"""
        core = GameCore()
        core._npc_growth_clock.is_up = MagicMock(  # pylint: disable=W0212
            return_value=npc_growth_up
        )
        core._money = money  # pylint: disable=W0212
        patcher_min_cost = patch.object(
            core._field,  # pylint: disable=W0212
            "min_acquisition_cost",
            return_value=self.MIN_COST,
        )
        patcher_min_cost.start()
        self.addCleanup(patcher_min_cost.stop)
        if has_player_shop:
            core._field.set_shop(0, 0, Owner.PLAYER)  # pylint: disable=W0212
        return core

    def test_game_over_when_no_shops_and_money_is_below_the_min_acquisition_cost(
        self,
    ):
        """他店建設間隔が満了して `grow_npc()` が走った直後、プレイヤー所有
        店舗が0軒かつ資金が最小取得費用未満なら、ゲームオーバーポップアップが
        現れること（要件 3.15 の中心。決算の直後と対になるもう一方の契機）"""
        core = self._make_core(money=self.MIN_COST - 1, has_player_shop=False)
        core.update()
        self._draw(core)
        expected = (
            self._expected_field_calls(money=self.MIN_COST - 1)
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

    def test_money_boundary_against_the_min_acquisition_cost(self):
        """資金の境界3点（`<` と `<=` の取り違えを弾く）。0軒の盤面で、
        最小取得費用の1つ下では終了し、ちょうど・1つ上では終了しないこと"""
        test_cases = [
            ("1つ下（終了）", self.MIN_COST - 1, GameEndState.GAME_OVER),
            ("ちょうど（継続）", self.MIN_COST, GameEndState.NONE),
            ("1つ上（継続）", self.MIN_COST + 1, GameEndState.NONE),
        ]
        for case_name, money, expected_state in test_cases:
            with self.subTest(case_name=case_name):
                core = self._make_core(money=money, has_player_shop=False)
                core.update()
                self.assertEqual(
                    expected_state, core._game_end_state  # pylint: disable=W0212
                )

    def test_no_game_over_when_a_player_shop_exists_regardless_of_money(self):
        """プレイヤー所有店舗が1軒以上あれば、資金がいくら最小取得費用を
        下回っていても終了しないこと（要件「1つ以上ある場合はこの判定を
        行わない」。決定2の第1条件が短絡することの確認）"""
        core = self._make_core(money=self.MIN_COST - 1, has_player_shop=True)
        core.update()
        self.assertEqual(
            GameEndState.NONE, core._game_end_state  # pylint: disable=W0212
        )

    def test_sales_and_settlement_do_not_run_in_the_frame_the_game_ends(self):
        """他店建設間隔の満了で事業継続のゲームオーバーが成立したフレームでは、
        同じフレームで満了した売上発生間隔・決算間隔もいずれも起きないこと
        （決定4「_end_game() が4タイマーを pause() するため、同じフレームの
        後続の is_up() はいずれも偽を返す」の根拠を固定する）。

        `Clock.is_up` を差し替えず実時間で3つの間隔をすべて満了させる
        （`Clock.pause()` が実際に効くことを確認したいため。is_up を
        差し替えると pause() の効果がテストへ現れない）。プレイヤー所有
        店舗を一度実際に建設してタイマーを起動させたのち、盤面を空にして
        （`apply_load_data([])`。0軒でもタイマーは動き続ける——ID-016）
        資金を最小取得費用未満にする"""
        self.patcher_clock.stop()
        now = [0.0]
        patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: now[0]
        )
        patcher_perf_counter.start()
        self.addCleanup(patcher_perf_counter.stop)
        core = GameCore()
        core._field.set_shop(0, 0, Owner.PLAYER)  # pylint: disable=W0212
        core._start_shop_clocks()  # pylint: disable=W0212
        core._field.apply_load_data([])  # pylint: disable=W0212
        core._money = self.MIN_COST - 1  # pylint: disable=W0212
        patcher_min_cost = patch.object(
            core._field,  # pylint: disable=W0212
            "min_acquisition_cost",
            return_value=self.MIN_COST,
        )
        patcher_min_cost.start()
        self.addCleanup(patcher_min_cost.stop)
        # 決算間隔（最長。60秒）ぶん進め、他店建設・売上・決算の3間隔を
        # すべて満了させる
        now[0] += GameCore.SETTLEMENT_INTERVAL_MS / 1000
        core.update()
        # TestParent.tearDown() が patcher_clock.stop() を呼べるよう、
        # 検証の前に掛け直しておく（TestNpcGrowthInterval 等と同じ、
        # setUp で外した無効化を対称に戻す作法）
        self.patcher_clock.start()
        self.assertEqual(
            GameEndState.GAME_OVER, core._game_end_state  # pylint: disable=W0212
        )
        # 決算が起きていれば SHOWN へ変わるはずだが、pause() に阻まれ
        # NONE のまま（決算ポップアップが現れない＝精算が実行されない）
        self.assertEqual(
            SettlementPopupState.NONE,
            core._settlement_popup_state,  # pylint: disable=W0212
        )


class TestNpcGrowthClockSaveLoad(TestParent):
    """他店建設間隔の残り時間の保存・復元（TDD サイクル5）に関する振る舞いの
    テスト。サイクル4までは満了したかどうかだけを扱っていたが、本サイクルは
    満了までの残り時間そのものが保存データに含まれ、復元後もその続きから
    経過することを固定する。

    タイマーの発火は TestNpcGrowthInterval と同じく、Clock.is_up の
    差し替えではなく time.perf_counter() を固定して時刻そのものを進める
    形で与える（「続きから」経過することは、満了する時刻そのものでしか
    確認できない）。TestParent が既定で掛けている Clock.is_up の無効化は、
    本クラスの間だけ外す。

    本クラスの経過では**売上発生間隔（3秒。他店建設間隔 10 秒より短い）も
    必ず満了する**ため、資金は売上のぶんだけ増える。本クラスの関心は盤面の
    変化であり、資金は「他店建設そのものでは変わらない」ことの確認に留めたい
    ので、売上の抽選は常にプレイヤー所有店舗（規模1）を選ばせ、その売上額を
    期待値へ織り込む（どの店舗が選ばれるかで額が揺れないようにする）。2つの
    間隔が同じ update() で満了しても、抽選が乱数源の別々のメソッドに分かれて
    いるため呼び出し順を数える必要がないことが、ここで実際に効いている"""

    # 起点にするプレイヤー所有店舗の区画（TestNpcGrowthInterval と同じ）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる（上記の理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押す）で
        最初の店舗を建設する（TestNpcGrowthInterval と同じ）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _restored_player_shop_data(self, remaining_ms):
        """プレイヤー所有店舗が1軒だけあり、他店建設間隔の残り時間が
        remaining_ms である保存データ"""
        return {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "npc_growth_remaining_ms": remaining_ms,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }

    def test_save_data_has_no_remaining_ms_before_the_first_player_shop_is_built(
        self,
    ):
        """最初のプレイヤー所有店舗を建設する前（他店建設間隔のタイマーが
        まだ生成されていない）は、保存データの残り時間が None（未開始）
        であること"""
        core = GameCore()
        self.assertIsNone(
            core._get_save_data()["npc_growth_remaining_ms"]  # pylint: disable=W0212
        )

    def test_save_data_holds_remaining_ms_after_the_clock_starts(self):
        """最初のプレイヤー所有店舗を建設し、間隔の一部が経過した時点の
        保存データに、満了までの残り時間が正しく含まれること"""
        interval = GameCore.NPC_GROWTH_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        elapsed_ms = interval // 4
        self._advance_ms(elapsed_ms)
        self.assertEqual(
            interval - elapsed_ms,
            core._get_save_data()["npc_growth_remaining_ms"],  # pylint: disable=W0212
        )

    def test_restoring_remaining_ms_continues_from_where_it_left_off(self):
        """残り時間を含む保存データから復元すると、その残り時間の続きから
        経過すること（復元直後に満了しない・既定の間隔ぶん待たされない）。
        検証は draw() の描画呼び出し列で行う（TestNpcGrowthInterval と同じ
        理由。他店建設間隔で起きるのは盤面そのものの変化のため）"""
        npc_shop = (self.NPC_COL, self.NPC_ROW, Owner.NPC)
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        remaining_ms = GameCore.NPC_GROWTH_INTERVAL_MS // 3
        # 残り時間（3,333ms）はいずれのケースでも売上発生間隔（3,000ms）を
        # 超えるため、売上が1回ぶん入る（上記クラス docstring の理由）
        money = self.RESTORED_MONEY + Shop.SALES_AMOUNT * 2**0
        test_cases = [
            (
                "保存された残り時間に満たない経過では建たない",
                remaining_ms - 1,
                [player_shop],
            ),
            (
                "保存された残り時間ぶん経つとNPC所有店舗が1軒建つ",
                remaining_ms,
                [npc_shop, player_shop],
            ),
        ]
        for case_name, elapsed_ms, expected_shops in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                # サブテストをまたいで押下・経過時間が残らないようにする
                # （TestNpcGrowthInterval と同じ理由）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = self._restored_player_shop_data(
                    remaining_ms
                )
                core = GameCore()
                self._advance_ms(elapsed_ms)
                core.update()
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(
                        expected_shops,
                        money=money,
                        # 売上も満了しているため、抽選先（常に起点の
                        # プレイヤー所有店舗）が囲まれる
                        sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                        # 決算タイマーは復元されたプレイヤー所有店舗により
                        # 起動時（t=0）から経過するため、経過は elapsed_ms と
                        # 同じ（ID-014 サイクル3）
                        remaining_sec=self._expected_settlement_remaining_sec(
                            elapsed_ms
                        ),
                        shop_count=1,
                        tax=self._expected_tax([Shop.BUILD_COST]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_restoring_unstarted_state_does_not_start_the_clock(self):
        """未開始（最初の店舗の建設前）の状態も保存・復元され、リロードで
        勝手に開始しないこと（プレイヤー所有店舗がない保存データで
        npc_growth_remaining_ms が None のとき）"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": GameCore.INITIAL_MONEY,
            "npc_growth_remaining_ms": None,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        for _ in range(3):
            self._advance_ms(GameCore.NPC_GROWTH_INTERVAL_MS)
            core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(money=GameCore.INITIAL_MONEY),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_restoring_data_without_saved_remaining_ms_starts_fresh(self):
        """他店建設間隔が導入される前の保存データ（npc_growth_remaining_ms
        キーが無い）を読み込んでも例外にならず、タイマーは最初から
        （NPC_GROWTH_INTERVAL_MS ぶん）始まること。既存の進行（店舗・資金）を
        破棄しない後方互換の確認（サイクル5 Refactor の判断: ReportStore.VERSION
        は繰り上げず、キーの欠落を既定値 None で補う）"""
        interval = GameCore.NPC_GROWTH_INTERVAL_MS
        npc_shop = (self.NPC_COL, self.NPC_ROW, Owner.NPC)
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        # interval - 1 の経過で売上発生間隔も満了し、売上が1回ぶん入る。
        # 続く 1ms の経過では売上は入らない（満了のたびに基準時刻が更新される）
        money = self.RESTORED_MONEY + Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        # 売上の抽選先（常に起点のプレイヤー所有店舗）。続く 1ms の経過では
        # 売上は満了しないが、囲みは次の満了まで同じ区画に残り続ける
        sales_plot = (self.PLAYER_COL, self.PLAYER_ROW)
        core = GameCore()
        self._advance_ms(interval - 1)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [player_shop],
                money=money,
                sales_plot=sales_plot,
                remaining_sec=self._expected_settlement_remaining_sec(interval - 1),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.test_view.call_params = []
        self._advance_ms(1)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [npc_shop, player_shop],
                money=money,
                sales_plot=sales_plot,
                remaining_sec=self._expected_settlement_remaining_sec(interval),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestSalesInterval(TestParent):
    """売上発生間隔（GameCore.SALES_INTERVAL_MS）の満了による売上の抽選・
    所有者による分岐・資金への加算と、その起点（最初のプレイヤー所有店舗が
    建設された時点。要件 3.2）に関する振る舞いのテスト。

    **検証はすべて draw() の描画呼び出し列で行う**（save() へ渡ったデータは
    見ない）。売上で変わるのはステータス領域の資金テキストだけで、盤面
    （店舗の所有者・規模）は変わらないことも、同じ1つの列で確認できる。

    **タイマーの発火は Clock.is_up の差し替えではなく、time.perf_counter() を
    固定して時刻そのものを進める形で与える**（TestNpcGrowthInterval と同じ
    与え方・同じ理由。「起点がどこか」は満了する時刻の違いとしてしか現れず、
    is_up を差し替えると起動を起点にした実装と建設を起点にした実装が区別
    できなくなる）。TestParent が既定で掛けている Clock.is_up の無効化は、
    本クラスの間だけ外す。

    どの店舗が抽選されるかは、乱数源の pick_sales_shop() を**区画で**仕込む
    （呼び出し順ではなく意図で書ける）。他店建設の抽選とはメソッドが分かれて
    いるため、売上発生間隔（3,000ms）と他店建設間隔（10,000ms）が同じ
    update() で満了しても、どちらの抽選なのかを順序で数える必要がない。
    本クラスの経過は他店建設間隔に満たない範囲に収め、盤面が変わるのは
    他店建設だけであることと混ざらないようにする"""

    # 起点にするプレイヤー所有店舗の区画（TestNpcGrowthInterval と同じ。
    # 画面左半分 → ポップアップは右下）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 同じ盤面に置くNPC所有店舗の区画（プレイヤー所有店舗の真上）
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1
    # 保存データから復元する資金（初期資金と区別できる値）
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _pick_sales_shop(self, col, row):
        """売上の抽選で常に区画 (col, row) が選ばれるようにする。同時に、その
        区画が**抽選対象に含まれていること**も確かめる（対象に無い区画を
        返させたせいで期待どおりに見えている、ということがないようにする）。
        これにより「抽選対象はマップ上のすべての店舗」——NPC所有店舗も規模が
        上限の店舗も対象になる——ことが、各テストの選び方そのもので確認される"""

        def pick(targets):
            self.assertIn((col, row), targets)
            return (col, row)

        self.test_random_source.pick_sales_shop.side_effect = pick

    def _shop_save_entry(self, col, row, owner, scale=Shop.INITIAL_SCALE):
        """保存データの1区画分（座標・所有者・店舗規模・資産価値）。資産価値は
        要件 3.11（初期店舗設置費用＋これまでに行った増資費用の合計）どおり
        規模から求め、規模と食い違った盤面を作らない"""
        value = Shop.BUILD_COST + Shop.INVEST_COST * (2 ** (scale - 1) - 1)
        return [col, row, owner.value, scale, value]

    def _restored_data(self, shops):
        """`shops`（_shop_save_entry() の並び）の店舗と RESTORED_MONEY の資金を
        持つ保存データ。売上発生間隔の残り時間は保存対象に含めない
        （残り時間の保存・復元は TDD サイクル3 の範囲）"""
        return {
            "shops": shops,
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押して離し、
        「x」で閉じる）で最初の店舗を建設する。**タイマーの起点は「建設された
        時点」のため、Field へ直接店舗を置くのではなく実際の建設の経路を通す**
        （TestNpcGrowthInterval と同じ。「x」で閉じる理由も同じ——ID-022 決定1）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        o_x, o_y, o_w, o_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (o_x + o_w // 2, o_y + o_h // 2))
        self._release(core)
        x_x, x_y, x_w, x_h = self._expected_button_rect(popup_x, 1)
        self._press(core, (x_x + x_w // 2, x_y + x_h // 2))
        self._release(core)

    def test_no_sales_before_the_first_player_shop_is_built(self):
        """店舗が1軒もない起動直後は、売上発生間隔ぶんの時間が何度過ぎても
        資金が変わらないこと（要件 3.2「それ以前は経過しない」）"""
        core = GameCore()
        for _ in range(3):
            self._advance_ms(GameCore.SALES_INTERVAL_MS)
            core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_money_grows_by_the_sales_of_the_picked_player_shop(self):
        """最初のプレイヤー所有店舗を起点として売上発生間隔が満了したとき、
        抽選されたプレイヤー所有店舗の**店舗規模に応じた売上額**
        （Shop.SALES_AMOUNT × 2^(規模-1)）が資金へ加算されること。
        盤面（店舗の所有者・規模）は売上では変わらない。

        起点は「建設された時点」であり、それ以前の経過は持ち越されない
        （建設した直後は満了しておらず、建設から間隔に満たない経過でも
        売上は入らない）。保存データから復元してプレイヤー所有店舗が既に
        ある場合は、起動の時点が起点になる。

        規模1の売上額は SALES_AMOUNT × 2^0 = 50 となり ID-009 以前の一律の
        仮値と偶然一致するため、**規模2以上のケースを必ず併せて確認する**
        （規模1だけでは、規模に依存しない実装のままでも通ってしまう）"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        built_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST
        interval = GameCore.SALES_INTERVAL_MS
        # 起動から「プレイヤーが最初の店舗を建設する」までの経過。**間隔より
        # 短い値**にすることが重要で、ここに間隔ぶん以上を置くと、起動を起点に
        # した実装でも建設の時点でタイマーが一度満了して起点が建設時刻へ揃って
        # しまい、正しい実装と区別が付かなくなる（TestNpcGrowthInterval と同じ）
        boot_to_build_ms = interval // 2
        test_cases = [
            (
                "建設した直後は満了していない（建設前の経過は持ち越されない）",
                None,
                0,
                built_money,
            ),
            (
                "建設から間隔に満たない経過では売上が入らない",
                None,
                interval - 1,
                built_money,
            ),
            (
                "建設から間隔ぶん経つと規模1の売上額が入る",
                None,
                interval,
                built_money + Shop.SALES_AMOUNT * 2**0,
            ),
            (
                "復元した店舗があるとき、起動から間隔に満たない経過では入らない",
                3,
                interval - 1,
                self.RESTORED_MONEY,
            ),
            (
                "復元した規模3の店舗では規模に応じた売上額が入る",
                3,
                interval,
                self.RESTORED_MONEY + Shop.SALES_AMOUNT * 2**2,
            ),
            (
                "規模10（上限）の店舗も抽選され、売上額は頭打ちにならない",
                10,
                interval,
                self.RESTORED_MONEY + Shop.SALES_AMOUNT * 2**9,
            ),
        ]
        for case_name, restored_scale, elapsed_ms, money in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                # サブテストをまたいで押下の状態・経過時間が残らないよう、
                # ケースごとに入力を未押下へ戻す（前のケースの建設操作の押下が
                # 残っていると、次のケースでポップアップが追従してしまう）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = (
                    None
                    if restored_scale is None
                    else self._restored_data(
                        [
                            self._shop_save_entry(
                                self.PLAYER_COL,
                                self.PLAYER_ROW,
                                Owner.PLAYER,
                                scale=restored_scale,
                            )
                        ]
                    )
                )
                self._pick_sales_shop(self.PLAYER_COL, self.PLAYER_ROW)
                core = GameCore()
                if restored_scale is None:
                    self._advance_ms(boot_to_build_ms)
                    self._build_player_shop(core)
                self._advance_ms(elapsed_ms)
                core.update()
                self._draw(core)
                # 決算タイマーは他店建設間隔・売上発生間隔と同時に起動するため
                # 経過は同じ elapsed_ms（ID-014 サイクル3）。税額は盤面の
                # 店舗規模から求まる資産価値（建設直後は Shop.BUILD_COST、
                # 復元時は _shop_save_entry() と同じ式）に対応する
                shop_value = (
                    Shop.BUILD_COST
                    if restored_scale is None
                    else Shop.BUILD_COST
                    + Shop.INVEST_COST * (2 ** (restored_scale - 1) - 1)
                )
                self.assertEqual(
                    self._expected_field_calls(
                        [player_shop],
                        money=money,
                        scale=(
                            Shop.INITIAL_SCALE
                            if restored_scale is None
                            else restored_scale
                        ),
                        # 満了したケースでは抽選先（このテストでは常に
                        # プレイヤー所有店舗）が囲まれる。満了していない
                        # ケースでは囲みがまだ現れない
                        sales_plot=(
                            (self.PLAYER_COL, self.PLAYER_ROW)
                            if elapsed_ms >= interval
                            else None
                        ),
                        remaining_sec=self._expected_settlement_remaining_sec(
                            elapsed_ms
                        ),
                        shop_count=1,
                        tax=self._expected_tax([shop_value]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_nothing_happens_when_the_picked_shop_is_owned_by_npc(self):
        """NPC所有店舗が抽選されたときは何も起きないこと（資金も盤面も
        変わらない）。同じ盤面・同じ経過でプレイヤー所有店舗が抽選された
        ときには売上が入ることを併せて確認し、**違いが抽選された店舗の
        所有者だけであること**を固定する。
        NPC所有店舗が抽選され得ること（抽選対象は所有者を問わないすべての
        店舗であること）も、この選び方そのもので確認される"""
        npc_shop = (self.NPC_COL, self.NPC_ROW, Owner.NPC)
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        shops_data = [
            self._shop_save_entry(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER),
            self._shop_save_entry(self.NPC_COL, self.NPC_ROW, Owner.NPC),
        ]
        test_cases = [
            (
                "NPC所有店舗が抽選されたときは資金も盤面も変わらない",
                (self.NPC_COL, self.NPC_ROW),
                self.RESTORED_MONEY,
            ),
            (
                "同じ盤面でプレイヤー所有店舗が抽選されれば売上が入る",
                (self.PLAYER_COL, self.PLAYER_ROW),
                self.RESTORED_MONEY + Shop.SALES_AMOUNT * 2**0,
            ),
        ]
        for case_name, picked, money in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                self.mock_store.load.return_value = self._restored_data(shops_data)
                self._pick_sales_shop(*picked)
                core = GameCore()
                self._advance_ms(GameCore.SALES_INTERVAL_MS)
                core.update()
                self._draw(core)
                self.assertEqual(
                    # 描画は行昇順→列昇順のため、真上のNPC所有店舗が先に来る。
                    # 囲みは抽選された区画に付き、**所有者を問わない**
                    # （NPC所有店舗が抽選されたケースでは資金が変わらないまま
                    # 囲みだけが現れる）。税額はプレイヤー所有店舗
                    # （Shop.BUILD_COST）のみが対象で、NPC所有店舗が抽選されて
                    # も変わらない（ID-014 サイクル3）
                    self._expected_field_calls(
                        [npc_shop, player_shop],
                        money=money,
                        sales_plot=picked,
                        remaining_sec=self._expected_settlement_remaining_sec(
                            GameCore.SALES_INTERVAL_MS
                        ),
                        shop_count=1,
                        tax=self._expected_tax([Shop.BUILD_COST]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_sales_are_added_on_every_expiry(self):
        """売上発生間隔が満了するたびに売上が入ること（2回満了すれば2回ぶん
        増える）。Clock が満了のたびに基準時刻を更新する既存の振る舞いに
        乗っていることの確認でもある（1回目の満了以降ずっと満了し続ける、
        あるいは1回きりで止まる、のいずれでもない）"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales = Shop.SALES_AMOUNT * 2**0
        built_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST
        self._pick_sales_shop(self.PLAYER_COL, self.PLAYER_ROW)
        core = GameCore()
        self._build_player_shop(core)
        for times in (1, 2):
            with self.subTest(times=times):
                self._advance_ms(GameCore.SALES_INTERVAL_MS)
                core.update()
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(
                        [player_shop],
                        money=built_money + times * sales,
                        sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                        remaining_sec=self._expected_settlement_remaining_sec(
                            times * GameCore.SALES_INTERVAL_MS
                        ),
                        shop_count=1,
                        tax=self._expected_tax([Shop.BUILD_COST]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestSalesClockSaveLoad(TestParent):
    """売上発生間隔の残り時間の保存・復元（TDD サイクル3）に関する振る舞いの
    テスト。他店建設間隔の残り時間の保存・復元（TestNpcGrowthClockSaveLoad。
    ID-008 サイクル5）と同じ形を、ShopClock を挟んだ2件目としてそのまま
    適用する。

    タイマーの発火は TestNpcGrowthClockSaveLoad と同じく、Clock.is_up の
    差し替えではなく time.perf_counter() を固定して時刻そのものを進める
    形で与える（「続きから」経過することは、満了する時刻そのものでしか
    確認できない）。TestParent が既定で掛けている Clock.is_up の無効化は、
    本クラスの間だけ外す。

    本クラスの経過は他店建設間隔（10秒）に満たない範囲に収め、盤面
    （店舗の所有者・規模）は売上では変わらないことを、資金テキストの変化と
    併せて確認する。どの店舗が抽選されるかは常に起点のプレイヤー所有店舗
    （規模1）に固定し、その売上額（Shop.SALES_AMOUNT × 2^0）を期待値へ
    織り込む"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる（上記の理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押す）で
        最初の店舗を建設する（TestNpcGrowthClockSaveLoad と同じ）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _restored_player_shop_data(self, remaining_ms):
        """プレイヤー所有店舗が1軒だけあり、売上発生間隔の残り時間が
        remaining_ms である保存データ"""
        return {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "sales_remaining_ms": remaining_ms,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }

    def test_save_data_has_no_remaining_ms_before_the_first_player_shop_is_built(
        self,
    ):
        """最初のプレイヤー所有店舗を建設する前（売上発生間隔のタイマーが
        まだ生成されていない）は、保存データの残り時間が None（未開始）
        であること"""
        core = GameCore()
        self.assertIsNone(
            core._get_save_data()["sales_remaining_ms"]  # pylint: disable=W0212
        )

    def test_save_data_holds_remaining_ms_after_the_clock_starts(self):
        """最初のプレイヤー所有店舗を建設し、間隔の一部が経過した時点の
        保存データに、満了までの残り時間が正しく含まれること"""
        interval = GameCore.SALES_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        elapsed_ms = interval // 4
        self._advance_ms(elapsed_ms)
        self.assertEqual(
            interval - elapsed_ms,
            core._get_save_data()["sales_remaining_ms"],  # pylint: disable=W0212
        )

    def test_restoring_remaining_ms_continues_from_where_it_left_off(self):
        """残り時間を含む保存データから復元すると、その残り時間の続きから
        経過すること（復元直後に満了しない・既定の間隔ぶん待たされない）。
        検証は draw() の描画呼び出し列（資金テキスト）で行う"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        remaining_ms = GameCore.SALES_INTERVAL_MS // 3
        sales = Shop.SALES_AMOUNT * 2**0
        # 復元直後は囲みが無い（囲みは保存対象に含めない）。満了して初めて
        # 抽選先（このテストでは常にプレイヤー所有店舗）が囲まれる
        sales_plot = (self.PLAYER_COL, self.PLAYER_ROW)
        test_cases = [
            (
                "保存された残り時間に満たない経過では売上が入らない",
                remaining_ms - 1,
                self.RESTORED_MONEY,
                None,
            ),
            (
                "保存された残り時間ぶん経つと売上が入る",
                remaining_ms,
                self.RESTORED_MONEY + sales,
                sales_plot,
            ),
        ]
        for case_name, elapsed_ms, money, expected_sales_plot in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                # サブテストをまたいで押下・経過時間が残らないようにする
                # （TestNpcGrowthClockSaveLoad と同じ理由）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = self._restored_player_shop_data(
                    remaining_ms
                )
                core = GameCore()
                self._advance_ms(elapsed_ms)
                core.update()
                self._draw(core)
                self.assertEqual(
                    self._expected_field_calls(
                        [player_shop],
                        money=money,
                        sales_plot=expected_sales_plot,
                        remaining_sec=self._expected_settlement_remaining_sec(
                            elapsed_ms
                        ),
                        shop_count=1,
                        tax=self._expected_tax([Shop.BUILD_COST]),
                    ),
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_restoring_unstarted_state_does_not_start_the_clock(self):
        """未開始（最初の店舗の建設前）の状態も保存・復元され、リロードで
        勝手に開始しないこと（プレイヤー所有店舗がない保存データで
        sales_remaining_ms が None のとき）"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": GameCore.INITIAL_MONEY,
            "sales_remaining_ms": None,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        for _ in range(3):
            self._advance_ms(GameCore.SALES_INTERVAL_MS)
            core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(money=GameCore.INITIAL_MONEY),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_restoring_data_without_saved_remaining_ms_starts_fresh(self):
        """売上発生間隔が導入される前の保存データ（sales_remaining_ms
        キーが無い）を読み込んでも例外にならず、タイマーは最初から
        （SALES_INTERVAL_MS ぶん）始まること。既存の進行（店舗・資金）を
        破棄しない後方互換の確認（ID-008 サイクル5 Refactor の判断:
        ReportStore.VERSION は繰り上げず、キーの欠落を既定値 None で補う）"""
        interval = GameCore.SALES_INTERVAL_MS
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales = Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        self._advance_ms(interval - 1)
        core.update()
        self._draw(core)
        self.assertEqual(
            # 満了前のため囲みはまだ現れない
            self._expected_field_calls(
                [player_shop],
                money=self.RESTORED_MONEY,
                sales_plot=None,
                remaining_sec=self._expected_settlement_remaining_sec(interval - 1),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.test_view.call_params = []
        self._advance_ms(1)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [player_shop],
                money=self.RESTORED_MONEY + sales,
                sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                remaining_sec=self._expected_settlement_remaining_sec(interval),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_both_clocks_restore_independently_without_interfering(self):
        """他店建設間隔と売上発生間隔の残り時間が同時に保存・復元されても、
        互いに干渉せず独立に続きから経過すること（要件 3.13「各時間間隔の
        残り時間」）。他店建設間隔の残り時間は本テストの経過（売上発生間隔の
        残り時間ぶん）では絶対に満了しない大きさにとり、盤面
        （NPC所有店舗が増えないこと）が変わらないことで確認する"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales_remaining_ms = GameCore.SALES_INTERVAL_MS // 3
        npc_growth_remaining_ms = GameCore.NPC_GROWTH_INTERVAL_MS
        sales = Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "npc_growth_remaining_ms": npc_growth_remaining_ms,
            "sales_remaining_ms": sales_remaining_ms,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        self._advance_ms(sales_remaining_ms)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [player_shop],
                money=self.RESTORED_MONEY + sales,
                # 売上だけが満了したため、抽選先が囲まれる
                sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                remaining_sec=self._expected_settlement_remaining_sec(
                    sales_remaining_ms
                ),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestSalesFrame(TestParent):
    """売上の抽選が起きた店舗をフィールド上で四角形に囲む表示（要件 3.3）に
    関する振る舞いのテスト。

    **囲みの有無・所有者非依存の検証の大半は本クラスではなく
    `TestSalesInterval` / `TestSalesClockSaveLoad` が担う**（`TestSelectionFrame`
    が選択枠の描画順・状態ごとの有無をポップアップの各テストへ委譲するのと
    同じ考え方）。`_expected_field_calls()` の `sales_plot` 引数を経由して、
    「抽選が起きるまで囲みが無い」「所有者を問わず囲まれる（NPC所有店舗の
    ケースを含む）」「満了ごとに資金と同じ列で確認される」ことは、それらの
    クラスの既存テストが売上発生間隔・保存復元の検証と併せてすでに確認して
    いる。そのため本クラスでは重複を作らず、**他クラスが単一の固定区画
    （PLAYER_COL, PLAYER_ROW）でしか確認していない観点**だけを持つ。

    | 確認したいこと | 他クラスでは確認できない理由 |
    |---|---|
    | 抽選が切り替わるたびに囲みが移動し、前の区画に残らない | 他クラスは同じ区画を繰り返し抽選させるか、単発の抽選しか行わない |
    | 満了していない間、複数フレームにわたって同じ区画を囲み続ける | 他クラスは満了の瞬間の描画列しか見ない |
    | 選択枠との重なり順（店舗の後・選択枠の前） | 選択枠側のどのテストも売上の囲みとの順序関係を確認しない |
    | 区画座標から枠の矩形を導く経路（四隅・中央） | 他クラスはいずれも `PLAYER_COL`/`PLAYER_ROW` 固定の1区画でしか確認しない |

    **検証はすべて draw() の描画呼び出し列で行う**（囲みを覚えている内部変数は
    見ない。ID-004 以降と同じ方針）。

    **タイマーの発火は Clock.is_up の差し替えではなく、time.perf_counter() を
    固定して時刻そのものを進める形で与える**（TestSalesInterval と同じ与え方・
    同じ理由）。TestParent が既定で掛けている Clock.is_up の無効化は、本クラスの
    間だけ外す。

    どの店舗が抽選されるかは乱数源の pick_sales_shop() を**区画で**仕込む。
    本クラスの経過は他店建設間隔（10,000ms）に満たない範囲に収め、盤面が
    変わるのは他店建設だけであることと混ざらないようにする"""

    # 起点にするプレイヤー所有店舗の区画（TestSalesInterval と同じ。
    # 画面左半分 → ポップアップは右下）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 同じ盤面に置くNPC所有店舗の区画（プレイヤー所有店舗の真上）。
    # 囲みが別の区画へ移ることの確認にも使う
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1
    # 保存データから復元する資金（初期資金と区別できる値）
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _pick_sales_shop(self, col, row):
        """売上の抽選で常に区画 (col, row) が選ばれるようにする。同時に、その
        区画が**抽選対象に含まれていること**も確かめる（TestSalesInterval と
        同じ与え方）"""

        def pick(targets):
            self.assertIn((col, row), targets)
            return (col, row)

        self.test_random_source.pick_sales_shop.side_effect = pick

    def _shop_save_entry(self, col, row, owner, scale=Shop.INITIAL_SCALE):
        """保存データの1区画分（座標・所有者・店舗規模・資産価値）。資産価値は
        要件 3.11 どおり規模から求め、規模と食い違った盤面を作らない"""
        value = Shop.BUILD_COST + Shop.INVEST_COST * (2 ** (scale - 1) - 1)
        return [col, row, owner.value, scale, value]

    def _restored_data(self, shops):
        """`shops`（_shop_save_entry() の並び）の店舗と RESTORED_MONEY の資金を
        持つ保存データ。囲みは保存対象に含まれない（設計判断）ため、復元直後は
        必ず囲みが無い状態から始まる"""
        return {
            "shops": shops,
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押す）で
        最初の店舗を建設する。**タイマーの起点は「建設された時点」のため、
        Field へ直接店舗を置くのではなく実際の建設の経路を通す**"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_the_sales_frame_moves_to_the_newly_picked_shop(self):
        """次の売上発生で囲みが新しく抽選された店舗へ移り、**前に囲まれていた
        店舗の囲みが残らない**こと（要件 3.3「次の売上発生まで」）。
        囲みは常に1つで、売上が発生した店舗の一覧・履歴は持たない。
        1回目にプレイヤー所有店舗・2回目にNPC所有店舗を抽選させることで、
        囲みが移ること（囲みが増えないこと）と、移った先の所有者を問わない
        ことを同時に確認する"""
        npc_shop = (self.NPC_COL, self.NPC_ROW, Owner.NPC)
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales = Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = self._restored_data(
            [
                self._shop_save_entry(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER),
                self._shop_save_entry(self.NPC_COL, self.NPC_ROW, Owner.NPC),
            ]
        )
        self._pick_sales_shop(self.PLAYER_COL, self.PLAYER_ROW)
        core = GameCore()
        # 1回目の満了: プレイヤー所有店舗が抽選され、そこが囲まれる
        self._advance_ms(GameCore.SALES_INTERVAL_MS)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [npc_shop, player_shop],
                money=self.RESTORED_MONEY + sales,
                sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                remaining_sec=self._expected_settlement_remaining_sec(
                    GameCore.SALES_INTERVAL_MS
                ),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        # 2回目の満了: NPC所有店舗が抽選され、囲みはそちらへ移る
        # （資金は増えないが囲みは移動する）
        self._pick_sales_shop(self.NPC_COL, self.NPC_ROW)
        self._advance_ms(GameCore.SALES_INTERVAL_MS)
        core.update()
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [npc_shop, player_shop],
                money=self.RESTORED_MONEY + sales,
                sales_plot=(self.NPC_COL, self.NPC_ROW),
                remaining_sec=self._expected_settlement_remaining_sec(
                    2 * GameCore.SALES_INTERVAL_MS
                ),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_the_sales_frame_stays_until_the_next_expiry(self):
        """満了していない間は囲みが同じ店舗に留まり続けること（要件 3.3
        「次の売上発生まで」）。1回目の満了の後、間隔に満たない経過を重ねても
        囲みの位置も資金も変わらない（囲みが1フレームだけ現れて消える実装を
        弾く）"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales = Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = self._restored_data(
            [self._shop_save_entry(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)]
        )
        self._pick_sales_shop(self.PLAYER_COL, self.PLAYER_ROW)
        core = GameCore()
        self._advance_ms(GameCore.SALES_INTERVAL_MS)
        core.update()
        elapsed_ms = GameCore.SALES_INTERVAL_MS
        # 満了直後と、そこから間隔に満たない経過を 2 回重ねた後（合計しても
        # 次の満了には届かない刻み）で、囲み・資金・税額は同じまま描かれ続ける
        # 一方、決算までの残り時間は経過に応じてステップごとに進む
        # （ID-014 サイクル3）
        for step in range(3):
            with self.subTest(step=step):
                self._draw(core)
                expected = self._expected_field_calls(
                    [player_shop],
                    money=self.RESTORED_MONEY + sales,
                    sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                    remaining_sec=self._expected_settlement_remaining_sec(elapsed_ms),
                    shop_count=1,
                    tax=self._expected_tax([Shop.BUILD_COST]),
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self._advance_ms(GameCore.SALES_INTERVAL_MS // 3)
                elapsed_ms += GameCore.SALES_INTERVAL_MS // 3
                core.update()

    def test_the_sales_frame_is_drawn_after_shops_and_before_the_selection_frame(self):
        """描画順が「ステータス → 道路 → 店舗 → 売上の囲み → 選択枠 →
        ポップアップ」であること。売上が発生している区画をそのまま押して、
        2つの枠が同じ区画へ**完全に重なる**状態で確認する（両者は原点・幅・
        高さのすべてが一致する）。
        店舗より先に囲みを描くと店舗画像の不透明部分で上書きされて消え、
        選択枠より後に描くことで、範囲が重なったときに操作への直接の応答で
        ある選択枠の色が売上の囲みより上に見える（設計判断: 同時発生時は
        選択枠を優先する）"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        sales = Shop.SALES_AMOUNT * 2**0
        self.mock_store.load.return_value = self._restored_data(
            [self._shop_save_entry(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)]
        )
        self._pick_sales_shop(self.PLAYER_COL, self.PLAYER_ROW)
        core = GameCore()
        self._advance_ms(GameCore.SALES_INTERVAL_MS)
        core.update()
        # 売上が発生した区画をそのまま押し、選択枠とポップアップを出す
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._draw(core)
        self.assertEqual(
            self._expected_field_calls(
                [player_shop],
                money=self.RESTORED_MONEY + sales,
                sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                remaining_sec=self._expected_settlement_remaining_sec(
                    GameCore.SALES_INTERVAL_MS
                ),
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            )
            + self._expected_selection_and_popup_calls(pos, owner=Owner.PLAYER),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_the_sales_frame_is_derived_from_the_picked_plot(self):
        """フィールドの四隅と中央のいずれの区画が抽選されても、その区画を
        囲む枠が正しい位置・サイズで描かれること（`TestSelectionFrame` の
        `test_selection_frame_drawn_for_pressed_plot` と同じ観点）。
        他の売上関連テストはいずれも起点の1区画（PLAYER_COL, PLAYER_ROW）
        でしか確認していないため、枠の位置
        （GRID_LEFT + col * PLOT_SIZE, FIELD_ORIGIN_Y + row * PITCH）と
        サイズ（PREVIEW_W × PREVIEW_H）がどちらの軸についても正しく導かれる
        ことを、列・行を独立に動かして確認する。
        店舗の建設順・所有者・描画順は他のテストが担うため、ここでは枠の
        呼び出しが含まれることだけを見る（全件一致では比較しない）。
        枠が選択枠と同じ高さ（PREVIEW_H。判定範囲の PITCH より道路1本分
        縦に長い）を持つため、`TestSelectionFrame` と同じく最下行のケースが
        画面外へはみ出さないことも併せて確認する"""
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
                self._now = 0.0
                # サブテストをまたいで押下の状態が残らないようにする
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = self._restored_data(
                    [self._shop_save_entry(col, row, Owner.PLAYER)]
                )
                self._pick_sales_shop(col, row)
                core = GameCore()
                self._advance_ms(GameCore.SALES_INTERVAL_MS)
                core.update()
                self._draw(core)
                # 枠の呼び出しはその区画につき1件だけ組み立てられる
                (expected_frame,) = self._expected_sales_frame_calls((col, row))
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


class TestSettlementInterval(TestParent):
    """決算間隔（GameCore.SETTLEMENT_INTERVAL_MS）の起点（最初のプレイヤー所有
    店舗が建設された時点。要件 3.2）・満了周期・満了が決算ポップアップの表示に
    結びつくこと（要件 3.8。ID-015 サイクル1）に関する振る舞いのテスト。

    タイマーそのものの正しさは**`GameCore._settlement_clock.remaining_ms()`
    を直接読む**（`core._save_clock.is_up` を直接差し替える既存の型と同じ、
    内部状態への直接アクセス）ことで確認し、同じシナリオに対するもう1つの
    観測点として、**満了が実際に決算ポップアップの表示へ結びついているか**
    （`_assert_settlement_popup_shown()`。`draw()` の呼び出し列に決算
    ポップアップの背景・枠が含まれるか）も併せて確認する。1つのシナリオに
    対して複数の観測点を1つのテストへ持たせる形は、`TestSalesFrame`
    （`assertIn` で描画の有無、`assertLessEqual` でレイアウトの性質を同じ
    シナリオで併用する）と同じ考え方（ID-015 TASK-015-4）。
    決算ポップアップ自体の描画の継続性・他のポップアップとの重なりの上下
    関係は、発生契機が時間経過であっても検証対象が描画そのものであるため
    `test_main_popup.py` の `TestSettlementPopupDisplay` 側で扱う（分類
    ルール1。`TestSalesFrame` / `TestSelectionFrame` と同じ境界の考え方）。
    保存を経由した検証はサイクル4で追加される。

    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    TestNpcGrowthInterval / TestSalesInterval と同じ"""

    # 起点にするプレイヤー所有店舗の区画（他の TestXInterval と同じ。
    # 画面左半分 → ポップアップは右下）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    # NPC所有店舗だけを復元するケースに使う区画（プレイヤー所有店舗の真上）
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔（60秒）は売上発生間隔（3秒）より長いため、本クラスの経過中に
        # 売上発生間隔が必ず何度か満了する。本クラスの関心は決算タイマーの
        # 残り時間だけであり、抽選先を固定して無関係な失敗（乱数源を差し替え
        # ていない状態での抽選）を避ける（TestNpcGrowthInterval と同じ理由・
        # 同じ与え方）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押す）で
        最初の店舗を建設する。**タイマーの起点は「建設された時点」のため、
        Field へ直接店舗を置くのではなく実際の建設の経路を通す**（他の
        TestXInterval と同じ）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _remaining_ms(self, core):
        """決算タイマーの残り時間を直接読む"""
        return core._settlement_clock.remaining_ms()  # pylint: disable=W0212

    def _assert_settlement_popup_shown(self, core, shown):
        """決算ポップアップの背景・枠（`_expected_settlement_popup_calls()`。
        ID-015 サイクル1）が `draw()` の呼び出し列に含まれるか（`shown` が
        真なら含まれる、偽なら含まれない）を確認する。`remaining_ms()` の
        直接読み取りと同じシナリオに対する、もう1つの観測点（満了が実際に
        画面へ結びついているか）として各テストの末尾で併用する"""
        self._draw(core)
        calls = self.test_view.get_call_params()
        bg_call, border_call = self._expected_settlement_popup_calls()
        if shown:
            self.assertIn(bg_call, calls, calls)
            self.assertIn(border_call, calls, calls)
        else:
            self.assertNotIn(bg_call, calls, calls)
            self.assertNotIn(border_call, calls, calls)

    def test_settlement_does_not_start_before_the_first_player_shop_is_built(self):
        """店舗が1軒もない起動直後は、決算間隔ぶんの時間が何度過ぎてもタイマーが
        未開始（remaining_ms が None）のままであり、決算ポップアップも現れない
        こと（要件 3.2「それ以前は経過しない」。起動と同時に決算する誤実装・
        盤面と無関係に間隔だけで満了させる誤実装を弾く）。起動直後（advance
        前）と、間隔を3回進めた後の両方で決算ポップアップが現れないことを
        確認する"""
        core = GameCore()
        self._assert_settlement_popup_shown(core, False)
        for _ in range(3):
            self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
            core.update()
            self._assert_settlement_popup_shown(core, False)
        self.assertIsNone(self._remaining_ms(core))

    def test_settlement_starts_from_the_interval_at_the_moment_of_build(self):
        """最初のプレイヤー所有店舗を建設した時点で経過が始まり、残り時間が
        決算間隔そのものになり、決算ポップアップはまだ現れないこと。起動から
        建設までに経過があっても、その分は持ち越さない（**間隔未満**に
        留めることで、起動を起点にした誤実装——建設の時点で一度満了して
        起点が揃ってしまう——を弾く。TestNpcGrowthInterval と同じ理由）"""
        core = GameCore()
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS // 2)
        self._build_player_shop(core)
        self.assertEqual(GameCore.SETTLEMENT_INTERVAL_MS, self._remaining_ms(core))
        self._assert_settlement_popup_shown(core, False)

    def test_settlement_has_not_expired_just_before_the_interval(self):
        """建設を起点として決算間隔の直前まで進めても満了しておらず（残り
        時間が正の）、決算ポップアップも現れないこと。境界のずれ（`>` と
        `>=` の取り違え）を弾く"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS - 1)
        core.update()
        self.assertGreater(self._remaining_ms(core), 0)
        self._assert_settlement_popup_shown(core, False)

    def test_settlement_expires_periodically_after_starting(self):
        """建設を起点として決算間隔が満了するたびに、残り時間が間隔まで巻き
        戻り、決算ポップアップが現れること。**1回だけでなく周期的に繰り返す**
        ことを確認する（空回しの呼び出しが効いておらず0で張り付く誤実装・
        1回だけ満了して止まる誤実装をともに弾く）。決算ポップアップの背景・
        枠が**毎回1組だけ**（`count()` で計測）であることも併せて確認し、
        満了のたびに描画が積み上がらない（二重に開かない）ことを弾く"""
        interval = GameCore.SETTLEMENT_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        for times in (1, 2):
            with self.subTest(times=times):
                self._advance_ms(interval)
                core.update()
                self.assertEqual(interval, self._remaining_ms(core))
                self._assert_settlement_popup_shown(core, True)
                bg_call, border_call = self._expected_settlement_popup_calls()
                calls = self.test_view.get_call_params()
                self.assertEqual(1, calls.count(bg_call), calls)
                self.assertEqual(1, calls.count(border_call), calls)

    def test_settlement_starts_at_boot_when_only_an_npc_owned_shop_is_restored(self):
        """NPC所有店舗だけを含む保存データから復元したときも、起動の時点から
        決算タイマーの経過が始まること（要件 3.2 の起点は**マップ上の店舗の
        有無**であり、所有者を問わない。プレイヤー所有店舗が現れるまで開始
        しない——所有者で絞る——誤実装を弾く。ID-025）"""
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.NPC_COL,
                    self.NPC_ROW,
                    Owner.NPC.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": GameCore.INITIAL_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        self.assertEqual(GameCore.SETTLEMENT_INTERVAL_MS, self._remaining_ms(core))
        self._assert_settlement_popup_shown(core, False)

    def test_settlement_starts_at_boot_when_a_player_shop_is_restored(self):
        """プレイヤー所有店舗を含む保存データから復元したときは、起動の
        時点から経過を始め、決算ポップアップはまだ現れないこと（リロードで
        決算までの経過が止まったままにならない。復元経路で開始を呼び忘れる
        誤実装——`_start_shop_clocks()` の一覧に足し忘れる——を弾く）"""
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": GameCore.INITIAL_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        self.assertEqual(GameCore.SETTLEMENT_INTERVAL_MS, self._remaining_ms(core))
        self._assert_settlement_popup_shown(core, False)


class TestSettlementPopupSuppressesFieldOperations(TestParent):
    """決算ポップアップ表示中は、区画への押下操作が区画選択ポップアップ・
    選択枠を一切生まないこと（要件 3.8。ID-015 サイクル3）に関するテスト。
    発生契機（決算タイマーの満了）が時間経過であるため、
    `TestSettlementInterval` と同じファイルに置く（テスト置き場の確定どおり）。

    決算タイマーの満了が決算ポップアップの表示に結びつくことは
    `TestSettlementInterval` が固定済みのため、本クラスはその結びつきを
    実際のタイマー経過で再現せず、`_core_with_settlement_popup_shown()`
    （`TestParent`）で状態を直接立てて検証する（`TestSettlementPopupDisplay`
    と同じ考え方）。「満了時に既に開いていた区画選択ポップアップが閉じる」
    ことは別クラス（`TestSettlementPopupResetsSelectionOnExpiry`）で扱う
    （本クラスは「表示中は最初から効かない」ことだけを検証し、サイクル境界
    をまたぐケースを持たない。TASK-015-8 の注意書きのとおり）"""

    def test_press_release_or_track_while_shown_draws_nothing_from_selection(self):
        """決算ポップアップ表示中に区画を押す・押して解除する（MODAL 化を
        試みる）・押した後に位置を動かす（追従を試みる）のいずれを行っても、
        draw() の呼び出し列が決算ポップアップとフィールドのみのまま変わらない
        こと（`_update_popup()` が動き続ける誤実装・解除の経路だけ抑止し漏れる
        誤実装・追従だけ生き残る誤実装をいずれも弾く）。3つの操作は共通して
        「区画選択ポップアップ・選択枠がまったく現れないこと」を確認する形の
        ため、1つのテストへ `subTest` でまとめる"""
        pos_a = self._plot_center_pos(0, 0)
        pos_b = self._plot_center_pos(1, 0)
        test_cases = [
            ("押す", (lambda core: self._press(core, pos_a),)),
            (
                "押して解除する",
                (
                    lambda core: self._press(core, pos_a),
                    self._release,
                ),
            ),
            (
                "押した後に位置を動かす",
                (
                    lambda core: self._press(core, pos_a),
                    lambda core: self._press(core, pos_b),
                ),
            ),
        ]
        expected = (
            self._expected_field_calls()
            + self._expected_settlement_popup_calls()
            + self._expected_settlement_popup_value_calls(
                GameCore.INITIAL_MONEY, 0, GameCore.INITIAL_MONEY
            )
            + self._expected_settlement_popup_button_calls()
        )
        for case_name, actions in test_cases:
            with self.subTest(case_name=case_name):
                core = self._core_with_settlement_popup_shown()
                for action in actions:
                    action(core)
                self._draw(core)
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_build_invest_or_buyout_does_not_happen_while_shown(self):
        """決算ポップアップ表示中は、区画を押して離し「o」ボタンの位置を押しても
        買収が起きず、盤面・資金が変わらないこと（「o」の押下判定だけ生き残る
        誤実装を弾く）。対象はNPC所有店舗（買収）とし、資金が減る・所有者が
        変わるという最も分かりやすい変化の有無で確認する（建設・増資は
        「o」が実行に結びつく点で買収と同じ形のため、代表して買収だけを扱う）"""
        core = self._core_with_settlement_popup_shown()
        col, row = 0, 0
        core._field.set_shop(col, row, Owner.NPC)  # pylint: disable=W0212
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)
        owner_after = core._field.get_owner(col, row)  # pylint: disable=W0212
        self.assertEqual(Owner.NPC, owner_after)
        self.assertEqual(GameCore.INITIAL_MONEY, core._money)  # pylint: disable=W0212


class TestSettlementPopupResetsSelectionOnExpiry(TestParent):
    """決算タイマーが満了した瞬間、区画選択ポップアップが開いていれば閉じる
    こと（要件 3.8。ID-015 サイクル3）に関するテスト。発生契機（決算タイマーの
    満了）が時間経過であるため、`TestSettlementInterval` と同じファイルに置く
    （テスト置き場の確定どおり）。

    区画選択ポップアップが TRACKING（押下中）・MODAL（表示中）・CLOSING
    （終了待ち）のいずれの状態で決算タイマーが満了しても、区画選択の枠・
    ポップアップが描画されなくなること（draw() の呼び出し列）に加え、状態が
    実際に「なし」（`PopupState.NONE`）へリセットされていることも確認する。
    CLOSING は `_is_selection_shown()` が NONE と同様に除外するため、
    リセットの有無がこの1フレームの draw() だけでは区別できない（リセット
    せず CLOSING のまま据え置いても、この描画は変わらない——決算ポップアップ
    自体を閉じる手段（サイクル5）が無い本サイクルの時点では、据え置かれた
    状態が後から表に出る経路も無い）。そのため本クラスに限り、`_remaining_ms()`
    を直接読む `TestSettlementInterval` と同じ考え方で、`core._popup_state`
    を直接読んでリセットの完了を確認する（TASK-015-10 で「リセットが
    `_reset_popup()` の再利用によるものか」を確認する足場として、まず
    リセットそのものが起きていることを本サイクルの Red で固定する）。
    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    `TestSettlementInterval` と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 区画選択ポップアップの状態を作る区画（プレイヤー所有店舗の建設に使う
    # 区画とは別。画面左半分 → ポップアップは右下）
    OTHER_COL = 0
    OTHER_ROW = 0

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

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作で最初の店舗を建設し、決算タイマーを起動する
        （`TestSettlementInterval._build_player_shop()` と同じ経路）。「o」を
        押した指を離すところまで行い、区画選択ポップアップを NONE へ戻して
        おく（この後で作る OTHER_COL/OTHER_ROW の TRACKING / MODAL / CLOSING
        の状態と混ざらないようにする）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def test_selection_popup_resets_when_settlement_expires_regardless_of_its_state(
        self,
    ):
        """決算タイマーが満了した瞬間、区画選択ポップアップが TRACKING /
        MODAL / CLOSING のいずれであっても「なし」へリセットされ、決算
        ポップアップだけが描かれること（2つが重なって描かれる誤実装・押下中の
        追従が決算表示の裏で続く誤実装・状態の取り残しをいずれも弾く）"""
        other_pos = self._plot_center_pos(self.OTHER_COL, self.OTHER_ROW)

        def to_tracking(core):
            # 押したまま（release しない）にして、追従中の状態を作る
            self._press(core, other_pos)

        def to_modal(core):
            self._press(core, other_pos)
            self._release(core)

        def to_closing(core):
            # 空き区画のため「o」は建設を実行してから CLOSING へ移る。押した
            # 指はまだ離さない（release しない）ことで終了待ち状態を作る
            to_modal(core)
            popup_x = self._expected_popup_x(other_pos[0])
            btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
                popup_x, GameCore.POPUP_BTN_INDEX_O
            )
            self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

        test_cases = [
            ("TRACKING（押下中）", to_tracking),
            ("MODAL（表示中）", to_modal),
            ("CLOSING（終了待ち）", to_closing),
        ]
        for case_name, make_state in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                core = GameCore()
                self._build_player_shop(core)
                make_state(core)
                self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
                core.update()
                self.assertEqual(
                    PopupState.NONE, core._popup_state  # pylint: disable=W0212
                )
                self._draw(core)
                calls = self.test_view.get_call_params()
                for expected_call in self._expected_selection_calls(
                    other_pos
                ) + self._expected_popup_calls(
                    popup_x=self._expected_popup_x(other_pos[0])
                ):
                    self.assertNotIn(expected_call, calls, calls)
                bg_call, border_call = self._expected_settlement_popup_calls()
                self.assertIn(bg_call, calls, calls)
                self.assertIn(border_call, calls, calls)


class TestSettlementPopupFreezesTime(TestParent):
    """決算ポップアップ表示中は、保存・他店建設・売上・決算の4つのタイマー
    すべての経過が止まり（完全凍結）、閉じた後は止めた時点の残り時間の
    続きから再開すること（要件 3.8。ID-015 サイクル4）に関するテスト。
    発生契機（決算タイマーの満了）が時間経過であるため、
    `TestSettlementInterval` と同じファイルに置く（テスト置き場の確定
    どおり）。

    `is_up()` を呼ばないだけでは時間が止まらない（`Clock` は
    `time.perf_counter()` の差分で判定するため、呼ばずにいても実時間は
    進み続ける）という設計判断の前提を踏まえ、**表示中に大きく時間を
    進めてから閉じても、閉じた直後に一気に進行が起きない**ことを重点的に
    確認する（弾く誤実装: `is_up()` を呼ばないだけの実装。閉じた瞬間に
    実時間ベースで即座に満了してしまう）。

    一時停止（`GameCore.update()`）は決算タイマーが満了した**その場**でだけ
    呼ばれ、表示中のフレームで毎回呼び直されることはない（真偽値の状態を
    毎フレーム読んで同期する形は採らない。`GameCore.update()` の docstring
    を参照）。決算ポップアップを閉じる手段（クリックによる精算）はまだ無い
    （サイクル5）。本サイクルの時点では、`_close_settlement_popup()` が
    精算処理が将来行うはずの操作（表示を「なし」へ戻す・凍結していた4つの
    タイマーを再開する）を直接呼んで模す（`_core_with_settlement_popup_
    shown()` が True を直接立てるのと対になる形。
    `TestSettlementPopupSuppressesFieldOperations` と同じ考え方）。

    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    `TestSettlementInterval` と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # NPC所有店舗が建つ区画（他店建設間隔の抽選対象の先頭。TestNpcGrowthInterval
    # と同じ規則）
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔（60秒）は売上発生間隔（3秒）より長いため、経過中に売上
        # 発生間隔が必ず満了する。抽選先を固定して無関係な失敗を避ける
        # （TestSettlementInterval と同じ理由・同じ与え方）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押して
        離す）で最初の店舗を建設し、決算タイマーを起動する
        （`TestSettlementInterval` と同じ経路）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _open_settlement_popup(self, core):
        """決算タイマーを実際に満了させ、決算ポップアップを表示状態にする"""
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )

    def _close_settlement_popup(self, core):
        """決算ポップアップの表示を終え、凍結を解く操作を、実際の精算
        （クリックによる精算。ID-015 サイクル5・_settle_tax()）を経由せずに
        模す。本クラスの関心は完全凍結（表示中は時間経過・保存が止まり、
        閉じると止めた時点の続きから再開すること）であり、精算そのもの
        （税額の減算・矩形の押下判定）は test_main_popup.py の
        TestSettlementPopupSettlement が別途担う。実際の精算を経由すると
        資金が変わってしまい、本クラスの各テストが「閉じても資金・盤面は
        変わらない」ことを凍結の観点だけで確認できなくなるため、ここでは
        資金を変えずに「表示が終わり、凍結が解ける」ことだけを起こす
        （_core_with_settlement_popup_shown() が状態を直接立てるのと
        対になる形）"""
        core._settlement_popup_state = (  # pylint: disable=W0212
            SettlementPopupState.NONE
        )
        for clock in core._freeze_clocks:  # pylint: disable=W0212
            clock.resume()
        core.update()

    def test_sales_growth_save_and_settlement_do_not_progress_while_shown(self):
        """表示中に4つの間隔（売上・他店建設・保存・決算）のいずれのぶんを
        進めても、資金・盤面・保存呼び出し・決算タイマーの残り時間・
        ステータスの残り時間の表示のいずれも変わらないこと（`is_up()` を
        呼び続ける誤実装を弾く）"""
        core = GameCore()
        self._build_player_shop(core)
        self._open_settlement_popup(core)
        money_before = core._money  # pylint: disable=W0212
        shops_before = core._field.get_save_data()  # pylint: disable=W0212
        self.mock_store.save.reset_mock()
        interval = max(
            GameCore.SALES_INTERVAL_MS,
            GameCore.NPC_GROWTH_INTERVAL_MS,
            GameCore.SAVE_INTERVAL_MS,
            GameCore.SETTLEMENT_INTERVAL_MS,
        )
        self._advance_ms(interval)
        core.update()
        self.assertEqual(money_before, core._money)  # pylint: disable=W0212
        self.assertEqual(
            shops_before, core._field.get_save_data()  # pylint: disable=W0212
        )
        self.mock_store.save.assert_not_called()
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self._draw(core)
        tax = self._expected_tax([Shop.BUILD_COST])
        calls = self.test_view.get_call_params()
        # 決算ポップアップ表示中は残り時間・税額のいずれも動かないことを、
        # ID-026 サイクル026-1でアイコン＋数値の組へ分かれた税額側、
        # サイクル026-4で移った2列2行のレイアウト（税額は左列・右詰め）、
        # ID-027 サイクル027-2でバーへ置き換わった残り時間側（プレイテスト
        # 指示によりバーの位置・幅を STATUS_BAR_X / STATUS_BAR_W へ改めた
        # 後のもの）も含めて主張する（主張の意図は変えず、分割・移動・
        # 置き換え後の呼び出しへ書き換えたもの）。残り時間は満了直後に
        # ちょうど間隔へ戻っているため（満杯 = 割合1.0）、凍結中もバーが
        # 満杯（枠と同じ幅の中身）のまま変わらないことを確認する
        line2_y = GameCore.STATUS_Y + GameCore.STATUS_PAD + GameCore.STATUS_LINE_H
        self.assertIn(
            (
                "draw_rectb",
                GameCore.STATUS_BAR_X,
                line2_y,
                GameCore.STATUS_BAR_W,
                GameCore.STATUS_BAR_H,
                GameCore.STATUS_BAR_FRAME_COL,
            ),
            calls,
            calls,
        )
        self.assertIn(
            (
                "draw_rect",
                GameCore.STATUS_BAR_X,
                line2_y,
                GameCore.STATUS_BAR_W,
                GameCore.STATUS_BAR_H,
                GameCore.STATUS_BAR_FILL_COL,
            ),
            calls,
            calls,
        )
        for expected in self._expected_icon_value_right_calls(
            GameCore.STATUS_X + GameCore.STATUS_PAD,
            line2_y,
            *GameCore.ICON_TAX,
            tax,
            GameCore.STATUS_VALUE_MAX_DIGITS,
        ):
            self.assertIn(expected, calls, calls)

    def test_accumulated_progress_does_not_burst_immediately_after_closing(self):
        """`is_up()` を呼ばないだけの実装（実時間ベースのため、閉じた瞬間に
        即座に満了する）を弾く: 表示中に各間隔の3倍ぶん進めてから閉じても、
        閉じた直後のフレームで売上・成長・保存・決算の再表示が一気に起きない
        こと"""
        core = GameCore()
        self._build_player_shop(core)
        self._open_settlement_popup(core)
        money_before = core._money  # pylint: disable=W0212
        shops_before = core._field.get_save_data()  # pylint: disable=W0212
        self.mock_store.save.reset_mock()
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS * 3)
        core.update()  # 表示中のまま。凍結の効果でここでは何も起きない
        self._close_settlement_popup(core)
        self.assertEqual(money_before, core._money)  # pylint: disable=W0212
        self.assertEqual(
            shops_before, core._field.get_save_data()  # pylint: disable=W0212
        )
        self.mock_store.save.assert_not_called()
        self.assertEqual(
            SettlementPopupState.NONE,
            core._settlement_popup_state,  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )

    def test_timer_resumes_from_the_remaining_time_captured_at_freeze(self):
        """凍結中に時間を進めても、閉じた後は「凍結した時点の残り時間」の
        続きから経過し、実際に流れた時間には巻き戻らないこと（他店建設
        間隔タイマーで確認する。停止した時点の残り時間ぶん経つとちょうど
        満了し、1ms 足りなければまだ満了しないことの両方を確かめる。再開時に
        間隔そのものへ巻き戻る誤実装を弾く）。

        決算タイマーは**実際に満了させて**凍結させる（一時停止は
        `GameCore.update()` 内で決算タイマー自身が満了したその場でしか
        呼ばれないため、`core._settlement_popup_state` を SHOWN へ直接
        立てるだけでは凍結が効かない）。他店建設間隔の残り時間に端数（0でも間隔そのもの
        でもない値）を作るため、決算間隔ちょうどの経過を1回でなく**2段階**
        （決算間隔−3000ms → 3000ms）に分けて与える。1段階目の経過で他店
        建設間隔が一度満了して基準時刻がその時点（決算満了の3000ms前）へ
        揃うため、2段階目の3000msだけでは満了せず、決算タイマーが満了した
        瞬間に捉えられる他店建設間隔の残り時間がちょうど7000ms
        （10000−3000）という端数になる"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS - 3000)
        core.update()  # ここで他店建設間隔が一度満了し、基準時刻が揃う
        self._advance_ms(3000)
        core.update()  # ここで決算タイマーが満了し、凍結が始まる
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )
        remaining_before_freeze = (
            core._npc_growth_clock.remaining_ms()  # pylint: disable=W0212
        )
        self.assertEqual(7000, remaining_before_freeze)
        shops_before = core._field.get_save_data()  # pylint: disable=W0212
        self._advance_ms(GameCore.NPC_GROWTH_INTERVAL_MS * 5)
        core.update()
        self.assertEqual(
            remaining_before_freeze,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            shops_before, core._field.get_save_data()  # pylint: disable=W0212
        )
        self._close_settlement_popup(core)
        self.assertEqual(
            remaining_before_freeze,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self._advance_ms(remaining_before_freeze - 1)
        core.update()
        self.assertEqual(
            shops_before, core._field.get_save_data()  # pylint: disable=W0212
        )
        self._advance_ms(1)
        core.update()
        self.assertEqual(
            len(shops_before) + 1,
            len(core._field.get_save_data()),  # pylint: disable=W0212
        )


class TestSettlementClockSaveLoad(TestParent):
    """決算間隔の残り時間の保存・復元（ID-014 サイクル4）に関する振る舞いの
    テスト。他店建設間隔・売上発生間隔の残り時間の保存・復元
    （TestNpcGrowthClockSaveLoad / TestSalesClockSaveLoad。ID-008 サイクル5 /
    ID-010）と同じ形を、ShopClock を挟んだ3件目としてそのまま適用する。

    **既存2件と異なる点**: 本タスクは ReportStore.VERSION を 4 → 5 へ
    繰り上げる（設計判断の章のとおり、ID-008/ID-010 が据え置きを選んだ型
    からの意図的な逸脱）。そのため既存2件が持つ「導入前の保存データに
    キーが無くても後方互換で動く」テスト（test_restoring_data_without_
    saved_remaining_ms_starts_fresh）は本クラスには**無い**。
    「旧バージョン（4）の保存データが読み捨てられる」こと自体は、
    ReportStore.VERSION の具体的な値に依存しない汎用のテストとして
    test_report_store.py の TestReportStore.test_load（"unmatch version"
    ケース。ReportStore.VERSION + 1 で相対的に検証）が既に固定している。
    ここへ version 4 決め打ちのテストを重ねると、VERSION が5から6以降へ
    進むたびに無意味になっていく保守負担だけが残るため、本クラスでは
    持たない（設計判断の章の追記）。

    タイマーの発火は既存2件と同じく、Clock.is_up の差し替えではなく
    time.perf_counter() を固定して時刻そのものを進める形で与える
    （「続きから」経過することは、満了する時刻そのものでしか確認できない）。
    TestParent が既定で掛けている Clock.is_up の無効化は、本クラスの間だけ
    外す。

    決算タイマーの満了は ID-015 サイクル1から決算ポップアップの表示に結びつく
    ようになったが、本クラスが検証するのは保存・復元（残り時間そのものが
    続きから経過すること）であり、その確認手段は従来どおり
    TestSettlementInterval と同じ core._settlement_clock.remaining_ms() を
    直接読む形のままでよい（決算タイマーの満了が決算ポップアップの表示へ
    結びついているかは TestSettlementInterval が、決算ポップアップ自体の
    描画の継続性・描画順は test_main_popup.py の TestSettlementPopupDisplay が
    それぞれ担う）"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # NPC所有店舗だけを復元するケースに使う区画（プレイヤー所有店舗の真上。
    # TestSettlementInterval と同じ）
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1
    RESTORED_MONEY = GameCore.INITIAL_MONEY + 500

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔（60秒）は売上発生間隔（3秒）より長いため、経過のさせ方に
        # よっては売上発生間隔が満了しうる。抽選先を固定して無関係な失敗
        # （乱数源を差し替えていない状態での抽選）を避ける
        # （TestSettlementInterval と同じ理由・同じ与え方）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押す）で
        最初の店舗を建設する（TestSettlementInterval と同じ）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def _restored_player_shop_data(self, remaining_ms):
        """プレイヤー所有店舗が1軒だけあり、決算間隔の残り時間が
        remaining_ms である保存データ"""
        return {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "settlement_remaining_ms": remaining_ms,
            "speed_index": 0,
        }

    def test_save_data_has_no_remaining_ms_before_the_first_player_shop_is_built(
        self,
    ):
        """最初のプレイヤー所有店舗を建設する前（決算タイマーがまだ生成
        されていない）は、保存データの残り時間が None（未開始）であること"""
        core = GameCore()
        self.assertIsNone(
            core._get_save_data()["settlement_remaining_ms"]  # pylint: disable=W0212
        )

    def test_save_data_holds_remaining_ms_after_the_clock_starts(self):
        """最初のプレイヤー所有店舗を建設し、間隔の一部が経過した時点の
        保存データに、満了までの残り時間が正しく含まれること"""
        interval = GameCore.SETTLEMENT_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        elapsed_ms = interval // 4
        self._advance_ms(elapsed_ms)
        self.assertEqual(
            interval - elapsed_ms,
            core._get_save_data()["settlement_remaining_ms"],  # pylint: disable=W0212
        )

    def test_restoring_remaining_ms_continues_from_where_it_left_off(self):
        """残り時間を含む保存データから復元すると、その残り時間の続きから
        経過すること（復元直後に満了しない・既定の間隔ぶん待たされない）。
        検証は TestSettlementInterval と同じく
        core._settlement_clock.remaining_ms() を直接読む（ID-015 サイクル1で
        満了が決算ポップアップの表示に結びついた後も、本テストの関心は
        残り時間そのものの続き方であり、この手段のままでよい）。
        「満たない経過ではまだ満了しない」ケースは、_advance_ms() が経由する
        float 演算の丸み誤差（例: 期待値1msに対し1.000000000007276msなど）を
        避けるため、正確な残り時間ではなく「まだ満了していない（正の値）」
        ことだけを確認する（TestSettlementInterval.
        test_settlement_has_not_expired_just_before_the_interval と同じ理由・
        同じ手段）。満了直後は Clock.is_up() が基準時刻をリセットするため
        丸め誤差が乗らず、間隔そのものへの厳密な一致を確認できる"""
        remaining_ms = GameCore.SETTLEMENT_INTERVAL_MS // 3
        test_cases = [
            ("保存された残り時間に満たない経過ではまだ満了しない", remaining_ms - 1),
            ("保存された残り時間ぶん経つと満了し、間隔まで巻き戻る", remaining_ms),
        ]
        for case_name, elapsed_ms in test_cases:
            with self.subTest(case_name=case_name):
                self._now = 0.0
                # サブテストをまたいで押下・経過時間が残らないようにする
                # （TestNpcGrowthClockSaveLoad と同じ理由）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                self.mock_store.load.return_value = self._restored_player_shop_data(
                    remaining_ms
                )
                core = GameCore()
                self._advance_ms(elapsed_ms)
                core.update()
                if elapsed_ms < remaining_ms:
                    self.assertGreater(
                        core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
                        0,
                    )
                else:
                    self.assertEqual(
                        GameCore.SETTLEMENT_INTERVAL_MS,
                        core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
                    )

    def test_restoring_unstarted_state_does_not_start_the_clock(self):
        """未開始（最初の店舗の建設前）の状態も保存・復元され、リロードで
        勝手に開始しないこと（プレイヤー所有店舗がない保存データで
        settlement_remaining_ms が None のとき）。
        TestSettlementInterval.test_settlement_does_not_start_before_the_
        first_player_shop_is_built（保存データ自体が無い＝
        _apply_load_data(None) の分岐）とは異なるコードパスを確認する：
        本テストは保存データが存在し、その中身が「未開始（None）」である
        ＝ _apply_load_data(data) で data["settlement_remaining_ms"] が
        None の分岐を通ることを固定する（TestNpcGrowthClockSaveLoad /
        TestSalesClockSaveLoad の同名テストと同じ観点）"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": GameCore.INITIAL_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        for _ in range(3):
            self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
            core.update()
        self.assertIsNone(
            core._settlement_clock.remaining_ms()  # pylint: disable=W0212
        )

    def test_all_three_clocks_restore_independently_without_interfering(self):
        """他店建設間隔・売上発生間隔・決算間隔の3つの残り時間が同時に保存・
        復元されても、互いに干渉せず独立に続きから経過すること（要件 3.13
        「各時間間隔の残り時間」）。決算間隔の残り時間**だけ**が満了するに
        足りる短さで復元し、その満了（残り時間の巻き戻り）が他の2つの間隔の
        進行（盤面・資金の据え置き）に影響しないことを確認する。他店建設・
        売上発生の残り時間はいずれも間隔そのもの（この経過では絶対に満了
        しない大きさ）で復元する。決算タイマーが満了するため、draw() の
        期待値には決算ポップアップの背景・枠（ID-015 サイクル1）・
        数値3行（同サイクル2）が付く"""
        player_shop = (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)
        # 売上発生間隔（3,000ms）より短い経過に留め、決算だけを満了させる
        settlement_remaining_ms = 500
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "npc_growth_remaining_ms": GameCore.NPC_GROWTH_INTERVAL_MS,
            "sales_remaining_ms": GameCore.SALES_INTERVAL_MS,
            "settlement_remaining_ms": settlement_remaining_ms,
            "speed_index": 0,
        }
        core = GameCore()
        self._advance_ms(settlement_remaining_ms)
        core.update()
        # 決算だけが満了し、残り時間が間隔まで巻き戻ったこと（復元された
        # 残り時間の続きから経過したことの直接確認）。draw() の秒表示は
        # 切り上げのため、復元を無視して間隔そのものから始まった場合の
        # 残り（59,500ms）と正しく復元された場合の残り（60,000ms）が
        # どちらも 60 秒と表示され区別できない。したがって raw の ms を
        # 直接読む（TestSettlementInterval と同じ理由・同じ手段）
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self._draw(core)
        tax = self._expected_tax([Shop.BUILD_COST])
        self.assertEqual(
            self._expected_field_calls(
                [player_shop],
                # 決算だけが満了しても他店建設・売上はまだ満了していない
                # ため、盤面（NPC所有店舗が増えない）・資金は変わらない
                money=self.RESTORED_MONEY,
                remaining_sec=GameCore.SETTLEMENT_INTERVAL_MS // 1000,
                shop_count=1,
                tax=tax,
            )
            + self._expected_settlement_popup_calls()
            # 決算ポップアップの数値3行（ID-015 サイクル2）。減算前・減算後は
            # 精算前のためいずれもステータスと同じ資金・税額から導出する
            + self._expected_settlement_popup_value_calls(
                self.RESTORED_MONEY, tax, self.RESTORED_MONEY - tax
            )
            # 決算ポップアップの「o」ボタン（ID-015 サイクル5 Refactor・再考）
            + self._expected_settlement_popup_button_calls(),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_all_three_clocks_start_at_boot_when_only_an_npc_owned_shop_is_restored(
        self,
    ):
        """NPC所有店舗だけを含む保存データから復元したときも、他店建設・
        売上発生・決算の3つのタイマーすべてが起動の時点から経過を始める
        こと（要件 3.2。ID-025）。`_shop_clocks` の一覧から1件だけ
        開始を漏らす誤実装——例えば決算だけを反転させ他店建設・売上は
        プレイヤー所有店舗のみを起点のままにする——を弾くため、3つとも
        1つのテストで確認する（`test_all_three_clocks_restore_
        independently_without_interfering` と同じ、一覧を回す形の確認）"""
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.NPC_COL,
                    self.NPC_ROW,
                    Owner.NPC.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": GameCore.INITIAL_MONEY,
            "npc_growth_remaining_ms": None,
            "sales_remaining_ms": None,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SALES_INTERVAL_MS,
            core._sales_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )

    def test_clocks_keep_progressing_after_buying_out_the_restored_npc_shop(self):
        """0軒（NPC所有店舗のみ）で復元した後、その店舗を買収で取得しても
        3つのタイマーが進行し続けること（ID-024からの申し送り①の決着。
        `_buyout_selected_plot()` は `_start_shop_clocks()` を呼ば
        ないが、復元の時点で既に開始済みのため呼ぶ必要が無い——買収の前後で
        決算タイマーの残り時間が連続していることで確認する。買収費用
        （BUILD_COST × BUYOUT_RATE = 200）を賄える資金で復元する）"""
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.NPC_COL,
                    self.NPC_ROW,
                    Owner.NPC.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": Shop.BUILD_COST * Shop.BUYOUT_RATE,
            "npc_growth_remaining_ms": None,
            "sales_remaining_ms": None,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        elapsed_before_buyout = GameCore.SETTLEMENT_INTERVAL_MS // 3
        self._advance_ms(elapsed_before_buyout)
        core.update()

        pos = self._plot_center_pos(self.NPC_COL, self.NPC_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

        self.assertEqual(
            Owner.PLAYER,
            core._field.get_owner(self.NPC_COL, self.NPC_ROW),  # pylint: disable=W0212
        )
        # 買収そのものはタイマーへ触れないため、残り時間は買収前の経過ぶん
        # だけ減った値のまま（間隔まで巻き戻ったり None に戻ったりしない）
        remaining_after_buyout = (
            core._settlement_clock.remaining_ms()
        )  # pylint: disable=W0212
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS - elapsed_before_buyout,
            remaining_after_buyout,
        )
        # 買収後も残り時間の続きから経過し、満了すれば間隔まで巻き戻ること
        self._advance_ms(remaining_after_buyout)
        core.update()
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )


class TestSettlementRemainingRatio(TestParent):
    """決算間隔に対する残り時間の割合（`GameCore._settlement_remaining_
    ratio()`）に関するテスト（ID-027 TDD サイクル 027-1）。プログレスバー
    が読む値そのものだけを扱い、バーの矩形の描画はサイクル 027-2 で扱う
    ため本クラスでは検証しない。

    割合は既存の `T {秒}` 表示と同じ秒粒度（`math.ceil`）で量子化する
    （決定3-A）。生の ms 比率のままだと、`time.perf_counter()` を
    モックしていないテストファイル（`test_main_shop_action.py` など）が
    実時間に依存して不安定になることが実測で分かっているため（サブ
    タスクリストの「既存テストへの影響」参照）。

    決算タイマーは実際の建設操作（`_build_player_shop()`）で起動する
    （`TestSettlementInterval` と同じ経路。タイマーの起点そのものは本
    タスクの範囲外だが、起動の仕方はここでも揃える）。タイマーの発火の
    与え方（time.perf_counter 固定・_advance_ms）も `TestSettlementInterval`
    と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 決算間隔（60秒）は売上発生間隔（3秒）より長いため、経過中に売上
        # 発生間隔が必ず満了する。抽選先を固定して無関係な失敗を避ける
        # （TestSettlementInterval と同じ理由・同じ与え方）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作で最初の店舗を建設し、決算タイマーを起動する
        （`TestSettlementInterval` と同じ経路）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _press_pause_button(self, core):
        """ポーズボタンの矩形の中心を1回押して離す"""
        x, y, w, h = self._expected_status_pause_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def _press_speed_button(self, core):
        """スピードボタンの矩形の中心を1回押して離す"""
        x, y, w, h = self._expected_status_speed_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def _open_settlement_popup(self, core):
        """決算タイマーを実際に満了させ、決算ポップアップを表示状態にする
        （`TestSettlementPopupFreezesTime` と同じ経路）"""
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )

    def test_ratio_is_full_before_the_first_player_shop_is_built(self):
        """店舗が1軒もなく決算タイマーが未開始のとき、割合は満杯（1.0）に
        なること（決定4-A。remaining_ms() が None を返す「未開始」を、
        バーは満杯として読み替える——既存の T {秒} 表示が未開始のとき
        間隔そのものを表示する〈ID-025〉のと同じ読み替えを割合へも写す）"""
        core = GameCore()
        self.assertIsNone(
            core._settlement_clock.remaining_ms()  # pylint: disable=W0212
        )
        self.assertEqual(
            1.0, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )

    def test_ratio_is_full_immediately_after_building_the_first_shop(self):
        """建設した直後（未経過）は割合が満杯（1.0）になること"""
        core = GameCore()
        self._build_player_shop(core)
        self.assertEqual(
            1.0, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )

    def test_ratio_equals_the_fraction_of_the_interval_remaining(self):
        """決算間隔の半分だけ経過すると割合が0.5になること（秒粒度で
        割り切れる経過を選び、量子化の丸めが結果に影響しないようにする）"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS // 2)
        core.update()
        self.assertEqual(
            0.5, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )

    def test_ratio_reaches_zero_and_does_not_go_negative_past_expiry(self):
        """満了の瞬間に0になり、間隔を過ぎても負にならないこと
        （`Clock.remaining_ms()` が0で頭打ちにする振る舞いが割合へも
        伝わることの確認）。`core.update()` を呼ばず、is_up() による
        周期の巻き戻し（満了のたびに残り時間が間隔まで戻る）が起きる
        前の状態で読む"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS * 3)
        self.assertEqual(
            0.0, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )

    def test_ratio_granularity_is_seconds(self):
        """割合の粒度が秒であること: 決算間隔の1/60（=1秒）未満の経過
        では割合が変わらず、1秒ちょうど経過すると変わること（決定3-A）"""
        core = GameCore()
        self._build_player_shop(core)
        full_ratio = core._settlement_remaining_ratio()  # pylint: disable=W0212
        self._advance_ms(999)
        core.update()
        self.assertEqual(
            full_ratio, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )
        self._advance_ms(1)
        core.update()
        self.assertNotEqual(
            full_ratio, core._settlement_remaining_ratio()  # pylint: disable=W0212
        )

    def test_ratio_is_unaffected_by_a_game_speed_change(self):
        """ゲームスピードを変更しても、変更の前後で割合が変わらないこと
        （残り時間が `Clock.scale_remaining_ms()` で新旧の間隔の比率へ
        スケールされるため）。**分母に開始済みの `ShopClock._count_ms`
        （change_count_ms() で更新されない古い値）を使う誤実装を弾く**
        本サイクルの中心の主張——そこを分母にすると、スピードを上げた
        直後に割合が誤って縮む（サブタスクリストの「落とし穴」参照）"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS // 2)
        core.update()
        ratio_before = core._settlement_remaining_ratio()  # pylint: disable=W0212
        self._press_speed_button(core)  # 除数1→3
        self._press_speed_button(core)  # 除数3→10
        self.assertEqual(
            ratio_before,
            core._settlement_remaining_ratio(),  # pylint: disable=W0212
        )

    def test_ratio_is_frozen_while_paused(self):
        """ポーズ中は割合が変わらないこと（分子〈残り時間〉が固定される
        ため。tasks.md のチェック項目4に対応）"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(2000)
        core.update()
        self._press_pause_button(core)
        ratio_before = core._settlement_remaining_ratio()  # pylint: disable=W0212
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            ratio_before,
            core._settlement_remaining_ratio(),  # pylint: disable=W0212
        )

    def test_ratio_is_frozen_while_the_settlement_popup_is_shown(self):
        """決算ポップアップ表示中（完全凍結）は割合が変わらないこと
        （tasks.md のチェック項目4に対応）。満了直後は残り時間がちょうど
        間隔まで戻っているため（割合1.0）、凍結の有無を区別できるよう
        間隔の半分だけ経過させてから確認する（凍結していなければ0.5へ
        下がるはずの経過）"""
        core = GameCore()
        self._build_player_shop(core)
        self._open_settlement_popup(core)
        ratio_before = core._settlement_remaining_ratio()  # pylint: disable=W0212
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS // 2)
        core.update()
        self.assertEqual(
            ratio_before,
            core._settlement_remaining_ratio(),  # pylint: disable=W0212
        )


class TestGameSpeedAppliesToTimers(TestParent):
    """スピードボタンの押下で切り替わる段階（GameCore.GAME_SPEED_STEPS の
    添字）が、他店建設・売上・決算の3つのタイマーへ実際に反映され、保存
    タイマー（`_save_clock`）はその影響を受けないことに関するテスト
    （ID-019 サイクル5）。段階そのもの・ラベルの循環表示は前サイクルの
    `TestStatusSpeedButtonCycle`（test_main_popup.py）が確認済みのため、
    ここでは段階がタイマーの待機時間・残り時間へどう効くかだけを見る
    （分類ルール2。押下判定を経由しないタイマーの反映は clock、押下判定
    そのもの・ラベルの循環は popup、という分け方は ID-019_subtasks.md の
    対応表どおり）。

    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    `TestSettlementPopupFreezesTime` と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる（他クラスと
        # 同じ理由。無関係な失敗を避ける）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作で最初の店舗を建設し、3つのタイマーを起動する
        （`TestSettlementPopupFreezesTime` と同じ経路）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _press_speed_button(self, core):
        """スピードボタンの矩形の中心を1回押して離し、段階を1つ進める"""
        x, y, w, h = self._expected_status_speed_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def test_switching_speed_scales_the_remaining_time_of_all_three_timers(self):
        """スピードを等倍（>）から3倍（>>）へ切り替えると、他店建設・売上・
        決算の3タイマーいずれも残り時間が新旧の間隔の比率（÷3）でスケール
        されること。切り替え直前はいずれも残り時間が待機時間そのものと
        一致している（建設直後で未経過）ため、期待値がちょうど割り切れる"""
        core = GameCore()
        self._build_player_shop(core)
        self._press_speed_button(core)  # index 0 -> 1（除数 3）
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS // 3,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SALES_INTERVAL_MS // 3,
            core._sales_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS // 3,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )

    def test_switching_speed_does_not_affect_the_save_timer(self):
        """スピードを切り替えても保存タイマー（`_save_clock`）の間隔は
        `SAVE_INTERVAL_MS` のまま変わらないこと（要件 3.12 に列挙された
        3タイマーの対象外）。切り替え後 `SAVE_INTERVAL_MS` 未満の経過では
        保存されず、ちょうど `SAVE_INTERVAL_MS` 経つと保存されることで、
        間隔がスケールされていないことを確認する（スケールされていれば
        1ms 手前の経過で既に保存されてしまうはずの誤実装を弾く）"""
        core = GameCore()
        self._build_player_shop(core)
        self._press_speed_button(core)  # 除数 3 へ
        self.mock_store.save.reset_mock()
        self._advance_ms(GameCore.SAVE_INTERVAL_MS - 1)
        core.update()
        self.mock_store.save.assert_not_called()
        self._advance_ms(1)
        core.update()
        self.mock_store.save.assert_called()

    def test_events_fire_at_the_new_interval_after_switching_to_the_fastest_speed(
        self,
    ):
        """最高速（>>>、除数10）へ切り替えた後、他店建設・売上・決算の
        いずれも新しい待機時間（基準間隔 ÷ 10）でちょうど発生すること
        （各段階の除数が実際に 1 / 3 / 10 であることの確認）。売上は
        発生額そのもの（`Shop.SALES_AMOUNT`）も併せて確認し、スピードを
        変えても待機時間が短くなるだけでゲームルール上の結果（額）は
        変わらないこと（要件 3.12）も同時に確かめる"""
        cases = (
            ("npc", "NPC_GROWTH_INTERVAL_MS"),
            ("sales", "SALES_INTERVAL_MS"),
            ("settlement", "SETTLEMENT_INTERVAL_MS"),
        )
        for target, interval_attr in cases:
            with self.subTest(target=target):
                self._now = 0.0
                # サブテストをまたいで押下・経過時間が残らないようにする
                # （TestNpcGrowthInterval の subTest と同じ理由）
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                core = GameCore()
                self._build_player_shop(core)
                self._press_speed_button(core)  # 除数 3
                self._press_speed_button(core)  # 除数 10
                new_interval_ms = getattr(GameCore, interval_attr) // 10
                shops_before = core._field.get_save_data()  # pylint: disable=W0212
                money_before = core._money  # pylint: disable=W0212
                self._advance_ms(new_interval_ms)
                core.update()
                if target == "npc":
                    self.assertEqual(
                        len(shops_before) + 1,
                        len(core._field.get_save_data()),  # pylint: disable=W0212
                    )
                elif target == "sales":
                    self.assertEqual(
                        money_before + Shop.SALES_AMOUNT,
                        core._money,  # pylint: disable=W0212
                    )
                else:
                    self.assertEqual(
                        SettlementPopupState.SHOWN,
                        core._settlement_popup_state,  # pylint: disable=W0212
                    )

    def test_completing_one_full_cycle_returns_timers_to_the_original_interval(
        self,
    ):
        """スピードを >→>>→>>>→> と1周させると（押下3回）、他店建設・売上・
        決算のいずれの残り時間も元の間隔（等倍）へ戻ること。3回とも押下の
        間に時間を進めないため、各切り替え直前の残り時間はちょうど直前の
        待機時間と一致しており（`Clock.scale_remaining_ms()` が
        `old_count_ms` で正確に割り切れる）、往復しても丸め誤差が乗らない"""
        core = GameCore()
        self._build_player_shop(core)
        for _ in range(3):
            self._press_speed_button(core)
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SALES_INTERVAL_MS,
            core._sales_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )


class TestPauseHaltsAndResumesTimers(TestParent):
    """ポーズボタンの押下による一時停止・解除が、保存・他店建設・売上・
    決算の4つのタイマー（`GameCore._freeze_clocks`）へ実際に反映される
    ことに関するテスト（ID-019 サイクル7）。ポーズ状態の保持・2つの
    ボタンの押下判定・配色は前サイクルの `TestStatusPauseButtonToggle`
    （test_main_popup.py）が確認済みのため、ここではポーズがタイマーへ
    どう効くかだけを見る（分類ルール2。押下判定を経由しないタイマーの
    反映は clock、押下判定そのもの・配色の入れ替えは popup、という
    分け方は `TestGameSpeedAppliesToTimers` と同じ境界）。

    ポーズの対象は決算・終了の凍結と同じ `_freeze_clocks`（保存タイマー
    を含む4件。設計方針4の「要確認」を4件で決着）。決算ポップアップの
    精算（`_settle_tax()`）での再開がポーズ中には効かないこと（設計方針4）
    は、決算ポップアップ自体の状態遷移を伴うため test_main_popup.py の
    `TestPauseCoexistsWithFieldOperationsAndSettlement` に置く。

    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    `TestGameSpeedAppliesToTimers` と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    NPC_COL = PLAYER_COL
    NPC_ROW = PLAYER_ROW - 1

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる
        # （TestGameSpeedAppliesToTimers と同じ理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作で最初の店舗を建設し、3つのタイマーを起動する
        （`TestGameSpeedAppliesToTimers` と同じ経路）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _press_pause_button(self, core):
        """ポーズボタンの矩形の中心を1回押して離す"""
        x, y, w, h = self._expected_status_pause_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def _press_speed_button(self, core):
        """スピードボタンの矩形の中心を1回押して離す"""
        x, y, w, h = self._expected_status_speed_button_rect()
        pos = (x + w // 2, y + h // 2)
        self._press(core, pos)
        self._release(core)

    def test_pausing_halts_all_four_timers_and_advancing_time_triggers_nothing(
        self,
    ):
        """ポーズ中は保存・他店建設・売上・決算のいずれの間隔ぶん進めても
        資金・盤面・保存呼び出し・決算ポップアップの表示のいずれも変わら
        ないこと（`is_up()` を呼び続ける誤実装、および対象を3タイマーの
        みにする誤実装の両方を弾く）"""
        core = GameCore()
        self._build_player_shop(core)
        self._press_pause_button(core)
        money_before = core._money  # pylint: disable=W0212
        shops_before = core._field.get_save_data()  # pylint: disable=W0212
        self.mock_store.save.reset_mock()
        interval = max(
            GameCore.SALES_INTERVAL_MS,
            GameCore.NPC_GROWTH_INTERVAL_MS,
            GameCore.SAVE_INTERVAL_MS,
            GameCore.SETTLEMENT_INTERVAL_MS,
        )
        self._advance_ms(interval)
        core.update()
        self.assertEqual(money_before, core._money)  # pylint: disable=W0212
        self.assertEqual(
            shops_before, core._field.get_save_data()  # pylint: disable=W0212
        )
        self.mock_store.save.assert_not_called()
        self.assertEqual(
            SettlementPopupState.NONE,
            core._settlement_popup_state,  # pylint: disable=W0212
        )

    def test_resuming_via_either_button_continues_from_the_remaining_time_captured_at_pause(
        self,
    ):
        """ポーズ解除は、押したボタン（ポーズ・スピードのいずれ）に
        よらず、止めた時点の残り時間の続きから再開すること（設計方針
        6-1）。止めた時点の残り時間ぶん経過するとちょうど満了し、1ms
        足りなければまだ満了しないことの両方で、実際に流れた時間へ
        巻き戻らないことを確かめる（`TestSettlementPopupFreezesTime.
        test_timer_resumes_from_the_remaining_time_captured_at_freeze`
        と同じ観点をポーズについて確認する）"""
        for which_button in ("pause", "speed"):
            with self.subTest(which_button=which_button):
                self._now = 0.0
                # サブテストをまたいで押下・経過時間が残らないようにする
                self.test_input.set_down(False)
                self.test_input.set_pos(0, 0)
                core = GameCore()
                self._build_player_shop(core)
                # 端数を作るため、ポーズする前に少しだけ経過させる
                self._advance_ms(2000)
                core.update()
                self._press_pause_button(core)
                remaining_before_pause = (
                    core._npc_growth_clock.remaining_ms()  # pylint: disable=W0212
                )
                self.assertEqual(
                    GameCore.NPC_GROWTH_INTERVAL_MS - 2000, remaining_before_pause
                )
                # ポーズ中に大きく進めても凍結されたまま変わらない
                self._advance_ms(GameCore.NPC_GROWTH_INTERVAL_MS * 5)
                core.update()
                self.assertEqual(
                    remaining_before_pause,
                    core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
                )
                if which_button == "pause":
                    self._press_pause_button(core)
                else:
                    self._press_speed_button(core)
                self.assertEqual(
                    remaining_before_pause,
                    core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
                )
                shops_before = core._field.get_save_data()  # pylint: disable=W0212
                self._advance_ms(remaining_before_pause - 1)
                core.update()
                self.assertEqual(
                    shops_before,
                    core._field.get_save_data(),  # pylint: disable=W0212
                )
                self._advance_ms(1)
                core.update()
                self.assertEqual(
                    len(shops_before) + 1,
                    len(core._field.get_save_data()),  # pylint: disable=W0212
                )

    def test_no_settlement_popup_appears_while_paused(self):
        """ポーズ中は決算タイマー自体が止まっているため、決算間隔の何倍
        進めても決算ポップアップが現れないこと"""
        core = GameCore()
        self._build_player_shop(core)
        self._press_pause_button(core)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS * 3)
        core.update()
        self.assertEqual(
            SettlementPopupState.NONE,
            core._settlement_popup_state,  # pylint: disable=W0212
        )

    def test_switching_speed_after_exiting_pause_applies_the_new_interval_correctly(
        self,
    ):
        """ポーズ → 解除 → スピード切り替え の順でも、切り替え後の待機
        時間が正しく反映されること（019-5 との組み合わせの回帰。ポーズの
        導入が既存のスピード切り替えの計算を壊していないことを確かめる）。
        解除の押下では段階が進まないため、解除直後はまだ等倍（除数1）で
        あり、続けてスピードボタンを押して初めて除数3へ進む"""
        core = GameCore()
        self._build_player_shop(core)
        self._press_pause_button(core)
        self._advance_ms(1000)
        core.update()
        self._press_pause_button(core)  # 解除。段階は進まない
        self._press_speed_button(core)  # ここで初めて除数3へ進む
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS // 3,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SALES_INTERVAL_MS // 3,
            core._sales_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS // 3,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )


class TestGameSpeedRestoresTimersAtTheSavedSpeed(TestParent):
    """保存データのスピード段階（speed_index）が、他店建設・売上・決算の
    3タイマーへ残り時間・**待機時間**の組で正しく反映されて復元されることに
    関するテスト（ID-019 サイクル8）。保存データのキーの追加・欠落時の
    既定は test_main_save.py の TestGameSpeedSaveLoad が担う（分類ルール2。
    ここではタイマー固有の状態遷移を伴う「残り時間との組」を確認する）。

    **残り時間だけを見るテストでは不十分な理由**: Clock.is_up() は満了した
    瞬間に基準時刻をその場（now）へ置き直すため、残り時間（_bef の
    オフセット）が正しく復元されていれば、満了した瞬間の待機時間
    （_count_ms）が誤って等倍のまま復元されていても**1回目の満了は
    正しいタイミングで起きてしまい区別できない**（2回目以降の満了だけが
    等倍の間隔にずれる）。これはユーザーが指摘した「ゲーム再起動で速度が
    通常に戻ると、残り時間に不整合が出る」という懸念そのものであるため、
    満了を連続で2回起こし、いずれも復元した段階の待機時間で起きることを
    確認する。

    **「保存データに speed_index キーが無い」ケースのテストは無い**:
    本タスクは ID-018 と ID-019 の保存データに互換性が無いという
    ユーザーの明示的な指示により ReportStore.VERSION を 6 → 7 へ
    繰り上げ、GameCore._apply_load_data() は speed_index を .get() を
    経ずに直接読む（test_main_save.py の TestGameSpeedSaveLoad の
    docstring を参照）。VERSION が一致した保存データには speed_index が
    必ず存在するため、キー欠落を復元する経路自体が実装上存在しない"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    RESTORED_MONEY = GameCore.INITIAL_MONEY

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 売上の抽選は常に起点のプレイヤー所有店舗を選ばせる
        # （TestGameSpeedAppliesToTimers と同じ理由）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )

    def tearDown(self):
        self.patcher_perf_counter.stop()
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _restored_data(self, speed_index):
        """プレイヤー所有店舗が1軒だけあり、指定したスピード段階
        （speed_index）で保存されたデータ。3タイマーの残り時間は、
        いずれも「ちょうど切り替え直後（残り時間＝待機時間そのもの）」と
        して保存されたものとする（保存時に等倍へ換算し直さない。
        設計方針7・ID-019_subtasks.md）"""
        divisor = GameCore.GAME_SPEED_STEPS[speed_index][1]
        return {
            "shops": [
                [
                    self.PLAYER_COL,
                    self.PLAYER_ROW,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            "money": self.RESTORED_MONEY,
            "speed_index": speed_index,
            "npc_growth_remaining_ms": GameCore.NPC_GROWTH_INTERVAL_MS // divisor,
            "sales_remaining_ms": GameCore.SALES_INTERVAL_MS // divisor,
            "settlement_remaining_ms": GameCore.SETTLEMENT_INTERVAL_MS // divisor,
        }

    def test_restoring_a_non_default_speed_index_scales_the_remaining_time_of_all_three_timers(
        self,
    ):
        """最高速（添字2、除数10）で保存されたデータから復元すると、他店
        建設・売上・決算の3タイマーいずれも残り時間が復元直後から除数10で
        スケールされた値のままであること（保存された値をそのまま使い、
        等倍への再換算をしないこと。設計方針7）"""
        self.mock_store.load.return_value = self._restored_data(speed_index=2)
        core = GameCore()
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS // 10,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SALES_INTERVAL_MS // 10,
            core._sales_clock.remaining_ms(),  # pylint: disable=W0212
        )
        self.assertEqual(
            GameCore.SETTLEMENT_INTERVAL_MS // 10,
            core._settlement_clock.remaining_ms(),  # pylint: disable=W0212
        )

    def test_the_waiting_time_after_the_first_expiry_also_stays_at_the_saved_speed(
        self,
    ):
        """最高速（添字2、除数10）で保存されたデータから復元すると、他店
        建設タイマーが満了した直後の残り時間（＝次の満了までの待機時間）も
        除数10でスケールされたままであること。復元時に段階（speed_index）を
        3タイマーへ反映せず残り時間だけを復元した誤実装だと、満了直後の
        残り時間が等倍の間隔（NPC_GROWTH_INTERVAL_MS）に戻ってしまう——
        本テストのクラス docstring が説明する不整合そのものを固定する"""
        self.mock_store.load.return_value = self._restored_data(speed_index=2)
        core = GameCore()
        new_interval_ms = GameCore.NPC_GROWTH_INTERVAL_MS // 10
        self._advance_ms(new_interval_ms)
        core.update()
        self.assertEqual(
            new_interval_ms,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )

    def test_events_fire_twice_in_a_row_at_the_saved_speeds_interval(self):
        """最高速（添字2、除数10）で保存されたデータから復元すると、他店
        建設が復元後の待機時間（NPC_GROWTH_INTERVAL_MS // 10）でちょうど
        2回連続して発生すること（1回目だけでなく2回目も同じ短い間隔で
        起きることを、実際に街が2軒増える形で確認し、上の remaining_ms()
        による確認を実際のイベント発生でも裏付ける）"""
        self.mock_store.load.return_value = self._restored_data(speed_index=2)
        core = GameCore()
        new_interval_ms = GameCore.NPC_GROWTH_INTERVAL_MS // 10
        shops_before = len(core._field.get_save_data())  # pylint: disable=W0212
        for _ in range(2):
            self._advance_ms(new_interval_ms)
            core.update()
        self.assertEqual(
            shops_before + 2,
            len(core._field.get_save_data()),  # pylint: disable=W0212
        )


class TestShopClocksAfterSellingOutAllShops(TestParent):
    """全プレイヤー所有店舗を売却（ID-016）した後も、他店建設・売上発生・
    決算の3つのタイマー（ShopClock）が未開始へ戻らず、周期的な満了を
    引き続き繰り返すことの回帰テスト。`ShopClock` の docstring
    （main.py:105-108）が「ID-016（税金が払えないときの店舗売却）は
    プレイヤー所有店舗が0軒になり得る唯一の経路であり、そこで街の成長や
    売上が止まるのは要件にない振る舞いになる」と本タスクを名指しで
    予告しており、その決着として ID-016 の完了フェーズ（TASK-016-11）に置く
    （案8の但し書き。main 側を薄く保つ方針の唯一の例外）。

    本タスクは各タイマーに一切触れておらず、新規の振る舞いを追加した
    わけではない。「一度開始したら未開始へ戻さない」という
    `ShopClock` 既存の設計が、ID-016 が実際に作る唯一の経路
    （プレイヤー所有店舗が0軒になる）でも成り立つことを確認する回帰
    テストである。

    起点（プレイヤー所有店舗の建設）・満了の与え方（time.perf_counter
    固定・_advance_ms）は TestSettlementInterval と、決算ポップアップを
    実際に満了させて精算する経路は
    TestSettlementPopupSettlement（test_main_popup.py）と同じ"""

    PLAYER_COL = 0
    PLAYER_ROW = 2

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
        # 抽選先を固定して無関係な失敗を避ける（TestSettlementInterval と
        # 同じ理由・同じ与え方）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: (
            self.PLAYER_COL,
            self.PLAYER_ROW,
        )
        # 資金不足時の売却（ID-016）の抽選先。本クラスの盤面はプレイヤー
        # 所有店舗が常に1軒のため、対象は常にその1軒のみ
        # （TestSettlementPopupSettlement と同じ与え方）
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_player_shop(self, core):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押して
        離す）で唯一のプレイヤー所有店舗を建設する（TestSettlementPopup
        Settlement._core_with_settlement_popup_expired() と同じ、後続の
        押下判定が残留状態に引きずられないよう最後まで離し切る形）"""
        pos = self._plot_center_pos(self.PLAYER_COL, self.PLAYER_ROW)
        self._press(core, pos)
        self._release(core)
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(
            popup_x, GameCore.POPUP_BTN_INDEX_O
        )
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def _sell_out_the_only_player_shop(self, core):
        """唯一のプレイヤー所有店舗へ増資したうえで、決算タイマーを実際に
        満了させ、資金を0にしたうえで決算ポップアップの「o」を押し、その
        店舗を売却させる（TestSettlementPopupSettlement.test_press_inside_
        settles_money_and_closes_popup の「資金 < 税額」ケースと同じ経路。
        売る店舗が1軒しか無ければ、その1軒が売られて尽きる）。
        **不足額は売却で必ず賄える大きさにする**: 増資後の資産価値
        （Shop.BUILD_COST + Shop.INVEST_COST = 250。列0は地域価格倍率が
        等倍のためそのままの額）ぶんの税額（250 * Field.ASSET_TAX_RATE_
        PERCENT // 100 = 12）は売却額（250 // 2 = 125）より小さいため、
        資金0からの精算はその1軒の売却で必ず賄える。
        **増資が必要な理由（ID-024）**: 増資しないまま（資産価値
        Shop.BUILD_COST = 100）売却すると、売却額（50）は不足額（税額5）を
        上回っても、0軒になった後の資金（45）が最小取得費用（盤面がほぼ
        空のため Shop.BUILD_COST = 100）を下回り、事業継続の判定
        （要件 3.15）が新たにゲームオーバーを成立させて4タイマーを止めて
        しまう。増資して売却額を最小取得費用（100）以上に引き上げること
        （125 ≥ 100）で、本クラスが確認したい「売却で税を払えた場合は
        ゲームが続く」場面（要件 3.9。ShopClock の docstring が
        名指しで述べる性質）を保つ。売り尽くしてもなお足りない場合は
        ゲームオーバー（ID-017）が成立し、時間経過そのものが止まる
        （TestGameEndFreezesTime）ため、いずれにせよ不足額を必ず賄える
        大きさにしておく必要がある"""
        core._field.invest_shop(
            self.PLAYER_COL, self.PLAYER_ROW
        )  # pylint: disable=W0212
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        core._money = 0  # pylint: disable=W0212
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)

    def test_all_clocks_keep_running_after_selling_out_the_only_player_shop(self):
        """決算の精算で唯一のプレイヤー所有店舗を売却させ0軒にしたうえで
        時間を進め、他店建設・売上発生・決算の3つのタイマーがいずれも
        未開始（remaining_ms が None）へ戻らず、引き続き満了し続けることを
        確認する。売却された店舗は NPC所有店舗として盤面に残るため、他店
        建設（成長対象）・売上（所有者を問わない抽選対象）のいずれも
        引き続き起こり得ることも併せて確認する（ShopClock の
        docstring が本タスクを名指しで予告している性質の決着）"""
        core = GameCore()
        self._build_player_shop(core)
        self._sell_out_the_only_player_shop(core)

        # プレイヤー所有店舗が0軒になったこと（本回帰テストの前提）
        self.assertEqual(
            Owner.NPC,
            core._field.get_owner(  # pylint: disable=W0212
                self.PLAYER_COL, self.PLAYER_ROW
            ),
        )
        # 3つのタイマーがいずれも未開始（None）へ戻っていないこと
        self.assertIsNotNone(
            core._npc_growth_clock.remaining_ms()  # pylint: disable=W0212
        )
        self.assertIsNotNone(core._sales_clock.remaining_ms())  # pylint: disable=W0212
        self.assertIsNotNone(
            core._settlement_clock.remaining_ms()  # pylint: disable=W0212
        )

        # 他店建設間隔が満了し続けること（売却された店舗はNPC所有として
        # 残り、成長対象になり続けるため成長そのものも起こる）
        self._advance_ms(GameCore.NPC_GROWTH_INTERVAL_MS)
        core.update()
        self.assertEqual(
            GameCore.NPC_GROWTH_INTERVAL_MS,
            core._npc_growth_clock.remaining_ms(),  # pylint: disable=W0212
        )

        # 売上発生間隔が満了し続けること（抽選対象は所有者を問わないため、
        # 売却された店舗が引き続き対象になる）
        self.test_random_source.pick_sales_shop.reset_mock()
        self._advance_ms(GameCore.SALES_INTERVAL_MS)
        core.update()
        self.test_random_source.pick_sales_shop.assert_called_once()

        # 決算間隔が満了し続け、決算ポップアップが再び現れること
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        self.assertEqual(
            SettlementPopupState.SHOWN,
            core._settlement_popup_state,  # pylint: disable=W0212
        )


class TestGameEndFreezesTime(TestParent):
    """ゲーム終了（クリア／ゲームオーバー）が成立した後は、保存・他店建設・
    売上・決算の4つのタイマーの経過がすべて止まり、**再開しない**こと
    （要件「ゲーム終了後」。ID-017 サイクル4・案5）に関するテスト。
    発生契機は操作（建設・買収・精算）だが、検証対象が時間経過の停止で
    あるため、決算ポップアップの完全凍結（TestSettlementPopupFreezesTime）
    と同じファイルに置く（分類ルール3）。

    決算ポップアップの凍結との違いは**解く契機が無い**こと。決算は精算で
    必ず再開するが、終了の凍結は解けない（出口は ID-018 のリセットのみ）。
    クリア・ゲームオーバーのいずれも精算（_settle_tax()）の中で起きるため
    （ID-028 でクリアの判定契機が建設・買収から精算へ移った）、**精算が
    必ず行う resume() の直後に凍結し直される**ことがそのまま検証対象になる
    （resume() だけが残り、時間が動き続ける誤実装を弾く）。

    「何も進まない」ことは、**終了直後に描いた画面と、時間を進めた後に
    描いた画面が1件も違わないこと**で確認する（4つのタイマーそれぞれの
    残り時間を個別に読まない）。売上（資金の増加と抽選の囲み）・他店建設
    （盤面の店舗）・決算（決算ポップアップの再出現）はいずれも画面に現れる
    ため、1つの全件一致でまとめて捉えられる。画面に現れない保存だけは
    self.mock_store.save の呼び出しの有無で確認する。

    タイマーの発火の与え方（time.perf_counter 固定・_advance_ms）は
    TestSettlementInterval と同じ"""

    # ゲームオーバー側で唯一のプレイヤー所有店舗を建てる区画（他の
    # TestXInterval と同じ。画面左半分 → ポップアップは右下）
    PLAYER_COL = 0
    PLAYER_ROW = 2
    # クリア側で決算まわりの税額を固定する（本クラスの盤面は規定店舗数
    # 分の店舗を持つため、実際の Field.total_tax() は座標ごとの地域価格
    # 倍率が絡み予測しづらい。TestGameEndPopup._core_with_fixed_tax() と
    # 同じ考え方）
    CLEAR_TAX = 30

    def setUp(self):
        super().setUp()
        # Clock を実物として動かすため、TestParent の無効化を外す
        self.patcher_clock.stop()
        self._now = 0.0
        self.patcher_perf_counter = patch.object(
            time, "perf_counter", side_effect=lambda: self._now
        )
        self.patcher_perf_counter.start()
        # 凍結が効かなかった場合に売上の抽選が走る。どの店舗が選ばれるかは
        # 本クラスの関心ではないため、対象の先頭を常に選ばせる（盤面が
        # テストごとに異なるため区画を直接指定せず、対象から選ぶ形にする）
        self.test_random_source.pick_sales_shop.side_effect = lambda targets: targets[0]
        # 資金不足時の売却（ID-016）の抽選先。ゲームオーバー側の盤面は
        # プレイヤー所有店舗が1軒のみのため、対象は常にその1軒
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]

    def tearDown(self):
        self.patcher_perf_counter.stop()
        # setUp で外した無効化を掛け直し、TestParent.tearDown() が対称に
        # 止められる状態へ戻す
        self.patcher_clock.start()
        super().tearDown()

    def _advance_ms(self, ms):
        """経過時間を ms ミリ秒進める（実時間には依存しない）"""
        self._now += ms / 1000

    def _build_plot(self, core, col, row):
        """プレイヤーの操作（区画を押して離し、ポップアップの「o」を押して
        離す）で (col, row) へ店舗を建設する（TestSettlementInterval の
        _build_player_shop() と同じ経路。建設する区画がテストごとに異なる
        ため引数で受ける）。最後まで離し切るのは、続く押下判定（決算
        ポップアップの「o」）が残留状態に引きずられないようにするため"""
        self._press_plot_and_o_button(core, col, row)
        self._release(core)

    def _drawn_calls(self, core):
        """いまの状態で draw() を1回行い、その描画呼び出し列を返す"""
        self._draw(core)
        return self.test_view.get_call_params()

    def _advance_past_every_interval(self, core):
        """4つの間隔（保存・他店建設・売上・決算）のうち最も長いぶんの時間を
        進めて update() を1フレーム回す。凍結が効いていなければ4つとも
        満了する（最も長い間隔を選ぶことで、4つを個別に進めなくても
        すべての満了をこの1フレームへ集められる）"""
        self._advance_ms(
            max(
                GameCore.SAVE_INTERVAL_MS,
                GameCore.NPC_GROWTH_INTERVAL_MS,
                GameCore.SALES_INTERVAL_MS,
                GameCore.SETTLEMENT_INTERVAL_MS,
            )
        )
        core.update()

    def test_nothing_progresses_after_the_clear(self):
        """規定店舗数（Field.CLEAR_SHOP_COUNT）ちょうどの盤面で決算を通過し
        クリアが成立した後、4つの間隔のうち最も長いぶんの時間を進めても、
        画面（資金・盤面・売上の囲み・決算ポップアップの再出現）が1件も
        変わらず、定期保存も走らないこと。

        クリアの成立契機は建設・買収から精算（_settle_tax()）へ移った
        （ID-028。要件 3.16）ため、ゲームオーバー側
        （test_nothing_progresses_after_the_game_over）と同じく決算
        ポップアップの「o」ボタン押下で成立させる。盤面は規定店舗数
        ちょうどのため他店建設の成長対象（空き区画）が残っており、凍結が
        効いていることは他店建設が止まることでもこの画面の一致で捉え
        られる（対象そのものが無いために画面に現れないゲームオーバー側とは
        異なる観点）"""
        core = GameCore()
        self._build_plot(core, self.PLAYER_COL, self.PLAYER_ROW)
        for col, row in self._player_shop_positions(Field.CLEAR_SHOP_COUNT):
            if (col, row) == (self.PLAYER_COL, self.PLAYER_ROW):
                continue
            core._field.set_shop(col, row, Owner.PLAYER)  # pylint: disable=W0212
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        core._money = self.CLEAR_TAX  # pylint: disable=W0212
        patcher_tax = patch.object(
            core._field,  # pylint: disable=W0212
            "total_tax",
            return_value=self.CLEAR_TAX,
        )
        patcher_tax.start()
        self.addCleanup(patcher_tax.stop)
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)
        screen_at_the_end = self._drawn_calls(core)
        # クリアが実際に成立していること（成立していなければタイマーが
        # 動いたままでも画面が変わらず、本テストが素通りしてしまう）
        self.assertIn(
            self._expected_game_end_popup_message_call(GameCore.GAME_END_MESSAGE_CLEAR),
            screen_at_the_end,
        )
        self.mock_store.save.reset_mock()
        self._advance_past_every_interval(core)
        self.assertEqual(
            screen_at_the_end, self._drawn_calls(core), self.test_view.get_call_params()
        )
        self.mock_store.save.assert_not_called()

    def test_nothing_progresses_after_the_game_over(self):
        """精算で売り尽くしても不足額に届かずゲームオーバーが成立した後、
        4つの間隔のうち最も長いぶんの時間を進めても、画面（資金・盤面・
        売上の囲み・決算ポップアップの再出現）が1件も変わらず、定期保存も
        走らないこと。**精算は凍結していた4つのタイマーを必ず再開する**
        ため、本テストは「再開したまま終わる」誤実装を弾く（売却で
        NPC所有店舗として残る1軒が他店建設の成長対象になるため、
        他店建設が止まることもこの画面の一致で捉えられる）"""
        core = GameCore()
        self._build_plot(core, self.PLAYER_COL, self.PLAYER_ROW)
        self._advance_ms(GameCore.SETTLEMENT_INTERVAL_MS)
        core.update()
        # 唯一のプレイヤー所有店舗を売り尽くしても届かない不足額にする
        # （売却額は Shop.BUILD_COST // 2 の1軒ぶんだけ。売却で賄えて
        # ゲームが続く側は TestShopClocksAfterSellingOutAllShops が
        # 確認しており、本テストはその裏返しの境界に当たる）
        core._money = -10 * GameCore.INITIAL_MONEY  # pylint: disable=W0212
        btn_x, btn_y, btn_w, btn_h = self._expected_settlement_popup_button_rect()
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))
        self._release(core)
        screen_at_the_end = self._drawn_calls(core)
        # ゲームオーバーが実際に成立していること（前提）
        self.assertIn(
            self._expected_game_end_popup_message_call(
                GameCore.GAME_END_MESSAGE_GAME_OVER
            ),
            screen_at_the_end,
        )
        self.mock_store.save.reset_mock()
        self._advance_past_every_interval(core)
        self.assertEqual(
            screen_at_the_end, self._drawn_calls(core), self.test_view.get_call_params()
        )
        self.mock_store.save.assert_not_called()
