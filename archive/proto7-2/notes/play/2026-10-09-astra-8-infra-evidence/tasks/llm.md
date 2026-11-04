# 子線 llm：llmcall／budget／metrics／diag／prompt／author／step

線名 `llm`。範圍：
- `packs/llmcall/`（真傳輸 `aos7_llmcall_litellm.py`、假傳輸、退出碼 0～4、adopt、恢復）、`packs/budget/`（部分結算、overrun、cancel unknown）、`packs/prompt/`、`packs/author/`（第一／二刀、aos 學徒、三關、publish）、`packs/step/`。
- `modules/metrics/`（吸收 usage：`job --by`、`--detail`／`--json`、`ledger()`）、`modules/diag/`（吸收 llmdiag：`aos7-diag --llm`）；`archive/usage`、`archive/llmdiag` 與轉址 stub（`packs/usage/bin/aos7-usage`、`modules/llmdiag/aos7-llmdiag`）——吸收後行為／欄位／退出碼與原版和文件一致嗎？stub 退 1 是否與錯誤路徑慣例衝突？
- 一致性：同一筆呼叫在 llmcall 回條、budget ledger、metrics 統計、diag 列表、author job 裡，數字（token、成本、重試、狀態詞）是否對得上；metrics 是否仍把多回合當重試（longtask 報告）；token 單位（加權成本 vs token）各處是否一致。
- 錯誤路徑：真傳輸的網路錯誤、逾時、HTTP 4xx/5xx、回應壞 JSON、choices 空，分別落到哪個退出碼／狀態，和 spec、error_path.json、budget 的 unknown 規則一致嗎？
- 副作用：metrics／diag 號稱唯讀，是否真的不寫、不拿會擋人的鎖。
