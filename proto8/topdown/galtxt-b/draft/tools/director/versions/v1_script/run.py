# run.py - director 的固化版（round6 §1：lifecycle stage pure；舊版 versions/v0_agent（單發腦函數）、versions/v1_script（查表、查不到才叫腦））。
#   對外介面不變：認領 new/<n>.json（{"attempt", "brief", "feedback"}）→ out/<n>.txt 一份 beat 表 JSON、題目 cur/→done/（draft 照舊叫 aos-exec tools/director）。
#   順序固化在這支程式：叫 tools/plan_template（純函數，查 plans.json）→ 寫答案。不問腦。
#   查不到（表上沒有這組開關）＝不退回問腦、不停線：照 default 出表、答案帶 "degraded"，並在自己的小格寫一行難例
#   $AOS_STACK/hard_cases.jsonl（runtime 不寫定義資料夾，P-15；train/record 收、train/apply 的 teach 補上）。
#   FALLBACK＝"agent" 時（v1_script 的那份）查不到改叫 tools/agent（＝v0_agent）出表，這就是第 2 階 script 跟第 3 階 pure 的差別。
# 自己的錯一行 stderr「director: 代號 原因」退 1：StackMissing、QuestionMissing／QuestionBad、TemplateFailed、AgentFailed。
import json, os, shutil, subprocess, sys
from datetime import datetime, timezone

FALLBACK = "agent"                               # v1_script：查不到叫 tools/agent（＝v0_agent）


def die(code, reason):
    print("director: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted((n for n in os.listdir(os.path.join(ws, d)) if not n.startswith(".") and n.endswith(".json")),
                      key=lambda n: (len(n), n))
    except FileNotFoundError:
        return []


names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
fname = names[0]
name = fname[:-len(".json")]
try:
    with open(os.path.join(ws, "cur", fname), encoding="utf-8") as f:
        question = json.load(f)
    brief = question["brief"]
except (ValueError, KeyError, TypeError) as e:
    die("QuestionBad", "%s 不是 {brief, …}：%s" % (fname, e))

env = dict(os.environ, AOS_STACK=os.path.join(stack, "plan_template") + "/")
try:
    r = subprocess.run(["aos-exec", "tools/plan_template"], input=json.dumps({"brief": brief}, ensure_ascii=False),
                       stdout=subprocess.PIPE, text=True, env=env)
    got = json.loads(r.stdout) if r.returncode == 0 else None
except (OSError, ValueError) as e:
    die("TemplateFailed", "tools/plan_template 起不來或回的不是 JSON：%s" % e)
if not isinstance(got, dict) or not isinstance(got.get("plan"), dict):
    die("TemplateFailed", "tools/plan_template 結束碼 %d" % r.returncode)

answer = dict(got["plan"], source="plans.json#/plans/%s" % got.get("key") if got.get("hit") else "plans.json#/default",
              degraded=got.get("degraded") or [])
if not got.get("hit"):
    if FALLBACK == "agent":
        sub = os.path.join(stack, "agent") + "/"
        aws = os.path.join(sub, "ws")
        os.makedirs(os.path.join(aws, "new"), exist_ok=True)
        with open(os.path.join(aws, "new", "1.json"), "w", encoding="utf-8") as f:
            json.dump(question, f, ensure_ascii=False)
        r = subprocess.run(["aos-exec", "--ws", aws, "tools/agent"], env=dict(os.environ, AOS_STACK=sub), stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            die("AgentFailed", "tools/agent 結束碼 %d" % r.returncode)
        with open(os.path.join(aws, "out", "1.txt"), encoding="utf-8") as f:
            answer = f.read()
    else:
        case = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "node": "draft/tools/director",
                "input": {k: (brief.get("scene") or {}).get(k) for k in ("switches", "event", "must_mention", "cast", "intent")},
                "output": answer["source"], "reason": "；".join(answer["degraded"])}
        with open(os.path.join(stack, "hard_cases.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
content = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name + ".txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content.rstrip("\n") + "\n")
os.replace(tmp, os.path.join(ws, "out", name + ".txt"))
shutil.move(os.path.join(ws, "cur", fname), os.path.join(ws, "done", fname))
