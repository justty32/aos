"""把一份 inst 快照解成「執行計畫」：展開指示詞、拆選項、驗欄位、檢查展開後的 user。

對應 spec：proto6/spec/base/inst.md〈形狀與版本〉〈路徑、環境與指示詞〉〈選項〉〈執行與錯誤〉
〈頂層整份指示詞〉；指示詞機制見 proto5/spec/directives/。搬自 proto5/lib/aos_inst.py。

解析順序：整份頂層 → `cwd` →（cwd 有 mkdir 就先建）→ `argv` → `envs` → `stdin`／`stdout`／`stderr`／`exit`。
整份與 `cwd` 以 base 為中心，其餘以解出的 `cwd` 為中心；絕對路徑照字面用。
每個欄位的循環鏈各自從空開始，只有走進 `$ref` 取回的 argv／envs 容器才把鏈帶下去。
"""
import dataclasses
import os
from typing import Dict, List, Optional, Union

from .directives import Context, Document, parse_options, resolve, resolve_located
from .errors import InstError
from .identity import (check_resolved_user, check_unchanged, lookup_uid, raw_user, read_snapshot,
                       snapshot_from_obj)
from .target import find_inst

__all__ = ["Stream", "Plan", "OPTIONS", "PATH_FIELDS", "KNOWN_KEYS", "resolve_plan", "load_plan",
           "load_plan_obj"]

PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")
# inst 認得的頂層鍵；其餘鍵原樣放進 Plan.extra（tick 任務表的 id／kind／group／needs 等）
KNOWN_KEYS = ("_metainfo", "user", "argv", "cwd", "envs") + PATH_FIELDS

# 各位置認得的選項（inst.md〈選項〉表）。val：required 必帶／forbidden 不可帶／optional；
# alone：不能跟別的選項一起（inherit／merge）。同位置只有 append＋mkdir 可合用。
_REQ = {"val": "required"}
_ALONE = {"val": "forbidden", "alone": True}
OPTIONS = {
    "stdin": {"inherit": _ALONE},
    "stdout": {"append": _REQ, "mkdir": _REQ, "inherit": _ALONE},
    "stderr": {"append": _REQ, "mkdir": _REQ, "inherit": _ALONE, "merge": _ALONE},
    "exit": {"append": _REQ, "mkdir": _REQ},
    "cwd": {"mkdir": _REQ},
    "envs": {"clear": {"val": "optional"}},
}
_NO_OPTIONS = {}            # 頂層、argv 與其元素、envs 值、$val 裡：放了 $opt 就是 UnknownOption

_METAINFO = {"_type": "posix", "_version": 1}


@dataclasses.dataclass
class Stream:
    """一個路徑欄解完的樣子。`path` 是絕對路徑；空字串＝沒寫（串流接 /dev/null、exit 不寫）。"""
    path: str = ""
    append: bool = False
    mkdir: bool = False
    inherit: bool = False
    merge: bool = False


@dataclasses.dataclass
class Plan:
    """解好的執行計畫：開程序需要的一切都在這裡，路徑都是絕對的。

    `uid` 是本次已授權的身分；`user` 是 inst 裡寫的字面（None＝繼承）。
    `envs_clear` 為真＝從空環境開始疊 `envs`，否則疊在 runner 環境上（只加不減）。
    `extra` 是 inst 不認得的頂層鍵（取自展開後的頂層），原樣帶出、不展開不驗——
    tick 任務表一項是 inst 的超集，呼叫方從這裡拿 id、kind 等。
    `source` 是 inst 檔路徑（記憶體來源時是呼叫方給的 label，可能是 None）。
    """
    uid: int
    user: Optional[Union[str, int]]
    argv: List[str]
    cwd: str
    cwd_mkdir: bool
    envs: Dict[str, str]
    envs_clear: bool
    stdin: Stream
    stdout: Stream
    stderr: Stream
    exit: Stream
    source: Optional[str]
    base: str
    metainfo: dict = dataclasses.field(default_factory=lambda: dict(_METAINFO))
    extra: dict = dataclasses.field(default_factory=dict)

    def to_json(self):
        """轉成可 `json.dumps` 的 dict（CLI 印的就是這個）。"""
        return dataclasses.asdict(self)


def resolve_plan(snapshot, authorized_uid, env=None, create_dirs=True):
    """快照 → `Plan`。呼叫前身分須已授權（並已切好）；`authorized_uid` 就是那個身分。

    - `env`：`$env` 查的表，應是切身分後 runner 自己的環境（沒給＝`os.environ`）。
    - `create_dirs`：cwd 有 mkdir 時，照 spec 在解其他欄位前先建目錄；只想看計畫（CLI）就傳 False。
    - 展開後頂層帶 `user` 時須解到同一個 UID，否則 `UserInvalid`／`UserMismatch`。
    錯誤一律丟 `InstError`（代號見 errors.py）。
    """
    src = snapshot.source
    base = os.path.abspath(src.base)
    # 記憶體來源（raw 是 None）當純記憶體文件：$ref:"" 指它自己，label 不當檔案讀
    doc_path = src.path if snapshot.raw is not None else None
    ctx = Context(Document(doc_path, snapshot.obj), base_dir=base, env=env)

    top = resolve_located(snapshot.obj, ctx, [])
    obj = _no_options(top.value, top.position)
    if not isinstance(obj, dict):
        raise InstError("NotAnObject", "inst 頂層解完必須是 JSON 物件，不是 %s" % type(obj).__name__)
    metainfo = _metainfo(obj.get("_metainfo"))
    check_resolved_user(obj, authorized_uid)
    user = raw_user(snapshot)                   # 字面 user：展開後有寫就以它為準（已驗同一 UID）
    if obj.get("user") not in (None, ""):
        user = obj["user"]

    # cwd 最先解：它是其他欄位的中心；自己的相對路徑與 $ref 以 base 為中心。
    cwd_raw, cwd_names = "", frozenset()
    if "cwd" in obj:
        cwd_raw, cwd_names = _path(obj["cwd"], top.ctx.fresh(base), top.position + ["cwd"], "cwd")
    cwd = _abspath(base, cwd_raw) if cwd_raw else base
    cwd_mkdir = "mkdir" in cwd_names
    if cwd_mkdir and create_dirs:
        make_dir(cwd, "cwd")
    fctx = top.ctx.fresh(cwd)

    argv = _argv(obj.get("argv"), fctx, top.position + ["argv"])
    envs, envs_clear = _envs(obj.get("envs", {}), top.ctx.fresh(cwd), top.position + ["envs"])

    streams = {}
    for name in PATH_FIELDS:
        s = Stream()
        if name in obj:
            v, names = _path(obj[name], top.ctx.fresh(cwd), top.position + [name], name)
            for n in names:
                setattr(s, n, True)
            if v:
                s.path = _abspath(cwd, v)
        streams[name] = s

    return Plan(uid=authorized_uid, user=user, argv=argv, cwd=cwd, cwd_mkdir=cwd_mkdir,
                envs=envs, envs_clear=envs_clear, stdin=streams["stdin"], stdout=streams["stdout"],
                stderr=streams["stderr"], exit=streams["exit"], source=src.path, base=base,
                metainfo=metainfo, extra={k: v for k, v in obj.items() if k not in KNOWN_KEYS})


def load_plan(target, authorize, inherited_uid=None, env=None, create_dirs=True,
              verify_source=True):
    """一條龍：找 inst → 讀快照 → 原始 user → `authorize` → （比對來源）→ 解計畫。

    `authorize(user, uid, snapshot) -> 已授權 UID` 是呼叫方的接口（見 `identity.Authorizer`／
    `identity.grant_only`）：在這裡做額度檢查與切身分；不准就丟 `UserNotGranted`。
    `inherited_uid`：`user` 省略時繼承的身分（沒給＝目前 UID）。
    `env`：切身分後的 runner 環境；None＝呼叫時的 `os.environ`（切身分後才讀，所以回呼可以先改它）。
    `verify_source`：授權後重讀來源與快照比對（`SourceChanged`）。
    """
    snap = read_snapshot(find_inst(target))
    user = raw_user(snap)
    uid = lookup_uid(user, inherited_uid)
    authorized = authorize(user, uid, snap)
    if verify_source:
        check_unchanged(snap)
    return resolve_plan(snap, authorized, env=env, create_dirs=create_dirs)


def load_plan_obj(obj, base, authorize, inherited_uid=None, env=None, create_dirs=True,
                  label=None):
    """同 `load_plan`，但吃記憶體裡已讀好的一份 inst（dict）＋ base，不找檔、不比對來源。

    給 tick 任務表用：一項是 inst 的超集，從 tasks.json 陣列拿出來直接丟進來；
    不認得的鍵（id、kind…）會出現在 `Plan.extra`。`label` 只供顯示（見 `snapshot_from_obj`）。
    """
    snap = snapshot_from_obj(obj, base, label)
    user = raw_user(snap)
    authorized = authorize(user, lookup_uid(user, inherited_uid), snap)
    return resolve_plan(snap, authorized, env=env, create_dirs=create_dirs)


def make_dir(path, what):
    """建目錄（含上層）；建不起來＝`PrepareFailed`。"""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise InstError("PrepareFailed", "%s 的 mkdir 建不起來 %s：%s" % (what, path, e))


# ------------------------------------------------------------------ 內部 ----

def _metainfo(mi):
    """`_metainfo`：沒寫＝posix v1；要是含 `_type`／`_version` 的物件；只認 "posix" 與整數 1。"""
    if mi is None:
        return dict(_METAINFO)
    if not isinstance(mi, dict):
        raise InstError("MetainfoInvalid", "_metainfo 必須是物件，不是 %s" % type(mi).__name__)
    missing = [k for k in ("_type", "_version") if k not in mi]
    if missing:
        raise InstError("MetainfoInvalid", "_metainfo 缺了 %s" % "、".join(missing))
    t, v = mi["_type"], mi["_version"]
    if not (isinstance(t, str) and t == "posix"):
        raise InstError("UnsupportedInstType", "_metainfo 的 _type 只認 \"posix\"，不是 %r" % (t,))
    if not (isinstance(v, int) and not isinstance(v, bool) and v == 1):
        raise InstError("UnsupportedInstVersion", "_metainfo 的 _version 只認 1，不是 %r" % (v,))
    return dict(_METAINFO)


def _no_options(value, position):
    """不吃選項的位置：解出來是選項物件就是 `UnknownOption`；不是就原樣回。"""
    return parse_options(value, position, _NO_OPTIONS)[1]


def _str(value, position, what):
    """要字串的位置：解完不是字串（或含 NUL，exec 帶不過去）＝`FieldTypeMismatch`。"""
    value = _no_options(value, position)
    if not isinstance(value, str):
        raise InstError("FieldTypeMismatch", "%s 要是字串，不是 %s" % (what, type(value).__name__))
    if "\0" in value:
        raise InstError("FieldTypeMismatch", "%s 不能含 NUL 字元" % what)
    return value


def _argv(raw, ctx, position):
    """`argv`：整個陣列或每個元素都可以是指示詞；解完要非空字串陣列、首項不空。"""
    if raw is None:
        raise InstError("EmptyArgv", "argv 必填")
    loc = resolve_located(raw, ctx, position)
    argv = _no_options(loc.value, loc.position)
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    out = [_str(resolve(x, loc.ctx, loc.position + [str(i)]), loc.position + [str(i)], "argv[%d]" % i)
           for i, x in enumerate(argv)]
    if not out or out[0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空陣列，或 argv[0] 是空字串")
    return out


def _envs(raw, ctx, position):
    """`envs`：鍵值都是字串的物件，或 `{"$opt":"clear","$val":{…}}`。回 `(dict, clear)`。"""
    loc = resolve_located(raw, ctx, position)
    names, val, has_val = parse_options(loc.value, loc.position, OPTIONS["envs"])
    clear = "clear" in names
    what = "envs"
    if names:
        what = "envs 的 $val"
        loc = resolve_located(val if has_val else {}, loc.ctx, loc.position + ["$val"])
        val = _no_options(loc.value, loc.position)
    if not isinstance(val, dict):
        raise InstError("FieldTypeMismatch", "%s 要是物件，不是 %s" % (what, type(val).__name__))
    out = {}
    for k, v in val.items():
        if k == "" or "=" in k or "\0" in k:
            raise InstError("EnvKeyInvalid", "envs 的 key 不能是空字串或含 '='：%r" % (k,))
        out[k] = _str(resolve(v, loc.ctx, loc.position + [k]), loc.position + [k], "envs[%r]" % k)
    return out, clear


def _path(raw, ctx, position, name):
    """路徑欄（stdin／stdout／stderr／exit／cwd）：解指示詞、拆選項、`$val` 再解、驗字串。

    回 `(路徑字串, 選項名集合)`。inherit／merge 不帶值、路徑＝沒寫；append／mkdir 的 `$val`
    是空字串＝`OptionConflict`。
    """
    loc = resolve_located(raw, ctx, position)
    names, val, has_val = parse_options(loc.value, loc.position, OPTIONS[name])
    if names and not has_val:                   # inherit／merge
        return "", names
    what = name
    if names:
        what = "%s 的 $val" % name
        position = loc.position + ["$val"]
        val = resolve(val, loc.ctx, position)
    val = _str(val, position, what)
    if names and val == "":
        raise InstError("OptionConflict", "%s 的 %s 要帶非空路徑" % (name, "／".join(sorted(names))))
    return val, names


def _abspath(base, p):
    """絕對的照字面用，相對的從 base 起算。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
