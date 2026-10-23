# title: pyxel tycoon
# author: masatobu

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import NamedTuple, Optional
import random

# ブラウザ実行版（pyxel package / app2html）では src/ 配下が直接実行され、src パッケージ
# として解決できないため、相対 import を試したうえでトップレベル import にフォールバックする
try:
    from .util import enum_from_name, enum_name
except ImportError:
    from util import enum_from_name, enum_name


class MaterialType(Enum):
    WOOD = 0
    STONE = 1
    PLANK = 2
    BRICK = 3
    HAMMER = 4

    def get_resource_type(self) -> "ResourceType":
        # PLANK・BRICK・HAMMER は作業台が加工する資材で対応する資源が無いため、対応表に含めない。
        # 呼び出し元（Resource.__init__）は資源のエリアの material_type からのみ呼ぶため、
        # 現状は Wood/Stone 以外で呼ばれない
        return {
            MaterialType.WOOD: ResourceType.TREE,
            MaterialType.STONE: ResourceType.ROCK,
        }[self]


class ResourceType(Enum):
    TREE = 0
    ROCK = 1


class AreaKind(Enum):
    """ナビゲーションの目標のエリアの種別（find_nearest_area の問い合わせ対象）"""

    TREE = auto()
    ROCK = auto()
    WORKBENCH = auto()
    NEXT_BLOCK = auto()


class WorkbenchParam(NamedTuple):
    # 作業台が消費する素材の種類・必要量・加工時間。加工後の資材の種類・個数は
    # ここに持たせず、作業台のエリアの AreaParam.material_type / material_num
    # （加工後の資材。U1）で表す（二重持ちを避ける。U2）。
    # material_types は消費する素材の種類の並び（単一素材は要素 1 つ）、material_num は
    # 種類ごとに共通の必要量。全種類を 1 つずつ同時に投入するため、投入済みの数は
    # 種類によらず等しく、Workbench は投入回数 1 つで持つ（ID-025 U1）
    material_types: tuple[MaterialType, ...]
    material_num: int
    process_frames: int

    def to_save_data(self) -> dict:
        return {
            "material_types": [t.name for t in self.material_types],
            "material_num": self.material_num,
            "process_frames": self.process_frames,
        }

    @classmethod
    def from_save_data(cls, data: dict) -> "WorkbenchParam":
        return cls(
            material_types=tuple(MaterialType[n] for n in data["material_types"]),
            material_num=data["material_num"],
            process_frames=data["process_frames"],
        )


class AreaParam(NamedTuple):
    fee_num: int = 0
    enemy_power: int = 0
    spawner_power: int = 0
    material_num: int = 0
    material_type: Optional[MaterialType] = None
    fee_type: Optional[MaterialType] = None
    workbench: Optional[WorkbenchParam] = None

    @property
    def is_special(self) -> bool:
        # 作業台のエリアは、加工後の資材（Plank/Brick/Hammer）を material_type に持つ
        # （U1）ため、workbench の有無を別途判定しなくても material_type is not
        # None で特殊エリアとして扱われる（サイクル024-3。冗長な判定を避ける）
        return self.spawner_power != 0 or self.material_type is not None

    def to_save_data(self) -> dict:
        return {
            "fee_num": self.fee_num,
            "enemy_power": self.enemy_power,
            "spawner_power": self.spawner_power,
            "material_num": self.material_num,
            "material_type": enum_name(self.material_type),
            "fee_type": enum_name(self.fee_type),
            "workbench": self.workbench and self.workbench.to_save_data(),
        }

    @classmethod
    def from_save_data(cls, data: dict) -> "AreaParam":
        return cls(
            fee_num=data["fee_num"],
            enemy_power=data["enemy_power"],
            spawner_power=data["spawner_power"],
            material_num=data["material_num"],
            material_type=enum_from_name(MaterialType, data["material_type"]),
            fee_type=enum_from_name(MaterialType, data["fee_type"]),
            workbench=data["workbench"]
            and WorkbenchParam.from_save_data(data["workbench"]),
        )


class IMapGenerator(ABC):
    _instance = None

    @abstractmethod
    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_boss_power(self) -> int:
        pass

    @abstractmethod
    def get_step_power_gain(self, block_lv: int, order: int, count: int) -> int:
        """ナビゲーションのブロック block_lv（0 始まり）の order 番目（0 始まり）の
        指示をクリアしたときの武器の強さの上昇量。count はそのブロックの指示の個数"""

    @abstractmethod
    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_material_num(self, area_axis_x, area_axis_y) -> int:
        pass

    @abstractmethod
    def get_material_type(self, area_axis_x, area_axis_y) -> Optional[MaterialType]:
        pass

    @abstractmethod
    def get_fee_type(self, area_axis_x, area_axis_y) -> Optional[MaterialType]:
        pass

    @abstractmethod
    def get_workbench(self, area_axis_x, area_axis_y) -> Optional[WorkbenchParam]:
        pass

    @abstractmethod
    def to_save_data(self) -> dict:
        """生成結果を JSON にできる保存データへ変換する"""

    @abstractmethod
    def get_start_materials(self) -> list[tuple[MaterialType, int]]:
        pass

    @abstractmethod
    def get_start_pos(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def get_boss_pos(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def find_nearest_area(
        self, block_lv: int, kind: AreaKind, base_pos: tuple[int, int]
    ) -> tuple[int, int]:
        """レベル block_lv のブロックの、種別 kind に該当するエリアのうち
        base_pos に最も近いもの（マンハッタン距離。同距離は座標の順）を返す。
        NEXT_BLOCK は、次のブロック（block_lv + 1）のうち block_lv のブロックと
        辺で接するエリアを対象とする"""

    @abstractmethod
    def is_area_kind(self, block_lv: int, kind: AreaKind, pos: tuple[int, int]) -> bool:
        """pos が、レベル block_lv のブロックの種別 kind のエリアか。NEXT_BLOCK は
        次のブロック（block_lv + 1）のいずれかのエリア"""

    @abstractmethod
    def get_block_lv(self, area_axis_x, area_axis_y) -> Optional[int]:
        """エリア座標が属するブロックのレベル。経路に無いブロックは None"""

    @classmethod
    def create(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def recreate(cls):
        """シングルトンを作り直す。以後の create() は新しい生成結果（マップ）を返す"""
        cls._instance = cls()
        return cls._instance


class AreaBlockAlgorithmGenerator(IMapGenerator):
    BLOCK_SIZE = 6
    BLOCK_PATH_LEN = 4
    # ブロック（distance）ごとの Tree/Rock の配置数。requirements.md 開発フェーズ3
    # 「資源の種類と配置」のブロック1〜5に対応する（添字が distance）。ブロック5 は、
    # 武器の配置の廃止で空いた配置枠を使い、4 つずつ（スポナーとあわせて 9 エリア）に
    # する（requirements.md 開発フェーズ4「ブロック5 の資源配置数と採取量の変更」）
    TREE_NUM = (2, 3, 3, 3, 4)
    ROCK_NUM = (2, 3, 3, 3, 4)
    # ブロック（distance）ごとの採取量（資材1個あたりの個数）。requirements.md
    # 開発フェーズ3「資源の採取量」のブロック1〜5に対応する（添字が distance）
    MATERIAL_NUM = (6, 8, 13, 28, 40)
    # ブロック（distance）ごとの作業台の内容（Plank: distance 1・Brick: distance 2・
    # Hammer: distance 3）。
    # requirements.md 開発フェーズ3「作業台と資材加工」に対応する（添字が distance。U2）。
    # 加工後の資材の種類・個数は WorkbenchParam に持たせず（二重持ちを避ける）、
    # WORKBENCH_OUTPUT_TYPES とエリアの material_type/material_num（U1）で表す
    WORKBENCH_PARAMS: tuple = (
        None,
        WorkbenchParam((MaterialType.WOOD,), 10, 60),
        WorkbenchParam((MaterialType.STONE,), 10, 60),
        WorkbenchParam((MaterialType.PLANK, MaterialType.BRICK), 5, 90),
        None,
    )
    # 作業台（WORKBENCH_PARAMS）と同じ添字（distance）で、加工後の資材の種類を表す。
    # 個数は常に1（U1）
    WORKBENCH_OUTPUT_TYPES: tuple = (
        None,
        MaterialType.PLANK,
        MaterialType.BRICK,
        MaterialType.HAMMER,
        None,
    )
    # ブロック（distance）ごとの、未開放エリアの開放に必要な資材の種類。
    # requirements.md 開発フェーズ3「エリア開放条件」のブロック1〜5に対応する
    # （添字が distance。U2）
    FEE_TYPES = (
        MaterialType.WOOD,
        MaterialType.STONE,
        MaterialType.PLANK,
        MaterialType.BRICK,
        MaterialType.HAMMER,
    )
    # ブロック（distance）ごとの、未開放エリア1つあたりの開放に必要な資材の個数。
    # FEE_TYPES と同じ添字（distance）で、requirements.md 開発フェーズ3
    # 「エリア開放条件」のブロック1〜5に対応する（U2）
    FEE_NUMS = (2, 4, 1, 2, 1)
    # ゲーム開始時の木材の所持数。requirements.md 開発フェーズ3
    # 「開始時の資材と序盤の開放」の値（Wood ×1）。取得の仕組み（U13）は
    # get_start_materials として残す
    START_MATERIAL_WOOD_NUM = 1

    def __init__(self):
        self.area_data_map = {}
        self.start_pos = None
        self.boss_pos = None
        self.area_block_lv_map = self._get_area_block_route(self.BLOCK_PATH_LEN)

    def to_save_data(self) -> dict:
        """生成結果を JSON にできる保存データへ変換する。保存時点で未生成のブロックは
        含めない（復元後に初めて問い合わせたときに生成する。U1）"""
        return {
            "area_block_lv_map": [
                [*pos, lv] for pos, lv in self.area_block_lv_map.items()
            ],
            "area_data_map": [
                [*pos, [[param.to_save_data() for param in row] for row in grid]]
                for pos, grid in self.area_data_map.items()
            ],
            "start_pos": self.start_pos and list(self.start_pos),
            "boss_pos": self.boss_pos and list(self.boss_pos),
        }

    @classmethod
    def restore(cls, data: dict):
        """保存データから生成結果を復元し、シングルトンを差し替える"""
        generator = cls()
        generator.area_block_lv_map = {
            (x, y): lv for x, y, lv in data["area_block_lv_map"]
        }
        generator.area_data_map = {
            (x, y): [[AreaParam.from_save_data(p) for p in row] for row in grid]
            for x, y, grid in data["area_data_map"]
        }
        generator.start_pos = data["start_pos"] and tuple(data["start_pos"])
        generator.boss_pos = data["boss_pos"] and tuple(data["boss_pos"])
        cls._instance = generator
        return generator

    def _shuffle(self, lst: list[AreaParam]) -> list[list[AreaParam]]:
        specials = [p for p in lst if p.is_special]
        non_specials = [p for p in lst if not p.is_special]
        random.shuffle(specials)
        random.shuffle(non_specials)

        grid = [[None] * self.BLOCK_SIZE for _ in range(self.BLOCK_SIZE)]
        blocked = set()
        for p in specials:
            candidates = [
                (x, y)
                for x in range(self.BLOCK_SIZE)
                for y in range(self.BLOCK_SIZE)
                if grid[x][y] is None and (x, y) not in blocked
            ]
            x, y = random.choice(candidates)
            grid[x][y] = p
            blocked.add((x, y))
            blocked.update({(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)})

        non_special_iter = iter(non_specials)
        for x in range(self.BLOCK_SIZE):
            for y in range(self.BLOCK_SIZE):
                if grid[x][y] is None:
                    grid[x][y] = next(non_special_iter)
        return grid

    def _get_area_num_list(self, distance) -> list[AreaParam]:
        sep_num = 2 ** (distance + 1) * 2
        start_num = 2 ** (distance + 1) - 1
        # 敵・スポナーの強さのみに使う（開放条件は FEE_TYPES・FEE_NUMS で決まる）
        are_level_map = {i: i // 2 + start_num for i in range(sep_num)}
        # 各ブロックに1か所スポナーを配置
        spawner_pos = 2
        # ブロックごとの Tree・Rock・作業台の配置数だけ、スポナーと重ならない
        # エリアを割り当てる。Tree・Rock・作業台は同じ free_pos_iter から重複なく
        # 引くため、tree_pos_set・rock_pos_set・workbench_pos は互いにも重ならない
        excluded_pos_set = {spawner_pos}
        free_pos_iter = (
            i for i in range(self.BLOCK_SIZE**2) if i not in excluded_pos_set
        )
        tree_pos_set = {next(free_pos_iter) for _ in range(self.TREE_NUM[distance])}
        rock_pos_set = {next(free_pos_iter) for _ in range(self.ROCK_NUM[distance])}
        workbench_param = self.WORKBENCH_PARAMS[distance]
        workbench_pos = next(free_pos_iter) if workbench_param is not None else None

        # エリアの資材。資源は Tree が Wood・Rock が Stone で採取量はブロックごとの値。
        # スポナーのエリアは、そのブロックの開放に必要な資材を1個（敵が倒されたときの
        # ドロップ。ID-027 U1・U2）、作業台のエリアは加工後の資材を1個（ID-024 U1）とする
        def get_material_type(i) -> Optional[MaterialType]:
            if i in tree_pos_set:
                return MaterialType.WOOD
            if i in rock_pos_set:
                return MaterialType.STONE
            if i == spawner_pos:
                return self.FEE_TYPES[distance]
            if i == workbench_pos:
                return self.WORKBENCH_OUTPUT_TYPES[distance]
            return None

        def get_material_num(i) -> int:
            if i in tree_pos_set or i in rock_pos_set:
                return self.MATERIAL_NUM[distance]
            if i in (spawner_pos, workbench_pos):
                return 1
            return 0

        return [
            AreaParam(
                fee_num=self.FEE_NUMS[distance],
                enemy_power=are_level_map[i % sep_num] if i % 2 == 0 else 0,
                spawner_power=are_level_map[i % sep_num] if i == spawner_pos else 0,
                material_num=get_material_num(i),
                material_type=get_material_type(i),
                fee_type=self.FEE_TYPES[distance],
                workbench=workbench_param if i == workbench_pos else None,
            )
            for i in range(self.BLOCK_SIZE**2)
        ]

    def _get_area_data(self, area_axis_x, area_axis_y):
        block_axis_pos = tuple(i // self.BLOCK_SIZE for i in (area_axis_x, area_axis_y))
        if block_axis_pos not in self.area_data_map:
            if block_axis_pos in self.area_block_lv_map:
                lv = self.area_block_lv_map[block_axis_pos]
                self.area_data_map[block_axis_pos] = self._shuffle(
                    self._get_area_num_list(lv)
                )
                if lv == 0:
                    self._decide_start_pos(block_axis_pos)
            else:
                self.area_data_map[block_axis_pos] = [
                    [AreaParam() for _ in range(self.BLOCK_SIZE)]
                    for _ in range(self.BLOCK_SIZE)
                ]
        return self.area_data_map[block_axis_pos][(area_axis_x) % self.BLOCK_SIZE][
            (area_axis_y) % self.BLOCK_SIZE
        ]

    def get_fee_num(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y).fee_num

    def get_enemy_power(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y).enemy_power

    def get_boss_power(self) -> int:
        return 2 ** (self.BLOCK_PATH_LEN + 1 + 1) - 1

    def _get_block_pos_set(self, block_axis_pos) -> set[tuple[int, int]]:
        block_edge_pos = tuple(p * self.BLOCK_SIZE for p in block_axis_pos)
        return {
            (x, y)
            for x in range(block_edge_pos[0], block_edge_pos[0] + self.BLOCK_SIZE)
            for y in range(block_edge_pos[1], block_edge_pos[1] + self.BLOCK_SIZE)
        }

    def _get_block_random_pos(self, block_axis_pos):
        enable_list = [
            pos
            for pos in self._get_block_pos_set(block_axis_pos)
            if not self._get_area_data(*pos).is_special
        ]
        return random.choice(enable_list)

    def get_boss_pos(self) -> tuple[int, int]:
        """ボスエリアを返す。スタート位置と同じく生成結果の一部で、
        初回の問い合わせ時に決まり、何度呼んでも同じ位置を返す。"""
        if self.boss_pos is None:
            boss_block_pos = [
                k for k, v in self.area_block_lv_map.items() if v == self.BLOCK_PATH_LEN
            ][0]
            self.boss_pos = self._get_block_random_pos(boss_block_pos)
        return self.boss_pos

    @staticmethod
    def _cumulative_power_gain(block_lv: int) -> int:
        return 2 ** (block_lv + 1 + 2)

    def get_step_power_gain(self, block_lv: int, order: int, count: int) -> int:
        # ブロック k（= block_lv + 1）の指示を終えた時点の累計を 2 ** (k + 2) とし、
        # ブロックの上昇量はその累計の差。ブロック内の指示の個数で割って配る
        # （割り切れない分は最後の指示に加える）
        block_total = self._cumulative_power_gain(block_lv) - (
            self._cumulative_power_gain(block_lv - 1) if block_lv > 0 else 0
        )
        gain = block_total // count
        if order == count - 1:
            gain += block_total % count
        return gain

    def get_spawner_power(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y).spawner_power

    def get_material_num(self, area_axis_x, area_axis_y) -> int:
        return self._get_area_data(area_axis_x, area_axis_y).material_num

    def get_material_type(self, area_axis_x, area_axis_y) -> Optional[MaterialType]:
        return self._get_area_data(area_axis_x, area_axis_y).material_type

    def get_fee_type(self, area_axis_x, area_axis_y) -> Optional[MaterialType]:
        return self._get_area_data(area_axis_x, area_axis_y).fee_type

    def get_workbench(self, area_axis_x, area_axis_y) -> Optional[WorkbenchParam]:
        return self._get_area_data(area_axis_x, area_axis_y).workbench

    def get_start_materials(self) -> list[tuple[MaterialType, int]]:
        return [(MaterialType.WOOD, self.START_MATERIAL_WOOD_NUM)]

    def _is_tree(self, area_axis_x, area_axis_y) -> bool:
        area_data = self._get_area_data(area_axis_x, area_axis_y)
        return (
            area_data.spawner_power == 0
            and area_data.material_type == MaterialType.WOOD
        )

    def _get_block_tree_adjacent_pos(self, block_axis_pos):
        block_pos_set = self._get_block_pos_set(block_axis_pos)
        tree_pos = next((pos for pos in block_pos_set if self._is_tree(*pos)), None)
        if tree_pos is None:
            return None
        candidate_list = [
            (x, y)
            for x, y in self._get_adjacent_pos_list(*tree_pos)
            if (x, y) in block_pos_set and not self._get_area_data(x, y).is_special
        ]
        return random.choice(candidate_list) if candidate_list else None

    @staticmethod
    def _get_adjacent_pos_list(area_axis_x, area_axis_y):
        return [
            (area_axis_x + dx, area_axis_y + dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        ]

    def _decide_start_pos(self, block_axis_pos):
        """スタートエリアを決め、隣接する Tree のエリアの必要量を 1 にする。

        ブロックのエリアデータを保存した直後に呼ぶ。Tree の無い配列（テストで
        `_shuffle` を差し替えた場合）ではスタートは決まらず、`start_pos` は `None` のまま。
        """
        start_pos = self._get_block_tree_adjacent_pos(block_axis_pos)
        if start_pos is None:
            return
        self.start_pos = start_pos
        for pos in self._get_adjacent_pos_list(*start_pos):
            if self._is_tree(*pos):
                area_data = self._get_area_data(*pos)
                block_axis = tuple(i // self.BLOCK_SIZE for i in pos)
                self.area_data_map[block_axis][pos[0] % self.BLOCK_SIZE][
                    pos[1] % self.BLOCK_SIZE
                ] = area_data._replace(fee_num=1)

    def get_start_pos(self) -> tuple[int, int]:
        """スタートエリアを返す。ブロック(0,0) のエリアデータの生成時に決まり、
        何度呼んでも同じ位置を返す。"""
        self._get_area_data(0, 0)
        return self.start_pos

    def get_block_lv(self, area_axis_x, area_axis_y) -> Optional[int]:
        return self.area_block_lv_map.get(
            (area_axis_x // self.BLOCK_SIZE, area_axis_y // self.BLOCK_SIZE)
        )

    def is_area_kind(self, block_lv: int, kind: AreaKind, pos: tuple[int, int]) -> bool:
        if kind == AreaKind.NEXT_BLOCK:
            return self.get_block_lv(*pos) == block_lv + 1
        return self.get_block_lv(*pos) == block_lv and self._is_kind(kind, *pos)

    def _get_block_area_list(self, block_lv: int) -> list[tuple[int, int]]:
        return [
            pos
            for block_axis_pos, lv in self.area_block_lv_map.items()
            if lv == block_lv
            for pos in sorted(self._get_block_pos_set(block_axis_pos))
        ]

    def _is_kind(self, kind: AreaKind, area_axis_x, area_axis_y) -> bool:
        if kind == AreaKind.TREE:
            return self._is_tree(area_axis_x, area_axis_y)
        if kind == AreaKind.ROCK:
            area_data = self._get_area_data(area_axis_x, area_axis_y)
            return (
                area_data.spawner_power == 0
                and area_data.material_type == MaterialType.STONE
            )
        return self.get_workbench(area_axis_x, area_axis_y) is not None

    def find_nearest_area(
        self, block_lv: int, kind: AreaKind, base_pos: tuple[int, int]
    ) -> tuple[int, int]:
        # 該当するエリア（is_area_kind）のうち、NEXT_BLOCK は現在のブロックと辺で接するもの
        # だけを目標の候補とする
        current_set = set(self._get_block_area_list(block_lv))
        search_lv = block_lv + 1 if kind == AreaKind.NEXT_BLOCK else block_lv
        candidate_list = [
            pos
            for pos in self._get_block_area_list(search_lv)
            if self.is_area_kind(block_lv, kind, pos)
            and (
                kind != AreaKind.NEXT_BLOCK
                or any(adj in current_set for adj in self._get_adjacent_pos_list(*pos))
            )
        ]
        return min(
            candidate_list,
            key=lambda pos: (
                abs(pos[0] - base_pos[0]) + abs(pos[1] - base_pos[1]),
                pos,
            ),
        )

    @classmethod
    def _get_area_block_route(cls, goal_steps: int) -> dict[tuple[int, int], int]:
        goal_pos_list = [
            (x, y)
            for x in range(-goal_steps, goal_steps + 1)
            for y in range(-goal_steps, goal_steps + 1)
            if abs(x) + abs(y) == goal_steps
        ]
        goal_pos = random.choice(goal_pos_list)
        goal_direct_path = [(1 if goal_pos[0] > 0 else -1, 0)] * abs(goal_pos[0]) + [
            (0, 1 if goal_pos[1] > 0 else -1)
        ] * abs(goal_pos[1])
        random.shuffle(goal_direct_path)
        route = {(0, 0): 0}
        current_pos = (0, 0)
        for i, d in enumerate(goal_direct_path):
            current_pos = tuple(c + d for c, d in zip(current_pos, d))
            route[current_pos] = i + 1
        return route
