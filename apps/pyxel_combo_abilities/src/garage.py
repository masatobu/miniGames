"""部品の枠とストックを持つ Garage。"""

try:
    from .resource import Component, Resource  # pylint: disable=C0413
except ImportError:
    from resource import Component, Resource  # pylint: disable=C0413


class Garage:
    """部品（Component）ごとの枠と、各部品のレベルを持つ。

    lv は、チューニング対象の部品（Component.tuned()）ごとのレベル。
    boxes は、全部品（STOCK を含む）の枠のリスト。空の枠は None。
    """

    def __init__(self):
        self.lv = {i: 1 for i in Component.tuned()}
        self.boxes = {i: [None for _ in i.value] for i in Component}

    def set_stock(self, lst):
        """ストックを lst で置き換える。枠より長いときは何も変えずに IndexError。"""
        if len(self.boxes[Component.STOCK]) < len(lst):
            raise IndexError(f"Error: unexpected list length ({lst})")
        self.boxes[Component.STOCK] = [None for _ in Component.STOCK.value]
        for i, resource in enumerate(lst):
            self.boxes[Component.STOCK][i] = resource

    def reset_lv(self):
        """部品ごとに、枠のランク値の最小 + 1 をレベルにする（空の枠は 0 + 1）。"""
        for comp in Component.tuned():
            res_lvs = [Resource.get_rank(i) + 1 for i in self.boxes[comp]]
            self.lv[comp] = min(res_lvs)

    def get_lv(self, component):
        """部品のレベル。"""
        return self.lv[component]

    def get_box_resources(self, target):
        """部品の枠の内容のリスト。"""
        return self.boxes[target]

    def change(self, source, target):
        """source と target（それぞれ (Component, 枠の番号)）の中身を入れ替える。"""
        src_comp, src_idx = source
        tgt_comp, tgt_idx = target
        src_res = self.boxes[src_comp][src_idx]
        tgt_res = self.boxes[tgt_comp][tgt_idx]
        if not (
            Resource.check_mask(tgt_comp.value[tgt_idx], src_res)
            and Resource.check_mask(src_comp.value[src_idx], tgt_res)
        ):
            return False
        self.boxes[src_comp][src_idx] = tgt_res
        self.boxes[tgt_comp][tgt_idx] = src_res
        self.reset_lv()
        return True
