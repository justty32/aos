# aos-daemon 與 ctl（程式規範，第 1 版）

← [README](../README.md)｜格式：[daemon-home](daemon-home.md)｜反覆執行：[aos-run](aos-run.md)

```sh
aos-daemon [--home PATH]
aos-daemon-ctl [--home PATH] add FILE.json [aos-run 旗標]
aos-daemon-ctl [--home PATH] rm FILE.json
aos-daemon-ctl [--home PATH] ls
aos-daemon-ctl [--home PATH] stop
```

daemon **在前景執行**，由呼叫者決定是否放背景。ctl 的 FILE 相對呼叫者 cwd，轉成絕對 realpath
再交件；只支援 JSON inst 目標。旗標／家／回音欄位見格式規範。

## 一輪與停止

1. 讀各 runner 的非阻塞 status pipe，按行處理 ready／start／done／stop；收已退出 runner。
2. 按檔名處理 requests。add 建新 session 的 aos-run，stdin=/dev/null、stdout／stderr 追加 daemon.log。
   args 只傳允許的 run 旗標，status-fd 用專用 pipe；daemon 不解析 inst。
   runner 環境的 AOS_DAEMON_HOME 設為實際家（含 --home 覆蓋），讓其啟動的 kernel tick 回到同一 daemon。
3. remove 先標 stopping、TERM runner group，請求留 pending，直到 runner 退出才寫最後 entry 回音。
   其他 runner 和請求照常推進，不用執行緒，也不為每個 remove 阻塞主迴圈。
4. 原子保存 state，閒置輪詢間隔 20 ms。這是輪詢，不承諾固定時鐘或每個事件都能被讀者看見。

SIGTERM／SIGINT 或 stop 請求會標全域 stopping，**同時 TERM 所有 runner**；正在停止時拒絕新 add／remove，
仍收事件。各 runner 從 TERM 時算 **5 秒仍未退出就 KILL group**，不是每支串行等 5 秒。
aos-run 正常會立即轉送 TERM 至 inst group，2 秒後 KILL，包含它負責追蹤的子孫；
daemon 的 5 秒是 runner 失去反應時的最後保險。程序主動另開 session、或 runner 被不可恢復地
凍結／KILL 時，不能只靠 runner group 推論已涵蓋所有其他 session，界線見 aos-run。

全清空後 state 寫 pid=0／runs={}，移除 daemon.pid，才回覆 stop。
磁碟 I/O 失敗導致 daemon 退場時也先停所有已登記 runner；原請求可能仍在。
正常 runner 自行達到 max-runs／stop-exit 也會被收屍、從表移除。

ctl ls 直接讀 state。其他指令原子送件，最多等同名 done **10 秒**；逾時退 ReadFailed、請求留著，
不能把「ctl 沒等到」推論成 op 沒發生。ctl 成功 stdout 印一行 result JSON，daemon stdout 不印內容。

## 退出碼與錯誤

0 成功／正常停止；1 家、讀驗、I/O 或 daemon 拒絕；2 argparse 用法錯。
1 的 stderr 固定一行 `aos-daemon: <代號>: <白話>`，ctl 也用相同前綴。

| 代號 | 情況 |
|---|---|
| NotAHome | home 不是資料夾；ctl 缺 requests／done |
| ReadFailed | 讀寫失敗或 ctl 等 done 超過 10 秒 |
| JsonSyntax | JSON 語法／UTF-8 壞了 |
| FieldTypeMismatch | state、請求 op／target／args 型別或範圍不合 |
| NotRunning | daemon 沒持鎖、target 未登記、或 daemon 正在停止 |
| AlreadyRunning | 同家已有 daemon、或 target 已登記 |

壞原始請求會在 done 收到具名錯誤，daemon 繼續服務；不把每份壞請求當 daemon 自己的退出。
兩支 daemon 同家以持續存在的 .daemon.lock 排他，不靠 pid 存在就誤殺別的進程。
重啟從空表開始，不收養、不掃 pid 猜身分；先前異常崩潰的 runner 要由操作者清理。

## Python API

```python
home(path=None)                      # 環境／預設路徑，回絕對 realpath
read_state(path=None)                # 讀驗最後快照，不要求 daemon 活著
request(op, target=None, args=None, home=None, timeout=10)  # 回 result；失敗丟 DaemonError
serve(path=None)                     # 前景迴圈，正常回 0
main(argv=None)
ctl_main(argv=None)
```

DaemonError 帶 code／msg。request("ls") 就是 read_state；remove 回最後 entry，讓 kernel
在取得 CPU slot 鎖後停止 runner並收齊最後事件，再換檔。沒有 pause／resume／restart／get。
