# 子世界：一個世界內可以有子世界，子世界的推進依賴主世界的 inst

← [ideas](README.md)

**使用者 2026-08-30 原話**：「一個世界內，可能會有子世界，子世界的推進依賴於主世界的 inst。」
記錄日期 2026-08-30。**方向是使用者的，尚未拍板細節；還沒派隊。**

## 一句話

子世界＝主世界資料夾底下另一個有 `.aos/` 的資料夾；它**自己不會動**，主世界的某條 inst
（例如 `aos run sub --step 1`）跑到時才推它一回合。推進的節奏、要不要推、推幾步，全由主世界的
指令決定——子世界是主世界的一顆「被呼叫的機器」。

## 現有機制能直接做到的

- 主世界 `.aos/every/sub.json`：`{"argv":["aos","run","sub","--step","1"]}` → 每回合推子世界一步。
- 用 `every_ms` 可以讓子世界跑得比主世界慢；用一次性 `aos deliver` 可以只推一步。
- `find_folder()` 往上找最近的 `.aos/`，所以在 `sub/` 裡下 `aos say` 找到的是子世界，不會誤指主世界。

## 使用者裁決（2026-08-30）

> 「子世界與否不用管太多，inst 內沒推進的就不管它。但子 agent 與否，那確實是要登記的。」

- **子世界不是一等公民**：沒有任何 inst 去推它，它就只是個資料夾——不鏡射、不追蹤、不設計管道。下面第 1、2、4 條**作廢**。
- **子 agent 不用「登記」，就是一份通訊錄**（使用者補充 2026-08-30：「也不用登記，反正就是類似 wf 的 inbox contact list」）：像 wf inbox 的 ROSTER／CONTACTS——誰是誰、住哪個資料夾（＝往哪投遞）。不是 schema、不是白名單，就是名字→地址。交給 tool 規劃隊：agent 的通訊錄跟 tool 登記表是兩份東西，別揉在一起。

## 還沒想的（給 tool 規劃隊）

1. 通訊錄住哪（world 級 `.aos/contacts.json`？）、欄位最少到什麼程度（name、folder 就夠？）、誰維護（`aos agent init` 自動加一行？）。
2. 子 agent 用哪顆 CPU、tools.json 要不要繼承父 agent 的。
3. 跟 [top-down-cli §三](top-down-cli.md)「把思考投遞到另一顆 llm pu 資料夾」是同一件事的兩種說法？——llm pu 也是一個子世界。

## 交接

- tool 規劃隊（待開）要把「子世界」當一種 tool 看：呼叫＝`aos run <sub>`／投遞到它的 inbox。
- 相關：[self-delivery-in-loop](self-delivery-in-loop.md)、[ai-core-field](ai-core-field/README.md)（unipath 的路徑樹可能是同一個直覺）。
