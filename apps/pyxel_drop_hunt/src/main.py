# title: pyxel drop hunt
# author: masatobu

import math
import random
from abc import ABC, abstractmethod
from enum import Enum


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, color):
        pass

    @abstractmethod
    def draw_circ(self, x, y, r, color):
        pass

    @abstractmethod
    def draw_circb(self, x, y, r, color):
        pass

    @abstractmethod
    def draw_blt(self, x, y, img, u, v, w, h, colkey, rotate=0):
        pass

    @abstractmethod
    def clear(self, x, y):
        pass

    @abstractmethod
    def get_frame(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def draw_circ(self, x, y, r, color):
        self.pyxel.circ(x, y, r, color)

    def draw_circb(self, x, y, r, color):
        self.pyxel.circb(x, y, r, color)

    def draw_blt(self, x, y, img, u, v, w, h, colkey, rotate=0):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey, rotate=rotate)

    def clear(self, x, y):
        self.pyxel.camera(x, y)
        self.pyxel.cls(0)

    def get_frame(self) -> int:
        return self.pyxel.frame_count


class IInput(ABC):
    @abstractmethod
    def is_btn_pressed(self) -> bool:
        pass

    @property
    @abstractmethod
    def mouse_x(self) -> int:
        pass

    @property
    @abstractmethod
    def mouse_y(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class Actor:
    def __init__(self, x, y, speed, width, height):
        # x/y は画像の中心点（登録座標＝スプライト左上ではない）のワールド
        # 座標を表す。方向計算（turn_to()/advance()）は画像の中心点を基準に
        # 行うため、中心点そのものを内部状態にすることで基準点の変換が不要に
        # なる。少数のまま保持・蓄積し、参照時にのみ整数へ丸めることで、
        # 整数返却でも任意方向への移動を可能にする
        self._x = float(x)
        self._y = float(y)
        self._speed = speed
        # 画像サイズ。中心点から登録座標（描画時にのみ必要）を求めるために保持する
        self._width = width
        self._height = height
        # 進行方向の単位ベクトル（初期値は上方向）
        self._dir_x = 0.0
        self._dir_y = -1.0

    @property
    def x(self):
        # 画像の中心点（他アクターから方向の目標として参照される点）
        return round(self._x)

    @property
    def y(self):
        return round(self._y)

    @property
    def image_x(self):
        # 登録座標（スプライト左上）。IView.draw_blt() など描画時にのみ
        # 必要なため、中心点から画像サイズの半分を引いて算出する
        return self.x - self._width // 2

    @property
    def image_y(self):
        return self.y - self._height // 2

    @property
    def direction(self):
        # 進行方向の単位ベクトル（他アクターから生成時点の向きとしてコピー
        # される用途のため、rotate_angle への変換を経ない生の値を公開する）
        return self._dir_x, self._dir_y

    @property
    def rotate_angle(self):
        # 進行方向に対応する角度（度数法。0度=上方向、スクリーン上の時計回りが
        # 正、範囲は -180 < angle <= 180）。弾の発射方向など正確な角度が必要な
        # 用途で使われるため丸めは行わない（描画時の8/16方向へのスナップは
        # GameCore 側の責務とする）
        return self._angle_of(self._dir_x, self._dir_y)

    @staticmethod
    def _angle_of(dx, dy):
        # (dx, dy) 方向に対応する角度（rotate_angle と同じ規約）。上方向
        # (0, -1) を 0度とするため atan2 には (dx, -dy) を渡す
        return math.degrees(math.atan2(dx, -dy))

    def _diff_to(self, world_x, world_y):
        # 方向は画像の中心点（内部状態そのもの）を基準に計算する
        # （プレイヤーの見た目の中心がタップ位置＝目的地へ向かって移動し、
        # 到着時に目的地の旗の根本と一致するため）
        diff_x = world_x - self._x
        diff_y = world_y - self._y
        return diff_x, diff_y, math.hypot(diff_x, diff_y)

    def turn_to(self, world_x, world_y):
        diff_x, diff_y, dist = self._diff_to(world_x, world_y)
        if dist == 0:
            # 画像中心点と同一座標が指定された場合は方向を変えず、直前の進行方向を維持する
            return
        self._dir_x = diff_x / dist
        self._dir_y = diff_y / dist

    def advance(self):
        self._x += self._speed * self._dir_x
        self._y += self._speed * self._dir_y


class Bullet(Actor):
    # 弾の画像サイズ（Player/Mob と同様、Bullet 自身が定義する。
    # tasks.md/requirements.md より4×4）
    WIDTH = 4
    HEIGHT = 4

    def __init__(self, x, y, speed):
        super().__init__(x, y, speed, self.WIDTH, self.HEIGHT)


class MoveMode(Enum):
    # 移動モードの状態（requirements.md §3.1。初期値は自動戦闘。他プロジェクト
    # 〔pyxel_dig_smith の Direct 等〕と同様、状態の集合はモジュール直下の
    # Enum として定義する）。Player がモード情報を保持するため、Player より
    # 前で定義する。
    #
    # この3値をすべて返すのは Field.player_move_mode（実効モード）のみ。
    # Player.move_mode（基底モード）は ATTACK/COLLECT の2値のみを返し、
    # DESTINATION へは決してならない（目的地移動モードは Player 自身が持つ
    # 目的地の有無から Field が導出する派生的な状態のため、ID-022）
    ATTACK = "attack"
    COLLECT = "collect"
    DESTINATION = "destination"


class Player(Actor):
    # プレイヤーの画像サイズ。何ピクセルかは Player 自身が決めるものであり、
    # 生成時に外部（GameCore）から与えられるものではないため、ここで定義し
    # Actor へ渡す
    WIDTH = 8
    HEIGHT = 8
    # 発射する弾の速度。将来的にプレイヤー自身のパラメータ（強化・武器種
    # など）として個体差を持たせる予定のため、Field ではなく Player 自身が
    # 定義する（WIDTH/HEIGHT と同じ理由）
    BULLET_SPEED = 2
    # 弾を発射する間隔（フレーム数）。速度と同様、将来的にプレイヤー自身の
    # パラメータ（強化・武器種など）として個体差を持たせる予定のため、
    # Player 自身が定義し、発射契機の判定（タイマー）も Player 自身が持つ
    BULLET_SHOOT_INTERVAL = 30
    # 通常ドロップの累計取得数がこの値へ到達するたびに発射間隔を半分にする
    # （しきい値 = 10×(2^level−1)、level=1,2,3。頻度の成長はレベル3
    # （8倍）が上限で、レベル4以降は集合に含まれる値がないため変化しない。
    # shoot() は毎フレーム呼ばれるのに対し、しきい値到達はドロップ回収時の
    # みのまれな事象のため、判定・間隔の更新は shoot() 側ではなく
    # add_normal_drop_count() 側で行う（毎フレームの再計算を避ける）
    _INTERVAL_HALVING_THRESHOLDS = frozenset(10 * (2**level - 1) for level in (1, 2, 3))
    # HP の初期値（満タン値）。HP・レアドロップ数は Player 自身の状態の
    # 関心事のため Field から移した（Field は委譲するだけになる。委譲への
    # 書き換えは ID-013-20 の Refactor で行う）
    INITIAL_HP = 3
    # 被弾後に無敵となるフレーム数（fps 未指定＝Pyxel 既定の 30fps で
    # 約1秒）。HP と同じ「接触イベント」に閉じた Player 自身の関心事の
    # ため INITIAL_HP と同様 Player が定義する
    INVINCIBLE_FRAMES = 30
    # 被弾時に接触したモブと反対方向へ移動（ヒットバック）する距離
    # （スプライト1枚分。具体値はプレイテストで調整するゲームバランスの
    # 詳細）。無敵時間と同じ「接触イベント」に閉じた関心事のため
    # INVINCIBLE_FRAMES と同様 Player が定義する
    HITBACK_DISTANCE = 8
    # ヒットバックの継続フレーム数（接触フレームを1フレーム目として、
    # HITBACK_DISTANCE をこのフレーム数で等分して少しずつ移動する。
    # 1フレームでは移動し切らない仕様のため2以上。具体値は
    # HITBACK_DISTANCE と同様プレイテストで調整するゲームバランスの詳細）
    HITBACK_FRAMES = 4
    # 目的地への「到着」とみなす、画像中心点と目的地の距離のしきい値
    # （具体的な値・境界ちょうどの挙動は仕様として固定しない実装の詳細）。
    # 到着判定は自身の位置（画像中心点）と自身が保持する目的地のみで完結
    # し、他の actor との相互作用（接触判定等）を伴わないため、Field では
    # なく Player 自身が定義・判定する（ID-022 サイクル4 で目的地の保持先を
    # Player へ移したのに合わせ、サイクル4 Refactor で判定も移した）
    DESTINATION_ARRIVAL_DISTANCE = 2

    def __init__(self, x, y, speed):
        super().__init__(x, y, speed, self.WIDTH, self.HEIGHT)
        self._bullet_shoot_timer = 0
        # クラス定数を初期値とするインスタンス変数。将来的な個体差
        # （強化・武器種など）の付与やテストからの上書きに備え、判定は
        # 常にこちらを参照する
        self._bullet_shoot_interval = self.BULLET_SHOOT_INTERVAL
        # 通常ドロップの累計取得数。成長（発射頻度・発射方向数）の判定に使う
        self._normal_drop_count = 0
        # HP・レアドロップ累計取得数。HP は decrease_hp() で1ずつ減らす
        self._hp = self.INITIAL_HP
        self._rare_drop_count = 0
        # 被弾後の無敵時間の残りフレーム数。0 は無敵でない状態を表す。
        # HP と同じ「接触イベント」に閉じた関心事のため Player が保持する
        self._invincible_timer = 0
        # ヒットバックの残りフレーム数（0 はヒットバック中でない状態）。
        # 無敵時間と同じ「接触イベント」に閉じた関心事のため Player が
        # 保持する。移動方向は別途保持せず、ヒットバック中は進行方向
        # （_dir_x/_dir_y、ヒットしたモブの方向）の反対として都度導出する
        # （_advance_hitback() 参照。ヒットバック中は自動追尾が Field 側で
        # 抑止されるため進行方向は変化しない）
        self._hitback_frames_left = 0
        self._move_mode = MoveMode.ATTACK
        # 目的地移動モードの移動先ワールド座標（None は目的地未設定を表す）。
        # 目的地の有無で実効モード（3値）を導出するのは Field 側の関心の
        # ため（ID-022）、Player 自身はここでは座標の保持のみ担う
        self._destination = None

    def add_normal_drop_count(self):
        # 通常ドロップを1個取得したことを表す（Field がドロップ回収のたびに
        # 呼ぶ想定。加算のみで消費・リセットは行わない）。累計が半減しきい値
        # ちょうどに到達した瞬間だけ発射間隔を半分にする（1ずつの加算のため
        # しきい値を飛び越えることはなく、一致判定のみで判定できる）
        self._normal_drop_count += 1
        if self._normal_drop_count in self._INTERVAL_HALVING_THRESHOLDS:
            self._bullet_shoot_interval /= 2

    @property
    def normal_drop_count(self):
        return self._normal_drop_count

    @property
    def normal_drop_level(self):
        return self._normal_drop_level()

    def _normal_drop_level(self):
        # 累計取得数（しきい値の系列 10×(2^level−1)、level=1..8）から現在の
        # レベル（0〜8）を導出する。shoot() と next_normal_drop_threshold の
        # 双方が参照する共通ロジック
        level = 0
        while level < 8 and self._normal_drop_count >= 10 * (2 ** (level + 1) - 1):
            level += 1
        return level

    @property
    def next_normal_drop_threshold(self):
        # 次のレベルへ到達する累計しきい値 10×(2^(level+1)−1) を返す。
        # レベル8（成長上限）到達後は次のしきい値が存在しないため None を返す
        level = self._normal_drop_level()
        if level >= 8:
            return None
        return 10 * (2 ** (level + 1) - 1)

    @property
    def hp(self):
        return self._hp

    def decrease_hp(self):
        self._hp -= 1

    @property
    def is_invincible(self):
        # 無敵タイマーが残っているか（副作用なしの参照専用）。接触判定の
        # スキップ判定だけでなく、無敵中の点滅描画など描画側からの参照にも
        # 使う想定のため、タイマーの消費（tick_invincibility()）とは
        # 別メソッドに分離する
        return self._invincible_timer > 0

    def tick_invincibility(self):
        # 無敵タイマーを1減らす（呼び出し側は is_invincible で無敵中である
        # ことを確認してから呼ぶ想定）。呼び出し側から毎フレーム1回呼ばれる
        # 想定で、この減算が1フレームの経過を表す
        self._invincible_timer -= 1

    def start_invincibility(self):
        self._invincible_timer = self.INVINCIBLE_FRAMES

    def hitback_from(self, world_x, world_y):
        # 指定座標（接触したモブの中心）と反対方向へ、HITBACK_FRAMES
        # フレームかけて合計 HITBACK_DISTANCE だけ移動するヒットバックを
        # 開始する（1フレーム分の移動は接触フレームから始める）。方向は
        # turn_to() と同じく画像中心点を基準に計算する。ヒットバック中は
        # 接触したモブの方向を向き続けるため、進行方向はモブへ向ける
        # （移動はヒットバックの等分移動が担うため、この向きで前進する
        # ことはない。advance() 参照）
        diff_x, diff_y, dist = self._diff_to(world_x, world_y)
        if dist == 0:
            # 画像中心点と同一座標が指定された場合は方向が定まらないため移動しない
            return
        self._dir_x = diff_x / dist
        self._dir_y = diff_y / dist
        self._hitback_frames_left = self.HITBACK_FRAMES
        self._advance_hitback()

    def _advance_hitback(self):
        # ヒットバックの1フレーム分（HITBACK_DISTANCE の等分）だけ、進行
        # 方向（ヒットしたモブの方向）と反対向きへ移動し、残りフレーム数を
        # 消費する
        step = self.HITBACK_DISTANCE / self.HITBACK_FRAMES
        self._x -= step * self._dir_x
        self._y -= step * self._dir_y
        self._hitback_frames_left -= 1

    @property
    def is_in_hitback(self):
        # ヒットバックの残りフレームがあるか（副作用なしの参照専用）。
        # ヒットバック中の自動追尾の抑止判定（Field 側）が参照する
        return self._hitback_frames_left > 0

    def add_rare_drop_count(self):
        # レアドロップを1個取得したことを表す（Field がドロップ回収のたびに
        # 呼ぶ想定。加算のみで消費・リセットは行わない）。レベルアップ判定
        # （モブ出現間隔の半減）は Player の関心事ではなく Field が持つ
        # ため、ここでは加算のみを行う（責務分離。add_normal_drop_count()
        # は発射間隔という Player 自身が持つ状態への半減も担うため、この
        # メソッドと役割が異なる点に注意）
        self._rare_drop_count += 1

    @property
    def rare_drop_count(self):
        return self._rare_drop_count

    @property
    def move_mode(self):
        return self._move_mode

    def set_move_mode(self, mode):
        self._move_mode = mode

    @property
    def destination(self):
        return self._destination

    def set_destination(self, world_x, world_y):
        self._destination = (world_x, world_y)

    def clear_destination(self):
        self._destination = None

    def clear_destination_if_arrived(self):
        # 目的地未設定（自動追尾中）の間は判定不要
        if self._destination is None:
            return
        # 画像中心点（自身の位置）が目的地へ明確に到着したと言える距離まで
        # 近づいたら目的地を解除する。向きは変更せず、次フレーム以降は
        # 自動追尾へ委ねる。呼び出し側（Field）はこの解除を毎フレームの
        # 前進の後に呼ぶ想定（advance() 呼び出し前は前進前の位置になり
        # 到着の検出が1フレーム遅れるため）
        dest_x, dest_y = self._destination
        _, _, dist = self._diff_to(dest_x, dest_y)
        if dist <= self.DESTINATION_ARRIVAL_DISTANCE:
            self._destination = None

    def advance(self):
        # ヒットバック中は進行方向（接触したモブの方向）への前進を行わず、
        # ヒットバックの等分移動のみで位置が変わる（前進を続けると
        # ヒットバックと逆向きの移動が混ざり打ち消し合ってしまうため）
        if self._hitback_frames_left > 0:
            self._advance_hitback()
        else:
            super().advance()
        # 発射間隔のタイマーは「1フレーム経過」を表す advance() の呼び出し
        # ごとに進める（前進処理と同じ、毎フレーム必ず1回呼ばれる契機に
        # 乗せる）。shoot() 側はタイマーを進めず、発射可否の判定と発射時の
        # リセットのみを行う
        self._bullet_shoot_timer += 1

    def shoot(self):
        # 毎フレーム呼び出される想定。発射間隔（advance() の呼び出し回数）
        # に達していればその時点の弾を1発以上含むリストを返し、タイマーを
        # リセットする。達していなければ空リストを返す（呼び出し側はこの
        # 返却値をそのまま自身の弾リストへ追加していく想定で、Field 側は
        # 発射契機の判定を持たない）
        if self._bullet_shoot_timer < self._bullet_shoot_interval:
            return []
        # タイマーを0へリセットせず余りを繰り越す（端数間隔でも平均発射
        # 周期が interval と一致するようにするため）。自動収集モード中で
        # 弾を返さない場合もこの消費は必ず行う。消費せず素通りさせると
        # 自動収集モード中もタイマーが際限なく積み上がり、自動戦闘へ
        # 戻した瞬間に複数回分の発射がまとまって起きてしまう（弾を
        # 溜め込む仕様は求められていない）
        self._bullet_shoot_timer -= self._bullet_shoot_interval
        # 自動収集モード中は攻撃を行わない（requirements.md §3.1）ため、
        # 発射契機に達していても弾を返さない。ただし目的地移動モード中
        # （目的地が設定されている間）は基底モードが自動収集モードで
        # あっても攻撃する（ユーザー決定 2026-07-25・2026-07-26、ID-022）
        if self._move_mode == MoveMode.COLLECT and self._destination is None:
            return []
        # 現在のレベル（1〜8、多方向化はレベル4以上でのみ発生）から
        # n = 2^(L−3) + 1 方向・広がり角 θ = min(30×2^(L−4), 360) 度の計算式
        # （requirements.md §3.5／tasks.md／ID-013_subtasks.md の成長
        # テーブルの式と一致）で n・θ を導出する。n を奇数にすることで、
        # 扇の中央（進行方向そのもの、相対角度0度）に一致する弾を必ず1発
        # 含める。相対角度列は θ < 360 では「−θ/2 から θ/(n−1) 度間隔で
        # n 発（両端を含む対称配置）」、θ = 360 のみ両端（±180度）が一致
        # するため「k×360/n 度間隔で n 発の全周等間隔配置（k=0 が進行方向）」
        # の計算式で導出する
        level = self._normal_drop_level()
        if level < 4:
            relative_angles = [0.0]
        else:
            n = 2 ** (level - 3) + 1
            theta = min(30 * 2 ** (level - 4), 360)
            if theta < 360:
                relative_angles = [-theta / 2 + k * theta / (n - 1) for k in range(n)]
            else:
                relative_angles = [k * 360 / n for k in range(n)]
        # 弾を発射するのはプレイヤー自身の振る舞いのため、Bullet の生成は
        # Player が担う。x/y は画像中心点のため、画像サイズが異なっていても
        # 弾の中心点をそのまま自身の中心点に一致させて生成できる
        # （登録座標基準では必要だった画像サイズの半分オフセット計算が不要）
        bullets = []
        for relative in relative_angles:
            bullet = Bullet(self.x, self.y, self.BULLET_SPEED)
            # 弾の向きは turn_to() で設定する。目標点に「弾の中心点（生成
            # 直後は自身の中心点と一致）+ 向きの単位ベクトル」を渡すと、
            # turn_to() 内部の差分計算の結果がそのまま弾の進行方向の単位
            # ベクトルになる。向きの単位ベクトルは「自身の進行方向の角度 +
            # 相対角度」から sin/−cos（rotate_angle の逆変換）で算出する
            rad = math.radians(self.rotate_angle + relative)
            bullet.turn_to(self.x + math.sin(rad), self.y - math.cos(rad))
            bullets.append(bullet)
        return bullets


class Mob(Actor):
    # モブの画像サイズ（Player と同様、Mob 自身が定義する）
    WIDTH = 8
    HEIGHT = 8
    # 1回（1フレーム）の方向転換で回転できる最大角度（度数法）。
    # プレイヤーへの追尾を急旋回ではなく緩やかな旋回にするための制限
    MAX_TURN_ANGLE = 6

    def __init__(self, x, y, speed):
        super().__init__(x, y, speed, self.WIDTH, self.HEIGHT)

    def turn_toward_limited(self, world_x, world_y):
        diff_x, diff_y, dist = self._diff_to(world_x, world_y)
        if dist == 0:
            # 画像中心点と同一座標が指定された場合は方向を変えず、直前の進行方向を維持する
            return
        target_angle = self._angle_of(diff_x, diff_y)
        # 現在の向きとの角度差を最短の回転方向へ正規化（-180 <= diff < 180）
        angle_diff = (target_angle - self.rotate_angle + 180) % 360 - 180
        if abs(angle_diff) <= self.MAX_TURN_ANGLE:
            new_angle = target_angle
        else:
            new_angle = self.rotate_angle + math.copysign(
                self.MAX_TURN_ANGLE, angle_diff
            )
        rad = math.radians(new_angle)
        self._dir_x = math.sin(rad)
        self._dir_y = -math.cos(rad)


class Drop(Actor):
    # ドロップの画像サイズ（tasks.md 描画アセット表より 4×4。Mob と同様、
    # Drop 自身が定義する）
    WIDTH = 4
    HEIGHT = 4

    def __init__(self, x, y, speed, is_rare):
        super().__init__(x, y, speed, self.WIDTH, self.HEIGHT)
        self._is_rare = is_rare

    @property
    def is_rare(self):
        return self._is_rare

    @property
    def is_attracted(self):
        # 引き寄せ中かどうかは速度そのものが表す（生成時は静止＝速度0で、
        # 引き寄せの開始で速度を与えられる）。専用のフラグは持たず既存の
        # 状態から導出する
        return self._speed > 0

    def start_attraction(self, speed):
        # 引き寄せの移動速度を与える（プレイヤーの移動モードは参照しない。
        # 開始の契機を判断するのは Field 側の責務で、Drop は与えられた速度を
        # 保持して以後プレイヤーへ向かい続けるのみ。Player が無敵時間の残り
        # フレームを自分で持ち、Field が契機だけを与えるのと同じ責務分担）
        self._speed = speed


class Field:
    # actor 関連の状態（プレイヤー・モブ・目的地・出現タイマー）と挙動ロジック
    # を持つクラス。GameCore からの結線の置き換えは ID-007-22 で行うため、
    # この時点では以下の定数値は GameCore 側の同名定数と重複して持つ
    # （二重管理の解消は結線時に GameCore 側がここを単一の情報源として
    # 参照する形で行う想定）
    SCREEN_WIDTH = 150
    SCREEN_HEIGHT = 200
    PLAYER_SPEED = 0.5
    MOB_SPEED = 0.25
    # 出現時に上下の画面辺から画面外へずらす距離（モブ全体が画面外に収まる値）
    MOB_SPAWN_OFFSET = 8
    # 左右の画面辺から出現する場合に画面外へずらす距離（画面の縦横差の半分だけ
    # 遠くから出現させ、上下の辺から出現した場合との到達時間差を補う）
    MOB_SPAWN_OFFSET_SIDE = MOB_SPAWN_OFFSET + (SCREEN_HEIGHT - SCREEN_WIDTH) // 2
    # モブの出現間隔（フレーム数）
    MOB_SPAWN_INTERVAL = 60
    # 消滅判定矩形の余白。最も遠い出現オフセットと一致させ、出現直後のモブが
    # 画面内へ入るより先に消滅判定されるのを防ぐ
    MOB_DESPAWN_MARGIN = MOB_SPAWN_OFFSET_SIDE
    # 弾の射程。プレイヤーの画面上の位置からこの距離に達した弾を消滅させる
    # （requirements.md §3.3）
    BULLET_RANGE = 35
    # ドロップの引き寄せ範囲。プレイヤー中心からこの距離以下のドロップが
    # 引き寄せを開始する（requirements.md §3.4）。範囲はプレイヤーの成長
    # レベルに応じて広がるため、この定数はレベル0（成長前）の範囲を表す
    DROP_ATTRACT_RANGE = 12
    # モブ撃破時に通常ドロップの代わりにレアドロップが生成される確率
    # （具体値はプレイテストで調整するゲームバランスの詳細。可変にする
    # 予定はないためインスタンス変数化せず、クラス定数のみを持つ）
    RARE_DROP_RATE = 0.02
    # ゲームクリアに必要なレアドロップの累計取得数（requirements.md §3.7
    # の「規定値」を具体化した固定値。レベルアップのしきい値系列
    # （1, 3, 7, 15, …）とは独立した別の定数で、レベルアップが今後も
    # 続くかどうかに関わらず変化しない）
    RARE_DROP_CLEAR_TARGET = 20
    # ドロップの消滅領域の広さ（表示領域の縦の長さ SCREEN_HEIGHT × この
    # 倍率を一辺とする、表示領域と中心を揃えた正方形の外へ出たドロップを
    # 消滅させるか）。回収し損ねたドロップが表示領域から外れてもすぐには
    # 消えず戻って回収できるよう表示領域より広く、縦横で広さが変わらない
    # よう正方形に取る。具体値はプレイ体験を見て調整する
    DROP_DESPAWN_VIEW_SCALE = 3

    def __init__(self):
        # Player の x/y は画像中心点のため、画面中央へ配置する座標は単純に
        # 画面サイズの半分になる（登録座標を経由する半分オフセット計算が不要）
        self._player = Player(
            self.SCREEN_WIDTH // 2,
            self.SCREEN_HEIGHT // 2,
            self.PLAYER_SPEED,
        )
        self._mobs = [self._spawn_mob()]
        self._mob_spawn_timer = 0
        # クラス定数を初期値とするインスタンス変数。将来的な難易度変化
        # やテストからの上書きに備え、判定は常にこちらを参照する
        self._mob_spawn_interval = self.MOB_SPAWN_INTERVAL
        # レアドロップの次のレベルアップしきい値（累計取得数）。モブ出現
        # 間隔の半減は Field 自身の状態（_mob_spawn_interval）への操作の
        # ため、半減の契機となるレベル判定も Field 側で持つ（Player は
        # 累計取得数の加算のみを担う。責務分離）。レベル L のしきい値は
        # 2^L−1（1, 3, 7, 15, …）で、Player._normal_drop_level() の
        # 固定8段階（frozenset の半減しきい値）と異なり打ち止めを設けない
        # ため、次のしきい値を「次 = 次×2+1」でその都度際限なく生成する
        self._next_rare_level_threshold = 1
        # 発射契機の判定・弾の生成は Player.shoot() が担う（発射間隔の
        # タイマーも Player 自身が持つ）ため、Field は毎フレームの呼び出しで
        # 得られた弾をリストへ追加していくのみで、ここでは空のまま始める
        self._bullets = []
        # モブ撃破時に撃破位置へ生成されるドロップ（Drop(Actor)。Mob と同様、
        # 撃破されたモブと画像中心を揃えた位置に生成される）
        self._drops = []
        # ステータス（HP・レアドロップ数・通常ドロップ数・無敵タイマー）と
        # 目的地（目的地移動モードの移動先ワールド座標）は、いずれも Player
        # 自身の状態の関心事のため Player が保持し、Field は委譲する
        # （player_hp／rare_drop_count／normal_drop_count／destination の各
        # プロパティ、tick_invincibility()／start_invincibility() 参照）

    def _camera_offset(self):
        return (
            self._player.image_x - (self.SCREEN_WIDTH - Player.WIDTH) // 2,
            self._player.image_y - (self.SCREEN_HEIGHT - Player.HEIGHT) // 2,
        )

    def _spawn_position_top_bottom(self, camera_x, camera_y, is_top):
        # 横の線分（上辺または下辺）上のランダムな登録座標 x、画面外方向へは
        # 固定オフセット（画面辺・出現余白との整合が取りやすいよう、この
        # メソッドの計算は登録座標＝スプライト左上のまま行う。中心点への
        # 変換は呼び出し元の _spawn_mob() で行う）
        spawn_x = random.uniform(camera_x, camera_x + self.SCREEN_WIDTH - Mob.WIDTH)
        if is_top:
            spawn_y = camera_y - self.MOB_SPAWN_OFFSET
        else:
            spawn_y = camera_y + self.SCREEN_HEIGHT - Mob.HEIGHT + self.MOB_SPAWN_OFFSET
        return spawn_x, spawn_y

    def _spawn_position_left_right(self, camera_x, camera_y, is_right):
        # 縦の線分（左辺または右辺）上のランダムな登録座標 y、画面外方向へは
        # 固定オフセット（登録座標のまま計算する理由は _spawn_position_top_bottom 参照）
        spawn_y = random.uniform(camera_y, camera_y + self.SCREEN_HEIGHT - Mob.HEIGHT)
        if is_right:
            spawn_x = (
                camera_x + self.SCREEN_WIDTH - Mob.WIDTH + self.MOB_SPAWN_OFFSET_SIDE
            )
        else:
            spawn_x = camera_x - self.MOB_SPAWN_OFFSET_SIDE
        return spawn_x, spawn_y

    def _spawn_position(self, camera_x, camera_y):
        # プレイヤーの進行方向側の画面辺の線分上のランダムな登録座標から、
        # 画面外へ辺ごとのオフセット分ずらした位置を返す
        angle = self._player.rotate_angle
        if 45 <= abs(angle) <= 135:
            return self._spawn_position_left_right(camera_x, camera_y, angle > 0)
        return self._spawn_position_top_bottom(camera_x, camera_y, abs(angle) < 45)

    def _spawn_mob(self):
        camera_x, camera_y = self._camera_offset()
        image_x, image_y = self._spawn_position(camera_x, camera_y)
        # Mob の x/y は画像中心点のため、登録座標から画像サイズの半分を
        # 足して変換する
        mob = Mob(image_x + Mob.WIDTH / 2, image_y + Mob.HEIGHT / 2, self.MOB_SPEED)
        # 出現時は最大角度制限のある緩やかな旋回を待たず、瞬時にプレイヤーの
        # 方向（中心点同士）を向く（以降のフレームごとの追尾は process_frame() 側で行う）
        mob.turn_to(self._player.x, self._player.y)
        return mob

    @staticmethod
    def _rects_overlap(x1, y1, width1, height1, x2, y2, width2, height2):
        # 登録座標（左上）+ 幅・高さで表される2矩形が1ピクセルでも重なって
        # いるかを返す（辺が接するだけでは重ならないとみなす strict 不等式。
        # _remove_outside_view() の消滅判定・命中判定で共通に使う低レベルの
        # 重なり算術）
        return (
            x1 + width1 > x2
            and x1 < x2 + width2
            and y1 + height1 > y2
            and y1 < y2 + height2
        )

    def _remove_outside_view(self, actors, width, height, margin):
        # 消滅判定矩形（表示領域を全辺 margin だけ外側へ広げた矩形）から
        # actor 矩形が完全にはみ出した actor を取り除いたリストを返す
        # （モブ専用。弾の消滅判定は射程によるため _remove_bullets_out_of_
        # range() を使う。margin=MOB_DESPAWN_MARGIN で呼ばれる）
        camera_x, camera_y = self._camera_offset()
        left = camera_x - margin
        top = camera_y - margin
        despawn_width = self.SCREEN_WIDTH + 2 * margin
        despawn_height = self.SCREEN_HEIGHT + 2 * margin
        return [
            actor
            for actor in actors
            if self._rects_overlap(
                actor.image_x,
                actor.image_y,
                width,
                height,
                left,
                top,
                despawn_width,
                despawn_height,
            )
        ]

    def _remove_bullets_out_of_range(self):
        # 弾はモブ・ドロップと異なり、表示領域ではなくプレイヤーの画面上の
        # 位置からの距離（射程）で消滅させる（requirements.md §3.3）。
        # _camera_offset() はプレイヤーの画面上の位置を常に固定値に保つ
        # ため、画面上の距離は中心点同士のワールド座標上の距離とそのまま
        # 一致し、カメラ変換を経由する必要はない（`Actor.x`/`y` はいずれも
        # round() 済みの整数のため丸め差も生じない）
        return [
            bullet
            for bullet in self._bullets
            if math.hypot(bullet.x - self._player.x, bullet.y - self._player.y)
            < self.BULLET_RANGE
        ]

    def _resolve_bullet_mob_hits(self):
        # 弾とモブの矩形が1ピクセルでも重なった組を命中とみなし、命中した
        # モブ・弾をそれぞれ取り除いたリストの組 (mobs, bullets,
        # destroyed_mobs) を返す（辺が接するだけでは命中しない）。命中で
        # 双方を除去するため、判定は除去前の self._mobs / self._bullets
        # 同士で行う（先に片方を除去してからもう片方を判定すると、命中相手が
        # 消えて判定できなくなるため）。destroyed_mobs は撃破位置への
        # ドロップ生成のため、呼び出し側（process_frame()）が必要とする
        def hit(bullet, mob):
            return self._rects_overlap(
                bullet.image_x,
                bullet.image_y,
                Bullet.WIDTH,
                Bullet.HEIGHT,
                mob.image_x,
                mob.image_y,
                Mob.WIDTH,
                Mob.HEIGHT,
            )

        # 各モブの命中有無を1回だけ判定し、生存/撃破の分割元とする（呼び出し
        # 側で除去前後のリストを突き合わせて撃破モブを再導出する必要がない）
        mob_is_hit = [
            (mob, any(hit(bullet, mob) for bullet in self._bullets))
            for mob in self._mobs
        ]
        mobs = [mob for mob, is_hit in mob_is_hit if not is_hit]
        destroyed_mobs = [mob for mob, is_hit in mob_is_hit if is_hit]
        bullets = [
            bullet
            for bullet in self._bullets
            if not any(hit(bullet, mob) for mob in self._mobs)
        ]
        return mobs, bullets, destroyed_mobs

    def _try_spawn_mob(self):
        self._mob_spawn_timer += 1
        # タイマーを0へリセットせず余りを繰り越す（端数間隔でも平均出現
        # 周期が interval と一致するようにするため。Player.shoot() と同じ
        # キャリーオーバー方式）。単発の if ではなく while ループにする
        # ことで、間隔が1フレーム未満のとき同一フレーム内で複数回ループが
        # 回り、1フレームあたりの出現数が間隔に応じて増える
        while self._mob_spawn_timer >= self._mob_spawn_interval:
            self._mobs.append(self._spawn_mob())
            self._mob_spawn_timer -= self._mob_spawn_interval

    def _track_nearest(self, items):
        # 画面内（カメラオフセット基準の表示領域）に存在する対象のうち最も
        # 近いものの方向を瞬時に向く。画面内に対象が存在しない場合は向きを
        # 変えない（直前の向きを維持する）。Drop/Mob はいずれも Actor の
        # image_x/image_y（登録座標）・x/y（中心点）を共通に持つため、
        # 対象の種類によらず同じ実装で扱える
        camera_x, camera_y = self._camera_offset()
        visible = [
            item
            for item in items
            if camera_x <= item.image_x < camera_x + self.SCREEN_WIDTH
            and camera_y <= item.image_y < camera_y + self.SCREEN_HEIGHT
        ]
        if not visible:
            return
        player_x, player_y = self._player.x, self._player.y
        nearest_x, nearest_y = min(
            ((item.x, item.y) for item in visible),
            key=lambda center: math.hypot(center[0] - player_x, center[1] - player_y),
        )
        self._player.turn_to(nearest_x, nearest_y)

    def _track_facing(self):
        # 目的地移動モード中は自動追尾を抑止し、目的地の方向へ向き続ける
        # （目的地の有無ではなく実効モードで判定する。目的地は「移動先の
        # 座標」という役割に留め、モードの判定は player_move_mode に一本化
        # する）
        if self.player_move_mode == MoveMode.DESTINATION:
            return
        # ヒットバック中はヒットしたモブの方向（hitback_from() で設定
        # 済み）を向き続けるため、自動追尾による向きの上書きを抑止する
        # （目的地移動中の抑止と同型のパターン）
        if self._player.is_in_hitback:
            return
        # 自動収集モードでは最も近いドロップを、自動戦闘モードでは最も近い
        # モブを追尾する（上記の抑止はモードによらず優先されるため、
        # モードの分岐は抑止の後に置く）
        if self._player.move_mode == MoveMode.COLLECT:
            self._track_nearest(self._drops)
        else:
            self._track_nearest(self._mobs)

    def _spawn_drop(self, mob):
        # 撃破されたモブの画像中心をそのままドロップの生成座標として渡し、
        # 一定確率でレア種別の Drop を生成する（画像中心の一致は
        # コンストラクタ引数そのもので表現され、登録座標への変換は
        # Actor.image_x/image_y に委ねる）。速度0＝静止した状態で生成し、
        # 引き寄せの開始時に速度を与える（_attract_drops() 参照）
        is_rare = random.random() < self.RARE_DROP_RATE
        return Drop(mob.x, mob.y, 0, is_rare)

    def _cancel_destination_move_to_attack(self):
        # 目的地移動を中止し自動戦闘モードへ戻す（モブ接触
        # 〔_apply_mob_contact_damage()〕・ボタン押下
        # 〔toggle_player_move_mode()、ID-022 サイクル6〕による目的地移動
        # モードからの離脱で共通の操作。目的地への到着による直前モードへの
        # 復帰〔Player.clear_destination_if_arrived()〕は「直前モードへ戻る」
        # 別の操作であり、ここでの共通化の対象ではない）
        self._player.clear_destination()
        self._player.set_move_mode(MoveMode.ATTACK)

    def _apply_mob_contact_damage(self):
        # 被弾後の無敵時間中は接触の判定自体を行わない（接触は「なかった
        # こと」として扱う）。タイマーの消費（tick_invincibility()）は
        # 本メソッドが毎フレーム必ず1回呼ばれることで1フレームの経過を表す
        if self._player.is_invincible:
            self._player.tick_invincibility()
            return

        # プレイヤーの矩形とモブの矩形が1ピクセルでも重なったら HP を1
        # 減らし、無敵時間を開始し、接触したモブと反対方向へヒットバック
        # する（_collect_drops() と同じ _rects_overlap() の重なり規約。
        # 複数モブと同時に重なっても減少・ヒットバックは1フレームにつき
        # 1回で、方向は最初に見つかった接触モブから計算する）
        def hit(mob):
            return self._rects_overlap(
                self._player.image_x,
                self._player.image_y,
                Player.WIDTH,
                Player.HEIGHT,
                mob.image_x,
                mob.image_y,
                Mob.WIDTH,
                Mob.HEIGHT,
            )

        contacted_mob = next((mob for mob in self._mobs if hit(mob)), None)
        if contacted_mob is not None:
            self._player.decrease_hp()
            self._player.start_invincibility()
            # 目的地移動中であれば目的地をキャンセルし自動戦闘モードへ
            # 戻す。ヒットバック終了後は自動追尾（自動戦闘）へ戻すため
            # （hitback_from() が進行方向をモブへ上書きするため、目的地が
            # 残っていると自動追尾の抑止によりモブ方向のまま前進し続け、
            # 目的地にも到達できなくなってしまう）
            self._cancel_destination_move_to_attack()
            self._player.hitback_from(contacted_mob.x, contacted_mob.y)

    def _advance_rare_drop_level(self):
        # レアドロップの累計取得数（Player.add_rare_drop_count() 呼び出し
        # 後の最新値）が次のレベルのしきい値ちょうどに到達した瞬間だけ、
        # モブ出現間隔（_mob_spawn_interval）を半分（出現頻度2倍。上限
        # なし）にし、次のしきい値を更新する（1ずつの加算のためしきい値
        # を飛び越えることはなく一致判定のみで判定できる）。半減の対象は
        # Field 自身の状態のため、契機となるレベル判定も Player に問い
        # 合わせず Field 側で持つ（責務分離）。_try_spawn_mob() は毎フレーム
        # 呼ばれるのに対し、レア取得はドロップ回収時のみのまれな事象の
        # ため、間隔の更新は取得イベントの発生点である _collect_drops()
        # から呼ばれるここでその場実行する（毎フレームの再計算を避ける）
        if self._player.rare_drop_count == self._next_rare_level_threshold:
            self._next_rare_level_threshold = self._next_rare_level_threshold * 2 + 1
            self._mob_spawn_interval /= 2

    def _collect_drops(self):
        # プレイヤーの矩形と重なったドロップを回収（種別 is_rare に応じて
        # 通常/レアの回収数を加算）し、残ったドロップのリストを返す
        # （_resolve_bullet_mob_hits() の命中判定と同じ _rects_overlap()
        # の重なり規約）
        kept_drops = []
        for drop in self._drops:
            if self._rects_overlap(
                self._player.image_x,
                self._player.image_y,
                Player.WIDTH,
                Player.HEIGHT,
                drop.image_x,
                drop.image_y,
                Drop.WIDTH,
                Drop.HEIGHT,
            ):
                if drop.is_rare:
                    # レアドロップの累計は Player 自身の状態の関心事のため、
                    # 回収のたびに Player 側の加算メソッドを呼ぶ。累計は
                    # Player のみが保持する（Field 側の加算は持たない）
                    self._player.add_rare_drop_count()
                    self._advance_rare_drop_level()
                else:
                    # 通常ドロップの累計は Player の成長の関心事のため、
                    # 回収のたびに Player 側の加算メソッドを呼ぶ（成長への
                    # 結線）。累計は Player のみが保持する（Field 側の
                    # 加算は持たない）
                    self._player.add_normal_drop_count()
            else:
                kept_drops.append(drop)
        return kept_drops

    def _attract_drops(self):
        # 自動収集モード中にプレイヤー中心から一定範囲内へ入ったドロップへ
        # 引き寄せの速度を与え、速度を持つ（＝引き寄せを開始済みの）ドロップを
        # プレイヤーへ向かって進める（requirements.md §3.4）。
        # 開始の判定は実効モード（player_move_mode）で行う。基底モードが自動
        # 収集モードでも目的地移動中は開始しない要件のため、3値の実効モードとの
        # 一致がそのまま要件に対応する。
        # 開始済みのドロップは以降モードも範囲も参照せず、回収されるまで
        # 追い続ける（モードの切り替えで動いたり止まったりしないようにする
        # ため。引き寄せ中であることは Drop 自身が速度として保持する）
        #
        # 引き寄せ範囲はプレイヤーの成長レベルに応じて広がる（レベル0の
        # DROP_ATTRACT_RANGE から、レベルが1上がるごとに4px。レベルは
        # Player 側で0〜8へキャップ済みのため、ここでは上限を扱わず一次式
        # のみで表す）。同一フレーム内でレベルは変わらない（_collect_drops()
        # による累計取得数の加算は本メソッドの後）ため、ループの外で一度だけ
        # 求めればよい
        attract_range = self.DROP_ATTRACT_RANGE + 4 * self._player.normal_drop_level
        for drop in self._drops:
            if (
                not drop.is_attracted
                and self.player_move_mode == MoveMode.COLLECT
                and math.hypot(drop.x - self._player.x, drop.y - self._player.y)
                <= attract_range
            ):
                # 速度はプレイヤーの移動速度の2倍（requirements.md §3.4。
                # ドロップの進行方向と同じ向きへプレイヤーが移動しても
                # 追いつけるようにするため）。倍率は計算式で意図を表現し、
                # 独立した定数は持たない
                drop.start_attraction(self.PLAYER_SPEED * 2)
            if drop.is_attracted:
                drop.turn_to(self._player.x, self._player.y)
                drop.advance()

    def _remove_drops_outside_despawn_area(self):
        # 消滅領域（表示領域の縦の長さ × DROP_DESPAWN_VIEW_SCALE を一辺と
        # する、表示領域と中心を揃えた正方形）から完全にはみ出したドロップを
        # 取り除いたリストを返す（モブの _remove_outside_view() と同じ
        # 重なり規約。消滅矩形が余白付き表示領域ではなく正方形のため
        # margin 引数の形に合わず、_remove_outside_view() は流用せず
        # 独立した実装とした）
        camera_x, camera_y = self._camera_offset()
        despawn_size = self.SCREEN_HEIGHT * self.DROP_DESPAWN_VIEW_SCALE
        despawn_left = camera_x - (despawn_size - self.SCREEN_WIDTH) // 2
        despawn_top = camera_y - (despawn_size - self.SCREEN_HEIGHT) // 2
        return [
            drop
            for drop in self._drops
            if self._rects_overlap(
                drop.image_x,
                drop.image_y,
                Drop.WIDTH,
                Drop.HEIGHT,
                despawn_left,
                despawn_top,
                despawn_size,
                despawn_size,
            )
        ]

    def set_click(self, world_x, world_y):
        # ゲームクリア・ゲームオーバー到達後はクリックを無視する（目的地の
        # 設定・方向転換を行わない。ポップアップ押下によるリセットは
        # ID-017 で追加する）
        if self._is_game_end:
            return
        # クリック位置（ワールド座標）を目的地として記録し、その方向
        # （プレイヤーの画像中心点が目的地へ向かう方向）へ進行方向を変更する。
        # 目的地移動中の再クリックも同様に扱われ、新しい目的地への転換となる
        # （ID-022 で「再クリックは解除」という旧仕様〔ID-007〕を置き換えた）。
        # 目的地は Player 自身が保持する（Player はこの有無で攻撃可否を
        # 判断し〔shoot()〕、Field はこの有無から実効モードを導出する
        # 〔player_move_mode〕）
        self._player.set_destination(world_x, world_y)
        self._player.turn_to(world_x, world_y)

    def toggle_player_move_mode(self):
        # 目的地移動モード中の押下は、基底モードの2値反転ではなく目的地移動
        # からの離脱になる（requirements.md §3.1）。目的地を解除しないと
        # 実効モードの導出元が残り自動戦闘モードへ戻れないため、モブ接触時と
        # 同じ操作（_cancel_destination_move_to_attack()）を行う。起点が
        # 自動収集モードでも自動収集モードへは戻らない（到着時の「直前モード
        # へ戻る」とは非対称。ユーザー決定 2026-07-26、ID-022）
        if self.player_move_mode == MoveMode.DESTINATION:
            self._cancel_destination_move_to_attack()
            return
        self._player.set_move_mode(
            MoveMode.COLLECT
            if self._player.move_mode == MoveMode.ATTACK
            else MoveMode.ATTACK
        )

    def process_frame(self):
        # ゲームクリア・ゲームオーバー到達後はフィールドの進行（全 actor の
        # 移動・出現・消滅・回収）を止める。ゲームの進行状態は Field 自身の
        # 関心事のため、結線側（GameCore.update()）ではなくここでガードする
        # （ポップアップ押下によるリセットは ID-017 で追加する）
        if self._is_game_end:
            return
        self._track_facing()
        self._player.advance()
        # そのフレームの前進の結果、目的地へ到着していれば目的地を解除する
        # （到着判定は Player 自身の位置と目的地のみで完結するため Player が
        # 持つ。advance() の後に呼ぶことで、前進後の位置で判定する）。解除で
        # player_move_mode の導出元が消えるため、実効モードは目的地移動へ
        # 入る前の基底モードへ自動的に戻る（復元処理は不要）
        self._player.clear_destination_if_arrived()
        for mob in self._mobs:
            # 前進済みのプレイヤーの中心点を目標に、最大角度制限付きで向きを
            # 変えてから前進する（急旋回ではなく緩やかな旋回で追尾する）
            mob.turn_toward_limited(self._player.x, self._player.y)
            mob.advance()
        for bullet in self._bullets:
            # 弾は発射時点の向き（生成時に固定済み）のまま直進するのみで、
            # モブのような毎フレームの旋回は行わない
            bullet.advance()
        # そのフレームの移動結果に対して命中判定する。撃破されたモブの
        # 撃破位置にドロップを生成する（レア化確率で通常/レアを決める）。
        # 画像中心を撃破されたモブと一致させる
        self._mobs, self._bullets, destroyed_mobs = self._resolve_bullet_mob_hits()
        self._drops.extend(self._spawn_drop(mob) for mob in destroyed_mobs)
        # 弾で撃破された（生存 self._mobs から除去済みの）モブとは接触
        # ダメージを判定しない。同一フレームで撃破されたモブとの接触が
        # 二重にペナルティにならないようにするため
        self._apply_mob_contact_damage()
        # 引き寄せは前進済みのプレイヤーの位置を基準に判断し、回収より前に
        # 置く（届いたドロップは同じフレームの接触判定で回収される）
        self._attract_drops()
        self._drops = self._collect_drops()
        self._drops = self._remove_drops_outside_despawn_area()
        self._mobs = self._remove_outside_view(
            self._mobs, Mob.WIDTH, Mob.HEIGHT, self.MOB_DESPAWN_MARGIN
        )
        self._bullets = self._remove_bullets_out_of_range()
        self._try_spawn_mob()
        # 発射契機の判定・弾の生成は Player.shoot() が担う（自身の advance()
        # 呼び出し回数で発射間隔を計るのは Player 自身の責務）。Field は
        # 毎フレーム呼び出し、返却されたリスト（発射契機でなければ空）を
        # そのまま自身の弾リストへ追加するのみ
        self._bullets.extend(self._player.shoot())

    @property
    def destination(self):
        # 目的地のワールド座標。None は目的地未設定（自動追尾中）を表す
        # （保持先は Player。旗の描画〔GameCore._draw_destination_flag()〕の
        # 参照先として Field 側の IF も維持する）
        return self._player.destination

    def player_state(self):
        # 登録座標 image_x/image_y と角度（スナップ前）を返す
        return self._player.image_x, self._player.image_y, self._player.rotate_angle

    def mob_states(self):
        return [(mob.image_x, mob.image_y, mob.rotate_angle) for mob in self._mobs]

    def bullet_states(self):
        # 弾は進行方向を内部に持つが描画では回転させない（小さいスプライトを
        # 回転させると画像が歪む）ため、状態として公開するのは座標のみ
        return [(bullet.image_x, bullet.image_y) for bullet in self._bullets]

    def drop_states(self):
        # ドロップは移動・回転しないため、状態として公開するのは座標と
        # 種別（is_rare）のみ
        return [(drop.image_x, drop.image_y, drop.is_rare) for drop in self._drops]

    @property
    def player_hp(self):
        return self._player.hp

    @property
    def player_is_invincible(self):
        return self._player.is_invincible

    @property
    def normal_drop_count(self):
        return self._player.normal_drop_count

    @property
    def next_normal_drop_threshold(self):
        return self._player.next_normal_drop_threshold

    @property
    def rare_drop_count(self):
        return self._player.rare_drop_count

    @property
    def player_move_mode(self):
        # 実効モード（3値）。目的地が設定されている間が目的地移動モードで
        # あることは定義そのもののため、独立した状態としては持たず目的地の
        # 有無から導出する（同期漏れが起こり得ず、目的地の解除だけで基底
        # モードへ戻せる）。基底モード（Player.move_mode）は自動戦闘/自動
        # 収集の2値のまま保たれ、目的地移動へ入る前のモードを兼ねる
        if self._player.destination is not None:
            return MoveMode.DESTINATION
        return self._player.move_mode

    @property
    def is_game_clear(self):
        return self._player.rare_drop_count >= self.RARE_DROP_CLEAR_TARGET

    @property
    def is_game_over(self):
        return self._player.hp <= 0

    @property
    def _is_game_end(self):
        # ゲームクリア・ゲームオーバーいずれかに到達した状態。
        # process_frame()/set_click() の進行停止ガードで共通して参照する
        # 条件のため、判定式そのものを単一の情報源へ集約する（is_game_clear/
        # is_game_over は個別の判定として公開 IF・描画分岐から引き続き
        # 参照されるため残す）
        return self.is_game_clear or self.is_game_over


class GameCore:
    # 表示領域のサイズは Field を単一の情報源として参照する（GameCore が
    # 独自の値を持つと Field 側の変更と食い違う恐れがあるため）
    SCREEN_WIDTH = Field.SCREEN_WIDTH
    SCREEN_HEIGHT = Field.SCREEN_HEIGHT
    FIELD_IMG = 1
    FIELD_TILE_U = 8
    FIELD_TILE_V = 0
    FIELD_TILE_W = 30
    FIELD_TILE_H = 40
    PLAYER_IMG = 0
    PLAYER_U = 8
    PLAYER_V = 0
    # サイズは Player 自身が持つ値を単一の情報源として参照する（GameCore が
    # 独自の値を持つと Player 側の変更と食い違う恐れがあるため）
    PLAYER_W = Player.WIDTH
    PLAYER_H = Player.HEIGHT
    MOB_IMG = 0
    MOB_U = 16
    MOB_V = 0
    # サイズは Mob 自身が持つ値を単一の情報源として参照する（PLAYER_W/H と同じ理由）
    MOB_W = Mob.WIDTH
    MOB_H = Mob.HEIGHT
    # 攻撃弾のアセット（tasks.md 描画アセット表より layer0・起点 (8, 8)）
    BULLET_IMG = 0
    BULLET_U = 8
    BULLET_V = 8
    # サイズは Bullet 自身が持つ値を単一の情報源として参照する（PLAYER_W/H と同じ理由）
    BULLET_W = Bullet.WIDTH
    BULLET_H = Bullet.HEIGHT
    # ドロップのアセット（tasks.md 描画アセット表より layer0・通常 (16, 8)・
    # レア (24, 8)。レアは同じ画像バンク・サイズのまま U/V のみ異なる）
    DROP_IMG = 0
    DROP_U = 16
    DROP_V = 8
    RARE_DROP_U = 24
    RARE_DROP_V = 8
    # サイズは Drop 自身が持つ値を単一の情報源として参照する（PLAYER_W/H と同じ理由）
    DROP_W = Drop.WIDTH
    DROP_H = Drop.HEIGHT
    FLAG_IMG = 0
    FLAG_U = 8
    FLAG_V = 16
    FLAG_W = 6
    FLAG_H = 8
    # 旗の根本（旗竿が地面に接する点）に対応する画像内ローカル座標
    # （tasks.md 描画アセット表より）。旗は回転しない目印のため、この座標が
    # 目的地のワールド座標と一致するよう描画位置を決める
    FLAG_BASE_X = 0
    FLAG_BASE_Y = 7
    # スプライト画像の色0を透明色として扱う（背景色が矩形のまま描画されるのを防ぐ）
    COLKEY = 0
    # Pyxel の blt rotate は中途半端な角度を指定すると小さいスプライトで
    # 画像が崩れて描画されるため、描画時にこの単位（度数法）へスナップする
    ROTATE_SNAP_STEP = 22.5
    # 無敵時間中のプレイヤー点滅描画の周期（IView.get_frame() のフレーム数を
    # この値で割った余りで非表示/表示を切り替える）と、周期のうち非表示と
    # する先頭フレーム数（参考実装 pyxel_connect_city の
    # PyxelView.get_frame() を用いたアニメーション処理にならう。2フレーム
    # ごとに描画の有無が切り替わる点滅として Red（ID-015-11）で決定した値）
    BLINK_CYCLE_FRAMES = 4
    BLINK_HIDDEN_FRAMES = 2
    # Pyxel 標準フォントの1文字の送り幅・グリフ高（テキストの表示幅・
    # 表示高の計算に使う。送り幅は文字間の余白 1px を含むため、実際の
    # 表示幅は末尾の余白分だけ短いが、中央寄せでは±1px の違いは視認
    # できないため送り幅×文字数で近似する）
    FONT_CHAR_W = 4
    FONT_GLYPH_H = 5
    # ステータス HUD の RARE 表示（クリア必要数）は Field を単一の情報源
    # として参照する（PLAYER_W/H 等と同じ理由）
    RARE_DROP_CLEAR_TARGET = Field.RARE_DROP_CLEAR_TARGET
    # ステータス HUD（HP・通常/レアドロップ数）の表示仕様。プレイヤーは
    # 常に画面中央付近に描画されるため、行動の観測を妨げにくい画面左上へ
    # 横1行で表示する（具体値は描画結線テスト TestStatusDraw が固定する）。
    # 背景は画面左端（x=0）にぴったりくっつけて描画する単一の矩形とし、
    # 項目間・内部にすき間を作らないことで、フィールドタイルの描画が項目間に
    # ちらついて見える問題を避ける
    # Pyxel 標準フォント（グリフ 5px 高）+ 上下パディング 2px
    STATUS_RECT_H = 9
    # 背景矩形の横幅は画面全体（右端まで隙間なく覆う）: 項目分の幅だけに
    # 留めると右側だけ空いて不自然に見える、というプレイテスト指摘を反映し、
    # 表示領域のサイズを単一の情報源として持つ既存の SCREEN_WIDTH をそのまま
    # 使う
    STATUS_RECT_W = SCREEN_WIDTH
    # 背景は色1（濃い青）。テキストの色7（白・PyxelView 固定）とのコント
    # ラストで視認性を確保する
    STATUS_RECT_COLOR = 1
    # 矩形内のテキスト左・上パディング（上下対称になる）
    STATUS_TEXT_OFFSET = 2
    # 項目間の余白（2026-07-19 人間プレイテスト指摘により追加。旧
    # STATUS_SLOT_W〔均一60px×3項目=180px〕は SCREEN_WIDTH（150px）を
    # 超えており、3項目目〔RARE〕が画面右端で見切れる不具合があった。
    # HP/DROP間の隙間が広すぎるという指摘も合わせ、各項目を想定最大文字数
    # ぶんの幅で左詰めし、項目間はこの最小限の余白のみで区切る設計へ変更
    # する）。初回の値（4px）は HP/DROP 間の隙間が DROP/RARE 間（実際の
    # 表示文字数が短い序盤ほど、予約幅の余りにより見かけ上広く見える）に
    # 比べて狭すぎるという再指摘を受け、全項目のペア間で一貫した見た目の
    # 余白になるよう12pxへ拡大した（RARE:20/20到達時でも描画終端135pxと
    # なりSCREEN_WIDTH=150pxに収まる最大値19pxより余裕を持たせた値）
    STATUS_ITEM_GAP = 12
    # DROP・RARE表示をまとめて右へずらす追加オフセット（2026-07-20
    # 人間プレイテスト指摘: HP-DROP間の余白〔STATUS_ITEM_GAP=12px〕に
    # 比べ、RARE表示の右側の余白〔画面幅150px−RARE終端109px＝41px〕が
    # 広く感じられるという指摘を受け、DROP・RARE表示をまとめて右へ
    # 約10pxずらす〔HP-DROP間の余白は12→22pxに広がるが、RARE右側の
    # 余白は41→31pxに縮み、指摘された余白の偏りが緩和される〕。HPの
    # 位置・DROP-RARE間の余白〔STATUS_ITEM_GAP〕はそのまま変更しない）
    STATUS_DROP_GROUP_OFFSET = 10
    # RARE の想定最大文字数（位置を固定するための基準。カウント増加の
    # たびに幅が変わって表示がちらつくのを避けるため、実際の現在値ではなく
    # 想定最大文字数を基準にする設計思想は旧 STATUS_SLOT_W から踏襲する）。
    # ラベル文字（"RARE:"）は ID-019 サイクル2でアイコンへ置き換えたため、
    # DROP と同じくラベルを除いた数値部分のみを基準にする。クリア必要数
    # RARE_DROP_CLEAR_TARGET が分子・分母の最大値になるため
    # "{クリア必要数}/{クリア必要数}" の長さを使う
    RARE_NUMBER_MAX_CHARS = len(f"{RARE_DROP_CLEAR_TARGET}/{RARE_DROP_CLEAR_TARGET}")
    # HP のハートアイコン表示（requirements.md §4「HPはハートアイコンを
    # 3つ並べて表示する」）。アセットは他スプライトと同じバンク0の
    # 赤ハート画像（起点 (32,8)、5×4）
    HEART_IMG = 0
    HEART_U = 32
    HEART_V = 8
    HEART_W = 5
    HEART_H = 4
    # ハート同士のすき間: ハート画像は中段の横一列が 5px 幅の左右端まで
    # 達する形状のため、すき間なしで並べると隣接ハートと繋がって見える。
    # 1px のすき間で区切る
    HEART_GAP = 1
    # HP 減少分（灰色）のハート画像。バンク・サイズは赤ハートと同じで、
    # 起点のみ異なる（requirements.md §4「減少したHPを灰色のハートアイコン
    # で表示できる」）
    HEART_GRAY_U = 40
    HEART_GRAY_V = 8
    # ハートの縦位置（人間プレイテスト指摘により2026-07-20改訂）:
    # STATUS_TEXT_OFFSET（=2）のままだとハート（高さ4px）は矩形（高さ9px）
    # の中で上2px・下3pxとなり、テキスト（高さ5px、上下2px対称で中央）に
    # 比べて上寄りに見える。1px下げて上3px・下2pxにする方が中央寄りに
    # 見えるという指摘を反映し、STATUS_TEXT_OFFSET + 1 とする（テキストの
    # y座標自体は変更しない）
    HEART_Y_OFFSET = STATUS_TEXT_OFFSET + 1
    # HP 項目の表示幅（ハート Player.INITIAL_HP 個分 + 間のすき間。HP 上限は
    # 常に Player.INITIAL_HP＝3 固定のため、並べる個数・表示幅も固定でよい）
    HEART_ITEM_W = Player.INITIAL_HP * HEART_W + (Player.INITIAL_HP - 1) * HEART_GAP
    # 通常ドロップ数のアイコン表示（requirements.md §4「ドロップ数のラベルを
    # ドロップ画像のアイコンで表示できる」）。アイコン画像はフィールド描画と
    # 同じ DROP_IMG/DROP_U/DROP_V/DROP_W/DROP_H を流用する
    # アイコンと数値テキストの間のすき間: HEART_GAP（1px、隣接ハート同士の
    # すき間）よりも一回り広く取り、アイコン（4px高）と数値テキスト
    # （グリフ5px高）の境界を判別しやすくする
    DROP_ICON_GAP = 2
    # DROP 項目の想定最大文字数はラベルを除いた数値部分のみ（成長上限直前の
    # "2549/2550" の9文字。しきい値の系列 10×(2^level−1)、level=8 で最大
    # 2550。ID-016-17 と同じ根拠）
    DROP_NUMBER_MAX_CHARS = len("2549/2550")
    # アイコンの縦位置: ハートと同じ考え方（アイコン高4px はテキストの
    # グリフ高5pxより1px低いため、STATUS_TEXT_OFFSET+1で中央寄せに揃える）
    DROP_ICON_Y_OFFSET = STATUS_TEXT_OFFSET + 1
    # 各項目（HP/DROP/RARE）の描画開始x（カメラオフセットからの相対値）。
    # 左詰めで、直前の項目の表示幅（HP はハートアイコン列の HEART_ITEM_W、
    # DROP はアイコン幅+すき間+数値部分の想定最大幅〔DROP_W+DROP_ICON_GAP+
    # DROP_NUMBER_MAX_CHARS×FONT_CHAR_W−1px〕。末尾の送り分は実際の描画幅に
    # 含まれないため−1px）+ STATUS_ITEM_GAP ぶんだけ右へ積み上げる。HP→
    # DROP間のみ STATUS_DROP_GROUP_OFFSET ぶん追加で広げ、DROP・RARE表示を
    # まとめて右へずらす（プレイテスト指摘対応。DROP-RARE間の余白
    # STATUS_ITEM_GAP は変更しない）。RARE は最後の項目のため後続の項目
    # 位置の計算には使わないが、RARE 自身のアイコン+すき間+数値部分の
    # 想定最大幅〔DROP_W+DROP_ICON_GAP+RARE_NUMBER_MAX_CHARS×FONT_CHAR_W
    # −1px〕を加えても SCREEN_WIDTH（150px）に収まる（HP:2px開始、
    # DROP:41px開始、RARE:94px開始+最大想定幅25px=119px で画面内に収まる）
    STATUS_ITEM_X = (
        STATUS_TEXT_OFFSET,
        STATUS_TEXT_OFFSET + HEART_ITEM_W + STATUS_ITEM_GAP + STATUS_DROP_GROUP_OFFSET,
        STATUS_TEXT_OFFSET
        + HEART_ITEM_W
        + STATUS_ITEM_GAP
        + STATUS_DROP_GROUP_OFFSET
        + (DROP_W + DROP_ICON_GAP + DROP_NUMBER_MAX_CHARS * FONT_CHAR_W - 1)
        + STATUS_ITEM_GAP,
    )
    # 終了（ゲームクリア）ポップアップの表示仕様。位置・サイズは参考実装
    # pyxel_sort_water/ID-005 のポップアップ定数を同じ画面サイズ 150×200 の
    # ため流用し、画面中央付近へ表示する（具体値は描画結線テスト
    # TestGameClearPopupDraw が固定する）。サイクル4で "GAME OVER" にも
    # 共用するため CLEAR_POPUP_* ではなく END_POPUP_* と命名する
    END_POPUP_X = 25
    END_POPUP_Y = 85
    END_POPUP_W = 100
    END_POPUP_H = 30
    # 背景はステータス HUD と同じ色1（濃い青）。テキストの色7（白・
    # PyxelView 固定）とのコントラストで視認性を確保する
    END_POPUP_COLOR = 1
    # 終了ポップアップ2行目（再起動案内）の行間・文言。参考実装
    # pyxel_sort_water/ID-005 の RESTART_TEXT／LINE_GAP と同じ値を流用する
    END_POPUP_LINE_GAP = 4
    RESTART_TEXT = "CLICK TO RESTART"

    # 移動モード切り替えボタンの表示仕様（requirements.md §3.1「画面右下に
    # 移動モード切り替えボタンを表示する」）。画像アセットは登録済みの
    # layer0（他スプライトと同じバンク0）の自動攻撃/自動収集モードアイコン
    # （起点 (16,16)/(24,16)、いずれも 6×8）
    MODE_BUTTON_IMG = 0
    MODE_BUTTON_ATTACK_U = 16
    MODE_BUTTON_ATTACK_V = 16
    MODE_BUTTON_COLLECT_U = 24
    MODE_BUTTON_COLLECT_V = 16
    MODE_BUTTON_ICON_W = 6
    MODE_BUTTON_ICON_H = 8
    # ボタンの円形背景の半径・色。自動戦闘モードの色はステータス HUD・
    # 終了ポップアップの色1（濃い青）とは別の色2（濃い赤）とし、他の HUD
    # 要素と見分けやすくする。自動収集モードの色は色3（緑）とする
    # （2026-07-23 ユーザー指示）。目的地移動モードの色は青（色5）とする
    # （ユーザー決定 2026-07-25、ID-022）
    MODE_BUTTON_RADIUS = 12
    MODE_BUTTON_COLOR_ATTACK = 2
    MODE_BUTTON_COLOR_COLLECT = 3
    MODE_BUTTON_COLOR_DESTINATION = 5
    # モード →（アイコン起点U, アイコン起点V, 円形背景色）の対応表。モードが
    # 増えるたびに _draw_mode_button() の分岐を増やすのではなく、この表へ
    # 1行追加するだけで済むようにする（_draw_status() でドロップ／
    # レアドロップの描画をタプルの1ループへまとめたのと同じ設計判断。ID-022
    # Refactor）。目的地移動モードのアイコンは新規アセットを追加せず、既存の
    # 目的地の旗の起点座標（FLAG_U/FLAG_V）を単一の情報源として参照する
    # （ユーザー決定 2026-07-25、ID-022）
    MODE_BUTTON_ICON_AND_COLOR_BY_MODE = {
        MoveMode.ATTACK: (
            MODE_BUTTON_ATTACK_U,
            MODE_BUTTON_ATTACK_V,
            MODE_BUTTON_COLOR_ATTACK,
        ),
        MoveMode.COLLECT: (
            MODE_BUTTON_COLLECT_U,
            MODE_BUTTON_COLLECT_V,
            MODE_BUTTON_COLOR_COLLECT,
        ),
        MoveMode.DESTINATION: (FLAG_U, FLAG_V, MODE_BUTTON_COLOR_DESTINATION),
    }
    # 円の外周に重ねる白枠の色。テキストの色7（白・PyxelView 固定）と
    # 同じ色を使い、既存の白系配色と統一する
    MODE_BUTTON_BORDER_COLOR = 7
    # 円の外周と画面右端・下端の間に空ける余白
    MODE_BUTTON_MARGIN = 10
    # 円の中心座標（画面右下）＝ 画面端 − 余白 − 半径
    # （= 150−10−12=128, 200−10−12=178。円の外周〔半径12px+余白10px=22px〕は
    # 画面端から22px内側となり、画面外へのはみ出しはない）
    MODE_BUTTON_CENTER_X = SCREEN_WIDTH - MODE_BUTTON_MARGIN - MODE_BUTTON_RADIUS
    MODE_BUTTON_CENTER_Y = SCREEN_HEIGHT - MODE_BUTTON_MARGIN - MODE_BUTTON_RADIUS
    # アイコンは重心が円の中心と一致するよう、中心からアイコン幅・高さの
    # 半分だけ左上へずらした位置に描画する。X はさらに +1px
    # （= 128−6//2+1=126, 178−8//2=174。2026-07-23 プレイテストでアイコンが
    # わずかに左寄りに見えると指摘され、見た目の中央寄せを補正するための
    # 微調整）
    MODE_BUTTON_ICON_X = MODE_BUTTON_CENTER_X - MODE_BUTTON_ICON_W // 2 + 1
    MODE_BUTTON_ICON_Y = MODE_BUTTON_CENTER_Y - MODE_BUTTON_ICON_H // 2
    # ボタンの当たり判定は円周ちょうどではなく外接矩形で行う（境界条件を
    # テストで固定する意義が薄いため、既存の END_POPUP_* と同じ矩形判定の
    # 考え方に揃える）
    MODE_BUTTON_RECT_X = MODE_BUTTON_CENTER_X - MODE_BUTTON_RADIUS
    MODE_BUTTON_RECT_Y = MODE_BUTTON_CENTER_Y - MODE_BUTTON_RADIUS
    MODE_BUTTON_RECT_W = MODE_BUTTON_RADIUS * 2
    MODE_BUTTON_RECT_H = MODE_BUTTON_RADIUS * 2

    def __init__(self):
        self._view = PyxelView.create()
        self._input = PyxelInput.create()
        # actor（プレイヤー・モブ）関連の状態と挙動ロジックは Field が持つ
        self._field = Field()
        self._needs_reset = False

    @property
    def needs_reset(self):
        return self._needs_reset

    def update(self):
        # タップの入力判定とワールド座標変換 → Field へのクリック指定 →
        # Field のフレーム処理、という結線のみを担う（actor の挙動ロジックの
        # 実体は Field 側にある。ゲームクリア到達後の進行停止も Field 自身が
        # set_click()/process_frame() の中でガードする）
        self._handle_tap()
        self._field.process_frame()

    @staticmethod
    def _is_point_in_rect(x, y, rect_x, rect_y, rect_w, rect_h):
        # 半開区間（[rect_x, rect_x+rect_w) × [rect_y, rect_y+rect_h)）での
        # 矩形内判定。_is_end_popup_clicked()/_is_mode_button_clicked() の
        # 両方が同じ形の判定だったため Refactor で共通化した
        return rect_x <= x < rect_x + rect_w and rect_y <= y < rect_y + rect_h

    def _is_end_popup_clicked(self):
        return self._is_point_in_rect(
            self._input.mouse_x,
            self._input.mouse_y,
            self.END_POPUP_X,
            self.END_POPUP_Y,
            self.END_POPUP_W,
            self.END_POPUP_H,
        )

    def _is_mode_button_clicked(self):
        return self._is_point_in_rect(
            self._input.mouse_x,
            self._input.mouse_y,
            self.MODE_BUTTON_RECT_X,
            self.MODE_BUTTON_RECT_Y,
            self.MODE_BUTTON_RECT_W,
            self.MODE_BUTTON_RECT_H,
        )

    def _handle_tap(self):
        if not self._input.is_btn_pressed():
            return
        # 終了状態（クリア／オーバー）中のクリックは目的地移動ではなく
        # ポップアップ押下によるリセット要求として扱う（ポップアップ矩形外
        # のクリックは無視する）
        if self._field.is_game_over or self._field.is_game_clear:
            if self._is_end_popup_clicked():
                self._needs_reset = True
            return
        # 移動モード切り替えボタンの押下は目的地移動ではなくモード切替として
        # 扱う（Field.set_click() へは委譲しない）。モードの状態自体は
        # Field（Player）が保持する（モードに応じた実際の挙動＝攻撃停止・
        # 追尾先の切替を Player/Field が担うため）ため、他の Field 参照
        # （set_click() 等）と同様にここから直接呼び出す
        if self._is_mode_button_clicked():
            self._field.toggle_player_move_mode()
            return
        # タップ位置（スクリーン座標）をカメラオフセットでワールド座標へ
        # 変換し、Field へクリック位置として伝える（目的地としての設定は
        # Field の責務）
        camera_x, camera_y = self._camera_offset()
        world_x = self._input.mouse_x + camera_x
        world_y = self._input.mouse_y + camera_y
        self._field.set_click(world_x, world_y)

    @staticmethod
    def _visible_tile_range(camera, screen_size, tile_size):
        first = camera // tile_size
        last = (camera + screen_size - 1) // tile_size
        return range(first, last + 1)

    def _draw_field(self):
        camera_x, camera_y = self._camera_offset()
        cols = self._visible_tile_range(camera_x, self.SCREEN_WIDTH, self.FIELD_TILE_W)
        rows = self._visible_tile_range(camera_y, self.SCREEN_HEIGHT, self.FIELD_TILE_H)
        for row in rows:
            for col in cols:
                self._view.draw_blt(
                    col * self.FIELD_TILE_W,
                    row * self.FIELD_TILE_H,
                    self.FIELD_IMG,
                    self.FIELD_TILE_U,
                    self.FIELD_TILE_V,
                    self.FIELD_TILE_W,
                    self.FIELD_TILE_H,
                    self.COLKEY,
                )

    def _snap_rotate_angle(self, angle):
        snapped = round(angle / self.ROTATE_SNAP_STEP) * self.ROTATE_SNAP_STEP
        # 丸めにより -180（範囲の下限を含んでしまい規約外）になる場合は、
        # 同じ向きを表す範囲内の値 180 へ読み替える
        return 180 if snapped == -180 else snapped

    def _draw_actor(self, x, y, rotate_angle, img, u, v, w, h):
        self._view.draw_blt(
            x,
            y,
            img,
            u,
            v,
            w,
            h,
            self.COLKEY,
            rotate=self._snap_rotate_angle(rotate_angle),
        )

    def _draw_drops(self):
        # ドロップは移動・回転しない地面の拾い物のため回転なしで描画する。
        # レアは同じ画像バンク・サイズのまま U/V のみ切り替える
        for drop_x, drop_y, is_rare in self._field.drop_states():
            self._draw_actor(
                drop_x,
                drop_y,
                0,
                self.DROP_IMG,
                self.RARE_DROP_U if is_rare else self.DROP_U,
                self.RARE_DROP_V if is_rare else self.DROP_V,
                self.DROP_W,
                self.DROP_H,
            )

    def _draw_bullets(self):
        # 弾は進行方向を内部に持つが、小さいスプライトを回転させると画像が
        # 歪むため、向きによらず回転なし（回転 0）で描画する
        for bullet_x, bullet_y in self._field.bullet_states():
            self._draw_actor(
                bullet_x,
                bullet_y,
                0,
                self.BULLET_IMG,
                self.BULLET_U,
                self.BULLET_V,
                self.BULLET_W,
                self.BULLET_H,
            )

    def _draw_mobs(self):
        for mob_x, mob_y, mob_rotate in self._field.mob_states():
            self._draw_actor(
                mob_x,
                mob_y,
                mob_rotate,
                self.MOB_IMG,
                self.MOB_U,
                self.MOB_V,
                self.MOB_W,
                self.MOB_H,
            )

    def _is_player_hidden_for_blink(self):
        # 無敵時間中は被弾を視覚的に示すため、周期 BLINK_CYCLE_FRAMES の
        # 先頭 BLINK_HIDDEN_FRAMES フレームは描画を省略する（点滅）。無敵中
        # でなければ常に描画する
        if not self._field.player_is_invincible:
            return False
        return (
            self._view.get_frame() % self.BLINK_CYCLE_FRAMES < self.BLINK_HIDDEN_FRAMES
        )

    def _draw_player(self):
        if self._is_player_hidden_for_blink():
            return
        player_x, player_y, player_rotate = self._field.player_state()
        self._draw_actor(
            player_x,
            player_y,
            player_rotate,
            self.PLAYER_IMG,
            self.PLAYER_U,
            self.PLAYER_V,
            self.PLAYER_W,
            self.PLAYER_H,
        )

    def _camera_offset(self):
        player_x, player_y, _ = self._field.player_state()
        return (
            player_x - (self.SCREEN_WIDTH - self.PLAYER_W) // 2,
            player_y - (self.SCREEN_HEIGHT - self.PLAYER_H) // 2,
        )

    def _draw_destination_flag(self):
        destination = self._field.destination
        if destination is None:
            return
        dest_x, dest_y = destination
        # 根本（FLAG_BASE_X, FLAG_BASE_Y）が目的地＝タップ位置のワールド座標と
        # 一致するよう、その分だけ描画位置をずらす（向きを持たない地面の目印の
        # ため回転なし）。プレイヤーは画像中心点が目的地へ向かって移動するため、
        # 到着時にプレイヤーの見た目の中心が旗の根本と一致する
        self._view.draw_blt(
            dest_x - self.FLAG_BASE_X,
            dest_y - self.FLAG_BASE_Y,
            self.FLAG_IMG,
            self.FLAG_U,
            self.FLAG_V,
            self.FLAG_W,
            self.FLAG_H,
            self.COLKEY,
        )

    def _draw_status(self):
        # ステータスはスクリーン上の固定位置に表示し続ける HUD のため、
        # clear() が設定したカメラオフセットを足したワールド座標へ描画する。
        # 画面幅いっぱいの単一の背景矩形（画面左端にぴったりくっつけ、
        # 右端まで覆う） → HP のハートアイコン → 通常ドロップのアイコン＋
        # 数値テキスト → レアドロップのアイコン＋数値テキストの順で描画し、
        # 矩形を数値の背景として機能させる（項目の並びは requirements.md §4
        # の列挙順のまま左から横1行に並べる）。各項目は STATUS_ITEM_X の
        # 固定位置へ左詰めで描画され、項目間は STATUS_ITEM_GAP の最小限の
        # 余白のみで区切る
        camera_x, camera_y = self._camera_offset()
        # 次のレベルの累計しきい値が存在しない（成長上限到達後）場合は
        # 「次がない」ことを表す文字として "-" を使う
        next_threshold = self._field.next_normal_drop_threshold
        next_threshold_text = "-" if next_threshold is None else str(next_threshold)
        drop_number_text = f"{self._field.normal_drop_count}/{next_threshold_text}"
        rare_number_text = (
            f"{self._field.rare_drop_count}/{self.RARE_DROP_CLEAR_TARGET}"
        )
        self._view.draw_rect(
            camera_x,
            camera_y,
            self.STATUS_RECT_W,
            self.STATUS_RECT_H,
            self.STATUS_RECT_COLOR,
        )
        # HP はテキストではなくハートアイコンで表示する。左から現在HP個ぶん
        # 赤ハート、残りは灰色ハートへ切り替える（requirements.md §4）。
        # HP 項目の開始xから左詰めで HEART_GAP のすき間をあけて横に並べる。
        # 縦位置は HEART_Y_OFFSET を使う（テキストと同じ STATUS_TEXT_OFFSET
        # だと矩形内で上寄りに見えるという人間プレイテスト指摘により、
        # テキストとは別のy座標に改訂）
        for i in range(Player.INITIAL_HP):
            is_lost = i >= self._field.player_hp
            self._view.draw_blt(
                camera_x + self.STATUS_ITEM_X[0] + i * (self.HEART_W + self.HEART_GAP),
                camera_y + self.HEART_Y_OFFSET,
                self.HEART_IMG,
                self.HEART_GRAY_U if is_lost else self.HEART_U,
                self.HEART_GRAY_V if is_lost else self.HEART_V,
                self.HEART_W,
                self.HEART_H,
                self.COLKEY,
            )
        # 通常ドロップ数・レアドロップ数はテキストではなくドロップ画像の
        # アイコン＋数値のみのテキストで表示する（requirements.md §4）。
        # 両者は起点座標（U/V）以外は完全に同型の処理（アイコンサイズ・
        # すき間・縦位置は共通）のため、フィールド描画の is_rare 分岐
        # （L1223-1224付近）と同じ考え方で、項目の開始x・起点座標・数値
        # テキストをタプルにまとめて1ループで描画する（HP の赤/灰ハートを
        # 1ループへ統合したのと同じ設計判断）。アイコンは項目の開始xへ、
        # 数値テキストはアイコン幅＋DROP_ICON_GAP ぶん右へずらして続けて
        # 描画する
        for item_x, drop_u, drop_v, number_text in (
            (self.STATUS_ITEM_X[1], self.DROP_U, self.DROP_V, drop_number_text),
            (
                self.STATUS_ITEM_X[2],
                self.RARE_DROP_U,
                self.RARE_DROP_V,
                rare_number_text,
            ),
        ):
            self._view.draw_blt(
                camera_x + item_x,
                camera_y + self.DROP_ICON_Y_OFFSET,
                self.DROP_IMG,
                drop_u,
                drop_v,
                self.DROP_W,
                self.DROP_H,
                self.COLKEY,
            )
            self._view.draw_text(
                camera_x + item_x + self.DROP_W + self.DROP_ICON_GAP,
                camera_y + self.STATUS_TEXT_OFFSET,
                number_text,
            )

    def _draw_mode_button(self):
        # 移動モード切り替えボタンはステータスと同様にスクリーン上の固定
        # 位置に表示し続ける HUD のため、カメラオフセットを足したワールド
        # 座標へ描画する。円形背景（塗りつぶし） → フィールドとの境界を
        # 見やすくする白枠 → 中心に重ねたアイコンの順で描画する。アイコンと
        # 背景色は現在の移動モード（Field が保持する）に応じて
        # MODE_BUTTON_ICON_AND_COLOR_BY_MODE から引く
        camera_x, camera_y = self._camera_offset()
        icon_u, icon_v, button_color = self.MODE_BUTTON_ICON_AND_COLOR_BY_MODE[
            self._field.player_move_mode
        ]
        self._view.draw_circ(
            camera_x + self.MODE_BUTTON_CENTER_X,
            camera_y + self.MODE_BUTTON_CENTER_Y,
            self.MODE_BUTTON_RADIUS,
            button_color,
        )
        self._view.draw_circb(
            camera_x + self.MODE_BUTTON_CENTER_X,
            camera_y + self.MODE_BUTTON_CENTER_Y,
            self.MODE_BUTTON_RADIUS,
            self.MODE_BUTTON_BORDER_COLOR,
        )
        self._view.draw_blt(
            camera_x + self.MODE_BUTTON_ICON_X,
            camera_y + self.MODE_BUTTON_ICON_Y,
            self.MODE_BUTTON_IMG,
            icon_u,
            icon_v,
            self.MODE_BUTTON_ICON_W,
            self.MODE_BUTTON_ICON_H,
            self.COLKEY,
        )

    def _draw_end_popup(self, text):
        # 終了ポップアップはスクリーン上の固定位置に表示する HUD のため、
        # ステータスと同様にカメラオフセットを足したワールド座標へ描画する。
        # 背景矩形 → 中央寄せテキスト（判定結果 → 再起動案内の2行）の順で
        # 描画し、矩形をテキストの背景として機能させる
        camera_x, camera_y = self._camera_offset()
        self._view.draw_rect(
            camera_x + self.END_POPUP_X,
            camera_y + self.END_POPUP_Y,
            self.END_POPUP_W,
            self.END_POPUP_H,
            self.END_POPUP_COLOR,
        )
        # 2行（text／RESTART_TEXT）をブロックとしてポップアップ縦中央に
        # 配置する（pyxel_sort_water/ID-005 の _draw_clear_popup と同じ
        # レイアウト計算）。各行は「矩形の中心 − テキストの半幅」で
        # 横中央寄せする
        lines = (text, self.RESTART_TEXT)
        block_h = len(lines) * self.FONT_GLYPH_H + (len(lines) - 1) * (
            self.END_POPUP_LINE_GAP
        )
        top_y = self.END_POPUP_Y + self.END_POPUP_H // 2 - block_h // 2
        for i, line in enumerate(lines):
            line_w = len(line) * self.FONT_CHAR_W
            line_x = self.END_POPUP_X + self.END_POPUP_W // 2 - line_w // 2
            line_y = top_y + i * (self.FONT_GLYPH_H + self.END_POPUP_LINE_GAP)
            self._view.draw_text(camera_x + line_x, camera_y + line_y, line)

    def draw(self):
        self._view.clear(*self._camera_offset())
        self._draw_field()
        # 目的地の旗は地面の目印としてフィールドの直後（弾・モブ・プレイヤー
        # より奥）に描画する
        self._draw_destination_flag()
        # ドロップは地面に落ちている拾い物として旗の直後（弾・モブ・
        # プレイヤーより奥）に描画し、重なった場合に actor を手前に表示する
        self._draw_drops()
        # 弾はモブ・プレイヤーより奥に描画し、重なった場合にモブ・プレイヤーを
        # 手前に表示する
        self._draw_bullets()
        # モブをプレイヤーより先に描画し、重なった場合にプレイヤーを手前に表示する
        self._draw_mobs()
        self._draw_player()
        # ステータスは最前面の HUD として全ワールド要素の後に描画する
        self._draw_status()
        # 移動モード切り替えボタンはステータス HUD の直後・終了ポップアップ
        # より前に描画する（ポップアップは全描画要素の最前面という既存の
        # invariant を維持するため）
        self._draw_mode_button()
        # ゲームクリア・ゲームオーバー到達後は終了ポップアップをステータス
        # よりさらに手前＝全描画要素の最前面へ描画する（両方が同時に真になる
        # 場合の優先順位はプレイ中に作りにくい境界条件のため要件・テストと
        # して固定していないが、実装上は is_game_over を先に判定する）
        if self._field.is_game_over:
            self._draw_end_popup("GAME OVER")
        elif self._field.is_game_clear:
            self._draw_end_popup("CLEAR")


class App:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(
            GameCore.SCREEN_WIDTH, GameCore.SCREEN_HEIGHT, title="pyxel drop hunt"
        )
        pyxel.load("images.pyxres")
        pyxel.mouse(True)
        self._core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        if self._core.needs_reset:
            self._core = GameCore()
        else:
            self._core.update()

    def draw(self):
        self._core.draw()


if __name__ == "__main__":
    App()
