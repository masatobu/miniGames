# title: pyxel fishing
# author: masatobu

import math
import random
from abc import ABC, abstractmethod

from fish import Fish, FishRarity, FishSize
from hook import BaitType, Hook, HookState


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_line(self, x1, y1, x2, y2, color):
        pass

    @abstractmethod
    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, color):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, color):
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

    def draw_line(self, x1, y1, x2, y2, color):
        self.pyxel.line(x1, y1, x2, y2, color)

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def draw_rectb(self, x, y, w, h, color):
        self.pyxel.rectb(x, y, w, h, color)

    def draw_rect(self, x, y, w, h, color):
        self.pyxel.rect(x, y, w, h, color)

    def get_frame(self) -> int:
        return self.pyxel.frame_count


class IFishView(ABC):
    @abstractmethod
    def draw_fish(self, x, y, fish_size, vx, is_hit: bool):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelFishView(IFishView):
    # スプライトシート（img=1）のレイアウト
    #   タイル x=1(静止A), x=2(泳ぎ), x=3(静止B)
    #   アニメーションパターン: タイル x = 1→2→1→3 (u = 8→16→8→24)
    IMG_BANK = 1  # 魚画像のバンク番号（レイヤー 1）
    TILE_SIZE = 8
    BASE_TILE_X = 1  # アニメーション基準タイル x 座標
    ANIM_PATTERN = [0, 1, 0, 2]  # BASE_TILE_X からのオフセット → u = 8→16→8→24
    ANIM_INTERVAL = 8  # コマ切替フレーム数（暫定値。プレイテスト後に調整）
    ESCAPE_ANIM_INTERVAL = (
        3  # 逃げ状態のコマ切替フレーム数（暫定値。プレイテスト後に調整）
    )
    COLKEY = 0  # 透明色（色 0 を透明扱い）

    def __init__(self):
        self.view = self._create_view()

    def _create_view(self):
        return PyxelView.create()

    def draw_fish(self, x, y, fish_size, vx, is_hit: bool):
        """魚をアニメーション付きで描画する。
        - u: frame_count に応じた 4 コマアニメーション
        - v: FishSize に応じたタイル行（SMALL=0, MEDIUM_S=8, MEDIUM_L=16, LARGE=24）
        - w: 画像は右向き基準。左向き移動時（vx<0）は負値で左右反転する
        - is_hit: True のとき ESCAPE_ANIM_INTERVAL で高速アニメーション
        """
        frame = self.view.get_frame()
        interval = self.ESCAPE_ANIM_INTERVAL if is_hit else self.ANIM_INTERVAL
        anim_index = (frame // interval) % 4
        u = (self.BASE_TILE_X + self.ANIM_PATTERN[anim_index]) * self.TILE_SIZE
        v = fish_size.value * self.TILE_SIZE
        w = self.TILE_SIZE if vx > 0 else -self.TILE_SIZE  # 画像が右向き基準
        self.view.draw_blt(x, y, self.IMG_BANK, u, v, w, self.TILE_SIZE, self.COLKEY)


class IInput(ABC):
    @abstractmethod
    def is_mouse_btn_pressed(self) -> bool:
        pass

    @abstractmethod
    def is_mouse_btn_held(self) -> bool:
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

    def is_mouse_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def is_mouse_btn_held(self) -> bool:
        return self.pyxel.btn(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class BasePopup:
    """ポップアップ共通の矩形判定・枠描画を担当する基底クラス。"""

    def __init__(self, x, y, w, h, bg_color, border_color):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.bg_color = bg_color
        self.border_color = border_color

    def handle_dismiss(self, input_obj) -> bool:
        """矩形内タップでポップアップを解除する。解除したら True を返す。"""
        if not input_obj.is_mouse_btn_pressed():
            return False
        mx, my = input_obj.mouse_x, input_obj.mouse_y
        return self.x <= mx < self.x + self.w and self.y <= my < self.y + self.h

    def _draw_frame(self, view):
        """背景矩形と枠を描画する。"""
        view.draw_rect(self.x, self.y, self.w, self.h, self.bg_color)
        view.draw_rectb(self.x, self.y, self.w, self.h, self.border_color)


class FishCatchPopup(BasePopup):
    """魚捕捉ポップアップの状態管理・描画を担当するクラス。"""

    TILE_SIZE = 8
    W = 80
    H = 48
    X = 80  # (SCREEN_WIDTH=240 - W=80) // 2
    Y = 136  # (SCREEN_HEIGHT=320 - H=48) // 2（画面中央）
    BG_COLOR = 1  # 背景色（暗い青）
    BORDER_COLOR = 7  # 枠色（白）
    FISH_X = X + (W - TILE_SIZE) // 2  # 魚画像X（水平中央）
    FISH_Y = (
        Y + (H - (TILE_SIZE + 4 + 5)) // 2
    )  # 魚画像Y（垂直中央: コンテンツ高=TILE_SIZE+gap4+text5）
    SCORE_Y = FISH_Y + TILE_SIZE + 4  # スコアテキストY（魚画像下4px）
    # レア度別タイル列 u 座標（requirements.md: タイル x=4〜7 × TILE_SIZE）
    RARITY_U = {
        FishRarity.LOW: 4 * TILE_SIZE,  # u=32
        FishRarity.MEDIUM: 5 * TILE_SIZE,  # u=40
        FishRarity.HIGH: 6 * TILE_SIZE,  # u=48
        FishRarity.ULTRA: 7 * TILE_SIZE,  # u=56
    }

    def __init__(self, score, fish_size, fish_rarity):
        super().__init__(
            self.X, self.Y, self.W, self.H, self.BG_COLOR, self.BORDER_COLOR
        )
        self.score = score
        self.fish_size = fish_size
        self.fish_rarity = fish_rarity

    def draw(self, view):
        """ポップアップ（背景・枠・魚画像・スコアテキスト）を描画する。"""
        self._draw_frame(view)
        u = self.RARITY_U[self.fish_rarity]
        v = self.fish_size.value * self.TILE_SIZE
        view.draw_blt(
            self.FISH_X, self.FISH_Y, 1, u, v, self.TILE_SIZE, self.TILE_SIZE, 0
        )
        # "+N" 形式、水平中央配置（Pyxel フォント: 1文字=4px幅）
        score_text = f"+{self.score}"
        score_x = self.X + (self.W - len(score_text) * 4) // 2
        view.draw_text(score_x, self.SCORE_Y, score_text)


class GameOverPopup(BasePopup):
    """ゲームオーバーポップアップの状態管理・描画を担当するクラス。"""

    W = 160
    H = 80
    X = (240 - W) // 2  # (SCREEN_WIDTH=240 - W=160) // 2 = 40（画面水平中央）
    Y = (320 - H) // 2  # (SCREEN_HEIGHT=320 - H=80) // 2 = 120（画面垂直中央）
    BG_COLOR = 0  # 背景色（黒）
    BORDER_COLOR = 7  # 枠色（白）
    TITLE_TEXT = "GAME OVER"
    RESTART_TEXT = "Click to Restart."
    _LINE_SPACING = 16  # テキスト行間（px）
    _TEXT_H = 6  # Pyxel フォント高さ（px）
    # 3行コンテンツ（TITLE・SCORE・RESTART）を枠内縦中央配置
    TITLE_Y = Y + (H - (_LINE_SPACING * 2 + _TEXT_H)) // 2
    SCORE_Y = TITLE_Y + _LINE_SPACING
    RESTART_Y = SCORE_Y + _LINE_SPACING

    def __init__(self, score):
        super().__init__(
            self.X, self.Y, self.W, self.H, self.BG_COLOR, self.BORDER_COLOR
        )
        self.score = score

    def draw(self, view):
        """ゲームオーバーポップアップ（背景・枠・メッセージ・スコア）を描画する。"""
        self._draw_frame(view)
        # タイトル（Pyxel フォント: 1文字=4px幅、水平中央配置）
        title_x = self.X + (self.W - len(self.TITLE_TEXT) * 4) // 2
        view.draw_text(title_x, self.TITLE_Y, self.TITLE_TEXT)
        score_text = f"Score: {self.score}"
        score_x = self.X + (self.W - len(score_text) * 4) // 2
        view.draw_text(score_x, self.SCORE_Y, score_text)
        restart_x = self.X + (self.W - len(self.RESTART_TEXT) * 4) // 2
        view.draw_text(restart_x, self.RESTART_Y, self.RESTART_TEXT)


class GameCore:
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 320
    WATER_Y = 96
    TILE_SIZE = 8
    THROW_X = 200
    THROW_Y = WATER_Y - TILE_SIZE  # 水面直上: スプライト底辺が水面に接する
    LINE_ORIGIN_X = THROW_X + 3  # 釣り糸起点X（スプライト内のロッド先端位置）
    LINE_ORIGIN_Y = THROW_Y + 6  # 釣り糸起点Y（スプライト内のロッド先端位置）

    # 水上レイヤースプライト: (u, v, w, h)
    BG_SPRITE = (112, 0, 48, 96)  # 背景（最後背・最初に描画）
    MID_SPRITE = (64, 0, 48, 96)  # 中景
    FG_SPRITE = (16, 0, 48, 96)  # 前景（最前・最後に描画）

    # 水中領域スプライト: (u, v, w, h)
    WATER_SURFACE_SPRITE = (16, 96, 48, 8)  # 水面スプライト（1行）
    UNDERWATER_SPRITE = (16, 104, 48, 8)  # 水中スプライト（複数行）

    HOOK_COLOR = 13  # 灰色ピクセル（Pyxel 標準カラー）
    SELECTED_BTN_COLOR = 7  # 選択中ボタン強調枠の色（白）

    BTN_SIZE = 16  # ボタンスプライトのサイズ（幅・高さ共通）
    BTN_GAP = 4  # ボタン間のギャップ

    # えさ種類ボタン座標
    FLOAT_BAIT_BTN_X = 8
    FLOAT_BAIT_BTN_Y = (
        SCREEN_HEIGHT - BTN_SIZE - TILE_SIZE
    )  # 画面下端 - ボタン高さ - TILE_SIZE マージン = 296
    LURE_BTN_X = FLOAT_BAIT_BTN_X  # 浮餌ボタンと同じX（縦並び）= 8
    LURE_BTN_Y = (
        FLOAT_BAIT_BTN_Y - BTN_SIZE - BTN_GAP
    )  # 浮餌ボタン上端 - ギャップ = 276

    # えさ種類ボタンスプライト: (u, v, w, h)
    FLOAT_BAIT_SPRITE = (0, 8, BTN_SIZE, BTN_SIZE)  # u=0, v=8: 浮餌スプライト
    LURE_SPRITE = (0, 24, BTN_SIZE, BTN_SIZE)  # u=0, v=24: ルアースプライト

    # 疲労値
    MAX_FATIGUE = 1200  # 初期疲労値（20秒 × 60fps、プレイテストで調整）

    # スコア表示（画面左上）
    SCORE_X = 4
    SCORE_Y = 4

    # 疲労ゲージ（画面右上）
    FATIGUE_GAUGE_W = SCREEN_WIDTH // 2  # 外枠の幅（画面幅の半分）
    FATIGUE_GAUGE_H = 6  # 外枠の高さ
    FATIGUE_GAUGE_X = (
        SCREEN_WIDTH - FATIGUE_GAUGE_W - SCORE_X
    )  # 右端マージンをスコアと統一
    FATIGUE_GAUGE_Y = SCORE_Y  # スコアと同じ高さに揃える
    FATIGUE_GAUGE_COLOR = 13  # 内側の色（灰色）
    FATIGUE_GAUGE_BG_COLOR = 13  # 外枠の色（灰色）

    # パワーゲージ（投擲起点の左側に縦方向で表示）
    GAUGE_X = THROW_X - 12  # ゲージ左端X（= 188）
    GAUGE_BOTTOM_Y = WATER_Y - 4  # ゲージ下端Y（水面のすぐ上 = 92）
    GAUGE_MAX_H = 24  # ゲージ最大高さ（MAX_CHARGE_FRAMES に対応）
    GAUGE_W = 4  # ゲージ幅
    GAUGE_COLOR = 13  # ゲージ色（灰色）
    MAX_GAUGE_COLOR = 2  # ゲージ強調色（紫: MAX 到達時）

    GAUGE_BG_COLOR = 1  # ゲージ背景色（暗い青）

    # 魚の移動・出現範囲
    # 【深度ゾーン設計】
    #   浅域（SMALL）  : WATER_Y+TILE_SIZE 〜 WATER_Y+FLOAT_BAIT_DEPTH = 104〜112
    #                    浮餌の停止Y(112)以浅 → 浮餌で必ず狙える
    #   深域（MEDIUM+）: WATER_Y+FLOAT_BAIT_DEPTH 〜 WATER_Y+184 = 112〜280
    #                    3サイズを等幅セグメントで分割 → ルアー専用
    #                    セグメント幅 = (184 - FLOAT_BAIT_DEPTH) // 3 = 56px（7タイル分）
    FISH_SPEED = 0.5  # 魚の速度（毎フレーム px、プレイテストで調整）
    _D = Hook.FLOAT_BAIT_DEPTH  # 深度ゾーン起点オフセット = 16
    _S = 56  # 1セグメント幅 = (184 - _D) // 3 = 56px（7タイル分）
    FISH_Y_RANGE_BY_SIZE = {
        FishSize.SMALL: (WATER_Y + TILE_SIZE, WATER_Y + _D),  # 浅域: (104, 112)
        FishSize.MEDIUM_S: (WATER_Y + _D, WATER_Y + _D + _S),  # 深域第1区画: (112, 168)
        FishSize.MEDIUM_L: (
            WATER_Y + _D + _S,
            WATER_Y + _D + 2 * _S,
        ),  # 深域第2区画: (168, 224)
        FishSize.LARGE: (
            WATER_Y + _D + 2 * _S,
            WATER_Y + 184,
        ),  # 深域第3区画: (224, 280)
    }
    del _D, _S  # クラス属性汚染防止（計算用の一時変数）

    # スポーン制御
    SPAWN_INTERVAL_MIN = 60  # 最短スポーン間隔（フレーム、暫定値）
    SPAWN_INTERVAL_MAX = 180  # 最長スポーン間隔（フレーム、暫定値）
    MAX_FISH_BY_SIZE = {
        FishSize.SMALL: 2,  # 出現幅8px(1タイル)のため密集防止
        FishSize.MEDIUM_S: 2,
        FishSize.MEDIUM_L: 1,
        FishSize.LARGE: 1,
    }

    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()
        self.fish_view = PyxelFishView.create()
        self.hook = self._create_hook()
        self.fish_list = []
        self._spawn_timer = 0
        self._next_spawn_interval = self.SPAWN_INTERVAL_MIN
        self._score = 0
        self._prev_held = False
        # overlap してヒットした特定の魚への参照（None = 追従なし）。
        # is_hit=True の任意の魚ではなく、overlap した魚のみを追う設計にすることで、
        # 複数の魚が存在しても正しい魚のみにフックが追従できる。
        self._following_fish = None
        self._popup = None
        self._fatigue = self.MAX_FATIGUE
        self._is_game_over = False
        self._game_over_popup = None
        self._needs_reset = False
        # 疲労値 0 で釣り上げた場合、釣り上げポップアップ解除後にゲームオーバーへ遷移するためのフラグ
        self._pending_game_over = False

    def _create_hook(self, bait_type=BaitType.FLOAT_BAIT):
        hook = Hook(self.LINE_ORIGIN_X, self.LINE_ORIGIN_Y, self.WATER_Y)
        hook.set_bait_type(bait_type)
        return hook

    def _create_fish(self, fish_size):
        y_min, y_max = self.FISH_Y_RANGE_BY_SIZE[fish_size]
        y = random.randint(y_min, y_max)
        vx = self.FISH_SPEED * random.choice([1, -1])
        return Fish(y, vx, fish_size, x_min=0, x_max=self.SCREEN_WIDTH)

    def _count_fish_by_size(self) -> dict:
        """現在の fish_list に含まれる FishSize ごとの数を返す。"""
        counts = {size: 0 for size in FishSize}
        for fish in self.fish_list:
            counts[fish.fish_size] += 1
        return counts

    def _select_spawn_size(self):
        """上限未満の FishSize からランダムに1つ選ぶ。全サイズ上限なら None。"""
        counts = self._count_fish_by_size()
        available = [
            size for size in FishSize if counts[size] < self.MAX_FISH_BY_SIZE[size]
        ]
        if not available:
            return None
        return random.choice(available)

    def _try_spawn_fish(self):
        """スポーンを試みる。サイズ選択 → 魚生成 → fish_list に追加。"""
        fish_size = self._select_spawn_size()
        if fish_size is None:
            return
        fish = self._create_fish(fish_size)
        self.fish_list.append(fish)

    def _draw_horizontal_tiles(self, y, u, v, w, h, x_offset=0):
        col_count = math.ceil((self.SCREEN_WIDTH - x_offset) / w)
        for i in range(col_count):
            self.view.draw_blt(x_offset + i * w, y, 0, u, v, w, h, 0)

    def _is_in_rect(self, mx, my, rx, ry, rw, rh) -> bool:
        return rx <= mx < rx + rw and ry <= my < ry + rh

    def _is_in_btn(self, mx, my, bx, by):
        return self._is_in_rect(mx, my, bx, by, self.BTN_SIZE, self.BTN_SIZE)

    def _handle_popup_dismiss(self):
        if self._popup is None:
            return
        if not self._popup.handle_dismiss(self.input):
            return
        self._popup = None
        # 疲労値 0 での釣り上げポップアップ解除 → ゲームオーバーへ遷移（順次表示の完結）
        if self._pending_game_over:
            self._is_game_over = True
            self._pending_game_over = False

    def _handle_click(self):
        if not self.input.is_mouse_btn_pressed():
            return
        mx, my = self.input.mouse_x, self.input.mouse_y
        if self.hook.state != HookState.IDLE:
            return
        if self._is_in_btn(mx, my, self.FLOAT_BAIT_BTN_X, self.FLOAT_BAIT_BTN_Y):
            self.hook.set_bait_type(BaitType.FLOAT_BAIT)
        elif self._is_in_btn(mx, my, self.LURE_BTN_X, self.LURE_BTN_Y):
            self.hook.set_bait_type(BaitType.LURE)

    def _handle_hold(self):
        if self.input.is_mouse_btn_held():
            if self.hook.state in (HookState.SINKING, HookState.SURFACE):
                self.hook.start_reeling()
        else:
            if self.hook.state == HookState.REELING:
                self.hook.stop_reeling()

    def _handle_power_charge(self):
        if self.hook.state != HookState.IDLE:
            return
        held = self.input.is_mouse_btn_held()
        released = self._prev_held and not held
        if released:
            self.hook.throw_charged()
            if self.hook.state == HookState.THROWING:
                # 投擲成立時に固定コスト（MIN_CHARGE_FRAMES 分）を疲労値から一括減算する。
                # 充電長さによらず一定コストとすることで、連打抑止の効果を持たせる。
                self._update_fatigue(Hook.MIN_CHARGE_FRAMES)
            self.hook.stop_charge()
            self._prev_held = False
        elif held:
            self.hook.start_charge()
            self._prev_held = held
        else:
            self.hook.stop_charge()
            self._prev_held = held

    def _update_game_over_popup(self) -> bool:
        """ゲームオーバー状態を処理する。ゲームオーバー中なら True を返す。"""
        if not self._is_game_over:
            return False
        if self._game_over_popup is None:
            self._game_over_popup = GameOverPopup(self._score)
        if self._game_over_popup.handle_dismiss(self.input):
            self._needs_reset = True
        return True

    def update(self):
        if self._update_game_over_popup():
            return
        self._handle_popup_dismiss()
        if self._popup is None:
            self._handle_click()
            self._handle_hold()
            self._handle_power_charge()
        self._update_reeling()
        if self.hook.state == HookState.FINISHED_SUCCESS:
            if self._following_fish is not None:
                score = self._following_fish.get_score()
                self._score += score
                self._popup = FishCatchPopup(
                    score,
                    self._following_fish.fish_size,
                    self._following_fish.fish_rarity,
                )
                self._following_fish.set_caught()
                self._following_fish = None
                # 疲労値 0 での釣り上げ: 釣り上げポップアップを先に表示し、解除後にゲームオーバーへ遷移
                if self._fatigue == 0:
                    self._pending_game_over = True
            # 魚あり・なしどちらも即座に hook をリセット（ポップアップ表示は is_popup_visible で管理）
            self.hook = self._create_hook(self.hook.bait_type)
        elif self.hook.state == HookState.FINISHED_FAIL:
            self.hook = self._create_hook(self.hook.bait_type)
            # _following_fish をクリアしないと新しい IDLE フックが毎フレーム FINISHED になるバグが発生する
            self._following_fish = None
            # IDLE 復帰直後に疲労値 0 ならゲームオーバーへ自動遷移する
            if self._fatigue == 0:
                self._is_game_over = True
        for fish in self.fish_list:
            fish.update()
        self._update_hit_detection()
        # フック追従を先に行い、追従後の位置で画面外判定を行う（処理順が重要）
        self._update_hook_following()
        # 画面外または釣り上げ済みの魚を fish_list から除去
        self.fish_list = [
            f
            for f in self.fish_list
            if not self._is_fish_offscreen(f) and not f.is_caught
        ]
        self._update_spawn_timer()

    def _update_reeling(self):
        """リーリング処理を行う。魚ヒット中は疲労値を 1 減少させる。"""
        self.hook.update()
        if self.hook.state == HookState.REELING and self._following_fish is not None:
            self._update_fatigue(1)

    def _update_fatigue(self, amount):
        """疲労値を減少させる（0 以下にはならない）。"""
        self._fatigue = max(0, self._fatigue - amount)

    def _update_spawn_timer(self):
        """スポーンタイマーを進め、間隔到達でスポーンを試みる。"""
        self._spawn_timer += 1
        if self._spawn_timer >= self._next_spawn_interval:
            self._try_spawn_fish()
            self._spawn_timer = 0
            self._next_spawn_interval = random.randint(
                self.SPAWN_INTERVAL_MIN, self.SPAWN_INTERVAL_MAX
            )

    def _is_fish_offscreen(self, fish) -> bool:
        """魚が画面外に出ているか判定する。"""
        return fish.draw_x + fish.TILE_SIZE < 0 or fish.draw_x > self.SCREEN_WIDTH

    def _update_hit_detection(self):
        """ヒット判定を処理する（オーバーラップ検出 → try_hit() → hook 通知）。

        is_hit チェック: すでにヒット済みの魚への二重判定を防ぐ（GameCore 側の責務）。
        _following_fish チェック: 追従中の魚がいる場合は追加ヒット処理をスキップ。
        hook.hook_fish(fish.fish_size): ヒット確定時に呼び出し、魚サイズに応じた巻き上げ速度・糸切れフレームを設定する。
        """
        if self._following_fish is not None:
            return
        for fish in self.fish_list:
            if not fish.is_hit and fish.overlaps(self.hook.x, self.hook.y):
                if fish.try_hit():
                    # overlap した特定の魚を記録（複数魚がいても正しい魚のみ追従するため）
                    self._following_fish = fish
                    self.hook.hook_fish(fish.fish_size)
                    break  # 先着1匹のみ追従（以降の魚へのtry_hit()呼び出しを防ぐ）

    def _update_hook_following(self):
        """ヒットした魚とフックの追従方向を状態に応じて切り替える。

        REELING 中: 魚がフックに追従（魚を引っ張る）
            fish.set_head_position(hook.x, hook.y) で魚頭をフック位置に合わせる。
        それ以外（逃げ中など）: フックが魚に追従（既存動作）
            hook.move_to(head_x, head_y) でフックを魚頭位置に合わせる。
        画面外判定とサイクル終了（FINISHED 遷移）は Hook の責任（GameCore は判定しない）。
        """
        if self._following_fish is None:
            return
        if self.hook.state == HookState.REELING:
            self._following_fish.set_head_position(self.hook.x, self.hook.y)
        else:
            head_x, head_y = self._following_fish.get_head_pos()
            self.hook.move_to(head_x, head_y)

    def draw(self):
        # 水上レイヤー（奥→手前: 背景→中景→前景、x_offset で奥行き表現）
        for sprite, x_offset in [
            (self.BG_SPRITE, -32),
            (self.MID_SPRITE, -16),
            (self.FG_SPRITE, 0),
        ]:
            self._draw_horizontal_tiles(0, *sprite, x_offset=x_offset)
        # 水中領域（水面スプライト1行 + 水中スプライト複数行）
        self._draw_horizontal_tiles(self.WATER_Y, *self.WATER_SURFACE_SPRITE)
        row_count = (
            self.SCREEN_HEIGHT - self.WATER_Y - self.TILE_SIZE
        ) // self.TILE_SIZE
        for row in range(row_count):
            self._draw_horizontal_tiles(
                self.WATER_Y + self.TILE_SIZE * (row + 1), *self.UNDERWATER_SPRITE
            )
        # 釣り人スプライト（タイル座標 (1,0): u=TILE_SIZE（列1 × タイルサイズ）, v=0）
        self.view.draw_blt(
            self.THROW_X,
            self.THROW_Y,
            0,
            self.TILE_SIZE,
            0,
            self.TILE_SIZE,
            self.TILE_SIZE,
            0,
        )
        # 魚の描画（ボタン・釣り針より奥に描画）
        for fish in self.fish_list:
            self.fish_view.draw_fish(
                fish.draw_x, fish.draw_y, fish.fish_size, fish.vx, fish.is_hit
            )
        # えさ種類ボタン（スプライト + 選択中のみ強調枠）
        self._draw_bait_button(BaitType.FLOAT_BAIT)
        self._draw_bait_button(BaitType.LURE)
        # スコア表示（背景・ボタン描画後）
        self.view.draw_text(self.SCORE_X, self.SCORE_Y, str(self._score))
        # 釣り針（待機以外の状態で投擲地点から釣り針位置へ線を描画）
        if self.hook.state != HookState.IDLE:
            self.view.draw_line(
                self.LINE_ORIGIN_X,
                self.LINE_ORIGIN_Y,
                self.hook.x,
                self.hook.y,
                self.HOOK_COLOR,
            )
        # パワーゲージ（充電中のみ表示）
        self._draw_power_gauge()
        # 疲労ゲージ（常時表示）
        self._draw_fatigue_gauge()
        # ポップアップ（最前面：他の描画より後に描画）
        if self._popup is not None:
            self._popup.draw(self.view)
        # ゲームオーバーポップアップ（すべての描画より最前面）
        if self._game_over_popup is not None:
            self._game_over_popup.draw(self.view)

    def needs_reset(self) -> bool:
        """ゲームリセットが必要かどうかを返す。"""
        return self._needs_reset

    def _draw_fatigue_gauge(self):
        inner_w = int(self._fatigue / self.MAX_FATIGUE * self.FATIGUE_GAUGE_W)
        inner_x = self.FATIGUE_GAUGE_X + self.FATIGUE_GAUGE_W - inner_w
        self.view.draw_rectb(
            self.FATIGUE_GAUGE_X,
            self.FATIGUE_GAUGE_Y,
            self.FATIGUE_GAUGE_W,
            self.FATIGUE_GAUGE_H,
            self.FATIGUE_GAUGE_BG_COLOR,
        )
        self.view.draw_rect(
            inner_x,
            self.FATIGUE_GAUGE_Y,
            inner_w,
            self.FATIGUE_GAUGE_H,
            self.FATIGUE_GAUGE_COLOR,
        )

    def _draw_power_gauge(self):
        # charge_ratio は MIN_CHARGE_FRAMES 未満（タップ相当）で 0.0 を返すため、
        # 0.0 チェックのみで「非充電」と「タップ相当」の両方を非表示にできる。
        ratio = self.hook.charge_ratio
        if ratio == 0.0:
            return
        gauge_h = max(1, int(ratio * self.GAUGE_MAX_H))
        gauge_top_y = self.GAUGE_BOTTOM_Y - gauge_h
        gauge_full_top_y = self.GAUGE_BOTTOM_Y - self.GAUGE_MAX_H
        gauge_color = self.MAX_GAUGE_COLOR if ratio >= 1.0 else self.GAUGE_COLOR
        self.view.draw_rect(
            self.GAUGE_X,
            gauge_full_top_y,
            self.GAUGE_W,
            self.GAUGE_MAX_H,
            self.GAUGE_BG_COLOR,
        )
        self.view.draw_rect(
            self.GAUGE_X, gauge_top_y, self.GAUGE_W, gauge_h, gauge_color
        )
        self.view.draw_rectb(
            self.GAUGE_X, gauge_full_top_y, self.GAUGE_W, self.GAUGE_MAX_H, gauge_color
        )

    def _draw_bait_button(self, bait_type):
        configs = {
            BaitType.FLOAT_BAIT: (
                self.FLOAT_BAIT_BTN_X,
                self.FLOAT_BAIT_BTN_Y,
                self.FLOAT_BAIT_SPRITE,
            ),
            BaitType.LURE: (self.LURE_BTN_X, self.LURE_BTN_Y, self.LURE_SPRITE),
        }
        bx, by, sprite = configs[bait_type]
        self.view.draw_blt(bx, by, 0, *sprite, 0)
        if self.hook.bait_type == bait_type:
            self.view.draw_rectb(
                bx, by, self.BTN_SIZE, self.BTN_SIZE, self.SELECTED_BTN_COLOR
            )


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        self.game_core = GameCore()

        pyxel.init(GameCore.SCREEN_WIDTH, GameCore.SCREEN_HEIGHT, title="Pyxel Fishing")
        pyxel.load("images.pyxres")
        pyxel.mouse(True)
        pyxel.run(self.update, self.draw)

    def update(self):
        if self.game_core.needs_reset():
            self.game_core = GameCore()
        else:
            self.game_core.update()

    def draw(self):
        self.pyxel.cls(0)
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
