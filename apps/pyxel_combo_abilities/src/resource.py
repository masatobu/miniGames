"""リソース（Resource）と部品（Component）の静的な定義。"""

from enum import Enum


class Resource(Enum):
    """リソース。値は (ID, 基本の重み, レベルごとの加算)。MASK は種類の判定用。

    ID の十の位が種類（1=things、2=star、3=bolt）、一の位がランク
    （1=BRONZE、2=SILVER、3=GOLD）を表す。
    """

    THINGS_MASK = 10
    THINGS_BRONZE = (11, 100, 0)
    THINGS_SILVER = (12, 10, 3)
    THINGS_GOLD = (13, 0, 1)
    STAR_MASK = 20
    STAR_BRONZE = (21, 100, 0)
    STAR_SILVER = (22, 10, 3)
    STAR_GOLD = (23, 0, 1)
    BOLT_MASK = 30
    BOLT_BRONZE = (31, 100, 0)
    BOLT_SILVER = (32, 10, 3)
    BOLT_GOLD = (33, 0, 1)

    @classmethod
    def avails(cls):
        """MASK を除いた、出現するリソースの一覧。"""
        return [i for i in cls if not isinstance(i.value, int)]

    @classmethod
    def get_rank(cls, target):
        """ランク値（BRONZE=1、SILVER=2、GOLD=3）。Resource 以外は 0。"""
        if isinstance(target, cls):
            return target.value[0] % 10
        return 0

    @classmethod
    def check_mask(cls, mask, target):
        """target が mask の種類に合うか。どちらかが None なら True。"""
        if mask is None or target is None:
            return True
        return mask.value // 10 == target.value[0] // 10


class Component(Enum):
    """部品。値は、各枠に置けるリソースの種類（MASK）。None は制約なし。"""

    ENGINE = [Resource.THINGS_MASK, Resource.BOLT_MASK]
    GUN = [Resource.STAR_MASK, Resource.BOLT_MASK]
    BODY = [Resource.THINGS_MASK, Resource.STAR_MASK]
    STOCK = [None for _ in range(5)]

    @classmethod
    def tuned(cls):
        """チューニング対象の部品。"""
        return [cls.ENGINE, cls.GUN, cls.BODY]
