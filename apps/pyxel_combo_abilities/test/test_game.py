"""ComboAbilitiesGame（ターンの進行とゲーム終了）のテスト。乱数は rand 引数で固定する。"""

import math
import unittest

from src.binom_dist import BinomDist
from src.field import Field
from src.game import ComboAbilitiesGame
from src.resource import Component, Resource

# 乱数列の読み方（Field の呼び出し順）:
#   攻撃 1 回 = 対象数(1) + 破壊数(1) + リソースの抽選(破壊数ぶん) + 繰り返し判定(1)
#   ただし、敵を全滅させたときは繰り返し判定の乱数を使わず、必ず繰り返す。
# Garage の初期レベルは全部品 1。このとき:
#   対象数: 0.0 -> 10（最大）、0.5 -> 4
#   破壊数: 0.0 -> 1（対象がいれば最低 1）、1.0 -> 対象数すべて
#   リソース: 0.0 -> THINGS_BRONZE、0.5 -> STAR_BRONZE、0.999999 -> BOLT_GOLD
#   繰り返し: BODY レベル 1 の止まる確率は 0.5。0.0 は止まる、0.999 は繰り返す
ATTACK_1_KILL = (0.5, 0.0, 0.0)  # 対象 4、破壊 1、THINGS_BRONZE を 1 個獲得
STOP = (0.0,)  # 繰り返しを止める
REPEAT = (0.999,)  # 繰り返す


class Script:
    """渡した値を順に返す乱数の供給元。尽きたあとに呼ばれたら IndexError にする。"""

    def __init__(self, *values):
        self.queue = list(values)

    def feed(self, *values):
        """続きの値を足す。"""
        self.queue.extend(values)

    def __call__(self):
        return self.queue.pop(0)


def start_game(*extra):
    """開始時の自動攻撃（ATTACK_1_KILL + STOP）を行ったゲームと、乱数の供給元を返す。"""
    script = Script(*ATTACK_1_KILL, *STOP, *extra)
    return ComboAbilitiesGame(rand=script), script


class TestInitialState(unittest.TestCase):
    """FR1・FR3.2: ゲームの状態と、開始時の自動攻撃。"""

    def test_max_turn(self):
        """最大ターン数は 10。"""
        self.assertEqual(ComboAbilitiesGame.MAX_TURN, 10)

    def test_start_attack(self):
        """作った直後に自動で 1 回攻撃する。ターン 1、撃破 1、ストックは獲得した 1 個。"""
        game, script = start_game()
        self.assertEqual(game.turn, 1)
        self.assertEqual(game.kills, 1)
        self.assertEqual(game.level, 1)
        stock = game.garage.get_box_resources(Component.STOCK)
        self.assertEqual(stock, [Resource.THINGS_BRONZE] + [None] * 4)
        self.assertEqual(script.queue, [])

    def test_start_garage(self):
        """Garage は部品の枠が空（ストック以外）で、全部品レベル 1。"""
        game, _ = start_game()
        for comp in Component.tuned():
            self.assertEqual(game.garage.get_box_resources(comp), [None, None])
            self.assertEqual(game.garage.get_lv(comp), 1)


class TestTurnDestroy(unittest.TestCase):
    """FR2: 1 ターン分の攻撃。"""

    def test_single_attack(self):
        """繰り返しが止まれば 1 回で終わり、獲得したリソースを返して撃破数に加える。"""
        game, script = start_game(*ATTACK_1_KILL, *STOP)
        kills = game.kills
        result = game.turn_destroy()
        self.assertEqual(result, [Resource.THINGS_BRONZE])
        self.assertEqual(game.kills, kills + 1)  # 破壊数 1
        self.assertEqual(script.queue, [])

    def test_repeat_and_order(self):
        """繰り返し判定が通る間は攻撃を続け、獲得をランクの高い順に並べる。"""
        game, script = start_game(
            *ATTACK_1_KILL,
            *REPEAT,  # 1 回目: THINGS_BRONZE、繰り返す
            0.5,
            0.0,
            0.999999,
            *STOP,  # 2 回目: BOLT_GOLD、止める
        )
        kills = game.kills
        result = game.turn_destroy()
        # 並び順は BRONZE -> GOLD の獲得順ではなく、ランクの高い順（GOLD が先頭）
        self.assertEqual(result, [Resource.BOLT_GOLD, Resource.THINGS_BRONZE])
        self.assertEqual(game.kills, kills + 1 + 1)  # 2 回の攻撃で破壊数 1 ずつ
        self.assertEqual(script.queue, [])

    def test_gain_limited_to_stock_size(self):
        """獲得が 5 個を超えるときは、ストックの枠数 5 個までに絞る。"""
        per_attack = 3  # 1 回の攻撃で 3 体破壊（対象 3、破壊 3）
        game, _ = start_game(
            *(0.999, 1.0, 0.0, 0.0, 0.0, *REPEAT),  # 1 回目: 3 個獲得、繰り返す
            *(0.999, 1.0, 0.0, 0.0, 0.0, *STOP),  # 2 回目: 3 個獲得、止める
        )
        kills = game.kills
        result = game.turn_destroy()
        self.assertEqual(len(Component.STOCK.value), 5)
        self.assertEqual(len(result), len(Component.STOCK.value))
        self.assertLess(len(result), per_attack * 2)  # 6 個のうち 5 個
        self.assertEqual(game.kills, kills + per_attack * 2)

    def test_level_up(self):
        """敵を全滅させるとゲームのレベルが 1 上がり、その判定では必ず繰り返す。"""
        game, script = start_game(
            *(0.0, 1.0),  # 対象 10、破壊 10（全滅）
            *([0.0] * Field.MAX_NPC_NUM),  # 10 個のリソース（THINGS_BRONZE）
            # 全滅したので繰り返し判定の乱数は使わず、必ず繰り返す
            *ATTACK_1_KILL,
            *STOP,  # レベル 2 の敵に 1 回攻撃して止める
        )
        kills = game.kills
        result = game.turn_destroy()
        self.assertEqual(game.level, 2)
        self.assertEqual(game.kills, kills + Field.MAX_NPC_NUM + 1)
        self.assertEqual(len(result), len(Component.STOCK.value))  # 11 個のうち 5 個
        self.assertEqual(script.queue, [])

    def test_next_field_uses_game_level(self):
        """レベルが上がったあとのターンは、そのレベルの Field で攻撃する。"""
        game, script = start_game(
            *(0.0, 1.0),
            *([0.0] * Field.MAX_NPC_NUM),
            *ATTACK_1_KILL,
            *STOP,
        )
        game.turn_destroy()
        self.assertEqual(game.level, 2)
        # レベル 2 の重み: THINGS_BRONZE 100、THINGS_SILVER 10+3*2=16、THINGS_GOLD 0+1*2=2
        # 累積では THINGS_BRONZE が 100、SILVER が 116、GOLD が 118。全体の合計は
        # 100*3 + 16*3 + 2*3 = 354。乱数 (100 + 1) / 354 は、レベル 2 では
        # THINGS_SILVER（累積 100〜116）になる（レベル 1 の合計 333 では STAR_BRONZE に近い）。
        total = (100 + 16 + 2) * 3
        rand = (100 + 1) / total
        script.feed(0.5, 0.0, rand, *STOP)
        result = game.turn_destroy()
        self.assertEqual(result, [Resource.THINGS_SILVER])


class TestPlayTurn(unittest.TestCase):
    """FR3.1: ターンの進行とストックの置き換え。"""

    def test_turn_and_stock(self):
        """ターンの攻撃で、ターン数が 1 増え、ストックは新しい獲得で置き換わる。"""
        game, script = start_game(0.5, 0.0, 0.5, *STOP)  # STAR_BRONZE を 1 個獲得
        kills = game.kills
        game.play_turn()
        self.assertEqual(game.turn, 2)  # 開始時の 1 から 1 増える
        self.assertEqual(game.kills, kills + 1)
        stock = game.garage.get_box_resources(Component.STOCK)
        # 前のターンの THINGS_BRONZE は失われる
        self.assertEqual(stock, [Resource.STAR_BRONZE] + [None] * 4)
        self.assertEqual(script.queue, [])

    def test_stock_full(self):
        """獲得が多くても、ストックは最大 5 個で、エラーにならない。"""
        game, _ = start_game(0.0, 1.0, *([0.0] * 10), *ATTACK_1_KILL, *STOP)
        game.play_turn()
        stock = game.garage.get_box_resources(Component.STOCK)
        self.assertEqual(len([i for i in stock if i is not None]), 5)


class TestPlayTurnSteps(unittest.TestCase):
    """ID-008 FR1: play_turn は、攻撃 1 回ごとの結果（破壊数・レベルアップ）の列を返す。"""

    def test_steps_match_attacks(self):
        """列の長さは攻撃の回数と等しく、破壊数の合計は撃破数の増分と等しい。"""
        game, _ = start_game(
            *ATTACK_1_KILL,
            *REPEAT,  # 1 回目: 破壊 1、繰り返す
            *ATTACK_1_KILL,
            *STOP,  # 2 回目: 破壊 1、止める
        )
        kills = game.kills
        steps = game.play_turn()
        self.assertEqual(len(steps), 2)
        self.assertEqual(sum(s.killed for s in steps), game.kills - kills)
        self.assertFalse(any(s.leveled_up for s in steps))

    def test_level_up_is_reported(self):
        """全滅した攻撃は leveled_up が True。その数は、上がったレベルと等しい。"""
        game, _ = start_game(
            *(0.0, 1.0),  # 対象 10、破壊 10（全滅）
            *([0.0] * Field.MAX_NPC_NUM),
            *ATTACK_1_KILL,
            *STOP,  # レベル 2 の敵に 1 回攻撃して止める
        )
        level = game.level
        steps = game.play_turn()
        self.assertEqual([s.killed for s in steps], [Field.MAX_NPC_NUM, 1])
        self.assertEqual([s.leveled_up for s in steps], [True, False])
        self.assertEqual(sum(s.leveled_up for s in steps), game.level - level)

    def test_state_same_as_before(self):
        """列を返しても、ターン数・撃破数・ストックの更新は従来どおり。"""
        game, _ = start_game(0.5, 0.0, 0.5, *STOP)  # STAR_BRONZE を 1 個獲得
        game.play_turn()
        self.assertEqual(game.turn, 2)
        stock = game.garage.get_box_resources(Component.STOCK)
        self.assertEqual(stock, [Resource.STAR_BRONZE] + [None] * 4)

    def test_no_steps_after_end(self):
        """ゲーム終了後は空の列を返し、乱数も状態も使わない。"""
        game, script = start_game(
            *[
                v
                for _ in range(ComboAbilitiesGame.MAX_TURN - 1)
                for v in (*ATTACK_1_KILL, *STOP)
            ]
        )
        for _ in range(ComboAbilitiesGame.MAX_TURN - 1):
            game.play_turn()
        self.assertTrue(game.is_end())
        self.assertEqual(game.play_turn(), [])
        self.assertEqual(script.queue, [])


class TestEnd(unittest.TestCase):
    """FR4: ゲーム終了と New Game。"""

    def test_is_end(self):
        """ターン数が最大ターン数（10）以上で終了。それ未満は終了していない。"""
        game, _ = start_game()
        self.assertFalse(game.is_end())
        game.turn = game.MAX_TURN - 1
        self.assertFalse(game.is_end())
        game.turn = game.MAX_TURN
        self.assertTrue(game.is_end())

    def test_playable_turns(self):
        """操作できる攻撃は 9 回（開始時の攻撃 1 回を足して、計 10 ターン）で終わる。"""
        game, script = start_game()
        playable = game.MAX_TURN - 1  # 開始時の自動攻撃でターン 1
        for i in range(playable):
            self.assertFalse(game.is_end())
            script.feed(*ATTACK_1_KILL, *STOP)
            game.play_turn()
            self.assertEqual(game.turn, 1 + i + 1)
        self.assertEqual(game.turn, game.MAX_TURN)
        self.assertTrue(game.is_end())
        self.assertEqual(game.kills, game.MAX_TURN)  # 1 ターンの破壊数 1 × 10

    def test_play_turn_after_end_is_inert(self):
        """終了後のターンの攻撃は何もしない（乱数も使わず、状態を変えない）。"""
        game, _ = start_game()
        game.turn = game.MAX_TURN
        stock = list(game.garage.get_box_resources(Component.STOCK))
        kills = game.kills
        level = game.level
        game.play_turn()  # 乱数が尽きているので、攻撃すれば IndexError になる
        self.assertEqual(game.turn, game.MAX_TURN)
        self.assertEqual(game.kills, kills)
        self.assertEqual(game.level, level)
        self.assertEqual(game.garage.get_box_resources(Component.STOCK), stock)

    def test_new_game(self):
        """New Game は、レベル・撃破数・ターン数・Garage を初期化して開始時の攻撃を行う。"""
        game, script = start_game(
            *(0.0, 1.0),  # レベルが上がる攻撃
            *([0.0] * Field.MAX_NPC_NUM),
            *ATTACK_1_KILL,
            *STOP,
        )
        old_garage = game.garage
        game.play_turn()
        self.assertEqual(game.level, 2)
        game.garage.boxes[Component.ENGINE] = [Resource.THINGS_GOLD, Resource.BOLT_GOLD]
        game.garage.reset_lv()
        script.feed(*ATTACK_1_KILL, *STOP)
        game.new_game()
        self.assertIsNot(game.garage, old_garage)
        self.assertEqual(game.level, 1)
        self.assertEqual(game.kills, 1)  # 開始時の攻撃の破壊数 1
        self.assertEqual(game.turn, 1)
        for comp in Component.tuned():
            self.assertEqual(game.garage.get_lv(comp), 1)
            self.assertEqual(game.garage.get_box_resources(comp), [None, None])
        self.assertEqual(script.queue, [])

    def test_new_game_after_end(self):
        """終了した後でも New Game で再び遊べる。"""
        game, script = start_game()
        game.turn = game.MAX_TURN
        script.feed(*ATTACK_1_KILL, *STOP, *ATTACK_1_KILL, *STOP)
        game.new_game()
        self.assertFalse(game.is_end())
        game.play_turn()
        self.assertEqual(game.turn, 2)


class TestGarageLevels(unittest.TestCase):
    """FR5.1: 調整後の部品レベルで攻撃する。"""

    @staticmethod
    def tune(game, comp, resources):
        """枠 comp にリソースを置き、レベルを再計算する。"""
        game.garage.boxes[comp] = list(resources)
        game.garage.reset_lv()

    def test_engine_and_gun_levels(self):
        """ENGINE と GUN のレベルが、対象数と破壊数の判定に使われる。"""
        game, script = start_game()
        self.tune(game, Component.ENGINE, [Resource.THINGS_GOLD, Resource.BOLT_GOLD])
        self.tune(game, Component.GUN, [Resource.STAR_GOLD, Resource.BOLT_GOLD])
        engine = game.garage.get_lv(Component.ENGINE)
        gun = game.garage.get_lv(Component.GUN)
        self.assertEqual((engine, gun), (4, 4))  # GOLD のランク値 3 + 1
        # 乱数 1.0 は対象数の平均（確率密度が最大）。ceil(engine / (4 + 1) * 10) = 8
        target = math.ceil(engine / (Field.MAX_ENGINE_LEVEL + 1) * Field.MAX_NPC_NUM)
        # 破壊数は GUN レベルの二項分布から。レベル 1 の GUN では結果が変わる乱数を選ぶ
        prob = gun / (Field.MAX_GUN_LEVEL + 1) * (1 / 2) ** (game.level / 10)
        killed = max(1, BinomDist(p=prob, n=target).inv_binom_pdf(0.999))
        script.feed(1.0, 0.999, *([0.0] * killed), *STOP)  # BODY はレベル 1 のまま
        kills = game.kills
        game.turn_destroy()
        self.assertEqual(game.kills, kills + killed)
        self.assertEqual(script.queue, [])

    def test_body_level_repeat(self):
        """BODY のレベルが上がると止まる確率が下がり、同じ乱数でも繰り返す。"""
        # 繰り返し乱数 0.1: BODY レベル 1 の止まる確率 0.5 では止まる（0.1 < 0.5）
        game, script = start_game(*ATTACK_1_KILL, 0.1)
        kills = game.kills
        game.turn_destroy()
        self.assertEqual(game.kills, kills + 1)
        self.assertEqual(script.queue, [])
        # BODY レベル 4 の止まる確率は 0.5 ** 4 = 0.0625。0.1 >= 0.0625 なので繰り返す
        game, script = start_game()
        self.tune(game, Component.BODY, [Resource.THINGS_GOLD, Resource.STAR_GOLD])
        self.assertEqual(game.garage.get_lv(Component.BODY), 4)
        script.feed(*ATTACK_1_KILL, 0.1, *ATTACK_1_KILL, *STOP)
        kills = game.kills
        game.turn_destroy()
        self.assertEqual(game.kills, kills + 2)  # 2 回攻撃した
        self.assertEqual(script.queue, [])


class TestDefaultRand(unittest.TestCase):
    """既定の乱数（rand を渡さない）でも、ゲーム全体が不変条件を満たす。"""

    def test_turn_destroy_default_rand(self):
        """1 ターン分の獲得はリソースだけで、ストックの枠数以下。レベルは 1 以上。"""
        game = ComboAbilitiesGame()
        gain = game.turn_destroy()
        for res in gain:
            self.assertIn(res, Resource.avails())
        self.assertLessEqual(len(gain), len(Component.STOCK.value))
        self.assertGreaterEqual(game.level, 1)

    def test_kills_accumulate_default_rand(self):
        """2 ターン分の攻撃で、撃破数は少なくとも 1 ターンにつき 1 ずつ増える。"""
        game = ComboAbilitiesGame()
        kills = game.kills
        game.turn_destroy()
        game.turn_destroy()
        self.assertGreaterEqual(game.kills, kills + 2)


if __name__ == "__main__":
    unittest.main()
