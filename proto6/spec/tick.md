# 通用 tick：註冊任務與 git 提交

← [規格入口](README.md)｜[daemon](daemon.md)｜[kernel 樹](scheduling/README.md)｜[agent 任務](agent/README.md)

依據：[09-29 新架構](../notes/2026-09-29-kernel-tree.md)、[使用者裁定](../notes/2026-09-29-verdicts.md)第三～十二批、[第十八批](../notes/verdicts/09-special-computing-os.md)。所有 node 共用這套引擎。下文指 node 內的任務註冊表；與 daemon 登記表的區別見[名詞](terms.md)。

〔使用者方向 2026-09-30，第十八批〕**tick 是一切的基底**，不跟 once、LLM 嘗試、agent 一輪這些計算單位共用外殼（[T-07](terms.md)）；哪些事算在基底裡見 [B-626](#b-626tick-是基底系統性任務的範圍)。

## B-602：同一 node 一次一格

〔使用者方向 2026-09-29〕loop 只做「跑一次 inst」，inst 跑 `aos-tick`。daemon 不同時開同一 node 的兩格 tick；舊 tick 及其後代清乾淨才開下一格。程序收尾見 [base/execution](base/execution.md)，重啟見 [B-603](daemon.md)。

〔建議預設，未拍板〕`aos-tick` 在可取得 node 獨占鎖後才執行，全格自己持鎖。鎖放在不受 git 還原或一般清理替換的位置。其他人、agent、工具要改受這格管理的檔案，也須協調這把鎖或先暫停 tick；否則它們的改動可能一起被 commit 或還原。這是所有寫入者共用的規則，不另外禁止工具改檔。〔使用者方向 2026-09-30，第十八批〕`aos-tick` 只在 daemon 開的本 node `tick` 框裡跑；人手直接呼叫、不在那個框就拒跑，要跑一格改經 daemon（[B-627](#b-627人手跑一格不在正確的框就拒跑)）。

## B-620：任務註冊表

〔使用者方向 2026-09-29〕`aos-tick` 依序跑**系統性任務 → kernel／agent 任務 → 自訂任務**。一格 tick 裡的所有任務（含系統性任務）都用該 node inst 的 `user` 跑，不另設服務帳號（第九批）；沒有 helper 時整棵樹都是通用 user。自己帳號做不到的事：要 root 的固定步驟交 helper（[B-609](daemon.md)），管成員的事（例如成員收件區權限）由上層 kernel 在自己的 tick 用自己的帳號做。固定特權步驟只在 [root helper](base/identity-resources.md)。任務類別不授予身分或權限。

〔使用者方向 2026-09-29〕註冊表只放 `.aos/tasks.json`，陣列位置就是順序；每項是一份 [inst](base/inst.md) 加排程欄位，**不准 `user`**（`$ref` 展開後也算，是 [C-07](contracts.md) 的永遠禁止鍵）。欄位、JSON 與 schema 以 [P-202](protocol/node.md) 為準，本節只定意思：

- **類別與順序**：`kind` 決定這項排在哪一段，同段內照陣列位置。〔使用者方向 2026-09-30，第十八批〕kernel 可以自訂任務種類（[T-06](terms.md)）；〔暫定〕自訂種類寫成「類別.名稱」（例如 `agent.review`），類別只能是 `kernel`、`agent`、`custom`，tick 只看點前的類別排順序，名稱的意思由定義它的 kernel 自己解釋。`system` 屬基底（B-626），不開放自訂。
- **`methods`**〔使用者方向 2026-09-29，第十七批〕：**node 接受哪些檔案請求由任務表決定**，每項用 `methods` 宣告自己處理哪些 method；同一 method 只能由一項任務宣告，兩項宣告同一個算任務表錯。method 的意思與 -32601 的條件見 [B-501](base/transport.md)。
- **沒人宣告的 method 由 tick 自己回**：tick 開格載入任務表後、跑第一組前，列一次 `requests/` 裡已發布的請求；method 沒有任何任務宣告的，tick 照 [B-501](base/transport.md) 回 -32601：原件複製進追蹤區當消費證據、錯誤回應放進待送區，以一個 commit 提交後照 [B-624](#b-624派出先-commit-請求再送出q2) 投出、照 [B-623](#b-623收件commit-後才刪原件q1) 清原件（路徑與提交訊息見 [P-202](protocol/node.md)、[P-205](protocol/node.md)）。有宣告的留給那項任務自己讀。沒有合法 ID 或回址的壞件照 B-623 只報一次。
- **一個 module 一項任務**：收件、產生請求及處理結果都在該項內做，投件與清收件原件交 tick，任務不另登記清收件工作。

表壞了（重名、缺依賴、循環、非連續 group、類別順序錯、methods 重複、inst 不合法）整表拒絕載入，任務一項也不跑，不退回舊表；tick 回 2，並在本 node 寫一件 `config_invalid` 事項指出 `.aos/tasks.json` 哪裡錯，同一問題沿用同一 `issue_id`（[S-405](scheduling/operations.md)）。任務表在開格時載入；各任務直接開檔讀自己的設定。

〔使用者方向 2026-09-29〕資源 module 也是 node 任務表上的普通項目；啟用與父層限制政策見 [scheduling/admission](scheduling/admission.md)。`aos-clean`、收信程式也用同一張表，不再分 pre／post 掛勾；有權限者同樣能直接跑這些程式。

## B-621：group 與 needs

〔使用者方向 2026-09-29〕組內全成功才一起生效，任一失敗就還原這組的 git 管理範圍；`needs` 的前置成功才執行。前面已提交的組不因後面失敗而撤回。

〔建議預設，未拍板〕採最小的順序語意：

- 同組項目連續，每項只屬一組。`needs` 只能指向本表前面的任務；重名、缺依賴、循環、非連續 group 或類別順序錯誤，整表拒絕載入，任務一項也不跑。
- 同組可依賴前項本次執行成功；跨組則須等前項所在組提交成功。任務預設以正常退出且碼為 0 表示本步成功，不代表整件產品任務完成。
- 組內有失敗或因前置不成立而跳過，該組不提交，餘下項目跳過並還原。該組先前暫時成功的任務，也不能供後續組當成有效前置。
- 後面的獨立組可以繼續，依賴失敗組的組跳過。依賴只管本格，不沿用上格的成功旗標，也不另做跨格任務排程器。

## B-622：git 提交與還原

〔使用者方向 2026-09-29〕每個 node 資料夾是一個 git repo。一格開始前，受管理的工作區回到最近一次 commit；每組成功便 commit 它的變動，失敗便還原到該組開始時的 commit。外部收件與不想管理的內容放 `.gitignore`。不用帳本或 SQLite，也不另存一套提交提案與收據。

〔使用者方向 2026-09-30，第十八批〕**落盤**：git 最低版本 2.36（啟動自檢見 [B-605](daemon.md)）。aos 自己的程式每次呼叫 git 都帶 `-c core.fsync=committed,reference`，不靠 repo 或使用者的 git 設定；這樣 commit 成功時物件與 ref 都已落盤，之後才刪收件原件（B-623）、才投件（B-624）。

〔建議預設，未拍板〕第一格前先有初始 commit。每組開始固定這組的管理範圍；還原包含修改、刪除、已暫存及尚未 `add` 的本組新增檔，卻不能清掉 ignored 收件與工作資料夾。任務改 `.gitignore` 不能逃出還原範圍。

〔建議預設，未拍板〕commit 或還原失敗時停止這個 node 的後續任務與新一格，保留既有 commit 並報出原因，修復後才恢復；不把未提交工作當成功。停格由 daemon 依 [B-607](daemon.md) 做，錯誤摘要走[待處理事項](scheduling/operations.md)，不能只寫在即將還原的檔案裡。擋板檔與結束碼見 [P-205](protocol/node.md)。

〔建議預設，未拍板〕這裡的「原子」只指**同一 repo 的已提交版本與恢復基線**，不保證執行期間多個工作檔同時變動。需要一致狀態的查詢或正式輸出讀同一 commit。ignored 檔、另一個 repo、外部 workspace 與 API／寄信等不可逆後果不會跟著還原。

## B-623：收件：commit 後才刪原件（Q1）

〔使用者方向 2026-09-29〕訊息及工具／LLM 結果落在 ignored `requests/`、`responses/`。任務先把原件逐 byte 複製到追蹤區，留下消費證據；**tick 在這組 commit 成功後才刪與已提交副本 bytes 相同的收件原件**。commit 前當機，原件仍在，下格可重收；commit 後當機，tick 依已提交證據補清原件，不重吃。原件跟已提交副本不同就報衝突並保留（[B-503](base/transport.md)）。組歸屬由 commit 邊界決定，不另寫 task／group 欄位。

〔使用者方向 2026-09-30，第十八批〕**壞掉的收件錯誤只報一次**：`requests/` 裡讀不懂、沒有合法 ID 或安全回址、因而回不了錯誤回應的件，發現的一方（tick 或宣告該 method 的任務）在本 node 寫一件事項；〔暫定〕`issue_id` 由檔名固定算出，`.aos/attention/` 的 open 或 done 已有同一 `issue_id` 就不再寫，所以同一個壞件不會每格重報。原件留在收件區不動，過了保留期由 `aos-clean` 刪（[B-404](base/storage.md)）。只算 `requests/`，`responses/` 與同 ID 異內容的衝突照各自規則。

請求 ID、同 ID 衝突及保留期內的去重見 [base/transport](base/transport.md)，完整檔案發布與儲存位置見 [base/storage](base/storage.md)，追蹤區路徑見 [P-206](protocol/node.md)。

## B-624：派出：先 commit 請求，再送出（Q2）

〔使用者方向 2026-09-29〕任務把帶固定 ID 的請求或回應放進追蹤的 `.aos/outbox/`，**tick 在所屬 group commit 成功後才投出**；失敗組的待送檔一起還原。LLM／工具結果留待後續 tick 收，不在原地等遠端工作結束。待送封套與鬧鐘紀錄的格式見 [P-206](protocol/node.md)。

每組 commit 成功後，tick 從該 commit 發布 `.aos/summary/published.json`、投出待送 message、照 B-623 刪收件原件；新格恢復後也補做發布與投件，只用已提交內容。投件成功後移除待送檔，刪除在下一組或格末一起提交；刪除本身就是變動，不造空 commit。提交前當機可再投相同 bytes，接收方依 [B-503](base/transport.md) 去重。

〔使用者方向 2026-09-29 晚，第十五批〕**投件只查一件事：目標是不是一個 node**（照 [inst 目標](base/inst.md#inst-目標檔案或資料夾)的找法：`target_node` 是資料夾，且有 `.aos/inst.json` 或 `inst.json`）。

- 不是 node，或投件時沒有寫入權限：tick 在 stderr 印一行（`target_not_node`／`target_not_writable`），這封不投、不重試、不改投別處，待送檔跟成功投件一樣移除（原檔仍在 git 歷史），不寫待辦。權限補上後要再送，由投件者重新產生待送檔。
- 送出遇到暫時性錯誤：留著待送檔，下格再投。
- 是 node 就投進去，之後 aos 都不管：對方有沒有裝任務、有沒有被 tick、多久才處理，都不過問。

〔使用者方向 2026-09-29 晚，第十五批〕**鬧鐘（可選）**：待送封套可帶 `alarm_ms`。投出成功後 tick 在 ignored 的 `.aos/alarms/` 記一筆；到期後本 node 的下一格去看，那封原件還在對方收件區就算沒被處理，在 stderr 印 `request_not_handled`；不寫待辦、不重投、不取消。原件已被取走就算處理了，不印。看完不管結果都刪掉這筆。aos 不為鬧鐘另外叫醒 node，要準時就讓這個 node 有定期 tick；沒設就完全不等、不逾時。〔使用者方向 2026-09-30，第十八批〕agent 範本對每個請求預設帶鬧鐘（[P-706](protocol/agent-tasks.md)）；被丟掉的件沒有鬧鐘、兩者對不上的問題延後（[P-008](protocol/README.md#p-008)）。

tick 可重投同 ID、同 bytes 的已提交封套，這只是補投同一封檔案，不授權重做不明的工具／LLM 執行。once 由 module 後續讀已提交材料，再向 daemon 登記及 wake，不往待送區塞 IPC。無可信結果且不能證明未執行的工作記 unknown，不自動再執行；見 [S-401](scheduling/operations.md)。

## B-625：當機恢復、設定與清理

〔使用者方向 2026-09-29〕daemon／VM 重啟先按 [B-603](daemon.md) 清空舊程序。各 node 下一格在鎖內還原未 commit 的變動，已提交組與完整結果檔保留；收件重複按 Q1 處理，未明的工具／LLM 請求按 Q2 處理。能恢復本地 tick 不等於能重做 unknown 外部工作。

設定修改、重要設定暫停手改、普通設定匯入，以 [A-102](agent/configuration.md) 為正本。恢復 tick 前須完成該流程，不能把合法手改當作未提交任務還原。

〔使用者方向 2026-09-29〕**別濫用 git**：沒變動不 commit；實作可定期合併提交，也可用 git submodule 分開高頻與不常變動的部分。清理見 [B-404](base/storage.md)。

〔建議預設，未拍板〕沒變動的成功組視為完成，不製造空 commit。合併提交的維護須與 tick 互斥，保留可恢復的目前版本及仍需的請求證據；不能為省 commit 把「先提交再送出」延到送出之後。使用 submodule 時各 repo 有自己的提交邊界，父 repo 的 commit 不代表子 repo 工作區也已提交／還原，不承諾跨 repo 的 group 原子性。

## B-626：tick 是基底：系統性任務的範圍

〔使用者方向 2026-09-30，第十八批〕tick 與它的系統性任務是一切的基底（[T-07](terms.md)）。算在基底裡的有三樣：

1. 任務表裡 `kind:system` 的任務；
2. tick 自己做的事：替沒人宣告的 method 回 -32601（B-620）、投件與鬧鐘（B-624）、刪收件原件（B-623）、發布摘要（B-624）、清 `task-*` 框（[B-202](base/execution.md)）；
3. `aos-clean`（[B-404](base/storage.md)）。〔暫定〕範本裡它維持 custom 類、排在最後；它算基底是看程式本身，不看任務表寫的 kind。

這些事的規則（互斥、提交、收尾、清框）以本篇、[B-202](base/execution.md) 與 [B-404](base/storage.md) 為正本。kernel、agent、custom 類（含自訂種類）的任務不算基底，歸其餘計算單位；它們的外殼、逾時與取消延後（[P-008](protocol/README.md#p-008)）。預設範本裡的 kernel 設定檢查從 `kind:system` 改成 kernel 類（[P-814](protocol/kernel-tasks.md)），所以範本本身沒有 system 類任務；`system` 留給以後真正屬於基底的任務。

**驗收：**範本任務表沒有 system 類任務也能正常跑；tick 自己回 -32601、投件、刪原件、清框，不需要任何任務宣告。

## B-627：人手跑一格：不在正確的框就拒跑

〔使用者方向 2026-09-30，第十八批〕`aos-tick` 開始時、取鎖和讀任務表之前，先看 `/proc/self/cgroup` 自己所在的 cgroup v2 路徑，結尾必須是本 node 的 `n-<h>/tick`（`<h>` 的算法見 [B-605](daemon.md)）。不是就在 stderr 印 `not_in_tick_cgroup: <node>`，回 **2**，什麼都不做。只限 `aos-tick`；`aos-clean`、`aos-attend` 等其他工具直接跑不受這條限制。

人手要「立刻跑一格」改經 daemon：送 `node.wake`，以 wake 回應的值為起點，再用 `node.show` 等格次前進；怎樣算新的一格已完成、`registration_id` 換了怎麼辦（舊登記已結束，要重新核對、不再等），以 [B-607](daemon.md) 為正本。不另開「跑一格並等結果」的 IPC。CLI 入口見 [H-004](cli/commands.md)。

**驗收：**在 daemon 框外直接跑 `aos-tick` 回 2，不取鎖、不改檔、不開任務；經 `node.wake` 跑的那一格照 B-607 判定為完成。

## 驗收與尚未定案

group、Q1／Q2、還原範圍、設定與空 commit 的故障驗收，統一見 [V-03](conformance.md)。

註冊表格式以協議篇為準；順序式 group／needs 是工程預設。
