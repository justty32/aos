# `knowledge/aos/cli/sweeper.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/sweeper.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-sweeper：為一個 daemon 做一輪清理

它平常是每個 daemon 的 `_sweeper` loop 列在跑（範本裡每 10 分鐘一次）。要自己動手，用 `aos-daemon-ctl sweep`（`aos/cli/daemon.json#/sweep`）或：

```sh
aos-sweeper -d stacks/root --dry-run --min-bytes 1000
# _clock: would archive .../procs/_clock/stderr.txt (4053 bytes) to .../stderr_archives/2026-...Z.txt.gz
aos-sweeper -d stacks/root --report /tmp/rep.json     # also writes the round as JSON
```

一輪，只處理這個 daemon（不會進到子 daemon）：(1) 至少 `--min-bytes`（預設 1 MiB）的 stderr 檔會用 gzip 複製到 `<stack>/stderr_archives/`，並截成 0；(2) 比 `--retention-days`（預設 7；`none` = 保留）舊的封存檔會被刪掉；(3) 只在 daemon 執行中時，`D/procs/NAME/` 裡不在表上、但確定還活著的 loop 會收到 ctl stop，`--stop-grace-s`（預設 300）之後再送 SIGTERM；(4) 舊的、刪到一半的鎖資料夾會被刪掉。對話歷史、帳本（ledger）和 `.trash` 絕不會被動到。另一個 sweeper 拿著鎖 = 結束碼 0。錯誤：`DaemonMissing`、`WriteFailed`。
