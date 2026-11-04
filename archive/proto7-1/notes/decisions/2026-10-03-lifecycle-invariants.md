# 生命週期三個不變條件（頂層 10-03 決定，回應 astra-8 總評）

使用者 10-03 授權頂層自走、「之後再說」的項目也由頂層取最簡。這份是頂層代做的設計決定，使用者回來可推翻。來源：[astra-8 報告](../play/2026-10-03-astra-8-infra.md) 第四、五節。

astra-8 總評：剩下的不是邊角，是「用檔案有／沒有推定事實」的結構性缺口。頂層決定（使用者授權自走、取最簡）：不要再逐窗口加檢查，改成下面三個**不變條件**＋一條**判定原則**，然後用固定中斷矩陣驗。

## 判定原則：三態
凡是 daemon／tick／tock 要「推定一個事實」（回合關了沒、任務活著沒、程序是不是同一個），結果一律三態：**是／否／不知道**。「不知道」（讀不到、EIO、starttime 讀不到、檔案半寫）**不得當成「否」**，也不得當成「是」去做破壞性動作；它的處理是：保留現狀、記 last_error（或 status 欄位）、下一圈再看。

## 不變條件一：回合（K-01、K-02）
- 舊回合「確知已關」才開下一回合。round.json 讀不到＝不知道＝停在 error 退避重試，不 tick。
- 恢復成功（補 tock 關回合）後，**回到迴圈頂端**重新判斷 pause／rounds 倒數，不直接往下 tick。
- status 對每個 node 明示 `round_open`（true／false／null＝不知道）與 `recovery_pending`。

## 不變條件二：任務啟動交接（K-03、K-04、K-05、K-06）
權威是**合作式身分掃描**：環境變數 `AOS7_NODE`＋`AOS7_TID` 相符的活程序（Q1 已用、stop-sweep 已用）。
- tock 要把一個沒有 exit.json 的任務判成 lost／死之前（不論是 runner 死、pid.json 沒寫、birth 太久沒動靜），**先做一次身分掃描**：
  - 找到相符的活程序 → 先 kill（照 Q1 範圍）再判 lost。這樣 keep 重起時不會雙開（K-04）。
  - 沒找到、且 runner 也確知已死 → lost。
  - 「只有 birth、沒有 runner.json」超過 2 個回合，掃描也沒有相符程序 → lost（K-03，tick 與 runner 都死）。
- starttime 讀不到＝不知道 → 當活（保守），記原因；不得當成 PID 重用（K-05）。
- **搬移（K-06）頂層定範圍，不再追窗口**：node 在任務啟動途中或執行中被搬走，照 Q4 處理＝舊任務一律收掉、新位置由 keep 重起；被收掉的任務在死前經字串路徑寫出的「鬼目錄」是**已接受的界線**，寫進 spec。只要求：aos7-run 在 exec 前最後一次確認 node 身分，不符就不起；以及 daemon 的 node-gone 收尾能收掉這種任務（身分掃描）。不要再加更晚的 stat。

## 不變條件三：清歷史不改上層的累計（K-07）
- kernel 的用量加總改成在 kernel-state 裡記每個 tid 的「已見最大用量」，任務資料夾被 purge 後用記住的值；累計只增不減。
- spec §9 寫明：開 `keep_old_rounds` 時，依賴歷史的上層（kernel 用量、agent 接前任 state）只保證接到「最近 N 回合內」的前任；kernel 用量靠 kernel-state 自己記。

## 其他
- K-08：owner.json 分成 `owner`（權限：node、tid、allow_stop，歷史沿用）與 `daemon`（`pid`、`since`，現役 daemon 每次拿到鎖都更新）。人手重開沿用 owner 權限、更新 daemon。
- K-09：disk 計算移到 daemon 內的背景 thread（daemon 內管迴圈本來就用 thread，S-04 管的是「動作」），主迴圈只讀結果；計算本身每 30 秒、有時間上限。
- K-10：文件改成「自動在後續掃描發現，低負載約一個主迴圈週期（~20 ms），重負載更久」。
