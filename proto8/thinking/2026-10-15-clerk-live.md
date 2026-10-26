# 2026-10-15 報時員（agent 當工具）用 LM Studio 實跑

← [thinking](README.md)｜前一次 LM Studio：[topics §9](2026-10-15-topics/03-試146-qwen與LM-Studio.md#9-試-lm-studioqwen3-17b)

**原文**：使用者 10-15「用 LM Studio 實跑一次報時員」。

**結論（AI 整理）**：Qwen3-1.7B 當外層與報時員的腦，端到端跑得通；tool_calls 形狀正確、一次只叫一個工具，兩層都照 system.md 回繁體中文一句話。

**邊緣狀況**
- **小模型有時不用工具、直接編答案**：clerk 的 system.md 寫了「用 clock 查，不要自己猜」仍會發生；外層看不出（回的格式一樣、只有 ticks 少）。
- 真腦一趟 16～20 秒，demo `loop.json` 的 20 秒逾時對真腦太緊。

**決定**：10-15 使用者「隨意」→ 先不處理小模型（Qwen3-1.7B）不查 clock 就編答案的問題；proto8 接受此限制。日後要治時的候選：加強提示、換大模型、在表上強制「沒叫過工具不准回答」（環境保證，C-22b 思路）。
