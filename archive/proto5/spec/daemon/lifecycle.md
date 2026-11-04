← [daemon](README.md)｜[spec 總導航](../README.md)

# 6. 主人的一生

```text
aos-daemon boot  [--target D]                                     # 跑 daemon（前景程式）
aos-daemon halt  [--target D] [--wait-ms N]                       # 放 stop、等它退出
aos-daemon ls    [--target D] [--pool P] [--json] [--no-busy]     # 看池（§6.3）
aos-daemon scale [--target D] --pool P --count N [--skip I,J...] [--inst PATTERN] [--home PATTERN] [--force]   # §6.3
aos-daemon kill  [--target D] --pool P (NAME... | --all)          # §6.3
aos-daemon -h ／ aos-daemon <子命令> -h
```

（2026-09-24 proto5-2 池式納入：加 `ls`／`scale`／`kill`，全帶 `--pool`；啟動時照 `pool.json` 把孩子拉回來。2026-09-24 one-boot：啟動時也照 `kernels/` 接著開 tick；平常用 `aos up` 開。）

裸 `aos-daemon`（沒子命令）不直接跑 daemon：stderr 印用法、退 2。D 一樣找：`--target D`，其次 `AOS_DAEMON_HOME`，再其次目前資料夾；`--target ""`＝用法錯 2。
退 1 的錯誤行尾巴附 `（D＝<絕對路徑>，取自 --target｜AOS_DAEMON_HOME｜目前資料夾（…））`，講清楚這次用了哪個家。

`halt`：先用 flock 探測 daemon 活不活——**不活就不放檔**（放了會讓下一任一開機就停）、印 `not running`、退 0；
活的就照範式 §3.1 往 `D/requests/` 放一則 `stop-*.json` notification，等到 flock 探測不到它、印 `stopped`、退 0。
`--wait-ms` 預設 30000，逾時 stderr `Timeout`、退 1（stop 已放、不撤回）。停機走批次階梯（§5）；`pool.json` 留著。

## 6.1 啟動

**平常用 `aos up`**（[§11](up.md)）：它會替你在背景開 daemon、PATH 補好、stderr 接到 `D/daemon.log`。下面是自己開的做法（debug 用）。

**開之前先想好環境**：daemon 拉的每顆 cpu、開的每格 tick、cpu 跑的每件工作都繼承 daemon 啟動那一刻的環境。
所以 PATH 要先含 `proto5/cli`（`aos-cpu`、`aos-exec`、`aos-kernel`、`aos-agent`、`aos-llm` 都靠 PATH 找）再開 daemon：

```sh
export PATH=/abs/repo/proto5/cli:$PATH
aos-daemon boot --target D 2>>D/daemon.log &            # 前景程式，放背景或另開終端
aos-kernel check --target K                             # boot 前檢查 PATH、池、llm 設定（kernel §6）
```

daemon 開了之後再 `export` 不會影響它；PATH 漏了就停掉 daemon 重開。

1. 建家（缺的目錄）、讀驗或寫預設 `info.json`；忽略 `SIGPIPE`；開檔數軟上限調到硬上限。
2. 拿 `.daemon.lock` 的獨占 flock（持到退出）。拿不到＝同家已有一支 daemon 在跑 → `AlreadyRunning`、退 1。
   這是 daemon 這一層唯一的一把鎖：它綁的是 daemon 行程的壽命（行程死鎖就消失），不是跨檔交易，所以沒有「鎖沒人解」的問題；外人也靠它探測 daemon 活不活（§1）。
3. **等上一任的孩子死透**：讀每個 `pools/*/kids/*.json` 的 pid（只拿 `state` 是 `running`／`killing` 的；O(孩子數)，只在啟動），
   舊家的 `state.json` 還有 `children` 的一併算進來。**整批一起**用 `kill(pid, 0)` 看還在不在——在的送 TERM、等 **`stop_wait_ms`＋`kill_wait_ms`**、還在就 KILL 整組，直到全部不在
   （接手專用的等法：pipe 已經沒了，沒得先好好說）。讀到壞的 `pool.json`＝`ReadFailed`、退 1，在殺之前就判。注意兩件事：
   (a) 那個 TERM 對孩子來說可能是「第一次」、只會溫和停，所以才等兩段加起來的時間；(b) 上一任死後它的孩子歸 init 管、死了 init 會收屍，
   所以 `kill(pid,0)` 看到「不在」就是真的不在了（不會收孤兒的 PID 1 環境不在保證內）。pid 被別的程式重用的機率當作可忽略。
   上一任 fork 了、還沒寫 kids 檔就死的孩子——它等不到 `go`、自己就退了（§2），不用找。
4. 照範式 §6.2 對帳自己的 `current`（上一任崩在處理哪則 request；scale 單對帳成 `Interrupted`，kernel 會整份重送）。
5. 殺完：每個 kids 檔改成 `pending`（`pid` null；`gen`、`exits` 照留，`streak` 歸 0），不是成員的刪掉；沒有 `pool.json` 的池資料夾整個刪掉；
   寫新 `state.json`（pid、`current` null、`stopping` false；`children` 拿掉）；重算 `summary.json`。
6. **照 `pool.json` 把孩子拉回來**：每池的成員全部進 `pending`，照節流慢慢拉（§4）。第 1 版的「孩子表從空開始、等客戶再 spawn」**拿掉**。
   （one-boot）再照 `kernels/*.json` 載入登記（壞的略過），每個登記的 kernel 馬上開一格（[§10](ticks.md)）。上一任開的 tick 還活著的**不殺**，它撞鎖就退 75。然後進 §4 的迴圈。

對 kernel 的影響（[kernel §6 boot](../kernel/boot.md)）：工作 cpu 上一任在做的那件，新主人開機對帳回 `Interrupted`、再補丟通知，kernel 照常收；
kernel 的 tick 照 `kernels/` 的登記接著開，**不用重 boot**（2026-09-24 one-boot 改；第 2 版是「kernel cpu 的鏈多半自己接得上」）。
`aos-kernel ls` 的 health 不是 ok 時，`aos up` 一次就好。

**daemon 被 kill -9 之後、下一任開之前**（試玩 one-boot 追加，刻意的）：孩子（cpu）不綁 daemon 的命，照樣活著、把手上那件做完或等 stop；
這段時間沒人開 tick、沒人重拉。下一任開機第 3 步先把它們 TERM／KILL 掉、**等死透才拉新的**，所以同一個 cpu 家不會同時有兩個主人；
上一任手上那件：舊 cpu 收到 TERM 會先停掉它、照常寫回音（`stopped: true`）；沒來得及寫的，新主人開機對帳回 `Interrupted`。kernel 照常收：
once 的把回音原樣交給交件者（不重派；agent 自己決定要不要重送），反覆的 `stopped` 照間隔再排、`Interrupted` 算一次失敗（連敗到 `bad_after` 就停）。這段「沒爸爸」的時間多長不在保證內（要等人或 `aos up` 開下一任）。

開機、正常停機各在 stderr 留一行（`aos up` 開的 daemon，stderr 在 `D/daemon.log`）：
`aos-daemon: Boot: <時間> 開機 pid N`（上一任沒正常停——`state.json` 的 pid 不是 0——再加 `（上一任 pid M 沒正常停，先收它留下的 K 顆孩子）`）、
`aos-daemon: Stopped: <時間> 正常停機 pid N`（`state.json` 的 pid 寫成 0 之後才印）。被 kill -9 那一刻留不下字，下一任的 Boot 行替它記。
「沒正常停」是**依 `state.json` 裡有效的舊 pid 推定**的：`state.json` 壞掉（不是 JSON）daemon 根本開不起來（`ReadFailed`），pid 缺或型別不對就當正常；
開機途中、第一次存檔前又崩，這一任不會被記到。

## 6.2 退出碼與 stderr

| 碼 | 什麼時候 |
|---|---|
| 0 | 正常停機（§5 走完）；`halt` 印 `not running`／`stopped` |
| 1 | 家、info 讀驗、鎖（`AlreadyRunning`）、壞的 `pool.json`、state 寫不進去；CLI 的讀驗／I/O／daemon 回錯；stderr 一行 `aos-daemon: <代號>: <白話>` |
| 2 | 用法錯 |

一則 request 自己的錯誤回在 response 裡，不影響退出碼。
