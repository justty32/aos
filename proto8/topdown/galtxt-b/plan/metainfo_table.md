# galtxt-b `_metainfo` 表

由 `plan/metainfo_table.py` 產生（不要手改）。數量欄寫 `val/max`；實測欄 `題:值`（q01_河鹿堂讓書、q08_河鹿堂進新書日）。

| 路徑 | kind | summary | resource | time_ms | 實測 time_ms | llm_calls | 實測 llm_calls | llm_tokens | 實測 llm_tokens | det | side | interrupt | parallel | 其他 key | 超過 max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| . | fn | galtxt-b：工作區 new/<題名>.json 的場景（兩人、一地、一事、意圖）→ out/<… | llm、cpu | 26000/900000 | q01:19321 q08:13748 | 3/11 | q01:5 q08:4 | 7000/45000 | q01:23074 q08:17485 | false | true | resumable | true | grow_level、idempotent、llm_endpoint、llm_model、lock、per_questi… |  |
| brief | fn | 認領一題場景 JSON，查 tables/ 編成稿紙 brief.json（人物卡、稱謂階、地點硬設… | cpu、disk | 60/2000 | q01:20 q08:20 |  |  |  |  | true | true | safe | false | grow_level、idempotent、reads、tier、writes |  |
| brief/tables | data | brief 查的規則表：人物卡、稱謂階、地點卡、禁語、開場收尾句、samples.json（語料錨：… | disk |  |  |  |  |  |  | true | false |  |  | refresh、source |  |
| check | fn | 黏合格：叫 tools/lint 拿 violations（Tier 0 護欄、Tier 1 語域）… | cpu | 80/2000 | q01:45 q08:44 |  |  |  |  | true | true | safe | false | calls、grow_level、idempotent、reads、tier、writes |  |
| check/tools/lint | link | 捷徑 → ../../lib/lint |  |  |  |  |  |  |  |  |  |  |  |  |  |
| check/tools | dir | check 格叫的工具：lint（相對捷徑指 lib/lint） |  |  |  |  |  |  |  |  |  |  |  |  |  |
| deliver | fn | 有 score.json 就交件：寫 $AOS_WS/out/<題名>/{answer.txt,sc… | cpu、disk | 20/1000 | q01:0 q08:0 |  |  |  |  | true | true | resumable | false | grow_level、idempotent、note、reads、writes |  |
| draft | fn | 黏合格，兩步：沒 plan.json 先叫 tools/director 出 beat 表、tool… | llm、cpu | 16000/600000 | q01:16632 q08:11280 | 2/5 | q01:4 q08:3 | 4300/15000 | q01:19459 q08:13925 | false | true | resumable | false | calls、grow_level、idempotent、llm_endpoint、llm_model、note、read… | q01_河鹿堂讓書 llm_tokens 19459>15000 |
| draft/tools | dir | draft 格叫的工具（資料夾程式；C-61 工具放在叫它的那一格自己的資料夾裡）：director… |  |  |  |  |  |  |  |  |  |  |  |  |  |
| draft/tools/director | fn | 規劃節拍的單發腦函數：工作區 new/<n>.json 是稿紙（第 2 次附 plan_lint 的… | llm、cpu | 6000/150000 | q01:7332 q08:4499 | 1/1 | q01:1 q08:1 | 1800/4000 | q01:3610 q08:3448 | false | true | safe | true | grow_level、idempotent、llm_endpoint、llm_model、lock、reads、shap… |  |
| draft/tools/director/_entry | 單子 | 規劃節拍的單發腦函數：工作區 new/<n>.json 是稿紙（第 2 次附 plan_lint 的… | llm、cpu | 6000/150000 | q01:7332 q08:4499 | 1/1 | q01:1 q08:1 | 1800/4000 | q01:3610 q08:3448 | false | true | safe | true | grow_level、idempotent、llm_endpoint、llm_model、lock、reads、shap… |  |
| draft/tools/plan_lint | fn | beat 表的文法校驗：序列合 B0 B1 B2 B3+ (B4) B5 (B6) B7（c1 B5… | cpu | 20/1000 |  |  |  |  |  | true | false | safe | true | callers、grow_level、idempotent、reads、tier、writes |  |
| draft/tools/writer | fn | 寫稿的 agent：工作區 new/<n>.json 是稿紙＋beat 表（第 2 稿起附打回理由）… | llm、cpu | 10000/400000 | q01:9191 q08:6674 | 1/3 | q01:3 q08:2 | 3000/11000 | q01:15849 q08:10477 | false | true | resumable | true | calls、grow_level、idempotent、llm_endpoint、llm_model、lock、read… | q01_河鹿堂讓書 llm_tokens 15849>11000 |
| draft/tools/writer/fsm.json#/states/think/exec | 單子 | 問腦一次：把 brief＋beat 表（或打回理由、lint 的結果）送去，收回一稿台詞或一次 li… | llm | 8000/180000 | q01:2973 q08:3246 | 1 | q01:1 q08:1 | 2500/11000 | q01:5283 q08:5238 | false | false | safe |  | idempotent、llm_endpoint、llm_model |  |
| draft/tools/writer/fsm.json#/states/act/exec | 單子 | 照腦的最後一則回覆動手：有 tool_calls 就叫 tools/<名>（lint）、結果接回 h… | cpu | 100/30000 |  |  |  |  |  | true | true | safe |  | idempotent |  |
| draft/tools/writer/idle | fn | 看工作區還有沒有題目：有退 0、沒有退 10 讓 loop 停 | cpu | 5/100 |  |  |  |  |  | true | false | safe | true | idempotent、reads、writes |  |
| draft/tools/writer/tools/lint | link | 捷徑 → ../../../../lib/lint |  |  |  |  |  |  |  |  |  |  |  |  |  |
| draft/tools/writer/tools | dir | writer 的腦叫的工具：lint（相對捷徑指 lib/lint；交稿前自檢） |  |  |  |  |  |  |  |  |  |  |  |  |  |
| examples | data | 範例場景 JSON（題目的形狀）：複製到工作區 new/ 就能跑；q01、q08 各對應 judge… | disk |  |  |  |  |  |  | true | false |  |  |  |  |
| idle | fn | 看工作區 cur/ 或 new/ 還有沒有場景 JSON：有退 0 往下走一圈，沒有退 10 讓 l… | cpu | 5/100 |  |  |  |  |  | true | false | safe | true | grow_level、idempotent、reads、writes |  |
| judge | fn | 黏合格：check 定稿後把 brief、定稿、benchmarks/<id>.json 正解交給 … | llm、cpu | 7500/300000 | q01:2601 q08:2380 | 1/1 | q01:1 q08:1 | 2200/4500 | q01:3615 q08:3560 | false | true | resumable | false | calls、grow_level、idempotent、llm_endpoint、llm_model、note、read… |  |
| judge/benchmarks | data | corpus/評測 挖空題的抄本（context、挖空對白、正解、評分要點），只給 judge 當打… | disk |  |  |  |  |  |  | true | false |  |  | source |  |
| judge/tools | dir | judge 格叫的工具（資料夾程式）：critic |  |  |  |  |  |  |  |  |  |  |  |  |  |
| judge/tools/critic | fn | 打分的單發腦函數：工作區 new/<n>.json 是稿子＋場景＋benchmark，問腦一次，答案… | llm、cpu | 7000/150000 | q01:2521 q08:2303 | 1/1 | q01:1 q08:1 | 2200/4500 | q01:3615 q08:3560 | false | true | safe | true | grow_level、idempotent、llm_endpoint、llm_model、reads、shape、wri… |  |
| judge/tools/critic/_entry | 單子 | 打分的單發腦函數：工作區 new/<n>.json 是稿子＋場景＋benchmark，問腦一次，答案… | llm、cpu | 7000/150000 | q01:2521 q08:2303 | 1/1 | q01:1 q08:1 | 2200/4500 | q01:3615 q08:3560 | false | true | safe | true | grow_level、idempotent、llm_endpoint、llm_model、reads、shape、wri… |  |
| lib | dir | galtxt-b 自己的函式庫：被兩處以上叫的純函數（stdin 一份 JSON → stdout … |  |  |  |  |  |  |  |  |  |  |  |  |  |
| lib/lint | fn | 稿子的確定性檢核：格式、護欄關鍵詞、禁語、地點穿幫（Tier 0）；稱謂階、感嘆號、口頭禪、句長、旁… | cpu | 30/1000 |  |  |  |  |  | true | false | safe | true | callers、grow_level、idempotent、reads、tier、writes |  |

## 宣告 val 跟實測差最多的幾列

| 路徑 | 題 | key | 宣告 val | 實測 | 倍數 |
|---|---|---|---|---|---|
| draft/tools/writer | q01_河鹿堂讓書 | llm_tokens | 3000 | 15849 | 5.28 |
| draft | q01_河鹿堂讓書 | llm_tokens | 4300 | 19459 | 4.53 |
| draft/tools/writer | q08_河鹿堂進新書日 | llm_tokens | 3000 | 10477 | 3.49 |
| . | q01_河鹿堂讓書 | llm_tokens | 7000 | 23074 | 3.30 |
| draft | q08_河鹿堂進新書日 | llm_tokens | 4300 | 13925 | 3.24 |
| judge | q08_河鹿堂進新書日 | time_ms | 7500 | 2380 | 0.32 |
| judge/tools/critic/_entry | q08_河鹿堂進新書日 | time_ms | 7000 | 2303 | 0.33 |
| judge/tools/critic | q08_河鹿堂進新書日 | time_ms | 7000 | 2303 | 0.33 |
| draft/tools/writer | q01_河鹿堂讓書 | llm_calls | 1 | 3 | 3.00 |
| brief | q08_河鹿堂進新書日 | time_ms | 60 | 20 | 0.33 |
| brief | q01_河鹿堂讓書 | time_ms | 60 | 20 | 0.33 |
| judge | q01_河鹿堂讓書 | time_ms | 7500 | 2601 | 0.35 |
| judge/tools/critic/_entry | q01_河鹿堂讓書 | time_ms | 7000 | 2521 | 0.36 |
| judge/tools/critic | q01_河鹿堂讓書 | time_ms | 7000 | 2521 | 0.36 |
| draft/tools/writer/fsm.json#/states/think/exec | q01_河鹿堂讓書 | time_ms | 8000 | 2973 | 0.37 |
