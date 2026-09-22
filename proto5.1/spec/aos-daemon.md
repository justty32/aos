# aos-daemon 與 ctl：程式規範

← [README](../README.md)｜格式：[daemon-home](daemon-home.md)｜反覆執行：[aos-run](aos-run.md)

```sh
aos-daemon [--home PATH]
aos-daemon-ctl [--home PATH] add FILE.json [aos-run 數值旗標] [--kill-tree]
aos-daemon-ctl [--home PATH] rm FILE.json
aos-daemon-ctl [--home PATH] ls
aos-daemon-ctl [--home PATH] stop
```

daemon 在前景執行，由呼叫者決定是否放背景。ctl 的 FILE 相對呼叫者 cwd 轉成絕對路徑，
保留符號連結路徑，不把 kernel 的 CPU 槽固定到某一個行程。只支援 JSON inst 目標。

## 一輪

1. 收已退出的 runner；檢查正在停止者的下一個訊號期限。
2. 按檔名處理 requests。add 建 runner 家，再啟動新 session 的 aos-run；
   傳 `--home <D>/runners/<名>`，kill_tree=true 時加 --kill-tree。
   stdin=/dev/null、stdout／stderr 追加 daemon.log；只傳允許的數值旗標，不解析 inst。
   runner 的 AOS_DAEMON_HOME 設成實際 daemon 家，讓 kernel tick 找回同一處。
3. remove 標 stopping，送第一個 TERM；請求留 pending，直到 runner 退出才回 entry。
   其他 runner 和請求照常推進，不為每份 remove 阻塞主迴圈。
4. 原子保存 state，輪詢間隔 20 ms。daemon 不接執行事件、不代讀 run.json。

## 停止

SIGTERM／SIGINT 或 stop 請求標全域 stopping，向全部 runner 同時開始停止程序。
停止時拒絕新 add／remove，繼續收屍；剛好在啟動與登記之間收到停止訊號，新登記者也補上停止。

| runner 的 kill_tree | 停止階梯 |
|---|---|
| false（預設） | TERM → 等 5 秒 → 再 TERM → 再等 5 秒 → KILL runner group |
| true | TERM → 等 5 秒 → KILL runner group |

預設第一次 TERM 讓目前工作做完，第二次請 runner TERM 直接子程式那組。
開 kill_tree 時第一次 TERM 讓 runner 走 exec 的後代快照、TERM／兩秒／KILL。
所有 runner 各自有期限，並行停止，不會每支串行累加五秒或十秒。
runner 如果已退出就直接收屍，不繼續發下一階段訊號。

daemon 只能 KILL runner 的 group；其他 session 能不能收掉，取決於 runner 是否執行過相應清理。
runner 被凍結或突然 KILL 不能保證已清子孫；預設不開 kill_tree，本來就允許其他 session 活下去。

全清空後 state 寫 pid=0／runs={}、移除 daemon.pid，才回覆 stop。
磁碟 I/O 失敗導致 daemon 退場也先停所有已登記 runner，原請求可能保留。
runner 自行達到 max-runs／stop-exit 也會收屍、移出 state。

ctl ls 直接讀 state。其他指令送件後最多等同名 done **15 秒**，足夠容納預設停止的 5＋5 秒
與發布回音；request 的 timeout 可由呼叫者指定。逾時回 ReadFailed、請求保留，不能據此說 op 沒發生。
成功時 ctl stdout 印一行 result JSON；daemon stdout 不印內容。

## 退出碼與錯誤

0 成功／正常停止；1 家、讀驗、I/O 或 daemon 拒絕；2 argparse 用法錯。
1 的 stderr 是一行 `aos-daemon: <代號>: <白話>`；ctl 同樣使用此格式。

| 代號 | 情況 |
|---|---|
| NotAHome | home 不是資料夾；ctl 缺 requests／done |
| ReadFailed | 讀寫失敗或等 done 逾時 |
| JsonSyntax | JSON 語法／UTF-8 壞了 |
| FieldTypeMismatch | state、op／target／args／kill_tree 型別或範圍不合 |
| NotRunning | daemon 沒持鎖、target 未登記、或正在停止 |
| AlreadyRunning | 同家已有 daemon、或 target 已登記 |

壞請求在 done 收到錯誤，daemon 繼續服務。兩支 daemon 同家靠 .daemon.lock 排他；
不靠舊 PID 判斷身分或殺程序。重啟從空表開始，不收養、不掃 PID 猜身分。

## Python API

```python
home(path=None)
read_state(path=None)
request(op, target=None, args=None, home=None, timeout=15, kill_tree=False)
serve(path=None)
main(argv=None)
ctl_main(argv=None)
```

home 回實際家的絕對 realpath。read_state 讀驗最後快照，不要求 daemon 還活著。
request 回 result，失敗丟帶 code／msg 的 DaemonError；ls 就是 read_state，
remove 回收屍後 entry，stop 等全部收尾。serve 正常回 0。
