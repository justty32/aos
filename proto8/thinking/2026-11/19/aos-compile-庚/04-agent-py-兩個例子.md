# `agent.py` 的兩個例子：一個最小的、一個對應現有範本 reviewer 的完整版

← [README](README.md)｜上一份：[03-agent-py-長相](03-agent-py-長相.md)｜下一份：[05-打架規則-總則](05-打架規則-總則.md)

兩個例子都是設計稿，還沒有程式；函式名以施工計劃定的為準。

## 最小例子

空資料夾裡只放這一支，跑一次就是一隻掛得上去的 agent。

```python
#!/usr/bin/env python3
"""helper - an agent that looks things up in the workspace (agent.py: the source of this definition)."""
# ---- setup: find the aos package (keep these lines as they are) ----
#      （跟 tool.py 同樣那 20 行，最後 import 換成：from aos import agent_spec as ag）
# ---- your agent: change the lines below ----

DESCRIPTION = "Look things up in the workspace and answer by mail."

SYSTEM = """You are an assistant that looks things up in the workspace.
Answer each letter with mailbox_send to its reply_to.
"""

TOOLS = [ag.pack("look"), ag.pack("mailbox"), ag.pack("json")]

LLM = {"model": "luna"}

FSM = ag.stock_fsm()        # the four cells of the agent-fsm template: idle, think, wait, act

ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
```

`python3 agent.py --write-defs` 之後夾裡長這樣：

| 檔 | 內容 | 重生時 |
|---|---|---|
| `agent.py` | 上面那支 | 不碰 |
| `_entry` | `{"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}` | 直接蓋 |
| `body.json` | `{"argv": ["aos-loop", "loop.json"]}` | 直接蓋 |
| `loop.json` | 每拍跑 `fsm.json`、間隔 300 毫秒、三個窗的檔名 | 直接蓋 |
| `fsm.json` | 四格；格的程式指到 `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm/idle.py"}` 等（跟 reviewer 今天的寫法一樣） | 直接蓋 |
| `interfaces.json` | `entry`、`tools`、`llm`、`llm_keys`、`history`、`system` | 直接蓋 |
| `tools.json` | `{"$override": [look、mailbox、json 三包的指示詞]}` | 直接蓋 |
| `llm.json` | `{"model": "luna"}` | 直接蓋 |
| `system.txt` | 那兩行字 | 直接蓋 |
| `_metainfo.json` | `summary` | 只設自己的鍵 |
| `README.md` | 一行 `DESCRIPTION` | 不在才寫 |

每份 json 帶一個 `description`（照 reviewer 範本的慣例，說這份檔是做什麼的）。夾裡不放任何「我是生成的」記號：產出之後它就是普通的定義夾（[10](10-使用者裁定.md)）。

接著 `aos-agent ctl add <這個夾>` 就掛上去。對照今天：`agent_def new` 抄 19 個檔、再分別去改三份。

## 完整例子：reviewer

對照 `templates/reviewer/`（10 檔）。這支重生出來的 json，內容要跟今天手寫的那 8 份等價；這是第三刀的驗收，只拿來比對，範本本身不換（使用者第 5 題）。

```python
#!/usr/bin/env python3
"""reviewer - review measured definition costs (agent.py: the source of this definition)."""
# ---- setup: find the aos package (keep these lines as they are) ----
# ---- your agent: change the lines below ----

DESCRIPTION = "Review measured definition costs and prescribe a fix or split when model downgrades fail."

META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}

SYSTEM = ag.by_hand("system.txt")       # 2.4 KB of text: kept as a file, written by hand

def lib(name):                          # ordinary Python is the point: no more 11 copies of the same path
    return ag.tool(name.rsplit("/", 1)[-1], ag.home("/lib/tools/" + name))

TOOLS = [lib("aos/" + n) for n in ("review_round", "watch", "promote", "rollback", "measure")] \
      + [lib("base/" + n) for n in ("json_get", "json_ls", "json_set", "json_del", "read", "ls")]

LLM = {}                                # no model named: the caller's default kernel endpoint

def cell(name):                         # borrow the cells of the agent-fsm template
    return ["python3", ag.home("/templates/agent-fsm/%s.py" % name)]

FSM = ag.fsm("idle", [
    ag.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
    ag.state("think", cell("brain"), {0: "wait", 10: "idle"}),
    ag.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
    ag.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
])

INTERFACES = {"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}

FILES = {"ladder.json": {
    "ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_score": 0.9,
    "watch": {"window": 3, "tolerance": 0.1, "metric": "/token/in", "baseline_cases": 3},
    "promote_by": "self", "max_prompt_tokens_median": 10000, "retire_after_cases": 3,
}}

ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, meta=META, interfaces=INTERFACES, files=FILES)
```

看得到的差別：

| 項目 | 今天手寫 | 用 `agent.py` |
|---|---|---|
| 要動的檔 | 8 份 json＋`system.txt` | 1 支 `agent.py`＋`system.txt` |
| 15 處 `{"$env": "AOS_HOME", "$path": …}`（工具 11、格 4） | 一處一處打 | 兩個三行的小函式 |
| 狀態機打錯下一格的名字 | `agent_def check` 過、跑起來才 `CfgBad` | 重生時就報 `SpecBad`，講是 `agent.py` 的哪一格 |
| `system.txt` | 手寫 | 還是手寫（`ag.by_hand`） |

`INTERFACES` 裡的 `"history": None` 表示「預設有的這個鍵拿掉」，因為 reviewer 今天的 `interfaces.json` 沒有它；預設值照 agent-fsm 範本那份。

## eca 版（沒有狀態機的身體）會長怎樣

排在第三刀，這裡只示意。不宣告 `FSM`，骨架（`_entry`、`loop.json`、`cli.json`、`screen/`）照舊用 `agent_def new` 從 eca-claude 抄來，`agent.py` 只寫三份內容檔：

```python
DESCRIPTION = "Run Claude Code as an aos agent for the docs team."
SYSTEM = """..."""
TOOLS = [ag.pack(p) for p in ("gadgets", "events", "self", "def", "mailbox", "json", "jsonx", "index")] \
      + [ag.no("do_task")]
LLM = {"model": "sonnet"}

ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM)
```

這時它是「把 `agent_def tools`／`llm`／`system` 三個動作寫成一份檔」，`interfaces.json`、`loop.json` 重生不碰。
