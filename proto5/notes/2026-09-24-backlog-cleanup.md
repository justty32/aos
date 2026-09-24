# backlog 清光（2026-09-24，agent 線定稿後）

← [proto5 README](../README.md)｜09-23 那輪：[backlog-cleanup](2026-09-23-rearch/backlog-cleanup.md)

agent 線三份規範（[agent.md](../spec/agent.md)、[aos-agent.md](../spec/aos-agent.md)、[aos-llm.md](../spec/aos-llm.md)）09-24 定稿並實作後，`proto5/backlog/` 六個檔逐一判掉，資料夾拿掉。

## 新規範解掉的（刪檔）

| 檔 | 原問題 | 結論 | 新規範 |
|---|---|---|---|
| `request-identity.md` | 送出請求與加 waits 之間崩掉會重送 | 身分只記在 `state.batch`：建批那一刻就把每個 call 的工作名（`B-i`）寫進 state，這一寫之前什麼都沒送；崩了靠「查有沒有放過」四步（`K/requests` → 帳本 `procs`／`replies` → `K/responses`）判斷，不盲目重送 | agent.md §4.3；aos-agent.md §5.1、§5.2 |
| `tool-call-order.md` | 同批工具呼叫沒有先後保證 | 09-22 已拍板接受並行，新規範把這句正式寫進定稿：「只保證接回的順序，不保證執行順序」 | agent.md §7.1 第 1 條；aos-agent.md §7 |
| `kiss-holes.md` 第 1、7 條（agent 那半） | 同 request-identity | 同上 | agent.md §4.3；aos-agent.md §5.2 |
| `kiss-holes.md` 第 4 條 | 另開入口同時跑同一 agent，沒有並行鎖 | 明文列進保證外：「一個 agent 家同時只能有一個驅動者……沒有鎖」，跟 cpu／kernel 那層同一種約定 | aos-agent.md §13 |
| `review-leftovers.md` R4 | cpu 主人被 KILL、daemon 重拉後可能跟孤兒子程式重疊 | 新形狀（daemon 重拉 cpu）一樣寫進保證外，cpu／kernel 兩層都已明文 | cpu.md §5.3；kernel.md §7 |

## 還沒解、併進 WAIT_USER 的（刪檔）

| 檔 | 原問題 | 現況 | 去處 |
|---|---|---|---|
| `agent-fail-state.md` | 連敗暫停要不要改成明確 `fail` 狀態 | agent.md §6 明寫「這輪沒做」，本來就在 [WAIT_USER A.14(d)](../../wf/WAIT_USER.md) | 改連結指來這份筆記，內容不變 |
| `llm-cpu-fallback.md` | 問模型的 endpoint 壞掉要不要自動換手 | aos-llm-call 一個代號只認一個 endpoint、不重試，沒人追這題 | 併入 [WAIT_USER A.16](../../wf/WAIT_USER.md) |
| `kiss-holes.md` 第 2 條（kernel 那半） | kernel 的 `queue` 沒有期限，只有 `timeout_ms` 管跑的時間 | agent 那半（半批沒送完永遠等）已經解掉（見上，aos-agent.md §13 有手動 escape：stop 後把 `batch` 設 `null`）；kernel 排隊本身要不要加期限沒人追 | 併入 [WAIT_USER A.17](../../wf/WAIT_USER.md) |
| `review-leftovers.md` R11 | once 工作要等 kernel 一格派、下一格收，一次問答的延遲綁在 `tick_ms` | 09-23 那輪已判定「這算不算要做，要人判」，agent 重寫沒碰這塊，沒人追 | 併入 [WAIT_USER A.18](../../wf/WAIT_USER.md) |

## 沒動的連結

`proto5/README.md`、`proto5/spec/agent.md` §6 原本連到 `backlog/README.md`／`backlog/agent-fail-state.md`，都改指來這份筆記或 WAIT_USER。
