# 2026-10-09 真 AI 第一圈：消耗報告（R1 隊）

← [proto7-2 notes](../../)｜傳輸：[llmcall](../../../packs/llmcall/README.md)（`llm.litellm`）｜學徒：[author](../../../packs/author/README.md)（`propose --llm`）｜逐次數據：[evidence/calls.csv](evidence/calls.csv)

使用者 14:20 准許接真 AI（LiteLLM `localhost:4000/v1`，gpt 系，不用 `lm-*`／`ollama-*`，上限拉滿，跑完再訂限制）。本報告就是「跑完一個大段落」的實際消耗，給之後訂限制用。

## 怎麼跑的

- **冒煙**：`packs/llmcall/examples/litellm/run.sh`，`chatgpt-gpt-6-sol` 回「OK」→ [evidence/litellm-smoke/](evidence/litellm-smoke/)。
- **一整圈**：`packs/author/examples/llm-request/run.sh MODEL OUTDIR`。需求＝`examples/csv-request/request.json`（rid `csv1`，部門統計）。流程：真 AI 產候選（提示詞＝需求＋白名單工具卡＋候選 schema＋規則，**不含 valid.json**，不設 max_tokens／temperature）→ 三關檢查（格式、工具卡契約、step 檢查器）→ `publish` → daemon 起 step 跑完 → `answer` 獨立檢查器 → step close → author close。每次都是新暫存 root、新預算帳（grant 1 億 token、reserve 每次 100 萬）。
- 每個 `evidence/loop-<模型>[-rN]/` 有：llmcall 的 request／raw／receipt、作者的 candidate／verdict、propose／publish／answer／close 輸出、`jobs/<job>/out/report.json`、`summary.json`。空的 stderr 已刪（＝沒有錯誤輸出）。

## 結果（12 次一整圈＋1 次冒煙，全部同一份提示詞）

| 模型 | prompt | completion | 其中推理 | cached | total | HTTP 秒 | 三關 | step | 答案 |
|---|---|---|---|---|---|---|---|---|---|
| chatgpt-gpt-6-sol ×3 | 2365 | 225／262／218 | 91／125／79 | 0 | 2590／2627／2583 | 7.1／6.8／5.7 | 過 | ok | 對 |
| chatgpt-gpt-6-sol-high | 2365 | 201 | 62 | 0 | 2566 | 6.4 | 過 | ok | 對 |
| chatgpt-gpt-6-astra ×3 | 2365 | 139／140／137 | 0 | 1408 | 2504／2505／2502 | 4.3／4.7／5.2 | 過 | ok | 對 |
| chatgpt-gpt-6-astra-max | 2365 | 323 | 184 | 0 | 2688 | 10.9 | 過 | ok | 對 |
| chatgpt-gpt-6-luna ×3 | 2365 | 186／193／201 | 35／45／54 | 0 | 2551／2558／2566 | 3.6／2.9／3.8 | 過 | ok | 對 |
| chatgpt-gpt-6-luna-nothink | 2365 | 134 | 0 | 0 | 2499 | 2.4 | 過 | ok | 對 |
| 冒煙（sol，回 OK） | 1644 | 5 | 0 | 1408 | 1649 | 1.6 | — | — | — |

- **12／12 過三關、step 都 ok、答案都對、都 close**；**沒有任何候選被拒**（被拒也會照實記，這次沒有可記的）。12 份候選的 job 雜湊各不同（intent 文字不同），結構都等同 valid.json：convert → stats、`${req:convert}`。
- 合計 30 739 tokens（12 圈）＋1649（冒煙）。單次 total 2499～2688，HTTP 2.4～10.9 秒；整圈（propose 到 close，含 daemon 跑 step）sol 那次牆鐘約 12 秒。
- 所有呼叫 `finish_reason: stop`、`billing: final`、`overrun 0`；used＝total_tokens（軟預算、部分結算）。
- **代理有固定前置開銷**：只說「請只回 OK」也算 1644 prompt tokens，且 astra 有 1408 cached——LiteLLM／上游會注入約 1.6k token 的前置內容。作者提示詞本身約 720 tokens。

## 給訂限制用的建議（使用者定，以下只是數據推出的起點）

| 項目 | 實測最大 | 建議起點 | 理由 |
|---|---|---|---|
| 單次 reserve（token） | 2688 | 8 000 | 約 3 倍；超出只記 overrun、退出 4，不會丟內容 |
| 單次 deadline（秒） | 10.9 | 120 | 推理強的 `-max` 最慢；逾時＝intent 留著、要人手 adopt，寧可寬 |
| 單需求預算（token） | — | 50 000 | 允許約 15 次重試／換模型 |
| max_tokens | 未設（輸出最多 323） | 仍不設 | CSV 候選很短；設了反而可能截斷推理模型 |

目前程式預設仍是「拉滿」：author `--reserve` 預設 1 000 000、llmcall litellm deadline 預設 86 400 秒、不設 max_tokens。

## 還沒驗到的（邊緣狀況）

- 只有一份需求（2 工具、2 步）：太簡單，五個模型都一次就過，看不出模型差異與三關的拒絕率；要比較要出更難的需求（更多工具、分支、會誘導寫 `${out}` 外的）。
- 沒遇到真 provider 的 4xx／5xx／逾時／usage 缺；這些只在假 HTTP 伺服器測試裡驗過。
- 費用（價格）不在帳上：只有 token 數。
