# proto5/lib — 公司與市場（12 支）

← [proto5/lib README](../README.md)｜上一份：[team](team.md)｜下一份：[測試](tests.md)

一檔一行（新增模組照這個格式插一行）：

| 檔 | 職責 |
|---|---|
| [`aos_company.py`](../aos_company.py) | 公司（09-25 組織設計，spec/team/company.md）：`company.json` 讀驗、照樣板生一家（成員名加前綴）、數正式員工與 cpu（`aos-kernel ls --json`）、`up`／`down`、機械總機 `Switchboard`（〔給 部門〕→ 對方門房開單或窗口信，回覆照 reply_to／任務單 request 抄回，先記帳再動作）；指令包裝 `examples/company/company.py`。這支留開機、關機與命令列 |
| [`aos_company_config.py`](../aos_company_config.py) | 公司設定：路徑與型別常數、收件部門標記、`CompanyError`、`company.json` 讀驗、部門與團隊資料夾、窗口成員 |
| [`aos_company_new.py`](../aos_company_new.py) | 生一家公司：照樣板把名冊與門房規則加成員名前綴、寫出整家、列全公司成員 |
| [`aos_company_switchboard.py`](../aos_company_switchboard.py) | 機械總機 `Switchboard`：〔給 部門〕→ 對方門房開單或窗口信，回覆抄回，先記帳再動作 |
| [`aos_company_count.py`](../aos_company_count.py) | 數人頭、數 cpu 與狀態：正式員工人頭、kernel 的 cpu、上限檢查、daemon 家與環境、狀態資料與印法 |
| [`aos_market.py`](../aos_market.py) | 市場層（09-25，spec/team/market.md）：幾家公司的排名（品質／快／省加權；09-25 晚起品質＝原始品質×成功率×審查係數、快只在成功張數最多的之間比，第 74、75 題）、照名次撥額度（`aos_team_cost` 帳戶）、總池（錢與名額）、倒閉／裁撤回收、`slots` 撥名額、兩家合併（經理只留一個、名額滿了改臨時工、notes 帶過去）；指令包裝 `examples/company/market.py`。這支留命令列 `main` 與印表 |
| [`aos_market_book.py`](../aos_market_book.py) | 市場的帳本：常數與預設參數、`MarketError`、資料夾與鎖、`market.json` 讀寫、營業中判定、總池 |
| [`aos_market_review.py`](../aos_market_review.py) | 市場的審查係數（09-25 晚第 75 題）：製造部單子第幾次審查才過（讀單子的 `review`）→ 品質要乘的係數（`review_factors`，起始 1.0／0.7／0.4、FAILED＝0；讀 `market.json` 時檢查每個 0～1；係數在 `score` 時算好存下，**改 `review_factors` 要重新 `score` 才生效**） |
| [`aos_market_score.py`](../aos_market_score.py) | 市場的表現：評估結果與品管判決算品質、一家的成績板（成功／失敗張數、董事等的秒數、成功那幾張的審查輪數 `reviews`）、記一筆成績（含 `review_rounds`、`review_factor`；沒紀錄當 1.0 寫進說明） |
| [`aos_market_grant.py`](../aos_market_grant.py) | 市場的開戶與撥款：開帳戶、加權排名（品質乘成功率與審查係數；快只在成功張數最多的之間比，少的 0）、照名次撥額度、撥名額 |
| [`aos_market_close.py`](../aos_market_close.py) | 市場的倒閉與裁撤：停機、回收額度與名額、崩在半路的收尾重跑 |
| [`aos_market_merge.py`](../aos_market_merge.py) | 市場的合併：合併計畫（經理只留一個、名額滿了改臨時工、notes 帶過去）與逐步照做 |
