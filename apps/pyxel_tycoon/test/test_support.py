import json
import unittest
from unittest.mock import patch

from src.main import (
    Color,
    GameObject,
    IInput,
    InstructionKind,
    Instruction,
    IUnitView,
    IView,
    NavigationPopup,
)
from src.map_generator import AreaKind, IMapGenerator, MaterialType


class TestView(IView):
    def __init__(self):
        super().__init__(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        self.frame = 0
        self.call_params = []

    def draw_text(self, x, y, text, col=Color.WHITE):
        self.call_params.append(("draw_text", x, y, text, col))

    def draw_circ(self, x, y, r, col, is_fill):
        self.call_params.append(("draw_circ", x, y, r, col, is_fill))

    def draw_rect(self, x, y, w, h, col, is_fill):
        self.call_params.append(("draw_rect", x, y, w, h, col, is_fill))

    def draw_image(self, x, y, src_x, src_y, revert, is_trans):
        self.call_params.append(("draw_image", x, y, src_x, src_y, revert, is_trans))

    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        self.call_params.append(("draw_tri", x1, y1, x2, y2, x3, y3, col))

    def clear(self, x, y):
        self.call_params.append(("clear", x, y))

    def get_frame(self):
        return self.frame

    def get_call_params(self):
        return self.call_params

    def increment_frame(self):
        self.frame += 1

    def reset(self):
        self.frame = 0
        self.call_params = []


class TestInput(IInput):
    def __init__(self):
        self.b_is_click = False
        self.b_is_release = False
        self.mouse_pos = None

    def is_click(self):
        return self.b_is_click

    def is_release(self):
        return self.b_is_release

    def get_mouse_x(self):
        return self.mouse_pos[0]

    def get_mouse_y(self):
        return self.mouse_pos[1]

    def set_is_click(self, b_is_click):
        self.b_is_click = b_is_click

    def set_is_release(self, b_is_release):
        self.b_is_release = b_is_release

    def set_mouse_pos(self, x, y):
        self.mouse_pos = (x, y)

    def reset(self):
        self.b_is_click = False
        self.b_is_release = False
        self.mouse_pos = None


class TestUnitView(IUnitView):
    def __init__(self):
        self.call_params = []

    def draw_unit(self, x, y, image_x, image_y, face, direct, is_blinking):
        self.call_params.append(
            ("draw_unit", x, y, image_x, image_y, face, direct, is_blinking)
        )

    def get_call_params(self):
        return self.call_params

    def reset(self):
        self.call_params = []


class TestMapGenerator(IMapGenerator):  # pylint: disable=too-many-public-methods
    POWER_WEIGHT = 2
    BOSS_POWER_WEIGHT = 4

    def __init__(self):
        self.fee_zero_flg = False
        self.spawner_zero_flg = True
        self.material_zero_flg = True
        self.start_pos = (2, 2)
        self.boss_pos = (100, 100)
        self.material_type = None
        self.fee_type = MaterialType.WOOD
        self.start_materials = []
        self.workbench = None
        self.save_data = {"marker": "generator"}

    def to_save_data(self) -> dict:
        return self.save_data

    @classmethod
    def calc_area_level(cls, area_axis_x, area_axis_y):
        return max(1, 10 * (max(abs(p) for p in (area_axis_x, area_axis_y)) // 5))

    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        return (
            0 if self.fee_zero_flg else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        return self.calc_area_level(area_axis_x, area_axis_y) * self.POWER_WEIGHT

    def get_boss_power(self) -> int:
        return self.BOSS_POWER_WEIGHT

    def get_step_power_gain(self, block_lv: int, order: int, count: int) -> int:
        # 呼び出された (block_lv, order) を一意に識別できる値（count は使わない）
        return block_lv * 100 + order + 1

    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        return (
            0
            if self.spawner_zero_flg
            else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_material_num(self, area_axis_x, area_axis_y) -> int:
        return (
            0
            if self.material_zero_flg
            else self.calc_area_level(area_axis_x, area_axis_y)
        )

    def get_start_pos(self) -> tuple[int, int]:
        return self.start_pos

    def get_boss_pos(self) -> tuple[int, int]:
        return self.boss_pos

    def get_material_type(self, area_axis_x, area_axis_y):
        return self.material_type

    def get_fee_type(self, area_axis_x, area_axis_y):
        return None if self.fee_zero_flg else self.fee_type

    def get_workbench(self, area_axis_x, area_axis_y):
        return self.workbench

    def get_start_materials(self):
        return self.start_materials

    def find_nearest_area(self, block_lv, kind, base_pos):
        return base_pos

    def is_area_kind(self, block_lv, kind, pos):
        return False

    def get_block_lv(self, area_axis_x, area_axis_y):
        return 0

    def set_fee_ret_zero(self, flg):
        self.fee_zero_flg = flg

    def set_spawner_ret_zero(self, flg):
        self.spawner_zero_flg = flg

    def set_material_ret_zero(self, flg):
        self.material_zero_flg = flg

    def set_start_pos(self, pos):
        self.start_pos = pos

    def set_boss_pos(self, pos):
        self.boss_pos = pos

    def set_material_type(self, material_type):
        self.material_type = material_type

    def set_fee_type(self, fee_type):
        self.fee_type = fee_type

    def set_start_materials(self, materials):
        self.start_materials = materials

    def set_workbench(self, workbench):
        self.workbench = workbench

    def reset(self):
        self.fee_zero_flg = False
        self.spawner_zero_flg = True
        self.material_zero_flg = True
        self.start_pos = (2, 2)
        self.boss_pos = (100, 100)
        self.material_type = None
        self.fee_type = MaterialType.WOOD
        self.start_materials = []
        self.workbench = None


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "src.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "src.main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()

    def reset(self):
        self.test_view.reset()
        self.test_input.reset()


class TestNavigator:
    """Navigator のテストダブル。送られたイベントを記録し、表示中の指示 current を
    差し替えられる（U8）。既定は Tree のエリアの開放"""

    DEFAULT_INSTRUCTION = Instruction(InstructionKind.UNVEIL, AreaKind.TREE, 0, (3, 2))

    def __init__(self):
        self.events = []
        self.current = self.DEFAULT_INSTRUCTION
        self.cleared = []

    def set_current(self, current):
        self.current = current

    def set_cleared(self, cleared):
        """次の notify が返す、今回クリアした指示の添字のリストを差し替える"""
        self.cleared = cleared

    def notify(self, event):
        self.events.append(event)
        return self.cleared

    def to_save_data(self) -> dict:
        return {"marker": "navigator"}

    def reset(self):
        self.events = []
        self.current = self.DEFAULT_INSTRUCTION
        self.cleared = []


class TestSaveStore:
    """SaveStore のテストダブル。save された保存データを JSON を往復して記録し、
    load() はその最新の保存データを返す（保存データが JSON にできることも確かめる）"""

    def __init__(self, stored=None):
        self.stored = stored
        self.save_calls = []
        self.load_count = 0

    def save(self, data):
        self.stored = json.loads(json.dumps(data))
        self.save_calls.append(self.stored)
        return True

    def load(self):
        self.load_count += 1
        return self.stored


class TestUnitParent(TestParent):
    def setUp(self):
        super().setUp()
        self.test_unit_view = TestUnitView()
        self.patcher_unit_view = patch(
            "src.main.PyxelUnitView.create",
            return_value=self.test_unit_view,
        )
        self.mock_unit_view = self.patcher_unit_view.start()
        self.test_map_generator = TestMapGenerator()
        self.patcher_map_generator = patch(
            "src.map_generator.AreaBlockAlgorithmGenerator.create",
            return_value=self.test_map_generator,
        )
        self.mock_map_generator = self.patcher_map_generator.start()
        self.test_navigator = TestNavigator()
        self.patcher_navigator = patch(
            "src.main.Navigator.create",
            return_value=self.test_navigator,
        )
        self.mock_navigator = self.patcher_navigator.start()
        # シングルトンの状態がテスト間で漏れないよう、テストごとに新しい本物を返す
        self.navigation_popup = NavigationPopup()
        self.patcher_popup = patch(
            "src.main.NavigationPopup.create",
            return_value=self.navigation_popup,
        )
        self.mock_popup = self.patcher_popup.start()

    def tearDown(self):
        super().tearDown()
        self.patcher_unit_view.stop()
        self.patcher_map_generator.stop()
        self.patcher_navigator.stop()
        self.patcher_popup.stop()

    def reset(self):
        super().reset()
        self.test_unit_view.reset()
        self.test_map_generator.reset()
        self.test_navigator.reset()
        self.navigation_popup = NavigationPopup()
        self.mock_popup.return_value = self.navigation_popup
