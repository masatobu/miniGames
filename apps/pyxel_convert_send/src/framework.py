from abc import ABC, abstractmethod
from enum import Enum


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


class PyxelView(IView):
    TILE_MAP_WIDTH = 8 * (8 * 2)
    TILE_MAP_HEIGHT = 8 * (8 * 2 - 1)

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
    NODE_CYAN = 3
    NODE_PURPLE = 2
    NODE_BROWN = 4
    NODE_NAVY = 5
    NODE_DEEP_BLUE = 1
    PLAYER = 6
    ENEMY = 14
    BLACK = 0
    GREEN = 3


class Direct(Enum):
    RIGHT = (1, 0)
    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)


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


class GameObject(ABC):
    MONITOR_HEIGHT = PyxelView.TILE_MAP_HEIGHT
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
