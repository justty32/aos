# 任務書：llm cpu 預先規劃（2026-09-22）

使用者一句話：「aos-agent 的 think 目前是直接呼叫 llm-ask，改成將呼叫請求丟給另一個 cpu。可能要先規劃 llm cpu，
這塊也要先去看 proto4。」

## 要做什麼

**只規劃、不寫程式、不寫定稿規範**：產出一份規劃筆記 `proto5/notes/2026-09-22-llm-cpu-plan.md`，讓使用者審完再決定要不要
變成規範（規範到時會照 proto5 的慣例分「JSON 格式（協議）」一份、「程式」一份）。

筆記要回答三件事：

1. **proto4 是怎麼做的**（照現況整理，一頁以內）：proto4-5 的 `aos-llm`（一次同步呼叫）與 `llm-cpu`（收請求、排隊、按 endpoint
   容量派工；可獨立跑、可掛成 kernel module）——請求檔／回應檔長什麼樣、放哪、誰寫誰讀、怎麼知道做完了、錯誤怎麼回；
   proto4-7 的 `aos-agent` 把問題交給 kernel 的 LLM 排程之後怎麼等、怎麼收回、退 101 讓出 CPU 的細節。
2. **proto5 這邊 llm cpu 該長什麼樣**（方案，可以給 2～3 個選項但要有推薦）：
   - 請求／回應的**檔案協議**：請求就是 aos-llm-ask 現在組出來的 body（`build_request` 那包）加什麼欄位？回應就是
     `choices[0].message` 那一行？放在 cpu 的家還是 agent 資料夾？檔名怎麼取、做完怎麼標（rename `.done`？寫回應檔？）。
   - **程式**：llm cpu 是獨立一支反覆被叫的程式（像 aos-agent 一樣一次做一件事、退 0／101）還是常駐？每 tick 做什麼？
     endpoint 容量、逾時、重試放哪一層？
   - 跟已有東西的關係：`aos_llm_ask.call(engine, body)` 直接重用；`engine` 設定從 agent 的 `info.json` 帶過去還是 cpu 自己有
     endpoint 表（proto4-5 是 endpoint 表）。
3. **aos-agent 的 `think` 要怎麼改**：現在 `think` 一格內同步問完；改成丟請求後，`think` 得拆成「送出」跟「收回」。用
   proto5 已有的機制講：送出＝寫請求檔＋往 `state.json` 的 `waits` 加一條等回應檔；收回＝門開了、把回應那則 `assistant`
   接進記憶、決定去 `act` 或 `idle`。要說清楚：狀態要不要多一格（例如 `think` 留著、`waits` 當門，還是加 `asked`）、
   回應檔是誰 rename、崩在中間怎麼自癒（對照 aos-agent.md 現在的自癒規則）、`consume` 要不要開。跟現在的 aos-agent.md
   對照，列出「要改哪幾行」。

## 先讀什麼

1. proto5 現況（術語要一致）：`proto5/README.md`、`proto5/spec/agent.md`（`state.json` 三格、`waits` 五個選項）、
   `proto5/spec/aos-agent.md`（三格、門、自癒）、`proto5/spec/aos-llm-ask.md`（body 怎麼組、`call`／`ask`、`EngineFailed`）、
   `proto5/lib/README.md` 的 aos_llm_ask 那節、`proto5/spec/inst-posix.md`（cpu 之後大概也是 inst 跑起來的）。
2. proto4-5：`README.md`、`aos_llm.py`、`aos_llm_cli.py`、`llm_cpu*.py`、`test/`。
3. proto4-7：`README.md`、`aos-agent`、`agent_tools.py` 裡跟「交給 kernel 的 LLM 排程、等結果、101」有關的部分。
4. proto4-3 `docs/kernel.md` 只看 module 怎麼掛那一節（另一個 agent 正在把 daemon／kernel 寫成規範，你不用重做）。

## 規則

1. 只寫 `proto5/notes/2026-09-22-llm-cpu-plan.md` 這一份；**不要碰** `proto5/spec/`、`proto5/lib/`、`proto5/cli/`、`proto5/README.md`
   （另外兩個 agent 正在那些地方動）。
2. 大白話、中文、表格；目標 150～250 行。不要寫太瑣碎的東西：檔案形狀、誰寫誰讀、狀態轉換、退出碼這種要；實作細節不要。
3. 拿不定的地方列成「要使用者拍板的問題」，每題附你的推薦與理由（一兩句）。使用者要的是最精簡的標準，缺的之後再補。
4. 不 commit。
5. 回報用中文、條列：筆記幾行；三件事各一段摘要；推薦方案一句話；要使用者拍板的問題清單。
