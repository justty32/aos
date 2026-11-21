# `knowledge/aos/cli/parts/loop.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/loop.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-loop：一遍又一遍地跑一個主體

```sh
AOS_STACK=/tmp/st aos-loop --max 3 loop.json    # loop.json: {"exec": {"argv": ["sh", "-c", "echo run"]}}
AOS_STACK=/tmp/st aos-loop --interval-ms 100 loop2.json
```

每一輪的結束碼：0 = 再跑一次，10 = 停下並 exit 0，其他 = 以那個碼停下（`aos-loop: error: RunFailed run 1: loop3.json#/exec failed with exit code 4`）。它的 ctl 窗口需要 `AOS_STACK`（`StackMissing`）。`aos-loop CONFIG -- ARGS` 把 ARGS 接到每一輪的 exec 後面。四個可選的點，每個寫法都跟 exec 一樣：

- `on_start` / `on_stop` 只跑一次（在第一輪之前 / 在 aos-loop 快要結束時，SIGKILL 時不跑）；on_stop 拿到 `AOS_LOOP_CODE`、`AOS_LOOP_SIGNAL`（訊號編號或空）和 `AOS_LOOP_CAUSE`（stop、sleep、remove、shutdown、stuck、signal、max、body_exit 或 error）；兩者都受最上層 `on_timeout_ms` 限制（預設 5000，0 = 不限）。
- `on_before_run` / `on_after_run` 在主體每一輪的前後跑（不限時，除非該指令設了 `timeout_ms`）。on_before_run 拿到 `AOS_LOOP_RUNS`；exit 10 跳過這一輪（不算數、沒有 on_after_run，過 interval_ms 後再試）。on_after_run 拿到 `AOS_LOOP_RUNS`、`AOS_LOOP_RUN_CODE`、`AOS_LOOP_RUN_SIGNAL`、`AOS_LOOP_RUN_MS`；非零只在主體 exit 0 時才停下迴圈（不然就一則警告）。
- `on_before_run_if` / `on_after_run_if`：一個檔案路徑；那個點只在檔案存在時才跑。
- 失敗的點（非零、逾時、跑不起來）以 `PointFailed` 和該點的碼停下迴圈：on_start 失敗 = 主體從沒跑過；on_stop 失敗只在結束碼原本會是 0 時才改掉它。

現成範本用 `aos-hook fire` 填這些點（aos/cli/offer_hooks.json）。`--ctl`、`--state`、`--state-flux` 選窗口；在 ctl 窗口寫 `{"cmd": "pause"}`、resume 和 stop 來控制它（aos-daemon-ctl pause 寫的就是這個）。`--enable-logs` 每一輪印一行 JSON；`--enable-counters` 在狀態窗口旁邊寫 counter_runs.txt。agent 和 daemon 的列都是 daemon 啟動的迴圈；你很少自己啟動一個。

更多旗標：跑 `aos-loop --help`。
