"""BinomDist（二項分布）のテスト。期待値は数式で表す。"""

import math
import unittest

from src.binom_dist import BinomDist


class TestBinomPdf(unittest.TestCase):
    """FR2.1, FR2.2: 確率質量"""

    def test_default_is_fair_coin_twice(self):
        # 既定は p=0.5, n=2
        dist = BinomDist()
        self.assertEqual((dist.p, dist.n), (0.5, 2))

    def test_pdf_matches_formula(self):
        # P(x) = C(n, x) * p^x * (1-p)^(n-x)
        dist = BinomDist(p=0.3, n=10)
        for x in range(11):
            expected = math.comb(10, x) * 0.3**x * 0.7 ** (10 - x)
            self.assertAlmostEqual(dist.binom_pdf(x), expected, places=12)

    def test_pdf_sums_to_one(self):
        dist = BinomDist(p=0.7, n=10)
        total = sum(dist.binom_pdf(x) for x in range(11))
        self.assertAlmostEqual(total, 1.0, places=12)


class TestInvBinomPdf(unittest.TestCase):
    """FR2.3, FR2.4: 累積の逆算"""

    def test_boundaries_of_fair_coin_twice(self):
        # n=2, p=0.5 の確率は 0.25, 0.5, 0.25。累積は 0.25, 0.75, 1.0
        # 累積が p を超える最初の x を返す（p < 累積）
        dist = BinomDist(p=0.5, n=2)
        self.assertEqual(dist.inv_binom_pdf(0.0), 0)  # 0.0 < 0.25
        self.assertEqual(dist.inv_binom_pdf(0.25), 1)  # 0.25 < 0.25 は偽 → 次の x
        self.assertEqual(dist.inv_binom_pdf(0.74), 1)  # 0.74 < 0.75
        self.assertEqual(dist.inv_binom_pdf(0.75), 2)  # 0.75 < 0.75 は偽 → 次の x

    def test_one_returns_n(self):
        # 累積がどこでも p を超えなければ n を返す
        self.assertEqual(BinomDist(p=0.3, n=10).inv_binom_pdf(1), 10)

    def test_out_of_range_raises(self):
        dist = BinomDist()
        with self.assertRaises(ValueError):
            dist.inv_binom_pdf(-0.001)
        with self.assertRaises(ValueError):
            dist.inv_binom_pdf(1.001)


if __name__ == "__main__":
    unittest.main()
