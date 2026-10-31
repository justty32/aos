"""aos_ai_agents - aos-ai 對單隻 agent 的命令：templates、spawn、ask、run、status、answer、wait、trace、history、exec（前景跑、讀 stack）。

10-31 自 bin/aos-ai 拆出（行為不變）。"""
import fcntl, json, os, shutil, signal, subprocess, sys, time
from pathlib import Path
from aos_ai_base import AGAIN, DAN_TOOLS, Daemon, Fail, HINTS, TEMPLATE, TEMPLATES, aos_ws, child_env, clip, env_pairs, hint_for, need, now, out, parse_errors, read_json, read_text, register_tool, tail_jsonl, tool_rows, write_atomic


def cmd_templates(root, o, pos):
    rows = []
    for d in sorted(TEMPLATES.iterdir()):
        if d.name.startswith("agent-") and (d / "_entry").exists():
            rows.append({"name": d.name, "path": str(d), **tool_rows(d)})
    out({"ok": True, "templates": rows, "default": TEMPLATE,
         "bundled_tools": sorted(p.name for p in DAN_TOOLS.iterdir() if (p / "_tooldef.json").exists())})


def resolve_src(spec, home, what):
    p = Path(spec) if ("/" in spec or spec.startswith(".")) else home / spec
    if not p.is_dir():
        raise Fail(what + "Missing", "找不到%s：%s" % ({"Template": "範本", "Tool": "工具"}[what], spec),
                   "aos-ai templates 看有哪些")
    return p.resolve()


def absolutize(src, reg, key):
    """複製來的註冊檔（parts.json／tools.json）：每一格 {"path": 相對路徑} 從範本資料夾算、指到範本外面的，改成絕對路徑。
    指在範本裡面的（例 tools/clock，跟著複製了）照舊相對；指示詞（$ref／$env）與不是字串的不碰；沒有要改的就不寫檔。"""
    if not reg.is_file():
        return
    data = read_json(reg)
    table = data.get(key) if isinstance(data, dict) else None
    if not isinstance(table, dict) or "$ref" in table or "$env" in table:
        return
    changed = False
    for row in table.values():
        path = row.get("path") if isinstance(row, dict) else None
        if not isinstance(path, str) or os.path.isabs(path):
            continue
        target = os.path.normpath(os.path.join(src, path))           # 不解開捷徑（同 add 存 abspath）
        if target != str(src) and not target.startswith(str(src) + os.sep):
            row["path"], changed = target, True
    if changed:
        write_atomic(reg, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def cmd_spawn(root, o, pos):
    need(pos, 1, "spawn NAME [--from 範本] [--tool 工具]...")
    a = root.agent(pos[0], must=False)
    if a.base.exists():
        raise Fail("AgentExists", "已經有 %s 了：%s" % (a.name, a.base), "換個名字，或直接 aos-ai ask %s" % a.name)
    src = resolve_src(o.get("from", [TEMPLATE])[-1], TEMPLATES, "Template")
    tools = [resolve_src(t, DAN_TOOLS, "Tool") for t in o.get("tool", [])]
    for t in tools:
        if (src / "tools" / t.name).exists():
            raise Fail("ToolExists", "範本裡已經有工具 %s" % t.name)
    ignore = shutil.ignore_patterns("__pycache__", ".stack", "*.pyc")
    shutil.copytree(src, a.agent, symlinks=True, ignore=ignore)
    for link in [p for p in a.agent.rglob("*") if p.is_symlink()]:     # 範本裡指出範本的相對捷徑（例：tools/read -> ../../../lib/base/read）
        target = os.readlink(link)                                      # 搬到新位置會斷：改成指同一個東西的絕對路徑（照舊跟著庫走）
        if not os.path.isabs(target) and not link.exists():
            orig = src / link.relative_to(a.agent)
            if orig.exists():
                link.unlink()
                link.symlink_to(orig.resolve())
    for reg in ("parts.json", "tools.json"):                           # 註冊檔裡指出範本的相對路徑（例：agent-nia 的 ../../lib/agent/round）
        absolutize(src, a.agent / reg, "parts" if reg == "parts.json" else "tools")   # 搬家會斷：改成絕對（同 aos-parts／aos-tools add）
    for t in tools:
        shutil.copytree(t, a.agent / "tools" / t.name, symlinks=True, ignore=ignore)
        register_tool(a.agent, a.agent / "tools" / t.name)             # 範本的 tools.json 是相對路徑、複製後照用；加的工具登記絕對路徑
    a.stack.mkdir(parents=True, exist_ok=True)         # 工作區只放成品；queue 由 ask 在 stack 裡建
    out({"ok": True, "name": a.name, "from": str(src), "agent": str(a.agent), "ws": str(a.ws), **tool_rows(a.agent)})


def cmd_ask(root, o, pos):
    need(pos, 2, "ask NAME 題目文字（或 - 從 stdin 讀）")
    a = root.agent(pos[0])
    text = sys.stdin.read() if pos[1:] == ["-"] else " ".join(pos[1:])
    if not text.strip():
        raise Fail("QuestionBad", "題目是空的")
    os.environ["PATH"] = child_env()["PATH"]           # aos_ws.put 叫 PATH 上的 aos-post
    try:                                                # 寄一封有序的信進 ws/.stack/queue/（aos_ws.put，跟 aos-say 同一份）
        qid = aos_ws.put(str(a.stack), text)
    except aos_ws.Error as e:
        raise Fail(e.code, str(e), HINTS.get(e.code))
    out({"ok": True, "name": a.name, "id": qid, "path": str(a.stack / "queue" / "new" / qid),
         "next": "aos-ai run %s（前景跑完）或 aos-ai start %s（背景）" % (a.name, a.name)})


def run_group(argv, env, cwd, timeout, stdin=None):
    """起一個自成行程群組的子行程、等它；逾時送 SIGTERM 給整群、10 秒後 SIGKILL。回 (碼, stdout, stderr, 逾時?, ms)。"""
    t0 = time.monotonic()
    p = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        so, se = p.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid, signal.SIGTERM)
        try:
            so, se = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            so, se = p.communicate()
    return p.returncode, so, se, timed_out, int((time.monotonic() - t0) * 1000)


def code_fields(rc):
    return {"code": 128 - rc if rc < 0 else rc, "signal": -rc if rc < 0 else None}


def cmd_run(root, o, pos):
    need(pos, 1, "run NAME [--timeout 秒] [--env K=V]...")
    a = root.agent(pos[0])
    if Daemon(root).row(a.name) and Daemon(root).row(a.name).get("phase") in ("running", "stopping"):
        raise Fail("AgentBusy", "%s 正在背景跑" % a.name, "等它（aos-ai wait）或先 aos-ai stop %s" % a.name)
    with open(a.base / ".run.flock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Fail("AgentBusy", "%s 已經有一個 aos-ai run 在跑" % a.name, "等它跑完")
        before, asked = len(a.answers()), a.waiting()
        extra = {"AOS_STACK": str(a.stack) + "/"}       # 明寫：被別的 aos 程式叫時外面的 AOS_STACK 不能漏進來
        extra.update(env_pairs(o))
        rc, so, se, timed_out, ms = run_group(["aos-exec", "--ws", str(a.ws), str(a.agent)], child_env(extra),
                                              str(a.base), float(o.get("timeout", ["300"])[-1]))
    errors = parse_errors(se)
    got = a.answers()
    answers = [{"text": clip(t)} for t in got[before:] if before <= len(got)]    # 這次 history 新長出來的回答
    left = a.waiting()
    res = {"ok": rc == 0 and not timed_out, "name": a.name, **code_fields(rc), "timed_out": timed_out,
           "elapsed_ms": ms, "answers": answers, "answered": [q for q in asked if q not in left], "waiting": left,
           "loop_phase": (aos_ws.loop_state(str(a.stack)) or {}).get("phase"),
           "fsm_state": read_text(a.stack / "state.txt"), "errors": errors}
    if so.strip():
        res["stdout"] = clip(so)
    if not res["ok"]:
        res["hint"] = ("超過 --timeout 被收掉；" + AGAIN) if timed_out else hint_for(errors) or AGAIN
    with open(a.base / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"finished_at": now(), **{k: res[k] for k in ("code", "signal", "timed_out", "elapsed_ms", "errors")},
                            "answered": res["answered"], "counter_answers": len(answers)}, ensure_ascii=False) + "\n")
    out(res)


def agent_status(root, a, brief=False):
    d = Daemon(root)
    s = {"name": a.name, "fsm_state": read_text(a.stack / "state.txt"),
         "loop_phase": (aos_ws.loop_state(str(a.stack)) or {}).get("phase"),
         "new": a.ls("new"), "cur": a.ls("cur"), "done": a.ls("done"), "counter_answers": len(a.answers()),
         "background": d.row(a.name), "last_run": (tail_jsonl(a.base / "runs.jsonl", 1) or [None])[0]}
    if not brief:
        s["trace_tail"] = tail_jsonl(a.stack / "trace.jsonl", 5)
        s["paths"] = {"agent": str(a.agent), "ws": str(a.ws), "stack": str(a.stack),
                      "cfgs": sorted(str(p.relative_to(a.agent)) for p in a.agent.rglob("*.json")
                                     if "__pycache__" not in p.parts),
                      **tool_rows(a.agent)}
    return s


def cmd_status(root, o, pos):
    if pos:
        out({"ok": True, **agent_status(root, root.agent(pos[0]))})
        return
    names = sorted(p.name for p in (root.dir / "agents").glob("*") if (p / "agent").is_dir())
    out({"ok": True, "root": str(root.dir), "daemon_pid": Daemon(root).running(),
         "agents": [agent_status(root, root.agent(n), brief=True) for n in names]})


def find_answer(a, qid):
    """A-8：信還在 queue 的 new/ 或 cur/＝還沒答（回 None）；不見了＝history 最新那則回答（沒有回答也 None）。"""
    if qid in a.waiting():
        return None
    got = a.answers()
    return got[-1] if got else None


def cmd_answer(root, o, pos):
    need(pos, 1, "answer NAME [信號]")
    a = root.agent(pos[0])
    if len(pos) == 1:
        out({"ok": True, "name": a.name, "answers": [{"asked": q, "text": clip(t)} for q, t in aos_ws.exchanges(str(a.stack))],
             "waiting": a.waiting()})
        return
    text = find_answer(a, pos[1])
    if text is None:
        where = "還在排隊（queue 的 new/）" if pos[1] in a.ls("new") else \
                "做到一半（queue 的 cur/）" if pos[1] in a.ls("cur") else "history 裡沒有回答"
        raise Fail("AnswerMissing", "%s 還沒有答案：%s" % (pos[1], where), "aos-ai run %s，或背景的話 aos-ai wait" % a.name)
    out({"ok": True, "name": a.name, "id": pos[1], "text": clip(text), "path": str(a.stack / "history.jsonl")})


def cmd_wait(root, o, pos):
    need(pos, 2, "wait NAME 信號 [--timeout 秒]")
    a = root.agent(pos[0])
    end = time.monotonic() + float(o.get("timeout", ["120"])[-1])
    t0 = time.monotonic()
    while True:
        text = find_answer(a, pos[1])
        if text is not None:
            out({"ok": True, "name": a.name, "id": pos[1], "text": clip(text), "path": str(a.stack / "history.jsonl"),
                 "waited_ms": int((time.monotonic() - t0) * 1000)})
            return
        row = Daemon(root).row(a.name)
        if row is None or row.get("phase") not in ("running", "stopping"):
            raise Fail("WaitFailed", "%s 沒在背景跑（%s），不會有人做這題" % (a.name, (row or {}).get("phase", "不在表上")),
                       "aos-ai start %s 或 aos-ai run %s；失敗原因看 ws/.stack/stderr.txt 與 aos-ai status" % (a.name, a.name))
        if time.monotonic() > end:
            raise Fail("WaitFailed", "等了 %s 秒還沒有答案" % o.get("timeout", ["120"])[-1], "aos-ai status %s 看卡在哪" % a.name)
        time.sleep(0.3)


def cmd_trace(root, o, pos):
    need(pos, 1, "trace NAME [-n 行數]")
    a = root.agent(pos[0])
    out({"ok": True, "name": a.name, "fsm_state": read_text(a.stack / "state.txt"),
         "trace": tail_jsonl(a.stack / "trace.jsonl", int(o.get("n", ["10"])[-1]))})


def cmd_history(root, o, pos):
    need(pos, 1, "history NAME [-n 則數]")
    a = root.agent(pos[0])
    rows = tail_jsonl(a.stack / "history.jsonl", int(o.get("n", ["6"])[-1]))
    for m in rows:
        if isinstance(m.get("content"), str) and len(m["content"]) > 500:
            m["content"] = m["content"][:500] + "…"
    out({"ok": True, "name": a.name, "history": rows})


def cmd_exec(root, o, pos):
    need(pos, 1, "exec [--ws WS] [--timeout 秒] 目標 [參數...]")
    ws = root.inside(o.get("ws", [str(root.dir)])[-1], "--ws")
    stdin = None if sys.stdin.isatty() else sys.stdin.read()
    rc, so, se, timed_out, ms = run_group(["aos-exec", "--ws", str(ws), "--"] + pos, child_env(env_pairs(o)),
                                          os.getcwd(), float(o.get("timeout", ["300"])[-1]), stdin)
    errors = parse_errors(se)
    res = {"ok": rc == 0 and not timed_out, **code_fields(rc), "timed_out": timed_out, "elapsed_ms": ms,
           "stdout": clip(so), "errors": errors}
    if not res["ok"] and errors:
        res["hint"] = hint_for(errors)
    out(res)
