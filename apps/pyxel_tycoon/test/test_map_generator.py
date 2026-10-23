import json
import unittest
from unittest.mock import patch
from src.map_generator import (
    AreaBlockAlgorithmGenerator,
    AreaKind,
    AreaParam,
    MaterialType,
)


class GeneratorTestHelper:
    ADJACENT_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    @classmethod
    def _adjacent_pos_list(cls, pos):
        return [(pos[0] + dx, pos[1] + dy) for dx, dy in cls.ADJACENT_DIRECTIONS]

    @classmethod
    def _is_tree(cls, generator, pos):
        """公開の getter だけで Tree（スポナー無しの Wood）のエリアかを判定する"""
        return (
            generator.get_material_type(*pos) == MaterialType.WOOD
            and generator.get_spawner_power(*pos) == 0
        )


class TestAreaBlockAlgorithmGenerator(  # pylint: disable=too-many-public-methods
    GeneratorTestHelper, unittest.TestCase
):
    # requirements.md 開発フェーズ3「資源の種類と配置」「資源の採取量」の値（添字が
    # distance）。実装の定数（TREE_NUM など）を参照すると定数を変えても Red にならない
    # ため、要件の値をリテラルで持つ（サイクル 027-1）
    REQUIRED_TREE_NUM = (2, 3, 3, 3, 4)
    REQUIRED_ROCK_NUM = (2, 3, 3, 3, 4)
    REQUIRED_MATERIAL_NUM = (6, 8, 13, 28, 40)

    @patch("src.map_generator.AreaBlockAlgorithmGenerator._shuffle")
    def test_get(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        mock.return_value = [
            [
                AreaParam(
                    fee_num=x,
                    enemy_power=y,
                    spawner_power=1 if (x, y) == (1, 1) else 0,
                    material_num=1 if (x, y) == (2, 2) else 0,
                )
                for x in range(s)
            ]
            for y in range(s)
        ]
        test_cases = [
            ("pos spawner", 1, 1, 1, 0, (1, 1)),
            ("pos resource", 2, 2, 0, 1, (2, 2)),
            ("pos 1", s // 2, s // 2, 0, 0, (s // 2, s // 2)),
            ("pos 2", 0, s - 1, 0, 0, (0, s - 1)),
            ("pos 3", s - 1, 0, 0, 0, (s - 1, 0)),
            ("pos 4", s - 1, s - 1, 0, 0, (s - 1, s - 1)),
        ]
        for (
            case_name,
            eep,
            efn,
            esp,
            emp,
            area_axis,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                expected_enemy_power=eep,
                expected_fee_num=efn,
                expected_spawner_power=esp,
                expected_material_num=emp,
                area_axis=area_axis,
            ):
                map_genetator = AreaBlockAlgorithmGenerator()
                self.assertEqual(eep, map_genetator.get_enemy_power(*area_axis))
                self.assertEqual(efn, map_genetator.get_fee_num(*area_axis))
                self.assertEqual(esp, map_genetator.get_spawner_power(*area_axis))
                self.assertEqual(emp, map_genetator.get_material_num(*area_axis))

    def test_get_fee_num(self):
        """開放対象を置く全エリアで、1エリアあたりの必要量がエリアの属する
        ブロックごとの値として返ることを確認する（サイクル 026-3。
        requirements.md 開発フェーズ3「エリア開放条件」）。

        ブロック1: 2、ブロック2: 4、ブロック3: 1、ブロック4: 2、ブロック5: 1。
        経路外のブロックは開放対象を置かないため全エリア 0 になる。ブロック1 のスタートに隣接する
        Tree は 1 になるため、このテストでは除く（サイクル 026-5）。
        旧仕様の `test_sum_area_block`（必要量の合計が距離に応じて単調増加する）は、
        資材の種類がブロックごとに異なり数の合計を比べる意味が無くなったため
        削除した（U3）。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (start block)", {(0, 0): 0}, 2),
            ("lv 1", {(0, 0): 1}, 4),
            ("lv 2", {(0, 0): 2}, 1),
            ("lv 3", {(0, 0): 3}, 2),
            ("lv 4", {(0, 0): 4}, 1),
            ("out of route", {}, 0),
        ]
        for case_name, block_path_map, expected_num in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                # スタートに隣接する Tree の必要量 1 は test_get_fee_num_start_adjacent_tree
                # で確認する。ここではスタート隣接の Tree を除いたエリアを見る
                start_tree_set = set()
                if case_name == "lv 0 (start block)":
                    start_pos = map_genetator.get_start_pos()
                    start_tree_set = {
                        pos
                        for pos in self._adjacent_pos_list(start_pos)
                        if self._is_tree(map_genetator, pos)
                    }
                fee_nums = [
                    map_genetator.get_fee_num(x, y)
                    for x in range(s)
                    for y in range(s)
                    if (x, y) not in start_tree_set
                ]
                self.assertEqual(
                    [expected_num] * (s**2 - len(start_tree_set)),
                    fee_nums,
                    "ブロック内の全エリアの必要量がブロックの値のはず",
                )

    def test_spawner_only_one(self):
        """スポナーは各ブロックにちょうど1エリアだけ配置される

        スポナーは経路上のすべてのブロック（distance(lv) 0〜4）に1つずつ配置され
        （requirements.md §3.7。ID-027 U5）、`area_block_lv_map` に無いブロックには
        配置されない。強さはブロックごとの式 `2 ** (lv + 1)`（`are_level_map[2]`）に
        従う。実際の `_get_area_num_list`/`_shuffle` を通して確認する。

        移植元 `../pyxel_expand_area/` に対応テストは無い（MG `test_spawner_coin` は
        コイン依存のテストでフェーズ1で削除済み）。`tasks.md` の ID-014 完了条件
        「スポナーがマップ上に1つだけであること」の機械的な検証手段として、ID-021で
        移植元に対応が無い独自追加であることを明記した上で残し、ID-027 でスポナーを
        各ブロック1つずつへ広げたのに合わせて期待値を更新した。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (start block)", {(0, 0): 0}, (0, 0), 1, 2),
            ("lv 1", {(0, 0): 1}, (0, 0), 1, 4),
            ("lv 2", {(0, 0): 2}, (0, 0), 1, 8),
            ("lv 3", {(0, 0): 3}, (0, 0), 1, 16),
            ("lv 4", {(0, 0): 4}, (0, 0), 1, 32),
            ("out of route", {}, (0, 0), 0, None),
        ]
        for case_name, block_path_map, block_pos, expected_count, power in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                power_list = [
                    p
                    for x in range(s)
                    for y in range(s)
                    if (
                        p := map_genetator.get_spawner_power(
                            *(q + b * s for q, b in zip((x, y), block_pos))
                        )
                    )
                    > 0
                ]
                self.assertEqual(expected_count, len(power_list))
                self.assertEqual([power] * expected_count, power_list)

    def test_spawner_area_material(self):
        """スポナーを置くエリアは、資源の採取量（サイクル 023-3 でブロックごとの
        値へ変更）とは独立に、そのブロックの開放に必要な資材を1個返す（U1〜U3）。

        敵の撃破時の資材ドロップ（ID-020-2）は、撃破位置のエリアの
        get_material_type / get_material_num から種類・個数を決める。ID-027 で
        スポナーを各ブロックに配置したため、ブロック1〜5（distance 0〜4）の
        スポナーのエリアが、同じエリアの get_fee_type と同じ種類（Wood・Stone・
        Plank・Brick・Hammer。requirements.md 開発フェーズ3「エリア開放条件」）の
        資材を1個返すことを確認する。経路外のブロックにはスポナーが無い。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (block 1)", 0, MaterialType.WOOD),
            ("lv 1 (block 2)", 1, MaterialType.STONE),
            ("lv 2 (block 3)", 2, MaterialType.PLANK),
            ("lv 3 (block 4)", 3, MaterialType.BRICK),
            ("lv 4 (block 5)", 4, MaterialType.HAMMER),
        ]
        for case_name, lv, expected_type in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = {(0, 0): lv}
                spawner_pos = next(
                    (x, y)
                    for x in range(s)
                    for y in range(s)
                    if map_genetator.get_spawner_power(x, y) != 0
                )
                self.assertEqual(
                    expected_type, map_genetator.get_material_type(*spawner_pos)
                )
                self.assertEqual(
                    map_genetator.get_fee_type(*spawner_pos),
                    map_genetator.get_material_type(*spawner_pos),
                    "ドロップの種類はそのエリアの開放に必要な資材と同じはず",
                )
                self.assertEqual(1, map_genetator.get_material_num(*spawner_pos))

    def test_get_workbench(self):
        """作業台はブロック（distance）ごとに、requirements.mdの作業台の表（Plankの
        作業台: ブロック2=distance1、Brickの作業台: ブロック3=distance2、Hammerの
        作業台: ブロック4=distance3）どおり0または1エリアに配置される（サイクル
        024-2・025-3）。

        作業台の内容（消費する素材の種類・必要量・加工時間）はget_workbenchが返す
        WorkbenchParamで表し、加工後の資材の種類・個数は作業台の項目自体には持たせず
        （U2）、作業台のエリアのget_material_type/get_material_numがPlank/Brick・1個を
        返す（U1）。Hammerの作業台はPlank・Brickの2種類を各5個消費して90フレームで加工する
        （ID-025）。作業台の無いブロックとルート外のブロックは全エリアでNoneになる。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        from src.map_generator import WorkbenchParam  # pylint: disable=C0415

        test_cases = [
            ("lv 0 (start block, no workbench)", {(0, 0): 0}, (0, 0), None, None),
            (
                "lv 1 (Plank workbench)",
                {(0, 0): 1},
                (0, 0),
                WorkbenchParam((MaterialType.WOOD,), 10, 60),
                MaterialType.PLANK,
            ),
            (
                "lv 2 (Brick workbench)",
                {(0, 0): 2},
                (0, 0),
                WorkbenchParam((MaterialType.STONE,), 10, 60),
                MaterialType.BRICK,
            ),
            (
                "lv 3 (Hammer workbench)",
                {(0, 0): 3},
                (0, 0),
                WorkbenchParam((MaterialType.PLANK, MaterialType.BRICK), 5, 90),
                MaterialType.HAMMER,
            ),
            ("lv 4 (no workbench)", {(0, 0): 4}, (0, 0), None, None),
        ]
        for (
            case_name,
            block_path_map,
            block_pos,
            expected_workbench,
            expected_output_type,
        ) in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                positions = [
                    tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for x in range(s)
                    for y in range(s)
                ]
                workbenches = [map_genetator.get_workbench(*pos) for pos in positions]
                workbench_positions = [
                    pos for pos, wb in zip(positions, workbenches) if wb is not None
                ]
                if expected_workbench is None:
                    self.assertEqual([], workbench_positions, case_name)
                    continue
                self.assertEqual(1, len(workbench_positions), case_name)
                workbench_pos = workbench_positions[0]
                self.assertEqual(
                    expected_workbench,
                    map_genetator.get_workbench(*workbench_pos),
                    case_name,
                )
                self.assertEqual(
                    expected_output_type,
                    map_genetator.get_material_type(*workbench_pos),
                    "作業台のエリアのget_material_typeは加工後の資材のはず（U1）",
                )
                self.assertEqual(
                    1,
                    map_genetator.get_material_num(*workbench_pos),
                    "作業台のエリアのget_material_numは加工後の資材の個数（1）のはず（U1）",
                )
                self.assertEqual(
                    map_genetator.get_workbench(*workbench_pos),
                    map_genetator.get_workbench(*workbench_pos),
                    "同じ座標への問い合わせは決定論的であるはず",
                )
        with self.subTest(case_name="out of route"):
            map_genetator = AreaBlockAlgorithmGenerator()
            map_genetator.area_block_lv_map = {}
            workbenches = [
                map_genetator.get_workbench(x, y) for x in range(s) for y in range(s)
            ]
            self.assertEqual([], [wb for wb in workbenches if wb is not None])

    def test_get_material_type(self):
        """ブロック（distance）ごとに、資材の種類が Wood のエリアが Tree の数、Stone の
        エリアが Rock の数だけ存在することを確認する（サイクル 023-1。requirements.md
        開発フェーズ3「資源の種類と配置」）。スポナーのエリア（そのブロックの開放に
        必要な資材。ID-027 U1）は Tree/Rock の集計から除く。ルート外のブロックは全エリア None のままになる。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (start block)", {(0, 0): 0}, (0, 0), 0),
            ("lv 1", {(0, 0): 1}, (0, 0), 1),
            ("lv 2", {(0, 0): 2}, (0, 0), 2),
            ("lv 3", {(0, 0): 3}, (0, 0), 3),
            ("lv 4", {(0, 0): 4}, (0, 0), 4),
        ]
        for case_name, block_path_map, block_pos, lv in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                positions = [
                    tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for x in range(s)
                    for y in range(s)
                ]
                # スポナーのエリアの資材（ID-027 U1）は Tree/Rock の集計から除く
                non_spawner_positions = [
                    pos
                    for pos in positions
                    if map_genetator.get_spawner_power(*pos) == 0
                ]
                material_types = [
                    map_genetator.get_material_type(*pos)
                    for pos in non_spawner_positions
                ]
                material_nums = [
                    map_genetator.get_material_num(*pos)
                    for pos in non_spawner_positions
                ]
                wood_count = material_types.count(MaterialType.WOOD)
                stone_count = material_types.count(MaterialType.STONE)
                self.assertEqual(
                    self.REQUIRED_TREE_NUM[lv],
                    wood_count,
                    "Wood(Tree) のエリア数が要件の数と一致するはず",
                )
                self.assertEqual(
                    self.REQUIRED_ROCK_NUM[lv],
                    stone_count,
                    "Stone(Rock) のエリア数が要件の数と一致するはず",
                )
                self.assertEqual(
                    [num != 0 for num in material_nums],
                    [t is not None for t in material_types],
                    "material_num の有無と種類の有無が一致するはず",
                )
                self.assertEqual(
                    material_types,
                    [
                        map_genetator.get_material_type(*pos)
                        for pos in non_spawner_positions
                    ],
                    "同じ座標への問い合わせは決定論的であるはず",
                )
        with self.subTest(case_name="out of route"):
            map_genetator = AreaBlockAlgorithmGenerator()
            map_genetator.area_block_lv_map = {}
            material_types = [
                map_genetator.get_material_type(x, y)
                for x in range(s)
                for y in range(s)
            ]
            self.assertEqual(set(), {t for t in material_types if t is not None})

    def test_get_material_num(self):
        """資源のエリア（スポナー・作業台のエリアを除く）の get_material_num が、
        ブロックごとに定めた採取量（6/8/13/28/40）と一致することを確認する（サイクル
        023-3。requirements.md 開発フェーズ3「資源の採取量」）。資源の無いエリア
        （スポナー・作業台を除く）の採取量は0のままである。

        作業台のエリアも get_material_type が None でない（U1。加工後の資材が
        Plank/Brick）ため、資源のエリアの判定にスポナーの除外と同様、作業台の除外も
        必要になる（サイクル024-2）。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (start block)", {(0, 0): 0}, (0, 0), 0),
            ("lv 1", {(0, 0): 1}, (0, 0), 1),
            ("lv 2", {(0, 0): 2}, (0, 0), 2),
            ("lv 3", {(0, 0): 3}, (0, 0), 3),
            ("lv 4", {(0, 0): 4}, (0, 0), 4),
        ]
        for case_name, block_path_map, block_pos, lv in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                positions = [
                    tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for x in range(s)
                    for y in range(s)
                ]
                non_spawner_positions = [
                    pos
                    for pos in positions
                    if map_genetator.get_spawner_power(*pos) == 0
                ]
                resource_positions = [
                    pos
                    for pos in non_spawner_positions
                    if map_genetator.get_material_type(*pos) is not None
                    and map_genetator.get_workbench(*pos) is None
                ]
                material_nums = {
                    map_genetator.get_material_num(*pos) for pos in resource_positions
                }
                self.assertEqual(
                    {self.REQUIRED_MATERIAL_NUM[lv]},
                    material_nums,
                    "資源のエリアの採取量はブロックごとの値のはず",
                )
                non_resource_positions = [
                    pos
                    for pos in non_spawner_positions
                    if pos not in resource_positions
                    and map_genetator.get_workbench(*pos) is None
                ]
                self.assertTrue(
                    all(
                        map_genetator.get_material_num(*pos) == 0
                        for pos in non_resource_positions
                    ),
                    "資源の無い、作業台でも無いエリア（スポナーを除く）の採取量は0のはず",
                )

    def test_get_fee_type(self):
        """開放対象を置く全エリア（fee_num > 0）で、開放に必要な資材の種類が
        エリアの属するブロックごとの種類として決定論的に返ることを確認する
        （サイクル 026-2。requirements.md 開発フェーズ3「エリア開放条件」）。

        ブロック1: Wood、ブロック2: Stone、ブロック3: Plank、ブロック4: Brick、
        ブロック5: Hammer。開放対象を置かないエリア（fee_num == 0。経路外）は
        None になる。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (start block)", {(0, 0): 0}, (0, 0), MaterialType.WOOD),
            ("lv 1", {(0, 0): 1}, (0, 0), MaterialType.STONE),
            ("lv 2", {(0, 0): 2}, (0, 0), MaterialType.PLANK),
            ("lv 3", {(0, 0): 3}, (0, 0), MaterialType.BRICK),
            ("lv 4", {(0, 0): 4}, (0, 0), MaterialType.HAMMER),
            ("out of route", {}, (0, 0), None),
        ]
        for case_name, block_path_map, block_pos, expected_type in test_cases:
            with self.subTest(case_name=case_name):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                positions = [
                    tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for x in range(s)
                    for y in range(s)
                ]
                fee_nums = [map_genetator.get_fee_num(*pos) for pos in positions]
                fee_types = [map_genetator.get_fee_type(*pos) for pos in positions]
                self.assertEqual(
                    [num > 0 for num in fee_nums],
                    [t is not None for t in fee_types],
                    "fee_num の有無と開放に必要な資材の種類の有無が一致するはず",
                )
                non_none_types = {t for t in fee_types if t is not None}
                self.assertEqual(
                    non_none_types,
                    set() if expected_type is None else {expected_type},
                    "ブロック内の開放対象を置く全エリアが同じ種類のはず",
                )
                self.assertEqual(
                    fee_types,
                    [map_genetator.get_fee_type(*pos) for pos in positions],
                    "同じ座標への問い合わせは決定論的であるはず",
                )

    def test_get_start_materials(self):
        """ゲーム開始時の所持資材として木材1が返ることを確認する
        （requirements.md 開発フェーズ3「開始時の資材と序盤の開放」）。
        何度問い合わせても同じ値であること。
        """
        map_genetator = AreaBlockAlgorithmGenerator()
        expected = [(MaterialType.WOOD, 1)]
        self.assertEqual(expected, map_genetator.get_start_materials())
        self.assertEqual(
            map_genetator.get_start_materials(),
            map_genetator.get_start_materials(),
            "同じ問い合わせは決定論的であるはず",
        )

    def _count_group_num_map(self, n, zero_rate, sep_num, dup_num, start_num):
        counts = {}
        for i in range(int(n * (1 - zero_rate))):
            group = (i // dup_num) % sep_num
            counts[start_num + group] = counts.get(start_num + group, 0) + 1
        if zero_rate > 0:
            counts[0] = int(n * zero_rate)
        return counts

    def test_level_count(self):  # pylint: disable=too-many-locals
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("case 1", (0, 0), 2, 1, {(0, 0): 0}),
            ("case 2", (1, 0), 4, 3, {(1, 0): 1}),
            ("case 3", (1, 1), 8, 7, {(1, 1): 2}),
            ("case 4", (2, 1), 16, 15, {(2, 1): 3}),
            ("case 5", (-1, -1), 8, 7, {(-1, -1): 2}),
            ("lv chg case 1", (0, 0), 4, 3, {(0, 0): 1}),
            ("lv chg case 2", (1, 0), 2, 1, {(1, 0): 0}),
            ("lv chg case 3", (0, 0), 0, 0, {}),
            ("lv chg case 4", (1, 0), 0, 0, {(0, 0): 0}),
        ]
        for (
            case_name,
            block_pos,
            sep_num,
            start_num,
            block_path_map,
        ) in test_cases:
            with self.subTest(
                case_name=case_name,
                block_pos=block_pos,
                sep_num=sep_num,
                start_num=start_num,
                block_path_map=block_path_map,
            ):
                map_genetator = AreaBlockAlgorithmGenerator()
                map_genetator.area_block_lv_map = block_path_map
                result_count = {elm: {} for elm in ["enemy", "spawner", "resource"]}
                for x, y in [(x, y) for x in range(s) for y in range(s)]:
                    area_pos = tuple(p + b * s for p, b in zip((x, y), block_pos))
                    for elm, num in (
                        ("enemy", map_genetator.get_enemy_power(*area_pos)),
                        ("spawner", map_genetator.get_spawner_power(*area_pos)),
                        ("resource", map_genetator.get_material_num(*area_pos)),
                    ):
                        result_count[elm][num] = result_count[elm].get(num, 0) + 1
                half_div_map = self._count_group_num_map(
                    s**2, 0.5 if sep_num != 0 else 1, sep_num, 1, start_num
                )
                # スポナーは経路上の各ブロックに1エリアだけ存在し、値は
                # are_level_map[2 % sep_num] = 2 // 2 + start_num
                # （lv0: 2、lv1: 4、lv2: 8、lv3: 16）で決まる
                # （block_path_map に block_pos の記載が無ければ0件）
                spawner_value = 2 // 2 + start_num
                spawner_count_map = (
                    {0: s**2 - 1, spawner_value: 1}
                    if block_path_map.get(block_pos) is not None
                    else {0: s**2}
                )
                # 資源はブロック（distance(lv)）ごとに Tree の数 + Rock の数のエリアに
                # 配置され、採取量はブロックごとの値（サイクル 023-3）になる。
                # 経路上の各ブロックはスポナーのエリアにも資材（そのブロックの開放に
                # 必要な資材・1個。ID-027 U1〜U3）が設定されるため、値1が別枠で +1 エリア
                # になる（block_path_map に block_pos の記載が無ければ0件）。lv 1〜3 は
                # 作業台のエリアにも加工後の資材（Plank/Brick/Hammer・1個。U1）が設定される
                # ため、同じく値1が別枠で +1 エリアになる（サイクル024-2・025-3）
                lv = block_path_map.get(block_pos)
                if lv is None:
                    resource_count_map = {0: s**2}
                else:
                    resource_num = (
                        self.REQUIRED_TREE_NUM[lv] + self.REQUIRED_ROCK_NUM[lv]
                    )
                    material_num = self.REQUIRED_MATERIAL_NUM[lv]
                    spawner_num = 1
                    workbench_num = 1 if lv in (1, 2, 3) else 0
                    resource_count_map = {
                        0: s**2 - resource_num - spawner_num - workbench_num,
                        material_num: resource_num,
                    }
                    if spawner_num:
                        resource_count_map[1] = (
                            resource_count_map.get(1, 0) + spawner_num
                        )
                    if workbench_num:
                        resource_count_map[1] = (
                            resource_count_map.get(1, 0) + workbench_num
                        )
                for elm, expect_map in (
                    ("enemy", half_div_map),
                    ("spawner", spawner_count_map),
                    ("resource", resource_count_map),
                ):
                    for num, count in expect_map.items():
                        if count == 0:
                            self.assertEqual(True, num not in result_count[elm], elm)
                        else:
                            self.assertEqual(count, result_count[elm][num], elm)

    @patch("src.map_generator.AreaBlockAlgorithmGenerator._get_area_num_list")
    def test_dont_repeat(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        map_genetator = AreaBlockAlgorithmGenerator()
        mock.return_value = [
            AreaParam(
                fee_num=x,
                enemy_power=y,
                spawner_power=1 if (x, y) == (1, 1) else 0,
                material_num=1 if (x, y) == (2, 2) else 0,
            )
            for x in range(s)
            for y in range(s)
        ]
        repeat_flg = True
        for x, y in [(x, y) for x in range(s) for y in range(s)]:
            if (
                x != map_genetator.get_fee_num(x, y)
                or y != map_genetator.get_enemy_power(x, y)
                or (1 if (x, y) == (1, 1) else 0)
                != map_genetator.get_spawner_power(x, y)
                or (1 if (x, y) == (2, 2) else 0)
                != map_genetator.get_material_num(x, y)
            ):
                repeat_flg = False
        self.assertEqual(False, repeat_flg)

    def test_special_area_not_adjacent(self):
        """同一ブロック内で、スポナー・資源・作業台を持つエリアの合計が
        要件どおりの件数で 10 以下であり、どの2つも隣接しない

        全ブロック（distance 0〜4）について、特殊エリアの件数が requirements.md の
        配置数から導かれる値（lv0: スポナー1+Tree2+Rock2=5、lv1・lv2・lv3: スポナー1+
        Tree3+Rock3+作業台1=8、lv4: スポナー1+Tree4+Rock4=9）と
        一致し、10 以下であることを
        確認する。生成を繰り返しても隣接（上下左右の距離1）が発生せず、`_shuffle` が
        例外なく配置を完了することを確認する（一様なシャッフルでは偶然 green になり
        得るため、繰り返し回数を十分に取る）。

        作業台のエリアは U1 により `material_type`（Plank/Brick/Hammer）を持つため、
        `get_material_num` による判定を変えなくても特殊エリアとして数えられる
        （サイクル024-2の時点で成立している特性。サイクル024-3で件数を確認し、
        サイクル025-4でHammerの作業台（lv3）も同じ判定で数えられることを確認する）。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        test_cases = [
            ("lv 0 (5 special areas)", 0, 5),
            ("lv 1 (8 special areas, with workbench)", 1, 8),
            ("lv 2 (8 special areas, with workbench)", 2, 8),
            ("lv 3 (8 special areas, with workbench)", 3, 8),
            ("lv 4 (9 special areas)", 4, 9),
        ]
        for case_name, distance, expected_num in test_cases:
            with self.subTest(case_name=case_name):
                for _ in range(50):
                    map_genetator = AreaBlockAlgorithmGenerator()
                    map_genetator.area_block_lv_map = {(0, 0): distance}
                    special_pos_list = [
                        (x, y)
                        for x in range(s)
                        for y in range(s)
                        if map_genetator.get_spawner_power(x, y) != 0
                        or map_genetator.get_material_num(x, y) != 0
                    ]
                    self.assertEqual(expected_num, len(special_pos_list), case_name)
                    self.assertLessEqual(len(special_pos_list), 10, case_name)
                    for i, (x1, y1) in enumerate(special_pos_list):
                        for x2, y2 in special_pos_list[i + 1 :]:
                            self.assertNotEqual(
                                1,
                                abs(x1 - x2) + abs(y1 - y2),
                                (case_name, (x1, y1), (x2, y2)),
                            )

    def test_start_pos_adjacent_to_tree(self):
        """スタート位置の上下左右のいずれかに必ず Tree（資材の種類が Wood の資源）がある

        Rock（Stone）の隣ではなく、Tree の隣であることを確認する（U3）。ブロック1 には
        Rock も 2 つ入るため（023-1）、資源の判定を Wood に絞らない限り Rock の隣が
        選ばれ得ることを、生成を繰り返しても Tree の隣になることで確認する。スポナーの
        エリアにも資材（ID-027 U1）が設定されるため、資源の判定は spawner_power == 0 を
        あわせて見る。
        """
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        for _ in range(50):
            map_genetator = AreaBlockAlgorithmGenerator()
            start_pos = map_genetator.get_start_pos()
            neighbor_is_tree_list = [
                map_genetator.get_spawner_power(start_pos[0] + dx, start_pos[1] + dy)
                == 0
                and map_genetator.get_material_type(
                    start_pos[0] + dx, start_pos[1] + dy
                )
                == MaterialType.WOOD
                for dx, dy in directions
            ]
            self.assertIn(True, neighbor_is_tree_list)

    def test_get_fee_num_start_adjacent_tree(self):
        """スタートエリアに隣接するエリアのうち Tree のあるエリアの必要量は 1（サイクル 026-5。
        requirements.md §3.3・開発フェーズ3「開始時の資材と序盤の開放」）。

        Rock のあるエリアと資源の無いエリアは、隣接していてもエリアの属するブロックの
        必要量のままである（スタートブロックの隣接では 2。U1 改訂）。スタート位置は
        エリアデータの生成時に決まるため、`get_start_pos` を呼ぶ前の `get_fee_num` も
        同じ値を返す。生成を繰り返して、隣接するエリアの Tree・Rock・資源なしの
        すべてを確認する。
        """
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        seen = set()
        for _ in range(200):
            map_genetator = AreaBlockAlgorithmGenerator()
            fee_num_before = {
                (x, y): map_genetator.get_fee_num(x, y)
                for x in range(s)
                for y in range(s)
            }
            start_pos = map_genetator.get_start_pos()
            tree_neighbor_set = set()
            for pos in self._adjacent_pos_list(start_pos):
                if map_genetator.get_material_type(*pos) is None:
                    kind = "none"
                elif self._is_tree(map_genetator, pos):
                    kind = "tree"
                    tree_neighbor_set.add(pos)
                else:
                    kind = "other"
                fee_num = map_genetator.get_fee_num(*pos)
                if fee_num == 0:
                    continue  # 経路外のブロックは開放対象を置かない
                seen.add(kind)
                if kind == "tree":
                    self.assertEqual(1, fee_num, (start_pos, pos))
                    if pos in fee_num_before:
                        self.assertEqual(1, fee_num_before[pos], (start_pos, pos))
                else:
                    self.assertNotEqual(1, fee_num, (kind, start_pos, pos))
            block_fee_one_set = {
                pos
                for pos, num in fee_num_before.items()
                if 0 <= pos[0] < s and 0 <= pos[1] < s and num == 1
            }
            self.assertEqual(
                {
                    pos
                    for pos in tree_neighbor_set
                    if 0 <= pos[0] < s and 0 <= pos[1] < s
                },
                block_fee_one_set,
                "必要量 1 のエリアはスタート隣接の Tree だけのはず",
            )
        self.assertEqual({"tree", "other", "none"}, seen)

    def test_get_pos(self):
        test_cases = [
            ("start", True, 0),
            ("boss", False, AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN),
        ]
        for case_name, check_start, expected_lv in test_cases:
            with self.subTest(
                case_name=case_name, check_start=check_start, lv=expected_lv
            ):
                map_genetator = AreaBlockAlgorithmGenerator()
                start_pos = map_genetator.get_start_pos()
                boss_pos = map_genetator.get_boss_pos()
                self.assertNotEqual(start_pos, boss_pos)
                check_pos = start_pos if check_start else boss_pos
                self.assertEqual(0, map_genetator.get_spawner_power(*check_pos))
                self.assertEqual(0, map_genetator.get_material_num(*check_pos))
                block_lv = map_genetator.area_block_lv_map[
                    tuple(
                        p // AreaBlockAlgorithmGenerator.BLOCK_SIZE for p in check_pos
                    )
                ]
                self.assertEqual(expected_lv, block_lv)

    def test_get_boss_power(self):
        map_genetator = AreaBlockAlgorithmGenerator()
        expected_lv = 2 ** (AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN + 1 + 1) - 1
        self.assertEqual(expected_lv, map_genetator.get_boss_power())

    # requirements.md フェーズ4「指示の流れ」のブロック1〜4の指示の個数
    # （ボスの撃破を除く。Navigator.STEPS の個数と一致）。実装の定数を参照しない
    STEP_NUMS_PER_BLOCK = (5, 3, 3, 3)
    INITIAL_POWER = 1

    def _gains(self, map_genetator, block_idx):
        count = self.STEP_NUMS_PER_BLOCK[block_idx]
        return [
            map_genetator.get_step_power_gain(block_idx, i, count) for i in range(count)
        ]

    def test_get_step_power_gain_cumulative(self):
        """ブロック k（1〜4）の指示を終えた時点の累計の上昇量は 2 ** (k + 2)
        （8・16・32・64）。ブロック内は個数で割って配り、割り切れない分は最後の
        指示に加える（U1）。"""
        map_genetator = AreaBlockAlgorithmGenerator()
        total = 0
        for block_idx, count in enumerate(self.STEP_NUMS_PER_BLOCK):
            with self.subTest(block=block_idx + 1):
                gains = self._gains(map_genetator, block_idx)
                total += sum(gains)
                self.assertEqual(2 ** (block_idx + 1 + 2), total)
                self.assertEqual([gains[0]] * (count - 1), gains[:-1])
                self.assertGreaterEqual(gains[-1], gains[0])
                self.assertTrue(all(g > 0 for g in gains))

    def test_get_step_power_gain_beats_spawner(self):
        """各ブロックの最後の指示までの累計（初期の強さを含む）が、そのブロックの
        スポナーの強さと次のブロックの通常の敵の最大を超える（U2）。"""
        map_genetator = AreaBlockAlgorithmGenerator()
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        total = self.INITIAL_POWER
        for block_idx in range(len(self.STEP_NUMS_PER_BLOCK)):
            total += sum(self._gains(map_genetator, block_idx))
            with self.subTest(block=block_idx + 1):
                map_genetator.area_block_lv_map = {(0, 0): block_idx}
                areas = [(x, y) for x in range(s) for y in range(s)]
                spawner_power = max(map_genetator.get_spawner_power(*a) for a in areas)
                self.assertGreater(total, spawner_power)
                map_genetator.area_block_lv_map = {(0, 0): block_idx + 1}
                next_enemy_max = max(map_genetator.get_enemy_power(*a) for a in areas)
                self.assertGreater(total, next_enemy_max)

    def test_get_step_power_gain_beats_boss(self):
        """ボスの撃破の直前（14 個目）までの累計 + 初期の強さが、ボスの強さを超える。"""
        map_genetator = AreaBlockAlgorithmGenerator()
        total = self.INITIAL_POWER + sum(
            sum(self._gains(map_genetator, b))
            for b in range(len(self.STEP_NUMS_PER_BLOCK))
        )
        self.assertGreater(total, map_genetator.get_boss_power())

    def test_get_area_block_route(self):  # pylint: disable=too-many-locals
        # main.Direct への依存を避けるため、方向差分をこのテスト内に閉じて持つ
        # (判断: map_generator は main.py に非依存な独立モジュールとして設計されて
        # おり、そのテストが main.py の Direct を import すると U2 未着手のこの
        # 時点で main.py に不要な結合が生まれるため)
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        test_cases = [("path 1", 1), ("path 2", 2), ("path 5", 5), ("path 10", 10)]
        for case_name, path_len in test_cases:
            with self.subTest(case_name=case_name, path_len=path_len):
                route = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                    path_len
                )
                self.assertEqual(0, route[(0, 0)])
                visited = set()
                stack = [(0, 0)]
                visited.add((0, 0))
                step_max = 0

                while stack:
                    x, y = stack.pop()
                    current_step = route[(x, y)]
                    step_max = max(step_max, current_step)
                    for dx, dy in directions:
                        nx, ny = x + dx, y + dy
                        if (nx, ny) in route and (nx, ny) not in visited:
                            if abs(route[(nx, ny)] - current_step) == 1:
                                visited.add((nx, ny))
                                stack.append((nx, ny))
                self.assertEqual(len(visited), len(route))
                self.assertEqual(path_len, step_max)

    def test_dont_repeat_area_block_route(self):
        test_cases = [("path 1", 1), ("path 2", 2), ("path 5", 5), ("path 10", 10)]
        for case_name, path_len in test_cases:
            with self.subTest(case_name=case_name, path_len=path_len):
                different_flg = False
                for _ in range(10):
                    route1 = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                        path_len
                    )
                    route2 = AreaBlockAlgorithmGenerator._get_area_block_route(  # pylint: disable=W0212
                        path_len
                    )
                    if route1 != route2:
                        different_flg = True
                        break
                self.assertEqual(True, different_flg)


class TestGeneratedMapResult(GeneratorTestHelper, unittest.TestCase):
    """生成結果（スタート位置・ボス位置・エリアの値）が生成器ごとに固定され、
    再作成でのみ新しくなることのテスト（ID-028）。"""

    def _restore_instance_after_test(self):
        """シングルトンはテスト間で持ち越されるため、テスト後に元の生成器へ戻す"""
        instance_patch = patch.object(
            AreaBlockAlgorithmGenerator,
            "_instance",
            AreaBlockAlgorithmGenerator.create(),
        )
        instance_patch.start()
        self.addCleanup(instance_patch.stop)

    @patch("src.map_generator.AreaBlockAlgorithmGenerator._get_area_num_list")
    def test_get_same_result(self, mock):
        s = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        mock.return_value = [
            AreaParam(
                fee_num=x,
                enemy_power=y,
                spawner_power=1 if (x, y) == (1, 1) else 0,
                material_num=1 if (x, y) == (2, 2) else 0,
            )
            for x in range(s)
            for y in range(s)
        ]
        result = []
        for _ in range(2):
            map_genetator = AreaBlockAlgorithmGenerator.create()
            sub_result = []
            for x, y in [(x, y) for x in range(s) for y in range(s)]:
                sub_result.append(
                    (
                        map_genetator.get_fee_num(x, y),
                        map_genetator.get_enemy_power(x, y),
                        map_genetator.get_spawner_power(x, y),
                        map_genetator.get_material_num(x, y),
                    )
                )
            result.append(sub_result)
        self.assertEqual(result[0], result[1])

    def test_recreate(self):
        # シングルトンはテスト間で持ち越されるため、実体の生成器を残さない
        self._restore_instance_after_test()
        before = AreaBlockAlgorithmGenerator.create()
        AreaBlockAlgorithmGenerator.recreate()
        after = AreaBlockAlgorithmGenerator.create()
        self.assertIsNot(before, after)
        self.assertIs(after, AreaBlockAlgorithmGenerator.create())

    def test_recreate_keeps_start_conditions(self):
        """再生成した新しいマップでも、スタート位置は Tree に隣接し、その Tree の
        エリアの必要量は 1、ボス位置はスタート位置と異なる（サイクル 028-4）。
        """
        self._restore_instance_after_test()
        for _ in range(50):
            AreaBlockAlgorithmGenerator.recreate()
            map_genetator = AreaBlockAlgorithmGenerator.create()
            start_pos = map_genetator.get_start_pos()
            tree_neighbor_list = [
                pos
                for pos in self._adjacent_pos_list(start_pos)
                if self._is_tree(map_genetator, pos)
            ]
            self.assertNotEqual([], tree_neighbor_list, start_pos)
            for pos in tree_neighbor_list:
                self.assertEqual(1, map_genetator.get_fee_num(*pos), (start_pos, pos))
            self.assertNotEqual(start_pos, map_genetator.get_boss_pos())

    def test_get_start_pos_is_fixed(self):
        """スタート位置は生成時に決まるため、`get_start_pos` を何度呼んでも同じ位置を返す
        （マップの再生成は別途行う。U1 改訂）。
        """
        for _ in range(30):
            map_genetator = AreaBlockAlgorithmGenerator()
            start_pos = map_genetator.get_start_pos()
            for _ in range(5):
                self.assertEqual(start_pos, map_genetator.get_start_pos())

    def test_get_boss_pos_is_fixed(self):
        """ボス位置はスタート位置と同じく生成結果の一部のため、`get_boss_pos` を
        何度呼んでも同じ位置を返す（マップの再生成は別途行う）。
        """
        for _ in range(30):
            map_genetator = AreaBlockAlgorithmGenerator()
            boss_pos = map_genetator.get_boss_pos()
            for _ in range(5):
                self.assertEqual(boss_pos, map_genetator.get_boss_pos())


class TestFindNearestArea(GeneratorTestHelper, unittest.TestCase):
    """ナビゲーションの目標のエリアを決める問い合わせ（サイクル 029-2。U5・U6）。

    期待値は、公開の getter（`get_material_type`・`get_spawner_power`・`get_workbench`）と
    `area_block_lv_map` から求める。ブロックのレベルはブロックの経路上の位置（0〜4）で、
    requirements.md のブロック1〜5 に対応する（ブロック1 = レベル 0）。
    """

    BLOCK_SIZE = AreaBlockAlgorithmGenerator.BLOCK_SIZE

    @classmethod
    def _block_pos_list(cls, generator, lv):
        """レベル lv のブロックに属するエリア座標の一覧"""
        return [
            (bx * cls.BLOCK_SIZE + dx, by * cls.BLOCK_SIZE + dy)
            for (bx, by), block_lv in generator.area_block_lv_map.items()
            if block_lv == lv
            for dx in range(cls.BLOCK_SIZE)
            for dy in range(cls.BLOCK_SIZE)
        ]

    @classmethod
    def _candidate_list(cls, generator, lv, kind):
        """目標の種別 kind に該当するエリアの一覧（公開の getter だけで判定する）"""
        pos_list = cls._block_pos_list(generator, lv)
        if kind == AreaKind.TREE:
            return [p for p in pos_list if cls._is_tree(generator, p)]
        if kind == AreaKind.ROCK:
            return [
                p
                for p in pos_list
                if generator.get_material_type(*p) == MaterialType.STONE
                and generator.get_spawner_power(*p) == 0
            ]
        if kind == AreaKind.WORKBENCH:
            return [p for p in pos_list if generator.get_workbench(*p) is not None]
        # NEXT_BLOCK: 次のブロック（lv + 1）のうち、現在のブロックと辺で接するエリア
        current_set = set(pos_list)
        return [
            p
            for p in cls._block_pos_list(generator, lv + 1)
            if any(adj in current_set for adj in cls._adjacent_pos_list(p))
        ]

    @staticmethod
    def _nearest(candidate_list, base_pos):
        """マンハッタン距離が最小のエリア。同距離は座標の順"""
        return min(
            candidate_list,
            key=lambda p: (abs(p[0] - base_pos[0]) + abs(p[1] - base_pos[1]), p),
        )

    def test_find_nearest_area(self):
        """目標の種別ごとに、該当エリアのうち基準位置に最も近いものが得られる。

        基準位置は、現在のブロックの全エリアで確認する。Tree・Rock はブロック1（レベル 0）、
        作業台はブロック2〜4（レベル 1〜3）、次のブロックのエリアはレベル 0〜3 の
        ブロックから次のブロックへ。
        """
        generator = AreaBlockAlgorithmGenerator()
        test_cases = [
            (AreaKind.TREE, [0]),
            (AreaKind.ROCK, [0]),
            (AreaKind.WORKBENCH, [1, 2, 3]),
            (AreaKind.NEXT_BLOCK, [0, 1, 2, 3]),
        ]
        for kind, lv_list in test_cases:
            for lv in lv_list:
                candidate_list = self._candidate_list(generator, lv, kind)
                self.assertNotEqual([], candidate_list, (kind, lv))
                for base_pos in self._block_pos_list(generator, lv):
                    with self.subTest(kind=kind, lv=lv, base_pos=base_pos):
                        self.assertEqual(
                            self._nearest(candidate_list, base_pos),
                            generator.find_nearest_area(lv, kind, base_pos),
                        )

    def test_find_nearest_tree_from_start_pos_is_adjacent(self):
        """スタート位置を基準にした Tree は、スタートに隣接する Tree になる（U6）。

        スタート位置は Tree に隣接する（距離 1）ため、距離 1 より近い Tree は無く、
        最寄りの Tree は必ず隣接する。
        """
        for _ in range(30):
            generator = AreaBlockAlgorithmGenerator()
            start_pos = generator.get_start_pos()
            tree_pos = generator.find_nearest_area(0, AreaKind.TREE, start_pos)
            self.assertTrue(self._is_tree(generator, tree_pos), tree_pos)
            self.assertIn(tree_pos, self._adjacent_pos_list(start_pos))

    def test_is_area_kind(self):
        """エリアが、レベル lv のブロックの種別 kind に該当するかが得られる。
        Tree・Rock・作業台はそのブロックの該当エリア、次のブロックのエリアは次のブロック
        （lv + 1）のいずれかのエリア。経路上の全エリアと経路外のエリアで確認する"""
        generator = AreaBlockAlgorithmGenerator()
        route_pos_list = [
            pos
            for lv in range(AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN + 1)
            for pos in self._block_pos_list(generator, lv)
        ] + [(100, 100)]
        test_cases = [
            (AreaKind.TREE, [0, 1, 2]),
            (AreaKind.ROCK, [0, 1, 2]),
            (AreaKind.WORKBENCH, [1, 2, 3]),
            (AreaKind.NEXT_BLOCK, [0, 1, 2, 3]),
        ]
        for kind, lv_list in test_cases:
            for lv in lv_list:
                if kind == AreaKind.NEXT_BLOCK:
                    expected_set = set(self._block_pos_list(generator, lv + 1))
                else:
                    expected_set = set(self._candidate_list(generator, lv, kind))
                self.assertNotEqual(set(), expected_set, (kind, lv))
                for pos in route_pos_list:
                    with self.subTest(kind=kind, lv=lv, pos=pos):
                        self.assertEqual(
                            pos in expected_set,
                            generator.is_area_kind(lv, kind, pos),
                        )

    def test_get_block_lv(self):
        """座標が属するブロックのレベルが得られる。経路に無いブロックは None"""
        generator = AreaBlockAlgorithmGenerator()
        for lv in range(AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN + 1):
            for pos in self._block_pos_list(generator, lv):
                self.assertEqual(lv, generator.get_block_lv(*pos), pos)
        outside_pos = (100, 100)
        self.assertNotIn(
            (100 // self.BLOCK_SIZE, 100 // self.BLOCK_SIZE),
            generator.area_block_lv_map,
        )
        self.assertIsNone(generator.get_block_lv(*outside_pos))


if __name__ == "__main__":
    unittest.main()


class TestMapGeneratorSaveData(GeneratorTestHelper, unittest.TestCase):
    """生成結果の保存データへの変換と復元のテスト（ID-033 サイクル 033-2。D1・U1）。

    保存データは生成結果そのものを持ち（乱数の種からの再生成はしない）、JSON で往復できる。
    保存時点で未生成のブロックは、復元後に初めて問い合わせたときに生成する。
    """

    def setUp(self):
        instance_patch = patch.object(
            AreaBlockAlgorithmGenerator,
            "_instance",
            AreaBlockAlgorithmGenerator.create(),
        )
        instance_patch.start()
        self.addCleanup(instance_patch.stop)

    @staticmethod
    def _block_pos_list(generator, block_lv):
        """レベル block_lv のブロックのエリア座標（公開の問い合わせだけで探す）"""
        size = AreaBlockAlgorithmGenerator.BLOCK_SIZE
        return [
            (x, y)
            for x in range(-5 * size, 5 * size)
            for y in range(-5 * size, 5 * size)
            if generator.get_block_lv(x, y) == block_lv
        ]

    @staticmethod
    def _area_answer(generator, pos):
        return (
            generator.get_fee_num(*pos),
            generator.get_enemy_power(*pos),
            generator.get_spawner_power(*pos),
            generator.get_material_num(*pos),
            generator.get_material_type(*pos),
            generator.get_fee_type(*pos),
            generator.get_workbench(*pos),
        )

    def _query_generated_blocks(self, generator):
        """ブロックのレベル 0・1・4 だけを生成する問い合わせをして、答えを返す。
        レベル 2・3 のブロックは未生成のまま残る"""
        start_pos = generator.get_start_pos()
        boss_pos = generator.get_boss_pos()  # レベル 4 のブロックを生成する
        nearest = {
            (lv, kind): generator.find_nearest_area(lv, kind, start_pos)
            for lv, kind in [
                (0, AreaKind.TREE),
                (0, AreaKind.ROCK),
                (0, AreaKind.NEXT_BLOCK),  # レベル 1 のブロックを生成する
                (1, AreaKind.TREE),
                (1, AreaKind.ROCK),
                (1, AreaKind.WORKBENCH),
            ]
        }
        area_answers = {
            pos: self._area_answer(generator, pos)
            for lv in (0, 1, 4)
            for pos in self._block_pos_list(generator, lv)
        }
        return start_pos, boss_pos, nearest, area_answers

    def _restore_via_json(self, generator):
        return AreaBlockAlgorithmGenerator.restore(
            json.loads(json.dumps(generator.to_save_data()))
        )

    def test_restore_gives_same_answers(self):
        """保存データを JSON で往復して復元すると、生成済みのブロックの問い合わせ
        （エリアの値・スタート位置・ボス位置・最も近いエリア）が保存前と同じ答えを返し、
        ブロックのレベルの経路も同じになる"""
        for _ in range(20):
            generator = AreaBlockAlgorithmGenerator.recreate()
            expected = self._query_generated_blocks(generator)
            lv_answers = {lv: self._block_pos_list(generator, lv) for lv in range(5)}

            restored = self._restore_via_json(generator)

            self.assertEqual(expected, self._query_generated_blocks(restored))
            self.assertEqual(
                lv_answers,
                {lv: self._block_pos_list(restored, lv) for lv in range(5)},
            )

    def test_restore_replaces_singleton(self):
        """復元した生成器が、以後の create() の返す生成器（シングルトン）になる"""
        generator = AreaBlockAlgorithmGenerator.recreate()
        generator.get_start_pos()
        restored = self._restore_via_json(generator)
        self.assertIsNot(generator, restored)
        self.assertIs(restored, AreaBlockAlgorithmGenerator.create())

    def test_ungenerated_block_is_generated_after_restore(self):
        """保存時点で未生成のブロック（レベル 2）は、復元後に初めて問い合わせたときに
        生成され、以後は同じ答えを返す。生成されたブロックはスポナーをちょうど 1 つ持つ"""
        for _ in range(10):
            generator = AreaBlockAlgorithmGenerator.recreate()
            self._query_generated_blocks(generator)
            restored = self._restore_via_json(generator)

            pos_list = self._block_pos_list(restored, 2)
            first = [self._area_answer(restored, pos) for pos in pos_list]
            second = [self._area_answer(restored, pos) for pos in pos_list]

            self.assertEqual(first, second)
            self.assertEqual(1, sum(1 for answer in first if answer[2] != 0))
