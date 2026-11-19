# c-daemon 報告：實測 daemon 這層（「硬體」）

隊員 `c-daemon`，2026-11-19 12:45～13:12（CST），乾淨複本 HEAD 3c4cc4c52（`~/.aos/scratch/aos-base-audit-1119/src/`）。
所有指令都經 `~/.aos/scratch/aos-base-audit-1119/bin/clean` 跑；暫存 daemon 全在 `c-daemon/run/<題>/`，`interval_ms` 50（t09 用 200）。只查、只測，沒改任何程式。

重現腳本在 `c-daemon/repro/`，共用函式在 `repro/common.sh`。跑法一律：

```sh
cd ~/.aos/scratch/aos-base-audit-1119/c-daemon && ../bin/clean bash repro/<腳本>.sh
```

每支腳本自己起 daemon、最後 `shutdown`；會先清掉 `run/<題>/` 再重來。

## 嚴重發現一覽

| # | 一句話 | 嚴重度 |
|---|---|---|
| F1 | exec 型 proc：daemon 在「fork 了、表還沒寫」時被 kill -9，重開後**同一格起第二份**，第一份變成表外孤兒，收工也收不掉 | 會丟資料 |
| F2 | daemon 不在的期間 proc 死了（被 kill 或崩潰），重開後那列**整列從表上消失**：沒有 log、沒有原因。接回的 proc 之後被 kill -9 也是直接下表，跟 daemon 自己生的「留 stopped＋原因」不一致 | 會丟資料（丟的是表上的登記） |
| F3 | stderr 沒上限：一隻狂印的 proc **不到 5 秒就寫滿 200 MB**（那是我設的 file_mb 上限），換算約 40 MB/s 以上；清道夫 10 分鐘才來一次 | 會卡死（磁碟） |
| F4 | 沒 cgroup 時，stop／sleep／rm／shutdown 只對主行程送 SIGTERM。**同一個行程群組的子孫也活下來**（只有主行程撐過 10 秒才 killpg）；setsid 出去的、sub:N 的子孫一樣留著 | 會誤導（資源外洩；醒來後跟舊子孫並行） |
| F5 | 10 支並行 `aos-daemon-ctl add` 同名：最多 10 支都回 0（「成功」），實際只跑一支；之後 sleep＋wake，跑的是**另一個呼叫者**的設定 | 會誤導 |
| F6 | sub:N 的 proc 讀得到活樹以外所有權限 644／755 的使用者檔：同台**沒換身分的 proc 的 stack**、daemon 的表與 daemon.json、整個 `~/repo`、`~/.bashrc`、`~/.gitconfig`、`~/.aos/scratch` 底下其他隊員的檔 | 會誤導（上層以為的隔離比實際大） |
| F7 | `auto_restart` 的 proc 每次撐過 3 秒才掛＝**永遠重起、沒有退避、表上永遠 running**，看不出它在連環崩潰 | 會誤導 |
| F8 | 對 exec 型 proc 下 `stop`＝永遠 `stopping`（沒人讀 ctl），但 `aos-daemon-ctl --help` 寫的是「finish this round, stop」 | 會誤導 |
| F9 | 小事：auto_restart 上限訊息說「restarted 3 times」，其實只重起 2 次；退 0 的 auto_restart 被寫成「failed to start (code 0)」；`rm` 回 0 時列還在 stopping，馬上 `add` 同名會被 InstanceExists 擋；其他見內文 | 只是醜 |

下面逐條照 BRIEF 格式寫。

---

## F1　exec 型：daemon 在 fork 與寫表之間被 kill -9，重開後同一格起兩份

- **現象**：用一份 `procs_ctl.json` 的 `procs_added` 一次加 40 支 exec 型 proc，第一支寫出 pid 就 `kill -9` daemon。這時表上 0 列，33 格已經有活行程。重開 daemon 後 40 列都 running，其中 **32 格同時活著兩支**（舊的那支不在表上）。`shutdown` 只收掉表上那支，舊的 32 支照跑（最後是我照 pid 手收的）。同樣步驟換成 loop 型：0 格重複，因為 `live_in_cell` 會看子 loop 的 state 窗把它接回。
- **怎麼重現**：`../bin/clean bash repro/t03b_fork_window.sh exec`（對照組：`../bin/clean bash repro/t03b_fork_window.sh loop`）
- **嚴重度**：會丟資料（兩支用同一個 stack 同時寫；舊的那支 daemon 永遠不知道有它，收工、sleep、rm 都碰不到）
- **影響到今天哪個上層東西**：今天範本裡的列（`_clock`、`_sweeper`、aos-agent 加的 agent）都是 loop 型，**不受影響**。受影響的是 exec 型的掛法：docs/02 推薦的子 daemon 掛法 `"sub": {"exec": "../sub", "auto_restart": true}`，以及任何 `aos-daemon-ctl add <腳本>`。子 daemon 的話，第二份會撞 `DaemonExists` 退 1，於是表上那列是 stopped，真正在跑的那台變成沒人管的孤兒。
- **建議處理方向**：(a) exec 型也在 proc 的 stack 留一個「誰起的、pid＋ticks」小檔，開門時照 `live_in_cell` 的方式比對；(b) fork 前先把列寫進表（phase `starting`），開門看到 `starting` 就去比 /proc；(c) 不修，在 docs/08 寫明這個窗只保護 loop 型。
- **依據**：實測。輸出摘要：`rows in table at kill: 0  cells with a live proc: 33`；重開後 `live procs: 72 cells with >1 live copy: 32 rows: 40`；`survivors after shutdown (killed now): 32`。讀程式：`cpp/aos-daemon/src/daemon/reconcile.cpp:59` 只呼叫 `live_in_cell`，而 `live_in_cell` 讀的是子 loop 的 state 窗（`daemon/adopt.cpp:93-122`）；`reconcile.cpp:313-317` 每 200 ms 才寫一次表。

## F2　daemon 不在的期間死掉的 proc，重開後整列消失

- **現象**：
  1. `kill -9` daemon 後，從外面 `kill -9` 一支 exec 型 proc（`sl`）、`kill -TERM` 另一支（`sl2`），再重開 daemon。這兩列**直接從表上消失**：daemon.log 沒有任何一行，daemon.err 是空的，`adopt_warning` 也沒提。`launch`、`def`、`ws`、`limits` 跟著沒了（stack 還留著）。
  2. 被接回（adopt）的 proc 之後被外面 `kill -9`：0.15 秒內下表（log 一行 `done`、code null）。同一件事發生在 daemon 自己生的 proc 上，則是留 `stopped`、code 137、有 `reason`。同一種死法，表上的結果要看 daemon 中間有沒有重開過。
  3. 有 `auto_restart` 的照樣重起，這部分沒問題。
- **怎麼重現**：`../bin/clean bash repro/t03_crash_adopt.sh`（看「while daemon is dead」與「adopted lp: kill -9」兩段）；`../bin/clean bash repro/t09_table_truth.sh` 的最後一段（daemon 死時 kill c，重開後 c 不見）。
- **嚴重度**：會丟資料（丟的是表上的登記：這隻是誰、怎麼起、份額多少；人得自己記得重新 add，而且看不到它死過）
- **影響到今天哪個上層東西**：agent.py 重生；aos-agent ctl（`ctl ls`／`ctl state` 找不到這隻）；eca。最容易遇到的是沒加 `--auto-restart` 的 agent，在家機 WSL 被 `wsl --shutdown` 或 OOM 一起帶走的時候。重開機那條走 boot_id，表上的行程都當不在了，結果一樣是下表。
- **建議處理方向**：(a) 接回時發現行程不在，就留 `stopped`＋`reason: "exited while the daemon was down (code unknown)"`，跟「出錯結束一律留」一致；(b) 至少印一行 adopt log 或寫進 `adopt_warning`；(c) 維持現狀（docs/08 已寫「照自然結束下表」），在 aos-agent 的文件提醒上層。
- **依據**：實測。重開那一刻 daemon.log 只有 `lp running`、`ar running` 兩行，`sl`、`sl2` 無聲消失；接回的是 `table changed after 0.15s -> NOROW`，自己生的是 `table changed after 0.23s -> stopped 137 9 failed to start: ...`。文件：docs/08「表上 running、行程已不在：adopt 拿不到結束碼，不分起法、照自然結束下表」；docs/03 把「adopt 接回的（不是 daemon 生的，拿不到結束碼；代定）」列在下表的那一類。

## F3　proc 的 stderr.txt 沒上限，狂印 5 秒就 200 MB

- **現象**：一隻 python 不停往 stderr 寫、一行 100 位元組，**不到 5 秒**就撞到我設的 `file_mb: 200`（209715200 位元組）被擋下。沒有這個上限就會一直長下去，速度約 40 MB/s 以上。`_sweeper` 每 10 分鐘才封存一次，兩次之間可以多出數十 GB。對照：stdout 接 `/dev/null`，不會長；daemon 自己的 log 只寫 stdout（給 `--enable-logs` 才印），20 秒只有 603 位元組；loop 型 proc 的身體一失敗 aos-loop 就退，不會狂印。
- **怎麼重現**：`../bin/clean bash repro/t10_logs.sh`（帶 `file_mb: 200` 上限，跑完自己刪掉那 200 MB）
- **嚴重度**：會卡死（磁碟一滿，整台機器的 daemon 都寫不了表）
- **影響到今天哪個上層東西**：所有 proc；特別是 eca、agent-fsm 的身體出錯時一直印 traceback 的那種迴圈。
- **建議處理方向**：(a) daemon 開 stderr 時套一個預設的 `file_mb`（例如 100 MB，daemon.json 可調）；(b) daemon 每圈看一下 stderr 的大小，超過就截，不等清道夫的 10 分鐘；(c) 維持現狀（docs/08 已列為「已知限制」），在範本 daemon.json 的 `limits` 預設帶上 `file_mb`。附帶一點：Python 預設忽略 SIGXFSZ，所以撞到 `file_mb` 時表上沒有 `limit_hit`，只看得到 code 120。
- **依據**：實測：`t=5s ferr/stderr.txt=209715200`、`ferr stopped code=120 hit=None`。文件：docs/08「proc 的 stack stderr.txt 沒有上限、不輪替」。

## F4　沒 cgroup：停掉 proc 時子孫留下來

- **現象**（這台沒有 systemd user，cgroup 是 off）：
  - exec 型，sh 主行程跑 `sleep 601 & wait`：子孫跟主行程在**同一個行程群組**。對這隻下 `sleep` 後主行程 0.5 秒內就退了，子孫還活著（daemon 只在主行程撐過 10 秒時才 killpg）。
  - 用 `setsid sleep 602 &` 逃出去的：活著（這個本來就預期）。
  - `( trap "" TERM; exec sleep 605 ) &`：活著。
  - 主行程退 0、留下背景子孫：列下表，子孫活著。
  - loop 型，身體每輪留一支 `nohup sleep 604 &`：`rm` 之後 17 支全活著。
  - sub:N 的 proc 的背景子孫：`rm` 後 0.2 秒主行程就沒了，uid 100004 的子孫活著；daemon `shutdown` 之後也還活著。
  - **對照（這部分可以放心）**：loop 型或 fsm 型的身體是前景長命令（`exec sleep 606`，或 fsm 狀態裡的 `sleep 607`）時，sleep／rm／shutdown 都會把身體一起帶走（aos-loop、aos-fsm 有轉發 SIGTERM）。
- **怎麼重現**：`../bin/clean bash repro/t04_orphans.sh`、`../bin/clean bash repro/t04b_loop_body.sh`（對照組）、`../bin/clean bash repro/t08_subuid.sh`（sub:N 那段）。腳本最後會照記下的 pid 收孤兒。
- **嚴重度**：會誤導（表上說 sleeping 或已經不在了，實際上還有東西在跑、可能還在寫 ws；wake 之後跟舊的子孫並行）
- **影響到今天哪個上層東西**：agent 的工具呼叫在背景起東西的情況（MCP server、`npm run dev &` 之類）；sub:N（子孫是別的 uid，使用者用 `ps` 不好認）。
- **建議處理方向**：(a) SIGTERM 改成送給整個行程群組（`kill(-pgid)`），主行程退了之後再對群組補送一次；(b) 主行程退了之後，掃一次同一個 session 的殘留（daemon 替它 setsid 過，session id 就是主行程的 pid）；(c) 維持現狀，在文件寫明「沒 cgroup 時只收主行程」。docs/09 安全邊界那句講的是 cgroup 會收；沒 cgroup 時的界線，現在只寫在 subuid-1119 的紀錄裡。
- **依據**：實測：`fork_wait kid 348177: alive`（子孫的 pgid 就是主行程的 pgid 348174）、`lp kids alive: 17 alive`、`kid (sleep 601 inside the sub ns) alive uid=100004`。讀程式：`daemon/tend.cpp:116` 的 `kill(c.pid, SIGTERM)` 只送主行程，`tend.cpp:160` 開始的 SIGKILL 才對整群。

## F5　並行 add 同名：好幾個呼叫者都被告知成功，設定被悄悄換掉

- **現象**：10 支 `aos-daemon-ctl add --name same a.sh -- vN` 同時下。三輪分別有 10、5、4 支回 0（其他的是 `InstanceExists`），但只有 1 支在跑。接著 `sleep`＋`wake`，跑起來的換成了**另一個呼叫者**的參數（第一輪 v10 → v8，第二輪 v8 → v2，第三輪 v7 → v8）。原因：`InstanceExists` 是 ctl 先看表再寄信，看表和寄信之間有競賽；而 daemon 收到同名的 `procs_added`，照規則是「設定換掉、已在跑的不重起」。
- **怎麼重現**：`../bin/clean bash repro/t06b_add_race.sh`（`repro/t06_concurrent.sh` 第一段也看得到 3 支回 0）
- **嚴重度**：會誤導
- **影響到今天哪個上層東西**：aos-agent ctl add（兩個人或兩個 agent 同時掛同名的）、kernel 站轉寄的 add。
- **建議處理方向**：(a) daemon 那端對「信箱來的 add、名字已在表上」回 `applied: false`＋`InstanceExists`，讓 ctl 等到的回覆才是真正的判斷；(b) 信裡帶一個「只在不存在時才加」的旗標；(c) 維持現狀，在文件寫明 InstanceExists 只是盡力檢查。
- **依據**：實測：`round 1: told OK: 10 [...] running: 412924 r1v10` → `after sleep+wake running: 413221 r1v8`。文件：docs/03「同名 add＝設定換掉、停照停」；docs/04「名單上已有的名字寫進 procs_added＝設定換成這份，已在跑的不重起」。

## F6　sub:N 的 proc 讀得到的東西比想像的多

- **現象**：sub:5（uid 100004、gid 160000、附屬群組清空、`HOME=/nonexistent`）實測：
  - **讀得到**：同台沒換身分的 proc 的 stack（`peer_note.txt`、`stderr.txt`，也列得出目錄）；daemon 的 `procs_state.json`；`procs_requests/new` 列得出；daemon.json 和腳本；`~/repo/aos/README.md`，也列得出 `~/repo/aos`、`~/repo/aos/proto8`；`~/.bashrc`、`~/.profile`、`~/.gitconfig`；列得出 `~/.config`、`~/.aos`、`~/.aos/scratch`；讀得到 `BRIEF.md`。
  - **讀不到**：另一隻 sub:6 的 stack（0700＋ACL 有效）；列不出 `~`（751）；列不出 `~/.ssh`。
  - **寫不了**：別的 proc 的 stack、daemon 的 stack、信箱的 `new/`、`~/.aos/scratch`。**寫得了**：自己的格、`/tmp`。
  - 訊號：對 peer 和 daemon 送 `kill -0` 都被拒。
  - 寄信：`aos-post: error: MailboxBad tmp/ is not writable: …/procs_requests/tmp`，接著 `SendFailed`。已知寄不出，**這次確認**。
  - 它寫的檔擁有者是 `100004:160000`；使用者讀、附加都可以（預設 ACL 有效），它建的子夾使用者也寫得進去。
  - daemon 收得掉：sleep 一隻不理 SIGTERM 的 sub:N proc，10.16 秒後 SIGKILL 收掉；`rm` 0.2 秒；kill -9 daemon 再起，照 pid 接回、沒有重複起（loop 型、exec 型都試了）。
- **怎麼重現**：`../bin/clean bash repro/t08_subuid.sh`（只測「能不能開」，不印內容）、`../bin/clean bash repro/t08b_subuid_adopt.sh`
- **嚴重度**：會誤導（不會丟資料；但「換了身分，同台別隻就進不去」只在換了身分的 proc 之間成立，沒換身分的 agent、kernel 的 stack 照樣讀得到）
- **影響到今天哪個上層東西**：sub:N；kernel 站照 `users` 表填 sub:N 的用法；eca（eca 本體留在 uid 1000，K7）。
- **建議處理方向**：(a) 在文件（docs/09「換成 subuid」）寫明「讀得到所有 o+r 的檔，包括沒換身分的 proc 的 stack」；(b) daemon 起任何 proc 時都把小格改成 0700，不只 sub:N 的；(c) 使用者自己收緊 `~/.aos`、`~/repo`（例如改 750，只給 160000 群組 x）。依 subuid-1119 紀錄，現在的目標是單人、模型可信的防呆，要不要再收由使用者決定。
- **依據**：實測，`probe.txt` 摘要如上；`Uid: 100004 100004 100004 100004`、`Gid: 160000 …`。

## F7　auto_restart：撐過 3 秒才掛的 proc 永遠重起，看不出在崩潰

- **現象**：
  - 立刻退 1：0.2 秒內起了 3 次（第一次＋重起 2 次），之後留 `stopped`＋reason。**沒有退避**，兩次重起只隔 1～80 毫秒。下 `start` 後計數歸 0，又是 3 次。
  - 立刻退 0：一樣 3 次就停，reason 寫「failed to start … (code 0)」。
  - 每次 3.3 秒才退 1：20 秒裡起了 7 次，**永遠不停、也沒有退避**；表上和 `ls` 一直是 `running`、`reason` 是 null，表上也沒有重起次數。
- **怎麼重現**：`../bin/clean bash repro/t02_autorestart.sh`
- **嚴重度**：會誤導（一直在崩的 agent 看起來是活的，每 3 秒重來一次：重新問腦、重新寫 stderr）
- **影響到今天哪個上層東西**：aos-agent ctl add `--auto-restart`（start-api 範本預設就加）、`_clock`、`_sweeper`、eca。
- **建議處理方向**：(a) 表上加「連續重起次數」和「最後一次的退出碼、原因」兩欄，running 的列也看得到；(b) 加指數退避（例如 1、2、4 秒…最多 60 秒）；(c) 讓 3 秒門檻可以設。
- **依據**：實測：`d33 starts: 7`、`d33 running … reason=None`；`d1 start times 12:49:05.724 / .813 / .886`。文件：docs/03「連 3 次都在起來 3 秒內就退＝列留 stopped」「中間有一次撐過 3 秒就重算」。行為跟文件一致，問題出在表上看不出來。

## F8　exec 型 proc 的 stop 永遠停不下來

- **現象**：對 exec 型的 `exec sleep 600` 下 `aos-daemon-ctl stop`：3 秒後、之後也一直是 `stopping`，行程活著。改下 `sleep` 才在 0.6 秒內收掉（留 `stopped`、code 143）。原因是 `stop` 寫的是 proc 的 ctl 窗，exec 型的程式根本不讀它。
- **怎麼重現**：`../bin/clean bash repro/t01_lifecycle.sh`（第二段）；`repro/t06_concurrent.sh` 裡 `stop p1-5` 那 5 支也一直 stopping。
- **嚴重度**：會誤導（help 表寫的是 `stop | finish this round, stop | writes its ctl, waits`，沒說 exec 型會永遠等；docs/08 倒是有寫「沒有時間上限」）
- **影響到今天哪個上層東西**：所有 exec 型的列；如果 aos-agent ctl stop 掛的是 exec 型，也一樣。
- **建議處理方向**：(a) ctl 對 exec 型下 stop 時直接提示「這種 proc 不讀 ctl，請用 sleep」；(b) daemon 對沒有 loop.json 的列，stop 改送 SIGTERM；(c) 只在 help 補一句。
- **依據**：實測：`after 3s phase=stopping pid alive? alive`。文件：docs/03「不改送 SIGTERM，沒人讀就等程式自己結束」。

## F9　小事（只是醜）

- `restarted 3 times in a row` 其實只重起了 2 次（一共起 3 次）。依據：t02 的 `d1 starts: 3`。
- 有 `auto_restart`、退 0 的 proc，也被寫成「failed to start … (code 0)」。依據：t02 的 `d0`。
- `aos-daemon-ctl rm` 回 0 時，不理 SIGTERM 的 proc 還在 `stopping`（最多 10 秒），這時馬上 `add` 同名會被 `InstanceExists` 擋；腳本得自己等列消失。依據：`repro/t05_samename.sh` 的 y 段：`stopping:401354` 連續 9 次後才 `NOROW`，中間那次 add 失敗。
- loop 型寫成 `{"exec": ["sleep", "0.3"]}` 時，陣列第一個 `sleep` 會照 daemon 的 cwd 轉成 `…/t01/sleep`，起不來（`RunFailed`）。docs/02 有寫（「內嵌單子的 argv 才走 PATH」），但很容易踩到。依據：t01 的 `lp` 段。
- 「手動 sleep」不會跨 daemon 重開保留：sleep 途中 daemon 被 kill -9，重開後收完立刻又 wake（新 pid）。docs/03 有寫（「daemon 收工再開時 slept 集合是空的＝睡著的列開門自己醒」），放在這裡給上層參考。依據：t03 的 daemon.log 裡 `nt` 是 `stopping → sleeping → running`，後兩步在同一毫秒。

---

## 測試表

| 項目 | 預期（依哪份文件哪一句） | 實際 | 差在哪 |
|---|---|---|---|
| add exec 型 | docs/02「字串、陣列＝跑一次」 | running，表上 exec／def／as_written 都有 | 無 |
| stop exec 型 | docs/03「寫 ctl…沒人讀就等程式自己結束」、docs/08「沒有時間上限」 | 一直 stopping | 跟文件一致；help 會誤導（F8） |
| stopping 中下 sleep | docs/03「stop 中改送 SIGTERM、退後仍 stopped」 | 0.61 s 後 stopped、code 143 | 無 |
| start | docs/03「從 stopped 集合拿掉→下一圈再起」 | 新 pid、running | 無 |
| sleep／wake | docs/03「SIGTERM…列留 sleeping」「wake 用列上的 stack 再起」 | 0.56 s 變 sleeping；wake 起新 pid | 無 |
| sleep 不理 TERM 的 proc | docs/03「10 秒還在就 SIGKILL 整群」 | 10.58 s，code 137、signal 9 | 無 |
| 有不理 TERM 的 proc 時 shutdown | 同上 | 10.27 s、10.42 s；列 sleeping，重開全醒 | 無 |
| restart 子命令 | 沒有這個指令 | `CommandUnknown` | 無（要用 sleep＋wake 或 stop＋start） |
| loop 型 stop／start | docs/03 | t01 用錯寫法沒驗到（F9）；t04b 的 fsm 型 stop 照「等這輪做完」一直 stopping（身體要跑 607 秒） | 跟文件一致 |
| auto_restart 立刻掛 | docs/03「連 3 次都在起來 3 秒內就退＝留 stopped＋reason」 | 3 次後 stopped，沒有退避 | 訊息字樣（F9） |
| auto_restart 3.3 秒才掛 | docs/03「中間有一次撐過 3 秒就重算」 | 無限重起，表上一直 running | 跟文件一致，但看不出來（F7） |
| 沒 auto_restart，退 0／退 1 | docs/01「自然退 0 才下表，非 0 留 stopped」 | 退 0 下表；退 1 stopped＋reason | 無 |
| daemon kill -9：還活著的 proc | docs/08「子項還活著＝adopt 接回」 | 同 pid 接回、沒重起；行程的 ppid 換成外面的收養者 | 無 |
| kill -9 後的鎖 | docs/03「flock…kill -9 也會放」 | 立刻 `flock -n` 拿得到，重開沒問題；沒有 pid 檔 | 無 |
| 同 stack 起第二台 | docs/03 `DaemonExists` | `DaemonExists …`、退 1 | 無 |
| daemon 死的期間 proc 也死了 | docs/08「照自然結束下表；auto_restart 的照樣重起」 | 無聲消失；auto_restart 的有重起 | 跟文件一致，但沒有任何訊息（F2） |
| fork 了、表還沒寫就被 kill -9 | docs/08「起任何 proc 前看公開 state 窗…不另起一份」 | loop 型 OK；exec 型 40 格裡 32 格重複 | exec 型沒有保護（F1） |
| sleep 途中 kill -9 | docs/08「依表內 stop_mode 接著收」 | 重開後接著收（SIGKILL），收完立刻 wake | 收的部分一致；醒的部分見 F9 |
| kill -TERM daemon | docs/03「SIGTERM…都走 finish」 | 收工，running 的睡下，重開全醒 | 無 |
| 孤兒：同群組的子孫 | docs/01「滿 10 秒還在就 SIGKILL 整群」 | 主行程先退了，子孫就留下 | 文件只講主行程撐過 10 秒的情況（F4） |
| 孤兒：setsid 逃出去的 | docs/09「這裡防…setsid 孤兒」（指的是 cgroup） | 留下 | 沒 cgroup，預期內 |
| 孤兒：loop／fsm 的前景身體 | — | 一起收掉 | 無 |
| add 同名兩次 | `aos-daemon-ctl` 的 InstanceExists | 一支接一支下會被擋；並行下則好幾支回 0（F5） | 有競賽 |
| rm 後馬上 add | — | 等 rm 回覆後再 add 成功、只有一份；不理 TERM 的要等 10 秒 | F9 |
| 並行 20 支 add 不同名 | 不丟指令 | 21/21 running、0 錯 | 無 |
| 並行 stop／sleep／rm 共 15 支 | 不丟指令 | 全部生效（5 stopping、5 sleeping、5 下表） | 無 |
| 同一個名字亂下 10 種指令 | 表不壞 | 表正常；PhaseBad、InstanceExists 照擋；最後最多 1 份在跑 | 無 |
| 半寫的 json | docs/04「先寫 . 暫存檔再改名」 | 25 秒內讀了 32673 次，三扇窗 0 次壞 JSON | 無 |
| 信箱殘留 | — | new／cur／tmp 都是 0 | 無 |
| cpu_s 1 | docs/09「cpu_s 到頂＝SIGXCPU；limit_hit cpu_s」 | code 152、signal 24、`limit_hit: cpu_s` | reason 字串本身不提份額，只看得到 limit_hit 欄 |
| cpu_s 1，sh 沒用 exec 包 | docs/09「沒用 exec…就可能看不到」 | `limit_hit` 是 null | 一致 |
| cpu_s 1，fork 三個各吃 0.9 秒的子行程 | docs/09「fork 的子行程重新起算」 | 跑完、退 0 | 一致 |
| mem_mb 50 | docs/09「MemoryError；limit_suspect」 | code 1、`limit_suspect: mem_mb` | 一致 |
| files 20 | docs/09「open 失敗」 | code 1，reason 帶 `Too many open files` | 一致 |
| procs 5（不換身分） | docs/09「數那個帳號的全部行程」＋K11 警告 | `Cannot fork`；daemon.err 有 K11 那行 | 一致 |
| file_mb 1 | docs/09「SIGXFSZ；limit_hit file_mb」 | code 153、signal 25、`limit_hit: file_mb`，檔停在 1 MiB | 一致（Python 會忽略 SIGXFSZ，見 F3） |
| 寫壞的份額 | docs/09「寫壞＝信壞信」 | ctl 先擋：`ArgumentsBad cpu_s … positive integer` | 一致 |
| sub:N 的身分 | docs/09「真 uid＝起點＋N－1；群組 G」 | /proc 的 Uid 四欄都是 100004、Gid 都是 160000；ns 裡是 uid 5 | 一致 |
| sub:N 讀活樹以外的檔 | docs/09「同台別隻進不去」 | 別的 sub 進不去；沒換身分的 stack、repo、家目錄的 644 檔都讀得到 | F6 |
| sub:N 寄信 | subuid-1119「換了身分的 agent 寫不進 daemon、kernel 的信箱」 | `MailboxBad tmp/ is not writable` | 一致（確認寄不出） |
| sub:N 的檔擁有者 | docs/09「agent 寫的檔是 100004:160000，使用者照改」 | 一致，使用者附加成功 | 無 |
| sub:N 收不收得掉 | docs/09「daemon 是那個 ns 的擁有者，照舊停得了」 | sleep 10.16 s（不理 TERM 的）、rm 0.2 s、shutdown，主行程都收掉 | 子孫見 F4 |
| sub:N 接回 | docs/08 | kill -9 daemon 後同 pid 接回、沒重起 | 無 |
| 外面 kill -9 後表多久更新 | docs/04（每圈看一次） | interval 50：0.23 s；interval 200：0.11 s；接回的 0.15 s | 接回的下表，自己生的留 stopped（F2） |
| 被 SIGSTOP 的 proc | — | 表上 running（/proc 是 T） | daemon 不看這個，預期內 |
| daemon 死時下 `ls` | — | 明寫 `daemon: not running (pid … is gone); the table above is what it left` | 無（做得好） |
| proc 的 stdout | docs/03「子項的 stdout 接 /dev/null」 | fd 1 → /dev/null | 無 |
| proc 的 stderr | docs/08「沒有上限、不輪替」 | 5 秒 200 MB | F3 |
| daemon 的 log | docs/03「--enable-logs 才印到 stdout，不寫 log 檔」 | 一致，20 秒 603 位元組 | 無 |

## 時間（讀程式答）

- **用 monotonic 的（`steady_clock`）**：daemon 一圈的間隔、SIGTERM 後的 10 秒寬限（`daemon/tend.cpp:115,160`）、「3 秒內退」的判斷（`tend.cpp:196`、`daemon/failure.cpp:18`）、身體的下一次時間（`daemon/daemon.hpp:265`）、分檔退役的 2 秒（`daemon.hpp:241`）；aos-loop 的間隔也是 steady（`aos-loop/src/engine/loop.cpp:25`）。這些不怕系統時鐘跳。
- **用牆鐘的（`system_clock`）**：判卡住。`stuck_after_ms`，以及沒設 `AOS_CLOCK` 時的 `stuck_after_cycles`，都換算成牆鐘毫秒（`aos-util/src/clock.cpp:100-118`、`aos-daemon/src/daemon/stuck.cpp:63-75`）；判斷有沒有刺激，是拿 ctl 的 mtime 跟 `responded_at`（UTC 字串）、`utc_now_ms()` 比（`stuck.cpp:46-61`）。所以時鐘**往前跳**時，有刺激在等的列可能被誤判成 `stuck`（加了 `restart_on_stuck` 的會被重起）；**往後跳**時 mtime 落在未來，暫時不判（這條有寫成規則）。log 的 `at`、表的 `updated_at` 也是牆鐘，只是給人看的。
- **用開機時鐘的（`CLOCK_BOOTTIME`）**：`stop_cause.json` 的 `at_ticks`（`tend.cpp:67-71`）；行程身分則靠 /proc 第 22 欄＋`boot_id` 比對。
- **系統時鐘跳：未測**（不能 sudo 改時鐘；aos-daemon 是靜態連結，也套不上 libfaketime）。最可能遇到的情況是 Windows 睡眠醒來時，WSL 的牆鐘一次往前跳。

## 可以放心的（測了、跟文件一致）

- 起、停、sleep／wake、start、shutdown 的狀態轉換，以及 10 秒強收，都照文件；shutdown 後再開，睡著的全部醒來。
- kill -9 daemon：還活著的 proc 照 pid＋ticks 接回、不重起（exec 型、loop 型、sub:N 都是）；鎖立刻放掉；沒有 pid 檔殘留；同一個 stack 起第二台確實 `DaemonExists`。
- loop 型「fork 了、表還沒寫」的窗有保護（40 格 0 格重複）。
- loop／fsm 的前景身體在 sleep／rm／shutdown 時會一起被帶走。
- 並行 ctl：20 支不同名的 add、15 支混合的 stop／sleep／rm 都沒丟；三扇狀態窗讀了 3 萬多次，0 次讀到寫一半的；信箱沒有殘信。
- rlimit 的五種份額都會命中；表上的 `limit_hit`／`limit_suspect` 照文件寫的條件出現；K11 警告有印。
- sub:N：身分、群組、環境白名單（`HOME=/nonexistent`）、別隻 sub 的格進不去、寄不出信（已知）、使用者改得動它的檔、daemon 收得掉、接回不重複。
- daemon 死了的時候，`aos-daemon-ctl ls` 會明說這張表是舊的。

## 沒測到的＋原因

- **系統時鐘跳**：不能 sudo；靜態連結套不上 faketime（見上面「時間」）。
- **cgroup 模式**（`cgroup: auto/on`、`mem_total_mb`、`procs_total`、用 cgroup.kill 收孤兒）：這台沒有 systemd user，沒有可以委派的 cgroup。
- **sub:N 的 `procs` 份額擋 fork 炸彈**：只跑了 `procs: 20` 的正常 proc，沒做會 fork 到上限的測試（test_subuid.py 已經有 `procs: 3` 的真機測試）。
- **磁碟滿時 procs_state 寫不了**：要真的灌滿磁碟，不做。
- **pid 被重用、撞到別人的行程**（接回的 proc 退了、pid 剛好被別的行程拿走，daemon 卻送 SIGTERM 過去）：機率太小，沒辦法穩定重現。讀程式看，`tend.cpp:116` 送訊號前沒有再比一次 ticks（推測）。
- **loop 型 stop／start 的正常路徑**：t01 寫錯了寫法（見 F9）；只有 t04b 的 fsm 型 stop 測到「等這輪做完」那一半。

## 收尾核對

- 開工前 `pgrep -af aos-`：沒有我的行程（只有別條線的編譯和測試）。
- 我一共起過 24 台 daemon（pid 記在 `c-daemon/mypids.txt`），每支腳本最後都下 `aos-daemon-ctl -d <stack> shutdown`；t01 第一次記錯 pid 的那台，也是用 shutdown 收的。收尾時逐一 `kill -0`：全都不在了。
- 測孤兒時留下的子孫（t04、t04b 的，還有 t03b 那 32 支重複的 proc），都在腳本裡照記下的 pid、先確認 cwd 在 `c-daemon/` 底下，再收掉。
- **例外兩支**：t08 留下的 sub:N 背景子孫 `sleep 601`（pid 421388 是 uid 100005、421507 是 uid 100004）。它們的 cwd 是 `/usr/bin`（exec 型的 aos-exec 會 cd 到目標所在的資料夾，那次的目標是 `/usr/bin/env`），不符合「kill 前 cwd 要在自己子夾」這條規則，所以沒有收，等它們 601 秒後自己結束（約 13:11）。
- 13:11:08 收尾複查：421388、421507 都已自己結束；`mypids.txt` 裡 24 台 daemon 全不在；整台機器上 cwd 在 `c-daemon/` 底下的行程 0 支；`pgrep -af aos-` 剩下的 17 行都是別條線的（d-mailkern 等）。
- 磁碟：t10 那 200 MB 的 stderr 跑完就刪了；`c-daemon/run/` 留著當證據。
