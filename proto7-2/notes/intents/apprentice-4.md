# 學徒自我改進對照實驗 意圖卡（AP4）

← [intents](README.md)｜上一輪 [apprentice-3x](apprentice-3x.md)

**①解決什麼**：證明學徒「做第 N 件事時用上自己前面留下的技能，所以做得更好」。A 組每題全新開始；B 組連做，每題後自己寫一本技能（坑＋驗過的骨架），下一題 propose 用 skills 本機挑出來放進提示。學徒換成較弱的 `chatgpt-gpt-6-luna`（試跑 6/6 第一輪就卡在候選格式），同三題、同模型，每組 ≥3 次，比通過率、輪數、token、三關失敗次數。

**②必要的副作用**：暫存學徒 node `/tmp/ap4-node`（budget 帳＋llmcall 紀錄，收尾刪）；真 AI 呼叫（學徒 luna、審查 astra-high、全走 llmcall 記帳）；三關沙箱；證據存 `evidence/apprentice4/`。

**③不做**：不發布 `apprentice/` 分支（「過」＝propose 三關含審查都過）；不給答案檢查器；不改 skills 挑書規則；不改 LiteLLM。

**④對照現狀多出來的**：
- `propose --skills <node>`：用 aos7-skills 本機挑一本，全文放進提示 → **保留**（不給＝與現在相同）。
- `learn --skill-into <node> --skill <名>`：學徒把這題的坑與驗過的骨架寫成整本 SKILL.md（≤8 KiB，格式不合就不寫） → **保留**。
- 第 1 關 schema／json 訊息寫明缺哪欄、多哪欄、多餘內容在哪 → **保留**（兩組都受益，不偏袒）。
