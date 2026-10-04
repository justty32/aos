# astra-3：step／手寫 Python 對照與長跑分報告

本線 8 個對照案例全部完成、最終統計內容相同；真 daemon 的 450 個已關回合中觀察到 112 次 CSV 工作結束，沒有 halted／error，工作結束時檔案固定 10 個。本線未發現 B 或 G；刻意 SIGKILL 屬 X，step 的停住／選定自動重派符合契約。這只描述本次工作與中斷位置，不推論其他工作或所有故障窗口。

## 對照方法

- 共同輸入：10,000 列 CSV；同一份 [csv_worker.py](csv_worker.py) 實作 convert、stats，四個部門、相同數值與原子產物發布，所有案例統計 JSON 完全相同。
- Python baseline 是**單一程序、自己保存每步 checkpoint**：執行前寫 `pc`，成功後記 `done`；重啟略過已完成步。不是無 checkpoint 的 baseline，也未使用外部 supervisor 自動重啟。
- step 為真 daemon／node、keep 直譯器＋once 子工作；預設 `on_unknown: stop`，另列冪等步選 `resend` 的兩案。
- kill 點精確設在 convert／stats 的第 **5,001／10,000** 列已處理、該步產物尚未發布。step 殺子工作的程序群組；Python 殺整個單程序 pipeline 的程序群組。step 直譯器／daemon 此時仍活著，這是兩種執行架構的實際差異。
- 一次性 gate 只用於固定故障位置；新 attempt 看見已命中的標記即繼續，不需人手解 gate。額外人工動作**不含首次啟動、觀察與注入故障**，每個恢復 CLI 命令算 1；baseline 是重新執行同一程式，step 是 `resume --resend`。重派次數＝兩個必要步驟之外額外啟動的次數。

| 實作／策略 | SIGKILL 位置 | 恢復人工命令 | 重派次數 | convert 啟動 | stats 啟動 | 耗時秒 |
|---|---|---:|---:|---:|---:|---:|
| python-checkpoint | none | 0 | 0 | 1 | 1 | 0.031 |
| step-default | none | 0 | 0 | 1 | 1 | 0.336 |
| python-checkpoint | convert | 1 | 1 | 2 | 1 | 0.053 |
| step-default | convert | 1 | 1 | 2 | 1 | 0.39 |
| python-checkpoint | stats | 1 | 1 | 1 | 2 | 0.063 |
| step-default | stats | 1 | 1 | 1 | 2 | 0.552 |
| step-auto | convert | 0 | 1 | 2 | 1 | 0.397 |
| step-auto | stats | 0 | 1 | 1 | 2 | 0.397 |

時間含首次啟動與故障注入／恢復，只各跑一次；step 含 daemon 與排程成本，這張表不是效能基準測試。

直接讀檔定位：兩者都只需讀 **1 個主要 JSON**。Python 的 `checkpoint.json` 有 `pc`、`done`，可知道停在 convert 或 stats，但它本身不記故障種類；step 的 `frame.json` 有 `pc`、`pending` 的 request／attempt 與 `halt.kind: unknown`，並指出沒有結果檔。step 還能讀 `results/` 與槽 `exit.json` 核對完成證據。探針的 `events.jsonl`、gate 標記僅用於量測，未算作產品自帶診斷能力。

8 案都沒有人工修改 checkpoint、frame、產物或結果檔。預設 step 與此 checkpoint baseline，在這兩個 kill 點都只重做被殺步；選定 step 自動 resend 時恢復人工命令為 0。其他提交窗口未由這個對照測試涵蓋。

契約對應：step README「直譯器」保證同一嘗試不派第二次、證據不足停 unknown；spec §4「群組被 kill 沒有結果」、§5.6「冪等 resend 同 request 新 attempt 最多一次」。這些 X 注入的結果符合保證，不列待修。

證據：[比較數字與中斷 frame](comparison.json)、[數字摘要](summary.json)。重現：從 repo 根執行 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/comparison/run_comparison.py --mode comparison`。

## 真 node 長跑

使用原本 `packs/step/examples/csv/`（5 列，convert → stats → end）、`restart_on_end: true`、`wake: false`、interval 20 ms；不是純函式 loop，也不是 mock tick／tock。每 10 ms 觀察、每個已關回合至少保存一次量測（含初始 round 0），另外保存工作 `ended` 同階段快照。

| 量測 | 結果 |
|---|---:|
| 已關回合 | 450 |
| 逐回合樣本（含 round 0） | 451 |
| 牆鐘時間 | 25.195 秒 |
| 觀察到 ended 的不同 inst | 112 |
| ended 報表列數與 convert request 相符 | 112／112 |
| ended 的 convert／stats attempt 各為 1 | 112／112 |
| halted／error | 0 |
| ended 工作目錄檔案數 | 10，每次相同 |
| ended 工作目錄 bytes 範圍 | 4,381～4,397 |
| 第一／最後 ended | round 4／448 |
| 最後 ended 對第一個的 bytes 差 | +16 bytes |
| 所有階段 node 檔案數範圍 | 7～27 |
| 所有階段 root 檔案數範圍 | 8～35 |

整個觀察窗中，工作目錄各階段為 4～10 檔，未見檔案數隨 inst 累積。不同階段及原子暫存檔會影響 node／root 的瞬間數量，因此不把其 min/max 當作固定階段的成長量；工作 `ended` 才是比較基準。+16 bytes 是本次觀察值，不能由有限長跑宣稱永久固定大小。最後兩回合可已開始下一個工作，112 是實際看到 ended 且核對過的數量。

證據：[451 個回合樣本＋112 個 ended 快照＋最終回合／框架](longrun.json)。重現：從 repo 根執行 `PYTHONDONTWRITEBYTECODE=1 python3 proto7-2/notes/play/2026-10-04-astra-3-infra-evidence/comparison/run_comparison.py --mode longrun --rounds 450`。

## 清理

本線只使用自建 `/tmp/aos72-test-*`、`/tmp/astra3-python-*`，未碰 scratchpad。每案以追蹤的 PID／程序群組結束自己程序；daemon 先 SIGTERM，必要時保底 SIGKILL，沒有使用 `pkill -f`。所有暫存根已移除；每案 cleanup 的 PID `ps` 核對只剩表頭，AOS7_ROOT／daemon root 參數掃描無殘留。完整清理欄位在 comparison.json／longrun.json，彙總在 summary.json。沒有 LLM 呼叫，沒有修改既有程式、測試、文件，沒有 commit／push。
