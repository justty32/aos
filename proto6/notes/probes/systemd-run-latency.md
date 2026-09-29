# systemd-run 開短命程序的延遲實測

← [探針說明](README.md)　·　[三條降低延遲的路](../2026-09-29-verdicts.md)

2026-09-29 實測。問題：daemon 若每次工具呼叫都用 `systemd-run --user` 開一個 once 工作，比直接開程序多花多少？

## 機器

- CPU：AMD Ryzen 7 9800X3D（8 核 16 執行緒，`nproc` = 16）
- systemd 261（261.2-1-manjaro）、kernel 6.18.49-1-MANJARO、Manjaro
- 使用者 systemd（`systemd-run --user`），沒用 sudo、沒碰系統層。閒置桌面，沒有別的重負載。

## 方法

腳本：[systemd-run-latency.py](systemd-run-latency.py)。重跑：`python3 proto6/notes/probes/systemd-run-latency.py 200`（參數是每項次數）。

- 每項跑 200 次，序列執行（一次量一個），量「從 Python 開始呼叫到子程序結束被收回」的牆鐘時間，取中位數、p90、最大值。
- 目標程序 `/bin/true`，另用 `python3 -c pass` 對照（Python 自己啟動就要約 5.6 ms）。
- 全部加 `--quiet`；2、4、5、6 都是 `--wait --collect`，scope 沒有 `--wait`。
- 第 4 項限制：`-p MemoryMax=512M -p CPUQuota=50% -p TasksMax=64`。
- 第 7 項：10 個執行緒同時一直呼叫，跑 200 次，算總共每秒完成幾個。
- 第 8 項：小 git repo 裡，每次改一個小檔案後 `git add -A && git commit`，共 200 次，commit 數有核對。
- 跑完沒有殘留 unit（`--collect` 或 `--scope` 自己會收；腳本結尾也對自己命名的 unit 做 reset-failed）。

## 數字（毫秒，N=200）

`/bin/true`：

| 方式 | 中位 | p90 | 最大 |
|---|---|---|---|
| 1 直接 fork/exec | 0.1 | 0.2 | 0.3 |
| 2 `run --wait --collect` | 4.9 | 5.1 | 22.4 |
| 3 `run --scope` | 2.4 | 2.6 | 2.8 |
| 4 = 2 加 MemoryMax／CPUQuota／TasksMax | 24.3 | 35.4 | 47.9 |
| 5 = 2 加 `KillMode=control-group` | 4.9 | 5.1 | 19.8 |
| 5b = 2 拿掉 `--collect` | 4.9 | 5.3 | 5.8 |
| 6 `run --pipe --wait --collect` | 5.0 | 5.2 | 6.5 |

`python3 -c pass`：

| 方式 | 中位 | p90 | 最大 |
|---|---|---|---|
| 1 直接 fork/exec | 5.6 | 5.8 | 6.3 |
| 2 `run --wait --collect` | 10.0 | 10.3 | 24.4 |
| 3 `run --scope` | 7.8 | 8.1 | 9.7 |
| 4 加資源限制 | 32.2 | 44.4 | 52.2 |
| 5 加 `KillMode=control-group` | 10.1 | 11.0 | 30.9 |
| 5b 拿掉 `--collect` | 10.2 | 10.8 | 27.7 |
| 6 `--pipe` | 10.3 | 10.7 | 25.4 |

並發 10 的吞吐（每秒開幾個）：

| 方式 | 每秒 |
|---|---|
| 直接 fork/exec `/bin/true` | 約 12100 |
| `systemd-run --wait` `/bin/true` | 約 450 |
| `systemd-run --wait` `python3 -c pass` | 約 290 |

git 對照（第 8 項）：`git add -A && git commit` 小變動，中位 1.9、p90 2.0、最大 2.5。

## 白話結論

- 用 `systemd-run --user --wait` 開一個短命程序，比直接開多約 5 毫秒（中位數 4.9 對 0.1）。`--scope` 約多 2.4 毫秒。
- 加資源限制（記憶體、CPU 配額、程序數）是最大的一筆：多約 20 毫秒，p90 到 35 至 44 毫秒，約是沒加時的五倍。三個限制是一起加的，這次沒有拆開量哪一個最貴。
- `--collect`、`KillMode=control-group`、`--pipe` 對中位數沒有可見差別（都在 5 毫秒上下）。偶爾會有 20 多毫秒的離群一次，在有 `--collect` 的組別比較常見，原因這次沒查。
- 同時 10 個一起開，systemd 這邊每秒約完成 450 個（`/bin/true`），比序列跑（1000 / 4.9 約 200 個／秒）高，但遠低於直接開的 12000 個／秒。可見 systemd-run 有共同的瓶頸（可能是使用者 systemd 主程序處理 unit 的速度，這次沒證實）。
- 這台機器上，一次 `git add` 加 commit 只要約 2 毫秒，比一次 `systemd-run` 還便宜。

對三條路的第 3 條的意義（只陳述數字）：
- 那條寫「若每次多等幾百毫秒，就考慮讓工具在 agent 那格 tick 裡直接跑」。在這台機器上，多等的只有約 5 毫秒（不加限制）到約 25 毫秒（加三個限制），沒有到幾百毫秒。
- 限制要不要每次工具呼叫都加，決定多的是 5 還是 25 毫秒。
- tick 的長度沒在這裡量，要和 tick 比較請以 spec 為準。

## 沒量到的、要小心的

- 這是一台強的桌機（9800X3D、閒置），較慢的機器或有其他負載時數字會變大，這次沒模擬。
- 量的是「開一個立刻結束的程序」；真正的工具本身的執行時間不在內。
- 只量了 `--user`；系統層 `systemd-run`（切帳號用的那種）沒量，因為不能用 sudo。
- git 的 repo 很小、快取是熱的；大 repo 或冷快取會慢得多。
