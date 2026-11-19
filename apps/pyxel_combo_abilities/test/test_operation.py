"""操作（クリック座標の判定）のテスト。"""

import itertools
import unittest

from src import screen
from src.game import AttackStep, ComboAbilitiesGame
from src.garage import Garage
from src.operation import BUTTON, Operation, hit_test, in_new_game
from src.resource import Component, Resource

SIZE = screen.ICON_SIZE


def _inside(x, y):
    """アイコン 1 つ分の領域（左上 (x, y)・SIZE 四方）の、四隅と中心の座標。"""
    return [
        (x, y),
        (x + SIZE - 1, y),
        (x, y + SIZE - 1),
        (x + SIZE - 1, y + SIZE - 1),
        (x + SIZE // 2, y + SIZE // 2),
    ]


class TestHitTestBoxes(unittest.TestCase):
    """部品の枠 6 個（空でもよい）の判定。"""

    def test_each_box_hit_inside(self):
        """全部品の全枠は、描かれる領域の内側（四隅・中心）で、その枠として判定される。"""
        garage = Garage()
        for comp in Component.tuned():
            for idx in range(len(comp.value)):
                x, y = screen.box_pos(comp, idx)
                for px, py in _inside(x, y):
                    self.assertEqual(hit_test(garage, px, py), (comp, idx))

    def test_box_miss_just_outside(self):
        """領域の 1 画素外側（上下左右）は、枠として判定されない。"""
        garage = Garage()
        x, y = screen.box_pos(Component.ENGINE, 0)
        for px, py in [(x - 1, y), (x, y - 1), (x + SIZE, y), (x, y + SIZE)]:
            self.assertNotEqual(hit_test(garage, px, py), (Component.ENGINE, 0))


class TestHitTestStock(unittest.TestCase):
    """ストックの枠の判定（リソースが入っているものだけ）。"""

    def test_filled_stock_hit(self):
        """リソースが入っているストックの枠は、領域の内側で、ストックの枠として判定される。"""
        garage = Garage()
        garage.set_stock([Resource.BOLT_BRONZE, Resource.STAR_BRONZE])
        for idx in range(2):
            x, y = screen.stock_pos(idx)
            for px, py in _inside(x, y):
                self.assertEqual(hit_test(garage, px, py), (Component.STOCK, idx))

    def test_empty_stock_not_hit(self):
        """空のストックの枠は、クリックできない（対象なし）。"""
        garage = Garage()
        garage.set_stock([Resource.BOLT_BRONZE])
        x, y = screen.stock_pos(1)
        self.assertIsNone(hit_test(garage, x + SIZE // 2, y + SIZE // 2))


class TestHitTestButton(unittest.TestCase):
    """決定ボタン（枠の四角）の判定。"""

    def test_button_hit_inside_frame(self):
        """枠の四角の中心と、四隅の画素（端を含む）は、決定ボタンとして判定される。"""
        garage = Garage()
        x, y, w, h = screen.button_frame_rect()
        for px, py in [
            (screen.BUTTON_X, screen.BUTTON_Y),
            (x, y),
            (x + w - 1, y),
            (x, y + h - 1),
            (x + w - 1, y + h - 1),
        ]:
            self.assertEqual(hit_test(garage, px, py), BUTTON, (px, py))

    def test_button_miss_outside_frame(self):
        """枠の四角の 1 画素外側（上下左右）は、決定ボタンではない。"""
        garage = Garage()
        x, y, w, h = screen.button_frame_rect()
        mid_x, mid_y = x + w // 2, y + h // 2
        for px, py in [(x - 1, mid_y), (x + w, mid_y), (mid_x, y - 1), (mid_x, y + h)]:
            self.assertIsNone(hit_test(garage, px, py), (px, py))


class TestHitTestNothing(unittest.TestCase):
    """どれにも当たらない座標。"""

    def test_empty_area_is_none(self):
        """画面の隅（フィールド側）や、枠のすき間は、対象なし。"""
        garage = Garage()
        self.assertIsNone(hit_test(garage, 0, 0))
        self.assertIsNone(hit_test(garage, screen.SCREEN_W - 1, screen.SCREEN_H - 1))


def _rand_cycle():
    """同じ並びを毎回繰り返す乱数（0 以上 1 未満）の関数を作る。"""
    values = itertools.cycle([0.1, 0.9, 0.5, 0.3, 0.7])
    return lambda: next(values)


def _operation():
    """固定の乱数で ComboAbilitiesGame を作り、Operation を返す。"""
    return Operation(ComboAbilitiesGame(rand=_rand_cycle()))


ENGINE0 = (Component.ENGINE, 0)
ENGINE1 = (Component.ENGINE, 1)
GUN0 = (Component.GUN, 0)
STOCK0 = (Component.STOCK, 0)
STOCK1 = (Component.STOCK, 1)


class TestOperationSelect(unittest.TestCase):
    """枠の選択と入れ替え（FR3）。"""

    def test_first_click_selects(self):
        """何も選択していないときに枠をクリックすると、その枠が選択される。"""
        op = _operation()
        self.assertIsNone(op.selected)
        op.click(ENGINE0)
        self.assertEqual(op.selected, ENGINE0)

    def test_second_click_swaps_and_clears(self):
        """選択中に別の枠をクリックすると、2 つの中身が入れ替わり、選択が解除される。"""
        op = _operation()
        garage = op.game.garage
        garage.boxes[Component.STOCK] = [Resource.THINGS_BRONZE] + [None] * 4
        op.click(STOCK0)
        op.click(ENGINE0)
        self.assertEqual(garage.boxes[Component.ENGINE][0], Resource.THINGS_BRONZE)
        self.assertIsNone(garage.boxes[Component.STOCK][0])
        self.assertIsNone(op.selected)

    def test_swap_recalculates_level(self):
        """入れ替えが成立すると、部品のレベルが計算し直される（FR3.3）。"""
        op = _operation()
        garage = op.game.garage
        garage.boxes[Component.ENGINE] = [None, Resource.BOLT_GOLD]
        garage.boxes[Component.STOCK] = [Resource.THINGS_GOLD] + [None] * 4
        op.click(STOCK0)
        op.click(ENGINE0)
        # ENGINE の枠は THINGS_GOLD と BOLT_GOLD（ランク 3）なので、レベルは 3 + 1。
        self.assertEqual(
            garage.get_lv(Component.ENGINE), Resource.get_rank(Resource.THINGS_GOLD) + 1
        )

    def test_mismatch_changes_nothing_but_clears(self):
        """種類が合わない入れ替えは何も変えず、選択だけが解除される。"""
        op = _operation()
        garage = op.game.garage
        garage.boxes[Component.STOCK] = [Resource.STAR_BRONZE] + [None] * 4
        before = {comp: list(boxes) for comp, boxes in garage.boxes.items()}
        op.click(STOCK0)
        op.click(ENGINE0)  # ENGINE の枠 0 は THINGS 用。STAR は入らない。
        self.assertEqual(garage.boxes, before)
        self.assertIsNone(op.selected)

    def test_same_box_clears_only(self):
        """同じ枠をもう一度クリックすると、何も変えずに選択が解除される。"""
        op = _operation()
        garage = op.game.garage
        garage.boxes[Component.STOCK] = [Resource.THINGS_BRONZE] + [None] * 4
        before = {comp: list(boxes) for comp, boxes in garage.boxes.items()}
        op.click(STOCK0)
        op.click(STOCK0)
        self.assertEqual(garage.boxes, before)
        self.assertIsNone(op.selected)


class TestOperationExecute(unittest.TestCase):
    """決定ボタンと、対象なし、終了後（FR4・FR5）。"""

    def test_button_plays_turn_and_keeps_selection(self):
        """決定ボタンで 1 ターン進み、ストックが置き換わる。選択は残る（解除は再生の終わり）。"""
        op = _operation()
        expect = ComboAbilitiesGame(rand=_rand_cycle())
        expect.play_turn()
        op.click(ENGINE0)
        op.click(BUTTON)
        self.assertEqual(op.game.turn, expect.turn)
        self.assertEqual(
            op.game.garage.boxes[Component.STOCK], expect.garage.boxes[Component.STOCK]
        )
        self.assertEqual(op.selected, ENGINE0)  # 移植元は、ターンの終わりまで選択を残す

    def test_button_returns_attack_steps(self):
        """ID-008 FR2.1: 決定ボタンは攻撃 1 回ごとの結果の列を返し、それ以外は None を返す。"""
        op = _operation()
        self.assertIsNone(op.click(ENGINE0))
        self.assertIsNone(op.click(None))
        steps = op.click(BUTTON)
        self.assertTrue(steps)
        self.assertTrue(all(isinstance(s, AttackStep) for s in steps))

    def test_button_returns_none_after_end(self):
        """ID-008 FR5: ターン数が最大なら、決定ボタンも何も返さない。"""
        op = _operation()
        op.game.turn = op.game.MAX_TURN
        self.assertIsNone(op.click(BUTTON))

    def test_none_keeps_selection(self):
        """対象なしをクリックしても、何も変わらない（選択も保つ）。"""
        op = _operation()
        op.click(ENGINE0)
        turn = op.game.turn
        op.click(None)
        self.assertEqual(op.selected, ENGINE0)
        self.assertEqual(op.game.turn, turn)

    def test_nothing_accepted_after_end(self):
        """ターン数が最大に達していると、枠も決定ボタンも受け付けない。"""
        op = _operation()
        op.game.turn = op.game.MAX_TURN
        op.click(ENGINE0)
        self.assertIsNone(op.selected)
        op.click(BUTTON)
        self.assertEqual(op.game.turn, op.game.MAX_TURN)


if __name__ == "__main__":
    unittest.main()


class TestInNewGame(unittest.TestCase):
    """ID-009 FR4: New Game ボタンの矩形（端を含む）の内側だけが当たる。"""

    def test_inside_rect_hits(self):
        """矩形の四隅と中心は当たる。"""
        x, y, w, h = screen.NEW_GAME_RECT
        for px, py in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
            self.assertTrue(in_new_game(px, py), (px, py))
        self.assertTrue(in_new_game(x + w // 2, y + h // 2))

    def test_just_outside_rect_misses(self):
        """矩形の 1 画素外側（上下左右）は当たらない。"""
        x, y, w, h = screen.NEW_GAME_RECT
        for px, py in ((x - 1, y), (x + w, y), (x, y - 1), (x, y + h)):
            self.assertFalse(in_new_game(px, py), (px, py))
