import random
import math


class CityGrid:
    MAX_LEVEL = 4
    SPECIAL_LEVEL = 5

    def __init__(self, distance: float):
        self._distance = distance
        self._level = 0
        self._variant = random.randint(0, 8)

    @classmethod
    def from_state(cls, distance: float, level: int, variant: int) -> "CityGrid":
        grid = cls.__new__(cls)
        grid._distance = distance
        grid._level = level
        grid._variant = variant
        return grid

    @property
    def level(self) -> int:
        return self._level

    @property
    def variant(self) -> int:
        return self._variant

    def get_next_lv_growth(self) -> int:
        return 5**self._level + math.ceil(self._distance)

    @property
    def is_max_level(self) -> bool:
        return self._level >= self.MAX_LEVEL

    def level_up(self):
        self._level += 1

    def make_special(self):
        self._level = self.SPECIAL_LEVEL


class City:
    COLUMN_NUM = 14  # 画面横の長さ
    ROW_NUM = 36  # 画面縦の長さ
    MAX_FUNDS = 99999999

    def __init__(self):
        self._grid_table = self._get_initial_grid_table()
        self._population = self._sum_grid_levels(self._grid_table)
        self._rest_growth = 0
        self._funds = 0
        self._update_counter = 0
        self._is_game_over = False

    @property
    def funds(self) -> int:
        return self._funds

    @property
    def population(self) -> int:
        return self._population

    @property
    def is_game_over(self) -> bool:
        return self._is_game_over

    @staticmethod
    def _sum_grid_levels(grid_table) -> int:
        return sum(
            grid.level
            for col in grid_table
            for grid in col
            if grid.level < CityGrid.SPECIAL_LEVEL
        )

    def deduct_funds(self, amount: int):
        self._funds -= amount

    def update(self):
        self._update_counter += 1
        if self._update_counter >= 60:
            self._update_counter = 0
            self._funds = min(self._funds + self.population, self.MAX_FUNDS)

    def _get_initial_grid_table(self):
        center_x, center_y = self.COLUMN_NUM // 2, self.ROW_NUM // 2
        ret = [
            [
                CityGrid(math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2))
                for y in range(self.ROW_NUM)
            ]
            for x in range(self.COLUMN_NUM)
        ]
        ret[center_x][center_y].level_up()
        return ret

    def get_grid_level(self, col: int, row: int) -> int:
        return self._grid_table[col][row].level

    def get_grid_variant(self, col: int, row: int) -> int:
        return self._grid_table[col][row].variant

    def to_dict(self) -> dict:
        return {
            "column_num": self.COLUMN_NUM,
            "row_num": self.ROW_NUM,
            "rest_growth": self._rest_growth,
            "funds": self._funds,
            "grid_states": [
                [{"level": grid.level, "variant": grid.variant} for grid in col]
                for col in self._grid_table
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "City":
        city = cls.__new__(cls)
        city._rest_growth = data["rest_growth"]
        city._funds = data["funds"]
        city._update_counter = 0
        center_x = data["column_num"] // 2
        center_y = data["row_num"] // 2
        city._grid_table = [
            [
                CityGrid.from_state(
                    distance=((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5,
                    level=state["level"],
                    variant=state["variant"],
                )
                for y, state in enumerate(col)
            ]
            for x, col in enumerate(data["grid_states"])
        ]
        city._population = cls._sum_grid_levels(city._grid_table)
        city._is_game_over = all(
            grid.is_max_level for col in city._grid_table for grid in col
        )
        return city

    def apply_growth(self, amount, special=False):
        candidate_map = {}
        for x in range(self.COLUMN_NUM):
            for y in range(self.ROW_NUM):
                grid = self._grid_table[x][y]
                if grid.is_max_level:
                    continue
                candidate_map.setdefault(grid.get_next_lv_growth(), []).append((x, y))

        if not candidate_map:
            self._is_game_over = True
            return

        if special:
            min_amount = min(candidate_map.keys())
            x, y = random.choice(candidate_map[min_amount])
            self._population -= self._grid_table[x][y].level
            self._grid_table[x][y].make_special()
            return

        self._rest_growth += amount
        while candidate_map:
            min_amount = min(candidate_map.keys())
            if self._rest_growth < min_amount:
                break
            x, y = random.choice(candidate_map[min_amount])
            self._rest_growth -= min_amount
            self._grid_table[x][y].level_up()
            self._population += 1
            candidate_map[min_amount].remove((x, y))
            if not candidate_map[min_amount]:
                del candidate_map[min_amount]
