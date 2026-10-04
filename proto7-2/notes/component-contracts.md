# proto7-2 組件功能定義藍圖：契約卡與錯誤歸屬

← [proto7-2](../README.md)｜[spec](../spec.md)｜[problems](problems.md)｜依據：[設計原則](../../proto7/notes/principles.md)第 7～10 條、[核心 spec](../../proto7/spec/core.md)（S-）、[四層交接點](layer-interfaces/01-daemon-ticktock.md)

**用途**：判斷「一個錯誤是不是某組件的問題」（原則 9、10）。每個組件一張契約卡：**前置條件**（呼叫者／環境要保證的，違反＝誤用，不歸它管）與**保證**（前置成立時它承諾的）。改進循環每輪：先對這份分類 → 再精簡／修補 → 再回歸。是大概規劃，不是 spec；細節條文仍以 spec 為準，衝突處以本檔的「歸屬」為準去改 spec。2026-10-04，Fable 寫；只讀 repo，沒改程式。寫的時候 `notes/core-slimming.md` 還不存在，`notes/layer-interfaces/` 只有 01、02 兩份。

## 1. 組件清單與邊界

| 組件 | 程式 | 一句話 | 誰呼叫它 | 它呼叫誰 |
|---|---|---|---|---|
| **daemon** | `aos7_daemon.py` | aos 與 Linux 的介面：跑登記的 node、處理控制檔、寫 status（S-03～06） | 人、父 node 的任務（路一） | 時間線迴圈（thread） |
| **時間線迴圈** | `aos7_daemon_timeline.py` | 一個 node 的節拍：照 2.1 六步起 tick／tock 程序 | daemon | tick、tock |
| **tick** | `aos7_tick.py` | 開回合、執行任務控制、照 tasks.json 在槽裡起 run，不等（S-09、S-10） | 時間線（人手也行） | aos7-run |
| **tock** | `aos7_tock.py` | 關回合：判槽、寫上一次總結、通知活任務、刪不要的槽（S-08、S-11） | 時間線（人手也行） | 無 |
| **aos7-run（runner）** | `aos7_run.py` | Linux 子程序與檔案協定的交接者：pid.json／exit.json／out.log | tick | 任務 |
| **控制檔處理** | `aos7_daemon.py`（`.aosd/ctl/`）、`aos7_task.run_ctl`（槽 `ctl.json`） | 把「寫檔」變成「動作」，每件一回條，重播只生效一次（S-17、S-18、S-21 路二） | daemon 主迴圈／tick、tock | — |
| **模組（擴充點）** | `modules/*.py` | 核心以外的功能，一律以普通任務掛上（原則 1、7） | tick（經 tasks.json） | 核心檔（只讀） |
| **任務** | 任何程式 | tick 起的程序；kernel／agent 都是任務（S-16），分四類（§2.8） | aos7-run | 彼此（檔案協定） |
| **人／外部程式** | `aos7-ctl`、`aos7-wait-tock`、編輯器、cron… | 寫給人寫的檔、修復 §12 停點；工具是這一側的便利，不是核心 | — | daemon／tick（寫檔） |

共用程式庫（`aos7_fs`、`aos7_proc`、`aos7_task` 的判定）不是組件，是**四個判定入口**（檔／回合／程序／槽，spec §0）；它們的 bug 歸「呼叫它的那個組件的保證沒兌現」，修在入口。

**檔案所有權（判誤用最常用的一張表）**：

| 檔 | 唯一寫者 | 給誰寫（合法輸入） |
|---|---|---|
| `.aosd/nodes.json`、`paused.json`、`gen.json`、`status.json`、`ctl-done/`、`ctl-failed/` | daemon | 沒有人 |
| `.aosd/ctl/*.json`、`log.on`、`owner.json` 的 `owner` 塊 | — | 人、任務、kernel（控制檔）；子 daemon 自己（owner） |
| `.aos/round.json`、`last-round.json`、`ctl-seen.json`、`action.owner.json` | tick／tock | 沒有人（§12 修復例外：先 pause、保存證據） |
| `.aos/tasks.json` | 多人，**一律拿 `tasks.json.lock`** | 人、kernel、tick、tock |
| `.aos/timeline.json`、`mount_allow` | — | 人、kernel |
| 槽 `birth.json`、`tock.json`、`mnt/`、`mount-done/` | tick／tock | 沒有人 |
| 槽 `pid.json`、`exit.json`、`out.log` | aos7-run（lost 時 tock／tick 寫 exit） | 沒有人 |
| 槽 `ctl.json`、`mount-req/` | — | 人、任務、kernel |
| 槽其他檔（`state.json`、`usage.json`…）、槽外交付物 | 任務 | 任務自己；核心不讀格式 |

**規則一句話**：寫了不是給你寫的檔、或不照要求的方式寫（不拿鎖、換成 FIFO／資料夾／符號連結、手改內容）＝誤用，後果不歸任何核心組件。

## 2. 契約卡

格式固定：職責／輸入→輸出／前置條件／保證／最基礎保護／明確不管。「最基礎保護」只列程序被殺、I/O 錯、/proc 讀不到這三種外部故障的處理，其餘不加。

### 2.1 daemon（`aos7-daemon <root>`）

- **職責**：只跑 `nodes.json` 登記的 node，每個一條時間線；處理 `.aosd/ctl/`；每圈寫 `status.json`；是空間根的守門人（S-07）。
- **輸入→輸出**：root 路徑、`nodes.json`／`paused.json`／`gen.json`／`timeline.json`、控制檔、SIGTERM／SIGINT → `status.json`、回條、`nodes.json`／`paused.json`／`gen.json` 更新、可選 `log.jsonl`。退出碼 1＝`daemon.lock` 拿不到。
- **前置條件**：root 存在、可 stat、是真資料夾；同一個 root 同時只有一個 daemon（鎖保證）；node 路徑在 root 下、沒有符號連結、不包住別的 daemon 根；`.aosd/` 內部檔沒人手改；控制檔是 JSON 物件、檔名由寫者保證不互蓋。
- **保證**：只跑登記的 node，一個 node 任一時刻最多一條時間線；舊回合確知已關才開下一回合（2.2）；每件控制檔要嘛回條、要嘛進 `ctl-failed`、要嘛留著下次做；SIGTERM＝stop＋kill；**絕不沿符號連結寫出 root**；status 每圈更新，`stopped: true` 是最後一份。
- **最基礎保護**：daemon 被殺→重開照 `nodes.json` 接著跑、gen＋1、先收未關回合；root／node 看不到（EIO、EACCES）→保留現狀、記 `last_error`，不判 missing、不殺；/proc 讀不到→不殺、不清記著的 live／pgid；一件控制檔丟例外不擋同圈其他件；暫存檔清「寫者確定不在」的。
- **明確不管**：手改 `nodes.json`／`paused.json`／`gen.json`／`status.json`；兩個 daemon 根重疊；控制成環（S-22）；誰有權寫控制檔（§11）；控制檔檔名互蓋（W3：檔名是寫者的事）；斷電後檔案系統的持久化順序；不在管理範圍的程序（§11）。

### 2.2 時間線迴圈（daemon 內，每 node 一條）

- **職責**：按 `timeline.json` 的節拍，照 2.1 六步起 tick／tock 程序，處理 pause／wake／resume，把 tick／tock 的退出碼翻成 status。
- **輸入→輸出**：`timeline.json`、`round.json`（判定）、`paused.json`、wake／resume 事件、tick／tock 的 stdout／退出碼 → 起 `aos7-tick`／`aos7-tock`（環境 `AOS7_GEN`／`AOS7_EARLY`／`AOS7_INCOMPLETE`）、status 的 node 區、`last_error`、`last_event`。
- **前置條件**：tick／tock 是本 repo `bin/` 的程式並守退出碼契約（0 做了、3 不知道）；`round.json` 只由 tick／tock 寫；`timeline.json` 的數值合法（不合＝用預設並記一筆，不是故障）。
- **保證**：同一 node 不會同時跑兩個動作；`round.json` 不知道→不 tick、退避；tick 退出 3→退避；tock 沒關上→馬上補一次；動作逾時 SIGKILL 並記；pause 清單非空不開回合；wake／resume 語意照 P2-01、A2-11；`rounds` 倒數按 owner 各記。
- **最基礎保護**：tick／tock 卡住→`action_timeout_s`；舊世代持鎖者認得出就殺、認不出不殺並記提示；迴圈丟例外→記 `last_error`、0.5 秒後續跑。
- **明確不管**：節拍準不準（S-08）；interval 0 的 CPU；tick 退出碼 1（例外）當正常回合只記 `last_error`（layer-interfaces 01 的缺口 G2，待定）。

### 2.3 tick（`aos7-tick <root> <node-id>`）

- **職責**：開回合（round＋1）；執行任務控制與加掛審核；拿表鎖讀 `tasks.json`、挑要起的、在槽裡起 run；印一行 JSON；**不等任務**。
- **輸入→輸出**：`round.json`／`last-round.json`／`tasks.json`／`ctl-seen.json`／`gen.json`、各槽 birth／pid／exit／ctl／mount-req、`AOS7_GEN` → `round.json`（open:true、reaped、tasks_rev）、`tasks.json`（只在 once／restart 時）、槽的 `birth.json`／`mnt/`／`mount-done/`、`ctl-done.json`／`ctl-seen.json`；stdout；退出碼 0／3。
- **前置條件**：在 `action.lock` 下、世代正確地被呼叫（人手跑要自己確保沒有 daemon 在跑同一 node）；上一回合已確知關上；改 `tasks.json` 的人都拿鎖；生命週期檔只有核心寫、是一般檔；node 路徑沒有符號連結。
- **保證**：一個槽一個 tick 最多起一次；只在「空」或「已結束」的槽起；once 不重複、不無痕消失（`launch` 標記）；單項欄位錯只跳那項；不知道→退出 3、什麼都不寫；不起、不判 lost、不刪槽；起之前把「已結束未報」的 run 記進 `reaped`。
- **最基礎保護**：被殺在任一點→下一個 tick 靠 `launch`／birth／exit／pid 證據恢復，不多起；表鎖 1 秒拿不到→回合照開、不起、記 `tasks_error`；列不出槽／讀不到 round→退出 3。
- **明確不管**：任務跑什麼、跑多久、退出碼意義；不拿鎖編輯 `tasks.json` 被蓋（W8）；生命週期檔被換成 FIFO／資料夾或手改內容（A3-03）；交付物寫在槽內被刪（W7）；回合數被人手倒退（run 仍遞增，僅此而已）。

### 2.4 tock（`aos7-tock <root> <node-id>`）

- **職責**：關回合：執行任務控制、掃槽判定、lost 補 `exit.json`、寫 `last-round.json`、再寫活任務的 `tock.json`、補 `seen_round`、刪該刪的槽、`open: false`。
- **輸入→輸出**：`round.json`、各槽、`tasks.json`（刪槽前嚴格讀）、`AOS7_GEN`／`AOS7_EARLY`／`AOS7_INCOMPLETE` → `last-round.json`、`tock.json`、lost 的 `exit.json`、`round.json`（open:false、notify_errors）、`ctl-seen`／`ctl-done`；stdout 總結；退出碼 0／3。
- **前置條件**：同 tick；只收 `open: true` 的回合；槽內基礎設施檔由核心寫。
- **保證**：**先提交 `last-round.json`（讀回確認）才寫 `tock.json`**（模組收到通知時總結一定已在）；同回合已有完整總結→重播不重寫、只收尾；不知道的槽不判 lost、不刪、記 `errors`；只刪「名字不在表上、已結束、結束已報過一回合」的槽；通知寫失敗不吞，記 `notify_errors`，下一個 tick 補。
- **最基礎保護**：寫完總結被殺→重播；讀回不符→不往下、退出 3；列不出槽→不關回合。
- **明確不管**：任務漏看 tock（只留最新，S-11）；槽被刪連帶任務自己的檔；任務不理 SIGTERM 拖慢動作；tock 不「收掉」任務。

### 2.5 aos7-run（runner，`aos7-run <taskdir> <fd>`）

- **職責**：讀 `birth.json`，把任務起在自己的程序群組，寫 `pid.json`，等它，寫 `exit.json`；`out.log` 收 stdout＋stderr。
- **輸入→輸出**：任務資料夾 fd、`birth.json`、`AOS7_*` 環境 → `pid.json`（run、pid、pgid、starttime、runner_pid、uid）、`out.log`、`exit.json`（run、code、round）。退出碼 2＝fd 無效。
- **前置條件**：由 tick 以新 session、傳好 fd、cwd＝node 起；`birth.json` 已寫好；環境變數齊。人手直接跑不在保證內。
- **保證**：起程序前任何失敗→`exit.json` code 127 帶 error；fd 是權威，不回退字串路徑；活到任務結束才寫 exit；`AOS7_*` 原樣傳給任務。
- **最基礎保護**：runner 被殺→tick／tock 靠身分掃描與 pid.json 判定（不是 runner 自己處理）。
- **明確不管**：任務換 session／pgid、清 `AOS7_*`、換 uid、關 dumpable（§11）；`out.log` 大小（W10）；任務退出碼語意；任務自己的 state／usage。

### 2.6 控制檔處理（daemon 的 `.aosd/ctl/`＋槽的 `ctl.json`，一張卡）

- **職責**：把一份 JSON 請求變成一次動作，給一份回條；同一個意圖重播只生效一次。
- **輸入→輸出**：`ctl/<名>.json`／槽 `ctl.json` → `ctl-done/`／`ctl-done.json`、`ctl-failed/`、`ctl-seen.json`；副作用在 `nodes.json`、`paused.json`、`tasks.json`、程序。
- **前置條件**：JSON 物件、`op` 合法；**檔名由寫者負責**（同名＝同一件事的最新一次）；新請求用新 `id`，重送同一件才沿用；owner／by／node 的檔名編碼是寫工具的事；要嚴格只收某一次就帶 `run`。
- **保證**：每件三選一（回條／ctl-failed／留著）；同槽同 `ctl_id` 不重做；kill 只在確知任務程序已不在時回 `ok: true`，否則 `ok: false`（unknown）；restart 先加 once 項再 kill；回條 `ok` 只表示「daemon 接受」，不表示已生效。
- **最基礎保護**：處理到一半被殺→靠 `ctl-seen.json`（槽）或「搬不走不再做」（daemon）；刪不掉請求→`dup` 記錄；寫回條失敗→`ctl-failed`。
- **明確不管**：誰有權寫；成環；不同寫者取同檔名互蓋；手改 `ctl-seen.json`；不帶 `run` 的 kill 在重播窗口打到新 run（已接受）；保留 mtime 複製還原請求檔造成的誤判（A3-05）。

### 2.7 模組（擴充點）

- **職責**：核心以外的功能，用普通任務掛上：history、counter，未來的清理、量測（`timing` 統計）、kernel 包。核心完全不知道它存在（沒有鉤子）。
- **核心對模組的前置條件**：是 `tasks.json` 的一項（S-10）；只碰給的資料夾與掛載；自己管保留與輪替；不寫核心檔。
- **核心對模組的保證**：收到自己 node 的 `tock.json` 時 `last-round.json` 已是該回合；同槽 state 接續；`tock.json` 帶 run 過濾；只留最新。
- **明確不管**：模組漏取樣（§9 已接受）；模組自己的 bug（例如 A2-10）；模組寫壞自己的檔；模組慢了拖住 early_tock。

### 2.8 任務（kernel、agent 都是）

- **核心看到的只有一種任務**；四類是 kernel 層的標籤，寫在任務包的 README，`tasks.json` 不加 kind 欄：**核心任務**（kernel 自己運作必需：排程器、准入、控制時間線、帳本）、**通用任務**（把 LLM 換成 cron 仍成立：記帳、配額、history、copier、量測、批次登記）、**agent 任務**（idle／think／act 狀態機、工具使用）、**LLM 任務**（沒有 LLM 就沒有這個問題：端點分配者、摘要者、摘要驗證器）。
- **核心對任務的前置條件**（違反＝誤用）：跟 daemon 同 uid、environ 可讀、保留 `AOS7_*`、不換 session 又不可讀（§11）；交付物寫槽外；改 `tasks.json` 用 `edit_json`／拿鎖；只碰給的資料夾（S-10，合作式）；要控制別人寫 ctl 檔，不直接 kill。
- **核心對任務的保證**：環境變數齊、cwd＝node、`PATH` 有 `bin/`；同槽上一次的 state 讀得到；每回合結束有 `tock.json`（可能漏、只留最新）；kill 範圍是 Q1；keep 重起前舊的已收掉（管理範圍內）。
- **明確不管**：任務邏輯錯；任務之間的協定（kernel↔agent 的格式、grant、帳）——那是 kernel 層契約，錯歸 kernel 層，不歸 daemon／tick；`usage.json` 只是取樣下界（§8）；故意脫離身分。

### 2.9 人／外部程式

- **職責**：寫給人寫的檔（§1 表）、`register`、`timeline.json`、照 §12 修復停點；工具 `aos7-ctl`／`aos7-wait-tock` 只是替你寫檔／輪詢，LLM 直接讀寫檔一樣做得到（S-01）。
- **對核心的前置條件**：只寫合法輸入；修核心內部檔前先 pause、保存證據（§12 通則）；不把 node、生命週期檔換成符號連結／FIFO／資料夾；工具 bug 歸工具（A2-13、A3-06），不動 daemon。
- **核心保證**：所有狀態 `cat` 看得懂（S-01）；每件控制有回條；停下等人的情況都有證據與恢復步驟（§12）。

## 3. 錯誤分類

四類，判準與統一處理分支：

| 類 | 判準 | 誰處理 | 怎麼呈現給人 | 回歸測試 |
|---|---|---|---|---|
| **M 誤用** | 某方違反了被害組件的前置條件（§1 表、各卡「前置條件」） | 違反的那一方：核心組件違反＝那個組件的 B；任務／人／工具違反＝不修核心，寫進「明確不管」 | 文件界線；核心碰巧偵測到就記 `last_error`／`errors`，**不保證、不加新檢查** | 可以留案例，標 `misuse`，失敗不算 bug |
| **X 外部故障** | 程序被殺、I/O 錯、/proc 讀不到、權限暫時變了；前置條件成立 | 被害組件走**同一條「不知道」分支**：保留現狀、記 `kind`、退避、下一圈再看（spec §0 三態） | status `last_error`／`uncertain`、總結 `errors`、§12 表 | 故障注入矩陣，每案斷言注入命中 ≥1 |
| **B 組件 bug** | 前置條件成立、保證沒兌現（含：X 發生時沒走「不知道」分支而做了破壞性動作） | 擁有該保證的組件；修在四個判定入口之一，不在呼叫處各補一次 | 修＋problems.md 一列 | 固定回歸案例 |
| **G 契約缺口** | 翻遍契約卡找不到對應的前置條件或保證 | 先補卡（Fable／astra），再重新分類成 M／X／B | 本檔更新一行 | 補卡後才寫測試 |

```mermaid
flowchart TD
  A[現象] --> B{哪個組件的保證沒兌現？}
  B -- 找不到對應保證 --> G[G 契約缺口：先補卡]
  B -- 找到 --> C{那個組件的前置條件都成立？}
  C -- 否 --> D{違反者是核心組件？}
  D -- 是 --> B2[歸違反者：它的 B]
  D -- 否（任務／人／工具） --> M[M 誤用：寫界線，不修核心]
  C -- 是 --> E{有外部故障？被殺／I-O 錯／proc 讀不到}
  E -- 否 --> Bb[B：修擁有保證的組件]
  E -- 是 --> F{它走了「不知道」分支、沒做破壞性動作？}
  F -- 是 --> X[X：正常保守停下，照 §12 恢復]
  F -- 否 --> Bb
```

歸屬口訣：**誰的保證破了就先看誰；誰違反前置條件就歸誰。** 任務之間的事（kernel 對 agent）在 kernel 層另立契約，不往 daemon／tick 推。

## 4. astra A2／A3 試分類

| 編號 | 歸哪個組件 | 類 | 照藍圖該不該修 |
|---|---|---|---|
| A2-01 /proc 讀不到當沒有 | tick／tock（程序判定入口） | B（X 沒走不知道分支） | 該修，已修 |
| A2-02 round 半寫當已關 | 時間線迴圈＋tick（回合判定入口） | B | 該修，已修 |
| A2-03 birth 半寫使 once 重跑 | tick（槽判定入口） | B（保證「once 不重複」破了） | 該修，已修 |
| A2-04 node 換符號連結寫出 root | daemon（保證「不寫出 root」） | B；「同 inode 連回原處」那半是 M | 該修「不寫出 root」這條，已修；拍板題 3 |
| A2-05 restart 重播兩次 | 控制檔處理 | B | 該修，已修 |
| A2-06 rounds 倒數每 node 一份 | 時間線迴圈（pause owner） | B | 該修，已修 |
| A2-07 SIGKILL 留暫存檔 | tick／tock／daemon 寫檔（fs 入口） | X 的清理，屬「最基礎保護」 | 修成一處 `sweep_tmp` 可以；再長就交清理模組 |
| A2-08 診斷截尾、原因看不到 | 時間線迴圈（status） | B（低） | 該修，已修 |
| A2-09 §8 憑 usage 下降辨重建 | 任務（kernel 通用任務，未實作） | G | 補契約（已改 spec），不是核心 bug |
| A2-10 history max-lines 沒套事件檔 | 模組 | B（模組自己的） | 修模組，不算核心 |
| A2-11 early 回合中 wake 被保留 | 時間線迴圈 | B | 該修，已修 |
| A2-12 history 通知早於總結 | tock（保證「先總結後通知」） | B | 該修，已修 |
| A2-13 CLI 檔名沒含 owner | 人／外部程式（`aos7-ctl`） | B（工具的），對 daemon 是「檔名寫者負責」 | 修工具，已修；不動 daemon |
| A3-01 restart 完成證據隨換 run 消失 | 控制檔處理 | B | 該修，已修 |
| A3-02 environ EACCES 不可 ptrace 雙開 | 任務違反前置「同 uid、environ 可讀」 | **M** | 不修；精簡時把 A3-02 加的特判收回一句「管理範圍外＝不是任務」 |
| A3-03 生命週期檔換 FIFO 繞過保護 | 人違反前置「生命週期檔只有核心寫、是一般檔」 | **M**（非阻塞開 FIFO 防卡住的那半是 X 保護，留） | 不修；精簡時兩套讀檔規則併一套（拍板題 2） |
| A3-04 id 靜默截 64 字 | 控制檔處理 | B | 該修，已修 |
| A3-05 內容＋mtime 不唯一、作用域未定 | 控制檔處理 | G→已補契約；「保留 mtime 複製還原」那半是 M | 補契約與 CLI 產 id，已做 |
| A3-06 owner 編碼互蓋 | 人／外部程式（`aos7-ctl`） | B（工具的） | 修工具，已修；daemon 不管檔名 |
| A3-07 mount 子目錄暫存檔漏清 | tock（sweep 範圍） | X 的清理（低） | 修在同一個 `sweep_tmp` 可以；不遞迴 |
| A3-08 重播通知失敗被吞 | tock（保證「通知失敗不吞」） | B | 該修，已修 |
| A3-09 kill 回成功但任務仍活 | 控制檔處理（回條誠實） | B（由 M 的情境觸發，但回條不能說謊） | 該修，已修 |

小計 22 條：B 15、M 2（A3-02、A3-03；另 A2-04、A3-05 各有一半是 M）、X 清理 2、G 2、模組 1。astra 兩輪的判斷跟藍圖一致處多；差別是本檔把 A3-02／A3-03 直接歸誤用，而 A2-07／A3-07 降為「最基礎保護」裡的清理而非 bug。

## 5. 對精簡與下一輪的建議

1. **精簡以契約卡為刀**：核心程式裡每個檢查都要能指到某張卡的「保證」或「最基礎保護」；指不到的（尤其 A3-02、A3-03 定原則 9 之前加的特判）就收掉或併進四個判定入口。`core-slimming.md` 寫方案時建議每條刪改都標卡號。
2. **判定只留四個入口，呼叫處不再各判一次**：檔（`read_json3`）、回合（`read_round`）、程序（`aos7_proc` 單一入口）、槽（`judge`）。bug 修在入口，回歸矩陣也按入口分軸，而不是按現象累加案例。
3. **回歸報告先分類再報**：astra 下一輪每條新問題先標「組件／類別」（可直接用 §3 的流程圖），M 的放進「界線」節而非 bug 節；矩陣案例檔名或 docstring 標 `misuse`／`fault`／`bug`，M 案例失敗不算紅燈。
4. **任務分類不進核心**：四類任務只在 kernel 任務包的 README 標籤；`tasks.json`、tick 不認 kind。kernel↔agent 的契約另立一張卡（layer-interfaces 03 的事），錯誤歸屬在那裡解，不往 daemon／tick 推。
5. **工具歸人側**：`aos7-ctl`、`aos7-wait-tock` 的 bug 不算核心 bug，也不因工具的問題動 daemon／tick（A2-13、A3-06 兩次都守住了，寫成規則）。

## 6. 要使用者拍板的題目（最多 3 題）

能做成選項的已排除（例如 `retry_lost`、`early_tock`、`min_interval_ms`）。

1. **誤用被核心碰巧偵測到時，要不要「順手記一筆」？** (a) 記進 `last_error`／`errors` 但不保證、不為它加任何新檢查（現狀多數如此）；(b) 完全不管，連既有的順手記錄也不保證維持。**推薦 (a)**：零成本的診斷對 LLM 可讀（S-01）有價值，但要寫明「不保證」，免得下一輪又被當成缺口來補。
2. **「存在但不是一般檔」要不要併成一條規則？** 現在是兩套：生命週期檔＝不知道、其他檔＝不存在（A3-03）。(a) 核心讀的所有檔一律「不是一般檔＝不知道」（少一個分支，合原則 9「同類走同一分支」；控制垃圾會變成留著不處理）；(b) 維持兩套；(c) 一律當不存在（回到 A3-03 前，FIFO 換掉 birth 會雙開，但那是誤用）。**推薦 (a)**。
3. **daemon 對符號連結守到哪？** (a) 守「絕不寫出 root」：登記時與每次開 node 都比 realpath（現狀，A2-04）；(b) 只在登記時檢查，之後把 node 換成符號連結算誤用、不再每圈重驗。**推薦 (a)**：空間邊界是 S-07 的核心保證，而且實作已收在一處（`canonical_node`）；(b) 省的檢查很少。
