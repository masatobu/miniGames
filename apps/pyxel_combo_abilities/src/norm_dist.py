"""正規分布の確率密度と、その逆算（移植元 norm_dist.py と同じ計算）。"""

import math


class NormDist:
    """平均 mu、標準偏差 sigma の正規分布。"""

    PRECISION = 100

    def __init__(self, mu=0, sigma=1):
        self.mu = mu
        self.sigma = sigma
        self.point0 = self.normal_pdf(mu)

    def normal_pdf(self, x):
        """x での確率密度を返す。"""
        exponent = -((x - self.mu) ** 2) / (2 * self.sigma**2)
        coefficient = 1 / math.sqrt(2 * math.pi * self.sigma**2)
        return coefficient * math.exp(exponent)

    def inv_normal_pdf(self, p):
        """確率密度が p になる点のうち、平均以上の側の点を返す。

        p が 0 未満、または point0 を超えるときは ValueError。
        """
        if p < 0 or p > self.point0:
            raise ValueError(f"Error: out of  argument range ({p})")
        base = 1.0
        point = self.mu
        rate = 2
        for _ in range(self.PRECISION):
            ret = self.normal_pdf(point)
            direct = 1
            if p > ret:
                direct = -1
                rate = 0.5
            elif p == ret:
                break
            base *= rate
            point += direct * base
        return point
