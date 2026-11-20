"""二項分布の確率質量と、その累積の逆算（移植元 binom_dist.py と同じ計算）。"""

import math


class BinomDist:
    """成功確率 p、試行回数 n の二項分布。"""

    def __init__(self, p=0.5, n=2):
        self.p = p
        self.n = n

    def binom_pdf(self, x):
        """x 回成功する確率を返す。"""
        return math.comb(self.n, x) * self.p**x * (1 - self.p) ** (self.n - x)

    def inv_binom_pdf(self, p):
        """累積確率がはじめて p を超える x を返す（超えなければ n）。

        p が 0 未満、または 1 を超えるときは ValueError。
        """
        if p < 0 or p > 1:
            raise ValueError(f"Error: out of  argument range ({p})")
        total = 0
        for i in range(self.n + 1):
            total += self.binom_pdf(i)
            if p < total:
                return i
        return self.n
