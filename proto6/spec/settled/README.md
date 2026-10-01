# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[第二十批裁定](../../notes/verdicts/11-tick-as-unit.md)

## 這是什麼

整理區（`settled/`）放**已經定案、整理好的 tick 與 daemon 基礎**，跟 kernel、agent、LLM、CLI 等其他篇分開。〔使用者方向 2026-09-30，第二十批「整理區」〕

- **git 與 cgroup 已納入，是「有就用」，不是前提。** 沒有時照原來的做法跑；有時的做法寫在各條（git：[B-630、B-622](tick.md)；cgroup：[B-605](daemon/cgroup.md)、[B-634](tick.md)）。提交與還原只限 aos 自己的東西（`.aos/`、任務表、系統級任務動到的檔），使用者任務改的檔 aos 不管。
- **要能自己讀懂。** 區內各篇互相連結；對區外的依賴盡量少，必要的列在下面「對外依賴」。
- **條號不變。** 搬進來的條文條號一律不改，只換檔案位置；搬的時候只改寫法（短句、先講結論、表格、來源標記收到段末「依據：」）。之後的修正輪（[astra 審整理區](../../notes/reviews/2026-09-30/astra-settled-report.md)）照使用者裁定改了規則，改了什麼、哪些先寫成暫定，見下面「疑點」。「建議預設」「暫定」「記錄者理解」這些狀態標記仍留在對應規則旁。
- **收送只管系統訊息佇列**：node 之間經 daemon 通道互送請求與回應，由系統級任務 `aos-mq get`／`aos-mq post` 處理；檔案收件區 `requests/`、`responses/` 的收與寫是普通程式，aos 不管（[B-623、B-624](tick.md)）。
- **主規格是行為正本，協議篇只留格式**（方案 A，[V-01](../conformance.md)）：`tick.md`、`daemon/`、`helper.md` 寫行為；`protocol/` 底下只寫欄位、JSON、argv、結束碼。
- **其他篇之後才放進來**：kernel、LLM、agent、CLI、基底其餘各篇、協議篇其餘各檔，等它們整理好、跟上新基礎，再一起放入。

## 閱讀順序

1. [名詞](terms.md)（T-07 tick 核心、T-09 daemon 用語、T-10 四類程式）：先知道「核心、系統級任務、普通程式、停格檔、擋板檔、通道」這些詞。
2. [通用 tick](tick.md)：核心四件事、結束碼紀錄、標準任務表範本、系統訊息佇列的取與送；git（`aos-git`，B-630、B-622）與每項一框（`aos-cg`，B-634）。
3. [daemon](daemon/README.md)：先讀 [B-615 部件／核心開關](daemon/components.md)，再看登記、叫醒、重啟、收尾、熱重載、佈建、tick–daemon 通道；cgroup 子樹、node 框與上限（B-605）。runner 是什麼見[名詞 T-09](terms.md#t-09收尾排空停機熱重載逃生口)。
4. [helper 與 aos-as](helper.md)：root helper 的界線、怎麼用別的帳號跑任務。
5. 要看格式時：[node 協議](protocol/node.md)（P-200～213：資料夾、任務表、`aos-tick` 與各系統級任務、普通程式的 argv 與結束碼）→ [daemon 協議](protocol/daemon/README.md)（P-100～119：設定、IPC、通道、helper 私有通道、runner）。

## 檔案清單

| 檔 | 條號 | 從哪裡來 |
|---|---|---|
| [README.md](README.md) | — | 新建 |
| [terms.md](terms.md) | T-07、T-09、T-10 | 從 [名詞與責任](../terms.md) 拆出，原處留一行指向這裡 |
| [tick.md](tick.md) | B-602、B-620～634 | 整篇從 `spec/tick.md` 搬來；B-634（`aos-cg`）是納入 cgroup 時從 [B-202](../base/execution.md) 的草稿搬進來的新條 |
| [daemon/](daemon/README.md) | B-504、B-601、B-603～615 | 從 `spec/daemon.md` 搬來，依職責拆檔；落點見 [daemon 目錄](daemon/README.md) |
| [helper.md](helper.md) | B-303 | 從 [身分與資源](../base/identity-resources.md) 拆出，原處留一行指向這裡 |
| [protocol/node.md](protocol/node.md) | P-200～213 | 整篇從 `spec/protocol/node.md` 搬來 |
| [protocol/daemon/](protocol/daemon/README.md) | P-100～119 | 整個資料夾從 `spec/protocol/daemon/` 搬來 |

`spec/protocol/daemon.md` 是舊的單檔入口，留在原處，只改成指向這裡的 daemon 協議。

### daemon 分檔落點

〔使用者方向 2026-09-30 晚〕核心、可掛部件與可關維運分開；條號不改。細分目錄見 [daemon/](daemon/README.md)。

| 落點 | 內容 |
|---|---|
| [components](daemon/components.md) | B-615：分工、開關及未拍板預設 |
| [runtime](daemon/runtime.md) | B-601、B-504；B-605 共通自檢，runner 清程序留核心 |
| [registration](daemon/registration.md) | B-606、B-607：登記、叫醒／暫停 |
| [lifecycle](daemon/lifecycle.md) | B-603、B-604、B-611：重啟、收尾、停機、核心鎖 |
| [channel](daemon/channel.md) | B-610、B-612、B-613：診斷、憑證、掛行程 |
| [reload](daemon/reload.md)、[helper-actions](daemon/helper-actions.md) | B-608、B-609：留核心，各自可關 |
| [messaging](daemon/messaging.md) | B-614：可掛訊息與急件 |
| [cgroup](daemon/cgroup.md) | B-605；B-601、B-603、B-604、B-609、B-611、B-613 的 cgroup 部分 |
| [service](daemon/service.md) | 既有部署範例 |

## 怎麼判斷哪些放進來

- **整篇只講 tick／daemon 基礎** → 整篇搬：`tick.md`、`daemon.md`、node 協議、daemon 協議。
- **混合檔裡某一條整條只講 tick／daemon，拆出來不會斷上下文** → 把那一條搬出來，原處留一行：T-07、T-09、T-10（名詞）、B-303（helper 與 `aos-as`）。
- **條目同時是其他篇的共用基礎，或跟 kernel／agent／LLM 規則纏在一起** → 先留原處，列在下面「待放入」。拆開反而更亂，例如 inst 整份格式、身分額度的歸屬、執行器的後代收尾、清理、跨篇驗收場景。
- **schema 與範例暫留原處**（`spec/protocol/schemas/`、`spec/protocol/examples/node/`、`examples/daemon/`）。理由：schema 彼此以相對檔名 `$ref` 互引，而且是雙向交纏——`common.schema.json` 引用 `node-inst`，kernel、agent、work、llm、msg 各 schema 又引用 `node-inst`、`node-tasks`、`daemon-registration`，daemon 各 schema 則引用 `common`。搬開就得把兩邊的 `$ref` 都改成跨目錄路徑，驗證腳本也要改成兩處登記；等其他篇放進來時一起搬比較穩。整理區的協議篇直接連回原處的 schema 與範例，`validate.py` 不用改。

## 對外依賴

整理區內的文件會引用下面這些區外內容。分兩種：**基礎必需**是普通 tick／daemon 就要用的；**使用例**只是 kernel、agent、LLM 怎麼用這套基礎，不是普通 tick 的前提。

### 基礎必需

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| 來源標記、裁定優先序、「保證跟著掛了什麼走」 | [T-01](../terms.md) | 全區 |
| node 與角色、兩張註冊表 | [T-02](../terms.md) | tick、daemon |
| 工作識別、辨識 tick 的路徑規則 | [T-03](../terms.md) | B-628、B-606 |
| 自訂任務種類 `<類別>.<名稱>`、`system` 不開放子名 | [T-06](../terms.md) | B-626、B-620、P-202 |
| 投件權就是執行權 | [T-08](../terms.md) | B-629、B-612、B-614 |
| 時間以 tick 為基準（格數與毫秒） | [C-01](../contracts.md) | B-633、B-607、B-610、全區時間欄位 |
| 有效上層（跨篇共用說法） | [C-02](../contracts.md) | B-628、B-606 |
| 版本演進、不認得的欄位、永遠禁止的鍵 | [C-07](../contracts.md) | 設定、IPC、通道格式 |
| inst 第 1 版（任務是 inst 的超集；runner 照 inst 跑；子程式另開 session） | [base/inst](../base/inst.md) | B-620、B-601、B-609、B-625、P-201 |
| 身分額度的歸屬 | [B-301](../base/identity-resources.md) | B-620、B-606 |
| 執行器：串流收完、取消競態；OOM 證據 | [B-202、B-203、B-204](../base/execution.md) | B-601、B-604、B-613 |
| 工作材料與結果（掛載行程用新的 inst 路徑、已放行後的結果處理） | [base/work](../base/work.md) | B-610、B-613 |
| 清理（`aos-clean` 這項系統級任務的規則） | [B-404](../base/storage.md) | B-625、B-626、B-629、B-632 |
| 收件區權限（通道送件拿它當判準）；權限落點 | [B-506](../base/transport.md) | B-614、P-208 |
| JSON、錯誤、argv 通則、集中碼表、延後清單 | [P-001～P-008](../protocol/README.md) | 協議篇全部 |
| 請求物件、摘要檔 | [P-301、P-307](../protocol/messages.md) | B-614、B-624、P-206 |
| 事項檔格式、`aos-clean` 的 argv | [P-601、P-605](../protocol/ops.md) | B-601、B-607、B-629 |
| 共用型別 | [common.schema.json](../protocol/schemas/common.schema.json) | 全部 schema |
| schema 與範例 | [schemas/](../protocol/schemas/)、[examples/node/](../protocol/examples/node/)、[examples/daemon/](../protocol/examples/daemon/) | 協議篇 |
| 建立 node、恢復、經 daemon 跑一格的 CLI 入口 | [H-004](../cli/commands.md)、[H-036](../cli/walkthrough.md) | B-625、B-627、P-210 |
| 驗收入口、正本表、條號預留表 | [V-01～V-05](../conformance.md) | 全區 |

### 使用例（不是普通 tick 的前提）

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| 誰叫醒成員、補查、登記成員、資源 | [S-201、S-202、S-203](../scheduling/admission.md)、[P-802](../protocol/kernel-tasks.md) | B-504、B-601、B-603、B-604、B-606、B-614 |
| unknown 判讀、事項處理 | [S-401、S-405](../scheduling/operations.md) | B-601、B-603、B-604、B-607、B-613、B-624 |
| kernel／agent 的領域設定驗證 | [A-102](../agent/configuration.md) | B-625、P-207、P-210 |
| 掛行程的參數怎麼填（agent 自跑工具、LLM 池代發） | [P-402](../protocol/work.md) | B-613 |
| kernel／agent 範本 | [P-715](../protocol/agent-tasks.md)、[P-814](../protocol/kernel-tasks.md) | B-629、P-210 |
| LLM 與工具路線的核對、kernel 對成員的觀察權 | [B-506](../base/transport.md) | P-208 |

## 待放入

跟 tick／daemon 有關、但這輪先留在原處的：

- [名詞與責任](../terms.md) 的 T-01、T-02、T-03、T-06、T-08（上表）。
- [共用契約](../contracts.md) C-01、C-02、C-07。
- [base/inst](../base/inst.md) 整篇；[身分與資源](../base/identity-resources.md) 的 B-301、B-302；[執行器](../base/execution.md) 的 B-201～204（`aos-cg` 已搬成整理區的 B-634）；[儲存](../base/storage.md) 的 B-404；[投件](../base/transport.md) 的 B-506。
- [驗收入口](../conformance.md)：V-01 的正本表與條號預留表（已改成指向整理區的檔名）、V-03 第十九批與第二十批的 tick／daemon 場景（跟各條文末的驗收句重複，正本以條文為準）。
- 上面列的 schema 與範例。
- **待處理的舊格式**〔astra 審整理區同日定案後〕：待送封套 schema [msg-outbox](../protocol/schemas/msg-outbox.schema.json) 與範例 `examples/messages/outbox.*`（`validate.py` 還用 `outbox` 這個檔名對它）是檔案投件的格式，已不適用；`.aos/mq/post/` 與 `.aos/mq/failed/` 的新格式（P-206）還沒有 schema。先不刪，下一輪換掉。

## 疑點

### 09-30 晚拆分：開關細節未拍板

本輪的名稱、預設值、重開時機、關閉行為與 helper 動作界線集中在 [B-615 待拍板](daemon/components.md#這輪待拍板)。本輪只改 Markdown，P-101 的五個設定鍵尚未同步到 schema／範例；不影響這輪拆檔完成，落實前須補。

整理時發現、沒有自己改的；以及這輪修正裡先寫成「暫定」的。每條附條號。

### 系統訊息佇列改寫後，區外要跟上的（本輪沒改）

檔案收件與投件改成普通程式、aos 不管（B-623、B-624），系統級收送只剩 `aos-mq`，鬧鐘撤。下面這些區外條文還寫著舊保證（-32601 由收件任務回、下一格刪原件、`.aos/outbox/` 待送封套、投件任務寫對方 `requests/`、鬧鐘），下一輪要改：

| 篇 | 條號 |
|---|---|
| base | [B-501、B-503、B-506](../base/transport.md)（-32601、補投原回應、「已消費的原件等下一格收件任務刪」）；[B-401、B-402、B-404](../base/storage.md)（`.aos/outbox/`、Q1／Q2 順序、壞收件原件保留）；[B-101](../base/work.md) |
| scheduling | [S-301、S-307](../scheduling/llm.md)（-32601 並清原件）；[S-406](../scheduling/operations.md) |
| agent | [A-201、A-203](../agent/input.md)（通道收件由「收件任務」`node.take`，現在只准 `aos-mq get`）；[A-302、A-304](../agent/memory.md)；[A-403](../agent/tools.md)；[agent 篇首](../agent/README.md)（module 把請求放 `.aos/outbox/`） |
| 協議 | [P-003、P-004、P-005、P-008、P-009](../protocol/README.md)；[P-300、P-301、P-303、P-305、P-306、P-307](../protocol/messages.md)；[P-402、P-411](../protocol/work.md)；[P-502](../protocol/resources.md)；[P-601](../protocol/ops.md)（`bad_request` 事項）；[P-701、P-703～706、P-715](../protocol/agent-tasks.md)（P-706 的預設鬧鐘已撤）；[P-800、P-803、P-814](../protocol/kernel-tasks.md) |
| CLI | [H-004](../cli/commands.md)（布局還列 `outbox/`、`alarms/`）、[H-030](../cli/mapping-and-alias.md)、[H-037](../cli/debugging.md) |
| 契約與驗收 | [T-08](../terms.md)；[V-01](../conformance.md) 正本表第 08～11、27、28 列；V-03 收件與派出、-32601、壞收件、鬧鐘、git 斷電等場景 |

### 納入 git 與 cgroup 後，區外的狀況

**已改到不矛盾**（只換掉「本輪／下一步納入」這類句子，沒重寫）：terms T-01、T-06；spec 入口的定位與依賴段；contracts C-01（格數斷電不倒退只在開 `--firstdo-fsync` 時保證）、C-05 殘句、C-07 第 3 點；base [B-202、B-204](../base/execution.md)（`aos-cg` 改指 B-634）、[storage 篇首與 B-404](../base/storage.md)、[transport 篇首、B-502、B-503 驗收](../base/transport.md)、[inst 撤回範圍句](../base/inst.md)、[B-302](../base/identity-resources.md)、base/README；[P-603、P-606](../protocol/ops.md)；[P-305](../protocol/messages.md)；[A-102](../agent/configuration.md) 第 15 行；V-01～V-03。

**仍跟新規則衝突、下一輪要改**：

| 篇 | 條號 | 衝突在哪 |
|---|---|---|
| agent | [A-102](../agent/configuration.md)（第 17、21、24 行） | 「由標準配備的 git 提交」「node 是 dirty 就拒絕」；現在 `config/` 不在 aos 範圍、`aos-config-add` 不提交 |
| agent | [A-403 等](../agent/tools.md) | 「標準配備」「cgroup 讀數；備援」字樣 |
| base | [B-503](../base/transport.md) | 補投從 git 歷史撈 `.aos/outbox/`（檔案收件已不歸 aos） |
| base | [storage](../base/storage.md) 第 12、31 行 | 「git 還原不碰」與提交語意是整格原子的舊說法 |
| 範本 | [P-814](../protocol/kernel-tasks.md)、[P-715](../protocol/agent-tasks.md) | 還沒有有 git 版範本 |
| scheduling | [S-203、S-205](../scheduling/admission.md) | kernel 資源任務經 `cgroup_limits` 寫上限、沒 cgroup 時只記帳，要核對 |
| CLI | [H-004、H-036](../cli/commands.md) | `aos node new` 建初始 commit、建 `.aos/mq/get/` 並設權限、`--firstdo-fsync` 旗標 |
| 原型程式 | `proto6/proto/aosproto/config.py` | 還把 `cgroup_create` 當合法佈建動作 |

### 納入 git 與 cgroup：原暫定 13 題，已定案

使用者 2026-09-30 對這 13 題說「隨意」，照暫定寫法定案（[裁定](../../notes/verdicts/11-tick-as-unit.md)），對應條文的「暫定」標記已拿掉。定案內容：

- B-630、P-205：兩個相鄰存檔點之間全是 `kind:"system"` 的段才算 aos 範圍，`kind` 照紀錄 `id` 查任務表；`aos-git mark <路徑…>` 讓使用者任務把自己的檔加進 aos 範圍；失敗還原到往前最近的存檔點。
- B-629：第二個存檔點放在清理之前；範本 `id`（`git-open`、`mark-get`、`mark-user`、`git-close`）。
- B-623、B-624、B-630：作廢那格 `mq-get` 取出的訊息丟失、`mq-post` 已送檔下一格重送，靠 ID 去重。
- B-622：只有開頭檢查算「不能用」，做到一半失敗算故障（擋板＋停格檔，含任務 id 當不了 ref 名）。
- B-625、P-207：`config/` 不在 aos 範圍，`aos-config-add` 不自己提交。
- B-605、B-601：某 node 建框失敗只有它照沒 cgroup 跑、寫事項。
- B-609：`cgroup_limits` 不收本格憑證。
- B-633、B-601：`--firstdo-fsync` 由 daemon 放環境變數 `AOS_TICK_FIRSTDO_FSYNC=1` 傳下去。
- B-614、P-200：佇列授權看收件 tick 的 `.aos/mq/get/`。
- B-624、P-206：失敗紀錄搬到 `.aos/mq/failed/`，由 `mq-post` 下次開始送之前清掉。
- **同 ID 撞檔名（原第 13 題，沒有現成做法，落 spec 者挑最簡單的）**：`.aos/mq/post/` 與 `.aos/mq/failed/` 的檔名改成 `<id>.req.json`（請求）、`<id>.resp.json`（回應），同 ID 的請求與回應各有各的檔（P-206、B-624）。

### 前一輪留下、仍是暫定的（astra 審整理區修正輪）

1. B-609、B-303：`aos-as` 被殺後，runner 從回報 pipe 斷線發現、清空原指令；從 `aos-as` 結束到 runner 清完之間，本格下一項可能短暫重疊。沒有另設取消介面。
2. B-609：`aos-as` 寫的暫存 inst 要讓目標帳號讀得到，才過得了 runner 的來源核對；怎麼給讀權（群組？）還沒定。
3. B-633：沒有紀錄的格不佔 `seq`；~~本格紀錄失效後不再寫、不設 `AOS_TICK_RECORD`~~（作廢，2026-09-30 晚）；兩份舊紀錄都讀不懂時每格都沒有紀錄，要人手修。
4. B-620「誰驗什麼」：核心看到缺 `kind`、`system.x` 照跑，只有恢復前驗證（B-625）擋。
5. B-625、P-207：`aos-config-add` 有擋板時回 125。
6. B-606：名稱綁 UID 只在本次 daemon 存續期內有效，不存檔。
7. B-610、B-607（裁-2 落地）：`mount_diag_ttl_ticks` 數上層那筆登記的 `tick_seq`，是「時長一律數 `seq`」的唯一例外。runner 的 `--timeout-ms` 照第二十批疑-11 仍是毫秒。
8. B-623（裁-1 落地）：只有 `aos-mq get` 取佇列是 node 內的約定，daemon 分不出是哪一項在取。沒有通道時 `aos-mq` 回 0。
9. B-624：鬧鐘撤；`.aos/mq/post/` 的格式暫定，schema 未補。
10. B-629：範本沒有另列「檔案收件程式」。kernel、agent 範本（P-814、P-715）與範本範例還沒改，也還沒有有 git 版（`validate.py` 過渡期兩種項數都收）。

### 這輪關掉的

- 舊第 1 題（B-601 runner 當收屍人）：使用者確認定案，拿掉暫定。
- 舊第 4 題的「開格一定 fsync」：改成預設不 fsync、格數不倒退不保證，除非開 `--firstdo-fsync`（B-633）；剩下的已定案（見上「原暫定 13 題」）與第 3 題。
- 舊第 8 題的一半：pause 存檔間隔與事項批次保留毫秒，使用者裁定。
- 舊第 10 題的「回應怎麼回」：回應也走 `aos-mq`（B-623、B-624、B-614、P-119）；送不出去的改成留一格失敗紀錄（已定案，見上）。
- 舊第 11 題（佇列授權看 `requests/`）：改看 `.aos/mq/get/`（已定案，見上）。
- 舊第 13 題（逃生口）：疑-7 准，照第十八批 Q19：aos 不管，`kill_escape_cgroups` 恢復、預設不殺（B-605、T-09）。
- 舊第 14 題（草稿的「開格刪收件原件」）：疑-4 下游不認得 git，那一步拿掉（B-630）。
- 納入 cgroup 與 git 計畫的疑-1～12：照使用者裁定落進 B-620、B-622～625、B-629、B-630、B-632、B-602（git）與 B-601、B-603～606、B-609、B-611、B-613、B-634（cgroup）；計畫裡的救援 ref（疑-3 b）、close 前景 gc、`cgroup_create`／`cgroup_delegate` 兩個佈建動作（疑-10 b）都沒採用。

### 基礎條文依賴 kernel／agent 規則（已在上面「使用例」標出，留待其他篇放進來時再定）

11. B-601、B-607：事項怎麼處理、`issue_id` 沿用規則依賴 S-405；事項檔格式依賴 P-601。
12. B-603、B-604（排空停）、B-613、B-624：被收尾或結果不明的工作怎麼判讀，依賴 S-401 的 unknown 規則。
13. B-504、B-604（停用與退役）、B-606（別每格重登）：補查、成員登記依賴 S-202、P-802；條文已標「使用例：kernel 那側」。
14. B-614：急件越過上層排程任務的 `max_active_members`（S-202）。
15. B-605：沒有 quota 時磁碟用量由磁碟資源任務量（S-203）。

### 更早幾輪修掉的舊疑點

舊第 11、12（git 殘句）→ B-607、P-207 改寫；13、14、15（cgroup 沒標下一步）→ P-208、B-303、B-611 已標；16 → B-626 改成 B-601、B-603～605、B-609；17～25（行為只寫在協議篇）→ 已搬回 B-601、B-603、B-606、B-620、B-633，協議篇只留連結；26 → P-101 寫明九種不含 `spawn_as`；27 → P-119 改寫。舊第 1 題的 A-102 依賴改成 B-625 為通用正本、A-102 只管領域驗證。
