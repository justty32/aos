# 動態加掛與 restart：第二輪分線證據

本分線先讀 README → spec.md → core.md，並對照第一輪 astra 報告及 problems.md。產品碼是在第一份黑箱實測完成之後才讀。沒有改產品碼。重跑：`python3 proto7-1/notes/play/2026-10-03-astra-2-evidence/requests/probe.py` 與同目錄 `additional.py`。

## 新發現 1：加掛 name 是非空陣列時，請求被吞掉，tick 失敗且部分成功結果沒進回合總結〔bug〕

**重現步驟：**

1. 建 `n` 與對照 `healthy` 兩條 150 ms 時間線，各起 keep sleeper 與 each pulse。
2. 用 daemon ctl 暫停 n，等 phase 為 paused。
3. 在 n 的活任務 `mount-req/` 依序放 `01-good.json`＝`{"name":"ok","path":"recipient/inbox"}`、`02-bad.json`＝`{"name":["bad"],"path":"recipient/inbox"}`、`03-later.json`＝`{"name":"later","path":"recipient/other"}`。
4. 用 ctl 恢復，等三回合；cat status、mount-done、birth、rounds。

**看到什麼：** n 第 2 回合 tick code 1，`TypeError: cannot use 'list' as a dict key`；02-bad 請求已刪，卻無拒絕回條。該回合的 `pulse-r2` 沒出生；03-later 到第 3 回合才掛。01-good 已成功修改 birth 且有成功回條，但 `rounds/2.json` 的 `mounts: []`，不能靠該回合總結知道它曾加掛。healthy 不受影響。status.last_error 現在有錯誤，這是第一輪之後的改善；n 下一回合恢復，不能把這說成第一輪 ctl [] 那種反覆阻斷。

`probe.py` 額外證實語法錯誤、頂層陣列／null／字串／數字、path 是陣列／物件、name 是數字都可得到失敗回條；因此不是泛稱「壞 JSON 都出錯」。事後讀碼可見 serve 先 `os.remove`，再於型別檢查前建立 `{name: path}`，碰到不可 hash 的 name 就拋例外。

**牽涉：** S-01（請求／回條與回合總結失真）、S-06（邊緣失敗隔離）、S-09／S-10（同回合應啟動任務被跳過）、S-23（下一個 tick 審核）。

**證據：** [additional-results.json](additional-results.json) 的 `daemon-bad-name`（含 daemon log、status、birth、回條、rounds）；[results.json](results.json) 的 `name-list`；重跑 [additional.py](additional.py)、[probe.py](probe.py)。

## 新發現 2：不同合法 node 共用自動掛載名，第二個對象永久被衝突拒絕〔bug〕

**重現步驟：**

1. 建 `sender`、`a/b`、`a_b` 三個 node；sender 是 fake agent，`mount_allow: ["a", "a_b"]`，出生不預掛。
2. sender 的 goal 寫 `{"say_first":{"to":"a/b","body":"hello first"}}`，跑 8 回合。
3. 再寫 goal 寄給 `a_b`，繼續跑 8 回合。

**看到什麼：** 第一封送到 `a/b/inbox`；birth 的掛載名是 `a_b_inbox`。第二個合法目標 `a_b/inbox` 也自動變成同一名字。mount-done 回 `ok:false`，原因為「名字 a_b_inbox 已經掛了別的（a/b/inbox）」；信移到 sender/outbox/failed，`a_b/inbox` 沒信。兩者均在允許清單，錯誤由自動名稱推導造成，使用者沒有自行給衝突別名。兩個不同路徑的回條又共用同一檔，後來拒絕回條蓋掉先前成功回條。可以手動另取名字加掛第二個對象，但 agent 的正常 send 無法自行解決。

這不同於既有 M-8（被拒回條不重試）；M-8 解釋其持續性，沒有記錄正常有效收件人因自動名稱碰撞而首次被拒。也不同於刻意指定同名的正確拒絕。

**牽涉：** S-14（node id 以相對路徑表示）、S-23（跨 node 掛載通訊）、S-01（需了解內部命名轉換才能排錯）、S-19（agent send）。

**證據：** [additional-results.json](additional-results.json) 的 `first-auto-name` 與 `second-auto-name`，含兩個收件匣、birth、回條與失敗信件；[additional.py](additional.py)。

## 新證據：restart 前未審核的請求留在已死任務，沒有終態回條〔技術選型〕

**重現步驟：** worker 已成功掛載 allowed/a 等目標；把 `pending.json` 加掛請求與 `ctl.json: {"op":"restart"}` 同時放入任務，下一個 tick 後再跑 3 回合。

**看到什麼：** 第 24 回合新 worker-r24 取得既有全部 4 個掛載（符合 spec／M-9）；舊 worker-r1 的 pending.json 卻一直留在舊目錄，新任務沒有該請求／掛載／回條。因 ctl 在加掛前執行，舊任務已結束；之後只處理活任務的請求。拒絕回條也不搬進新任務，符合已知 M-8。只看舊 mount-req 的 pending 無法分辨「尚未審」與「再也不會審」，要再讀 exit 與 restart_of。

**牽涉：** S-01、S-17、S-23。核心未要求 generic task 的未審請求跨 restart 接續，因此列技術選型／新證據，不逕判 bug。此實驗是一般任務，不能推論 agent outbox 一定會遺失；agent 可能自行重請。

**證據：** [results.json](results.json) 的 `restart-with-pending`、`pending-after-three-more-ticks`。

## 覆蓋與沒有另報的項目

| 案例 | 結果 |
|---|---|
| 語法錯誤、[]、null、字串、數字 | 均有 `ok:false` 回條；語法錯誤內容被歸為 raw:null，沒有拖垮 tick。 |
| 空物件、path 陣列／物件、name 數字、斜線／點開頭名字 | 均正常拒絕；name 空字串按省略處理，自動命名。 |
| 絕對目標、../ 逃出根 | 正常拒絕。 |
| mount_allow 前綴邊界 | allowed/ 不給 allowed_evil/a；不會單純字串誤放行。 |
| 同名同目標重複請求 | `ok:true / 已經掛了`，沒有重複連結。 |
| 同名異目標請求、同 tick 競爭同名 | 後者拒絕，先成功的掛載保留；同 tick 依請求檔名字母順序。 |
| 同一請求檔名再次人工寫入 | 新內容有被處理、覆寫同名回條；M-8 的不重請在 helper，不是 tick 禁止人工再寫。 |
| 已掛載 restart | 全部 4 個成功動態掛載移到新 tid，at 更新為新位置。 |
| 非 .json 副檔名 | 不掃描，照 spec 的 *.json 協議；不列 bug。 |

## 清理證明

兩支腳本都在 finally 透過 task ctl kill／daemon stop+kill 收尾，再以 `/proc/<pid>/stat` 排除已死／殭屍程序；全部 `alive: []`。主 probe 不需要緊急 SIGKILL（`live_before_emergency_kill: []`）。三個 `/tmp/astra2-requests-*` 目錄皆 `root_removed: true`；daemon 正常 exit 0。證明保留於兩份 results 的 cleanup 欄。
