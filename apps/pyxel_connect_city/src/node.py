import random
from dataclasses import dataclass
from enum import Enum

_ROW_ZONES = {
    "TOPMOST": (0, 1),
    "UPPER": (2, 3),
    "MIDDLE": (4, 7),
    "LOWER": (8, 9),
    "BOTTOM": (10, 11),
}
_COL_ZONES = {
    "LEFT": (0, 1),
    "CENTER": (2, 4),
    "RIGHT": (5, 6),
}


class NodeType(Enum):
    FOREST = "FOREST"
    MOUNTAIN = "MOUNTAIN"
    CITY = "CITY"
    FACTORY = "FACTORY"


class MaterialType(Enum):
    TREE = "TREE"
    STONE = "STONE"
    WOOD = "WOOD"
    STONE_BLOCK = "STONE_BLOCK"
    PLYWOOD = "PLYWOOD"


@dataclass(frozen=True)
class NodeParams:
    production_rates: dict
    consumption_rates: dict
    production_limits: dict
    growth_limits: dict

    _RATE = 3
    _LIMIT = 15
    _CITY_MAINTENANCE_RATE = 2

    _CITY_GROWTH_MATERIALS = {
        0: MaterialType.TREE,
        1: MaterialType.WOOD,
        2: MaterialType.STONE_BLOCK,
        3: MaterialType.PLYWOOD,
    }

    _FACTORY_CHAIN = {
        0: (MaterialType.TREE, MaterialType.WOOD, MaterialType.STONE),
        1: (MaterialType.STONE, MaterialType.STONE_BLOCK, MaterialType.WOOD),
        2: (MaterialType.WOOD, MaterialType.PLYWOOD, None),
    }

    @property
    def production_stock_cols(self):
        return list(self.production_limits.keys())

    @property
    def consumption_stock_cols(self):
        return list(self.consumption_rates.keys())

    @property
    def growth_stock_cols(self):
        return list(self.growth_limits.keys())

    @classmethod
    def get(cls, node_type, level=0) -> "NodeParams":
        if node_type == NodeType.FOREST:
            return cls(
                production_rates={MaterialType.TREE: cls._RATE},
                consumption_rates={},
                production_limits={MaterialType.TREE: cls._RATE},
                growth_limits={},
            )
        if node_type == NodeType.MOUNTAIN:
            return cls(
                production_rates={MaterialType.STONE: cls._RATE},
                consumption_rates={},
                production_limits={MaterialType.STONE: cls._RATE},
                growth_limits={},
            )
        if node_type == NodeType.CITY:
            if level == 4:
                return cls(
                    production_rates={},
                    consumption_rates={
                        MaterialType.PLYWOOD: cls._CITY_MAINTENANCE_RATE
                    },
                    production_limits={},
                    growth_limits={MaterialType.PLYWOOD: cls._LIMIT},
                )
            growth = cls._CITY_GROWTH_MATERIALS.get(level)
            return cls(
                production_rates={},
                consumption_rates={},
                production_limits={},
                growth_limits={growth: cls._LIMIT} if growth else {},
            )
        if node_type == NodeType.FACTORY and level in cls._FACTORY_CHAIN:
            input_m, output_m, growth_m = cls._FACTORY_CHAIN[level]
            return cls(
                production_rates={output_m: cls._RATE},
                consumption_rates={input_m: cls._RATE},
                production_limits={output_m: cls._RATE},
                growth_limits={growth_m: cls._LIMIT} if growth_m else {},
            )
        raise ValueError(f"Unknown node type: {node_type}")


class Node:
    def __init__(
        self,
        col,
        row,
        node_type,
        production_stock=None,
        consumption_stock=None,
        growth_stock=None,
        level=0,
    ):
        self._col = col
        self._row = row
        self._node_type = node_type
        self._params = NodeParams.get(node_type, level)
        self._production_stock = {
            m: (production_stock or {}).get(m, 0)
            for m in self._params.production_stock_cols
        }
        self._consumption_stock = {
            m: (consumption_stock or {}).get(m, 0)
            for m in self._params.consumption_stock_cols
        }
        self._growth_stock = {
            m: (growth_stock or {}).get(m, 0) for m in self._params.growth_stock_cols
        }
        self._level = level

    @property
    def col(self):
        return self._col

    @property
    def row(self):
        return self._row

    @property
    def node_type(self):
        return self._node_type

    @property
    def params(self):
        return self._params

    @property
    def level(self):
        return self._level

    def get_production_stock(self, material: MaterialType) -> int:
        return self._production_stock[material]

    def get_consumption_stock(self, material: MaterialType) -> int:
        return self._consumption_stock[material]

    def get_growth_stock(self, material: MaterialType) -> int:
        return self._growth_stock[material]

    def add_production_stock(self, material: MaterialType, num: int):
        limit = self._params.production_limits[material]
        self._production_stock[material] = min(
            self._production_stock[material] + num, limit
        )

    def subtract_production_stock(self, material: MaterialType, num: int):
        self._production_stock[material] -= num

    def subtract_consumption_stock(self, material: MaterialType, num: int):
        self._consumption_stock[material] -= num

    def add_consumption_stock(self, material: MaterialType, num: int):
        limit = self._params.consumption_rates[material]
        self._consumption_stock[material] = min(
            self._consumption_stock[material] + num, limit
        )

    def is_growth_complete(self) -> bool:
        limits = self._params.growth_limits
        if not limits:
            return False
        return all(self._growth_stock[m] == limits[m] for m in limits)

    @property
    def is_maintenance_mode(self) -> bool:
        return (
            bool(self._params.consumption_stock_cols)
            and not self._params.production_stock_cols
            and bool(self._params.growth_stock_cols)
        )

    def _reset_params(self):
        self._params = NodeParams.get(self._node_type, self._level)
        self._production_stock = {m: 0 for m in self._params.production_stock_cols}
        self._consumption_stock = {m: 0 for m in self._params.consumption_stock_cols}
        self._growth_stock = {m: 0 for m in self._params.growth_stock_cols}

    def level_up(self):
        self._level += 1
        prev_growth = self._growth_stock
        self._reset_params()
        # 維持モードへの遷移時は growth_stock を引き継ぐ（Lv3→Lv4 の PLYWOOD キャリーオーバー）
        if self.is_maintenance_mode:
            for m in self._params.growth_stock_cols:
                if m in prev_growth:
                    self._growth_stock[m] = prev_growth[m]

    def subtract_growth_stock(self, material: MaterialType, num: int):
        self._growth_stock[material] -= num

    def level_down(self):
        # stocks を全リセット: 降格はペナルティで再成長を要求する
        self._level -= 1
        self._reset_params()

    def add_growth_stock(self, material: MaterialType, num: int):
        limit = self._params.growth_limits[material]
        self._growth_stock[material] = min(self._growth_stock[material] + num, limit)

    def to_dict(self):
        return {
            "col": self._col,
            "row": self._row,
            "type": self._node_type.value,
            "production_stock": {m.value: v for m, v in self._production_stock.items()},
            "consumption_stock": {
                m.value: v for m, v in self._consumption_stock.items()
            },
            "growth_stock": {m.value: v for m, v in self._growth_stock.items()},
            "level": self._level,
        }

    @classmethod
    def from_dict(cls, d):
        def _parse_stock(raw):
            return (
                {MaterialType(k): v for k, v in raw.items()}
                if raw is not None
                else None
            )

        return cls(
            col=d["col"],
            row=d["row"],
            node_type=NodeType(d["type"]),
            production_stock=_parse_stock(d.get("production_stock")),
            consumption_stock=_parse_stock(d.get("consumption_stock")),
            growth_stock=_parse_stock(d.get("growth_stock")),
            level=d.get("level", 0),
        )


class NodeManager:
    HEX_COLUMN_NUM = 7
    HEX_ROW_NUM = 12
    FOREST_COUNT = 3
    MOUNTAIN_COUNT = 1
    INITIAL_CITY_POS = (3, 5)
    PLACEMENT_LIMITED_TYPES = {NodeType.CITY, NodeType.FACTORY}
    DELETABLE_TYPES = {NodeType.CITY, NodeType.FACTORY}

    def __init__(self, nodes=None):
        if nodes is None:
            self._nodes = self._create_initial_nodes()
        else:
            self._nodes = nodes

    def _create_initial_nodes(self):
        city_pos = self.INITIAL_CITY_POS

        mountain_row_zone = random.choice(["TOPMOST", "BOTTOM"])
        mountain_col_zone = random.choice(list(_COL_ZONES))

        forest_middle_col_zone = random.choice(["LEFT", "RIGHT"])

        upper_forbidden = {forest_middle_col_zone}
        if mountain_row_zone == "TOPMOST":
            upper_forbidden.add(mountain_col_zone)
        forest_upper_col_zone = random.choice(
            [cz for cz in _COL_ZONES if cz not in upper_forbidden]
        )

        lower_forbidden = {forest_middle_col_zone}
        if mountain_row_zone == "BOTTOM":
            lower_forbidden.add(mountain_col_zone)
        forest_lower_col_zone = random.choice(
            [cz for cz in _COL_ZONES if cz not in lower_forbidden]
        )

        def rand_in(col_zone, row_zone):
            c_start, c_end = _COL_ZONES[col_zone]
            r_start, r_end = _ROW_ZONES[row_zone]
            return random.randint(c_start, c_end), random.randint(r_start, r_end)

        mountain_pos = rand_in(mountain_col_zone, mountain_row_zone)
        forest_middle_pos = rand_in(forest_middle_col_zone, "MIDDLE")
        forest_upper_pos = rand_in(forest_upper_col_zone, "UPPER")
        forest_lower_pos = rand_in(forest_lower_col_zone, "LOWER")

        positions_and_types = [
            (mountain_pos, NodeType.MOUNTAIN),
            (forest_middle_pos, NodeType.FOREST),
            (forest_upper_pos, NodeType.FOREST),
            (forest_lower_pos, NodeType.FOREST),
            (city_pos, NodeType.CITY),
        ]
        return [Node(col=c, row=r, node_type=t) for (c, r), t in positions_and_types]

    def positions(self) -> list:
        return [(n.col, n.row) for n in self._nodes]

    def has_node(self, col, row) -> bool:
        return any(n.col == col and n.row == row for n in self._nodes)

    def get_node(self, col, row):
        return next((n for n in self._nodes if n.col == col and n.row == row), None)

    def is_deletable_node(self, col, row) -> bool:
        node = self.get_node(col, row)
        return node is not None and node.node_type in self.DELETABLE_TYPES

    def is_connectable_edge(self, pos1, pos2) -> bool:
        """少なくとも片方のエンドポイントが CITY/FACTORY であれば True"""
        n1 = self.get_node(*pos1)
        n2 = self.get_node(*pos2)
        return (n1 is not None and n1.node_type in self.DELETABLE_TYPES) or (
            n2 is not None and n2.node_type in self.DELETABLE_TYPES
        )

    def _count_by_type(self, node_type) -> int:
        return sum(1 for n in self._nodes if n.node_type == node_type)

    def place_node(self, col, row, node_type, blocked_grids=None) -> bool:
        if node_type in self.PLACEMENT_LIMITED_TYPES:
            if self.available_placement_count(node_type) == 0:
                return False
        if self.has_node(col, row):
            return False
        if blocked_grids and (col, row) in blocked_grids:
            return False
        self._nodes.append(Node(col=col, row=row, node_type=node_type))
        return True

    def _factory_limit(self) -> int:
        return sum(
            (n.level >= 1) + (n.level >= 2)
            for n in self._nodes
            if n.node_type == NodeType.CITY
        )

    def _lv4_city_count(self) -> int:
        return sum(
            1 for n in self._nodes if n.node_type == NodeType.CITY and n.level == 4
        )

    def _city_limit(self) -> int:
        return 1 + min(self._lv4_city_count(), 2)

    def is_game_clear(self) -> bool:
        return self._lv4_city_count() >= 3

    def available_placement_count(self, node_type) -> int | None:
        if node_type == NodeType.FACTORY:
            limit = self._factory_limit()
        elif node_type == NodeType.CITY:
            limit = self._city_limit()
        else:
            return None
        return max(0, limit - self._count_by_type(node_type))

    def remove_node(self, col, row) -> bool:
        if not self.is_deletable_node(col, row):
            return False
        self._nodes.remove(self.get_node(col, row))
        return True

    def to_list(self):
        return [n.to_dict() for n in self._nodes]

    @classmethod
    def from_list(cls, data):
        return cls(nodes=[Node.from_dict(d) for d in data])
