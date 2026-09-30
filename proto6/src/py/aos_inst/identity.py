"""身分先行：讀快照、取原始頂層字面 `user`、名稱→UID、授權接口、來源沒變的比對。

對應 spec：proto6/spec/base/inst.md〈先決定身分，切完才解析〉〈頂層整份指示詞〉〈執行與錯誤〉。

流程（呼叫方照這個順序接）：
1. `read_snapshot(source)`：一次讀進原始位元組與 JSON（之後解析都用這份快照，不重讀）。
2. `raw_user(snapshot)`：只看原始頂層物件的 `user` 字面，不展開任何指示詞。
3. 呼叫方授權、切身分（本套件**不做**切身分；見 `Authorizer`）。
4. `check_unchanged(snapshot)`（可選）：授權後原來源內容跟快照不同 → `SourceChanged`。
5. `plan.resolve_plan(snapshot, authorized_uid, ...)`：展開整份，並檢查展開後的 `user`。
"""
import collections
import json
import os
import pwd

from .errors import InstError

__all__ = [
    "Snapshot", "read_snapshot", "snapshot_from_bytes", "snapshot_from_obj", "raw_user", "lookup_uid",
    "check_resolved_user", "check_unchanged", "Authorizer", "grant_only",
]

# source：target.Source；raw：原始位元組（記憶體來源為 None）；obj：解好的 JSON（未展開指示詞）
Snapshot = collections.namedtuple("Snapshot", "source raw obj")


def read_snapshot(source):
    """讀 `source.path` 成 `Snapshot`。讀不到＝`ReadFailed`，不是合法 JSON（含非 UTF-8）＝`JsonSyntax`。"""
    try:
        with open(source.path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReadFailed", "讀不到 inst %s：%s" % (source.path, e))
    return snapshot_from_bytes(source, raw)


def snapshot_from_bytes(source, raw):
    """用已經拿到的位元組做快照（例如 daemon 讀好、經 memfd 交給 runner 的那份）。"""
    try:
        obj = json.loads(raw.decode("utf-8"))
    except ValueError as e:     # UnicodeDecodeError 也是 ValueError
        raise InstError("JsonSyntax", "inst %s 不是合法 JSON：%s" % (source.path, e))
    return Snapshot(source, bytes(raw), obj)


def snapshot_from_obj(obj, base, label=None):
    """記憶體裡已讀好的一份 inst（例如 tick 任務表 tasks.json 陣列裡的一項，是 inst 的超集）。

    `base` 是相對路徑與 `$ref` 的起點。`label` 只拿來顯示／放進 `Plan.source`，不會被當檔案讀：
    這份文件是純記憶體文件，`$ref:""` 指的是這個 obj 自己（它的根就是這一項，不是整份 tasks.json）。
    這種快照沒有原始位元組，不能拿去 `check_unchanged`。
    """
    from .target import Source
    return Snapshot(Source(label, os.path.abspath(base), False), None, obj)


def _check_literal(value, where):
    """`user` 字面值驗型別：字串或非負整數，布林不算；空字串＝繼承（回 None）。"""
    if isinstance(value, str):
        return value if value != "" else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, dict):
        raise InstError("UserInvalid", "%s 的 user 不可用指示詞或選項物件" % where)
    raise InstError("UserInvalid", "%s 的 user 要是帳號名稱字串或非負整數 UID，不是 %r" % (where, value))


def raw_user(snapshot):
    """取原始頂層字面 `user`（不展開）。回帳號名稱、UID 整數，或 None（省略／空字串＝繼承）。

    原始頂層不是物件（例如陣列）→ None，讓後面的展開去報 `NotAnObject`。
    原始頂層是指示詞物件（例如 `{"$ref":…, "user":"bob"}`）時一樣讀它的 `user` 鍵——
    spec 說的是「原始頂層字面」，所以照字面取（見 README〈自己做的判斷〉）。
    """
    obj = snapshot.obj
    if not isinstance(obj, dict) or "user" not in obj:
        return None
    return _check_literal(obj["user"], "原始頂層")


def lookup_uid(user, inherited_uid=None):
    """`user`（名稱／UID／None）→ UID。None＝繼承 `inherited_uid`（沒給就用目前 UID）。

    名稱查不到＝`UserInvalid`。整數 UID 原樣用，不要求系統有這個帳號（見 README）。
    """
    if user is None or user == "":
        return os.getuid() if inherited_uid is None else inherited_uid
    user = _check_literal(user, "inst")
    if isinstance(user, int):
        return user
    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        raise InstError("UserInvalid", "帳號 %r 不存在" % user)


def check_resolved_user(resolved_top, authorized_uid):
    """展開後頂層若帶 `user`，須為合法字面值且解到同一個已授權 UID。

    型別錯／查不到＝`UserInvalid`；解到別的 UID＝`UserMismatch`；沒寫或空字串＝沿用，不檢查。
    """
    if not isinstance(resolved_top, dict) or "user" not in resolved_top:
        return
    value = _check_literal(resolved_top["user"], "展開後頂層")
    if value is None:
        return
    uid = lookup_uid(value)
    if uid != authorized_uid:
        raise InstError("UserMismatch",
                        "展開後的 user %r（UID %d）跟已授權的 UID %d 不同，不能再換身分"
                        % (value, uid, authorized_uid))


def check_unchanged(snapshot):
    """重讀原來源，內容跟快照不同（或已讀不到）＝`SourceChanged`。不管改的是不是 user。

    只適用從檔案讀的快照；記憶體快照（`snapshot_from_obj`）的比對由呼叫方自己做。
    """
    if snapshot.raw is None:
        raise ValueError("記憶體快照沒有原始來源可比對")
    try:
        with open(snapshot.source.path, "rb") as f:
            now = f.read()
    except OSError as e:
        raise InstError("SourceChanged", "授權後讀不到原來源 %s：%s" % (snapshot.source.path, e))
    if now != snapshot.raw:
        raise InstError("SourceChanged", "授權後原來源 %s 的內容跟快照不同" % snapshot.source.path)


class Authorizer:
    """留給呼叫方的接口：授權＋切身分。

    `plan.load_plan()` 會呼叫 `authorize(user, uid, snapshot)`：`user` 是原始頂層字面（None＝繼承），
    `uid` 是它查出來的 UID。子類別覆寫 `authorize`：不准就丟 `InstError("UserNotGranted", …)`；
    准了就在這裡做額度檢查、安置資源、切身分（setgid／initgroups／setuid 或叫 helper），
    最後回「本次已授權的 UID」。也可以直接傳一個同簽名的函式，不必繼承這個類別。
    """

    def authorize(self, user, uid, snapshot):
        raise NotImplementedError

    def __call__(self, user, uid, snapshot):
        return self.authorize(user, uid, snapshot)


def grant_only(uids):
    """現成的授權函式：UID 在 `uids` 裡才准，**不切身分**（沒有 helper 時的最小做法）。"""
    allowed = frozenset(uids)

    def authorize(user, uid, snapshot):
        if uid not in allowed:
            raise InstError("UserNotGranted", "UID %d 不在允許的身分裡" % uid)
        return uid
    return authorize
