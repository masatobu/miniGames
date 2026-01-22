import itertools
import os
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import (  # pylint: disable=C0413
    IView,
    GameCore,
    Action,
    IInput,
    Cursor,
    GameObject,
    Color,
    Count,
    AtBat,
    StrikeZone,
    Diamond,
    EnemyManager,
    Player,
    Console,
)


class TestView(IView):
    def __init__(self):
        self.call_params = []

    def draw_text(self, x, y, text, color=Color.WHITE):
        self.call_params.append(("draw_text", x, y, text, color))

    def draw_tilemap(self):
        self.call_params.append("draw_tilemap")

    def draw_rect(self, x, y, width, height, color, is_fill):
        self.call_params.append(("draw_rect", x, y, width, height, color, is_fill))

    def draw_image(self, x, y, src_tile_x, src_tile_y):
        self.call_params.append(("draw_image", x, y, src_tile_x, src_tile_y))

    def clear(self):
        self.call_params.append("clear")

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
        self.test_view = TestView()
        self.patcher_view = patch(
            "main.PyxelView.create", return_value=self.test_view
        )
        self.mock_view = self.patcher_view.start()
        self.test_input = TestInput()
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_input.stop()


class TestCount(TestParent):
    def test_draw(self):
        test_cases = [
            ("no count", {"B": 0, "S": 0, "O": 0}),
            ("1 ball", {"B": 1, "S": 0, "O": 0}),
            ("1 strike", {"B": 0, "S": 1, "O": 0}),
            ("1 out", {"B": 0, "S": 0, "O": 1}),
            ("full count", {"B": 3, "S": 2, "O": 2}),
        ]
        for (
            case_name,
            count_map,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                count_map=count_map,
            ):
                self.setUp()
                count = Count()
                count.ball, count.strike, count.out = (
                    count_map["B"],
                    count_map["S"],
                    count_map["O"],
                )
                count.draw()
                expected_list = []
                for i, letter in enumerate(["B", "S", "O"]):
                    expected_list.append(
                        (
                            "draw_text",
                            Count.COUNT_OFFSET_X + 2,
                            Count.COUNT_OFFSET_Y + i * 8 + 2,
                            letter,
                            Color.WHITE,
                        )
                    )
                    for j in range(count_map[letter]):
                        expected_list.append(
                            (
                                "draw_image",
                                Count.COUNT_OFFSET_X + (j + 1) * 8,
                                Count.COUNT_OFFSET_Y + i * 8,
                                *Count.LIGHT_IMAGE_POS_MAP[letter],
                            )
                        )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_act(self):
        test_cases = [
            ("one ball", [False], (1, 0, 0), [AtBat.BALL]),
            ("one strike", [False], (0, 1, 0), [AtBat.STRIKE]),
            ("4 ball", [False] * 3 + [True], (0, 0, 0), [AtBat.BALL] * 4),
            ("3 strike", [False] * 3, (0, 0, 1), [AtBat.STRIKE] * 3),
            ("hit", [False, True], (0, 0, 0), [AtBat.STRIKE, AtBat.HIT]),
            ("out", [False, False], (0, 0, 1), [AtBat.STRIKE, AtBat.OUT]),
            ("3 faul", [False] * 3, (0, 2, 0), [AtBat.FAUL] * 3),
        ]
        for case_name, expect_result, expected_count, atbat_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expect_result=expect_result,
                expected_count=expected_count,
                atbat_list=atbat_list,
            ):
                self.setUp()
                count = Count()
                for i, atbat in enumerate(atbat_list):
                    result = count.pitch(atbat)
                    self.assertEqual(expect_result[i], result)
                self.assertEqual(expected_count, (count.ball, count.strike, count.out))
                self.tearDown()


class TestEnemyManager(TestParent):
    def test_sign(self):
        base_set = (0, 0, 0, [False] * 3, {player: [] for player in Player})
        test_cases = (
            [(f"out: {out}", out, *base_set[1:]) for out in range(3)]
            + [(f"ball: {ball}", base_set[0], ball, *base_set[2:]) for ball in range(4)]
            + [
                (f"strike: {strike}", *base_set[:2], strike, *base_set[3:])
                for strike in range(3)
            ]
            + [
                (f"runner: {runner}", *base_set[:3], runner, *base_set[4:])
                for runner in list(itertools.product([True, False], repeat=3))
            ]
            + [
                (f"score: {score}", *base_set[:4], score)
                for score in [
                    {Player.U: [0] * 1, Player.E: [0] * 1},
                    {Player.U: [0] * 4, Player.E: [0] * 4},
                    {Player.U: [0] * 8, Player.E: [0] * 8},
                    {Player.U: [1] * 8, Player.E: [1] * 8},
                    {Player.U: [9] * 8, Player.E: [9] * 8},
                    {Player.U: [9] * 8, Player.E: [0] * 8},
                    {Player.U: [0] * 8, Player.E: [9] * 8},
                ]
            ]
        )
        for case_name, out, ball, strike, runner, score in test_cases:
            with self.subTest(
                case_name=case_name,
                out=out,
                ball=ball,
                strike=strike,
                runner=runner,
                score=score,
            ):
                self.setUp()
                enemy_manager = EnemyManager()
                enemy_manager.set_info(out, ball, strike, runner, score)
                for is_offence in [True, False]:
                    self.assertTrue(
                        enemy_manager.sign(is_offence)
                        in [(x, y) for x in range(5) for y in range(5)] + [None]
                    )
                self.tearDown()


class TestStrikeZone(TestParent):
    def test_draw(self):
        ox, oy = GameObject.STRIKE_ZONE_OFFSET_X, GameObject.STRIKE_ZONE_OFFSET_Y
        test_cases = [
            ("(0, 0)", (0, 0), [(0, 0)]),
            ("(0, 4)", (0, 4), [(0, 4)]),
            ("(4, 0)", (4, 0), [(4, 0)]),
            ("(4, 4)", (4, 4), [(4, 4)]),
            ("(2, 2)", (2, 2), [(2, 2)]),
            ("no select", None, [None]),
            ("2 select", None, [(0, 0), (0, 0)]),
            ("3 select", (0, 0), [(0, 0)] * 3),
            ("select change", (1, 1), [(0, 0), (1, 1)]),
        ]
        for case_name, expected_pos, cursor_pos_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                cursor_pos_list=cursor_pos_list,
            ):
                self.setUp()
                enemy_manager = EnemyManager()
                strike_zone = StrikeZone(enemy_manager)
                for cursor_pos in cursor_pos_list:
                    strike_zone.set(cursor_pos)
                strike_zone.draw()
                expected_list = []
                if expected_pos is not None:
                    expected_list.append(
                        (
                            "draw_rect",
                            expected_pos[0] * 8 + ox,
                            expected_pos[1] * 8 + oy,
                            8,
                            8,
                            Color.LIGHT_RED,
                            False,
                        )
                    )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    @patch.object(EnemyManager, "sign")
    @patch.object(random, "choice")
    def test_get_pitch_result(self, mock_choice, mock_sign):
        ox, oy = GameObject.STRIKE_ZONE_OFFSET_X, GameObject.STRIKE_ZONE_OFFSET_Y
        test_cases = [
            ("defence strike by swing", (AtBat.STRIKE, 0), (0, 0), (2, 2), False),
            ("defence ball left up", (AtBat.BALL, 0), (0, 0), None, False),
            ("defence ball right up", (AtBat.BALL, 0), (4, 0), None, False),
            ("defence ball left down", (AtBat.BALL, 0), (0, 4), None, False),
            ("defence ball right down", (AtBat.BALL, 0), (4, 4), None, False),
            ("defence strike by throw left up", (AtBat.STRIKE, 0), (1, 1), None, False),
            (
                "defence strike by throw right up",
                (AtBat.STRIKE, 0),
                (3, 1),
                None,
                False,
            ),
            (
                "defence strike by throw left down",
                (AtBat.STRIKE, 0),
                (1, 3),
                None,
                False,
            ),
            (
                "defence strike by throw right down",
                (AtBat.STRIKE, 0),
                (3, 3),
                None,
                False,
            ),
            ("defence ball no throw", (AtBat.BALL, 0), None, None, False),
            (
                "defence strike by swing with no throw",
                (AtBat.STRIKE, 0),
                None,
                (2, 2),
                False,
            ),
            ("defence contact to faul", (AtBat.FAUL, 0), (2, 2), (2, 2), False),
            ("defence contact to out", (AtBat.OUT, 0), (2, 2), (2, 2), False),
            ("defence contact to hit 1 base", (AtBat.HIT, 1), (2, 2), (2, 2), False),
            ("defence contact to hit 2 base", (AtBat.HIT, 2), (2, 2), (2, 2), False),
            ("defence contact to hit 3 base", (AtBat.HIT, 3), (2, 2), (2, 2), False),
            ("defence contact to hit 4 base", (AtBat.HIT, 4), (2, 2), (2, 2), False),
            ("offence strike by swing", (AtBat.STRIKE, 0), (2, 2), (0, 0), True),
            ("offence ball left up", (AtBat.BALL, 0), None, (0, 0), True),
            ("offence ball right up", (AtBat.BALL, 0), None, (4, 0), True),
            ("offence ball left down", (AtBat.BALL, 0), None, (0, 4), True),
            ("offence ball right down", (AtBat.BALL, 0), None, (4, 4), True),
            ("offence strike by throw left up", (AtBat.STRIKE, 0), None, (1, 1), True),
            (
                "offence strike by throw right up",
                (AtBat.STRIKE, 0),
                None,
                (3, 1),
                True,
            ),
            (
                "offence strike by throw left down",
                (AtBat.STRIKE, 0),
                None,
                (1, 3),
                True,
            ),
            (
                "offence strike by throw right down",
                (AtBat.STRIKE, 0),
                None,
                (3, 3),
                True,
            ),
            ("offence ball no throw", (AtBat.BALL, 0), None, None, True),
            (
                "offence strike by swing with no throw",
                (AtBat.STRIKE, 0),
                (2, 2),
                None,
                True,
            ),
            ("offence contact to faul", (AtBat.FAUL, 0), (2, 2), (2, 2), True),
            ("offence contact to out", (AtBat.OUT, 0), (2, 2), (2, 2), True),
            ("offence contact to hit 1 base", (AtBat.HIT, 1), (2, 2), (2, 2), True),
            ("offence contact to hit 2 base", (AtBat.HIT, 2), (2, 2), (2, 2), True),
            ("offence contact to hit 3 base", (AtBat.HIT, 3), (2, 2), (2, 2), True),
            ("offence contact to hit 4 base", (AtBat.HIT, 4), (2, 2), (2, 2), True),
        ]
        for (
            case_name,
            expected_pitch_result,
            set_pos,
            opponent_pos,
            is_offence,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pitch_result=expected_pitch_result,
                set_pos=set_pos,
                opponent_pos=opponent_pos,
                is_offence=is_offence,
            ):
                self.setUp()
                mock_choice.return_value = expected_pitch_result
                mock_sign.return_value = opponent_pos
                enemy_manager = EnemyManager()
                strike_zone = StrikeZone(enemy_manager)
                strike_zone.set_offence(is_offence)
                strike_zone.set(set_pos)
                strike_zone.draw()
                self.assertEqual(expected_pitch_result, strike_zone.get_pitch_result())
                strike_zone.draw()
                expected_list = []
                if set_pos is not None:
                    expected_list.extend(
                        [
                            (
                                "draw_rect",
                                set_pos[0] * 8 + ox,
                                set_pos[1] * 8 + oy,
                                8,
                                8,
                                Color.LIGHT_RED,
                                False,
                            )
                        ]
                        * 2
                    )
                if opponent_pos is not None:
                    expected_list.append(
                        (
                            "draw_rect",
                            opponent_pos[0] * 8 + ox + 1,
                            opponent_pos[1] * 8 + oy + 1,
                            6,
                            6,
                            Color.YELLOW,
                            False,
                        )
                    )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()


class TestDiamond(TestParent):
    def test_draw(self):
        test_cases = [
            ("no runner", [0], 0, False),
            ("1 runner", [0, 1], 1, False),
            ("2 runner", [0, 1, 2], 2, False),
            ("3 runner", [0, 1, 2, 3], 3, False),
            ("game over", [], 3, True),
        ]
        for (
            case_name,
            expected,
            put_runner_count,
            is_game_over,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                put_runner_count=put_runner_count,
                is_game_over=is_game_over,
            ):
                self.setUp()
                diamond = Diamond()
                if is_game_over:
                    diamond.set_game_over()
                for _ in range(put_runner_count):
                    diamond.put_runner(1)
                diamond.draw()
                expected_list = []
                for x in expected:
                    expected_list.append(
                        (
                            "draw_image",
                            Diamond.RUNNER_OFFSET_X
                            + (x * Diamond.RUNNER_IMAGE_TILE_DISTANCE) * 8,
                            Diamond.RUNNER_OFFSET_Y,
                            *Diamond.RUNNER_IMAGE_POS,
                        )
                    )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_put_runner(self):
        test_cases = [
            ("1 base hit", 0, [1]),
            ("3 runner hone run", 4, [1] * 3 + [4]),
            ("3 runner 1 base hit", 1, [1] * 4),
            ("2 runner 2 base hit", 2, [2] * 3),
            ("1 runner no hit", 0, [3, 0]),
        ]
        for (
            case_name,
            expected,
            runner_list,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                runner_list=runner_list,
            ):
                self.setUp()
                diamond = Diamond()
                for hit_bases in runner_list:
                    diamond.put_runner(hit_bases)
                self.assertEqual(expected, diamond.get_score())
                self.tearDown()


class TestCursor(TestParent):
    def test_draw_update(self):
        ox, oy = GameObject.STRIKE_ZONE_OFFSET_X, GameObject.STRIKE_ZONE_OFFSET_Y
        test_cases = [
            ("(0, 0)", [(0, 0)], [(ox, oy)]),
            ("(1, 1)", [(1, 1)], [(ox + 8, oy + 8)]),
            (
                "(4, 4)",
                [(4, 4)],
                [
                    (
                        ox + GameObject.STRIKE_ZONE_WIDTH - 1,
                        oy + GameObject.STRIKE_ZONE_HEIGHT - 1,
                    )
                ],
            ),
            (
                "next left up",
                [Action.NEXT.value],
                [(ox + 2 * 8, oy + 6 * 8)],
            ),
            (
                "next right down",
                [Action.NEXT.value],
                [(ox + 3 * 8 - 1, oy + 7 * 8 - 1)],
            ),
            ("less x", [None], [(ox - 1, oy + 8)]),
            ("less y", [None], [(ox + 8, oy - 1)]),
            ("over x", [None], [(ox + GameObject.STRIKE_ZONE_WIDTH, oy + 8)]),
            ("over y", [None], [(ox + 8, oy + GameObject.STRIKE_ZONE_HEIGHT)]),
            ("double", [(0, 0), None], [(ox, oy), (ox, oy)]),
            ("hold", [(0, 0), (0, 0)], [(ox, oy), None]),
            ("double there", [(0, 0), (1, 1)], [(ox, oy), (ox + 8, oy + 8)]),
            ("double over", [(0, 0), None], [(ox, oy), (ox - 1, oy + 8)]),
            ("triple", [(0, 0), None, (0, 0)], [(ox, oy), (ox, oy), (ox, oy)]),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                mouse_pos=mouse_pos,
            ):
                self.setUp()
                cursor = Cursor()
                cursor.update()
                cursor.draw()
                for pos in mouse_pos:
                    if pos is not None:
                        self.test_input.set_mouse_pos(pos[0], pos[1])
                        self.test_input.set_is_click(True)
                    else:
                        self.test_input.set_mouse_pos(None, None)
                        self.test_input.set_is_click(False)
                    cursor.update()
                    cursor.draw()
                expected_list = []
                for e_pos in expected:
                    if e_pos is not None:
                        expected_list.append(
                            (
                                "draw_rect",
                                e_pos[0] * 8 + ox,
                                e_pos[1] * 8 + oy,
                                8,
                                8,
                                Color.RED,
                                False,
                            )
                        )
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_get_action(self):
        ox, oy = GameObject.STRIKE_ZONE_OFFSET_X, GameObject.STRIKE_ZONE_OFFSET_Y
        test_cases = [
            ("strike_zone", [(0, 0)], [Action.STRIKE_ZONE], [(ox, oy)]),
            (
                "2 strike_zone",
                [(0, 0), (1, 0)],
                [Action.STRIKE_ZONE, Action.STRIKE_ZONE],
                [(ox, oy), (ox + 8, oy)],
            ),
            (
                "next strike_zone",
                [Action.NEXT.value, (0, 0)],
                [Action.NEXT, Action.STRIKE_ZONE],
                [(ox + 2 * 8, oy + 6 * 8), (ox, oy)],
            ),
            (
                "next strike_zone 2",
                [(0, 1), Action.NEXT.value, (0, 0)],
                [Action.STRIKE_ZONE, Action.NEXT, Action.STRIKE_ZONE],
                [(ox, oy + 8), (ox + 2 * 8, oy + 6 * 8), (ox, oy)],
            ),
        ]
        for case_name, expected_list, expected_action_list, click_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list=expected_list,
                expected_action_list=expected_action_list,
                click_list=click_list,
            ):
                self.setUp()
                cursor = Cursor()
                self.assertEqual(None, cursor.get_select_pos(), case_name)
                self.assertEqual(None, cursor.get_action(), case_name)
                for i, click in enumerate(click_list):
                    self.test_input.set_mouse_pos(*click)
                    self.test_input.set_is_click(True)
                    cursor.update()
                    cursor.draw()
                    self.assertEqual(None, cursor.get_select_pos(), case_name)
                    self.assertEqual(None, cursor.get_action(), case_name)
                    cursor.update()
                    cursor.draw()
                    self.assertEqual(
                        expected_list[i], cursor.get_select_pos(), case_name
                    )
                    self.assertEqual(
                        expected_action_list[i], cursor.get_action(), case_name
                    )
                expected_draw_list = []
                for i, expected in enumerate(expected_list):
                    expected_cursor = (j * 8 + o for j, o in zip(expected, (ox, oy)))
                    expected_draw_list.append(
                        ("draw_rect", *expected_cursor, 8, 8, Color.RED, False)
                    )
                self.assertEqual(
                    expected_draw_list, self.test_view.get_call_params(), case_name
                )
                self.tearDown()


class TestConsole(TestParent):
    def test_draw(self):
        test_cases = [
            ("win", "You Win", 1, 0),
            ("lose", "You Lose", 0, 1),
            ("draw", "Draw", 1, 1),
            ("no result", None, None, None),
        ]
        for case_name, expected, score_player, score_enemy in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                score_player=score_player,
                score_enemy=score_enemy,
            ):
                self.setUp()
                console = Console()
                console.set_scores(score_player, score_enemy)
                console.draw()
                expected_draw = [
                    ("draw_rect", *Console.CONSOLE_RECT, Color.GREEN, True),
                    ("draw_rect", *Console.CONSOLE_RECT, Color.WHITE, False),
                ]
                if expected is not None:
                    expected_draw.append(
                        (
                            "draw_text",
                            Console.CONSOLE_RECT[0] + 10,
                            Console.CONSOLE_RECT[1] + 5,
                            expected,
                            Color.WHITE,
                        )
                    )
                expected_draw.append(
                    (
                        "draw_text",
                        Console.CONSOLE_RECT[0] + 10,
                        Console.CONSOLE_RECT[1] + 20,
                        "Tap to Continue",
                        Color.WHITE,
                    )
                )
                self.assertEqual(
                    expected_draw,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.tearDown()

    def test_is_tap(self):
        ox, oy = Console.CONSOLE_RECT[0], Console.CONSOLE_RECT[1]
        test_cases = [
            ("left up", True, (ox, oy)),
            ("middle", True, (ox + 8, oy + 8)),
            (
                "right down",
                True,
                (
                    ox + Console.CONSOLE_RECT[2] - 1,
                    oy + Console.CONSOLE_RECT[3] - 1,
                ),
            ),
            ("less x", False, (ox - 1, oy + 8)),
            ("less y", False, (ox + 8, oy - 1)),
            ("over x", False, (ox + Console.CONSOLE_RECT[2], oy + 8)),
            ("over y", False, (ox + 8, oy + Console.CONSOLE_RECT[3])),
        ]
        for case_name, expected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                mouse_pos=mouse_pos,
            ):
                self.setUp()
                console = Console()
                self.test_input.set_mouse_pos(*mouse_pos)
                self.test_input.set_is_click(True)
                console.update()
                self.assertEqual(expected, console.is_tap())
                self.tearDown()


class TestGameCore(TestParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.core = GameCore()

    def tearDown(self):
        self.assertEqual(
            self.expect_view_call,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        return super().tearDown()

    def put_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "clear":
                self.expect_view_call.extend(
                    [
                        "clear",
                    ]
                )
            elif draw_action[0] == "tilemap":
                self.expect_view_call.extend(
                    [
                        "draw_tilemap",
                    ]
                    + [
                        (
                            "draw_text",
                            GameObject.SCORE_BOARD_OFFSET_X + i * 8 + 2,
                            GameObject.SCORE_BOARD_OFFSET_Y + 2,
                            str(i),
                            Color.WHITE,
                        )
                        for i in range(1, 10)
                    ]
                    + [
                        (
                            "draw_text",
                            GameObject.SCORE_BOARD_OFFSET_X + 10 * 8 + 2,
                            GameObject.SCORE_BOARD_OFFSET_Y + 2,
                            "T",
                            Color.WHITE,
                        )
                    ]
                )
            elif draw_action[0] == "count":
                for i, letter in enumerate(["B", "S", "O"]):
                    self.expect_view_call.append(
                        (
                            "draw_text",
                            Count.COUNT_OFFSET_X + 2,
                            Count.COUNT_OFFSET_Y + i * 8 + 2,
                            letter,
                            Color.WHITE,
                        )
                    )
                    for j in range(draw_action[1].get(letter, 0)):
                        self.expect_view_call.append(
                            (
                                "draw_image",
                                Count.COUNT_OFFSET_X + (j + 1) * 8,
                                Count.COUNT_OFFSET_Y + i * 8,
                                *Count.LIGHT_IMAGE_POS_MAP[letter],
                            )
                        )
            elif draw_action[0] == "cursor":
                self.expect_view_call.extend(
                    [
                        (
                            "draw_rect",
                            draw_action[1][0] * 8 + GameObject.STRIKE_ZONE_OFFSET_X,
                            draw_action[1][1] * 8 + GameObject.STRIKE_ZONE_OFFSET_Y,
                            8,
                            8,
                            draw_action[1][2],
                            False,
                        )
                    ]
                )
            elif draw_action[0] == "score":
                for team, y, team_score in [
                    ("U", 1 * 8, draw_action[1]),
                    ("E", 2 * 8, draw_action[2]),
                ]:
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_text",
                                GameObject.SCORE_BOARD_OFFSET_X + 2,
                                GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                                team,
                                Color.WHITE,
                            )
                        ]
                    )
                    for i, score in enumerate(team_score):
                        is_offence = draw_action[3] == team and len(team_score) - 1 == i
                        self.expect_view_call.extend(
                            [
                                (
                                    "draw_text",
                                    GameObject.SCORE_BOARD_OFFSET_X + (i + 1) * 8 + 2,
                                    GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                                    str(score),
                                    Color.LIGHT_RED if is_offence else Color.WHITE,
                                )
                            ]
                        )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_text",
                                GameObject.SCORE_BOARD_OFFSET_X + 10 * 8 + 2,
                                GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                                str(sum(team_score)),
                                Color.WHITE,
                            )
                        ]
                    )
            elif draw_action[0] == "diamond":
                for x in draw_action[1]:
                    self.expect_view_call.append(
                        (
                            "draw_image",
                            Diamond.RUNNER_OFFSET_X
                            + (x * Diamond.RUNNER_IMAGE_TILE_DISTANCE) * 8,
                            Diamond.RUNNER_OFFSET_Y,
                            *Diamond.RUNNER_IMAGE_POS,
                        )
                    )
            elif draw_action[0] == "strike_zone":
                self.expect_view_call.extend(
                    [
                        (
                            "draw_rect",
                            pos[0] * 8 + GameObject.STRIKE_ZONE_OFFSET_X + padding,
                            pos[1] * 8 + GameObject.STRIKE_ZONE_OFFSET_Y + padding,
                            width,
                            width,
                            color,
                            False,
                        )
                        for pos, color, padding, width in [
                            (draw_action[1], Color.LIGHT_RED, 0, 8),
                            (draw_action[2], Color.YELLOW, 1, 6),
                        ]
                        if pos is not None
                    ]
                )
            elif draw_action[0] == "message":
                self.expect_view_call.append(
                    (
                        "draw_text",
                        GameObject.MESSAGE_OFFSET_X,
                        GameObject.MESSAGE_OFFSET_Y,
                        draw_action[1],
                        Color.WHITE,
                    )
                )
            elif draw_action[0] == "console":
                self.expect_view_call.extend(
                    [
                        ("draw_rect", *Console.CONSOLE_RECT, Color.GREEN, True),
                        ("draw_rect", *Console.CONSOLE_RECT, Color.WHITE, False),
                        (
                            "draw_text",
                            Console.CONSOLE_RECT[0] + 10,
                            Console.CONSOLE_RECT[1] + 5,
                            draw_action[1],
                            Color.WHITE,
                        ),
                        (
                            "draw_text",
                            Console.CONSOLE_RECT[0] + 10,
                            Console.CONSOLE_RECT[1] + 20,
                            "Tap to Continue",
                            Color.WHITE,
                        ),
                    ]
                )

    def test_draw(self):
        self.core.draw()
        self.put_draw_result(
            [
                ["clear"],
                ["tilemap"],
                ["score", [0], [], "U"],
                ["count", {}],
                ["diamond", [0]],
                ["message", "Play Ball"],
            ]
        )

    def test_mouse_click(self):
        ox, oy = GameObject.STRIKE_ZONE_OFFSET_X, GameObject.STRIKE_ZONE_OFFSET_Y
        test_cases = [
            ("one click", [(0, 0)], [None], [(ox, oy)]),
            ("two click", [(0, 0), None], [None, (0, 0)], [(ox, oy), (ox, oy)]),
            ("hold", [(0, 0), (0, 0)], [None, None], [(ox, oy), None]),
        ]
        for case_name, expected_cursol, expected_selected, mouse_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_cursol=expected_cursol,
                expected_selected=expected_selected,
                mouse_pos=mouse_pos,
            ):
                self.setUp()
                self.core.update()
                self.core.draw()
                for pos in mouse_pos:
                    if pos is not None:
                        self.test_input.set_mouse_pos(pos[0], pos[1])
                        self.test_input.set_is_click(True)
                    else:
                        self.test_input.set_mouse_pos(None, None)
                        self.test_input.set_is_click(False)
                    self.core.update()
                    self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["tilemap"],
                        ["score", [0], [], "U"],
                        ["count", {}],
                        ["diamond", [0]],
                        ["message", "Play Ball"],
                    ]
                )
                for e_pos, s_pos in zip(expected_cursol, expected_selected):
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["tilemap"],
                            ["score", [0], [], "U"],
                            ["count", {}],
                            ["diamond", [0]],
                        ]
                    )
                    if s_pos is not None:
                        self.put_draw_result([["strike_zone", s_pos, None]])
                    self.put_draw_result([["message", "Play Ball"]])
                    if e_pos is not None:
                        self.put_draw_result([["cursor", [*e_pos, Color.RED]]])
                self.tearDown()

    @patch.object(StrikeZone, "get_pitch_result")
    def test_next(self, mock_get_pitch_result):
        inning_time = 2
        mock_get_pitch_result.side_effect = (
            ([(AtBat.OUT, 0)] + [(AtBat.HIT, 4)] + [(AtBat.OUT, 0)] * 2)
            * inning_time
            * 2
        )
        expected_messages = [
            "Catch Fly OUT",
            "Home Run",
            "Catch Fly OUT",
            "Catch Fly OUT",
        ]
        self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
        self.test_input.set_is_click(True)
        score_map = {"U": [0], "E": []}
        for _ in range(inning_time):
            for turn in ["U", "E"]:
                for pitch in range(4):
                    self.core.update()
                    self.core.update()
                    self.core.draw()
                    offence = turn
                    if pitch == 3:
                        offence = "E" if turn == "U" else "U"
                        score_map[offence].append(0)
                    elif pitch == 1:
                        score_map[turn][-1] = 1
                    self.put_draw_result(
                        [
                            ["clear"],
                            ["tilemap"],
                            ["score", score_map["U"], score_map["E"], offence],
                        ]
                    )
                    out_map = {0: 1, 1: 1, 2: 2}
                    out_count = {} if pitch == 3 else {"O": out_map[pitch]}
                    self.put_draw_result(
                        [
                            ["count", out_count],
                            ["diamond", [0]],
                            ["strike_zone", None, None],
                            ["message", expected_messages[pitch]],
                        ]
                    )

    @patch.object(StrikeZone, "get_pitch_result")
    def test_hit(self, mock_get_pitch_result):
        mock_get_pitch_result.return_value = (AtBat.HIT, 1)
        self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
        self.test_input.set_is_click(True)
        score_map = {"U": [0], "E": []}
        for pitch in range(4):
            self.core.update()
            self.core.update()
            self.core.draw()
            runner = min(pitch + 2, 4)
            if pitch == 3:
                score_map["U"][-1] = 1
            self.put_draw_result(
                [
                    ["clear"],
                    ["tilemap"],
                    ["score", score_map["U"], score_map["E"], "U"],
                    ["count", {}],
                    ["diamond", list(range(runner))],
                    ["message", "1 Base Hit"],
                ]
            )

    @patch.object(EnemyManager, "sign")
    @patch.object(random, "choice")
    def test_pitch(self, mock_choice, mock_sign):
        mock_sign.return_value = (0, 0)
        mock_choice.return_value = (AtBat.OUT, 0)
        self.test_input.set_is_click(True)
        score_map = {"U": [0], "E": []}
        self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.STRIKE_ZONE][0:2])
        self.core.update()
        self.core.update()
        self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
        for i in range(3):
            self.core.update()
            self.core.update()
            self.core.draw()
            out = (i + 1) if i < 2 else 0
            offence = "U"
            if i == 2:
                score_map["E"] = [0]
                offence = "E"
            self.put_draw_result(
                [
                    ["clear"],
                    ["tilemap"],
                    ["score", score_map["U"], score_map["E"], offence],
                    ["count", {"O": out}],
                    ["diamond", [0]],
                    ["strike_zone", (0, 0), (0, 0)],
                    ["message", "Catch Fly OUT"],
                ]
            )

    @patch.object(StrikeZone, "get_pitch_result")
    def test_message(self, mock_pich):
        test_cases = [
            ("out", "Catch Fly OUT", (AtBat.OUT, 0), 0, {"O": 1}, [0]),
            ("strike", "Strike", (AtBat.STRIKE, 0), 0, {"S": 1}, [0]),
            ("ball", "Ball", (AtBat.BALL, 0), 0, {"B": 1}, [0]),
            ("faul", "Faul", (AtBat.FAUL, 0), 0, {"S": 1}, [0]),
            ("1 base hit", "1 Base Hit", (AtBat.HIT, 1), 0, {}, [0, 1]),
            ("2 base hit", "2 Base Hit", (AtBat.HIT, 2), 0, {}, [0, 2]),
            ("3 base hit", "3 Base Hit", (AtBat.HIT, 3), 0, {}, [0, 3]),
            ("home run", "Home Run", (AtBat.HIT, 4), 1, {}, [0]),
        ]
        for case_name, expected, pich_result, score, count, diamond in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                pich_result=pich_result,
                score=score,
                count=count,
                diamond=diamond,
            ):
                self.setUp()
                mock_pich.return_value = pich_result
                self.test_input.set_is_click(True)
                score_map = {"U": [score], "E": []}
                self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
                self.core.update()
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["tilemap"],
                        ["score", score_map["U"], score_map["E"], "U"],
                        ["count", count],
                        ["diamond", diamond],
                        ["strike_zone", None, None],
                        ["message", expected],
                    ]
                )
                self.tearDown()

    @patch.object(StrikeZone, "get_pitch_result")
    def test_game_over(self, mock_pich):
        test_cases = [
            ("win", "You Win", 1, 0),
            ("draw", "Draw", 1, 1),
            ("lose", "You Lose", 0, 1),
        ]
        for case_name, expected_message, player_score, enemy_score in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_message=expected_message,
                player_score=player_score,
                enemy_score=enemy_score,
            ):
                self.setUp()
                mock_pich.return_value = (AtBat.OUT, 0)
                self.test_input.set_is_click(True)
                score_map = self.core.score = {
                    Player.U: [player_score] * 9,
                    Player.E: [enemy_score] * 8 + [0],
                }
                self.test_input.set_mouse_pos(*Cursor.AVAIL_POS_MAP[Action.NEXT][0:2])
                for _ in range(3):
                    self.core.update()
                    self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ["clear"],
                        ["tilemap"],
                        ["score", score_map[Player.U], score_map[Player.E], None],
                        ["count", {}],
                        ["diamond", []],
                        ["strike_zone", None, None],
                        ["message", "Game Over"],
                        ["console", expected_message],
                    ]
                )
                self.assertEqual(False, self.core.is_reset())
                self.test_input.set_mouse_pos(*Console.CONSOLE_RECT[0:2])
                self.core.update()
                self.assertEqual(True, self.core.is_reset())
                self.tearDown()


if __name__ == "__main__":
    unittest.main()
