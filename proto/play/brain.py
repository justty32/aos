#!/usr/bin/env python3
"""互動台 agent 的腦：沿用 agent-real，另外在每圈開頭收使用者的信。"""

import datetime
import json
import os
import shlex
import subprocess
import sys


LAND = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(LAND, "state")
ROUNDS = os.path.join(STATE, "rounds")
MAIL = os.path.join(LAND, ".aos", "mail")
MAIL_READ = os.path.join(MAIL, "read")

TOOL_MARK = "TOOL:"
DONE_MARK = "DONE:"
OBS_LIMIT = 2000
ANSWER = os.path.join(STATE, "answer.txt")


def read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return default


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(temp, path)


def cfg():
    value = json.loads(read(os.path.join(LAND, "agent.json"), "{}") or "{}")
    value.setdefault("max_rounds", 10)
    value.setdefault("max_llm_calls", 10)
    value.setdefault("tools", ["python3", "cat", "ls"])
    value.setdefault("tier", "smart")
    value.setdefault("tool_timeout_ms", 30000)
    value.setdefault("work", "work")
    value.setdefault("echo_rounds", 0)
    return value


def round_no():
    try:
        return int(read(os.path.join(STATE, "round.txt"), "1").strip() or "1")
    except ValueError:
        return 1


def transcript():
    return read(os.path.join(STATE, "transcript.md"), "")


def append_transcript(text):
    write(os.path.join(STATE, "transcript.md"), transcript() + text.rstrip("\n") + "\n")


def finish(why, message, number):
    write(os.path.join(STATE, "next.txt"), "end\n")
    write(os.path.join(STATE, "done.json"), json.dumps({
        "why": why,
        "message": message,
        "rounds": number,
    }, ensure_ascii=False, indent=2) + "\n")
    print("收工（%s）：%s" % (why, message))
    return 0


def report_round(number, tool, ok, reason):
    summary = {"round": number, "tool": tool or "", "ok": bool(ok), "reason": reason}
    write(os.path.join(ROUNDS, "%03d" % number, "round.json"),
          json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    progress_path = os.path.join(LAND, ".aos", "agent-progress.json")
    try:
        previous = json.loads(read(progress_path, "{}") or "{}")
    except ValueError:
        previous = {}
    old_streak = previous.get("fail_streak", 0)
    old_streak = old_streak if isinstance(old_streak, int) and old_streak >= 0 else 0
    streak = 0 if ok else old_streak + 1
    write(progress_path, json.dumps({
        "format_version": 1,
        "latest": summary,
        "fail_streak": streak,
    }, ensure_ascii=False, indent=2) + "\n")
    return streak


def take_mail():
    """把這圈會讀的信先原子搬到 read/；搬不成的信留給下一圈。"""
    os.makedirs(MAIL_READ, exist_ok=True)
    try:
        names = sorted(name for name in os.listdir(MAIL) if name.endswith(".json"))
    except OSError:
        names = []
    messages = []
    for name in names:
        source = os.path.join(MAIL, name)
        target = os.path.join(MAIL_READ, name)
        try:
            os.replace(source, target)
        except OSError:
            continue
        try:
            value = json.loads(read(target, "{}") or "{}")
        except ValueError:
            value = {"body": "（這封信不是合法 JSON，原件在 %s）" % target}
        messages.append(value)
    return messages


def mail_text(messages):
    if not messages:
        return "（這圈沒有新信）"
    lines = []
    for index, message in enumerate(messages, 1):
        body = message.get("body", "") if isinstance(message, dict) else message
        if not isinstance(body, str):
            body = json.dumps(body, ensure_ascii=False)
        subject = message.get("subject") if isinstance(message, dict) else None
        sender = message.get("from") if isinstance(message, dict) else None
        lines.append("%d. %s%s：%s" % (
            index,
            ("[%s] " % subject) if subject else "",
            sender or "使用者",
            body,
        ))
    return "\n".join(lines)


def build_prompt(config, number, messages):
    work = os.path.join(LAND, config["work"])
    lines = [
        "你是一個 agent。你住在這塊地：%s" % LAND,
        "你能動的東西只有 %s 底下的檔案。" % work,
        "今天是 %s。" % datetime.date.today().isoformat(),
        "",
        "== 任務 ==",
        read(os.path.join(LAND, "task.md"), "（沒有 task.md）").strip(),
        "",
        "== 使用者在等待期間寄來的信 ==",
        mail_text(messages),
        "",
        "== 你能用的程式（白名單，其他一律拒絕）==",
        "、".join(config["tools"]),
        "",
        "== 怎麼回話 ==",
        "一次只做一件事，回話要短。",
        "要跑指令，就在回話裡放一行長這樣（一次只准一行）：",
        "    TOOL: ls work",
    ]
    if "write" in config["tools"]:
        lines.extend([
            "要新增或覆蓋一個檔案：先在回話裡放一個用三個反引號圍起來的區塊，",
            "裡面是那個檔案的完整內容，然後放一行：",
            "    TOOL: write work/某個檔.py",
        ])
    lines.extend([
        "做完了、不必再跑指令，就放一行長這樣：",
        "    DONE: 我做完了，也確認過結果",
        "兩種行都沒有＝你覺得做完了，我就收工。",
        "",
        "== 到目前為止（現在是第 %d 圈，最多 %d 圈）==" %
        (number, min(config["max_rounds"], config["max_llm_calls"])),
        transcript().strip() or "（還沒做過任何事）",
    ])
    return "\n".join(lines) + "\n"


def op_prep():
    config = cfg()
    number = round_no()
    os.makedirs(STATE, exist_ok=True)
    for path in (ANSWER, ANSWER + ".status.json", ANSWER + ".usage.json"):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    prompt = build_prompt(config, number, take_mail())
    write(os.path.join(STATE, "prompt.txt"), prompt)
    write(os.path.join(ROUNDS, "%03d" % number, "prompt.txt"), prompt)
    write(os.path.join(STATE, "req.json"), json.dumps({
        "kind": "llm",
        "prompt": "state/prompt.txt",
        "result": "state/answer.txt",
        "tier": config["tier"],
    }, ensure_ascii=False, indent=2) + "\n")
    print("第 %d 圈：prompt %d 字，投給 LLM 世界" % (number, len(prompt)))
    return 0


def looks_echoed(answer, prompt):
    value = (prompt or "").strip()
    return bool(value) and value in answer


def pick_line(answer, mark, echoed=()):
    for raw in answer.splitlines():
        line = raw.strip()
        if line.startswith(mark) and line not in echoed:
            return line[len(mark):].strip()
    return None


def last_code_block(text):
    parts = text.split("```")
    if len(parts) < 3:
        return None
    body = parts[-2]
    if "\n" in body:
        head, rest = body.split("\n", 1)
        if head.strip() and " " not in head.strip():
            body = rest
    return body.strip("\n") + "\n"


def do_write(argv, answer):
    if len(argv) != 2:
        return False, "用法是：write <路徑>（路徑要在這塊地裡面）"
    target = os.path.abspath(os.path.join(LAND, argv[1]))
    work = os.path.abspath(os.path.join(LAND, cfg()["work"]))
    if target != work and not target.startswith(work + os.sep):
        return False, "只能寫 work/ 裡面的檔案：%s" % work
    body = last_code_block(answer)
    if body is None:
        return False, "回話裡沒有三個反引號圍起來的完整內容"
    write(target, body)
    return True, "寫好了 %s（%d 個字）" % (argv[1], len(body))


def run_tool(config, command, answer=""):
    try:
        argv = shlex.split(command)
    except ValueError as error:
        return False, "這條指令拆不開（%s）：%s" % (error, command)
    if not argv:
        return False, "TOOL: 後面是空的"
    if argv[0] not in config["tools"]:
        return False, "`%s` 不在白名單裡。能用的只有：%s" % (
            argv[0], "、".join(config["tools"]))
    if argv[0] == "write":
        return do_write(argv, answer)
    try:
        process = subprocess.run(argv, cwd=LAND, capture_output=True, text=True,
                                 timeout=config["tool_timeout_ms"] / 1000.0)
    except FileNotFoundError:
        return False, "找不到程式 `%s`" % argv[0]
    except subprocess.TimeoutExpired:
        return False, "跑超過 %d 毫秒被停掉：%s" % (config["tool_timeout_ms"], command)
    output = (process.stdout or "")
    if process.stderr:
        output += "\n[錯誤輸出]\n" + process.stderr
    output = output.strip()
    if len(output) > OBS_LIMIT:
        output = output[:OBS_LIMIT] + "\n…（後面截掉了）"
    return process.returncode == 0, "結束碼 %d\n%s" % (
        process.returncode, output or "（沒有輸出）")


def op_act():
    config = cfg()
    number = round_no()
    answer = read(ANSWER, "")
    write(os.path.join(ROUNDS, "%03d" % number, "answer.txt"), answer)
    if not answer.strip():
        append_transcript("第 %d 圈：LLM 回了空的。" % number)
        report_round(number, "", False, "empty_answer")
        return finish("empty_answer", "第 %d 圈 LLM 回話是空的" % number, number)

    prompt = read(os.path.join(STATE, "prompt.txt"), "")
    echoed = set(line.strip() for line in prompt.splitlines()) if looks_echoed(answer, prompt) else set()
    command = pick_line(answer, TOOL_MARK, echoed)
    done = pick_line(answer, DONE_MARK, echoed)
    # echo: 不會自己叫工具；離線自測第一圈補一個無害動作，才能真的驗到下一圈收信。
    if echoed and number < config["echo_rounds"]:
        command = "ls work"
    if command is None:
        why = "said_done" if done is not None else "no_tool_call"
        first = next((line.strip() for line in answer.splitlines() if line.strip()), "")
        message = done if done is not None else first[:200]
        if echoed:
            message = "假後端回音結束，離線流程正常"
        append_transcript("第 %d 圈：LLM 沒有再叫工具。它說：%s" % (number, message))
        report_round(number, "", True, why)
        return finish(why, message or "LLM 這圈沒有叫工具", number)

    ok, observation = run_tool(config, command, answer)
    write(os.path.join(ROUNDS, "%03d" % number, "tool.txt"),
          "指令：%s\n成功：%s\n%s\n" % (command, ok, observation))
    append_transcript("第 %d 圈：我跑了 `%s`\n觀察（%s）：\n%s\n" % (
        number, command, "成功" if ok else "失敗",
        "\n".join("  " + line for line in observation.splitlines())))
    print("第 %d 圈：跑了 `%s`（%s）" % (number, command, "成功" if ok else "失敗"))

    fail_streak = report_round(number, command, ok, "ok" if ok else "tool_failed")
    if fail_streak >= 3:
        return finish("fail_streak", "工具連續失敗 %d 圈，停下來等人檢查" % fail_streak, number)
    cap = min(config["max_rounds"], config["max_llm_calls"])
    if number >= cap:
        why = "round_cap" if cap == config["max_rounds"] else "call_cap"
        return finish(why, "跑滿 %d 圈還沒收工" % cap, number)
    write(os.path.join(STATE, "round.txt"), "%d\n" % (number + 1))
    write(os.path.join(STATE, "next.txt"), "prep\n")
    return 0


OPS = {"prep": op_prep, "act": op_act}


if __name__ == "__main__":
    operation = sys.argv[1] if len(sys.argv) > 1 else ""
    function = OPS.get(operation)
    if function is None:
        sys.stderr.write("用法：python3 brain.py prep|act\n")
        sys.exit(2)
    sys.exit(function())
