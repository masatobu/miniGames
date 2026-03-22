import math
from enum import Enum

from fish import FishSize


class HookState(str, Enum):
    IDLE = "idle"
    THROWING = "throwing"
    SURFACE = "surface"
    SINKING = "sinking"
    REELING = "reeling"
    FINISHED_SUCCESS = "finished_success"  # 手元到達（釣り上げ成功）
    FINISHED_FAIL = "finished_fail"  # 画面外・糸切れ・沈下超過（釣り失敗）


class BaitType(str, Enum):
    FLOAT_BAIT = "float_bait"
    LURE = "lure"


class Hook:
    # --- 投擲パラメータ ---
    GRAVITY = 0.5  # 重力加速度（毎フレーム vy に加算）

    # --- 充電・速度変換パラメータ ---
    MIN_CHARGE_FRAMES = 10  # 最小充電フレーム数
    MAX_CHARGE_FRAMES = 60  # 最大充電フレーム数（これ以上は上限でキャップ）
    MIN_VX = -1.5  # 最小充電時の初速度 X
    MAX_VX = -6.5  # 最大充電時の初速度 X
    MIN_VY = -3.0  # 最小充電時の初速度 Y
    MAX_VY = -6.0  # 最大充電時の初速度 Y

    # --- 水面停止パラメータ ---
    SURFACE_PAUSE_FRAMES = 8  # 水面停止フレーム数（30fps × 8 = 約0.27秒）

    # --- 巻き上げパラメータ ---
    REEL_SPEED = 2  # 巻き上げ速度（毎フレーム px）
    REEL_SPEED_WITH_FISH_MAP = {  # サイズ別巻き上げ速度（大きいほど遅い）
        FishSize.SMALL: 1.5,
        FishSize.MEDIUM_S: 1.0,
        FishSize.MEDIUM_L: 0.7,
        FishSize.LARGE: 0.5,
    }
    REEL_FINISH_DIST = 6  # 手元到達とみなす距離（px）: y_gap=2 を上回り水面到達を可能にする（プレイテストで微調整）
    REEL_LINE_BREAK_FRAMES_MAP = {  # サイズ別糸切れフレーム数（大きいほど短い）
        FishSize.SMALL: 120,  # 約4秒
        FishSize.MEDIUM_S: 90,  # 約3秒
        FishSize.MEDIUM_L: 60,  # 約2秒
        FishSize.LARGE: 45,  # 約1.5秒
    }

    # --- 有効範囲（この範囲を外れると FINISHED に遷移）---
    FINISH_X_MIN = 0  # X 方向の左端
    FINISH_X_MAX = 240  # X 方向の右端

    # --- 沈下パラメータ ---
    FINISH_Y_MAX = 320  # 沈下の下限 Y 座標（この値以上で FINISHED に遷移）
    FLOAT_BAIT_DEPTH = 16  # 浮餌の停止深度（水面から 16px 下 ≒ 水域全体の約1/14）
    SINK_VY_MAP = {  # えさ種類 → 沈下速度のマッピング（毎フレーム px）
        BaitType.FLOAT_BAIT: 1,
        BaitType.LURE: 1,
    }

    def __init__(self, x, y, water_y):
        self._state = HookState.IDLE
        self._x = x
        self._y = y
        self._throw_x = x  # 投擲起点 X（REELING 移動の目標）
        self._throw_y = y  # 投擲起点 Y（REELING 移動の目標）
        self._vx = 0
        self._vy = 0
        self._water_y = water_y
        self._bait_type = BaitType.FLOAT_BAIT
        self._surface_timer = 0
        self._charging_frames = 0
        self._is_charging = False
        self._has_fish = False
        self._reel_with_fish_frames = 0
        self._reel_speed_with_fish = 0.0  # hook_fish() で魚サイズに応じた値に設定される
        self._reel_line_break_frames = (
            0  # hook_fish() で REEL_LINE_BREAK_FRAMES_MAP の値に設定される
        )

    @property
    def bait_type(self) -> BaitType:
        return self._bait_type

    def set_bait_type(self, value: BaitType):
        self._bait_type = value

    @property
    def state(self):
        return self._state

    @property
    def x(self) -> int:
        return int(self._x)

    @property
    def y(self) -> int:
        return int(self._y)

    @property
    def charge_ratio(self) -> float:
        """充電進捗の割合（0.0〜1.0）。MIN_CHARGE_FRAMES 未満は 0.0 を返す。

        MIN_CHARGE_FRAMES 未満（タップ相当）は充電とみなさず 0.0 を返すことで、
        呼び出し元は 0.0 チェックのみで非表示を判断できる。
        """
        if self._charging_frames < self.MIN_CHARGE_FRAMES:
            return 0.0
        return min(1.0, self._charging_frames / self.MAX_CHARGE_FRAMES)

    def start_charge(self):
        self._is_charging = True

    def stop_charge(self):
        self._is_charging = False
        self._charging_frames = 0

    def _calculate_velocity(self):
        ratio = max(
            0.0,
            min(
                1.0,
                (self._charging_frames - self.MIN_CHARGE_FRAMES)
                / (self.MAX_CHARGE_FRAMES - self.MIN_CHARGE_FRAMES),
            ),
        )
        vx = self.MIN_VX + (self.MAX_VX - self.MIN_VX) * ratio
        vy = self.MIN_VY + (self.MAX_VY - self.MIN_VY) * ratio
        return vx, vy

    def throw_charged(self):
        if self._charging_frames < self.MIN_CHARGE_FRAMES:
            return
        vx, vy = self._calculate_velocity()
        self._vx = vx
        self._vy = vy
        self._state = HookState.THROWING

    def start_reeling(self):
        self._state = HookState.REELING

    def stop_reeling(self):
        self._reel_with_fish_frames = 0
        if self._y > self._water_y:
            self._state = HookState.SINKING
        else:
            self._state = HookState.SURFACE
            self._surface_timer = 0

    def hook_fish(self, fish_size: FishSize):
        self._has_fish = True
        self._reel_speed_with_fish = self.REEL_SPEED_WITH_FISH_MAP[fish_size]
        self._reel_line_break_frames = self.REEL_LINE_BREAK_FRAMES_MAP[fish_size]

    def move_to(self, x: int, y: int):
        """フックを指定座標に移動する（公開 IF）。

        有効範囲外（x < FINISH_X_MIN または x > FINISH_X_MAX）に出た場合は FINISHED に遷移する。
        範囲判定と終了処理は Hook の責任であり、呼び出し元（GameCore）は判定しない。
        """
        self._x = float(x)
        self._y = float(y)
        if self._x < self.FINISH_X_MIN or self._x > self.FINISH_X_MAX:
            self._state = HookState.FINISHED_FAIL

    def update(self):
        if self._is_charging:
            self._charging_frames += 1
        if self._state == HookState.THROWING:
            self._update_throwing()
        elif self._state == HookState.SURFACE:
            self._update_surface()
        elif self._state == HookState.REELING:
            self._update_reeling()
        elif self._state == HookState.SINKING:
            self._update_sinking()

    def _update_throwing(self):
        self._x += self._vx
        self._y += self._vy
        self._vy += self.GRAVITY
        if self._y >= self._water_y:
            self._state = HookState.SURFACE
            self._y = self._water_y
            self._vx = 0
            self._vy = 0

    def _update_surface(self):
        self._surface_timer += 1
        if self._surface_timer >= self.SURFACE_PAUSE_FRAMES:
            self._state = HookState.SINKING

    def _update_reeling(self):
        dx = self._throw_x - self._x
        dy = self._throw_y - self._y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < self.REEL_FINISH_DIST:
            self._state = HookState.FINISHED_SUCCESS
            return
        speed = self.REEL_SPEED
        if self._has_fish:
            self._reel_with_fish_frames += 1
            if self._reel_with_fish_frames >= self._reel_line_break_frames:
                self._state = HookState.FINISHED_FAIL
                return
            speed = self._reel_speed_with_fish
        if self._y > self._water_y:
            # 水中: 投擲起点方向へ斜め移動（ベクトル正規化）
            self._x += dx / dist * speed
            self._y = max(self._water_y, self._y + dy / dist * speed)
        else:
            # 水面: 水平移動のみ、y は水面に固定（釣り針は常に投擲起点より左）
            self._y = self._water_y
            self._x += speed

    def _update_sinking(self):
        if (
            self._bait_type == BaitType.FLOAT_BAIT
            and self._y >= self._water_y + self.FLOAT_BAIT_DEPTH
        ):
            return  # 浮餌が停止深度に達している: 何もしない
        self._y += self.SINK_VY_MAP[self._bait_type]
        if self._y >= self.FINISH_Y_MAX:
            self._state = HookState.FINISHED_FAIL
