# title: pyxel dig smith
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum
import math


class Item(Enum):
    METAL_1 = (1, 4)
    METAL_2 = (2, 4)
    METAL_3 = (3, 4)
    METAL_4 = (4, 4)
    METAL_5 = (5, 4)
    JEWEL = (7, 4)  # ← 順序を前に移動（get_item()でレアアイテムを優先判定）
    COAL = (6, 4)


class Pickaxe(Enum):
    METAL_1 = (1, 5)
    METAL_2 = (2, 5)
    METAL_3 = (3, 5)
    METAL_4 = (4, 5)
    METAL_5 = (5, 5)
    JEWEL = (6, 5)


class IFieldGenerator(ABC):
    LAYERS = [
        ((3, 12), (1, 2)),
        ((12, 22), (2, 2)),
        ((22, 32), (3, 2)),
        ((32, 42), (4, 2)),
        ((42, None), (5, 2)),
    ]
    _instance = None

    @abstractmethod
    def get_item(self, axis_x, axis_y) -> Item:
        pass

    @classmethod
    def get_layer_image_pos(cls, axis_y):
        for y_range, pos in cls.LAYERS:
            if y_range[0] <= axis_y and (y_range[1] is None or axis_y < y_range[1]):
                return pos
        return None

    @classmethod
    def get_lightest_path(cls, start_pos, rel_pos, dig_pos_set):
        start = start_pos
        goal = (start_pos[0] + rel_pos[0], start_pos[1] + rel_pos[1])

        # 探索範囲制限
        min_x = min(start[0], goal[0]) - 1
        max_x = max(start[0], goal[0]) + 1
        min_y = min(start[1], goal[1]) - 1
        max_y = max(start[1], goal[1]) + 1

        def in_range(p):
            return min_x <= p[0] <= max_x and min_y <= p[1] <= max_y

        # pos -> (dist, cost)
        best = {start: (0, 0)}
        prev = {}

        queue = [start]
        head = 0

        while head < len(queue):
            cur = queue[head]
            head += 1

            cur_dist, cur_cost = best[cur]

            if cur == goal:
                continue

            for dx, dy in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
                nxt = (cur[0] + dx, cur[1] + dy)
                if not in_range(nxt):
                    continue

                nd = cur_dist + 1

                # コスト計算
                if nxt[1] <= 1 or nxt in dig_pos_set:
                    step_cost = 0
                else:
                    step_cost = 1

                nc = cur_cost + step_cost

                if (
                    nxt not in best
                    or nd < best[nxt][0]
                    or (nd == best[nxt][0] and nc < best[nxt][1])
                ):
                    best[nxt] = (nd, nc)
                    prev[nxt] = cur
                    queue.append(nxt)

        # 経路復元
        path = [goal]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return path

    @classmethod
    def create(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class FieldGenerator(IFieldGenerator):
    APPEAR_PEAK_MAP = {
        Item.METAL_1: 7,
        Item.METAL_2: 14,
        Item.METAL_3: 24,
        Item.METAL_4: 34,
        Item.METAL_5: 45,
        Item.JEWEL: 48,  # JEWEL ピークを層5に移動（ID-033）
    }
    # APPEAR_PEAK_MAP = {  # for test stability
    #     Item.METAL_1: 4,
    #     Item.METAL_2: 5,
    #     Item.METAL_3: 6,
    #     Item.METAL_4: 7,
    #     Item.METAL_5: 8,
    #     Item.JEWEL: 9,
    # }
    FLAT_APPEAR_RATE_MAP = {
        Item.COAL: (0, 0.15),  # y >= 0 で一定確率 0.15（全深度、既存動作維持）
        Item.JEWEL: (
            48,
            0.01,
        ),  # y >= 48 で一定確率 0.01（ID-034-10.5.1 確率再調整 5%→1%）
    }
    # FLAT_APPEAR_RATE_MAP = {Item.COAL: 0.2}  # for test stability

    def __init__(self):
        self.pickaxe_power_map = {
            p: self.LAYERS[i][0][1] if i < len(self.LAYERS) else None
            for i, p in enumerate(sorted(Pickaxe, key=lambda e: e.value[0]))
        }

    def get_hash(self, value):
        return hash(value)

    def get_item(self, axis_x, axis_y):
        for item in Item:
            if self._is_appear(axis_x, axis_y, item):
                return item
        return None

    def _is_appear(self, x, y, item):
        rate = (self.get_hash((x, y)) % 10000) / 10000
        if item in self.FLAT_APPEAR_RATE_MAP:
            # FLAT_APPEAR_RATE_MAP は (threshold_y, flat_prob) タプル形式で統一
            # threshold_y以上のみ出現、未満は出現しない（確率0）
            threshold_y, flat_prob = self.FLAT_APPEAR_RATE_MAP[item]
            threathold = flat_prob if y >= threshold_y else 0.0
        else:
            threathold = self._normal_pdf(y, self.APPEAR_PEAK_MAP[item])
        return rate < threathold

    def _normal_pdf(self, x, mu=0, sigma=3, amplify=1.4):
        """
        標準偏差をもつ正規分布の確率密度関数を計算します。
        :param x: 確率密度関数を評価する値
        :param mu: 平均値(デフォルトは0)
        :param sigma: 標準偏差(デフォルトは3)
        :param amplify: 確率密度の倍率(デフォルトは1.4)
        :return: 確率密度関数の値
        """
        exponent = -((x - mu) ** 2) / (2 * sigma**2)
        coefficient = 1 / math.sqrt(2 * math.pi * sigma**2)
        return min(1.0, coefficient * math.exp(exponent) * amplify)

    def is_digable(self, axis_x, axis_y, pickaxe):  # pylint: disable=W0613
        if pickaxe is None or pickaxe not in Pickaxe:
            return False
        power = self.pickaxe_power_map[pickaxe]
        if power is None:
            return True
        return axis_y < power


class PickaxeGenerator:
    ITEM_TO_PICKAXE_MAP = {
        Item.METAL_1: [None, Pickaxe.METAL_1],
        Item.METAL_2: [Pickaxe.METAL_1, Pickaxe.METAL_2],
        Item.METAL_3: [Pickaxe.METAL_2, Pickaxe.METAL_3],
        Item.METAL_4: [Pickaxe.METAL_3, Pickaxe.METAL_4],
        Item.METAL_5: [Pickaxe.METAL_4, Pickaxe.METAL_5],
        Item.JEWEL: [Pickaxe.METAL_5, Pickaxe.JEWEL],
    }

    @classmethod
    def get_recipe(cls, item: Item):
        if item not in cls.ITEM_TO_PICKAXE_MAP:
            return []
        return [item] + cls.ITEM_TO_PICKAXE_MAP.get(item, None)

    @classmethod
    def is_generatable(cls, item_set):
        if not item_set:
            return False
        metal_1_material = {Item.COAL, Item.METAL_1}
        have_pickaxe = not set(Pickaxe).isdisjoint(item_set)
        have_material = metal_1_material.issubset(item_set)
        return have_pickaxe or have_material
