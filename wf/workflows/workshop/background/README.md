# workshop／background — 研討會背景資料索引

← [BACKGROUND（原路徑入口）](../BACKGROUND.md)｜[workshop](../README.md)｜[待答問題](../OPEN-QUESTIONS/README.md)

這份不是第八份結論，而是查表。先查名詞，再跳到要回答的題目；每個「目前」都以 `.aos` 資料夾規格 與 [roadmap](../../roadmap.md) 為準，研討會產生但尚未轉交進規格的東西一律標成「提案」。

> 2026-09-25 整理：〈分檔導航〉與〈名詞索引〉原本在 [BACKGROUND.md](../BACKGROUND.md)，該檔超過 8 KB，照「導航表超 8 KB 就往下一層放」兩節逐字搬來這裡。

## 分檔導航

| 檔案 | 裡面有什麼 |
|---|---|
| [回合、執行與喚醒](execution-and-turns/README.md) | world、`kernel.json`、`.runi`、tick 與 cursor 等回合執行詞彙；已拆成三份（回合邊界／回合開頭的固定步驟與版本／喚醒、進度與短路），逐詞索引見該資料夾 README。 |
| [工作、行程與 lane](work-and-lanes.md) | process、lane、job 與 promotion 的分界。 |
| [控制平面與生命週期](process-control.md) | root、control plane、capability、proc-table、join 與 handle。 |
| [投遞契約與追蹤](delivery-contract.md) | Publish、Deliver、correlation ID 與 receipt。 |
| [可靠性、冪等與持久化](reliability.md) | Effect、idempotency key、ledger、unknown、two-phase commit 與 durability。 |
| [Agent loop 與工具呼叫](agent-loop.md) | golden slice、agent loop、driver／adapter、tool allowlist 與 coding agent。 |
| [Agent 互通與上下文](agent-interop.md) | skill、MCP、façade、session 與 envelope。 |
| [工作流狀態與版本演進](workflow-state.md) | front matter、唯一真源、reconcile、ABI／schema 與 template 升級。 |
| [佇列、資源與同步](queues-and-resources.md) | Maildir、queue／spool／inbox、jobserver 與 DMA／fence。 |
| [題目導讀：方向與產品邊界](questions-direction.md) | 阻塞題第 1–3 題：痛點、近期範圍與第一個產品體驗。 |
| [題目導讀：宿主、安全與信任](questions-host-and-trust.md) | 阻塞題第 4–6 題：執行信任、第一個宿主與第一條可執行路徑。 |
| [題目導讀：Deliver 介面與契約](questions-deliver.md) | 阻塞題第 7–9 題：命令列形狀、key 與輸出／錯誤契約。 |
| [題目導讀：工作流狀態](questions-workflow-state.md) | 阻塞題第 10–11 題：狀態放哪裡，以及人如何修改。 |
| [題目導讀：外部效果與崩潰恢復](questions-reliability.md) | 阻塞題第 12–14 題：unknown、崩潰保證與斷電持久性。 |
| [題目導讀：工作流政策與演進](questions-workflow-policy.md) | 阻塞題第 15–17 題：完成歷史、template 更新與排程。 |
| [題目導讀：Agent 輸入、session 與工具面](questions-agent-context.md) | 阻塞題第 18、19、24 題：輸入上下文、續談狀態與公開工具集合。 |
| [題目導讀：子工作、等待與失敗](questions-child-work.md) | 阻塞題第 20–23 題：子工作提交、等待、失敗與核心步驟失敗。 |

## 名詞索引

- world／world folder → [回合邊界與崩潰現場](execution-and-turns/turn-boundary.md)
- process／核心行程／子行程 → [工作、行程與 lane](work-and-lanes.md)
- lane → [工作、行程與 lane](work-and-lanes.md)
- job／task／work item → [工作、行程與 lane](work-and-lanes.md)
- promotion → [工作、行程與 lane](work-and-lanes.md)
- root → [控制平面與生命週期](process-control.md)
- control plane → [控制平面與生命週期](process-control.md)
- capability → [控制平面與生命週期](process-control.md)
- proc-table／manager manifest → [控制平面與生命週期](process-control.md)
- `kernel.json` → [回合開頭的固定步驟與版本](execution-and-turns/boot-and-versioning.md)
- 彙整（aggregate）／取件（claim）／釋放（release） → [回合邊界與崩潰現場](execution-and-turns/turn-boundary.md)
- 角色表（role table）／`boot.json` → [回合開頭的固定步驟與版本](execution-and-turns/boot-and-versioning.md)
- 單一執行檔多子命令（busybox applet）／`/proc/self/exe` → [回合開頭的固定步驟與版本](execution-and-turns/boot-and-versioning.md)
- init(1)／reset vector → [回合開頭的固定步驟與版本](execution-and-turns/boot-and-versioning.md)
- Publish／commit／bundle → [投遞契約與追蹤](delivery-contract.md)
- Deliver／enqueue／handoff → [投遞契約與追蹤](delivery-contract.md)
- Effect／capture／invoke → [可靠性、冪等與持久化](reliability.md)
- idempotency key → [可靠性、冪等與持久化](reliability.md)
- correlation ID／request ID → [投遞契約與追蹤](delivery-contract.md)
- receipt／completion record → [投遞契約與追蹤](delivery-contract.md)
- no-replace／`renameat2(RENAME_NOREPLACE)` → [投遞契約與追蹤](delivery-contract.md)
- consumer acknowledgment → [投遞契約與追蹤](delivery-contract.md)
- TOCTOU → [投遞契約與追蹤](delivery-contract.md)
- ledger → [可靠性、冪等與持久化](reliability.md)
- `unknown` → [可靠性、冪等與持久化](reliability.md)
- two-phase commit → [可靠性、冪等與持久化](reliability.md)
- `.runi` → [回合邊界與崩潰現場](execution-and-turns/turn-boundary.md)
- 孤兒行程（orphan）／process group／`setpgid` → [回合邊界與崩潰現場](execution-and-turns/turn-boundary.md)
- running marker（起跑標記）／租約（lease） → [回合邊界與崩潰現場](execution-and-turns/turn-boundary.md)
- 短路（short-circuit）／`"needs"` → [喚醒、進度與短路](execution-and-turns/wake-and-progress.md)
- visibility atomicity／power-loss durability → [可靠性、冪等與持久化](reliability.md)
- terminal projection → [可靠性、冪等與持久化](reliability.md)
- golden slice → [Agent loop 與工具呼叫](agent-loop.md)
- agent loop → [Agent loop 與工具呼叫](agent-loop.md)
- driver／adapter → [Agent loop 與工具呼叫](agent-loop.md)
- tool allowlist → [Agent loop 與工具呼叫](agent-loop.md)
- coding agent → [Agent loop 與工具呼叫](agent-loop.md)
- 結構化輸出（`--output-schema`） → [Agent loop 與工具呼叫](agent-loop.md)
- skill → [Agent 互通與上下文](agent-interop.md)
- MCP → [Agent 互通與上下文](agent-interop.md)
- façade → [Agent 互通與上下文](agent-interop.md)
- session → [Agent 互通與上下文](agent-interop.md)
- envelope → [Agent 互通與上下文](agent-interop.md)
- tick／wake → [喚醒、進度與短路](execution-and-turns/wake-and-progress.md)
- cursor → [喚醒、進度與短路](execution-and-turns/wake-and-progress.md)
- front matter → [工作流狀態與版本演進](workflow-state.md)
- single source of truth／generated view／drift → [工作流狀態與版本演進](workflow-state.md)
- reconcile → [工作流狀態與版本演進](workflow-state.md)
- Maildir → [佇列、資源與同步](queues-and-resources.md)
- queue／spool／inbox → [佇列、資源與同步](queues-and-resources.md)
- GNU make jobserver → [佇列、資源與同步](queues-and-resources.md)
- DMA／staging buffer／doorbell／fence → [佇列、資源與同步](queues-and-resources.md)
- join／barrier／completion event → [控制平面與生命週期](process-control.md)
- handle／generation → [控制平面與生命週期](process-control.md)
- ABI／schema／golden files／conformance → [工作流狀態與版本演進](workflow-state.md)
- JSON Pointer → [工作流狀態與版本演進](workflow-state.md)
- plumbing／porcelain → [工作流狀態與版本演進](workflow-state.md)
- template／source version／base hash／three-way diff／doctor → [工作流狀態與版本演進](workflow-state.md)
