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

## 還沒想的（挖出來給使用者判斷，不代答）

1. 子世界的 `state.json` 要不要鏡射進主世界的 `state.json`（像 agents 那樣一段），主世界才看得到「子世界在跑什麼」。
2. 子世界要跟主世界講話的管道：投到主世界 `inbox/`（子世界知道父路徑嗎？`AOS_FOLDER` 只給自己的）。
3. 子世界的 agent 用哪顆 CPU、tools.json 要不要繼承主世界的。
4. 遞迴深度與同名 id 撞在 `batch/` 裡的問題（先不管）。
5. 跟 [top-down-cli §三](top-down-cli.md)「把思考投遞到另一顆 llm pu 資料夾」是同一件事的兩種說法？——llm pu 也是一個子世界。

## 交接

- tool 規劃隊（待開）要把「子世界」當一種 tool 看：呼叫＝`aos run <sub>`／投遞到它的 inbox。
- 相關：[self-delivery-in-loop](self-delivery-in-loop.md)、[ai-core-field](ai-core-field/README.md)（unipath 的路徑樹可能是同一個直覺）。
