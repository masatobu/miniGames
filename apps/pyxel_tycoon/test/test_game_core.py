import traceback
from unittest.mock import MagicMock, Mock, patch

from test.test_support import TestSaveStore, TestUnitParent

from src.main import (
    Area,
    Color,
    Console,
    Direct,
    Fee,
    GameCore,
    GameObject,
    Enemy,
    Material,
    PyxelController,
    Resource,
    Status,
    Unit,
    Workbench,
)
from src.map_generator import MaterialType, WorkbenchParam


class TestGameCore(TestUnitParent):
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.core = GameCore()

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.core = GameCore()

    def check(self):
        """描画結果の検証ヘルパー。test_field.py の同名ヘルパーと実装が一致するが、
        check / put_draw_result / put_unit_draw_result は一体で各クラスの検証方式を
        構成しており、扱う描画アクション種別がクラスごとに異なる。check のみを親クラスへ
        切り出すとヘルパー群が分断されるため、各クラス固有のヘルパーとして扱う
        （検討の経緯は ID-011_subtasks.md「ID-011-10」を参照）"""
        # pylint: disable=duplicate-code
        self.assertEqual(
            self.expect_view_call,
            self.test_view.get_call_params(),
            self.test_view.get_call_params(),
        )
        self.assertEqual(
            self.expect_unit_view_call,
            self.test_unit_view.get_call_params(),
            self.test_unit_view.get_call_params(),
        )

    def put_draw_result(self, draw_action_list):
        try:
            for draw_action in draw_action_list:
                if draw_action[0] == "clear":
                    self.expect_view_call.append(draw_action)
                elif draw_action[0] == "controller":
                    expected_center = tuple(
                        s + c - l // 2
                        for s, c, l in zip(
                            draw_action[1:3],
                            draw_action[3:5],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                        )
                    )
                    expected_stick = tuple(
                        d * 10 + s
                        for s, d in zip(
                            expected_center,
                            draw_action[5].value,
                        )
                    )
                    self.expect_view_call.extend(
                        [
                            ("draw_circ", *expected_center, 20, Color.BLACK, True),
                            ("draw_circ", *expected_center, 20, Color.WHITE, False),
                            ("draw_circ", *expected_stick, 10, Color.WHITE, True),
                        ]
                    )
                elif draw_action[0] == "area":
                    s = Area.SIZE
                    self.expect_view_call.extend(
                        [
                            ("draw_rect", s * x, s * y, s, s, Color.GREEN, False)
                            for x, y in draw_action[1]
                        ]
                    )
                    self.expect_view_call.extend(
                        [
                            ("draw_rect", s * x, s * y, s, s, Color.DARK_BLUE, False)
                            for x, y in draw_action[2]
                        ]
                    )
                elif draw_action[0] == "status":
                    expected_image_center = tuple(
                        c - l // 2 + 1
                        for c, l in zip(
                            draw_action[1:3],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                        )
                    )
                    expected_loss_heart = draw_action[3][1] - draw_action[3][0]
                    expected_rest_heart = draw_action[3][0]
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_image",
                                expected_image_center[0] + i * 9,
                                expected_image_center[1] + 1,
                                *Status.LOSS_HAERT_IMAGE_POS,
                                False,
                                True,
                            )
                            for i in range(expected_loss_heart)
                        ]
                    )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_image",
                                expected_image_center[0]
                                + (expected_loss_heart + i) * 9,
                                expected_image_center[1] + 1,
                                *Status.HAERT_IMAGE_POS,
                                False,
                                True,
                            )
                            for i in range(expected_rest_heart)
                        ]
                    )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_image",
                                expected_image_center[0] + Status.POWER_PADDING,
                                expected_image_center[1],
                                *Status.WEAPON_IMAGE_POS,
                                False,
                                True,
                            ),
                            (
                                "draw_text",
                                expected_image_center[0] + Status.POWER_PADDING + 9,
                                expected_image_center[1] + 2,
                                str(draw_action[3][2]),
                                Color.WHITE,
                            ),
                        ]
                    )
                elif draw_action[0] == "material":
                    self.expect_view_call.extend(
                        self._material_draw_calls(*draw_action[1:3], draw_action[3])
                    )
                elif draw_action[0] == "navigation":
                    # ナビゲーションのポップアップ（Tree のエリアの指示）。位置の計算式は
                    # test_screen_object.py の TestNavigationPopup の期待値と同じ
                    origin = tuple(
                        c - l // 2
                        for c, l in zip(
                            draw_action[1:3],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                        )
                    )
                    popup_x = origin[0] + GameObject.SCREEN_WIDTH // 2 - 20
                    popup_y = origin[1] + 10 + 4
                    self.expect_view_call.extend(
                        [
                            ("draw_rect", popup_x, popup_y, 40, 16, Color.BLACK, True),
                            ("draw_rect", popup_x, popup_y, 40, 16, Color.WHITE, False),
                            ("draw_image", popup_x + 4, popup_y + 4, 1, 8, False, True),
                            # 目標（エリア (3, 2)）はプレイヤーの右にあるため、右向きの矢印
                            (
                                "draw_tri",
                                popup_x + 28 + 5,
                                popup_y + 8,
                                popup_x + 28 - 3,
                                popup_y + 8 + 4,
                                popup_x + 28 - 3,
                                popup_y + 8 - 4,
                                Color.WHITE,
                            ),
                        ]
                    )
                elif draw_action[0] == "console":
                    expected_pos = tuple(
                        c - l // 2 + r
                        for c, l, r in zip(
                            draw_action[1:3],
                            (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT),
                            Console.CONSOLE_RECT[0:2],
                        )
                    )
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                *expected_pos,
                                *Console.CONSOLE_RECT[2:4],
                                Color.GREEN,
                                True,
                            ),
                            (
                                "draw_rect",
                                *expected_pos,
                                *Console.CONSOLE_RECT[2:4],
                                Color.WHITE,
                                False,
                            ),
                            (
                                "draw_text",
                                expected_pos[0] + 10,
                                expected_pos[1] + 5,
                                draw_action[3],
                                Color.WHITE,
                            ),
                            (
                                "draw_text",
                                expected_pos[0] + 10,
                                expected_pos[1] + 20,
                                "Tap to Continue",
                                Color.WHITE,
                            ),
                        ]
                    )
                elif draw_action[0] in ["enemy_power", "fee_num"]:
                    # test_field.py の同名分岐と実装が一致するが、put_draw_result が
                    # 扱う描画アクション種別はクラスごとに異なるため、各クラス固有の分岐
                    # として扱う（検討の経緯は ID-011_subtasks.md「ID-011-10」を参照）
                    # pylint: disable=duplicate-code
                    stat = str(draw_action[3])
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_text",
                                *tuple(
                                    p - d - l
                                    for p, d, l in zip(
                                        draw_action[1:3],
                                        Unit.STAT_PADDING,
                                        (len(stat) * Unit.LETTER_SIZE, 0),
                                    )
                                ),
                                stat,
                                Color.WHITE,
                            )
                        ]
                    )
        except Exception as e:  # pylint: disable=W0718
            print(e)
            traceback.print_exc()

    def _material_draw_calls(self, pos_x, pos_y, materials):
        # test_screen_object.py の TestStatus.test_draw_material の期待値計算と
        # 実装が一致するが、put_draw_result はクラスごとの描画アクション種別を扱う
        # ヘルパーであり、test_screen_object.py 側は Status 単体の期待値計算のため、
        # 共通化せず各クラス固有のヘルパーとして扱う
        # （検討の経緯は ID-011_subtasks.md「ID-011-10」を参照）
        # pylint: disable=duplicate-code
        base_pos = tuple(
            c - l // 2
            for c, l in zip(
                (pos_x, pos_y), (GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
            )
        )
        return [
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

    def put_unit_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            if draw_action[0] == "player":
                self.expect_unit_view_call.append(
                    ("draw_unit", *draw_action[1:3], 1, 0, *draw_action[3:6])
                )
            elif draw_action[0] == "fee":
                self.expect_unit_view_call.append(
                    (
                        "draw_unit",
                        *draw_action[1:3],
                        *Fee.IMAGE_POS_MAP[MaterialType.WOOD],
                        *draw_action[3:6],
                    )
                )

    def _put_result_default_fee(self):
        for axis in [(3, 2), (2, 1), (1, 2), (2, 3)]:
            pos = tuple(p * Area.SIZE + Area.SIZE // 2 for p in axis)
            # test_field.py の同名リストと記述が一致するが、各テストケース固有の
            # 期待値データであり、共通化せず各クラス固有のデータとして扱う
            # （検討の経緯は ID-011_subtasks.md「ID-011-10」を参照）
            # pylint: disable-next=duplicate-code
            self.put_unit_draw_result(
                [
                    (
                        "fee",
                        *pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    )
                ]
            )
            self.put_draw_result([("fee_num", *pos, 1)])

    def test_draw(self):
        self.core.draw()
        self.put_draw_result(
            [
                ("clear", 100, 100),
                ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
            ]
        )
        self._put_result_default_fee()
        self.put_draw_result(
            [
                ("status", 100, 100, (3, 3, 1)),
                ("navigation", 100, 100),
            ]
        )
        self.put_unit_draw_result(
            [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
        )
        self.check()

    def test_workbench_popup_world_pos(self):
        """GameCore.draw 経由でも、ポップアップはワールド座標で描かれ、プレイヤーが
        同じエリア内で動いても座標は変わらない（サイクル 024-12）。カメラはプレイヤーの
        位置に追従する（clear の引数）ため、画面上では作業台と一緒に動く。"""
        s = Area.SIZE
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        popup_calls_list = []
        for player_pos in [workbench_pos, (workbench_pos[0] + 10, workbench_pos[1])]:
            self.reset()
            self.test_map_generator.set_material_type(MaterialType.PLANK)
            self.test_map_generator.set_workbench(
                WorkbenchParam((MaterialType.WOOD,), 10, 60)
            )
            self.core.field.unit_map = {area_axis: [Workbench(*workbench_pos)]}
            self.core.field.player.pos = player_pos
            self.core.draw()
            calls = self.test_view.get_call_params()
            self.assertEqual(("clear", *player_pos), calls[0])
            wood_image_pos = Material.IMAGE_POS_MAP[MaterialType.WOOD]
            popup_calls_list.append(
                [
                    call
                    for call in calls
                    if (call[0] == "draw_image" and call[3:5] == wood_image_pos)
                    or (call[0] == "draw_text" and call[3] == "0/10")
                ]
            )
        self.assertEqual(2, len(popup_calls_list[0]))
        self.assertEqual(popup_calls_list[0], popup_calls_list[1])

    def test_material_pickup(self):
        """開始直後は資材の項目が無く、資材に接触した後の描画で右上に項目が現れる
        ことを GameCore.update / GameCore.draw 経由で確認する（サイクル 018-2。配線の確認）。"""
        area_axis = (2, 2)
        material_pos = self.core.field.player.get_pos()
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        material = Material(*material_pos)
        material.set_num(1)
        self.core.field.unit_map.setdefault(area_axis, []).append(material)
        self.core.update()
        self.core.draw()
        self.put_draw_result(
            [
                ("clear", 100, 100),
                ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
            ]
        )
        self._put_result_default_fee()
        self.put_draw_result(
            [
                ("status", 100, 100, (3, 3, 1)),
                ("material", 100, 100, [(MaterialType.WOOD, 1)]),
                ("navigation", 100, 100),
            ]
        )
        self.put_unit_draw_result(
            [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
        )
        self.check()

    def _drawn_power_texts(self, expected_power):
        """描画結果のうち、ステータスの武器の強さの位置のテキスト（表示の x は
        Status.POWER_PADDING の右）を返す"""
        x = 1 + Status.POWER_PADDING + 9 - GameObject.SCREEN_WIDTH // 2 + 100
        return [
            call
            for call in self.test_view.get_call_params()
            if call[0] == "draw_text"
            and call[1] == x
            and call[3] == str(expected_power)
        ]

    def test_status_power_updated_on_clear(self):
        """指示のクリアで上がった武器の強さが、次の描画でステータスに表示され、
        ゲームを作り直す（リセット）と初期の強さへ戻る（サイクル 031-3。U3）。
        上昇量は TestMapGenerator が `block_lv * 100 + order + 1` を返す"""
        fee_pos = self.core.field.player.get_pos()
        area_axis = (2, 2)
        fee = Fee(*fee_pos)
        self.core.field.unit_map.setdefault(area_axis, []).append(fee)
        self.core.field.player.add_material(fee.get_type(), fee.get_num())
        self.test_navigator.set_cleared([0, 5])
        self.core.update()
        self.test_view.reset()
        self.core.draw()
        expected_power = 1 + 1 + 101
        self.assertEqual(1, len(self._drawn_power_texts(expected_power)))

        self.reset()
        self.core.draw()
        self.assertEqual(1, len(self._drawn_power_texts(1)))

    def test_power_gain_drawn_through_core(self):
        """指示のクリアの増分が GameCore の描画で黄色の文字として描かれ、update() を
        表示フレーム数だけ重ねると消える（サイクル 031-4。D1〜D3）。set_power_gain は
        Field.update 内、ポップアップの update() はその後に呼ばれるため、クリアした
        update() の分を含めて 60 回目の update() で消える"""
        fee_pos = self.core.field.player.get_pos()
        fee = Fee(*fee_pos)
        self.core.field.unit_map.setdefault((2, 2), []).append(fee)
        self.core.field.player.add_material(fee.get_type(), fee.get_num())
        self.test_navigator.set_cleared([0, 5])
        self.core.update()

        def gain_texts():
            self.test_view.reset()
            self.core.draw()
            return [
                call
                for call in self.test_view.get_call_params()
                if call[0] == "draw_text" and call[4] == Color.YELLOW
            ]

        self.assertEqual(["+102"], [call[3] for call in gain_texts()])
        self.test_navigator.set_cleared([])
        for _ in range(58):
            self.core.update()
        self.assertEqual(["+102"], [call[3] for call in gain_texts()])
        self.core.update()
        self.assertEqual([], gain_texts())

    def test_player_walk(self):
        self.test_input.set_is_click(True)
        self.test_input.set_mouse_pos(100, 100)
        self.core.update()
        self.test_input.set_is_click(False)
        self.test_input.set_mouse_pos(50, 100)
        self.core.update()

        self.core.draw()
        self.put_draw_result(
            [
                ("clear", 99, 100),
                ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
            ]
        )
        self._put_result_default_fee()
        self.put_draw_result(
            [
                ("status", 99, 100, (3, 3, 1)),
                ("navigation", 99, 100),
                ("controller", 100, 100, 99, 100, Direct.LEFT),
            ]
        )
        self.put_unit_draw_result(
            [("player", 99, 100, Direct.LEFT, Direct.LEFT, False)]
        )
        self.check()

    def test_game_over(self):
        test_cases = [
            ("game over by no hp", 0, "Game Over", False),
            ("game clear", 3, "Game Clear", True),
        ]
        for case_name, hp, message, is_clear in test_cases:
            with self.subTest(
                case_name=case_name,
                hp=hp,
                message=message,
                is_clear=is_clear,
            ):
                self.reset()
                self.core.field.player.hp = hp
                self.core.field.flg_clear = is_clear
                self.core.update()
                self.core.draw()
                self.put_draw_result(
                    [
                        ("clear", 100, 100),
                        ("area", [(2, 2)], [(3, 2), (2, 1), (1, 2), (2, 3)]),
                    ]
                )
                self._put_result_default_fee()
                self.put_draw_result(
                    [
                        ("status", 100, 100, (hp, 3, 1)),
                        ("console", 100, 100, message),
                    ]
                )
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                self.assertEqual(False, self.core.is_reset())
                self.test_input.set_is_click(True)
                self.test_input.set_mouse_pos(*Console.CONSOLE_RECT[0:2])
                self.core.update()
                self.assertEqual(True, self.core.is_reset())
                self.check()


class TestGameCoreSave(TestUnitParent):
    """GameCore の保存と復元・保存のタイミング（ID-033 サイクル 033-5。D2・U4）。
    保存の仕組みはテストダブル（TestSaveStore）へ差し替える。保存データは
    {"game": {"generator", "navigator", "field"}}、ゲーム無しは {"game": None}"""

    FEE_AXIS = (3, 2)

    def _core(self, store):
        return GameCore(store)

    def _open_fee(self, core):
        """プレイヤーを開放対象 Fee（3, 2）へ置き、資材を足して 1 フレーム進める"""
        s = Area.SIZE
        core.field.player.pos = tuple(p * s + s // 2 for p in self.FEE_AXIS)
        core.field.player.add_material(MaterialType.WOOD, 1)
        core.update()

    def _pickup_material(self, core):
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        material = Material(*core.field.player.get_pos())
        material.set_num(1)
        core.field.unit_map.setdefault((2, 2), []).append(material)
        core.update()

    def _defeat_boss(self, core):
        core.field.unit_map[(3, 2)][0].set_hp(0)
        core.update()

    def test_new_game_without_saved_data(self):
        """起動時に保存データを 1 度だけ読み込み、無ければ復元せず新しいゲームになる。
        起動しただけでは保存しない"""
        store = TestSaveStore()
        with patch("src.map_generator.AreaBlockAlgorithmGenerator.restore") as gen:
            with patch("src.main.Navigator.restore") as nav:
                core = self._core(store)
        self.assertEqual(1, store.load_count)
        gen.assert_not_called()
        nav.assert_not_called()
        self.assertEqual([], store.save_calls)
        self.assertEqual((3, 3, 1), core.field.get_player_status())

    def test_new_game_with_no_game_data(self):
        """保存データが「ゲーム無し」のときも、復元せず新しいゲームになる"""
        store = TestSaveStore({"game": None})
        with patch("src.map_generator.AreaBlockAlgorithmGenerator.restore") as gen:
            with patch("src.main.Navigator.restore") as nav:
                self._core(store)
        gen.assert_not_called()
        nav.assert_not_called()

    def test_restore_from_saved_data(self):
        """保存データがあれば、生成器 → navigator の順に保存データから復元し、Field も
        同じ状態（開放済みエリア・プレイヤー）から始まる"""
        saved_store = TestSaveStore()
        saved_core = self._core(saved_store)
        saved_core.field.player.add_power(4)
        self._open_fee(saved_core)
        saved = saved_store.stored["game"]

        manager = Mock()
        with patch(
            "src.map_generator.AreaBlockAlgorithmGenerator.restore",
            manager.generator,
        ):
            with patch("src.main.Navigator.restore", manager.navigator):
                core = self._core(TestSaveStore(saved_store.stored))
        self.assertEqual(
            [
                ("generator", (saved["generator"],)),
                ("navigator", (saved["navigator"],)),
            ],
            [(name, args) for name, args, _ in manager.mock_calls],
        )
        self.assertEqual(
            saved_core.field.get_player_status(), core.field.get_player_status()
        )
        self.assertEqual(
            saved_core.field.get_player_materials(), core.field.get_player_materials()
        )
        self.assertEqual(saved_core.field.to_save_data(), core.field.to_save_data())

    def test_saved_data_contains_unit_states(self):
        """イベントのフレームに保存する Field の保存データにユニットの状態が含まれ、
        それを読み込んだ GameCore が同じユニットの状態から始まる（ID-034）"""
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        store = TestSaveStore()
        core = self._core(store)
        self._open_fee(core)

        saved_field = store.stored["game"]["field"]
        resource_entries = [
            entry for entry in saved_field["units"] if "resource" in entry
        ]
        self.assertEqual([list(self.FEE_AXIS)], [e["area"] for e in resource_entries])

        with patch("src.map_generator.AreaBlockAlgorithmGenerator.restore"):
            with patch("src.main.Navigator.restore"):
                restored = self._core(TestSaveStore(store.stored))
        self.assertEqual(saved_field, restored.field.to_save_data())

    def test_save_on_navigator_event(self):
        """ナビゲーションへイベントを送ったフレーム（エリアの開放・資材の拾得）で保存し、
        保存データに生成器・navigator・Field の状態がまとまっている"""
        for case_name, act in [
            ("unveil", self._open_fee),
            ("gather", self._pickup_material),
        ]:
            with self.subTest(case_name=case_name):
                self.reset()
                store = TestSaveStore()
                core = self._core(store)
                act(core)
                self.assertEqual(1, len(store.save_calls))
                self.assertEqual(
                    {
                        "game": {
                            "generator": {"marker": "generator"},
                            "navigator": {"marker": "navigator"},
                            "field": core.field.to_save_data(),
                        }
                    },
                    store.stored,
                )

    def test_not_save_without_event(self):
        """イベントの無いフレームでは保存しない"""
        store = TestSaveStore()
        core = self._core(store)
        for _ in range(3):
            core.update()
            core.draw()
        self.assertEqual([], store.save_calls)

    def test_not_save_on_game_over(self):
        """ゲームオーバーになったフレームでは保存しない（最後のイベントの時点が残る）"""
        store = TestSaveStore()
        core = self._core(store)
        self._open_fee(core)
        saved = store.stored
        core.field.player.hp = 0
        core.draw()
        core.update()
        self.assertEqual(1, len(store.save_calls))
        self.assertEqual(saved, store.stored)

    def _start_area_center(self):
        s = Area.SIZE
        return tuple(p * s + s // 2 for p in (2, 2))

    def _drop_by_resource(self, core):
        """資源を置いて、採取の完了のフレームまで進める"""
        core.field.unit_map.setdefault((2, 2), []).append(
            Resource(*self._start_area_center())
        )
        core.field.player.pos = self._start_area_center()
        # 接触した最初の update() は消費フレームにならないため、完了には +1 回必要
        for _ in range(Resource.HARVEST_FRAMES + 1):
            core.update()

    def _drop_by_workbench(self, core):
        self.test_map_generator.set_workbench(
            WorkbenchParam((MaterialType.WOOD,), 1, 10)
        )
        workbench = Workbench(*self._start_area_center())
        core.field.unit_map.setdefault((2, 2), []).append(workbench)
        core.field.player.pos = self._start_area_center()
        core.field.player.add_material(MaterialType.WOOD, 1)
        for _ in range(Workbench.INPUT_INTERVAL_FRAMES + 10):
            core.update()

    def _drop_by_enemy(self, core):
        enemy = Enemy(*self._start_area_center())
        enemy.set_hp(0)
        core.field.unit_map.setdefault((2, 2), []).append(enemy)
        core.field.player.pos = (self._start_area_center()[0] + 100, 0)

    def test_save_on_material_drop(self):
        """資源の採取の完了・作業台の加工の完了・敵の撃破で資材が落ちたフレームに保存し、
        保存データに落ちた資材が含まれ、それを読み込んだ GameCore で資材を拾える（ID-034 サイクル 034-7）"""
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        self.test_map_generator.set_material_ret_zero(False)
        for case_name, prepare in [
            ("resource", self._drop_by_resource),
            ("workbench", self._drop_by_workbench),
            ("enemy", self._drop_by_enemy),
        ]:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                self.test_map_generator.set_material_ret_zero(False)
                store = TestSaveStore()
                core = self._core(store)
                prepare(core)
                if case_name == "enemy":
                    self.assertEqual([], store.save_calls)
                    core.update()
                self.assertEqual(1, len(store.save_calls))
                saved_field = store.stored["game"]["field"]
                self.assertEqual(core.field.to_save_data(), saved_field)
                drops = [
                    unit
                    for unit in core.field.unit_map[(2, 2)]
                    if isinstance(unit, Material)
                ]
                self.assertEqual(1, len(drops))

                with patch("src.map_generator.AreaBlockAlgorithmGenerator.restore"):
                    with patch("src.main.Navigator.restore"):
                        restored = self._core(TestSaveStore(store.stored))
                restored.field.player.pos = drops[0].get_pos()
                before = restored.field.get_player_materials()
                restored.update()
                self.assertNotEqual(before, restored.field.get_player_materials())

    def test_not_save_before_material_drop(self):
        """資材が落ちる前（採取の途中）のフレームでは保存しない"""
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        store = TestSaveStore()
        core = self._core(store)
        core.field.unit_map.setdefault((2, 2), []).append(
            Resource(*self._start_area_center())
        )
        core.field.player.pos = self._start_area_center()
        for _ in range(Resource.HARVEST_FRAMES):
            core.update()
        self.assertEqual([], store.save_calls)

    def test_save_once_when_drop_and_event_overlap(self):
        """資材が落ちるフレームにナビゲーションへのイベントが重なっても、保存は 1 回"""
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        self.test_map_generator.set_material_ret_zero(False)
        store = TestSaveStore()
        core = self._core(store)
        enemy = Enemy(*self._start_area_center())
        enemy.set_hp(0)
        core.field.unit_map.setdefault((2, 2), []).append(enemy)
        self._open_fee(core)
        self.assertTrue(core.field.area_map[self.FEE_AXIS].unveiled)
        self.assertTrue(
            any(isinstance(u, Material) for u in core.field.unit_map[(2, 2)])
        )
        self.assertEqual(1, len(store.save_calls))

    def test_clear_overwrites_with_no_game(self):
        """ボスを倒してクリアしたフレームでは、最終的に「ゲーム無し」で上書きされ、
        それを読み込むと新しいゲームになる"""
        self.test_map_generator.set_boss_pos(self.FEE_AXIS)
        store = TestSaveStore()
        core = self._core(store)
        self._defeat_boss(core)
        self.assertTrue(core.field.is_clear())
        self.assertEqual({"game": None}, store.stored)
        self.assertEqual({"game": None}, store.save_calls[-1])

        with patch("src.map_generator.AreaBlockAlgorithmGenerator.restore") as gen:
            self._core(TestSaveStore(store.stored))
        gen.assert_not_called()


class TestPyxelControllerSave(TestUnitParent):
    """PyxelController の読み込み待ちとリセット時の上書き保存（ID-033 サイクル 033-6。
    §3.12・§3.16 技術制約）。pyxel をモックし、保存の仕組みをテストダブルへ差し替える
    （pyxel_shop_grow の TestAppLoadWait・TestAppReset と同じ形）"""

    def setUp(self):
        super().setUp()
        self.mock_pyxel = MagicMock()
        patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        patcher_pyxel.start()
        self.addCleanup(patcher_pyxel.stop)
        self.store = TestSaveStore()
        patcher_store = patch("src.main.SaveStore", return_value=self.store)
        patcher_store.start()
        self.addCleanup(patcher_store.stop)

    def _app_with_core(self):
        """GameCore が生成済みの PyxelController を作る（読み込み待ちのフレームを進める）"""
        app = PyxelController()
        for _ in range(PyxelController.LOAD_WAIT_FRAMES):
            app.update()
        return app

    def test_core_not_created_before_wait_frames(self):
        """待機フレーム数に満たない間は GameCore を作らず（保存データも読まない）、
        その間の draw は例外にならない"""
        app = PyxelController()
        for _ in range(PyxelController.LOAD_WAIT_FRAMES - 1):
            app.update()
            app.draw()
        self.assertIsNone(app.game_core)
        self.assertEqual(0, self.store.load_count)

    def test_core_created_from_saved_data_after_wait_frames(self):
        """待機フレーム数に達すると、保存データから GameCore を作る"""
        saved_core = GameCore(self.store)
        saved_core.field.player.add_power(4)
        self._save_after_open_fee(saved_core)
        saved = self.store.stored["game"]
        self.store.load_count = 0

        with patch(
            "src.map_generator.AreaBlockAlgorithmGenerator.restore"
        ) as gen, patch("src.main.Navigator.restore") as nav:
            app = self._app_with_core()
        gen.assert_called_once_with(saved["generator"])
        nav.assert_called_once_with(saved["navigator"])
        self.assertIsInstance(app.game_core, GameCore)
        self.assertEqual(1, self.store.load_count)

    @staticmethod
    def _save_after_open_fee(core):
        s = Area.SIZE
        core.field.player.pos = tuple(p * s + s // 2 for p in (3, 2))
        core.field.player.add_material(MaterialType.WOOD, 1)
        core.update()

    def test_reset_creates_new_game_and_overwrites_saved_data(self):
        """リセット時は、生成器 → navigator → ポップアップの順にマップを作り直したうえで、
        保存データを読まずに新しいゲームを作り、その状態で上書き保存する"""
        app = self._app_with_core()
        old_core = app.game_core
        self.assertEqual(1, self.store.load_count)
        self.assertEqual([], self.store.save_calls)

        manager = Mock()
        with patch(
            "src.map_generator.AreaBlockAlgorithmGenerator.recreate",
            manager.generator,
        ), patch("src.main.Navigator.recreate", manager.navigator), patch(
            "src.main.NavigationPopup.recreate", manager.popup
        ), patch.object(
            old_core, "is_reset", return_value=True
        ):
            app.update()

        self.assertEqual(
            ["generator", "navigator", "popup"],
            [name for name, _, _ in manager.mock_calls],
        )
        self.assertIsNot(old_core, app.game_core)
        self.assertEqual(1, self.store.load_count)
        self.assertEqual(1, len(self.store.save_calls))
        self.assertEqual(
            {
                "game": {
                    "generator": {"marker": "generator"},
                    "navigator": {"marker": "navigator"},
                    "field": app.game_core.field.to_save_data(),
                }
            },
            self.store.stored,
        )
