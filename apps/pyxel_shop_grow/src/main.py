# title: pyxel_shop_grow
# author: masatobu

import math
import time
from abc import ABC, abstractmethod
from enum import Enum
from field import Field, Owner, Shop  # pylint: disable=E0401
from report_store import ReportStore  # pylint: disable=E0401


class Clock:
    def __init__(self, count_ms, remaining_ms=None):
        self._count_ms = count_ms
        # 一時停止中の残り時間（ID-015）。None は「一時停止していない」を表す。
        # 停止中は is_up() / remaining_ms() のいずれも time.perf_counter() を
        # 読まない（呼ばないだけでは時間が止まらないため、ここで実際に
        # 判定・計算の入力そのものを止める）
        self._paused_remaining_ms = None
        # 基準時刻（_rebase() が組み直す）。__init__ で属性として宣言してから
        # _rebase() へ実際の値を委ねる
        self._bef = None
        # remaining_ms を指定しない既定の生成は、満了までの残りが count_ms その
        # ものになる（従来どおり、生成した瞬間から数え始める）。指定したときは、
        # 残りがちょうど remaining_ms になるよう基準時刻をその分だけ過去へ
        # ずらす。保存データから復元した残り時間の「続きから」経過させるための
        # 仕様（ShopClock.start()）。resume() / change_count_ms() と
        # 同じ _rebase() を使う
        self._rebase(
            time.perf_counter(), count_ms if remaining_ms is None else remaining_ms
        )

    def is_up(self) -> bool:
        if self._count_ms == 0:
            return False
        if self._paused_remaining_ms is not None:
            return False
        now = time.perf_counter()
        if (now - self._bef) * 1000 >= self._count_ms:
            self._bef = now
            return True
        return False

    def remaining_ms(self):
        """満了（is_up() が真になる）までの残り時間を ms で返す。経過が
        count_ms を超えていても負にはならず 0 で頭打ちにする。count_ms が
        0（is_up() が常に False の無効化）のときは常に 0 を返す。一時停止中は
        停止した瞬間の値のまま変わらない。保存データへ残り時間を書き出す
        ために使う（GameCore._get_save_data()）"""
        if self._count_ms == 0:
            return 0
        if self._paused_remaining_ms is not None:
            return self._paused_remaining_ms
        elapsed_ms = (time.perf_counter() - self._bef) * 1000
        return max(0, self._count_ms - elapsed_ms)

    def remaining_ratio(self):
        """満了までの残り時間を、count_ms に対する割合（0.0〜1.0）で
        返す（ID-027 TDD サイクル 027-1。決算までの残り時間をプログレス
        バーで表示する要件のために新設）。remaining_ms() と同じ秒粒度
        （math.ceil）へ量子化してから割る（決定3-A）——生の ms のまま
        割ると、time.perf_counter() をモックしていないテストファイルが
        実時間に依存して不安定になることが実測で分かっている
        （ID-027_subtasks.md「既存テストへの影響」）。count_ms が 0
        （無効化中）のときは 0.0 を返す（0除算を避ける。remaining_ms() が
        常に0になる無効化中の割合として自然な値）。分母には常に
        self._count_ms（この Clock 自身が現在使っている間隔）を使うため、
        ゲームスピード変更で間隔が変わっても変更前後で割合は変わらない
        （change_count_ms() が残り時間を新旧の比率でスケールするため）"""
        if self._count_ms == 0:
            return 0.0
        remaining_sec = math.ceil(self.remaining_ms() / 1000)
        interval_sec = math.ceil(self._count_ms / 1000)
        return remaining_sec / interval_sec

    def pause(self):
        """一時停止する（ID-015。決算ポップアップ表示中の完全凍結
        GameCore._freeze_clocks が呼ぶ）。停止した瞬間の残り時間を控え、
        以後 is_up() / remaining_ms() はその値を返し続ける（time.perf_
        counter() を読まなくなるため、実時間がどれだけ進んでも変わらない）。
        既に一時停止中なら何もしない（2回目以降の呼び出しで残り時間が
        呼んだ時点の値へ巻き戻らない）。

        一時停止・再開の仕組みを（ShopClock ではなく）Clock 側に
        置いたのは、GameCore._save_clock が素の Clock であり
        ShopClock ではないため。4つの凍結対象（保存・他店建設・
        売上・決算）すべてを止めるには、両者が共通して持つ Clock 側に
        置くのが自然（ShopClock.pause() / resume() は本メソッドへの
        中継のみを持つ）"""
        if self._paused_remaining_ms is not None:
            return
        self._paused_remaining_ms = self.remaining_ms()

    def resume(self):
        """一時停止から再開する（ID-015）。一時停止していなければ何もしない。
        停止した時点の残り時間の続きから経過するよう、基準時刻を組み直す
        （__init__ / change_count_ms() と共有する _rebase()。保存データから
        の復元・一時停止からの再開・間隔変更が、同じ1つの式で表せる）"""
        if self._paused_remaining_ms is None:
            return
        remaining_ms = self._paused_remaining_ms
        self._paused_remaining_ms = None
        self._rebase(time.perf_counter(), remaining_ms)

    def change_count_ms(self, new_count_ms):
        """間隔を new_count_ms へ変更する（ID-019 ゲームスピード）。次の
        満了までの待機時間が新しい間隔になり、残り時間も新旧の間隔の比率で
        スケールする（新旧比率 new/old を残り時間へ掛ける）。一時停止中なら
        time.perf_counter() を読まず一時停止中の残り時間だけをスケールし
        （_bef は再開時に組み直されるため触らない）、稼働中は現在の残り時間を
        求めたうえで __init__ / resume() と共有する _rebase() で基準時刻を
        組み直す"""
        old_count_ms = self._count_ms
        if self._paused_remaining_ms is not None:
            self._count_ms = new_count_ms
            self._paused_remaining_ms = self.scale_remaining_ms(
                self._paused_remaining_ms, old_count_ms, new_count_ms
            )
            return
        now = time.perf_counter()
        if old_count_ms == 0:
            old_remaining_ms = 0
        else:
            elapsed_ms = (now - self._bef) * 1000
            old_remaining_ms = max(0, old_count_ms - elapsed_ms)
        self._count_ms = new_count_ms
        new_remaining_ms = self.scale_remaining_ms(
            old_remaining_ms, old_count_ms, new_count_ms
        )
        self._rebase(now, new_remaining_ms)

    def _rebase(self, now, remaining_ms):
        """time.perf_counter() の現在値 now を基準に、残りがちょうど
        remaining_ms になるよう基準時刻 _bef を組み直す（過去へその分
        ずらす）。__init__（remaining_ms 指定時）・resume()・
        change_count_ms() の3箇所が共有する1つの式"""
        elapsed_ms = self._count_ms - remaining_ms
        self._bef = now - elapsed_ms / 1000

    @staticmethod
    def scale_remaining_ms(remaining_ms, old_count_ms, new_count_ms):
        """残り時間を新旧の間隔の比率でスケールする。old_count_ms が 0
        （無効化中）のときは比率そのものを持たないため、新しい間隔から
        数え直す（新しい間隔そのものを残り時間とする）。Clock 自身の
        change_count_ms() だけでなく、ShopClock.change_count_ms()
        が未開始時に控えている保存値をスケールする際にも同じ式を使う
        （前置アンダースコアを外し、クラスをまたいで共有できる形にした）"""
        if old_count_ms == 0:
            return new_count_ms
        return remaining_ms * new_count_ms / old_count_ms


class ShopClock:
    """**マップ上に店舗が1軒も無い間は経過を開始しない**タイマー
    （要件 3.2）。他店建設間隔（ID-008）に続き売上発生間隔（ID-010）が2件目と
    なった時点で、両者に共通していた「開始まわりの3つの知識」——開始は一度だけ
    であること・「まだ経過を開始していない」の表し方・保存された残り時間の
    続きから始めること——を Clock の外側に1つだけ持たせた。決算間隔（ID-014）が
    3件目として同じ形で乗った（GameCore._settlement_clock）。

    開始条件そのもの（マップ上に店舗が1軒でもあるか。所有者は問わない。
    ID-025）は盤面を知る GameCore._start_shop_clocks() が持ち、本クラスは
    持たない（本クラスは Field を知らない）。

    「まだ経過を開始していない」は、開始したかを表す真偽値を別に持つのでは
    なく、**内側の Clock が未生成（None）であること**そのもので表す。状態を
    2つ（開始フラグと残り時間）持つと、「未開始なのに残り時間がある」
    「開始済みなのに残り時間がない」という食い違った組み合わせが実装上
    作れてしまうため（PopupState を 1 つの Enum へ一本化したのと同じ考え方）。
    また「経過しない」を**タイマーそのものを持たない**ことで表すため、未開始の
    間は時刻を読むことすらしない（満了しても何もしない、という形にはしていない）。

    一度開始したら、プレイヤー所有店舗が0軒に戻っても未開始へは戻さない。
    **ID-016（税金が払えないときの店舗売却）はプレイヤー所有店舗が0軒に
    なり得る唯一の経路**であり、そこで街の成長や売上が止まるのは要件にない
    振る舞いになる（要件 3.9 は売却で税を払えた場合ゲームを続ける）。
    プレイヤー所有店舗の有無から毎フレーム導出する形にするとこの問題が必ず
    起きるため、導出ではなく「一度開始したら開始したまま」とする"""

    def __init__(self, count_ms):
        self._count_ms = count_ms
        self._clock = None
        self._saved_remaining_ms = None

    def start(self):
        """まだ開始していなければ経過を開始する。開始条件（プレイヤー所有店舗が
        あるか）は呼び出し側が判断済みで、ここが持つのは「開始は一度だけ」だけ。
        保存データに残り時間があればその続きから、なければ（未開始のまま
        保存された・保存データ自体が無い）間隔そのものから始める"""
        if self._clock is not None:
            return
        self._clock = Clock(self._count_ms, remaining_ms=self._saved_remaining_ms)

    def is_up(self) -> bool:
        """満了したかを返す。未開始の間は時刻を読まずに False を返すため、
        呼び出し側は未開始かどうかを判定しなくてよい"""
        return self._clock is not None and self._clock.is_up()

    def remaining_ms(self):
        """満了までの残り時間を返す。未開始のときは None を返し、保存データ上も
        「未開始」がそのまま None で表される（GameCore._get_save_data()）"""
        return None if self._clock is None else self._clock.remaining_ms()

    def remaining_ratio(self):
        """満了までの残り時間の割合（0.0〜1.0）を返す（ID-027 TDD サイクル
        027-1。決定1-A）。未開始のときは remaining_ms() と同じく None を
        返す——「未開始」を満杯として読み替えるかどうかは呼び手ごとに
        意味が異なり得るため、ここでは読み替えず表示側へ委ねる
        （_draw_status() が remaining_ms() の None を SETTLEMENT_
        INTERVAL_MS へ読み替えるのと同じ ID-025 の方針。決定4）。
        開始済みなら内側の Clock（現在有効な間隔を持つ）へそのまま
        委譲するため、開始済みの ShopClock 自身の self._count_ms
        （change_count_ms() で更新されない古い値。決定2 参照）を
        分母として使うことはない——ゲームスピード変更の前後で割合が
        変わらないのはこのため"""
        return None if self._clock is None else self._clock.remaining_ratio()

    def apply_saved_remaining_ms(self, remaining_ms):
        """保存データの残り時間を、start() したときの続きの起点として控える
        （GameCore._apply_load_data()）。復元は開始より前に行われるため、
        start() の中で読めるようここへ預けておく"""
        self._saved_remaining_ms = remaining_ms

    def pause(self):
        """一時停止する（ID-015）。未開始（self._clock が None）のときは
        何もしない——「未開始」と「一時停止」は別物であり、一時停止が未開始へ
        戻す形にはしない（本クラスの「一度開始したら未開始へ戻さない」という
        性質を壊さない）。開始済みなら内側の Clock へそのまま中継する"""
        if self._clock is not None:
            self._clock.pause()

    def resume(self):
        """一時停止から再開する（ID-015）。未開始のときは何もしない。
        開始済みなら内側の Clock へそのまま中継する"""
        if self._clock is not None:
            self._clock.resume()

    def change_count_ms(self, new_count_ms):
        """間隔を new_count_ms へ変更する（ID-019 ゲームスピード）。開始済み
        なら内側の Clock へそのまま中継する。未開始のときは「内側の Clock が
        無い」ぶんだけを足す中継として、次の start() が新しい間隔から始まる
        よう _count_ms を差し替え、保存値（apply_saved_remaining_ms()）を
        控えている場合は Clock.scale_remaining_ms() と同じ式でスケールする
        （未開始のまま時刻を読まないという性質は変わらない）"""
        if self._clock is not None:
            self._clock.change_count_ms(new_count_ms)
            return
        if self._saved_remaining_ms is not None:
            self._saved_remaining_ms = Clock.scale_remaining_ms(
                self._saved_remaining_ms, self._count_ms, new_count_ms
            )
        self._count_ms = new_count_ms


class IView(ABC):
    @abstractmethod
    def draw_text(self, x, y, text):
        pass

    @abstractmethod
    def draw_image(self, x, y, img, u, v, w, h, colkey):
        pass

    @abstractmethod
    def draw_rect(self, x, y, w, h, col):
        pass

    @abstractmethod
    def draw_rectb(self, x, y, w, h, col):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelView(IView):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def draw_text(self, x, y, text):
        self.pyxel.text(x, y, text, 7)

    def draw_image(self, x, y, img, u, v, w, h, colkey):
        self.pyxel.blt(x, y, img, u, v, w, h, colkey)

    def draw_rect(self, x, y, w, h, col):
        self.pyxel.rect(x, y, w, h, col)

    def draw_rectb(self, x, y, w, h, col):
        self.pyxel.rectb(x, y, w, h, col)


class IInput(ABC):
    @abstractmethod
    def is_mouse_btn_down(self) -> bool:
        pass

    @abstractmethod
    def get_mouse_pos(self):
        pass

    @classmethod
    def create(cls):
        return cls()


class PyxelInput(IInput):
    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        self.pyxel = pyxel

    def is_mouse_btn_down(self) -> bool:
        return self.pyxel.btn(self.pyxel.MOUSE_BUTTON_LEFT)

    def get_mouse_pos(self):
        return self.pyxel.mouse_x, self.pyxel.mouse_y


class PopupState(Enum):
    """ポップアップの状態遷移（requirements.md / ID-005_subtasks.md の状態遷移図の
    NONE → TRACKING → MODAL → CLOSING に対応。ID-022 で「o」の実行後だけが
    経由する EXECUTED を MODAL と CLOSING の間へ追加した——MODAL → EXECUTED
    → MODAL、MODAL → CLOSING → NONE の2系統に分かれる）。
    フラグの組み合わせ（_popup_plot の有無 × 真偽値）で表現していると、
    「対象区画が無いのに表示状態」のようなあり得ない組み合わせが型の上では
    作れてしまう。1 つの Enum に一本化することで、状態は常に 5 つのいずれか
    だけになる"""

    NONE = "none"
    TRACKING = "tracking"
    MODAL = "modal"
    # 「o」ボタン押下で建設・増資・買収を実行したが、そのボタンからまだ
    # 指が離れていない実行済み状態（ID-022 決定1）。CLOSING と異なり
    # 非表示にはせず、ポップアップの表示を続けたまま（_is_selection_shown()
    # の除外リストに加えないことで、追加の実装なしに描かれ続ける）フィールド
    # 操作は無効のままにする（取りこぼし防止・決定2の1押下＝1実行を、
    # 押下保持のレベル判定だけで表す）。released で MODAL へ戻る
    EXECUTED = "executed"
    # 「o」「x」ボタン押下でポップアップは非表示になったが、そのボタンから
    # まだ指が離れていない終了待ち状態。フィールド操作は NONE へ戻るまで
    # 無効のまま（取りこぼし防止。押下保持のレベル判定だけで書けるように、
    # ボタン押下から NONE へ直接遷移させず本状態を経由させる）
    CLOSING = "closing"


class SettlementPopupState(Enum):
    """決算ポップアップの状態遷移（設計判断「決算ポップアップの状態は…
    区画選択の PopupState とは別に持つ」への、TASK-015-16 時点での回答）。

    サイクル5（クリックによる精算）の Red 時点では「押下で精算・非表示に
    し、指が離れるまでフィールド操作を受け付けない」ため、区画選択の
    CLOSING と同じ形の3状態（NONE / SHOWN / CLOSING）を持っていた。
    ID-018 のプレイテストで、決算の「o」を離さないまま終了ポップアップの
    「o」の位置へ指が乗り続けると、その同じ押下保持が終了ポップアップ側の
    判定にまで流れ込み、終了ポップアップが見えないまま needs_reset が
    立ってしまう不具合が見つかった（`_update_settlement_popup()` /
    `_update_game_end_popup()` の docstring を参照）。原因は「押下（down）の
    瞬間に実行する」設計そのものにあり、CLOSING（実行後に指が離れるのを
    別途待つ状態）はその場しのぎだった。実行そのものを「指を離した瞬間
    （released）」まで遅らせれば、実行される時点で押下は必ずもう終わって
    いるため、CLOSING が担っていた「取りこぼし防止」は成立の時点で自動的に
    満たされる。CLOSING は不要になったため削除し、NONE / SHOWN の2状態へ
    戻した。

    区画選択ポップアップの4状態（押下位置に追従し、解除で固定し、ボタン
    押下で閉じ、指が離れて戻る）とは遷移の形が異なる（時間経過で勝手に
    現れ、矩形内の押下解除だけで閉じる。押下位置への追従が無い）ため、
    PopupState へは混ぜず独立させたまま（設計判断のとおり）"""

    # 決算ポップアップが出ていない。区画選択ポップアップ・フィールド操作は
    # 通常どおり（_update_popup() が動く）
    NONE = "none"
    # 決算タイマー満了で現れ、矩形内での押下解除（released）を待っている
    SHOWN = "shown"


class GameEndState(Enum):
    """ゲーム終了（クリア／ゲームオーバー）の状態（ID-017 案4。ID-015 が
    予告した「3つ目のモーダル」の決着）。PopupState（区画選択の4状態）・
    SettlementPopupState（決算の2状態）とは別に持つ、1つの独立した Enum。

    クリアとゲームオーバーは同時に成立し得ない——規定店舗数
    （`Field.CLEAR_SHOP_COUNT` ≧ 1軒）への到達と、売り尽くし（0軒）は
    両立しない（ID-028_subtasks.md 決定3）。したがって真偽値2つ
    （クリア中フラグ・オーバー中フラグ）ではなく、1つの Enum の相異なる
    値として持てる（PopupState / SettlementPopupState を1つの Enum へ
    一本化した判断と同じ理由。両方が立つというあり得ない組み合わせを
    型の上で作れなくする）。

    「押されて閉じた」に相当する状態は持たない。本タスク（ID-017）は
    終了ポップアップの押下を一切受け付けない（クリックによるリセットは
    ID-018）ため、押下由来で状態が変わること自体が無い。一度立った終了
    状態は本タスクの範囲では戻らない（出口は ID-018 のリセットのみ。
    保存もしない——ID-017 案3）"""

    # 終了していない。区画選択・決算の各ポップアップ、フィールド操作は
    # 通常どおり
    NONE = "none"
    # 規定店舗数（Field.CLEAR_SHOP_COUNT）へ到達した状態で決算を通過した
    # （Field.is_clear_shop_count_reached。ID-028）
    CLEAR = "clear"
    # 成立経路は2つ（決定5。いずれも _settle_tax() の中で判定される）:
    # (1) 売り尽くしても不足額に届かなかった（not Field.shortfall_covered。
    #     ID-017）
    # (2) 事業を再開する手段が無い——プレイヤー所有店舗が0軒かつ資金が
    #     最小取得費用未満（GameCore._check_business_continuation()。
    #     要件 3.15。ID-024）。他店建設間隔ごとの建設・増資の直後
    #     （update()）からも成立し得る。(1) が成立するときは必ず (2) も
    #     成立するが、(1) が先に判定され return するため、その場合 (2) の
    #     判定（Field.min_acquisition_cost() の呼び出し）へは到達しない
    GAME_OVER = "game_over"


class GameCore:
    SCREEN_W = 300
    SCREEN_H = 400
    SAVE_INTERVAL_MS = 10000
    # 他店建設間隔（仮値 10 秒）。BUILD_COST / INITIAL_MONEY / INVEST_COST と同じ
    # 扱いで値そのものは暫定であり、売上（ID-010）・税（ID-014）・決算（ID-015）が
    # 揃って収支が成立する時点でゲームバランスとして再調整する
    NPC_GROWTH_INTERVAL_MS = 10000
    # 売上発生間隔（仮値 3 秒）。他店建設間隔より**短くする**。売上の抽選は
    # マップ上の全店舗が対象のため、街が広がるほど自店が当たる確率は下がり、
    # 間隔まで同じだと序盤から収入が止まって見える。また異なる値にすることで、
    # 2つのタイマーが独立に動いていることが画面から見分けられる（同値だと
    # 起点が同じため以後ほぼ毎回同時に満了する）。値そのものは
    # NPC_GROWTH_INTERVAL_MS と同じく暫定
    SALES_INTERVAL_MS = 3000
    # 決算間隔（仮値 60 秒）。他店建設間隔（10秒）の6倍・売上発生間隔（3秒）の
    # 20倍で、決算までに売上が約20回・他店の成長が6回入る（他店が育って地価が
    # 上がり、税額が増えていくことが1回の決算を待つ間に読み取れる）。3つの
    # 間隔がいずれも異なる値であることは、SALES_INTERVAL_MS の docstring が
    # 述べる理由（3つのタイマーが独立に動いていることが画面から見分けられる）の
    # 3件目でもある。値そのものは他の2つと同じく仮値で、税額（ID-014）・
    # 各費用（ID-006〜ID-009）が出そろって収支が成立する ID-015 で再調整する
    SETTLEMENT_INTERVAL_MS = 60000

    # フィールドの縦方向レイアウト: 「道路 ROAD_SIZE → 区画 PLOT_SIZE」を 1 ピッチとして
    # 繰り返し、最下段に閉じの道路をもう 1 本描く（道路の本数 = 区画の行数 + 1）
    ROAD_SIZE = 8
    PLOT_SIZE = 16
    PITCH = ROAD_SIZE + PLOT_SIZE  # 24
    STATUS_H = 24  # ステータス領域の高さ（仮値。正式なレイアウトは ID-004 で確定）
    FIELD_ORIGIN_Y = STATUS_H  # フィールド上原点
    STATUS_X = 0
    STATUS_Y = 0
    STATUS_W = SCREEN_W
    STATUS_BG_COL = 1  # 濃紺
    STATUS_PAD = 4  # ステータス領域の内側余白（テキストの起点に使う）
    # ステータス2行目（決算までの残り時間・支払い予定税額）の、1行目からの
    # 縦方向のずれ（行高。ID-014）。Pyxel のデフォルトフォントの行高そのもの
    # であり、ポップアップの数値3行の行間 POPUP_LINE_H と**値としては同じ
    # 8 になるが別の定数として持つ**（一方は「ステータスの行を1行分ずらす」
    # 意味、他方は「ポップアップの数値行を積む」意味で、たまたま同じ値なだけ。
    # 共通化すると片方の行高を変えたときにもう片方が意図せず連動してしまう。
    # Shop.sales と増資費用の式が同じ形でも共通化しない判断と同じ）。
    # STATUS_PAD（4）+ 2行 × STATUS_LINE_H（8）＝ 20 は STATUS_H（24。ID-004で
    # 確定済み・本タスクでは変えない）に収まる
    STATUS_LINE_H = 8
    # ステータス右列（店舗数）の固定 x（要件「4. プレイヤーステータス」。
    # ID-028 サイクル028-4で1行目の店舗数として新設）。左列（資金・税額。
    # STATUS_X + STATUS_PAD）へ続けて同じ draw_text で描かず、**固定 x を
    # 持つ別の draw_text にする**——資金・税額の桁数（右詰めでも
    # STATUS_VALUE_MAX_DIGITS 桁を超えれば動く）で右列の表示位置が左右に
    # 動かないようにするため（決定6-D の却下理由。ID-028_subtasks.md）。
    # 値は資金の最大表示幅（"MONEY 999999" = 12文字 × FONT_CHAR_W = 48px。
    # STATUS_PAD を足すと x=52 で終わる）より右、右側のポーズ／スピード
    # ボタン（pause_x = STATUS_X + STATUS_W - STATUS_PAD - STATUS_BTN_GAP -
    # STATUS_BTN_W * 2 = 252）より左に収まる仮値。プレイテストで確定する。
    # **2行目（決算までの残り時間）はこの x を共有しない**——ID-026
    # サイクル026-4では2行目も同じ列へ移して共用していた（決定9）が、
    # ID-027 でプログレスバーへ置き換えた際、プレイテスト指示により
    # バーの位置を税額の数値に近づける形へ変更し（STATUS_BAR_X）、この
    # 共有は終わった（ID-027_subtasks.md「プレイテスト指摘」参照）
    STATUS_SHOP_COUNT_X = 100
    # 資金・支払い予定税額の数値を右詰めにするときに見込む最大桁数
    # （ID-026 サイクル026-4。プレイテスト指示3「数値は最大長を決めて
    # 右詰めにする」）。値そのものへの上限キャップではなく、右詰め計算に
    # 使う表示幅（FONT_CHAR_W × 10 = 40px）を決めるための想定値——資金・
    # 税額の理論上限桁数（ID-026_subtasks.md 実測。資金6桁・税額8桁）に
    # 余裕を持たせた10桁とし、両者は同じ列に縦に並んで一の位を揃えるため
    # 共通の1つの定数として持つ（項目ごとに分けない）。10桁を超える値は
    # 右詰め計算上そのまま左へはみ出す（キャップしない）
    STATUS_VALUE_MAX_DIGITS = 10
    # ステータス領域右のポーズ「||」・スピード「>」ボタン（ID-019）の
    # 位置・大きさ・配色。専用定数として新設する（設計方針6。値が既存の
    # 定数と同じでも意味が異なる定数は別に持つという本コードベース一貫の
    # 方針——STATUS_LINE_H / POPUP_LINE_H などと同じ）。幅・高さは2つの
    # ボタンに共通の値を1つ持つ（ラベルの長さでボタンの大きさが変われば
    # ポーズ・スピードの押し間違いが起きやすくなるため、最長ラベル
    # 「>>>」が収まる大きさに揃える）。値はいずれも仮値で、プレイテストで
    # 確定する
    STATUS_BTN_W = 20
    STATUS_BTN_H = 16
    STATUS_BTN_GAP = 4  # 2つのボタンの間隔（横方向）
    STATUS_BTN_COL = 5
    # 「いま効いていない側」を示す無効表示の背景色（黒。設計方針6-1）。
    # 資金不足時のポップアップの無効ボタン（POPUP_BTN_DISABLED_COL。
    # 塗りつぶさず枠線だけを描き「押しても実行されない」ことを示す）とは
    # 意味が異なる——こちらは押下そのものを常に受け付けており（ポーズ中は
    # どちらのボタンを押しても解除される）、「押せない見た目」ではなく
    # 「今は効いていない状態」を示すため、同じ見た目にはせず専用の定数を
    # 新設する
    STATUS_BTN_DISABLED_COL = 0
    PAUSE_BTN_LABEL = "||"
    # ゲームスピードの段階（ラベル, 待機時間の除数）の並び（ID-019）。
    # POPUP_BTN_ICONS が「ボタンの並び1つを描画・判定・実行のすべてが
    # 読む」形にしているのと同じく、段階が増えたときにラベル・除数の
    # 対応を複数箇所で揃える必要が無いよう1つの並びで持つ。現在の段階は
    # この並びの添字（self._speed_index）で表し、押すたびに
    # (index + 1) % len(GAME_SPEED_STEPS) で循環する（最高速の次は
    # 最低速へ戻る）。除数は各タイマーへの反映（サイクル 019-5）で使い、
    # 本サイクル（019-4）はラベルの循環表示のみを扱う
    GAME_SPEED_STEPS = ((">", 1), (">>", 3), (">>>", 10))
    # ラベルの中央寄せに使う、Pyxel 組み込みフォント1文字あたりの幅の目安
    # （既存コメント「1文字4×6px相当」より）。既存の単一文字ボタン
    # （「o」「x」など）は中央寄せの量（半分の幅＝2）を "-2" の固定値の
    # まま書いていたが、本ボタンは「||」（2文字）〜「>>>」（3文字）まで
    # ラベルの文字数が変わるため、文字数から中央寄せの量を求める
    # （FONT_CHAR_W * 文字数 の半分）必要がある
    FONT_CHAR_W = 4
    # 区画の列数・行数は「区画ごとの状態を保持する」Field 自身の役割に含まれる
    # ため、値の決め手は Field 側の知識（ID-008）とし、定数を二重に持たないよう
    # Field.GRID_COLS / Field.GRID_ROWS を参照する（Shop.SCALE_MAX を
    # SHOP_SCALE_MAX が参照するのと同じ判断）。画面レイアウト（SCREEN_W /
    # SCREEN_H / PLOT_SIZE / PITCH）はこの区画数がちょうど収まるように選んだ値
    GRID_COLS = Field.GRID_COLS
    GRID_ROWS = Field.GRID_ROWS
    # 左原点 = 左右の余白を均等割り（余白 6px ずつ）
    GRID_LEFT = (SCREEN_W - GRID_COLS * PLOT_SIZE) // 2

    # 道路の転送元（layer0 の (8, 0) 8×8、透過色 0）
    ROAD_IMG = 0
    ROAD_U = 8
    ROAD_V = 0
    ROAD_COLKEY = 0

    # 店舗の転送元（layer0、16×24、透過色 0）。u は規模 n（SHOP_SCALE_MIN..
    # SHOP_SCALE_MAX）ごとに SHOP_U_STEP 刻みで変わり、v は所有者（NPC / プレイヤー）
    # で切り替わる
    SHOP_W = 16
    SHOP_H = 24
    SHOP_IMG = 0
    SHOP_U_ORIGIN = 8
    SHOP_U_STEP = 16
    SHOP_V_NPC = 8
    SHOP_V_PLAYER = 32
    SHOP_COLKEY = 0
    # 店舗規模の下限・上限（登録済み画像の段階数（10 段階）に対応する境界）。
    # いずれも値の決め手は Shop 側の知識（下限＝初期規模、上限＝増資の上限。
    # ID-007）のため、定数を二重に持たないよう Shop.INITIAL_SCALE /
    # Shop.SCALE_MAX を参照する
    SHOP_SCALE_MIN = Shop.INITIAL_SCALE
    SHOP_SCALE_MAX = Shop.SCALE_MAX

    # アイコン（layer0 の v=56、u=8刻みで8種）の転送元・大きさ・配色・間隔。
    # 数値の意味を表すアイコンはすべて 7×7・色13・余白0（透過色として使える）
    # で1枚のシートへ作成済みであり、大きさ・画像バンク・透過色は8種で共通の
    # 1組しか持たない（ID-026 決定1。ROAD_* / SHOP_* とは異なり、アイコンの
    # 大きさは「たまたま同じ値」ではなく1枚の画像シート上の実体が同一で、
    # 意味も1つ（アイコン1個の大きさ）しか持たないため、描画箇所ごとに
    # 定数を分けない）
    ICON_IMG = 0
    ICON_W = 7
    ICON_H = 7
    ICON_COLKEY = 0
    # アイコンと数値の組を描くときの、アイコンの右端から数値までの間隔。
    # 出発点は区画選択ポップアップの数値行に使える幅（28px = 7文字）を
    # 超えない範囲で最小の1pxだったが、プレイテスト指示2により3pxへ
    # 広げた（ID-026 サイクル026-4）。ポップアップ側の残り幅は 28 − 2 =
    # 26px（6文字）となり、最大桁数6桁 = 24px は引き続き収まる
    # （ID-026_subtasks.md「レイアウトの制約」。026-2 で確認する）
    ICON_GAP = 3
    # 8つのアイコンの転送元 (u, v) は、意味ごとの名前付き定数として持つ
    # （ID-026 決定2）。店舗画像の u が規模という順序を添字で導けるのとは
    # 異なり、アイコンの並びは意味の並びにすぎず、添字（「資金は3番目」）に
    # 画像の配置以外の根拠が無いため、添字では導かない。026-1 で資金・
    # 支払い予定税額・店舗数の3つを、026-2 で費用・資産価値・売上額の3つを、
    # 026-3 で残る○×の2つを追加した
    ICON_MONEY = (32, 56)
    ICON_TAX = (24, 56)
    ICON_SHOP_COUNT = (40, 56)
    # 区画選択ポップアップ数値3行（_draw_popup_values()）が使う3つ。費用は
    # 建設・増資・買収のいずれでも同じ1枚を使う（ID-026 決定3。
    # src/images.pyxres に費用アイコンは1枚しか作成されておらず、3つの費用は
    # 選択中の区画の状態が一意に決めるため区画の状態による切り替えが要らない）
    ICON_COST = (48, 56)
    ICON_VALUE = (56, 56)
    ICON_SALES = (64, 56)
    # 4つのポップアップのボタン（区画選択の○×、決算・ゲームクリア・
    # ゲームオーバーの○）が使う2つ（ID-026 サイクル026-3）。○は実行に
    # 結び付くボタン全て（区画選択・決算・ゲームクリア・ゲームオーバー）が
    # 共有し、×は区画選択のキャンセルのみが使う
    ICON_OK = (16, 56)
    ICON_CANCEL = (8, 56)

    # 決算までの残り時間を示すプログレスバー（ID-027 決定5。位置・幅は
    # プレイテスト指示〈2026-08-30〉により、出発点〈STATUS_SHOP_COUNT_X
    # 共有・幅60px仮値〉から改めた）。
    # 高さ: 1行目のアイコン（ICON_H）と視覚的な行の高さを揃える
    STATUS_BAR_H = ICON_H
    # 左端: 左列の税額の数値領域の右端（STATUS_X + STATUS_PAD + ICON_W +
    # ICON_GAP + FONT_CHAR_W * STATUS_VALUE_MAX_DIGITS。_draw_icon_value_
    # right() が右詰めに使う領域そのもの）から5px離した位置——税額の数値に
    # バーを近づけて欲しいというプレイテスト指示による。右詰めのため
    # 実際の桁数によらずこの右端は動かない。右列1行目（店舗数）と共有して
    # いた固定 x（STATUS_SHOP_COUNT_X）はもう使わない
    STATUS_BAR_X = (
        STATUS_X
        + STATUS_PAD
        + ICON_W
        + ICON_GAP
        + FONT_CHAR_W * STATUS_VALUE_MAX_DIGITS
        + 5
    )
    # 幅: 右端をポーズボタンの左端（STATUS_X + STATUS_W - STATUS_PAD -
    # STATUS_BTN_GAP - STATUS_BTN_W * 2）の手前 STATUS_BAR_PAUSE_GAP ぶんまで
    # 伸ばす——プレイテスト指示「ポーズボタンの横まで引っ張ってみて
    # 欲しい」により出発点の60px仮値から使える幅いっぱいまで拡張した後、
    # 「ポーズボタンとバーの右枠の間に5pxの空間を入れて欲しい」という
    # 追加のプレイテスト指示を受け、ちょうど届く幅から5px引いた
    STATUS_BAR_PAUSE_GAP = 5
    STATUS_BAR_W = (
        STATUS_X
        + STATUS_W
        - STATUS_PAD
        - STATUS_BTN_GAP
        - STATUS_BTN_W * 2
        - STATUS_BAR_X
        - STATUS_BAR_PAUSE_GAP
    )
    # 枠・中身の色。STATUS_BG_COL（濃紺）の上に載るため、背景から分離して
    # 見える色を選ぶ。意味の異なる既存の色定数（STATUS_BTN_COL など）は
    # 流用せず、専用の定数として別に持つ（ID-026 決定6と同じ方針）。
    # 枠を白、中身を緑（残量が視覚的に伝わる配色）とする仮値で、値は
    # プレイテストで確定する
    STATUS_BAR_FRAME_COL = 7  # 白
    STATUS_BAR_FILL_COL = 11  # 緑

    # 「店舗画像とその下の道路」を合わせた範囲の大きさ。ポップアップのプレビュー
    # 領域（_draw_popup_preview）と、フィールド上の選択枠（_draw_selection）が
    # **同じ範囲**を示すための共通の定数。両者を揃えることで、枠の中に見えている
    # ものとプレビューに描かれるものが一致する（中間プレイテストでの指示による。
    # 枠は判定範囲（高さ PITCH）より道路 1 本分だけ縦に長くなる）
    PREVIEW_W = PLOT_SIZE
    PREVIEW_H = SHOP_H + ROAD_SIZE

    # ポップアップ（区画選択）の位置・サイズ・配色。いずれも仮値で、
    # プレイテストで確定する。
    # 画面の縁から空ける間隔。ポップアップがフィールドの上に浮いて見えるようにする。
    # 左右 2 通りの表示位置（後続サイクル）でも同じ値を使い、どちらの位置でも
    # 縁からの間隔を揃える
    POPUP_MARGIN = 4
    # 数値3行の右端（POPUP_PAD + PLOT_SIZE + POPUP_GAP + ICON_W + ICON_GAP +
    # POPUP_VALUE_MAX_DIGITS(7) × FONT_CHAR_W(4) = 4+16+4+7+3+28 = 62）に
    # 右側の内側余白 POPUP_PAD(4) を足した値。プレビュー画像・ボタンの左端が
    # 左の内側余白 POPUP_PAD と揃っているのに対し、数値の右端と右枠線の間が
    # それより狭く見えるという中間プレイテスト指示により、左右の余白が揃う
    # 66 へ広げた（ID-026 サイクル026-6。POPUP_BTN_W はポップアップ幅いっぱい
    # − 2×POPUP_PAD の式のまま追従するため、ボタン幅も自動的に広がる）
    POPUP_W = 66
    # ポップアップの「内側」の余白（枠と中身との間）。POPUP_MARGIN（外側の間隔）
    # とは別物
    POPUP_PAD = 4
    # プレビュー（幅 PREVIEW_W）と数値3行の間の横方向の間隔
    POPUP_GAP = 4
    # 数値3行（費用・資産価値・売上額）の行間。出発点は8（ICON_H(7)+1px）
    # だったが、行同士がアイコン画像の直後で詰まって見えるという中間
    # プレイテスト指示により、アイコンの下端との間が3px空く10へ広げた
    # （ID-026 サイクル026-5）
    POPUP_LINE_H = 10
    # 数値3行のブロック（アイコンの高さ ICON_H + 行間 POPUP_LINE_H を2回ぶん）の
    # 高さと、プレビュー領域（PREVIEW_H）に対して縦方向中央へ来るための上余白。
    # 中間プレイテスト指示（プレビュー画像に対して3行が上に詰まって見える）に
    # よる。中央揃えの余り（PREVIEW_H − ブロック高さ）が奇数のときは整数除算で
    # 切り捨て、余った1pxは下側へ回す（STATUS_BTN_H // 2 − 2 と同じ丸め方針）
    POPUP_VALUES_BLOCK_H = 2 * POPUP_LINE_H + ICON_H
    POPUP_VALUES_TOP_PAD = (PREVIEW_H - POPUP_VALUES_BLOCK_H) // 2
    # 数値3行の右詰め計算に使う想定最大桁数（ID-026 サイクル026-5。中間
    # プレイテスト指示）。STATUS_VALUE_MAX_DIGITS と同じくキャップではなく
    # 表示幅を決めるための想定値で、これを超える桁数の値はそのまま左へ
    # はみ出す。実測の理論上限（6桁。「レイアウトの制約」節）に対し1桁の
    # 余裕を持たせた値のため、実際に7桁へ達することは無い
    POPUP_VALUE_MAX_DIGITS = 7
    # 費用が存在しないとき（規模が上限のプレイヤー所有店舗は増資できないため
    # 増資費用が存在しない。要件 3.6）に、費用の行へ数値の代わりに描く文字。
    # 表示上の記号を決めるのは描画側という分担（Field/Shop は費用の不在を
    # None で返すだけ）を、この定数が GameCore 側にあることで表す。
    # PAUSE_BTN_LABEL / GAME_END_MESSAGE_CLEAR と同じく、画面に出る文字は
    # 定数として名前を付ける（記号そのものを変えるときの触り先を1箇所にする）
    POPUP_NO_COST_TEXT = "-"
    # 「o」「x」ボタン（矩形＋アイコン）。中間プレイテストでの指示により、横並びから
    # 縦並びへ変更した。幅はポップアップ幅いっぱい（左右に内側余白 POPUP_PAD ぶんを
    # 残す）に広げ、高さは横並びだったときの値（10）の3倍にした
    POPUP_BTN_W = POPUP_W - 2 * POPUP_PAD
    POPUP_BTN_H = 10 * 3
    POPUP_BTN_GAP = 4  # 縦に並ぶ o・x の間隔
    POPUP_BTN_COL = 5
    # ボタンの並び（上から順）。描画のアイコン・押下判定の対象数・実行に結び付く
    # ボタンの特定が、いずれもこの 1 つの並びを読む（ボタンが増減したときに
    # 片方だけ追従し損なうことがないよう、個数を別に持たない）。文字だった時期は
    # POPUP_BTN_LABELS（"o", "x"）という名前だったが、アイコン化（ID-026
    # 決定2）に伴い、名前付き定数 ICON_OK / ICON_CANCEL を並べたものへ置き換えた
    # ——中身が意味ごとの名前付き定数であることと、並びとして持つ必要があること
    # （_popup_button_index_at() が len() を読む）は両立する
    POPUP_BTN_ICONS = (ICON_OK, ICON_CANCEL)
    # 実行（本タスクでは建設。増資は ID-007、買収は ID-009）に結び付くボタン。
    # 「x」は常にキャンセル（閉じるだけ）
    POPUP_BTN_INDEX_O = 0
    # ポップアップ全体の高さ。上から「上余白 → プレビュー領域（PREVIEW_H）→
    # 余白 → ボタン2つ（縦に POPUP_BTN_GAP 空けて並ぶ）→ 下余白」の合計。
    # ボタンを縦並び・3倍の高さへ変更したことに合わせて算出し直した
    POPUP_H = (
        POPUP_PAD
        + PREVIEW_H
        + POPUP_PAD
        + (2 * POPUP_BTN_H + POPUP_BTN_GAP)
        + POPUP_PAD
    )
    # 表示は常に画面下部。縦位置は固定で、押下位置に応じて切り替わるのは左右のみ。
    # 左下・右下それぞれの原点 x を定数として持ち、_popup_origin_x() が押下位置から
    # どちらを使うかを選ぶ（画面の縁からの間隔 POPUP_MARGIN はどちらも同じ値を使う）
    POPUP_Y = SCREEN_H - POPUP_H - POPUP_MARGIN
    POPUP_LEFT_X = POPUP_MARGIN
    POPUP_RIGHT_X = SCREEN_W - POPUP_W - POPUP_MARGIN
    # 背景は黒。テクスチャのある道路・店舗の上でも中身が読めるよう塗りつぶし、
    # 枠線（濃紺）で外周を締めてフィールドとの境目を分ける
    POPUP_BG_COL = 0
    POPUP_BORDER_COL = 1
    # 実行できないボタン（本タスクでは資金不足時の「o」）の枠線の色。無効なボタンは
    # 塗りつぶさず枠線だけを描くため、ポップアップの地の一部として静かに沈んで
    # いてほしい。外周の枠線と**同じ色である**ことが意図のため、値 1 を直接書かず
    # POPUP_BORDER_COL を参照する（外周の色を変えたときに無効ボタンだけ取り残されない）
    POPUP_BTN_DISABLED_COL = POPUP_BORDER_COL

    # 決算ポップアップ（決算タイマー満了で現れ、区画選択ポップアップとは無関係に
    # 独立して開閉する）の位置・大きさ・配色。区画選択ポップアップと異なり
    # 押下位置に応じて左右へ切り替わらない（時間経過で勝手に現れるため、指の
    # 位置とは無関係）ため、画面中央固定の1組の定数で足りる。値はいずれも
    # 仮値で、プレイテストで確定する（POPUP_* を再利用するか決算専用に新設
    # するかは ID-015 サイクル1時点では新設を選んだ。3行の表示が入るサイクル2で
    # 改めて判断する）
    SETTLEMENT_POPUP_W = 100
    # 数値3行（減算前・税額・減算後）の内側余白・行間。値は POPUP_PAD /
    # POPUP_LINE_H と同じ 4・8 だが、他の SETTLEMENT_POPUP_* と同じく決算専用に
    # 独立して持つ（サイクル2 Refactor で判断）
    SETTLEMENT_POPUP_PAD = 4
    SETTLEMENT_POPUP_LINE_H = 8
    # 精算を実行する「o」ボタン（サイクル5 Refactor・再考。ユーザー指摘に
    # よる変更）。当初はポップアップの矩形全体をタップ対象にしていたが、
    # 見ただけでは「タップして閉じる」ことが読み取れないという指摘を受け、
    # 区画選択ポップアップと同じ「塗りつぶした矩形＋アイコン」のボタンへ
    # 変更した。数値3行の下、内側余白ぶん空けて幅いっぱいに置く（区画選択
    # ポップアップの POPUP_BTN_W が POPUP_PAD を左右に残して幅いっぱいに
    # 広げているのと同じ考え方）。「x」（キャンセル）に相当するボタンは
    # 持たない——精算は必ず実行される操作であり、キャンセルできる余地は
    # 要件に無い（設計判断「資金が足りない場合も減算し、資金をマイナスに
    # する」のとおり）。アイコンは区画選択ポップアップの実行ボタンと同じ
    # ICON_OK（ID-026 サイクル026-3。実行ボタンは常に○のため、専用の
    # ラベル定数は持たず ICON_OK を直接参照する）
    SETTLEMENT_POPUP_BTN_W = SETTLEMENT_POPUP_W - 2 * SETTLEMENT_POPUP_PAD
    SETTLEMENT_POPUP_BTN_H = 20
    # 値は区画選択ポップアップの POPUP_BTN_COL と同じ 5 だが、他の
    # SETTLEMENT_POPUP_* と同じく決算専用に独立して持つ
    SETTLEMENT_POPUP_BTN_COL = 5
    # 数値3行 + 余白2つ + ボタンの高さ（横線と3行目の隙間を空ける前の
    # 素の合計）。SETTLEMENT_POPUP_Y の中央揃えはこの高さを基準にする
    # （SETTLEMENT_POPUP_RULE_TEXT_GAP は下方向にだけ枠を広げるためのもので、
    # 上端の位置には影響させない。2026-08-30 プレイテスト指摘）
    SETTLEMENT_POPUP_BASE_H = (
        SETTLEMENT_POPUP_PAD
        + 3 * SETTLEMENT_POPUP_LINE_H
        + SETTLEMENT_POPUP_PAD
        + SETTLEMENT_POPUP_BTN_H
        + SETTLEMENT_POPUP_PAD
    )
    SETTLEMENT_POPUP_X = (SCREEN_W - SETTLEMENT_POPUP_W) // 2
    SETTLEMENT_POPUP_Y = (SCREEN_H - SETTLEMENT_POPUP_BASE_H) // 2
    # 値は区画選択ポップアップ（POPUP_BG_COL / POPUP_BORDER_COL）と同じ 0・1 だが、
    # 意味が異なる（決算ポップアップ専用）ため独立して定義する
    # （STATUS_LINE_H / POPUP_LINE_H が同じ値 8 を別々に持つ判断と同じ）
    SETTLEMENT_POPUP_BG_COL = 0
    SETTLEMENT_POPUP_BORDER_COL = 1
    # 筆算の横線（3行目の上・決定11）の色。SETTLEMENT_POPUP_BORDER_COL
    # （枠線）を流用せず、意味の異なる専用の定数として持つ（STATUS_BAR_
    # FRAME_COL と同じ白 7 を出発点とし、値そのものはプレイテストで確定する）
    SETTLEMENT_POPUP_RULE_COL = 7
    # 横線と3行目（減算後）の数字との間の余白（プレイテスト指摘。
    # 2026-08-30。当初は横線の直下に数字が接しており「数字が横罫線に
    # 触れている」という指摘を受けた）。3行目だけをこのぶん下へずらし、
    # ボタン・枠の高さも同じぶん下方向へ追従させる
    SETTLEMENT_POPUP_RULE_TEXT_GAP = 2
    # 枠全体の高さ。SETTLEMENT_POPUP_BASE_H に、3行目を下へずらしたぶん
    # （SETTLEMENT_POPUP_RULE_TEXT_GAP）を足して、枠を下方向にだけ広げる
    SETTLEMENT_POPUP_H = SETTLEMENT_POPUP_BASE_H + SETTLEMENT_POPUP_RULE_TEXT_GAP
    # 数値3行の右端とポップアップ右枠の内側との間に空ける余白（プレイテスト
    # 指摘。2026-08-30）。従来は数値領域の左端を SETTLEMENT_POPUP_PAD の
    # 位置に固定していたため、桁数の少ない値ほど罫線の長さに対して数字が
    # 中央寄りに見えていた。右端をポップアップ右枠からこのぶんだけ空けた
    # 位置に固定し、そこから桁数ぶん左へ伸ばす右詰めへ変更する
    SETTLEMENT_POPUP_VALUE_RIGHT_GAP = 5

    # 終了（クリア／ゲームオーバー）ポップアップ（要件「ゲーム終了後」。
    # ID-017 案4・案6）の位置・大きさ・配色。決算ポップアップと同じく画面
    # 中央固定・押下位置に応じて左右へ切り替わらない（時間経過・操作の結果
    # として現れ、指の位置とは無関係）ため、画面中央固定の1組の定数で足りる。
    # 値はいずれも仮値で、プレイテストで確定する。SETTLEMENT_POPUP_* を
    # 再利用せず専用に新設する（ID-015 が決算ポップアップを区画選択の
    # POPUP_* から独立させた判断の3件目。値が同じでも意味が異なる定数は
    # 別に持つという本コードベース一貫の方針——STATUS_LINE_H / POPUP_LINE_H
    # などと同じ）
    GAME_END_POPUP_W = 100
    # 文言（1行）の内側余白・行間。SETTLEMENT_POPUP_PAD / _LINE_H と同じ 4・8
    # だが、他の GAME_END_POPUP_* と同じく専用に独立して持つ
    GAME_END_POPUP_PAD = 4
    GAME_END_POPUP_LINE_H = 8
    # 終了ポップアップの「o」ボタン。押しても閉じない（本タスクでは押下を
    # 受け付けない。クリックによるリセットは ID-018）が、決算ポップアップと
    # 同じ「塗りつぶした矩形＋アイコン」の見た目で描く——ID-015 のプレイテストで
    # 「ポップアップを見ただけでは閉じ方が分からない」という指摘を受けた
    # 経緯（決算ポップアップのボタン化）を踏まえ、押せそうな見た目を最初から
    # 用意する（案6）。アイコンは決算ポップアップと同じ ICON_OK（ID-026
    # サイクル026-3。専用のラベル定数は持たず ICON_OK を直接参照する）
    GAME_END_POPUP_BTN_W = GAME_END_POPUP_W - 2 * GAME_END_POPUP_PAD
    GAME_END_POPUP_BTN_H = 20
    GAME_END_POPUP_BTN_COL = 5
    # ポップアップ全体の高さ。上から「上余白 → 文言1行 → 余白 → 「o」
    # ボタン → 下余白」の合計（区画選択・決算の各ポップアップの POPUP_H /
    # SETTLEMENT_POPUP_H と同じ、内側余白を区切りに積み上げる組み立て方）
    GAME_END_POPUP_H = (
        GAME_END_POPUP_PAD
        + GAME_END_POPUP_LINE_H
        + GAME_END_POPUP_PAD
        + GAME_END_POPUP_BTN_H
        + GAME_END_POPUP_PAD
    )
    GAME_END_POPUP_X = (SCREEN_W - GAME_END_POPUP_W) // 2
    GAME_END_POPUP_Y = (SCREEN_H - GAME_END_POPUP_H) // 2
    # 値は区画選択・決算の各ポップアップと同じ 0・1 だが、意味が異なる
    # （終了ポップアップ専用）ため独立して定義する
    GAME_END_POPUP_BG_COL = 0
    GAME_END_POPUP_BORDER_COL = 1
    # 文言（Pyxel の ASCII 制約内の仮値）。クリアとゲームオーバーで変わるのは
    # この1行だけで、枠・位置・大きさ・配色・ボタンは共通にする（案6）
    GAME_END_MESSAGE_CLEAR = "CLEAR"
    GAME_END_MESSAGE_GAME_OVER = "GAME OVER"

    # 選択中の区画をフィールド上で示す枠の色（黄色）。フィールド上の既存要素
    # （道路タイル・店舗画像・濃紺のステータス背景）に埋もれないことが条件で、
    # 仮値としてプレイテスト（TASK-005-32）で確定する
    SELECTION_COL = 10

    # 売上の抽選が起きた店舗をフィールド上で囲む枠の色（赤）。フィールド上の
    # 既存要素（道路タイル・店舗画像・濃紺のステータス背景）に埋もれないことが
    # 条件。範囲が選択枠（SELECTION_COL）と完全に一致するため、**同じ区画で
    # 同時に出たときは色による見分けができず、後に描く選択枠がそのまま
    # 見える**（_draw_sales_frame() の docstring）。仮値であり、SELECTION_COL と
    # 同じくプレイテストで確定する
    SALES_FRAME_COL = 8

    # プレイヤーの初期資金。ID-006 では表示が成立することの確認までを範囲とし
    # 1000（暫定）のまま確定していたが、ID-028 のプレイテストで「開始直後に
    # 中心（建設費用が最も高い区画。地域価格倍率3.0で BUILD_COST の3倍=300）を
    # 確保できてしまい、序盤の難易度がほぼ無くなる」という指摘を受け、中心を
    # 即座には確保できない額（200。外周の建設費用100の2軒分）へ引き下げた
    # （ユーザー確認・2026-08-25）。他の8定数（BUILD_COST 等）と同じく、
    # ゲームバランスとしての妥当性は収支が揃う中で継続的に調整する対象である
    INITIAL_MONEY = 200

    def __init__(self, reset=False):
        self._view = PyxelView.create()
        self._input = PyxelInput.create()
        self._field = Field()
        self._report_store = ReportStore()
        # 起点（マップ上に店舗が1軒でも現れること。所有者は問わない。
        # ID-025）を共有するタイマー。開始まわりの知識（開始は一度だけ・
        # 未開始の表し方・復元の続き方）は ShopClock が持ち、ここは間隔を
        # 与えて並べるだけ
        self._npc_growth_clock = ShopClock(self.NPC_GROWTH_INTERVAL_MS)
        self._sales_clock = ShopClock(self.SALES_INTERVAL_MS)
        self._settlement_clock = ShopClock(self.SETTLEMENT_INTERVAL_MS)
        # 開始を1箇所（_start_shop_clocks()）から回すための一覧。タイマーが
        # 増えたときに、開始を呼ぶ側（復元・建設の2箇所）を触らずに済む
        self._shop_clocks = (
            self._npc_growth_clock,
            self._sales_clock,
            self._settlement_clock,
        )
        # ゲームスピードの現在の段階（_apply_load_data() が実際の値へ組み直す）。
        # __init__ で属性として宣言してから _apply_load_data() へ委ねる
        self._speed_index = None
        # reset=True（ID-018 のリセット）のときは self._report_store.load() を
        # 呼ばず、_apply_load_data(None) へ渡す。「保存データが無いときの初期化」
        # として既に存在する経路（空マップ・初期資金・3タイマーとも未開始）を
        # そのまま再利用でき、リセット専用の初期化分岐を新設せずに済む
        self._apply_load_data(None if reset else self._report_store.load())
        # 復元した盤面に既に店舗が1軒でもあれば（所有者は問わない。ID-025）、
        # 起動の時点から経過を始める（リロードで街の成長・売上が止まった
        # ままにならない）
        self._start_shop_clocks()
        # reset=True のときもこの _save() をそのまま使う。上の _apply_load_data(None)
        # で初期状態を適用済みのため、通常の保存経路が初期状態をそのまま
        # 上書き保存する（保存データの初期化専用の別経路は持たない）
        self._save()
        self._save_clock = Clock(self.SAVE_INTERVAL_MS)
        self._bef_down = False
        self._popup_plot = None
        self._popup_x = None
        self._popup_state = PopupState.NONE
        self._sales_plot = None
        self._settlement_popup_state = SettlementPopupState.NONE
        # ポーズボタン「||」によるポーズ中かどうか（ID-019 サイクル6）。
        # 決算・終了ポップアップの状態と同じく保存・復元の対象にしない
        # （設計方針7の「決着」）ため、__init__ は常に False（ポーズ解除）
        # から始まる——リロードするとポーズは必ず解除された状態になる
        self._paused = False
        # ゲーム終了（クリア／ゲームオーバー）の状態（ID-017 案4）。保存も
        # 復元時の再判定もしない（案3）ため、__init__ は常に NONE から始まる
        # （リロードすると終了ポップアップ表示中でもゲームが再開する。
        # ID-018 への申し送り）
        self._game_end_state = GameEndState.NONE
        # 終了ポップアップの「o」ボタンが押されたという事実だけを公開する
        # フラグ（ID-018）。実際に新しい GameCore を作り直すのは App の
        # 役割で、ここでは「作り直してほしい」ことを読み取り専用プロパティ
        # needs_reset で示すだけ（ID-005 / ID-007 と同じ needs_reset パターン）
        self._needs_reset = False
        # 決算ポップアップ表示中に完全凍結する対象（保存・他店建設・売上・
        # 決算の4つ）の一覧。_save_clock は素の Clock、残り3件は
        # ShopClock だが、どちらも pause() / resume() を持つため
        # 同じ一覧で回せる。_shop_clocks（開始をまとめる一覧。3件）とは
        # 対象がずれる（_save_clock を含む）ため別に持つ。update() が
        # この一覧を1箇所だけ回す形にすることで、タイマーが増えても
        # 呼び出し側（update()）を触らずに済み、「4つのうち1つだけ止め
        # 忘れる」経路を実装上作れない（_shop_clocks を
        # _start_shop_clocks() が回す判断（ID-008）と同じ考え方）
        self._freeze_clocks = self._shop_clocks + (self._save_clock,)

    @property
    def needs_reset(self):
        """終了ポップアップの「o」ボタンが押され、この GameCore を
        GameCore(reset=True) へ差し替えてほしいかどうか（ID-018）。
        読み取り専用として公開し、実際に作り直す判断・実行は App.update()
        に委ねる（needs_reset パターン）"""
        return self._needs_reset

    def update(self):
        """時間経過で起きること（保存・NPCの成長・売上・決算）を、押下から
        起きること（ポップアップ操作）より先に、間隔ごとに1行ずつ同じ形で
        処理する。起点を共有するタイマー（他店建設・売上・決算）は、まだ
        開始していない間（マップ上に店舗が1軒も無い間。所有者は問わない。
        ID-025）は時刻を読むこともしない＝経過そのものが始まっていない
        （ShopClock）。
        他店建設間隔（10秒）と売上発生間隔（3秒）が同じフレームで満了しても、
        抽選が乱数源の別々のメソッドに分かれているため、互いの抽選の回数・
        順序に影響しない（IRandomSource）。

        他店建設の直後（self._field.grow_npc() の1行後）に事業継続の判定
        （_check_business_continuation()。要件 3.15。ID-024）を置く。
        この判定でゲームオーバーが成立しても、**そのフレームの残りの処理へ
        追加のガードは要らない**: _end_game() が保存・他店建設・売上・決算の
        4タイマーを pause() するため、同じフレームで続く売上・決算の
        is_up() 判定はいずれも Clock の一時停止分岐で偽を返し、押下由来の
        処理は下の「終了中は…呼ばない」分岐がそのまま抑止する
        （ID-024_subtasks.md 決定4）。

        決算タイマーが満了したフレームは、決算ポップアップを表示するだけで
        なく、区画選択ポップアップが開いていれば既存の _reset_popup()（区画
        外での解除・CLOSING からの復帰と同じ「なし」への戻し方）でその場
        閉じる（要件 3.8。TRACKING / MODAL / CLOSING のいずれであっても同じ
        1行で戻せる——3つの状態を個別に分岐する必要はない）。2つの
        ポップアップが画面上で重ならないことは、この**満了時のリセット**と、
        下の**表示中は _update_popup() を呼ばないこと**の2つで保証しており、
        PopupState 自体は区画選択専用のまま据え置く（設計判断「決算
        ポップアップの状態は…別に持つ」）。

        決算ポップアップの状態が NONE（表示していない）でない間は
        _update_popup() を一切呼ばず、代わりに _update_settlement_popup()
        （精算・終了待ちの押下判定。下記）を呼ぶ。押下保持の記録
        （self._bef_down）は止めずに続ける（凍結が解けて操作が戻ったとき、
        表示中の押下保持を誤って「解除」と読み違えないため）。ポップアップの
        状態機械（_update_popup()）そのものを外側で止めているのは、その中で
        早期に return する形にすると「なぜ何もしないか」が4分岐の奥に
        埋もれるのに対し、ここで止めれば「決算中はフィールド操作そのものが
        無い」ことが呼び出し側の1行で読めるため（ShopClock が
        「経過しない」をタイマーを持たないことで表した判断と同じ考え方）。
        draw() 側（_draw_selection() / _draw_popup()）は区画選択の枠・
        ポップアップを _is_selection_shown()（NONE を除外する述語）から
        描いており、決算用の分岐は新たに足していない——満了時に状態を
        NONE へ戻すだけで、描画が現れないことが自動的に導かれる。

        押下由来の処理（抑止。上記）と、決算ポップアップ表示中に時間経過
        そのものを止める完全凍結（サイクル4）は別の仕組みである。前者は
        _update_popup() を呼ばないことで実現し、後者は保存・他店建設・
        売上・決算の4つのタイマー自体を一時停止する（self._freeze_clocks。
        __init__ を参照）。`is_up()` を呼ばないだけでは時間は止まらない
        （Clock は time.perf_counter() の差分で満了を判定するため、呼ばずに
        いても実時間は進み続ける）ため、Clock.pause() が time.perf_
        counter() の読み取りそのものを止める（Clock 参照）。

        一時停止は、決算タイマーが満了した**その場**（self._settlement_
        popup_state を SHOWN にした直後）で1回だけ呼ぶ。pause() は冪等
        （二度目以降は何もしない）だが、真偽値の状態を毎フレーム読んで
        「表示中なら毎フレーム pause()」という形にはしない——満了していない
        フレームでは呼ばれないという1回性が、ここで読めなくなるため（読む側が
        「これは満了の瞬間にだけ起きる処理だ」と分かる形を優先する）。**この
        位置（4つの is_up() 判定のうち決算タイマー自身の判定の直後）で
        呼ぶことが重要**: この if 文より前（他の3つの is_up() 判定の前や
        更新全体の先頭）に置くと、決算タイマーが満了した「そのフレーム」より
        後——早くても次に update() が呼ばれたとき——にしか一時停止が効かず、
        その間（テストの _advance_ms() による一括の時刻送りなど）に実時間が
        大きく進んでいた場合、既に間隔を超過した値（0で頭打ち）を凍結して
        しまう（決算タイマーの周期性テストが実際にこの順序で壊れたことで
        判明した）。決算タイマー自身の判定の直後に置けば、他の3つのタイマーの
        判定（この if より前で既に完了している）を含め、満了したフレーム
        自身の中でその瞬間の残り時間をそのまま捉えられる。

        再開（resume()）は「表示中でないなら毎フレーム resume()」という形で
        先回りして書かず、pause() と対称に、凍結を解く契機（精算）が実際に
        起きたその場でだけ呼ぶ（_settle_tax() を参照）。決算ポップアップが
        SHOWN でなくなる（矩形内での押下解除＝released で精算し NONE へ
        移る。_update_settlement_popup() を参照）その1行の中で resume() まで
        呼び切ることで、「閉じたのに凍結だけ残る」状態を実装上作れないように
        している（TASK-015-16 の観点「精算と凍結の解除が同じ1つの処理として
        書かれているか」への回答）。

        完全凍結が踏み倒しを防ぐ根拠は、保存（_save_clock）が決算タイマーより
        **先**に判定される、この行の並び順にある。同じフレームで両方が
        満了しても、保存はまだ凍結されていない時点の残り時間（満了直前の
        値）を書き、その直後の一時停止でその状態のまま固定される。この
        並び順を変えると踏み倒しが復活するため、崩さないこと。

        ID-015 が「ID-017（ゲームクリア／ゲームオーバー時の時間経過の停止）も
        同じ self._freeze_clocks・pause() / resume() の仕組みをそのまま使う
        見込み」と予告していたとおり、**ID-017 は実際に同じ一覧へ pause() を
        呼ぶだけで足りた**（_end_game()）。決算との違いは**再開しないこと**
        だけである——決算の凍結は精算（_settle_tax()）で必ず解けるが、終了の
        凍結を解く契機はこのクラスに存在しない（出口は ID-018 のリセットのみ）。
        そのため終了側は「pause() と対称な resume() をどこで呼ぶか」を持たず、
        pause() だけが片道で呼ばれる。

        終了中（self._game_end_state が NONE でない）は、区画選択・決算の
        いずれの状態機械（_update_popup() / _update_settlement_popup()）も
        呼ばない。分岐は2択（決算中か否か）から**3択（終了中／決算中／
        通常）**へ増えるが、終了中は「どちらの状態機械も呼ばない」ため
        else の枝を持たず、押下保持の記録（self._bef_down）まで済ませた
        直後に return する形にした（3つ目の分岐を if/elif/else の3枝で
        書くと、何も呼ばない枝の中身が pass だけになり「終了中は何も
        呼ばない」ことが枝の不在としてより読みにくくなる）。**要件には
        「終了中は操作を受け付けない」という明記が無い**が、ゲームが
        終わっているのに盤面を動かせるのは要件の意図から外れるため足した
        （ID-017 案7）。実際に塞がる経路はクリア後の増資のみである——
        クリア後は空き区画もNPC所有店舗も無いため建設・買収は起こり得ず、
        ゲームオーバー後は資金が負のため可否判定（_cost_covered()）が
        すべて偽になる。

        フィールド操作の状態機械を呼ばない一方、終了中の押下解除
        （released）は _update_game_end_popup()（ID-018）へだけは渡す——
        終了ポップアップの「o」ボタン押下でリセットを起動するのに使う
        唯一の経路であるため、return する前に呼ぶ。区画選択・決算の状態
        機械を止めることと、リセット判定を通すことは矛盾しない: 前者は
        「盤面を動かせない」ためのもの、後者は「終了後の唯一の出口」であり、
        両者は別の目的で押下を扱っている。released だけを渡し down は
        渡さない理由は _update_game_end_popup() の docstring を参照
        （決算の「o」を離さないまま終了ポップアップの「o」の位置へ指が
        乗り続けても、押下保持そのものからは反応しないようにするため）。

        終了状態が立った瞬間に区画選択ポップアップを _reset_popup() で閉じる
        （決算タイマー満了時と同じ扱い）ことは**しない**。終了が立つ経路は
        建設・買収（_update_popup() の「o」押下の中。直後に CLOSING へ移る）と
        精算（決算タイマーの満了時に既に _reset_popup() 済み）だけで、
        いずれも終了の直後に区画選択ポップアップが描かれる状態にならないため
        （_is_selection_shown() は CLOSING と NONE のどちらも描かない）。

        ステータス右のスピードボタンの押下判定（_update_status_buttons()。
        ID-019 サイクル4）は、_update_popup() と同じ「通常時（settlement_
        popup_state が NONE）のみ」の枝に並べて呼ぶ——決算ポップアップ
        表示中・ゲーム終了中は反応しない（要件どおり）ことを、既存の3分岐
        を増やさずそのまま利用して表す。ステータス領域の押下は
        _screen_to_plot() が None を返すため区画選択には影響せず、
        _update_popup() と _update_status_buttons() は同じ押下・押下解除を
        独立に見るだけで競合しない"""
        if self._save_clock.is_up():
            self._save()
        if self._npc_growth_clock.is_up():
            self._field.grow_npc()
            self._check_business_continuation()
        if self._sales_clock.is_up():
            self._collect_sales()
        if self._settlement_clock.is_up():
            self._settlement_popup_state = SettlementPopupState.SHOWN
            self._reset_popup()
            for clock in self._freeze_clocks:
                clock.pause()
        down = self._input.is_mouse_btn_down()
        # 押下解除（前フレーム押下 → 今フレーム未押下）を押下保持から導出する。
        # 入力へ btnr 相当を足さずに済ませる
        released = self._bef_down and not down
        self._bef_down = down
        if self._game_end_state != GameEndState.NONE:
            self._update_game_end_popup(released)
            return
        if self._settlement_popup_state == SettlementPopupState.NONE:
            self._update_popup(down, released)
            self._update_status_buttons(released)
        else:
            self._update_settlement_popup(released)

    def _update_popup(self, down, released):
        """押下の状態からポップアップの対象区画・表示位置・状態（PopupState）を
        更新する。状態遷移図（NONE → TRACKING → MODAL → EXECUTED → MODAL /
        MODAL → CLOSING → NONE）と同じ順序で読める5分岐にしている。EXECUTED
        は「o」の実行直後（ID-022 決定1）だけが経由し、指が離れる
        （released）まではフィールドの押下を一切受け付けず、離れると
        CLOSING を経ずに MODAL へ直接戻る（非表示にしないため、閉じて
        から再び開く手順が要らない）。分岐を MODAL より手前に置くのは、
        「実行後の指の保持」を「固定表示中の押下」より先に判定させるため
        （EXECUTED は MODAL から一度しか遷移しないため、順序を入れ替えても
        振る舞いは変わらないが、状態遷移図の順で読める並びを優先する）。
        MODAL の間に自分で扱うのは**ポップアップの矩形の内側への押下だけ**で、
        内側なら続けてボタン矩形かを判定し（_update_popup_button_press()）、
        ボタン以外（余白・プレビュー領域）は何も起こさない——矩形に重なって
        いる区画も、ポップアップを閉じるまで選択できない（遮断）。矩形の
        **外側**への押下は自分では扱わず、下の共通の押下処理へそのまま委譲
        する（区画上ならその区画へ内容・表示位置・選択枠が切り替わって
        TRACKING へ戻り、区画外なら NONE ＝ ポップアップが閉じる）。委譲に
        例外を設けない（押下位置ごとの「通す／通さない」の表を持たない）
        ため、ステータス領域のボタンのように押下位置に固有の処理があれば、
        ポップアップが閉じたうえでそれも従来どおり働く。遮断を MODAL の分岐に
        だけ置くのは、追従中（TRACKING）はポップアップが常に押下位置と反対側の
        半分へ出るため、指がポップアップの矩形へ入ること自体が起こり得ない
        ためである（同じ遮断を TRACKING にも書くと、振る舞いとして観測できない
        分岐になる）。CLOSING の間はボタンを押した指が離れる
        （released）までフィールドの押下を一切受け付けず、離れて初めて NONE
        へ戻す（取りこぼし防止。ボタン押下から直接 NONE へ戻すと、指を離さず
        にフィールドへ移動しただけで同じ押下保持から新しい追従が始まって
        しまう。CLOSING を挟むことで、状態遷移のすべてを押下保持のレベル
        判定だけで書ける）。押下中は押下位置の区画へ毎フレーム追従し
        （区画外なら NONE のまま）、区画上で押下を解除したときに、その直前の
        フレームで追従していた値のまま MODAL へ固定する。それ以外（区画外
        での解除・未押下）は NONE へ戻す（取り消しの逃げ道）"""
        if self._popup_state == PopupState.EXECUTED:
            if released:
                self._popup_state = PopupState.MODAL
            return
        if self._popup_state == PopupState.MODAL:
            if not down:
                return
            x, y = self._input.get_mouse_pos()
            if self._point_in_popup(x, y):
                self._update_popup_button_press(x, y)
                return
            # ポップアップの矩形の外側は自分では扱わず、下の共通の押下処理へ
            # そのまま委譲する（区画上なら TRACKING、区画外なら NONE）
        if self._popup_state == PopupState.CLOSING:
            if released:
                self._reset_popup()
            return
        if down:
            x, y = self._input.get_mouse_pos()
            self._popup_plot = self._screen_to_plot(x, y)
            self._popup_x = self._popup_origin_x(x)
            self._popup_state = (
                PopupState.TRACKING if self._popup_plot is not None else PopupState.NONE
            )
        elif released and self._popup_state == PopupState.TRACKING:
            self._popup_state = PopupState.MODAL
        else:
            self._reset_popup()

    def _update_popup_button_press(self, x, y):
        """固定表示中（MODAL）にポップアップの矩形の**内側**が押されたときの
        処理。押下位置が「o」「x」いずれかのボタン矩形内であれば、押した
        ボタンに応じて行き先が分かれる（ID-022 決定1）。「o」は、選択中の
        区画がプレイヤー所有店舗なら増資を、NPC所有店舗なら買収を、空き
        区画なら建設を実行したうえで EXECUTED へ移り、ポップアップは表示
        したまま残す（続けて同じ区画へ実行できる。指を離すと MODAL へ戻る）。
        「x」は常にキャンセルで、実行せず CLOSING へ移りポップアップを
        非表示にする。ボタン以外（余白・プレビュー領域）への押下と、無効な
        ボタン（_is_popup_button_enabled() が False。資金不足のときの「o」）
        への押下は、どちらも何も起こさず MODAL のまま残す（閉じるには「x」を
        押す）。
        呼び出し元（_update_popup()）が矩形の内側であることを確かめた後に呼ぶ
        ため、本メソッドは「ポップアップの内側か → ボタンの内側か」という入れ子の
        内側だけを担う（ボタンの矩形はポップアップの矩形の部分集合である）"""
        index = self._popup_button_index_at(x, y)
        if index is None:
            return
        if not self._is_popup_button_enabled(index):
            return
        if index == self.POPUP_BTN_INDEX_O:
            # 区画の状態（空き／プレイヤー所有店舗／NPC所有店舗）で実行
            # 内容を分ける。_is_popup_button_enabled() も同じ3分岐を持つが、
            # 対応表（owner → (述語, 実行) の1箇所化）は採らないと判断した
            # （ID-009 TASK-009-10。区画の状態は空き／プレイヤー所有／
            # NPC所有の3つで閉じており増える予定がないこと、getattr等の
            # 間接層を挟むコストが「分岐を片方だけ足し忘れる」という低確率の
            # リスクを上回ると判断したことが理由）
            col, row = self._popup_plot
            owner = self._field.get_owner(col, row)
            if owner == Owner.PLAYER:
                self._invest_selected_plot()
            elif owner == Owner.NPC:
                self._buyout_selected_plot()
            else:
                self._build_selected_plot()
            self._popup_state = PopupState.EXECUTED
        else:
            self._popup_state = PopupState.CLOSING

    def _update_settlement_popup(self, released):
        """決算ポップアップの状態が NONE でない間（SHOWN）に呼ばれ、押下
        解除から精算を更新する。区画選択ポップアップと違い、押下位置への
        追従は無く、「o」ボタン1つに対する押下解除の有無だけを見る。

        押下の対象を**ポップアップの矩形全体から「o」ボタンへ絞った**のは
        サイクル5の Refactor での再考（ユーザー指摘による）: ポップアップの
        矩形全体をタップ対象にすると、見た目からは「タップして閉じる」ことが
        読み取れない。区画選択ポップアップと同じ「押せるボタン」の形にする
        ことで、精算の実行が視覚的に読み取れるようにした。

        実行の契機を**押下（down）ではなく押下解除（released）**にしたのは
        ID-018 のプレイテストで見つかった不具合の修正（未確定事項1の候補Aを
        改めた）: 押下の瞬間に実行していた旧実装では、この「o」を離さない
        まま決算ポップアップが閉じて終了ポップアップが現れても、同じ押下
        保持が次フレームでそのまま終了ポップアップ側の「o」判定へ流れ込み、
        終了ポップアップが画面に見えないままリセットされてしまっていた
        （_update_game_end_popup() も参照）。released（指がボタンの矩形内で
        離れた瞬間）を契機にすれば、実行される時点で押下は必ずもう終わって
        いるため、この巻き込みが起こらない。矩形外（ボタン以外のポップアップの
        余白を含む）での押下解除は無視して SHOWN のまま留まる（設計判断の
        とおり、精算せず閉じない）。押下解除が無ければ何もしない（区画選択の
        「o」「x」と異なり、SHOWN のまま待ち続けるだけで自然に消える受け皿は
        無い——決算ポップアップは「o」ボタンの押下解除でしか閉じない）。

        実行と同じ行で状態を直接 NONE へ戻し、CLOSING 相当の中継状態を
        持たない: released を契機にした時点で押下はもう終わっているため、
        区画選択ポップアップの CLOSING が担っていた「取りこぼし防止（指を
        離さずフィールドへ移動しても新しい操作が始まらない）」は、実行の
        タイミングそのものによって自動的に満たされている（SettlementPopupState
        の docstring を参照）"""
        if not released:
            return
        x, y = self._input.get_mouse_pos()
        if not self._point_in_rect(x, y, *self._settlement_popup_button_rect()):
            return
        self._settle_tax()
        self._settlement_popup_state = SettlementPopupState.NONE

    def _update_game_end_popup(self, released):
        """終了（クリア／ゲームオーバー）ポップアップの表示中に、押下解除
        から needs_reset を更新する（ID-018）。_update_settlement_popup() と
        同じく「o」ボタン1つに対する押下解除の有無だけを見る。

        当初は押下（down）の瞬間に needs_reset を立てていた——needs_reset が
        立った時点でこの GameCore インスタンスは次フレームで App により
        丸ごと差し替えられるため、「押下後に指が離れるまで待つ」処理は
        差し替え後の新しいインスタンスには意味を持たない、という判断
        （TASK-018-7）による。しかしプレイテストで、決算ポップアップの
        「o」を離さないまま精算が成立して終了ポップアップが現れると、
        その同じ押下保持が**このメソッド自身**への入力としてそのまま
        続いてしまい、ユーザーが終了ポップアップを目にする前に
        needs_reset が立ってリセットされる不具合が見つかった。旧実装の
        判断は「差し替え後の新しいインスタンスに対する待機は無意味」という
        点では正しいが、「差し替え前のこのインスタンスに対しても、押下の
        瞬間に反応してよい」という前提が誤りだった——終了ポップアップが
        現れた時点で既に継続中だった押下は、終了ポップアップに対する
        ユーザーの意思表示ではない。released を契機にすることで、終了
        ポップアップが現れる前から続いていた押下ではなく、現れた後に
        ユーザーが改めて押して離した押下解除だけに反応する
        （_update_settlement_popup() の docstring も参照）。

        _point_in_rect() 単独の判定に、指を離すまでのガードを追加しない
        （TASK-018-7 再確認）: リセット直後も指が置かれたままだと、
        差し替え後の新しい GameCore の _update_popup() が同じ座標を
        down=True として受け取り、終了ポップアップの位置と重なる区画が
        TRACKING になり得る。しかし TRACKING は区画へ追従するだけで
        建設等の副作用を持たず、MODAL 化して「o」ボタンを押すという
        別操作を経なければ何も実行されない。このメソッド（旧 GameCore の
        needs_reset を立てるだけの役割）にガードを足しても、次に生まれる
        新しい GameCore の状態には関与できない（別インスタンスのため）
        ため、ここに足す理由が無いと判断した。実機での見え方は
        TASK-018-12 プレイテストで確認する"""
        if not released:
            return
        x, y = self._input.get_mouse_pos()
        if not self._point_in_rect(x, y, *self._game_end_popup_button_rect()):
            return
        self._needs_reset = True

    def _update_status_buttons(self, released):
        """ステータス右の2つのボタン（ポーズ「||」・スピード「>」系）の
        押下解除を扱う。スピードボタンは段階を1つ進め、他店建設・売上・
        決算の3タイマーへ反映する（ID-019 サイクル4・5）。ポーズボタンは
        ポーズの開始・解除を切り替える（サイクル6。下記）。
        _update_settlement_popup() / _update_game_end_popup() と同じ形——
        押下解除（released）を契機に、その位置がボタンの矩形内かどうかだけを
        見る。呼び出し元（update()）が通常時（決算ポップアップ表示中・
        ゲーム終了中でない）だけこのメソッドを呼ぶため、ここでは状態を
        確認しない。

        段階は GAME_SPEED_STEPS の添字（self._speed_index）で表し、
        (index + 1) % len(GAME_SPEED_STEPS) で循環する——最高速の次は
        最低速へ戻る（要件どおり）。段階そのものは _draw_status_buttons() が
        描くラベルを通してのみ外から観測できる（設計方針1。段階を直接読む
        テストは作らない）。段階の切り替えに続けて _apply_speed_to_timers()
        を呼び、3タイマーの待機時間・残り時間を新しい段階へそろえる
        （サイクル5）。

        ポーズボタン「||」の押下解除でポーズへ入り、ポーズ中はどちらの
        ボタン（ポーズ・スピードのいずれ）を押下解除してもポーズを解除
        する（段階は進めない。設計方針6-1の表・ID-019 サイクル6）。
        押下位置がどちらの矩形にも入っていなければ何もしない（回帰。
        矩形外での押下解除では反応しない）。

        判定は「まずどちらかの矩形内かどうか」→「ポーズ中なら押された
        矩形によらず解除する／通常時のみ、押された矩形に応じてポーズへ
        入る・段階を進める」という2段の形にまとめている（設計方針6-1・
        ID-019_subtasks.md）。ポーズ中はスピードボタンの矩形内であっても
        段階を進める分岐へは進まない——「ポーズ中にスピードを切り替える」
        経路がそもそも存在しないため、段階はポーズ前のまま保たれる（退避
        を持たなくてよい理由もここにある）。4通り（押したボタン×ポーズ
        の有無）を個別に分岐せずに済んでいる。

        **ポーズは self._paused を切り替えるだけでなく、実際に4つの
        タイマー（self._freeze_clocks。保存・他店建設・売上・決算。決算・
        終了の凍結と対象を揃える。設計方針4）を止め・再開する（ID-019
        サイクル7）**。ポーズへ入る側（in_pause の分岐）は pause() を
        その場で呼び切る——決算満了時の完全凍結（update() を参照）と同じ
        「契機が起きたその場で1回だけ呼ぶ」形。ポーズを解除する側は
        self._resume_clocks() を経由する（生の resume() ループを直接
        書かない）。理由は _settle_tax() も同じ凍結解除を行うため:
        両者が別々に「再開してよいか」を判断すると、どちらか一方だけが
        ポーズを見落とす経路を実装上作れてしまう。ここでは
        self._paused を先に False へ落としてから呼ぶため、
        self._resume_clocks() は素通りしてそのまま4つを再開する
        （_resume_clocks() のガードが効くのは _settle_tax() 側だけ）"""
        if not released:
            return
        x, y = self._input.get_mouse_pos()
        in_pause = self._point_in_rect(x, y, *self._status_pause_button_rect())
        in_speed = self._point_in_rect(x, y, *self._status_speed_button_rect())
        if not (in_pause or in_speed):
            return
        if self._paused:
            self._paused = False
            self._resume_clocks()
            return
        if in_pause:
            self._paused = True
            for clock in self._freeze_clocks:
                clock.pause()
            return
        self._speed_index = (self._speed_index + 1) % len(self.GAME_SPEED_STEPS)
        self._apply_speed_to_timers()

    def _resume_clocks(self):
        """凍結解除の窓口（ID-019 サイクル7）。self._paused でなければ
        self._freeze_clocks（保存・他店建設・売上・決算の4件）を再開する。
        ポーズ中はここで何もしない——決算の精算（_settle_tax()）による
        resume() が、ユーザーがポーズ中であっても時間を動かしてしまう
        組み合わせ（設計方針4）を、この1箇所で防ぐ。ポーズボタンによる
        解除（_update_status_buttons()）はこのメソッドを呼ぶ**前に**
        self._paused を False へ落とすため、そちらは実際に再開される"""
        if self._paused:
            return
        for clock in self._freeze_clocks:
            clock.resume()

    def _apply_speed_to_timers(self):
        """現在のスピード段階（self._speed_index）を、他店建設・売上・決算の
        3タイマーへ反映する（ID-019 サイクル5）。対象は開始をまとめる一覧
        self._shop_clocks と同じ3件（保存タイマー _save_clock は
        要件 3.12 に列挙されていないため対象外——_freeze_clocks の4件とは
        対象がずれる）。基準の間隔（等倍時の値。NPC_GROWTH_INTERVAL_MS 等）を
        段階の除数で割った値を Clock.change_count_ms() へそのまま渡すことで、
        待機時間の差し替えと残り時間の比例スケールを1回の呼び出しで行う
        （ShopClock.change_count_ms() 経由。未開始のタイマーでも
        壊れない）。割り切れない場合は整数へ切り捨てる（設計方針2。
        ID-019_subtasks.md）"""
        _, divisor = self.GAME_SPEED_STEPS[self._speed_index]
        base_intervals_ms = (
            self.NPC_GROWTH_INTERVAL_MS,
            self.SALES_INTERVAL_MS,
            self.SETTLEMENT_INTERVAL_MS,
        )
        for clock, base_interval_ms in zip(self._shop_clocks, base_intervals_ms):
            clock.change_count_ms(base_interval_ms // divisor)

    def _status_speed_button_rect(self):
        """ステータス右のスピードボタン「>」系の矩形 (x, y, w, h) を返す。
        押下判定（_update_status_buttons()）と描画（_draw_status_buttons()）の
        両方がこの1つの式を経由することで、片方だけレイアウト変更に
        追従し損なうことを防ぐ（_popup_button_rect() と同じ考え方）"""
        speed_x = self.STATUS_X + self.STATUS_W - self.STATUS_PAD - self.STATUS_BTN_W
        btn_y = self.STATUS_Y + (self.STATUS_H - self.STATUS_BTN_H) // 2
        return speed_x, btn_y, self.STATUS_BTN_W, self.STATUS_BTN_H

    def _status_pause_button_rect(self):
        """ステータス右のポーズボタン「||」の矩形 (x, y, w, h) を返す
        （ID-019 サイクル6）。スピードボタンの矩形（_status_speed_button_
        rect()）から STATUS_BTN_GAP・STATUS_BTN_W ぶん左の位置——
        _draw_status_buttons() が並べる順（ポーズ → スピード）と同じ式を
        1箇所に持つことで、押下判定（_update_status_buttons()）と描画の
        両方がこれを経由し、片方だけレイアウト変更に追従し損なうことを
        防ぐ（_status_speed_button_rect() と同じ考え方）"""
        speed_x, btn_y, btn_w, btn_h = self._status_speed_button_rect()
        pause_x = speed_x - self.STATUS_BTN_GAP - self.STATUS_BTN_W
        return pause_x, btn_y, btn_w, btn_h

    def _settle_tax(self):
        """決算ポップアップの精算を実行する: 表示されていた税額
        （Field.total_tax()）を資金から引き、引いた結果が負なら不足額ぶんの
        売却（ID-016）を Field へ委ね、調達できた額を資金へ足し、凍結して
        いた4つのタイマーを再開し（self._resume_clocks()。pause() と対称の
        形。update() の docstring を参照）、ゲームオーバー・クリアのいずれも
        成立していなければ直後に保存する（self._save()。いずれかが成立した
        ときは保存せず、代わりに _end_game() が終了状態を立てて4つの
        タイマーを凍結し直す。理由は下記）。

        **ポーズ中は再開されない（ID-019 サイクル7）**: 決算ポップアップが
        表示されている間はステータスのポーズボタンが反応しないため
        （_update_status_buttons() は settlement_popup_state が NONE の
        間しか呼ばれない）、通常の操作で「表示中に新たにポーズへ入る」
        経路は無い。それでも self._resume_clocks() へ窓口を1本化したのは、
        ポーズの開始・解除（_update_status_buttons()）と精算のいずれもが
        「凍結を解いてよいか」を毎回自分で判断する形にすると、判断が2箇所に
        散り、片方だけがポーズを見落とす経路を実装上作れてしまうため
        （設計方針4）。self._resume_clocks() は self._paused を1箇所だけで
        確認し、真なら何もしない——精算の resume() がユーザーのポーズ操作を
        踏み越えて時間を動かしてしまう組み合わせを防ぐ。

        _build_selected_plot() / _invest_selected_plot() /
        _buyout_selected_plot() と異なり、**可否条件を自分で確認しない**
        （常に実行する）。この非対称は本質的な違いに基づく: あちらは
        「資金が足りなければ実行しない」建設・増資・買収の可否判定を持つが、
        精算は「資金が足りなくても引き、資金をマイナスにする」という設計
        判断（ID-015）そのものが可否条件の不在を要求する。
        資金を減らす式（`self._money -= tax`）は _draw_settlement_popup_
        values() の「減算後 = 減算前 − 税額」と同じ式であり、表示された額と
        実際に引かれる額が食い違う経路を作らない。両者が同じ
        Field.total_tax() を読んでおり、かつ表示中（SHOWN の間）は完全凍結
        （サイクル4）により盤面が変わらないため、表示された税額と精算時に
        読み直す税額は必ず一致する（完全凍結を選んだことの副次的な利点）。

        **不足時の売却（ID-016）**: `self._money -= tax` の結果が負に
        なった場合のみ（`self._money < 0`）、その絶対値（`-self._money`）を
        不足額として `Field.sell_shops_for_shortfall()` へ渡し、返った
        調達額を資金へ足す（`self._money += ...`）。資金が税額を上回る・
        ちょうど一致する（減算後が0になる）場合はいずれも呼ばない——
        `self._money < 0` という1つの判定が「不足しているか」と「いくら
        不足しているか（絶対値）」の両方を兼ねる。判定・呼び出し・加算の
        3点が `GameCore` の役割のすべてで、対象の列挙・抽選・NPC所有化・
        繰り返しと停止条件・**不足額を満たせたかの判定（`Field.
        shortfall_covered` プロパティが答える）**はいずれも `Field` の
        内側に閉じており `GameCore` は関知しない（案6・ID-017 案2）。
        売却の中身の検証は `test_field.py` の
        `TestFieldSellShopsForShortfall` が担い、本メソッドのテスト
        （`test_main_popup.py` の `TestSettlementPopupSellsShortfall`）は
        「呼ばれる条件・引数・戻り値の反映」の3点のみを、`Field` を
        スタブにして確認する（案8）。

        **ゲームオーバーの判定（ID-017 サイクル3）**: 売却を行った
        （`self._money < 0` だった）ときだけ `self._field.shortfall_covered`
        を読み、偽（満たせなかった）なら終了状態を GAME_OVER へ写す。
        資金が税額を上回る・ちょうど一致する場合は売却そのものを呼ばない
        ため `shortfall_covered` も読まない（前回の売却の結果が残っていて
        誤って読まれることを避ける。「不足していなければ判定もしない」と
        いう、売却を呼ぶかどうかの条件とまったく同じ境界）。判定結果は
        ローカル変数 `game_over` に一度だけ控え、凍結解除（resume()）の
        **後**で終了状態へ反映する——凍結の再開そのものは精算の一部として
        必ず行い（下記「タイマーの凍結・再開」を参照）、その後で終了状態を
        書くかどうかを分ける、という順序にした。
        **resume() してから改めて pause() し直す**（ゲームオーバーなら
        resume() を飛ばす形は採らない。ID-017 サイクル4）。理由は、決算
        ポップアップの凍結と終了の凍結が**別々の理由による別々の凍結**
        だから: 前者は「決算ポップアップの表示中である」ことに対応し、
        精算した時点でその理由は必ず消える（update() の docstring が述べる
        「閉じたのに凍結だけ残る状態を実装上作れないようにする」形を、
        ゲームオーバーの場合にだけ崩さない）。後者は「ゲームが終わった」
        ことに対応する新しい凍結であり、_end_game() が掛け直す。resume() を
        条件付きで飛ばす形にすると、1つの resume() が2つの理由を兼ねること
        になり、「決算の凍結は必ず解ける」という不変が読めなくなる。
        終了状態への反映と保存の両方に関与するのは `GameCore` 側の
        「`Field` が返した答えを写す」役割のみで、「何軒売れば足りたのか」
        「なぜ止まったのか」には一切関知しない（案2）。

        **クリアの判定（要件 3.16。ID-028 サイクル028-2）**: ゲームオーバーの
        判定・`_end_game(GAME_OVER)` の**後**——ゲームオーバーが成立して
        いれば return 済みのため、ここへ到達するのはゲームオーバーが不成立の
        ときだけ——で `self._field.is_clear_shop_count_reached` を読み、真なら
        終了状態を CLEAR へ写す。読むのは常に**売却まで終わった後**（`self.
        _resume_clocks()` の後、かつ売却が起きたかどうかによらず毎回）であり、
        ゲームオーバーの判定（売却を行ったときだけ `shortfall_covered` を
        読む）とは対称ではない——クリアの側には「売却を呼んだかどうか」で
        読む・読まないを分ける理由が無く、`is_clear_shop_count_reached` は
        Field の内部状態を都度算出するだけの読み取り専用プロパティのため、
        何度読んでも副作用も食い違いも無い（ID-028_subtasks.md 決定2）。
        **この位置（売却の後）に置くことで、「決算時の店舗売却によって
        規定店舗数を下回った場合はクリアにならない」（要件 3.16）が専用の
        条件式を1行も書かずに成立する**——売却で `player_shop_count` が
        既に減った後の値を読むため（`Field._sell_player_shop()` の
        docstring を参照）。ゲームオーバーとの判定順序を**ゲームオーバー
        優先**で固定したのは、両者が同時に成立し得ないという不変
        （`GameEndState` の docstring。`CLEAR_SHOP_COUNT >= 1` である限り
        0軒＝ゲームオーバーと規定数以上＝クリアは両立しない）を、順序を
        暗黙にせず明示するため（ID-024 が3つ目の終了判定——事業継続による
        ゲームオーバー——を同じ契機へ、下記のとおり1件差し込む形で実現した）。
        ゲームオーバーと異なりローカル変数へ結果を控えない——`resume()` の
        前後で分岐する必要が無く（クリアが `self._money` の符号にもポーズ
        にも関与しない）、`if` の条件式で直接読んでも「凍結解除の後で
        終了状態を反映する」という順序は崩れない。

        **事業継続の判定（要件 3.15。ID-024 決定4-A）**: ID-017 の
        ゲームオーバーの判定・`_end_game(GAME_OVER)` の**直後**、クリアの
        判定の**前**で `self._check_business_continuation()` を呼び、真
        （事業を再開する手段が無いと判定してゲームオーバーを成立させた）
        なら return する。ID-017 のゲームオーバーが既に成立していれば
        return 済みのため、ここへ到達するのは ID-017 側が不成立のときだけ
        であり、`Field.min_acquisition_cost()`（盤面全体を走査する）は
        ID-017 側が成立するケースでは一度も呼ばれない（決定5。両者には
        包含関係があり——ID-017 が成立するとき、盤面は必ず0軒・資金は必ず
        最小取得費用未満になるため事業継続の判定も必ず成立する——先に
        成立した判定がそのまま結果を決めれば足り、後から重ねて判定し直す
        必要は無い。この「先に成立した判定が後続の呼び出しを完全に止める」
        ことは `test_main_popup.py` の
        `TestSettlementTriggersBusinessContinuationCheck.
        test_existing_game_over_takes_precedence_and_skips_the_min_
        acquisition_cost_lookup` が、`min_acquisition_cost()` の呼び出しの
        有無という観測可能な形で固定する）。クリアより前に置くのは、事業
        継続とクリアも同時に成立し得ない（事業継続は0軒、クリアは
        `CLEAR_SHOP_COUNT` 軒以上）という同じ不変に基づき、他店建設間隔
        ごとの建設・増資の直後（`update()`）と呼び出し方を揃えるため
        （`_check_business_continuation()` 自身の docstring を参照）。

        **税額を読み直さないこと（案1）**: 売却が繰り返される間も
        `Field.total_tax()` は一度も呼ばれない——「税金を納めてから、
        売却する」という順序であり、売却は納税額を交渉し直す行為ではない
        ため。`sell_shops_for_shortfall()` が不足額を**引数**で受け取る
        形（`self._money` の符号を渡すのではなく、その絶対値を渡す）である
        ため、売却の内側から税額を導く経路がそもそも存在しない。「読み
        直さない」という規律を守るのではなく、構造的に読めない形にして
        いる。

        保存は建設・増資・買収と同じ「プレイヤーの操作由来の変更は直後に
        保存する」扱い。凍結中は定期保存（_save_clock）も止まっているため、
        ここで保存しないと精算が保存データへ載らない（凍結を解いた後の
        次の保存間隔まで、精算が保存されないまま残ってしまう）。売却の
        呼び出しは保存より前に置くため、売却後の盤面・資金がそのまま
        保存される。**ただしゲームオーバー・クリアのいずれかが成立した
        ときは、この保存を呼ばずに戻る**（終了を成立させた操作は保存を
        省くという申し送り。ID-017 サイクル2完了時にゲームオーバー側で
        確立し、ID-028_subtasks.md 決定3でクリア側にも適用した。理由:
        終了状態そのものは保存しない方針（_end_game() の docstring・案3）の
        もとで通常どおり保存してしまうと、盤面・資金だけが「終了している」
        状態で保存され、終了ポップアップが一度も出せないまま出す手段が
        無くなる詰みが生まれ得る——保存を省くことで、その間にリロードが
        起きても直前の（終了していない）状態へ戻るだけになり、終了を
        成立させる操作をやり直せる）。

        盤面（Field）が変わるのは不足時の売却が起きたときだけで、資金が
        足りている間は変わらない（税の支払いだけで店舗を減らす経路は無い）。

        **ID-016 からの申し送りを反転させた経緯**: ID-016 時点では「売る
        店舗が尽きてもなお資金が負のままかどうかは、本メソッドの実行後の
        `self._money` の符号がそのまま表すため、`sell_shops_for_shortfall()`
        の戻り値を別途保持する必要はない」という申し送りだった。ID-017 で
        その符号がゲームオーバーという業務上の判定になることが分かり、
        判定そのものを `Field` の内側に閉じる形へ反転させた。判定結果は
        `sell_shops_for_shortfall()` の戻り値ではなく、`Field` が持つ
        `shortfall_covered` プロパティ越しに読む（コマンドとクエリを分離し、
        `sell_shops_for_shortfall()` を「不足額ぶんを売却し、調達額を返す」
        という単一の機能に保つため。詳細は `Field.sell_shops_for_shortfall()`
        / `Field.shortfall_covered` の docstring を参照）。"""
        self._money -= self._field.total_tax()
        game_over = False
        if self._money < 0:
            self._money += self._field.sell_shops_for_shortfall(-self._money)
            game_over = not self._field.shortfall_covered
        self._resume_clocks()
        if game_over:
            self._end_game(GameEndState.GAME_OVER)
            return
        if self._check_business_continuation():
            return
        if self._field.is_clear_shop_count_reached:
            self._end_game(GameEndState.CLEAR)
            return
        self._save()

    def _settlement_popup_button_rect(self):
        """決算ポップアップ内の「o」ボタンの矩形 (x, y, w, h) を返す。数値3行
        （SETTLEMENT_POPUP_PAD + 3 × SETTLEMENT_POPUP_LINE_H +
        SETTLEMENT_POPUP_RULE_TEXT_GAP。3行目を横線から離すぶんの余白を
        含む）の直後に、内側余白 SETTLEMENT_POPUP_PAD を挟んで置く。区画選択
        ポップアップの _popup_button_rect() と同じく、押下判定
        （_update_settlement_popup()）と描画（_draw_settlement_popup_button()）
        の両方がこの1つの式を経由することで、片方だけレイアウト変更に
        追従し損なうことを防ぐ"""
        btn_x = self.SETTLEMENT_POPUP_X + self.SETTLEMENT_POPUP_PAD
        btn_y = (
            self.SETTLEMENT_POPUP_Y
            + self.SETTLEMENT_POPUP_PAD
            + 3 * self.SETTLEMENT_POPUP_LINE_H
            + self.SETTLEMENT_POPUP_RULE_TEXT_GAP
            + self.SETTLEMENT_POPUP_PAD
        )
        return btn_x, btn_y, self.SETTLEMENT_POPUP_BTN_W, self.SETTLEMENT_POPUP_BTN_H

    def _cost_covered(self):
        """選択中の区画の費用（Field.get_cost()）を、いまの資金で賄えるかを
        返す（`資金 >= 費用` の比較）。区画の状態（空き／プレイヤー所有）に
        よらず同じ比較のため、_build_possible() / _invest_possible() の
        双方から呼ばれる1箇所に一本化する。資金の比較（`>=`）を複数箇所に
        書くと、一方だけ境界の書き方（`>` と `>=` の取り違えなど）がずれる
        経路を実装上作れてしまう（ID-006 で _build_possible() に一本化した
        判断を、増資が2件目の呼び手として現れたためさらに1段くくり出した）。
        **費用が存在する（get_cost() が数値を返す）ことを前提にする**。費用が
        存在しないのは規模が上限のプレイヤー所有店舗だけで、その1件は
        _invest_possible() が本メソッドより前に打ち切る（同メソッドの
        docstring を参照）ため、ここには数値だけが届く"""
        col, row = self._popup_plot
        return self._money >= self._field.get_cost(col, row)

    def _build_possible(self):
        """選択中の区画に、いま実際に建設できるかを返す（空き区画かつ資金が
        設置費用以上）。「建設できるか」という業務上の判定はここに一本化する
        （資金の比較そのものは _cost_covered() に一本化している）。店舗のある
        区画は増資・買収の対象であり本メソッドの言う「建設」には当たらない
        ため、常に `False`（「o」を常に有効にする判断は
        `_is_popup_button_enabled()` 側が別に行う）"""
        col, row = self._popup_plot
        if self._field.get_owner(col, row) is not None:
            return False
        return self._cost_covered()

    def _invest_possible(self):
        """選択中の区画に、いま実際に増資できるかを返す（プレイヤー所有店舗かつ
        店舗規模が上限未満かつ資金が増資費用以上）。「増資できるか」という
        業務上の判定はここに一本化する（資金の比較そのものは _build_possible()
        と同じ _cost_covered() を読む）。
        判定材料（所有者・店舗規模）はいずれも区画・店舗の状態で、資金だけが
        GameCore の持ち物という非対称があるが、「増資できるか」という1つの
        真偽値へ畳むこと自体は変わらないため、両者を同じメソッドの中で並べて
        判定する（呼び出し元は理由を区別せず、押下判定・無効表示のいずれも
        この1つの結果だけを読む）。
        **3つの判定の順序には意味がある**——規模が上限のプレイヤー所有店舗は
        増資費用が存在せず（Field.get_cost() が None を返す。要件 3.6）、
        資金と比較できない。規模の判定を _cost_covered() より**前**に置く
        ことで、比較する相手が無い状態のまま _cost_covered() へ進む経路を
        作らない。順序を入れ替えてはならない（規模上限の判定を
        _cost_covered() 側へ重ねて持たせないのは、「増資できるか」の判定を
        2箇所に散らさないため。資金を賄えるかだけを見るのが
        _cost_covered() の役割で、費用の不在はその問いの外にある）"""
        col, row = self._popup_plot
        if self._field.get_owner(col, row) != Owner.PLAYER:
            return False
        if self._field.get_scale(col, row) >= self.SHOP_SCALE_MAX:
            return False
        return self._cost_covered()

    def _buyout_possible(self):
        """選択中の区画に、いま実際に買収できるかを返す（NPC所有店舗かつ資金が
        買収費用以上）。「買収できるか」という業務上の判定はここに一本化する
        （資金の比較そのものは _build_possible() / _invest_possible() と同じ
        _cost_covered() を読む）。買収の可否条件は資金のみで店舗規模を問わない
        （要件 3.7）ため、_invest_possible() のような規模の判定は持たない
        （規模10の店舗も買収でき、買収後の増資は _invest_possible() の上限
        判定が自動的に効く）"""
        col, row = self._popup_plot
        if self._field.get_owner(col, row) != Owner.NPC:
            return False
        return self._cost_covered()

    def _is_popup_button_enabled(self, index):
        """index 番目のボタンを、押下判定・表示のいずれにおいても有効として
        扱ってよいかを返す。押下判定（_update_popup()）と無効表示
        （_draw_popup_buttons()）が**同じ本メソッドを読む**ことで、
        「見た目は押せそうなのに押せない」「見た目は無効なのに押せる」を
        実装上作れないようにしている（_is_selection_shown() を選択枠と
        ポップアップで共有しているのと同じ考え方）。
        「x」（キャンセル）は常に有効。「o」（実行）は区画の状態で判定が
        分かれる：空き区画は _build_possible()、プレイヤー所有店舗は
        _invest_possible()（資金不足のときだけ無効。ID-007）、NPC所有店舗は
        _buyout_possible()（資金不足のときだけ無効。ID-009）"""
        if index != self.POPUP_BTN_INDEX_O:
            return True
        col, row = self._popup_plot
        owner = self._field.get_owner(col, row)
        if owner is None:
            return self._build_possible()
        if owner == Owner.PLAYER:
            return self._invest_possible()
        return self._buyout_possible()

    def _build_selected_plot(self):
        """選択中の区画へ、プレイヤー所有・最小規模の店舗を建設し、資金から
        設置費用を引く。呼び出し元（_update_popup()）は、選択中の区画が
        空き区画であることを確認した上で本メソッドを呼ぶが、呼び出し側の
        保証に頼らず _build_possible() を自分でも確認する（建設が実行される
        条件をここでも保証する。_invest_selected_plot() /
        _buyout_selected_plot() と同じ形）。
        区画の状態変更は Field、資金は GameCore の持ち物であり、建設は両方に
        またがる操作のため、両者を呼ぶ側であるここに置く。
        設置費用はポップアップに表示されているものと同じ Field.get_cost() から
        得るため、**見えている数字がそのまま引かれる**。設置すると同じ区画の
        費用は増資費用へ変わるので、設置の前に読んでおく。ゲームデータが
        変わったので、建設の直後に保存する。
        建設は**空の盤面へ最初の1軒が現れ得る経路**（ID-025。他に区画に
        店舗を生む経路は買収のみで、買収の対象はマップ上に既に店舗がある
        NPC所有店舗のため、空の盤面から最初の1軒を生むのは建設だけ）の
        ため、起点を共有するタイマー（他店建設間隔・売上発生間隔）の起動を
        試みる（既に起動済みなら何も起きない。開始条件そのものは
        _start_shop_clocks() が持ち、ここは呼ぶだけ。タイマーが増えても
        ここは変わらない）。

        **建設だけではゲームクリアは成立しない**（ID-028。かつては全区画が
        プレイヤー所有になった時点でクリアとしていたが、要件 3.16 により
        「規定店舗数へ到達し、その状態で決算を通過する」へ変更された。
        判定は `Field.is_clear_shop_count_reached` を読む `GameCore.
        _settle_tax()` の末尾——決算の精算完了直後——のみで行い、建設の
        直後には行わない。設置された区画の分だけ資金を減らし、常に
        self._save() を呼んで戻る"""
        if not self._build_possible():
            return
        col, row = self._popup_plot
        cost = self._field.get_cost(col, row)
        self._field.set_shop(col, row, Owner.PLAYER)
        self._money -= cost
        self._start_shop_clocks()
        self._save()

    def _invest_selected_plot(self):
        """選択中の区画（プレイヤー所有店舗）へ増資し、資金から増資費用を引く。
        呼び出し元（_update_popup()）は、選択中の区画がプレイヤー所有店舗で
        資金が増資費用以上であることを _is_popup_button_enabled() 経由で
        確認した上で本メソッドを呼ぶが、呼び出し側の保証に頼らず
        _invest_possible() を自分でも確認する（_build_selected_plot() が
        _build_possible() を自分でも確認しているのと同じ、同じ1つの述語に
        揃える形）。
        店舗規模の変更と資産価値への加算は Field.invest_shop()（実体は
        Shop.invest()）が担う店舗自身の状態変更のため Field 側の責務、
        資金は GameCore の持ち物であり、増資は両方にまたがる操作のため、
        両者を呼ぶ側であるここに置く（_build_selected_plot() と同じ形）。
        増資費用はポップアップに表示されているものと同じ Field.get_cost() から
        得るため、**見えている数字がそのまま引かれる**。増資すると同じ区画の
        費用は次の規模の額へ変わるので、増資の前に読んでおく（設置と同じ
        順序依存）。冒頭の _invest_possible() が規模上限を弾いた後に読むため、
        ここで得る費用は必ず数値になる（規模が上限だと費用は存在せず None が
        返る。要件 3.6）。ゲームデータが変わったので、増資の直後に保存する"""
        if not self._invest_possible():
            return
        col, row = self._popup_plot
        cost = self._field.get_cost(col, row)
        self._field.invest_shop(col, row)
        self._money -= cost
        self._save()

    def _buyout_selected_plot(self):
        """選択中の区画（NPC所有店舗）を買収し、資金から買収費用を引く。
        呼び出し元（_update_popup()）は、選択中の区画がNPC所有店舗で資金が
        買収費用以上であることを _is_popup_button_enabled() 経由で確認した
        上で本メソッドを呼ぶが、呼び出し側の保証に頼らず _buyout_possible() を
        自分でも確認する（_build_selected_plot() / _invest_selected_plot() が
        それぞれ自分の可否述語を確認しているのと同じ、同じ1つの述語に揃える
        形。ID-009 サイクル2の時点では可否の述語がまだ無かったため確認して
        いなかったが、サイクル3で _buyout_possible() を追加したことで対称に
        なった）。
        所有者の変更は Field.buyout_shop()（実体は Shop.buyout()）が担う
        店舗自身の状態変更のため Field 側の責務、資金は GameCore の持ち物で
        あり、買収は両方にまたがる操作のため、両者を呼ぶ側であるここに置く
        （_build_selected_plot() / _invest_selected_plot() と同じ形）。
        買収費用はポップアップに表示されているものと同じ Field.get_cost() から
        得るため、**見えている数字がそのまま引かれる**。買収すると同じ区画の
        費用は増資費用へ変わるので、買収の前に読んでおく。ゲームデータが
        変わったので、買収の直後に保存する。

        **買収だけではゲームクリアは成立しない**（_build_selected_plot() と
        対になる。理由は同じそちらの docstring を参照）"""
        if not self._buyout_possible():
            return
        col, row = self._popup_plot
        cost = self._field.get_cost(col, row)
        self._field.buyout_shop(col, row)
        self._money -= cost
        self._save()

    def _reset_popup(self):
        """選択中の区画・表示位置・状態をすべて「なし」（PopupState.NONE）へ戻す。
        区画外での解除（取り消し）と、CLOSING（「o」「x」ボタン押下で終了した後、
        押下が解除された）の両方から呼ばれる共通処理"""
        self._popup_plot = None
        self._popup_x = None
        self._popup_state = PopupState.NONE

    def _popup_button_index_at(self, x, y):
        """画面座標 (x, y) が「o」（index 0）／「x」（index 1）いずれかのボタン
        矩形内にあればそのインデックスを、どちらでもなければ None を返す。
        矩形は _popup_button_rect()（描画と共通）から導くため、片方だけが
        レイアウト変更に追従し損なうことはない"""
        for index in range(len(self.POPUP_BTN_ICONS)):
            rect = self._popup_button_rect(self._popup_x, self.POPUP_Y, index)
            if self._point_in_rect(x, y, *rect):
                return index
        return None

    def _point_in_popup(self, x, y):
        """画面座標 (x, y) が、表示中のポップアップの矩形の内側にあるかを返す。
        矩形は描画（_draw_popup()）と同じ定数の組（原点 (_popup_x, POPUP_Y)、
        大きさ POPUP_W × POPUP_H）から導くため、押下判定と描画の片方だけが
        レイアウト変更に追従し損なうことはない（_popup_button_rect() が描画と
        押下判定で共有されているのと同じ形）。
        ボタンの矩形（_popup_button_index_at()）はこの矩形の部分集合であり、
        _update_popup() は「ポップアップの内側か → ボタンの内側か」という入れ子の
        順序で押下位置を絞り込む。順序が逆だと、ポップアップに重なっている区画が
        先に選ばれてしまう（要件「ポップアップに重なっている区画は、ポップアップを
        閉じるまで選択できない」の実装が、この順序そのものである）"""
        return self._point_in_rect(
            x, y, self._popup_x, self.POPUP_Y, self.POPUP_W, self.POPUP_H
        )

    def _point_in_rect(self, px, py, rx, ry, rw, rh):
        """点 (px, py) が矩形 (rx, ry, rw, rh) の内側にあるかを判定する。
        半開区間 [rx, rx + rw) × [ry, ry + rh) での判定であり、左端・上端を
        含み、右端・下端を含まない（区画の判定範囲 _screen_to_plot() と同じ
        半開区間の考え方を、矩形の点内判定という形で表す）"""
        return rx <= px < rx + rw and ry <= py < ry + rh

    def draw(self):
        """画面を奥から手前の順に描く。ステータス → 道路 → 店舗 までがフィールド、
        その上に盤面を変えずに載る2つの枠（売上の囲み → 選択中の区画を示す枠）が
        重なり、区画選択ポップアップ → 決算ポップアップ → 終了（クリア／
        ゲームオーバー）ポップアップの順で、3つのモーダルのうち後発のものほど
        最前面へ来る（ID-017 案4・案6。ID-015 が予告した「3つ目のモーダルも
        同じ型で足せる見込み」の決着——実際に、既存の2つに1行足すだけの
        同じ型で足せた）。
        枠を店舗より先に描くと、枠は店舗画像の範囲を覆うため店舗の不透明部分で
        上書きされて消える。いずれの枠も下の道路まで含む範囲（PREVIEW_W ×
        PREVIEW_H）を囲うので、下の行に店舗があればその上端 8px にも重なるが、
        店舗をすべて描き終えた後に描くためどちらの店舗にも隠されない（この理由は
        2つの枠に共通して当てはまる）。
        2つの枠の間の順序は「売上の囲み → 選択枠」とする。選択枠はプレイヤーが
        **いま押している区画**に対する直接の応答であり、同じ区画で重なった
        ときは操作側の応答が上に出るのが自然なため。売上の囲みは時間経過で
        勝手に付くものであり、操作の邪魔をしない側へ置く。
        **2つの枠は原点・幅・高さがすべて一致する**ため、同じ区画で同時に
        出たときは完全に重なり、後に描く選択枠（色）だけが見える
        （_draw_sales_frame() の docstring）。
        決算ポップアップを区画選択ポップアップよりさらに後（最前面）に描くのは、
        決算ポップアップの表示中は他の操作を受け付けない状態（要件 3.8。
        抑止そのものはサイクル3）であることを、重なりの上下関係でも表すため
        （画面上、常に決算ポップアップが他のすべてを覆う）。終了ポップアップを
        さらにその後（最前面）に描くのも同じ理由——終了中は他の操作を一切
        受け付けない状態（要件「ゲーム終了後」。抑止そのものは ID-017
        サイクル4）であることを表す。3つのモーダルは要件上どの2つも同時に
        現れないため、実際に重なりが問題になる場面は無いが、描画順そのものが
        「後発ほど強い（他を覆う）」という一貫した規則になっていることを、
        描く順序の並びだけで示す"""
        self._draw_status()
        self._draw_roads()
        self._draw_shops()
        self._draw_sales_frame()
        self._draw_selection()
        self._draw_popup()
        self._draw_settlement_popup()
        self._draw_game_end_popup()

    def _is_selection_shown(self):
        """選択中の区画に対する表示（フィールド上の枠とポップアップ）を行う
        状態かを返す。NONE（選択なし）と CLOSING（ボタン押下で閉じたが指が
        まだ離れていない）では、どちらも描かない。_draw_selection() と
        _draw_popup() が同じ述語を読むことで、**片方だけが描かれる状態を
        作れない**ようにしている（両者は同じ「選択中の区画」から導かれる
        表示であり、描画の有無が食い違ってはならない）"""
        return self._popup_state not in (PopupState.NONE, PopupState.CLOSING)

    def _draw_sales_frame(self):
        """売上の抽選が起きた店舗をフィールド上で囲む枠を、店舗の後・選択枠の
        前へ描画する（要件 3.3）。囲むのは**抽選された店舗**であり、資金が
        増えたかどうかとは独立している（NPC所有店舗が抽選されたときも囲む。
        所有者による分岐を持つのは資金の加算だけ。_collect_sales()）。
        _draw_selection() と同じく「区画を1つ覚えている状態から枠線を1回描く」
        形だが、**描くかどうかの判定が異なる**。選択枠は状態の述語
        （_is_selection_shown()）を読むのに対し、こちらは覚えている区画が
        あるか（_sales_plot is None）だけで決まる（囲みは押下やポップアップの
        状態と無関係に、抽選が起きたかどうかだけで決まるため）。
        囲う範囲は選択枠と同じ PREVIEW_W × PREVIEW_H（店舗画像とその下の道路）
        で、**原点・幅・高さのすべてが選択枠と一致する**。そのため同じ区画が
        選択中かつ売上発生中のときは2つの枠が完全に重なり、色による見分けは
        できない。この重なりでは**選択枠を優先する**（draw() で選択枠を後に
        描く。選択はプレイヤーが今指で押している区画への直接の応答であり、
        時間経過で勝手に付く売上の囲みより優先して見える方が自然という判断）。
        塗りつぶし（draw_rect）ではなく枠線（draw_rectb）にすることで、
        どの店舗かを示しながら中の店舗画像を隠さない"""
        if self._sales_plot is None:
            return
        x, y = self._plot_origin(*self._sales_plot)
        self._view.draw_rectb(
            x, y, self.PREVIEW_W, self.PREVIEW_H, self.SALES_FRAME_COL
        )

    def _draw_selection(self):
        """選択中の区画をフィールド上で示す黄色い枠を、店舗の後・ポップアップの
        前へ描画する。枠は押下位置ではなく、ポップアップと同じ「選択中の区画」
        （self._popup_plot）から導くため、MODAL で押下位置が動いても
        ポップアップの内容と食い違わない。塗りつぶし（draw_rect）ではなく
        枠線（draw_rectb）にすることで、選択を示しながら中の店舗画像を隠さない。
        囲う範囲は店舗画像とその下の道路（PREVIEW_W × PREVIEW_H）で、
        ポップアップのプレビュー領域と同じ範囲になる"""
        if not self._is_selection_shown():
            return
        x, y = self._plot_origin(*self._popup_plot)
        self._view.draw_rectb(x, y, self.PREVIEW_W, self.PREVIEW_H, self.SELECTION_COL)

    def _draw_icon(self, x, y, u, v):
        """アイコン1つ（ICON_W × ICON_H）を位置 (x, y) へ描画する。転送元
        (u, v) は呼び出し側が意味ごとの名前付き定数（ICON_MONEY など。
        ID-026 決定2）から渡す。大きさ・画像バンク・透過色は8種のアイコンで
        共通の1組しか持たない（決定1）ため、_draw_road_tile() /
        _draw_shop_image() と同じ形の共通処理として、転送元だけを引数に取る。
        ステータス・ポップアップ数値・ポップアップボタンの3箇所が呼ぶ
        （026-2・026-3 で呼び出しが増える）"""
        self._view.draw_image(
            x, y, self.ICON_IMG, u, v, self.ICON_W, self.ICON_H, self.ICON_COLKEY
        )

    def _draw_icon_value(self, x, y, u, v, text):
        """アイコン1つ（転送元 (u, v)）と、その右へ ICON_GAP を挟んで
        並べる数値・文字列 text の組を、位置 (x, y) へ描画する（決定1。
        「アイコンと数値の組で1つの項目を表す」という要件を、ステータス
        3項目（本サイクル）とポップアップ数値3行（026-2）が共有する処理
        として1箇所へ持つ。ボタン（026-3）はアイコンを矩形の中央へ置くため
        数値を伴わず、_draw_icon() を直接使う——引数がここへ増え始めたら
        決定1の差し戻し条件に該当する"""
        self._draw_icon(x, y, u, v)
        self._view.draw_text(x + self.ICON_W + self.ICON_GAP, y, text)

    def _right_aligned_number_x(self, area_x, text, max_digits):
        """幅 FONT_CHAR_W × max_digits の領域（左端 area_x）内で右詰めに
        したときの文字列 text の描画 x を返す（ID-027 サイクル027-3
        Refactor。決定10）。max_digits を超える桁数の値は、右詰め計算の
        とおりそのまま左へはみ出す（キャップしない）。
        _draw_icon_value_right()（アイコン付き。ID-026 サイクル026-4）と
        _draw_settlement_popup_values()（アイコン無し。決算ポップアップの
        筆算はここが本コードベース初のアイコンを伴わない右詰め）の両方が
        使う——アイコンの有無をフラグ引数で呼び分ける形は取らない
        （決定1の差し戻し条件「どこから呼ばれたか」を伝える引数が増え
        始めたら分ける、に触れるため）。「右詰め位置の計算」だけを両者から
        独立させ、アイコンを描くかどうかは呼び出し元にそれぞれ残す"""
        return area_x + (max_digits - len(text)) * self.FONT_CHAR_W

    def _draw_icon_value_right(self, x, y, u, v, value, max_digits):
        """アイコン1つ（転送元 (u, v)）と、その右の幅
        FONT_CHAR_W × max_digits の領域内で右詰めにした数値 value の組を、
        位置 (x, y) へ描画する（ID-026 サイクル026-4 決定9）。
        _draw_icon_value() へ「桁数」引数を足す形は取らない——呼び出し元に
        よって右詰めの要否が変わる引数は、決定1の差し戻し条件（「どこから
        呼ばれたか」を伝える引数が増え始めたら分ける）に触れるため、
        右詰めが要る箇所（資金・税額）専用の処理として別に持つ。
        アイコンは (x, y) に固定で描き、数値領域は
        x + ICON_W + ICON_GAP から始まる——右詰め位置そのものの計算は
        _right_aligned_number_x()（ID-027 サイクル027-3 Refactor）へ譲る"""
        self._draw_icon(x, y, u, v)
        text = f"{value}"
        number_area_x = x + self.ICON_W + self.ICON_GAP
        number_x = self._right_aligned_number_x(number_area_x, text, max_digits)
        self._view.draw_text(number_x, y, text)

    def _settlement_remaining_ratio(self):
        """決算間隔に対する残り時間の割合を返す（ID-027 TDD サイクル
        027-1）。ShopClock.remaining_ratio()（決定1-A）が未開始のとき
        返す None を、ここで満杯（1.0）へ読み替える（決定4-A）——
        remaining_ms() の None を SETTLEMENT_INTERVAL_MS へ読み替えて
        `T {秒}` を描いていた ID-025 の方針（読み替えを表示側に置く）を
        踏襲する。_draw_status() のプログレスバー（サイクル 027-2）が
        中身の幅を求めるために呼ぶ"""
        ratio = self._settlement_clock.remaining_ratio()
        return 1.0 if ratio is None else ratio

    def _draw_status(self):
        """ステータス領域の背景と、2列2行に並ぶ資金・店舗数・支払い予定
        税額・決算までの残り時間、右のポーズ／スピードボタン2つを描画する
        （背景の後にテキスト・ボタンが載る。ID-014 サイクル3で1行構成から
        2行構成へ広げ、ID-019 サイクル3でボタン2つを3件目の要素として加え、
        ID-028 サイクル028-4で1行目へ店舗数を4件目の要素として加え、ID-026
        サイクル026-1で資金・店舗数・税額をアイコン＋数値の組へ置き換え、
        サイクル026-4でプレイテスト指示により2列2行のレイアウトへ組み替えた）。

        2列2行のレイアウト（決定6・決定8。プレイテスト指示1）: 左列
        （x = STATUS_X + STATUS_PAD = left_x）に資金（1行目）・税額
        （2行目）、右列1行目（x = STATUS_SHOP_COUNT_X）に店舗数を置く。
        資金と税額を同じ列に縦へ並べたのは、右詰め（後述）で一の位を揃え、
        桁数の違う2つの金額を目で比べられるようにするため。店舗数は
        左詰めのまま——`n/m` 形式は桁を比べる対象ではないため右詰めの
        必要が無い（決定8）。**2行目のプログレスバーは右列の固定 x を
        共有しない**——ID-027 決定5改訂（プレイテスト指示・2026-08-30）
        により、税額の数値に近づけた STATUS_BAR_X を独自に持つ（後述）。
        ボタン2つは**押下判定を持つ**ため（次サイクル 019-4
        以降）、テキストと同じ「まとめて描く」形にはせず、
        _draw_status_buttons() へ分離した。

        資金・税額: _draw_icon_value_right()（決定9）で、アイコンの右へ
        ICON_GAP 空けた位置から幅 FONT_CHAR_W × STATUS_VALUE_MAX_DIGITS の
        領域内に右詰めで描く。STATUS_VALUE_MAX_DIGITS はキャップではなく
        表示幅を決めるための想定桁数であり、これを超える桁数の値はそのまま
        左へはみ出す。

        店舗数: Field.player_shop_count（現在のプレイヤー所有店舗数）と
        Field.CLEAR_SHOP_COUNT（規定店舗数）をそのまま relay する
        （_draw_popup_values() が Field の戻り値を relay に徹しているのと
        同じ形）。player_shop_count は Field 側で内部状態として保持される
        値だが、**GameCore 側では持ち回らずプロパティ越しに毎フレーム
        読む**——決算の店舗売却（ID-016）でプレイヤー所有店舗が減っても、
        次のフレームの draw() で必ず追従する（要件「4. プレイヤーステータス」。
        ID-028_subtasks.md「テスト設計の注意」3）。

        残り時間: 数値ではなくプログレスバーで表す（ID-027 決定5。ID-026
        決定6が申し送っていた置き換え）。バーは残り時間ぶんの中身
        （draw_rect）と、枠（draw_rectb）の2つを、この順で同じ原点
        (STATUS_BAR_X, line2_y) に重ねて描く——**枠を後（中身より前面）に
        描く**のは、満杯（割合1.0）のとき中身の矩形が枠と完全に重なり、
        先に枠を描くと中身に隠れて見えなくなる（枠が「時間の経過につれて
        現れる」ように見えてしまう）ため。枠を後に描くことで、時間経過と
        無関係に常に見える状態を保つ（プレイテスト指摘・2026-08-30）。
        位置・幅（STATUS_BAR_X / STATUS_BAR_W）も同日のプレイテスト指示
        により、出発点（右列の固定 x を店舗数と共有・幅60px仮値）から
        改めた——**左端は税額の数値に近づける**（左列の数値領域の右端から
        5px。右詰めのため実際の桁数によらず右端は動かない）、**右端は
        ポーズボタンの手前 STATUS_BAR_PAUSE_GAP（5px）まで伸ばす**（使える
        幅いっぱいから、ボタンとの間に空間を空ける追加指示ぶんを引く）。
        中身の幅は _settlement_remaining_ratio()（決算間隔に対する残り
        時間の割合。ID-027 TDD サイクル 027-1）に STATUS_BAR_W を掛けて
        求める。割合が None を返すことはない——同メソッドが未開始
        （ShopClock.remaining_ratio() の None）を満杯（1.0）へ読み替え済み
        であり（決定4）、その読み替えを行う場所（表示側）は本メソッドから
        _settlement_remaining_ratio() へ移っている。

        税額: Field.total_tax() の戻り値をそのまま描くだけで、GameCore 側に
        計算式は持たない（_draw_popup_values() が Field の戻り値を relay に
        徹しているのと同じ形）。持ち回らず**毎フレーム導出する**ことで、
        盤面（建設・増資・買収・他店の成長）が変わればステータスの表示も
        必ず追従する（Shop.cost / Shop.sales が持ち回りから導出へ移された
        判断と同じ。ID-005〜ID-006。なお Shop 側は ID-020 で地域価格倍率が
        式へ入った負荷を理由に持ち回りへ戻したが、更新箇所を状態が変わる
        メソッドの中に閉じ込めることで追従は保っている）。

        資金・店舗数・税額は、数値の意味を表すアイコン画像（ICON_MONEY /
        ICON_SHOP_COUNT / ICON_TAX）を数値の直前に置いた組で描く（ID-026
        決定4。"MONEY" / "SHOP" / "TAX" の文字ラベルはアイコンへ置き換わり、
        「/」と規定店舗数は文字のまま残る）"""
        self._view.draw_rect(
            self.STATUS_X,
            self.STATUS_Y,
            self.STATUS_W,
            self.STATUS_H,
            self.STATUS_BG_COL,
        )
        left_x = self.STATUS_X + self.STATUS_PAD
        line1_y = self.STATUS_Y + self.STATUS_PAD
        line2_y = line1_y + self.STATUS_LINE_H
        self._draw_icon_value_right(
            left_x,
            line1_y,
            *self.ICON_MONEY,
            self._money,
            self.STATUS_VALUE_MAX_DIGITS,
        )
        self._draw_icon_value(
            self.STATUS_SHOP_COUNT_X,
            line1_y,
            *self.ICON_SHOP_COUNT,
            f"{self._field.player_shop_count}/{self._field.CLEAR_SHOP_COUNT}",
        )
        self._draw_icon_value_right(
            left_x,
            line2_y,
            *self.ICON_TAX,
            self._field.total_tax(),
            self.STATUS_VALUE_MAX_DIGITS,
        )
        bar_fill_w = round(self.STATUS_BAR_W * self._settlement_remaining_ratio())
        self._view.draw_rect(
            self.STATUS_BAR_X,
            line2_y,
            bar_fill_w,
            self.STATUS_BAR_H,
            self.STATUS_BAR_FILL_COL,
        )
        self._view.draw_rectb(
            self.STATUS_BAR_X,
            line2_y,
            self.STATUS_BAR_W,
            self.STATUS_BAR_H,
            self.STATUS_BAR_FRAME_COL,
        )
        self._draw_status_buttons()

    def _draw_status_buttons(self):
        """ステータス領域右の、ポーズ「||」・スピード「>」系の2つのボタンを
        描画する（ID-019 サイクル3で新設、サイクル4でスピードのラベルを
        現在の段階から描く形に変えた、サイクル6でポーズの状態
        （self._paused）による配色の入れ替えを加えた）。2つのボタンは
        「いま効いていない側」が無効表示（背景 STATUS_BTN_DISABLED_COL）
        になる排他の対（設計方針 6-1）——ポーズ解除中（self._paused が
        偽。時間が進んでいる）はポーズが無効表示・スピードが通常表示、
        ポーズ中はその逆になる。ラベル自体（「||」・現在の段階のラベル）
        はポーズの有無で変わらない（状態は配色だけで示す）。

        2つのボタンは幅・高さを共通にし（STATUS_BTN_W / _H。ラベルの
        長さでボタンの大きさが変わると押し間違いが起きやすくなるため）、
        ステータス領域の右端（内側余白 STATUS_PAD ぶんを残す）から
        左向きに、ポーズ → スピードの順で STATUS_BTN_GAP を空けて並べる。
        縦位置はステータス領域の高さ（STATUS_H）の中央に揃える。
        2つのボタンの矩形はいずれも専用の式（_status_pause_button_rect() /
        _status_speed_button_rect()。押下判定と共通）から導くため、
        片方だけがレイアウト変更に追従し損なうことはない。
        配色は「効いている側かどうか」の真偽値1つから決まる同じ規則
        （_status_button_col()）を2つのボタンで共有し、ポーズ・スピードで
        真偽が常に逆になる（自分が効いていれば相手は効いていない、
        設計方針6-1の排他の対）ことを `not self._paused` の1箇所だけで
        表す——if/else をボタンごとに重ねて書くと、この排他が2箇所の
        独立した条件式に分かれ、将来どちらかだけ直し忘れる経路を作れて
        しまう"""
        pause_x, btn_y, _, _ = self._status_pause_button_rect()
        speed_x, _, _, _ = self._status_speed_button_rect()
        self._draw_status_button(
            pause_x, btn_y, self.PAUSE_BTN_LABEL, self._status_button_col(self._paused)
        )
        speed_label, _ = self.GAME_SPEED_STEPS[self._speed_index]
        self._draw_status_button(
            speed_x, btn_y, speed_label, self._status_button_col(not self._paused)
        )

    def _status_button_col(self, active):
        """ステータスボタンの配色を、「いま効いているかどうか」の真偽値
        active から決める（ID-019 サイクル6）。効いていれば通常表示
        （STATUS_BTN_COL）、効いていなければ無効表示
        （STATUS_BTN_DISABLED_COL）を返す——ポーズ・スピードの2つの
        ボタンが常に排他（設計方針6-1）であることを、呼び出し側が
        `self._paused` / `not self._paused` の対で渡す1組の引数だけで
        表せるようにする"""
        return self.STATUS_BTN_COL if active else self.STATUS_BTN_DISABLED_COL

    def _draw_status_button(self, x, y, label, col):
        """ステータスボタン1つ（矩形＋ラベル）を、位置 (x, y)・色 col で
        描画する。col は通常表示（STATUS_BTN_COL）・無効表示
        （STATUS_BTN_DISABLED_COL）のいずれかを呼び出し側が渡す——資金
        不足時のポップアップの無効ボタン（枠線のみで「押しても実行され
        ない」ことを示す）とは異なり、こちらは押下そのものをどちらの
        表示でも受け付けるため、いずれも塗りつぶし（draw_rect）で描く
        （枠線だけの draw_rectb にはしない）。
        ラベルは矩形の中央へ、文字数（FONT_CHAR_W）に応じて左右を中央
        寄せする（単一文字を前提にした既存ボタンの "-2" 固定値の一般化。
        縦方向は行の高さによらない既存と同じ "-2" のまま）"""
        self._view.draw_rect(x, y, self.STATUS_BTN_W, self.STATUS_BTN_H, col)
        text_x = x + (self.STATUS_BTN_W - len(label) * self.FONT_CHAR_W) // 2
        text_y = y + self.STATUS_BTN_H // 2 - 2
        self._view.draw_text(text_x, text_y, label)

    def _draw_roads(self):
        """道路を横方向に画面幅まで敷き詰め、縦方向に PITCH 間隔で
        （区画の行数 + 1）本（最下段の閉じの道路を含む）描画する"""
        # 画面幅を道路サイズで切り上げ割りした枚数（右端に欠けが出ないよう敷き詰める）
        road_cols = -(-self.SCREEN_W // self.ROAD_SIZE)
        for row in range(self.GRID_ROWS + 1):
            y = self.FIELD_ORIGIN_Y + row * self.PITCH
            for col in range(road_cols):
                self._draw_road_tile(col * self.ROAD_SIZE, y)

    def _draw_road_tile(self, x, y):
        """道路タイル1枚（ROAD_SIZE × ROAD_SIZE）を位置 (x, y) へ描画する。
        フィールドの道路敷き詰め（_draw_roads）とポップアップのプレビューの
        下の道路（_draw_popup_preview）の両方から呼ばれる、転送元（ROAD_*）を
        まとめた共通処理"""
        self._view.draw_image(
            x,
            y,
            self.ROAD_IMG,
            self.ROAD_U,
            self.ROAD_V,
            self.ROAD_SIZE,
            self.ROAD_SIZE,
            self.ROAD_COLKEY,
        )

    def _draw_shops(self):
        """Field の列挙順（行昇順→列昇順）に、区画に対応する画面座標へ店舗を描画する。
        道路の後に呼ばれるため、店舗が道路の上に載る（後勝ち）"""
        for col, row in self._field.iter_shop_pos():
            owner = self._field.get_owner(col, row)
            scale = self._field.get_scale(col, row)
            shop_x, shop_y = self._plot_origin(col, row)
            self._draw_shop_image(shop_x, shop_y, owner, scale)

    def _draw_shop_image(self, x, y, owner, scale):
        """位置 (x, y) へ、所有者・規模から求めた転送元で店舗画像（SHOP_W ×
        SHOP_H）を描画する。フィールド上の店舗描画（_draw_shops）とポップアップの
        プレビューの店舗画像（_draw_popup_preview）の両方から呼ばれる"""
        shop_u, shop_v = self._shop_transfer_src(owner, scale)
        self._view.draw_image(
            x,
            y,
            self.SHOP_IMG,
            shop_u,
            shop_v,
            self.SHOP_W,
            self.SHOP_H,
            self.SHOP_COLKEY,
        )

    def _popup_origin_x(self, x):
        """押下位置 x から、その回のポップアップ原点 x（POPUP_LEFT_X /
        POPUP_RIGHT_X のいずれか）を求める。画面右半分（x >= SCREEN_W // 2）は
        左下、左半分（x < SCREEN_W // 2）は右下に表示する（押している指と反対側へ
        逃がすことで、指でポップアップが隠れないようにする）。境界 x == SCREEN_W
        // 2 は右半分（左下表示）に含める半開区間として扱う"""
        return self.POPUP_LEFT_X if x >= self.SCREEN_W // 2 else self.POPUP_RIGHT_X

    def _draw_popup(self):
        """選択中の区画があるとき、ポップアップの背景・枠線・プレビューを
        最前面（店舗の後）へ描画する。枠線は背景と同じ位置・同じサイズで、
        塗りつぶしの後に描くことで背景に上書きされずに残る。ポップアップを
        表示しないとき（self._popup_state が NONE または、ボタン押下で
        既に閉じているが指がまだ離れていない CLOSING のとき）は何も描かない。
        原点 x は update() で押下位置から求めた self._popup_x（左右いずれか）を
        使い、原点 y は常に定数 POPUP_Y（画面下部固定）を使う。内部の全要素は
        この原点からの相対で描くため、表示位置が切り替わっても同じ導出で済む"""
        if not self._is_selection_shown():
            return
        x, y = self._popup_x, self.POPUP_Y
        self._view.draw_rect(x, y, self.POPUP_W, self.POPUP_H, self.POPUP_BG_COL)
        self._view.draw_rectb(x, y, self.POPUP_W, self.POPUP_H, self.POPUP_BORDER_COL)
        # 選択中の区画の所有者はここで一度だけ判定し、プレビュー・数値3行の
        # 両方へ渡す（同じ区画の状態を2箇所で別々に判定しない）
        owner = self._field.get_owner(*self._popup_plot)
        self._draw_popup_preview(x + self.POPUP_PAD, y + self.POPUP_PAD, owner)
        self._draw_popup_values(x, y)
        self._draw_popup_buttons(x, y)

    def _draw_popup_preview(self, x, y, owner):
        """ポップアップ内のプレビュー領域（選択位置の店舗画像とその下の道路。
        全体で PREVIEW_W × PREVIEW_H で、フィールド上の選択枠と同じ範囲）を、
        プレビュー原点 (x, y) からの相対で描画する。下の道路は区画の状態に
        よらず常に同じ位置へ描く（プレビュー幅 PREVIEW_W を ROAD_SIZE 幅で
        敷き詰める）。店舗画像は選択中の区画に店舗があるときだけ、プレビュー
        原点そのもの（rel y = 0、道路の後）へ上乗せで描く。owner は選択中の
        区画の所有者（_draw_popup が一度だけ判定した値）を受け取る"""
        road_y = y + self.SHOP_H
        for i in range(self.PREVIEW_W // self.ROAD_SIZE):
            self._draw_road_tile(x + i * self.ROAD_SIZE, road_y)
        if owner is None:
            return
        scale = self._field.get_scale(*self._popup_plot)
        self._draw_shop_image(x, y, owner, scale)

    def _draw_popup_values(self, x, y):
        """ポップアップ内の数値3行（費用・資産価値・売上額）を、ポップアップ原点
        (x, y) からの相対で、数値の意味を表すアイコン画像（ICON_COST /
        ICON_VALUE / ICON_SALES）を直前に置いた組で描画する（ID-026 決定4。
        _draw_icon_value_right() は026-4 の Refactor で用意済みの共通処理を
        そのまま使う。026-5 で本メソッドへ採用した）。横位置はプレビュー
        （幅 PLOT_SIZE）の右へ POPUP_GAP 空けた位置に揃え、縦位置は3行の
        ブロックがプレビュー領域（PREVIEW_H）に対して中央へ来るよう
        POPUP_VALUES_TOP_PAD ぶん下げた位置を起点に、POPUP_LINE_H 間隔で
        3行を並べる（ID-026 サイクル026-5。中間プレイテスト指示——3行が
        プレビュー画像に対して上に詰まって見えるため、行間を広げ
        （POPUP_LINE_H を8→10へ）中央寄せにした）。
        費用・資産価値・売上額の中身（区画の状態による切り替え・実データか仮の
        定数か）はすべて Field の責務であり、GameCore は Field.get_cost() /
        get_value() / get_sales() の戻り値をそのまま描画するだけの relay に徹する。
        費用アイコン（ICON_COST）は区画の状態（空き／プレイヤー所有／NPC所有）
        によらず常に同じ1種で、区画の状態で切り替えない（ID-026 決定3。
        建設・増資・買収は同時に表示されず、どの費用かは選択中の区画の状態が
        一意に決めるためアイコンで区別する必要が無い）。
        ただし**値が存在しないこと**（Field が None を返すこと）の見せ方だけは
        描画側で決める。費用は存在しないことがあり（規模が上限のプレイヤー所有
        店舗は増資できない。要件 3.6）、そのときも費用アイコンは描いたまま数値の
        側だけ POPUP_NO_COST_TEXT にする（ID-026 決定5-A。項目そのものは
        存在し、値だけが存在しないため、アイコンを消すと項目の対応が崩れる）。
        資産価値は空き区画で存在せず、そのときは 0 を描く。どちらも値を取り出す
        3行に並べて書き、3行を同じ形で描くループ側は分岐を持たない。
        費用の判定は `or` ではなく `is None` で行う——`or` は「費用0」と「費用が
        存在しない」を同じものとして扱ってしまい、ここで述べたいのは後者だけの
        ため（資産価値の `or 0` は、空き区画では0と不在のどちらでも0を描くのが
        正しいためこの書き方でよい）。
        数値は最大 POPUP_VALUE_MAX_DIGITS（7）桁ぶんの幅で右詰めにする
        （ID-026 サイクル026-5。中間プレイテスト指示）。ステータスの資金・
        税額（STATUS_VALUE_MAX_DIGITS）と同じくキャップではなく表示幅を
        決めるための想定値で、実測の理論上限（6桁）を超えることは無い"""
        col, row = self._popup_plot
        raw_cost = self._field.get_cost(col, row)
        cost = self.POPUP_NO_COST_TEXT if raw_cost is None else raw_cost
        value = self._field.get_value(col, row) or 0
        sales = self._field.get_sales(col, row)
        text_x = x + self.POPUP_PAD + self.PLOT_SIZE + self.POPUP_GAP
        values_top_y = y + self.POPUP_PAD + self.POPUP_VALUES_TOP_PAD
        icons = (self.ICON_COST, self.ICON_VALUE, self.ICON_SALES)
        for i, (num, (u, v)) in enumerate(zip((cost, value, sales), icons)):
            self._draw_icon_value_right(
                text_x,
                values_top_y + i * self.POPUP_LINE_H,
                u,
                v,
                num,
                self.POPUP_VALUE_MAX_DIGITS,
            )

    def _popup_button_rect(self, x, y, index):
        """ポップアップ原点 (x, y) から index 番目のボタン（0: 「o」（上）, 1: 「x」
        （下））の矩形 (btn_x, btn_y, w, h) を導く。o・x はポップアップ左下（内側
        余白 POPUP_PAD ぶん内側）を起点に、POPUP_BTN_GAP 空けて縦に並ぶため、
        index 1つにつき (POPUP_BTN_H + POPUP_BTN_GAP) だけ y が進む形で1つの式に
        まとめられる。x はポップアップ幅いっぱい（POPUP_BTN_W）に広げているため
        index によらず同じ。描画（_draw_popup_buttons）と押下判定
        （_popup_button_index_at()）の両方がこの式を経由することで、片方だけ
        レイアウト変更に追従し損なうことを防ぐ"""
        block_h = 2 * self.POPUP_BTN_H + self.POPUP_BTN_GAP
        block_top = y + self.POPUP_H - self.POPUP_PAD - block_h
        btn_x = x + self.POPUP_PAD
        btn_y = block_top + index * (self.POPUP_BTN_H + self.POPUP_BTN_GAP)
        return btn_x, btn_y, self.POPUP_BTN_W, self.POPUP_BTN_H

    def _draw_popup_buttons(self, x, y):
        """ポップアップ内の「o」「x」ボタン（矩形＋アイコン）を、ポップアップ原点
        (x, y) からの相対で描画する。矩形は _popup_button_rect() から導き、ここでは
        描画にのみ徹する（押下判定は _popup_button_index_at() が同じ矩形を
        再利用して行う）。アイコンは矩形の中央へ寄せる（ID-026 サイクル026-3。
        文字（フォント1文字ぶんのオフセットでの近似）からアイコンへ置き換え、
        (矩形の大きさ − ICON_W/H) // 2 の正確な中央揃えにした）。実行ボタン
        「o」は ICON_OK、キャンセルボタン「x」は ICON_CANCEL を使う。
        押せないボタン（_is_popup_button_enabled() が False。押下判定もこの同じ
        述語で無効になる）は塗りつぶさず、枠線だけを描く。**無効を伝えるのは色では
        なく塗りつぶしの有無**（面の違い）であり、色は「ポップアップの一部として
        馴染む」ことだけを担う。描画メソッドと色は必ず対で切り替わるよう1組の値と
        して選び（色だけ変えて塗りつぶしが残る組み合わせを書けないようにする）、
        矩形（位置・大きさ）とアイコンは有効・無効で変わらないよう呼び出しを1つに
        保つ"""
        for index, (u, v) in enumerate(self.POPUP_BTN_ICONS):
            btn_x, btn_y, btn_w, btn_h = self._popup_button_rect(x, y, index)
            draw_button, col = (
                (self._view.draw_rect, self.POPUP_BTN_COL)
                if self._is_popup_button_enabled(index)
                else (self._view.draw_rectb, self.POPUP_BTN_DISABLED_COL)
            )
            draw_button(btn_x, btn_y, btn_w, btn_h, col)
            self._draw_icon(
                btn_x + (btn_w - self.ICON_W) // 2,
                btn_y + (btn_h - self.ICON_H) // 2,
                u,
                v,
            )

    def _draw_settlement_popup(self):
        """決算ポップアップの背景・枠線・数値3行（減算前・税額・減算後）・
        「o」ボタンを、最前面（区画選択ポップアップの後）へ描画する。表示
        するかどうかは self._settlement_popup_state が SHOWN かどうかだけで
        決まる（区画選択の PopupState とは別に持つ独立した状態）。精算は
        「o」ボタンの押下解除（released）の瞬間に実行され、同じ行で状態が
        直接 NONE へ戻るため（_update_settlement_popup() を参照）、精算後に
        指がまだ画面に置かれたままでも、見た目にはもうポップアップは無い。
        数値3行・「o」ボタンの中身はそれぞれ _draw_settlement_popup_values() /
        _draw_settlement_popup_button() が担う（背景・枠線 → 数値3行 →
        ボタンの順に描く。区画選択ポップアップが背景・枠線・プレビュー・
        数値3行・ボタンをそれぞれ別メソッドへ分けているのと同じ形）"""
        if self._settlement_popup_state != SettlementPopupState.SHOWN:
            return
        self._view.draw_rect(
            self.SETTLEMENT_POPUP_X,
            self.SETTLEMENT_POPUP_Y,
            self.SETTLEMENT_POPUP_W,
            self.SETTLEMENT_POPUP_H,
            self.SETTLEMENT_POPUP_BG_COL,
        )
        self._view.draw_rectb(
            self.SETTLEMENT_POPUP_X,
            self.SETTLEMENT_POPUP_Y,
            self.SETTLEMENT_POPUP_W,
            self.SETTLEMENT_POPUP_H,
            self.SETTLEMENT_POPUP_BORDER_COL,
        )
        self._draw_settlement_popup_values()
        self._draw_settlement_popup_button()

    def _draw_settlement_popup_button(self):
        """決算ポップアップ内の「o」ボタン（矩形＋アイコン）を描画する。矩形は
        _settlement_popup_button_rect()（押下判定と共通）から導く。区画選択
        ポップアップの _draw_popup_buttons() と異なり**無効表示を持たない**
        ——精算には可否条件が無く（_settle_tax() の docstring を参照）、
        資金が足りなくても常に押せるため、塗りつぶし・枠線だけの2択（無効
        表示）を必要としない。アイコンは矩形の中央へ寄せる（ID-026
        サイクル026-3。文字から ICON_OK へ置き換え、_draw_popup_buttons() と
        同じ (矩形の大きさ − ICON_W/H) // 2 の正確な中央揃えにした）"""
        btn_x, btn_y, btn_w, btn_h = self._settlement_popup_button_rect()
        self._view.draw_rect(btn_x, btn_y, btn_w, btn_h, self.SETTLEMENT_POPUP_BTN_COL)
        self._draw_icon(
            btn_x + (btn_w - self.ICON_W) // 2,
            btn_y + (btn_h - self.ICON_H) // 2,
            *self.ICON_OK,
        )

    def _draw_settlement_popup_values(self):
        """決算ポップアップ内の数値3行（減算前の資金・税額・減算後の資金）を
        筆算（ひっ算）の形で、ポップアップ原点からの相対で描画する（ID-027
        サイクル027-3。プレイテスト指摘によるユーザー指示。決定8〜決定12）。
        3つの値は持ち回らず**毎フレーム導出する**（減算前 = self._money /
        税額 = self._field.total_tax() / 減算後 = 減算前 − 税額）。盤面・
        資金が変われば必ず追従し、完全凍結（サイクル4）で表示中は動かなく
        なるのは時間経過そのものが止まるためであり、表示側が値を固定して
        いるわけではない。
        減算後は 0 で頭打ちにせず、負の数もそのまま描く（資金が税額に
        満たない場合の設計判断。符号付きの文字列もそのまま右詰めされる）。
        減算後の式（減算前 − 税額）は、精算処理（サイクル5）が資金へ行う
        `self._money -= tax` と同じ式であり、表示と実際の減算とで別々に
        書かない（食い違う経路を作らない）。
        数値3行は、幅 FONT_CHAR_W × STATUS_VALUE_MAX_DIGITS の領域内で
        右詰めにする（決定10。**プレイヤーステータスの資金・税額の右詰め
        〈ID-026〉と同じ想定桁数を流用する**——決算ポップアップの3値は
        いずれもステータスの資金・税額と同じ由来の数値であり、想定桁数を
        分ける理由が無いという判断で、専用の定数は新設しない〈ユーザー
        指示による決定10の改訂。実装を簡素にする〉。右詰め位置の計算は
        _right_aligned_number_x() と共有——アイコンを伴わない右詰めは本
        コードベース初）。**右詰めの領域はポップアップ右枠の内側から
        SETTLEMENT_POPUP_VALUE_RIGHT_GAP ぶん空けた位置を右端とする**
        （プレイテスト指摘。2026-08-30。当初は領域の左端を
        SETTLEMENT_POPUP_PAD の位置に固定していたため、桁数の少ない値ほど
        罫線の長さに対して数字が中央寄りに見えていた）。
        3行目の直前の行間へ高さ1の横線を引き（決定9・決定11。draw_rect。
        左端・幅は数値領域の全幅）、その左端の真上・2行目（税額）の行へ
        独立した draw_text で `-` を描く（決定12。税額の数値へ連結すると
        右詰め計算に1文字食い込み、3行の桁の縦の揃いが崩れるため連結
        しない）。**ラベル文言は付けない**——文言ではなく、右詰め・横線・
        `-` という配置だけで「1つ目 − 2つ目 = 3つ目」という関係を示すのが
        本サイクルの狙い。
        **3行目（減算後）だけ、横線との間に SETTLEMENT_POPUP_RULE_TEXT_GAP
        ぶんの余白を空けて下へずらす**（プレイテスト指摘。2026-08-30。
        当初は横線の直下に数字が接していた）。1・2行目と横線・`-` の位置は
        動かさない。
        位置・行間は SETTLEMENT_POPUP_PAD / SETTLEMENT_POPUP_LINE_H を使い、
        区画選択ポップアップの数値3行（_draw_popup_values()）と「3つの数字を
        縦に積む」という描画の形は同じだが、**共通化はしない**（値の意味が
        異なるため定数は共有しない。STATUS_LINE_H / POPUP_LINE_H が同じ値
        でも別に持つ判断と同じ）。右詰めの基準は POPUP_VALUE_MAX_DIGITS
        （7。区画選択ポップアップ専用）とは引き続き別だが、ステータスとは
        STATUS_VALUE_MAX_DIGITS を共有する"""
        before = self._money
        tax = self._field.total_tax()
        after = before - tax
        text_x = self.SETTLEMENT_POPUP_X + self.SETTLEMENT_POPUP_PAD
        text_y = self.SETTLEMENT_POPUP_Y + self.SETTLEMENT_POPUP_PAD
        value_area_x = (
            self.SETTLEMENT_POPUP_X
            + self.SETTLEMENT_POPUP_W
            - self.SETTLEMENT_POPUP_VALUE_RIGHT_GAP
            - self.STATUS_VALUE_MAX_DIGITS * self.FONT_CHAR_W
        )
        # 3行目（減算後。i == 2）だけ、横線との間に余白を空けて下へずらす
        row_y_offsets = (0, 0, self.SETTLEMENT_POPUP_RULE_TEXT_GAP)
        for i, num in enumerate((before, tax, after)):
            text = str(num)
            number_x = self._right_aligned_number_x(
                value_area_x, text, self.STATUS_VALUE_MAX_DIGITS
            )
            row_y = text_y + i * self.SETTLEMENT_POPUP_LINE_H + row_y_offsets[i]
            self._view.draw_text(number_x, row_y, text)
        rule_y = text_y + 2 * self.SETTLEMENT_POPUP_LINE_H - 1
        rule_w = self.SETTLEMENT_POPUP_W - 2 * self.SETTLEMENT_POPUP_PAD
        self._view.draw_rect(text_x, rule_y, rule_w, 1, self.SETTLEMENT_POPUP_RULE_COL)
        self._view.draw_text(text_x, text_y + self.SETTLEMENT_POPUP_LINE_H, "-")

    def _draw_game_end_popup(self):
        """終了（クリア／ゲームオーバー）ポップアップの背景・枠線・文言・
        「o」ボタンを、最前面（決算ポップアップのさらに後）へ描画する。
        表示するかどうかは self._game_end_state が NONE でないかだけで
        決まる（区画選択・決算のいずれとも別に持つ独立した状態）。
        クリアとゲームオーバーで変わるのは文言（_draw_game_end_popup_
        message()）だけで、枠・位置・大きさ・配色・ボタンは共通（案6）。
        いったん立った終了状態は本タスクの範囲では戻らないため（出口は
        ID-018 のリセットのみ）、精算済みで非表示になる決算ポップアップの
        ような中間の非表示状態は持たない——NONE でなければ常に表示する"""
        if self._game_end_state == GameEndState.NONE:
            return
        self._view.draw_rect(
            self.GAME_END_POPUP_X,
            self.GAME_END_POPUP_Y,
            self.GAME_END_POPUP_W,
            self.GAME_END_POPUP_H,
            self.GAME_END_POPUP_BG_COL,
        )
        self._view.draw_rectb(
            self.GAME_END_POPUP_X,
            self.GAME_END_POPUP_Y,
            self.GAME_END_POPUP_W,
            self.GAME_END_POPUP_H,
            self.GAME_END_POPUP_BORDER_COL,
        )
        self._draw_game_end_popup_message()
        self._draw_game_end_popup_button()

    def _draw_game_end_popup_message(self):
        """終了ポップアップ内の文言（1行）を、ポップアップ原点からの相対で
        描画する。self._game_end_state（CLEAR / GAME_OVER のいずれか。
        _draw_game_end_popup() が NONE を弾いた後にしか呼ばれない）から
        GAME_END_MESSAGE_CLEAR / GAME_END_MESSAGE_GAME_OVER のいずれかを選ぶ
        だけで、文言そのものの組み立て（数値の埋め込みなど）は持たない
        （決算ポップアップの数値3行と異なり、終了ポップアップは固定文言の
        みで盤面・資金の値を表示しない。要件に無い演出のため）"""
        message = (
            self.GAME_END_MESSAGE_CLEAR
            if self._game_end_state == GameEndState.CLEAR
            else self.GAME_END_MESSAGE_GAME_OVER
        )
        self._view.draw_text(
            self.GAME_END_POPUP_X + self.GAME_END_POPUP_PAD,
            self.GAME_END_POPUP_Y + self.GAME_END_POPUP_PAD,
            message,
        )

    def _game_end_popup_button_rect(self):
        """終了ポップアップ内の「o」ボタンの矩形 (x, y, w, h) を返す。文言
        1行（GAME_END_POPUP_PAD + GAME_END_POPUP_LINE_H）の直後に、内側
        余白 GAME_END_POPUP_PAD を挟んで置く。区画選択・決算の各ポップアップ
        と同じく、描画（_draw_game_end_popup_button()）だけでなく押下判定
        （_update_game_end_popup()。ID-018 でリセット起動に接続）からも
        呼ばれる——レイアウトの導出を1箇所にまとめる形も他の2つの
        ポップアップと揃っている"""
        btn_x = self.GAME_END_POPUP_X + self.GAME_END_POPUP_PAD
        btn_y = (
            self.GAME_END_POPUP_Y
            + self.GAME_END_POPUP_PAD
            + self.GAME_END_POPUP_LINE_H
            + self.GAME_END_POPUP_PAD
        )
        return btn_x, btn_y, self.GAME_END_POPUP_BTN_W, self.GAME_END_POPUP_BTN_H

    def _draw_game_end_popup_button(self):
        """終了ポップアップ内の「o」ボタン（矩形＋アイコン）を描画する。矩形は
        _game_end_popup_button_rect() から導く。決算ポップアップの
        _draw_settlement_popup_button() と同じく無効表示を持たない——
        押下すれば必ずリセットが起動し、押しても効かない状況（無効化すべき
        条件）自体が無いため「押せない見た目」を区別する理由が無く、常に
        塗りつぶしで描く。アイコンは矩形の中央へ寄せる（ID-026 サイクル
        026-3。文字から ICON_OK へ置き換え、他の2つのポップアップのボタンと
        同じ正確な中央揃えにした）"""
        btn_x, btn_y, btn_w, btn_h = self._game_end_popup_button_rect()
        self._view.draw_rect(btn_x, btn_y, btn_w, btn_h, self.GAME_END_POPUP_BTN_COL)
        self._draw_icon(
            btn_x + (btn_w - self.ICON_W) // 2,
            btn_y + (btn_h - self.ICON_H) // 2,
            *self.ICON_OK,
        )

    def _screen_to_plot(self, x, y):
        """画面座標 (x, y) を区画のグリッド座標 (col, row) へ変換する（区画外なら None）。
        _plot_origin() の逆変換であり、同じ原点（GRID_LEFT / FIELD_ORIGIN_Y）と
        同じ刻み（PLOT_SIZE / PITCH）を、引く・割るの向きで用いる。
        判定範囲は半開区間 [開始, 開始 + サイズ) で、縦は道路 ROAD_SIZE と区画
        PLOT_SIZE を合わせた 1 ピッチ全体を 1 行分とする。これは店舗画像の描画範囲
        （PLOT_SIZE × SHOP_H）と一致し、見えている店舗の絵がそのまま押せる範囲になる
        （選択枠はこれより道路 1 本分だけ縦に長い PREVIEW_H で描かれるため、
        枠の下端 8px は判定範囲の外側にあたる）。
        原点より左・上の座標は floor 除算で負の商になるため、下限 0 の判定だけで
        左右・上下いずれの範囲外も弾ける"""
        col = (x - self.GRID_LEFT) // self.PLOT_SIZE
        row = (y - self.FIELD_ORIGIN_Y) // self.PITCH
        if not (0 <= col < self.GRID_COLS and 0 <= row < self.GRID_ROWS):
            return None
        return col, row

    def _plot_origin(self, col, row):
        """区画のグリッド座標 (col, row) を、その区画に関わる描画・判定がすべて
        起点にする左上座標 (x, y) へ変換する。次の 4 つはこの 1 点を共有する。
          ・押下位置 → 区画の判定範囲（PLOT_SIZE × PITCH。_screen_to_plot()）
          ・店舗画像の描画範囲（SHOP_W × SHOP_H）
          ・選択中の区画を示す枠の範囲（PREVIEW_W × PREVIEW_H）
          ・売上の抽選が起きた店舗を囲む枠の範囲（PREVIEW_W × PREVIEW_H。
            **選択枠とまったく同じ大きさ**。同じ区画で両方が出たときは
            完全に重なり、後に描く選択枠だけが見える。_draw_sales_frame()）
        y は区画上部より ROAD_SIZE 分だけ上（区画上部の道路の上端に画像上部 8px が
        重なり、店舗が区画の上に建っているように見える）。
        **共通化できるのは原点だけで、大きさは 4 つのうち 2 通りに分かれる**
        （選択枠と売上の囲みが下の道路まで含む範囲へ広がったため、判定範囲・
        店舗画像の 24px とは別の 32px になった）。
        大きさはそれぞれの意味を表す定数で個別に持ち、原点だけをここへ集約する。
        原点を別々の式で書くと「押した場所」「見えている店舗」「枠の左上」が
        ずれてしまうため、必ずこの 1 つの導出を経由する。
        _screen_to_plot() の逆変換であり、同じ原点（GRID_LEFT / FIELD_ORIGIN_Y）と
        同じ刻み（PLOT_SIZE / PITCH）を、掛ける・足すの向きで用いる"""
        return (
            self.GRID_LEFT + col * self.PLOT_SIZE,
            self.FIELD_ORIGIN_Y + row * self.PITCH,
        )

    def _shop_transfer_src(self, owner, scale):
        """店舗規模・所有者から店舗画像の転送元 (u, v) を求める。scale は
        SHOP_SCALE_MIN..SHOP_SCALE_MAX（1..10）の範囲を前提とする。
        u は規模 n の起点（SHOP_U_ORIGIN）から SHOP_U_STEP（16px）刻みで
        右へ進み（規模ごとに絵柄が変わる）、v は所有者（NPC / プレイヤー）で
        段が切り替わる"""
        shop_u = self.SHOP_U_ORIGIN + self.SHOP_U_STEP * (scale - 1)
        shop_v = self.SHOP_V_PLAYER if owner == Owner.PLAYER else self.SHOP_V_NPC
        return shop_u, shop_v

    def _start_shop_clocks(self):
        """マップ上に店舗が1軒でもあれば（所有者は問わない）、起点を共有する
        タイマー（他店建設間隔・売上発生間隔）をまとめて開始する（要件 3.2
        「進行の条件は店舗が存在することのみとし、その所有者は問わない」。
        ID-025 決定1。開始条件そのもの——マップ上に店舗が1軒でもあるか——は
        Field.has_shop が答える）。呼び出し元は、店舗が現れ得る2つの
        経路——保存データからの復元（__init__）と建設
        （_build_selected_plot()）——の双方から同じ本メソッドを呼び、
        **呼び出し側は開始条件もタイマーの数も持たない**。買収
        （_buyout_selected_plot()）はここを呼ばないが、買収の対象は
        マップ上に既に店舗があるNPC所有店舗のため、その盤面を復元した
        時点で3タイマーは開始済みであり、呼ぶ必要そのものが無い。
        タイマーごとに開始メソッドを分けると、経路2箇所 × タイマーの数だけ
        呼び出しが並び、「リロードしたら売上だけ止まる」ように**片方だけ
        呼び忘れる経路が実装上作れてしまう**ため、一覧
        （self._shop_clocks）をここで回す形にした（ID-008 が申し送った
        「2件目が現れた時点で束ねる仕組みの要否を判断する」の決着。決算間隔
        （ID-014）が3件目として乗ったときも、増えたのは一覧（タプル）への
        1行だけだった。予告どおりであることを本メソッドの呼び出し側は
        1箇所も変わらずに確認できる）。
        ここが持つのは**開始条件だけ**で、開始が一度だけであることや未開始の
        表し方・復元の続き方は ShopClock 側にある（盤面を知るのは
        GameCore、タイマーの状態を知るのは ShopClock という分担）"""
        if not self._field.has_shop:
            return
        for clock in self._shop_clocks:
            clock.start()

    def _end_game(self, state):
        """ゲーム終了（クリア／ゲームオーバー）を成立させる: 終了状態を立て、
        凍結対象の4つのタイマー（保存・他店建設・売上・決算）を一時停止する
        （要件「ゲーム終了後」。ID-017 案5・サイクル4）。
        クリアが成立し得る経路は精算（_settle_tax()）の1つのみ（ID-028。
        かつては建設・買収も終了（クリア）を成立させ得たが、要件 3.16 の
        変更によりゲームクリアは「規定店舗数へ到達した状態で決算を通過する」
        ことでのみ成立するようになり、その判定は _settle_tax() だけが行う）。
        ゲームオーバーは2つの経路から成立し得る——精算（_settle_tax()。
        売り尽くしても不足額に届かない。ID-017）と、事業継続の判定
        （_check_business_continuation()。他店建設間隔ごとの建設・増資の
        直後（update()）と精算の直後の両方から呼ばれる。ID-024）。
        _start_shop_clocks() と同じく、呼び出し側は「何を止めるか」
        （self._freeze_clocks の中身）も「いくつ止めるか」も持たない
        ——止め忘れる経路を実装上作れないようにするため（タイマーが増えても
        呼び出し側は変わらない）。

        **再開（resume()）と対になっていない**唯一の pause() である。決算
        ポップアップの凍結は精算で必ず解けるが、終了の凍結を解く契機は
        存在しない（ゲームが終わっている以上、時間経過が再び始まることは
        無い。出口は ID-018 のリセットのみ）。クリア・ゲームオーバーの
        いずれも精算の中で起きるため、**_settle_tax() が凍結を解いた
        （resume() した）直後に本メソッドが掛け直す**形になる
        （_settle_tax() の docstring を参照）。

        **終了の直後に改めて保存はしない**。終了を成立させた操作そのものが
        保存を省くこと（_settle_tax() の docstring）に加え、ここで
        定期保存（_save_clock）も止まるが、止まった後はゲームの状態が変わり
        得ない（時間経過は止まり、押下由来の操作も受け付けない。update()）
        ため、保存すべき新しい変更がそもそも生まれない。
        なお凍結そのものは保存されない（保存キーは増えない。案3）ため、
        終了ポップアップの表示中にリロードすると、終了状態が消えるのと
        同時に4つのタイマーも通常どおり動き出す（＝ゲームが再開する。
        __init__ の self._game_end_state の注記と同じ、ID-018 への申し送り）"""
        self._game_end_state = state
        for clock in self._freeze_clocks:
            clock.pause()

    def _check_business_continuation(self):
        """事業継続の判定（要件 3.15）: プレイヤー所有店舗が0軒、かつ資金が
        最小取得費用（Field.min_acquisition_cost()）を下回るなら、事業を
        再開する手段が無いものとしてゲームオーバーを成立させる。

        他店建設間隔ごとの建設・増資の直後（update()）と、決算の精算完了
        直後（_settle_tax()）の2つの契機から同じ本メソッドを呼ぶ
        （ID-024_subtasks.md 決定4）。判定条件を契機ごとに直書きすると、
        条件が2箇所へ散り、片方だけ要件変更に追従し損なう経路を実装上
        作れてしまうため、呼び出し側は「終了を成立させたか」だけを受け取り、
        return するかどうかだけを決める。

        第1条件に Field.player_shop_count（内部状態を読むだけで盤面を
        走査しない。ID-028）を置くことで、and の短絡により
        Field.min_acquisition_cost()（盤面全体を走査する）は0軒のときにしか
        呼ばれない（決定2。要件「プレイヤー所有店舗が1つ以上ある場合は、
        この判定は行わない」を式の並びでそのまま表す）。金額を返すのは
        Field、資金と比べるのは GameCore という分担は、_cost_covered() が
        Field.get_cost() の返す費用を資金と比べる型と同じ（決定2）"""
        if (
            self._field.player_shop_count == 0
            and self._money < self._field.min_acquisition_cost()
        ):
            self._end_game(GameEndState.GAME_OVER)
            return True
        return False

    def _collect_sales(self):
        """売上発生間隔が満了したときの売上を1回行う（要件 3.3）。抽選そのものは
        Field（乱数源を持ち、店舗の並びを知る層）が行い、**選ばれた区画**を
        受け取ってから、その所有者による分岐と資金への加算をここで行う。
        売上額（Field.get_sales()）ではなく区画を返してもらうのは、額だけを
        受け取る形にすると「0」が「NPC所有だった」と「店舗が無かった」の
        両方を意味してしまうため。所有者による分岐がここにあるのは、資金が
        GameCore の持ち物であること（Field.grow_npc() のように Field 内で
        完結しない）と、区画の所有者で処理を分ける形が _update_popup() の
        「o」の分岐と同じ層に揃うことによる。
        抽選された区画は、**表示のために覚える**（_sales_plot）。囲み
        （_draw_sales_frame()）は資金と無関係に所有者を問わず付くため、
        代入は所有者による分岐の**外**に置く。ここを分岐の中に書くと、
        NPC所有店舗が抽選されたときに画面へ何も現れず、抽選が起きたこと自体が
        読み取れなくなる（要件 3.3 の対象は「抽選された店舗」であり、
        資金が増えた店舗ではない）。所有者で分かれるのは資金の加算だけ。
        盤面（所有者・規模）は売上では変わらない。資金が増えるだけのため、
        保存は定期保存（_save_clock）が拾う（プレイヤーの操作由来の変更
        （建設・増資・買収）が変更の直後に保存するのと異なり、**時間経過由来の
        変更は定期保存に一本化する**。他店建設 ID-008 と同じ扱い）。
        覚えた区画そのものは保存しない（要件 3.13 の保存対象に無く、失われても
        進行に差が出ない表示のための一時的な状態のため。リロード直後は囲みが
        無い状態から始まるが、売上発生間隔の残り時間は保存されているため、
        遅くとも間隔ぶん待てば必ず囲みが現れる）"""
        picked = self._field.pick_sales_shop()
        if picked is None:
            return
        col, row = picked
        self._sales_plot = picked
        if self._field.get_owner(col, row) == Owner.PLAYER:
            self._money += self._field.get_sales(col, row)

    def _save(self):
        self._report_store.save(self._get_save_data())

    def _get_save_data(self):
        """保存データ全体を組み立てる。Field は自分の区画分だけを提供し、
        全体の組み立て（資金・各タイマーなどの追加）は GameCore が担う。
        他店建設間隔・売上発生間隔・決算間隔の3つのタイマーいずれも、まだ
        開始していなければ None（未開始）、開始していれば満了までの残り時間を
        書き出す（ShopClock.remaining_ms() がその使い分けを持つ）。
        保存の周期（_save_clock）は残り時間を保存しない対象（再開時に新しく
        始めてよい）ため、ここには含めない。
        3件のタイマーの行は完全に同じ形（`<キー名>: <clock>.remaining_ms()`）
        で並ぶが、ループへは括らない（決算間隔が3件目として増えた本タスク
        （ID-014）で改めてこの判断を見直し、変えないと結論した。理由は
        _apply_load_data() の docstring にまとめて記す）。
        ゲームスピードの現在の段階（self._speed_index。GAME_SPEED_STEPS の
        添字）も "speed_index" として書き出す（ID-019 サイクル8）。残り時間
        （上記3件）は切り替え後のスピードの時間軸のまま書き出しており
        （等倍への再換算はしない）、この段階と組で復元して初めて元の状態が
        そのまま戻る"""
        return {
            "shops": self._field.get_save_data(),
            "money": self._money,
            "npc_growth_remaining_ms": self._npc_growth_clock.remaining_ms(),
            "sales_remaining_ms": self._sales_clock.remaining_ms(),
            "settlement_remaining_ms": self._settlement_clock.remaining_ms(),
            "speed_index": self._speed_index,
        }

    def _apply_load_data(self, data):
        """保存データがあればその店舗配置と資金を、なければ空マップと初期資金を
        適用する。_get_save_data() が組み立てるキーごとに、値の決め方（保存データが
        あればそれを、なければ既定値を）を1行ずつ揃えて書き、キーが増えたときの
        増やし方を対称に保つ。
        他店建設間隔・売上発生間隔の残り時間だけは .get() でキーの欠落を許す
        （shops / money と異なり、それぞれの間隔の導入前に保存されたデータには
        存在しないキーのため。欠落時は None＝未開始として扱われ、タイマーは
        対応する間隔（NPC_GROWTH_INTERVAL_MS / SALES_INTERVAL_MS）そのものから
        始まる＝進行中の店舗・資金は失わずにタイマーだけ最初からになる。
        ReportStore.VERSION は繰り上げない判断と対になる。ID-008 サイクル5
        Refactor で確立し、本メソッドで2件目として適用した）。
        決算間隔の残り時間だけは .get() を使わず data["settlement_remaining_ms"]
        で直接読む。ID-008 / ID-010 が VERSION を据え置いてキー欠落を許容
        したのに対し、本タスク（ID-014）は ReportStore.VERSION を 4 → 5 へ
        繰り上げる（ユーザーの明示的な指示による、既存の型からの意図的な
        逸脱。AGENTS.md の「原則逸脱の扱い」に従い、両論併記はせず繰り上げに
        一本化する）。VERSION が一致した保存データには settlement_remaining_ms
        が必ず存在するため .get() による欠落の手当ては不要——旧バージョンの
        保存データは ReportStore.load() がバージョン不一致の時点で None を
        返して読み捨てるため、このメソッドへ旧形式のデータが渡ることはない。
        既存2件の .get() はこの繰り上げに伴って変更しない。VERSION 繰り上げに
        より形式上は不要になるが、それらを書き換えるのは本タスクの完了条件の
        外側であり、差分に混ぜない（.get() と直接参照が1メソッドの中に混在する
        理由はここに記した経緯そのもの）。
        読み出した残り時間はタイマー自身へ預ける（開始は復元より後のため、
        ShopClock.apply_saved_remaining_ms() が start() まで控える）。
        3件のタイマーの保存・復元がまったく同じ形で並んだことは
        _start_shop_clocks() が一覧（_shop_clocks）を回す形へ
        束ねた判断（ID-008 が申し送った判断の決着）と対になるように見えるが、
        ここは束ねない。束ねた開始処理は「経路2箇所（復元・建設）× タイマーの
        数」だけ同じ呼び出しが離れた場所に並ぶことで片方だけ呼び忘れる経路が
        実装上作れたのに対し、保存・復元は1メソッドの中に1行ずつ並ぶだけで
        キーを書き忘れれば即座にテストが落ちる。呼び忘れが離れた場所に隠れる
        リスクが無いため、キー名がその場で読めるここでの明示的な1行ずつの形
        （ID-008 サイクル5 Refactor の確立した型）を、決算間隔が3件目として
        増えた本タスクでも改めて優先する（.get() と直接参照が混在しても、
        1行ずつの形自体は崩れない）。
        ゲームスピードの段階（speed_index）は .get() を使わず data["speed_index"]
        で直接読む。決算間隔（ID-014）と同じ理由・同じ型: 本タスク（ID-019）は
        ReportStore.VERSION を 6 → 7 へ繰り上げる（ID-018 の保存データと
        ID-019 の保存データは互換性が無いというユーザーの明示的な指示に
        よる、既存の型からの意図的な逸脱。AGENTS.md の「原則逸脱の扱い」に
        従い、両論併記はせず繰り上げに一本化する）。VERSION が一致した
        保存データには speed_index が必ず存在するため .get() による欠落の
        手当ては不要——旧バージョンの保存データは ReportStore.load() が
        バージョン不一致の時点で None を返して読み捨てるため、このメソッドへ
        旧形式のデータが渡ることはない。既存2件（他店建設間隔・売上発生
        間隔）の .get() はこの繰り上げに伴って変更しない（ID-014 が既に
        確立した判断そのもの。差分に混ぜない）。
        3タイマーの残り時間を預ける（apply_saved_remaining_ms()）**前**に
        _apply_speed_to_timers() を呼ぶ順序が重要: 3タイマー（ShopClock）は
        この時点でまだ未開始（start() は本メソッドの後で呼ばれる）であり、
        _apply_speed_to_timers() は未開始のタイマーの待機時間
        （_count_ms）を段階どおりへ差し替える（ShopClock.change_count_ms()
        の未開始分岐）。保存データの残り時間は保存時点のスピードの時間軸の
        まま（等倍へ再換算していない）であるため、待機時間を先に段階へ
        揃えたうえで残り時間をそのまま渡す——逆順（先に残り時間を
        預けてから _apply_speed_to_timers() を呼ぶ）だと、未開始分岐が
        保存値をもう一段スケールしてしまい、残り時間が二重にスケールされる
        （ShopClock.change_count_ms() は「未開始のまま保存値を控えて
        いれば、その値もスケールする」ため、既に段階が反映済みの値へ
        重ねて適用してしまう）"""
        self._speed_index = 0 if data is None else data["speed_index"]
        self._apply_speed_to_timers()
        shops = [] if data is None else data["shops"]
        self._money = self.INITIAL_MONEY if data is None else data["money"]
        self._npc_growth_clock.apply_saved_remaining_ms(
            None if data is None else data.get("npc_growth_remaining_ms")
        )
        self._sales_clock.apply_saved_remaining_ms(
            None if data is None else data.get("sales_remaining_ms")
        )
        self._settlement_clock.apply_saved_remaining_ms(
            None if data is None else data["settlement_remaining_ms"]
        )
        self._field.apply_load_data(shops)


class App:
    LOAD_WAIT_FRAMES = 10

    def __init__(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.init(GameCore.SCREEN_W, GameCore.SCREEN_H, title="pyxel_shop_grow")
        pyxel.load("images.pyxres")
        # マウス座標の追跡を有効化する（呼ばないと pyxel.mouse_x / mouse_y が常に 0 を
        # 返し、押下位置から区画を特定できない）
        pyxel.mouse(True)
        self._core = None
        self._wait_frames = 0
        pyxel.run(self.update, self.draw)

    def update(self):
        """_core の状態に応じて3つに分岐する: (1) 未生成なら LOAD_WAIT_FRAMES
        フレーム待ってから生成する、(2) 生成済みで needs_reset が立っていれば
        GameCore(reset=True) へ差し替える（ID-018。終了ポップアップの「o」
        ボタン押下を GameCore 側が検知した結果）、(3) それ以外は通常どおり
        _core.update() を呼ぶ。(2) は _core を None へ戻さず直接差し替える
        ため、リセット後に (1) の待機カウンタ（_wait_frames）を再び通ること
        はない"""
        if self._core is None:
            self._wait_frames += 1
            if self._wait_frames >= self.LOAD_WAIT_FRAMES:
                self._core = GameCore()
        elif self._core.needs_reset:
            self._core = GameCore(reset=True)
        else:
            self._core.update()

    def draw(self):
        import pyxel  # pylint: disable=W0621, C0415

        pyxel.cls(0)
        if self._core is not None:
            self._core.draw()


if __name__ == "__main__":
    App()
