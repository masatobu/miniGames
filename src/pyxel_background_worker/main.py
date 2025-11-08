# title: pyxel background worker
# author: masatobu

import time
import json
import random
import hashlib
import base64
import binascii
from abc import ABC, abstractmethod
from enum import Enum

try:
    from .logic import GameLogic, Job, Building, Resource  # pylint: disable=C0413
except ImportError:
    from logic import GameLogic, Job, Building, Resource  # pylint: disable=C0413


class Color(Enum):
    BUTTON_EDGE = 9
    BUTTON_EDGE_HOVER = 14
    TEXT = 12
    CURSOL = 7
    ADD = 13
    SELECTED_ADD = 14
    AREA_FRAME = 1
    BACK = 0


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, col):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col, is_fill):
        pass

    @abstractmethod
    def draw_image(self, x, y, width, height, src_tile_x, src_tile_y, scale):
        pass

    @abstractmethod
    def clear(self):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text, col):
        self.pyxel.text(x, y, str(text), col.value)

    def draw_rect(self, x, y, w, h, col, is_fill):
        param = {"x": x, "y": y, "w": w, "h": h, "col": col.value}
        if is_fill:
            self.pyxel.rect(**param)
        else:
            self.pyxel.rectb(**param)

    def draw_image(self, x, y, width, height, src_tile_x, src_tile_y, scale):
        self.pyxel.blt(
            x,
            y,
            0,
            src_tile_x * 8,
            src_tile_y * 8,
            width,
            height,
            scale=scale,
            colkey=Color.BACK.value,
        )

    def clear(self):
        self.pyxel.cls(0)


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


class GameObject(ABC):
    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class Clock:
    def __init__(self, count_ms):
        self.count_ms = count_ms
        self.bef_count = time.perf_counter()

    def is_up(self):
        if self.count_ms == 0:
            return False
        if self.count_ms == 1:
            return True
        now_count = time.perf_counter()
        if (now_count - self.bef_count) * 1000 >= self.count_ms:
            self.bef_count = now_count
            return True
        return False


class BuildingArea(GameObject):
    IMAGE_SIZE = (7, 7)

    def __init__(self, image_pos, vacant_image_pos, pos, area_width):
        super().__init__()
        self.stay_num = 0
        self.pos_list = []
        self.image_pos = image_pos
        self.vacant_image_pos = vacant_image_pos
        self.pos = pos
        self.area_width = area_width

    def _get_pos(self):
        return (int(random.random() * self.area_width), 0)

    def draw(self):
        for i, d in enumerate(self.pos_list):
            image_pos = self.image_pos if i < self.stay_num else self.vacant_image_pos
            self.view.draw_image(
                self.pos[0] + d[0], self.pos[1] + d[1], *self.IMAGE_SIZE, *image_pos, 1
            )

    def set_num(self, total, stay):
        append_num = total - len(self.pos_list)
        for _ in range(append_num):
            self.pos_list.append(self._get_pos())
        self.stay_num = stay


class HouseArea(BuildingArea):
    IMAGE_POS = (1, 2)
    VACANT_IMAGE_POS = (3, 2)

    def __init__(self):
        super().__init__(self.IMAGE_POS, self.VACANT_IMAGE_POS, (35, 45), 245)


class FarmArea(BuildingArea):
    IMAGE_POS = (2, 2)
    VACANT_IMAGE_POS = (4, 2)

    def __init__(self):
        super().__init__(self.IMAGE_POS, self.VACANT_IMAGE_POS, (35, 90), 100)


class WoodshedArea(BuildingArea):
    IMAGE_POS = (2, 2)
    VACANT_IMAGE_POS = (4, 2)

    def __init__(self):
        super().__init__(self.IMAGE_POS, self.VACANT_IMAGE_POS, (180, 90), 100)


class WorkingArea(GameObject):
    IMAGE_SIZE = (5, 6)
    SELECTED_IMAGE_POS = (1, 1)

    def __init__(self, image_pos, pos, area_width, area_height):
        super().__init__()
        self.pos_list = []
        self.image_pos = image_pos
        self.pos = pos
        self.area_width = area_width
        self.area_height = area_height
        self.selected_flg_list = []

    def _get_pos(self):
        x = int(random.random() * self.area_width)
        y = int(random.random() * (self.area_height - self.IMAGE_SIZE[1]))
        return (x, y)

    def draw(self):
        self.draw_back()
        self.draw_workers()

    def draw_workers(self, scale=1):
        for d, selected_flg in zip(self.pos_list, self.selected_flg_list):
            image_pos = self.SELECTED_IMAGE_POS if selected_flg else self.image_pos
            self.view.draw_image(
                self.pos[0] + d[0],
                self.pos[1] + d[1],
                *self.IMAGE_SIZE,
                *image_pos,
                scale,
            )

    def draw_back(self):
        size = self.get_area_size()
        frame_rect = (*self.pos, size[0] + 10, size[1])
        self.view.draw_rect(*frame_rect, Color.AREA_FRAME, True)

    def set_num(self, total, append_pos_list=None):
        append_num = total - len(self.pos_list)
        if append_num < 0:
            self.pos_list = self.pos_list[:total]
            self.selected_flg_list = self.selected_flg_list[:total]
        else:
            for i in range(append_num):
                append_pos = (
                    self._get_pos() if append_pos_list is None else append_pos_list[i]
                )
                self.pos_list.append(append_pos)
                self.selected_flg_list.append(False)

    def select(self, x, y, w, h) -> bool:
        self.selected_flg_list = [
            (
                x <= self.pos[0] + pos_x
                and y <= self.pos[1] + pos_y
                and x + w >= self.pos[0] + pos_x + self.IMAGE_SIZE[0]
                and y + h >= self.pos[1] + pos_y + self.IMAGE_SIZE[1]
            )
            for pos_x, pos_y in self.pos_list
        ]
        return any(self.selected_flg_list)

    def unselect(self):
        self.selected_flg_list = [False for _ in self.pos_list]

    def is_click(self, x, y, w, h) -> bool:
        click_point = (x + w, y + h)
        area_size = self.get_area_size()
        return (
            self.pos[0] <= click_point[0] <= self.pos[0] + area_size[0] + 10
            and self.pos[1] <= click_point[1] <= self.pos[1] + area_size[1]
        )

    def get_selected_num(self) -> int:
        return sum(1 for selected in self.selected_flg_list if selected)

    def get_area_size(self):
        return self.area_width, self.area_height


class NoJobArea(WorkingArea):
    def __init__(self):
        image_pos = (1, 0)
        pos = (35, 30)
        width = 245
        height = self.IMAGE_SIZE[1]
        super().__init__(image_pos, pos, width, height)


class FarmerArea(WorkingArea):
    def __init__(self):
        image_pos = (3, 0)
        pos = (35, 120)
        width = 100
        height = 110
        super().__init__(image_pos, pos, width, height)


class LoggerArea(WorkingArea):
    def __init__(self):
        image_pos = (4, 0)
        pos = (180, 120)
        width = 100
        height = 110
        super().__init__(image_pos, pos, width, height)


class HouseBuilderArea(WorkingArea):
    def __init__(self):
        image_pos = (2, 0)
        pos = (35, 60)
        width = 245
        height = self.IMAGE_SIZE[1]
        super().__init__(image_pos, pos, width, height)


class FarmBuilderArea(WorkingArea):
    def __init__(self):
        image_pos = (2, 0)
        pos = (35, 105)
        width = 100
        height = self.IMAGE_SIZE[1]
        super().__init__(image_pos, pos, width, height)


class WoodshedBuilderArea(WorkingArea):
    def __init__(self):
        image_pos = (2, 0)
        pos = (180, 105)
        width = 100
        height = self.IMAGE_SIZE[1]
        super().__init__(image_pos, pos, width, height)


class NewWorkerArea(WorkingArea):
    SCALE = 2

    def __init__(self):
        image_pos = (1, 0)
        pos = (10, 7)
        width = None
        height = None
        super().__init__(image_pos, pos, width, height)
        self.set_num(1, append_pos_list=[(10, 3)])

    def draw(self):
        super().draw()
        color = Color.SELECTED_ADD if all(self.selected_flg_list) else Color.ADD
        self.view.draw_text(14, 11, "+", color)

    def draw_workers(self, scale=1):
        super().draw_workers(self.SCALE)

    def get_area_size(self):
        return tuple(img_size * self.SCALE for img_size in self.IMAGE_SIZE)


class ReportStore:
    LOAD_FILENAME = "/load_data.txt"
    SAVE_FILENAME = "/save_data.txt"
    SECRET = "my background worker game secret hahaha"

    def __init__(self):
        self.version = 2
        self.secret_hash = hashlib.sha256(self.SECRET.encode("utf-8")).digest()

    def set_local_storage(self, value):
        with open(self.SAVE_FILENAME, "w", encoding="utf-8") as f:
            save_data = self._crypt(value)
            f.write(save_data)
        return True

    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    def _crypt(self, target):
        data = target.encode("utf-8")
        xored = self._xor_bytes(data, self.secret_hash)
        enc = base64.b64encode(xored).decode("ascii")
        return enc

    def get_local_storage(self):
        ret = ""
        try:
            with open(self.LOAD_FILENAME, "r", encoding="utf-8") as f:
                ret = f.read()
        except FileNotFoundError:
            return None
        decrypt = self._decrypt(ret)
        return decrypt

    def _decrypt(self, target):
        try:
            xored = base64.b64decode(target.encode("ascii"))
        except binascii.Error:
            return None
        data = self._xor_bytes(xored, self.secret_hash)
        return data.decode("utf-8")

    def save(self, data):
        return self.set_local_storage(json.dumps({**data, "version": self.version}))

    def load(self):
        storage_str = self.get_local_storage()
        if storage_str is None:
            return None
        try:
            dump = json.loads(storage_str)
        except (json.JSONDecodeError, TypeError):
            return None
        if dump.get("version", None) != self.version:
            return None
        del dump["version"]
        return dump


class Cursol(GameObject):
    def __init__(self):
        super().__init__()
        self.start = None
        self.end = None
        self.select_rect = None

    def _get_rect(self) -> tuple[int, int, int, int]:
        size = (abs(j - i) for i, j in zip(self.start, self.end))
        pos = (min(i, j) for i, j in zip(self.start, self.end))
        return (*pos, *size)

    def update(self):
        super().update()
        self.select_rect = None
        if self.input.is_click():
            self.start = (self.input.get_mouse_x(), self.input.get_mouse_y())
            self.end = self.start
            return
        if self.start is None:
            return
        if self.input.is_release():
            self.select_rect = self._get_rect()
            self.start = self.end = None
            return
        self.end = (self.input.get_mouse_x(), self.input.get_mouse_y())

    def draw(self):
        if self.start is None or self.end is None:
            return
        self.view.draw_rect(*self._get_rect(), Color.CURSOL, False)

    def get_select(self) -> tuple[int, int, int, int]:
        return self.select_rect


class GameCore:
    NEW_WORKER_ID = "NEW WORKER"

    def __init__(self, is_reset=False):
        self.report_store = ReportStore()
        self.view = PyxelView.create()
        self.input = PyxelInput.create()
        load_data = self.report_store.load() if not is_reset else None
        self.game_logic = GameLogic.from_dict(load_data)
        self.job_workers_map = {
            key: []
            for key in [
                (None, None),
                (Job.BUILDER, Building.HOUSE),
                (Job.FARMER, Building.FARM),
                (Job.BUILDER, Building.FARM),
                (Job.LOGGER, Building.WOODSHED),
                (Job.BUILDER, Building.WOODSHED),
            ]
        }
        self.clock = Clock(1000)
        self.area_map = {
            Building.HOUSE: HouseArea(),
            Building.FARM: FarmArea(),
            Building.WOODSHED: WoodshedArea(),
        }
        self.working_area = {
            (None, None): NoJobArea(),
            (Job.FARMER, Building.FARM): FarmerArea(),
            (Job.LOGGER, Building.WOODSHED): LoggerArea(),
            (Job.BUILDER, Building.HOUSE): HouseBuilderArea(),
            (Job.BUILDER, Building.FARM): FarmBuilderArea(),
            (Job.BUILDER, Building.WOODSHED): WoodshedBuilderArea(),
            self.NEW_WORKER_ID: NewWorkerArea(),
        }
        self._update_job_workers_map()
        self.cursol = Cursol()
        self.selected_area_map = None
        self.flg_is_reset = False

    def update(self):
        if self.game_logic.is_clear():
            if self.input.is_release():
                self.flg_is_reset = True
            return
        is_updated = False
        if self.clock.is_up():
            self.game_logic.turn()
            is_updated = True
        if self._update_cursol_action():
            self.report_store.save(self.game_logic.to_dict())
            is_updated = True
        if is_updated:
            self._update_job_workers_map()

    def _update_cursol_action(self) -> bool:
        self.cursol.update()
        select_rect = self.cursol.get_select()
        if select_rect is None:
            return False
        if self.selected_area_map is None:
            self.selected_area_map = {}
            if self.working_area[self.NEW_WORKER_ID].select(*select_rect):
                # NEW WORKERのiconは必ず一つ
                self.selected_area_map[self.NEW_WORKER_ID] = 1
                return False
            for key, area in self.working_area.items():
                if area.select(*select_rect):
                    self.selected_area_map[key] = area.get_selected_num()
            if len(self.selected_area_map) == 0:
                self.selected_area_map = None
            return False
        for area in self.working_area.values():
            area.unselect()
        selected_area_map = self.selected_area_map
        self.selected_area_map = None
        for to_key, to_area in self.working_area.items():
            if to_key == self.NEW_WORKER_ID:
                continue
            if to_area.is_click(*select_rect):
                return self._move_worker(to_key, selected_area_map)
        return False

    def _move_worker(self, to_key, selected_area_map) -> bool:
        return_flg = False
        for from_key, select_count in selected_area_map.items():
            pop_list = []
            if from_key == self.NEW_WORKER_ID:
                add_id = self.game_logic.add_worker()
                pop_list.append(add_id)
            else:
                pop_list = self.job_workers_map[from_key]
            for _ in range(select_count):
                worker_id = pop_list.pop()
                result = self.game_logic.set_worker_job(worker_id, *to_key)
                if not result:
                    pop_list.append(worker_id)
                    return return_flg
                return_flg = True
        return return_flg

    def _update_job_workers_map(self):
        worker_count = self.game_logic.get_worker_num()
        self.job_workers_map = {key: [] for key in self.job_workers_map}
        for i in range(worker_count):
            job, place = self.game_logic.get_worker_job(
                i
            ), self.game_logic.get_worker_place(i)
            self.job_workers_map[(job, place)].append(i)
        for attribute, area in self.area_map.items():
            area.set_num(
                self.game_logic.get_building_num(attribute),
                self.game_logic.get_stay_building_num(attribute),
            )
        for attribute, area in self.working_area.items():
            if attribute == self.NEW_WORKER_ID:
                continue
            area.set_num(len(self.job_workers_map[attribute]))

    def draw(self):
        self.view.clear()
        if self.game_logic.is_clear():
            self._draw_clear()
            return
        self._draw_status_text()
        self._draw_progress()
        for area in list(self.area_map.values()) + list(self.working_area.values()):
            area.draw()
        self._draw_worker_num()
        self._draw_icon()
        self.cursol.draw()

    def _draw_worker_num(self):
        for x, y, label in [
            (35, 10, self.game_logic.get_worker_num()),
            (60, 10, "/"),
            (70, 10, self.game_logic.get_target_num()),
        ]:
            self.view.draw_text(x, y, label, Color.TEXT)

    def _draw_clear(self):
        self.view.draw_text(300 // 2 - 50, 400 // 2 - 100, "Game Clear", Color.TEXT)
        self.view.draw_text(300 // 2 - 60, 400 // 2 - 70, "Tap to Continue", Color.TEXT)

    def _draw_icon(self):
        for pos, image_pos in [
            ((65, 77), (1, 3)),
            ((210, 77), (2, 3)),
        ]:
            for i in range(5):
                icon_pos = (pos[0] + i * 10, pos[1])
                self.view.draw_image(*icon_pos, 8, 8, *image_pos, 1)

    def _draw_status_text(self):
        for pos, text in [
            (pos, self._get_resource_change_text(job, place))
            for pos, job, place in [
                ((120, 241), None, None),
                ((10, 51), Job.BUILDER, Building.HOUSE),
                ((80, 241), Job.FARMER, Building.FARM),
                ((10, 96), Job.BUILDER, Building.FARM),
                ((235, 241), Job.LOGGER, Building.WOODSHED),
                ((155, 96), Job.BUILDER, Building.WOODSHED),
            ]
        ] + [
            (pos, self.get_scale_str(self.game_logic.get_resoruce(resource)))
            for pos, resource in [
                ((40, 241), Resource.FOOD),
                ((185, 241), Resource.WOOD),
            ]
        ]:
            self.view.draw_text(*pos, text, Color.TEXT)

    def _get_resource_change_text(self, job, place):
        if job != Job.BUILDER:
            resource_change = max(
                self.game_logic.get_resource_change(job, place).values()
            )
            ret = f"{'+' if resource_change > 0 else ''}{self.get_scale_str(resource_change)}"
            ret += "/s"
            return ret
        resource_change = max(self.game_logic.get_build_cost(place).values())
        ret = (
            f"{'+' if resource_change > 0 else ''}{self.get_scale_str(resource_change)}"
        )
        return ret

    def _draw_progress(self):
        for x, y, is_fill, width in [
            (35, 52, False, 255),
            (
                35,
                52,
                True,
                255
                * self.game_logic.get_build_progress(Building.HOUSE)
                / self.game_logic.get_time_cost(Building.HOUSE),
            ),
            (35, 97, False, 110),
            (
                35,
                97,
                True,
                110
                * self.game_logic.get_build_progress(Building.FARM)
                / self.game_logic.get_time_cost(Building.FARM),
            ),
            (180, 97, False, 110),
            (
                180,
                97,
                True,
                110
                * self.game_logic.get_build_progress(Building.WOODSHED)
                / self.game_logic.get_time_cost(Building.WOODSHED),
            ),
        ]:
            self.view.draw_rect(x, y, width, 5, Color.TEXT, is_fill)

    def is_reset(self):
        return self.flg_is_reset

    @staticmethod
    def get_scale_str(num):
        digit_list = ["K", "M", "B", "T", "Q"]
        neg_let = "-" if num < 0 else ""
        abs_num = abs(num)

        sep_num_list = [abs_num % 1000]
        buf_num = abs_num
        for _ in range(len(digit_list)):
            buf_num = buf_num // 1000
            if buf_num == 0:
                break
            sep_num_list.append(buf_num % 1000)

        digit = "" if len(sep_num_list) == 1 else digit_list[len(sep_num_list) - 2]
        return f"{neg_let}{sep_num_list[-1]}{digit}"


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        pyxel.init(300, 260, title="Pyxel Background Worker")
        self.pyxel.load("images.pyxres")
        self.pyxel.mouse(True)

        self.game_core = GameCore()
        pyxel.run(self.update, self.draw)

    def update(self):
        self.game_core.update()
        if self.game_core.is_reset():
            self.game_core = GameCore(is_reset=True)

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
