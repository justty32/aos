"""agent_tool - 「把一隻 agent 包成工具」的轉接與 claude、codex 的工具形入口，共用一支。

P-41「agent 當腦的工具，轉接寫在那個工具自己的 _entry」；10-24 遷移（tool-lib 遷移清單、agent-as-tool 選項 4）把 pyfix 裡那段通用的抽出來：
每次呼叫開一個新的小格 $AOS_STACK/runs/<三位數>/（子 agent 的工作區 ws/ 與 stack/）→ 題目寫進 ws/new/<題名> → aos-exec 跑子 agent 到答完
→ 從 ws/out/<題名> 拿答案。不帶上次的記憶（每次新 stack）。子 agent 的 stdout 不混進工具的結果（轉到 stderr）；它的 stderr 原樣透出，失敗時這裡只多寫自己一行（stdio-unify R10）。
這支不是工具（沒有 _entry），是模組；工具用 realpath 找到 lib/agent 這層再 import（同 cli_session.py）。純標準庫。
錯：照 lib/tool_io.py（工具先 tool_io.start 過）——AgentFailed（起不來、退非 0）、AnswerMissing（跑完沒答案）。
找 tool_io：用它的工具已把 lib/ 放進 sys.path（lib/docs/01 規則 9）。"""
import os, subprocess, sys

import tool_io


die = tool_io.die


def fresh_cell(stack):
    """$AOS_STACK/runs/001、002…（mkdir 搶號，兩個同時叫也不會撞）；回這次的小格路徑。"""
    runs = os.path.join(stack, "runs")
    os.makedirs(runs, exist_ok=True)
    n = len(os.listdir(runs)) + 1
    while True:
        cell = os.path.join(runs, "%03d" % n)
        try:
            os.mkdir(cell)
            return cell
        except FileExistsError:
            n += 1


def run_agent(agent, task, cell, env_extra=None, question="task.txt"):
    """在小格 cell 裡跑子 agent（資料夾 agent）做 task，回它的答案（ws/out/<question> 的內容）。
    --dotenv-override：子 agent 自己 .env 的值（例：模型名）蓋過外層傳下來的。env_extra 加給子 agent 的環境變數。
    要先放檔給子 agent 讀（例 pyfix 的 pyfix_dir.txt）就先建好 <cell>/stack/ 寫進去（已在就沿用）。"""
    sub_ws, sub_stack = os.path.join(cell, "ws"), os.path.join(cell, "stack")
    os.makedirs(os.path.join(sub_ws, "new"))
    os.makedirs(sub_stack, exist_ok=True)
    with open(os.path.join(sub_ws, "new", question), "w", encoding="utf-8") as f:
        f.write(task)
    env = dict(os.environ, AOS_STACK=sub_stack + "/", **(env_extra or {}))
    try:
        r = subprocess.run(["aos-exec", "--dotenv-override", "--ws", sub_ws, agent], env=env, stdout=sys.stderr)
    except OSError as e:
        die("AgentFailed", "sub-agent failed to start: %s" % e)
    if r.returncode != 0:
        die("AgentFailed", "sub-agent exited %d (its state is in %s)" % (r.returncode, cell))
    try:
        with open(os.path.join(sub_ws, "out", question), encoding="utf-8") as f:
            return f.read()
    except OSError:
        die("AnswerMissing", "sub-agent finished without an answer (its state is in %s)" % cell)


def ask_cli(tool_dir, name, help_text):
    """claude、codex 工具形：tool_io 收參數與工作區，cli_session 問一輪並續存對話。"""
    import cli_session

    tool_io.start(name, help_text)
    cli_session.PROG, cli_session.ECHO = name, True
    cfg = cli_session.load_cfg(tool_dir)
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "AOS_STACK is not set")
    ws = tool_io.workspace()
    args = tool_io.arguments()
    if not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        die("ArgumentsBad", "missing prompt (a non-empty string)")
    cell = cli_session.Cell(stack)
    text = cli_session.ask(cfg, cell, os.path.abspath(tool_dir), ws, cell.path, args["prompt"], "yield")
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
