import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from fish import Fish, FishRarity, FishSize  # pylint: disable=C0413


class TestFishInitialState(unittest.TestCase):
    """Fish の初期状態テスト。各 FishSize で生成した Fish が正しい初期値を持つこと。"""

    X_MIN, X_MAX, Y = 10, 200, 150

    def test_initial_state_by_fish_size(self):
        """各 FishSize で生成した Fish の初期状態（位置・速度・サイズ・ヒット状態）を確認する"""
        cases = [
            (FishSize.SMALL, 1.0),
            (FishSize.MEDIUM_S, -1.5),
            (FishSize.MEDIUM_L, 2.0),
            (FishSize.LARGE, -2.0),
        ]
        for fish_size, vx in cases:
            with self.subTest(fish_size=fish_size):
                fish = Fish(
                    y=self.Y,
                    vx=vx,
                    fish_size=fish_size,
                    x_min=self.X_MIN,
                    x_max=self.X_MAX,
                )
                self.assertGreaterEqual(fish.draw_x, self.X_MIN)
                self.assertLessEqual(fish.draw_x, self.X_MAX)
                self.assertEqual(fish.vx, vx)
                self.assertEqual(fish.fish_size, fish_size)
                self.assertFalse(fish.is_hit)


class TestFishHeadPos(unittest.TestCase):
    """get_head_pos の仕様テスト。

    draw_x を決定論的にするため random.uniform をパッチして固定する。
    魚頭のタイル内オフセット: HEAD_OFFSET_X=7, HEAD_OFFSET_Y=3（全サイズ共通）
    描画時の左右反転（draw_fish() は「画像が右向き基準」）:
        vx > 0（右向き）→ フリップなし → 頭はスプライト右端（offset_x=HEAD_OFFSET_X=7）
        vx < 0（左向き）→ 左右フリップ → 頭はスプライト左端（offset_x=0）
    """

    FIXED_X = 50.0  # random.uniform の戻り値を固定
    Y = 150

    def _make_fish(self, vx):
        with patch("fish.random.uniform", return_value=self.FIXED_X):
            return Fish(y=self.Y, vx=vx, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def test_head_pos_by_direction(self):
        """向きによって頭の x オフセットが変わること。y オフセットは方向によらず一定。
        右向き（vx > 0）→ フリップなし     → 頭はスプライト右端（offset_x=HEAD_OFFSET_X=7）
        左向き（vx < 0）→ 左右フリップ     → 頭はスプライト左端（offset_x=0）
        """
        cases = [
            ("right", 2.0, Fish._HEAD_OFFSET_X),  # pylint: disable=W0212
            ("left", -2.0, 0),
        ]
        for direction, vx, expected_offset_x in cases:
            with self.subTest(direction=direction):
                fish = self._make_fish(vx=vx)
                head_x, head_y = fish.get_head_pos()
                self.assertEqual(head_x, int(self.FIXED_X) + expected_offset_x)
                self.assertEqual(
                    head_y, self.Y + Fish._HEAD_OFFSET_Y  # pylint: disable=W0212
                )


class TestFishMovement(unittest.TestCase):
    """Fish の移動・壁折り返しテスト。"""

    FIXED_X = 50.0  # random.uniform の戻り値を固定

    def _make_fish(self, vx, x_min=0, x_max=240, fixed_x=None):
        fixed = fixed_x if fixed_x is not None else self.FIXED_X
        with patch("fish.random.uniform", return_value=fixed):
            return Fish(
                y=150, vx=vx, fish_size=FishSize.SMALL, x_min=x_min, x_max=x_max
            )

    def test_fish_movement(self):
        """update() 後の draw_x・vx・draw_y を確認する（移動・壁折り返し・y 不変）"""
        # (説明, fixed_x, vx, x_min, x_max, 期待draw_x, 期待vx)
        cases = [
            ("通常移動", 50.0, 2.0, 0, 240, 52, 2.0),  # 50+2=52, 壁なし
            (
                "右壁折り返し",
                235.0,
                2.0,
                0,
                240,
                232,
                -2.0,
            ),  # 235+2=237; 237+8=245>240 → x=232, vx=-2.0
            ("左壁折り返し", 2.0, -2.0, 0, 240, 0, 2.0),  # 2-2=0; 0<=0 → x=0, vx=2.0
        ]
        for desc, fixed_x, vx, x_min, x_max, exp_x, exp_vx in cases:
            with self.subTest(desc):
                fish = self._make_fish(vx=vx, x_min=x_min, x_max=x_max, fixed_x=fixed_x)
                fish.update()
                self.assertEqual(fish.draw_x, exp_x)
                self.assertEqual(fish.vx, exp_vx)
                self.assertEqual(fish.draw_y, 150)  # y は壁折り返しの有無によらず不変


class TestFishOverlaps(unittest.TestCase):
    """Fish.overlaps() の仕様テスト。魚頭位置 (_get_head_pos()) から TILE_SIZE/2=4px 以内で判定。

    Fish: FIXED_X=50.0, Y=100, vx=1.0（右向き）
    head_pos = (int(50.0) + HEAD_OFFSET_X, 100 + HEAD_OFFSET_Y) = (57, 103)
    TILE_SIZE=8, 判定範囲=4px
    """

    FIXED_X = 50.0
    Y = 100
    # head_pos: vx=1.0（右向き）→ フリップなし → offset_x=HEAD_OFFSET_X=7, offset_y=HEAD_OFFSET_Y=3
    HEAD_X = int(FIXED_X) + Fish._HEAD_OFFSET_X  # = 57  # pylint: disable=W0212
    HEAD_Y = Y + Fish._HEAD_OFFSET_Y  # = 103  # pylint: disable=W0212

    def _make_fish(self):
        with patch("fish.random.uniform", return_value=self.FIXED_X):
            return Fish(y=self.Y, vx=1.0, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def test_overlaps(self):
        """head=(50, 103), TILE_SIZE/2=4px で overlaps() の境界値を確認する"""
        # (説明, hook_x, hook_y, 期待結果)
        cases = [
            ("範囲内", self.HEAD_X + 2, self.HEAD_Y, True),  # abs(2), abs(0) <= 4
            ("範囲外", self.HEAD_X + 5, self.HEAD_Y, False),  # abs(5) > 4
            ("境界上", self.HEAD_X + 4, self.HEAD_Y + 4, True),  # abs(4), abs(4) <= 4
        ]
        fish = self._make_fish()
        for desc, hook_x, hook_y, expected in cases:
            with self.subTest(desc):
                self.assertEqual(fish.overlaps(hook_x=hook_x, hook_y=hook_y), expected)

    def test_overlaps_left_facing_fish(self):
        """左向き（vx < 0）の魚: 頭位置は左端（_x + 0）になる（左右フリップ後）"""
        # vx=-1.0 左向き: head_x = int(FIXED_X) + 0 = 50 + 0 = 50
        left_head_x = int(self.FIXED_X) + 0  # = 50
        # (説明, hook_x, hook_y, 期待結果)
        cases = [
            ("範囲内", left_head_x + 2, self.HEAD_Y, True),  # abs(2), abs(0) <= 4
            ("範囲外", left_head_x + 5, self.HEAD_Y, False),  # abs(5) > 4
            ("境界上", left_head_x + 4, self.HEAD_Y + 4, True),  # abs(4), abs(4) <= 4
        ]
        with patch("fish.random.uniform", return_value=self.FIXED_X):
            fish = Fish(y=self.Y, vx=-1.0, fish_size=FishSize.SMALL, x_min=0, x_max=240)
        for desc, hook_x, hook_y, expected in cases:
            with self.subTest(desc):
                self.assertEqual(fish.overlaps(hook_x=hook_x, hook_y=hook_y), expected)


class TestFishHitState(unittest.TestCase):
    """Fish.try_hit() のヒット確率テスト。

    random.random の値が HIT_PROBABILITY を下回るかどうかでヒット判定が変わること。
    """

    FIXED_X = 50.0
    Y = 100

    def _make_fish(self):
        with patch("fish.random.uniform", return_value=self.FIXED_X):
            return Fish(y=self.Y, vx=1.0, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def test_try_hit(self):
        """random.random の値に応じてヒット判定が変わること。
        HIT_PROBABILITY の具体値に依存しない固定値（0.0 / 0.999）を使用。
        """
        p = Fish.HIT_PROBABILITY
        # (説明, random.random戻り値, 期待try_hit戻り値, 期待is_hit)
        cases = [
            ("ヒットあり", 0.0, True, True),  # 0.0 < p → ヒット
            ("境界直下", p - 0.001, True, True),  # p-0.001 < p → ヒット
            ("境界値（外れ）", p, False, False),  # p < p は False → 外れ
            ("ヒットなし", 0.999, False, False),  # 0.999 >= p → 外れ
        ]
        for desc, random_val, expected_result, expected_is_hit in cases:
            with self.subTest(desc):
                fish = self._make_fish()
                with patch("fish.random.random", return_value=random_val):
                    result = fish.try_hit()
                self.assertEqual(result, expected_result)
                self.assertEqual(fish.is_hit, expected_is_hit)


class TestFishEscape(unittest.TestCase):
    """Fish のヒット後逃げ移動テスト。

    try_hit() でヒットすると魚が左方向に逃げること。
    投擲地点は常に画面右端（THROW_X=200）固定のため、逃げ方向は常に左（vx < 0）。
    """

    FIXED_X = 100.0
    Y = 150

    def _make_fish(self, vx=0.5, fixed_x=None):
        x = fixed_x if fixed_x is not None else self.FIXED_X
        with patch("fish.random.uniform", return_value=x):
            return Fish(y=self.Y, vx=vx, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def _hit_fish(self, fish):
        """try_hit() を必ずヒットさせるヘルパー。"""
        with patch("fish.random.random", return_value=0.0):
            fish.try_hit()

    def test_fish_escape_moves_left(self):
        """try_hit() でヒット後に update() を 1 回呼ぶと左方向に移動すること。"""
        fish = self._make_fish(vx=0.5, fixed_x=100.0)
        initial_x = fish.draw_x
        self._hit_fish(fish)
        fish.update()
        self.assertLess(fish.draw_x, initial_x)  # 左方向に移動
        self.assertLess(fish.vx, 0)  # 速度が負

    def test_fish_escape_direction_is_always_left(self):
        """Fish の位置によらずヒット後の逃げ方向は常に左（vx < 0）。"""
        cases = [
            ("左側の魚", 50.0),
            ("中央の魚", 120.0),
            ("右側の魚", 180.0),
        ]
        for desc, fixed_x in cases:
            with self.subTest(desc):
                fish = self._make_fish(vx=1.0, fixed_x=fixed_x)
                self._hit_fish(fish)
                self.assertLess(fish.vx, 0)  # 常に左方向

    def test_fish_escape_does_not_bounce(self):
        """ヒット後は壁での折り返しをせず、左端より左に消えていくこと。"""
        # 左端付近から開始し、update() を繰り返しても vx が正に反転しない
        fish = self._make_fish(vx=-2.0, fixed_x=5.0)
        self._hit_fish(fish)
        for _ in range(20):
            fish.update()
            self.assertLess(fish.vx, 0)  # vx が正に反転しない


class TestFishSetHeadPosition(unittest.TestCase):
    """Fish.set_head_position() の仕様テスト。

    set_head_position(x, y) 後に get_head_pos() が (x, y) を返すこと（get_head_pos() の逆演算）。
    vx の向きに応じたオフセットが正しく逆算されること。
    """

    def _make_fish(self, vx):
        with patch("fish.random.uniform", return_value=50.0):
            return Fish(y=150, vx=vx, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def test_set_head_position_right_facing(self):
        """右向き魚の set_head_position: 頭が指定座標に来るよう描画起点が逆算される"""
        fish = self._make_fish(vx=0.5)
        fish.set_head_position(100, 200)
        head_x, head_y = fish.get_head_pos()
        self.assertEqual(head_x, 100)
        self.assertEqual(head_y, 200)

    def test_set_head_position_left_facing(self):
        """左向き魚の set_head_position: 向きに応じたオフセットで正しく逆算される"""
        fish = self._make_fish(vx=-0.5)
        fish.set_head_position(100, 200)
        head_x, head_y = fish.get_head_pos()
        self.assertEqual(head_x, 100)
        self.assertEqual(head_y, 200)


class TestFishRarityInit(unittest.TestCase):
    """Fish が生成時に内部でレア度を決定すること"""

    def test_fish_has_rarity(self):
        """Fish 生成時に fish_rarity 属性が設定されること（random.choices をモック）"""
        with patch("fish.random.choices", return_value=[FishRarity.HIGH]):
            fish = Fish(y=50, vx=1.0, fish_size=FishSize.SMALL, x_min=0, x_max=160)
        self.assertEqual(fish.fish_rarity, FishRarity.HIGH)

    def test_fish_rarity_is_from_enum(self):
        """Fish 生成時の fish_rarity が FishRarity のいずれかであること"""
        fish = Fish(y=50, vx=1.0, fish_size=FishSize.SMALL, x_min=0, x_max=160)
        self.assertIn(fish.fish_rarity, list(FishRarity))


class TestFishCaughtState(unittest.TestCase):
    """Fish の釣り上げフラグ (is_caught) テスト。"""

    def _make_fish(self):
        with patch("fish.random.uniform", return_value=50.0):
            return Fish(y=150, vx=1.0, fish_size=FishSize.SMALL, x_min=0, x_max=240)

    def test_is_caught_false_by_default(self):
        """is_caught はデフォルト False"""
        fish = self._make_fish()
        self.assertFalse(fish.is_caught)

    def test_set_caught(self):
        """set_caught() を呼ぶと is_caught が True になる"""
        fish = self._make_fish()
        fish.set_caught()
        self.assertTrue(fish.is_caught)


class TestGetScore(unittest.TestCase):
    def test_score_is_size_times_rarity_multiplier(self):
        """get_score() が サイズスコア × レア度倍率 を返すこと（全サイズ × 全レア度）"""
        cases = [
            (FishSize.SMALL, FishRarity.LOW),  # 基準: LOW 倍率=1
            (FishSize.SMALL, FishRarity.MEDIUM),
            (FishSize.SMALL, FishRarity.HIGH),
            (FishSize.SMALL, FishRarity.ULTRA),
            (FishSize.MEDIUM_S, FishRarity.LOW),
            (FishSize.MEDIUM_S, FishRarity.HIGH),
            (FishSize.MEDIUM_L, FishRarity.MEDIUM),
            (FishSize.LARGE, FishRarity.ULTRA),  # 最大サイズ × 最高倍率
        ]
        for fish_size, rarity in cases:
            with self.subTest(fish_size=fish_size, rarity=rarity):
                with patch("fish.random.choices", return_value=[rarity]):
                    fish = Fish(y=50, vx=1.0, fish_size=fish_size, x_min=0, x_max=160)
                expected = (
                    Fish.SCORE_BY_SIZE[fish_size] * Fish.SCORE_MULT_BY_RARITY[rarity]
                )
                self.assertEqual(fish.get_score(), expected)


if __name__ == "__main__":
    unittest.main()
