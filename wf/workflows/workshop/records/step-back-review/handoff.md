# 轉交提案（未拍板，不自行改規格／roadmap）

← [三場研討會的回頭審視](README.md)

1. **近期 scope 回撤。** 近期 core 候選只留最小 Deliver；公開 Publish、通用 Effect、lane／proc-table／
   capability／promotion／UUID／generation／join／分層 kernel 全部退回「有實測觸發條件再重開」。
   會改變前兩場的 roadmap／規格方向，要使用者確認。

2. **最小 Deliver 的誠實契約。** 只承諾 schema／大小檢查、唯一同目錄 temp、write-all、rename 入 queue；
   不承諾沒有 ledger 支撐的跨回合 Already／Conflict。待使用者定：CLI 名稱、BASE／world 傳法，
   以及只保 rename 可見性還是另有 fsync 選項。

3. **指定 T5 的第一支真 LLM CLI 與最小 golden slice。** 單一 world、單一串行工具、模型→工具→模型
   三回合；driver／adapter 先是腳本，prompt／response／result 檔名先是實驗格式，不升成 core ABI。

4. **先定威脅模型，再讓模型碰工具。** 待使用者定：T5 是全信任實驗，還是會碰真實檔案、網路與憑證。
   首版至少採具名工具 allowlist 與固定 argv；未知工具停住。人工核准或 sandbox 要不要立即做，看這個拍板。

5. **定義 crash 測試承諾。** Ctrl-C、hard kill、斷電分開，不混稱「可恢復」；逐點 kill 並記錄 `.runi`、
   temp、已 rename 結果與人工處置。第一輪可以只觀察，不先承諾自動恢復。

6. **「有證據才升 core」的重開門檻。** 兩支腳本重複同一發布交易 → 考慮公開 Publish；兩個 provider
   adapter 重複同一 unknown 狀態機 → 考慮 Effect；第二個長壽 world／共享 writer 出現 → 重開行程機制；
   平行工具成為實際需求 → 談 join／barrier；stale receipt 真出現 → 加 generation／ledger。

7. **三份舊紀錄先維持歷史，不直接當規格。** 本輪審視拍板後，再把保留／撤回項轉交 roadmap 或規格；
   在那之前，[核心行程紀錄](../core-process-and-subprocess.md)、[四個選擇紀錄](../four-open-choices-tradeoffs.md)、
   [agent loop 紀錄](../agent-loop-architecture.md)都只是研討產出，不改寫成新真源。
