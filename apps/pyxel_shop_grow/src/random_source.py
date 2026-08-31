from abc import ABC, abstractmethod


class IRandomSource(ABC):
    """ゲーム内の非決定性（抽選）の唯一の出どころ。IView（描画）・IInput（入力）と
    同じく、pyxel の実装をゲームロジックから切り離すための境界であり、テストは
    create() を差し替えて決定的な実装にする。目的は乱数そのものを検証することでは
    なく、非決定性をゲームロジックの外から注入して UT を決定論的に保つこと。
    公開するのは random() / randrange(n) のような汎用の乱数ではなく、
    **その抽選が何を選ぶのかが名前で分かるメソッド**だけにする。汎用メソッドを
    公開すると、テストが「1回目の乱数→…」という呼び出し順で結果を仕込む形に
    なり、内部で引く回数や順序が変わるたびに、仕様が変わったのか順序が変わった
    のか区別できないまま壊れる（ID-015/ID-016 は決算1回で複数回引くため、この
    問題が実際に噛む）。
    抽選が増えても（売上 ID-010 が2件目・売却 ID-016）**分割せず本インタフェースへ
    メソッドを足す**。分割はシーンごとではなく、変更理由・責務が実際に
    分かれてきたときに検討する。
    メソッド単位で分けておく効果は、2件目（売上 ID-010）で実際に現れた。
    売上発生間隔（3秒）と他店建設間隔（10秒）は同じ update() で両方満了し得るが、
    抽選のメソッドが分かれているため、テストも実装も**どちらの抽選なのかを
    呼び出し順で数える必要がない**。
    IView / IInput と違い main.py ではなく専用のモジュールへ置くのは、抽選を
    行うのが Field（field.py）であり、main.py に置くと main → field の依存と
    逆向きの参照が生まれるため。本モジュール自体は pyxel を（PyxelRandomSource の
    生成時まで）import しないため、field.py が pyxel 非依存であることは変わらない
    （report_store.py と同じ、main.py・field.py のどちらからも独立した部品）"""

    @abstractmethod
    def pick_npc_growth_target(self, targets):
        """他店建設間隔（ID-008）の抽選：NPC所有店舗＋店舗に隣接する空き区画から
        1つを等確率で選び、**選ばれた対象そのもの**（(col, row)）を返す。
        index を返す形にすると、呼び出し側とテストの双方が列挙順を知る必要が
        生じ、順序を変えただけで壊れる。targets は空でないことを呼び出し側が
        保証する（「対象が無いときに何を返すか」を実装ごとに決めさせない）"""

    @abstractmethod
    def pick_sales_shop(self, targets):
        """売上発生間隔（ID-010）の抽選：**受け取った並びから1つを等確率で選び**、
        **選ばれた対象そのもの**（(col, row)）を返す。targets の扱いは
        pick_npc_growth_target() と同じ（index ではなく対象そのものを返す・
        空でないことは呼び出し側が保証する）。
        隣接による選ばれやすさの違い（ID-012）は**本メソッドの関知するところでは
        ない**。呼び手（Field.list_sales_lottery_entries()）が同じ区画を重み分だけ
        重複させた並びを渡すため、等確率で1つ引くだけで重み付き抽選として成立する。
        重みを別の引数で受け取る形にしなかったのは、抽選ロジック（累積和と探索）が
        実装ごとに必要になり、テスト用の実装にも同じロジックを書くことになるため。
        境界は薄いほうがよく、**乱数源は重みを知らない**"""

    @abstractmethod
    def pick_sell_shop(self, targets):
        """税金不足時の売却（ID-016）の抽選：**受け取った並びから1つを等確率で
        選び**、**選ばれた対象そのもの**（(col, row)）を返す。targets の扱いは
        他の2件（pick_npc_growth_target / pick_sales_shop）と同じ（index では
        なく対象そのものを返す・空でないことは呼び出し側が保証する）"""

    @classmethod
    def create(cls):
        return cls()


class PyxelRandomSource(IRandomSource):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def pick_npc_growth_target(self, targets):
        # 一様な等確率の抽選。標準 random ではなく pyxel.rndi を使うのは処理速度の
        # ため（rndi は下限・上限とも含む閉区間を取る）
        return targets[self.pyxel.rndi(0, len(targets) - 1)]

    def pick_sales_shop(self, targets):
        # pick_npc_growth_target() と同じ一様な等確率の抽選のままで、重み付き抽選
        # （ID-012）として働く。並びに同じ区画が重み分だけ重複して入っているため、
        # 一様に引けば選ばれる確率がその重みに比例する。重みを表すのは呼び手の
        # 責務であり、実装をここで分ける必要はない
        return targets[self.pyxel.rndi(0, len(targets) - 1)]

    def pick_sell_shop(self, targets):
        # 他の2件と同じ一様な等確率の抽選
        return targets[self.pyxel.rndi(0, len(targets) - 1)]
