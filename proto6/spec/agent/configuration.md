# 設定與生效時點

← [Agent](README.md)｜[身分與資源](../base/identity-resources.md)

## A-101 設定檔〔使用者方向 2026-09-29〕

設定就是 node 裡可按權限修改的檔案。人與有權限的 agent 使用同一套檔案及工具；具體權限依[兩條通則](../README.md)。

〔建議預設，未拍板〕設定保留模型、人格文字、工具清單、context 選擇規則、工作目錄及所需檔案引用。載入時驗證必需內容、引用及格式，錯誤指出檔案與欄位；不採用缺一半的設定。模型與工具清單可分檔，格式見[協議 node](../protocol/node.md)。LLM 位址用 `llm.target_node`；工具位址用 `tools.target_node`，兩條路線見[LLM](../scheduling/llm.md)及[工具](tools.md)。

〔使用者方向 2026-09-29〕執行身分依 [inst 的 `user`](../base/inst.md)，額度與可選 helper 依[身分與資源](../base/identity-resources.md)，不在 agent 設定另加一套授權。

## A-102 改設定與下一 tick 生效〔使用者方向 2026-09-29〕

改設定在 tick 外用 `aos-config-add`、`aos agent tools add` 等指令，持與 tick 相同的 node 鎖寫入並 commit；`--from` 可指定任意可讀路徑。重要設定仍先 pause、等正在跑的 tick 與後代清空再手改，確認提交後才 resume；暫停 run 不等於暫停 tick。

任務直接開檔讀設定。**tick 裡的任務不改 `config/` 是軟性原則，不檢查也不阻擋；同一格新舊設定混用的風險由寫任務的人承擔。** 正常在 tick 外提交的修改，下次 tick 就可讀到；已派工作沿用派出時固定的材料。

設定無效時報出檔案與欄位，停止依賴它的新工作並留[待處理事項](../scheduling/operations.md)。任務表錯誤依 [tick](../tick.md) 整格不跑，身分錯誤依 [inst](../base/inst.md) 拒絕啟動。

驗收：匯入任意可讀檔案時與 tick 互斥，提交後下一格可讀；任務改設定不被攔截，已派出的工作材料不被更新覆蓋。

## A-103 人格與權限分界

（09-29 重寫：已刪／併入[兩條通則](../README.md)與[身分與資源](../base/identity-resources.md)。）
