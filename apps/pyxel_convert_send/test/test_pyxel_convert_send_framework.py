import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from framework import (  # pylint: disable=C0413
    IView,
    IFieldView,
    IInput,
)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_tilemap(self):
        self.call_params.append("draw_tilemap")

    def draw_image(self, x, y, src_tile_x, src_tile_y, direct):
        self.call_params.append(("draw_image", x, y, src_tile_x, src_tile_y, direct))

    def draw_rect(self, x, y, width, height, color, is_fill):
        self.call_params.append(("draw_rect", x, y, width, height, color, is_fill))

    def clear(self):
        self.call_params.append("clear")

    def set_clip(self, rect):
        self.call_params.append(("set_clip", rect))

    def set_pal(self, params):
        self.call_params.append(("set_pal", params))

    def get_call_params(self):
        return self.call_params


class TestFieldView(IFieldView, TestView):
    def __init__(self):
        super().__init__()
        self.call_params = []

    def draw_node(self, tile_x, tile_y, node, direct, color):
        self.call_params.append(("draw_node", tile_x, tile_y, node, direct, color))

    def draw_object(self, x, y, image, color):
        self.call_params.append(("draw_object", x, y, image, color))

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    def __init__(self):
        self.b_is_click = False
        self.mouse_pos = None

    def is_click(self):
        return self.b_is_click

    def get_mouse_x(self):
        return self.mouse_pos[0]

    def get_mouse_y(self):
        return self.mouse_pos[1]

    def set_is_click(self, b_is_click):
        self.b_is_click = b_is_click

    def set_mouse_pos(self, x, y):
        self.mouse_pos = (x, y)


class TestParent(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.test_view = TestView()
        self.patcher_view = patch(
            "framework.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "framework.PyxelInput.create",
            return_value=self.test_input,
        )
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        super().tearDown()
        self.patcher_view.stop()
        self.patcher_input.stop()


class TestFieldParent(TestParent):
    def setUp(self):
        super().setUp()
        self.test_field_view = TestFieldView()
        self.patcher_view = patch(
            "framework.PyxelFieldView.create",
            return_value=self.test_field_view,
        )
        self.mock_view = self.patcher_view.start()

    def tearDown(self):
        super().tearDown()
        self.patcher_view.stop()
