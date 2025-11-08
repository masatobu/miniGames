import os
import sys
import unittest
import time
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from pyxel_background_worker.main import (  # pylint: disable=C0413
    IView,
    GameCore,
    Color,
    IInput,
    Clock,
    Resource,
    ReportStore,
    Building,
    HouseArea,
    FarmArea,
    WoodshedArea,
    NoJobArea,
    FarmerArea,
    WorkingArea,
    LoggerArea,
    HouseBuilderArea,
    FarmBuilderArea,
    WoodshedBuilderArea,
    Cursol,
    NewWorkerArea,
)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text, col):
        self.call_params.append(("draw_text", x, y, text, col))

    def draw_rect(self, x, y, w, h, col, is_fill):
        self.call_params.append(("draw_rect", x, y, w, h, col, is_fill))

    def draw_image(self, x, y, width, height, src_tile_x, src_tile_y, scale):
        self.call_params.append(
            ("draw_image", x, y, width, height, src_tile_x, src_tile_y, scale)
        )

    def clear(self):
        self.call_params.append("clear")

    def get_call_params(self):
        return self.call_params

    def reset(self):
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


class TestBuildingArea(TestParent):
    AREA_POS_MAP = {
        HouseArea: (35, 45),
        FarmArea: (35, 90),
        WoodshedArea: (180, 90),
    }

    def setUp(self):
        super().setUp()
        self.reset()

    def tearDown(self):
        self.mock_stop()
        return super().tearDown()

    def reset(self):
        super().reset()
        self.patcher_get_pos = patch(
            "pyxel_background_worker.main.BuildingArea._get_pos",
            side_effect=[(i * 7, 0) for i in range(10)],
        )
        self.mock_get_pos = self.patcher_get_pos.start()

    def mock_stop(self):
        self.patcher_get_pos.stop()

    def test_draw(self):
        test_cases = [
            ("1 building", [(0, 1)], 1, 1, HouseArea),
            ("2 building", [(0, 1), (7, 1)], 2, 2, HouseArea),
            ("1 building vacant", [(0, 3)], 1, 0, HouseArea),
            ("2 building vacant", [(0, 3), (7, 3)], 2, 0, HouseArea),
            ("2 building vacant and stay", [(0, 1), (7, 3)], 2, 1, HouseArea),
            ("1 farm", [(0, 2)], 1, 1, FarmArea),
            ("1 farm vacant", [(0, 4)], 1, 0, FarmArea),
            ("1 woodshed", [(0, 2)], 1, 1, WoodshedArea),
            ("1 woodshed vacant", [(0, 4)], 1, 0, WoodshedArea),
        ]
        for (
            case_name,
            expected_x_pos_list,
            total,
            stay,
            area_class,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_x_pos_list=expected_x_pos_list,
                total=total,
                stay=stay,
                area_class=area_class,
            ):
                self.reset()
                house_area = area_class()
                house_area.set_num(total, stay)
                house_area.draw()
                expected_pos = self.AREA_POS_MAP[area_class]
                expected_list = [
                    (
                        "draw_image",
                        expected_pos[0] + x,
                        expected_pos[1],
                        7,
                        7,
                        img_x,
                        2,
                        1,
                    )
                    for x, img_x in expected_x_pos_list
                ]
                self.assertEqual(self.test_view.get_call_params(), expected_list)
                self.mock_stop()


class TestWorkerArea(TestParent):
    AREA_RECT_MAP = {
        NoJobArea: (35, 30, 255, 6),
        FarmerArea: (35, 120, 110, 110),
        LoggerArea: (180, 120, 110, 110),
        HouseBuilderArea: (35, 60, 255, 6),
        FarmBuilderArea: (35, 105, 110, 6),
        WoodshedBuilderArea: (180, 105, 110, 6),
        NewWorkerArea: (10, 7, 20, 12),
    }

    def setUp(self):
        super().setUp()
        self.reset()

    def tearDown(self):
        self.mock_stop()
        return super().tearDown()

    def reset(self):
        super().reset()
        self.patcher_get_pos_list = []
        for target in [
            "NoJobArea",
            "FarmerArea",
            "LoggerArea",
            "HouseBuilderArea",
            "FarmBuilderArea",
            "WoodshedBuilderArea",
        ]:
            y = 10 if target in ["FarmerArea", "LoggerArea"] else 0
            patcher_get_pos = patch(
                f"pyxel_background_worker.main.{target}._get_pos",
                side_effect=[(i * 7, y) for i in range(20)],
            )
            patcher_get_pos.start()
            self.patcher_get_pos_list.append(patcher_get_pos)

    def mock_stop(self):
        for patcher in self.patcher_get_pos_list:
            patcher.stop()

    def test_draw(self):
        test_cases = [
            ("no job", [(0, 0)], 1, 1, NoJobArea),
            ("2 no job", [(0, 0), (7, 0)], 1, 2, NoJobArea),
            ("farmer", [(0, 10)], 3, 1, FarmerArea),
            ("logger", [(0, 10)], 4, 1, LoggerArea),
            ("house builder", [(0, 0)], 2, 1, HouseBuilderArea),
            ("farm builder", [(0, 0)], 2, 1, FarmBuilderArea),
            ("woodshed builder", [(0, 0)], 2, 1, WoodshedBuilderArea),
            ("new worker", [(10, 3)], 1, 1, NewWorkerArea),
        ]
        for (
            case_name,
            expected_pos_list,
            expected_image_pos_x,
            num,
            area_class,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_x_pos_list=expected_pos_list,
                expected_image_pos_x=expected_image_pos_x,
                num=num,
                area_class=area_class,
            ):
                self.reset()
                working_area = area_class()
                working_area.set_num(num)
                working_area.draw()
                expected_list = []
                pos_list = [
                    [
                        p + d
                        for p, d in zip(
                            self.AREA_RECT_MAP[area_class][:2], (expected_x, expected_y)
                        )
                    ]
                    for expected_x, expected_y in expected_pos_list
                ]
                expected_list.append(
                    (
                        "draw_rect",
                        *self.AREA_RECT_MAP[area_class],
                        Color.AREA_FRAME,
                        True,
                    )
                )
                scale = 2 if isinstance(working_area, NewWorkerArea) else 1
                expected_list.extend(
                    [
                        ("draw_image", *pos, 5, 6, expected_image_pos_x, 0, scale)
                        for pos in pos_list
                    ]
                )
                if isinstance(working_area, NewWorkerArea):
                    pos = pos_list[0]
                    expected_list.extend(
                        [
                            ("draw_text", pos[0] - 6, pos[1] + 1, "+", Color.ADD),
                        ]
                    )
                self.assertEqual(self.test_view.get_call_params(), expected_list)
                self.mock_stop()

    def test_select(self):
        test_cases = [
            ("1 select", [True], 1, (0, 0), (5, 6), NoJobArea),
            ("no select by left", [False], 1, (0, 0), (5, 5), NoJobArea),
            ("no select by down", [False], 1, (0, 0), (4, 6), NoJobArea),
            ("no select by up", [False], 1, (0, 1), (5, 6), NoJobArea),
            ("no select by right", [False], 1, (1, 0), (5, 6), NoJobArea),
            ("2 select", [True] * 2, 2, (0, 0), (12, 6), NoJobArea),
            ("1 select 1 no select", [True, False], 2, (0, 0), (11, 6), NoJobArea),
            ("1 no select 1 select ", [False, True], 2, (1, 0), (11, 6), NoJobArea),
            ("1 select new woker", [True], 1, (0, 0), (5, 6), NewWorkerArea),
            (
                "no select new woker by left",
                [False],
                1,
                (0, 0),
                (5, 5),
                NewWorkerArea,
            ),
            (
                "no select new woker by down",
                [False],
                1,
                (0, 0),
                (4, 6),
                NewWorkerArea,
            ),
            (
                "no select new woker by up",
                [False],
                1,
                (0, 1),
                (5, 6),
                NewWorkerArea,
            ),
            (
                "no select new woker by right",
                [False],
                1,
                (1, 0),
                (5, 6),
                NewWorkerArea,
            ),
        ]
        for (
            case_name,
            expected_selected_list,
            num,
            select_pos_diff,
            select_size,
            area_class,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_selected_list=expected_selected_list,
                num=num,
                select_pos_diff=select_pos_diff,
                select_size=select_size,
                area_class=area_class,
            ):
                self.reset()
                working_area = area_class()
                working_area.set_num(num)
                worker_pos = (
                    (
                        self.AREA_RECT_MAP[area_class][0] + 10,
                        self.AREA_RECT_MAP[area_class][1] + 3,
                    )
                    if isinstance(working_area, NewWorkerArea)
                    else self.AREA_RECT_MAP[area_class]
                )
                select_pos = [p + d for p, d in zip(worker_pos, select_pos_diff)]
                result = working_area.select(*select_pos, *select_size)
                working_area.draw()
                expected_list = []
                expected_list.append(
                    (
                        "draw_rect",
                        *self.AREA_RECT_MAP[area_class],
                        Color.AREA_FRAME,
                        True,
                    )
                )
                scale = 2 if isinstance(working_area, NewWorkerArea) else 1
                expected_list.extend(
                    [
                        (
                            "draw_image",
                            worker_pos[0] + i * 7,
                            worker_pos[1],
                            5,
                            6,
                            1,
                            1 if selected else 0,
                            scale,
                        )
                        for i, selected in enumerate(expected_selected_list)
                    ]
                )
                if isinstance(working_area, NewWorkerArea):
                    color = (
                        Color.SELECTED_ADD if any(expected_selected_list) else Color.ADD
                    )
                    expected_list.append(
                        ("draw_text", worker_pos[0] - 6, worker_pos[1] + 1, "+", color)
                    )
                self.assertEqual(self.test_view.get_call_params(), expected_list)
                self.assertEqual(result, any(expected_selected_list))
                self.assertEqual(
                    working_area.get_selected_num(),
                    sum(1 for b in expected_selected_list if b),
                )
                self.mock_stop()

    def test_is_click(self):
        test_cases = [
            ("click left up", True, (0, 0), (0, 0), NoJobArea),
            ("click left up over", False, (-1, 0), (0, 0), NoJobArea),
            ("click right down", True, (255, 6), (0, 0), NoJobArea),
            ("click right down over", False, (255, 7), (0, 0), NoJobArea),
            ("slide left up", True, (-50, -10), (50, 10), NoJobArea),
            ("slide left up over", False, (-51, -10), (50, 10), NoJobArea),
            ("slide right down", True, (255 - 10, 6 - 10), (10, 10), NoJobArea),
            ("slide right down over", False, (255 - 10, 6 - 9), (10, 10), NoJobArea),
            ("click new worker left up", True, (0, 0), (0, 0), NewWorkerArea),
            ("click new worker left up over", False, (-1, 0), (0, 0), NewWorkerArea),
            ("click new worker right down", True, (10, 12), (0, 0), NewWorkerArea),
            (
                "click new worker right down over",
                False,
                (10, 13),
                (0, 0),
                NewWorkerArea,
            ),
        ]
        for case_name, expected, select_pos_diff, select_size, area_class in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                select_pos_diff=select_pos_diff,
                select_size=select_size,
                area_class=area_class,
            ):
                self.reset()
                working_area = area_class()
                select_pos = [
                    p + d
                    for p, d in zip(self.AREA_RECT_MAP[area_class][:2], select_pos_diff)
                ]
                result = working_area.is_click(*select_pos, *select_size)
                self.assertEqual(result, expected)
                self.mock_stop()

    def test_select_set_num(self):
        test_cases = [
            ("5 to 2", [False, True, True, False, False], [False, True]),
            ("3 to 3", [False, True, True], [False, True, True]),
            ("2 to 5", [False, True], [False, True, False, False, False]),
            ("5 to 0", [False, True, True, False, False], []),
            ("0 to 5", [], [False, False, False, False, False]),
        ]
        for (
            case_name,
            expected_before,
            expected_after,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_before=expected_before,
                expected_after=expected_after,
            ):
                self.reset()
                working_area = NoJobArea()
                working_area.set_num(len(expected_before))
                p_x, p_y = self.AREA_RECT_MAP[NoJobArea][:2]
                result = working_area.select(p_x + 7, p_y, 14, 6)  # select 2
                working_area.draw()
                expected_list = [
                    (
                        "draw_rect",
                        *self.AREA_RECT_MAP[NoJobArea],
                        Color.AREA_FRAME,
                        True,
                    )
                ]
                expected_list.extend(
                    [
                        (
                            "draw_image",
                            p_x + i * 7,
                            p_y,
                            5,
                            6,
                            1,
                            1 if selected else 0,
                            1,
                        )
                        for i, selected in enumerate(expected_before)
                    ]
                )
                self.assertEqual(result, any(expected_before))
                self.assertEqual(
                    working_area.get_selected_num(),
                    sum(1 for b in expected_before if b),
                )

                working_area.set_num(len(expected_after))
                working_area.draw()
                expected_list.append(
                    (
                        (
                            "draw_rect",
                            *self.AREA_RECT_MAP[NoJobArea],
                            Color.AREA_FRAME,
                            True,
                        )
                    )
                )
                expected_list.extend(
                    [
                        (
                            "draw_image",
                            p_x + i * 7,
                            p_y,
                            5,
                            6,
                            1,
                            1 if selected else 0,
                            1,
                        )
                        for i, selected in enumerate(expected_after)
                    ]
                )
                self.assertEqual(self.test_view.get_call_params(), expected_list)
                self.assertEqual(
                    working_area.get_selected_num(),
                    sum(1 for b in expected_after if b),
                )
                self.mock_stop()


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
            ("no json format", None, "version: 2"),
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

    def test_crypt(self):
        test_cases = [
            ("case1", "test", "test", False),
            (
                "case2",
                " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
                False,
            ),
            ("error", None, "error test", True),
        ]
        for case_name, expected, target, is_old_stored in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                target=target,
                is_old_stored=is_old_stored,
            ):
                report_store = ReportStore()
                crypt_str = report_store._crypt(target)  # pylint: disable=W0212
                if is_old_stored:
                    crypt_str = target
                decrypt_str = report_store._decrypt(crypt_str)  # pylint: disable=W0212
                self.assertEqual(decrypt_str, expected)


class TestCursol(TestParent):
    def test_draw(self):
        test_cases = [
            (
                "to right down",
                [(1, 1, 0, 0), (1, 1, 10, 10)],
                [
                    (True, False, (1, 1)),
                    (False, False, (11, 11)),
                    (False, True, (21, 21)),
                ],
            ),
            (
                "to left up",
                [(21, 21, 0, 0), (11, 11, 10, 10)],
                [
                    (True, False, (21, 21)),
                    (False, False, (11, 11)),
                    (False, True, (1, 1)),
                ],
            ),
            (
                "to right up",
                [(1, 21, 0, 0), (1, 11, 10, 10)],
                [
                    (True, False, (1, 21)),
                    (False, False, (11, 11)),
                    (False, True, (21, 1)),
                ],
            ),
            (
                "to left down",
                [(21, 1, 0, 0), (11, 1, 10, 10)],
                [
                    (True, False, (21, 1)),
                    (False, False, (11, 11)),
                    (False, True, (1, 21)),
                ],
            ),
        ]
        for case_name, expected, action in test_cases:
            with self.subTest(case_name=case_name, expected=expected, action=action):
                self.setUp()
                cursol = Cursol()
                for is_click, is_release, mouse_pos in action:
                    self.test_input.set_is_click(is_click)
                    self.test_input.set_is_release(is_release)
                    self.test_input.set_mouse_pos(*mouse_pos)
                    cursol.update()
                    cursol.draw()
                expected_list = [
                    ("draw_rect", *rect, Color.CURSOL, False) for rect in expected
                ]
                self.assertEqual(
                    self.test_view.get_call_params(),
                    expected_list,
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_get_select(self):
        test_cases = [
            (
                "to right down",
                (10, 10, 10, 10),
                [(10, 10), (20, 20), (30, 30), (40, 40)],
            ),
            (
                "to left up",
                (30, 30, 10, 10),
                [(40, 40), (30, 30), (20, 20), (10, 10)],
            ),
            (
                "to right up",
                (0, 30, 10, 10),
                [(0, 40), (10, 30), (20, 20), (30, 10)],
            ),
            (
                "to left down",
                (30, 0, 10, 10),
                [(40, 0), (30, 10), (20, 20), (10, 30)],
            ),
        ]
        for case_name, expected, action in test_cases:
            with self.subTest(case_name=case_name, expected=expected, action=action):
                self.setUp()
                cursol = Cursol()
                for expected_pos, is_click, is_release, mouse_pos in [
                    (None, True, False, action[0]),
                    (None, False, False, action[1]),
                    (expected, False, True, action[2]),
                    (None, False, False, action[3]),
                ]:
                    self.test_input.set_is_click(is_click)
                    self.test_input.set_is_release(is_release)
                    self.test_input.set_mouse_pos(*mouse_pos)
                    cursol.update()
                    self.assertEqual(cursol.get_select(), expected_pos)
                self.tearDown()


class TestGameCore(TestParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
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
        self._reset_x_pos()
        self.core = GameCore()
        self.core.game_logic.resource_map = {r: 0 for r in Resource}

    def tearDown(self):
        self.assertEqual(
            self.test_view.get_call_params(),
            self.expect_view_call,
            self.test_view.get_call_params(),
        )
        self.patcher_set_local_storage.stop()
        self.patcher_get_local_storage.stop()
        for patcher in self.patcher_get_pos_list:
            patcher.stop()
        return super().tearDown()

    def _reset_x_pos(self):
        self.patcher_get_pos_list = []
        for target in [
            "HouseArea",
            "FarmArea",
            "WoodshedArea",
            "NoJobArea",
            "FarmerArea",
            "LoggerArea",
            "HouseBuilderArea",
            "FarmBuilderArea",
            "WoodshedBuilderArea",
        ]:
            patcher_get_pos = patch(
                f"pyxel_background_worker.main.{target}._get_pos",
                side_effect=[(i * 7, 0) for i in range(20)],
            )
            patcher_get_pos.start()
            self.patcher_get_pos_list.append(patcher_get_pos)

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self._reset_x_pos()
        self.core = GameCore()
        self.core.game_logic.resource_map = {r: 0 for r in Resource}

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
            elif draw_action[0] == "draw_status":
                self.expect_view_call.append(
                    ("draw_text", *draw_action[1:], Color.TEXT)
                )
            elif draw_action[0] == "draw_progress":
                for x, y, is_fill, width in [
                    (35, 52, False, 255),
                    (35, 52, True, 255 * draw_action[1]["HOUSE"]),
                    (35, 97, False, 110),
                    (35, 97, True, 110 * draw_action[1]["FARM"]),
                    (180, 97, False, 110),
                    (180, 97, True, 110 * draw_action[1]["WOODSHED"]),
                ]:
                    self.expect_view_call.append(
                        ("draw_rect", x, y, width, 5, Color.TEXT, is_fill)
                    )
            elif draw_action[0] == "draw_building_area":
                for i, img_x in enumerate(
                    [
                        draw_action[3] if i < draw_action[2] else draw_action[3] + 2
                        for i in range(draw_action[1])
                    ]
                ):
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            draw_action[4][0] + i * 7,
                            draw_action[4][1],
                            7,
                            7,
                            img_x,
                            2,
                            1,
                        )
                    )
            elif draw_action[0] == "draw_working_area":
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        *draw_action[3],
                        *draw_action[6],
                        Color.AREA_FRAME,
                        True,
                    )
                )
                worker_pos = (
                    (draw_action[3][0] + 10, draw_action[3][1] + 3)
                    if draw_action[5] == 2
                    else draw_action[3]
                )
                for i in range(draw_action[1]):
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            worker_pos[0] + i * 7,
                            worker_pos[1],
                            *WorkingArea.IMAGE_SIZE,
                            draw_action[2] if i >= draw_action[4] else 1,
                            0 if i >= draw_action[4] else 1,
                            draw_action[5],
                        )
                    )
                if draw_action[5] == 2:  # label == "NEW WORKER"
                    color = Color.SELECTED_ADD if draw_action[4] > 0 else Color.ADD
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            worker_pos[0] - 6,
                            worker_pos[1] + 1,
                            "+",
                            color,
                        )
                    )
            elif draw_action[0] == "draw_cursol":
                self.expect_view_call.append(
                    (
                        "draw_rect",
                        *draw_action[1],
                        *draw_action[2],
                        Color.CURSOL,
                        False,
                    )
                )
            elif draw_action[0] == "draw_icon":
                self.expect_view_call.append(
                    (
                        "draw_image",
                        *draw_action[1],
                        *draw_action[2],
                        1,
                    )
                )
            elif draw_action[0] == "draw_end":
                self.expect_view_call.extend(
                    [
                        (
                            "draw_text",
                            300 // 2 - 50,
                            400 // 2 - 100,
                            "Game Clear",
                            Color.TEXT,
                        ),
                        (
                            "draw_text",
                            300 // 2 - 60,
                            400 // 2 - 70,
                            "Tap to Continue",
                            Color.TEXT,
                        ),
                    ]
                )

    def _check_result_base(
        self, worker_map, consume_map, progress_map, status_map, select_map
    ):
        self.put_draw_result([["clear"]])
        for x, y, label, consume_default in [
            (120, 241, "NO JOB", "0/s"),
            (10, 51, "HOUSE BUILDER", "-5"),
            (80, 241, "FARMER", "0/s"),
            (10, 96, "FARM BUILDER", "-5"),
            (235, 241, "LOGGER", "0/s"),
            (155, 96, "WOODSHED BUILDER", "-5"),
        ]:
            self.put_draw_result(
                [
                    ["draw_status", x, y, consume_map.get(label, consume_default)],
                ]
            )
        base_status_map = {
            "FOOD": "0",
            "WOOD": "0",
            "HOUSE": 1,
            "FARM": 1,
            "WOODSHED": 1,
            "HOUSE STAY": 0,
            "FARM STAY": 0,
            "WOODSHED STAY": 0,
        }
        base_status_map.update(status_map)
        for x, y, label in [
            (40, 241, "FOOD"),
            (185, 241, "WOOD"),
        ]:
            self.put_draw_result(
                [
                    ["draw_status", x, y, base_status_map[label]],
                ]
            )
        base_progress_map = {"HOUSE": 0, "FARM": 0, "WOODSHED": 0}
        base_progress_map.update(progress_map)
        self.put_draw_result([["draw_progress", base_progress_map]])
        for label, image_pos, pos in [
            ("HOUSE", 1, (35, 45)),
            ("FARM", 2, (35, 90)),
            ("WOODSHED", 2, (180, 90)),
        ]:
            self.put_draw_result(
                [
                    [
                        "draw_building_area",
                        base_status_map[label],
                        base_status_map[f"{label} STAY"],
                        image_pos,
                        pos,
                    ]
                ]
            )
        worker_icon_map = {"NEW WORKER": 1} | worker_map
        for label, image_pos, pos, frame_size in [
            ("NO JOB", 1, (35, 30), (255, 6)),
            ("FARMER", 3, (35, 120), (110, 110)),
            ("LOGGER", 4, (180, 120), (110, 110)),
            ("HOUSE BUILDER", 2, (35, 60), (255, 6)),
            ("FARM BUILDER", 2, (35, 105), (110, 6)),
            ("WOODSHED BUILDER", 2, (180, 105), (110, 6)),
            ("NEW WORKER", 1, (10, 7), (20, 12)),
        ]:
            self.put_draw_result(
                [
                    [
                        "draw_working_area",
                        worker_icon_map.get(label, 0),
                        image_pos,
                        pos,
                        select_map.get(label, 0),
                        2 if label == "NEW WORKER" else 1,
                        frame_size,
                    ]
                ]
            )
        for x, y, label in [
            (35, 10, sum(v for k, v in worker_icon_map.items() if k != "NEW WORKER")),
            (60, 10, "/"),
            (70, 10, self.core.game_logic.TARGET_NUM),
        ]:
            self.put_draw_result([["draw_status", x, y, label]])
        for label, pos, image_pos in [
            ("WHEET", (65, 77), (1, 3)),
            ("WOOD", (210, 77), (2, 3)),
        ]:
            for i in range(5):
                icon_pos = (pos[0] + i * 10, pos[1])
                self.put_draw_result([["draw_icon", (*icon_pos, 8, 8), image_pos]])

    def _check_result(self, worker_map, consume_map, progress_map, status_map):
        self._check_result_base(worker_map, consume_map, progress_map, status_map, {})

    def _check_select_result(self, worker_map, consume_map, status_map, select_map):
        self._check_result_base(worker_map, consume_map, {}, status_map, select_map)

    def _add_worker(self, to_area):
        area_pos_map = {
            NoJobArea: (35, 30),
            FarmerArea: (35, 120),
            HouseBuilderArea: (35, 60),
        }
        add_pos = [(20, 10), (30, 22)]

        for is_click, is_release, mouse_pos in [
            # 1回目は選択
            (True, False, add_pos[0]),
            (False, False, add_pos[1]),
            (False, True, add_pos[1]),
            # 2回目で操作
            (True, False, area_pos_map[to_area]),
            (False, False, area_pos_map[to_area]),
            (False, True, area_pos_map[to_area]),
        ]:
            self.test_input.set_is_click(is_click)
            self.test_input.set_is_release(is_release)
            self.test_input.set_mouse_pos(*mouse_pos)
            self.core.update()

    def test_draw(self):
        try:
            self.core.game_logic.resource_map.update({Resource.FOOD: 2_000})
            # 5, 10, 20, 40, 80, 160, 320, 640, 1280
            self.core.game_logic.building_num_map[Building.FARM] = 9
            self.core.area_map[Building.FARM].set_num(9, 0)
            self.core.draw()
            self._check_result(
                {}, {"FARM BUILDER": "-1K"}, {}, {"FOOD": "2K", "FARM": 9}
            )
        except Exception as e:  # pylint: disable=W0703
            self.fail(f"test failed {e}")

    def test_cursol_draw(self):
        try:
            for is_click, is_release, mouse_pos in [
                (True, False, (1, 1)),
                (False, False, (11, 11)),
            ]:
                self.test_input.set_is_click(is_click)
                self.test_input.set_is_release(is_release)
                self.test_input.set_mouse_pos(*mouse_pos)
                self.core.update()
            self.core.draw()
            self._check_result({}, {}, {}, {})
            self.put_draw_result([["draw_cursol", (1, 1), (10, 10)]])
        except Exception as e:  # pylint: disable=W0703
            self.fail(f"test failed {e}")

    @patch.object(Clock, "is_up")
    def test_worker_select(self, mock):
        mock.return_value = False
        area_pos_map = {
            NoJobArea: (35, 30),
            FarmerArea: (35, 120),
            HouseBuilderArea: (35, 60),
            FarmBuilderArea: (35, 105),
            LoggerArea: (180, 120),
        }
        add_pos = (20, 10)
        test_cases = [
            (
                "2 farmer to 1 no job",
                [
                    {"FARMER": 2},
                    {"NO JOB": "-2/s", "FARMER": "+4/s"},
                    {},
                    {"FARMER": 1},
                ],
                [
                    {"FARMER": 1, "NO JOB": 1},
                    {"NO JOB": "-2/s", "FARMER": "+2/s"},
                    {},
                    {},
                ],
                False,
                [FarmerArea] * 2,
                (*area_pos_map[FarmerArea], 5, 6),
                (*area_pos_map[NoJobArea], 0, 0),
            ),
            (
                "2 no job to 1 farmer",
                [{"NO JOB": 2}, {"NO JOB": "-2/s"}, {}, {"NO JOB": 1}],
                [
                    {"FARMER": 1, "NO JOB": 1},
                    {"NO JOB": "-2/s", "FARMER": "+2/s"},
                    {},
                    {},
                ],
                False,
                [NoJobArea] * 2,
                (*area_pos_map[NoJobArea], 5, 6),
                (*area_pos_map[FarmerArea], 0, 0),
            ),
            (
                "2 no job to 2 no job",
                [{"NO JOB": 2}, {"NO JOB": "-2/s"}, {}, {"NO JOB": 2}],
                [{"NO JOB": 2}, {"NO JOB": "-2/s"}, {}, {}],
                False,
                [NoJobArea] * 2,
                (*area_pos_map[NoJobArea], 12, 6),
                (*area_pos_map[NoJobArea], 0, 0),
            ),
            (
                "3 house builder to 2 farm builder",
                [{"HOUSE BUILDER": 3}, {"NO JOB": "-3/s"}, {}, {"HOUSE BUILDER": 2}],
                [{"HOUSE BUILDER": 1, "FARM BUILDER": 2}, {"NO JOB": "-3/s"}, {}, {}],
                False,
                [HouseBuilderArea] * 3,
                (*area_pos_map[HouseBuilderArea], 12, 6),
                (*area_pos_map[FarmBuilderArea], 0, 0),
            ),
            (
                "4 no job to 4 logger",
                [{"NO JOB": 4}, {"NO JOB": "-4/s"}, {"HOUSE STAY": 1}, {"NO JOB": 4}],
                [
                    {"LOGGER": 4},
                    {"NO JOB": "-4/s", "LOGGER": "+8/s"},
                    {"HOUSE STAY": 1, "WOODSHED STAY": 1},
                    {},
                ],
                False,
                [NoJobArea] * 4,
                (*area_pos_map[NoJobArea], 26, 6),
                (*area_pos_map[LoggerArea], 0, 0),
            ),
            (
                "5 no job to 4 over 1 farmer",
                [{"NO JOB": 5}, {"NO JOB": "-5/s"}, {"HOUSE STAY": 1}, {"NO JOB": 5}],
                [
                    {"FARMER": 4, "NO JOB": 1},
                    {"NO JOB": "-5/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 1, "FARM STAY": 1},
                    {},
                ],
                False,
                [NoJobArea] * 5,
                (*area_pos_map[NoJobArea], 33, 6),
                (*area_pos_map[FarmerArea], 0, 0),
            ),
            (
                "4 no job and 4 farm to over 4 farmer",
                [
                    {"NO JOB": 4, "FARMER": 4},
                    {"NO JOB": "-8/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 2, "FARM STAY": 1},
                    {"NO JOB": 4},
                ],
                [
                    {"NO JOB": 4, "FARMER": 4},
                    {"NO JOB": "-8/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 2, "FARM STAY": 1},
                    {},
                ],
                False,
                [NoJobArea] * 4 + [FarmerArea] * 4,
                (*area_pos_map[NoJobArea], 26, 6),
                (*area_pos_map[FarmerArea], 0, 0),
            ),
            (
                "2 no job and 2 farm to 2 farmer",
                [
                    {"NO JOB": 2, "FARMER": 2},
                    {"NO JOB": "-4/s", "FARMER": "+4/s"},
                    {"HOUSE STAY": 1},
                    {"NO JOB": 2},
                ],
                [
                    {"FARMER": 4},
                    {"NO JOB": "-4/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 1, "FARM STAY": 1},
                    {},
                ],
                True,
                [NoJobArea] * 2 + [FarmerArea] * 2,
                (*area_pos_map[NoJobArea], 12, 6),
                (*area_pos_map[FarmerArea], 0, 0),
            ),
            (
                "2 no job and 2 farm to 4 logger",
                [
                    {"NO JOB": 2, "FARMER": 2},
                    {"NO JOB": "-4/s", "FARMER": "+4/s"},
                    {"HOUSE STAY": 1},
                    {"NO JOB": 2, "FARMER": 2},
                ],
                [
                    {"LOGGER": 4},
                    {"NO JOB": "-4/s", "LOGGER": "+8/s"},
                    {"HOUSE STAY": 1, "WOODSHED STAY": 1},
                    {},
                ],
                True,
                [NoJobArea] * 2 + [FarmerArea] * 2,
                (*area_pos_map[NoJobArea], 12, 96),
                (*area_pos_map[LoggerArea], 0, 0),
            ),
            (
                "new worker to farmer",
                [{}, {}, {}, {"NEW WORKER": 1}],
                [
                    {"FARMER": 1},
                    {"NO JOB": "-1/s", "FARMER": "+2/s"},
                    {},
                    {},
                ],
                False,
                [],
                (*add_pos, 10, 12),
                (*area_pos_map[FarmerArea], 0, 0),
            ),
            (
                "4 no job and 4 farm to new worker icon",
                [
                    {"NO JOB": 4, "FARMER": 4},
                    {"NO JOB": "-8/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 2, "FARM STAY": 1},
                    {"NO JOB": 4},
                ],
                [
                    {"NO JOB": 4, "FARMER": 4},
                    {"NO JOB": "-8/s", "FARMER": "+8/s"},
                    {"HOUSE STAY": 2, "FARM STAY": 1},
                    {},
                ],
                False,
                [NoJobArea] * 4 + [FarmerArea] * 4,
                (*area_pos_map[NoJobArea], 26, 6),
                (*add_pos, 0, 0),
            ),
            (
                "2 no job and new worker to logger",
                [
                    {"NO JOB": 2, "FARMER": 1},
                    {"NO JOB": "-3/s", "FARMER": "+2/s"},
                    {},
                    {"NEW WORKER": 1},
                ],
                [
                    {"NO JOB": 2, "FARMER": 1, "LOGGER": 1},
                    {"NO JOB": "-4/s", "FARMER": "+2/s", "LOGGER": "+2/s"},
                    {"HOUSE STAY": 1},
                    {},
                ],
                True,
                [NoJobArea] * 2 + [FarmerArea],
                (
                    *add_pos,
                    30,
                    29,
                ),  # (10, 7) + (10, 3) + (10, 12) -> (35, 30) + (5, 6)
                (*area_pos_map[LoggerArea], 0, 0),
            ),
            (
                "no select, and select",
                [{"NO JOB": 2}, {"NO JOB": "-2/s"}, {}, {}],
                [{"NO JOB": 2}, {"NO JOB": "-2/s"}, {}, {"NO JOB": 1}],
                False,
                [NoJobArea] * 2,
                (0, 0, 0, 0),
                (*area_pos_map[NoJobArea], 5, 6),
            ),
        ]
        for (
            case_name,
            expected_first,
            expected_second,
            expected_is_append,
            add_worker_list,
            select_rect_fiest,
            select_rect_second,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_first=expected_first,
                expected_second=expected_second,
                expected_is_append=expected_is_append,
                add_worker_list=add_worker_list,
                select_rect_fiest=select_rect_fiest,
                select_rect_second=select_rect_second,
            ):
                self.reset()
                try:
                    self.core.game_logic.building_num_map[Building.HOUSE] = 2
                    self.core._update_job_workers_map()  # pylint: disable=W0212
                    for worker in add_worker_list:
                        self._add_worker(worker)
                    select_end_list = [
                        [p + l for p, l in zip(rect[:2], rect[2:])]
                        for rect in [select_rect_fiest, select_rect_second]
                    ]
                    for is_click, is_release, mouse_pos in [
                        # 1回目は選択
                        (True, False, select_rect_fiest[:2]),
                        (False, False, select_end_list[0]),
                        (False, True, select_end_list[0]),
                        # 2回目で操作
                        (True, False, select_rect_second[:2]),
                        (False, False, select_end_list[1]),
                        (False, True, select_end_list[1]),
                    ]:
                        self.test_input.set_is_click(is_click)
                        self.test_input.set_is_release(is_release)
                        self.test_input.set_mouse_pos(*mouse_pos)
                        self.core.update()
                        if is_release:
                            self.core.draw()
                            if not expected_is_append:
                                self._reset_x_pos()
                except Exception as e:  # pylint: disable=W0703
                    self.fail(f"test failed {e}")
                expected_first[2]["HOUSE"] = expected_second[2]["HOUSE"] = 2
                expected_first[1]["HOUSE BUILDER"] = expected_second[1][
                    "HOUSE BUILDER"
                ] = "-10"
                self._check_select_result(*expected_first)
                self._check_select_result(*expected_second)
                self.check()

    @patch.object(Clock, "is_up")
    def test_turn(self, mock):
        test_cases = [
            (
                "harvest food",
                {"FOOD": "1"},
                {"FARMER": 1},
                {"NO JOB": "-1/s", "FARMER": "+2/s", "HOUSE BUILDER": "-10"},
                {"HOUSE": 1 / 3},
                [FarmerArea],
                {},
            ),
            (
                "build house",
                {},
                {"HOUSE BUILDER": 1},
                {"NO JOB": "-1/s", "HOUSE BUILDER": "-10"},
                {"HOUSE": 2 / 3},
                [HouseBuilderArea],
                {Resource.FOOD: 1},
            ),
            (
                "builded house",
                {"HOUSE": 2},
                {"HOUSE BUILDER": 3},
                {"NO JOB": "-3/s", "HOUSE BUILDER": "-10"},
                {},
                [HouseBuilderArea] * 3,
                {Resource.FOOD: 3},
            ),
        ]
        for (
            case_name,
            expected_status,
            expected_worker,
            expected_change,
            expected_progress,
            add_worker_list,
            first_resources,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_status=expected_status,
                expected_worker=expected_worker,
                expected_change=expected_change,
                expected_progress=expected_progress,
                click_pos_list=add_worker_list,
                first_resources=first_resources,
            ):
                self.reset()
                try:
                    self.core.game_logic.resource_map.update(first_resources)
                    self.core.game_logic.build_workload_map[Building.HOUSE] = 1
                    mock.return_value = False
                    for worker in add_worker_list:
                        self._add_worker(worker)
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
        test_cases = [
            ("play again", ({"NO JOB": 1}, {"NO JOB": "-1/s"}, {}, {}), False),
            ("reset", ({}, {}, {}, {"FOOD": "100"}), True),
        ]
        for case_name, expect, reset_flg in test_cases:
            with self.subTest(case_name=case_name, expect=expect, reset_flg=reset_flg):
                self.reset()
                try:
                    self._add_worker(NoJobArea)
                    save_data = self.mock_set_local_storage.call_args.args[0]
                    self.mock_get_local_storage.return_value = save_data
                    self._reset_x_pos()
                    self.core = GameCore(is_reset=reset_flg)
                    self.core.draw()
                except Exception as e:  # pylint: disable=W0703
                    self.fail(f"test failed {e}")
                self._check_result(*expect)
                self.check()

    def test_get_scale_str(self):
        test_cases = [
            ("10", "10", 10),
            ("1K", "1K", 1_000),
            ("1M", "1M", 1_001_001),
            ("2B", "2B", 2_001_001_001),
            ("10T", "10T", 10_001_001_001_001),
            ("1Q", "1Q", 1_999_999_999_999_999),
            ("-1K", "-1K", -1_000),
            ("-1M", "-1M", -1_001_001),
        ]
        for case_name, expected, param in test_cases:
            with self.subTest(case_name=case_name, expected=expected, param=param):
                ret = GameCore.get_scale_str(param)
                self.assertEqual(ret, expected)

    @patch.object(Clock, "is_up")
    def test_game_over(self, mock):
        mock.return_value = False
        self.core.draw()
        self._check_result({}, {}, {}, {})
        self.core.game_logic.building_num_map[Building.HOUSE] = 13
        for _ in range(50):
            self._reset_x_pos()
            self._add_worker(NoJobArea)
        self.core.draw()
        self.put_draw_result([["clear"], ["draw_end"]])

        for expect, is_click, is_release in [(False, True, False), (True, False, True)]:
            self.test_input.set_is_click(is_click)
            self.test_input.set_is_release(is_release)
            self.core.update()
            self.assertEqual(expect, self.core.is_reset())


if __name__ == "__main__":
    unittest.main()
