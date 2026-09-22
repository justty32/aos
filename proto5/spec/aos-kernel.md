# aos-kernel：普通 inst 的輪轉排程器

← [README](../README.md)｜格式：[kernel-home](kernel-home.md)｜下層：[aos-daemon](aos-daemon.md)、[aos-run](aos-run.md)

> 這份是 proto5.1 做出來的版本（2026-09-22 回流，照 [23 題拍板](../notes/2026-09-22-decisions.md)）。**proto5 的程式還沒照這份實作**；能跑的實作在 [proto5.1/lib](../../proto5.1/lib/README.md)。

實作：[`lib/aos_kernel.py`](../../proto5.1/lib/aos_kernel.py)，入口 [`cli/aos-kernel`](../../proto5.1/cli/aos-kernel)。只用 Python 標準庫與本目錄模組。

## 命令列

```sh
aos-kernel init K --ncpu 3
aos-kernel add K path/to/inst.json --name agent
aos-kernel boot K
aos-kernel ls K
aos-kernel rm K agent
# tick 只接受 cwd，不接受 K 參數：
(cd K && /absolute/path/to/aos-kernel tick)
```

init 拒絕覆蓋既有目錄，產生 kernel 家。boot 用 `AOS_DAEMON_HOME` 選 daemon（預設 `~/.aos-daemon`），
先驗 daemon 身分，把絕對家路徑存入 K/info.json 的 daemon，再把 K/inst.json add 進去；kernel 與工作 CPU 的 aos-run 都由該 daemon 管。重複 boot 報 AlreadyRunning，沒有隱含 restart。boot 先確認目標 daemon 正持鎖；綁定相同不重寫 info，交件拋錯時恢復原 info。這不是跨檔交易，等回音逾時仍不能據此認定 add 沒發生。add 解驗完整 inst，回印 NAME；不建立 agent 特例。rm 交 syscall 並等最多 10 秒，逾時回 ReadFailed；回音保留在 syscalls/done。

tick／ls／rm 都從 K/info.json 的 daemon 找家，先驗其 info 身分，不再看環境變數。
未 boot 的 tick／rm 回 NotRunning；ls 顯示 daemon=None，不自行找預設家。
ls 讀 kernel state 與 daemon state，再依 daemon entry 的 home 讀各 runner 的 run.json，印 CPU、指派行程、busy、完成次數、最新退出碼、waiting、bad count、queue、done、bad；沒有固定欄寬。RUNNING 欄是 run.json 的 busy，PROC 是目前指派，兩者可能屬於換人前後不同工作。daemon state 讀不到時 ls 仍可顯示 daemon=None。

退出碼 0＝完成命令或 tick 無事可做；1＝讀驗／執行／daemon 錯誤；2＝用法錯。不會為 idle tick 回 101。stderr 一行 `aos-kernel: <代號>: <白話>`；代號 NotAHome／ReadFailed／JsonSyntax／UnsupportedVersion／FieldTypeMismatch／NotRunning／AlreadyRunning。inst 的詳細錯誤附在白話中，解驗型別／指示詞錯誤歸 FieldTypeMismatch。

## 每格 tick

1. 讀驗 info，取得 `.kernel.lock`；已有 tick／add 持鎖就退 0。
2. 讀驗 state，拒絕重複 CPU 指派或超出 ncpu 的狀態。
3. 驗已記錄的 daemon 家並讀 state；只看最後快照的 pid 欄，為 0 就報 NotRunning，不探測 PID 是否存活。
4. 處理 rm syscalls：直接撤掉 CPU 目標並移除行程，無須等 runner。
5. 完整讀驗未指派的 procs inst；解不開搬 bad，成功固定 cwd／路徑與選項；與原內容相同就不重寫。
6. 維護 FIFO queue：既有名字保序，新檔按數字名數值順序（再接文字名）排尾，消失的移除。
7. 從 daemon entry.home 讀 run.json。last_target 對得上目前行程，才觀察新完成次數及 last_*，更新 waiting、bad_runs、aos_ticks。
8. 判 done_exit 完成；aos 連續兩次或一般連敗 bad_after 達標退 bad。等待行程且有人排隊就讓位；否則跑滿 quantum 次且有人排隊才換人。沒人排隊繼續跑。
9. 要換人便先原子把 CPU 連結換成指向固定的 K/idle.json，原行程退回 queue 或搬入 done／bad。換檔不停止、不重建 runner。
10. 從 queue 取候選 X；**每次排 X 之前，重新讀每顆 CPU 的 run.json。只要某顆 busy=true 且 target 是 X 的絕對路徑或 null，本格跳過 X，留在 queue 下格再看。** 其他候選照序試。run.json 尚未出現視為 busy=true、target=null。
11. 沒有擋住 X 才建立指向 procs/X.json 的臨時 symlink，rename 成 cpus/N.json，保存指派。缺 runner 才向 daemon add，帶 interval／timeout 及 kill_tree。
12. 原子保存 state、append kernel.log，退 0。I/O 或 daemon 操作失敗退 1；中途可能已有部分變更。

## 為何能擋同名重疊

run 保證先寫 busy=true、target=null，再讀目標；確定目標後才寫絕對路徑並讀 inst，而且解析與執行用同一個已確定的路徑；CPU 一律是 symlink，連 idle 也指向固定檔，解析後不再讀可換人的槽路徑。kernel 保證先撤掉 X 的舊 CPU 目標，再讀各 run.json：舊 runner 若已取到 X，會被 busy 的 X／null 擋住；若尚未開始讀，它之後只能讀到換好的目標。這兩個順序搭配，X 在舊 CPU 完成前不能排去另一顆，換檔本身則隨時可做。

只有 kernel 的 tick／add 共用一把家鎖以免兩個排程者同時改指派。這個保證限於遵循協議的 runner 與 kernel；不會攔住使用者直接執行同一 inst，也不把不同 NAME 指向同一 agent 家視為同一行程。kernel 崩潰或有人手改 CPU 檔不在自動恢復保證內。

## 次數與結果

quantum 看 runs 減這次指派的基線，busy 時也能決定換人，因此 interval=0 不必等一個碰巧看見的空檔。結果判定用 last_target 相符的新快照，busy=true 也能收一次；基線排除換人當下還在跑的前一人。每個新且可確定的結果快照只計一次：讀基線到換檔之間可能夾著 idle，runs 差值不能全算本行程的失敗。這讓前一人的完成碼與未知完成次數不會讓新行程誤退，同格多次與換下後的結果仍可能漏記；沒有每次執行的歷史。
