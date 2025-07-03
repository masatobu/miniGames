# title: pyxel convert send
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum
import random


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_tilemap(self):
        pass

    @abstractmethod
    def draw_image(self, x, y, src_tile_x, src_tile_y, direct):
        pass

    @abstractmethod
    def draw_rect(self, x, y, width, height, color, is_fill):
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def set_clip(self, rect):
        pass

    @abstractmethod
    def set_pal(self, params):
        pass

    @classmethod
    def create(cls):
        return cls()


class Color(Enum):
    RED = 8
    BLUE = 12
    WHITE = 7
    NODE_BLUE = 12
    NODE_RED = 8
    NODE_GREEN = 11
    NODE_YELLOW = 10
    NODE_ORANGE = 9
    NODE_GRAY = 13
    PLAYER = 6
    ENEMY = 14


class Direct(Enum):
    RIGHT = (1, 0)
    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)


class PyxelView(IView):
    TILE_MAP_WIDTH = 8 * (8 * 2)
    TILE_MAP_HEIGHT = 8 * (8 * 2 - 2)

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_tilemap(self):
        self.pyxel.bltm(0, 0, 0, 0, 0, self.TILE_MAP_WIDTH, self.TILE_MAP_HEIGHT)

    def draw_image(self, x, y, src_tile_x, src_tile_y, direct):
        degree_map = {
            Direct.RIGHT: 0,
            Direct.UP: 270,
            Direct.LEFT: 180,
            Direct.DOWN: 90,
        }
        self.pyxel.blt(
            x,
            y,
            0,
            src_tile_x * 8,
            src_tile_y * 8,
            8,
            8,
            colkey=0,
            rotate=degree_map[direct],
        )

    def draw_rect(self, x, y, width, height, color, is_fill):
        param = {"x": x, "y": y, "w": width, "h": height, "col": color.value}
        if is_fill:
            self.pyxel.rect(**param)
        else:
            self.pyxel.rectb(**param)

    def clear(self):
        self.pyxel.cls(0)

    def set_clip(self, rect):
        if rect is None:
            self.pyxel.clip()
        else:
            self.pyxel.clip(*rect)

    def set_pal(self, params):
        self.pyxel.pal(*[col.value for col in params])


class Image(Enum):
    PLAYER = (4, 1)
    PLAYER_BULLET = (5, 0)
    CURVE = (5, 1)
    CURVE_REV = (5, 2)
    CONVERT = (6, 1)
    SPLIT = (6, 2)
    MERGE = (7, 2)
    ENEMY = (7, 1)
    ENEMY_BULLET = (7, 0)


class Node(Enum):
    UNIT_PLAYER = Image.PLAYER
    UNIT_CURVE = Image.CURVE
    UNIT_CURVE_REV = Image.CURVE_REV
    UNIT_SPLIT = Image.SPLIT
    UNIT_CONVERT = Image.CONVERT
    UNIT_MERGE = Image.MERGE
    UNIT_ENEMY = Image.ENEMY


class IFieldView(ABC):
    @abstractmethod
    def draw_node(self, tile_x, tile_y, node, direct, color):
        pass

    @abstractmethod
    def draw_object(self, x, y, image, color):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelFieldView(IFieldView):
    FIELD_TILE_WIDTH = 12
    FIELD_TILE_HEIGHT = 12
    FIELD_OFFSET_X = 8
    FIELD_OFFSET_Y = 8
    FIELD_WIDTH = 8 * FIELD_TILE_WIDTH
    FIELD_HEIGHT = 8 * FIELD_TILE_HEIGHT
    NODE_BASE_COLOR = Color.WHITE

    def __init__(self):
        super().__init__()
        self.view = PyxelView.create()

    def _draw(self, params, color):
        if color is not None:
            self.view.set_pal([self.NODE_BASE_COLOR, color])
        self.view.draw_image(*params)
        if color is not None:
            self.view.set_pal([])

    def draw_node(self, tile_x, tile_y, node, direct, color):
        self._draw(
            (
                8 * tile_x + self.FIELD_OFFSET_X,
                8 * tile_y + self.FIELD_OFFSET_Y,
                *node.value.value,
                direct,
            ),
            color,
        )

    def draw_object(self, x, y, image, color):
        self._draw(
            (
                x - 8 // 2 + self.FIELD_OFFSET_X,
                y - 8 // 2 + self.FIELD_OFFSET_Y,
                *image.value,
                Direct.RIGHT,
            ),
            color,
        )

    @classmethod
    def get_rect(cls):
        return cls.FIELD_OFFSET_X, cls.FIELD_OFFSET_Y, cls.FIELD_WIDTH, cls.FIELD_HEIGHT


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
    MONITOR_HEIGHT = PyxelView.TILE_MAP_HEIGHT + 8
    MONITOR_WIDTH = PyxelView.TILE_MAP_WIDTH

    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class FieldObject(GameObject):
    def __init__(self):
        super().__init__()
        self.field_view = PyxelFieldView.create()


class FieldNode(FieldObject):
    def __init__(self, tile_x, tile_y, node):
        super().__init__()
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.node = node
        self.direct = Direct.RIGHT
        self.bullet_cls = Bullet
        self.color = None

    def draw(self):
        self.field_view.draw_node(
            self.tile_x, self.tile_y, self.node, self.direct, self.color
        )

    @classmethod
    def node_factory(cls, tile_x, tile_y, node):
        node_class_map = {
            Node.UNIT_PLAYER: UnitPlayer,
            Node.UNIT_CURVE: Curve,
            Node.UNIT_CURVE_REV: Curve,
            Node.UNIT_CONVERT: Convert,
            Node.UNIT_SPLIT: Split,
            Node.UNIT_MERGE: Merge,
        }
        node_cls = node_class_map.get(node)
        param = [tile_x, tile_y]
        if node in [Node.UNIT_CURVE, Node.UNIT_CURVE_REV]:
            param += [node == Node.UNIT_CURVE_REV]
        return node_cls(*param) if node_cls is not None else None

    def shot(self, direct=None, color=None):
        d = direct.value if direct is not None else self.direct.value
        return self.bullet_cls(
            self.tile_x + d[0],
            self.tile_y + d[1],
            direct if direct is not None else self.direct,
            self.color if self.color is not None else color,
        )

    @abstractmethod
    def mainte(self):
        pass

    def get_tile_pos(self):
        return self.tile_x, self.tile_y


class Unit(FieldNode):
    def __init__(self, tile_x, tile_y, unit):
        super().__init__(tile_x, tile_y, unit)
        self.interval = 0
        self.max_interval = 0
        self.hp = 0

    def shot(self, direct=None, color=None):
        if self.interval < self.max_interval:
            self.interval += 1
            return None
        else:
            self.interval = 0
            return super().shot(direct, color)

    def mainte(self):
        pass

    def hit(self, bullet):
        if not isinstance(bullet, self.bullet_cls):
            self.hp -= 1

    def is_death(self):
        return self.hp <= 0


class UnitPlayer(Unit):
    SHOT_INTERVAL = 10  # over tile_width / bullet_speed
    MAX_HP = 10

    def __init__(self, tile_x, tile_y):
        super().__init__(tile_x, tile_y, Node.UNIT_PLAYER)
        self.max_interval = self.SHOT_INTERVAL
        self.bullet_cls = BulletPlayer
        self.hp = self.MAX_HP
        self.color = Color.NODE_BLUE


class UnitEnemy(Unit):
    SHOT_INTERVAL = 20  # over tile_width / bullet_speed
    MAX_HP = 3
    COLOR_LIST = [
        Color.NODE_RED,
        Color.NODE_BLUE,
        Color.NODE_GREEN,
        Color.NODE_YELLOW,
        Color.NODE_ORANGE,
    ]

    def __init__(self, tile_x, tile_y, color_num=2, split_num=2):
        super().__init__(tile_x, tile_y, Node.UNIT_ENEMY)
        self.max_interval = self.SHOT_INTERVAL
        self.direct = Direct.LEFT
        self.bullet_cls = BulletEnemy
        self.hp = self.MAX_HP
        self.color_num = color_num
        self.split_num = split_num
        self.color = self.get_color()

    def hit(self, bullet):
        if self.color == bullet.color:
            super().hit(bullet)

    def get_color(self):
        return self.COLOR_LIST[(self.tile_y // self.split_num) % self.color_num]


class Curve(FieldNode):
    CYCLE_MAP = {
        Direct.UP: Direct.RIGHT,
        Direct.RIGHT: Direct.DOWN,
        Direct.DOWN: Direct.LEFT,
        Direct.LEFT: Direct.UP,
    }
    REV_CYCLE_MAP = {
        Direct.UP: Direct.LEFT,
        Direct.LEFT: Direct.DOWN,
        Direct.DOWN: Direct.RIGHT,
        Direct.RIGHT: Direct.UP,
    }

    def __init__(self, tile_x, tile_y, rev):
        super().__init__(
            tile_x, tile_y, Node.UNIT_CURVE_REV if rev else Node.UNIT_CURVE
        )
        self.cycle_map = self.REV_CYCLE_MAP if rev else self.CYCLE_MAP
        self.bullet_cls = BulletPlayer

    def reshot(self, bullet):
        if (
            not isinstance(bullet, self.bullet_cls)
            or self.cycle_map[bullet.direct] != self.direct
        ):
            return []
        return [super().shot(color=bullet.color)]

    def mainte(self):
        self.direct = self.CYCLE_MAP[self.direct]


class Convert(FieldNode):
    CYCLE_MAP = {
        Color.NODE_BLUE: Color.NODE_RED,
        Color.NODE_RED: Color.NODE_GREEN,
        Color.NODE_GREEN: Color.NODE_BLUE,
    }

    def __init__(self, tile_x, tile_y):
        super().__init__(tile_x, tile_y, Node.UNIT_CONVERT)
        self.bullet_cls = BulletPlayer
        self.color = Color.NODE_BLUE

    def reshot(self, bullet):
        if not isinstance(bullet, self.bullet_cls):
            return []
        return [super().shot(bullet.direct)]

    def mainte(self):
        self.color = self.CYCLE_MAP[self.color]


class Split(FieldNode):
    CYCLE_MAP = {
        Direct.UP: Direct.RIGHT,
        Direct.RIGHT: Direct.DOWN,
        Direct.DOWN: Direct.LEFT,
        Direct.LEFT: Direct.UP,
    }

    def __init__(self, tile_x, tile_y):
        super().__init__(tile_x, tile_y, Node.UNIT_SPLIT)
        self.bullet_cls = BulletPlayer

    def mainte(self):
        self.direct = self.CYCLE_MAP[self.direct]

    def reshot(self, bullet):
        if (
            not isinstance(bullet, self.bullet_cls)
            or self.CYCLE_MAP[bullet.direct] != self.direct
        ):
            return []
        return [
            super().shot(color=bullet.color),
            super().shot(direct=bullet.direct, color=bullet.color),
        ]


class Merge(FieldNode):
    CYCLE_MAP = {
        Direct.UP: Direct.RIGHT,
        Direct.RIGHT: Direct.DOWN,
        Direct.DOWN: Direct.LEFT,
        Direct.LEFT: Direct.UP,
    }
    ACCEPT_MAP = {
        Direct.UP: [Direct.RIGHT, Direct.LEFT],
        Direct.RIGHT: [Direct.DOWN, Direct.UP],
        Direct.DOWN: [Direct.RIGHT, Direct.LEFT],
        Direct.LEFT: [Direct.DOWN, Direct.UP],
    }
    COLOR_MAP = {
        frozenset([Color.NODE_BLUE, Color.NODE_BLUE]): Color.NODE_BLUE,
        frozenset([Color.NODE_RED, Color.NODE_RED]): Color.NODE_RED,
        frozenset([Color.NODE_GREEN, Color.NODE_GREEN]): Color.NODE_GREEN,
        frozenset([Color.NODE_RED, Color.NODE_GREEN]): Color.NODE_YELLOW,
        frozenset([Color.NODE_RED, Color.NODE_YELLOW]): Color.NODE_ORANGE,
    }

    def __init__(self, tile_x, tile_y):
        super().__init__(tile_x, tile_y, Node.UNIT_MERGE)
        self.bullet_cls = BulletPlayer
        self.buffer = None

    def mainte(self):
        self.direct = self.CYCLE_MAP[self.direct]

    def reshot(self, bullet):
        if (
            not isinstance(bullet, self.bullet_cls)
            or bullet.direct not in self.ACCEPT_MAP[self.direct]
        ):
            return []
        if self.buffer is None:
            self.buffer = bullet
            return []
        merge_color = self.COLOR_MAP.get(
            frozenset([self.buffer.color, bullet.color]), Color.NODE_GRAY
        )
        self.buffer = None
        return [super().shot(color=merge_color)]


class Bullet(FieldObject):
    @staticmethod
    def get_start_pos(pos):
        return 8 // 2 if pos == 0 else 0 if pos > 0 else 8 - 1

    def __init__(self, tile_x, tile_y, d, color):
        super().__init__()
        self.x = tile_x * 8 + self.get_start_pos(d.value[0])
        self.y = tile_y * 8 + self.get_start_pos(d.value[1])
        self.direct = d
        self.color = color

    def update(self):
        self.x, self.y = self.x + self.direct.value[0], self.y + self.direct.value[1]

    def draw(self):
        self.field_view.draw_object(
            self.x,
            self.y,
            self.image,
            self.color,
        )

    def get_pos(self):
        return self.x, self.y

    def get_tile_pos(self):
        return tuple(p // 8 for p in self.get_pos())


class BulletPlayer(Bullet):
    def __init__(self, tile_x, tile_y, d, color=Color.NODE_BLUE):
        super().__init__(tile_x, tile_y, d, color)
        self.image = Image.PLAYER_BULLET


class BulletEnemy(Bullet):
    def __init__(self, tile_x, tile_y, d, color=Color.NODE_BLUE):
        super().__init__(tile_x, tile_y, d, color)
        self.image = Image.ENEMY_BULLET


class Action(Enum):
    FIELD = (0, 0)
    CURVE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 0)
    CURVE_REV = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 2)
    CONVERT = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 4)
    SPLIT = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 6)
    MERGE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 8)
    DELETE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 11)


class Field(FieldObject):
    def __init__(self, enemy_split_num, enemy_color_num):
        super().__init__()
        self.enemy_split_num = enemy_split_num
        self.enemy_color_num = enemy_color_num
        unit_player = UnitPlayer(0, self._get_random_new_player_y_pos())
        unit_enemy = UnitEnemy(
            11, self._get_random_new_enemy_y_pos(set())[0], self.enemy_color_num
        )
        self.unit_list = [unit_player, unit_enemy]
        self.bullet_map = {}
        self.node_map = {unit.get_tile_pos(): unit for unit in self.unit_list}

    def _get_random_new_player_y_pos(self):
        return random.randint(0, PyxelFieldView.FIELD_TILE_HEIGHT - 1)

    def update(self):
        self._update_bullet()
        self._update_unit()
        self._shot()

    def _update_unit(self):
        bef_enemies_y_set = self._get_enemies_y_set()
        self.unit_list = [unit for unit in self.unit_list if not unit.is_death()]
        if len(bef_enemies_y_set) > len(self._get_enemies_y_set()):
            append_unit_list = [
                UnitEnemy(11, y, self.enemy_color_num)
                for y in self._get_random_new_enemy_y_pos(bef_enemies_y_set)
            ]
            self.unit_list.extend(append_unit_list)
            for unit in append_unit_list:
                pos = unit.get_tile_pos()
                if pos in self.node_map:
                    raise KeyError(f"node_map already has key: {pos}")
                self.node_map[pos] = unit

    def _get_enemies_y_set(self):
        return {unit.tile_y for unit in self.unit_list if isinstance(unit, UnitEnemy)}

    def _get_random_new_enemy_y_pos(self, enemies_y_set):
        candidate = [
            i
            for i in range(PyxelFieldView.FIELD_TILE_HEIGHT)
            if i % self.enemy_split_num == 0 and i not in enemies_y_set
        ]
        if len(candidate) > 2:
            return random.sample(
                candidate,
                k=2,
            )
        return candidate

    def _update_bullet(self):
        append_bullet = self._update_and_get_new_bullet()
        append_bullet_map = self._get_new_bullet_map(append_bullet)
        self.bullet_map = self._regenerate_bullet_map(append_bullet_map)

    def _is_collied(self, bullet, bullet_set):
        if bullet in bullet_set:
            return False
        else:
            if isinstance(bullet, BulletPlayer):
                return True
            for target in bullet_set:
                if isinstance(target, BulletEnemy) or bullet.color == target.color:
                    return True
            return False

    def _regenerate_bullet_map(self, append_bullet_map):
        bef_collied_map = {
            bullet.get_tile_pos(): {bullet}
            for pos, bullet in self.bullet_map.items()
            if pos in append_bullet_map
            and self._is_collied(bullet, append_bullet_map[pos])
        }
        ret_map = {}
        for pos, bset in append_bullet_map.items():
            remain_set = bset - bef_collied_map.get(pos, set())
            if len(remain_set) == 1:
                ret_map[pos] = next(iter(remain_set))
            else:
                enemy_set = {
                    bullet for bullet in remain_set if isinstance(bullet, BulletEnemy)
                }
                if len(enemy_set) == 1:
                    enemy = next(iter(enemy_set))
                    if not self._is_collied(enemy, bset - enemy_set):
                        ret_map[pos] = enemy
        return ret_map

    def _get_new_bullet_map(self, append_bullet):
        append_bullet_map = {}
        for bullet in append_bullet + list(self.bullet_map.values()):
            pos = bullet.get_tile_pos()
            if (
                -8 < bullet.x < PyxelFieldView.FIELD_WIDTH + 8
                and -8 < bullet.y < PyxelFieldView.FIELD_HEIGHT + 8
                and pos not in self.node_map
            ):
                append_bullet_map[pos] = append_bullet_map.get(pos, set()) | {bullet}
        return append_bullet_map

    def _update_and_get_new_bullet(self):
        append_bullet = []
        for bullet in self.bullet_map.values():
            bullet.update()
            node = self.node_map.get(bullet.get_tile_pos())
            if isinstance(node, (Curve, Convert, Split, Merge)):
                new_bullet_list = node.reshot(bullet)
                append_bullet.extend(new_bullet_list)
            elif isinstance(node, Unit):
                node.hit(bullet)
                if node.is_death():
                    del self.node_map[node.get_tile_pos()]
        return append_bullet

    def _shot(self):
        for unit in self.unit_list:
            shot_bullet = unit.shot()
            if shot_bullet is not None:
                tile_pos = shot_bullet.get_tile_pos()
                if tile_pos not in self.bullet_map:
                    self.bullet_map[tile_pos] = shot_bullet

    def draw(self):
        self.view.draw_tilemap()
        self.view.set_clip(PyxelFieldView.get_rect())
        for bullet in self.bullet_map.values():
            bullet.draw()
        for node in self.node_map.values():
            node.draw()

    def build(self, action, tile_x, tile_y):
        action_node_map = {
            Action.CURVE: Node.UNIT_CURVE,
            Action.CURVE_REV: Node.UNIT_CURVE_REV,
            Action.CONVERT: Node.UNIT_CONVERT,
            Action.SPLIT: Node.UNIT_SPLIT,
            Action.MERGE: Node.UNIT_MERGE,
        }
        if action not in action_node_map or not self.is_able_to_build(tile_x, tile_y):
            return False
        self.node_map[(tile_x, tile_y)] = FieldNode.node_factory(
            tile_x, tile_y, action_node_map[action]
        )
        return True

    def is_able_to_build(self, tile_x, tile_y):
        if tile_x >= PyxelFieldView.FIELD_TILE_WIDTH - 2:
            return False
        check_list = [(tile_x + d.value[0], tile_y + d.value[1]) for d in Direct]
        check_list.append((tile_x, tile_y))
        return not any(pos in self.node_map for pos in check_list)

    def mainte(self, tile_x, tile_y):
        if (tile_x, tile_y) in self.node_map:
            self.node_map[(tile_x, tile_y)].mainte()

    def delete(self, tile_x, tile_y):
        if (tile_x, tile_y) in self.node_map and not issubclass(
            self.node_map[(tile_x, tile_y)].__class__, Unit
        ):
            del self.node_map[(tile_x, tile_y)]

    def get_bullet_count(self):
        total = len(self.bullet_map)
        player_num = len(
            [
                bullet
                for bullet in self.bullet_map.values()
                if isinstance(bullet, BulletPlayer)
            ]
        )
        return player_num, total - player_num


class Cursor(GameObject):
    AVAIL_POS_MAP = {Action.FIELD: PyxelFieldView.get_rect()} | {
        v: (
            v.value[0] * 8 + PyxelFieldView.FIELD_OFFSET_X,
            v.value[1] * 8 + PyxelFieldView.FIELD_OFFSET_Y,
            8,
            8,
        )
        for v in [
            Action.CURVE,
            Action.CURVE_REV,
            Action.CONVERT,
            Action.SPLIT,
            Action.MERGE,
            Action.DELETE,
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
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if x is not None and y is not None:
                for k, v in self.AVAIL_POS_MAP.items():
                    if v[0] <= x < v[0] + v[2] and v[1] <= y < v[1] + v[3]:
                        next_click_pos = (
                            (x - PyxelFieldView.FIELD_OFFSET_X) // 8,
                            (y - PyxelFieldView.FIELD_OFFSET_Y) // 8,
                        )
                        if self.click_pos != next_click_pos:
                            self.is_select = True
                            self.click_pos = next_click_pos
                            return
                        else:
                            self.select_pos = self.click_pos
                            self.select_action = (
                                k
                                if k == Action.FIELD or k != self.select_action
                                else None
                            )
                        break
            self.is_select = False
            self.click_pos = (-1, -1)

    def draw(self):
        draws = []
        if self.select_action not in [None, Action.FIELD]:
            draws.append(
                (*self.AVAIL_POS_MAP[self.select_action][0:2], 8, 8, Color.BLUE, False)
            )
        if self.is_select:
            draws.append(
                (
                    *[
                        r * 8 + o
                        for r, o in zip(
                            self.click_pos,
                            (
                                PyxelFieldView.FIELD_OFFSET_X,
                                PyxelFieldView.FIELD_OFFSET_Y,
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
            self.view.set_clip(None)
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


class GameCore(GameObject):
    GAMA_PARAMS_LIST = [
        (8, 5),
        (2, 2),
        (6, 4),
    ]

    def __init__(self, param_num=0):
        super().__init__()
        self.field = Field(*self.GAMA_PARAMS_LIST[param_num])
        self.cursor = Cursor()

    def update(self):
        self._action()
        self.field.update()

    def _action(self):
        bef_act = self.cursor.get_action()
        self.cursor.update()
        click_pos = self.cursor.get_select_pos()
        if self.cursor.get_action() == Action.FIELD and click_pos is not None:
            if bef_act is None or bef_act == Action.FIELD:
                self.field.mainte(*click_pos)
            elif bef_act == Action.DELETE:
                self.field.delete(*click_pos)
            else:
                self.field.build(bef_act, *click_pos)

    def draw(self):
        self.view.clear()
        self.view.set_clip(None)
        self.field.draw()
        self.cursor.draw()
        self._draw_graph()

    def _draw_graph(self):
        player_count, enemy_count = self.field.get_bullet_count()
        if player_count + enemy_count == 0:
            player_rate = 0.5
        else:
            player_rate = player_count / (player_count + enemy_count)
        self.view.set_clip(None)
        self.view.draw_rect(
            PyxelFieldView.FIELD_OFFSET_X,
            1 * 8 + PyxelFieldView.FIELD_OFFSET_Y + PyxelFieldView.FIELD_HEIGHT,
            int(PyxelFieldView.FIELD_HEIGHT * player_rate),
            2,
            Color.PLAYER,
            True,
        )
        self.view.draw_rect(
            PyxelFieldView.FIELD_OFFSET_X
            + int(PyxelFieldView.FIELD_HEIGHT * player_rate),
            1 * 8 + PyxelFieldView.FIELD_OFFSET_Y + PyxelFieldView.FIELD_HEIGHT,
            PyxelFieldView.FIELD_HEIGHT
            - int(PyxelFieldView.FIELD_HEIGHT * player_rate),
            2,
            Color.ENEMY,
            True,
        )


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        pyxel.init(
            GameObject.MONITOR_WIDTH, GameObject.MONITOR_HEIGHT, title="Pyxel on Pico W"
        )
        self.pyxel.load("map_tile.pyxres")
        self.pyxel.mouse(True)

        self.game_core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self.game_core.update()

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
