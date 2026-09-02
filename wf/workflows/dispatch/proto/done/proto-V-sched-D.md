# 任務：排程保底 D——flock 槽、兩層並行上限、數字優先度、等待上限（`core/llm`）

> 交接書是唯一契約。研究與**使用者 11 條裁決**在 [ideas/scheduling/README](../../../ideas/scheduling/README.md)（§方案 D 的設計與改動量估算、末段裁決表**壓過**建議）；實測 [experiments](../../../ideas/scheduling/experiments.md)；協定 [PROTOCOL](../PROTOCOL.md)。

## 背景與唯一目標

受限的 LLM CPU 數量：每顆 CPU 有使用者設定的並行上限（例 `deepseek: 3`、`lmstudio: 1`），超過就排隊。裁決：**先做 D 保底**（正式 B 之後另開）。
**唯一目標**：`aos llm`（與 engine=pi 的 step）在打 CPU 之前先取一個該 CPU 的槽（檔案鎖），槽滿就依**數字優先度**排隊、等超過**等待上限**就退回（exit 75、status `waiting-llm`）；上限設定分兩層（使用者層權威、世界層只能往下限）。最小原型、邊緣狀況跳過。

## 團隊（你是 Opus 隊長）

工作量押給 codex（`codex exec -m gpt-5.6-sol -C <worktree> --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；sol／terra／luna 皆可，最多 4 條、量力而為；**任務書要寫「最終回覆即成品，另外也寫到 -o」**——隊 S 的 codex 曾把 -o 誤讀而交白卷）。建議：① 槽機制（flock 目錄、取／放槽、優先度排隊、等待上限）；② 設定兩層讀取與合併（`~/.aos/cpus.json`＋`.aos/llm.json`）與 `aos llm --engine/--priority`；③ pi step 佔槽（只動 `core/agent/src/engine_pi.cpp`）；④ 測試＋README＋code map。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。

## 工作

1. 讀 README §D、裁決表、`core/llm/`、`core/agent/src/engine_pi.cpp`、`step.cpp`（只讀）。
2. **槽**：每顆 CPU 一個目錄（使用者層 `~/.aos/slots/<cpu>/`，可用 `AOS_HOME` 覆寫），`N` 個槽檔 `0..N-1` 用 `flock(LOCK_EX|LOCK_NB)` 輪取；取不到就進等待：依 `priority`（數字，大者先）與到達時間排序——最簡做法是**等待者寫一個 `wait/<priority>-<ts>-<pid>` 檔、輪詢時只有隊首才去搶槽**；等待超過 `wait_ms`（設定，預設 60s）就退出 **exit 75**、stderr 一行 `waiting-llm`。持有者死掉 flock 自動釋放。
3. **設定**：使用者層 `~/.aos/cpus.json`：`{"deepseek":{"max_inflight":3,"wait_ms":60000},"lmstudio":{"max_inflight":1}}`；世界層 `.aos/llm.json` 同形，只能把 `max_inflight` 往下改（往上就取小者）。CPU 名＝engine 名（`lmstudio`／`deepseek`／`pi` 對應到它的 provider）。沒設定＝不限（維持現狀）。
4. **`aos llm`**：加 `--engine <cpu>`（預設 lmstudio）、`--priority <int>`（預設 0）；打端點前取槽、回來放槽。`aos agent step` 走 lmstudio 時用 agent 的 `engine.json` 裡的 `priority`（沒有＝0）；`aos agent init --priority N` 寫進去（`init.cpp` 只插一個欄位——隊 U 同時在改 `core/agent`，衝突面要小）。
5. **pi 佔槽**：`engine_pi.cpp` 起 pi 之前取 `deepseek`（或其 provider 名）的槽，整個 step 佔到結束。
6. `state.json`：不動（B 再做）；但 `aos llm --slots` 印每顆 CPU 目前佔用／等待（給人看）。
7. 測試（用假端點或 `AOS_LLM_URL` 指向本機假 server／或只測槽層：多 process 搶槽、優先度順序、等待逾時 exit 75；不 sleep 長時間、可注入 wait_ms）；README、code map。
8. commit 到你的 worktree 分支，**收線時 rebase main**（隊 U 會先落地），不 merge。

## 硬性限制

- **禁區**：`core/exec`、`core/wire`、`core/loop`、`core/tick`、`reference/`、`app/`；`core/agent` 只可改 `engine_pi.cpp`、`init.cpp`（一個欄位）、`README.md`（一段）；`wf/` 除 code-map、本資料夾、`ideas/scheduling/`（只追加「實作註記」）之外不碰。
- `git add` 只加明確路徑；不 push；不取鎖（**flock 槽是產品功能不算**）、不開 GUI、不 load／unload LM Studio、不用 wf-lint；真打 DeepSeek 只在 smoke 一次、key 從環境變數、不落檔。
- 邊緣狀況跳過；小裁決記「隊長裁決」；只有裁決表自相矛盾才 BLOCKED。

## 驗收（就這 5 條）

1. build＋ctest 全綠（rebase 到最新 main 後）。
2. `~/.aos/cpus.json` 設 `lmstudio: {max_inflight: 1, wait_ms: 2000}` → 同時起兩個 `aos llm`（stdin 各一句）→ 一個先跑、另一個等到第一個結束才打端點（用 `--slots` 或 log 證明）；把 `wait_ms` 改 100 → 第二個 exit 75、stderr 有 `waiting-llm`。
3. 三個等待者 priority 1／5／3 → 取槽順序 5、3、1（測試）。
4. 世界層 `.aos/llm.json` 設 `lmstudio: {max_inflight: 0}` → `aos llm` 立即 exit 75（世界只能往下限）；設 5 → 仍是 1（取小者）。
5. `aos agent init --engine pi` 的 step 期間 `aos llm --slots` 顯示 deepseek 佔 1。

## 回報

最後一則訊息＝ `reports/V.md` 摘要（≤ 30 行）＋STATUS＋worktree 路徑與分支名。

## 隊長裁決

完整理由見 [reports/V](../reports/V.md)。

| # | 裁決 |
|---|---|
| 1 | **不做 `aos agent init --priority N`**——需要動 `run.cpp`／`agent.hpp`／`engine.cpp`／`step.cpp` 四個檔，超出硬性限制允許的 `core/agent` 範圍，且 5 條驗收都不需要它。priority 全落在 `core/llm`（`--priority` 旗標＋`AOS_LLM_PRIORITY` 環境變數），pi 那條讀同一個環境變數 |
| 2 | pi 的 CPU 名＝`engine.json` 的 `provider`，空的話 `deepseek` |
| 3 | pi 取槽放在**吃掉 `say/*.md` 之前**——逾時退回時訊息才不會消失，下回合 `every` 自然重試 |
| 4 | 世界層的 `wait_ms` 直接覆蓋（不套「只能往下」）——它不是資源上限 |
| 5 | 沒設定＝不限（依 §3）；裁決 9 的 lmstudio 1／deepseek 3 寫進 README 當建議值 |
| 6 | 等待迴圈「前 N 名都可搶槽」而非「只有隊首搶」——一樣是嚴格優先序，但 N 個槽能同一輪填滿 |
| 7 | `core/llm` 自己實作 `resolve_world()`，不為了找 `.aos/` 引入 `aos::loop` 相依 |

