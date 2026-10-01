# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[第二十批裁定](../../notes/verdicts/11-tick-as-unit.md)｜[現行程式](../../src/py/README.md)

## 這是什麼

整理區（`settled/`）放**已經定案、整理好的 tick 與 daemon 基礎**，跟 kernel、agent、LLM、CLI 等其他篇分開。〔使用者方向 2026-09-30，第二十批「整理區」〕

**2026-10-01 統一更新**：整理區改成跟現行 Python POC（[proto6/src/py](../../src/py/README.md)）與當天的裁定一致，分成兩塊：

- **正式篇**：現在就照著做的規定。tick 核心縮成三件事（簡單互斥鎖、照表跑、每項結束碼紀錄）；daemon 縮成「定期叫 `aos-exec` 的 cron」加一個可掛的控制模組；另開一篇通用慣例（結束碼、狀態資料夾名、環境變數）。
- **[暫緩區](deferred/README.md)**：已經想好、但現在先不做的規定（完整互斥、上下層判定、任務帳號 125、落盤與紀錄失效、整套舊 daemon、helper、cgroup、訊息）。原文照留、條號保留不重用，每條標「暫緩」或「已被 X 取代」。

其他原則照舊：

- **條號不變、不重用。** 搬家只換檔案位置；新規定開新號。
- **主規格是行為正本，協議篇只留格式**（方案 A，[V-01](../conformance.md)）：`tick.md`、`daemon/` 寫行為；`protocol/` 底下只寫欄位、JSON、argv、結束碼。
- **git 與 cgroup 是「有就用」，不是前提**（git：[B-630、B-622](tick/git.md)；cgroup：`aos-cg` [B-634](tick/cg.md)，daemon 那側在暫緩區）。提交與還原只限 aos 自己的東西，使用者任務改的檔 aos 不管。
- **系統級任務與普通程式**（`aos-git`、`aos-mq`、`aos-clean`、`aos-cg`；`aos-publish` 2026-10-01、`aos-tick-check-task` 第十六批搬暫緩區）放在正式篇的 [tick/ 子篇](tick/README.md)：它們是之後幾段要做的獨立程式，規定沒被推翻；每篇開頭一行標狀態（已實作／待實作／依賴暫緩），用到暫緩區東西的地方各條有註明。〔使用者 2026-10-01；astra 報告建議 1〕
- **要能自己讀懂**：區內各篇互相連結；對區外的依賴列在下面「對外依賴」。
- **其他篇之後才放進來**：kernel、LLM、agent、CLI、基底其餘各篇，等它們跟上新基礎再放入。

## 閱讀順序

1. [通用慣例](conventions.md)（C-08 結束碼、C-09 `AOS_DIRNAME`、C-10 環境變數總表、C-11 設定檔頂層 `cwd` 與指示詞展開範圍）：aos 每支程式都守的規矩，最短，先讀。
2. [名詞](terms.md)（T-07 tick 核心、T-10 四類程式、T-11 daemon 核心與模組）：先知道「核心、系統級任務、普通程式、tasks-blocked（原停格檔）、擋板檔、模組」這些詞。
3. [通用 tick 核心](tick.md)：核心三件事（B-626、B-602、B-620、B-633）與直接跑（B-627）→ [tick/ 子篇](tick/README.md)：標準任務表範本、`aos-cg`、佇列的取與送、git、當機恢復，每篇開頭標狀態。〔使用者 2026-10-01 拆篇〕
4. [daemon](daemon/README.md)：[B-640 最核心 daemon](daemon/core.md) → [B-641 控制模組與 `aos-ctl`](daemon/control.md) → [B-642 重讀設定](daemon/reload.md)、[B-643 記住狀態](daemon/state.md)、[B-644 收屍／cgroup](daemon/cgroup.md)、[B-645 訊息與 `aos-mq`](daemon/mq.md)、[B-646 帳號](daemon/account.md)。
5. 要看格式時：[tick 協議](protocol/tick.md)（P-200～214：工作資料夾布局、任務表、`aos-tick` 與各系統級任務的 argv 與結束碼；原 `protocol/node.md`，2026-10-01 改名）→ [daemon 協議](protocol/daemon/README.md)（P-120 設定檔與輸出、P-121 控制 socket 與 `aos-ctl`）。
6. 想知道「以後還會有什麼」：[暫緩區](deferred/README.md)。

## 檔案清單

| 檔 | 條號 | 說明 |
|---|---|---|
| [README.md](README.md) | — | 本篇 |
| [conventions.md](conventions.md) | C-08、C-09、C-10、C-11 | 2026-10-01 新開；C-11 是第二批新開 |
| [terms.md](terms.md) | T-07、T-10、T-11 | 從 [名詞與責任](../terms.md) 拆出；T-11 是 2026-10-01 新開；T-09 搬到暫緩區 |
| [tick.md](tick.md) | B-626、B-602、B-620、B-633、B-627 | tick 核心（已實作）。從 `spec/tick.md` 搬來；B-628 與 B-602、B-620、B-633 的部分內容搬到暫緩區；2026-10-01 其餘各條拆到 tick/〔使用者 2026-10-01〕 |
| [tick/](tick/README.md) | B-629、B-636、B-634、B-631（撤）、B-623、B-624、B-630、B-622、B-632、B-625、B-635 | 2026-10-01 從 tick.md 拆出，條號不變；同日第六批新開 [hooks](tick/hooks.md)（B-635，外掛掛點，已實作）：[template](tick/template.md)（B-629）、[check-task](deferred/tick.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)（B-621）、[cg](tick/cg.md)（B-634、B-631）、[mq](tick/mq.md)（B-623、B-624）、[git](tick/git.md)（B-630、B-622、B-632）、[recovery](tick/recovery.md)（B-625）；狀態見[子篇入口](tick/README.md) |
| [daemon.md](daemon.md) | — | 舊的 daemon 入口，只指向 daemon 目錄 |
| [daemon/](daemon/README.md) | B-640～646 | 2026-10-01 重寫：[core](daemon/core.md)（B-640）、[control](daemon/control.md)（B-641）、[reload](daemon/reload.md)（B-642）、[state](daemon/state.md)（B-643）、[cgroup](daemon/cgroup.md)（B-644）、[mq](daemon/mq.md)（B-645）、[account](daemon/account.md)（B-646） |
| [protocol/tick.md](protocol/tick.md) | P-200～214 | tick 協議。從 `spec/protocol/node.md` 搬來；2026-10-01 由 `protocol/node.md` 改名〔使用者 2026-10-01〕 |
| [protocol/daemon/](protocol/daemon/README.md) | P-100、P-120～126 | 2026-10-01 重寫：[core](protocol/daemon/core.md)（P-120）、[control](protocol/daemon/control.md)（P-121）、[reload](protocol/daemon/reload.md)（P-122）、[state](protocol/daemon/state.md)（P-123）、[cgroup](protocol/daemon/cgroup.md)（P-124）、[mq](protocol/daemon/mq.md)（P-125）、[account](protocol/daemon/account.md)（P-126） |
| [deferred/](deferred/README.md) | B-628、T-09、B-303、B-504、B-601、B-603～615、P-101～119 | 暫緩區；總表與每條狀態見它的 README |

`spec/protocol/daemon.md` 是更舊的單檔入口，留在原處，只指向這裡的 daemon 協議。

## 怎麼判斷哪些放進來

- **整篇只講 tick／daemon 基礎** → 整篇搬：`tick.md`（2026-10-01 再拆成核心與 tick/ 子篇）、`daemon.md`、tick 協議（原 node 協議）、daemon 協議。
- **混合檔裡某一條整條只講 tick／daemon，拆出來不會斷上下文** → 把那一條搬出來，原處留一行：T-07、T-09、T-10（名詞）、B-303（helper 與 `aos-as`）。
- **條目同時是其他篇的共用基礎，或跟 kernel／agent／LLM 規則纏在一起** → 先留原處，列在下面「待放入」。拆開反而更亂，例如 inst 整份格式、身分額度的歸屬、執行器的後代收尾、清理、跨篇驗收場景。
- **schema 與範例暫留原處**（`spec/protocol/schemas/`、`spec/protocol/examples/tick/`（原 `examples/node/`）、`examples/daemon/`；schema 2026-10-01 改名：`node-inst`→`inst`、`node-tasks`→`tick-tasks`、`node-tick-record`→`tick-record`〔使用者 2026-10-01〕）。理由：schema 彼此以相對檔名 `$ref` 互引，而且是雙向交纏——`common.schema.json` 引用 `inst`，kernel、agent、work、llm、msg 各 schema 又引用 `inst`、`tick-tasks`、`daemon-registration`，daemon 各 schema 則引用 `common`。搬開就得把兩邊的 `$ref` 都改成跨目錄路徑，驗證腳本也要改成兩處登記；等其他篇放進來時一起搬比較穩。整理區的協議篇直接連回原處的 schema 與範例，`validate.py` 不用改。

## 對外依賴

整理區內的文件會引用下面這些區外內容。分三種：**基礎必需**是現行 tick 核心、tick/ 子篇的系統級任務與現行 daemon 就要用的；**只適用舊 daemon** 是暫緩區才用的〔astra 報告必修 1〕；**使用例**只是 kernel、agent、LLM 怎麼用這套基礎，不是普通 tick 的前提。

### 基礎必需

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| 來源標記、裁定優先序、「保證跟著掛了什麼走」 | [T-01](../terms.md) | 全區 |
| 自訂任務種類 `<類別>.<名稱>`、`system` 不開放子名 | [T-06](../terms.md) | B-626、B-620、P-202 |
| 投件權就是執行權 | [T-08](../terms.md) | B-629、B-612、B-614 |
| 時間以 tick 為基準（格數與毫秒） | [C-01](../contracts.md) | B-633、B-607、B-610、全區時間欄位 |
| 版本演進、不認得的欄位、永遠禁止的鍵 | [C-07](../contracts.md) | 設定、IPC、通道格式 |
| inst 第 1 版（任務是 inst 的超集；runner 照 inst 跑；子程式另開 session） | [base/inst](../base/inst.md) | B-620、B-601、B-609、B-625、P-201 |
| 清理（`aos-clean` 這項系統級任務的規則） | [B-404](../base/storage.md) | B-625、B-626、B-629、B-632 |
| 收件區權限（通道送件拿它當判準）；權限落點 | [B-506](../base/transport.md) | B-614、P-208 |
| JSON、錯誤、argv 通則、集中碼表、延後清單 | [P-001～P-008](../protocol/README.md) | 協議篇全部 |
| 請求物件、摘要檔 | [P-301、P-307](../protocol/messages.md) | B-614、B-624、P-206 |
| 事項檔格式、`aos-clean` 的 argv | [P-601、P-605](../protocol/ops.md) | B-601、B-607、B-629 |
| 共用型別 | [common.schema.json](../protocol/schemas/common.schema.json) | 全部 schema |
| schema 與範例 | [schemas/](../protocol/schemas/)、[examples/tick/](../protocol/examples/tick/)、[examples/daemon/](../protocol/examples/daemon/) | 協議篇 |
| 驗收入口、正本表、條號預留表 | [V-01～V-05](../conformance.md) | 全區 |

### 只適用舊 daemon（暫緩區）

〔astra 報告必修 1〕下面這些只有[暫緩區](deferred/README.md)的舊 daemon（登記、通道、格後清理與後代收尾、node 框、上下層、身分額度、經 daemon 跑一格）才用到，現行 tick 核心與 daemon 核心（[B-640](daemon/core.md)、[B-641](daemon/control.md)）都不靠它們，所以不列進「基礎必需」。

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| node 與角色、兩張註冊表 | [T-02](../terms.md) | 舊 daemon 的登記（B-606、B-607） |
| 工作識別、辨識 tick 的路徑規則 | [T-03](../terms.md) | B-628、B-606 |
| 有效上層（跨篇共用說法） | [C-02](../contracts.md) | B-628、B-606 |
| 身分額度的歸屬 | [B-301](../base/identity-resources.md) | B-606（B-620 任務的 `user` 已撤回） |
| 執行器：串流收完、取消競態；OOM 證據 | [B-202、B-203、B-204](../base/execution.md) | B-601、B-604、B-613 |
| 工作材料與結果（掛載行程用新的 inst 路徑、已放行後的結果處理） | [base/work](../base/work.md) | B-610、B-613 |
| 建立 node、恢復、經 daemon 跑一格的舊 CLI 入口 | [H-004](../cli/commands.md)、[H-036](../cli/walkthrough.md) | B-625、B-627、P-210 |

### 使用例（不是普通 tick 的前提）

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| 誰叫醒成員、補查、登記成員、資源 | [S-201、S-202、S-203](../scheduling/admission.md)、[P-802](../protocol/kernel-tasks.md) | B-504、B-601、B-603、B-604、B-606、B-614 |
| unknown 判讀、事項處理 | [S-401、S-405](../scheduling/operations.md) | B-601、B-603、B-604、B-607、B-613、B-624 |
| kernel／agent 的領域設定驗證 | [A-102](../agent/configuration.md) | B-625、P-210（P-207 2026-10-01 搬[暫緩區](deferred/protocol/tick.md)） |
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

### 2026-10-01 統一更新：要使用者裁定的

這輪照現行程式與裁定改 spec 時發現、先照下面寫法落筆的。每條附暫定寫法。〔astra 報告建議 2，2026-10-01 第二批〕已有裁定的（第 3、7 題）與只是文件怎麼標的（第 10 題）改記成結案或編輯事項，真的還要問人的只剩第 1、2、4 題。

1. ~~**`aos-as`（P-212）留在正式篇還是搬暫緩區？**~~ **結案**（使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」）：P-212 整條搬到 [tick 協議暫緩區](deferred/protocol/tick.md)；現行切帳號只在 daemon 設定檔做（帳號模組）。
2. **最簡鎖不傳給任務後，系統級任務沒辦法判斷「我在不在 tick 裡」。** `aos-git` 的 `not_in_tick`、`aos-mq`（以及 2026-10-01 搬暫緩區的 `aos-publish`）原本都靠繼承的鎖核對。暫時：各條寫「要等暫緩區的『鎖 fd 傳給任務』回來才有判法」。
3. ~~**任務 `id` 重複沒人擋。**~~ **照既有裁定，不用再問**（[極簡檢查](../../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查已寫入-speccommit-前由我補號)：「默認不重複」）：核心不檢查；`aos-git` 存檔點用 `id` 取名、重複會混，這個後果寫在 B-620「誰驗什麼」表。〔astra 報告建議 2〕
4. **上下層判定（B-628）暫緩後，兩處沒有正式判準**：`aos-git` 排除巢狀子資料夾（B-622）、發摘要核對「直接下層」（B-624；發摘要 2026-10-01 整段搬暫緩區，這處跟著暫緩）。暫時：寫「B-628 回來前沒有正式判準」。
5. ~~**「node」這個詞在 tick 層還剩不少。**~~ **結案**（使用者 2026-10-01 定：tick 層一律叫「工作資料夾」，英文 `tick dir`）：`protocol/node.md` 改名 [protocol/tick.md](protocol/tick.md)（tick 協議）；schema `node-inst`→`inst`、`node-tasks`→`tick-tasks`、`node-tick-record`→`tick-record`；範例 `examples/node/`→`examples/tick/`；P-200 與系統級任務各條的 node 改成工作資料夾。暫緩區講上下層的「上層 node／下層 node」與 kernel、agent 各篇的 node 不動（[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第二批astra-審查修正tick-層改名拆篇tasksjson-頂層預設已寫入-speccommit-前由我補號)）。
6. ~~**控制 socket 收到不認得的欄位照收不理**（照程式），跟 [C-07](../contracts.md)「daemon IPC 嚴格拒絕不認得的欄位」打架。~~ **結案**（使用者 2026-10-01：「socket收到看不懂的欄位就不理他」，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01daemon-輸出socket-欄位inst-user)）：[C-07](../contracts.md) 的放寬表單列一行「現行控制 socket 忽略」，嚴格只剩舊設計的 daemon IPC；[P-121](protocol/daemon/control.md) 寫明。
7. **照既有裁定，不用再問**（[POC 默認一切正常](../../notes/verdicts/11-tick-as-unit.md#2026-10-01poc-默認一切正常)）〔astra 報告建議 2〕：**`aos-daemon` 的設定錯誤處理有三處跟 schema 不一致**（照「默認一切正常」）：只有指示詞錯印 `aos-daemon: config: <代號>: …`，自己的檢查印 `aos-daemon: config: <說明>`；缺 `insts`、`control` 沒寫 `socket`、某項的值不是物件時程式直接丟 traceback 回 1；schema 要求 `interval_ms` 是非負整數，程式不查型別。暫時：[P-120](protocol/daemon/core.md) 照程式寫，schema 照嚴格寫。
8. ~~**`aos-exec` 的 stdout 直接接到 daemon 的 stdout**，不經 daemon 那把鎖，可能跟 daemon 自己的行交錯。~~ **結案**（使用者 2026-10-01，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01daemon-輸出socket-欄位inst-user)）：頂層新鍵 `exec_out_path` 照 `exec_err_path` 規則收齊再寫；兩個鍵沒寫都丟到 `/dev/null`（[B-640](daemon/core.md)、[P-120](protocol/daemon/core.md)）。
9. ~~**inst 第 1 版的頂層 `user` 要不要留？**~~ **結案**（使用者 2026-10-01：「inst頂層的user欄位不留」，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01daemon-輸出socket-欄位inst-user)）：[inst](../base/inst.md) 拿掉 `user` 的定義與「先決定身分」整節（直接刪、不搬暫緩，記在[暫緩區撤回表](deferred/tick.md)）；任務表的 `user` 一併拿掉。
10. **編輯事項，不是待裁定**〔astra 報告建議 2〕：**整理區以外還有「2＝用法錯」**（kernel 工具、ops、CLI 等）。照 [C-08](conventions.md) 字面是改 1，但那幾篇不在這輪範圍，沒動；整理那幾篇時逐條定改 1 或列為特別指定的碼。

### 2026-10-01 第二批：astra 審查與使用者裁定落實

〔使用者 2026-10-01〕對 [astra 審查](../../notes/reviews/2026-10-01/astra-spec-sync-report.md) 的處理（[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第二批astra-審查修正tick-層改名拆篇tasksjson-頂層預設已寫入-speccommit-前由我補號)）：

- **必修 1～9 已修。** 例如擋板改成「daemon 照常叫，由 tick 自己擋」、舊 daemon 才用的依賴移到上面「只適用舊 daemon」、`AOS_TICK_TOKEN` 改標「現行控制不使用；舊通道憑證暫緩」（[C-10](conventions.md)）、H-036 改連 walkthrough。
- **設計 1（`aos-cg` 收尾會殺到自己）**：記在暫緩區，這輪不改（daemon 那側本來就暫緩）。
- **設計 2（自訂任務表交不給 aos-git）**：結案。`aos-tick` 的目標只能是資料夾、任務表只有一個位置，`aos-git` 讀 `$AOS_TICK_CWD/<狀態資料夾>/tasks.json` 就好（[暫緩區撤回表](deferred/tick.md#已撤回被取代)）。
- **設計 3（`interval_ms` 規則拆成 schema 與腳本兩套）**：改用 schema 的條件規則表達，範例腳本不再重複判定（[P-120](protocol/daemon/core.md)）。
- **建議 1（核心與待做程式分篇）**：已拆成 [tick.md](tick.md) 核心＋[tick/ 子篇](tick/README.md)，各篇開頭標狀態。
- **建議 2（疑點分清哪些要問人）**：上面「要使用者裁定的」已把有裁定的第 3、7 題改記結案、第 10 題改記編輯事項。
- **要使用者裁定 1（`AOS_DIRNAME=""` 時 git 管什麼）**：使用者定「不用特別弄清單，就全部」（[C-09](conventions.md)、[B-630](tick/git.md)）。
- **要使用者裁定 2（檔觸發入口與控制模組的關係）**：node 模組方向裡「用檔觸發、不開 socket」那句已被控制模組（B-641）取代。

這輪落筆時發現、先照下面寫法、要使用者裁定的：

1. ~~**`aos-config-add` 的旗標**：tick 層改名時從 `--node <node_dir>` 改成 `--dir <工作資料夾>`（P-207）。程式還沒寫，沒有相容問題；名字請確認。~~ **已裁定：搬暫緩區**（使用者 2026-10-01，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第四批aos-config-add-搬暫緩區擋板檔與停格檔照現狀)）：`aos-config-add` 從沒寫過程式，整個指令（B-625 那段與 P-207）搬到[暫緩區](deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)；旗標名等加回來時再定。
2. ~~**`AOS_DIRNAME=""` 時的固定排除**~~ **已裁定**（使用者 2026-10-01：照現寫法，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）：狀態資料夾就是工作資料夾，`aos-git` 固定排除的 `tick/`、`tick.lock` 等直接落在工作資料夾頂層；使用者自己的檔剛好同名就不提交也不還原，風險自負（[B-622](tick/git.md)）。
3. ~~**tasks.json 頂層 `_metainfo` 在 schema 是必填**，要不要改成可省？~~ **已裁定**（使用者 2026-10-01，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）：頂層 `_metainfo` 可省，schema 的 `required` 拿掉；每項的 `_metainfo` 照 inst 規則可省（沒寫＝posix 第 1 版），寫了跑到那一項才驗，驗不過＝跑到某項展開失敗（[B-620](tick.md)、[P-202](protocol/tick.md)）。
4. ~~**`modules` 內部 tick 不展開，daemon 那邊整份展開**，兩邊不同。~~ **已裁定**（使用者 2026-10-01，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）：tasks.json 的 `modules` 讀表時也整個展開，跟 daemon 設定檔一致；展開失敗＝`bad_table`、回 1（[C-11](conventions.md)、[B-620](tick.md)）。
5. ~~**頂層陌生鍵讀表時不解**~~ **已裁定**（使用者 2026-10-01：照現寫法，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）：只有七個預設欄位、`tasks` 解一層、`modules` 整個展開；其他頂層鍵（含 `_metainfo`）不解，寫壞了也不會 `bad_table`（[B-620](tick.md)）。
6. ~~**整項 `$ref` 引進來的項、或預設值從別的檔引進來時**~~ **已裁定**（使用者 2026-10-01：照現寫法，[裁定](../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）：合併後裡面的 `$ref:""`／`#…` 指合併後的這一項，不再指原檔，寫在 B-620。

### 系統訊息佇列改寫後，區外要跟上的（還沒改）

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
| agent | [A-102](../agent/configuration.md)（第 17、21、24 行） | 「由標準配備的 git 提交」「node 是 dirty 就拒絕」；現在 `config/` 不在 aos 範圍、`aos-config-add` 不提交（2026-10-01 `aos-config-add` 搬暫緩區，A-102 那段已標暫緩） |
| agent | [A-403 等](../agent/tools.md) | 「標準配備」「cgroup 讀數；備援」字樣 |
| base | [B-503](../base/transport.md) | 補投從 git 歷史撈 `.aos/outbox/`（檔案收件已不歸 aos） |
| base | [storage](../base/storage.md) 第 12、31 行 | 「git 還原不碰」與提交語意是整格原子的舊說法 |
| 範本 | [P-814](../protocol/kernel-tasks.md)、[P-715](../protocol/agent-tasks.md) | 還沒有有 git 版範本 |
| scheduling | [S-203、S-205](../scheduling/admission.md) | kernel 資源任務經 `cgroup_limits` 寫上限、沒 cgroup 時只記帳，要核對 |
| CLI | [H-004](../cli/commands.md)、[H-036](../cli/walkthrough.md)〔astra 報告必修 9〕 | `aos node new` 建初始 commit、建 `.aos/mq/get/` 並設權限、`--firstdo-fsync` 旗標 |
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
- B-633、B-601：`--firstdo-fsync` 由 daemon 放環境變數 `AOS_TICK_FIRSTDO_FSYNC=1` 傳下去。（2026-10-01 跟落盤一起暫緩，見[暫緩區](deferred/tick.md)）
- B-614、P-200：佇列授權看收件 tick 的 `.aos/mq/get/`。
- B-624、P-206：失敗紀錄搬到 `.aos/mq/failed/`，由 `mq-post` 下次開始送之前清掉。
- **同 ID 撞檔名（原第 13 題，沒有現成做法，落 spec 者挑最簡單的）**：`.aos/mq/post/` 與 `.aos/mq/failed/` 的檔名改成 `<id>.req.json`（請求）、`<id>.resp.json`（回應），同 ID 的請求與回應各有各的檔（P-206、B-624）。

### 前一輪留下、仍是暫定的（astra 審整理區修正輪）

2026-10-01 起，第 1、2、6、7 題講的條（B-609、B-303、B-606、B-610、B-607）都在[暫緩區](deferred/README.md)，跟著暫緩；第 4 題已由「極簡檢查」取代（核心連 `kind` 都不看）。

1. B-609、B-303：`aos-as` 被殺後，runner 從回報 pipe 斷線發現、清空原指令；從 `aos-as` 結束到 runner 清完之間，本格下一項可能短暫重疊。沒有另設取消介面。
2. B-609：`aos-as` 寫的暫存 inst 要讓目標帳號讀得到，才過得了 runner 的來源核對；怎麼給讀權（群組？）還沒定。
3. B-633：沒有紀錄的格不佔 `seq`（現行）；兩份舊紀錄都讀不懂時每格都沒有紀錄、要人手修（2026-10-01 跟紀錄失效處理一起暫緩，見[暫緩區](deferred/tick.md)）。
4. B-620「誰驗什麼」：核心看到缺 `kind`、`system.x` 照跑，只有恢復前驗證（B-625）擋。
5. B-625、P-207：`aos-config-add` 有擋板時回 125。（2026-10-01 隨 `aos-config-add` 搬[暫緩區](deferred/tick.md#暫緩b-625-加入普通設定aos-config-add)。）
6. B-606：名稱綁 UID 只在本次 daemon 存續期內有效，不存檔。
7. B-610、B-607（裁-2 落地）：`mount_diag_ttl_ticks` 數上層那筆登記的 `tick_seq`，是「時長一律數 `seq`」的唯一例外。runner 的 `--timeout-ms` 照第二十批疑-11 仍是毫秒。
8. B-623（裁-1 落地）：只有 `aos-mq get` 取佇列是 node 內的約定，daemon 分不出是哪一項在取。沒有通道時 `aos-mq` 回 0。
9. B-624：鬧鐘撤；`.aos/mq/post/` 的格式暫定，schema 未補。
10. B-629：範本沒有另列「檔案收件程式」。kernel、agent 範本（P-814、P-715）與範本範例還沒改，也還沒有有 git 版（`validate.py` 過渡期兩種項數都收）。

### 這輪關掉的

- 舊第 1 題（B-601 runner 當收屍人）：使用者確認定案，拿掉暫定。
- 舊第 4 題的「開格一定 fsync」：改成預設不 fsync、格數不倒退不保證，除非開 `--firstdo-fsync`（B-633；這個旗標 2026-10-01 暫緩）；剩下的已定案（見上「原暫定 13 題」）與第 3 題。
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
