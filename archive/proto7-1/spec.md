# proto7-1 檔案格式與行為（細部 spec）

← [proto7-1](README.md)｜要合的是 [proto7 核心 spec](../proto7/spec/core.md)（條號 S-）

這份是 proto7-1 自己定的技術選型，全部取「最簡單」。每節標它落實哪幾條 S-。照做遇到的問題記在 [notes/problems.md](notes/problems.md)。

## 0. 共同約定（S-01）

- 所有狀態與控制都是 **JSON 檔**，能用 `cat` 看懂、用寫檔操作。寫檔一律「寫暫存檔再 rename」（原子），讀不到或壞掉當作不存在。**不是一般檔（FIFO、資料夾、裝置）也當不存在**：讀 JSON 一律非阻塞開、先看檔案型別，控制檔、tasks.json、spawn 被換成 FIFO 不會卡住 daemon 或 tick（probes/chaos B10、llmops）。暫存檔名以 `.` 開頭（`.<名字>.tmp.<pid>`），列資料夾的人略過 `.` 開頭的檔，就不會讀到寫一半的（probes/polyglot）。
- 多個寫的人要讀—改—寫同一個 JSON 檔（例如 tasks.json）時，約定對 `<檔>.lock` 拿 `flock`；`aos7_fs.edit_json(path, fn)` 就是這樣做。tick 只讀不拿鎖（probes/selfmod、lifecycle：不拿鎖會互相蓋掉）。
- 流水帳用 JSON Lines（`*.jsonl`，一行一個 JSON 物件）。讀的人跳過解析不了的行，後面的合法行照讀。`append_jsonl` 加行前先看檔尾：上次 append 中途被殺、留下沒換行結尾的半行，就先補一個換行再寫（半行原樣留著當證據），新的一行不會跟半行黏成一條壞行（astra-6 G-08）；任務的寫入紀錄 `writes.jsonl`（audit hook 直接寫，第 5 節）也一樣先補換行，看檔尾＋寫入期間對檔拿 `flock`（astra-7 H-03）。讀的一律**以 bytes 逐行**、每行各自 UTF-8 解碼＋`json.loads`：半個 UTF-8 字元（append 被殺在多 byte 字元中間）也只壞那一行，不會整檔丟例外或回空清單；`aos7_fs.read_jsonl(path, with_bad=True)` 回 `(紀錄, 壞行數)`，`aos7_audit.scan` 多 `bad_lines`（astra-7 H-04）。
- 時間欄位 `at` 是 ISO 8601 字串（本機時間，到毫秒）；只給人看，邏輯不依賴牆鐘。
- 每支程式是 `bin/` 下一個 Python 檔（薄入口），本體在 `lib/aos7_*.py`。純標準庫，Python 3.11+。

## 1. 空間與 node（S-07、S-13～S-15）

- `aos7-daemon <root>` 的 `<root>` 是空間根。`<root>/.aosd/` 是 daemon 自己的地方。
- **node**＝含 `.aos/timeline.json` 的資料夾。node id＝相對 root 的路徑，用 `/` 分隔；根本身是 `.`。
- 掃描：從 root 往下走，跳過以 `.` 開頭的資料夾；遇到**含 `.aosd/` 的子資料夾**（別的 daemon 的根）整棵不進去（S-15 最基本的重疊）。巢狀 node（`team` 與 `team/agents/amy`）各是各的時間線。
- **宣告了的子根也不收**（astra-5 F-08）：新出現的 node 若落在某個祖先 node 的 tasks.json 項目（或待起的 spawn 檔）宣告的合格 `subroot`（第 4 節）底下，父 daemon 不收——tick 建 `<subroot>/.aosd/` 之前的第一次掃描也一樣。只看「新出現」的 node；已經在跑的時間線照舊（之後 tick 建了 `.aosd/` 才照上一條離開）。
- **看不到不等於消失**（astra-5 F-03）：掃描時 `scandir`／`stat` 丟 `ENOENT`、`ENOTDIR` 才算「確定不存在」；其他 OSError（網路掛載的 `ESTALE`、`EIO`、`EACCES`…）是「無法觀測」：那個資料夾（與底下）既有的時間線、記著的 pgid 都留著、不 kill，log 記 `ev: "scan-error"`（`errors`＝{id: 錯誤}，同一組錯誤只記一次；恢復時記 `scan-ok`），status 的 `io_errors` +1，下一圈重掃。只有確定不存在才走下面的「node 消失」（Q4）。
- FUSE 不做。跨 node 用掛載（第 4 節 `mounts`，S-23）。

`<node>/.aos/timeline.json`（人或別的程式寫，daemon 只讀）：

```json
{"interval_ms": 100}
```

沒寫 `interval_ms` 當 1000。可選 `keep_ended_rounds`（非負整數，預設 20）：結束超過這麼多回合的任務資料夾，由 tock 搬到 `.aos/tasks-old/`（第 7 節）。可選 `keep_old_rounds`（非負整數；**不寫＝永久保留**，Q3 的預設不變）：tasks-old 裡結束超過這麼多回合的任務資料夾，由 tock 刪掉（astra-7 H-08）。

生一個新 node：**先寫 tasks.json（與其他檔），最後寫 timeline.json**。timeline.json 一出現 daemon 就開回合（1～2 ms 內撿到，不必寫 rescan）；順序反過來會有空回合（probes/subtimeline）。

## 2. daemon（S-03～S-06、S-18、S-21）

`aos7-daemon <root>`：常駐。主迴圈每 ~20 ms：讀控制檔 → 重掃 node（新的起迴圈、消失的收迴圈）→ 寫 status。

**每條時間線一個迴圈**（daemon 內用 thread 管迴圈；每個動作都是獨立程序，S-04）：

1. 若此 node 被 pause → 等，不開新回合。
2. 跑 `aos7-tick <root> <node-id>`（程序，很快結束），從它 stdout 讀回本回合起了哪些任務。
3. 等到「本回合 tick 起的任務都結束」或「離 tick 已過 interval」，二者先到（S-09：tock 可能提前進場）。
4. 跑 `aos7-tock <root> <node-id>`（程序）。
5. 等到離本回合 tick 滿 interval，回 1。

`interval_ms` 不是有限數字（字串、null、NaN、過大——包括 `10**309` 這種大整數、**負數**）時用預設 1000（0 合法，等於不等；probes/chaos B9），並在 status 的 `last_error` 記 `prog: "timeline"`；修好檔下一回合就用新的。時間線迴圈丟任何例外，記 `last_error` 與 log 的 `ev: "error"`，等 0.5 秒接著跑，不會永久停掉（astra-4 I-06）。

**動作逾時**（eval/2026-10-03-batch-tick 順帶發現）：tick、tock 一次最多跑 `action_timeout_s` 秒（timeline.json 可設，預設 30）。超過就 SIGKILL 這個動作、記 `last_error` 與 log 的 `incomplete: true`，該回合照常往下走。tick 被收掉的回合，tock 收到環境變數 `AOS7_INCOMPLETE=tick`，總結多 `incomplete: "tick"`。daemon 停機時，正在跑的 tick／tock 最多再等 3 秒就收掉，一條線卡在 I/O 不會讓整個 daemon 停不下來。

**舊動作接管**（astra-5 F-04）：tick、tock 拿到 `action.lock` 後把自己寫進 `<node>/.aos/action.owner.json`＝`{"pid", "gen", "starttime"（/proc/<pid>/stat 第 22 欄）, "at"}`。daemon 的動作等鎖逾時（被收掉）時讀它：`gen` 比自己小、而且那個 pid 現在的 starttime 跟記的一樣（確定是同一個程序，不是重用的 pid）→ SIGKILL 它（鎖跟著放掉），log 記 `ev: "stale-holder-kill"`，下一個動作就拿得到鎖。daemon 被 kill -9 時留下、還拿著鎖的舊 tick／tock 因此最多拖一個 `action_timeout_s`。**不 unlink 鎖檔**（新舊程序會鎖到不同 inode）。

**有界接管只限 owner 身分可驗證**（astra-6 G-10）：鎖真的有人拿著，但 action.owner.json 讀不到、缺 `pid`／`gen`／`starttime`、`gen` 不比自己舊、`/proc/<pid>/stat` 讀不到或 starttime 對不上（pid 可能被重用）時，**照樣不殺**（不猜 PID 強殺）；該 node 的 `last_error` 記 `{"prog": "action-lock", "err": "stale-holder-unverified：原因。人工恢復提示"}`，log 記 `ev: "stale-holder-unverified"`（`pid`、`why`、`hint`；同一個原因只記一次）。人工恢復：確認是誰拿著 `<node>/.aos/action.lock`（`fuser`／`lsof`），確定是舊的 tick／tock 就 kill 它，或補正 action.owner.json，下一次逾時就自動回收。鎖其實沒人拿（逾時的是自己的動作、已被收掉）不記。

**tock 被逾時收掉**（astra-5 F-05）：round.json 還開著，daemon 馬上補一次 tock（`AOS7_INCOMPLETE=tock`、log 的 tock 行帶 `replay: true`）。被殺的 tock 若已經寫了總結，補的這次照第 7 節「同回合已有總結」只收尾、不寫第二行；沒寫過就寫一行帶 `incomplete: "tock"` 的總結。補的也逾時、或停機已超時，就留給下一次「沒關的回合」。

**沒關的回合**：時間線起來後第一次開回合前，round.json 若還是 `open: true`（node 在回合中消失又出現、daemon 回合中死掉重開），先 tock 一次把它關掉，總結標 `incomplete: "unclosed"`，rounds.jsonl 不缺號（probes/chaos B8）。

**tock 沒把回合關上**（astra-7 H-01）：每次 tock 完都看 round.json，還是 `open: true`（不只逾時：非零退出、第 7 節讀回確認失敗、印出不確定的結果都算）就馬上補一次 tock（同上面的逾時補 tock；同回合已有總結就只收尾、不寫第二行）。補的也沒關上 → log `ev: "round-unclosed"`、`phase: "error"`、`last_error` 寫「第 N 回合沒關上…」，**下一次 tick 之前先走上面「沒關的回合」恢復**；恢復成功前不開新回合（round 不往前跳、不越過沒提交的總結），失敗就保持 error、退避重試（0.5 秒起加倍，最多 8 秒）。resume 帶 `rounds` 的倒數也要等回合真的關上才算一回合。停機中不做這段（回合留著 open，下次起來照「沒關的回合」收）。round.json 壞掉（不是物件、round 不是整數）時，時間線當 0 起、不讓 daemon 退出（chaos B1）；tick（以及 tick 之後才被寫壞時的 tock）從 rounds.jsonl 最後幾行裡最大的整數 round 接著數，並記 `tasks_error`（chaos B6）。

daemon 跑 tock 時給環境變數 `AOS7_EARLY`（`1`＝本回合起的任務都結束、提前進場；`0`＝等滿 interval）。tick 印 `gone`（node 已不在）時這圈不開回合，等掃描收掉這條。

**世代**（astra-4 I-01）：daemon 拿到 `daemon.lock` 後把 `.aosd/gen.json` 的 `gen` +1，起 tick／tock 時給環境變數 `AOS7_GEN`。tick、tock 整個動作期間對 `<node>/.aos/action.lock` 拿 `flock`，拿到後比對 `AOS7_GEN` 與 gen.json；不同（舊 daemon 留下的動作）就什麼都不寫、印 `{"stale": true}`。沒有 `AOS7_GEN`（人手跑）不比對。

pause 在回合中途下：本回合照常 tock 完才停。pause 的 node 清單存在 `<root>/.aosd/paused.json`（`{"paused": [...]}`），daemon 重開照樣有效；daemon 一起來就寫一份（空清單也寫，讀的人不會碰到「不存在」；probes/llmkernel）。

**node 消失**（資料夾不見、或 `.aos/timeline.json` 不見；搬家改名＝舊 id 消失、新 id 出現）：daemon kill 那個 node 上的活任務（使用者 10-03 Q4 選 (a)）。因為 rm -rf 後 pid.json 跟著沒了，daemon 平常記著各 node 活任務的 pgid（記憶體裡，跟 status 的 live 一起每 0.25 秒更新），再加上找環境變數 `AOS7_NODE` 是那個 node 的程序（aos7-run 不殺，讓它照常寫 exit.json；搬家時經 fd 寫到新位置）。在背景做、不擋主迴圈；log 記 `ev: "node-gone-kill"`。記憶體裡的 pgid 是**週期採樣**：剛起不到 0.25 秒、又清掉環境變數的任務可能漏收（Q1 的責任邊界）。「消失」要是確定不存在，看不到（I/O 錯）不算（第 1 節，astra-5 F-03）。新位置由 keep 重起。想「暫停但保留任務」用 pause，不要拿掉 timeline.json。

stop：回合中途的時間線不等 interval，（`kill` 時先 kill 本 node 所有活任務）立刻 tock 收回合再結束；daemon 等所有時間線結束才退出。

stop 帶 `kill`（含 SIGTERM／SIGINT）時，所有時間線結束後再**掃一次 `/proc/*/environ`**：`AOS7_NODE` 是本 daemon 任一 node、又有 `AOS7_TID` 的程序（主程序已結束的任務留下的子孫、tasks-old 裡任務的也算），連同它們的群組與活後代收掉（第 6 節 Q1 的範圍；不含 aos7-run、不含 daemon 自己與祖先）。一次掃描、不逐任務掃；log 記 `ev: "stop-sweep"`（`groups`＝收到幾個群組、`ok`）。故意清掉環境又脫離群組的照 Q1 由任務自負（astra-5 F-01）。

同一個 root 只能有一個 daemon：`<root>/.aosd/daemon.lock` 用 `flock` 鎖，鎖不到就 stderr 說明、退出碼 1。

**`.aosd` 綁 root 的 fd**（astra-6 G-03）：daemon 一起來就抓住 root 資料夾的 fd，自己的 `.aosd/`（status、log、paused、gen、ctl、ctl-done…）一律經 `/proc/self/fd/N/.aosd` 讀寫：root 被搬走就寫到新位置，被刪掉就寫不進去（記 io-error），**不會照舊路徑 makedirs 建回來**。主迴圈每圈先比 root 的字串路徑與抓著的 fd：確定不存在（ENOENT／ENOTDIR）或 inode 不同（搬走、換成符號連結）＝root 消失 → 照 stop 帶 kill 收尾（Q4：搬家＝舊任務全死；子 daemon 由父的 keep 在新位置重起），log 記 `ev: "root-gone"`、status 多 `root_gone: true`。ESTALE、EIO 這類看不到的不算。

**控制檔**（S-18、S-21 路二）：任何人寫 `<root>/.aosd/ctl/<任意名>.json`：

```json
{"op": "pause", "node": "team/agents/bob", "by": "team:kernel-r1"}
```

| op | 意思 |
|---|---|
| `pause` | 該 node 不再開新回合（跑著的任務不動、收不到 tock） |
| `resume` | 恢復 |
| `stop` | 整個 daemon 結束；`"kill": true` 時先 kill 所有活著的任務。帶 `node` 回 `ok: false`（多半是想停一個 node，該用 pause；probes/llmteam）。子 daemon 要擁有者允許（下面「子 daemon 的所有權」） |
| `rescan` | 立刻重掃 node |
| `wake` | 該 node 正在等下一回合（idle）就不等滿 interval，馬上開下一回合；回合中的照舊等任務或 interval。改了 interval 想馬上生效也用它（probes/event N1、astra-4 I-08） |

`resume` 可帶 `"rounds": N`：只再跑 N 回合，第 N 次 tock 完自動 pause（status 帶 `steps_left`；log `ev: "steps-done"`；probes/sched N2）。之後的 pause／resume 會清掉倒數。

**每圈有預算**（astra-5 F-10）：一圈最多處理 `CTL_BATCH`＝200 個控制檔或花 `CTL_BUDGET_S`＝0.05 秒（先到為準；`lib/aos7_daemon.py` 頂端），剩下的下一圈接著做（照檔名順序，pause／resume 的先後不變），中間照常掃描、寫 status；還有剩的時候這圈不睡。一萬個 wake 也不會讓 status 停更。

`pause`／`resume`／`wake` 的 node 落在含 `.aosd/` 的子資料夾（別的 daemon 的根）底下時回 `ok: false`，msg 說它屬於哪個 daemon（probes/multid N4）。node 目前不存在照樣接受（可以預先 pause），msg 加註「目前沒有這個 node，出現時才生效」。同一批控制檔依檔名排序執行。

**逐件錯誤邊界**（astra-6 G-01）：一件控制檔處理丟例外（最常見：回條 `ctl-done/<名>.json` 是資料夾、寫不進去），不擋同圈其他件（特別是 stop）：那件原物搬到 `.aosd/ctl-failed/<名>`（撞名換 `<名>.<time_ns>`、再撞加 `.1`、`.2`…；一般檔用 `os.link` 排他建立再刪原檔，**保證不覆蓋**舊的隔離檔，astra-7 H-07；`ctl-done/<名>.bad` 同樣），log 記 `ev: "ctl-error"`（`file`、`err`、`moved_to`），status 的 `io_errors` +1、`last_ctl_error`＝`{"file", "at", "err", "moved_to"}`。那件的效果可能已經生效（回條才失敗；err 會寫「已執行（ok=…）」），所以**不重做**；要重送就把檔搬回 `ctl/`。連 `ctl-failed/` 都搬不進去時留在 `ctl/`，之後每圈排到最後（不會每圈卡在同一件、讓後面的餓死）。

`ctl/` 底下不以 `.` 開頭的每個名字都會處理：不是 `.json` 結尾、或不是一般檔（FIFO、資料夾）的，原物搬到 `ctl-done/<名>.bad`、另寫 `ctl-done/<名>.json`（不是 .json 結尾的補上）回條 `ok: false`（以前默默略過、FIFO 卡死主迴圈、資料夾每圈重處理；probes/llmkernel、chaos B5、B10）。寫給停著的 daemon 的控制檔留在 `ctl/`，下次起來才執行。

daemon 讀到後執行，把檔案搬到 `<root>/.aosd/ctl-done/<同名>.json`，內容加上 `"result": {"ok": true, "msg": "...", "at": "...", "queued_at": 控制檔的 mtime}`。回條的 ok 只表示 daemon 接受並改了狀態；pause 真的停住要看 status 的 `phase`／`pause_pending`。讀不懂的也搬過去，`ok: false`。

daemon 收到 SIGTERM／SIGINT＝`stop` 加 `kill: true`（路一：子 daemon 被父時間線 kill 時，帶走自己的任務）。

**子 daemon 的所有權**（使用者 10-03 答 Q5：「子daemon歸屬於哪個node，那他的所有權就歸屬於那個node，如果那個node允許，那stop就有用。」）：

- `<subroot>/.aosd/owner.json`＝`{"node": 擁有者 node id, "tid", "allow_stop": bool, "at", "daemon_pid"}`（`allow_stop` 取任務項目的，預設 false；第 4 節）。**由子 daemon 自己在拿到 `daemon.lock` 之後寫**（astra-7 H-02）：tick 起帶 `subroot` 的任務時不寫 owner.json，只給任務三個環境變數 `AOS7_OWNER_NODE`、`AOS7_OWNER_TID`、`AOS7_ALLOW_STOP`（`1`／`0`）；aos7-daemon 拿到鎖後，若自己的 root 就是 `AOS7_SUBROOT`（同一個資料夾），照這三個寫 owner.json，然後把它們從自己的環境拿掉（不傳給自己的 tick／tock／任務）。拿不到鎖的敗者在開頭就退出、什麼都不寫，所以 owner 一定指著真正在跑的那個。擁有者想即時改權限，直接改這個檔（它在擁有者自己的 node 底下）；任務重起（keep、restart）後新的子 daemon 起來時照項目重寫。
- 控制檔 `stop`：daemon 讀自己根的 `.aosd/owner.json`。有這個檔、而 `allow_stop` 不是 `true`（檔壞掉也算）→ 不停，回條 `ok: false`，msg 說它屬於哪個 node（任務 tid）、要停請那個 node 設 `allow_stop` 或 kill 這個任務。`allow_stop: true` → 照常 stop，並先寫 `<根>/.aosd/stopped.json`＝`{"by", "why", "at", "kill"}`（取控制檔的 `by`、`why`、`kill`）。沒有 owner.json（頂層 daemon）照舊，不寫 stopped.json。只管 `stop`；pause／resume／wake／rescan 不看所有權。
- SIGTERM／SIGINT（路一：擁有者 kill 任務）照舊，不看 allow_stop、不寫 stopped.json。
- **認領要跟 daemon.lock 一致**（astra-6 G-04、astra-7 H-02）：tick 起帶 `subroot` 的任務之前，先對 `<subroot>/.aosd/daemon.lock` 試非阻塞 flock：拿得到就馬上放掉、照常起；拿不到＝已經有 daemon 在跑 → **不起（不佔 tid）**，記 `tasks_error`（「子根已經有 daemon 在跑（owner：node … 任務 …），沒起、沒改 owner.json」），spawn 檔照刪；keep 下一回合再試。同一個 tick 裡第二項（spawn 或 tasks.json）宣告同一個子根也不起，記 `tasks_error`（「這個 tick 已經有別的任務認領」）。兩個 tick（不同 node）在子 daemon 拿到鎖之前同時起任務時，兩個子 daemon 搶 daemon.lock，敗者退出（任務 exit 1）、不寫 owner.json——owner 只由贏家寫，不會再指錯（以前 tick 先寫 owner，12 次有 9 次指錯）。
- 擁有者 node 的 tick 起帶 `subroot` 的任務（tasks.json 的 keep／each、spawn、restart 寫的 spawn 全部）時，`<subroot>/.aosd/stopped.json` 在 → 不起（不佔 tid），記 `tasks_error`（「子 daemon 已被誰在何時 stop；刪掉 stopped.json 就會再起」），spawn 檔照刪。刪掉 stopped.json，下一回合 keep 照常起。
- daemon 起來時 stopped.json 還在（tick 會擋，所以多半是人手跑 aos7-daemon）：算人決定的，刪掉標記、log 記 `ev: "stopped-cleared"`（`was`＝原內容）。
- **這是合作式檔案協定**（astra-6 G-09，技術選型）：owner.json、stopped.json 都是普通檔，只照檔案的值判斷，**分不出是誰改的**——擁有者、子 daemon 底下的任務、人都改得動。任務把 `allow_stop` 改成 true，外部 stop 就成功；任務刪掉 stopped.json，父的 keep 就重起；刪掉 owner.json，子 daemon 就當自己是頂層（stop 成功、不留 stopped.json）。「人手跑 aos7-daemon 清標記」也無法確認真的是人。要防的是**失誤**，不是惡意任務；帳號隔離、FUSE、cgroup 不在範圍內。同樣地，stop-sweep 與 node 消失的收程序以環境變數 **`AOS7_NODE`＋`AOS7_TID`** 認程序、**不比 `AOS7_ROOT`**（Q1 的範圍）：不同 NODE、沒有 TID 的不收；相同 NODE＋TID 但 ROOT 不同的照收。這不是 daemon 身分驗證。

**狀態** `<root>/.aosd/status.json`（daemon 寫，每圈覆寫）：

```json
{"pid": 123, "root": "/abs/root", "at": "...", "poll_s": 0.02, "gen": 3, "io_errors": 0,
 "stopping": false, "stopped": false,
 "nodes": {"team": {"round": 7, "phase": "running", "paused": false, "pause_pending": false,
                    "interval_ms": 100, "live": ["kernel-r1"]}}}
```

`phase`：`idle`（等下回合）／`tick`／`running`（回合中）／`tock`／`paused`／`error`（迴圈出例外、等著接著跑）／`stopped`。`pause_pending`＝已要求 pause、但這回合還沒收完。`interval_ms`＝最近一回合實際用的。`live` 每 0.25 秒才重算一次（任務資料夾多時每圈全掃太貴；probes/fleet、swarm）。`disk`＝容量粗估（每 30 秒算一次，`DISK_EVERY`；astra-7 H-08）：`{"at", "every_s", "aosd_bytes": .aosd 底下檔案 bytes 合計, "nodes": {id: {"tasks": 數, "tasks_old": 數}}}`。`stopped: true`＝daemon 正常退出前寫的最後一份；`at` 超過幾個 `poll_s` 沒動，daemon 可能卡住或死了（probes/multid N5）。另有 `kill_on_stop`。`round` 以 tick 印的結果為準，tick 沒印（失敗）時讀 round.json。tick／tock 退出碼非 0 時，該 node 多一欄 `last_error`：`{"prog", "rc", "round", "at", "err"}`（stderr 末段），留著直到下次出錯覆寫（認不出持鎖者時 `prog` 是 `"action-lock"`，見上面 G-10）。控制檔處理失敗過時多 `last_ctl_error`；root 消失時多 `root_gone: true`。

**流水帳** `<root>/.aosd/log.jsonl`：daemon 每個 tick、tock、ctl、node 出現消失寫一行（`node+` 時若在 paused 清單裡多 `paused: true`）。

**保留政策（可選；astra-7 H-08）**：預設什麼都不刪（Q3 只搬不刪）。人寫 `<root>/.aosd/retention.json`＝`{"ctl_done_max": N, "ctl_failed_max": N, "log_max_bytes": N}`（每項可省；值不是非負整數的那項不管）：daemon 每 30 秒（跟 `disk` 一起）把 `ctl-done/`、`ctl-failed/` 超過 N 件的刪最舊的（依 mtime），`log.jsonl` 超過 N bytes 就換名成 `log.1.jsonl`（覆蓋上一份，只留一份舊的）、之後寫新的 `log.jsonl`。node 的任務歷史用 timeline.json 的 `keep_old_rounds`（第 1 節）。

主迴圈（讀控制檔、掃描、寫 status）任一步丟例外不退出：印 stderr、寫得進去就記 log（OSError 記 `ev: "io-error"`，其他例外記 `ev: "error"`）、status 的 `io_errors` +1，下一圈再試（astra-4 I-07；chaos B1：一個 node 的壞檔以前會讓整個 daemon 退出）。掃描一圈最多起 20 條新時間線，其餘下一圈（啟動時 node 很多，控制檔與 status 不會停擺；probes/fleet N2、astra-4 I-11）。

daemon 給 tick／tock 的環境：`PATH` 前面加上 proto7-1 的 `bin/`。

## 3. 回合（S-08、S-11）

`<node>/.aos/round.json`（tick、tock 寫）：

```json
{"round": 3, "open": true, "tick_at": "...", "tock_at": null}
```

tick 把 round +1、`open: true`，並記下本回合的 `started`、`ctl`、`mounts`（加掛審核結果 `[{"tid","name","path","ok","msg"}]`；給 tock 寫總結用）；tock 設 `open: false` 與 `tock_at`。第一次 tick 的回合是 1。daemon 重開後接著數（讀這個檔）。

`<node>/.aos/rounds.jsonl`（tock 寫，一回合加一行總結；`tail -1` 是最近一回合，`grep '"round": 3,'` 找第 3 回合）：

```json
{"round": 3, "tick_at": "...", "tock_at": "...",
 "started": ["agent-r1"], "alive": ["kernel-r1"],
 "ended": [{"tid": "stuck-r2", "code": -15}], "ctl": [{"tid": "x", "op": "kill", "ok": true}], "mounts": []}
```

`ended`＝上次 tock 之後才看到結束的任務；`ctl`＝本回合 tick 與 tock 執行的任務控制。

原本一回合一個 `rounds/<N>.json`；長跑時小檔佔掉的磁碟是內容的 9 倍（astra-3 長跑、R-10），改成同一個檔一行一回合（P-12）。

## 4. 任務表與 tick（S-09、S-10、S-12）

`<node>/.aos/tasks.json`（人或 kernel 寫）：

```json
{"tasks": [
  {"name": "kernel", "mode": "keep", "argv": ["aos7-kernel"]},
  {"name": "job", "mode": "each", "argv": ["python3", "job.py"], "from_round": 3},
  {"name": "x", "mode": "keep", "inst": "x.inst.json", "mounts": {"bob": "team/agents/bob/inbox"}}
]}
```

- `argv`：直接跑；相對路徑以 node 為 cwd。argv 裡的 `$AOS7_TASK`、`${AOS7_NODE}` 這類 `AOS7_*` 變數由 aos7-run 展開（其他 `$` 原樣），用來指到掛載點。`inst`：一份 inst JSON（相對 node 的路徑），用搬來的 `aos-exec` 跑（S-12）。二選一。
- `mode`：`each`＝每回合起一個；`keep`＝本 node 沒有同名活任務才起（常駐用）。預設 `each`。
- `from_round`：從第幾回合起才生效（預設 1）。
- `name`：沒寫當 `"task"`（birth.json 與 keep 判斷都用它）。
- `max_live`（可選）：同名活任務已有這麼多個，本回合不起（`keep`＝`each` 加 `max_live: 1`；probes/longrun N-3）。
- `subroot`（可選，空間路徑）：這個任務要在那裡開子 daemon（路一）。**要在任務自己的 node 底下、不能是 node 本身**（S-10；不合的不建、birth.json 記 `subroot_error`；probes/llmteam 寫成 `"sub"` 就在空間根建了 `.aosd`）。tick 起它之前先建 `<subroot>/.aosd/`，父 daemon 掃描就跳過那棵，不會在子 daemon 起來前把裡面的 node 當自己的（P-11；probes/nest3 N3）。任務多一個環境變數 `AOS7_SUBROOT`＝子根的絕對路徑，argv 寫 `["aos7-daemon", "$AOS7_SUBROOT"]`（cwd 是 node，寫空間路徑會跑錯地方；llmteam 兩個模型都犯）。寫入紀錄把子根整棵算這個任務的（子 daemon 與它的 tick／tock 繼承這個任務的環境）。另給 `AOS7_OWNER_NODE`／`AOS7_OWNER_TID`／`AOS7_ALLOW_STOP`，子 daemon 拿到鎖後用來寫 owner.json（第 2 節；astra-7 H-02）。tick 建 `.aosd/` 之前，父 daemon 的掃描也已經照第 1 節跳過宣告了的子根，子 node 先建好也不會被父撿走（astra-5 F-08）。restart 會帶上。owner.json 由子 daemon 拿到鎖後寫（不是 tick）；子根有 `.aosd/stopped.json`、`.aosd/daemon.lock` 已經有人拿著（已有 daemon 在跑；astra-6 G-04）、或同一個 tick 已有別項認領這個子根（astra-7 H-02）時不起（第 2 節「子 daemon 的所有權」）。
- `allow_stop`（可選，bool，預設 false；只對帶 `subroot` 的有意義）：允許別人用路二的控制檔 `stop` 這個子 daemon（Q5，第 2 節）。restart 會帶上。
- 某一項欄位型別不對（**在算 tid、起任務之前就整項驗完**；`name` 不是非空字串、`argv` 不是非空字串陣列、沒 argv 時 `inst` 不是字串、`mounts` 不是物件、`subroot` 不是字串、`allow_stop` 不是 bool、`from_round` 不是整數、`mode` 不認得）：**只跳過那一項**（tasks.json 與 spawn 同一套檢查；probes/chaos B2～B4），其他照起；tasks.json 整份讀不懂當空表。兩種都記在 round.json 與回合總結的 `tasks_error`（probes/selfmod）。
- 起任務本身失敗（建掛載點、寫 birth.json 丟例外…）也只記那一項的 `tasks_error`，其他項照起；連 aos7-run 都起不來時任務資料夾照樣寫 `exit.json` `{"code": 127, "error"}`。spawn 的 `batch` 裡不是物件、或欄位壞掉的項目只跳過那項（記 `tasks_error`），其他照起、檔照刪（astra-5 F-06）。
- `mounts`：**掛載**（S-23）。`{"名字": "空間裡的路徑"}`，路徑相對空間根、跟 node id 同一套（根的 daemon 資料夾是 `.aosd`）。tick 起任務時在任務資料夾建 `mnt/<名字>`，是指向目標的相對符號連結；目標不存在先建成資料夾。名字不能含 `/`、不能以 `.` 開頭；路徑不能是絕對、不能跑出空間根（沿符號連結走到的實際位置也算，realpath 後要在空間根內），不合的不掛、在 birth.json 記 `error`。任務要碰別的 node 或 daemon 的資料夾，一律經過掛載點（第 5 節「只碰給的資料夾」）。**不強制**（沒有 FUSE），靠寫入紀錄檢查。

- `mount_allow`（tasks.json 頂層，可選）：執行中加掛請求的允許清單，空間路徑前綴（`["team/agents/", ".aosd"]`；`"."`＝全部）。比對時請求路徑與每一項都接空間根再 realpath，比**實際位置**（problems.md M-13）；跑出空間根的一律不給。沒寫＝全給（仍要在空間根內）。只管執行中的請求，不管 `mounts` 宣告。

**執行中加掛**（S-23，M-6 使用者選 (b)）：任務寫 `$AOS7_TASK/mount-req/<名字>.json`＝`{"name", "path"（空間路徑）, "why"}`（`name` 可省，由路徑推：路徑只有英數、`-`、`/` 時把 `/` 換成 `_`，例如 `team/agents/bob/inbox` → `team_agents_bob_inbox`；其他（含 `_`、`.`）再接 `-` 與路徑 sha1 前 8 碼，所以不同路徑一定推出不同名字）。下一個 tick 審核：路徑不合、不在 `mount_allow`、名字已掛了別的 → 拒絕；否則建 `mnt/<名字>`、加進 birth.json 的 `mounts`。`name`／`path` 不是字串、請求不是物件、或處理時出任何例外，都寫失敗回條，不影響同一輪其他請求與 tick 的其他工作。回條寫 `$AOS7_TASK/mount-done/<同名>.json`＝請求內容加 `{"result": {"ok", "msg", "at"}}`，**回條寫成功才刪請求**（astra-5 F-07）：回條寫不進去（例如那個名字被佔成資料夾）時請求留著、這筆在 round.json 的 `mounts` 記 `receipt_error`，同一輪其他請求照做；下次重處理是冪等的（已掛同名同目標＝「已經掛了」，直接補回條）。一個任務的加掛處理整個丟例外，也只在它那筆記失敗。被拒的回條留著，`aos7_mount.request` 看到就不再重請（要重請就刪回條）。restart 把加掛的一起帶到新任務。卸掛不做。

`<node>/.aos/spawn/<任意名>.json`：別人請求「下個 tick 起一個任務」，格式同 tasks.json 的一項（多一個可選 `restart_of`，restart 寫的還可能有 `mounts_dyn`＝執行中加掛的名字清單，新任務照樣標 `dyn`；`from_round` 不看），或 `{"batch": [項目, ...]}`（一個檔一次 rename，整批同一回合起；probes/swarm N3）。spawn 一樣看 `mode`／`max_live`：`keep` 而同名已有活的就不起、記 `tasks_error`、檔照刪（probes/llmops：改好 tasks.json 又補 spawn，keep 變兩份）；restart 寫的 spawn 沒有 mode（＝each），不受影響。壞的一項（或整檔讀不懂、不是一般檔）記 `tasks_error`、檔照刪，不會變成每回合的毒丸（chaos B3）。tick **起完才刪**（中途被殺，下次會再起一次，不會無痕丟掉；astra-4 I-02），birth.json 記 `spawn`＝檔名。restart 靠它。

測試鉤子：環境變數 `AOS7_TEST_TICK_HANG=<node id>` 時，那個 node 的 tick 寫完 round.json 後就睡著（只給 tests 模擬「tick 卡在 I/O」；以前用 FIFO 的 tasks.json，現在不會卡了）。

`aos7-tick <root> <node-id>`，依序：

1. round +1，寫 `round.json`。
2. 執行任務控制（第 6 節），再審核活任務的加掛請求（上面）。
3. 起任務：先 `spawn/*.json`（檔名排序），再 tasks.json 各項（`keep` 的檢查會算進剛起的）。
4. stdout 印一行 JSON `{"round": N, "started": [tid...]}`，結束。**不等任務。**

`.aos/timeline.json` 不在（node 被刪、搬走）時什麼都不寫、印 `{"gone": true}`，免得把資料夾建回來（probes/subtimeline、rename）。

**抓著 node 目錄做整個動作**（astra-5 F-09）：tick、tock 一開始 `os.open(node, O_RDONLY|O_DIRECTORY)`，之後 `.aos/` 底下的讀寫（action.lock、round.json、rounds.jsonl、任務資料夾、spawn…）都經過 `/proc/self/fd/N/…` 做。動作中途 node 被搬走：寫到新位置；被刪掉：寫入失敗（被刪的資料夾不能再建東西），收手印 `{"gone": true}`，**不會**在舊路徑建出鬼目錄。任務的環境變數、掛載點記錄（birth.json 的 `at`）仍用實際路徑。

**起任務也跟抓著的 node 一致**（astra-6 G-02）：起每個任務、建掛載前，比 node 的字串路徑與抓著的 fd（`samestat`）：已經不是同一個資料夾（中途被搬走、換成指到別處的符號連結）→ **受控失敗**：不建掛載、不起 aos7-run，任務資料夾（經 fd，在新位置）寫 birth.json（帶 `error`）與 `exit.json` `{"code": 127, "error": "node … 在 tick 中途被搬走或換掉…"}`，任務是 ended、不會永遠 born；新位置由 keep 重起（Q4）。還是同一個時：掛載目標落在 node 底下的經 fd 建（之後才搬走也不建回舊 node）；aos7-run 的 cwd 是抓著的 node，第二個參數是任務資料夾的 fd（第 5 節），讀 birth、寫 pid／exit 都經它，不靠舊的字串路徑。**最後交接**（astra-7 H-05）：Popen aos7-run 之前 tick 再比一次 node；aos7-run 起任務之前也比：給任務的 `AOS7_TASK`、`AOS7_NODE`（也是 argv 展開、birth.json 掛載點 `at` 用的同一個字串路徑）現在要跟它抓著的任務資料夾 fd、cwd 是同一個資料夾，不是就**不起任務**、經 fd 寫 `exit.json` `{"code": 127, "error": "AOS7_… 已經不是 runner 抓著的資料夾…"}`（寫到新位置），新位置由 keep 重起。任務起來之後才搬家的（長命任務整個生命期）不追隨，照 Q4 由 daemon 收。tick、tock 收到 SIGTERM 不中斷（把這個動作做完；被一起 kill 的子 daemon 群組裡的 tick／tock 不會寫一半；probes/nest3 N1），SIGKILL 保底。

## 5. 任務（S-10、S-11、S-16）

tid＝`<name>-r<回合>`，同回合撞名加 `-2`、`-3`（name 裡不是英數、`_.-` 的字元換成 `_`，所以 tid 不能拿來反推名字，要看 birth.json）。任務資料夾 `<node>/.aos/tasks/<tid>/`：

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `birth.json` | tick | `{"tid","name","node","round","argv"或"inst","mounts","at","restart_of"}`（有的話加 `subroot`／`subroot_error`、`allow_stop`、`spawn`）；`mounts`＝`{名字: {"to": 空間路徑, "at": 掛載點絕對路徑}}`（壞的宣告是 `{"error"}`；執行中加掛的多 `"dyn": true`） |
| `mnt/<名字>` | tick | 掛載點（符號連結） |
| `writes.jsonl` | 任務（audit hook） | 開了寫入紀錄才有，見下 |
| `mount-req/<名字>.json` | 任務 | 執行中加掛的請求（第 4 節） |
| `mount-done/<名字>.json` | tick | 加掛回條 |
| `runner.json` | tick | `{"pid","starttime","at"}`：起的 aos7-run 是誰（Popen 之後寫；astra-7 H-06） |
| `pid.json` | aos7-run | `{"pid","pgid","runner_pid","at"}` |
| `out.log` | 任務 | stdout＋stderr |
| `exit.json` | aos7-run | `{"code","at","round"}`；code 負數＝被訊號殺（-15）；`round` 是結束時 node 的回合數。aos7-run 一開始就抓住任務資料夾的 fd，out.log、pid.json、exit.json 都經過它寫：node 搬家就寫到新位置，被刪就不寫回舊路徑（probes/rename N8；第二波：pid.json 以前用 makedirs 寫，任務資料夾剛被刪時會建回來、測試留下 /tmp 殘留）。一開始資料夾就不在，aos7-run 什麼都不做就退出 |
| `tock.json` | tock | `{"round": N, "at", "early"}`：第 N 回合剛結束（覆寫，只留最新；漏掉的回合看 node 的 `rounds.jsonl`） |
| `ctl.json` | 任何人 | `{"op": "kill"或"restart", "by", "why"}`；restart 可加 `"reload": true`（第 6 節） |
| `ctl-done.json` | tick／tock | ctl.json 搬過來加 `result` |
| `ended.json` | tock | `{"round": N}`：tock 在第 N 回合記下它結束 |

tick 用 `aos7-run <taskdir> <fd>` 起任務（新 session，tick 不等它）：`<fd>` 是 tick 開好、傳下去的任務資料夾 fd，cwd 是 tick 抓著的 node（astra-6 G-02）；aos7-run 經這個 fd 讀 birth.json、寫 out.log／pid.json／exit.json，不再照 `<taskdir>` 字串重開（人手跑時不給 fd，照 `<taskdir>` 開）。**讀不到 birth.json 也經 fd 寫 `exit.json` `{"code": 127, "error": "讀不到 birth.json"}`**，不留永遠 born 的任務。aos7-run 讀 birth.json，把真正的任務起在**自己的程序群組**，寫 pid.json，等它結束，寫 exit.json。起不來（找不到程式、argv 有非字串或 NUL 等）直接寫 exit.json `{"code": 127, "error": "..."}`（以前 argv 有數字時 aos7-run 當場例外，任務永遠算「剛起」；chaos B4）。**起程序前的任何 I/O 失敗**（例如 `out.log` 是資料夾、開不了）也一樣：stderr 說明、經 fd 寫 exit.json `{"code": 127, "error"}`；連 exit.json 都寫不進去時 stderr 再說一次，由 tock 照 `runner.json` 判 lost（astra-7 H-06）。

**`<fd>` 是內部交接的能力，不是身分約束**（astra-7 H-09，技術選型）：第二參數必須是呼叫者開好、繼承下來的任務資料夾 fd，cwd 也由呼叫者保證是那個 node；給了它，fd 就是權威（`<taskdir>` 字串只拿來跟環境對照）。fd 無效（不是數字、沒開、不是資料夾）時 stderr 說清楚、退出碼 2，**不回退**去寫 `<taskdir>` 字串指的地方（可能已被換掉）。這個入口不是驗證或隔離任務身分的邊界：字串與 fd 指不同任務時照 fd 跑。

任務的環境變數（找到自己的唯一管道）：`AOS7_ROOT`、`AOS7_NODE`（絕對路徑）、`AOS7_NODE_ID`、`AOS7_TASK`（任務資料夾絕對路徑）、`AOS7_TID`；`PATH` 前面加 `bin/`。cwd＝node。

任務狀態判斷：有 exit.json＝結束；有 pid.json 且任務程序或 aos7-run（`runner_pid`）還在＝活；有 pid.json、兩者都不在、又沒 exit.json＝**lost**（tock 替它寫 `exit.json` `{"code": null, "lost": true}`）；沒有 pid.json、`runner.json` 記的 aos7-run 確定已不在（pid 不在／殭屍、或 starttime 不同）＝也是 **lost**（runner 在寫 pid.json 前就死了；astra-7 H-06）；其餘只有 birth.json＝剛起（算活；沒有 runner.json 的、starttime 沒記到的不猜）。

任務自己知道時間的方法：輪詢 `$AOS7_TASK/tock.json`（S-11）。非 Python 任務可用 `aos7-wait-tock [--after N] [--timeout 秒]`：等到就印回合數（逾時退出碼 1；probes/polyglot N6）。tock.json 不是物件（`[1]`、`2`）當沒有、繼續等（astra-5 F-06）。

**只碰給的資料夾**（S-10、S-23）：任務能寫的是自己的 node（**扣掉裡面巢狀的別的 node 與 daemon 根**）加上掛載點的目標。程式碰別的 node 一律用 `lib/aos7_mount.py` 的 `resolver(taskdir)`：把空間裡的路徑換成掛載點下的路徑，沒掛到回 None（不寫）。

**寫入紀錄**（檢查用，只記不擋）：起 daemon 的環境有 `AOS7_AUDIT`（任何非空值）時，aos7-run 起任務時把 `lib/audit_site/` 放進任務的 `PYTHONPATH`（aos7-run 自己不載入，它寫的 pid.json、exit.json 不算任務的寫入；probes/polyglot N7），Python 任務啟動時載入 audit hook，把空間根底下每個寫入動作（開檔寫、rename／replace、remove、mkdir、rmdir、symlink）記一行到 `$AOS7_TASK/writes.jsonl`：`{"op", "path"（實際位置）, "ok", "pid", "via"（經過連結時寫的路徑）}`。`ok`＝實際位置在上面說的範圍內；掛載點的範圍取 birth.json 宣告的 `to`（接空間根再 realpath），不看連結現在指哪（任務自己改指連結不算）；判不過時重讀 birth.json，算進執行中加掛的。帶 `dir_fd` 的 mkdir／rmdir／remove／rename／replace／symlink／link 以那個 fd 指的資料夾為起點；`open` 的 audit 事件不帶 dir_fd，看不到（M-12）。`lib/aos7_audit.py` 的 `scan(root)` 把整個空間的紀錄拼起來挑出 `ok: false` 的（壞行跳過、計 `bad_lines`）。hook 寫 writes.jsonl 也先補半行的換行（第 0 節；astra-7 H-03）。只看得到 Python 程序（problems.md M-3）。

## 6. 任務控制（S-17）

任何人寫 `<taskdir>/ctl.json`。**tick 與 tock 時刻**才執行（S-17「在 tick-tock 時」）：

- **kill 只保證收到這些**（使用者 10-03 Q1 選 (a)）：任務的程序群組、群組成員活著的後代所在的群組、環境變數 `AOS7_TID`＋`AOS7_NODE` 都是這個任務的程序。任務故意脫離（setsid 又改環境變數、雙 fork 後清掉環境、刪掉自己的 taskdir）由任務自己負責；daemon 不用 subreaper／cgroup。
- pid.json 在任務自己寫得到的 taskdir：kill 前先確認那個 pgid 群組裡有程序（或它的父程序＝aos7-run）的環境變數 `AOS7_TID`＋`AOS7_NODE` 是這個任務；不是就不打那個群組（回 `ok: false`），只收環境變數相符的（probes/chaos B7：改了 pgid 的任務能讓 kill 打到別人，包括 daemon）。群組已沒有活成員照常算。
- `kill`：對 pid.json 的 pgid **以及該群組成員所有後代所在的群組**送 SIGTERM，等至多 1 秒，還在就 SIGKILL（後代：aos-exec 把 inst 的子程式開在另一個 session）。另外掃 `/proc/*/environ`，環境變數 `AOS7_TID` 與 `AOS7_NODE` 都是這個任務、但已被 init 收養的程序（雙 fork、setsid）也一起收（不含 aos7-run；probes/polyglot N5）。
- `restart`：kill，再把 birth.json 的定義（`name`、`argv`／`inst`、`subroot`、`allow_stop`、`mounts` 宣告）寫成 `spawn/restart-<tid>.json`（帶 `restart_of`），下回合 tick 起新的（維持「任務一律由 tick 啟動」）。**restart 照出生時的定義；改了 tasks.json 想照新的起，用 `reload: true`。**
- `restart` 加 `"reload": true`（使用者 10-03 答 Q6：「加上flag reload」）：新任務的定義取**自己 node 現在的 `.aos/tasks.json` 裡同名（birth.json 的 `name`）的第一個項目**，去掉 `mode`、`from_round`、`max_live`（跟一般 restart 的 spawn 一樣當 each 起），帶 `restart_of`；掛載＝項目的 `mounts` 加上執行中加掛的（birth.json 標 `dyn` 的；同名以項目為準）。**同名被項目接管的，來源也改成宣告**：新任務不再標 `dyn`，spawn 的 `mounts_dyn` 只帶沒被宣告接管的名字；之後從 tasks.json 刪掉這個宣告再 reload，它就真的拿掉，`diff` 看得到（astra-6 G-06）。找不到同名項目、tasks.json 讀不懂、或該項目不合格（第 4 節的**完整**檢查，含 `mode`、`from_round`、`max_live` 的型別：先驗原項目，過了才剝這三欄；astra-6 G-05）→ **整個 ctl 不執行（不 kill）**，回條 `ok: false`，msg 說原因（「不加 reload 會照出生時的定義重起」）。找到就照常 kill、寫 spawn，回條 `result.diff`＝`{欄: {"old", "new"}}`（`argv`、`inst`、`mounts` 宣告、`subroot`、`allow_stop` 有變的），msg 也列 `欄 舊 → 新`；沒變寫「定義沒變」。`reload` 不是 bool → `ok: false`、不執行。沒有 `reload`（或 false）行為不變。
- 已結束的任務：kill 當成功，但照上面的環境變數比對收掉它留下還活著的子孫（msg 寫 `already ended; N leftover process(es) killed`；astra-4 I-04）；restart 照樣寫 spawn（帶原本的 `mounts` 宣告，新任務照樣掛）。
- ctl.json 讀不懂或不是 JSON 物件（例如 `[]`）：不執行，照樣搬成 ctl-done.json，內容 `{"raw": 原內容或 "unreadable", "result": {"ok": false, "msg": "not a JSON object"／"unreadable JSON"}}`（同 daemon ctl；不拖垮 tick／tock）。

執行完把 ctl.json 搬成 ctl-done.json。node 被 pause 時沒有 tick／tock，ctl 會等到 resume。

## 7. tock（S-08、S-11）

`aos7-tock <root> <node-id>`：

1. 執行任務控制（第 6 節）。
2. 掃所有任務：lost 的補 exit.json；記下新結束的。
3. 對每個活任務寫 `tock.json`。
- 掃之前先把「已寫 ended.json、而且 `本回合 − ended 的回合 > keep_ended_rounds`」的任務資料夾整個搬到 `<node>/.aos/tasks-old/<tid>/`（使用者 10-03 Q3 選 (a)），總結多 `archived: [tid...]`。之後 tick、tock、status 只掃 `.aos/tasks/`，舊任務多也不變慢（probes/swarm D 段）。tid 不跟 tasks-old 裡的撞。要看歷史（kernel 接前任狀態 `restart_of`、agent 接前任 state.json、kernel 算用量總和）的地方兩處都找：`aos7_fs.task_dirs_of(aos)`（同一 tid 只回一次）、`aos7_task.find_task_dir(node, tid)`。**讀到一半被搬走**（列到舊路徑、還沒開檔就被 tock 搬了；astra-5 F-02）：一律用 `aos7_fs.task_read(aos, tid, 路徑, fn)` 讀——fn 讀完時資料夾已不在原處，就重新定位、整份重讀；哪裡都找不到回「讀不齊」（unknown），呼叫的人不能當成「沒有」或 0。
4. 在 `rounds.jsonl` 加一行總結（檔尾有上次中途被殺留下的半行時先補換行，總結的 `errors` 多一筆 `phase: "rounds.jsonl"`；寫完讀回最後幾行確認這回合的總結**完整提交**，讀不回就失敗退出、不寫 ended.json、不關回合，下次 tock 重來；astra-6 G-08）；**之後**才對新結束的寫 ended.json（中途被殺時下次 tock 會再報一次，不會永久漏掉；astra-4 I-03）；寫 `round.json`（open: false）。
5. stdout 印一行 JSON 總結，結束。

- node 不在（同 tick，含動作中途被刪）印 `{"gone": true}`；舊世代印 `{"stale": true}`；round.json 已是 `open: false`（這回合 tock 過了，例如 tick 被打斷）印 `skipped`、不寫第二行總結（probes/nest3 N1）。
- **同回合已有總結**（astra-5 F-05）：寫總結前看 `rounds.jsonl` 最後 5 行，已有這個 round 的（上一次 tock 寫完總結就被 kill -9 或逾時收掉）就不寫第二行，只把收尾做完：那行總結 `ended` 裡的任務補 `ended.json`（總結之後才結束的不補，留給下一回合報，不會漏）、`alive` 裡還沒收到這回合 tock.json 的補寫，round.json 關上並標 `replayed: true`、`incomplete`（`AOS7_INCOMPLETE`，沒給是 `"tock"`）。stdout 印原總結加 `replayed: true`。所以 rounds.jsonl 每個 round 至多一行；要知道哪回合的收尾是補做的，看 round.json（最近一回合）或 daemon log 的 `replay`。
- 一個任務的資料夾壞掉（birth.json 不是物件、tock.json 被改成資料夾…）只記在總結的 `errors`（`[{"tid","phase","err"}]`），其他任務照收 tock（astra-4 I-05）。birth.json 讀不到時 name 從 tid 推（`<name>-r<N>[-k]`），keep 不會以為沒有活實例又起一份。
- timeline.json 設了 `keep_old_rounds`（第 1 節）時，tock 也把 tasks-old 裡 `本回合 − ended 的回合 > keep_old_rounds` 的任務資料夾刪掉，總結多 `purged: [tid...]`（刪不掉的記 `errors` 的 `phase: "purge"`；astra-7 H-08）。沒設不刪。
- 總結多三欄：`early`（同 tock.json）；`ended` 每項多 `name`，被 kill／restart 收掉的多 `by_ctl: {"op","by"}`（probes/lifecycle N-4）；有的話 `tasks_error`。

## 8. 小工具（S-01）

`aos7-ctl` 只是「替你寫控制檔」，LLM 用寫檔一樣做得到：

- `aos7-ctl daemon <root> <op> [node] [--kill] [--rounds N]`：寫 `<root>/.aosd/ctl/<時間>-<pid>.json`（`--kill` 給 stop 用，`--rounds` 給 resume 用；op 多一個 `wake`）。`<root>` 也可以是掛進來的 `.aosd` 或 `.aosd/ctl`（任務裡用掛載點）。
- `aos7-ctl task <taskdir> <kill|restart> [why] [--reload]`：寫 ctl.json（`--reload` 只給 restart，寫 `"reload": true`；給 kill 退出碼 1）。
- 兩者都可加 `--by WHO`（預設：在任務裡是 `<node-id>:<tid>`，否則 `cli`）；stdout 印一行 `{"wrote": 路徑}`。

## 9. kernel（S-16～S-18）

一個 `keep` 任務 `aos7-kernel`，設定在 `<node>/kernel.json`：

```json
{"members": ["agents/amy", "agents/bob"],
 "stuck_rounds": 3, "budget_tokens": 400, "cool_rounds": 3,
 "max_age": {"subd": 8},
 "llm_stuck_rounds": 200, "cap_tokens": 200000,
 "roles": {"agents/amy": "寫程式", "agents/bob": "審稿"}}
```

後三個可選。

kernel 要看的東西都經過掛載點（S-23）：daemon 的 `.aosd`（讀 status.json、寫 ctl）、每個成員的 `.aos`（讀 round.json、任務；寫任務 ctl.json）。**每輪先對沒掛到的寫加掛請求**（第 4 節），所以 tasks.json 不必寫 mounts，加成員只改 kernel.json；下一個 tick 掛上之前，那個成員當作不存在（快照 `mounted: false`，不下決定），`.aosd` 還沒掛時 pause／resume 寫不出去，decisions.jsonl 記 `skipped`。kernel 自己 node 的任務直接寫。

每收到一次 tock（自己 node 的回合）跑一輪規則，判斷結果寫成控制檔：

- **卡住**：成員 node 的活任務，若有 `progress.json`，它的內容連續 `stuck_rounds` 個**成員 node 的回合**（看成員的 `round.json` 有沒有前進）沒變 → 寫該任務 ctl.json `restart`。沒有 progress.json 的任務不管；成員 node 被 pause 時不數。progress 有 `llm_since`（agent 正在等 LLM）時改用 `llm_stuck_rounds`，沒寫就不管（problems-real.md R-3）。
- 快照讀任務資料夾用 `aos7_fs.task_read`（第 7 節）：讀到一半被 tock 搬到 tasks-old/ 就到新位置重讀；讀不齊的任務列在快照的 `unknown`，那個 node 的 `usage_total` 是 None（unknown，不是 0）。那一輪預算／總額規則跳過這個成員：**不更新基準、不 pause、不 resume、不歸零**；卡住規則保留它的 progress 紀錄（astra-5 F-02）。
- **預算**：成員 node 各任務（含已結束的）的 `usage.json`（`{"tokens": int, "calls": int}`）加總，比上一輪多出的量累計超過 `budget_tokens` → 寫 daemon ctl `pause` 該 node；pause 後 `cool_rounds` 個 **kernel 自己 node 的回合** → `resume`，累計歸零（被移出 members 後到期的 resume 也歸零，astra-3 三-1）。第一次看到某 node 時現有用量當基準、不算舊帳。成員是 kernel 自己的 node 時不管（pause 自己就收不到 tock、無法 resume）。**kernel 自己 pause 的，自己負責到期 resume，不管對方還在不在 members**（astra-2 二-7）。
- **總額**：成員 node 的用量總和（不扣基準）超過 `cap_tokens` → `pause`（rule `cap`），冷卻不 resume；人把 `cap_tokens` 調高到總和以上或拿掉後，下一輪 `resume`（理由寫實際的用量與上限）。被移出 members 的成員若是總額 pause 的，一直停著（R-4）。
- **名冊**：每輪把 `{"by": 自己 node id, "members": [{"node", "inbox": "<node>/inbox", "role": roles 裡那句或空字串}]}` 經過 `<成員>/.aos` 掛載點寫到每個成員的 `.aos/roster.json`；內容沒變不寫（R-2、M-15）。寫不進去（成員搬走、掛載斷了）不丟例外：decisions.jsonl 記一行 `{"rule": "roster", "op": "write", "target": 成員, "skipped": 原因}`，跳過那個成員，其他照做（astra-3 三-2、M-16）。
- **壽命**：自己 node 名為 `max_age` 鍵的活任務，活超過（自己 node 回合數 − birth round）那麼多回合 → ctl.json `kill`。
- 對同一任務的指令只下一次；目標已有 ctl.json（別人先下了）就不蓋、不下。
- 每個決定寫一行到 `$AOS7_TASK/decisions.jsonl`：`{"round","rule","target","op","why","at"}`；沒寫出去的多 `skipped`（沒掛載，或寫控制檔丟了 OSError——同樣只記不死）。`target`：任務是 `<node id>:<tid>`，node 是 `<node id>`。
- 每輪重讀 kernel.json（改檔即生效）。規則狀態存 `$AOS7_TASK/kernel-state.json`（含 `round`＝已處理到第幾回合）；新任務資料夾裡沒有時，接 birth.json 的 `restart_of`，否則接同名任務裡 birth round 最大的那份。
- 啟動時跳過 ≤ 狀態 `round` 的 tock；`--rounds N` 收到 N 次 tock 後結束；SIGTERM／SIGINT 乾淨結束。

成員 node id＝自己的 node id 接上成員相對路徑。daemon ctl 經過掛載點寫到（`.aosd` 的）`ctl/kernel-<tid>-r<回合>-<序>-<op>-<node>.json`，內容 `{"op","node","by","why"}`，`by`＝`<node id>:<tid>`。程式：`lib/aos7_kernel.py`（迴圈、套用）、`lib/aos7_kernel_rules.py`（快照＋純函式 `run_rules`）。

## 10. agent（S-16、S-19）

一個 `keep` 任務 `aos7-agent`。狀態 `$AOS7_TASK/state.json`：

```json
{"state": "idle", "round": 4, "steps": 7, "tocks": 9, "plan": null, "pc": 0,
 "letters": [], "goal": null, "last": "...", "from": null}
```

`pc`＝act 做到 plan 第幾步；`letters`＝這輪 idle→think 時抓下的信檔名（之後新到的信留給下一輪）；`goal`＝這輪要先開口的 goal 內容；`from`＝接續的前任 tid。

**每收到一次 tock 換一次狀態**（S-19「依託 tick-tock 換狀態」）。時機：收到 tock 先換狀態、存檔，再做「新狀態的事」（think＝問 LLM、act＝跑工具），所以 state.json 寫 think 表示「這回合在想」。一封信從寄出到回信約 2～4 回合。

- `idle`：看 `<node>/inbox/*.json` 有沒有新信（或 `<node>/goal.json` 要它先開口）；有 → `think`，沒有 → 留在 idle。
- `think`：先寫 progress.json＝`{"round","state":"think","steps","llm_since": 時間}`（給 kernel 分辨「在等 LLM」，R-3），再呼叫 LLM（輸入：persona、信件、`<node>/.aos/roster.json` 有的話帶上），得到 plan（JSON 動作清單）→ `act`。
- `act`：照 plan 做工具動作 → `idle`。處理過的信搬到 `inbox/done/`。
- 下一個 tock：`act` → `idle`（這個 tock 不看信箱，下一個才看）。
- `goal.json` 用掉後改名 `goal.done.json`（不論 plan 成不成功）。
- 重啟：自己的 state.json 沒有時，接同 node 同名任務中回合最新的那份 state.json（讀到一半被搬到 tasks-old/ 的到新位置重讀，astra-5 F-02）；停在 think 且沒 plan → 重問一次 LLM；停在 act → 從 `pc` 接著做（`pc` 那步可能重做一次）。
- 單執行緒：LLM 呼叫比回合長時，期間來的 tock 只看最新一個（中間的回合被併掉）。

工具（plan 是 `[{"tool": ...}, ...]`）：

| tool | 參數 | 做什麼 |
|---|---|---|
| `send` | `to`（node id）、`body` | 經過掛載點寫一封信到 `<to>/inbox/<時間>-<自己>.json`：`{"from","to","round","body"}`。對方的 inbox 沒掛：寫加掛請求，信先放 `<node>/outbox/`；之後每個 tock 一開始先清 outbox（掛上了就寄，加掛被拒就搬到 `outbox/failed/`）。被拒過的對象直接失敗。已掛但收件夾不在（被刪、被搬走）或寫不進去：這封失敗，信放 `outbox/failed/`，信裡加 `failed: {"why","at"}`（M-14） |
| `write` | `path`（相對自己 node）、`text` | 寫檔 |
| `save` | `letter`（收到的信的檔名）、`path`（相對自己 node）、可選 `code` | **不經 LLM**，把 `inbox/` 或 `inbox/done/` 裡那封信原樣寫成檔：`code: true` 時只取 body 第一段 ``` 程式碼（沒有圍欄取整段），否則整段 body（R-15 (b)）。找不到信、檔名含 `/` 就那步失敗 |
| `none` | — | 什麼都不做 |

每次 LLM 呼叫把用量累加到 `$AOS7_TASK/usage.json`（`{"tokens","calls"}`，每個任務自己從 0 起算，不接前任）。**每處理完一個 tock** 覆寫 `$AOS7_TASK/progress.json`＝`{"round","state","steps"}`（給 kernel 判斷卡住：idle 等信也會更新，只有卡在 LLM 呼叫、收不到 tock 時才連續不變）。

設定在 `<node>/agent.json`：`{"name": "amy", "persona": "...", "llm": "fake"}`；`llm` 可為 `fake`（決定性、離線）或 `{"url": "http://localhost:1234/v1", "model": "..."}`（OpenAI 相容）。可選：`max_ping`（fake 用，預設 6）；`llm` 物件可加 `timeout_s`（預設 120）、`temperature`（預設 0）、`max_tokens`、`api_key`。

- fake：`goal.json` 的 `{"say_first": {"to", "body"}}` 讓它先開口；收到 body 為 `ping N` 的信回 `ping N+1` 給寄件者，N ≥ `max_ping` 改成 `write work/done.txt`、不再回。tokens＝prompt 字元數 // 4。
- 任何工具丟例外都當成那一步失敗（state.last 記「工具失敗：…」），agent 不退出。
- OpenAI 相容：system＝規則（四個工具）＋persona，user＝`{"roster"（有名冊才有）,"goal","letters"}` 的 JSON，每封信帶 `file`（信檔名，給 save 用）；要模型只回 JSON 陣列。解不出就當 `[{"tool":"none"}]`，原因寫進 state.last。tokens＝回應的 `usage.total_tokens`。
- `send` 的 `to` 必須是空間裡的路徑（不能絕對、不能跑出根）；`write`、`save` 的 `path` 不能跑出自己的 node。不合就跳過該步並記在 last。

**真模型用的補充**（`demo/real.py` 用到；不設就跟上面一樣）：

- `agent.json` 的 `"memory": N`：think 的 user JSON 多一個 `memory`＝`{"recent_letters": 最近 N 封往來的信（收：inbox/done/，帶 `file`；寄：<node>/sent.jsonl，依 at 排；視窗外的每個往來對象再補它最近一封，R-13）, "my_files": 自己 work/ 底下的檔（每檔截 4000 字）}`。`send` 一律把信多記一行到 `<node>/sent.jsonl`。**只讀尾端**（astra-3 三-3）：inbox/done/ 依檔名（時間開頭）取最後 max(N, 200) 封、sent.jsonl 從檔尾往回讀最後 max(N, 200) 行，不隨歷史變慢；「每個對象補一封」也只在這範圍內找。
- `agent.json` 的 `"wake": {"rounds": N, "unless": "相對 node 的路徑"}`：idle 且沒信沒 goal、離上次開始 think 已 N 個回合、`unless` 的檔又不在 → 自己 think 一次，goal＝`{"wake": "…"}`（不改名 goal.json）。
- `llm` 物件的 `retry`（預設 1）：plan 解析不出時，把原回應接一句更正再問，最多 retry 次；每次都算進 usage 的 `calls`。
- 每次真模型 think 在 `$AOS7_TASK/llm.jsonl` 記一行：`{"at","round","round_before","round_after"（node 的回合，呼叫前後）,"ms","calls","tokens","note","letters","raw"（原文前 4000 字）}`。
- 每處理一個 tock，在 `$AOS7_TASK/trace.jsonl` 記一行 `{"round","state","steps","at"}`（跟 progress.json 同時寫）。

agent 的進出流水印在 stdout（一行一個 JSON，aos7-run 收進 out.log）。`aos7-agent --rounds N`：處理 N 次 tock 後自行結束；SIGTERM／SIGINT 乾淨結束（code 0）。
