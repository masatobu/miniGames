"""Garage（部品の枠とストック）のテスト。"""

import unittest

from src.garage import Garage
from src.resource import Component, Resource


class TestGarage(unittest.TestCase):
    """Garage の初期状態、ストック、レベルの算出のテスト。"""

    def test_get_resource_boxes(self):
        """初期状態は、全部品の枠が None で埋まる（STOCK は 5 枠）。"""
        garage = Garage()
        expect = {
            Component.ENGINE: [None, None],
            Component.GUN: [None, None],
            Component.BODY: [None, None],
            Component.STOCK: [None for _ in range(5)],
        }
        self.assertEqual(garage.boxes, expect)

    def test_reset_lv(self):
        """初期状態でレベルを算出すると、全部品がレベル 1 になる。"""
        garage = Garage()
        garage.reset_lv()
        expect = {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        self.assertEqual(garage.lv, expect)

    def test_set_stock(self):
        """ストックを設定すると先頭から詰まり、残りは None。再設定で置き換わる。"""
        garage = Garage()
        lst = [Resource.BOLT_BRONZE, Resource.STAR_BRONZE, Resource.THINGS_BRONZE]
        garage.set_stock(lst)
        exp = [
            Resource.BOLT_BRONZE,
            Resource.STAR_BRONZE,
            Resource.THINGS_BRONZE,
            None,
            None,
        ]
        self.assertEqual(garage.boxes[Component.STOCK], exp)
        lst = [Resource.BOLT_GOLD]
        garage.set_stock(lst)
        exp = [Resource.BOLT_GOLD, None, None, None, None]
        self.assertEqual(garage.boxes[Component.STOCK], exp)

    def test_reset_lv_bronze(self):
        """BRONZE だけの部品はレベル 2（BRONZE のランク値 1 + 1）。"""
        garage = Garage()
        garage.boxes[Component.BODY] = [Resource.THINGS_BRONZE, Resource.STAR_BRONZE]
        garage.reset_lv()
        expect = {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 2}
        self.assertEqual(garage.lv, expect)

    def test_reset_lv_none(self):
        """空の枠が 1 つでもあれば、その部品はレベル 1。"""
        garage = Garage()
        garage.boxes[Component.ENGINE] = [None, Resource.BOLT_GOLD]
        garage.reset_lv()
        expect = {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        self.assertEqual(garage.lv, expect)

    def test_reset_lv_silver(self):
        """SILVER と GOLD の組み合わせは、小さいほうの SILVER で決まる（2 + 1）。"""
        garage = Garage()
        garage.boxes[Component.GUN] = [Resource.STAR_SILVER, Resource.BOLT_GOLD]
        garage.reset_lv()
        expect = {Component.ENGINE: 1, Component.GUN: 3, Component.BODY: 1}
        self.assertEqual(garage.lv, expect)

    def test_reset_lv_gold(self):
        """GOLD 同士はレベル 4、SILVER 同士はレベル 3。"""
        garage = Garage()
        garage.boxes[Component.GUN] = [Resource.STAR_GOLD, Resource.BOLT_GOLD]
        garage.boxes[Component.BODY] = [Resource.THINGS_SILVER, Resource.STAR_SILVER]
        garage.reset_lv()
        expect = {Component.ENGINE: 1, Component.GUN: 4, Component.BODY: 3}
        self.assertEqual(garage.lv, expect)

    def test_reset_lv_formula(self):
        """全てのランクの組み合わせで、レベル = 小さいランク値 + 1。"""
        ranks = ["BRONZE", "SILVER", "GOLD"]
        for first in ranks:
            for second in ranks:
                garage = Garage()
                res_a = Resource[f"THINGS_{first}"]
                res_b = Resource[f"STAR_{second}"]
                garage.boxes[Component.BODY] = [res_a, res_b]
                garage.reset_lv()
                expect = min(Resource.get_rank(res_a), Resource.get_rank(res_b)) + 1
                with self.subTest(first=first, second=second):
                    self.assertEqual(garage.lv[Component.BODY], expect)

    def test_get_lv(self):
        """get_lv は、部品ごとのレベルを返す。"""
        garage = Garage()
        garage.boxes[Component.GUN] = [Resource.STAR_GOLD, Resource.BOLT_GOLD]
        garage.reset_lv()
        self.assertEqual(garage.get_lv(Component.GUN), 4)
        self.assertEqual(garage.get_lv(Component.ENGINE), 1)

    def test_get_box_resources(self):
        """get_box_resources は、部品の枠の内容を返す。"""
        garage = Garage()
        garage.set_stock([Resource.BOLT_GOLD])
        garage.boxes[Component.ENGINE] = [Resource.THINGS_BRONZE, None]
        self.assertEqual(
            garage.get_box_resources(Component.ENGINE), [Resource.THINGS_BRONZE, None]
        )
        self.assertEqual(
            garage.get_box_resources(Component.STOCK),
            [Resource.BOLT_GOLD, None, None, None, None],
        )

    def test_set_stock_too_long(self):
        """枠より長いリストは IndexError になり、ストックは変わらない。"""
        garage = Garage()
        garage.set_stock([Resource.BOLT_GOLD])
        too_long = [Resource.STAR_BRONZE for _ in range(len(Component.STOCK.value) + 1)]
        with self.assertRaises(IndexError):
            garage.set_stock(too_long)
        exp = [Resource.BOLT_GOLD, None, None, None, None]
        self.assertEqual(garage.boxes[Component.STOCK], exp)

    def test_change(self):
        """ストックの部品をエンジンの枠に入れ替える（移植元 test_resource_change）。"""
        garage = Garage()
        garage.set_stock(
            [Resource.BOLT_BRONZE, Resource.STAR_BRONZE, Resource.THINGS_BRONZE]
        )
        ret = garage.change((Component.STOCK, 2), (Component.ENGINE, 0))
        self.assertTrue(ret)
        self.assertEqual(garage.boxes[Component.ENGINE], [Resource.THINGS_BRONZE, None])
        self.assertEqual(
            garage.boxes[Component.STOCK],
            [Resource.BOLT_BRONZE, Resource.STAR_BRONZE, None, None, None],
        )
        self.assertEqual(garage.boxes[Component.GUN], [None, None])
        self.assertEqual(garage.boxes[Component.BODY], [None, None])
        # 空の枠が残るので、全部品がレベル 1（0 + 1）
        self.assertEqual(
            garage.lv, {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        )

    def test_change_none(self):
        """空の枠との入れ替えは成立し、中身もレベルも変わらない（移植元 _none）。"""
        garage = Garage()
        garage.set_stock(
            [Resource.BOLT_BRONZE, Resource.STAR_BRONZE, Resource.THINGS_BRONZE]
        )
        ret = garage.change((Component.STOCK, 4), (Component.ENGINE, 0))
        self.assertTrue(ret)
        self.assertEqual(garage.boxes[Component.ENGINE], [None, None])
        self.assertEqual(
            garage.boxes[Component.STOCK],
            [
                Resource.BOLT_BRONZE,
                Resource.STAR_BRONZE,
                Resource.THINGS_BRONZE,
                None,
                None,
            ],
        )
        self.assertEqual(
            garage.lv, {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        )

    def test_change_fail(self):
        """部品の型が合わない入れ替えは False で、枠もレベルも変わらない。"""
        garage = Garage()
        garage.set_stock(
            [Resource.STAR_BRONZE, Resource.STAR_GOLD, Resource.THINGS_BRONZE]
        )
        before_boxes = {comp: list(boxes) for comp, boxes in garage.boxes.items()}
        before_lv = dict(garage.lv)
        ret = garage.change((Component.ENGINE, 1), (Component.STOCK, 1))
        self.assertFalse(ret)
        self.assertEqual(garage.boxes, before_boxes)
        self.assertEqual(garage.lv, before_lv)

    def test_change_tuned(self):
        """チューニング対象の部品どうしでも入れ替えられる（移植元 _tuned）。"""
        garage = Garage()
        garage.set_stock(
            [Resource.STAR_BRONZE, Resource.STAR_GOLD, Resource.THINGS_BRONZE]
        )
        self.assertTrue(garage.change((Component.GUN, 0), (Component.STOCK, 0)))
        self.assertTrue(garage.change((Component.BODY, 1), (Component.STOCK, 1)))
        self.assertTrue(garage.change((Component.BODY, 1), (Component.GUN, 0)))
        self.assertEqual(garage.boxes[Component.ENGINE], [None, None])
        self.assertEqual(garage.boxes[Component.GUN], [Resource.STAR_GOLD, None])
        self.assertEqual(garage.boxes[Component.BODY], [None, Resource.STAR_BRONZE])
        self.assertEqual(
            garage.boxes[Component.STOCK],
            [None, None, Resource.THINGS_BRONZE, None, None],
        )
        self.assertEqual(
            garage.lv, {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        )

    def test_change_lvup(self):
        """枠が全て埋まった部品は、入れ替えのたびにレベルが上がる（移植元 _lvup）。"""
        garage = Garage()
        garage.set_stock(
            [Resource.STAR_BRONZE, Resource.STAR_GOLD, Resource.THINGS_BRONZE]
        )
        self.assertTrue(garage.change((Component.BODY, 1), (Component.STOCK, 1)))
        self.assertTrue(garage.change((Component.BODY, 0), (Component.STOCK, 2)))
        self.assertEqual(
            garage.boxes[Component.BODY], [Resource.THINGS_BRONZE, Resource.STAR_GOLD]
        )
        self.assertEqual(
            garage.boxes[Component.STOCK],
            [Resource.STAR_BRONZE, None, None, None, None],
        )
        self.assertEqual(garage.lv[Component.ENGINE], 1)
        self.assertEqual(garage.lv[Component.GUN], 1)
        self.assertEqual(garage.lv[Component.BODY], 2)

    def test_change_lv_formula(self):
        """入れ替え後のレベルは、枠のランク値の最小 + 1 になる。"""
        garage = Garage()
        garage.set_stock([Resource.STAR_SILVER, Resource.BOLT_GOLD])
        self.assertTrue(garage.change((Component.GUN, 0), (Component.STOCK, 0)))
        self.assertTrue(garage.change((Component.GUN, 1), (Component.STOCK, 1)))
        ranks = [Resource.get_rank(res) for res in garage.boxes[Component.GUN]]
        # SILVER と GOLD の小さいほうで決まる
        self.assertEqual(garage.lv[Component.GUN], min(ranks) + 1)
        self.assertEqual(garage.get_lv(Component.GUN), 3)

    def test_change_same_slot(self):
        """同じ枠どうしの入れ替えは成立し、中身は変わらず、レベルは再計算される。"""
        garage = Garage()
        garage.boxes[Component.BODY] = [Resource.THINGS_SILVER, Resource.STAR_GOLD]
        before = list(garage.boxes[Component.BODY])
        ret = garage.change((Component.BODY, 0), (Component.BODY, 0))
        self.assertTrue(ret)
        self.assertEqual(garage.boxes[Component.BODY], before)
        # lv の初期値 1 ではなく、再計算で最小ランク値 + 1 になる
        expect = min(Resource.get_rank(res) for res in before) + 1
        self.assertEqual(garage.lv[Component.BODY], expect)

    def test_change_both_empty(self):
        """空の枠どうしの入れ替えは成立し、何も変わらない。"""
        garage = Garage()
        ret = garage.change((Component.STOCK, 0), (Component.ENGINE, 1))
        self.assertTrue(ret)
        self.assertEqual(garage.boxes[Component.STOCK], [None for _ in range(5)])
        self.assertEqual(garage.boxes[Component.ENGINE], [None, None])
        self.assertEqual(
            garage.lv, {Component.ENGINE: 1, Component.GUN: 1, Component.BODY: 1}
        )


if __name__ == "__main__":
    unittest.main()
