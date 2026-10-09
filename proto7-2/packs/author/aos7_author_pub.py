"""author 包的發布與恢復（spec §5；llm-author §4.3 五列）：意圖 → 表鎖內只合併自己那一項 → 回條。

模型與驗證都在表鎖外；表鎖（tasks.json.lock）只用來重讀、比自己那一項、合併。作者寫者之間另有共用鎖 author/author.lock。
重啟看到舊 intent 一律走證據恢復，不因同 rid 自動補加；只有人手 --resend 能讓 unknown 的版本重走首次發布。
"""
import os

import aos7_author
from aos7_author import (MAX_VERSIONS, OK, N, Node, Refuse, Unknown, check_rid, fact, published, recompute_payload, result,
                         sha256, read_bytes, test_point, aos7_step)
from aos7_fs import edit_json

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
