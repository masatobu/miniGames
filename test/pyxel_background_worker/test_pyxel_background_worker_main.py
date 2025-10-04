import os
import sys
import unittest
import time
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from pyxel_background_worker.main import (  # pylint: disable=C0413
    IView,
    GameCore,
    Button,
    Color,
    IInput,
    Clock,
    Resource,
    ReportStore,
)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text, col):
        self.call_params.append(("draw_text", x, y, text, col))

    def draw_rect(self, x, y, w, h, col, is_fill):
        self.call_params.append(("draw_rect", x, y, w, h, col, is_fill))

    def clear(self):
        self.call_params.append("clear")

    def get_call_params(self):
        return self.call_params

    def reset(self):
        self.call_params = []


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

    def reset(self):
        self.b_is_click = False
        self.mouse_pos = None


class TestParent(unittest.TestCase):
    def setUp(self):
        self.test_view = TestView()
        self.patcher_view = patch(
            "pyxel_background_worker.main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "pyxel_background_worker.main.PyxelInput.create",
            return_value=self.test_input,
        )
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()

    def reset(self):
        self.test_view.reset()
        self.test_input.reset()


class TestButton(TestParent):
    def test_draw(self):
        test_cases = [
            ("no click", Color.BUTTON_EDGE, False),
            ("click", Color.BUTTON_EDGE_HOVER, True),
        ]
        for case_name, expected, is_click in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, is_click=is_click
            ):
                self.setUp()
                expected_list = []
                button = Button(100, 100, "msg")
                if is_click:
                    self.test_input.set_mouse_pos(100, 100)
                    self.test_input.set_is_click(True)
                button.update()
                button.draw()
                expected_list.append(
                    ("draw_rect", 100, 100, Button.WIDTH, Button.HEIGHT, expected, True)
                )
                expected_list.append(
                    (
                        "draw_text",
                        100 + Button.TEXT_LEFT_MARGIN,
                        100 + Button.TEXT_TOP_MARGIN,
                        "msg",
                        Color.TEXT,
                    )
                )
                self.assertEqual(
                    self.test_view.get_call_params(),
                    expected_list,
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_update_click(self):
        test_cases = [
            ("on left up", True, 100, 100),
            ("on right up", True, 100 + Button.WIDTH, 100),
            ("on right down", True, 100 + Button.WIDTH, 100 + Button.HEIGHT),
            ("on left down", True, 100, 100 + Button.HEIGHT),
            ("in middle", True, 100 + Button.WIDTH // 2, 100 + Button.HEIGHT // 2),
            ("out lefter up", False, 99, 100),
            ("out left upper", False, 100, 99),
            ("out righter up", False, 100 + Button.WIDTH + 1, 100),
            (
                "out righter downer",
                False,
                100 + Button.WIDTH + 1,
                100 + Button.HEIGHT + 1,
            ),
            ("out left downer", False, 100, 100 + Button.HEIGHT + 1),
        ]
        for case_name, expected, x, y in test_cases:
            with self.subTest(case_name=case_name, expected=expected, x=x, y=y):
                self.setUp()
                button = Button(100, 100, "msg")
                self.test_input.set_mouse_pos(x, y)
                self.test_input.set_is_click(True)
                for result in [False, expected, False]:
                    button.update()
                    self.assertEqual(button.is_click(), result)

    def test_update_hover(self):
        in_pos = (100, 100)
        out_pos = (99, 99)
        test_scenario = [
            ("on hover", False, True, in_pos),
            ("click", True, False, in_pos),
            ("on hover", False, True, in_pos),
            ("out hover", False, False, out_pos),
            ("on hover", False, True, in_pos),
            ("click", True, False, in_pos),
        ]
        button = Button(*in_pos, "msg")
        self.test_input.set_is_click(True)
        for scenario_name, expected_click, expected_hover, pos in test_scenario:
            self.test_input.set_mouse_pos(*pos)
            button.update()
            self.assertEqual(button.is_click(), expected_click, scenario_name)
            self.assertEqual(button.is_hover(), expected_hover, scenario_name)


class TestClock(TestParent):
    @patch.object(time, "perf_counter")
    def test_is_up(self, mock):
        test_cases = [
            ("1 sec", [False, True, False, True], 1000),
            ("1.1 sec", [False, False, True, False, False, True], 1100),
            ("always", [True, True, True, True, True, True], 1),
            ("never", [False, False, False, False, False, False], 0),
        ]
        for case_name, expected_list, base_time in test_cases:
            with self.subTest(
                case_name=case_name, expected_list=expected_list, base_time=base_time
            ):
                self.setUp()
                mock.side_effect = [i * 0.5 for i in range(10)]
                clock = Clock(base_time)
                for expected in expected_list:
                    self.assertEqual(expected, clock.is_up())
                self.tearDown()


class TestReportStore(unittest.TestCase):
    @patch.object(ReportStore, "set_local_storage")
    def test_save(self, mock):
        mock.return_value = True
        report_store = ReportStore()
        report_store.version = 1
        self.assertEqual(True, report_store.save({"test": "value"}))
        mock.assert_called_once_with('{"test": "value", "version": 1}')

    @patch.object(ReportStore, "set_local_storage")
    def test_save_exception(self, mock):
        mock.return_value = False
        report_store = ReportStore()
        report_store.version = 1
        self.assertEqual(False, report_store.save({"test": "value"}))
        mock.assert_called_once_with('{"test": "value", "version": 1}')

    @patch.object(ReportStore, "get_local_storage")
    def test_load(self, mock):
        test_cases = [
            ("success", {"test": "value"}, '{"test": "value", "version": 2}'),
            ("unmatch version", None, '{"test": "value", "version": 1}'),
            ("fail", None, None),
        ]
        for case_name, expected, load_str in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, load_str=load_str
            ):
                mock.return_value = load_str
                report_store = ReportStore()
                report_store.version = 2
                self.assertEqual(expected, report_store.load())


class TestGameCore(TestParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.core = GameCore()
        self.patcher_set_local_storage = patch(
            "pyxel_background_worker.main.ReportStore.set_local_storage",
            return_value=False,
        )
        self.mock_set_local_storage = self.patcher_set_local_storage.start()
        self.patcher_get_local_storage = patch(
            "pyxel_background_worker.main.ReportStore.get_local_storage",
            return_value=None,
        )
        self.mock_get_local_storage = self.patcher_get_local_storage.start()

    def tearDown(self):
        self.assertEqual(
            self.test_view.get_call_params(),
            self.expect_view_call,
            self.test_view.get_call_params(),
        )
        self.patcher_set_local_storage.stop()
        self.patcher_get_local_storage.stop()
        return super().tearDown()

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self.core = GameCore()

    def check(self):
        self.assertEqual(
            self.test_view.get_call_params(),
            self.expect_view_call,
            self.test_view.get_call_params(),
        )

    def put_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "clear":
                self.expect_view_call.extend(["clear"])
            elif draw_action[0] == "draw_line":
                for x, text in [
                    (20, draw_action[2]),
                    (100, draw_action[3]),
                    (250, draw_action[6]),
                ]:
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            x,
                            draw_action[1] + Button.TEXT_TOP_MARGIN,
                            text,
                            Color.TEXT,
                        )
                    )
                for x, text, is_hover in [
                    (150, "add", draw_action[4]),
                    (200, "del", draw_action[5]),
                ]:
                    if is_hover is not None:
                        self.expect_view_call.extend(
                            [
                                (
                                    "draw_rect",
                                    x,
                                    draw_action[1],
                                    Button.WIDTH,
                                    Button.HEIGHT,
                                    (
                                        Color.BUTTON_EDGE_HOVER
                                        if is_hover
                                        else Color.BUTTON_EDGE
                                    ),
                                    True,
                                ),
                                (
                                    "draw_text",
                                    x + Button.TEXT_LEFT_MARGIN,
                                    draw_action[1] + Button.TEXT_TOP_MARGIN,
                                    text,
                                    Color.TEXT,
                                ),
                            ]
                        )
            elif draw_action[0] == "draw_status":
                for x, y, text in [
                    (20, 200, "FOOD"),
                    (60, 200, draw_action[1]["FOOD"]),
                    (100, 200, "WOOD"),
                    (140, 200, draw_action[1]["WOOD"]),
                    (20, 210, "HOUSE"),
                    (60, 210, draw_action[1]["HOUSE"]),
                    (100, 210, "FARM"),
                    (140, 210, draw_action[1]["FARM"]),
                    (180, 210, "WOODSHED"),
                    (220, 210, draw_action[1]["WOODSHED"]),
                ]:
                    self.expect_view_call.append(("draw_text", x, y, text, Color.TEXT))
                for x, is_fill, width in [
                    (20, False, 70),
                    (20, True, 70 * draw_action[2]["HOUSE"]),
                    (100, False, 70),
                    (100, True, 70 * draw_action[2]["FARM"]),
                    (180, False, 70),
                    (180, True, 70 * draw_action[2]["WOODSHED"]),
                ]:
                    self.expect_view_call.append(
                        ("draw_rect", x, 218, width, 5, Color.TEXT, is_fill)
                    )

    def _check_result(self, worker_map, consume_map, progress_map, status_map):
        self.put_draw_result([["clear"]])
        for x, label, enable_del, consume_default in [
            (20, "NO JOB", False, "0/s"),
            (50, "HOUSE BUILDER", True, "-5"),
            (80, "FARMER", True, "0/s"),
            (110, "FARM BUILDER", True, "-5"),
            (140, "LOGGER", True, "0/s"),
            (170, "WOODSHED BUILDER", True, "-5"),
        ]:
            self.put_draw_result(
                [
                    [
                        "draw_line",
                        x,
                        label,
                        worker_map.get(label, 0),
                        False,
                        False if enable_del else None,
                        consume_map.get(label, consume_default),
                    ],
                ]
            )
        base_progress_map = {"HOUSE": 0, "FARM": 0, "WOODSHED": 0}
        base_progress_map.update(progress_map)
        base_status_map = {"FOOD": 0, "WOOD": 0, "HOUSE": 1, "FARM": 1, "WOODSHED": 1}
        base_status_map.update(status_map)
        self.put_draw_result([["draw_status", base_status_map, base_progress_map]])

    def _click(self, x, y):
        self.test_input.set_mouse_pos(x, y)
        self.test_input.set_is_click(True)
        self.core.update()
        self.core.update()

    def test_draw(self):
        try:
            self.core.draw()
            self._check_result({}, {}, {}, {})
        except Exception as e:  # pylint: disable=W0703
            self.fail(f"test failed {e}")

    def test_add_worker(self):
        try:
            self._click(150, 20)
            self.core.draw()
        except Exception as e:  # pylint: disable=W0703
            self.fail(f"test failed {e}")
        self._check_result({"NO JOB": 1}, {"NO JOB": "-1/s"}, {}, {})

    def test_change_job(self):
        test_cases = [
            (
                "farmer",
                {"FARMER": 1},
                {"NO JOB": "-1/s", "FARMER": "+2/s"},
                [(150, 20), (150, 80)],
            ),
            (
                "farmer builder",
                {"FARM BUILDER": 1},
                {"NO JOB": "-1/s", "FARM BUILDER": "-5"},
                [(150, 20), (150, 110)],
            ),
            (
                "reset",
                {"NO JOB": 1},
                {"NO JOB": "-1/s"},
                [(150, 20), (150, 80), (200, 80)],
            ),
        ]
        for case_name, expected, expected_consume, click_pos_list in test_cases:
            with self.subTest(
                case_name=case_name, expected=expected, click_pos_list=click_pos_list
            ):
                self.reset()
                try:
                    for pos in click_pos_list:
                        self._click(*pos)
                    self.core.draw()
                except Exception as e:  # pylint: disable=W0703
                    self.fail(f"test failed {e}")
                self._check_result(expected, expected_consume, {}, {})
                self.check()

    @patch.object(Clock, "is_up")
    def test_turn(self, mock):
        test_cases = [
            (
                "harvest food",
                {"FOOD": 1},
                {"FARMER": 1},
                {"NO JOB": "-1/s", "FARMER": "+2/s"},
                {},
                [(150, 20), (150, 80)],
                {},
            ),
            (
                "build house",
                {},
                {"HOUSE BUILDER": 1},
                {"NO JOB": "-1/s"},
                {"HOUSE": 1 / 3},
                [(150, 20), (150, 50)],
                {Resource.FOOD: 1, Resource.WOOD: 5},
            ),
        ]
        for (
            case_name,
            expected_status,
            expected_worker,
            expected_change,
            expected_progress,
            click_pos_list,
            first_resources,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_status=expected_status,
                expected_worker=expected_worker,
                expected_change=expected_change,
                expected_progress=expected_progress,
                click_pos_list=click_pos_list,
                first_resources=first_resources,
            ):
                self.reset()
                try:
                    self.core.game_logic.resource_map.update(first_resources)
                    mock.return_value = False
                    for pos in click_pos_list:
                        self._click(*pos)
                    self._click(0, 0)
                    mock.return_value = True
                    self.core.update()
                    self.core.draw()
                except Exception as e:  # pylint: disable=W0703
                    self.fail(f"test failed {e}")
                self._check_result(
                    expected_worker, expected_change, expected_progress, expected_status
                )
                self.check()

    def test_save_load(self):
        try:
            self._click(150, 20)
            save_data = self.mock_set_local_storage.call_args.args[0]
            self.reset()
            self.mock_get_local_storage.return_value = save_data
            self.core = GameCore()
            self.core.draw()
        except Exception as e:  # pylint: disable=W0703
            self.fail(f"test failed {e}")
        self._check_result({"NO JOB": 1}, {"NO JOB": "-1/s"}, {}, {})


if __name__ == "__main__":
    unittest.main()

# TODO: セーブとロードの時間差で、ゲームを自動進行させる。
# TODO:  自動進行させる最大時間を決める。
# TODO: 最初からボタン

# TODO: ワーカーの仕事を変える
# TODO: ワーカーを絵で表示
# TODO: 仕事を枠で表示
# TODO: フリックで、ワーカーを増やす
# TODO: ドラッグで、ワーカーを複数選択、同時操作

# TODO: セーブデータのファイルエクスポート・インポート
# TODO: cookieのオプトアウト選択（最初に使ってよいとなったら、以後は言わない）
