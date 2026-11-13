"""aos_refpath - `$ref` 與 index 共用的「路徑字串 → (檔, 指標)」：`#` 左邊一律檔案系統、右邊一律 json 內部（使用者 11-13 晚定，thinking 2026-11/13/ref-path-rules）。

使用者 11-13 晚：「他應該是以#作爲json內部尋址的標示，比如#/aaa，就是根obj的aaa，而#./bbb，就是當前所在的obj的bbb，#../ccc，就是當前所在obj的上一層的ccc。
而如果是普通的./zzz.json，那就是當前所在資料夾下的zzz.json，而../xxx.json就是上一層。yyy.json#/kkk，就是當前資料夾下的yyy.json中的kkk這個key。
然後yyy.json#./, yyy.json#../都是不允許的。」確認三點：「1.還是報錯吧，#aaa,yyy.json#aaa都報錯。2.對。3.對」。
舊規則（物件當資料夾走、`#/` 後的 `..` 走出檔、`#/` 是空字串 key）整個廢掉，不留相容（proto8 一律當沒有舊版）。
C++ 對應的是 aos-directive 的 aos::ref_spot；兩邊跑同一張對照表 lib/tests/ref_path_cases.json。純標準庫、不讀檔。"""
import os


class RefPathBad(ValueError):
    """寫法不合（`#aaa`、`yyy.json#./…`、`#../` 超出根…）。呼叫者換成自己的錯誤代號（$ref＝DirectiveBad、index＝IndexBad）。"""


class RefPathUnknown(ValueError):
    """寫法合，但手上沒有算得出來的起點（不知道是哪份檔、不知道所在物件在哪）。"""


def spot(text, file=None, here=None, folder=None):
    """路徑字串 → (檔案系統路徑, token 串或 None)。

    text   寫在 json 裡的路徑字串。
    file   寫著它的那份 json 檔（`#…` 沒寫檔名時＝這份）；不知道＝None。
    here   「當前所在的物件」在 file 裡的位置（token 串，跳脫後的樣子，[]＝根物件）；不知道＝None。
    folder 檔案系統相對路徑的起點；沒給＝file 所在的資料夾；兩個都沒給＝"."。

    回傳 token 串：None＝`#` 左邊那一段就是全部（檔或資料夾，看磁碟才知道）；[]＝那份 json 整份；其他＝RFC 6901 token（照字面、跳脫後的樣子）。
    | 寫法 | 結果 |
    | `x.json`、`./x.json`、`../x.json`、`sub/`、絕對路徑 | (folder/x.json 整理過, None) |
    | `#`、`#/` | (file, [])               整份文件 |
    | `#/a/b` | (file, [a, b])             本檔根起算；`..` 不特別、是 key 名 |
    | `#.`、`#./`、`#./b` | (file, here、here+[b]) |
    | `#..`、`#../`、`#../c`、`#../../c` | (file, here 少一層＋[c])；超出根＝RefPathBad |
    | `y.json#`、`y.json#/`、`y.json#/k` | (folder/y.json, []、[k]) |
    | `y.json#./…`、`y.json#../…`、`#aaa`、`y.json#aaa`、空字串、不是字串 | RefPathBad |"""
    if not isinstance(text, str) or not text:
        raise RefPathBad("a path must be a non-empty string")
    if folder is None:
        folder = os.path.dirname(file) if file else "."
    cut = text.find("#")
    left, right = (text, None) if cut < 0 else (text[:cut], text[cut + 1:])
    if left:
        path = os.path.normpath(left if os.path.isabs(left) else os.path.join(folder or ".", left))
    elif file is None:
        raise RefPathUnknown("%s: # without a file name means this file, but which file is not known" % text)
    else:
        path = file
    if right is None:
        return path, None
    if right in ("", "/"):
        return path, []                                     # `#`、`#/`＝整份
    if right.startswith("/"):
        return path, right[1:].split("/")                   # RFC 6901，從根起算
    if right[0] != ".":
        raise RefPathBad("%s: after # write /, ./ or ../ (e.g. #/key, #./key, #../key)" % text)
    if left:
        raise RefPathBad("%s: #./ and #../ count from the object this path is written in, so they cannot follow a file name; write %s#/POINTER" % (text, left))
    segs, up, i = right.split("/"), 0, 0
    while i < len(segs) and segs[i] in (".", ".."):
        up += segs[i] == ".."
        i += 1
    if i == 0:
        raise RefPathBad("%s: after # write /, ./ or ../ (e.g. #/key, #./key, #../key)" % text)
    rest = segs[i:]                                         # 開頭那串 . 與 .. 之後照字面是 token（中間的 .. 是 key 名）
    if rest == [""]:
        rest = []                                           # `#./`、`#../`＝那個物件整個
    if here is None:
        raise RefPathUnknown("%s: #./ and #../ count from the object this path is written in, but where that is is not known" % text)
    if up > len(here):
        raise RefPathBad("%s: goes above the root of %s (%d level%s up from #/%s)" % (text, path, up, "" if up == 1 else "s", "/".join(here)))
    return path, list(here[:len(here) - up]) + rest


def shown(path, toks):
    """(檔, token 串) → N-62 的一整串寫法：None 或 []＝只寫檔（整份），其他＝檔#/a/b。"""
    return path if not toks else "%s#/%s" % (path, "/".join(toks))
