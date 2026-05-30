import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from edge import Edge, EdgeDirect, EdgeManager  # pylint: disable=C0413


class TestEdgeManager(unittest.TestCase):
    def test_initial_edges_is_empty(self):
        """EdgeManager() の初期状態でエッジがないこと"""
        manager = EdgeManager()
        self.assertEqual([], manager.endpoint_pairs())

    def test_place_edge_returns_true_and_adds_edge(self):
        """`place_edge((0, 0), (2, 0))` が True を返し、エッジが 1 つ追加されること"""
        manager = EdgeManager()
        result = manager.place_edge((0, 0), (2, 0))
        self.assertTrue(result)
        pairs = manager.endpoint_pairs()
        self.assertEqual(1, len(pairs))
        start, end = pairs[0]
        self.assertEqual((0, 0), start)
        self.assertEqual((2, 0), end)

    def test_place_edge_initializes_direct_as_none(self):
        """place_edge が作成するエッジは initial direct=None であること"""
        cases = [(0, 0), (0, 1), (0, 2), (0, 3)]
        for start in cases:
            with self.subTest(start=start):
                manager = EdgeManager()
                col, row = start
                manager.place_edge(start, (col + 2, row))
                draw_data = list(manager.iter_draw_data())
                self.assertIsNone(draw_data[-1][2])

    def test_get_edge_returns_matching_edge(self):
        """get_edge が start/end に一致する Edge を順序非依存で返すこと"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (2, 0))
        edge = manager.get_edge((0, 0), (2, 0))
        self.assertIsNotNone(edge)
        self.assertEqual((0, 0), edge.start)
        self.assertEqual((2, 0), edge.end)
        self.assertIs(edge, manager.get_edge((2, 0), (0, 0)))

    def test_get_edge_returns_none_when_no_match(self):
        """一致するエッジがない場合は None を返すこと"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (2, 0))
        result = manager.get_edge((5, 5), (7, 5))
        self.assertIsNone(result)

    def test_reset_directs_sets_all_to_none(self):
        """reset_directs() が全エッジを direct=None にすること"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (2, 0))
        manager.place_edge((1, 1), (3, 1))
        edge1 = manager.get_edge((0, 0), (2, 0))
        edge2 = manager.get_edge((1, 1), (3, 1))
        edge1.set_direct(EdgeDirect.FORWARD)
        edge2.set_direct(EdgeDirect.FORWARD)
        manager.reset_directs()
        for _, _, direct in manager.iter_draw_data():
            self.assertIsNone(direct)

    def test_place_edge_placement_cases(self):
        """place_edge の配置可否ケースをまとめて検証する"""
        cases = [
            {
                "desc": "同一ノード: False、エッジ変化なし",
                "start": (0, 0),
                "end": (0, 0),
                "node_positions": None,
                "expected_result": False,
                "expected_edge_count": 0,
            },
            {
                "desc": "中間ノードあり: False、エッジ変化なし",
                "start": (0, 0),
                "end": (2, 0),
                "node_positions": [(0, 0), (1, 0), (2, 0)],
                "expected_result": False,
                "expected_edge_count": 0,
            },
            {
                "desc": "端点ノードのみ（中間ノードなし）: True、エッジに追加",
                "start": (0, 0),
                "end": (2, 0),
                "node_positions": [(0, 0), (2, 0)],
                "expected_result": True,
                "expected_edge_count": 1,
            },
            {
                "desc": "経路外ノードのみ: True、エッジに追加",
                "start": (0, 0),
                "end": (2, 0),
                "node_positions": [(0, 0), (2, 0), (5, 5)],
                "expected_result": True,
                "expected_edge_count": 1,
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = EdgeManager()
                kwargs = {}
                if case["node_positions"] is not None:
                    kwargs["node_positions"] = case["node_positions"]
                result = manager.place_edge(case["start"], case["end"], **kwargs)
                self.assertEqual(case["expected_result"], result)
                self.assertEqual(
                    case["expected_edge_count"], len(manager.endpoint_pairs())
                )


class TestEdge(unittest.TestCase):
    def test_to_dict_contains_all_fields(self):
        cases = [
            (EdgeDirect.FORWARD, {"start": [2, 3], "end": [5, 1], "direct": "forward"}),
            (
                EdgeDirect.BACKWARD,
                {"start": [2, 3], "end": [5, 1], "direct": "backward"},
            ),
            (None, {"start": [2, 3], "end": [5, 1], "direct": None}),
        ]
        for direct_val, expected in cases:
            with self.subTest(direct=direct_val):
                edge = Edge((2, 3), (5, 1))
                edge.set_direct(direct_val)
                self.assertEqual(expected, edge.to_dict())

    def test_from_dict_restores_start_end_and_direct(self):
        cases = [
            ({"start": [2, 3], "end": [5, 1], "direct": None}, (2, 3), (5, 1), None),
            (
                {"start": [0, 0], "end": [2, 0], "direct": "backward"},
                (0, 0),
                (2, 0),
                EdgeDirect.BACKWARD,
            ),
        ]
        for d, exp_start, exp_end, exp_direct in cases:
            with self.subTest(d=d):
                restored = Edge.from_dict(d)
                self.assertEqual(exp_start, restored.start)
                self.assertEqual(exp_end, restored.end)
                self.assertEqual(exp_direct, restored.direct)

    def test_to_dict_from_dict_roundtrip(self):
        """to_dict → from_dict の往復で start/end/direct が保たれること"""
        edge = Edge((0, 0), (4, 2))
        edge.set_direct(EdgeDirect.FORWARD)
        restored = Edge.from_dict(edge.to_dict())
        self.assertEqual(edge.start, restored.start)
        self.assertEqual(edge.end, restored.end)
        self.assertEqual(EdgeDirect.FORWARD, restored.direct)

    def test_set_direct_accepts_forward_backward_none(self):
        cases = [
            (EdgeDirect.FORWARD, EdgeDirect.FORWARD),
            (EdgeDirect.BACKWARD, EdgeDirect.BACKWARD),
            (None, None),
        ]
        for direct_val, expected in cases:
            with self.subTest(direct=direct_val):
                edge = Edge((0, 0), (2, 0))
                edge.set_direct(direct_val)
                self.assertEqual(expected, edge.direct)


class TestEdgeManagerSerialize(unittest.TestCase):
    def test_to_list_returns_list_of_dicts(self):
        """EdgeManager.to_list() が複数エッジの辞書リストを返すこと"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (2, 0))
        manager.place_edge((1, 1), (3, 1))
        result = manager.to_list()
        self.assertEqual(2, len(result))
        self.assertEqual({"start": [0, 0], "end": [2, 0], "direct": None}, result[0])
        self.assertEqual({"start": [1, 1], "end": [3, 1], "direct": None}, result[1])

    def test_from_list_restores_edges(self):
        """EdgeManager.from_list() がリストから EdgeManager を復元できること"""
        data = [
            {"start": [0, 0], "end": [2, 0], "direct": None},
            {"start": [1, 1], "end": [3, 1], "direct": None},
        ]
        restored = EdgeManager.from_list(data)
        pairs = restored.endpoint_pairs()
        self.assertEqual(2, len(pairs))
        self.assertEqual((0, 0), pairs[0][0])
        self.assertEqual((2, 0), pairs[0][1])
        self.assertEqual((1, 1), pairs[1][0])
        self.assertEqual((3, 1), pairs[1][1])

    def test_to_list_from_list_roundtrip_preserves_equality(self):
        """to_list → from_list の往復で同値性が保たれること"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (3, 0))
        manager.place_edge((0, 0), (0, 2))
        restored = EdgeManager.from_list(manager.to_list())
        self.assertEqual(manager.endpoint_pairs(), restored.endpoint_pairs())

    def test_from_list_empty_returns_empty_manager(self):
        """空リストから復元するとエッジなしの EdgeManager が得られること"""
        manager = EdgeManager.from_list([])
        self.assertEqual([], manager.endpoint_pairs())


class TestEdgeManagerRemoveConnected(unittest.TestCase):
    def test_removes_edges_connected_to_node(self):
        """指定ノードに接続するエッジが削除されること（start/end・複数接続）"""
        cases = [
            {
                "desc": "start が指定座標のエッジが削除される",
                "setup_edges": [((1, 0), (3, 0)), ((0, 0), (2, 0))],
                "col": 1,
                "row": 0,
                "expected_remaining": [((0, 0), (2, 0))],
            },
            {
                "desc": "end が指定座標のエッジが削除される",
                "setup_edges": [((0, 0), (2, 0)), ((0, 0), (4, 0))],
                "col": 2,
                "row": 0,
                "expected_remaining": [((0, 0), (4, 0))],
            },
            {
                "desc": "複数エッジが全て削除される",
                "setup_edges": [((0, 0), (2, 0)), ((2, 0), (4, 0)), ((0, 2), (4, 2))],
                "col": 2,
                "row": 0,
                "expected_remaining": [((0, 2), (4, 2))],
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = EdgeManager()
                for start, end in case["setup_edges"]:
                    manager.place_edge(start, end)
                manager.remove_edges_connected_to(case["col"], case["row"])
                self.assertEqual(case["expected_remaining"], manager.endpoint_pairs())

    def test_no_edges_removed_when_no_match(self):
        """指定ノードに接続するエッジがない場合、エッジが変化しないこと"""
        manager = EdgeManager()
        manager.place_edge((0, 0), (2, 0))
        manager.remove_edges_connected_to(5, 5)
        self.assertEqual(1, len(manager.endpoint_pairs()))


class TestEdgeManagerRemoveEdge(unittest.TestCase):

    def test_remove_edge(self):
        """remove_edge の各ケースを検証する"""
        cases = [
            {
                "desc": "指定したエッジが削除されること",
                "setup_edges": [((0, 0), (2, 0)), ((1, 1), (3, 1))],
                "remove": ((0, 0), (2, 0)),
                "expected_return": True,
                "expected_pairs": [((1, 1), (3, 1))],
            },
            {
                "desc": "start/end の順序を逆にしても削除できること",
                "setup_edges": [((0, 0), (2, 0))],
                "remove": ((2, 0), (0, 0)),
                "expected_return": True,
                "expected_pairs": [],
            },
            {
                "desc": "存在しないエッジを指定しても他のエッジが残ること",
                "setup_edges": [((0, 0), (2, 0))],
                "remove": ((5, 5), (7, 5)),
                "expected_return": False,
                "expected_pairs": [((0, 0), (2, 0))],
            },
            {
                "desc": "複数エッジがある場合、指定したエッジのみ削除されること",
                "setup_edges": [((0, 0), (2, 0)), ((0, 0), (1, 1)), ((2, 0), (3, 1))],
                "remove": ((0, 0), (2, 0)),
                "expected_return": True,
                "expected_pairs": [((0, 0), (1, 1)), ((2, 0), (3, 1))],
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                manager = EdgeManager()
                for start, end in case["setup_edges"]:
                    manager.place_edge(start, end)
                result = manager.remove_edge(*case["remove"])
                self.assertEqual(case["expected_return"], result)
                self.assertEqual(case["expected_pairs"], manager.endpoint_pairs())
