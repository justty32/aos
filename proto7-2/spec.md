# proto7-2 細部 spec（草稿）

← [proto7-2](README.md)｜要合的：[proto7 核心 spec](../proto7/spec/core.md)（條號 S-）｜跟 proto7-1 的差別：[changes-from-7-1](notes/changes-from-7-1.md)

**照這份做的程式在 `lib/`、`bin/`（10-04），做的時候改過的地方標「P2-」，astra 第一輪回歸（[報告](notes/play/2026-10-04-astra-1-infra.md)）之後改的標「A2-」，理由都在 [notes/problems.md](notes/problems.md)。** 寫的是規則本身；來源只標條號或一個簡短出處（N-／K-／Q 編號指 [proto7-1 需求清單](../proto7-1/notes/infra-needs.md)、[生命週期決定](../proto7-1/notes/decisions/2026-10-03-lifecycle-invariants.md)、[astra-8](../proto7-1/notes/play/2026-10-03-astra-8-infra.md)）。程式名沿用 proto7-1 的 `aos7-*`。標「W」的地方還等使用者決定（題目在 changes 最後），先照推薦寫；「Q1～Q6」是 proto7-1 使用者已答的題。

## 0. 共同約定（S-01、S-06）

- 狀態與控制都是 JSON 檔，`cat` 看得懂、寫檔就能操作。寫檔一律寫 `.` 開頭的暫存檔（`.<名>.tmp.<pid>`）再 rename；列資料夾的人略過 `.` 開頭的檔。寫的人在 rename 前被殺會留下暫存檔：tick／tock 在自己的 `.aos/` 與槽、daemon 在 `.aosd/`、`ctl/`、`ctl-done/` 清掉「寫者 pid 確定已不在」的（A2-07）。
- 讀 JSON 先看檔案型別、非阻塞開；不是一般檔（FIFO、資料夾）當不存在。
- 多人讀—改—寫同一個檔時，對 `<檔>.lock` 拿 `flock`（tasks.json、paused.json 都是）。
- `at` 欄是 ISO 8601 本機時間，只給人看，邏輯不依賴牆鐘。
- **三態判定**（K 系列的總原則）：daemon、tick、tock 要推定一個事實（回合關了沒、任務活著沒、程序是不是同一個）時，結果只有**是／否／不知道**。讀不到、EIO、starttime 讀不到、檔案半寫、缺欄位、型別不對都是「不知道」；只有 ENOENT／ENOTDIR 是「確定不存在」。「不知道」不能當「否」，也不能當「是」去做破壞性動作；處理一律是**保留現狀、記在 status（`last_error`，錯誤類型分欄放、不被截掉）或回合總結的 `errors`、下一圈再看**。下文每個判定都照這條。
- **判定收在少數幾處**（A2-01）：檔案＝三態讀檔（存在／不存在／壞掉／讀不到）；回合＝round.json 判定（3 節）；程序＝/proc 讀取（讀到／程序已不在／讀不到，讀不到一路往上傳，掃描不完整就不能當「沒有」）；槽＝5.4 的判定。/proc 讀不到時：不殺、不判 lost、不起新 run、不清 daemon 記著的 live／pgid。
- **核心只留「上一次」**（使用者 10-04 追加）：每個 node 只留最近一回合的總結，每個任務資料夾只留最近一次執行的結果，daemon 的回條每個名字只留最近一份。更前面的歷史核心不管，所以核心也沒有「保留上限」這類設定；要歷史用第 9 節的可選 module。

## 1. 空間與 node：登記，不掃描（S-07、S-13～S-15）

- `aos7-daemon <root>` 的 `<root>` 是空間根，`<root>/.aosd/` 是 daemon 自己的地方。
- **node＝登記在 `<root>/.aosd/nodes.json` 裡的資料夾**。daemon 不走資料夾找 node，只跑清單上的。node id＝相對 root 的路徑（`/` 分隔，根本身是 `.`）。
- `nodes.json`＝`{"nodes": {"team": {"by", "at"}, "team/agents/amy": {...}}}`，只有 daemon 寫（處理 `register`／`unregister` 控制檔時，第 2.3 節）。daemon 重開照這份接著跑。
- 登記時檢查：路徑在 root 底下、沒有跑出 root（realpath 後也算）、**路徑上沒有符號連結**（realpath 要等於 `realpath(root)/<id>`，A2-04）、路上沒有別的 daemon 的根（含 `.aosd/` 的子資料夾，S-15）。不合就回條 `ok: false`。資料夾目前不在照樣接受，回條註明「出現時才開回合」。
- **登記綁定實際位置**（A2-04）：之後每次用到 node（daemon 每圈檢查、tick／tock 開 node）都重驗——node 本身變成符號連結、或路徑上某一段被換成符號連結（指到 root 外、或連回搬走的同一個資料夾）＝ node 不在（2.6 的 missing），**絕不沿符號連結寫出空間根**。
- `<node>/.aos/timeline.json` 可有可無（登記本身就是 node 的標記；W12）；沒有就全用預設：

```json
{"interval_ms": 1000, "early_tock": false, "action_timeout_s": 30}
```

- `interval_ms` 不是有限非負數字時用 1000，並在 status 的 `last_error` 記一筆；修好下一回合生效。0 合法（不等）。
- `early_tock`：預設 `false`＝**固定 interval**，tick 之後等滿 interval 才 tock。`true`＝本回合 tick 起的任務都結束就提前 tock（S-09 的「也可能提前進場」）。使用者 10-04。
- FUSE 不做。跨 node 靠掛載（第 4.5 節，S-23）。

## 2. daemon（S-03～S-06、S-18、S-21）

### 2.1 主迴圈與時間線

daemon 主迴圈每 ~20 ms：讀控制檔（有預算）→ 檢查已登記 node 在不在 → 寫 status。

每個已登記、資料夾在的 node 一條時間線迴圈（daemon 內用 thread 管迴圈；每個動作都是獨立程序，S-04）：

1. 不變條件一（2.2）沒過 → 停在 `error`，退避重試（0.5 秒起加倍，最多 8 秒），回 1。
2. node 被 pause（2.4）→ 等，回 1。
3. 跑 `aos7-tick <root> <node-id>`，從 stdout 讀回本回合起了什麼。
4. 等：`early_tock: false` 時等到離 tick 滿 interval；`true` 時等到「本回合起的任務都結束」或「滿 interval」先到者。
5. 跑 `aos7-tock <root> <node-id>`（環境 `AOS7_EARLY`＝`1` 提前、`0` 沒有）。tock 完 round.json 沒關上 → 馬上補一次 tock（`AOS7_INCOMPLETE=tock`）。
6. 等到離本回合 tick 滿 interval（**回合關上之後**送來的 `wake`、`resume` 會打斷這段等待；回合中送來的照「回合中照舊」不起作用，也不留到這裡才生效，A2-11），回 1。`early_tock: false` 時第 4 步已經等滿 interval，這段幾乎是 0：固定 interval 的 node 整段都在回合中，`wake` 照「回合中照舊」不起作用（P2-01，要使用者決定）。

時間線迴圈丟任何例外：記 `last_error`，等 0.5 秒接著跑。主迴圈任一步丟例外不退出，status 的 `io_errors` +1，下一圈再試。

### 2.2 不變條件一：回合（K-01、K-02）

- **舊回合「確知已關」才開下一回合。** 確知已關＝round.json 是物件、`round` 是整數、`open` **明確是 `false`**；round.json 確定不存在（新空間）也可以開。讀不到、半寫、缺 `open`、`open` 不是 true／false、`round` 不是整數＝不知道 → 停在 `error` 退避、`last_error` 寫原因（`kind: "round-unknown"`），不 tick，等人確認後寫回 round.json（A2-02）。tick 自己也照這條檢查（3 節），不只靠 daemon。
- round.json 還是 `open: true`（daemon 在回合中死掉重開、補 tock 也失敗）→ 先跑一次 tock 關掉它（總結標 `incomplete: "unclosed"`），成功後**回到迴圈頂端**重新看 pause 與 `rounds` 倒數，不直接往下 tick。
- status 對每個 node 寫 `round_open`（`true`／`false`／`null`＝不知道）與 `recovery_pending`。

### 2.3 控制檔（S-18、S-21 路二）

任何人寫 `<root>/.aosd/ctl/<名字>.json`：

```json
{"op": "pause", "node": "team/agents/bob", "by": "team:kernel", "owner": "budget"}
```

| op | 意思 |
|---|---|
| `register` | 登記 `node`（第 1 節的檢查）。已登記回 `ok: true`、註明「已登記」 |
| `unregister` | 取消登記：馬上從 nodes.json 拿掉（P2-10），本回合不等 interval、照常 tock 收完，然後時間線結束。預設 kill 那個 node 上的活任務（`"kill": false` 不殺，任務從此收不到 tock，由寫的人負責；W2） |
| `pause` | 該 node 不開新回合（跑著的任務不動），帶 `owner`（2.4） |
| `resume` | 拿掉自己 `owner` 的 pause；可帶 `"rounds": N`、`"all": true`（2.4）。node 因此變成沒人 pause 時，順便打斷等待、馬上開回合（同 `wake`；N-84） |
| `wake` | node 正在等下一回合就馬上開；回合中照舊 |
| `stop` | 整個 daemon 結束；`"kill": true` 先 kill 所有活任務。帶 `node` 回 `ok: false`（想停一個 node 用 pause 或 unregister）。子 daemon 要擁有者允許（2.7） |

- 處理完把原檔搬到 `<root>/.aosd/ctl-done/<同名>.json`，加 `"result": {"ok", "msg", "at", "queued_at"}`。**同名的舊回條直接蓋掉**（每個名字只留最近一份）。`ok` 只表示 daemon 接受並改了狀態；真的停了沒要看 status。
- **檔名由寫的人取，建議固定**（`<by>.<op>.<node>[@<owner>].json` 這類），這樣回條自然只留「每個寫的人、每個 owner、每件事的上一次」，不會越積越多；每次取新名字的人，回條留多少由他自己收（W3）。`aos7-ctl` 預設就用固定名，帶 `--owner` 時檔名含 owner：不同 owner 是不同控制者，daemon 處理前的待辦請求不互相蓋掉（A2-13）。
- 讀不懂的、不是 `.json` 結尾、不是一般檔的：照樣寫回條 `ok: false`（原物搬成 `ctl-done/<名>.bad`，同樣蓋掉舊的）。
- 一件處理丟例外不擋同圈其他件（特別是 stop）：原物搬到 `.aosd/ctl-failed/<名>`（蓋掉同名舊的），status 記 `last_ctl_error`；效果可能已生效，所以不重做——搬不走而留在 `ctl/` 的也不再執行，只每圈再試著搬（daemon 重開後才會被當成新請求）。
- **每圈有預算**：最多 200 件或 0.05 秒，先到為準，剩下的照檔名順序下一圈做。
- 寫給停著的 daemon 的控制檔留在 `ctl/`，下次起來才做（子 daemon 起來前先登記 node 就靠這個）。
- `pause`／`resume`／`wake`／`register` 的 node 落在別的 daemon 的根底下 → `ok: false`，msg 說它屬於哪個 daemon。
- SIGTERM／SIGINT＝`stop` 加 `kill: true`（路一：子 daemon 被父時間線 kill 時帶走自己的任務）。

### 2.4 pause 帶 owner（N-81）

- `<root>/.aosd/paused.json`＝`{"paused": {"team/agents/bob": ["budget", "human"]}}`：每個 node 一份「誰在 pause 它」的清單，**清單空了才開回合**。daemon 一起來就寫一份（空的也寫）。
- `pause` 把 `owner` 加進清單；沒寫 `owner` 時用 `""`（不帶 owner 的人共用一格，行為跟 proto7-1 的單一開關一樣）。
- `resume` 只拿掉自己的 `owner`；`"all": true` 全清（人工推翻用）。
- `resume` 帶 `"rounds": N`：拿掉自己的 owner，再跑 N 回合（回合真的關上才算一回合），到了自動以同一個 owner 再 pause。之後同一 owner 的 pause／resume 清掉倒數。**倒數按 owner 各記一份**（A2-06）：A 的 rounds 不會被 B 的 rounds 蓋掉，每關上一回合各扣一，誰到零誰再 pause；`"all": true` 清掉全部倒數。status 的 `steps_left`＝`{owner: 剩幾回合}`。
- 回合中途下 pause：本回合照常 tock 完才停。status 的 `paused_by` 列清單，`pause_pending`＝已要求、本回合還沒收完。

### 2.5 世代、動作鎖、逾時（S-06）

- **世代**：daemon 拿到 `.aosd/daemon.lock`（flock；鎖不到就退出碼 1）後把 `.aosd/gen.json` 的 `gen` +1，起 tick／tock 時給 `AOS7_GEN`。
- **動作鎖**：tick、tock 整個動作期間對 `<node>/.aos/action.lock` 拿 flock，拿到後比對 `AOS7_GEN` 與 gen.json，不同就什麼都不寫（連 action.owner.json 也不寫）、印 `{"stale": true}`；gen.json 讀不到或不是 `{"gen": 整數}`＝不知道 → 什麼都不寫、退出碼 3。確定是現役才寫 `action.owner.json`＝`{"pid", "gen", "starttime", "at"}`。
- **動作逾時**：tick、tock 最多跑 `action_timeout_s` 秒，超過 SIGKILL、記 `last_error`。tick 被收掉的回合，tock 收到 `AOS7_INCOMPLETE=tick`。
- **舊動作接管**：等鎖逾時時讀 action.owner.json，`gen` 比自己舊、而且那個 pid 現在的 starttime 跟記的一樣 → SIGKILL 它。認不出身分（讀不到、starttime 不同或讀不到）＝不知道 → **不殺**，`last_error` 寫人工恢復提示。鎖檔不 unlink。
- **抓著目錄的 fd 做事**：daemon 抓住 root 的 fd，`.aosd/` 一律經 fd 讀寫；tick、tock 抓住 node 的 fd（開的時候不跟最後一段的符號連結，開到後 realpath 要等於登記的實際位置，不是就印 `{"gone": true}`；開不了但不是 ENOENT＝不知道、退出碼 3；A2-04），`.aos/` 一律經 fd 讀寫。root 確定不存在或換了 inode → 照 `stop` 加 `kill` 收尾、status 記 `root_gone: true`；看不到 root（EIO 等）保留現狀、status 頂層記 `last_error`。
- tick、tock 收到 SIGTERM 不中斷，把動作做完（SIGKILL 保底）。

### 2.6 node 消失或搬走（Q4）

daemon 每圈只看**已登記**的 node：

- 資料夾**確定不存在**（ENOENT／ENOTDIR）、inode 跟時間線開始時記的不同（被搬走、換成別的資料夾）、**變成符號連結或路徑經過符號連結**（A2-04；看 node 用 lstat 加 realpath 比對）→ kill 那個 node 上的活任務（範圍見 2.6 末），時間線停下，status 的 `phase` 記 `missing`，**登記保留**；資料夾再出現就重新開時間線（先照 2.2 收掉沒關的回合）。
- 看不到（ESTALE、EIO、EACCES…）＝不知道 → 保留時間線與記著的程序，記 `last_error`（`kind` 是 errno 名），下一圈再看。
- 搬家＝舊 id 的任務全死；新位置**要另外 register** 才會跑（沒有掃描就沒有自動發現；W1）。
- 想暫停但保留任務：用 pause。

收程序的範圍（Q1 選 (a)）：daemon 平常記著各 node 活任務的 pgid（跟 status 的 `live` 一起每 0.25 秒更新；列不出槽或判不出的槽沿用上次記的，不清空），再加上環境變數 `AOS7_NODE` 是那個 node、有 `AOS7_TID` 的程序。剛起不到 0.25 秒又清掉環境變數的可能漏收，由任務自負。/proc 掃描不完整時只打記著的群組，事件記 `ok: false`。

### 2.7 stop 與子 daemon 的所有權（S-21、Q5）

- `stop`：回合中途的時間線不等 interval，（帶 `kill` 時先 kill 本 node 活任務）立刻 tock 收回合；所有時間線結束後，帶 `kill` 的再掃一次 `/proc/*/environ`，收掉 `AOS7_NODE` 是本 daemon 任一 node、又有 `AOS7_TID` 的程序（不含 aos7-run、daemon 自己與祖先）。
- **子 daemon**（路一）：tasks.json 項目帶 `subroot`（第 4.1 節）起的任務。`<subroot>/.aosd/owner.json` 分兩塊（K-08）：
  - `owner`＝`{"node", "tid", "allow_stop"}`：權限，任務重起時照項目重寫，人手重開沿用。
  - `daemon`＝`{"pid", "since"}`：現役 daemon，每次拿到 daemon.lock 都更新。
  - 由子 daemon **拿到鎖之後**自己寫：tick 只給任務 `AOS7_OWNER_NODE`、`AOS7_OWNER_TID`、`AOS7_ALLOW_STOP`，子 daemon 照這三個寫完就從自己環境拿掉。
- 子 daemon 收到控制檔 `stop`：有 owner.json 而 `owner.allow_stop` 不是 `true`（檔壞掉也算）→ 不停，回條說它屬於誰。允許 → 先寫 `<subroot>/.aosd/stopped.json`＝`{"by", "why", "at", "kill"}` 再停。SIGTERM 照停、不看 allow_stop。
- 擁有者 node 的 tick 起帶 `subroot` 的任務前：子根有 stopped.json、或 `<subroot>/.aosd/daemon.lock` 已經有人拿著、或同一個 tick 已有別項認領這個子根 → 不起，記 `tasks_error`。刪掉 stopped.json，下一回合照常起。daemon 起來時看到 stopped.json（多半是人手跑）→ 刪掉、status 記 `last_event`。
- 子 daemon 起來時 nodes.json 是空的：起它的任務要先往 `$AOS7_SUBROOT/.aosd/ctl/` 寫 `register`（子 daemon 還沒起也行，起來就處理）。

### 2.8 status

`<root>/.aosd/status.json`（daemon 每圈覆寫）：

```json
{"pid": 123, "root": "/abs/root", "at": "...", "poll_s": 0.02, "gen": 3, "io_errors": 0,
 "stopping": false, "stopped": false, "last_event": null,
 "nodes": {"team": {"round": 7, "round_open": true, "recovery_pending": false,
                    "phase": "running", "paused_by": [], "pause_pending": false,
                    "interval_ms": 1000, "early_tock": false, "live": ["kernel#3"]}}}
```

- `phase`：`idle`／`tick`／`running`／`tock`／`paused`／`error`／`missing`／`unregistering`（已 unregister、本回合還沒收完；P2-12）／`stopped`。
- `live` 列 run id（第 5.2 節），每 0.25 秒重算。
- 有的話多 `last_error`（每 node：`{"prog", "rc", "round", "at", "kind", "err"}`；`kind` 是錯誤類型，`err` 太長時保留開頭與結尾，A2-08）、`uncertain`（每 node：判不出的槽 `[{"slot", "run", "why"}]`——UNKNOWN、pid／starttime 讀不到當活的、birth 壞掉的，A2-08）、`last_ctl_error`、`root_gone`、頂層 `last_error`（看不到 root）、`steps_left`。
- `last_event`（全域與每 node 各一）：最近一件值得看的事（`node-gone-kill`、`stale-holder-kill`、`stopped-cleared`…），只留最近一件。
- `stopped: true`＝正常退出前寫的最後一份；`at` 好幾個 `poll_s` 沒動，daemon 可能卡住或死了。
- 核心**沒有 log.jsonl**：要事件流水帳用第 9 節的可選開關。

## 3. 回合（S-08、S-09、S-11）

`<node>/.aos/round.json`（tick、tock 寫）＝`{"round": 3, "open": true, "tick_at", "tock_at", "started", "ctl", "mounts", "tasks_error"}`：tick 把 round +1、`open: true`；tock 設 `open: false`。第一次 tick 的回合是 1，daemon 重開後接著數。

`<node>/.aos/last-round.json`（tock 寫，**覆寫，只留最近一回合**）：

```json
{"round": 3, "tick_at": "...", "tock_at": "...", "early": false,
 "started": ["job#3"], "alive": ["kernel#1"],
 "ended": [{"run": "job#2", "code": 0}, {"run": "x#2", "code": -15, "by_ctl": {"op": "kill", "by": "..."}}],
 "skipped": [{"name": "job", "why": "busy"}],
 "ctl": [], "mounts": [], "tasks_error": [], "errors": []}
```

- `ended`＝上次 tock 之後才看到結束的任務；`skipped`＝這回合該起卻沒起的（還在跑、子根被擋、沒空槽…）。
- round.json 的判定（daemon、tick、tock 共用一個；A2-02）：物件、`round` 是整數、`open` 是 true／false 才算讀到；確定不存在另算；其餘（讀不到、半寫、缺欄、型別不對）＝不知道。
- 回合數接續：tick 只在 round.json 明確 `open: false` 時開 `round + 1`；`open: true`（上一回合沒關）、不知道 → 什麼都不寫、退出碼 3，等 tock 收掉或人寫回（**不再用 last-round.json 的 `round` 接著數**：那樣會把還開著的同號回合再開一次、蓋掉它的 `reaped`）。round.json 不存在：tick 用 last-round.json 的 `round` 接著數，last-round.json 也不存在就從 1 起，它讀不到或壞掉＝不知道（P2-06）。tock 只收 `open: true` 的回合；不存在、已關印 `skipped`；不知道退出碼 3。tick／tock 推定不了時什麼都不寫，退出碼 3（daemon 照 2.2 退避）。
- 漏掉的回合（例如任務太忙、只看到最新的 tock）核心不補，看得到的只有「上一次」；要每回合都留，用第 9 節。

## 4. 任務表與 tick（S-09、S-10、S-12）

### 4.1 tasks.json：唯一的任務表

`<node>/.aos/tasks.json`（人、kernel、tick、tock 都會寫；**寫的人一律拿 `tasks.json.lock`**）：

```json
{"tasks": [
  {"name": "kernel", "mode": "keep", "argv": ["aos7-kernel"]},
  {"name": "job", "mode": "each", "argv": ["python3", "job.py"], "max_live": 2},
  {"name": "fix", "mode": "once", "argv": ["sh", "fix.sh"], "from_round": 12},
  {"name": "x", "mode": "keep", "inst": "x.inst.json", "mounts": {"bob": "team/agents/bob/inbox"}}
]}
```

| 欄 | 意思 |
|---|---|
| `name` | 必填，只能用英數、`_`、`-`（`.` 留給槽號，第 5.1 節）。不合的整項跳過（W5） |
| `argv`／`inst` | 二選一。`argv` 直接跑（相對路徑以 node 為 cwd；`$AOS7_*` 由 aos7-run 展開）；`inst` 是 inst JSON 的路徑，用 `aos-exec` 跑（S-12） |
| `mode` | `keep`＝槽沒有活任務就起，每次把所有空槽補滿（常駐）；`each`＝每回合在一個空槽起一次，**上一次還在跑就跳過這回合**（`max_live` 是 1 時跟 keep 行為一樣，W5）；`once`＝起一次，起完 tick 把這項從 tasks.json 刪掉。預設 `each` |
| `max_live` | 同名最多幾個同時跑（＝幾個槽），預設 1 |
| `from_round` | 第幾回合起才生效（預設 1）。`once` 也看，所以「第 12 回合才跑一次」寫一項就好；supervisor 的退避就是改它（N-79 的 not_before） |
| `enabled` | 預設 `true`；`false` 時不起，但項目與槽都留著（N-79，W11） |
| `mounts` | 掛載宣告（4.5） |
| `subroot`、`allow_stop` | 子 daemon（2.7）。`subroot` 要在自己 node 底下、不能是 node 本身，也不能包住父 daemon 已登記的 node |
| `slot` | 只給 `once`：指定要起在哪個槽（restart 用，第 6 節） |
| `restart_of`、`mounts_dyn` | 只給 restart 寫的 `once` 項 |
| `launch` | tick 寫的起動標記（4.4），別人不要動 |

- 欄位型別不對（`name`、`argv`、`mode`、`max_live`、`from_round`、`enabled`、`mounts`、`subroot`、`allow_stop` 任一）：**只跳過那一項**，記 `tasks_error`，其他照起；整份讀不懂當空表。驗證在挑槽、算 run 之前做完。
- 想一次加一批任務：一次 `edit_json` 加多項（同一次 rename，同一回合看到）。全有全無的成組准入（N-85）不做，要的用合作式協定。

### 4.2 tick 的步驟

`aos7-tick <root> <node-id>`：

1. 抓 node fd、拿 action.lock、比世代（2.5）。node 不在 → 印 `{"gone": true}`、什麼都不寫。
2. 照第 3 節判定上一回合已關，清 `.aos/` 裡寫者已死的暫存檔，round +1，寫 round.json。
3. 執行任務控制（第 6 節），審核活任務的加掛請求（4.5）。
4. **拿 tasks.json.lock**（最多等 1 秒；等不到這回合不從 tasks.json 起任何東西，記 `tasks_error`）：讀、驗證、挑這回合要起的（先 `once`，照檔案順序；再 `keep`／`each`），替每個要起的決定槽與 run（第 5 節）；有 `once` 要起就在那項寫 `launch` 標記並寫回 tasks.json。放鎖。
5. 一個一個起（5.3）。一個槽一個 tick 最多起一次。
6. 有起成的 `once`：再拿鎖，刪掉 `launch` 標記對得上的那些項（照標記比對，不照位置；中間有人改過檔也不會刪錯），放鎖。
7. stdout 印 `{"round": N, "started": [run id...], "tasks_rev": "<讀到的 tasks.json 前 12 碼 sha1>"}`。**不等任務。**

要重用的槽裡如果有「已結束、還沒在 last-round.json 報過」的 run（tock 之後才結束、下一個 tick 就重用），清掉之前先把它記進 round.json 的 `reaped`，tock 併進 `ended` 照樣報（P2-03）。`.aos/tasks/` 列不出來（I/O）＝不知道，在寫 round.json 之前就退出碼 3。

`tasks_rev` 也寫進 round.json，看得出這回合用的是哪一版表（N-80）。

### 4.3 tick 改 tasks.json 的約定

- tick 只在有 `once` 項要處理時才改 tasks.json，而且一定拿鎖、整份 rename。
- 不拿鎖直接編輯 tasks.json 的人（例如用編輯器存檔），跟 tick 同時寫會有一方被蓋掉（W8）。工具與 kernel 一律用 `edit_json`。

### 4.4 once 不重起、最多一次、不無痕消失（N-86、K-03）

`launch`＝`{"slot": "fix", "run": 12, "round": 12}`，在**寫 birth.json 之前**寫進那項。下一個 tick 看到已有 `launch` 的 once 項：

- 那個槽判定出的 run（5.4，birth.json 壞掉時看同槽 exit.json／pid.json 的 `run`）是同一個 `run` → 已經起了（或起到一半，交給 5.3／5.4 判定）→ 直接刪掉這項，不重起。
- 判定出的 run 不是這個 run（或槽是空的）→ 上次在寫 birth.json 之前就被殺了，任務確定沒起 → 用新的 run 照常起，更新標記。
- 判不出（birth.json 讀不到、壞掉又沒有其他證據）→ 不知道 → 這項留著，下一回合再看（A2-03：以前 birth 壞掉＋掃不到活程序當空槽，已跑完的 once 會再跑一次）。

所以 tick 在任何一步被殺，once 項都不會變兩份，也不會無痕消失。代價：被殺在「寫了 birth.json、runner 還沒記進去」這一段時，分不出 runner 起了沒，只能照 5.4 等兩回合判 lost——這項**一次都沒跑，但會在 `ended` 報成 lost**（最多一次，不是至少一次；P2-02，要使用者決定）。

### 4.5 掛載（S-23）

- `mounts`：`{"名字": "空間裡的路徑"}`。tick 起任務時在任務資料夾建 `mnt/<名字>`（相對符號連結，目標不在先建成資料夾）。名字不能含 `/`、不能以 `.` 開頭；路徑不能絕對、realpath 後要在空間根內。不合的不掛，記在 birth.json。
- `mount_allow`（tasks.json 頂層，可選）：執行中加掛允許的空間路徑前綴，比 realpath 後的實際位置。沒寫＝空間根內全給。
- **執行中加掛**：任務寫 `$AOS7_TASK/mount-req/<名字>.json`＝`{"name", "path", "why"}`；下一個 tick 審核，回條寫 `mount-done/<同名>.json`（**寫成功才刪請求**），成功的建 `mnt/<名字>`、在 birth.json 標 `dyn`。卸掛不做。
- 每次起新的 run，tick 依定義重建 `mnt/`（宣告的，加上 restart 帶的 `mounts_dyn`），清掉 `mount-req/`、`mount-done/`。
- 不強制（沒有 FUSE）；可選的寫入紀錄（`AOS7_AUDIT`）照 proto7-1 第 5 節，`writes.jsonl` 也只留這次 run。

## 5. 任務（S-10、S-11、S-16）

### 5.1 槽：照名字重用的任務資料夾

- 任務資料夾＝`<node>/.aos/tasks/<槽名>/`。`max_live` 是 1 時槽名就是 `name`；大於 1 時是 `<name>`、`<name>.1`、`<name>.2`…到 `<name>.(max_live−1)`（調大調小都不改既有槽的名字）。
- **同名重用、覆寫**：每次在槽裡起新的 run，tick 先清掉上一個 run 的基礎設施檔（下表），再寫新的。每回合發生什麼只留在 last-round.json；資料夾數目只跟「有幾個名字、幾個槽」有關，不隨回合長。
- **任務自己寫的檔留著**（state.json、kernel-state.json、usage.json、progress.json…）：同一個槽的下一個 run 看得到，等於自動「接前任」（W6）。

| 基礎設施檔（換 run 時清掉） | 誰寫 | 內容 |
|---|---|---|
| `birth.json` | tick | `{"name","slot","run","round","node","argv"或"inst","mounts","once","restart_of","at","runner"}`；`runner`＝`{"pid","starttime"}`，Popen 之後才補上 |
| `pid.json` | aos7-run | `{"run","pid","pgid","starttime","runner_pid","at"}` |
| `out.log` | 任務 | stdout＋stderr（這次 run 的） |
| `exit.json` | aos7-run（lost 時 tock） | `{"run","code","at","round"}`；code 負數＝被訊號殺；lost 是 `{"code": null, "lost": true}`；tock 報過之後補 `seen_round` |
| `tock.json` | tock | `{"run","round","at","early"}`，覆寫、只留最新 |
| ~~`ctl.json`／`ctl-done.json`~~ | 任何人／tick、tock | **不在換 run 時清**（P2-04）：各只有一份、下一次控制就蓋掉；restart 的回條要活過新 run 起來那一刻，請求者才讀得到。回條 `result.run` 記它作用在哪個 run |
| `mnt/`、`mount-req/`、`mount-done/`、`writes.jsonl` | tick／任務 | 第 4.5 節 |

- 讀到的 pid.json、exit.json、tock.json 的 `run` 跟 birth.json 不同 → 是上一個 run 沒清乾淨的，當不存在。
- **槽什麼時候刪**：名字已不在 tasks.json（或槽號 ≥ 現在的 `max_live`）、run 已結束、而且結束已經在某一回合的 last-round.json 報過（`seen_round` 比現在的回合小）→ tock 刪掉整個槽（含任務自己寫的檔）。所以 once 任務的資料夾在報完結束後再留一回合；**交付物要寫到槽外面**（W7）。

### 5.2 run 與 tid

- **tid＝槽名**（`AOS7_TID`），是「哪個資料夾」。**run**＝這個槽第幾次起，整數，寫在 birth.json，也給任務 `AOS7_RUN`。
- run 的值＝起它的回合數；萬一不大於上一個 run（回合數被人手倒退）就用上一個 run＋1。一個槽一個 tick 最多起一次，所以 run 一定遞增（W4）。
- **run id**＝`<槽名>#<run>`（例如 `job.1#57`），status、last-round.json、回條裡指「哪一次」都用它。
- 身分掃描（kill 收程序、lost 前的確認）比對 `AOS7_NODE`＋`AOS7_TID`＋`AOS7_RUN` 三個：同一個槽上一個 run 留下的孫程序，不會被算成這次的，kill 這次也不會打到上一次的（反之亦然）。

### 5.3 不變條件二：起任務的交接（K-03～K-06）

tick 在一個槽起新的 run：

1. 判定這個槽現在的 run（5.4）。只有「沒有」或「已結束」才往下；活著或不知道就跳過（記進 `skipped`）。
2. 清掉上一個 run 的基礎設施檔，重建 `mnt/`。
3. 寫 birth.json（這時還沒有 `runner`）。
4. 比對 node 的路徑與抓著的 fd 還是同一個資料夾，再 Popen `aos7-run <taskdir> <fd>`（新 session；`<fd>` 是 tick 開好的任務資料夾 fd，cwd 是抓著的 node）。
5. 把 runner 的 pid 與 starttime 補進 birth.json。

aos7-run：經 fd 讀 birth.json、開 out.log；起任務前最後確認一次 `AOS7_TASK`／`AOS7_NODE` 跟抓著的 fd、cwd 是同一個資料夾，不是就不起、寫 `exit.json` `{"code": 127, "error"}`；起在自己的程序群組，寫 pid.json，等它結束，寫 exit.json。任何起程序前的失敗都寫 exit 127。fd 無效時退出碼 2，不回退去寫字串路徑。

**搬移的界線（K-06）**：node 在起任務途中或執行中被搬走，照 2.6 處理（舊任務收掉，新位置要 register）。任務死前經字串路徑寫出的「鬼目錄」是已接受的界線；不再往後加更晚的檢查。

### 5.4 任務狀態的判定（三態）

照槽裡 birth.json 的 run：

| 看到 | 判定 |
|---|---|
| 沒有 birth.json | 空槽 |
| birth.json 讀不到（I/O） | **不知道**：不起、不判 lost，記 `errors` |
| birth.json 內容壞掉（半寫、不是物件、run 不是整數） | **掃不到活程序不是「從未執行」的證明**（A2-03）：身分掃描（只比 NODE＋TID）有相符活程序＝活（run 不明）；沒有時看同槽其他證據——exit.json 帶 run R＝結束（run R）；只有 pid.json 帶 run R＝疑似 lost（run R）；都沒有＝**不知道**（等人確認後刪掉 birth.json 才當空槽）。換 run 時先清舊的 pid／exit 才寫新 birth，所以這些檔一定是這個 run 的 |
| 有同 run 的 exit.json | 結束 |
| 有 pid.json：任務程序（pid＋starttime 對得上）或 runner 還在 | 活 |
| 有 pid.json、兩者確定都不在 | 疑似 lost → 身分掃描 |
| 沒有 pid.json、runner 確定已不在（pid 不在或 starttime 不同） | 疑似 lost → 身分掃描 |
| 沒有 pid.json、沒有 runner、birth 的 round 已比現在早 2 回合以上 | 疑似 lost → 身分掃描（tick 與 runner 都死了，K-03） |
| starttime 或 `/proc/<pid>/stat` 讀不到（pid 還在） | **不知道** → 當活（保守），原因進 tock 總結的 `errors`（`phase: "unsure"`）與 status 的 `uncertain`（K-05、A2-01、A2-08） |
| 其餘（剛起） | 活 |

**疑似 lost 一律先做身分掃描**（NODE＋TID＋RUN）：找到相符的活程序 → 先照 Q1 範圍 kill，再判 lost；**確定**找不到 → lost。lost 寫 `exit.json` `{"run", "code": null, "lost": true}`（tock，以及要在這個槽起新 run 的 tick；P2-03）。收了 SIGKILL 還在、掃描不完整（列不出 /proc、某個程序的 stat／environ 讀不到；A2-01）、最後重讀 exit.json 讀不到＝不知道，不判 lost。這樣 keep 重起前舊的一定已經收掉，不會雙開（K-04）。environ 是 EACCES 的程序（別的 uid、不可 ptrace 的）讀不到身分，當成不是任務（11 節）。

### 5.5 任務看得到什麼

- 環境：`AOS7_ROOT`、`AOS7_NODE`（絕對路徑）、`AOS7_NODE_ID`、`AOS7_TASK`（槽資料夾絕對路徑）、`AOS7_TID`（槽名）、`AOS7_RUN`；帶 `subroot` 的另有 `AOS7_SUBROOT` 與三個 owner 變數；`PATH` 前面加 `bin/`。cwd＝node。
- 知道時間：輪詢 `$AOS7_TASK/tock.json`（S-11），或 `aos7-wait-tock [--after N] [--timeout 秒]`。漏掉的回合只看得到最新一個。
- 只碰給的資料夾（S-10、S-23）：自己的 node（扣掉巢狀的別的 node 與 daemon 根）加上掛載目標。

## 6. 任務控制（S-17）

任何人寫 `<槽>/ctl.json`＝`{"op": "kill"或"restart", "by", "why", "run": 可選, "reload": 可選, "id": 可選}`。**tick 與 tock 時刻**才執行；執行完搬成 `ctl-done.json`（蓋掉舊的）加 `result`。node 被 pause 時等到 resume。槽的狀態不知道、或 ctl.json 讀不到時**請求留著**，下一次再看（不寫 ok:false 的回條）。

- **`run`（可選）**：指定要收的是哪一次。跟槽現在的 run 不同（已經換人）→ 不執行、`ok: false`。不寫＝現在這次。
- **kill 的範圍**（Q1 (a)）：任務的程序群組、群組成員活著的後代所在的群組、環境變數 NODE＋TID＋RUN 相符的程序（含被 init 收養的）。打群組前先確認群組裡有程序的環境是這個任務，不是就不打（防改了 pgid 的任務讓 kill 打到別人）。SIGTERM，最多等 1 秒，還在就 SIGKILL。故意脫離（setsid 又改環境、刪自己的槽）由任務自負。
- 已結束的任務：kill 算成功，順便收掉相符的殘留程序。
- **restart**：在 tasks.json（拿鎖，最多等 1 秒，等不到整個 ctl 不執行）加一項 `once`，然後 kill（先加後殺：中途被殺時 once 項等槽空了才起，不會「殺了沒重起」；P2-07）。once 項的 `slot`＝這個槽、定義照 birth.json（`name`、`argv`／`inst`、`subroot`、`allow_stop`、`mounts` 宣告，執行中加掛的寫進 `mounts_dyn`）、`restart_of`＝原 run id、`ctl_id`＝這份請求的識別。下一個 tick 起它（維持 S-10「任務一律由 tick 啟動」），新 run 的 birth.json 也帶 `ctl_id`。槽沒換，所以任務自己寫的 state 接得上。
- **重播只生效一次**（A2-05）：處理到一半被殺時，同一份 ctl.json 下次會再執行。`ctl_id`＝請求的 `id`（有寫的話），否則＝原始內容加檔案 mtime 的雜湊（重播時不變；有人重新寫一份就變）。槽現在的 birth.json 帶同一個 `ctl_id` → 已經重起過，只補回條、不 kill；tasks.json 已有同 `ctl_id` 的 once 項 → 不再加；kill 本來就冪等。
- **`reload: true`**（Q6，proto7-1）：定義改取 tasks.json 裡同名的第一個非 `once` 項（完整驗證過再用，去掉 `mode`、`from_round`、`max_live`、`enabled`），掛載＝項目宣告加上沒被宣告接管的執行中加掛。找不到、讀不懂、不合格 → **整個 ctl 不執行（不 kill）**，`ok: false` 說原因。成功時回條 `result.diff` 列有變的欄（`argv`、`inst`、`mounts`、`subroot`、`allow_stop`）。
- restart 的 once 項跟同名的 keep 項搶同一個槽時：tick 先處理 once，keep 看到槽已活就不起。
- ctl.json 讀不懂或不是物件：不執行，照樣搬成 ctl-done.json，`ok: false`。

## 7. tock（S-08、S-11）

`aos7-tock <root> <node-id>`：

1. 抓 node fd、拿鎖、比世代。node 不在印 `{"gone": true}`；舊世代印 `{"stale": true}`；round.json 已是 `open: false` 印 `skipped`。
2. 執行任務控制（第 6 節）。
3. 掃所有槽（順便清槽裡寫者已死的暫存檔）：照 5.4 判定，lost 的補 exit.json；記下新結束的（同 run 的 exit.json 還沒有 `seen_round`）。一個槽壞掉、判不出、當活但 unsure 的都記進 `errors`，其他照做。
4. **寫 last-round.json**（覆寫），整份讀回確認；確認不了就失敗退出，不做後面，下次 tock 重來。
5. 之後才對每個活任務寫 `tock.json`（A2-12：任務收到這回合的 tock 時，last-round.json 一定已經是這回合的；寫不進去的記在 round.json 的 `notify_errors`）。
6. 替新結束的補 `seen_round`、刪掉該刪的槽（5.1）。
7. 寫 round.json（`open: false`），stdout 印總結。

**同回合已有總結**（上一次 tock 寫完 last-round.json 就被殺）：last-round.json 是**完整的**這回合總結（物件、`round` 是這回合、`tock_at` 是字串、`started`／`alive`／`ended` 是陣列）→ 不重寫，只把收尾做完（`ended` 裡的補 `seen_round`、`alive` 裡沒收到這回合 tock.json 的補寫、關 round.json 並標 `replayed: true`）；列不出槽就不關（退出碼 3）。不完整的（人手寫壞）照常重新產生。恢復只靠 round.json 與 last-round.json 這兩份「上一次」，不需要更前面的歷史。

## 8. 不變條件三：清掉的東西不改上層的累計（K-07）

核心會刪的只有兩種：換 run 時上一個 run 的基礎設施檔、名字不在表上的槽（5.1）。依賴它們的上層改成依賴自己的 state 檔：

- **agent 接前任**：state.json 在槽裡，下一個 run（同槽）直接讀，不用找前任的資料夾。槽被刪（名字從表上拿掉）就是不要了。
- **kernel 用量累計**（A2-09 改；kernel 還沒做，這是設計）：**用量以 run 為單位記**。任務的 `usage.json` 只記**這一次 run** 的用量（`{"run": <AOS7_RUN>, "usage": N}`，run 內只增不減；新 run 從 0 起，不必接前任）。kernel 在自己的 kernel-state 裡對每個 run id（`<slot>#<run>`）記「已見最大值」，**總用量＝所有見過的 run 的最大值相加**，只增不減。
  - 換 run、槽被刪又重建（同名槽的 run 一定比前任大，5.2）都只是多一個 run id，不靠「usage 變小」去猜重建，也不會把舊 run 的用量蓋掉。
  - 同名槽重建後的 run 取起它的回合數（5.2），回合只增，不會撞到被刪之前的 run id。
  - 代價（已接受）：kernel 是取樣的，run 在最後一次被看到之後又用掉、還沒被看到就結束並被清掉的那一段算不到——總數是「已觀測用量」的下界，不是精確值；要精確的 cap，任務在超用前自己停（合作式）。kernel-state 裡的 run 紀錄由 kernel 自己決定何時合併成一個「已退役總和」以免無限長。
- **tock 恢復**：只靠 round.json、last-round.json（第 7 節）。
- **kernel 接前任**：kernel-state.json 在自己的槽裡，同理。

## 9. 歷史 module（可選，非核心）

核心只留上一次。要更前面的歷史，用一個**普通的 keep 任務**當歷史 module：

- 每收到一次 tock，讀自己要記的「上一次」檔（自己 node 或經掛載的別的 node 的 `.aos/last-round.json`、daemon 的 `.aosd/status.json`），追加到它自己的地方（例如 `<node>/history/rounds.jsonl`），要不要輪替、留多少，都是它自己的設定（參考實作的 `--max-lines` 同時套在 node 歷史與事件歷史，A2-10）。收到自己 node 的 tock 時，那一回合的 last-round.json 已經提交（第 7 節第 5 步，A2-12）；別的 node 的照樣是取樣。
- 它是任務，合 S-10（tick 起、只碰給的資料夾），核心完全不知道它存在。
- **代價**：它是取樣的。它慢了、被 pause、或那條線一回合內就跑完兩回合，中間的就看不到；它看得出缺號（`round` 跳號）並記一行 `gap`，但補不回來。daemon 停機前最後一回合、它起來之前的回合也記不到（從第一次看到的回合開始記，不為之前的回合記 gap），所以「沒有 gap」不等於全歷史完整。這正是「核心不管更前面」的意思。
- **daemon 事件**（node 消失收程序、接管舊動作…）task 只能從 status 的 `last_event` 取樣，可能漏。需要完整事件流水帳的人，放一個空檔 `<root>/.aosd/log.on`：daemon 看到就把事件追加到 `.aosd/log.jsonl`；**不清、不輪替**，開的人自己管大小（例如讓歷史 module 定期截斷）。沒有這個檔＝不寫 log（W9）。

不選「核心提供每回合鉤子」：鉤子要在 tock 裡同步呼叫外部程式，失敗、逾時、它自己的歷史都會變成核心的邊緣狀況，跟「核心只留上一次」相反。

## 10. 小工具（S-01）

`aos7-ctl` 只是替你寫檔，LLM 直接寫檔一樣做得到：

- `aos7-ctl daemon <root> <op> [node] [--kill] [--rounds N] [--owner X] [--all]`：寫 `<root>/.aosd/ctl/<by>.<op>.<node>.json`，帶 `--owner` 時是 `<by>.<op>.<node>@<owner>.json`（固定名，回條只留最近一份；A2-13）。`<root>` 也可以是掛進來的 `.aosd`。
- `aos7-ctl task <槽> <kill|restart> [why] [--reload] [--run N]`：寫 ctl.json。
- `aos7-ctl add <node> '<項目 JSON>'...`：拿鎖把一或多項加進 tasks.json（一次 rename）。
- 都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印 `{"wrote": 路徑}`。

## 11. 已接受的界線

- **合作式檔案協定**：owner.json、stopped.json、paused.json、tasks.json 都是普通檔，分不出是誰改的。防的是失誤，不是惡意任務；帳號隔離、FUSE、cgroup 不在範圍內。身分掃描靠環境變數，不是身分驗證；environ 讀不到權限（別的 uid、不可 ptrace）的程序當成不是任務——任務自己變成那樣算故意脫離。
- **kill 只保證收到 Q1 的範圍**；搬移造成的鬼目錄照 K-06 接受。
- **慢就慢**（N-41）：每個動作一個程序，這台機器約每秒 100～150 回合，到了就一起遲到、不丟回合。要更多分到多個 daemon。
- **看得到的只有上一次**：漏掉的回合、被覆寫的回條與執行結果，核心不補。
- **之後再說**：keep 的 restart 政策（always／on-failure／never，N-79 的一部分）、pause 中做任務控制（N-82）、事件式喚醒（N-83）、成組全有全無（N-85）、out.log 單次 run 的大小上限（W10）。
