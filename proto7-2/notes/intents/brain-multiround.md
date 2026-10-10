# brain 多回合 意圖卡（r4，B5 隊）

← [intents](README.md)｜[up 卡](up.md)｜計畫 plan-2026-10-09-r4（已封存）

**①解決什麼**：現在 brain 一回合只處理一封信、一問一答就結案。目標 1 要的是「AI 真的用 wf 管自己跑一段長任務」：一封信可能要跑很多回合，中間會記續行點、會整理記憶、會挑技能、會回報進度。

**②必要的副作用**：每回合讀寫自己 node 的 `wf/handoffs/<日>/STATE.md`（續行點）與 `wf/SESSION-LOG.md`（這件事的 open 一行，做完即刪）；每 N 回合寄一封 PROGRESS 給寄件者、卡住寄 NEEDS-USER、做完寄 DONE；記憶檔超過門檻就呼叫 `aos7-compact now`（可能花一次 AI 錢）；挑技能呼叫 `aos7-skills pick`（預設本機關鍵字、不花錢）；每回合最多一次 llmcall。

**③不做**：不給 AI 工具（仍是「資料都附在下面、直接回答」）；不改 QUICKSTART 的五個詞三個指令；不做多 node 協作；不自動重送 unknown（照 llmcall 退 3 同 call 接續）；不改 lib/。

**④對照現狀多出來的**：
- 跨回合的任務狀態檔（STATE.md 一行＋`brain/task.json`）→ **保留**（這就是目標）。
- compact 由 brain 觸發 → **改成可選**（`up.json` 的 `compact: true` 預設開，但只在記憶檔超門檻時）。
- PROGRESS 信會讓人的信箱多信 → **保留**，但 N 預設 5 回合且可關。
