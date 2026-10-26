← [回入口](../2026-10-15-topics.md)｜上一份：[02-agent工具與試146](02-agent工具與試146.md)｜下一份：[04-agent當函數](04-agent當函數.md)

## 8. 試 146 ollama：qwen2.5:14b

**原文**：「試試看 qwen2.5:14b」（主對話親口；ops-notes 同時監控）。

**結果**：qwen2.5:14b 第一次對真模型把 idle → thinking → tool → thinking → idle 整圈跑通，`tool_calls` 形狀正確（ollama 沒給 id，腦自己編）。

**挖到的邊緣狀況**
- 帶 tools 時回覆語言亂跳（泰文、韓文），沒帶工具結果的那題正常中文；history 沒有 system 訊息（→ §10 加系統提示，例「用繁體中文回答」）。
- CPU：qwen 雖全在 GPU，整機 CPU 仍被吃滿；ops-notes 要求暫停，見 [dev-env](../../../wf/workflows/dev-env.md)。
- 第一次叫腦含載入約 15 秒：loop 的 20 秒逾時不夠。

## 9. 試 LM Studio：Qwen3-1.7B

**原文**：使用者允許在公司這台用 LM Studio 試 agent（「可以」）；同時定「那就都用本地的就好，別碰146」——146 不再使用，一律用本地（[dev-env](../../../wf/workflows/dev-env/01-跨機與外部工具.md#跨機--離線差異)）。

**結果**：Qwen3-1.7B 叫 clock 回對時間、中文；不需要工具的題目沒叫工具。tool_calls 形狀正確（LM Studio 給 32 字的亂數 id、arguments `"{}"`、content `""`）。`<think>` 沒漏進 content：LM Studio 把想的字放在另一個欄位 `reasoning_content`，腦只取 `content`，所以 history 乾淨。跟 qwen2.5:14b 比語言沒亂跳，延遲多花在「想」。

**挖到的邊緣狀況**
- `reasoning_content` 被丟掉（→ §10 一律丟）。
- 「想」佔 token 也佔時間：沒設 `max_tokens` 時一題 4～8 秒；要設上限得 1500 以上，不然想完就沒字可回。
- LM Studio `--ttl 600` 閒 10 分鐘會自己卸模型，但 server 不會自己關——試完一定手動關。

## 10. 丟掉想的內容、加系統提示

**原文**：使用者（10-15）看完 §9 的邊緣狀況後說「（模型想的內容）丟掉。加上系統提示。」

**決定**
- `reasoning_content` 等想的字**一律丟**，腦只留 `content`／`tool_calls`，不另存。
- agent 設定加選填 `system`＝系統提示檔路徑（沿用 [07 §12.1](../2026-10-14-json-entry/07-fsm樹與一拍.md) 的 `"system":"system.md"` 想法）。think 每次叫腦在 messages 最前面插 system 訊息，**不進 history**（改檔下一拍生效）；沒寫＝不帶；檔讀不了＝`SystemUnreadable`（N-29）。
- 假腦不理 system。
