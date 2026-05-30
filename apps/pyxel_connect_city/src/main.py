# title: pyxel connect city
# author: masatobu

import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from report_store import ReportStore
from node import NodeType, NodeManager, MaterialType, NodeParams
from button import Button
from edge import EdgeDirect, EdgeManager
from grid_path import GridPath, GridDirect, SegmentPhase
from material_flow import MaterialFlow

_TILE_W = 32
_TILE_H = 31
_ROW_Y_STEP = 24
_ODD_ROW_X_OFFSET = 16


class Clock:
    def __init__(self, count_ms):
        self._count_ms = count_ms
        self._bef = time.perf_counter()

    def is_up(self) -> bool:
        if self._count_ms == 0:
            return False
        now = time.perf_counter()
        if (now - self._bef) * 1000 >= self._count_ms:
            self._bef = now
            return True
        return False


class GridType(Enum):
    NORMAL = auto()
    HIGHLIGHTED = auto()
    SELECTED = auto()
    FAIL_HIGHLIGHTED = auto()
    SHORE = auto()
    SEA = auto()


class EdgeFlow(Enum):
    OUTWARD = auto()
    INWARD = auto()


class PlacementMode(Enum):
    NO_MODE = auto()
    CITY = auto()
    FACTORY = auto()
    EDGE = auto()
    DELETE_NODE = auto()
    DELETE_EDGE = auto()


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_image(self, x, y, img, u, v, w, h, colkey):
        pass

    @abstractmethod
    def get_frame(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def draw_rect(self, x, y, w, h, col):
        self.pyxel.rect(x, y, w, h, col)

    def draw_rectb(self, x, y, w, h, col):
        self.pyxel.rectb(x, y, w, h, col)

    def draw_image(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def get_frame(self) -> int:
        return self.pyxel.frame_count


class IInput(ABC):
    @abstractmethod
    def is_mouse_btn_pressed(self) -> bool:
        pass

    @property
    @abstractmethod
    def mouse_x(self) -> int:
        pass

    @property
    @abstractmethod
    def mouse_y(self) -> int:
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=C0415

        self.pyxel = pyxel

    def is_mouse_btn_pressed(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    @property
    def mouse_x(self) -> int:
        return self.pyxel.mouse_x

    @property
    def mouse_y(self) -> int:
        return self.pyxel.mouse_y


class IGridInput(ABC):
    @abstractmethod
    def get_clicked_grid(self):
        """クリックされていれば (col, row) を、されていなければ None を返す"""

    @classmethod
    def create(cls):
        return cls()


class PyxelGridInput(IGridInput):
    _PIXEL_TO_GRID_Y_OFFSET = 4

    def __init__(self):
        self._input = PyxelInput.create()

    def get_clicked_grid(self):
        if not self._input.is_mouse_btn_pressed():
            return None
        col, row = self._pixel_to_grid(self._input.mouse_x, self._input.mouse_y)
        if not self._is_valid_grid(col, row):
            return None
        return col, row

    @staticmethod
    def _is_valid_grid(col: int, row: int) -> bool:
        return (
            0 <= col < NodeManager.HEX_COLUMN_NUM and 0 <= row < NodeManager.HEX_ROW_NUM
        )

    @staticmethod
    def _pixel_to_grid(px: int, py: int) -> tuple:
        row = (py - PyxelGridInput._PIXEL_TO_GRID_Y_OFFSET) // _ROW_Y_STEP
        x_offset = _ODD_ROW_X_OFFSET if row % 2 == 1 else 0
        col = (px - x_offset) // _TILE_W
        return col, row


class IHexGridView(ABC):
    @abstractmethod
    def draw_grid(self, col, row, grid_type=GridType.NORMAL):
        pass

    @abstractmethod
    def draw_node(self, col, row, node_type, level=0):
        pass

    @abstractmethod
    def draw_edge(self, col, row, direct, flow):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelHexGridView(IHexGridView):
    TILE_UV = {
        GridType.NORMAL: (8, 0),
        GridType.HIGHLIGHTED: (40, 0),
        GridType.SELECTED: (72, 0),
        GridType.FAIL_HIGHLIGHTED: (104, 0),
        GridType.SHORE: (136, 0),
        GridType.SEA: (168, 0),
    }
    NODE_W = 16
    NODE_H = 16
    NODE_V = {
        NodeType.CITY: 0,
        NodeType.FACTORY: 16,
        NodeType.FOREST: 32,
        NodeType.MOUNTAIN: 48,
    }
    LEVEL_U = {0: 8, 1: 24, 2: 40, 3: 56, 4: 72}
    EDGE_U = {
        GridDirect.UL: 8,
        GridDirect.UR: 40,
        GridDirect.R: 72,
        GridDirect.DR: 104,
        GridDirect.DL: 136,
        GridDirect.L: 168,
    }
    EDGE_V_STATIC = 32
    EDGE_V_ANIM = [64, 96, 128, 160]
    ANIM_INTERVAL = 8

    def __init__(self):
        self.view = self._create_view()

    def _create_view(self):
        return PyxelView.create()

    def _tile_px_py(self, col, row):
        x_offset = _ODD_ROW_X_OFFSET if row % 2 == 1 else 0
        return col * _TILE_W + x_offset, row * _ROW_Y_STEP

    def draw_grid(self, col, row, grid_type=GridType.NORMAL):
        px, py = self._tile_px_py(col, row)
        u, v = self.TILE_UV[grid_type]
        self.view.draw_blt(px, py, 0, u, v, _TILE_W, _TILE_H, 0)

    def draw_node(self, col, row, node_type, level=0):
        x_offset = _ODD_ROW_X_OFFSET if row % 2 == 1 else 0
        px = col * _TILE_W + x_offset + (_TILE_W - self.NODE_W) // 2
        py = row * _ROW_Y_STEP + (_TILE_H - self.NODE_H) // 2 + 2
        v = self.NODE_V[node_type]
        u = self.LEVEL_U[level]
        self.view.draw_blt(px, py, 1, u, v, self.NODE_W, self.NODE_H, 0)

    def draw_edge(self, col, row, direct, flow):
        px, py = self._tile_px_py(col, row)
        u = self.EDGE_U[direct]
        if flow is None:
            v = self.EDGE_V_STATIC
        else:
            anim_index = (self.view.get_frame() // self.ANIM_INTERVAL) % 4
            if flow == EdgeFlow.INWARD:
                anim_index = 3 - anim_index
            v = self.EDGE_V_ANIM[anim_index]
        self.view.draw_blt(px, py, 0, u, v, _TILE_W, _TILE_H, 0)


class GridSelectionState:
    def __init__(self):
        self._tapped_grid = None
        self._selected_grid = None
        # True after rule-1 unconfirm; distinguishes rule-2 (full clear) from rule-4 (confirm)
        self._tap_reverted = False
        self._edge_first_node = None
        self._selected_edge = None

    @property
    def tapped_grid(self):
        return self._tapped_grid

    @property
    def selected_grid(self):
        return self._selected_grid

    @property
    def selected_edge(self):
        return self._selected_edge

    def on_tap(self, col, row, active_mode):
        pos = (col, row)
        _is_edge_mode = active_mode in (PlacementMode.EDGE, PlacementMode.DELETE_EDGE)
        if pos == self._selected_grid:  # rule 1: unconfirm
            self._selected_grid = None
            self._tapped_grid = pos
            self._tap_reverted = True
            return
        if pos == self._tapped_grid and self._tap_reverted:  # rule 2: full clear
            self._tapped_grid = None
            self._tap_reverted = False
            if _is_edge_mode:
                self._edge_first_node = None
            return
        if (
            pos == self._tapped_grid and self._selected_grid is not None
        ):  # rule 3: pair decide
            if _is_edge_mode and self._edge_first_node is not None:
                if pos != self._edge_first_node:
                    self._selected_edge = (self._edge_first_node, pos)
                self._edge_first_node = None
            self._tapped_grid = None
            self._selected_grid = None
            return
        if pos == self._tapped_grid:  # rule 4: confirm
            self._selected_grid = pos
            self._tapped_grid = None
            if _is_edge_mode and self._edge_first_node is None:
                self._edge_first_node = pos
                self._selected_edge = None
            elif active_mode is None:
                self.reset()
            return
        self._tapped_grid = pos  # rule 5: move tap
        self._tap_reverted = False

    def reset(self):
        self._tapped_grid = None
        self._selected_grid = None
        self._tap_reverted = False
        self._edge_first_node = None
        self._selected_edge = None


class GameCore:
    POPUP_X = 40
    POPUP_Y = 80
    POPUP_W = 160
    POPUP_H = 160
    POPUP_BG_COL = 1
    POPUP_BORDER_COL = 7
    POPUP_PADDING = 4

    CLEAR_POPUP_W = 80
    CLEAR_POPUP_H = 80
    CLEAR_POPUP_X = 80  # (240 - CLEAR_POPUP_W) // 2
    CLEAR_POPUP_Y = 120  # (320 - CLEAR_POPUP_H) // 2

    MATERIAL_UV = {
        MaterialType.TREE: (8, 0),
        MaterialType.STONE: (16, 0),
        MaterialType.WOOD: (24, 0),
        MaterialType.PLYWOOD: (32, 0),
        MaterialType.STONE_BLOCK: (40, 0),
    }
    MATERIAL_ICON_W = 8
    MATERIAL_ICON_H = 8
    MATERIAL_ICON_LAYER = 2
    LINE_H = 10

    CHAR_W = 4

    POPUP_HEADER_H = 20
    POPUP_HEADER_DIVIDER_Y = POPUP_Y + POPUP_PADDING + POPUP_HEADER_H
    POPUP_SECTION1_Y = POPUP_HEADER_DIVIDER_Y + POPUP_PADDING
    POPUP_SECTION1_CONSUMPTION_X = POPUP_X + POPUP_PADDING
    POPUP_SECTION1_ARROW_X = POPUP_X + POPUP_W // 2 - 4
    POPUP_SECTION1_PRODUCTION_X = POPUP_X + POPUP_W // 2 + 8
    POPUP_DIVIDER_Y = (POPUP_HEADER_DIVIDER_Y + POPUP_Y + POPUP_H) // 2
    POPUP_SECTION_H = POPUP_DIVIDER_Y - POPUP_HEADER_DIVIDER_Y
    POPUP_SECTION2_Y = POPUP_DIVIDER_Y + POPUP_PADDING
    POPUP_SECTION2_X = POPUP_X + POPUP_PADDING
    POPUP_SECTION2_TEXT_RIGHT_X = POPUP_X + POPUP_W - POPUP_PADDING
    POPUP_SECTION2_SLASH_X = (
        POPUP_SECTION2_X + MATERIAL_ICON_W + POPUP_SECTION2_TEXT_RIGHT_X
    ) // 2

    TICK_INTERVAL_MS = 1000
    SAVE_INTERVAL_MS = 10000

    def __init__(self, load_data=True):
        self._view = PyxelView.create()
        self._hex_grid_view = PyxelHexGridView.create()
        self._input = PyxelInput.create()
        self._grid_input = PyxelGridInput.create()
        self._report_store = ReportStore()
        self._apply_load_data(self._report_store.load() if load_data else None)
        self._report_store.save(self._get_save_data())
        self._grid_selection = GridSelectionState()
        node_v = PyxelHexGridView.NODE_V
        level0_u = PyxelHexGridView.LEVEL_U[0]
        # ボタン配置: ノード群 x=4,32,60 ─ エッジ群 x=96,124（グループ間 12px 追加）
        self._buttons = {
            PlacementMode.CITY: Button(
                4, 292, 24, 24, (level0_u, node_v[NodeType.CITY])
            ),
            PlacementMode.FACTORY: Button(
                32, 292, 24, 24, (level0_u, node_v[NodeType.FACTORY])
            ),
            PlacementMode.DELETE_NODE: Button(60, 292, 24, 24, (8, 80)),
            PlacementMode.EDGE: Button(96, 292, 24, 24, (8, 64)),
            PlacementMode.DELETE_EDGE: Button(124, 292, 24, 24, (24, 80)),
        }
        self._popup_node = None
        self._clear_popup_shown = False
        self._needs_reset = False
        self._tick_clock = Clock(self.TICK_INTERVAL_MS)
        self._save_clock = Clock(self.SAVE_INTERVAL_MS)
        self._material_flow = MaterialFlow()

    @property
    def needs_reset(self):
        return self._needs_reset

    def _get_save_data(self):
        return {
            "nodes": self._node_manager.to_list(),
            "edges": self._edge_manager.to_list(),
        }

    def _apply_load_data(self, data):
        if data is None:
            self._node_manager = NodeManager()
            self._edge_manager = EdgeManager()
        else:
            self._node_manager = NodeManager.from_list(data["nodes"])
            self._edge_manager = EdgeManager.from_list(data.get("edges", []))

    def _click_button(self, px, py) -> bool:
        clicked_mode = next(
            (mode for mode, btn in self._buttons.items() if btn.is_clicked(px, py)),
            None,
        )
        if clicked_mode is None:
            return False
        if clicked_mode in (PlacementMode.CITY, PlacementMode.FACTORY):
            node_type = NodeType[clicked_mode.name]
            if self._node_manager.available_placement_count(node_type) == 0:
                return True
        clicked = self._buttons[clicked_mode]
        if clicked.is_active:
            clicked.set_active(False)
        else:
            for btn in self._buttons.values():
                btn.set_active(False)
            clicked.set_active(True)
        self._grid_selection.reset()
        return True

    def _get_selected_edge_if_valid(self):
        """確定済みの selected_edge を返す。未確定・ノード不在なら None を返す（不在時は reset も実行）。"""
        selected_edge = self._grid_selection.selected_edge
        selected_node = self._grid_selection.selected_grid
        if selected_node is None and selected_edge is None:
            return None
        check_node = selected_node if selected_node is not None else selected_edge[1]
        if not self._node_manager.has_node(*check_node):
            self._grid_selection.reset()
            return None
        if selected_edge is None:
            return None
        return selected_edge

    def update(self):
        if self._clear_popup_shown:
            if (
                self._input.is_mouse_btn_pressed()
                and self.CLEAR_POPUP_X
                <= self._input.mouse_x
                < self.CLEAR_POPUP_X + self.CLEAR_POPUP_W
                and self.CLEAR_POPUP_Y
                <= self._input.mouse_y
                < self.CLEAR_POPUP_Y + self.CLEAR_POPUP_H
            ):
                self._needs_reset = True
            return
        if self._tick_clock.is_up():
            self._material_flow.process(self._node_manager, self._edge_manager)
            if self._node_manager.is_game_clear():
                self._clear_popup_shown = True
        if self._save_clock.is_up():
            self._report_store.save(self._get_save_data())
        if self._input.is_mouse_btn_pressed():
            if self._popup_node is not None:
                self._popup_node = None
                return
            if self._click_button(self._input.mouse_x, self._input.mouse_y):
                return
        result = self._grid_input.get_clicked_grid()
        if result is None:
            return
        col, row = result
        active_mode = next(
            (mode for mode, btn in self._buttons.items() if btn.is_active), None
        )
        prev_tapped = self._grid_selection.tapped_grid
        self._grid_selection.on_tap(col, row, active_mode)
        if active_mode is None and prev_tapped == (col, row):
            self._popup_node = self._node_manager.get_node(col, row)
        if active_mode == PlacementMode.EDGE:
            selected_edge = self._get_selected_edge_if_valid()
            if selected_edge is None:
                return
            if not self._node_manager.is_connectable_edge(*selected_edge):
                self._grid_selection.reset()
                return
            placed = self._edge_manager.place_edge(
                *selected_edge,
                node_positions=self._node_manager.positions(),
            )
            self._grid_selection.reset()
            if placed:
                self._buttons[PlacementMode.EDGE].set_active(False)
                self._report_store.save(self._get_save_data())
        elif active_mode == PlacementMode.DELETE_NODE:
            selected = self._grid_selection.selected_grid
            if selected is None:
                return
            col, row = selected
            removed = self._node_manager.remove_node(col, row)
            self._grid_selection.reset()
            if removed:
                self._edge_manager.remove_edges_connected_to(col, row)
                self._buttons[PlacementMode.DELETE_NODE].set_active(False)
                self._report_store.save(self._get_save_data())
        elif active_mode == PlacementMode.DELETE_EDGE:
            selected_edge = self._get_selected_edge_if_valid()
            if selected_edge is None:
                return
            removed = self._edge_manager.remove_edge(*selected_edge)
            self._grid_selection.reset()
            if removed:
                self._buttons[PlacementMode.DELETE_EDGE].set_active(False)
                self._report_store.save(self._get_save_data())
        elif active_mode is not None:
            selected = self._grid_selection.selected_grid
            if selected is None:
                return
            col, row = selected
            placed = self._node_manager.place_node(
                col=col,
                row=row,
                node_type=NodeType[active_mode.name],
                blocked_grids=self._edge_manager.occupied_grids(),
            )
            self._grid_selection.reset()
            if placed:
                self._buttons[active_mode].set_active(False)
                self._report_store.save(self._get_save_data())

    def _draw_edge_segments(self, start, end, edge_direct):
        for col, row, direct, phase in GridPath.iter_edge_segments(start, end):
            flow = self._segment_flow(edge_direct, phase)
            self._hex_grid_view.draw_edge(col, row, direct, flow)

    _SEGMENT_FLOW_TABLE = {
        (EdgeDirect.FORWARD, SegmentPhase.OUT): EdgeFlow.OUTWARD,
        (EdgeDirect.FORWARD, SegmentPhase.IN): EdgeFlow.INWARD,
        (EdgeDirect.BACKWARD, SegmentPhase.OUT): EdgeFlow.INWARD,
        (EdgeDirect.BACKWARD, SegmentPhase.IN): EdgeFlow.OUTWARD,
    }

    @staticmethod
    def _segment_flow(edge_direct, phase):
        if edge_direct is None:
            return None
        return GameCore._SEGMENT_FLOW_TABLE[(edge_direct, phase)]

    def _tapped_highlight_type(self, tapped, selected, active_mode):
        if active_mode == PlacementMode.EDGE:
            if not self._node_manager.has_node(*tapped):
                return GridType.FAIL_HIGHLIGHTED
            if selected is not None:
                for col, row in GridPath.route_grids(selected, tapped)[1:-1]:
                    if self._node_manager.has_node(col, row):
                        return GridType.FAIL_HIGHLIGHTED
                if not self._node_manager.is_connectable_edge(selected, tapped):
                    return GridType.FAIL_HIGHLIGHTED
        elif active_mode == PlacementMode.DELETE_EDGE:
            if not self._node_manager.has_node(*tapped):
                return GridType.FAIL_HIGHLIGHTED
            if selected is not None:
                if self._edge_manager.get_edge(selected, tapped) is None:
                    return GridType.FAIL_HIGHLIGHTED
        elif active_mode in (PlacementMode.CITY, PlacementMode.FACTORY):
            if self._node_manager.has_node(*tapped):
                return GridType.FAIL_HIGHLIGHTED
            if tapped in self._edge_manager.occupied_grids():
                return GridType.FAIL_HIGHLIGHTED
        elif active_mode == PlacementMode.DELETE_NODE:
            if not self._node_manager.is_deletable_node(*tapped):
                return GridType.FAIL_HIGHLIGHTED
        return GridType.HIGHLIGHTED

    @staticmethod
    def _row_grid_type(row):
        if row == NodeManager.HEX_ROW_NUM:
            return GridType.SHORE
        if row > NodeManager.HEX_ROW_NUM:
            return GridType.SEA
        return GridType.NORMAL

    def draw(self):
        for row in range(-1, NodeManager.HEX_ROW_NUM + 2):
            for col in range(-1, NodeManager.HEX_COLUMN_NUM + 1):
                self._hex_grid_view.draw_grid(
                    col, row, grid_type=self._row_grid_type(row)
                )
        selected = self._grid_selection.selected_grid
        if selected is not None:
            self._hex_grid_view.draw_grid(*selected, grid_type=GridType.SELECTED)
        tapped = self._grid_selection.tapped_grid
        tapped_hl_type = None
        tapped_grids = []
        if tapped is not None:
            active_mode = next(
                (mode for mode, btn in self._buttons.items() if btn.is_active), None
            )
            tapped_hl_type = self._tapped_highlight_type(tapped, selected, active_mode)
            if (
                active_mode in (PlacementMode.EDGE, PlacementMode.DELETE_EDGE)
                and selected is not None
            ):
                tapped_grids = list(GridPath.route_grids(selected, tapped)[1:])
            else:
                tapped_grids = [tapped]
            for col, row in tapped_grids:
                self._hex_grid_view.draw_grid(col, row, grid_type=tapped_hl_type)
        for start, end, direct in self._edge_manager.iter_draw_data():
            self._draw_edge_segments(start, end, direct)
        for col, row in self._node_manager.positions():
            node = self._node_manager.get_node(col, row)
            self._hex_grid_view.draw_node(
                node.col, node.row, node.node_type, node.level
            )
        placement_counts = {
            PlacementMode.CITY: self._node_manager.available_placement_count(
                NodeType.CITY
            ),
            PlacementMode.FACTORY: self._node_manager.available_placement_count(
                NodeType.FACTORY
            ),
        }
        for mode, button in self._buttons.items():
            button.draw(self._view, count=placement_counts.get(mode))
        if self._clear_popup_shown:
            self._draw_clear_popup()
        elif self._popup_node is not None:
            self._draw_popup(self._popup_node)

    def _draw_popup_frame(self):
        self._view.draw_rect(
            self.POPUP_X, self.POPUP_Y, self.POPUP_W, self.POPUP_H, self.POPUP_BG_COL
        )
        self._view.draw_rectb(
            self.POPUP_X,
            self.POPUP_Y,
            self.POPUP_W,
            self.POPUP_H,
            self.POPUP_BORDER_COL,
        )

    def _draw_clear_popup(self):
        cx = self.CLEAR_POPUP_X
        cy = self.CLEAR_POPUP_Y
        cw = self.CLEAR_POPUP_W
        ch = self.CLEAR_POPUP_H
        self._view.draw_rect(cx, cy, cw, ch, self.POPUP_BG_COL)
        self._view.draw_rectb(cx, cy, cw, ch, self.POPUP_BORDER_COL)
        text1 = "CLEAR"
        tx1 = cx + (cw - len(text1) * self.CHAR_W) // 2
        ty1 = cy + ch // 2 - 9
        self._view.draw_text(tx1, ty1, text1)
        text2 = "click to restart"
        tx2 = cx + (cw - len(text2) * self.CHAR_W) // 2
        ty2 = cy + ch // 2 + 4
        self._view.draw_text(tx2, ty2, text2)

    def _draw_material_with_value(self, x, y, material, value_text):
        u, v = self.MATERIAL_UV[material]
        self._view.draw_blt(
            x,
            y,
            self.MATERIAL_ICON_LAYER,
            u,
            v,
            self.MATERIAL_ICON_W,
            self.MATERIAL_ICON_H,
            0,
        )
        self._view.draw_text(x + 10, y, value_text)

    def _draw_divider(self, y):
        self._view.draw_rect(
            self.POPUP_X + self.POPUP_PADDING,
            y,
            self.POPUP_W - 2 * self.POPUP_PADDING,
            1,
            self.POPUP_BORDER_COL,
        )

    def _draw_popup(self, node):
        self._draw_popup_frame()
        cx = self.POPUP_X + self.POPUP_PADDING
        cy = self.POPUP_Y + self.POPUP_PADDING
        v = PyxelHexGridView.NODE_V[node.node_type]
        self._view.draw_blt(
            cx, cy, 1, PyxelHexGridView.LEVEL_U[node.level], v, 16, 16, 0
        )
        self._view.draw_text(cx + 20, cy + 4, f"{node.node_type.value} Lv.{node.level}")
        self._draw_divider(self.POPUP_HEADER_DIVIDER_Y)
        self._draw_popup_section1(node)
        self._draw_divider(self.POPUP_DIVIDER_Y)
        self._draw_popup_section2(node)

    def _draw_popup_section1(self, node):
        params = NodeParams.get(node.node_type, node.level)
        y = self.POPUP_SECTION1_Y
        for material, rate in params.consumption_rates.items():
            self._draw_material_with_value(
                self.POPUP_SECTION1_CONSUMPTION_X, y, material, f"{rate}/s"
            )
        if params.consumption_rates or params.production_rates:
            self._view.draw_text(self.POPUP_SECTION1_ARROW_X, y, "->")
        for material, rate in params.production_rates.items():
            self._draw_material_with_value(
                self.POPUP_SECTION1_PRODUCTION_X, y, material, f"{rate}/s"
            )

    def _draw_popup_section2(self, node):
        params = NodeParams.get(node.node_type, node.level)
        for i, material in enumerate(params.growth_stock_cols):
            current = node.get_growth_stock(material)
            limit = params.growth_limits.get(material, 0)
            y = self.POPUP_SECTION2_Y + i * self.LINE_H
            u, v = self.MATERIAL_UV[material]
            self._view.draw_blt(
                self.POPUP_SECTION2_X,
                y,
                self.MATERIAL_ICON_LAYER,
                u,
                v,
                self.MATERIAL_ICON_W,
                self.MATERIAL_ICON_H,
                0,
            )
            current_text = str(current)
            limit_text = str(limit)
            self._view.draw_text(
                self.POPUP_SECTION2_SLASH_X
                - len(current_text) * self.CHAR_W
                - self.CHAR_W,
                y,
                current_text,
            )
            self._view.draw_text(self.POPUP_SECTION2_SLASH_X, y, "/")
            self._view.draw_text(
                self.POPUP_SECTION2_TEXT_RIGHT_X - len(limit_text) * self.CHAR_W,
                y,
                limit_text,
            )


class App:
    LOAD_WAIT_FRAMES = 10

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(240, 320, title="pyxel connect city")
        pyxel.mouse(True)
        pyxel.load("images.pyxres")
        self._core = None
        self._wait_frames = 0
        pyxel.run(self.update, self.draw)

    def update(self):
        if self._core is None:
            self._wait_frames += 1
            if self._wait_frames >= self.LOAD_WAIT_FRAMES:
                self._core = GameCore()
        elif self._core.needs_reset:
            self._core = GameCore(load_data=False)
        else:
            self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(0)
        if self._core is not None:
            self._core.draw()


if __name__ == "__main__":
    App()
