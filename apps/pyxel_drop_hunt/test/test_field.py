import math
import unittest
from unittest.mock import patch

from src.main import Bullet, Drop, Field, Mob, MoveMode, Player


class TestParent(unittest.TestCase):
    """Field の公開 IF（set_click/process_frame/player_state/mob_states/
    destination）に対するテストの共通土台。test_main.py の e2e テストが
    描画呼び出し（draw()）で検証していた「actor がどう動くか」の観点を、
    Field の返却値で直接検証する（描画の有無・順序・スクロール・旗の描画
    位置は test_main.py に残す観点のため、ここでは対象外）"""

    INITIAL_PLAYER_X = (Field.SCREEN_WIDTH - Player.WIDTH) // 2
    INITIAL_PLAYER_Y = (Field.SCREEN_HEIGHT - Player.HEIGHT) // 2
    # プレイヤーの登録座標（スプライト左上）から画像中心点までのオフセット。
    # set_click（内部の turn_to）は画像中心点を基準に方向を計算するため、
    # クリック位置（目的地）の期待値はこのオフセットを介して
    # 「プレイヤー中心点 + 差分」で計算する
    PLAYER_CENTER_OFFSET_X = Player.WIDTH // 2
    PLAYER_CENTER_OFFSET_Y = Player.HEIGHT // 2
    # ゲーム開始時に出現するモブの位置・回転（setUp が乱数をプレイヤー真上の
    # x へ固定するため、出現位置はプレイヤー真上の画面外、出現時の
    # turn_to(player中心点) による回転は真下＝180度の自明値になる）
    INITIAL_MOB_X = INITIAL_PLAYER_X
    INITIAL_MOB_Y = -Field.MOB_SPAWN_OFFSET
    INITIAL_MOB_ROTATE = 180.0
    INITIAL_MOB = (INITIAL_MOB_X, INITIAL_MOB_Y, INITIAL_MOB_ROTATE)

    def setUp(self):
        # ゲーム開始時のモブ出現位置の乱数を決定的な値（プレイヤー真上の x）に
        # 固定する（出現仕様自体の検証は TestMobSpawnAtStart で行う）
        self.patcher_uniform = patch(
            "src.main.random.uniform", return_value=float(self.INITIAL_MOB_X)
        )
        self.mock_uniform = self.patcher_uniform.start()

    def tearDown(self):
        self.patcher_uniform.stop()

    def _expected_pos(self, start, diff, frames):
        # 進行方向は目的地ワールド座標とプレイヤー中心点の差分ベクトル diff を
        # 正規化した単位ベクトル。期待値（登録座標）は「開始座標 + フレーム数 ×
        # 速度 × 単位ベクトル」を丸めて求める（test_actor.py・test_main.py と
        # 同一の計算式）
        dist = math.hypot(*diff)
        return (
            round(start[0] + frames * Field.PLAYER_SPEED * diff[0] / dist),
            round(start[1] + frames * Field.PLAYER_SPEED * diff[1] / dist),
        )

    def _raw_rotate(self, diff):
        # 進行方向（差分の正規化単位ベクトル）に対応する、スナップされて
        # いない生の角度（0度=上方向・時計回りが正）。ROTATE_SNAP_STEP への
        # スナップは GameCore の描画時の責務であり、Field はこの生の値を
        # 返す（TestPlayerRotateAngle 参照）
        dist = math.hypot(*diff)
        return math.degrees(math.atan2(diff[0] / dist, -diff[1] / dist))

    def _tapped_dest(self, player_pos, diff):
        """プレイヤー（登録座標 player_pos）の画像中心点から差分 diff の
        クリック先ワールド座標を返す"""
        return (
            player_pos[0] + self.PLAYER_CENTER_OFFSET_X + diff[0],
            player_pos[1] + self.PLAYER_CENTER_OFFSET_Y + diff[1],
        )

    def _click_at(self, field, player_pos, diff):
        """プレイヤー（登録座標 player_pos）の画像中心点から差分 diff の
        ワールド座標を Field.set_click() へ渡す。渡したワールド座標を返す"""
        world = self._tapped_dest(player_pos, diff)
        field.set_click(*world)
        return world

    def _turn_player(self, field, diff):
        """初期位置からのクリックで方向転換し、そのフレームを進める
        （GameCore の _handle_tap → update() の結線と同じ順序: クリック
        指定の直後にそのフレームの前進が反映される）"""
        self._click_at(field, (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), diff)
        field.process_frame()

    def _make_mob_facing_initial_player(self, x, y):
        """速度 0 のモブを登録座標（スプライト左上） (x, y) へ生成し、初期
        プレイヤーの画像中心点の方向へ向けて返す（モブとプレイヤーは同サイズ
        のため中心点同士の方向は登録座標同士の方向と一致し、期待描画回転は
        軸沿いの自明値のまま）。Mob のコンストラクタは中心点を受け取るため、
        登録座標から画像サイズの半分を足して変換する"""
        mob = Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0)
        mob.turn_to(
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y,
        )
        return mob

    def _drop_at_mob(self, mob_pos):
        """登録座標（スプライト左上）mob_pos のモブと画像中心を揃えた
        ドロップ（速度0・通常種別）を返す（Field._spawn_drop() が撃破位置へ
        生成するのと同じ、モブ中心をそのまま渡す変換）。自動戦闘モードの
        モブ追尾と自動収集モードのドロップ追尾は、対象の画像中心が一致
        していれば同じ動きになるため、両モードを同じ期待値の組で検証する
        テスト（TestDestinationSuppressesAutoTrack 等）が追尾対象の注入に使う"""
        return Drop(
            mob_pos[0] + Mob.WIDTH / 2,
            mob_pos[1] + Mob.HEIGHT / 2,
            0,
            False,
        )

    def _drop_states_of(self, drops):
        """Drop オブジェクトのリストを、Field.drop_states() と同じ形式
        （登録座標・種別のタプルのリスト）へ変換する（field._drops へ注入
        した Drop をそのまま drop_states() の期待値として使うためのテスト
        専用の変換。公開 IF である drop_states() 自体の形式は変えない）"""
        return [(drop.image_x, drop.image_y, drop.is_rare) for drop in drops]


class TestPlayerAdvance(TestParent):
    """プレイヤーが毎フレーム一定速度で前進すること"""

    def test_player_advances_by_constant_speed_every_frame(self):
        test_cases = [
            ("1フレーム経過", 1),
            ("3フレーム経過", 3),
        ]
        for name, frame_count in test_cases:
            with self.subTest(name):
                field = Field()
                # モブの移動は本テストの検証対象外のため除去する
                field._mobs = []  # pylint: disable=W0212

                for _ in range(frame_count):
                    field.process_frame()

                self.assertEqual(
                    (
                        self.INITIAL_PLAYER_X,
                        round(self.INITIAL_PLAYER_Y - frame_count * Field.PLAYER_SPEED),
                        0.0,
                    ),
                    field.player_state(),
                )


class TestClickTurnsPlayer(TestParent):
    """クリック位置（ワールド座標）への方向転換、および目的地移動中の再
    クリックによる新しい目的地への転換の検証（スクリーン→ワールド座標
    変換は GameCore の責務のため、Field はワールド座標を直接受け取る）"""

    PRE_CLICK_FRAMES = 10

    def test_click_turns_player_toward_world_position(self):
        test_cases = [
            ("クリック後1フレーム（少数位置の丸め）", 1),
            ("クリック後10フレーム（少数の蓄積で整数へ到達）", 10),
        ]
        for name, post_click_frames in test_cases:
            with self.subTest(name):
                field = Field()
                field._mobs = []  # pylint: disable=W0212
                for _ in range(self.PRE_CLICK_FRAMES):
                    field.process_frame()
                start = (
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y - self.PRE_CLICK_FRAMES * Field.PLAYER_SPEED,
                )
                # 目的地は差分が 3:4:5 の直角三角形になるワールド座標
                diff = (30, 40)
                self._click_at(field, start, diff)
                field.process_frame()  # クリックを検知したフレーム
                for _ in range(post_click_frames - 1):
                    field.process_frame()

                player_x, player_y, player_rotate = field.player_state()
                self.assertEqual(
                    self._expected_pos(start, diff, post_click_frames),
                    (player_x, player_y),
                )
                self.assertAlmostEqual(self._raw_rotate(diff), player_rotate)

    def test_second_click_converts_to_new_destination(self):
        """目的地移動中に再度クリックすると、押下地点が新しい目的地として
        設定され、その方向へ向きを変えて目的地移動モードを継続すること
        （3回目のクリックでも同様に転換し続けることを含める）。ID-007の
        「再クリックで解除」仕様は本タスクで置き換えるため、以降クリックは
        常に「新しい目的地への転換」としてのみ扱われる"""
        first_diff = (30, 40)
        second_diff = (-40, -30)
        third_diff = (40, -30)
        test_cases = [
            ("2回目のクリックで新しい目的地へ転換する", [first_diff, second_diff]),
            (
                "3回目のクリックでも新しい目的地へ転換し続ける",
                [first_diff, second_diff, third_diff],
            ),
        ]

        for name, click_diffs in test_cases:
            with self.subTest(name):
                field = Field()
                field._mobs = []  # pylint: disable=W0212
                for _ in range(self.PRE_CLICK_FRAMES):
                    field.process_frame()
                pos = (
                    self.INITIAL_PLAYER_X,
                    self.INITIAL_PLAYER_Y - self.PRE_CLICK_FRAMES * Field.PLAYER_SPEED,
                )
                # クリックのたびに目的地・向きが更新されるため、直近のクリック
                # 位置とその向きでの経過フレーム数（10固定）から都度、
                # 期待位置を算出する
                dest, click_diff = None, None
                for click_diff in click_diffs:
                    dest = self._click_at(field, pos, click_diff)
                    field.process_frame()
                    for _ in range(9):
                        field.process_frame()
                    pos = self._expected_pos(pos, click_diff, 10)

                self.assertEqual(dest, field.destination)
                player_x, player_y, player_rotate = field.player_state()
                self.assertEqual(pos, (player_x, player_y))
                self.assertAlmostEqual(self._raw_rotate(click_diff), player_rotate)


class TestPlayerRotateAngle(TestParent):
    """player_state() が返す角度はスナップされていない生の値であること
    （ROTATE_SNAP_STEP へのスナップは GameCore の描画時の変換であり、Field
    の責務ではない）"""

    def test_player_state_returns_unsnapped_angle(self):
        test_cases = [
            ("右方向は+90度", (30, 0)),
            ("下方向は180度", (0, 40)),
            ("左方向は-90度", (-30, 0)),
            ("下方向よりわずかに左寄りの斜め方向", (-10, 200)),
        ]
        for name, diff in test_cases:
            with self.subTest(name):
                field = Field()
                field._mobs = []  # pylint: disable=W0212
                initial_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                self._click_at(field, initial_pos, diff)
                field.process_frame()

                self.assertAlmostEqual(self._raw_rotate(diff), field.player_state()[2])

    def test_player_state_boundary_angle_not_snapped_to_180(self):
        # GameCore はこの向きを描画時に180度へ読み替える（境界の丸め。
        # test_main.py の TestPlayerRotateDraw 参照）が、Field はスナップ
        # 前の生の値（約-177.14度）を返すため、180度とは明確に異なる
        field = Field()
        field._mobs = []  # pylint: disable=W0212
        self._click_at(
            field, (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), (-10, 200)
        )
        field.process_frame()
        self.assertNotAlmostEqual(180.0, field.player_state()[2], places=1)


class TestMobSpawnAtStart(TestParent):
    """ゲーム開始時に進行方向側の辺へモブが1匹出現すること"""

    def _expected_mob_rotate(self, mob_pos):
        diff = (
            self.INITIAL_PLAYER_X - mob_pos[0],
            self.INITIAL_PLAYER_Y - mob_pos[1],
        )
        dist = math.hypot(*diff)
        return math.degrees(math.atan2(diff[0] / dist, -diff[1] / dist))

    def test_one_mob_spawns_on_heading_side_edge_at_start(self):
        test_cases = [
            ("プレイヤー真上（プレイヤー方向は真下=180度）", self.INITIAL_PLAYER_X),
            ("線分の左端", 0),
            ("線分の右端", Field.SCREEN_WIDTH - Mob.WIDTH),
        ]
        for name, spawn_x in test_cases:
            with self.subTest(name):
                with patch("src.main.random.uniform", return_value=float(spawn_x)):
                    field = Field()

                mob_y = -Field.MOB_SPAWN_OFFSET
                self.assertEqual(
                    [(spawn_x, mob_y, self._expected_mob_rotate((spawn_x, mob_y)))],
                    field.mob_states(),
                )


class TestMobPeriodicSpawn(TestParent):
    """出現間隔ごとにモブが1匹追加されること"""

    def _mob_state_for_spawn_frame(self, spawn_frame, elapsed_frames):
        spawn_y = -spawn_frame * Field.PLAYER_SPEED - Field.MOB_SPAWN_OFFSET
        mob_y = round(spawn_y + (elapsed_frames - spawn_frame) * Field.MOB_SPEED)
        return (self.INITIAL_MOB_X, mob_y, 180.0)

    def test_mob_is_added_every_spawn_interval(self):
        interval = Field.MOB_SPAWN_INTERVAL
        test_cases = [
            ("間隔経過の直前までは開始時の1匹のみ", interval - 1, [0]),
            ("間隔の経過で2匹目が追加される", interval, [0, interval]),
            (
                "間隔の2回目の経過で3匹目が追加される",
                2 * interval,
                [0, interval, 2 * interval],
            ),
        ]
        for name, elapsed_frames, spawn_frames in test_cases:
            with self.subTest(name):
                field = Field()
                # モブはプレイヤー真上（弾道上）に出現するため、そのままでは
                # 弾の命中で消滅し追加の検証にならない。本テストの観点は出現
                # 間隔のみ（命中は TestMobDestroyedOnBulletHit の観点）のため、
                # 検証期間中は弾を発射させない
                field._player._bullet_shoot_interval = (  # pylint: disable=W0212
                    elapsed_frames + 1
                )
                for _ in range(elapsed_frames):
                    field.process_frame()

                self.assertEqual(
                    [
                        self._mob_state_for_spawn_frame(spawn_frame, elapsed_frames)
                        for spawn_frame in spawn_frames
                    ],
                    field.mob_states(),
                )


class TestMobSpawnEdgeByPlayerDirection(TestParent):
    """出現時点のプレイヤーの向きに応じて出現辺・オフセットが切り替わること"""

    def _expected_player_pos(self, diff):
        dist = math.hypot(*diff)
        frames = Field.MOB_SPAWN_INTERVAL
        return (
            round(self.INITIAL_PLAYER_X + frames * Field.PLAYER_SPEED * diff[0] / dist),
            round(self.INITIAL_PLAYER_Y + frames * Field.PLAYER_SPEED * diff[1] / dist),
        )

    def _expected_mob_on_edge(self, edge, player_x, player_y):
        camera_x = player_x - self.INITIAL_PLAYER_X
        camera_y = player_y - self.INITIAL_PLAYER_Y
        if edge == "bottom":
            mob_y = camera_y + Field.SCREEN_HEIGHT - Mob.HEIGHT + Field.MOB_SPAWN_OFFSET
            return (player_x, mob_y, 0.0)
        if edge == "left":
            return (camera_x - Field.MOB_SPAWN_OFFSET_SIDE, player_y, 90.0)
        mob_x = camera_x + Field.SCREEN_WIDTH - Mob.WIDTH + Field.MOB_SPAWN_OFFSET_SIDE
        return (mob_x, player_y, -90.0)

    def test_mob_spawns_from_edge_matching_player_direction(self):
        test_cases = [
            ("右向き（90度）は右辺", (60, 0), "right"),
            ("左向き（-90度）は左辺", (-60, 0), "left"),
            ("下向き（180度）は下辺", (0, 80), "bottom"),
        ]
        for name, diff, edge in test_cases:
            with self.subTest(name):
                player_x, player_y = self._expected_player_pos(diff)
                expected_mob = self._expected_mob_on_edge(edge, player_x, player_y)
                rand_value = float(player_x if edge == "bottom" else player_y)
                with patch("src.main.random.uniform", return_value=rand_value):
                    field = Field()
                    # 開始時の1匹（上辺出現）は本テストの検証対象外のため
                    # 除去し、方向転換後の出現間隔の経過で追加される2匹目
                    # のみを検証対象にする
                    field._mobs = []  # pylint: disable=W0212
                    self._turn_player(field, diff)
                    for _ in range(Field.MOB_SPAWN_INTERVAL - 1):
                        field.process_frame()

                self.assertEqual([expected_mob], field.mob_states())

    def _spawn_distance_from_player(self, diff, edge):
        """出現辺 edge（"bottom"/"right"）へタップで方向転換した後、出現間隔
        の経過で追加されるモブの、出現時点でのプレイヤーとの距離を返す"""
        player_x, player_y = self._expected_player_pos(diff)
        rand_value = float(player_x if edge == "bottom" else player_y)
        with patch("src.main.random.uniform", return_value=rand_value):
            field = Field()
            field._mobs = []  # pylint: disable=W0212
            self._turn_player(field, diff)
            for _ in range(Field.MOB_SPAWN_INTERVAL - 1):
                field.process_frame()

        mob_x, mob_y, _ = field.mob_states()[0]
        return math.hypot(mob_x - player_x, mob_y - player_y)

    def test_side_and_top_bottom_spawn_distance_from_player_is_equal(self):
        """出現辺が上下辺・左右辺のどちらでも、出現時点でのプレイヤーとの
        距離が揃うこと（画面の縦横差を出現オフセットで補う設計の、直接
        観測できる帰結）"""
        bottom_distance = self._spawn_distance_from_player((0, 80), "bottom")
        right_distance = self._spawn_distance_from_player((60, 0), "right")
        self.assertEqual(bottom_distance, right_distance)


class TestMobFollowsPlayerEveryFrame(TestParent):
    """モブが毎フレーム最大角度制限付きでプレイヤーへ追尾すること"""

    # クリック目的地への差分（右方向）。距離は検証フレーム数（最大
    # MOB_SPAWN_INTERVAL - 1 = 59）の前進（29.5）では明確に到着しない遠さ
    TAP_DIFF = (60, 0)

    def _expected_mob_following_player(self, frames):
        # Mob のコンストラクタは中心点を受け取るため、登録座標の初期出現
        # 位置（INITIAL_MOB_X/Y）から画像サイズの半分を足して変換する
        mob = Mob(
            self.INITIAL_MOB_X + Mob.WIDTH / 2,
            self.INITIAL_MOB_Y + Mob.HEIGHT / 2,
            Field.MOB_SPEED,
        )
        mob.turn_to(
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y,
        )
        for frame in range(1, frames + 1):
            player_x = round(self.INITIAL_PLAYER_X + frame * Field.PLAYER_SPEED)
            mob.turn_toward_limited(
                player_x + self.PLAYER_CENTER_OFFSET_X,
                self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y,
            )
            mob.advance()
        # field.mob_states() は登録座標を返すため、比較対象もそろえる
        return (mob.image_x, mob.image_y, mob.rotate_angle)

    def test_mob_keeps_turning_toward_player_after_player_turns(self):
        test_cases = [
            ("追従による位置のずれが現れるフレーム数", 30),
            ("回転のずれも現れるフレーム数", 40),
            ("出現間隔の直前", Field.MOB_SPAWN_INTERVAL - 1),
        ]
        for name, frames in test_cases:
            with self.subTest(name):
                expected_mob = self._expected_mob_following_player(frames)

                field = Field()
                self._turn_player(field, self.TAP_DIFF)
                for _ in range(frames - 1):
                    field.process_frame()

                mob_states = field.mob_states()
                self.assertEqual(1, len(mob_states))
                mob_x, mob_y, mob_rotate = mob_states[0]
                self.assertEqual(expected_mob[:2], (mob_x, mob_y))
                self.assertAlmostEqual(expected_mob[2], mob_rotate)


class TestPlayerAutoTracksNearestMob(TestParent):
    """画面内の最も近いモブへプレイヤーが毎フレーム向き続けること"""

    # 画面外に置くモブの x 座標（ワールド座標）。左辺の外側で、消滅判定矩形
    # （余白 MOB_DESPAWN_MARGIN）の内側で生存し続ける位置
    OFFSCREEN_MOB_X = -10

    def _assert_offscreen_mob_survives(self, x):
        self.assertLessEqual(x + Mob.WIDTH, 0)
        self.assertGreater(x + Mob.WIDTH, -Field.MOB_DESPAWN_MARGIN)

    def test_player_turns_toward_nearest_of_multiple_onscreen_mobs(self):
        frames = 10
        test_cases = [
            ("右のモブが最近傍", -30, 20, 90.0),
            ("左のモブが最近傍", 30, -20, -90.0),
        ]
        for name, far_dx, near_dx, player_rotate in test_cases:
            with self.subTest(name):
                field = Field()
                far_x = self.INITIAL_PLAYER_X + far_dx
                near_x = self.INITIAL_PLAYER_X + near_dx
                field._mobs = [  # pylint: disable=W0212
                    self._make_mob_facing_initial_player(far_x, self.INITIAL_PLAYER_Y),
                    self._make_mob_facing_initial_player(near_x, self.INITIAL_PLAYER_Y),
                ]

                for _ in range(frames):
                    field.process_frame()

                expected_player_x = round(
                    self.INITIAL_PLAYER_X
                    + frames * Field.PLAYER_SPEED * math.copysign(1, near_dx)
                )
                self.assertEqual(
                    (expected_player_x, self.INITIAL_PLAYER_Y, player_rotate),
                    field.player_state(),
                )
                self.assertEqual(
                    [
                        (far_x, self.INITIAL_PLAYER_Y, 90.0 if far_dx < 0 else -90.0),
                        (
                            near_x,
                            self.INITIAL_PLAYER_Y,
                            90.0 if near_dx < 0 else -90.0,
                        ),
                    ],
                    field.mob_states(),
                )

    def test_tracking_switches_when_nearest_mob_changes(self):
        field = Field()
        right_near_x = self.INITIAL_PLAYER_X + 20
        left_far_x = self.INITIAL_PLAYER_X - 30
        right_mob = self._make_mob_facing_initial_player(
            right_near_x, self.INITIAL_PLAYER_Y
        )
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(left_far_x, self.INITIAL_PLAYER_Y),
            right_mob,
        ]
        # 1 フレーム目: 右のモブ（距離 20 < 30）が最近傍
        field.process_frame()

        # 右のモブ（距離 19.5）より近い、左のモブ（距離 10.5）へ入れ替える
        left_nearest_x = self.INITIAL_PLAYER_X - 10
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(left_nearest_x, self.INITIAL_PLAYER_Y),
            right_mob,
        ]
        # 2 フレーム目: 新しい最近傍（左）へ向き直る
        field.process_frame()

        self.assertEqual(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y, -90.0),
            field.player_state(),
        )
        self.assertEqual(
            [
                (left_nearest_x, self.INITIAL_PLAYER_Y, 90.0),
                (right_near_x, self.INITIAL_PLAYER_Y, -90.0),
            ],
            field.mob_states(),
        )

    def test_offscreen_mob_is_not_tracked(self):
        onscreen_dy = 90
        onscreen_y = self.INITIAL_PLAYER_Y + onscreen_dy
        self._assert_offscreen_mob_survives(self.OFFSCREEN_MOB_X)
        self.assertLess(onscreen_y + Mob.HEIGHT, Field.SCREEN_HEIGHT)
        self.assertLess(self.INITIAL_PLAYER_X - self.OFFSCREEN_MOB_X, onscreen_dy)
        field = Field()
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(
                self.OFFSCREEN_MOB_X, self.INITIAL_PLAYER_Y
            ),
            self._make_mob_facing_initial_player(self.INITIAL_PLAYER_X, onscreen_y),
        ]

        frames = 2
        for _ in range(frames):
            field.process_frame()

        self.assertEqual(
            (
                self.INITIAL_PLAYER_X,
                round(self.INITIAL_PLAYER_Y + frames * Field.PLAYER_SPEED),
                180.0,
            ),
            field.player_state(),
        )
        # モブは速度 0 のため回転にかかわらず位置は変わらない。回転値自体は
        # 本クラスの観点（追尾対象の選択）の対象外のため位置のみ検証する
        # （モブの追尾の振る舞いは TestMobFollowsPlayerEveryFrame の対象）
        self.assertEqual(
            [
                (self.OFFSCREEN_MOB_X, self.INITIAL_PLAYER_Y),
                (self.INITIAL_PLAYER_X, onscreen_y),
            ],
            [(mob_x, mob_y) for mob_x, mob_y, _ in field.mob_states()],
        )

    def test_direction_is_kept_when_no_mob_is_onscreen(self):
        self._assert_offscreen_mob_survives(self.OFFSCREEN_MOB_X)
        field = Field()
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(
                self.OFFSCREEN_MOB_X, self.INITIAL_PLAYER_Y
            )
        ]

        frames = 2
        for _ in range(frames):
            field.process_frame()

        self.assertEqual(
            (
                self.INITIAL_PLAYER_X,
                round(self.INITIAL_PLAYER_Y - frames * Field.PLAYER_SPEED),
                0.0,
            ),
            field.player_state(),
        )
        # モブは速度 0 のため回転にかかわらず位置は変わらない（回転値は本
        # クラスの観点対象外のため位置のみ検証する）
        self.assertEqual(
            [(self.OFFSCREEN_MOB_X, self.INITIAL_PLAYER_Y)],
            [(mob_x, mob_y) for mob_x, mob_y, _ in field.mob_states()],
        )


class TestCollectModeSuppressesMobTracking(TestParent):
    """自動収集モード中は、画面内にモブがいてもモブへ向きが変わらないこと
    （ID-021 サイクル4 Red、振る舞いテスト）。

    仕様: 自動戦闘モード（既定）では画面内の最も近いモブの方向を向いて進む
    （TestPlayerAutoTracksNearestMob の既存挙動）。自動収集モードへ切り替えた
    後は、同じ位置に同じモブが画面内にいてもその方向へは向かず、直前の向き
    （生成直後＝真上）を維持したまま進み続ける（requirements.md §3.1）。

    本サイクルではドロップが1つも存在しない状況を対象とし、「モブを追尾
    しない」ことのみを固定する（自動収集モードで最も近いドロップへ向く
    挙動はサイクル5 の関心）。モードの保持・トグル自体は
    TestFieldTogglesPlayerMoveMode の関心。

    各ケースは (モード, 向き続ける方向) の自己完結した組であり、ケースごとに
    期待値の系統が変わるわけではないため、1つの subTest ループへまとめる
    （[[feedback_split_subtest_by_expectation]] の適用除外）。自動戦闘の
    ケースは「そのモブが画面内にあり追尾対象になり得る」ことを示す対照
    としても働く（自動収集のケースが、モブが画面外だったために向きが
    変わらなかった、という理由で通ることを防ぐ）"""

    # 画面内モブのプレイヤーからの x 差分（プレイヤーの左、同じ y）
    MOB_DX = -30
    FRAMES = 10
    # (設定するモード, 向き続ける方向の差分ベクトル)
    MODE_AND_EXPECTED_DIRECTION = (
        # 自動戦闘: 画面内のモブ（左）の方向を向いて進む
        (MoveMode.ATTACK, (MOB_DX, 0)),
        # 自動収集: モブへは向かず、生成直後の向き（真上）を維持して進む
        (MoveMode.COLLECT, (0, -1)),
    )

    def test_player_direction_per_move_mode_with_onscreen_mob(self):
        for mode, direction in self.MODE_AND_EXPECTED_DIRECTION:
            with self.subTest(mode=mode):
                field = Field()
                if mode is MoveMode.COLLECT:
                    field.toggle_player_move_mode()
                mob_x = self.INITIAL_PLAYER_X + self.MOB_DX
                field._mobs = [  # pylint: disable=W0212
                    self._make_mob_facing_initial_player(mob_x, self.INITIAL_PLAYER_Y)
                ]

                for _ in range(self.FRAMES):
                    field.process_frame()

                expected_x, expected_y = self._expected_pos(
                    (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                    direction,
                    self.FRAMES,
                )
                self.assertEqual(
                    (expected_x, expected_y, self._raw_rotate(direction)),
                    field.player_state(),
                )
                # モブは速度 0 のため位置は変わらない（回転値は本クラスの
                # 観点対象外のため位置のみ検証する）
                self.assertEqual(
                    [(mob_x, self.INITIAL_PLAYER_Y)],
                    [(m_x, m_y) for m_x, m_y, _ in field.mob_states()],
                )


class TestCollectModeTracksNearestDrop(TestParent):
    """自動収集モード中は、画面内の最も近いドロップの方向へ向いて進むこと
    （ID-021 サイクル5 Red、振る舞いテスト）。

    仕様: 自動収集モードでは画面内に存在するドロップのうち、プレイヤーの
    画像中心点から最も近いものの方向を毎フレーム向く（requirements.md
    §3.1「最も近いドロップの方向を向く」）。既存のモブ追尾
    （TestPlayerAutoTracksNearestMob）と同じく、
    対象は画面内（カメラオフセット基準の表示領域）に限り、画面外の
    ドロップは（消滅せず残っていても）追尾しない。自動戦闘モードでは
    逆にドロップの方向へは向かず、従来どおり最も近いモブを追尾する。

    本 Red で決定したスコープ:
    - **ドロップ不在時の挙動**: 直前の向きを維持する（画面内にモブが
      いない場合と同型）。この挙動はドロップが1つも存在しない状況を扱う
      TestCollectModeSuppressesMobTracking の自動収集ケースが既に固定
      しているため、本クラスでは重複して検証しない。
    - **目的地移動中の抑止**: 踏襲する。自動収集モード中でもフィールド
      押下で目的地が設定される（GameCore._handle_tap はモードによらず
      set_click する）ため、目的地移動中にドロップ追尾で向きが上書き
      されると目的地へ到達できなくなる。検証は既存クラス
      TestDestinationSuppressesAutoTrack へ自動収集モードのケースを
      追加する形で行う（モブと画像中心を揃えた位置にドロップを置けば
      両モードで期待値が一致するため。ユーザー指摘、2026-07-25）。
    - **ヒットバック中の抑止**: 同じく踏襲するが、専用のテストは追加
      しない。目的地・ヒットバックの抑止は _track_facing() の同じ
      early return 群で表現されており、ドロップ追尾をその抑止より前に
      置くという想定される実装ミスは目的地のケースで検出できるため
      （ヒットバック中にモブ追尾が抑止されることは
      TestPlayerHitbackOnMobContact が既に固定している）。

    各ケースは (モード, 向き続ける方向) の自己完結した組であり、ケースごとに
    期待値の系統が変わるわけではないため、1つの subTest ループへまとめる
    （[[feedback_split_subtest_by_expectation]] の適用除外。サイクル4 の
    TestCollectModeSuppressesMobTracking と同型）。モードの保持・トグル
    自体は TestFieldTogglesPlayerMoveMode の関心"""

    # 画面内モブのプレイヤーからの x 差分（プレイヤーの左、同じ y。
    # 自動戦闘モードの対照として TestCollectModeSuppressesMobTracking と
    # 同じ配置を使う）
    MOB_DX = -30
    # 画面内ドロップのプレイヤー中心点からの差分。最近傍（右、距離 30）と
    # それより遠いもの（下、距離 50）を別方向に置き、「最も近い方」が
    # 選ばれることを向く方向の違いで観測する
    NEAR_DROP_DIFF = (30, 0)
    FAR_DROP_DIFF = (0, 50)
    FRAMES = 10
    # (設定するモード, 向き続ける方向の差分ベクトル)
    MODE_AND_EXPECTED_DIRECTION = (
        # 自動戦闘: ドロップがあってもモブ（左）の方向を向いて進む
        (MoveMode.ATTACK, (MOB_DX, 0)),
        # 自動収集: モブではなく最も近いドロップ（右）の方向を向いて進む
        (MoveMode.COLLECT, NEAR_DROP_DIFF),
    )
    # 画面外に置くドロップのプレイヤー中心点からの差分（左辺の外側）と、
    # それより明確に遠い画面内のドロップの差分（下方向）
    OFFSCREEN_DROP_DIFF = (-83, 0)
    ONSCREEN_DROP_DIFF = (0, 90)
    OFFSCREEN_CASE_FRAMES = 2

    def _drop_at(self, diff):
        """プレイヤー（開始時の位置）の画像中心点から差分 diff の位置へ
        画像中心が来るドロップ（速度0・通常種別）を返す"""
        return Drop(
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X + diff[0],
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y + diff[1],
            0,
            False,
        )

    def test_player_direction_per_move_mode_with_onscreen_drops_and_mob(self):
        # 前進（FRAMES × PLAYER_SPEED = 5 ピクセル）後も最近傍のドロップは
        # 入れ替わらない（右のドロップまで 30 − 5 = 25、下のドロップまで
        # hypot(5, 50) ≈ 50.2）。回収されるほど近づくこともない
        #
        # 前提ガード: 上記の最近傍ドロップの最終距離（25px）が引き寄せ範囲の
        # 外にあること。本テストは「ドロップは移動せず、回収もされない」ことを
        # 検証するため、範囲内だと引き寄せによってこの前提が崩れる（ID-024 で
        # 追加）。引き寄せ範囲はプレイヤーの成長レベルに応じて広がるが、本
        # テストのプレイヤーは累計取得数0（レベル0）のままのため、レベル0の
        # 範囲（Field.DROP_ATTRACT_RANGE）と比較すればよい
        self.assertGreater(
            math.hypot(*self.NEAR_DROP_DIFF) - self.FRAMES * Field.PLAYER_SPEED,
            Field.DROP_ATTRACT_RANGE,
        )
        for mode, direction in self.MODE_AND_EXPECTED_DIRECTION:
            with self.subTest(mode=mode):
                field = Field()
                if mode is MoveMode.COLLECT:
                    field.toggle_player_move_mode()
                mob_x = self.INITIAL_PLAYER_X + self.MOB_DX
                field._mobs = [  # pylint: disable=W0212
                    self._make_mob_facing_initial_player(mob_x, self.INITIAL_PLAYER_Y)
                ]
                drops = [
                    self._drop_at(self.FAR_DROP_DIFF),
                    self._drop_at(self.NEAR_DROP_DIFF),
                ]
                field._drops = list(drops)  # pylint: disable=W0212

                for _ in range(self.FRAMES):
                    field.process_frame()

                expected_pos = self._expected_pos(
                    (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                    direction,
                    self.FRAMES,
                )
                self.assertEqual(
                    (*expected_pos, self._raw_rotate(direction)),
                    field.player_state(),
                )
                # ドロップは移動せず、回収もされない（追尾対象の選択が
                # 観点のため、位置が変わらないことのみ確認する）
                self.assertEqual(self._drop_states_of(drops), field.drop_states())

    def test_offscreen_drop_is_not_tracked(self):
        offscreen_drop = self._drop_at(self.OFFSCREEN_DROP_DIFF)
        onscreen_drop = self._drop_at(self.ONSCREEN_DROP_DIFF)
        # 画面外のドロップは表示領域の左外にありながら消滅領域
        # （表示領域と中心を揃えた一辺 SCREEN_HEIGHT × DROP_DESPAWN_VIEW_SCALE
        # の正方形）の内側のため消滅せずに残る
        self.assertLessEqual(offscreen_drop.image_x + Drop.WIDTH, 0)
        despawn_size = Field.SCREEN_HEIGHT * Field.DROP_DESPAWN_VIEW_SCALE
        self.assertGreater(
            offscreen_drop.image_x, -((despawn_size - Field.SCREEN_WIDTH) // 2)
        )
        # 画面内のドロップは表示領域の明確な内側にあり、画面外のドロップ
        # より遠い（近さだけで選ばれるなら画面外の方が選ばれる配置）
        self.assertLess(onscreen_drop.image_y + Drop.HEIGHT, Field.SCREEN_HEIGHT)
        self.assertLess(
            math.hypot(*self.OFFSCREEN_DROP_DIFF),
            math.hypot(*self.ONSCREEN_DROP_DIFF),
        )
        field = Field()
        field.toggle_player_move_mode()
        field._drops = [offscreen_drop, onscreen_drop]  # pylint: disable=W0212

        for _ in range(self.OFFSCREEN_CASE_FRAMES):
            field.process_frame()

        expected_pos = self._expected_pos(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
            self.ONSCREEN_DROP_DIFF,
            self.OFFSCREEN_CASE_FRAMES,
        )
        self.assertEqual(
            (*expected_pos, self._raw_rotate(self.ONSCREEN_DROP_DIFF)),
            field.player_state(),
        )


class TestFieldTogglesPlayerMoveMode(TestParent):
    """Field 経由でモードをトグルすると Player 側の状態が変わること（ID-021
    サイクル2 Red、構造テスト）。参照側は既存の委譲プロパティパターン
    （player_hp・player_is_invincible 等、L933-950）と同型の getter
    （player_move_mode property）。設定側（command）は、実際の利用箇所
    （GameCore._toggle_move_mode()、L1258-1260）が任意の値への set ではなく
    常にトグル（自動戦闘⇔自動収集の反転）のみであることを踏まえ、
    引数なしのトグルメソッド（toggle_player_move_mode()）とする（ユーザー
    指摘、2026-07-25。実際に使われない `set_player_move_mode(mode)` は
    speculative generalization のため採用しない
    〔[[feedback_no_speculative_generalization]]〕）。`Player` 自身の
    IF（`move_mode`/`set_move_mode()`、ID-021-2）は変更せず、`Field` が
    それらを使ってトグルの計算を行う想定。

    仕様: Field 生成直後の既定値は Player と同じく自動戦闘
    （MoveMode.ATTACK）。field.toggle_player_move_mode() を1回呼ぶと
    自動収集（COLLECT）へ、続けてもう1回呼ぶと自動戦闘（ATTACK）へ戻る。
    いずれも Field 自身の player_move_mode だけでなく、委譲先である
    Player 側の move_mode も変わることを検証する（Field 独自の状態を
    持たず Player へ委譲しているだけであることの確認のため、
    field._player.move_mode を直接参照する）。

    加えて、目的地移動モード中のトグルは2値の反転ではなく自動戦闘モードへの
    離脱になる（ID-022 サイクル6、requirements.md §3.1）:
    - 目的地移動中に toggle_player_move_mode() を呼ぶと自動戦闘モードになる
      （目的地移動へ入る前が自動収集モードであっても自動収集モードへは
      戻らない。到着による離脱が直前モードへ戻る
      〔TestPlayerMoveModeDuringDestinationMove〕のとは非対称で、モブ接触に
      よる離脱〔ID-022 サイクル2〕と同じ扱いになる）
    - 同時に目的地も解除される（目的地の有無から実効モードを導出する設計の
      ため、目的地が残っていると自動戦闘モードへ戻れない。解除は「旗が
      描画されなくなる」ことでも観測でき、その e2e は test_main.py の
      TestModeButtonToggle が扱う）

    各ケースは (トグル回数, 期待するモード) の自己完結した組であり、
    ケースごとに期待値の系統が変わるわけではないため、1つの subTest
    ループへまとめる（[[feedback_split_subtest_by_expectation]] の
    「ケースごとに期待値の組が変わってよい」場合の適用除外に該当。
    ユーザー指摘、2026-07-25）。目的地移動モード起点のケースは、期待値へ
    「目的地が解除される」が加わり期待値の系統が変わるため、既存のトグル表
    （0回／1回／2回）はそのままに別のケース表・別のテスト関数として分ける
    （同原則の適用）。

    モードが挙動へ及ぼす効果（攻撃停止・追尾停止）は
    TestPlayerShootInMoveMode（test_actor.py）・
    TestCollectModeSuppressesMobTracking で検証する。本クラスはトグルの
    結果を player_move_mode getter で直接読む唯一のテストのため、それらの
    振る舞いテストが本クラスの検証を包含することはない
    （[[feedback_keep_structure_test_unless_property_read]]。目的地の有無
    から導出される目的地移動モードを同 getter で読むテストは別にあるが
    〔TestPlayerMoveModeDuringDestinationMove、ID-022 サイクル4〕、
    トグルによる2値の切り替えは扱わないため本クラスの検証は包含されない）"""

    TOGGLE_COUNT_AND_EXPECTED_MODE = (
        (0, MoveMode.ATTACK),  # 未トグル＝既定値（自動戦闘）
        (1, MoveMode.COLLECT),  # 1回で自動収集へ切り替わる
        (2, MoveMode.ATTACK),  # 2回で自動戦闘へ戻る
    )

    # 目的地移動モード起点のケースで使うクリック目的地への差分（右方向、
    # 距離 20。TestPlayerMoveModeDuringDestinationMove と同じ値だが、本クラス
    # はクリック直後にトグルするだけでフレームを進めないため、到着までの
    # フレーム数は用いない）
    DESTINATION_TAP_DIFF = (20, 0)
    # 目的地移動モード起点のケース表（目的地移動へ入る前の基底モード）。
    # 期待値はどちらの起点でも「自動戦闘モードになり目的地も解除される」で
    # 共通のため、表は起点のモードのみを持つ（自動収集モード起点でも自動
    # 収集モードへ戻らないことがこのケース表の要点）
    BASE_MODE_BEFORE_DESTINATION_MOVE = (
        ("自動戦闘モードから目的地移動へ入った場合", MoveMode.ATTACK),
        ("自動収集モードから目的地移動へ入った場合", MoveMode.COLLECT),
    )

    def test_field_player_move_mode_after_toggles(self):
        for toggle_count, expected_mode in self.TOGGLE_COUNT_AND_EXPECTED_MODE:
            with self.subTest(toggle_count=toggle_count):
                field = Field()
                for _ in range(toggle_count):
                    field.toggle_player_move_mode()

                self.assertEqual(expected_mode, field.player_move_mode)
                self.assertEqual(
                    expected_mode, field._player.move_mode  # pylint: disable=W0212
                )

    def test_toggle_during_destination_move_switches_to_attack_and_clears_it(self):
        for name, base_mode in self.BASE_MODE_BEFORE_DESTINATION_MOVE:
            with self.subTest(name):
                field = Field()
                if base_mode is MoveMode.COLLECT:
                    field.toggle_player_move_mode()
                # クリックだけで目的地移動モードへ入るためフレームは進めない
                # （進めると到着・モブ接触といった別の離脱契機が混ざり得る）
                self._click_at(
                    field,
                    (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                    self.DESTINATION_TAP_DIFF,
                )
                self.assertEqual(MoveMode.DESTINATION, field.player_move_mode)

                field.toggle_player_move_mode()

                self.assertEqual(MoveMode.ATTACK, field.player_move_mode)
                # 基底モードも自動戦闘へ書き換わる（目的地の解除だけでは、
                # 自動収集モード起点のとき基底モードが再び現れてしまう）
                self.assertEqual(
                    MoveMode.ATTACK, field._player.move_mode  # pylint: disable=W0212
                )
                self.assertIsNone(field.destination)


class TestDestinationState(TestParent):
    """クリックで目的地状態が設定されること（旗の描画は test_main.py に残す
    観点のため本クラスの対象外）"""

    def test_destination_is_none_before_click(self):
        field = Field()
        self.assertIsNone(field.destination)

    def test_click_sets_destination_to_clicked_world_position(self):
        field = Field()
        field._mobs = []  # pylint: disable=W0212
        start = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
        diff = (30, 40)
        dest = self._click_at(field, start, diff)

        self.assertEqual(dest, field.destination)


class TestDestinationSuppressesAutoTrack(TestParent):
    """目的地移動中は自動追尾が抑止されること（自動戦闘モードのモブ追尾・
    自動収集モードのドロップ追尾のいずれも抑止される）。

    モブと画像中心を揃えた位置（モブ撃破時に実際にドロップが生成される
    位置と同じ、_spawn_drop() の変換）にドロップを置くと、追尾対象が
    モブかドロップかによらずクリック前後の動きが一致するため、両モードを
    同じ期待値の組で検証できる（ユーザー指摘、2026-07-25）"""

    # 画面内モブのプレイヤーからの x 差分（プレイヤーの左、同じ y）
    MOB_DX = -30
    # クリック目的地への差分（モブと反対の右方向）
    TAP_DIFF = (60, 0)
    PRE_CLICK_FRAMES = 10

    def test_click_suppresses_tracking_and_player_heads_to_destination(self):
        # (ケース名, 設定するモード, クリック後に進めるフレーム数)
        test_cases = [
            ("自動戦闘モードでクリックを検知したフレーム", MoveMode.ATTACK, 1),
            (
                "自動戦闘モードでクリック後も目的地の方向へ直進し続けるフレーム",
                MoveMode.ATTACK,
                10,
            ),
            ("自動収集モードでクリックを検知したフレーム", MoveMode.COLLECT, 1),
            (
                "自動収集モードでクリック後も目的地の方向へ直進し続けるフレーム",
                MoveMode.COLLECT,
                10,
            ),
        ]
        for name, mode, post_click_frames in test_cases:
            with self.subTest(name):
                self._assert_destination_overrides_tracking(mode, post_click_frames)

    def _assert_destination_overrides_tracking(self, mode, post_click_frames):
        field = Field()
        if mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        mob_pos = (self.INITIAL_PLAYER_X + self.MOB_DX, self.INITIAL_PLAYER_Y)
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(*mob_pos)
        ]
        # 追尾対象はモード次第（自動戦闘＝モブ、自動収集＝ドロップ）だが、
        # 両者は画像中心が一致するため向き・前進は同じになる
        drop = self._drop_at_mob(mob_pos)
        field._drops = [drop]  # pylint: disable=W0212
        # クリック前は自動追尾が働き、プレイヤーは左の追尾対象へ前進する
        for _ in range(self.PRE_CLICK_FRAMES):
            field.process_frame()
        click_start = self._expected_pos(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
            (self.MOB_DX, 0),
            self.PRE_CLICK_FRAMES,
        )
        dest = self._click_at(field, click_start, self.TAP_DIFF)
        field.process_frame()  # クリックを検知したフレーム
        for _ in range(post_click_frames - 1):
            field.process_frame()

        player_x, player_y, player_rotate = field.player_state()
        self.assertEqual(
            self._expected_pos(click_start, self.TAP_DIFF, post_click_frames),
            (player_x, player_y),
        )
        self.assertAlmostEqual(self._raw_rotate(self.TAP_DIFF), player_rotate)
        self.assertEqual(dest, field.destination)
        # 追尾対象（モブ・ドロップ）はいずれも動かず回収もされない
        # （目的地と反対方向にあり続け、抑止の検証が成立する）
        self.assertEqual([(*mob_pos, 90.0)], field.mob_states())
        self.assertEqual(self._drop_states_of([drop]), field.drop_states())


class TestDestinationArrivalResumesAutoTrack(TestParent):
    """目的地への到着で目的地状態が解除され、自動追尾へ戻ること（自動戦闘
    モードのモブ追尾・自動収集モードのドロップ追尾のいずれも再開する）。

    追尾再開の検証では、モブと画像中心を揃えた位置（モブ撃破時に実際に
    ドロップが生成される位置と同じ、_spawn_drop() の変換）にドロップを
    置くことで、追尾対象がモブかドロップかによらず同じ期待値の組で
    両モードを検証する（TestDestinationSuppressesAutoTrack と同型。
    ユーザー指摘、2026-07-25）。目的地の維持・解除自体はモードに依らない
    ため、その検証では追尾対象を一切置かない"""

    # クリック目的地への差分（右方向、距離 20）
    TAP_DIFF = (20, 0)
    # プレイヤー中心点が目的地ちょうどへ到達するフレーム数
    ARRIVAL_FRAMES = int(TAP_DIFF[0] / Field.PLAYER_SPEED)
    POST_ARRIVAL_FRAMES = 10
    # 到着後に注入する追尾対象（モブ・ドロップ）の、到着位置のプレイヤー
    # からの x 差分
    MOB_DX = -30

    def _start_destination_move(self, mode):
        """指定モードの Field を作り、追尾対象を除いた状態で目的地
        （TAP_DIFF）へのクリックとその検知フレームまでを進めて返す"""
        field = Field()
        if mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        field._mobs = []  # pylint: disable=W0212
        self._turn_player(field, self.TAP_DIFF)
        return field

    def test_destination_is_kept_before_arrival_and_cleared_after_arrival(self):
        # (ケース名, 設定するモード, 進めるフレーム数, 目的地が維持されるか)
        arrival_frames = self.ARRIVAL_FRAMES + self.POST_ARRIVAL_FRAMES
        test_cases = [
            ("自動戦闘モードで到着前は目的地が維持される", MoveMode.ATTACK, 10, True),
            (
                "自動戦闘モードで到着後は目的地が解除される",
                MoveMode.ATTACK,
                arrival_frames,
                False,
            ),
            ("自動収集モードで到着前は目的地が維持される", MoveMode.COLLECT, 10, True),
            (
                "自動収集モードで到着後は目的地が解除される",
                MoveMode.COLLECT,
                arrival_frames,
                False,
            ),
        ]
        for name, mode, frames, destination_is_kept in test_cases:
            with self.subTest(name):
                start = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                field = self._start_destination_move(mode)
                for _ in range(frames - 1):
                    field.process_frame()

                self.assertEqual(
                    self._expected_pos(start, self.TAP_DIFF, frames),
                    field.player_state()[:2],
                )
                if destination_is_kept:
                    self.assertIsNotNone(field.destination)
                else:
                    self.assertIsNone(field.destination)

    def test_auto_track_resumes_toward_onscreen_target_after_arrival(self):
        # (ケース名, 設定するモード)
        test_cases = [
            ("自動戦闘モードでは最も近いモブへの追尾が再開する", MoveMode.ATTACK),
            ("自動収集モードでは最も近いドロップへの追尾が再開する", MoveMode.COLLECT),
        ]
        for name, mode in test_cases:
            with self.subTest(name):
                self._assert_auto_track_resumes_after_arrival(mode)

    def _assert_auto_track_resumes_after_arrival(self, mode):
        start = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
        field = self._start_destination_move(mode)
        for _ in range(self.ARRIVAL_FRAMES - 1):
            field.process_frame()

        # 到着済み（目的地状態は解除済み）のプレイヤーの左（同じ y）へ速度 0
        # のモブと、それと画像中心を揃えたドロップを注入する。追尾対象は
        # モード次第（自動戦闘＝モブ、自動収集＝ドロップ）だが、両者は
        # 画像中心が一致するため向き・前進は同じになる
        arrival_pos = self._expected_pos(start, self.TAP_DIFF, self.ARRIVAL_FRAMES)
        mob_x = arrival_pos[0] + self.MOB_DX
        camera_x = arrival_pos[0] - self.INITIAL_PLAYER_X
        # テストデータの前提: 追尾対象は注入時点の画面内にあること
        # （ドロップはモブと中心が一致するため、モブの判定で足りる）
        self.assertTrue(camera_x <= mob_x < camera_x + Field.SCREEN_WIDTH)
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(mob_x, self.INITIAL_PLAYER_Y)
        ]
        drop = self._drop_at_mob((mob_x, self.INITIAL_PLAYER_Y))
        field._drops = [drop]  # pylint: disable=W0212
        for _ in range(self.POST_ARRIVAL_FRAMES):
            field.process_frame()

        self.assertIsNone(field.destination)
        player_x, player_y, player_rotate = field.player_state()
        self.assertEqual(
            self._expected_pos(arrival_pos, (self.MOB_DX, 0), self.POST_ARRIVAL_FRAMES),
            (player_x, player_y),
        )
        self.assertAlmostEqual(-90.0, player_rotate)
        # 追尾対象（モブ・ドロップ）はいずれも動かず回収もされない
        self.assertEqual([(mob_x, self.INITIAL_PLAYER_Y, 90.0)], field.mob_states())
        self.assertEqual(self._drop_states_of([drop]), field.drop_states())


class TestPlayerMoveModeDuringDestinationMove(TestParent):
    """目的地移動中は Field.player_move_mode が目的地移動モードを返し、目的地
    へ到着すると目的地移動モードへ入る前のモードへ戻ること（ID-022 サイクル4、
    requirements.md §3.1、ユーザー決定 2026-07-26）。

    仕様（このテストで固定する）:
    - 目的地が設定されている間、Field.player_move_mode は目的地移動モード
      （MoveMode.DESTINATION。値の名称をこの Red で決定する）を返す
    - 基底モード（Player.move_mode）は自動戦闘／自動収集の2値のままで、
      目的地の有無に影響されない（3値化は Field の公開 IF 側にのみ現れる）
    - 目的地へ到着すると、目的地移動モードへ入る前のモード（自動戦闘起点
      なら自動戦闘、自動収集起点なら自動収集）へ戻る

    実効モードを Field 側の独立した状態として持たず「目的地の有無」から
    導出する設計（ユーザー決定 2026-07-26）のため、到着で目的地が解除
    されれば基底モードが再び現れる。基底モード（field._player.move_mode）を
    直接読むのは、目的地移動中も基底モードが書き換えられずに保存されている
    こと（＝復元処理を持たずに戻れること）を確認するため（委譲先を直接
    参照する点は TestFieldTogglesPlayerMoveMode と同型）。

    目的地移動モードからの他の出口は本クラスの関心ではない:
    モブ接触による離脱（起点によらず自動戦闘モードへ戻る。ID-022 サイクル2）は
    TestPlayerHitbackOnMobContact の
    test_move_mode_becomes_attack_and_mob_tracking_resumes_after_contact_from_collect_mode
    で検証済みで、ボタン押下による離脱（同じく起点によらず自動戦闘モードへ
    戻る。ID-022 サイクル6）は TestFieldTogglesPlayerMoveMode の
    test_toggle_during_destination_move_switches_to_attack_and_clears_it
    で検証する。目的地移動中に自動
    追尾が抑止されること自体は TestDestinationSuppressesAutoTrack、目的地の
    維持・解除自体は TestDestinationArrivalResumesAutoTrack の関心のため、
    ここではモード値のみを検証する"""

    # クリック目的地への差分（右方向、距離 20）と、プレイヤー中心点がそこへ
    # ちょうど到達するフレーム数（TestDestinationArrivalResumesAutoTrack と
    # 同じ計算式）。到着前の観測フレーム数は、その到達フレーム数より明確に
    # 少ない値とする
    TAP_DIFF = (20, 0)
    ARRIVAL_FRAMES = int(TAP_DIFF[0] / Field.PLAYER_SPEED)
    PRE_ARRIVAL_FRAMES = 10

    def _start_destination_move(self, base_mode):
        """指定した基底モードの Field を作り、追尾対象を置かない状態で目的地
        （TAP_DIFF）へのクリックとその検知フレームまでを進めて返す
        （TestDestinationArrivalResumesAutoTrack の同名ヘルパーと同型）"""
        field = Field()
        if base_mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        field._mobs = []  # pylint: disable=W0212
        self._turn_player(field, self.TAP_DIFF)
        return field

    def test_player_move_mode_is_destination_before_arrival_and_base_mode_after(self):
        # (ケース名, 目的地移動へ入る前の基底モード, 進めるフレーム数,
        #  player_move_mode の期待値)
        test_cases = [
            (
                "自動戦闘モードから入ると到着前は目的地移動モード",
                MoveMode.ATTACK,
                self.PRE_ARRIVAL_FRAMES,
                MoveMode.DESTINATION,
            ),
            (
                "自動戦闘モードから入ると到着後は自動戦闘モードへ戻る",
                MoveMode.ATTACK,
                self.ARRIVAL_FRAMES,
                MoveMode.ATTACK,
            ),
            (
                "自動収集モードから入ると到着前は目的地移動モード",
                MoveMode.COLLECT,
                self.PRE_ARRIVAL_FRAMES,
                MoveMode.DESTINATION,
            ),
            (
                "自動収集モードから入ると到着後は自動収集モードへ戻る",
                MoveMode.COLLECT,
                self.ARRIVAL_FRAMES,
                MoveMode.COLLECT,
            ),
        ]
        for name, base_mode, frames, expected_mode in test_cases:
            with self.subTest(name):
                field = self._start_destination_move(base_mode)
                for _ in range(frames - 1):
                    field.process_frame()

                self.assertEqual(expected_mode, field.player_move_mode)
                # 基底モードは目的地の有無によらず2値のまま保存されている
                self.assertEqual(
                    base_mode, field._player.move_mode  # pylint: disable=W0212
                )


class TestDestinationMoveResumesShootingInCollectMode(TestParent):
    """自動収集モード中にフィールドを押下して目的地移動モードへ入ると攻撃が
    再開し、目的地へ到着して自動収集モードへ戻ると再び攻撃が止まること
    （ID-022 サイクル4、ユーザー決定 2026-07-25・2026-07-26）。

    Player 単体での発射可否（自動収集モードでも目的地が設定されている間は
    shoot() が弾を返す）は test_actor.py の TestPlayerShootInMoveMode で
    検証済みのため、本クラスの関心は set_click() 〜 process_frame() の経路が
    そこへ結線されていること（押下でクリック位置が Player の目的地として
    渡り、到着で解除されること）に絞る。

    基準の発射間隔（BULLET_SHOOT_INTERVAL = 30フレーム）のままでは、3つの
    観測フェーズ（押下前・目的地移動中・到着後）で発射契機を待つ合計
    フレーム数がモブの出現間隔（MOB_SPAWN_INTERVAL = 60フレーム）を超え、
    途中で出現したモブとの接触（目的地移動モードからの離脱契機）が混ざって
    しまう。そのため発射間隔を短く上書きし、各フェーズを最小フレーム数で
    観測する（TestMobPeriodicSpawn 等が別の理由で
    _bullet_shoot_interval を上書きするのと同じ手法）"""

    # 上書きする発射間隔（1フェーズにちょうど1回の発射契機が来る最小値）
    SHOOT_INTERVAL = 2
    # クリック目的地への差分（右方向、距離 20）と、プレイヤー中心点がそこへ
    # ちょうど到達するフレーム数（TestDestinationArrivalResumesAutoTrack と
    # 同じ計算式）。SHOOT_INTERVAL より十分長いため、到着前に必ず発射契機が
    # 訪れる
    TAP_DIFF = (20, 0)
    ARRIVAL_FRAMES = int(TAP_DIFF[0] / Field.PLAYER_SPEED)
    # 1回の発射で返る弾数（通常ドロップ未回収＝成長レベル1では多方向化せず
    # 進行方向へ1発。多方向化そのものは TestShootingGrowsOnNormalDropCollect
    # の関心）
    BULLETS_PER_SHOT = 1

    def test_shooting_resumes_during_destination_move_and_stops_after_arrival(self):
        field = Field()
        field.toggle_player_move_mode()
        # モブは追尾・接触（接触は目的地移動モードからの離脱契機）を避ける
        # ため除去する（進めるフレーム数の合計は出現間隔 MOB_SPAWN_INTERVAL
        # 未満に収め、途中の出現もさせない）
        field._mobs = []  # pylint: disable=W0212
        field._player._bullet_shoot_interval = (  # pylint: disable=W0212
            self.SHOOT_INTERVAL
        )

        # 押下前（目的地なしの自動収集モード）は発射契機が来ても発射しない
        for _ in range(self.SHOOT_INTERVAL):
            field.process_frame()
        self.assertEqual([], field.bullet_states())

        # フィールドを押下して目的地移動モードへ入ると攻撃が再開する
        # （押下位置は、押下前フレームで初期進行方向〔真上〕へ前進した
        # プレイヤーの画像中心点からの差分で求める）
        click_start = self._expected_pos(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
            (0, -1),
            self.SHOOT_INTERVAL,
        )
        self._click_at(field, click_start, self.TAP_DIFF)
        for _ in range(self.SHOOT_INTERVAL):
            field.process_frame()

        # 前提: まだ到着しておらず目的地移動モードが続いている
        self.assertIsNotNone(field.destination)
        self.assertEqual(self.BULLETS_PER_SHOT, len(field.bullet_states()))

        # 到着して自動収集モードへ戻ると再び攻撃が止まる
        for _ in range(self.ARRIVAL_FRAMES - self.SHOOT_INTERVAL):
            field.process_frame()
        self.assertIsNone(field.destination)
        # 目的地移動中に発射済みの弾を取り除き、到着後のフレームで新たに
        # 発射されないことだけを見る（TestPlayerHitbackOnMobContact が接触後の
        # 検証で発射済みの弾を取り除くのと同じ手法）
        field._bullets = []  # pylint: disable=W0212
        for _ in range(self.SHOOT_INTERVAL):
            field.process_frame()

        self.assertEqual([], field.bullet_states())


class TestSecondClickChangesDestination(TestParent):
    """目的地移動中の再クリックで、押下地点が新しい目的地として設定され、
    その方向へ向きを変え、目的地移動モードが継続すること（destination が
    None にならないこと。ID-007の「再クリックで解除」仕様の置き換え）。

    自動追尾が再開しないこと（＝抑止されたまま新しい目的地へ転換する
    こと）の検証では、モブと画像中心を揃えたドロップ（_drop_at_mob()）を
    併せて注入し、追尾対象がモブかドロップかによらず同じ期待値の組で両
    モードを検証する（TestDestinationSuppressesAutoTrack・
    TestDestinationArrivalResumesAutoTrack と同型。ユーザー指摘、
    2026-07-25）。向き転換の検証はモードに依らないため、そちらでは追尾
    対象を一切置かない"""

    TAP_DIFF = (60, 0)
    # 2回目のクリック位置の、その時点のプレイヤー中心点からの差分
    # （進行方向・追尾対象のいずれとも異なる方向）
    SECOND_TAP_DIFF = (0, -60)
    DEST_FRAMES = 10
    MOB_DX = -30
    POST_SECOND_CLICK_FRAMES = 10

    def test_second_click_sets_new_destination_and_turns_player_when_no_target(self):
        # (ケース名, 設定するモード, 2回目のクリック後に進めるフレーム数)
        test_cases = [
            ("自動戦闘モードで2回目のクリックを検知したフレーム", MoveMode.ATTACK, 1),
            (
                "自動戦闘モードで2回目のクリック後も新しい目的地へ前進し続けるフレーム",
                MoveMode.ATTACK,
                self.POST_SECOND_CLICK_FRAMES,
            ),
            ("自動収集モードで2回目のクリックを検知したフレーム", MoveMode.COLLECT, 1),
            (
                "自動収集モードで2回目のクリック後も新しい目的地へ前進し続けるフレーム",
                MoveMode.COLLECT,
                self.POST_SECOND_CLICK_FRAMES,
            ),
        ]
        for name, mode, post_click_frames in test_cases:
            with self.subTest(name):
                field = Field()
                if mode is MoveMode.COLLECT:
                    field.toggle_player_move_mode()
                field._mobs = []  # pylint: disable=W0212
                start = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y)
                self._click_at(field, start, self.TAP_DIFF)
                field.process_frame()
                for _ in range(self.DEST_FRAMES - 1):
                    field.process_frame()

                second_start = self._expected_pos(
                    start, self.TAP_DIFF, self.DEST_FRAMES
                )
                second_dest = self._click_at(field, second_start, self.SECOND_TAP_DIFF)
                field.process_frame()  # 2回目のクリックを検知したフレーム
                for _ in range(post_click_frames - 1):
                    field.process_frame()

                self.assertEqual(second_dest, field.destination)
                player_x, player_y, player_rotate = field.player_state()
                self.assertEqual(
                    self._expected_pos(
                        second_start, self.SECOND_TAP_DIFF, post_click_frames
                    ),
                    (player_x, player_y),
                )
                self.assertAlmostEqual(
                    self._raw_rotate(self.SECOND_TAP_DIFF), player_rotate
                )

    def test_auto_track_remains_suppressed_after_second_click(self):
        # (ケース名, 設定するモード)
        test_cases = [
            (
                "自動戦闘モードでも最も近いモブへは向かわず新しい目的地へ向かう",
                MoveMode.ATTACK,
            ),
            (
                "自動収集モードでも最も近いドロップへは向かわず新しい目的地へ向かう",
                MoveMode.COLLECT,
            ),
        ]
        for name, mode in test_cases:
            with self.subTest(name):
                self._assert_auto_track_stays_suppressed_after_second_click(mode)

    def _assert_auto_track_stays_suppressed_after_second_click(self, mode):
        field = Field()
        if mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        mob_pos = (self.INITIAL_PLAYER_X + self.MOB_DX, self.INITIAL_PLAYER_Y)
        field._mobs = [  # pylint: disable=W0212
            self._make_mob_facing_initial_player(*mob_pos)
        ]
        # 追尾対象はモード次第（自動戦闘＝モブ、自動収集＝ドロップ）だが、
        # 両者は画像中心が一致するため向き・前進は同じになる
        drop = self._drop_at_mob(mob_pos)
        field._drops = [drop]  # pylint: disable=W0212
        # クリック前は自動追尾が働き、プレイヤーは左の追尾対象へ前進する
        for _ in range(self.DEST_FRAMES):
            field.process_frame()
        tap_start = self._expected_pos(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
            (self.MOB_DX, 0),
            self.DEST_FRAMES,
        )
        # 1回目のクリック: 追尾対象と反対の右方向への目的地移動を開始する
        self._click_at(field, tap_start, self.TAP_DIFF)
        field.process_frame()
        for _ in range(self.DEST_FRAMES - 1):
            field.process_frame()

        # 2回目のクリック: 新しい目的地へ転換する。自動追尾は再開せず、
        # 追尾対象ではなく2回目のクリック位置へ向かうこと
        second_start = self._expected_pos(tap_start, self.TAP_DIFF, self.DEST_FRAMES)
        camera_x = second_start[0] - self.INITIAL_PLAYER_X
        # テストデータの前提: 追尾対象は2回目のクリック時点の画面内にある
        # こと（ドロップはモブと中心が一致するため、モブの判定で足りる）
        self.assertTrue(camera_x <= mob_pos[0] < camera_x + Field.SCREEN_WIDTH)
        second_dest = self._click_at(field, second_start, self.SECOND_TAP_DIFF)
        field.process_frame()
        for _ in range(self.POST_SECOND_CLICK_FRAMES - 1):
            field.process_frame()

        self.assertEqual(second_dest, field.destination)
        player_x, player_y, player_rotate = field.player_state()
        self.assertEqual(
            self._expected_pos(
                second_start, self.SECOND_TAP_DIFF, self.POST_SECOND_CLICK_FRAMES
            ),
            (player_x, player_y),
        )
        self.assertAlmostEqual(self._raw_rotate(self.SECOND_TAP_DIFF), player_rotate)
        # 追尾対象（モブ・ドロップ）はいずれも動かず回収もされない（モブは
        # プレイヤーの位置を毎フレーム追って緩やかに向きを変える仕様
        # 〔process_frame() の turn_toward_limited()〕があるため、本テストの
        # 観点である「位置」のみを検証し、向きは対象外とする）
        self.assertEqual([mob_pos], [(m_x, m_y) for m_x, m_y, _ in field.mob_states()])
        self.assertEqual(self._drop_states_of([drop]), field.drop_states())


class TestMobDespawnOutsideView(TestParent):
    """完全に画面外へ出たモブが取り除かれること（残存モブの回転値は本クラス
    の観点対象外のため、位置のみを検証する）"""

    DESPAWN_MARGIN = Field.MOB_DESPAWN_MARGIN

    def _run_process_frame_with_mobs(self, positions, pre_frames=0, click_diff=None):
        field = Field()
        # 開始時の1匹は検証対象外のため除去し、注入したモブのみを判定対象にする
        field._mobs = []  # pylint: disable=W0212
        for _ in range(pre_frames):
            field.process_frame()
        # Mob のコンストラクタは中心点を受け取るため、positions（登録座標）
        # から画像サイズの半分を足して変換する
        field._mobs = [  # pylint: disable=W0212
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in positions
        ]
        if click_diff is not None:
            self._click_at(field, self._expected_player_pos(pre_frames), click_diff)
        field.process_frame()
        return field

    def _expected_player_pos(self, frames):
        return (
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - frames * Field.PLAYER_SPEED),
        )

    def _assert_kept_positions(self, field, kept_positions):
        self.assertEqual(
            list(kept_positions),
            [(mob_x, mob_y) for mob_x, mob_y, _ in field.mob_states()],
        )

    def test_mob_clearly_outside_view_is_removed(self):
        player_pos = self._expected_player_pos(1)
        player_x, player_y = player_pos
        inside_pos = (player_x + 20, player_y)
        # プレイヤーの進行方向（上）の真上の遠い位置をクリックし、目的地
        # 移動中（追尾抑止）の状態で検証する（進行方向はクリック前と変わら
        # ないため、期待値は上方向への直進のまま）
        click_diff = (0, -60)
        test_cases = [
            ("上方向の明確な画面外", (player_x, player_y - 2 * Field.SCREEN_HEIGHT)),
            ("下方向の明確な画面外", (player_x, player_y + 2 * Field.SCREEN_HEIGHT)),
            ("左方向の明確な画面外", (player_x - 2 * Field.SCREEN_WIDTH, player_y)),
            ("右方向の明確な画面外", (player_x + 2 * Field.SCREEN_WIDTH, player_y)),
        ]
        for name, outside_pos in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_mobs(
                    [outside_pos, inside_pos], click_diff=click_diff
                )
                self._assert_kept_positions(field, [inside_pos])

    def test_mob_is_removed_exactly_when_fully_outside_despawn_rect(self):
        player_pos = self._expected_player_pos(1)
        player_x, player_y = player_pos
        camera_x = player_x - self.INITIAL_PLAYER_X
        camera_y = player_y - self.INITIAL_PLAYER_Y
        left_removed = camera_x - self.DESPAWN_MARGIN - Mob.WIDTH
        right_removed = camera_x + Field.SCREEN_WIDTH + self.DESPAWN_MARGIN
        top_removed = camera_y - self.DESPAWN_MARGIN - Mob.HEIGHT
        bottom_removed = camera_y + Field.SCREEN_HEIGHT + self.DESPAWN_MARGIN
        test_cases = [
            ("左辺", (left_removed, player_y), (left_removed + 1, player_y)),
            ("右辺", (right_removed, player_y), (right_removed - 1, player_y)),
            ("上辺", (player_x, top_removed), (player_x, top_removed + 1)),
            ("下辺", (player_x, bottom_removed), (player_x, bottom_removed - 1)),
        ]
        for name, removed_pos, kept_pos in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_mobs([removed_pos, kept_pos])
                self._assert_kept_positions(field, [kept_pos])

    def test_despawn_boundary_follows_camera_offset(self):
        total_frames = 12
        player_pos = self._expected_player_pos(total_frames)
        player_x, _ = player_pos
        camera_y = player_pos[1] - self.INITIAL_PLAYER_Y
        bottom_removed = camera_y + Field.SCREEN_HEIGHT + self.DESPAWN_MARGIN
        # テストデータの前提: 開始時のカメラ（オフセット0）基準の消滅境界より
        # 内側（カメラ追従しない誤実装では消滅しない位置）であること
        self.assertLess(bottom_removed, Field.SCREEN_HEIGHT + self.DESPAWN_MARGIN)

        field = self._run_process_frame_with_mobs(
            [(player_x, bottom_removed), (player_x, bottom_removed - 1)],
            pre_frames=total_frames - 1,
        )

        self._assert_kept_positions(field, [(player_x, bottom_removed - 1)])

    def test_mob_at_spawn_position_is_not_removed(self):
        player_pos = self._expected_player_pos(1)
        player_x, player_y = player_pos
        camera_x = player_x - self.INITIAL_PLAYER_X
        camera_y = player_y - self.INITIAL_PLAYER_Y
        positions = [
            (player_x, camera_y - Field.MOB_SPAWN_OFFSET),
            (
                player_x,
                camera_y + Field.SCREEN_HEIGHT - Mob.HEIGHT + Field.MOB_SPAWN_OFFSET,
            ),
            (camera_x - Field.MOB_SPAWN_OFFSET_SIDE, player_y),
            (
                camera_x + Field.SCREEN_WIDTH - Mob.WIDTH + Field.MOB_SPAWN_OFFSET_SIDE,
                player_y,
            ),
        ]

        field = self._run_process_frame_with_mobs(positions)

        self._assert_kept_positions(field, positions)


class TestBulletAdvancesStraightEveryFrame(TestParent):
    """発射済みの弾が発射時点の向きのまま毎フレーム一定速度で直進し続けること
    （検証対象は最初に発射される1発。発射契機の判定・タイマーは Player
    自身が持つため（advance() の呼び出し回数で計る）、Field 生成直後には
    まだ弾は存在せず、発射間隔ぶん process_frame() を進めた時点で初めて
    1発発射される。射程到達による消滅は本ファイルの
    TestBulletDespawnOutOfRange で検証する。発射後にプレイヤーが向きを
    変えても既存の弾の向きには影響しないこと、および一定間隔での発射は
    test_actor.py の TestPlayerShoot（Player.shoot()/advance() の単体
    テスト）で検証済みのためここでは扱わない）"""

    def _fire_first_bullet(self):
        """発射間隔ぶん process_frame() を進め、最初の1発が発射された
        直後（まだ移動していない）の Field と、その弾の発射時点の状態
        （登録座標）を返す"""
        field = Field()
        # モブの移動・追尾は本テストの検証対象外のため除去する
        field._mobs = []  # pylint: disable=W0212
        for _ in range(Player.BULLET_SHOOT_INTERVAL):
            field.process_frame()
        (start,) = field.bullet_states()
        return field, start

    def _expected_bullet_state(self, start, frames):
        # 発射時点のプレイヤーの向き（setUp でモブは画面外のため自動追尾が
        # 働かず、初期の進行方向＝真上のまま発射される）は変わらないため、
        # x は変わらず y のみ「フレーム数 × 速度」だけ減る（少数のまま蓄積し
        # 参照時に丸める。test_actor.py・TestPlayerAdvance と同一の計算式）
        start_x, start_y = start
        return (start_x, round(start_y - frames * Player.BULLET_SPEED))

    def test_bullet_advances_in_fired_direction_every_frame(self):
        test_cases = [
            ("1フレーム経過（少数位置の丸め）", 1),
            ("10フレーム経過（少数の蓄積）", 10),
        ]
        for name, frames in test_cases:
            with self.subTest(name):
                field, start = self._fire_first_bullet()

                for _ in range(frames):
                    field.process_frame()

                self.assertEqual(
                    [self._expected_bullet_state(start, frames)], field.bullet_states()
                )


class TestBulletDespawnOutOfRange(TestParent):
    """プレイヤーの画面上の位置から射程（Field.BULLET_RANGE）だけ離れた弾が
    process_frame() 後に bullet_states() から取り除かれ、射程内の弾は残ること
    （requirements.md §3.3。表示領域外での消滅を置き換える判定）。

    カメラオフセットはプレイヤーの画面上の位置を常に固定値へ保つため、
    「画面上の距離」は弾とプレイヤーの画像中心点同士のワールド座標上の
    距離と一致する（双方 round() 済みの整数を経由するため丸め差も出ない）。
    要件が「ワールド座標ではなく画面上の位置で」と言うのは、縦横で非対称な
    表示領域矩形（150×200）による判定を否定する趣旨のため、方向によって
    結果が変わらないことを軸方向・斜め方向の双方で固定する。

    他の消滅判定（表示領域外・ドロップ消滅領域）と異なり、境界ちょうどの
    位置を仕様として固定する。射程は弾が消える位置としてプレイヤーの目に
    直接見える距離であり、境界の1pxが「どこまで届くか」の体感に直結する
    ため。距離が射程ちょうどで消滅し、射程−1px では残ることを検証する"""

    def _expected_player_pos(self, frames):
        return (
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - frames * Field.PLAYER_SPEED),
        )

    def _bullet_pos_at(self, player_pos, diff):
        """プレイヤー（登録座標 player_pos）の画像中心点から差分 diff だけ
        離れた位置に画像中心点を置く弾の登録座標を返す（射程判定は中心点
        同士の距離のため、テストデータは中心点の差分で組み立てる）"""
        return (
            player_pos[0] + self.PLAYER_CENTER_OFFSET_X + diff[0] - Bullet.WIDTH // 2,
            player_pos[1] + self.PLAYER_CENTER_OFFSET_Y + diff[1] - Bullet.HEIGHT // 2,
        )

    def _run_process_frame_with_bullets(self, positions):
        field = Field()
        # モブの移動・追尾・命中は本テストの検証対象外のため除去する
        field._mobs = []  # pylint: disable=W0212
        # 注入した弾のみを対象にするため弾リストを置き換える。Bullet の
        # コンストラクタは中心点を受け取るため、positions（登録座標）から
        # 画像サイズの半分を足して変換する。速度 0 のため process_frame() の
        # 前進では位置が変わらず、注入時のプレイヤーとの距離が保たれる
        field._bullets = [  # pylint: disable=W0212
            Bullet(x + Bullet.WIDTH / 2, y + Bullet.HEIGHT / 2, 0) for x, y in positions
        ]
        field.process_frame()
        return field

    def _field_after_first_shot(self):
        """発射間隔ぶん process_frame() を進め、最初の1発が発射された直後
        （まだ移動していない）の Field を返す
        （TestBulletAdvancesStraightEveryFrame の同名ヘルパーと同型）"""
        field = Field()
        # モブの移動・追尾・命中は本テストの検証対象外のため除去する
        field._mobs = []  # pylint: disable=W0212
        for _ in range(Player.BULLET_SHOOT_INTERVAL):
            field.process_frame()
        return field

    def test_bullet_is_removed_exactly_at_range_in_every_direction(self):
        player_pos = self._expected_player_pos(1)
        # 方向ごとに「射程−1px（残存）」と「射程ちょうど（消滅）」の中心点
        # 差分の組を並べる。整数座標で距離を厳密に作れる差分は距離ごとに
        # 決まっている（35px は 3:4:5 の7倍、34px は 8:15:17 の2倍）ため、
        # 斜め方向の2点は厳密には同一角度上へ載らないが、いずれも軸から
        # 外れた方向であり「矩形ではなく距離で判定される」ことの検証には
        # 足りる。距離が射程と一致することはテストデータの前提で担保する。
        # 射程は表示領域の半分より短く、ここで挙げる位置はすべて表示領域の
        # 内側に収まるため、旧仕様（表示領域外での消滅）とは結果が異なる
        test_cases = [
            ("上（軸方向）", (0, -34), (0, -35)),
            ("下（軸方向）", (0, 34), (0, 35)),
            ("左（軸方向）", (-34, 0), (-35, 0)),
            ("右（軸方向）", (34, 0), (35, 0)),
            ("右上（斜め・縦寄り）", (16, -30), (21, -28)),
            ("左上（斜め・横寄り）", (-30, -16), (-28, -21)),
            ("右下（斜め・横寄り）", (30, 16), (28, 21)),
            ("左下（斜め・縦寄り）", (-16, 30), (-21, 28)),
        ]
        for name, kept_diff, removed_diff in test_cases:
            with self.subTest(name):
                # テストデータの前提: 中心点同士の距離が射程ちょうど／
                # 射程−1px であること（射程の値を変えた場合はここで検知され、
                # 厳密な距離を作れる差分の組へ取り直すことになる）
                self.assertEqual(Field.BULLET_RANGE, math.hypot(*removed_diff))
                self.assertEqual(Field.BULLET_RANGE - 1, math.hypot(*kept_diff))
                kept_pos = self._bullet_pos_at(player_pos, kept_diff)
                removed_pos = self._bullet_pos_at(player_pos, removed_diff)

                field = self._run_process_frame_with_bullets([removed_pos, kept_pos])

                self.assertEqual([kept_pos], field.bullet_states())

    def test_fired_bullet_is_removed_when_it_reaches_range(self):
        # 実際に発射された弾（注入ではなく発射・前進の経路）でも射程が働く
        # こと。弾は BULLET_SPEED、プレイヤーは同じ向き（真上）へ
        # PLAYER_SPEED で進むため、両者の距離は相対速度
        # (BULLET_SPEED − PLAYER_SPEED) で開いていく。
        # ただしプレイヤーの中心点は毎フレーム round() されるため、座標が
        # 半端になる奇数フレームでは観測される距離に 0.5px の丸め差が乗る。
        # 境界そのものは test_bullet_is_removed_exactly_at_range_in_every_
        # direction で 1px 単位に固定済みのため、ここでは丸め差の出ない
        # 偶数フレームで射程到達フレームの前後を挟み、消滅が起きることのみ
        # を見る
        relative_speed = Player.BULLET_SPEED - Field.PLAYER_SPEED
        frames_to_range = Field.BULLET_RANGE / relative_speed
        kept_frames = 2 * math.floor(frames_to_range / 2)
        removed_frames = 2 * math.ceil(frames_to_range / 2)
        # テストデータの前提: 挟んだ2つの偶数フレームでの相対距離が、
        # それぞれ射程未満／射程以上であること
        self.assertLess(relative_speed * kept_frames, Field.BULLET_RANGE)
        self.assertGreaterEqual(relative_speed * removed_frames, Field.BULLET_RANGE)
        test_cases = [
            ("射程内のフレーム", kept_frames, 1),
            ("射程へ到達した後のフレーム", removed_frames, 0),
        ]
        for name, frames, expected_count in test_cases:
            with self.subTest(name):
                field = self._field_after_first_shot()

                for _ in range(frames):
                    field.process_frame()

                self.assertEqual(expected_count, len(field.bullet_states()))


class TestMobDestroyedOnBulletHit(TestParent):
    """弾の矩形（登録座標 + 4x4）とモブの矩形（登録座標 + 8x8）が1ピクセル
    でも重なると、モブは process_frame() 後に mob_states() から、命中した
    弾も bullet_states() から取り除かれる（弾がモブを貫通しないことの保証）。
    辺が接するだけ（重なりなし）のモブ・無関係な弾は残ること。命中判定の
    境界は毎フレームの移動で自然に通過する条件のため、境界値を
    パラメタライズテストで仕様として固定する（_remove_outside_view() と
    同じ矩形重なりの規約）。残存モブの回転値は観点対象外のため位置のみを
    検証する"""

    def _run_process_frame_with_bullets_and_mobs(self, bullet_positions, mob_positions):
        """弾・モブ（いずれも登録座標・speed 0）を注入して process_frame()
        を1回呼ぶ（TestMobDespawnOutsideView・TestBulletDespawnOutOfRange の
        注入ヘルパーの合成。コンストラクタは中心点を受け取るため、登録座標
        から画像サイズの半分を足して変換する。速度 0 のため前進では位置が
        変わらず、重なり／非重なりの配置が固定される）"""
        field = Field()
        # 開始時の1匹は検証対象外のため、注入したモブのみへ置き換える
        field._mobs = [  # pylint: disable=W0212
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in mob_positions
        ]
        # 開始時に発射される1発は検証対象外のため、注入した弾のみへ置き換える
        field._bullets = [  # pylint: disable=W0212
            Bullet(x + Bullet.WIDTH / 2, y + Bullet.HEIGHT / 2, 0)
            for x, y in bullet_positions
        ]
        field.process_frame()
        return field

    def test_mob_is_removed_exactly_when_rect_overlaps_bullet(self):
        # 位置はすべて開始時の表示領域の明確な内側とし、領域外除去の判定と
        # 干渉させない（speed 0 のため1フレームでの移動もない）
        bullet_x, bullet_y = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y - 40)
        # 変化させない側の軸は弾とモブの中心を揃え、その軸では明確に重ねる
        aligned_x = bullet_x + Bullet.WIDTH // 2 - Mob.WIDTH // 2
        aligned_y = bullet_y + Bullet.HEIGHT // 2 - Mob.HEIGHT // 2
        # 各辺で「1ピクセル重なる（命中）」と「辺が接するだけ（非命中）」の
        # 境界値の組。左・上はモブ矩形の右辺・下辺が弾矩形に届くか、右・下は
        # モブ矩形の左辺・上辺が弾矩形に入るかの境界になる
        test_cases = [
            (
                "左辺",
                (bullet_x - Mob.WIDTH + 1, aligned_y),
                (bullet_x - Mob.WIDTH, aligned_y),
            ),
            (
                "右辺",
                (bullet_x + Bullet.WIDTH - 1, aligned_y),
                (bullet_x + Bullet.WIDTH, aligned_y),
            ),
            (
                "上辺",
                (aligned_x, bullet_y - Mob.HEIGHT + 1),
                (aligned_x, bullet_y - Mob.HEIGHT),
            ),
            (
                "下辺",
                (aligned_x, bullet_y + Bullet.HEIGHT - 1),
                (aligned_x, bullet_y + Bullet.HEIGHT),
            ),
        ]
        for name, hit_pos, kept_pos in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_bullets_and_mobs(
                    [(bullet_x, bullet_y)], [hit_pos, kept_pos]
                )
                self.assertEqual(
                    [kept_pos],
                    [(mob_x, mob_y) for mob_x, mob_y, _ in field.mob_states()],
                )

    def test_hitting_bullet_is_removed_and_missing_bullet_is_kept(self):
        # 弾は双方とも射程（Field.BULLET_RANGE）の明確な内側へ置き、射程に
        # よる消滅と干渉させない（命中による除去だけを観測するため。命中弾
        # まで射程外にすると、除去が命中によるものか射程によるものか判別
        # できなくなる。speed 0 のため1フレームでの移動もない）
        hit_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y - 20)
        # 命中弾からもモブからも明確に離れた（どのモブとも重ならない）弾
        kept_pos = (hit_pos[0] + 20, hit_pos[1])
        # モブは命中弾と中心を揃えて明確に重ねる
        mob_pos = (
            hit_pos[0] + Bullet.WIDTH // 2 - Mob.WIDTH // 2,
            hit_pos[1] + Bullet.HEIGHT // 2 - Mob.HEIGHT // 2,
        )

        field = self._run_process_frame_with_bullets_and_mobs(
            [hit_pos, kept_pos], [mob_pos]
        )

        self.assertEqual([kept_pos], field.bullet_states())


class TestDropSpawnOnMobDestroyed(TestParent):
    """モブが弾で撃破されると、その撃破位置に通常ドロップが生成され、
    process_frame() 後の drop_states() で観測できる。撃破されなかった
    モブからはドロップが生成されないこと。ドロップ
    （Drop.WIDTH/HEIGHT。モブ 8x8 とサイズが異なる）は撃破
    されたモブと画像中心が一致する位置に生成されるため、drop_states() が
    返すドロップの登録座標は「モブの登録座標をそのまま流用した値」では
    なく「モブの中心からドロップのサイズの半分を引いた値」を期待する。
    種別（通常/レア）の検証は TestRareDropSpawnByChance の観点のため、
    ここでは件数・位置のみを検証する"""

    def _run_process_frame_with_bullets_and_mobs(self, bullet_positions, mob_positions):
        """弾・モブ（いずれも登録座標・speed 0）を注入して process_frame()
        を1回呼ぶ（TestMobDestroyedOnBulletHit の注入ヘルパーと同型。
        速度 0 のため前進では位置が変わらず、重なり／非重なりの配置が
        固定される）"""
        field = Field()
        # 開始時の1匹は検証対象外のため、注入したモブのみへ置き換える
        field._mobs = [  # pylint: disable=W0212
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in mob_positions
        ]
        # 開始時に発射される1発は検証対象外のため、注入した弾のみへ置き換える
        field._bullets = [  # pylint: disable=W0212
            Bullet(x + Bullet.WIDTH / 2, y + Bullet.HEIGHT / 2, 0)
            for x, y in bullet_positions
        ]
        field.process_frame()
        return field

    def test_drop_spawns_at_destroyed_mob_position(self):
        # 位置はすべて開始時の表示領域の明確な内側とし、領域外除去の判定と
        # 干渉させない（speed 0 のため1フレームでの移動もない）
        bullet_pos = (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y - 40)
        # 撃破されるモブは弾と中心を揃えて明確に重ねる
        destroyed_pos = (
            bullet_pos[0] + Bullet.WIDTH // 2 - Mob.WIDTH // 2,
            bullet_pos[1] + Bullet.HEIGHT // 2 - Mob.HEIGHT // 2,
        )
        # 弾と明確に重ならない（撃破されない）モブ。ドロップが生成されない
        # ことの検証を兼ねる
        kept_pos = (destroyed_pos[0] + 40, destroyed_pos[1])

        field = self._run_process_frame_with_bullets_and_mobs(
            [bullet_pos], [destroyed_pos, kept_pos]
        )

        # ドロップの登録座標 = 撃破されたモブの中心（登録座標 + モブサイズの
        # 半分）− ドロップサイズの半分（画像中心を一致させる仕様）
        expected_drop_pos = (
            destroyed_pos[0] + Mob.WIDTH // 2 - Drop.WIDTH // 2,
            destroyed_pos[1] + Mob.HEIGHT // 2 - Drop.HEIGHT // 2,
        )
        self.assertEqual(
            [expected_drop_pos], [(x, y) for x, y, _ in field.drop_states()]
        )


class TestRareDropSpawnByChance(TestParent):
    """レア化確率 Field.RARE_DROP_RATE で、通常ドロップの代わりにレア
    ドロップが生成される。種別は drop_states() の各要素 (x, y, is_rare) の
    第3要素で観測する。レア化判定に使われる乱数（random.random、[0, 1) の
    一様乱数）を setUp の random.uniform と同様に patch で固定し、乱数値が
    確率を明確に下回れば全ドロップがレア、明確に上回れば全ドロップが通常に
    なることを決定的に検証する。RARE_DROP_RATE は変更予定がなくゲーム
    バランスに直結する定数のため、境界ちょうど（乱数値が確率と等しい場合）
    の挙動も実装の詳細とせず仕様として固定する: random() は [0, 1) を
    返すため、P(random() < rate) を厳密に rate とするには境界ちょうどを
    含まない（＝通常ドロップ）必要があり、境界を含めてしまう実装
    （<= 判定）だと発生確率が仕様値からずれる"""

    def _drop_states_with_rarity_random(self, rarity_random):
        """レア化判定の乱数を rarity_random に固定したうえで、弾・モブ
        （いずれも登録座標・speed 0）を中心を揃えて重ねた組を2組注入し、
        process_frame() を1回呼んで drop_states() を返す
        （TestDropSpawnOnMobDestroyed の注入ヘルパーと同型。2体撃破で
        「生成されるドロップすべてが乱数値どおりの種別になる」ことを
        観測する）"""
        field = Field()
        # 位置はすべて開始時の表示領域の明確な内側とし、領域外除去の判定と
        # 干渉させない（speed 0 のため1フレームでの移動もない）。2組は
        # 互いに明確に離し、弾とモブの組み合わせを1対1に保つ
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
        # 開始時の1匹・1発は検証対象外のため、注入したもののみへ置き換える
        field._mobs = [  # pylint: disable=W0212
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in mob_positions
        ]
        field._bullets = [  # pylint: disable=W0212
            Bullet(x + Bullet.WIDTH / 2, y + Bullet.HEIGHT / 2, 0)
            for x, y in bullet_positions
        ]
        with patch("src.main.random.random", return_value=rarity_random):
            field.process_frame()
        return field.drop_states()

    def test_drop_rarity_follows_rarity_random(self):
        test_cases = [
            (
                "確率を明確に下回る乱数値では全ドロップがレア",
                Field.RARE_DROP_RATE / 2,
                [True, True],
            ),
            (
                "確率を明確に上回る乱数値では全ドロップが通常",
                (Field.RARE_DROP_RATE + 1) / 2,
                [False, False],
            ),
            (
                "乱数値が確率とちょうど等しい場合は全ドロップが通常"
                "（P(random() < rate) を厳密に rate とする境界の仕様）",
                Field.RARE_DROP_RATE,
                [False, False],
            ),
        ]
        for name, rarity_random, expected_is_rare in test_cases:
            with self.subTest(name):
                drop_states = self._drop_states_with_rarity_random(rarity_random)
                # 2体撃破のドロップ数（件数の検証を兼ねる）と種別を検証する
                self.assertEqual(
                    expected_is_rare, [is_rare for _, _, is_rare in drop_states]
                )


class TestDropCollectedOnPlayerContact(TestParent):
    """プレイヤーの矩形（登録座標 + 8x8）とドロップの矩形（登録座標 +
    Drop.WIDTH/HEIGHT）が重なると、そのドロップは回収され、
    process_frame() 後の drop_states() から取り除かれる。プレイヤーから
    明確に離れた位置のドロップは残ること。種別（通常/レア）は回収判定の
    観点外（種別の検証は TestRareDropSpawnByChance の観点）のため、
    注入するドロップはすべて通常種別とし位置のみを検証する"""

    def _run_process_frame_with_drops(self, drop_positions):
        """ドロップ（登録座標・速度0・通常種別）を注入して process_frame()
        を1回呼ぶ（TestMobDestroyedOnBulletHit の注入ヘルパーと同型）。
        プレイヤーは開始時の画面中央から動かさない（開始時のモブは画面外に
        あり自動追尾で向きは変わらず、1フレームの前進量 Field.PLAYER_SPEED
        は 1 ピクセル未満のため、明確な重なり／非重なりの配置は覆らない）"""
        field = Field()
        field._drops = [  # pylint: disable=W0212
            Drop(x + Drop.WIDTH / 2, y + Drop.HEIGHT / 2, 0, False)
            for x, y in drop_positions
        ]
        field.process_frame()
        return field

    def test_drop_overlapping_player_is_collected_and_distant_drop_is_kept(self):
        # 回収されるドロップはプレイヤー（開始時は画面中央）と画像中心を
        # 揃えて明確に重ねる（4x4 の全体が 8x8 の内側に収まる）
        collected_pos = (
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X - Drop.WIDTH // 2,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y - Drop.HEIGHT // 2,
        )
        # プレイヤーと明確に重ならないドロップ。位置は表示領域の明確な
        # 内側とし、領域外消滅の判定（ID-011-5 の観点）と干渉させない
        kept_pos = (collected_pos[0] + 40, collected_pos[1])

        field = self._run_process_frame_with_drops([collected_pos, kept_pos])

        self.assertEqual([kept_pos], [(x, y) for x, y, _ in field.drop_states()])

    def test_drop_is_collected_exactly_when_rect_overlaps_player(self):
        # プレイヤー（登録座標 + 8x8、開始時は画面中央固定で不動）を基準に、
        # 各辺で「1ピクセル重なる（回収）」と「辺が接するだけ（残存）」の
        # 境界値の組を検証する（TestMobDestroyedOnBulletHit の
        # test_mob_is_removed_exactly_when_rect_overlaps_bullet と同型。
        # そちらは弾を基準にモブの位置を動かすが、ここではプレイヤーを
        # 基準にドロップの位置を動かす）
        player_x, player_y = self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y
        # 変化させない側の軸はプレイヤーとドロップの中心を揃え、その軸では
        # 明確に重ねる
        aligned_x = player_x + Player.WIDTH // 2 - Drop.WIDTH // 2
        aligned_y = player_y + Player.HEIGHT // 2 - Drop.HEIGHT // 2
        # 各辺で「1ピクセル重なる（回収）」と「辺が接するだけ（非回収）」の
        # 境界値の組。左・上はドロップ矩形の右辺・下辺がプレイヤー矩形に
        # 届くか、右・下はドロップ矩形の左辺・上辺がプレイヤー矩形に入るかの
        # 境界になる
        test_cases = [
            (
                "左辺",
                (player_x - Drop.WIDTH + 1, aligned_y),
                (player_x - Drop.WIDTH, aligned_y),
            ),
            (
                "右辺",
                (player_x + Player.WIDTH - 1, aligned_y),
                (player_x + Player.WIDTH, aligned_y),
            ),
            (
                "上辺",
                (aligned_x, player_y - Drop.HEIGHT + 1),
                (aligned_x, player_y - Drop.HEIGHT),
            ),
            (
                "下辺",
                (aligned_x, player_y + Player.HEIGHT - 1),
                (aligned_x, player_y + Player.HEIGHT),
            ),
        ]
        for name, hit_pos, kept_pos in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_drops([hit_pos, kept_pos])
                self.assertEqual(
                    [kept_pos], [(x, y) for x, y, _ in field.drop_states()]
                )


class TestDropDespawnOutsideView(TestParent):
    """ドロップの消滅領域（表示領域の縦の長さ SCREEN_HEIGHT ×
    Field.DROP_DESPAWN_VIEW_SCALE を一辺とする、表示領域と中心を揃えた
    正方形）から明確に外へ出たドロップが process_frame() 後の
    drop_states() から取り除かれ、明確に領域内のドロップは残ること。
    消滅領域は表示領域より広いため、表示領域の明確な外側であっても
    消滅領域の明確な内側にあるドロップは残る（表示領域ちょうどで消滅させる
    誤実装との判別を兼ねる本クラスの主眼）。倍率はプレイ体験を見て調整する
    予定の定数のため、境界ちょうどの位置は使わず、具体的な判定境界も
    仕様として固定しない（消滅位置がプレイヤーの目に直接見えるため境界を
    固定する射程〔TestBulletDespawnOutOfRange〕とは、この点で方針が異なる）。
    種別（通常/レア）は消滅判定の観点外のため、注入するドロップはすべて
    通常種別とし位置のみを検証する"""

    # 消滅領域（正方形）の一辺 = 表示領域の縦の長さ × 倍率
    DESPAWN_SIZE = Field.SCREEN_HEIGHT * Field.DROP_DESPAWN_VIEW_SCALE
    # 消滅領域が表示領域の各辺から外側へ広がる余白幅（正方形と表示領域の
    # 中心を揃えるため、辺ごとの余白は「(一辺 − 画面サイズ) の半分」になる。
    # 表示領域が縦長のため、横の余白の方が広い）
    DESPAWN_MARGIN_X = (DESPAWN_SIZE - Field.SCREEN_WIDTH) // 2
    DESPAWN_MARGIN_Y = (DESPAWN_SIZE - Field.SCREEN_HEIGHT) // 2

    def _expected_player_pos(self, frames):
        return (
            self.INITIAL_PLAYER_X,
            round(self.INITIAL_PLAYER_Y - frames * Field.PLAYER_SPEED),
        )

    def _run_process_frame_with_drops(self, drop_positions):
        """ドロップ（登録座標・速度0・通常種別）を注入して process_frame()
        を1回呼ぶ（TestDropCollectedOnPlayerContact の注入ヘルパーと同型）。
        注入位置はいずれもプレイヤー（開始時の画面中央から動かさない）と
        明確に重ならない位置とし、回収判定（ID-011-2 の観点）と干渉させない"""
        field = Field()
        field._drops = [  # pylint: disable=W0212
            Drop(x + Drop.WIDTH / 2, y + Drop.HEIGHT / 2, 0, False)
            for x, y in drop_positions
        ]
        field.process_frame()
        return field

    def test_drop_clearly_outside_despawn_area_is_removed_and_inside_is_kept(self):
        player_x, player_y = self._expected_player_pos(1)
        camera_x = player_x - self.INITIAL_PLAYER_X
        camera_y = player_y - self.INITIAL_PLAYER_Y
        # 表示領域の明確な内側の残存ドロップ（プレイヤーからは明確に離す）
        inside_view_pos = (player_x + 40, player_y)
        # 各方向で「消滅領域の明確な外（消滅領域の辺からさらに画面1個分
        # 外側）」と「表示領域の明確な外だが消滅領域の明確な内（余白幅の
        # 半分だけ外側）」の組を検証する
        test_cases = [
            (
                "上方向",
                (player_x, camera_y - self.DESPAWN_MARGIN_Y - Field.SCREEN_HEIGHT),
                (player_x, camera_y - self.DESPAWN_MARGIN_Y // 2),
            ),
            (
                "下方向",
                (
                    player_x,
                    camera_y
                    + Field.SCREEN_HEIGHT
                    + self.DESPAWN_MARGIN_Y
                    + Field.SCREEN_HEIGHT,
                ),
                (
                    player_x,
                    camera_y + Field.SCREEN_HEIGHT + self.DESPAWN_MARGIN_Y // 2,
                ),
            ),
            (
                "左方向",
                (camera_x - self.DESPAWN_MARGIN_X - Field.SCREEN_WIDTH, player_y),
                (camera_x - self.DESPAWN_MARGIN_X // 2, player_y),
            ),
            (
                "右方向",
                (
                    camera_x
                    + Field.SCREEN_WIDTH
                    + self.DESPAWN_MARGIN_X
                    + Field.SCREEN_WIDTH,
                    player_y,
                ),
                (
                    camera_x + Field.SCREEN_WIDTH + self.DESPAWN_MARGIN_X // 2,
                    player_y,
                ),
            ),
        ]
        for name, outside_pos, inside_margin_pos in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_drops(
                    [outside_pos, inside_margin_pos, inside_view_pos]
                )
                self.assertEqual(
                    [inside_margin_pos, inside_view_pos],
                    [(x, y) for x, y, _ in field.drop_states()],
                )


class DropAttractionTestParent(TestParent):
    """ドロップの引き寄せ（requirements.md §3.4「プレイヤーへの引き寄せ」）を
    検証するテストクラスの共通土台。

    引き寄せ中であることはドロップ自身の**速度**で表される。ドロップは静止
    （速度0）した状態で生成され、引き寄せの開始時に Field から速度を与えられ、
    以後は移動モード・プレイヤーとの距離によらずプレイヤーを追い続ける
    （ユーザー決定 2026-07-30）。そのためテストが注入するドロップはすべて
    静止した状態で作り、動き出すかどうかは Field の判定に委ねる。

    観測の組み立て:
    - 引き寄せ範囲はプレイヤーの成長レベル（§3.5 の通常ドロップによる成長
      レベル）に応じて広がり、レベル n では 12 + 4×n px になる
      （requirements.md §3.4 の表）。テストは実装側の値を参照せず、この
      仕様の計算式（_attract_range()）で範囲を組み立てる
    - 累計取得数を操作しないテストの Player はレベル0のため、範囲は
      _attract_range(0) = 12px（ATTRACT_RANGE）になる。レベルに応じて
      広がること自体は TestDropAttractRangeGrowsWithPlayerLevel の関心
    - 引き寄せの判定・移動はそのフレームの前進後のプレイヤー中心を基準に
      行われる。プレイヤーが動くと前進 0.5px 分の丸め（round(x.5) の偶数
      丸め）が判定距離へ方向ごとに異なる形で混ざり、範囲を 1px 単位で
      固定できなくなるため、引き寄せの有無・移動量を観測するテストでは
      プレイヤーを動かさない（_field_with_stationary_player）"""

    # 引き寄せ速度（要件「プレイヤーの移動速度の2倍」を計算式で表す）
    ATTRACT_SPEED = Field.PLAYER_SPEED * 2
    # 引き寄せを開始する範囲（プレイヤー中心とドロップ中心の距離）のうち、
    # レベル0（累計取得数0＝生成直後の Player）の範囲
    ATTRACT_RANGE = 12
    # 引き寄せの有無を観測するドロップの距離（レベル0の範囲の境界より内側に
    # 余裕を持たせる）
    IN_RANGE_DISTANCE = 10

    @classmethod
    def _attract_range(cls, level):
        """レベル level の引き寄せ範囲（requirements.md §3.4 の表）。レベル0の
        12px から、レベルが1上がるごとに4px 広がる。上限（レベル8の44px）は
        レベルそのものが0〜8へキャップされることで決まるため、ここでは
        上限を扱わず一次式のみで表す"""
        return cls.ATTRACT_RANGE + 4 * level

    def _player_center(self):
        """プレイヤー（開始位置＝画面中央）の画像中心点のワールド座標"""
        return (
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y,
        )

    def _field_without_mobs(self, base_mode=MoveMode.COLLECT):
        """基底モードを base_mode にし、モブを除いた Field を返す（モブの
        追尾・接触・撃破は引き寄せの観測へ混ぜないため取り除く。開始時の1匹を
        除けば次の出現は MOB_SPAWN_INTERVAL フレーム後で、本クラス群の観測
        期間中には起きない）"""
        field = Field()
        field._mobs = []  # pylint: disable=W0212
        if base_mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        return field

    def _field_with_stationary_player(self, base_mode=MoveMode.COLLECT):
        """プレイヤーが開始位置（画面中央）から動かない Field を返す
        （TestMobSpawnGrowsOnRareDropCollect と同じ抑止方法）。注入時に置いた
        距離がそのまま引き寄せの判定距離になり、観測される位置の変化も
        ドロップ自身の移動だけになる"""
        field = self._field_without_mobs(base_mode)
        field._player._speed = 0  # pylint: disable=W0212
        return field

    def _drop_at(self, diff):
        """プレイヤー中心から差分 diff だけ離れた位置に画像中心を置く、静止
        した（引き寄せをまだ開始していない）通常種別のドロップを返す"""
        center_x, center_y = self._player_center()
        return Drop(center_x + diff[0], center_y + diff[1], 0, False)

    def _attracted_state(self, diff, frames):
        """プレイヤー中心から差分 diff に置いたドロップが、プレイヤー中心へ
        向かって frames フレーム分（frames × ATTRACT_SPEED）進んだ後の
        drop_states() 上の期待値。進行方向は差分 diff の単位ベクトルで一定
        （プレイヤーへ向かって直進するため、プレイヤーが動かない限り毎
        フレーム同じ向きになる）のため、期待値は TestParent._expected_pos()
        と同じ「開始座標 + フレーム数 × 速度 × 単位ベクトル」で求まる"""
        center_x, center_y = self._player_center()
        dist = math.hypot(*diff)
        remaining = dist - frames * self.ATTRACT_SPEED
        return (
            round(center_x + diff[0] * remaining / dist) - Drop.WIDTH // 2,
            round(center_y + diff[1] * remaining / dist) - Drop.HEIGHT // 2,
            False,
        )

    def _kept_state(self, diff):
        """引き寄せを開始せず注入位置から動かないドロップの drop_states() 上の
        期待値"""
        return self._attracted_state(diff, 0)

    def _center_distance(self, player_state, drop_state):
        """player_state() とdrop_states() の要素（いずれも登録座標）から、
        プレイヤーとドロップの画像中心点同士の距離を求める"""
        player_x, player_y, _ = player_state
        drop_x, drop_y, _ = drop_state
        return math.hypot(
            drop_x + Drop.WIDTH // 2 - (player_x + self.PLAYER_CENTER_OFFSET_X),
            drop_y + Drop.HEIGHT // 2 - (player_y + self.PLAYER_CENTER_OFFSET_Y),
        )

    def _assert_player_stayed(self, field):
        """プレイヤーが開始位置から動いていないこと（観測されたドロップの
        位置の変化がドロップ自身の移動だけであることの前提ガード）"""
        player_x, player_y, _ = field.player_state()
        self.assertEqual(
            (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), (player_x, player_y)
        )

    def _assert_observed_before_collect(self, distance, frames):
        """観測の最後まで回収（矩形の重なり）へ至らないことの前提ガード。
        軸方向では中心間の距離が (Player.WIDTH + Drop.WIDTH) // 2 未満に
        なった時点で回収される"""
        self.assertGreaterEqual(
            distance - frames * self.ATTRACT_SPEED,
            (Player.WIDTH + Drop.WIDTH) // 2,
        )


class TestDropAttractedToPlayerInRange(DropAttractionTestParent):
    """自動収集モード中、プレイヤー中心から一定範囲内へ入ったドロップが、
    プレイヤーへ向かってプレイヤーの移動速度の2倍で移動を始めること
    （ID-024 サイクル1 Red、振る舞いテスト。requirements.md §3.4）。

    仕様:
    - プレイヤー中心とドロップ中心の距離が引き寄せ範囲**以下**になった
      ドロップは、毎フレーム「プレイヤーの移動速度の2倍」だけプレイヤー中心へ
      向かって進む。範囲より遠いドロップは動かない。境界を範囲内へ含めるのは、
      ドロップが動き出す距離がプレイヤーの目に直接見えるため（射程の境界を
      仕様として固定した TestBulletDespawnOutOfRange と同じ理由。向きは
      「範囲の内側／外側」の直感に合わせ、射程とは逆になる）
    - 範囲の内外は中心点同士の距離（math.hypot）で決まり、方向によって
      変わらない（縦横それぞれの差で判定する矩形ではない）
    - 引き寄せは回収そのものを行わない。回収は従来どおりプレイヤーとの矩形の
      重なりで起きる（TestDropCollectedOnPlayerContact の観点）ため、本クラス
      の観測はいずれも回収へ至らない距離・フレーム数に留める

    本クラスのスコープ:
    - テストはすべて自動収集モードで書く。引き寄せを**開始しない**モード
      （自動戦闘モード・目的地移動モード）は
      TestDropAttractionStartsOnlyInCollectMode の関心、**開始後の継続**は
      TestDropAttractionContinuesAfterStart の関心
    - 引き寄せ速度は Field が開始時にドロップへ与える。撃破で生成された
      ドロップも同じ経路で引き寄せられることは
      test_drop_spawned_on_mob_destroyed_is_attracted で固定する"""

    # 移動量の観測フレーム数（1フレーム目の移動と、フレームごとに積み上がる
    # ことの双方を見る）
    OBSERVE_FRAMES = (1, 3)
    # 範囲の内外を観測するテストのフレーム数（引き寄せが起きた場合の移動が
    # 明確に観測でき、かつ回収へ至らないフレーム数）
    ATTRACT_FRAMES = 3
    # 軸方向（境界ちょうどの距離を整数座標で作れる方向）の単位差分
    AXIS_DIRECTIONS = (
        ("上", (0, -1)),
        ("下", (0, 1)),
        ("左", (-1, 0)),
        ("右", (1, 0)),
    )
    # (象限, 範囲内の斜め差分, 範囲外だが縦横の差はいずれも範囲以内の斜め差分)。
    # 範囲内の側は縦横の差の最大（11）が範囲外の側（9）より大きく、矩形
    # （縦横それぞれの差）で判定する実装では内外が逆になる組にしている
    DIAGONAL_CASES = (
        ("右下", (4, 11), (9, 9)),
        ("左下", (-11, 4), (-9, 9)),
        ("右上", (11, -4), (9, -9)),
        ("左上", (-4, -11), (-9, -9)),
    )
    # プレイヤーが逃げる向きを作る囮ドロップの差分（プレイヤーの真上）。
    # 自動収集モードのプレイヤーは最も近いドロップを追尾するため、観測対象
    # より近いドロップを反対側へ置くことがプレイヤーを遠ざける唯一の方法に
    # なる（目的地移動・ヒットバックによる遠ざかりはサイクル2 の関心）
    FLEE_BAIT_DIFF = (0, -10)
    # 逃げるプレイヤーが追われる側（プレイヤーの真下）の観測対象の差分
    FLEE_TARGET_DIFF = (0, 11)
    # 囮が回収されてプレイヤーが向きを変える前に観測を終えるフレーム数
    FLEE_FRAMES = 2
    # 撃破位置に生成されたドロップを引き寄せの対象にするモブ中心の差分
    SPAWN_MOB_DIFF = (DropAttractionTestParent.IN_RANGE_DISTANCE, 0)

    def test_drop_in_range_moves_toward_player_at_double_player_speed(self):
        self._assert_observed_before_collect(
            self.IN_RANGE_DISTANCE, max(self.OBSERVE_FRAMES)
        )
        for name, unit in self.AXIS_DIRECTIONS:
            diff = (
                unit[0] * self.IN_RANGE_DISTANCE,
                unit[1] * self.IN_RANGE_DISTANCE,
            )
            for frames in self.OBSERVE_FRAMES:
                with self.subTest(direction=name, frames=frames):
                    field = self._field_with_stationary_player()
                    field._drops = [self._drop_at(diff)]  # pylint: disable=W0212

                    for _ in range(frames):
                        field.process_frame()

                    self.assertEqual(
                        [self._attracted_state(diff, frames)], field.drop_states()
                    )
                    self._assert_player_stayed(field)

    def test_drop_starts_moving_exactly_within_range_in_axis_directions(self):
        # 境界ちょうど（動き出す）と境界の1px 外（動かない）の組を軸方向ごとに
        # 検証する。距離が ATTRACT_RANGE ちょうどになる整数座標は軸方向にしか
        # 作れない（斜めで距離12の整数点は存在しない）ため、境界の検証は軸方向
        # に限り、方向によらないことは
        # test_drop_in_range_is_attracted_by_distance_not_by_axis_difference
        # で示す
        self._assert_observed_before_collect(self.ATTRACT_RANGE, self.ATTRACT_FRAMES)
        for name, unit in self.AXIS_DIRECTIONS:
            with self.subTest(name):
                in_range_diff = (
                    unit[0] * self.ATTRACT_RANGE,
                    unit[1] * self.ATTRACT_RANGE,
                )
                out_of_range_diff = (
                    unit[0] * (self.ATTRACT_RANGE + 1),
                    unit[1] * (self.ATTRACT_RANGE + 1),
                )
                field = self._field_with_stationary_player()
                field._drops = [  # pylint: disable=W0212
                    self._drop_at(in_range_diff),
                    self._drop_at(out_of_range_diff),
                ]

                for _ in range(self.ATTRACT_FRAMES):
                    field.process_frame()

                self.assertEqual(
                    [
                        self._attracted_state(in_range_diff, self.ATTRACT_FRAMES),
                        self._kept_state(out_of_range_diff),
                    ],
                    field.drop_states(),
                )
                self._assert_player_stayed(field)

    def test_drop_in_range_is_attracted_by_distance_not_by_axis_difference(self):
        for name, in_range_diff, out_of_range_diff in self.DIAGONAL_CASES:
            with self.subTest(name):
                # テストデータの前提: 距離では範囲内／範囲外である一方、縦横
                # それぞれの差では範囲内の側の方が大きい（矩形で判定する実装
                # では内外が逆になり、どちらのケースも失敗する）
                self.assertLessEqual(math.hypot(*in_range_diff), self.ATTRACT_RANGE)
                self.assertGreater(math.hypot(*out_of_range_diff), self.ATTRACT_RANGE)
                self.assertGreater(
                    max(abs(diff) for diff in in_range_diff),
                    max(abs(diff) for diff in out_of_range_diff),
                )
                field = self._field_with_stationary_player()
                field._drops = [  # pylint: disable=W0212
                    self._drop_at(in_range_diff),
                    self._drop_at(out_of_range_diff),
                ]

                for _ in range(self.ATTRACT_FRAMES):
                    field.process_frame()

                self.assertEqual(
                    [
                        self._attracted_state(in_range_diff, self.ATTRACT_FRAMES),
                        self._kept_state(out_of_range_diff),
                    ],
                    field.drop_states(),
                )
                self._assert_player_stayed(field)

    def test_drop_closes_gap_while_player_moves_away(self):
        # 要件の狙い（ドロップの進行方向と同じ向きへプレイヤーが移動しても
        # 追いつける）を、プレイヤーの真上に置いた囮ドロップで作る。プレイヤー
        # は囮を追尾して真上へ進み続け、真下の観測対象からは遠ざかる。速度が
        # プレイヤーの2倍のため、観測対象は遠ざかるプレイヤーへ相対
        # PLAYER_SPEED で近づく
        bait_distance = math.hypot(*self.FLEE_BAIT_DIFF)
        target_distance = math.hypot(*self.FLEE_TARGET_DIFF)
        # テストデータの前提: 囮の方が近い（プレイヤーが囮の方向へ向かう）／
        # 観測対象は引き寄せ範囲の内側にある
        self.assertLess(bait_distance, target_distance)
        self.assertLessEqual(target_distance, self.ATTRACT_RANGE)
        field = self._field_without_mobs()
        field._drops = [  # pylint: disable=W0212
            self._drop_at(self.FLEE_BAIT_DIFF),
            self._drop_at(self.FLEE_TARGET_DIFF),
        ]

        for _ in range(self.FLEE_FRAMES):
            field.process_frame()

        # プレイヤーは観測期間を通じて囮の方向（真上＝観測対象の進行方向と
        # 同じ向き）へ進み続けた
        player_x, player_y, _ = field.player_state()
        self.assertEqual(
            self._expected_pos(
                (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                (0, -1),
                self.FLEE_FRAMES,
            ),
            (player_x, player_y),
        )
        # 双方のドロップが、プレイヤーの移動によらず毎フレーム
        # ATTRACT_SPEED だけプレイヤーへ近づいた
        self.assertEqual(
            [
                self._attracted_state(self.FLEE_BAIT_DIFF, self.FLEE_FRAMES),
                self._attracted_state(self.FLEE_TARGET_DIFF, self.FLEE_FRAMES),
            ],
            field.drop_states(),
        )
        # 遠ざかるプレイヤーとの中心間距離が縮んでいる（追いつける）
        self.assertLess(
            self._center_distance(field.player_state(), field.drop_states()[1]),
            target_distance,
        )

    def test_drop_spawned_on_mob_destroyed_is_attracted(self):
        # 撃破で生成されたドロップも引き寄せられること（引き寄せ速度が
        # テストの注入時ではなく実装側の生成〔Field._spawn_drop()〕でも
        # 渡されていることの固定）。処理順（ドロップ生成 → 引き寄せ →
        # 回収）により、生成されたフレームのうちに1フレーム分だけ近づく
        center_x, center_y = self._player_center()
        mob_center = (
            center_x + self.SPAWN_MOB_DIFF[0],
            center_y + self.SPAWN_MOB_DIFF[1],
        )
        # テストデータの前提: モブの矩形はプレイヤーの矩形と重ならない
        # （接触ダメージ・ヒットバックが観測へ混ざらない）
        self.assertGreaterEqual(
            math.hypot(*self.SPAWN_MOB_DIFF), (Player.WIDTH + Mob.WIDTH) // 2
        )
        field = self._field_with_stationary_player()
        # 速度0のモブと、それに中心を揃えた速度0の弾で、そのフレームに撃破する
        field._mobs = [Mob(mob_center[0], mob_center[1], 0)]  # pylint: disable=W0212
        field._bullets = [  # pylint: disable=W0212
            Bullet(mob_center[0], mob_center[1], 0)
        ]

        # レア化判定の乱数を固定し、生成されるドロップを通常種別にする
        # （種別は本クラスの観点外。TestRareDropSpawnByChance と同じ固定方法）
        with patch("src.main.random.random", return_value=1.0):
            field.process_frame()

        self.assertEqual(
            [self._attracted_state(self.SPAWN_MOB_DIFF, 1)], field.drop_states()
        )
        self._assert_player_stayed(field)


class TestDropAttractionStartsOnlyInCollectMode(DropAttractionTestParent):
    """引き寄せを開始するのは自動収集モード中のみで、自動戦闘モード・目的地
    移動モード中は範囲内のドロップでも新たに引き寄せを開始しないこと
    （ID-024 サイクル2 Red、振る舞いテスト。requirements.md §3.4）。

    判定は実効モード（Field.player_move_mode の3値）で行う。基底モード
    （Player.move_mode の2値）が自動収集モードでも目的地移動中は開始しない
    ため、基底モードで判定する実装ミスは「目的地移動モード（自動収集起点）」の
    ケースでのみ検出できる。

    自動収集モードのケースは、同じ配置で引き寄せが実際に開始することを示す
    対照として並べる（他のケースが「配置が範囲外だった」等の理由で通ることを
    防ぐ。TestCollectModeSuppressesMobTracking と同型）"""

    # 引き寄せ範囲の内側に置くドロップの差分（プレイヤーの右）
    DROP_DIFF = (DropAttractionTestParent.IN_RANGE_DISTANCE, 0)
    # クリック（目的地）位置のプレイヤー中心からの差分。到着による目的地の
    # 解除（Player.DESTINATION_ARRIVAL_DISTANCE）が起きない距離へ置く
    DESTINATION_DIFF = (0, -50)
    FRAMES = 3
    # (ケース名, 基底モード, 目的地移動へ入るか, 実効モード, 引き寄せを開始するか)
    MODE_CASES = (
        ("自動戦闘モード", MoveMode.ATTACK, False, MoveMode.ATTACK, False),
        (
            "目的地移動モード（自動戦闘起点）",
            MoveMode.ATTACK,
            True,
            MoveMode.DESTINATION,
            False,
        ),
        (
            "目的地移動モード（自動収集起点）",
            MoveMode.COLLECT,
            True,
            MoveMode.DESTINATION,
            False,
        ),
        ("自動収集モード（対照）", MoveMode.COLLECT, False, MoveMode.COLLECT, True),
    )

    def test_attraction_starts_only_in_collect_mode(self):
        self._assert_observed_before_collect(self.IN_RANGE_DISTANCE, self.FRAMES)
        for name, base_mode, to_destination, mode, starts in self.MODE_CASES:
            with self.subTest(name):
                field = self._field_with_stationary_player(base_mode)
                if to_destination:
                    self._click_at(
                        field,
                        (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                        self.DESTINATION_DIFF,
                    )
                # 実効モードの前提ガード（目的地移動のケースは基底モードでは
                # なく目的地の有無から導出された値になっていること）
                self.assertEqual(mode, field.player_move_mode)
                field._drops = [self._drop_at(self.DROP_DIFF)]  # pylint: disable=W0212

                for _ in range(self.FRAMES):
                    field.process_frame()

                expected = (
                    self._attracted_state(self.DROP_DIFF, self.FRAMES)
                    if starts
                    else self._kept_state(self.DROP_DIFF)
                )
                self.assertEqual([expected], field.drop_states())
                self._assert_player_stayed(field)


class TestDropAttractionContinuesAfterStart(DropAttractionTestParent):
    """一度引き寄せを開始したドロップは、以降の移動モード・プレイヤーとの距離に
    かかわらずプレイヤーへ向かって移動し続け、回収されるまで追い続けること
    （ID-024 サイクル2 Red、振る舞いテスト。requirements.md §3.4）。

    モードの切り替えでドロップが動いたり止まったりしないようにするための
    要件で、引き寄せ中であることをドロップ自身の状態（速度）として持ち、以後は
    モードも範囲も参照しない実装の裏返しになる。

    「範囲の外へ離れても継続する」ことは通常の移動では観測できない。ドロップは
    プレイヤーの2倍の速度で近づくため、プレイヤーがどの方向へ動いても中心間の
    距離は縮む一方である。距離が広がるのはヒットバック（HITBACK_DISTANCE を
    HITBACK_FRAMES で等分＝プレイヤーの移動より速い）の間だけのため、その
    ケースはモブ接触で作る。モブ接触は自動戦闘モードへの復帰も同時に起こす
    ため、モードの切り替えだけによる継続は
    test_attracted_drop_keeps_moving_after_move_mode_changes で分けて扱う"""

    # 引き寄せ範囲の内側に置くドロップの差分（プレイヤーの右）
    DROP_DIFF = (DropAttractionTestParent.IN_RANGE_DISTANCE, 0)
    # 引き寄せを開始させるフレーム数と、モードを切り替えた後の観測フレーム数
    START_FRAMES = 1
    POST_SWITCH_FRAMES = 2
    DESTINATION_DIFF = (0, -50)
    # ヒットバックでプレイヤーをドロップから引き離すために接触させるモブの
    # 差分。ドロップと同じ側（真下）へ置くことで、ヒットバック（接触モブと
    # 反対方向）がドロップから遠ざかる向きになる。矩形が重なる距離のため
    # 注入した次のフレームで接触が成立する
    CONTACT_MOB_DIFF = (0, 4)
    # 範囲の外へ取り残されたドロップが回収されるまでの観測フレーム数
    CHASE_FRAMES = 9

    def test_attracted_drop_keeps_moving_after_move_mode_changes(self):
        total_frames = self.START_FRAMES + self.POST_SWITCH_FRAMES
        self._assert_observed_before_collect(self.IN_RANGE_DISTANCE, total_frames)
        test_cases = (
            ("自動戦闘モードへ切り替え", False, MoveMode.ATTACK),
            ("目的地移動モードへ入る", True, MoveMode.DESTINATION),
        )
        for name, to_destination, mode in test_cases:
            with self.subTest(name):
                field = self._field_with_stationary_player()
                field._drops = [self._drop_at(self.DROP_DIFF)]  # pylint: disable=W0212
                for _ in range(self.START_FRAMES):
                    field.process_frame()
                # 引き寄せが開始したことのガード
                self.assertEqual(
                    [self._attracted_state(self.DROP_DIFF, self.START_FRAMES)],
                    field.drop_states(),
                )
                if to_destination:
                    self._click_at(
                        field,
                        (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y),
                        self.DESTINATION_DIFF,
                    )
                else:
                    field.toggle_player_move_mode()
                self.assertEqual(mode, field.player_move_mode)

                for _ in range(self.POST_SWITCH_FRAMES):
                    field.process_frame()

                # 切り替え後も止まらず、通算フレーム数ぶん進み続けている
                self.assertEqual(
                    [self._attracted_state(self.DROP_DIFF, total_frames)],
                    field.drop_states(),
                )
                self._assert_player_stayed(field)

    def test_attracted_drop_chases_player_out_of_range_until_collected(self):
        # 引き寄せ範囲の内側（境界の1px 内）のドロップで引き寄せを開始する
        drop_diff = (0, self.ATTRACT_RANGE - 1)
        center_x, center_y = self._player_center()
        field = self._field_with_stationary_player()
        field._drops = [self._drop_at(drop_diff)]  # pylint: disable=W0212

        field.process_frame()

        # 引き寄せが開始したことのガード
        self.assertEqual([self._attracted_state(drop_diff, 1)], field.drop_states())
        # ドロップと同じ側のモブへ接触させ、ヒットバックでドロップから引き離す
        # （プレイヤーは速度0のため、ヒットバック以外では動かない）
        field._mobs = [  # pylint: disable=W0212
            Mob(
                center_x + self.CONTACT_MOB_DIFF[0],
                center_y + self.CONTACT_MOB_DIFF[1],
                0,
            )
        ]

        for _ in range(Player.HITBACK_FRAMES):
            field.process_frame()

        # ヒットバックの結果、中心間の距離が引き寄せ範囲を超えた（範囲を毎
        # フレーム再評価する実装ではここでドロップの移動が止まる）
        distance = self._center_distance(field.player_state(), field.drop_states()[0])
        self.assertGreater(distance, self.ATTRACT_RANGE)
        # テストデータの前提: 残りの観測フレーム数で回収の成立距離へ達する
        self.assertLess(
            distance - self.CHASE_FRAMES * self.ATTRACT_SPEED,
            (Player.HEIGHT + Drop.HEIGHT) // 2,
        )

        for _ in range(self.CHASE_FRAMES):
            field.process_frame()

        # 範囲の外へ取り残されても追い続け、回収された
        self.assertEqual([], field.drop_states())
        self.assertEqual(1, field.normal_drop_count)


class TestDropAttractRangeGrowsWithPlayerLevel(DropAttractionTestParent):
    """引き寄せ範囲が、プレイヤーの成長レベル（§3.5 の通常ドロップによる成長
    レベル）に応じて広がること（ID-025 サイクル1 Red、振る舞いテスト。
    requirements.md §3.4）。

    仕様: レベル n の引き寄せ範囲は 12 + 4×n px（レベル0=12px、レベルが1
    上がるごとに4px 広がり、上限のレベル8で44px）。境界の扱いは
    TestDropAttractedToPlayerInRange と同じで、距離が範囲**以下**であれば
    引き寄せを開始する。

    観測の組み立て:
    - レベルは累計取得数（しきい値の系列 10×(2^level−1)）から作る。
      レベルそのものを注入する経路は設けず、プレイヤーが実際に通常ドロップを
      集めた状態を再現する
    - レベル軸（0・2・8）と範囲の内外の軸（境界ちょうど／境界の1px 外）を
      test_cases 一覧へ展開する。レベル2・8 の境界（20px・44px）はいずれも
      レベル0の範囲（12px）の外にあるため、範囲がレベルに連動しない実装では
      これらのケースが「引き寄せを開始しない」となって失敗する
    - 範囲の内外が方向によらないこと（中心間の距離で決まること）は
      TestDropAttractedToPlayerInRange の関心のため、ここでは境界ちょうどの
      距離を整数座標で作れる軸方向（右）のみで観測する"""

    # 観測する軸方向の単位差分（右）
    DIRECTION = (1, 0)
    # 引き寄せが起きた場合の移動が明確に観測でき、かつ回収へ至らない
    # フレーム数（TestDropAttractedToPlayerInRange と同じ）
    ATTRACT_FRAMES = 3

    @staticmethod
    def _threshold(level):
        # 累計しきい値 = 10 x (2^level - 1)（レベル level に達するために
        # 必要な累計取得数。増分方式のしきい値を累計値へ読み替えた式）
        return 10 * (2**level - 1)

    def _field_with_player_level(self, level):
        """プレイヤーが動かず、通常ドロップの累計取得数が level のしきい値
        ちょうどに達した（＝レベル level の）Field を返す"""
        field = self._field_with_stationary_player()
        field._player._normal_drop_count = self._threshold(  # pylint: disable=W0212
            level
        )
        return field

    def test_attract_range_grows_with_player_level(self):
        test_cases = [
            # (名前, レベル, プレイヤー中心からの距離, 引き寄せを開始するか)
            ("レベル0: 境界(12px)ちょうど", 0, self._attract_range(0), True),
            ("レベル0: 境界の1px 外(13px)", 0, self._attract_range(0) + 1, False),
            # レベル0の範囲(12px)の外にあるドロップが、レベル2では境界
            # (20px)の内側になり引き寄せを開始する
            ("レベル2: 境界(20px)ちょうど", 2, self._attract_range(2), True),
            ("レベル2: 境界の1px 外(21px)", 2, self._attract_range(2) + 1, False),
            # 成長の上限（レベル8）でも同じ式（12 + 4×8 = 44px）に従う
            ("レベル8: 境界(44px)ちょうど", 8, self._attract_range(8), True),
            ("レベル8: 境界の1px 外(45px)", 8, self._attract_range(8) + 1, False),
        ]
        for name, level, distance, attracted in test_cases:
            with self.subTest(name):
                self._assert_observed_before_collect(distance, self.ATTRACT_FRAMES)
                diff = (self.DIRECTION[0] * distance, self.DIRECTION[1] * distance)
                field = self._field_with_player_level(level)
                field._drops = [self._drop_at(diff)]  # pylint: disable=W0212

                for _ in range(self.ATTRACT_FRAMES):
                    field.process_frame()

                expected = (
                    self._attracted_state(diff, self.ATTRACT_FRAMES)
                    if attracted
                    else self._kept_state(diff)
                )
                self.assertEqual([expected], field.drop_states())
                self._assert_player_stayed(field)


class TestPlayerHpInitialValue(TestParent):
    """Field 生成直後に player_hp が既定の初期値で取得できること（ID-012
    サイクル1）。HP の具体的な初期値はゲームバランスの詳細（RARE_DROP_RATE
    と同じ理由で数値そのものは Green が決める）ため、テストは値を固定せず
    `Player.INITIAL_HP` を参照する（HP は Player 自身が保持し Field は
    委譲するのみ（ID-013-20）のため、初期値の情報源は Player を参照する。
    準備フェーズの設計方針どおり、初期値の表現形式はここでは決めない）。
    HP に関する処理は今後（ID-015 の被弾処理など）拡張が見込まれるため、
    ドロップ数のテストとは分離し、HP 専用のクラスとして独立させる"""

    def test_player_hp_starts_at_initial_value(self):
        field = Field()
        self.assertEqual(Player.INITIAL_HP, field.player_hp)


class TestPlayerHpDecreasesOnMobContact(TestParent):
    """プレイヤーの矩形（登録座標 + 8x8）とモブの矩形（登録座標 + 8x8）が
    1ピクセルでも重なると、process_frame() 後に player_hp が1減少し、
    辺が接するだけ（重なりなし）では減少しないこと（ID-015 サイクル2）。
    接触判定の境界は毎フレームの移動で自然に通過する条件のため、
    TestMobDestroyedOnBulletHit・TestDropCollectedOnPlayerContact と同様、
    各辺の境界値をパラメタライズテストで仕様として固定する（同じ
    _rects_overlap() の重なり規約）。同一フレームで複数モブと接触した
    場合の減少量はここでは仕様として固定しない（連続接触の抑制は
    無敵時間＝サイクル3の観点）ため、1回の実行につきモブは1体のみ
    注入する。

    接触した（HPが減少した）フレームでは無敵時間が開始されるため
    player_is_invincible が True になり、接触しなかった（HPが変化しない）
    フレームでは無敵時間が一度も開始されないため False のままであることも
    あわせて検証する（ID-015 サイクル3で Field に追加した公開IF
    player_is_invincible の、接触判定と同一フレームでの振る舞いを固定する。
    無敵時間の残りフレーム数の推移そのものは TestPlayerInvincibleAfterMobContact
    の観点のためここでは扱わない）"""

    def _run_process_frame_with_mobs(self, mob_positions):
        """モブ（登録座標・speed 0）を注入して process_frame() を1回呼ぶ
        （TestMobDestroyedOnBulletHit の注入ヘルパーと同型。速度 0 のため
        前進では位置が変わらず、重なり／非重なりの配置が固定される）。
        開始時に発射される1発の弾は、プレイヤーに重ねたモブを同一フレーム
        で撃破して接触の検証を妨げるため取り除く。プレイヤーの進行方向は
        真上の目的地へのクリックで固定する（注入モブへの自動追尾で横へ
        前進すると image_x の丸め位置が1ピクセル動き、境界値の配置が
        覆るため。真上への前進 0.5px では丸め位置が変わらず、接触解決の
        挿入位置が前進の前後いずれでも同じ配置で判定される）"""
        field = Field()
        # 開始時の1匹は検証対象外のため、注入したモブのみへ置き換える
        field._mobs = [  # pylint: disable=W0212
            Mob(x + Mob.WIDTH / 2, y + Mob.HEIGHT / 2, 0) for x, y in mob_positions
        ]
        field._bullets = []  # pylint: disable=W0212
        self._click_at(field, (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), (0, -50))
        field.process_frame()
        return field

    # プレイヤー矩形の各辺における「1ピクセル重なる（接触）」と「辺が
    # 接するだけ（非接触）」の境界値の組 (名前, 接触位置, 非接触位置)。
    # 変化させない側の軸はプレイヤーとモブの中心を揃え、その軸では明確に
    # 重ねる（プレイヤーとモブは同サイズのため中心合わせの座標は
    # プレイヤーの登録座標と一致する）。左・上はモブ矩形の右辺・下辺が
    # プレイヤー矩形に届くか、右・下はモブ矩形の左辺・上辺がプレイヤー
    # 矩形に入るかの境界になる。位置はすべて開始時の表示領域の明確な
    # 内側で、領域外除去の判定と干渉しない
    ALIGNED_X = TestParent.INITIAL_PLAYER_X + Player.WIDTH // 2 - Mob.WIDTH // 2
    ALIGNED_Y = TestParent.INITIAL_PLAYER_Y + Player.HEIGHT // 2 - Mob.HEIGHT // 2
    BOUNDARY_CASES = [
        (
            "左辺",
            (TestParent.INITIAL_PLAYER_X - Mob.WIDTH + 1, ALIGNED_Y),
            (TestParent.INITIAL_PLAYER_X - Mob.WIDTH, ALIGNED_Y),
        ),
        (
            "右辺",
            (TestParent.INITIAL_PLAYER_X + Player.WIDTH - 1, ALIGNED_Y),
            (TestParent.INITIAL_PLAYER_X + Player.WIDTH, ALIGNED_Y),
        ),
        (
            "上辺",
            (ALIGNED_X, TestParent.INITIAL_PLAYER_Y - Mob.HEIGHT + 1),
            (ALIGNED_X, TestParent.INITIAL_PLAYER_Y - Mob.HEIGHT),
        ),
        (
            "下辺",
            (ALIGNED_X, TestParent.INITIAL_PLAYER_Y + Player.HEIGHT - 1),
            (ALIGNED_X, TestParent.INITIAL_PLAYER_Y + Player.HEIGHT),
        ),
    ]

    def test_player_hp_decreases_when_mob_overlaps_by_one_pixel(self):
        for name, contact_pos, _ in self.BOUNDARY_CASES:
            with self.subTest(name):
                field = self._run_process_frame_with_mobs([contact_pos])
                self.assertEqual(Player.INITIAL_HP - 1, field.player_hp)
                self.assertTrue(field.player_is_invincible)

    def test_player_hp_is_kept_when_mob_only_touches_edge(self):
        for name, _, apart_pos in self.BOUNDARY_CASES:
            with self.subTest(name):
                field = self._run_process_frame_with_mobs([apart_pos])
                self.assertEqual(Player.INITIAL_HP, field.player_hp)
                self.assertFalse(field.player_is_invincible)


class TestPlayerInvincibleAfterMobContact(TestParent):
    """モブとの接触で被弾した直後の Player.INVINCIBLE_FRAMES フレームの
    間は無敵となり、接触し続けても player_hp がそれ以上減少しないこと、
    および無敵時間の経過後（被弾フレームの INVINCIBLE_FRAMES + 1 フレーム
    後）の接触では再び減少すること（ID-015 サイクル3）。無敵時間の長さは
    Player の新規クラス定数 INVINCIBLE_FRAMES として導入し（HP と同じ
    「接触イベント」に閉じた Player 自身の状態の関心事のため INITIAL_HP と
    同じ Player 側へ置く。具体的な値はゲームバランスの詳細のためテストでは
    固定せず Green が決める）、期待値はこの定数を用いた計算式で表現する。
    接触判定の境界仕様はサイクル2（TestPlayerHpDecreasesOnMobContact）の
    観点のため、ここでは明確な重なりの位置のみを使う。

    Field.player_is_invincible（次サイクルの点滅描画結線が参照する予定の
    公開IF）についても、各フレーム数での想定値をあわせて検証する。ただし
    player_is_invincible は Field.process_frame() 完了後（＝その時点の
    無敵タイマー消費（Player.tick_invincibility()）も終わった後）の値を
    返すため、「無敵時間の最終フレーム（被弾フレームの INVINCIBLE_FRAMES
    フレーム後）」は接触こそ無敵で防がれる（player_hp は変化しない）ものの、
    そのフレームの消費で残りフレーム数がちょうど0になるため
    player_is_invincible は False になる（player_hp が保たれる期間と
    player_is_invincible が True であり続ける期間は、この最終フレームの
    1フレーム分だけずれる）。この振る舞いの違いにより、フレーム数の区分は
    2つに分かれる: (1) 被弾直後のフレームから「無敵時間の最終フレーム」
    （INVINCIBLE_FRAMES + 1 フレーム目）までは player_hp が一貫して
    「保たれる」ため1関数でまとめて検証し、その中で player_is_invincible
    はフレームごとに異なる（INVINCIBLE_FRAMES フレーム目までは True、
    最終フレームのみ False）ためケースごとにパラメータ化する。
    (2) 無敵時間が明けた直後のフレーム（INVINCIBLE_FRAMES + 2 フレーム目）
    は player_hp が再び減少し player_is_invincible も True に戻るという、
    (1) とは異なる期待値の組のため別の1関数に分ける
    （[[feedback-split-subtest-by-expectation]] が禁じるのは、1関数内で
    異なる期待値「系統」を複数の subTest ループに分けて回す書き方であり、
    区分内で一部の期待値が一貫し他がケースごとに異なるグルーピングや、
    各ケースが自身の期待値の組を持つパラメータ化自体は対象外）"""

    def _run_frames_with_mob_kept_on_player(self, frame_count):
        """毎フレーム、プレイヤーの画像中心に重ねた速度 0 のモブ1体へ
        置き換えてから process_frame() を呼ぶことを frame_count 回繰り返す。
        プレイヤーは毎フレーム前進するため、固定位置のモブでは無敵時間の
        フレーム数の経過中に重なりが解けてしまうことから、接触状態の維持は
        モブの毎フレーム再配置で行う（両矩形は同サイズの完全一致の配置から
        1フレームの前進（丸めで最大1ピクセル）分しかずれず、明確な重なりが
        保たれる）。弾は発射間隔の経過ごとに重なったモブを撃破して接触を
        解いてしまうため、毎フレーム取り除く（サイクル2の注入ヘルパーと
        同じ理由。複数フレームにわたるため除去も毎フレーム行う）"""
        field = Field()
        for _ in range(frame_count):
            player_x, player_y, _ = field.player_state()
            field._mobs = [  # pylint: disable=W0212
                Mob(player_x + Player.WIDTH / 2, player_y + Player.HEIGHT / 2, 0)
            ]
            field._bullets = []  # pylint: disable=W0212
            field.process_frame()
        return field

    def test_player_hp_is_kept_from_contact_until_invincible_period_ends(self):
        # 被弾直後のフレームから「無敵時間の最終フレーム」（被弾フレームの
        # INVINCIBLE_FRAMES + 1 フレーム後）までは、接触し続けても最初の
        # 被弾の1減少のみで player_hp が保たれる。player_is_invincible は
        # 無敵タイマーを消費し切る前（INVINCIBLE_FRAMES フレーム目まで）は
        # True だが、「無敵時間の最終フレーム」はその接触自体は無敵で
        # 防がれるものの、そのフレームの消費（tick_invincibility()）で
        # 無敵タイマーがちょうど0になるため False になる（player_hp が
        # 保たれる期間と player_is_invincible が True であり続ける期間は、
        # この最終フレームの1フレーム分だけずれる）
        test_cases = [
            ("被弾直後のフレームの再接触", 2, True),
            (
                "無敵タイマーを消費し切る前の最終フレーム",
                Player.INVINCIBLE_FRAMES,
                True,
            ),
            ("無敵時間の最終フレームの再接触", 1 + Player.INVINCIBLE_FRAMES, False),
        ]
        for name, frame_count, expected_is_invincible in test_cases:
            with self.subTest(name):
                field = self._run_frames_with_mob_kept_on_player(frame_count)
                self.assertEqual(Player.INITIAL_HP - 1, field.player_hp)
                self.assertEqual(expected_is_invincible, field.player_is_invincible)

    def test_player_hp_decreases_and_becomes_invincible_again_after_period_elapses(
        self,
    ):
        # 無敵時間が明けた直後のフレーム（被弾フレームの
        # INVINCIBLE_FRAMES + 2 フレーム後）の接触では再びHPが減少し、
        # 新たな無敵時間が開始されるため player_is_invincible も True になる
        field = self._run_frames_with_mob_kept_on_player(2 + Player.INVINCIBLE_FRAMES)
        self.assertEqual(Player.INITIAL_HP - 2, field.player_hp)
        self.assertTrue(field.player_is_invincible)


class TestPlayerHitbackOnMobContact(TestParent):
    """モブとの接触で被弾した際のヒットバック（ID-015 サイクル5・6・7）。
    プレイヤーは接触フレームを1フレーム目として Player.HITBACK_FRAMES
    フレームかけて、モブと反対方向（モブの画像中心からプレイヤーの画像
    中心へ向かう方向）へ合計 Player.HITBACK_DISTANCE だけ少しずつ移動する
    （kフレーム目までの合計変位は HITBACK_DISTANCE × k / HITBACK_FRAMES。
    1フレームでは移動し切らない）。接触時は目的地移動中であれば目的地を
    キャンセルする（サイクル7。接触後は自動追尾の状態へ戻る）。ヒット
    バック中は：

    - プレイヤーの向き（player_state() の角度）はヒットしたモブの方向を
      向き続ける（画面内の最も近いモブへの自動追尾よりも優先される。
      目的地は接触時にキャンセル済みのため向きの維持と競合しない）
    - 通常の前進（進行方向への advance）は行わず、位置はヒットバックの
      変位のみで変化する（向きはモブへ向いているため、前進を続けると
      ヒットバックと逆向きの移動が混ざり打ち消し合ってしまう）

    無敵時間中の再接触では新しいヒットバックは始まらず、進行中の
    ヒットバックがそのまま継続する（目的地のキャンセルも起きない）。

    ヒットバックが自動追尾より優先されることはモードに依らないため、
    向きの維持の検証（test_facing_is_kept_on_contacted_mob_despite_
    nearer_visible_target）は自動戦闘・自動収集の両モードで行う
    （ユーザー指摘、2026-07-25）。ただし他クラス
    （TestDestinationSuppressesAutoTrack 等）のように「モブと同じ位置へ
    ドロップを置く」ことはできない: ドロップの回収判定には無敵時間の
    例外がなく、プレイヤー矩形（8x8）と重なる位置のドロップは接触
    フレームで回収されて消えてしまうため（本クラスの注入モブはいずれも
    プレイヤーの矩形内・至近に置かれる）。そのため自動収集モードの囮は
    プレイヤーから十分離した位置のドロップとし、囮の位置ではなく
    「囮の方向を向かず接触モブの方向を向き続ける」期待値を両モードで
    共通にしている。

    継続フレーム数は Player の新規クラス定数 HITBACK_FRAMES として名称・
    保持場所をここで決定する（距離 HITBACK_DISTANCE と同じ「接触
    イベント」に閉じた Player 自身の関心事のため同じ Player 側へ置く。
    具体的な値はゲームバランスの詳細のためテストでは固定せず Green が
    決める。ただし「1フレームで移動し切らない」仕様の前提として 2以上で
    あることのみをテストで固定する）。期待値はこの定数とプレイヤーの
    移動モデル（float の中心点へ変位を蓄積し、参照時に丸めて登録座標へ
    変換する）に合わせた計算式で表現する。接触判定の境界仕様はサイクル2
    （TestPlayerHpDecreasesOnMobContact）の観点のため、明確な重なりの
    位置のみを使う"""

    # 接触解決時（セットアップ1フレーム + 接触フレームの前進2回の後）の
    # プレイヤーの画像中心点。真上への前進のため x は初期中心のまま、y は
    # 2フレーム分 PLAYER_SPEED だけ上がり整数座標になる。前進1回（.5）の
    # 中心 y では期待値の丸め（round の偶数丸め）が HITBACK_DISTANCE の
    # 偶奇に依存してしまうため、2フレームで整数座標に揃える
    CONTACT_CENTER_X = TestParent.INITIAL_PLAYER_X + TestParent.PLAYER_CENTER_OFFSET_X
    CONTACT_CENTER_Y = (
        TestParent.INITIAL_PLAYER_Y
        + TestParent.PLAYER_CENTER_OFFSET_Y
        - 2 * Field.PLAYER_SPEED
    )
    # 接触フレームで注入するモブの、接触解決時のプレイヤー画像中心からの
    # 中心間距離。同サイズ（8x8）の両矩形が4ピクセル重なる明確な接触の配置
    MOB_CENTER_GAP = 4

    # (名前, モブ中心のプレイヤー中心からのオフセット, ヒットバックの
    # 単位ベクトル)。モブの中心を接触解決時のプレイヤー中心と片軸で揃える
    # ことで、反対方向（モブ中心からプレイヤー中心への方向）が軸沿いの
    # 単位ベクトルになり、期待値の変位が1軸に閉じる
    DIRECTION_CASES = [
        ("左からの接触", (-MOB_CENTER_GAP, 0), (1, 0)),
        ("右からの接触", (MOB_CENTER_GAP, 0), (-1, 0)),
        ("上からの接触", (0, -MOB_CENTER_GAP), (0, 1)),
        ("下からの接触", (0, MOB_CENTER_GAP), (0, -1)),
    ]
    # 自動戦闘モードの囮（接触モブより常に近い、プレイヤー中心の 3px 真上の
    # モブ）と、自動収集モードの囮（真上 30px のドロップ）の、接触解決時の
    # プレイヤー画像中心からの y 差分。ドロップは唯一のドロップであれば
    # 距離によらず「最も近いドロップ」になるため、囮としての条件は「回収
    # されないこと」（プレイヤー矩形 8x8 とドロップ 4x4 が重ならない片軸
    # 6px 以上の距離）であり、モブの囮と同じ位置には置けない
    NEARER_MOB_DY = -3
    DECOY_DROP_DY = -30
    # ヒットバック終了後に注入する追尾対象の、その時点のプレイヤー画像
    # 中心点からの差分。モブは右、ドロップの囮は真上という異なる方向に
    # 置き、モードの復帰有無を向きで判別できるようにする（ID-022 サイクル2）
    POST_CONTACT_MOB_DX = 20
    POST_CONTACT_DECOY_DROP_DY = -30

    def _run_frames_to_contact(self, mob_center_offset, mode=MoveMode.ATTACK):
        """セットアップフレーム（モブなし）+ 接触フレーム（プレイヤー中心
        からオフセット位置へ速度 0 のモブを注入）の2フレームを進める。
        プレイヤーの進行方向は真上の目的地へのクリックで固定する（注入モブ
        への自動追尾で向き・前進方向が変わると期待値の配置が覆るため。
        サイクル2の注入ヘルパーと同じ理由）。弾はプレイヤーに重ねたモブを
        撃破して接触の検証を妨げないよう取り除く（同ヘルパーと同じ理由の
        予防措置。本シナリオの3フレーム以内では発射間隔に達しない）。
        ドロップは1つも存在しないため、モードによらず接触までの動きは
        同じになる（目的地移動中で自動追尾自体が抑止されてもいる）"""
        field = Field()
        if mode is MoveMode.COLLECT:
            field.toggle_player_move_mode()
        field._mobs = []  # pylint: disable=W0212
        field._bullets = []  # pylint: disable=W0212
        self._click_at(field, (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), (0, -50))
        field.process_frame()
        field._mobs = [  # pylint: disable=W0212
            Mob(
                self.CONTACT_CENTER_X + mob_center_offset[0],
                self.CONTACT_CENTER_Y + mob_center_offset[1],
                0,
            )
        ]
        field.process_frame()
        return field

    def _advance_hitback_frames(self, field, frames, extra_mobs=()):
        """接触フレーム後のヒットバック継続フレームを進める。毎フレーム、
        モブを接触モブ（+ 追加注入モブ）のみへ、弾を空へ揃えてから
        process_frame() を呼ぶ（発射間隔・出現間隔への到達で構成が変わら
        ないよう固定する。TestPlayerInvincibleAfterMobContact の注入
        ヘルパーと同じ理由。接触モブは速度 0 のため接触時の位置に留まり
        続ける）"""
        hit_mob = field._mobs[0]  # pylint: disable=W0212
        for _ in range(frames):
            field._mobs = [hit_mob, *extra_mobs]  # pylint: disable=W0212
            field._bullets = []  # pylint: disable=W0212
            field.process_frame()

    def _expected_hitback_pos(self, hitback_unit, elapsed_frames):
        # 接触解決時の画像中心点 + ヒットバックの変位（HITBACK_DISTANCE を
        # HITBACK_FRAMES で等分した1フレームあたりの距離 × 接触フレームを
        # 1フレーム目とする経過フレーム数）を丸めて登録座標へ変換する
        # （プレイヤーの移動モデルと同じ計算式。ヒットバック中は通常の
        # 前進を行わないため、変位はヒットバック分のみ）
        moved = Player.HITBACK_DISTANCE * elapsed_frames / Player.HITBACK_FRAMES
        return (
            round(self.CONTACT_CENTER_X + moved * hitback_unit[0])
            - self.PLAYER_CENTER_OFFSET_X,
            round(self.CONTACT_CENTER_Y + moved * hitback_unit[1])
            - self.PLAYER_CENTER_OFFSET_Y,
        )

    def test_player_is_knocked_back_gradually_while_facing_contacted_mob(self):
        # 「1フレームで移動し切らない」仕様の前提（HITBACK_FRAMES が 1 だと
        # 接触フレームで全変位が完了してしまい複数フレーム仕様にならない）
        self.assertGreater(Player.HITBACK_FRAMES, 1)
        for name, mob_center_offset, hitback_unit in self.DIRECTION_CASES:
            with self.subTest(name):
                field = self._run_frames_to_contact(mob_center_offset)
                # 接触の成立ガード（配置ミスでヒットバックの検証が空振り
                # していないことの確認。HP減少の仕様自体はサイクル2の観点）
                self.assertEqual(Player.INITIAL_HP - 1, field.player_hp)
                # ヒットバック中の期待角度はヒットしたモブの方向。プレイ
                # ヤーはモブと反対の軸沿いへだけ遠ざかるため、モブへの
                # 方向は接触時の軸沿いの単位ベクトルのまま変わらず、全
                # フレームで同じ角度になる（セットアップの目的地は接触時に
                # キャンセルされるが、ヒットバック中は自動追尾も抑止される
                # ため、左右・下からの接触ケースで目的地方向（0度）から
                # モブ方向へ向き変わったまま維持されることが固定される）
                expected_angle = self._raw_rotate(mob_center_offset)
                for elapsed in range(1, Player.HITBACK_FRAMES + 1):
                    with self.subTest(name, elapsed=elapsed):
                        player_x, player_y, player_angle = field.player_state()
                        self.assertEqual(
                            self._expected_hitback_pos(hitback_unit, elapsed),
                            (player_x, player_y),
                        )
                        self.assertEqual(expected_angle, player_angle)
                    self._advance_hitback_frames(field, 1)

    def test_player_is_not_knocked_back_on_recontact_while_invincible(self):
        # 左からの接触でヒットバック中・無敵中のプレイヤーへ、次の
        # フレームで画像中心に重なるモブを追加注入する。無敵中の接触は
        # 「なかったこと」として扱われるため、新しいヒットバックは
        # 始まらず、位置は進行中のヒットバックの2フレーム目の変位のみで
        # 変化する
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0))
        self.assertTrue(field.player_is_invincible)
        player_x, player_y, _ = field.player_state()
        recontact_mob = Mob(
            player_x + self.PLAYER_CENTER_OFFSET_X,
            player_y + self.PLAYER_CENTER_OFFSET_Y,
            0,
        )
        self._advance_hitback_frames(field, 1, extra_mobs=(recontact_mob,))
        recontact_x, recontact_y, _ = field.player_state()
        self.assertEqual(
            self._expected_hitback_pos((1, 0), 2), (recontact_x, recontact_y)
        )

    def test_destination_is_cancelled_on_mob_contact(self):
        # セットアップで真上へ設定した目的地が、モブとの接触（左からの
        # 接触。方向によらない目的地状態の仕様のため1方向のみで固定する）
        # で解除されること。接触の成立は HP の1減少でガードする（解除
        # されないと、ヒットバック終了後も自動追尾へ戻らず、接触時の
        # 向きのまま前進し続けてしまう）
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0))
        self.assertEqual(Player.INITIAL_HP - 1, field.player_hp)
        self.assertIsNone(field.destination)

    def test_destination_is_kept_on_recontact_while_invincible(self):
        # 接触で目的地が解除された無敵中のプレイヤーへ、新しい目的地を
        # クリックで設定してから、次のフレームで画像中心に重なるモブを
        # 追加注入する。無敵中の接触は「なかったこと」として扱われる
        # ため、新しい目的地は解除されず保持される
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0))
        self.assertTrue(field.player_is_invincible)
        player_x, player_y, _ = field.player_state()
        new_dest = self._click_at(field, (player_x, player_y), (0, -50))
        recontact_mob = Mob(
            player_x + self.PLAYER_CENTER_OFFSET_X,
            player_y + self.PLAYER_CENTER_OFFSET_Y,
            0,
        )
        self._advance_hitback_frames(field, 1, extra_mobs=(recontact_mob,))
        self.assertEqual(new_dest, field.destination)

    def test_facing_is_kept_on_contacted_mob_despite_nearer_visible_target(self):
        # (ケース名, 設定するモード)
        test_cases = [
            ("自動戦闘モードでより近いモブを追尾しない", MoveMode.ATTACK),
            ("自動収集モードでドロップを追尾しない", MoveMode.COLLECT),
        ]
        for name, mode in test_cases:
            with self.subTest(name):
                self._assert_facing_is_kept_during_hitback(mode)

    def _assert_facing_is_kept_during_hitback(self, mode):
        # 左からの接触で目的地はキャンセル済み（目的地による自動追尾の
        # 抑止が働かない、自動追尾が有効な状態）のまま、ヒットバック中の
        # プレイヤーへ両モードの追尾対象の囮を注入する。
        #
        # - 自動戦闘の囮: プレイヤーの画像中心の 3px 真上へ注入し続ける
        #   速度 0 のモブ。プレイヤーとの中心間距離 hypot(d, 3)（d は
        #   ヒットバックの経過変位 0 < d <= 8）は接触モブとの距離 4 + d
        #   より常に近い（hypot(d,3)² = d²+9 < d²+8d+16 = (4+d)²）ため、
        #   抑止がなければこのモブの方向を向くはず。プレイヤーと重なるが
        #   無敵中のため接触は「なかったこと」として扱われ判定に影響しない
        # - 自動収集の囮: プレイヤーの真上 30px のドロップ。唯一のドロップ
        #   のため距離によらず最も近いドロップであり、抑止がなければ
        #   その方向（ほぼ真上）を向くはず（ID-022 サイクル2 Refactor 注記:
        #   接触した時点で move_mode は既に自動戦闘へ遷移済み〔ID-022-6〕
        #   のため、実際に抑止がなければ向くのは自動戦闘の囮〔nearer_mob〕
        #   の方向であり、この囮ドロップは元から追尾対象にならない。それでも
        #   「ヒットバック中は接触モブの方向を向き続け、いずれの囮も追尾
        #   されない」という本テストの結論・期待値は変わらないため、モード
        #   ごとの区別は維持する）
        #
        # いずれのモードでも、ヒットバック中は接触モブの方向（真横 =
        # -90度）を向き続け、位置はヒットバックの変位のみで変化する
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0), mode)
        # 接触による目的地キャンセルの成立ガード（キャンセル仕様自体の
        # 検証は test_destination_is_cancelled_on_mob_contact の観点）
        self.assertIsNone(field.destination)
        nearer_mob = Mob(
            self.CONTACT_CENTER_X, self.CONTACT_CENTER_Y + self.NEARER_MOB_DY, 0
        )
        decoy_drop = Drop(
            self.CONTACT_CENTER_X,
            self.CONTACT_CENTER_Y + self.DECOY_DROP_DY,
            0,
            False,
        )
        field._drops = [decoy_drop]  # pylint: disable=W0212
        expected_angle = self._raw_rotate((-self.MOB_CENTER_GAP, 0))
        for elapsed in range(2, Player.HITBACK_FRAMES + 1):
            self._advance_hitback_frames(field, 1, extra_mobs=(nearer_mob,))
            with self.subTest(elapsed=elapsed):
                player_x, player_y, player_angle = field.player_state()
                self.assertEqual(
                    self._expected_hitback_pos((1, 0), elapsed),
                    (player_x, player_y),
                )
                self.assertEqual(expected_angle, player_angle)
        # 囮のドロップは回収されずに残っている（追尾対象として有効なまま
        # 追尾されなかったことのガード）
        self.assertEqual(self._drop_states_of([decoy_drop]), field.drop_states())

    def test_move_mode_becomes_attack_and_mob_tracking_resumes_after_contact_from_collect_mode(
        self,
    ):
        # ID-022 サイクル2: 自動収集モードで目的地移動へ入った状態でモブと
        # 接触すると、ヒットバック終了後は自動戦闘モードへ戻ること（＝最も
        # 近いモブを追尾し、最も近いドロップは追尾しないこと）と、
        # field.player_move_mode が自動戦闘モードを返すことを検証する
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0), MoveMode.COLLECT)
        self.assertEqual(Player.INITIAL_HP - 1, field.player_hp)
        self.assertIsNone(field.destination)
        # ヒットバック終了までの残りフレームを進める（接触フレームを1
        # フレーム目として HITBACK_FRAMES フレームで終了する）
        self._advance_hitback_frames(field, Player.HITBACK_FRAMES - 1)

        hitback_end_x, hitback_end_y, _ = field.player_state()
        center_x = hitback_end_x + self.PLAYER_CENTER_OFFSET_X
        center_y = hitback_end_y + self.PLAYER_CENTER_OFFSET_Y
        # 接触モブに代えて、ヒットバック終了後のプレイヤー中心から見て右方向
        # へ新しいモブを、真上へドロップの囮を注入する。自動戦闘モードへ
        # 戻っていればモブの方向（右）を、自動収集モードのままならドロップの
        # 方向を向くはずのため、モードの復帰有無を向きで判別できる
        mob = Mob(center_x + self.POST_CONTACT_MOB_DX, center_y, 0)
        decoy_drop = Drop(
            center_x,
            center_y + self.POST_CONTACT_DECOY_DROP_DY,
            0,
            False,
        )
        field._mobs = [mob]  # pylint: disable=W0212
        field._drops = [decoy_drop]  # pylint: disable=W0212
        field._bullets = []  # pylint: disable=W0212
        field.process_frame()

        self.assertEqual(MoveMode.ATTACK, field.player_move_mode)
        _, _, player_angle = field.player_state()
        self.assertAlmostEqual(
            self._raw_rotate((self.POST_CONTACT_MOB_DX, 0)), player_angle
        )
        # 囮のドロップは回収されずに残っている（追尾対象として有効なまま
        # 追尾されなかったことのガード）
        self.assertEqual(self._drop_states_of([decoy_drop]), field.drop_states())

    def test_move_mode_is_unchanged_on_recontact_while_invincible(self):
        # 接触直後（無敵中）の再接触は「なかったこと」として扱われ、新たな
        # モード遷移も起きないこと
        # （test_destination_is_kept_on_recontact_while_invincible と同型）
        field = self._run_frames_to_contact((-self.MOB_CENTER_GAP, 0), MoveMode.COLLECT)
        self.assertEqual(MoveMode.ATTACK, field.player_move_mode)
        self.assertTrue(field.player_is_invincible)
        player_x, player_y, _ = field.player_state()
        recontact_mob = Mob(
            player_x + self.PLAYER_CENTER_OFFSET_X,
            player_y + self.PLAYER_CENTER_OFFSET_Y,
            0,
        )
        self._advance_hitback_frames(field, 1, extra_mobs=(recontact_mob,))
        self.assertEqual(MoveMode.ATTACK, field.player_move_mode)


class TestDropCountIncrementsOnCollect(TestParent):
    """通常/レアドロップ数（normal_drop_count／rare_drop_count）が、
    Field 生成直後は既定の初期値 0 であり（ID-012 サイクル1）、プレイヤーとの
    接触で回収されたドロップの種別に応じて加算されること（ID-012 サイクル2）
    を、process_frame() 経由の e2e で検証する。初期値 0 は「回収したドロップ
    が0個の場合の加算結果」として、加算の検証と同じ subTest 群の1ケースに
    含める（回収0個時にも初期値 0 が保たれることの検証を兼ねるため、独立した
    初期値専用テストは設けない）。回収判定の境界仕様は
    TestDropCollectedOnPlayerContact の観点のため、ここでは明確な重なり／
    非重なりの位置のみを使う"""

    def _run_process_frame_with_drops(self, drops):
        """ドロップ（(x, y, is_rare) のタプル）を注入して process_frame() を
        1回呼ぶ（TestDropCollectedOnPlayerContact の注入ヘルパーと同型だが、
        種別ごとのカウント加算の検証に is_rare が必要なため、種別も注入で
        指定する）。プレイヤーは開始時の画面中央から動かさない（1フレームの
        前進量は 1 ピクセル未満のため、明確な重なり／非重なりの配置は
        覆らない）"""
        field = Field()
        field._drops = [  # pylint: disable=W0212
            Drop(x + Drop.WIDTH / 2, y + Drop.HEIGHT / 2, 0, is_rare)
            for x, y, is_rare in drops
        ]
        field.process_frame()
        return field

    def test_collected_drop_increments_count_of_its_type(self):
        # 回収されるドロップはプレイヤー（開始時は画面中央）と画像中心を
        # 揃えて明確に重ねる（TestDropCollectedOnPlayerContact と同じ配置）
        collected_pos = (
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X - Drop.WIDTH // 2,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y - Drop.HEIGHT // 2,
        )
        # 同一フレームで複数個の回収を検証するための2個目・3個目の重なり
        # 位置（中心合わせから1ピクセルずらしても 4x4 のドロップ全体が
        # 8x8 のプレイヤーの明確な内側に収まる）
        collected_pos_2 = (collected_pos[0] + 1, collected_pos[1])
        collected_pos_3 = (collected_pos[0], collected_pos[1] + 1)
        # プレイヤーと明確に重ならない残存ドロップ。位置は表示領域の明確な
        # 内側とし、領域外消滅の判定と干渉させない（回収されていない
        # ドロップがカウントされないことの検証を兼ねる）
        kept_pos = (collected_pos[0] + 40, collected_pos[1])
        # (名前, 注入するドロップ, 期待する通常カウント, 期待するレアカウント)
        test_cases = [
            (
                "ドロップを回収しない場合はカウントは初期値の0のまま",
                [],
                0,
                0,
            ),
            (
                "通常ドロップの回収は通常カウントのみ加算（残存レアは数えない）",
                [(*collected_pos, False), (*kept_pos, True)],
                1,
                0,
            ),
            (
                "レアドロップの回収はレアカウントのみ加算（残存通常は数えない）",
                [(*collected_pos, True), (*kept_pos, False)],
                0,
                1,
            ),
            (
                "同一フレームの複数回収は種別ごとにすべて加算される",
                [
                    (*collected_pos, False),
                    (*collected_pos_2, False),
                    (*collected_pos_3, True),
                ],
                2,
                1,
            ),
        ]
        for name, drops, expected_normal, expected_rare in test_cases:
            with self.subTest(name):
                field = self._run_process_frame_with_drops(drops)
                self.assertEqual(expected_normal, field.normal_drop_count)
                self.assertEqual(expected_rare, field.rare_drop_count)


class TestShootingGrowsOnNormalDropCollect(TestParent):
    """通常ドロップの回収が Player の成長（add_normal_drop_count()）へ
    結線され、「ドロップ回収 → 累計加算 → 強化が発射へ反映」が
    process_frame() 経由の e2e で成立すること（ID-013 サイクル5）。
    成長の個別の効果値（各しきい値・間隔・角度）の網羅的な検証は
    test_actor.py の Player 単体テスト（サイクル1〜4）で済んでいるため、
    ここでは発射間隔・発射方向数が実際に変わる代表しきい値を1つずつ使い、
    結線されていることの確認に絞る。レアドロップは成長に寄与しない
    （requirements.md §3.5）ため通常種別のみを注入する"""

    def _collect_drops_then_return_field(self, drop_count):
        """プレイヤーと明確に重なる通常ドロップを drop_count 個注入し、
        1フレームの process_frame() で全て回収させた Field を返す
        （TestDropCountIncrementsOnCollect の注入ヘルパーと同型。回収は
        同一フレームの発射判定より先に処理されるため、返却時点で成長は
        反映済み・弾は未発射（発射タイマー1フレーム目）の状態になる）"""
        field = Field()
        # モブの移動・追尾・撃破によるドロップ生成は本テストの検証対象外の
        # ため除去する（検証で進めるフレーム数は出現間隔 MOB_SPAWN_INTERVAL
        # 未満に収め、途中の出現もさせない）
        field._mobs = []  # pylint: disable=W0212
        # 回収されるドロップはプレイヤー（開始時は画面中央）と画像中心を
        # 揃えて明確に重ねる（TestDropCollectedOnPlayerContact と同じ配置。
        # ドロップは重なって存在できるため、全個数を同一位置で注入し
        # 1フレームでまとめて回収させる）
        collected_pos = (
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X - Drop.WIDTH // 2,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y - Drop.HEIGHT // 2,
        )
        # 複製すると同一オブジェクトの参照が並んでしまうため、内包表記で
        # drop_count 個の Drop インスタンスを個別に生成する
        field._drops = [  # pylint: disable=W0212
            Drop(
                collected_pos[0] + Drop.WIDTH / 2,
                collected_pos[1] + Drop.HEIGHT / 2,
                0,
                False,
            )
            for _ in range(drop_count)
        ]
        field.process_frame()
        return field

    def test_shoot_interval_halves_after_collecting_threshold_drops(self):
        # 累計しきい値 10×(2^1−1) = 10 個の回収で発射間隔が半分（頻度2倍）に
        # なる（サイクル1で確定済みの効果）。回収後、基準間隔
        # BULLET_SHOOT_INTERVAL（30フレーム）の窓では半減間隔（30/2 = 15）
        # による発射が 30 / 15 = 2 回起こり、1回の発射は1発（レベル1は
        # 多方向化しない）のため弾数 = 発射回数になる。結線されていない場合は
        # 基準間隔のまま窓内の発射が1回（弾1発）になるため判別できる
        threshold = 10 * (2**1 - 1)
        window = Player.BULLET_SHOOT_INTERVAL
        halved_interval = Player.BULLET_SHOOT_INTERVAL / 2
        expected_bullets = int(window / halved_interval)

        field = self._collect_drops_then_return_field(threshold)
        for _ in range(window):
            field.process_frame()

        self.assertEqual(expected_bullets, len(field.bullet_states()))

    def test_bullets_split_into_directions_after_collecting_threshold_drops(self):
        # 累計しきい値 10×(2^4−1) = 150 個の回収で1回の発射が
        # n(4) = 2^(4−3) + 1 = 3 方向（3発同時。サイクル8で進行方向と一致
        # する弾の+1発を追加）になる。発射間隔の具体値・弾の角度の検証は
        # サイクル1〜4・8の担当のため、ここでは間隔へ依存せず「最初の発射」
        # まで基準間隔を上限にフレームを進め、その発射の弾数のみを検証する。
        # 結線されていない場合は最初の発射が進行方向へ1発のままになるため
        # 判別できる
        threshold = 10 * (2**4 - 1)
        expected_bullets = 2 ** (4 - 3) + 1

        field = self._collect_drops_then_return_field(threshold)
        for _ in range(Player.BULLET_SHOOT_INTERVAL):
            field.process_frame()
            if field.bullet_states():
                break

        self.assertEqual(expected_bullets, len(field.bullet_states()))


class TestNextNormalDropThresholdExposed(TestParent):
    """Field が「次のレベルの累計しきい値」を公開 IF
    （`next_normal_drop_threshold`）から取得できること（ID-013 サイクル7）。
    しきい値は増分方式の系列 10×(2^level−1)（level=1..8 →
    10/30/70/150/310/630/1270/2550）であり、現在の累計取得数がどの区間に
    あるかで「次に到達するしきい値」が決まる。レベル8（累計2550個）到達後は
    次のしきい値が存在しないため、その場合は None を返す（「次がない」ことを
    表す内部表現として None を採用する。表示側での「-」への変換は
    TestStatusDraw の担当）。個別の効果（発射間隔・方向数）自体の検証は
    test_actor.py・TestShootingGrowsOnNormalDropCollect で済んでいるため、
    ここではしきい値の値自体の取得のみを扱う"""

    def _field_with_normal_drop_count(self, count):
        field = Field()
        field._player._normal_drop_count = count  # pylint: disable=W0212
        return field

    def test_returns_next_level_threshold_for_current_cumulative_count(self):
        # しきい値の系列 10×(2^level−1)（level=1..8）の各区間について、
        # 下端（前回のしきい値ちょうど）と上端（次のしきい値の1個手前）の
        # 両方で「次のしきい値」が変わらないことを境界値として検証する
        # （例: 累計0〜9個はいずれも次が10、9個から10個への到達で30に
        # 切り替わる）。レベル8到達（累計2550個）以降は次のしきい値が
        # 存在しないため、しきい値ちょうど・それを大きく超えた値の両方で
        # None になることも検証する
        thresholds = [10 * (2**level - 1) for level in range(1, 9)]
        test_cases = []
        previous = 0
        for threshold in thresholds:
            test_cases.append((previous, threshold))
            test_cases.append((threshold - 1, threshold))
            previous = threshold
        test_cases.append((thresholds[-1], None))
        test_cases.append((thresholds[-1] * 2, None))

        for count, expected_threshold in test_cases:
            with self.subTest(count=count):
                field = self._field_with_normal_drop_count(count)
                self.assertEqual(expected_threshold, field.next_normal_drop_threshold)


class TestMobSpawnGrowsOnRareDropCollect(TestParent):
    """レアドロップの累計取得数がレベルアップのしきい値（次のレベルへの
    追加取得数が 1, 2, 4, 8, … と倍化し続ける増分方式で、累計しきい値は
    1, 3, 7, 15, 31, 63, …＝2^level−1）に到達した回収のときのみモブの
    出現間隔が半分（出現頻度が2倍）になること（ID-016、ID-014〔レア1個
    ごとに無条件で半減〕の置き換え、requirements.md §3.6）を、実際の
    レア取得イベント（プレイヤーと重なるドロップの回収）を経由した
    process_frame() の e2e で検証する。レベルアップを伴わない回収では
    間隔が変化しないこと（イベント駆動）も、毎フレームの累計出現数の
    照合で同時に検証する。出現間隔が1フレーム未満になった場合に1フレーム
    あたりの出現数が増える挙動（`_try_spawn_mob()` のキャリーオーバー、
    ID-014で確立済み）自体は本テストの検証範囲に含めない（MAX_RARE_COUNT
    の説明を参照。到達に必要なレア取得数がプレイヤー固定という本テストの
    前提と両立しない）。

    期待出現数は「レアドロップ累計 n 個取得後の出現間隔
    interval(n) = MOB_SPAWN_INTERVAL / 2^levelups(n)」（levelups(n) は
    累計 n 個に到達するまでのレベルアップ回数。レベル L のレベルアップ
    しきい値〔累計取得数〕は 2^L − 1 のため、levelups(n) は
    「2^L − 1 <= n を満たす最大の L」）と、出現タイマーのキャリーオーバー
    計算（毎フレーム timer を1進め、while timer >= interval:
    timer -= interval のループ回数だけ出現）から導出する。式はテストの
    期待値算出のみに使い、実装はイベント駆動（レベルアップ到達時のみ
    半減）を想定する"""

    # 検証するレア取得数の上限。レベルアップしきい値は 1, 3, 7, 15, 31, …
    # （2^level−1）で、interval(n) = 60/2^levelups(n) は window
    # （MOB_SPAWN_INTERVAL=60）を必ず割り切る（window/interval=2^levelups(n)
    # は常に整数）ため、レベルが進んでもフェーズ最終フレームで timer は
    # ちょうど0へ戻る。7 まで進めることで、レベル1（n=1）・レベル2（n=3）・
    # レベル3（n=7）の3回のレベルアップと、レベルアップを伴わない回収
    # （n=2,4,5,6）で間隔が変化しないことの両方を確認できる。
    # なお、この検証はプレイヤーを静止させ続ける前提（本クラス docstring
    # 参照）に依存しており、n=7 のフェーズ終盤（フレーム57、ID-014から
    # 変更していない既存のモブ出現ペースで到達する時点）で最初に出現した
    # モブがプレイヤーへ接触しヒットバックが発生する（ID-015）。接触は
    # モブ数を変化させないため n<=7 の検証自体は影響を受けないが、
    # ヒットバック後はプレイヤー位置が固定という前提が崩れ、以降のフェーズ
    # で注入するレアドロップの座標（固定の開始位置基準）が実際の
    # プレイヤー位置と重ならなくなり回収イベントが発生しなくなるため、
    # 7 より先には安全に拡張できない（interval < 1 に到達するレベル6
    # 〔n=63〕はこの制約の外にあり、本テストの対象外とする）
    MAX_RARE_COUNT = 7

    def _levelups_for_rare_count(self, count):
        """累計レア取得数が count に達するまでに発生したレベルアップの
        回数を返す。レベル L のレベルアップしきい値（累計取得数）は
        2^L − 1 で、「次 = 次 × 2 + 1」により次のしきい値を際限なく
        生成する（打ち止めを設けない設計はID-014と同じ）"""
        levelups = 0
        threshold = 1
        while threshold <= count:
            levelups += 1
            threshold = threshold * 2 + 1
        return levelups

    def _expected_spawn_count_per_frame(self, timer, interval):
        """1フレーム分のキャリーオーバー計算: timer を1進め、
        while timer >= interval: timer -= interval のループ回数を
        そのフレームの出現数として、(出現数, 更新後の timer) を返す。
        interval = 60/2^n と timer の値はいずれも2進小数で正確に表せる
        ため、浮動小数点の誤差は蓄積しない"""
        timer += 1
        spawn_count = 0
        while timer >= interval:
            timer -= interval
            spawn_count += 1
        return spawn_count, timer

    def _inject_rare_drop_on_player(self, field):
        """プレイヤー（速度0のため開始時の画面中央に固定）と画像中心を
        揃えて明確に重なるレアドロップを1個注入する
        （TestDropCountIncrementsOnCollect と同じ配置・注入パターン）。
        次の process_frame() で回収され、レア取得イベントが発生する"""
        collected_pos = (
            self.INITIAL_PLAYER_X + self.PLAYER_CENTER_OFFSET_X - Drop.WIDTH // 2,
            self.INITIAL_PLAYER_Y + self.PLAYER_CENTER_OFFSET_Y - Drop.HEIGHT // 2,
        )
        field._drops.append(  # pylint: disable=W0212
            Drop(
                collected_pos[0] + Drop.WIDTH / 2,
                collected_pos[1] + Drop.HEIGHT / 2,
                0,
                True,
            )
        )

    def test_spawn_interval_halves_on_rare_drop_levelup(self):
        # レア取得数 n = 0..MAX_RARE_COUNT の各フェーズで観測窓
        # MOB_SPAWN_INTERVAL（60）フレームを進め、毎フレームの累計出現数を
        # 照合する。interval(n) = 60/2^levelups(n) は常に窓 60 を割り切る
        # ため、1フェーズの出現数は 60 / interval(n) = 2^levelups(n) 体に
        # なり、フェーズの最終フレームで timer はちょうど 0 へ戻る（n=0 は
        # 窓の最終フレームに1体のみ＝変化なしの基準）
        window = Field.MOB_SPAWN_INTERVAL
        field = Field()
        # len(mob_states()) がそのまま累計出現数になるよう、出現以外で
        # モブ数が増減する要因を取り除く:
        # - 開始時の1匹は除去する（出現数の基準を0にする）
        # - 弾は検証期間中は発射させない（命中でモブが消滅するのを防ぐ。
        #   TestMobPeriodicSpawn と同じ抑止方法。弾がなければモブの撃破も
        #   起きず、乱数種別の新規ドロップも生成されない）
        # - プレイヤーは動かさない（カメラ・出現位置・消滅判定矩形が固定
        #   され、出現したモブは常にプレイヤーへ向かって追尾するため
        #   消滅領域の外へ出ることがない。注入するドロップの重なり位置も
        #   フェーズによらず開始時の画面中央のままになる）
        field._mobs = []  # pylint: disable=W0212
        field._player._speed = 0  # pylint: disable=W0212
        field._player._bullet_shoot_interval = (  # pylint: disable=W0212
            self.MAX_RARE_COUNT + 1
        ) * window + 1
        expected_total = 0
        timer = 0
        for rare_count in range(self.MAX_RARE_COUNT + 1):
            interval = Field.MOB_SPAWN_INTERVAL / 2 ** self._levelups_for_rare_count(
                rare_count
            )
            if rare_count > 0:
                # フェーズ先頭のフレームで回収され、同一フレーム内の処理順
                # （_collect_drops() → _try_spawn_mob()）により、そのフレーム
                # の出現判定から半減後の間隔が反映される
                self._inject_rare_drop_on_player(field)
            for frame in range(1, window + 1):
                field.process_frame()
                spawn_count, timer = self._expected_spawn_count_per_frame(
                    timer, interval
                )
                expected_total += spawn_count
                self.assertEqual(
                    expected_total,
                    len(field.mob_states()),
                    f"rare_count={rare_count}, frame={frame}",
                )


class TestGameClearAndGameOverState(TestParent):
    """レアドロップ累計が Field.RARE_DROP_CLEAR_TARGET（ゲームクリアに
    必要な累計数。requirements.md §3.7 の「規定値」を20に具体化した値）
    以上で is_game_clear が True になること、HP が0以下で is_game_over が
    True になること（ID-016 サイクル2）。しきい値の直前（19個/HP1）と
    ちょうど（20個/HP0）の境界値を含めて検証する。判定は Field 単体
    （Player への委譲）で完結するため、Field を直接生成し判定対象の状態
    （_player._rare_drop_count / _player._hp）のみを書き換える単体テスト
    とし、GameCore・TestView・TestParent の描画・入力モックは使わない
    （sort_water/ID-005 の Board.is_clear と同じ独立先行実装の考え方）"""

    def test_is_game_clear_false_below_target_true_at_and_above_target(self):
        cases = [
            (0, False),
            (Field.RARE_DROP_CLEAR_TARGET - 1, False),
            (Field.RARE_DROP_CLEAR_TARGET, True),
            (Field.RARE_DROP_CLEAR_TARGET + 1, True),
        ]
        for rare_count, expected in cases:
            with self.subTest(rare_count=rare_count):
                field = Field()
                field._player._rare_drop_count = rare_count  # pylint: disable=W0212
                self.assertEqual(expected, field.is_game_clear)

    def test_is_game_over_false_above_zero_true_at_and_below_zero(self):
        cases = [
            (Player.INITIAL_HP, False),
            (1, False),
            (0, True),
            (-1, True),
        ]
        for hp, expected in cases:
            with self.subTest(hp=hp):
                field = Field()
                field._player._hp = hp  # pylint: disable=W0212
                self.assertEqual(expected, field.is_game_over)


class TestFieldStopsWhenGameEnd(TestParent):
    """ゲーム終了（クリア／オーバー）到達後のフィールド進行停止（ID-016
    サイクル3・4。IF: Field.process_frame()/set_click() の終了時ガード）

    仕様（このテストで固定する）:
    - is_game_clear または is_game_over が真の間は、process_frame() を
      何度呼んでもフィールドの状態（プレイヤー位置・回転、全モブ・弾・
      ドロップ、目的地）が一切変化しない（ゲームの進行が止まる）
    - is_game_clear または is_game_over が真の間は、set_click() も
      無視される（目的地の設定・方向転換が起こらない）

    ゲームの進行状態は Field 自身の関心事のため、結線（GameCore.update()）
    の e2e テストではなく Field の公開 IF に対する単体テストとして検証する
    （人間レビュー指摘による責務配置。ポップアップ押下によるリセットは
    ID-017 のスコープ）。クリア・ゲームオーバー判定の条件自体（境界値）は
    TestGameClearAndGameOverState で固定済みのため、レアドロップ累計・HP を
    直接注入して終了状態を作る。

    クリア・オーバーの2ケースは「終了状態を作る注入方法」だけが異なり、
    検証内容（process_frame()/set_click() が状態を変えないこと）は完全に
    同型のため、サブテストで両ケースをまとめて検証する（当初 ID-016-9〜11
    でクリアのみを対象に TestFieldStopsWhenGameClear として実装し、
    ID-016-12〜13 でゲームオーバーのケースを同型のまま TestFieldStopsWhenGameOver
    として追加した2クラスを、ID-016-14 の Refactor で人間レビュー指摘に
    より本クラスへ統合した）"""

    # 進行停止を確認するフレーム数。PLAYER_SPEED（0.5）との積が整数
    # （5px）になる値のため、ガードなしの誤実装では前進が必ず座標の変化
    # として観測できる
    STOP_CHECK_FRAMES = 10

    def _state_snapshot(self, field):
        """フィールドの観測可能な状態（プレイヤー位置・回転、全モブ、全弾、
        全ドロップ、目的地）を公開 IF から取得して返す。各 IF は呼び出し
        ごとに新しいタプル・リストを返すため、そのまま比較用のスナップ
        ショットとして保持できる"""
        return (
            field.player_state(),
            field.mob_states(),
            field.bullet_states(),
            field.drop_states(),
            field.destination,
        )

    def _make_game_clear_field(self):
        field = Field()
        field._player._rare_drop_count = (  # pylint: disable=W0212
            Field.RARE_DROP_CLEAR_TARGET
        )
        return field

    def _make_game_over_field(self):
        field = Field()
        field._player._hp = 0  # pylint: disable=W0212
        return field

    def _game_end_field_factories(self):
        """終了状態（クリア／オーバー）ごとの Field 生成関数を
        (ラベル, 生成関数) の組で返す。サブテストのラベル・アサーション
        メッセージにそのまま使う"""
        return [
            ("game_clear", self._make_game_clear_field),
            ("game_over", self._make_game_over_field),
        ]

    def test_process_frame_does_not_change_field_state_when_game_end(self):
        """終了状態（クリア／オーバーそれぞれ）で process_frame() を複数
        フレーム呼んでも、フィールドの状態が呼び出し前とまったく同じで
        あること（ガードなしの誤実装ではプレイヤーの前進・モブの追尾移動が
        起こりスナップショットが一致しなくなる）"""
        for label, make_field in self._game_end_field_factories():
            with self.subTest(state=label):
                field = make_field()
                snapshot = self._state_snapshot(field)
                for _ in range(self.STOP_CHECK_FRAMES):
                    field.process_frame()
                self.assertEqual(
                    snapshot,
                    self._state_snapshot(field),
                    f"{label} 後の process_frame() でフィールドの状態が変化した",
                )

    def test_set_click_is_ignored_when_game_end(self):
        """終了状態（クリア／オーバーそれぞれ）では set_click() が
        無視されること（目的地が設定されず、プレイヤーの向き
        〔player_state の回転角度〕も変わらない。ガードなしの誤実装では
        目的地の記録と turn_to による方向転換が起こる）"""
        for label, make_field in self._game_end_field_factories():
            with self.subTest(state=label):
                field = make_field()
                snapshot = self._state_snapshot(field)
                # プレイヤー中心点から右方向のワールド座標をクリックする
                # （進行方向の初期値＝真上から必ず変わる位置のため、方向
                # 転換が起きれば回転角度の変化として観測できる）
                self._click_at(
                    field, (self.INITIAL_PLAYER_X, self.INITIAL_PLAYER_Y), (40, 0)
                )
                self.assertEqual(
                    snapshot,
                    self._state_snapshot(field),
                    f"{label} 後の set_click() でフィールドの状態が変化した",
                )


if __name__ == "__main__":
    unittest.main()
