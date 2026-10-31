← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 agent-eve、agent-fay、agent-gus、agent-hal（10-24）｜下一份：[04-demo-agents-2](04-demo-agents-2.md)（agent-kai、liv、meg、pip、llm-kernel/agent-ivy）

> 10-28 起 demo／lib 的 agent 範本：工具清單＝範本的 `tools.json`〔手寫相對路徑〕，brain `aos-tools ls --json`、act `aos-tools call`；topdown 的 agent 照舊掃 `tools/*/_tooldef.json`。

> 2026-10-24 收尾補（各 agent 做的時候沒改 code map）。用法與跑法在 [demo/README](../../../../../proto8/demo/README.md)；範本 agent-dan 見[入口](../proto8.md)的 `proto8/demo/` 段。12:46 那筆（babdaad2）只是各隻的 `brain.py` 認領題目時跳過 `new/` 裡 `.` 開頭的暫存檔。「同 agent-dan」＝只改了檔頭註解或錯誤訊息開頭的名字；10-24 下午 agent-dan 的 `brain.py` 才加的 `AOS_KERNEL_REPORT` 那幾行（經 LLM kernel 跑時把 usage 交給它），10-24 遷移時抄進了 eve、pyfix 子 agent、fay、hal、kai、liv、meg、pip、talk 的 member、self-improve 的改進者（gus 的 `shared.py`、hal 的 `compact/ask.py` 問腦的寫法不同，沒抄）。

### agent-eve

agent 當工具：主 agent 照抄 agent-dan，唯一的工具 `pyfix` 是另一整隻 agent（專改 Python）。[thinking](../../../../../proto8/thinking/2026-10-24-agent-as-tool.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`idle/`、`brain.py`、`act.py` | 同 agent-dan |
| `fsm.json` | 同 agent-dan，act 逾時放寬到 30 分鐘（等子 agent） |
| `.env`、`system.txt` | 模型名（會往下傳，但子 agent 用自己的）；人格：改 Python 交給 pyfix、task 寫清楚、回答前看 diff |
| `tools/pyfix` | 符號連結 → `../../../lib/agent/pyfix`（10-24 遷移；轉接、子 agent pyfix-agent、它掛的 lib/base 工具都在庫裡，見 [09-lib](09-lib.md)） |

### agent-fay

claude／codex CLI 當工具，人可以 `attach` 接進同一段對話。[thinking](../../../../../proto8/thinking/2026-10-24-cli-tools.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`idle/`、`.env`、`act.py` | 同 agent-dan |
| `fsm.json` | act 逾時 15 分鐘 |
| `brain.py` | 同 agent-dan，假腦改成把題目原樣交給 `claude` 工具 |
| `system.txt` | 腦有 claude、codex 兩個幫手，看檔或判斷程式就交代給它們 |
| `cli_session.py` | 符號連結 → `../../lib/agent/cli_session.py`（10-24 遷移；給 `attach` import，做法見 [09-lib](09-lib.md)） |
| `attach` | 人用的入口（python3、沒副檔名）：`attach claude`／`attach -d codex`／`attach` 列狀態；Ctrl-\ 跳出、畫面留著；把自己的資料夾傳給 `cli_session.attach_main` 列 `tools/` |
| `tools/claude`、`tools/codex` | 符號連結 → `../../../lib/agent/<名>`（10-24 遷移） |

### agent-gus

小念頭：先規劃 steps、每步 fork 成再跑一次自己，回來只帶結論。[thinking](../../../../../proto8/thinking/2026-10-24-thoughts.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`idle/` | 同 agent-dan |
| `loop.json`、`fsm.json` | max 60；idle → plan（120 秒）→ fork（1 小時）→ think（120 秒）→ act（180 秒） |
| `.env` | 模型名＋上限 `AOS_THOUGHT_MAX_STEPS`／`MAX_DEPTH`／`MAX_TOTAL`／`PARALLEL`／`TIMEOUT_S`／`MAX_CHARS`（`AOS_THOUGHT_DEPTH`、`AOS_THOUGHT_BUDGET` 由 fork 往下帶） |
| `shared.py` | 各格共用（不是格）：`die`、`claim`、讀寫 history、`tools_spec`、`ask`（問腦、記 `usage.jsonl`）、`launch`／`conclusion`（起小念頭、取結論） |
| `plan.py` | 認領題目、請腦回 `{context, steps}` → `$AOS_STACK/steps.json`；深度到頂或額度不夠、或腦回散文不是規劃（10-24），就不拆；規劃寫錯 `PlanBad` |
| `fork.py` | needs 齊了才起、同時 `AOS_THOUGHT_PARALLEL` 個，小格 `thoughts/<id>/{ws,stack}`；全到齊一步一則接進 history；小念頭失敗＝那步記「失敗了：原因」照樣接、不停，needs 它的步不起（10-24 晚） |
| `brain.py`、`act.py` | think／act 同 agent-dan 的做法但改寫成用 `shared`；brain 不認領題目（plan 做了）；act 交答案時把 `steps.json` 收進 `plans/`；叫工具出的問題（退非 0、沒有的工具、arguments 壞）回給腦、不停，同 agent-dan |
| `thought.json`、`thought.py` | 給別的程式叫一個小念頭：stdin `{goal, context?, needs?}` → stdout 只有結論，過程在 `runs/NNN/`；錯 `StepBad` |
| `system.txt` | 人格（看到小念頭結論就彙整） |
| `tools/run_python` | 符號連結 → `../../../lib/base/run_python`（10-24 遷移；stdin `{"code", "timeout_s"}` → 結束碼與輸出） |

### agent-hal

土法 compact：history 太大時先壓再想。[thinking](../../../../../proto8/thinking/2026-10-24-compact.md)

| 哪裡 | 負責什麼 |
|---|---|
| `_entry`、`loop.json`、`.env`、`idle/`、`brain.py`、`act.py` | 同 agent-dan |
| `tools/math`、`tools/clock` | 符號連結 → `../../../lib/base/<名>`（10-24 遷移前是 agent-dan 的複本） |
| `fsm.json` | idle → compact（資料夾）→ think → act |
| `system.txt` | 同 agent-dan，多一句：開頭【compact】那則是摘要、沒有的別猜 |
| `compact/_entry`、`compact.py` | `exec python3 compact.py`（`--force` 不看門檻）；超過 `AOS_COMPACT_OVER_KB` 才壓：① 工具呼叫各一句 ② 每段摘要＋keep ③ 修成一份；保留最近幾題；原檔收進 `compact/<run>/orig.jsonl`、`report.json`、`log.jsonl`；斷了接著做；錯 `SummaryEmpty`、`HistoryChanged`… |
| `compact/ask.py` | 問腦（`AOS_COMPACT_URL`，沒設用 `AOS_BRAIN_URL`；都沒設＝假腦照字面拼），回 content 與 usage（沒帶就粗估） |
| `compact/prompts/` | `note.txt`、`segment.txt`、`final.txt`：三步的 system 訊息 |
| `compact/.env` | 門檻 32 KB、段 8 KB、保留最近 2 題、保留行上限、三步的模型 |
