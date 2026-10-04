# 跨層的交接：kernel→daemon、agent→daemon、子 daemon↔父時間線、任務↔任務

← [入口](../layer-interfaces.md)｜上一份：[kernel ↔ agent](03-kernel-agent.md)｜下一份：[缺口與風險](05-gaps.md)

這四條都跳過了中間層：任務直接跟 daemon 說話，或任務經由掛載直接碰別的 node。它們全部是**通用**機制，沒有一條只為 agent／LLM。

## 1. kernel → daemon 控制檔（S-18、S-21 路二）

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 |
|---|---|---|---|
| `<root>/.aosd/ctl/<名>.json` | 任何人（kernel、agent、人、`aos7-ctl`）→ daemon | daemon 主迴圈每約 20 ms 一圈，每圈最多 200 件或 0.05 秒 | `{op, node, by, owner?, rounds?, all?, kill?, why?}`；op 是 `register`／`unregister`／`pause`／`resume`／`wake`／`stop` |
| `<root>/.aosd/ctl-done/<同名>.json` | daemon → 請求者 | 處理完 | 原請求加 `result: {ok, msg, at, queued_at}`；**同名蓋掉** |
| `ctl-done/<名>.bad`、`ctl-failed/<名>` | daemon | 壞檔、處理丟例外 | 原物；status 記 `last_ctl_error` |
| `<root>/.aosd/status.json` | daemon → kernel（經掛載）| 每圈覆寫 | 每 node：`round`、`round_open`、`phase`、`paused_by`、`pause_pending`、`live`、`uncertain`、`steps_left`、`last_error`、`last_event` |
| `<root>/.aosd/paused.json` | daemon（唯一寫者）→ daemon 起來時讀 | pause／resume 處理時 | `{"paused": {node: [owner...]}}` |
| 檔名慣例 | 寫的人自己取 | — | 建議 `<by>.<op>.<node>[@<owner>].json`，每段無損編碼；`aos7-ctl` 預設就是 |

**機制**：

- **身分是自己宣稱的**：`by`、`owner` 都是寫的人自己填，daemon 不驗證（合作式，spec 第 11 節）。
- **owner 讓多個控制者各管各的 pause**：`paused.json` 每個 node 一份 owner 清單，清單空了才開回合；`resume` 只拿掉自己的。kernel 一定要帶自己的 owner，否則跟所有不帶 owner 的人共用 `""` 這一格。
- **`resume --rounds N`**：daemon 替你數 N 個「關上的回合」，到了用同一個 owner 再 pause。倒數按 owner 各記一份。
- **回條只表示「接受並改了狀態」**，不表示已經停了；要看 status。回條沒有請求 id，同名的舊回條會被蓋掉。
- **不記完成證據**（任務控制有 `ctl-seen.json`，daemon 控制檔沒有）：daemon 在「改了狀態、還沒刪掉請求」之間死掉，重開後會把留在 `ctl/` 的當新請求再做一次；請求刪不掉（權限壞了）時，`aos7_daemon.py` 的 `ctl_one` 把刪除失敗吞掉，同一份請求**每一圈**都會再做一次。pause、wake 重做無害；`resume --rounds N` 每做一次就把倒數重設（讀碼推論，沒實測）。
- **怎麼寫得到 `.aosd/`**：任務有 `AOS7_ROOT`，直接寫得到；要合 S-10 就把 `.aosd`（或 `.aosd/ctl`）掛進來，`aos7-ctl daemon <掛載點>` 也認得。預設 `mount_allow` 是整個空間根，所以任何任務都能請求掛 `.aosd`。

**影響**：

- **pause 是「不開新回合」，不是「停任務」**：被 pause 的 node 上任務照跑，但收不到 tock、`ctl.json` 不執行、mount-req 不審。一個靠 tock 過日子的任務（kernel、agent、counter 範例）會停在原地；`wait_tock` 不設逾時就永遠等。
- **pause 生效要等本回合收完**：固定 interval 下最多一個 interval（實測 2 秒 interval 約 2.0 秒）。
- **kernel pause 自己的 node 會鎖死自己**（K-5），控制成環照 S-22 不管。
- **register 讓 kernel 可以長出新 node**：下一圈就開時間線；資料夾還不在也接受，出現時才開。
- **unregister 預設會 kill 那個 node 上的任務**（W2）。

**延遲**：收件約 20 ms；pause 到本回合結束；wake／resume（變成沒人 pause）約 20 ms 開新回合；register 下一圈開時間線。

## 2. agent → daemon

跟 kernel 用的是同一個控制檔通道，沒有 agent 專用的東西。兩種情形：

- **agent 當操作者**：proto7-1 的 llmkernel、llmops、selfprog、llmteam 探針讓 LLM 只靠讀寫檔來操作 daemon（S-01）。proto7-2 對 LLM 友善的改動：回條同名蓋掉、壞檔也有回條、status 有 `paused_by` 清單。仍要注意：**直接改 `paused.json` 不會生效**——daemon 只在起來時讀它，之後由自己整份覆寫（`aos7_daemon.py:112-136`），但 spec 第 0 節第 13 行把 paused.json 列成「多人讀—改—寫、要拿鎖」的檔，寫法含糊（G9）。
- **agent 寄信後叫醒對方**：寫完對方 inbox 再寫一個 `wake`，對方的 node 約 20 ms 開新回合，比等對方的 interval 快很多。這是通用的「事件喚醒」做法（N-83 的簡化版），任何寫信的任務都能用。

## 3. 子 daemon ↔ 父時間線（S-21 路一）

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 |
|---|---|---|---|
| tasks.json 項目的 `subroot`、`allow_stop` | 人／kernel → 父 node 的 tick | 起任務時檢查：子根要在自己 node 底下、不能包住父 daemon 已登記的 node | 字串路徑、bool |
| 環境 `AOS7_SUBROOT`、`AOS7_OWNER_NODE`、`AOS7_OWNER_TID`、`AOS7_ALLOW_STOP` | 父的 tick → 子 daemon | 起任務時 | 子 daemon 拿到 `daemon.lock` 後照它們寫 owner.json，再從自己環境拿掉三個 OWNER 變數 |
| `<subroot>/.aosd/owner.json` | 子 daemon 寫 → 子 daemon 處理 `stop` 時讀 | 每次拿到鎖 | `{owner: {node, tid, allow_stop}, daemon: {pid, since}}` |
| `<subroot>/.aosd/stopped.json` | 子 daemon（允許的 stop）→ 父的 tick | stop 前 | 有它、或子根的 `daemon.lock` 有人拿著、或同一個 tick 已有別項認領 → 父不起，記 `tasks_error` |
| `<subroot>/.aosd/ctl/` 的 `register` | 起子 daemon 的任務 → 子 daemon | 子 daemon 起來前後都行 | 子 daemon 起來時 nodes.json 是空的，要靠這個 |
| SIGTERM | 父的 kill／restart／node 消失 → 子 daemon | 父的 tick／tock 或 daemon | 子 daemon 當成 `stop` 加 `kill: true` |

**機制**：daemon 核心不知道從屬；子 daemon 對父時間線就是一個普通任務（status 只看到一個 `sd#3` 這樣的 run id），子 daemon 的 status 父看不到（N-14 沒做）。子 daemon 的 tick／tock 程序從子 daemon 繼承了父任務的 `AOS7_NODE`／`AOS7_TID`／`AOS7_RUN`，所以父的身分掃描收得到它們；但**子 daemon 起的任務**會被重設成子 node 的身分，而且各自在新 session 裡，父的 kill 範圍蓋不到它們。

**影響**：

- **父 node 被 pause，子 daemon 照跑**：pause 不停任務，所以子空間裡的回合繼續開。要停整個子空間得 kill 那個任務，或對子 daemon 下 stop（要 `allow_stop: true`）。
- **父 kill 子 daemon 時，子的任務可能變孤兒（已實驗）**：父的 kill 給 1 秒寬限就 SIGKILL；子 daemon 收到 SIGTERM 後要逐槽收自己的任務，每槽也是最多 1 秒。子任務不理 SIGTERM 時，子 daemon 在收完之前就被 SIGKILL。實驗裡子 node 有兩個不理 SIGTERM 的 keep 任務，父表拿掉子 daemon 那項、再下 kill：子 daemon 死了，兩個子任務留下來沒人管。父表上那項如果還在，下一個 tick 會起新的子 daemon，新的子 daemon 從槽檔認出它們還活著，不會雙開——所以真正會漏的是「父不再要這個子空間」的情況。
- **子 daemon 自己掛掉**：父的 keep 下一個 tick 起新的（子根有 stopped.json 就不起）；子的回合數接著數。
- **兩邊的回合各數各的**：子空間的回合跟父的回合沒有對應關係，跨線比先後只能靠「我看到你的第幾回合」這種紀錄（事實傳遞筆記待定點 4）。
- **掛載跨不過去**：掛載的路徑要在**同一個空間根**內，子空間的任務掛不到父空間的資料夾（綜合筆記「跨空間信箱：缺」）。

## 4. 任務 ↔ 任務，經掛載（S-23）

| 交接點 | 誰寫 → 誰讀 | 時機 | 格式 |
|---|---|---|---|
| tasks.json 的 `mounts` 宣告 | 人／kernel → tick | 每次起新 run 重建 `mnt/` | `{名字: 空間路徑}`；名字不能有 `/`、不能 `.` 開頭 |
| `mnt/<名字>` | tick 建相對符號連結 → 任務 | 起 run 時 | 目標不在先建成資料夾 |
| `mount-req/` → `mount-done/` | 任務 ↔ 下一個 tick | 執行中加掛 | 見 [02](02-ticktock-task.md)；被拒的回條留著，同名不再自動重請 |
| `mount_allow` | tasks.json 頂層 → tick | 審加掛時 | 空間路徑前綴清單，比 realpath；沒寫＝全給 |
| 別人資料夾裡的檔（inbox、`.aos/last-round.json`、`.aosd/status.json`…） | 一方寫 → 另一方讀 | 任何時候 | 原子寫；格式是兩邊的約定 |

**機制與影響**：

- **掛載只是把路徑接過來，不是權限**：沒有 FUSE，任務照樣可以用 `AOS7_ROOT` 繞過去（合作式）。`mount_allow` 寫在 tasks.json 裡，而 tasks.json 任務自己也改得到。
- **沒有通知**：寫進別人的 inbox，對方要等自己的下一個 tock 才會看（或寫的人另外下 `wake`）。
- **只看得到「上一次」**：讀別的 node 的 `last-round.json` 是取樣，對方一回合跑得比你快就會漏；要完整的用歷史 module。
- **掛到別人的槽裡很危險**：槽會被 tock 刪掉（名字離開表、結束報過再一回合），掛載目標跟著消失。收件夾、交付物要放在 node 層（`inbox/`、`outbox/`），不要放在槽裡（W7）。
- **寫入沒有鎖的約定**：核心只保證自己寫的是原子 rename；兩個任務同時讀—改—寫同一個檔，要自己約定（例如照 spec 第 0 節對 `<檔>.lock` 拿 flock）。
- **延遲**：宣告的掛載在起 run 時就有；執行中加掛等下一個 tick；keep 任務換 run 時執行中加掛的會消失，要重請一次。
