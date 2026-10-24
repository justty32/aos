"""agent_tool - 「把一隻 agent 包成工具」的轉接，共用一支（lib/agent 的工具 import 它）。

P-41「agent 當腦的工具，轉接寫在那個工具自己的 _entry」；10-24 遷移（tool-lib 遷移清單、agent-as-tool 選項 4）把 pyfix 裡那段通用的抽出來：
每次呼叫開一個新的小格 $AOS_STACK/runs/<三位數>/（子 agent 的工作區 ws/ 與 stack/）→ 題目寫進 ws/new/<題名> → aos-exec 跑子 agent 到答完
→ 從 ws/out/<題名> 拿答案。不帶上次的記憶（每次新 stack）。子 agent 的 stdout 不混進工具的結果（轉到 stderr）。
這支不是工具（沒有 _entry），是模組；工具用 realpath 找到 lib/agent 這層再 import（同 cli_session.py）。純標準庫。
錯：stderr 與 stdout 各一行「<工具名>: 代號 原因」、退 1（lib/README 規則 3）——AgentFailed（起不來、退非 0）、AnswerMissing（跑完沒答案）。"""
import os, subprocess, sys


def die(name, code, reason):
    line = "%s: %s %s" % (name, code, str(reason).replace("\n", " "))
    print(line, file=sys.stderr)
    print(line)                                 # stdout 也印：stdout 是給腦看的結果
    sys.exit(1)


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


def run_agent(name, agent, task, cell, env_extra=None, question="task.txt"):
    """在小格 cell 裡跑子 agent（資料夾 agent）做 task，回它的答案（ws/out/<question> 的內容）。
    --dotenv-override：子 agent 自己 .env 的值（例：模型名）蓋過外層傳下來的。env_extra 加給子 agent 的環境變數。"""
    sub_ws, sub_stack = os.path.join(cell, "ws"), os.path.join(cell, "stack")
    os.makedirs(os.path.join(sub_ws, "new"))
    os.makedirs(sub_stack)
    with open(os.path.join(sub_ws, "new", question), "w", encoding="utf-8") as f:
        f.write(task)
    env = dict(os.environ, AOS_STACK=sub_stack + "/", **(env_extra or {}))
    try:
        r = subprocess.run(["aos-exec", "--dotenv-override", "--ws", sub_ws, agent], env=env, stdout=sys.stderr)
    except OSError as e:
        die(name, "AgentFailed", "子 agent 起不來：%s" % e)
    if r.returncode != 0:
        die(name, "AgentFailed", "子 agent 結束碼 %d（現場在 %s）" % (r.returncode, cell))
    try:
        with open(os.path.join(sub_ws, "out", question), encoding="utf-8") as f:
            return f.read()
    except OSError:
        die(name, "AnswerMissing", "子 agent 跑完了但沒有答案（現場在 %s）" % cell)
