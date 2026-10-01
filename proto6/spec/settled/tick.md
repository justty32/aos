# 通用 tick：核心

← [整理區](README.md)｜[名詞](terms.md)｜[慣例](conventions.md)｜[daemon](daemon/README.md)｜格式：[tick 協議](protocol/tick.md)｜系統級任務、範本與普通程式：[tick 子篇](tick/README.md)｜先不做的：[tick 暫緩區](deferred/tick.md)、[helper 與 aos-as](deferred/helper.md)

依據：[09-29 新架構](../../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../../notes/verdicts/09-special-computing-os.md)、[第十九批](../../notes/verdicts/10-tick-minimal-core.md)、[第二十批](../../notes/verdicts/11-tick-as-unit.md)與它篇末 2026-10-01 各節；現行程式 [proto6/src/py](../../src/py/README.md)。

讀之前先知道四件事：

- **本篇只寫已實作的核心**（B-626、B-602、B-620、B-633、B-627），由現行程式 `aos-tick` 實作。普通程式 `aos-cg`、tick 模組與 hooks 在 [tick 子篇](tick/README.md)（系統級任務與範本第十八批全部搬暫緩區；`aos-tick-check-task` 第十六批、`aos-git` 第十七批），一篇一個主題，大多還沒有程式，每篇開頭標了狀態。〔astra 報告建議 1；使用者 2026-10-01〕
- **工作資料夾**（英文 `tick dir`）＝這一格 `aos-tick` 跑的資料夾（它的 cwd），由命令列給的目標決定（`aos-tick [<目標>]`，B-620）。tick 這層只講工作資料夾；「node」是之後 node 模組才出場的詞，暫緩區講上下層時的「上層 node／下層 node」照舊。〔使用者 2026-10-01〕
- 「任務表」指工作資料夾裡的任務註冊表 `.aos/tasks.json`，跟舊 daemon 的登記表是兩回事（[T-02](../terms.md)）。
- 本篇寫的 `.aos/…` 都是環境變數 `AOS_DIRNAME` 沒設時的樣子（[C-09](conventions.md)）；結束碼照 aos 慣例：0＝預料之中、非 0＝要處理、1＝通用錯誤（[C-08](conventions.md)）。

## 先講重點

- **tick 是一個定期被執行的程式**（`aos-tick`）。誰來跑都行：daemon、cron、人手（B-627）。它執行時的目前目錄（cwd）就是它的**管轄區**，也就是工作資料夾。
- **核心只做三件事**：同一資料夾一次一格的簡單互斥鎖（B-602）、照任務表依序跑（B-620）、每項結束碼紀錄（B-633）。上下層判定（B-628）已搬到[暫緩區](deferred/tick.md)。
- **hooks（外掛掛點）**：任務表頂層鍵 `hooks`，跟 `tasks` 同層（[B-635](tick/hooks.md)）。目前只開 `after_all`：照表跑完（含被 tasks-blocked 擋下）之後跑一串 inst，寫法比照 `tasks`，碼記進紀錄的 `hooks.after_all`、不影響 tick 的結束碼。〔使用者 2026-10-01 第六批〕
- **任務怎麼結束都不影響 tick 的結束碼**：任務回幾都照實記進紀錄、照常跑下一項。tick 自己只回 0 或 1。
- **tick 是整個 aos 的衡量基準**：排程以格計，反應最快是下一格；aos 內部的時長與起算點都用本資料夾的格數（B-633、[C-01](../contracts.md)）。
- tick 不跟 once、LLM 嘗試、agent 一輪這些計算單位共用外殼（[T-07](terms.md)）。
- **git 與 cgroup 是「有就用」，不是前提。** 沒有 git、沒有 cgroup 時照原來的做法跑（[B-632](deferred/git.md)、[B-601](deferred/daemon/runtime.md)）。
  - **git**：〔使用者 2026-10-01 第十七批〕`aos-git` 整套暫緩（[暫緩區 git](deferred/git.md)）；要用 git 就用 hooks 加普通 git 指令（[B-635 範例](tick/hooks.md#範例用-hook-加普通-git-指令管版本)）。以下是暫緩前的規定：掛了 `aos-git` 三項系統級任務而且 git 能用，aos 自己的東西（`.aos/`、任務表、系統級任務動到的檔）才有提交與還原（[B-630、B-622](deferred/git.md)）。使用者任務改的檔 aos 不提交、不還原；`AOS_DIRNAME` 是空字串時例外，整個工作資料夾都算 aos 的（[B-630](deferred/git.md)）。
  - **cgroup**：工作資料夾的框與資源上限歸舊 daemon（[B-605](deferred/daemon/cgroup.md)，在暫緩區）；每項一框要任務包普通程式 `aos-cg`（[B-634](tick/cg.md)）。
- **收送**：〔使用者 2026-10-01 第十八批〕現行任務之間收發信用 daemon 訊息模組 `aos-mq send`／`take`（[B-645](daemon/mq.md)），任務直接叫，不是系統級任務。〔暫緩〕原本工作資料夾之間經舊 daemon 的通道互送訊息，由系統級任務 `aos-mq get`／`aos-mq post` 處理（[B-623、B-624](deferred/mq.md)）。檔案收件區 `requests/`、`responses/` 的收與寫是普通程式的事，aos 不管。
- **保證跟著「掛了什麼」走**：核心三件事（B-626）不靠任何系統級任務也成立；其餘保證看任務表掛了哪幾項系統級任務、任務包了哪些普通程式。〔建議預設，未拍板〕各條只寫「掛了時保證什麼」，沒掛的後果不逐條寫。

依據：第十八批（外殼）；第十九批（定期被執行的程式、管轄區）；第二十批（衡量基準、進行順序；推翻第十九批「本篇的保證以標準配備全掛為前提」與完整／備援兩級）；使用者 2026-10-01（POC 默認一切正常、核心縮成三件事、目標改成位置參數、工作資料夾、拆篇）。

## B-626：核心與系統級任務的界線

tick 裡的東西分四類：

| 類 | 是什麼 | 有哪些 |
|---|---|---|
| tick 核心 | `aos-tick` 本身，只做三件事 | 簡單互斥鎖（B-602）、照任務表依序跑（B-620）、每項結束碼紀錄（B-633） |
| 系統級任務 | 從核心拆出、掛在任務表上的獨立程式，以 `kind:"system"` 標記；**寫在表上才跑，沒寫就不跑** | 〔使用者 2026-10-01 第十八批〕**現行沒有系統級任務，全部在暫緩區**：系統訊息佇列 `aos-mq get`／`aos-mq post`（[B-623、B-624](deferred/mq.md)，用途已被 daemon 訊息模組 [B-645](daemon/mq.md) 取代）、清理 `aos-clean`（[B-404](../base/storage.md) 的系統級任務那部分，現在沒東西可清）、git 開格／存檔點／收尾 `aos-git`（[B-630](deferred/git.md)，第十七批）；標準任務表範本（[B-629](deferred/template.md)）跟著暫緩 |
| 普通程式 | 任務會用到的工具；不是系統級任務 | 要的任務自己在 argv 包的：每項一框 `aos-cg`（[B-634](tick/cg.md)）；〔暫緩，第十六批〕自己占一項、檢查前面的項沒跑好就停格的 `aos-tick-check-task`（[B-621](deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)，2026-10-01 取代包裝 `aos-needs`）。發布摘要 `aos-publish` 2026-10-01 搬到[暫緩區](deferred/tick.md#暫緩b-624-發布摘要aos-publish) |
| 其他任務 | kernel、agent、clock、檔案收件程式、自訂任務等 | 它們的外殼、逾時與取消延後（[P-008](../protocol/README.md#p-008)）；檔案收件 aos 不管（[B-623](deferred/mq.md)） |

**核心**：照表跑時另外只認兩個檔——tasks-blocked 與擋板檔（B-620，只看存不存在）；**任務沒有 `user`**（寫了照陌生鍵），一律用 tick 自己的帳號跑。核心只要 Python 3.9 與 flock，不靠 daemon、git、cgroup、helper，也不靠任何系統級任務。上下層判定原本是第四件事，使用者 2026-10-01 說「也不需要判斷上下層」，整條搬到[暫緩區](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)。

**系統級任務**：

- 〔使用者 2026-10-01 第十八批〕現行沒有系統級任務（上表），下面幾點是這個類別本身的規定，留給之後回來的系統級任務用。
- 各自是獨立的程式，彼此只靠檔案（結束碼紀錄、`.aos/mq/post/`）交接，不靠任務 `id` 相認。〔暫緩〕標準任務表範本就是預設的一組（[B-629](deferred/template.md)）。
- `kind:"system"` 的意思是「這一項是系統級任務」。它只是標記：核心不看，也不授予身分或權限；`system` 不開放自訂子名（`system.x`，[T-06](../terms.md)；誰擋見 B-620「誰驗什麼」）。
- 〔建議預設，未拍板〕不檢查 kind 的先後（撤掉第十九批暫定的「system 最前、custom 最後」）：範本的系統級任務分在頭尾兩段，照陣列順序就好。
- 〔暫緩，第十八批〕`aos-clean` 也是系統級任務，範本裡寫 `kind:"system"`。

**daemon 不在任務表上**：現行 daemon 核心只定期叫 `aos-exec`，不認得 node（[T-11](terms.md)、[B-640](daemon/core.md)）。舊設計裡一格結束後殺殘留、重啟、排空停機、helper 歸 daemon（[B-601](deferred/daemon/runtime.md)、[B-603～605](deferred/daemon/README.md)、[B-609](deferred/daemon/helper-actions.md)），這些在暫緩區。

**管轄權是約定，不是前提**：tick 對管轄區有最高裁量權，這是 aos 體系裡的約定。Linux 權限上碰不到某些東西時，tick 照樣跑完一格，碰不到的那件照各自規則失敗。管轄區可以重疊，風險自己承擔；aos 體系裡的慣例是不重疊、可以包含（上下層怎麼算在暫緩區，B-628）。

依據：第二十批追答 8、9（推翻第十九批「三層：核心／標準配備／其他掛載」、疑點裁定 1「標準配備跟核心同一支 `aos-tick`、不另做包裝」；`kind:"system"` 取代第十九批「留給以後真正屬於標準配備的任務、範本沒有 system 類」；`aos-clean` 取代第十九批疑點裁定 2「範本裡仍是 custom 類」）；第十九批第 2、5 條（管轄權）；astra 審整理區裁定（收送改成系統訊息佇列 `aos-mq`，檔案收件與投件是普通程式、aos 不管）；使用者 2026-10-01（核心不判上下層、不看 `user`）。

**驗收：**拿掉 daemon、git、cgroup、helper 與所有系統級任務，任務表只放一項 `true`，直接跑 `aos-tick`：互斥、照表跑與結束碼紀錄照常成立，回 0；任務寫了 `user` 也當陌生鍵、照 tick 自己的帳號跑；佇列沒人取也沒人送。

## B-602：同一資料夾一次一格：互斥鎖

**同一資料夾同時只能跑一個 tick。** 這把鎖屬核心，不靠 git、cgroup 或 daemon。

現在只做最簡版（使用者 2026-10-01：外層定期跑 `aos-tick`，上一格沒跑完下一格就來，是正常使用會碰到的）。鎖 fd 傳給任務、後代擋下一格等完整細節在[暫緩區](deferred/tick.md#暫緩b-602-完整互斥的其餘細節)。

### 鎖怎麼取

- **認哪個資料夾**：照 B-620「認哪個資料夾」（`aos-tick [<目標>]`，argv 見 [P-203](protocol/tick.md)）。tick 在那個工作資料夾裡跑，cwd 就是它。
- **鎖檔**：`.aos/tick.lock`，ignored。不存在就建（`.aos/` 不在也建）；tick 自己不刪它。不放在 git 管理目錄；`aos-clean` 與一般清理都不得移除或替換它，`aos-git` 固定排除它，提交與還原都不碰（[B-622](deferred/git.md)）。
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

〔暫緩，第十七批 `aos-git` 搬暫緩區〕有 git 時，人手改到 aos 範圍（[B-630](deferred/git.md)）的東西，aos 也不替它另外做什麼：

| 上一格 | 格間手改的下場 |
|---|---|
| 正常收尾 | 被下一格的 `aos-git close` 跟著提交 |
| 沒正常收尾 | 被下一格的 `aos-git open` 還原掉 |

所以要手改工作資料夾：先停住排程（經 daemon 跑的用 `aos-ctl pause`，[B-641](daemon/control.md)；舊設計的 `node.pause` 見 [B-607](deferred/daemon/registration.md)，在暫緩區），改完要保住就自己 `git commit`。〔使用者 2026-10-01〕aos 不另存救援副本。

依據：第十九批（核心；第 7 條認資料夾）；第二十批（核心不清後代）、疑點裁定 8（取代第十九批建議預設「其他寫入者也須協調這把鎖或先暫停 tick」）；納入 cgroup 與 git 疑-3（人手改的不管、不做救援 ref）；使用者 2026-10-01（最簡互斥、拿不到回 0、鎖 fd 不傳給任務）。

**驗收：**同資料夾同時跑兩個 `aos-tick`（第一格的任務卡住）：後到的那個印 `busy`、回 0，兩份紀錄與 `seq` 都不變；第一格照常跑完，之後下一格照常。用絕對路徑、相對路徑、不給目標（cd 進去）各跑一次，搶的是同一把鎖〔使用者 2026-10-01：目標只能是資料夾〕。任務的環境裡沒有 `AOS_TICK_LOCK_FD`，前一格的任務留下的後代還在跑時，下一格照樣拿得到鎖。沒有 git repo 也取得到鎖。

## B-620：任務註冊表：照表依序跑

任務表只有一個位置：工作資料夾的 `.aos/tasks.json`（`AOS_DIRNAME` 是空字串時就是 `tasks.json`）〔使用者 2026-10-01〕。**陣列位置就是順序**，核心照順序一項一項跑。欄位、JSON 與 schema 以 [P-202](protocol/tick.md) 為準，本節只定意思。

### 一格怎麼走

1. 認工作資料夾與任務表（下面「認哪個資料夾」）；不對就回 1。
2. 取鎖（B-602）；拿不到印 `busy`、回 0。
3. 看擋板檔；在就直接回 0、stderr 不印、不開格（下面「tasks-blocked 與擋板檔」）。
4. 讀表、做極簡檢查（下面「讀表」）；不過就印 `bad_table`、回 1，不開格。
5. 換一份新的結束碼紀錄（B-633）。做到這一步才算開了一格、佔一個 `seq`。
6. 照陣列順序跑每一項：每一項之前看 tasks-blocked，在就這一項與後面都不跑；每項結束後寫紀錄。
7. 有寫 `hooks.after_all` 就跑那一串（[B-635](tick/hooks.md)，不看 tasks-blocked、碼只記下）；**所有 hooks 跑完才紀錄收尾（`ended:true`）**〔使用者 2026-10-01 第十八批〕。〔第十七批〕`hooks.before_all` 在第 5 步之後、第一項之前跑；`after_task.<id>`、`after_every_task` 在每一項跑完之後跑。
8. 刪掉 tasks-blocked（有的話）。
9. 回結束碼（下面「核心的結束碼」）。

### 認哪個資料夾：目標

`aos-tick [<目標>]`，目標是位置參數，跟 `aos-exec` 一樣；沒有 `--node`、`--target` 這類旗標。

- **沒給**：用目前目錄。**相對路徑**一律先轉成絕對路徑；不往上層目錄找。
- **是資料夾**：要有 `.aos/tasks.json`，它就是這一格的任務表；不看 `.aos/inst.json`（tick 跟 inst.json 分開）。沒有 → stderr `no_tasks:`、回 1。
- **是檔**：用法錯，stderr `usage: …`、回 1，什麼都不建。〔使用者 2026-10-01：拿掉「目標給檔就當任務表」；原規則記在[暫緩區撤回表](deferred/tick.md#已撤回被取代)〕
- **不存在** → stderr `no_target:`、回 1。
- **表裡的相對路徑與指示詞**以工作資料夾為中心；什麼時候展開、`$ref:""` 指哪裡，見下面「指示詞什麼時候展開」。

### 任務表

- **每項任務是 inst 的超集**：一份 [inst](../base/inst.md) 加 aos 的欄位（`id`、`kind`）。
- **先只定基本欄位**：不認得的鍵照收、核心忽略（任務是 inst 的超集，沿 [P-007](../protocol/README.md)）。第十九批的 `group`、`needs` 不再是欄位，寫了就當陌生鍵：前置原本改用 `aos-tick-check-task`（[B-621](deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)，第十六批搬暫緩區），組改由存檔點劃分（[B-630](deferred/git.md)）。第十七批的 `methods` 也拿掉了（使用者 2026-10-01），寫了一樣當陌生鍵。
- **`id`**：可以不寫。沒寫時，這一項的 id 就是它在 `tasks` 陣列的位置轉成字串（第 1 項是 `"0"`，第 4 項是 `"3"`）；紀錄、`AOS_TASK_ID`、`blocked_before` 都用它。跟別項寫的 id 撞了不管（默認不重複）。
- **`kind`**：可以不寫；只是標記（B-626），核心不看。
- **一個 module 一項任務**：產生請求、處理結果都在該項內做；〔暫緩〕要經佇列送的訊息交給系統級任務 `aos-mq post`（[B-624](deferred/mq.md)）。檔案收件與投件是任務表上的普通任務，aos 不管（[B-623](deferred/mq.md)、[B-624](deferred/mq.md)）。
- 資源 module、`aos-clean`、收信程式都是同一張表上的項目，不分 pre／post 掛勾。有權限者也能直接跑這些程式；在 tick 外跑算外部世界（B-602）。資源 module 的啟用與父層限制見 [scheduling/admission](../scheduling/admission.md)。
- 開格讀過表之後就不再讀：〔第二十批〕指示詞在開格時全部展開完，之後被引用的檔怎麼變都不影響這一格。
- **`tasks` 維持陣列**；頂層除了 `tasks` 還可以放每一項的預設（下面「頂層預設」）、`modules` 與外掛掛點 `hooks`（[B-635](tick/hooks.md)）。

### 頂層預設〔使用者 2026-10-01〕

- **可當預設的鍵**：頂層可以放 inst 的七個欄位 `argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`，當每一項的預設。
- **不是預設的鍵**：頂層的 `_metainfo` 照舊是整份表的格式標記（可省〔使用者裁定 2026-10-01〕）；`id`、`kind` 是 aos 欄位；`modules` 見下一節。頂層其他鍵照舊當陌生鍵忽略。
- **淺層合併**：項自己寫了某個鍵，就整個蓋過頂層那個鍵。`envs` 也是整包換掉，不逐變數合併。
- **頂層 `cwd` 不改 tick 自己的 cwd**：tick 永遠在工作資料夾跑（鎖、紀錄、tasks-blocked 都在工作資料夾的 `.aos/`）；頂層 `cwd` 只是任務的預設 cwd，相對路徑以工作資料夾為起點，跟項自己寫的 cwd 一樣。跟 daemon 設定檔頂層 `cwd` 的對照見 [C-11](conventions.md)。

例子（頂層 `_metainfo` 可省、核心不查，這裡照 [P-202](protocol/tick.md) 寫上）：

```json
{
  "_metainfo": {"_type": "aos-tasks", "_version": 1},
  "cwd": "work",
  "envs": {"LANG": "C.UTF-8"},
  "stdout": {"$opt": "append", "$val": "logs/tasks.log"},
  "tasks": [
    {"id": "build", "argv": ["make"]},
    {"id": "report", "argv": ["./report.sh"], "cwd": "reports"},
    {"$ref": "tasks.d/clean.json"}
  ]
}
```

- `build` 在 `<工作資料夾>/work` 跑，輸出接在 `work/logs/tasks.log`。
- `report` 自己寫了 cwd，在 `<工作資料夾>/reports` 跑；stdout 預設照用，接在 `reports/logs/tasks.log`（stdout 以解出的 cwd 為中心）。
- 第三項整項從 `<工作資料夾>/tasks.d/clean.json` 讀，再套預設。

### 頂層 `modules`〔使用者 2026-10-01〕

- 頂層可選 `modules` 鍵，比照 daemon 設定檔的 `modules`（[B-640](daemon/core.md)、[P-120](protocol/daemon/core.md)）：放 tick 模組的設定，一個模組一個鍵。
- 目前 tick 只認一個模組 `tasks-blocked`（[B-636](tick/tasks-blocked.md)；〔第二十批〕由 `tasks_blocked` 改名，跟檔名一樣）；其他鍵照收不理，型別也不查。外掛掛點 `hooks` 不是模組，是跟 `tasks` 同層的頂層鍵（[B-635](tick/hooks.md)；使用者 2026-10-01 第六批：「就不讓他當模組了，直接讓他變頂層key」），寫在 `modules.hooks` 底下不會跑。
- 它不是 inst 欄位，**不當任務預設值合併**。
- **讀表時整個展開指示詞**〔使用者裁定 2026-10-01；第二十批起整份 tasks.json 都這樣，`tasks-blocked` 不再例外〕：跟 daemon 設定檔一樣一路走進物件與陣列，不是只解一層。`$ref:""`／`#…` 指整份 tasks.json、相對檔名以工作資料夾為起點（跟讀表其他部分一致）。展開失敗＝`bad_table`、回 1。~~原本只解一層、內部留給模組~~（[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）。

### 指示詞什麼時候展開〔使用者 2026-10-01 第二十批：「tasks.json改成全部解完」「除了陌生鍵和_metainfo」〕

**開格時整份展開**，跟 daemon 設定檔的展開同一做法（一路走進物件與陣列）；不再「只解到每一項那一層、內部跑到才解」（~~第二批原話：「展開指示詞的時候不整份解好，而是只解到tasks。」~~ 第二十批推翻）。用 `Document(表的路徑, 整份)`、中心路徑＝工作資料夾。

- **整個展開的**：整份文件本身（是指示詞就先解）；頂層七個預設欄位；`tasks`、`hooks` 各掛點（`before_all`、`after_task.<id>`、`after_every_task`、`after_all`）與 `modules["tasks-blocked"].insts` 的每一元素——元素整項解一層（整項 `$ref`）後，裡面**已知的鍵**（七個 inst 欄位、`id`、`kind`）整個展開；`modules`（含 `tasks-blocked`，不再例外）。
- **不解、原樣留的**：頂層的陌生鍵與 `_metainfo`；每一項裡的 `_metainfo`（留給 inst 規則驗）與陌生鍵（例如 `group`、`needs`、`methods`）；`hooks` 裡不認得的掛點。所以陌生鍵裡寫壞的指示詞不影響開格。
- **選項物件**（`$opt`）：`$opt` 原樣留，`$val` 也整個展開；展開完只剩選項物件，沒有取值指示詞。
- **展開失敗**（任何一個要展開的鍵）＝`bad_table`、回 1、不開格（不換紀錄、不加 `seq`，一項也不跑）。
- **跑到某一項時**：頂層預設＋這一項淺層合併（項蓋過），交給 inst 規則（[inst](../base/inst.md)）——這時已經沒有指示詞可解，只剩路徑換算（`cwd` 以工作資料夾為中心、其他路徑以解出的 cwd 為中心）、選項物件、`_metainfo` 與型別檢查。

**第二十批改了的語意**：

- `$ref:""`／`#…` 一律指整份 tasks.json（整項 `$ref` 引進來的元素裡則指被引用的那份檔），**不再指「合併後的這一項」**。
- `$ref` 的相對檔名一律以工作資料夾為準，**不以那一項的 cwd 為準**。
- `$env`／`$fmt`／`$ref` 讀到的是**開格那一刻**的值：前面的任務改了被引用的檔或環境，後面的項看不到。
- 讀不到的 `$ref`（例如指向前面任務才會產生的檔）開格就是 `bad_table`。
- 「跑到某項時才展開失敗」不再發生；跑到時還會出錯的只剩 inst 規則本身（`_metainfo` 不對、型別不對…），照下面「誰驗什麼」自然丟錯。

### 讀表：極簡檢查

開格時讀一次表（照上面「指示詞什麼時候展開」整份展開），**只查這幾件**：

- 讀得到、是合法 JSON；
- 頂層是物件，而且有 `tasks` 陣列（可以是空的）；
- 每一項（整項解一層後）是物件；
- 每一項合併頂層預設後有 `argv`：項自己有，或頂層有。〔使用者 2026-10-01〕
- 有寫頂層 `hooks` 時：它是物件；`before_all`、`after_every_task`、`after_all` 有寫時是陣列，`after_task` 有寫時是物件、每個值是陣列；每項是物件、合併頂層預設後有 `argv`（[B-635](tick/hooks.md)）。

任何一個要展開的鍵展開失敗，也算不過〔第二十批〕。

**不過**：stderr 印一行 `bad_table: …`、回 1。這不算開過一格：不換紀錄、不加 `seq`，一項也不跑。

**其他一概不查**：外層與每項的 `_metainfo`、`id`、`kind` 填不填與它們的值、值的型別（含頂層預設與 `modules`）、`id` 重不重複、陌生鍵。

〔使用者裁定 2026-10-01〕`_metainfo` 都可省：外層的不是必填，核心不看；每項的照 inst（aos-exec）的規則。

- 每項沒寫 `_metainfo`：照 posix 第 1 版跑。
- 寫了就照 inst 規則驗，但跑到那一項才驗（讀表時不看）。寫了但不對（或合併後的 inst 部分有別的錯）：跑到那一項、展開成 inst 時自然丟錯（traceback）、回 1；前面的項已跑，紀錄停在 `ended:false`。

### 誰驗什麼〔暫定〕

任務表的完整 schema（[P-202](protocol/tick.md)）比核心查的多。分工如下：

| 檢查 | 誰驗、什麼時候 | 不合時 |
|---|---|---|
| 讀得到、合法 JSON、有 `tasks` 陣列、每項是物件、合併預設後有 `argv`、讀表那一層指示詞解得開、`modules` 整個展開得了 | 核心，每格開格 | `bad_table:`、回 1、不開格 |
| 每項合併預設後的 inst 部分（`_metainfo` 照 inst 規則、`argv` 的型別、串流、`envs`…） | 核心，跑到那一項展開時 | 自然丟錯、回 1，紀錄停在 `ended:false` |
| 其餘 schema 限制：外層 `_metainfo`、`id` 的形狀、`kind` 的值（含 `system.x`） | 工具或人工在 `aos-ctl resume` 前先驗（恢復前驗證，[B-625](tick/recovery.md)；daemon 不代驗），以及建立工作資料夾的工具；核心不驗 | 由驗的人保持暫停、不 resume；核心照跑〔astra 報告必修 2〕 |
| `id` 重複 | 沒人驗（默認不重複） | 核心照跑；靠 id 的系統級任務（例如 `aos-git` 的存檔點）自己會混淆 |
| 不認得的鍵（含 `group`、`needs`、`methods`） | 沒人驗 | 照收、核心忽略 |

所以核心看到缺 `kind` 或 `system.x` 的表照跑；要擋，就在改表後、`aos-ctl resume`（[B-641](daemon/control.md)）前由工具或人照 [B-625](tick/recovery.md) 先驗，daemon 不代驗〔astra 報告必修 2〕。完整 schema 是給外部工具與恢復前驗證用的。

### 跑每一項

- 前一項結束才開下一項。每項結束後寫進結束碼紀錄（B-633：`ran` 加 1，結束碼不是 0 才記進 `tasks`）。
- **先合併再展開**〔使用者 2026-10-01〕：跑到某一項時，頂層預設＋這一項（項蓋過）合成一份記憶體 inst，照上面「指示詞什麼時候展開」展開後執行。
- **任務的結束碼完全不影響 tick**：回 0、1、2、125～127、被訊號殺，都照常跑下一項；不是 0 的照實記進紀錄（0 不記，只算進 `ran`，B-633）。要判斷成敗的人照 [C-08](conventions.md) 只分 0 與非 0：正常退出 0 才算成功。普通程式回 125 不能猜成「沒跑」。
- **某項沒跑成**：mkdir、cwd、重導向的檔開不起來，記 `exit:125`（照 inst，跟 `aos-exec` 一致）；找不到程式記 127、沒執行權記 126。這幾種 stderr 另印一行 `exec_failed: <id>: 說明`。
- 「沒事做」可以不改檔、回 0。在途工作存在任務自己的領域狀態裡，不用特殊結束碼當排程訊號。
- 任務的 stdin、stdout、stderr 照合併後的 inst 走（都沒寫時預設 `/dev/null`）。
- 核心在每項的環境多放下面這些變數（格式見 [P-203](protocol/tick.md)，aos 全部的環境變數見 [C-10](conventions.md)）。命名規則：整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`（hook 改給 `AOS_HOOK_*`；`before_all`、`after_all` 不給 `AOS_TASK_*`，`after_task`、`after_every_task` 另給剛跑完那一項的 `AOS_TASK_*` 與 `AOS_TASK_EXIT`，[B-635](tick/hooks.md)）。

| 變數 | 內容 |
|---|---|
| `AOS_TICK_CWD` | 工作資料夾的絕對路徑，也就是這一格 tick 的 cwd。本格紀錄在 `$AOS_TICK_CWD/.aos/tick/current/`（B-633；`record.json` 加上它 `$ref` 的檔） |
| `AOS_TASK_ID` | 這一項的 id（沒寫 id 時是位置字串；id 不是字串時轉成字串） |
| `AOS_TASK_INDEX` | 這一項在任務表陣列的位置，從 0 起 |

- 其他環境變數（含 `AOS_DIRNAME`）任務照常繼承；繼承來的 `AOS_TASK_*`（含 `AOS_TASK_EXIT`〔使用者 2026-10-01 第十七批〕）、`AOS_HOOK_*`（例如這個 tick 本身是別的 tick 的任務）先拿掉再放這一項的，任務拿不到 `AOS_HOOK_*`、`AOS_TASK_EXIT`。這一項的 inst 用 `envs` 清空環境時，上表的變數也不放。
- 沒有 `AOS_TICK_LOCK_FD`（鎖 fd 不傳給任務，B-602）。

### tasks-blocked 與擋板檔〔暫定〕

使用者 2026-10-01：擋板檔與 tasks-blocked 的機制之後會詳細設計，下面是目前的做法。**tasks-blocked 的內容已定案**〔使用者 2026-10-01 第十八批：「3.對，我就不想了。」〕：tick 只看存不存在、永遠不讀內容；內容要寫什麼、怎麼用，交給 `modules.tasks_blocked` 的 insts 自己讀（[B-636](tick/tasks-blocked.md)）。〔使用者 2026-10-01 第十六批〕原停格檔 `tick/stop` 改名 `tick/tasks-blocked`：「然後是stop，我要稍微改個名字：.aos/tick/tasks-blocked。」改成每一項之前看、內容 tick 不管、整格最後 tick 自己刪：「task_blocked要改成tick在最後會自動刪掉。然後tasks-blocked中的內容，tick不管。」擋板檔改成只看存不存在、直接結束、stderr 不印：「正常機制結束的話stderr不應該印東西。hook也根本不會啓動。」

任務能影響之後的項或之後的格，只有這兩個檔；**結束碼沒有特別意義**，任務回 3、100 都只是一般的非 0，照記、照跑。

| | tasks-blocked `<狀態資料夾>/tick/tasks-blocked` | 擋板檔 `<狀態資料夾>/tick-blocked` |
|---|---|---|
| 擋什麼 | **本格**還沒跑的項（含正要跑的那一項） | 擋住**之後各格**，直到有人刪 |
| 誰建 | 任務、hook，或在格與格之間由人或別的程式放 | 任務（例如發現需要人處理的故障）或人手；`aos-git` 故障時也寫它（[B-622](deferred/git.md)） |
| 內容 | **tick 不管**，只看存不存在（空檔、資料夾、讀不到、壞 symlink 都算在） | **tick 不看**，只看存不存在；要寫原因給人看可以 |
| 核心什麼時候看 | **每一項跑之前**（含第一項） | 取鎖後、讀表前 |
| 核心看到時 | 這一項與後面的都不跑；**stderr 不印**（正常機制）；紀錄寫 `ended:true`、`exit:0` 與 `blocked_before`＝被擋下、沒跑的那一項（[P-213](protocol/tick.md)）；`after_all` 照跑（它跟任務無關，[B-635](tick/hooks.md)）；這格回 0 | 直接結束：一項都不跑、hooks 不啟動、不寫結束碼紀錄、不加 `seq`；**stderr 不印**（正常機制結束不印，[C-08](conventions.md)），回 0。所以人手或 cron 直接跑也被擋 |
| 誰刪 | **核心，整格最後**：`after_all` 跑完、回結束碼之前（〔AI 隊定、可改〕被擋下的格與最後才出現的〔例如 hook 寫的〕都刪；開格時不刪；是資料夾就整個刪） | **只有人手**，修好後刪；aos 不自動刪 |
| daemon | 不看它 | 現行 daemon 核心照常叫，由 `aos-tick` 自己擋；舊設計是有它就不開格（[B-607](deferred/daemon/registration.md)，在暫緩區） |

- **掛了 tick 模組 `modules["tasks-blocked"]`**（[B-636](tick/tasks-blocked.md)，第十六批）時，看到 tasks-blocked 不直接擋下：先依序跑那一串 inst（拿被擋下那一項的 `AOS_TASK_ID`／`AOS_TASK_INDEX`、碼不記），跑完再看一次，檔被刪了就放行這一項與後面的，還在才擋下。
- **開格時不刪**：格與格之間有人放的 tasks-blocked，下一格第一項之前就擋下（`ran:0`、`blocked_before` 是第一項），整格最後再刪。
- **跟 hooks**：hook 之間不看 tasks-blocked（hook 寫的也不擋下一個 hook，只擋下一項任務），整格最後一樣刪。被擋下、沒跑的任務不觸發 `after_task`、`after_every_task`；任務跑完接著跑它的 hook 時不看 tasks-blocked〔第十六批〕。`before_all` 在第一項的檢查之前跑，它寫的 tasks-blocked 會擋下第一項〔第十七批〕。
- 〔暫緩，`aos-git` 第十七批搬暫緩區〕**有 git 時，tasks-blocked 等於這格作廢**：排在後面的 `aos-git close` 不跑、不提交，下一格 `aos-git open` 把 aos 範圍還原（[B-630](deferred/git.md)）。想提早結束又保住結果的任務，別建它，改讓後面的項讀紀錄自己跳過。〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-1〕
- 要知道這格是不是被擋下，讀紀錄的 `blocked_before`；外層要分出 `busy` 看 stderr。被擋板檔擋下的格什麼都不留（stderr 空、紀錄與 `seq` 不變），要知道就自己看擋板檔在不在。
- **tick 子篇裡還沒實作的程式**（`aos-git`、`aos-cg`、`aos-mq` 等）寫「建停格檔」的地方，現在讀成「建 tasks-blocked」；它們的設計是照舊停格檔寫的，回來實作時要照上表重看。

兩個檔都 ignored。檔名、stderr 細節是〔建議預設，未拍板〕；兩種都回 0 照 [C-08](conventions.md)。

使用者 2026-10-01 第十六批：「我們可以弄一個tick的module，用於設定讀取tasks-blocked的時候，要做的事情，類似hook，但是是在發現有tasks-blocked這個檔案之後，要做的insts」——已做成 tick 模組 `modules["tasks-blocked"]`（[B-636](tick/tasks-blocked.md)）。〔未來方向，記錄用、現在不做〕更早第五批記過的方向（停格檔變成特定 JSON、`aos-tick-check-task-continue` 檢查與改寫它）由 tick 那側來看已被第十八批定案取代（tick 不讀內容）；內容格式要怎麼用是 `tasks-blocked` insts 的事；會建停格檔的普通程式 `aos-tick-check-task`（[B-621](deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）第十六批搬暫緩區。

### 任務的帳號

- **任務沒有 `user`**〔使用者方向 2026-10-01〕：inst 頂層沒有 `user`（[inst](../base/inst.md)），任務是 inst 的超集，所以也沒有；寫了就是陌生鍵、照收不理，一律用 tick 自己的帳號跑。原本「帶了不同帳號就那一項回 125」的歷史記錄在[暫緩區](deferred/tick.md#暫緩b-620-任務的帳號125)，隨 `user` 一起撤回、不會回來。
- **tick 不切帳號**。要用別的帳號跑，就在 daemon 設定檔把它拆成另一項、指定帳號（帳號模組 `modules.account`，[plan m3m 模組五](../../plan/m3m-daemon-modules.md#模組五帳號modulesaccount)，還沒做）；單位是 daemon 的一項，不在一格裡面中途換。在 argv 包 `aos-as <帳號> --` 的做法〔使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」〕搬到暫緩區（[B-303](deferred/helper.md)、[P-212](deferred/protocol/tick.md#p-212aos-as切換帳號建議預設未拍板)）。
- 不另設服務帳號（第九批）；要 root 的固定步驟交給 helper（[B-609](deferred/daemon/helper-actions.md)）；管成員的事由上層 kernel 在自己的 tick 用自己的帳號做。任務類別不授予身分或權限。

### 核心的結束碼

照 [C-08](conventions.md)，`aos-tick` 只回 0 或 1，只講 tick 自己：

| 回 | 什麼時候 |
|---|---|
| `0` | 照表跑完（不管任務成敗、回幾）；被 tasks-blocked 擋下；拿不到鎖（`busy`）；有擋板檔（stderr 不印） |
| `1` | argv 用法錯（含目標是檔）、`AOS_DIRNAME` 不合法、`no_target`、`no_tasks`、`bad_table`；tick 自用的檔（`tick/current/`、`tick/last/` 裡的紀錄檔；擋板檔與 tasks-blocked 只看存不存在、不讀，不在此列〔使用者 2026-10-01 第十六批〕）讀不到、寫不進或格式壞——這種就讓程式自然丟錯（traceback 進 stderr），不分發生時機、不補救 |

stderr 的代碼一覽（格式見 [P-203](protocol/tick.md)）：`usage`、`busy`、`no_target`、`no_tasks`、`bad_table`、`exec_failed`。（擋板檔、tasks-blocked 擋下時不印，第十六批拿掉 `blocked`、`stopped`。）

依據：使用者方向 2026-09-29；第十九批、第二十批改寫（核心）；第二十批（任務表先只定基本欄位、環境變數命名、停格檔與擋板檔並用）；第二十批疑點裁定 1（改：停掉本格靠偵測檔案，不靠結束碼）、8（tick 外跑算外部世界）；使用者 2026-10-01（目標改成位置參數、極簡檢查、`id` 與 `kind` 可省、拿掉 `methods`、撤回任務與 inst 的 `user`、結束碼照 C-08、`AOS_TICK_CWD`）；使用者 2026-10-01 第二批（目標只能是資料夾、tasks.json 頂層預設、指示詞只解到 tasks、頂層 `modules`）；同日第三批（`_metainfo` 可省、每項照 inst、`modules` 讀表時整個展開）；同日第六批（頂層 `hooks` 外掛掛點，[B-635](tick/hooks.md)）。

**驗收：**

- 任務寫了 `user` 當陌生鍵照收，照 tick 自己的帳號跑。
- 任務回 1、2、125 或被訊號殺時照實記進紀錄（`id`、`index` 與碼）、後面照跑，整格回 0；回 0 的項不記。
- 某項建立 `.aos/tick/tasks-blocked` 後，後面的項不跑、stderr 空，紀錄 `ended:true`、`exit:0` 並記 `blocked_before`（下一項），`after_all` 照跑，整格回 0、最後 tasks-blocked 被刪；下一格照常跑。格與格之間放的：第一項就被擋（`ran:0`）。
- 任務表不是合法 JSON、沒有 `tasks` 陣列或某項缺 `argv`：stderr 有 `bad_table`、回 1，兩份紀錄與 `seq` 都不變。表裡 `id` 重複、缺 `kind`、沒有 `_metainfo` 都照跑。
- 第 4 項沒寫 id：它的 `AOS_TASK_ID` 是 `"3"`；它失敗時紀錄裡那筆是 `"id":"3","index":3`。
- 目標是資料夾但沒有 `.aos/tasks.json`：`no_tasks`、回 1；給不存在的路徑：`no_target`、回 1；什麼都不建。
- 給檔（例如 `aos-tick /m/t.json`、`aos-tick /m/.aos/tasks.json`）：stderr 是 `usage: …`、回 1，什麼都不建。〔使用者 2026-10-01〕
- 頂層 `cwd:"work"`：沒寫 cwd 的項在 `<工作資料夾>/work` 跑，鎖與紀錄仍在工作資料夾的 `.aos/`；項自己寫了 `envs` 時頂層 `envs` 整包不用。某項沒 `argv`、頂層也沒有：`bad_table`、回 1；頂層有 `argv` 時只寫 `id` 的項照跑。帶 `modules` 的表照跑、`modules` 不進任何一項；`modules` 裡解不開的 `$ref`＝`bad_table`、回 1〔使用者裁定 2026-10-01〕。頂層與每項都沒寫 `_metainfo` 照跑；某項 `_metainfo` 寫成 `posix` 第 2 版：前面的項照跑，跑到它時丟錯、回 1。〔使用者 2026-10-01〕

## B-633：每項結束碼紀錄與格數

核心多開放一件事：**本格跑了幾項、哪幾項結束碼不是 0，寫成一份檔，讓後面的任務讀得到。**〔使用者 2026-10-01 第八批：「tasks如果結果是0，那就不用紀錄了。hooks也是。」〕 本資料夾的**格數**也記在這裡。這份紀錄直接取代第十九批的 git 備援日誌（[B-632](deferred/git.md)）：git 與無 git 合成同一種模式。

依據：第二十批追答 8、疑點裁定 5；修正輪暫定的裁定（格數不倒退改成不保證）；納入 cgroup／git 輪疑點 10：使用者 2026-09-30 同意照暫定；使用者 2026-10-01（默認紀錄是好的、`--firstdo-fsync` 先不做、拿掉 `AOS_TICK_RECORD`）；同日第八批（只記不是 0 的、加 `ran`，[verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）；同日第九批（紀錄拆檔、用 `$ref` 引用）。以下位置、欄位與寫法都是〔建議預設，未拍板〕。落盤、寫不進、讀不懂的處理在[暫緩區](deferred/tick.md#暫緩b-633-落盤寫不進與讀不懂)。

### 放哪、記什麼

一格的紀錄是一個資料夾，兩個都 ignored：`.aos/tick/current/`（本格）與 `.aos/tick/last/`（上一格，同結構）。任務從 `$AOS_TICK_CWD/.aos/tick/current/` 讀本格紀錄（狀態資料夾名照 `AOS_DIRNAME`）。格式見 [P-213](protocol/tick.md)。**只有核心寫**，而且只在持鎖時寫。

〔使用者 2026-10-01 第九批〕「current.json這邊，也要引入指示詞，把容易被改動的弄成$ref指向其他檔案，不容易被改動的留在current.json」：常變的欄位各自一個檔，`record.json` 用 `$ref`（[指示詞](../../../proto5/spec/directives/README.md)）指過去：

| 檔 | 內容 | 什麼時候寫 |
|---|---|---|
| `record.json` | `version`、`seq`、`started_at_ms`、`ended`、`exit`、`blocked_before`，加上 `"ran":{"$ref":"ran.json"}`、`"tasks":{"$ref":"task-exits.json"}`，有 hooks 時再加 `"hooks":{"$ref":"hook-exits.json"}`（開格就加，〔第十七批〕） | 開格一次、收尾一次 |
| `ran.json` | 一個數字＝下表的 `ran` | 開格寫 `0`，每跑完一項重寫 |
| `task-exits.json` | 下表的 `tasks`（陣列） | 開格寫 `[]`，有項結束碼不是 0 才重寫 |
| `hook-exits.json` | 下表的 `hooks`（各掛點一個陣列） | 任務表有寫 hooks 掛點時，〔第十七批〕**開格**就寫好各掛點的 `[]`；之後有 hook 不是 0 才重寫 |

`$ref` 都是相對路徑（相對 `record.json` 所在資料夾），整個資料夾改名成 `last/` 後仍指得對。讀的一方展開 `record.json` 頂層各鍵的 `$ref`，得到下表的完整紀錄。下表講的都是展開後的欄位。

| 欄位 | 意思 |
|---|---|
| `seq` | 格數（下面） |
| `ran` | 本格到目前為止跑完幾項（含失敗的；被 tasks-blocked 擋掉、沒跑到的不算）。開格時 0，每跑完一項加 1 |
| `tasks` | 已跑完**而且結束碼不是 0** 的項，照順序；每筆 `{"id","index","exit"}`：`id` 是任務表那一項的 id（沒寫 id 時是位置字串），`index` 是它在 `tasks` 陣列的位置；被訊號結束的記 `signal` 不記 `exit`。結束碼 0 的不記、沒跑到的不列 |
| `ended` | 照表跑完、或被 tasks-blocked 擋下，而且**所有 hooks（含 `after_all`）跑完之後**〔使用者 2026-10-01 第十八批〕寫成 true，同時加 `exit`＝這格 tick 的結束碼。tick 在跑 hook 時被殺，紀錄停在 `ended:false`。有紀錄收尾時 tick 一定回 0，所以 `exit` 只會是 0：busy、blocked、bad_table 根本不寫紀錄；tick 中途出錯時紀錄停在 `ended:false` |
| `blocked_before` | 〔使用者 2026-10-01 第十六批〕（原 `stopped_after`）被 tasks-blocked 擋下時，被擋下、沒跑的那一項的 id（就是位置 `ran` 那一項；第一項就被擋時 `ran` 是 0）。這時 `exit` 也是 0 |
| `started_at_ms` | 只給人看，不參與計算 |
| `hooks` | 任務表有寫 hooks 掛點時才有（開格就有）：寫了哪幾個掛點就有哪幾個鍵，每個格式跟 `tasks` 相同、一樣只記不是 0 的；`after_task`、`after_every_task` 每筆另帶 `task_index`〔第十七批〕；hooks 不記 `ran`（[B-635](tick/hooks.md)） |

### 格數 `seq`

- 本資料夾第幾格，從 1 起，每格加 1。
- **跨重啟、換 daemon、改用 cron 都接著數。** aos 內部的時長與起算點都用它數（[C-01](../contracts.md)）。
- **斷電可能倒退，不保證**：預設不 fsync，斷電或 WSL 強關後 `seq` 可能退回幾格。依賴格數單調的地方——保留期與清理（[B-404](../base/storage.md)）、摘要的 `observed_seq`、以格數算的起算點（[C-01](../contracts.md)）——同樣不保證。保證不倒退的 `--firstdo-fsync` 在暫緩區。
- **沒有紀錄的格不佔號**：拿不到鎖（busy）、被擋板擋住（blocked）、表沒過極簡檢查（bad_table）的格，都不加 `seq`。這些格裡沒有任務拿得到 `seq`，所以下一格用同一個號也不會重複。
- 跟舊 daemon 每筆登記的 `tick_seq` 是兩回事：那個只用在叫醒後等新格，登記換了就重算（[B-607](deferred/daemon/registration.md)，在暫緩區）。

### 開格：換紀錄

讀表過了之後、開第一項之前（B-620「一格怎麼走」第 5 步）：

1. **算新的 `seq`**：有 `current/record.json` 就取它的 `seq` 加 1；沒有就取 `last/record.json` 的加 1；都沒有就是 1。默認兩份都讀得懂；讀不懂就自然丟錯、回 1。
2. **寫新紀錄**到暫存資料夾 `.aos/tick/.current.tmp/`：`record.json`（`ended:false`）、`ran.json`（`0`）、`task-exits.json`（`[]`）。`.aos/tick/` 不在就建；上次留下的暫存資料夾先刪。
3. **換紀錄**：刪掉 `last/`；有 `current/` 就把整個資料夾 rename 成 `last/`。沒有 `current/` 卻有 `last/`，表示上一格沒留下紀錄，刪掉之後讀的人看到「不知道上一格」。
4. 暫存資料夾 rename 成 `current/`。

做完第 4 步才開第一項。

### 每項之後

- `ran` 加 1（重寫 `ran.json`）；結束碼不是 0（含被訊號殺）才在 `tasks` 加一筆（重寫 `task-exits.json`，先於 `ran.json`）。
- 每個檔都整份重寫：寫同資料夾的暫存檔 → rename。不 fsync。`record.json` 這時不動。
- 照表跑完、被 tasks-blocked 擋下，**`after_all` 也跑完之後**〔使用者 2026-10-01 第十八批〕重寫 `record.json`：`ended:true`、`exit:0`（擋下的另加 `blocked_before`；`hooks` 的 `$ref` 開格時已經在）。所以 hook 跑的時候讀到的本格紀錄都還是 `ended:false`。
- tick 中途出錯（自然丟錯）或被殺時，紀錄停在最後一次寫成的樣子，`ended:false`。

### 誰讀

- 任務讀 `current/` 看本格前面跑了幾項（`ran`）、哪幾項失敗（`tasks`），讀 `last/` 看上一格有沒有正常收尾。讀的時候展開 `record.json` 的 `$ref`（Python 版：`aos_tick_record.read_record(資料夾)`）。某項不在 `tasks` 裡＝它成功或還沒跑到；要分這兩種，比它的位置跟 `ran`。
- **正常收尾**＝`ended:true` 而且沒有 `blocked_before`。
- 核心自己除了算 `seq`，不拿它做任何決定。

### 其他

- **被擋板檔擋住的格**不寫紀錄、不加 `seq`（B-620），跟 busy 一樣當成沒開過格。
- **別刪它**：`.aos/tick/` 不被 `aos-clean` 清；`aos-git` 固定排除它，不靠 `.gitignore`，提交與還原都不碰（[B-622](deferred/git.md)）。人手刪掉兩份紀錄，`seq` 從 1 重數，以格數算的保留期會算錯，風險自負。

**驗收：**有 `.aos/tick-blocked` 時直接跑 `aos-tick` 回 0、stderr 是空的、沒有任務跑、兩份紀錄與 `seq` 都不變，刪掉擋板後下一格照常；第一項回 7 時第二項讀得到 `ran:1`、`tasks:[{"id":…,"index":0,"exit":7}]`，第一項回 0 時讀到 `ran:1`、`tasks:[]`；第三項被 SIGKILL 時紀錄那筆是 `"index":2,"signal":9`；tick 在第二項中途被殺，下一格的 `last/` 是 `ended:false`；同一資料夾連跑十格，`seq` 從 1 到 10，換成 cron 跑仍接著數；busy 或 bad_table 時兩份紀錄都不變；`current/` 裡有 `record.json`、`ran.json`、`task-exits.json` 三個檔（有 hooks 時多 `hook-exits.json`），`record.json` 的 `ran`、`tasks` 是 `$ref`，換成 `last/` 後展開結果不變。

## B-627：人手或 cron 直接跑一格：風險自負

`aos-tick` 誰都能直接跑（人手、cron、其他程式），照常做完一格；風險由跑的人自己承擔。

**現行 daemon 跑的格跟直接跑一樣**〔astra 報告必修 1〕：現行 daemon 核心只是定期叫 `aos-exec`（[B-640](daemon/core.md)），不給通道、不做格後收尾、不開框，所以經它跑的格跟人手、cron 直接跑的沒有差別。擋板檔也一樣：daemon 照常叫，由 `aos-tick` 自己擋（B-620）。

下面三點差別**只適用舊 daemon**（[暫緩區](deferred/daemon/README.md)）：舊 daemon 開的格有，直接跑的格（以及現行 daemon 跑的格）都沒有。

- **沒有通道**：once、系統訊息佇列用不到（`aos-mq` 什麼都不做、回 0），`aos-as` 回 125（`no_channel`）。需要通道的事一律算功能受限，不另設替代路。
- **沒有 daemon 的格後收尾**：任務留下的後代沒人收。它們不握鎖（B-602），下一格照常開。
- **不在工作資料夾的框裡**：包了 `aos-cg` 的項照沒 cgroup 的做法退回（[B-634](tick/cg.md)）。

其餘照常：

- 同一資料夾 daemon 正在跑一格時，直接跑的那格拿不到鎖、印 `busy`、回 0（B-602）；反過來也一樣。
- 直接跑的格同樣寫結束碼紀錄、同樣加 `seq`（B-633）。
- 想經 daemon 跑一格：現行 daemon 用 `aos-ctl wake`（[B-641](daemon/control.md)）。舊設計（在暫緩區）是送 `node.wake`，以回應的值為起點，再用 `node.show` 等格次前進；怎樣算新的一格已完成、`registration_id` 換了怎麼辦，以 [B-607](deferred/daemon/registration.md) 為正本。不另開「跑一格並等結果」的 IPC。CLI 入口見 [H-004](../cli/commands.md)。

依據：第十九批第 12 條（撤第十八批審稿裁定 16「不在框就拒跑」）；第十九批疑點裁定 11（記錄者歸類：需要通道的事算功能受限）；使用者 2026-10-01（最核心 daemon 只定期叫 `aos-exec`）。

**驗收：**不經 daemon 直接跑 `aos-tick` 照常做完一格；有擋板檔時現行 daemon 照常叫、`aos-tick` 印 `blocked`、回 0；daemon 正在跑同一資料夾時直接跑印 `busy`、回 0、不改檔；直接跑與 daemon 跑交替時 `seq` 連續。

## 驗收與尚未定案

當機、Q1／Q2、設定的故障驗收，統一見 [V-03](../conformance.md)。

- **本篇（核心）**：各條驗收寫在各條底下。任務表格式以 [P-202](protocol/tick.md) 為準。〔使用者方向 2026-09-30，第二十批〕任務表先只定基本欄位，`group`、`needs` 當陌生鍵（2026-10-01 起 `methods` 也是）；2026-10-01 加了頂層預設與 `modules`。
- **子篇**：`aos-cg`、hooks、tick 模組、恢復與設定的驗收寫在 [tick 子篇](tick/README.md) 各篇，都還沒有程式。git 與 cgroup 是有就用（[B-630、B-622](deferred/git.md)、[B-634](tick/cg.md)）。
- **暫緩**：上下層判定、完整互斥、帳號核對、紀錄落盤與失效處理在 [tick 暫緩區](deferred/tick.md)。
- **工程預設**：tasks-blocked 的位置、結束碼紀錄的位置與欄位、各系統級任務與普通程式的程式名。這輪先寫成暫定的列在 [README 疑點](README.md#疑點)。
