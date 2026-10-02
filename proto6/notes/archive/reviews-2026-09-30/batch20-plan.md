> 封存 2026-10-02：09-30 審稿與第十八～二十批（含 cgroup／git）改寫計畫、交接、核對報告，批次已結束；結論已由 proto6/spec（settled/ 與 settled/deferred/）與裁定紀錄 proto6/notes/verdicts/09～11 吸收

# 依第二十批改寫 proto6 spec：計畫（待使用者同意）

← [審稿紀錄](README.md)｜[第二十批](../../verdicts/11-tick-as-unit.md)｜[第十九批](../../verdicts/10-tick-minimal-core.md)｜[spec 入口](../../../spec/README.md)

**這是計畫，spec 一個字都還沒改。** 你看過、回答完標「先定」的疑點後才動手。依據是 11 號檔方向 1～4、追答 1～9（含第 9 條「系統級任務」與同日兩句追答：標記是 `kind:"system"`；`aos-cg`、`aos-as` 是普通程式）；跟第十九批、第十八批衝突的，以第二十批為準。逐條落點在 [batch20-map.json](batch20-map.json)（378 列，欄位說明見文末）。

## 摘要

- **大方向**：tick 是 aos 的衡量基準。**核心只剩四件事**：同資料夾互斥鎖、照任務表依序跑、上下層判定、**每項結束碼紀錄**（新）。其他原本算在 tick 裡的——git 開格與收尾、收件、投件、發摘要、清理——都變成**系統級任務**：寫在任務表上、`kind:"system"` 標記的普通程式；**標準任務表範本**就是預設那一組。cgroup 拆成 daemon 端（node 框、上限、格後收尾）加包裝 `aos-cg`；切換使用者做成包裝 `aos-as`。aos 內部自己決定的時長改成格數，外部規定的留毫秒；「收到就處理」改成「下一格處理」。
- **改多少**：spec 的 46 篇 md 約動 40 篇（只有 `cli.md`、`cli/gaps.md` 與三份 daemon 協議小檔不用動）；其中約一半只是把「標準配備」換成「某某任務」。schema 確定要改約 15 份，另有約 10 份看疑-5、疑-7、疑-10、疑-11；範例跟著改。逐條見 map，分九類：新條 18、撤銷 59、改寫 168、時間 70、下一格 11、tick 外 10、排程 7、舊疑點 29、原型 6。
- **推翻第十九批的結構**：三層（核心／標準配備／其他掛載）、標準配備「必須全掛、不能拆、同一支 `aos-tick`」、有備援仍算全掛、完整級／備援級兩級保證、全掛檢查與 y／n、`aos-tick --check` 與 `aos node check`、`standard: cgroup=… git=…` 輸出、`standard_incomplete` 事項、tick 替任務切帳號（`spawn_as` 由 tick 發）、標準配備替每項任務開 `task-*` 框並一結束就清、needs／group 由 tick 在每組後提交、收件在 commit 後當格刪原件、每格開頭一律回到基線。細目見第一節。
- **沿用第十九批、不動的**：鎖、上下層、tick–daemon 通道（B-612～614）、`node.mount`、daemon 端 cgroup 與 helper 的佈建動作、「管轄權是約定不是前提」。
- **新寫的**：核心四件事與結束碼紀錄（第二節）、範本與 git 開格／收尾任務（第三節）、`aos-cg`、`aos-as`（第四節）、時間原則（第五節）。
- **請你看這四處**：
  1. 第三節的範本與 git 任務草稿——尤其兩個連帶效果：**上一格好好做完就不還原**，所以格與格之間人手改的檔會被下一格提交；**保證改成照「掛了哪一項」寫**，沒掛的不逐條寫後果（沿第十九批「沒掛不管」的精神，但不再有「全掛」這個整包狀態）。
  2. 第五節「算誰的格」的理解：任務用的時長算本 node 自己的格，kernel 對成員的判斷算 kernel 的格。
  3. 第十一節疑點 14 題，其中 **8 題標「先定」**。
  4. 第八節仍要問的 4 題舊暫定（上一輪就沒答，這輪照暫定寫，除非你想現在答）。

**名詞**：

- **系統級任務**：從 tick 核心拆出來、掛在任務表上的程式（git 開格／收尾、收件、投件、發摘要、清理），任務表上標 `kind:"system"`。
- **標準任務表範本**：預設的一組系統級任務加上原本的 kernel／agent 任務。
- **包裝**：`aos-cg -- 原指令`、`aos-as <帳號> -- 原指令` 這類「先做一件事、再跑原指令、照原指令的結果結束」的普通程式。
- **結束碼紀錄**：核心每格寫的一份檔，記本格各項怎麼結束，後面的任務讀得到。
- **格數**（`seq`）：本 node 第幾格，記在結束碼紀錄裡，跨重啟不倒退；aos 內部時長就用它數。
- **提交紀錄**：git 收尾任務每格寫的一份檔，記哪些組成功、哪些收件已消費、哪些待送檔可送。
- **停格碼**：daemon 看到就暫停這個 node 的結束碼（現在是 3、125）。

## 一、撤銷／改寫清單

細節（每組所有落點）見 map `kind=撤銷`、`kind=改寫`。下表只列主要位置。

| # | 撤／改什麼 | 現在在哪 | 改成什麼 |
|---|---|---|---|
| 撤-A | 三層與「標準配備」（必須全掛、不能拆、跟核心同一支 `aos-tick`、沒有關掉的旗標） | T-10、T-07 末段、T-06、README 定位段、B-626、B-629、V-01 正本表 25、預留表 | 「核心＋系統級任務＋其他任務」；B-626 換主題「核心與系統級任務的界線」，B-629 換主題「標準任務表範本」；系統級任務各自獨立，寫在表上才跑 |
| 撤-B | 保證以標準配備全掛為前提、完整級／備援級兩級 | T-01、README「來源與正本」、V-01 正本規則、V-02、B-631 與 B-632 的對照表、S-203 | 保證照「掛了哪一項系統級任務、包了哪個包裝、daemon 有沒有 cgroup」各條自己寫；兩張對照表刪 |
| 撤-C | 全掛檢查、y／n、`standard_incomplete` 事項 | B-630、P-203 stdin 列與碼 2「答 n」、P-601、S-405、V-03（第十九批段 3 句） | 刪；B-630 條號換主題「git 開格與收尾任務」 |
| 撤-D | `aos-tick --check`、`aos node check` | P-203 argv、protocol/README 碼表、H-004 第 58 列、debugging、walkthrough、mapping | 刪 |
| 撤-E | `standard: cgroup=… git=…` 輸出 | B-630、B-627 驗收、B-605、P-101、H-004 第 1 列、walkthrough | tick 不再印；daemon 啟動只報自己的 cgroup（〔建議〕`cgroup=on\|off`） |
| 撤-F | tick 側的 cgroup 備援（subreaper、每項後殺 process group、rlimit、getrusage） | B-631、B-602 末句、B-204 | tick 側刪；daemon 側的 subreaper＋程序群組收尾留在 B-604；`aos-cg` 沒 cgroup 時怎麼辦見疑-9；B-631 留一句殘根 |
| 改-G | B-202 每任務一框（`task-*` 由標準配備開、一結束就 `cgroup.kill`、格首清上一格殘留） | B-202、B-204、B-605 命名與委派、P-203、V-01 正本表 01／05 | 搬進包裝 `aos-cg`，要的任務才包；**放棄「沒包的任務一結束就清殘留」**；格後殘留由 daemon 收尾（已有） |
| 改-H | 跨帳號任務：tick 握鎖經通道發 `spawn_as` | B-620「任務的帳號」、B-629 末段、B-601、B-609、B-303、T-10 詞條、P-203 身分列、V-01 正本表 22、V-03 | 由包裝 `aos-as` 發；`spawn_as` 本身不變，只是呼叫者換人；`.aos/jobs/` 檔名改由 `aos-as` 定；任務表 `user` 欄見疑-6 |
| 改-I | group／needs：tick 每組跑完就提交或還原、needs 前置沒成功就跳過、跨組要等前組提交 | B-621、B-622、P-204、P-205、P-814「每項各自一組」、V-03 | 失敗整組還原搬進 `aos-git close`；跳過誰做見疑-2；組怎麼認見疑-3 |
| 改-J | 每格開頭一律回到最近 commit | B-622、B-625、P-205 | `aos-git open` 只在「上一格做到一半」才還原 |
| 改-K | B-623 收件在「這組 commit 成功後」當格刪原件（Q1） | B-623、B-624、B-503、B-632、P-203 讀寫列、messages 投件順序段、kernel-tasks、work、V-03 | 下一格 `aos-git open` 照提交紀錄刪上一格已提交的原件；連帶寄件方鬧鐘「原件還在就算沒處理」會晚一格才準（B-624 寫明） |
| 改-L | Q2 先提交再送、每組提交後發布摘要 | B-624、P-307、agent-tasks、V-03 | 範本把投件、發摘要排在收尾前，怎麼守見疑-4 |
| 改-M | git 備援的檔案日誌（只在沒 git 時寫、只記成功組） | B-632、P-205、node-journal schema 與兩份範例、summary_commit、source_journal_seq | 「git 與無 git 同一模式」：提交紀錄有 git 沒 git 都寫（記錄者理解，見疑-5）；`tasks[].exit` 改由核心結束碼紀錄提供 |
| 改-N | 整格原子、擋板、結束碼 3／125 屬 tick | B-622、P-203 碼表、P-205、B-607、P-704、kernel-tasks | 整格原子只在掛了 `open`／`close` 且有 git 時才有；擋板與 3／125 屬 git 任務；daemon 停格怎麼觸發見疑-1 |
| 改-O | `kind:system` 留給「以後真正屬於標準配備的任務」、範本沒有 system 類、`aos-clean` 是 custom | B-626、P-202、T-06、V-03 | `kind:"system"`＝系統級任務的標記；範本頭尾都有 system 類；`aos-clean` 改 system；kind 分段檢查〔建議〕撤 |
| 改-P | 「標準配備」清單裡不在範本的項目：once、通道傳訊、鬧鐘、daemon 端、helper | B-629 表、B-613、B-612、T-09 | once 與通道傳訊是任務呼叫的通道事務；鬧鐘歸 `outbox`；重啟清空、收尾、排空、helper 歸 daemon 本身 |

**不用撤、主詞照改的**：`task-*` 保留名稱、node 框委派給 node 帳號（`aos-cg` 仍要）、B-611 cgroup 子樹鎖、helper 刪殘留框、`cgroup_*` 佈建動作、`spawn_as` 的參數與限制。

## 二、核心新條：只剩四件事

### 2.1 核心條文草稿（T-07 改寫、B-626 換主題）

> 〔使用者方向 2026-09-30，第二十批〕**tick 核心只做四件事**：
>
> 1. **互斥**：同一資料夾同時只跑一格（B-602，不變）。
> 2. **照表跑**：照 `.aos/tasks.json` 的陣列順序一項一項跑，每項是 inst 的超集（B-620，只驗 JSON、`_metainfo`、每項是合法 inst、`id` 不重複）。
> 3. **上下層**：預設看資料夾包含，可登記覆蓋（B-628，不變）。
> 4. **每項結束碼紀錄**：本格每一項怎麼結束，寫成一份檔讓後面的任務讀得到（B-633，新）。
>
> 核心只要 Python 3.9 與 flock，不靠 daemon、git、cgroup、helper。其餘原本算在 tick 裡的事——git 開格與收尾、收件（-32601、刪原件）、投件與鬧鐘、發布摘要、清理——都是**系統級任務**：掛在任務表上、`kind:"system"` 標記的普通程式；**標準任務表範本**就是預設的一組系統級任務（B-629）。`aos-cg`、`aos-as` 這類包裝不是系統級任務，是任務會用到的普通程式。

B-626 換主題為「核心與系統級任務的界線」，改寫要點：

- 撤「三層」「標準配備」「同一支 `aos-tick` 只在規格上分層」「沒有關掉其中一塊的旗標」。改成：核心是 `aos-tick`；系統級任務是各自獨立的程式，寫在任務表上才會跑，沒寫就不跑。
- `kind:"system"` 的意思改成「這一項是系統級任務」。只是標記，核心不看；不授予身分或權限。`system` 仍不開放自訂子名（`system.x` 拒收，沿 T-06）。
- `aos-clean` 從 custom 類改成 system 類。
- 管轄權是約定不是前提、管轄區可重疊風險自負：不變。
- 驗收改寫：任務表只放一項 `true` 也能跑；沒有任何系統級任務時，互斥、照表跑、上下層、結束碼紀錄照常成立；不會有人替沒宣告的 method 回 -32601、不會投件、不會刪原件（這些都是系統級任務做的）。

### 2.2 每項結束碼紀錄（B-633 新；格式放 P-213 新）

〔建議預設，未拍板；位置、檔名、欄位都是草稿〕

- **位置**：ignored 的 `.aos/tick/current.json`（本格）與 `.aos/tick/last.json`（上一格）。任務環境多一個 `AOS_TICK_RECORD`＝`current.json` 的絕對路徑（跟 `AOS_NODE_DIR`、`AOS_TICK_LOCK_FD` 並列，P-203）。
- **格式**：

  ```json
  {"version":1,"seq":1234,"started_at_ms":1790000000000,
   "tasks":[{"id":"open","exit":0},{"id":"inbox","exit":0},{"id":"agent","signal":9}],
   "ended":false}
  ```

  - `seq`：本 node 的**格數**，從 1 起，每格加 1，跨重啟不倒退（從 `last.json` 的 `seq` 加 1；兩份都沒有才從 1 起）。這就是「aos 內部時間改 tick」要用的**自己的格數**（見第五節）。跟 daemon 每筆登記的 `tick_seq`（叫醒後等新格用，登記換了就重算）是兩回事，後者不變。
  - `tasks`：已跑完的項，照順序；每項 `exit`（正常結束的碼）或 `signal`（被訊號結束），兩者擇一。沒跑到的不列。
  - `started_at_ms`：只給人看，不參與計算。
  - `ended`：這格跑完寫成 `true`，並加 `exit`（核心這格的結束碼）。
- **寫法**：取鎖之後、讀任務表之前：把舊 `current.json` rename 成 `last.json`（原子替換），寫新的 `current.json`（`ended:false`、`tasks:[]`）。每項結束後整份重寫（暫存檔→rename）。全部跑完寫 `ended:true`。只在格內、持鎖時寫；不 fsync（當機時少一筆，下一格看到的是「沒寫完」，照「上一格做到一半」處理，較保守）。
- **讀**：任務讀 `current.json` 看前面各項；git 開格任務讀 `last.json` 判斷上一格有沒有做完。核心自己不讀它做任何決定（跳過、停止都不是核心的事，除非疑-1、疑-2 選 a）。疑-2 選 a 或 b 時，紀錄多一種結果「跳過」，〔建議〕記成 `{"id":…,"skipped":true}`。
- **寫不進時**（唯讀資料夾、滿碟）：照跑，stderr 印一行 `record_unwritable`，不設 `AOS_TICK_RECORD`；讀的任務把「沒有紀錄」當「不知道」。這延續「管轄權不是前提」。
- **跟舊東西的關係**：取代 git 備援日誌裡的 `tasks[].exit`（P-205 的 journal 改成只記提交相關）；核心結束碼（0／1／2／75）不變，3 與 125 改由 git 任務自己回（見疑-1）。

驗收：任務第二項讀得到第一項的結束碼；第三項被 SIGKILL 時紀錄是 `signal:9`；tick 被殺掉，下一格的 `last.json` 是 `ended:false`；同一資料夾連跑十格，`seq` 從 1 到 10，刪掉 daemon 重跑仍接著數；資料夾唯讀時仍照表跑完。

## 三、標準任務表範本：預設的系統級任務

### 3.1 順序與每項是什麼（B-629 換主題「標準任務表範本」）

照 11 號檔追答 8 的順序。程式名都是草稿，〔建議預設〕。

| # | 任務 `id` | `kind` | 程式與 argv | 讀 | 寫 |
|---|---|---|---|---|---|
| 1 | `open` | system | `aos-git open` | `.aos/tick/last.json`、`.aos/tick-blocked`、`.aos/journal/` 最新一筆、git HEAD、`.aos/tasks.json`（驗 group／needs 形狀） | 還原工作樹、刪上一格已提交的收件原件、`.aos/tick-blocked`（故障時） |
| 2 | `inbox` | system | `aos-inbox` | `requests/`、`.aos/tasks.json` 的 `methods` | 消費副本 `state/messages/…`、-32601 回應進 `.aos/outbox/responses/`、壞件事項 |
| 3… | 使用者任務 | kernel／agent／custom | 各自的程式；要框的包 `aos-cg --`、要換帳號的包 `aos-as <帳號> --` | 各自 | 各自（待送檔進 `.aos/outbox/`） |
| n-3 | `outbox` | system | `aos-outbox` | `.aos/outbox/`、`.aos/alarms/`（見疑-4 決定送哪一份） | 投件、通道送件、鬧鐘紀錄 |
| n-2 | `summary` | system | `aos-publish` | `.aos/summary/summary.json`（見疑-4） | `.aos/summary/published.json` |
| n-1 | `clean` | system | `aos-clean --config config/clean.json` | `config/clean.json`、`state/ops/clean.json` | 清理、封存 |
| n | `close` | system | `aos-git close` | `.aos/tick/current.json`、`.aos/tasks.json` 的 `group`／`needs` | git commit 或還原、`.aos/journal/<seq>.json`、`.aos/tick-blocked`（故障時） |

- 預設 kernel 範本（P-814）與 agent 範本（P-704 一帶）都改成：頭兩項 `open`、`inbox`，中間是原本的 kernel／agent 任務，尾四項 `outbox`、`summary`、`clean`、`close`。
- 範本只是預設。任務表可以拿掉任何一項；拿掉了該項的保證就沒有（例如沒掛 `open`／`close` 就沒有整格原子，沒掛 `inbox` 就沒人回 -32601）。〔建議〕spec 的保證照「掛了哪一項」寫，沒掛的後果不逐條寫（延續第十九批「沒掛不管」的精神，但不再有「全掛」這個整包狀態）。
- `kind` 的分段檢查（system 最前、custom 最後）跟這個順序衝突；〔建議〕撤掉分段檢查，照陣列順序就好（分段本來就是暫定，見第八節）。

### 3.2 git 開格任務 `aos-git open`（B-630 換主題「git 開格與收尾」；B-622、B-625 併入）

1. **擋板**：有 `.aos/tick-blocked` 就不碰工作樹，回停格碼（見疑-1）。
2. **上一格做到一半**：`last.json` 是 `ended:false`、或上一格的 `close` 那項不是 `exit:0`、或沒有 `close` 那項 → 工作樹還原到最近一次 commit（還原範圍沿用 B-622 的規則：以基線 commit 的 ignore 規則管修改、新增、刪除；不用全樹 `git clean -x`；任務換了 HEAD／分支或後代還沒清空時保留現場、回停格碼）。上一格好好做完的，**不還原**。連帶：格和格之間人手改了、沒提交的檔，會被下一次 `close` 一起提交（以前是開格一律回基線、手改被丟）；要改重要設定照 A-102 先暫停、持鎖、自己提交的流程不變。
3. **刪上一格已提交的收件原件**（原 B-623 的 Q1）：讀 `.aos/journal/` 裡上一格的提交紀錄，`consumed` 列出的消費副本，對照 `requests/`、`responses/` 裡的原件，bytes 相同才刪；不同就報衝突、保留（B-503）。沒有提交紀錄就不刪（下一格重收）。
4. **驗任務表的 group／needs 形狀**（原「標準配備另驗的」一部分）：needs 指到不存在或後面的項、循環、非連續 group。壞了怎麼擋見疑-1。
5. **巢狀下層的排除**：把下層 tick 的資料夾寫進 git 管理目錄的 `info/exclude`（原 B-628 建議預設、上一輪 T6 疑點，改由這一項每格做）。

沒有 git（沒裝、版本不夠、沒 repo）時：第 2 步不還原（只在 stderr 印一行），第 1、3、4 步照做。

### 3.3 git 收尾任務 `aos-git close`

1. 讀 `current.json` 的各項結束碼與 `.aos/tasks.json` 的 `group`／`needs`，算出每組成敗：組內每項 `exit:0` 才成功；needs 指到的前項失敗，這組也算失敗。
2. **失敗組還原**：失敗組的改動回到開格時的狀態（怎麼認出哪些改動屬於失敗組，見疑-3）。
3. **提交**：剩下的改動 commit 一次，訊息 `aos-tick <seq>`〔建議〕；aos 呼叫 git 一律帶 `-c core.fsync=committed,reference`（git ≥ 2.36，B-622 原文保留）。沒變動不 commit。
4. **寫提交紀錄**：`.aos/journal/<seq>.json`（暫存檔→fsync→rename→fsync 目錄），內容：`seq`、`commit`（git 的 commit id；沒 git 時 null）、`groups`（每組成敗）、`consumed`（本格成功組的消費副本）、`outbox`（本格成功組的待送檔）。**有 git 沒 git 都寫同一份**——這就是「git 與無 git 的日誌合成同一種模式」〔記錄者理解，見疑-5〕：下一格的 `open`（刪原件）、`outbox`（投件，看疑-4）都只看這份紀錄，不管背後有沒有 git。
5. **故障**：commit、還原或寫紀錄失敗 → 寫 `.aos/tick-blocked`、回停格碼（疑-1）。修復者暫停、持鎖、核對後移除擋板（B-622 原文保留）。

沒有 git 時：第 2 步做不到（失敗組的改動留在工作區，沿上一輪暫定「不還原」），第 3 步跳過，第 4 步照寫（`commit:null`），失敗組本格新出現的待送檔搬到 `.aos/journal/discarded/<seq>/`、不投（沿 B-632）。

**原子**：整格原子只在掛了 `open` 與 `close`、而且有 git 時才有；指的仍是「同一 repo 的已提交版本與恢復基線」（B-622 原文），不保證執行期間多個檔同時變動。沒 git 時只有「有紀錄才算生效」，沒有還原與歷史。

### 3.4 當機恢復（B-625 改寫）

- tick 在某項中途被殺：`current.json` 停在 `ended:false`，下一格 rename 成 `last.json`，`open` 看到就還原到上次 commit；已提交的內容與提交紀錄都在，照紀錄補刪原件。
- 在 `close` 寫完紀錄之後、`ended:true` 之前被殺：紀錄在、commit 在；下一格 `open` 看 `last.json` 沒做完 → 還原到最近 commit（就是剛剛那個），不丟東西；照紀錄刪原件。
- 在 commit 之後、寫紀錄之前被殺：commit 在、紀錄不在；〔建議〕`open` 看到最近 commit 的訊息是 `aos-tick <seq>` 而沒有對應紀錄時，從 commit 補寫紀錄再往下；沒 git 時不會有這一段。
- daemon／VM 重啟：先照 B-603 清空舊程序（不變），之後同上。

### 3.5 其他系統級任務（改主詞，行為大多不變）

- **收件 `aos-inbox`**（B-623）：分派與 -32601、接件前核對回址、壞件只報一次，行為不變；改的是「commit 後才刪原件」→「下一格 `open` 刪」，以及 -32601 回應不再自成一組提交（跟本格一起由 `close` 提交，見疑-3）。`methods` 重複的檢查搬來這裡。通道暫存訊息仍由要收的任務自己 `node.take`（不變）。
- **投件 `aos-outbox`**（B-624）：目標檢查、通道送、鬧鐘，行為不變；「送哪一份」看疑-4。鬧鐘改成格數（第五節）。
- **發摘要 `aos-publish`**（B-624 發布摘要段）：從哪一版取內容看疑-4。
- **清理 `aos-clean`**（B-404）：kind 改 system；「在 tick 裡跑時不自行 commit，由所在 group 提交」改成「由 `close` 提交」；保留期、清理間隔改格數（第五節）。

## 四、包裝程式草稿（普通程式，不是系統級任務）

### 4.1 `aos-cg`：每項一框（B-202 改寫；argv 放 P-211 新）

〔建議預設，未拍板〕

- **argv**：`aos-cg [--] <原指令…>`。不收上限參數（上限歸 daemon 設在 node 框，B-605）。
- **開框**：看 `/proc/self/cgroup`，自己在本 node 的 `n-<h>/tick` 框（B-605）時，在 `n-<h>` 下開 `task-<seq>-<序號>`〔建議：`seq` 取結束碼紀錄的格數，序號是本格第幾次呼叫 aos-cg〕，把自己搬進去再 exec 原指令的父程序（aos-cg 自己留著當 wait 的一方）。
- **跑**：fork＋exec 原指令，wait 主程序。
- **收尾**：主程序結束後看框的 `cgroup.events` populated；還有程序就直接寫 `cgroup.kill`（不先 TERM，沿 B-202），等 populated 變 0 再 rmdir。清不空就回 3〔建議，跟疑-1 的停格碼同一個〕。
- **結束碼**：原指令正常結束就回它的碼；被訊號結束就把自己也用同一個訊號結束（讓上一層的 wait 看到的是訊號，核心的結束碼紀錄記 `signal`）。
- **開框前**：同一 node 框下有上一格留下、已沒有主人的 `task-*`，先照同法清掉（原 B-202「格首清上一格殘留」改由 aos-cg 做；daemon 開的格另外有 daemon 收尾兜底）。
- **沒 cgroup 時**（不在 node 框、沒 v2、寫不進）：見疑-9。
- **跟 `aos-as` 一起用**：寫成 `aos-cg -- aos-as <帳號> -- 原指令`。`aos-as` 把自己目前所在的 `task-*` 框帶給 helper（下一段），別的帳號的程序也放進這個框。反過來寫（`aos-as … -- aos-cg …`）會因框不歸那個帳號而開不了框。
- **撤掉的**：「沒包裝的任務一結束就清殘留」。沒包的任務留下的程序，同帳號的會一直留到這格結束；daemon 開的格由 daemon 在格後收尾整個 `tick` 框（B-604，已有）；人手或 cron 跑的沒人收，握著鎖 fd 的會讓下一格回 75（B-602，已有）。

### 4.2 `aos-as`：切換使用者（B-303 加段、B-620 改寫；argv 放 P-212 新）

〔建議預設，未拍板〕

- **argv**：`aos-as <帳號> [--] <原指令…>`。
- **做什麼**：
  1. 把原指令寫成一份 inst（`argv`、目前 cwd、目前的環境），放到 ignored 的 `.aos/jobs/as-<seq>-<序號>.json`（檔名取格數，不再用開格毫秒）。
  2. 經通道送 `node.provision` 的 `spawn_as`（B-609，參數不變）：帶本格憑證、帳號、那份 inst 的路徑；同包交來繼承到的鎖 fd（`AOS_TICK_LOCK_FD`）與一條回報 pipe 的寫端，〔建議〕另交自己的 stdin／stdout／stderr 三個 fd，讓那一項照任務表寫的 stdio 走（`spawn_as` 附的 fd 從 2 個變 5 個，P-107 與 daemon-provision schema 小改；不交的話別帳號的輸出一律 `/dev/null`）；自己在 `task-*` 框裡時帶 `frame`＝那個框。
  3. 讀 pipe 到 EOF，拿到 runner 的回報（P-110），照它結束：正常結束回同一碼，被訊號結束就用同一個訊號結束自己。
- **不行時**：沒有通道變數（不是 daemon 開的格）回 125、stderr 印 `no_channel`；daemon 回 `helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping` 也回 125 並印代碼；回應成功但 pipe 沒回報就關了回 125、印 `result_unknown`（呼叫它的一方不能重跑）。
- **鎖**：任務繼承同一份鎖 fd，照 B-602 核對；aos-as 等到 pipe EOF 才結束，所以它結束前核心不會開下一項。
- **daemon 那側**：`spawn_as` 的規則（誰能叫、帳號限制、放在哪、回傳）不變，只把「tick 呼叫」改成「帶本格憑證的任何程序呼叫」——實際上就是 `aos-as`。
- 任務表的 `user` 欄怎麼辦：見疑-6。

## 五、毫秒→tick

逐欄見 map `kind=時間`（70 列：改 tick 27、保留毫秒 29、要你選 13）。

### 5.1 原則（C-01、P-002 改寫，T1）

〔使用者方向 2026-09-30，第二十批追答 1、2、4、6〕

- **aos 自己決定的時長改成格數**，欄位名 `_ticks` 結尾（例如 `retention_ticks`、`alarm_ticks`、`member_stale_ticks`）；schema 在 `common.schema.json` 加 `Ticks`（正整數）。
- **外部世界規定的保留毫秒**，欄位名照舊 `_ms`：LLM 供應商的限流窗口與 `Retry-After`、HTTP 逾時、daemon 叫醒 tick 的週期 `interval_ms`；另外 daemon 自己的計時（`shutdown_grace_ms`、`drain_timeout_ms`、`pause_save_interval_ms`、`mount_diag_ttl_ms`、事項批次 1000 ms）也保留——daemon 不在任何一格裡，沒有格可數（記錄者歸類，跟追答 5「通道外一切在 tick 內」不衝突：這些是 daemon 本身的事）。
- **算誰的格**：算**安排它的那一層**的格。〔記錄者理解〕任務表上的任務是它那個 tick 安排的，所以任務自己用的時長（保留期、清理間隔、鬧鐘、補查間隔）算**本 node 自己的格**；kernel 對成員的判斷（失聯、重試、給幾格）算 **kernel 的格**。上下層週期不同不管（追答 6）。
- **格數從哪來**：本 node 的格數就是核心結束碼紀錄的 `seq`（第二節 2.2），跨重啟不倒退、沒 daemon 也有。daemon 的 `tick_seq` 只用在「叫醒後等新格」，不拿來算時長。
- **一格的標準長度**是那個 tick 的 `interval_ms`（追答 1），只用來換算預設值與寫說明，不參與計算。沒週期的 node（只靠叫醒的 agent）一格多長，見疑-12。
- **時間點**（`*_at_ms`）怎麼辦，見疑-7；這一題決定上面好幾個起算點的寫法。
- 「運行中逾時用經過時間、排隊看序號不看牆鐘」（C-01）不變；格數本身就是序號。

### 5.2 改成格數與保留毫秒的（確定的）

逐欄在 map（`title` 是「改 tick」或「保留毫秒」），這裡只講大類：

- **改成格數**：清理的 `retention_ms`、`interval_seconds`、`last_cleaned_at_ms` 與各條保留期（本 node 的格）；鬧鐘 `alarm_ms` 與到期點（寄件 node 的格）；kernel 的 `scan_interval_ms`、`next_scan_ms`、`usage_max_age_ms`、`member_stale_ms`、登記失敗隔 60 秒重查、`sync.json` 的 `retry_at_ms`、S-204 的「等 60 秒」、S-104 的退避（kernel 的格）；S-303 沒有 `Retry-After` 時的退避（池 node 的格；追答 4 明列「重試間隔」，有 `Retry-After` 時仍不早於它）。新欄名一律 `_ticks`（時長）或 `_seq`（第幾格到期）。
- **保留毫秒**：daemon 的 `interval_ms`、各種寬限、`drain_timeout_ms`、`pause_save_interval_ms`、`mount_diag_ttl_ms`、最近一格的時間；LLM 與 HTTP 的逾時、限流窗口、`unknown_hold_ms`、`Retry-After` 與池狀態的時間點；作業系統的 2 秒強殺與 cgroup 微秒；只給人看的紀錄時間；量測數字；人在終端機等的 CLI `--wait`、`aos inst run --timeout-ms`。

### 5.3 要你選的（併進疑-7、疑-10～12）

時間點當起算點（B-404 各起點、P-601 `reported_at_ms`、P-205 `at_ms`、P-803 `woken_at_ms`、P-703 `completed_at_ms`、P-806 `finished_at_ms`、摘要與用量的 `observed_at_ms`）→ 疑-7；成員摘要的 `due_ms` → 疑-10；工作與工具的 `timeout_ms`、runner `--timeout-ms`、B-203 逾時規則 → 疑-11；預設值怎麼換算、沒週期的 node → 疑-12。

## 六、排程是掛在任務表上的程式

〔使用者方向 2026-09-30，第二十批方向 2、追答 3〕**現況已經做到**：預設 kernel 範本的九項（check、members、resources、work、forward、pool、usage、schedule、clean）與 agent 範本的兩項，都是任務表上每格跑一次的程式；沒有常駐排程器、沒有常駐 LLM 池（P-811 明寫）；daemon 明寫不排業務工作、不分資源（B-601）。所以這條要改的是寫法與單位，不是結構。

要改的條文：

- **S 篇首、S-201～204（T5）**：加一句總則「排程就是任務表上的 schedule 等程式，每格跑一次；時長以安排者的格數計」（〔使用者方向 2026-09-30，第二十批〕），各欄改格數（第五節）。
- **daemon 那邊不再叫「排程」**（T2）：B-601「daemon 自己的排程」、B-606「登記＝請 daemon 定期或被叫醒時跑（排程）」改成「定期開格」「開格安排」，「排程」一詞留給任務表上的 schedule 程式。
- **成員的 `interval_ms`**：追答 4 已把「daemon 叫醒 tick 的週期」歸外部、保留毫秒，所以有週期的成員照舊由 daemon 計時開格，不改成上層「每 N 格叫一次」。
- **急件**：B-614 寫明急件會越過上層 schedule 的同時叫醒上限（`max_active_members`），這是追答 7 允許的唯一例外。上一輪暫定「不受上層節流」沿用。
- **範本加系統級任務**（T5 P-814、T6 agent 範本）：`clean` 改 system 並移到尾段；頭加 `open`、`inbox`，尾加 `outbox`、`summary`、`close`。
- **「給你 10 格」**：spec 目前沒有任何「給成員／任務 N 格」的欄位或規則，只有叫不叫醒、配額、失聯判斷。要不要這輪就加，見疑-14。
- **順序造成多一格**：範本裡 schedule（在使用者任務段）叫醒成員時，本格要給成員的請求還沒被後面的 `outbox` 送出，成員醒來收件區是空的，一問一答多一格。跟疑-4 一起決定。

## 七、「收到就處理」→「下一格處理」

逐條見 map `kind=下一格`（11 列）。盤了 45 處，**要改 11 處**，其餘是通道上的事、本來就在格內、daemon 本身的事或只是用詞撞到。

要改的重點：

- **B-504 的「新檔通知開 tick」要刪**（T2）：這是全 spec 唯一暗示 daemon 會盯收件區、有新檔就開格的地方，需要常駐監看，跟追答 5、7 直接衝突。改成「daemon 只照登記週期或叫醒（含急件）開格，不看收件區」。連帶 S-202 的「被通知」「通知溢出」「有收件通知」與驗收（T5）、V-04 的「收件通知」（T1）改成「kernel 每格看成員收件」「急件走通道叫醒」；S-202 標題「通知與補查」改「收件檢查與補查」。
- **S-201「有結果再叫醒」、S-301「看到後叫醒」**（T5、T4）：改成「上層 schedule 下一格看到收件再叫醒」。
- **S-302「立刻撤掉占用」、S-304 與 V-03「本機連線名額立刻還」**（T4、T1）：改成「池任務下一格看到那支 `aos-llm-call` 已結束才還」。連帶：同一 scope 的並行名額會多占一格，範本預設值可能要調（只寫一句，不改數字）。
- **走查「可立即請 top 重看」**（T6）：改「top 下一格重看」。
- **agent 串流「要不要盯著它」**（T6，A 篇約 25 行）：〔建議〕寫明「agent 只在自己的格裡讀串流檔」，免得被讀成另開監看程序。
- **B-608 的「即時改」**（T2，約 28 處）：行為不變，〔建議〕換詞成「免重開」，免得跟追答 7 的「立刻處理」混。

**tick 外的東西**（map 同一類，標 `tick外`）：daemon 開格、收尾、重啟清空、node 框與上限、helper、通道信箱、掛載行程、daemon 自己的狀態檔都保留（追答 8 已把 node 框、上限、格後收尾歸 daemon）。有衝突、要你選的兩件：tick 外持鎖改檔的指令與工具（疑-8）、逃生口（疑-13）。其餘〔建議〕：daemon 寫進 node 資料夾的事項、`runner-stderr.log`、`.err` 旁檔當成開格與收尾的附帶產物，保留；daemon 對回 3／125 的格自動停格，當成 daemon 對自己開格的安全閘，保留。

## 八、舊暫定疑點的處置

來源是[第十九批各隊交接](batch19-handoffs.md)的暫定疑點、[第十九批計畫](batch19-plan.md)第六節仍要問的 4 題與第九節未答的疑-8～10。逐題見 map `kind=舊疑點`（29 列）。

- **被第二十批推翻或變得無關（5 題）**：備援級要不要警告或問 y／n、有備援後什麼算沒全掛（兩級與全掛都撤了）；任務帶別的 user 怎麼開（改由 `aos-as`，第十九批裁定 10 的「tick 握鎖經 helper 開」照搬進包裝）；kind 分段保留（範本的系統級任務在頭尾兩段，原暫定已不成立，〔建議〕撤掉 kind 分段檢查，照陣列順序就好）；`aos node check`（對應被撤的 `aos-tick --check`，人手指令名那題只剩 `aos mount run`／`aos mount kill`）。
- **被第十九批追答或第二十批解掉（3 題）**：資料夾上層沒在 daemon 登記時覆蓋怎麼同意（裁定 11：只要新上層）；池不在 daemon 底下、agent 人手跑沒通道（裁定 11 記錄者歸類：功能受限，第二十批追答 5 再確認通道是唯一路）。
- **換了位置、仍照暫定（5 題）**：沒 git 時失敗組不還原、裝好 git 後第一格 `aos-tick adopt`（搬進 `aos-git close`）；巢狀 git 由誰寫 `info/exclude`（〔建議〕由 `aos-git open` 每格寫）；急件不受上層節流（第六節寫明它越過 `max_active_members`）；不在 daemon 底下的成員怎麼判失聯（改成 `member_stale_ticks`，預設值跟疑-12 走；〔建議〕可改看摘要裡成員自己的格數有沒有前進，見疑-7）。
- **不受影響、照暫定當建議預設（12 題）**：通道外層嚴格內層放寬、通道只傳請求、中間資料夾後來開新 tick、設定裡兩棵 root 互相包含、明寫 `cgroup_root` 卻準備不好、掛載已登記的 tick 資料夾、`mount_diag_max` 設 0、`no_channel` 回 125、通道上沒人取的訊息、有 tick 的資料夾看 inst 檔、備援時 kernel 分的額度只記帳不擋（「備援級」字眼改成「沒 cgroup 時」）、標記建了 `node.mount` 還沒送出就當掉。
- **仍要問你（4 題）**，這輪不處理、照暫定寫，除非你想現在答：
  1. **unknown 份額什麼時候還**：a 到該請求 `timeout_ms`（暫定）／b 固定時間／c 預設不占。（份額是供應商的，仍用毫秒。）
  2. **補投時 git 歷史被合併提交整理掉**：a 當成證據已清、照保留期處理（暫定）／b 合併提交必須保留待送回應。
  3. **第十八批 Q8「超分」擋什麼**：A 整個 kernel 暫停會增加占用的新派工（暫定）／B 只擋配額增加的那個成員／C 只寫事項不擋。
  4. **失聯判斷**：A 只看被叫醒後格次有沒有前進，預設 10 分鐘→改 N 格（暫定）／B 也看有週期的成員／C 預設不判斷。

## 九、分工建議

沿上一輪七隊，每隊只改自己的檔，別隊要改的句子交給主責隊落筆。這輪最重的是 T3（核心、範本、git 任務、包裝）與 T1（總綱、時間原則）；T2 比上一輪輕。

| 隊 | 改哪些檔 | 主要內容 | 建議模型 |
|---|---|---|---|
| T1 總綱 | README、terms、contracts、conformance、protocol/README、common schema、check_ids | T-07 四件事、T-10 改寫（撤三層與全掛，改「核心／系統級任務／其他任務」）、T-01 撤兩級保證、T-09 用詞、C-01／P-002 時間原則與 `Ticks`、V-01 正本表（25 列重寫、01／05／08／09／22 列改主詞）與預留表、V-03 驗收 | opus |
| T2 daemon | daemon.md、protocol/daemon/*、daemon schema 與範例 | B-605 撤 `standard:` 輸出與「備援級」字眼（改「有沒有 cgroup」）、B-604 備援收尾留在 daemon 側、B-609 `spawn_as` 呼叫者改「帶憑證的程序（`aos-as`）」、B-504 刪新檔通知、B-601／B-606「排程」換詞、B-608 換詞、逃生口（疑-13） | sonnet（B-605 由 opus 收） |
| T3 tick 與基底 | tick.md、base/*、protocol/node、messages、ops，node schema 與範例 | B-626 換主題、B-620 改寫、B-629 範本、B-630 git 開格與收尾、B-631 殘根、B-632 提交紀錄、B-633 結束碼紀錄、B-621～625 改寫、B-627、B-202 改成 `aos-cg`、B-303 加 `aos-as`、B-404 改格數；P-202／203／205／206、新 P-211～213；node-journal、node-tasks、msg-outbox、ops-clean-config schema | opus |
| T4 工作與 LLM | protocol/work、llm-work、scheduling/llm，對應 schema 與範例 | S-301／302／304「下一格」、S-303 退避改格數、工作 `timeout_ms`（疑-11） | sonnet |
| T5 kernel 與資源 | protocol/kernel-tasks、resources、scheduling 其餘，對應 schema 與範例 | S 篇首排程總則、S-201～207 改格數與「下一格」、S-202 撤通知、P-801～804 欄位、P-814 範本加系統級任務、S-203 撤「兩級」 | opus |
| T6 agent 與 CLI | agent/*、protocol/agent-tasks、cli/*，agent schema 與範例 | agent 範本加系統級任務、P-704 撤標準配備句、鬧鐘改格數、串流「只在格內讀」、H-004 撤 `aos node check`／`standard:`、tick 外持鎖指令（疑-8）、走查 | sonnet（H-004 由 opus 收） |
| T7 notes | proto6/notes（不含封存）、proto6/README | 11 號檔補「落點」、10 號檔加取代註（標準配備、兩級、全掛被第二十批推翻）、裁定索引、審稿索引、notes/README 與 proto6/README 的入口句 | sonnet |

**順序**：

1. 你回答疑點，至少先定標「先定」的 8 題。
2. T1 先寫 T-07、T-10、C-01 時間原則與 V-01 預留條號；**T3 同時寫核心（B-626、B-633）、範本（B-629）與 git 任務（B-630、B-632）**，先交出程式名、檔名、環境變數名（`AOS_TICK_RECORD`）與結束碼。T7 隨時可以開始。
3. T2、T4、T5、T6 照 T1、T3 交出的名字平行改。
4. T1 收尾：收各隊驗收句進 V-03，跑 `check_ids.py --strict`、`validate.py`、`wf-lint`。
5. 另派一隊唯讀核對，對照 map 逐列確認。

## 十、原型影響（這輪不改）

逐條見 map `kind=原型`。重點：

- **`tick.py` 大改**：只留鎖、讀表（只驗四件事）、照表跑、上下層、寫結束碼紀錄；git 的還原、group、needs、提交全部搬出去成 `aos-git open`／`close`。現在的 `tasks_validate` 還擋 `user`、還驗 kind 順序與 group／needs，要拆。鎖仍在 git 管理目錄的 `aos/tick.lock`，要搬到 `.aos/tick.lock`（上一輪就該搬）。
- **新程式**：`aos-git`、`aos-inbox`、`aos-outbox`、`aos-publish`、`aos-cg`、`aos-as`（`aos-clean` 原型還沒有）。
- **`cgroup.py`**：原型本來就沒做每任務一框（spec-gaps G-15），`aos-cg` 從頭寫；daemon 端的 node 框與上限不動。
- **`daemon.py`**：`spawn_as` 還沒做；通道、憑證也還沒做（上一輪的原型影響仍未落）。
- **tests**：`test_tick.py` 的 group／needs、還原、擋板案例改測 `aos-git`；新增結束碼紀錄（`seq` 跨格遞增、被殺時 `ended:false`）、`aos-cg`（setsid 後代被清）、`aos-as`（沒通道回 125）的測試。
- **`spec-gaps.md`**：註明第二十批，新開「結束碼紀錄」「系統級任務」「格數」三條。

## 十一、疑點（請你裁定，不替你選）

只列第二十批沒講到、又會影響設計的。標「先定」的不定就不能動筆，括號裡是會卡住的隊。選項順序不代表推薦。

**疑-1（先定；卡 T3、T2）任務能不能叫核心停掉本格其餘項？**
核心照表跑、不看結果。`aos-git open` 看到擋板、repo 壞了、任務表的 group／needs 壞了，後面的任務照樣在不對的工作樹上改檔。另外 daemon 的故障停格靠 tick 回 3／125（B-607），現在 3、125 是 git 任務回的，核心只會回 1。
- a：核心多一條：任務回某個碼（例如 3）時，核心不跑後面的項，整格也回那個碼；daemon 停格照舊。
- b：核心照跑到底，但整格結束碼取最嚴重的一項（3／125 優先），daemon 照舊停格；後面的任務要不要跑，各自讀結束碼紀錄決定。
- c：核心不加；每個系統級任務開頭自己查擋板檔，看到就什麼都不做；使用者任務照跑，交給 `close` 還原；停格改由 git 任務經通道 `node.pause` 自己停（只有 daemon 底下有）。

**疑-2（先定；卡 T3）needs 的「前置沒成功就跳過」誰做？**
第二十批說 needs 的失敗還原搬進收尾任務，但「跳過」要在那一項開始**之前**擋，收尾任務排在最後，擋不到。
- a：核心讀 `needs` 與結束碼紀錄，前置沒成功就不開這一項、紀錄記成跳過（核心變五件事）。
- b：普通程式包裝 `aos-needs <前置 id…> -- 原指令`：讀結束碼紀錄，前置沒成功就不跑、回「跳過」；有 needs 的項都包。
- c：不跳過，前置失敗照跑；`needs` 只剩「還原時連坐」的意思：`close` 把依賴失敗組的組一起當失敗還原。

**疑-3（先定；卡 T3）失敗組的改動怎麼認出來、只還原那一組？**
以前每組跑完就 commit，組界就是 commit 界；現在 `close` 在最後一次看整格，各組的改動混在同一個工作樹裡。「跨組要等前組提交成功」也跟著不成立。
- a：每組後面插一項系統級任務 `aos-git mark <組>`，把到此為止的工作樹存成暫存提交；`close` 照這些記點逐組保留或還原。
- b：不分組：任一組失敗就整格還原，只有全成功的格才提交（「前組成功保留」沒了）。
- c：組在任務表上宣告自己寫哪些路徑（新欄位），`close` 照路徑還原。

**疑-4（先定；卡 T3、T5、T6）「先提交再送」（Q2）在新順序下怎麼守？**
範本順序是 投件 → 發摘要 → 清理 → git 收尾，投件與發摘要排在提交**之前**。
- a：`outbox` 與 `summary` 只處理**上一格已提交**的內容（照上一格的提交紀錄送、從最近 commit 發布），跟「下一格刪原件」同一個道理。代價：回覆多慢一格；再加上 schedule 在 `outbox` 之前叫醒成員（第六節），一問一答可能多兩格。
- b：把 `outbox`、`summary` 排到 `close` 之後（改範本順序），提交完當格就送；`close` 失敗時它們看不到新紀錄、不送。
- c：放棄 Q2，照範本順序當格送；之後被還原的組已送出的收不回，接收方靠 ID 去重。

**疑-5（先定；卡 T3、T5、T6）「git 與無 git 的日誌合成同一種模式」是什麼意思？**
這一題決定 `node-journal` schema、`summary_commit`、`source_journal_seq`、沒 git 時的補投與保留期起點。
- a：一律寫提交紀錄（`.aos/journal/<seq>.json`），有 git 時另外 commit、紀錄裡多一個 commit id；下游（刪原件、投件、讀摘要）只看紀錄。第三節草稿照這個寫。
- b：同一對 git 任務、兩種後端：有 git 只用 commit 當證據，沒 git 才寫日誌（跟第十九批差不多，只是從 tick 搬進任務）。
- c：核心的結束碼紀錄取代日誌；git 任務只做提交與還原，沒 git 就沒有「已提交」這回事（刪原件、投件看結束碼紀錄）。

**疑-6（先定；卡 T3、T4、T6）任務表的 `user` 欄怎麼辦？**
第十九批才准任務帶 `user`、由 tick 切帳號；第二十批切帳號改成包裝 `aos-as`，核心不切。
- a：保留欄位，核心照 inst 規則：跟 tick 的帳號不同就那一項回 125、不切；要切就在 argv 包 `aos-as`。
- b：保留欄位，核心看到帳號不同就自動改用 `aos-as` 開（核心多一步）。
- c：拿掉欄位（回到任務表不准 `user`），只能用 `aos-as` 表達。

**疑-7（先定；卡 T1、T3、T5）時間點（`*_at_ms`）當起算點時怎麼辦？**
保留期、失聯、清理間隔都要「從某一格起算」，但現在的起點是毫秒時間點（commit 時間、`reported_at_ms`、`woken_at_ms`、`completed_at_ms`、摘要與用量的 `observed_at_ms` 等）。
- a：時間點照舊留 `_at_ms` 給人看；要拿來算的另加一欄「那時是第幾格」（`_seq`），計算只看 `_seq`。
- b：要拿來算的時間點直接改成格數，拿掉毫秒。
- c：時間點都留毫秒，只把時長改格數；起算時用「格數 × 週期」換回毫秒比較。

**疑-8（先定；卡 T6、T3、T5）tick 外自己取鎖改檔的指令與工具怎麼算？**
追答 5 說通道外一切都要在某一格裡做。現在有十多條人手指令在 tick 外取鎖、改檔、自己 commit：`aos-config-add`、`aos kernel members add/rm`、`aos agent tools add/rm`、`aos agent config recheck`、`aos agent say`（在寄件 node 提交）、`aos node resume`、`aos clean run`、`aos migrate`、`aos node new`、kernel 段「底層加 `--node`、直接跑持鎖提交」各指令、`aos llm pool step`；另有 B-602「其他寫入者協調這把鎖」、B-620「有權限者同樣能直接跑這些程式」、B-404「人或 agent 也可直接跑」。
- a：「持 tick 的鎖做完一件事」也算一格（人手格），跟 B-627 人手直接跑 `aos-tick` 同級；指令照舊。
- b：指令只寫請求或草稿，由 node 下一格的任務套用（例如 `members add` 投一份請求）；指令都變成非同步。
- c：人手與 CLI 是外部世界，追答 5 只管 aos 自己的程式（tick、任務、daemon），指令照舊。
- d：混搭：設定類走 b，`resume`、`migrate`、`node new` 這些維護動作走 a，「直接跑 module」整類刪掉。

同一題也決定：`node.provision`、`node.pause`／`resume`、`node.show` 等不在追答 5 那四件事（登記、掛行程、叫醒、傳訊）裡的 daemon IPC，人手能不能在 tick 外直接打。

**疑-9（T3）`aos-cg` 在沒 cgroup 時怎麼辦？**（不在 node 框、沒 cgroup v2、框寫不進）
- a：退成程序群組＋subreaper：原指令另開 process group，結束後對群組送 SIGKILL 並收孤兒（沿用 B-631 的備援做法），stderr 印一行。
- b：不開框，直接跑原指令，stderr 印一行。
- c：回 125、不跑。

**疑-10（T5、T6）成員摘要的 `due_ms`（希望上層什麼時候叫醒我）？**
成員不知道上層現在是第幾格。
- a：改 `due_after_ticks`，算上層的格，意思是「從上層讀到這份摘要起再 N 格」；上層讀到時換成自己的 `seq`。
- b：留毫秒時間點，上層每格拿牆鐘比。
- c：算成員自己的格，上層不管。

**疑-11（T3、T4、T5）工作與工具的 `timeout_ms`（once、runner `--timeout-ms`、B-203 逾時）？**
追答 4 說「預算」改 tick、「HTTP 逾時」留毫秒；工具工作的執行上限介於兩者之間。
- a：留毫秒，runner 用 monotonic 量（程序在格外跑）。
- b：改 `timeout_ticks`，算上層（kernel）的格：kernel 每格看，超過就 `node.kill`；精度只到一格。
- c：兩個都有：runner 的毫秒上限是硬擋，kernel 的格數上限是排程預算。

**疑-12（T3、T5、T6）預設值怎麼訂？沒週期的 node 一格多長？**
例如保留期 30 日：週期 1 秒的 node 是 259 萬格，只靠叫醒的 agent 可能好幾年才到。
- a：預設值直接用格數訂（例如保留 10000 格），不從毫秒換；說明裡附「週期 1 秒時約等於…」。
- b：部署時照「舊毫秒 ÷ 本 node 的 `interval_ms`」換；沒週期的用有效上層的週期。
- c：沒週期的 node 不能用這幾個以格計的預設，範本必須寫明。

**疑-13（T2、T1）逃生口（node 自開子框留常駐程序）還留不留？**
它不經通道、不經 tick，正是追答 5 不准的「常駐服務繞過 tick」。
- a：刪掉，要常駐就用 `node.mount` 掛（daemon 追得到、`node.kill` 砍得掉）；`kill_escape_cgroups` 一起刪。
- b：保留，寫明它在 aos 體系之外、部署者自負。
- c：保留，但要經通道向 daemon 報備。

**疑-14（T5）「給你 N 格」要不要這輪就做成機制？**
方向 1 的例子「這個任務要花十個 tick」，spec 目前沒有任何對應欄位。
- a：這輪只把既有時長換成格數，不加新機制，延後到 P-008。
- b：這輪就加：上層在成員清單或叫醒紀錄上寫「給幾格」；用完了怎樣（不再叫醒／`node.pause`／只寫事項）再問一次。

**已寫成建議預設、不另問的**：結束碼紀錄的位置與格式、`seq` 放在紀錄裡、`AOS_TICK_RECORD`；範本各程式名（`aos-git`、`aos-inbox`、`aos-outbox`、`aos-publish`）；git 開格也驗 group／needs 形狀、收件任務驗 `methods` 重複；每格一個 commit、訊息 `aos-tick <seq>`（取代 `aos-tick group …` 與 `aos-tick unclaimed`）；-32601 回應跟本格一起提交；`aos-cg` 開 `task-<seq>-<序號>`、清舊框、清不空回 3；`aos-as` 寫 `.aos/jobs/as-<seq>-<序號>.json`、交 0／1／2；撤 kind 分段檢查；撤 `aos node check`；daemon 啟動那行改成只報自己的 cgroup（例如 `cgroup=on|off`）；daemon 寫進 node 資料夾的事項與旁檔保留；daemon 自動停格保留；「即時改」換詞「免重開」。

## map 欄位說明

[batch20-map.json](batch20-map.json)，契約 `wf-table/1`，378 列。

- `id`：列號，前綴照 kind（新、撤、改、時、格、外、排、舊、原）。
- `kind`：新條、撤銷、改寫、時間、下一格、tick外、排程、舊疑點、原型。
- `title`：主題；`kind=時間` 時是分類（改 tick／保留毫秒／要選）。
- `files`、`clauses`：落在哪些檔與條號（相對 `proto6/spec/`，原型列相對 repo 根）。
- `now`、`change`：現在寫什麼、改成什麼。
- `team`：建議落筆的隊（第九節）。
- `depends`：卡在哪一題疑點。
- `note`：盤點時的補充；`kind=tick外` 保留原盤點的判定與選項。
