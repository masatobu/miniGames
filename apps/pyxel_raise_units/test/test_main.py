import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))
from main import (  # pylint: disable=C0413
    IView,
    IInput,
    IMovableView,
    GameCore,
    PyxelController,
)
from unit import Unit  # pylint: disable=C0413
from attack import Attack  # pylint: disable=C0413
from movable import Direct, Movable, Side, UnitType  # pylint: disable=C0413
from force import Force, EnemyStrategy  # pylint: disable=C0413
from button import Button  # pylint: disable=C0413


class TestView(IView):
    def __init__(self):
        self.call_params = []
        self._frame_count = 0

    def draw_text(self, x, y, text):
        self.call_params.append(("draw_text", x, y, text))

    def draw_rect(self, x, y, w, h, color):
        self.call_params.append(("draw_rect", x, y, w, h, color))

    def draw_rectb(self, x, y, w, h, color):
        self.call_params.append(("draw_rectb", x, y, w, h, color))

    def draw_image(self, x, y, img, u, v, w, h, colkey=None):
        self.call_params.append(("draw_image", x, y, img, u, v, w, h, colkey))

    def clear(self, color):
        self.call_params.append(("clear", color))

    def get_frame(self):
        return self._frame_count

    def set_frame(self, frame):
        """テスト用: フレームカウントを設定"""
        self._frame_count = frame

    def get_call_params(self):
        return self.call_params


class TestMovableView(IMovableView):
    """IMovableViewのモック実装（テスト用）"""

    def __init__(self):
        self.call_params = []

    def draw_unit(self, x, y, side, face, direct, is_damaged, unit_type):
        self.call_params.append(
            ("draw_unit", x, y, side, face, direct, is_damaged, unit_type)
        )

    def draw_attack(self, x, y, side, progress, unit_type):
        self.call_params.append(("draw_attack", x, y, side, progress, unit_type))

    def get_call_params(self):
        return self.call_params


class TestInput(IInput):
    """IInputのテスト用実装"""

    def __init__(self):
        self._is_click = False
        self._mouse_x = 0
        self._mouse_y = 0

    def is_click(self):
        return self._is_click

    @property
    def mouse_x(self):
        return self._mouse_x

    @property
    def mouse_y(self):
        return self._mouse_y

    def set_click(self, value):
        """テスト用: クリック状態を設定"""
        self._is_click = value

    def set_mouse(self, x, y):
        """テスト用: マウス座標を設定"""
        self._mouse_x = x
        self._mouse_y = y


class TestParent(unittest.TestCase):
    # ボタン定数: 画面下部、3ボタン配置（各44px幅、隙間3px）
    SCREEN_W, SCREEN_H = 150, 200
    BUTTON_W = 42  # 各ボタン幅: 合計132 = 3×42 + 2×3
    BUTTON_H = 12
    BUTTON_Y = 168  # 画面下部（共通）
    LOW_BUTTON_X = 9  # = (150 - 132) // 2
    MID_BUTTON_X = 54  # = 9 + 42 + 3
    UPP_BUTTON_X = 99  # = 54 + 42 + 3
    # ポップアップ定数: 画面中央配置
    POPUP_W, POPUP_H = 130, 30
    POPUP_X = (SCREEN_W - POPUP_W) // 2  # = 10
    POPUP_Y = (SCREEN_H - POPUP_H) // 2  # = 85

    @staticmethod
    def expected_coin_calls(player_fund, enemy_fund):
        """軍資金に対応するコイン描画呼び出しリストを生成するヘルパー"""
        calls = []
        for fund, is_player in [(player_fund, True), (enemy_fund, False)]:
            coin_count = min(fund // GameCore.FUND_PER_COIN, GameCore.COIN_MAX)
            for i in range(coin_count):
                col = i // GameCore.COIN_MAX_PER_COL
                row = i % GameCore.COIN_MAX_PER_COL
                y = GameCore.COIN_BOTTOM_Y - row * GameCore.COIN_STEP
                if is_player:
                    x = col * GameCore.COIN_STEP
                else:
                    x = 150 - GameCore.COIN_SIZE - col * GameCore.COIN_STEP
                calls.append(("draw_image", x, y, 0, 0, 8, 4, 4, None))
        return calls

    @staticmethod
    def expected_spawn_button_calls(core):
        """GameCore の Button インスタンスからアイコン描画＋コストシンボル描画の呼び出しリストを生成するヘルパー"""
        calls = []
        for button, unit_type in [
            (core.low_button, UnitType.LOWER),
            (core.mid_button, UnitType.MIDDLE),
            (core.upp_button, UnitType.UPPER),
        ]:
            u, v = button.icon.value
            icon_x = button.x + (button.width - Button.ICON_SIZE) // 2
            icon_y = button.y + (button.height - Button.ICON_SIZE) // 2
            calls += [
                ("draw_rect", button.x, button.y, button.width, button.height, Button.NORMAL_BG_COLOR),
                ("draw_rectb", button.x, button.y, button.width, button.height, 7),
                (
                    "draw_image",
                    icon_x,
                    icon_y,
                    0,
                    u,
                    v,
                    Button.ICON_SIZE,
                    Button.ICON_SIZE,
                    0,
                ),
            ]
            count = Force.SPAWN_COST[unit_type] // GameCore.FUND_PER_COIN
            symbol_x = button.x + (button.width - GameCore.SYMBOL_SIZE) // 2
            for i in range(count):
                y = button.y - GameCore.SYMBOL_SIZE - 1 - i * GameCore.SYMBOL_STEP
                calls.append(
                    (
                        "draw_image",
                        symbol_x,
                        y,
                        0,
                        GameCore.SYMBOL_U,
                        GameCore.SYMBOL_V,
                        GameCore.SYMBOL_SIZE,
                        GameCore.SYMBOL_SIZE,
                        None,
                    )
                )
        return calls

    @staticmethod
    def expected_hp_bar_calls(player_ratio, enemy_ratio):
        """HPバー描画呼び出しリストを生成するヘルパー（PLAYER先、ENEMY後）"""
        calls = []
        for bar_x, ratio, fg_color in [
            (GameCore.HP_BAR_PLAYER_X, player_ratio, GameCore.HP_BAR_PLAYER_COLOR),
            (GameCore.HP_BAR_ENEMY_X, enemy_ratio, GameCore.HP_BAR_ENEMY_COLOR),
        ]:
            bar_bottom_y = GameCore.UNIT_Y - GameCore.HP_BAR_MARGIN
            fill_h = round(GameCore.HP_BAR_MAX_H * ratio)
            calls.append(
                (
                    "draw_rect",
                    bar_x,
                    bar_bottom_y - GameCore.HP_BAR_MAX_H,
                    GameCore.HP_BAR_W,
                    GameCore.HP_BAR_MAX_H,
                    GameCore.HP_BAR_BG_COLOR,
                )
            )
            calls.append(
                (
                    "draw_rect",
                    bar_x,
                    bar_bottom_y - fill_h,
                    GameCore.HP_BAR_W,
                    fill_h,
                    fg_color,
                )
            )
        return calls

    @staticmethod
    def _destroy_base(core, side):
        """テスト用: 指定サイドの拠点ユニットを除去してゲーム終了を再現"""
        core.force[side]._units = [  # pylint: disable=W0212
            u
            for u in core.force[side]._units  # pylint: disable=W0212
            if u.unit_type != UnitType.BASE
        ]

    def setUp(self):
        self.test_view = TestView()
        self.test_movable_view = TestMovableView()
        self.test_input = TestInput()
        self.patcher_view = patch("main.PyxelView.create", return_value=self.test_view)
        self.patcher_movable_view = patch(
            "main.PyxelMovableView.create", return_value=self.test_movable_view
        )
        self.patcher_input = patch(
            "main.PyxelInput.create", return_value=self.test_input
        )
        self.mock_view = self.patcher_view.start()
        self.mock_movable_view = self.patcher_movable_view.start()
        self.mock_input = self.patcher_input.start()

    def tearDown(self):
        self.patcher_view.stop()
        self.patcher_movable_view.stop()
        self.patcher_input.stop()


class TestGameCore(TestParent):
    def test_game_core_update_moves_units(self):
        """GameCore.update() はユニットを移動させる"""
        core = GameCore()
        player = Unit(Side.PLAYER, UnitType.MIDDLE)
        core.force[Side.PLAYER]._units.append(player)  # pylint: disable=W0212

        start_x = player.x
        # SPEED=0.5 なので、2回更新で1ピクセル移動
        core.update()
        core.update()
        self.assertNotEqual(player.x, start_x)  # 移動した
        self.assertEqual(player.direct, Direct.RIGHT)  # 右向き

    def test_game_core_accepts_enemy_strategy_param(self):
        """GameCore(enemy_strategy=...) で敵軍 Force の戦略が設定される"""
        for strategy in EnemyStrategy:
            with self.subTest(strategy=strategy):
                core = GameCore(enemy_strategy=strategy)
                self.assertEqual(core.enemy_strategy, strategy)

    def test_game_core_enemy_strategy_default_is_random(self):
        """GameCore() 引数なしのとき enemy_strategy は EnemyStrategy の何れかになる"""
        core = GameCore()
        self.assertIn(core.enemy_strategy, list(EnemyStrategy))

    def test_game_core_update_start_attack(self):
        """GameCore.update()でユニットが攻撃を開始する"""
        core = GameCore()
        for side, x in [(Side.PLAYER, 100), (Side.ENEMY, 115)]:
            unit = Unit(side, UnitType.MIDDLE)
            unit._x = x  # pylint: disable=W0212
            core.force[side]._units.append(unit)  # pylint: disable=W0212

        core.update()
        core.update()
        for force in core.force.values():
            for unit in force.units:
                if unit.unit_type == UnitType.MIDDLE:
                    self.assertEqual(
                        unit.direct, Direct.NEUTRAL
                    )  # 攻撃状態になっている
                    max_hp = Unit.TYPE_PARAMS[UnitType.MIDDLE].hp
                    self.assertEqual(unit.hp, max_hp - 1)  # 被弾している

        # 描画確認 - 攻撃後の状態が正しく描画される（ユニットが攻撃エフェクトより先）
        self.test_movable_view.call_params = []
        core.draw()
        unit_range = Unit.TYPE_PARAMS[UnitType.MIDDLE].range
        attack_range = unit_range - Movable.TILE_SIZE + 1
        attack_progress = Attack.SPEED / attack_range
        base_player = (
            "draw_unit",
            0,
            GameCore.UNIT_Y,
            Side.PLAYER,
            Direct.RIGHT,
            Direct.RIGHT,
            False,
            UnitType.BASE,
        )
        base_enemy = (
            "draw_unit",
            142,
            GameCore.UNIT_Y,
            Side.ENEMY,
            Direct.LEFT,
            Direct.LEFT,
            False,
            UnitType.BASE,
        )
        # 逆順描画: 各 Force で [BASE, MIDDLE] → reversed → [MIDDLE, BASE]
        self.assertEqual(
            self.test_movable_view.get_call_params(),
            [
                (
                    "draw_unit",
                    100,
                    GameCore.UNIT_Y,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.NEUTRAL,
                    True,
                    UnitType.MIDDLE,
                ),
                base_player,
                (
                    "draw_attack",
                    110,
                    GameCore.UNIT_Y,
                    Side.PLAYER,
                    attack_progress,
                    UnitType.MIDDLE,
                ),
                (
                    "draw_unit",
                    115,
                    GameCore.UNIT_Y,
                    Side.ENEMY,
                    Direct.LEFT,
                    Direct.NEUTRAL,
                    True,
                    UnitType.MIDDLE,
                ),
                base_enemy,
                (
                    "draw_attack",
                    105,
                    GameCore.UNIT_Y,
                    Side.ENEMY,
                    attack_progress,
                    UnitType.MIDDLE,
                ),
            ],
        )


class TestUnitDrawing(TestParent):
    """ユニット描画のふるまいテスト"""

    def test_draw_draws_units(self):
        """GameCore.draw() は自軍・敵軍のユニットを描画する
        描画順序: 各 Force を逆順に描画するため、BASE（先頭登録）が最後＝最前面になる"""
        # Arrange
        core = GameCore()
        player_unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        player_unit._x = 50  # pylint: disable=W0212
        core.force[Side.PLAYER]._units.append(player_unit)  # pylint: disable=W0212
        enemy_unit = Unit(Side.ENEMY, UnitType.MIDDLE)
        enemy_unit._x = 100  # pylint: disable=W0212
        core.force[Side.ENEMY]._units.append(enemy_unit)  # pylint: disable=W0212
        self.test_view.call_params = []
        self.test_movable_view.call_params = []

        # Act
        core.draw()

        # Assert - 描画フローの検証: 画面クリア → HPバー → fund → ボタン描画
        expected_view = (
            [("clear", 0)]
            + self.expected_hp_bar_calls(1.0, 1.0)
            + self.expected_coin_calls(
                core.force[Side.PLAYER].fund, core.force[Side.ENEMY].fund
            )
            + self.expected_spawn_button_calls(core)
        )
        self.assertEqual(self.test_view.get_call_params(), expected_view)
        # 逆順描画: 各 Force で [BASE, MIDDLE] → reversed → [MIDDLE, BASE]
        self.assertEqual(
            self.test_movable_view.get_call_params(),
            [
                (
                    "draw_unit",
                    50,
                    GameCore.UNIT_Y,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.RIGHT,
                    False,
                    UnitType.MIDDLE,
                ),
                (
                    "draw_unit",
                    0,
                    GameCore.UNIT_Y,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.RIGHT,
                    False,
                    UnitType.BASE,
                ),
                (
                    "draw_unit",
                    100,
                    GameCore.UNIT_Y,
                    Side.ENEMY,
                    Direct.LEFT,
                    Direct.LEFT,
                    False,
                    UnitType.MIDDLE,
                ),
                (
                    "draw_unit",
                    142,
                    GameCore.UNIT_Y,
                    Side.ENEMY,
                    Direct.LEFT,
                    Direct.LEFT,
                    False,
                    UnitType.BASE,
                ),
            ],
        )

    def test_draw_damaged_unit(self):
        """被弾中のユニットはis_damaged=Trueで描画される"""
        # Arrange
        core = GameCore()
        for side in Side:
            core.force[side]._units = []  # pylint: disable=W0212
        unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        unit._x = 50  # pylint: disable=W0212
        unit.take_damage()  # 被弾状態にする
        core.force[Side.PLAYER]._units.append(unit)  # pylint: disable=W0212
        self.test_view.call_params = []
        self.test_movable_view.call_params = []

        # Act
        core.draw()

        # Assert - is_damaged=Trueで呼ばれる
        self.assertEqual(
            self.test_movable_view.get_call_params(),
            [
                (
                    "draw_unit",
                    50,
                    GameCore.UNIT_Y,
                    Side.PLAYER,
                    Direct.RIGHT,
                    Direct.RIGHT,
                    True,
                    UnitType.MIDDLE,
                )
            ],
        )


class TestPyxelController(unittest.TestCase):
    def setUp(self):
        self.mock_pyxel = MagicMock()
        self.patcher_pyxel = patch.dict("sys.modules", {"pyxel": self.mock_pyxel})
        self.patcher_view = patch("main.PyxelView.create", return_value=TestView())
        self.patcher_movable_view = patch(
            "main.PyxelMovableView.create", return_value=TestMovableView()
        )
        self.patcher_input = patch("main.PyxelInput.create", return_value=TestInput())
        self.patcher_pyxel.start()
        self.patcher_view.start()
        self.patcher_movable_view.start()
        self.patcher_input.start()

    def tearDown(self):
        self.patcher_input.stop()
        self.patcher_movable_view.stop()
        self.patcher_view.stop()
        self.patcher_pyxel.stop()

    def test_screen_size(self):
        """画面サイズは150×200px"""
        PyxelController()

        # pyxel.init が正しいサイズで呼ばれたことを検証
        self.mock_pyxel.init.assert_called_once()
        call_args = self.mock_pyxel.init.call_args
        # 最初の2つの引数（width, height）を検証
        self.assertEqual(call_args[0][0], 150)  # width
        self.assertEqual(call_args[0][1], 200)  # height

    def test_update_recreates_game_core_when_needs_reset(self):
        """needs_reset()がTrueのときGameCoreを再作成する"""
        controller = PyxelController()
        controller.game_core._needs_reset = True  # pylint: disable=W0212
        old_game_core = controller.game_core

        controller.update()

        # GameCoreが新しいインスタンスに置き換えられた
        self.assertIsNot(controller.game_core, old_game_core)
        # 新しいGameCoreのneeds_resetはFalse（初期状態）
        self.assertFalse(controller.game_core.needs_reset())

    def test_update_enemy_strategy_on_retry(self):
        """リトライ時の enemy_strategy が勝敗に応じて正しく設定される
        - 敗北時（PLAYER拠点撃破）: 前回の enemy_strategy を継続（UPPER_ONLY が残る）
        - 勝利時（ENEMY拠点撃破）: random.choice で再選択（LOWER_ONLY になる）
        リトライ時の random.choice は常に LOWER_ONLY を返すようにモックする
        """
        test_cases = [
            ("player loss: strategy preserved", Side.PLAYER, EnemyStrategy.UPPER_ONLY),
            (
                "player win: strategy reset by random",
                Side.ENEMY,
                EnemyStrategy.LOWER_ONLY,
            ),
        ]
        for case_name, destroyed_side, expected_strategy in test_cases:
            with self.subTest(case_name=case_name):
                with patch(
                    "force.random.choice", return_value=EnemyStrategy.UPPER_ONLY
                ):
                    controller = PyxelController()

                target_force = controller.game_core.force[destroyed_side]
                target_force._units = [  # pylint: disable=W0212
                    u
                    for u in target_force._units  # pylint: disable=W0212
                    if u.unit_type != UnitType.BASE
                ]
                controller.game_core._needs_reset = True  # pylint: disable=W0212
                with patch(
                    "force.random.choice", return_value=EnemyStrategy.LOWER_ONLY
                ):
                    controller.update()

                self.assertEqual(controller.game_core.enemy_strategy, expected_strategy)


class TestGameOver(TestParent):
    """ゲーム終了判定のテスト（TDDサイクル2）"""

    def test_is_game_over(self):
        """いずれかのForceの拠点が撃破されればゲーム終了"""
        test_cases = [
            ("both bases alive", [], False),
            ("enemy base destroyed", [Side.ENEMY], True),
            ("player base destroyed", [Side.PLAYER], True),
        ]
        for case_name, destroyed_sides, expected in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                for side in destroyed_sides:
                    self._destroy_base(core, side)
                self.assertEqual(core.is_game_over(), expected)


class TestGameOverUpdate(TestParent):
    """ゲーム終了時のupdate停止とクリック検出のテスト（TDDサイクル3）"""

    def test_update_skips_force_update_when_game_over(self):
        """ゲーム終了時（拠点撃破時）にupdate()がForce更新をスキップする"""
        core = GameCore()
        player_unit = Unit(Side.PLAYER, UnitType.MIDDLE)
        player_unit._x = 50  # pylint: disable=W0212
        core.force[Side.PLAYER]._units.append(player_unit)  # pylint: disable=W0212
        # 敵軍拠点を撃破 → ゲーム終了
        self._destroy_base(core, Side.ENEMY)

        start_x = player_unit.x
        # SPEED=0.5 なので、2回更新で1ピクセル移動
        core.update()
        core.update()

        # ゲーム終了時はユニットが移動しない（Force更新がスキップされる）
        self.assertEqual(player_unit.x, start_x)

    def test_click_sets_needs_reset_depends_on_game_over(self):
        """ポップアップ領域クリック時のneeds_resetはゲーム終了状態（拠点撃破）に依存する"""
        test_cases = [
            ("game over, popup click", True, True),
            ("not game over, popup click", False, False),
        ]
        for case_name, is_game_over, expected in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                if is_game_over:
                    self._destroy_base(core, Side.ENEMY)

                # ポップアップ中央をクリック
                self.test_input.set_mouse(
                    self.POPUP_X + self.POPUP_W // 2,
                    self.POPUP_Y + self.POPUP_H // 2,
                )
                self.test_input.set_click(True)
                core.update()

                self.assertEqual(core.needs_reset(), expected)

    def test_game_over_reset_depends_on_click_position(self):
        """拠点撃破によるゲーム終了時、リセット有無はクリック位置（ポップアップ内/外）に依存する"""
        test_cases = [
            # ポップアップ境界上（内側）→ リセットする
            ("top-left corner", self.POPUP_X, self.POPUP_Y, True),
            ("top-right corner", self.POPUP_X + self.POPUP_W - 1, self.POPUP_Y, True),
            ("bottom-left corner", self.POPUP_X, self.POPUP_Y + self.POPUP_H - 1, True),
            (
                "bottom-right corner",
                self.POPUP_X + self.POPUP_W - 1,
                self.POPUP_Y + self.POPUP_H - 1,
                True,
            ),
            # ポップアップ領域外 → リセットしない
            (
                "left of popup",
                self.POPUP_X - 1,
                self.POPUP_Y + self.POPUP_H // 2,
                False,
            ),
            (
                "right of popup",
                self.POPUP_X + self.POPUP_W,
                self.POPUP_Y + self.POPUP_H // 2,
                False,
            ),
            ("above popup", self.POPUP_X + self.POPUP_W // 2, self.POPUP_Y - 1, False),
            (
                "below popup",
                self.POPUP_X + self.POPUP_W // 2,
                self.POPUP_Y + self.POPUP_H,
                False,
            ),
            (
                "mid button area",
                self.MID_BUTTON_X + self.BUTTON_W // 2,
                self.BUTTON_Y + self.BUTTON_H // 2,
                False,
            ),
        ]
        for case_name, mx, my, expected_reset in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                self._destroy_base(core, Side.ENEMY)
                self.test_input.set_mouse(mx, my)
                self.test_input.set_click(True)
                core.update()
                self.assertEqual(core.needs_reset(), expected_reset)


class TestAttackDrawing(TestParent):
    """攻撃エフェクト描画のテスト（TDDサイクル5）"""

    def test_game_core_draw_draws_attacks(self):
        """GameCore.draw() が攻撃エフェクトを描画する"""
        # Arrange
        core = GameCore()
        for s in Side:
            core.force[s]._attacks = []  # pylint: disable=W0212
        attack = Attack(50, Side.PLAYER, UnitType.MIDDLE, Movable.TILE_SIZE)
        core.force[Side.PLAYER]._attacks.append(attack)  # pylint: disable=W0212
        self.test_view.call_params = []
        self.test_movable_view.call_params = []

        # Act
        core.draw()

        # Assert - 描画フローの検証: 画面クリア → ユニット・攻撃エフェクト描画 → HPバー → fund → ボタン描画
        expected_view = (
            [("clear", 0)]
            + self.expected_hp_bar_calls(1.0, 1.0)
            + self.expected_coin_calls(
                core.force[Side.PLAYER].fund, core.force[Side.ENEMY].fund
            )
            + self.expected_spawn_button_calls(core)
        )
        self.assertEqual(self.test_view.get_call_params(), expected_view)
        base_player = (
            "draw_unit",
            0,
            GameCore.UNIT_Y,
            Side.PLAYER,
            Direct.RIGHT,
            Direct.RIGHT,
            False,
            UnitType.BASE,
        )
        base_enemy = (
            "draw_unit",
            142,
            GameCore.UNIT_Y,
            Side.ENEMY,
            Direct.LEFT,
            Direct.LEFT,
            False,
            UnitType.BASE,
        )
        self.assertEqual(
            self.test_movable_view.get_call_params(),
            [
                base_player,
                ("draw_attack", 50, GameCore.UNIT_Y, Side.PLAYER, 0.0, UnitType.MIDDLE),
                base_enemy,
            ],
        )


class TestGameResultPopup(TestParent):
    """勝敗結果ポップアップ描画のテスト（TDDサイクル4）"""

    # ポップアップ座標: 画面(150x200)中央配置
    SCREEN_W, SCREEN_H = 150, 200
    POPUP_W, POPUP_H = 130, 30
    POPUP_X = (SCREEN_W - POPUP_W) // 2  # = 10
    POPUP_Y = (SCREEN_H - POPUP_H) // 2  # = 85
    TEXT_X = POPUP_X + 10  # = 20
    TEXT_Y = POPUP_Y + 10  # = 95

    def test_draw_shows_result_popup_when_game_over(self):
        """拠点撃破時にdraw()が勝敗ポップアップを表示する
        描画順序: clear → ゲーム要素 → 黒背景 → 白枠線 → テキスト（最前面）"""
        test_cases = [
            ("enemy base destroyed", Side.ENEMY, "You Win! Click to Restart."),
            ("player base destroyed", Side.PLAYER, "You Lose! Click to Restart."),
        ]
        for case_name, destroyed_side, expected_message in test_cases:
            with self.subTest(case_name=case_name):
                # Arrange: 片方の拠点のみ撃破（生存側のBASEは残す）
                core = GameCore()
                self._destroy_base(core, destroyed_side)
                self.test_view.call_params = []

                # Act
                core.draw()

                # Assert - 全callsを順序込みで検証（ボタン → ポップアップの順で描画）
                # ※ 生存側のBASEユニット描画はmovable_viewに行くためtest_viewには含まれない
                player_ratio = 0.0 if destroyed_side == Side.PLAYER else 1.0
                enemy_ratio = 0.0 if destroyed_side == Side.ENEMY else 1.0
                expected = (
                    [("clear", 0)]
                    + self.expected_hp_bar_calls(player_ratio, enemy_ratio)
                    + self.expected_coin_calls(
                        core.force[Side.PLAYER].fund, core.force[Side.ENEMY].fund
                    )
                    + self.expected_spawn_button_calls(core)
                    + [
                        (
                            "draw_rect",
                            self.POPUP_X,
                            self.POPUP_Y,
                            self.POPUP_W,
                            self.POPUP_H,
                            0,
                        ),  # 黒背景（塗りつぶし）
                        (
                            "draw_rectb",
                            self.POPUP_X,
                            self.POPUP_Y,
                            self.POPUP_W,
                            self.POPUP_H,
                            7,
                        ),  # 白枠線（輪郭のみ）
                        ("draw_text", self.TEXT_X, self.TEXT_Y, expected_message),
                    ]
                )
                self.assertEqual(self.test_view.get_call_params(), expected)


class TestSpawnButton(TestParent):
    """出撃ボタン描画のテスト（TDDサイクル1: ID-008）"""

    def test_draw_shows_spawn_button_during_gameplay(self):
        """ゲームプレイ中、draw()が出撃ボタンを描画する
        描画順序: clear → ユニット → ボタン背景 → ボタン枠線 → ボタンテキスト"""
        # Arrange
        core = GameCore()
        self.test_view.call_params = []

        # Act
        core.draw()

        # Assert - ボタンが描画される
        expected = (
            [("clear", 0)]
            + self.expected_hp_bar_calls(1.0, 1.0)
            + self.expected_coin_calls(
                core.force[Side.PLAYER].fund, core.force[Side.ENEMY].fund
            )
            + self.expected_spawn_button_calls(core)
        )
        self.assertEqual(self.test_view.get_call_params(), expected)


class TestSpawnButtonClick(TestParent):
    """出撃ボタンクリックによるユニット生成のテスト（TDDサイクル2: ID-008）"""

    def test_button_click_spawns_unit_depends_on_game_state(self):
        """ボタン領域クリック時のユニット生成はゲーム状態と fund に依存する"""
        test_cases = [
            (
                "gameplay with fund: spawns unit",
                False,
                Force.SPAWN_COST[UnitType.MIDDLE],
                1,
            ),
            ("game over: no spawn", True, Force.SPAWN_COST[UnitType.MIDDLE], 0),
        ]
        for case_name, is_game_over, fund, expected_delta in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                core.force[Side.PLAYER]._fund = fund  # pylint: disable=W0212
                if is_game_over:
                    self._destroy_base(core, Side.ENEMY)
                initial_count = len(core.force[Side.PLAYER].units)
                self.test_input.set_mouse(
                    self.MID_BUTTON_X + self.BUTTON_W // 2,
                    self.BUTTON_Y + self.BUTTON_H // 2,
                )
                self.test_input.set_click(True)

                core.update()

                self.assertEqual(
                    len(core.force[Side.PLAYER].units), initial_count + expected_delta
                )
                self.assertFalse(core.needs_reset())

    def test_each_button_click_spawns_correct_unit_type(self):
        """fund 充分時: LOW/MID/UPPボタンクリック → 対応する種別のユニットがスポーンする"""
        test_cases = [
            ("LOW button spawns LOWER", self.LOW_BUTTON_X, UnitType.LOWER),
            ("MID button spawns MIDDLE", self.MID_BUTTON_X, UnitType.MIDDLE),
            ("UPP button spawns UPPER", self.UPP_BUTTON_X, UnitType.UPPER),
        ]
        for case_name, button_x, expected_unit_type in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                fund = Force.SPAWN_COST[expected_unit_type]
                core.force[Side.PLAYER]._fund = fund  # pylint: disable=W0212
                self.test_input.set_mouse(
                    button_x + self.BUTTON_W // 2,
                    self.BUTTON_Y + self.BUTTON_H // 2,
                )
                self.test_input.set_click(True)
                core.update()
                spawned = [
                    u
                    for u in core.force[Side.PLAYER].units
                    if u.unit_type == expected_unit_type
                ]
                self.assertEqual(len(spawned), 1, case_name)


class TestSpawnButtonWithFund(TestParent):
    """軍資金とスポーンボタンの連携テスト（ID-019）"""

    def test_button_click_fails_when_insufficient_fund(self):
        """fund 不足時はボタンクリックしてもユニットがスポーンされない"""
        core = GameCore()
        core.force[Side.PLAYER]._fund = 0  # pylint: disable=W0212
        initial_count = len(core.force[Side.PLAYER].units)
        self.test_input.set_mouse(
            self.MID_BUTTON_X + self.BUTTON_W // 2,
            self.BUTTON_Y + self.BUTTON_H // 2,
        )
        self.test_input.set_click(True)
        core.update()
        self.assertEqual(len(core.force[Side.PLAYER].units), initial_count)


class TestFundDisplay(TestParent):
    """軍資金表示のテスト（TDDサイクル 2: ID-025）"""

    def test_draw_shows_coins_for_fund(self):
        """draw() が軍資金をコイン画像で描画する"""
        test_cases = [
            ("fund=0: no coins", 0, 0),
            ("fund=5: 1 coin each", 5, 5),
            ("fund=60: 12 coins (1 col full)", 60, 60),
            ("fund=65: 13 coins (2nd col starts)", 65, 60),
            ("fund=120: 24 coins (2 cols full)", 120, 120),
            ("fund=125: capped at 24", 125, 125),
        ]
        for case_name, player_fund, enemy_fund in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                core.force[Side.PLAYER]._fund = player_fund  # pylint: disable=W0212
                core.force[Side.ENEMY]._fund = enemy_fund  # pylint: disable=W0212
                self.test_view.call_params = []
                core.draw()
                expected = (
                    [("clear", 0)]
                    + self.expected_hp_bar_calls(1.0, 1.0)
                    + self.expected_coin_calls(player_fund, enemy_fund)
                    + self.expected_spawn_button_calls(core)
                )
                self.assertEqual(self.test_view.call_params, expected)


class TestBaseHpBar(TestParent):
    """拠点HPバー描画のテスト（TDDサイクル2: ID-029）"""

    def test_draw_base_hp_bar(self):
        """拠点HPバーが残HP割合に応じた高さ・陣営色で描画されること

        描画順: clear → HPバー(PLAYER先・ENEMY後) → コイン → ボタン
        自軍バー: HP_BAR_PLAYER_X（左端近く）、色=HP_BAR_PLAYER_COLOR
        敵軍バー: HP_BAR_ENEMY_X（右端近く）、色=HP_BAR_ENEMY_COLOR
        背景バー（常に最大高さ）＋ 前景バー（割合分の高さ）
        """
        test_cases = [
            ("full HP: player=1.0, enemy=1.0", 0, 1.0, 1.0),
            ("half HP: player=0.5, enemy=1.0", 10, 0.5, 1.0),
        ]
        for case_name, player_damage_count, player_ratio, enemy_ratio in test_cases:
            with self.subTest(case_name=case_name):
                core = GameCore()
                if player_damage_count > 0:
                    base_unit = next(
                        u
                        for u in core.force[Side.PLAYER].units
                        if u.unit_type == UnitType.BASE
                    )
                    for _ in range(player_damage_count):
                        base_unit.take_damage()
                self.test_view.call_params = []
                core.draw()

                expected = (
                    [("clear", 0)]
                    + self.expected_hp_bar_calls(player_ratio, enemy_ratio)
                    + self.expected_coin_calls(
                        core.force[Side.PLAYER].fund, core.force[Side.ENEMY].fund
                    )
                    + self.expected_spawn_button_calls(core)
                )
                self.assertEqual(self.test_view.call_params, expected)


class TestSpawnButtonPressUpdate(TestParent):
    """スポーンボタン press/update 統合テスト（TDD サイクル 2: ID-028）"""

    def _get_button_bg_color(self, call_params, button):
        """draw_rect の呼び出しからボタン背景色を取得するヘルパー"""
        return next(
            c[5]
            for c in call_params
            if c[0] == "draw_rect"
            and c[1] == button.x
            and c[2] == button.y
            and c[3] == button.width
            and c[4] == button.height
        )

    def test_after_press_duration_button_returns_to_normal_color(self):
        """クリック後 PRESS_DURATION フレーム経過すると draw() でボタンが NORMAL_BG_COLOR に戻る"""
        core = GameCore()
        core.force[Side.PLAYER]._fund = Force.SPAWN_COST[UnitType.MIDDLE]  # pylint: disable=W0212
        self.test_input.set_mouse(
            self.MID_BUTTON_X + self.BUTTON_W // 2,
            self.BUTTON_Y + self.BUTTON_H // 2,
        )
        self.test_input.set_click(True)
        core.update()
        self.test_input.set_click(False)

        # 前提確認: クリック直後はボタンが PRESSED_BG_COLOR で描画される
        self.test_view.call_params = []
        core.draw()
        self.assertEqual(
            self._get_button_bg_color(self.test_view.call_params, core.mid_button),
            Button.PRESSED_BG_COLOR,
            "クリック直後はボタンが PRESSED_BG_COLOR で描画されること",
        )

        # PRESS_DURATION フレーム経過後は NORMAL_BG_COLOR に戻る
        for _ in range(Button.PRESS_DURATION):
            core.update()
        self.test_view.call_params = []
        core.draw()

        self.assertEqual(
            self._get_button_bg_color(self.test_view.call_params, core.mid_button),
            Button.NORMAL_BG_COLOR,
        )


if __name__ == "__main__":
    unittest.main()
