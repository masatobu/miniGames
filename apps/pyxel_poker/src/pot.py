"""コインの支払いとポット（Pyxel に依存しないゲームのロジック。乱数も使わない）。"""

# 参加費。参加するときに 1 回だけ払う
ENTRY_FEE = 1


def raise_cost(round_number):
    """レイズで追加で払うコインを返す。1 回目は 1、2 回目は 2。

    累積支払いは 参加費 + レイズ追加額の合計 なので、
    1 回目のレイズまでで 1 + 1 = 2、2 回目のレイズまでで 1 + 1 + 2 = 4（最大）になる。
    ドロップは追加で払わないため、この関数の対象外。
    """
    if round_number not in (1, 2):
        raise ValueError(f"レイズの追加額は 1・2 回目だけ: {round_number}")
    return round_number


# 1 ゲームの累積支払いの最大。開始時にこれ未満の所持コインの人は破産になる
MAX_PAYMENT = ENTRY_FEE + raise_cost(1) + raise_cost(2)


class Pot:
    """ポット。支払いの合計と、前のゲームから引き継いだコインの合計を持つ。"""

    def __init__(self):
        self.amount = 0

    def pay(self, player, amount):
        """player が amount を払ってポットに加える。実際に払った額を返す。

        所持コインを超える分は払えないので、払う額は min(amount, 所持コイン)。
        所持コインは 0 を下回らない。
        """
        if amount < 0:
            raise ValueError(f"払う額は 0 以上: {amount}")
        paid = min(amount, player.coins)
        player.coins -= paid
        self.amount += paid
        return paid

    def award(self, winner):
        """勝者にポットの全額を渡し、ポットを 0 に戻す。受け取った額を返す。

        勝者が無いとき（全員ドロップ）は呼ばない。ポットは残って持ち越される。
        """
        received = self.amount
        winner.coins += received
        self.amount = 0
        return received
