# `knowledge/aos/cli/parts/daemon.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/daemon.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-daemon：daemon 本身

它照顧 `daemon.json` 裡的 proc，以及後來透過它的 `procs_requests` 信箱加進來的 proc；可選的自己的 `exec` 身體像 aos-loop 那樣跑。從一個 `_entry` 會跑它的定義啟動 daemon：

```sh
unset AOS_CLOCK AOS_DAEMON AOS_STACK      # a set AOS_DAEMON makes a new root think it is a child
aos-exec --stack stacks/root defs         # defs/_entry: {"argv": ["aos-daemon", "--enable-logs", "daemon.json"]}
AOS_STACK=/tmp/st aos-daemon --max 10 daemon.json   # a short test: 10 rounds, then its procs sleep
```

從 agent 的 shell 啟動 root（它帶著 `AOS_STACK`、`AOS_WS` 等等）：先清掉所有 `AOS_*`，再只把 `AOS_HOME` 設回來。留下任何一個，新的 root 就會用錯資料夾。

旗標跟 aos-loop 一樣（`--max`、`--interval-ms`、`--ctl`、`--state`、`--state-flux`、`--enable-counters`）。它需要 `AOS_STACK`（`StackMissing`）。daemon.json 像 aos-loop 一樣收 `on_start` / `on_stop`（aos/cli/parts/loop.json）：on_start 失敗表示 daemon 不啟動，它的 proc 一個都不啟動；on_stop 失敗會在結束碼本來是 0 時改掉它。`on_before_run`、`on_after_run` 和它們的 `_if` 鍵在 daemon.json 裡是 `CfgBad`。`--enable-logs` 每次 proc 變動印一行 JSON。用 aos-daemon-ctl（`aos/cli/daemon.json`）控制它，用 `aos-daemon-ctl shutdown` 停它。proc 以 0 結束會移除它那一列；已知的非 0 結束會留著、停止狀態；shutdown 讓每個活著的 proc 睡著，下次啟動時把它們叫醒。每個 proc 各自用 `stuck_after_cycles` / `stuck_after_ms` 和 `restart_on_stuck` 處理不回應它 ctl 時窗的 proc。

更多旗標：跑 `aos-daemon --help`。
