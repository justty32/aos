← [daemon](README.md)｜[spec 總導航](../README.md)

# 6. 主人的一生

```text
aos-daemon boot [--target D]                  # （09-24 fix-r4 改）跑 daemon（前景程式）
aos-daemon halt [--target D] [--wait-ms N]    # （09-24 fix-r4 改名，原 stop）放 stop、等它退出
aos-daemon -h ／ aos-daemon boot -h ／ aos-daemon halt -h
```

（09-24 fix-r4 改）裸 `aos-daemon`（沒子命令）不再直接跑 daemon：stderr 印用法、退 2。`boot`／`halt` 的 D 一樣找：
`--target D`，其次 `AOS_DAEMON_HOME`，再其次目前資料夾；`--target ""`＝用法錯 2。退 1 的錯誤行尾巴附
`（D＝<絕對路徑>，取自 --target｜AOS_DAEMON_HOME｜目前資料夾（…））`，講清楚這次用了哪個家。

（09-24 補）`halt`（原 `stop`）：先用 flock 探測 daemon 活不活——**不活就不放檔**（放了會讓下一任一開機就停）、印 `not running`、退 0；
活的就照範式 §3.1 往 `D/requests/` 放一則 `stop-*.json` notification，等到 flock 探測不到它、印 `stopped`、退 0。
`--wait-ms` 預設 30000，逾時 stderr `Timeout`、退 1（stop 已放、不撤回）。

## 6.1 啟動

（09-24 試玩 r1 補）**開之前先想好環境**：daemon 拉的每顆 cpu、cpu 跑的每件工作都繼承 daemon 啟動那一刻的環境。
所以 PATH 要先含 `proto5/cli`（`aos-cpu`、`aos-exec`、`aos-kernel`、`aos-agent`、`aos-llm` 都靠 PATH 找）再開 daemon：

```sh
export PATH=/abs/repo/proto5/cli:$PATH
aos-daemon boot --target D 2>>daemon.log &              # 前景程式，放背景或另開終端
aos-kernel check --target K --daemon-target D           # boot 前檢查 PATH、池、llm 設定（kernel.md §6）
```

daemon 開了之後再 `export` 不會影響它；PATH 漏了就停掉 daemon 重開。

1. 建家（缺的目錄）、讀驗或寫預設 `info.json`；忽略 `SIGPIPE`。
2. 拿 `.daemon.lock` 的獨占 flock（持到退出）。拿不到＝同家已有一支 daemon 在跑 → `AlreadyRunning`、退 1。
   這是 daemon 這一層唯一的一把鎖（09-24 fix-r4 改措辭：agent 家另有同樣做法的 tick 鎖）：它綁的是 daemon 行程的壽命（行程死鎖就消失），不是跨檔交易，
   所以沒有「鎖沒人解」的問題；外人也靠它探測 daemon 活不活（§1）。
3. **等上一任的孩子死透**：讀舊 `state.json`，對每個記錄的 pid 用 `kill(pid, 0)` 看還在不在——在的
   就送 TERM、等 **`stop_wait_ms`＋`kill_wait_ms`**、還在就 KILL 整組，直到全部不在（這是接手專用的等法，
   跟 §5 正常停機的階梯不同：pipe 已經沒了，沒得先好好說）。注意兩件事：
   (a) 那個 TERM 對孩子來說可能是「第一次」（它還沒讀到 EOF）、只會溫和停，所以才等兩段加起來的時間，最後可能落到硬砍；(b) 上一任 daemon 死後它的孩子歸 init 管、死了 init 會收屍，
   所以 `kill(pid,0)` 看到「不在」就是真的不在了（09-24 補：不會收孤兒的 PID 1 環境，不在接手完成保證內）。pid 被別的程式重用的機率當作可忽略，寫在這裡讓人知道。
   上一任 fork 了、還沒寫表就死的孩子不在表裡——但它等不到 `go`、自己就退了（§2），不用找。
4. 照範式 §6.2 對帳自己的 `current`（上一任崩在處理哪則 request）。
5. 寫新 `state.json`（pid、`current` null、children 空）。孩子表**從空開始**：daemon 不收養；要什麼孩子由客戶再
   `spawn`。
6. 進 §4 的迴圈。

## 6.2 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停機（§5 走完） |
| 1 | 家、info 讀驗、鎖（`AlreadyRunning`）、state 寫不進去；stderr 一行 `aos-daemon: <代號>: <白話>` |
| 2 | 用法錯 |

一則 request 自己的錯誤回在 response 裡，不影響退出碼。
