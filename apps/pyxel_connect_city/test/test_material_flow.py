import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from edge import EdgeDirect, EdgeManager  # pylint: disable=C0413
from material_flow import MaterialFlow  # pylint: disable=C0413
from node import NodeType, MaterialType, NodeManager  # pylint: disable=C0413


class TestMaterialFlowPureProduction(unittest.TestCase):
    def test_node_produces_material_per_tick(self):
        """1ティックでノードが資材を生産蓄積へ加算する（純粋生産ノード以外は変化なし）"""
        cases = [
            # (説明, ノード種別, 期待生産蓄積, 期待消化蓄積, 期待成長蓄積, 加算回数)
            (
                "森が TREE を 1 ティック生産する（rate=3）",
                NodeType.FOREST,
                {MaterialType.TREE: 3},
                {},
                {},
                1,
            ),
            (
                "山が STONE を 1 ティック生産する（rate=3）",
                NodeType.MOUNTAIN,
                {MaterialType.STONE: 3},
                {},
                {},
                1,
            ),
            (
                "CITY は純粋生産しない（Lv0 growth_stock キーは TREE のみ）",
                NodeType.CITY,
                {},
                {},
                {MaterialType.TREE: 0},
                1,
            ),
            (
                "森が TREE を生産し、上限 3 に達する（rate=3 × 2 ticks → cap 3）",
                NodeType.FOREST,
                {MaterialType.TREE: 3},
                {},
                {},
                2,
            ),
        ]
        for desc, node_type, exp_prod, exp_cons, exp_growth, times in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(
                    [
                        {
                            "col": 0,
                            "row": 0,
                            "type": node_type.value,
                            "production_stock": {},
                            "consumption_stock": {},
                            "growth_stock": {},
                        }
                    ]
                )
                flow = MaterialFlow()
                for _ in range(times):
                    flow.process(node_manager, EdgeManager.from_list([]))
                node = node_manager.get_node(0, 0)
                self.assertEqual(
                    exp_prod, node._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_cons, node._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_growth, node._growth_stock  # pylint: disable=W0212
                )


class TestMaterialFlowTransfer(unittest.TestCase):
    def test_transfer_single_destination(self):
        """単一接続先への転送（全 stock を確認）"""
        cases = [
            (
                "森 → 工場：TREE を消化蓄積へ（合計需要3 ≤ 蓄積3 → 必要量分配）",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                # source (FOREST): 純粋生産で TREE=3、全量転送 → 0
                ({MaterialType.TREE: 0}, {}, {}),
                # dest (FACTORY Lv0): 転送で消化蓄積 TREE=3 充足 → _produce_conditional で WOOD+3・TREE-3
                # 工場 Lv0 は growth_limits={STONE:15} を持つため growth_stock は {STONE: 0}
                (
                    {MaterialType.WOOD: 3},
                    {MaterialType.TREE: 0},
                    {MaterialType.STONE: 0},
                ),
            ),
            (
                "森 → 街：TREE を成長蓄積へ（合計需要15 > 蓄積3 → 均等割り share=3）",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                # source (FOREST): 純粋生産で TREE=3、全量転送 → 0
                ({MaterialType.TREE: 0}, {}, {}),
                # dest (CITY): 需要15 > 蓄積3 → share=3//1=3、成長蓄積 TREE に 3 加算
                ({}, {}, {MaterialType.TREE: 3}),
            ),
            (
                "山(STONE=2) → 工場Lv1: 純粋生産が上限3にクリップ、全量転送 → STONE_BLOCK 生産",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "MOUNTAIN",
                        "production_stock": {"STONE": 2},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {},
                        "consumption_stock": {"STONE": 0},
                        "growth_stock": {"WOOD": 0},
                        "level": 1,
                    },
                ],
                # source (MOUNTAIN): 純粋生産で min(2+3, 3) = 3、全量転送 → 0
                ({MaterialType.STONE: 0}, {}, {}),
                # dest (FACTORY Lv1): 消化蓄積 STONE=3 充足 → _produce_conditional で STONE_BLOCK+3・STONE-3
                (
                    {MaterialType.STONE_BLOCK: 3},
                    {MaterialType.STONE: 0},
                    {MaterialType.WOOD: 0},
                ),
            ),
        ]
        for (
            desc,
            nodes,
            (exp_src_prod, exp_src_cons, exp_src_growth),
            (exp_dst_prod, exp_dst_cons, exp_dst_growth),
        ) in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(nodes)
                edge_manager = EdgeManager.from_list(
                    [{"start": [0, 0], "end": [1, 0], "direct": None}]
                )
                flow = MaterialFlow()
                flow.process(node_manager, edge_manager)
                source = node_manager.get_node(0, 0)
                dest = node_manager.get_node(1, 0)
                self.assertEqual(
                    exp_src_prod, source._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_cons, source._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_growth, source._growth_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_prod, dest._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_cons, dest._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_growth, dest._growth_stock  # pylint: disable=W0212
                )

    def test_transfer_multi_destination(self):
        """複数接続先への転送（全 stock 確認）"""
        cases = [
            (
                "1森 → 2工場：合計需要(6) > 蓄積(3) → 均等割り share=1、森は 0",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 2,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                [
                    {"start": [0, 0], "end": [1, 0], "direct": None},
                    {"start": [0, 0], "end": [2, 0], "direct": None},
                ],
                # source (FOREST): 純粋生産で TREE=3、share=3//2=1×2=2 を全量転送 → 0
                ({MaterialType.TREE: 0}, {}, {}),
                # dests (FACTORY Lv0 × 2): 消化蓄積に share=1 ずつ → 消化未満(3)で _produce_conditional は走らず WOOD=0
                # 工場 Lv0 の growth_stock は {STONE: 0}
                [
                    (
                        {MaterialType.WOOD: 0},
                        {MaterialType.TREE: 1},
                        {MaterialType.STONE: 0},
                    ),
                    (
                        {MaterialType.WOOD: 0},
                        {MaterialType.TREE: 1},
                        {MaterialType.STONE: 0},
                    ),
                ],
            ),
            (
                "1森 → 3街：合計需要(45) > 蓄積(3) → 均等割り share=1、森は 0",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 2,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 3,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                [
                    {"start": [0, 0], "end": [1, 0], "direct": None},
                    {"start": [0, 0], "end": [2, 0], "direct": None},
                    {"start": [0, 0], "end": [3, 0], "direct": None},
                ],
                # source (FOREST): 純粋生産で TREE=3、share=3//3=1×3=3 を全量転送 → 0
                ({MaterialType.TREE: 0}, {}, {}),
                # dests (CITY × 3): 成長蓄積に share=3//3=1 ずつ加算
                [
                    ({}, {}, {MaterialType.TREE: 1}),
                    ({}, {}, {MaterialType.TREE: 1}),
                    ({}, {}, {MaterialType.TREE: 1}),
                ],
            ),
        ]
        for (
            desc,
            nodes,
            edges,
            (exp_src_prod, exp_src_cons, exp_src_growth),
            dest_expectations,
        ) in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(nodes)
                edge_manager = EdgeManager.from_list(edges)
                flow = MaterialFlow()
                flow.process(node_manager, edge_manager)
                source = node_manager.get_node(0, 0)
                self.assertEqual(
                    exp_src_prod, source._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_cons, source._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_growth, source._growth_stock  # pylint: disable=W0212
                )
                for i, (exp_prod, exp_cons, exp_growth) in enumerate(
                    dest_expectations, start=1
                ):
                    dest = node_manager.get_node(i, 0)
                    self.assertEqual(
                        exp_prod, dest._production_stock  # pylint: disable=W0212
                    )
                    self.assertEqual(
                        exp_cons, dest._consumption_stock  # pylint: disable=W0212
                    )
                    self.assertEqual(
                        exp_growth, dest._growth_stock  # pylint: disable=W0212
                    )

    def test_no_transfer_when_dest_cannot_receive(self):
        """受け入れ不可な dest への非転送（種別不一致・上限到達の2系統）"""
        cases = [
            (
                "種別不一致：山 → 街 Lv0（STONE 非対応、Lv0 は TREE のみ）",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "MOUNTAIN",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                [{"start": [0, 0], "end": [1, 0], "direct": None}],
                # 山: 純粋生産後 STONE=3、転送なし → 3 のまま
                ({MaterialType.STONE: 3}, {}, {}),
                # 街 Lv0: 転送なし → TREE 変化なし
                ({}, {}, {MaterialType.TREE: 0}),
            ),
            (
                "上限到達（消化蓄積）：森 → 工場（consumption_stock[TREE]=3 で満タン）",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {
                            "TREE": 3
                        },  # 上限到達（consumption_rates[TREE]=3）
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                [{"start": [0, 0], "end": [1, 0], "direct": None}],
                # 森: 純粋生産後 TREE=3、転送なし（工場が満タン）→ 3 のまま
                ({MaterialType.TREE: 3}, {}, {}),
                # 工場 Lv0: 転送なし、既存 TREE=3 充足 → _produce_conditional で WOOD+3・TREE-3
                # 工場 Lv0 の growth_stock は {STONE: 0}
                (
                    {MaterialType.WOOD: 3},
                    {MaterialType.TREE: 0},
                    {MaterialType.STONE: 0},
                ),
            ),
            (
                "上限到達（成長蓄積）：森 → 街（growth_stock[TREE]=15 で満タン）",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "CITY",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {
                            "TREE": 15,
                        },  # TREE 上限到達（growth_limits[TREE]=15）
                        "level": 0,
                    },
                ],
                [{"start": [0, 0], "end": [1, 0], "direct": None}],
                # 森: 純粋生産後 TREE=3（上限）、転送なし → 3 のまま
                ({MaterialType.TREE: 3}, {}, {}),
                # 街: 転送なし → TREE 変化なし。is_growth_complete=True で level_up が走り、Lv1 の WOOD growth_stock にリセット
                ({}, {}, {MaterialType.WOOD: 0}),
            ),
        ]
        for (
            desc,
            nodes,
            edges,
            (exp_src_prod, exp_src_cons, exp_src_growth),
            (exp_dst_prod, exp_dst_cons, exp_dst_growth),
        ) in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(nodes)
                edge_manager = EdgeManager.from_list(edges)
                flow = MaterialFlow()
                flow.process(node_manager, edge_manager)
                source = node_manager.get_node(0, 0)
                dest = node_manager.get_node(1, 0)
                self.assertEqual(
                    exp_src_prod, source._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_cons, source._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_src_growth, source._growth_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_prod, dest._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_cons, dest._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_dst_growth, dest._growth_stock  # pylint: disable=W0212
                )

    def test_no_transfer_to_saturated_dest_in_mixed_case(self):
        """混在ケース：上限到達の dest は share カウントから除外される"""
        # 森 → [工場A(TREE消化満タン=3), 工場B(TREE消化空=0)]
        # 純粋生産後の森の蓄積 = 3
        # 工場A は consumption_stock 上限到達で受け入れ不可 → dest は工場B のみ
        # 工場B の需要 = 3 → 必要量(3) ≤ 蓄積(3) → 工場B に 3 転送、森は 0
        node_manager = NodeManager.from_list(
            [
                {
                    "col": 0,
                    "row": 0,
                    "type": "FOREST",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 1,
                    "row": 0,
                    "type": "FACTORY",
                    "production_stock": {"WOOD": 0},
                    "consumption_stock": {"TREE": 3},  # TREE 上限到達
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 2,
                    "row": 0,
                    "type": "FACTORY",
                    "production_stock": {"WOOD": 0},
                    "consumption_stock": {"TREE": 0},  # TREE 空き
                    "growth_stock": {},
                    "level": 0,
                },
            ]
        )
        edge_manager = EdgeManager.from_list(
            [
                {"start": [0, 0], "end": [1, 0], "direct": None},
                {"start": [0, 0], "end": [2, 0], "direct": None},
            ]
        )
        flow = MaterialFlow()
        flow.process(node_manager, edge_manager)
        forest = node_manager.get_node(0, 0)
        factory_a = node_manager.get_node(1, 0)
        factory_b = node_manager.get_node(2, 0)
        # 森: 全量転送 → 0
        self.assertEqual(
            0, forest._production_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        # 工場A: 上限到達のまま（受け入れ不可）→ 既存 TREE=3 充足 → _produce_conditional で WOOD+3・TREE-3
        self.assertEqual(
            0, factory_a._consumption_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        self.assertEqual(
            3, factory_a._production_stock[MaterialType.WOOD]  # pylint: disable=W0212
        )
        # 工場B: 必要量(3) を受け取り → 充足 → _produce_conditional で WOOD+3・TREE-3
        self.assertEqual(
            0, factory_b._consumption_stock[MaterialType.TREE]  # pylint: disable=W0212
        )
        self.assertEqual(
            3, factory_b._production_stock[MaterialType.WOOD]  # pylint: disable=W0212
        )

    def test_no_transfer_when_no_edge(self):
        """エッジが無い場合は転送なし（純粋生産のみ反映）"""
        node_manager = NodeManager.from_list(
            [
                {
                    "col": 0,
                    "row": 0,
                    "type": "FOREST",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 1,
                    "row": 0,
                    "type": "FACTORY",
                    "production_stock": {"WOOD": 0},
                    "consumption_stock": {"TREE": 0},
                    "growth_stock": {},
                    "level": 0,
                },
            ]
        )
        edge_manager = EdgeManager.from_list([])
        flow = MaterialFlow()
        flow.process(node_manager, edge_manager)
        # 森: 純粋生産で TREE=3、転送なし
        self.assertEqual(
            3,
            node_manager.get_node(0, 0)._production_stock[  # pylint: disable=W0212
                MaterialType.TREE
            ],
        )
        # 工場: 転送なし → 消化蓄積 0 のまま
        self.assertEqual(
            0,
            node_manager.get_node(1, 0)._consumption_stock[  # pylint: disable=W0212
                MaterialType.TREE
            ],
        )


class TestMaterialFlowLevelUpCities(unittest.TestCase):
    def test_city_level_up_by_growth_stock(self):
        """成長蓄積の状態に応じたレベルアップと全蓄積の変化を確認する"""
        cases = [
            # (説明, 初期growth_stock, 期待level, 期待production_stock, 期待consumption_stock, 期待growth_stock)
            (
                "TREE未達（10/15）→ レベル変化なし、全蓄積そのまま",
                {"TREE": 10},
                0,
                {},
                {},
                {MaterialType.TREE: 10},
            ),
            (
                "全上限到達（TREE=15）→ lv1、Lv1 の growth_stock_cols (WOOD) のみにリセット",
                {"TREE": 15},
                1,
                {},
                {},
                {MaterialType.WOOD: 0},
            ),
        ]
        for desc, init_growth, exp_level, exp_prod, exp_cons, exp_growth in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(
                    [
                        {
                            "col": 0,
                            "row": 0,
                            "type": "CITY",
                            "production_stock": {},
                            "consumption_stock": {},
                            "growth_stock": init_growth,
                            "level": 0,
                        }
                    ]
                )
                flow = MaterialFlow()
                flow.process(node_manager, EdgeManager.from_list([]))
                city = node_manager.get_node(0, 0)
                self.assertEqual(exp_level, city.level)
                self.assertEqual(
                    exp_prod, city._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_cons, city._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_growth, city._growth_stock  # pylint: disable=W0212
                )

    def test_non_city_nodes_unaffected_by_loop_d(self):
        """森・山・工場ノードは process() 後にレベル変化がないこと"""
        node_manager = NodeManager.from_list(
            [
                {
                    "col": 0,
                    "row": 0,
                    "type": "FOREST",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 1,
                    "row": 0,
                    "type": "MOUNTAIN",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 2,
                    "row": 0,
                    "type": "FACTORY",
                    "production_stock": {"WOOD": 0},
                    "consumption_stock": {"TREE": 0},
                    "growth_stock": {},
                    "level": 0,
                },
            ]
        )
        flow = MaterialFlow()
        flow.process(node_manager, EdgeManager.from_list([]))
        self.assertEqual(0, node_manager.get_node(0, 0).level)
        self.assertEqual(0, node_manager.get_node(1, 0).level)
        self.assertEqual(0, node_manager.get_node(2, 0).level)


class TestMaterialFlowEdgeDirect(unittest.TestCase):
    def test_edge_direct_after_transfer(self):
        """process() 後の edge.direct が転送方向に応じて正しく設定されること"""
        cases = [
            (
                "FOREST(start)→FACTORY(end): start→end 転送 → FORWARD",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                EdgeDirect.FORWARD,
            ),
            (
                "FACTORY(start)←FOREST(end): end→start 転送 → BACKWARD",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 0},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {"TREE": 0},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                EdgeDirect.BACKWARD,
            ),
            (
                "転送なし（FACTORY 消化蓄積満タン）→ None",
                [
                    {
                        "col": 0,
                        "row": 0,
                        "type": "FOREST",
                        "production_stock": {},
                        "consumption_stock": {},
                        "growth_stock": {},
                        "level": 0,
                    },
                    {
                        "col": 1,
                        "row": 0,
                        "type": "FACTORY",
                        "production_stock": {"WOOD": 0},
                        "consumption_stock": {"TREE": 3},
                        "growth_stock": {},
                        "level": 0,
                    },
                ],
                None,
            ),
        ]
        for desc, nodes, expected_direct in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(nodes)
                edge_manager = EdgeManager.from_list(
                    [{"start": [0, 0], "end": [1, 0], "direct": None}]
                )
                MaterialFlow().process(node_manager, edge_manager)
                edge = edge_manager.get_edge((0, 0), (1, 0))
                self.assertEqual(expected_direct, edge.direct)

    def test_mixed_edges_some_with_transfer(self):
        """転送ありと転送なしのエッジが混在する場合の確認"""
        # edge1: FOREST(0,0)→FACTORY(1,0): TREE 転送あり → FORWARD
        # edge2: FACTORY(1,0)→CITY(2,0): _transfer 時点で WOOD=0 のため転送なし → None
        # 注: 工場 Lv0 出力は WOOD だが街 Lv0 は TREE のみ受け入れる。
        #     WOOD=0 のため _can_send=False で転送発生せず direct は None のまま。
        node_manager = NodeManager.from_list(
            [
                {
                    "col": 0,
                    "row": 0,
                    "type": "FOREST",
                    "production_stock": {"TREE": 0},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 1,
                    "row": 0,
                    "type": "FACTORY",
                    "production_stock": {"WOOD": 0},
                    "consumption_stock": {"TREE": 0},
                    "growth_stock": {},
                    "level": 0,
                },
                {
                    "col": 2,
                    "row": 0,
                    "type": "CITY",
                    "production_stock": {},
                    "consumption_stock": {},
                    "growth_stock": {},
                    "level": 0,
                },
            ]
        )
        edge_manager = EdgeManager.from_list(
            [
                {"start": [0, 0], "end": [1, 0], "direct": None},
                {"start": [1, 0], "end": [2, 0], "direct": None},
            ]
        )
        MaterialFlow().process(node_manager, edge_manager)
        edge1 = edge_manager.get_edge((0, 0), (1, 0))
        edge2 = edge_manager.get_edge((1, 0), (2, 0))
        self.assertEqual(EdgeDirect.FORWARD, edge1.direct)
        self.assertIsNone(edge2.direct)


class TestMaterialFlowConditionalProduction(unittest.TestCase):
    def test_factory_conditional_production(self):
        """工場の条件生産：消化蓄積の充足・不足で生産量が変わる"""
        cases = [
            # (説明, 初期production_stock, 初期consumption_stock,
            #  期待production_stock, 期待consumption_stock, 期待growth_stock)
            (
                "消化蓄積充足(TREE=3) → WOOD +3、TREE -3",
                {"WOOD": 0},
                {"TREE": 3},
                {"WOOD": 3},
                {"TREE": 0},
                {MaterialType.STONE: 0},
            ),
            (
                "消化蓄積充足・WOOD=1(途中) → WOOD は cap=3 にクリップ、TREE -3",
                {"WOOD": 1},
                {"TREE": 3},
                {"WOOD": 3},
                {"TREE": 0},
                {MaterialType.STONE: 0},
            ),
            (
                "消化蓄積空(TREE=0) → 生産なし",
                {"WOOD": 0},
                {"TREE": 0},
                {"WOOD": 0},
                {"TREE": 0},
                {MaterialType.STONE: 0},
            ),
            (
                "消化蓄積不足(TREE=2) → 生産なし",
                {"WOOD": 0},
                {"TREE": 2},
                {"WOOD": 0},
                {"TREE": 2},
                {MaterialType.STONE: 0},
            ),
            (
                "生産蓄積上限到達(WOOD=3)・消化蓄積充足 → WOOD 変化なし・TREE -3",
                {"WOOD": 3},
                {"TREE": 3},
                {"WOOD": 3},
                {"TREE": 0},
                {MaterialType.STONE: 0},
            ),
        ]
        for desc, init_prod, init_cons, exp_prod, exp_cons, exp_growth in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(
                    [
                        {
                            "col": 0,
                            "row": 0,
                            "type": "FACTORY",
                            "production_stock": init_prod,
                            "consumption_stock": init_cons,
                            "growth_stock": {},
                            "level": 0,
                        }
                    ]
                )
                edge_manager = EdgeManager.from_list([])
                flow = MaterialFlow()
                flow.process(node_manager, edge_manager)
                node = node_manager.get_node(0, 0)
                self.assertEqual(
                    {MaterialType.WOOD: exp_prod["WOOD"]},
                    node._production_stock,  # pylint: disable=W0212
                )
                self.assertEqual(
                    {MaterialType.TREE: exp_cons["TREE"]},
                    node._consumption_stock,  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_growth, node._growth_stock  # pylint: disable=W0212
                )


class TestMaterialFlowMaintenanceCity(unittest.TestCase):
    """Lv4 維持モードのノードループE 挙動"""

    def test_maintenance_city_process(self):
        """供給・減衰・降格・レベルアップスキップの全ケースを確認する"""
        cases = [
            # (説明, 初期growth, 初期consumption, 期待level, 期待production_stock, 期待consumption_stock, 期待growth_stock)
            (
                "供給=減衰=2 → growth 維持・Lv5 にならない（維持モード）",
                15,
                2,
                4,
                {},
                {MaterialType.PLYWOOD: 0},
                {MaterialType.PLYWOOD: 15},
            ),
            (
                "供給なし → growth が 2 減る",
                15,
                0,
                4,
                {},
                {MaterialType.PLYWOOD: 0},
                {MaterialType.PLYWOOD: 13},
            ),
            (
                "供給 1 < 減衰 2 → growth が 1 減る",
                15,
                1,
                4,
                {},
                {MaterialType.PLYWOOD: 0},
                {MaterialType.PLYWOOD: 14},
            ),
            (
                "growth=1 で供給 2 → 降格なし（1 - 2 + 2 = 1）",
                1,
                2,
                4,
                {},
                {MaterialType.PLYWOOD: 0},
                {MaterialType.PLYWOOD: 1},
            ),
            (
                "growth=2 で供給なし → 降格（Lv3、全蓄積リセット）",
                2,
                0,
                3,
                {},
                {},
                {MaterialType.PLYWOOD: 0},
            ),
        ]
        for (
            desc,
            init_growth,
            init_consumption,
            exp_level,
            exp_prod,
            exp_cons,
            exp_growth,
        ) in cases:
            with self.subTest(desc):
                node_manager = NodeManager.from_list(
                    [
                        {
                            "col": 0,
                            "row": 0,
                            "type": "CITY",
                            "production_stock": {},
                            "consumption_stock": {"PLYWOOD": init_consumption},
                            "growth_stock": {"PLYWOOD": init_growth},
                            "level": 4,
                        }
                    ]
                )
                MaterialFlow().process(node_manager, EdgeManager.from_list([]))
                city = node_manager.get_node(0, 0)
                self.assertEqual(exp_level, city.level)
                self.assertEqual(
                    exp_prod, city._production_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_cons, city._consumption_stock  # pylint: disable=W0212
                )
                self.assertEqual(
                    exp_growth, city._growth_stock  # pylint: disable=W0212
                )
