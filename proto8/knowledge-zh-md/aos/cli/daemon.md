# `knowledge/aos/cli/daemon.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/daemon.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/daemon.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Daemon procs: direct control, bypassing the kernel`**

# Daemon 的 proc：直接控制，繞過 kernel

要管一個 daemon 上的任意 proc，用 aos-daemon-ctl；信送出去，不代表要求的變更已經做完。要經過 kernel，用 `aos-agent ctl`（`aos/cli/agent.md`）。

**`#/add: attach a proc`**

# add：掛上一個 proc

```sh
aos-daemon-ctl -d /srv/d add --name tick tick.json      # a loop config: runs again and again
aos-daemon-ctl -d /srv/d add --name job job.sh -- 3     # runs once; ARGS after --
aos-daemon-ctl -d /srv/d where --stack tick             # /srv/d/procs/tick
```

add 會印出一個信名。loop 設定是一個有 `exec`、沒有 `argv` 的物件；其他目標只跑一次，也只有它們吃 `--` 後面的 ARGS。定義夾會跑它的 `_entry`；agent 請用 `aos-agent ctl add`。只跑一次的 proc 以 0 結束，它那一列就被移除；已知的非零結束會留著，狀態 `stopped` 並附原因（`failed to start: exited within 3s of wake/start (code 3)`）。`--auto-restart` 每次結束都重啟，直到連續 3 次都在 3 秒內結束為止。`--def DEF` = 記在表上的定義夾（預設：目標本身）；`--ws`、`--stack`、`--ws-json`、`--stack-json`、`--path-json`、`--limits` 用法跟 `aos-agent ctl add` 一樣。`limits: {}` 用 daemon 的預設。非空的 `limits` 會取代所有數字預設：你要的每個鍵都要寫；只有缺少的 `user` 會從預設拿。請求不准拿掉的預設鍵，放進 daemon.json 的 `limits_max`；超過或漏掉一個有上限的鍵，只會停掉那個 proc（`LimitBad`，不會自動壓到上限）。預設必須寫出每個有上限的鍵，而且不能超過上限。列上可能會出現 `limit_hit`，表示直接子程序收到 CPU／檔案大小的訊號；`limit_suspect` 表示以 1 結束且有 `mem_mb`（是猜的）。名字已經被用掉 = `InstanceExists`；對表上沒有的名字做 where 或 rm = `ProcMissing`。

**`#/stop, sleep, pause, rm`**

# stop、sleep、pause、rm

所有 proc 都能 stop、start、sleep、wake。stop 會寫這個 proc 的 ctl 窗口並等它結束（不會退而送 SIGTERM）：列變成 `stopped`，用 `start` 回來。sleep 送 SIGTERM（10 秒後送 SIGKILL）：列變成 `sleeping`，用 `wake` 回來。配錯對會得到 `PhaseBad`（sleep 也收 `stopping` 的列；pause／resume 只收 running 或卡住的列）；已經在那個狀態 = `NAME: already X`，以 0 結束。pause／resume 會把 `{"cmd": "pause", "seq": N}` 寫進 ctl 窗口，印出 N，然後最多等 `--timeout-s`（預設 5）讓它生效；逾時會警告並以 0 結束；要不要讀它由程式自己決定。rm 不問就卸下；stack 留著。ctl 檔名是上層寫的 loop 設定裡非空的 `ctl`，沒有就是 ctl.json。sleeping 的列會在下一次 daemon 啟動時醒來。

**`#/Letters, waiting and the kernel`**

# 信、等待與 kernel

add／rm／stop／start／sleep／wake 會印出信名，並最多等 `--timeout-s`（預設 3）讓 daemon 領走它；`prune --apply` 也會等，但印的是 `NAME: removed`。信還在排隊就警告並以 0 結束。領走之後會短暫讀一下 daemon 的回覆：被拒絕的信是錯誤，附上原因（`BodyBad`，否則 `CtlRejected`）。領走不代表已經套用：要看 `ls`。`--reply-to BOX` 只送；回覆你自己讀（`applied: true|false`）；它不能跟 `--timeout-s` 一起用。

aos-daemon-ctl 指名一個 daemon：它直接送到那個 daemon 的 ctl 信箱，從不讀 `$AOS_KERNEL`；只要你能寫那個信箱，它就能用。`aos-agent ctl` 經 `$AOS_KERNEL` 轉送，並警告 `routing via AOS_KERNEL=PATH`。kernel 在睡或停了，是設計者的風險：用 `aos-daemon-ctl wake NAME` 叫醒它（停了的話：`start`）。

daemon 也回答一個關於表的問題：body `{"procs_state_path": true}` 加上 `reply_to`，會得到 `{"applied": true, "procs_state_path": "<absolute path of its procs_state.json>"}`（它的 procs_state 窗口關著時是 `null`），什麼都不改；別的值 = `BodyBad`。aos-daemon-ctl 從不送這個（`ls`、`where` 直接讀檔）。`aos-agent ctl ls`／`who`／`where`／`state` 會在讀表之前把它送給 `$AOS_KERNEL`，等 3 秒（`--timeout-s`），失敗就給 `KernelFailed`，而不是改讀 `$AOS_DAEMON`（`aos/kernel.md#/Where to send requests`）。

**`#/ls, ping, poke`**

# ls、ping、poke

```sh
aos-daemon-ctl -d /srv/d ls
aos-daemon-ctl -d /srv/d ping        # replied in 108 ms
aos-daemon-ctl -d /srv/d poke --all  # run a full round now
```

```text
_clock	running	1082359	-	-	-
# daemon: running (pid 1082357)
# root daemon (no supervisor)
```

ls 的欄位（TAB 分隔）：NAME PHASE PID CODE WS REASON。最後兩行以 `# ` 開頭：這個 daemon 有沒有在跑，以及它的監督者怎麼看；寫解析程式時跳過它們。`ls -j` 印一個物件（`running`：daemon 活著）。有身體的 daemon（llm kernel、kernel station）如果上一輪身體失敗，會在 `# daemon:` 那行說（`; its body failed last round (code N; the reason is in the daemon's stderr)`；`ls -j`：`body_code`）：送給那個 kernel 的信沒人在處理。ls 和 where 只讀檔：不能證明還活著。ping 會等回覆（逾時 `DaemonFailed`）。poke 是門鈴：`--ctl`（預設）、`--mail` 或 `--all`；先寫 ctl 或先送信。其他代號：`CtlMissing`（ctl 窗口關著）、`StateMissing`、`StateBad`、`PokeFailed`。更多旗標：跑 `aos-daemon-ctl --help`。

**`#/shutdown: stop the whole daemon`**

# shutdown：停掉整個 daemon

```sh
aos-daemon-ctl -d stacks/root shutdown
# daemon at /.../stacks/root stopped (ctl seq 1); 2 procs asleep
```

每個在跑的 proc 都進入 sleep，並留在表上；再啟動 daemon 就會叫醒它們。它最多等 `--timeout-s`（預設 15）；還在跑 = `StillRunning`：先別 commit 或複製 stack；再跑一次。正在進行的 stop 會維持停止，正在進行的 sleep 會變成 sleeping，正在進行的 rm 會被移除；如果 kill -9 打斷了 shutdown，下次啟動會得到同樣的結果。

**`#/prune: check rows and remove old ones`**

# prune：檢查列並移除舊的

```sh
aos-daemon-ctl -d /srv/d prune
aos-daemon-ctl -d /srv/d prune --older-than 7d
aos-daemon-ctl -d /srv/d prune --older-than 7d --apply
```

`prune` 把每個可疑的列印成 `NAME: PHASE: PROBLEM`（stack 不見、ctl 檔壞掉、停止原因）；只有發現問題時仍以 0 結束。

`--older-than`（正整數加上 `s`、`m`、`h` 或 `d`）只選出 stopped／sleeping、而且最近一次 stack 變動（stack 資料夾和它底下直接的檔案）比這更舊的列；沒有 stack 的列永遠不會被選。預覽行是 `NAME: would remove (last change ISO_TIME)`。`--apply` 必須搭配 `--older-than`，走跟 `rm` 一樣的送信路徑，印出 `NAME: removed`；stack 和工作區都留著。

**`#/sweep: one sweeper round now`**

# sweep：馬上跑一輪清掃

```sh
aos-daemon-ctl -d /srv/d sweep --dry-run
aos-daemon-ctl -d /srv/d sweep --purge --dry-run
```

sweep 在這個指令裡跑跟 `_sweeper` 列（`aos/cli/sweeper.md`）一樣的程式，所以那列暫停或不在時也能用。`--purge` 刪掉這個 daemon 所有的 stderr 封存（在終端機上會問；`-y` 跳過）。只有給了 `--retention-days N`，才會按年齡刪封存；`--min-bytes` 和 `--stop-grace-s` 調整這一輪。`--purge` 不能跟這三個一起用（`ArgumentsBad`）。另一個清掃者忙超過 `--timeout-s`（預設 30）= `SweepBusy`。`-j` 把這一輪印成 JSON。

**`#/Optional cgroup v2`**

# 選用的 cgroup v2

把 daemon.json 的 cgroup 設成 off（預設）、auto（探測失敗就警告並退回）或 on（失敗就 CfgBad）；在委派的 scope 裡自己啟動它：systemd-run --user --scope --collect -p Delegate=yes -- aos-daemon daemon.json（launch.json 的 wrap 還沒做）。拿到 stack 鎖之後，daemon 會把自己移進 base/daemon，並在 base 和 base/procs 上開啟 memory／pids。limits 的 mem_total_mb 設定 memory.max，可用時同時設 memory.swap.max=0；procs_total 設定 pids.max，涵蓋 proc 和它的子孫，連執行緒也算。兩者都收正整數，也受 limits_max 限制；沒有 cgroup 時會警告一次，並出現在 limits_ignored。每個有開的列會回報自己的 cgroup 絕對路徑；重新啟動會重建空的群組並重設事件。直接子程序結束時，cpu_s／file_mb 命中優先，其次 oom_kill 給 limit_hit mem，再來 pids max 給 procs；有命中就清掉 limit_suspect。接手過來、正在跑的列不讀事件。以 0 結束的列照樣被移除；結束日誌不會多出 hit／suspect 欄位。正常停止不變；cgroup.kill 也會在結束時或 10 秒的 kill 寬限之後，收掉剩下的子孫（連 setsid 的也算）。用你自己 uid 跑的 proc 可以改寫 cgroupfs：對它們來說，這些限制擋的是意外，不是蓄意竄改。`--limits` 以及 kernel station 的 default／max 表兩個都收；aos-sandbox 不收。

**`#/Running a proc as a subuid (limits.user sub:N)`**

# 以 subuid 跑 proc（limits.user sub:N）

`limits: {"user": "sub:5"}` 讓那個 proc 以 daemon 使用者的第 5 個 subuid 跑，不需要 root：真正的 uid = 那個使用者在 /etc/subuid 的第一個起點 + N - 1（起點 100000 得到 100004）。N 是 1 到 60000。通常 kernel 會從它的 `users` 表填這個值；不是你選的。同一個 daemon 的這類 proc 共用一個主要群組：daemon.json 的 `group`（60001 到 65536，預設 60001；daemon 的 state.json 會顯示）；附加群組會被丟掉。這類 proc 的 `procs` 只算那個 proc 自己的程序和執行緒（兩個同樣 sub:N 的 proc 分開算）；整個帳號仍受 daemon 本身的程序上限管。

啟動前，daemon 會把這個 proc 的 stack 設成 0700，並加上給那個 uid 和給 daemon 使用者的 ACL 項目，讓使用者仍能讀、改 proc 寫出來的東西。proc 從環境只拿到 PATH、LANG、LC_ALL、LC_CTYPE、TZ、TERM、PYTHONDONTWRITEBYTECODE、PYTHONIOENCODING 和 AOS_*，HOME=/nonexistent，以及把 git safe.directory 設成它的 ws。

需要 newuidmap／newgidmap（uidmap 套件），而且 stack、daemon 的 cwd 和 ws 的每一層上層資料夾都要讓那個 uid 能進入。出錯只停掉那個 proc 並附原因：`LimitBad user sub:5: newuidmap not found on PATH (install the uidmap package)`、`LimitBad user sub:5: cannot reach /home/me: Permission denied`（別人進不去的家目錄）、`LimitBad user sub:5: setgroups: ...`。信箱和共用資料夾不會為它打開：用 aos-share。limits 裡的 `groups` 還不收。
