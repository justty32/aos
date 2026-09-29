# 通用 tick：註冊任務與 git 提交

← [規格入口](README.md)｜[daemon](daemon.md)｜[kernel 樹](scheduling/README.md)｜[agent 任務](agent/README.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)第三～七批。所有 node 共用這套引擎。下文指 node 內的任務註冊表；與 daemon 登記表的區別見[名詞](terms.md)。

## B-602：同一 node 一次一格

〔使用者方向 2026-09-29〕loop 只做「跑一次 inst」，inst 跑 `aos-tick`。daemon 不同時開同一 node 的兩格 tick；舊 tick 及其後代清乾淨才開下一格。程序收尾見 [base/execution](base/execution.md)，重啟見 [B-603](daemon.md)。

〔建議預設，未拍板〕`aos-tick` 在可取得 node 獨占鎖後才執行，全格自己持鎖，直接呼叫也須遵守。鎖放在不受 git 還原或一般清理替換的位置。其他人、agent、工具要改受這格管理的檔案，也須協調這把鎖或先暫停 tick；否則它們的改動可能一起被 commit 或還原。這是所有寫入者共用的規則，不另外禁止工具改檔。

（09-29 重寫：已刪 claim／generation／checkpoint revision／提案交易；互斥由本條接手。）

## 任務註冊表

〔使用者方向 2026-09-29〕`aos-tick` 依序跑**系統性任務 → kernel／agent 任務 → 自訂任務**。有 UID 隔離時，系統性任務沿用控制側專用的非 root 服務身分；沒有 helper 時，依最新裁定整棵樹都用通用 user。固定特權步驟只在 [root helper](base/identity-resources.md)。任務類別不授予身分或權限，身分須受 inst 與 daemon 的身分額度約束，不能在表裡填個 UID 就借權限。

〔建議預設，未拍板〕最小格式是一個 JSON 陣列；陣列位置就是順序，不再加另一個排序欄。每項只有下列資料，欄位拼法留待協議篇落實：

| 欄位 | 意思 |
|---|---|
| `id` | 本表內唯一的任務名 |
| `argv` | 非空字串陣列：普通程式及參數 |
| `kind` | `system`、`kernel`／`agent`、`custom`；依上述類別順序排列 |
| `group`（可省） | 要一起提交的一組；省略就是單任務一組 |
| `needs`（可省） | 需先成功的任務 ID 陣列；省略就是沒有前置 |

例如一份含 agent 任務的 node 表的片段（程式名稱只作示意）：

```json
[
  {"id":"receive", "argv":["receive-input"], "kind":"agent", "group":"prepare"},
  {"id":"prepare", "argv":["prepare-request"], "kind":"agent", "group":"prepare", "needs":["receive"]},
  {"id":"send", "argv":["send-request"], "kind":"agent", "needs":["prepare"]},
  {"id":"clean", "argv":["aos-clean"], "kind":"custom"}
]
```

〔使用者方向 2026-09-29〕資源 module 也是 node 任務表上的普通項目；啟用與父層限制政策見 [scheduling/admission](scheduling/admission.md)。`aos-clean`、收信程式也用同一張表，不再分 pre／post 掛勾；有權限者同樣能直接跑這些程式。

## group 與 needs

〔使用者方向 2026-09-29〕組內全成功才一起生效，任一失敗就還原這組的 git 管理範圍；`needs` 的前置成功才執行。前面已提交的組不因後面失敗而撤回。

〔建議預設，未拍板〕採最小的順序語意：

- 同組項目連續，每項只屬一組。`needs` 只能指向本表前面的任務；重名、缺依賴、循環、非連續 group 或類別順序錯誤，整表拒絕載入，任務一項也不跑。
- 同組可依賴前項本次執行成功；跨組則須等前項所在組提交成功。任務預設以正常退出且碼為 0 表示本步成功，不代表整件產品任務完成。
- 組內有失敗或因前置不成立而跳過，該組不提交，餘下項目跳過並還原。該組先前暫時成功的任務，也不能供後續組當成有效前置。
- 後面的獨立組可以繼續，依賴失敗組的組跳過。依賴只管本格，不沿用上格的成功旗標，也不另做跨格任務排程器。

## git 提交與還原

〔使用者方向 2026-09-29〕每個 node 資料夾是一個 git repo。一格開始前，受管理的工作區回到最近一次 commit；每組成功便 commit 它的變動，失敗便還原到該組開始時的 commit。外部收件與不想管理的內容放 `.gitignore`。不用帳本或 SQLite，也不另存一套提交提案與收據。

〔建議預設，未拍板〕第一格前先有初始 commit。每組開始固定這組的管理範圍；還原包含修改、刪除、已暫存及尚未 `add` 的本組新增檔，卻不能清掉 ignored 收件與工作資料夾。不能只還原既有追蹤檔，也不能讓失敗任務臨時改 `.gitignore` 就逃出還原範圍。

〔建議預設，未拍板〕commit 或還原失敗時停止這個 node 的後續任務與新一格，保留既有 commit 並報出原因，修復後才恢復；不把未提交工作當成功。錯誤摘要走[待處理事項](scheduling/operations.md)，不能只寫在即將還原的檔案裡。

〔建議預設，未拍板〕這裡的「原子」只指**同一 repo 的已提交版本與恢復基線**，不保證執行期間多個工作檔同時變動。需要一致狀態的查詢或正式輸出讀同一 commit。ignored 檔、另一個 repo、外部 workspace 與 API／寄信等不可逆後果不會跟著還原。

## 收件：commit 後才刪原件（Q1）

〔使用者方向 2026-09-29〕訊息及工具／LLM 結果先落在 ignored 收件區。吃訊息是邏輯搬移：**先複製到追蹤區，與這組的狀態一起 commit 成功後，才刪收件原件**。失敗或 commit 前當機，原件仍在，下格可重收；commit 後、刪原件前當機，已提交的同 ID 檔就是消費證據，恢復時只清多留的原件，不重吃。

請求 ID、同 ID 衝突及保留期內的去重見 [base/transport](base/transport.md)，完整檔案發布與儲存位置見 [base/storage](base/storage.md)。

## 派出：先 commit 請求，再送出（Q2）

〔使用者方向 2026-09-29〕任務要用 LLM 或工具，先產生帶固定 ID 的最小請求檔，**提交成功才對外送出，下一格收結果**。tick 不在原地等遠端工作結束。上例 `prepare` 組先提交請求，後面的 `send` 才交接；送出失敗不會抹掉已提交的請求。

〔建議預設，未拍板〕請求的最少資料沿 [共用契約](contracts.md)，不另做通用 outbox。本地 commit 不能證明外部有沒有執行；送出中斷、組失敗或重啟後，能確認仍在途就等結果，**無可信結果且不能確認仍在途或從未送出／執行，就記 unknown，不自動補送**。即使實際當機在 commit 後、送出前，也不能憑猜測重做。接收方的同 ID 去重不等於外部只執行一次；unknown 處置見 [S-401](scheduling/operations.md)。

## 當機恢復、設定與清理

〔使用者方向 2026-09-29〕daemon／VM 重啟先按 [B-603](daemon.md) 清空舊程序。各 node 下一格在鎖內還原未 commit 的變動，已提交組與完整結果檔保留；收件重複按 Q1 處理，未明的工具／LLM 請求按 Q2 處理。能恢復本地 tick 不等於能重做 unknown 外部工作。

設定與註冊表的讀定、重要設定暫停手改、普通設定匯入，以 [A-102](agent/configuration.md) 為正本。恢復 tick 前須完成該流程，不能把合法手改當作未提交任務還原。

〔使用者方向 2026-09-29〕**別濫用 git**：沒變動不 commit；實作可定期合併提交，也可用 git submodule 分開高頻與不常變動的部分。清理與 git 歷史空間的邊界見 [B-404](base/storage.md)。

〔建議預設，未拍板〕沒變動的成功組視為完成，不製造空 commit。合併提交的維護須與 tick 互斥，保留可恢復的目前版本及仍需的請求證據；不能為省 commit 把「先提交再送出」延到送出之後。使用 submodule 時各 repo 有自己的提交邊界，父 repo 的 commit 不代表子 repo 工作區也已提交／還原，不承諾跨 repo 的 group 原子性。

## 驗收與尚未定案

group、Q1／Q2、還原範圍、設定與空 commit 的故障驗收，統一見 [V-03](conformance.md)。

註冊表欄位拼法、順序式 group／needs 的工程細節仍是建議預設；Q1～Q4 已裁定，不再列待裁。有 UID 隔離時，系統任務的非 root 服務身分如何透過可信登記接到共用表與 runner，仍須配合身分篇；不能由 `kind` 自動提權，也不能默默全改成 node 的 UID。
