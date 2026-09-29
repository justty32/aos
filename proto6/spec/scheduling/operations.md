# 查詢與待處理事項

← [node 樹與資源](README.md)｜[整體驗收](../conformance.md)

讀狀態、處理問題與改設定沿用[入口通則](../README.md)。

## S-401．結果不明就放著

〔使用者方向 2026-09-29〕結果不明的工作保持 unknown，沒人處理就隨定期清理清掉；不自動重做。

<a id="s-402查詢回應與拒絕理由建議預設未拍板09-29-精簡依冗餘審查-b2b4"></a>

## S-402．查詢回應與拒絕理由

〔使用者方向 2026-09-29〕查詢直接讀有權限的本地檔案或摘要，不為了查詢啟動 node 的 tick。跨層只取下層摘要；不能靠猜 ID 讀到無權存取的內容。一致查詢依 [儲存](../base/storage.md) 讀同一已提交版本，結果到期與清理也以該篇為準。

〔建議預設，未拍板〕顯示至少能分清排隊、等待資源、等結果、執行中、暫停、取消中、unknown 與需要人處理；拒絕執行要能看出原因。摘要附來源與觀測時間，預估等待時間不能當保證，也不能把顯示狀態當成成功證據。

資源 module 的啟用與不足處置依 [S-203](admission.md)；已啟用的要求無法滿足，才報部署不可用並停止相關新工作。身分額度不允許開 tick 等啟動錯誤也要看得到，並進 S-405 待處理事項。

驗收：不啟動 node 的 tick 也能分辨「還在排隊」與「結果不明」；父 kernel 看得到子 kernel 的阻擋摘要，讀不到未授權的成員內容。

## S-403．最小量測與過載

（09-29 重寫：已刪；必要容量與拒收邊界併入 [S-203](admission.md) 與[儲存](../base/storage.md)，具體量測留待實作驗證。）

## S-404．留存

（09-29 重寫：已刪／併入[儲存 B-404](../base/storage.md)；保留期與 `aos-clean` 只在該篇定義。）

<a id="s-405待處理資料夾使用者方向-2026-09-29"></a>

## S-405．待辦清單

〔使用者方向 2026-09-29〕attention 是 aos 自己不該或不能處理、交給人或 agent 手動處理的待辦清單。node 事項放自己的 `.aos/attention/`（ignore、不隨 group 還原）。runner 沒開始、tick 壞掉自動停格、程序清不乾淨，也由 daemon 寫到該 node；once 單檔沿用 `.err`。寫不進去就不管，daemon 在 stdout 警告一行。helper 不見、state 存不下等 daemon 自己的事，走 `daemon.attention.ls/show/done`；`state_dir/attention/` 供重開接續。

每件事項有白話 `message`，可附 `suggestion`（建議處理文字，可含建議指令，不會自動執行）；格式見 [ops](../protocol/ops.md)。`aos-attend` 只做三件事：

- `aos attend ls`：沿登記樹彙整 node 與 daemon 的待辦。
- `aos attend show N ID`：顯示出了什麼事與建議處理。
- `aos attend done N ID`：人或 agent 處理完後標完成；node 事項由 `.aos/attention/open/` 搬到 `done/`，daemon 事項走 `daemon.attention.done`。

驗收：兩個 node 同名事項不覆蓋，group 還原不碰事項；daemon 寫不進 node 只警告、不接管。show 只顯示文字，done 只標完成。
