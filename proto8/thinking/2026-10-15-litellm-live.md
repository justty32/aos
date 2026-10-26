# 2026-10-15 proto8 新架構用 LiteLLM（GPT 類）實跑

← [thinking](README.md)｜上一次真腦：[報時員實跑](2026-10-15-clerk-live.md)、[判官實跑之二](2026-10-15-judge-live2.md)

**原文**：使用者 10-15 開了本機 LiteLLM proxy，要用它（盡量 GPT 類）實跑 proto8 新架構（定義資料夾＋frame）的 agent。

**結論（AI 整理）**：fsm demo、報時員兩層真腦、同 frame 續跑、boss 叫 clerk、腦連錯、kernel agent 判官都跑通；tool_calls 形狀全對、全程繁體中文，比 LM Studio Qwen3-1.7B 快且穩（clerk 真的叫 clock、沒編時間）。GPT 類判官合法、照規則（human 先、8 封全服務完）。

**挖到的問題**（5 題，拍板見下節）

1. **綁定不往下傳**：外層 frame 換了腦，叫出去的子 agent 還是用定義裡的腦；「工具在子 frame 放什麼」牽涉 C-46 綁定語意。
2. **判官腳本寫死 `parent` 是 judge/**，換腦只能改定義或抄一份腳本。
3. **平行 tool_calls 第二個被 `Skipped`**，GPT 類很常一次發多個；模型看到 Skipped 只會說「沒成功」，不會自己重叫。
4. **halted 時 loop 退出碼 0、state `done`**，呼叫方只能看 `ret.json` 有沒有 `error`。
5. proxy 每次多塞約 1600 prompt tokens（codex 後端），LLM kernel 的 token 額度會被放大。

## 拍板（10-15）

**原文**：使用者對上面 5 題與畫家 demo 兩個自定點「**都按照推薦**」；第 4 題照他的新原則（C-52「只管自己這一層」，見 CONCEPTS）改成維持現狀，他回「**都同意。**」。

1. **換腦只換那一層**：子 agent 沿自己 frame 往上找，不看呼叫方；要換子 agent 的腦就在它的 frame 放 `brain.json`。
2. **判官腳本收定義資料夾當引數**（沒給＝`judge/`）；換腦＝另開資料夾放 `brain.json`，指回 `judge/`。
3. **多個 tool_calls 一拍照順序跑完**，每個回對應 id；沒有 `Skipped`。
4. **halted 時 loop 照舊退 0**（C-52），外面看 `ret.json` 的 `error`。
5. **proxy 多塞 token**：不處理。

畫家 demo：畫家想到才把畫筆當工具叫＝維持；`brain.json` 只換那一層＝維持（同 1）。
