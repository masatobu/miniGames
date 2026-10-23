import json
import math
import traceback
from unittest.mock import patch

from test.test_support import TestMapGenerator, TestParent, TestUnitParent

from src.main import (
    Area,
    Boss,
    Color,
    Direct,
    Enemy,
    Event,
    EventType,
    Fee,
    Field,
    InstructionKind,
    Material,
    Navigator,
    Player,
    PyxelUnitView,
    Resource,
    Spawner,
    Unit,
    Workbench,
)
from src.map_generator import (
    AreaBlockAlgorithmGenerator,
    MaterialType,
    ResourceType,
    WorkbenchParam,
)


class TestArea(TestParent):
    def test_draw(self):
        s = Area.SIZE
        test_cases = [
            ("default", (s * 2, s * 2), (2, 2), True),
            ("case 1", (0, 0), (0, 0), True),
            ("case 2", (s * -1, s * -1), (-1, -1), True),
            ("case 3", (s, s * -1), (1, -1), True),
            ("not unveiled", (s * 2, s * 2), (2, 2), False),
        ]
        for case_name, expected, area_axis, unveiled in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
                unveiled=unveiled,
            ):
                self.reset()
                area = Area(*area_axis)
                if unveiled:
                    area.unveil()
                area.draw()
                expected = [
                    (
                        "draw_rect",
                        *expected,
                        s,
                        s,
                        Color.GREEN if unveiled else Color.DARK_BLUE,
                        False,
                    ),
                ]
                self.assertEqual(
                    expected,
                    self.test_view.get_call_params(),
                    self.test_view.get_call_params(),
                )

    def test_contains(self):
        s = Area.SIZE
        test_cases = [
            ("default", True, (2, 2), (100, 100)),
            ("in edge left up", True, (2, 2), (s * 2, s * 2)),
            ("in edge right up", True, (2, 2), (s * 3 - 1, s * 2)),
            ("in edge right down", True, (2, 2), (s * 3 - 1, s * 3 - 1)),
            ("in edge left down", True, (2, 2), (s * 2, s * 3 - 1)),
            ("out edge right", False, (2, 2), (s * 3, s * 2)),
            ("out edge left", False, (2, 2), (s * 2 - 1, s * 3 - 1)),
            ("out edge down", False, (2, 2), (s * 2, s * 3)),
            ("out edge up", False, (2, 2), (s * 3 - 1, s * 2 - 1)),
            ("negative pos in edge left down", True, (-2, -2), (s * -2, s * -1 - 1)),
            ("negative pos out edge left", False, (-2, -2), (s * -2 - 1, s * -2)),
        ]
        for case_name, expected, area_axis, check_pos in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                area_axis=area_axis,
                check_pos=check_pos,
            ):
                self.reset()
                area = Area(*area_axis)
                self.assertEqual(expected, area.contains(*check_pos))


class TestField(TestUnitParent):  # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.field = Field()

    def reset(self):
        super().reset()
        self.expect_view_call = []
        self.expect_unit_view_call = []
        self.field = Field()

    def expected_opposite_pos(self, center_pos, diff, distance=None):
        """Field._get_opposite_pos が返すべき値を期待値として計算する
        （サイクル 017-9: 差分ベクトルの向きを保ったまま長さを距離定数へ揃える）。
        縮退ケース（diff == (0, 0)）は実装と同じく呼び出し側で代替の diff を渡す。"""
        if distance is None:
            distance = Field.OPPOSITE_DISTANCE
        length = math.hypot(*diff)
        scale = distance / length
        return tuple(round(c - d * scale) for c, d in zip(center_pos, diff))

    def check(self):
        """描画結果の検証ヘルパー。test_game_core.py の同名ヘルパーと実装が一致するが、
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
                if draw_action[0] == "area":
                    s = Area.SIZE
                    self.expect_view_call.extend(
                        [
                            (
                                "draw_rect",
                                s * x,
                                s * y,
                                s,
                                s,
                                (
                                    Color.GREEN
                                    if (x, y) in draw_action[2]
                                    else Color.DARK_BLUE
                                ),
                                False,
                            )
                            for x, y in draw_action[1]
                        ]
                    )
                if draw_action[0] in ["enemy_power", "fee_num", "boss_power"]:
                    # test_game_core.py の同名分岐と実装が一致するが、put_draw_result が
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
                if draw_action[0] == "workbench_popup":
                    self.expect_view_call.extend(
                        self.workbench_popup_calls(*draw_action[1:])
                    )
        except Exception as e:  # pylint: disable=W0718
            print(e)
            traceback.print_exc()

    def workbench_popup_calls(  # pylint: disable=too-many-locals
        self, workbench_pos, material_types, input_num, required
    ):
        """作業台のポップアップの描画呼び出しの期待値（サイクル 024-11）。x は作業台に
        揃えた中央揃え、縦幅の半分がエリアの上辺（枠線）の内側に入る位置（U6 を改訂）。背景の幅は「99/10」の
        5 文字ぶんで固定し、投入済みの桁数で変わらない（U7）。テキストは背景の右端
        （右の余白の内側）に右詰めで描き、桁が増えると左へ伸びる"""
        letter_w, letter_h = 4, 5  # Pyxel の標準フォントは 1 文字 4px 幅・5px 高
        image_size = PyxelUnitView.SIZE
        padding = 2
        # 絵柄は素材の種類数だけ横に隙間なく並べ、テキストは 1 つ（U2）
        images_w = image_size * len(material_types)
        popup_w = padding + images_w + padding + 5 * letter_w + padding
        popup_h = padding + image_size + padding
        popup_x = workbench_pos[0] - popup_w // 2
        # ポップアップの縦幅の半分がエリアの内側に入る（下端がエリアの上辺より縦幅の半分下）
        popup_y = workbench_pos[1] // Area.SIZE * Area.SIZE - popup_h + popup_h // 2
        calls = [
            ("draw_rect", popup_x, popup_y, popup_w, popup_h, Color.BLACK, True),
            ("draw_rect", popup_x, popup_y, popup_w, popup_h, Color.WHITE, False),
        ]
        for i, material_type in enumerate(material_types):
            calls.append(
                (
                    "draw_image",
                    popup_x + padding + i * image_size,
                    popup_y + padding,
                    *Material.IMAGE_POS_MAP[material_type],
                    False,
                    True,
                )
            )
        text = f"{input_num}/{required}"
        calls.append(
            (
                "draw_text",
                popup_x + popup_w - padding - len(text) * letter_w,
                popup_y + (popup_h - letter_h) // 2,
                text,
                Color.WHITE,
            )
        )
        return calls

    def put_unit_draw_result(self, draw_action_list):
        for draw_action in draw_action_list:
            image_pos = None
            if draw_action[0] == "player":
                image_pos = Player.IMAGE_POS
            if draw_action[0] == "fee":
                image_pos = Fee.IMAGE_POS_MAP[MaterialType.WOOD]
            if draw_action[0] == "enemy":
                image_pos = Enemy.IMAGE_POS
            if draw_action[0] == "boss":
                image_pos = Boss.IMAGE_POS
            if draw_action[0] == "spawner":
                image_pos = Spawner.IMAGE_POS
            if draw_action[0] == "workbench":
                image_pos = Workbench.IMAGE_POS
            if draw_action[0] == "resource":
                image_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE][0]
            if draw_action[0] == "resource harvested":
                image_pos = Resource.IMAGE_POS_MAP[ResourceType.TREE][1]
            if draw_action[0] == "material":
                material_type = (
                    draw_action[6] if len(draw_action) > 6 else MaterialType.WOOD
                )
                image_pos = Material.IMAGE_POS_MAP[material_type]
            self.expect_unit_view_call.append(
                ("draw_unit", *draw_action[1:3], *image_pos, *draw_action[3:6])
            )

    def test_walk_to_edge(self):
        s = Area.SIZE
        test_cases = [
            ("to right", (s * 3 - 1, 100), Direct.RIGHT, Direct.RIGHT, False),
            ("to left", (s * 2, 100), Direct.LEFT, Direct.LEFT, False),
            ("to down", (100, s * 3 - 1), Direct.RIGHT, Direct.DOWN, False),
            ("to up", (100, s * 2), Direct.RIGHT, Direct.UP, False),
            ("over right", (s * 4 - 1, 100), Direct.RIGHT, Direct.RIGHT, True),
            ("over left", (s * 1, 100), Direct.LEFT, Direct.LEFT, True),
            ("over down", (100, s * 4 - 1), Direct.RIGHT, Direct.DOWN, True),
            ("over up", (100, s * 1), Direct.RIGHT, Direct.UP, True),
        ]
        for (
            case_name,
            expected_pos,
            expected_face,
            to_direct,
            expand_area,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                expected_face=expected_face,
                to_direct=to_direct,
                expand_area=expand_area,
            ):
                self.reset()
                areas = [(2, 2)]
                self.field.area_map = {p: Area(*p) for p in areas}
                self.field.unit_map = {}
                if expand_area:
                    new_area = tuple(p + d for p, d in zip((2, 2), to_direct.value))
                    self.field.area_map[new_area] = Area(*new_area)
                    areas.append(new_area)
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                for _ in range(s * 2 + 1):
                    self.field.operate(to_direct)
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [("player", *expected_pos, expected_face, to_direct, False)]
                )
                self.check()

    def test_navigator_event_unveil(self):
        """開放対象に払って開放すると、開放したエリアの座標の UNVEIL イベントが
        navigator へ送られる。足りずに開放されない場合や、ゲーム開始時の開放
        （スタート・ボス）では送られない（サイクル 029-5。U1・U8）"""
        s = Area.SIZE
        fee_axis = (2, 6)
        fee_pos = tuple(p * s + s // 2 for p in fee_axis)
        test_cases = [
            ("unveil", 0, [Event(EventType.UNVEIL, fee_axis)]),
            ("not enough", -1, []),
        ]
        for case_name, material_delta, expected_events in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.assertEqual([], self.test_navigator.events)
                required_num = TestMapGenerator.calc_area_level(*fee_axis)
                self.field.area_map = {fee_axis: Area(*fee_axis)}
                self.field.unit_map = {fee_axis: [Fee(*fee_pos)]}
                self.field.player.pos = fee_pos
                self.field.player.add_material(
                    MaterialType.WOOD, required_num + material_delta
                )
                self.field.update()
                self.assertEqual(expected_events, self.test_navigator.events)

    def test_clear_instruction_adds_power(self):
        """指示をクリアすると、クリアした指示ごとの上昇量だけ武器の強さが上がる。
        開放・資材の採集のどちらでも上がり、即時クリアで複数進んだ場合は進んだ数だけ、
        クリアが無い場合・ボスの撃破（強化なし）では上がらない。上がった強さは保持される
        （サイクル 031-2。U3・U5）。上昇量は TestMapGenerator が
        `block_lv * 100 + order + 1`（ステップ0 = 1・ステップ1 = 2・ステップ5 = 101）を返す"""
        s = Area.SIZE
        fee_axis = (2, 6)
        fee_pos = tuple(p * s + s // 2 for p in fee_axis)
        material_axis = (2, 2)
        material_pos = tuple(p * s + s // 2 for p in material_axis)
        initial_power = self.field.player.get_power()
        test_cases = [
            ("unveil, one step", "unveil", [0], 1),
            ("unveil, two steps", "unveil", [0, 5], 1 + 101),
            ("unveil, no clear", "unveil", [], 0),
            ("gather, one step", "gather", [1], 2),
            ("gather, no clear", "gather", [], 0),
        ]
        for case_name, kind, cleared, expected_gain in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_navigator.set_cleared(cleared)
                if kind == "unveil":
                    self.field.area_map = {fee_axis: Area(*fee_axis)}
                    self.field.unit_map = {fee_axis: [Fee(*fee_pos)]}
                    self.field.player.pos = fee_pos
                    self.field.player.add_material(
                        MaterialType.WOOD, TestMapGenerator.calc_area_level(*fee_axis)
                    )
                else:
                    self.test_map_generator.set_material_type(MaterialType.WOOD)
                    self.field.area_map = {material_axis: Area(*material_axis)}
                    self.field.unit_map = {material_axis: [Material(*material_pos)]}
                    self.field.player.pos = material_pos
                self.field.player.set_power(initial_power)
                self.field.update()
                self.assertEqual(
                    initial_power + expected_gain, self.field.player.get_power()
                )
                self.field.update()
                self.assertEqual(
                    initial_power + expected_gain, self.field.player.get_power()
                )

    def test_clear_instruction_notifies_power_gain(self):
        """指示をクリアすると、強化した合計の増分が NavigationPopup へ 1 回だけ渡る。
        クリアが無い・ボスの撃破（強化なし。増分 0）では渡らない（サイクル 031-4。D1）。
        上昇量は TestMapGenerator が `block_lv * 100 + order + 1` を返す"""
        s = Area.SIZE
        fee_axis = (2, 6)
        fee_pos = tuple(p * s + s // 2 for p in fee_axis)
        test_cases = [
            ("one step", [0], 1),
            ("two steps, total once", [0, 5], 1 + 101),
            ("no clear", [], None),
            ("boss only", [14], None),
        ]
        for case_name, cleared, expected_gain in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_navigator.set_cleared(cleared)
                self.field.area_map = {fee_axis: Area(*fee_axis)}
                self.field.unit_map = {fee_axis: [Fee(*fee_pos)]}
                self.field.player.pos = fee_pos
                self.field.player.add_material(
                    MaterialType.WOOD, TestMapGenerator.calc_area_level(*fee_axis)
                )
                with patch.object(
                    self.navigation_popup, "set_power_gain"
                ) as mock_set_power_gain:
                    self.field.update()
                if expected_gain is None:
                    mock_set_power_gain.assert_not_called()
                else:
                    mock_set_power_gain.assert_called_once_with(expected_gain)

    def test_defeat_boss_does_not_add_power(self):
        """ボスの撃破でクリアした指示（DEFEAT_BOSS。添字 14）では武器の強さが上がらない"""
        boss_axis = (3, 2)
        self.reset()
        self.test_map_generator.set_start_pos((2, 2))
        self.test_map_generator.set_boss_pos(boss_axis)
        self.field = Field()
        initial_power = self.field.player.get_power()
        self.test_navigator.set_cleared([14])
        self.field.unit_map[boss_axis][0].set_hp(0)
        self.field.update()
        self.assertTrue(self.field.is_clear())
        self.assertEqual(initial_power, self.field.player.get_power())

    def test_clear_all_instructions_beats_boss(self):
        """本物の navigator・生成器で、ゲーム開始からボスの撃破の直前まで全指示を
        順にクリアすると、武器の強さがボスの強さより大きくなる。各ブロックの最後の
        指示をクリアした時点で、そのブロックのスポナーの強さを超えている
        （サイクル 031-3。U1・U2）"""
        # pylint: disable=protected-access
        generator = AreaBlockAlgorithmGenerator()
        navigator = Navigator(generator)
        with patch(
            "src.map_generator.AreaBlockAlgorithmGenerator.create",
            return_value=generator,
        ), patch("src.main.Navigator.create", return_value=navigator):
            field = Field()
            self.assertEqual(1, field.player.get_power())
            block_last_steps = {4: 0, 7: 1, 10: 2, 13: 3}
            while navigator.step < len(Navigator.STEPS):
                current = navigator.current
                if current.kind == InstructionKind.GATHER:
                    event = Event(EventType.GATHER, current.pos, current.material_type)
                else:
                    event = Event(EventType.UNVEIL, current.pos)
                step = navigator.step
                field._notify_navigator(event)
                if step in block_last_steps:
                    lv = block_last_steps[step]
                    spawner_power = 2 ** (lv + 1)  # ブロック lv のスポナーの強さ
                    self.assertGreater(field.player.get_power(), spawner_power)
            self.assertEqual(len(Navigator.STEPS), navigator.step)
            self.assertEqual(InstructionKind.DEFEAT_BOSS, navigator.current.kind)
            self.assertGreater(field.player.get_power(), generator.get_boss_power())

    def test_navigator_event_not_sent_on_start(self):
        """Field の生成（スタート・ボスのエリアの開放）ではイベントを送らない"""
        self.reset()
        Field()
        self.assertEqual([], self.test_navigator.events)

    def test_navigator_event_defeat_boss(self):
        """ボスを倒すと、ボスのエリアの座標の DEFEAT_BOSS イベントが navigator へ送られる"""
        boss_axis = (3, 2)
        self.reset()
        self.test_map_generator.set_start_pos((2, 2))
        self.test_map_generator.set_boss_pos(boss_axis)
        self.field = Field()
        self.field.unit_map[boss_axis][0].set_hp(0)
        self.assertEqual([], self.test_navigator.events)
        self.field.update()
        self.assertTrue(self.field.is_clear())
        self.assertEqual(
            [Event(EventType.DEFEAT_BOSS, boss_axis)], self.test_navigator.events
        )

    def test_navigator_event_gather(self):
        """資材を拾うと、拾ったエリアの座標と資材の種類の GATHER イベントが navigator へ
        送られる。資材の出どころ（資源・作業台・敵のドロップ）は区別せず、接触していない
        資材では送られない。同座標に重なった資材は 1 つずつ送られる（サイクル 030-3。U1）"""
        s = Area.SIZE
        area_axis = (2, 2)
        material_pos = tuple(p * s + s // 2 for p in area_axis)
        far_pos = (material_pos[0] + s * 2, material_pos[1])
        test_cases = [
            (
                "wood",
                [MaterialType.WOOD],
                material_pos,
                [Event(EventType.GATHER, area_axis, MaterialType.WOOD)],
            ),
            (
                "plank (workbench material)",
                [MaterialType.PLANK],
                material_pos,
                [Event(EventType.GATHER, area_axis, MaterialType.PLANK)],
            ),
            (
                "overlapping materials, one event each",
                [MaterialType.STONE, MaterialType.BRICK],
                material_pos,
                [
                    Event(EventType.GATHER, area_axis, MaterialType.STONE),
                    Event(EventType.GATHER, area_axis, MaterialType.BRICK),
                ],
            ),
            ("not touched", [MaterialType.WOOD], far_pos, []),
        ]
        for case_name, material_types, player_pos, expected_events in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                materials = []
                for material_type in material_types:
                    self.test_map_generator.set_material_type(material_type)
                    materials.append(Material(*material_pos))
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: materials}
                self.field.player.pos = player_pos
                self.field.update()
                self.assertEqual(expected_events, self.test_navigator.events)

    def test_unveil_area(self):
        s = Area.SIZE
        test_cases = [
            (
                "default",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [],
                False,
            ),
            (
                "again",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [(2, 2)],
                False,
            ),
            (
                "neighbor",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3), (1, 1), (0, 2), (1, 3)],
                [],
                {(2, 2), (1, 2)},
                [(1, 2)],
                False,
            ),
            (
                "cant unveil",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [],
                {(2, 2)},
                [(1, 1)],
                False,
            ),
            (
                "over monitor left",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [1, 0, -1]
                    for (x, y) in [(p, 1), (p - 1, 2), (p, 3)]
                ]
                + [(-2, 1), (-2, 3)],
                [],
                {(p, 2) for p in [2, 1, 0, -1, -2]},
                [(p, 2) for p in [1, 0, -1, -2]],
                False,
            ),
            (
                "over monitor right",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [(x, y) for p in [3, 4, 5] for (x, y) in [(p + 1, 2), (p, 1), (p, 3)]]
                + [(6, 1), (6, 3)],
                [],
                {(p, 2) for p in [2, 3, 4, 5, 6]},
                [(p, 2) for p in [3, 4, 5, 6]],
                False,
            ),
            (
                "over monitor up",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [1, 0, -1, -2]
                    for (x, y) in [(3, p), (2, p - 1), (1, p)]
                ]
                + [(3, -3), (1, -3)],
                [],
                {(2, p) for p in [2, 1, 0, -1, -2, -3]},
                [(2, p) for p in [1, 0, -1, -2, -3]],
                False,
            ),
            (
                "over monitor down",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)]
                + [
                    (x, y)
                    for p in [3, 4, 5, 6]
                    for (x, y) in [(3, p), (1, p), (2, p + 1)]
                ]
                + [(3, 7), (1, 7)],
                [],
                {(2, p) for p in [2, 3, 4, 5, 6, 7]},
                [(2, p) for p in [3, 4, 5, 6, 7]],
                False,
            ),
            (
                "unveil void",
                [(2, 2), (3, 2), (2, 1), (1, 2), (2, 3)],
                [(1, 1), (0, 2), (1, 3)],
                {(2, 2), (1, 2)},
                [(1, 2)],
                True,
            ),
        ]
        for (
            case_name,
            expected_list_with_fee,
            expected_list_without_fee,
            expected_unveiled_set,
            unveil_list,
            void_flg,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_list_with_fee=expected_list_with_fee,
                expected_list_without_fee=expected_list_without_fee,
                expected_unveiled_set=expected_unveiled_set,
                unveil_list=unveil_list,
                void_flg=void_flg,
            ):
                self.reset()
                self.test_map_generator.set_fee_ret_zero(void_flg)
                for pos in unveil_list:
                    self.field._unveil(*pos)  # pylint: disable=W0212
                self.field.draw()
                self.put_draw_result(
                    [
                        (
                            "area",
                            expected_list_with_fee + expected_list_without_fee,
                            expected_unveiled_set,
                        )
                    ]
                )
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(s * p + s // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for pos in expected_list_with_fee
                        if pos != (2, 2)
                    ]
                )
                self.put_unit_draw_result(
                    [("player", 100, 100, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(s * p + s // 2 for p in pos),
                            TestMapGenerator.calc_area_level(*pos),
                        )
                        for pos in expected_list_with_fee
                        if pos != (2, 2)
                    ]
                )
                self.check()

    def test_walk_to_fee(self):
        # 本テストの主題は「どの方向から歩いて接触しても隣接エリアが開放され、
        # 開放対象が消費される」という移動方向に関する振る舞いであり、資材条件
        # （種類・量）そのものの観点は test_fee_material_condition で確認する。
        # ID-019 により接触時に所持資材の条件判定が入るため、ここでは開放を
        # 成立させるための前準備として、必要量ちょうどの木材を先に持たせる。
        s = Area.SIZE
        test_cases = [
            (
                "to up",
                [(2, 1)],
                Direct.UP,
                [(3, 1), (2, 0), (1, 1)],
                Direct.RIGHT,
                (2, 2),
            ),
            (
                "to down",
                [(2, 3)],
                Direct.DOWN,
                [(3, 3), (1, 3), (2, 4)],
                Direct.RIGHT,
                (2, 2),
            ),
            (
                "to right",
                [(3, 2)],
                Direct.RIGHT,
                [(4, 2), (3, 1), (3, 3)],
                Direct.RIGHT,
                (2, 2),
            ),
            (
                "to left",
                [(1, 2)],
                Direct.LEFT,
                [(1, 1), (0, 2), (1, 3)],
                Direct.LEFT,
                (2, 2),
            ),
            (
                "with areas",
                [(2, 1)] + [(2, 3 + p) for p in range(4)],
                Direct.UP,
                [(3, 1), (2, 0), (1, 1)],
                Direct.RIGHT,
                (2, 2),
            ),
            (
                "to down far",
                [(2, 5)],
                Direct.DOWN,
                [(3, 5), (1, 5), (2, 6)],
                Direct.RIGHT,
                (2, 4),
            ),
        ]
        for (
            case_name,
            first_area_list,
            to_direct,
            extend_pos_list,
            expected_face,
            start_pos,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                first_area_list=first_area_list,
                to_direct=to_direct,
                extend_pos_list=extend_pos_list,
                expected_face=expected_face,
                start_pos=start_pos,
            ):
                self.reset()
                areas = [start_pos] + first_area_list
                self.field.player.pos = tuple(p * s + s // 2 for p in start_pos)
                self.field.area_map = {p: Area(*p) for p in areas}
                self.field.unit_map = {
                    pos: [Fee(*tuple(p * s + s // 2 for p in pos))]
                    for pos in first_area_list
                }
                touched_pos = tuple(p + d for p, d in zip(start_pos, to_direct.value))
                self.field.player.add_material(
                    MaterialType.WOOD,
                    TestMapGenerator.calc_area_level(*touched_pos),
                )
                for _ in range(s - PyxelUnitView.SIZE):
                    self.field.operate(to_direct)
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", areas, set())])
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in first_area_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(
                                p * s + s // 2 + d * (s - PyxelUnitView.SIZE)
                                for d, p in zip(to_direct.value, start_pos)
                            ),
                            expected_face,
                            to_direct,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(p * s + s // 2 for p in axis),
                            TestMapGenerator.calc_area_level(*axis),
                        )
                        for axis in first_area_list
                    ]
                )
                self.check()
                self.assertFalse(
                    self.field.area_map[
                        tuple(p + d for p, d in zip(start_pos, to_direct.value))
                    ].unveiled
                )
                # ここで Fee に触れる（あと1ドット進む）。事前に必要量ちょうどの
                # 資材を持たせてあるため開放される。
                self.field.update()
                self.field.draw()
                areas.extend(extend_pos_list)
                append_pos = tuple(p + d for p, d in zip(start_pos, to_direct.value))
                self.put_draw_result([("area", areas, {append_pos})])
                fee_appended_pos_list = [
                    pos
                    for pos in first_area_list + extend_pos_list
                    if pos != append_pos
                ]
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in fee_appended_pos_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(
                                p * s + s // 2 + d * (s - PyxelUnitView.SIZE + 1)
                                for d, p in zip(to_direct.value, start_pos)
                            ),
                            expected_face,
                            to_direct,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(p * s + s // 2 for p in axis),
                            TestMapGenerator.calc_area_level(*axis),
                        )
                        for axis in fee_appended_pos_list
                    ]
                )
                self.check()
                self.assertTrue(self.field.area_map[append_pos].unveiled)
                self.assertNotIn(append_pos, self.field.unit_map)

    def test_fee_material_condition(self):
        # 開放対象に接触しても、その種類の所持数が必要量に満たない場合・種類が
        # 違う場合は開放されないことを、全種類（木材・石・板材・レンガ・ハンマー）の
        # 開放対象で確認する
        # （U3）。「ちょうど足りる」は境界値として移植元の `<=` と同じ向きを確認する
        # （判断5（ID-006）により一度消滅した観点が、ID-019 で種類付きの資材として復活）。
        s = Area.SIZE
        fee_axis = (2, 6)
        fee_pos = tuple(p * s + s // 2 for p in fee_axis)
        test_cases = [
            ("wood, enough", MaterialType.WOOD, MaterialType.WOOD, 0, True),
            ("wood, not enough", MaterialType.WOOD, MaterialType.WOOD, -1, False),
            ("wood, wrong type", MaterialType.WOOD, MaterialType.STONE, 0, False),
            ("stone, enough", MaterialType.STONE, MaterialType.STONE, 0, True),
            ("stone, not enough", MaterialType.STONE, MaterialType.STONE, -1, False),
            ("stone, wrong type", MaterialType.STONE, MaterialType.WOOD, 0, False),
            ("plank, enough", MaterialType.PLANK, MaterialType.PLANK, 0, True),
            ("plank, not enough", MaterialType.PLANK, MaterialType.PLANK, -1, False),
            ("plank, wrong type", MaterialType.PLANK, MaterialType.BRICK, 0, False),
            ("brick, enough", MaterialType.BRICK, MaterialType.BRICK, 0, True),
            ("brick, not enough", MaterialType.BRICK, MaterialType.BRICK, -1, False),
            ("brick, wrong type", MaterialType.BRICK, MaterialType.HAMMER, 0, False),
            ("hammer, enough", MaterialType.HAMMER, MaterialType.HAMMER, 0, True),
            ("hammer, not enough", MaterialType.HAMMER, MaterialType.HAMMER, -1, False),
            ("hammer, wrong type", MaterialType.HAMMER, MaterialType.PLANK, 0, False),
        ]
        for (
            case_name,
            fee_type,
            material_type,
            material_delta,
            expected_unveiled,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                fee_type=fee_type,
                material_type=material_type,
                material_delta=material_delta,
                expected_unveiled=expected_unveiled,
            ):
                self.reset()
                self.test_map_generator.set_fee_type(fee_type)
                required_num = TestMapGenerator.calc_area_level(*fee_axis)
                self.field.area_map = {fee_axis: Area(*fee_axis)}
                self.field.unit_map = {fee_axis: [Fee(*fee_pos)]}
                self.field.player.pos = fee_pos
                self.field.player.add_material(
                    material_type, required_num + material_delta
                )
                self.field.update()
                self.assertEqual(
                    expected_unveiled, self.field.area_map[fee_axis].unveiled
                )
                if expected_unveiled:
                    self.assertNotIn(fee_axis, self.field.unit_map)
                else:
                    self.assertIn(fee_axis, self.field.unit_map)

    def test_fee_consume_material(self):  # pylint: disable=too-many-locals
        # 開放すると、開放対象の種類の所持数が必要量だけ減ること、他の種類の
        # 所持数は変わらないこと、必要量ちょうどを払うとその種類が
        # get_player_materials() から消えること、開放されなかった場合
        # （019-3のケース）は所持数が変わらないことを、全種類（木材・石・板材・
        # レンガ・ハンマー）の開放対象で確認する（サイクル019-4。ID-019-13）。
        s = Area.SIZE
        fee_axis = (2, 6)
        fee_pos = tuple(p * s + s // 2 for p in fee_axis)
        # 「他の種類」は種類の並びで次の種類（末尾は先頭）とする
        material_types = list(MaterialType)
        other_type_map = {
            material_type: material_types[(i + 1) % len(material_types)]
            for i, material_type in enumerate(material_types)
        }
        other_num = 4
        test_cases = [
            ("wood, exact -> removed", MaterialType.WOOD, 0, True),
            ("wood, extra -> remains", MaterialType.WOOD, 3, True),
            ("wood, not enough -> unchanged", MaterialType.WOOD, -1, False),
            ("stone, exact -> removed", MaterialType.STONE, 0, True),
            ("stone, extra -> remains", MaterialType.STONE, 3, True),
            ("stone, not enough -> unchanged", MaterialType.STONE, -1, False),
            ("plank, exact -> removed", MaterialType.PLANK, 0, True),
            ("plank, extra -> remains", MaterialType.PLANK, 3, True),
            ("plank, not enough -> unchanged", MaterialType.PLANK, -1, False),
            ("brick, exact -> removed", MaterialType.BRICK, 0, True),
            ("brick, extra -> remains", MaterialType.BRICK, 3, True),
            ("brick, not enough -> unchanged", MaterialType.BRICK, -1, False),
            ("hammer, exact -> removed", MaterialType.HAMMER, 0, True),
            ("hammer, extra -> remains", MaterialType.HAMMER, 3, True),
            ("hammer, not enough -> unchanged", MaterialType.HAMMER, -1, False),
        ]
        for case_name, fee_type, held_extra, expected_unveiled in test_cases:
            with self.subTest(
                case_name=case_name, fee_type=fee_type, held_extra=held_extra
            ):
                self.reset()
                self.test_map_generator.set_fee_type(fee_type)
                required_num = TestMapGenerator.calc_area_level(*fee_axis)
                held_num = required_num + held_extra
                other_type = other_type_map[fee_type]
                self.field.area_map = {fee_axis: Area(*fee_axis)}
                self.field.unit_map = {fee_axis: [Fee(*fee_pos)]}
                self.field.player.pos = fee_pos
                self.field.player.add_material(fee_type, held_num)
                self.field.player.add_material(other_type, other_num)
                self.field.update()
                self.assertEqual(
                    expected_unveiled, self.field.area_map[fee_axis].unveiled
                )
                expected_fee_num = (
                    held_num - required_num if expected_unveiled else held_num
                )
                expected_counts = {fee_type: expected_fee_num, other_type: other_num}
                expected_materials = [
                    (material_type, expected_counts[material_type])
                    for material_type in MaterialType
                    if expected_counts.get(material_type, 0) > 0
                ]
                self.assertEqual(expected_materials, self.field.get_player_materials())

    def test_start_materials(self):
        # Field を生成すると、マップ生成から得た開始時の所持資材をプレイヤーが
        # 持っていることを確認する（サイクル019-4。U13）。開始時の値には
        # 依存させず、木材だけ・石だけ・空のケースで確認する。
        test_cases = [
            ("wood only", [(MaterialType.WOOD, 3)]),
            ("stone only", [(MaterialType.STONE, 5)]),
            ("empty", []),
        ]
        for case_name, start_materials in test_cases:
            with self.subTest(case_name=case_name, start_materials=start_materials):
                self.reset()
                self.test_map_generator.set_start_materials(start_materials)
                self.field = Field()
                self.assertEqual(start_materials, self.field.get_player_materials())

    def test_spawn(self):
        # 移植元 本体 test_spawn の enemy 系8ケースと "enemy not spawn" ケースは
        # ID-013 で削除した敵の生成経路（_spawn の enemy 分岐）を前提とするため移植しない。
        # "enemy not spawn" は敵前提の enemy_power_zero_flg に代えて spawner を
        # 0 にした "not spawn" として移植する（ID-021 判断3）。
        s = Area.SIZE
        area_axis = (2, 2)
        center_pos = tuple(p * s + s // 2 for p in area_axis)
        test_cases = [
            ("spawner spawn", center_pos, (100, 107), (2, 2), "spawner"),
            ("resource spawn", center_pos, (100, 107), (2, 2), "resource"),
            # 作業台のエリアは加工後の資材（Plank）を material_type に持つ（U1）が、
            # 作業台は資源より前に決まる（U3）ため Resource は生成されない。
            # 優先順が逆だと get_resource_type() が Plank で KeyError になる
            ("workbench spawn", center_pos, (100, 107), (2, 2), "workbench"),
            ("not spawn", None, (100, 107), (2, 2), None),
        ]
        for (
            case_name,
            expected_pos,
            player_pos,
            area_axis,
            unit_kind,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_pos=expected_pos,
                player_pos=player_pos,
                area_axis=area_axis,
                unit_kind=unit_kind,
            ):
                self.reset()
                self.test_map_generator.set_spawner_ret_zero(unit_kind != "spawner")
                self.test_map_generator.set_material_type(
                    {
                        "resource": MaterialType.WOOD,
                        "workbench": MaterialType.PLANK,
                    }.get(unit_kind)
                )
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), 10, 60)
                    if unit_kind == "workbench"
                    else None
                )
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {
                    area_axis: [Fee(*tuple(p * s + s // 2 for p in area_axis))]
                }
                self.field.player.pos = player_pos
                # 主題（開放時の出現）を変えないための前準備。ID-019 で開放条件が
                # 追加されたため、開放対象が開放される（＝出現の主題を検証できる）
                # だけの資材を先に持たせる
                self.field.player.add_material(
                    MaterialType.WOOD, TestMapGenerator.calc_area_level(*area_axis)
                )
                self.field.update()
                self.field.draw()
                extend_area = [
                    tuple(p + d for p, d in zip(area_axis, direct.value))
                    for direct in Direct
                    if direct != Direct.NUTRAL
                ]
                self.put_draw_result([("area", [area_axis] + extend_area, {area_axis})])
                if expected_pos is not None:
                    self.put_unit_draw_result(
                        [
                            (
                                unit_kind,
                                *expected_pos,
                                Direct.RIGHT,
                                Direct.NUTRAL,
                                False,
                            )
                        ]
                    )
                self.put_unit_draw_result(
                    [
                        (
                            "fee",
                            *tuple(p * s + s // 2 for p in axis),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for axis in extend_area
                    ]
                    + [
                        (
                            "player",
                            *player_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "fee_num",
                            *tuple(p * s + s // 2 for p in axis),
                            TestMapGenerator.calc_area_level(*axis),
                        )
                        for axis in extend_area
                    ]
                )
                if unit_kind == "workbench":
                    # プレイヤーが作業台と同じエリアにいるためポップアップも描かれる
                    self.put_draw_result(
                        [("workbench_popup", center_pos, (MaterialType.WOOD,), 0, 10)]
                    )
                self.check()

    def test_resource_spot(self):  # pylint: disable=too-many-locals
        s = Area.SIZE
        d = PyxelUnitView.SIZE
        rd = Field.OPPOSITE_DISTANCE
        h = Resource.HARVEST_FRAMES
        g = Resource.SUSPEND_FRAMES
        r = Resource.REGEN_FRAMES
        area_axis = (2, 2)
        resource_pos = tuple(p * s + s // 2 for p in area_axis)
        touched_pos = (resource_pos[0] - (d - 1), resource_pos[1])
        boundary_pos = (resource_pos[0] - d, resource_pos[1])
        far_pos = (resource_pos[0] - d - 50, resource_pos[1])
        off_screen_pos = tuple(
            p * s + s // 2 for p in (area_axis[0] + 10, area_axis[1])
        )
        # 採取済みに達した瞬間、資源と同じエリアに資材が1つ出現する（サイクル 017-5）。
        # 出現位置はエリア中心からプレイヤーの反対側へ距離 rd だけ離れた位置になる
        # （Field._spawn の武器と共通の算出。サイクル 017-8で点対称から一定距離へ変更）
        material_pos = (resource_pos[0] + rd, resource_pos[1])
        # 接触した最初の update() では Field._hit() 経由の hit() が消費フレームより後に
        # 呼ばれるため、経過フレームは (updates - 1) になる。採取済みに達するには
        # HARVEST_FRAMES + 1 回の update() が必要。中断（サイクル 016-4）後の再開も同様に、
        # 再開後の最初の update() は消費フレームにならないため (残り進行 + 1) 回が必要
        test_cases = [
            ("touched", [(touched_pos, 1)], "resource", True, touched_pos, 0),
            (
                "boundary",
                [(boundary_pos, 1)],
                "resource",
                False,
                boundary_pos,
                0,
            ),
            ("far", [(far_pos, 1)], "resource", False, far_pos, 0),
            (
                "harvested",
                [(touched_pos, h + 1)],
                "resource harvested",
                False,
                touched_pos,
                1,
            ),
            (
                "suspended after leaving",
                [(touched_pos, 1), (far_pos, g + 1)],
                "resource",
                False,
                far_pos,
                0,
            ),
            (
                "resumes and retains progress after leaving",
                [(touched_pos, 1), (far_pos, g + 1), (touched_pos, h - g + 1)],
                "resource harvested",
                False,
                touched_pos,
                1,
            ),
            (
                "regenerates and can be harvested again",
                # 再生は接触の有無によらず進むため、再生の待ち時間は far_pos（非接触）で
                # 経過させる。regen 完了直後の資源は「一度も接触していない資源」と同じ
                # 初期状態に戻るため、再度の採取には最初の採取と同じ h + 1 回の update() が
                # 必要になる（上記コメントの +1 の理由と同一）。未回収の資材は消えずに
                # 残るため、資材は2つになる（サイクル 017-10）
                [(touched_pos, h + 1), (far_pos, r), (touched_pos, h + 1)],
                "resource harvested",
                False,
                touched_pos,
                2,
            ),
            (
                # 採取済みの資源は画面外でも再生が進み、画面に戻ると採取可能な絵柄で
                # 見える（requirements.md §3.13。U4: 画面内外で資源の扱いを変えない
                # 方針とし、画面外でも Resource.update() をそのまま呼ぶ）。再生の
                # 境界値は TestResource.test_regenerate で検証済みのため、ここでは
                # Field.update が画面外の資源にも update() を呼ぶ配線だけを確認する
                # （steps の最後は非接触の位置へ移動するだけで Field.update は呼ばない）
                "regenerates off screen, available on return",
                [(touched_pos, h + 1), (off_screen_pos, r), (far_pos, 0)],
                "resource",
                False,
                far_pos,
                1,
            ),
        ]
        for (
            case_name,
            steps,
            resource_kind,
            expected_blink,
            final_player_pos,
            material_count,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                steps=steps,
                expected_blink=expected_blink,
                final_player_pos=final_player_pos,
            ):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [Resource(*resource_pos)]}
                for player_pos, updates in steps:
                    self.field.player.pos = player_pos
                    for _ in range(updates):
                        self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            resource_kind,
                            *resource_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            expected_blink,
                        ),
                    ]
                    + [
                        (
                            "material",
                            *material_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                    * material_count
                    + [
                        (
                            "player",
                            *final_player_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.check()

    def test_enemy_move(self):
        s = Area.SIZE
        test_cases = [
            ("next to", [(100, 60 + 1, Direct.RIGHT, Direct.DOWN)], [(2, 1)], []),
            (
                "near 2",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                    (100, 140 - 1, Direct.RIGHT, Direct.UP),
                ],
                [(2, 1), (2, 3)],
                [],
            ),
            (
                "near and stop",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                    (100, -20, Direct.RIGHT, Direct.NUTRAL),
                    (100, -60, Direct.RIGHT, Direct.NUTRAL),
                ],
                [(2, 1), (2, -1), (2, -2)],
                [],
            ),
            (
                "near and stay",
                [
                    (100, 60 + 1, Direct.RIGHT, Direct.DOWN),
                ],
                [(2, 1)],
                [(2, -4), (2, 8), (7, 2), (-3, 2)],
            ),
        ]
        for case_name, expected, near_area_axis_list, far_area_axis_list in test_cases:
            with self.subTest(
                case_name=case_name,
                expected=expected,
                near_area_axis_list=near_area_axis_list,
                far_area_axis_list=far_area_axis_list,
            ):
                self.reset()
                first_area_axis = (2, 2)
                self.field.area_map = {
                    area_axis: Area(*area_axis)
                    for area_axis in [first_area_axis]
                    + near_area_axis_list
                    + far_area_axis_list
                }
                self.field.unit_map = {
                    area_axis: [Enemy(*tuple(p * s + s // 2 for p in area_axis))]
                    for area_axis in near_area_axis_list + far_area_axis_list
                }
                self.field.player.pos = (100, 100)
                self.field.update()
                self.field.draw()
                self.put_draw_result(
                    [("area", [first_area_axis] + near_area_axis_list, set())]
                )
                self.put_unit_draw_result(
                    [("enemy", *stat, False) for stat in expected]
                    + [
                        (
                            "player",
                            100,
                            100,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.put_draw_result(
                    [
                        ("enemy_power", *stat[0:2], TestMapGenerator.POWER_WEIGHT)
                        for stat in expected
                    ]
                )
                self.check()

    def test_enemy_frozen_off_screen(self):
        """画面外の敵は行動しない（requirements.md §3.13）ことの回帰確認。資源の再生を
        画面外でも進める経路（TDD サイクル 022-1）の追加によって、画面外のエリアが
        誤って敵まで更新してしまわないかを確認する。画面内で追跡方向を持たせたあと
        画面外へ長時間置いても位置が変わらず、画面に戻ると凍結していた地点から
        追跡を再開することを、Field.draw で観測する。"""
        s = Area.SIZE
        r = Resource.REGEN_FRAMES
        enemy_axis = (2, 1)
        enemy_pos = tuple(p * s + s // 2 for p in enemy_axis)
        near_pos = (100, 100)
        far_pos = (100, (enemy_axis[1] + 10) * s + s // 2)
        self.reset()
        self.field.area_map = {enemy_axis: Area(*enemy_axis)}
        self.field.unit_map = {enemy_axis: [Enemy(*enemy_pos)]}
        for player_pos, updates in [
            (near_pos, 1),
            (far_pos, r),
            (near_pos, 1),
        ]:
            self.field.player.pos = player_pos
            for _ in range(updates):
                self.field.update()
        self.field.draw()
        # 1回目の近接 update() で1歩追跡し（(2,1) の敵が画面内で下方向へ1歩進む）、
        # 画面外での r 回はその位置のまま凍結し、2回目の近接 update() でさらに1歩
        # 追跡を再開する。画面外で誤って進んでいれば、この位置には一致しない
        final_enemy_pos = (enemy_pos[0], enemy_pos[1] + 2)
        self.put_draw_result([("area", [enemy_axis], set())])
        self.put_unit_draw_result(
            [
                ("enemy", *final_enemy_pos, Direct.RIGHT, Direct.DOWN, False),
                ("player", *near_pos, Direct.RIGHT, Direct.NUTRAL, False),
            ]
        )
        self.put_draw_result(
            [("enemy_power", *final_enemy_pos, TestMapGenerator.POWER_WEIGHT)]
        )
        self.check()

    def test_hit_mob(self):
        # 移植元 test_hit_mob は Enemy/Boss 双方を対象とし、所持資材が尽きた場合の
        # ゲームオーバー分岐や、資材枯渇・クリア状態を確認するアサートを含んでいた。
        # Boss は U7 スコープで未移植のため Boss 関連ケースもあわせて除外し、
        # Enemy との戦闘のみを検証する内容とした。
        s = Area.SIZE
        test_cases = [
            ("enemy from down", Direct.DOWN, True, (100, 107), 2),
            ("enemy from left", Direct.LEFT, True, (93, 100), 3),
            ("enemy from up", Direct.UP, True, (100, 93), 4),
            ("enemy from right", Direct.RIGHT, True, (107, 100), 5),
            ("player damaged by enemy", Direct.DOWN, False, (100, 107), 0),
        ]
        for (
            case_name,
            expected_direct,
            expected_unit_killed,
            player_pos,
            player_power,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_direct=expected_direct,
                expected_unit_killed=expected_unit_killed,
                player_pos=player_pos,
                player_power=player_power,
            ):
                area_axis = (2, 2)
                fee_axis = (2, 1)
                self.reset()
                self.field.area_map = {
                    axis: Area(*axis) for axis in (area_axis, fee_axis)
                }
                fee_pos = tuple(p * s + s // 2 for p in fee_axis)
                fee = Fee(*fee_pos)
                fee.set_num(5)
                self.field.unit_map = {
                    area_axis: [Enemy(*tuple(p * s + s // 2 for p in area_axis))],
                    fee_axis: [fee],
                }
                self.field.player.pos = player_pos
                self.field.player.set_power(player_power)
                for _ in range(2):
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis, fee_axis], set())])
                next_pos = tuple(
                    p * s + s // 2 + d * (1 if expected_unit_killed else 2)
                    for p, d in zip(area_axis, expected_direct.value)
                )
                default_result = [
                    (
                        "fee",
                        *fee_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        False,
                    ),
                    (
                        "player",
                        *player_pos,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        not expected_unit_killed,
                    ),
                ]
                self.put_unit_draw_result(
                    [
                        (
                            "enemy",
                            *next_pos,
                            (
                                Direct.RIGHT
                                if expected_direct != Direct.LEFT
                                else Direct.LEFT
                            ),
                            (
                                expected_direct
                                if not expected_unit_killed
                                else Direct.NUTRAL
                            ),
                            expected_unit_killed,
                        )
                    ]
                    + default_result
                )
                self.put_draw_result(
                    [("enemy_power", *next_pos, TestMapGenerator.POWER_WEIGHT)]
                    + [("fee_num", *fee_pos, 5)]
                )
                self.check()
                for _ in range(Unit.I_FRAMES - 1):
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis, fee_axis], set())])
                result = []
                if not expected_unit_killed:
                    result += [
                        (
                            "enemy",
                            *player_pos,
                            (
                                Direct.RIGHT
                                if expected_direct != Direct.LEFT
                                else Direct.LEFT
                            ),
                            Direct.RIGHT,
                            expected_unit_killed,
                        )
                    ]
                    self.put_draw_result(
                        [("enemy_power", *player_pos, TestMapGenerator.POWER_WEIGHT)]
                    )
                self.put_draw_result([("fee_num", *fee_pos, 5)])
                result += default_result
                self.put_unit_draw_result(result)
                self.check()
                self.assertEqual(
                    (3 if expected_unit_killed else 1, 3, player_power),
                    self.field.player.get_status(),
                )

    def test_enemy_drop_material(self):
        """敵を倒すと、撃破された位置に、そのエリアの種類・個数の資材が現れることを
        Field.update -> Field.draw で確認する（U4・U5、サイクル 020-2）。資材の
        種類が None のエリアでは現れず（U7）、ボスを倒しても現れない（U6）。撃破後は
        プレイヤーを隣接エリア判定の外（`_get_hit_units` の area 差分が1を超える位置）
        へ離し、出現した資材が同じフレームで拾われずに残ることを観測する。"""
        s = Area.SIZE
        area_axis = (2, 2)
        start_pos = tuple(p * s + s // 2 for p in area_axis)
        hit_pos = (start_pos[0] + 5, start_pos[1])
        away_pos = (start_pos[0], start_pos[1] + s * 2)
        test_cases = [
            ("enemy drops wood", Enemy, MaterialType.WOOD, True),
            ("enemy drops stone", Enemy, MaterialType.STONE, True),
            ("enemy area has no material, nothing drops", Enemy, None, False),
            ("boss defeated, nothing drops", Boss, MaterialType.WOOD, False),
        ]
        for case_name, mob_cls, material_type, expect_material in test_cases:
            with self.subTest(
                case_name=case_name,
                mob_cls=mob_cls,
                material_type=material_type,
                expect_material=expect_material,
            ):
                self.reset()
                self.test_map_generator.set_material_ret_zero(material_type is None)
                if material_type is not None:
                    self.test_map_generator.set_material_type(material_type)
                self.field.area_map = {area_axis: Area(*area_axis)}
                mob = mob_cls(*start_pos)
                self.field.unit_map = {area_axis: [mob]}
                self.field.player.pos = hit_pos
                self.field.player.set_power(mob.get_power())
                self.field.update()
                drop_pos = mob.get_pos()
                self.field.player.pos = away_pos
                for _ in range(Unit.I_FRAMES):
                    self.field.update()
                self.assertTrue(mob.is_killed())
                self.assertEqual(
                    (3, 3, mob.get_power()), self.field.player.get_status()
                )
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    (
                        [
                            (
                                "material",
                                *drop_pos,
                                Direct.RIGHT,
                                Direct.NUTRAL,
                                False,
                                material_type,
                            )
                        ]
                        if expect_material
                        else []
                    )
                    + [("player", *away_pos, Direct.RIGHT, Direct.NUTRAL, False)]
                )
                self.check()

    def test_get_material(self):
        """プレイヤーが資材に接触すると資材が取得され画面から消えることを
        Field.update / Field.draw 経由で確認する（サイクル 017-3）。同じエリアの
        資源や、離れた位置にある別の資材が巻き添えで消えないこと、同座標に重なった
        資材は1回の接触で両方とも消えることをあわせて確認する。"""
        s = Area.SIZE
        area_axis = (2, 2)
        resource_pos = tuple(p * s + s // 2 for p in area_axis)
        material_pos = (resource_pos[0] - 20, resource_pos[1])
        other_material_pos = (resource_pos[0], resource_pos[1] - 20)
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        test_cases = [
            (
                "touched material disappears, resource and other material remain",
                [Material(*material_pos), Material(*other_material_pos)],
                [other_material_pos],
            ),
            (
                "overlapping materials at the same position both disappear in one hit",
                [Material(*material_pos), Material(*material_pos)],
                [],
            ),
        ]
        for (
            case_name,
            materials,
            expected_material_pos_list,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [Resource(*resource_pos)] + materials}
                self.field.player.pos = material_pos
                self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            "resource",
                            *resource_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                    + [
                        (
                            "material",
                            *pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for pos in expected_material_pos_list
                    ]
                    + [
                        (
                            "player",
                            *material_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.check()

    def test_get_material_count(self):
        """資材に接触すると、その資材の種類の所持数が Material.get_num() だけ増えることを
        Field.update 経由で確認する（サイクル 018-1）。種類が異なれば別々に数えられること、
        同じ種類（同座標に重なった場合を含む）は合算されること、HP・武器の強さが変わらない
        ことをあわせて確認する。"""
        s = Area.SIZE
        area_axis = (2, 2)
        material_pos = tuple(p * s + s // 2 for p in area_axis)

        def make_material(material_type, num):
            self.test_map_generator.set_material_type(material_type)
            material = Material(*material_pos)
            material.set_num(num)
            return material

        test_cases = [
            (
                "single type",
                [(MaterialType.WOOD, 3)],
                {MaterialType.WOOD: 3, MaterialType.STONE: 0},
            ),
            (
                "different types counted separately",
                [(MaterialType.WOOD, 2), (MaterialType.STONE, 5)],
                {MaterialType.WOOD: 2, MaterialType.STONE: 5},
            ),
            (
                "same type accumulates, including overlapping materials",
                [(MaterialType.WOOD, 2), (MaterialType.WOOD, 2)],
                {MaterialType.WOOD: 4, MaterialType.STONE: 0},
            ),
        ]
        for case_name, material_specs, expected_counts in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {
                    area_axis: [
                        make_material(material_type, num)
                        for material_type, num in material_specs
                    ]
                }
                self.field.player.pos = material_pos
                self.field.update()
                for material_type, expected_num in expected_counts.items():
                    self.assertEqual(
                        expected_num,
                        self.field.player.get_material_count(material_type),
                        material_type,
                    )
                self.assertEqual((3, 3, 1), self.field.get_player_status())

    def test_workbench_input(self):  # pylint: disable=too-many-locals
        """作業台に重なっている間、重なっているフレームを数えて INPUT_INTERVAL_FRAMES
        ごとに素材を1つ投入し、所持資材から減算することを Field.update 経由で確認する
        （サイクル 024-5）。最初の投入は重なって INPUT_INTERVAL_FRAMES フレーム目。
        素材を所持していない場合、素材でない種類しか持たない場合は投入しない。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        test_cases = [
            # (ケース名, 所持資材, 重なるフレーム数, 投入済みの期待値)
            ("before first interval", {MaterialType.WOOD: 20}, interval - 1, 0),
            ("first interval", {MaterialType.WOOD: 20}, interval, 1),
            ("just before second", {MaterialType.WOOD: 20}, interval * 2 - 1, 1),
            (
                "every interval up to just below required",
                {MaterialType.WOOD: 20},
                interval * (required_num - 1),
                required_num - 1,
            ),
            (
                # 必要量に達すると必要量を消費して加工を始める（サイクル 024-7）
                "consumed by processing at required",
                {MaterialType.WOOD: 20},
                interval * required_num,
                0,
            ),
            (
                "stops when owned material runs out",
                {MaterialType.WOOD: 3},
                interval * required_num,
                3,
            ),
            (
                "no material",
                {},
                interval * required_num,
                0,
            ),
            (
                "only non-input material",
                {MaterialType.STONE: 20},
                interval * required_num,
                0,
            ),
        ]
        for case_name, materials, frames, expected_input_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, 60)
                )
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                for material_type, num in materials.items():
                    self.field.player.add_material(material_type, num)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(expected_input_num, workbench.input_num)
                # 投入した数は、間隔ごとの投入回数と所持数の小さい方（加工の開始で
                # 投入済みの数が減っても、所持資材は投入した数だけ減っている）
                input_count = min(
                    frames // interval, materials.get(MaterialType.WOOD, 0)
                )
                for material_type, num in materials.items():
                    expected_owned = num - (
                        input_count if material_type == MaterialType.WOOD else 0
                    )
                    self.assertEqual(
                        expected_owned,
                        self.field.player.get_material_count(material_type),
                        material_type,
                    )

    def test_workbench_input_multiple_materials(
        self,
    ):  # pylint: disable=too-many-locals
        """複数素材の作業台は、全種類を 1 つ以上所持している場合にのみ、INPUT_INTERVAL_FRAMES
        ごとに全種類を 1 つずつ同時に投入し、所持資材から減算することを Field.update 経由で
        確認する（サイクル 025-5）。一部の種類しか所持していない場合、どれも所持していない
        場合は投入せず、所持資材も減らない。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        input_times = 3
        frames = interval * input_times
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        plank, brick = MaterialType.PLANK, MaterialType.BRICK
        test_cases = [
            # (ケース名, 所持資材, 投入済みの期待値)
            ("both owned", {plank: 20, brick: 20}, input_times),
            ("only plank", {plank: 20}, 0),
            ("only brick", {brick: 20}, 0),
            ("none", {}, 0),
            ("only non-input material", {MaterialType.STONE: 20}, 0),
            # 同数ずつ減る。少ない方が尽きた時点で投入が止まる
            ("stop when either runs out", {plank: 2, brick: 20}, 2),
        ]
        for case_name, materials, expected_input_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((plank, brick), required_num, 60)
                )
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                for material_type, num in materials.items():
                    self.field.player.add_material(material_type, num)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(expected_input_num, workbench.input_num)
                for material_type, num in materials.items():
                    consumed = (
                        expected_input_num if material_type in (plank, brick) else 0
                    )
                    self.assertEqual(
                        num - consumed,
                        self.field.player.get_material_count(material_type),
                        material_type,
                    )

    def test_workbench_input_stops_when_either_runs_out(self):
        """複数素材の作業台は、一方の種類を使い切ると重なり続けても投入が止まり、もう一方が
        残っていても減らない。全種類を同時に 1 つずつ投入するため、投入済みの数は種類によらず
        常に等しく、片方だけが投入済みになる状態は生じない。使い切った種類を補充して重なり
        続けると、続きから投入される（サイクル 025-6）。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        plank, brick = MaterialType.PLANK, MaterialType.BRICK
        plank_num, brick_num, refill_num = 3, 5, 4
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        self.reset()
        self.test_map_generator.set_material_type(MaterialType.PLANK)
        self.test_map_generator.set_workbench(
            WorkbenchParam((plank, brick), required_num, 60)
        )
        workbench = Workbench(*workbench_pos)
        self.field.area_map = {area_axis: Area(*area_axis)}
        self.field.unit_map = {area_axis: [workbench]}
        self.field.player.pos = workbench_pos
        for material_type in MaterialType:
            self.field.player.consume_material(
                material_type, self.field.player.get_material_count(material_type)
            )
        self.field.player.add_material(plank, plank_num)
        self.field.player.add_material(brick, brick_num)

        def stay(frames):
            for _ in range(frames):
                self.field.update()

        def owned(material_type):
            return self.field.player.get_material_count(material_type)

        # Plank を使い切る回数を超えて重なり続けても、投入は Plank の所持数で止まる
        stay(interval * (brick_num + 1))
        self.assertEqual(plank_num, workbench.input_num)
        self.assertEqual(0, owned(plank))
        self.assertEqual(brick_num - plank_num, owned(brick))
        # 補充すると、止まっている間も数えていた重なりのフレームにより直ちに続きから
        # 投入され、以降は間隔ごとに 1 つずつ投入される。Brick が尽きると再び止まる
        self.field.player.add_material(plank, refill_num)
        stay(1)
        self.assertEqual(plank_num + 1, workbench.input_num)
        stay(interval * refill_num)
        self.assertEqual(brick_num, workbench.input_num)
        self.assertEqual(refill_num - (brick_num - plank_num), owned(plank))
        self.assertEqual(0, owned(brick))

    def test_workbench_input_resumes_after_leaving(
        self,
    ):  # pylint: disable=too-many-locals
        """作業台から離れると投入が止まり、投入済みの数・所持資材・投入間隔の経過は保持され、
        再び重なると続きから投入されることを Field.update 経由で確認する（サイクル 024-6）。
        離れている間のフレームは投入間隔に数えない。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        owned_num = 20
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        away_pos = tuple(p + s * 2 for p in workbench_pos)
        test_cases = [
            # (ケース名, [(重なっているか, フレーム数), ...], 投入済みの期待値)
            ("leave after input", [(True, interval), (False, interval * 3)], 1),
            (
                "leave mid interval then resume",
                [(True, interval - 1), (False, interval * 3), (True, 1)],
                1,
            ),
            (
                "leave mid interval, not enough after resume",
                [(True, interval - 1), (False, interval * 3), (True, 0)],
                0,
            ),
            (
                "resume keeps input count",
                [(True, interval * 2), (False, 1), (True, interval)],
                3,
            ),
            (
                # 通り過ぎるたびの (interval - 1) フレームは保持され合算される
                "pass through repeatedly",
                [(True, interval - 1), (False, 1)] * 3,
                (interval - 1) * 3 // interval,
            ),
            (
                "pass through then stay",
                [(True, interval - 1), (False, 1)] * 3 + [(True, interval)],
                ((interval - 1) * 3 + interval) // interval,
            ),
        ]
        for case_name, steps, expected_input_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, 60)
                )
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(MaterialType.WOOD, owned_num)
                for is_touching, frames in steps:
                    self.field.player.pos = workbench_pos if is_touching else away_pos
                    input_num_before = workbench.input_num
                    for _ in range(frames):
                        self.field.update()
                    if not is_touching:
                        self.assertEqual(input_num_before, workbench.input_num)
                self.assertEqual(expected_input_num, workbench.input_num)
                self.assertEqual(
                    owned_num - expected_input_num,
                    self.field.player.get_material_count(MaterialType.WOOD),
                )

    def test_workbench_process(self):  # pylint: disable=too-many-locals
        """投入済みの資材が必要量に達すると必要量を消費して加工を始め、加工時間の経過で
        加工後の資材（作業台のエリアの material_type / material_num。U1）が作業台の
        エリアの _get_opposite_pos の位置に1つ出現し、触れると所持資材に加算されることを
        Field.update 経由で確認する（サイクル 024-7）。投入済みの資材が必要量に
        満たない間は加工しない。加工中の状態は投入済みの数（消費後）と出現した資材で観測する。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        process_frames = 60
        # 所持数を必要量ちょうどにして、加工の開始後に次の投入が起きないようにする
        # （加工中の投入・繰り返しは 024-8）
        owned_num = required_num
        input_frames = interval * required_num
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        # プレイヤーが作業台と同じ位置のとき、方向が定まらない縮退ケースで (1, 0) 方向の反対側
        expected_material_pos = (
            workbench_pos[0] - Field.OPPOSITE_DISTANCE,
            workbench_pos[1],
        )
        test_cases = [
            # (ケース名, 所持資材(Wood), 重なるフレーム数, 投入済みの期待値, 出現する資材の数)
            ("below required", required_num - 1, input_frames, required_num - 1, 0),
            ("just started", owned_num, input_frames, 0, 0),
            ("just before done", owned_num, input_frames + process_frames - 1, 0, 0),
            ("done", owned_num, input_frames + process_frames, 0, 1),
            ("stays done", owned_num, input_frames + process_frames * 2, 0, 1),
        ]
        for (
            case_name,
            wood_num,
            frames,
            expected_input_num,
            expected_material_num,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, process_frames)
                )
                # 加工後の資材の個数は作業台のエリアの material_num（U1）
                expected_num = self.test_map_generator.get_material_num(*area_axis)
                self.assertGreater(expected_num, 0)
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(MaterialType.WOOD, wood_num)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(expected_input_num, workbench.input_num)
                materials = [
                    unit
                    for unit in self.field.unit_map[area_axis]
                    if isinstance(unit, Material)
                ]
                self.assertEqual(expected_material_num, len(materials))
                if expected_material_num > 0:
                    self.assertEqual(MaterialType.PLANK, materials[0].get_type())
                    self.assertEqual(expected_num, materials[0].get_num())
                    self.assertEqual(expected_material_pos, materials[0].get_pos())
                    # 出現した資材に触れると所持資材に加算される（既存の拾得経路）
                    self.field.player.pos = expected_material_pos
                    self.field.update()
                    self.assertEqual(
                        expected_num,
                        self.field.player.get_material_count(MaterialType.PLANK),
                    )
                    self.assertFalse(
                        any(
                            isinstance(u, Material)
                            for u in self.field.unit_map[area_axis]
                        )
                    )

    def test_workbench_process_multiple_materials(
        self,
    ):  # pylint: disable=too-many-locals
        """複数素材の作業台は、投入済みが必要量に達すると全種類の必要量を消費して加工を始め、
        加工時間の経過で加工後の資材が出現し、触れると所持資材に加算されることを Field.update
        経由で確認する（サイクル 025-7）。投入済みが上限 INPUT_MAX_NUM に達すると、全種類とも
        投入せず所持資材も減らない。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 5
        max_num = Workbench.INPUT_MAX_NUM
        plank, brick, hammer = (
            MaterialType.PLANK,
            MaterialType.BRICK,
            MaterialType.HAMMER,
        )
        # 加工の開始後に次の投入が起きないよう、所持数は必要量ちょうど。上限のケースだけ十分に持つ
        owned_num = required_num
        owned_for_max = 200
        input_frames = interval * required_num
        # 上限に達するまでに投入する回数は、加工の開始で消費した必要量の分だけ増える
        reach_max = interval * (max_num + required_num)
        long_process = reach_max + interval * 20
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        expected_material_pos = (
            workbench_pos[0] - Field.OPPOSITE_DISTANCE,
            workbench_pos[1],
        )
        test_cases = [
            # (ケース名, 加工時間, 所持数, 重なるフレーム数, 投入済みの期待値, 加工を開始した回数, 出現数)
            ("below required", 90, owned_num, input_frames - 1, required_num - 1, 0, 0),
            ("just started", 90, owned_num, input_frames, 0, 1, 0),
            ("just before done", 90, owned_num, input_frames + 90 - 1, 0, 1, 0),
            ("done", 90, owned_num, input_frames + 90, 0, 1, 1),
            ("reach max", long_process, owned_for_max, reach_max, max_num, 1, 0),
            ("stay at max", long_process, owned_for_max, long_process, max_num, 1, 0),
        ]
        for (
            case_name,
            process_frames,
            owned,
            frames,
            expected_input_num,
            started_num,
            expected_material_num,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_material_type(hammer)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((plank, brick), required_num, process_frames)
                )
                expected_num = self.test_map_generator.get_material_num(*area_axis)
                self.assertGreater(expected_num, 0)
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(plank, owned)
                self.field.player.add_material(brick, owned)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(expected_input_num, workbench.input_num)
                # 全種類とも、投入した数（投入済み＋加工の開始で消費した数）だけ同数減る
                consumed = expected_input_num + required_num * started_num
                for material_type in (plank, brick):
                    self.assertEqual(
                        owned - consumed,
                        self.field.player.get_material_count(material_type),
                        material_type,
                    )
                materials = [
                    unit
                    for unit in self.field.unit_map[area_axis]
                    if isinstance(unit, Material)
                ]
                self.assertEqual(expected_material_num, len(materials))
                if expected_material_num > 0:
                    self.assertEqual(hammer, materials[0].get_type())
                    self.assertEqual(expected_num, materials[0].get_num())
                    self.assertEqual(expected_material_pos, materials[0].get_pos())
                    self.field.player.pos = expected_material_pos
                    self.field.update()
                    self.assertEqual(
                        expected_num, self.field.player.get_material_count(hammer)
                    )

    def test_workbench_process_repeat(self):  # pylint: disable=too-many-locals
        """投入済みの資材が必要量を満たす間は加工を繰り返す（サイクル 024-8）。
        加工中も投入は続き、加工中に必要量に達しても加工の時間は巻き戻らない。加工の
        完了時に必要量を満たしていれば次の加工を始め、必要量を下回ると加工は止まる。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        process_frames = 60
        owned_num = 25
        first_start = interval * required_num
        first_done = first_start + process_frames
        second_done = first_done + process_frames
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)

        def expected_input_num(frames, started_num):
            # 投入は所持数を上限に間隔ごとに 1 つ。加工の開始ごとに必要量が減る
            return min(frames // interval, owned_num) - required_num * started_num

        test_cases = [
            # (ケース名, 重なるフレーム数, 加工を開始した回数, 出現した資材の数)
            ("first processing", first_done - 1 - 10, 1, 0),
            # 加工中に必要量に達しても加工の時間は巻き戻らず、次の加工は待つ
            ("reached required while processing", first_start * 2, 1, 0),
            ("just before first done", first_done - 1, 1, 0),
            ("first done starts second", first_done, 2, 1),
            ("just before second done", second_done - 1, 2, 1),
            ("second done stops", second_done, 2, 2),
            ("stays stopped", second_done + process_frames, 2, 2),
        ]
        for case_name, frames, started_num, expected_material_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, process_frames)
                )
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(MaterialType.WOOD, owned_num)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(
                    expected_input_num(frames, started_num), workbench.input_num
                )
                materials = [
                    unit
                    for unit in self.field.unit_map[area_axis]
                    if isinstance(unit, Material)
                ]
                self.assertEqual(expected_material_num, len(materials))

    def test_workbench_process_off_screen(self):  # pylint: disable=too-many-locals
        """作業台が画面外にあっても加工は進み、加工後の資材が作業台のエリアの
        _get_opposite_pos の位置（U8）に出現する（サイクル 024-10）。画面外の作業台には
        プレイヤーが重なり得ないため投入は進まず、所持資材も変わらない。加工の進行は
        画面外の資源の再生と同じく、画面の内外で作業台の扱いを変えない方針で確認する。"""
        s = Area.SIZE
        required_num = 10
        process_frames = 60
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        off_screen_pos = tuple(
            p * s + s // 2 for p in (area_axis[0] + 10, area_axis[1])
        )
        owned_num = 5
        test_cases = [
            # (ケース名, 画面外で update する回数, 出現する資材の数)
            ("just before done", process_frames - 1, 0),
            ("done", process_frames, 1),
            ("stays done", process_frames * 2, 1),
        ]
        for case_name, frames, expected_material_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, process_frames)
                )
                expected_num = self.test_map_generator.get_material_num(*area_axis)
                self.assertGreater(expected_num, 0)
                workbench = Workbench(*workbench_pos)
                # 画面内で必要量まで投入して加工を開始した状態にする
                workbench.input_num = required_num - 1
                workbench.input_material()
                self.assertEqual(0, workbench.input_num)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = off_screen_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(MaterialType.WOOD, owned_num)
                for _ in range(frames):
                    self.field.update()
                # 画面外では投入されず、所持資材も変わらない
                self.assertEqual(0, workbench.input_num)
                self.assertEqual(
                    owned_num,
                    self.field.player.get_material_count(MaterialType.WOOD),
                )
                materials = [
                    unit
                    for unit in self.field.unit_map[area_axis]
                    if isinstance(unit, Material)
                ]
                self.assertEqual(expected_material_num, len(materials))
                if expected_material_num > 0:
                    self.assertEqual(MaterialType.PLANK, materials[0].get_type())
                    self.assertEqual(expected_num, materials[0].get_num())
                    self.assertEqual(
                        self.field._get_opposite_pos(  # pylint: disable=W0212
                            area_axis
                        ),
                        materials[0].get_pos(),
                    )

    def test_workbench_popup(self):
        """プレイヤーが作業台と同じエリアにいる間だけ、作業台の上部（x は作業台に揃えた
        中央揃え、下端はエリアの上辺より上。U6）に、背景（黒の塗りつぶし＋白の枠線）・
        素材の絵柄・「投入済み/必要量」のテキストが描画される（サイクル 024-11）。
        ポップアップはエリア・ユニット・プレイヤーの後に描く。背景の幅は「99/10」の
        5 文字ぶんで固定し、投入済みの桁数で変わらない（U7）。"""
        s = Area.SIZE
        required_num = 10
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        test_cases = [
            # (ケース名, プレイヤーの位置, 投入済み, ポップアップを描くか)
            ("empty", workbench_pos, 0, True),
            ("middle", workbench_pos, 5, True),
            ("max", workbench_pos, Workbench.INPUT_MAX_NUM, True),
            (
                "same area, other position",
                (workbench_pos[0] + 10, workbench_pos[1] - 10),
                5,
                True,
            ),
            (
                "adjacent area",
                (workbench_pos[0] + s, workbench_pos[1]),
                5,
                False,
            ),
        ]
        # 素材の種類の並び。複数素材は絵柄を横に並べ、背景の幅を絵柄の分だけ広げる（U2）
        for material_types in (
            (MaterialType.WOOD,),
            (MaterialType.PLANK, MaterialType.BRICK),
        ):
            self.check_workbench_popup(
                s, required_num, area_axis, workbench_pos, test_cases, material_types
            )

    def check_workbench_popup(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, s, required_num, area_axis, workbench_pos, test_cases, material_types
    ):
        for case_name, player_pos, input_num, expected_popup in test_cases:
            with self.subTest(case_name=case_name, material_types=material_types):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam(material_types, required_num, 60)
                )
                workbench = Workbench(*workbench_pos)
                workbench.input_num = input_num
                player_area = tuple(p // s for p in player_pos)
                self.field.area_map = {
                    area_axis: Area(*area_axis),
                    player_area: Area(*player_area),
                }
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = player_pos
                self.field.draw()
                self.put_draw_result([("area", sorted(self.field.area_map), set())])
                self.put_unit_draw_result(
                    [
                        (
                            "workbench",
                            *workbench_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                        ("player", *player_pos, Direct.RIGHT, Direct.NUTRAL, False),
                    ]
                )
                if expected_popup:
                    self.put_draw_result(
                        [
                            (
                                "workbench_popup",
                                workbench_pos,
                                material_types,
                                input_num,
                                required_num,
                            )
                        ]
                    )
                self.check()

    def test_workbench_popup_follows_field(self):
        """ポップアップはフィールドのワールド座標で描かれ、同じエリア内でプレイヤーが
        動いても描画座標は変わらない（サイクル 024-12）。プレイヤーの位置に追従する
        画面固定の ScreenObject とは異なり、画面上では作業台と一緒に動く。"""
        s = Area.SIZE
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        player_pos_list = [
            workbench_pos,
            (workbench_pos[0] + 10, workbench_pos[1] - 10),
            (workbench_pos[0] - 15, workbench_pos[1] + 15),
        ]
        self.test_map_generator.set_material_type(MaterialType.PLANK)
        self.test_map_generator.set_workbench(
            WorkbenchParam((MaterialType.WOOD,), 10, 60)
        )
        popup_calls_list = []
        for player_pos in player_pos_list:
            self.reset()
            self.test_map_generator.set_material_type(MaterialType.PLANK)
            self.test_map_generator.set_workbench(
                WorkbenchParam((MaterialType.WOOD,), 10, 60)
            )
            workbench = Workbench(*workbench_pos)
            workbench.input_num = 5
            self.field.area_map = {area_axis: Area(*area_axis)}
            self.field.unit_map = {area_axis: [workbench]}
            self.field.player.pos = player_pos
            self.field.draw()
            # エリア（1 件）・作業台とプレイヤーは unit_view のため、view の呼び出しの
            # 残りがポップアップ
            popup_calls_list.append(self.test_view.get_call_params()[1:])
        self.assertEqual(
            self.workbench_popup_calls(workbench_pos, (MaterialType.WOOD,), 5, 10),
            popup_calls_list[0],
        )
        for popup_calls in popup_calls_list[1:]:
            self.assertEqual(popup_calls_list[0], popup_calls)

    def test_workbench_input_cap(self):  # pylint: disable=too-many-locals
        """投入済みの資材は INPUT_MAX_NUM（99）を上限とする（サイクル 024-9）。上限に
        達すると重なっていても投入せず、所持資材も減らない。加工の開始で上限を下回れば
        再び投入する。上限に達する状態は、長い加工時間の間に投入だけが進むことで作る。"""
        s = Area.SIZE
        interval = Workbench.INPUT_INTERVAL_FRAMES
        required_num = 10
        max_num = Workbench.INPUT_MAX_NUM
        owned_num = 200
        first_start = interval * required_num
        # 加工の開始直後（投入済み 0）から上限に達するまでに必要なフレーム数
        reach_max = first_start + interval * max_num
        process_frames = reach_max + interval * 20
        first_done = first_start + process_frames
        area_axis = (2, 2)
        workbench_pos = tuple(p * s + s // 2 for p in area_axis)
        test_cases = [
            # (ケース名, 重なるフレーム数, 投入済みの期待値)
            ("just before max", reach_max - 1, max_num - 1),
            ("reach max", reach_max, max_num),
            ("stay at max", first_done - 1, max_num),
            # 加工の完了で次の加工を始めて必要量を消費し、上限を下回ると投入が再開する。
            # 上限の間も重なったフレームは数えているため、再開の最初の投入は直ちに行われ、
            # その後は間隔ごとに 1 つ（完了のフレーム＋間隔のフレームで 2 つ）
            ("resume after start", first_done + interval, max_num - required_num + 2),
        ]
        for case_name, frames, expected_input_num in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), required_num, process_frames)
                )
                workbench = Workbench(*workbench_pos)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [workbench]}
                self.field.player.pos = workbench_pos
                for material_type in MaterialType:
                    self.field.player.consume_material(
                        material_type,
                        self.field.player.get_material_count(material_type),
                    )
                self.field.player.add_material(MaterialType.WOOD, owned_num)
                for _ in range(frames):
                    self.field.update()
                self.assertEqual(expected_input_num, workbench.input_num)
                # 所持資材は、投入した数（投入済み＋加工の開始で消費した数）だけ減る
                started_num = (frames >= first_start) + (frames >= first_done)
                self.assertEqual(
                    owned_num - (expected_input_num + required_num * started_num),
                    self.field.player.get_material_count(MaterialType.WOOD),
                )

    def test_player_start_pos(self):
        test_cases = [
            ("pos 1", (2, 2)),
            ("pos 2", (5, 5)),
        ]
        for case_name, pos in test_cases:
            with self.subTest(case_name=case_name, pos=pos):
                self.reset()
                self.test_map_generator.set_start_pos(pos)
                self.field = Field()
                self.field.area_map = {pos: Area(*pos)}
                self.field.unit_map = {}
                self.field.draw()
                self.put_draw_result([("area", [pos], set())])
                self.put_unit_draw_result(
                    [
                        (
                            "player",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.check()

    def test_set_boss(self):
        test_cases = [
            ("pos 1", (2, 2)),
            ("pos 2", (5, 5)),
        ]
        for case_name, pos in test_cases:
            with self.subTest(case_name=case_name, pos=pos):
                self.reset()
                player_pos = (pos[0] - 1, pos[1])
                self.test_map_generator.set_start_pos(player_pos)
                self.test_map_generator.set_boss_pos(pos)
                self.field = Field()
                self.field.draw()
                areas = [
                    tuple(p + d for p, d in zip(player_pos, direct.value))
                    for direct in Direct
                ]
                self.put_draw_result([("area", areas, {player_pos, pos})])
                fee_pos_list = [
                    tuple(
                        (p + d) * Area.SIZE + Area.SIZE // 2
                        for p, d in zip(player_pos, direct.value)
                    )
                    for direct in Direct
                    if direct not in [Direct.NUTRAL, Direct.RIGHT]
                ]
                self.put_unit_draw_result(
                    [
                        (
                            "boss",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                    # test_game_core.py の同名リストと記述が一致するが、各テストケース
                    # 固有の期待値データであり、共通化せず各クラス固有のデータとして扱う
                    # （検討の経緯は ID-011_subtasks.md「ID-011-10」を参照）
                    # pylint: disable=duplicate-code
                    + [
                        (
                            "fee",
                            *pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                        for pos in fee_pos_list
                    ]
                    + [
                        (
                            "player",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in player_pos),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.put_draw_result(
                    [
                        (
                            "boss_power",
                            *tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos),
                            TestMapGenerator.BOSS_POWER_WEIGHT,
                        )
                    ]
                    + [
                        (
                            "fee_num",
                            *pos,
                            TestMapGenerator.calc_area_level(
                                *tuple(p // Area.SIZE for p in pos)
                            ),
                        )
                        for pos in fee_pos_list
                    ]
                )
                self.check()

    def test_spawner_spawn(self):
        self.reset()
        self.test_map_generator.set_spawner_ret_zero(False)
        first_area_axis = (2, 2)
        self.field.area_map = {first_area_axis: Area(*first_area_axis)}
        self.field.unit_map = {}
        self.field.spawner_map = {first_area_axis: Spawner(100, 100)}
        self.field.player.pos = (80, 100)
        self.field.player.power = 0
        self.field.draw()
        self.put_draw_result([("area", [first_area_axis], set())])
        self.put_unit_draw_result(
            [
                ("spawner", 100, 100, Direct.RIGHT, Direct.NUTRAL, False),
                (
                    "player",
                    80,
                    100,
                    Direct.RIGHT,
                    Direct.NUTRAL,
                    False,
                ),
            ]
        )
        for enemy_stat, player_stat in [
            ((100, 100, Direct.RIGHT, Direct.NUTRAL, False), False),
            ((80, 100, Direct.LEFT, Direct.LEFT, False), True),
        ]:
            for _ in range(Spawner.START_SPAWN_INTERVAL):
                self.field.update()
            self.field.draw()
            self.put_draw_result([("area", [first_area_axis], set())])
            self.put_unit_draw_result(
                [
                    ("spawner", 100, 100, Direct.RIGHT, Direct.NUTRAL, False),
                    ("enemy", *enemy_stat),
                    (
                        "player",
                        80,
                        100,
                        Direct.RIGHT,
                        Direct.NUTRAL,
                        player_stat,
                    ),
                ]
            )
            self.put_draw_result([("enemy_power", *enemy_stat[0:2], 1)])
        self.check()

    def test_multiple_spawners(self):
        """異なるエリアの複数のスポナーが、それぞれ独立して敵を出現させる

        スポナーは各ブロックに 1 つずつ配置される（requirements.md §3.7。ID-027 U5）ため、
        マップ上に同時に複数のスポナーがある。出現の抑止（出現させた敵が残っている間は
        新たな敵を出現させない）は、スポナーごと（そのスポナーのエリアの敵）に働き、
        他のスポナーの敵の有無には影響されないことを確認する。

        `Field` は既にスポナーをエリアごとに保持しており、追加時点から PASSED になる
        特性テスト（サイクル 027-4）。
        """
        self.reset()
        self.test_map_generator.set_spawner_ret_zero(False)
        area_a, area_b = (2, 2), (4, 2)
        self.field.area_map = {area_a: Area(*area_a), area_b: Area(*area_b)}
        self.field.unit_map = {}
        self.field.spawner_map = {area_a: Spawner(100, 100), area_b: Spawner(180, 100)}
        # 敵の追跡範囲（Enemy.STOP_DISTANCE_AREA）の外かつ画面内に置き、
        # 敵がプレイヤーに接触しない位置にする
        self.field.player.pos = (60, 100)

        def enemies(area_axis):
            return [
                u
                for u in self.field.unit_map.get(area_axis, [])
                if isinstance(u, Enemy)
            ]

        for _ in range(Spawner.START_SPAWN_INTERVAL):
            self.field.update()
        self.assertEqual((1, 1), (len(enemies(area_a)), len(enemies(area_b))))
        enemy_a = enemies(area_a)[0]
        # 一方の敵が残っている間も、他方は敵を出現させない（スポナーごとに抑止される）
        for _ in range(Spawner.START_SPAWN_INTERVAL * 2):
            self.field.update()
        self.assertEqual((1, 1), (len(enemies(area_a)), len(enemies(area_b))))
        # B の敵だけがいなくなると、B だけが次の敵を出現させる（A の敵は残ったまま増えない）
        del self.field.unit_map[area_b]
        for _ in range(Spawner.START_SPAWN_INTERVAL):
            self.field.update()
        self.assertEqual([enemy_a], enemies(area_a))
        self.assertEqual(1, len(enemies(area_b)))

    def test_material_spawn_pos(self):
        """資材の出現位置が、エリア中心からプレイヤーの反対側へ距離 rd だけ離れた位置に
        なることを、接触位置を変えた6ケース（下・遠い下・左・斜め45度・斜めで軸が優勢・
        中心で縮退）で Field.update / Field.draw 経由で確認する（ID-032: 武器の出現位置の
        テストから付け替え。サイクル 017-8・017-9）。"""
        s = Area.SIZE
        h = Resource.HARVEST_FRAMES
        rd = Field.OPPOSITE_DISTANCE
        area_axis = (2, 2)
        resource_pos = tuple(p * s + s // 2 for p in area_axis)
        # 縮退ケース（プレイヤーが中心と同一座標）は方向に意味を持たせないため、
        # 実装が代替する任意の差分 (1, 0) から期待値を算出する（サイクル 017-9）
        degenerate_pos = self.expected_opposite_pos(resource_pos, (1, 0), rd)
        # 斜めに接触したケースでも4方向へ丸められず、差分ベクトルの向きを保った位置に
        # 出現することを確認する（サイクル 017-9）
        test_cases = [
            (
                "player near below center",
                (0, 1),
                (resource_pos[0], resource_pos[1] - rd),
            ),
            (
                "player far below center",
                (0, 7),
                (resource_pos[0], resource_pos[1] - rd),
            ),
            (
                "player left of center",
                (-7, 0),
                (resource_pos[0] + rd, resource_pos[1]),
            ),
            (
                "player diagonally below-right of center (45 degrees)",
                (7, 7),
                self.expected_opposite_pos(resource_pos, (7, 7), rd),
            ),
            (
                "player diagonally below-right, axis-dominant",
                (7, 3),
                self.expected_opposite_pos(resource_pos, (7, 3), rd),
            ),
            ("player on center (degenerate)", (0, 0), degenerate_pos),
        ]
        for case_name, diff, expected_material_pos in test_cases:
            with self.subTest(case_name=case_name, diff=diff):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [Resource(*resource_pos)]}
                self.field.player.pos = tuple(c + d for c, d in zip(resource_pos, diff))
                for _ in range(h + 1):
                    self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            "resource harvested",
                            *resource_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                        (
                            "material",
                            *expected_material_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                        (
                            "player",
                            *self.field.player.get_pos(),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        ),
                    ]
                )
                self.check()

    def test_material_spawn(self):  # pylint: disable=too-many-locals
        """採取完了の瞬間に資源と同じエリアへ資材が1つ現れて Field が保持・描画すること
        （配線）、未回収なら蓄積し2個で打ち止めにならないこと、回収済みなら蓄積されず
        1個のまま再出現することを Field.update / Field.draw 経由で確認する
        （サイクル 017-5・017-10・017-3）。出現タイミングの境界（採取未完了／採取済み
        継続で増えない）は TestResource.test_spawn_materials で検証済み。出現位置
        （方向・距離一定・斜め・縮退）は test_material_spawn_pos で検証する
        （本テストでは再検証しない）。"""
        s = Area.SIZE
        d = PyxelUnitView.SIZE
        rd = Field.OPPOSITE_DISTANCE
        h = Resource.HARVEST_FRAMES
        r = Resource.REGEN_FRAMES
        area_axis = (2, 2)
        resource_pos = tuple(p * s + s // 2 for p in area_axis)
        touched_pos = (resource_pos[0] - (d - 1), resource_pos[1])
        far_pos = (resource_pos[0] - d - 50, resource_pos[1])
        # 資材はエリア中心からプレイヤーの反対側へ距離 rd だけ離れた位置に出現する
        # （Field._spawn の武器と共通の算出。サイクル 017-8で点対称から一定距離へ変更）
        material_pos = (resource_pos[0] + rd, resource_pos[1])
        test_cases = [
            (
                # 資源が返した Material を Field が unit_map へ載せ、描画することの配線確認
                "just harvested",
                [(touched_pos, h + 1)],
                "resource harvested",
                False,
                1,
            ),
            (
                # 蓄積が2つで打ち止めにならず、3回目でさらに1つ増える（サイクル 017-10）
                "harvested three times after regenerate",
                [
                    (touched_pos, h + 1),
                    (far_pos, r),
                    (touched_pos, h + 1),
                    (far_pos, r),
                    (touched_pos, h + 1),
                ],
                "resource harvested",
                False,
                3,
            ),
            (
                # 資材を取得済みなら、再生後の再採取で新しい資材が重ならず
                # 1個のまま出現する（サイクル 017-3 の取得とサイクル 017-10 の
                # 蓄積の両立。上の「未回収なら3個まで増える」との対比）
                "collected then harvested again after regenerate, does not accumulate",
                [
                    (touched_pos, h + 1),
                    (material_pos, 1),
                    (far_pos, r),
                    (touched_pos, h + 1),
                ],
                "resource harvested",
                False,
                1,
            ),
        ]
        for (
            case_name,
            steps,
            resource_kind,
            expected_blink,
            material_count,
        ) in test_cases:
            with self.subTest(case_name=case_name, steps=steps):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.WOOD)
                self.field.area_map = {area_axis: Area(*area_axis)}
                self.field.unit_map = {area_axis: [Resource(*resource_pos)]}
                for player_pos, updates in steps:
                    self.field.player.pos = player_pos
                    for _ in range(updates):
                        self.field.update()
                self.field.draw()
                self.put_draw_result([("area", [area_axis], set())])
                self.put_unit_draw_result(
                    [
                        (
                            resource_kind,
                            *resource_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            expected_blink,
                        )
                    ]
                    + [
                        (
                            "material",
                            *material_pos,
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                    * material_count
                    + [
                        (
                            "player",
                            *self.field.player.get_pos(),
                            Direct.RIGHT,
                            Direct.NUTRAL,
                            False,
                        )
                    ]
                )
                self.check()


class TestFieldSaveData(TestUnitParent):
    """Field の状態（開放済みエリア・プレイヤーの位置・HP・武器の強さ・所持資材）の保存データへの
    変換と復元（ID-033 サイクル 033-4。U3）。ボスの位置は生成器の保存データが持つ。

    開放済みエリアのユニットは、開放時と同じく初期状態で出現する（ユニットの状態の保存は ID-034）。
    """

    def _open_area(self, field, axis):
        """開放対象 Fee のあるエリア axis にプレイヤーを置いて 1 フレーム進め、開放する"""
        s = Area.SIZE
        field.player.pos = tuple(p * s + s // 2 for p in axis)
        field.player.add_material(MaterialType.WOOD, 1)
        field.update()

    def _restore_via_json(self, field):
        return Field(json.loads(json.dumps(field.to_save_data())))

    def _draw_calls(self, field):
        self.test_view.reset()
        self.test_unit_view.reset()
        field.draw()
        return self.test_view.get_call_params(), self.test_unit_view.get_call_params()

    def test_restore_draws_same_field(self):
        """保存データから復元した Field は、保存前と同じエリア・開放対象・（開放済みエリアの）ユニット・
        プレイヤーを描き、同じ HP・武器の強さ・所持資材を返す"""
        test_cases = [
            ("no unit", True, [(3, 2), (4, 2)]),
            ("spawner in unveiled area", False, [(3, 2)]),
        ]
        for case_name, spawner_zero, open_axis_list in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_spawner_ret_zero(spawner_zero)
                field = Field()
                field.player.add_material(MaterialType.WOOD, 5)
                for axis in open_axis_list:
                    self._open_area(field, axis)
                field.player.add_power(7)
                field.player.hp = 2

                restored = self._restore_via_json(field)

                self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
                self.assertEqual(
                    field.get_player_status(), restored.get_player_status()
                )
                self.assertEqual(
                    field.get_player_materials(), restored.get_player_materials()
                )
                self.assertEqual((2, 3, 8), restored.get_player_status())

    def _resource_field(self):
        """資源（Tree）のあるエリア (3, 2) を開放し、そのエリアの中央にプレイヤーを置いた Field"""
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        field = Field()
        self._open_area(field, (3, 2))
        return field

    @staticmethod
    def _area_center(axis):
        s = Area.SIZE
        return tuple(p * s + s // 2 for p in axis)

    @staticmethod
    def _collect_materials(field):
        """未回収の資材（保存対象は ID-034 サイクル 034-2）を残さないよう、プレイヤーが拾う"""
        for units in field.unit_map.values():
            for unit in [u for u in units if isinstance(u, Material)]:
                field.player.pos = unit.get_pos()
                field.update()

    def _assert_same_progress(self, field, restored, steps):
        """steps = [(プレイヤーの位置, フレーム数), ...] を両方の Field に同じ順で与え、
        毎フレームの描画と所持資材が一致することを確かめる"""
        for pos, frames in steps:
            for target in (field, restored):
                target.player.pos = pos
            for _ in range(frames):
                field.update()
                restored.update()
                self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
                self.assertEqual(
                    field.get_player_materials(), restored.get_player_materials()
                )

    def test_restore_resource_progress(self):
        """採取の進行・最終接触からの経過・採取済みの再生までの残り時間が復元され、
        保存前と同じフレームで採取の完了（資材の出現）・再生が起きる"""
        center = self._area_center((3, 2))
        away = self._area_center((10, 10))
        h = Resource.HARVEST_FRAMES
        r = Resource.REGEN_FRAMES
        test_cases = [
            ("harvesting", [(center, h // 2)]),
            ("harvesting then suspended", [(center, h // 2), (away, 5)]),
            ("harvested waiting regen", [(center, h + 100)]),
        ]
        for case_name, before_steps in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                field = self._resource_field()
                for pos, frames in before_steps:
                    field.player.pos = pos
                    for _ in range(frames):
                        field.update()
                self._collect_materials(field)

                restored = self._restore_via_json(field)

                self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
                self._assert_same_progress(
                    field,
                    restored,
                    [(center, h), (away, 20), (center, r + h)],
                )

    def test_restore_uncollected_materials(self):
        """拾わずに残した資材（資源が落としたもの・敵が落としたもの）の位置・種類・個数が復元され、
        拾うと保存前と同じ種類・個数が所持資材に加わる。種類・個数は保存データの値で、
        復元時に生成器へ引き直さない（保存後に生成器の個数が変わっても保存時の個数のまま）"""
        self.test_map_generator.set_material_ret_zero(False)
        field = self._resource_field()
        center = self._area_center((3, 2))
        field.player.pos = center
        for _ in range(Resource.HARVEST_FRAMES + 1):
            field.update()
        enemy = Enemy(center[0] + 20, center[1])
        enemy.hp = 0
        field.unit_map.setdefault((3, 2), []).append(enemy)
        field.update()
        materials = [
            unit for unit in field.unit_map[(3, 2)] if isinstance(unit, Material)
        ]
        self.assertEqual(2, len(materials))
        self.assertEqual(
            [MaterialType.WOOD] * 2, [material.get_type() for material in materials]
        )
        before = field.get_player_materials()

        self.test_map_generator.set_material_ret_zero(True)
        restored = self._restore_via_json(field)

        self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
        self._assert_same_progress(
            field,
            restored,
            [(material.get_pos(), 1) for material in materials],
        )
        self.assertNotEqual(before, restored.get_player_materials())

    def test_restore_workbench_progress(self):
        """作業台の投入済みの数・投入間隔の途中の接触フレーム数・加工の進行が復元され、
        保存前と同じフレームで次の投入・加工後の資材の出現が起きる"""
        center = self._area_center((3, 2))
        away = self._area_center((10, 10))
        interval = Workbench.INPUT_INTERVAL_FRAMES
        test_cases = [
            ("touching before first input", [(center, interval // 2)]),
            ("input after first interval", [(center, interval + 3)]),
            ("processing", [(center, interval * 2 + 5)]),
            ("touch interrupted", [(center, interval // 2), (away, 5)]),
        ]
        for case_name, before_steps in test_cases:
            with self.subTest(case_name=case_name):
                self.reset()
                self.test_map_generator.set_material_type(MaterialType.PLANK)
                self.test_map_generator.set_material_ret_zero(False)
                self.test_map_generator.set_workbench(
                    WorkbenchParam((MaterialType.WOOD,), 2, 60)
                )
                field = Field()
                field.player.add_material(MaterialType.WOOD, 10)
                self._open_area(field, (3, 2))
                for pos, frames in before_steps:
                    field.player.pos = pos
                    for _ in range(frames):
                        field.update()

                restored = self._restore_via_json(field)

                self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
                self._assert_same_progress(
                    field,
                    restored,
                    [(center, interval * 3), (away, 20), (center, 200)],
                )

    def _spawner_field(self):
        """スポナーのあるエリア (3, 2) を開放し、敵が追ってこない画面内の位置にプレイヤーを置いた Field"""
        self.test_map_generator.set_spawner_ret_zero(False)
        self.test_map_generator.set_material_ret_zero(False)
        self.test_map_generator.set_material_type(MaterialType.WOOD)
        field = Field()
        self._open_area(field, (3, 2))
        field.player.pos = self._area_center((6, 2))
        return field

    @staticmethod
    def _enemies(field):
        return [u for u in field.unit_map.get((3, 2), []) if isinstance(u, Enemy)]

    def _update_until_enemy(self, field):
        for _ in range(Spawner.START_SPAWN_INTERVAL * 2):
            if self._enemies(field):
                return
            field.update()
        self.fail("enemy did not appear")

    def test_restore_enemy_and_spawner_stays_quiet(self):
        """出現済みの敵（位置・強さ）が復元され、敵が残っているスポナーは復元後も
        新たな敵を出さない。敵を倒すと、保存前と同じ規則で次の敵を出す"""
        field = self._spawner_field()
        self._update_until_enemy(field)
        for _ in range(10):
            field.update()
        self.assertEqual(1, len(self._enemies(field)))

        restored = self._restore_via_json(field)

        self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
        self.assertEqual(
            [e.get_status() for e in self._enemies(field)],
            [e.get_status() for e in self._enemies(restored)],
        )
        self._assert_same_progress(
            field,
            restored,
            [(self._area_center((6, 2)), Spawner.START_SPAWN_INTERVAL * 3)],
        )
        self.assertEqual(1, len(self._enemies(restored)))
        for target in (field, restored):
            self._enemies(target)[0].hp = 0
        self._assert_same_progress(
            field,
            restored,
            [(self._area_center((6, 2)), Spawner.START_SPAWN_INTERVAL * 2)],
        )
        self.assertEqual(1, len(self._enemies(restored)))

    def test_restore_spawner_interval(self):
        """スポナーの次に敵を出現させるまでの残り時間が復元され、保存前と同じフレームで敵が出る"""
        field = self._spawner_field()
        for _ in range(Spawner.START_SPAWN_INTERVAL // 2):
            field.update()
        self.assertEqual([], self._enemies(field))

        restored = self._restore_via_json(field)

        self.assertEqual(self._draw_calls(field), self._draw_calls(restored))
        self._assert_same_progress(
            field, restored, [(self._area_center((6, 2)), Spawner.START_SPAWN_INTERVAL)]
        )
        self.assertEqual(1, len(self._enemies(restored)))

    def test_restore_killed_enemy_disappears_and_drops_material(self):
        """倒された直後（HP 0・無敵時間中）の敵は HP が復元され、無敵時間は保存されないため、
        復元後の最初の更新で消えて資材を落とす"""
        field = self._spawner_field()
        self._update_until_enemy(field)
        enemy = self._enemies(field)[0]
        enemy.hp = 0
        enemy.damaged_frames = 5

        restored = self._restore_via_json(field)

        self.assertEqual(0, self._enemies(restored)[0].get_status()[0])
        restored.update()
        self.assertEqual([], self._enemies(restored))
        self.assertEqual(
            1,
            len([u for u in restored.unit_map[(3, 2)] if isinstance(u, Material)]),
        )

    def test_restore_does_not_keep_invincibility(self):
        """無敵時間は保存せず、復元時はプレイヤー・敵とも無敵時間でない（点滅しない）。
        プレイヤーは復元直後の接触でダメージを受ける（既存の振る舞いの明文化）"""
        field = self._spawner_field()
        self._update_until_enemy(field)
        enemy = self._enemies(field)[0]
        enemy.set_hp(3)
        enemy.set_power(field.get_player_status()[2] + 1)
        enemy.set_damaged()
        field.player.set_damaged()
        self.assertEqual(2, field.get_player_status()[0])
        self.assertTrue(self._is_any_blinking(field))

        restored = self._restore_via_json(field)

        self.assertFalse(self._is_any_blinking(restored))
        self.assertEqual(2, restored.get_player_status()[0])
        restored.player.pos = self._enemies(restored)[0].get_pos()
        restored.update()
        self.assertEqual(1, restored.get_player_status()[0])

    def _is_any_blinking(self, field):
        _, unit_calls = self._draw_calls(field)
        return any(call[0] == "draw_unit" and call[-1] for call in unit_calls)

    def test_restore_does_not_notify_navigator(self):
        """復元でナビゲーションへイベントは送られない（復元で進行が進まない）"""
        field = Field()
        self._open_area(field, (3, 2))
        self.assertNotEqual([], self.test_navigator.events)
        self.test_navigator.events = []

        self._restore_via_json(field)

        self.assertEqual([], self.test_navigator.events)

    def test_restored_field_continues_unveil(self):
        """復元した Field は、開放済みエリアに隣接する開放対象に払うと、続けて開放できる"""
        field = Field()
        self._open_area(field, (3, 2))
        restored = self._restore_via_json(field)

        self.test_navigator.events = []
        self._open_area(restored, (4, 2))

        self.assertEqual([Event(EventType.UNVEIL, (4, 2))], self.test_navigator.events)
