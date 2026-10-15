"""通用 kernel（aos_kernel_general.py）的判官那一半：跑判官格、讀它的答案、判官錯時用的確定規則。純標準庫。說明在 kernel_general.md。

判官＝一張 inst（N-12）：stdin＝kernel 的 state 窗只留 queue、running、slots、budget 四個 key（同一份物件的子集，C-48），
stdout 最後一份＝{"run": [id…], "reject": [{"id", "error": {"code", "msg"}}]}（reject 的錯誤＝N-29 形狀）；沒點名的＝不是我挑的
（原本還有 `defer` 一個 key 說同一件事，10-15 深夜 KISS 批次 1 拿掉）。
kernel 跑判官跟跑任何 inst 一樣：環境變數、逾時（判官 inst 自己寫 `timeout_ms`，沒寫＝不限）一個都不碰（C-52）。

相依：aos_inst ← aos_kernel_llm（order）← aos_kernel_judge ← aos_kernel_general。
"""
import json
import os
import shutil
import tempfile

import aos_cli
import aos_inst
from aos_cli import CliError
from aos_kernel_llm import order

__all__ = ["JUDGE_KEYS", "ask_judge", "decide_rules", "parse_decision", "resource"]

JUDGE_KEYS = ("queue", "running", "slots", "budget")   # 判官的 stdin＝state 窗的這幾個 key（輸入小，小模型才快）


def resource(doc):
    """信的資源種類（`_metainfo.resource`）；沒寫＝None（kernel 當 ResourceUnknown：會經閘門排隊的 inst 就是要佔格的）。"""
    meta = doc.get("_metainfo")
    return meta.get("resource") if isinstance(meta, dict) else None


# ---- 判官 ----

def parse_decision(text, queue):
    """判官 stdout（最後一份 JSON）→ {run, reject}。reject 每項 {"id", "error": {"code", "msg"}}（N-29）。
    不認得的 id 丟掉；同一個 id 出現兩次、形狀不對丟 ValueError。"""
    docs = aos_cli.read_stream(text)
    d = docs[-1] if docs else None
    if not isinstance(d, dict) or set(d) - {"run", "reject"}:
        raise ValueError("判官要回 {run, reject}，回的是 %r" % (d,))
    run, reject = d.get("run", []), d.get("reject", [])

    def err_ok(r):
        e = r.get("error") if isinstance(r, dict) else None
        return isinstance(r.get("id"), str) and isinstance(e, dict) and isinstance(e.get("code"), str) \
            and isinstance(e.get("msg", ""), str)
    if not (isinstance(run, list) and isinstance(reject, list)
            and all(isinstance(x, str) for x in run) and all(isinstance(r, dict) and err_ok(r) for r in reject)):
        raise ValueError("run 要是 id 字串陣列、reject 要是 [{id, error: {code, msg}}]")
    ids = run + [r["id"] for r in reject]
    if len(ids) != len(set(ids)):
        raise ValueError("同一個 id 出現兩次")
    return {"run": [x for x in run if x in queue],
            "reject": [{"id": r["id"], "error": {"code": r["error"]["code"], "msg": r["error"].get("msg", "")}}
                       for r in reject if r["id"] in queue]}


def decide_rules(queue, free, seen, n, now, cfg):
    """第一種的確定規則（級數＋aging＋deadline 插隊＋先來後到），每種資源各自補滿空格。"""
    left, run = dict(free), []
    for name, doc in order(list(queue.items()), seen, n, now, cfg):
        k = resource(doc)
        if left.get(k, 0) > 0:
            left[k] -= 1
            run.append(name)
    return {"run": run, "reject": []}


def ask_judge(cfg, snap, ids):
    """跑判官格：stdin＝state 窗 snap 的 JUDGE_KEYS 子集。回決定；結束碼非 0、逾時、起不來、形狀不對丟 ValueError（帶原因）。"""
    j = cfg["judge"]
    try:
        inst = aos_inst.load(j) if isinstance(j, str) else aos_inst.parse(j, os.getcwd(), "<judge>")
    except CliError as e:
        raise ValueError("%s：%s" % (e.code, e.msg))
    tmp = tempfile.mkdtemp(prefix="aos-judge-")
    try:
        files = {k: os.path.join(tmp, k) for k in ("stdin", "stdout")}
        with open(files["stdin"], "w", encoding="utf-8") as f:
            json.dump({k: snap[k] for k in JUDGE_KEYS if k in snap}, f, ensure_ascii=False)
        inst = dict(inst, stdin=files["stdin"], stdout=files["stdout"], stderr=None,
                    stdout_append=False, stdout_mkdir=False, stderr_merge=False)
        try:
            res = aos_inst.run(inst)
        except aos_inst.InstError as e:
            raise ValueError("%s：%s" % (e.code, e.msg))
        if res["timed_out"] or res["code"] != 0:
            raise ValueError("判官%s（碼 %d）" % ("逾時" if res["timed_out"] else "結束碼非 0", res["code"]))
        with open(files["stdout"], encoding="utf-8", errors="replace") as f:
            return parse_decision(f.read(), ids)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
