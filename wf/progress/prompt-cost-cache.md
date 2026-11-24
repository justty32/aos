# prompt-cost-cache：agent-fsm 每輪問模型的輸入成本；aos 這側能修的都修完了，剩 B～E 四個方案等使用者定

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## 11-22 傍晚的現況（線 progress-1122-sweep 對 commit 補的）

- 重量過了（`907ddecc9`，線 prompt-cost-1122）：「九成六是工具說明、快取沒命中」是 11-20 的舊數字。今天 HEAD 的起手 ann 問一句話約 6,225 token（工具 4,199、instructions 2,011、對話 15）；前綴每輪逐字穩定，aos 這側沒有不改行為就能修的快取問題；沒中的大頭是上游偶發整段沒中（約 18% 的後續輪）。
- 選項 A（讓上游拿到快取鍵）實驗過，無效，aos 改動不交、正式 LiteLLM 不用套 patch（`22501d7af`，線 prompt-cache-key-1122）。
- 原本 next 寫的「等別線交了補」兩件，11-21 已做：self_llm 說明含 reasoning_effort、範本文件改成 36 支（`949925842`，線 top-1121-chore）。
- 原本 next 寫的「使用者跑 install.py、把 ann 的 tools.json 與 system.txt 抄到 `~/aos-home/agents/ann`」不用做了：install.py 11-21 起跑過多次；11-22 搬家時舊樹的 ann 照使用者「舊樹的不搬」沒搬進 `_stack`（[工作區與stack-1122](../../proto8/thinking/2026-11/22/工作區與stack-1122/README.md)），`~/aos-home` 往後只裝 llm kernel。範本 `templates/starts/start-api` 的 ann 已是新版，用它起的新樹就吃得到。
- 剩：B（縮短 LiteLLM 自動加的 codex 指示）、C（再縮預設工具）、D（自加的工具排最後，推薦不做）、E（都不做）要使用者定，見 [prompt-cost-1122「要你定的」](../../proto8/thinking/2026-11/22/prompt-cost-1122/README.md#要你定的)。

## 11-21 以前（what 欄原文，逐字）

11-20 晚家機 ~/aos-home 的 ann（sol）：think/request.json 53 KB 裡 tools 50.8 KB，問一句話 prompt_tokens 約 12.6k、cached_tokens 0。11-21 暫存樹實測（線 top-1121-skey）：sol 不加 session_key 4 輪快取都是 0；加 "session_key": "litellm_session_id" 第 2 輪起每輪命中 12,416（約 99%），4 輪沒中快取的 50,314 → 13,066。工具順序、system、對話前綴都穩定，原因就是沒寫這個鍵。續量（線 top-1121-skey2）：luna、terra、astra（chatgpt-gpt-6-astra，暫存樹新加一包）結果跟 sol 一樣；命中停在 12,416 是上游 128 一格、短句長不過下一格，長句會往上長。範本與活樹都沒改。 範本兩份與 ~/aos-home 已加 session_key、新增 astra 包（11-21）；使用者提：公開發佈時怕別人誤以為 aos 依賴 litellm（只記錄）。 工具說明（線 top-1121-tooldesc，11-21）：使用者選「只留一兩句＋指去知識庫」「self 只留兩支」，已施工：39 支說明改短、系統提示寫明知識庫在 $AOS_HOME/knowledge、agent-fsm 範本 self 只開 self_tools 與 self_state（36 支），sol 每輪 12,553 → 5,837 token（−53%）；全套測試沒有新紅。
