import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from reel import Reel, ReelSymbol  # pylint: disable=C0413


class TestReelSpinning(unittest.TestCase):
    # result は停止時（update() で _spin_frames_left が 0 になった瞬間）に確定する
    # click() 直後は result=None、is_spinning=True

    # (click_count, update_count, mock_returns, expected_spinning, expected_result, expected_just_stopped, label)
    CASES = [
        (0, 0, [], False, None, False, "クリックなし: 非スピン・result=None"),
        (1, 0, [], True, None, False, "1回クリック直後: スピン中・result未確定"),
        (2, 0, [], True, None, False, "スピン中2回目クリック: 無視・result未確定"),
        (
            1,
            Reel.SPIN_DURATION,
            [3],
            False,
            3,
            True,
            "SPIN_DURATIONフレーム: 停止直後・just_stopped=True",
        ),
        (
            1,
            Reel.SPIN_DURATION + 1,
            [3],
            False,
            3,
            False,
            "SPIN_DURATION+1フレーム: 停止済み・just_stopped=False",
        ),
    ]

    def test_spinning_state_and_result(self):
        """click回数・update回数に応じて is_spinning・result・just_stopped が正しく変化すること"""
        for (
            click_count,
            update_count,
            mock_returns,
            expected_spinning,
            expected_result,
            expected_just_stopped,
            label,
        ) in self.CASES:
            with self.subTest(label):
                reel = Reel()
                with patch("reel.random.choice", side_effect=mock_returns):
                    for _ in range(click_count):
                        reel.click()
                    for _ in range(update_count):
                        reel.update()
                self.assertEqual(reel.is_spinning, expected_spinning)
                self.assertEqual(reel.result, expected_result)
                self.assertEqual(reel.just_stopped, expected_just_stopped)


class TestReelDisplayTextAndCurrentSymbol(unittest.TestCase):
    """Reel.display_text と current_symbol の振る舞いをテスト

    両プロパティは同じ状態（停止後の出目、スピン中のアニメーション値）を
    異なる型で返す。display_text は表示用の str、current_symbol はロジック用の ReelSymbol。
    """

    def _make_spinning_reel(self, updates_after_click):
        """click後にupdates回update()を呼んだReel（スピン中）を生成"""
        reel = Reel()
        reel.click()
        for _ in range(updates_after_click):
            reel.update()
        return reel

    def test_initial_state(self):
        """初期状態（クリックなし）は display_text='0'、current_symbol=ZERO を返すこと"""
        reel = Reel()
        self.assertEqual(reel.display_text, "0")
        self.assertEqual(reel.current_symbol, ReelSymbol.ZERO)

    def test_stopped_state(self):
        """停止後は出目に対応する display_text と current_symbol を返すこと"""
        reel = Reel()
        with patch("reel.random.choice", return_value=2):
            reel.click()
            for _ in range(Reel.SPIN_DURATION):
                reel.update()
        self.assertFalse(reel.is_spinning)
        self.assertEqual(reel.result, 2)
        self.assertEqual(reel.display_text, "2")
        self.assertEqual(reel.current_symbol, ReelSymbol.TWO)

    def test_spinning_follows_deceleration(self):
        """スピン中は速度漸減アルゴリズムに従った display_text と current_symbol を返すこと

        速度漸減計算式:
          elapsed  = SPIN_DURATION - _spin_frames_left
          interval = max(1, elapsed * 8 // SPIN_DURATION)
          idx      = (elapsed // interval) % len(RESULT_VALUES)
        """
        # (updates_after_click, expected_text, expected_symbol, label)
        cases = [
            (
                0,
                "0",
                ReelSymbol.ZERO,
                "click直後(elapsed=0): interval=1, idx=0 → RESULT_VALUES[0]=0",
            ),
            (
                1,
                "1",
                ReelSymbol.ONE,
                "1フレーム後(elapsed=1): interval=1, idx=1 → RESULT_VALUES[1]=1",
            ),
            (
                4,
                "0",
                ReelSymbol.ZERO,
                "4フレーム後(elapsed=4): interval=1, idx=0 → RESULT_VALUES[0]=0",
            ),
            (
                45,
                "3",
                ReelSymbol.THREE,
                "45フレーム後(elapsed=45): interval=4, idx=3 → RESULT_VALUES[3]=3",
            ),
            (
                89,
                "0",
                ReelSymbol.ZERO,
                "89フレーム後(elapsed=89): interval=7, idx=0 → RESULT_VALUES[0]=0",
            ),
        ]
        for updates, expected_text, expected_symbol, label in cases:
            with self.subTest(label):
                reel = self._make_spinning_reel(updates)
                self.assertTrue(reel.is_spinning)
                self.assertEqual(reel.display_text, expected_text)
                self.assertEqual(reel.current_symbol, expected_symbol)


class TestReelStreak(unittest.TestCase):
    """リール出目の連番カウンタ（同出目加算・異出目リセット・4回目リセット）"""

    # (スピン列, 期待 streak, ラベル)
    CASES = [
        ([2],          1, "初回: streak=1（マークなし）"),
        ([2, 2],       2, "2連続: streak=2（灰色マーク1個相当）"),
        ([2, 2, 2],    3, "3連続: streak=3（黄色マーク2個相当）"),
        ([2, 2, 3],    1, "異出目でリセット: streak=1"),
        ([2, 2, 2, 2], 1, "4連続でリセット: streak=1（4回目が次の起点）"),
    ]

    def _force_result(self, reel, value):
        """リールを 1 回スピンして指定出目で停止させる（テスト用ヘルパ）"""
        with patch("reel.random.choice", return_value=value):
            reel.click()
            for _ in range(Reel.SPIN_DURATION):
                reel.update()

    def test_streak_behavior(self):
        """スピン列に応じて streak が正しく変化すること"""
        for results, expected, label in self.CASES:
            with self.subTest(label):
                reel = Reel()
                for v in results:
                    self._force_result(reel, v)
                self.assertEqual(reel.streak, expected)


class TestReelSerialize(unittest.TestCase):
    """Reel.to_dict() / Reel.from_dict() の往復シリアライズ"""

    def _force_result(self, reel, value):
        with patch("reel.random.choice", return_value=value):
            reel.click()
            for _ in range(Reel.SPIN_DURATION):
                reel.update()

    # (スピン列, 期待 to_dict 結果, ラベル)
    TO_DICT_CASES = [
        ([], {"last_result": None, "streak": 0}, "初期状態"),
        ([2, 2], {"last_result": 2, "streak": 2}, "同出目2連続"),
    ]

    def test_to_dict(self):
        for results, expected, label in self.TO_DICT_CASES:
            with self.subTest(label):
                reel = Reel()
                for v in results:
                    self._force_result(reel, v)
                self.assertEqual(reel.to_dict(), expected)

    def test_from_dict(self):
        reel = Reel.from_dict({"last_result": 2, "streak": 2})
        self.assertEqual(reel.streak, 2)
        self.assertFalse(reel.is_spinning)
        self.assertIsNone(reel.result)

    def test_roundtrip(self):
        original = Reel()
        self._force_result(original, 3)
        self._force_result(original, 3)
        restored = Reel.from_dict(original.to_dict())
        self.assertEqual(restored.streak, original.streak)


if __name__ == "__main__":
    unittest.main()
