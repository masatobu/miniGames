import math
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from hook import Hook, HookState, BaitType  # pylint: disable=C0413
from fish import FishSize  # pylint: disable=C0413
from main import GameCore  # pylint: disable=C0413


class TestHook(unittest.TestCase):
    def test_can_change_bait_type(self):
        """えさ種類を指定した値に切り替えられる"""
        for bait_type in [BaitType.LURE, BaitType.FLOAT_BAIT]:
            with self.subTest(bait_type=bait_type):
                hook = Hook(0, 0, GameCore.WATER_Y)
                hook.set_bait_type(bait_type)
                self.assertEqual(hook.bait_type, bait_type)

    def test_initial_state(self):
        """釣り針の初期状態は待機(idle)、与えた位置に配置、速度は0、えさは浮餌"""
        hook = Hook(GameCore.LINE_ORIGIN_X, GameCore.LINE_ORIGIN_Y, GameCore.WATER_Y)
        self.assertEqual(hook.state, HookState.IDLE)
        self.assertEqual(hook.x, GameCore.LINE_ORIGIN_X)
        self.assertEqual(hook.y, GameCore.LINE_ORIGIN_Y)
        self.assertEqual(hook._vx, 0)  # pylint: disable=W0212
        self.assertEqual(hook._vy, 0)  # pylint: disable=W0212
        self.assertEqual(hook.bait_type, BaitType.FLOAT_BAIT)

    def test_hook_moves_during_throw(self):
        """投擲中は毎フレーム速度に従って位置が更新され、vy に重力が加算される"""
        hook = Hook(GameCore.THROW_X, GameCore.THROW_Y, GameCore.WATER_Y)
        hook._charging_frames = Hook.MAX_CHARGE_FRAMES  # pylint: disable=W0212
        hook.throw_charged()
        initial_x = hook.x
        initial_y = hook.y

        # 1フレーム目: 位置が速度分だけ移動する
        hook.update()
        self.assertEqual(hook.x, int(initial_x + Hook.MAX_VX))
        self.assertEqual(hook.y, int(initial_y + Hook.MAX_VY))
        # vx は変化しない（横方向等速）
        self.assertEqual(hook._vx, Hook.MAX_VX)  # pylint: disable=W0212
        # vy に重力が加算される
        self.assertEqual(hook._vy, Hook.MAX_VY + Hook.GRAVITY)  # pylint: disable=W0212

        # 2フレーム目: 更新後の vy（重力加算済み）で位置が移動する
        expected_vy2 = Hook.MAX_VY + Hook.GRAVITY
        hook.update()
        self.assertEqual(hook.y, int(initial_y + Hook.MAX_VY + expected_vy2))

    def test_hook_water_surface_boundary(self):
        """水面到達判定の境界値テスト（y >= WATER_Y で停止、< では継続）"""
        # (初期y, vy, 期待state, 期待y)
        cases = [
            (
                GameCore.WATER_Y - 1,
                10,
                HookState.SURFACE,
                GameCore.WATER_Y,
                "大きく超える",
            ),
            (
                GameCore.WATER_Y - 1,
                1,
                HookState.SURFACE,
                GameCore.WATER_Y,
                "ちょうど水面 (==)",
            ),
            (
                GameCore.WATER_Y - 2,
                1,
                HookState.THROWING,
                GameCore.WATER_Y - 1,
                "水面直前 (<)",
            ),
        ]
        for initial_y, vy, expected_state, expected_y, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(100, initial_y, GameCore.WATER_Y)
                hook._state = HookState.THROWING  # pylint: disable=W0212
                hook._vx = 0  # pylint: disable=W0212
                hook._vy = vy  # pylint: disable=W0212
                hook.update()
                self.assertEqual(hook.state, expected_state)
                self.assertEqual(hook.y, expected_y)

    def test_surface_pause_boundary(self):
        """SURFACE_PAUSE_FRAMES の前後・えさ種類で状態が正しく切り替わる境界値テスト"""
        # (更新フレーム数, えさ種類, 期待状態, 説明)
        cases = [
            (
                Hook.SURFACE_PAUSE_FRAMES - 1,
                BaitType.LURE,
                HookState.SURFACE,
                "1フレーム前はまだ SURFACE",
            ),
            (
                Hook.SURFACE_PAUSE_FRAMES,
                BaitType.LURE,
                HookState.SINKING,
                "ちょうど SURFACE_PAUSE_FRAMES で SINKING（ルアー）",
            ),
            (
                Hook.SURFACE_PAUSE_FRAMES,
                BaitType.FLOAT_BAIT,
                HookState.SINKING,
                "ちょうど SURFACE_PAUSE_FRAMES で SINKING（浮餌）",
            ),
        ]
        for frames, bait_type, expected_state, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(100, GameCore.WATER_Y - 1, GameCore.WATER_Y)
                hook.set_bait_type(bait_type)
                hook._state = HookState.THROWING  # pylint: disable=W0212
                hook._vx = 0  # pylint: disable=W0212
                hook._vy = 1  # pylint: disable=W0212
                hook.update()  # SURFACE に到達
                for _ in range(frames):
                    hook.update()
                self.assertEqual(hook.state, expected_state)

    def test_sinking_behavior_by_bait_type(self):
        """SINKING 状態でのえさ種類別の沈下・停止挙動"""
        # (えさ種類, 初期y, フレームごとの期待y リスト, 説明)
        cases = [
            (
                BaitType.LURE,
                GameCore.WATER_Y,
                [
                    GameCore.WATER_Y + Hook.SINK_VY_MAP[BaitType.LURE],
                    GameCore.WATER_Y + Hook.SINK_VY_MAP[BaitType.LURE] * 2,
                ],
                "ルアーは毎フレーム SINK_VY_MAP[LURE] 分だけ沈下し続ける",
            ),
            (
                BaitType.FLOAT_BAIT,
                GameCore.WATER_Y + Hook.FLOAT_BAIT_DEPTH - 1,
                [
                    GameCore.WATER_Y + Hook.FLOAT_BAIT_DEPTH,
                    GameCore.WATER_Y + Hook.FLOAT_BAIT_DEPTH,
                ],
                "浮餌は FLOAT_BAIT_DEPTH に達したら停止する",
            ),
        ]
        for bait_type, initial_y, expected_ys, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(100, initial_y, GameCore.WATER_Y)
                hook.set_bait_type(bait_type)
                hook._state = HookState.SINKING  # pylint: disable=W0212
                for expected_y in expected_ys:
                    hook.update()
                    self.assertEqual(hook.y, expected_y)

    def test_sinking_hook_transitions_to_finished_at_bottom(self):
        """SINKING 中に y が FINISH_Y_MAX に達したら FINISHED_FAIL に遷移する"""
        sink_vy = Hook.SINK_VY_MAP[BaitType.LURE]
        cases = [
            (
                Hook.FINISH_Y_MAX - sink_vy - 1,
                HookState.SINKING,
                "FINISH_Y_MAX 1px 前はまだ SINKING",
            ),
            (
                Hook.FINISH_Y_MAX - sink_vy,
                HookState.FINISHED_FAIL,
                "ちょうど FINISH_Y_MAX に到達で FINISHED_FAIL",
            ),
            (
                Hook.FINISH_Y_MAX - sink_vy + 1,
                HookState.FINISHED_FAIL,
                "FINISH_Y_MAX を超えた場合も FINISHED_FAIL",
            ),
        ]
        for initial_y, expected_state, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(100, initial_y, GameCore.WATER_Y)
                hook.set_bait_type(BaitType.LURE)
                hook._state = HookState.SINKING  # pylint: disable=W0212
                hook.update()
                self.assertEqual(hook.state, expected_state)


class TestStartReeling(unittest.TestCase):
    def test_start_reeling_sets_reeling_state(self):
        """start_reeling() を呼ぶと REELING 状態になる"""
        hook = Hook(100, GameCore.WATER_Y + 10, GameCore.WATER_Y)
        hook.start_reeling()
        self.assertEqual(hook.state, HookState.REELING)


class TestReelingMovement(unittest.TestCase):
    def test_reeling_underwater_moves_toward_throw_origin(self):
        """水中 REELING 中に毎フレーム投擲起点方向へ移動する（複数の直角三角形で三角計測）"""
        # (hook_x, hook_y, throw_x, throw_y, water_y, 説明)
        # 条件: hook_y > water_y（水中）、hook_x < throw_x（左投擲）、throw_y < water_y（投擲起点は水面上）
        cases = [
            # 3-4-5 三角形 ×10: dx=+30, dy=-40, dist=50
            (30, 50, 60, 10, 30, "3-4-5三角形×10 (dx=30, dy=-40, dist=50)"),
            # 5-12-13 三角形 ×10: dx=+50, dy=-120, dist=130
            (10, 130, 60, 10, 30, "5-12-13三角形×10 (dx=50, dy=-120, dist=130)"),
            # 8-15-17 三角形 ×10: dx=+80, dy=-150, dist=170
            (10, 160, 90, 10, 30, "8-15-17三角形×10 (dx=80, dy=-150, dist=170)"),
        ]
        for hook_x, hook_y, throw_x, throw_y, water_y, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = hook_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212

                hook.update()

                dx = throw_x - hook_x
                dy = throw_y - hook_y
                dist = math.sqrt(dx * dx + dy * dy)
                expected_x = hook_x + dx / dist * Hook.REEL_SPEED
                expected_y = hook_y + dy / dist * Hook.REEL_SPEED
                self.assertAlmostEqual(
                    hook._x, expected_x, places=5  # pylint: disable=W0212
                )
                self.assertAlmostEqual(
                    hook._y, expected_y, places=5  # pylint: disable=W0212
                )

    def test_reeling_at_surface_moves_horizontally_only(self):
        """水面 REELING（y <= water_y）の境界値テスト: 水平移動のみ・y は水面に固定される"""
        # 条件: _y > water_y → 水中, _y <= water_y → 水面（水平移動）
        # (hook_y, 説明)
        surface_cases = [
            (30, "y == water_y（境界: ちょうど水面）"),
            (29, "y == water_y - 1（境界: 水面より 1px 上）"),
        ]
        throw_x, throw_y, water_y = 60, 10, 30
        initial_x = 10
        for hook_y, desc in surface_cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = initial_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212

                hook.update()

                # y は水面に固定（垂直移動なし）
                self.assertAlmostEqual(
                    hook._y, water_y, places=5  # pylint: disable=W0212
                )
                # x は投擲起点方向（右）へ REEL_SPEED 分だけ移動
                self.assertAlmostEqual(
                    hook._x,  # pylint: disable=W0212
                    initial_x + Hook.REEL_SPEED,
                    places=5,
                )

    def test_reeling_just_below_surface_uses_vector_movement(self):
        """y == water_y + 1（境界: 水面より 1px 下）は水中扱いでベクトル移動になる"""
        # _y > water_y の最小ケース（水面/水中の境界 +1）
        throw_x, throw_y, water_y = 60, 10, 30
        hook = Hook(throw_x, throw_y, water_y)
        hook._x = 10  # pylint: disable=W0212
        hook._y = water_y + 1  # == 31 （水中側の最小値）# pylint: disable=W0212
        hook._state = HookState.REELING  # pylint: disable=W0212

        hook.update()

        # 水中ベクトル移動なので y は水面より大きくなる（水平固定にはならない）
        # x は REEL_SPEED より小さい（斜め移動のため dx/dist < 1）
        dx = throw_x - 10
        dy = throw_y - (water_y + 1)
        dist = math.sqrt(dx * dx + dy * dy)
        expected_x = 10 + dx / dist * Hook.REEL_SPEED
        expected_y_raw = (water_y + 1) + dy / dist * Hook.REEL_SPEED
        expected_y = max(water_y, expected_y_raw)
        self.assertAlmostEqual(hook._x, expected_x, places=5)  # pylint: disable=W0212
        self.assertAlmostEqual(hook._y, expected_y, places=5)  # pylint: disable=W0212
        # 水平固定ではないことを確認（x の移動量は REEL_SPEED 未満）
        self.assertLess(hook._x - 10, Hook.REEL_SPEED)  # pylint: disable=W0212

    def test_reel_speed_reduced_with_fish(self):
        """魚ありの巻き上げ: REEL_SPEED_WITH_FISH_MAP[MEDIUM_S] の速度で投擲起点方向へ移動する（複数の直角三角形で三角測定）"""
        # (hook_x, hook_y, throw_x, throw_y, water_y, 説明)
        cases = [
            # 3-4-5 三角形 ×10: dx=+30, dy=-40, dist=50
            (30, 50, 60, 10, 30, "3-4-5三角形×10 (dx=30, dy=-40, dist=50)"),
            # 5-12-13 三角形 ×10: dx=+50, dy=-120, dist=130
            (10, 130, 60, 10, 30, "5-12-13三角形×10 (dx=50, dy=-120, dist=130)"),
            # 8-15-17 三角形 ×10: dx=+80, dy=-150, dist=170
            (10, 160, 90, 10, 30, "8-15-17三角形×10 (dx=80, dy=-150, dist=170)"),
        ]
        for hook_x, hook_y, throw_x, throw_y, water_y, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = hook_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.hook_fish(FishSize.MEDIUM_S)

                hook.update()

                dx = throw_x - hook_x
                dy = throw_y - hook_y
                dist = math.sqrt(dx * dx + dy * dy)
                expected_x = (
                    hook_x
                    + dx / dist * Hook.REEL_SPEED_WITH_FISH_MAP[FishSize.MEDIUM_S]
                )
                expected_y = (
                    hook_y
                    + dy / dist * Hook.REEL_SPEED_WITH_FISH_MAP[FishSize.MEDIUM_S]
                )
                self.assertAlmostEqual(
                    hook._x, expected_x, places=5  # pylint: disable=W0212
                )
                self.assertAlmostEqual(
                    hook._y, expected_y, places=5  # pylint: disable=W0212
                )

    def test_reel_speed_reduced_with_fish_at_surface(self):
        """魚あり・水面 REELING: REEL_SPEED_WITH_FISH_MAP[MEDIUM_S] の速度で水平移動する"""
        surface_cases = [
            (30, "y == water_y（境界: ちょうど水面）"),
            (29, "y == water_y - 1（境界: 水面より 1px 上）"),
        ]
        throw_x, throw_y, water_y = 60, 10, 30
        initial_x = 10
        for hook_y, desc in surface_cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = initial_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.hook_fish(FishSize.MEDIUM_S)

                hook.update()

                # y は水面に固定（垂直移動なし）
                self.assertAlmostEqual(
                    hook._y, water_y, places=5  # pylint: disable=W0212
                )
                # x は投擲起点方向（右）へ REEL_SPEED_WITH_FISH_MAP[MEDIUM_S] 分だけ移動
                self.assertAlmostEqual(
                    hook._x,  # pylint: disable=W0212
                    initial_x + Hook.REEL_SPEED_WITH_FISH_MAP[FishSize.MEDIUM_S],
                    places=5,
                )


class TestReelingWithFishFrames(unittest.TestCase):
    def test_reel_with_fish_frames(self):
        """_reel_with_fish_frames カウンターの挙動: 魚あり/なし・stop_reeling によるリセット"""
        n_updates = 5
        # (has_fish, call_stop_reeling, expected_frames, desc)
        cases = [
            (True, False, n_updates, "魚あり・5フレーム → カウンター == 5"),
            (False, False, 0, "魚なし・5フレーム → カウンター変化なし"),
            (True, True, 0, "魚あり・5フレーム後 stop_reeling → カウンターリセット"),
        ]
        for has_fish, call_stop_reeling, expected, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(60, 10, 30)
                hook._x = 10  # pylint: disable=W0212
                hook._y = 50  # 水中  # pylint: disable=W0212
                if has_fish:
                    hook.hook_fish(FishSize.SMALL)
                hook.start_reeling()
                for _ in range(n_updates):
                    hook.update()
                if call_stop_reeling:
                    hook.stop_reeling()
                self.assertEqual(
                    hook._reel_with_fish_frames, expected  # pylint: disable=W0212
                )


class TestLineBreak(unittest.TestCase):
    """連続引き時間超過による糸切れ（REEL_LINE_BREAK_FRAMES_MAP[SMALL]）のテスト"""

    def _make_hook_with_fish_reeling(self):
        """SMALL 魚あり・REELING 状態のフックを返す。投擲起点から十分離れた位置に配置"""
        # throw_origin(200, 10) から hook(10, 200) まで dist ≈ 268px
        # REEL_LINE_BREAK_FRAMES_MAP[SMALL]=120 フレームで速度 1.5px/f でも最大 180px → 起点には届かない
        throw_x, throw_y, water_y = 200, 10, 30
        hook = Hook(throw_x, throw_y, water_y)
        hook._x = 10  # pylint: disable=W0212
        hook._y = 200  # 水中（200 > water_y=30）# pylint: disable=W0212
        hook.hook_fish(FishSize.SMALL)
        hook.start_reeling()
        return hook

    def test_line_break_after_continuous_reel(self):
        """連続引き時間超過: SMALL魚のReel_LINE_BREAK_FRAMES_MAP フレーム後に FINISHED_FAIL（糸切れ）に遷移する"""
        hook = self._make_hook_with_fish_reeling()
        line_break_frames = Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.SMALL]
        for _ in range(line_break_frames):
            hook.update()
        self.assertEqual(hook.state, HookState.FINISHED_FAIL)

    def test_no_line_break_just_before_limit(self):
        """REEL_LINE_BREAK_FRAMES_MAP[SMALL] - 1 フレーム時点ではまだ FINISHED_FAIL にならない（境界値）"""
        hook = self._make_hook_with_fish_reeling()
        line_break_frames = Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.SMALL]
        for _ in range(line_break_frames - 1):
            hook.update()
        self.assertNotIn(
            hook.state, (HookState.FINISHED_SUCCESS, HookState.FINISHED_FAIL)
        )

    def test_reel_release_resets_line_break_counter(self):
        """途中でリーリング解除してから再開: カウンターがリセットされ、再度 REEL_LINE_BREAK_FRAMES_MAP[SMALL] 後に FINISHED_FAIL になる"""
        hook = self._make_hook_with_fish_reeling()
        line_break_frames = Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.SMALL]
        # 1回目: 上限直前まで引く
        for _ in range(line_break_frames - 1):
            hook.update()
        # 一度離す（カウンターリセット）
        hook.stop_reeling()
        self.assertNotIn(
            hook.state, (HookState.FINISHED_SUCCESS, HookState.FINISHED_FAIL)
        )
        # 再度引き始める
        hook.start_reeling()
        # 再開後に line_break_frames - 1 フレームではまだ FINISHED_FAIL でない
        for _ in range(line_break_frames - 1):
            hook.update()
        self.assertNotIn(
            hook.state, (HookState.FINISHED_SUCCESS, HookState.FINISHED_FAIL)
        )
        # ちょうど line_break_frames フレームで FINISHED_FAIL
        hook.update()
        self.assertEqual(hook.state, HookState.FINISHED_FAIL)


class TestStopReeling(unittest.TestCase):
    def test_stop_reeling_underwater_returns_to_sinking(self):
        """水中（y > water_y）で stop_reeling() を呼ぶと SINKING に戻る"""
        hook = Hook(60, 10, 30)
        hook._x = 30  # pylint: disable=W0212
        hook._y = 50  # 水中（50 > water_y=30）# pylint: disable=W0212
        hook._state = HookState.REELING  # pylint: disable=W0212
        hook.stop_reeling()
        self.assertEqual(hook.state, HookState.SINKING)

    def test_stop_reeling_at_surface_returns_to_surface(self):
        """水面（y <= water_y）で stop_reeling() を呼ぶと SURFACE に戻る"""
        water_y = 30
        cases = [
            (water_y, "y == water_y（境界: ちょうど水面）"),
            (water_y - 1, "y == water_y - 1（境界: 水面より 1px 上）"),
        ]
        for hook_y, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(60, 10, water_y)
                hook._x = 10  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.stop_reeling()
                self.assertEqual(hook.state, HookState.SURFACE)

    def test_stop_reeling_surface_then_sinks_after_pause_frames(self):
        """stop_reeling() で SURFACE に戻った後、SURFACE_PAUSE_FRAMES 経過で SINKING に遷移する
        （_surface_timer が正しくリセットされていることを確認）"""
        water_y = 30
        hook = Hook(60, 10, water_y)
        hook._x = 10  # pylint: disable=W0212
        hook._y = water_y  # 水面 # pylint: disable=W0212
        hook._state = HookState.REELING  # pylint: disable=W0212
        # REELING 前に SURFACE を経験していた場合を想定し、タイマーに残留値を設定
        hook._surface_timer = Hook.SURFACE_PAUSE_FRAMES - 1  # pylint: disable=W0212

        hook.stop_reeling()
        self.assertEqual(hook.state, HookState.SURFACE)

        # SURFACE_PAUSE_FRAMES - 1 回更新してもまだ SURFACE のまま
        for _ in range(Hook.SURFACE_PAUSE_FRAMES - 1):
            hook.update()
        self.assertEqual(hook.state, HookState.SURFACE)

        # ちょうど SURFACE_PAUSE_FRAMES 回目の更新で SINKING に遷移
        hook.update()
        self.assertEqual(hook.state, HookState.SINKING)


class TestReelingFinished(unittest.TestCase):
    def test_reeling_reaches_throw_origin_becomes_finished(self):
        """REELING 中に投擲起点との2D距離が REEL_FINISH_DIST 未満になったら FINISHED_SUCCESS になる（境界値テスト）"""
        throw_x, throw_y, water_y = 60, 10, 30
        finish_dist = Hook.REEL_FINISH_DIST
        cases = [
            # dist < REEL_FINISH_DIST → FINISHED_SUCCESS（投擲起点周辺の極近距離）
            (
                throw_x - 1,
                throw_y,
                HookState.FINISHED_SUCCESS,
                "x方向のみ: dist=1 < REEL_FINISH_DIST",
            ),
            (
                throw_x,
                throw_y + 1,
                HookState.FINISHED_SUCCESS,
                "y方向のみ: dist=1 < REEL_FINISH_DIST",
            ),
            (
                throw_x - 1,
                throw_y + 1,
                HookState.FINISHED_SUCCESS,
                "斜め: dist≈1.41 < REEL_FINISH_DIST",
            ),
            # dist > REEL_FINISH_DIST → REELING（投擲起点から十分遠い）
            (
                throw_x - int(finish_dist) - 10,
                throw_y,
                HookState.REELING,
                f"x方向のみ: dist={int(finish_dist)+10} > REEL_FINISH_DIST",
            ),
            (
                throw_x,
                throw_y + int(finish_dist) + 10,
                HookState.REELING,
                f"y方向のみ: dist={int(finish_dist)+10} > REEL_FINISH_DIST",
            ),
        ]
        for hook_x, hook_y, expected_state, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = hook_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.update()
                self.assertEqual(hook.state, expected_state)

    def test_reeling_at_surface_reaches_origin_becomes_finished(self):
        """水面 REELING 中: 投擲起点付近（x が十分近い）に到達で FINISHED になる（水面到達ケース）
        実ゲーム値: LINE_ORIGIN_Y=94, WATER_Y=96 → y_gap=2
        水面では y = water_y に固定されるため 2D 距離は sqrt(dx² + y_gap²) となる。
        旧判定 dist < REEL_SPEED (2px): y_gap=2 で dist >= 2 が常に成立 → FINISHED 不可。
        新判定 dist < REEL_FINISH_DIST で水面からの手元到達を可能にする。
        """
        throw_x = GameCore.LINE_ORIGIN_X
        throw_y = GameCore.LINE_ORIGIN_Y
        water_y = GameCore.WATER_Y
        y_gap = water_y - throw_y  # = 2: 水面での 2D 距離の最小値（dx=0 のとき）
        finish_dist = Hook.REEL_FINISH_DIST
        cases = [
            # 水面で x == throw_x: dist = y_gap=2 → REEL_FINISH_DIST > 2 なら FINISHED_SUCCESS
            (
                throw_x,
                water_y,
                HookState.FINISHED_SUCCESS,
                f"水面: dx=0, dist={y_gap} < REEL_FINISH_DIST",
            ),
            # 水面で x が十分遠い: dist > REEL_FINISH_DIST → REELING
            (
                throw_x - int(finish_dist) - 1,
                water_y,
                HookState.REELING,
                "水面: x が遠く dist > REEL_FINISH_DIST",
            ),
        ]
        for hook_x, hook_y, expected_state, desc in cases:
            with self.subTest(desc=desc):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = hook_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.update()
                self.assertEqual(hook.state, expected_state)


class TestHookCharging(unittest.TestCase):
    def setUp(self):
        self.hook = Hook(
            GameCore.LINE_ORIGIN_X, GameCore.LINE_ORIGIN_Y, GameCore.WATER_Y
        )

    def test_charging_count_increments_while_charging_in_idle(self):
        """IDLE 状態で start_charge() 後に update() すると充電フレームがインクリメントされる"""
        self.hook.start_charge()
        self.hook.update()
        self.assertEqual(self.hook._charging_frames, 1)  # pylint: disable=W0212
        self.hook.update()
        self.assertEqual(self.hook._charging_frames, 2)  # pylint: disable=W0212

    def test_charging_count_resets_after_stop_charge(self):
        """stop_charge() を呼ぶと充電フレームがリセットされる"""
        self.hook.start_charge()
        self.hook.update()  # charging_frames = 1
        self.hook.stop_charge()
        self.assertEqual(self.hook._charging_frames, 0)  # pylint: disable=W0212


class TestCalculateVelocity(unittest.TestCase):
    def setUp(self):
        self.hook = Hook(
            GameCore.LINE_ORIGIN_X, GameCore.LINE_ORIGIN_Y, GameCore.WATER_Y
        )

    def test_calculate_velocity_increases_with_charging_frames(self):
        """充電フレームが多いほど初速度が大きい"""
        self.hook._charging_frames = Hook.MIN_CHARGE_FRAMES  # pylint: disable=W0212
        vx_min, vy_min = self.hook._calculate_velocity()  # pylint: disable=W0212
        self.hook._charging_frames = Hook.MAX_CHARGE_FRAMES  # pylint: disable=W0212
        vx_max, vy_max = self.hook._calculate_velocity()  # pylint: disable=W0212
        self.assertGreater(abs(vx_max), abs(vx_min))
        self.assertGreater(abs(vy_max), abs(vy_min))

    def test_calculate_velocity_returns_expected_for_given_frames(self):
        """充電フレーム数に応じた期待速度を返す（境界値・上限キャップ）"""
        cases = [
            (
                Hook.MIN_CHARGE_FRAMES,
                Hook.MIN_VX,
                Hook.MIN_VY,
                "MIN_CHARGE_FRAMES → MIN速度",
            ),
            (
                Hook.MAX_CHARGE_FRAMES,
                Hook.MAX_VX,
                Hook.MAX_VY,
                "MAX_CHARGE_FRAMES → MAX速度",
            ),
            (
                Hook.MAX_CHARGE_FRAMES + 100,
                Hook.MAX_VX,
                Hook.MAX_VY,
                "MAX超過 → MAX速度でキャップ",
            ),
        ]
        for frames, expected_vx, expected_vy, desc in cases:
            with self.subTest(desc=desc):
                self.hook._charging_frames = frames  # pylint: disable=W0212
                vx, vy = self.hook._calculate_velocity()  # pylint: disable=W0212
                self.assertAlmostEqual(vx, expected_vx)
                self.assertAlmostEqual(vy, expected_vy)


class TestThrowCharged(unittest.TestCase):
    def setUp(self):
        self.hook = Hook(
            GameCore.LINE_ORIGIN_X, GameCore.LINE_ORIGIN_Y, GameCore.WATER_Y
        )

    def test_throw_charged_state_transition_by_charge(self):
        """充電フレームと MIN_CHARGE_FRAMES の境界値で状態遷移が正しく行われる"""
        cases = [
            (Hook.MIN_CHARGE_FRAMES - 1, HookState.IDLE, "MIN未満 → 状態変化なし"),
            (Hook.MIN_CHARGE_FRAMES, HookState.THROWING, "MIN到達 → THROWING"),
        ]
        for frames, expected_state, desc in cases:
            with self.subTest(desc=desc):
                self.hook._state = HookState.IDLE  # pylint: disable=W0212
                self.hook._charging_frames = frames  # pylint: disable=W0212
                self.hook.throw_charged()
                self.assertEqual(self.hook.state, expected_state)

    def test_throw_charged_velocity_at_boundary_frames(self):
        """充電フレーム数の境界値で投擲後の移動速度が正しく設定される"""
        cases = [
            (Hook.MIN_CHARGE_FRAMES - 1, 0, 0, "MIN未満 → 投擲されず速度は0"),
            (Hook.MIN_CHARGE_FRAMES, Hook.MIN_VX, Hook.MIN_VY, "MIN到達 → MIN速度"),
            (Hook.MAX_CHARGE_FRAMES, Hook.MAX_VX, Hook.MAX_VY, "MAX到達 → MAX速度"),
            (
                Hook.MAX_CHARGE_FRAMES + 1,
                Hook.MAX_VX,
                Hook.MAX_VY,
                "MAX超過 → MAX速度でキャップ",
            ),
        ]
        for frames, expected_vx, expected_vy, desc in cases:
            with self.subTest(desc=desc):
                self.hook._state = HookState.IDLE  # pylint: disable=W0212
                self.hook._vx = 0  # pylint: disable=W0212
                self.hook._vy = 0  # pylint: disable=W0212
                self.hook._charging_frames = frames  # pylint: disable=W0212
                self.hook.throw_charged()
                self.assertAlmostEqual(
                    self.hook._vx, expected_vx  # pylint: disable=W0212
                )
                self.assertAlmostEqual(
                    self.hook._vy, expected_vy  # pylint: disable=W0212
                )

    def test_charge_ratio_at_boundary_frames(self):
        """charge_ratio は充電進捗を 0.0〜1.0 の割合で返す

        MIN_CHARGE_FRAMES 未満（タップ相当）は 0.0 を返す。
        境界値: MIN_CHARGE_FRAMES - 1 → 0.0、MIN_CHARGE_FRAMES → 比例値。
        """
        cases = [
            (0, 0.0, "未充電 → 0.0"),
            (Hook.MIN_CHARGE_FRAMES - 1, 0.0, "MIN未満（タップ相当）→ 0.0"),
            (
                Hook.MIN_CHARGE_FRAMES,
                Hook.MIN_CHARGE_FRAMES / Hook.MAX_CHARGE_FRAMES,
                "MIN → 比例値",
            ),
            (Hook.MAX_CHARGE_FRAMES, 1.0, "MAX → 1.0"),
            (Hook.MAX_CHARGE_FRAMES + 100, 1.0, "MAX超過 → 1.0 でキャップ"),
        ]
        for frames, expected_ratio, desc in cases:
            with self.subTest(desc=desc):
                self.hook._charging_frames = frames  # pylint: disable=W0212
                self.assertAlmostEqual(self.hook.charge_ratio, expected_ratio)

    def test_hook_lands_near_left_at_max_charge(self):
        """MAX充電時、着水X座標が画面左寄り（ボタン右端より右かつ画面左1/4以内）になる"""
        self.hook._charging_frames = Hook.MAX_CHARGE_FRAMES  # pylint: disable=W0212
        self.hook.throw_charged()
        while self.hook.state == HookState.THROWING:
            self.hook.update()

        btn_right_edge = GameCore.FLOAT_BAIT_BTN_X + GameCore.BTN_SIZE
        # ボタンに被らない（ボタン右端以上）
        self.assertGreaterEqual(self.hook.x, btn_right_edge)
        # 画面左寄りまで飛ぶ（中央着水より明らかに左、画面左1/4 以内）
        self.assertLessEqual(self.hook.x, GameCore.SCREEN_WIDTH // 4)


class TestHookMoveTo(unittest.TestCase):
    """Hook.move_to() の仕様テスト（サイクル 5.6 公開 IF）。"""

    def _make_hook(self):
        return Hook(x=120, y=10, water_y=100)

    def test_hook_move_to_updates_position(self):
        """move_to(x, y) を呼ぶと hook.x と hook.y がその座標になること（有効範囲内）。
        フック状態は変化しないこと。
        """
        hook = self._make_hook()
        initial_state = hook.state
        hook.move_to(50, 80)
        self.assertEqual(hook.x, 50)
        self.assertEqual(hook.y, 80)
        self.assertEqual(hook.state, initial_state)

    def test_hook_move_to_finishes_when_out_of_range(self):
        """move_to(x, y) で x が有効範囲外（x < FINISH_X_MIN または x > FINISH_X_MAX）の場合、
        hook.state が FINISHED_FAIL になること。
        """
        cases = [
            ("x < FINISH_X_MIN（左端外）", Hook.FINISH_X_MIN - 1, 80),
            ("x > FINISH_X_MAX（右端外）", Hook.FINISH_X_MAX + 1, 80),
        ]
        for desc, x, y in cases:
            with self.subTest(desc=desc):
                hook = self._make_hook()
                hook.move_to(x, y)
                self.assertEqual(
                    hook.state,
                    HookState.FINISHED_FAIL,
                    f"{desc}: state が FINISHED_FAIL になるべき",
                )


class TestReelingSpeedByFishSize(unittest.TestCase):
    """サイズ別巻き上げ速度のテスト（TDD サイクル 2）"""

    def test_reel_speed_with_fish_by_size_movement(self):
        """hook_fish(fish_size) 後の移動量がサイズ別速度に応じていること（3-4-5 三角形）
        hook(30, 50) → throw_origin(60, 10), water_y=30
        dx=30, dy=-40, dist=50 (3-4-5×10)
        期待移動量: dx/dist * speed, dy/dist * speed
        """
        hook_x, hook_y, throw_x, throw_y, water_y = 30, 50, 60, 10, 30
        for fish_size in FishSize:
            with self.subTest(fish_size=fish_size):
                hook = Hook(throw_x, throw_y, water_y)
                hook._x = hook_x  # pylint: disable=W0212
                hook._y = hook_y  # pylint: disable=W0212
                hook._state = HookState.REELING  # pylint: disable=W0212
                hook.hook_fish(fish_size)

                hook.update()

                dx = throw_x - hook_x
                dy = throw_y - hook_y
                dist = math.sqrt(dx * dx + dy * dy)
                expected_speed = Hook.REEL_SPEED_WITH_FISH_MAP[fish_size]
                expected_x = hook_x + dx / dist * expected_speed
                expected_y = hook_y + dy / dist * expected_speed
                self.assertAlmostEqual(
                    hook._x, expected_x, places=5  # pylint: disable=W0212
                )
                self.assertAlmostEqual(
                    hook._y, expected_y, places=5  # pylint: disable=W0212
                )


class TestLineBreakByFishSize(unittest.TestCase):
    """サイズ別糸切れフレームのテスト（TDD サイクル 3）"""

    def _make_hook_with_fish_reeling(self, fish_size):
        """指定サイズの魚あり・REELING 状態のフックを返す。
        throw_origin(200, 10), hook(10, 200), water_y=30
        dist ≈ 268px — LARGE(0.5px/f × 45f = 22.5px)でも届かない距離
        """
        throw_x, throw_y, water_y = 200, 10, 30
        hook = Hook(throw_x, throw_y, water_y)
        hook._x = 10  # pylint: disable=W0212
        hook._y = 200  # 水中（200 > water_y=30）# pylint: disable=W0212
        hook.hook_fish(fish_size)
        hook.start_reeling()
        return hook

    def test_line_break_frames_by_fish_size(self):
        """hook_fish(fish_size) 後の糸切れフレームがサイズに応じて変わること"""
        cases = [
            (FishSize.SMALL, Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.SMALL]),
            (FishSize.MEDIUM_S, Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.MEDIUM_S]),
            (FishSize.MEDIUM_L, Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.MEDIUM_L]),
            (FishSize.LARGE, Hook.REEL_LINE_BREAK_FRAMES_MAP[FishSize.LARGE]),
        ]
        for fish_size, expected_frames in cases:
            with self.subTest(fish_size=fish_size):
                hook = self._make_hook_with_fish_reeling(fish_size)
                for _ in range(expected_frames - 1):
                    hook.update()
                self.assertNotEqual(
                    hook.state,
                    HookState.FINISHED_FAIL,
                    f"{fish_size}: {expected_frames - 1} フレームでまだ糸切れしないはず",
                )
                hook.update()  # 限界到達
                self.assertEqual(
                    hook.state,
                    HookState.FINISHED_FAIL,
                    f"{fish_size}: {expected_frames} フレームで糸切れするはず",
                )


if __name__ == "__main__":
    unittest.main()
