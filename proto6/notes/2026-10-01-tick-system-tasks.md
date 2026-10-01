# 2026-10-01：aos-tick 的系統級任務總整理（給 hooks 慢慢想用）

← [筆記索引](README.md)｜[tick 子篇入口](../spec/settled/tick/README.md)｜[hooks B-635](../spec/settled/tick/hooks.md)｜[第二段 plan 草稿](../plan/m2-system-tasks.md)｜[第六、七批裁定](verdicts/11-tick-as-unit.md#2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄)

**這份只是整理，不是裁定。** 使用者 2026-10-01：「把aos-tick的系統性任務，先前有規劃過的，都寫下來，我之後慢慢思考他們要怎麼在hook下實作」。下面把過去規劃過的系統級任務、相關普通程式、範本、已暫緩與已撤回的東西全部列出來，每項附「放到 hooks 下」的觀察。**每項的「hooks 想法」都只是選項，標了「待使用者想」，沒有替使用者決定。**

背景方向（[第七批](verdicts/11-tick-as-unit.md#2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄)）：tick 模組能用 hooks 做的就用 hooks；node、逾時不做 tick 模組；歷史紀錄不做；停格與 git 先不動。

## 現在 hooks 能做什麼、限制在哪

正本：[B-635](../spec/settled/tick/hooks.md)。

**能做的：**

- 任務表頂層鍵 `hooks`，跟 `tasks` 同層，不是模組。
- 只開一個掛點 `after_all`：一串 inst，寫法比照 `tasks`（`id` 可省、吃頂層預設、同樣的 cwd 與環境變數）。
- 照表跑完之後跑，**被停格檔停下的那格也照跑**——這是它存在的理由。
- hook 看得到本格紀錄：這時紀錄已經收尾（`ended:true`），有 `ran`、失敗清單 `tasks`、`stopped_after`，以及前面 hook 裡不是 0 的碼。

**限制：**

- **只有 `after_all`**。`before_all`、`before_task`、`after_task` 都沒開，寫了照收不理。所以「每格開頭」「每項前後」的事，現在只能當任務表上的一般項。
- **hook 不看停格檔**：hook 之間互不擋，hook 建停格檔也沒人理（下一格開頭刪掉）。所以 hook **擋不住任何東西**，也沒辦法「前一個 hook 失敗就不跑下一個」。
- **碼不影響 tick**：hook 回幾都只記進 `hooks.after_all`（0 不記），tick 照舊回 0。
- **擋板檔、拿不到鎖（busy）、表壞時一個都不跑**。
- **紀錄在 hook 跑之前就寫成 `ended:true`**：hook 跑到一半 tick 被殺，下一格的 `last/` 看起來仍是「正常收尾」，看不出 hook 沒跑完；hooks 也不記 `ran`。
- **hook 的 `AOS_TASK_INDEX` 從 0 數起，跟 `tasks` 的位置各算各的**：拿 index 當名字的東西（例如 `aos-git` 存檔點，plan 待問 2 的建議）會跟任務撞號。**已解決**（使用者 2026-10-01 第十批）：hook 改拿 `AOS_HOOK_POINT`／`AOS_HOOK_INDEX`／`AOS_HOOK_ID`，不再有 `AOS_TASK_INDEX`（[B-635](../spec/settled/tick/hooks.md)）；要用 index 當名字時，hook 跟任務的變數名本來就不同，自己加前綴（例如掛點名）即可。

## 怎麼讀每一項

每項固定五欄：**做什麼**／**原本的位置與機制**／**狀態與正本**／**現在已經不在的前提**／**放到 hooks 的想法（待使用者想）**。「範本位置」指 [B-629](../spec/settled/tick/template.md) 的兩版範本。

## 一、標準任務表範本（B-629）

- **做什麼**：預設的一組系統級任務，夾著使用者任務。
- **原本的順序**：
  - 沒有 git：`mq-get` → 使用者任務 → `mq-post` → `clean`。
  - 有 git：`git-open` → `mq-get` → `mark-get` → 使用者任務 → `mark-user` → `clean` → `git-close` → `mq-post`。
  - 更早（第二十批原話）還有收件、投件、發摘要；發摘要 `summary` 10-01 拿掉。
- **機制**：全靠**陣列順序**給保證，例如「先提交再送」靠 `git-close` 排在 `mq-post` 前面，close 失敗建停格檔就擋住 `mq-post`。系統級任務標 `kind:"system"`，核心不看。
- **狀態**：待實作（[B-629](../spec/settled/tick/template.md)）；plan 待問 11、12 還沒裁定，建議第二段版只剩 `git-open` → 使用者任務 → `mark-user` → `git-close`。
- **前提不在了**：`aos-mq` 要的通道在暫緩區；`clean` 沒東西可清；`kind` 沒人讀。
- **hooks 想法（待使用者想）**：範本可能拆成「`tasks` 放使用者任務＋必須被停格擋住的項」、「`hooks.after_all` 放停格後也要做的收尾」兩半。關鍵是每一項要不要被停格檔擋——**現在範本的保證大多靠「停格就不跑後面」，搬進 `after_all` 就失去這個擋法**，那一項得自己讀紀錄的 `stopped_after` 判斷。

## 二、git 三項（B-630、B-622、B-632）

使用者 10-01：「git也先不動」。plan 待問 1～8 都還在想。共通前提：[git.md](../spec/settled/tick/git.md)、格式 P-205。

### aos-git open（`git-open`）

- **做什麼**：上一格沒正常收尾（`last/` 是 `ended:false` 或有 `stopped_after`）就把 aos 範圍還原到 HEAD；清掉殘留的 `refs/aos/marks/*`；打本格第一個存檔點。
- **原本位置**：有 git 版第 1 項。
- **機制**：讀上一格紀錄；「在不在 tick 內」靠繼承的鎖 fd；故障時寫擋板＋停格檔。
- **狀態**：待實作（[B-630](../spec/settled/tick/git.md)）。
- **前提不在了**：鎖 fd 不傳給任務（`not_in_tick` 判不了）；`kind` 回查、巢狀排除（上下層判定 B-628 暫緩）都沒依據；紀錄只記非 0，存檔點命名、組的判法 plan 已改照 `index`。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 第一項：最單純，沒什麼不行。
  - 等開 `before_all`：使用者不會忘了排、也不會被誤排到中間。
  - **注意**：如果 close 搬進 `after_all`（下面），「上一格有 `stopped_after`」這種情況可能在當格就處理掉，open 只剩管當機（`ended:false`）。但 hook 跑到一半被殺時紀錄仍是 `ended:true`，open 會看不出來——這是 hooks 現行紀錄設計的洞。

### aos-git mark（`mark-get`、`mark-user`、使用者自己加的存檔點）

- **做什麼**：打存檔點；剛結束那組有失敗，就把那組改的 aos 範圍還原到往前最近的存檔點再打點。`mark <路徑…>` 可把使用者的檔加進 aos 範圍。
- **原本位置**：有 git 版的 `mark-get`（`mq-get` 之後，把取件那段隔開）、`mark-user`（使用者任務之後、`clean` 之前）；使用者任務要存檔就自己插一項。存檔點各占一項，不做包裝寫法（疑-12）。
- **機制**：讀本格紀錄判斷「組」有沒有失敗（現在照 `index`）；ref 名原用 `AOS_TASK_ID`，plan 建議改 `AOS_TASK_INDEX`。
- **狀態**：待實作（[B-630](../spec/settled/tick/git.md)）；`mark <路徑…>` plan 建議先不做（待問 3）。
- **前提不在了**：「兩個存檔點之間全是 `kind:"system"` 就整段算 aos 範圍」要回查 `kind`，plan 建議拿掉（待問 1）；`id` 可重複、可省。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 當一般項：它本來就是「夾在兩項之間」，`after_all` 做不到。
  - 等開 `after_task`：每項後自動打點＝每項自成一組，使用者不用自己插；代價是每項都掃一遍 aos 範圍（成本）、組變細。
  - `mark-get` 只在有 `mq-get` 時才需要；`mq-get` 如果搬去 `before_all`，`mark-get` 可能跟著併進去。
  - 若 hook 也要打點，ref 名不能只用 `AOS_TASK_INDEX`（會跟任務撞號），要加前綴之類。（第十批後 hook 沒有 `AOS_TASK_INDEX`，改用 `AOS_HOOK_POINT`＋`AOS_HOOK_INDEX`。）

### aos-git close（`git-close`）

- **做什麼**：處理最後一組（失敗就還原）、把 aos 範圍剩下的改動提交一次（`aos-tick <seq>`）、刪本格存檔點。
- **原本位置**：有 git 版倒數第二，`clean` 之後、`mq-post` 之前。
- **機制**：**被停格擋住是刻意的**——停格＝這格作廢，close 不跑、不提交，交給下一格 open 還原。close 失敗建停格檔，保住「先提交再送」。
- **狀態**：待實作（[B-630](../spec/settled/tick/git.md)）；故障處理 plan 建議只回 1（待問 5）。
- **前提不在了**：同 open；故障寫擋板＋停格檔 plan 建議拿掉。
- **hooks 想法（待使用者想）**：
  - 留在 `tasks` 倒數：照原設計，停格自然不跑。
  - 搬進 `after_all`：停格也會跑，得自己讀 `stopped_after`，再選「停格就不提交（照舊作廢）」或「停格也提交前面成功的組」——後者會改掉「停格＝整格作廢」的語意。
  - 搬進 `after_all` 後，close 失敗**擋不住**後面的 hook（例如 `mq-post`），「先提交再送」要改由 `mq-post` 自己核對。

## 三、系統訊息佇列 aos-mq（B-623、B-624）

兩項都要暫緩區的 daemon 通道（B-612、B-614）；現行 daemon 沒有通道，跑了也只是 `no_channel`、回 0。plan 排在第四段。

### aos-mq get（`mq-get`）

- **做什麼**：用 `node.take` 把本工作資料夾佇列裡的請求與回應取到空；取出後怎麼分派 aos 不管。每個工作資料夾只有它取。
- **原本位置**：沒有 git 版第 1 項；有 git 版第 2 項（`git-open` 之後）。
- **機制**：通道、本格憑證；「在不在 tick 內」靠鎖 fd，不在就自己取鎖、拿不到回 75。
- **狀態**：待實作、依賴暫緩（[B-623](../spec/settled/tick/mq.md)、P-206）。
- **前提不在了**：通道、憑證、鎖 fd、75 碼（C-08 後要重定）。
- **hooks 想法（待使用者想）**：「每格開頭」的事，適合 `before_all`（還沒開）；在那之前只能是 `tasks` 第一項。`after_all` 不合適（取了要給這格的任務用）。訊息模組本身可能整個改成 daemon 模組，到時候再看。

### aos-mq post（`mq-post`）

- **做什麼**：把 `.aos/mq/post/` 裡的訊息用 `node.send` 一件件送出；送不了的搬到 `.aos/mq/failed/`（下一格開送前清掉）。
- **原本位置**：沒有 git 版倒數第二；有 git 版最後（`git-close` 之後）。
- **機制**：排在使用者任務之後，「前面都跑完才送」「停格就不送」「有 git 時只送已提交的」全靠順序與停格檔。
- **狀態**：待實作、依賴暫緩（[B-624](../spec/settled/tick/mq.md)、P-206）。
- **前提不在了**：同 `mq-get`。
- **hooks 想法（待使用者想）**：「每格收尾」很像 `after_all`；但 `after_all` 停格也跑，要保住「停格不送」得自己讀 `stopped_after`。跟 close 都放 `after_all` 時，陣列順序 close → post 照樣排得出來，只是 close 失敗擋不住 post。也可以乾脆留在 `tasks` 尾巴。

## 四、aos-clean（B-404）

- **做什麼**：過了保留期（以格數計，`retention_ticks`）的資料封存或刪除；自己記上次清理是第幾格，間隔 `interval_ticks` 未到就回 0。只清自己認得的（agent／kernel 任務產生的）。
- **原本位置**：沒有 git 版最後；有 git 版移到 `git-close` 前、自成一段（讓清理的變動當格提交）。舊 kernel 範本裡是 `custom` 類、排最後。
- **機制**：`kind:"system"`；在 tick 內靠鎖 fd、有 git 交給 close 提交；直接跑時自己取鎖、自己 commit。
- **狀態**：待實作（[B-404](../spec/base/storage.md)、[P-605](../spec/protocol/ops.md)）；plan 待問 9 建議第二段不做（POC 沒有它認得的資料）。
- **前提不在了**：沒有 kernel、agent 任務可清；鎖 fd；`state/ops/clean.json` 不在新的 aos 範圍。
- **hooks 想法（待使用者想）**：跟這格任務成敗無關、停格也可以清，很像 `after_all`。但有 git 時它原本要排在 close 前「當格提交」——兩個都在 `after_all` 就排 clean → close；close 留在 `tasks` 的話 clean 在 `after_all` 會變成下一格才提交。也可能根本不屬於 tick，交給使用者自己掛一項。

## 五、普通程式（不是系統級任務）

### aos-tick-check-task（原 aos-needs，B-621）

- **做什麼**：自己是任務表一項；指定的 id 出現在本格失敗清單（不寫 id＝清單非空）就建停格檔，本格後面全不跑。都回 0。
- **原本位置**：使用者任務中間，排在要檢查的項後面。前身 `aos-needs <前置…> -- <原指令>` 是包裝，10-01 改寫。
- **機制**：讀本格紀錄（只記非 0）、停格檔。
- **狀態**：待實作，不依賴暫緩（[B-621](../spec/settled/tick/check-task.md)、P-204）；plan 步驟 1，已裁定。
- **前提不在了**：幾乎沒有，它是照現在的 tick 設計的。
- **hooks 想法（待使用者想）**：**放 `after_all` 沒有意義**（hook 不看停格檔，它建了也沒人擋）。它就是「任務表的關卡」，留在 `tasks`。若哪天開 `before_task`，「每項前檢查某條件」可以變成 hook，正好接到下面的停格檔 JSON 構想。

### aos-cg（B-634；B-631 撤）

- **做什麼**：包裝 `aos-cg -- 原指令`：每項一框，主程序結束後清掉框裡（或程序群組裡）剩下的程序。
- **原本位置**：不占位置，要的任務自己包。
- **機制**：有 cgroup 時開 `task-*` 框（框樹要舊 daemon 開）；沒 cgroup 時 subreaper＋程序群組。框清不空就建停格檔。
- **狀態**：待實作（[B-634](../spec/settled/tick/cg.md)、P-211）；daemon 那側（B-605）暫緩，現行只會走「沒 cgroup」那欄。
- **前提不在了**：舊 daemon 的工作資料夾框；格後收屍（B-601）。
- **hooks 想法（待使用者想）**：本質是每項包一層，不是掛點。`after_task`（沒開）可以想成「沒包的任務也清殘留」，但 tick 核心不是 subreaper，孤兒會掛到 init 或 daemon，hook 找不到它們，除非有 cgroup。大概留著當包裝最自然。

### aos-as（B-303）

- **做什麼**：包裝 `aos-as <帳號> -- 原指令`：請 root helper 用別的帳號開程序，交出鎖 fd 與 stdio。
- **原本位置**：不占位置，要換帳號的任務自己包；跟 `aos-cg` 一起寫成 `aos-cg -- aos-as …`。
- **機制**：helper、通道、鎖 fd。
- **狀態**：暫緩（[helper.md](../spec/settled/deferred/helper.md)、P-212），整條靠暫緩區。
- **前提不在了**：helper、通道、鎖 fd 都在暫緩區；任務的 `user` 已撤。
- **hooks 想法（待使用者想）**：跟掛點無關，是包裝；helper 之後若成 daemon 模組再說。

## 六、在 tick 外的工具

### 恢復前驗證（B-625；構想名 aos-check）

- **做什麼**：改了 inst 或任務表之後、`aos-ctl resume` 之前，持鎖驗 inst、任務表（完整 schema）、kernel／agent 設定，過了才恢復。
- **原本位置**：不在任務表；人或工具在格間用。
- **狀態**：待實作（[recovery.md](../spec/settled/tick/recovery.md)、P-210）；plan 待問 10 建議先不做，最小版構想 `aos-check <資料夾>`（把讀表＋每項展開走一遍、不真跑）。
- **前提不在了**：舊 daemon 代驗再送 `node.resume` 那套暫緩；標準庫沒有 schema 驗證器。
- **hooks 想法（待使用者想）**：不在格內，看起來不需要 hook。只有一個邊角：若想「每格開頭先驗一次表」，那是 `before_all` 的事，但 tick 讀表時的 `bad_table` 已經擋掉大半。

### aos-config-add（B-625 部分、P-207）

- **做什麼**：在 tick 外持鎖、原子替換 `config/` 裡的設定檔。
- **狀態**：**暫緩**（[暫緩區](../spec/settled/deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)），從沒寫過程式；現在改 `config/` 就自己改。
- **hooks 想法（待使用者想）**：格外工具，跟 hooks 無關，大概不需要。

## 七、已暫緩或只是構想

### aos-publish（發摘要，B-624 部分、P-206 那列）

- **做什麼**：把 `.aos/summary/summary.json` 原樣發布成 ignored 的 `published.json`，給只有摘要讀權的上層讀。
- **原本位置**：沒有 git 版在 `mq-post` 之後、`clean` 之前（id `summary`）；有 git 版最後。
- **狀態**：**暫緩**（[暫緩區](../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)），使用者想改名。
- **前提不在了**：上下層判定（核對直接下層）暫緩。
- **hooks 想法（待使用者想）**：「格末把東西整理好給別人看」很像 `after_all`；停格的格也發，可能反而是好事（上層看得到這格停了）。

### aos-summarize（構想，不做）

- **做什麼**：把這一格的狀況總結成 JSON。使用者 10-01：「那看來aos-summarize其實是暫時不需要了，拿掉。」之後若要，名字不用 publish。
- **hooks 想法（待使用者想）**：`after_all` 看得到收尾後的紀錄，天然適合；而紀錄本身（`ran`、失敗清單、`stopped_after`、hooks 的碼）已經很像摘要，可能根本不需要另一支。

### aos-tick-check-task-continue 與停格檔 JSON（未來方向）

- **做什麼**：停格檔變成 JSON、存條件；tick 每項執行前看停格檔，滿足條件才跑；`aos-tick-check-task-continue` 檢查並改寫停格檔。記在 [B-620](../spec/settled/tick.md) 與 B-621。
- **狀態**：只記錄、不做；使用者 10-01：「停格這一塊先不動」。
- **hooks 想法（待使用者想）**：「每項前看條件」就是 `before_task` 的形狀；要嘛改核心（停格檔規定），要嘛開 `before_task`，兩條路都還沒選。

### 往上叫醒 `aos-ctl wake <上層>`（第七批）

- **做什麼**：一格跑完叫上層現在就跑一格。
- **狀態**：第七批建議做法，前提是 daemon `insts` 的鍵直接寫資料夾；node 那塊使用者「感覺總有哪裡不對」。
- **hooks 想法（待使用者想）**：第七批已經寫明用 `after_all` 掛。要不要停格也叫醒、要不要只在有事時叫，hook 自己讀紀錄決定。

## 八、第七批列過的模組候選

[第七批](verdicts/11-tick-as-unit.md#2026-10-01-第七批tick-模組的取捨node逾時歷史紀錄)候選有收尾、node、git、關卡、逾時、收屍、歷史紀錄、訊息。已定的：歷史紀錄不做；逾時用系統 `timeout` 包；node 不做 tick 模組；git、停格先不動。其餘：

- **收尾**：比較像 `after_all` 本身（git close、mq-post、clean、摘要、叫醒）。
- **關卡**：比較像 `aos-tick-check-task`（任務表一項）或未來的 `before_task`。
- **收屍**：原本歸舊 daemon 的 runner 格後收（B-601，暫緩）；`after_all` 能做多少要看有沒有 cgroup（見 `aos-cg`）。
- **訊息**：就是 `aos-mq`，見第三節。

以上歸類都只是觀察，待使用者想。

## 九、已撤回或改名、不會照原樣回來的

| 舊東西 | 變成什麼 | 出處 |
|---|---|---|
| `aos-needs`（包裝、回 125） | `aos-tick-check-task` | [暫緩區篇末](../spec/settled/deferred/tick.md#已撤回被取代) |
| 收件 aos-inbox → aos-intake → `aos-sysinbox`；投件 aos-outbox | `aos-mq get`／`post` | verdicts 11「astra 審整理區」 |
| 檔案收件、檔案投件（`requests/`、`responses/`） | 普通程式，aos 不管 | [B-623、B-624](../spec/settled/tick/mq.md) |
| 鬧鐘 `alarm_ticks`、`.aos/alarms/` | 撤，任務自己記 | B-624 |
| `.aos/journal/`、`aos-tick adopt` | 結束碼紀錄取代 | [B-632](../spec/settled/tick/git.md) |
| tick 側 cgroup 備援 | 撤，改 `aos-cg` | [B-631](../spec/settled/tick/cg.md) |
| 第十九批「標準配備」（同一支 aos-tick、必須全掛） | 標準任務表範本 | verdicts 11 追答 8、9 |

## 十、daemon 那側、本來就不在任務表上的

這些原本跟範本一起講，但歸 daemon，全在暫緩區：格後收屍與 runner（B-601）、重啟清框（B-603）、排空停機（B-604）、once 掛行程 `node.mount`（B-613，任務自己呼叫）、helper 固定動作（B-609）。擋板檔的「之後各格不開」現在由 `aos-tick` 自己看（B-620）。這些大概都不是 tick hooks 的事，列著備查。

proto5 沒有同名的東西：它的 daemon 直接開 `aos-kernel tick`（`lib/aos_daemon_ticks.py`），沒有任務表與系統級任務。

## 總表

| 名字 | 狀態 | 可能的掛點（待使用者想） | 備註 |
|---|---|---|---|
| 標準任務表範本 B-629 | 待實作 | `tasks`＋`after_all` 兩半 | 保證多半靠停格擋後面 |
| `aos-git open` | 待實作 | `tasks` 首項／`before_all` | git 先不動 |
| `aos-git mark`（mark-get、mark-user） | 待實作 | `tasks` 中間／`after_task` | index 會跟 hook 撞號 |
| `aos-git close` | 待實作 | `tasks` 倒數／`after_all` | 進 `after_all` 會改「停格＝作廢」 |
| `aos-mq get` | 待實作、依賴暫緩 | `tasks` 首項／`before_all` | 要通道 |
| `aos-mq post` | 待實作、依賴暫緩 | `tasks` 尾／`after_all` | `after_all` 要自己判停格 |
| `aos-clean` | 待實作（plan 建議先不做） | `after_all`／`tasks` | 有 git 時要排 close 前 |
| `aos-tick-check-task` | 待實作（已裁定） | 留 `tasks`；將來 `before_task` | `after_all` 無意義 |
| `aos-cg` | 待實作 | 留包裝 | 無 cgroup 時 hook 收不到孤兒 |
| `aos-as` | 暫緩 | 留包裝 | 要 helper |
| 恢復前驗證（aos-check） | 待實作（plan 建議先不做） | 不需要 | 格外工具 |
| `aos-config-add` | 暫緩 | 不需要 | 格外工具 |
| `aos-publish` | 暫緩 | `after_all` | 要改名 |
| `aos-summarize` | 構想，不做 | `after_all`／可能不需要 | 紀錄已像摘要 |
| `aos-tick-check-task-continue` | 未來方向 | `before_task` 或改核心 | 停格先不動 |
| `aos-ctl wake <上層>` | 第七批建議 | `after_all` | node 還在想 |
| 收屍（runner） | 暫緩（daemon） | 不明 | 要 cgroup 才收得到 |
| 逾時 | 不做模組 | 不需要 | 用系統 `timeout` |
| 歷史紀錄 | 不做 | — | 第七批 |
