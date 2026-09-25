← [第三波 W3-2 隊報告](README.md)｜[回報](review-astra-2.md)｜第一輪：[任務書](review-task.md)／[回報](review-astra.md)

# 審查任務書（第二輪）：W3-2 的審查修法＋09-25 收尾（唯讀）

你是唯讀審查者。**不要改任何檔、不要跑模型、不要開 daemon／kernel、不要碰 LM Studio／`lms`／localhost:1234／ollama／localhost:4000。** 可以讀檔、跑單元測試（`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p 'test_llm_ask.py'`，同樣可跑 `test_compact_summarize.py`、`test_agent_tools_wrapcli.py`、`test_team_crystal.py`）。不要跑全套。繁體中文、白話。

## 審什麼

兩段改動，以前的審查已修的不用重提：

1. **第一輪必修的修法**：`git diff f141b01 162cc59 -- proto5/lib`（第一輪的問題 M1～M9、S1～S3、S5 與修法摘要在 `proto5/notes/2026-09-24-tool-era/w3b/README.md` §9，原回報 `review-astra.md`）。看的是：**修法有沒有真的堵住原問題、有沒有修出新洞**。重點四項：
   - wrap-cli（`lib/aos_agent_tools_wrapcli.py`）：M1 值不能變成旗標、M7 nargs／append／多個可變位置參數、M8 跑 `CMD --help` 的上限與環境、M9 `--spec` 欄位驗證、S1 控制字元、S5 套用指令的 quoting。
   - wrap-py 補描述（`lib/aos_agent_tools_dev.py` 的 `describe_with_llm`／`check_describe`／`apply_describe`）。
   - compact 濃縮（`lib/aos_agent_compact.py` 的 `make_summarizer`／`check_summary`／`compose`／`keywords`）：M6 使用者原話機械保留、數字完整比對；S2 用量記帳。
   - crystal（`lib/aos_team_crystal.py`）：M2 不准蓋 routes.json、M3 整份例句全過、M4 次數從歷史算、M5 內建反例、S3 舊 log 配信可信度。
2. **09-25 收尾（S4）**：`git diff 60e4b81 3195d6b`。
   - `lib/aos_llm_ask.py` 的 `parse_json`：前後多字、``` 圍欄（大小寫、沒收尾）容忍；只收物件或陣列；純量、重複 key、NaN／Infinity＝`BadModelOutput`；重複 key 與 NaN 整份不收、不往裡找。
   - `lib/aos_agent_compact.py` 的 `_clean`：一個圍欄＋圍欄外 ≤ 80 字、各 ≤ 1 行＝只取圍欄裡的；沒收尾去第一行；其他原樣。
   - 新測試：`test_llm_ask.py` 的 `ParseJsonGuardTest`、`test_agent_tools_wrapcli.py` 的 `BrokenReplyTests`、`test_team_crystal.py` 的三條、`test_compact_summarize.py` 兩條 `_clean`。

## 特別想知道

- `parse_json` 從第一個 `{`／`[` 往後掃：有沒有情況會撿到「不是答案」的一小塊，而且呼叫端的形狀檢查接不住、結果寫進提案檔或規則？
- `_clean` 只取圍欄時，會不會丟掉摘要的主體、卻仍通過 `check_summary`（也就是關鍵詞剛好都在圍欄裡）？
- 四個呼叫端（wrap-cli `llm_table`、wrap-py `describe_with_llm`、crystal `llm_candidates`＋`screen_llm`、compact `make_summarizer`）碰到怪形狀的回話，有沒有哪裡會噴出 Python 例外（TypeError、KeyError、AttributeError…）而不是乾淨的 `aos-agent: 代號: 白話` 或退回？
- 測試有沒有假設信箱檔名順序＝時間順序、或其他會 flaky 的寫法？

## 產出格式

寫到 `-o` 指定的檔（Markdown），開頭一行 `← [第三波 W3-2 隊報告](README.md)｜[任務書](review-task-2.md)`，接著：

1. **必修**（會造成錯誤結果、寫壞檔、繞過檢查、或噴例外）：編號 M1、M2…，每條寫「哪個檔哪一行／函式、怎麼觸發（最好給一段能重現的輸入）、建議怎麼修」。
2. **建議**（不修也不會錯）：編號 S1、S2…，同樣格式。
3. **看過、沒問題的**：一段話列出你確認過的點。

沒有就寫「無」。每條三五行內，不要貼大段程式。
