# Agent 規格入口

← [規格總入口](../README.md)｜[共用契約](../contracts.md)

本區管 agent 角色的吃訊息、整理 context、選工具與回覆；node 與角色定義見[術語](../terms.md)。

| 檔案 | 責任 |
|---|---|
| [設定](configuration.md) | 設定檔、tick 外修改與任務直接讀檔 |
| [輸入與回覆](input.md) | 收件、消費與正式輸出 |
| [記憶與 context](memory.md) | 歷史、筆記、材料選擇與結果預覽 |
| [工具](tools.md) | 模型呼叫驗證、工作配對與結果解讀 |
| [通用 tick](../settled/tick.md) | 核心（互斥、照表跑、上下層）與標準配備（group／needs、git 提交、收件、投件、once、cgroup） |

## 預設 agent 任務（N-14）

〔使用者方向 2026-09-29〕LLM／工具的非同步派出與收結果依[通用 tick](../settled/tick.md)，LLM 代發依 [LLM 資源](../scheduling/llm.md)。

每個 module 一項任務：讀自己的收件與已回來的結果、整理 context、驗證工具呼叫，再保存進度或回覆。請求／回應放 `.aos/outbox/`，何時投出、何時清原件依 [B-623](../settled/tick.md)、[B-624](../settled/tick.md)（Q1／Q2）。最小範本見[agent 任務表](../protocol/agent-tasks.md)，分組及失敗處理由通用 tick 決定。

〔第十八批，P-704 從協議篇搬上；第十九批補通道〕**module 每格做的事**：一項 module 就是任務表上一項任務（`agent`，`aos-agent-step`），另一項是 `aos-clean`（標準配備，到期才清）。每格：先收件（檔案與通道兩條路，[A-201](input.md)，最多處理 64 件）→ 收工具與 LLM 的結果（[A-403](tools.md)）→ 推進輸入、準備請求或回覆（[A-302](memory.md)、[A-203](input.md)）→ 記用量與摘要。module 只把請求或回應放 `.aos/outbox/`，並把已消費的原件複製進追蹤區；何時投件、刪原件由標準配備依 B-623、B-624 做。還有可推進的輸入，摘要 `ready=true`；只在等結果則 `false`。〔第十八批〕在等自己開的 once 時，`due_ms` 設成下次查看的時間（[A-401](tools.md)），其餘沒有到期事務時為 null。〔第十九批〕任務可帶自己的 `user`（[B-620](../settled/tick.md)）；agent 的預設任務都不帶，沿 node 的身分。

〔使用者方向 2026-09-30，第十八批〕**agent 範本對每個送出的請求預設設鬧鐘**（待送封套的 `alarm_ms`，[P-206](../settled/protocol/node.md)），對方逾時沒處理，agent 自己會發現，不靠 aos 寫待辦。預設多久、鬧鐘和「投件當場被丟掉」對不上的地方（Q26）、鬧鐘響了之後 agent 怎麼收尾，都延後（[P-008](../protocol/README.md#p-008)）。

〔建議預設，未拍板〕必要狀態直接放普通檔案，例如連續無效回覆次數、尚待結果的請求、已選 context 的來源；只保存接續工作真正需要的內容。檔案隨所屬 group 生效，不另存一套相同進度。

## A-503 完成與等待〔建議預設，未拍板〕

回覆的完成證據必須和內容相符：仍在等相關工具／LLM 結果，或結果是 unknown，不能宣稱該工作成功。正式回覆依 [A-203](input.md)；模型說「完成」不能代替完成證據。沒有可推進的材料就結束本格，等所屬 kernel 再叫醒，不忙轉。

輪次邊界只沿用 [run 的軟性原則](../scheduling/runs.md)，不在這裡決定途中新訊息屬於哪一輪。重啟清程序依 [B-603](../settled/daemon/lifecycle.md)（標準配備的 daemon 端），unknown 與不自動重做依 [S-401](../scheduling/operations.md)。

驗收：模型回覆已完成，但相關工具還沒交回結果時，不把工作記成成功；等結果處理完且 final 提交後，才有正式完成回覆。

## A-504 按需啟動〔使用者方向 2026-09-29〕

扮演 agent 的 node 通常不設定期，等所屬 kernel 叫醒；登記與排程依 [daemon](../settled/daemon/README.md)，daemon 是定期跑 `aos-tick` 的標準程式，不是 agent 存在的前提（[B-626](../settled/tick.md)）：agent 也可以由 cron 或人手跑，只是沒有通道。沒有每 node 常駐 worker，也不靠空轉讀 history 找事做。

驗收：10,000 個閒置、沒有到期工作的 node，不因此產生 10,000 支 tick 程序或週期讀取整份 history。

## 舊條款去向

- A-501（09-29 重寫：已刪／併入[通用 tick](../settled/tick.md)與本頁預設任務。）
- A-502（09-29 重寫：已刪／併入[通用 tick](../settled/tick.md)；必要 agent 狀態見本頁。）
- A-505（09-29 重寫：已刪／併入[共通操作](../scheduling/operations.md)。）
- A-506（09-29 重寫：已刪／併入[通用 tick 的註冊任務](../settled/tick.md)。）
