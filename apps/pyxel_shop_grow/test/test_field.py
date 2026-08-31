import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from field import Field, Owner, Shop  # pylint: disable=C0413,E0401
from random_source import IRandomSource  # pylint: disable=C0413,E0401


class TestRandomSource(IRandomSource):
    """抽選の結果を固定するテスト用の RandomSource（ID-008）。
    与えるのは「選ばせたい区画の座標」そのもので、列挙順の n 番目ではない。
    乱数を呼び出し順（1回目→…）で仕込む形にすると、内部で引く回数や順序が
    変わるたびにテストが壊れ、しかも壊れた理由が仕様の変化なのか順序の変化
    なのか区別できなくなるため、**意味を持つメソッド単位**で結果を固定する。
    受け取った対象と呼ばれた回数を控え、列挙と実行の結び付きが迂回されて
    いないことの確認に使う（呼び出しを控えて後から取り出す形は、test_main.py の
    TestView が get_call_params() で行っているのと同じ）。
    仕込みと記録は**抽選ごとに別々に持つ**。他店建設間隔（10秒）と売上発生間隔
    （3秒）は同じ update() で両方満了し得るため、共有すると控えた並びや回数が
    どちらの抽選のものか区別できなくなる（IRandomSource が抽選ごとにメソッドを
    分けたことで「呼び出し順で数えなくてよくなった」効果を、テスト側でも保つ）。
    抽選を行わないテストでも Field の生成に伴って本実装が使われるが、
    そこでは一度も呼ばれない"""

    def __init__(self):
        self._picked_npc_growth_target = None
        self._npc_growth_received_targets = None
        self._npc_growth_call_count = 0
        self._picked_sales_shop = None
        self._sales_shop_received_targets = None
        self._sales_shop_call_count = 0
        self._picked_sell_shop = None
        self._picked_sell_shop_sequence = None
        self._sell_shop_received_targets = None
        self._sell_shop_call_count = 0

    def pick_npc_growth_target(self, targets):
        self._npc_growth_call_count += 1
        self._npc_growth_received_targets = list(targets)
        return self._picked_npc_growth_target

    def pick_sales_shop(self, targets):
        """売上の抽選（ID-010・ID-012）。選ばれた店舗の売上額を**資金**へ加算する
        振る舞いそのものは、資金が GameCore の持ち物のため test_main.py
        （TestSalesInterval）で確認する。一方、**どの並びが抽選へ渡されるか**は
        盤面から決まる Field の責務（ID-012 の重み付き抽選）のため、受け取った
        並びをここで控えて test_field.py 側で確認する"""
        self._sales_shop_call_count += 1
        self._sales_shop_received_targets = list(targets)
        return self._picked_sales_shop

    def pick_sell_shop(self, targets):
        """売却（ID-016）の抽選。3件目の抽選のため、他の2件（pick_npc_growth_target /
        pick_sales_shop）と同じく専用の受け取り記録を別々に持つ（同一 update() 内
        では起きないが、抽選ごとに分ける既存方針をそのまま踏襲する）。
        売却は不足額を満たすまで**同一フレーム内で繰り返し**呼ばれ得る唯一の
        抽選（サイクル2の sell_shops_for_shortfall()）のため、他の2件には無い
        複数回ぶんの仕込み（_picked_sell_shop_sequence）を先に見る"""
        self._sell_shop_call_count += 1
        self._sell_shop_received_targets = list(targets)
        if self._picked_sell_shop_sequence is not None:
            return self._picked_sell_shop_sequence.pop(0)
        return self._picked_sell_shop

    def set_picked_npc_growth_target(self, picked):
        self._picked_npc_growth_target = picked

    def get_npc_growth_received_targets(self):
        return self._npc_growth_received_targets

    def get_npc_growth_call_count(self):
        return self._npc_growth_call_count

    def set_picked_sales_shop(self, picked):
        self._picked_sales_shop = picked

    def get_sales_shop_received_targets(self):
        return self._sales_shop_received_targets

    def get_sales_shop_call_count(self):
        return self._sales_shop_call_count

    def set_picked_sell_shop(self, picked):
        self._picked_sell_shop = picked

    def set_picked_sell_shop_sequence(self, picks):
        """呼び出し順で異なる区画を返すための仕込み（サイクル2専用）。
        set_picked_sell_shop() が毎回同じ値を返す単一の仕込みなのに対し、
        こちらは呼ばれるたびに先頭から順に払い出す並びを持つ。売却は
        1回の sell_shops_for_shortfall() 呼び出しの中で複数回続けて起き、
        売った店舗はその場でプレイヤー所有でなくなり次の対象から外れるため、
        呼び出しごとに異なる区画を選ばせる必要がある（他の2件の抽選——
        pick_npc_growth_target / pick_sales_shop——は1フレームに高々1回しか
        呼ばれず単一の仕込みで足りるため、専用のメソッドをこちらにだけ足す）"""
        self._picked_sell_shop_sequence = list(picks)

    def get_sell_shop_received_targets(self):
        return self._sell_shop_received_targets

    def get_sell_shop_call_count(self):
        return self._sell_shop_call_count


class TestParent(unittest.TestCase):
    """Field が生成する乱数源を、テスト用の決定的な実装へ差し替える共通の親。
    差し替えは本番実装の create() を patch する形（test_main.py が
    PyxelView.create / PyxelInput.create に対して行っているのと同じ）で、
    生成された実装は self.test_random_source から設定・確認できる。
    抽選を行わないテストも Field() の生成で本番実装に触れてしまうため、
    差し替えは Field を生成するすべてのテストに効かせる（pyxel を巻き込まず、
    test_field.py が pyxel なしで動く状態を保つ）"""

    def setUp(self):
        self.test_random_source = TestRandomSource()
        self.patcher_random_source = patch(
            "field.PyxelRandomSource.create", return_value=self.test_random_source
        )
        self.patcher_random_source.start()

    def tearDown(self):
        self.patcher_random_source.stop()


class TestFieldShop(TestParent):
    def test_new_field_has_no_shop_on_any_plot(self):
        """生成直後の Field はどの区画も空き地であること（左上・中間・右下を代表点として確認）"""
        test_cases = [
            ("top left", 0, 0),
            ("middle", 9, 7),
            ("bottom right", 17, 14),
        ]
        field = Field()
        for case_name, col, row in test_cases:
            with self.subTest(case_name=case_name):
                self.assertIsNone(field.get_owner(col, row))
                self.assertIsNone(field.get_scale(col, row))
                self.assertIsNone(field.get_value(col, row))

    def test_set_shop_only_affects_its_own_plot(self):
        """店舗を設置すると、その区画では所有者・初期の店舗規模・設置費用と等しい
        資産価値（Shop.BUILD_COST。要件 3.11 の増資 0 回の状態）が取得でき、
        他の店舗の区画や未設置の区画には影響しないこと。資産価値が入るのは
        設置そのものの性質であり、所有者（プレイヤー／NPC）にはよらない。
        店舗は地域価格倍率が等倍（1.0）になる列0へ置く（ID-020 案8-A）——
        倍率が資産価値へ効くこと自体は TestFieldAreaValue が押さえるため、
        本テストは倍率の乗らない区画で「設置そのものの性質」に集中する"""
        field = Field()
        field.set_shop(0, 3, Owner.NPC)
        field.set_shop(0, 9, Owner.PLAYER)
        test_cases = [
            ("npc shop", 0, 3, Owner.NPC, Shop.INITIAL_SCALE, Shop.BUILD_COST),
            ("player shop", 0, 9, Owner.PLAYER, Shop.INITIAL_SCALE, Shop.BUILD_COST),
            ("vacant plot", 1, 3, None, None, None),
        ]
        for case_name, col, row, owner, scale, value in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(owner, field.get_owner(col, row))
                self.assertEqual(scale, field.get_scale(col, row))
                self.assertEqual(value, field.get_value(col, row))


class TestFieldCostAndSales(TestParent):
    """区画の費用（建設／増資／買収）・売上額の取得に関する振る舞いテスト。
    いずれも仮の値（ID-006/ID-007/ID-009 で費用の、ID-010 で売上額の算出ロジックへ
    置き換える）だが、区画の状態でどの値が返るかは Field/Shop の責務であり、
    GameCore はこの戻り値をそのまま描画するだけの relay であることの根拠になる。
    店舗はいずれも地域価格倍率が等倍（1.0）になる列0へ置く（ID-020 案8-A）——
    倍率が費用・売上額へ効くことは TestFieldAreaCost / TestFieldAreaSales が
    押さえるため、本クラスは「区画の状態でどの値が返るか」という軸に集中する"""

    def test_get_cost_switches_by_plot_state(self):
        """空き区画は建設費用（Shop.BUILD_COST）、プレイヤー所有店舗は増資費用
        （Shop.INVEST_COST × 2^(規模-1)）、NPC所有店舗は買収費用（資産価値の2倍。
        算出は ID-009）を返すこと。設置直後は規模1のため INVEST_COST × 2^0 =
        INVEST_COST と一致し、NPC所有店舗の資産価値も設置直後は Shop.BUILD_COST と
        等しいため、買収費用は Shop.BUILD_COST × 2 になる（規模に応じて増資費用・
        買収費用が変わることは
        test_get_cost_for_restored_player_shop_follows_shop_scale で確認する）"""
        field = Field()
        field.set_shop(0, 1, Owner.PLAYER)
        field.set_shop(0, 2, Owner.NPC)
        test_cases = [
            ("空き区画", 0, 0, Shop.BUILD_COST),
            ("プレイヤー所有店舗", 0, 1, Shop.INVEST_COST),
            ("NPC所有店舗", 0, 2, Shop.BUILD_COST * 2),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_cost(col, row))

    def test_get_cost_for_restored_player_shop_follows_shop_scale(self):
        """apply_load_data() で保存データから復元したプレイヤー所有店舗は、
        規模に応じた増資費用（Shop.INVEST_COST × 2^(規模-1)）を返すこと。
        Shop.restore() は規模のみを書き換えるため、費用を設置時に確定させ
        持ち回る構造のままだと、復元後も規模1相当の費用が固定されたまま
        返ってしまう（本テストが Shop.restore() 後の追従漏れを直接捉える）。
        NPC所有店舗の費用は資産価値の2倍で決まること（買収費用の算出は ID-009）、
        費用が店舗規模ではなく資産価値そのものから決まること（同じ規模5でも
        資産価値が異なれば費用が変わること）も併せて確認する。
        規模が上限（Shop.SCALE_MAX）のプレイヤー所有店舗は増資できないため、
        その増資費用は**存在しない**（None）ことも確認する（要件 3.6）。
        上限の1つ手前（規模9）では従来どおり数値が返ることが境界になり、
        上限の判定を > と >= で取り違える誤実装をこの2行が弾く。
        規模が上限でも**NPC所有店舗は買収できる**（要件 3.7）ため、その費用は
        買収費用（資産価値の2倍）の数値のままであることも併せて確認し、
        「存在しない」のがプレイヤー所有店舗の増資費用だけであることを固定する"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, 3, 550],
                [0, 1, Owner.PLAYER.value, 9, 38350],
                [0, 2, Owner.NPC.value, 3, 550],
                [0, 3, Owner.NPC.value, 5, 4750],
                [0, 4, Owner.NPC.value, 5, 3000],
                [0, 5, Owner.PLAYER.value, Shop.SCALE_MAX, 76750],
                [0, 6, Owner.NPC.value, Shop.SCALE_MAX, 76750],
            ]
        )
        test_cases = [
            ("プレイヤー所有・規模3", 0, 0, Shop.INVEST_COST * 2**2),
            ("プレイヤー所有・規模9", 0, 1, Shop.INVEST_COST * 2**8),
            ("プレイヤー所有・規模上限（増資費用は存在しない）", 0, 5, None),
            ("NPC所有・規模3・資産価値550", 0, 2, 550 * 2),
            ("NPC所有・規模5・資産価値4750", 0, 3, 4750 * 2),
            ("NPC所有・規模5・資産価値3000", 0, 4, 3000 * 2),
            ("NPC所有・規模上限（買収費用は数値のまま）", 0, 6, 76750 * 2),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_cost(col, row))

    def test_get_sales_switches_by_plot_state(self):
        """空き区画は0のまま変わらないこと。店舗があれば、店舗規模に応じた
        売上額（Shop.SALES_AMOUNT × 2^(規模-1)）を返すこと。規模3・規模10は
        apply_load_data() で保存データから復元した店舗で確認する（Shop.restore()
        が規模のみを書き換えるため、売上額を設置時に確定させ持ち回る構造の
        ままだと、復元後も規模1相当の売上額が固定されたまま返ってしまう。
        本テストがその追従漏れを直接捉える）。設置直後の店舗（規模1）は
        SALES_AMOUNT × 2^0 = 50 となり現行の一律の仮値と偶然一致するため、
        規模2以上のケースを必ず併せて確認する。所有者（NPC/プレイヤー）に
        よって売上額が変わらないことも併せて確認する（売上金が資金に入るかは
        所有者で決まるが、抽選側の話であり売上額そのものの性質ではない）"""
        field = Field()
        field.apply_load_data(
            [
                [0, 1, Owner.PLAYER.value, 1, 100],
                [0, 2, Owner.PLAYER.value, 3, 550],
                [0, 3, Owner.PLAYER.value, 10, 76750],
                [0, 4, Owner.NPC.value, 3, 550],
            ]
        )
        test_cases = [
            ("空き区画", 0, 0, 0),
            ("店舗あり・規模1（復元）", 0, 1, Shop.SALES_AMOUNT * 2**0),
            ("プレイヤー所有・規模3（復元）", 0, 2, Shop.SALES_AMOUNT * 2**2),
            ("プレイヤー所有・規模10（復元）", 0, 3, Shop.SALES_AMOUNT * 2**9),
            (
                "NPC所有・規模3（復元、同規模のプレイヤー所有と同額）",
                0,
                4,
                Shop.SALES_AMOUNT * 2**2,
            ),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_sales(col, row))


class TestFieldIterShopPos(TestParent):
    def test_iter_shop_pos_yields_in_row_then_column_order(self):
        """複数の区画に店舗を設置すると、行昇順→列昇順の決定的な順序で列挙され、
        設置した順序には依存しないこと"""
        field = Field()
        # 設置順序を、期待する列挙順（行昇順→列昇順）とは異なる順にする
        field.set_shop(5, 2, Owner.NPC)
        field.set_shop(0, 0, Owner.PLAYER)
        field.set_shop(3, 0, Owner.NPC)
        field.set_shop(1, 2, Owner.PLAYER)

        positions = list(field.iter_shop_pos())

        self.assertEqual([(0, 0), (3, 0), (1, 2), (5, 2)], positions)

    def test_iter_shop_pos_is_empty_when_no_shop_is_set(self):
        """店舗が1つもない場合は空の列挙になること"""
        field = Field()

        self.assertEqual([], list(field.iter_shop_pos()))


class TestFieldSaveData(TestParent):
    """Field の保存用データへの変換・保存用データからの復元のテスト"""

    def test_get_save_data_lists_shops_in_row_then_column_order(self):
        """保存用データが、店舗のある区画を行昇順→列昇順に並べた
        [col, row, 所有者, 店舗規模, 資産価値] のリストになること。
        所有者は JSON で扱えるよう整数で載る（Owner そのものは載らない）。
        店舗は地域価格倍率が等倍（1.0）になる列0・列17へ置く（ID-020 案8-A。
        資産価値には倍率が乗る——ID-020 ステップ 020-2 以降、保存データの
        資産価値スロットは倍率版の実額になる）。2つの列を使うことで、
        行昇順だけでなく同じ行の中の列昇順も併せて確認できる"""
        test_cases = [
            ("店舗が1つもない", [], []),
            (
                "複数の区画に設置",
                # 設置順序を、期待する並び（行昇順→列昇順）とは異なる順にする
                [(0, 2, Owner.NPC), (0, 0, Owner.PLAYER), (17, 0, Owner.NPC)],
                [
                    [0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, Shop.BUILD_COST],
                    [17, 0, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST],
                    [0, 2, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST],
                ],
            ),
        ]
        for case_name, shops, expected in test_cases:
            with self.subTest(case_name=case_name):
                field = Field()
                for col, row, owner in shops:
                    field.set_shop(col, row, owner)

                self.assertEqual(expected, field.get_save_data())

    def test_apply_load_data_restores_shops_from_save_data(self):
        """保存用データから、初期値以外の店舗規模・資産価値を持つ店舗配置が
        復元されること（データに含まれない区画は空き地のままであること）。
        所有者は整数から Owner へ戻ること"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, 4, 300],
                [5, 2, Owner.NPC.value, 7, 800],
            ]
        )
        test_cases = [
            ("player shop", 0, 0, Owner.PLAYER, 4, 300),
            ("npc shop", 5, 2, Owner.NPC, 7, 800),
            ("vacant plot", 1, 0, None, None, None),
        ]
        for case_name, col, row, owner, scale, value in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(owner, field.get_owner(col, row))
                self.assertEqual(scale, field.get_scale(col, row))
                self.assertEqual(value, field.get_value(col, row))

    def test_save_data_can_be_restored_after_json_round_trip(self):
        """保存用データが JSON を往復しても（ReportStore が json.dumps / json.loads で
        保存・読み込みするため）同じ店舗配置へ復元できること"""
        test_cases = [
            ("店舗が1つもない", []),
            ("複数の区画に設置", [(5, 2, Owner.NPC), (0, 0, Owner.PLAYER)]),
        ]
        for case_name, shops in test_cases:
            with self.subTest(case_name=case_name):
                source = Field()
                for col, row, owner in shops:
                    source.set_shop(col, row, owner)
                save_data = json.loads(json.dumps(source.get_save_data()))

                restored = Field()
                restored.apply_load_data(save_data)

                self.assertEqual(source.get_save_data(), restored.get_save_data())


class TestFieldListNpcGrowthTargets(TestParent):
    """他店建設間隔（ID-008）の抽選対象の列挙（_list_npc_growth_targets()）。
    対象は「規模が上限未満のNPC所有店舗」と「任意の所有者の店舗に上下左右で
    隣接する空き区画」（重複は1回だけ）で、プレイヤー所有店舗そのものは含まれ
    ない。列挙は区画の状態を読むだけで、Field の状態は変えない。
    _list_npc_growth_targets() は grow_npc() 専用の内部ヘルパー（ID-013 で
    _total_shop_value() に揃えた扱い）であり直接テストしない。grow_npc() を
    実行し、乱数源（TestRandomSource）が受け取った並びを検証することで、
    直接テストと同じ精度（並びの完全一致）のまま間接的に確認する"""

    # 抽選結果そのものは本クラスの関心事ではないため固定値で良い（実装は
    # picked が対象集合に含まれるかを検証しない）
    DUMMY_PICK = (0, 0)

    def _received_targets(self, shops):
        # shops: [[col, row, owner.value, scale, value], ...]
        self.test_random_source.set_picked_npc_growth_target(self.DUMMY_PICK)
        field = Field()
        field.apply_load_data(shops)
        field.grow_npc()
        return self.test_random_source.get_npc_growth_received_targets()

    def test_lists_targets_by_plot_state_in_row_then_column_order(self):
        """区画の状態ごとに、抽選へ渡される対象が行昇順→列昇順の並びと一致する
        こと。期待値を並びとして書くことで、除外・重複排除をいずれも「その並びに
        なる」という同じ形の確認で表す。マップの範囲は Field.GRID_COLS /
        Field.GRID_ROWS（現在 18×15）を用いる。店舗が1つもない（対象が空の）
        ときに grow_npc() が抽選そのものを呼ばないことは
        TestFieldGrowNpc.test_does_nothing_when_no_target_exists が確認済みの
        ため、本テストでは扱わない（受け取る並びが無い＝None になるケースを
        subTest の並びに混ぜると、抽選を呼ばない反復だけ self.test_random_source
        の受け取り記録が前の反復の値を引き継いでしまい、誤って通ってしまうため）"""
        last_col = Field.GRID_COLS - 1  # 17
        test_cases = [
            (
                "NPC所有店舗＋隣接する空き区画（プレイヤー所有店舗自身とマップ外の"
                "隣接候補は含まれない）",
                # 右上端のプレイヤー所有店舗はマップ右端・上端のため、隣接候補の
                # うちマップ外にあたる (GRID_COLS, 0)・(last_col, -1) が含まれない
                # ことも併せて確認する
                [
                    [
                        last_col - 1,
                        1,
                        Owner.NPC.value,
                        Shop.INITIAL_SCALE,
                        Shop.BUILD_COST,
                    ],
                    [
                        last_col,
                        0,
                        Owner.PLAYER.value,
                        Shop.INITIAL_SCALE,
                        Shop.BUILD_COST,
                    ],
                ],
                [
                    (last_col - 1, 0),
                    (last_col - 2, 1),
                    (last_col - 1, 1),
                    (last_col, 1),
                    (last_col - 1, 2),
                ],
            ),
            (
                "上限規模（Shop.SCALE_MAX）のNPC所有店舗は除外されるが、"
                "隣接する空き区画は対象のまま残る",
                [[9, 7, Owner.NPC.value, Shop.SCALE_MAX, 99999]],
                [(9, 6), (8, 7), (10, 7), (9, 8)],
            ),
            (
                "複数の店舗に隣接する空き区画は重複せず1回だけ現れる",
                [
                    [9, 7, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST],
                    [9, 9, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST],
                ],
                # (9, 8) は両方の店舗に上下左右で隣接する空き区画だが1回だけ現れる
                [
                    (9, 6),
                    (8, 7),
                    (9, 7),
                    (10, 7),
                    (9, 8),
                    (8, 9),
                    (9, 9),
                    (10, 9),
                    (9, 10),
                ],
            ),
        ]
        for case_name, shops, expected in test_cases:
            with self.subTest(case_name=case_name):
                received = self._received_targets(shops)

                self.assertEqual(expected, received)


class TestFieldGrowNpc(TestParent):
    """他店建設間隔（ID-008）の抽選と実行。抽選対象から1つを選び、それが空き区画
    であれば最小規模のNPC所有店舗を建設し（サイクル2）、NPC所有店舗であれば
    増資する（サイクル3）。どれが選ばれるかは RandomSource が決め、Field は
    乱数の実装を知らない。
    時間経過との結び付け（タイマーの満了・保存）はサイクル4以降で扱う"""

    # 区画はいずれも地域価格倍率が等倍（1.0）になる列0へ置く（ID-020 案8-A）。
    # 本クラスが確認するのは「抽選で選ばれた区画に何が起きるか」であり、
    # 倍率が資産価値へ効くことは TestFieldAreaValue が押さえる。PICKED_VACANT /
    # OTHER_VACANT は PLAYER_SHOP に上下で隣接する（抽選対象に入る条件）
    PLAYER_SHOP = (0, 7)
    PICKED_VACANT = (0, 8)
    OTHER_VACANT = (0, 6)
    NPC_SHOP = (0, 3)
    NPC_SHOP_AT_SCALE_MAX = (0, 1)

    def _make_field(self, shops, picked=None):
        # shops: [[col, row, owner.value, scale, value], ...]
        self.test_random_source.set_picked_npc_growth_target(picked)
        field = Field()
        field.apply_load_data(shops)
        return field

    def _player_shop_only(self, picked):
        return self._make_field(
            [
                [
                    *self.PLAYER_SHOP,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
            ],
            picked=picked,
        )

    def test_builds_npc_shop_on_picked_vacant_plot(self):
        """抽選で空き区画が選ばれると、その区画へ Owner.NPC・最小規模
        （Shop.INITIAL_SCALE）・資産価値 Shop.BUILD_COST の店舗が建ち、
        他の区画（既存の店舗・選ばれなかった空き区画）は一切変わらないこと"""
        field = self._player_shop_only(picked=self.PICKED_VACANT)

        field.grow_npc()

        test_cases = [
            (
                "選ばれた空き区画",
                self.PICKED_VACANT,
                Owner.NPC,
                Shop.INITIAL_SCALE,
                Shop.BUILD_COST,
            ),
            (
                "既存のプレイヤー所有店舗",
                self.PLAYER_SHOP,
                Owner.PLAYER,
                Shop.INITIAL_SCALE,
                Shop.BUILD_COST,
            ),
            ("選ばれなかった空き区画", self.OTHER_VACANT, None, None, None),
        ]
        for case_name, (col, row), owner, scale, value in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(owner, field.get_owner(col, row))
                self.assertEqual(scale, field.get_scale(col, row))
                self.assertEqual(value, field.get_value(col, row))

    def test_picks_from_the_listed_targets(self):
        """抽選対象（_list_npc_growth_targets() の列挙）に選ばれた区画が実在する
        こと。テスト用の実装は列挙に無い座標でも返せてしまうため、この確認が
        ないと列挙と実行の結び付きが迂回されても素通りしてしまう（列挙の並び
        そのものの網羅的な検証は TestFieldListNpcGrowthTargets が持つ）"""
        field = self._player_shop_only(picked=self.PICKED_VACANT)

        field.grow_npc()

        received = self.test_random_source.get_npc_growth_received_targets()
        self.assertIn(self.PICKED_VACANT, received)

    def test_does_nothing_when_no_target_exists(self):
        """抽選対象が1つもない（店舗が1つもない）ときは抽選そのものが行われず、
        盤面も変わらないこと"""
        field = self._make_field([])

        field.grow_npc()

        self.assertEqual(0, self.test_random_source.get_npc_growth_call_count())
        self.assertEqual([], field.get_save_data())

    def test_invests_in_picked_npc_shop(self):
        """抽選でNPC所有店舗が選ばれると、その店舗の規模が1段階上がり、資産価値へ
        増資費用（元の規模から求めた Shop.INVEST_COST × 2^(元の規模-1)。プレイヤー
        の増資 ID-007 と同じ算出式）が加算されること。他の区画（プレイヤー所有
        店舗）は一切変わらないこと"""
        original_scale = 3
        original_value = 12345
        field = self._make_field(
            [
                [
                    *self.PLAYER_SHOP,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ],
                [*self.NPC_SHOP, Owner.NPC.value, original_scale, original_value],
            ],
            picked=self.NPC_SHOP,
        )

        field.grow_npc()

        expected_value = original_value + Shop.INVEST_COST * 2 ** (original_scale - 1)
        test_cases = [
            (
                "増資されたNPC所有店舗",
                self.NPC_SHOP,
                Owner.NPC,
                original_scale + 1,
                expected_value,
            ),
            (
                "既存のプレイヤー所有店舗",
                self.PLAYER_SHOP,
                Owner.PLAYER,
                Shop.INITIAL_SCALE,
                Shop.BUILD_COST,
            ),
        ]
        for case_name, (col, row), owner, scale, value in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(owner, field.get_owner(col, row))
                self.assertEqual(scale, field.get_scale(col, row))
                self.assertEqual(value, field.get_value(col, row))

    def test_excludes_player_shop_and_scale_max_npc_shop_from_received_targets(self):
        """抽選へ渡す対象に、プレイヤー所有店舗と上限規模（Shop.SCALE_MAX）の
        NPC所有店舗が含まれないこと（サイクル1の列挙結果を、grow_npc() 実行時に
        改めて固定する）"""
        field = self._make_field(
            [
                [
                    *self.PLAYER_SHOP,
                    Owner.PLAYER.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ],
                [
                    *self.NPC_SHOP_AT_SCALE_MAX,
                    Owner.NPC.value,
                    Shop.SCALE_MAX,
                    99999,
                ],
                [
                    *self.NPC_SHOP,
                    Owner.NPC.value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ],
            ],
            picked=self.NPC_SHOP,
        )

        field.grow_npc()

        received = self.test_random_source.get_npc_growth_received_targets()
        self.assertNotIn(self.PLAYER_SHOP, received)
        self.assertNotIn(self.NPC_SHOP_AT_SCALE_MAX, received)
        self.assertIn(self.NPC_SHOP, received)


class TestShopValueConsistency(TestParent):
    """資産価値（Shop.value）が、経路（建設 ID-006・増資 ID-007・NPC増資 ID-008・
    買収 ID-009）によらず「Shop.BUILD_COST + Σ（増資時点の Shop.INVEST_COST ×
    2^(規模-1)）」という1つの式に従うことを横断的に固定する特性テスト（ID-013）。
    この振る舞いは既に実装済み（Shop.__init__ / Shop.invest() / Shop.buyout()）
    であり、本テストは新規実装を伴わない——追加した時点で通ることが正しく、
    落ちた場合は ID-006/ID-007/ID-008 のいずれかに退行があることを意味する。
    既存テスト（TestFieldShop・TestFieldCostAndSales・TestFieldSaveData・
    TestFieldGrowNpc）は建設・増資・NPC増資・買収の各経路を個別に検証している
    が、経路をまたいで同じ式に従うことを述べたテストが無かったため、その空白を
    埋める。期待値は実装の式をテスト側で繰り返さず、可能な限り数値として書き
    下ろす（式で書くと、式が誤っていても実装とテストが同じように誤るため）"""

    # 区画はいずれも地域価格倍率が等倍（1.0）になる列0へ置く（ID-020 案8-A）。
    # 本クラスが固定するのは「経路によらず1つの式に従う」ことであり、その式へ
    # 倍率が乗ることは TestFieldAreaValue が横断的に押さえる
    PLAYER_SHOP = (0, 1)
    NPC_SHOP = (0, 6)

    def test_build_gives_the_build_cost_as_the_value(self):
        """建設直後（set_shop()）の資産価値は Shop.BUILD_COST（100）であること
        （要件3.11の増資0回の状態）。設置費用が資産価値へ入らない誤実装を弾く"""
        col, row = self.PLAYER_SHOP
        field = Field()
        field.set_shop(col, row, Owner.PLAYER)

        self.assertEqual(Shop.BUILD_COST, field.get_value(col, row))

    def test_one_player_invest_adds_the_invest_cost_to_the_value(self):
        """プレイヤー所有店舗への1回の増資（invest_shop()）で、資産価値が
        100 + 150 = 250 になること。増資費用が加算されない・規模だけ上がる
        誤実装を弾く"""
        col, row = self.PLAYER_SHOP
        field = Field()
        field.set_shop(col, row, Owner.PLAYER)

        field.invest_shop(col, row)

        self.assertEqual(250, field.get_value(col, row))

    def test_player_invest_to_scale_max_accumulates_by_the_doubling_formula(self):
        """規模1から上限（Shop.SCALE_MAX=10）まで9回増資すると、資産価値が
        100 + 150 × (2^9 − 1) = 76,750（tasks.md の ID-007 確定値と一致）に
        なること。増資費用が規模に追従せず定数のまま積まれる誤実装
        （100 + 150 × 9 = 1,450 になる）を弾く"""
        col, row = self.PLAYER_SHOP
        field = Field()
        field.set_shop(col, row, Owner.PLAYER)

        for _ in range(Shop.SCALE_MAX - Shop.INITIAL_SCALE):
            field.invest_shop(col, row)

        self.assertEqual(Shop.SCALE_MAX, field.get_scale(col, row))
        self.assertEqual(76750, field.get_value(col, row))

    def test_npc_growth_invest_adds_to_the_value_by_the_same_formula_as_player(self):
        """他店の成長（grow_npc() 経由のNPC増資）が、プレイヤーの増資
        （invest_shop()）と同じ式で資産価値を積むこと。式をテスト側に書き
        下ろさず、同じ元の規模・資産価値（式どおりでない任意の値）を持つ店舗を
        両方の経路で1回だけ増資し、結果の資産価値が一致することで確認する。
        NPCの増資に買収費用や別の式が使われる誤実装は、この一致が崩れることで
        弾かれる"""
        original_scale = 6
        original_value = 8000
        player_col, player_row = self.PLAYER_SHOP
        npc_col, npc_row = self.NPC_SHOP

        player_field = Field()
        player_field.apply_load_data(
            [
                [
                    player_col,
                    player_row,
                    Owner.PLAYER.value,
                    original_scale,
                    original_value,
                ]
            ]
        )
        player_field.invest_shop(player_col, player_row)

        npc_field = Field()
        npc_field.apply_load_data(
            [[npc_col, npc_row, Owner.NPC.value, original_scale, original_value]]
        )
        self.test_random_source.set_picked_npc_growth_target(self.NPC_SHOP)
        npc_field.grow_npc()

        self.assertEqual(
            player_field.get_value(player_col, player_row),
            npc_field.get_value(npc_col, npc_row),
        )

    def test_buyout_does_not_change_the_value(self):
        """買収（buyout_shop()）は所有者をプレイヤーへ変えるが、資産価値は
        変わらないこと（Shop.buyout() の docstring が述べる、invest() との
        非対称の確認）。買収費用を資産価値へ加算する誤実装を弾く"""
        value = 550
        col, row = self.NPC_SHOP
        field = Field()
        field.apply_load_data([[col, row, Owner.NPC.value, 3, value]])

        field.buyout_shop(col, row)

        self.assertEqual(Owner.PLAYER, field.get_owner(col, row))
        self.assertEqual(value, field.get_value(col, row))

    def test_invest_on_restored_shop_adds_to_the_restored_value(self):
        """apply_load_data() で復元した店舗（式どおりでない任意の資産価値
        999・規模4）への増資が、復元済みの値へその規模の増資費用を加算した
        999 + 150 × 2^3 = 2,199 になること。増資費用を規模1相当で固定する
        誤実装（999 + 150 = 1,149 になる）を弾く"""
        col, row = self.PLAYER_SHOP
        field = Field()
        field.apply_load_data([[col, row, Owner.PLAYER.value, 4, 999]])

        field.invest_shop(col, row)

        self.assertEqual(2199, field.get_value(col, row))


class TestFieldTotalTax(TestParent):
    """支払い予定税額（土地税＋資産税。ID-014）。土地税は「プレイヤー所有店舗数
    × 地価」、資産税は「プレイヤー所有店舗の資産価値総額 × 税率（5%）」の
    切り捨てで求め、total_tax() はその合計のみを返す（内訳は非公開）。
    合計は足し算のため、一方が過大でもう一方が過小な誤実装は打ち消し合って
    合計が正しく見える可能性がある。したがって、片方の税だけが単独で見える
    盤面（NPC所有店舗のみ／地価0）を必ず含め、誤実装ごとに異なる値になる
    盤面（所有者の混在）で弁別する。期待値は数値で書き下ろし、実装と同じ式を
    テスト側で繰り返さない（ID-013 で確立した書き方）。

    **_land_price() の非公開化（ID-014 TASK-014-7）に伴う統合**: 旧
    TestFieldLandPrice（_land_price() を直接呼んでいた）はここへ統合した。
    _land_price() は total_tax() 専用の内部ヘルパーになったため、直接の
    テストは持たず、以下の方針で間接テストへ作り替える。
    - **既に本クラスにある盤面と同じものは重複させない**。「総額が270未満
      なら地価0」（旧 test_zero_when_the_total_value_is_less_than_the_grid_size）
      は test_asset_tax_alone_when_land_price_is_zero と同じ盤面（資産価値100の
      プレイヤー所有店舗1軒）であり、既存のテストがそのまま地価0のケースを
      兼ねる。「空盤面の地価は0」（旧 test_zero_for_the_empty_field）も、
      店舗が無ければプレイヤー所有店舗数が0で土地税は地価の値によらず0になり
      地価そのものは total_tax() 越しに観測できないため、独立したテストとしては
      持たない（空盤面の税額0は test_zero_for_the_empty_field が既に検証する）
    - **単調性の個別テスト（旧 test_land_price_does_not_decrease_as_the_total_value_increases）は持たない**。
      商の向き（割る数と割られる数）を取り違えた誤実装は、以下の
      floor-division の境界テストが返す具体的な数値（42 / 43 など）と
      まったく異なる値になるため、その誤実装は数値の不一致で既に弾かれており、
      不等式による別テストを重ねる意味が無い
    - **地価が観測できるよう、いずれのケースもプレイヤー所有店舗数を1以上に
      保つ**（0軒だと土地税が地価の値によらず0になり、地価の変化が
      total_tax() に現れない）"""

    def test_zero_for_the_empty_field(self):
        """店舗が1軒も無い盤面の支払い予定税額は 0 であること（空盤面での
        例外・None を返す誤実装を弾く）"""
        field = Field()

        self.assertEqual(0, field.total_tax())

    def test_zero_when_only_npc_owned_shops_exist(self):
        """NPC所有店舗のみ（資産価値5,000）の盤面では、地価は正（5,000 // 270 =
        18）でも支払い予定税額は 0 であること。土地税が全店舗数（NPC所有を
        含む）を数える誤実装（1 × 18 = 18）と、資産税が全店舗の総額を使う
        誤実装（5,000 × 5 // 100 = 250）の両方をこの1件で弾く"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.NPC.value, Shop.INITIAL_SCALE, 5000]])

        self.assertEqual(0, field.total_tax())

    def test_asset_tax_alone_when_land_price_is_zero(self):
        """プレイヤー所有店舗1軒（資産価値100=Shop.BUILD_COST）のみの盤面では、
        総額が全区画数（270）未満のため地価・土地税は0だが、資産税
        （100 × 5 // 100 = 5）は付くこと。総額が270未満のとき税額全体を0に
        する誤実装を弾く"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 100]])

        self.assertEqual(5, field.total_tax())

    def test_sums_land_tax_and_asset_tax_for_mixed_ownership(self):
        """プレイヤー所有2軒（資産価値1,000・2,000）とNPC所有1軒（資産価値
        3,000）が混在する盤面。
        総額 = 1,000 + 2,000 + 3,000 = 6,000、地価 = 6,000 // 270 = 22、
        土地税 = プレイヤー所有店舗数2 × 22 = 44、
        プレイヤー所有の資産価値総額 = 1,000 + 2,000 = 3,000、
        資産税 = 3,000 × 5 // 100 = 150、
        支払い予定税額 = 44 + 150 = 194。
        土地税が全店舗数（3軒）を数える誤実装（3 × 22 + 150 = 216）、資産税が
        全店舗の総額（6,000）を使う誤実装（44 + 300 = 344）、地価をプレイヤー
        所有分だけ（3,000 // 270 = 11）で求める誤実装（2 × 11 + 150 = 172）、
        土地税と資産税を取り違える誤実装のいずれとも異なる値になり、この
        1件で弁別できる"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 1000],
                [0, 1, Owner.PLAYER.value, Shop.INITIAL_SCALE, 2000],
                [0, 2, Owner.NPC.value, Shop.INITIAL_SCALE, 3000],
            ]
        )

        self.assertEqual(194, field.total_tax())

    def test_asset_tax_rounds_down(self):
        """プレイヤー所有店舗1軒（資産価値1,999）の資産税は切り捨てで99
        （1,999 × 5 // 100 = 9,995 // 100 = 99）であること。地価は
        1,999 // 270 = 7、土地税は1 × 7 = 7で、支払い予定税額は7 + 99 = 106。
        四捨五入する誤実装（資産税が100になり合計107）を弾く"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 1999]])

        self.assertEqual(106, field.total_tax())

    def test_shop_grown_to_the_scale_limit(self):
        """規模上限まで育ったプレイヤー所有店舗1軒（資産価値76,750。ID-007の
        確定値どおり規模10到達時点の資産価値）の支払い予定税額。
        地価 = 76,750 // 270 = 284、土地税 = 1 × 284 = 284、
        資産税 = 76,750 × 5 // 100 = 383,750 // 100 = 3,837、
        支払い予定税額 = 284 + 3,837 = 4,121。大きい値での桁あふれ・式の
        取り違えを弾く"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.PLAYER.value, Shop.SCALE_MAX, 76750]])

        self.assertEqual(4121, field.total_tax())

    def test_land_price_floor_division_boundary_reflected_in_total_tax(self):
        """地価（総額 // 270）の端数が切り捨てられること（旧
        test_exact_division・test_floor_division_truncates_the_remainder を
        統合）。総額 809（270未満側）・810（ちょうど3倍）・811（3倍超）の
        いずれもプレイヤー所有店舗1軒の資産価値そのものであるため、資産税は
        3件とも 40（809×5//100 = 811×5//100 = 40、810×5//100 = 40）で一定になり、
        支払い予定税額の差はすべて地価の切り捨てに由来する。四捨五入の誤実装
        は 809 を地価3（総額42）にしてしまい、810側（総額43）と区別できなく
        なるため、この境界で弾かれる"""
        test_cases = [
            ("270未満側の端数は切り捨てで地価2・総額42", 809, 42),
            ("270のちょうど3倍で地価3・総額43", 810, 43),
            ("270の3倍を超える端数は切り捨てで地価3のまま・総額43", 811, 43),
        ]
        for case_name, value, expected in test_cases:
            with self.subTest(case_name=case_name):
                field = Field()
                field.apply_load_data(
                    [[0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, value]]
                )

                self.assertEqual(expected, field.total_tax())

    def test_land_price_sums_both_player_and_npc_owned_shops(self):
        """地価の算出（_land_price() が使う _total_shop_value()）はプレイヤー
        所有店舗とNPC所有店舗の両方を含めること（要件3.10は全店舗が対象）を
        total_tax() 経由で検証する（旧 test_sums_both_player_and_npc_owned_shops
        を統合）。
        総額 = 300（プレイヤー）+ 300（NPC）= 600、地価 = 600 // 270 = 2、
        土地税 = プレイヤー所有店舗数1 × 2 = 2、資産税 = 300 × 5 // 100 = 15、
        支払い予定税額 = 2 + 15 = 17。NPC所有店舗を総額から除く誤実装は総額が
        300に下がり地価が1になるため、支払い予定税額が16に落ちてこの不一致で
        弾かれる"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 300],
                [0, 1, Owner.NPC.value, Shop.INITIAL_SCALE, 300],
            ]
        )

        self.assertEqual(17, field.total_tax())

    def test_land_price_does_not_collapse_shops_with_the_same_value(self):
        """同じ資産価値の店舗が複数あっても、地価の算出でその口数ぶん総額へ
        合算されることを total_tax() 経由で検証する（旧
        test_does_not_collapse_shops_with_the_same_value を統合）。集合（set）で
        重複を潰す誤実装は総額が 900→300 に下がり、地価が 3→1 に落ちるため、
        この不一致で弾かれる。
        総額 = 300 × 3 = 900、地価 = 900 // 270 = 3、プレイヤー所有店舗数2
        （区画(0,0)・(0,2)）、土地税 = 3 + 3 = 6、プレイヤー所有の資産価値総額
        = 300 + 300 = 600、資産税 = 600 × 5 // 100 = 30、
        支払い予定税額 = 6 + 30 = 36"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 300],
                [0, 1, Owner.NPC.value, Shop.INITIAL_SCALE, 300],
                [0, 2, Owner.PLAYER.value, Shop.INITIAL_SCALE, 300],
            ]
        )

        self.assertEqual(36, field.total_tax())

    def test_land_price_uses_the_restored_value_without_recomputing_from_scale(self):
        """apply_load_data() で復元した、規模と資産価値が式どおりでない店舗
        （規模4・資産価値999）でも、地価の算出に保持している資産価値がそのまま
        使われることを total_tax() 経由で検証する（旧
        test_uses_the_restored_value_without_recomputing_from_scale を統合）。
        規模から資産価値を再計算する誤実装（Shop.BUILD_COST +
        Shop.INVEST_COST × (2^3 − 1) = 1,150）は地価が4・資産税が57になり
        支払い予定税額が61になるため、正しい実装（999 → 地価3・資産税49・
        支払い予定税額52）と食い違い、この不一致で弾かれる。
        地価 = 999 // 270 = 3、土地税 = 1 × 3 = 3、資産税 = 999 × 5 // 100 = 49、
        支払い予定税額 = 3 + 49 = 52"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.PLAYER.value, 4, 999]])

        self.assertEqual(52, field.total_tax())

    def test_land_price_sums_all_shops_scattered_across_multiple_rows(self):
        """複数行に散らばった、規模・資産価値がばらばらの店舗の全件が地価の
        算出に含まれることを total_tax() 経由で検証する（旧
        test_sums_all_shops_scattered_across_multiple_rows を統合）。1行分・
        1件目だけを見る誤実装は総額が大きく下がり（先頭の店舗のみなら 100 →
        地価0・資産税5・支払い予定税額5）、正しい実装と食い違うため、この
        不一致で弾かれる。
        総額 = 100 + 250 + 550 + 700 = 1,600、地価 = 1,600 // 270 = 5、
        プレイヤー所有店舗数2（(0,0)・(0,7)）、土地税 = 5 + 5 = 10、
        プレイヤー所有の資産価値総額 = 100 + 550 = 650、
        資産税 = 650 × 5 // 100 = 32、支払い予定税額 = 10 + 32 = 42。
        4軒は左端の列0と右端の列17へ振り分ける（ID-020 案8-A。いずれも
        地域価格倍率は等倍で、行も4通りに散らばる）"""
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, 1, 100],
                [17, 3, Owner.NPC.value, 2, 250],
                [0, 7, Owner.PLAYER.value, 5, 550],
                [17, 14, Owner.NPC.value, 3, 700],
            ]
        )

        self.assertEqual(42, field.total_tax())

    def test_land_price_increases_after_npc_growth_by_building(self):
        """総額 2,680（地価9）の盤面へ、grow_npc() が空き区画にNPC所有店舗
        （Shop.BUILD_COST=100）を建てると、総額が2,780になり地価が10へ上がる
        ことを total_tax() 経由で検証する（旧
        test_npc_growth_by_building_increases_land_price を統合）。切り捨ての
        境界（270の倍数）を跨ぐ盤面を選んでいるため、建設による増分（+100）が
        確実に地価へ現れる。プレイヤー所有店舗（(0,0)、資産価値2,680）は
        NPC所有店舗の建設で変化しないため、資産税は建設の前後で134のまま
        （2,680 × 5 // 100 = 134）一定になり、支払い予定税額の差（143→144）は
        地価の上昇（土地税9→10）にのみ由来する。
        **総額 ÷ 店舗数（平均店舗価値）の誤実装を弾く**: 店舗数が1→2に増えると
        平均は 2,680 → 1,390 に下がり、地価が下がる方向に誤る"""
        col, row = 0, 0
        # 空き区画も列0（地域価格倍率が等倍）に取る。倍率の乗る区画だと
        # 建設される店舗の資産価値が Shop.BUILD_COST を超え、増分が +100 で
        # なくなって地価の遷移する境界がずれる（ID-020 案8-A）
        vacant = (0, 1)
        field = Field()
        field.apply_load_data([[col, row, Owner.PLAYER.value, 5, 2680]])
        self.assertEqual(143, field.total_tax())

        self.test_random_source.set_picked_npc_growth_target(vacant)
        field.grow_npc()

        self.assertEqual(144, field.total_tax())

    def test_land_price_increases_after_npc_growth_by_investing(self):
        """総額2,600（地価9）の盤面で、grow_npc() がNPC所有店舗（規模1）へ
        増資すると増資費用（150）が加わり総額が2,750になり地価が10へ上がる
        ことを total_tax() 経由で検証する（旧
        test_npc_growth_by_investing_increases_land_price を統合）。
        地価の変化を土地税から観測するにはプレイヤー所有店舗が1軒以上要る
        （0軒だと土地税が常に0で地価の値によらない）ため、資産価値0の
        プレイヤー所有店舗を1軒加える。資産価値0なら資産税は増資の前後で
        常に0のままとなり、地価の遷移する総額の境界（2,600→2,750。旧テストの
        地価9→10）を動かさずに済む（正の資産価値を足すと、その分だけ境界の
        総額がずれてしまう）。増資が資産価値へ反映されない誤実装は、特性テスト
        （TestShopValueConsistency）と二重の網で弾く。
        NPC所有店舗も列0（地域価格倍率が等倍）に取る。倍率の乗る区画だと
        増資費用に倍率が掛かって増分が +150 でなくなり、地価の遷移する境界が
        ずれる（ID-020 案8-A）"""
        col, row = 0, 5
        field = Field()
        field.apply_load_data(
            [
                [0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 0],
                [col, row, Owner.NPC.value, 1, 2600],
            ]
        )
        self.assertEqual(9, field.total_tax())

        self.test_random_source.set_picked_npc_growth_target((col, row))
        field.grow_npc()

        self.assertEqual(10, field.total_tax())


class TestFieldListSalesLotteryEntries(TestParent):
    """売上の抽選（ID-012）で乱数源へ渡す並びの列挙（_list_sales_lottery_entries()）。
    並びには同じ区画が**重み分だけ重複して**現れ、乱数源はこれまでどおり等確率で
    1つを引く（重みは呼び手が並びの作り方で表す）。重みは**横方向に連続する
    プレイヤー所有店舗の本数**で、連なりに属する全店舗が同じ重みを持つ。NPC所有
    店舗と空き区画は連なりを断ち切り、NPC所有店舗と単独のプレイヤー所有店舗の
    重みは 1。列挙は区画の状態を読むだけで、Field の状態は変えない。
    _list_sales_lottery_entries() は pick_sales_shop() 専用の内部ヘルパー
    （ID-013 で _total_shop_value() に揃えた扱い）であり直接テストしない。
    pick_sales_shop() を実行し、乱数源（TestRandomSource）が受け取った並びを
    検証することで、直接テストと同じ精度（並びの完全一致）のまま間接的に確認
    する。店舗が1つもない（対象が空の）ときに抽選そのものが呼ばれないことは
    TestFieldPickSalesShop.test_returns_none_without_lottery_when_no_shop_exists
    が確認済みのため、本クラスでは扱わない"""

    ROW = 3

    # 抽選結果そのものは本クラスの関心事ではないため固定値で良い
    DUMMY_PICK = (0, 0)

    def _received_entries(self, *rows):
        """盤面を「行番号・左端の列・1行分の文字列」の組で与える
        （p=プレイヤー所有店舗・n=NPC所有店舗・.=空き区画）。店舗規模と資産価値は
        重みに影響しないため初期値で揃える"""
        owners = {"p": Owner.PLAYER, "n": Owner.NPC}
        self.test_random_source.set_picked_sales_shop(self.DUMMY_PICK)
        field = Field()
        field.apply_load_data(
            [
                [
                    start_col + offset,
                    row,
                    owners[char].value,
                    Shop.INITIAL_SCALE,
                    Shop.BUILD_COST,
                ]
                for row, start_col, pattern in rows
                for offset, char in enumerate(pattern)
                if char != "."
            ]
        )
        field.pick_sales_shop()
        return self.test_random_source.get_sales_shop_received_targets()

    def test_weight_is_the_length_of_the_horizontal_player_run(self):
        """連なりの長さがそのまま重みになり、連なりの全メンバーが同じ重みを持つ
        こと。期待値は実装と同じ算出をテスト側で繰り返さず、並びをそのまま
        書き下ろす（行昇順→列昇順・重複は連続配置）"""
        row = self.ROW
        test_cases = [
            ("単独のプレイヤー所有店舗の重みは 1", ((row, 0, "p"),), [(0, row)]),
            (
                "2連は各 2",
                ((row, 0, "pp"),),
                [(0, row), (0, row), (1, row), (1, row)],
            ),
            (
                "3連は各 3（「隣接数+1」なら端 2・中 3 に割れ、"
                "「隣接していれば一律 2」なら各 2 になる）",
                ((row, 0, "ppp"),),
                [
                    (0, row),
                    (0, row),
                    (0, row),
                    (1, row),
                    (1, row),
                    (1, row),
                    (2, row),
                    (2, row),
                    (2, row),
                ],
            ),
            (
                "NPC所有店舗は横に並んでも重みが上がらない（各 1）",
                ((row, 0, "nnn"),),
                [(0, row), (1, row), (2, row)],
            ),
        ]
        for case_name, rows, expected in test_cases:
            with self.subTest(case_name=case_name):
                received = self._received_entries(*rows)

                self.assertEqual(expected, received)

    def test_run_is_broken_by_npc_shop_vacant_plot_and_row_boundary(self):
        """連なりが繋がる条件（同一行で列が連続し、プレイヤー所有店舗のみで
        繋がる）を、切れ方の側から確認する。縦方向は連なりに数えず、行を跨いでも
        連ならない"""
        row = self.ROW
        last_col = Field.GRID_COLS - 1  # 17
        test_cases = [
            (
                "NPC所有店舗は連なりを断ち切り、跨いで繋げもしない（ppnpp）",
                ((row, 0, "ppnpp"),),
                [
                    (0, row),
                    (0, row),
                    (1, row),
                    (1, row),
                    (2, row),
                    (3, row),
                    (3, row),
                    (4, row),
                    (4, row),
                ],
            ),
            (
                "空き区画は連なりを断ち切る（pp.p）",
                ((row, 0, "pp.p"),),
                [(0, row), (0, row), (1, row), (1, row), (3, row)],
            ),
            (
                "端のNPC所有店舗は連なりの一員に数えない（npp）",
                ((row, 0, "npp"),),
                [(0, row), (1, row), (1, row), (2, row), (2, row)],
            ),
            (
                "端のNPC所有店舗は連なりの一員に数えない（ppn）",
                ((row, 0, "ppn"),),
                [(0, row), (0, row), (1, row), (1, row), (2, row)],
            ),
            (
                "縦に並んでも連ならない（各 1）",
                ((row, 5, "p"), (row + 1, 5, "p")),
                [(5, row), (5, row + 1)],
            ),
            (
                "行末と次の行の先頭は隣接しない（各 1）",
                ((row, last_col, "p"), (row + 1, 0, "p")),
                [(last_col, row), (0, row + 1)],
            ),
            (
                "行ごとに独立した連なりになる（2連の行と3連の行）",
                ((row, 2, "pp"), (row + 1, 4, "ppp")),
                [
                    (2, row),
                    (2, row),
                    (3, row),
                    (3, row),
                    (4, row + 1),
                    (4, row + 1),
                    (4, row + 1),
                    (5, row + 1),
                    (5, row + 1),
                    (5, row + 1),
                    (6, row + 1),
                    (6, row + 1),
                    (6, row + 1),
                ],
            ),
        ]
        for case_name, rows, expected in test_cases:
            with self.subTest(case_name=case_name):
                received = self._received_entries(*rows)

                self.assertEqual(expected, received)


class TestFieldPickSalesShop(TestParent):
    """売上発生間隔（ID-010）の抽選。抽選へ渡す並びは ID-012 で重み付き抽選リスト
    へ差し替わったが、抽選そのもの（並びから1つを引く）と戻り値（選ばれた区画）は
    変わらない。どれが選ばれるかは RandomSource が決め、Field は乱数の実装を
    知らない。
    盤面には**3連のプレイヤー所有店舗を必ず含める**。店舗がすべて単独の盤面だと
    重み付き抽選リストが iter_shop_pos() と一致してしまい、差し替えが行われて
    いなくてもテストが通ってしまう"""

    ROW = 3
    PLAYER_RUN = ((0, ROW), (1, ROW), (2, ROW))
    NPC_SHOP = (5, ROW)
    PICKED = (1, ROW)

    def _make_field(self, shops, picked=None):
        # shops: [[col, row, owner.value, scale, value], ...]
        self.test_random_source.set_picked_sales_shop(picked)
        field = Field()
        field.apply_load_data(shops)
        return field

    def _player_run_and_npc_shop(self, picked):
        shops = [
            [col, row, Owner.PLAYER.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]
            for col, row in self.PLAYER_RUN
        ]
        shops.append(
            [*self.NPC_SHOP, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]
        )
        return self._make_field(shops, picked=picked)

    def test_passes_the_sales_lottery_entries_to_the_lottery(self):
        """抽選へ渡される並びが iter_shop_pos() のような対象の単純な列挙ではなく、
        _list_sales_lottery_entries() が組み立てる重み付きの並びであること。
        3連の重みで並びが伸びる盤面（両者が一致しない盤面）で確かめる（並びの
        網羅的な検証は TestFieldListSalesLotteryEntries が持つ）"""
        field = self._player_run_and_npc_shop(picked=self.PICKED)

        field.pick_sales_shop()

        received = self.test_random_source.get_sales_shop_received_targets()
        self.assertNotEqual(list(field.iter_shop_pos()), received)

    def test_returns_the_picked_shop_with_a_single_lottery(self):
        """乱数源が選んだ区画がそのまま戻り値になり、抽選は1回だけ行われること"""
        field = self._player_run_and_npc_shop(picked=self.PICKED)

        picked = field.pick_sales_shop()

        self.assertEqual(self.PICKED, picked)
        self.assertEqual(1, self.test_random_source.get_sales_shop_call_count())

    def test_returns_none_without_lottery_when_no_shop_exists(self):
        """店舗が1軒も無いときは抽選そのものが行われず、None を返すこと
        （ID-010 の振る舞いの維持）"""
        field = self._make_field([])

        self.assertIsNone(field.pick_sales_shop())
        self.assertEqual(0, self.test_random_source.get_sales_shop_call_count())


class TestFieldSellShopsForShortfall(TestParent):
    """税金不足時の売却（ID-016。本タスクの機能の中心）。
    sell_shops_for_shortfall(shortfall) は、不足額（shortfall）を満たすまで、
    または売る店舗が尽きるまで、抽選で選ばれたプレイヤー所有店舗を1軒ずつ
    NPC所有へ変更し、**調達できた額（raised）を返す**（案6。ID-016 の形の
    まま）。
    加えて、**不足額を満たせたか**（shortfall_covered。raised >= shortfall
    と厳密に同値）を本メソッド呼び出しの**副作用として内部状態へ記録し**、
    `shortfall_covered` プロパティ越しに読ませる（ID-017 案2）。これは
    「売り尽くしても不足額に届かなかったか」（ID-017 のゲームオーバー判定）
    を Field 自身が答えるために ID-017 で追加した値であり、コマンド
    （売却を実行する）とクエリ（満たせたかを答える）を分離して
    sell_shops_for_shortfall() を単一の機能に保つため、戻り値ではなく
    プロパティとして分離している（ID-016 時点では raised のみを返し、
    残不足は呼び手が self._money の符号から読む設計だったが、その符号が
    ゲームオーバーという業務上の判定になったため、判定そのものを Field の
    内側へ閉じる形へ反転させた。詳細は sell_shops_for_shortfall() /
    shortfall_covered の docstring を参照）。
    Field の公開インタフェースは本メソッドと shortfall_covered プロパティの
    みで、抽選対象の列挙（_list_sell_targets()）・1軒ぶんの実行
    （_sell_player_shop()）はいずれも非公開の内部ヘルパーであり直接の
    テストを持たない（_list_npc_growth_targets() / grow_npc() などと同じ、
    **クラスの公開インタフェースに対して振る舞いを検証し、内部の実装詳細は
    直接テストしない**という既存方針の踏襲）。
    そのため、1軒ぶんの抽選・所有者変更・売却額の算出・対象の絞り込みという
    サイクル1相当の性質も、繰り返しと停止条件・shortfall_covered という
    サイクル2固有の性質も、すべて本クラスが sell_shops_for_shortfall() 経由の
    間接テストとして扱う。
    店舗の資産価値は既定で Shop.BUILD_COST（100・売却額50）に揃え、繰り返しの
    回数が調達額からそのまま読み取れるようにする（例外は資産価値の半額の
    切り捨てを確かめるテストのみ、奇数の資産価値を使う）"""

    SHOP_A = (0, 0)
    SHOP_B = (1, 0)
    SHOP_C = (2, 0)
    EARLIER_ROW_SHOP = (2, 1)
    SAME_ROW_OTHER_SHOP = (0, 7)
    SAME_ROW_TARGET_SHOP = (9, 7)
    NPC_SHOP = (5, 5)
    SALE_AMOUNT = Shop.BUILD_COST // 2  # 50

    def _player_shop(self, pos, value=Shop.BUILD_COST, scale=Shop.INITIAL_SCALE):
        return [*pos, Owner.PLAYER.value, scale, value]

    def _npc_shop(self, pos, value=Shop.BUILD_COST, scale=Shop.INITIAL_SCALE):
        return [*pos, Owner.NPC.value, scale, value]

    def _make_field(self, shops, picks=None):
        # shops: [[col, row, owner.value, scale, value], ...]
        if picks is not None:
            self.test_random_source.set_picked_sell_shop_sequence(picks)
        field = Field()
        field.apply_load_data(shops)
        return field

    def test_stops_after_one_sale_when_it_is_enough(self):
        """1軒の売却額だけで不足額を満たせる場合、抽選で選ばれた店舗を1軒だけ
        売って止まり、抽選も1回しか呼ばれないこと（**満たした時点で止まり
        余分に売らない**。選ばれなかった SHOP_B が売られずに残ることで確認）。
        売却された店舗は所有者が NPC へ変わる一方、店舗規模・資産価値は
        変わらない（案3。買収 Shop.buyout() と対称の非対称）。資産価値を
        奇数（101）にして、調達額が資産価値の半額の切り捨て（50）であることも
        併せて確認する（いずれも同じ1回の売却の結果であり独立した条件では
        ないため1つのテストにまとめる）。**1軒で足りた**ため
        shortfall_covered は真"""
        scale = 4
        value = 101
        field = self._make_field(
            [
                self._player_shop(self.SHOP_A, value=value, scale=scale),
                self._player_shop(self.SHOP_B),
            ],
            picks=[self.SHOP_A],
        )

        raised = field.sell_shops_for_shortfall(30)  # 50 で足りる不足額

        self.assertEqual(50, raised)
        self.assertTrue(field.shortfall_covered)
        self.assertEqual(1, self.test_random_source.get_sell_shop_call_count())
        self.assertEqual(Owner.NPC, field.get_owner(*self.SHOP_A))
        self.assertEqual(scale, field.get_scale(*self.SHOP_A))
        self.assertEqual(value, field.get_value(*self.SHOP_A))
        self.assertEqual(Owner.PLAYER, field.get_owner(*self.SHOP_B))

    def test_lists_only_player_shops_in_row_major_order(self):
        """抽選（乱数源）へ渡される対象がプレイヤー所有店舗のみで、行昇順→列昇順の
        並びになっていること（_list_sell_targets() の間接テスト。異なる行
        （EARLIER_ROW_SHOP）と同じ行の列違い（SAME_ROW_OTHER_SHOP と
        SAME_ROW_TARGET_SHOP）の両方で並び順を確かめ、NPC所有店舗が対象に
        含まれないことも併せて確認する）。同じ1回の売却の結果として、
        選ばれなかった他のプレイヤー所有店舗・NPC所有店舗が影響を受けない
        ことも確認する（対象の列挙と非干渉は同じ観測から導けるため1つの
        テストにまとめる）"""
        field = self._make_field(
            [
                self._player_shop(self.EARLIER_ROW_SHOP),
                self._player_shop(self.SAME_ROW_OTHER_SHOP),
                self._player_shop(self.SAME_ROW_TARGET_SHOP),
                self._npc_shop(self.NPC_SHOP),
            ],
            picks=[self.SAME_ROW_TARGET_SHOP],
        )

        field.sell_shops_for_shortfall(1)  # 1軒売れば足りる不足額

        received = self.test_random_source.get_sell_shop_received_targets()
        self.assertEqual(
            [
                self.EARLIER_ROW_SHOP,
                self.SAME_ROW_OTHER_SHOP,
                self.SAME_ROW_TARGET_SHOP,
            ],
            received,
        )
        self.assertEqual(Owner.PLAYER, field.get_owner(*self.EARLIER_ROW_SHOP))
        self.assertEqual(Owner.PLAYER, field.get_owner(*self.SAME_ROW_OTHER_SHOP))
        self.assertEqual(Owner.NPC, field.get_owner(*self.NPC_SHOP))

    def test_sells_shops_until_the_exact_shortfall_is_met(self):
        """1軒では不足額に届かない場合、複数軒を続けて売ること。不足額を
        2軒ぶんの売却額にちょうど合わせ（**ちょうど足りる境界**）、3軒目
        （SHOP_C）は不要なため売られずに残ることを確認する。**ちょうど
        足りた**（raised == shortfall）ため shortfall_covered は真"""
        field = self._make_field(
            [
                self._player_shop(self.SHOP_A),
                self._player_shop(self.SHOP_B),
                self._player_shop(self.SHOP_C),
            ],
            picks=[self.SHOP_A, self.SHOP_B],
        )

        raised = field.sell_shops_for_shortfall(self.SALE_AMOUNT * 2)

        self.assertEqual(self.SALE_AMOUNT * 2, raised)
        self.assertTrue(field.shortfall_covered)
        self.assertEqual(2, self.test_random_source.get_sell_shop_call_count())
        self.assertEqual(Owner.NPC, field.get_owner(*self.SHOP_A))
        self.assertEqual(Owner.NPC, field.get_owner(*self.SHOP_B))
        self.assertEqual(Owner.PLAYER, field.get_owner(*self.SHOP_C))

    def test_includes_the_surplus_in_the_raised_amount(self):
        """最後の1軒の売却額が不足額を上回っても、超過分を切り捨てず全額を
        調達額に含めること（案2。不足分ちょうどに削らない）。超過して足りた
        ため shortfall_covered は真"""
        field = self._make_field([self._player_shop(self.SHOP_A)], picks=[self.SHOP_A])

        raised = field.sell_shops_for_shortfall(self.SALE_AMOUNT - 20)  # 30 < 50

        self.assertEqual(self.SALE_AMOUNT, raised)  # 超過分20を含む全額
        self.assertTrue(field.shortfall_covered)

    def test_stops_when_shops_run_out_while_still_short(self):
        """売る店舗が尽きたら、不足額に届かなくても止まり、それまでに調達
        できた額を返すこと。抽選の呼び出し回数がプレイヤー所有店舗数（2）を
        超えないことで、**繰り返しが必ず終わる**こと（1回の売却で対象が必ず
        1つ減るため）も併せて確認する。**売る店舗が尽きて届かなかった**ため
        shortfall_covered は偽（ID-017 のゲームオーバー判定が答えを得る境界
        そのもの）"""
        field = self._make_field(
            [self._player_shop(self.SHOP_A), self._player_shop(self.SHOP_B)],
            picks=[self.SHOP_A, self.SHOP_B],
        )

        raised = field.sell_shops_for_shortfall(self.SALE_AMOUNT * 100)  # 尽きる不足額

        self.assertEqual(self.SALE_AMOUNT * 2, raised)
        self.assertFalse(field.shortfall_covered)
        self.assertEqual(2, self.test_random_source.get_sell_shop_call_count())
        self.assertEqual(Owner.NPC, field.get_owner(*self.SHOP_A))
        self.assertEqual(Owner.NPC, field.get_owner(*self.SHOP_B))

    def test_does_nothing_when_no_player_shop_exists(self):
        """プレイヤー所有店舗が1軒も無いときは抽選そのものが行われず、盤面も
        変わらず、調達額として 0 を返すこと（NPC所有店舗のみの盤面でも売却は
        起きない。売る店舗が最初から尽きている場合の境界）。**最初から売る
        店舗が無い**ため shortfall_covered は偽（不足額が0でない限り）"""
        field = self._make_field([self._npc_shop(self.NPC_SHOP)])

        raised = field.sell_shops_for_shortfall(100)

        self.assertEqual(0, raised)
        self.assertFalse(field.shortfall_covered)
        self.assertEqual(0, self.test_random_source.get_sell_shop_call_count())
        self.assertEqual(Owner.NPC, field.get_owner(*self.NPC_SHOP))

    def test_sells_nothing_when_the_shortfall_is_zero(self):
        """不足額が0のときは1軒も売らず、抽選も呼ばれず、0を返すこと。
        不足していない（shortfall <= raised が最初から成立する）ため
        shortfall_covered は真"""
        field = self._make_field([self._player_shop(self.SHOP_A)])

        raised = field.sell_shops_for_shortfall(0)

        self.assertEqual(0, raised)
        self.assertTrue(field.shortfall_covered)
        self.assertEqual(0, self.test_random_source.get_sell_shop_call_count())

    def test_shortfall_covered_defaults_to_true_before_any_sale(self):
        """sell_shops_for_shortfall() を一度も呼んでいない Field（生成直後・
        復元直後のいずれも同じ状態）では、shortfall_covered が真を返すこと
        （「まだ不足していない」という自然な既定値。ID-017 案3により終了
        状態は保存も復元時の再判定もしないため、apply_load_data() 越しの
        復元でも本プロパティの値は変わらない）"""
        field = self._make_field([self._player_shop(self.SHOP_A)])

        self.assertTrue(field.shortfall_covered)
        self.assertEqual(Owner.PLAYER, field.get_owner(*self.SHOP_A))


class TestFieldClearShopCount(TestParent):
    """規定店舗数への到達判定（要件 3.16。ID-028 サイクル 028-1）。
    プレイヤー所有店舗が規定店舗数（Field.CLEAR_SHOP_COUNT）へ到達している
    かを Field.is_clear_shop_count_reached プロパティで返す。
    **「軒数」（player_shop_count）と「到達しているか」（is_clear_shop_count_reached）
    は別々のプロパティに分ける**（ID-028_subtasks.md 決定2・案2-C）。
    前者は内部状態として保持し、set_shop() / buyout_shop() /
    _sell_player_shop()（sell_shops_for_shortfall() 越し）/ apply_load_data()
    の4つの操作の直後に更新する。後者は内部状態を持たず、前者を
    `>=` で比べるだけの都度算出（is_all_player_owned が
    TASK-017-7 で真偽値そのものを内部状態化したのとは異なり、真偽値は
    算出のまま、数量だけを内部状態にする）。
    player_shop_count は本判定だけでなく、プレイヤーステータスの店舗数
    表示（サイクル 028-4。決定6-A）からも読まれるため、ここで両方の
    公開プロパティの形を固める。
    規定店舗数は tasks.md の完了条件どおり調整対象のため、期待値へ
    100 を直書きせず Field.CLEAR_SHOP_COUNT を参照する式で書く
    （ID-028_subtasks.md「テスト設計の注意」1）"""

    def _player_shop_positions(self, count):
        """行昇順→列昇順で先頭から count 個ぶんの座標を返す（他クラスと
        揃え iter_shop_pos() と同じ順序にする）。100軒規模の盤面を
        set_shop() の繰り返しで組み立てるのは低コストなので専用の
        座標ヘルパーのみを用意し、保存データの組み立てはテスト側に残す"""
        return [
            (col, row)
            for row in range(Field.GRID_ROWS)
            for col in range(Field.GRID_COLS)
        ][:count]

    def _load_player_shops(self, field, count):
        """apply_load_data() 経由で count 軒ぶんのプレイヤー所有店舗を
        持つ盤面を作る（更新経路4——apply_load_data()——を通す）"""
        field.apply_load_data(
            [
                [col, row, Owner.PLAYER.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]
                for col, row in self._player_shop_positions(count)
            ]
        )

    def test_zero_for_the_empty_field(self):
        """店舗が1軒も無い盤面は player_shop_count が0で、
        is_clear_shop_count_reached も偽であること（Field() の生成直後の
        既定値。例外を返す誤実装も弾く）"""
        field = Field()

        self.assertEqual(0, field.player_shop_count)
        self.assertFalse(field.is_clear_shop_count_reached)

    def test_not_reached_one_shop_below_the_threshold(self):
        """規定店舗数の1つ手前（CLEAR_SHOP_COUNT - 1軒）では到達しないこと"""
        field = Field()
        self._load_player_shops(field, Field.CLEAR_SHOP_COUNT - 1)

        self.assertEqual(Field.CLEAR_SHOP_COUNT - 1, field.player_shop_count)
        self.assertFalse(field.is_clear_shop_count_reached)

    def test_reached_exactly_at_the_threshold(self):
        """規定店舗数ちょうど（CLEAR_SHOP_COUNT軒）で到達すること"""
        field = Field()
        self._load_player_shops(field, Field.CLEAR_SHOP_COUNT)

        self.assertEqual(Field.CLEAR_SHOP_COUNT, field.player_shop_count)
        self.assertTrue(field.is_clear_shop_count_reached)

    def test_reached_above_the_threshold(self):
        """規定店舗数を超えた（CLEAR_SHOP_COUNT + 1軒）状態でも到達している
        こと（`==` ではなく `>=` で判定していることの確認）"""
        field = Field()
        self._load_player_shops(field, Field.CLEAR_SHOP_COUNT + 1)

        self.assertEqual(Field.CLEAR_SHOP_COUNT + 1, field.player_shop_count)
        self.assertTrue(field.is_clear_shop_count_reached)

    def test_npc_owned_shops_are_not_counted(self):
        """店舗の総数が規定店舗数に達していても、その1軒がNPC所有なら
        player_shop_count には数えず到達しないこと（総数と混同する
        誤実装を弾く境界）"""
        field = Field()
        positions = self._player_shop_positions(Field.CLEAR_SHOP_COUNT)
        save_data = [
            [col, row, Owner.PLAYER.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]
            for col, row in positions
        ]
        npc_col, npc_row = positions[-1]
        save_data[-1] = [
            npc_col,
            npc_row,
            Owner.NPC.value,
            Shop.INITIAL_SCALE,
            Shop.BUILD_COST,
        ]
        field.apply_load_data(save_data)

        self.assertEqual(Field.CLEAR_SHOP_COUNT - 1, field.player_shop_count)
        self.assertFalse(field.is_clear_shop_count_reached)

    def test_set_shop_updates_player_shop_count_only_for_the_player_owner(self):
        """更新経路1: set_shop() の直後に player_shop_count が追従すること。
        owner=NPC で置いたときも更新自体は常に行われるが値は増えないこと
        （決定2）も併せて確認する"""
        field = Field()

        field.set_shop(0, 0, Owner.PLAYER)
        self.assertEqual(1, field.player_shop_count)

        field.set_shop(1, 0, Owner.NPC)
        self.assertEqual(1, field.player_shop_count)

    def test_buyout_shop_increments_player_shop_count(self):
        """更新経路2: buyout_shop() の直後に player_shop_count が+1される
        こと（NPC所有店舗がプレイヤー所有へ変わる経路）"""
        field = Field()
        field.set_shop(0, 0, Owner.NPC)
        self.assertEqual(0, field.player_shop_count)

        field.buyout_shop(0, 0)

        self.assertEqual(1, field.player_shop_count)

    def test_selling_a_shop_for_shortfall_decrements_player_shop_count(self):
        """更新経路3: 税金不足時の売却（sell_shops_for_shortfall() 越しの
        _sell_player_shop()）の直後に player_shop_count が-1されること。
        規定店舗数ちょうどの盤面から1軒売れて到達しなくなる、境界そのもの
        （ID-028_subtasks.md「クリアにならない」境界のうち、判定位置を
        売却の前に置く誤実装を弾く境界は本クラスでは扱わず、決算の直後に
        判定するサイクル 028-2 の Red で扱う。本テストは player_shop_count
        の更新経路の確認に留める）"""
        field = Field()
        self._load_player_shops(field, Field.CLEAR_SHOP_COUNT)
        sold_col, sold_row = self._player_shop_positions(Field.CLEAR_SHOP_COUNT)[-1]
        self.test_random_source.set_picked_sell_shop((sold_col, sold_row))

        field.sell_shops_for_shortfall(1)

        self.assertEqual(Field.CLEAR_SHOP_COUNT - 1, field.player_shop_count)
        self.assertFalse(field.is_clear_shop_count_reached)

    def test_apply_load_data_recomputes_player_shop_count(self):
        """更新経路4: apply_load_data() による復元の直後に
        player_shop_count が復元後の盤面に合わせて再算出されること
        （is_all_player_owned とは異なり、復元では更新しない案3を
        適用しない——決定2。復元前の値（set_shop() で1軒建てた状態）を
        引きずらないことを、復元前後で異なる値にして確認する）"""
        field = Field()
        field.set_shop(0, 0, Owner.PLAYER)
        self.assertEqual(1, field.player_shop_count)

        self._load_player_shops(field, Field.CLEAR_SHOP_COUNT)

        self.assertEqual(Field.CLEAR_SHOP_COUNT, field.player_shop_count)
        self.assertTrue(field.is_clear_shop_count_reached)


class TestFieldHasShop(TestParent):
    """マップ上に店舗が1軒でもあるか（所有者を問わない）を Field.has_shop
    プロパティで返す（要件 3.2。ID-025 決定1）。
    **player_shop_count と異なり所有者を問わない**——時間経過処理の開始条件
    （GameCore._start_shop_clocks()）が読む値であり、開始条件は
    「プレイヤー所有店舗が1軒でもあるか」から「マップ上に店舗が1軒でもある
    （所有者を問わない）」へ改まった（ID-025_subtasks.md 決定1）。
    **内部状態を持たず、self._shops の要素数から都度算出する**
    （is_clear_shop_count_reached と同じ、コマンドとクエリの分離。
    ID-025_subtasks.md 決定1）ため、専用の更新経路（_update_...()）は
    持たない。店舗は売却されても NPC 所有になるだけで self._shops のキーが
    消えないため（Field._sell_player_shop()）、**一度真になったら偽へ
    戻らない**ことも本クラスで確認する"""

    def test_false_for_the_empty_field(self):
        """店舗が1軒も無い盤面（Field() の生成直後）は偽であること"""
        field = Field()

        self.assertFalse(field.has_shop)

    def test_true_when_a_player_owned_shop_exists(self):
        """プレイヤー所有店舗が1軒あれば真であること"""
        field = Field()
        field.set_shop(0, 0, Owner.PLAYER)

        self.assertTrue(field.has_shop)

    def test_true_when_only_an_npc_owned_shop_exists(self):
        """NPC所有店舗しか無くても真であること（所有者を問わないことの
        直接確認。player_shop_count と食い違う唯一の境界）"""
        field = Field()
        field.set_shop(0, 0, Owner.NPC)

        self.assertTrue(field.has_shop)

    def test_stays_true_after_selling_the_only_player_shop(self):
        """唯一のプレイヤー所有店舗が税金不足で売却され NPC 所有へ変わった
        （player_shop_count が0に戻った）後も、真のままであること
        （店舗自体はマップから消えない。決定3の前提でもある）"""
        field = Field()
        field.apply_load_data([[0, 0, Owner.PLAYER.value, Shop.INITIAL_SCALE, 100]])
        self.test_random_source.set_picked_sell_shop((0, 0))

        field.sell_shops_for_shortfall(1)

        self.assertEqual(0, field.player_shop_count)
        self.assertTrue(field.has_shop)

    def test_apply_load_data_matches_the_restored_board(self):
        """復元（apply_load_data()）直後も盤面と一致すること。空の盤面を
        経由して復元前後で異なる値になることを、真→偽・偽→真の両方向で
        確認する（is_clear_shop_count_reached の復元テストと同じ考え方）"""
        field = Field()
        field.apply_load_data(
            [[0, 0, Owner.NPC.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]]
        )
        self.assertTrue(field.has_shop)

        field.apply_load_data([])

        self.assertFalse(field.has_shop)


class TestFieldAreaCost(TestParent):
    """地域価格倍率（要件 3.10）が建設費用・増資費用へ効くこと（ID-020 サイクル
    020-1-2）。観測は Field.get_cost(col, row) 越しに行う。
    TestFieldCostAndSales が「区画の状態（空き／プレイヤー所有／NPC所有）で
    どの費用が返るか」を等倍の区画で押さえるのに対し、本クラスは同じ
    get_cost() を**倍率の軸**で押さえる（中心と外周で値が異なること、
    等倍の区画では倍率が乗らないこと）。
    NPC所有店舗の買収費用（get_cost() のもう一方の分岐）は
    TestFieldAreaBuyoutCost で扱うため、本クラスでは確認しない"""

    def test_vacant_plot_area_cost_is_build_cost_times_area_rate(self):
        """空き区画の建設費用が `BUILD_COST × その区画の倍率 // 1000`
        （丸めは切り捨て。決定4）になること。中心（倍率3000）・距離4（倍率2000）・
        外周（倍率1000）で異なる値になることを確認する"""
        field = Field()
        test_cases = [
            ("中心（倍率3000）", 8, 7, Shop.BUILD_COST * 3000 // Shop.AREA_RATE_BASE),
            ("距離4（倍率2000）", 4, 7, Shop.BUILD_COST * 2000 // Shop.AREA_RATE_BASE),
            ("外周（倍率1000）", 0, 7, Shop.BUILD_COST * 1000 // Shop.AREA_RATE_BASE),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_cost(col, row))

    def test_player_shop_area_cost_is_invest_cost_times_scale_and_area_rate(self):
        """プレイヤー所有店舗の増資費用が
        `INVEST_COST × 2^(規模-1) × 倍率 // 1000` になること。中心（倍率3000・
        規模3）で確認し、店舗規模による指数的な増加（ID-007）が、倍率を反映した
        後も維持されていることを押さえる"""
        field = Field()
        field.apply_load_data([[8, 7, Owner.PLAYER.value, 3, 1800]])
        expected = Shop.INVEST_COST * 2**2 * 3000 // Shop.AREA_RATE_BASE
        self.assertEqual(expected, field.get_cost(8, 7))

    def test_area_cost_is_the_unscaled_base_amount_on_edge_plots(self):
        """外周（倍率1000＝等倍）の区画では、費用が倍率を掛ける前の基準額
        （建設費用は Shop.BUILD_COST、増資費用は INVEST_COST × 2^(規模-1)）
        そのものになること——AREA_RATE_BASE が等倍の基準値であり、外周では
        倍率が金額を動かさないことの確認。空き区画（建設費用）・プレイヤー
        所有店舗（増資費用）の両方で確認する"""
        field = Field()
        field.apply_load_data([[0, 7, Owner.PLAYER.value, 5, 2400]])
        test_cases = [
            ("外周・空き区画", 0, 6, Shop.BUILD_COST),
            ("外周・プレイヤー所有店舗（規模5）", 0, 7, Shop.INVEST_COST * 2**4),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_cost(col, row))

    def test_area_cost_follows_the_scale_after_investing(self):
        """増資（invest_shop()）で規模が上がった直後、増資費用（get_cost()）が
        新しい規模を反映すること。Shop.cost は都度算出せず invest() が書き直す
        持ち回り値（負荷対策。Shop.__init__() の docstring 参照）のため、この
        更新を忘れると規模1相当のまま固定される誤実装をここで弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.PLAYER)  # 中心（倍率3000）

        field.invest_shop(8, 7)

        expected = Shop.INVEST_COST * 2**1 * 3000 // Shop.AREA_RATE_BASE
        self.assertEqual(expected, field.get_cost(8, 7))


class TestFieldAreaValue(TestParent):
    """地域価格倍率（要件 3.10）が資産価値へ効くこと（ID-020 サイクル 020-1-3）。
    観測は Field.get_value(col, row) 越しに行う。
    倍率が Shop へ届くこと自体は本クラスを含む金額のテストが間接的に押さえ、
    建設費用・増資費用の式そのものは TestFieldAreaCost が押さえているため、
    本クラスは資産価値が「倍率を反映した建設費用 + Σ 倍率を反映した増資費用」
    という1つの式に、建設・プレイヤー増資・NPC増資・買収の4経路すべてで従う
    ことに集中する（TestShopValueConsistency の倍率版に相当）"""

    def test_build_gives_the_area_adjusted_build_cost_as_the_area_value(self):
        """建設直後(set_shop())の資産価値が、その区画の倍率を反映した
        建設費用(Shop.BUILD_COST × 倍率 // 1000)と一致すること。中心
        (倍率3000)・外周(倍率1000)の両方で確認する"""
        field = Field()
        field.set_shop(8, 7, Owner.PLAYER)  # 中心(倍率3000)
        field.set_shop(0, 7, Owner.NPC)  # 外周(倍率1000)
        test_cases = [
            ("中心", 8, 7, Shop.BUILD_COST * 3000 // Shop.AREA_RATE_BASE),
            ("外周", 0, 7, Shop.BUILD_COST * 1000 // Shop.AREA_RATE_BASE),
        ]
        for case_name, col, row, expected in test_cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(expected, field.get_value(col, row))

    def test_player_invest_adds_the_area_adjusted_invest_cost(self):
        """プレイヤー所有店舗への1回の増資(invest_shop())で、資産価値に
        倍率を反映した増資費用(INVEST_COST × 倍率 // 1000)が加算されること。
        中心(倍率3000)で確認し、加算されない・倍率を掛けない増資費用のまま
        加算される誤実装を弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.PLAYER)  # 中心(倍率3000)
        build_cost = Shop.BUILD_COST * 3000 // Shop.AREA_RATE_BASE
        invest_cost = Shop.INVEST_COST * 3000 // Shop.AREA_RATE_BASE

        field.invest_shop(8, 7)

        self.assertEqual(build_cost + invest_cost, field.get_value(8, 7))

    def test_npc_growth_invest_adds_by_the_same_formula_as_player(self):
        """他店の成長(grow_npc() 経由のNPC増資)が、プレイヤーの増資
        (invest_shop())と同じ式で資産価値を積むこと。同じ区画
        (外周・倍率1000)へ両方の経路で1回だけ増資し、結果が一致することで
        確認する"""
        player_field = Field()
        player_field.set_shop(0, 7, Owner.PLAYER)
        player_field.invest_shop(0, 7)

        npc_field = Field()
        npc_field.set_shop(0, 7, Owner.NPC)
        self.test_random_source.set_picked_npc_growth_target((0, 7))
        npc_field.grow_npc()

        self.assertEqual(player_field.get_value(0, 7), npc_field.get_value(0, 7))

    def test_buyout_does_not_change_the_area_value(self):
        """買収(buyout_shop())は所有者をプレイヤーへ変えるが、資産価値は
        変わらないこと(要件 3.12)。中心(倍率3000)のNPC所有店舗で確認する"""
        field = Field()
        field.set_shop(8, 7, Owner.NPC)  # 中心(倍率3000)
        area_value_before = field.get_value(8, 7)

        field.buyout_shop(8, 7)

        self.assertEqual(Owner.PLAYER, field.get_owner(8, 7))
        self.assertEqual(area_value_before, field.get_value(8, 7))

    def test_area_value_follows_the_build_plus_invests_formula_across_all_four_routes(
        self,
    ):
        """建設・プレイヤー増資・NPC増資・買収の4経路のいずれでも、資産
        価値が「倍率を反映した建設費用 + Σ 倍率を反映した増資費用」という
        1つの式に従うこと(TestShopValueConsistency の倍率版に相当)。
        中心(倍率3000)で規模1→4まで3回増資した店舗を、プレイヤーの建設・
        増資のみで作った場合と、NPCの建設(grow_npc() 経由)・増資を経て
        買収した場合の両方で作り、資産価値が一致することを確認する"""
        expected = Shop.BUILD_COST * 3000 // Shop.AREA_RATE_BASE
        for scale in range(1, 4):
            expected += (
                Shop.INVEST_COST * 2 ** (scale - 1) * 3000 // Shop.AREA_RATE_BASE
            )

        player_field = Field()
        player_field.set_shop(8, 7, Owner.PLAYER)
        for _ in range(3):
            player_field.invest_shop(8, 7)

        npc_field = Field()
        npc_field.set_shop(8, 7, Owner.NPC)
        self.test_random_source.set_picked_npc_growth_target((8, 7))
        for _ in range(3):
            npc_field.grow_npc()
        npc_field.buyout_shop(8, 7)

        self.assertEqual(expected, player_field.get_value(8, 7))
        self.assertEqual(expected, npc_field.get_value(8, 7))

    def test_area_value_is_the_unscaled_base_amount_on_edge_plots(self):
        """外周(倍率1000＝等倍)の区画では、資産価値が倍率を掛ける前の基準額
        (Shop.BUILD_COST + Shop.INVEST_COST = 250)そのものになること——
        AREA_RATE_BASE が等倍の基準値であることの確認。増資後の値で確認する
        （建設直後だけでは、建設費用にしか倍率が乗らない誤実装を見逃す）"""
        field = Field()
        field.set_shop(0, 7, Owner.PLAYER)  # 外周(倍率1000)
        field.invest_shop(0, 7)

        self.assertEqual(Shop.BUILD_COST + Shop.INVEST_COST, field.get_value(0, 7))


class TestFieldAreaBuyoutCost(TestParent):
    """地域価格倍率（要件 3.10）が買収費用へ効くこと（ID-020 サイクル 020-1-4）。
    観測は Field.get_cost(col, row)（NPC所有店舗）越しに行う。資産価値へ倍率が
    乗ることは TestFieldAreaValue が押さえているため、本クラスは買収費用が
    その資産価値**経由で**倍率を反映すること（BUYOUT_RATE 自体は変えない
    こと）に集中する"""

    def test_npc_shop_area_cost_is_area_value_times_buyout_rate(self):
        """NPC所有店舗の買収費用が「資産価値 × BUYOUT_RATE」になること。
        中心(倍率3000)で確認し、倍率を反映しない資産価値がそのまま使われる
        誤実装を弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.NPC)  # 中心(倍率3000)
        area_value = field.get_value(8, 7)

        self.assertEqual(area_value * Shop.BUYOUT_RATE, field.get_cost(8, 7))

    def test_center_npc_shop_has_a_higher_area_buyout_cost_than_edge_of_the_same_scale(
        self,
    ):
        """同じ規模のNPC所有店舗でも、中心(倍率3000)の店舗のほうが外周
        (倍率1000)の店舗より買収費用が高いこと(資産価値を通じて倍率が乗る
        ことの確認)。両者を同じ経路(建設 + grow_npc() 経由の増資2回)で
        規模3まで育てることで、規模の差ではなく位置の差だけが残る"""
        field = Field()
        field.set_shop(8, 7, Owner.NPC)  # 中心
        field.set_shop(0, 7, Owner.NPC)  # 外周
        for pos in ((8, 7), (0, 7)):
            self.test_random_source.set_picked_npc_growth_target(pos)
            for _ in range(2):
                field.grow_npc()

        self.assertEqual(3, field.get_scale(8, 7))
        self.assertEqual(3, field.get_scale(0, 7))
        self.assertGreater(field.get_cost(8, 7), field.get_cost(0, 7))

    def test_buyout_rate_itself_is_unchanged(self):
        """BUYOUT_RATE自体は変えていないこと。外周(倍率1000＝等倍)の設置
        直後のNPC所有店舗では、買収費用が「Shop.BUILD_COST × BUYOUT_RATE」
        そのものになることで確認する(TestFieldAreaCost の
        test_area_cost_is_the_unscaled_base_amount_on_edge_plots と同じ形だが
        NPC所有店舗版)"""
        field = Field()
        field.set_shop(0, 7, Owner.NPC)  # 外周(倍率1000)

        self.assertEqual(Shop.BUILD_COST * Shop.BUYOUT_RATE, field.get_cost(0, 7))

    def test_area_cost_switches_to_the_player_formula_immediately_after_buyout(self):
        """買収（buyout_shop()）の直後、費用（get_cost()）がNPC所有店舗の
        買収費用（資産価値×BUYOUT_RATE）ではなく、プレイヤー所有店舗の
        増資費用（INVEST_COST×2^(規模-1)×倍率//1000）へ即座に切り替わる
        こと。Shop.cost は都度算出せず buyout() が書き直す持ち回り値
        （負荷対策）のため、この更新を忘れると買収費用のまま固定される
        誤実装をここで弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.NPC)  # 中心（倍率3000）

        field.buyout_shop(8, 7)

        expected = Shop.INVEST_COST * 3000 // Shop.AREA_RATE_BASE  # 規模1
        self.assertEqual(expected, field.get_cost(8, 7))


class TestFieldAreaSales(TestParent):
    """中心売上倍率（地域価格倍率の指数乗。要件 3.10）が売上額へ効くこと
    （ID-020 サイクル 020-1-5）。観測は Field.get_sales(col, row) 越しに行う。
    地域価格倍率そのものの算出は費用側のテストが押さえているため、本クラスは
    中心売上倍率と、それを反映した売上額の式に集中する。
    TestFieldCostAndSales が「区画の状態でどの売上額が返るか」を等倍の区画で
    押さえるのに対し、本クラスは同じ get_sales() を**倍率の軸**で押さえる"""

    def test_center_sales_multiplier_matches_the_requirement_table_at_exponent_2(self):
        """中心売上倍率(地域価格倍率の指数乗)が、要件3.10の対応表
        (1.0→1.00/1.5→2.25/2.0→4.00/2.5→6.25/3.0→9.00)どおりであること。
        規模1(基準額SALES_AMOUNTそのまま)の店舗で、盤面上に実在する5つの
        倍率(1000/1500/2000/2500/3000)を代表点として確認する。指数は
        調整対象の定数(Shop.CENTER_SALES_EXPONENT)のため、対応表そのものを
        検証する本テストだけは指数2を明示的に与える(他のテストは定数から
        読む。ID-020_subtasks.md 決定6)"""
        field = Field()
        field.set_shop(0, 7, Owner.PLAYER)  # 倍率1000(距離8)
        field.set_shop(8, 1, Owner.PLAYER)  # 倍率1500(距離6)
        field.set_shop(4, 7, Owner.PLAYER)  # 倍率2000(距離4)
        field.set_shop(8, 5, Owner.PLAYER)  # 倍率2500(距離2)
        field.set_shop(8, 7, Owner.PLAYER)  # 倍率3000(距離0)
        test_cases = [
            ("倍率1.0→中心売上倍率1.00", 0, 7, 50),
            ("倍率1.5→中心売上倍率2.25", 8, 1, 112),
            ("倍率2.0→中心売上倍率4.00", 4, 7, 200),
            ("倍率2.5→中心売上倍率6.25", 8, 5, 312),
            ("倍率3.0→中心売上倍率9.00", 8, 7, 450),
        ]
        with patch.object(Shop, "CENTER_SALES_EXPONENT", 2):
            for case_name, col, row, expected in test_cases:
                with self.subTest(case_name=case_name):
                    self.assertEqual(expected, field.get_sales(col, row))

    def test_area_sales_is_sales_amount_times_scale_factor_times_center_sales_multiplier(
        self,
    ):
        """売上額が `SALES_AMOUNT × 2^(規模-1) × 倍率^指数 // 1000^指数` に
        なること。中心(倍率3000)・規模5の店舗で確認し、店舗規模による
        指数的な増加(ID-010)が、中心売上倍率を反映した後も維持されている
        ことを押さえる(指数は定数から読む)"""
        field = Field()
        field.apply_load_data([[8, 7, Owner.PLAYER.value, 5, 100000]])
        exponent = Shop.CENTER_SALES_EXPONENT
        expected = (
            Shop.SALES_AMOUNT * 2**4 * 3000**exponent // Shop.AREA_RATE_BASE**exponent
        )
        self.assertEqual(expected, field.get_sales(8, 7))

    def test_center_shop_earns_center_sales_multiplier_times_the_edge_shop_of_the_same_scale(
        self,
    ):
        """同じ規模でも、中心(倍率3000)の店舗は外周(倍率1000)の店舗の
        中心売上倍率倍(指数を定数から読む。既定は9倍)の売上額になること
        (費用が3倍に対して売上が指数倍、という中心売上優位の核心)"""
        field = Field()
        field.apply_load_data(
            [
                [8, 7, Owner.PLAYER.value, 5, 100000],  # 中心
                [0, 7, Owner.PLAYER.value, 5, 100000],  # 外周
            ]
        )
        exponent = Shop.CENTER_SALES_EXPONENT
        center_sales_multiplier = 3000**exponent // Shop.AREA_RATE_BASE**exponent

        self.assertEqual(
            field.get_sales(0, 7) * center_sales_multiplier, field.get_sales(8, 7)
        )

    def test_area_sales_is_the_unscaled_base_amount_on_edge_plots(self):
        """外周(倍率1000＝等倍)の区画では、売上額が中心売上倍率を掛ける前の
        基準額(SALES_AMOUNT × 2^(規模-1))そのものになること——AREA_RATE_BASE
        が等倍の基準値であることの確認。規模7で確認する(規模1では
        2^(規模-1)=1 となり、規模の項の誤りを見逃す)"""
        field = Field()
        field.apply_load_data([[0, 7, Owner.PLAYER.value, 7, 5000]])

        self.assertEqual(Shop.SALES_AMOUNT * 2**6, field.get_sales(0, 7))

    def test_vacant_plot_area_sales_is_zero(self):
        """空き区画の売上額が0のままであること。中心(倍率3000)の空き区画で
        確認する——倍率が乗る区画であっても店舗が無ければ売上は発生しない"""
        field = Field()

        self.assertEqual(0, field.get_sales(8, 7))

    def test_area_sales_follows_the_scale_after_investing(self):
        """増資（invest_shop()）で規模が上がった直後、売上額（get_sales()）が
        新しい規模を反映すること。Shop.sales は都度算出せず invest() が
        書き直す持ち回り値（負荷対策。Shop.__init__() の docstring 参照）の
        ため、この更新を忘れると規模1相当のまま固定される誤実装をここで弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.PLAYER)  # 中心（倍率3000）

        field.invest_shop(8, 7)

        expected = Shop.SALES_AMOUNT * 2**1 * 3000**2 // Shop.AREA_RATE_BASE**2
        self.assertEqual(expected, field.get_sales(8, 7))


class TestFieldAreaTotalTax(TestParent):
    """地域価格倍率（要件 3.10）が支払い予定税額へ効くこと（ID-020 サイクル
    020-1-6）。観測は Field.total_tax() 越しに行う。
    土地税は「プレイヤー所有店舗のある各区画の 地価 × その区画の地域価格倍率
    // 1000」の合計（区画ごとに丸めてから合計。決定4）、資産税は「プレイヤー
    所有店舗の資産価値総額 × 税率(5%)」の切り捨てで、total_tax() はその合計
    のみを返す（内訳は非公開）。
    TestFieldTotalTax が税額の骨格（空盤面・NPC所有のみ・地価0・切り捨て・
    所有者の混在）を等倍の区画で押さえるのに対し、本クラスは**倍率の軸**
    だけを足す。等倍でも成立するケース（空盤面の0、NPC所有のみの0、地価0で
    資産税のみ）は TestFieldTotalTax が既に持つため、本クラスでは重ねない。
    旧 TestFieldTotalTax と同じく、合計は足し算のため一方が過大でもう一方が
    過小な誤実装は打ち消し合い得る。期待値は数値で書き下ろし、実装と同じ式を
    テスト側で繰り返さない(ID-013で確立した書き方)"""

    def test_asset_tax_follows_the_area_adjusted_asset_value(self):
        """資産税が、倍率を反映した資産価値へ追従すること。中心(倍率3000)の
        プレイヤー所有店舗1軒(規模1。資産価値300)で確認する——地価
        (300 // 270 = 1)×倍率(1×3000//1000 = 3)の土地税3と、資産価値300を
        使う資産税(300×5//100 = 15)を合わせた18になる。倍率を反映しない
        資産価値(100)のままなら地価0・土地税0・資産税5の合計5にとどまる
        誤実装を弾く"""
        field = Field()
        field.set_shop(8, 7, Owner.PLAYER)  # 中心(倍率3000)

        self.assertEqual(18, field.total_tax())

    def test_land_tax_is_sum_of_land_price_times_area_rate_for_player_shops(self):
        """土地税が「プレイヤー所有店舗のある各区画の 地価 × その区画の
        地域価格倍率 // 1000」の合計になること(区画ごとに丸めてから合計。
        決定4)。同じ規模・同じ資産価値(76,750)のプレイヤー所有店舗を中心と
        外周に1軒ずつ置き、資産税を揃えたうえで土地税だけに位置の差が出る
        盤面にする。対象外であることを示すNPC所有店舗(外周・資産価値100)を
        1軒混ぜる。
        総額 = 76,750 + 76,750 + 100 = 153,600、地価 = 153,600 // 270 = 568、
        土地税 = 中心分(568×3000//1000 = 1,704) + 外周分
        (568×1000//1000 = 568) = 2,272(NPC所有分は対象外)、
        プレイヤー所有の資産価値総額 = 153,500、
        資産税 = 153,500×5//100 = 7,675、
        支払い予定税額 = 2,272 + 7,675 = 9,947。
        土地税が旧式(プレイヤー所有店舗数×地価 = 2×568 = 1,136)のままの
        誤実装、区画の倍率ではなく一律に中心の倍率を掛ける誤実装
        (1,704×2 = 3,408)、土地税が全店舗を数える誤実装のいずれとも異なる
        値になり、この1件で弁別できる"""
        field = Field()
        field.apply_load_data(
            [
                [8, 7, Owner.PLAYER.value, Shop.SCALE_MAX, 76750],  # 中心
                [0, 7, Owner.PLAYER.value, Shop.SCALE_MAX, 76750],  # 外周
                [17, 0, Owner.NPC.value, Shop.INITIAL_SCALE, 100],  # 外周
            ]
        )

        self.assertEqual(9947, field.total_tax())

    def test_matches_the_traditional_formula_when_all_area_rates_are_1_0(self):
        """すべての区画の倍率が1.0のとき、土地税が従来式(プレイヤー所有
        店舗数 × 地価)と一致すること(要件3.8が明記する性質)。地域価格倍率の
        算出(Field._area_rate())をすべて等倍(Shop.AREA_RATE_BASE)を返すよう
        差し替えて盤面を作ることで確認する(土地税は Field が座標から倍率を
        都度求めるため、店舗が保持する倍率とは無関係にこの差し替えが効く)。
        プレイヤー所有2軒(いずれも規模2・資産価値250)とNPC所有1軒
        (規模1・資産価値100)の盤面で、
        総額 = 250 + 250 + 100 = 600、地価 = 600 // 270 = 2、
        **区画ごとの合計による土地税** = 2×1000//1000 + 2×1000//1000 = 4 は
        **従来式**(プレイヤー所有店舗数2 × 地価2 = 4)と一致し、
        プレイヤー所有の資産価値総額 = 500、資産税 = 500×5//100 = 25、
        支払い予定税額 = 4 + 25 = 29 になる。
        区画ごとに丸めずに合計してから丸める誤実装も、等倍では同じ4を返す
        ため本テストでは弾けない——丸めの位置は
        test_land_tax_is_sum_of_land_price_times_area_rate_for_player_shops
        の中心・外周が混在する盤面が押さえる"""
        field = Field()
        with patch.object(field, "_area_rate", return_value=Shop.AREA_RATE_BASE):
            field.set_shop(0, 0, Owner.PLAYER)
            field.set_shop(1, 0, Owner.PLAYER)
            field.set_shop(2, 0, Owner.NPC)
            field.invest_shop(0, 0)
            field.invest_shop(1, 0)

            self.assertEqual(29, field.total_tax())

    def test_area_total_tax_increases_as_the_player_shop_moves_toward_the_center(self):
        """中心に店舗を持つほど支払い予定税額が高くなること。外周
        (倍率1000)・距離4(倍率2000)・中心(倍率3000)のいずれも規模1の
        プレイヤー所有店舗1軒のみの盤面で、支払い予定税額が距離が縮むほど
        単調に増えることを確認する(外周5 < 距離4の10 < 中心18)"""
        edge_field = Field()
        edge_field.set_shop(0, 7, Owner.PLAYER)  # 外周(倍率1000)

        mid_field = Field()
        mid_field.set_shop(4, 7, Owner.PLAYER)  # 距離4(倍率2000)

        center_field = Field()
        center_field.set_shop(8, 7, Owner.PLAYER)  # 中心(倍率3000)

        self.assertLess(edge_field.total_tax(), mid_field.total_tax())
        self.assertLess(mid_field.total_tax(), center_field.total_tax())


class TestFieldMinAcquisitionCost(TestParent):
    """マップ上でいま取得できる区画の費用のうち最も安いもの（要件 3.15。
    ID-024 サイクル 024-1）。対象は「空き区画の建設費用」と「NPC所有店舗の
    買収費用」で、いずれも get_cost() が返す値（地域価格倍率を反映済み）を
    そのまま読む——本クラスは新しい金額の式を1つも足さない
    (ID-024_subtasks.md 決定3)。
    **公開されるため直接のテストを持つ**（決定1）。資金との比較（境界3点）は
    GameCore 側のテスト（サイクル 024-2）が担うため、本クラスは
    「最小値がいくつか・どちらから来るか」だけに集中する。
    金額の期待値は Shop.BUILD_COST / Field.AREA_RATE_EDGE /
    Shop.AREA_RATE_BASE / Shop.BUYOUT_RATE / Shop.INVEST_COST を参照する式で
    書き、数値を直書きしない(ID-020_subtasks.md「数値直書きの3クラス」を
    増やさないため)"""

    def _fill_all_plots_with_npc_shops(self, field):
        """全 GRID_PLOT_COUNT 区画を、二重ループで NPC 所有店舗で埋める
        （空き区画を1つも残さない盤面。テスト設計の注意3）。set_shop() を
        そのまま使うため、各区画の資産価値は地域価格倍率をそのまま反映した
        自然な値（Shop.BUILD_COST × その区画の倍率 // AREA_RATE_BASE）になる"""
        for row in range(Field.GRID_ROWS):
            for col in range(Field.GRID_COLS):
                field.set_shop(col, row, Owner.NPC)

    def _npc_full_board_save_data(self, cheapest_pos, cheapest_value, other_value):
        """全 GRID_PLOT_COUNT 区画ぶんの NPC 所有店舗の保存データを二重ループで
        組む。cheapest_pos の区画だけ cheapest_value、他はすべて other_value を
        資産価値として持つ（規模はいずれも INITIAL_SCALE）。増資（invest_shop()）
        の前後で最小取得費用がどう動くかを、地域価格倍率によるタイ（同じ距離の
        区画が複数ある。外周は列0・列17の全行が該当）に左右されずに固定するため、
        _fill_all_plots_with_npc_shops() の自然な値ではなく明示的な値を使う"""
        return [
            [
                col,
                row,
                Owner.NPC.value,
                Shop.INITIAL_SCALE,
                cheapest_value if (col, row) == cheapest_pos else other_value,
            ]
            for row in range(Field.GRID_ROWS)
            for col in range(Field.GRID_COLS)
        ]

    def test_min_cost_comes_from_the_cheapest_vacant_plot_on_the_default_board(self):
        """既定の盤面（生成直後。店舗が1軒も無い）では、最小取得費用が最も
        安い空き区画の建設費用（最大距離の区画＝等倍。Shop.BUILD_COST ×
        Field.AREA_RATE_EDGE // Shop.AREA_RATE_BASE）になること"""
        field = Field()

        expected = Shop.BUILD_COST * Field.AREA_RATE_EDGE // Shop.AREA_RATE_BASE
        self.assertEqual(expected, field.min_acquisition_cost())

    def test_min_cost_comes_from_the_cheapest_npc_buyout_when_no_plot_is_vacant(self):
        """空き区画を残さない盤面（全 GRID_PLOT_COUNT 区画をNPC所有店舗で
        埋める）では、最小取得費用がNPC所有店舗の買収費用（最も安いのは
        最大距離の区画。資産価値 = Shop.BUILD_COST × Field.AREA_RATE_EDGE //
        Shop.AREA_RATE_BASE、買収費用はその2倍＝ Shop.BUYOUT_RATE 倍）から
        来ること"""
        field = Field()
        self._fill_all_plots_with_npc_shops(field)

        cheapest_value = Shop.BUILD_COST * Field.AREA_RATE_EDGE // Shop.AREA_RATE_BASE
        expected = cheapest_value * Shop.BUYOUT_RATE
        self.assertEqual(expected, field.min_acquisition_cost())

    def test_investing_in_the_cheapest_npc_shop_raises_the_min_cost(self):
        """空き区画を残さない盤面で最も安いNPC所有店舗を増資すると、その
        買収費用（資産価値の2倍）が上がり、最小取得費用も上がること（要件
        「他店の建設・増資によって最小取得費用が変化する」）。空き区画が
        1つでも残っていると最小は空き区画側に固定されるため、この検証は
        全区画がNPC所有の盤面でしか作れない。
        増資前は最も安い区画（外周・倍率1000）の買収費用が最小取得費用と
        一致し、増資後はその区画の資産価値へ増資費用（Shop.INVEST_COST ×
        規模1相当 × 倍率1000 // AREA_RATE_BASE。丸めは効かない）が加算された
        値が新しい最小取得費用になること（他の区画の買収費用は増資後も
        なお上回るよう、他区画の資産価値を十分大きく設定する）"""
        field = Field()
        cheapest_pos = (0, 7)  # 外周（倍率1000）
        cheapest_value = Shop.BUILD_COST
        other_value = Shop.BUILD_COST * 100
        field.apply_load_data(
            self._npc_full_board_save_data(cheapest_pos, cheapest_value, other_value)
        )
        cost_before = field.min_acquisition_cost()
        self.assertEqual(cheapest_value * Shop.BUYOUT_RATE, cost_before)

        field.invest_shop(*cheapest_pos)

        invested_value = (
            cheapest_value
            + Shop.INVEST_COST * Field.AREA_RATE_EDGE // Shop.AREA_RATE_BASE
        )
        expected_after = invested_value * Shop.BUYOUT_RATE
        cost_after = field.min_acquisition_cost()
        self.assertEqual(expected_after, cost_after)
        self.assertGreater(cost_after, cost_before)

    def test_scale_max_npc_shop_is_included_as_a_candidate(self):
        """規模が上限（Shop.SCALE_MAX）のNPC所有店舗も買収費用の対象に
        含まれること（買収に規模上限は無い。要件 3.7）。
        _list_npc_growth_targets() は規模が上限のNPC所有店舗を対象から
        除外するが、本メソッドはその絞り込みを流用しないため除外されない。
        規模上限のNPC所有店舗の買収費用が、盤面のどの空き区画の建設費用
        よりも安くなるよう資産価値を小さく設定することで、誤って除外する
        実装ではこの安い方が見つからず、より高い空き区画側の建設費用が
        返ってしまう——この1件で弁別する"""
        field = Field()
        field.apply_load_data(
            [[0, 7, Owner.NPC.value, Shop.SCALE_MAX, 10]]  # 外周・規模上限
        )

        expected = 10 * Shop.BUYOUT_RATE
        vacant_cost = Shop.BUILD_COST * Field.AREA_RATE_EDGE // Shop.AREA_RATE_BASE
        self.assertLess(expected, vacant_cost)
        self.assertEqual(expected, field.min_acquisition_cost())

    def test_none_when_every_plot_is_player_owned(self):
        """全区画がプレイヤー所有の盤面では取得できる区画が1つも無いため、
        min_acquisition_cost() が None を返すこと。0を返さないのは、0が
        「取得費用0で再開できる」という誤った意味を持ってしまうため
        （get_value() / get_cost() が値の不在を None で表す既存の型に
        合わせる。テスト設計の注意4）"""
        field = Field()
        field.apply_load_data(
            [
                [col, row, Owner.PLAYER.value, Shop.INITIAL_SCALE, Shop.BUILD_COST]
                for row in range(Field.GRID_ROWS)
                for col in range(Field.GRID_COLS)
            ]
        )

        self.assertIsNone(field.min_acquisition_cost())
