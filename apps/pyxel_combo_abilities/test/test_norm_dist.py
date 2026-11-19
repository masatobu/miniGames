"""NormDist（正規分布）のテスト。期待値は数式で表す。"""

import math
import unittest

from src.norm_dist import NormDist


class TestNormalPdf(unittest.TestCase):
    """FR1.1, FR1.2: 確率密度と point0"""

    def test_standard_normal_at_zero(self):
        # 標準正規分布の x=0: 1 / sqrt(2π)
        self.assertEqual(NormDist().normal_pdf(0), 1 / math.sqrt(2 * math.pi))

    def test_density_one_sigma_away(self):
        # x=μ+σ の密度は、ピーク（point0）の exp(-1/2) 倍
        norm = NormDist(mu=2, sigma=3)
        self.assertAlmostEqual(
            norm.normal_pdf(2 + 3), norm.point0 * math.exp(-0.5), places=12
        )

    def test_point0_is_density_at_mean(self):
        # point0 は平均での密度: 1 / (σ·sqrt(2π))
        norm = NormDist(mu=5, sigma=2)
        self.assertAlmostEqual(norm.point0, 1 / (2 * math.sqrt(2 * math.pi)), places=12)

    def test_default_is_standard_normal(self):
        # 既定は mu=0, sigma=1
        norm = NormDist()
        self.assertEqual((norm.mu, norm.sigma), (0, 1))


class TestInvNormalPdf(unittest.TestCase):
    """FR1.3〜FR1.5: 確率密度の逆算"""

    def test_inverse_of_density_one_sigma_away(self):
        # pdf(μ+σ) を逆算すると μ+σ に収束する（平均より大きい側）
        norm = NormDist(mu=2, sigma=3)
        self.assertAlmostEqual(
            norm.inv_normal_pdf(norm.normal_pdf(2 + 3)), 2 + 3, places=6
        )

    def test_peak_returns_mean(self):
        # p == point0 のとき、平均を返す
        norm = NormDist(mu=4, sigma=1)
        self.assertEqual(norm.inv_normal_pdf(norm.point0), 4)

    def test_larger_p_is_closer_to_mean(self):
        # p が大きいほど、平均に近い
        norm = NormDist()
        far = norm.inv_normal_pdf(0.5 * norm.point0)
        near = norm.inv_normal_pdf(0.6 * norm.point0)
        self.assertGreater(far, near)

    def test_out_of_range_raises(self):
        # p < 0 と p > point0 は ValueError
        norm = NormDist()
        with self.assertRaises(ValueError):
            norm.inv_normal_pdf(-0.001)
        with self.assertRaises(ValueError):
            norm.inv_normal_pdf(norm.point0 * 1.001)


if __name__ == "__main__":
    unittest.main()
