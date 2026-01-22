# title: pyxel baseball
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum
import random


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, color):
        pass

    @abstractmethod
    def draw_tilemap(self):
        pass

    @abstractmethod
    def draw_rect(self, x, y, width, height, color, is_fill):
        pass

    @abstractmethod
    def draw_image(self, x, y, src_tile_x, src_tile_y):
        pass

    @classmethod
    def create(cls):
        return cls()


class Color(Enum):
    RED = 8
    LIGHT_RED = 14
    YELLOW = 10
    WHITE = 7
    GREEN = 3


class PyxelView(IView):
    MONITOR_WIDTH = 8 * (8 * 2 - 1)
    MONITOR_HEIGHT = 8 * (8 * 2)

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, color=Color.WHITE):
        self.pyxel.text(x, y, text, color.value)

    def draw_tilemap(self):
        self.pyxel.bltm(0, 0, 0, 0, 0, self.MONITOR_WIDTH, self.MONITOR_HEIGHT)

    def draw_rect(self, x, y, width, height, color, is_fill):
        param = {"x": x, "y": y, "w": width, "h": height, "col": color.value}
        if is_fill:
            self.pyxel.rect(**param)
        else:
            self.pyxel.rectb(**param)

    def draw_image(self, x, y, src_tile_x, src_tile_y):
        self.pyxel.blt(
            x,
            y,
            0,
            src_tile_x * 8,
            src_tile_y * 8,
            8,
            8,
        )

    def clear(self):
        self.pyxel.cls(0)


class IInput(ABC):
    @abstractmethod
    def is_click(self):
        pass

    @abstractmethod
    def get_mouse_x(self):
        pass

    @abstractmethod
    def get_mouse_y(self):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_click(self):
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_x(self):
        return self.pyxel.mouse_x

    def get_mouse_y(self):
        return self.pyxel.mouse_y


class GameObject(ABC):
    STRIKE_ZONE_OFFSET_X = 2 * 8
    STRIKE_ZONE_OFFSET_Y = 4 * 8
    STRIKE_ZONE_WIDTH = 5 * 8
    STRIKE_ZONE_HEIGHT = 5 * 8
    SCORE_BOARD_OFFSET_X = 2 * 8
    SCORE_BOARD_OFFSET_Y = 12 * 8
    MESSAGE_OFFSET_X = 8 * 8
    MESSAGE_OFFSET_Y = 10 * 8

    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class AtBat(Enum):
    BALL = 0
    STRIKE = 1
    HIT = 2
    OUT = 3
    FAUL = 4


class Count(GameObject):
    COUNT_OFFSET_X = 9 * 8
    COUNT_OFFSET_Y = 5 * 8
    LIGHT_IMAGE_POS_MAP = {
        "B": (4, 2),
        "S": (5, 2),
        "O": (3, 2),
    }

    def __init__(self):
        super().__init__()
        self.ball = 0
        self.strike = 0
        self.out = 0

    def draw(self):
        count_map = {"B": self.ball, "S": self.strike, "O": self.out}
        for i, letter in enumerate(["B", "S", "O"]):
            self.view.draw_text(
                self.COUNT_OFFSET_X + 2,
                self.COUNT_OFFSET_Y + i * 8 + 2,
                letter,
            )
            for j in range(count_map[letter]):
                self.view.draw_image(
                    Count.COUNT_OFFSET_X + (j + 1) * 8,
                    Count.COUNT_OFFSET_Y + i * 8,
                    *Count.LIGHT_IMAGE_POS_MAP[letter],
                )

    def _reset(self):
        self.ball = 0
        self.strike = 0

    def pitch(self, at_bat):
        if at_bat == AtBat.BALL:
            self.ball += 1
            if self.ball == 4:
                self._reset()
                return True
        elif at_bat == AtBat.STRIKE:
            self.strike += 1
            if self.strike == 3:
                self._reset()
                self.out += 1
        elif at_bat == AtBat.FAUL:
            if self.strike < 2:
                self.strike += 1
        elif at_bat == AtBat.HIT:
            self._reset()
            return True
        elif at_bat == AtBat.OUT:
            self._reset()
            self.out += 1
        return False

    def get_out(self):
        return self.out

    def get_info(self):
        return self.out, self.ball, self.strike


class EnemyManager:
    STRIKE_ZONE_LIST = [(x, y) for x in range(1, 4) for y in range(1, 4)]
    BALL_ZONE_LIST = [
        (x, y) for x in range(0, 5) for y in range(0, 5) if x in [0, 4] or y in [0, 4]
    ]

    def __init__(self):
        self.inf_out = 0
        self.inf_ball = 0
        self.inf_strike = 0
        self.inf_runner = [False] * 3
        self.inf_score = {player: [] for player in Player}

    def sign(self, is_offence):
        if is_offence:
            return self._should_swing()
        return self._pitch_target()

    def _should_swing(self):
        """
        攻撃側：このカウント・塁状況・スコアでバッターは振るかどうか
        """
        my_score = sum(self.inf_score[Player.E])
        opponent_score = sum(self.inf_score[Player.U])
        base_prob = 0.5

        if self.inf_strike == 2:
            base_prob += 0.4
        if any(self.inf_runner):
            base_prob += 0.2
        if my_score < opponent_score:
            base_prob += 0.1

        return (
            None
            if random.random() > base_prob
            else random.choice(self.STRIKE_ZONE_LIST)
        )

    def _pitch_target(self):
        """
        守備側：このカウント・塁状況・スコアでストライク or ボールを狙うか
        """
        base_prob = 0.5

        if self.inf_strike == 2:
            base_prob -= 0.2  # ボール気味にしたい
        if self.inf_ball == 3:
            base_prob += 0.3  # ストライク狙う

        if random.random() < base_prob:
            return random.choice(self.STRIKE_ZONE_LIST)
        else:
            return random.choice(self.BALL_ZONE_LIST)

    def set_info(self, out, ball, strike, runner, score):
        self.inf_out = out
        self.inf_ball = ball
        self.inf_strike = strike
        self.inf_runner = runner
        self.inf_score = score


class StrikeZone(GameObject):
    CONTACT_RESULT_LIST = [
        (AtBat.FAUL, 0),
        (AtBat.OUT, 0),
        (AtBat.HIT, 1),
        (AtBat.HIT, 2),
        (AtBat.HIT, 3),
        (AtBat.HIT, 4),
    ]

    def __init__(self, enemy_manager):
        super().__init__()
        self.selected_pos = None
        self.bef_result_pos = None
        self.is_offence = False
        self.enemy_manager = enemy_manager

    def draw(self):
        for pos, color, padding, width in [
            (self.selected_pos, Color.LIGHT_RED, 0, 8),
            (self.bef_result_pos, Color.YELLOW, 1, 6),
        ]:
            if pos is not None:
                self.view.draw_rect(
                    *[
                        r * 8 + o + padding
                        for r, o in zip(
                            pos,
                            (
                                self.STRIKE_ZONE_OFFSET_X,
                                self.STRIKE_ZONE_OFFSET_Y,
                            ),
                        )
                    ],
                    width,
                    width,
                    color,
                    False,
                )

    def set(self, pos):
        self.selected_pos = None if self.selected_pos == pos else pos

    def get_pitch_result(self):
        self.bef_result_pos = self.enemy_manager.sign(not self.is_offence)
        offence_pos, defence_pos = (
            (self.selected_pos, self.bef_result_pos)
            if self.is_offence
            else (self.bef_result_pos, self.selected_pos)
        )
        if offence_pos is None and defence_pos is None:
            return AtBat.BALL, 0
        if (
            offence_pos is None
            and (defence_pos is None or any(i in [0, 4] for i in defence_pos))
            and offence_pos != defence_pos
        ):
            return AtBat.BALL, 0
        if offence_pos == defence_pos:
            return random.choice(self.CONTACT_RESULT_LIST)
        return AtBat.STRIKE, 0

    def set_offence(self, flg):
        self.is_offence = flg


class Diamond(GameObject):
    RUNNER_OFFSET_X = 1 * 8
    RUNNER_OFFSET_Y = 1 * 8
    RUNNER_IMAGE_TILE_DISTANCE = 3
    RUNNER_IMAGE_POS = (1, 1)

    def __init__(self):
        super().__init__()
        # 1塁, 2塁, 3塁の状態(塁上にランナーがいるかどうか)
        self.bases = [False, False, False]
        self.score = 0
        self.is_game_over = False

    def draw(self):
        for i, is_in in enumerate([not self.is_game_over] + self.bases):
            if not is_in:
                continue
            self.view.draw_image(
                self.RUNNER_OFFSET_X + (i * self.RUNNER_IMAGE_TILE_DISTANCE) * 8,
                self.RUNNER_OFFSET_Y,
                *self.RUNNER_IMAGE_POS,
            )

    def put_runner(self, hit_bases):
        """
        hit_bases: 打者が何塁打を打ったか(1: 単打, 2: 二塁打, 3: 三塁打, 4: 本塁打)
        """
        if self.is_game_over:
            return
        if hit_bases < 1:
            return
        # 走者を進める順番(逆から処理しないと重なってしまう)
        for i in reversed(range(3)):
            if self.bases[i]:
                if i + hit_bases >= 3:
                    self.score += 1  # ホームイン
                else:
                    self.bases[i + hit_bases] = True  # ランナー進塁
                self.bases[i] = False  # 元の塁を空ける

        # 打者を塁に置く(ホームランなら得点)
        if hit_bases >= 4:
            self.score += 1
        else:
            self.bases[hit_bases - 1] = True  # 打者が出塁

    def get_score(self):
        return self.score

    def get_runner(self):
        return self.bases

    def set_game_over(self):
        self.bases = [False, False, False]
        self.score = 0
        self.is_game_over = True


class Action(Enum):
    STRIKE_ZONE = (0, 0)
    NEXT = (2, 6)


class Cursor(GameObject):
    AVAIL_POS_MAP = {
        Action.STRIKE_ZONE: (
            GameObject.STRIKE_ZONE_OFFSET_X,
            GameObject.STRIKE_ZONE_OFFSET_Y,
            GameObject.STRIKE_ZONE_WIDTH,
            GameObject.STRIKE_ZONE_HEIGHT,
        )
    } | {
        v: (
            v.value[0] * 8 + GameObject.STRIKE_ZONE_OFFSET_X,
            v.value[1] * 8 + GameObject.STRIKE_ZONE_OFFSET_Y,
            8,
            8,
        )
        for v in [
            Action.NEXT,
        ]
    }

    def __init__(self):
        super().__init__()
        self.is_select = False
        self.click_pos = (-1, -1)
        self.select_pos = None
        self.select_action = None

    def update(self):
        self.select_pos = None
        self.select_action = None
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if x is not None and y is not None:
                for k, v in self.AVAIL_POS_MAP.items():
                    if v[0] <= x < v[0] + v[2] and v[1] <= y < v[1] + v[3]:
                        next_click_pos = (
                            (x - self.STRIKE_ZONE_OFFSET_X) // 8,
                            (y - self.STRIKE_ZONE_OFFSET_Y) // 8,
                        )
                        if self.click_pos != next_click_pos:
                            self.is_select = True
                            self.click_pos = next_click_pos
                            return
                        self.select_pos = self.click_pos
                        self.select_action = k
                        break
            self.is_select = False
            self.click_pos = (-1, -1)

    def draw(self):
        draws = []
        if self.is_select:
            draws.append(
                (
                    *[
                        r * 8 + o
                        for r, o in zip(
                            self.click_pos,
                            (
                                self.STRIKE_ZONE_OFFSET_X,
                                self.STRIKE_ZONE_OFFSET_Y,
                            ),
                        )
                    ],
                    8,
                    8,
                    Color.RED,
                    False,
                )
            )
        if len(draws) > 0:
            for draw in draws:
                self.view.draw_rect(*draw)

    def get_select_pos(self):
        return self.select_pos

    def get_action(self):
        return self.select_action

    def clear(self):
        self.is_select = False
        self.click_pos = (-1, -1)
        self.select_pos = None
        self.select_action = None


class Console(GameObject):
    CONSOLE_RECT = (20, 40, 80, 30)

    def __init__(self):
        super().__init__()
        self.flg_is_tap = False
        self.scores = [None, None]

    def draw(self):
        self.view.draw_rect(*self.CONSOLE_RECT, Color.GREEN, True)
        self.view.draw_rect(*self.CONSOLE_RECT, Color.WHITE, False)
        if self.scores[0] is not None and self.scores[1] is not None:
            message = (
                "You Win"
                if self.scores[0] > self.scores[1]
                else "You Lose" if self.scores[0] < self.scores[1] else "Draw"
            )
            self.view.draw_text(
                self.CONSOLE_RECT[0] + 10,
                self.CONSOLE_RECT[1] + 5,
                message,
                Color.WHITE,
            )
        self.view.draw_text(
            self.CONSOLE_RECT[0] + 10,
            self.CONSOLE_RECT[1] + 20,
            "Tap to Continue",
            Color.WHITE,
        )

    def update(self):
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if (
                x is not None
                and y is not None
                and self.CONSOLE_RECT[0]
                <= x
                < self.CONSOLE_RECT[0] + self.CONSOLE_RECT[2]
                and self.CONSOLE_RECT[1]
                <= y
                < self.CONSOLE_RECT[1] + self.CONSOLE_RECT[3]
            ):
                self.flg_is_tap = True

    def is_tap(self):
        return self.flg_is_tap

    def set_scores(self, score_player, score_enemy):
        self.scores = [score_player, score_enemy]


class Player(Enum):
    U = 0
    E = 1


class GameCore:
    def __init__(self):
        self.view = PyxelView.create()
        self.cursor = Cursor()
        self.player = Player.U
        self.score = {player: [] for player in Player}
        self.score[self.player].append(0)
        self.count = Count()
        self.enemy_manager = EnemyManager()
        self.strike_zone = StrikeZone(self.enemy_manager)
        self.strike_zone.set_offence(True)
        self.flg_end = False
        self.diamond = Diamond()
        self.message = "Play Ball"
        self.console = Console()

    def update(self):
        if self.flg_end:
            self.console.update()
            return
        self.cursor.update()
        if self.cursor.get_action() == Action.NEXT:
            pitch_result, hit_base_num = self.strike_zone.get_pitch_result()
            self._set_message(pitch_result, hit_base_num)
            is_run = self.count.pitch(pitch_result)
            base_run_num = 1 if is_run and pitch_result == AtBat.BALL else hit_base_num
            self.diamond.put_runner(base_run_num)
            self.score[self.player][-1] = self.diamond.get_score()
            if self.count.get_out() >= 3:
                self._update_inning()
            self.cursor = Cursor()
            self.enemy_manager.set_info(
                *self.count.get_info(), self.diamond.get_runner(), self.score
            )
        elif self.cursor.get_action() == Action.STRIKE_ZONE:
            self.strike_zone.set(self.cursor.get_select_pos())

    def _update_inning(self):
        self.player = Player.U if self.player == Player.E else Player.E
        self.count = Count()
        self.diamond = Diamond()
        if all(len(self.score[player]) == 9 for player in Player):
            self.flg_end = True
            self.message = "Game Over"
            self.diamond.set_game_over()
            self.player = None
            self.console.set_scores(
                sum(self.score[Player.U]), sum(self.score[Player.E])
            )
        else:
            self.score[self.player].append(0)
            self.strike_zone.set_offence(self.player == Player.U)

    def draw(self):
        self.view.clear()
        self._draw_frame()
        self._draw_score_board()
        self.count.draw()
        self.diamond.draw()
        self.strike_zone.draw()
        self._draw_message()
        self.cursor.draw()
        if self.flg_end:
            self.console.draw()

    def _draw_frame(self):
        self.view.draw_tilemap()
        for i in range(1, 10):
            self.view.draw_text(
                GameObject.SCORE_BOARD_OFFSET_X + i * 8 + 2,
                GameObject.SCORE_BOARD_OFFSET_Y + 2,
                str(i),
            )
        self.view.draw_text(
            GameObject.SCORE_BOARD_OFFSET_X + 10 * 8 + 2,
            GameObject.SCORE_BOARD_OFFSET_Y + 2,
            "T",
        )

    def _draw_score_board(self):
        for y, p in [(1 * 8, Player.U), (2 * 8, Player.E)]:
            self.view.draw_text(
                GameObject.SCORE_BOARD_OFFSET_X + 2,
                GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                p.name,
            )
            for i, score in enumerate(self.score[p]):
                is_offence = p == self.player and len(self.score[p]) - 1 == i
                self.view.draw_text(
                    GameObject.SCORE_BOARD_OFFSET_X + (i + 1) * 8 + 2,
                    GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                    str(score),
                    Color.LIGHT_RED if is_offence else Color.WHITE,
                )
            self.view.draw_text(
                GameObject.SCORE_BOARD_OFFSET_X + 10 * 8 + 2,
                GameObject.SCORE_BOARD_OFFSET_Y + y + 2,
                str(sum(self.score[p])),
            )

    def _draw_message(self):
        self.view.draw_text(
            GameObject.MESSAGE_OFFSET_X,
            GameObject.MESSAGE_OFFSET_Y,
            self.message,
        )

    def _set_message(self, pitch_result, hit_base_num):
        message_map = {
            AtBat.BALL: "Ball",
            AtBat.STRIKE: "Strike",
            AtBat.FAUL: "Faul",
            AtBat.HIT: "Hit",
            AtBat.OUT: "Catch Fly OUT",
        }
        if hit_base_num == 4:
            self.message = "Home Run"
        elif pitch_result == AtBat.HIT:
            self.message = f"{hit_base_num} Base Hit"
        else:
            self.message = message_map[pitch_result]

    def is_reset(self):
        return self.console.is_tap()


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        pyxel.init(
            PyxelView.MONITOR_WIDTH, PyxelView.MONITOR_HEIGHT, title="Pyxel BaseBall"
        )
        self.pyxel.load("map_tile.pyxres")
        self.pyxel.mouse(True)

        self.game_core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self.game_core.update()
        if self.game_core.is_reset():
            self.game_core = GameCore()

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
