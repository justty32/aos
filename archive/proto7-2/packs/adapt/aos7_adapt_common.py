"""adapt 共用宣告欄位與精確十進位數值工具。"""
import decimal
import math
import os
import re
import sys

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(TOP, "lib")]
from aos7_fs import json_sha256  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
AS_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
DECL_KEYS = {"v", "sense", "src", "src_clock", "max_age", "patience", "stall", "steps", "need", "note"}
REQUIRED = ("sense", "src", "src_clock", "steps", "need")
STEP_KINDS = ("select", "scale", "threshold")
CMP_KEYS = ("ge", "gt", "le", "lt")
META = ("v", "seq", "round", "at")          # 來源物件的信封欄，不算 omitted
FRAME_KEYS = ("sense", "chain", "since", "my_round", "last_ok_my_round", "last_clock", "last_seq", "stall_rounds",
              "skipped", "resetting", "void_sha", "prev_state", "cur", "last")



# 鏈的數值一律用精確十進位算（A8-01～03）：精度、指數都開到上限，乘、加、比較都是精確的（鏈裡沒有除法），
# 不會因 Decimal 預設 28 位拋例外，也不會在 float 端點塌縮。來源與宣告的數字取 JSON 文字的十進位值（float 取 repr）。
EXACT = decimal.Context(prec=decimal.MAX_PREC, Emax=decimal.MAX_EMAX, Emin=decimal.MIN_EMIN)
FLOAT_MAX = decimal.Decimal(repr(sys.float_info.max))


def dec(v):
    """JSON 數字 → 精確十進位（int 原樣；float 取 repr，也就是讀進來的那段文字）。"""
    return decimal.Decimal(v) if isinstance(v, int) else decimal.Decimal(repr(v))


def round_half_up(x, nd):
    """十進位 x 四捨五入到小數 nd 位（平手遠離零；Python 內建 round 是平手取偶數，不合 spec §2）。精確，不轉 float。"""
    return x.quantize(decimal.Decimal(1).scaleb(-nd), rounding=decimal.ROUND_HALF_UP, context=EXACT)


def publish(x, e=None):
    """精確十進位 → 發布用的 JSON 數字。回 (值, 誤差界)；超出 float 範圍（A8-04）回 (None, None)。
    整數值且小數點後沒有位數（整數相乘、round 0），或整數值但 float 放不下＝ Python int，原樣不失真（A8-02）；其餘＝float，
    float 的 repr 跟 x 不同時，差距算進誤差界（A8-02），誤差界本身往上取到 float。"""
    if abs(x) > FLOAT_MAX or (e is not None and e > FLOAT_MAX):
        return None, None
    v = float(x)
    if x == x.to_integral_value() and (x.as_tuple().exponent >= 0 or dec(v) != x):
        v = int(x)
    elif v == 0.0:
        v = 0.0              # 不發布 -0.0
    if e is None:
        return v, None
    e = e + abs(dec(v) - x) if isinstance(v, float) else e
    f = float(e)
    if dec(f) < e:
        f = math.nextafter(f, math.inf)
    return v, (f if math.isfinite(f) else None)


def sha(obj):
    """正規 JSON（鍵排序）的 sha256：依據版本與鏈版本都用它。"""
    return json_sha256(obj)


def is_num(v):
    """有限的數字（JSON 的 true／false 不算）。int 一律有限（大整數不轉 float，免得 OverflowError）。"""
    if isinstance(v, bool):
        return False
    return isinstance(v, int) or (isinstance(v, float) and math.isfinite(v))


def space_path_ok(p):
    """空間路徑：非空字串、相對、不含 `..` 段（跟核心掛載的字面檢查同一套）。"""
    if not isinstance(p, str) or not p or os.path.isabs(p):
        return False
    return ".." not in p.replace(os.sep, "/").split("/")


