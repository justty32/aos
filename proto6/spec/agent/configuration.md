# 設定與生效時點

← [Agent](README.md)｜[身分與資源](../base/identity-resources.md)

## A-101 設定檔〔使用者方向 2026-09-29〕

設定就是 node 裡可按權限修改的檔案。人與有權限的 agent 使用同一套檔案及工具；具體權限依[兩條通則](../README.md)。

〔建議預設，未拍板〕設定保留模型、人格文字、工具清單、context 選擇規則、工作目錄及所需檔案引用。載入時驗證必需內容、引用及格式，錯誤指出檔案與欄位；不採用缺一半的設定。模型與工具清單可分檔，格式見 [P-701](../protocol/agent-tasks.md)。LLM 位址用 `llm.target_node`、工具位址用 `tools.target_node`；兩條路線、預設先實作哪一檔，以 [S-301](../scheduling/llm.md) 為準，工具那側見 [A-401](tools.md)。

〔使用者方向 2026-09-29〕執行身分依 [inst 的 `user`](../base/inst.md)，額度與可選 helper 依[身分與資源](../base/identity-resources.md)，不在 agent 設定另加一套授權。

## A-102 改設定與下一 tick 生效〔使用者方向 2026-09-29〕

改設定在 tick 外用 `aos-config-add`、`aos agent tools add` 等指令，持與 tick 相同的 node 鎖寫入並由標準配備的 git 提交；`--from` 可指定任意可讀路徑。重要設定仍先 pause、等正在跑的 tick 與後代清空再手改，確認提交後才 resume；暫停 run 不等於暫停 tick。

任務直接開檔讀設定。**tick 裡的任務不改 `config/` 是軟性原則，不檢查也不阻擋；同一格新舊設定混用的風險由寫任務的人承擔。** 正常在 tick 外提交的修改，下次 tick 就可讀到；已派工作沿用派出時固定的材料。

〔使用者方向 2026-09-30，第十九批；P-207 從協議篇搬上〕**`aos-config-add` 的鎖與提交流程**（argv 與結束碼見 [P-207](../protocol/node.md)）：它在 tick 外自己持鎖，取 tick 的同一把非阻塞鎖（[B-602](../tick.md)），node 是 dirty 或有擋板就拒絕；不能在同 node 的 tick 內呼叫，任務直接讀目前設定。JSON 草稿先驗基本格式，領域設定留到下一格依本條驗。寫法是在目標旁完整寫暫存檔 → fsync → rename 替換 → fsync 目錄，再只 stage 目標、提交，訊息 `aos-config-add <target>`，沒變動不提交；提交由標準配備的 git 做（[B-622](../tick.md)），失敗還原、commit 或還原故障依 B-622 擋新格。**沒有 git 時只做原子替換、不提交**（[B-632](../tick.md)）。重要設定（inst 的身分、任務表）不用這個工具：依下段，暫停、等程序全空、持鎖修改並驗證、提交後才 resume，保留已派工作所需的舊內容。

〔第十九批；P-210 從協議篇搬上，建立步驟也見 [H-036](../cli/walkthrough.md)〕**建立與恢復前驗證**：
- **建立**（`aos node new`）：範本只安裝普通任務，不寫角色旗標；先驗產物有效、有初始 commit（沒有 git 時略過，[B-632](../tick.md)），才報建好。建立本身不授身分、不登記、不叫醒；頂層額度仍要放進 daemon 設定的 roots，成員保存與同步沿 kernel 篇。kernel 與 agent 的範本內容見[協議篇](../protocol/kernel-tasks.md)。
- **恢復**（`aos node resume`）：daemon 已暫停且程序全空後，持同一把鎖依序檢查手改的內容：(1) 按 [inst 目標](../base/inst.md#inst-目標檔案或資料夾)選 inst，驗原始結構與身分宣告，daemon 在 resume 與開格時仍另驗可信額度，不以本地檢查代替授權；(2) 驗任務表的 schema，及重名、needs、group 連續、kind 順序（[B-620](../tick.md)）；(3) 有 kernel 預設任務就跑 kernel 設定檢查，有 agent 預設任務就用 [P-712](../protocol/agent-tasks.md) 的規則對**候選工作樹**驗 agent 設定、工具與引用，兩種都有便都驗；自訂普通程式沒有 aos 的領域設定契約，不因它沒提供 validator 就拒收合法任務表；(4) 任何檢查失敗保持暫停、保留手改、stderr 指出檔案與欄位，通過後才照 CLI 確認流程提交手改，再送 `node.resume`。
- 唯讀驗證由外層持鎖、不另取鎖，不寫追蹤或 ignored 檔、不發事項、不自行提交；它只證明設定可採用，不證明外部 endpoint 可達。

設定無效時報出檔案與欄位，停止依賴它的新工作並留[待處理事項](../scheduling/operations.md)。任務表錯誤依 [tick](../tick.md) 整格不跑，身分錯誤依 [inst](../base/inst.md) 拒絕啟動。〔第十九批〕任務可帶自己的 `user`（B-620），所以不再有「任務不准帶 user」這一項檢查。

驗收：匯入任意可讀檔案時與 tick 互斥，提交後下一格可讀；任務改設定不被攔截，已派出的工作材料不被更新覆蓋。

## A-103 人格與權限分界

（09-29 重寫：已刪／併入[兩條通則](../README.md)與[身分與資源](../base/identity-resources.md)。）
