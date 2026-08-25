# 研討會背景資料
← [workshop](README.md)｜[待答問題](OPEN-QUESTIONS.md)

這份不是第八份結論，而是查表。先查名詞，再跳到要回答的題目；每個「目前」都以 [`.aos` 資料夾規格](../../../docs/aos-folder.md) 與 [roadmap](../../../docs/roadmap.md) 為準，研討會產生但尚未轉交進規格的東西一律標成「提案」。

## 分檔導航

| 檔案 | 裡面有什麼 |
|---|---|
| [回合、執行與喚醒](background/execution-and-turns.md) | world、`kernel.json`、`.runi`、tick 與 cursor 等回合執行詞彙。 |
| [工作、行程與 lane](background/work-and-lanes.md) | process、lane、job 與 promotion 的分界。 |
| [控制平面與生命週期](background/process-control.md) | root、control plane、capability、proc-table、join 與 handle。 |
| [投遞契約與追蹤](background/delivery-contract.md) | Publish、Deliver、correlation ID 與 receipt。 |
| [可靠性、冪等與持久化](background/reliability.md) | Effect、idempotency key、ledger、unknown、two-phase commit 與 durability。 |
| [Agent loop 與工具呼叫](background/agent-loop.md) | golden slice、agent loop、driver／adapter、tool allowlist 與 coding agent。 |
| [Agent 互通與上下文](background/agent-interop.md) | skill、MCP、façade、session 與 envelope。 |
| [工作流狀態與版本演進](background/workflow-state.md) | front matter、唯一真源、reconcile、ABI／schema 與 template 升級。 |
| [佇列、資源與同步](background/queues-and-resources.md) | Maildir、queue／spool／inbox、jobserver 與 DMA／fence。 |
| [題目導讀：方向與產品邊界](background/questions-direction.md) | 阻塞題第 1–3 題：痛點、近期範圍與第一個產品體驗。 |
| [題目導讀：宿主、安全與信任](background/questions-host-and-trust.md) | 阻塞題第 4–6 題：執行信任、第一個宿主與第一條可執行路徑。 |
| [題目導讀：Deliver 介面與契約](background/questions-deliver.md) | 阻塞題第 7–9 題：命令列形狀、key 與輸出／錯誤契約。 |
| [題目導讀：工作流狀態](background/questions-workflow-state.md) | 阻塞題第 10–11 題：狀態放哪裡，以及人如何修改。 |
| [題目導讀：外部效果與崩潰恢復](background/questions-reliability.md) | 阻塞題第 12–14 題：unknown、崩潰保證與斷電持久性。 |
| [題目導讀：工作流政策與演進](background/questions-workflow-policy.md) | 阻塞題第 15–17 題：完成歷史、template 更新與排程。 |
| [題目導讀：Agent 輸入、session 與工具面](background/questions-agent-context.md) | 阻塞題第 18、19、24 題：輸入上下文、續談狀態與公開工具集合。 |
| [題目導讀：子工作、等待與失敗](background/questions-child-work.md) | 阻塞題第 20–23 題：子工作提交、等待、失敗與核心步驟失敗。 |

## 名詞索引

- world／world folder → [回合、執行與喚醒](background/execution-and-turns.md)
- process／核心行程／子行程 → [工作、行程與 lane](background/work-and-lanes.md)
- lane → [工作、行程與 lane](background/work-and-lanes.md)
- job／task／work item → [工作、行程與 lane](background/work-and-lanes.md)
- promotion → [工作、行程與 lane](background/work-and-lanes.md)
- root → [控制平面與生命週期](background/process-control.md)
- control plane → [控制平面與生命週期](background/process-control.md)
- capability → [控制平面與生命週期](background/process-control.md)
- proc-table／manager manifest → [控制平面與生命週期](background/process-control.md)
- `kernel.json` → [回合、執行與喚醒](background/execution-and-turns.md)
- init(1)／reset vector → [回合、執行與喚醒](background/execution-and-turns.md)
- Publish／commit／bundle → [投遞契約與追蹤](background/delivery-contract.md)
- Deliver／enqueue／handoff → [投遞契約與追蹤](background/delivery-contract.md)
- Effect／capture／invoke → [可靠性、冪等與持久化](background/reliability.md)
- idempotency key → [可靠性、冪等與持久化](background/reliability.md)
- correlation ID／request ID → [投遞契約與追蹤](background/delivery-contract.md)
- receipt／completion record → [投遞契約與追蹤](background/delivery-contract.md)
- ledger → [可靠性、冪等與持久化](background/reliability.md)
- `unknown` → [可靠性、冪等與持久化](background/reliability.md)
- two-phase commit → [可靠性、冪等與持久化](background/reliability.md)
- `.runi` → [回合、執行與喚醒](background/execution-and-turns.md)
- visibility atomicity／power-loss durability → [可靠性、冪等與持久化](background/reliability.md)
- golden slice → [Agent loop 與工具呼叫](background/agent-loop.md)
- agent loop → [Agent loop 與工具呼叫](background/agent-loop.md)
- driver／adapter → [Agent loop 與工具呼叫](background/agent-loop.md)
- tool allowlist → [Agent loop 與工具呼叫](background/agent-loop.md)
- coding agent → [Agent loop 與工具呼叫](background/agent-loop.md)
- skill → [Agent 互通與上下文](background/agent-interop.md)
- MCP → [Agent 互通與上下文](background/agent-interop.md)
- façade → [Agent 互通與上下文](background/agent-interop.md)
- session → [Agent 互通與上下文](background/agent-interop.md)
- envelope → [Agent 互通與上下文](background/agent-interop.md)
- tick／wake → [回合、執行與喚醒](background/execution-and-turns.md)
- cursor → [回合、執行與喚醒](background/execution-and-turns.md)
- front matter → [工作流狀態與版本演進](background/workflow-state.md)
- single source of truth／generated view／drift → [工作流狀態與版本演進](background/workflow-state.md)
- reconcile → [工作流狀態與版本演進](background/workflow-state.md)
- Maildir → [佇列、資源與同步](background/queues-and-resources.md)
- queue／spool／inbox → [佇列、資源與同步](background/queues-and-resources.md)
- GNU make jobserver → [佇列、資源與同步](background/queues-and-resources.md)
- DMA／staging buffer／doorbell／fence → [佇列、資源與同步](background/queues-and-resources.md)
- join／barrier／completion event → [控制平面與生命週期](background/process-control.md)
- handle／generation → [控制平面與生命週期](background/process-control.md)
- ABI／schema／golden files／conformance → [工作流狀態與版本演進](background/workflow-state.md)
- template／source version／base hash／three-way diff／doctor → [工作流狀態與版本演進](background/workflow-state.md)
