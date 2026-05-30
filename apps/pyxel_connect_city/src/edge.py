from enum import Enum

from grid_path import GridPath


class EdgeDirect(Enum):
    FORWARD = "forward"
    BACKWARD = "backward"


class Edge:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.direct = None

    def set_direct(self, value):
        self.direct = value

    def to_dict(self):
        return {
            "start": list(self.start),
            "end": list(self.end),
            "direct": self.direct.value if self.direct is not None else None,
        }

    @classmethod
    def from_dict(cls, d):
        edge = cls(tuple(d["start"]), tuple(d["end"]))
        raw = d["direct"]
        edge.set_direct(EdgeDirect(raw) if raw is not None else None)
        return edge


class EdgeManager:
    def __init__(self):
        self._edges = []

    def endpoint_pairs(self) -> list:
        return [(edge.start, edge.end) for edge in self._edges]

    def iter_draw_data(self):
        for edge in self._edges:
            yield edge.start, edge.end, edge.direct

    def to_list(self):
        return [e.to_dict() for e in self._edges]

    @classmethod
    def from_list(cls, data):
        manager = cls()
        manager._edges = [Edge.from_dict(d) for d in data]
        return manager

    def occupied_grids(self) -> set:
        return {
            grid
            for edge in self._edges
            for grid in GridPath.route_grids(edge.start, edge.end)
        }

    def get_edge(self, start, end) -> "Edge | None":
        for edge in self._edges:
            if (edge.start == start and edge.end == end) or (
                edge.start == end and edge.end == start
            ):
                return edge
        return None

    def reset_directs(self) -> None:
        for edge in self._edges:
            edge.set_direct(None)

    def remove_edges_connected_to(self, col, row):
        pos = (col, row)
        self._edges = [e for e in self._edges if e.start != pos and e.end != pos]

    def remove_edge(self, start, end) -> bool:
        edge = self.get_edge(start, end)
        if edge is None:
            return False
        self._edges.remove(edge)
        return True

    def place_edge(self, start, end, node_positions=None) -> bool:
        if start == end:
            return False
        if node_positions:
            intermediate = set(GridPath.route_grids(start, end)[1:-1])
            blocking = {p for p in node_positions if p not in (start, end)}
            if intermediate & blocking:
                return False
        edge = Edge(start, end)
        self._edges.append(edge)
        return True
