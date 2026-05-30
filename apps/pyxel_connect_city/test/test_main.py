import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from src.main import (  # pylint: disable=C0413
    IView,
    IHexGridView,
    GameCore,
    GridType,
    IGridInput,
    IInput,
    PyxelHexGridView,
    PlacementMode,
    EdgeFlow,
    Clock,
)
from node import NodeType, Node, NodeManager, MaterialType  # pylint: disable=C0413
from button import Button  # pylint: disable=C0413
from edge import EdgeDirect, Edge  # pylint: disable=C0413
from grid_path import GridPath, SegmentPhase, GridDirect  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_blt(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_blt", x, y, img, u, v, w, h, colkey))

    def draw_rect(self, x, y, w, h, col):
        self.call_params.append(("draw_rect", x, y, w, h, col))

    def draw_rectb(self, x, y, w, h, col):
        self.call_params.append(("draw_rectb", x, y, w, h, col))

    def draw_image(self, x, y, img, u, v, w, h, colkey):
        self.call_params.append(("draw_image", x, y, img, u, v, w, h, colkey))

    def get_frame(self) -> int:
        return 0

    def get_call_params(self):
        return self.call_params


class TestGridInput(IGridInput):
    def __init__(self):
        self._clicked_grid = None

    def get_clicked_grid(self):
        return self._clicked_grid

    def set_clicked_grid(self, col: int, row: int):
        self._clicked_grid = (col, row)

    def clear(self):
        self._clicked_grid = None


class TestInput(IInput):
    def __init__(self):
        self._pressed = False
        self._mouse_x = 0
        self._mouse_y = 0

    def is_mouse_btn_pressed(self) -> bool:
        return self._pressed

    @property
    def mouse_x(self) -> int:
        return self._mouse_x

    @property
    def mouse_y(self) -> int:
        return self._mouse_y

    def set_pressed(self, x: int, y: int):
        self._pressed = True
        self._mouse_x = x
        self._mouse_y = y

    def clear(self):
        self._pressed = False


class TestHexGridView(IHexGridView):
    def __init__(self):
        self.call_params = []

    def draw_grid(self, col, row, grid_type=GridType.NORMAL):
        self.call_params.append(("draw_grid", col, row, grid_type))

    def draw_node(self, col, row, node_type, level=0):
        self.call_params.append(("draw_node", col, row, node_type, level))

    def draw_edge(self, col, row, direct, flow):
        self.call_params.append(("draw_edge", col, row, direct, flow))

    def get_call_params(self):
        return self.call_params


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.patcher_store = patch("src.main.ReportStore")
        self.mock_store_cls = self.patcher_store.start()
        self.mock_store = self.mock_store_cls.return_value
        self.mock_store.load.return_value = None
        self.test_hex_grid_view = TestHexGridView()
        self.patcher_hex_grid_view = patch(
            "src.main.PyxelHexGridView.create", return_value=self.test_hex_grid_view
        )
        self.patcher_hex_grid_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.patcher_input.start()
        self.test_grid_input = TestGridInput()
        self.patcher_grid_input = patch(
            "src.main.PyxelGridInput.create", return_value=self.test_grid_input
        )
        self.patcher_grid_input.start()
        self.patcher_clock = patch.object(Clock, "is_up", return_value=False)
        self.patcher_clock.start()

    def tearDown(self):
        self.patcher_clock.stop()
        self.patcher_grid_input.stop()
        self.patcher_input.stop()
        self.patcher_hex_grid_view.stop()
        self.patcher_view.stop()
        self.patcher_store.stop()

    def _grid_draw_calls(self):
        def _grid_type(row):
            if row == NodeManager.HEX_ROW_NUM:
                return GridType.SHORE
            if row > NodeManager.HEX_ROW_NUM:
                return GridType.SEA
            return GridType.NORMAL

        return [
            ("draw_grid", col, row, _grid_type(row))
            for row in range(-1, NodeManager.HEX_ROW_NUM + 2)
            for col in range(-1, NodeManager.HEX_COLUMN_NUM + 1)
        ]

    def _node_draw_calls(self, positions, node_types, levels=None):
        if levels is None:
            levels = [0] * len(node_types)
        return [
            ("draw_node", col, row, node_type, level)
            for (col, row), node_type, level in zip(positions, node_types, levels)
        ]

    def _activate_button(self, core, mode):
        """update() 経由でボタンをアクティブ化する"""
        btn = core._buttons[mode]  # pylint: disable=W0212
        self.test_input.set_pressed(btn.x + btn.width // 2, btn.y + btn.height // 2)
        core.update()
        self.test_input.clear()

    def _tap_grid(self, core, col, row):
        """update() 経由でグリッドをタップする"""
        self.test_grid_input.set_clicked_grid(col, row)
        core.update()
        self.test_grid_input.clear()

    def _double_tap(self, core, col, row):
        self._tap_grid(core, col, row)
        self._tap_grid(core, col, row)

    def _draw_calls(self, core):
        self.test_hex_grid_view.call_params.clear()
        self.test_view.call_params.clear()
        core.draw()
        return self.test_hex_grid_view.call_params[:]

    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (3, 0)]
    INITIAL_TYPES = [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1

    def _initial_node_calls(self):
        return self._node_draw_calls(self.FIXED_POSITIONS, self.INITIAL_TYPES)

    def _inject_node_manager(self, core, positions=None, types=None, extra_nodes=None):
        """positions/types（デフォルトは FIXED_POSITIONS・INITIAL_TYPES）から NodeManager を注入する"""
        positions = positions if positions is not None else self.FIXED_POSITIONS
        types = types if types is not None else self.INITIAL_TYPES
        nodes = [Node(col=c, row=r, node_type=t) for (c, r), t in zip(positions, types)]
        if extra_nodes:
            nodes.extend(extra_nodes)
        core._node_manager = NodeManager(nodes=nodes)  # pylint: disable=W0212

    def _edge_draw_calls(self, start, end, edge_direct=None):
        flow_table = {
            (EdgeDirect.FORWARD, SegmentPhase.OUT): EdgeFlow.OUTWARD,
            (EdgeDirect.FORWARD, SegmentPhase.IN): EdgeFlow.INWARD,
            (EdgeDirect.BACKWARD, SegmentPhase.OUT): EdgeFlow.INWARD,
            (EdgeDirect.BACKWARD, SegmentPhase.IN): EdgeFlow.OUTWARD,
        }

        return [
            ("draw_edge", col, row, direct, flow_table.get((edge_direct, phase)))
            for col, row, direct, phase in GridPath.iter_edge_segments(start, end)
        ]

    def _route_preview_calls(self, start, end):
        """start を除く経路グリッドの HIGHLIGHTED draw_grid 呼び出しリスト"""
        return [
            ("draw_grid", col, row, GridType.HIGHLIGHTED)
            for col, row in GridPath.route_grids(start, end)[1:]
        ]

    def _route_fail_calls(self, start, end):
        """start を除く経路グリッドの FAIL_HIGHLIGHTED draw_grid 呼び出しリスト"""
        return [
            ("draw_grid", col, row, GridType.FAIL_HIGHLIGHTED)
            for col, row in GridPath.route_grids(start, end)[1:]
        ]

    def _button_view_calls(self, active_mode=None, city_count=1, factory_count=0):
        """ボタン描画の期待呼び出しリストを返す（CITY → FACTORY → DELETE_NODE → EDGE → DELETE_EDGE の順）"""
        btn_w, btn_h = 24, 24
        icon_pad = (btn_w - Button.ICON_SIZE) // 2
        city_x, city_y = 4, 292
        factory_x, factory_y = 32, 292
        edge_x, edge_y = 96, 292
        delete_x, delete_y = 60, 292
        delete_edge_x, delete_edge_y = 124, 292
        city_u, city_v = 8, PyxelHexGridView.NODE_V[NodeType.CITY]
        factory_u, factory_v = 8, PyxelHexGridView.NODE_V[NodeType.FACTORY]
        edge_u, edge_v = 8, 64
        delete_u, delete_v = 8, 80
        delete_edge_u, delete_edge_v = 24, 80

        def _bg(mode, count):
            if count == 0:
                return Button.DISABLED_BG_COLOR
            if active_mode == mode:
                return Button.ACTIVE_BG_COLOR
            return Button.NORMAL_BG_COLOR

        def _btn_calls(x, y, mode, u, v, count):
            bg = _bg(mode, count)
            calls = [
                ("draw_rect", x, y, btn_w, btn_h, bg),
                ("draw_rectb", x, y, btn_w, btn_h, 7),
                (
                    "draw_image",
                    x + icon_pad,
                    y + icon_pad,
                    1,
                    u,
                    v,
                    Button.ICON_SIZE,
                    Button.ICON_SIZE,
                    0,
                ),
            ]
            if count is not None:
                label = str(count) if count < 10 else "9+"
                calls.append(("draw_text", x + btn_w - 8, y + btn_h - 8, label))
            return calls

        return (
            _btn_calls(city_x, city_y, PlacementMode.CITY, city_u, city_v, city_count)
            + _btn_calls(
                factory_x,
                factory_y,
                PlacementMode.FACTORY,
                factory_u,
                factory_v,
                factory_count,
            )
            + _btn_calls(
                delete_x,
                delete_y,
                PlacementMode.DELETE_NODE,
                delete_u,
                delete_v,
                None,
            )
            + _btn_calls(edge_x, edge_y, PlacementMode.EDGE, edge_u, edge_v, None)
            + _btn_calls(
                delete_edge_x,
                delete_edge_y,
                PlacementMode.DELETE_EDGE,
                delete_edge_u,
                delete_edge_v,
                None,
            )
        )


class TestAppLoadWait(TestParent):
    """App による GameCore 生成の待機フレーム動作のテスト"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()
        from src.main import App as _App  # pylint: disable=C0415

        self.app_class = _App

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def test_core_not_created_before_wait_frames(self):
        """LOAD_WAIT_FRAMES 未満の update() では _core が生成されないこと"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES - 1):
            app.update()
        self.assertIsNone(app._core)  # pylint: disable=W0212

    def test_core_created_after_wait_frames(self):
        """LOAD_WAIT_FRAMES 回 update() を呼ぶと _core が GameCore として生成されること"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES):
            app.update()
        self.assertIsInstance(app._core, GameCore)  # pylint: disable=W0212


class TestGameCoreInitialDraw(TestParent):
    # FOREST×3: (0,0),(1,0),(2,0) / MOUNTAIN×1: (3,0) / CITY×1: (3,5) 固定
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 5)]
    INITIAL_TYPES = (
        [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1 + [NodeType.CITY] * 1
    )

    def test_draw_full_sequence(self):
        """初期状態: NORMAL グリッド全セル → ノード全件の順で描画されること"""
        core = GameCore()
        self._inject_node_manager(core)
        core.draw()
        expected = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS,
            self.INITIAL_TYPES,
        )
        self.assertEqual(expected, self.test_hex_grid_view.call_params)

    def test_draw_button_sequence(self):
        """初期状態: CITY → FACTORY → EDGE の順に draw_rect / draw_rectb / draw_image が描画されること"""
        core = GameCore()
        self._inject_node_manager(core)
        core.draw()
        # 初期 CITY×1 配置済み → city_count=0
        self.assertEqual(
            self._button_view_calls(city_count=0), self.test_view.call_params
        )


class TestGameCoreTapDraw(TestParent):
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 5)]
    INITIAL_TYPES = (
        [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1 + [NodeType.CITY] * 1
    )

    def _tap(self, col, row):
        self.test_grid_input.set_clicked_grid(col, row)

    def _node_calls(self):
        return self._node_draw_calls(self.FIXED_POSITIONS, self.INITIAL_TYPES)

    def test_draw_after_taps(self):
        """NO_MODE タップ後の描画: NORMAL → HIGHLIGHTED（あれば）→ ノードの順で描画されること（SELECTED は NO_MODE では表示されない）"""
        cases = [
            # (label, taps, expected_selected, expected_highlight)
            ("A をタップ → HIGHLIGHTED(A)", [(0, 0)], None, (0, 0)),
            ("B をタップ → HIGHLIGHTED(B) に移動", [(0, 0), (1, 0)], None, (1, 0)),
            ("A を2回タップ → リセット（表示なし）", [(0, 0), (0, 0)], None, None),
            (
                "A 2回タップ後 B タップ → HIGHLIGHTED(B) のみ",
                [(0, 0), (0, 0), (1, 0)],
                None,
                (1, 0),
            ),
            (
                "A B それぞれ2回タップ → 全クリア",
                [(0, 0), (0, 0), (1, 0), (1, 0)],
                None,
                None,
            ),
            (
                "2回タップリセット後に再タップ → HIGHLIGHTED(A)",
                [(0, 0), (0, 0), (0, 0)],
                None,
                (0, 0),
            ),
            (
                "再ハイライト後に2回タップ → 全クリア",
                [(0, 0), (0, 0), (0, 0), (0, 0)],
                None,
                None,
            ),
        ]
        for label, taps, expected_selected, expected_highlight in cases:
            with self.subTest(label):
                core = GameCore()
                self._inject_node_manager(core)
                for tap in taps:
                    self._tap(*tap)
                    core.update()
                selected_calls = (
                    [("draw_grid", *expected_selected, GridType.SELECTED)]
                    if expected_selected is not None
                    else []
                )
                highlight_calls = (
                    [("draw_grid", *expected_highlight, GridType.HIGHLIGHTED)]
                    if expected_highlight is not None
                    else []
                )
                expected = (
                    self._grid_draw_calls()
                    + selected_calls
                    + highlight_calls
                    + self._node_calls()
                )
                self.assertEqual(expected, self._draw_calls(core))

    def test_reset_clears_draw(self):
        """reset() 後の描画: HIGHLIGHTED が表示されないこと（NO_MODE では selected_grid は update() で即リセット済み）"""
        cases = [
            ("1回タップ後に reset() → ハイライトなし", [(0, 0)]),
            (
                "2回タップ後（NO_MODE で update() リセット済み）に reset() → 変化なし",
                [(0, 0), (0, 0)],
            ),
        ]
        for label, taps in cases:
            with self.subTest(label):
                core = GameCore()
                self._inject_node_manager(core)
                for tap in taps:
                    self._tap(*tap)
                    core.update()
                core._grid_selection.reset()  # pylint: disable=W0212
                expected = self._grid_draw_calls() + self._node_calls()
                self.assertEqual(expected, self._draw_calls(core))


class TestGameCoreButtonPlacement(TestParent):
    # FIXED_POSITIONS は TestParent デフォルト: FOREST×3:(0,0),(1,0),(2,0) / MOUNTAIN×1:(3,0)
    # CITY は注入時に含めず、CITY ボタンを活性化可能にする
    # 空きセル: (5,0), (6,0)

    def _click_button(self, core, mode):
        """ボタン中央座標で _click_button を呼ぶ"""
        btn = core._buttons[mode]  # pylint: disable=W0212
        core._click_button(  # pylint: disable=W0212
            btn.x + btn.width // 2, btn.y + btn.height // 2
        )

    def test_placement_scenarios(self):
        """ボタン押下→グリッド 2 タップ後の描画を検証するパラメタライズドテスト"""
        _city_lv1 = Node(col=7, row=0, node_type=NodeType.CITY, level=1)
        cases = [
            # (label, button_modes, grid_cell, no_active_pixel, extra_nodes, exp_positions, exp_types, exp_levels, exp_active_mode, city_count, factory_count)
            # grid_cell: (col, row) を 2 タップして配置 / no_active_pixel: _click_button() 直呼び（ボタン非 active 検証）
            (
                "CITY ボタン → グリッド 2 タップ → CITY ノードが描画される",
                [PlacementMode.CITY],
                (5, 0),
                None,
                None,
                self.FIXED_POSITIONS + [(5, 0)],
                self.INITIAL_TYPES + [NodeType.CITY],
                None,
                None,
                0,  # CITY配置後: 街lv1=0、街1個 → count=0
                0,  # factory limit=0 (街Lv1なし)
            ),
            (
                "FACTORY ボタン → グリッド 2 タップ → FACTORY ノードが描画される",
                [PlacementMode.FACTORY],
                (6, 0),
                None,
                [_city_lv1],  # factory limit=1 にするため街Lv1を注入
                self.FIXED_POSITIONS + [(7, 0), (6, 0)],
                self.INITIAL_TYPES + [NodeType.CITY, NodeType.FACTORY],
                [0] * len(self.INITIAL_TYPES) + [1, 0],
                None,
                0,  # city limit=1、街1個(Lv1) → count=0
                0,  # factory limit=1、工場1個 → count=0
            ),
            (
                "CITY → FACTORY の順でクリック: ノードが追加されない",
                [PlacementMode.CITY, PlacementMode.FACTORY],
                None,
                None,
                [_city_lv1],  # factory limit=1 にするため街Lv1を注入
                self.FIXED_POSITIONS + [(7, 0)],
                self.INITIAL_TYPES + [NodeType.CITY],
                [0] * len(self.INITIAL_TYPES) + [1],
                PlacementMode.FACTORY,
                0,  # city limit=1、街1個(Lv1) → count=0
                1,  # factory limit=1、工場0個 → count=1
            ),
            (
                "active なボタンが無い状態でグリッドをクリックしても描画に変化がない",
                [],
                None,
                (176, 16),
                None,
                self.FIXED_POSITIONS,
                self.INITIAL_TYPES,
                None,
                None,
                1,
                0,  # factory limit=0 (街Lv1なし)
            ),
        ]
        for (
            label,
            button_modes,
            grid_cell,
            no_active_pixel,
            extra_nodes,
            exp_positions,
            exp_types,
            exp_levels,
            exp_active_mode,
            city_count,
            factory_count,
        ) in cases:
            with self.subTest(label):
                self.test_hex_grid_view.call_params.clear()
                self.test_view.call_params.clear()
                core = GameCore()
                self._inject_node_manager(core, extra_nodes=extra_nodes)
                for mode in button_modes:
                    self._click_button(core, mode)
                if grid_cell is not None:
                    col, row = grid_cell
                    self._tap_grid(core, col, row)
                    self._tap_grid(core, col, row)
                if no_active_pixel is not None:
                    core._click_button(*no_active_pixel)  # pylint: disable=W0212
                core.draw()
                expected_hex = self._grid_draw_calls() + self._node_draw_calls(
                    exp_positions, exp_types, exp_levels
                )
                self.assertEqual(expected_hex, self.test_hex_grid_view.call_params)
                self.assertEqual(
                    self._button_view_calls(
                        exp_active_mode,
                        city_count=city_count,
                        factory_count=factory_count,
                    ),
                    self.test_view.call_params,
                )


class TestGameCoreGridButtonIntegration(TestParent):
    """ケース2・ケース4: ボタンモードとグリッド選択の統合テスト"""

    # FIXED_POSITIONS は TestParent デフォルト: FOREST×3:(0,0),(1,0),(2,0) / MOUNTAIN×1:(3,0)
    # CITY は注入時に含めず、CITY ボタンを活性化可能にする

    def _new_core(self, extra_nodes=None):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_button_click_resets_tapped_grid(self):
        """ケース2: グリッドをタップ済みの状態でボタンをクリックすると tapped_grid がリセットされること"""
        core = self._new_core()
        self._tap_grid(core, 5, 0)
        self.assertEqual(
            (5, 0), core._grid_selection.tapped_grid  # pylint: disable=W0212
        )
        self._activate_button(core, PlacementMode.CITY)
        self.assertIsNone(core._grid_selection.tapped_grid)  # pylint: disable=W0212
        expected_hex = self._grid_draw_calls() + self._initial_node_calls()
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.CITY), self.test_view.call_params
        )

    def test_button_active_tap_scenarios(self):
        """ケース4: ボタンアクティブ状態でのタップ数別描画検証"""
        cases = [
            (
                "1タップ → グリッドがハイライトされノードが配置されないこと",
                [(5, 0)],
                [("draw_grid", 5, 0, GridType.HIGHLIGHTED)],
                self.FIXED_POSITIONS,
                self.INITIAL_TYPES,
                PlacementMode.CITY,
                1,
            ),
            (
                "同グリッド2タップ → ノードが配置されハイライトがリセットされること",
                [(5, 0), (5, 0)],
                [],
                self.FIXED_POSITIONS + [(5, 0)],
                self.INITIAL_TYPES + [NodeType.CITY],
                None,
                0,  # CITY配置後: count=0
            ),
        ]
        for (
            label,
            taps,
            highlight_calls,
            exp_positions,
            exp_types,
            exp_active_mode,
            city_count,
        ) in cases:
            with self.subTest(label):
                core = self._new_core()
                self._activate_button(core, PlacementMode.CITY)
                for col, row in taps:
                    self._tap_grid(core, col, row)
                expected_hex = (
                    self._grid_draw_calls()
                    + highlight_calls
                    + self._node_draw_calls(exp_positions, exp_types)
                )
                self.assertEqual(expected_hex, self._draw_calls(core))
                self.assertEqual(
                    self._button_view_calls(exp_active_mode, city_count=city_count),
                    self.test_view.call_params,
                )

    def test_toggle_off(self):
        """同じボタンを 2 回クリックで active が解除され、その後グリッドをタップしてもノードが追加されないこと"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._activate_button(core, PlacementMode.CITY)  # toggle off

        # トグル OFF 直後: active ボタンなし
        expected_hex = self._grid_draw_calls() + self._initial_node_calls()
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(self._button_view_calls(None), self.test_view.call_params)

        # トグル OFF 後のグリッドタップ: NO_MODE 扱いで同一グリッド2回タップはリセット、ノード未追加
        self._tap_grid(core, 5, 0)
        self._tap_grid(core, 5, 0)
        expected_hex = self._grid_draw_calls() + self._initial_node_calls()
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_no_duplicate_placement(self):
        """CITY 配置済みの位置に FACTORY モードでクリックしてもノードが増えず、FACTORY ボタンが active のままであること"""
        city_lv1 = Node(col=7, row=0, node_type=NodeType.CITY, level=1)
        core = self._new_core(extra_nodes=[city_lv1])

        # FACTORY モードで既存 CITY(7,0) と同じ位置をタップ → FACTORY は配置されない
        self._activate_button(core, PlacementMode.FACTORY)
        self._tap_grid(core, 7, 0)
        self._tap_grid(core, 7, 0)

        # ノードは extra_nodes の CITY のみ（FACTORY は配置されない）、FACTORY ボタンは active のまま
        placed_positions = self.FIXED_POSITIONS + [(7, 0)]
        placed_types = self.INITIAL_TYPES + [NodeType.CITY]
        placed_levels = [0] * len(self.INITIAL_TYPES) + [1]
        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            placed_positions, placed_types, placed_levels
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        # 街Lv1×1 → city_count=0（city_limit=1）、factory_count=1（factory_limit=1、工場0個）
        self.assertEqual(
            self._button_view_calls(
                PlacementMode.FACTORY, city_count=0, factory_count=1
            ),
            self.test_view.call_params,
        )

    def test_deactivated_after_placement_and_no_further_nodes(self):
        """ノード配置後にボタンが非アクティブになり、以降のタップでノードが追加されないこと"""
        city_lv1 = Node(col=7, row=0, node_type=NodeType.CITY, level=1)
        _fp = self.FIXED_POSITIONS
        _it = self.INITIAL_TYPES
        cases = [
            # (label, mode, extra_nodes, placed_positions, placed_types, placed_levels, city_count, factory_count)
            # CITY: 街なし → city_limit=1 → 配置後 city_count=0、factory_count=0（Lv0街は工場枠を増やさない）
            (
                "CITY",
                PlacementMode.CITY,
                None,
                _fp + [(5, 0)],
                _it + [NodeType.CITY],
                [0] * len(_it) + [0],
                0,
                0,
            ),
            # FACTORY: 街Lv1×1 → factory_limit=1 → 配置後 factory_count=0、city_limit=1 超過で city_count=0
            (
                "FACTORY",
                PlacementMode.FACTORY,
                [city_lv1],
                _fp + [(7, 0), (5, 0)],
                _it + [NodeType.CITY, NodeType.FACTORY],
                [0] * len(_it) + [1, 0],
                0,
                0,
            ),
        ]
        for (
            label,
            mode,
            extra_nodes,
            placed_positions,
            placed_types,
            placed_levels,
            city_count,
            factory_count,
        ) in cases:
            with self.subTest(label):
                core = self._new_core(extra_nodes=extra_nodes)
                self._activate_button(core, mode)
                self._tap_grid(core, 5, 0)
                self._tap_grid(core, 5, 0)

                # 配置直後: ボタン非アクティブ + 配置ノードが描画される
                expected_hex = self._grid_draw_calls() + self._node_draw_calls(
                    placed_positions, placed_types, placed_levels
                )
                self.assertEqual(expected_hex, self._draw_calls(core))
                self.assertEqual(
                    self._button_view_calls(
                        None,
                        city_count=city_count,
                        factory_count=factory_count,
                    ),
                    self.test_view.call_params,
                )

                # 配置後のタップ: NO_MODE 扱いで同一グリッド2回タップはリセット、ノード未追加
                self._tap_grid(core, 6, 0)
                self._tap_grid(core, 6, 0)
                expected_hex = self._grid_draw_calls() + self._node_draw_calls(
                    placed_positions, placed_types, placed_levels
                )
                self.assertEqual(expected_hex, self._draw_calls(core))


class TestGameCoreEdgePlacement(TestParent):
    """TDD サイクル 3 Red: 2回押下によるノード確定フロー テスト"""

    # CITY 配置可能にするため CITY なしの NodeManager を注入する想定。
    # MOUNTAIN を (4,0) に置くことで test_two_double_taps_in_edge_mode の (5,0)→(4,0) エッジテストを満たす。
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (4, 0)]
    INITIAL_TYPES = [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1

    def _new_core(self, extra_nodes=None):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_two_double_taps_in_edge_mode_creates_edge_and_deactivates_button(self):
        """EDGE モードで 2 つのノードをそれぞれ2回押下するとエッジが作成されボタンが非アクティブになること（正常フロー）"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(
            core, 5, 0
        )  # CITY ノードを配置（片方が CITY/FACTORY であることが必要）
        self._activate_button(core, PlacementMode.EDGE)
        self.assertEqual(0, len(core._edge_manager._edges))  # pylint: disable=W0212
        self._double_tap(core, 5, 0)  # CITY ノード確定
        self.assertEqual(0, len(core._edge_manager._edges))  # pylint: disable=W0212
        self._double_tap(core, 4, 0)  # MOUNTAIN ノード確定 → エッジ作成
        self.assertEqual(1, len(core._edge_manager._edges))  # pylint: disable=W0212
        placed_positions = self.FIXED_POSITIONS + [(5, 0)]
        placed_types = self.INITIAL_TYPES + [NodeType.CITY]
        expected_hex = (
            self._grid_draw_calls()
            + self._edge_draw_calls((5, 0), (4, 0))
            + self._node_draw_calls(placed_positions, placed_types)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        # CITY 配置済み → city_count=0
        self.assertEqual(
            self._button_view_calls(None, city_count=0), self.test_view.call_params
        )

    def test_edge_not_created_in_non_edge_mode(self):
        """EDGE 以外のモード active 中に同じ操作をしてもエッジが追加されないこと"""
        _city_lv1 = Node(col=7, row=0, node_type=NodeType.CITY, level=1)
        cases = [
            # (mode, extra_nodes, node_positions, node_types, node_levels, city_count, factory_count)
            (
                PlacementMode.CITY,
                None,
                self.FIXED_POSITIONS,
                self.INITIAL_TYPES,
                [0] * len(self.INITIAL_TYPES),
                1,  # city_limit=1、街0個 → count=1
                0,
            ),
            (
                PlacementMode.FACTORY,
                [_city_lv1],
                self.FIXED_POSITIONS + [(7, 0)],
                self.INITIAL_TYPES + [NodeType.CITY],
                [0] * len(self.INITIAL_TYPES) + [1],
                0,  # city_limit=1、街Lv1×1 → count=0
                1,
            ),
        ]
        for (
            mode,
            extra_nodes,
            node_positions,
            node_types,
            node_levels,
            city_count,
            factory_count,
        ) in cases:
            with self.subTest(mode=mode):
                core = self._new_core(extra_nodes=extra_nodes)
                self._activate_button(core, mode)
                self._tap_grid(core, 0, 0)
                self._tap_grid(core, 1, 0)
                self.assertEqual(
                    0, len(core._edge_manager._edges)  # pylint: disable=W0212
                )
                expected_hex = (
                    self._grid_draw_calls()
                    + [("draw_grid", 1, 0, GridType.FAIL_HIGHLIGHTED)]
                    + self._node_draw_calls(node_positions, node_types, node_levels)
                )
                self.assertEqual(expected_hex, self._draw_calls(core))
                self.assertEqual(
                    self._button_view_calls(
                        mode, city_count=city_count, factory_count=factory_count
                    ),
                    self.test_view.call_params,
                )

    def test_button_still_active_after_first_node_click(self):
        """EDGE モードでノードを1回押下してもボタンはアクティブであること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._tap_grid(core, 0, 0)
        self.assertEqual(0, len(core._edge_manager._edges))  # pylint: disable=W0212
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 0, 0, GridType.HIGHLIGHTED)]
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.EDGE), self.test_view.call_params
        )

    def test_button_stays_active_when_empty_grid_clicked(self):
        """EDGE モードで空グリッドをクリックしてもエッジが追加されず、ボタンがアクティブのままであること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._tap_grid(core, 5, 0)
        self._tap_grid(core, 6, 0)
        self.assertEqual(0, len(core._edge_manager._edges))  # pylint: disable=W0212
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 6, 0, GridType.FAIL_HIGHLIGHTED)]
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.EDGE), self.test_view.call_params
        )

    def test_double_tap_on_node_confirms_first_node_and_shows_selected(self):
        """EDGE モードでノードありグリッドを2回押下すると1つ目のノードが確定し選択状態が表示されること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 0, 0)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 0, 0, GridType.SELECTED)]
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.EDGE), self.test_view.call_params
        )

    def test_empty_grid_double_tap_resets_selection_and_continues_edge_mode(self):
        """ステップ2でノードなしグリッドを2回押下した場合、グリッド選択がリセットされ EDGE モードが継続されること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)  # ノードなしグリッドを2回押下
        expected_hex = self._grid_draw_calls() + self._initial_node_calls()
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.EDGE), self.test_view.call_params
        )

    def test_double_tap_after_first_confirm_resets_and_continues(self):
        """1つ目のノード確定後、エッジ配置が失敗する操作をすると選択がリセットされモードが継続されること"""
        cases = [
            ("同一グリッド", 0, 0),
            ("ノードなしグリッド", 5, 0),
            ("経路上に中間ノードあり", 2, 0),  # (0,0)→(2,0) は (1,0) でブロック
        ]
        for label, col, row in cases:
            with self.subTest(second_tap=label):
                core = self._new_core()
                self._activate_button(core, PlacementMode.EDGE)
                self._double_tap(core, 0, 0)  # 1つ目のノード確定
                self._double_tap(core, col, row)  # エッジ配置失敗 → リセット
                expected_hex = self._grid_draw_calls() + self._initial_node_calls()
                self.assertEqual(expected_hex, self._draw_calls(core))
                self.assertEqual(
                    self._button_view_calls(PlacementMode.EDGE),
                    self.test_view.call_params,
                )

    def test_edge_not_placed_after_switching_to_city_mode(self):
        """EDGE モードから CITY モードに切り替えてグリッドをタップしてもエッジが配置されないこと"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 0, 0)
        self._double_tap(core, 1, 0)
        self.assertEqual(0, len(core._edge_manager._edges))  # pylint: disable=W0212
        expected_hex = self._grid_draw_calls() + self._initial_node_calls()
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.CITY), self.test_view.call_params
        )

    def test_draw_single_edge_calls_draw_edge_per_segment(self):
        """単一エッジ (5,0)→(5,2) が存在するとき、draw() が中間グリッド (4,1) を含む全セグメントの draw_edge を呼ぶこと"""
        # (5,0)→(5,2) の経路は (4,1) を経由（FIXED_POSITIONS にノードなし）
        # city_lv4: city_limit=2（Lv4×1）なので CITY 追加配置が可能、factory_limit=2 で FACTORY 配置も可能
        city_lv4 = Node(col=7, row=0, node_type=NodeType.CITY, level=4)
        core = self._new_core(extra_nodes=[city_lv4])
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)
        self._activate_button(core, PlacementMode.FACTORY)
        self._double_tap(core, 5, 2)
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)
        self._double_tap(core, 5, 2)
        self.assertEqual(1, len(core._edge_manager._edges))  # pylint: disable=W0212
        placed_positions = self.FIXED_POSITIONS + [(7, 0), (5, 0), (5, 2)]
        placed_types = self.INITIAL_TYPES + [
            NodeType.CITY,
            NodeType.CITY,
            NodeType.FACTORY,
        ]
        placed_levels = [0] * len(self.INITIAL_TYPES) + [4, 0, 0]
        expected_hex = (
            self._grid_draw_calls()
            + self._edge_draw_calls((5, 0), (5, 2))
            + self._node_draw_calls(placed_positions, placed_types, placed_levels)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_draw_edge_appears_after_highlight_in_sequence(self):
        """エッジ描画はハイライト/選択グリッドの後、ノードの前に行われること"""
        core = self._new_core()
        # CITY(5,0)→MOUNTAIN(4,0) のエッジを作成
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)
        self._double_tap(core, 4, 0)
        # EDGE モードを再度アクティブにして (2,0) を1回タップ → ハイライト状態
        self._activate_button(core, PlacementMode.EDGE)
        self._tap_grid(core, 2, 0)
        placed_positions = self.FIXED_POSITIONS + [(5, 0)]
        placed_types = self.INITIAL_TYPES + [NodeType.CITY]
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 2, 0, GridType.HIGHLIGHTED)]
            + self._edge_draw_calls((5, 0), (4, 0))
            + self._node_draw_calls(placed_positions, placed_types)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_draw_two_crossing_edges_renders_all_segments(self):
        """2本のエッジが同一グリッドを通る場合、両方のエッジの draw_edge が当該グリッドに描画されること"""
        # エッジ1: (5,0)→(5,2) ─ (4,1) を通過
        # エッジ2: (3,0)→(5,2) ─ (3,1) と (4,1) を通過
        # 両エッジとも (4,1) を経由（FIXED_POSITIONS のノードは経路上になし）
        # (3,0) を FOREST として追加することで、エッジ2の始点として確定可能にする
        # city_lv4: city_limit=2（Lv4×1）なので CITY 追加配置が可能、factory_limit=2 で FACTORY 配置も可能
        city_lv4 = Node(col=7, row=0, node_type=NodeType.CITY, level=4)
        core = self._new_core(
            extra_nodes=[Node(col=3, row=0, node_type=NodeType.FOREST), city_lv4]
        )
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)
        self._activate_button(core, PlacementMode.FACTORY)
        self._double_tap(core, 5, 2)
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)
        self._double_tap(core, 5, 2)
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 3, 0)
        self._double_tap(core, 5, 2)
        self.assertEqual(2, len(core._edge_manager._edges))  # pylint: disable=W0212
        placed_positions = self.FIXED_POSITIONS + [(3, 0), (7, 0), (5, 0), (5, 2)]
        placed_types = self.INITIAL_TYPES + [
            NodeType.FOREST,
            NodeType.CITY,
            NodeType.CITY,
            NodeType.FACTORY,
        ]
        placed_levels = [0] * len(self.INITIAL_TYPES) + [0, 4, 0, 0]
        expected_hex = (
            self._grid_draw_calls()
            + self._edge_draw_calls((5, 0), (5, 2))
            + self._edge_draw_calls((3, 0), (5, 2))
            + self._node_draw_calls(placed_positions, placed_types, placed_levels)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_no_route_preview_without_first_node_confirmation(self):
        """1つ目のノード未確定時は通常のハイライト描画のみで、経路ハイライトが表示されないこと"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._tap_grid(core, 2, 0)  # 1回だけタップ（_edge_first_node = None）
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 2, 0, GridType.HIGHLIGHTED)]
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_route_preview_highlighted_after_first_node_confirmed(self):
        """1つ目のノード確定後、タップ位置が変わるたびに経路全体（起点除く）が HIGHLIGHTED 更新されること"""
        # CITY(5,0) を始点として隣接ノードへのプレビューを確認
        # (4,0)=MOUNTAIN と (6,0)=FACTORY (配置済み) は (5,0) に隣接し中間ノードなし
        cases = [
            ("直接ターゲット選択", [(4, 0)], (4, 0)),
            ("ターゲット変更", [(4, 0), (6, 0)], (6, 0)),
        ]
        # city_lv4: city_limit=2（Lv4×1）なので CITY 追加配置が可能、factory_limit=2 で FACTORY 配置も可能
        city_lv4 = Node(col=7, row=0, node_type=NodeType.CITY, level=4)
        for label, taps, end in cases:
            with self.subTest(case=label):
                core = self._new_core(extra_nodes=[city_lv4])
                self._activate_button(core, PlacementMode.CITY)
                self._double_tap(core, 5, 0)  # CITY at (5,0)
                self._activate_button(core, PlacementMode.FACTORY)
                self._double_tap(core, 6, 0)  # FACTORY at (6,0) for "ターゲット変更"
                self._activate_button(core, PlacementMode.EDGE)
                self._double_tap(core, 5, 0)  # 1つ目ノード確定 (CITY)
                for col, row in taps:
                    self._tap_grid(core, col, row)
                placed_positions = self.FIXED_POSITIONS + [(7, 0), (5, 0), (6, 0)]
                placed_types = self.INITIAL_TYPES + [
                    NodeType.CITY,
                    NodeType.CITY,
                    NodeType.FACTORY,
                ]
                placed_levels = [0] * len(self.INITIAL_TYPES) + [4, 0, 0]
                expected_hex = (
                    self._grid_draw_calls()
                    + [("draw_grid", 5, 0, GridType.SELECTED)]
                    + self._route_preview_calls((5, 0), end)
                    + self._node_draw_calls(
                        placed_positions, placed_types, placed_levels
                    )
                )
                self.assertEqual(expected_hex, self._draw_calls(core))

    def test_node_placement_relative_to_edge_path(self):
        """エッジ作成後、経路上への配置は失敗し、経路外への配置は成功すること"""
        cases = [
            {
                "desc": "経路上の中間グリッド (4,1) には配置できない",
                "col": 4,
                "row": 1,
                "expected_node_count": 6,  # 4 (初期) + 2 (lv1 CITY×2)
            },
            {
                "desc": "経路外のグリッド (6,0) には配置できる",
                "col": 6,
                "row": 0,
                "expected_node_count": 7,  # 4 (初期) + 2 (lv1 CITY×2) + 1 (6,0)
            },
        ]
        for case in cases:
            with self.subTest(case["desc"]):
                # エッジ (5,0)→(5,2) を作成。経路は (4,1) を経由
                # Lv4 CITY×2 で city_limit=3 を確保し、3番目の CITY 配置テストを可能にする
                core = GameCore()
                self._inject_node_manager(
                    core,
                    extra_nodes=[
                        Node(col=5, row=0, node_type=NodeType.CITY, level=4),
                        Node(col=5, row=2, node_type=NodeType.CITY, level=4),
                    ],
                )
                self._activate_button(core, PlacementMode.EDGE)
                self._double_tap(core, 5, 0)
                self._double_tap(core, 5, 2)
                self.assertEqual(
                    1, len(core._edge_manager._edges)  # pylint: disable=W0212
                )
                self._activate_button(core, PlacementMode.CITY)
                self._double_tap(core, case["col"], case["row"])
                self.assertEqual(
                    case["expected_node_count"],
                    len(core._node_manager._nodes),  # pylint: disable=W0212
                )


class TestGameCoreFailHighlight(TestParent):
    """TDD サイクル 6.5 Red: 配置不可グリッドへのシングルタップ時 FAIL_HIGHLIGHTED 表示テスト"""

    # CITY 配置可能にするため CITY なしの NodeManager を注入する想定
    # MOUNTAIN を (4,0) に置くことで経路テストの端点を確保
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (4, 0)]
    INITIAL_TYPES = [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1

    def _new_core(self, extra_nodes=None):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_fail_highlighted_on_single_tap_to_blocked_grid(self):
        """配置不可グリッドへのシングルタップ時、HIGHLIGHTED ではなく FAIL_HIGHLIGHTED で描画されること"""
        cases = [
            ("既存ノードへのタップ", PlacementMode.CITY, 0, 0),
        ]
        for label, mode, col, row in cases:
            with self.subTest(label):
                core = self._new_core()
                self._activate_button(core, mode)
                self._tap_grid(core, col, row)
                expected_hex = (
                    self._grid_draw_calls()
                    + [("draw_grid", col, row, GridType.FAIL_HIGHLIGHTED)]
                    + self._initial_node_calls()
                )
                self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_in_edge_mode_invalid_tap(self):
        """EDGE モードで無効なグリッドをタップすると FAIL_HIGHLIGHTED で描画されること"""
        cases = [
            (
                "ステップ1: 未確定状態で空グリッドをタップ",
                [],
                5,
                0,
                None,
            ),
            (
                "ステップ2: 1つ目ノード確定後に空グリッドをタップ（経路全体が FAIL_HIGHLIGHTED）",
                [(0, 0), (0, 0)],
                5,
                0,
                (0, 0),
            ),
        ]
        for label, pre_taps, col, row, selected_pos in cases:
            with self.subTest(label):
                core = self._new_core()
                self._activate_button(core, PlacementMode.EDGE)
                for pre_col, pre_row in pre_taps:
                    self._tap_grid(core, pre_col, pre_row)
                self._tap_grid(core, col, row)
                selected_calls = (
                    [("draw_grid", *selected_pos, GridType.SELECTED)]
                    if selected_pos is not None
                    else []
                )
                fail_calls = (
                    self._route_fail_calls(selected_pos, (col, row))
                    if selected_pos is not None
                    else [("draw_grid", col, row, GridType.FAIL_HIGHLIGHTED)]
                )
                expected_hex = (
                    self._grid_draw_calls()
                    + selected_calls
                    + fail_calls
                    + self._initial_node_calls()
                )
                self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_in_edge_mode_blocked_route_tap(self):
        """EDGE モードのステップ2で経路上に別ノードがある場合、経路全体が FAIL_HIGHLIGHTED で描画されること"""
        # 1つ目ノード (0,0) 確定後、(2,0) をタップ。
        # (0,0)→(2,0) の経路上に (1,0) FOREST があり経路がブロックされる。
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 0, 0)
        self._tap_grid(core, 2, 0)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 0, 0, GridType.SELECTED)]
            + self._route_fail_calls((0, 0), (2, 0))
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_on_single_tap_to_edge_path_grid(self):
        """エッジ経路上グリッドへのシングルタップ時、FAIL_HIGHLIGHTED で描画されること"""
        # エッジ (5,0)→(5,2) を作成。中間グリッド (4,1) を経由
        # Lv4 CITY×2 で city_limit=3 を確保し、CITY 2個配置済みでも追加 CITY 活性化可能にする
        core = GameCore()
        self._inject_node_manager(
            core,
            extra_nodes=[
                Node(col=5, row=0, node_type=NodeType.CITY, level=4),
                Node(col=5, row=2, node_type=NodeType.CITY, level=4),
            ],
        )
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)
        self._double_tap(core, 5, 2)
        placed_positions = self.FIXED_POSITIONS + [(5, 0), (5, 2)]
        placed_types = self.INITIAL_TYPES + [NodeType.CITY, NodeType.CITY]
        placed_levels = [0] * len(self.INITIAL_TYPES) + [4, 4]
        # CITY モードで経路上の (4,1) をシングルタップ → FAIL_HIGHLIGHTED
        self._activate_button(core, PlacementMode.CITY)
        self._tap_grid(core, 4, 1)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 4, 1, GridType.FAIL_HIGHLIGHTED)]
            + self._edge_draw_calls((5, 0), (5, 2))
            + self._node_draw_calls(placed_positions, placed_types, placed_levels)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))


class TestGameCoreNodeSaveLoad(TestParent):
    # FOREST×3: (0,0),(1,0),(2,0) / MOUNTAIN×1: (3,0) / CITY×1: (3,5)（固定）
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 5)]
    INITIAL_TYPES = (
        [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1 + [NodeType.CITY] * 1
    )

    def test_apply_load_data_restores_nodes(self):
        """_apply_load_data() で復元されたノードが level を含めて draw() で描画されること"""
        core = GameCore()
        core._apply_load_data(  # pylint: disable=W0212
            {
                "nodes": [
                    {
                        "col": 1,
                        "row": 2,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 1,
                    }
                ],
            }
        )
        self.test_hex_grid_view.call_params.clear()
        core.draw()
        expected = self._grid_draw_calls() + self._node_draw_calls(
            [(1, 2)],
            [NodeType.CITY],
            [1],
        )
        self.assertEqual(expected, self.test_hex_grid_view.call_params)

    def test_save_load_roundtrip_preserves_draw(self):
        """保存したノード配置を復元すると同じ描画になること"""
        core = GameCore()
        self._inject_node_manager(core)
        saved = core._get_save_data()  # pylint: disable=W0212
        core._apply_load_data(saved)  # pylint: disable=W0212
        self.test_hex_grid_view.call_params.clear()
        core.draw()
        expected = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS,
            self.INITIAL_TYPES,
        )
        self.assertEqual(expected, self.test_hex_grid_view.call_params)

    def test_get_save_data_includes_placed_edge(self):
        """エッジ配置後に save → load すると同じ道描画が再現されること"""
        core = GameCore()
        self._inject_node_manager(core)
        core._edge_manager.place_edge((3, 0), (4, 0))  # pylint: disable=W0212
        saved = core._get_save_data()  # pylint: disable=W0212
        core._apply_load_data(saved)  # pylint: disable=W0212
        self.test_hex_grid_view.call_params.clear()
        core.draw()
        expected = (
            self._grid_draw_calls()
            + self._edge_draw_calls((3, 0), (4, 0))
            + self._node_draw_calls(
                self.FIXED_POSITIONS,
                self.INITIAL_TYPES,
            )
        )
        self.assertEqual(expected, self.test_hex_grid_view.call_params)

    def test_apply_load_data_with_edges_restores_edge_drawing(self):
        """_apply_load_data() でエッジが復元され draw() の道描画呼び出しに反映されること"""
        core = GameCore()
        core._apply_load_data(  # pylint: disable=W0212
            {
                "nodes": [],
                "edges": [{"start": [0, 0], "end": [2, 0], "direct": None}],
            }
        )
        self.test_hex_grid_view.call_params.clear()
        core.draw()
        expected = self._grid_draw_calls() + self._edge_draw_calls(
            (0, 0), (2, 0), edge_direct=None
        )
        self.assertEqual(expected, self.test_hex_grid_view.call_params)

    def test_save_load_roundtrip_preserves_stock_and_level(self):
        """保存・復元のラウンドトリップで production_stock / consumption_stock / growth_stock / level が維持されること"""
        core = GameCore()
        core._apply_load_data(  # pylint: disable=W0212
            {
                "nodes": [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 2},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 2,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {"TREE": 5},
                        "level": 0,
                    },
                    {
                        "col": 4,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 1},
                        "consumption_stock": {"TREE": 2},
                        "growth_stock": {"STONE": 4},
                        "level": 0,
                    },
                ],
                "edges": [],
            }
        )
        saved = core._get_save_data()  # pylint: disable=W0212

        # _get_save_data() が蓄積・レベル情報を含むこと
        forest_dict, city_dict, factory_dict = saved["nodes"]
        self.assertEqual({"TREE": 2}, forest_dict["production_stock"])
        self.assertEqual({"TREE": 5}, city_dict["growth_stock"])
        self.assertEqual(0, city_dict["level"])
        self.assertEqual({"WOOD": 1}, factory_dict["production_stock"])
        self.assertEqual({"TREE": 2}, factory_dict["consumption_stock"])
        self.assertEqual({"STONE": 4}, factory_dict["growth_stock"])

        # _apply_load_data() が蓄積・レベル情報を復元すること
        core._apply_load_data(saved)  # pylint: disable=W0212
        forest, city, factory = core._node_manager._nodes  # pylint: disable=W0212
        self.assertEqual(
            2, forest._production_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        self.assertEqual(
            5, city._growth_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        self.assertEqual(0, city.level)
        self.assertEqual(
            1, factory._production_stock[MaterialType.WOOD]  # pylint: disable=W0212
        )
        self.assertEqual(
            2, factory._consumption_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        self.assertEqual(
            4, factory._growth_stock[MaterialType.STONE]  # pylint: disable=W0212
        )


class TestGameCoreSaveTrigger(TestParent):
    """TDD サイクル 8 Red: 配置操作後の自動保存トリガー テスト"""

    # CITY 配置可能にするため CITY なしの NodeManager を注入する想定。
    # MOUNTAIN を (4,0) に置くことで test_save_triggered_after_edge_placement の (5,0)→(4,0) エッジテストを満たす。
    FIXED_POSITIONS = [(0, 0), (1, 0), (2, 0), (4, 0)]
    INITIAL_TYPES = [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1

    def _new_core(self, extra_nodes=None):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_save_triggered_after_node_placement(self):
        """ノード配置成功後（CITY / FACTORY）に保存呼び出しが発生すること"""
        city_lv1 = Node(col=7, row=0, node_type=NodeType.CITY, level=1)
        cases = [
            (PlacementMode.CITY, 5, 0, None),
            (
                PlacementMode.FACTORY,
                6,
                0,
                [city_lv1],
            ),  # factory limit=1 にするため街Lv1を注入
        ]
        for mode, col, row, extra_nodes in cases:
            with self.subTest(mode=mode.name):
                core = self._new_core(extra_nodes=extra_nodes)
                initial_save_count = self.mock_store.save.call_count
                self._activate_button(core, mode)
                self._double_tap(core, col, row)
                self.assertGreater(
                    self.mock_store.save.call_count,
                    initial_save_count,
                )

    def test_save_triggered_after_edge_placement(self):
        """エッジ配置成功後（EDGE モードで 2 ノード確定）に保存呼び出しが発生すること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # CITY を配置（エッジ要件: 片方が CITY/FACTORY）
        initial_save_count = self.mock_store.save.call_count
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)  # CITY ノード確定
        self._double_tap(core, 4, 0)  # MOUNTAIN ノード確定 → エッジ作成
        self.assertGreater(self.mock_store.save.call_count, initial_save_count)

    def test_save_triggered_after_node_deletion(self):
        """ノード削除成功後（DELETE_NODE モード）に保存呼び出しが発生すること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # CITY ノードを配置
        initial_save_count = self.mock_store.save.call_count
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._double_tap(core, 5, 0)  # CITY ノードを削除
        self.assertGreater(self.mock_store.save.call_count, initial_save_count)

    def test_save_triggered_after_edge_deletion(self):
        """エッジ削除成功後（DELETE_EDGE モード）に保存呼び出しが発生すること"""
        core = self._new_core()
        core._edge_manager.place_edge((0, 0), (2, 0))  # pylint: disable=W0212
        initial_save_count = self.mock_store.save.call_count
        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._double_tap(core, 0, 0)
        self._double_tap(core, 2, 0)  # → エッジ削除
        self.assertGreater(self.mock_store.save.call_count, initial_save_count)

    def test_save_not_triggered_after_failed_placement(self):
        """配置失敗時には保存が呼び出されないこと"""
        cases = [
            (
                "重複ノード配置（既存 FOREST ノード位置）",
                PlacementMode.CITY,
                [(0, 0), (0, 0)],
            ),
            (
                "ノードなしグリッドへのエッジ 1 つ目（EDGE モード）",
                PlacementMode.EDGE,
                [(5, 0), (5, 0)],
            ),
            (
                "経路上に別ノードがある接続（EDGE モード）",
                PlacementMode.EDGE,
                [(0, 0), (0, 0), (2, 0), (2, 0)],
            ),
        ]
        for label, mode, taps in cases:
            with self.subTest(label):
                core = self._new_core()
                initial_save_count = self.mock_store.save.call_count
                self._activate_button(core, mode)
                for tap_col, tap_row in taps:
                    self._tap_grid(core, tap_col, tap_row)
                self.assertEqual(initial_save_count, self.mock_store.save.call_count)


class TestGameCoreNodeDeletion(TestParent):
    """ID-008: ノード削除モードのテスト"""

    # CITY 配置可能にするため CITY なしの NodeManager を注入する想定。
    # FIXED_POSITIONS は TestParent デフォルト: FOREST×3:(0,0),(1,0),(2,0) / MOUNTAIN×1:(3,0)

    def _new_core(self, extra_nodes=None):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_double_tap_in_delete_mode_removes_node_and_deactivates_button(self):
        """DELETE_NODE モードで CITY ノードをダブルタップするとノードが描画から消えてボタンが非アクティブになること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # CITY ノードを配置
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._double_tap(core, 5, 0)  # CITY ノード (5,0) を削除
        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS, self.INITIAL_TYPES
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(self._button_view_calls(None), self.test_view.call_params)

    def test_delete_node_also_removes_connected_edges(self):
        """DELETE_NODE モードで CITY ノードを削除すると接続エッジも描画から消えること"""
        # city_lv4: city_limit=2（Lv4×1）なので CITY 追加配置が可能、factory_limit=2 で FACTORY 配置も可能
        city_lv4 = Node(col=7, row=0, node_type=NodeType.CITY, level=4)
        core = self._new_core(extra_nodes=[city_lv4])
        # CITY(5,0) と FACTORY(6,0) を配置してエッジを作成
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)
        self._activate_button(core, PlacementMode.FACTORY)
        self._double_tap(core, 6, 0)
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 5, 0)
        self._double_tap(core, 6, 0)
        # ノード (5,0) と接続エッジを削除
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._double_tap(core, 5, 0)
        remaining_positions = self.FIXED_POSITIONS + [(7, 0), (6, 0)]
        remaining_types = self.INITIAL_TYPES + [NodeType.CITY, NodeType.FACTORY]
        remaining_levels = [0] * len(self.INITIAL_TYPES) + [4, 0]
        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            remaining_positions, remaining_types, remaining_levels
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        # CITY(5,0)削除後: 街Lv4×1残存 → city_count=1（city_limit=2）、工場1個 → factory_count=1（factory_limit=2）
        self.assertEqual(
            self._button_view_calls(None, city_count=1, factory_count=1),
            self.test_view.call_params,
        )

    def test_double_tap_on_non_deletable_node_in_delete_mode_does_nothing(self):
        """DELETE_NODE モードで FOREST・MOUNTAIN をダブルタップしてもノードが消えずボタンがアクティブのままであること"""
        cases = [
            ("FOREST ノードは削除不可", 0, 0),
            ("MOUNTAIN ノードは削除不可", 3, 0),
        ]
        for label, col, row in cases:
            with self.subTest(label):
                core = self._new_core()
                self._activate_button(core, PlacementMode.DELETE_NODE)
                self._double_tap(core, col, row)
                expected_hex = self._grid_draw_calls() + self._node_draw_calls(
                    self.FIXED_POSITIONS, self.INITIAL_TYPES
                )
                self.assertEqual(expected_hex, self._draw_calls(core))
                self.assertEqual(
                    self._button_view_calls(PlacementMode.DELETE_NODE),
                    self.test_view.call_params,
                )

    def test_double_tap_on_empty_grid_in_delete_mode_does_nothing(self):
        """DELETE_NODE モードで空グリッドをダブルタップすると描画が変化しないこと"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._double_tap(core, 5, 0)  # ノードなし
        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS, self.INITIAL_TYPES
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.DELETE_NODE),
            self.test_view.call_params,
        )


class TestGameCoreDeleteHighlight(TestParent):
    """DELETE_NODE モード時のハイライト表示テスト"""

    # CITY 配置可能にするため CITY なしの NodeManager を注入する想定。
    # FIXED_POSITIONS は TestParent デフォルト: FOREST×3:(0,0),(1,0),(2,0) / MOUNTAIN×1:(3,0)

    def _new_core(self):
        """CITY なしの NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core)
        return core

    def test_highlighted_when_tapping_deletable_node_in_delete_mode(self):
        """DELETE_NODE モードで CITY ノードをシングルタップすると HIGHLIGHTED になること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # CITY ノードを配置
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._tap_grid(core, 5, 0)  # CITY ノードあり
        placed_positions = self.FIXED_POSITIONS + [(5, 0)]
        placed_types = self.INITIAL_TYPES + [NodeType.CITY]
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 5, 0, GridType.HIGHLIGHTED)]
            + self._node_draw_calls(placed_positions, placed_types)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_when_tapping_non_deletable_node_in_delete_mode(self):
        """DELETE_NODE モードで FOREST・MOUNTAIN ノードをシングルタップすると FAIL_HIGHLIGHTED になること"""
        cases = [
            ("FOREST ノードは削除不可", 0, 0),
            ("MOUNTAIN ノードは削除不可", 3, 0),
        ]
        for label, col, row in cases:
            with self.subTest(label):
                core = self._new_core()
                self._activate_button(core, PlacementMode.DELETE_NODE)
                self._tap_grid(core, col, row)
                expected_hex = (
                    self._grid_draw_calls()
                    + [("draw_grid", col, row, GridType.FAIL_HIGHLIGHTED)]
                    + self._node_draw_calls(self.FIXED_POSITIONS, self.INITIAL_TYPES)
                )
                self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_when_tapping_empty_grid_in_delete_mode(self):
        """DELETE_NODE モードでノードのないグリッドをシングルタップすると FAIL_HIGHLIGHTED になること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.DELETE_NODE)
        self._tap_grid(core, 5, 0)  # ノードなし
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 5, 0, GridType.FAIL_HIGHLIGHTED)]
            + self._node_draw_calls(self.FIXED_POSITIONS, self.INITIAL_TYPES)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))


class TestGameCoreEdgePlacementRestriction(TestParent):
    """両端とも非 CITY/FACTORY のエッジ設置禁止テスト"""

    # (0,0) と (1,0) を空きにして CITY/FACTORY 配置可能にする
    FIXED_POSITIONS = [(0, 1), (3, 0), (4, 0), (5, 0)]
    INITIAL_TYPES = [NodeType.FOREST] * 3 + [NodeType.MOUNTAIN] * 1

    def _new_core(self, extra_nodes=None):
        """NodeManager を注入した GameCore を返す"""
        core = GameCore()
        self._inject_node_manager(core, extra_nodes=extra_nodes)
        return core

    def test_edge_placement_scenarios(self):
        """CITY/FACTORY 接続制約のエッジ設置シナリオテスト"""
        city_factory = [
            Node(col=0, row=0, node_type=NodeType.CITY),
            Node(col=1, row=0, node_type=NodeType.FACTORY),
        ]
        cases = [
            # (label, extra_nodes, start, end, expected_edge)
            # expected_edge=None はエッジが設置されないことを意味する
            (
                "CITY-FACTORY 間のエッジが描画されること",
                city_factory,
                (0, 0),
                (1, 0),
                ((0, 0), (1, 0)),
            ),
            (
                "CITY→FOREST のエッジが描画されること（片方が CITY なので許可）",
                city_factory,
                (0, 0),
                (0, 1),
                ((0, 0), (0, 1)),
            ),
            (
                "両端とも非 CITY/FACTORY のエッジ設置が拒否されエッジが描画されないこと",
                None,
                (3, 0),
                (4, 0),
                None,
            ),
        ]
        for label, extra_nodes, start, end, expected_edge in cases:
            with self.subTest(label):
                core = self._new_core(extra_nodes=extra_nodes)
                self._activate_button(core, PlacementMode.EDGE)
                self._double_tap(core, *start)
                self._double_tap(core, *end)
                extra_positions = (
                    [(n.col, n.row) for n in extra_nodes] if extra_nodes else []
                )
                extra_types = [n.node_type for n in extra_nodes] if extra_nodes else []
                edge_calls = (
                    self._edge_draw_calls(*expected_edge)
                    if expected_edge is not None
                    else []
                )
                expected_hex = (
                    self._grid_draw_calls()
                    + edge_calls
                    + self._node_draw_calls(
                        self.FIXED_POSITIONS + extra_positions,
                        self.INITIAL_TYPES + extra_types,
                    )
                )
                self.assertEqual(expected_hex, self._draw_calls(core))

    def test_fail_highlighted_when_both_endpoints_are_non_city_factory(self):
        """EDGE モードで始点・終点ともに非 CITY/FACTORY の場合は FAIL_HIGHLIGHTED になること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.EDGE)
        self._double_tap(core, 3, 0)  # FOREST 始点確定
        self._tap_grid(core, 4, 0)  # FOREST 終点候補タップ
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 3, 0, GridType.SELECTED)]
            + [("draw_grid", 4, 0, GridType.FAIL_HIGHLIGHTED)]
            + self._node_draw_calls(self.FIXED_POSITIONS, self.INITIAL_TYPES)
        )
        self.assertEqual(expected_hex, self._draw_calls(core))


class TestDrawEdgeSegmentsFlow(TestParent):
    """MaterialFlow 実行後のエッジ flow 方向が描画に正しく反映されることを検証するテスト"""

    def _make_core_with_tick(self, load_data):
        """指定した初期データで GameCore を作り、tick を発火させて MaterialFlow を実行"""
        self.mock_store.load.return_value = load_data
        core = GameCore()
        core._tick_clock.is_up = MagicMock(return_value=True)  # pylint: disable=W0212
        core._save_clock.is_up = MagicMock(return_value=False)  # pylint: disable=W0212
        core.update()
        return core

    def test_flow_direction_reflected_in_draw_calls(self):
        """MaterialFlow 実行後のエッジ flow 方向が描画に正しく反映されること"""
        start, end = (0, 0), (1, 0)
        cases = [
            (
                "FORWARD: FOREST(start)→FACTORY(end) で転送",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                EdgeDirect.FORWARD,
                [NodeType.FOREST, NodeType.FACTORY],
            ),
            (
                "BACKWARD: FOREST(end)→FACTORY(start) で転送",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                EdgeDirect.BACKWARD,
                [NodeType.FACTORY, NodeType.FOREST],
            ),
            (
                "None: FACTORY 消費庫が満杯で転送なし",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 10},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                None,
                [NodeType.FOREST, NodeType.FACTORY],
            ),
        ]
        for label, nodes, expected_direct, node_types in cases:
            with self.subTest(label):
                core = self._make_core_with_tick(
                    {
                        "nodes": nodes,
                        "edges": [{"start": [0, 0], "end": [1, 0], "direct": None}],
                    }
                )
                expected_hex = (
                    self._grid_draw_calls()
                    + self._edge_draw_calls(start, end, expected_direct)
                    + self._node_draw_calls([start, end], node_types)
                )
                self.assertEqual(expected_hex, self._draw_calls(core))


class TestPopup(TestParent):
    """ポップアップ開閉・描画のテスト"""

    def setUp(self):
        super().setUp()
        self.mock_store.load.return_value = {
            "nodes": [
                {
                    "col": 2,
                    "row": 3,
                    "type": "CITY",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
            ],
            "edges": [],
        }
        self.core = GameCore()

    def _popup_frame_calls(self):
        """CITY lv0 ポップアップの期待描画呼び出し（新仕様: TREE のみ 0/15）"""
        cx = GameCore.POPUP_X + GameCore.POPUP_PADDING
        cy = GameCore.POPUP_Y + GameCore.POPUP_PADDING
        div_x = GameCore.POPUP_X + GameCore.POPUP_PADDING
        div_w = GameCore.POPUP_W - 2 * GameCore.POPUP_PADDING
        s2x = GameCore.POPUP_SECTION2_X
        s2y = GameCore.POPUP_SECTION2_Y
        sx = GameCore.POPUP_SECTION2_SLASH_X
        tr = GameCore.POPUP_SECTION2_TEXT_RIGHT_X
        cw = GameCore.CHAR_W
        tree_cur, tree_lim = "0", "15"
        return [
            (
                "draw_rect",
                GameCore.POPUP_X,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                GameCore.POPUP_BG_COL,
            ),
            (
                "draw_rectb",
                GameCore.POPUP_X,
                GameCore.POPUP_Y,
                GameCore.POPUP_W,
                GameCore.POPUP_H,
                GameCore.POPUP_BORDER_COL,
            ),
            ("draw_blt", cx, cy, 1, 8, 0, 16, 16, 0),
            ("draw_text", cx + 20, cy + 4, "CITY Lv.0"),
            (
                "draw_rect",
                div_x,
                GameCore.POPUP_HEADER_DIVIDER_Y,
                div_w,
                1,
                GameCore.POPUP_BORDER_COL,
            ),
            (
                "draw_rect",
                div_x,
                GameCore.POPUP_DIVIDER_Y,
                div_w,
                1,
                GameCore.POPUP_BORDER_COL,
            ),
            ("draw_blt", s2x, s2y, 2, 8, 0, 8, 8, 0),
            ("draw_text", sx - len(tree_cur) * cw - cw, s2y, tree_cur),
            ("draw_text", sx, s2y, "/"),
            ("draw_text", tr - len(tree_lim) * cw, s2y, tree_lim),
        ]

    def test_double_tap_node_opens_popup(self):
        """NO_MODE でノードをダブルタップするとポップアップが開き、draw() でボタン後に描画される"""
        self._tap_grid(self.core, 2, 3)  # 1回目: ハイライト
        self._tap_grid(self.core, 2, 3)  # 2回目: rule 4 発火 → ポップアップ開く
        self.assertEqual(self.core._popup_node.col, 2)  # pylint: disable=W0212
        self.assertEqual(self.core._popup_node.row, 3)  # pylint: disable=W0212
        self.test_view.call_params.clear()
        self.core.draw()
        # setUp で CITY×1 配置済み → city_count=0
        self.assertEqual(
            self.test_view.call_params,
            self._button_view_calls(city_count=0) + self._popup_frame_calls(),
        )

    def test_double_tap_empty_grid_does_not_open_popup(self):
        """ノードが存在しないグリッドをダブルタップしても draw() の IView 呼び出しはボタン描画のみ"""
        self._tap_grid(self.core, 0, 0)
        self._tap_grid(self.core, 0, 0)
        self.test_view.call_params.clear()
        self.core.draw()
        # setUp で CITY×1 配置済み → city_count=0
        self.assertEqual(
            self.test_view.call_params, self._button_view_calls(city_count=0)
        )

    def test_any_click_closes_popup(self):
        """ポップアップ表示中に画面をクリックするとポップアップが閉じ、draw() でポップアップが描画されない"""
        city_btn = self.core._buttons[PlacementMode.CITY]  # pylint: disable=W0212
        cases = [
            (
                "領域内",
                GameCore.POPUP_X + GameCore.POPUP_W // 2,
                GameCore.POPUP_Y + GameCore.POPUP_H // 2,
            ),
            ("領域外", 0, 0),  # 左上隅（ポップアップ外・ボタン外）
            (
                "ボタン領域",
                city_btn.x + city_btn.width // 2,
                city_btn.y + city_btn.height // 2,
            ),
        ]
        for label, px, py in cases:
            with self.subTest(label):
                self._tap_grid(self.core, 2, 3)
                self._tap_grid(self.core, 2, 3)

                self.test_input.set_pressed(px, py)
                self.core.update()
                self.test_input.clear()

                self.test_view.call_params.clear()
                self.core.draw()
                # setUp で CITY×1 配置済み → city_count=0
                self.assertEqual(
                    self.test_view.call_params,
                    self._button_view_calls(city_count=0),
                )


class TestClock(TestParent):
    def setUp(self):
        super().setUp()
        self.patcher_clock.stop()

    def tearDown(self):
        self.patcher_clock.start()
        super().tearDown()

    @patch.object(time, "perf_counter")
    def test_is_up(self, mock):
        test_cases = [
            ("1 sec", [False, True, False, True], 1000),
            ("1.1 sec", [False, False, True, False, False, True], 1100),
            ("always", [True, True, True, True, True, True], 1),
            ("never", [False, False, False, False, False, False], 0),
        ]
        for case_name, expected_list, count_ms in test_cases:
            with self.subTest(
                case_name=case_name, expected_list=expected_list, count_ms=count_ms
            ):
                self.setUp()
                mock.side_effect = [i * 0.5 for i in range(10)]
                clock = Clock(count_ms)
                for expected in expected_list:
                    self.assertEqual(expected, clock.is_up())
                self.tearDown()


class TestGameCoreMaterialFlowTick(TestParent):
    def setUp(self):
        super().setUp()
        self.mock_store.load.return_value = {
            "nodes": [
                {
                    "col": 0,
                    "row": 0,
                    "type": "FOREST",
                    "production_stock": {"TREE": 0},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
            ],
            "edges": [],
        }

    def _make_core(self, tick_up=False, save_up=False):
        """tick/save clock の is_up 戻り値を指定して GameCore を作る"""
        core = GameCore()
        core._tick_clock.is_up = MagicMock(  # pylint: disable=W0212
            return_value=tick_up
        )
        core._save_clock.is_up = MagicMock(  # pylint: disable=W0212
            return_value=save_up
        )
        self.mock_store.save.reset_mock()
        return core

    def _forest_node(self, core):
        return core._node_manager.get_node(0, 0)  # pylint: disable=W0212

    def test_forest_production_stock_increases_when_tick_fires(self):
        """tick clock が True のとき FOREST ノードの production_stock[TREE] が rate=3 になる"""
        core = self._make_core(tick_up=True)
        core.update()
        self.assertEqual(
            self._forest_node(core).get_production_stock(MaterialType.TREE), 3
        )

    def test_forest_production_stock_unchanged_when_tick_not_fired(self):
        """tick clock が False のとき FOREST ノードの production_stock は変化しない"""
        core = self._make_core(tick_up=False)
        core.update()
        self.assertEqual(
            self._forest_node(core).get_production_stock(MaterialType.TREE), 0
        )

    def test_save_called_when_save_clock_fires(self):
        """save clock が True のとき _report_store.save() が呼ばれる"""
        core = self._make_core(save_up=True)
        core.update()
        self.mock_store.save.assert_called_once()

    def test_save_not_called_when_save_clock_not_fired(self):
        """save clock が False のとき _report_store.save() は呼ばれない"""
        core = self._make_core(tick_up=True, save_up=False)
        core.update()
        self.mock_store.save.assert_not_called()

    def test_tick_and_save_are_independent(self):
        """tick が発火しても save は走らない（tick と save の独立性）"""
        core = self._make_core(tick_up=True, save_up=False)
        core.update()
        self.assertEqual(
            self._forest_node(core).get_production_stock(MaterialType.TREE), 3
        )
        self.mock_store.save.assert_not_called()


class TestGameCoreButtonIntegration(TestParent):
    """TDD サイクル 4: count=0 ボタンの無効化クリック統合テスト"""

    # --- クリック制御 ---

    def test_disabled_button_click_does_not_activate(self):
        # CITY 配置後（city_count=0）に CITY ボタンをクリックしても描画で active にならない
        core = GameCore()
        self._inject_node_manager(core)
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # city_count=0 になる
        self._activate_button(core, PlacementMode.CITY)  # disabled クリック
        self.test_view.call_params.clear()
        core.draw()
        self.assertEqual(
            self._button_view_calls(active_mode=None, city_count=0, factory_count=0),
            self.test_view.call_params,
        )

    def test_disabled_button_click_does_not_deactivate_other_buttons(self):
        # EDGE active かつ city_count=0 の状態で CITY をクリックしても EDGE active のまま描画される
        core = GameCore()
        self._inject_node_manager(core)
        self._activate_button(core, PlacementMode.CITY)
        self._double_tap(core, 5, 0)  # city_count=0 になる
        self._activate_button(core, PlacementMode.EDGE)
        self._activate_button(core, PlacementMode.CITY)  # disabled クリック
        self.test_view.call_params.clear()
        core.draw()
        self.assertEqual(
            self._button_view_calls(
                active_mode=PlacementMode.EDGE, city_count=0, factory_count=0
            ),
            self.test_view.call_params,
        )


class TestDeleteEdgeMode(TestParent):
    """TDD サイクル 5: DELETE_EDGE モードの統合テスト"""

    def _new_core(self):
        core = GameCore()
        self._inject_node_manager(core)
        return core

    def test_delete_edge_removes_existing_edge(self):
        """DELETE_EDGE モードで2ノードをダブルタップすると存在するエッジが削除されボタンが非アクティブになること"""
        core = self._new_core()
        core._edge_manager.place_edge((0, 0), (2, 0))  # pylint: disable=W0212

        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._double_tap(core, 0, 0)
        self._double_tap(core, 2, 0)  # → エッジ削除

        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS, self.INITIAL_TYPES
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(self._button_view_calls(None), self.test_view.call_params)

    def test_delete_edge_no_edge_between_selected_nodes_is_noop(self):
        """DELETE_EDGE モードでエッジのない2ノードを選択してもエッジが描画されずボタンがアクティブのままであること"""
        core = self._new_core()

        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._double_tap(core, 0, 0)
        self._double_tap(core, 2, 0)

        expected_hex = self._grid_draw_calls() + self._node_draw_calls(
            self.FIXED_POSITIONS, self.INITIAL_TYPES
        )
        self.assertEqual(expected_hex, self._draw_calls(core))
        self.assertEqual(
            self._button_view_calls(PlacementMode.DELETE_EDGE),
            self.test_view.call_params,
        )


class TestTappedHighlightDeleteEdge(TestParent):
    """TDD サイクル 6: _tapped_highlight_type の DELETE_EDGE 分岐テスト"""

    def _new_core(self):
        core = GameCore()
        self._inject_node_manager(core)
        return core

    def test_delete_edge_no_node_at_tapped_is_fail_highlighted(self):
        """DELETE_EDGE モードで空グリッドをタップすると FAIL_HIGHLIGHTED になること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._tap_grid(core, 5, 5)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 5, 5, GridType.FAIL_HIGHLIGHTED)]
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_delete_edge_step2_no_edge_between_nodes_is_fail_highlighted(self):
        """DELETE_EDGE モードのステップ2で接続なし2ノードをタップすると経路全体が FAIL_HIGHLIGHTED になること"""
        core = self._new_core()
        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._double_tap(core, 0, 0)
        self._tap_grid(core, 2, 0)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 0, 0, GridType.SELECTED)]
            + self._route_fail_calls((0, 0), (2, 0))
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))

    def test_delete_edge_step2_existing_edge_is_highlighted(self):
        """DELETE_EDGE モードのステップ2でエッジが存在する2つ目ノードをタップすると HIGHLIGHTED になること"""
        core = self._new_core()
        core._edge_manager.place_edge((0, 0), (2, 0))  # pylint: disable=W0212
        self._activate_button(core, PlacementMode.DELETE_EDGE)
        self._double_tap(core, 0, 0)
        self._tap_grid(core, 2, 0)
        expected_hex = (
            self._grid_draw_calls()
            + [("draw_grid", 0, 0, GridType.SELECTED)]
            + self._route_preview_calls((0, 0), (2, 0))
            + self._edge_draw_calls((0, 0), (2, 0))
            + self._initial_node_calls()
        )
        self.assertEqual(expected_hex, self._draw_calls(core))


class TestGameClearPopup(TestParent):
    """TDD サイクル 2: CLEAR ポップアップ自動表示・描画・操作無効化テスト"""

    def _make_clear_core(self):
        """Lv4 街3つを持つ GameCore を生成"""
        core = GameCore()
        core._node_manager = NodeManager(  # pylint: disable=W0212
            nodes=[
                Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                Node(col=1, row=0, node_type=NodeType.CITY, level=4),
                Node(col=2, row=0, node_type=NodeType.CITY, level=4),
            ]
        )
        return core

    def _clear_popup_view_calls(self):
        """CLEAR ポップアップの期待 IView 呼び出しリストを返す"""
        G = GameCore
        cx = G.CLEAR_POPUP_X
        cy = G.CLEAR_POPUP_Y
        cw = G.CLEAR_POPUP_W
        ch = G.CLEAR_POPUP_H
        text1 = "CLEAR"
        tx1 = cx + (cw - len(text1) * G.CHAR_W) // 2
        ty1 = cy + ch // 2 - 9
        text2 = "click to restart"
        tx2 = cx + (cw - len(text2) * G.CHAR_W) // 2
        ty2 = cy + ch // 2 + 4
        return [
            ("draw_rect", cx, cy, cw, ch, G.POPUP_BG_COL),
            ("draw_rectb", cx, cy, cw, ch, G.POPUP_BORDER_COL),
            ("draw_text", tx1, ty1, text1),
            ("draw_text", tx2, ty2, text2),
        ]

    def _view_calls_after_draw(self, core):
        """core.draw() 後の IView 呼び出しリストを返す"""
        self.test_view.call_params.clear()
        core.draw()
        return self.test_view.call_params[:]

    def _enter_clear_state(self, core):
        """tick を発火させてクリア状態に遷移させる（process()はモックしてLv4を維持）"""
        with patch.object(core._material_flow, "process"):  # pylint: disable=W0212
            with patch.object(
                core._tick_clock, "is_up", return_value=True
            ):  # pylint: disable=W0212
                core.update()

    def test_clear_popup_not_drawn_when_two_lv4_cities(self):
        """Lv4 街が2つでは CLEAR ポップアップが描画されないこと"""
        core = GameCore()
        core._node_manager = NodeManager(  # pylint: disable=W0212
            nodes=[
                Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                Node(col=1, row=0, node_type=NodeType.CITY, level=4),
            ]
        )
        self._enter_clear_state(core)  # tick 発火 → is_game_clear() は False
        # Lv4×2: city_limit=3, 配置数2 → available=1, factory=2×2=4
        expected = self._button_view_calls(city_count=1, factory_count=4)
        self.assertEqual(expected, self._view_calls_after_draw(core))

    def test_clear_popup_overrides_node_popup(self):
        """ノードポップアップ表示中にゲームクリアになったとき、クリアポップアップのみ描画されること"""
        core = self._make_clear_core()
        core._popup_node = Node(  # pylint: disable=W0212
            col=0, row=0, node_type=NodeType.FOREST, level=0
        )
        self._enter_clear_state(core)  # tick 発火 → クリア状態へ
        expected = (
            self._button_view_calls(city_count=0, factory_count=6)
            + self._clear_popup_view_calls()
        )
        self.assertEqual(expected, self._view_calls_after_draw(core))

    def test_clear_state_draws_popup_and_blocks_all_input(self):
        """Lv4 街3つのとき: CLEARポップアップが全描画され、ボタンとグリッドへの入力が無効になること"""
        core = self._make_clear_core()
        self._enter_clear_state(core)  # tick 発火 → クリア状態へ

        # ① CLEAR ポップアップが全描画されること
        expected = (
            self._button_view_calls(city_count=0, factory_count=6)
            + self._clear_popup_view_calls()
        )
        self.assertEqual(expected, self._view_calls_after_draw(core))

        # ② ボタンクリックが無効になること（DELETE_NODE: カウント制限なし）
        btn = core._buttons[PlacementMode.DELETE_NODE]  # pylint: disable=W0212
        self.test_input.set_pressed(btn.x + btn.width // 2, btn.y + btn.height // 2)
        core.update()
        active_modes = [
            m for m, b in core._buttons.items() if b.is_active
        ]  # pylint: disable=W0212
        self.assertEqual([], active_modes)

        # ③ グリッドタップが無効になること
        self.test_input.clear()
        self.test_grid_input.set_clicked_grid(5, 5)
        core.update()
        self.assertIsNone(core._grid_selection.tapped_grid)  # pylint: disable=W0212

    def _edge_draw_calls_after_draw(self, core):
        """core.draw() 後の draw_edge 呼び出しリストを返す"""
        self.test_hex_grid_view.call_params.clear()
        core.draw()
        return [c for c in self.test_hex_grid_view.call_params if c[0] == "draw_edge"]

    def test_flow_direction_reflected_in_draw_calls(self):
        """クリア状態でも EdgeDirect が draw_edge の flow に反映されること"""
        core = self._make_clear_core()
        edge = Edge(start=(0, 0), end=(1, 0))
        edge.set_direct(EdgeDirect.FORWARD)
        core._edge_manager._edges.append(edge)  # pylint: disable=W0212
        self._enter_clear_state(core)
        self.assertEqual(
            self._edge_draw_calls_after_draw(core),
            [
                ("draw_edge", 0, 0, GridDirect.R, EdgeFlow.OUTWARD),
                ("draw_edge", 1, 0, GridDirect.L, EdgeFlow.INWARD),
            ],
        )


class TestGameClearReset(TestParent):
    """TDD サイクル 3: クリアポップアップクリックで保存データ初期化・再開始テスト"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_pyxel.start()
        from src.main import App as _App  # pylint: disable=C0415

        self.app_class = _App

    def tearDown(self):
        self.patcher_pyxel.stop()
        super().tearDown()

    def _make_clear_core(self):
        """Lv4 街3つを持つ GameCore を生成"""
        core = GameCore()
        core._node_manager = NodeManager(  # pylint: disable=W0212
            nodes=[
                Node(col=0, row=0, node_type=NodeType.CITY, level=4),
                Node(col=1, row=0, node_type=NodeType.CITY, level=4),
                Node(col=2, row=0, node_type=NodeType.CITY, level=4),
            ]
        )
        return core

    def _enter_clear_state(self, core):
        """tick を発火させてクリア状態に遷移させる（process()はモックしてLv4を維持）"""
        with patch.object(core._material_flow, "process"):  # pylint: disable=W0212
            with patch.object(
                core._tick_clock, "is_up", return_value=True
            ):  # pylint: disable=W0212
                core.update()

    def _click_popup_center(self):
        """CLEAR ポップアップの中央をクリックする"""
        self.test_input.set_pressed(
            GameCore.CLEAR_POPUP_X + GameCore.CLEAR_POPUP_W // 2,
            GameCore.CLEAR_POPUP_Y + GameCore.CLEAR_POPUP_H // 2,
        )

    def test_needs_reset_initial_value_is_false(self):
        """GameCore の初期状態で needs_reset が False を返すこと"""
        core = GameCore()
        self.assertFalse(core.needs_reset)

    def test_clear_popup_click_sets_needs_reset(self):
        """クリアポップアップ表示中のクリックで needs_reset が True になること"""
        core = self._make_clear_core()
        self._enter_clear_state(core)
        self._click_popup_center()
        core.update()
        self.assertTrue(core.needs_reset)

    def test_app_recreates_game_core_without_loading_on_needs_reset(self):
        """App は needs_reset のとき GameCore を再生成し、保存データを読み込まないこと"""
        app = self.app_class()
        for _ in range(self.app_class.LOAD_WAIT_FRAMES):
            app.update()
        original_core = app._core  # pylint: disable=W0212
        load_count_before = self.mock_store.load.call_count
        original_core._needs_reset = True  # pylint: disable=W0212
        app.update()
        self.assertIsNot(app._core, original_core)  # pylint: disable=W0212
        self.assertEqual(load_count_before, self.mock_store.load.call_count)
