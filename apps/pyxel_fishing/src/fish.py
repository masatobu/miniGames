import random
from enum import Enum


class FishSize(Enum):
    SMALL = 0  # タイル y=0
    MEDIUM_S = 1  # タイル y=1
    MEDIUM_L = 2  # タイル y=2
    LARGE = 3  # タイル y=3


class FishRarity(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    ULTRA = 3


class Fish:
    TILE_SIZE = 8
    # タイル内の魚頭ピクセル座標（全サイズ共通）
    _HEAD_OFFSET_X = 7
    _HEAD_OFFSET_Y = 3
    HIT_PROBABILITY = 0.3  # 1フレームあたりのヒット確率（プレイテストで調整）
    ESCAPE_SPEED_MULTIPLIER = 3  # 逃げ速度倍率（通常速度の何倍か。プレイテストで調整）
    # スコア比率: SMALL を基準に 2 倍ずつ増加（1:2:4:8）— 大物ほど飛躍的に高得点
    SCORE_BY_SIZE = {
        FishSize.SMALL: 1,    # 基準
        FishSize.MEDIUM_S: 2,  # ×2
        FishSize.MEDIUM_L: 4,  # ×4
        FishSize.LARGE: 8,     # ×8
    }
    # スポーン確率: LOW→ULTRA の順に約 10 倍ずつ減少（合計 1.0）
    # 比率: LOW:MEDIUM:HIGH:ULTRA = 900:90:9:1
    SPAWN_PROB_BY_RARITY = {
        FishRarity.LOW: 0.900,  # 最頻出
        FishRarity.MEDIUM: 0.090,  # ÷10
        FishRarity.HIGH: 0.009,  # ÷10
        FishRarity.ULTRA: 0.001,  # 最稀少（÷9）
    }
    # random.choices 用: Fish 生成のたびに list() 変換しないようクラス定義時に一度だけ計算
    _RARITY_POPULATION = list(SPAWN_PROB_BY_RARITY.keys())
    _RARITY_WEIGHTS = list(SPAWN_PROB_BY_RARITY.values())
    # スコア倍率: LOW=1 を基準に 10 倍ずつ増加（スポーン確率の逆数に対応）
    SCORE_MULT_BY_RARITY = {
        FishRarity.LOW: 1,  # 基準
        FishRarity.MEDIUM: 10,  # ×10
        FishRarity.HIGH: 100,  # ×100
        FishRarity.ULTRA: 1000,  # ×1000
    }

    def __init__(self, y, vx, fish_size, x_min, x_max):
        self._x_min = x_min
        self._x_max = x_max
        self._x = random.uniform(x_min, x_max - self.TILE_SIZE)
        self._y = y
        self._vx = vx
        self._initial_speed = abs(vx)  # 通常速度の絶対値（逃げ速度の基準）
        self._fish_size = fish_size
        self._fish_rarity = random.choices(
            self._RARITY_POPULATION, weights=self._RARITY_WEIGHTS
        )[0]
        self._is_hit = False
        self._is_caught = False

    @property
    def draw_x(self):
        return int(self._x)

    @property
    def draw_y(self):
        return int(self._y)

    @property
    def vx(self):
        return self._vx

    @property
    def fish_size(self):
        return self._fish_size

    @property
    def fish_rarity(self):
        return self._fish_rarity

    @property
    def is_hit(self) -> bool:
        return self._is_hit

    @property
    def is_caught(self) -> bool:
        return self._is_caught

    def get_score(self) -> int:
        # サイズ基本スコア × レア度倍率（LOW=1, MEDIUM=10, HIGH=100, ULTRA=1000）
        return (
            self.SCORE_BY_SIZE[self._fish_size]
            * self.SCORE_MULT_BY_RARITY[self._fish_rarity]
        )

    def set_caught(self):
        """釣り上げフラグを立てる。GameCore が hook FINISHED 時に呼ぶ。

        is_caught=True になった魚は次フレームの fish_list 再構築時に除外される。
        """
        self._is_caught = True

    def update(self):
        self._x += self._vx
        if not self._is_hit:
            # 通常移動: 左右の壁で折り返す
            if self._x + self.TILE_SIZE > self._x_max:
                self._x = self._x_max - self.TILE_SIZE
                self._vx = -abs(self._vx)
            if self._x <= self._x_min:
                self._x = self._x_min
                self._vx = abs(self._vx)
        # is_hit=True: 逃げモード。壁折り返しなし、そのまま画面外へ消える

    def try_hit(self) -> bool:
        """ヒット確率判定。ヒット成立時にヒット状態への遷移と逃げ開始を同時に行う。

        is_hit=True が逃げモードを兼ねる設計。
        GameCore は try_hit() を呼ぶだけで、ヒット判定と逃げ移動開始の両方が完了する。
        逃げ速度 = 通常速度 × ESCAPE_SPEED_MULTIPLIER（魚ごとの速さに比例）。
        """
        if random.random() < self.HIT_PROBABILITY:
            self._is_hit = True
            self._vx = -self._initial_speed * self.ESCAPE_SPEED_MULTIPLIER
            return True
        return False

    def overlaps(self, hook_x: int, hook_y: int) -> bool:
        """当たり判定の主実装。Hook が Fish の頭位置 (get_head_pos()) から TILE_SIZE/2=4px 以内にあれば True。

        判定基準: 魚頭位置（get_head_pos()）vs フック位置（hook_x, hook_y）。
        draw_x/draw_y（描画起点）ではなく頭位置を基準とすることで、
        魚の向きに関係なく一貫したヒット判定ができる。
        判定方式: 矩形距離（チェビシェフ距離）
          abs(hook_x - head_x) <= TILE_SIZE / 2
          abs(hook_y - head_y) <= TILE_SIZE / 2
        """
        head_x, head_y = self.get_head_pos()
        return (
            abs(hook_x - head_x) <= self.TILE_SIZE / 2
            and abs(hook_y - head_y) <= self.TILE_SIZE / 2
        )

    def get_head_pos(self):
        """魚頭のピクセル座標を返す（公開 IF）。set_head_position() と対称。

        呼び出し元:
          - overlaps(): ヒット判定の基準位置として使用
          - GameCore._update_hook_following(): フック追従先の座標として使用（非 REELING 時）

        draw_fish() は「画像が右向き基準」で描画する:
          vx > 0（右向き）: フリップなし → 頭はスプライト右端（offset_x = HEAD_OFFSET_X）
          vx < 0（左向き）: 左右フリップ → 頭はスプライト左端（offset_x = 0）
        """
        offset_x = self._HEAD_OFFSET_X if self._vx > 0 else 0
        return int(self._x) + offset_x, int(self._y) + self._HEAD_OFFSET_Y

    def set_head_position(self, x: int, y: int):
        """頭位置を指定座標に合わせる（公開 IF）。get_head_pos() の逆演算。

        巻き上げ中にフックへ追従させる際に使用。
        vx の向きに応じたオフセットを逆算して _x, _y を更新する。
        """
        offset_x = self._HEAD_OFFSET_X if self._vx > 0 else 0
        self._x = float(x - offset_x)
        self._y = float(y - self._HEAD_OFFSET_Y)
