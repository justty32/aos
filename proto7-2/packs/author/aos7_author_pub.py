"""author 包的發布與恢復（spec §5；llm-author §4.3 五列）：意圖 → 表鎖內只合併自己那一項 → 回條。

模型與驗證都在表鎖外；表鎖（tasks.json.lock）只用來重讀、比自己那一項、合併。作者寫者之間另有共用鎖 author/author.lock。
重啟看到舊 intent 一律走證據恢復，不因同 rid 自動補加；只有人手 --resend 能讓 unknown 的版本重走首次發布。
"""
import os

import aos7_author
from aos7_author import (MAX_VERSIONS, OK, N, Node, Refuse, Unknown, check_rid, fact, published, recompute_payload, result,
                         sha256, read_bytes, test_point, aos7_step)
from aos7_fs import edit_json, write_json

TABLE_TIMEOUT = 2.0
MISSING = object()


def tasks_path(nd):
    return os.path.join(nd.node, ".aos", "tasks.json")


def _items(t):
    items = t.get("tasks") if isinstance(t, dict) else None
    if not isinstance(items, list):
        raise Unknown("tasks.json 不是 {\"tasks\": [...]}，不知道原本有什麼，不寫", kind="table")
    return items


def judge_item(items, task):
    """表上自己那一項：None 不在｜"same" 完全相符｜"changed" 同名但改過或 disabled（conflict）。"""
    mine = [i for i in items if isinstance(i, dict) and i.get("name") == task["name"]]
    if not mine:
        return None
    return "same" if len(mine) == 1 and mine[0] == task else "changed"


def publish(node, rid, *, candidate_sha=None, resend=False):
    """發布一版（省略 sha 取 active）。回 {ok, why, receipt}；why：invalid／conflict／unknown。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        with nd.lock():
            return _publish_locked(nd, rid, candidate_sha, resend)
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg, **r.extra)
    except (Unknown, OSError) as e:
        return result(False, "unknown", rid=rid, error=str(e))


def recover(node, rid, *, candidate_sha=None):
    """只走證據恢復（不新登記）：回條／相符表項／相符 birth 或 frame／只有 intent／同名改過，五列。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        check_rid(rid)
        with nd.lock():
            request, rsha = nd.request(rid)
            cdoc, vdoc, idoc, receipt = nd.docs(rid)
            sha = candidate_sha or cdoc.get("active")
            if sha in published(receipt):
                return result(True, rid=rid, receipt=published(receipt)[sha], dup=True)
            if sha not in idoc["versions"]:
                raise Refuse("invalid", "版本 %s 沒有發布意圖可恢復" % (sha or "-")[:12])
            return _recover(nd, rid, sha, idoc["versions"][sha], receipt, rsha)
    except Refuse as r:
        return result(False, r.why, rid=rid, error=r.msg, **r.extra)
    except (Unknown, OSError) as e:
        return result(False, "unknown", rid=rid, error=str(e))


def _publish_locked(nd, rid, sha, resend):
    request, rsha = nd.request(rid)
    cdoc, vdoc, idoc, receipt = nd.docs(rid)
    sha = sha or cdoc.get("active")
    pub = published(receipt)
    if sha in pub:                                   # 第一列：有回條→回原條，不補表（不復活已移除的工作；結案後也一樣）
        if resend:
            raise Refuse("conflict", "版本 %s 已有回條，不重送" % sha[:12], receipt=pub[sha])
        return result(True, rid=rid, receipt=pub[sha], dup=True)
    if receipt and receipt.get("closed"):
        raise Refuse("conflict", "需求 %s 已結案" % rid)
    v = vdoc["versions"].get(sha)
    if sha in idoc["versions"]:                      # 舊 intent：一律走證據恢復
        try:
            return _recover(nd, rid, sha, idoc["versions"][sha], receipt, rsha)
        except Refuse as r:
            if not (resend and r.why == "unknown"):
                raise                                # 只有 unknown＋人手 --resend 才往下重走首次發布
    elif resend:
        raise Refuse("invalid", "版本 %s 沒有結果不明的發布，--resend 不適用" % (sha or "-")[:12])
    if not (v and v.get("ok") and v.get("validated")):
        raise Refuse("invalid", "版本 %s 沒過驗證，不發布" % (sha or "-")[:12])
    if len(pub) >= MAX_VERSIONS:
        raise Refuse("full", "已發布版本達上限")
    links = aos7_author.out_links(nd, v["job"])
    if links:
        raise Refuse("invalid", "jobs/%s/out 裡有 symlink（%s），寫路徑可能逃出 out" % (v["job"], links[0]))
    have = recompute_payload(nd, rid, v)             # 表鎖外重算；與 verdict 不同＝驗證後內容被換
    if have != v["payload_sha"]:
        raise Refuse("invalid", "payload_changed：驗證後固定來源或工具卡被改（%s ≠ %s）" % (have[:12], v["payload_sha"][:12]))
    task = v["manifest"]["task"]
    task = dict(task, x={"author": dict(task["x"]["author"], payload_sha=v["payload_sha"])})
    intent = {"v": 1, "rid": rid, "request_sha": rsha, "candidate_sha": sha, "owner": "author", "job": v["job"],
              "payload_sha": v["payload_sha"], "steps_sha256": v["steps_sha256"], "files": v["manifest"]["files"],
              "task": task}
    idoc["versions"][sha] = intent
    nd.save(rid, "intent.json", idoc)
    test_point("author:after-intent")

    def merge(t):
        t = {"tasks": []} if t is MISSING else t     # 只有「檔不存在」才從空表起；JSON null 之類＝壞表

        items = _items(t)
        got = judge_item(items, task)
        if got == "changed":
            raise Refuse("conflict", "表上已有同名 %s 但內容不同或 disabled；保留現況" % task["name"])
        if got == "same":
            return None                              # 相符：不追加
        return dict(t, tasks=items + [task])         # 只加自己那一項；其他項與頂層設定原樣
    edit_json(tasks_path(nd), merge, default=MISSING, timeout=TABLE_TIMEOUT)
    test_point("author:after-merge")
    return _write_receipt(nd, rid, intent, receipt, rsha, "table")


def _write_receipt(nd, rid, intent, receipt, rsha, evidence):
    receipt = receipt or {"v": 1, "rid": rid, "request_sha": rsha, "closed": False, "versions": {}}
    rc = {"v": 1, "rid": rid, "request_sha": rsha, "candidate_sha": intent["candidate_sha"],
          "payload_sha": intent["payload_sha"], "job": intent["job"], "task_name": intent["task"]["name"],
          "registered": True, "evidence": evidence, "closed": False}
    receipt["versions"][intent["candidate_sha"]] = rc
    nd.save(rid, "receipt.json", receipt)
    test_point("author:after-receipt")
    return result(True, rid=rid, receipt=rc)


def _recover(nd, rid, sha, intent, receipt, rsha):
    """證據恢復（llm-author §4.3）。只讀表，不改表。"""
    task = intent["task"]
    st, t = fact(tasks_path(nd))
    if st not in (OK, N):
        raise Unknown("tasks.json %s；不知道表上有什麼" % t, kind="table")
    got = judge_item(_items(t) if st == OK else [], task)
    if got == "same":                                # 第二列：相符表項→補回條，不追加
        return _write_receipt(nd, rid, intent, receipt, rsha, "table")
    if got == "changed":                             # 第五列：同名改過／disabled→conflict，保留現況
        raise Refuse("conflict", "表上 %s 已被改過或 disabled；保留現況" % task["name"])
    ev = _positive(nd, intent)
    if ev:                                           # 第三列：表項消失、有相符 birth／frame→補回條，不補表
        return _write_receipt(nd, rid, intent, receipt, rsha, ev)
    raise Refuse("unknown", "版本 %s 只有發布意圖、沒有登記證據；不補加（查明後人手 publish %s --resend）" % (sha[:12], rid))


def _positive(nd, intent):
    """表外的正證據：槽 birth 的 name／argv／x.author 與意圖相符，或 frame.table 綁得上意圖的 steps 雜湊。"""
    task = intent["task"]
    st, b = fact(os.path.join(nd.node, ".aos", "tasks", task["name"], "birth.json"))
    if st == OK and isinstance(b, dict) and b.get("name") == task["name"] and b.get("argv") == task["argv"] \
            and (b.get("x") or {}).get("author") == task["x"]["author"]:
        return "birth"
    if st not in (OK, N):
        raise Unknown("槽 %s 的 birth.json %s" % (task["name"], b), kind="slot")
    jd = nd.jd(intent["job"])
    raw = read_bytes(os.path.join(jd, "steps.json"))
    st, fr = fact(os.path.join(jd, "frame.json"))
    files = intent.get("files") or {}
    same = bool(files) and all((lambda b: b is not None and sha256(b) == h)(read_bytes(os.path.join(jd, n)))
                               for n, h in files.items())          # 固定來源全部對得上 intent，不只 steps
    if same and raw is not None and sha256(raw) == intent["steps_sha256"] and st == OK and isinstance(fr, dict) \
            and fr.get("job") == intent["job"] and fr.get("table") == aos7_step.table_rev(raw):
        return "frame"
    return None


def _events():
    """只在事件接線時載入；舊命令不依賴 events。"""
    import sys
    sys.path.insert(0, os.path.join(aos7_author.TOP, "modules", "events"))
    import aos7_events_pub, aos7_events_read, aos7_events_store
    return aos7_events_pub, aos7_events_read, aos7_events_store


def send_request(node, request_path, events_dir):
    """輕驗需求原文後送 must；保存端只按識別碼去重，重送另比原文雜湊。"""
    nd = node if isinstance(node, Node) else Node(node)
    try:
        raw = read_bytes(request_path)
        req = aos7_author.strict_json(raw) if raw is not None else None
        rid = req.get("rid") if isinstance(req, dict) else None
        check_rid(rid)
        payload = dict(v=1, rid=rid, request_sha=sha256(raw), request=raw.decode("utf-8"))
        pub, reader, _ = _events()
        sent = pub.publish(events_dir, "author.request", "author/" + rid, payload,
                           must=True, node=os.path.basename(nd.node))
        if not sent["ok"]:
            return result(False, {"usage": "invalid", "too_large": "invalid"}.get(sent["why"], sent["why"]))
        if sent["dup"]:
            found = reader.read(events_dir, "must", cursor=sent["seq"], limit=1)
            if found["errors"]:
                raise Unknown("重送事件讀取有錯：%s" % found["errors"])
            for rec in found["records"]:
                if rec["seq"] == sent["seq"] and (not isinstance(rec.get("payload"), dict) or rec["payload"].get("request_sha") != payload["request_sha"]):
                    return result(False, "conflict", rid=rid, seq=sent["seq"])
        return result(True, seq=sent["seq"], dup=sent["dup"])
    except Refuse as r:
        return result(False, r.why, error=r.msg)
    except (ValueError, UnicodeError) as e:
        return result(False, "invalid", error=str(e))
    except (Unknown, OSError) as e:
        return result(False, "unknown", error=str(e))


def _intake_record(nd, rec):
    """壞事件是確定答案；登記的 I/O 未知則保留事件重試。"""
    p = rec.get("payload")
    rid = p.get("rid") if isinstance(p, dict) and isinstance(p.get("rid"), str) else None
    rsha = p.get("request_sha") if isinstance(p, dict) and isinstance(p.get("request_sha"), str) else None
    if rec.get("kind") != "author.request":
        return rid, rsha, "ignored", "外來 kind"
    try:
        check_rid(rid)
        if not (type(p.get("v")) is int and p["v"] == 1 and isinstance(p.get("request"), str)
                and rec.get("event_id") == "author/" + rid):
            raise ValueError("payload 格式不合")
        raw = p["request"].encode("utf-8")
        req = aos7_author.strict_json(raw)
        if sha256(raw) != rsha or not isinstance(req, dict) or req.get("rid") != rid:
            raise ValueError("需求識別或雜湊不合")
    except (Refuse, ValueError, UnicodeError) as e:
        return rid, rsha, "invalid", str(e)
    r = aos7_author._register_raw(nd, raw)
    return rid, rsha, ("dup" if r.get("dup") else "registered") if r["ok"] else r["why"], r.get("error")


def intake(node, events_dir, limit=20):
    """唯一 must 消費者：登記 → 固定回條 → ack；重起先補上次 ack。"""
    nd = node if isinstance(node, Node) else Node(node)
    handled = []
    cursor, acked = None, 0
    if type(limit) is not int or limit < 1:
        return result(False, "invalid", error="limit 須為正整數")
    try:
        _, reader, store = _events()
        events = os.path.realpath(events_dir)
        path = os.path.join(nd.dir, "events.json")
        with nd.lock():
            aos7_author.sweep_tmp(nd.dir)   # 回條寫到一半被殺留下的 .events.json.tmp.<pid>
            status, doc = fact(path)
            if status == N:
                st = store.load_state(events)
                if st is None and any(e.get("kind") == "state_unreadable"
                                      for e in reader.read(events, "must", limit=1)["errors"]):
                    raise Unknown("events state 讀不到")
                acked = st["channels"]["must"]["acked_upto"] if st else 0
                if type(acked) is not int or acked < 0:
                    raise Unknown("events 確認進度格式不合")
                cursor = acked + 1
            else:
                if status != OK or not isinstance(doc, dict) or type(doc.get("v")) is not int or doc["v"] != 1 \
                        or not isinstance(doc.get("events"), str) or type(doc.get("cursor")) is not int \
                        or doc["cursor"] < 1 or "last" not in doc or not (doc["last"] is None or isinstance(doc["last"], dict)):
                    raise Unknown("作者事件帳讀不到或格式不合")
                last = doc["last"]
                if last is not None and (not all(k in last for k in ("seq", "event_id", "rid", "result", "request_sha"))
                        or type(last["seq"]) is not int or last["seq"] != doc["cursor"] - 1
                        or last["result"] not in ("registered", "dup", "invalid", "conflict", "ignored")):
                    raise Unknown("作者事件帳讀不到或格式不合")
                if doc["events"] != events:
                    return result(False, "conflict", error="事件目錄與作者游標不符")
                cursor = doc["cursor"]
            if cursor > 1:
                test_point("author:intake-after-receipt")  # 恢復仍在同一個回條與 ack 窗口，可連續殺死
                acked = store.ack(events, cursor - 1)
            for _ in range(limit):
                got = reader.read(events, "must", cursor=cursor, limit=1)
                if got["errors"]:
                    raise Unknown("事件讀取有錯：%s" % got["errors"])
                if not got["records"]:
                    break
                rec = got["records"][0]
                rid, rsha, answer, error = _intake_record(nd, rec)
                if answer == "unknown":
                    raise Unknown(error or "登記結果不明")
                seq = rec["seq"]
                last = dict(seq=seq, event_id=rec.get("event_id"), rid=rid, result=answer, request_sha=rsha)
                if error:
                    last["error"] = error
                test_point("author:intake-before-receipt")
                write_json(path, dict(v=1, events=events, cursor=seq + 1, last=last))
                cursor = seq + 1
                handled.append(dict(seq=seq, rid=rid, result=answer))
                test_point("author:intake-after-receipt")
                acked = store.ack(events, seq)
        return result(True, handled=handled, cursor=cursor, acked_upto=acked)
    except (Unknown, OSError, ValueError, KeyError, TypeError) as e:
        return result(False, "unknown", handled=handled, error=str(e))
