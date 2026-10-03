"""hsched 的 policy-agent／picker（keep 任務，node `ctl`）：讀 kernel 發的 `requests/<rev>.json`，寫 `answers/<rev>.txt`
（原文，可能是壞的）與 `answers/<rev>.meta.json`（{round, tokens, calls, secs, model, error}；meta 寫好才算到）。
只碰自己的 node；kernel 從不等它。

`cfg.json` 的 `agent`：
  {"mode": "script", "script": {"policy": {...}, "pick": {...}}}   離線：預錄回答（run_all 用，不打 LLM）
      每種請求依出現順序編號 0,1,2…；script[kind][str(序號)] 或 script[kind]["default"]：
        {"delay": k}       到 請求回合＋k 才寫         {"late": k}   到 期限＋k 才寫（晚 k 回合）
        {"raw": "..."}     原文照寫（壞 JSON）          {"override": {...}}  蓋在產生的合格回答上（超父額、舊 epoch、pause 自己）；C 的 "jobs": "@all"＝全挑
        {"choice": {...}}  D 的政策內容                 C 的挑選規則固定：最早到的先、照空位
  {"mode": "real", "model": "deepseek-chat", "max_calls": N}       真模型：只打 LiteLLM 127.0.0.1:4000
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import aos7_fs as fs  # noqa: E402
import sim  # noqa: E402

NODE = os.environ.get("AOS7_NODE", ".")
RQ = os.path.join(NODE, "requests")
AN = os.path.join(NODE, "answers")
cfg = (fs.read_json(os.path.join(NODE, "cfg.json"), {}) or {}).get("agent") or {}
CNT = os.path.join(NODE, "agent-calls.json")
URL = "http://127.0.0.1:4000/v1/chat/completions"

SYS_POLICY = """你是 aos 的政策 agent。一個確定性 kernel 每個控制回合（約 1 秒）照「目前有效的政策」派工給兩個專案 P、Q；
你不直接派工，只提出接下來一段期間的政策。只輸出一個 JSON 物件，不要任何其他文字。

格式：
{"schema": "aos.agent-policy-proposal.v1", "proposal_id": "自取", "input_revision": 照抄, "envelope_id": 照抄,
 "validity": {"clock_node": "ctl", "epoch": 照抄, "until_round": 整數},
 "choice": {...}, "pause": [], "reason_code": "短代號", "why": "一句話", "evidence": ["..."]}

choice 可調的欄位（都可省略，省略＝預設值）：
- group_policy："stride_inspired"（預設：兩專案權重 1:1，依 token 份額輪流）或 "interactive_first"（任一專案有互動工作就先派互動）
- interactive_max_wait_rounds：1～20 或 null（預設 null）。互動工作等到這麼多回合就插到最前
- dependency_donation：true／false（預設 false）。被依賴擋住的互動工作，把優先權借給它等的那件
- max_calls_inflight：1～3（預設 3）。每專案同時在途上限；父 envelope 只給 3，超過整份被拒
- background_max_inflight：1～4（預設 4）。非互動工作全域同時在途上限；全域只有 4 個位子，設小＝留位子給互動
pause 只能列 "P" 或 "Q"（這段期間不派該專案），不能列 "ctl"。
until_round 要大於現在的回合、最多現在＋40。input_revision、envelope_id、epoch 照抄輸入；晚於 respond_by 才到的會被拒。

工作：互動工作便宜（150～300 token、做 1 回合），期限 8 回合；背景工作昂貴（2000～3000 token、做 6～8 回合），期限 60 回合；
檢索工作期限 30 回合。目標：互動等待短、背景不要過期、不要浪費額度。"""

SYS_PICK = """你是排程器，直接挑現在要開工的工作。只輸出一個 JSON 物件，不要任何其他文字：
{"schema": "aos.pick.v1", "input_revision": 照抄, "epoch": 照抄, "jobs": ["工作 id", ...], "why": "一句話"}
規則：jobs 只能從 ready 裡挑；件數不超過 free_slots.global，每個專案不超過 free_slots 裡該專案的數字；
每專案同時在途上限 3、全域 4。互動工作（interactive）期限 8 回合、背景 60 回合、檢索 30 回合；
waited 是已經等了幾回合。要在 respond_by 回合之前回答（每回合約 1 秒），晚了作廢，由保底規則代派。"""


def rnd():
    return (fs.read_json(os.path.join(NODE, ".aos", "round.json"), {}) or {}).get("round", 0)


def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def good_policy(req, choice):
    return {"schema": "aos.agent-policy-proposal.v1", "proposal_id": "policy-%d" % req["revision"],
            "input_revision": req["revision"], "envelope_id": req["envelope_id"],
            "validity": {"clock_node": sim.CTL, "epoch": req["epoch"], "until_round": req["round"] + 30},
            "choice": dict(choice), "pause": [], "reason_code": "scripted", "why": "預錄", "evidence": []}


def good_pick(req):
    inp = req["input"]
    free = dict(inp["free_slots"])
    jobs = []
    for j in sorted(inp["ready"], key=lambda j: (-j["waited"], j["id"])):
        if free["global"] <= 0:
            break
        if free.get(j["project"], 0) > 0:
            jobs.append(j["id"])
            free["global"] -= 1
            free[j["project"]] -= 1
    return {"schema": "aos.pick.v1", "input_revision": req["revision"], "epoch": req["epoch"], "jobs": jobs,
            "why": "預錄：最早到的先"}


def calls_used():
    return (fs.read_json(CNT, {}) or {}).get("calls", 0)


def llm(req):
    """真模型：一次 chat completion。回 (原文, tokens, error)。"""
    sysmsg = SYS_POLICY if req["kind"] == "policy" else SYS_PICK
    user = {k: req[k] for k in ("revision", "round", "respond_by", "epoch", "envelope_id")}
    user["input_revision"] = user.pop("revision")
    user["now_round"] = user.pop("round")
    user.update(req["input"])
    body = {"model": cfg["model"], "temperature": 0, "max_tokens": 500 if req["kind"] == "policy" else 250,
            "messages": [{"role": "system", "content": sysmsg},
                         {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]}
    r = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            data = json.loads(resp.read())
        return (data["choices"][0]["message"].get("content") or ""), (data.get("usage") or {}).get("total_tokens", 0), None
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as e:
        return "", 0, str(e)[:200]


def answer(req, idx):
    kind = req["kind"]
    if cfg.get("mode") == "real":
        with LOCK:
            if calls_used() >= cfg.get("max_calls", 0):
                fs.append_jsonl(os.path.join(NODE, "agent.jsonl"), {"revision": req["revision"], "skip": "call cap"})
                return False
            fs.write_json(CNT, {"calls": calls_used() + 1})
        t0 = time.monotonic()
        raw, tok, err = llm(req)
        meta = {"tokens": tok, "calls": 1, "secs": round(time.monotonic() - t0, 2), "model": cfg["model"], "error": err}
    else:
        sc = (cfg.get("script") or {}).get(kind) or {}
        ent = sc.get(str(idx)) or sc.get("default") or {}
        target = req["round"] + ent.get("delay", 0)
        if "late" in ent:
            target = req["respond_by"] + ent["late"]
        while rnd() < target:
            time.sleep(0.005)
        if "raw" in ent:
            raw = ent["raw"]
        else:
            o = good_policy(req, ent.get("choice") or sc.get("choice") or {}) if kind == "policy" else good_pick(req)
            o = merge(o, ent.get("override") or {})
            if o.get("jobs") == "@all":            # 超父額：把現在可派的全挑上（比空位多）
                o["jobs"] = [j["id"] for j in req["input"]["ready"]]
            raw = json.dumps(o, ensure_ascii=False)
        meta = {"tokens": 0, "calls": 0, "secs": 0, "model": "script", "error": None, "script": ent}
    with open(os.path.join(AN, ".%06d.txt.tmp" % req["revision"]), "w", encoding="utf-8") as f:
        f.write(raw)
    os.replace(os.path.join(AN, ".%06d.txt.tmp" % req["revision"]), os.path.join(AN, "%06d.txt" % req["revision"]))
    meta["round"] = rnd()
    fs.write_json(os.path.join(AN, "%06d.meta.json" % req["revision"]), meta)
    return True


LOCK = threading.Lock()


def main():
    os.makedirs(AN, exist_ok=True)
    seen = set()
    count = {"policy": 0, "pick": 0}
    while True:
        for f in sorted(x for x in os.listdir(RQ) if x.endswith(".json") and not x.startswith(".")):
            rev = int(f[:-5])
            if rev in seen:
                continue
            req = fs.read_json(os.path.join(RQ, f))
            if not isinstance(req, dict):
                continue
            seen.add(rev)
            idx = count[req["kind"]]
            count[req["kind"]] += 1
            if os.path.exists(os.path.join(AN, "%06d.meta.json" % rev)):
                continue
            threading.Thread(target=answer, args=(req, idx), daemon=True).start()   # 晚回的不擋下一份
        time.sleep(0.005)


if __name__ == "__main__":
    main()
