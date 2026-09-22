# 任務書：llm cpu 預先規劃（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-llm-cpu-plan-task.md](../notes/2026-09-22-llm-cpu-plan-task.md)

## 要做什麼、交什麼

使用者的方向是：「aos-agent 的 think 目前是直接呼叫 llm-ask，改成將呼叫請求丟給另一個 cpu。可能要先規劃 llm cpu，這塊也要先去看 proto4。」

本次 **只規劃，不寫程式，也不寫定稿規範**。唯一產出是 `proto5/notes/2026-09-22-llm-cpu-plan.md`，先讓使用者審閱，再決定是否升格為規範；到時仍按 proto5 慣例，分成「JSON 格式／協議」與「程式」兩份。

## 筆記一定要回答的三件事

### 一、proto4 現在怎麼做

這部分控制在一頁內，依現況整理，不憑空推測。

| 調查對象 | 要交代清楚的事 |
|---|---|
| proto4-5 的 `aos-llm` | 一次同步呼叫的工作方式。 |
| proto4-5 的 `llm-cpu` | 如何收請求、排隊，按 endpoint 容量派工；如何獨立跑，以及如何掛成 kernel module。 |
| 請求／回應檔 | 各自長什麼樣、放哪裡、誰寫誰讀、怎麼表示完成、錯誤怎麼送回。 |
| proto4-7 的 aos-agent | 問題交給 kernel 的 LLM 排程後，怎麼等、怎麼收回結果，以及退 101 讓出 CPU 的細節。 |

### 二、proto5 的 llm cpu 該長什麼樣

可以給兩三個方案，**一定要有推薦與理由**。使用者要最精簡的標準，缺的日後再補，別把每個可能性都先做進去。

| 規劃面向 | 必須回答的選擇 |
|---|---|
| 請求內容 | 以 aos-llm-ask 現在 `build_request` 組出的 body 為基礎，還要加哪些欄位？ |
| 回應內容 | 是否只回 `choices[0].message`？成功與失敗各用什麼形狀？ |
| 檔案位置與生命週期 | 請求／回應放 cpu 家目錄還是 agent 資料夾？怎麼命名？完成靠 rename `.done`，還是另外寫回應檔？ |
| CPU 程式形態 | 是像 agent 一樣反覆被呼叫、一次做一件事、退出 0／101，還是常駐？每 tick 到底做什麼？ |
| 控制責任 | endpoint 容量、逾時、重試各屬哪一層？ |
| 與既有 client 的關係 | 直接重用 `aos_llm_ask.call(engine, body)`。engine 從 agent 的 info 帶過去，還是由 cpu 自己維護 endpoint 表？proto4-5 用的是 endpoint 表。 |

### 三、aos-agent 的 think 怎麼改

現行 think 一格內同步問完；新方案必須拆成「送出」與「收回」，用 proto5 已有機制說明，不只畫抽象架構。

| 階段／風險 | 規劃至少要說清楚 |
|---|---|
| 送出 | 寫請求檔，再往 `state.json` 的 waits 加一條等待回應檔的條件。 |
| 收回 | 門開後，把回應的 assistant 訊息接到記憶，再決定去 act 或 idle。 |
| 狀態格數 | 保留 think、以 waits 當門，還是新增 asked 等狀態？各方案怎麼分辨已送出與待收回？ |
| 檔案歸誰收 | 回應檔由誰 rename？wait 的 consume 要不要開？ |
| 崩潰與自癒 | 送請求、登記等待、收回、寫記憶等步驟中途崩掉怎麼恢復？要對照現行 aos-agent 自癒規則。 |
| 修改清單 | 對照現行 `aos-agent.md`，列出「要改哪幾行」，讓使用者知道採用後規範會變哪裡。 |

## 先讀什麼

| 次序 | 閱讀範圍 | 用途 |
|---|---|---|
| 1：proto5 | README；`spec/agent.md`、`aos-agent.md`、`aos-llm-ask.md`、`inst-posix.md`；lib README 的 aos_llm_ask 一節。 | 統一術語，掌握 state 三格、waits 五選項、門與自癒、body 組法、call／ask、EngineFailed。CPU 日後可能也是用 inst 跑。 |
| 2：proto4-5 | README、`aos_llm.py`、`aos_llm_cli.py`、`llm_cpu*.py`、測試。 | 查同步 client 與排隊派工的實際行為。 |
| 3：proto4-7 | README、`aos-agent`、`agent_tools.py` 中交給 kernel 排 LLM、等結果、101 的部分。 | 查 agent 非同步送出與收回的完整流程。 |
| 4：proto4-3 | `docs/kernel.md` 只讀掛 module 那節。 | 知道如何接 kernel 即可；另一個 agent 正在整理 daemon／kernel 規範，不重做那份工作。 |

## 全部規則與回報

| 項目 | 要求 |
|---|---|
| 修改範圍 | 只寫指定的 llm-cpu-plan 筆記。不碰 `proto5/spec/`、`proto5/lib/`、`proto5/cli/`、`proto5/README.md`；另兩個 agent 正在處理那些地方。 |
| 文字形式 | 中文大白話、表格，目標 150～250 行。保留檔案形狀、誰寫誰讀、狀態轉換、退出碼；不寫瑣碎實作細節。 |
| 尚未確定的事 | 集中成「要使用者拍板的問題」，每題都附自己的推薦，以及一兩句理由。任務書中列的選項是待比較事項，不是已定答案。 |
| 版本操作 | 不 commit。 |
| 最後回報 | 中文條列：筆記幾行；上述三件事各一段摘要；推薦方案一句話；完整待拍板問題清單。 |
