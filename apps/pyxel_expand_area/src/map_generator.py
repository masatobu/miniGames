# title: pyxel expand area
# author: masatobu

from abc import ABC, abstractmethod
import random
import math


class IMapGenerator(ABC):
    _instance = None

    @abstractmethod
    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_boss_power(self) -> int:
        pass

    @abstractmethod
    def get_coin_num(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_weapon_power(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_start_pos(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def get_boss_pos(self) -> tuple[int, int]:
        pass

    @classmethod
    def create(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class AreaBlockAlgorithmGenerator(IMapGenerator):
    BLOCK_SIZE = 6
    BLOCK_PATH_LEN = 4

    def __init__(self):
        self.area_data_map = {}
        self.area_block_lv_map = self._get_area_block_route(self.BLOCK_PATH_LEN)

    def _shuffle(self, lst: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
        shuffled = lst[:]
        random.shuffle(shuffled)
        return [
            shuffled[i : i + self.BLOCK_SIZE]
            for i in range(0, len(shuffled), self.BLOCK_SIZE)
        ]

    def _get_area_num_list(self, distance):
        sep_num = 2 ** (distance + 1) * 2
        start_num = 2 ** (distance + 1) - 1
        are_level_map = {i: i // 2 + start_num for i in range(sep_num)}
        # 2か所で武器を配置
        weapon_pos_set = {1, 5}
        return [
            (
                are_level_map[i % sep_num],
                are_level_map[i % sep_num] if i % 2 == 0 else 0,
                sep_num // 2 if i in weapon_pos_set else 0,
                are_level_map[i % sep_num] if i == 2 and distance == 0 else 0,
            )
            for i in range(self.BLOCK_SIZE**2)
        ]

    def _get_area_data(self, area_axis_x, area_axis_y):
        block_axis_pos = tuple(i // self.BLOCK_SIZE for i in (area_axis_x, area_axis_y))
        if block_axis_pos not in self.area_data_map:
            if block_axis_pos in self.area_block_lv_map:
                lv = self.area_block_lv_map[block_axis_pos]
                self.area_data_map[block_axis_pos] = self._shuffle(
                    self._get_area_num_list(lv)
                )
            else:
                self.area_data_map[block_axis_pos] = [
                    [(0, 0, 0, 0) for _ in range(self.BLOCK_SIZE)]
                    for _ in range(self.BLOCK_SIZE)
                ]
        return self.area_data_map[block_axis_pos][(area_axis_x) % self.BLOCK_SIZE][
            (area_axis_y) % self.BLOCK_SIZE
        ]

    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y)[0]

    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y)[1]

    def get_boss_power(self) -> int:
        return 2 ** (self.BLOCK_PATH_LEN + 1 + 1) - 1

    def _get_block_random_pos(self, block_axis_pos):
        block_edge_pos = tuple(p * self.BLOCK_SIZE for p in block_axis_pos)
        enable_list = [
            (x, y)
            for x in range(block_edge_pos[0], block_edge_pos[0] + self.BLOCK_SIZE)
            for y in range(block_edge_pos[1], block_edge_pos[1] + self.BLOCK_SIZE)
            if self.get_spawner_power(x, y) == 0 and self.get_weapon_power(x, y) == 0
        ]
        return random.choice(enable_list)

    def get_boss_pos(self) -> tuple[int, int]:
        boss_block_pos = [
            k for k, v in self.area_block_lv_map.items() if v == self.BLOCK_PATH_LEN
        ][0]
        return self._get_block_random_pos(boss_block_pos)

    def get_coin_num(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y)[1] * 2

    def get_weapon_power(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y)[2]

    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y)[3]

    def get_start_pos(self) -> tuple[int, int]:
        return self._get_block_random_pos((0, 0))

    @classmethod
    def _get_area_block_route(cls, goal_steps: int) -> dict[tuple[int, int], int]:
        goal_pos_list = [
            (x, y)
            for x in range(-goal_steps, goal_steps + 1)
            for y in range(-goal_steps, goal_steps + 1)
            if abs(x) + abs(y) == goal_steps
        ]
        goal_pos = random.choice(goal_pos_list)
        goal_direct_path = [(1 if goal_pos[0] > 0 else -1, 0)] * abs(goal_pos[0]) + [
            (0, 1 if goal_pos[1] > 0 else -1)
        ] * abs(goal_pos[1])
        random.shuffle(goal_direct_path)
        route = {(0, 0): 0}
        current_pos = (0, 0)
        for i, d in enumerate(goal_direct_path):
            current_pos = tuple(c + d for c, d in zip(current_pos, d))
            route[current_pos] = i + 1
        return route
