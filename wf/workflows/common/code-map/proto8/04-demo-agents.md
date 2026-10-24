← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 agent-eve、agent-fay、agent-gus、agent-hal（10-24）｜下一份：[04-demo-agents-2](04-demo-agents-2.md)（agent-kai、liv、meg、pip、kernel-llm/agent-ivy）

> 2026-10-24 收尾補（各 agent 做的時候沒改 code map）。用法與跑法在 [demo/README](../../../../../proto8/demo/README.md)；範本 agent-dan 見[入口](../proto8.md)的 `proto8/demo/` 段。12:46 那筆（babdaad2）只是各隻的 `brain.py` 認領題目時跳過 `new/` 裡 `.` 開頭的暫存檔。「同 agent-dan」＝只改了檔頭註解或錯誤訊息開頭的名字；10-24 下午 agent-dan 的 `brain.py` 才加的 `AOS_KERNEL_REPORT` 那幾行，這些抄本都沒有。

### agent-eve

agent 當工具：主 agent 照抄 agent-dan，唯一的工具 `pyfix` 是另一整隻 agent（專改 Python）。[thinking](../../../../../proto8/thinking/2026-10-24-agent-as-tool.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`idle/`、`brain.py`、`act.py` | 同 agent-dan |
| `fsm.json` | 同 agent-dan，act 逾時放寬到 30 分鐘（等子 agent） |
| `.env`、`system.txt` | 模型名（會往下傳，但子 agent 用自己的）；人格：改 Python 交給 pyfix、task 寫清楚、回答前看 diff |
| `tools/pyfix/tool.json`、`_entry` | 給腦看：`task`（必填）、`dir`；轉接（python3）：每次開新小格 `runs/NNN/`（`ws/`、`stack/`、備份 `before/`）、task 寫進子 agent 的 `new/task.txt`、`aos-exec --dotenv-override` 叫它、印 `out/task.txt`＋實際 diff；錯 `AgentFailed`、`AnswerMissing`、`DirBad`… |
| `tools/pyfix/agent/` | 子 agent pyfix-agent：agent-dan 範本（錯誤開頭 `pyfix-agent`），自己的 `system.txt`、`.env`（`--dotenv-override` 蓋過外層模型）、`loop.json` max 60、think 180 秒／act 300 秒 |
| `tools/pyfix/agent/tools/*` | `list_files`、`read_file`、`write_file`、`edit_file`、`run_python`，只碰 `$PYFIX_DIR`（沒設＝`DirMissing`） |

### agent-fay

claude／codex CLI 當工具，人可以 `attach` 接進同一段對話。[thinking](../../../../../proto8/thinking/2026-10-24-cli-tools.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`idle/`、`.env`、`act.py` | 同 agent-dan |
| `fsm.json` | act 逾時 15 分鐘 |
| `brain.py` | 同 agent-dan，假腦改成把題目原樣交給 `claude` 工具 |
| `system.txt` | 腦有 claude、codex 兩個幫手，看檔或判斷程式就交代給它們 |
| `cli_session.py` | 共用做法：畫面沒開＝非互動（`claude -p --resume`／`codex exec resume`）；畫面開著＝tmux 貼字、等 hook 寫 `turns.jsonl`；小格放 `session.txt`、`tty.sock`、`lock`…；錯 `cli_session: 代號`（`SessionBad`、`CliMissing`…） |
| `attach` | 人用的入口（python3、沒副檔名）：`attach claude`／`attach -d codex`／`attach` 列狀態；Ctrl-\ 跳出、畫面留著 |
| `tools/claude/`、`tools/codex/` | `_entry`（stdin `{"prompt"}` → 回答，叫 `cli_session`）、`tool.json`、`cli.json`（旗標：claude 只給 Read／Glob／Grep、sonnet、每次 0.5 美元；codex 唯讀沙盒） |

### agent-gus

小念頭：先規劃 steps、每步 fork 成再跑一次自己，回來只帶結論。[thinking](../../../../../proto8/thinking/2026-10-24-thoughts.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`idle/` | 同 agent-dan |
| `loop.json`、`fsm.json` | max 60；idle → plan（120 秒）→ fork（1 小時）→ think（120 秒）→ act（180 秒） |
| `.env` | 模型名＋上限 `THOUGHT_MAX_STEPS`／`MAX_DEPTH`／`MAX_TOTAL`／`PARALLEL`／`TIMEOUT_S`／`MAX_CHARS`（`THOUGHT_DEPTH`、`THOUGHT_BUDGET` 由 fork 往下帶） |
| `shared.py` | 各格共用（不是格）：`die`、`claim`、讀寫 history、`tools_spec`、`ask`（問腦、記 `usage.jsonl`）、`launch`／`conclusion`（起小念頭、取結論） |
| `plan.py` | 認領題目、請腦回 `{context, steps}` → `$AOS_STACK/steps.json`；深度到頂或額度不夠就不拆；錯 `PlanBad` |
| `fork.py` | needs 齊了才起、同時 `THOUGHT_PARALLEL` 個，小格 `thoughts/<id>/{ws,stack}`；全到齊一步一則接進 history；錯 `ThoughtFailed`，重跑只補失敗的 |
| `brain.py`、`act.py` | think／act 同 agent-dan 的做法但改寫成用 `shared`；brain 不認領題目（plan 做了）；act 交答案時把 `steps.json` 收進 `plans/` |
| `thought.json`、`thought.py` | 給別的程式叫一個小念頭：stdin `{goal, context?, needs?}` → stdout 只有結論，過程在 `runs/NNN/`；錯 `StepBad` |
| `system.txt`、`tools/run_python/` | 人格（看到小念頭結論就彙整）；唯一的工具：stdin `{"code"}` → 結束碼與輸出 |

### agent-hal

土法 compact：history 太大時先壓再想。[thinking](../../../../../proto8/thinking/2026-10-24-compact.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`.env`、`idle/`、`brain.py`、`act.py`、`tools/math/`、`tools/clock/` | 同 agent-dan |
| `fsm.json` | idle → compact（資料夾）→ think → act |
| `system.txt` | 同 agent-dan，多一句：開頭【compact】那則是摘要、沒有的別猜 |
| `compact/_entry`、`compact.py` | `exec python3 compact.py`（`--force` 不看門檻）；超過 `COMPACT_OVER_KB` 才壓：① 工具呼叫各一句 ② 每段摘要＋keep ③ 修成一份；保留最近幾題；原檔收進 `compact/<run>/orig.jsonl`、`report.json`、`log.jsonl`；斷了接著做；錯 `SummaryEmpty`、`HistoryChanged`… |
| `compact/ask.py` | 問腦（`COMPACT_URL`，沒設用 `AOS_BRAIN_URL`；都沒設＝假腦照字面拼），回 content 與 usage（沒帶就粗估） |
| `compact/prompts/` | `note.txt`、`segment.txt`、`final.txt`：三步的 system 訊息 |
| `compact/.env` | 門檻 32 KB、段 8 KB、保留最近 2 題、保留行上限、三步的模型 |
