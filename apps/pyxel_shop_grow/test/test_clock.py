import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import Clock, ShopClock  # pylint: disable=C0413


class TestClock(unittest.TestCase):
    @patch.object(time, "perf_counter")
    def test_is_up(self, mock):
        """指定時間の経過前は False、経過後は True を返し、True の後は基準時刻がリセットされること。
        interval が 0 の場合は常に False（無効化）を返すこと"""
        test_cases = [
            ("1 sec", [False, True, False, True], 1000),
            ("1.1 sec", [False, False, True, False, False, True], 1100),
            ("always", [True, True, True, True, True, True], 1),
            ("never", [False, False, False, False, False, False], 0),
        ]
        for case_name, expected_list, count_ms in test_cases:
            with self.subTest(
                case_name=case_name, expected_list=expected_list, count_ms=count_ms
            ):
                mock.side_effect = [i * 0.5 for i in range(10)]
                clock = Clock(count_ms)
                for expected in expected_list:
                    self.assertEqual(expected, clock.is_up())

    @patch.object(time, "perf_counter")
    def test_remaining_ms_equals_count_ms_immediately_after_creation(self, mock):
        """remaining_ms を指定せずに生成すると、生成直後（経過0）の残り時間が
        count_ms そのものになること（続きからではなく最初から数え始める、
        既定の生成の挙動）"""
        mock.side_effect = [0.0, 0.0]
        clock = Clock(1000)
        self.assertEqual(1000, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_remaining_ms_counts_down_and_clamps_at_zero(self, mock):
        """残り時間が経過とともに減り、count_ms を過ぎても負にならず 0 で
        頭打ちになること。count_ms が 0（is_up() が常に False の無効化）の
        ときは常に 0 を返すこと"""
        test_cases = [
            ("1 sec", [500, 0, 0], 1000),
            ("never", [0, 0, 0], 0),
        ]
        for case_name, expected_list, count_ms in test_cases:
            with self.subTest(case_name=case_name, count_ms=count_ms):
                mock.side_effect = [i * 0.5 for i in range(10)]
                clock = Clock(count_ms)
                for expected in expected_list:
                    self.assertEqual(expected, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_resumes_from_a_given_remaining_ms(self, mock):
        """Clock(count_ms, remaining_ms=...) で生成すると、生成直後の残り
        時間が指定した値そのものになり（count_ms からではなく続きから始まる）、
        その残り時間ぶん経過するとちょうど is_up() が真になること。保存
        データからの復元で「続きから」経過させるための仕様
        （ShopClock.start()）"""
        mock.side_effect = [0.0, 0.0, 0.299, 0.300]
        clock = Clock(1000, remaining_ms=300)
        self.assertEqual(300, clock.remaining_ms())
        self.assertFalse(clock.is_up())  # 299ms 経過。まだ満了しない
        self.assertTrue(clock.is_up())  # 300ms 経過。ちょうど満了する


class TestClockPauseResume(unittest.TestCase):
    """一時停止・再開（ID-015 サイクル4）に関するテスト。`is_up()` を
    呼ばないだけでは時間が止まらない（Clock は time.perf_counter() の差分で
    判定するため、呼ばずにいても実時間は進み続ける）という設計判断の前提を、
    Clock 単体で確認する"""

    @patch.object(time, "perf_counter")
    def test_pause_freezes_remaining_ms_regardless_of_elapsed_time(self, mock):
        """一時停止すると、その後どれだけ実時間が進んでも remaining_ms() が
        停止した瞬間の値のまま変わらないこと"""
        mock.side_effect = [0.0, 0.3]
        clock = Clock(1000)
        clock.pause()  # 300ms 経過した時点で停止（残り700）
        for _ in range(3):
            # remaining_ms() はここでは perf_counter を読まないため、
            # side_effect が尽きても呼べる（停止中は時刻そのものを読まない）
            self.assertEqual(700, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_pause_makes_is_up_stay_false_even_past_the_interval(self, mock):
        """一時停止すると、間隔を過ぎるだけの実時間を進めても is_up() が
        False のままであること（`is_up()` を呼ばないだけの実装ではなく、
        実際に時刻の差分そのものを止めていることの確認。停止中は
        is_up() が perf_counter を読まないため、side_effect は生成と
        pause() の分の2つだけで足りる）"""
        mock.side_effect = [0.0, 0.0]
        clock = Clock(1000)
        clock.pause()
        self.assertFalse(clock.is_up())
        self.assertFalse(clock.is_up())

    @patch.object(time, "perf_counter")
    def test_pausing_twice_does_not_re_freeze_the_remaining_ms(self, mock):
        """一時停止を2回続けて呼んでも、2回目は何も起きない（1回目に停止した
        時点の残り時間のままで、2回目に呼んだ時点の残り時間へ巻き戻らない）"""
        # 3つ目の値は「2回目の pause() が誤って remaining_ms() を読み直して
        # しまう誤実装」を検出するための撒き餌（読まれれば残りが0へ巻き戻り、
        # 下のアサーションが失敗する）
        mock.side_effect = [0.0, 0.0, 999.0]
        clock = Clock(1000)
        clock.pause()  # 経過0で停止（残り1000）
        clock.pause()  # 2回目は何もしないはず
        self.assertEqual(1000, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_resume_continues_from_the_paused_remaining_ms(self, mock):
        """再開すると、停止した時点の残り時間の続きから経過し、実際に停止
        していた時間の長さには影響されないこと（再開時に間隔そのものへ
        巻き戻る誤実装を弾く）。停止した時点の残り時間ぶん経過すると
        ちょうど is_up() が真になる"""
        mock.side_effect = [
            0.0,  # 生成
            0.3,  # 300ms 経過後に停止（残り700）
            50.0,  # 長時間経過後に再開
            50.699,  # 再開から699ms 経過。まだ満了しない（合計999ms）
            50.700,  # 再開から700ms 経過。ちょうど満了する（合計1000ms）
        ]
        clock = Clock(1000)
        clock.pause()
        self.assertFalse(clock.is_up())  # 停止中は perf_counter を読まない
        clock.resume()
        self.assertFalse(clock.is_up())
        self.assertTrue(clock.is_up())

    @patch.object(time, "perf_counter")
    def test_resume_without_pause_does_nothing(self, mock):
        """一時停止していない状態で再開しても何も起きず、生成からの経過が
        そのまま続くこと"""
        mock.side_effect = [0.0, 0.5]
        clock = Clock(1000)
        clock.resume()
        self.assertEqual(500, clock.remaining_ms())


class TestClockChangeCountMs(unittest.TestCase):
    """間隔変更（ID-019 ゲームスピード。TDD サイクル 019-1）に関するテスト。
    Clock.change_count_ms() は、次の満了までの待機時間を新しい間隔へ差し替え、
    同時に残り時間も新旧の間隔の比率でスケールする"""

    @patch.object(time, "perf_counter")
    def test_change_count_ms_scales_the_remaining_ms_by_the_same_ratio(self, mock):
        """変更した瞬間の残り時間が、新旧の間隔の比率で縮む・伸びること
        （1/3 に変えると残りも1/3、3倍に戻すと残りも3倍に戻る）"""
        mock.side_effect = [0.0, 0.3, 0.3, 0.3, 0.3]
        clock = Clock(900)
        clock.change_count_ms(300)  # 300ms経過後に1/3へ変更。残り600→200
        self.assertEqual(200, clock.remaining_ms())
        clock.change_count_ms(900)  # 3倍に戻す。残り200→600
        self.assertEqual(600, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_is_up_fires_after_the_new_remaining_ms_and_next_cycle_uses_new_interval(
        self, mock
    ):
        """変更後は新しい残り時間ぶん経過するとちょうど is_up() が真になり、
        満了後の次の周期の待機時間も新しい間隔になること（間隔を変えたまま
        居続ける）"""
        mock.side_effect = [0.0, 0.0, 0.299, 0.300, 0.599, 0.600]
        clock = Clock(900)
        clock.change_count_ms(300)  # 生成直後に変更。残りは新しい間隔そのまま
        self.assertFalse(clock.is_up())  # 299ms経過。まだ満了しない
        self.assertTrue(clock.is_up())  # 300msでちょうど満了
        self.assertFalse(clock.is_up())  # 満了後、次の周期の299msではまだ
        self.assertTrue(clock.is_up())  # 300msで再び満了（新間隔のまま）

    @patch.object(time, "perf_counter")
    def test_change_count_ms_while_paused_scales_the_paused_remaining_ms(self, mock):
        """一時停止中に変更すると time.perf_counter() を読まずに一時停止中の
        残り時間だけがスケールされ（_bef は再開時に組み直されるため触らない）、
        再開すると停止していた実時間に関わらずその続きから新しい間隔で
        経過すること"""
        mock.side_effect = [0.0, 0.3, 50.0, 50.199, 50.200]
        clock = Clock(900)
        clock.pause()  # 300ms経過後に停止（残り600）
        clock.change_count_ms(300)  # 一時停止中に1/3へ変更。残りも1/3(200)へ
        self.assertEqual(200, clock.remaining_ms())
        clock.resume()  # 停止していた実時間に関わらず、残り200からの続き
        self.assertFalse(clock.is_up())  # 再開から199ms経過。まだ満了しない
        self.assertTrue(clock.is_up())  # 再開から200msでちょうど満了（新間隔300の続き）

    @patch.object(time, "perf_counter")
    def test_change_count_ms_after_remaining_ms_clamped_to_zero_does_not_break(
        self, mock
    ):
        """満了を過ぎて残り時間が 0 で頭打ちの状態で変更しても壊れないこと
        （0 をそのままスケールしても 0 のまま）"""
        mock.side_effect = [0.0, 2.0, 2.0]
        clock = Clock(900)
        clock.change_count_ms(300)  # 2000ms経過後（頭打ちで残り0）に変更
        self.assertEqual(0, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_change_count_ms_to_zero_disables_the_timer(self, mock):
        """新しい間隔を 0 に変更すると、count_ms=0（無効化）の既定どおり
        is_up() が常に False・remaining_ms() が常に 0 になること"""
        mock.side_effect = [0.0, 0.3]
        clock = Clock(900)
        clock.change_count_ms(0)
        self.assertEqual(0, clock.remaining_ms())
        self.assertFalse(clock.is_up())

    @patch.object(time, "perf_counter")
    def test_change_count_ms_from_zero_does_not_divide_by_zero(self, mock):
        """count_ms=0（無効化）の状態から実際の間隔へ変更しても 0 除算で
        壊れないこと。無効化中は比率を持たないため、変更後は新しい間隔
        そのものから数え直す"""
        mock.side_effect = [0.0, 0.3, 0.3]
        clock = Clock(0)
        clock.change_count_ms(300)
        self.assertEqual(300, clock.remaining_ms())


class TestShopClockPauseResume(unittest.TestCase):
    """ShopClock の一時停止・再開（ID-015 サイクル4）に関するテスト。
    内側の Clock への中継と、**未開始（self._clock is None）のときは何も
    しない**こと（「未開始」と「一時停止」は別物であるという設計判断。
    一時停止で未開始へ戻す・開始扱いにするのいずれもしない）を確認する"""

    def test_pause_and_resume_do_nothing_while_not_started(self):
        """未開始のタイマーへ一時停止・再開を呼んでも、未開始のまま
        （remaining_ms() が None・is_up() が False のまま）であること。
        店舗0軒の間は決算ポップアップ自体が出ないため GameCore からは
        起こらないが、ShopClock 単体では起こり得る"""
        clock = ShopClock(1000)
        clock.pause()
        self.assertIsNone(clock.remaining_ms())
        self.assertFalse(clock.is_up())
        clock.resume()
        self.assertIsNone(clock.remaining_ms())
        self.assertFalse(clock.is_up())

    @patch.object(time, "perf_counter")
    def test_pause_and_resume_relay_to_the_inner_clock_once_started(self, mock):
        """開始済みのタイマーは、一時停止・再開が内側の Clock へそのまま
        中継されること（停止中は経過が進まず、再開すると続きから経過する）"""
        mock.side_effect = [0.0, 0.0, 100.0, 100.999, 101.0]
        clock = ShopClock(1000)
        clock.start()
        clock.pause()
        self.assertFalse(clock.is_up())
        clock.resume()
        self.assertFalse(clock.is_up())
        self.assertTrue(clock.is_up())


class TestShopClockChangeCountMs(unittest.TestCase):
    """ShopClock の間隔変更（ID-019 ゲームスピード。TDD サイクル
    019-2）に関するテスト。未開始のときは内側の Clock が無いぶんだけを
    足す中継（_count_ms と、控えている保存値のスケール）とし、開始済みは
    内側の Clock へそのまま中継する"""

    @patch.object(time, "perf_counter")
    def test_change_count_ms_before_start_changes_the_interval_used_by_start(
        self, mock
    ):
        """未開始のまま間隔を変更すると、time.perf_counter() を読まずに
        （未開始のまま時刻を読まないことは維持したまま）、その後 start()
        したときに新しい間隔から始まること"""
        mock.side_effect = [0.0, 0.0]
        clock = ShopClock(900)
        clock.change_count_ms(300)
        clock.start()
        self.assertEqual(300, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_change_count_ms_before_start_scales_the_saved_remaining_ms(self, mock):
        """保存値（apply_saved_remaining_ms()）を控えた状態で間隔を変更すると、
        start() 後の残り時間が新旧の間隔の比率でスケールされた値になること"""
        mock.side_effect = [0.0, 0.0]
        clock = ShopClock(900)
        clock.apply_saved_remaining_ms(600)
        clock.change_count_ms(300)  # 600 * 300/900 = 200
        clock.start()
        self.assertEqual(200, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_change_count_ms_after_start_relays_to_the_inner_clock(self, mock):
        """開始済みのタイマーへ間隔を変更すると、内側の Clock へそのまま
        中継され、残り時間が新旧の間隔の比率でスケールされること
        （Clock.change_count_ms() 自身のスケールはサイクル 019-1 で確認
        済みのため、ここでは中継されることのみ確認する）"""
        mock.side_effect = [0.0, 0.3, 0.3]
        clock = ShopClock(900)
        clock.start()
        clock.change_count_ms(300)  # 300ms経過後に1/3へ。残り600→200
        self.assertEqual(200, clock.remaining_ms())

    @patch.object(time, "perf_counter")
    def test_change_count_ms_after_start_does_not_revert_to_not_started(self, mock):
        """開始済みで間隔を変更したあとに start() をもう一度呼んでも、
        「一度開始したら未開始へ戻らない」性質のとおり何も起きず、変更後の
        残り時間がそのまま続くこと（内側の Clock を未開始へ戻す・作り
        直すことがないことの確認）"""
        mock.side_effect = [0.0, 0.3, 0.3]
        clock = ShopClock(900)
        clock.start()
        clock.change_count_ms(300)  # 300ms経過後に1/3へ。残り600→200
        clock.start()  # 二度目の start() は何もしない
        self.assertEqual(200, clock.remaining_ms())
