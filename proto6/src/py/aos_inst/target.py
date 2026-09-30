"""找 inst：給一個目標（檔案或資料夾），決定讀哪份 inst、base 是哪裡。

對應 spec：proto6/spec/base/inst.md〈inst 目標：檔案或資料夾〉。

- 資料夾 `xxx`：先 `xxx/.aos/inst.json`，沒有再 `xxx/inst.json`；base＝`xxx` 自己。兩個都沒有＝用法錯（2）。
- 檔案：就是它；base＝檔案所在的資料夾。
- 先看是不是資料夾，再當檔案。首版不提供改尋找路徑的選項。
"""
import collections
import os

from .errors import usage

__all__ = ["Source", "find_inst", "node_dir"]

DIR_CANDIDATES = (os.path.join(".aos", "inst.json"), "inst.json")

# path：要讀的 inst 檔（絕對路徑）；base：相對路徑起點（絕對路徑）；
# is_dir：目標是不是資料夾（＝照資料夾那列找到的，可當 node）
Source = collections.namedtuple("Source", "path base is_dir")


def find_inst(target):
    """目標 → `Source(path, base, is_dir)`。

    資料夾兩個位置都沒有 → `Usage`（2）。目標根本不存在也算用法錯（spec 沒明講，見 README）。
    檔案存在但讀不到的情況留給讀檔那步報 `ReadFailed`。
    """
    p = os.path.abspath(target)
    if os.path.isdir(p):
        for rel in DIR_CANDIDATES:
            cand = os.path.join(p, rel)
            if os.path.isfile(cand):
                return Source(cand, p, True)
        raise usage("資料夾 %s 裡沒有 .aos/inst.json 也沒有 inst.json" % p)
    if not os.path.lexists(p):
        raise usage("找不到目標 %s" % p)
    return Source(p, os.path.dirname(p), False)


def node_dir(path):
    """把「node 資料夾裡的 inst 路徑」正規化成那個資料夾；不是就回 None。

    對應 inst.md 第十九批第 7 條：給 `X/.aos/inst.json` 或 `X/inst.json` 一律變 `X`；
    給資料夾本身就是它自己（有找得到 inst 才算）。判斷法：把候選資料夾照「資料夾那列」
    找一次，找到的正好是這個檔才算——所以 `X/.aos/inst.json` 存在時，`X/inst.json` 不是 node 的
    inst（回 None）。once 的單檔目標不該呼叫這個（spec：單檔不做這個正規化）。
    """
    p = os.path.abspath(path)
    if os.path.isdir(p):
        try:
            find_inst(p)
        except Exception:
            return None
        return p
    name = os.path.basename(p)
    parent = os.path.dirname(p)
    if name != "inst.json":
        return None
    cand = os.path.dirname(parent) if os.path.basename(parent) == ".aos" else parent
    try:
        src = find_inst(cand)
    except Exception:
        return None
    if src.is_dir and os.path.realpath(src.path) == os.path.realpath(p):
        return cand
    return None
