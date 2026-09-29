# 任務與排程

← [規格入口](../README.md)｜[共用契約](../contracts.md)

本層決定執行機會與額度，不替 agent 選工具，也不取代基底的 UID／cgroup 強制限制。所有具體政策為建議預設，尚未拍板。

- [任務、claim 與恢復](runs.md)：輪次、單寫者、取消、遲到結果。
- [ready／due 與准入](admission.md)：增量取件、名額、公平、冷資料。
- [LLM 共享額度](llm.md)：預留、限流、未知結果、用量結算。
- [觀測與操作](operations.md)：查詢、人工解決、保留（跟著 tick 清）、待處理資料夾與驗收。
