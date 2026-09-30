# 通用 tick：核心與標準任務表範本

← [整理區](README.md)｜[名詞](terms.md)｜[daemon](daemon/README.md)｜[helper 與 aos-as](helper.md)｜格式：[node 協議](protocol/node.md)

依據：[09-29 新架構](../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../notes/verdicts/11-tick-as-unit.md)。下文「任務表」指 node 裡的任務註冊表 `.aos/tasks.json`，跟 daemon 的登記表是兩回事（[T-02](../terms.md)）。

## 先講重點

- **tick 是一個定期被執行的程式**（`aos-tick`）。誰來跑都行：daemon、cron、人手（B-627）。它執行時的目前目錄（cwd）就是它的**管轄區**。
- **tick 是整個 aos 的衡量基準**：排程以格計，反應最快是下一格；aos 內部的時長與起算點都用本 node 的格數（B-633、[C-01](../contracts.md)）。
- tick 不跟 once、LLM 嘗試、agent 一輪這些計算單位共用外殼（[T-07](terms.md)）。
- **git 與 cgroup 是「有就用」，不是前提。** 沒有 git、沒有 cgroup 時照原來的做法跑（B-632、[B-601](daemon/runtime.md)）。
  - **git**：掛了 `aos-git` 三項系統級任務而且 git 能用，aos 自己的東西（`.aos/`、任務表、系統級任務動到的檔）才有提交與還原（B-630、B-622）。使用者任務改的檔 aos 不提交、不還原。
  - **cgroup**：node 框與資源上限歸 daemon（[B-605](daemon/cgroup.md)）；每項一框要任務包普通程式 `aos-cg`（B-634）。
- **收送只管系統訊息佇列**：node 之間經 daemon 通道互送訊息，由系統級任務 `aos-mq get`／`aos-mq post` 處理（B-623、B-624）。檔案收件區 `requests/`、`responses/` 的收與寫是普通程式的事，aos 不管。
- **保證跟著「掛了什麼」走**：核心四件事（B-626）不靠任何系統級任務也成立；其餘保證看任務表掛了哪幾項系統級任務、任務包了哪些普通程式。〔建議預設，未拍板〕各條只寫「掛了時保證什麼」，沒掛的後果不逐條寫。

依據：第十八批（外殼）；第十九批（定期被執行的程式、管轄區）；第二十批（衡量基準、進行順序；推翻第十九批「本篇的保證以標準配備全掛為前提」與完整／備援兩級）。

## B-626：核心與系統級任務的界線

tick 裡的東西分四類：

| 類 | 是什麼 | 有哪些 |
|---|---|---|
| tick 核心 | `aos-tick` 本身，只做四件事 | 同資料夾互斥鎖（B-602）、照任務表依序跑（B-620）、上下層判定（B-628）、每項結束碼紀錄（B-633） |
| 系統級任務 | 從核心拆出、掛在任務表上的獨立程式，以 `kind:"system"` 標記；**寫在表上才跑，沒寫就不跑** | 系統訊息佇列 `aos-mq`：開頭取件 `aos-mq get`（B-623）、收尾送出 `aos-mq post`（B-624）；發布摘要 `aos-publish`（B-624）；清理 `aos-clean`（[B-404](../base/storage.md)）；git 開格、存檔點與收尾 `aos-git open`／`mark`／`close`（B-630） |
| 普通程式 | 任務會用到的工具，要的任務自己在 argv 包；不是系統級任務 | 切換帳號 `aos-as`（[B-303](helper.md)）、前置沒成功就不跑 `aos-needs`（B-621）、每項一框 `aos-cg`（B-634） |
| 其他任務 | kernel、agent、clock、檔案收件程式、自訂任務等 | 它們的外殼、逾時與取消延後（[P-008](../protocol/README.md#p-008)）；檔案收件 aos 不管（B-623） |

**核心**：照表跑時另外只認兩件事——停格檔，以及任務帶的 `user` 跟 tick 不同（B-620）。核心只要 Python 3.9 與 flock，不靠 daemon、git、cgroup、helper，也不靠任何系統級任務。

**系統級任務**：

- 各自是獨立的程式，彼此只靠檔案（結束碼紀錄、`.aos/mq/post/`）交接，不靠任務 `id` 相認。標準任務表範本就是預設的一組（B-629）。
- `kind:"system"` 的意思是「這一項是系統級任務」。它只是標記：核心不看，也不授予身分或權限；`system` 不開放自訂子名（`system.x`，[T-06](../terms.md)；誰擋見 B-620「誰驗什麼」）。
- 〔建議預設，未拍板〕不檢查 kind 的先後（撤掉第十九批暫定的「system 最前、custom 最後」）：範本的系統級任務分在頭尾兩段，照陣列順序就好。
- `aos-clean` 也是系統級任務，範本裡寫 `kind:"system"`。

**daemon 不在任務表上**：一格結束後殺殘留、重啟、排空停機、helper，都歸 daemon（[B-601](daemon/runtime.md)、[B-603～605](daemon/README.md)、[B-609](daemon/helper-actions.md)）。

**管轄權是約定，不是前提**：tick 對管轄區有最高裁量權，這是 aos 體系裡的約定。Linux 權限上碰不到某些東西時，tick 照樣跑完一格，碰不到的那件照各自規則失敗。管轄區可以重疊，風險自己承擔；aos 體系裡的慣例是不重疊、可以包含（B-628）。

依據：第二十批追答 8、9（推翻第十九批「三層：核心／標準配備／其他掛載」、疑點裁定 1「標準配備跟核心同一支 `aos-tick`、不另做包裝」；`kind:"system"` 取代第十九批「留給以後真正屬於標準配備的任務、範本沒有 system 類」；`aos-clean` 取代第十九批疑點裁定 2「範本裡仍是 custom 類」）；第十九批第 2、5 條（管轄權）；astra 審整理區裁定（收送改成系統訊息佇列 `aos-mq`，檔案收件與投件是普通程式、aos 不管）。

**驗收：**拿掉 daemon、git、cgroup、helper 與所有系統級任務，任務表只放一項 `true`，直接跑 `aos-tick`：互斥、照表跑、上下層判定與結束碼紀錄照常成立；佇列沒人取也沒人送、不發摘要。

## B-602：同一資料夾一次一格：互斥鎖

**同一資料夾同時只能跑一個 tick。** 這把鎖屬核心，不靠 git、cgroup 或 daemon。

### 鎖怎麼取

- **認哪個資料夾**：看資料夾路徑或 inst.json 路徑。給的是 node 資料夾裡的 `.aos/inst.json` 或 `inst.json` 時，一律正規化成那個資料夾（[inst 目標](../base/inst.md#inst-目標檔案或資料夾)）。tick 在這個資料夾裡跑，cwd 就是它；argv 見 [P-203](protocol/node.md)。
- **鎖檔**：`.aos/tick.lock`，ignored，不存在就建立。不放在 git 管理目錄；`aos-clean` 與一般清理都不得移除或替換它，`aos-git` 固定排除它，提交與還原都不碰（B-622）。
- **取鎖**：定位資料夾之後第一件事，對鎖檔取**非阻塞**獨占 flock。拿不到就回 75、什麼都不做（也不寫結束碼紀錄），不在程式內重試。拿到了就整格持鎖。

### 任務與後代

- **任務繼承鎖**：任務繼承同一個 open file description 的鎖 fd，號碼放在環境變數 `AOS_TICK_LOCK_FD`。工具要以 fstat 對上鎖檔、核對是獨占鎖，才算在 tick 內；沒有繼承到鎖就自己取同一把鎖，不能只信環境變數。任務不得解鎖，退出前關掉自己的副本。這是同帳號的合作約定，不是授權。
- **後代也擋下一格**：只要還有任何程序握著這份鎖（例如任務留下的後代），下一格就拿不到鎖、回 75；這一點不需要 cgroup。核心不清後代；daemon 開的格，由 daemon 在格後收尾（[B-604](daemon/lifecycle.md)）。經 `aos-as` 用別的帳號開的程序同樣繼承這份鎖 fd（[B-303](helper.md)）。
- daemon 不同時開同一 node 的兩格，是 daemon 自己的開格安排（[B-601](daemon/runtime.md)），不是互斥的來源。

### tick 外的寫入者

CLI 或工具在 tick 之外自己取鎖改檔，當成外部世界，aos 不管。沒有 git 時，改動就直接留在資料夾裡。

有 git 時，人手改到 aos 範圍（B-630）的東西，aos 也不替它另外做什麼：

| 上一格 | 格間手改的下場 |
|---|---|
| 正常收尾 | 被下一格的 `aos-git close` 跟著提交 |
| 沒正常收尾 | 被下一格的 `aos-git open` 還原掉 |

所以要手改 node：先暫停（[B-607](daemon/registration.md)），改完要保住就自己 `git commit`。aos 不另存救援副本。

依據：第十九批（核心；第 7 條認資料夾）；第二十批（核心不清後代）、疑點裁定 8（取代第十九批建議預設「其他寫入者也須協調這把鎖或先暫停 tick」）；納入 cgroup 與 git 疑-3（人手改的不管、不做救援 ref）。

**驗收：**同資料夾同時跑兩個 `aos-tick`，一個回 75、不改檔；用資料夾路徑與 `.aos/inst.json` 路徑各跑一次，搶的是同一把鎖；前一格留下握著鎖 fd 的後代時，在沒有 cgroup 的機器上下一格也回 75；沒有 git repo 也取得到鎖。

## B-620：任務註冊表：照表依序跑

任務表只放 `.aos/tasks.json`，**陣列位置就是順序**，核心照順序一項一項跑。欄位、JSON 與 schema 以 [P-202](protocol/node.md) 為準，本節只定意思。

### 一格怎麼走

1. 取鎖（B-602），拿不到回 75。
2. 看擋板檔，有就整格不跑、回 1（下面「擋板檔」）。
3. 換一份新的結束碼紀錄（讀任務表之前，B-633）。
4. 讀任務表並驗證，表壞回 2。
5. 照陣列順序跑每一項；開第一項前刪掉上一格留下的停格檔，每項結束後寫紀錄、查停格檔。
6. 回結束碼。

### 任務表

- **資料夾沒有 `.aos/` 時**〔使用者方向 2026-09-30 晚〕：去找 `inst.json`，跟 inst 目標找檔同一套（先 `.aos/`，沒有就 `inst.json`）。
- **`aos-tick` 缺檔時**〔使用者方向 2026-09-30 晚〕：資料夾沒有 `.aos/` 就直接報錯、不自建（回 2、`config_invalid`，不取鎖、不寫紀錄）；有 `.aos/` 但沒有 `tasks.json` 算表壞、回 2。開格驗過表之後到跑到某項重新展開之間，假設檔案不會變，不為這種情況另做設計。
- **每項任務是 inst 的超集**：一份 [inst](../base/inst.md) 加 aos 的欄位（`id`、`kind`、`methods`）。
- **先只定基本欄位**：不認得的鍵照收、核心忽略（任務是 inst 的超集，沿 [P-007](../protocol/README.md)）。第十九批的 `group`、`needs` 不再是欄位，寫了就當陌生鍵：前置改用包裝 `aos-needs`（B-621），組改由存檔點劃分（B-630）。
- **`kind`、`methods` 與其他欄位核心不看**：`kind` 只是標記（B-626）。`methods` 是給檔案收件程式讀的宣告：這一項處理哪些檔案請求 method。〔暫定，第二十批檔案收件 aos 不管〕它的意思、跨項重複怎麼辦，由收件程式定（B-623）。
- **一個 module 一項任務**：產生請求、處理結果都在該項內做；要經佇列送的訊息交給系統級任務 `aos-mq post`（B-624）。檔案收件與投件是任務表上的普通任務，aos 不管（B-623、B-624）。
- 資源 module、`aos-clean`、收信程式都是同一張表上的項目，不分 pre／post 掛勾。有權限者也能直接跑這些程式；在 tick 外跑算外部世界（B-602）。資源 module 的啟用與父層限制見 [scheduling/admission](../scheduling/admission.md)。

### 讀表：核心只驗四件事

開格時讀一次表，只驗：是合法 JSON、`_metainfo` 對、每項（整份 `$ref` 展開後）是合法 inst、`id` 在本表唯一。

**表壞了**就整表拒絕，任務一項也不跑，也不退回舊表；stderr 印 `config_invalid:` 加哪裡錯，tick 回 2。

### 誰驗什麼〔暫定〕

任務表的完整 schema（[P-202](protocol/node.md)）比核心驗的多。分工如下：

| 檢查 | 誰驗、什麼時候 | 不合時 |
|---|---|---|
| 合法 JSON、`_metainfo`、每項是合法 inst、`id` 唯一 | 核心，每格開格 | 整表拒絕、回 2 |
| 其餘 schema 限制：缺 `kind`、`kind` 的值（含 `system.x`）、`methods` 的形狀 | 恢復前驗證（B-625）與建立 node 的工具；核心不驗 | 保持暫停、不 resume；核心照跑 |
| `methods` 的意思、跨項重複 | 檔案收件程式自己（B-623），aos 不管 | 由收件程式定 |
| 不認得的鍵 | 沒人驗 | 照收、核心忽略 |

所以核心看到缺 `kind` 或 `system.x` 的表照跑；要擋，就在改表後、resume 前照 B-625 驗。完整 schema 是給外部工具與恢復前驗證用的。

### 跑每一項

- 前一項結束才開下一項。每項結束後寫進結束碼紀錄（B-633）。
- **成敗**：以可信 wait 的正常退出 0 算成功；exec 失敗、非零、被訊號結束都算失敗。普通程式回 125 不能猜成「沒跑」。
- 「沒事做」可以不改檔、回 0。在途工作存在任務自己的領域狀態裡，不用特殊結束碼當排程訊號。
- 核心在每項的環境多放下面這些變數（格式見 [P-203](protocol/node.md)）。命名規則：整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`。

| 變數 | 內容 |
|---|---|
| `AOS_NODE_DIR` | node id |
| `AOS_TICK_LOCK_FD` | 鎖 fd 的號碼（B-602） |
| `AOS_TICK_RECORD` | 本格結束碼紀錄 `current.json` 的絕對路徑；本格紀錄失效後開的項不設（B-633） |
| `AOS_TASK_ID` | 任務表這一項的 `id` 字串，原樣 |
| `AOS_TASK_INDEX` | 這一項在任務表陣列的位置，從 0 起 |

### 停格檔與擋板檔

任務能影響之後的項或之後的格，只有這兩個檔；**結束碼沒有特別意義**，任務回 3、100 都只是一般的失敗。

| | 停格檔 `.aos/tick/stop` | 擋板檔 `.aos/tick-blocked` |
|---|---|---|
| 擋什麼 | **只擋本格**剩下的項；下一格照常開、照常跑 | 擋住**之後各格** |
| 誰建 | 任務。系統級任務與普通程式要叫停也建它 | 任務（例如發現需要人處理的故障）或人手；`aos-git` 故障時也寫它（B-622） |
| 內容 | 不拘，建議一行 UTF-8 原因 | 一行 UTF-8 原因 |
| 核心什麼時候看 | 每跑完一項就檢查 | 取鎖後第一件事 |
| 核心看到時 | 不開後面的項；紀錄寫 `ended:true` 與 `stopped_after`（在哪一項之後停，[P-213](protocol/node.md)），這格回 1 | 一項都不跑、不寫結束碼紀錄、不加 `seq`、不刪停格檔；stderr 印 `blocked:` 加檔內原因，回 1。所以人手或 cron 直接跑也被擋 |
| 誰刪 | 核心：取鎖後、開第一項前刪掉上一格留下的 | **只有人手**，修好後刪；aos 不自動刪 |
| daemon | 不看它，不因它暫停 node | 有它就不開格（[B-607](daemon/registration.md)） |

- **有 git 時，停格檔等於這格作廢**：排在後面的 `aos-git close` 不跑、不提交，下一格 `aos-git open` 把 aos 範圍還原（B-630）。想提早結束又保住結果的任務，別建停格檔，改讓後面的項讀紀錄自己跳過。〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-1〕

兩個檔都 ignored。使用者裁定的是分工：停格檔靠偵測檔案停掉本格、只在任務層面、daemon 不看、下一格核心開頭刪；擋板檔擋之後的格、有它時 daemon 不開格，本輪就啟用。檔名、內容、stderr 與回 1 等細節是〔建議預設，未拍板〕。

### 任務的帳號

- 任務可以帶 `user`；省略就用 tick 自己的有效帳號。
- 帶了而且跟 tick 的有效帳號不同（名稱先解析成 UID 再比）時，**核心不切帳號**：那一項不跑，照 inst 算 125、不寫 `exit`，stderr 印 `user_mismatch: <id>`，紀錄記 `exit:125`，其餘照表處理。
- 要用別的帳號跑，就在 argv 包普通程式 `aos-as <帳號> -- 原指令`（[B-303](helper.md)）；准不准照該 node 的身分額度核（[B-301](../base/identity-resources.md)）。
- 不另設服務帳號（第九批）；要 root 的固定步驟交給 helper（[B-609](daemon/helper-actions.md)）；管成員的事由上層 kernel 在自己的 tick 用自己的帳號做。任務類別不授予身分或權限。

### 核心的結束碼

`0` 全部成功；`1` 有任務失敗（含回 125 的）、被停格檔停下，或被擋板檔擋住；`2` argv 或任務表不合法（尚未開任務）；`75` 鎖被占。碼表見 [P-203](protocol/node.md)。

- 〔建議預設〕被停下的格回 1：這格沒把表跑完，對呼叫者就是「沒全部成功」。停格檔只管本格，所以不另設一個會讓 daemon 誤當成暫停訊號的碼；要知道是不是被停下，讀紀錄的 `stopped_after`。

依據：使用者方向 2026-09-29；第十七批（`methods`）；第十九批、第二十批改寫（核心）；第二十批（任務表先只定基本欄位、環境變數命名、停格檔與擋板檔並用）；第二十批疑點裁定 1（改：停掉本格靠偵測檔案，不靠結束碼）、6（任務的帳號，取代第十九批「由標準配備的切換使用者開這一項」）、8（tick 外跑算外部世界）。

**驗收：**任務帶 `user` 整份照收；帶了跟 tick 不同的帳號時那一項回 125、紀錄記 125，其餘照表跑；包了 `aos-as` 而且有 helper、有通道時以指定帳號跑，任務內用 `AOS_TICK_LOCK_FD` 核對得到獨占鎖，它結束前下一項不開、同資料夾另一格回 75。某項建立 `.aos/tick/stop` 後，後面的項不跑、紀錄 `ended:true` 並記 `stopped_after`、整格回 1，下一格照常跑；任務回 3 或 100 照一般失敗處理，後面照跑。表裡 `id` 重複時一項都不跑、回 2。

## B-633：每項結束碼紀錄與格數

核心多開放一件事：**本格每一項怎麼結束，寫成一份檔，讓後面的任務讀得到。** 本 node 的**格數**也記在這裡。這份紀錄直接取代第十九批的 git 備援日誌（B-632）：git 與無 git 合成同一種模式。

依據：第二十批追答 8、疑點裁定 5；修正輪暫定的裁定（格數不倒退改成不保證、`--firstdo-fsync`）；納入 cgroup／git 輪疑點 10：使用者 2026-09-30 同意照暫定。以下位置、欄位與寫法都是〔建議預設，未拍板〕；失效一小節是〔暫定，astra 審整理區設-2〕。

### 放哪、記什麼

兩個檔都 ignored：`.aos/tick/current.json`（本格）與 `.aos/tick/last.json`（上一格）。任務環境 `AOS_TICK_RECORD` 是 `current.json` 的絕對路徑。格式見 [P-213](protocol/node.md)。**只有核心寫**，而且只在持鎖時寫。

| 欄位 | 意思 |
|---|---|
| `seq` | 格數（下面） |
| `tasks` | 已跑完的項，照順序；正常結束記 `exit`，被訊號結束記 `signal`；沒跑到的不列 |
| `ended` | 這格跑完、被停格檔停下或表壞時寫成 true，同時加 `exit`＝這格 tick 的結束碼（只會是 0、1、2；75 不寫紀錄） |
| `stopped_after` | 被停格檔停下時，是哪一項跑完後停的；記那一項的 `id` 字串，這時 `exit` 一定是 1 |
| `started_at_ms` | 只給人看，不參與計算 |

### 格數 `seq`

- 本 node 第幾格，從 1 起，每格加 1。
- **跨重啟、換 daemon、改用 cron 都接著數。** aos 內部的時長與起算點都用它數（[C-01](../contracts.md)）。
- **斷電不倒退：預設不保證，開了 `--firstdo-fsync` 才保證**（下面「落盤」）。〔使用者方向 2026-09-30，修正輪暫定的裁定〕沒開時，斷電或 WSL 強關後格數可能退回幾格。依賴格數單調的地方——保留期與清理（[B-404](../base/storage.md)）、摘要的 `observed_seq`、以格數算的起算點（[C-01](../contracts.md)）——同樣不保證，除非開旗標。
- **沒有紀錄的格不佔號**：被擋板擋住的格、鎖被占的格、本格紀錄開不起來的格（下面「失效」），都不加 `seq`。這些格裡沒有任務拿得到 `seq`，所以下一格用同一個號也不會重複。
- 跟 daemon 每筆登記的 `tick_seq` 是兩回事：那個只用在叫醒後等新格，登記換了就重算（[B-607](daemon/registration.md)）。

### 開格：換檔

取鎖之後、讀任務表之前：

1. **算新的 `seq`**：有 `current.json` 就取它的 `seq` 加 1；沒有就取 `last.json` 的加 1；都沒有就是 1。讀不懂的那份當成沒有。
2. **寫新紀錄**（`ended:false`、`tasks:[]`）到暫存檔。
3. **換檔**：有 `current.json` 就 rename 成 `last.json`；沒有 `current.json` 卻有 `last.json`，表示上一格沒留下紀錄，就刪掉 `last.json`，讓讀的人看到「不知道上一格」。
4. 暫存檔 rename 成 `current.json`。

做完第 4 步才開第一項。

### 每項之後

- 整份重寫：寫暫存檔 → rename。
- 跑完、被停格檔停下時寫 `ended:true`；表壞回 2 時寫 `ended:true`、`exit:2`、`tasks:[]`。

### 落盤：`--firstdo-fsync`

〔使用者方向 2026-09-30，修正輪暫定的裁定；旗標名照使用者原話〕**預設不 fsync。** 要格數不倒退，就開旗標：

| | 沒開（預設） | 開了 |
|---|---|---|
| 開格 | 不 fsync | 第 2 步 fsync 暫存檔，第 4 步後 fsync `.aos/tick/` 目錄 |
| 每項之後 | 不 fsync | rename 前 fsync 暫存檔；不 fsync 目錄 |
| 斷電或 VM 強關後 | 紀錄可能退回較早的一版、壞掉或不見；`seq` 可能倒退 | 只要有任務拿到這格的 `seq`，這個號已經落盤，不倒退。`current.json` 可能退回較早的一版，但一定完整；少掉的結果讓下一格看到 `ended:false`，照「上一格沒正常收尾」處理 |

- **怎麼開**：直接跑時帶 `aos-tick --firstdo-fsync`（[P-203](protocol/node.md)）。daemon 帶了 `aos daemon --firstdo-fsync`（使用者原話 `aos-daemon --firstdo-fsync`）時，它開的每一格都照開：daemon 在那一格的環境放 `AOS_TICK_FIRSTDO_FSYNC=1`，`aos-tick` 看到它就等於帶了旗標（[B-601](daemon/runtime.md)）。daemon 碰不到 inst 的 argv，所以用環境變數傳〔使用者 2026-09-30 同意照暫定〕。
- 紀錄壞掉時照下面「失效」的「舊紀錄讀不懂」處理。

### 失效：寫不進時

**本格紀錄失效**＝這一格有任何一次寫紀錄失敗（唯讀資料夾、滿碟、rename 失敗）。

| 什麼時候失敗 | 核心怎麼做 | 下一格看到的 |
|---|---|---|
| 開格（上面 2～4 步） | 刪掉暫存檔；已經有 `current.json` 的，rename 成 `last.json`（rename 不佔新空間）；本格一項都不設 `AOS_TICK_RECORD` | 沒有 `current.json`：照第 3 步刪 `last.json`，上一格算「不知道」；`seq` 從舊 `last.json` 接著數 |
| 跑到中途 | 留著最後一次寫成功的 `current.json`（`ended:false`）不動，本格之後不再寫；之後開的項不設 `AOS_TICK_RECORD` | `last.json` 是 `ended:false`，算沒正常收尾 |

- 兩種都照跑完整張表，stderr 印一次 `record_unwritable`。
- 讀的任務只經 `AOS_TICK_RECORD` 找本格紀錄；沒有這個變數就是「不知道」，不能自己去讀 `.aos/tick/` 裡的殘留檔當本格紀錄。
- 失效後就算空間回來了，本格也不再寫，免得後面的項把一份缺了幾項的紀錄當成完整的。
- **舊紀錄讀不懂**（兩份都壞）：當成開格失敗，兩份檔都不動，stderr 另印 `record_unreadable`，要人手修；修好前每格都沒有紀錄。

### 誰讀

- 任務讀 `current.json` 看本格前面各項，讀 `last.json` 看上一格有沒有正常收尾。
- **正常收尾**＝`ended:true` 而且沒有 `stopped_after`。
- 核心自己除了算 `seq`，不拿它做任何決定。

### 其他

- **被擋板檔擋住的格**不寫紀錄、不加 `seq`（B-620），跟鎖被占一樣當成沒開過格。
- **別刪它**：`.aos/tick/` 不被 `aos-clean` 清；`aos-git` 固定排除它，不靠 `.gitignore`，提交與還原都不碰（B-622）。人手刪掉兩份檔，`seq` 從 1 重數，以格數算的保留期會算錯，風險自負。

**驗收：**有 `.aos/tick-blocked` 時直接跑 `aos-tick` 回 1、stderr 有 `blocked`、沒有任務跑、兩份紀錄與 `seq` 都不變，刪掉擋板後下一格照常；任務第二項讀得到第一項的結束碼；第三項被 SIGKILL 時紀錄是 `signal:9`；tick 在第二項中途被殺，下一格的 `last.json` 是 `ended:false`；同一資料夾連跑十格，`seq` 從 1 到 10，換成 cron 跑仍接著數；帶 `--firstdo-fsync`（或 daemon 帶了旗標）時，第一項開跑後模擬斷電（丟掉沒 fsync 的寫入），重開後下一格的 `seq` 仍比斷電那格大；沒帶時不要求；資料夾唯讀時仍照表跑完、stderr 有 `record_unwritable`、沒有任務拿到 `AOS_TICK_RECORD`；開格時滿碟，下一格的 `last.json` 不存在、`seq` 接著數；第二項後滿碟，第三項沒有 `AOS_TICK_RECORD`，下一格的 `last.json` 是 `ended:false` 且只有前兩項；鎖被占回 75 時兩份紀錄都不變。

## B-628：上下層判定：預設看資料夾包含、可登記覆蓋

每個 tick 都有上層與下層。預設看資料夾，在 daemon 底下可以登記覆蓋。

- **預設上層**：從本 tick 的資料夾往上找，最近一個「有 tick 的資料夾」。〔暫定，計畫疑-10 未答，照 a〕「有 tick」的判準：資料夾裡有 `.aos/inst.json` 或 `inst.json`（[inst 目標](../base/inst.md#inst-目標檔案或資料夾)）。路徑逐段比對，不展開 symlink（沿 [T-03](../terms.md)）。找不到就沒有上層。這是純路徑計算，不靠 daemon。
- **登記覆蓋**：經 daemon 登記時可以指定上層（`parent_id`），蓋過預設。
  - 覆蓋要**新舊兩個上層都同意**。〔建議預設〕舊上層指**目前的有效上層**：第一次覆蓋時是資料夾推得的那個，再次換上層時是目前覆蓋的那個（B-606）。
  - 舊上層沒在 daemon 登記（例如 cron 跑的）時，aos 管不著它，**只要新上層同意**。
  - 覆蓋後**管轄權仍跟著資料夾**，覆蓋只改管理關係：誰分資源、誰叫醒、誰能解除登記。
  - 覆蓋存在 daemon 的登記裡，只在 daemon 底下有；cron 或人手跑的 tick 只看資料夾。登記規則與重啟後怎麼長回來見 [B-606](daemon/registration.md)。
- **有效上層**：有覆蓋就是覆蓋的那個，否則是預設上層。**下層**＝有效上層是我的 tick。
  - 〔建議預設〕daemon 設定列的頂層（root）有效上層是 null，算部署者在設定裡做的覆蓋。它的資料夾上層沒在同一個 daemon 登記時，照上面「只要新上層同意」（這裡沒有上層，由部署者決定）；已在同一個 daemon 登記時，整份設定不收（[B-606](daemon/registration.md)）。
- **換上層有兩條路**（撤第十八批「只有重新登記一條路」）：
  1. **搬資料夾**：搬進別的 tick 的資料夾，新位置最近的那個自動成為預設上層。路徑就是 id，所以等於舊 id 解除、新 id 重登；引用舊路徑的回址會失效，風險自負（T-03）。
  2. **改登記**：用 `parent_id` 覆蓋（B-606）。

  兩條都要被搬的那棵先暫停、程序全空（沿第十八批 Q10）。
- 〔建議預設，未拍板〕**身分繼承**：inst 的 `user` 省略時繼承上層，指的是有效上層（[inst](../base/inst.md)）。
- **巢狀 git**：下層 tick 的資料夾寫進上層 repo 的 `info/exclude`，上層的 `aos-git` 不提交也不還原它們（B-622）。

依據：第十九批第 2、8 條（核心；推翻「上下層看登記、與目錄位置無關」）；第十九批疑點裁定 5、11（登記覆蓋、舊上層沒登記時只要新上層同意）。

**驗收：**`/a` 與 `/a/b` 都有 `.aos/inst.json`、`/a/x` 沒有時，`/a/b` 與 `/a/x/c` 的預設上層都是 `/a`；沒有 daemon 也算得出來。資料夾上層已在 daemon 登記時，只有新上層同意的覆蓋被拒；資料夾上層是 cron 跑、沒在 daemon 登記的，只要新上層同意就收。已覆蓋成 B 再改成 C，要 B 與 C 同意。設定只列 `/a/b` 為頂層、`/a` 由 cron 跑時，daemon 下 `/a/b` 是頂層，直接跑的核心照資料夾仍算出 `/a`。覆蓋後 `/a` 對 `/a/b` 資料夾的管轄不變，叫醒與分資源改由新上層做。

## B-629：標準任務表範本

**標準任務表範本**＝預設的一組系統級任務，加上原本的 kernel／agent 任務。分兩版：

| 版 | 順序 |
|---|---|
| 沒有 git | `mq-get` → 使用者任務 → `mq-post` → 發摘要 → 清理 |
| 有 git | git 開格 → `mq-get` → 存檔點 → 使用者任務 → 存檔點 → 清理 → git 收尾 → `mq-post` → 發摘要 |

### 沒有 git 版

〔建議預設，未拍板；`id`〕

| # | `id` | `kind` | argv | 做什麼 | 正本 |
|---|---|---|---|---|---|
| 1 | `mq-get` | system | `aos-mq get` | 用 `node.take` 取出本 node 佇列裡的訊息；取出後怎麼分派 aos 不管 | B-623 |
| … | 使用者任務 | kernel／agent／custom | 各自的程式；要換帳號的包 `aos-as <帳號> --`，要前置的包 `aos-needs <前置 id…> --`，要每項一框的包 `aos-cg --`。檔案收件、檔案投件也是這裡的普通任務，aos 不管 | 各自 | [B-303](helper.md)、B-621、B-634、B-623、B-624 |
| n-2 | `mq-post` | system | `aos-mq post` | 把 `.aos/mq/post/` 裡的訊息用 `node.send` 送出 | B-624 |
| n-1 | `summary` | system | `aos-publish` | 發布 `published.json` | B-624 |
| n | `clean` | system | `aos-clean --config config/clean.json` | 過了保留期的清理 | [B-404](../base/storage.md) |

### 有 git 版

〔使用者方向 2026-09-30，aos-git 分工；`id` 與第二個存檔點的位置：使用者 2026-09-30 同意照暫定〕

| # | `id` | `kind` | argv | 做什麼 | 正本 |
|---|---|---|---|---|---|
| 1 | `git-open` | system | `aos-git open` | 上一格沒正常收尾就還原；打本格第一個存檔點 | B-630 |
| 2 | `mq-get` | system | `aos-mq get` | 同上 | B-623 |
| 3 | `mark-get` | system | `aos-git mark` | 存下 `mq-get` 這一段 | B-630 |
| … | 使用者任務 | kernel／agent／custom | 同上。要自己的存檔點，就在中間加 `aos-git mark` 項，或在程式裡呼叫 | 各自 | B-630 |
| n-4 | `mark-user` | system | `aos-git mark` | 把使用者任務這一段跟清理隔開 | B-630 |
| n-3 | `clean` | system | 同上 | 移到 git 收尾前，讓清理的變動當格提交 | [B-404](../base/storage.md) |
| n-2 | `git-close` | system | `aos-git close` | 處理最後一段（清理）、提交 | B-630 |
| n-1 | `mq-post` | system | 同上 | 排在提交之後：送的都是已提交的 | B-624 |
| n | `summary` | system | 同上 | 排在提交之後：發的是剛提交的那一版 | B-624 |

- **存檔點各占一項**，不另設包裝寫法（納入 cgroup 與 git 疑-12）。系統級任務之間的存檔點由範本自帶；其他 kind 的任務範本不替它們插，要就自己加（B-630）。
- 〔使用者 2026-09-30 同意照暫定〕使用者給的順序是「使用者任務 → 清理 → 存檔點 → git 收尾」。這裡把第二個存檔點移到清理**之前**：git 收尾本來就會處理最後一段，放在清理前才能讓清理自成一段，被認成「系統級任務動到的檔」（B-630），清理失敗也不會連帶還原使用者任務那段寫的訊息。存檔點總數不變。

### 共通

- **範本只是預設**（[T-10](terms.md)）：任務表可以拿掉任何一項，拿掉了那一項的保證就沒有。例如沒掛 `mq-get`，佇列裡的訊息就沒人取；沒掛 `mq-post`，要送的訊息就一直留著；沒掛 `aos-git` 三項，就照 B-632 沒有提交與還原。
- **順序帶來的保證**：「先提交再送」靠 `git-close` 排在 `mq-post`、`summary` 前面（B-624）。使用者自己把送出排到 git 收尾前面，就沒有這個保證；照 [T-01](../terms.md)，沒排對的後果不逐條寫。
- 預設 kernel 範本（[P-814](../protocol/kernel-tasks.md)）與 agent 範本（[P-715](../protocol/agent-tasks.md)）都照沒有 git 版的順序：頭一項 `mq-get`，中間是原本的任務，尾三項 `mq-post`、`summary`、`clean`。〔那兩份範本還沒改，也還沒有有 git 版，見 README 疑點〕
- **不在範本上的**：once 是任務自己呼叫的通道事務（[B-613](daemon/channel.md)）；重啟、格後收尾、排空、helper 歸 daemon（[B-601](daemon/runtime.md)、[B-603～605](daemon/README.md)、[B-609](daemon/helper-actions.md)）。
- **通道**：daemon 開 tick 時給的通道（環境變數、憑證、事務）以 [B-612～614](daemon/README.md) 為正本。任務會繼承這些環境變數，在投件權就是執行權（[T-08](../terms.md)）之下這是預期行為。沒有通道（不是 daemon 開的格）只算功能受限：`aos-mq`、`aos-as`、once 用不了，其他照常。

依據：第二十批追答 8、9（推翻第十九批「標準配備：必須全掛、不能拆、跟核心同一支 `aos-tick`」「功能受限不算沒掛」「有備援就算全掛」）；第二十批進行順序、疑點裁定 3、4（存檔點、git 收尾之後才送）；astra 審整理區裁定（系統訊息佇列 `aos-mq` 取代收件與投件，順序照原位置）；aos-git 分工（系統級任務之間夾存檔點，範本自帶）。

**驗收：**沒有 git 版在沒有 git、沒有 cgroup 的機器上照常跑完；拿掉 `mq-post` 後 `.aos/mq/post/` 的訊息不送、其餘照常；拿掉 `mq-get` 後別的 tick 送來的訊息留在 daemon、其餘照常。有 git 版在有 git 的機器上每格最多一個 commit `aos-tick <seq>`；在沒有 git 的機器上 `aos-git` 三項只印 `no_git` 警告、回 0，其餘照沒有 git 版的結果。

## B-621：aos-needs：前置沒成功就不跑

`needs` 的意思不變：前置成功才執行。只是改成普通程式 `aos-needs`，核心不做。

- **`aos-needs <前置任務 id…> -- <原指令…>`**（argv 見 [P-204](protocol/node.md)）：讀結束碼紀錄（`AOS_TICK_RECORD`）。每個前置都在本格紀錄裡、而且正常退出 0，才 exec 原指令，結束碼就是原指令的；否則不跑，stderr 印 `needs_unmet: <id>`，回 125。沒有紀錄可讀也回 125（`no_record`）。
- 前置只看本格：不沿用上一格的成功，也不另做跨格任務排程器。
- 被 `aos-needs` 擋下的項在紀錄裡是 `exit:125`，算失敗；再依賴它的項也會被擋。
- `aos-needs` 只擋後面的項不跑，自己不還原。失敗任務寫到一半的改動：有 git 時，aos 範圍裡的由它那組的存檔點還原（B-630）；使用者任務自己的檔、以及沒有 git 時的一切，都留在資料夾裡。
- 任務預設以正常退出且碼為 0 表示本步成功，不代表整件產品任務完成。

依據：使用者方向 2026-09-29（needs 的意思）；第二十批疑點裁定 2（改成普通程式）。

**驗收：**`aos-needs a -- …` 在 `a` 失敗或還沒跑時回 125、原指令沒跑，`a` 成功時照跑、結束碼是原指令的；`b` 被擋下後，`aos-needs b -- …` 也回 125。

## B-634：aos-cg：每項一框

〔使用者方向 2026-09-30，第二十批追答 8〕每項任務一框做成普通程式 `aos-cg`，要的任務自己在 argv 包：`aos-cg -- 原指令`（argv、代碼與結束碼見 [P-211](protocol/node.md)）。它不是系統級任務。框的樹與命名見 [B-605](daemon/cgroup.md)。**放棄「沒包的任務一結束就清殘留」**：沒包的任務留下的程序，等格後由 daemon 收（[B-601](daemon/runtime.md)）。

| | 有 cgroup | 沒 cgroup |
|---|---|---|
| 什麼時候 | 自己在本 node 的 `n-<h>/tick` 框裡（看 `/proc/self/cgroup`） | 不在 node 框、沒有 cgroup v2，或框寫不進。人手或 cron 跑的格一律是這種 |
| 開框 | 在 `n-<h>` 下開 `task-<seq>-<pid>`（跟 `tick` 並列），把自己搬進去，再 fork＋exec 原指令、wait 主程序 | 不開框；stderr 印 `cgroup_unavailable`，設 `PR_SET_CHILD_SUBREAPER`，原指令另開程序群組 |
| 主程序結束後 | 框裡還有程序就直接寫 `cgroup.kill`（不先 TERM），看 `cgroup.events` 的 populated 變 0，再 rmdir | 對那個程序群組送 SIGKILL，再反覆收掛回自己的孤兒、逐一 SIGKILL 並 wait，到沒有為止 |
| 清不到的 | 經外部服務（`systemd-run --user`、`at`、cron）開的程序，會跑出 `n-<h>` | 同左，加上換成別的帳號的；也沒有上限、量測與 OOM 證據 |

- **清不空**：框一直不空時，stderr 印 `frame_not_empty`，建停格檔（[B-620](#b-620任務註冊表照表依序跑)）、回 1，不讓後面的項在還有人寫檔時開跑。
- **結束碼**照原指令；原指令被訊號結束時，`aos-cg` 用同一個訊號結束自己。
- **不放在 `tick` 底下**：cgroup v2 規定開了 controller 的那層不能同時放程序和子層。每項多約 0.1 毫秒（[實測](../../notes/probes/per-task-cgroup-cost.md)）。
- **跟 `aos-as` 一起用**：寫成 `aos-cg -- aos-as <帳號> -- 原指令`；`aos-as` 把自己所在的 `task-*` 框帶給 helper，別的帳號的程序也放進同一框（[B-303](helper.md)、[B-609](daemon/helper-actions.md)）。反過來寫開不了框，因為框不歸那個帳號。
- **不清上一格留下的 `task-*`**：只有 daemon 開的格才有 `task-*`，daemon 每格格後與重啟時都會收（[B-601](daemon/runtime.md)、[B-603](daemon/lifecycle.md)）。
- **跑出框的**：`setsid`、double fork 逃不出 cgroup；只有經外部服務開的逃得出。aos 不擋這條路（管轄權是約定，B-626），經外部服務開的不歸 aos 管。
- 〔暫定，第二十批疑-9 照 a〕沒 cgroup 時退回 subreaper 加程序群組，跟 daemon「沒有就退回」一致。

依據：第十七批（任務層框）；第二十批追答 8（改成普通程式 `aos-cg`、放棄沒包的任務一結束就清殘留）；第二十批疑-9（沒 cgroup 時的退回，暫定）；納入 cgroup 與 git 改寫計畫（拿掉開框前清舊 `task-*`；經外部服務開的不歸 aos 管）。

**驗收：**有 cgroup 時，包了 `aos-cg` 的項用 `setsid` 加 double fork 留下的程序，在它的 `task-*` 框被 `cgroup.kill`，下一項開跑時已經沒有；`aos-cg -- aos-as <帳號> --` 時別的帳號的程序也在同一框；框清不空時 `frame_not_empty`、建停格檔。沒 cgroup 時包了 `aos-cg` 的項留下、掛回 aos-cg 的後代也被清掉，stderr 有 `cgroup_unavailable`；沒包的任務留下的程序在 daemon 格後收尾時被清。

## B-623：系統訊息佇列：取件（mq-get）；檔案收件 aos 不管

**aos 只管系統訊息佇列。** 佇列是 aos 的系統級 IPC：同一個 daemon 底下的 tick 經通道互送訊息，daemon 替每個 tick 暫存（[B-614](daemon/messaging.md)）。**請求與回應都走佇列**〔使用者方向 2026-09-30，修正輪暫定的裁定〕。本條是取的那一側，送的那一側見 B-624。

| | 系統訊息佇列 | 檔案收件區（`requests/`、`responses/`） |
|---|---|---|
| 誰處理 | 系統級任務 `aos-mq get`（任務 id `mq-get`） | 任務表上的普通任務，aos 不管 |
| aos 規定什麼 | 只有它取；取出後怎麼分派不規定 | 不規定 |

### aos-mq get：只有它取

- **每個 node 只有 `aos-mq get` 用 `node.take` 取佇列**，其他任務不直接取。範本排在第一項（B-629）。
- 一格裡把佇列取到空為止（回應說還有就再取，[P-119](protocol/daemon/channel.md)）。請求與回應一起取出，不分兩個佇列。
- **取出後怎麼分派 aos 不管**：放哪、交給哪一項、先後怎麼排，由 `aos-mq get` 的實作決定，不在規範內。
- daemon 的憑證一格一張，分不出是哪一項在取，所以「只有它取」是同一個 node 裡的約定，不是授權（跟 [B-602](#b-602同一資料夾一次一格互斥鎖) 的鎖同一種）。
- 沒掛 `mq-get` 就沒人取：訊息留在 daemon，滿了寄件方收到 `mailbox_full`，daemon 重啟就丟（B-614）。
- 不保證送達；沒人取的也不回任何錯誤。
- 〔建議預設，未拍板〕daemon 訊息部件沒掛時，`node.take` 回空，`mq-get` 回 0；任務表不用改（[B-614](daemon/messaging.md)、[B-615](daemon/components.md)）。
- 沒有通道（不是 daemon 開的格）時什麼都不取，回 0（argv 與結束碼見 [P-206](protocol/node.md)）。
- 有 git 時〔使用者 2026-09-30 同意照暫定〕，這格作廢（停格檔、當機）的話，`mq-get` 這格取出、寫進 aos 範圍的訊息會被下一格 `aos-git open` 還原掉，等於丟了；daemon 那邊已經刪了，不會重取。佇列本來就不保證送達（B-630）。

### 檔案收件 aos 不管

- 收件區 `requests/`、`responses/` 裡的件，由任務表上的普通任務（收件程式）處理，不是系統級任務；怎麼讀、要不要回 -32601、原件何時刪、壞件怎麼報、接件前要不要核對回址，都由收件程式自己定。
- 所以 aos 不再保證：沒人宣告的 method 回 -32601、上一格正常收尾才刪原件、壞件只報一次、接件前核對 `reply_to`。這些原本是第十七～二十批給收件任務的規則，撤出基礎；依賴它們的區外條文列在 [README 疑點](README.md#疑點)，下一輪跟上。
- 任務表的 `methods` 仍可寫，核心不看，給收件程式讀（B-620）。

依據：使用者方向 2026-09-29；第十九批疑點裁定 7（通道訊息不由別人代取）；astra 審整理區裁定裁-1（每個 node 只准一個任務取件，分派 aos 不管）與同日定案（系統訊息佇列 `aos-mq`；檔案收件是普通程式，aos 不管）。

**驗收：**掛了 `mq-get` 時，別的 tick 送來的請求與回應都被它取走，同一件再取不到；沒掛時訊息留在 daemon、下一格也沒人取；任務表沒有收件程式時，`requests/` 的件留著、沒人回 -32601，核心照常跑完。

## B-624：派出：系統訊息佇列送出（mq-post）與發摘要（Q2）

派出只剩兩項系統級任務：`aos-mq post`（任務 id `mq-post`）把本 node 要送的訊息經通道送進對方的佇列；`aos-publish` 發布摘要。**檔案投件（寫對方的 `requests/`、`responses/`）是普通程式的事，aos 不管。**

### aos-mq post：只走通道

- 任務把要送的訊息寫進追蹤的 `.aos/mq/post/<id>.req.json`（請求）或 `<id>.resp.json`（回應）（格式見 [P-206](protocol/node.md)）。`aos-mq post` 排在使用者任務之後（B-629），用 `node.send` 一件一件送進對方的佇列（[B-614](daemon/messaging.md)）。不寫對方的收件區。
- 訊息是一份請求物件或回應物件（[P-301](../protocol/messages.md)）：回別人的請求，也是寫一份回應進 `.aos/mq/post/`，由 `mq-post` 送回對方的佇列。〔使用者方向 2026-09-30，修正輪暫定的裁定〕請求與回應分檔名後綴，同一格同 ID 的請求與回應不會撞檔名。
- `urgent:true` 是急件：送到時 daemon 叫醒收件 tick。
- 誰能送由 daemon 判（B-614）。
- **先提交再送**：有 git 版範本把 `mq-post` 排在 `aos-git close` 之後；close 失敗會建停格檔，核心就不開 `mq-post`。所以走到 `mq-post` 時，`.aos/mq/post/` 裡的都已提交；失敗組寫的訊息已在它的存檔點被還原，不送（B-630）。`mq-post` 自己不認得 git。
- 沒有 git 時只剩「本格前面的任務都跑完才送」：失敗任務寫出的訊息也會送；前面有項建了停格檔時，核心不開後面的項，這格不送。
- LLM／工具的結果留待後續格收，不在原地等遠端工作結束。

〔建議預設，未拍板〕送的結果：

| 結果 | 怎麼辦 |
|---|---|
| 送成功 | 移除那個檔；不保證送達 |
| `forbidden`、`not_registered`、`kind_mismatch`、`message_too_large`、`invalid_params` | 送不了：不保留、不重試、不改走檔案。stderr 印 `post_failed: <to> <id> <code>`，把那個檔搬到 ignored 的失敗紀錄 `.aos/mq/failed/`（檔名不變）並記下代碼（格式見 [P-206](protocol/node.md)） |
| `not_available`〔建議預設，未拍板〕 | daemon 訊息部件關閉；同「送不了」搬到 `.aos/mq/failed/`、記代碼且不自動重試；本次有待送件就回 1，沒件照沒事做回 0（[B-614](daemon/messaging.md)）。任務表不用改 |
| 其他錯誤（`mailbox_full`、`stopping`、連不上 socket 等） | 留著，下一格再送 |
| 本格沒有通道（`no_channel`） | 一件都不送、檔都留著；stderr 印一次，回 0 |

### 送出之後

- **失敗紀錄只留一格**〔使用者方向 2026-09-30，修正輪暫定的裁定；誰清：使用者 2026-09-30 同意照暫定〕：`mq-post` 每次開始送之前，先刪掉 `.aos/mq/failed/` 裡的舊紀錄（都是前面各格留下的）。所以寄件的任務在下一格、`mq-post` 跑之前讀得到它；要留久一點就自己抄走。
- 送成功、還沒移除時當機：下一格再送同一份，對方可能拿到兩次；取的一方靠訊息 ID 去重。
- 有 git 時〔使用者 2026-09-30 同意照暫定〕，`mq-post` 移除已送檔這一步要到下一格的 `aos-git close` 才提交；下一格作廢的話，這些檔會被還原、再送一次。同樣靠 ID 去重（B-630）。
- 可重送同一份訊息：這只是補送，不授權重做不明的工具／LLM 執行。無可信結果、又不能證明未執行的工作記 unknown，不自動再執行（[S-401](../scheduling/operations.md)）。
- once 由 module 經通道用 `node.mount` 掛到 daemon（[B-613](daemon/channel.md)），不往 `.aos/mq/post/` 塞 IPC。
- 〔暫定〕**鬧鐘撤**：原本的鬧鐘看對方收件區的原件還在不在；aos 不再寫對方收件區，佇列裡的訊息 daemon 也不說有沒有被取走，所以 `alarm_ticks` 與 `.aos/alarms/` 撤出 aos。要等回覆的任務，自己在領域狀態裡記、自己以格數判逾時。

### 發布摘要〔建議預設，未拍板〕

- 發摘要任務 `aos-publish` 排在 `mq-post` 之後：把 `.aos/summary/summary.json` 目前的原 bytes，用暫存檔再 rename 的方式整份發布成 ignored 的 `.aos/summary/published.json`（格式與權限見 [P-307](../protocol/messages.md)），給只有摘要讀權的上層讀；讀者一次 open 就拿到完整一版。
- 有 git 版範本把它排在 `aos-git close` 之後，發布的就是剛提交的那一版；沒有 git 時不保證跟其他檔是同一版。
- 發布失敗：留舊值、stderr 報錯、回 1，下一格再發。過時或缺失不等於 idle。
- 有 repo 讀權的上層讀 `summary.json`，讀的是目前檔案。兩種讀法都要核對 `node_id` 是自己的直接下層（B-628）。
- 摘要是觀測，不能蓋掉較新的收件事件。上層不為了查詢而叫醒成員 tick，也不因要讀摘要就取得成員 repo 或下層內容的權限。

### 檔案投件 aos 不管

寫對方 `requests/`、`responses/` 的是普通程式：目標是不是 node、權限不夠、暫時性錯誤怎麼辦，都由那個程式定。原本「投件只查目標是不是 node」「`channel:true` 才改走通道、其餘走檔案」撤出基礎。

依據：使用者方向 2026-09-29；第十五批（鬧鐘，第二十批撤）；第十九批第 9 條與疑點裁定 6（經通道送）；第二十批疑點裁定 4、進行順序（送出排在使用者任務之後）；astra 審整理區同日定案（`aos-mq post` 只走通道，檔案投件是普通程式）；納入 cgroup 與 git 疑-4（送出與發摘要不認得 git，靠順序）；修正輪暫定的裁定（回應也走佇列；送不出去的留失敗紀錄、下一格清）。

**驗收：**`.aos/mq/post/` 有一件給同一 daemon 底下 tick 的訊息時，`mq-post` 經通道送出並移除該檔，對方的 `requests/` 沒有多出檔案；對方回 `mailbox_full` 時檔留著、下一格再送；目標不在這個 daemon（`not_registered`）時 stderr 有 `post_failed`、檔搬到 `.aos/mq/failed/`，下一格 `mq-post` 跑之前還讀得到、跑過之後就沒了；寫在 `.aos/mq/post/` 的回應物件同樣送進對方佇列；直接跑的格（沒有通道）檔都留著、回 0。

## B-625：當機恢復、設定與清理

本條同時寫有沒有 git 兩種情形；「有 git」指掛了 `aos-git` 三項而且 git 能用（B-630），其餘照沒有 git。

### 當機之後

**程序**：整機或 WSL VM 重開時舊程序本來就沒了。只有 daemon 自己重開時，舊程序可能還在：有 cgroup 時 daemon 先清空舊框才開格；沒有 cgroup 時清不掉（已接受），舊格還握著鎖時新格回 75，等它自己結束（[B-603](daemon/lifecycle.md)）。

**檔案**：當在哪一步，下一格看到的：

| 當在哪 | 有 git | 沒有 git |
|---|---|---|
| 使用者任務或清理途中、`aos-git close` 提交前 | `last.json` 是 `ended:false`；下一格 `aos-git open` 把 aos 範圍還原到 HEAD，這格作廢。使用者任務自己的檔留著，由任務自己的狀態恢復 | 寫到一半的改動留在資料夾裡，由各任務自己的狀態恢復 |
| `aos-git close` 提交後、`mq-post` 或發摘要途中 | 已提交的都在。`mq-post` 已送、還沒移除的訊息：移除那一步沒提交，會被 open 還原回來，下一格再送；對方靠請求 ID 去重（B-624）。摘要下一格再發 | 已送、還沒移除的下一格再送；摘要下一格再發 |

- **未明的工具／LLM 請求**：按 Q2（B-624）處理。能恢復本地 tick，不等於能重做 unknown 外部工作。

### 改設定〔暫定，astra 審整理區必-5〕

| 改什麼 | 怎麼改 |
|---|---|
| 普通設定（`config/` 裡的檔） | 在 tick 外用 `aos-config-add`（argv 見 [P-207](protocol/node.md)）：非阻塞取 node 鎖（B-602），拿不到回 75；有擋板檔就不寫、回 125。寫法：在目標旁寫完整暫存檔 → fsync → rename 替換 → fsync 目錄。沒變動就不寫。不能在同 node 的 tick 內呼叫 |
| 重要設定（inst 的身分、任務表）與其他手改 | 先 `node.pause`，等 `node.show` 看到 `running:false`，持 node 鎖修改，照下面驗過再 resume（[B-607](daemon/registration.md)） |

- tick 裡的任務不改 `config/` 是軟性原則，不檢查也不阻擋；同一格新舊設定混用的風險由寫任務的人承擔（[A-102](../agent/configuration.md)）。
- **有 git 時**〔暫定〕：
  - `config/` 不在 aos 範圍（B-630），`aos-config-add` 也不自己提交；要留歷史就自己 `git commit`。
  - inst 與任務表在 `.aos/` 底下，屬 aos 範圍：格間手改的下場照 [B-602](#b-602同一資料夾一次一格互斥鎖)「tick 外的寫入者」，上一格沒正常收尾時會被還原，所以改完自己提交。

### 恢復前驗證

resume 之前，持同一把鎖依序檢查：

1. inst：照 [inst 目標](../base/inst.md#inst-目標檔案或資料夾)選 inst，驗原始結構與身分宣告。daemon 在 resume 與開格時仍另驗可信額度，本地檢查不代替授權。
2. 任務表：照完整 schema 驗（[P-202](protocol/node.md)；含 `kind` 的值，B-620「誰驗什麼」）。不認得的鍵照收，`group`、`needs` 也是陌生鍵，不檢查。
3. **只在裝了對應任務時**：kernel、agent 的領域設定照各自的篇驗（[A-102](../agent/configuration.md)）。自訂任務沒有 aos 的領域設定契約，不因它沒提供驗證就拒收。
4. 任何一項不過就保持暫停、保留手改，stderr 指出檔案與欄位；都過才送 `node.resume`。

驗證只證明設定可採用，不證明外部 endpoint 可達。清理見 [B-404](../base/storage.md)。

依據：使用者方向 2026-09-29；第二十批改寫、進行順序、疑點裁定（沒有 cgroup 時重啟清不掉舊程序，接受；任務表只定基本欄位）；納入 cgroup 與 git 疑-1、疑-3、aos-git 分工（提交與還原只限 aos 自己的東西）。

**驗收：**`aos-config-add` 寫入後下一格讀得到新值，寫到一半被殺時目標是舊版或新版、不會半份，有 git 時不產生 commit；有 git 時使用者任務途中當機，下一格 `.aos/` 回到 HEAD、使用者任務自己的檔不動；`aos-git close` 提交後、`mq-post` 途中當機，已提交的不丟，已送的下一格重送；有擋板時回 125、目標不變；任務表帶 `group`、`needs` 的 node 通過恢復前驗證；帶 `system.x` 的不通過、保持暫停。

## B-632：結束碼紀錄取代日誌：沒有 git 時怎麼做

git 與無 git 合成同一種模式：**核心的結束碼紀錄（B-633）直接取代日誌。** 第十九批的 `.aos/journal/`（完成紀錄、`sent/`、`discarded/`）與換回 git 的 `aos-tick adopt` 都撤。

本條管「沒有 git」：任務表沒掛 `aos-git`，或掛了但 git 不能用（`aos-git` 印 `no_git` 警告、回 0，B-622）。這時沒有「已提交」這回事：

| 下游 | 沒有 git 時怎麼做 |
|---|---|
| 佇列送出 | `mq-post` 送 `.aos/mq/post/` 裡所有的訊息（B-624） |
| 發摘要 | 從目前的 `summary.json` 發布（B-624） |
| 保留期起點 | 從 `aos-clean` 記下的格數算（[B-404](../base/storage.md)） |
| 檔案收件原件 | aos 不管（B-623） |

〔記錄者理解〕所以沒有 git 時：失敗任務與當機時寫到一半的改動都留在資料夾裡；失敗任務寫出的訊息也會送；沒有歷史與一致快照，只能讀目前的檔案。

**下游不認得 git**：`aos-mq`、`aos-publish`、`aos-clean` 在有 git、沒 git 時跑同一份程式；git 只活在 `aos-git` 三項裡（B-630）。有 git 時多出的保證全靠範本的順序（B-629）。

依據：第二十批追答 8、疑點裁定 5（取代第十九批「git 提交的備援：檔案日誌」）；astra 審整理區同日定案（收送改成系統訊息佇列）；納入 cgroup 與 git 疑-4（下游不認得 git）、疑-5（git 不能用照本條）。

**驗收：**沒有 git 的機器上，兩版範本任務表都照常跑完、每格都有結束碼紀錄；上一格被殺時下一格的 `last.json` 是 `ended:false`。git 沒裝、低於 2.36、不是 repo、repo 壞到讀不了 HEAD 時，`aos-git` 三項都印 `no_git` 警告、回 0、不寫擋板。

## B-627：人手或 cron 直接跑一格：風險自負

`aos-tick` 誰都能直接跑（人手、cron、其他程式），照常做完一格；風險由跑的人自己承擔。直接跑的格跟 daemon 開的格差在：

- **沒有通道**：once、系統訊息佇列用不到（`aos-mq` 什麼都不做、回 0），`aos-as` 回 125（`no_channel`）。需要通道的事一律算功能受限，不另設替代路。
- **沒有 daemon 的格後收尾**：任務留下的後代沒人收，還握著鎖 fd 的會讓下一格回 75（B-602）。
- **不在 node 框裡**：包了 `aos-cg` 的項照沒 cgroup 的做法退回（B-634）。

其餘照常：

- 同一資料夾 daemon 正在跑一格時，直接跑的那格拿不到鎖、回 75（B-602）；反過來也一樣。
- 直接跑的格同樣寫結束碼紀錄、同樣加 `seq`（B-633）。
- 想經 daemon 跑一格：送 `node.wake`，以回應的值為起點，再用 `node.show` 等格次前進；怎樣算新的一格已完成、`registration_id` 換了怎麼辦，以 [B-607](daemon/registration.md) 為正本。不另開「跑一格並等結果」的 IPC。CLI 入口見 [H-004](../cli/commands.md)。

依據：第十九批第 12 條（撤第十八批審稿裁定 16「不在框就拒跑」）；第十九批疑點裁定 11（記錄者歸類：需要通道的事算功能受限）。

**驗收：**不經 daemon 直接跑 `aos-tick` 照常做完一格；daemon 正在跑同一 node 時直接跑回 75、不改檔；經 `node.wake` 跑的那一格照 B-607 判定為完成；直接跑與 daemon 跑交替時 `seq` 連續。

## B-630：git：開格、存檔點、收尾

〔使用者方向 2026-09-30，第二十批追答 8、疑點裁定 3、5；納入 cgroup 與 git 疑點裁定；aos-git 分工〕git 做成三個系統級任務：`aos-git open`、`aos-git mark`、`aos-git close`（argv、代碼與結束碼見 [P-205](protocol/node.md)）。範本怎麼排見 B-629；共同規則（能不能用、呼叫參數、固定排除、故障）見 B-622。

**有 git 才用**：沒掛這三項，或 git 不能用，照 B-632。核心不認得 git，其他系統級任務也不認得（B-632）。

### 管什麼：只管 aos 自己的東西

**提交與還原只限 aos 自己的東西**〔使用者方向 2026-09-30，aos-git 分工〕。叫它「aos 範圍」：

| 東西 | 在不在 aos 範圍 |
|---|---|
| `.aos/` 底下追蹤的檔：任務表、inst、`.aos/mq/post/`、`summary.json` 等 | 在 |
| 系統級任務動到的檔 | 在。怎麼認〔使用者 2026-09-30 同意照暫定〕：兩個相鄰存檔點之間的項**全是** `kind:"system"` 時，這一段的所有改動都算 |
| 任務呼叫 `aos-git mark <路徑…>` 帶的路徑 | 在，從那個存檔點起到本格結束〔使用者 2026-09-30 同意照暫定〕 |
| 使用者任務改的其他檔 | 不在：aos 不提交、不還原 |
| 核心檔（B-622 固定排除） | 永遠不在 |

- **保證**：aos 只保證自己的東西——`kind:"system"` 任務與 tick／daemon 基底——是原子的。tick 本身不保證整格原子。
- **使用者任務要存檔**：自己在任務表加 `aos-git mark` 項，或在程式裡呼叫、帶上自己的路徑；範本不替它們插存檔點。
- `kind` 怎麼查〔使用者 2026-09-30 同意照暫定〕：`aos-git` 照結束碼紀錄裡的 `id` 去任務表查；查不到的當成不是系統級任務。

### 組與存檔點

- **存檔點**＝`aos-git mark` 這一項，把此刻的 aos 範圍存成暫存提交，記在 `refs/aos/marks/<本項 id>`（取 `AOS_TASK_ID`）。不動分支、HEAD 與正式 index。`aos-git open` 也打一個。
- **組**＝相鄰兩個存檔點之間的各項；最後一組是最後一個存檔點到 `aos-git close` 之間。組內每項 `exit:0` 才算成功；被 `aos-needs` 擋下的（`exit:125`）也算失敗。
- **失敗就當場還原**（疑-2）：存檔點發現剛結束那組有失敗，就把那組改過的 aos 範圍路徑（含新增、刪除）還原到**往前最近的存檔點**〔使用者 2026-09-30 同意照暫定：不分範本放的或任務自己打的〕，再打點。所以後面的組看不到失敗組寫的東西，close 只要提交。
- 存檔點只看結束碼紀錄與已打的存檔點；不看 argv，也不管任務在格內改了表。
- 存檔點各占一項（疑-12），不另設包裝寫法。

### 開格 `aos-git open`

1. **看 git 能不能用**（B-622）。不能用就印 `no_git` 警告、回 0，這格照 B-632。
2. **上一格沒正常收尾就還原**：`last.json` 是 `ended:false`、有 `stopped_after`（B-633），都算沒正常收尾。還原範圍是 `.aos/`，加上上一格留下的存檔點記的 aos 範圍，一律回到 HEAD。上一格正常收尾，或沒有 `last.json`，不還原。
3. **清殘留**：上一格留下的 `refs/aos/marks/*` 清掉。〔建議預設〕上一格是當機（`ended:false`）時，一併清掉 git 管理目錄裡 aos 自己可能留下的鎖檔（`index.lock`、`HEAD.lock`、`refs/**/*.lock`）。
4. HEAD 不在上一格提交時的那個分支上（任務自己換了 HEAD 或分支）：不碰工作樹，當故障（B-622）。
5. **巢狀排除**（B-622），再打本格第一個存檔點 `refs/aos/marks/<本項 id>`。

### 收尾 `aos-git close`

1. 照存檔點的做法處理最後一組：成功就留、失敗就還原。
2. 巢狀排除再掃一次。
3. **提交**：aos 範圍剩下的改動 commit 一次，訊息 `aos-tick <seq>`（`seq` 見 B-633）；沒變動就不 commit，所以每格最多一個。〔建議預設〕訊息另加一行 `aos-failed: <存檔點 id…>`，列出失敗的組，只給人看。
4. 刪掉本格的存檔點，回 0。

close 排在 `mq-post`、發摘要前面（B-629）：它失敗會建停格檔，後面的項不開，保住「先提交再送」（B-624）。

### 跟停格檔、擋板檔、當機怎麼互動

| 情況 | 會怎樣 |
|---|---|
| 上一格正常收尾 | 不還原 |
| 上一格當機（`ended:false`） | open 把 aos 範圍還原到 HEAD；那格的改動作廢 |
| 本格某項建停格檔（疑-1） | close 不跑、不提交；下一格 open 還原。**這格作廢**，前面已成功的組也一起丟（B-620） |
| `mq-get` 這格取出的訊息 | 這格作廢時一起被還原，等於丟了（B-623） |
| `aos-git` 自己故障 | 寫擋板、建停格檔：這格作廢，之後各格被擋，要人處理（B-622） |
| 有擋板 | 核心一項都不跑（B-620），`aos-git` 不另外看擋板 |
| 格間人手改 aos 範圍 | 見 [B-602](#b-602同一資料夾一次一格互斥鎖)「tick 外的寫入者」 |

### 其他〔建議預設〕

- **還原時還有人在寫**：沒包 `aos-cg` 的任務留下的程序，要等格後才被 daemon 收掉，還原之後可能又寫回來。只有包了 `aos-cg` 而且 daemon 有 cgroup，才保證還原時那一項已經沒人在寫（B-634）。
- **成本**：每個存檔點都掃一遍 aos 範圍；實作用 stat 快取（先複製正式 index 再加，不必每次重算整樹 hash）。
- **多帳號**：`aos-as` 開的程序寫進 aos 範圍的檔，要讓 tick 帳號讀得到（例如 [B-609](daemon/helper-actions.md) 的共享群組），否則 git 讀不到，當故障。

依據：第二十批追答 8（git 做成任務表上的任務；tick 不再保證整格原子）、疑點裁定 3（每組跑完打存檔點）、4（送出在 git 收尾之後）、5（git 與無 git 合成一種模式）；納入 cgroup 與 git 疑-1（停格＝本格作廢）、疑-2（存檔點當場還原）、疑-4（下游不認得 git，拿掉草稿的「開格刪收件原件」「只送 HEAD 裡的」）、疑-12（存檔點獨立一項）；aos-git 分工（開格與收尾管 tick／daemon 基底與系統級任務；提交與還原只限 aos 自己的東西；失敗還原到往前最近的存檔點，暫定）。

**驗收：**有 git 版範本裡，使用者任務那組有一項失敗：它寫進 `.aos/mq/post/` 的訊息在 `mark-user` 被還原、不送，它改的 `state/` 檔留著、不被提交；清理成功、那格一個 commit `aos-tick <seq>`，含清理的變動。某項建停格檔：close 沒跑、沒有 commit，下一格 open 把 `.aos/` 還原到 HEAD。上一格 close 後 `mq-post` 途中當機：已提交的都在。任務 id 以 `.lock` 結尾的存檔點：`mark_id_invalid`、擋板＋停格檔。

## B-622：git 的共同規則

〔使用者方向 2026-09-29；第十八批（落盤）；納入 cgroup 與 git 疑點裁定〕`aos-git` 三項共用。每個 node 資料夾是一個 git repo；不用帳本或 SQLite。

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
| `-c gc.auto=0 -c maintenance.auto=false` | 不讓 aos 自己那幾次呼叫觸發背景整理；背景程序會握著鎖 fd 讓下一格回 75，也違反「不准背景程序繞過 tick」〔使用者方向 2026-09-30〕 |
| 〔建議預設〕`-c core.hooksPath=/dev/null`、`-c commit.gpgSign=false`、`-c safe.directory=<node 根>` | 不跑 hooks；使用者全域開了簽章也不會卡住；node 根的擁有者跟 tick 帳號不同時（[B-203](../base/execution.md) 的兩種主人）git 仍肯動 |

- **不動使用者的設定**：上面都是命令列參數，只管 aos 自己那幾次呼叫。git 的背景整理（gc、maintenance）aos 不管；文件建議使用者自己關掉（例如 `git config gc.auto 0`、`git config maintenance.auto false`），要整理就先暫停 node 再手動跑。
- **環境**〔建議預設〕：呼叫前清掉所有繼承的 `GIT_*`，只設自己要的，免得操作到別的 repo。
- **作者**〔建議預設〕：用 repo 設定；repo 與全域都沒設時用 `aos <aos@localhost>`，不擋。
- **不在 tick 內**：沒有繼承到鎖（B-602 的核對不過）時回 125、印 `not_in_tick`；人手要提交就直接用 git。

### 範圍怎麼切

- **固定排除**：不管 `.gitignore` 寫了什麼，[P-200](protocol/node.md) 表裡 ignore 的核心檔一律不提交、不還原：`.aos/tick.lock`、`.aos/tick/`、`.aos/tick-blocked`、`.aos/jobs/`、`.aos/attention/`、`.aos/runner-stderr.log`、`.aos/summary/published.json`、`.aos/mq/failed/`、`requests/`、`responses/`、`work/`。否則 `.gitignore` 漏列時，結束碼紀錄會被還原、`seq` 倒退。
- **巢狀**：下層 tick 的資料夾（判準照 B-628）寫進 git 管理目錄的 `info/exclude`，不改 `.gitignore`。open、mark、close 存之前都重掃一次，免得格中新建的子 node 被上層提交（已追蹤的檔不會因為之後才排除就不追）。子 node 自己是 repo 時不進去。
- **不遍歷**：不用全樹 `git clean -x`，不進 git 管理目錄或子 repo。

### 故障

還原、存檔點、commit 失敗，HEAD 被換（B-630 open 第 4 步），任務 `id` 當不了 ref 名（`mark_id_invalid`，例如以 `.lock` 結尾），在 tick 內卻沒有結束碼紀錄（`record_missing`）：

1. 寫擋板檔、建停格檔、回 1；
2. daemon 照 [B-607](daemon/registration.md) 不再開格，錯誤摘要走[待處理事項](../scheduling/operations.md)；
3. 修復者暫停、持鎖、核對、自己提交修好的改動，再移除擋板。

### 其他

- **原子**只指同一 repo 裡 aos 範圍的已提交版本與恢復基線；使用者任務自己的檔、ignored 檔、另一個 repo、外部 workspace 與不可逆後果，都不會跟著還原。
- 〔使用者方向 2026-09-29〕別濫用 git：沒變動不 commit；可定期合併提交、可用 submodule。合併提交要暫停、持鎖；submodule 不承諾跨 repo 的組原子性。

依據：使用者方向 2026-09-29（每個 node 一個 repo、別濫用 git）；第十八批第 17 條、Q31（落盤）；納入 cgroup 與 git 疑-5（不能用就警告、照沒 git 做）；同日裁定（背景整理 aos 不管，自己呼叫時帶 `gc.auto=0`、`maintenance.auto=false`）。

**驗收：**`.gitignore` 拿掉 `/.aos/tick/` 後 `seq` 仍連續、紀錄不進 commit；格中用 `aos node new` 建的子 node 不進上層的 commit；格結束後沒有 git 程序握著鎖 fd，下一格不回 75；node 根擁有者跟 tick 帳號不同時照常提交；使用者全域開了 commit 簽章也照常提交；滿碟時 commit 失敗：擋板＋停格檔，`mq-post` 不跑。

## B-631：（撤）cgroup 框的備援

〔使用者方向 2026-09-30，第二十批追答 8〕撤：tick 側的 cgroup 備援（開格設 subreaper、每項後殺程序群組並掃孤兒、`RLIMIT_AS`／`RLIMIT_CPU`、getrusage）與完整／備援對照表。每項一框改成普通程式 `aos-cg`（B-634）；daemon 側的收尾見 [B-604](daemon/lifecycle.md)。

## 驗收與尚未定案

當機、Q1／Q2、設定的故障驗收，統一見 [V-03](../conformance.md)。

註冊表格式以協議篇為準。〔暫定〕「有 tick 的資料夾」看 inst 檔（計畫疑-10）；〔使用者方向 2026-09-30，第二十批〕任務表先只定基本欄位，`group`、`needs` 當陌生鍵。停格檔的位置、結束碼紀錄的位置與欄位、各系統級任務與普通程式的程式名都是工程預設。git 與 cgroup 是有就用（B-630、B-622、B-634）；這輪先寫成暫定的列在 [README 疑點](README.md#疑點)。
