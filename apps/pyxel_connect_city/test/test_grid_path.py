import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from grid_path import GridPath, GridDirect, SegmentPhase  # pylint: disable=C0413


class TestGridDirectOpposite(unittest.TestCase):
    def test_opposite(self):
        """各 GridDirect の opposite() が正反対の方向を返すこと"""
        pairs = [
            (GridDirect.L, GridDirect.R),
            (GridDirect.UL, GridDirect.DR),
            (GridDirect.UR, GridDirect.DL),
        ]
        for a, b in pairs:
            with self.subTest(direction=a):
                self.assertEqual(b, a.opposite())
                self.assertEqual(a, b.opposite())


class TestGridPathCubeToOffset(unittest.TestCase):
    def test_cube_to_offset(self):
        """cube_to_offset が offset_to_cube の逆変換になること"""
        cases = [
            # (col, row)
            (0, 0),
            (1, 0),
            (2, 0),
            (0, 1),
            (1, 1),
            (0, 2),
            (3, 2),
        ]
        for col, row in cases:
            with self.subTest(col=col, row=row):
                cube = GridPath.offset_to_cube(col, row)
                result = GridPath.cube_to_offset(cube)
                self.assertEqual((col, row), result)


class TestGridPathIterEdgeSegments(unittest.TestCase):
    def test_iter_edge_segments_yields_phase(self):
        """iter_edge_segments が (col, row, direct, phase) の4タプルを yield すること"""
        cases = [
            (
                (0, 0),
                (1, 0),
                [
                    (0, 0, GridDirect.R, SegmentPhase.OUT),
                    (1, 0, GridDirect.L, SegmentPhase.IN),
                ],
            ),
            (
                (0, 0),
                (2, 0),
                [
                    (0, 0, GridDirect.R, SegmentPhase.OUT),
                    (1, 0, GridDirect.L, SegmentPhase.IN),
                    (1, 0, GridDirect.R, SegmentPhase.OUT),
                    (2, 0, GridDirect.L, SegmentPhase.IN),
                ],
            ),
        ]
        for start, end, expected in cases:
            with self.subTest(start=start, end=end):
                segments = list(GridPath.iter_edge_segments(start, end))
                self.assertEqual(expected, segments)

    def test_segments_consistent_with_get_route(self):
        """iter_edge_segments の方向列が get_route の結果と一致すること"""
        start, end = (0, 0), (0, 1)
        route = GridPath.get_route(start, end)
        segments = list(GridPath.iter_edge_segments(start, end))
        # exit 方向（偶数インデックス）が route の各方向と一致する
        exit_directs = [segments[i * 2][2] for i in range(len(route))]
        self.assertEqual(route, exit_directs)


class TestGridMove(unittest.TestCase):
    def test_get_route(self):
        cases = [
            # (start_pos, end_pos, expected_list)
            # 1歩
            ((0, 0), (-1, 0), [GridDirect.L]),
            ((0, 0), (1, 0), [GridDirect.R]),
            ((0, 0), (-1, -1), [GridDirect.UL]),
            ((0, 0), (0, -1), [GridDirect.UR]),
            ((0, 0), (-1, 1), [GridDirect.DL]),
            ((0, 0), (0, 1), [GridDirect.DR]),
            ((0, 1), (-1, 1), [GridDirect.L]),
            ((0, 1), (1, 1), [GridDirect.R]),
            ((0, 1), (0, 0), [GridDirect.UL]),
            ((0, 1), (1, 0), [GridDirect.UR]),
            ((0, 1), (0, 2), [GridDirect.DL]),
            ((0, 1), (1, 2), [GridDirect.DR]),
            # 複数歩直進（端点はすべて範囲内）
            ((2, 0), (0, 0), [GridDirect.L, GridDirect.L]),
            ((0, 0), (2, 0), [GridDirect.R, GridDirect.R]),
            ((1, 2), (0, 0), [GridDirect.UL, GridDirect.UL]),
            ((0, 2), (1, 0), [GridDirect.UR, GridDirect.UR]),
            ((1, 0), (0, 2), [GridDirect.DL, GridDirect.DL]),
            ((0, 0), (1, 2), [GridDirect.DR, GridDirect.DR]),
            ((2, 1), (0, 1), [GridDirect.L, GridDirect.L]),
            ((0, 1), (2, 1), [GridDirect.R, GridDirect.R]),
            ((0, 1), (-1, -1), [GridDirect.UL, GridDirect.UL]),
            ((0, 1), (1, -1), [GridDirect.UR, GridDirect.UR]),
            ((0, 1), (-1, 3), [GridDirect.DL, GridDirect.DL]),
            ((0, 1), (1, 3), [GridDirect.DR, GridDirect.DR]),
        ]
        for start_pos, end_pos, expected_list in cases:
            with self.subTest(start_pos=start_pos, end_pos=end_pos):
                result = GridPath.get_route(start_pos, end_pos)
                self.assertEqual(expected_list, result)

    def test_route_grids_stays_within_bounds(self):
        """端列ルートが範囲外グリッドを通過しないこと"""
        cases = [
            # (start, end, out_of_bounds_grid)
            ((0, 2), (0, 4), (-1, 3)),  # 左端: col=-1 を通過しない
            ((6, 1), (6, 3), (7, 2)),  # 右端: col=7 を通過しない
        ]
        for start, end, forbidden in cases:
            with self.subTest(start=start, end=end):
                grids = GridPath.route_grids(start, end)
                self.assertEqual(start, grids[0])
                self.assertEqual(end, grids[-1])
                self.assertNotIn(forbidden, grids)


if __name__ == "__main__":
    unittest.main()
