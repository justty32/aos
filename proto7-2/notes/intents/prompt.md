# prompt 意圖卡

← [intents](README.md)｜[包 README](../../packs/prompt/README.md)

**①解決什麼**：照一張清單現讀現拼出要給 AI 看的請求；太長的段自動收起來省 token，要看再展開。

**②必要的副作用**：有段落超過門檻才寫 `<node>/refs/<sha>.json`（內容定址、相同不重寫；展開要靠它）；`--out` 寫一個檔。不鎖、不起程序、不連網、不問 AI。

**③不做**：不送請求、不碰 llmcall／budget、失敗不輸出半份。

**④多出來的（現狀）**：零。`refs/` 只增不清——**保留**，但 README 加一句「refs/ 可整夾刪，只影響舊請求的展開」。
