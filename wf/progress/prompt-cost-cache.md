# prompt-cost-cache：agent-fsm 每輪問模型的輸入成本：工具說明佔九成六、快取沒命中（what 欄全文，逐字）

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

11-20 晚家機 ~/aos-home 的 ann（sol）：think/request.json 53 KB 裡 tools 50.8 KB，問一句話 prompt_tokens 約 12.6k、cached_tokens 0。11-21 暫存樹實測（線 top-1121-skey）：sol 不加 session_key 4 輪快取都是 0；加 "session_key": "litellm_session_id" 第 2 輪起每輪命中 12,416（約 99%），4 輪沒中快取的 50,314 → 13,066。工具順序、system、對話前綴都穩定，原因就是沒寫這個鍵。續量（線 top-1121-skey2）：luna、terra、astra（chatgpt-gpt-6-astra，暫存樹新加一包）結果跟 sol 一樣；命中停在 12,416 是上游 128 一格、短句長不過下一格，長句會往上長。範本與活樹都沒改。 範本兩份與 ~/aos-home 已加 session_key、新增 astra 包（11-21）；使用者提：公開發佈時怕別人誤以為 aos 依賴 litellm（只記錄）。 工具說明（線 top-1121-tooldesc，11-21）：使用者選「只留一兩句＋指去知識庫」「self 只留兩支」，已施工：39 支說明改短、系統提示寫明知識庫在 $AOS_HOME/knowledge、agent-fsm 範本 self 只開 self_tools 與 self_state（36 支），sol 每輪 12,553 → 5,837 token（−53%）；全套測試沒有新紅。
