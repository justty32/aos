# 增量排程與執行准入

← [排程](README.md)

以下均為〔建議預設，未拍板〕；冷agent與工具共享資源的方向見[使用者紀錄](../../notes/2026-09-28-linux-resources-and-task-scheduling.md)。責任為排程寫入者，執行前資源強制由基底完成。

## S-201．ready／due 的權威與讀取

每agent的排程摘要含 `ready:bool=false`、`next_due_at_ms:int|null=null`、`ready_since_at_ms:int|null=null`、`pending_seq:int>=0=0`、`served_seq:int>=0=0`。請求／結果／到期事件更新對應摘要，不載入其他agent history。SQLite索引至少支援ready選取及非空next_due按時間排序；每輪先搬到期列，再claim有限批次，預設最多64列，可配置正整數。

pending_seq／served_seq只表示排程事件已出現／已被投影，不是agent輸入消費cursor。事件交易增加pending_seq並重算ready：當前run有可消費結果、可推進continuation或due才ready；只有後續queued run的新訊息而當前run仍等待既有工作時，不使當前run ready。無當前run才檢查FIFO隊首；隊首paused則不ready、不跳過它，否則投影ready。重算後served_seq更新至該交易已看見的事件序號；語意消費仍由C-05另記。

claim與提案提交也在交易內重算這個投影，不以tick看到的舊ready值覆蓋新事件。當前run終局時同交易檢查FIFO下一run並設ready。無新事件、到期維護或待核對條件的冷agent不排定期tick。

驗收：Given tick即將轉idle時新輸入到達，When 兩筆交易任一順序提交，Then 重算後新run仍ready；不遺失喚醒、不平行雙寫。Given R1長等工具而R2入站，When 事件已投影，Then R2保留queued但不反覆開R1空tick；R1終局同交易才使R2 ready。

## S-202．通知與補查

通知只提示有事；持久入口及B層交接狀態才是證據。正常熱路徑只碰被通知的owner及due列。未知直寫檔案不視為已接納；使用正式入口取得收據才享有接納承諾。若相容匯入目錄，需持久游標分批導入，每圈至多64項，重送按request_id去重。

啟動、門鈴溢出或交接不一致觸發分批reconcile；正常低頻核對預設60秒一次、每批64owner，不喚醒agent只核對入口與索引。完整巡回時長要可查，不承諾每60秒掃完所有人。重啟允許全量恢復但分批讓新工作穿插，不每20ms掃一萬個家。

驗收：Given 持久接件後通知丟失，When 門鈴沒有到達但補查推進到該owner，Then 工作仍被導入ready；量測顯示無逐agent程序啟動，正常輪詢未全量解碼history。

## S-203．全局與每agent名額

部署必填正整數 `max_tick_inflight`、`max_tool_inflight`、`max_llm_inflight`、`max_pending_jobs`、`per_agent_inflight`；不由一小時活躍數推導預設併發。首版需配置才enabled，缺值拒絕啟動新工作。tick每agent仍最多1；工具與LLM另受每agent合計上限，不讓等待HTTP占住tick槽。

排程以單一帳本交易查全部適用上限，足夠才建立reserved attempt與占票；不可先占一種名額再等另一種。基底報確定啟動失敗／清空受管範圍後釋放本機票；unknown而程序未清空仍占票，標診斷原因。全局父cgroup保護整機，每agent上限只限制自己的合計，不能取代全局准入。

驗收：Given 上限為2且五個工具ready，When 派送並有一個啟動失敗，Then 最多2個占票，失敗票可回收再派第三個；unknown存活工作不被當成免費名額。

## S-204．可預測的簡單公平

首版priority只有控制政策設定的整數，0為一般，1為互動；其他值拒絕。每次可用機會先選等待超過60秒的可入場job（較早進入ready者優先，先後以ready序號判定），否則優先1再0；同級按agent輪流，一agent每輪最多取一件，再按job的`seq`排序。〔使用者方向 2026-09-29〕**先後一律以控制帳本配發的持久遞增序號判定，不用牆鐘**：`seq`在建立job時配發，`ready_seq`在每次進入ready時配發，兩者都只增不減、重啟不重置；`created_at_ms`等牆鐘時間只供顯示與查詢。等待是否超過60秒以經過時間判定（[C-01](../contracts.md)），牆鐘跳動不改變排隊順序（WSL 見[平台](../README.md#平台原生-linux-與-wsl)）。等額度完全不足的job跳過但保留等待年齡，不能堵住獨立可用scope。

名額調小不主動殺已有工作；等在途回落才再派。擴大也須受父cgroup限制。使用者可取消或管理者強制停工，但不把自動調整與取消混在一起。高階成本最優、跨機排程與分散式lease延後。

驗收：Given 互動job持續湧入且背景job已等60秒、二者都可入場，When 出現下一個機會，Then 背景job可按最老順序獲派；若其scope無額度則顯示quota_wait而非假裝已滿足公平。
