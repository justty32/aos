"""投遞、收件匣、去重、拒絕回信。WRITER-BRIEF 4.5 投遞物那段。"""
import json
import os

from . import fsutil, instrun, layout

KINDS = ("inst", "mail", "llm")

# spec 沒講「id 去重要記在哪」；原型用這個檔（見 FINDINGS）
SEEN = ".seen.json"


class Rejected(Exception):
    def __init__(self, reason, message):
        Exception.__init__(self, message)
        self.reason = reason
        self.message = message


def _seen_path(land):
    return os.path.join(land.inbox, SEEN)


def _seen(land):
    return fsutil.read_json(_seen_path(land), {}) or {}


def _mark_seen(land, obj_id, note):
    s = _seen(land)
    s[obj_id] = {"at": fsutil.now_iso(), "note": note}
    fsutil.write_json(_seen_path(land), s)


def make(kind, from_land, **fields):
    obj = {
        "format_version": 1,
        "id": fields.pop("id", None) or fsutil.new_id(),
        "kind": kind,
        "from": from_land,
        "at": fsutil.now_iso(),
    }
    obj.update(fields)
    return obj


def deliver(land, obj):
    """投遞：生成中 <id>.json.temp，完成 <id>.json。回傳 (成功?, 說明)。"""
    if not land.is_land():
        return False, "%s 不是一塊地（沒有 .aos/layout.json）；先跑 aos init" % land.root
    obj_id = obj.get("id")
    if not obj_id:
        return False, "投遞物少了 `id`"
    fsutil.ensure_dir(land.inbox)
    final = os.path.join(land.inbox, "%s.json" % obj_id)
    if os.path.exists(final) or obj_id in _seen(land):
        # I-05 同 id 再投＝拒絕並回報投遞者
        _report(land, obj, "duplicate", "同一個 id 已經投過了：%s" % obj_id)
        return False, "重複投遞：id %s 已經在 %s 收過" % (obj_id, land.root)
    n = len([f for f in os.listdir(land.inbox) if f.endswith(".json") and f != SEEN])
    if n >= land.inbox_max():
        _report(land, obj, "inbox_full", "收件匣滿了（%d 封）" % n)
        return False, "收件匣背壓：%s 已經有 %d 封，上限 %d" % (land.root, n, land.inbox_max())
    temp = final + ".temp"
    fsutil.atomic_write_text(temp, json.dumps(obj, ensure_ascii=False, indent=2))
    os.rename(temp, final)
    return True, final


def _report(land, obj, reason, message):
    """往投遞者的收件匣回一則 mail（I-05／I-06）。"""
    frm = obj.get("from")
    if not frm:
        return
    back = layout.Land(frm)
    if not back.is_land() or os.path.abspath(frm) == land.root:
        return
    note = make("mail", land.root, subject="rejected", body={
        "reason": reason, "message": message, "delivery_id": obj.get("id"),
    })
    final = os.path.join(back.inbox, "%s.json" % note["id"])
    try:
        fsutil.ensure_dir(back.inbox)
        fsutil.atomic_write_text(final + ".temp", json.dumps(note, ensure_ascii=False, indent=2))
        os.rename(final + ".temp", final)
    except OSError:
        pass


def validate(obj):
    if not isinstance(obj, dict):
        raise Rejected("not_object", "投遞物不是 json 物件")
    if obj.get("format_version") != 1:
        raise Rejected("bad_format_version", "`format_version` 必須是 1")
    for k in ("id", "kind", "from", "at"):
        if k not in obj:
            raise Rejected("missing_field", "少了必填欄 `%s`" % k)
    if obj["kind"] not in KINDS:
        raise Rejected("bad_kind", "`kind` 是 `%s`，只認得 %s" % (obj["kind"], "／".join(KINDS)))
    if obj["kind"] == "inst":
        inst = obj.get("inst")
        if not isinstance(inst, dict) or not isinstance(inst.get("argv"), list) or not inst["argv"]:
            raise Rejected("bad_inst", "`kind:inst` 要帶 `inst` 物件，且 `argv` 是非空陣列")
    if obj["kind"] == "mail":
        if "subject" not in obj:
            raise Rejected("missing_field", "`kind:mail` 少了 `subject`")
    if obj["kind"] == "llm":
        for k in ("prompt", "result"):
            if k not in obj:
                raise Rejected("missing_field", "`kind:llm` 少了 `%s`" % k)
    return obj


def _reject_to(land, path, obj, reason, message):
    obj_id = (obj or {}).get("id") or os.path.basename(path)[:-5]
    dst = os.path.join(land.inbox_rejected, "%s.json" % obj_id)
    fsutil.ensure_dir(land.inbox_rejected)
    _mark_seen(land, obj_id, "rejected:%s" % reason)
    try:
        os.replace(path, dst)
    except OSError:
        pass
    if obj:
        _report(land, obj, reason, message)
    return {"id": obj_id, "reason": reason, "message": message}


def scan(land, kinds=None):
    """列出收件匣裡待處理的投遞檔（不含 rejected/、.temp、.seen.json）。"""
    if not os.path.isdir(land.inbox):
        return []
    out = []
    for f in sorted(os.listdir(land.inbox)):
        if not f.endswith(".json") or f == SEEN:
            continue
        p = os.path.join(land.inbox, f)
        if not os.path.isfile(p):
            continue
        obj = fsutil.read_json(p)
        if kinds and (not isinstance(obj, dict) or obj.get("kind") not in kinds):
            continue
        out.append((p, obj))
    return out


def process(land, tick, timeout_ms=None):
    """exec 每格做一次：搬信、處理 kind:inst、拒絕無效的。

    回傳 {"mail":[…],"inst":[…],"rejected":[…],"left":[…]}
    """
    done = {"mail": [], "inst": [], "rejected": [], "left": []}
    for path, obj in scan(land):
        try:
            validate(obj)
        except Rejected as e:
            done["rejected"].append(_reject_to(land, path, obj if isinstance(obj, dict) else None,
                                               e.reason, e.message))
            continue
        kind = obj["kind"]
        # 先記「這批收了哪個 id」再動投遞檔：中間掛掉的話，寧可留著一封處理過的信
        # 讓人看見，也不要 id 消失後同一筆被重投一次（edge-cases：先記再刪）。
        if kind in ("mail", "inst"):
            _mark_seen(land, obj["id"], kind)
        if kind == "mail":
            fsutil.ensure_dir(land.mail)
            os.replace(path, os.path.join(land.mail, "%s.json" % obj["id"]))
            done["mail"].append(obj["id"])
        elif kind == "inst":
            inst = dict(obj["inst"])
            inst.setdefault("id", obj["id"])
            res = instrun.run_inst(land, tick, inst, "delivered", timeout_ms=timeout_ms,
                                   extra_env={"AOS_CALLER": obj["from"]})
            os.unlink(path)
            done["inst"].append({"id": obj["id"], "result": res})
        else:  # llm：留在收件匣，由 LLM 世界自己的圈取用
            done["left"].append(obj["id"])
    return done
