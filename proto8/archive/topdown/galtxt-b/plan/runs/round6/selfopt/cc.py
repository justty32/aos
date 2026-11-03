"""cc.py FIELD fake|real [steps] — claude_code 示範：writer 交給 Claude Code 優化（FIELD 先用 demo.py 跑過 init r0 r1）。
steps：cc（叫工具）、r2（第 2 輪第一題 ×1 真腦／假腦 → score、record）。fake＝SELFOPT_CLAUDE_BIN 指假 claude（fakeclaude.py）。"""
import json, os, shutil, subprocess, sys, time
P8 = "/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a4ee4157053b3206d/proto8"
GB = P8 + "/topdown/galtxt-b"
HERE = os.path.dirname(os.path.abspath(__file__))
bins = [P8 + "/impls/%s/bin" % n for n in ("aos-exec", "aos-loop", "aos-fsm", "aos-daemon", "aos-json")]
F = os.path.abspath(sys.argv[1])
real = sys.argv[2] == "real"
steps = sys.argv[3:] or ["cc", "r2"]
Q1, W = "新書_宮澤_主角先_梅花章", "draft/tools/writer"
env = {k: v for k, v in os.environ.items() if not k.startswith(("AOS_", "GALTXT_", "SELFOPT_"))}
env["PATH"] = ":".join(bins + [env["PATH"]])
stack = F + "/.stack/"
sdir = F + "/selfopt/cc"
EVIDENCE = [
    "plan/runs/round6/measure.md（真腦 luna-low，每組 6 次）：現在的樹（有 trim）根 token 平均 20204／次、其中 writer 16612（3 次問腦：叫 lint、叫 trim、交稿）；總分 5.00（σ 0）；lint 違規 0/6；trim 被叫 6/6 但 changes 全空。",
    "不給 trim 的那組：根 token 19402、writer 15843；總分 4.83；3/6 次第一次叫 lint 漏給 brief_path（ArgumentsBad、再叫一次），幾乎每次自檢兩回。",
    "每多一次工具來回，整段對話要重送一次，約 +5000 token。",
    "對照：gpt 自我優化（同題同證據）改 system.txt 拿掉 trim、lint 無違規就直接交——真腦 2 次：4 分（旁白 5 行超上限、narration_max 回來了）與 5 分；writer token 16.4k、10.2k。",
    "第 1 輪的跑在 runs/1/（匯入的 6 次；run.json 有 tool_calls）。"]
if "cc" in steps and not os.path.exists(sdir + "/report.json"):
    os.makedirs(sdir, exist_ok=True)
    sess = {"session": "cc", "node": W, "goal": "請優化：降低 token 且分數不掉（證據：measure.md——lint 漏給 brief_path、自檢兩回、trim 叫了卻沒改字）",
            "round": 1, "max_calls": 3, "max_tokens": 0, "max_usd": 2.0, "self_test": "off", "counter_calls": 0, "counter_tokens": 0,
            "calls": [], "edits": [], "self_tests": [], "attempted_violations": [], "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(sess, open(sdir + "/session.json", "w"), ensure_ascii=False, indent=1)
    e = dict(env, AOS_STACK=sdir + "/.stack/", SELFOPT_SESSION=sdir + "/session.json")
    if not real:
        e["SELFOPT_CLAUDE_BIN"] = HERE + "/fakeclaude.py"
    t = time.time()
    r = subprocess.run(["aos-exec", "--ws", F, GB + "/lib/selfopt/claude_code"], input=json.dumps({"goal": sess["goal"], "evidence": EVIDENCE}, ensure_ascii=False),
                       env=e, capture_output=True, text=True, timeout=1200)
    print("claude_code", r.returncode, "%.0fs" % (time.time() - t), r.stderr[-800:])
    out = json.loads(r.stdout) if r.returncode == 0 else {"error": r.stdout}
    sess = json.load(open(sdir + "/session.json"))
    vdir = F + "/tree/" + W + "/versions/selfopt_cc"
    diffs = {}
    for rel, how in (json.load(open(vdir + "/_metainfo")).get("files") or {}).items() if os.path.exists(vdir + "/_metainfo") else []:
        a = vdir + "/" + rel if how == "saved" else "/dev/null"
        diffs[rel] = subprocess.run(["diff", "-u", a, F + "/tree/" + W + "/" + rel], capture_output=True, text=True).stdout
    json.dump({"session": "cc", "node": W, "goal": sess["goal"], "answer": out.get("result"), "out": out, "claude_code": sess.get("claude_code"),
               "tools_called": ["claude_code"], "counter_calls": 1, "counter_tokens": 0, "counter_tokens_brain": 0, "counter_tokens_tests": 0,
               "noted": "claude_code", "edits": sess["edits"], "diff": diffs, "self_tests": [], "attempted_violations": sess["attempted_violations"]},
              open(sdir + "/report.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out.get(k) for k in ("changed", "restored", "num_turns", "cost_usd", "usage", "permission_denials")}, ensure_ascii=False))
if "r2" in steps:
    cp = F + "/changes/1.json"
    if not os.path.exists(cp):
        rep = json.load(open(sdir + "/report.json"))
        os.makedirs(F + "/changes", exist_ok=True)
        json.dump({"round": 1, "moves": [{"kind": "selfopt", "via": "claude_code", "node": W, "status": "applied", "changed": sorted({x["path"] for x in rep["edits"]}),
                                          "cost_usd": (rep.get("claude_code") or {}).get("cost_usd")}],
                   "touched": [W], "cost": {"counter_tokens": 0, "cost_usd": (rep.get("claude_code") or {}).get("cost_usd")},
                   "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(cp, "w"), ensure_ascii=False, indent=1)
    json.dump({"round": 2}, open(stack + "round.json", "w"))
    ws = F + "/runs/2/%s/1" % Q1
    if not os.path.exists(ws + "/run.json"):
        shutil.rmtree(ws, ignore_errors=True)
        os.makedirs(ws + "/new")
        shutil.copy(F + "/set/%s.json" % Q1, ws + "/new/")
        e = dict(env, AOS_BRAIN_URL="http://localhost:4000/v1") if real else env
        t = time.time()
        r = subprocess.run(["aos-exec", "--ws", ws, F + "/tree"], env=e, capture_output=True, text=True, timeout=1500)
        json.dump({"code": r.returncode, "elapsed_ms": int((time.time() - t) * 1000)}, open(ws + "/run.json", "w"))
        print("run", r.returncode, r.stderr[-500:])
    for c in ("score", "record"):
        r = subprocess.run(["aos-exec", "--ws", F, GB + "/train/" + c], env=dict(env, AOS_STACK=stack), capture_output=True, text=True)
        print(c, r.returncode, r.stdout[-200:], r.stderr[-300:])
