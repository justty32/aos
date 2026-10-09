# brain 跨信記憶 意圖卡（r5，M1 隊）

← [intents](README.md)｜[brain 多回合卡](brain-multiround.md)｜起因 [longtask 問題 4](../play/2026-10-09-longtask/README.md)

**①解決什麼**：brain 換一封信就忘了前一封（11 號信問前件只能回「請貼原文」）。要讓「用 wf 記事」跨信有效，且**記憶在檔不在模型**。

**記在 wf 哪裡**：每封信結案時把回信全文存 `notes/done/<信 id>.md`（成果不摘），`notes/done/INDEX.md` 加一行「id｜標題｜一句話結論」；INDEX 只留 50 行，舊的搬 `INDEX-old.md`（檔數固定、不交 compact）。

**提示裡帶多少**：每回合固定附 INDEX（≤2 KB）；信提到前件（關鍵詞或「前面／你交的」對上 INDEX 一行）才附**一份** done 檔 ≤3000 字；AI 可回第四種格式「要檔案：<id>」下回合附（多一回合、不給工具）。超過 `max_prompt_chars`（預設 12000）先砍軌跡再砍技能全文，INDEX 永遠在。

**②必要的副作用**：寫 `notes/done/`、INDEX；prompts 多一段；status 不動（歸 LT）；只有「要檔案」多花一回合。

**③不做**：不做向量檢索、不給工具、不整份成果塞提示、不跨 node、不改 compact／prompt 包、QUICKSTART 零新概念。

**④對照現狀多出來的**：`notes/done/` 隨信累積 → **保留**（可選：超過 200 封打包）；「要檔案」格式、INDEX 輪替 → **保留**。

**驗收**：重跑 L 的 12 封：11 號回 DONE 且命中 01 號第 5 節關鍵詞 ≥2、不再 NEEDS-USER；每回合 prompt ≤ 上限；token 不比 L 跑 2 多 15%；寫 done 與寄 DONE 之間 SIGKILL ×3 不重寫不重寄。
