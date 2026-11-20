B 題之三：同一個事件名，在 agent-fsm 與 eca（aos-eca-turn＋aos-mcp）兩種身體裡行為差在哪，逐事件列表；最後一格是看程式推的疑點。

← [04](04-B2-誰假設只有這九種.md)｜下一份 [06 形狀甲乙丙](06-C1-形狀甲乙丙.md)

## 結論

九種事件名兩種身體共用一張表，但**同名行為明顯不同的有 5 種**（before_queue、after_queue、before_tool、after_tool、brain_failed），tool_added、on_clock 只差時機與頻率：觸發範圍、失敗時停不停、能改的怎麼放回、事件欄位，都可能不同。哪種身體怎麼做只寫在文件（`06-hook.md:133-145`）與 eca 範本的 hooks.json 說明，表裡沒有。

## 逐事件

| 事件 | agent-fsm | eca | 差在哪 |
|---|---|---|---|
| before_queue | idle 每封好信（`idle.py:176`）；**`/compact` 信不過這個 hook**（`:170-175` 先挑走） | 每封好信（`eca/turn.py:64`），**slash 信也過**；等回答時又來的信也過（`eca/midturn.py:41`） | 哪些信會被看到不同 |
| after_queue | 信進 history、收掉之後；**失敗當場退 1** | 交給 CLI 那刻接進 history 後；**失敗等回答接進 history 才報**（`eca/handoff.py:41-45`）；slash 一輪也跑（`slash.py:342`） | 失敗時機不同 |
| before_tool | act 跑**每一支**工具之前（`act.py:183`） | **只有經 aos-mcp 叫的 aos 工具**（`mcp/main.py:247`）；CLI 自己的 Read、Bash… 看不到 | 範圍不同 |
| | hook 失敗（on_error stop）＝**這格退 1、agent 停** | hook 失敗＝**那次工具呼叫回 isError，CLI 照樣往下**（`mcp/main.py:235-239`） | `on_error: stop` 的意思不同 |
| | 改了參數：只交工具，history 裡的 tool_calls 不動 | 改了參數：交工具；CLI 那邊記的是它原本送的 | 大致同 |
| after_tool | 永遠拿回 content（`act.py:238-239`） | 只有 hook 改了才換、多段併成一段（`mcp/main.py:264-267`） | 結果的形狀可能變 |
| brain_failed | `name`＝LlmKernelMissing、SendFailed、BudgetMissing、BrainFailed、ReplyBad；欄位 `reason`，有時加 `error`、`retry`、`wait_s`、`attempt`… | `name`＝CliFailed、ReplyMissing；claude 加 `code`、`retry`、`attempt`、`dropped`、`wait_s`、`status`、`cause`；codex 只有 `name`、`reason` | 代號與欄位不同（`brain_notify` 靠有沒有 `dropped` 分兩種講法） |
| tool_added | think 每次組請求時比名單 | 每輪交出去之前比；有這種 hook 才多叫一次 `aos-tools ls` | 時機略不同 |
| after_start／after_stop | loop.json 的 on_start／on_stop → hook_fire | 同 | 同 |
| on_clock | **每格開頭**都看一次時鐘（一圈最多四次） | 每輪開頭一次（冷卻、退讓的那輪也看） | 檢查頻率不同；到了才起行程，所以結果大致同 |

## 跟你第 1 點的關係

「每次 loop 的時候都會觸發」最接近的是 on_clock 配 `every_cycles: 1`，但它數的是**時鐘的格數**（daemon 的鐘），不是 loop 的圈數；fsm 一圈裡四格各看一次，eca 一輪看一次。現在沒有「每圈一次」的事件（aos-compile-base-1120 [01](../aos-compile-base-1120/01-現況-定義夾有哪幾種.md) 第 35 行也記了這點）。

## 看程式推的疑點（沒實跑，不確定）

- **eca 等回答時來的 slash 信可能過兩次 before_queue**：`midturn.py:41` 先過 hook，`:44-46` 看到是 slash 就停下、不收這封；下一輪 `turn.py:64` 會再過一次。hook 第一次改的 content 沒留下，計數型的 hook 會算兩次。要不要查證列在 D。
