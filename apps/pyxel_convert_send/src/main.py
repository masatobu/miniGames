# title: pyxel convert send
# author: masatobu

from enum import Enum
import random

try:
    from .framework import (
        PyxelFieldView,
        Direct,
        Node,
        Color,
        GameObject,
        FieldObject,
        Image,
    )  # pylint: disable=C0413
    from .field_nodes import (
        UnitPlayer,
        UnitEnemy,
        BulletPlayer,
        BulletEnemy,
        Curve,
        Convert,
        Split,
        Merge,
        Unit,
        FieldNode,
    )  # pylint: disable=C0413
except ImportError:
    from framework import (
        PyxelFieldView,
        Direct,
        Node,
        Color,
        GameObject,
        FieldObject,
        Image,
    )  # pylint: disable=C0413
    from field_nodes import (
        UnitPlayer,
        UnitEnemy,
        BulletPlayer,
        BulletEnemy,
        Curve,
        Convert,
        Split,
        Merge,
        Unit,
        FieldNode,
    )  # pylint: disable=C0413


class Action(Enum):
    FIELD = (0, 0)
    CURVE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 0)
    CURVE_REV = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 2)
    CONVERT = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 4)
    SPLIT = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 6)
    MERGE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 8)
    DELETE = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 11)
    NEXT = (PyxelFieldView.FIELD_TILE_WIDTH + 1, 13)


class Field(FieldObject):
    def __init__(self, enemy_split_num, enemy_color_list):
        super().__init__()
        self.enemy_split_num = enemy_split_num
        self.enemy_color_list = enemy_color_list
        self.enemy_y_color_map = {}
        unit_player = UnitPlayer(0, self._get_random_new_player_y_pos())
        y_list = self._get_random_new_enemy_y_pos(set())
        unit_enemy = UnitEnemy(11, *self._get_enemy_param(y_list[0:1])[0])
        self.unit_list = [unit_player, unit_enemy]
        self.bullet_map = {}
        self.node_map = {unit.get_tile_pos(): unit for unit in self.unit_list}

    def _get_random_new_player_y_pos(self):
        return random.randint(0, PyxelFieldView.FIELD_TILE_HEIGHT - 1)

    def update(self):
        self._update_bullet()
        self._update_unit()
        self._shot()

    def _get_enemy_param(self, y_list):
        ret = []
        for y in y_list:
            if y not in self.enemy_y_color_map:
                counter = len(self.enemy_y_color_map)
                if counter >= len(self.enemy_color_list):
                    continue
                self.enemy_y_color_map[y] = self.enemy_color_list[counter]
            ret.append((y, self.enemy_y_color_map[y]))
        return ret

    def _update_unit(self):
        bef_enemies_y_set = self._get_enemies_y_set()
        self.unit_list = [unit for unit in self.unit_list if not unit.is_death()]
        if len(bef_enemies_y_set) > len(self._get_enemies_y_set()):
            if len(self.enemy_y_color_map) == len(self.enemy_color_list):
                bef_enemies_y_set |= (
                    set(y for y in range(PyxelFieldView.FIELD_TILE_HEIGHT))
                    - self.enemy_y_color_map.keys()
                )
            append_unit_list = [
                UnitEnemy(11, y, color)
                for y, color in self._get_enemy_param(
                    self._get_random_new_enemy_y_pos(bef_enemies_y_set)
                )
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

    def get_enemy_color(self, tile_x, tile_y):
        if (tile_x, tile_y) in self.node_map:
            node = self.node_map[(tile_x, tile_y)]
            if isinstance(node, UnitEnemy):
                return node.get_color()
        return None


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
            Action.NEXT,
        ]
    }

    def __init__(self):
        super().__init__()
        self.is_select = False
        self.click_pos = (-1, -1)
        self.select_pos = None
        self.select_action = None
        self.flg_stage_clear = False

    def update(self):
        self.select_pos = None
        if self.input.is_click():
            x, y = self.input.get_mouse_x(), self.input.get_mouse_y()
            if x is not None and y is not None:
                for k, v in self.AVAIL_POS_MAP.items():
                    if v[0] <= x < v[0] + v[2] and v[1] <= y < v[1] + v[3]:
                        if k == Action.NEXT and not self.flg_stage_clear:
                            break
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
        if not self.flg_stage_clear:
            draws.append(
                (*self.AVAIL_POS_MAP[Action.NEXT][0:2], 8, 8, Color.BLACK, True)
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

    def set_stage_clear(self, flg_stage_clear):
        self.flg_stage_clear = flg_stage_clear


class Scout(GameObject):
    FRAME_RECT = (-10, -3, 17, 14)
    PADDING_CENTER = (4, 3)
    PADDING_UP = (0, 0)
    PADDING_DOWN = (0, 6)

    def __init__(self, tile_y, color):
        super().__init__()
        x_pos = (
            PyxelFieldView.FIELD_OFFSET_X
            + PyxelFieldView.FIELD_WIDTH
            - self.FRAME_RECT[2]
            + self.FRAME_RECT[0]
        )
        y_pos = 8 * tile_y + PyxelFieldView.FIELD_OFFSET_Y + self.FRAME_RECT[1]
        self.draw_pos = (x_pos, y_pos)
        self.color = color
        self.merge_color = self._get_merge_color(color)

    def _get_merge_color(self, color):
        for merge_color, key_color in Merge.COLOR_MAP.items():
            # 配合色が異なる場合のみ設定する
            if color == key_color and len(merge_color) > 1:
                return sorted(merge_color, key=lambda x: x.value)
        return None

    def _draw_elm(self, kind, pos_list, opt):
        draw_pos = tuple(
            pos + padding + line_pos for pos, padding, line_pos in zip(*pos_list)
        )
        if kind == "draw_image":
            self.view.set_pal([Color.WHITE, opt])
            self.view.draw_image(*draw_pos, *Image.PLAYER_BULLET.value, Direct.RIGHT)
            self.view.set_pal([])
        elif kind == "draw_text":
            self.view.draw_text(*draw_pos, opt)

    def draw(self):
        self.view.set_clip(None)
        self.view.draw_rect(*self.draw_pos, *self.FRAME_RECT[2:4], Color.BLACK, True)
        self.view.draw_rect(*self.draw_pos, *self.FRAME_RECT[2:4], Color.GREEN, False)
        if self.merge_color is not None:
            for kind, padding, line_pos, opt in [
                ("draw_image", Scout.PADDING_UP, (0, 0), self.color),
                ("draw_text", Scout.PADDING_UP, (7, 2), "="),
                ("draw_image", Scout.PADDING_DOWN, (0, 0), self.merge_color[0]),
                ("draw_text", Scout.PADDING_DOWN, (7, 1), "+"),
                ("draw_image", Scout.PADDING_DOWN, (9, 0), self.merge_color[1]),
            ]:
                self._draw_elm(kind, [self.draw_pos, padding, line_pos], opt)
        else:
            self._draw_elm(
                "draw_image",
                [self.draw_pos, Scout.PADDING_CENTER, (0, 0)],
                self.color,
            )


class GameParameter:
    GAMA_PARAMS_LIST = [
        (2, [Color.NODE_RED, Color.NODE_GREEN, Color.NODE_BLUE] * 2),
        (4, [Color.NODE_YELLOW, Color.NODE_RED, Color.NODE_GREEN]),
        (4, [Color.NODE_CYAN, Color.NODE_GREEN, Color.NODE_BLUE]),
        (4, [Color.NODE_PURPLE, Color.NODE_RED, Color.NODE_BLUE]),
        (2, [Color.NODE_YELLOW, Color.NODE_ORANGE]),
        (2, [Color.NODE_YELLOW, Color.NODE_BROWN]),
        (2, [Color.NODE_PURPLE, Color.NODE_NAVY]),
        (2, [Color.NODE_CYAN, Color.NODE_DEEP_BLUE]),
    ]

    @classmethod
    def get(cls):
        param = random.randint(0, len(cls.GAMA_PARAMS_LIST) - 1)
        return cls.GAMA_PARAMS_LIST[param]


class GameCore(GameObject):
    WAIT_ENABLE_NEXT_TERN = 180

    def __init__(self):
        super().__init__()
        self.field = None
        self.cursor = None
        self.stage_clear_tern = 0
        self.scout = None
        self.parameter = GameParameter()
        self._game_reset()

    def update(self):
        self._action()
        self.field.update()
        self._update_stage_clear_wait_tern()

    def _update_stage_clear_wait_tern(self):
        if self.field.get_bullet_count()[1] == 0:
            self.stage_clear_tern += 1
        else:
            self.stage_clear_tern = 0
        self.cursor.set_stage_clear(self.stage_clear_tern > self.WAIT_ENABLE_NEXT_TERN)

    def _action(self):
        bef_act = self.cursor.get_action()
        self.cursor.update()
        click_pos = self.cursor.get_select_pos()
        aft_act = self.cursor.get_action()
        if click_pos is not None:
            self.scout = None
        if aft_act == Action.NEXT:
            self._game_reset()
        elif aft_act == Action.FIELD and click_pos is not None:
            if bef_act is None or bef_act == Action.FIELD:
                enemy_color = self.field.get_enemy_color(*click_pos)
                if enemy_color is not None:
                    self.scout = Scout(click_pos[1], enemy_color)
                else:
                    self.field.mainte(*click_pos)
            elif bef_act == Action.DELETE:
                self.field.delete(*click_pos)
            else:
                self.field.build(bef_act, *click_pos)

    def _get_game_parameter(self):
        return self.parameter.get()

    def _game_reset(self):
        self.field = Field(*self._get_game_parameter())
        self.cursor = Cursor()
        self.stage_clear_tern = 0
        self.scout = None

    def draw(self):
        self.view.clear()
        self.view.set_clip(None)
        self.field.draw()
        self.cursor.draw()
        self._draw_graph()
        if self.scout is not None:
            self.scout.draw()

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
