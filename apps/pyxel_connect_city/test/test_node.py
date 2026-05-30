import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from node import (  # pylint: disable=C0413
    NodeType,
    Node,
    NodeManager,
    NodeParams,
    MaterialType,
)


class TestNode(unittest.TestCase):
    def test_node_initialization(self):
        """Node の各パラメータを正しく初期化すること"""
        cases = [
            {
                "desc": "FOREST ノードの初期化",
                "node_type": NodeType.FOREST,
                "expected_production_stock_cols": [MaterialType.TREE],
                "expected_consumption_stock_cols": [],
                "expected_growth_stock_cols": [],
            },
            {
                "desc": "MOUNTAIN ノードの初期化",
                "node_type": NodeType.MOUNTAIN,
                "expected_production_stock_cols": [MaterialType.STONE],
                "expected_consumption_stock_cols": [],
                "expected_growth_stock_cols": [],
            },
            {
                "desc": "CITY ノードの初期化",
                "node_type": NodeType.CITY,
                "expected_production_stock_cols": [],
                "expected_consumption_stock_cols": [],
                "expected_growth_stock_cols": [MaterialType.TREE],
            },
            {
                "desc": "FACTORY ノードの初期化",
                "node_type": NodeType.FACTORY,
                "expected_production_stock_cols": [MaterialType.WOOD],
                "expected_consumption_stock_cols": [MaterialType.TREE],
                "expected_growth_stock_cols": [MaterialType.STONE],
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                node = Node(col=1, row=2, node_type=case["node_type"])
                self.assertEqual(
                    {k: 0 for k in case["expected_production_stock_cols"]},
                    node._production_stock,  # pylint: disable=W0212
                )
                self.assertEqual(
                    {k: 0 for k in case["expected_consumption_stock_cols"]},
                    node._consumption_stock,  # pylint: disable=W0212
                )
                self.assertEqual(
                    {k: 0 for k in case["expected_growth_stock_cols"]},
                    node._growth_stock,  # pylint: disable=W0212
                )
                self.assertEqual(0, node.level)

    def test_node_to_dict(self):
        """Node.to_dict() が col / row / type / stocks / level を辞書で返すこと"""
        node = Node(col=2, row=3, node_type=NodeType.FOREST)
        self.assertEqual(
            {
                "col": 2,
                "row": 3,
                "type": "FOREST",
                "production_stock": {"TREE": 0},
                "consumption_stock": {},
                "growth_stock": {},
                "level": 0,
            },
            node.to_dict(),
        )

    def test_node_from_dict(self):
        """Node.from_dict() が辞書から col / row / type / stocks / level を復元すること"""
        node = Node.from_dict(
            {
                "col": 1,
                "row": 4,
                "type": "MOUNTAIN",
                "production_stock": {"STONE": 50},
                "consumption_stock": {},
                "growth_stock": {},
                "level": 0,
            }
        )
        self.assertEqual(1, node.col)
        self.assertEqual(4, node.row)
        self.assertEqual(NodeType.MOUNTAIN, node.node_type)
        self.assertEqual(
            {MaterialType.STONE: 50}, node._production_stock  # pylint: disable=W0212
        )
        self.assertEqual({}, node._consumption_stock)  # pylint: disable=W0212
        self.assertEqual({}, node._growth_stock)  # pylint: disable=W0212
        self.assertEqual(0, node.level)

    def test_node_round_trip(self):
        """to_dict() → from_dict() で col / row / type / stocks がすべて復元されること"""
        original = Node(col=2, row=3, node_type=NodeType.FACTORY)
        original._production_stock[MaterialType.WOOD] = 30  # pylint: disable=W0212
        original._consumption_stock[MaterialType.TREE] = 10  # pylint: disable=W0212
        restored = Node.from_dict(original.to_dict())
        self.assertEqual(original.col, restored.col)
        self.assertEqual(original.row, restored.row)
        self.assertEqual(original.node_type, restored.node_type)
        self.assertEqual(
            original._production_stock,  # pylint: disable=W0212
            restored._production_stock,  # pylint: disable=W0212
        )
        self.assertEqual(
            original._consumption_stock,  # pylint: disable=W0212
            restored._consumption_stock,  # pylint: disable=W0212
        )
        self.assertEqual(
            original._growth_stock, restored._growth_stock  # pylint: disable=W0212
        )

    def test_add_production_stock(self):
        material = MaterialType.TREE
        cases = [
            ("通常加算", 2, 2),
            ("上限到達", 3, 3),
            ("上限超過はクリップ", 5, 3),  # production_limits[TREE] = 3
        ]
        for desc, amount, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    }
                )
                node.add_production_stock(material, amount)
                self.assertEqual(expected, node.get_production_stock(material))

    def test_subtract_production_stock(self):
        material = MaterialType.TREE
        cases = [
            ("全量減算", 3, 0),
            ("一部減算", 1, 2),
        ]
        for desc, amount, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 3},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    }
                )
                node.subtract_production_stock(material, amount)
                self.assertEqual(expected, node.get_production_stock(material))

    def test_add_consumption_stock(self):
        material = MaterialType.TREE
        cases = [
            ("通常加算", 2, 2),
            ("上限到達", 3, 3),
            ("上限超過はクリップ", 5, 3),  # consumption_rates[TREE] = 3
        ]
        for desc, amount, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    }
                )
                node.add_consumption_stock(material, amount)
                self.assertEqual(expected, node.get_consumption_stock(material))

    def test_subtract_consumption_stock(self):
        material = MaterialType.TREE
        cases = [
            ("消化蓄積から指定量を減算する", 3, 0),
            ("一部減算", 1, 2),
        ]
        for desc, amount, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 3},
                        "growth_stock": {},
                        "level": 0,
                    }
                )
                node.subtract_consumption_stock(material, amount)
                self.assertEqual(expected, node.get_consumption_stock(material))

    def test_add_growth_stock(self):
        material = MaterialType.WOOD
        cases = [
            ("通常加算", 5, 5),
            ("上限到達", 15, 15),
            ("上限超過はクリップ", 20, 15),  # growth_limits[WOOD] = 15
        ]
        for desc, amount, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {"WOOD": 0},
                        "level": 1,
                    }
                )
                node.add_growth_stock(material, amount)
                self.assertEqual(expected, node.get_growth_stock(material))

    def test_is_growth_complete_for_city_lv0(self):
        cases = [
            ("TREE未満", 0, False),
            ("TREE上限到達", 15, True),  # growth_limits[TREE] = 15
        ]
        for desc, tree, expected in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {"TREE": tree},
                        "level": 0,
                    }
                )
                self.assertEqual(expected, node.is_growth_complete())

    def test_growth_complete_returns_false_for_no_growth_node(self):
        cases = [
            ("FOREST", "FOREST", {"TREE": 0}, {}, {}, 0),
            ("MOUNTAIN", "MOUNTAIN", {"STONE": 0}, {}, {}, 0),
            ("FACTORY", "FACTORY", {"WOOD": 0}, {"TREE": 0}, {}, 0),
            ("CITY lv1", "CITY", {}, {}, {}, 1),
        ]
        for desc, node_type, prod, cons, growth, level in cases:
            with self.subTest(desc):
                node = Node.from_dict(
                    {
                        "col": 0,
                        "row": 0,
                        "type": node_type,
                        "production_stock": prod,
                        "consumption_stock": cons,
                        "growth_stock": growth,
                        "level": level,
                    }
                )
                self.assertFalse(node.is_growth_complete())

    def test_level_up_city_lv0_to_lv1(self):
        """CITY lv0 で level_up() するとレベル・params・全蓄積が lv1 の状態になること"""
        node = Node.from_dict(
            {
                "col": 0,
                "row": 0,
                "type": "CITY",
                "production_stock": {},
                "consumption_stock": {},
                "growth_stock": {"TREE": 15},
                "level": 0,
            }
        )
        node.level_up()
        self.assertEqual(1, node.level)
        self.assertEqual({MaterialType.WOOD: 15}, node.params.growth_limits)
        self.assertEqual({}, node._production_stock)  # pylint: disable=W0212
        self.assertEqual({}, node._consumption_stock)  # pylint: disable=W0212
        self.assertEqual(
            {MaterialType.WOOD: 0}, node._growth_stock  # pylint: disable=W0212
        )

    def test_level_up_lv3_to_lv4(self):
        """CITY lv3 で level_up() するとレベル・params・全蓄積が lv4 の状態になること"""
        node = Node.from_dict(
            {
                "col": 0,
                "row": 0,
                "type": "CITY",
                "production_stock": {},
                "consumption_stock": {},
                "growth_stock": {"PLYWOOD": 15},
                "level": 3,
            }
        )
        node.level_up()
        self.assertEqual(4, node.level)
        self.assertEqual({MaterialType.PLYWOOD: 15}, node.params.growth_limits)
        self.assertEqual({}, node._production_stock)  # pylint: disable=W0212
        self.assertEqual(
            {MaterialType.PLYWOOD: 0}, node._consumption_stock  # pylint: disable=W0212
        )
        self.assertEqual(
            {MaterialType.PLYWOOD: 15}, node._growth_stock  # pylint: disable=W0212
        )

    def test_level_down(self):
        """level_down 時の状態リセット"""
        node = Node(col=0, row=0, node_type=NodeType.CITY, level=4)
        node.add_growth_stock(MaterialType.PLYWOOD, 10)
        node.add_consumption_stock(MaterialType.PLYWOOD, 2)
        node.level_down()
        self.assertEqual(node.level, 3)
        self.assertEqual(node.get_growth_stock(MaterialType.PLYWOOD), 0)
        # Lv3 は consumption_stock_cols が空
        self.assertEqual(node.params.consumption_stock_cols, [])


class TestNodeManager(unittest.TestCase):
    def test_nodes_to_list_and_from_list(self):
        """to_list() → from_list() でノード一覧が完全に復元されること"""
        manager = NodeManager(
            nodes=[
                Node(col=0, row=0, node_type=NodeType.FOREST),
                Node(col=1, row=1, node_type=NodeType.MOUNTAIN),
            ]
        )
        manager.get_node(0, 0)._production_stock[  # pylint: disable=W0212
            MaterialType.TREE
        ] = 75
        restored = NodeManager.from_list(manager.to_list())
        self.assertEqual(len(manager.positions()), len(restored.positions()))
        for orig, rest in zip(manager.positions(), restored.positions()):
            self.assertEqual(orig, rest)
            self.assertEqual(
                manager.get_node(*orig).node_type, restored.get_node(*rest).node_type
            )
            self.assertEqual(
                manager.get_node(*orig)._production_stock,  # pylint: disable=W0212
                restored.get_node(*rest)._production_stock,  # pylint: disable=W0212
            )
            self.assertEqual(
                manager.get_node(*orig)._consumption_stock,  # pylint: disable=W0212
                restored.get_node(*rest)._consumption_stock,  # pylint: disable=W0212
            )
            self.assertEqual(
                manager.get_node(*orig)._growth_stock,  # pylint: disable=W0212
                restored.get_node(*rest)._growth_stock,  # pylint: disable=W0212
            )

    def test_place_node_returns_true_when_accepted(self):
        """place_node() が配置可能な位置へのノード追加を許可して True を返し、指定位置・タイプで配置されること"""
        cases = [
            {
                "desc": "空き位置にノードを追加",
                "col": 0,
                "row": 0,
                "node_type": NodeType.CITY,
                "blocked_grids": set(),
            },
            {
                "desc": "blocked_grids に含まれない位置への配置を許可",
                "col": 3,
                "row": 0,
                "node_type": NodeType.CITY,
                "blocked_grids": {(1, 0), (2, 0)},
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = NodeManager(nodes=[])
                result = manager.place_node(
                    col=case["col"],
                    row=case["row"],
                    node_type=case["node_type"],
                    blocked_grids=case["blocked_grids"],
                )
                self.assertTrue(result)
                self.assertEqual(1, len(manager.positions()))
                added = manager.get_node(case["col"], case["row"])
                self.assertEqual(case["col"], added.col)
                self.assertEqual(case["row"], added.row)
                self.assertEqual(case["node_type"], added.node_type)

    def test_place_node_returns_false_when_rejected(self):
        """place_node() が拒否条件に合致する位置への配置を拒否して False を返し、ノード数が変わらないこと"""
        cases = [
            {
                "desc": "既にノードがある位置への追加を拒否",
                "initial_nodes": [Node(0, 0, NodeType.CITY)],
                "col": 0,
                "row": 0,
                "node_type": NodeType.FACTORY,
                "blocked_grids": set(),
                "expected_count": 1,
            },
            {
                "desc": "blocked_grids に含まれる位置への配置を拒否",
                "initial_nodes": [],
                "col": 1,
                "row": 0,
                "node_type": NodeType.CITY,
                "blocked_grids": {(1, 0), (2, 0)},
                "expected_count": 0,
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = NodeManager(nodes=case["initial_nodes"])
                result = manager.place_node(
                    col=case["col"],
                    row=case["row"],
                    node_type=case["node_type"],
                    blocked_grids=case["blocked_grids"],
                )
                self.assertFalse(result)
                self.assertEqual(case["expected_count"], len(manager.positions()))

    def test_positions_returns_all_node_positions(self):
        """positions() が全ノードの (col, row) リストを順序通りに返すこと"""
        cases = [
            {
                "desc": "ノードなし: 空リストを返す",
                "nodes": [],
                "expected": [],
            },
            {
                "desc": "ノード1件: 単一要素リストを返す",
                "nodes": [Node(1, 2, NodeType.CITY)],
                "expected": [(1, 2)],
            },
            {
                "desc": "ノード複数件: 追加順で全位置を返す",
                "nodes": [Node(1, 2, NodeType.CITY), Node(3, 4, NodeType.FACTORY)],
                "expected": [(1, 2), (3, 4)],
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = NodeManager(nodes=case["nodes"])
                self.assertEqual(case["expected"], manager.positions())

    def _nodes_by_type(self, manager, node_type):
        return [
            (col, row)
            for col, row in manager.positions()
            if manager.get_node(col, row).node_type == node_type
        ]

    def _col_zone(self, col):
        """col 番号から列ゾーン名を返す（LEFT: 0-1, CENTER: 2-4, RIGHT: 5-6）"""
        if col <= 1:
            return "LEFT"
        if col <= 4:
            return "CENTER"
        return "RIGHT"

    def test_initial_nodes(self):
        """初期ノードが構成・位置・ゾーン制約・列ゾーン隣接制約をすべて満たすこと（200回試行）

        - 数: 森×3・山×1・街×1 の合計5個、位置の重複なし
        - 街: (3, 5) 固定
        - 山: 最上部（row 0-1）または最下部（row 10-11）ゾーンに配置
        - 森3つ: 上部（row 2-3）・中部（row 4-7）・下部（row 8-9）に1つずつ配置
        - 中部の森: 中列（col 2-4）を避けて左列か右列に配置
        - 中部森 ↔ 上部森: 異なる列ゾーン
        - 中部森 ↔ 下部森: 異なる列ゾーン
        - 山が最上部のとき: 上部森 ↔ 山が異なる列ゾーン
        - 山が最下部のとき: 下部森 ↔ 山が異なる列ゾーン
        - 山の最上部・最下部ケースが両方発生する
        """
        topmost_count = 0
        bottom_count = 0
        for _ in range(200):
            manager = NodeManager()
            positions = manager.positions()

            self.assertEqual(5, len(positions))
            self.assertEqual(len(positions), len(set(positions)))

            self.assertEqual([(3, 5)], self._nodes_by_type(manager, NodeType.CITY))

            forests = self._nodes_by_type(manager, NodeType.FOREST)
            self.assertEqual(3, len(forests))
            forest_col_by_row = {row: col for col, row in forests}

            middle_col = next(
                col for row, col in forest_col_by_row.items() if 4 <= row <= 7
            )
            upper_col = next(
                col for row, col in forest_col_by_row.items() if 2 <= row <= 3
            )
            lower_col = next(
                col for row, col in forest_col_by_row.items() if 8 <= row <= 9
            )

            self.assertFalse(
                2 <= middle_col <= 4,
                f"中部森 col={middle_col} は中列ゾーン（2-4）不可",
            )

            self.assertNotEqual(
                self._col_zone(middle_col),
                self._col_zone(upper_col),
                f"中部森 col={middle_col}, 上部森 col={upper_col} は同列ゾーン不可",
            )
            self.assertNotEqual(
                self._col_zone(middle_col),
                self._col_zone(lower_col),
                f"中部森 col={middle_col}, 下部森 col={lower_col} は同列ゾーン不可",
            )

            ((mountain_col, mountain_row),) = self._nodes_by_type(
                manager, NodeType.MOUNTAIN
            )
            if mountain_row <= 1:
                topmost_count += 1
                self.assertNotEqual(
                    self._col_zone(upper_col),
                    self._col_zone(mountain_col),
                    f"上部森 col={upper_col}, 最上部山 col={mountain_col} は同列ゾーン不可",
                )
            else:
                bottom_count += 1
                self.assertNotEqual(
                    self._col_zone(lower_col),
                    self._col_zone(mountain_col),
                    f"下部森 col={lower_col}, 最下部山 col={mountain_col} は同列ゾーン不可",
                )

        self.assertGreater(topmost_count, 0, "最上部ケースが1件も発生しなかった")
        self.assertGreater(bottom_count, 0, "最下部ケースが1件も発生しなかった")

    def test_is_game_clear(self):
        """is_game_clear: Lv4 街が3つ以上でクリア、それ未満は未クリア"""
        cases = [
            {
                "desc": "Lv4 街なし: クリアでない",
                "nodes": [],
                "expected": False,
            },
            {
                "desc": "Lv4 街2つ: クリアでない",
                "nodes": [
                    Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                    Node(col=1, row=0, node_type=NodeType.CITY, level=4),
                ],
                "expected": False,
            },
            {
                "desc": "Lv4 街3つ: クリア",
                "nodes": [
                    Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                    Node(col=1, row=0, node_type=NodeType.CITY, level=4),
                    Node(col=2, row=0, node_type=NodeType.CITY, level=4),
                ],
                "expected": True,
            },
            {
                "desc": "Lv4 街2つ + Lv3 街1つ: クリアでない",
                "nodes": [
                    Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                    Node(col=1, row=0, node_type=NodeType.CITY, level=4),
                    Node(col=2, row=0, node_type=NodeType.CITY, level=3),
                ],
                "expected": False,
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = NodeManager(nodes=case["nodes"])
                self.assertEqual(manager.is_game_clear(), case["expected"])


class TestNodeManagerRemove(unittest.TestCase):
    def test_remove_node_returns_true_and_decrements_count(self):
        """存在するノードを remove_node() すると True を返しノード数が 1 減ること"""
        manager = NodeManager(
            nodes=[
                Node(1, 2, NodeType.CITY),
                Node(3, 4, NodeType.FACTORY),
            ]
        )
        result = manager.remove_node(1, 2)
        self.assertTrue(result)
        self.assertEqual(1, len(manager.positions()))
        self.assertFalse(manager.has_node(1, 2))

    def test_remove_node_returns_false_when_not_found(self):
        """存在しないノードを remove_node() すると False を返しノード数が変わらないこと"""
        manager = NodeManager(nodes=[Node(1, 2, NodeType.CITY)])
        result = manager.remove_node(5, 5)
        self.assertFalse(result)
        self.assertEqual(1, len(manager.positions()))

    def test_remove_node_returns_false_for_non_deletable_types(self):
        """FOREST・MOUNTAIN ノードは remove_node() で削除できず False を返しノード数が変わらないこと"""
        cases = [
            ("FOREST は削除不可", NodeType.FOREST),
            ("MOUNTAIN は削除不可", NodeType.MOUNTAIN),
        ]
        for desc, node_type in cases:
            with self.subTest(desc):
                manager = NodeManager(nodes=[Node(1, 2, node_type)])
                result = manager.remove_node(1, 2)
                self.assertFalse(result)
                self.assertEqual(1, len(manager.positions()))


class TestPlaceNodePlacementLimit(unittest.TestCase):

    def _make_manager_with(self, node_specs):
        """node_specs: list of (col, row, NodeType, level)"""
        nodes = [
            Node(col=c, row=r, node_type=t, level=lv) for c, r, t, lv in node_specs
        ]
        return NodeManager(nodes=nodes)

    def test_place_node_respects_placement_limit(self):
        cases = [
            ("街0個・上限1→配置できる", [], (0, 0, NodeType.CITY), True),
            (
                "街1個配置済み・上限1→配置できない",
                [(0, 0, NodeType.CITY, 0)],
                (1, 0, NodeType.CITY),
                False,
            ),
            ("街0個・工場上限0→配置できない", [], (0, 0, NodeType.FACTORY), False),
            (
                "工場1個配置済み・上限0→配置できない",
                [(0, 0, NodeType.FACTORY, 0)],
                (1, 0, NodeType.FACTORY),
                False,
            ),
            (
                "街Lv4が1個→上限2・街1個配置済み→あと1個配置できる",
                [(0, 0, NodeType.CITY, 4)],
                (1, 0, NodeType.CITY),
                True,
            ),
            (
                "街lv1が1個→上限2・街2個配置済み→配置できない",
                [(0, 0, NodeType.CITY, 1), (1, 0, NodeType.CITY, 0)],
                (2, 0, NodeType.CITY),
                False,
            ),
            (
                "街Lv1×1→工場上限1・工場1個配置済み→配置できない",
                [(0, 0, NodeType.CITY, 1), (1, 0, NodeType.FACTORY, 0)],
                (2, 0, NodeType.FACTORY),
                False,
            ),
            (
                "森は配置上限の対象外",
                [(0, 0, NodeType.FOREST, 0), (1, 0, NodeType.FOREST, 0)],
                (2, 0, NodeType.FOREST),
                True,
            ),
        ]
        for desc, node_specs, (col, row, node_type), expected in cases:
            with self.subTest(desc):
                mgr = self._make_manager_with(node_specs)
                self.assertEqual(expected, mgr.place_node(col, row, node_type))


class TestAvailablePlacementCount(unittest.TestCase):

    def _make_manager_with(self, node_specs):
        nodes = [
            Node(col=c, row=r, node_type=t, level=lv) for c, r, t, lv in node_specs
        ]
        return NodeManager(nodes=nodes)

    def test_city_available_placement_count(self):
        # city_limit = 1 + min(count(city.level == 4), 2)
        cases = [
            ("初期状態（街0個）→街上限1→配置可能数1", [], 1),
            (
                "街1個配置済み（Lv0）→配置可能数0",
                [(0, 0, NodeType.CITY, 0)],
                0,
            ),
            (
                "Lv4街1個存在→街上限2→配置可能数1",
                [(0, 0, NodeType.CITY, 4)],
                1,
            ),
            (
                "Lv4街2個存在→街上限3・街2個設置済み→配置可能数1",
                [(0, 0, NodeType.CITY, 4), (1, 0, NodeType.CITY, 4)],
                1,
            ),
            (
                "Lv4街3個は上限に寄与しない→街上限3→配置可能数0",
                [
                    (0, 0, NodeType.CITY, 4),
                    (1, 0, NodeType.CITY, 4),
                    (2, 0, NodeType.CITY, 4),
                ],
                0,
            ),
            (
                "上限超過時もマイナスにならず0→上限1・街2個",
                [(0, 0, NodeType.CITY, 0), (1, 0, NodeType.CITY, 0)],
                0,
            ),
        ]
        for desc, node_specs, expected in cases:
            with self.subTest(desc):
                mgr = self._make_manager_with(node_specs)
                self.assertEqual(mgr.available_placement_count(NodeType.CITY), expected)

    def test_factory_available_placement_count(self):
        cases = [
            (
                "初期状態（街Lv0×1）→工場上限0",
                [(0, 0, NodeType.CITY, 0)],
                0,
            ),
            (
                "街がLv1に1回到達→工場上限1",
                [(0, 0, NodeType.CITY, 1)],
                1,
            ),
            (
                "街がLv1に2回到達（2都市）→工場上限2",
                [(0, 0, NodeType.CITY, 1), (1, 0, NodeType.CITY, 1)],
                2,
            ),
            (
                "街Lv1×1+Lv2×1→上限3・工場0個→配置可能数3",
                [(0, 0, NodeType.CITY, 1), (1, 0, NodeType.CITY, 2)],
                3,
            ),
            (
                "街Lv2×1（Lv1通過済み）→上限2・工場1個→配置可能数1",
                [(0, 0, NodeType.CITY, 2), (1, 0, NodeType.FACTORY, 0)],
                1,
            ),
            (
                "街Lv3×1（Lv1・Lv2通過済み）→上限2・工場0個→配置可能数2",
                [(0, 0, NodeType.CITY, 3)],
                2,
            ),
        ]
        for desc, node_specs, expected in cases:
            with self.subTest(desc):
                mgr = self._make_manager_with(node_specs)
                self.assertEqual(
                    mgr.available_placement_count(NodeType.FACTORY), expected
                )

    def test_unlimited_type_returns_none(self):
        mgr = self._make_manager_with([])
        self.assertIsNone(mgr.available_placement_count(NodeType.FOREST))


class TestNodeParamsRates(unittest.TestCase):
    def test_params_by_node_type(self):
        cases = [
            {
                "desc": "FOREST: 木を 3/sec 生産、生産蓄積上限 3",
                "node_type": NodeType.FOREST,
                "level": 0,
                "production_rates": {MaterialType.TREE: 3},
                "consumption_rates": {},
                "production_limits": {MaterialType.TREE: 3},
                "growth_limits": {},
            },
            {
                "desc": "MOUNTAIN: 石を 3/sec 生産、生産蓄積上限 3",
                "node_type": NodeType.MOUNTAIN,
                "level": 0,
                "production_rates": {MaterialType.STONE: 3},
                "consumption_rates": {},
                "production_limits": {MaterialType.STONE: 3},
                "growth_limits": {},
            },
            {
                "desc": "FACTORY lv0: 木→木材 3/sec, 生産蓄積上限 3, 成長 石 15",
                "node_type": NodeType.FACTORY,
                "level": 0,
                "production_rates": {MaterialType.WOOD: 3},
                "consumption_rates": {MaterialType.TREE: 3},
                "production_limits": {MaterialType.WOOD: 3},
                "growth_limits": {MaterialType.STONE: 15},
            },
            {
                "desc": "FACTORY lv1: 石→石材 3/sec, 生産蓄積上限 3, 成長 木材 15",
                "node_type": NodeType.FACTORY,
                "level": 1,
                "production_rates": {MaterialType.STONE_BLOCK: 3},
                "consumption_rates": {MaterialType.STONE: 3},
                "production_limits": {MaterialType.STONE_BLOCK: 3},
                "growth_limits": {MaterialType.WOOD: 15},
            },
            {
                "desc": "FACTORY lv2: 木材→加工材 3/sec, 生産蓄積上限 3, 成長なし",
                "node_type": NodeType.FACTORY,
                "level": 2,
                "production_rates": {MaterialType.PLYWOOD: 3},
                "consumption_rates": {MaterialType.WOOD: 3},
                "production_limits": {MaterialType.PLYWOOD: 3},
                "growth_limits": {},
            },
            {
                "desc": "CITY lv0: 木 15 で成長",
                "node_type": NodeType.CITY,
                "level": 0,
                "production_rates": {},
                "consumption_rates": {},
                "production_limits": {},
                "growth_limits": {MaterialType.TREE: 15},
            },
            {
                "desc": "CITY lv1: 木材 15 で成長",
                "node_type": NodeType.CITY,
                "level": 1,
                "production_rates": {},
                "consumption_rates": {},
                "production_limits": {},
                "growth_limits": {MaterialType.WOOD: 15},
            },
            {
                "desc": "CITY lv2: 石材 15 で成長",
                "node_type": NodeType.CITY,
                "level": 2,
                "production_rates": {},
                "consumption_rates": {},
                "production_limits": {},
                "growth_limits": {MaterialType.STONE_BLOCK: 15},
            },
            {
                "desc": "CITY lv3: 加工材 15 で成長",
                "node_type": NodeType.CITY,
                "level": 3,
                "production_rates": {},
                "consumption_rates": {},
                "production_limits": {},
                "growth_limits": {MaterialType.PLYWOOD: 15},
            },
            {
                "desc": "CITY lv4: 加工材 2/sec 消費・成長上限 15 の維持モード（生産なし）",
                "node_type": NodeType.CITY,
                "level": 4,
                "production_rates": {},
                "consumption_rates": {MaterialType.PLYWOOD: 2},
                "production_limits": {},
                "growth_limits": {MaterialType.PLYWOOD: 15},
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                params = NodeParams.get(case["node_type"], level=case["level"])
                self.assertEqual(params.production_rates, case["production_rates"])
                self.assertEqual(params.consumption_rates, case["consumption_rates"])
                self.assertEqual(params.production_limits, case["production_limits"])
                self.assertEqual(params.growth_limits, case["growth_limits"])
