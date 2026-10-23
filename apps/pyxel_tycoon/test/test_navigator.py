import json
import unittest
from unittest.mock import patch

from src.main import Event, EventType, InstructionKind, Navigator
from src.map_generator import AreaBlockAlgorithmGenerator, AreaKind, MaterialType


class TestNavigator(unittest.TestCase):
    """ナビゲーションの指示の進行（サイクル 029-3。U1・U5・U6）。

    navigator の入力はイベントだけで、目標のエリアは生成器の問い合わせ
    （`find_nearest_area`。サイクル 029-2 で確認済み）から求める。
    """

    # requirements.md フェーズ4「指示の流れ」（作業台の資材の採集は、投入を含めて 1 つの指示）
    # （(指示の種類, 目標の種別, ブロックのレベル)。ブロック1 = 0）
    EXPECTED_INSTRUCTION_LIST = [
        (InstructionKind.UNVEIL, AreaKind.TREE, 0),
        (InstructionKind.GATHER, AreaKind.TREE, 0),
        (InstructionKind.UNVEIL, AreaKind.ROCK, 0),
        (InstructionKind.GATHER, AreaKind.ROCK, 0),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 0),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 1),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 1),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 1),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 2),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 2),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 2),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 3),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 3),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 3),
    ]

    # 作業台で加工する資材（ブロックのレベル → 加工後の資材）
    WORKBENCH_MATERIAL_MAP = {
        1: MaterialType.PLANK,
        2: MaterialType.BRICK,
        3: MaterialType.HAMMER,
    }

    def setUp(self):
        self.generator = AreaBlockAlgorithmGenerator()
        self.navigator = Navigator(self.generator)

    def _non_workbench_area(self, lv, excluded_pos=None):
        """レベル lv のブロックの、作業台でないエリア（次のブロックの指示を達成するとき、
        作業台の指示まで続けて達成してしまうのを避けるために使う）"""
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        return next(
            (bx * s + dx, by * s + dy)
            for (bx, by), block_lv in self.generator.area_block_lv_map.items()
            if block_lv == lv
            for dx in range(s)
            for dy in range(s)
            if (bx * s + dx, by * s + dy) != excluded_pos
            and self.generator.get_workbench(bx * s + dx, by * s + dy) is None
        )

    def _unveil_current(self):
        """表示中の指示の目標のエリアを開放したイベントを送り、その座標を返す"""
        pos = self.navigator.current.pos
        self.navigator.notify(Event(EventType.UNVEIL, pos))
        return pos

    def _achieve_current(self):
        """表示中の指示を達成するイベントを送る。エリアの開放は目標のエリアの開放、
        資材の採集は目標のエリアでの指示の資材の拾得"""
        current = self.navigator.current
        if current.kind == InstructionKind.GATHER:
            self.navigator.notify(
                Event(EventType.GATHER, current.pos, current.material_type)
            )
        else:
            self.navigator.notify(Event(EventType.UNVEIL, current.pos))
        return current.pos

    def test_first_instruction(self):
        """最初の指示は Tree のエリアの開放。基準位置はスタート位置"""
        current = self.navigator.current
        self.assertEqual(InstructionKind.UNVEIL, current.kind)
        self.assertEqual(AreaKind.TREE, current.area_kind)
        self.assertEqual(
            self.generator.find_nearest_area(
                0, AreaKind.TREE, self.generator.get_start_pos()
            ),
            current.pos,
        )

    def test_advance_by_target_event(self):
        """目標のエリアの開放で次の指示へ進み、その目標は開放した座標を基準に決まる。
        目標でないエリアの開放では進まない"""
        self._unveil_current()
        wood_pos = self._achieve_current()
        self.assertEqual(InstructionKind.UNVEIL, self.navigator.current.kind)
        self.assertEqual(AreaKind.ROCK, self.navigator.current.area_kind)
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, wood_pos),
            self.navigator.current.pos,
        )

        rock = self.navigator.current
        self.navigator.notify(Event(EventType.UNVEIL, self.generator.get_start_pos()))
        self.assertEqual(rock, self.navigator.current)

    def test_next_block_advance_by_any_area_of_next_block(self):
        """次のブロックの指示は、目標以外でも次のブロックのいずれかのエリアの開放で進む。
        次の指示の目標は、その開放したエリアを基準に決まる"""
        for _ in range(4):
            self._achieve_current()
        current = self.navigator.current
        self.assertEqual(AreaKind.NEXT_BLOCK, current.area_kind)

        other_pos = self._non_workbench_area(1, current.pos)
        self.navigator.notify(Event(EventType.UNVEIL, other_pos))
        self.assertEqual(AreaKind.WORKBENCH, self.navigator.current.area_kind)
        self.assertEqual(
            self.generator.find_nearest_area(1, AreaKind.WORKBENCH, other_pos),
            self.navigator.current.pos,
        )

    def test_instruction_sequence_and_finish(self):
        """目標を順に達成すると、指示は Tree → Wood → Rock → Stone → （次のブロック → 作業台）→ … →
        ボスの撃破の順に進み、ボスの撃破のイベントで終了する（表示中の指示が無くなる）"""
        kind_list = []
        for _ in self.EXPECTED_INSTRUCTION_LIST:
            current = self.navigator.current
            kind_list.append((current.kind, current.area_kind, current.block_lv))
            if current.area_kind == AreaKind.NEXT_BLOCK:
                # 目標が作業台のエリアだと、続く作業台の指示まで達成してしまうため避ける
                pos = current.pos
                if self.generator.get_workbench(*pos) is not None:
                    pos = self._non_workbench_area(current.block_lv + 1)
                self.navigator.notify(Event(EventType.UNVEIL, pos))
            else:
                self._achieve_current()
        self.assertEqual(self.EXPECTED_INSTRUCTION_LIST, kind_list)

        current = self.navigator.current
        self.assertEqual(InstructionKind.DEFEAT_BOSS, current.kind)
        self.assertEqual(self.generator.get_boss_pos(), current.pos)

        self.navigator.notify(Event(EventType.UNVEIL, self.generator.get_boss_pos()))
        self.assertEqual(current, self.navigator.current)
        self.navigator.notify(
            Event(EventType.DEFEAT_BOSS, self.generator.get_boss_pos())
        )
        self.assertIsNone(self.navigator.current)

    def test_skip_achieved_instruction(self):
        """後の指示の目標を先に達成していると、前の指示をクリアしたときに、その指示は
        即座にクリアとなり、未達成の指示まで一度に進む。即時クリアで進んだ後の目標は、
        その指示を達成した履歴のイベントの座標を基準に決まる"""
        tree_pos = self.navigator.current.pos
        rock_pos = self.generator.find_nearest_area(0, AreaKind.ROCK, tree_pos)
        # Tree より先に、Tree を基準にしたときの Rock の目標を開放しておく
        self.navigator.notify(Event(EventType.UNVEIL, rock_pos))
        self.assertEqual(AreaKind.TREE, self.navigator.current.area_kind)

        self.navigator.notify(Event(EventType.UNVEIL, tree_pos))
        self._achieve_current()
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.ROCK, 0),
            (current.kind, current.area_kind, current.block_lv),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, rock_pos),
            current.pos,
        )

    def test_skip_achieved_instruction_chain(self):
        """達成済みの指示が続く場合は、未達成の指示に当たるまで繰り返し進む。
        1 つのイベントが連続する複数の指示を達成することもある
        （ブロック2 の作業台のエリアの開放は、次のブロックの指示と作業台の開放の指示を達成し、
        加工後の資材の採集の指示で止まる）"""
        workbench_pos = self.generator.find_nearest_area(
            1, AreaKind.WORKBENCH, self.generator.get_start_pos()
        )
        self.navigator.notify(Event(EventType.UNVEIL, workbench_pos))
        for _ in range(4):
            self._achieve_current()
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.WORKBENCH, 1, MaterialType.PLANK),
            (current.kind, current.area_kind, current.block_lv, current.material_type),
        )
        self.assertEqual(
            self.generator.find_nearest_area(1, AreaKind.WORKBENCH, workbench_pos),
            current.pos,
        )

    def _area_list(self, lv):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        return [
            (bx * s + dx, by * s + dy)
            for (bx, by), block_lv in self.generator.area_block_lv_map.items()
            if block_lv == lv
            for dx in range(s)
            for dy in range(s)
        ]

    def _same_kind_other_area(self, lv, target_pos, material_type):
        """レベル lv のブロックの、資材が material_type のスポナーでないエリア
        （Tree・Rock）のうち、target_pos でないもの"""
        return next(
            pos
            for pos in self._area_list(lv)
            if pos != target_pos
            and self.generator.get_material_type(*pos) == material_type
            and self.generator.get_spawner_power(*pos) == 0
        )

    def test_advance_by_same_kind_other_area(self):
        """達成は位置ではなく種別で判定する（U6 改訂）。目標でない同じブロックの同じ種別の
        エリア（もう一方の Rock）の開放でも進み、次の目標はその開放したエリアを基準に決まる"""
        tree_pos = self._unveil_current()
        self._achieve_current()
        rock_pos = self.navigator.current.pos
        other_rock_pos = self._same_kind_other_area(0, rock_pos, MaterialType.STONE)
        self.navigator.notify(Event(EventType.UNVEIL, other_rock_pos))
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.ROCK),
            (current.kind, current.area_kind),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, other_rock_pos),
            current.pos,
        )
        self.assertNotEqual(tree_pos, other_rock_pos)

    def test_skip_by_same_kind_other_area(self):
        """目標でない同じ種別のエリア（もう一方の Rock）を先に開放していると、
        Rock の指示は即座にクリアとなる。次の目標は、その開放したエリアを基準に決まる"""
        tree_pos = self.navigator.current.pos
        rock_pos = self.generator.find_nearest_area(0, AreaKind.ROCK, tree_pos)
        other_rock_pos = self._same_kind_other_area(0, rock_pos, MaterialType.STONE)
        self.navigator.notify(Event(EventType.UNVEIL, other_rock_pos))
        self.navigator.notify(Event(EventType.UNVEIL, tree_pos))
        self._achieve_current()
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.ROCK),
            (current.kind, current.area_kind),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, other_rock_pos),
            current.pos,
        )

    def test_gather_instruction_after_unveil(self):
        """Tree・Rock のエリアの開放の次は、Wood・Stone の採集の指示。目標は、その資材を
        得られる同じブロックの資源のうち、直前の指示を達成した位置に最も近いもの（U3）"""
        tree_pos = self._unveil_current()
        wood = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.TREE, 0, MaterialType.WOOD),
            (wood.kind, wood.area_kind, wood.block_lv, wood.material_type),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.TREE, tree_pos), wood.pos
        )

        self._achieve_current()
        rock_pos = self._unveil_current()
        stone = self.navigator.current
        self.assertEqual(
            (InstructionKind.GATHER, AreaKind.ROCK, 0, MaterialType.STONE),
            (stone.kind, stone.area_kind, stone.block_lv, stone.material_type),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, rock_pos), stone.pos
        )

    def test_gather_advance_by_material_event(self):
        """採集の指示は、その種類の資材の拾得で進む。拾ったエリアは目標でなくてもよい
        （敵のドロップなど。U1）。次の目標は、拾ったエリアを基準に決まる"""
        self._unveil_current()
        start_pos = self.generator.get_start_pos()
        self.navigator.notify(Event(EventType.GATHER, start_pos, MaterialType.WOOD))
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.UNVEIL, AreaKind.ROCK),
            (current.kind, current.area_kind),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, start_pos), current.pos
        )

    def test_gather_not_advance_by_other_event(self):
        """採集の指示は、別の種類の資材の拾得や、目標のエリアの開放では進まない"""
        self._unveil_current()
        wood = self.navigator.current
        for material_type in (MaterialType.STONE, MaterialType.PLANK):
            self.navigator.notify(Event(EventType.GATHER, wood.pos, material_type))
            self.assertEqual(wood, self.navigator.current)
        self.navigator.notify(Event(EventType.UNVEIL, wood.pos))
        self.assertEqual(wood, self.navigator.current)

    def test_skip_gather_achieved_before_instruction(self):
        """採集の指示が表示される前に資材を拾っていると、その指示は即座にクリアとなる（U1）。
        次の目標は、拾ったエリアを基準に決まる"""
        tree_pos = self.navigator.current.pos
        start_pos = self.generator.get_start_pos()
        self.navigator.notify(Event(EventType.GATHER, start_pos, MaterialType.WOOD))
        self.assertEqual(AreaKind.TREE, self.navigator.current.area_kind)

        self.navigator.notify(Event(EventType.UNVEIL, tree_pos))
        current = self.navigator.current
        self.assertEqual(
            (InstructionKind.UNVEIL, AreaKind.ROCK),
            (current.kind, current.area_kind),
        )
        self.assertEqual(
            self.generator.find_nearest_area(0, AreaKind.ROCK, start_pos), current.pos
        )

    def test_gather_workbench_material(self):
        """作業台のエリアの開放の次は、加工後の資材（Plank・Brick・Hammer）の採集の指示
        （作業台への投入を含む。U2）。目標はそのブロックの作業台で、加工後の資材の拾得で
        次の指示へ進む。作業台のエリアの開放や別の資材の拾得では進まない"""
        for _ in range(4):
            self._achieve_current()
        for block_lv, material_type in self.WORKBENCH_MATERIAL_MAP.items():
            with self.subTest(block_lv=block_lv):
                # 次のブロックの開放（作業台でないエリア）→ 作業台の開放
                self.navigator.notify(
                    Event(EventType.UNVEIL, self._non_workbench_area(block_lv))
                )
                workbench_pos = self._unveil_current()
                current = self.navigator.current
                self.assertEqual(
                    (InstructionKind.GATHER, AreaKind.WORKBENCH, block_lv),
                    (current.kind, current.area_kind, current.block_lv),
                )
                self.assertEqual(material_type, current.material_type)
                self.assertEqual(
                    self.generator.find_nearest_area(
                        block_lv, AreaKind.WORKBENCH, workbench_pos
                    ),
                    current.pos,
                )
                self.assertEqual(
                    material_type,
                    self.generator.get_material_type(*current.pos),
                )

                self.navigator.notify(Event(EventType.UNVEIL, current.pos))
                self.navigator.notify(
                    Event(EventType.GATHER, current.pos, MaterialType.WOOD)
                )
                self.assertEqual(current, self.navigator.current)

                self._achieve_current()
                self.assertEqual(AreaKind.NEXT_BLOCK, self.navigator.current.area_kind)

    def test_full_instruction_sequence(self):
        """ゲーム開始からボスの撃破まで、requirements.md フェーズ4 の 15 個の指示を
        順にクリアできる（作業台への投入だけでは進まず、加工後の資材の拾得で進む）"""
        count = 0
        while self.navigator.current.kind != InstructionKind.DEFEAT_BOSS:
            current = self.navigator.current
            if current.area_kind == AreaKind.NEXT_BLOCK and (
                self.generator.get_workbench(*current.pos) is not None
            ):
                pos = self._non_workbench_area(current.block_lv + 1)
                self.navigator.notify(Event(EventType.UNVEIL, pos))
            else:
                self._achieve_current()
            count += 1
        self.assertEqual(14, count)
        self.navigator.notify(
            Event(EventType.DEFEAT_BOSS, self.generator.get_boss_pos())
        )
        self.assertIsNone(self.navigator.current)

    def test_not_advance_by_same_kind_in_other_block(self):
        """同じ種別でも別のブロックのエリア（ブロック2 の Tree）の開放では進まない"""
        target = self.navigator.current
        other_block_tree_pos = self._same_kind_other_area(
            1, target.pos, MaterialType.WOOD
        )
        self.navigator.notify(Event(EventType.UNVEIL, other_block_tree_pos))
        self.assertEqual(target, self.navigator.current)

    def test_notify_returns_cleared_steps(self):
        """notify は今回クリアした指示の添字（STEPS の位置）のリストを返す。
        クリアなしは空、1 つなら 1 要素、即時クリアで進んだ分はすべて含む
        （サイクル 031-2。U3）"""
        tree_pos = self.navigator.current.pos
        wood_event = Event(EventType.GATHER, tree_pos, MaterialType.WOOD)
        self.assertEqual([], self.navigator.notify(wood_event))
        self.assertEqual(
            [0, 1], self.navigator.notify(Event(EventType.UNVEIL, tree_pos))
        )
        self.assertEqual([], self.navigator.notify(Event(EventType.UNVEIL, tree_pos)))
        self.assertEqual(2, self.navigator.step)
        rock_pos = self.navigator.current.pos
        self.assertEqual([2], self.navigator.notify(Event(EventType.UNVEIL, rock_pos)))

    def test_locate_step(self):
        """指示の添字から、ブロックの順位・ブロック内の順位・ブロック内の指示の個数を
        求める。ボスの撃破（強化なし。U5）と範囲外は None"""
        test_cases = [
            (0, (0, 0, 5)),
            (4, (0, 4, 5)),
            (5, (1, 0, 3)),
            (7, (1, 2, 3)),
            (8, (2, 0, 3)),
            (13, (3, 2, 3)),
            (14, None),
            (15, None),
        ]
        for step, expected in test_cases:
            with self.subTest(step=step):
                self.assertEqual(expected, Navigator.locate_step(step))


class TestNavigatorSingleton(unittest.TestCase):
    """Navigator のシングルトン（サイクル 029-5。U8）。生成器の再生成と対にして使う"""

    def test_create_and_recreate(self):
        """create() は同じインスタンスを返し、recreate() で新しいマップの最初の指示から
        始まる新しいインスタンスに作り直される"""
        generator = AreaBlockAlgorithmGenerator.recreate()
        navigator = Navigator.recreate()
        self.assertIs(navigator, Navigator.create())
        navigator.notify(Event(EventType.UNVEIL, navigator.current.pos))
        self.assertEqual(InstructionKind.GATHER, navigator.current.kind)

        generator = AreaBlockAlgorithmGenerator.recreate()
        new_navigator = Navigator.recreate()
        self.assertIsNot(navigator, new_navigator)
        self.assertIs(new_navigator, Navigator.create())
        self.assertEqual(AreaKind.TREE, new_navigator.current.area_kind)
        self.assertEqual(
            generator.find_nearest_area(0, AreaKind.TREE, generator.get_start_pos()),
            new_navigator.current.pos,
        )


class TestNavigatorSaveData(unittest.TestCase):
    """ナビゲーションの進行（指示の位置・表示中の指示・イベントの履歴）の保存データへの
    変換と復元（ID-033 サイクル 033-3。U2）。復元はイベントの再実行ではなく、値を直接与え直す。
    """

    def setUp(self):
        self.generator = AreaBlockAlgorithmGenerator()
        for target, name in (
            (AreaBlockAlgorithmGenerator, "_instance"),
            (Navigator, "_instance"),
        ):
            patcher = patch.object(
                target, name, self.generator if target is not Navigator else None
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        self.navigator = Navigator(self.generator)

    def _restore_via_json(self, navigator):
        return Navigator.restore(json.loads(json.dumps(navigator.to_save_data())))

    def _advance_with_gather_history(self):
        """Tree のエリアの開放の指示を終えて資材（Wood）の採集の指示を表示している状態で、
        表示中の指示より先の指示を達成するイベント（Rock の開放・Stone の拾得）を
        履歴に持たせる。履歴のイベントで、以後の Wood の拾得で続く指示まで即時クリアとなる"""
        tree_pos = self.navigator.current.pos
        self.navigator.notify(Event(EventType.UNVEIL, tree_pos))
        rock_pos = self.generator.find_nearest_area(0, AreaKind.ROCK, tree_pos)
        self.assertEqual([], self.navigator.notify(Event(EventType.UNVEIL, rock_pos)))
        self.assertEqual(
            [],
            self.navigator.notify(
                Event(EventType.GATHER, rock_pos, MaterialType.STONE)
            ),
        )
        return tree_pos

    def test_restore_gives_same_current_and_step(self):
        """JSON を往復して復元した navigator は、保存前と同じ表示中の指示・指示の位置を持つ"""
        self._advance_with_gather_history()
        restored = self._restore_via_json(self.navigator)
        self.assertEqual(self.navigator.step, restored.step)
        self.assertEqual(self.navigator.current, restored.current)
        self.assertEqual(InstructionKind.GATHER, restored.current.kind)

    def test_restore_gives_same_clear_by_history(self):
        """復元した navigator は、以後のイベントに対して保存前と同じ指示のクリアを返す。
        履歴にある先の指示のイベントによる即時クリアを含む"""
        tree_pos = self._advance_with_gather_history()
        restored = self._restore_via_json(self.navigator)

        event = Event(EventType.GATHER, tree_pos, MaterialType.WOOD)
        expected = self.navigator.notify(event)
        self.assertEqual([1, 2, 3], expected)  # Wood の拾得・Rock の開放・Stone の拾得
        self.assertEqual(expected, restored.notify(event))
        self.assertEqual(self.navigator.current, restored.current)

    def test_restore_replaces_singleton(self):
        """復元した navigator が、以後の create() の返す navigator（シングルトン）になる"""
        restored = self._restore_via_json(self.navigator)
        self.assertIsNot(self.navigator, restored)
        self.assertIs(restored, Navigator.create())

    def test_restore_finished_navigator(self):
        """全ての指示を終えて表示中の指示が無い状態も、そのまま復元できる"""
        while self.navigator.current is not None:
            current = self.navigator.current
            if current.kind == InstructionKind.DEFEAT_BOSS:
                event = Event(EventType.DEFEAT_BOSS, current.pos)
            elif current.kind == InstructionKind.GATHER:
                event = Event(EventType.GATHER, current.pos, current.material_type)
            else:
                event = Event(EventType.UNVEIL, current.pos)
            self.navigator.notify(event)
        restored = self._restore_via_json(self.navigator)
        self.assertIsNone(restored.current)
        self.assertEqual(self.navigator.step, restored.step)
