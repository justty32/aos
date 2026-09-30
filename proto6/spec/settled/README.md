# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[第二十批裁定](../../notes/verdicts/11-tick-as-unit.md)

## 這是什麼

整理區（`settled/`）放**已經定案、整理好的 tick 與 daemon 基礎**，跟 kernel、agent、LLM、CLI 等其他篇分開。〔使用者方向 2026-09-30，第二十批「整理區」〕

- **本輪假設沒有 cgroup、沒有 git。** 各篇的「下一步納入（git 與 cgroup）」段照原樣保留，不是現行規則；那兩樣另一輪才納入。
- **要能自己讀懂。** 區內各篇互相連結；對區外的依賴盡量少，必要的列在下面「對外依賴」。
- **條號不變。** 搬進來的條文條號一律不改，只換檔案位置；搬的時候只改寫法（短句、先講結論、表格、來源標記收到段末「依據：」）。之後的修正輪（[astra 審整理區](../../notes/reviews/2026-09-30/astra-settled-report.md)）照使用者裁定改了規則，改了什麼、哪些先寫成暫定，見下面「疑點」。「建議預設」「暫定」「記錄者理解」這些狀態標記仍留在對應規則旁。
- **收送只管系統訊息佇列**：node 之間經 daemon 通道互送，由系統級任務 `aos-mq get`／`aos-mq post` 處理；檔案收件區 `requests/`、`responses/` 的收與寫是普通程式，aos 不管（[B-623、B-624](tick.md)）。
- **主規格是行為正本，協議篇只留格式**（方案 A，[V-01](../conformance.md)）：`tick.md`、`daemon.md`、`helper.md` 寫行為；`protocol/` 底下只寫欄位、JSON、argv、結束碼。
- **其他篇之後才放進來**：kernel、LLM、agent、CLI、基底其餘各篇、協議篇其餘各檔，等它們整理好、跟上新基礎，再一起放入。

## 閱讀順序

1. [名詞](terms.md)（T-07 tick 核心、T-09 daemon 用語、T-10 四類程式）：先知道「核心、系統級任務、普通程式、停格檔、擋板檔、通道」這些詞。
2. [通用 tick](tick.md)：核心四件事、結束碼紀錄、標準任務表範本、系統訊息佇列的取與送。
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
| 執行器：串流收完、取消競態；`aos-cg` 草稿 | [B-202、B-203](../base/execution.md) | B-601、B-604、B-613 |
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
- [base/inst](../base/inst.md) 整篇；[身分與資源](../base/identity-resources.md) 的 B-301、B-302；[執行器](../base/execution.md) 的 B-201～204（B-202 內含 `aos-cg` 的下一步納入草稿）；[儲存](../base/storage.md) 的 B-404；[投件](../base/transport.md) 的 B-506。
- [驗收入口](../conformance.md)：V-01 的正本表與條號預留表（已改成指向整理區的檔名）、V-03 第十九批與第二十批的 tick／daemon 場景（跟各條文末的驗收句重複，正本以條文為準）。
- 上面列的 schema 與範例。
- **待處理的舊格式**〔astra 審整理區同日定案後〕：待送封套 schema [msg-outbox](../protocol/schemas/msg-outbox.schema.json) 與範例 `examples/messages/outbox.*`（`validate.py` 還用 `outbox` 這個檔名對它）是檔案投件的格式，已不適用；`.aos/mq/post/` 的新格式（P-206）還沒有 schema。先不刪，下一輪換掉。

## 疑點

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

### 這輪修正先寫成「暫定」的（astra 審整理區修正輪）

1. B-601：本輪沒有 cgroup，受管範圍改成「runner 名下整棵樹」：runner 設 subreaper、主程式結束就清空名下再回報；daemon 收尾對 runner 送兩次 SIGTERM（第一次轉送、第二次清空）。runner 自己意外死掉時，掛回 daemon 的程序一律殺掉，那一格記 `unknown`。
2. B-609、B-303：`aos-as` 被殺後，runner 從回報 pipe 斷線發現、清空原指令；從 `aos-as` 結束到 runner 清完之間，本格下一項可能短暫重疊。沒有另設取消介面。
3. B-609：`aos-as` 寫的暫存 inst 要讓目標帳號讀得到，才過得了 runner 的來源核對；怎麼給讀權（群組？）還沒定。
4. B-633：開格那一次要 fsync（暫存檔與目錄），每項之後只 fsync 暫存檔；沒有紀錄的格不佔 `seq`；本格紀錄失效後不再寫、不設 `AOS_TICK_RECORD`；兩份舊紀錄都讀不懂時每格都沒有紀錄，要人手修。
5. B-620「誰驗什麼」：核心看到缺 `kind`、`system.x` 照跑，只有恢復前驗證（B-625）擋。
6. B-625、P-207：`aos-config-add` 有擋板時回 125；結束碼撤掉 3（改到下一步納入 git）。
7. B-606：名稱綁 UID 只在本次 daemon 存續期內有效，不存檔。
8. daemon「時間」、B-610、B-607（裁-2 落地）：`mount_diag_ttl_ticks` 數上層那筆登記的 `tick_seq`，是「時長一律數 `seq`」的唯一例外；pause 存檔間隔與事項批次寫出仍用毫秒（daemon 沒有上層的格可數）。runner 的 `--timeout-ms` 照第二十批疑-11 仍是毫秒。
9. B-623（裁-1 落地）：只有 `aos-mq get` 取佇列是 node 內的約定，daemon 分不出是哪一項在取。沒有通道時 `aos-mq` 回 0。
10. B-624：`aos-mq post` 送不了的（`forbidden`、`not_registered` 等）直接移除不重試；鬧鐘撤；佇列只收請求物件，**回應怎麼回還沒定**（原本回應走檔案投件，現在 aos 不管檔案投件）。`.aos/mq/post/` 的格式暫定，schema 未補。
11. B-614：通道送件仍拿收件方 `requests/` 的寫權當授權判準，但 `requests/` 已不歸 aos 管。
12. B-629：範本沒有另列「檔案收件程式」，只在使用者任務那一列註明檔案收送也是普通任務。kernel、agent 範本（P-814、P-715）與範本範例還沒改（`validate.py` 過渡期兩種項數都收）。
13. B-605、T-09：逃生口本輪照第二十批疑-13 暫定撤；但納入 cgroup 輪的裁定疑-7 已改成「准、不管」，下一輪要對齊。
14. B-630（下一步納入草稿，本輪沒動設計）：第 4 步「刪已提交的收件原件」與「取代本輪由收件任務照 `last.json` 刪」，跟「檔案收件 aos 不管」對不上；納入 git 那輪要對齊。

### 基礎條文依賴 kernel／agent 規則（已在上面「使用例」標出，留待其他篇放進來時再定）

15. B-601、B-607：事項怎麼處理、`issue_id` 沿用規則依賴 S-405；事項檔格式依賴 P-601。
16. B-603、B-604（排空停）、B-613、B-624：被收尾或結果不明的工作怎麼判讀，依賴 S-401 的 unknown 規則。
17. B-504、B-604（停用與退役）、B-606（別每格重登）：補查、成員登記依賴 S-202、P-802；條文已標「使用例：kernel 那側」。
18. B-614：急件越過上層排程任務的 `max_active_members`（S-202）。
19. B-605：沒有 quota 時磁碟用量由磁碟資源任務量（S-203）。

### 已在這輪修掉的舊疑點

舊第 11、12（git 殘句）→ B-607、P-207 改寫；13、14、15（cgroup 沒標下一步）→ P-208、B-303、B-611 已標；16 → B-626 改成 B-601、B-603～605、B-609；17～25（行為只寫在協議篇）→ 已搬回 B-601、B-603、B-606、B-620、B-633，協議篇只留連結；26 → P-101 寫明九種不含 `spawn_as`；27 → P-119 改寫。舊第 1 題的 A-102 依賴改成 B-625 為通用正本、A-102 只管領域驗證。
