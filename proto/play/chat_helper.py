#!/usr/bin/env python3
"""play-chat.sh 的小幫手：只做檔案準備、摘要與 JSON 編碼。"""

import json
import os
import shutil
import sys


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp, path)


def ledger(home):
    rows = []
    path = os.path.join(home, ".aos", "ledger.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def prices():
    return (float(os.environ["AOS_PLAY_INPUT_USD_PER_MILLION"]),
            float(os.environ["AOS_PLAY_OUTPUT_USD_PER_MILLION"]))


def usage(rows):
    tin = sum((row.get("tokens_in") or 0) for row in rows)
    tout = sum((row.get("tokens_out") or 0) for row in rows)
    reasoning = sum((row.get("tokens_reasoning") or 0) for row in rows)
    pin, pout = prices()
    cost = tin * pin / 1_000_000 + (tout + reasoning) * pout / 1_000_000
    return tin, tout, reasoning, cost


def command_setup(argv):
    source, brain, agent, task, max_rounds, echo_rounds = argv
    os.makedirs(agent, exist_ok=False)
    for name in ("main.aos.json", "agent.json"):
        shutil.copy2(os.path.join(source, name), os.path.join(agent, name))
    shutil.copy2(brain, os.path.join(agent, "brain.py"))
    shutil.copytree(os.path.join(source, "work"), os.path.join(agent, "work"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with open(os.path.join(agent, "task.md"), "w", encoding="utf-8") as f:
        f.write(task.rstrip("\n") + "\n")
    config = read_json(os.path.join(agent, "agent.json"), {}) or {}
    config["tier"] = "smart"
    config["max_rounds"] = int(max_rounds)
    config["max_llm_calls"] = int(max_rounds)
    config["echo_rounds"] = int(echo_rounds)
    write_json(os.path.join(agent, "agent.json"), config)


def command_home_config(argv):
    home, llm_world, endpoint, model = argv
    write_json(os.path.join(home, ".aos", "config.json"), {
        "format_version": 1,
        "llm_world": os.path.abspath(llm_world),
        "max_parallel": 2,
        "units": [{
            "name": "deepseek",
            "endpoint": endpoint,
            "model": model,
            "tier": "smart",
            "max_parallel": 1,
            "api_key_env": "DEEPSEEK_API_KEY",
            "timeout_ms": 600000,
        }],
    })


def command_land_config(argv):
    agent, bin_dir = argv
    write_json(os.path.join(agent, ".aos", "config.json"), {
        "format_version": 1,
        "path": [os.path.abspath(bin_dir), "/usr/bin", "/bin"],
        "max_parallel": 4,
        "inst_timeout_ms": 120000,
        "inbox_max": 1000,
    })


def command_mail_json(argv):
    print(json.dumps({
        "kind": "mail",
        "subject": "使用者插話",
        "body": argv[0],
    }, ensure_ascii=False))


def answer_summary(answer, prompt):
    if prompt.strip() and prompt.strip() in answer:
        return "假後端把這圈的 prompt 原樣回來"
    fallback = ""
    for raw in answer.splitlines():
        line = " ".join(raw.strip().split())
        if not line or line.startswith("```") or line.startswith("echo:"):
            continue
        if line.startswith("DONE:"):
            return line[5:].strip()[:160] or "它說做完了"
        if line.startswith("TOOL:"):
            fallback = line
            continue
        return line[:160]
    return fallback[:160] or "（沒有可顯示的回話）"


def agent_rows(home, agent):
    target = os.path.abspath(agent)
    return [row for row in ledger(home) if os.path.abspath(row.get("from") or "") == target]


def command_report(argv):
    agent, home, after_raw = argv
    after = int(after_raw)
    rounds_dir = os.path.join(agent, "state", "rounds")
    rows = agent_rows(home, agent)
    all_rows = ledger(home)
    seen = after
    try:
        names = sorted(name for name in os.listdir(rounds_dir) if name.isdigit())
    except OSError:
        names = []
    for name in names:
        number = int(name)
        if number <= after:
            continue
        folder = os.path.join(rounds_dir, name)
        info = read_json(os.path.join(folder, "round.json"))
        if not isinstance(info, dict):
            continue
        try:
            with open(os.path.join(folder, "answer.txt"), encoding="utf-8") as f:
                answer = f.read()
        except OSError:
            answer = ""
        try:
            with open(os.path.join(folder, "prompt.txt"), encoding="utf-8") as f:
                prompt = f.read()
        except OSError:
            prompt = ""
        row = rows[number - 1] if number <= len(rows) else {}
        tin = row.get("tokens_in") or 0
        tout = row.get("tokens_out") or 0
        reasoning = row.get("tokens_reasoning")
        source = "後端回報" if row.get("tokens_source") == "reported" else "粗估"
        tool = info.get("tool") or ""
        print("\n── 第 %d 圈 ──" % number)
        print("它說：%s" % answer_summary(answer, prompt))
        if tool:
            print("工具：%s（%s）" % (tool, "成功" if info.get("ok") else "失敗"))
        else:
            print("工具：這圈沒有叫工具")
        if reasoning is None:
            print("tokens：進 %d、出 %d（%s；思考量沒有另報）" % (tin, tout, source))
        else:
            print("tokens：進 %d、出 %d、思考 %d（%s）" %
                  (tin, tout, reasoning, source))
        _tin, _tout, _reasoning, cost = usage(all_rows[:all_rows.index(row) + 1]) \
            if row in all_rows else usage(all_rows)
        print("累計估算：US$%.6f" % cost)
        seen = max(seen, number)
    print("__AOS_LAST_ROUND__=%d" % seen)


def done_text(agent):
    done = read_json(os.path.join(agent, "state", "done.json"))
    if isinstance(done, dict):
        reasons = {
            "said_done": "它自己說事情做完了",
            "no_tool_call": "模型沒有再叫工具",
            "fail_streak": "工具連續失敗三次",
            "round_cap": "跑到圈數上限",
            "call_cap": "跑到 LLM 次數上限",
            "empty_answer": "模型回了空話",
        }
        why = done.get("why") or "原因不明"
        message = done.get("message") or "沒有多留說明"
        return "它收工了：%s。%s" % (reasons.get(why, why), message)
    stopped = read_json(os.path.join(agent, ".aos", "stopped.json"))
    if isinstance(stopped, dict):
        reasons = {
            "control_stop": "使用者請它在格尾停下來",
            "idle": "這塊地已經閒著",
            "failed": "其中一條串壞了",
            "budget": "格數預算用完了",
            "signal": "收到中斷訊號",
            "parse_error": "原稿讀不懂",
            "stalled": "沒有往前走，也沒有在等東西",
        }
        why = stopped.get("reason") or "原因不明"
        return "它停下來了：%s。%s" % (
            reasons.get(why, why), stopped.get("message") or "沒有多留說明")
    return None


def registry_entry(home, agent):
    reg = read_json(os.path.join(home, ".aos", "registry.json"), {}) or {}
    target = os.path.abspath(agent)
    for entry in reg.get("entries") or []:
        if os.path.abspath(entry.get("path") or "") == target:
            return entry
    return None


def command_finished(argv):
    agent, home = argv
    text = done_text(agent)
    entry = registry_entry(home, agent)
    if text and (not entry or entry.get("state") == "stopped"):
        print(text)
        return
    raise SystemExit(1)


def command_registry(argv):
    home, agent = argv
    entry = registry_entry(home, agent)
    if not entry:
        print("  登記表：找不到這塊地那一筆")
        return
    clock = json.dumps(entry.get("clock"), ensure_ascii=False, separators=(",", ":"))
    pid = entry.get("pid") if entry.get("pid") is not None else "-"
    print("  登記表這筆：狀態 %s，pid %s，鐘 %s，預算 %s" %
          (entry.get("state"), pid, clock, entry.get("budget")))


def command_state(argv):
    home, agent = argv
    entry = registry_entry(home, agent)
    print(entry.get("state") if entry else "missing")


def last_round_folder(agent):
    root = os.path.join(agent, "state", "rounds")
    try:
        names = sorted(name for name in os.listdir(root) if name.isdigit())
    except OSError:
        names = []
    return os.path.join(root, names[-1]) if names else None


def command_log(argv):
    agent = argv[0]
    folder = last_round_folder(agent)
    if not folder:
        print("還沒有跑完任何一圈。")
        return
    print("===== 最後一圈的 prompt =====")
    try:
        with open(os.path.join(folder, "prompt.txt"), encoding="utf-8") as f:
            print(f.read().rstrip())
    except OSError:
        print("（讀不到 prompt）")
    print("===== 最後一圈的回話 =====")
    try:
        with open(os.path.join(folder, "answer.txt"), encoding="utf-8") as f:
            print(f.read().rstrip())
    except OSError:
        print("（還沒有回話）")


def command_final(argv):
    home = argv[0]
    rows = ledger(home)
    rounds = 0
    tools = 0
    lands_root = os.path.join(home, "lands")
    try:
        lands = [os.path.join(lands_root, name) for name in os.listdir(lands_root)]
    except OSError:
        lands = []
    for agent in lands:
        root = os.path.join(agent, "state", "rounds")
        try:
            names = [name for name in os.listdir(root) if name.isdigit()]
        except OSError:
            names = []
        for name in names:
            info = read_json(os.path.join(root, name, "round.json"))
            if isinstance(info, dict):
                rounds += 1
                tools += bool(info.get("tool"))
    tin, tout, reasoning, cost = usage(rows)
    failed = sum(row.get("outcome") != "ok" for row in rows)
    print("圈數：%d；工具：%d 次；LLM 請求：%d 次（失敗 %d 次）" %
          (rounds, tools, len(rows), failed))
    print("tokens：進 %d、出 %d、思考 %d；估算花費：US$%.6f" %
          (tin, tout, reasoning, cost))


COMMANDS = {
    "setup": command_setup,
    "home-config": command_home_config,
    "land-config": command_land_config,
    "mail-json": command_mail_json,
    "report": command_report,
    "finished": command_finished,
    "registry": command_registry,
    "state": command_state,
    "log": command_log,
    "final": command_final,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write("這支是 play-chat.sh 的內部副手，請從 play-chat.sh 起動。\n")
        return 2
    COMMANDS[sys.argv[1]](sys.argv[2:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
