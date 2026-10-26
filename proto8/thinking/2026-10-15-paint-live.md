# 2026-10-15 畫家 demo 用 LiteLLM 真腦實跑

← [thinking](README.md)｜前一次：[LiteLLM 實跑](2026-10-15-litellm-live.md)

**原文**：使用者 10-15 要用本機已開的 LiteLLM proxy 把畫家 demo 的真腦路徑實跑一遍，確認行為跟 README 一致；demo 自己的設定問題就修，lib 層的只記錄。

**結論（AI 整理）**：行為全部跟 README 一致，沒有要修的 demo 設定，也沒有新的 lib 問題。

- 畫家叫畫筆、畫筆叫調色盤，三層巢狀跑通；同 frame 續聊時畫筆每次在新的 `work/<n>/`、全新對話；定義資料夾不變。
- 腦連錯＝halted → done，loop 退 0，錯寫進 `ret.json`（帶 proxy 原話）——是已拍板行為（C-52）。
- tool 訊息內容是整份 inst 結果 JSON（不只 result），模型照用沒問題。
- 真腦會把 ASCII 畫包在 ```` ```text ```` 圍欄裡，`ret.json` 的 reply 就帶著圍欄。
- proxy 的 codex 後端自己的身分會蓋過畫家的 system.md（問「你是誰」回 Codex）。
- 問不相干的問題也會叫畫筆，是 `system.md`「先用 brush」的設計，不是 bug。
