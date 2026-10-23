import math

from test.test_support import TestParent, TestUnitParent

from src.main import (
    Area,
    Boss,
    Color,
    Console,
    Controller,
    Direct,
    Fee,
    GameObject,
    Instruction,
    InstructionKind,
    Material,
    NavigationPopup,
    Status,
    Workbench,
)
from src.map_generator import AreaKind, MaterialType


class TestStatus(TestParent):
    def test_draw(self):
        m_ctr = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        ctr_list = [
            ("left", (-GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)),
            ("right", (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT // 2)),
            ("up", (GameObject.SCREEN_WIDTH // 2, -GameObject.SCREEN_HEIGHT // 2)),
            ("down", (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT)),
        ]
        test_cases = [
            ("default", 0, 1, 1, (1, 1, 1), m_ctr),
            ("stat pattern 2", 3, 0, 5, (0, 3, 5), m_ctr),
        ] + [(f"center {mess}", 0, 1, 1, (1, 1, 1), ctr) for mess, ctr in ctr_list]
        for (
            case_name,
            expected_loss_heart,
            expected_rest_heart,
            expected_power,
            stat,
            center,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_loss_heart=expected_loss_heart,
                expected_rest_heart=expected_rest_heart,
                expected_power=expected_power,
                stat=stat,
                center=center,
            ):
                self.reset()
                status = Status()
                status.set_stat(*stat)
                status.set_center(*center)
                status.draw()
                draw_image_pos = tuple(
                    c - l // 2 + 1
                    for c, l in zip(
                        center,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                expected = (
                    [
                        (
                            "draw_image",
                            draw_image_pos[0] + i * 9,
                            draw_image_pos[1] + 1,
                            *Status.LOSS_HAERT_IMAGE_POS,
                            False,
                            True,
                        )
                        for i in range(expected_loss_heart)
                    ]
                    + [
                        (
                            "draw_image",
                            draw_image_pos[0] + (expected_loss_heart + i) * 9,
                            draw_image_pos[1] + 1,
                            *Status.HAERT_IMAGE_POS,
                            False,
                            True,
                        )
                        for i in range(expected_rest_heart)
                    ]
                    + [
                        (
                            "draw_image",
                            draw_image_pos[0] + Status.POWER_PADDING,
                            draw_image_pos[1],
                            *Status.WEAPON_IMAGE_POS,
                            False,
                            True,
                        ),
                        (
                            "draw_text",
                            draw_image_pos[0] + Status.POWER_PADDING + 9,
                            draw_image_pos[1] + 2,
                            str(expected_power),
                            Color.WHITE,
                        ),
                    ]
                )
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_draw_material(self):  # pylint: disable=too-many-locals
        """所持資材があるとき画面右上に絵柄と数量が1行描かれること、種類によって
        絵柄が異なること、中心を動かしても画面上の相対位置が変わらないことを
        確認する（サイクル018-2）。HP・武器の既存の描画は test_draw で確認済みのため、
        ここでは固定値（HP満タン・武器の強さ1）を用いる。Plank・Brick を含む場合も
        MaterialType の定義順（Wood → Stone → Plank → Brick）で行が並ぶことをあわせて
        確認する（サイクル024-1）。Hammer を加えた全種類でも、定義順の末尾の行に絵柄
        (1, 20) で描かれることをあわせて確認する（サイクル025-1）。"""
        m_ctr = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        ctr_list = [
            ("left", (-GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)),
            ("right", (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT // 2)),
            ("up", (GameObject.SCREEN_WIDTH // 2, -GameObject.SCREEN_HEIGHT // 2)),
            ("down", (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT)),
        ]
        material_wood = [(MaterialType.WOOD, 3)]
        material_stone = [(MaterialType.STONE, 12)]
        material_both = [(MaterialType.WOOD, 3), (MaterialType.STONE, 12)]
        material_plank = [(MaterialType.PLANK, 5)]
        material_brick = [(MaterialType.BRICK, 7)]
        material_all = [
            (MaterialType.WOOD, 3),
            (MaterialType.STONE, 12),
            (MaterialType.PLANK, 5),
            (MaterialType.BRICK, 7),
        ]
        material_hammer = [(MaterialType.HAMMER, 2)]
        material_all_with_hammer = material_all + material_hammer
        material_none = []
        test_cases = (
            [
                ("wood", material_wood, m_ctr),
                ("stone", material_stone, m_ctr),
                ("wood and stone", material_both, m_ctr),
                ("plank", material_plank, m_ctr),
                ("brick", material_brick, m_ctr),
                ("wood stone plank brick", material_all, m_ctr),
                ("hammer", material_hammer, m_ctr),
                (
                    "wood stone plank brick hammer",
                    material_all_with_hammer,
                    m_ctr,
                ),
                ("none", material_none, m_ctr),
            ]
            + [(f"center {mess}", material_wood, ctr) for mess, ctr in ctr_list]
            + [(f"center {mess} multi", material_both, ctr) for mess, ctr in ctr_list]
        )
        for case_name, materials, center in test_cases:
            with self.subTest(case_name=case_name, materials=materials, center=center):
                self.reset()
                status = Status()
                status.set_stat(1, 1, 1)
                status.set_materials(materials)
                status.set_center(*center)
                status.draw()
                draw_image_pos = tuple(
                    c - l // 2 + 1
                    for c, l in zip(
                        center,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                base_pos = tuple(
                    c - l // 2
                    for c, l in zip(
                        center,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                expected = [
                    (
                        "draw_image",
                        draw_image_pos[0],
                        draw_image_pos[1] + 1,
                        *Status.HAERT_IMAGE_POS,
                        False,
                        True,
                    ),
                    (
                        "draw_image",
                        draw_image_pos[0] + Status.POWER_PADDING,
                        draw_image_pos[1],
                        *Status.WEAPON_IMAGE_POS,
                        False,
                        True,
                    ),
                    (
                        "draw_text",
                        draw_image_pos[0] + Status.POWER_PADDING + 9,
                        draw_image_pos[1] + 2,
                        "1",
                        Color.WHITE,
                    ),
                ] + [
                    entry
                    for i, (material_type, num) in enumerate(materials)
                    for entry in [
                        (
                            "draw_image",
                            base_pos[0] + Status.MATERIAL_ICON_PADDING,
                            base_pos[1] + 1 + i * Status.MATERIAL_ROW_HEIGHT,
                            *Material.IMAGE_POS_MAP[material_type],
                            False,
                            True,
                        ),
                        (
                            "draw_text",
                            base_pos[0]
                            + Status.MATERIAL_ICON_PADDING
                            + Status.MATERIAL_ROW_HEIGHT,
                            base_pos[1] + 3 + i * Status.MATERIAL_ROW_HEIGHT,
                            str(num),
                            Color.WHITE,
                        ),
                    ]
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestController(TestParent):
    def test_stick_move(self):
        d = Direct
        m_ctr = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        ctr_list = [
            ("left", (-GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)),
            ("right", (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT // 2)),
            ("up", (GameObject.SCREEN_WIDTH // 2, -GameObject.SCREEN_HEIGHT // 2)),
            ("down", (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT)),
        ]
        test_cases = [
            ("no hover", d.NUTRAL, (None, None), (100, 100), m_ctr),
            ("no move", d.NUTRAL, (100, 100), (100, 100), m_ctr),
            ("no move edge up", d.NUTRAL, (100, 80), (100, 100), m_ctr),
            ("no move edge down", d.NUTRAL, (100, 120), (100, 100), m_ctr),
            ("no move edge left", d.NUTRAL, (80, 100), (100, 100), m_ctr),
            ("no move edge right", d.NUTRAL, (120, 100), (100, 100), m_ctr),
            ("up move", d.UP, (100, 79), (100, 100), m_ctr),
            ("down move", d.DOWN, (100, 121), (100, 100), m_ctr),
            ("left move", d.LEFT, (79, 100), (100, 100), m_ctr),
            ("right move", d.RIGHT, (121, 100), (100, 100), m_ctr),
            ("right up move", d.RIGHT, (121, 121), (100, 100), m_ctr),
            ("right more up move", d.DOWN, (121, 122), (100, 100), m_ctr),
            ("left down move", d.LEFT, (79, 79), (100, 100), m_ctr),
            ("left more down move", d.UP, (79, 78), (100, 100), m_ctr),
        ] + [
            l
            for mess, ctr in ctr_list
            for l in [
                (f"{mess} center no hover", d.NUTRAL, (None, None), (100, 100), ctr),
                (f"{mess} center no move", d.NUTRAL, (100, 100), (100, 100), ctr),
                (
                    f"{mess} center no move edge up",
                    d.NUTRAL,
                    (100, 80),
                    (100, 100),
                    ctr,
                ),
                (f"{mess} center down move", d.DOWN, (100, 121), (100, 100), ctr),
                (f"{mess} center left down move", d.LEFT, (79, 79), (100, 100), ctr),
            ]
        ]
        for case_name, expected_direct, mouse_pos, start_pos, center_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                mouse_pos=mouse_pos,
                start_pos=start_pos,
                center_pos=center_pos,
            ):
                self.reset()
                controller = Controller()
                controller.update()
                controller.set_center(*center_pos)
                controller.draw()
                self.test_input.set_is_click(True)
                self.test_input.set_mouse_pos(start_pos[0], start_pos[1])
                controller.update()
                controller.draw()
                self.test_input.set_is_click(False)
                self.test_input.set_mouse_pos(mouse_pos[0], mouse_pos[1])
                controller.update()
                controller.draw()
                draw_pos = tuple(
                    s + c - l // 2
                    for s, c, l in zip(
                        start_pos,
                        center_pos,
                        (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                    )
                )
                expected = [
                    ("draw_circ", *draw_pos, 20, Color.BLACK, True),
                    ("draw_circ", *draw_pos, 20, Color.WHITE, False),
                    (
                        "draw_circ",
                        *draw_pos,
                        10,
                        Color.WHITE,
                        True,
                    ),
                    ("draw_circ", *draw_pos, 20, Color.BLACK, True),
                    ("draw_circ", *draw_pos, 20, Color.WHITE, False),
                    (
                        "draw_circ",
                        *(i * 10 + s for i, s in zip(expected_direct.value, draw_pos)),
                        10,
                        Color.WHITE,
                        True,
                    ),
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )
                self.assertEqual(expected_direct, controller.get_direct())

    def test_stick_on_off(self):
        d = Direct
        test_cases = [
            (
                "tap on",
                [d.NUTRAL, d.NUTRAL],
                [(True, False, (100, 100)), (False, False, (100, 100))],
            ),
            (
                "tap move",
                [d.NUTRAL, d.RIGHT],
                [(True, False, (100, 100)), (False, False, (121, 100))],
            ),
            ("no tap move", [None], [(False, False, (121, 100))]),
            (
                "tap move and release",
                [d.NUTRAL, d.RIGHT, None],
                [
                    (True, False, (100, 100)),
                    (False, False, (121, 100)),
                    (False, True, (121, 100)),
                ],
            ),
            (
                "tap 3 move",
                [d.NUTRAL, d.NUTRAL, d.RIGHT, d.LEFT],
                [
                    (True, False, (100, 100)),
                    (False, False, (120, 100)),
                    (False, False, (121, 100)),
                    (False, False, (79, 100)),
                ],
            ),
            (
                "tap release move and tap",
                [d.NUTRAL, None, None, d.NUTRAL],
                [
                    (True, False, (100, 100)),
                    (False, True, (121, 100)),
                    (False, False, (121, 100)),
                    (True, False, (79, 100)),
                ],
            ),
            ("tap", [d.NUTRAL], [(True, False, (100, 100))]),
            ("tap2", [d.NUTRAL], [(True, False, (121, 100))]),
            (
                "tap and release",
                [d.NUTRAL, None],
                [(True, False, (121, 100)), (False, True, (121, 100))],
            ),
            (
                "tap 2 move",
                [d.NUTRAL, d.NUTRAL, d.LEFT],
                [
                    (True, False, (120, 100)),
                    (False, False, (121, 100)),
                    (False, False, (79, 100)),
                ],
            ),
            (
                "release move and tap",
                [None, None, d.NUTRAL],
                [
                    (False, True, (121, 100)),
                    (False, False, (121, 100)),
                    (True, False, (79, 100)),
                ],
            ),
        ]
        for (
            case_name,
            expected_direct_list,
            mouse_action_list,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct_list=expected_direct_list,
                mouse_action_list=mouse_action_list,
            ):
                self.reset()
                expected_list = []
                controller = Controller()
                start_pos = None
                for expected_direct, (is_click, is_release, mouse_pos) in zip(
                    expected_direct_list, mouse_action_list
                ):
                    if is_click:
                        start_pos = mouse_pos
                    self.test_input.set_is_click(is_click)
                    self.test_input.set_is_release(is_release)
                    self.test_input.set_mouse_pos(mouse_pos[0], mouse_pos[1])
                    controller.update()
                    controller.draw()
                    if expected_direct is not None:
                        expected_pos = (
                            i * 10 + s for s, i in zip(start_pos, expected_direct.value)
                        )
                        expected_list.extend(
                            [
                                ("draw_circ", *start_pos, 20, Color.BLACK, True),
                                ("draw_circ", *start_pos, 20, Color.WHITE, False),
                                ("draw_circ", *expected_pos, 10, Color.WHITE, True),
                            ]
                        )
                        self.assertEqual(expected_direct, controller.get_direct())
                    else:
                        self.assertEqual(d.NUTRAL, controller.get_direct())
                self.assertEqual(
                    expected_list,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )


class TestNavigationPopup(TestUnitParent):
    """ナビゲーションのポップアップの描画（サイクル 029-6。U3・U4）。

    画面上部の中央、ステータス表示（HP・武器。y=1〜10）の行より少し下に、背景の矩形
    （黒の塗り + 白の枠）と表示中の指示の目標のアイコンを画面固定で描く。
    """

    # 画面固定の位置の計算式（表示位置は ステータス行の下端 + 余白。U3）
    STATUS_ROW_BOTTOM = 10
    MARGIN = 4
    WIDTH = 40
    HEIGHT = 16
    ICON_PADDING = 4

    @classmethod
    def _expected_calls(cls, center, image_pos):
        origin = tuple(
            c - l // 2
            for c, l in zip(center, (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT))
        )
        x = origin[0] + GameObject.SCREEN_WIDTH // 2 - cls.WIDTH // 2
        y = origin[1] + cls.STATUS_ROW_BOTTOM + cls.MARGIN
        icon_y = y + (cls.HEIGHT - 8) // 2
        return [
            ("draw_rect", x, y, cls.WIDTH, cls.HEIGHT, Color.BLACK, True),
            ("draw_rect", x, y, cls.WIDTH, cls.HEIGHT, Color.WHITE, False),
            (
                "draw_image",
                x + cls.ICON_PADDING,
                icon_y,
                *image_pos,
                False,
                True,
            ),
        ]

    def test_draw_icon(self):
        """表示中の指示の目標の種別ごとのアイコンが描かれる。Tree・Rock は資源の絵柄、
        作業台は作業台、次のブロックのエリアは開放対象（そのエリアの Fee）、ボスは
        ボスの絵柄"""
        center = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        test_cases = [
            (
                "tree",
                Instruction(InstructionKind.UNVEIL, AreaKind.TREE, 0, (3, 2)),
                (1, 8),
            ),
            (
                "rock",
                Instruction(InstructionKind.UNVEIL, AreaKind.ROCK, 0, (3, 2)),
                (1, 12),
            ),
            (
                "workbench",
                Instruction(InstructionKind.UNVEIL, AreaKind.WORKBENCH, 1, (3, 2)),
                Workbench.IMAGE_POS,
            ),
            (
                "next block",
                Instruction(InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 0, (3, 2)),
                Fee.IMAGE_POS_MAP[MaterialType.STONE],
            ),
            (
                "boss",
                Instruction(InstructionKind.DEFEAT_BOSS, None, 4, (100, 100)),
                Boss.IMAGE_POS,
            ),
        ]
        for case_name, instruction, expected_image_pos in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_fee_type(MaterialType.STONE)
                self.test_navigator.set_current(instruction)
                popup = NavigationPopup()
                popup.draw()
                self.assertEqual(
                    self._expected_calls(center, expected_image_pos),
                    self.test_view.get_call_params(),
                )

    def test_draw_icon_gather(self):
        """資材の採集の指示は、採集する資材の絵柄（Material.IMAGE_POS_MAP）が描かれる（U4）。
        背景・枠・矢印は、エリアの開放の指示と同じ（U5）。同じ資材に関わる開放の
        アイコン（Fee.IMAGE_POS_MAP）とは別の絵柄になる"""
        center = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        gather_target_list = [
            (MaterialType.WOOD, AreaKind.TREE, 0),
            (MaterialType.STONE, AreaKind.ROCK, 0),
            (MaterialType.PLANK, AreaKind.WORKBENCH, 1),
            (MaterialType.BRICK, AreaKind.WORKBENCH, 2),
            (MaterialType.HAMMER, AreaKind.WORKBENCH, 3),
        ]
        for material_type, area_kind, block_lv in gather_target_list:
            with self.subTest(material_type=material_type):
                self.reset()
                self.test_map_generator.set_fee_type(material_type)
                self.test_navigator.set_current(
                    Instruction(
                        InstructionKind.GATHER,
                        area_kind,
                        block_lv,
                        (3, 2),
                        material_type,
                    )
                )
                popup = NavigationPopup()
                popup.draw()
                expected_image_pos = Material.IMAGE_POS_MAP[material_type]
                self.assertEqual(
                    self._expected_calls(center, expected_image_pos),
                    self.test_view.get_call_params(),
                )
                self.assertNotEqual(
                    Fee.IMAGE_POS_MAP[material_type], expected_image_pos
                )

    def test_draw_fixed_to_screen(self):
        """画面中心が動いても、画面上の位置は変わらない（画面固定）"""
        s = (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        for center in [(0, 0), (s[0], s[1]), (-s[0] // 2, s[1] * 3)]:
            with self.subTest(center=center):
                self.reset()
                popup = NavigationPopup()
                popup.set_center(*center)
                popup.draw()
                self.assertEqual(
                    self._expected_calls(center, (1, 8)),
                    self.test_view.get_call_params(),
                )

    def test_draw_nothing_when_no_instruction(self):
        """表示中の指示が無い（ナビゲーションの終了）ときは何も描かない"""
        self.test_navigator.set_current(None)
        NavigationPopup().draw()
        self.assertEqual([], self.test_view.get_call_params())

    # 武器の強さの増分表示（サイクル 031-4。D1〜D5）
    POWER_GAIN_FRAMES = 60
    # ステータスの武器の強さの数字（x = 1 + POWER_PADDING + 9）の右、3 桁分の余白（D5）
    POWER_GAIN_X = 1 + Status.POWER_PADDING + 9 + 4 * 3 + 2
    POWER_GAIN_Y = 3

    def _power_gain_calls(self, text):
        center = (GameObject.SCREEN_WIDTH // 2, GameObject.SCREEN_HEIGHT // 2)
        origin = tuple(
            c - l // 2
            for c, l in zip(center, (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT))
        )
        return [
            (
                "draw_text",
                origin[0] + self.POWER_GAIN_X,
                origin[1] + self.POWER_GAIN_Y,
                text,
                Color.YELLOW,
            )
        ]

    def _drawn_power_gain_calls(self, popup):
        self.test_view.reset()
        popup.draw()
        return [
            call for call in self.test_view.get_call_params() if call[0] == "draw_text"
        ]

    def test_draw_power_gain(self):
        """増分は、ステータスの武器の強さの右に黄色の `+N` で描かれる。増分を渡す前は
        描かれない"""
        popup = NavigationPopup()
        self.assertEqual([], self._drawn_power_gain_calls(popup))
        popup.set_power_gain(3)
        self.assertEqual(
            self._power_gain_calls("+3"), self._drawn_power_gain_calls(popup)
        )

    def test_power_gain_disappears(self):
        """増分は update() を表示フレーム数だけ重ねると消える。それまでは描かれ続ける"""
        popup = NavigationPopup()
        popup.set_power_gain(1)
        for _ in range(self.POWER_GAIN_FRAMES - 1):
            popup.update()
        self.assertEqual(
            self._power_gain_calls("+1"), self._drawn_power_gain_calls(popup)
        )
        popup.update()
        self.assertEqual([], self._drawn_power_gain_calls(popup))

    def test_power_gain_overwritten(self):
        """表示中に次の増分を渡すと、前の増分の表示をやめて最新の増分のみを表示し、
        表示フレーム数も数え直す"""
        popup = NavigationPopup()
        popup.set_power_gain(1)
        for _ in range(self.POWER_GAIN_FRAMES // 2):
            popup.update()
        popup.set_power_gain(2)
        self.assertEqual(
            self._power_gain_calls("+2"), self._drawn_power_gain_calls(popup)
        )
        for _ in range(self.POWER_GAIN_FRAMES - 1):
            popup.update()
        self.assertEqual(
            self._power_gain_calls("+2"), self._drawn_power_gain_calls(popup)
        )
        popup.update()
        self.assertEqual([], self._drawn_power_gain_calls(popup))

    def test_draw_power_gain_without_instruction(self):
        """ナビゲーションの指示が無くても、増分の表示は残りフレームの間描かれる"""
        self.test_navigator.set_current(None)
        popup = NavigationPopup()
        popup.set_power_gain(1)
        self.assertEqual(
            self._power_gain_calls("+1"), self._drawn_power_gain_calls(popup)
        )

    def test_not_overlap(self):
        """実装の表示領域が、ステータス表示（上端のステータス行・右上の所持資材）と
        ゲーム状態のポップアップ（Console）と重ならない"""
        popup = NavigationPopup()
        popup.draw()
        _, frame, _ = self.test_view.get_call_params()
        _, x, y, w, h, _, _ = frame
        self.assertLessEqual(self.STATUS_ROW_BOTTOM, y)
        self.assertLessEqual(y + h, Console.CONSOLE_RECT[1])
        self.assertLessEqual(x + w, Status.MATERIAL_ICON_PADDING)

    # 矢印の寸法（ポップアップの左上からの相対位置。アイコンの右側に置く）
    ARROW_CENTER = (28, 8)
    ARROW_TIP = 5
    ARROW_BACK = 3
    ARROW_HALF_WIDTH = 4

    @classmethod
    def _expected_arrow(cls, center, unit):
        """方向の単位ベクトル unit に対する矢印（三角形）の頂点。先端は中心から unit 方向へ
        ARROW_TIP、底辺の 2 点は中心から -unit 方向へ ARROW_BACK、そこから垂直方向へ
        ARROW_HALF_WIDTH"""
        origin = tuple(
            c - l // 2
            for c, l in zip(center, (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT))
        )
        cx = (
            origin[0]
            + GameObject.SCREEN_WIDTH // 2
            - cls.WIDTH // 2
            + cls.ARROW_CENTER[0]
        )
        cy = origin[1] + cls.STATUS_ROW_BOTTOM + cls.MARGIN + cls.ARROW_CENTER[1]
        ux, uy = unit
        px, py = -uy, ux
        tip = (cx + cls.ARROW_TIP * ux, cy + cls.ARROW_TIP * uy)
        back = (cx - cls.ARROW_BACK * ux, cy - cls.ARROW_BACK * uy)
        return (
            "draw_tri",
            round(tip[0]),
            round(tip[1]),
            round(back[0] + cls.ARROW_HALF_WIDTH * px),
            round(back[1] + cls.ARROW_HALF_WIDTH * py),
            round(back[0] - cls.ARROW_HALF_WIDTH * px),
            round(back[1] - cls.ARROW_HALF_WIDTH * py),
            Color.WHITE,
        )

    @staticmethod
    def _target_center(pos):
        return tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos)

    def test_draw_arrow_direction(self):
        """プレイヤーから目標のエリアの中心への方向（8 方向。U7）を矢印が指す。
        画面の座標は y が下向き"""
        d = math.sqrt(0.5)
        target_pos = (10, 10)
        test_cases = [
            ("right", (1, 0), (1, 0)),
            ("down right", (1, 1), (d, d)),
            ("down", (0, 1), (0, 1)),
            ("down left", (-1, 1), (-d, d)),
            ("left", (-1, 0), (-1, 0)),
            ("up left", (-1, -1), (-d, -d)),
            ("up", (0, -1), (0, -1)),
            ("up right", (1, -1), (d, -d)),
        ]
        target_center = self._target_center(target_pos)
        for case_name, direct, unit in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_navigator.set_current(
                    Instruction(InstructionKind.UNVEIL, AreaKind.TREE, 0, target_pos)
                )
                player_pos = tuple(t - 50 * v for t, v in zip(target_center, direct))
                popup = NavigationPopup()
                popup.set_center(*player_pos)
                popup.set_player_pos(*player_pos)
                popup.draw()
                self.assertEqual(
                    self._expected_calls(player_pos, (1, 8))
                    + [self._expected_arrow(player_pos, unit)],
                    self.test_view.get_call_params(),
                )

    def test_arrow_follows_player(self):
        """プレイヤーが動くと、矢印の向きが変わる"""
        target_pos = (10, 10)
        target_center = self._target_center(target_pos)
        self.test_navigator.set_current(
            Instruction(InstructionKind.UNVEIL, AreaKind.TREE, 0, target_pos)
        )
        popup = NavigationPopup()
        arrow_list = []
        for offset, unit in [((-50, 0), (1, 0)), ((0, -50), (0, 1))]:
            self.test_view.reset()
            player_pos = tuple(t + o for t, o in zip(target_center, offset))
            popup.set_center(*player_pos)
            popup.set_player_pos(*player_pos)
            popup.draw()
            arrow_list.append(self.test_view.get_call_params()[-1])
            self.assertEqual(self._expected_arrow(player_pos, unit), arrow_list[-1])
        self.assertNotEqual(arrow_list[0][3:], arrow_list[1][3:])

    def test_no_arrow_when_player_at_target_center(self):
        """プレイヤーが目標のエリアの中心にいる（方向が定まらない）ときは矢印を描かない"""
        target_pos = (10, 10)
        target_center = self._target_center(target_pos)
        self.test_navigator.set_current(
            Instruction(InstructionKind.UNVEIL, AreaKind.TREE, 0, target_pos)
        )
        popup = NavigationPopup()
        popup.set_center(*target_center)
        popup.set_player_pos(*target_center)
        popup.draw()
        self.assertEqual(
            self._expected_calls(target_center, (1, 8)),
            self.test_view.get_call_params(),
        )


class TestNavigationPopupSingleton(TestParent):
    """NavigationPopup はシングルトン。recreate() で増分の表示を持ち越さずに作り直す
    （サイクル 031-4。D1）"""

    def setUp(self):
        super().setUp()
        NavigationPopup._instance = None  # pylint: disable=protected-access

    def tearDown(self):
        super().tearDown()
        NavigationPopup._instance = None  # pylint: disable=protected-access

    def test_create_returns_same_instance(self):
        self.assertIs(NavigationPopup.create(), NavigationPopup.create())

    def test_recreate_drops_power_gain(self):
        popup = NavigationPopup.create()
        popup.set_power_gain(5)
        new_popup = NavigationPopup.recreate()
        self.assertIsNot(popup, new_popup)
        self.assertIs(new_popup, NavigationPopup.create())
        new_popup.draw()
        texts = [c for c in self.test_view.get_call_params() if c[0] == "draw_text"]
        self.assertEqual([], texts)
