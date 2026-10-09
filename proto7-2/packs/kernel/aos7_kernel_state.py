"""kernel 包的設定、state 與快照（spec.md §2～§4）。只讀寫：kernel.json（讀）、自己槽的 state.json／decisions.json、
來源的公開檔（birth.json、brain/task.json、round.json，只讀）。不呼叫核心會收程序的判定。"""
import hashlib
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))           # proto7-2/
sys.path[:0] = [os.path.join(TOP, "lib"), os.path.join(TOP, "modules", "tools")]
from aos7_fs import BAD, N, OK, ROUND_CLOSED, ROUND_NONE, ROUND_OPEN, fact, is_int, read_round, write_json  # noqa: E402

V = 1
DONE_KEEP = 20
KINDS = ("brain",)
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class Stop(Exception):
    """要停下來的情況：code 照統一退出碼（1 做不到、2 你給的不對、3 不知道），msg 是給人的一行。"""

    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# ---------- 設定（§2） ----------

def config_path(node):
    return os.path.join(node, "kernel", "kernel.json")


def sha_of(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                          .encode("utf-8")).hexdigest()[:16]


def _where(x):
    return isinstance(x, dict) and isinstance(x.get("node"), str) and x["node"] != "" \
        and isinstance(x.get("slot"), str) and NAME_RE.match(x["slot"]) is not None


def load_config(node, rule_names):
    """讀並驗證 kernel.json，回 (cfg, sha)。不合丟 Stop(2)；讀不到丟 Stop(3)。"""
    path = config_path(node)
    st, cfg = fact(path)
    eg = '例：{"v":1,"sources":[{"node":".","slot":"brain","kind":"brain"}],"targets":[{"node":".","slot":"brain"}],' \
         '"rules":[{"name":"supervise-brain"}]}'
    if st == N:
        raise Stop(2, "%s 不存在。照 spec 寫一份，%s" % (path, eg))
    if st not in (OK, BAD):
        raise Stop(3, "不確定：kernel.json 讀不到（%s），什麼都沒動。等一下照原樣再跑" % cfg)
    why = None
    if st == BAD or not isinstance(cfg, dict):
        why = "不是 JSON 物件"
    elif cfg.get("v") != V:
        why = "v 要是 1"
    elif not isinstance(cfg.get("sources"), list) or not all(_where(s) and s.get("kind") in KINDS for s in cfg["sources"]):
        why = "sources 每項要有 node、slot，kind 只有 brain"
    elif not isinstance(cfg.get("targets"), list) or not all(_where(t) for t in cfg["targets"]):
        why = "targets 每項要有 node、slot"
    elif any(not any(same_place(t, s) for s in cfg["sources"]) for t in cfg["targets"]):
        why = "targets 每項都要也在 sources 裡（看得到才能控制）"
    elif not isinstance(cfg.get("rules"), list) or not cfg["rules"] \
            or not all(isinstance(r, dict) and r.get("name") in rule_names for r in cfg["rules"]):
        why = "rules 要是非空清單，name 只能是 %s" % "、".join(sorted(rule_names))
    elif len({r["name"] for r in cfg["rules"]}) != len(cfg["rules"]):
        why = "rules 的 name 不能重複"
    elif cfg.get("events", False) is not False:
        why = "events 第一版只收 false"
    elif "mail" in cfg and not (isinstance(cfg["mail"], dict) and isinstance(cfg["mail"].get("root"), str)
                                and NAME_RE.match(str(cfg["mail"].get("from", "kernel")))):
        why = 'mail 要像 {"root": "..", "from": "kernel"}'
    if why:
        raise Stop(2, "kernel.json 不合：%s。改好再跑，%s" % (why, eg))
    return cfg, sha_of(cfg)


def same_place(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and norm_node(a.get("node")) == norm_node(b.get("node")) \
        and a.get("slot") == b.get("slot")


def norm_node(n):
    n = os.path.normpath(n) if isinstance(n, str) and n else n
    return "." if n in ("", ".") else n


def node_dir(env, node_id, resolve):
    """來源／目標 node id → 實際路徑；自己的 node 直接用 AOS7_NODE，別的經掛載（spec §2）。掛不到回 None。"""
    nid = norm_node(node_id)
    if nid == "." or nid == norm_node(env["node_id"]):
        return env["node"]
    return resolve(nid)


def slot_dir(env, where, resolve):
    d = node_dir(env, where["node"], resolve)
    return None if d is None else os.path.join(d, ".aos", "tasks", where["slot"])


# ---------- state（§3） ----------

def state_path(task):
    return os.path.join(task, "state.json")


def decisions_path(task):
    return os.path.join(task, "decisions.json")


def _state_ok(s):
    return isinstance(s, dict) and s.get("v") == V and isinstance(s.get("config_sha"), str) \
        and isinstance(s.get("instance"), str) and is_int(s.get("rev")) and is_int(s.get("last_tock")) \
        and isinstance(s.get("rules"), dict) and isinstance(s.get("pending"), list) \
        and all(isinstance(p, dict) and isinstance(p.get("id"), str) and p.get("op") in ("kill", "notify")
                for p in s["pending"]) and isinstance(s.get("done"), list)


def load_state(task, sha, init=True):
    """讀自己的 state。確定不存在且從沒跑過（沒 decisions.json）＝初始化（init=False 時只回新 state、不寫）；
    其餘不合丟 Stop：弄丟了 1、讀不到或壞掉 3、設定雜湊不合 1。絕不拿空 state 蓋掉讀不到的。"""
    st, s = fact(state_path(task))
    if st == N:
        dst, _ = fact(decisions_path(task))
        if dst != N:
            raise Stop(1, "state.json 不見了（這個槽之前跑過），不自動重建，免得重送或漏掉在途的 kill。"
                          "確認目標都沒有在途的 ctl.json 後，刪掉 %s 再起" % decisions_path(task))
        s = {"v": V, "config_sha": sha, "instance": uuid.uuid4().hex, "rev": 0, "last_tock": 0,
             "rules": {}, "pending": [], "done": [], "last_error": None}
        if init:
            save_state(task, s)
            write_json(decisions_path(task), {"tock": None, "at": None, "decided": [], "rejected": None,
                                              "note": "初始化 instance %s" % s["instance"]})
        return s
    if st != OK or not _state_ok(s):
        raise Stop(3, "不確定：%s 讀不到或內容不合（%s），什麼都沒動。磁碟正常就照原樣再跑；檔壞了請人看過再處理"
                   % (state_path(task), s if st != OK else "欄位不合"))
    if s["config_sha"] != sha:
        raise Stop(1, "kernel.json 跟 state 記的不同（%s≠%s），停止新的決定，在途的留著。改回原樣就接續；"
                      "要換設定，等 pending 清空後刪掉 state.json 與 decisions.json" % (sha, s["config_sha"]))
    return s


def save_state(task, s):
    """一次 rename 存整份 state（呼叫的人傳新的那份；失敗丟 OSError，呼叫的人不把記憶體換成新的）。"""
    s = dict(s, done=s["done"][-DONE_KEEP:])
    write_json(state_path(task), s)
    return s


# ---------- 快照（§4） ----------

def completed_tock(node):
    st, r, _ = read_round(os.path.join(node, ".aos", "round.json"))
    if st == ROUND_CLOSED:
        return r["round"]
    if st == ROUND_OPEN:
        return r["round"] - 1
    return 0 if st == ROUND_NONE else None


def _read(path):
    """四態讀：回 (read, value)。"""
    st, v = fact(path)
    if st == OK:
        return ("ok", v) if isinstance(v, dict) else ("bad", None)
    return {N: "absent", BAD: "bad"}.get(st, "unknown"), None


def _birth_run(path):
    r, b = _read(path)
    return r, (b.get("run") if r == "ok" and is_int(b.get("run")) else None), b


def snapshot(env, cfg, resolve):
    """每個來源兩項（birth.json、brain/task.json），帶 run／seq／completed_tock／read（spec §4）。"""
    out = []
    for src in cfg["sources"]:
        src = {"node": src["node"], "slot": src["slot"], "kind": src["kind"]}
        node = node_dir(env, src["node"], resolve)
        if node is None:
            for f in (".aos/tasks/%s/birth.json" % src["slot"], "brain/task.json"):
                out.append({"src": src, "file": f, "run": None, "seq": None, "completed_tock": None,
                            "read": "unknown", "value": None})
            continue
        bpath = os.path.join(node, ".aos", "tasks", src["slot"], "birth.json")
        clock = completed_tock(node)
        r1, run1, birth = _birth_run(bpath)
        tr, task = _read(os.path.join(node, "brain", "task.json"))
        r2, run2, _ = _birth_run(bpath)
        same = r1 == "ok" and r2 == "ok" and run1 is not None and run1 == run2
        brun = run1 if same else None
        out.append({"src": src, "file": ".aos/tasks/%s/birth.json" % src["slot"], "run": brun, "seq": None,
                    "completed_tock": clock, "read": r1 if r1 != "ok" or same else "unknown",
                    "value": birth if r1 == "ok" and same else None})
        if tr == "ok" and not same:
            tr, task = "unknown", None
        seq = task.get("step") if tr == "ok" and is_int(task.get("step")) else None
        out.append({"src": src, "file": "brain/task.json", "run": brun, "seq": seq, "completed_tock": clock,
                    "read": tr, "value": task})
    return out
