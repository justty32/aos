# 名詞、責任與狀態

← [規格入口](README.md)｜[共用資料契約](contracts.md)

## T-01．來源與適用範圍

〔主編補〕本疊是可實作的**規格草案**，不是現行行為。每節來源及驗收涵蓋該節全部條件；「必須／禁止」表示遵循本草案的條件，不代表使用者已逐條拍板。〔使用者方向〕只引用已有決定；〔建議預設，未拍板〕可被後續裁決替換；〔主編補〕補足跨篇編輯規則。使用者新決定優先於建議預設，替換時需同步受影響驗收。

驗收：Given 尚未批准的 timeout 預設，When 展示配置說明，Then 標為建議預設，不能說成使用者要求或已運行功能。

## T-02．三層 owner

〔使用者方向 2026-09-28，見[概念](../notes/concepts.md)〕**基底**負責執行與持久交接，**agent**負責理解內容、選 context／工具與推進狀態，**任務與排程**負責機會、預算與任務完成契約。每篇的「責任」是邏輯 owner，不要求每個 owner 各開一個 daemon。

〔建議預設，未拍板〕控制帳本只有一個邏輯寫入者；可信 launcher 和回報導入器可為該寫入者的模組。供工作程序讀寫的檔案不能作為 root 自由開檔指令。agent 身分可修改自己的資料，不可因此修改帳本、別人的歸屬或部署設定。

驗收：Given 工具聲稱自己優先且屬另一 agent，When 投件，Then agent 語意不授予該權限，控制層拒絕冒名，原 agent 的合法工作仍可排程。

## T-03．四種工作識別與一次 RPC

〔建議預設，未拍板〕`agent_id` 穩定代表一個 agent；`run_id` 代表一次已接納的任務輪次；`job_id` 代表一次邏輯委託，例如一個工具呼叫；`attempt_id` 代表實際嘗試。重送同一次結果保持 attempt_id，再執行才產生新 attempt_id。`request_id` 只代表 RPC 對應與去重，不當成以上全部層級的通用識別。

`generation` 是每 agent 單寫者的遞增世代，和 attempt 次數不同。刪除再建立一個 agent 使用新 agent_id；數字 UID 可經管理程序回收，但不得把舊結果接到新身分。全體 ID 型別依 [contracts](contracts.md)。

驗收：Given 同 job 的第一次嘗試結果未知，When 使用者明確允許重試，Then job_id 不變而 attempt_id 更新；第一個 attempt 的遲到結果不能覆寫第二個已選定的結果。

## T-04．控制狀態與觀測 phase 不混用

〔建議預設，未拍板；09-29 精簡，依冗餘審查 B4〕`agent.phase` 僅為 `idle|think|act|wait|paused|error`，是從 run／job／attempt 的控制事實與已保存的語意 continuation 推導出的唯讀觀測值，不是另一張可寫的控制狀態圖。`run.state` 為 `queued|active|paused|succeeded|failed|canceled|needs_attention`，描述任務生命週期。`job.state` 為 `queued|waiting|admitted|running|succeeded|failed|canceled|unknown`；`attempt.state` 為 `reserved|starting|running|canceling|succeeded|failed|canceled|unknown`。暫停、取消與錯誤屏障以 run 及工作狀態為權威，phase 不得解除或掩蓋它們。

job 的 `waiting` 表示尚未入場、等 due／quota 等條件；進行中的遠端 HTTP 即使本機在等回覆仍為 `running`。agent 的 `wait` 不等於某個 job 一定仍 running，也可能等工具／LLM 結果或額度；仍阻擋目前 run 的未解決 `unknown` 顯示 `error`。`unknown` 不是成功、不是可自動重試的普通錯誤。run `needs_attention` 是保留可解決的暫停狀態，不是終局；終局為 succeeded／failed／canceled。

驗收：Given 工具成功而 agent 還未回答，When 更新工具結果，Then job 可 succeeded，但 run 不能因此直接 succeeded；查詢可依 continuation 顯示 think。Given run 已 paused，When continuation 原先位於 act，Then phase 顯示 paused 且不得派新工作。

## T-05．一萬份本體與少量活動

〔使用者方向 2026-09-28，見[負載](../notes/2026-09-28-linux-resources-and-task-scheduling.md)〕目標為 10,000 個 agent、每小時活躍不到 100 個、雲端推論。一 agent 一 Linux 使用者、工具繼承權限與資源；cgroup 控執行用量，project quota 記帳自有資料（09-29 裁定 6、8：可選、只記帳，見 [B-304](base/identity-resources.md)）。取消 CPU worker 是方向，准入控制仍保留。FUSE、分散式 kernel、父子 demo 延後。

〔建議預設，未拍板〕冷 agent 保留 metadata／資料而無常駐程序；資源域由可信登記解析，不靠每次投件宣告。部署 profile 尚未選定；日常特權點依 09-29 裁定 5 為極小 root helper（[B-303](base/identity-resources.md)），主 daemon 不以 root 執行；不把探針成功當成整體隔離驗收。

驗收：Given 10,000 筆冷登記無待辦或到期維護，When 穩態觀察，Then 沒有 10,000 個程序與固定逐 agent tick；增加少數 ready 工作者才產生執行成本。
