from abc import abstractmethod

try:
    from .framework import (
        FieldObject,
        Direct,
        Node,
        Color,
        Image,
    )  # pylint: disable=C0413
except ImportError:
    from framework import (
        FieldObject,
        Direct,
        Node,
        Color,
        Image,
    )  # pylint: disable=C0413


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

    def get_color(self):
        return self.color


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

    def __init__(self, tile_x, tile_y, color=Color.NODE_RED):
        super().__init__(tile_x, tile_y, Node.UNIT_ENEMY)
        self.max_interval = self.SHOT_INTERVAL
        self.direct = Direct.LEFT
        self.bullet_cls = BulletEnemy
        self.hp = self.MAX_HP
        self.color = color

    def hit(self, bullet):
        if self.color == bullet.color:
            super().hit(bullet)


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
        frozenset([Color.NODE_RED, Color.NODE_GREEN]): Color.NODE_YELLOW,
        frozenset([Color.NODE_BLUE, Color.NODE_GREEN]): Color.NODE_CYAN,
        frozenset([Color.NODE_BLUE, Color.NODE_RED]): Color.NODE_PURPLE,
        frozenset([Color.NODE_RED, Color.NODE_YELLOW]): Color.NODE_ORANGE,
        frozenset([Color.NODE_BLUE, Color.NODE_YELLOW]): Color.NODE_BROWN,
        frozenset([Color.NODE_BLUE, Color.NODE_PURPLE]): Color.NODE_NAVY,
        frozenset([Color.NODE_BLUE, Color.NODE_CYAN]): Color.NODE_DEEP_BLUE,
    } | {
        frozenset([color, color]): color
        for color in [
            Color.NODE_BLUE,
            Color.NODE_RED,
            Color.NODE_GREEN,
            Color.NODE_YELLOW,
            Color.NODE_CYAN,
            Color.NODE_PURPLE,
            Color.NODE_ORANGE,
            Color.NODE_BROWN,
            Color.NODE_NAVY,
            Color.NODE_DEEP_BLUE,
        ]
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
