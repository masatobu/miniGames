import math
import unittest
from src.main import Actor, Mob, MoveMode, Player


class TestActorTurnTo(unittest.TestCase):
    """Actor.turn_to() の単体テスト（Pyxel・GameCore 非依存。Player/Mob 共通の移動ロジック）

    方向の基準点（このテストで固定する仕様）: Actor のコンストラクタに渡す
    x/y は画像の中心点（登録座標＝スプライト左上ではない）のワールド座標
    であり、turn_to() はこの中心点を基準に目的地への方向を計算する
    （プレイヤーの見た目の中心がタップ位置＝目的地へ向かって移動し、
    到着時に目的地の旗の根本と一致するため）
    """

    SPEED = 2
    WIDTH = 8
    HEIGHT = 8

    def _expected_pos(self, start, diff, frames):
        # 進行方向は目的地ワールド座標と中心点の差分ベクトル diff を
        # 正規化した単位ベクトル。内部位置（中心点）は少数のまま保持・蓄積し、
        # x/y の参照時に四捨五入した整数を返す仕様のため、期待値も
        # 「開始座標 + フレーム数 × 速度 × 単位ベクトル」を丸めて求める
        dist = math.hypot(*diff)
        return (
            round(start[0] + frames * self.SPEED * diff[0] / dist),
            round(start[1] + frames * self.SPEED * diff[1] / dist),
        )

    def test_advance_moves_toward_turned_direction(self):
        """turn_to(ワールド座標) を呼ぶと、以降の advance() でその座標の
        方向へ毎フレーム速度分だけ前進すること（フレーム0＝turn_to 直後は
        位置が変わらないことを含む）。内部位置は少数で蓄積されるため、x/y
        が整数返却でもフレームを重ねることで任意方向への移動が実現される
        （x/y が int 型で返却されることも併せて検証する）"""
        start = (10, 20)
        test_cases = [
            # (名前, 中心点から目的地への差分, フレーム数)
            # 差分は 3:4:5 の直角三角形になる値を使い、単位ベクトル
            # (0.6, 0.8) × 速度 2 = 毎フレーム (1.2, 1.6) の少数移動を生じさせる
            ("turn_to 直後（フレーム0）は移動しない", (30, 40), 0),
            ("右方向（x軸沿い）", (30, 0), 3),
            ("右下 3:4 方向・1フレーム（少数位置の丸め）", (30, 40), 1),
            ("右下 3:4 方向・5フレーム（少数の蓄積で整数へ到達）", (30, 40), 5),
            ("左上 3:4 方向（負方向への蓄積）", (-30, -40), 5),
        ]
        for name, diff, frames in test_cases:
            with self.subTest(name):
                actor = Actor(*start, self.SPEED, self.WIDTH, self.HEIGHT)
                actor.turn_to(start[0] + diff[0], start[1] + diff[1])

                for _ in range(frames):
                    actor.advance()

                self.assertIsInstance(actor.x, int)
                self.assertIsInstance(actor.y, int)
                self.assertEqual(
                    self._expected_pos(start, diff, frames),
                    (actor.x, actor.y),
                )

    def test_turn_to_own_center_keeps_previous_direction(self):
        """自身の中心点と同一座標へ turn_to() しても例外を起こさず、直前の
        進行方向のまま前進し続けること"""
        start = (10, 20)
        actor = Actor(*start, self.SPEED, self.WIDTH, self.HEIGHT)
        actor.turn_to(start[0] + 30, start[1] + 40)

        actor.turn_to(*start)
        actor.advance()

        expected = self._expected_pos(start, (30, 40), 1)
        self.assertEqual(expected, (actor.x, actor.y))


class TestActorRotateAngle(unittest.TestCase):
    """Actor.rotate_angle の単体テスト（Pyxel・GameCore 非依存。Player/Mob 共通の移動ロジック）

    回転角度の規約（このテストで固定する仕様）:
    - 単位: 度数法（IView.draw_blt の rotate 引数へそのまま渡せる値とする）
    - 0度: 上方向（スプライトの基準向き＝Actor の初期進行方向）
    - 正方向: スクリーン上の時計回り（上→右が +90度）
    - 範囲: -180度 < angle <= 180度
    - 丸めは行わず連続値を返す（弾の発射方向など正確な角度が必要な用途で
      使われるため）。描画時に8/16方向へスナップする処理は GameCore 側の
      責務とする（GameCore._snap_rotate_angle()。test_main.py で検証）

    方向の基準点は中心点（コンストラクタに渡す x/y そのもの。TestActorTurnTo
    で固定した仕様）のため、目的地はその座標からの差分で指定する
    """

    SPEED = 2
    START = (10, 20)
    WIDTH = 8
    HEIGHT = 8

    def test_initial_rotate_angle_is_zero(self):
        """turn_to() 前の初期状態では、初期進行方向（上方向）に対応する
        0度を返すこと（回転なしの現行描画と同一になる）"""
        actor = Actor(*self.START, self.SPEED, self.WIDTH, self.HEIGHT)

        self.assertAlmostEqual(0, actor.rotate_angle)

    def test_rotate_angle_follows_turned_direction(self):
        """turn_to(ワールド座標) 後は、進行方向に対応する角度
        （上方向を0度とするスクリーン上時計回りの度数）を返すこと"""
        test_cases = [
            # (名前, 中心点から目的地への差分, 期待角度)
            # 差分は軸沿いの値、および 3:4:5 の直角三角形になる値を使う
            ("上方向は 0 度", (0, -40), 0),
            ("右方向は +90 度", (30, 0), 90),
            ("下方向は 180 度", (0, 30), 180),
            ("左方向は -90 度", (-30, 0), -90),
            # 右（+90度）からさらに時計回りへ atan2(4, 3) だけ回った方向
            ("右下 3:4 方向", (30, 40), 90 + math.degrees(math.atan2(4, 3))),
        ]
        for name, diff, expected in test_cases:
            with self.subTest(name):
                actor = Actor(*self.START, self.SPEED, self.WIDTH, self.HEIGHT)
                actor.turn_to(self.START[0] + diff[0], self.START[1] + diff[1])

                self.assertAlmostEqual(expected, actor.rotate_angle)


class TestPlayerShoot(unittest.TestCase):
    """Player.shoot() の単体テスト（Pyxel・Field 非依存）

    仕様: 発射間隔（Player.BULLET_SHOOT_INTERVAL）のタイマーは、「1フレーム
    経過」を表す advance()（前進処理）の呼び出しごとに進む。shoot() は
    毎フレーム呼び出される想定で、そのタイマーが発射間隔に達していれば
    その時点の自身（プレイヤー）の中心点・向きを引き継いだ弾を1発以上
    含むリストを返してタイマーをリセットし、達していなければ空リストを
    返すのみで、それ自体はタイマーを進めない（呼び出し側はこの返却値を
    そのまま自身の弾リストへ追加していく想定で、発射契機の判定自体は
    Player の外に持たない）。返却された弾は生成後、自身の向きを変更する
    手段を持たないため、以後プレイヤーが向きを変えても既に返却済みの弾
    には影響しない
    """

    SPEED = 2
    START = (10, 20)

    def test_bullets_are_returned_only_on_shoot_interval_advances(self):
        """advance() の呼び出し回数が発射間隔に達したフレームでのみ弾
        （を含むリスト）が返ること（間隔経過の直前までは1度も発射されず、
        間隔の経過ごとに1回ずつ発射され続けることを、"1フレーム" ＝
        advance() + shoot() の対の累積回数で検証する）"""
        interval = Player.BULLET_SHOOT_INTERVAL
        test_cases = [
            ("間隔経過の直前までは1度も発射されない", interval - 1, 0),
            ("間隔の経過で1回発射される", interval, 1),
            ("間隔の2回目の経過で2回目が発射される", 2 * interval, 2),
        ]
        for name, frame_count, expected_fire_count in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)

                fire_count = 0
                for _ in range(frame_count):
                    player.advance()
                    if player.shoot():
                        fire_count += 1

                self.assertEqual(expected_fire_count, fire_count)

    def test_fired_bullets_reflect_player_position_and_direction_at_fire_time(self):
        """発射された弾は、要素数1以上のリストとして返り、各弾の位置・
        向きがその時点の自身（プレイヤー）の中心点・向きと一致すること
        （前進・方向転換した後に発射しても、発射時点の最新の状態が
        引き継がれること）"""
        player = Player(*self.START, self.SPEED)
        player.turn_to(player.x + 30, player.y)  # 右（90度）へ方向転換
        interval = Player.BULLET_SHOOT_INTERVAL

        for _ in range(interval - 1):
            player.advance()
            player.shoot()
        player.advance()
        fired = player.shoot()

        self.assertGreaterEqual(len(fired), 1)
        for bullet in fired:
            self.assertEqual((player.x, player.y), (bullet.x, bullet.y))
            self.assertAlmostEqual(player.rotate_angle, bullet.rotate_angle)

    def test_player_turn_after_fire_does_not_affect_already_fired_bullet(self):
        """発射後にプレイヤーが向きを変えても、既に返却済みの弾の向きには
        影響しないこと"""
        player = Player(*self.START, self.SPEED)
        interval = Player.BULLET_SHOOT_INTERVAL

        for _ in range(interval - 1):
            player.advance()
            player.shoot()
        player.advance()
        # この呼び出し時点のプレイヤーの向きは初期の進行方向（真上=0度）
        fired = player.shoot()

        player.turn_to(player.x + 30, player.y)  # 発射後に右（90度）へ方向転換

        self.assertAlmostEqual(0, fired[0].rotate_angle)


class TestPlayerNormalDropCount(unittest.TestCase):
    """Player の通常ドロップ累計取得数の保持・取得の単体テスト（Pyxel・Field
    非依存）。加算専用の公開メソッド add_normal_drop_count() と読み取り
    専用プロパティ normal_drop_count の名称・シグネチャをここで決定する。
    累計値が成長（発射頻度・発射方向数など）へ及ぼす効果は関心が別のため
    扱わず、専用クラス（TestPlayerNormalDropGrowthShootFrequency 等）で
    検証する（他の累計状態プロパティ（HP・レアドロップ数など）が今後
    追加された場合も、保持・取得自体の検証は同様に専用クラスへ分離する
    想定）
    """

    SPEED = 2
    START = (10, 20)

    def test_add_normal_drop_count_increments_public_property(self):
        """add_normal_drop_count() を呼んだ回数がそのまま公開プロパティ
        normal_drop_count に反映されること（0回＝初期値0を含む）"""
        test_cases = [
            ("0回（初期値）", 0, 0),
            ("1回", 1, 1),
            ("5回", 5, 5),
        ]
        for name, call_count, expected in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)

                for _ in range(call_count):
                    player.add_normal_drop_count()

                self.assertEqual(expected, player.normal_drop_count)


class TestPlayerNormalDropGrowthShootFrequency(unittest.TestCase):
    """通常ドロップの累計取得数による発射頻度の成長（レベル1〜3）の単体テスト
    （Pyxel・Field 非依存。Field との結線はここでは扱わない）

    仕様: 通常ドロップの累計取得数がしきい値 10×(2^L−1)（L=1,2,3）へ達する
    たびに発射間隔が半減する（頻度2倍→4倍→8倍。Player.BULLET_SHOOT_INTERVAL
    に対する倍率 f(L) = 2^L）。発射頻度の成長はレベル3で打ち止めであり
    （f(L) = 2^min(L, 3)）、成長の上限（レベル8・累計2550個）を超えて
    しきい値の倍増系列の次の値（10×(2^9−1) = 5110個）まで取得しても、
    間隔3.75のまま変化しない（成長上限）。累計値の加算・取得の公開IF
    （add_normal_drop_count()／normal_drop_count）自体の検証は
    TestPlayerNormalDropCount で行うため、ここでは成長効果の検証に絞る。

    端数間隔（7.5, 3.75）の実効周期: 発射時にタイマーを0へリセットするので
    はなく余りを繰り越す仕様とする（リセット方式だと実効周期が
    ceil(interval) になり、平均発射頻度が「正確に2倍」からずれるため）。
    このテストでは、発射間隔で割り切れる共通のフレーム数（基準間隔30と
    一致する30フレーム）の窓で発射回数を検証することで、繰り越し方式
    （期待どおりの回数）とリセット方式（回数が不足する）を区別する。
    """

    SPEED = 2
    START = (10, 20)

    @staticmethod
    def _threshold(level):
        # 累計しきい値 = 10 x (2^level - 1)（レベル level に達するために
        # 必要な累計取得数。増分方式のしきい値を累計値へ読み替えた式）
        return 10 * (2**level - 1)

    def test_shoot_frequency_grows_with_cumulative_normal_drop_count(self):
        """累計取得数がしきい値へ達するたびに発射間隔が半減し（頻度2倍→
        4倍→8倍）、しきい値未満では変化しないこと（境界値）、および成長の
        上限（レベル8・累計2550個）を超えて取得しても間隔3.75のまま変化
        しないこと（成長上限）を、基準間隔と一致する30フレームの窓での
        発射回数で検証する"""
        base_interval = Player.BULLET_SHOOT_INTERVAL  # 30
        frame_count = base_interval  # 30, 15, 7.5, 3.75 いずれでも割り切れる窓
        test_cases = [
            # (名前, 累計取得数, 30フレーム窓での期待発射回数)
            (
                "累計9個(しきい値10未満): 間隔30のまま(境界値)",
                self._threshold(1) - 1,
                1,
            ),
            ("累計10個(レベル1): 間隔15(頻度2倍)", self._threshold(1), 2),
            ("累計30個(レベル2): 間隔7.5(頻度4倍)", self._threshold(2), 4),
            ("累計70個(レベル3): 間隔3.75(頻度8倍)", self._threshold(3), 8),
            # 成長の上限(レベル8・累計2550個)を超えて、しきい値の倍増系列の
            # 次の値(10×(2^9−1) = 5110個)まで取得しても頻度は8倍のまま
            (
                "累計5110個(倍増系列の次の値): 間隔3.75のまま(成長上限)",
                self._threshold(9),
                8,
            ),
        ]
        for name, cumulative, expected_shots in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)
                for _ in range(cumulative):
                    player.add_normal_drop_count()

                fire_count = 0
                for _ in range(frame_count):
                    player.advance()
                    if player.shoot():
                        fire_count += 1

                self.assertEqual(expected_shots, fire_count)


class TestPlayerNormalDropGrowthMultiDirectionShoot(unittest.TestCase):
    """通常ドロップの累計取得数による多方向発射の成長（レベル4〜8）の
    単体テスト（Pyxel・Field 非依存。Field との結線はここでは扱わない）

    仕様: 累計取得数がしきい値 10×(2^L−1)（L=4〜8 → 150/310/630/1270/2550
    個）へ達するたびに、shoot() は1回の発射で n(L) = 2^(L−3) + 1 発
    （3/5/9/17/33発）を、進行方向を中心とした広がり角
    θ(L) = min(30×2^(L−4), 360) 度（30/60/120/240/360度）の扇へ返す
    （n は奇数のため、進行方向（相対角度0度）と一致する弾を必ず1発含む）。
    しきい値未満（累計149個）では従来どおり進行方向へ1発のまま変化しない
    （境界値）。成長の上限はレベル8（累計2550個）であり、超えてしきい値の
    倍増系列の次の値（10×(2^9−1) = 5110個）まで取得しても33発・全周の
    まま変化しない（成長上限）。発射頻度はレベル3までで打ち止め
    （f(L) = 2^min(L, 3)）のため、レベル4以降では間隔 3.75 のまま
    変わらない（間隔の検証はサイクル1・4 の担当のためここでは扱わない）。

    弾の向きの期待値の導出（テスト期待値決定ガイドの方針）:
    - 相対角度列（進行方向からの度数）は、θ < 360 では −θ/2 から
      θ/(n−1) 度間隔で n 発（両端を含む対称配置。n が奇数のため中央
      （k=(n−1)/2）が進行方向そのもの（0度）になる）、θ = 360 では両端
      （±180度）が一致するため k×360/n 度間隔で n 発の全周等間隔配置
      （k=0 が進行方向）の計算式で導出する。shoot() の返却リストはこの
      相対角度列の順とする
    - 各弾の向きは「進行方向の角度 + 相対角度」を rotate_angle と同じ角度
      規約（度数法、0度=上方向、時計回りが正）で単位ベクトル
      (sin(rad), −cos(rad)) へ変換した計算式で導出し、浮動小数のため
      近似比較とする
    """

    SPEED = 2
    START = (100, 100)
    # 進行方向の回転が弾の向きへ正しく反映されることを検証するため、
    # 軸沿いでない向き（右下 3:4 方向 = 90 + atan2(4, 3) 度）を使う
    FACING_ANGLE = 90 + math.degrees(math.atan2(4, 3))

    @staticmethod
    def _threshold(level):
        # 累計しきい値 = 10 x (2^level - 1)（レベル level に達するために
        # 必要な累計取得数。増分方式のしきい値を累計値へ読み替えた式）
        return 10 * (2**level - 1)

    @staticmethod
    def _direction_of(angle_deg):
        # 角度（rotate_angle と同じ規約）→ 進行方向の単位ベクトル。
        # rotate_angle の逆変換（0度=上方向 (0, -1) を時計回りへ回す）
        rad = math.radians(angle_deg)
        return math.sin(rad), -math.cos(rad)

    def _fire_once(self, player):
        # 最初の発射までフレーム（advance() + shoot() の対）を進め、その
        # 1回分の返却リストを返す。発射間隔は最長でも基準間隔のため、
        # 基準間隔のフレーム数以内に必ず1回は発射される
        for _ in range(Player.BULLET_SHOOT_INTERVAL):
            player.advance()
            fired = player.shoot()
            if fired:
                return fired
        return self.fail("基準間隔のフレーム数以内に発射されなかった")

    @staticmethod
    def _relative_angles(level):
        # レベル level (4〜8) の効果: n = 2^(level−3) + 1 方向
        # （奇数のため進行方向（0度）と一致する弾を必ず1発含む）、
        # 広がり角 theta = min(30×2^(level−4), 360) 度
        n = 2 ** (level - 3) + 1
        theta = min(30 * 2 ** (level - 4), 360)
        if theta < 360:
            # −θ/2 から θ/(n−1) 度間隔で n 発（両端を含む対称配置。
            # n が奇数のため中央（k=(n−1)/2）が0度=進行方向になる）
            return [-theta / 2 + k * theta / (n - 1) for k in range(n)]
        # 全周（θ = 360）は両端（±180度）が一致するため、
        # k×360/n 度間隔で n 発の全周等間隔配置（k=0 が進行方向）
        return [k * 360 / n for k in range(n)]

    def test_bullets_spread_widens_from_level4_to_level8_thresholds(self):
        """累計150/310/630/1270/2550個(レベル4〜8)で1回の発射が
        3/5/9/17/33発・広がり角30/60/120/240/360度になること(360度のみ
        全周等間隔配置)、各レベルとも進行方向(相対角度0度)と一致する弾を
        1発含むこと、累計149個では進行方向へ1発のまま変化しないこと
        (境界値)、および成長の上限(レベル8・累計2550個)を超えて取得しても
        33発・全周のまま変化しないこと(成長上限)"""
        test_cases = [
            # (名前, 累計取得数, 期待する相対角度列(進行方向からの度数))
            (
                "累計149個(しきい値150未満): 進行方向へ1発のまま(境界値)",
                self._threshold(4) - 1,
                [0.0],
            ),
            (
                "累計150個(レベル4): 3発、広がり角30度(−15/0/+15度)",
                self._threshold(4),
                self._relative_angles(4),
            ),
            (
                "累計310個(レベル5): 5発、広がり角60度(15度間隔・0度を含む)",
                self._threshold(5),
                self._relative_angles(5),
            ),
            (
                "累計630個(レベル6): 9発、広がり角120度(15度間隔・0度を含む)",
                self._threshold(6),
                self._relative_angles(6),
            ),
            (
                "累計1270個(レベル7): 17発、広がり角240度(15度間隔・0度を含む)",
                self._threshold(7),
                self._relative_angles(7),
            ),
            (
                "累計2550個(レベル8): 33発、全周360度(360/33度間隔・0度を含む)",
                self._threshold(8),
                self._relative_angles(8),
            ),
            (
                # 成長の上限(レベル8)を超えて、しきい値の倍増系列の次の値
                # (10×(2^9−1) = 5110個)まで取得しても強化されない
                "累計5110個(倍増系列の次の値): 33発・全周のまま(成長上限)",
                self._threshold(9),
                self._relative_angles(8),
            ),
        ]
        for name, cumulative, relative_angles in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)
                dir_x, dir_y = self._direction_of(self.FACING_ANGLE)
                player.turn_to(self.START[0] + dir_x, self.START[1] + dir_y)
                for _ in range(cumulative):
                    player.add_normal_drop_count()

                fired = self._fire_once(player)

                # 進行方向(相対角度0度)と一致する弾が必ず1発含まれること
                # （θ<360 は n が奇数のため中央が0度、θ=360 は k=0 が0度。
                # いずれも計算式の導出値が正確に 0.0 になる: θ<360 の間隔
                # θ/(n−1) = 30×2^(L−4) / 2^(L−3) = 15 度で中央 −θ/2+((n−1)/2)×15
                # は整数演算、θ=360 は k=0 の項）
                self.assertIn(0.0, relative_angles)
                self.assertEqual(len(relative_angles), len(fired))
                for relative, bullet in zip(relative_angles, fired):
                    expected_dir = self._direction_of(self.FACING_ANGLE + relative)
                    for axis, expected, actual in zip(
                        "xy", expected_dir, bullet.direction
                    ):
                        self.assertAlmostEqual(
                            expected,
                            actual,
                            msg=f"相対角度 {relative} 度の弾の向き（{axis} 成分）",
                        )


class TestPlayerHpAndRareDropCount(unittest.TestCase):
    """Player の HP・レアドロップ累計取得数の保持・取得の単体テスト（Pyxel・
    Field 非依存）。読み取り専用プロパティ hp／rare_drop_count と、レア
    ドロップ加算専用の公開メソッド add_rare_drop_count()、HP減少専用の
    公開メソッド decrease_hp() の名称・シグネチャをここで決定する
    （TestPlayerNormalDropCount と同様、累計状態プロパティの保持・取得
    自体の検証を専用クラスへ分離する方針を踏襲）
    """

    SPEED = 2
    START = (10, 20)

    def test_hp_starts_at_initial_hp(self):
        """生成直後の hp プロパティが、既定の初期値（Player.INITIAL_HP）で
        あること（HP初期値の定数は Refactor（ID-013-20）で Player を単一の
        情報源とし、未使用になった Field.INITIAL_HP は削除した）"""
        player = Player(*self.START, self.SPEED)

        self.assertEqual(Player.INITIAL_HP, player.hp)

    def test_rare_drop_count_starts_at_zero_and_increments_on_add(self):
        """生成直後の rare_drop_count プロパティが0であり、
        add_rare_drop_count() を呼んだ回数がそのまま反映されること
        （0回＝初期値0を含む）"""
        test_cases = [
            ("0回（初期値）", 0, 0),
            ("1回", 1, 1),
            ("5回", 5, 5),
        ]
        for name, call_count, expected in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)

                for _ in range(call_count):
                    player.add_rare_drop_count()

                self.assertEqual(expected, player.rare_drop_count)

    def test_hp_decreases_by_call_count_on_decrease_hp(self):
        """decrease_hp() を呼んだ回数分、hp が初期値から減ること（1回呼ぶと
        1減り、複数回呼ぶと呼んだ回数分減る）"""
        test_cases = [
            ("1回", 1),
            ("3回", 3),
        ]
        for name, call_count in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)

                for _ in range(call_count):
                    player.decrease_hp()

                self.assertEqual(Player.INITIAL_HP - call_count, player.hp)


class TestPlayerInvincibility(unittest.TestCase):
    """Player の無敵タイマー（is_invincible／tick_invincibility()／
    start_invincibility()）の単体テスト（Pyxel・Field 非依存）。ID-015-10
    の Refactor で `Field` から `Player` へ移した状態。無敵中かどうかの
    参照（is_invincible）と、タイマーの消費（tick_invincibility()）は
    別メソッドに分離する（無敵状態の参照だけを行いたい呼び出し元（無敵中の
    点滅描画など、今後のサイクルで追加予定）が、参照のたびにタイマーを
    消費してしまわないようにするため）。

    仕様: start_invincibility() を呼ぶと無敵タイマーが
    Player.INVINCIBLE_FRAMES にセットされる。is_invincible はタイマーが
    残っているか（副作用なし）を返す。tick_invincibility() は呼ばれる
    たびにタイマーを1減らす（呼び出し側は is_invincible で無敵中である
    ことを確認してから呼ぶ想定で、TestPlayerShoot の発射間隔タイマーと
    同様「1フレーム経過」をこの呼び出し自体で表す）
    """

    SPEED = 2
    START = (10, 20)

    def test_is_invincible_starts_false(self):
        """生成直後（一度も start_invincibility() を呼んでいない）は
        is_invincible が False であること"""
        player = Player(*self.START, self.SPEED)

        self.assertFalse(player.is_invincible)

    def test_is_invincible_is_true_before_tick_invincibility_exhausts_frames(self):
        """start_invincibility() 直後から、tick_invincibility() を
        INVINCIBLE_FRAMES 未満回呼んだ間（無敵時間の最終フレームまで）は
        is_invincible が True のままであること（TestPlayerShoot の
        interval 境界テストと同様、呼び出し回数の境界をパラメータ化する）"""
        test_cases = [
            ("start_invincibility() 直後（tick 0回）", 0),
            (
                "無敵時間の最終フレーム（tick INVINCIBLE_FRAMES-1回）",
                Player.INVINCIBLE_FRAMES - 1,
            ),
        ]
        for name, tick_count in test_cases:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)
                player.start_invincibility()

                for _ in range(tick_count):
                    player.tick_invincibility()

                self.assertTrue(player.is_invincible)

    def test_is_invincible_becomes_false_after_tick_invincibility_exhausts_frames(self):
        """start_invincibility() 後、tick_invincibility() を
        INVINCIBLE_FRAMES 回呼ぶと（無敵時間の経過後）is_invincible が
        False になること"""
        player = Player(*self.START, self.SPEED)
        player.start_invincibility()

        for _ in range(Player.INVINCIBLE_FRAMES):
            player.tick_invincibility()

        self.assertFalse(player.is_invincible)


class TestPlayerHitback(unittest.TestCase):
    """Player.hitback_from()／advance() のヒットバック分岐／is_in_hitback
    の単体テスト（Pyxel・Field 非依存。ID-015 サイクル5・6）。
    test_field.py の TestPlayerHitbackOnMobContact は「モブとの接触から
    ヒットバックが起動されること」を Field 経由で検証する統合テストの
    ため、ここでは起動されたヒットバック自体の振る舞い（移動量・向き・
    継続フレーム数・is_in_hitback の推移・発射間隔タイマーへの影響）を
    Player 単体で固定する（TestPlayerHpAndRareDropCount・
    TestPlayerInvincibility と同じ分業）。

    仕様: hitback_from(world_x, world_y) を呼ぶと、指定座標（接触した
    モブの中心）の方向を向き（advance() 中も向きは変えない）、その反対
    方向へ HITBACK_FRAMES フレームかけて合計 HITBACK_DISTANCE だけ移動する
    （呼び出し自体が1フレーム目の移動を兼ね、以降 advance() を呼ぶたびに
    1フレーム分ずつ進む。kフレーム目までの合計変位は
    HITBACK_DISTANCE × k / HITBACK_FRAMES）。ヒットバック中の advance()
    は通常の前進（進行方向への移動）を行わない。is_in_hitback は
    hitback_from() 直後から HITBACK_FRAMES 番目の advance() 呼び出しが
    完了するまで True で、その時点で False になる（HITBACK_FRAMES 未満の
    経過ではまだ True のまま）。発射間隔のタイマーは advance() の
    呼び出し自体で進むため、ヒットバック中でも滞らない
    （Player.advance() の分岐は前進処理のみを切り替え、タイマー加算は
    分岐の外で毎回行う実装）"""

    SPEED = 2
    START = (10, 20)
    # 中心点からの差分。他クラスと同じ 3:4:5 の直角三角形になる値
    DIFF = (30, 40)

    def _expected_hitback_pos(self, elapsed_frames):
        # 開始座標 − (HITBACK_DISTANCE × 経過フレーム数 / HITBACK_FRAMES) ×
        # 単位ベクトル（DIFF の正規化）を丸めて求める（DIFF 方向＝ヒット
        # した対象への方向のため、ヒットバックはその反対＝マイナス方向）
        dist = math.hypot(*self.DIFF)
        moved = Player.HITBACK_DISTANCE * elapsed_frames / Player.HITBACK_FRAMES
        return (
            round(self.START[0] - moved * self.DIFF[0] / dist),
            round(self.START[1] - moved * self.DIFF[1] / dist),
        )

    def test_hitback_faces_target_and_moves_away_gradually_over_frames(self):
        """hitback_from() 直後から HITBACK_FRAMES 番目の advance() 完了
        までの各フレームで、位置が反対方向への等分移動の計算式どおりに
        なり、向きは指定座標の方向を向いたまま変わらないこと。
        is_in_hitback は最終フレーム（HITBACK_FRAMES 番目）でのみ False に
        なること（1フレームで移動し切らない仕様の前提として HITBACK_FRAMES
        が2以上であることもあわせて確認する）"""
        self.assertGreater(Player.HITBACK_FRAMES, 1)
        player = Player(*self.START, self.SPEED)
        expected_angle = math.degrees(math.atan2(self.DIFF[0], -self.DIFF[1]))

        player.hitback_from(self.START[0] + self.DIFF[0], self.START[1] + self.DIFF[1])

        for elapsed in range(1, Player.HITBACK_FRAMES + 1):
            with self.subTest(elapsed=elapsed):
                self.assertEqual(
                    self._expected_hitback_pos(elapsed), (player.x, player.y)
                )
                self.assertAlmostEqual(expected_angle, player.rotate_angle)
                self.assertEqual(elapsed < Player.HITBACK_FRAMES, player.is_in_hitback)
            if elapsed < Player.HITBACK_FRAMES:
                player.advance()

    def test_hitback_from_own_center_does_not_start_hitback(self):
        """自身の中心点と同一座標へ hitback_from() しても例外を起こさず、
        直前の進行方向を維持したまま位置も変化せず、is_in_hitback も
        False のままであること（turn_to() のゼロ距離ガードと同型の
        振る舞い）"""
        player = Player(*self.START, self.SPEED)
        initial_angle = player.rotate_angle

        player.hitback_from(*self.START)

        self.assertFalse(player.is_in_hitback)
        self.assertEqual(
            (round(self.START[0]), round(self.START[1])), (player.x, player.y)
        )
        self.assertAlmostEqual(initial_angle, player.rotate_angle)

    def test_shoot_interval_timer_advances_during_hitback(self):
        """ヒットバック中（advance() が通常の前進をスキップしている間）
        でも、発射間隔のタイマーは advance() の呼び出しごとに進み続け、
        BULLET_SHOOT_INTERVAL 回の advance() 呼び出しで発射契機に達する
        こと（TestPlayerShoot.test_bullets_are_returned_only_on_shoot_
        interval_advances と同じ境界の検証を、ヒットバック中に対して
        行う）"""
        player = Player(*self.START, self.SPEED)
        player.hitback_from(self.START[0] + self.DIFF[0], self.START[1] + self.DIFF[1])
        interval = Player.BULLET_SHOOT_INTERVAL

        for _ in range(interval - 1):
            player.advance()
        self.assertEqual([], player.shoot())

        player.advance()

        self.assertNotEqual([], player.shoot())


class TestPlayerMoveMode(unittest.TestCase):
    """Player の移動モード（MoveMode）の保持・取得の単体テスト（Pyxel・Field
    非依存）。設定専用メソッド set_move_mode() と読み取り専用プロパティ
    move_mode の名称・シグネチャをここで決定する（IF を setter と getter に
    分けるのは TestPlayerInvincibility の start_invincibility()／
    is_invincible と同型。副作用のある操作と参照専用の取得を1メソッドに
    混ぜない既存方針に倣う）。モードが挙動へ及ぼす効果（自動収集モードでの
    攻撃停止など）は関心が別のため扱わず、専用クラス
    （TestPlayerShootInMoveMode 等）で検証する（TestPlayerNormalDropCount・
    TestPlayerHpAndRareDropCount と同じ、保持・取得自体の検証を専用クラスへ
    分離する方針を踏襲）
    """

    SPEED = 2
    START = (10, 20)

    # (ケース名, set_move_mode() で設定するモード〔None は呼ばない〕,
    #  move_mode プロパティの期待値)
    SET_MODE_AND_EXPECTED_MODE = [
        ("未設定（既定値）", None, MoveMode.ATTACK),
        ("自動収集モードを設定", MoveMode.COLLECT, MoveMode.COLLECT),
    ]

    def test_move_mode_returns_default_or_value_set_by_set_move_mode(self):
        """生成直後の move_mode が既定値の MoveMode.ATTACK（自動戦闘、
        requirements.md §3.1）であり、set_move_mode() で設定した値が
        そのまま move_mode に反映されること（未設定＝既定値を含む）"""
        for name, mode, expected_mode in self.SET_MODE_AND_EXPECTED_MODE:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)

                if mode is not None:
                    player.set_move_mode(mode)

                self.assertEqual(expected_mode, player.move_mode)

    def test_destination_does_not_affect_move_mode(self):
        """目的地（Player.set_destination()／clear_destination()、ID-022）の
        設定・解除は move_mode の返す値へ影響しない。目的地移動モードの
        3値化は Field.player_move_mode 側の関心であり、Player.move_mode は
        set_move_mode() で設定した基底モード（自動戦闘／自動収集の2値）の
        ままであること（ユーザー決定 2026-07-26）を、自動収集モードに
        目的地を設定・解除する前後で確認する"""
        player = Player(*self.START, self.SPEED)
        player.set_move_mode(MoveMode.COLLECT)

        player.set_destination(100, 200)
        self.assertEqual(MoveMode.COLLECT, player.move_mode)

        player.clear_destination()
        self.assertEqual(MoveMode.COLLECT, player.move_mode)


class TestPlayerDestination(unittest.TestCase):
    """Player の目的地（目的地移動モードでの移動先ワールド座標、ID-022）の
    保持・設定・解除の単体テスト（Pyxel・Field 非依存）。設定用メソッド
    set_destination()・解除用メソッド clear_destination()・読み取り専用
    プロパティ destination の名称・シグネチャをここで決定する（副作用のある
    設定操作と参照専用の取得を分けるのは start_invincibility()／
    is_invincible と同型）。目的地が move_mode・shoot() へ及ぼす効果は
    関心が別のため、それぞれ TestPlayerMoveMode・TestPlayerShootInMoveMode
    で検証する"""

    SPEED = 2
    START = (10, 20)
    DESTINATION = (100, 200)

    def test_destination_returns_none_by_default(self):
        """生成直後は目的地が未設定であり destination が None を返すこと"""
        player = Player(*self.START, self.SPEED)

        self.assertIsNone(player.destination)

    def test_destination_returns_value_set_by_set_destination(self):
        """set_destination() で与えたワールド座標が、そのまま destination
        から返ること"""
        player = Player(*self.START, self.SPEED)

        player.set_destination(*self.DESTINATION)

        self.assertEqual(self.DESTINATION, player.destination)

    def test_destination_returns_none_after_clear_destination(self):
        """目的地を設定した後に clear_destination() を呼ぶと、destination が
        再び None を返すこと"""
        player = Player(*self.START, self.SPEED)
        player.set_destination(*self.DESTINATION)

        player.clear_destination()

        self.assertIsNone(player.destination)


class TestPlayerShootInMoveMode(unittest.TestCase):
    """移動モード（MoveMode）・目的地の有無に応じた Player.shoot() の
    振る舞いの単体テスト（Pyxel・Field 非依存。ID-021 サイクル3・ID-022
    サイクル3）。モード・目的地の保持・取得自体は TestPlayerMoveMode・
    TestPlayerDestination の関心であり、ここではそれらが攻撃へ及ぼす効果
    のみを扱う

    仕様（requirements.md §3.1、ユーザー決定 2026-07-25・2026-07-26）:
    自動収集モード（MoveMode.COLLECT）では攻撃を行わないため、発射間隔の
    タイマーが発射契機に達していても shoot() は弾を返さない（空リスト）。
    ただし目的地移動モード中（Player.set_destination() で目的地が設定されて
    いる間）は、基底モードが自動収集モードであっても攻撃する。自動戦闘
    モード（MoveMode.ATTACK）では TestPlayerShoot のとおり目的地の有無に
    かかわらず弾を含むリストを返し、これが生成直後の既定値である。発射
    契機の判定自体は shoot() が持つ（Field 側は持たない）ため、モード・
    目的地の有無による攻撃可否も shoot() の責務として検証する
    """

    SPEED = 2
    START = (10, 20)
    DESTINATION = (100, 200)

    # (ケース名, set_move_mode() で設定するモード〔None は呼ばず既定のまま〕,
    #  set_destination() で目的地を設定するか, 発射契機のフレームで返る
    #  弾数)。自動戦闘モードの弾数1は「生成直後（通常ドロップ累計0個＝
    #  成長レベル4未満）の発射方向数は1」に由来する（多方向化そのものは
    #  TestPlayerNormalDropGrowthMultiDirectionShoot の関心）
    MODE_DESTINATION_AND_EXPECTED_BULLET_COUNT = [
        ("既定（自動戦闘）モード・目的地なしでは発射される", None, False, 1),
        ("自動収集モード・目的地なしでは発射されない", MoveMode.COLLECT, False, 0),
        ("自動収集モード・目的地ありでは発射される", MoveMode.COLLECT, True, 1),
        ("自動戦闘モード・目的地ありでも発射される", None, True, 1),
    ]

    def test_bullet_count_returned_at_fire_timing_per_move_mode_and_destination(self):
        """発射間隔（BULLET_SHOOT_INTERVAL 回の advance()）を経て発射契機に
        達したフレームで返る弾数が、自動戦闘モードでは目的地の有無に
        かかわらず1発、自動収集モードでは目的地なしなら0発・目的地ありなら
        1発であること"""
        interval = Player.BULLET_SHOOT_INTERVAL
        for (
            name,
            mode,
            has_destination,
            expected_bullet_count,
        ) in self.MODE_DESTINATION_AND_EXPECTED_BULLET_COUNT:
            with self.subTest(name):
                player = Player(*self.START, self.SPEED)
                if mode is not None:
                    player.set_move_mode(mode)
                if has_destination:
                    player.set_destination(*self.DESTINATION)

                # shoot() 自体はタイマーを進めないため、発射契機（advance()
                # の累積呼び出し回数が発射間隔に達したフレーム）まで
                # advance() のみを進めてから1回 shoot() する
                for _ in range(interval):
                    player.advance()
                fired = player.shoot()

                self.assertEqual(expected_bullet_count, len(fired))

    def test_bullet_fires_while_destination_set_in_collect_mode_and_stops_after_clear(
        self,
    ):
        """自動収集モード中に目的地を設定している間は発射契機のたびに弾が
        返り、目的地を解除する（自動収集モードへ戻る）と、以後の発射契機では
        再び弾が返らなくなること（ユーザー決定 2026-07-25・2026-07-26。
        到着・モブ接触・ボタン押下いずれの経路でも目的地は解除されるが、
        この単体テストでは経路を問わず clear_destination() 自体の効果を
        確認する）"""
        player = Player(*self.START, self.SPEED)
        player.set_move_mode(MoveMode.COLLECT)
        player.set_destination(*self.DESTINATION)
        interval = Player.BULLET_SHOOT_INTERVAL

        for _ in range(interval):
            player.advance()
        self.assertNotEqual([], player.shoot())

        player.clear_destination()

        for _ in range(interval):
            player.advance()
        self.assertEqual([], player.shoot())

    def test_bullet_shoot_timer_is_consumed_during_collect_mode(self):
        """自動収集モード中も発射契機（BULLET_SHOOT_INTERVAL 経過）ごとに
        タイマーは消費（リセット）され続け、弾を溜め込まないこと。溜め込むと
        自動戦闘へ切り替えた直後に、追加の advance() なしでも即座に発射が
        起きてしまう（弾を溜め込む仕様は求められていないため、切り替え直後
        の shoot() が空リストのままであることで確認する）"""
        player = Player(*self.START, self.SPEED)
        player.set_move_mode(MoveMode.COLLECT)
        interval = Player.BULLET_SHOOT_INTERVAL

        # 発射契機を複数回（3回）経過させる。自動収集モード中はいずれの
        # 契機でも弾は返らないが、タイマー自体は消費され続けているはず
        for _ in range(3 * interval):
            player.advance()
            player.shoot()

        player.set_move_mode(MoveMode.ATTACK)

        # 追加の advance() を行わずに shoot() しても、タイマーが消費済み
        # （0）であれば発射契機に達しておらず空リストが返るはず
        self.assertEqual([], player.shoot())


class TestMobTurnTowardLimited(unittest.TestCase):
    """Mob.turn_toward_limited() の単体テスト（Pyxel・GameCore 非依存）

    仕様: 現在の向きと目標方向の角度差が1回あたりの最大回転角度
    （Mob.MAX_TURN_ANGLE）以下なら目標方向へ即座に一致し、超える場合は
    最大回転角度分だけ現在の向きから目標方向（最短の回転方向）へ近づける。
    角度の規約は rotate_angle と同じ（度数法、0度=上方向、スクリーン上の
    時計回りが正、範囲 -180 < angle <= 180）。

    最大回転角度の具体値・境界ちょうど（差 == MAX_TURN_ANGLE）の丸め方は
    実装の詳細としてテストしない。テストデータは MAX_TURN_ANGLE からの
    相対値で構成し、明確に最大角度未満／超過のケースのみを検証する。
    """

    SPEED = 2
    START = (100, 100)
    TARGET_DIST = 50

    def _target_at(self, angle_deg):
        # 中心点（方向の基準点。TestActorTurnTo で固定した仕様）から見て
        # angle_deg 方向（0度=上、時計回りが正）へ TARGET_DIST 離れたワールド
        # 座標。rotate_angle と同じ角度規約のため、上方向 (0, -1) を angle_deg
        # だけ時計回りに回した単位ベクトル (sin(angle), -cos(angle)) を用いる
        rad = math.radians(angle_deg)
        return (
            self.START[0] + self.TARGET_DIST * math.sin(rad),
            self.START[1] - self.TARGET_DIST * math.cos(rad),
        )

    def test_turns_immediately_when_diff_within_max_angle(self):
        """目標方向との角度差が最大回転角度未満なら、1回の呼び出しで
        目標方向へ完全に一致すること（時計回り・反時計回りの両側、および
        角度差が 180度をまたぐ場合も最短の回転方向で一致すること）"""
        half = Mob.MAX_TURN_ANGLE / 2
        quarter = Mob.MAX_TURN_ANGLE / 4
        test_cases = [
            # (名前, 初期の向きの角度, 目標方向の角度)
            # 初期の向きから目標方向までの角度差はいずれも最大回転角度の
            # 半分（明確に最大角度未満）とする
            ("時計回り側", 0, half),
            ("反時計回り側", 0, -half),
            # 角度差が +180/-180 の境界をまたぐケース: 素朴な引き算では
            # 差がほぼ ±360度 に見えるが、正規化した最短差は
            # MAX_TURN_ANGLE / 2 のため即座に一致する必要がある
            ("180度をまたぐ最短方向", 180 - quarter, -(180 - quarter)),
        ]
        for name, start_angle, target_angle in test_cases:
            with self.subTest(name):
                mob = Mob(*self.START, self.SPEED)
                if start_angle != 0:
                    # 既存の turn_to()（瞬時に向く）で初期の向きを設定する
                    mob.turn_to(*self._target_at(start_angle))

                mob.turn_toward_limited(*self._target_at(target_angle))

                self.assertAlmostEqual(target_angle, mob.rotate_angle)

    def test_rotates_by_max_angle_per_call_and_converges(self):
        """目標方向との角度差が最大回転角度を超える場合、1回の呼び出しでは
        最大回転角度分だけ目標方向へ近づき、呼び出しを重ねると目標方向へ
        収束・以降は一致を維持すること（時計回り・反時計回りの両側）"""
        max_angle = Mob.MAX_TURN_ANGLE
        # 2.5回分の回転を要する角度差（明確に最大角度超過）。
        # 緩やかな旋回が目的のため MAX_TURN_ANGLE は 72度 以下
        # （2.5倍しても 180度 以内）である前提のテストデータ
        target_ratio = 2.5
        self.assertLessEqual(
            target_ratio * max_angle,
            180,
            "テストデータの前提: 目標角度が範囲 (-180, 180] に収まること",
        )
        for name, sign in [("時計回り側", 1), ("反時計回り側", -1)]:
            with self.subTest(name):
                mob = Mob(*self.START, self.SPEED)
                target_angle = sign * target_ratio * max_angle
                target = self._target_at(target_angle)
                # 1回目・2回目は最大回転角度ずつ近づき、3回目で残りの
                # 0.5回分が最大角度未満のため一致、4回目以降は一致を維持
                expected_angles = [
                    sign * max_angle,
                    sign * 2 * max_angle,
                    target_angle,
                    target_angle,
                ]
                for call_count, expected in enumerate(expected_angles, start=1):
                    mob.turn_toward_limited(*target)

                    self.assertAlmostEqual(
                        expected,
                        mob.rotate_angle,
                        msg=f"{call_count}回目の呼び出し後",
                    )
