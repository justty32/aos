# git：開格、存檔點、收尾

← [通用 tick 核心](../tick.md)｜[tick 子篇入口](README.md)｜格式：[tick 協議](../protocol/tick.md)

**狀態：待實作。`aos-git` 三項還沒有程式。主體不依賴暫緩區；只有「在不在 tick 內」的核對與巢狀排除的判準要等暫緩區（B-622）。**條號不變，2026-10-01 從 [tick.md](../tick.md) 拆出；節的順序改成先講有 git 時怎麼做（B-630）、共同規則（B-622），最後才是沒有 git（B-632）。

## B-630：git：開格、存檔點、收尾

〔使用者方向 2026-09-30，第二十批追答 8、疑點裁定 3、5；納入 cgroup 與 git 疑點裁定；aos-git 分工〕git 做成三個系統級任務：`aos-git open`、`aos-git mark`、`aos-git close`（argv、代碼與結束碼見 [P-205](../protocol/tick.md)）。範本怎麼排見 B-629；共同規則（能不能用、呼叫參數、固定排除、故障）見 B-622。

**有 git 才用**：沒掛這三項，或 git 不能用，照 B-632。核心不認得 git，其他系統級任務也不認得（B-632）。

### 管什麼：只管 aos 自己的東西

**提交與還原只限 aos 自己的東西**〔使用者方向 2026-09-30，aos-git 分工〕。叫它「aos 範圍」：

| 東西 | 在不在 aos 範圍 |
|---|---|
| 狀態資料夾（預設 `.aos/`）底下追蹤的檔：任務表、inst、`.aos/mq/post/`、`summary.json` 等 | 在 |
| 系統級任務動到的檔 | 在。怎麼認〔使用者 2026-09-30 同意照暫定〕：兩個相鄰存檔點之間的項**全是** `kind:"system"` 時，這一段的所有改動都算 |
| 任務呼叫 `aos-git mark <路徑…>` 帶的路徑 | 在，從那個存檔點起到本格結束〔使用者 2026-09-30 同意照暫定〕 |
| 使用者任務改的其他檔 | 不在：aos 不提交、不還原 |
| 核心檔（B-622 固定排除） | 永遠不在 |

- **`AOS_DIRNAME` 是空字串時，aos 範圍＝整個工作資料夾**〔使用者 2026-10-01，原話「不用特別弄清單，就全部」；回答 astra 報告要使用者裁定 1〕：這時狀態資料夾就是工作資料夾本身（[C-09](../conventions.md)），上表第一列「狀態資料夾底下追蹤的檔」就是整個資料夾裡 git 追蹤的檔，不另列 aos 自有檔的清單。上表「使用者任務改的其他檔：不在」這列這時不成立。
- **所以空字串時使用者自己的檔也會被提交、還原**〔使用者 2026-10-01〕：close 把整個資料夾剩下的改動一起提交；組失敗時，存檔點把那組改過的路徑（含使用者的檔）還原；上一格沒正常收尾時，open 把整個資料夾追蹤的檔還原到 HEAD。固定排除與 ignore 的檔照舊不碰（B-622「範圍怎麼切」）。
- **保證**：aos 只保證自己的東西——`kind:"system"` 任務與 tick／daemon 基底——是原子的。tick 本身不保證整格原子。
- **使用者任務要存檔**：自己在任務表加 `aos-git mark` 項，或在程式裡呼叫、帶上自己的路徑；範本不替它們插存檔點。
- `kind` 怎麼查〔使用者 2026-09-30 同意照暫定〕：`aos-git` 照結束碼紀錄裡的 `id` 去本格的任務表查；查不到的當成不是系統級任務。任務表只有一個位置：`$AOS_TICK_CWD/<狀態資料夾>/tasks.json`（預設 `.aos/tasks.json`，`AOS_DIRNAME` 空字串時是 `tasks.json`；[B-620](../tick.md#b-620任務註冊表照表依序跑)），照 B-620 讀表時那一層解到每一項再看 `kind`（`kind` 不是頂層預設）。〔使用者 2026-10-01：目標不能給檔，所以 astra 報告設計 2「自訂表沒辦法交給 aos-git」不成立，結案〕

### 組與存檔點

- **存檔點**＝`aos-git mark` 這一項，把此刻的 aos 範圍存成暫存提交，記在 `refs/aos/marks/<本項 id>`（取 `AOS_TASK_ID`）。不動分支、HEAD 與正式 index。`aos-git open` 也打一個。
- **組**＝相鄰兩個存檔點之間的各項；最後一組是最後一個存檔點到 `aos-git close` 之間。組內每項 `exit:0` 才算成功；〔2026-10-01〕原本的「被 `aos-needs` 擋下的（`exit:125`）也算失敗」隨 `aos-needs` 改寫成 `aos-tick-check-task` 失效：它沒跑好時建停格檔，這格作廢、close 不跑（見下面停格檔那列，[B-621](check-task.md)）。
- **失敗就當場還原**（疑-2）：存檔點發現剛結束那組有失敗，就把那組改過的 aos 範圍路徑（含新增、刪除）還原到**往前最近的存檔點**〔使用者 2026-09-30 同意照暫定：不分範本放的或任務自己打的〕，再打點。所以後面的組看不到失敗組寫的東西，close 只要提交。
- 存檔點只看結束碼紀錄與已打的存檔點；不看 argv，也不管任務在格內改了表。
- 存檔點各占一項（疑-12），不另設包裝寫法。

### 開格 `aos-git open`

1. **看 git 能不能用**（B-622）。不能用就印 `no_git` 警告、回 0，這格照 B-632。
2. **上一格沒正常收尾就還原**：`last.json` 是 `ended:false`、有 `stopped_after`（B-633），都算沒正常收尾。還原範圍是 `.aos/`（`AOS_DIRNAME` 空字串時就是整個工作資料夾），加上上一格留下的存檔點記的 aos 範圍，一律回到 HEAD。上一格正常收尾，或沒有 `last.json`，不還原。
3. **清殘留**：上一格留下的 `refs/aos/marks/*` 清掉。〔建議預設〕上一格是當機（`ended:false`）時，一併清掉 git 管理目錄裡 aos 自己可能留下的鎖檔（`index.lock`、`HEAD.lock`、`refs/**/*.lock`）。
4. HEAD 不在上一格提交時的那個分支上（任務自己換了 HEAD 或分支）：不碰工作樹，當故障（B-622）。
5. **巢狀排除**（B-622），再打本格第一個存檔點 `refs/aos/marks/<本項 id>`。

### 收尾 `aos-git close`

1. 照存檔點的做法處理最後一組：成功就留、失敗就還原。
2. 巢狀排除再掃一次。
3. **提交**：aos 範圍剩下的改動 commit 一次，訊息 `aos-tick <seq>`（`seq` 見 B-633）；沒變動就不 commit，所以每格最多一個。〔建議預設〕訊息另加一行 `aos-failed: <存檔點 id…>`，列出失敗的組，只給人看。
4. 刪掉本格的存檔點，回 0。

close 排在 `mq-post` 前面（B-629；發摘要 2026-10-01 搬暫緩區）：它失敗會建停格檔，後面的項不開，保住「先提交再送」（B-624）。

### 跟停格檔、擋板檔、當機怎麼互動

| 情況 | 會怎樣 |
|---|---|
| 上一格正常收尾 | 不還原 |
| 上一格當機（`ended:false`） | open 把 aos 範圍還原到 HEAD；那格的改動作廢 |
| 本格某項建停格檔（疑-1） | close 不跑、不提交；下一格 open 還原。**這格作廢**，前面已成功的組也一起丟（B-620） |
| `mq-get` 這格取出的訊息 | 這格作廢時一起被還原，等於丟了（B-623） |
| `aos-git` 自己故障 | 寫擋板、建停格檔：這格作廢，之後各格被擋，要人處理（B-622） |
| 有擋板 | 核心一項都不跑（B-620），`aos-git` 不另外看擋板 |
| 格間人手改 aos 範圍 | 見 [B-602](../tick.md#b-602同一資料夾一次一格互斥鎖)「tick 外的寫入者」 |

### 其他〔建議預設〕

- **還原時還有人在寫**：沒包 `aos-cg` 的任務留下的程序，要等格後才被 daemon 收掉，還原之後可能又寫回來。只有包了 `aos-cg` 而且 daemon 有 cgroup，才保證還原時那一項已經沒人在寫（B-634）。
- **成本**：每個存檔點都掃一遍 aos 範圍；實作用 stat 快取（先複製正式 index 再加，不必每次重算整樹 hash）。
- **多帳號**：`aos-as` 開的程序寫進 aos 範圍的檔，要讓 tick 帳號讀得到（例如 [B-609](../deferred/daemon/helper-actions.md) 的共享群組），否則 git 讀不到，當故障。

依據：第二十批追答 8（git 做成任務表上的任務；tick 不再保證整格原子）、疑點裁定 3（每組跑完打存檔點）、4（送出在 git 收尾之後）、5（git 與無 git 合成一種模式）；納入 cgroup 與 git 疑-1（停格＝本格作廢）、疑-2（存檔點當場還原）、疑-4（下游不認得 git，拿掉草稿的「開格刪收件原件」「只送 HEAD 裡的」）、疑-12（存檔點獨立一項）；aos-git 分工（開格與收尾管 tick／daemon 基底與系統級任務；提交與還原只限 aos 自己的東西；失敗還原到往前最近的存檔點，暫定）；使用者 2026-10-01（`AOS_DIRNAME` 空字串時管整個工作資料夾；任務表只有一個位置）。

**驗收：**`AOS_DIRNAME` 空字串時，使用者任務那組失敗，它改的使用者檔也被存檔點還原；close 的 commit 含使用者檔的改動。有 git 版範本裡，使用者任務那組有一項失敗：它寫進 `.aos/mq/post/` 的訊息在 `mark-user` 被還原、不送，它改的 `state/` 檔留著、不被提交；清理成功、那格一個 commit `aos-tick <seq>`，含清理的變動。某項建停格檔：close 沒跑、沒有 commit，下一格 open 把 `.aos/` 還原到 HEAD。上一格 close 後 `mq-post` 途中當機：已提交的都在。任務 id 以 `.lock` 結尾的存檔點：`mark_id_invalid`、擋板＋停格檔。

## B-622：git 的共同規則

〔使用者方向 2026-09-29；第十八批（落盤）；納入 cgroup 與 git 疑點裁定〕`aos-git` 三項共用。每個工作資料夾是一個 git repo〔使用者 2026-10-01：node 改稱工作資料夾〕；不用帳本或 SQLite。

### 能不能用

- **能用**＝git ≥ 2.36、`git rev-parse --absolute-git-dir` 成功、HEAD 讀得到（還沒有任何 commit 也算，由第一次 close 建第一個）。
- **不能用**（沒裝、太舊、不是 repo、repo 壞到讀不了 HEAD）：open、mark、close 都只在 stderr 印一行 `no_git: <原因>` 警告、回 0，這格照 B-632 做；**不寫擋板**。〔使用者方向 2026-09-30，疑-5「噴警告」；記錄者理解：一律照沒 git 的做法繼續〕
- git 之後又能用了：那一格照常，close 把累積在 aos 範圍的改動一次提交。
- 「不能用」只看上面這幾項開頭的檢查；檢查過了、做到一半才失敗的（還原、commit 失敗），算下面的「故障」。

### 呼叫 git

aos 自己呼叫 git 時一律帶：

| 參數 | 為什麼 |
|---|---|
| `-c core.fsync=committed,reference` | 落盤〔第十八批〕。存檔點只在本格有用，當機後 open 一律還原到 HEAD，所以存檔點改帶 `core.fsync=none`〔建議預設〕 |
| `-c gc.auto=0 -c maintenance.auto=false` | 不讓 aos 自己那幾次呼叫觸發背景整理；背景程序違反「不准背景程序繞過 tick」〔使用者方向 2026-09-30〕 |
| 〔建議預設〕`-c core.hooksPath=/dev/null`、`-c commit.gpgSign=false`、`-c safe.directory=<工作資料夾>` | 不跑 hooks；使用者全域開了簽章也不會卡住；工作資料夾的擁有者跟 tick 帳號不同時（[B-203](../../base/execution.md) 的兩種主人）git 仍肯動 |

- **不動使用者的設定**：上面都是命令列參數，只管 aos 自己那幾次呼叫。git 的背景整理（gc、maintenance）aos 不管；文件建議使用者自己關掉（例如 `git config gc.auto 0`、`git config maintenance.auto false`），要整理就先暫停這個工作資料夾的排程（經 daemon 跑的用 `aos-ctl pause`，[B-641](../daemon/control.md)）再手動跑。
- **環境**〔建議預設〕：呼叫前清掉所有繼承的 `GIT_*`，只設自己要的，免得操作到別的 repo。
- **作者**〔建議預設〕：用 repo 設定；repo 與全域都沒設時用 `aos <aos@localhost>`，不擋。
- **不在 tick 內**：沒有繼承到鎖時回 125、印 `not_in_tick`；人手要提交就直接用 git。這個核對靠「鎖 fd 傳給任務」，那段在[暫緩區](../deferred/tick.md#暫緩b-602-完整互斥的其餘細節)；最簡鎖不傳 fd，回來之前這條核對還沒有判法。

### 範圍怎麼切

- **固定排除**：不管 `.gitignore` 寫了什麼，[P-200](../protocol/tick.md) 表裡 ignore 的核心檔一律不提交、不還原：`.aos/tick.lock`、`.aos/tick/`、`.aos/tick-blocked`、`.aos/jobs/`、`.aos/attention/`、`.aos/runner-stderr.log`、`.aos/summary/published.json`、`.aos/mq/failed/`、`requests/`、`responses/`、`work/`。否則 `.gitignore` 漏列時，結束碼紀錄會被還原、`seq` 倒退。
- **`AOS_DIRNAME` 換名或是空字串時**〔使用者 2026-10-01〕：上面帶 `.aos/` 的各項換成狀態資料夾的名字；空字串時去掉前綴，直接在工作資料夾頂層排除 `tick.lock`、`tick/`、`tick-blocked`、`jobs/`、`attention/`、`runner-stderr.log`、`summary/published.json`、`mq/failed/`，連同 `requests/`、`responses/`、`work/`。這些以外、git 追蹤的檔全在 aos 範圍（B-630）。〔建議預設〕使用者自己的檔剛好叫這些名字時也一起被排除，不提交、不還原，風險自負。
- **巢狀**：下層 tick 的資料夾（判準照 [B-628](../deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)；那條在暫緩區，回來前沒有正式判準）寫進 git 管理目錄的 `info/exclude`，不改 `.gitignore`。open、mark、close 存之前都重掃一次，免得格中新建的下層資料夾被上層提交（已追蹤的檔不會因為之後才排除就不追）。下層資料夾自己是 repo 時不進去。
- **不遍歷**：不用全樹 `git clean -x`，不進 git 管理目錄或子 repo。

### 故障

還原、存檔點、commit 失敗，HEAD 被換（B-630 open 第 4 步），任務 `id` 當不了 ref 名（`mark_id_invalid`，例如以 `.lock` 結尾），在 tick 內卻沒有結束碼紀錄（`record_missing`）：

1. 寫擋板檔、建停格檔、回 1；
2. 之後各格：現行 daemon 照常叫，由 `aos-tick` 自己看到擋板、一項都不跑（[B-620](../tick.md#b-620任務註冊表照表依序跑)）；舊 daemon 照 [B-607](../deferred/daemon/registration.md) 不再開格（在暫緩區）。錯誤摘要走[待處理事項](../../scheduling/operations.md)；
3. 修復者（經 daemon 跑的先 `aos-ctl pause`）持鎖、核對、自己提交修好的改動，再移除擋板。〔astra 報告必修 1〕

### 其他

- **原子**只指同一 repo 裡 aos 範圍的已提交版本與恢復基線；使用者任務自己的檔、ignored 檔、另一個 repo、外部 workspace 與不可逆後果，都不會跟著還原。
- 〔使用者方向 2026-09-29〕別濫用 git：沒變動不 commit；可定期合併提交、可用 submodule。合併提交要暫停、持鎖；submodule 不承諾跨 repo 的組原子性。

依據：使用者方向 2026-09-29（每個 node 一個 repo、別濫用 git）；第十八批第 17 條、Q31（落盤）；納入 cgroup 與 git 疑-5（不能用就警告、照沒 git 做）；同日裁定（背景整理 aos 不管，自己呼叫時帶 `gc.auto=0`、`maintenance.auto=false`）。

**驗收：**`.gitignore` 拿掉 `/.aos/tick/` 後 `seq` 仍連續、紀錄不進 commit；格中用 `aos node new` 建的下層資料夾不進上層的 commit；格結束後沒有 aos 自己叫起來的 git 背景程序留下；工作資料夾的擁有者跟 tick 帳號不同時照常提交；`AOS_DIRNAME` 空字串時使用者任務改的檔也進 commit、`tick.lock` 與 `tick/` 不進；使用者全域開了 commit 簽章也照常提交；滿碟時 commit 失敗：擋板＋停格檔，`mq-post` 不跑。

## B-632：結束碼紀錄取代日誌：沒有 git 時怎麼做

git 與無 git 合成同一種模式：**核心的結束碼紀錄（B-633）直接取代日誌。** 第十九批的 `.aos/journal/`（完成紀錄、`sent/`、`discarded/`）與換回 git 的 `aos-tick adopt` 都撤。

本條管「沒有 git」：任務表沒掛 `aos-git`，或掛了但 git 不能用（`aos-git` 印 `no_git` 警告、回 0，B-622）。這時沒有「已提交」這回事：

| 下游 | 沒有 git 時怎麼做 |
|---|---|
| 佇列送出 | `mq-post` 送 `.aos/mq/post/` 裡所有的訊息（B-624） |
| 保留期起點 | 從 `aos-clean` 記下的格數算（[B-404](../../base/storage.md)） |
| 檔案收件原件 | aos 不管（B-623） |

〔記錄者理解〕所以沒有 git 時：失敗任務與當機時寫到一半的改動都留在資料夾裡；失敗任務寫出的訊息也會送；沒有歷史與一致快照，只能讀目前的檔案。

**下游不認得 git**：`aos-mq`、`aos-clean` 在有 git、沒 git 時跑同一份程式；git 只活在 `aos-git` 三項裡（B-630）。有 git 時多出的保證全靠範本的順序（B-629）。

依據：第二十批追答 8、疑點裁定 5（取代第十九批「git 提交的備援：檔案日誌」）；astra 審整理區同日定案（收送改成系統訊息佇列）；納入 cgroup 與 git 疑-4（下游不認得 git）、疑-5（git 不能用照本條）。

**驗收：**沒有 git 的機器上，兩版範本任務表都照常跑完、每格都有結束碼紀錄；上一格被殺時下一格的 `last.json` 是 `ended:false`。git 沒裝、低於 2.36、不是 repo、repo 壞到讀不了 HEAD 時，`aos-git` 三項都印 `no_git` 警告、回 0、不寫擋板。
