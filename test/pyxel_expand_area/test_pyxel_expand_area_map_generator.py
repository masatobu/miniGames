import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from pyxel_expand_area.main import (  # pylint: disable=C0413
    Direct,
    AreaBlockAlgorithmGenerator,
)


class TestAreaBlockAlgorithmGenerator(unittest.TestCase):
    @patch("pyxel_expand_area.main.AreaBlockAlgorithmGenerator._shuffle")
    def test_get(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        mock.return_value = [
            [
                (x, y, 1 if (x, y) == (0, 0) else 0, 1 if (x, y) == (1, 1) else 0)
                for x in range(s)
            ]
            for y in range(s)
        ]
        test_cases = [
            ("pos weapon", 0, 0, 0, 1, 0, (0, 0)),
            ("pos spawner", 1, 1, 2, 0, 1, (1, 1)),
            ("pos 1", s // 2, s // 2, s, 0, 0, (s // 2, s // 2)),
            ("pos 2", 0, s - 1, 0, 0, 0, (0, s - 1)),
            ("pos 3", s - 1, 0, (s - 1) * 2, 0, 0, (s - 1, 0)),
            ("pos 4", s - 1, s - 1, (s - 1) * 2, 0, 0, (s - 1, s - 1)),
        ]
        for (
            case_name,
            eep,
            efn,
            ecn,
            ewp,
            esp,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_enemy_power=eep,
                expected_fee_num=efn,
                expected_coin_num=ecn,
                expected_weapon_power=ewp,
                expected_spawner_pos=esp,
                area_axis=area_axis,
            ):

                map_genetator = AreaBlockAlgorithmGenerator()
                self.assertEqual(eep, map_genetator.get_enemy_power(*area_axis))
                self.assertEqual(efn, map_genetator.get_fee_num(*area_axis))
                self.assertEqual(ecn, map_genetator.get_coin_num(*area_axis))
                self.assertEqual(ewp, map_genetator.get_weapon_power(*area_axis))
                self.assertEqual(esp, map_genetator.get_spawner_power(*area_axis))

    def test_sum_area_block(self):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        map_genetator = AreaBlockAlgorithmGenerator()
        test_cases = [
            ("case 1", (0, 0)),
            ("case 2", (1, 1)),
            ("case 3", (-1, -1)),
            ("case 4", (3, 3)),
            ("case 5", (-3, -3)),
            ("case 6", (1, 0)),
        ]
        for (
            case_name,
            block_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                block_pos=block_pos,
            ):
                coin_sum = fee_sum = 0
                for x, y in [(x, y) for x in range(s) for y in range(s)]:
                    area_pos = tuple(p + b * s for p, b in zip((x, y), block_pos))
                    coin_sum += map_genetator.get_coin_num(*area_pos)
                    fee_sum += map_genetator.get_fee_num(*area_pos)
                self.assertEqual(0, coin_sum - fee_sum)

    def _count_group_num_map(self, n, zero_rate, sep_num, dup_num, start_num):
        counts = {}
        for i in range(int(n * (1 - zero_rate))):
            group = (i // dup_num) % sep_num
            counts[start_num + group] = counts.get(start_num + group, 0) + 1
        if zero_rate > 0:
            counts[0] = int(n * zero_rate)
        return counts

    def test_level_count(self):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("case 1", (0, 0), 2, 1, {(0, 0): 0}),
            ("case 2", (1, 0), 4, 3, {(1, 0): 1}),
            ("case 3", (1, 1), 8, 7, {(1, 1): 2}),
            ("case 4", (2, 1), 16, 15, {(2, 1): 3}),
            ("case 5", (-1, -1), 8, 7, {(-1, -1): 2}),
            ("lv chg case 1", (0, 0), 4, 3, {(0, 0): 1}),
            ("lv chg case 2", (1, 0), 2, 1, {(1, 0): 0}),
            ("lv chg case 3", (0, 0), 0, 0, {}),
            ("lv chg case 4", (1, 0), 0, 0, {(0, 0): 0}),
        ]
        for (
            case_name,
            block_pos,
            sep_num,
            start_num,
            block_path_map,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                block_pos=block_pos,
                sep_num=sep_num,
                start_num=start_num,
                block_path_map=block_path_map,
            ):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                result_count = {
                    elm: {} for elm in ["coin", "fee", "enemy", "weapon", "spawner"]
                }
                for x, y in [(x, y) for x in range(s) for y in range(s)]:
                    area_pos = tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for elm, num in (
                        ("coin", map_genetator.get_coin_num(*area_pos)),
                        ("fee", map_genetator.get_fee_num(*area_pos)),
                        ("enemy", map_genetator.get_enemy_power(*area_pos)),
                        ("weapon", map_genetator.get_weapon_power(*area_pos)),
                        ("spawner", map_genetator.get_spawner_power(*area_pos)),
                    ):
                        result_count[elm][num] = result_count[elm].get(num, 0) + 1
                half_div_map = self._count_group_num_map(
                    s**2, 0.5 if sep_num != 0 else 1, sep_num, 1, start_num
                )
                fee_div_map = self._count_group_num_map(
                    s**2, 0 if sep_num != 0 else 1, sep_num, 2, start_num
                )
                weapon_count_map = {sep_num: 2} | {0: s**2}
                spawner_count_map = {sep_num: 0} | {
                    2: 1 if block_path_map.get(block_pos, None) == 0 else 0
                }
                for elm, expect_map in (
                    ("coin", {k * 2: v for k, v in half_div_map.items()}),
                    ("enemy", half_div_map),
                    ("fee", fee_div_map),
                    (
                        "weapon",
                        {
                            0: s**2 - weapon_count_map[sep_num],
                            sep_num: weapon_count_map[sep_num],
                        },
                    ),
                    (
                        "spawner",
                        {
                            0: s**2 - spawner_count_map[sep_num],
                            2: spawner_count_map[sep_num],
                        },
                    ),
                ):
                    for num, count in expect_map.items():
                        if count == 0:
                            self.assertEqual(True, num not in result_count[elm], elm)
                        else:
                            self.assertEqual(count, result_count[elm][num], elm)

    @patch("pyxel_expand_area.main.AreaBlockAlgorithmGenerator._get_area_num_list")
    def test_dont_repeat(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        map_genetator = AreaBlockAlgorithmGenerator()
        mock.return_value = [
            (x, y, 1 if (x, y) == (0, 0) else 0, 1 if (x, y) == (1, 1) else 0)
            for x in range(s)
            for y in range(s)
        ]
        repeat_flg = True
        for x, y in [(x, y) for x in range(s) for y in range(s)]:
            if (
                y * 2 != map_genetator.get_coin_num(x, y)
                or x != map_genetator.get_fee_num(x, y)
                or y != map_genetator.get_enemy_power(x, y)
                or (1 if (x, y) == (0, 0) else 0)
                != map_genetator.get_weapon_power(x, y)
                or (1 if (x, y) == (1, 1) else 0)
                != map_genetator.get_spawner_power(x, y)
            ):
                repeat_flg = False
        self.assertEqual(False, repeat_flg)

    @patch("pyxel_expand_area.main.AreaBlockAlgorithmGenerator._get_area_num_list")
    def test_get_same_result(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        mock.return_value = [
            (x, y, 1 if (x, y) == (0, 0) else 0, 1 if (x, y) == (1, 1) else 0)
            for x in range(s)
            for y in range(s)
        ]
        result = []
        for _ in range(2):
            map_genetator = AreaBlockAlgorithmGenerator.create()
            sub_result = []
            for x, y in [(x, y) for x in range(s) for y in range(s)]:
                sub_result.append(
                    (
                        map_genetator.get_coin_num(x, y),
                        map_genetator.get_fee_num(x, y),
                        map_genetator.get_enemy_power(x, y),
                        map_genetator.get_weapon_power(x, y),
                        map_genetator.get_spawner_power(x, y),
                    )
                )
            result.append(sub_result)
        self.assertEqual(result[0], result[1])

    def test_spawner_coin(self):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        map_genetator = AreaBlockAlgorithmGenerator()
        for x, y in [(x, y) for x in range(s) for y in range(s)]:
            if map_genetator.get_spawner_power(x, y) != 0:
                self.assertEqual(4, map_genetator.get_coin_num(x, y))

    def test_get_pos(self):
        test_cases = [
            ("start", True, 0),
            ("boss", False, AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN),
        ]
        for case_name, check_start, expected_lv in test_cases:
            with self.subTest(
                case_name=case_name, check_start=check_start, lv=expected_lv
            ):
                map_genetator = AreaBlockAlgorithmGenerator()
                start_pos = map_genetator.get_start_pos()
                boss_pos = map_genetator.get_boss_pos()
                self.assertNotEqual(start_pos, boss_pos)
                check_pos = start_pos if check_start else boss_pos
                self.assertEqual(0, map_genetator.get_spawner_power(*check_pos))
                self.assertEqual(0, map_genetator.get_weapon_power(*check_pos))
                block_lv = map_genetator.area_block_lv_map[
                    tuple(
                        p // AreaBlockAlgorithmGenerator.BLOCK_SIZE for p in check_pos
                    )
                ]
                self.assertEqual(expected_lv, block_lv)

    def test_get_boss_power(self):
        map_genetator = AreaBlockAlgorithmGenerator()
        expected_lv = 2 ** (AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN + 1 + 1) - 1
        self.assertEqual(expected_lv, map_genetator.get_boss_power())

    def test_get_area_block_route(self):
        test_cases = [("path 1", 1), ("path 2", 2), ("path 5", 5), ("path 10", 10)]
        for case_name, path_len in test_cases:
            with self.subTest(case_name=case_name, path_len=path_len):
                route = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                    path_len
                )
                self.assertEqual(0, route[(0, 0)])
                visited = set()
                stack = [(0, 0)]
                visited.add((0, 0))
                step_max = 0

                while stack:
                    x, y = stack.pop()
                    current_step = route[(x, y)]
                    step_max = max(step_max, current_step)
                    for dx, dy in [d.value for d in Direct if d != Direct.NUTRAL]:
                        nx, ny = x + dx, y + dy
                        if (nx, ny) in route and (nx, ny) not in visited:
                            if abs(route[(nx, ny)] - current_step) == 1:
                                visited.add((nx, ny))
                                stack.append((nx, ny))
                self.assertEqual(len(visited), len(route))
                self.assertEqual(path_len, step_max)

    def test_dont_repeat_area_block_route(self):
        test_cases = [("path 1", 1), ("path 2", 2), ("path 5", 5), ("path 10", 10)]
        for case_name, path_len in test_cases:
            with self.subTest(case_name=case_name, path_len=path_len):
                different_flg = False
                for _ in range(10):
                    route1 = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                        path_len
                    )
                    route2 = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                        path_len
                    )
                    if route1 != route2:
                        different_flg = True
                        break
                self.assertEqual(True, different_flg)


if __name__ == "__main__":
    unittest.main()
