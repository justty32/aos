| path | depth | kind | grow_level | summary | time_ms | resource | llm_calls | llm_tokens | deterministic | idempotent | side_effect | interrupt | parallel | fs_needs | callers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| . | 0 | agent | 5 | 給一組場景條件（或評測的挖空題），寫幾份 galgame 台詞草稿、過護欄、評語… | 90000/3500000 | llm,cpu,disk | 9/60 | 24000/200000 | false | false | true | resumable | true | own_stack,git_tracked | 0 |
| brief | 1 | program | 3 | 認領一題，從 data/ 的人物卡、地點卡、固化表組出給寫手看的 brief.j… | 50/10000 | cpu,disk | — | — | true | true | true | safe | false | （空） | 1 |
| check | 1 | program | 4 | 每份草稿用 tools/lint 過一次 Tier 0 護欄與 Tier 1 語… | 300/30000 | cpu | — | — | true | true | false | safe | true | mount | 1 |
| check/tools/lint | 3 | program | 4 | 台詞護欄：stdin 收 {text}，照 $AOS_WS/rules.json… | 40/5000 | cpu | — | — | true | true | false | safe | true | tool_json,mount | 2 |
| data | 1 | data | 4 | 固化表的快取：人物卡、地點卡、稱謂階、禁語、語域標記、評測題、範例句；真源是 ~… | — | disk | — | — | true | — | false | — | — | git_tracked,isolation | 2 |
| data/bench | 2 | data | — | 評測題，一題一檔（<編號>.json）：前後文、說話者、護欄關鍵詞、評分要點、正… | — | — | — | — | — | — | — | — | — | git_tracked,isolation | — |
| data/cast | 2 | data | — | 人物卡，一人一張（<名>.json）：類型、口氣、稱謂各階的字面、語域標記 | — | — | — | — | — | — | — | — | — | git_tracked | — |
| data/places | 2 | data | — | 地點卡，一地一張（<名>.json）：給寫手的細節、不能改的硬設定 | — | — | — | — | — | — | — | — | — | git_tracked | — |
| data/samples | 2 | data | — | 合格範例句，一個角色一檔（<名>.json），從 corpus 場景抄、不含評測… | — | — | — | — | — | — | — | — | — | git_tracked | — |
| idle | 1 | program | 3 | cur/ 或 new/ 有題目退 0，沒有退 10 請 loop 停 | 5/1000 | cpu | — | — | true | true | false | safe | true | （空） | 1 |
| judge | 1 | glue | 3 | 過了護欄的草稿逐份交給評審 agent 打 0～3 的語意分，每份一個新小格，收… | 25000/960000 | llm,cpu | 3/12 | 6000/60000 | false | true | false | resumable | true | mount | 1 |
| judge/tools/judge | 3 | agent | 5 | 評審：讀前後文（或場景條件）與一份草稿，回「分數：N」「理由：標籤」兩行；沒有工… | 7000/300000 | llm,cpu | 1/2 | 2000/10000 | false | false | true | resumable | true | own_stack | 1 |
| judge/tools/judge/fsm.json#/states/think/exec | 4 | — | — | 問腦一次：讀題目（前後文或場景條件＋一份草稿），回「分數：N」「理由：標籤」 | 5000/90000 | llm | 1/— | 2000/10000 | false | false | false | safe | — | — | — |
| judge/tools/judge/idle | 4 | program | 3 | cur/ 或 new/ 有題目退 0，沒有退 10 請 loop 停 | 5/1000 | cpu | — | — | true | true | false | safe | true | （空） | 1 |
| meta | 1 | data | — | 管這棵樹自己的工具（metatable）與每輪收出來的表（table-round… | — | — | — | — | — | — | — | — | — | git_tracked | — |
| meta/metatable | 2 | program | 4 | 走一棵資料夾樹，把所有 _metainfo（含 fsm.json／loop.js… | 200/30000 | cpu | — | — | true | true | false | safe | true | mount | 0 |
| pick | 1 | program | 3 | 合 Tier 1＋Tier 2 分、嚴格比大小、平手編號小的贏；寫 out/<題… | 30/10000 | cpu,disk | — | — | true | true | true | safe | false | （空） | 1 |
| plan | 1 | data | — | 規劃書（round1.md）與實測（round1-measure.md），給人看… | — | — | — | — | — | — | — | — | — | git_tracked | — |
| plan/examples | 2 | data | — | 題目範例：scene.json（場景模式）、Q01.json（挖空模式）；複製到… | — | — | — | — | — | — | — | — | — | git_tracked | — |
| write | 1 | glue | 3 | 把 brief 交給寫手 agent 跑 N 次（預設 3），每次一個新小格，答… | 45000/2400000 | llm,cpu | 6/36 | 18000/150000 | false | true | false | resumable | true | mount | 1 |
| write/tools/writer | 3 | agent | 5 | 寫手：照 brief 寫一份台詞（整場 5～10 行，或挖空的那一行），交稿前用… | 15000/720000 | llm,cpu | 2/4 | 6000/50000 | false | false | true | resumable | true | own_stack,mount | 1 |
| write/tools/writer/fsm.json#/states/think/exec | 4 | — | — | 問腦一次：帶 history 與 tools（lint） | 6000/120000 | llm | 1/— | 3000/12000 | false | false | false | safe | — | — | — |
| write/tools/writer/idle | 4 | program | 3 | cur/ 或 new/ 有題目退 0，沒有退 10 請 loop 停 | 5/1000 | cpu | — | — | true | true | false | safe | true | （空） | 1 |
| write/tools/writer/tools/lint | 5 | 捷徑 | — | 捷徑 → ../../../../check/tools/lint | — | — | — | — | — | — | — | — | — | — | — |

| 彙總 | 值 |
|---|---|
| 節點數 | 24 |
| kind 各幾個 | agent 3、data 8、glue 2、program 8、— 2、捷徑 1 |
| 最大深度 | 5 |
| llm_calls.val 總和（只加 agent） | 12 |
| llm_tokens.val 總和（只加 agent） | 32000 |
| 頂層宣告（llm_calls／llm_tokens） | 9/60 ／ 24000/200000 |
| fs_needs 為空（收攏候選） | brief、idle、judge/tools/judge/idle、pick、write/tools/writer/idle |
