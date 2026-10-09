## 試用者
Claude Haiku（新手）
## 分鐘
0.2
## 有沒有跑成功
成功，第 1 行回條印出 `"outcome": "rendered"`、`tokens_est` 206、`tokens_est_full` 220，並有一段被折疊的 `ref://…`；第 3 行 `expand` 把原文完整印回來。
## 對外指令數
2：`aos7-prompt render`、`aos7-prompt expand`
## 新概念數
11：node（AI 的資料夾）、prompt.json（訊息清單，含 role／content）、`$opt`／`$val` 讀檔寫法（含 `tail`、`latest`、`append`）、`$ref`、`$fmt`、`$env`、`ref://` 折疊、`refs/` 原文資料夾、`max_chars`、`tokens_est`（字數÷3 的估值）、回條（outcome／why）、退出碼 0／2／3
## 卡點
1. [範例 `examples/node/`，README 第 42 行起] README 說有 `wf/AGENTS.md`、`wf/SESSION-LOG.md`、`wf/inbox/` 三樣東西，但沒說這套結構的約定（誰寫、何時搬進 `done/`、AGENTS.md 為什麼是入口），我看不懂 node 為什麼這樣分。不能讀 spec，只能記下來。約花 1 分鐘。
2. [第一次跑，第 17 行回條 `tokens_est` 206 對 `tokens_est_full` 220] 我以為「收起來」會省很多 token，結果只省約 6%。README 沒解釋這個示範為什麼省得少（是 `--max-chars 300` 的關係還是範例本身太短），我一度懷疑自己跑錯。約花 1 分鐘，最後判斷是範例太短、看不出效果。
## 五條分數（0–10，10 最好）
- 容易上手：9 三行照抄就跑成功，第一次跑沒有任何報錯。
- 容易理解：6 五個概念的表格很有用，但 node、wf 結構與 `$opt`／`$ref`／`$fmt` 等寫法要自己拼湊理解。
- 複雜的藏起來：6 指令只有兩個，但 prompt.json 的寫法（多種 `$` 指令）與退出碼都直接攤在 README 上，沒有藏起來。
- 外層簡單但全面：7 render＋expand 就涵蓋主要用法，但 req.json 裡的 litellm 等送模型的細節只露出一點點，需要另外看 llmcall。
- 要背的少：6 指令只有兩個，但 `$` 指令有七八種寫法加上 ref://、回條、退出碼，加起來仍然要背不少。
- 平均：6.8
## ELI5
這是一個把很多份文件拼成一封給 AI 看的信的小工具。你先寫一張清單，說明要給 AI 看哪些檔案。工具每次照清單現讀現拼，太長的段落會先收起來，只留一個編號和前 200 字。需要看原文時，再用 expand 把它叫出來。
## ELI5 之後還複雜嗎
是，因為清單裡有好幾種 `$` 寫法，而且「node」「wf」這套資料夾約定沒有說清楚，小孩子聽完還是會問為什麼要這樣分。
