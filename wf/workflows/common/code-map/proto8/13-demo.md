← [入口](../proto8.md)｜涵蓋：`proto8/demo/`（agent 範本、daemon、talk、eca、tick、`run.sh`）

用法、跑法與錯誤代號以 [demo/README](../../../../../proto8/demo/README.md) 為準。路徑相對於該段標題的資料夾。

**agent 骨架**（下面說「骨架」就是這組）：`_entry`（`exec aos-loop loop.json`）、`loop.json`（`exec` 指 `fsm.json`、`max`）、`fsm.json`（idle → think → act）、`idle/_entry`（`cur/` 或 `new/` 有題目退 0、沒有退 10）、`brain.py`（think：認領題目、問腦、接進 history；沒設 `AOS_BRAIN_URL`＝假腦）、`act.py`（跑工具，工具的問題回給腦不停）、`.env`（模型名）、`system.txt`（人格）、`tools.json`（工具註冊檔）、`tools/<名>`（捷徑到 `lib/`）。

## `demo/`

| 檔 | 負責什麼 |
|---|---|
| `run.sh` | 各建暫時工作區把幾個 demo 跑一遍，印整棵 stack 樹 |

## `demo/agent-nia/`（格組起來的 agent 範本：一輪走 `lib/agent/round`）

| 檔 | 負責什麼 |
|---|---|
| `_entry` | JSON 入口 `["aos-loop", "loop.json"]` |
| `loop.json` | 單子 `["aos-fsm", "fsm-stop.json"]`、`cwd` 指 `lib/agent/round`（停著等＝改指 `fsm-idle.json`） |
| `parts.json` | 格的通訊錄（aos-exec 格式）：queue、history、act、`hook/pre_think`＝compact、endpoint |
| `tools.json`、`system.txt` | 腦的工具（clock、math）、system 訊息 |

## `demo/agent-bob/`（混合範本：子資料夾＋單子；agent 當工具）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py` | 骨架；think 是 `fsm.json` 裡的單子 |
| `act/_entry` | 把 `plan.txt` 當題目交給 `tools/cathy`，答案寫 `out/` |
| `act/tools/cathy/*` | 另一隻 agent（自己的骨架＋`act/tools/stamp/_entry`：加時間戳、計次） |

## `demo/agent-ann/`（全內嵌對照：零子資料夾）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`brain.py`、`act.py`、`.env` | 骨架；`_entry`＝`exec aos-exec loop.json`，三格全是單子 |
| `idle.py` | idle 格（單子叫它） |

## `demo/agent-eve/`（agent 當工具）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；act 逾時 30 分鐘（等子 agent） |
| `tools/pyfix` | 捷徑 → `lib/agent/pyfix`（改 Python 的子 agent） |

## `demo/agent-gus/`（小念頭：規劃、fork、只帶結論回來）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；fsm 多 plan、fork 兩格 |
| `shared.py` | 各格共用：認領、history、問腦、`launch`／`conclusion`；上限寫死 |
| `plan.py` | 請腦回 `{context, steps}` → `steps.json`；`PlanBad` |
| `fork.py` | 每步起一個小念頭（同一隻 agent），全到齊接進 history |
| `thought.json`、`thought.py` | 給別的程式叫一個小念頭：stdin 一步 → stdout 只有結論 |
| `tools/run_python` | 捷徑 → `lib/base/run_python` |

## `demo/agent-hal/`（土法 compact）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；fsm 在 think 前多 compact 格 |
| `compact/_entry`、`compact/compact.py` | history 超過門檻才三步壓縮，原檔與報告留在 `compact/<run>/` |
| `compact/ask.py`、`compact/prompts/*` | 問腦；三步的 system 訊息 |
| `tools/math`、`tools/clock` | 捷徑 → `lib/base` |

## `demo/agent-kai/`（按意圖組 context）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架 |
| `brain.py` | 組 context：目錄＋挑出的舊題＋這題完整；記 `context.jsonl` |
| `tools/recall/_entry`、`tools/recall/_tooldef.json` | 搜舊題、展開一題 |
| `tools/recall/turns.py` | 把 history 切成題、照意圖挑（brain 也 import） |
| `tools/math`、`tools/clock`、`tools/read` | 捷徑 → `lib/base` |

## `demo/agent-liv/`（工具引用 lib、同名自己的贏）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；假腦叫一次 `ls` |
| `_metainfo` | 這隻 agent 的特性範例 |
| `tools/clock/_entry`、`tools/clock/_tooldef.json` | 自己的真資料夾，示範覆寫庫裡的 clock |
| `tools/read`、`tools/write`、`tools/edit`、`tools/bash`、`tools/ls`、`tools/json_read`、`tools/json_edit` | 捷徑 → `lib/base` |

## `demo/agent-meg/`（長期記憶庫）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；`.env` 說明 `AOS_HEAP` |
| `brain.py` | 問腦前附上相關記憶；庫壞＝`HeapBad` |
| `tools/memory` | 捷徑 → `lib/aos/memory` |

## `demo/agent-pip/`（coding agent）

| 檔 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`fsm.json`、`idle/_entry`、`brain.py`、`act.py`、`.env`、`system.txt`、`tools.json` | 骨架；max 200、act 15 分鐘 |
| `tools/*` | 十二條捷徑 → `lib/base`（read、write、edit、bash、ls、stat、view、json_edit、mkdir、move、copy、trash） |

## `demo/talk/`（agent 之間寄信）

| 檔 | 負責什麼 |
|---|---|
| `member/_entry`、`member/loop.json`、`member/fsm.json`、`member/idle/_entry`、`member/.env`、`member/system.txt`、`member/tools.json` | 一隻成員的骨架 |
| `member/brain.py` | 信翻成「[來信] …」、system 加名冊 |
| `member/act.py` | 要回的信經 `send_message` 自動寄回 |
| `member/tools/*` | 捷徑 → `lib/aos`（send_message、check_inbox）、`lib/base`（math、clock） |
| `team/_entry`、`team/daemon.json` | 團隊：一個 daemon 顧 ann、bob、cat 三個子 loop |
| `team/quiet.py` | 成員信箱都空＝退 10 收工；有成員失敗＝停 |
| `team/roster.json` | 名冊範例：成員、群組、手數與大小上限 |

## `demo/` 的 eca-claude、eca-codex（外部 coding agent 範本，兩份同形）

| 檔 | 負責什麼 |
|---|---|
| `eca-*/_entry` | `["aos-loop", "loop.json"]` |
| `eca-*/loop.json` | 停著等版：`aos-eca-turn --on-empty idle --on-busy yield` |
| `eca-*/cli.json`、`eca-*/tools.json` | CLI 種類與旗標；工具註冊檔 |

## `demo/` 的 daemon、daemon-2、daemon-3、tick

| 檔 | 負責什麼 |
|---|---|
| `daemon/_entry`、`daemon/daemon.json` | 一個 daemon 同時顧 bob、ann 兩個子 loop |
| `daemon-2/_entry`、`daemon-2/daemon.json` | 信箱模式的 daemon |
| `daemon-2/agent-sam/_entry` | 跑一次就寄信請 daemon 加一個子項 tick |
| `daemon-3/_entry`、`daemon-3/daemon.json` | 同一份 `procs` 兩種寫法各掛一次 tick（子 loop／aos-exec 一次） |
| `tick/_entry`、`tick/loop.json` | loop 跑 5 次 `aos-tick`，時鐘檔是 5 |
