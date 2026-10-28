# act.py - selfopt host 的 act 格（照 demo/agent-dan／writer 的 act.py）：有 tool_calls 就逐個 aos-exec tools/<名>（環境加 SELFOPT_SESSION）、結果接回 history；
#   沒有＝收工：$AOS_WS/selfopt/<n>/report.json（腦的報告、改了哪些檔的 diff、叫了哪些工具、用量、越界嘗試）、out/<n>.txt（腦的報告原文）、
#   這個 session 沒有成功寫過 note＝host 補記一筆 lifecycle.history（by host）、題目 cur/→done/。
# 工具失敗（結束碼非 0）照 agent-dan：stdout 那行回給腦、不停線；邊界與預算是工具自己擋（guard）。
# 自己的錯一行 stderr「selfopt: 代號 原因」退 1：StackMissing、HistoryBad、ToolFailed（起不來）。
import difflib, json, os, shutil, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import guard  # noqa: E402


def die(code, reason):
    print("selfopt: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.path.realpath(os.environ.get("AOS_WS", "."))
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    history.append(json.loads(line))
                except ValueError as e:
                    die("HistoryBad", "history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
except FileNotFoundError:
    pass
last = max((i for i, m in enumerate(history) if isinstance(m, dict) and m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
said = history[last]
with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
    name = f.read().strip()
session_path = os.path.join(ws, "selfopt", name, "session.json")


def append(message):
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


calls = said.get("tool_calls") or []
if calls:
    answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
    tools = sorted(t for t in (os.listdir("tools") if os.path.isdir("tools") else []) if os.path.isfile(os.path.join("tools", t, "_tooldef.json")))
    for call in calls:
        try:
            cid, tname, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
        except (KeyError, TypeError):
            die("HistoryBad", "tool_calls 裡有一個沒有 id 或 function.name：%s" % json.dumps(call, ensure_ascii=False))
        if cid in answered:
            continue
        if tname not in tools:
            append({"role": "tool", "tool_call_id": cid, "content": "act: ToolUnknown %s（能叫的：%s）\n" % (tname, "、".join(tools))})
            continue
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments or {}, ensure_ascii=False)
        env = dict(os.environ, AOS_STACK=os.path.join(stack, tname) + "/", SELFOPT_SESSION=session_path)
        try:
            r = subprocess.run(["aos-exec", "tools/" + tname], input=arguments, stdout=subprocess.PIPE, text=True, env=env)
        except OSError as e:
            die("ToolFailed", "%s 起不來：%s" % (tname, e))
        content = r.stdout
        if r.returncode != 0:
            print("selfopt: ToolFailed %s 結束碼 %d（回給腦）" % (tname, r.returncode), file=sys.stderr)
            content += "%s(工具 %s 結束碼 %d)\n" % ("" if content.endswith("\n") or not content else "\n", tname, r.returncode)
        append({"role": "tool", "tool_call_id": cid, "content": content})
    sys.exit(0)

# ── 收工 ──
session = guard.jload(session_path, {}) or {}
node = session.get("node", "")
home = os.path.realpath(os.path.join(ws, "tree", node))
vdir = os.path.join(home, guard.VERSIONS, "selfopt_" + name)
diffs = {}
for rel, how in sorted((guard.read_meta(vdir).get("files") or {}).items()):
    cur = os.path.join(home, rel)
    if how == "created":
        diffs[rel] = "（新建）" + (", ".join(sorted(os.listdir(cur))) if os.path.isdir(cur) else "")
        continue
    a = open(os.path.join(vdir, rel), encoding="utf-8").read()
    b = open(cur, encoding="utf-8").read() if os.path.exists(cur) else ""
    if rel.endswith(".json") or rel == "_metainfo":       # JSON 先正規化（indent 1）再比，edit_self 的 set 整份重排時 diff 只剩真的改動
        try:
            a, b = (json.dumps(json.loads(x), ensure_ascii=False, indent=1) + "\n" for x in (a, b))
        except ValueError:
            pass
    diffs[rel] = "".join(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True), "a/" + rel, "b/" + rel, n=1))
noted = session.get("counter_notes", 0) > 0
if not noted and os.path.isdir(home):
    os.environ["SELFOPT_SESSION"] = session_path
    try:
        ctx = guard.Ctx("host")
        noted_by_host = ctx.append_history(guard.history_entry(session, home, "（腦沒叫 note；host 收工補記）", by="host"))
    except guard.Fail:
        noted_by_host = False
else:
    noted_by_host = False
content = said.get("content") or ""
report = {"session": name, "node": node, "goal": session.get("goal"), "answer": content,
          "tools_called": [c.get("tool") + ("（拒：%s）" % c["refused"] if c.get("refused") else "") for c in session.get("calls") or []],
          "counter_calls": session.get("counter_calls", 0), "counter_tokens": session.get("counter_tokens", 0),
          "counter_tokens_brain": session.get("counter_tokens_brain", 0), "counter_tokens_tests": session.get("counter_tokens_tests", 0),
          "edits": session.get("edits") or [], "diff": diffs, "self_tests": session.get("self_tests") or [],
          "attempted_violations": session.get("attempted_violations") or [], "noted": "note" if noted else ("host" if noted_by_host else "none"),
          "finished_at": guard.now()}
guard.write_json(os.path.join(ws, "selfopt", name, "report.json"), report)
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
guard.write_text(os.path.join(ws, "out", name + ".txt"), content if content.endswith("\n") else content + "\n")
shutil.move(os.path.join(ws, "cur", name + ".json"), os.path.join(ws, "done", name + ".json"))
