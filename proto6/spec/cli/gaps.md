# 人手打的操作 CLI：舊缺口

← [CLI 入口](README.md)｜[規格入口](../README.md)

## H-034．舊缺口怎麼解、還有什麼留待後續〔主編補〕

| 舊編號 | 解法 |
|---|---|
| D1 登記／tick 證據 | P-106／115 已有 node.ls/show、boot_id、last_tick、掛載行程診斷。 |
| D2 成員／範本 | P-701～715 定 agent 設定／工具；P-801～814 定成員、同步、範本。 |
| D3 回話／context | P-703／708／713／714 定本地 input_id、reply、history、context；回話統一 agent.say＋in_reply_to。 |
| D4 驗證／待辦／清理 | P-210／712／805／609 定驗證／recheck；P-716／814 定清理遍歷。 |
| D5 池狀態 | P-808～812 定路由、共享窗口及 pool-status，pool usage 有實際落點。 |
| D6 停機／JSON | Ctrl-C、存檔重開見 [B-603](../settled/deferred/daemon/lifecycle.md)、[B-604](../settled/deferred/daemon/lifecycle.md)；〔第十八批〕排空或立即停由 daemon 設定 `stop_mode` 決定，仍沒有 stop IPC 或子命令。JSON 沿原 schema。 |

unknown 處置與自訂清理接口已裁定不做；git 歷史回收延後（第十八批 14，[P-008](../protocol/README.md#p-008)）。

| 剩餘缺口 | 為什麼現在不補 |
|---|---|
| 執行期驗收 | 實作後依 [驗收入口](../conformance.md)測權限、中斷、真實 provider。 |
| agent 內部機制（請求被拒收、卡在 unknown 的輸入、agent 之間問答、設定檢查結束碼） | 第十八批延後，見 [P-008](../protocol/README.md#p-008)。 |
