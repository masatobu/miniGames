"""保存・復元の基盤

「いつ保存するか」という保存の仕組みそのものを検証する（GameCore の
保存・復元、一定間隔ごとの定期保存、アプリ起動直後の待機、データ変化時の
保存契機）。タイマー固有の状態遷移を伴う保存の検証（未開始なら None で
保存し、復元後は続きから経過する）は clock 側に分類される（分類ルール2）。

分類ルール（test/test_main.py の分割時に定めた3条）:
1. 同じ「o押下」が起点でも、検証対象がポップアップの開閉なら popup、
   盤面・資金の変化なら shop_action
2. 保存のテストは「いつ保存するか」と「何が保存されるか」で分ける。
   前者（仕組み）は save、後者のうちタイマー固有の状態遷移を伴うものは clock
3. 描画のテストは、発生契機が時間経過なら clock
   （draw は操作・状態から直接決まる描画のみ）

TestSaveOnDataChange がこのファイルにある理由: 契機は建設・増資・買収
だが、検証対象は「いつ保存するか」という保存の仕組みで、TestPeriodicSave
（一定間隔ごと）と対になる片割れであるため、shop_action ではなく save へ
含める。
"""

import os
import sys
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import GameCore  # pylint: disable=C0413
from field import Owner, Shop  # pylint: disable=C0413,E0401
from test_main_tools import TestParent  # pylint: disable=C0413,E0401


class TestGameCoreSaveLoad(TestParent):
    """GameCore のマップ状態の保存・復元に関する振る舞いのテスト"""

    def test_load_called_once(self):
        """GameCore() の生成で ReportStore.load() が 1 回呼ばれること"""
        GameCore()
        self.mock_store.load.assert_called_once()

    def test_save_data_holds_field_shops_and_money(self):
        """GameCore() の生成で、Field のマップ状態と資金が保存データとして save() へ渡されること
        （起動カウンタは保存データに含まれないこと）。保存データがないときは空マップ・初期資金が渡ること。
        他店建設間隔・売上発生間隔・決算間隔の3つのタイマーはまだ開始していない
        （プレイヤー所有店舗がない）ため、残り時間はいずれも None（未開始）で渡ること。
        ゲームスピードの段階（speed_index）も保存データに含まれ、保存データが
        ないときは最低速（添字0）で渡ること（ID-019 サイクル8）"""
        GameCore()
        self.mock_store.save.assert_called_once_with(
            {
                "shops": [],
                "money": GameCore.INITIAL_MONEY,
                "npc_growth_remaining_ms": None,
                "sales_remaining_ms": None,
                "settlement_remaining_ms": None,
                "speed_index": 0,
            }
        )

    def test_draw_shows_shops_and_money_from_save_data_or_initial_values(self):
        """保存データがある場合はそのマップ状態と資金が復元されて描画され、保存データがない場合
        （load() が None）はフィールドに店舗が1つも描かれず初期資金のみが描画されること。
        復元後の資金の確認も、内部変数ではなく描画経由で行う"""
        restored_money = GameCore.INITIAL_MONEY + 500
        test_cases = [
            (
                "保存データあり（保存されたマップと資金を描く）",
                {
                    "shops": [[3, 2, Owner.PLAYER.value, 4, 300]],
                    "money": restored_money,
                    "settlement_remaining_ms": None,
                    "speed_index": 0,
                },
                [(3, 2, Owner.PLAYER)],
                4,
                restored_money,
                # 復元した資産価値300のプレイヤー所有店舗1軒ぶんの支払い予定
                # 税額（ID-014 サイクル3）
                self._expected_tax([300]),
            ),
            (
                "保存データなし（店舗は1つも描かれず初期資金を描く）",
                None,
                [],
                Shop.INITIAL_SCALE,
                GameCore.INITIAL_MONEY,
                0,
            ),
        ]
        for (
            case_name,
            load_data,
            expected_shops,
            scale,
            expected_money,
            expected_tax,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                self.mock_store.load.return_value = load_data
                core = GameCore()
                # サブテストをまたいで呼び出しログが積み上がらないよう、
                # ケースごとに描画呼び出しの記録をリセットする
                self.test_view.call_params = []
                core.draw()
                expected_shop_count = sum(
                    1 for _, _, owner in expected_shops if owner == Owner.PLAYER
                )
                expected = (
                    self._expected_status_calls(
                        money=expected_money,
                        shop_count=expected_shop_count,
                        tax=expected_tax,
                    )
                    + self._expected_road_calls()
                    + self._expected_shop_calls(expected_shops, scale=scale)
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_reset_ignores_save_data_and_saves_initial_state(self):
        """GameCore(reset=True) は、非空の保存データが存在していても無視し、
        空マップ・初期資金・3タイマーとも未開始（None）の初期状態を保存し
        描画すること。保存と描画は同じ1回の生成から生まれる2つの観点のため、
        test_save_data_holds_field_shops_and_money と
        test_draw_shows_shops_and_money_from_save_data_or_initial_values の
        保存データなしケースと同じ期待値を、1つのテスト関数の中でまとめて
        確認する。保存データが最低速でない段階（speed_index）を持っていても
        無視され、リセット後は最低速（添字0）へ戻ること（ID-019 サイクル8。
        チェックリストの「リセットで最低速へ戻ること」）"""
        self.mock_store.load.return_value = {
            "shops": [[3, 2, Owner.PLAYER.value, 4, 300]],
            "money": GameCore.INITIAL_MONEY + 500,
            "npc_growth_remaining_ms": 1000,
            "sales_remaining_ms": 1000,
            "settlement_remaining_ms": 1000,
            "speed_index": 2,
        }

        core = GameCore(reset=True)

        self.mock_store.save.assert_called_once_with(
            {
                "shops": [],
                "money": GameCore.INITIAL_MONEY,
                "npc_growth_remaining_ms": None,
                "sales_remaining_ms": None,
                "settlement_remaining_ms": None,
                "speed_index": 0,
            }
        )
        core.draw()
        expected = (
            self._expected_status_calls(money=GameCore.INITIAL_MONEY, tax=0)
            + self._expected_road_calls()
            + self._expected_shop_calls([])
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestGameSpeedSaveLoad(TestParent):
    """ゲームスピードの段階（GameCore.GAME_SPEED_STEPS の添字。
    self._speed_index）の保存データのキーの追加・復元に関するテスト
    （ID-019 サイクル8）。段階と3タイマーの残り時間が組で正しく戻ること
    （復元後の待機時間もその段階のものになること）は test_main_clock.py の
    TestGameSpeedRestoresTimersAtTheSavedSpeed が担う（分類ルール2。
    「何が保存されるか」のうちタイマー固有の状態遷移を伴わないキー
    そのものの追加はここ）。

    **保存データが無い（data is None）ケースは
    TestGameCoreSaveLoad.test_save_data_holds_field_shops_and_money が
    既に確認済み**（最低速＝添字0で保存される）ため本クラスには無い。
    **「保存データにキーが無い」ケースのテストも本クラスには無い**:
    本タスクは ReportStore.VERSION を 6 → 7 へ繰り上げるため（要確認済み。
    設計方針7）、speed_index は data.get() を経ずに data["speed_index"] を
    直接読む（ID-014 決算間隔と同じ型）。VERSION が一致した保存データには
    speed_index が必ず存在し、旧バージョン（ID-018 以前）の保存データは
    ReportStore.load() がバージョン不一致の時点で None を返して読み捨てる
    ため、このメソッドへ旧形式のデータが渡ることはない（「旧バージョンの
    保存データが読み捨てられる」こと自体は test_report_store.py の
    TestReportStore.test_load が VERSION の具体的な値に依存しない汎用の
    テストとして既に固定している。TestSettlementClockSaveLoad の
    docstring と同じ理由）。

    段階そのものは GameCore の内部状態で、押下（_update_status_buttons()。
    サイクル4）を経ずに外から切り替える手段が無いため、保存データの
    キーを確認するテストの都合として self._speed_index を直接差し替える
    （設計方針1「段階を直接読むテストは作らない」は、段階の**切り替え**を
    独立に検証するテストを指す。ここで確認するのは保存データのキーへの
    受け渡しという別の観点であり、これも直接読む形になる）"""

    def test_save_data_holds_the_current_speed_index(self):
        """保存データに現在のスピード段階が "speed_index" として含まれること"""
        core = GameCore()
        core._speed_index = 2  # pylint: disable=W0212
        self.assertEqual(
            2, core._get_save_data()["speed_index"]  # pylint: disable=W0212
        )


class TestPeriodicSave(TestParent):
    def _make_core(self, save_up):
        """save clock の is_up 戻り値を指定して GameCore を作る"""
        core = GameCore()
        core._save_clock.is_up = MagicMock(  # pylint: disable=W0212
            return_value=save_up
        )
        self.mock_store.save.reset_mock()
        return core

    def test_save_called_when_save_clock_is_up(self):
        """update() で保存クロックが満了したとき save() が呼ばれること"""
        core = self._make_core(save_up=True)
        core.update()
        self.mock_store.save.assert_called_once_with(
            core._get_save_data()  # pylint: disable=W0212
        )

    def test_save_not_called_when_save_clock_is_not_up(self):
        """update() で保存クロックが満了していないとき save() が呼ばれないこと"""
        core = self._make_core(save_up=False)
        core.update()
        self.mock_store.save.assert_not_called()


class TestAppLoadWait(TestParent):
    """App による GameCore 生成の待機フレーム動作のテスト"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()
        from src.main import App as _App  # pylint: disable=C0415

        self.app_class = _App

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def test_core_not_created_before_wait_frames(self):
        """LOAD_WAIT_FRAMES 未満の update() では _core が生成されないこと"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES - 1):
            app.update()
        self.assertIsNone(app._core)  # pylint: disable=W0212

    def test_core_created_after_wait_frames(self):
        """LOAD_WAIT_FRAMES 回 update() を呼ぶと _core が GameCore として生成されること"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES):
            app.update()
        self.assertIsInstance(app._core, GameCore)  # pylint: disable=W0212

    def test_draw_before_core_created_does_not_raise(self):
        """_core 生成前の draw() が例外にならず、GameCore.draw() を呼ばないこと"""
        app = self.app_class()
        app.draw()  # 例外にならないこと自体が検証対象

    def test_mouse_tracking_enabled_on_init(self):
        """App の初期化で pyxel.mouse(True) が呼ばれること。これを呼ばないと
        pyxel.mouse_x / mouse_y が常に 0 を返し、押下位置から区画を特定できない。
        描画・状態遷移のどのユニットテストにも現れない欠落であり、プレイテストまで
        発覚しないため、例外的に初期化の呼び出し契約そのものをテストで固定する"""
        self.app_class()
        self.mock_pyxel.mouse.assert_called_once_with(True)


class TestAppReset(TestParent):
    """App が GameCore.needs_reset を検知して GameCore を差し替える動作の
    テスト（TDD サイクル3）。TestAppLoadWait と同じセットアップ（pyxel
    モジュールをモックし、実 App を生成する）を使う"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()
        from src.main import App as _App  # pylint: disable=C0415

        self.app_class = _App

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def _app_with_core(self):
        """_core が生成済みの App を作る（LOAD_WAIT_FRAMES 分待つ）"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES):
            app.update()
        return app

    def test_core_not_replaced_while_needs_reset_is_false(self):
        """needs_reset が False の間は _core が同一インスタンスのままである
        こと（既存の _core.update() が呼ばれる通常経路の回帰）"""
        app = self._app_with_core()
        core = app._core  # pylint: disable=W0212

        app.update()

        self.assertIs(core, app._core)  # pylint: disable=W0212

    def test_core_replaced_with_fresh_reset_state_when_needs_reset_becomes_true(self):
        """_core.needs_reset が True になると、app.update() で _core が別
        インスタンス（かつ保存データを無視した初期状態）へ差し替わること。
        「別インスタンスになること」と「その中身が初期状態であること」は
        同じ操作（needs_reset を立てて update() を1回呼ぶ）から生まれる
        2つの観点のため、1つの関数の中でまとめて確認する（サイクル1の Red
        と同じ期待値を App 経由で確認する）"""
        self.mock_store.load.return_value = {
            "shops": [[3, 2, Owner.PLAYER.value, 4, 300]],
            "money": GameCore.INITIAL_MONEY + 500,
            "npc_growth_remaining_ms": 1000,
            "sales_remaining_ms": 1000,
            "settlement_remaining_ms": 1000,
            "speed_index": 0,
        }
        app = self._app_with_core()
        core = app._core  # pylint: disable=W0212
        core._needs_reset = True  # pylint: disable=W0212

        app.update()

        self.assertIsNot(core, app._core)  # pylint: disable=W0212
        app._core.draw()  # pylint: disable=W0212
        expected = (
            self._expected_status_calls(money=GameCore.INITIAL_MONEY, tax=0)
            + self._expected_road_calls()
            + self._expected_shop_calls([])
        )
        self.assertEqual(
            expected,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )


class TestSaveOnDataChange(TestParent):
    """保存の契機（TDD サイクル5）のテスト。押下の立ち上がりでの保存はなくなり、
    ゲームデータが変わったとき（本タスクの時点では建設のみ）に save() が呼ばれる。
    起動時（TestParent.setUp が生成する core の __init__）・一定フレームごと
    （TestPeriodicSave）の保存はこのサイクルでは変わらない。

    ゲームデータが変わらない操作（区画を探すだけの押下・押下解除による MODAL
    への確定・「x」で閉じる・資金不足で「o」が反応しない）では save() が
    呼ばれないことを、操作ごとに個別のテストで固定する（押下ごとの保存が
    消えたことを、押下そのものが起きるあらゆる場面で確認する）。

    建設は最初のプレイヤー所有店舗を生み得るため、起点を共有するタイマー
    （他店建設間隔・売上発生間隔）が起動する（_start_shop_clocks()）。
    保存データの残り時間
    （Clock.remaining_ms()）は実時間の経過とともに変わる値のため、
    time.perf_counter() を固定しないと「実行時に save() へ渡った値」と
    「アサーションで core._get_save_data() を呼び直して作る期待値」が
    別の実時刻で計算されてわずかに食い違う（ID-008 サイクル5 で顕在化）。
    本クラスはタイマーの発火そのものには関心が無いため、時刻を進めず
    固定するだけでよい"""

    # 建設の対象にする空き区画（画面左半分 → ポップアップは右下に表示される）
    BUILD_COL = 3
    BUILD_ROW = 2
    # 押し直し（TRACKING 中の再選択）を試す別の区画
    SECOND_COL = 5
    SECOND_ROW = 4
    # 増資・買収の費用を確実に賄える資金（ID-028 で GameCore.INITIAL_MONEY を
    # 200 へ引き下げたため、BUILD_COL/BUILD_ROW の地域価格倍率での増資費用
    # （262）・買収費用（350）のいずれも既定の初期資金では賄えない。本クラスの
    # 関心は「状態変更の直後に保存されること」であり資金の妥当性ではないため、
    # 保存データからの復元（load() の戻り値）で費用を問わず賄える額を与える）
    SUFFICIENT_MONEY = 1000

    def setUp(self):
        super().setUp()
        self.patcher_perf_counter = patch.object(time, "perf_counter", return_value=0.0)
        self.patcher_perf_counter.start()

    def tearDown(self):
        self.patcher_perf_counter.stop()
        super().tearDown()

    def _make_modal_core(self, col, row):
        """指定した区画を押して離し、MODAL 状態のポップアップを用意する。
        戻り値は (core, 押下位置)。選択そのものによる save() 呼び出しは
        以降のテストの対象外のため、ここでリセットする"""
        core = GameCore()
        pos = self._plot_center_pos(col, row)
        self._press(core, pos)
        self._release(core)
        self.mock_store.save.reset_mock()
        return core, pos

    def _press_popup_button(self, core, pos, index):
        """MODAL 状態のポップアップの index 番目のボタン（0: 「o」, 1: 「x」）の
        中心を押下する。ポップアップ原点 x は選択を決めた押下位置 pos から導く"""
        popup_x = self._expected_popup_x(pos[0])
        btn_x, btn_y, btn_w, btn_h = self._expected_button_rect(popup_x, index)
        self._press(core, (btn_x + btn_w // 2, btn_y + btn_h // 2))

    def test_save_called_with_built_shop_and_spent_money(self):
        """建設した update() で save() が呼ばれ、渡されたデータに建設後の店舗と
        減算後の資金が入っていること"""
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_called_once_with(
            core._get_save_data()  # pylint: disable=W0212
        )

    def test_save_called_with_invested_shop_and_updated_value(self):
        """増資した update() で save() が呼ばれ、渡されたデータの該当店舗の
        scale・value が更新後の値になっていること"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": self.SUFFICIENT_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.BUILD_COL, self.BUILD_ROW, Owner.PLAYER
        )
        pos = self._plot_center_pos(self.BUILD_COL, self.BUILD_ROW)
        self._press(core, pos)
        self._release(core)
        self.mock_store.save.reset_mock()
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_called_once_with(
            core._get_save_data()  # pylint: disable=W0212
        )

    def test_save_called_with_bought_out_shop_and_unchanged_scale_and_value(self):
        """買収した update() で save() が呼ばれ、渡されたデータの該当店舗の
        owner が Owner.PLAYER.value になり、scale・value は変わっていない
        こと（test_save_called_with_built_shop_and_spent_money /
        test_save_called_with_invested_shop_and_updated_value と同じ、
        「状態変更の直後に保存する」契機の確認）"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": self.SUFFICIENT_MONEY,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core = GameCore()
        core._field.set_shop(  # pylint: disable=W0212
            self.BUILD_COL, self.BUILD_ROW, Owner.NPC
        )
        pos = self._plot_center_pos(self.BUILD_COL, self.BUILD_ROW)
        self._press(core, pos)
        self._release(core)
        self.mock_store.save.reset_mock()
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_called_once_with(
            core._get_save_data()  # pylint: disable=W0212
        )

    def test_save_not_called_while_tracking_plot(self):
        """区画を探すだけの押下（TRACKING 中の押し直しを含む）では save() が
        呼ばれないこと"""
        core = GameCore()
        self.mock_store.save.reset_mock()
        self._press(core, self._plot_center_pos(self.BUILD_COL, self.BUILD_ROW))
        self._press(core, self._plot_center_pos(self.SECOND_COL, self.SECOND_ROW))
        self.mock_store.save.assert_not_called()

    def test_save_not_called_on_modal_confirm(self):
        """押下を解除して選択を MODAL へ確定するだけでは save() が呼ばれないこと"""
        core = GameCore()
        self._press(core, self._plot_center_pos(self.BUILD_COL, self.BUILD_ROW))
        self.mock_store.save.reset_mock()
        self._release(core)
        self.mock_store.save.assert_not_called()

    def test_save_not_called_when_closing_with_x(self):
        """「x」で閉じるだけでは save() が呼ばれないこと（建設に結び付かない）"""
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, 1)
        self.mock_store.save.assert_not_called()

    def test_save_not_called_when_build_blocked_by_insufficient_funds(self):
        """資金不足で「o」が反応せず建設されないときは save() が呼ばれないこと"""
        self.mock_store.load.return_value = {
            "shops": [],
            "money": Shop.BUILD_COST - 1,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_not_called()

    def test_save_not_called_when_invest_blocked_by_insufficient_funds(self):
        """資金不足で「o」が反応せず増資されないときは save() が呼ばれないこと"""
        self.mock_store.load.return_value = {
            "shops": [
                [self.BUILD_COL, self.BUILD_ROW, Owner.PLAYER.value, 1, Shop.BUILD_COST]
            ],
            "money": Shop.INVEST_COST - 1,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_not_called()

    def test_save_not_called_when_buyout_blocked_by_insufficient_funds(self):
        """資金不足で「o」が反応せず買収されないときは save() が呼ばれないこと"""
        value = 550
        cost = value * Shop.BUYOUT_RATE
        self.mock_store.load.return_value = {
            "shops": [[self.BUILD_COL, self.BUILD_ROW, Owner.NPC.value, 3, value]],
            "money": cost - 1,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_not_called()

    def test_save_not_called_when_invest_blocked_by_scale_max(self):
        """店舗規模が上限で「o」が反応せず増資されないときは save() が
        呼ばれないこと（資金は増資費用ちょうどを与え、規模が理由であることを
        資金不足のケースと切り分ける）"""
        scale = GameCore.SHOP_SCALE_MAX
        cost = Shop.INVEST_COST * 2 ** (scale - 1)
        self.mock_store.load.return_value = {
            "shops": [
                [
                    self.BUILD_COL,
                    self.BUILD_ROW,
                    Owner.PLAYER.value,
                    scale,
                    Shop.BUILD_COST + cost,
                ]
            ],
            "money": cost,
            "settlement_remaining_ms": None,
            "speed_index": 0,
        }
        core, pos = self._make_modal_core(self.BUILD_COL, self.BUILD_ROW)
        self._press_popup_button(core, pos, GameCore.POPUP_BTN_INDEX_O)
        self.mock_store.save.assert_not_called()
