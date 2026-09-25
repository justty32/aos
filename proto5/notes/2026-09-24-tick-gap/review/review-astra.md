以下依 `fdc93d6` 行號；僅靜態審查，未改檔、未啟動模型或 daemon。

## 必修

M1. [aos_kernel_ledger.py:332](../../../lib/aos_kernel_ledger.py) — **通知信不能保證崩潰後只寄一次** — 信已放好、提交 C 前 kernel 被殺；收件 agent 把信搬進 `done/`，恢復時帳本仍有 `letters`，原路徑卻已不存在，便再次投遞、再次當輸入處理。現有測試只涵蓋「寄出前崩潰」 — 建議收件端依固定信件 ID 持久去重，去重憑據不能隨原信搬走而消失。

M2. [aos_hops.py:53](../../../lib/aos_hops.py) — **量測寫檔可能卡住主程式** — `AOS_HOPS` 指向沒有讀端的 FIFO 時，`os.open(O_WRONLY)` 會一直等；有讀端但不讀時，後續 `write` 也可能阻塞，`except OSError` 救不了等待 — 建議非阻塞開啟、確認是普通檔才寫，其他情況直接略過。

M3. [aos_hops.py:55](../../../lib/aos_hops.py) — **量測的編碼錯誤會讓 kernel 失敗** — 啟用量測後，收到 `method: "\ud800"` 的 JSON request，Python 能解析，但記錄事件的 `.encode()` 會拋出 `UnicodeEncodeError`；這不屬於捕捉的 `OSError`，kernel 尚未處理、刪除該單就退出，下一格再撞同一張 — 建議使用可安全編碼的 JSON 輸出，並隔離序列化、編碼例外。

M4. [aos_kernel_ledger.py:321](../../../lib/aos_kernel_ledger.py) — **產生通知內容會同步讀工作檔，可能堵住整個 kernel** — 最後一次失敗回音產生後，`target` 的 `.json` 被換成 FIFO；判 bad 時 `stderr_hint()` 用 `read_text()` 等資料，卡在提交 B 前。下次恢復仍讀同一份檔，其他工作也無法正常排程 — 建議通知先使用帳本已有的 target；若要讀 stderr 提示，須限制為非阻塞、有大小上限的普通檔讀取。

## 建議（不修也不會壞）

S1. [aos_kernel_ledger.py:382](../../../lib/aos_kernel_ledger.py) — `on_bad.dir` 只檢查絕對路徑，接受 `..`，也會跟隨目錄 symlink；登記者確實能讓 kernel 往其權限可寫的任意目錄新增通知檔。**是否算安全漏洞不確定**：規範本來允許指定絕對路徑，未定義允許的根目錄。建議明寫信任邊界；若登記者不可信，才加目錄授權與防 symlink 解析。

S2. [aos_kernel_ledger.py:387](../../../lib/aos_kernel_ledger.py) — 64 KB 上限目前算字元數，中文內容實際 UTF-8 位元組數可超標；建議改算編碼後長度，並說明替換佔位符後是否也受限。

## 看過沒問題的

- 提交點 D 先存帳本、只放 `recent` 新增部分；D 前後崩潰的恢復路徑未見第一輪重放或漏帳。
- `classify` 的失敗分支不受 `woken` 加速；`done_exit` 優先於 102／103。
- 舊帳本缺 `again`，新版 kernel 會補標記；agent start 對已開機且缺能力標記的帳本會拒絕。
- agent 的 send／collect／settle／intake 退出碼有對應進度；未見新增的永久停車或無進度 103 迴圈，漏喚醒另有 `park_ms` 兜底。
- 正常門鈴流程採非阻塞開啟；普通檔不寫、末端 symlink 拒絕，cpu 不在不會卡住 kernel；保留寫端與排空讀端可避免 EOF 忙等。
- pidfd 在 `finally` 關閉；拿不到時退回睡眠，逾時仍走 TERM／寬限／KILL。
- 通知目錄不存在或無權限時，出貨會記失敗並清箱；health 的 `bad` 與團隊預設寄到 human 的接線一致。
- 未設 `AOS_HOPS` 時，`mark()` 在建立事件及檔案 I/O 前返回。