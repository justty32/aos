# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[第二十批裁定](../../notes/verdicts/11-tick-as-unit.md)

## 這是什麼

整理區（`settled/`）放**已經定案、整理好的 tick 與 daemon 基礎**，跟 kernel、agent、LLM、CLI 等其他篇分開。〔使用者方向 2026-09-30，第二十批「整理區」〕

- **本輪假設沒有 cgroup、沒有 git。** 各篇的「下一步納入（git 與 cgroup）」段照原樣保留，不是現行規則；那兩樣另一輪才納入。
- **要能自己讀懂。** 區內各篇互相連結；對區外的依賴盡量少，必要的列在下面「對外依賴」。
- **規則不變。** 搬進來的條文條號一律不改，只換檔案位置；順手整理只改寫法（短句、先講結論、表格、來源標記收到段末「依據：」），不改意思。「建議預設」「暫定」「記錄者理解」這些狀態標記仍留在對應規則旁。
- **主規格是行為正本，協議篇只留格式**（方案 A，[V-01](../conformance.md)）：`tick.md`、`daemon.md`、`helper.md` 寫行為；`protocol/` 底下只寫欄位、JSON、argv、結束碼。
- **其他篇之後才放進來**：kernel、LLM、agent、CLI、基底其餘各篇、協議篇其餘各檔，等它們整理好、跟上新基礎，再一起放入。

## 閱讀順序

1. [名詞](terms.md)（T-07 tick 核心、T-09 daemon 用語、T-10 四類程式）：先知道「核心、系統級任務、普通程式、停格檔、擋板檔、通道」這些詞。
2. [通用 tick](tick.md)：核心四件事、結束碼紀錄、標準任務表範本、收件與投件。
3. [daemon](daemon.md)：登記、叫醒、重啟、收尾、熱重載、佈建、tick–daemon 通道。
4. [helper 與 aos-as](helper.md)：root helper 的界線、怎麼用別的帳號跑任務。
5. 要看格式時：[node 協議](protocol/node.md)（P-200～213：資料夾、任務表、`aos-tick` 與各系統級任務、普通程式的 argv 與結束碼）→ [daemon 協議](protocol/daemon/README.md)（P-100～119：設定、IPC、通道、helper 私有通道、runner）。

## 檔案清單

| 檔 | 條號 | 從哪裡來 |
|---|---|---|
| [README.md](README.md) | — | 新建 |
| [terms.md](terms.md) | T-07、T-09、T-10 | 從 [名詞與責任](../terms.md) 拆出，原處留一行指向這裡 |
| [tick.md](tick.md) | B-602、B-620～633 | 整篇從 `spec/tick.md` 搬來 |
| [daemon.md](daemon.md) | B-504、B-601、B-603～614 | 整篇從 `spec/daemon.md` 搬來 |
| [helper.md](helper.md) | B-303 | 從 [身分與資源](../base/identity-resources.md) 拆出，原處留一行指向這裡 |
| [protocol/node.md](protocol/node.md) | P-200～213 | 整篇從 `spec/protocol/node.md` 搬來 |
| [protocol/daemon/](protocol/daemon/README.md) | P-100～119 | 整個資料夾從 `spec/protocol/daemon/` 搬來 |

`spec/protocol/daemon.md` 是舊的單檔入口，留在原處，只改成指向這裡的 daemon 協議。

## 怎麼判斷哪些放進來

- **整篇只講 tick／daemon 基礎** → 整篇搬：`tick.md`、`daemon.md`、node 協議、daemon 協議。
- **混合檔裡某一條整條只講 tick／daemon，拆出來不會斷上下文** → 把那一條搬出來，原處留一行：T-07、T-09、T-10（名詞）、B-303（helper 與 `aos-as`）。
- **條目同時是其他篇的共用基礎，或跟 kernel／agent／LLM 規則纏在一起** → 先留原處，列在下面「待放入」。拆開反而更亂，例如 inst 整份格式、身分額度的歸屬、執行器的後代收尾、清理、投件去重、跨篇驗收場景。
- **schema 與範例暫留原處**（`spec/protocol/schemas/`、`spec/protocol/examples/node/`、`examples/daemon/`）。理由：schema 沒有 `$id`，彼此以相對檔名互引，而且是雙向交纏——`common.schema.json` 引用 `node-inst`，kernel、agent、work、llm、msg 各 schema 又引用 `node-inst`、`node-tasks`、`daemon-registration`，daemon 各 schema 則引用 `common`。搬開就得把兩邊的 `$ref` 都改成跨目錄路徑，驗證腳本也要改成兩處登記；等其他篇放進來時一起搬比較穩。整理區的協議篇直接連回原處的 schema 與範例，`validate.py` 不用改。

## 對外依賴

整理區內的文件會引用下面這些區外內容。它們是共用的，或還沒整理進來。

| 依賴 | 在哪 | 用在哪 |
|---|---|---|
| 來源標記、裁定優先序、「保證跟著掛了什麼走」 | [T-01](../terms.md) | 全區 |
| node 與角色、兩張註冊表 | [T-02](../terms.md) | tick、daemon |
| 工作識別、辨識 tick 的路徑規則 | [T-03](../terms.md) | B-628、B-606 |
| 自訂任務種類 `<類別>.<名稱>`、`system` 不開放子名 | [T-06](../terms.md) | B-626、P-202 |
| 投件權就是執行權 | [T-08](../terms.md) | B-629、B-612、B-614 |
| 時間以 tick 為基準（格數與毫秒） | [C-01](../contracts.md) | B-633、B-607、全區時間欄位 |
| 有效上層（跨篇共用說法） | [C-02](../contracts.md) | B-628、B-606 |
| 版本演進、不認得的欄位、永遠禁止的鍵 | [C-07](../contracts.md) | 設定、IPC、通道格式 |
| inst 第 1 版（任務是 inst 的超集；runner 照 inst 跑） | [base/inst](../base/inst.md) | B-620、B-601、B-609、P-201 |
| 身分額度的歸屬 | [B-301](../base/identity-resources.md) | B-620、B-606 |
| 執行器：後代清空、取消、資源失敗；`aos-cg` 草稿 | [B-202、B-203、B-204](../base/execution.md) | B-601、B-604、B-613 |
| 工作材料與結果（掛載行程用新的 inst 路徑、已放行後的結果處理） | [base/work](../base/work.md) | B-610、B-613 |
| 清理（`aos-clean` 這項系統級任務的規則） | [B-404](../base/storage.md) | B-626、B-629、B-632 |
| method 與 -32601、去重與同 ID 衝突、收件區權限 | [B-501、B-503、B-506](../base/transport.md) | B-620、B-623、B-624 |
| JSON、錯誤、argv 通則、集中碼表、延後清單 | [P-001～P-008](../protocol/README.md) | 協議篇全部 |
| 請求物件、摘要檔 | [P-301、P-307](../protocol/messages.md) | B-614、B-624 |
| 待送封套的 schema 與範例 | [msg-outbox](../protocol/schemas/msg-outbox.schema.json)、`examples/messages/outbox.*` | P-206 |
| 事項檔格式、`aos-clean` 的 argv | [P-601、P-605](../protocol/ops.md) | B-623、B-607、B-629 |
| 共用型別 | [common.schema.json](../protocol/schemas/common.schema.json) | 全部 schema |
| schema 與範例 | [schemas/](../protocol/schemas/)、[examples/node/](../protocol/examples/node/)、[examples/daemon/](../protocol/examples/daemon/) | 協議篇 |
| 驗收入口、正本表、條號預留表 | [V-01～V-05](../conformance.md) | 全區 |

下面這些是**基礎條文依賴 kernel／agent／LLM 規則**的地方，照原樣保留，列在「疑點」等決定：[A-102](../agent/configuration.md)（設定修改與恢復）、[S-201、S-202、S-203](../scheduling/admission.md)（誰叫醒、補查、資源）、[S-401、S-405](../scheduling/operations.md)（unknown 判讀、事項處理）、[P-402](../protocol/work.md)、[P-706、P-715](../protocol/agent-tasks.md)、[P-802、P-814](../protocol/kernel-tasks.md)、[H-004](../cli/commands.md)。

## 待放入

跟 tick／daemon 有關、但這輪先留在原處的：

- [名詞與責任](../terms.md) 的 T-01、T-02、T-03、T-06、T-08（上表）。
- [共用契約](../contracts.md) C-01、C-02、C-07。
- [base/inst](../base/inst.md) 整篇；[身分與資源](../base/identity-resources.md) 的 B-301、B-302；[執行器](../base/execution.md) 的 B-201～204（B-202 內含 `aos-cg` 的下一步納入草稿）；[儲存](../base/storage.md) 的 B-404；[投件](../base/transport.md) 的 B-501、B-503、B-506。
- [驗收入口](../conformance.md)：V-01 的正本表與條號預留表（已改成指向整理區的檔名）、V-03 第十九批與第二十批的 tick／daemon 場景（跟各條文末的驗收句重複，正本以條文為準）。
- 上面列的 schema 與範例。

## 疑點

整理時發現、沒有自己改的。每條附條號。

**基礎條文依賴 kernel／agent 規則**

1. B-625、B-607（resume）、P-203、P-207、P-210：設定修改、暫停手改與恢復前驗證以 agent 篇的 A-102 為正本；P-210 還依賴 kernel／agent 範本與 CLI 走查 H-036。
2. B-601、B-607、B-623：事項怎麼處理、`issue_id` 沿用規則依賴 S-405（scheduling）；事項檔格式依賴 P-601（ops）。
3. B-603、B-604（排空停）、B-613、B-624：被收尾或結果不明的工作怎麼判讀，依賴 S-401 的 unknown 規則。
4. B-504、B-604（停用與退役）、B-606（別每格重登）：補查、成員登記依賴 S-202、P-802，而且條文直接寫了 kernel 在自己 repo 記 boot id 的做法；P-115 的驗收句也靠 kernel 逐層補回成員。
5. B-601：「agent 通常不設定期，由 kernel 決定何時叫醒…；kernel 本格結束就退出」是在寫 kernel／agent 的行為；daemon 篇首「kernel 決定成員何時能做事」同類。
6. B-614：急件越過上層排程任務的 `max_active_members`（S-202）。
7. B-613：參數怎麼填連到 P-402，舉例是 agent 自跑工具、LLM 池代發。
8. B-605：沒有 quota 時磁碟用量由磁碟資源任務量（S-203）。
9. B-624：agent 範本對每個請求預設帶鬧鐘（P-706）；B-629：預設 kernel 範本（P-814）與 agent 範本（P-715）照新順序，但那兩份範本還沒改（validate.py 過渡期兩種項數都收）。
10. P-208：依賴 B-506 的 LLM 與工具路線核對、kernel 對成員的觀察權。

**殘句或指向已撤、未納入的機制**

11. B-607：pause 寫「有 git 時再 commit」、resume 要「完成 A-102 的驗證與 commit」——本輪沒有 git。
12. P-207：本輪沒有 git，但結束碼 0「已提交」、1「已還原」、3「commit／還原故障」與提交訊息 `aos-config-add <target>` 看起來是 git 殘留，跟同條「只做原子替換」對不上。
13. P-208：表中的 `cgroup_delegate` 本輪回 `unsupported`，卻寫得像現行做法，沒標「下一步納入」。
14. B-303：helper「安置已配置資源框」——本輪沒有 cgroup，「資源框」要不要標下一步納入。
15. B-611：開頭理由還提到「cgroup 子樹」會互相清殺；本輪只取 `state_dir` 的鎖，這句是給以後 cgroup 用的說明，照留。
16. B-626：「helper 都歸 daemon（B-603～605）」——helper 的正本是 B-609 與 B-303，這個條號範圍不太準。

**行為只寫在協議篇（主規格沒有）**

17. P-204：「普通程式回 125 不能猜成沒跑」「沒事做可以不改檔回 0」「在途工作存在領域狀態裡，不用特殊結束碼當排程訊號」。
18. P-206：「領域狀態引用消費副本，不另做通用收據」。
19. P-213：「紀錄只有核心寫」（B-633 只寫「只在持鎖時寫」）。P-203：被停下的格回 1 的理由（不設會讓 daemon 誤當暫停訊號的碼）。
20. P-102：PID 提示檔的規則（啟動寫、正常退出刪、舊檔只當提示不拿來殺）。
21. P-103：「誰可呼叫」授權表本身是行為，B-612 也直接引用它；要不要搬進 B-601／B-606 當正本。
22. P-101：「讀不到 inst 就拒絕，不交 root 代讀」「找不到 inst 時設定檔是用法錯 2、IPC 回 invalid_params」。
23. P-108：`daemon.helper.unbind`「全空且沒有已登記子節點才移除鏡像，由子到父依序解除」。
24. P-111：「超長行回一次 `invalid_request` 後關連線」「可辨識合法 ID 就沿用」。
25. P-115：`boot_id` 的生命週期（每次啟動新生、只放記憶體、socket 路徑相同也不沿用）。

**寫法上容易誤會**

26. P-101：佈建權 `actions`「只認 P-107 的九種」，但 P-107 表有十列（`spawn_as` 不進 `provision.actions`）；意思對，容易誤讀。
27. P-117／P-119：`kind_mismatch` 說明寫「對掛載行程送 send」，指的應該是收件方是掛載行程。
