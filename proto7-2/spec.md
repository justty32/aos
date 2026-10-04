# proto7-2 核心 spec

← [proto7-2](README.md)｜要合的：[proto7 核心 spec](../proto7/spec/core.md)（條號 S-）｜跟 proto7-1 的差別：[changes-from-7-1](notes/changes-from-7-1.md)

**這份只收核心（`lib/aos7_*.py`、`bin/`）的規則**，每條引得到 S- 條或核心選項。模組包的規則在各包的 README（總覽：[modules/README.md](modules/README.md)）；為什麼這樣定、以前怎麼錯過，在 [notes/problems.md](notes/problems.md)（文中的 P2-／A2-／A3-／W／Q／K／N 只留編號，細節去那裡查；N-／K-／Q 指 [proto7-1 需求清單](../proto7-1/notes/infra-needs.md)、[生命週期決定](../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md)）。誰負責什麼、誤用怎麼判，見[組件契約藍圖](notes/component-contracts.md)。核心要長大先答 README「防再胖」的三問。

## 0. 共同約定（S-01、S-06）

- **錯誤四分支**：核心碰到的每個錯先分類，同類只走一條路，不在各處各判一次。
  - **N 不存在**（ENOENT／ENOTDIR；程序確定不在或是殭屍）：當沒有——新空間、空槽、沒有請求。
  - **U 不知道**（其他讀取錯誤；存在但不是一般檔；/proc 讀不到或掃描不完整；**核心自己寫的檔**內容不合）：保留現狀，不前進、不做破壞性動作，記一筆、下一圈再看。停多大看事實歸誰：回合事實＝整 node，槽事實＝單槽，請求＝那一件。
  - **B 輸入不合**（**別人寫給核心的**控制檔、tasks.json、timeline.json、加掛請求格式不對）：拒收那一件並回報（回條 `ok: false`、`tasks_error`、設定用預設並記一筆），其他照做。
  - **K 中斷**（自己被殺、逾時被收）：不偵測。靠「先寫證據再動作」的順序、重做是冪等的、清掉寫者已死的暫存檔。
  - 誤用（違反組件前置條件，11 節）不另立一類：落到哪類就照哪類走；順手偵測到的記一筆，不保證偵測到、不為它加檢查。
- **判定入口**：讀檔只經一個（不存在／讀到／讀到但不是 JSON／不知道；非阻塞開，FIFO 不會卡住讀的人）；程序只經一個（不在／同一個程序的 starttime／不知道）；回合＝round.json 的判定（第 3 節）；槽＝5.4 的表。
- **紀錄格式**：status 的 `last_error`、總結的 `errors`、round.json 的 `notify_errors` 一律 `{"kind", "where", "why", "at"}`（`kind` 是錯誤類型：errno 名、`round-unknown`、`unsure`…；`why` 太長保留頭尾），需要時另帶 `slot`／`run`／`round`／`rc`。
- **三態判定**（K 系列）：推定一個事實（回合關了沒、任務活著沒、程序是不是同一個）時，結果只有是／否／不知道；不知道不能當否，也不能當是去做破壞性動作。/proc 讀不到時：不殺、不判 lost、不起新 run、不清 daemon 記著的 live／pgid。
- 狀態與控制都是 JSON 檔，`cat` 看得懂、寫檔就能操作。寫檔一律先寫 `.<名>.tmp.<pid>` 再 rename；列資料夾的人略過 `.` 開頭的。寫者確定不在的暫存檔由 tick／tock（自己的 `.aos/` 與槽，含槽的 `mount-req/`、`mount-done/`，不遞迴）、daemon（`.aosd/`、`ctl/`、`ctl-done/`）清掉。
- 多人讀—改—寫同一個檔時，對 `<檔>.lock` 拿 `flock`。`at` 欄是給人看的本機時間，邏輯不依賴牆鐘。
- **核心只留「上一次」**：每個 node 只留最近一回合的總結，每個槽只留最近一次執行的結果，daemon 的回條每個名字只留最近一份。更前面的歷史用模組（[modules/README.md](modules/README.md) 的歷史 module）。

## 1. 空間與 node：登記，不掃描（S-07、S-13～S-15）

- `aos7-daemon <root>`：`<root>` 是空間根，`<root>/.aosd/` 是 daemon 的地方。
- **node＝登記在 `.aosd/nodes.json` 的資料夾**（`{"nodes": {"team": {"by", "at"}, …}}`，只有 daemon 寫）。daemon 不掃資料夾；node id＝相對 root 的路徑（根是 `.`）。
- 登記時檢查：在 root 底下、**路上沒有符號連結**（realpath 要等於 `realpath(root)/<id>`）、路上沒有別的 daemon 的根（帶 `.aosd/` 的資料夾，S-15）。不合回條 `ok: false`。資料夾還不在照樣接受，出現時才開回合。
- 之後只防 node **本身**被換掉：daemon 每圈 lstat（不是資料夾——含換成符號連結——或 inode 變了＝missing，2.6），tick／tock 用 `O_NOFOLLOW` 開 node。絕不沿符號連結寫出空間根。
- `<node>/.aos/timeline.json` 可有可無（W12），預設 `{"interval_ms": 1000, "early_tock": false, "action_timeout_s": 30}`。讀不到或數值不合＝用預設並記一筆（B）；`interval_ms` 是有限非負數字，0 合法（不等）。
- **核心選項 `early_tock`**：`false`（預設）＝固定 interval，tick 之後等滿 interval 才 tock；`true`＝本回合起的任務都結束就提前 tock（S-09）。
- 跨 node 靠掛載（4.5，S-23），不做 FUSE。

## 2. daemon（S-03～S-06、S-18、S-21）

### 2.1 主迴圈與時間線

主迴圈每 ~20 ms：處理控制檔（有預算）→ 檢查已登記 node → 寫 status。每個已登記、資料夾在的 node 一條時間線（thread；每個動作都是獨立程序，S-04）：

1. 不變條件一（2.2）沒過 → 停在 `error`，退避（0.5 秒起加倍，最多 8 秒），回 1。
2. node 被 pause（2.4）→ 等，回 1。
3. 跑 `aos7-tick <root> <node-id>`，從 stdout 讀回起了什麼。
4. 等：固定 interval 時等滿 interval，但 tick 之後收到 `wake`（或讓 node 從有人 pause 變成沒人 pause 的 `resume`）就**提前結束這回合**（P2-01）；`early_tock` 時等到本回合起的任務都結束或滿 interval，回合中的 wake 不起作用（A2-11）。
5. 跑 `aos7-tock`（`AOS7_EARLY`＝`1` 提前、`0` 沒有）。沒關上就馬上補一次（`AOS7_INCOMPLETE=tock`）。
6. 等到離 tick 滿 interval；回合關上之後送來的 wake／resume 打斷等待。被 wake 提前結束的回合不走這步。

- **tick／tock 的退出碼只看三種**：0＝做了；3＝不知道；其他（例外、退出碼 1）＝失敗。後兩者記 `last_error`、退避、回頂端，**不算一個回合**（不扣 `rounds` 倒數）。tick 被動作逾時收掉照第 5 步 tock，總結標 `incomplete: "tick"`。
- 時間線丟例外：記 `last_error`，0.5 秒後接著跑。主迴圈一步丟例外不退出，`io_errors` +1。

### 2.2 不變條件一：回合（K-01、K-02）

- **舊回合確知已關才開下一回合**：round.json 是物件、`round` 整數、`open` 明確 `false`，或確定不存在（新空間）。其餘＝不知道 → 停在 `error` 退避、`last_error.kind: round-unknown`，不 tick，等人寫回。tick 自己也照這條檢查。
- round.json 還開著（daemon 在回合中死掉重開、補 tock 也失敗）→ 先 tock 關掉（`incomplete: "unclosed"`），成功後回頂端重新看 pause 與倒數。
- status 每個 node 寫 `round_open`（`true`／`false`／`null`＝不知道）與 `recovery_pending`。

### 2.3 控制檔（S-18、S-21 路二）

任何人寫 `<root>/.aosd/ctl/<名字>.json`，例 `{"op": "pause", "node": "team/agents/bob", "by": "team:kernel", "owner": "budget"}`：

| op | 意思 |
|---|---|
| `register` | 登記 `node`（第 1 節的檢查） |
| `unregister` | 馬上從 nodes.json 拿掉（P2-10），本回合照常收完、時間線結束。預設 kill 那個 node 的活任務（`"kill": false` 不殺；W2） |
| `pause` | 帶 `owner`：該 node 不開新回合，跑著的任務不動（2.4） |
| `resume` | 拿掉自己 `owner` 的 pause；可帶 `"rounds": N`、`"all": true`。node **因此**變成沒人 pause 時順便 wake |
| `wake` | 等下一回合的馬上開；固定 interval 的回合中收到＝提前結束這回合；`early_tock` 的回合中不起作用 |
| `stop` | 整個 daemon 結束；`"kill": true` 先 kill 所有活任務。帶 `node` 回 `ok: false`。有守門檔時照 2.7 |

- 處理完原檔搬到 `ctl-done/<同名>.json`，加 `"result": {"ok", "msg", "at", "queued_at"}`，**同名舊回條直接蓋掉**。`ok` 只表示 daemon 接受了。
- 檔名由寫的人取，建議固定（工具的編碼見[工具包](modules/tools/README.md)），回條就只留每件事的上一次（W3）。
- 讀不到（I/O）的請求留著下一圈再看。讀不懂、不是 `.json` 結尾、不是一般檔（B）：回條 `ok: false`，原物留成 `ctl-done/<名>.bad`。
- 一件處理丟例外不擋同圈其他件（特別是 stop）：效果可能已生效、不重做——刪掉請求、記 `last_ctl_error`；刪不掉就不再執行，每圈再試著刪。
- 每圈最多 200 件或 0.05 秒，剩下的照檔名順序下一圈做。寫給停著的 daemon 的控制檔留到它起來。
- `pause`／`resume`／`wake`／`register` 的 node 在別的 daemon 的根底下 → `ok: false`。
- SIGTERM／SIGINT＝`stop` 加 `kill: true`。

### 2.4 pause 帶 owner（N-81）

- `.aosd/paused.json`＝`{"paused": {"team/agents/bob": ["budget", "human"]}}`，**清單空了才開回合**；daemon 起來就寫一份。沒寫 `owner` 用 `""`。
- `resume` 只拿掉自己的 owner；`"all": true` 全清（含所有倒數）。
- **核心選項 `rounds`**：`resume` 帶 `"rounds": N`＝再跑 N 回合（回合確知關上才算）就以同一個 owner 再 pause；倒數按 owner 各記一份（A2-06），同一 owner 再 pause／resume 時清掉。status 的 `steps_left`＝`{owner: 剩幾回合}`。
- 回合中途下 pause：本回合照常收完才停。status 的 `paused_by` 列清單，`pause_pending`＝已要求、本回合還沒收完。

### 2.5 世代、動作鎖、逾時（S-06）

- **世代**：daemon 拿到 `.aosd/daemon.lock`（拿不到退出碼 1）後把 `gen.json` 的 `gen` +1，起 tick／tock 時給 `AOS7_GEN`。起來時 `nodes.json`、`paused.json`、`gen.json` 讀不到或壞掉＝不知道 → 不起來（退出碼 3），不當空的照跑、不蓋掉它們。
- **動作鎖**：tick、tock 整個動作期間拿 `<node>/.aos/action.lock`，拿到後比 `AOS7_GEN` 與 gen.json：不同就什麼都不寫、印 `{"stale": true}`；gen.json 不能用＝不知道、退出碼 3。確定是現役才寫 `action.owner.json`＝`{"pid", "gen", "starttime", "at"}`。
- **動作逾時**：tick、tock 最多跑 `action_timeout_s` 秒，超過 SIGKILL、記 `last_error`。
- **舊動作接管**：等鎖逾時時，持有者是舊世代、而且 pid 的 starttime 跟記的一樣 → SIGKILL 它；認不出＝不知道 → 不殺，`last_error.kind: stale-holder-unverified`。鎖檔不 unlink。
- **抓著目錄的 fd 做事**：daemon 經 root 的 fd 讀寫 `.aosd/`；tick、tock 經 node 的 fd 讀寫 `.aos/`（node 不在或本身是符號連結＝`{"gone": true}`；開不了但不是 ENOENT＝不知道、退出碼 3）。root 確定不在或換了 inode → stop 加 kill、status 記 `root_gone`；看不到 root 保留現狀、頂層記 `last_error`。
- tick、tock 收到 SIGTERM 不中斷，把動作做完。

### 2.6 node 消失或搬走（Q4）

- 確定不在、不是資料夾了（含換成符號連結）、inode 跟時間線開始時的不同 → kill 那個 node 的活任務、時間線停下、`phase: missing`，**登記保留**；資料夾回來就重開時間線。
- 看不到（EIO、ESTALE、EACCES…）＝不知道 → 保留時間線與記著的程序，記 `last_error`（`kind` 是 errno 名）。
- 搬家＝舊 id 的任務全死；新位置要另外 register（W1）。想暫停但保留任務用 pause。
- **收程序的範圍**（Q1 (a)）：daemon 記著的各 node 活任務 pgid（跟 `live` 每 0.25 秒更新；判不出的沿用，不清空），加上環境 `AOS7_NODE` 是那個 node、有 `AOS7_TID` 的程序。掃描不完整時照樣打記著的群組，事件記 `ok: false`。

### 2.7 stop 與守門檔（S-21）

- `stop`：時間線不等 interval，（帶 `kill` 先 kill 本 node 活任務）立刻 tock 收回合；全部結束後帶 `kill` 的再掃一次環境身分，收掉殘留（不含 aos7-run、daemon 自己與祖先）。
- **守門檔** `.aosd/stop-guard.json`：存在而 `allow` 不是 `true`（讀不到、壞掉也算）→ 控制檔 `stop` 回 `ok: false`（帶 `note`）。SIGTERM 不看守門檔。核心不知道守門的語意；子 daemon 的所有權見[子 daemon 包](modules/subd/README.md)。

### 2.8 status 與事件

`.aosd/status.json` 每圈覆寫：

```json
{"pid": 123, "root": "/abs/root", "at": "...", "poll_s": 0.02, "gen": 3, "io_errors": 0, "stopping": false, "stopped": false,
 "last_event": null, "nodes": {"team": {"round": 7, "round_open": true, "recovery_pending": false, "phase": "running",
 "paused_by": [], "pause_pending": false, "interval_ms": 1000, "early_tock": false, "live": ["kernel#3"]}}}
```

- `phase`：`idle`／`tick`／`running`／`tock`／`paused`／`error`／`missing`／`unregistering`／`stopped`。`live` 列 run id（5.2），每 0.25 秒重算（判不出的保守列入）。
- 有的話多：每 node 的 `last_error`、`last_event`、`steps_left`、`missing`；頂層的 `last_ctl_error`、`root_gone`、`last_error`（看不到 root）。判不出的槽細節不放，用[診斷包](modules/diag/README.md)按需重算。
- `stopped: true`＝正常退出前的最後一份；`at` 好幾個 `poll_s` 沒動＝daemon 可能卡住或死了。
- **事件出口**：`last_event` 只留最近一件。放一個空檔 `.aosd/log.on`，daemon 就把事件追加到 `.aosd/log.jsonl`（不清、不輪替；W9）。

## 3. 回合（S-08、S-09、S-11）

- `<node>/.aos/round.json`（tick、tock 寫）＝`{"round", "open", "tick_at", "tock_at", "started", "ctl", "mounts", "tasks_error", "reaped", "skipped", "tasks_rev"}`：tick 開回合 round +1、`open: true`；tock 設 `open: false`。
- `<node>/.aos/last-round.json`（tock 寫，**只留最近一回合**）：`{"round", "tick_at", "tock_at", "early", "started", "alive", "ended", "skipped", "ctl", "mounts", "tasks_error", "errors"}`。`ended`＝上次 tock 之後才看到結束的（`{"run", "code"}`，lost 的帶 `lost`、`never_started`，被 kill 收掉的帶 `by_ctl`）；`skipped`＝該起卻沒起的。
- 判定（daemon、tick、tock 共用）：物件、`round` 整數、`open` 是 true／false 才算讀到；確定不存在另算；其餘＝不知道。
- **回合數接續**：tick 只在明確 `open: false` 時開 `round + 1`；還開著、不知道 → 什麼都不寫、退出碼 3（不拿 last-round.json 接號，A2-02）。round.json 不存在：照 last-round.json 的 `round` 接著數，它也不存在從 1 起，它讀不到或壞掉＝不知道（P2-06）。tock 只收開著的回合；不存在、已關印 `skipped`。
- 漏掉的回合核心不補，看得到的只有「上一次」。

## 4. 任務表與 tick（S-09、S-10、S-12）

### 4.1 tasks.json：唯一的任務表

`<node>/.aos/tasks.json`＝`{"tasks": [項目…], "mount_allow": 可選}`（人、kernel、tick、工具都會寫；**寫的人一律拿 `tasks.json.lock`**）：

| 欄 | 意思 |
|---|---|
| `name` | 必填，英數、`_`、`-`（W5） |
| `argv`／`inst` | 二選一。`argv` 直接跑（cwd＝node，`$AOS7_*` 由 aos7-run 展開）；`inst` 是 inst JSON 的路徑，用 `aos-exec` 跑（S-12） |
| `mode` | `keep`＝槽沒有活任務就起，把所有空槽補滿；`each`＝每回合在一個空槽起一次，上一次還在跑就跳過；`once`＝起一次，起完 tick 刪掉這項。預設 `each` |
| `max_live` | 同名最多幾個同時跑（＝幾個槽），預設 1 |
| `from_round`／`until_round` | 第幾回合起才起（預設 1）／回合數大於它就不再起新 run（已在跑的不殺，項目與槽留著）。once 也看 |
| `enabled` | `false`＝不起，項目與槽留著（W11） |
| `mounts` | 掛載宣告（4.5） |
| `x` | 模組用的宣告欄位（物件）：tick 不看內容，照抄進 birth.json |
| `slot` | 只給 once：釘在哪個槽起 |
| `launch` | tick 寫的起動標記（4.4），別人不要動 |

- **讀**：不存在＝空表；讀不到、不是一般檔（U）＝這回合不起、記 `tasks_error`、tock 不刪槽；不是 JSON 或不是 `{"tasks": [...]}`（B）＝當空表、記 `tasks_error`。
- **寫**（G1）：讀舊內容也照三態——不存在＝從空表起；讀不到、不是一般檔、壞掉＝**拒寫**並回報，絕不當空表把整份換掉。
- 一項的欄位不合：**只跳過那一項**、記 `tasks_error`，其他照起；驗證在挑槽、算 run 之前做完。已移到模組包的舊欄位（`subroot`、`allow_stop`、`retry_lost`）也算不合，訊息指到接手的包。

### 4.2 tick 的步驟

`aos7-tick <root> <node-id>`：

1. 抓 node fd、拿動作鎖、比世代（2.5）。node 不在印 `{"gone": true}`。
2. 判上一回合已關（第 3 節），清暫存檔；補上一回合欠的 tock.json（第 7 節末）；列不出 `.aos/tasks/`＝不知道、退出碼 3。round +1，寫 round.json。
3. 執行任務控制（第 6 節）；判定每個槽（5.4，疑似 lost 先掃描）；審核活任務的加掛請求（4.5）。
4. **拿 tasks.json.lock**（最多等 1 秒；等不到這回合不起、記 `tasks_error`）：驗證、挑要起的（先 once 照檔案順序，再 keep／each），決定槽與 run；有 once 要起就在那項寫 `launch` 並寫回。鎖內重讀表照三態，不知道＝這回合一個都不起。放鎖。
5. 要重用的槽裡有「已結束、還沒報過」的 run：先記進 round.json 的 `reaped`，tock 照樣報（P2-03）。
6. 一個一個起（5.3）；一個槽一個 tick 最多起一次。
7. 起成的 once：再拿鎖，刪掉 `launch` 對得上的項（照標記比對，不照位置）；刪不掉下一個 tick 照標記比對就知道起過了。
8. stdout 印 `{"round", "started", "tasks_rev"}`（`tasks_rev`＝讀到的 tasks.json 前 12 碼 sha1，也寫進 round.json，N-80）。**不等任務。**

### 4.3 改 tasks.json 的約定

- tick 只在有 once 要處理時才改 tasks.json，一定拿鎖、整份 rename。一次加多項＝一次 `edit_json`（同一次 rename）。
- 不拿鎖直接編輯 tasks.json 的人，跟別人同時寫會有一方被蓋掉（W8）。

### 4.4 once 不重起、最多一次、不無痕消失（N-86、K-03）

`launch`＝`{"slot", "run", "round"}`，在**寫 birth.json 之前**落地。下一個 tick 看到帶 `launch` 的 once：

- 槽判定出的 run 就是標記的 run → 已經起了（或起到一半）→ 刪掉這項，不重起。
- 不是這個 run（或槽是空的）→ 上次在寫 birth 之前就被殺了 → 用新的 run 照常起。
- 判不出 → 這項留著，下一回合再看。

被殺在「寫了 birth、runner 還沒記上」之間：只能照 5.4 等兩回合判 lost，這項一次都沒跑、報成 lost（帶 `never_started`），不再起——**最多一次**。要至少一次用 [once 保證包](modules/once_retry/README.md)（P2-02）。

### 4.5 掛載（S-23）

- `mounts`＝`{"名字": "空間路徑"}`：tick 起任務時建 `mnt/<名字>`（相對符號連結，目標不在先建成資料夾）。名字不能含 `/`、不能 `.` 開頭；路徑不能絕對、realpath 後要在空間根內。不合的不掛，記在 birth.json。
- **執行中加掛**：任務寫 `mount-req/<名字>.json`＝`{"name", "path", "why"}`；下一個 tick 審核（`mount_allow`＝允許的空間路徑前綴，比 realpath；沒寫＝空間根內全給；tasks.json 讀不到＝這回合不審），回條寫 `mount-done/<同名>.json`，寫成才刪請求；成功的建 `mnt/<名字>`、在 birth.json 標 `dyn`。不卸掛。
- 每次起新的 run，照項目的宣告重建 `mnt/`，清掉 `mount-req/`、`mount-done/`。掛載只是方便，不強制（沒有 FUSE）；要記寫入用[稽核包](modules/audit/README.md)。

## 5. 任務（S-10、S-11、S-16）

### 5.1 槽：照名字重用的任務資料夾

- 槽＝`<node>/.aos/tasks/<槽名>/`：`max_live` 是 1 時槽名＝`name`，大於 1 時是 `name`、`name.1`…`name.(max_live−1)`。
- 每次在槽裡起新的 run，先清掉上一個 run 的**基礎設施檔**：`birth.json`、`pid.json`、`out.log`、`exit.json`、`tock.json`、`writes.jsonl`、`mnt/`、`mount-req/`、`mount-done/`。任務自己寫的檔留著（同槽的下一個 run 接得上，W6）；`ctl.json`／`ctl-done.json` 也不清（回條要活過新 run 起來那一刻，P2-04）。

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `birth.json` | tick | `{"name","slot","run","round","node","argv"或"inst","mounts","once","at","runner","x"?}`；`runner`＝`{"pid","starttime"}`，起了之後才補 |
| `pid.json` | aos7-run | `{"run","pid","pgid","starttime","runner_pid","at"}` |
| `exit.json` | aos7-run（lost 時 tick／tock） | `{"run","code","at","round"}`；code 負數＝被訊號殺；lost 是 `{"code": null, "lost": true, "never_started"?}`；報過之後補 `seen_round` |
| `tock.json` | tock | `{"run","round","at","early"}`，只留最新 |

- pid.json、exit.json、tock.json 的 `run` 跟 birth 不同＝上一個 run 沒清乾淨的，當不存在。
- **槽什麼時候刪**：名字不在表上（或槽號 ≥ `max_live`）、run 已結束、結束早在之前的回合報過（`seen_round` < 現在）→ tock 刪整個槽。所以 once 的結果在報完後再留一回合；**交付物寫到槽外面**（W7）。

### 5.2 run 與 tid

- tid＝槽名（`AOS7_TID`）；run＝起它的回合數，不大於上一個 run 就用上一個＋1，一定遞增（W4）。run id＝`<槽名>#<run>`。
- 身分掃描比 `AOS7_NODE`＋`AOS7_TID`＋`AOS7_RUN`：同槽上一個 run 的殘留不算這次的。

### 5.3 不變條件二：起任務的交接（K-03～K-06）

1. 判定槽（5.4）：只有空槽或已結束才往下；活著或不知道就跳過（`skipped`）。
2. 清基礎設施檔、建掛載。3. 寫 birth.json（還沒有 `runner`）。
4. 起 `aos7-run <taskdir> <fd>`（新 session；fd 是 tick 開好的槽，cwd 是抓著的 node）。5. 把 runner 的 pid 與 starttime 補進 birth。

aos7-run 經 fd 讀 birth、開 out.log，把任務起在自己的程序群組，寫 pid.json，等它結束，寫 exit.json；起之前的任何失敗寫 exit 127；fd 無效退出碼 2，不回退寫字串路徑。node 在起任務途中被搬走照 2.6 處理（鬼目錄已接受，K-06）。

### 5.4 槽的判定（三態）

| 看到 | 判定 |
|---|---|
| 沒有 birth.json | 空槽 |
| birth／exit／pid 讀不到或不是一般檔 | **不知道**：不起、不判 lost，記 `errors` |
| birth.json 內容壞掉 | **不知道**（單槽保留）；人確認沒在跑後刪 birth.json 就當空槽 |
| 有同 run 的 exit.json | 結束 |
| 任務程序（pid＋starttime 對得上）或 runner 還在 | 活 |
| 有 pid.json 而兩者確定都不在；或沒 pid.json、runner 確定不在；或兩者都沒有、birth 的 round 早 2 回合以上 | 疑似 lost → 身分掃描 |
| pid 在但 starttime 讀不到 | 不知道 → 當活（`unsure`，進總結 `errors`；K-05） |
| 其餘（剛起） | 活 |

**疑似 lost 先做身分掃描**（NODE＋TID＋RUN）：這個 run 的 aos7-run 還在＝當活（unsure）；有相符的任務程序＝先照 Q1 收掉再判 lost；確定沒有＝lost，寫 `exit.json` `{"run", "code": null, "lost": true}`。**事實出口**：birth 沒有 runner、沒有 pid.json、out.log 不存在或空（讀不到大小＝不帶）→ 帶 `never_started: true`，給模組讀。掃描不完整（列不出 /proc、stat／cmdline 讀不到；environ 讀不到權限的程序當成不是任務）、收不掉、最後重讀 exit.json 讀不到＝不知道，不判 lost。這樣 keep 重起前舊的一定已經收掉，不會雙開（K-04）——只對管理範圍內的任務成立（11 節）。

### 5.5 任務看得到什麼

- 環境：`AOS7_ROOT`、`AOS7_NODE`（絕對路徑）、`AOS7_NODE_ID`、`AOS7_TASK`（槽的絕對路徑）、`AOS7_TID`、`AOS7_RUN`；`PATH` 前面加 `bin/`；cwd＝node。
- 知道時間：輪詢 `$AOS7_TASK/tock.json`（S-11；工具包有 `aos7-wait-tock`）。漏掉的回合只看得到最新一個。
- 只碰給的資料夾（S-10、S-23）：自己的 node（扣掉巢狀的別的 node 與 daemon 根）加上掛載目標。

## 6. 任務控制（S-17）

任何人寫 `<槽>/ctl.json`＝`{"op": "kill", "run": 整數, "by", "why"}`，**tick 與 tock 時刻**執行；執行完寫 `ctl-done.json`（請求加 `result`，蓋掉舊的）再刪請求。node 被 pause 時等到 resume。槽的狀態不知道、ctl.json 讀不到＝請求留著。

- **只有 kill，`run` 必填**：op 不是 kill、`run` 缺或不是整數＝輸入不合，回條 `ok: false`、刪請求。`run` 不是槽現在的 → `ok: false`、不執行。那個 run 已結束＝成功，順便收殘留。帶 `run` 讓重播只生效一次；刪不掉時總結那筆帶 `err`。
- **kill 的範圍**（Q1 (a)）：任務的程序群組、群組成員的後代所在的群組、環境 NODE＋TID＋RUN 相符的程序。打 pid.json 記的群組前先確認：群組沒有活成員，或有成員是這個 run 的，才打（防 pgid 被重用）。SIGTERM，最多等 1 秒，還在就 SIGKILL。
- **kill 回成功的條件**：最後確認 pid.json 記的任務程序已經不在；還活著或認不出 → `ok: false`（msg 以 `unknown` 開頭）。
- restart／reload 不在核心，見[控制包](modules/control/README.md)（請求端先加釘同槽的 once，再寫 kill；tick 先處理 once，所以它先佔住槽）。

## 7. tock（S-08、S-11）

`aos7-tock <root> <node-id>`：

1. 抓 node fd、拿鎖、比世代。node 不在 `{"gone": true}`；舊世代 `{"stale": true}`；回合已關印 `skipped`（順便補欠的 tock.json）。
2. 執行任務控制（第 6 節）。
3. 掃所有槽（順便清暫存檔），照 5.4 判定、lost 的補 exit.json；判不出、當活但 unsure 的記進 `errors`。
4. **寫 last-round.json，整份讀回確認**；確認不了＝不知道、退出碼 3，回合不關，下次重來。
5. 之後才對每個活任務寫 `tock.json`（任務收到這回合的 tock 時，總結一定已經是這回合的）；寫不進去的記在 round.json 的 `notify_errors`。
6. 新結束的補 `seen_round`，刪該刪的槽（5.1；表讀不到不刪）。
7. 寫 round.json `open: false`，stdout 印總結。

- **重播**：同回合已有完整的總結（上一次寫完就被殺）→ 不重寫，只收尾（補 `seen_round`、補沒收到的 tock.json、關回合並標 `replayed`）；列不出槽就不關。總結壞掉或不完整就照常重新產生。恢復只靠 round.json 與 last-round.json。
- **欠的 tock.json**：round.json 有 `notify_errors` 時，下一個 tick 開回合前（或對已關的回合再跑 tock）照它補：同一個 run 還活著才補（帶 `late: true`）；換了 run、結束、槽不在了就丟掉；補不上的記進新回合的 `tasks_error`。

## 8. 不變條件三：清掉的東西不改上層的累計（K-07）

核心會刪的只有換 run 時上一個 run 的基礎設施檔、名字不在表上的槽（5.1）。依賴它們的上層改依賴自己的 state 檔：同槽的下一個 run 直接讀上一個 run 留下的 state；用量以 run 為單位記、由上層加總（設計見 [problems](notes/problems.md)「kernel 用量以 run 為單位」）；tock 恢復只靠第 7 節的兩份「上一次」。

## 9. 擴充點（S-10、原則 1、7）

核心不呼叫模組、不知道模組的語意，也沒有 tick／tock 裡的鉤子。模組只從檔案協定接進來——**A 任務**（tick 起，收 tock、讀「上一次」檔、寫 tasks.json、ctl）、**B argv 包裝程式**、**C 工具**——加上核心給的三個小出口：tasks.json 的 `x` 照抄進 birth（4.1）、事實欄位（`never_started`，5.4）與事件出口 `log.on`（2.8）、通用守門檔 `stop-guard.json`（2.7）。包的清單與規則見 [modules/README.md](modules/README.md)。

## 10. 工具（S-01）

`aos7-ctl`、`aos7-wait-tock` 只是替你寫檔、輪詢，LLM 直接讀寫檔一樣做得到；在[工具包](modules/tools/README.md)。

## 11. 界線

**誤用，不處理**（違反[組件契約藍圖](notes/component-contracts.md)的前置條件；核心順手偵測到的記一筆，不保證偵測到）：

- 手改或寫壞核心寫的檔（`nodes.json`、`paused.json`、`gen.json`、`status.json`、round／last-round、birth／pid／exit）——壞 birth＝不知道、單槽保留，不從旁證推回（卡 2.1、2.3）。
- 把 node 路徑的中間段換成符號連結（卡 2.1）。
- 起任務途中搬 node（卡 2.5、K-06）。
- 任務換 uid、關 dumpable、environ 不可讀：當成不是任務，「不會雙開」「kill 收得到」不包含它們（卡 2.8）。
- 任務改自己的 pgid、清 `AOS7_*`、換 session 又脫離身分（卡 2.5、2.8）。
- 不拿鎖編輯 tasks.json（W8）；控制檔檔名互蓋（W3，檔名是寫者的事）。

**已接受的界線**：

- 合作式檔案協定：防失誤，不防惡意任務；帳號隔離、FUSE、cgroup 不在範圍內。身分掃描靠環境變數，不是身分驗證。
- kill 只保證收到 Q1 的範圍；搬移造成的鬼目錄照 K-06 接受。
- 慢就慢（N-41）：每個動作一個程序，約每秒 100～150 回合，到了就一起遲到、不丟回合。
- 看得到的只有上一次：漏掉的回合、被覆寫的回條與執行結果，核心不補。
- 之後再說：keep 的 restart 政策（N-79）、pause 中做任務控制（N-82）、事件式喚醒（N-83）、成組全有全無（N-85）、out.log 大小上限（W10）。

## 12. 會停下等人的情況

「不知道」保留現狀（第 0 節），停的範圍分三種：整 node 停開回合／單槽保留／單請求等待。哪些情況會停、證據在哪、怎麼恢復，見[診斷包](modules/diag/README.md)的操作手冊；判不出的槽用 `aos7-diag <root> [node]` 按需重算。
