# ① 核心組：照核心 spec 做下去遇到的問題

← [proto7-1 spec](../spec.md)｜核心 spec：[proto7/spec/core.md](../../proto7/spec/core.md)

範圍：daemon、tick、tock、任務包裝（aos7-run）、任務控制、aos7-ctl、搬來的 inst 執行器。程式在 `lib/aos7_daemon*.py`、`aos7_tick.py`、`aos7_tock.py`、`aos7_task.py`、`aos7_run.py`、`aos7_ctl.py`；測試 `tests/test_core*.py`。

分級：〔要使用者決定〕方向、核心 spec 說不清或互相衝突／〔技術選型，先這樣〕／〔默認正常〕。

## 要使用者決定（3 條）

### P-06 pause 時任務控制不會被執行——kernel 停不掉被 pause 的 node 上的任務〔要使用者決定〕

- 層：daemon × kernel；S-17「在 tick-tock 時」做 kill／restart，S-18 kernel 用 daemon ctl 停時間線。
- 發生什麼：ctl.json 只在 tick 與 tock 時刻執行（spec 第 6 節照 S-17 字面）。node 被 pause 就沒有 tick／tock，所以對它的任務寫的 ctl.json 一直放著，直到 resume。kernel 想「先 pause 這條時間線，再 kill 裡面燒錢的任務」做不到；kernel 的預算規則（pause 超支 node）跟卡住規則（restart 任務）疊在同一個 node 上時，restart 會被延到 cool_rounds 之後。
- 先這樣：照字面，pause 時 ctl 等著。
- 要決定的：「在 tick-tock 時」是指「控制只能落在回合邊界上」（那 pause 就是凍結一切，包括控制），還是只是「kernel 的判斷節奏」（那 daemon 可以在 pause 時照樣執行 ctl.json）？

### P-09 kill 一個 `keep` 任務，下個 tick 它就被任務表起回來〔要使用者決定〕

- 層：tick × kernel；S-17 kill、S-10 任務一律由 tick 啟動。
- 發生什麼：`keep`＝「沒有同名活任務才起」。kill 之後就沒有活的了，下個 tick 照 tasks.json 再起一個。所以對常駐任務來說 **kill 實際上等於 restart**（測試 `test_ctl_kill_and_restart` 驗了這個行為）。影響：kernel 的「壽命」規則 kill 掉的 subd 會回來；S-21 路一「父時間線 kill 子 daemon」也只是讓它重開一次（`test_child_daemon_as_task` 裡看得到 subd-r2 又起來）。
- 先這樣：不改。真的要停只能改 tasks.json 或 pause 該 node。
- 要決定的：kill 的意思是「這一個實例結束」還是「這個任務別再有了」？後者就要定「任務表誰能改」（核心 spec 列為之後再說），或在 ctl 加一個「停用」的 op。

### P-16 對常駐任務來說，回合幾乎只剩 tick 緊接 tock〔要使用者決定〕

- 層：daemon 時間線；S-09（任務跑完 tock 進場，可提前）× S-11（任務跨回合）。
- 發生什麼：daemon 的「提前 tock」只看**本回合 tick 起的**任務。kernel、agent 這種 keep 任務在第 1 回合起來後就不再算在任何回合裡，於是之後每回合 tick 沒起新東西，tock 就緊跟著來（實測 tick→tock 約 40 ms，interval 再長也一樣），接著是一整段 idle。kernel／agent 收到 tock 後做事，其實全落在「回合之間」的 idle 期；「回合中」對它們毫無意義。
- 先這樣：照 spec 第 2 節做，不改。
- 要決定的：回合的「中段」要不要給跨回合任務用？例如「tock 要等所有活任務都回報這回合做完」——那就需要任務→daemon 的訊息（核心 spec 列為之後再說的「任務與 tick、tock、daemon 之間的訊息交流」）。

## 技術選型，先這樣

### P-01 daemon 內用 thread 管迴圈 vs S-04「用程序，不用 thread」〔技術選型，先這樣〕

- 層：daemon；S-04、S-05。
- 發生什麼：每條時間線要同時「等 interval、等任務結束、隨時被 stop 叫醒」。用程序做就得一條時間線一支常駐程序（又多一層要管的程序與孤兒）。所以 daemon 內一條時間線一個 thread，tick、tock 每次都是獨立程序（`subprocess.run`）。另外 daemon 自己直接讀檔、讀 `/proc` 判斷任務是否結束（不是每次問一個程序），這也不是「每個動作一次程序呼叫」。
- 先這樣：解讀 S-04 為「aos 的動作（tick、tock、任務）是程序」，daemon 的內部排程不算動作。thread 裡只做等待與起程序，沒有共享可變狀態（只有 paused 集合與 stopping 旗標）。

### P-02 任務靠環境變數找自己的資料夾 vs S-01〔技術選型，先這樣〕

- 層：任務；S-01、S-10。
- 發生什麼：任務知道自己是誰只能靠 `AOS7_ROOT／AOS7_NODE／AOS7_TASK…`。環境變數不是檔案，`cat` 不到；一個「只靠讀寫檔案」的 LLM 若不是被 tick 起的，無從得知。另外環境變數在出生時就定死：見 P-10，node 換了 daemon 之後，舊任務的 `AOS7_ROOT` 還指向舊 daemon。
- 先這樣：環境變數之外，birth.json 也寫了 node、dirs、tid（檔案可讀），但任務要先知道 birth.json 在哪，還是得靠 `AOS7_TASK`。

### P-04 SIGKILL 子 daemon 會留孤兒；SIGTERM 也有寬限時間問題〔技術選型，先這樣〕

- 層：daemon；S-21 路一、S-06。
- 發生什麼：任務由 aos7-run 起在新 session，tick 結束後 aos7-run 被 reparent 給 init，不是 daemon 的後代。所以：
  - 實驗：對子 daemon `kill -9`，它的任務照活（`/proc/<pid>` 還在）。父那邊的「後代群組」走訪也找不到它們。
  - SIGTERM 路徑能用（`test_child_daemon_as_task` 通過），但子 daemon 要在**父的 1 秒寬限內**收完自己所有任務並 tock；任務多、或任務不理 SIGTERM（每個也等 1 秒，而且是一個一個收），父就會 SIGKILL 子 daemon → 剩下的變孤兒。
- 先這樣：SIGTERM＝stop+kill；SIGKILL 的孤兒默認正常（S-06 出事歸 daemon）。之後要根治可選 cgroup（整棵一起殺）或讓 daemon 當 subreaper（`PR_SET_CHILD_SUBREAPER`，任務仍是它的後代），都會碰到 S-03 的 Linux 細節。

### P-05 搬來的 aos-exec 把 inst 子程式開在另一個 session，kill 收不到〔技術選型，先這樣〕

- 層：任務控制 × inst 執行器；S-12、S-17。
- 發生什麼：proto6 的 aos-exec 規定「子程式另開 session」、「自己被訊號結束不轉送」。aos7-run 把 aos-exec 起在自己的群組，kill 對那個群組送 SIGTERM，aos-exec 死了、inst 的真正子程式活著。另外兩個不合：(1) inst 沒寫 `stdout` 就是 `/dev/null`，out.log 是空的；(2) 子程式被訊號殺時 aos-exec 回 128+N，aos7-run 直接跑的任務是 −N，同一件事兩種碼。
- 先這樣：kill 時先走 `/proc`，把群組成員所有後代所在的群組一起送訊號（`aos7_task._groups_with_descendants`；`test_inst_task_kill_reaches_grandchild`）。out.log 要內容就在 inst 寫 `"stdout": {"$opt": "inherit"}`。碼不統一，默認正常。aos-exec 本身原樣搬、沒改。

### P-08 daemon 重開：回合數接續、pause 要持久化、沒 kill 的 stop 留下的任務〔技術選型，先這樣〕

- 層：daemon；S-08（回合數每條時間線各自數）。核心 spec 列「重開後回合數延不延續」為技術選型。
- 發生什麼與做法：
  - 回合數讀 round.json 接著數（`test_node_appears_and_round_continues` 從 41 接 42）。
  - pause 原本只在 daemon 記憶體，重開就沒了——kernel 剛 pause 的 node 會被偷偷放行。改成存 `.aosd/paused.json`（已寫進 spec.md 第 2 節）。
  - `stop`（不帶 kill）後任務照跑，但 daemon 不在就沒有 tock，它們會一直等；daemon 重開後接上（aos7-run 還在，所以不會被誤判 lost）。
  - stop 帶 kill 時，處在 idle／paused 的時間線收完任務就退出、不 tock，所以這些任務的 `ended` 要到下次 daemon 起來第一次 tock 才記。

### P-10 兩個 daemon 搶同一個空間〔技術選型，先這樣〕

- 層：daemon；S-14、S-15。
- 發生什麼：
  - 同一個 root 起兩個 daemon：會兩邊都 tick 同一個 node。加 `.aosd/daemon.lock`（flock），第二個退出碼 1（`test_second_daemon_refused`，已寫進 spec.md）。
  - 不同 root 重疊（daemon A 管 `p`，有人在 `p/team` 起 daemon B）：沒鎖，只靠「含 `.aosd/` 的子資料夾跳過」。實驗：A 做完 team 的第 2 回合，B 一建 `.aosd/`，A 記 `node-` 放手，B 從第 3 回合接著數——碰巧乾淨。但：同一個資料夾的 node id 從 `team` 變成 `.`（S-14 的 id 跟著 daemon 根走）；A 起的舊任務 `AOS7_ROOT` 仍是 `p`，它們寫的 daemon ctl 會送到已經不管這個 node 的 A；若 A 放手時剛好在回合中，那個回合就不 tock、round.json 留 `open: true`（見 P-15）。
- 先這樣：S-15 只管最基本的，默認正常。

### P-11 巢狀根靠 `.aosd/` 存在判定，子 daemon 第一次起來前會被父當 node〔技術選型，先這樣〕

- 層：daemon 掃描；S-15、S-21 路一。
- 發生什麼：路一的子 daemon 是父的任務，要等它真的跑起來才建 `sub/.aosd/`。在那之前父每 20 ms 重掃，看到 `sub/.aos/timeline.json` 就會替 sub 起一條時間線——兩個 daemon 同時 tick 同一個資料夾。
- 先這樣：測試先建 `sub/.aosd/`。真的用時，要嘛「打算給子 daemon 的資料夾先建 `.aosd/`」成為慣例，要嘛 tasks.json 的 `dirs`／某個標記讓父知道「這棵是要交出去的」。

### P-14 stop 時回合中途怎麼辦，spec 沒寫〔技術選型，先這樣〕

- 層：daemon；S-08、S-09。
- 發生什麼：stop 若直接結束，正在 running 的回合就永遠 open。
- 先這樣：回合中的時間線不等 interval，（帶 kill 時先收任務）立刻 tock 收回合再結束——等於一次提前 tock。已寫進 spec.md 第 2 節。

### P-22 ctl op、ctl 檔、輸出格式的小補〔技術選型，先這樣〕

- `aos7-ctl daemon ... stop` 需要表達 `kill: true`，加 `--kill`；aos7-ctl 原本只印路徑，改印一行 JSON `{"wrote": 路徑}`（S-01）。
- tock 要寫的 `rounds/<N>.json` 裡有「本回合 tick 起了誰、tick 時做了哪些控制」，tick 與 tock 是兩支程序，只能經檔案傳：round.json 多 `started`、`ctl` 兩欄。
- aos7-run 起不來（找不到程式）就自己寫 exit.json `code: 127` 與 `error`，否則任務永遠停在 born（見 P-07）。
- 以上都已寫進 spec.md。

## 默認正常

### P-03 任務被 reparent 給 init，daemon 只能輪詢〔默認正常〕

- 層：tick／aos7-run；S-09（tick 不等）、S-10。
- 發生什麼：tick 起 aos7-run 後就結束，aos7-run 變成 init 的子程序。daemon 不能 waitpid 任何任務，「任務都結束了沒」只能每 20 ms 讀 exit.json／pid.json＋`os.kill(pid, 0)`；殭屍還要讀 `/proc/<pid>/stat` 才分得出來。等 tock.json 的任務也一樣是輪詢（`wait_tock` 20 ms）。

### P-07 lost 判斷有競態；任務也可能永遠停在 born〔默認正常〕

- 層：tock；spec 第 5 節的狀態判斷。
- 發生什麼：任務程序剛死、aos7-run 還沒寫 exit.json 的瞬間，照 spec 字面（pid.json 在、程序不在、沒 exit.json）會被判成 lost，tock 就替它寫 `lost`，蓋掉 aos7-run 隨後要寫的真碼。做法：再看 `runner_pid`——aos7-run 還在就算活；判完再看一次 exit.json（已寫進 spec.md）。剩下的洞：aos7-run 在寫 pid.json 前就死了→任務永遠是 born（算活，tock 永遠不會因它提前）；pid 被重用→死任務被當活的。

### P-12 任務資料夾只增不減，每 20 ms 全掃〔默認正常〕

- 層：daemon、tock。
- 發生什麼：daemon 主迴圈每 20 ms 重走整棵樹找 node，status.json 每圈都對每個 node 算一次活任務（讀每個任務資料夾＋/proc）；tock 每回合也掃該 node 全部歷史任務。interval 50 ms、跑 3 秒就有上百個任務資料夾（smoke test 時 `q-r1`～`q-r15`，each 任務一回合一個）。沒有回收、沒有歸檔；成本隨歷史線性長。tid 用字典序排序（`q-r10` 在 `q-r2` 前），只影響顯示。

### P-15 node 消失時該回合不 tock〔默認正常〕

- 層：daemon；S-13。
- 發生什麼：node 資料夾被刪，tock 會因為 write_json 的 makedirs 把 `.aos/` 建回來，讓 node「復活」。所以時間線發現 gone 就直接結束、不 tock，round.json 若還 open 就留 open。node 被搬家改名（S-14 說細節隨意）＝舊 id 消失、新 id 出現、回合從 round.json 接著數，但任務的 `AOS7_NODE` 是舊路徑。

### P-17 kill 很慢會拖慢 tick／tock〔默認正常〕

- 層：任務控制；S-09「tick 很快結束」。
- 發生什麼：kill 每個任務等至多 1 秒，一個一個做；剛起還沒 pid.json 的任務還要先等 pid.json（至多 1 秒）。ctl 多的回合，tick 就不是「很快結束」，daemon 的 interval 也被吃掉。tick／tock 本身的程序成本實測各約 13 ms（Python 啟動為主）。

### P-18 ctl.json 單檔，後寫的蓋掉先寫的〔默認正常〕

- 層：任務控制；S-17、S-22。
- 發生什麼：任務控制只有一個 `ctl.json`，kernel 寫 restart、人同時寫 kill，只留最後一個；被蓋掉的那方不會知道（ctl-done.json 也只留最後一份）。daemon ctl 是一個請求一個檔，沒有這問題。

### P-19 父 kill 子 daemon 時也會打斷子 daemon 正在跑的 tick／tock〔默認正常〕

- 層：daemon × 任務控制；S-21 路一。
- 發生什麼：kill 對群組與後代送 SIGTERM，子 daemon 當下的 aos7-tick／aos7-tock 程序也是它的後代，會一起被打斷——可能 round 已 +1 但 started 沒記、或 tock.json 只寫了一半的任務。子 daemon 隨後自己的 stop-tock 會把回合收掉，所以表面上沒事；寫到一半的狀態默認正常（S-06）。
