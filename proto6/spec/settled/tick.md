# 通用 tick：核心與標準任務表範本

← [整理區](README.md)｜[名詞](terms.md)｜[慣例](conventions.md)｜[daemon](daemon/README.md)｜格式：[node 協議](protocol/node.md)｜先不做的：[tick 暫緩區](deferred/tick.md)、[helper 與 aos-as](deferred/helper.md)

依據：[09-29 新架構](../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../notes/verdicts/11-tick-as-unit.md)與它篇末 2026-10-01 各節；現行程式 [proto6/src/py](../../src/py/README.md)。

讀之前先知道三件事：

- **工作資料夾**＝這一格 `aos-tick` 跑的資料夾（它的 cwd），由命令列給的目標決定（`aos-tick [<目標>]`，B-620）。tick 這層只講工作資料夾；「node」是之後 node 模組才出場的詞。本篇後半（系統級任務、git、佇列各條）還寫著 node，在 tick 這層就讀成工作資料夾。
- 「任務表」指工作資料夾裡的任務註冊表 `.aos/tasks.json`，跟舊 daemon 的登記表是兩回事（[T-02](../terms.md)）。
- 本篇寫的 `.aos/…` 都是環境變數 `AOS_DIRNAME` 沒設時的樣子（[C-09](conventions.md)）；結束碼照 aos 慣例：0＝預料之中、非 0＝要處理、1＝通用錯誤（[C-08](conventions.md)）。

## 先講重點

- **tick 是一個定期被執行的程式**（`aos-tick`）。誰來跑都行：daemon、cron、人手（B-627）。它執行時的目前目錄（cwd）就是它的**管轄區**。
- **核心只做三件事**：同一資料夾一次一格的簡單互斥鎖（B-602）、照任務表依序跑（B-620）、每項結束碼紀錄（B-633）。上下層判定（B-628）已搬到[暫緩區](deferred/tick.md)。
- **任務怎麼結束都不影響 tick 的結束碼**：任務回幾都照實記進紀錄、照常跑下一項。tick 自己只回 0 或 1。
- **tick 是整個 aos 的衡量基準**：排程以格計，反應最快是下一格；aos 內部的時長與起算點都用本資料夾的格數（B-633、[C-01](../contracts.md)）。
- tick 不跟 once、LLM 嘗試、agent 一輪這些計算單位共用外殼（[T-07](terms.md)）。
- **git 與 cgroup 是「有就用」，不是前提。** 沒有 git、沒有 cgroup 時照原來的做法跑（B-632、[B-601](deferred/daemon/runtime.md)）。
  - **git**：掛了 `aos-git` 三項系統級任務而且 git 能用，aos 自己的東西（`.aos/`、任務表、系統級任務動到的檔）才有提交與還原（B-630、B-622）。使用者任務改的檔 aos 不提交、不還原。
  - **cgroup**：node 框與資源上限歸 daemon（[B-605](deferred/daemon/cgroup.md)，在暫緩區）；每項一框要任務包普通程式 `aos-cg`（B-634）。
- **收送只管系統訊息佇列**：node 之間經 daemon 通道互送訊息，由系統級任務 `aos-mq get`／`aos-mq post` 處理（B-623、B-624；daemon 通道那側在暫緩區）。檔案收件區 `requests/`、`responses/` 的收與寫是普通程式的事，aos 不管。
- **保證跟著「掛了什麼」走**：核心三件事（B-626）不靠任何系統級任務也成立；其餘保證看任務表掛了哪幾項系統級任務、任務包了哪些普通程式。〔建議預設，未拍板〕各條只寫「掛了時保證什麼」，沒掛的後果不逐條寫。

依據：第十八批（外殼）；第十九批（定期被執行的程式、管轄區）；第二十批（衡量基準、進行順序；推翻第十九批「本篇的保證以標準配備全掛為前提」與完整／備援兩級）；使用者 2026-10-01（POC 默認一切正常、核心縮成三件事、目標改成位置參數、工作資料夾）。

## B-626：核心與系統級任務的界線

tick 裡的東西分四類：

| 類 | 是什麼 | 有哪些 |
|---|---|---|
| tick 核心 | `aos-tick` 本身，只做三件事 | 簡單互斥鎖（B-602）、照任務表依序跑（B-620）、每項結束碼紀錄（B-633） |
| 系統級任務 | 從核心拆出、掛在任務表上的獨立程式，以 `kind:"system"` 標記；**寫在表上才跑，沒寫就不跑** | 系統訊息佇列 `aos-mq`：開頭取件 `aos-mq get`（B-623）、收尾送出 `aos-mq post`（B-624）；發布摘要 `aos-publish`（B-624）；清理 `aos-clean`（[B-404](../base/storage.md)）；git 開格、存檔點與收尾 `aos-git open`／`mark`／`close`（B-630） |
| 普通程式 | 任務會用到的工具，要的任務自己在 argv 包；不是系統級任務 | 切換帳號 `aos-as`（[B-303](deferred/helper.md)，在暫緩區）、前置沒成功就不跑 `aos-needs`（B-621）、每項一框 `aos-cg`（B-634） |
| 其他任務 | kernel、agent、clock、檔案收件程式、自訂任務等 | 它們的外殼、逾時與取消延後（[P-008](../protocol/README.md#p-008)）；檔案收件 aos 不管（B-623） |

**核心**：照表跑時另外只認兩個檔——停格檔與擋板檔（B-620）；**任務沒有 `user`**（寫了照陌生鍵），一律用 tick 自己的帳號跑。核心只要 Python 3.9 與 flock，不靠 daemon、git、cgroup、helper，也不靠任何系統級任務。上下層判定原本是第四件事，使用者 2026-10-01 說「也不需要判斷上下層」，整條搬到[暫緩區](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)。

**系統級任務**：

- 各自是獨立的程式，彼此只靠檔案（結束碼紀錄、`.aos/mq/post/`）交接，不靠任務 `id` 相認。標準任務表範本就是預設的一組（B-629）。
- `kind:"system"` 的意思是「這一項是系統級任務」。它只是標記：核心不看，也不授予身分或權限；`system` 不開放自訂子名（`system.x`，[T-06](../terms.md)；誰擋見 B-620「誰驗什麼」）。
- 〔建議預設，未拍板〕不檢查 kind 的先後（撤掉第十九批暫定的「system 最前、custom 最後」）：範本的系統級任務分在頭尾兩段，照陣列順序就好。
- `aos-clean` 也是系統級任務，範本裡寫 `kind:"system"`。

**daemon 不在任務表上**：現行 daemon 核心只定期叫 `aos-exec`，不認得 node（[T-11](terms.md)、[B-640](daemon/core.md)）。舊設計裡一格結束後殺殘留、重啟、排空停機、helper 歸 daemon（[B-601](deferred/daemon/runtime.md)、[B-603～605](deferred/daemon/README.md)、[B-609](deferred/daemon/helper-actions.md)），這些在暫緩區。

**管轄權是約定，不是前提**：tick 對管轄區有最高裁量權，這是 aos 體系裡的約定。Linux 權限上碰不到某些東西時，tick 照樣跑完一格，碰不到的那件照各自規則失敗。管轄區可以重疊，風險自己承擔；aos 體系裡的慣例是不重疊、可以包含（上下層怎麼算在暫緩區，B-628）。

依據：第二十批追答 8、9（推翻第十九批「三層：核心／標準配備／其他掛載」、疑點裁定 1「標準配備跟核心同一支 `aos-tick`、不另做包裝」；`kind:"system"` 取代第十九批「留給以後真正屬於標準配備的任務、範本沒有 system 類」；`aos-clean` 取代第十九批疑點裁定 2「範本裡仍是 custom 類」）；第十九批第 2、5 條（管轄權）；astra 審整理區裁定（收送改成系統訊息佇列 `aos-mq`，檔案收件與投件是普通程式、aos 不管）；使用者 2026-10-01（核心不判上下層、不看 `user`）。

**驗收：**拿掉 daemon、git、cgroup、helper 與所有系統級任務，任務表只放一項 `true`，直接跑 `aos-tick`：互斥、照表跑與結束碼紀錄照常成立，回 0；任務寫了 `user` 也當陌生鍵、照 tick 自己的帳號跑；佇列沒人取也沒人送、不發摘要。

## B-602：同一資料夾一次一格：互斥鎖

**同一資料夾同時只能跑一個 tick。** 這把鎖屬核心，不靠 git、cgroup 或 daemon。

現在只做最簡版（使用者 2026-10-01：外層定期跑 `aos-tick`，上一格沒跑完下一格就來，是正常使用會碰到的）。鎖 fd 傳給任務、後代擋下一格等完整細節在[暫緩區](deferred/tick.md#暫緩b-602-完整互斥的其餘細節)。

### 鎖怎麼取

- **認哪個資料夾**：照 B-620「認哪個資料夾」（`aos-tick [<目標>]`，argv 見 [P-203](protocol/node.md)）。tick 在那個工作資料夾裡跑，cwd 就是它。
- **鎖檔**：`.aos/tick.lock`，ignored。不存在就建（`.aos/` 不在也建）；tick 自己不刪它。不放在 git 管理目錄；`aos-clean` 與一般清理都不得移除或替換它，`aos-git` 固定排除它，提交與還原都不碰（B-622）。
- **取鎖**：認好資料夾之後的第一件事，在看擋板檔之前。對鎖檔取**非阻塞**獨占 flock：
  - 拿不到：stderr 印一行 `busy: …`、回 0（預料之中，[C-08](conventions.md)）。不寫結束碼紀錄、不加 `seq`、不在程式內重試。被占的同時也有擋板檔時，印的是 `busy`（鎖在前）。
  - 拿到：整格持鎖，程序結束時自然放掉。
- 認資料夾失敗（用法錯、`no_target`、`no_tasks`）時還沒取鎖，什麼都不建。

### 任務與後代

- **鎖 fd 不傳給任務**：沒有 `AOS_TICK_LOCK_FD`。所以任務留下的後代不會佔住鎖，下一格照樣拿得到。
- 任務自己去取同一把鎖會拿不到（tick 正握著）。所以「在不在 tick 內」靠鎖判斷的那幾支程式（`aos-git`、`aos-mq`、`aos-as`），要等暫緩區的「鎖 fd 傳給任務」回來才有判法。
- 核心不清後代，也不管任務逾時；這些留給 daemon 那段（在暫緩區）。

### tick 外的寫入者

CLI 或工具在 tick 之外自己取鎖改檔，當成外部世界，aos 不管。沒有 git 時，改動就直接留在資料夾裡。

有 git 時，人手改到 aos 範圍（B-630）的東西，aos 也不替它另外做什麼：

| 上一格 | 格間手改的下場 |
|---|---|
| 正常收尾 | 被下一格的 `aos-git close` 跟著提交 |
| 沒正常收尾 | 被下一格的 `aos-git open` 還原掉 |

所以要手改 node：先停住排程（經 daemon 跑的用控制模組的 `pause`，[B-641](daemon/control.md)；舊設計的暫停見 [B-607](deferred/daemon/registration.md)，在暫緩區），改完要保住就自己 `git commit`。aos 不另存救援副本。

依據：第十九批（核心；第 7 條認資料夾）；第二十批（核心不清後代）、疑點裁定 8（取代第十九批建議預設「其他寫入者也須協調這把鎖或先暫停 tick」）；納入 cgroup 與 git 疑-3（人手改的不管、不做救援 ref）；使用者 2026-10-01（最簡互斥、拿不到回 0、鎖 fd 不傳給任務）。

**驗收：**同資料夾同時跑兩個 `aos-tick`（第一格的任務卡住）：後到的那個印 `busy`、回 0，兩份紀錄與 `seq` 都不變；第一格照常跑完，之後下一格照常。用資料夾路徑與 `.aos/tasks.json` 路徑各跑一次，搶的是同一把鎖。任務的環境裡沒有 `AOS_TICK_LOCK_FD`，前一格的任務留下的後代還在跑時，下一格照樣拿得到鎖。沒有 git repo 也取得到鎖。

## B-620：任務註冊表：照表依序跑

任務表預設是工作資料夾的 `.aos/tasks.json`（目標給的是檔時就是那個檔）。**陣列位置就是順序**，核心照順序一項一項跑。欄位、JSON 與 schema 以 [P-202](protocol/node.md) 為準，本節只定意思。

### 一格怎麼走

1. 認工作資料夾與任務表（下面「認哪個資料夾」）；不對就回 1。
2. 取鎖（B-602）；拿不到印 `busy`、回 0。
3. 看擋板檔；有就印 `blocked`、回 0，不開格（下面「停格檔與擋板檔」）。
4. 讀表、做極簡檢查（下面「讀表」）；不過就印 `bad_table`、回 1，不開格。
5. 換一份新的結束碼紀錄（B-633）。做到這一步才算開了一格、佔一個 `seq`。
6. 刪掉上一格留下的停格檔。
7. 照陣列順序跑每一項；每項結束後寫紀錄、查停格檔。
8. 回結束碼（下面「核心的結束碼」）。

### 認哪個資料夾：目標

`aos-tick [<目標>]`，目標是位置參數，跟 `aos-exec` 一樣；沒有 `--node`、`--target` 這類旗標。

- **沒給**：用目前目錄。**相對路徑**一律先轉成絕對路徑；不往上層目錄找。
- **是資料夾**：要有 `.aos/tasks.json`，它就是這一格的任務表；不看 `.aos/inst.json`（tick 跟 inst.json 分開）。沒有 → stderr `no_tasks:`、回 1。
- **是檔**：這個檔就是這一格的任務表，它所在的資料夾當工作資料夾。
  - 檔在 `.aos/` 裡時取上一層：`aos-tick yyy/.aos/tasks.json` 等於 `aos-tick yyy`。`AOS_DIRNAME` 是空字串時不往上取，檔所在的資料夾照字面當工作資料夾。
  - 鎖、擋板檔、停格檔、紀錄都在那個工作資料夾的 `.aos/` 下，不在就建（只建資料夾）。工作資料夾自己的 `.aos/tasks.json` 在不在都不管。
- **不存在** → stderr `no_target:`、回 1。
- **表裡的相對路徑與指示詞**以工作資料夾為中心（給檔時也一樣，不是以那個檔為中心）。每一項當成一份獨立的文件，項目裡的 `$ref:""` 指這一項自己，不是整份任務表。

### 任務表

- **每項任務是 inst 的超集**：一份 [inst](../base/inst.md) 加 aos 的欄位（`id`、`kind`）。
- **先只定基本欄位**：不認得的鍵照收、核心忽略（任務是 inst 的超集，沿 [P-007](../protocol/README.md)）。第十九批的 `group`、`needs` 不再是欄位，寫了就當陌生鍵：前置改用包裝 `aos-needs`（B-621），組改由存檔點劃分（B-630）。第十七批的 `methods` 也拿掉了（使用者 2026-10-01），寫了一樣當陌生鍵。
- **`id`**：可以不寫。沒寫時，這一項的 id 就是它在 `tasks` 陣列的位置轉成字串（第 1 項是 `"0"`，第 4 項是 `"3"`）；紀錄、`AOS_TASK_ID`、`stopped_after` 都用它。跟別項寫的 id 撞了不管（默認不重複）。
- **`kind`**：可以不寫；只是標記（B-626），核心不看。
- **一個 module 一項任務**：產生請求、處理結果都在該項內做；要經佇列送的訊息交給系統級任務 `aos-mq post`（B-624）。檔案收件與投件是任務表上的普通任務，aos 不管（B-623、B-624）。
- 資源 module、`aos-clean`、收信程式都是同一張表上的項目，不分 pre／post 掛勾。有權限者也能直接跑這些程式；在 tick 外跑算外部世界（B-602）。資源 module 的啟用與父層限制見 [scheduling/admission](../scheduling/admission.md)。
- 開格讀過表之後、到跑到某項展開之前，假設檔案不會變，不為這種情況另做設計。

### 讀表：極簡檢查

開格時讀一次表，**只查這幾件**：

- 讀得到、是合法 JSON；
- 頂層是物件，而且有 `tasks` 陣列（可以是空的）；
- 每一項（整份 `$ref` 先展開，展開不了也算不過）是物件，而且有 `argv`。

**不過**：stderr 印一行 `bad_table: …`、回 1。這不算開過一格：不換紀錄、不加 `seq`，一項也不跑。

**其他一概不查**：外層與每項的 `_metainfo`、`id`、`kind` 填不填與它們的值、值的型別、`id` 重不重複、陌生鍵。格式上 `_metainfo` 仍照 P-202 寫，只是核心不擋。

- 每項沒寫 `_metainfo`：照 posix 第 1 版跑。
- 寫了但不對（或 inst 部分有別的錯）：跑到那一項、展開成 inst 時自然丟錯（traceback）、回 1；前面的項已跑，紀錄停在 `ended:false`。

### 誰驗什麼〔暫定〕

任務表的完整 schema（[P-202](protocol/node.md)）比核心查的多。分工如下：

| 檢查 | 誰驗、什麼時候 | 不合時 |
|---|---|---|
| 讀得到、合法 JSON、有 `tasks` 陣列、每項是物件且有 `argv` | 核心，每格開格 | `bad_table:`、回 1、不開格 |
| 每項的 inst 部分（`_metainfo`、`argv` 的型別、串流、`envs`…） | 核心，跑到那一項展開時 | 自然丟錯、回 1，紀錄停在 `ended:false` |
| 其餘 schema 限制：外層 `_metainfo`、`id` 的形狀、`kind` 的值（含 `system.x`） | 恢復前驗證（B-625）與建立 node 的工具；核心不驗 | 保持暫停、不 resume；核心照跑 |
| `id` 重複 | 沒人驗（默認不重複） | 核心照跑；靠 id 的系統級任務（例如 `aos-git` 的存檔點）自己會混淆 |
| 不認得的鍵（含 `group`、`needs`、`methods`） | 沒人驗 | 照收、核心忽略 |

所以核心看到缺 `kind` 或 `system.x` 的表照跑；要擋，就在改表後、resume 前照 B-625 驗。完整 schema 是給外部工具與恢復前驗證用的。

### 跑每一項

- 前一項結束才開下一項。每項結束後寫進結束碼紀錄（B-633）。
- **任務的結束碼完全不影響 tick**：回 0、1、2、125～127、被訊號殺，都照實記進紀錄、照常跑下一項。要判斷成敗的人照 [C-08](conventions.md) 只分 0 與非 0：正常退出 0 才算成功。普通程式回 125 不能猜成「沒跑」。
- **某項沒跑成**：mkdir、cwd、重導向的檔開不起來，記 `exit:125`（照 inst，跟 `aos-exec` 一致）；找不到程式記 127、沒執行權記 126。這幾種 stderr 另印一行 `exec_failed: <id>: 說明`。
- 「沒事做」可以不改檔、回 0。在途工作存在任務自己的領域狀態裡，不用特殊結束碼當排程訊號。
- 任務的 stdin、stdout、stderr 照各自的 inst 走（預設 `/dev/null`）。
- 核心在每項的環境多放下面這些變數（格式見 [P-203](protocol/node.md)，aos 全部的環境變數見 [C-10](conventions.md)）。命名規則：整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`。

| 變數 | 內容 |
|---|---|
| `AOS_TICK_CWD` | 工作資料夾的絕對路徑，也就是這一格 tick 的 cwd。本格紀錄在 `$AOS_TICK_CWD/.aos/tick/current.json`（B-633） |
| `AOS_TASK_ID` | 這一項的 id（沒寫 id 時是位置字串；id 不是字串時轉成字串） |
| `AOS_TASK_INDEX` | 這一項在任務表陣列的位置，從 0 起 |

- 其他環境變數（含 `AOS_DIRNAME`）任務照常繼承。這一項的 inst 用 `envs` 清空環境時，上表的變數也不放。
- 沒有 `AOS_TICK_LOCK_FD`（鎖 fd 不傳給任務，B-602）。

### 停格檔與擋板檔〔暫定〕

使用者 2026-10-01：擋板檔與停格檔的機制之後會詳細設計，下面是目前的做法。

任務能影響之後的項或之後的格，只有這兩個檔；**結束碼沒有特別意義**，任務回 3、100 都只是一般的非 0，照記、照跑。

| | 停格檔 `.aos/tick/stop` | 擋板檔 `.aos/tick-blocked` |
|---|---|---|
| 擋什麼 | **只擋本格**剩下的項；下一格照常開、照常跑 | 擋住**之後各格** |
| 誰建 | 任務。系統級任務與普通程式要叫停也建它 | 任務（例如發現需要人處理的故障）或人手；`aos-git` 故障時也寫它（B-622） |
| 內容 | 不拘，建議一行 UTF-8 原因 | 一行 UTF-8 原因 |
| 核心什麼時候看 | 每跑完一項就檢查 | 取鎖後、讀表前 |
| 核心看到時 | 不開後面的項；stderr 印 `stopped:` 加檔內原因；紀錄寫 `ended:true`、`exit:0` 與 `stopped_after`（在哪一項之後停，[P-213](protocol/node.md)）；這格回 0——該停就停，不算中斷 | 一項都不跑、不寫結束碼紀錄、不加 `seq`、不刪停格檔；stderr 印 `blocked:` 加檔內原因，回 0。所以人手或 cron 直接跑也被擋 |
| 誰刪 | 核心：換完紀錄後、開第一項前，刪掉上一格留下的 | **只有人手**，修好後刪；aos 不自動刪 |
| daemon | 不看它 | 現行 daemon 核心照常叫，由 `aos-tick` 自己擋；舊設計是有它就不開格（[B-607](deferred/daemon/registration.md)，在暫緩區） |

- **有 git 時，停格檔等於這格作廢**：排在後面的 `aos-git close` 不跑、不提交，下一格 `aos-git open` 把 aos 範圍還原（B-630）。想提早結束又保住結果的任務，別建停格檔，改讓後面的項讀紀錄自己跳過。〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-1〕
- 要知道這格是不是被停下，讀紀錄的 `stopped_after`；外層要分出 `busy`、`blocked`，看 stderr。

兩個檔都 ignored。使用者裁定的是分工：停格檔靠偵測檔案停掉本格、只在任務層面、daemon 不看、下一格核心開頭刪；擋板檔擋之後的格。檔名、內容、stderr 細節是〔建議預設，未拍板〕；兩種都回 0 照 [C-08](conventions.md)。

### 任務的帳號

- **任務沒有 `user`**〔使用者方向 2026-10-01〕：inst 頂層沒有 `user`（[inst](../base/inst.md)），任務是 inst 的超集，所以也沒有；寫了就是陌生鍵、照收不理，一律用 tick 自己的帳號跑。原本「帶了不同帳號就那一項回 125」的歷史記錄在[暫緩區](deferred/tick.md#暫緩b-620-任務的帳號125)，隨 `user` 一起撤回、不會回來。
- 要用別的帳號跑，就在 argv 包普通程式 `aos-as <帳號> -- 原指令`（[B-303](deferred/helper.md)，要 helper 與通道，都在暫緩區）；准不准照該 node 的身分額度核（[B-301](../base/identity-resources.md)）。
- 不另設服務帳號（第九批）；要 root 的固定步驟交給 helper（[B-609](deferred/daemon/helper-actions.md)）；管成員的事由上層 kernel 在自己的 tick 用自己的帳號做。任務類別不授予身分或權限。

### 核心的結束碼

照 [C-08](conventions.md)，`aos-tick` 只回 0 或 1，只講 tick 自己：

| 回 | 什麼時候 |
|---|---|
| `0` | 照表跑完（不管任務成敗、回幾）；被停格檔停下；拿不到鎖（`busy`）；有擋板檔（`blocked`） |
| `1` | argv 用法錯、`AOS_DIRNAME` 不合法、`no_target`、`no_tasks`、`bad_table`；tick 自用的檔（擋板檔、停格檔、`current.json`、`last.json`）讀不到、寫不進或格式壞——這種就讓程式自然丟錯（traceback 進 stderr），不分發生時機、不補救 |

stderr 的代碼一覽（格式見 [P-203](protocol/node.md)）：`usage`、`busy`、`blocked`、`stopped`、`no_target`、`no_tasks`、`bad_table`、`exec_failed`。

依據：使用者方向 2026-09-29；第十九批、第二十批改寫（核心）；第二十批（任務表先只定基本欄位、環境變數命名、停格檔與擋板檔並用）；第二十批疑點裁定 1（改：停掉本格靠偵測檔案，不靠結束碼）、8（tick 外跑算外部世界）；使用者 2026-10-01（目標改成位置參數、極簡檢查、`id` 與 `kind` 可省、拿掉 `methods`、撤回任務與 inst 的 `user`、結束碼照 C-08、`AOS_TICK_CWD`）。

**驗收：**

- 任務寫了 `user` 當陌生鍵照收，照 tick 自己的帳號跑。
- 任務回 1、2、125 或被訊號殺時照實記進紀錄、後面照跑，整格回 0。
- 某項建立 `.aos/tick/stop` 後，後面的項不跑，stderr 有 `stopped`，紀錄 `ended:true`、`exit:0` 並記 `stopped_after`，整格回 0；下一格照常跑。
- 任務表不是合法 JSON、沒有 `tasks` 陣列或某項缺 `argv`：stderr 有 `bad_table`、回 1，兩份紀錄與 `seq` 都不變。表裡 `id` 重複、缺 `kind`、沒有 `_metainfo` 都照跑。
- 第 4 項沒寫 id：紀錄裡與它的 `AOS_TASK_ID` 都是 `"3"`。
- 目標是資料夾但沒有 `.aos/tasks.json`：`no_tasks`、回 1；給不存在的路徑：`no_target`、回 1；什麼都不建。
- `aos-tick /m/t.json`：拿它當任務表，鎖與紀錄在 `/m/.aos/` 下；表裡相對的 `cwd` 以 `/m` 為中心。

## B-633：每項結束碼紀錄與格數

核心多開放一件事：**本格每一項怎麼結束，寫成一份檔，讓後面的任務讀得到。** 本資料夾的**格數**也記在這裡。這份紀錄直接取代第十九批的 git 備援日誌（B-632）：git 與無 git 合成同一種模式。

依據：第二十批追答 8、疑點裁定 5；修正輪暫定的裁定（格數不倒退改成不保證）；納入 cgroup／git 輪疑點 10：使用者 2026-09-30 同意照暫定；使用者 2026-10-01（默認紀錄是好的、`--firstdo-fsync` 先不做、拿掉 `AOS_TICK_RECORD`）。以下位置、欄位與寫法都是〔建議預設，未拍板〕。落盤、寫不進、讀不懂的處理在[暫緩區](deferred/tick.md#暫緩b-633-落盤寫不進與讀不懂)。

### 放哪、記什麼

兩個檔都 ignored：`.aos/tick/current.json`（本格）與 `.aos/tick/last.json`（上一格）。任務從 `$AOS_TICK_CWD/.aos/tick/current.json` 讀本格紀錄（狀態資料夾名照 `AOS_DIRNAME`）。格式見 [P-213](protocol/node.md)。**只有核心寫**，而且只在持鎖時寫。

| 欄位 | 意思 |
|---|---|
| `seq` | 格數（下面） |
| `tasks` | 已跑完的項，照順序；`id` 是任務表那一項的 id（沒寫 id 時是位置字串）；正常結束記 `exit`，被訊號結束記 `signal`；沒跑到的不列 |
| `ended` | 照表跑完、或被停格檔停下時寫成 true，同時加 `exit`＝這格 tick 的結束碼。有紀錄收尾時 tick 一定回 0，所以 `exit` 只會是 0：busy、blocked、bad_table 根本不寫紀錄；tick 中途出錯時紀錄停在 `ended:false` |
| `stopped_after` | 被停格檔停下時，是哪一項跑完後停的；記那一項的 id。這時 `exit` 也是 0 |
| `started_at_ms` | 只給人看，不參與計算 |

### 格數 `seq`

- 本資料夾第幾格，從 1 起，每格加 1。
- **跨重啟、換 daemon、改用 cron 都接著數。** aos 內部的時長與起算點都用它數（[C-01](../contracts.md)）。
- **斷電可能倒退，不保證**：預設不 fsync，斷電或 WSL 強關後 `seq` 可能退回幾格。依賴格數單調的地方——保留期與清理（[B-404](../base/storage.md)）、摘要的 `observed_seq`、以格數算的起算點（[C-01](../contracts.md)）——同樣不保證。保證不倒退的 `--firstdo-fsync` 在暫緩區。
- **沒有紀錄的格不佔號**：拿不到鎖（busy）、被擋板擋住（blocked）、表沒過極簡檢查（bad_table）的格，都不加 `seq`。這些格裡沒有任務拿得到 `seq`，所以下一格用同一個號也不會重複。
- 跟舊 daemon 每筆登記的 `tick_seq` 是兩回事：那個只用在叫醒後等新格，登記換了就重算（[B-607](deferred/daemon/registration.md)，在暫緩區）。

### 開格：換檔

讀表過了之後、刪停格檔之前（B-620「一格怎麼走」第 5 步）：

1. **算新的 `seq`**：有 `current.json` 就取它的 `seq` 加 1；沒有就取 `last.json` 的加 1；都沒有就是 1。默認兩份都讀得懂；讀不懂就自然丟錯、回 1。
2. **寫新紀錄**（`ended:false`、`tasks:[]`）到暫存檔。`.aos/tick/` 不在就建。
3. **換檔**：有 `current.json` 就 rename 成 `last.json`；沒有 `current.json` 卻有 `last.json`，表示上一格沒留下紀錄，就刪掉 `last.json`，讓讀的人看到「不知道上一格」。
4. 暫存檔 rename 成 `current.json`。

做完第 4 步才開第一項。

### 每項之後

- 整份重寫：寫暫存檔 → rename。不 fsync。
- 照表跑完、被停格檔停下時寫 `ended:true`、`exit:0`（停下的另加 `stopped_after`）。
- tick 中途出錯（自然丟錯）或被殺時，紀錄停在最後一次寫成的樣子，`ended:false`。

### 誰讀

- 任務讀 `current.json` 看本格前面各項，讀 `last.json` 看上一格有沒有正常收尾。
- **正常收尾**＝`ended:true` 而且沒有 `stopped_after`。
- 核心自己除了算 `seq`，不拿它做任何決定。

### 其他

- **被擋板檔擋住的格**不寫紀錄、不加 `seq`（B-620），跟 busy 一樣當成沒開過格。
- **別刪它**：`.aos/tick/` 不被 `aos-clean` 清；`aos-git` 固定排除它，不靠 `.gitignore`，提交與還原都不碰（B-622）。人手刪掉兩份檔，`seq` 從 1 重數，以格數算的保留期會算錯，風險自負。

**驗收：**有 `.aos/tick-blocked` 時直接跑 `aos-tick` 回 0、stderr 有 `blocked`、沒有任務跑、兩份紀錄與 `seq` 都不變，刪掉擋板後下一格照常；任務第二項讀得到第一項的結束碼；第三項被 SIGKILL 時紀錄是 `signal:9`；tick 在第二項中途被殺，下一格的 `last.json` 是 `ended:false`；同一資料夾連跑十格，`seq` 從 1 到 10，換成 cron 跑仍接著數；busy 或 bad_table 時兩份紀錄都不變。

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
| … | 使用者任務 | kernel／agent／custom | 各自的程式；要換帳號的包 `aos-as <帳號> --`，要前置的包 `aos-needs <前置 id…> --`，要每項一框的包 `aos-cg --`。檔案收件、檔案投件也是這裡的普通任務，aos 不管 | 各自 | [B-303](deferred/helper.md)、B-621、B-634、B-623、B-624 |
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
- **不在範本上的**：once 是任務自己呼叫的通道事務（[B-613](deferred/daemon/channel.md)）；重啟、格後收尾、排空、helper 歸 daemon（[B-601](deferred/daemon/runtime.md)、[B-603～605](deferred/daemon/README.md)、[B-609](deferred/daemon/helper-actions.md)；daemon 那側在暫緩區）。
- **通道**：daemon 開 tick 時給的通道（環境變數、憑證、事務）以 [B-612～614](deferred/daemon/README.md) 為正本（daemon 那側在暫緩區）。任務會繼承這些環境變數，在投件權就是執行權（[T-08](../terms.md)）之下這是預期行為。沒有通道（不是 daemon 開的格）只算功能受限：`aos-mq`、`aos-as`、once 用不了，其他照常。

依據：第二十批追答 8、9（推翻第十九批「標準配備：必須全掛、不能拆、跟核心同一支 `aos-tick`」「功能受限不算沒掛」「有備援就算全掛」）；第二十批進行順序、疑點裁定 3、4（存檔點、git 收尾之後才送）；astra 審整理區裁定（系統訊息佇列 `aos-mq` 取代收件與投件，順序照原位置）；aos-git 分工（系統級任務之間夾存檔點，範本自帶）。

**驗收：**沒有 git 版在沒有 git、沒有 cgroup 的機器上照常跑完；拿掉 `mq-post` 後 `.aos/mq/post/` 的訊息不送、其餘照常；拿掉 `mq-get` 後別的 tick 送來的訊息留在 daemon、其餘照常。有 git 版在有 git 的機器上每格最多一個 commit `aos-tick <seq>`；在沒有 git 的機器上 `aos-git` 三項只印 `no_git` 警告、回 0，其餘照沒有 git 版的結果。

## B-621：aos-needs：前置沒成功就不跑

`needs` 的意思不變：前置成功才執行。只是改成普通程式 `aos-needs`，核心不做。

- **`aos-needs <前置任務 id…> -- <原指令…>`**（argv 見 [P-204](protocol/node.md)）：讀本格的結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current.json`，B-633）。每個前置都在本格紀錄裡、而且正常退出 0，才 exec 原指令，結束碼就是原指令的；否則不跑，stderr 印 `needs_unmet: <id>`，回 125。沒有紀錄可讀（沒有 `AOS_TICK_CWD` 或讀不到）也回 125（`no_record`）。
- 前置只看本格：不沿用上一格的成功，也不另做跨格任務排程器。
- 被 `aos-needs` 擋下的項在紀錄裡是 `exit:125`，算失敗；再依賴它的項也會被擋。
- `aos-needs` 只擋後面的項不跑，自己不還原。失敗任務寫到一半的改動：有 git 時，aos 範圍裡的由它那組的存檔點還原（B-630）；使用者任務自己的檔、以及沒有 git 時的一切，都留在資料夾裡。
- 任務預設以正常退出且碼為 0 表示本步成功，不代表整件產品任務完成。

依據：使用者方向 2026-09-29（needs 的意思）；第二十批疑點裁定 2（改成普通程式）。

**驗收：**`aos-needs a -- …` 在 `a` 失敗或還沒跑時回 125、原指令沒跑，`a` 成功時照跑、結束碼是原指令的；`b` 被擋下後，`aos-needs b -- …` 也回 125。

## B-634：aos-cg：每項一框

〔使用者方向 2026-09-30，第二十批追答 8〕每項任務一框做成普通程式 `aos-cg`，要的任務自己在 argv 包：`aos-cg -- 原指令`（argv、代碼與結束碼見 [P-211](protocol/node.md)）。它不是系統級任務。框的樹與命名見 [B-605](deferred/daemon/cgroup.md)。**放棄「沒包的任務一結束就清殘留」**：沒包的任務留下的程序，等格後由 daemon 收（[B-601](deferred/daemon/runtime.md)；daemon 那側在暫緩區，現行 daemon 核心不收）。

| | 有 cgroup | 沒 cgroup |
|---|---|---|
| 什麼時候 | 自己在本 node 的 `n-<h>/tick` 框裡（看 `/proc/self/cgroup`） | 不在 node 框、沒有 cgroup v2，或框寫不進。人手或 cron 跑的格一律是這種 |
| 開框 | 在 `n-<h>` 下開 `task-<seq>-<pid>`（跟 `tick` 並列），把自己搬進去，再 fork＋exec 原指令、wait 主程序 | 不開框；stderr 印 `cgroup_unavailable`，設 `PR_SET_CHILD_SUBREAPER`，原指令另開程序群組 |
| 主程序結束後 | 框裡還有程序就直接寫 `cgroup.kill`（不先 TERM），看 `cgroup.events` 的 populated 變 0，再 rmdir | 對那個程序群組送 SIGKILL，再反覆收掛回自己的孤兒、逐一 SIGKILL 並 wait，到沒有為止 |
| 清不到的 | 經外部服務（`systemd-run --user`、`at`、cron）開的程序，會跑出 `n-<h>` | 同左，加上換成別的帳號的；也沒有上限、量測與 OOM 證據 |

- **清不空**：框一直不空時，stderr 印 `frame_not_empty`，建停格檔（[B-620](#b-620任務註冊表照表依序跑)）、回 1，不讓後面的項在還有人寫檔時開跑。
- **結束碼**照原指令；原指令被訊號結束時，`aos-cg` 用同一個訊號結束自己。
- **不放在 `tick` 底下**：cgroup v2 規定開了 controller 的那層不能同時放程序和子層。每項多約 0.1 毫秒（[實測](../../notes/probes/per-task-cgroup-cost.md)）。
- **跟 `aos-as` 一起用**：寫成 `aos-cg -- aos-as <帳號> -- 原指令`；`aos-as` 把自己所在的 `task-*` 框帶給 helper，別的帳號的程序也放進同一框（[B-303](deferred/helper.md)、[B-609](deferred/daemon/helper-actions.md)）。反過來寫開不了框，因為框不歸那個帳號。
- **不清上一格留下的 `task-*`**：只有 daemon 開的格才有 `task-*`，daemon 每格格後與重啟時都會收（[B-601](deferred/daemon/runtime.md)、[B-603](deferred/daemon/lifecycle.md)）。
- **跑出框的**：`setsid`、double fork 逃不出 cgroup；只有經外部服務開的逃得出。aos 不擋這條路（管轄權是約定，B-626），經外部服務開的不歸 aos 管。
- 〔暫定，第二十批疑-9 照 a〕沒 cgroup 時退回 subreaper 加程序群組，跟 daemon「沒有就退回」一致。

依據：第十七批（任務層框）；第二十批追答 8（改成普通程式 `aos-cg`、放棄沒包的任務一結束就清殘留）；第二十批疑-9（沒 cgroup 時的退回，暫定）；納入 cgroup 與 git 改寫計畫（拿掉開框前清舊 `task-*`；經外部服務開的不歸 aos 管）。

**驗收：**有 cgroup 時，包了 `aos-cg` 的項用 `setsid` 加 double fork 留下的程序，在它的 `task-*` 框被 `cgroup.kill`，下一項開跑時已經沒有；`aos-cg -- aos-as <帳號> --` 時別的帳號的程序也在同一框；框清不空時 `frame_not_empty`、建停格檔。沒 cgroup 時包了 `aos-cg` 的項留下、掛回 aos-cg 的後代也被清掉，stderr 有 `cgroup_unavailable`；沒包的任務留下的程序在 daemon 格後收尾時被清。

## B-623：系統訊息佇列：取件（mq-get）；檔案收件 aos 不管

**aos 只管系統訊息佇列。** 佇列是 aos 的系統級 IPC：同一個 daemon 底下的 tick 經通道互送訊息，daemon 替每個 tick 暫存（[B-614](deferred/daemon/messaging.md)）。**請求與回應都走佇列**〔使用者方向 2026-09-30，修正輪暫定的裁定〕。本條是取的那一側，送的那一側見 B-624。

| | 系統訊息佇列 | 檔案收件區（`requests/`、`responses/`） |
|---|---|---|
| 誰處理 | 系統級任務 `aos-mq get`（任務 id `mq-get`） | 任務表上的普通任務，aos 不管 |
| aos 規定什麼 | 只有它取；取出後怎麼分派不規定 | 不規定 |

### aos-mq get：只有它取

- **每個 node 只有 `aos-mq get` 用 `node.take` 取佇列**，其他任務不直接取。範本排在第一項（B-629）。
- 一格裡把佇列取到空為止（回應說還有就再取，[P-119](deferred/protocol/daemon/channel.md)）。請求與回應一起取出，不分兩個佇列。
- **取出後怎麼分派 aos 不管**：放哪、交給哪一項、先後怎麼排，由 `aos-mq get` 的實作決定，不在規範內。
- daemon 的憑證一格一張，分不出是哪一項在取，所以「只有它取」是同一個 node 裡的約定，不是授權（跟 [B-602](#b-602同一資料夾一次一格互斥鎖) 的鎖同一種）。
- 沒掛 `mq-get` 就沒人取：訊息留在 daemon，滿了寄件方收到 `mailbox_full`，daemon 重啟就丟（B-614）。
- 不保證送達；沒人取的也不回任何錯誤。
- 〔建議預設，未拍板〕daemon 訊息部件沒掛時，`node.take` 回空，`mq-get` 回 0；任務表不用改（[B-614](deferred/daemon/messaging.md)、[B-615](deferred/daemon/components.md)）。
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

- 任務把要送的訊息寫進追蹤的 `.aos/mq/post/<id>.req.json`（請求）或 `<id>.resp.json`（回應）（格式見 [P-206](protocol/node.md)）。`aos-mq post` 排在使用者任務之後（B-629），用 `node.send` 一件一件送進對方的佇列（[B-614](deferred/daemon/messaging.md)）。不寫對方的收件區。
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
| `not_available`〔建議預設，未拍板〕 | daemon 訊息部件關閉；同「送不了」搬到 `.aos/mq/failed/`、記代碼且不自動重試；本次有待送件就回 1，沒件照沒事做回 0（[B-614](deferred/daemon/messaging.md)）。任務表不用改 |
| 其他錯誤（`mailbox_full`、`stopping`、連不上 socket 等） | 留著，下一格再送 |
| 本格沒有通道（`no_channel`） | 一件都不送、檔都留著；stderr 印一次，回 0 |

### 送出之後

- **失敗紀錄只留一格**〔使用者方向 2026-09-30，修正輪暫定的裁定；誰清：使用者 2026-09-30 同意照暫定〕：`mq-post` 每次開始送之前，先刪掉 `.aos/mq/failed/` 裡的舊紀錄（都是前面各格留下的）。所以寄件的任務在下一格、`mq-post` 跑之前讀得到它；要留久一點就自己抄走。
- 送成功、還沒移除時當機：下一格再送同一份，對方可能拿到兩次；取的一方靠訊息 ID 去重。
- 有 git 時〔使用者 2026-09-30 同意照暫定〕，`mq-post` 移除已送檔這一步要到下一格的 `aos-git close` 才提交；下一格作廢的話，這些檔會被還原、再送一次。同樣靠 ID 去重（B-630）。
- 可重送同一份訊息：這只是補送，不授權重做不明的工具／LLM 執行。無可信結果、又不能證明未執行的工作記 unknown，不自動再執行（[S-401](../scheduling/operations.md)）。
- once 由 module 經通道用 `node.mount` 掛到 daemon（[B-613](deferred/daemon/channel.md)），不往 `.aos/mq/post/` 塞 IPC。
- 〔暫定〕**鬧鐘撤**：原本的鬧鐘看對方收件區的原件還在不在；aos 不再寫對方收件區，佇列裡的訊息 daemon 也不說有沒有被取走，所以 `alarm_ticks` 與 `.aos/alarms/` 撤出 aos。要等回覆的任務，自己在領域狀態裡記、自己以格數判逾時。

### 發布摘要〔建議預設，未拍板〕

- 發摘要任務 `aos-publish` 排在 `mq-post` 之後：把 `.aos/summary/summary.json` 目前的原 bytes，用暫存檔再 rename 的方式整份發布成 ignored 的 `.aos/summary/published.json`（格式與權限見 [P-307](../protocol/messages.md)），給只有摘要讀權的上層讀；讀者一次 open 就拿到完整一版。
- 有 git 版範本把它排在 `aos-git close` 之後，發布的就是剛提交的那一版；沒有 git 時不保證跟其他檔是同一版。
- 發布失敗：留舊值、stderr 報錯、回 1，下一格再發。過時或缺失不等於 idle。
- 有 repo 讀權的上層讀 `summary.json`，讀的是目前檔案。兩種讀法都要核對 `node_id` 是自己的直接下層（[B-628](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)，上下層判定在暫緩區）。
- 摘要是觀測，不能蓋掉較新的收件事件。上層不為了查詢而叫醒成員 tick，也不因要讀摘要就取得成員 repo 或下層內容的權限。

### 檔案投件 aos 不管

寫對方 `requests/`、`responses/` 的是普通程式：目標是不是 node、權限不夠、暫時性錯誤怎麼辦，都由那個程式定。原本「投件只查目標是不是 node」「`channel:true` 才改走通道、其餘走檔案」撤出基礎。

依據：使用者方向 2026-09-29；第十五批（鬧鐘，第二十批撤）；第十九批第 9 條與疑點裁定 6（經通道送）；第二十批疑點裁定 4、進行順序（送出排在使用者任務之後）；astra 審整理區同日定案（`aos-mq post` 只走通道，檔案投件是普通程式）；納入 cgroup 與 git 疑-4（送出與發摘要不認得 git，靠順序）；修正輪暫定的裁定（回應也走佇列；送不出去的留失敗紀錄、下一格清）。

**驗收：**`.aos/mq/post/` 有一件給同一 daemon 底下 tick 的訊息時，`mq-post` 經通道送出並移除該檔，對方的 `requests/` 沒有多出檔案；對方回 `mailbox_full` 時檔留著、下一格再送；目標不在這個 daemon（`not_registered`）時 stderr 有 `post_failed`、檔搬到 `.aos/mq/failed/`，下一格 `mq-post` 跑之前還讀得到、跑過之後就沒了；寫在 `.aos/mq/post/` 的回應物件同樣送進對方佇列；直接跑的格（沒有通道）檔都留著、回 0。

## B-625：當機恢復、設定與清理

本條同時寫有沒有 git 兩種情形；「有 git」指掛了 `aos-git` 三項而且 git 能用（B-630），其餘照沒有 git。

### 當機之後

**程序**：整機或 WSL VM 重開時舊程序本來就沒了。只有 daemon 自己重開時，舊程序可能還在：有 cgroup 時 daemon 先清空舊框才開格；沒有 cgroup 時清不掉（已接受），舊格的 tick 還握著鎖時新格印 `busy`、回 0，等它自己結束（[B-603](deferred/daemon/lifecycle.md)；daemon 那側在暫緩區）。

**檔案**：當在哪一步，下一格看到的：

| 當在哪 | 有 git | 沒有 git |
|---|---|---|
| 使用者任務或清理途中、`aos-git close` 提交前 | `last.json` 是 `ended:false`；下一格 `aos-git open` 把 aos 範圍還原到 HEAD，這格作廢。使用者任務自己的檔留著，由任務自己的狀態恢復 | 寫到一半的改動留在資料夾裡，由各任務自己的狀態恢復 |
| `aos-git close` 提交後、`mq-post` 或發摘要途中 | 已提交的都在。`mq-post` 已送、還沒移除的訊息：移除那一步沒提交，會被 open 還原回來，下一格再送；對方靠請求 ID 去重（B-624）。摘要下一格再發 | 已送、還沒移除的下一格再送；摘要下一格再發 |

- **未明的工具／LLM 請求**：按 Q2（B-624）處理。能恢復本地 tick，不等於能重做 unknown 外部工作。

### 改設定〔暫定，astra 審整理區必-5〕

| 改什麼 | 怎麼改 |
|---|---|
| 普通設定（`config/` 裡的檔） | 在 tick 外用 `aos-config-add`（argv 見 [P-207](protocol/node.md)）：非阻塞取同一把 `.aos/tick.lock`（B-602），拿不到回 75（它自己特別指定的碼，[C-08](conventions.md)）；有擋板檔就不寫、回 125。寫法：在目標旁寫完整暫存檔 → fsync → rename 替換 → fsync 目錄。沒變動就不寫。不能在同 node 的 tick 內呼叫 |
| 重要設定（inst 的身分、任務表）與其他手改 | 先 `node.pause`，等 `node.show` 看到 `running:false`，持 node 鎖修改，照下面驗過再 resume（[B-607](deferred/daemon/registration.md)，舊 daemon 的做法，在暫緩區） |

- tick 裡的任務不改 `config/` 是軟性原則，不檢查也不阻擋；同一格新舊設定混用的風險由寫任務的人承擔（[A-102](../agent/configuration.md)）。
- **有 git 時**〔暫定〕：
  - `config/` 不在 aos 範圍（B-630），`aos-config-add` 也不自己提交；要留歷史就自己 `git commit`。
  - inst 與任務表在 `.aos/` 底下，屬 aos 範圍：格間手改的下場照 [B-602](#b-602同一資料夾一次一格互斥鎖)「tick 外的寫入者」，上一格沒正常收尾時會被還原，所以改完自己提交。

### 恢復前驗證

resume 之前，持同一把鎖依序檢查：

1. inst：照 [inst 目標](../base/inst.md#inst-目標檔案或資料夾)選 inst，驗原始結構。
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
- **沒有 daemon 的格後收尾**：任務留下的後代沒人收。它們不握鎖（B-602），下一格照常開。
- **不在 node 框裡**：包了 `aos-cg` 的項照沒 cgroup 的做法退回（B-634）。

其餘照常：

- 同一資料夾 daemon 正在跑一格時，直接跑的那格拿不到鎖、印 `busy`、回 0（B-602）；反過來也一樣。
- 直接跑的格同樣寫結束碼紀錄、同樣加 `seq`（B-633）。
- 想經 daemon 跑一格：現行 daemon 用控制模組的 `wake`（[B-641](daemon/control.md)）。舊設計（在暫緩區）是送 `node.wake`，以回應的值為起點，再用 `node.show` 等格次前進；怎樣算新的一格已完成、`registration_id` 換了怎麼辦，以 [B-607](deferred/daemon/registration.md) 為正本。不另開「跑一格並等結果」的 IPC。CLI 入口見 [H-004](../cli/commands.md)。

依據：第十九批第 12 條（撤第十八批審稿裁定 16「不在框就拒跑」）；第十九批疑點裁定 11（記錄者歸類：需要通道的事算功能受限）。

**驗收：**不經 daemon 直接跑 `aos-tick` 照常做完一格；daemon 正在跑同一資料夾時直接跑印 `busy`、回 0、不改檔；直接跑與 daemon 跑交替時 `seq` 連續。

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
- **多帳號**：`aos-as` 開的程序寫進 aos 範圍的檔，要讓 tick 帳號讀得到（例如 [B-609](deferred/daemon/helper-actions.md) 的共享群組），否則 git 讀不到，當故障。

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
| `-c gc.auto=0 -c maintenance.auto=false` | 不讓 aos 自己那幾次呼叫觸發背景整理；背景程序違反「不准背景程序繞過 tick」〔使用者方向 2026-09-30〕 |
| 〔建議預設〕`-c core.hooksPath=/dev/null`、`-c commit.gpgSign=false`、`-c safe.directory=<node 根>` | 不跑 hooks；使用者全域開了簽章也不會卡住；node 根的擁有者跟 tick 帳號不同時（[B-203](../base/execution.md) 的兩種主人）git 仍肯動 |

- **不動使用者的設定**：上面都是命令列參數，只管 aos 自己那幾次呼叫。git 的背景整理（gc、maintenance）aos 不管；文件建議使用者自己關掉（例如 `git config gc.auto 0`、`git config maintenance.auto false`），要整理就先暫停 node 再手動跑。
- **環境**〔建議預設〕：呼叫前清掉所有繼承的 `GIT_*`，只設自己要的，免得操作到別的 repo。
- **作者**〔建議預設〕：用 repo 設定；repo 與全域都沒設時用 `aos <aos@localhost>`，不擋。
- **不在 tick 內**：沒有繼承到鎖時回 125、印 `not_in_tick`；人手要提交就直接用 git。這個核對靠「鎖 fd 傳給任務」，那段在[暫緩區](deferred/tick.md#暫緩b-602-完整互斥的其餘細節)；最簡鎖不傳 fd，回來之前這條核對還沒有判法。

### 範圍怎麼切

- **固定排除**：不管 `.gitignore` 寫了什麼，[P-200](protocol/node.md) 表裡 ignore 的核心檔一律不提交、不還原：`.aos/tick.lock`、`.aos/tick/`、`.aos/tick-blocked`、`.aos/jobs/`、`.aos/attention/`、`.aos/runner-stderr.log`、`.aos/summary/published.json`、`.aos/mq/failed/`、`requests/`、`responses/`、`work/`。否則 `.gitignore` 漏列時，結束碼紀錄會被還原、`seq` 倒退。
- **巢狀**：下層 tick 的資料夾（判準照 [B-628](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)；那條在暫緩區，回來前沒有正式判準）寫進 git 管理目錄的 `info/exclude`，不改 `.gitignore`。open、mark、close 存之前都重掃一次，免得格中新建的子 node 被上層提交（已追蹤的檔不會因為之後才排除就不追）。子 node 自己是 repo 時不進去。
- **不遍歷**：不用全樹 `git clean -x`，不進 git 管理目錄或子 repo。

### 故障

還原、存檔點、commit 失敗，HEAD 被換（B-630 open 第 4 步），任務 `id` 當不了 ref 名（`mark_id_invalid`，例如以 `.lock` 結尾），在 tick 內卻沒有結束碼紀錄（`record_missing`）：

1. 寫擋板檔、建停格檔、回 1；
2. 舊 daemon 照 [B-607](deferred/daemon/registration.md) 不再開格（在暫緩區；現行由 `aos-tick` 自己看擋板），錯誤摘要走[待處理事項](../scheduling/operations.md)；
3. 修復者暫停、持鎖、核對、自己提交修好的改動，再移除擋板。

### 其他

- **原子**只指同一 repo 裡 aos 範圍的已提交版本與恢復基線；使用者任務自己的檔、ignored 檔、另一個 repo、外部 workspace 與不可逆後果，都不會跟著還原。
- 〔使用者方向 2026-09-29〕別濫用 git：沒變動不 commit；可定期合併提交、可用 submodule。合併提交要暫停、持鎖；submodule 不承諾跨 repo 的組原子性。

依據：使用者方向 2026-09-29（每個 node 一個 repo、別濫用 git）；第十八批第 17 條、Q31（落盤）；納入 cgroup 與 git 疑-5（不能用就警告、照沒 git 做）；同日裁定（背景整理 aos 不管，自己呼叫時帶 `gc.auto=0`、`maintenance.auto=false`）。

**驗收：**`.gitignore` 拿掉 `/.aos/tick/` 後 `seq` 仍連續、紀錄不進 commit；格中用 `aos node new` 建的子 node 不進上層的 commit；格結束後沒有 aos 自己叫起來的 git 背景程序留下；node 根擁有者跟 tick 帳號不同時照常提交；使用者全域開了 commit 簽章也照常提交；滿碟時 commit 失敗：擋板＋停格檔，`mq-post` 不跑。

## B-631：（撤）cgroup 框的備援

〔使用者方向 2026-09-30，第二十批追答 8〕撤：tick 側的 cgroup 備援（開格設 subreaper、每項後殺程序群組並掃孤兒、`RLIMIT_AS`／`RLIMIT_CPU`、getrusage）與完整／備援對照表。每項一框改成普通程式 `aos-cg`（B-634）；daemon 側的收尾見 [B-604](deferred/daemon/lifecycle.md)。

## 驗收與尚未定案

當機、Q1／Q2、設定的故障驗收，統一見 [V-03](../conformance.md)。

註冊表格式以協議篇為準。〔使用者方向 2026-09-30，第二十批〕任務表先只定基本欄位，`group`、`needs` 當陌生鍵（2026-10-01 起 `methods` 也是）。上下層判定、完整互斥、帳號核對、紀錄落盤與失效處理在 [tick 暫緩區](deferred/tick.md)。停格檔的位置、結束碼紀錄的位置與欄位、各系統級任務與普通程式的程式名都是工程預設。git 與 cgroup 是有就用（B-630、B-622、B-634）；這輪先寫成暫定的列在 [README 疑點](README.md#疑點)。
