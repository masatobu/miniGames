# title: pyxel background worker
# author: masatobu

import time
import json
from abc import ABC, abstractmethod
from enum import Enum

try:
    from .logic import GameLogic, Job, Building, Resource  # pylint: disable=C0413
except ImportError:
    from logic import GameLogic, Job, Building, Resource  # pylint: disable=C0413


class Color(Enum):
    BUTTON_EDGE = 9
    BUTTON_EDGE_HOVER = 14
    TEXT = 7


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text, col):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col, is_fill):
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
    def __init__(self):
        self.view = PyxelView.create()
        self.input = PyxelInput.create()

    @abstractmethod
    def draw(self):
        pass

    def update(self):
        pass


class Button(GameObject):
    WIDTH = 32
    HEIGHT = 14
    TEXT_LEFT_MARGIN = 5
    TEXT_TOP_MARGIN = 4

    def __init__(self, x, y, text):
        super().__init__()
        self.x = x
        self.y = y
        self.text = text
        self.hover_flg = False
        self.click_flg = False
        self.visible = True

    def click(self, mouse_x, mouse_y):
        if (
            self.x <= mouse_x <= self.x + self.WIDTH
            and self.y <= mouse_y <= self.y + self.HEIGHT
        ):
            result = self.hover_flg
            self.hover_flg = not self.hover_flg
            return result
        self.hover_flg = False
        return False

    def is_hover(self):
        return self.hover_flg

    def is_click(self):
        return self.click_flg

    def set_visible(self, visible):
        self.visible = visible

    def is_visible(self):
        return self.visible

    def draw(self):
        if self.is_visible():
            self.view.draw_rect(
                self.x,
                self.y,
                self.WIDTH,
                self.HEIGHT,
                Color.BUTTON_EDGE_HOVER if self.hover_flg else Color.BUTTON_EDGE,
                True,
            )
            self.view.draw_text(
                self.x + self.TEXT_LEFT_MARGIN,
                self.y + self.TEXT_TOP_MARGIN,
                self.text,
                Color.TEXT,
            )

    def update(self):
        self.click_flg = False
        if not self.is_visible():
            return
        if self.input.is_click():
            self.click_flg = self.click(
                self.input.get_mouse_x(), self.input.get_mouse_y()
            )


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


class GameCore:
    LINE_MAP = {
        (None, None): 20,
        (Job.BUILDER, Building.HOUSE): 50,
        (Job.FARMER, Building.FARM): 80,
        (Job.BUILDER, Building.FARM): 110,
        (Job.LOGGER, Building.WOODSHED): 140,
        (Job.BUILDER, Building.WOODSHED): 170,
    }

    def __init__(self):
        self.report_store = ReportStore()
        self.view = PyxelView.create()
        self.game_logic = GameLogic.from_dict(self.report_store.load())
        self.button_map = self._init_buttons()
        self.job_workers_map = {key: [] for key in self.LINE_MAP}
        self.clock = Clock(1000)
        self._update_job_workers_map()

    def _init_buttons(self):
        button_map = {}
        for key, y in self.LINE_MAP.items():
            line_buttons = [(150, "add")]
            if key != (None, None):
                line_buttons.append((200, "del"))
            for x, text in line_buttons:
                button_map[(*key, text)] = Button(x, y, text)
        return button_map

    def update(self):
        if self.clock.is_up():
            self.game_logic.turn()
        if self._update_button_click():
            self._update_job_workers_map()
            self.report_store.save(self.game_logic.to_dict())

    def _update_job_workers_map(self):
        worker_count = self.game_logic.get_worker_num()
        self.job_workers_map = {key: [] for key in self.LINE_MAP}
        for i in range(worker_count):
            job, place = self.game_logic.get_worker_job(
                i
            ), self.game_logic.get_worker_place(i)
            self.job_workers_map[(job, place)].append(i)

    def _update_button_click(self) -> bool:
        for key, button in self.button_map.items():
            button.update()
            if button.is_click():
                if key == (None, None, "add"):
                    self.game_logic.add_worker()
                else:
                    set_keys = [(None, None), key[:2]]
                    if key[2] == "del":
                        set_keys.reverse()
                    pop_list = self.job_workers_map[set_keys[0]]
                    if len(pop_list) > 0:
                        worker_id = pop_list.pop()
                        self.game_logic.set_worker_job(worker_id, *set_keys[1])
                return True
        return False

    def draw(self):
        self.view.clear()
        self._draw_worker_lines()
        self._draw_status()

    def _draw_worker_lines(self):
        for (job, place), y in self.LINE_MAP.items():
            label = (
                "NO JOB"
                if job is None
                else place.name + " " + job.name if job == Job.BUILDER else job.name
            )
            for x, text in [
                (20, label),
                (100, len(self.job_workers_map[(job, place)])),
                (250, self._get_resource_change_text(job, place)),
            ]:
                self.view.draw_text(x, y + Button.TEXT_TOP_MARGIN, text, Color.TEXT)
            for button_name in ("add", "del"):
                key = (job, place, button_name)
                if key in self.button_map:
                    self.button_map[key].draw()

    def _get_resource_change_text(self, job, place):
        resource_change = max(self.game_logic.get_resource_change(job, place).values())
        ret = f"{'+' if resource_change > 0 else ''}{resource_change}"
        if job != Job.BUILDER:
            ret += "/s"
        return ret

    def _draw_status(self):
        for x, y, text in [
            (20, 200, "FOOD"),
            (60, 200, self.game_logic.get_resoruce(Resource.FOOD)),
            (100, 200, "WOOD"),
            (140, 200, self.game_logic.get_resoruce(Resource.WOOD)),
            (20, 210, "HOUSE"),
            (60, 210, self.game_logic.get_building_num(Building.HOUSE)),
            (100, 210, "FARM"),
            (140, 210, self.game_logic.get_building_num(Building.FARM)),
            (180, 210, "WOODSHED"),
            (220, 210, self.game_logic.get_building_num(Building.WOODSHED)),
        ]:
            self.view.draw_text(x, y, text, Color.TEXT)
        for x, is_fill, width in [
            (20, False, 70),
            (
                20,
                True,
                70
                * self.game_logic.get_build_progress(Building.HOUSE)
                / self.game_logic.get_time_cost(Building.HOUSE),
            ),
            (100, False, 70),
            (
                100,
                True,
                70
                * self.game_logic.get_build_progress(Building.FARM)
                / self.game_logic.get_time_cost(Building.FARM),
            ),
            (180, False, 70),
            (
                180,
                True,
                70
                * self.game_logic.get_build_progress(Building.WOODSHED)
                / self.game_logic.get_time_cost(Building.WOODSHED),
            ),
        ]:
            self.view.draw_rect(x, 218, width, 5, Color.TEXT, is_fill)


class ReportStore:
    LOAD_FILENAME = "/load_data.txt"
    SAVE_FILENAME = "/save_data.txt"

    def __init__(self):
        self.version = 1

    def set_local_storage(self, value):
        with open(self.SAVE_FILENAME, "w", encoding="utf-8") as f:
            f.write(value)
        return True

    def get_local_storage(self):
        ret = ""
        try:
            with open(self.LOAD_FILENAME, "r", encoding="utf-8") as f:
                ret = f.read()
        except FileNotFoundError:
            return None
        return ret

    def save(self, data):
        return self.set_local_storage(json.dumps({**data, "version": self.version}))

    def load(self):
        storage_str = self.get_local_storage()
        if storage_str is not None:
            dump = json.loads(storage_str)
            if dump.get("version", None) == self.version:
                del dump["version"]
                return dump
        return None


class PyxelController:
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

        self.game_core = GameCore()

        pyxel.init(320, 240, title="Pyxel Background Worker")
        pyxel.mouse(True)
        pyxel.run(self.update, self.draw)

    def update(self):
        self.game_core.update()

    def draw(self):
        self.game_core.draw()


if __name__ == "__main__":
    PyxelController()
