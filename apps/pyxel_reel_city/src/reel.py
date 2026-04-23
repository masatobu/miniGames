import random
from enum import IntEnum


class ReelSymbol(IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3


class Reel:
    RESULT_VALUES = (0, 1, 2, 3)
    SPIN_DURATION = 90  # 約3秒 @ 30fps
    STREAK_MAX = 4

    def __init__(self):
        self._result = None
        self._spin_frames_left = 0
        self._just_stopped = False
        self._last_result = None
        self._streak = 0

    @property
    def result(self):
        return self._result

    @property
    def is_spinning(self):
        return self._spin_frames_left > 0

    @property
    def just_stopped(self):
        return self._just_stopped

    @property
    def streak(self):
        return self._streak

    @property
    def current_symbol(self) -> ReelSymbol:
        """現在の表示シンボル（スピン中はアニメーション値、停止後は出目）"""
        if self._result is not None:
            return ReelSymbol(self._result)
        if self.is_spinning:
            elapsed = self.SPIN_DURATION - self._spin_frames_left
            interval = max(1, elapsed * 8 // self.SPIN_DURATION)
            idx = (elapsed // interval) % len(self.RESULT_VALUES)
            return ReelSymbol(self.RESULT_VALUES[idx])
        return ReelSymbol.ZERO

    @property
    def display_text(self):
        return str(self.current_symbol.value)

    def to_dict(self):
        return {"last_result": self._last_result, "streak": self._streak}

    @classmethod
    def from_dict(cls, data):
        reel = cls()
        reel._last_result = data["last_result"]
        reel._streak = data["streak"]
        return reel

    def click(self):
        if self.is_spinning:
            return
        self._result = None
        self._spin_frames_left = self.SPIN_DURATION

    def update(self):
        self._just_stopped = False
        if self._spin_frames_left == 0:
            return
        self._spin_frames_left -= 1
        if self._spin_frames_left > 0:
            return
        self._result = random.choice(self.RESULT_VALUES)
        self._just_stopped = True
        if self._result == self._last_result:
            self._streak += 1
            if self._streak == self.STREAK_MAX:
                self._streak = 1
        else:
            self._streak = 1
        self._last_result = self._result
