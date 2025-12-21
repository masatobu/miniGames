# title: pyxel dig smith
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum

try:
    from .logic import (
        FieldGenerator,
        Item,
        Pickaxe,
        PickaxeGenerator,
    )  # pylint: disable=C0413
except ImportError:
    from logic import (
        FieldGenerator,
        Item,
        Pickaxe,
        PickaxeGenerator,
    )  # pylint: disable=C0413


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, color):
        pass

    @abstractmethod
    def draw_image(self, x, y, src_x, src_y, is_dither):
        pass

    @abstractmethod
    def draw_rect(self, x, y, width, height, color, is_fill):
        pass

    @abstractmethod
    def set_clip(self, rect):
        pass

    @abstractmethod
    def clear(self, x, y):
        pass

    @classmethod
    def create(cls):
        return cls()


class Color(Enum):
    BLUE = 1
    SKY_BLUE = 5
    WHITE = 7
    BLACK = 0
    DARK_BLUE = 1
    RED = 8
    YELLOW = 10


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, color):
        self.pyxel.text(x, y, text, color.value)

    def draw_image(self, x, y, src_x, src_y, is_dither, offset=(0, 0), is_revert=False):
        if is_dither:
            self.pyxel.dither(0.5)
        self.pyxel.blt(
            x * 8 + offset[0],
            y * 8 + offset[1],
            0,
            src_x * 8,
            src_y * 8,
            -8 if is_revert else 8,
            8,
            colkey=Color.BLACK.value,
        )
        if is_dither:
            self.pyxel.dither(1.0)

    def draw_rect(self, x, y, width, height, color, is_fill):
        params = {"x": x, "y": y, "w": width, "h": height, "col": color.value}
        if is_fill:
            self.pyxel.rect(**params)
        else:
            self.pyxel.rectb(**params)

    def set_clip(self, rect):
        if rect is None:
            self.pyxel.clip()
        else:
            self.pyxel.clip(*rect)

    def clear(self, x, y):
        self.pyxel.camera(x, y)
        self.pyxel.cls(Color.BLACK.value)

    def get_frame(self):
        return self.pyxel.frame_count


class Direct(Enum):
    RIGHT = (1, 0)
    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)
    NUTRAL = (0, 0)

    @classmethod
    def get(cls, value):
        return cls._value2member_map_.get(value)


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

    def is_click(self) -> bool:
        return self.pyxel.btnp(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_x(self):
        return self.pyxel.mouse_x

    def get_mouse_y(self):
        return self.pyxel.mouse_y


class IUnitView(ABC):
    @abstractmethod
    def draw_unit(self, x, y, image_x, image_y, face, direct, offset):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelUnitView(IUnitView):
    def __init__(self):
        super().__init__()
        self.view = PyxelView.create()

    def draw_unit(self, x, y, image_x, image_y, face, direct, offset):
        if direct == Direct.NUTRAL:
            moved_x = image_x if (self.view.get_frame() // 8) % 2 == 0 else image_x + 2
        else:
            image_frame = (self.view.get_frame() // 4) % 4
            moved_x = image_x + (image_frame if image_frame != 2 else 0)
        is_revert = face == Direct.LEFT
        self.view.draw_image(
            x,
            y,
            moved_x,
            image_y,
            False,
            is_revert=is_revert,
            offset=offset,
        )


class GameObject(ABC):
    TILE_SIZE = 11
    MONITOR_TILE_SIZE = 11
    FIELD_HEIGHT = 8 * TILE_SIZE
    FIELD_WIDTH = 8 * TILE_SIZE
    MONITOR_HEIGHT = 8 * 15
    MONITOR_WIDTH = 8 * MONITOR_TILE_SIZE
    TILE_TILT = TILE_SIZE // 2
    FIELD_OFFSET = (MONITOR_WIDTH - FIELD_WIDTH) // 2, (
        MONITOR_WIDTH - FIELD_WIDTH
    ) // 2
    FIELD_TILE_RECT = (1, 1, TILE_SIZE - 2, TILE_SIZE - 2)
    CAMERA_RECT = tuple(p * 8 for p in FIELD_TILE_RECT)

    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()
        self.unit_view = PyxelUnitView.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class Unit(GameObject):
    def __init__(self, x, y, image_x, image_y):
        super().__init__()
        self.pos = (x, y)
        self.to_pos = None
        self.to_direct = None
        self.move_step = 0
        self.image_pos = (image_x, image_y)
        self.face = Direct.RIGHT
        self.mv_dir = Direct.NUTRAL

    def draw(self):
        self.unit_view.draw_unit(
            *self.pos,
            *self.image_pos,
            self.face,
            self.mv_dir,
            self.get_offset(),
        )

    def update(self):
        if self.to_direct is not None:
            self.move_step += 1
            if self.move_step >= 8:
                self.pos = self.to_pos
                self.to_pos = None
                self.to_direct = None
                self.move_step = 0
                self.mv_dir = Direct.NUTRAL

    def move(self, to_pos, direct, is_blocked):
        self.face = direct if direct in {Direct.RIGHT, Direct.LEFT} else self.face
        if not is_blocked:
            self.to_pos = to_pos
            self.to_direct = direct
            self.mv_dir = direct

    def get_pos(self, direct):
        direct_axis = (0, 0) if direct is None else direct.value
        return self.pos[0] + direct_axis[0], self.pos[1] + direct_axis[1]

    def get_face_direct(self):
        return self.face

    def is_moving(self):
        return self.to_direct is not None

    def get_offset(self):
        return (
            tuple(self.move_step * d for d in self.to_direct.value)
            if self.to_direct is not None
            else (0, 0)
        )


class FieldObject(GameObject):
    def __init__(self, pos):
        super().__init__()
        self.center_pos = None
        self.pos = pos
        self.image_pos = None

    def draw(self):
        screen_axis = self._get_screen_axis()
        if all(0 <= i < GameObject.TILE_SIZE for i in screen_axis):
            self.view.draw_image(*self.pos, *self.image_pos, False)

    def draw_abs(self, center_pos):
        self.center_pos = center_pos
        self.draw()

    def _get_screen_axis(self):
        diff = tuple(GameObject.TILE_TILT - c for c in self.center_pos)
        return self.pos[0] + diff[0], self.pos[1] + diff[1]

    def get_abs_pos(self):
        return self.pos


def get_hash(value):
    return hash(value)


class Field(GameObject):
    SKYLINE_Y = 1

    def __init__(self, center_pos):
        super().__init__()
        self.dig_pos_set = {(2, 3)}
        self.center_pos = center_pos
        self.ores_map = {(2, 3): Ore((2, 3), Item.METAL_1)}
        self.field_generator = FieldGenerator.create()
        self.furnace = Furnace((0, 1))

    def draw(self):
        clip_rect = GameObject.CAMERA_RECT
        self.view.set_clip(clip_rect)
        ore_pos_set = self.ores_map.keys()
        for rel_x in range(GameObject.TILE_SIZE):
            for rel_y in range(GameObject.TILE_SIZE):
                abs_axis = self._convert_to_abs_pos((rel_x, rel_y))
                abs_px = tuple(a * 8 for a in abs_axis)
                if abs_axis[1] < self.SKYLINE_Y - 1:
                    self.view.draw_rect(*abs_px, 8, 8, Color.BLUE, True)
                    continue
                if abs_axis[1] == self.SKYLINE_Y:
                    self.view.draw_rect(*abs_px, 8, 8, Color.SKY_BLUE, True)
                    continue
                if abs_axis in self.dig_pos_set | ore_pos_set:
                    continue
                if abs_axis[1] == self.SKYLINE_Y - 1:
                    image_pos = (4, 3)
                elif abs_axis[1] == 2 or (
                    (abs_axis[0], abs_axis[1] - 1) in self.dig_pos_set | ore_pos_set
                ):
                    image_pos = (3, 3)
                else:
                    image_pos = self.field_generator.get_layer_image_pos(abs_axis[1])
                    if image_pos is None:
                        continue
                self.view.draw_image(*abs_axis, *image_pos, False)
                if abs_axis[1] > self.SKYLINE_Y:
                    appeared_item = self.field_generator.get_item(*abs_axis)
                    if appeared_item is not None:
                        self.view.draw_image(*abs_axis, *appeared_item.value, True)
        for ore in self.ores_map.values():
            ore.draw_abs(self.center_pos)
        if self.furnace is not None:
            self.furnace.draw_abs(self.center_pos)
        self.view.set_clip(None)

    def _convert_to_abs_pos(self, screen_pos):
        diff = tuple(c - GameObject.TILE_TILT for c in self.center_pos)
        return screen_pos[0] + diff[0], screen_pos[1] + diff[1]

    def is_movable(self, abs_pos):
        if abs_pos[1] == 1:
            is_hit_furnance = self.is_hit_furnance(abs_pos, Direct.NUTRAL)
            return not is_hit_furnance
        return abs_pos in self.dig_pos_set

    def set_center(self, center_abs_pos):
        self.center_pos = center_abs_pos

    def dig(self, abs_pos, pickaxe):
        if abs_pos[1] <= self.SKYLINE_Y or abs_pos in self.dig_pos_set:
            return False
        if not self.field_generator.is_digable(*abs_pos, pickaxe):
            return False
        self.dig_pos_set.add(abs_pos)
        appeared_item = self.field_generator.get_item(*abs_pos)
        if appeared_item is not None:
            self.ores_map[abs_pos] = Ore(abs_pos, appeared_item)
        return True

    def get_ore(self, abs_pos):
        if abs_pos in self.ores_map:
            return self.ores_map[abs_pos].get_item()
        return None

    def delete_ore(self, abs_pos):
        del self.ores_map[abs_pos]

    def is_hit_furnance(self, abs_pos, direct):
        to_pos = tuple(p + d for p, d in zip(abs_pos, direct.value))
        ret = self.furnace is not None and self.furnace.get_abs_pos() == to_pos
        return ret

    def get_route(self, rel_pos):
        route = self.field_generator.get_lightest_path(
            self.center_pos, rel_pos, self.dig_pos_set
        )
        ret = []
        for i in range(1, len(route)):
            direct_axis = tuple(n - b for b, n in zip(route[i - 1], route[i]))
            direct = Direct.get(direct_axis)
            ret.append(direct)
        return ret


class Ore(FieldObject):
    def __init__(self, pos, item):
        super().__init__(pos)
        self.item = item
        self.image_pos = item.value

    def get_item(self):
        return self.item


class Furnace(FieldObject):
    IMAGE_POS = (2, 6)

    def __init__(self, pos):
        super().__init__(pos)
        self.image_pos = self.IMAGE_POS


class Player(Unit):
    def __init__(self):
        super().__init__(2, 1, 1, 0)


class FrameOjbect(GameObject):
    NUM_OFFSET = (5, 3)

    def __init__(self, center_pos):
        super().__init__()
        self.center_pos = center_pos
        self.draw_offset = (0, 0)

    def draw_frame(self, tile_pos, box_map):
        draw_pos = tuple(
            ct - GameObject.TILE_TILT + dp for ct, dp in zip(self.center_pos, tile_pos)
        )
        self.view.draw_rect(
            draw_pos[0] * 8 + self.draw_offset[0] - 1,
            draw_pos[1] * 8 + self.draw_offset[1] - 1,
            8 * len(box_map[0]) + 2,
            8 * len(box_map) + 2,
            Color.WHITE,
            False,
        )
        for y, item_list in enumerate(box_map):
            for x, item in enumerate(item_list):
                self.draw_item(draw_pos, x, y, item, None)

    def draw_text(self, tile_pos, text, offset):
        draw_pos = tuple(
            ct - GameObject.TILE_TILT + dp for ct, dp in zip(self.center_pos, tile_pos)
        )
        self.view.draw_text(
            draw_pos[0] * 8 + self.draw_offset[0] + offset[0],
            draw_pos[1] * 8 + self.draw_offset[1] + offset[1],
            text,
            Color.WHITE,
        )

    def draw_rect(self, draw_pos, x, y, w, h, color, is_fill):
        item_pos = tuple(
            (p + i) * 8 + do for p, i, do in zip(draw_pos, (x, y), self.draw_offset)
        )
        self.view.draw_rect(*item_pos, w, h, color, is_fill)

    def draw_unit(self, draw_pos, x, y, img_x, img_y):
        item_pos = tuple(p + i for p, i in zip(draw_pos, (x, y)))
        self.unit_view.draw_unit(
            *item_pos, img_x, img_y, Direct.RIGHT, Direct.RIGHT, self.draw_offset
        )

    def draw_item(self, draw_pos, x, y, item, num, is_draw_back=True, is_dither=False):
        item_pos = tuple(
            (p + i) * 8 + do for p, i, do in zip(draw_pos, (x, y), self.draw_offset)
        )
        color = Color.DARK_BLUE if (x + y) % 2 == 1 else Color.BLACK
        if is_draw_back:
            self.view.draw_rect(*item_pos, 8, 8, color, True)
        if item is not None:
            self.view.draw_image(
                draw_pos[0] + x,
                draw_pos[1] + y,
                *item.value,
                is_dither,
                offset=self.draw_offset,
            )
            if num is not None:
                num_pos = tuple(p + o for p, o in zip(item_pos, self.NUM_OFFSET))
                self.view.draw_text(*num_pos, str(num), Color.WHITE)

    def set_center(self, x, y):
        self.center_pos = (x, y)

    def set_offset(self, offset):
        self.draw_offset = offset


class Icon(Enum):
    STRENGTH = (4, 6)
    ITEM_SHADE = (6, 6)
    PICKAXE_SHADE = (5, 6)


class Bag(FrameOjbect):
    class BagTags(Enum):
        EQUIP = 0
        STRENGTH = 1
        TARGET = 2

    TILE_POS = (1, GameObject.TILE_SIZE)
    ITEM_POS_MAP = (tuple(i for i in Item if i != Item.JEWEL), tuple(Pickaxe))
    EQUIP_TILE_POS = (1 + len(ITEM_POS_MAP[0]) + 1, GameObject.TILE_SIZE)
    MAX_NUM = 9
    MAX_STRENGTH = 20
    # 耐久度倍率マップ（既定1.0、JEWELのみ3.0）
    MAX_STRENGTH_WEIGHT_MAP = {Pickaxe.JEWEL: 3.0}

    def __init__(self, center_pos, init_items=None):
        super().__init__(center_pos)
        self.item_map = init_items if init_items is not None else {}
        self.equip_item = None
        self.select_item = None
        self.strength_map = {
            p: int(self.MAX_STRENGTH * self.MAX_STRENGTH_WEIGHT_MAP.get(p, 1.0))
            for p in Pickaxe
        }

    def draw(self):
        self.draw_frame(self.TILE_POS, self.ITEM_POS_MAP)
        self.draw_frame(
            self.EQUIP_TILE_POS,
            (
                (self.BagTags.EQUIP, self.BagTags.STRENGTH),
                (Item.JEWEL, self.BagTags.TARGET),
            ),
        )

    def draw_item(self, draw_pos, x, y, item, num, is_draw_back=True, is_dither=False):
        if item is not None and item in self.BagTags:
            self._draw_equip(draw_pos, x, y, item)
            return
        item = item if (item in self.item_map or item == Item.JEWEL) else None
        num = self.item_map.get(item, 0)
        super().draw_item(draw_pos, x, y, item, num)
        if self.select_item is not None and item == self.select_item:
            self.draw_rect(draw_pos, x, y, 8, 8, Color.YELLOW, False)

    def _draw_equip(self, draw_pos, x, y, item):
        draw_item = None
        draw_back = True
        draw_num = None
        draw_dither = False
        if item == self.BagTags.EQUIP:
            if self.equip_item is None:
                draw_item = Icon.PICKAXE_SHADE
                draw_dither = True
            else:
                draw_item = self.equip_item
        elif item == self.BagTags.STRENGTH:
            draw_item = None
            if self.equip_item is not None:
                draw_item = Icon.STRENGTH
                draw_back = False
                strength = self.strength_map[self.equip_item]
                current_max = int(
                    self.MAX_STRENGTH
                    * self.MAX_STRENGTH_WEIGHT_MAP.get(self.equip_item, 1.0)
                )
                draw_num = (strength * 9) // current_max
                meter = 1 + int(5 * strength / current_max)
                super().draw_rect(draw_pos, x, y, 8, 8, Color.BLACK, True)
                super().draw_rect(draw_pos, x, y, meter, 8, Color.YELLOW, True)
        super().draw_item(
            draw_pos,
            x,
            y,
            draw_item,
            draw_num,
            is_draw_back=draw_back,
            is_dither=draw_dither,
        )
        if item == self.BagTags.TARGET:
            text_pos = tuple(p + d for p, d in zip((x, y), self.EQUIP_TILE_POS))
            offset = tuple(o + l for o, l in zip(self.NUM_OFFSET, (-4, 0)))
            self.draw_text(text_pos, "/3", offset)

    def push(self, item):
        if item not in self.item_map or self.item_map[item] < self.MAX_NUM:
            self.item_map[item] = self.item_map.get(item, 0) + 1

    def pull(self, item_set, is_dryrun=False) -> bool:
        if not item_set.issubset(self.item_map.keys()):
            return False
        if is_dryrun:
            return True
        for item in item_set:
            self.item_map[item] -= 1
            if item in Pickaxe:
                self.strength_map[item] = int(
                    self.MAX_STRENGTH * self.MAX_STRENGTH_WEIGHT_MAP.get(item, 1.0)
                )
        self.item_map = {k: v for k, v in self.item_map.items() if v > 0}
        if self.get_equiped() not in self.item_map:
            self.equip(self.EQUIP_TILE_POS, None)
        return True

    def is_full(self, item):
        return self.item_map.get(item, 0) >= self.MAX_NUM

    def get_item_count(self, item):
        return self.item_map.get(item, 0)

    def select_pos(self, x, y):
        rect_map = {
            tuple(
                (*self.TILE_POS, len(self.ITEM_POS_MAP[0]), len(self.ITEM_POS_MAP))
            ): self.ITEM_POS_MAP,
            tuple((self.EQUIP_TILE_POS[0], self.EQUIP_TILE_POS[1] + 1, 1, 1)): [
                [Item.JEWEL]
            ],
        }
        for rect, pos_map in rect_map.items():
            if not (
                rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
            ):
                continue
            rel_pos = tuple(p - t for p, t in zip((x, y), rect[:2]))
            item = pos_map[rel_pos[1]][rel_pos[0]]
            if item in self.item_map:
                self.select_item = item
            return
        self.select_item = None

    def equip(self, pos, item):
        if pos != self.EQUIP_TILE_POS:
            return
        if item is None:
            self.equip_item = None
            return
        if item not in Pickaxe:
            return
        if item not in self.item_map:
            return
        self.equip_item = item

    def get_selected(self):
        return self.select_item

    def get_equiped(self):
        return self.equip_item

    def chip_equipment(self):
        if self.equip_item is None:
            return
        self.strength_map[self.equip_item] -= 1
        if self.strength_map[self.equip_item] <= 0:
            self.pull({self.equip_item})
            self.equip_item = None

    def get_strength(self):
        if self.equip_item is None:
            return None
        return self.strength_map[self.equip_item]


class Forge(FrameOjbect):
    class Tags(Enum):
        ITEM = (0, 0)
        PICKAXE = (2, 0)
        SMITH = (4, 0)
        COAL = (1, 2)

    TILE_POS = (3, 2)
    TAG_LIST = (Tags.ITEM, Tags.PICKAXE, Tags.SMITH, Tags.COAL)
    SHADOW_MAP = {(0, 0): Icon.ITEM_SHADE, (2, 0): None, (1, 2): None}

    def __init__(self, center_pos):
        super().__init__(center_pos)
        self.item_set = set()
        self.box_item = self._get_box_item(None)

    @classmethod
    def _get_box_item(cls, item):
        ret = {
            tag.value: item
            for tag, item in zip(
                cls.TAG_LIST[:-1],
                PickaxeGenerator.get_recipe(item),
            )
        }
        ret[cls.Tags.COAL.value] = Item.COAL
        return ret

    def draw(self):
        for tag in self.TAG_LIST:
            frame_pos = tuple(p + e for p, e in zip(tag.value, self.TILE_POS))
            self.draw_frame(frame_pos, ((tag,),))
        for x, y, text in ((1, 0, "+"), (3, 0, "=")):
            frame_pos = tuple(p + e for p, e in zip((x, y), self.TILE_POS))
            self.draw_text(frame_pos, text, (2, 1))

    def draw_item(self, draw_pos, x, y, item, num, is_draw_back=True, is_dither=False):
        box_item = self.box_item.get(item.value, None)
        draw_item = box_item if box_item in self.item_set else None
        if draw_item is not None:
            super().draw_item(draw_pos, x, y, draw_item, num)
            if Item.COAL == draw_item:
                self.draw_unit(draw_pos, 0, -1, 1, 1)
            return
        if item.value in self.SHADOW_MAP:
            shadow = self.SHADOW_MAP[item.value]
            is_dither = True
            if shadow is not None:
                draw_item = shadow
            elif box_item is not None:
                draw_item = box_item
        super().draw_item(draw_pos, x, y, draw_item, num, is_dither=is_dither)

    def push(self, pos, item) -> bool:
        rel_pos = tuple(p - t for p, t in zip(pos, self.TILE_POS))
        if rel_pos == (0, 0):
            is_in_coal = Item.COAL in self.item_set
            self.clear()
            self.box_item = self._get_box_item(item)
            if is_in_coal:
                self.item_set.add(Item.COAL)
        pos_set = set(t.value for t in self.TAG_LIST)
        if rel_pos not in pos_set:
            return False
        if (
            rel_pos != self.Tags.SMITH.value
            and rel_pos in self.box_item
            and self.box_item[rel_pos] == item
        ):
            self.item_set.add(item)
            recepi_set = set(
                value
                for key, value in self.box_item.items()
                if key != self.Tags.SMITH.value and value is not None
            )
            if self.Tags.SMITH.value in self.box_item and recepi_set == self.item_set:
                self.item_set.add(self.box_item[self.Tags.SMITH.value])
        return True

    def clear(self):
        self.item_set = set()
        self.box_item = self._get_box_item(None)

    def smith(self, pos):
        rel_pos = tuple(p - t for p, t in zip(pos, self.TILE_POS))
        if rel_pos != self.Tags.SMITH.value:
            return None
        if (
            self.Tags.SMITH.value not in self.box_item
            or self.box_item[self.Tags.SMITH.value] not in self.item_set
        ):
            return None
        return self.box_item[self.Tags.SMITH.value]

    def get_material(self):
        return {
            v
            for k, v in self.box_item.items()
            if v is not None and k != self.Tags.SMITH.value and v in self.item_set
        }


class Cursor(GameObject):
    TILT = tuple(-1 * o for o in GameObject.FIELD_OFFSET)
    BAG_RECT = (
        Bag.TILE_POS[0] * 8,
        Bag.TILE_POS[1] * 8,
        len(Bag.ITEM_POS_MAP[0]) * 8,
        len(Bag.ITEM_POS_MAP) * 8,
    )
    EQUIP_RECT = (
        Bag.EQUIP_TILE_POS[0] * 8,
        Bag.EQUIP_TILE_POS[1] * 8,
        1 * 8,  # 左だけ。右はステータス表示でクリックさせない。
        2 * 8,
    )

    def __init__(self, center_pos):
        super().__init__()
        self.is_select = False
        self.click_pos = (-1, -1)
        self.select_pos = None
        self.center_pos = center_pos

    @staticmethod
    def _is_in(pos, rect):
        if pos[0] is None:
            return False
        if pos[1] is None:
            return False
        if not rect[0] <= pos[0] < rect[0] + rect[2]:
            return False
        if not rect[1] <= pos[1] < rect[1] + rect[3]:
            return False
        return True

    def update(self):
        self.select_pos = None
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if any(
                self._is_in((x, y), rect)
                for rect in (self.BAG_RECT, self.CAMERA_RECT, self.EQUIP_RECT)
            ):
                next_click_pos = ((x + self.TILT[0]) // 8, (y + self.TILT[1]) // 8)
                if self.click_pos != next_click_pos:
                    self.is_select = True
                    self.click_pos = next_click_pos
                    return
                self.select_pos = self.click_pos
            self.is_select = False
            self.click_pos = (-1, -1)

    def draw(self):
        if self.is_select and self.center_pos is not None:
            self.view.draw_rect(
                *[
                    (ct + cl - GameObject.TILE_TILT) * 8
                    for cl, ct in zip(self.click_pos, self.center_pos)
                ],
                8,
                8,
                Color.RED,
                False,
            )

    def get_select_pos(self):
        return self.select_pos

    def get_select_rel_pos(self):
        if self.select_pos is None or not self._is_in(
            self.select_pos, self.FIELD_TILE_RECT
        ):
            return (0, 0)
        return tuple(p - GameObject.TILE_TILT for p in self.select_pos)

    def set_center(self, x, y):
        self.center_pos = (x, y)


class Console(FrameOjbect):
    TILE_POS = (2, 2)
    FRAME_SIZE_MAP = tuple(tuple(None for _ in range(7)) for _ in range(2))

    def __init__(self, center_pos):
        super().__init__(center_pos)
        self.flg_is_tap = False
        self.message_list = []

    def draw(self):
        self.draw_frame(self.TILE_POS, self.FRAME_SIZE_MAP)
        for i, message in enumerate(self.message_list):
            pos = tuple(p + e for p, e in zip((0, i), self.TILE_POS))
            self.draw_text(pos, message, (9, 1))

    def draw_item(self, draw_pos, x, y, item, num, is_draw_back=True, is_dither=False):
        super().draw_item(draw_pos, x, y, item, num, is_draw_back=False)
        self.draw_rect(draw_pos, x, y, 8, 8, Color.BLACK, True)

    def update(self):
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if (
                x is not None
                and y is not None
                and self.TILE_POS[0] * 8
                <= x
                < (self.TILE_POS[0] + len(self.FRAME_SIZE_MAP[0])) * 8
                and self.TILE_POS[1]
                <= y
                < (self.TILE_POS[1] + len(self.FRAME_SIZE_MAP)) * 8
            ):
                self.flg_is_tap = True

    def is_tap(self):
        return self.flg_is_tap

    def set_message(self, message_list: list):
        self.message_list = message_list


class Position(FrameOjbect):
    TILE_POS = (1, 0)
    TEXT_OFFSET = (2, 1)

    def draw(self):
        text = f"({self.center_pos[0] - 2},{self.center_pos[1] - 1})"
        self.draw_text(self.TILE_POS, text, self.TEXT_OFFSET)


class GameCore(GameObject):
    TARGET_NUM = 3
    INIT_ITEM_MAP = {Pickaxe.METAL_1: 1}
    # INIT_ITEM_MAP = {k: 9 for k in Pickaxe}

    def __init__(self):
        super().__init__()
        self.player = Player()
        center = self.player.get_pos(None)
        self.field = Field(center)
        self.bag = Bag(center, init_items=self.INIT_ITEM_MAP.copy())
        self.forge = Forge(center)
        self.flg_reset = False
        self.cursor = Cursor(center)
        self.direct_list = []
        self.console = Console(center)
        self.position = Position(center)
        self.flg_game_end = False
        self.avail_item_map = self.INIT_ITEM_MAP.copy()

    def update(self):
        if self.flg_game_end:
            self.console.update()
            return
        if self.player.is_moving():
            self._update_moving()
        elif len(self.direct_list) == 0:
            self.cursor.update()
            self._cursor_action()
        self._move()
        self._set_game_end()

    def _set_game_end(self):
        if self.is_game_clear():
            self.console.set_message(["Game Clear", "Click here"])
            self.flg_game_end = True
            return
        if self.is_game_over():
            self.console.set_message(["Game Over", "Click here"])
            self.flg_game_end = True
            return

    def _set_avail_item(self, item_set, num):
        for item in item_set:
            self.avail_item_map[item] = self.avail_item_map.get(item, 0) + num

    def _cursor_action(self):
        pos = self.cursor.get_select_pos()
        if pos is None:
            return
        selected_item = self.bag.get_selected()
        self.bag.select_pos(*pos)
        if self._is_hit_furnance():
            smith_item = self.forge.smith(pos)
            if smith_item is not None:
                if self.bag.is_full(smith_item):
                    return
                if not self.bag.pull(self.forge.get_material()):
                    return
                self.bag.push(smith_item)
                pull_item_set = self.forge.get_material()
                if not self.bag.pull(pull_item_set, is_dryrun=True):
                    self.forge.clear()
                for item_set, num in (({smith_item}, 1), (pull_item_set, -1)):
                    self._set_avail_item(item_set, num)
                return
            if self.forge.push(pos, selected_item):
                return
        self.bag.equip(pos, selected_item)
        rel_pos = self.cursor.get_select_rel_pos()
        self.direct_list = self.field.get_route(rel_pos)
        if len(self.direct_list) > 0:
            self.forge.clear()

    def _update_moving(self):
        self.player.update()
        for frame in [self.bag, self.forge, self.console, self.position]:
            frame.set_offset(self.player.get_offset())
            if not self.player.is_moving():
                frame.set_center(*self.player.get_pos(None))

    def _move(self):
        if len(self.direct_list) == 0 or self.player.is_moving():
            return
        direct = self.direct_list.pop(0)
        next_pos = self.player.get_pos(direct)
        is_movable = self.field.is_movable(next_pos)
        self.player.move(next_pos, direct, not is_movable)
        if not is_movable:
            equiped = self.bag.get_equiped()
            if self.field.dig(next_pos, equiped):
                self.bag.chip_equipment()
                self.direct_list.insert(0, direct)
                if not self.bag.get_equiped():
                    self._set_avail_item({equiped}, -1)
                item = self.field.get_ore(next_pos)
                if item is not None:
                    self._set_avail_item({item}, 1)
                return
            self.direct_list = []
            return
        self.field.set_center(next_pos)
        self.cursor.set_center(*next_pos)
        item = self.field.get_ore(next_pos)
        if item is not None and not self.bag.is_full(item):
            self.bag.push(item)
            self.field.delete_ore(next_pos)

    def draw(self):
        tilt = tuple(
            p * 8 + o - m // 2 + 4
            for p, o, m in zip(
                self.player.get_pos(None),
                self.player.get_offset(),
                (self.MONITOR_WIDTH, self.MONITOR_WIDTH),
            )
        )
        self.view.clear(*tilt)
        self.field.draw()
        self.position.draw()
        self.player.draw()
        self.bag.draw()
        if not self.player.is_moving() and self._is_hit_furnance():
            self.forge.draw()
        self.cursor.draw()
        if self.flg_game_end:
            self.console.draw()

    def _is_hit_furnance(self):
        player_pos = self.player.get_pos(None)
        face = self.player.get_face_direct()
        return self.field.is_hit_furnance(player_pos, face)

    def is_game_over(self):
        return not PickaxeGenerator.is_generatable(
            {k for k, v in self.avail_item_map.items() if v > 0}
        )

    def is_game_clear(self):
        return self.bag.get_item_count(Item.JEWEL) >= self.TARGET_NUM

    def is_reset(self):
        return self.console.is_tap()


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        self.game_core = GameCore()

        pyxel.init(
            GameCore.MONITOR_WIDTH, GameCore.MONITOR_HEIGHT, title="Pyxel on Pico W"
        )
        self.pyxel.load("map_tile.pyxres")
        pyxel.mouse(True)
        pyxel.run(self.update, self.draw)

    def update(self):
        self.game_core.update()
        if self.game_core.is_reset():
            self.game_core = GameCore()

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
