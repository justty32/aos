#!/usr/bin/env python3
"""agent 的腦：一圈＝prep（寫 prompt）→ ask（投給 LLM 世界）→ wait → act（跑工具）。

這支只用標準庫，而且**只碰自己這塊地**（裁決 2026-09-04：一塊地只看得到自己
地上的東西）。它不 import aosp，機器的內部長怎樣不關 agent 的事。

兩個 op：
  prep  讀 task.md + 到目前為止的紀錄，寫 state/prompt.txt 與 state/req.json，
        並且把上一圈的 state/answer.txt（跟它的狀態檔）清掉。
  act   讀 state/answer.txt：找到「TOOL:」那行就照白名單跑一條指令，把觀察寫進紀錄，
        state/next.txt 寫 `prep`（再一圈）；沒有 TOOL: 那行就寫 `end`（裁決 M-01：
        agent 停於 LLM 不再呼叫工具）。

設定在 agent.json；每圈的 prompt／回話留在 state/rounds/<圈>/，事後好對帳。
"""
import json
import os
import shlex
import subprocess
import sys

LAND = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(LAND, "state")
ROUNDS = os.path.join(STATE, "rounds")

TOOL_MARK = "TOOL:"
DONE_MARK = "DONE:"
OBS_LIMIT = 2000          # 觀察塞回 prompt 的字數上限
ANSWER = os.path.join(STATE, "answer.txt")


# ---------------------------------------------------------------- 小工具
def read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def cfg():
    c = json.loads(read(os.path.join(LAND, "agent.json"), "{}") or "{}")
    c.setdefault("max_rounds", 12)
    c.setdefault("max_llm_calls", 30)   # 花費上限：一圈＝一次 LLM 請求
    c.setdefault("tools", ["python3", "cat", "ls"])
    c.setdefault("tier", "fast")
    c.setdefault("tool_timeout_ms", 30000)
    c.setdefault("work", "work")
    return c


def round_no():
    try:
        return int(read(os.path.join(STATE, "round.txt"), "1").strip() or "1")
    except ValueError:
        return 1


def transcript():
    return read(os.path.join(STATE, "transcript.md"), "")


def append_transcript(text):
    path = os.path.join(STATE, "transcript.md")
    write(path, transcript() + text.rstrip("\n") + "\n")


def finish(why, message, n):
    """收工：state/next.txt 寫 end，並留一份 done.json 講清楚為什麼停。"""
    write(os.path.join(STATE, "next.txt"), "end\n")
    write(os.path.join(STATE, "done.json"), json.dumps(
        {"why": why, "message": message, "rounds": n}, ensure_ascii=False, indent=2) + "\n")
    print("收工（%s）：%s" % (why, message))
    return 0


# ---------------------------------------------------------------- prep
def build_prompt(c, n):
    work = os.path.join(LAND, c["work"])
    lines = []
    lines.append("你是一個 agent。你住在這塊地：%s" % LAND)
    lines.append("你能動的東西只有 %s 底下的檔案。" % work)
    lines.append("")
    lines.append("== 任務 ==")
    lines.append(read(os.path.join(LAND, "task.md"), "（沒有 task.md）").strip())
    lines.append("")
    lines.append("== 你能用的程式（白名單，其他一律拒絕）==")
    lines.append("、".join(c["tools"]))
    lines.append("")
    lines.append("== 怎麼回話 ==")
    lines.append("一次只做一件事，回話要短。")
    lines.append("要跑指令，就在回話裡放一行長這樣（一次只准一行）：")
    lines.append("    TOOL: ls work")
    if "write" in c["tools"]:
        lines.append("要新增或覆蓋一個檔案：先在回話裡放一個用三個反引號圍起來的區塊，")
        lines.append("裡面是那個檔案的**完整**內容，然後放一行：")
        lines.append("    TOOL: write work/某個檔.py")
    lines.append("做完了、不必再跑指令，就放一行長這樣：")
    lines.append("    DONE: 我加了函式，測試過了")
    lines.append("兩種行都沒有＝你覺得做完了，我就收工。")
    lines.append("")
    lines.append("== 到目前為止（現在是第 %d 圈，最多 %d 圈）=="
                 % (n, min(c["max_rounds"], c["max_llm_calls"])))
    t = transcript().strip()
    lines.append(t if t else "（還沒做過任何事）")
    return "\n".join(lines) + "\n"


def op_prep():
    c = cfg()
    n = round_no()
    os.makedirs(STATE, exist_ok=True)
    for p in (ANSWER, ANSWER + ".status.json"):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
    prompt = build_prompt(c, n)
    write(os.path.join(STATE, "prompt.txt"), prompt)
    write(os.path.join(ROUNDS, "%03d" % n, "prompt.txt"), prompt)
    # 不帶 `id`：`aos deliver` 會發一個新的，同一個 id 再投會被 I-05 擋掉
    write(os.path.join(STATE, "req.json"), json.dumps({
        "kind": "llm",
        "prompt": "state/prompt.txt",
        "result": "state/answer.txt",
        "tier": c["tier"],
    }, ensure_ascii=False, indent=2) + "\n")
    print("第 %d 圈：prompt %d 字，投給 LLM 世界" % (n, len(prompt)))
    return 0


# ---------------------------------------------------------------- act
def looks_echoed(answer, prompt):
    """回話是不是「把 prompt 原樣吐回來」（假後端 `echo:` 就是這樣）。

    只有這種時候才需要濾掉 prompt 裡示範用的那行。真模型的回話裡出現
    `TOOL: ls work`，那是它真的要跑那條指令——第一輪真模型就是被這裡誤殺的
    （見 FINDINGS「真模型第一輪」）。
    """
    p = (prompt or "").strip()
    return bool(p) and p in answer


def pick_line(answer, mark, echoed=()):
    """找回話裡第一行以 mark 開頭的。

    `echoed` 只有在回話被判定成「原樣回音」時才有東西（見 looks_echoed）。
    """
    for raw in answer.splitlines():
        line = raw.strip()
        if not line.startswith(mark):
            continue
        if line in echoed:
            continue
        return line[len(mark):].strip()
    return None


def last_code_block(text):
    """回話裡最後一個三反引號區塊的內容（沒有就 None）。"""
    fence = "```"
    parts = text.split(fence)
    if len(parts) < 3:
        return None
    body = parts[-2]
    if "\n" in body:
        head, rest = body.split("\n", 1)
        if head.strip() and " " not in head.strip():   # ```python 這種語言標記
            body = rest
    return body.strip("\n") + "\n"


def do_write(c, argv, answer):
    """內建工具 `write <路徑>`：把回話裡最後一個程式碼區塊寫進那個檔。

    模型沒有 shell、沒有 heredoc，光靠 `python3 -c` 寫多行檔案幾乎一定被引號咬到，
    所以給它一條寫檔的路。落點限制在這塊地裡面，而且不准指進 `.aos/`。
    """
    if len(argv) != 2:
        return False, "用法是：write <路徑>（路徑要在這塊地裡面）"
    target = os.path.abspath(os.path.join(LAND, argv[1]))
    if not (target == LAND or target.startswith(LAND + os.sep)):
        return False, "只能寫這塊地裡面的檔案：%s" % LAND
    if ".aos" in target.split(os.sep):
        return False, "`.aos/` 是機器的目錄，不准往裡面寫"
    body = last_code_block(answer)
    if body is None:
        return False, "回話裡沒有三反引號圍起來的區塊，不知道要寫什麼進去"
    write(target, body)
    return True, "寫好了 %s（%d 個字）" % (argv[1], len(body))


def run_tool(c, cmd, answer=""):
    """照白名單跑一條指令。回 (成功?, 觀察文字)。"""
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return False, "這條指令拆不開（%s）：%s" % (e, cmd)
    if not argv:
        return False, "TOOL: 後面是空的"
    if argv[0] not in c["tools"]:
        return False, ("`%s` 不在白名單裡。能用的只有：%s"
                       % (argv[0], "、".join(c["tools"])))
    if argv[0] == "write":
        return do_write(c, argv, answer)
    try:
        p = subprocess.run(argv, cwd=LAND, capture_output=True, text=True,
                           timeout=c["tool_timeout_ms"] / 1000.0)
    except FileNotFoundError:
        return False, "找不到程式 `%s`" % argv[0]
    except subprocess.TimeoutExpired:
        return False, "跑超過 %d 毫秒被砍掉：%s" % (c["tool_timeout_ms"], cmd)
    out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
    out = out.strip()
    if len(out) > OBS_LIMIT:
        out = out[:OBS_LIMIT] + "\n…（後面截掉了）"
    return p.returncode == 0, "結束碼 %d\n%s" % (p.returncode, out or "（沒有輸出）")


def op_act():
    c = cfg()
    n = round_no()
    answer = read(ANSWER, "")
    write(os.path.join(ROUNDS, "%03d" % n, "answer.txt"), answer)
    if not answer.strip():
        append_transcript("第 %d 圈：LLM 回了空的。" % n)
        return finish("empty_answer", "第 %d 圈 LLM 回話是空的" % n, n)

    prompt = read(os.path.join(STATE, "prompt.txt"), "")
    echoed = set()
    if looks_echoed(answer, prompt):
        echoed = set(x.strip() for x in prompt.splitlines())
    cmd = pick_line(answer, TOOL_MARK, echoed)
    done = pick_line(answer, DONE_MARK, echoed)

    if cmd is None:
        why = "said_done" if done is not None else "no_tool_call"
        first = next((x.strip() for x in answer.splitlines() if x.strip()), "")
        msg = done if done is not None else first[:200]
        append_transcript("第 %d 圈：LLM 沒有再叫工具。它說：%s" % (n, msg))
        return finish(why, msg or "LLM 這圈沒有叫工具", n)

    ok, obs = run_tool(c, cmd, answer)
    write(os.path.join(ROUNDS, "%03d" % n, "tool.txt"),
          "指令：%s\n成功：%s\n%s\n" % (cmd, ok, obs))
    append_transcript(
        "第 %d 圈：我跑了 `%s`\n觀察（%s）：\n%s\n"
        % (n, cmd, "成功" if ok else "失敗",
           "\n".join("  " + x for x in obs.splitlines())))
    print("第 %d 圈：跑了 `%s`（%s）" % (n, cmd, "成功" if ok else "失敗"))

    cap = min(c["max_rounds"], c["max_llm_calls"])
    if n >= cap:
        why = "round_cap" if cap == c["max_rounds"] else "call_cap"
        return finish(why, "跑滿 %d 圈（max_rounds=%s、max_llm_calls=%s）還沒收工"
                      % (cap, c["max_rounds"], c["max_llm_calls"]), n)
    write(os.path.join(STATE, "round.txt"), "%d\n" % (n + 1))
    write(os.path.join(STATE, "next.txt"), "prep\n")
    return 0


OPS = {"prep": op_prep, "act": op_act}

if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = OPS.get(op)
    if fn is None:
        sys.stderr.write("用法：python3 brain.py prep|act\n")
        sys.exit(2)
    sys.exit(fn())
