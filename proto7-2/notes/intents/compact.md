# compact 意圖卡

← [intents](README.md)｜[包 README](../../modules/compact/README.md)

**①解決什麼**：記憶檔（SESSION-LOG、journal）太厚時，舊的先封存再換成一則摘要；open 項與最近 N 則不丟。

**②必要的副作用**：寫 `<node>/compact/`（state、pending、archive、log、鎖）；原子覆寫被整理的記憶檔（原文在 archive）；有設 llm 時經 llmcall 問一次 AI（真模型＝花錢）；`watch` 當 keep 任務等 tock。

**③不做**：預設不摘現役段與 open（只有人明講 `forget` 或 `--include-open` 才動它們，程式照做、不自作主張）；不自己裝任務；不刪 archive。

**④多出來的（現狀）**
- 「不需要整理」也寫 `compact/state.json` → **移除**：沒動檔就不寫。
- 只要 `<node>/events/` 存在就發 `compact.done` 事件，發不出整次退 1 並留 pending → **改成可選**：`compact.json` 的 `events` 預設關；開了也只記 log，不讓整理算失敗。
- 掃使用者資料夾裡的 `.<檔>.compact-tmp` → **保留**（自己的暫存，寫者清）。
