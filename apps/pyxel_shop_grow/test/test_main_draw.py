"""道路・店舗・資金の描画

操作・状態から直接決まる描画（ステータスの資金表示・道路・店舗の描画）を
検証する。発生契機が時間経過の描画（例: 売上抽選の囲み）は clock 側に
分類される（分類ルール3）。

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
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import GameCore  # pylint: disable=C0413
from field import Owner, Shop  # pylint: disable=C0413,E0401
from test_main_tools import TestParent  # pylint: disable=C0413,E0401


class TestDrawMoney(TestParent):
    """GameCore.draw() のステータス領域（背景・資金表示）に関する振る舞いのテスト"""

    def test_draw_shows_money_in_status_area(self):
        """ゲーム開始時、draw() の最初に画面最上部のステータス領域が背景として
        塗られ（位置 (0, 0)、サイズ SCREEN_W × STATUS_H）、その後ろに資金のテキストが
        領域の内側余白（STATUS_PAD）を空けた位置へ描画されること。道路より前に
        描画されることを、呼び出し順を含めて検証する。増減 API がまだ無いため
        INITIAL_MONEY を差し替え、資金の値が変わっても表示に反映されること
        （定数を焼き付けた表示になっていないこと）もあわせて確認する"""
        test_money_values = [0, 1000, 999999]
        for money in test_money_values:
            with self.subTest(money=money):
                with patch.object(GameCore, "INITIAL_MONEY", money, create=True):
                    core = GameCore()
                # サブテストをまたいで呼び出しログが積み上がらないよう、
                # ケースごとに描画呼び出しの記録をリセットする
                self.test_view.call_params = []
                core.draw()
                expected = (
                    self._expected_status_calls(money=money)
                    + self._expected_road_calls()
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestDrawShopCount(TestParent):
    """ステータス領域1行目、資金の右へ描く「現在の店舗数／規定店舗数」の
    表示に関する振る舞いのテスト（要件「4. ゲーム画面仕様 / プレイヤー
    ステータス」。ID-028 サイクル028-4）。目標側は数値を直書きせず
    Field.CLEAR_SHOP_COUNT を参照する式で書く（ID-028_subtasks.md
    「テスト設計の注意」1）。期待値は _expected_field_calls() へ
    shop_count= を渡して得る（_expected_status_calls() へ統合済み。
    TASK-028-13）"""

    def test_shows_zero_out_of_clear_shop_count_on_the_initial_empty_board(self):
        """店舗が1軒もない初期盤面では、店舗数の表示が
        0/Field.CLEAR_SHOP_COUNT になること"""
        core = GameCore()
        self._draw(core)
        expected = self._expected_field_calls(shop_count=0)
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_shop_count_follows_construction_and_buyout_and_ignores_npc_shops(self):
        """建設・買収でプレイヤー所有店舗が増えると店舗数の表示が追従し、
        NPC所有店舗は数えないこと（要件「4. プレイヤーステータス」）。
        列0は地域価格倍率が等倍（1.0）になるため、税額の期待値を単純な
        式で書ける（ID-020 案8-A）"""
        core = GameCore()
        core._field.set_shop(0, 0, Owner.NPC)  # pylint: disable=W0212
        core._field.buyout_shop(0, 0)  # 買収 → 1軒目  # pylint: disable=W0212
        core._field.set_shop(  # 建設 → 2軒目  # pylint: disable=W0212
            0, 1, Owner.PLAYER
        )
        core._field.set_shop(0, 2, Owner.NPC)  # 数えない  # pylint: disable=W0212
        self._draw(core)
        expected = self._expected_field_calls(
            shop_count=2,
            shops=[(0, 0, Owner.PLAYER), (0, 1, Owner.PLAYER), (0, 2, Owner.NPC)],
            tax=self._expected_tax(
                [Shop.BUILD_COST, Shop.BUILD_COST], other_values=[Shop.BUILD_COST]
            ),
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_shop_count_follows_a_settlement_sale(self):
        """決算の店舗売却（ID-016）でプレイヤー所有店舗が減ると、店舗数の
        表示も追従すること（表示が持ち回りでなく毎フレーム導出であることを
        弾く。ID-028_subtasks.md「テスト設計の注意」3）。売却の抽選は
        行昇順→列昇順の先頭（0, 0）を選ぶよう固定する"""
        core = GameCore()
        core._field.set_shop(0, 0, Owner.PLAYER)  # pylint: disable=W0212
        core._field.set_shop(0, 1, Owner.PLAYER)  # pylint: disable=W0212
        self.test_random_source.pick_sell_shop.side_effect = lambda targets: targets[0]
        core._field.sell_shops_for_shortfall(1)  # pylint: disable=W0212
        self._draw(core)
        expected = self._expected_field_calls(
            shop_count=1,
            shops=[(0, 0, Owner.NPC), (0, 1, Owner.PLAYER)],
            tax=self._expected_tax([Shop.BUILD_COST], other_values=[Shop.BUILD_COST]),
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestDrawStatusButtons(TestParent):
    """ステータス領域右のポーズ・スピードボタンの描画に関する振る舞いの
    テスト（ID-019 サイクル3）。押下判定そのもの（ボタンを押した結果
    ポーズ・段階が切り替わること）は test_main_popup.py 側（分類ルール
    4件目。ID-019_subtasks.md）に置き、本クラスは押下判定を経由しない、
    状態から直接決まる描画——矩形の位置・大きさ・ラベル・配色——だけを
    検証する（初期状態はサイクル3、ポーズ中の配色入れ替えはサイクル6）"""

    def test_draw_shows_pause_and_speed_buttons_at_their_initial_state(self):
        """draw() の最初、ステータス領域の資金・決算情報の2行に続けて、
        右側にポーズ「||」・スピード「>」の2つの矩形とラベルが描画される
        こと。初期状態（ポーズ解除・最低速）ではポーズボタンが無効表示
        （背景 STATUS_BTN_DISABLED_COL）、スピードボタンが通常表示
        （背景 STATUS_BTN_COL）であること（設計方針 6-1）。道路より前に
        描かれることも、既存のステータス2行と同じくあわせて確認する"""
        core = GameCore()
        self._draw(core)
        expected = self._expected_status_calls() + self._expected_road_calls()
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_status_buttons_do_not_break_existing_status_lines_when_board_changes(
        self,
    ):
        """盤面が変わって資金・税額の表示が変わっても、その後ろにボタンの
        描画がそのまま続くこと（ボタン追加後も既存のステータス2行の
        表示が壊れていないことの回帰確認を兼ねる）"""
        core = GameCore()
        core._field.set_shop(0, 2, Owner.PLAYER)  # pylint: disable=W0212
        core._money -= Shop.BUILD_COST  # pylint: disable=W0212
        self._draw(core)
        expected = (
            self._expected_status_calls(
                money=GameCore.INITIAL_MONEY - Shop.BUILD_COST,
                shop_count=1,
                tax=self._expected_tax([Shop.BUILD_COST]),
            )
            + self._expected_road_calls()
            + self._expected_shop_calls([(0, 2, Owner.PLAYER)])
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_status_buttons_swap_colors_while_paused(self):
        """ポーズ中（self._paused が真）は、ポーズボタンが通常表示
        （背景 STATUS_BTN_COL）・スピードボタンが無効表示（背景
        STATUS_BTN_DISABLED_COL）へ入れ替わって描かれること（設計方針
        6-1）。ポーズへ入る操作そのもの（押下判定）は
        test_main_popup.py の TestStatusPauseButtonToggle が検証するため、
        ここでは状態を直接立てて配色だけを確認する（分類ルール4件目。
        ID-019 サイクル6）。ラベル「||」自体はポーズ中も変わらない
        （状態は配色だけで示す）ため、期待値のラベルは初期状態と同じ
        まま _expected_status_button_calls(paused=True) から得る"""
        core = GameCore()
        core._paused = True  # pylint: disable=W0212
        self._draw(core)
        expected = (
            self._expected_status_calls(paused=True) + self._expected_road_calls()
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestDrawShops(TestParent):
    """GameCore.draw() の店舗描画に関する振る舞いのテスト"""

    def test_draw_draws_shops_at_their_plot_screen_position(self):
        """Field に設置した店舗が、道路の後に、区画に対応する画面座標へ 16×24 で
        描画されること（店舗がない区画・ないマップでは道路だけが描画されること、
        右端列・最下行の区画でも画面内に収まること）"""
        test_cases = [
            ("店舗が1つもない空きマップ", []),
            ("通常の区画に1件設置", [(3, 2, Owner.NPC)]),
            (
                "右端列・最下行の区画に設置",
                [
                    (GameCore.GRID_COLS - 1, 0, Owner.PLAYER),
                    (0, GameCore.GRID_ROWS - 1, Owner.PLAYER),
                ],
            ),
        ]
        for case_name, shops in test_cases:
            with self.subTest(case_name=case_name):
                # サブテストをまたいで呼び出しログが積み上がらないよう、
                # ケースごとに描画呼び出しの記録をリセットする
                self.test_view.call_params = []
                core = GameCore()
                for col, row, owner in shops:
                    core._field.set_shop(col, row, owner)  # pylint: disable=W0212
                core.draw()
                # プレイヤー所有店舗は set_shop() 直後の資産価値
                # Shop.BUILD_COST を持つため、その分だけ税額の表示にも
                # 反映される（決算タイマーは set_shop() 経由では起動しない
                # ため、残り時間の表示は既定値のまま。ID-014 サイクル3）
                player_values = [
                    Shop.BUILD_COST for _, _, owner in shops if owner == Owner.PLAYER
                ]
                expected = (
                    self._expected_status_calls(
                        shop_count=len(player_values),
                        tax=self._expected_tax(player_values),
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls(shops)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestDrawShopsByScale(TestParent):
    """GameCore.draw() が店舗規模に応じた画像を描画することの振る舞いテスト"""

    def test_draw_draws_shop_image_matching_its_scale(self):
        """店舗規模 1〜10 のそれぞれで、区画に描画される店舗画像の転送元 x が
        SHOP_U_ORIGIN + SHOP_U_STEP * (規模 - 1) になること（規模ごとに絵柄が変わる）。
        増資 API（ID-007）が未実装のため、公開 API 経由では規模を変更できない。
        Shop の内部状態（_scale）を直接書き換えて規模を変え、draw() の実際の
        描画呼び出し（draw_image）で確認する"""
        col, row, owner = 3, 2, Owner.NPC
        core = GameCore()
        core._field.set_shop(col, row, owner)  # pylint: disable=W0212
        shop = core._field._shops[(col, row)]  # pylint: disable=W0212
        for scale in range(GameCore.SHOP_SCALE_MIN, GameCore.SHOP_SCALE_MAX + 1):
            with self.subTest(scale=scale):
                shop._scale = scale  # pylint: disable=W0212
                # サブテストをまたいで呼び出しログが積み上がらないよう、
                # ケースごとに描画呼び出しの記録をリセットする
                self.test_view.call_params = []
                core.draw()
                expected = (
                    self._expected_status_calls()
                    + self._expected_road_calls()
                    + self._expected_shop_calls([(col, row, owner)], scale=scale)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestDrawShopsByOwner(TestParent):
    """GameCore.draw() が所有者に応じた画像を描画することの振る舞いテスト"""

    def test_draw_draws_shop_image_matching_its_owner(self):
        """NPC所有・プレイヤー所有それぞれで、区画に描画される店舗画像の転送元 y が
        SHOP_V_NPC / SHOP_V_PLAYER になること（所有者ごとに色の異なる段を使う）。
        転送元 x（規模による絵柄）は所有者によらず同じ計算式から求まることを、
        _expected_shop_calls() が両ケースで同じ式を使うことで併せて確認する
        （専用のテストは追加しない）"""
        col, row = 0, 2
        for owner in (Owner.NPC, Owner.PLAYER):
            with self.subTest(owner=owner):
                # サブテストをまたいで呼び出しログが積み上がらないよう、
                # ケースごとに描画呼び出しの記録をリセットする
                self.test_view.call_params = []
                core = GameCore()
                core._field.set_shop(col, row, owner)  # pylint: disable=W0212
                core.draw()
                # プレイヤー所有のときだけ、set_shop() 直後の資産価値
                # Shop.BUILD_COST が税額の表示へ反映される（ID-014 サイクル3）
                player_values = [Shop.BUILD_COST] if owner == Owner.PLAYER else []
                expected = (
                    self._expected_status_calls(
                        shop_count=len(player_values),
                        tax=self._expected_tax(player_values),
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls([(col, row, owner)])
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestDrawSettlementStatus(TestParent):
    """ステータス2行目（決算までの残り時間・支払い予定税額）に関する
    振る舞いのテスト（ID-014 サイクル3）。

    決算タイマー自体の起動条件（最初のプレイヤー所有店舗の建設。要件3.2）・
    満了周期は TestSettlementInterval（test_main_clock.py）が固定済みのため、
    本クラスは「その残り時間・税額がどう画面に出るか」だけを検証する
    （表示のテストはタイマーのテストを内側に含まない。設計判断の章を参照）。

    盤面の作り方は他の draw 系テスト（TestDrawShops など）と同じく
    Field への直接操作に揃える。ただし決算タイマーの起点（要件3.2）は
    「最初のプレイヤー所有店舗の建設」であり、実際の建設経路
    （_build_selected_plot()）の最後で呼ばれる _start_shop_clocks()
    まで含めて再現しないとタイマーが起動しないため、_build_player_shop() は
    Field への設置・資金の減算・_start_shop_clocks() の呼び出しの
    3つをまとめて行う（ポップアップの押下操作までは経由しない。押下経路の
    検証は TestBuildShop / TestSettlementInterval が担う）。

    時刻の制御（time.perf_counter を side_effect で差し替え、_advance_ms()
    で進める）は TestSettlementInterval と同じ形を使う。時刻を固定しない
    テストにすると、ちょうど1秒をまたいだ瞬間に実行されたときだけ
    remaining_sec の期待値が1ずれる可能性があるため、本クラスの全テストで
    固定する"""

    PLAYER_COL = 0
    PLAYER_ROW = 2
    # 他店建設の抽選対象（プレイヤー所有店舗に上下左右で隣接する空き区画）を
    # Field の列挙順（行昇順→列昇順）に並べた先頭。TestParent が既定で仕込む
    # 乱数源（targets[0] を選ぶ）は常にこの区画を選ぶ（TestNpcGrowthInterval と
    # 同じ区画・同じ理由）
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
        # 決算間隔（60秒）は売上発生間隔（3秒）より長いため、経過中に売上発生
        # 間隔が必ず何度か満了する。本クラスの関心は表示だけであり、抽選先を
        # 固定して無関係な失敗（乱数源を差し替えていない状態での抽選）を
        # 避ける（TestSettlementInterval と同じ理由・同じ与え方）
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
        """最初のプレイヤー所有店舗を Field へ直接設置し、資金を減らし、
        決算タイマーを起動する。実際の建設操作（押下・ポップアップの「o」）を
        経由する TestBuildShop / TestSettlementInterval とは異なり、本クラスは
        描画の検証に徹するため、他の draw 系テストと同じ直接操作で盤面を作る。
        _start_shop_clocks() を明示的に呼ぶのは、実際の建設フロー
        （_build_selected_plot()）が最後に呼ぶのと同じ呼び出しを、「建設された
        こと」の代わりとしてここでも再現するため（決算タイマーの起点は要件3.2
        の「最初のプレイヤー所有店舗の建設」であり、Field への設置だけでは
        タイマーが起動しない）"""
        core._field.set_shop(  # pylint: disable=W0212
            self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER
        )
        core._money -= Shop.BUILD_COST  # pylint: disable=W0212
        core._start_shop_clocks()  # pylint: disable=W0212

    def test_shows_interval_and_zero_tax_before_any_shop_is_built(self):
        """店舗が1軒もない起動直後、残り時間は間隔そのもの（60）、税額は0で
        表示されること（未開始で None を出す・0を出す・例外のいずれも弾く）"""
        core = GameCore()
        self._draw(core)
        expected = self._expected_field_calls()
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_shows_full_interval_and_tax_just_after_building_the_first_shop(self):
        """最初の店舗を建設した直後、残り時間は間隔そのもの（開始したばかり）、
        税額は建てた店舗の資産価値（Shop.BUILD_COST）から求まる値になること
        （開始時に0から始まる誤実装・税額を起動時に確定させて持ち回る誤実装を
        弾く）"""
        core = GameCore()
        self._build_player_shop(core)
        self._draw(core)
        expected = self._expected_field_calls(
            [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
            money=GameCore.INITIAL_MONEY - Shop.BUILD_COST,
            shop_count=1,
            tax=self._expected_tax([Shop.BUILD_COST]),
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_remaining_seconds_round_up_and_wrap_around_the_interval(self):
        """残り時間が秒へ切り上げられ、間隔ちょうどで満了して巻き戻ること。
        建設からの経過時間を 1ms → 1,000ms → interval-1ms → interval ms の順
        （後戻りしない、既存の TestSettlementInterval と同じ進め方）で進める。
        1ms経過（59.999秒→60。切り捨てなら59になる誤実装を弾く）・
        1,000ms経過（59。切り上げの境界のずれを弾く）・interval-1ms経過
        （1。切り捨てなら0になる誤実装を弾く）・interval ms経過（60。空回しが
        効いておらず0のままになる誤実装を弾く）の4通りを確認する。

        remaining_ms() は時刻から都度導出する値のため、interval 未満の3ケース
        （1ms・1,000ms・interval-1ms）は core.update() を呼ばずに直接
        draw() するだけで正しい値が読める。update() を呼ばずに済ませるのは、
        呼ぶと他店建設間隔（10秒）・売上発生間隔（3秒）も同じ update() の中で
        満了してしまい（決算間隔60秒はその6倍・20倍。AGENTS.md
        「決算間隔の仮値」参照）、盤面・資金が本テストの関心外で変わって
        しまうため。**満了して巻き戻る最後の1ケースだけ**は、
        「空回しの呼び出しが無く0のまま張り付く」誤実装を弾くために
        is_up() の呼び出し（GameCore.update() 経由）が必須で、そこで初めて
        他の2つのタイマーも同時に満了する（1回の update() 呼び出しでは
        1タイマーにつき最大1回しか満了しない。TestSettlementInterval の
        _remaining_ms() が同じ理由で core.update() を呼んでいる形に揃える）。
        そのため最後のケースだけ、他店建設・売上ぶんの盤面・資金の変化を
        期待値へ織り込む。決算タイマーも満了するため、決算ポップアップの
        背景・枠（ID-015 サイクル1）・数値3行（同サイクル2）・「o」ボタン
        （同サイクル5）も期待値へ足す"""
        interval = GameCore.SETTLEMENT_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        tax = self._expected_tax([Shop.BUILD_COST])
        built_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST

        # interval 未満の3ケース: update() を呼ばず、時刻だけを進めて読む
        for total_elapsed_ms, expected_sec in [(1, 60), (1000, 59), (interval - 1, 1)]:
            with self.subTest(total_elapsed_ms=total_elapsed_ms):
                self._now = 0.0
                self._advance_ms(total_elapsed_ms)
                self._draw(core)
                expected = self._expected_field_calls(
                    [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
                    money=built_money,
                    remaining_sec=expected_sec,
                    shop_count=1,
                    tax=tax,
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

        # 満了して巻き戻る最後のケース: is_up() を呼ぶ必要があるため
        # core.update() を経由する。ここで初めて他店建設間隔・売上発生間隔も
        # 満了し（決算間隔がその6倍・20倍のため）、NPC所有店舗が1軒建ち、
        # 売上（規模1）が資金へ加算される
        with self.subTest(total_elapsed_ms=interval):
            self._now = 0.0
            self._advance_ms(interval)
            core.update()
            self._draw(core)
            money_at_settlement = built_money + Shop.SALES_AMOUNT * 2**0
            expected = (
                self._expected_field_calls(
                    [
                        (self.NPC_COL, self.NPC_ROW, Owner.NPC),
                        (self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER),
                    ],
                    money=money_at_settlement,
                    remaining_sec=60,
                    shop_count=1,
                    tax=tax,
                    sales_plot=(self.PLAYER_COL, self.PLAYER_ROW),
                )
                + self._expected_settlement_popup_calls()
                # 決算ポップアップの数値3行（ID-015 サイクル2）
                + self._expected_settlement_popup_value_calls(
                    money_at_settlement, tax, money_at_settlement - tax
                )
                # 決算ポップアップの「o」ボタン（ID-015 サイクル5 Refactor・再考）
                + self._expected_settlement_popup_button_calls()
            )
            self.assertEqual(
                expected,
                self.test_view.get_call_params(),
                self.test_view.get_call_params(),
            )

    def test_tax_display_follows_the_board_when_it_changes(self):
        """建設直後の税額から、増資で盤面（資産価値）が変わると税額の表示も
        それに追従して変わること（税額を起動時に確定させて持ち回る誤実装を
        弾く）。残り時間は増資でタイマーが起動し直さないため、間隔そのものの
        まま変わらないことも併せて確認する"""
        core = GameCore()
        self._build_player_shop(core)
        self._draw(core)
        tax_after_build = self._expected_tax([Shop.BUILD_COST])
        self.assertEqual(
            self._expected_field_calls(
                [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
                money=GameCore.INITIAL_MONEY - Shop.BUILD_COST,
                shop_count=1,
                tax=tax_after_build,
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

        # 増資して盤面（資産価値）を変える（押下経路は経由せず、Field と資金を
        # 直接操作する。増資の実行そのものの検証は TestInvestShop が担う）
        core._field.invest_shop(  # pylint: disable=W0212
            self.PLAYER_COL, self.PLAYER_ROW
        )
        core._money -= Shop.INVEST_COST  # pylint: disable=W0212
        self._draw(core)
        tax_after_invest = self._expected_tax([Shop.BUILD_COST + Shop.INVEST_COST])
        # 増資で税額が実際に変わることを前提として明示する（変わらない盤面では
        # 「追従した」のか「たまたま起動時の値のままだった」のか区別できない）
        self.assertNotEqual(tax_after_build, tax_after_invest)
        self.assertEqual(
            self._expected_field_calls(
                [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
                money=GameCore.INITIAL_MONEY - Shop.BUILD_COST - Shop.INVEST_COST,
                scale=2,
                shop_count=1,
                tax=tax_after_invest,
            ),
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )

    def test_bar_fill_width_follows_full_half_and_zero_ratio(self):
        """残り時間のプログレスバー（ID-027 決定5）の中身の幅が、決算間隔に
        対する残り時間の割合から導かれること（満杯・半分・0の3ケース。
        ID-027_subtasks.md TASK-027-5）。秒への量子化そのものは
        test_remaining_seconds_round_up_and_wrap_around_the_interval が
        別途検証済みのため、本テストは幅の式に絞る。0ケースでも枠
        （draw_rectb）は消えないこと——_expected_field_calls() が返す
        期待値に常に枠の呼び出しを含むため、完全一致（assertEqual）である
        本テストが自動的にそれも確認する"""
        interval = GameCore.SETTLEMENT_INTERVAL_MS
        core = GameCore()
        self._build_player_shop(core)
        tax = self._expected_tax([Shop.BUILD_COST])
        built_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST
        for elapsed_ms, expected_sec in [(0, 60), (interval // 2, 30), (interval, 0)]:
            with self.subTest(elapsed_ms=elapsed_ms):
                self._now = 0.0
                self._advance_ms(elapsed_ms)
                self._draw(core)
                expected = self._expected_field_calls(
                    [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
                    money=built_money,
                    remaining_sec=expected_sec,
                    shop_count=1,
                    tax=tax,
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_bar_leaves_a_gap_before_the_pause_button(self):
        """バーの右端とポーズボタンの左端の間に、STATUS_BAR_PAUSE_GAP
        （5px）ぶんの空間が空くこと（決定5のレイアウト制約。プレイテスト
        指示「ポーズボタンの横まで引っ張ってみて欲しい」・2026-08-30で
        使える幅いっぱいまで伸ばした後、「ポーズボタンとバーの右枠の間に
        5pxの空間を入れて欲しい」という追加指示を受けて改めた）。
        ポーズボタンの左端は _expected_status_pause_button_rect()（実装の
        _status_pause_button_rect() と同じ式）から求め、実装から独立した
        期待値の側だけで確認する（GameCore のインスタンスも draw() も
        不要）。STATUS_BAR_W はこの空間ぶんを引いた幅として定義されている
        （STATUS_BAR_X からポーズボタン左端の手前 STATUS_BAR_PAUSE_GAP
        までの距離）ため、本テストはその定義どおりに実装の各定数
        （STATUS_X / STATUS_W / STATUS_PAD / STATUS_BTN_GAP /
        STATUS_BTN_W / STATUS_BAR_PAUSE_GAP）が組まれていることの回帰
        確認になる"""
        pause_x, _, _, _ = self._expected_status_pause_button_rect()
        bar_right = GameCore.STATUS_BAR_X + GameCore.STATUS_BAR_W
        self.assertEqual(pause_x - GameCore.STATUS_BAR_PAUSE_GAP, bar_right)

    def test_money_remaining_and_tax_are_all_correct_together(self):
        """1行目（資金）と2行目（残り時間・税額）がそれぞれ独立して正しく、
        互いを取り違えたり上書きしたりしていないことを、3つとも異なる値になる
        盤面と経過時間で確認する（行の取り違えを弾く）"""
        core = GameCore()
        self._build_player_shop(core)
        self._advance_ms(1000)
        core.update()
        self._draw(core)
        expected_money = GameCore.INITIAL_MONEY - Shop.BUILD_COST
        expected_tax = self._expected_tax([Shop.BUILD_COST])
        expected_remaining_sec = 59
        # 3つの値が互いに異なることを前提として明示する（同じ値だと行の
        # 取り違えが起きても検出できないため）
        self.assertEqual(3, len({expected_money, expected_tax, expected_remaining_sec}))
        expected = self._expected_field_calls(
            [(self.PLAYER_COL, self.PLAYER_ROW, Owner.PLAYER)],
            money=expected_money,
            remaining_sec=expected_remaining_sec,
            shop_count=1,
            tax=expected_tax,
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
