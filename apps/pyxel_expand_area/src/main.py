# title: pyxel expand area
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum

try:
    from .map_generator import AreaBlockAlgorithmGenerator  # pylint: disable=C0413
except ImportError:
    from map_generator import AreaBlockAlgorithmGenerator  # pylint: disable=C0413


class IView(ABC):
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_circ(self, x, y, r, col, is_fill):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col, is_fill):
        pass

    @abstractmethod
    def draw_image(self, x, y, src_x, src_y, revert, is_trans):
        pass

    @abstractmethod
    def clear(self, x, y):
        pass

    @abstractmethod
    def get_frame(self):
        pass

    @classmethod
    def create(cls, screen_width, screen_height):
        return cls(screen_width, screen_height)

    def get_screen_size(self):
        return self.screen_width, self.screen_height


class Color(Enum):
    BLACK = 0
    WHITE = 7
    DARK_BLUE = 1
    GREEN = 3


class PyxelView(IView):
    def __init__(self, screen_width, screen_height):
        super().__init__(screen_width, screen_height)
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_circ(self, x, y, r, col, is_fill):
        param = (x, y, r, col.value)
        if is_fill:
            self.pyxel.circ(*param)
        else:
            self.pyxel.circb(*param)

    def draw_rect(self, x, y, w, h, col, is_fill):
        param = (x, y, w, h, col.value)
        if is_fill:
            self.pyxel.rect(*param)
        else:
            self.pyxel.rectb(*param)

    def draw_image(self, x, y, src_x, src_y, revert, is_trans):
        options = (
            x,
            y,
            0,
            src_x * 8,
            src_y * 8,
            -8 if revert else 8,
            8,
        )
        if is_trans:
            self.pyxel.blt(*options, colkey=Color.BLACK.value)
        else:
            self.pyxel.blt(*options)

    def clear(self, x, y):
        self.pyxel.camera(x - self.screen_width // 2, y - self.screen_height // 2)
        self.pyxel.cls(0)

    def get_frame(self):
        return self.pyxel.frame_count


class IInput(ABC):
    @abstractmethod
    def is_click(self):
        pass

    @abstractmethod
    def is_release(self):
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

    def is_release(self):
        return self.pyxel.btnr(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_x(self):
        return self.pyxel.mouse_x

    def get_mouse_y(self):
        return self.pyxel.mouse_y


class IUnitView(ABC):
    @abstractmethod
    def draw_unit(self, x, y, image_x, image_y, face, direct, is_damaged):
        pass

    @classmethod
    def create(cls):
        return cls()


class Direct(Enum):
    NUTRAL = (0, 0)
    RIGHT = (1, 0)
    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)


class PyxelUnitView(IUnitView):
    SIZE = 8

    def __init__(self):
        super().__init__()
        self.view = PyxelView.create(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)

    def draw_unit(self, x, y, image_x, image_y, face, direct, is_damaged):
        if is_damaged and (self.view.get_frame() // 5) % 2 == 0:
            return
        if direct == Direct.NUTRAL:
            moved_x = image_x if (self.view.get_frame() // 10) % 2 == 0 else image_x + 2
        else:
            image_frame = (self.view.get_frame() // 5) % 4
            moved_x = image_x + (image_frame if image_frame != 2 else 0)
        self.view.draw_image(
            x - self.SIZE // 2,
            y - self.SIZE // 2,
            moved_x,
            image_y,
            face == Direct.LEFT,
            False,
        )


class GameObject(ABC):
    SCREEN_WIDTH = 240
    SCREEN_HEIGHT = 320

    def __init__(self):
        self.view = PyxelView.create(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        self.unit_view = PyxelUnitView.create()
        self.input = PyxelInput.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class Unit(GameObject):
    I_FRAMES = 40
    LETTER_SIZE = 2
    STAT_PADDING = (0, PyxelUnitView.SIZE + LETTER_SIZE)

    def __init__(self, x, y, image_x, image_y):
        super().__init__()
        self.pos = (x, y)
        self.face = Direct.RIGHT
        self.mv_dir = Direct.NUTRAL
        self.mv_is_blocked = False
        self.image_pos = (image_x, image_y)
        self.damaged_frames = 0
        self.stat = None

    def draw(self):
        self.unit_view.draw_unit(
            *self.pos,
            *self.image_pos,
            self.face,
            self.mv_dir,
            self.damaged_frames > 0,
        )
        if self.stat is not None:
            self.view.draw_text(
                *tuple(
                    p - d - l
                    for p, d, l in zip(
                        self.get_pos(),
                        self.STAT_PADDING,
                        (len(self.stat) * self.LETTER_SIZE, 0),
                    )
                ),
                self.stat,
            )

    def update(self):
        if self.damaged_frames > 0:
            self.damaged_frames -= 1
        if self.mv_dir != Direct.NUTRAL and not self.mv_is_blocked:
            self.pos = self.get_next_pos(self.mv_dir)

    def move(self, direct, is_blocked):
        self.mv_dir = direct
        self.mv_is_blocked = is_blocked
        self.face = direct if direct in {Direct.RIGHT, Direct.LEFT} else self.face

    def get_next_pos(self, direct):
        return tuple(p + d for p, d in zip(self.pos, direct.value))

    def get_pos(self):
        return self.pos

    def set_damaged(self) -> bool:
        if not self.is_in_i_frames():
            self.damaged_frames = self.I_FRAMES
            return True
        return False

    def is_in_i_frames(self):
        return self.damaged_frames > 0

    def set_stat(self, stat):
        self.stat = str(stat)


class Mob(Unit):
    I_FRAMES = 40

    def __init__(self, x, y, image_x, image_y):
        super().__init__(x, y, image_x, image_y)
        self.hp = self.max_hp = 1
        self.power = 0

    def set_damaged(self):
        if super().set_damaged():
            self.hp -= 1

    def is_killed(self):
        return not self.is_in_i_frames() and self.hp <= 0

    def get_status(self):
        return self.hp, self.max_hp, self.power

    def set_power(self, power):
        self.power = power

    def get_power(self):
        return self.power

    def set_hp(self, hp):
        self.hp = self.max_hp = hp

    def battle(self, unit: "Mob"):
        if self.power > unit.get_power():
            unit.set_damaged()
        else:
            self.set_damaged()


class Player(Mob):
    IMAGE_POS = (1, 0)
    START_COIN_NUM = 30

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.set_power(1)
        self.set_hp(3)
        self.coin_num = self.START_COIN_NUM

    def get_coin_num(self):
        return self.coin_num

    def add_coin(self, num):
        self.coin_num += num

    def add_power(self, num):
        self.set_power(self.get_power() + num)


class Item(Unit):
    def __init__(self, x, y, image_x, image_y):
        super().__init__(x, y, image_x, image_y)
        self.num = 0
        self.map_generator = AreaBlockAlgorithmGenerator.create()

    def get_num(self):
        return self.num

    def set_num(self, num):
        self.num = num

    def get_area_pos(self):
        return tuple(p // Area.SIZE for p in self.get_pos())


class Fee(Item):
    IMAGE_POS = (1, 3)

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.set_num(self.map_generator.get_fee_num(*self.get_area_pos()))

    def set_num(self, num):
        super().set_num(num)
        self.set_stat(num)


class Coin(Item):
    IMAGE_POS = (1, 4)

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.set_num(self.map_generator.get_coin_num(*self.get_area_pos()))


class Weapon(Item):
    IMAGE_POS = (1, 5)

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.set_num(self.map_generator.get_weapon_power(*self.get_area_pos()))


class Enemy(Mob):
    IMAGE_POS = (1, 1)
    STOP_DISTANCE_AREA = 3

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.area_axis_pos = tuple(p // Area.SIZE for p in (x, y))
        map_generator = AreaBlockAlgorithmGenerator.create()
        self.set_power(map_generator.get_enemy_power(*self.area_axis_pos))
        self.set_hp(1)
        self.set_stat(self.get_power())

    def spot(self, x, y):
        direct = self._get_spot_direct(x, y)
        next_pos = self.get_next_pos(direct)
        is_in_area = all(
            a * Area.SIZE <= p < (a + 1) * Area.SIZE
            for a, p in zip(self.area_axis_pos, next_pos)
        )
        self.move(direct, not is_in_area)

    def _get_spot_direct(self, x, y):
        if self.is_in_i_frames():
            return Direct.NUTRAL
        distance_x = abs(x - self.pos[0])
        distance_y = abs(y - self.pos[1])
        if any(
            d // Area.SIZE >= self.STOP_DISTANCE_AREA for d in (distance_x, distance_y)
        ):
            return Direct.NUTRAL
        if distance_x >= distance_y:
            return Direct.RIGHT if self.pos[0] < x else Direct.LEFT
        return Direct.DOWN if self.pos[1] < y else Direct.UP

    def set_power(self, power):
        super().set_power(power)
        self.set_stat(power)


class Boss(Mob):
    IMAGE_POS = (1, 2)

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.area_axis_pos = tuple(p // Area.SIZE for p in (x, y))
        map_generator = AreaBlockAlgorithmGenerator.create()
        self.set_power(map_generator.get_boss_power())
        self.set_hp(1)
        self.set_stat(self.get_power())

    def set_power(self, power):
        super().set_power(power)
        self.set_stat(power)


class Spawner(Unit):
    IMAGE_POS = (1, 6)
    START_SPAWN_INTERVAL = 100

    def __init__(self, x, y):
        super().__init__(x, y, *self.IMAGE_POS)
        self.power = AreaBlockAlgorithmGenerator.create().get_spawner_power(
            *tuple(p // Area.SIZE for p in (x, y))
        )
        self.spawn_interval = self.START_SPAWN_INTERVAL

    def update(self):
        super().update()
        self.spawn_interval -= 1

    def set_power(self, power):
        self.power = power

    def get_power(self):
        return self.power

    def spawn(self):
        if self.spawn_interval <= 0:
            enemy = Enemy(*self.get_pos())
            enemy.set_power(self.get_power())
            self.spawn_interval = self.START_SPAWN_INTERVAL
            return enemy
        return None


class Area(GameObject):
    SIZE = 40

    def __init__(self, axis_x, axis_y):
        super().__init__()
        self.axis_pos = (axis_x, axis_y)
        self.unveiled = False

    def draw(self):
        self.view.draw_rect(
            *(a * self.SIZE for a in self.axis_pos),
            self.SIZE,
            self.SIZE,
            Color.GREEN if self.unveiled else Color.DARK_BLUE,
            False,
        )

    def contains(self, x, y) -> bool:
        return all(
            a * self.SIZE <= p < (a + 1) * self.SIZE
            for p, a in zip((x, y), self.axis_pos)
        )

    def unveil(self):
        self.unveiled = True


class Field(GameObject):
    def __init__(self):
        super().__init__()
        map_generator = AreaBlockAlgorithmGenerator.create()
        start_pos = map_generator.get_start_pos()
        boss_pos = map_generator.get_boss_pos()
        self.boss_pos = boss_pos
        self.player = Player(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in start_pos))
        self.area_map = {start_pos: Area(*start_pos), boss_pos: Area(*boss_pos)}
        self.area_map[boss_pos].unveil()
        self.unit_map = {
            boss_pos: Boss(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in boss_pos))
        }
        self.spawner_map = {}
        self._unveil(*start_pos)
        self.operation_dir = Direct.NUTRAL
        self.area_x_padding, self.area_y_padding = tuple(
            size // 2 // Area.SIZE + 1
            for size in [self.SCREEN_WIDTH, self.SCREEN_HEIGHT]
        )
        self.flg_clear = False
        self.flg_no_coin = False

    def update(self):
        for pos, unit in self._get_in_screen_area_map(self.unit_map).items():
            if isinstance(unit, Enemy):
                unit.spot(*self.player.get_pos())
            unit.update()
            if isinstance(unit, Mob) and unit.is_killed():
                del self.unit_map[pos]
                if isinstance(unit, Boss):
                    self.flg_clear = True
                else:
                    self.unit_map[pos] = Coin(*unit.get_pos())
                self.set_no_coin_flg()
        for pos, unit in self._get_in_screen_area_map(self.spawner_map).items():
            unit.update()
            if isinstance(unit, Spawner) and pos not in self.unit_map:
                spawn_unit = unit.spawn()
                if spawn_unit is not None:
                    self.unit_map[pos] = spawn_unit
        self.player.move(self.operation_dir, not self._contains_next_player_pos())
        self.player.update()
        self._hit()

    def draw(self):
        unit_draw_pos_list = []
        for pos, area in self._get_in_screen_area_map(self.area_map).items():
            area.draw()
            unit_draw_pos_list.append(pos)
        for pos in unit_draw_pos_list:
            if pos in self.spawner_map:
                self.spawner_map[pos].draw()
            if pos in self.unit_map:
                self.unit_map[pos].draw()
        self.player.draw()

    def _get_in_screen_area_map(self, targer_map):
        area_axis = tuple(i // Area.SIZE for i in self.player.get_pos())
        return {
            pos: v
            for pos, v in targer_map.items()
            if all(
                a - p <= pos <= a + p
                for a, p, pos in zip(
                    area_axis, (self.area_x_padding, self.area_y_padding), pos
                )
            )
        }

    def operate(self, direct):
        self.operation_dir = direct

    def _contains_next_player_pos(self) -> bool:
        next_pos = self.player.get_next_pos(self.operation_dir)
        area_axis = tuple(i // Area.SIZE for i in next_pos)
        return area_axis in self.area_map and self.area_map[area_axis].contains(
            *next_pos
        )

    def _unveil(self, axis_x, axis_y):
        if (axis_x, axis_y) not in self.area_map:
            return
        for d in Direct:
            pos = tuple(p + d for p, d in zip((axis_x, axis_y), d.value))
            if d == Direct.NUTRAL:
                self.area_map[(axis_x, axis_y)].unveil()
            elif pos not in self.area_map:
                self.area_map[pos] = Area(*pos)
                fee = Fee(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in pos))
                if fee.get_num() > 0:
                    self.unit_map[pos] = fee

    def _hit(self):
        for pos, unit in self._get_hit_units().items():
            if isinstance(unit, Fee):
                if unit.get_num() <= self.player.get_coin_num():
                    self.player.add_coin(unit.get_num() * -1)
                    del self.unit_map[pos]
                    self._unveil(*pos)
                    spawn_unit = self._spawn(pos)
                    if isinstance(spawn_unit, Spawner):
                        self.spawner_map[pos] = spawn_unit
                    elif spawn_unit is not None:
                        self.unit_map[pos] = spawn_unit
                    self.set_no_coin_flg()
            elif isinstance(unit, Coin):
                del self.unit_map[pos]
                self.player.add_coin(unit.get_num())
                self.set_no_coin_flg()
            elif isinstance(unit, Weapon):
                del self.unit_map[pos]
                self.player.add_power(unit.get_num())
            elif isinstance(unit, (Enemy, Boss)):
                unit.battle(self.player)

    def _spawn(self, area_axis):
        center_pos = tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis)
        player_pos = self.player.get_pos()
        diff = tuple(p - c for p, c in zip(player_pos, center_pos))
        param = tuple(c - d for c, d in zip(center_pos, diff))
        spawner = Spawner(*center_pos)
        if spawner.get_power() > 0:
            return spawner
        enemy = Enemy(*param)
        if enemy.get_power() > 0:
            return enemy
        weapon = Weapon(*param)
        if weapon.get_num() > 0:
            return weapon
        return None

    def _get_hit_units(self):
        ret = {}
        player_pos = self.player.get_pos()
        area_axis = tuple(i // Area.SIZE for i in player_pos)
        for pos, unit in self.unit_map.items():
            if all(abs(p - m) <= 1 for p, m in zip(area_axis, pos)):
                unit_pos = unit.get_pos()
                if all(
                    abs(p - m) < PyxelUnitView.SIZE
                    for p, m in zip(player_pos, unit_pos)
                ):
                    ret[pos] = unit
        return ret

    def get_center_pos(self):
        return self.player.get_pos()

    def get_player_status(self):
        return *self.player.get_status(), self.player.get_coin_num()

    def is_clear(self):
        return self.flg_clear

    def set_no_coin_flg(self):
        fee_list = [
            unit.get_num() for unit in self.unit_map.values() if isinstance(unit, Fee)
        ]
        self.flg_no_coin = (
            len(fee_list) > 0
            and self.player.get_coin_num() < min(fee_list)
            and len(
                list(
                    unit
                    for unit in self.unit_map.values()
                    if isinstance(unit, (Enemy, Coin))
                )
            )
            == 0
            and not bool(
                set(
                    tuple(p + d for p, d in zip(self.boss_pos, d.value))
                    for d in Direct
                    if d != Direct.NUTRAL
                )
                & self.area_map.keys(),
            )
            and len(self.spawner_map) == 0
        )

    def is_no_coin(self):
        return self.flg_no_coin


class ScreenObject(GameObject):
    def __init__(self):
        super().__init__()
        self.center_pos = tuple(i // 2 for i in self.view.get_screen_size())

    def get_draw_pos(self, padding_x, padding_y):
        return tuple(
            c - l // 2 + p
            for c, l, p in zip(
                self.center_pos, self.view.get_screen_size(), (padding_x, padding_y)
            )
        )

    def set_center(self, x, y):
        self.center_pos = (x, y)


class Status(ScreenObject):
    HAERT_IMAGE_POS = (1, 7)
    LOSS_HAERT_IMAGE_POS = (2, 7)
    POWER_PADDING = 40
    COIN_PADDING = 80

    def __init__(self):
        super().__init__()
        self.stat = (0, 0, 0, 0)

    def draw(self):
        loss_heart_num = self.stat[1] - self.stat[0]
        rest_heart_num = self.stat[0]
        for num, pad, image_pos in [
            (loss_heart_num, 0, self.LOSS_HAERT_IMAGE_POS),
            (rest_heart_num, loss_heart_num, self.HAERT_IMAGE_POS),
        ]:
            for i in range(num):
                self.view.draw_image(
                    *self.get_draw_pos(1 + (i + pad) * 9, 2),
                    *image_pos,
                    False,
                    False,
                )
        for pad, image_pos, num in [
            (self.POWER_PADDING, Weapon.IMAGE_POS, self.stat[2]),
            (self.COIN_PADDING, Coin.IMAGE_POS, self.stat[3]),
        ]:
            self.view.draw_image(
                *self.get_draw_pos(1 + pad, 1),
                *image_pos,
                False,
                False,
            )
            self.view.draw_text(
                *self.get_draw_pos(1 + pad + 9, 3),
                str(num),
            )

    def set_stat(self, hp, hp_max, power, coin):
        self.stat = (hp, hp_max, power, coin)

    def is_dead(self):
        return self.stat[0] <= 0


class Controller(ScreenObject):
    def __init__(self):
        super().__init__()
        self.direct = Direct.NUTRAL
        self.is_tap_on = False
        self.start_pos = None

    def draw(self):
        if self.is_tap_on:
            draw_pos = self.get_draw_pos(*self.start_pos)
            self.view.draw_circ(*draw_pos, 20, Color.BLACK, True)
            self.view.draw_circ(*draw_pos, 20, Color.WHITE, False)
            self.view.draw_circ(
                *(s + d * 10 for s, d in zip(draw_pos, self.direct.value)),
                10,
                Color.WHITE,
                True,
            )

    def update(self):
        super().update()
        if self.input.is_click():
            self.is_tap_on = True
            self.start_pos = (self.input.get_mouse_x(), self.input.get_mouse_y())
        elif self.input.is_release():
            self.direct = Direct.NUTRAL
            self.is_tap_on = False
        if self.is_tap_on:
            self.direct = self._select_direct()

    def _select_direct(self):
        if self.input.get_mouse_x() is None or self.input.get_mouse_y() is None:
            return Direct.NUTRAL
        x_pos_diff, y_pos_diff = (
            i - j
            for i, j in zip(
                (self.input.get_mouse_x(), self.input.get_mouse_y()), self.start_pos
            )
        )
        if abs(x_pos_diff) <= 20 and abs(y_pos_diff) <= 20:
            return Direct.NUTRAL
        if abs(x_pos_diff) < abs(y_pos_diff):
            if y_pos_diff < 0:
                return Direct.UP
            return Direct.DOWN
        if x_pos_diff < 0:
            return Direct.LEFT
        return Direct.RIGHT

    def get_direct(self):
        return self.direct


class Console(ScreenObject):
    CONSOLE_RECT = (GameObject.SCREEN_WIDTH // 2 - 40, 60, 80, 30)

    def __init__(self):
        super().__init__()
        self.flg_is_tap = False
        self.message = ""

    def draw(self):
        draw_pos = self.get_draw_pos(*self.CONSOLE_RECT[0:2])
        self.view.draw_rect(*draw_pos, *self.CONSOLE_RECT[2:4], Color.GREEN, True)
        self.view.draw_rect(*draw_pos, *self.CONSOLE_RECT[2:4], Color.WHITE, False)
        for message, y_pos in [(self.message, 5), ("Tap to Continue", 20)]:
            self.view.draw_text(
                draw_pos[0] + 10,
                draw_pos[1] + y_pos,
                message,
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

    def set_message(self, message):
        self.message = message


class GameCore:
    def __init__(self):
        self.view = PyxelView.create(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        self.controller = Controller()
        self.status = Status()
        self.field = Field()
        self.console = Console()
        self.status.set_stat(*self.field.get_player_status())

    def update(self):
        if self.status.is_dead() or self.field.is_clear() or self.field.is_no_coin():
            self.console.update()
        else:
            self.controller.update()
            self.field.operate(self.controller.get_direct())
            self.field.update()

    def draw(self):
        center_pos = self.field.get_center_pos()
        self._set_center(center_pos)
        self.view.clear(*center_pos)
        self.field.draw()
        self.status.set_stat(*self.field.get_player_status())
        self.status.draw()
        if self.status.is_dead() or self.field.is_no_coin():
            self.console.set_message("Game Over")
            self.console.draw()
        elif self.field.is_clear():
            self.console.set_message("Game Clear")
            self.console.draw()
        else:
            self.controller.draw()

    def _set_center(self, center_pos):
        self.console.set_center(*center_pos)
        self.controller.set_center(*center_pos)
        self.status.set_center(*center_pos)

    def is_reset(self):
        return self.console.is_tap()


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        pyxel.init(
            GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT, title="Pyxel Expand Area"
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
