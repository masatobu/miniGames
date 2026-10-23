# title: pyxel tycoon
# author: masatobu

# IView と IMapGenerator (src/map_generator.py) は互いに無関係な責務だが、どちらも
# ABC + シングルトン create() という同じ構造を独立に持つため、pylint の duplicate-code
# (R0801) が誤検出される。共通化は不要な抽象化になるため、このモジュール単位で抑制する。
# pylint: disable=duplicate-code

import math
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import NamedTuple, Optional

# ブラウザ実行版（pyxel package / app2html）では src/ 配下が直接実行され、src パッケージ
# として解決できないため、相対 import を試したうえでトップレベル import にフォールバックする
try:
    from .map_generator import (
        AreaBlockAlgorithmGenerator,
        AreaKind,
        IMapGenerator,
        MaterialType,
        ResourceType,
    )
    from .save_store import SaveStore
    from .util import enum_from_name, enum_name
except ImportError:
    from map_generator import (
        AreaBlockAlgorithmGenerator,
        AreaKind,
        IMapGenerator,
        MaterialType,
        ResourceType,
    )
    from save_store import SaveStore
    from util import enum_from_name, enum_name


class Color(Enum):
    BLACK = 0
    WHITE = 7
    DARK_BLUE = 1
    GREEN = 3
    YELLOW = 10


class IView(ABC):
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

    @abstractmethod
    def draw_text(self, x, y, text, col=Color.WHITE):
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
    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
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


class PyxelView(IView):
    def __init__(self, screen_width, screen_height):
        super().__init__(screen_width, screen_height)
        import pyxel  # pylint: disable=C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, col=Color.WHITE):
        self.pyxel.text(x, y, text, col.value)

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

    def draw_tri(self, x1, y1, x2, y2, x3, y3, col):
        self.pyxel.tri(x1, y1, x2, y2, x3, y3, col.value)

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
        import pyxel  # pylint: disable=C0415

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
    def draw_unit(self, x, y, image_x, image_y, face, direct, is_blinking):
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

    def draw_unit(self, x, y, image_x, image_y, face, direct, is_blinking):
        if is_blinking and (self.view.get_frame() // 5) % 2 == 0:
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
            True,
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

    def __init__(self, x, y, image_pos: Optional[tuple[int, int]]):
        super().__init__()
        self.pos = (x, y)
        self.face = Direct.RIGHT
        self.mv_dir = Direct.NUTRAL
        self.mv_is_blocked = False
        self.image_pos = image_pos
        self.damaged_frames = 0
        self.stat = None

    @staticmethod
    def get_area_pos(x, y):
        return tuple(p // Area.SIZE for p in (x, y))

    def draw(self):
        self.unit_view.draw_unit(
            *self.pos,
            *self._get_image_pos(),
            self.face,
            self.mv_dir,
            self._is_blinking(),
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

    def set_pos(self, x, y):
        self.pos = (x, y)

    def set_damaged(self) -> bool:
        if not self.is_in_i_frames():
            self.damaged_frames = self.I_FRAMES
            return True
        return False

    def is_in_i_frames(self):
        return self.damaged_frames > 0

    def set_stat(self, stat):
        self.stat = str(stat)

    def _is_blinking(self):
        return self.damaged_frames > 0

    def _get_image_pos(self):
        return self.image_pos


class Mob(Unit):
    I_FRAMES = 40

    def __init__(self, x, y, image_pos: Optional[tuple[int, int]]):
        super().__init__(x, y, image_pos)
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

    def __init__(self, x, y):
        super().__init__(x, y, self.IMAGE_POS)
        self.set_power(1)
        self.set_hp(3)
        self._materials = {}

    def add_power(self, num):
        self.set_power(self.get_power() + num)

    def add_material(self, material_type, num):
        self._materials[material_type] = self._materials.get(material_type, 0) + num

    def consume_material(self, material_type, num):
        self.add_material(material_type, -num)

    def get_material_count(self, material_type):
        return self._materials.get(material_type, 0)

    def get_materials(self):
        return [
            (material_type, num)
            for material_type in MaterialType
            if (num := self._materials.get(material_type, 0)) > 0
        ]

    def to_save_data(self) -> dict:
        return {
            "pos": list(self.pos),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "power": self.power,
            "materials": {t.name: n for t, n in self.get_materials()},
        }

    def restore(self, data: dict):
        self.set_pos(*data["pos"])
        self.set_hp(data["max_hp"])
        self.hp = data["hp"]
        self.set_power(data["power"])
        self._materials = {
            MaterialType[name]: num for name, num in data["materials"].items()
        }


class Item(Unit):
    def __init__(self, x, y, image_pos: Optional[tuple[int, int]]):
        super().__init__(x, y, image_pos)
        self.num = 0
        self.map_generator = AreaBlockAlgorithmGenerator.create()

    def get_num(self):
        return self.num

    def set_num(self, num):
        self.num = num


class Fee(Item):
    # 開放対象アイコンは資材の絵柄（Material.IMAGE_POS_MAP）の 1 つ右の絵柄
    IMAGE_POS_MAP = {
        MaterialType.WOOD: (1, 11),
        MaterialType.STONE: (1, 15),
        MaterialType.PLANK: (1, 17),
        MaterialType.BRICK: (1, 19),
        MaterialType.HAMMER: (1, 21),
    }

    def __init__(self, x, y):
        map_generator = AreaBlockAlgorithmGenerator.create()
        area_pos = self.get_area_pos(x, y)
        self.fee_type = map_generator.get_fee_type(*area_pos)
        super().__init__(x, y, self.IMAGE_POS_MAP.get(self.fee_type))
        self.set_num(self.map_generator.get_fee_num(*area_pos))

    def get_type(self):
        return self.fee_type

    def set_num(self, num):
        super().set_num(num)
        self.set_stat(num)


class Enemy(Mob):
    IMAGE_POS = (1, 1)
    STOP_DISTANCE_AREA = 3

    def __init__(self, x, y):
        super().__init__(x, y, self.IMAGE_POS)
        self.area_axis_pos = self.get_area_pos(x, y)
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

    def to_save_data(self) -> dict:
        # 出現元のスポナーへの参照は持たない。敵は出現したエリアの外へ動かないため、
        # 属するエリア（保存データのエリアごとの並び）が出現元のスポナーを表す
        return {
            "pos": list(self.pos),
            "hp": self.hp,
            "max_hp": self.max_hp,
            "power": self.power,
        }

    def restore(self, data: dict):
        self.set_pos(*data["pos"])
        self.set_power(data["power"])
        self.set_hp(data["max_hp"])
        self.hp = data["hp"]


class Boss(Mob):
    IMAGE_POS = (1, 2)

    def __init__(self, x, y):
        super().__init__(x, y, self.IMAGE_POS)
        self.area_axis_pos = self.get_area_pos(x, y)
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
        super().__init__(x, y, self.IMAGE_POS)
        self.power = AreaBlockAlgorithmGenerator.create().get_spawner_power(
            *self.get_area_pos(x, y)
        )
        self.spawn_interval = self.START_SPAWN_INTERVAL

    def update(self):
        super().update()
        self.spawn_interval -= 1

    def set_power(self, power):
        self.power = power

    def get_power(self):
        return self.power

    def to_save_data(self) -> dict:
        return {"spawn_interval": self.spawn_interval}

    def restore(self, data: dict):
        self.spawn_interval = data["spawn_interval"]

    def spawn(self):
        if self.spawn_interval <= 0:
            enemy = Enemy(*self.get_pos())
            enemy.set_power(self.get_power())
            self.spawn_interval = self.START_SPAWN_INTERVAL
            return enemy
        return None


class Workbench(Unit):
    IMAGE_POS = (1, 7)
    INPUT_INTERVAL_FRAMES = 5
    # 投入済みの上限。ポップアップの「投入済み/必要量」を 2 桁で表示する前提でもある
    INPUT_MAX_NUM = 99
    # ポップアップの寸法。テキストは「99/10」の 5 文字ぶんで幅を固定する（桁数で
    # 背景の幅を変えない）。Pyxel の標準フォントは 1 文字 4px 幅・5px 高
    POPUP_TEXT_CHARS = len("99/10")
    LETTER_WIDTH = 4
    LETTER_HEIGHT = 5
    POPUP_PADDING = 2
    POPUP_TEXT_WIDTH = POPUP_TEXT_CHARS * LETTER_WIDTH
    POPUP_HEIGHT = POPUP_PADDING + PyxelUnitView.SIZE + POPUP_PADDING
    # ポップアップの縦幅のうちエリアの上辺（枠線）より内側に入る量。半分を内側に入れ、
    # 上のエリアに完全に入って作業台のポップアップと感じにくくなるのを避ける
    POPUP_INSET = POPUP_HEIGHT // 2

    def __init__(self, x, y):
        super().__init__(x, y, self.IMAGE_POS)
        self._param = AreaBlockAlgorithmGenerator.create().get_workbench(
            *self.get_area_pos(x, y)
        )
        self.input_num = 0
        self._touch_frames = 0
        self._process_left_frames = 0
        self._is_just_processed = False

    def update(self):
        super().update()
        self._is_just_processed = False
        if self._process_left_frames > 0:
            self._process_left_frames -= 1
            self._is_just_processed = self._process_left_frames == 0
            if self._is_just_processed:
                self._try_start_process()

    @classmethod
    def popup_images_width(cls, material_num):
        """素材の絵柄を横に隙間なく並べた幅"""
        return PyxelUnitView.SIZE * material_num

    @classmethod
    def popup_width(cls, material_num):
        """背景の幅。絵柄の数だけ広がり、テキスト部分は固定（投入済みの桁数で変えない）"""
        return (
            cls.POPUP_PADDING
            + cls.popup_images_width(material_num)
            + cls.POPUP_PADDING
            + cls.POPUP_TEXT_WIDTH
            + cls.POPUP_PADDING
        )

    def draw_popup(self):
        """作業台の上部に「素材の絵柄 投入済み/必要量」を描く。ワールド座標で描くため、
        画面上では作業台と一緒に動く。縦幅の半分がエリアの上辺をまたいで内側に入る
        （作業台には重ならない）"""
        material_types = self._param.material_types
        popup_width = self.popup_width(len(material_types))
        popup_x = self.pos[0] - popup_width // 2
        popup_y = (
            self.get_area_pos(*self.pos)[1] * Area.SIZE
            - self.POPUP_HEIGHT
            + self.POPUP_INSET
        )
        self.view.draw_rect(
            popup_x, popup_y, popup_width, self.POPUP_HEIGHT, Color.BLACK, True
        )
        self.view.draw_rect(
            popup_x, popup_y, popup_width, self.POPUP_HEIGHT, Color.WHITE, False
        )
        for i, material_type in enumerate(material_types):
            self.view.draw_image(
                popup_x + self.POPUP_PADDING + i * PyxelUnitView.SIZE,
                popup_y + self.POPUP_PADDING,
                *Material.IMAGE_POS_MAP[material_type],
                False,
                True,
            )
        # テキストは背景の右端（右の余白の内側）に右詰めで描き、桁が増えると左へ伸びる
        text = f"{self.input_num}/{self._param.material_num}"
        self.view.draw_text(
            popup_x + popup_width - self.POPUP_PADDING - len(text) * self.LETTER_WIDTH,
            popup_y + (self.POPUP_HEIGHT - self.LETTER_HEIGHT) // 2,
            text,
        )

    def hit(self):
        self._touch_frames += 1

    def is_input_timing(self):
        return (
            self._touch_frames >= self.INPUT_INTERVAL_FRAMES
            and self.input_num < self.INPUT_MAX_NUM
        )

    def input_material(self):
        self.input_num += 1
        self._touch_frames = 0
        self._try_start_process()

    def _try_start_process(self):
        # 加工の開始条件は「加工中でない」かつ「投入済みが必要量以上」。投入時と加工の
        # 完了時のどちらからもここで判定する。加工中かどうかは残りフレーム数
        # （0 = 加工していない）で表し、専用の状態値は持たない
        if self._process_left_frames > 0 or self.input_num < self._param.material_num:
            return
        # 必要量は加工の開始時に消費する（U5）
        self.input_num -= self._param.material_num
        self._process_left_frames = self._param.process_frames

    def spawn_materials(self):
        if not self._is_just_processed:
            return None
        return Material(*self.get_pos())

    def to_save_data(self) -> dict:
        # _is_just_processed は update のたびに作り直され、同じフレームの
        # spawn_materials で使い切られるため保存しない
        return {
            "input_num": self.input_num,
            "touch_frames": self._touch_frames,
            "process_left_frames": self._process_left_frames,
        }

    def restore(self, data: dict):
        self.input_num = data["input_num"]
        self._touch_frames = data["touch_frames"]
        self._process_left_frames = data["process_left_frames"]

    @property
    def material_types(self):
        """消費する素材の種類の並び。自エリアに作業台の項目が無ければ None"""
        return self._param.material_types if self._param is not None else None


class Material(Item):
    IMAGE_POS_MAP = {
        MaterialType.WOOD: (1, 10),
        MaterialType.STONE: (1, 14),
        MaterialType.PLANK: (1, 16),
        MaterialType.BRICK: (1, 18),
        MaterialType.HAMMER: (1, 20),
    }

    def __init__(self, x, y):
        map_generator = AreaBlockAlgorithmGenerator.create()
        area_pos = self.get_area_pos(x, y)
        self.material_type = map_generator.get_material_type(*area_pos)
        super().__init__(x, y, self.IMAGE_POS_MAP.get(self.material_type))
        self.set_num(self.map_generator.get_material_num(*area_pos))

    def get_type(self):
        return self.material_type

    def to_save_data(self) -> dict:
        return {
            "pos": list(self.pos),
            "type": self.material_type.name if self.material_type else None,
            "num": self.num,
        }

    def restore(self, data: dict):
        self.set_pos(*data["pos"])
        self.material_type = (
            MaterialType[data["type"]] if data["type"] is not None else None
        )
        self.image_pos = self.IMAGE_POS_MAP.get(self.material_type)
        self.set_num(data["num"])


class Resource(Unit):
    IMAGE_POS_MAP = {
        ResourceType.TREE: ((1, 8), (1, 9)),
        ResourceType.ROCK: ((1, 12), (1, 13)),
    }
    HARVEST_FRAMES = 60
    SUSPEND_FRAMES = 15
    REGEN_FRAMES = 600

    def __init__(self, x, y):
        map_generator = AreaBlockAlgorithmGenerator.create()
        area_pos = self.get_area_pos(x, y)
        material_type = map_generator.get_material_type(*area_pos)
        self.resource_type = (
            material_type.get_resource_type() if material_type is not None else None
        )
        image_pos_pair = self.IMAGE_POS_MAP.get(self.resource_type)
        super().__init__(
            x, y, image_pos_pair[0] if image_pos_pair is not None else None
        )
        self.harvested_image_pos = (
            image_pos_pair[1] if image_pos_pair is not None else None
        )
        # 採取可能から採取済みを経て再生に至るまでの一巡を1つのカウンタで表す。
        # 0 <= progress_frames < HARVEST_FRAMES が採取中、HARVEST_FRAMES 以上
        # （_is_harvested()）が採取済み、HARVEST_FRAMES + REGEN_FRAMES 到達で一巡し 0 に戻る
        self.progress_frames = 0
        # 未接触は「最後の接触から猶予を超えて経過した」状態そのもので表す。
        # 未接触専用のセンチネルを progress_frames に持たせなくても、
        # _is_suspended() が常に True を返すため、点滅・進行の抑止は自然に成立する
        self.since_touch_frames = self.SUSPEND_FRAMES + 1

    def get_type(self):
        return self.resource_type

    def hit(self):
        self.since_touch_frames = 0

    def spawn_materials(self):
        if not self._is_just_harvested():
            return None
        return Material(*self.get_pos())

    def update(self):
        super().update()
        if self._is_harvested():
            self.progress_frames += 1
            if self._is_regenerated():
                self._reset_harvest()
        else:
            self.since_touch_frames += 1
            if not self._is_suspended():
                self.progress_frames += 1

    def _is_harvested(self):
        return self.progress_frames >= self.HARVEST_FRAMES

    def _is_just_harvested(self):
        return self.progress_frames == self.HARVEST_FRAMES

    def _is_suspended(self):
        return self.since_touch_frames > self.SUSPEND_FRAMES

    def _is_regenerated(self):
        return self.progress_frames >= self.HARVEST_FRAMES + self.REGEN_FRAMES

    def _reset_harvest(self):
        self.progress_frames = 0
        self.since_touch_frames = self.SUSPEND_FRAMES + 1

    def _is_blinking(self):
        return not self._is_harvested() and not self._is_suspended()

    def _get_image_pos(self):
        return self.harvested_image_pos if self._is_harvested() else self.image_pos

    def to_save_data(self) -> dict:
        return {
            "progress_frames": self.progress_frames,
            "since_touch_frames": self.since_touch_frames,
        }

    def restore(self, data: dict):
        self.progress_frames = data["progress_frames"]
        self.since_touch_frames = data["since_touch_frames"]


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
    OPPOSITE_DISTANCE = PyxelUnitView.SIZE * 3 // 2

    def __init__(self, save_data: Optional[dict] = None):
        super().__init__()
        map_generator = AreaBlockAlgorithmGenerator.create()
        start_pos = map_generator.get_start_pos()
        boss_pos = map_generator.get_boss_pos()
        self.boss_pos = boss_pos
        self.player = Player(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in start_pos))
        for material_type, num in map_generator.get_start_materials():
            self.player.add_material(material_type, num)
        self.area_map = {start_pos: Area(*start_pos), boss_pos: Area(*boss_pos)}
        self.area_map[boss_pos].unveil()
        self.unit_map = {
            boss_pos: [Boss(*tuple(p * Area.SIZE + Area.SIZE // 2 for p in boss_pos))]
        }
        self.spawner_map = {}
        self._unveil(*start_pos)
        self.operation_dir = Direct.NUTRAL
        self.area_x_padding, self.area_y_padding = tuple(
            size // 2 // Area.SIZE + 1
            for size in [self.SCREEN_WIDTH, self.SCREEN_HEIGHT]
        )
        self.flg_clear = False
        self.save_requested = False
        if save_data is not None:
            self._restore(save_data)

    def to_save_data(self) -> dict:
        """開放済みエリア・ユニットの状態・プレイヤーを JSON にできる保存データへ変換する。ボスの位置は
        生成器の保存データが持つ。ユニットの状態は型ごとに to_save_data() が返し、エリアごとに並べる"""
        return {
            "unveiled": [
                list(pos) for pos, area in self.area_map.items() if area.unveiled
            ],
            "units": self._units_save_data(),
            "player": self.player.to_save_data(),
        }

    _LIST_UNIT_KEYS = {Material: "materials", Enemy: "enemies"}

    @staticmethod
    def _spawn_unit_key(unit):
        """エリアに 1 つ出現する状態つきユニット（資源・作業台）の保存データ上のキー。対象外は None"""
        if isinstance(unit, Resource):
            return "resource"
        if isinstance(unit, Workbench):
            return "workbench"
        return None

    def _units_save_data(self) -> list:
        """状態を持つユニットを型ごとに to_save_data() で変換し、エリアごとの辞書に並べる。
        エリアに 1 つ出現するユニット（資源・作業台・スポナー）は単独のキー、数が変わるユニット
        （未回収の資材・出現済みの敵）はリストのキーに入れる"""
        entries = {}
        for pos, spawner in self.spawner_map.items():
            entries.setdefault(pos, {})["spawner"] = spawner.to_save_data()
        for pos, units in self.unit_map.items():
            entry = entries.setdefault(pos, {})
            for unit in units:
                if (key := self._spawn_unit_key(unit)) is not None:
                    entry[key] = unit.to_save_data()
                elif (key := self._LIST_UNIT_KEYS.get(type(unit))) is not None:
                    entry.setdefault(key, []).append(unit.to_save_data())
        return [{"area": list(pos), **entry} for pos, entry in entries.items() if entry]

    def _restore(self, data: dict):
        """保存データから状態を復元する。開放済みエリアは開放時と同じく開放対象の消去・隣接する
        未開放エリアの開放対象の生成・ユニットの出現を行う（ナビゲーションへは送らない）。
        開放対象は隣接する開放済みエリアの開放で作られるため、作られるまで順に繰り返す"""
        pending = {tuple(pos) for pos in data["unveiled"]} - {
            pos for pos, area in self.area_map.items() if area.unveiled
        }
        while pending:
            openable = {pos for pos in pending if pos in self.area_map}
            if not openable:
                break
            for pos in sorted(openable):
                for unit in list(self.unit_map.get(pos, [])):
                    if isinstance(unit, Fee):
                        self._remove_unit(pos, unit)
                self._unveil(*pos)
                self._place_spawn_unit(pos)
            pending -= openable
        self._restore_units(data["units"])
        self.player.restore(data["player"])

    def _restore_units(self, units_data: list):
        """_place_spawn_unit で出現済みのユニットへ、保存データの状態を型ごとの restore() で上書きする。
        数が変わるユニット（未回収の資材）は保存データから作ってエリアへ加える"""
        for entry in units_data:
            pos = tuple(entry["area"])
            for unit in self.unit_map.get(pos, []):
                if (key := self._spawn_unit_key(unit)) is not None:
                    unit.restore(entry[key])
            if pos in self.spawner_map:
                self.spawner_map[pos].restore(entry["spawner"])
            for unit_class, key in self._LIST_UNIT_KEYS.items():
                for unit_data in entry.get(key, []):
                    unit = unit_class(*unit_data["pos"])
                    unit.restore(unit_data)
                    self._add_unit(pos, unit)

    def update(self):
        for pos, units in list(self.unit_map.items()):
            in_screen = self._is_in_screen(pos)
            for unit in list(units):
                if in_screen:
                    self._update_in_screen_unit(pos, unit)
                elif isinstance(unit, (Resource, Workbench)):
                    # 資源の再生は画面外でも進める（requirements.md §3.13）。
                    # 敵・スポナー・ボスは画面外では行動しないため対象にしない（U2）。
                    # 画面の内外で資源の扱いを変えない方針（U4）のため通常の
                    # update() を呼ぶ。作業台の加工も画面外で進める
                    unit.update()
                    self._add_spawned_material(pos, unit)
        for pos, unit in self._get_in_screen_area_map(self.spawner_map).items():
            unit.update()
            if not any(isinstance(u, Enemy) for u in self.unit_map.get(pos, [])):
                spawn_unit = unit.spawn()
                if spawn_unit is not None:
                    self._add_unit(pos, spawn_unit)
        self.player.move(self.operation_dir, not self._contains_next_player_pos())
        self.player.update()
        self._hit()

    def _update_in_screen_unit(self, pos, unit):
        if isinstance(unit, Enemy):
            unit.spot(*self.player.get_pos())
        unit.update()
        if isinstance(unit, (Resource, Workbench)):
            self._add_spawned_material(pos, unit)
        if isinstance(unit, Mob) and unit.is_killed():
            if isinstance(unit, Enemy):
                material = Material(*unit.get_pos())
                if material.get_type() is not None:
                    self._add_dropped_material(pos, material)
            self._remove_unit(pos, unit)
            if isinstance(unit, Boss):
                self.flg_clear = True
                self._notify_navigator(Event(EventType.DEFEAT_BOSS, pos))

    def pop_save_requested(self) -> bool:
        """前回の呼び出し以降に保存すべき出来事（ナビゲーションへのイベントの送信・
        資材のドロップ）があったかを返し、記録を消す（GameCore が保存の契機として使う）"""
        requested, self.save_requested = self.save_requested, False
        return requested

    def _notify_navigator(self, event):
        """イベントを navigator へ送り、クリアした指示ごとに武器を強化する（U3）"""
        self.save_requested = True
        generator = AreaBlockAlgorithmGenerator.create()
        total_gain = 0
        for step in Navigator.create().notify(event):
            position = Navigator.locate_step(step)
            if position is not None:
                gain = generator.get_step_power_gain(*position)
                self.player.add_power(gain)
                total_gain += gain
        if total_gain > 0:
            NavigationPopup.create().set_power_gain(total_gain)

    def _add_spawned_material(self, pos, unit):
        # 資源・作業台が出した資材を、エリアの _get_opposite_pos の位置へ置く（U8）
        material = unit.spawn_materials()
        if material is not None:
            material.set_pos(*self._get_opposite_pos(pos))
            self._add_dropped_material(pos, material)

    def _add_dropped_material(self, pos, material):
        # 資源・作業台・敵が資材を落とす経路。ゲームの進行を表す出来事として保存の契機にする
        self._add_unit(pos, material)
        self.save_requested = True

    def draw(self):
        unit_draw_pos_list = []
        for pos, area in self._get_in_screen_area_map(self.area_map).items():
            area.draw()
            unit_draw_pos_list.append(pos)
        player_area = Unit.get_area_pos(*self.player.get_pos())
        popup_workbench = None
        for pos in unit_draw_pos_list:
            if pos in self.spawner_map:
                self.spawner_map[pos].draw()
            for unit in self.unit_map.get(pos, []):
                unit.draw()
                if pos == player_area and isinstance(unit, Workbench):
                    popup_workbench = unit
        self.player.draw()
        # ポップアップは作業台のエリアの外（上のエリアの下部）に重なり得るため、
        # 他のエリアのユニットに隠れないよう、ここで最前面に描く
        if popup_workbench is not None:
            popup_workbench.draw_popup()

    def _add_unit(self, pos, unit):
        self.unit_map.setdefault(pos, []).append(unit)

    def _remove_unit(self, pos, unit):
        units = self.unit_map[pos]
        units.remove(unit)
        if not units:
            del self.unit_map[pos]

    def _get_in_screen_area_map(self, targer_map):
        return {pos: v for pos, v in targer_map.items() if self._is_in_screen(pos)}

    def _is_in_screen(self, pos):
        area_axis = Unit.get_area_pos(*self.player.get_pos())
        return all(
            a - p <= c <= a + p
            for a, p, c in zip(
                area_axis, (self.area_x_padding, self.area_y_padding), pos
            )
        )

    def get_center_pos(self):
        return self.player.get_pos()

    def operate(self, direct):
        self.operation_dir = direct

    def _contains_next_player_pos(self) -> bool:
        next_pos = self.player.get_next_pos(self.operation_dir)
        area_axis = Unit.get_area_pos(*next_pos)
        return area_axis in self.area_map and self.area_map[area_axis].contains(
            *next_pos
        )

    def get_player_status(self):
        return self.player.get_status()

    def get_player_materials(self):
        return self.player.get_materials()

    def is_clear(self):
        return self.flg_clear

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
                    self._add_unit(pos, fee)

    def _hit(self):
        for pos, unit in self._get_hit_units():
            if isinstance(unit, Fee):
                if self.player.get_material_count(unit.get_type()) < unit.get_num():
                    continue
                self.player.consume_material(unit.get_type(), unit.get_num())
                self._remove_unit(pos, unit)
                self._unveil(*pos)
                self._notify_navigator(Event(EventType.UNVEIL, pos))
                self._place_spawn_unit(pos)
            elif isinstance(unit, Material):
                self._remove_unit(pos, unit)
                self.player.add_material(unit.get_type(), unit.get_num())
                self._notify_navigator(Event(EventType.GATHER, pos, unit.get_type()))
            elif isinstance(unit, (Enemy, Boss)):
                unit.battle(self.player)
            elif isinstance(unit, Resource):
                unit.hit()
            elif isinstance(unit, Workbench):
                self._hit_workbench(unit)

    def _place_spawn_unit(self, pos):
        spawn_unit = self._spawn(pos)
        if isinstance(spawn_unit, Spawner):
            self.spawner_map[pos] = spawn_unit
        elif spawn_unit is not None:
            self._add_unit(pos, spawn_unit)

    def _hit_workbench(self, workbench):
        workbench.hit()
        # 全種類を 1 つ以上所持している場合にのみ、全種類を 1 つずつ同時に投入する
        if workbench.is_input_timing() and all(
            self.player.get_material_count(material_type) > 0
            for material_type in workbench.material_types
        ):
            for material_type in workbench.material_types:
                self.player.consume_material(material_type, 1)
            workbench.input_material()

    def _get_opposite_pos(self, area_axis):
        center_pos = tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis)
        player_pos = self.player.get_pos()
        diff = tuple(p - c for p, c in zip(player_pos, center_pos))
        if diff == (0, 0):
            # 方向が定まらない縮退ケース。向きに意味を持たせる必要はないため、
            # ゼロ除算を避けられる任意の非ゼロ値で代替する
            diff = (1, 0)
        scale = self.OPPOSITE_DISTANCE / math.hypot(*diff)
        return tuple(round(c - d * scale) for c, d in zip(center_pos, diff))

    def _spawn(self, area_axis):
        center_pos = tuple(p * Area.SIZE + Area.SIZE // 2 for p in area_axis)
        spawner = Spawner(*center_pos)
        if spawner.get_power() > 0:
            return spawner
        # 作業台のエリアも加工後の資材（Plank / Brick / Hammer）を material_type に持つ（U1）ため、
        # 資源より前に決める。後ろに置くと Resource が生成され、get_resource_type() が
        # Plank / Brick / Hammer で KeyError になる（U3）
        workbench = Workbench(*center_pos)
        if workbench.material_types is not None:
            return workbench
        resource = Resource(*center_pos)
        if resource.get_type() is not None:
            return resource
        return None

    def _get_hit_units(self):
        ret = []
        player_pos = self.player.get_pos()
        area_axis = Unit.get_area_pos(*player_pos)
        for pos, units in self.unit_map.items():
            if not all(abs(p - m) <= 1 for p, m in zip(area_axis, pos)):
                continue
            for unit in units:
                unit_pos = unit.get_pos()
                if all(
                    abs(p - m) < PyxelUnitView.SIZE
                    for p, m in zip(player_pos, unit_pos)
                ):
                    ret.append((pos, unit))
        return ret


class ScreenObject(GameObject, ABC):
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
    HAERT_IMAGE_POS = (0, 1)
    LOSS_HAERT_IMAGE_POS = (0, 2)
    WEAPON_IMAGE_POS = (1, 5)
    POWER_PADDING = 40
    POWER_TEXT_X = 1 + POWER_PADDING + 9
    POWER_TEXT_Y = 3
    # 所持資材は画面右上に表示する（requirements.md §4）。アイコン列の x は右端からの
    # 固定余白とし、数量はアイコンの右へ左揃えで描く（既存のハート・武器と同じ並び順）。
    # 想定桁数は4桁（pyxel.FONT_WIDTH=4px、ID-018-1で確認。プレイテストで4桁ぶんの
    # 余白を要望されたため2桁から変更。ID-018-9 実施結果を参照）。桁あふれへの対応は対象外
    # （ID-018 対象外とした改善案）
    MATERIAL_ROW_HEIGHT = 9
    MATERIAL_DIGITS = 4
    MATERIAL_DIGIT_WIDTH = 4
    MATERIAL_ICON_PADDING = GameObject.SCREEN_WIDTH - (
        MATERIAL_ROW_HEIGHT + MATERIAL_DIGIT_WIDTH * MATERIAL_DIGITS + 1
    )

    def __init__(self):
        super().__init__()
        self.stat = (0, 0, 0)
        self.materials = []

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
                    True,
                )
        self.view.draw_image(
            *self.get_draw_pos(1 + self.POWER_PADDING, 1),
            *self.WEAPON_IMAGE_POS,
            False,
            True,
        )
        self.view.draw_text(
            *self.get_draw_pos(self.POWER_TEXT_X, self.POWER_TEXT_Y),
            str(self.stat[2]),
        )
        for i, (material_type, num) in enumerate(self.materials):
            row_y = i * self.MATERIAL_ROW_HEIGHT
            self.view.draw_image(
                *self.get_draw_pos(self.MATERIAL_ICON_PADDING, 1 + row_y),
                *Material.IMAGE_POS_MAP[material_type],
                False,
                True,
            )
            self.view.draw_text(
                *self.get_draw_pos(
                    self.MATERIAL_ICON_PADDING + self.MATERIAL_ROW_HEIGHT, 3 + row_y
                ),
                str(num),
            )

    def set_stat(self, hp, hp_max, power):
        self.stat = (hp, hp_max, power)

    def set_materials(self, materials):
        self.materials = materials

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


class EventType(Enum):
    """ナビゲーションへ送る出来事の種類"""

    UNVEIL = auto()
    DEFEAT_BOSS = auto()
    GATHER = auto()


class Event(NamedTuple):
    """ナビゲーションへ送る出来事。pos は出来事の起きたエリア座標、
    material_type は GATHER のとき拾った資材の種類"""

    type: EventType
    pos: tuple[int, int]
    material_type: Optional[MaterialType] = None

    def to_save_data(self) -> dict:
        return {
            "type": self.type.name,
            "pos": list(self.pos),
            "material_type": enum_name(self.material_type),
        }

    @classmethod
    def from_save_data(cls, data: dict) -> "Event":
        return cls(
            EventType[data["type"]],
            tuple(data["pos"]),
            enum_from_name(MaterialType, data["material_type"]),
        )


class InstructionKind(Enum):
    UNVEIL = auto()
    DEFEAT_BOSS = auto()
    GATHER = auto()


class Instruction(NamedTuple):
    """表示中の指示。area_kind は UNVEIL・GATHER のときの目標の種別、block_lv は目標のブロック
    （NEXT_BLOCK は現在のブロック）のレベル、pos は目標のエリア座標、
    material_type は GATHER のとき採集する資材の種類"""

    kind: InstructionKind
    area_kind: Optional[AreaKind]
    block_lv: int
    pos: tuple[int, int]
    material_type: Optional[MaterialType] = None

    def to_save_data(self) -> dict:
        return {
            "kind": self.kind.name,
            "area_kind": enum_name(self.area_kind),
            "block_lv": self.block_lv,
            "pos": list(self.pos),
            "material_type": enum_name(self.material_type),
        }

    @classmethod
    def from_save_data(cls, data: dict) -> "Instruction":
        return cls(
            InstructionKind[data["kind"]],
            enum_from_name(AreaKind, data["area_kind"]),
            data["block_lv"],
            tuple(data["pos"]),
            enum_from_name(MaterialType, data["material_type"]),
        )


class Navigator:
    """指示の列（種類と目標の種別の並び）と進行を持つ。入力はイベントだけで、
    目標のエリアは指示に切り替わった時点で、直前の指示を達成した位置を基準に決める"""

    # requirements.md フェーズ4「指示の流れ」（作業台の資材の採集は、投入を含めて 1 つの指示）
    # （(指示の種類, 目標の種別, ブロックのレベル, 採集する資材の種類)。最後は DEFEAT_BOSS）
    STEPS = (
        (InstructionKind.UNVEIL, AreaKind.TREE, 0, None),
        (InstructionKind.GATHER, AreaKind.TREE, 0, MaterialType.WOOD),
        (InstructionKind.UNVEIL, AreaKind.ROCK, 0, None),
        (InstructionKind.GATHER, AreaKind.ROCK, 0, MaterialType.STONE),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 0, None),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 1, None),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 1, MaterialType.PLANK),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 1, None),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 2, None),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 2, MaterialType.BRICK),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 2, None),
        (InstructionKind.UNVEIL, AreaKind.WORKBENCH, 3, None),
        (InstructionKind.GATHER, AreaKind.WORKBENCH, 3, MaterialType.HAMMER),
        (InstructionKind.UNVEIL, AreaKind.NEXT_BLOCK, 3, None),
    )

    _instance = None

    @classmethod
    def create(cls):
        if cls._instance is None:
            cls._instance = cls(AreaBlockAlgorithmGenerator.create())
        return cls._instance

    @classmethod
    def recreate(cls):
        """シングルトンを作り直す。生成器の recreate() の直後に呼び、新しいマップの
        最初の指示から始める"""
        cls._instance = cls(AreaBlockAlgorithmGenerator.create())
        return cls._instance

    def to_save_data(self) -> dict:
        """進行（指示の位置・表示中の指示・イベントの履歴）を JSON にできる保存データへ
        変換する。履歴は、指示が出る前に起きたイベントによる即時クリアの判定に要る"""
        return {
            "step": self.step,
            "current": self.current and self.current.to_save_data(),
            "history": [event.to_save_data() for event in self.history],
        }

    @classmethod
    def restore(cls, data: dict):
        """保存データから進行を復元し、シングルトンを差し替える。イベントの再実行は
        せず、値を直接与え直す。生成器は復元済みのものを使う（生成器の restore の後に呼ぶ）"""
        navigator = cls.__new__(cls)
        navigator.generator = AreaBlockAlgorithmGenerator.create()
        navigator.step = data["step"]
        navigator.history = [Event.from_save_data(e) for e in data["history"]]
        navigator.current = data["current"] and Instruction.from_save_data(
            data["current"]
        )
        cls._instance = navigator
        return navigator

    def __init__(self, generator: IMapGenerator):
        self.generator = generator
        self.step = 0
        self.history: list[Event] = []
        self.current: Optional[Instruction] = self._create(generator.get_start_pos())

    def _create(self, base_pos) -> Optional[Instruction]:
        if self.step < len(self.STEPS):
            kind, area_kind, block_lv, material_type = self.STEPS[self.step]
            pos = self.generator.find_nearest_area(block_lv, area_kind, base_pos)
            return Instruction(kind, area_kind, block_lv, pos, material_type)
        if self.step == len(self.STEPS):
            return Instruction(
                InstructionKind.DEFEAT_BOSS,
                None,
                AreaBlockAlgorithmGenerator.BLOCK_PATH_LEN,
                self.generator.get_boss_pos(),
            )
        return None

    def _is_achieved(self, event: Event) -> bool:
        current = self.current
        if current.kind == InstructionKind.DEFEAT_BOSS:
            return event.type == EventType.DEFEAT_BOSS
        if current.kind == InstructionKind.GATHER:
            return (
                event.type == EventType.GATHER
                and event.material_type == current.material_type
            )
        if event.type != EventType.UNVEIL:
            return False
        return self.generator.is_area_kind(
            current.block_lv, current.area_kind, event.pos
        )

    def notify(self, event: Event):
        """イベントを履歴に加え、表示中の指示を達成した履歴のイベントがある限り、
        次の指示へ進める（達成済みの指示は続けてクリアとなる）。今回クリアした
        指示の添字のリストを返す（クリアなしは空）"""
        self.history.append(event)
        cleared = []
        while self.current is not None:
            achieved = next((e for e in self.history if self._is_achieved(e)), None)
            if achieved is None:
                break
            cleared.append(self.step)
            self.step += 1
            self.current = self._create(achieved.pos)
        return cleared

    @classmethod
    def locate_step(cls, step: int) -> Optional[tuple[int, int, int]]:
        """指示の添字 step の、(ブロックの順位, ブロック内の順位, ブロック内の指示の個数)
        を返す。ブロックの順位は STEPS の第3要素（ブロックのレベル）。ボスの撃破
        （STEPS の外。武器の強化なし）は None"""
        if not 0 <= step < len(cls.STEPS):
            return None
        block_lv = cls.STEPS[step][2]
        block_steps = [i for i, v in enumerate(cls.STEPS) if v[2] == block_lv]
        return block_lv, block_steps.index(step), len(block_steps)


class NavigationPopup(ScreenObject):
    """ナビゲーションのポップアップ。画面上部の中央、ステータス表示の行より少し下に、
    表示中の指示の目標のアイコンを画面固定で描く（U3・U4）"""

    STATUS_ROW_BOTTOM = 10
    MARGIN = 4
    WIDTH = 40
    HEIGHT = 16
    ICON_SIZE = 8
    ICON_PADDING = 4
    # 矢印（三角形）の寸法。ポップアップの左上からの相対位置で、アイコンの右側に置く
    ARROW_CENTER = (28, 8)
    ARROW_TIP = 5
    ARROW_BACK = 3
    ARROW_HALF_WIDTH = 4
    # 8 方向の単位ベクトル（画面の座標は y が下向き。右から時計回り）
    ARROW_DIRECTS = tuple(
        (math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i in range(8)
    )

    # 武器の強さの増分表示。ステータスの武器の強さの数字の右、想定桁数（3 桁）ぶんの
    # 余白をとった固定位置に、y は数字と同じ行に描く。指示のクリアごとに上書きする
    POWER_GAIN_FRAMES = 60
    POWER_GAIN_DIGITS = 3
    POWER_GAIN_LETTER_WIDTH = 4
    POWER_GAIN_MARGIN = 2
    POWER_GAIN_X = (
        Status.POWER_TEXT_X
        + POWER_GAIN_DIGITS * POWER_GAIN_LETTER_WIDTH
        + POWER_GAIN_MARGIN
    )
    POWER_GAIN_Y = Status.POWER_TEXT_Y
    POWER_GAIN_COLOR = Color.YELLOW

    _instance = None

    @classmethod
    def create(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def recreate(cls):
        """シングルトンを作り直す。前のゲームの増分の表示を持ち越さない"""
        cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.player_pos = None
        self.power_gain = 0
        self.power_gain_frames = 0

    def set_player_pos(self, x, y):
        self.player_pos = (x, y)

    def set_power_gain(self, gain):
        """指示のクリアによる武器の強さの増分を表示する。表示中なら上書きする"""
        self.power_gain = gain
        self.power_gain_frames = self.POWER_GAIN_FRAMES

    def update(self):
        if self.power_gain_frames > 0:
            self.power_gain_frames -= 1

    def draw(self):
        self._draw_power_gain()
        self._draw_instruction()

    def _draw_power_gain(self):
        if self.power_gain_frames <= 0:
            return
        self.view.draw_text(
            *self.get_draw_pos(self.POWER_GAIN_X, self.POWER_GAIN_Y),
            f"+{self.power_gain}",
            self.POWER_GAIN_COLOR,
        )

    def _draw_instruction(self):
        instruction = Navigator.create().current
        if instruction is None:
            return
        x, y = self.get_draw_pos(
            GameObject.SCREEN_WIDTH // 2 - self.WIDTH // 2,
            self.STATUS_ROW_BOTTOM + self.MARGIN,
        )
        self.view.draw_rect(x, y, self.WIDTH, self.HEIGHT, Color.BLACK, True)
        self.view.draw_rect(x, y, self.WIDTH, self.HEIGHT, Color.WHITE, False)
        self.view.draw_image(
            x + self.ICON_PADDING,
            y + (self.HEIGHT - self.ICON_SIZE) // 2,
            *self._get_icon_pos(instruction),
            False,
            True,
        )
        direct = self._get_arrow_direct(instruction)
        if direct is not None:
            self._draw_arrow(x, y, direct)

    def _get_arrow_direct(self, instruction: Instruction) -> Optional[int]:
        """プレイヤーから目標のエリアの中心への方向（8 方向の添字）。方向が定まらない
        （プレイヤー位置が未設定、または目標のエリアの中心にいる）ときは None"""
        if self.player_pos is None:
            return None
        diff = tuple(
            t * Area.SIZE + Area.SIZE // 2 - p
            for t, p in zip(instruction.pos, self.player_pos)
        )
        if diff == (0, 0):
            return None
        return round(math.atan2(diff[1], diff[0]) / (math.pi / 4)) % 8

    def _draw_arrow(self, popup_x, popup_y, direct):
        ux, uy = self.ARROW_DIRECTS[direct]
        cx = popup_x + self.ARROW_CENTER[0]
        cy = popup_y + self.ARROW_CENTER[1]
        back_x = cx - self.ARROW_BACK * ux
        back_y = cy - self.ARROW_BACK * uy
        half = self.ARROW_HALF_WIDTH
        self.view.draw_tri(
            round(cx + self.ARROW_TIP * ux),
            round(cy + self.ARROW_TIP * uy),
            round(back_x - half * uy),
            round(back_y + half * ux),
            round(back_x + half * uy),
            round(back_y - half * ux),
            Color.WHITE,
        )

    @staticmethod
    def _get_icon_pos(instruction: Instruction) -> tuple[int, int]:
        """指示の目標のアイコンの絵柄。目標の種別と絵柄の対応はここに集約する。
        エリアの開放はエリア・開放対象のアイコン、資材の採集は採集する資材の絵柄"""
        if instruction.kind == InstructionKind.DEFEAT_BOSS:
            return Boss.IMAGE_POS
        if instruction.kind == InstructionKind.GATHER:
            return Material.IMAGE_POS_MAP[instruction.material_type]
        if instruction.area_kind == AreaKind.TREE:
            return Resource.IMAGE_POS_MAP[ResourceType.TREE][0]
        if instruction.area_kind == AreaKind.ROCK:
            return Resource.IMAGE_POS_MAP[ResourceType.ROCK][0]
        if instruction.area_kind == AreaKind.WORKBENCH:
            return Workbench.IMAGE_POS
        fee_type = AreaBlockAlgorithmGenerator.create().get_fee_type(*instruction.pos)
        return Fee.IMAGE_POS_MAP[fee_type]


class GameCore:
    def __init__(self, store: Optional[SaveStore] = None, reset: bool = False):
        """reset が真のときは保存データを読まずに新しいゲームを作り、その状態で保存データを
        上書きする（リセット時。呼び出し側が先に生成器・navigator を作り直しておく）"""
        self.view = PyxelView.create(GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT)
        self.store = store or SaveStore()
        self.controller = Controller()
        self.status = Status()
        self.field = self._create_field(
            None if reset else (self.store.load() or {}).get("game")
        )
        self.console = Console()
        self.navigation = NavigationPopup.create()
        self.status.set_stat(*self.field.get_player_status())
        self.status.set_materials(self.field.get_player_materials())
        if reset:
            self._save()

    @staticmethod
    def _create_field(game):
        """保存データ game があれば、生成器 → navigator の順に復元して Field を作る
        （navigator の目標は生成器の問い合わせで決まるため、生成器が先）。無ければ新しいゲーム"""
        if not game:
            return Field()
        AreaBlockAlgorithmGenerator.restore(game["generator"])
        Navigator.restore(game["navigator"])
        return Field(game["field"])

    def _save(self):
        """保存すべき出来事（ナビゲーションへのイベントの送信・資材のドロップ）があったフレームの保存。ボスを倒してクリアしたフレームは、
        保存データを「ゲーム無し」で上書きする（再読み込みで新しいゲームから始める）"""
        if self.field.is_clear():
            self.store.save({"game": None})
            return
        self.store.save(
            {
                "game": {
                    "generator": AreaBlockAlgorithmGenerator.create().to_save_data(),
                    "navigator": Navigator.create().to_save_data(),
                    "field": self.field.to_save_data(),
                }
            }
        )

    def update(self):
        if self.status.is_dead() or self.field.is_clear():
            self.console.update()
        else:
            self.controller.update()
            self.field.operate(self.controller.get_direct())
            self.field.update()
            self.navigation.update()
            if self.field.pop_save_requested():
                self._save()

    def draw(self):
        center_pos = self.field.get_center_pos()
        self._set_center(center_pos)
        self.view.clear(*center_pos)
        self.field.draw()
        self.status.set_stat(*self.field.get_player_status())
        self.status.set_materials(self.field.get_player_materials())
        self.status.draw()
        if self.status.is_dead():
            self.console.set_message("Game Over")
            self.console.draw()
        elif self.field.is_clear():
            self.console.set_message("Game Clear")
            self.console.draw()
        else:
            self.navigation.draw()
            self.controller.draw()

    def _set_center(self, center_pos):
        self.navigation.set_center(*center_pos)
        # 画面の中心はプレイヤーの位置（Field.get_center_pos）。矢印の起点に使う
        self.navigation.set_player_pos(*center_pos)
        self.console.set_center(*center_pos)
        self.controller.set_center(*center_pos)
        self.status.set_center(*center_pos)

    def is_reset(self):
        return self.console.is_tap()


class PyxelController:
    # ブラウザ実行版では、フック HTML が保存データを Pyodide のファイルへ書き込むのを待ってから
    # GameCore を作る（読み込みが間に合わないと新しいゲームとして始まってしまう）
    LOAD_WAIT_FRAMES = 10

    def __init__(self):
        import pyxel  # pylint: disable=C0415

        self.pyxel = pyxel

        pyxel.init(
            GameObject.SCREEN_WIDTH, GameObject.SCREEN_HEIGHT, title="pyxel tycoon"
        )
        self.pyxel.load("map_tile.pyxres")
        self.pyxel.mouse(True)

        self.game_core = None
        self.wait_frames = 0
        pyxel.run(self.update, self.draw)

    def update(self):
        if self.game_core is None:
            self.wait_frames += 1
            if self.wait_frames >= self.LOAD_WAIT_FRAMES:
                self.game_core = GameCore()
            return
        self.game_core.update()
        if self.game_core.is_reset():
            AreaBlockAlgorithmGenerator.recreate()
            Navigator.recreate()
            NavigationPopup.recreate()
            self.game_core = GameCore(reset=True)

    def draw(self):
        if self.game_core is not None:
            self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
