from enum import Enum


class GridDirect(Enum):
    L = (-1, 1, 0)
    UL = (0, 1, -1)
    UR = (1, 0, -1)
    R = (1, -1, 0)
    DR = (0, -1, 1)
    DL = (-1, 0, 1)

    def opposite(self):
        q, r, s = self.value
        return GridDirect((-q, -r, -s))


class SegmentPhase(Enum):
    OUT = "out"
    IN = "in"


class GridPath:

    HEX_COLUMN_NUM = 7
    HEX_ROW_NUM = 12

    # --- 方向逆引き(O(1)) ---
    DIRECT_MAP = {d.value: d for d in GridDirect}

    @classmethod
    def offset_to_cube(cls, x, y):
        z = y
        x2 = x - (y - (y & 1)) // 2
        y2 = -x2 - z
        return (x2, y2, z)

    @classmethod
    def cube_distance(cls, a, b):
        return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) // 2

    # --- lerp系 ---
    @classmethod
    def lerp(cls, a, b, t):
        return a + (b - a) * t

    @classmethod
    def cube_lerp(cls, a, b, t):
        return (
            cls.lerp(a[0], b[0], t),
            cls.lerp(a[1], b[1], t),
            cls.lerp(a[2], b[2], t),
        )

    @classmethod
    def cube_round(cls, frac):
        rx = round(frac[0])
        ry = round(frac[1])
        rz = round(frac[2])

        dx = abs(rx - frac[0])
        dy = abs(ry - frac[1])
        dz = abs(rz - frac[2])

        # x + y + z = 0 を維持
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry

        return (rx, ry, rz)

    @classmethod
    def cube_line(cls, a, b):
        n = cls.cube_distance(a, b)
        results = []

        for i in range(n + 1):
            t = 0 if n == 0 else i / n
            lerped = cls.cube_lerp(a, b, t)
            rounded = cls.cube_round(lerped)
            results.append(rounded)

        return results

    # --- cube <-> offset 変換 ---
    @classmethod
    def cube_to_offset(cls, cube):
        z = cube[2]
        return cube[0] + (z - (z & 1)) // 2, z

    # --- 差分 → 方向 ---
    @classmethod
    def diff_to_direct(cls, diff):
        try:
            return cls.DIRECT_MAP[diff]
        except KeyError as exc:
            raise ValueError(f"invalid diff: {diff}") from exc

    # --- lerpベースの経路 ---
    @classmethod
    def route_grids(cls, start, end):
        """start から end までの経路グリッド座標を (col, row) のリストで返す（両端含む）。"""
        start_cube = cls.offset_to_cube(*start)
        end_cube = cls.offset_to_cube(*end)
        raw = [cls.cube_to_offset(c) for c in cls.cube_line(start_cube, end_cube)]
        if len(raw) <= 2:
            return raw
        clamped = [raw[0]]
        for col, row in raw[1:-1]:
            clamped.append(
                (
                    max(0, min(cls.HEX_COLUMN_NUM - 1, col)),
                    max(0, min(cls.HEX_ROW_NUM - 1, row)),
                )
            )
        clamped.append(raw[-1])
        deduped = [clamped[0]]
        for cell in clamped[1:]:
            if cell != deduped[-1]:
                deduped.append(cell)
        return deduped

    @classmethod
    def get_route(cls, start, end):
        grids = cls.route_grids(start, end)
        ret = []
        for i in range(1, len(grids)):
            prev_cube = cls.offset_to_cube(*grids[i - 1])
            curr_cube = cls.offset_to_cube(*grids[i])
            diff = (
                curr_cube[0] - prev_cube[0],
                curr_cube[1] - prev_cube[1],
                curr_cube[2] - prev_cube[2],
            )
            ret.append(cls.diff_to_direct(diff))
        return ret

    # --- エッジセグメント展開 ---
    @classmethod
    def iter_edge_segments(cls, start, end):
        """エッジ (start -> end) の各セグメントを (col, row, direct, phase) で yield する。
        各ステップで out (出発グリッドから外へ)、in (次グリッドの中心へ) の順。"""
        grids = cls.route_grids(start, end)
        for i in range(len(grids) - 1):
            curr, nxt = grids[i], grids[i + 1]
            curr_cube = cls.offset_to_cube(*curr)
            nxt_cube = cls.offset_to_cube(*nxt)
            diff = (
                nxt_cube[0] - curr_cube[0],
                nxt_cube[1] - curr_cube[1],
                nxt_cube[2] - curr_cube[2],
            )
            direct = cls.diff_to_direct(diff)
            yield (*curr, direct, SegmentPhase.OUT)
            yield (*nxt, direct.opposite(), SegmentPhase.IN)
