from enum import Enum
from random_source import PyxelRandomSource  # pylint: disable=E0401


class Owner(Enum):
    NPC = 0
    PLAYER = 1


class Shop:
    # 1 区画に建つ店舗。設置直後は初期の店舗規模と、初期店舗設置費用と等しい
    # 資産価値を持つ。増資（規模変更・資産価値の加算）は ID-007 で invest() を
    # 追加した。買収（所有者変更）は更新用のメソッドを呼び手が現れる ID-009 で
    # 追加する
    INITIAL_SCALE = 1
    # 店舗規模の上限（登録済み画像の段階数に対応する境界）。「これ以上増資
    # できない」という増資（ID-007）の可否判定で初めて読まれる業務ルールでも
    # あり、店舗規模そのものの性質として Shop 側に置く（INITIAL_SCALE と同じ
    # 判断）。GameCore.SHOP_SCALE_MAX はこの値を参照で結び、値 10 を2箇所に
    # 書かない
    SCALE_MAX = 10
    # 初期店舗設置費用（建設費用）・増資費用・売上額の仮値と、買収費用の算出に
    # 使う倍率。いずれも「店舗にいくらかかるか」という店舗の知識のため Shop に
    # 置く。BUILD_COST は建てる前（空き区画）に参照されるが、インスタンスの
    # 有無と定数の帰属は別であり、要件 3.11「店舗の資産価値は、その店舗の
    # 初期店舗設置費用と、これまでに行った増資費用の合計」が設置費用と増資費用を
    # 同じ語彙で並べていることに合わせて、増資費用と同じ場所に置く。
    # BUYOUT_RATE は「買収費用そのもの」ではなく「資産価値に掛ける倍率」で
    # あることを名前で示す（_compute_cost() が self._value * BUYOUT_RATE を
    # 返す。資産価値は店舗ごとに異なるため、費用そのものを定数として持てない）。
    # 中心売上倍率（要件 3.10。ID-020）の指数。中心売上倍率＝地域価格倍率の
    # CENTER_SALES_EXPONENT 乗で、地域価格倍率が直接効く費用・資産価値とは
    # 別に、売上額にはこの指数乗が効く（中心地ほど売上面で優位になる）。
    # SALES_AMOUNT と同じく「この店舗がいくら稼ぐか」を決める定数のため
    # Shop に置く（盤面全体の集計に掛かる ASSET_TAX_RATE_PERCENT を Field に
    # 置いた判断と対になる）。要件 3.10 が「ゲームバランスの調整対象とする」
    # と明記する調整対象の定数（初期値 2）
    CENTER_SALES_EXPONENT = 2
    # SALES_AMOUNT は「所有者・店舗規模によらず一律の売上額」ではなく、
    # INVEST_COST（規模1の店舗を増資する基準額）と同じく「規模1・等倍の区画の
    # 店舗の売上額（基準額）」を指す（_compute_sales() が
    # self.SALES_AMOUNT * 2 ** (self._scale - 1) に中心売上倍率を掛けて返す。
    # 規模が上がるほど売上額も指数的に増える）。
    # 建設費用は ID-006、増資費用は ID-007、買収費用は ID-009、売上額は
    # ID-010 で、いずれも算出ロジックへ置き換え済み
    BUILD_COST = 100
    INVEST_COST = 150
    BUYOUT_RATE = 2
    SALES_AMOUNT = 50
    # 地域価格倍率（要件 3.10。ID-020）の等倍（1.0）を表す千分率の基準値。
    # 中心 3.0 倍・外周 1.0 倍を 3000/1000 のように整数で持つ（設計判断は
    # ID-020_subtasks.md 決定4）。Field.AREA_RATE_EDGE はこの値を基準に導出する
    # （Field → Shop という既存の一方向の参照を保つため。Field は既に
    # BUILD_COST / SCALE_MAX を参照しており、逆向きの参照は無い）
    AREA_RATE_BASE = 1000

    def __init__(self, owner, area_rate):
        self._owner = owner
        self._scale = self.INITIAL_SCALE
        # 店舗は自身の区画座標を知らないため、地域価格倍率（座標のみから決まる。
        # 要件 3.10）は Field が算出し、生成時に受け取ってインスタンス状態として
        # 持つ（ID-020_subtasks.md 決定5・案2-B）。デフォルト値は与えない
        # ——与えると渡し忘れた経路の店舗だけ等倍のまま作られてしまう
        # （資産価値を呼び手から受け取らない下記と同じ、渡し忘れを実装上
        # 作れなくするための判断）
        self._area_rate = area_rate
        # 設置直後の資産価値は、地域価格倍率を反映した初期店舗設置費用と等しい
        # （要件 3.11 の増資 0 回の状態）。**資産価値に設置費用が入るのは店舗が
        # 建つことそのものの性質**であり、誰が建てたか（プレイヤーの建設／NPC の
        # 建設 ID-008）にはよらないため、呼び手から受け取らずここで決める
        # （受け取る形にすると、渡し忘れた経路の店舗だけ資産価値 0 のまま
        # 地価 ID-013 の算出に混ざる）。
        # 丸め(切り捨て)は金額を得るこの箇所で1回だけ行う(ID-020 決定4)——増資
        # のたびに invest() が同じ単位で丸めた増資費用を積み上げるため、
        # 資産価値は常に「丸めた後の費用の合計」になる(要件 3.12)
        self._value = self.BUILD_COST * area_rate // self.AREA_RATE_BASE
        # 費用・売上額は、資産価値と同じく**都度算出せず、生成時に1回だけ
        # 計算してインスタンス状態として持ち回る**（cost / sales プロパティは
        # 本フィールドを返すだけ）。ID-007・ID-010 は逆に持ち回りを廃して都度
        # 導出へ移したが、ID-020 で地域価格倍率が式へ入り、区画選択ポップアップ
        # やステータス表示がフレームごとに読み得る値に規模・倍率の指数乗が
        # 含まれるようになったため、負荷を理由に持ち回りへ戻した。廃止の理由
        # だった「規模を上げる処理と値を更新する処理が別々に呼べてしまう」穴は、
        # 導出結果が変わり得る箇所——規模（invest()）・所有者（buyout() /
        # sell()。cost の NPC分岐のみ）・復元（restore()）——のいずれでも同じ
        # メソッドの中で再計算することで塞ぐ（詳細は各メソッドの docstring）
        self._cost = self._compute_cost()
        self._sales = self._compute_sales()

    @classmethod
    def restore(cls, save_data, area_rate):
        """保存データ（get_save_data() が返す並び）から店舗を組み立てる。
        設置（初期の店舗規模と設置費用ぶんの資産価値での生成）とは経路を分け、
        増資を重ねた後の任意の店舗規模・資産価値を持つ店舗を作れるのは復元の
        ときだけであることを名前で示す。
        area_rate は保存データには含まれない（座標から都度導出できるため
        保存キーを増やす必要が無い。ID-012 の重み・ID-013 の地価と同じ扱い）。
        呼び手（Field.apply_load_data()）が座標から算出して渡す。
        **保存データの資産価値スロットは、地域価格倍率を反映した実額を載せる**
        （ID-020 ステップ 020-2。設計方針7——「資産価値が倍率込みの実額に
        なる」ことが ReportStore.VERSION を 7→8 へ繰り上げた理由そのもの）。
        したがって復元でも保存された値をそのまま _value へ戻す。規模と倍率から
        解き直さないのは、_total_shop_value() の docstring が述べる理由と
        同じ——保存データの資産価値が式どおりとは限らず、解き直すと保存データの
        値と食い違うため"""
        owner, scale, value = save_data
        shop = cls(Owner(owner), area_rate)
        shop._scale = scale
        shop._value = value
        # 費用・売上額は、復元した規模・所有者・地域価格倍率・資産価値から
        # ここで1回だけ計算して持ち回る（__init__() と同じキャッシュ方針。
        # _compute_cost() / _compute_sales() はインスタンスメソッドだが、
        # この時点で owner / scale / area_rate / value がすべて揃っている
        # ため、生成済みの shop に対してそのまま呼べる）
        shop._cost = shop._compute_cost()
        shop._sales = shop._compute_sales()
        return shop

    def get_save_data(self):
        """1 区画分の保存データを組み立てる。所有者は JSON で扱えるよう整数で載せる
        （Owner のままでは json.dumps() が扱えない）。
        資産価値は地域価格倍率を反映した実額を載せる（ID-020 ステップ 020-2。
        restore() の docstring を参照）"""
        return [self._owner.value, self._scale, self._value]

    @property
    def owner(self):
        return self._owner

    @property
    def scale(self):
        return self._scale

    @property
    def value(self):
        """店舗の資産価値（要件 3.11）を返す。地域価格倍率を反映した建設費用に、
        増資のたびに倍率反映後の増資費用を積んだ額（都度導出せずインスタンス
        状態として保持する保持値。ID-020）"""
        return self._value

    @property
    def area_rate(self):
        """生成時に受け取った地域価格倍率（千分率の整数。要件 3.10）を返す。
        座標から都度算出し直すのではなく、生成時に受け取った値をそのまま
        持ち回る（区画は動かないため結果は同じになるが、区画の位置という
        Shop が知らない情報から都度導き直すのではなく、Field から渡された
        値を保持するという設計判断——ID-020_subtasks.md 決定5——をそのまま表す）。
        owner / scale / value（既存3プロパティ）の後ろに置くのは、これらが
        店舗の設置以来ずっと持ち回っている状態であるのに対し、area_rate は
        本タスク（ID-020）で新設した値であることを並び順でも示すため"""
        return self._area_rate

    @property
    def cost(self):
        """区画を選んだプレイヤーに見せる費用（増資／買収）を返す。**費用は
        存在しないことがあり**、その場合は None を返す（規模が上限の
        プレイヤー所有店舗は増資できないため増資費用が存在しない。要件 3.6。
        条件は _compute_cost() を参照）。算出は行わず、
        生成・復元時と規模・所有者が変わるたび（invest() / buyout() / sell()）に
        更新している _cost をそのまま返す（都度計算しない理由は __init__() の
        docstring を参照）。式そのものは _compute_cost() にある。
        invest() はこの値を使わない（ID-008。NPC の増資に買収費用を混ぜない
        ため。詳細は invest() の docstring）。プレイヤーの増資では
        GameCore._invest_selected_plot() が変更前に本プロパティを読んで資金
        から減算しており、その値は invest() が計算する増資費用の式（所有者が
        プレイヤーのときの _compute_cost() と同じ式）と一致する"""
        return self._cost

    def _compute_cost(self):
        """cost の算出式。プレイヤー所有店舗は増資費用に地域価格倍率
        （area_rate）を反映した `INVEST_COST × 2^(規模-1) × 倍率 //
        AREA_RATE_BASE`（丸めは切り捨て。金額を得るこの箇所で1回だけ丸める。
        ID-020_subtasks.md 決定4）。NPC所有店舗（買収費用）は「資産価値
        （value） × BUYOUT_RATE」（ID-009 で資産価値ベースの導出へ移した式）。
        value は既に倍率を反映した保持値のため、ここでは追加で倍率を掛けない
        ——資産価値経由で自動的に倍率が乗る（ID-020 設計方針5 の想定どおり）。
        BUYOUT_RATE 自体は変えない。
        ただしプレイヤー所有店舗の規模が上限（SCALE_MAX）に達している場合は
        増資できず、**その店舗に対する増資費用は存在しない**（要件 3.6）ため
        None を返す。費用が「いくらか」ではなく「存在するか」は店舗そのものの
        性質のため、規模と上限の両方を持つこのクラスで決め、Field は relay し、
        「-」という表示上の記号は描画側（GameCore.POPUP_NO_COST_TEXT）が決める。
        規模が上限でも**NPC所有店舗は買収できる**（要件 3.7）ため、買収費用は
        数値のまま返す——判定をプレイヤー所有の内側に置くのはこのため。
        呼び手（__init__() / restore() / invest() / buyout() / sell()）が
        結果を _cost へ書き込む。規模・所有者が変わるたびに呼び直されるため、
        増資で規模が上限へ達した直後や、規模が上限のNPC所有店舗を買収した
        直後に、費用が数値と不在の間で切り替わる。
        本メソッド自身は Shop の状態を変えない"""
        if self._owner == Owner.PLAYER:
            if self._scale >= self.SCALE_MAX:
                return None
            return (
                self.INVEST_COST
                * 2 ** (self._scale - 1)
                * self._area_rate
                // self.AREA_RATE_BASE
            )
        return self._value * self.BUYOUT_RATE

    @property
    def sales(self):
        """店舗が1回の売上で稼ぐ額を返す。算出は行わず、生成・復元時と規模が
        変わるたび（invest()）に更新している _sales をそのまま返す（都度
        計算しない理由は __init__() の docstring を参照）。式そのものは
        _compute_sales() にある"""
        return self._sales

    def _compute_sales(self):
        """sales の算出式。店舗規模に応じた基準額（SALES_AMOUNT ×
        2^(規模-1)）に、**中心売上倍率**（地域価格倍率の
        CENTER_SALES_EXPONENT 乗）を掛けて返す。地域価格倍率は千分率の整数で
        持つため、指数乗した分母（AREA_RATE_BASE ** 指数）で割ることで倍率を
        戻す。**中間の倍率（self._area_rate 自体）は丸めない**——先に千分率へ
        丸めてから指数乗すると、規模・倍率の組み合わせによって最大十数の
        誤差が生じることを確認済み（ID-020_subtasks.md 決定4）。丸め
        （切り捨て）は金額を得るこの箇所で1回だけ行う。
        所有者では値が変わらない点が cost と異なる（売上金が資金に入るかは
        所有者で決まるが、それは抽選側の話であり売上額そのものの性質ではない）。
        基準額の形（定数 × 2^(規模-1)）は増資費用（_compute_cost() の
        INVEST_COST 側）と同じだが、共通化はしない。同じなのは偶然であり、
        増資費用の伸び方と売上額の伸び方は別々の理由で決まる（増資費用は投資の
        重さ、売上額は店舗の稼ぐ力）。片方を調整したときにもう片方が連動して
        動くのは意図と逆になるため、式は別々に書く。売上額に効くのが地域価格
        倍率そのものではなく中心売上倍率である点も、両者を別々に保つ理由に
        なっている（ID-020 サイクル 020-1-5）。
        呼び手（__init__() / restore() / invest()）が結果を _sales へ
        書き込む。本メソッド自身は Shop の状態を変えない"""
        return (
            self.SALES_AMOUNT
            * 2 ** (self._scale - 1)
            * self._area_rate**self.CENTER_SALES_EXPONENT
            // self.AREA_RATE_BASE**self.CENTER_SALES_EXPONENT
        )

    def invest(self):
        """店舗規模を1段階上げ、増資費用（INVEST_COST × 2^(規模-1)）を資産価値へ
        加算する。所有者を問わない（プレイヤーの増資 ID-007・NPC の増資 ID-008
        いずれも同じ算出式。要件 3.4 の「増資」は所有者を区別しない）。規模と
        資産価値の変更を1つのメソッドにまとめているのは、呼び手が2件になっても
        「規模だけ上げて資産価値の加算を忘れる」経路を実装上作れないように
        するため。
        cost プロパティ（区画を選んだプレイヤーに見せる費用。所有者が NPC の
        ときは資産価値ベースの買収費用 ID-009 を返す）は使わない。cost をそのまま使うと
        NPC の増資額が買収費用（規模に依存しない定数）になってしまい、増資
        費用の算出式が所有者によって変わってしまう。呼び手が2件（プレイヤーの
        増資・NPC の増資）になった ID-008 の時点で確認したところ、共通なのは
        この状態変更（invest() 自体）だけで、起点・可否条件・資金の有無は
        呼び出し元（GameCore._invest_selected_plot() / Field.grow_npc()）ごとに
        異なる。それ以上の共通抽象（可否判定や呼び出し方をまとめる層）は
        作らない（ID-007 が建設と増資の共通化を見送った判断と同じ材料）。
        資産価値へ積むのは**地域価格倍率を反映した増資費用**（INVEST_COST ×
        2^(規模-1) × 倍率 // AREA_RATE_BASE。ID-020）。丸め（切り捨て）は
        __init__() が建設費用を丸めるのと同じ単位・同じ向きで行い、資産価値が
        常に「丸めた後の費用の合計」であるという要件 3.12 の関係を保つ。
        _cost / _sales（いずれも規模に依存する。__init__() の docstring を
        参照）も規模を上げた直後に再計算して書き直す。持ち回り（都度計算
        しない設計）を採る以上、規模が動くこのメソッドで更新し忘れると値が
        古いまま固定される——ID-007・ID-010 が持ち回りを廃止した理由（規模を
        上げる処理と値を更新する処理が別々に呼べてしまう）と同じ穴を、
        資産価値の加算と同じ1つのメソッドに閉じ込めて塞ぐ"""
        invest_cost = self.INVEST_COST * 2 ** (self._scale - 1)
        self._value += invest_cost * self._area_rate // self.AREA_RATE_BASE
        self._scale += 1
        self._cost = self._compute_cost()
        self._sales = self._compute_sales()

    def buyout(self):
        """店舗の所有者をプレイヤーへ変更する。店舗規模・資産価値は変えない
        （invest() が規模と資産価値を対で変えるのと異なり非対称になる）。
        要件 3.11 は資産価値を初期店舗設置費用と増資費用の合計と定めており
        買収費用はその構成要素ではないため、資産価値には触れない。
        引数を取らないのは、買収が常にプレイヤーへの変更であり、「NPC へ戻す」
        呼び手のための一般化はしないため。**その「NPC へ戻す」経路は
        sell()（税金不足時の売却 ID-016）として別途実装している**——買収と
        売却をそれぞれ一方向にのみ変更する専用メソッドとして分け、共通化は
        しない。一般化した1メソッド（例: set_owner(owner)）にすると、買収なのか
        売却なのか意図が名前から消え、呼び手ごとの前提（買収は NPC 所有・
        売却はプレイヤー所有であることを呼び出し側が保証する）も1メソッドの
        中へ紛れ込む。
        _cost（NPC所有店舗の買収費用分岐——value × BUYOUT_RATE——を持つ。
        _compute_cost() を参照）は所有者に依存するため、所有者を変えた直後に
        再計算して書き直す。買収後は cost がプレイヤー所有分岐（増資費用）へ
        切り替わる。_sales は所有者に依存しないため更新しない"""
        self._owner = Owner.PLAYER
        self._cost = self._compute_cost()

    def sell(self):
        """店舗の所有者を NPC へ変更する（税金不足時の売却 ID-016）。buyout() の
        逆向きで、店舗規模・資産価値は変えない（buyout() と同じ非対称。要件
        3.11 の資産価値の構成要素——初期店舗設置費用と増資費用の合計——に
        所有者は含まれないため）。
        引数を取らない理由は buyout() と同じ（売却が常に NPC への変更であり、
        一般化した「所有者を変更する」呼び手のための共通化はしない）。
        _cost は buyout() と同じ理由で再計算する（売却後は cost が買収費用
        分岐——value × BUYOUT_RATE——へ切り替わる）"""
        self._owner = Owner.NPC
        self._cost = self._compute_cost()


class Field:
    # マップの区画数（列数・行数）。画面上どこにどう配置するか（ピクセル座標・
    # 余白）は GameCore（画面レイアウト）の責務だが、区画が何列何行あるかは
    # 「区画ごとの状態を保持する」という Field 自身の役割に含まれる（Field は
    # 画面座標を知らなくても、盤面の大きさは知ってよいという整理。ID-008）。
    # GameCore.GRID_COLS / GameCore.GRID_ROWS はこの値を参照する（画面レイアウト
    # は、この区画数がちょうど収まるように選んだ値になっている）
    GRID_COLS = 18
    GRID_ROWS = 15
    # 全区画数。地価（_land_price()）が「マップ1区画あたりの平均資産価値」を
    # 求める際の割る数として使う（ID-013）。値 270 を直接書かず GRID_COLS ×
    # GRID_ROWS から導出することで、区画数が変わっても地価の式を書き換えずに
    # 追従する
    GRID_PLOT_COUNT = GRID_COLS * GRID_ROWS
    # 資産税率（パーセント。ID-014）。プレイヤー所有店舗の資産価値総額に掛けて
    # 資産税を求める（total_tax() 参照）。整数パーセントで持つのは、資金・
    # 費用・売上額・地価がすべて整数であり、税額の算出にここで初めて小数を
    # 持ち込む理由が無いため（除数を定数化する案・浮動小数で持つ案はいずれも
    # 却下——「何%の税か」が値から直接読めなくなる／このコードベースに小数を
    # 初めて持ち込む）。盤面全体の集計に掛かる値であり、店舗単体の知識である
    # Shop の費用定数群（BUILD_COST など）ではなく、同じく盤面全体に掛かる
    # GRID_PLOT_COUNT と同じ Field に置く。値 5（5%）は仮値で、BUILD_COST /
    # INVEST_COST / SALES_AMOUNT / INITIAL_MONEY / BUYOUT_RATE と同じく、収支が
    # 揃う ID-015 以降で再調整する前提（そのとき動かすのは GRID_PLOT_COUNT
    # ではなく税率と各費用側。_land_price() の docstring 参照）
    ASSET_TAX_RATE_PERCENT = 5
    # 地域価格倍率（要件 3.10。ID-020）の中心地・最も外側の区画の値
    # （千分率の整数。3.0 → 3000 / 1.0 → 1000）。中心地の区画は
    # AREA_RATE_CENTER、盤面上の最大距離の区画は AREA_RATE_EDGE になる
    # （_area_rate() 参照）。AREA_RATE_EDGE は Shop.AREA_RATE_BASE を基準に
    # 導出する（Field → Shop という既存の一方向の参照を保つため）
    AREA_RATE_CENTER = 3000
    AREA_RATE_EDGE = Shop.AREA_RATE_BASE
    # 地域価格倍率の算出に使う中心地・最大距離（ID-020_subtasks.md 決定1・2・3）。
    # 盤面（GRID_COLS × GRID_ROWS）は列数が偶数・行数が奇数のため、行方向の
    # 中心は1行（_CENTER_ROW）に定まるが、列方向は隣り合う2列（_CENTER_COL_LOW /
    # _CENTER_COL_HIGH）の中間になり1列に定まらない。距離はチェビシェフ距離
    # （列方向は2つの中心列への最小距離、行方向は中心行との差、そのうち大きい
    # 方）とし、値 8 / 9 / 7 を直書きせず GRID_COLS / GRID_ROWS から導出する
    _CENTER_COL_LOW = (GRID_COLS - 1) // 2
    _CENTER_COL_HIGH = GRID_COLS // 2
    _CENTER_ROW = GRID_ROWS // 2
    # 盤面上の距離の最大値（四隅の区画の距離と一致する）。列方向の距離の最大は
    # 盤面の両端（列0・列 GRID_COLS-1）、行方向の距離の最大は盤面の両端
    # （行0・行 GRID_ROWS-1）でそれぞれ生じるため、両者のうち大きい方を取る
    AREA_MAX_DISTANCE = max(
        _CENTER_COL_LOW,
        (GRID_COLS - 1) - _CENTER_COL_HIGH,
        _CENTER_ROW,
        (GRID_ROWS - 1) - _CENTER_ROW,
    )
    # ゲームクリアの規定店舗数（要件3.16。ID-028）。プレイヤー所有店舗数が
    # この値へ到達し、その状態で決算を通過するとクリアになる（判定は
    # GameCore 側。is_clear_shop_count_reached はここでは到達のみ答える）。
    # 仮値100はプレイテストで調整する前提（ID-028_subtasks.md 決定1）
    CLEAR_SHOP_COUNT = 100

    def __init__(self):
        # 店舗のある区画のみを (col, row) をキーに保持し、
        # 空き地はキーが存在しないことから導出する
        self._shops = {}
        # 抽選（ID-008 の他店建設、後続の売上 ID-010・売却 ID-016）の出どころ。
        # グローバルな乱数をここで直接呼ぶ形にすると、pyxel への依存が field.py へ
        # 持ち込まれ（field.py に pyxel の import は1つも無い）、テストも実行の
        # たびに結果が揺れる。境界（IRandomSource）越しに使うことで、Field は
        # 乱数の実装を知らないまま抽選を行える。
        # 生成は GameCore が IView / IInput を PyxelView.create() / PyxelInput.create()
        # で用意するのと同じ形で、**使う側が自分で行う**（引数で渡さない）。
        # テストは create() を差し替えることで決定的な実装に置き換えられるため、
        # 引数で受け取らなくても差し替えは効く。生成の形を揃えることで、Field()
        # の生成契約は引数なしのまま保たれる
        self._random_source = PyxelRandomSource.create()
        # 税金不足時の売却（ID-016）で、直近の sell_shops_for_shortfall() 呼び出しが
        # 不足額を満たせたか（ID-017 案2）。shortfall_covered プロパティ越しに
        # 読む。既定は True（＝まだ一度も売却が起きていない状態を「不足なし」
        # として表す）。売却が一度も呼ばれないまま読まれても「まだ不足していない」
        # という自然な答えになり、Field() の生成直後や復元直後（ID-017 案3。
        # 終了状態は保存も復元時の再判定もしない）に不定値を返すことがない
        self._shortfall_covered = True
        # マップ上のプレイヤー所有店舗の軒数（ゲームクリアの判定
        # is_clear_shop_count_reached とプレイヤーステータスの店舗数表示の
        # 両方が読む値。ID-028_subtasks.md 決定2・案2-C）。
        # player_shop_count プロパティ越しに読む。既定は0（＝店舗が1軒も
        # 無い盤面と同じ答え。Field() の生成直後の値として自然）。
        # set_shop() / buyout_shop() / _sell_player_shop() / apply_load_data()
        # （プレイヤー所有店舗数が変わり得る4つの経路。決算のたびに再評価
        # される判定であるため、復元（apply_load_data()）でも更新する——
        # shortfall_covered とは異なり、終了状態そのものではなく現在の
        # 軒数という盤面の一部を表す値であるため——決定2）の直後に
        # _update_player_shop_count() で更新する
        self._player_shop_count = 0

    @property
    def shortfall_covered(self):
        """直近の sell_shops_for_shortfall() 呼び出しで、渡された不足額
        （shortfall）を売却で満たせたか（raised >= shortfall）を返す
        （ID-017 案2）。sell_shops_for_shortfall() の**戻り値としてではなく
        本プロパティとして分離して持つ**——sell_shops_for_shortfall() を
        「不足額ぶんを売却し、調達額を返す」という単一の機能に保つため、
        「満たせたか」という副次的な答えを戻り値に混ぜない（呼び手が
        タプルを毎回アンパックする負担も避けられる）。
        呼び手（GameCore._settle_tax()）は
        `raised = self._field.sell_shops_for_shortfall(-self._money)` で
        調達額を受け取って資金を更新した**後**、必要なときだけ
        `self._field.shortfall_covered` を読む（ゲームオーバー判定への
        反映はサイクル3で配線する。本メソッド自身は「不足額を満たせたか」
        を答えるのみで、ゲームオーバーという業務上の意味付けは持たない）。
        売却が一度も起きていない間（Field() の生成直後）は True を返す
        （__init__ を参照）"""
        return self._shortfall_covered

    @property
    def player_shop_count(self):
        """マップ上のプレイヤー所有店舗の軒数（ゲームクリアの判定
        （is_clear_shop_count_reached）とプレイヤーステータスの店舗数表示の
        両方が読む値。要件 3.16・4章「プレイヤーステータス」。ID-028）を
        返す。
        **算出そのものではなく、内部状態（self._player_shop_count）を
        読むだけのプロパティとして持つ**（shortfall_covered と同じ、
        コマンドとクエリの分離。ID-028_subtasks.md 決定2・案2-C）。算出は
        set_shop() / buyout_shop() / _sell_player_shop() / apply_load_data()
        （プレイヤー所有店舗数が変わり得る4つの経路）の末尾で
        `_update_player_shop_count()` が行い、その結果を本プロパティが
        読む。増資（invest_shop()）は所有者を変えないため算出を行わない。
        **復元（apply_load_data()）でも更新する**——本プロパティは判定
        だけでなく常時のステータス表示にも使われるため、復元直後から
        実際の盤面と一致している必要がある（決定2）。
        店舗が1軒も無い盤面（Field() の生成直後を含む）は0を返す
        （__init__ を参照）"""
        return self._player_shop_count

    @property
    def is_clear_shop_count_reached(self):
        """プレイヤー所有店舗が規定店舗数（CLEAR_SHOP_COUNT）へ到達している
        か（ゲームクリアの判定。要件 3.16。ID-028）を返す。
        **内部状態を持たず都度算出する**（`player_shop_count >=
        CLEAR_SHOP_COUNT`）。真偽値そのものの更新経路を持たないため、
        player_shop_count の更新（4経路）を1つ漏らした場合に生じる
        不整合が本プロパティ自身には生じ得ない（決定2・案2-C。呼び手は
        GameCore._settle_tax() の末尾——決算の精算完了直後、ゲームオーバー
        判定の後——に置く。サイクル 028-2）"""
        return self.player_shop_count >= self.CLEAR_SHOP_COUNT

    @property
    def has_shop(self):
        """マップ上に店舗が1軒でもあるか（所有者を問わない）を返す
        （要件 3.2。時間経過処理の開始条件——GameCore._start_shop_clocks()
        ——が読む値。ID-025 決定1）。
        **player_shop_count とは異なり所有者を問わない**ため、それを流用
        せず self._shops から独立に答える。**内部状態を持たず、self._shops
        の要素数から都度算出する**（`bool(self._shops)`）。is_clear_shop_
        count_reached が真偽値の状態を持たず都度算出するのと同じ理由——
        更新経路（set_shop() / buyout_shop() / _sell_player_shop() /
        apply_load_data()）を1つ増やす必要がなく、更新漏れによる不整合が
        生じ得ない。店舗は売却されても NPC 所有になるだけで self._shops の
        キーが消えない（_sell_player_shop()）ため、**一度真になったら
        偽へ戻らない**"""
        return bool(self._shops)

    def _update_player_shop_count(self):
        """player_shop_count プロパティが読む内部状態
        （self._player_shop_count）を、現在の盤面から再計算して書き込む。
        set_shop() / buyout_shop() / _sell_player_shop() の末尾（プレイヤー
        所有店舗数が変わり得る3つの操作）と、apply_load_data() の末尾
        （復元でも更新する——決定2）で呼ぶ。
        既存の走査ヘルパー _count_player_shops()（当初 total_tax() 専用
        だった内部ヘルパー。ID-020）をそのまま流用する"""
        self._player_shop_count = self._count_player_shops()

    def set_shop(self, col, row, owner):
        """区画へ店舗を設置する。Field が持つのは「どの区画に店舗があるか」だけで、
        設置直後の店舗規模・資産価値がいくつになるかは Shop 自身が決める。
        設置後に player_shop_count の内部状態を更新する（プレイヤーの
        建設だけでなく、grow_npc() 越しのNPC建設でも呼ばれるため、owner を
        問わず常に更新する。owner=NPC のときは player_shop_count が
        増えないだけで、更新自体を省く理由にはならない）"""
        self._shops[(col, row)] = Shop(owner, self._area_rate(col, row))
        self._update_player_shop_count()

    def get_owner(self, col, row):
        shop = self._shops.get((col, row))
        return None if shop is None else shop.owner

    def get_scale(self, col, row):
        shop = self._shops.get((col, row))
        return None if shop is None else shop.scale

    def get_value(self, col, row):
        """区画の資産価値を返す。空き区画は None、店舗があればその店舗の
        資産価値（地域価格倍率を反映した建設費用 ＋ Σ 倍率を反映した増資費用。
        要件 3.10・3.12）を返す"""
        shop = self._shops.get((col, row))
        return None if shop is None else shop.value

    def get_cost(self, col, row):
        """区画の費用（建設／増資／買収）を返す。空き区画はこれから建てる店舗の
        建設費用、店舗があればその店舗の費用（増資／買収費用）を返す。
        いずれも**その区画の地域価格倍率（要件 3.10）を反映した額**で、
        中心地ほど高くなる。
        空き区画の建設費用だけは Field 側で算出する（Shop.BUILD_COST ×
        その区画の倍率 // Shop.AREA_RATE_BASE。丸めは切り捨てで、金額を得る
        この箇所で1回だけ行う。ID-020_subtasks.md 決定4）——まだ Shop が
        存在せず倍率を保持する相手がいないため。店舗がある場合は値を決めるのは
        Shop 側（cost）で、Field は区画の状態で選ぶだけ。
        **費用は存在しないことがあり**、その場合は None を返す（規模が上限の
        プレイヤー所有店舗は増資できないため。要件 3.6）。ここで握り潰さず
        そのまま relay するのは、費用が存在するかを決めるのが店舗そのものの
        性質であり、区画の状態で値を選ぶだけという本メソッドの役割の外に
        あるため（get_value() が空き区画で None を返すのと同じ形で、値の不在は
        None で表し、見せ方は呼び手が決める）"""
        shop = self._shops.get((col, row))
        if shop is None:
            return Shop.BUILD_COST * self._area_rate(col, row) // Shop.AREA_RATE_BASE
        return shop.cost

    def get_sales(self, col, row):
        """区画の売上額を返す。空き区画は 0、店舗があればその店舗の売上額
        （中心売上倍率——地域価格倍率の Shop.CENTER_SALES_EXPONENT 乗——を
        反映した額。要件 3.10）を返す"""
        shop = self._shops.get((col, row))
        return 0 if shop is None else shop.sales

    def min_acquisition_cost(self):
        """そのときマップ上で取得できる区画の費用のうち最も安いものを返す
        （要件 3.15）。対象は「空き区画の建設費用」と「NPC所有店舗の買収
        費用」で、いずれも get_cost() をそのまま読む——新しい金額の式は
        1つも作らない（ID-024_subtasks.md 決定3）。プレイヤー所有店舗は
        既にプレイヤーが所有しており取得の対象ではないため除外する
        （増資費用が存在するかどうかは問わない）。
        盤面全体（GRID_COLS × GRID_ROWS）を走査する専用の列挙をここに持つ。
        _list_npc_growth_targets() は「店舗に隣接する空き区画」のみに絞り、
        規模が上限のNPC所有店舗を対象から除外するため流用しない——本メソッド
        は**すべての**空き区画が対象で、買収に規模上限は無いため規模上限の
        NPC所有店舗も対象に含む。
        **公開する**（決定1）。GameCore が判定（プレイヤー所有店舗が0軒 かつ
        資金が本メソッドの戻り値を下回る）を組む唯一の呼び手になるが、
        is_clear_shop_count_reached / shortfall_covered と同じく盤面の
        語彙でのみ答え、事業継続という業務上の意味づけは持たない（決定2）。
        **取得できる区画が1つも無い**（全区画がプレイヤー所有）場合は None を
        返す。0を返さないのは、0が「取得費用0で再開できる」という誤った
        意味を持ってしまうため（get_value() / get_cost() が値の不在を None
        で表す既存の型に合わせる）"""
        costs = [
            self.get_cost(col, row)
            for row in range(self.GRID_ROWS)
            for col in range(self.GRID_COLS)
            if self._shops.get((col, row)) is None
            or self._shops[(col, row)].owner == Owner.NPC
        ]
        return min(costs) if costs else None

    def invest_shop(self, col, row):
        """区画の店舗へ増資する（店舗規模+1・資産価値へ増資費用を加算）。
        区画にプレイヤー所有の店舗があることは呼び出し側（GameCore）が
        保証する。費用（資金から引く額）は get_cost() から別途得る
        （build 系の set_shop() と対称な形にするため、ここでは返さない）。
        **player_shop_count の内部状態は更新しない**——増資は既に
        プレイヤー所有の区画に対してしか呼ばれず、所有者そのものは変えない
        （set_shop() / buyout_shop() と異なり、プレイヤー所有店舗数を
        動かし得ない操作のため）"""
        self._shops[(col, row)].invest()

    def buyout_shop(self, col, row):
        """区画の店舗を買収する（所有者をプレイヤーへ変更）。区画にNPC所有の
        店舗があることは呼び出し側（GameCore）が保証する。費用（資金から引く額）は
        get_cost() から別途得る（invest_shop() と同じく、ここでは返さない）。
        買収後に player_shop_count の内部状態を更新する（set_shop() と
        並ぶ、所有者がプレイヤーへ変わり得るもう一方の経路）"""
        self._shops[(col, row)].buyout()
        self._update_player_shop_count()

    def iter_shop_pos(self):
        # 店舗のある区画の座標 (col, row) を行昇順→列昇順の決定的な順序で返す。
        # 描画（グリッドの走査順）と保存データの並びの双方がこの順序に依存するため、
        # ソートキーはキーの並び (col, row) とは逆の (row, col) にして行を優先する。
        # 売上の抽選（ID-012）は本メソッドの結果をそのまま抽選へ渡さなくなったが、
        # _list_sales_lottery_entries() が重み付きの並びを組み立てる際の走査順として
        # 引き続き使う（並びが決定的であることをここから受け継ぐ）
        return sorted(self._shops.keys(), key=lambda pos: (pos[1], pos[0]))

    def _area_rate(self, col, row):
        """区画 (col, row) の地域価格倍率（千分率の整数。要件 3.10）を、座標
        のみから算出して返す。時間経過や店舗の状態には一切よらない
        （ID-020_subtasks.md 決定1〜4）。
        距離はチェビシェフ距離（列方向は2つの中心列 _CENTER_COL_LOW /
        _CENTER_COL_HIGH への最小距離、行方向は中心行 _CENTER_ROW との差、
        そのうち大きい方）。倍率は
        `AREA_RATE_CENTER - (AREA_RATE_CENTER - AREA_RATE_EDGE) * 距離 // AREA_MAX_DISTANCE`
        で求め、中心地（距離0）が AREA_RATE_CENTER、盤面上の最大距離の区画が
        AREA_RATE_EDGE になる（完了条件の「最も外側の区画が1.0」は、矩形の
        盤面である以上どの距離定義でも外周すべてを1.0にはできないため、
        「最大距離の区画が1.0」と読む）。
        丸め（切り捨て）は金額を得る箇所（get_cost() など）に任せ、
        倍率そのものは丸めない——このマップの大きさでは AREA_MAX_DISTANCE
        （8）が (AREA_RATE_CENTER - AREA_RATE_EDGE)（2000）を割り切るため
        実際には切り捨てが一度も効かないが、盤面の大きさを変えても壊れない
        よう `//` はそのまま残す。
        区画の状態を読まない（店舗の有無・所有者・規模のいずれにも触れない）
        純粋な座標の関数のため、Field の状態は変えない。
        非公開（_land_price() と同じ扱い）——プレイヤーが倍率そのものを
        確認・設定する操作は要件に無い。呼び手は set_shop() /
        apply_load_data()（生成・復元時に Shop へ渡す）と get_cost()（空き
        区画の建設費用）と total_tax()（土地税）で、いずれも Field の内部。
        直接のテストは持たず、倍率が金額へ効くこと——get_cost() /
        get_value() / get_sales() / total_tax() が中心と外周で異なる値を
        返すこと——を通じて間接的に検証する（_land_price() が total_tax()
        経由でのみ検証されるのと同じ扱い）"""
        col_distance = min(
            abs(col - self._CENTER_COL_LOW), abs(col - self._CENTER_COL_HIGH)
        )
        row_distance = abs(row - self._CENTER_ROW)
        distance = max(col_distance, row_distance)
        return (
            self.AREA_RATE_CENTER
            - (self.AREA_RATE_CENTER - self.AREA_RATE_EDGE)
            * distance
            // self.AREA_MAX_DISTANCE
        )

    def _total_shop_value(self):
        """マップ上の**すべての店舗**（所有者を問わない。要件3.10）の資産価値
        （Shop.value。地域価格倍率を反映した額）の合計を返す。
        _land_price() が使う中間値であり、唯一の
        消費者しか持たない（ID-014 が使うのは _land_price() のみ）ため、公開
        メソッドにはせず _land_price() 専用の内部ヘルパーとして置く
        （_list_npc_growth_targets() / _list_sales_lottery_entries() と同じ、
        「GameCore からは実行メソッド越しにしか使われない集計は非公開にする」
        という扱い）。
        資産価値は店舗が**持っている値をそのまま**足す（規模から再計算しない）。
        Shop.restore() は任意の資産価値を復元できる（保存データの資産価値が
        「倍率反映後の建設費用 + Σ 倍率反映後の増資費用」の式どおりとは
        限らない）ため、規模から解き直すと保存データの値と食い違う
        （区画ごとに倍率が異なるぶん、解き直す側が各店舗の倍率まで
        知る必要も生じる）。
        走査は self._shops の値（Shop インスタンス）を直接読み、iter_shop_pos()
        は経由しない。iter_shop_pos() が支える決定的な**並び**は
        _list_sales_lottery_entries() が重み付きの並びを組み立てる際に要るが、
        合計は**可換**でありどの順で足しても結果は変わらないため、並びを
        必要としない。
        ID-012 からの申し送り（「本タスクが Field へ足す、盤面を走査して値を
        導く形の2件目になり得るため、走査の共通化が要るかを判断する」）への
        答えはここで確定する: **共通化する走査は無い**。
        _list_sales_lottery_entries() は重み分の重複を含む並びを組み立て、
        本メソッドは重複を潰さず1回ずつ数えて合計するだけで、共通なのは
        「全店舗を1回ずつ見る」ことのみであり、束ねても意味のある単位に
        ならない。
        空き区画（self._shops にキーが無い区画）は self._shops.values() に
        現れないため、合計へ混ざらないことが辞書の走査そのものから自明になる
        （get_value() が返す None を足す経路が実装上存在しない）。
        区画の状態を読むだけで、Field の状態は変えない（_list_npc_growth_targets() /
        _list_sales_lottery_entries() と同じ）。
        内部専用のため直接のテストは持たず、_land_price() を経由して間接的に
        検証する（_horizontal_player_run_length() / _is_player_shop() が
        _list_sales_lottery_entries() 経由でのみ間接テストされているのと同じ
        扱い）"""
        return sum(shop.value for shop in self._shops.values())

    def _land_price(self):
        """地価——**マップ1区画あたりの平均資産価値**を返す。_total_shop_value()
        （マップ上のすべての店舗の資産価値の合計。所有者を問わない）を、全区画数
        （GRID_PLOT_COUNT = GRID_COLS × GRID_ROWS = 270）で**切り捨て除算**して
        求める。合計のロジックは持たず _total_shop_value() へ委譲する。
        **切り捨て**にするのは、資金・費用・売上額がすべて整数であり、地価だけ
        小数にすると土地税（プレイヤー所有店舗数 × 地価。ID-014）に小数が
        混ざるため。
        総額が全区画数（270）未満の**序盤は地価が0**になる（店舗が2軒以下の
        間）。土地税も0になるが、要件3.10は「総額が高いほど地価も高い」という
        単調性のみを定めており、これに反しない。
        **却下した案: 総額 ÷ 店舗数（平均店舗価値）**。NPCが最小規模（資産価値
        Shop.BUILD_COST）の店舗を建てると平均が下がるため、要件3.10「他店の
        店舗規模が大きくなるほど地価も上昇する」に反するケースが生じる
        （他店の建設で地価が下がってしまう）。
        **却下した案: 総額そのものを地価とする**。土地税が「プレイヤー所有
        店舗数 × 総額」となり、店舗を増やすほど二乗的に税が伸びる。
        値の水準（割る数=270が生む土地税の重さ）は、収支が揃う ID-015 以降で
        再調整する前提。そのとき動かすツマミは割る数ではなく、税率（ID-014）と
        各費用側に置く。
        **非公開（ID-014 TASK-014-7 でユーザー指示により land_price() から
        改名）**。呼び手は total_tax() のみで、GameCore 側の直接の呼び手は
        無い（地価そのものを画面に表示する要件も無い）。ID-013 完了時点では
        「地価が要件3.10に名前を持つ概念であること」を理由に公開のまま
        据え置いていたが、ID-014 で唯一の実装側の呼び手（total_tax()）が
        確定した時点で、「GameCore からは実行メソッド越しにしか使われず、
        直接の呼び手が無い集計は非公開にする」という統一方針（_total_shop_value() /
        _list_npc_growth_targets() / _list_sales_lottery_entries() と同じ）に
        揃える。直接のテストは持たず、total_tax() を経由した間接テストで
        検証する（test_field.py の TestFieldTotalTax を参照。以前の直接テスト
        TestFieldLandPrice はここへ統合した）。
        区画の状態を読むだけで、Field の状態は変えない"""
        return self._total_shop_value() // self.GRID_PLOT_COUNT

    def _count_player_shops(self):
        """マップ上の**プレイヤー所有店舗のみ**の軒数を返す。_total_shop_value()
        （所有者を問わない。_land_price() 専用）とは絞り込みの対象が異なり、
        名前でも区別する（取り違えると土地税と地価の要件——3.8のプレイヤー
        所有のみと3.10の全店舗——が入れ替わる）。
        当初は `_player_shop_count` という名だった（total_tax() 専用の内部
        ヘルパー）が、ID-028 で同じ意味の**公開プロパティ**
        `player_shop_count`（現在のプレイヤー所有店舗数。内部状態を返す）を
        新設したことに伴い、**走査を行う本メソッドとの名前の衝突を避けるため
        改名した**（動詞始まりの名前にすることで、内部状態を読むだけの
        プロパティ・属性と区別する。ID-028_subtasks.md 決定2 の申し送り）。
        呼び手は _update_player_shop_count()（ID-028。player_shop_count
        プロパティの内部状態の更新）の1つ。ID-020 で土地税が「プレイヤー
        所有店舗数 × 地価」から「区画ごとの `地価 × 地域価格倍率` の合計」へ
        変わり軒数を数えるだけでは済まなくなったため total_tax() 側の
        呼び手は既に消えている。
        Field 内部からの呼び出しのみで GameCore から直接呼ばれることは
        無いため、引き続き非公開のままとする。直接のテストは持たず、
        set_shop() / buyout_shop() / _sell_player_shop() / apply_load_data()
        （player_shop_count の内部状態を更新する経路）経由の間接テストで
        検証する（_total_shop_value() などと同じ扱い）"""
        return sum(1 for shop in self._shops.values() if shop.owner == Owner.PLAYER)

    def _player_shop_value(self):
        """マップ上の**プレイヤー所有店舗のみ**の資産価値（Shop.value。
        地域価格倍率を反映した額）の合計を返す。
        _total_shop_value()（所有者を問わない、_land_price() 専用）とは
        絞り込みの対象が異なるため使い回さない。
        total_tax() 専用の内部ヘルパーのため非公開とし、_count_player_shops() と
        同じ理由で直接のテストは持たない"""
        return sum(
            shop.value for shop in self._shops.values() if shop.owner == Owner.PLAYER
        )

    def total_tax(self):
        """支払い予定税額（次の決算で支払う額。土地税＋資産税。要件 3.8）を
        返す。
        - 土地税 = Σ（地価（_land_price()）× その区画の地域価格倍率
          // Shop.AREA_RATE_BASE）——プレイヤー所有店舗のある区画について、
          **区画ごとに丸めてから合計する**（要件 3.8。丸めの位置は
          ID-020_subtasks.md 決定4）。合計してから丸める形にすると、
          「全区画の倍率が 1.0 のとき従来式（プレイヤー所有店舗数 × 地価）と
          一致する」という要件 3.8 が明記する性質が偶然にしか成立しなくなる。
          その区画の倍率は、店舗が保持する値（Shop.area_rate）ではなく座標から
          都度算出する（_area_rate(col, row)）——土地税は「区画」に掛かる税で
          あり、そこに建つ店舗が過去に受け取った値の持ち回りには依存しない
          （倍率は位置のみで決まり店舗の状態によらない、という要件 3.10 を
          式の形でも表す）。地価は要件 3.10 により**全店舗（所有者を問わない）**
          が対象で、プレイヤー所有には絞らない
        - 資産税 = プレイヤー所有店舗の資産価値総額（_player_shop_value()）×
          ASSET_TAX_RATE_PERCENT // 100。こちらは**プレイヤー所有のみ**が対象。
          資産価値そのものが地域価格倍率を反映した額（Shop.value）で
          あるため、資産税は式を変えずに倍率へ追従する
        地価（全店舗が対象）と資産税（プレイヤー所有のみが対象）は対象範囲が
        非対称になる。地価は「他店の成長も映す土地の相場」、資産税は
        「プレイヤー自身の資産」であり、要件がそれぞれ別の対象を定めている
        ための意図どおりの非対称。
        いずれも**整数の切り捨て**（_land_price() が // で揃えた向きに資産税も
        揃える）。資金・費用・売上額がすべて整数であり、税額だけ小数にすると
        ID-015 の精算（資金からの減算）に小数が混ざるため。
        **地価が0の序盤（総額が全区画数未満）でも、資産税は独立して付く**
        （資産税は地価に一切依存しない別の式であるため。_land_price() の
        docstring が「地価が0でも土地税は要件3.10に反しない」と述べる話とは
        別に、資産税側は最初から地価を参照しない）。
        ASSET_TAX_RATE_PERCENT は仮値で、_land_price() の割る数（GRID_PLOT_COUNT）
        と同じく ID-015 以降で再調整する前提。そのとき動かすのは割る数では
        なく税率と各費用側であり、本メソッドの式の形（土地税＋資産税、
        それぞれの切り捨て）は変えない見込み。
        **公開するのは合計のみ**で、土地税・資産税の内訳や
        _land_price() / _player_shop_value() は公開しない（ID-013 で
        確立した「GameCore からは実行メソッド越しにしか使われず、直接の
        呼び手が無い集計は非公開にする」という統一方針の適用）。GameCore が
        読むのはステータスへ出す1つの数（支払い予定税額）だけであり、内訳を
        出す画面は要件に無い。
        内訳を公開しないぶん、土地税の誤りと資産税の誤りを別々のテストで
        切り分けられない（合計は足し算のため、一方の過大ともう一方の過小が
        打ち消し合い得る）。テスト側（test_field.py の TestFieldTotalTax）は
        打ち消し合いの起きない盤面（NPC所有店舗のみ／地価0で資産税のみ正）を
        必ず含めることでこれを補う。_land_price() 自身の非公開化（ID-014
        TASK-014-7）に伴い、旧 TestFieldLandPrice が直接検証していた地価の
        性質（端数の切り捨て・総額増加に対する単調性・所有者混在の合算・
        重複の非圧縮・復元値の直接利用・複数行の合算・他店成長による上昇）も
        本クラスへ統合し、いずれも本メソッド経由の間接テストで検証する。
        **資金には依存しない**（土地税・資産税とも盤面——プレイヤー所有店舗数・
        資産価値・地価——だけから決まる）。精算（資金からの減算）は ID-015 で
        GameCore 側に現れる。
        区画の状態を読むだけで、Field の状態は変えない"""
        land_price = self._land_price()
        land_tax = sum(
            land_price * self._area_rate(col, row) // Shop.AREA_RATE_BASE
            for (col, row), shop in self._shops.items()
            if shop.owner == Owner.PLAYER
        )
        asset_tax = self._player_shop_value() * self.ASSET_TAX_RATE_PERCENT // 100
        return land_tax + asset_tax

    def get_save_data(self):
        # 保存データは JSON で扱えるよう、座標をキーとする辞書ではなくリストの
        # 並びで持つ。並びは iter_shop_pos() の列挙順（行昇順→列昇順）に従い決定的。
        # Field が知るのは各要素の先頭に座標を置くことだけで、1 区画分の中身は
        # Shop が組み立てる（Field は Shop のデータ構造を知らない）
        return [
            [col, row] + self._shops[(col, row)].get_save_data()
            for col, row in self.iter_shop_pos()
        ]

    def apply_load_data(self, save_data):
        # 保存データの店舗配置で自身を置き換える（読み込み前の状態は残さない）。
        # 先頭 2 要素の座標だけを取り出し、残りはそのまま Shop へ渡す。
        # 地域価格倍率は保存データに含まれないため、座標から算出して渡す
        # （_area_rate(col, row)。ID-020_subtasks.md 決定5）
        self._shops = {
            (col, row): Shop.restore(shop_save_data, self._area_rate(col, row))
            for col, row, *shop_save_data in save_data
        }
        # player_shop_count の内部状態を復元後の盤面から再計算する。
        # クリア判定だけでなく常時のステータス表示にも使うため、復元直後
        # から実際の盤面と一致させる必要がある（ID-028_subtasks.md 決定2）
        self._update_player_shop_count()

    def _list_npc_growth_targets(self):
        """他店建設間隔（ID-008）の抽選対象を、行昇順→列昇順の決定的な順序で
        列挙する。対象は「規模が上限（Shop.SCALE_MAX）未満のNPC所有店舗」と
        「任意の所有者の店舗に上下左右で隣接する空き区画」（重複は1回だけ）で、
        プレイヤー所有店舗そのものは対象に含まれない。区画の状態を読むだけで、
        Field の状態は変えない。
        grow_npc() 専用の内部ヘルパー（GameCore からは grow_npc() 越しにしか
        使われず、GameCore 側の直接の呼び手は無い見込み）のため非公開とし、
        直接のテストは持たない。テストは grow_npc() を実行し、乱数源
        （TestRandomSource）が受け取った並びを検証することで間接的かつ正確に
        確認する（並びの等価性は乱数源が正確に控えるため、間接テストでも
        精度は落ちない）。

        マップの範囲は GRID_COLS / GRID_ROWS（クラス定数）を用いる"""
        targets = set()
        for (col, row), shop in self._shops.items():
            if shop.owner == Owner.NPC and shop.scale < Shop.SCALE_MAX:
                targets.add((col, row))
            for pos in self._adjacent_plot_positions(col, row):
                if pos not in self._shops:
                    targets.add(pos)
        return sorted(targets, key=lambda pos: (pos[1], pos[0]))

    def grow_npc(self):
        """他店建設間隔（ID-008）が満了したときのNPCの成長を1回行う。
        _list_npc_growth_targets() が列挙した対象から抽選で1つを選び、それが
        空き区画であれば最小規模のNPC所有店舗を建設し、NPC所有店舗であれば
        増資する（規模+1・資産価値へ増資費用を加算）。
        抽選を引くのは本メソッドの1箇所だけで、乱数源（IRandomSource）の
        pick_npc_growth_target() を1回呼ぶ。**どの対象を選ぶかは乱数源が決め、
        選ばれた対象に何が起きるかは Field が決める**という分担にすることで、
        テストは呼び出し順ではなく「どの区画を選ばせるか」で結果を固定できる。
        建設と増資のどちらを行うかは、選ばれた区画に既に店舗があるか
        （get_owner() が None かどうか）で分岐する。この判定は
        _build_possible()（main.py）が「店舗のある区画か」を同じ
        `get_owner(col, row) is not None` の形で読んでいるのと揃っている。
        建設はプレイヤーの建設と同じ set_shop() で所有者に Owner.NPC を
        渡すだけ、増資はプレイヤーの増資と同じ invest_shop() を呼ぶだけで
        済む（プレイヤー側の _build_selected_plot() / _invest_selected_plot()
        は資金の減算と可否判定を伴うが、NPC はそのいずれも持たない）。
        いずれの分岐も可否判定を持たない。建設側は _list_npc_growth_targets() が
        既にプレイヤー所有店舗を除外済み、増資側は同メソッドが既に上限規模
        （Shop.SCALE_MAX）のNPC所有店舗を除外済みのため、ここで二重に
        判定し直す必要がない（上限の除外は列挙側にのみ書く）。
        _update_popup() の「o」の分岐（プレイヤー所有→増資／それ以外→建設）と
        形は似ているが、対象の選び方（抽選 対 プレイヤーの選択）・可否条件
        （NPC は常に可 対 資金と規模の判定が要る）・資金の有無が異なるため、
        共通化はしない（_update_popup() 自身が買収 ID-009 が3件目になるまで
        this if/elseに留める、と同じ判断）。
        対象が1つもないときに抽選を呼ばないのは防御ではなく、
        pick_npc_growth_target() が「対象の中から1つを選ぶ」ものである以上、
        選ぶ対象が無い状態は抽選の前段（呼ぶかどうか）で決まるため
        （「対象が空のとき何を返すか」を乱数源の実装ごとに決めさせない）"""
        targets = self._list_npc_growth_targets()
        if not targets:
            return
        col, row = self._random_source.pick_npc_growth_target(targets)
        if self.get_owner(col, row) is None:
            self.set_shop(col, row, Owner.NPC)
        else:
            self.invest_shop(col, row)

    def pick_sales_shop(self):
        """売上発生間隔（ID-010）が満了したときの抽選を1回行い、**選ばれた区画**
        (col, row) を返す（店舗が1軒も無ければ None）。抽選対象はマップ上の
        すべての店舗で、所有者も規模も問わない（規模が上限の店舗も抽選される。
        売上は増資と違い上限で頭打ちにならない）。
        **抽選の対象集合**（どの店舗が選ばれ得るか）はマップ上のすべての店舗の
        ままだが、**抽選へ渡す並び**は iter_shop_pos() そのものではなく、
        _list_sales_lottery_entries() が組み立てる重み付きの並びである（ID-012）。
        重みを「同じ区画を重み分だけ並べる」ことで表すため、対象が変わらなくても
        並びのほうは変わる。ID-010 は「ID-012 が変えるのは選ばれやすさであって
        対象ではないため iter_shop_pos() の流用は崩れない」と見込んでいたが、
        崩れなかったのは対象で、崩れたのは並びだった。
        専用の列挙を設けたのは、grow_npc() が _list_npc_growth_targets() を持つのと
        同じ形の2件目である（**列挙は grow_npc() / pick_sales_shop() 専用の内部
        ヘルパーとし、実行メソッドを経由した間接テストで検証する**。ID-013 で
        総額（_total_shop_value()）も同じ扱いに揃えた）。
        選ばれた区画に何が起きるか（所有者による分岐と資金への加算）は、
        grow_npc() と違ってここでは決めない。**資金は GameCore の持ち物**で
        あり、売上は Field 内で完結しないため、抽選までを Field が行い、
        所有者の判定と加算は呼び出し側（GameCore._collect_sales()）が行う。
        売上額そのもの（get_sales() の結果）ではなく区画を返すのは、額だけを
        返す形にすると「0」が「NPC所有だった」と「店舗が無かった」の両方を
        意味してしまうため。
        対象が1つもないときに抽選を呼ばないのは grow_npc() と同じ理由で、
        「対象が空のとき何を返すか」を乱数源の実装ごとに決めさせないため
        （売上発生間隔のタイマーは最初のプレイヤー所有店舗の建設まで開始
        しないため店舗0軒での満了は起きないが、理由はそれとは独立している）"""
        targets = self._list_sales_lottery_entries()
        if not targets:
            return None
        return self._random_source.pick_sales_shop(targets)

    def _list_sales_lottery_entries(self):
        """売上の抽選（ID-012）で乱数源へ渡す並びを組み立てる。**同じ区画を重み分
        だけ重複して並べる**ことで重みを表し、乱数源はこれまでどおり受け取った
        並びから1つを等確率で引く。こうすると IRandomSource へ重み付き抽選の
        ロジック（累積和と探索）を持ち込まずに済み、境界の契約は「並びから1つを
        等確率で選ぶ」のまま据え置ける（重みは呼び手側の並びの作り方として表れる）。
        重みは **横方向に連続するプレイヤー所有店舗の本数**（連なりの長さ）で、
        連なりに属する全店舗が同じ重みを持つ（2連なら各2・3連なら各3）。
        「隣接する店舗数+1」ではない。それだと4連のとき端が2・中が3となり、
        同じ連なりの中で重みが割れる。要件 3.3 が「並んでいる場合、その店舗は
        他の店舗よりも選ばれる確率が高くなる」と連なり全体について述べている
        ことに対しては、全員が等しく強くなる連なりの長さのほうが素直で、
        プレイヤーにも説明しやすい。
        NPC所有店舗と空き区画はいずれも連なりを断ち切り、**NPC所有店舗の重みは
        常に 1**（要件 3.3 が隣接ボーナスを明示的に否定している）、単独の
        プレイヤー所有店舗の重みも 1（同要件の「基本的には、すべての店舗が同じ
        確率で選ばれる」と一致）。重みが 0 になる店舗は無く、どの店舗も最低 1 の
        重みを持つ（抽選の対象そのものは ID-010 から変わらない）。
        並びは iter_shop_pos() の順（行昇順→列昇順）に走査し、重複は連続して
        置くため決定的になる。抽選結果は乱数源が決めるためゲームの挙動は並び順に
        依存しないが、決定的であればテストが多重集合ではなく並びそのもので
        比較できる。
        _list_npc_growth_targets() が set を使うのと違い、**重複を潰してはならない**
        （重複がそのまま重みであるため）。名前に targets ではなく entries を使うのは、
        _list_npc_growth_targets() の targets が重複のない対象の集合を指しており、
        同じ語だと重複が誤りに見えるため（entries なら同じ店舗が複数の口を持つことが
        名前から読める）。
        並びの長さは最大でも 4,860 要素（270 区画 × 最大重み 18）で、組み立てるのは
        売上発生間隔ごと（毎フレームではない）のため、重み分の展開をそのまま許容する。
        区画の状態を読むだけで、Field の状態は変えない（_list_npc_growth_targets()
        と同じ）。
        pick_sales_shop() 専用の内部ヘルパー（GameCore からは pick_sales_shop()
        越しにしか使われず、GameCore 側の直接の呼び手は無い見込み）のため非公開
        とし、直接のテストは持たない。テストは pick_sales_shop() を実行し、乱数源
        （TestRandomSource）が受け取った並びを検証することで間接的かつ正確に
        確認する（並びの等価性は乱数源が正確に控えるため、間接テストでも精度は
        落ちない）"""
        entries = []
        for col, row in self.iter_shop_pos():
            weight = self._horizontal_player_run_length(col, row)
            entries.extend([(col, row)] * weight)
        return entries

    def _list_sell_targets(self):
        """税金不足時の売却（ID-016）の抽選対象を、行昇順→列昇順の決定的な順序で
        列挙する。対象は**プレイヤー所有店舗のみ**で、NPC所有店舗・空き区画は
        いずれも対象外——_list_npc_growth_targets()（NPC所有店舗＋隣接する
        空き区画が対象）とは真逆の絞り込みになる。区画の状態を読むだけで、
        Field の状態は変えない。
        _sell_player_shop() 専用の内部ヘルパー（GameCore からは
        _sell_player_shop() 越しにしか使われず、GameCore 側の直接の呼び手は
        無い見込み）のため非公開とし、直接のテストは持たない。
        _sell_player_shop() 自身も sell_shops_for_shortfall() 専用の内部
        ヘルパーであり直接のテストを持たないため、本ヘルパーのテストは
        sell_shops_for_shortfall() を実行し、乱数源（TestRandomSource）が
        受け取った並びを検証することで間接的かつ正確に確認する
        （_list_npc_growth_targets() が grow_npc() 越しに確認されるのと
        同じ扱い）。
        絞り込みの条件が「所有者がプレイヤーか」の1点のみのため
        _list_npc_growth_targets() のような隣接判定・重複排除（set）は不要
        （self._shops のキーはそもそも重複しない）"""
        return sorted(
            (pos for pos, shop in self._shops.items() if shop.owner == Owner.PLAYER),
            key=lambda pos: (pos[1], pos[0]),
        )

    def _sell_player_shop(self):
        """税金不足時の売却（ID-016）を1軒ぶん実行する。_list_sell_targets() が
        列挙した対象（プレイヤー所有店舗）から抽選で1つを選び、その店舗を
        Shop.sell() で NPC所有へ変更し、資産価値（Shop.value。地域価格
        倍率を反映した額）の半額（切り捨て）を売却額として返す（案2）。
        中心地の店舗ほど高く売れることになるが、これは資産価値そのものが
        倍率を反映することの帰結であり、売却側に倍率を持ち込んではいない。
        店舗規模・資産価値そのものは変えない（案3。
        Shop.sell() が既に保証する）。
        所有者がプレイヤーからNPCへ変わる（プレイヤー所有店舗数が減る）ため、
        売却の直後に player_shop_count の内部状態を更新する（規定店舗数への
        到達判定 is_clear_shop_count_reached が、決算の売却で規定数を
        下回った場合に追従して偽へ戻る経路。要件 3.16・ID-028_subtasks.md
        決定2）。
        抽選を引くのは本メソッドの1箇所だけで、乱数源（IRandomSource）の
        pick_sell_shop() を1回呼ぶ。grow_npc() / pick_sales_shop() と同じく
        **どの対象を選ぶかは乱数源が決め、選ばれた対象に何が起きるかは Field が
        決める**という分担にする。
        grow_npc()（盤面を変えるが値を返さない）と pick_sales_shop()（値を
        返すが盤面は変えない）の**両方の性質を併せ持つ**——所有者を NPC へ
        変えて盤面を変え、かつ売却額を返す。これは案6（機能を Field で
        帰結させる）の帰結で、売上（pick_sales_shop()）が「抽選までを
        Field、資金への加算は GameCore」に留めたのに対し、売却は所有者の
        変更まで Field 側で完結させるため。
        対象が1つもないとき（プレイヤー所有店舗が0軒）は抽選を呼ばず 0 を
        返す。grow_npc() / pick_sales_shop() と同じ理由（「対象が空のとき
        何を返すか」を乱数源の実装ごとに決めさせない）に加え、0 は
        「売却が起きなかった」ことを呼び出し側（sell_shops_for_shortfall()）が
        調達額の合計へそのまま加算でき、かつ「対象が尽きた」の合図としても
        使える中立の値になる（sell_shops_for_shortfall() の docstring 参照）。
        **不足額を満たすまでの繰り返しは持たない**（本メソッドは1軒ぶんの
        実行のみ）。繰り返しと停止条件は sell_shops_for_shortfall() 側に
        置く（案6）。
        buyout_shop()（費用を返さず、費用は get_cost() から呼び出し側が
        別途得る）とは戻り値の要否が異なる。買収は「これから買う店舗」を
        プレイヤーが区画選択で先に確定させているため費用を別途読めるが、
        売却は「どの店舗が売れるか」が抽選で決まった後にしか額が定まらず、
        呼び出し側が売却前に額を知る手段が無いため、実行と同時に返す形にする。
        本メソッドは GameCore からは sell_shops_for_shortfall() 越しにしか
        呼ばれず、GameCore 側の直接の呼び手は無い（案6の帰結。呼び手は
        _settle_tax() が sell_shops_for_shortfall() を1回呼ぶだけで、
        個々の1軒ぶんの実行は知らない）ため、直接のテストは持たない。
        テストは sell_shops_for_shortfall() を実行し、その結果（所有者・
        店舗規模・資産価値・調達額・抽選へ渡された対象）を検証することで
        間接的に確認する（TestFieldSellShopsForShortfall。既存テストが
        クラスの公開インタフェースに対して振る舞いを検証し、内部の実装
        詳細を直接テストしない方針の踏襲）"""
        targets = self._list_sell_targets()
        if not targets:
            return 0
        col, row = self._random_source.pick_sell_shop(targets)
        shop = self._shops[(col, row)]
        amount = shop.value // 2
        shop.sell()
        self._update_player_shop_count()
        return amount

    def sell_shops_for_shortfall(self, shortfall):
        """税金不足時の売却（ID-016）を、不足額（shortfall）を満たすまで、または
        売る店舗が尽きるまで繰り返し、**調達できた額の合計（raised）を返す**
        （案6・案7）。呼び手（GameCore._settle_tax()）は
        `self._money += self._field.sell_shops_for_shortfall(-self._money)`
        の形で1回呼ぶだけで、**繰り返しと停止条件は本メソッドの内側に閉じる**
        （GameCore は「何軒売ればよいか」を一切知らない）。
        **引数は不足額そのもの（正の数）**で、資金の符号を反転する手間は
        呼び手側に残す。資金（負の値）をそのまま渡す案も検討したが、
        「shortfall」という名前と符号が一致しない値を渡すことになり、
        `while raised < shortfall` という素直なループ条件も書けなくなるため
        却下した。
        **戻り値は raised のみ（ID-016 の形のまま）。「満たせたか」は
        `shortfall_covered` プロパティへ分離した**（ID-016 TASK-016-7 →
        ID-017 での再反転）。ID-016 時点は「戻り値は raised のみで、残不足は
        呼び手が `GameCore._money` の符号から読める」という判断だった。
        ID-017 でその符号がゲームオーバーという業務上の判定になることが
        分かり、判定そのもの（`raised >= shortfall`）を本メソッドの内側へ
        閉じる形に変えた（案2）。**当初は戻り値を `(raised, covered)` の
        タプルへ広げる形で閉じたが、それでは本メソッドが「売却を実行する」
        （コマンド）と「満たせたかを答える」（クエリ）の2つの役割を1つの
        戻り値に混ぜることになり、呼び手が常にタプルをアンパックする負担も
        生む。本メソッドを「不足額ぶんを売却し、調達額を返す」という単一の
        機能に保つため、判定結果は本メソッドの**副作用として内部状態
        （`self._shortfall_covered`）へ記録し、`shortfall_covered`
        プロパティ越しに独立して読ませる形へ改めた**（コマンドとクエリの
        分離）。raised は「呼び手が資金を更新できる」ため引き続き必要であり、
        戻り値からは削らない。
        **不足額0では1軒も売らない**——`while raised(0) < shortfall(0)` が
        最初から偽になるため、ループ本体（抽選の呼び出し）に一度も入らない。
        「不足していなければ呼ばない」を呼び手側の分岐に持たせず、本メソッド
        自身が0を渡されても無害（副作用なし）であることで保証する。
        `shortfall_covered` は `raised(0) >= shortfall(0)` により真になる
        （「不足していない」は「満たせた」に含まれる）。
        **売る店舗が尽きたことの表し方**: `_sell_player_shop()` の戻り値0を
        そのまま「対象が尽きた」の合図として使う（専用の例外や特別な戻り値は
        設けない）。0は「抽選が行われなかった」ときにしか返らず（盤面上の最小の
        地域価格倍率が AREA_RATE_EDGE ＝ Shop.AREA_RATE_BASE（等倍）であるため、
        店舗の資産価値は倍率を反映しても常に Shop.BUILD_COST 以上に保たれ、
        `value // 2` が実際の売却で0になることは
        無い）、`raised` への加算としても中立（0を足しても壊れない）ため、
        1つの値で「尽きた合図」と「合計へ足してよい値」を兼ねられる。専用の
        番兵（例: None や例外）を設けると、_sell_player_shop() の契約
        （「対象が無ければ0」）と2つの意味を持たせることになり、0の扱いを
        _sell_player_shop() の契約と、それを解釈する本メソッドの停止条件の
        2箇所で説明し直す必要が生じる。
        **繰り返しが必ず終わる根拠**: 1回の売却（`_sell_player_shop()` 内の
        `Shop.sell()`）で、売られた店舗の所有者がプレイヤーから NPC へ変わり、
        `_list_sell_targets()`（プレイヤー所有店舗のみを対象とする）の対象から
        必ず1つ減る。対象は盤面の店舗数を超えないため、ループは高々
        プレイヤー所有店舗数の回数で終わる（無限ループにならない。案4）。
        **`total_tax()` を読まない**（呼ばない）——引数で不足額を受け取るのみで、
        盤面から税額を導く経路がそもそも存在しない。案1（精算開始時に1回だけ
        税額を固定し、売却中に読み直さない）が「読まない規律を守る」のではなく
        「読めない形にする」ことで構造的に保証される。
        **ゲームクリア判定（`is_clear_shop_count_reached` プロパティ）との
        対比**: どちらも「Field の状態から答えを導き、独立したプロパティ
        として読ませる」という構造は共通するが、クリア側は軒数
        （player_shop_count）を内部状態として保持しつつ、真偽値自体は
        都度算出する（決定2・案2-C）のに対し、本メソッドが記録する
        `shortfall_covered` は**引数（shortfall）と盤面（売却で調達できる額）
        の関係で決まる真偽値そのものを内部状態として持つ**。「Field に
        閉じる」という帰結は同じでも、閉じ方の形が異なる"""
        raised = 0
        while raised < shortfall:
            amount = self._sell_player_shop()
            if amount == 0:
                break
            raised += amount
        self._shortfall_covered = raised >= shortfall
        return raised

    def _horizontal_player_run_length(self, col, row):
        """区画 (col, row) の店舗が属する、横方向に連続するプレイヤー所有店舗の
        本数を返す。プレイヤー所有店舗でなければ 1（NPC所有店舗は連なりに参加せず、
        跨いで繋げもしない）。
        _adjacent_plot_positions()（他店建設 ID-008 の上下左右4方向）とは共通化
        しない。同じ「隣接」でも定義が異なり（こちらは横方向のみ・プレイヤー所有
        のみで繋がる・繋がった先を再帰的に辿る）、束ねると片方の定義を変えた
        だけでもう片方が連動して動くため。ID-008 が共通化を見送った時点の判断を、
        2件目の使い手が現れた本タスクでも踏襲する。
        左右へ伸ばす際にマップ範囲の判定を持たないのは、参照するのが
        _shops のキーの有無だけであり、範囲外の座標にはキーが存在し得ないため
        （空き区画を列挙する _adjacent_plot_positions() は範囲判定を要するが、
        こちらは既にある店舗を辿るだけという違い）。
        行を跨がないのは row を固定して列だけを動かすことで表れる（行末の区画と
        次の行の先頭の区画は隣接しない）"""
        if not self._is_player_shop(col, row):
            return 1
        start = col
        while self._is_player_shop(start - 1, row):
            start -= 1
        end = col
        while self._is_player_shop(end + 1, row):
            end += 1
        return end - start + 1

    def _is_player_shop(self, col, row):
        """区画にプレイヤー所有の店舗があるか。空き区画（キーなし）とNPC所有店舗を
        同じ「連なりを断ち切るもの」として1つの判定にまとめる"""
        shop = self._shops.get((col, row))
        return shop is not None and shop.owner == Owner.PLAYER

    def _adjacent_plot_positions(self, col, row):
        """区画 (col, row) に上下左右で隣接する区画の座標を、マップの範囲
        （GRID_COLS 列 × GRID_ROWS 行）内に限って返す。他店建設間隔（ID-008）が
        定める「隣接」はこの4方向を指す。ID-012（売上の隣接ボーナス）で2件目の
        「隣接」を扱う使い手（_horizontal_player_run_length()）が現れた時点で
        共通化の可否を判断し、**共通化しないことを確定させた**。横方向のみ・
        プレイヤー所有のみで繋がる・繋がった先を辿るという別の定義であり、
        束ねると片方を変えただけでもう片方が連動して動くため。本メソッドは
        _list_npc_growth_targets() 専用のこの1箇所だけに置く"""
        candidates = ((col - 1, row), (col + 1, row), (col, row - 1), (col, row + 1))
        return [
            (n_col, n_row)
            for n_col, n_row in candidates
            if 0 <= n_col < self.GRID_COLS and 0 <= n_row < self.GRID_ROWS
        ]
