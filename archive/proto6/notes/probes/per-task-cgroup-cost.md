# 每任務一層 cgroup 的成本實測

← [探針說明](README.md)　·　[systemd-run 延遲](systemd-run-latency.md)

2026-09-29 實測。問題：tick 連續跑很多任務，每個任務跑完要確認沒留子程序。A「共用一個葉子」和 B「每任務開一層」各多花多少？

## 機器

- 同 [systemd-run 延遲](systemd-run-latency.md)：9800X3D、kernel 6.18.49、Manjaro、一般使用者、沒用 sudo、閒置桌面。
- 用 `systemd-run --user --scope -p Delegate=yes` 拿委派 cgroup；probe 先把自己搬進 `node/tick`，任務的層開在 `node/task-N`。

## 方法

腳本：[per-task-cgroup-cost.py](per-task-cgroup-cost.py)。重跑：`python3 proto6/notes/probes/per-task-cgroup-cost.py 200`。

- 任務都是 `/bin/true`，各 200 次（先暖機 20 次），序列執行，量牆鐘時間。
- 基準：fork+exec `true`+waitpid。
- A：fork+exec、waitpid，讀 `tick/cgroup.procs`，除了自己有剩就 kill。
- B：mkdir `task-N`，fork 後子程序自己寫 `cgroup.procs` 搬進去再 exec（Python 沒有 clone3 的 CLONE_INTO_CGROUP，所以用這招；真的用 clone3 只會更省），waitpid 後讀 `cgroup.events` 的 populated，有剩就寫 `cgroup.kill`，最後 rmdir。

## 數字（毫秒，N=200）

| 項目 | 中位 | p95 | 比基準多 |
|---|---|---|---|
| 基準 fork+exec true | 0.378 | 0.440 | 0 |
| A 共用葉子 | 0.405 | 0.476 | 約 0.03 |
| B 每任務一層 | 0.514 | 0.619 | 約 0.14 |
| 　B 裡的 mkdir | 0.012 | 0.018 | |
| 　B 裡的 events+rmdir | 0.033 | 0.063 | |

（跑幾次數字會小飄，但順序不變：A 幾乎不花，B 多約 0.1 毫秒。）

## 白話結論

- 兩種都便宜到可以忽略：每個任務 A 多約 0.03 毫秒，B 多約 0.14 毫秒。B 貴約 5 倍，但絕對值差 0.1 毫秒，比一次 `systemd-run`（約 5 毫秒）小 40 倍以上。
- B 多出來的錢大半在「子程序搬進 cgroup」和「rmdir」，不在 mkdir。
- 成本不該是選擇的理由，要看下面的正確性。

## 定性差別

A 共用葉子：
- 任務 double-fork 後留下一個 `sleep`，任務主程序結束了，那個孫程序還在 `tick/cgroup.procs` 裡，除了 tick 自己的 PID 就是它，實測抓得到。
- 分不出「誰的」：只要 tick 同時還有別的合法子程序（例如同時跑兩個任務、或 tick 自己開的 helper），「PID 不是我就殺」會誤殺；要分辨得另外記 PID 名單，而孤兒被 reparent 後 PID 名單就對不上。
- PID 重用：讀 procs 到 kill 之間，那個 PID 可能已經死掉並被別的程序拿走，`os.kill` 會打錯人（窗口很小，但不是零）。
- 讀 procs 跟 kill 是兩步，中間任務留下的程序可以繼續 fork，殺不乾淨要迴圈重試。

B 每任務一層：
- 誰留下的一目了然：`task-N` 裡有東西就是那個任務留的。
- 清理接近原子：寫 `cgroup.kill` 是由核心一次殺整層（含中途 fork 的），不用讀 PID 名單，沒有 PID 重用問題。實測 kill 到 populated 變 0 約 0.6 毫秒（含輪詢）。
- 但不是完全瞬間：kill 之後 populated 要等一下才變 0，rmdir 在那之前會 EBUSY，所以要輪詢或重試（實測有留 sleep 時就是這樣做）。
- 任務的子程序若被搬離（自己寫別的 cgroup.procs，要有寫入權限）就逃得掉，兩種做法都一樣。

## 沒量到的、要小心的

- 只量了 `true`，沒有量任務本身有很多子程序時的 kill 成本。
- 沒實作 clone3 CLONE_INTO_CGROUP，B 的搬進去這一步用 fork 後寫檔代替。
- 沒量 cgroup 上開了 memory／pids 控制器時 mkdir／rmdir 的變貴程度（前一份實測看到加限制很貴）。
- 閒置強機的數字，慢機器或有負載時會變大。
