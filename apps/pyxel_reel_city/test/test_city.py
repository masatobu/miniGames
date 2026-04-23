import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from city import CityGrid, City  # pylint: disable=C0413


class TestCityGrid(unittest.TestCase):
    def test_init(self):
        cases = [
            (0.0, 0),
            (1.0, 1),
            (1.5, 2),
        ]
        for dist, variant in cases:
            with self.subTest(distance=dist, variant=variant):
                with patch("city.random.randint", return_value=variant):
                    city_grid = CityGrid(dist)
                self.assertEqual(dist, city_grid._distance)  # pylint: disable=W0212
                self.assertEqual(0, city_grid.level)
                self.assertEqual(variant, city_grid.variant)
                self.assertFalse(city_grid.is_max_level)

    def test_make_special_sets_level_to_special(self):
        grid = CityGrid(distance=0)
        grid.make_special()
        self.assertEqual(CityGrid.SPECIAL_LEVEL, grid.level)

    def test_city_grid_is_max_level_true_when_level_4(self):
        grid = CityGrid(distance=0)
        for _ in range(CityGrid.MAX_LEVEL):
            grid.level_up()
        self.assertTrue(grid.is_max_level)

    def test_get_next_lv_growth(self):
        cases = [
            (0, 0, 5**0 + 0),
            (1, 0, 5**1 + 0),
            (2, 0, 5**2 + 0),
            (0, 1.0, 5**0 + 1),
            (0, 1.5, 5**0 + 2),
            (1, 0.5, 5**1 + 1),
        ]
        for lv, dist, growth in cases:
            with self.subTest(lv=lv, dist=dist):
                city_grid = CityGrid(dist)
                for _ in range(lv):
                    city_grid.level_up()
                self.assertEqual(growth, city_grid.get_next_lv_growth())
                self.assertEqual(lv, city_grid.level)


class TestCity(unittest.TestCase):
    def test_init(self):
        cases = [
            (0,),
            (5,),
            (8,),
        ]
        for variant in cases:
            with self.subTest(variant=variant):
                with patch("city.random.randint", return_value=variant):
                    city = City()
                cx, cy = City.COLUMN_NUM // 2, City.ROW_NUM // 2
                for col in range(City.COLUMN_NUM):
                    for row in range(City.ROW_NUM):
                        expected_level = 1 if (col == cx and row == cy) else 0
                        self.assertEqual(expected_level, city.get_grid_level(col, row))
                        self.assertEqual(variant, city.get_grid_variant(col, row))
                for x in range(City.COLUMN_NUM):
                    for y in range(City.ROW_NUM):
                        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                        self.assertEqual(
                            dist,
                            city._grid_table[x][y]._distance,  # pylint: disable=W0212
                        )
                self.assertFalse(city.is_game_over)

    def _check_grid_level(self, city, expected_lv_map):
        for x in range(City.COLUMN_NUM):
            for y in range(City.ROW_NUM):
                expected_level = expected_lv_map.get((x, y), 0)
                self.assertEqual(expected_level, city.get_grid_level(x, y))

    @patch("city.random.choice")
    def test_apply_growth(self, mock_choice):
        mock_choice.side_effect = lambda lst: lst[0]
        cx, cy = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        cases = [
            ("default", {}, [0]),
            ("add 2", {(cx - 1, cy): 1}, [2]),
            ("add 4", {(cx - 1, cy): 1, (cx, cy - 1): 1}, [4]),
            (
                "add 11",
                {
                    (cx - 1, cy): 1,
                    (cx, cy - 1): 1,
                    (cx, cy + 1): 1,
                    (cx + 1, cy): 1,
                    (cx - 2, cy): 1,
                },
                [11],
            ),
            ("add 1 + 2", {(cx - 1, cy): 1}, [1, 2]),
            ("add 3 + 1", {(cx - 1, cy): 1, (cx, cy - 1): 1}, [3, 1]),
        ]
        for case, expected_map, growth_list in cases:
            with self.subTest(case=case):
                city = City()
                for growth in growth_list:
                    city.apply_growth(growth)
                appended_map = {(cx, cy): 1}
                appended_map.update(expected_map)
                self._check_grid_level(city, appended_map)

    def test_game_over_when_all_grids_max_level(self):
        city = City()
        for col in city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()
        population_before = city.population
        city.apply_growth(9999)
        self.assertTrue(city.is_game_over)
        self.assertEqual(city.population, population_before)


class TestCityPopulation(unittest.TestCase):
    def test_population(self):
        """population がグリッドレベル合計を返すこと"""
        cases = [
            ("初期状態", 0, 1),  # apply_growth(0): レベルアップなし → center(lv1) = 1
            (
                "growth=2後",
                2,
                2,
            ),  # apply_growth(2): 隣接1グリッドlvup → center(lv1) + 隣(lv1) = 2
        ]
        for case, growth, expected in cases:
            with self.subTest(case=case):
                with patch("city.random.choice", side_effect=lambda lst: lst[0]):
                    city = City()
                    city.apply_growth(growth)
                self.assertEqual(expected, city.population)


class TestCityFunds(unittest.TestCase):
    def test_deduct_funds(self):
        """deduct_funds(amount) が funds から amount を差し引くこと"""
        city = City()
        city._funds = 15  # pylint: disable=W0212
        city.deduct_funds(6)
        self.assertEqual(9, city.funds)

    def test_funds_update_behavior(self):
        """フレーム経過と funds 増加の関係（初期状態: 中央グリッドのみ lv=1 → 合計レベル=1）"""
        cases = [
            ("初期値 (0フレーム)", 0, 0),
            ("インターバル未満 (59フレーム)", 59, 0),
            ("インターバル到達 (60フレーム)", 60, 1),
            ("2回繰り返し (120フレーム)", 120, 2),
        ]
        for case, frames, expected in cases:
            with self.subTest(case=case):
                city = City()
                for _ in range(frames):
                    city.update()
                self.assertEqual(expected, city.funds)

    def test_funds_capped_at_max(self):
        """資金が上限（99999999）を超えないこと"""
        funds_max = 99999999
        cases = [
            ("上限値スタート → 変化なし", funds_max, funds_max),
            ("上限-1スタート → ちょうど上限", funds_max - 1, funds_max),
        ]
        for case, initial, expected in cases:
            with self.subTest(case=case):
                city = City()
                city._funds = initial  # pylint: disable=W0212
                for _ in range(60):
                    city.update()
                self.assertEqual(expected, city.funds)


class TestCitySpecialGrid(unittest.TestCase):
    def _count_level5_grids(self, city):
        return sum(
            1
            for col in range(City.COLUMN_NUM)
            for row in range(City.ROW_NUM)
            if city.get_grid_level(col, row) == 5
        )

    def test_level5_grid_count_by_special_flag(self):
        """special フラグの有無でレベル 5 グリッドの生成数が変わる"""
        cases = [
            {"label": "special=True → 1箇所生まれる",  "special": True,  "expected": 1},
            {"label": "special省略 → 生まれない",       "special": False, "expected": 0},
        ]
        for case in cases:
            with self.subTest(label=case["label"]):
                city = City()
                city.apply_growth(0, special=case["special"])
                self.assertEqual(case["expected"], self._count_level5_grids(city))

    def test_special_grid_not_created_when_all_lv4(self):
        """レベル 0〜3 のグリッドがない盤面では指定があってもレベル 5 は生まれない"""
        city = City()
        for col in city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()
        city.apply_growth(0, special=True)
        self.assertEqual(0, self._count_level5_grids(city))

    def test_special_grid_targets_next_growth_candidate(self):
        """特殊グリッドは次の成長対象（最小閾値）グリッドになる"""
        city = City()
        cx, cy = City.COLUMN_NUM // 2, City.ROW_NUM // 2

        for col in city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()

        # 低閾値: 中心隣 (distance=1, threshold=1+1=2)
        city._grid_table[cx + 1][cy]._level = 0  # pylint: disable=W0212
        # 高閾値: 端 (distance大, threshold大)
        city._grid_table[0][0]._level = 0  # pylint: disable=W0212

        city.apply_growth(0, special=True)

        self.assertEqual(5, city.get_grid_level(cx + 1, cy))
        self.assertNotEqual(5, city.get_grid_level(0, 0))

    def test_special_grid_removes_original_level_from_population(self):
        """lv1〜3 のグリッドが特殊化されると、そのグリッドの人口寄与が 0 になること"""
        cx, cy = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        # 全グリッドを lv4 にして _population を確定させてから lv1 グリッドを1つ作る
        grid_states = [
            [{"level": 4 if not (x == cx + 1 and y == cy) else 1, "variant": 0}
             for y in range(City.ROW_NUM)]
            for x in range(City.COLUMN_NUM)
        ]
        city = City.from_dict({
            "column_num": City.COLUMN_NUM, "row_num": City.ROW_NUM,
            "rest_growth": 0, "funds": 0, "grid_states": grid_states,
        })
        population_before = city.population  # lv4×(N-1) + lv1×1

        city.apply_growth(0, special=True)  # cx+1,cy の lv1 グリッドが lv5 に

        # lv1 の寄与分（1）が population から引かれるべき
        self.assertEqual(population_before - 1, city.population)

    def test_special_grid_excluded_from_population_and_funds_after_restore(self):
        """from_dict 復元後の population と資金増加がレベル 5 グリッドを除外していること"""
        city = City()
        city.apply_growth(0, special=True)  # lv0 グリッドが lv5 に
        restored = City.from_dict(city.to_dict())

        # population が lv5 分を加算していないこと
        self.assertEqual(city.population, restored.population)

        # 60 フレーム後の資金増加が lv5 除外後の population と一致すること
        funds_before = restored.funds
        for _ in range(60):
            restored.update()
        self.assertEqual(funds_before + restored.population, restored.funds)


class TestCityExportImport(unittest.TestCase):
    def test_to_dict_values(self):
        """to_dict() が各グリッドの level・variant と _rest_growth を正しく出力すること"""
        with patch("city.random.randint", return_value=5):
            city = City()

        data = city.to_dict()

        self.assertEqual(0, data["rest_growth"])
        cx, cy = City.COLUMN_NUM // 2, City.ROW_NUM // 2
        for x in range(City.COLUMN_NUM):
            for y in range(City.ROW_NUM):
                expected_level = 1 if (x == cx and y == cy) else 0
                with self.subTest(x=x, y=y):
                    self.assertEqual(expected_level, data["grid_states"][x][y]["level"])
                    self.assertEqual(5, data["grid_states"][x][y]["variant"])

    def test_roundtrip(self):
        """to_dict() → from_dict() で get_grid_table() と _rest_growth が完全に復元されること"""
        cases = [
            # apply_growth(3): _rest_growth=1 が残るケース
            # center(4,6)lv1 → 隣接(distance=1)の必要成長度=2
            # _rest_growth: 0+3=3 → 1グリッドlvup(cost=2) → 残り1
            ("rest_growth が残るケース", 3),
            # apply_growth(10): 複数グリッドがレベルアップするケース
            ("複数グリッドがレベルアップするケース", 10),
        ]
        for case, amount in cases:
            with self.subTest(case=case):
                with patch("city.random.choice", side_effect=lambda lst: lst[0]):
                    city = City()
                    city.apply_growth(amount)

                restored = City.from_dict(city.to_dict())

                for col in range(City.COLUMN_NUM):
                    for row in range(City.ROW_NUM):
                        self.assertEqual(
                            city.get_grid_level(col, row),
                            restored.get_grid_level(col, row),
                        )
                        self.assertEqual(
                            city.get_grid_variant(col, row),
                            restored.get_grid_variant(col, row),
                        )
                self.assertEqual(
                    city._rest_growth,  # pylint: disable=W0212
                    restored._rest_growth,  # pylint: disable=W0212
                )

    def test_to_dict_includes_funds(self):
        """to_dict() に funds が含まれること"""
        city = City()
        for _ in range(60):
            city.update()  # funds = 1（中央グリッドのみlv=1 → 合計1増加）
        data = city.to_dict()
        self.assertIn("funds", data)
        self.assertEqual(city.funds, data["funds"])

    def test_roundtrip_restores_funds(self):
        """to_dict() → from_dict() で funds が復元されること"""
        city = City()
        for _ in range(120):
            city.update()  # funds = 2（2インターバル分）
        restored = City.from_dict(city.to_dict())
        self.assertEqual(city.funds, restored.funds)

    def test_roundtrip_restores_game_over(self):
        """ゲームオーバー状態で to_dict() → from_dict() すると is_game_over が True になること"""
        city = City()
        for col in city._grid_table:  # pylint: disable=W0212
            for grid in col:
                while not grid.is_max_level:
                    grid.level_up()
        city.apply_growth(0)
        restored = City.from_dict(city.to_dict())
        self.assertTrue(restored.is_game_over)
