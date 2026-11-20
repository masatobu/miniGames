"""Resource（リソース）と Component（部品）の静的な定義のテスト。"""

import unittest

from src.resource import Component, Resource

KINDS = ("THINGS", "STAR", "BOLT")
# ランク名 -> (ランク値, 基本の重み, レベルごとの加算)
RANKS = {
    "BRONZE": (1, 100, 0),
    "SILVER": (2, 10, 3),
    "GOLD": (3, 0, 1),
}


def resource_of(kind, rank):
    """種類とランク名から Resource を得る（例：THINGS, BRONZE）。"""
    return Resource[f"{kind}_{rank}"]


class TestResourceAvails(unittest.TestCase):
    """FR1.1: avails は 9 種類を返し、MASK 値を含まない"""

    def test_avails_has_every_kind_and_rank(self):
        # 3 種類 x 3 ランク = 9
        expected = {resource_of(k, r) for k in KINDS for r in RANKS}
        self.assertEqual(len(Resource.avails()), len(KINDS) * len(RANKS))
        self.assertEqual(set(Resource.avails()), expected)

    def test_avails_excludes_masks(self):
        for member in Resource.avails():
            self.assertNotIn("MASK", member.name)
            self.assertNotIsInstance(member.value, int)


class TestResourceRank(unittest.TestCase):
    """FR1.2: get_rank はランク値、None は 0"""

    def test_rank_value_by_rank_name(self):
        for kind in KINDS:
            for rank, (rank_value, _, _) in RANKS.items():
                with self.subTest(kind=kind, rank=rank):
                    self.assertEqual(
                        Resource.get_rank(resource_of(kind, rank)), rank_value
                    )

    def test_rank_of_none_is_zero(self):
        self.assertEqual(Resource.get_rank(None), 0)

    def test_rank_of_non_resource_is_zero(self):
        # Resource 以外（MASK の整数値や別の型）も 0
        self.assertEqual(Resource.get_rank(10), 0)
        self.assertEqual(Resource.get_rank("THINGS_GOLD"), 0)


class TestResourceCheckMask(unittest.TestCase):
    """FR1.3: check_mask は None なら True、種類が一致すれば True"""

    def test_none_mask_or_none_target_is_true(self):
        gold = Resource.STAR_GOLD
        self.assertTrue(Resource.check_mask(None, gold))
        self.assertTrue(Resource.check_mask(Resource.STAR_MASK, None))
        self.assertTrue(Resource.check_mask(None, None))

    def test_matching_kind_is_true(self):
        masks = {k: Resource[f"{k}_MASK"] for k in KINDS}
        for kind in KINDS:
            for rank in RANKS:
                with self.subTest(kind=kind, rank=rank):
                    self.assertTrue(
                        Resource.check_mask(masks[kind], resource_of(kind, rank))
                    )

    def test_mismatching_kind_is_false(self):
        masks = {k: Resource[f"{k}_MASK"] for k in KINDS}
        for mask_kind in KINDS:
            for target_kind in KINDS:
                if mask_kind == target_kind:
                    continue
                with self.subTest(mask=mask_kind, target=target_kind):
                    self.assertFalse(
                        Resource.check_mask(
                            masks[mask_kind], resource_of(target_kind, "BRONZE")
                        )
                    )


class TestResourceWeight(unittest.TestCase):
    """FR1.5: 出現の重み（基本 + 加算 x レベル）はランクだけで決まる"""

    def test_weight_is_base_plus_per_level_times_level(self):
        for kind in KINDS:
            for rank, (_, base, per_level) in RANKS.items():
                member = resource_of(kind, rank)
                for level in (1, 5):
                    with self.subTest(kind=kind, rank=rank, level=level):
                        weight = member.value[1] + member.value[2] * level
                        self.assertEqual(weight, base + per_level * level)

    def test_weight_has_no_difference_between_kinds(self):
        for rank in RANKS:
            weights = {resource_of(k, rank).value[1:] for k in KINDS}
            self.assertEqual(len(weights), 1, rank)


class TestComponent(unittest.TestCase):
    """FR2.1〜FR2.3: 部品ごとの制約リストと tuned"""

    def test_engine_gun_body_masks(self):
        self.assertEqual(
            Component.ENGINE.value, [Resource.THINGS_MASK, Resource.BOLT_MASK]
        )
        self.assertEqual(Component.GUN.value, [Resource.STAR_MASK, Resource.BOLT_MASK])
        self.assertEqual(
            Component.BODY.value, [Resource.THINGS_MASK, Resource.STAR_MASK]
        )

    def test_stock_is_five_empty_slots(self):
        self.assertEqual(Component.STOCK.value, [None] * 5)

    def test_tuned_is_engine_gun_body_in_order(self):
        self.assertEqual(
            Component.tuned(), [Component.ENGINE, Component.GUN, Component.BODY]
        )
        self.assertNotIn(Component.STOCK, Component.tuned())


if __name__ == "__main__":
    unittest.main()
