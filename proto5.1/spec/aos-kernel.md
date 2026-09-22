# aos-kernel：普通 inst 的輪轉排程器

← [README](../README.md)｜格式：[kernel-home](kernel-home.md)｜下層：[aos-daemon](aos-daemon.md)、[aos-run](aos-run.md)

實作：[`lib/aos_kernel.py`](../lib/aos_kernel.py)，入口 [`cli/aos-kernel`](../cli/aos-kernel)。只用 Python 標準庫與本目錄模組，不 import proto4-3。

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

init 拒絕覆蓋既有目錄，產生 kernel 家與每個 slot 的 stable lock。boot 把 K/inst.json add 進 `AOS_DAEMON_HOME` 指定的 daemon（預設 `~/.aos-daemon`）；kernel 與工作 CPU 的 aos-run 都由該 daemon 管。重複 boot 報 AlreadyRunning，沒有隱含 restart。add 解驗完整 proto5 inst，回印 NAME；不建立 agent 特例。rm 交 syscall 並等最多 10 秒，回音保留在 syscalls/done。ls 直接讀 kernel／daemon 快照，印 CPU、行程、running、完成次數、最新退出碼、waiting、bad count、queue、done、bad；沒有固定欄寬。

退出碼 0＝完成命令或 tick 無事可做；1＝讀驗／執行／daemon 錯誤；2＝用法錯。不會為 idle tick 回 101（101 是排程中的一般行程可回的等待碼）。stderr 一行 `aos-kernel: <代號>: <白話>`；代號 NotAHome／ReadFailed／JsonSyntax／FieldTypeMismatch／NotRunning／AlreadyRunning。inst 的詳細錯誤附在白話中，解驗型別／指示詞錯誤歸 FieldTypeMismatch。

## 每格 tick

沿舊版順序收斂成以下 12 步；沒有 module 階段，對 daemon 的補 CPU 與換 runner 合在排程尾端做，避免先啟動空閒 runner 又立刻停掉。

1. 讀驗 info，取得 `.kernel.lock`；已有 tick／add 持鎖就退 0。
2. 讀驗 state，拒絕重複 CPU 指派或超出 ncpu 的狀態。
3. 讀 daemon 快照。daemon 不在時報錯，不猜舊 runner 是否已死。
4. 處理 syscalls；只有 rm。CPU 還 running 或 slot 鎖拿不到時留單等下一格。
5. 逐份完整讀驗 procs inst；解不開搬 bad，成功固定 cwd／路徑與選項。
6. 維護 FIFO queue：既有名字保序，新檔按數字名數值順序（再接文字名）排尾，消失的移除。
7. 對 CPU 觀察新完成次數；更新 waiting、bad_runs、aos_ticks。換 runner 的次數基線歸零，行程連敗保留。
8. 判 done_exit 完成（至少一次可確定屬於本指派的結果）；aos 連續兩次或一般連敗 bad_after 達標退 bad。
9. 等待行程（101）且有人排隊就讓位；否則跑滿 quantum 次且有人排隊才換人。沒人排隊繼續跑。
10. 要換人時先在既有 slot 鎖檔首 byte 寫 `Y`，請 runner 完成本格後等候下一格。**再看 entry.running；true 這格不換。false 還要拿穩定 slot 鎖的 LOCK_EX|LOCK_NB，拿不到一樣不換。**
11. 持 slot 鎖 remove 舊 runner，等 daemon 回音與最終 entry；再觀察最後幾次完成並判 done／bad。舊 proc 搬回 queue 或退休，新 proc 搬到 slot，保存 state，鎖內清空 `Y`；add 新 runner 後讓它下一次執行。缺 runner 的 CPU 同樣補 add。remove 失敗不清意圖、不搬檔。
12. 原子保存 state、append kernel.log，退 0。I/O 或 daemon 操作失敗退 1；不聲稱中途無部分變更。

## 為何不只看 running

state.json 是快照：kernel 看見 running=false 之後，aos-run 可能立刻開始下一次。僅靠讀旗標再 replace，會讓舊行程還沒結束便在另一顆 CPU 開始。直接 rm/add 雖然擋重疊，也可能 TERM 掉剛開始的合法工作。

因此 init 建 `cpus/N.json.lock`，aos-run 只對**已存在** sidecar 的目標每輪取得排他鎖，從讀目標前持到 done 事件寫完。鎖檔首 byte `Y` 是請求讓位；run 取得鎖後看到 Y 便先解鎖等候，不開始下一格。kernel 的非阻塞同鎖證明此刻沒有工作在執行，再 remove runner；此時 runner 只能在間隔睡眠或等鎖，TERM 不會截斷一個 inst。remove 回音證明舊 runner 已退出且事件排空，換檔後重建 runner 也讓舊 done 不會被算到新 proc。沒有新增公開旗標、daemon op 或 entry 欄位。

只用鎖仍不能防排程飢餓：interval_ms=0／短間隔讓 kernel 可能始終讀到 running=true。Y 意圖讓工作完成後的 false 狀態保持到下一格 kernel，因而無須碰運氣抓瞬間空檔；running=true 當輪仍不換人。意圖取消必須拿 slot 鎖後清空，I/O 失敗報錯。kernel 崩在寫 Y 之後可能讓 runner 在格間等待，重新 tick 可完成或取消這個意圖。

sidecar 只協調遵循這個協議的 aos-run 與 kernel；不鎖使用者繞過 kernel 直接執行 agent 的情況，也不把「不同 NAME 指向同一 agent 家」認作同一行程。kernel 崩潰或有人手改 CPU 檔不在自動恢復保證內。

## 與 proto4-3 的差異

config.json 改為可解指示詞的 info.json，六個子命令合到一個入口；沒有 module、pause／resume／restart 或舊獨立 init／boot／tick 程式。完整 inst 先解後驗，不檢查 raw argv／cwd。bad_after 計數跟 proc 搬家；slot 鎖加停止回音封住快照競態，無兩顆 CPU 同跑同名 proc。done／bad 判定不再靠兩次 dummy 執行避舊事件，因每次切換已確認 runner 終止並重設次數基線。
