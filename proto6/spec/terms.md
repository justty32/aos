# 名詞與責任

← [規格入口](README.md)｜[共用契約](contracts.md)

## T-01．來源與適用範圍

〔主編補〕來源標記：〔使用者方向 YYYY-MM-DD〕表示已有裁定；〔建議預設，未拍板〕可替換；〔主編補〕只補編輯規則。每節標記涵蓋該節條件，遇不同來源另標。「必須／禁止」不表示未裁預設已獲批准。

依據是 [09-29 架構](../notes/2026-09-29-kernel-tree.md)及[裁定紀錄](../notes/2026-09-29-verdicts.md)，後續使用者裁定優先、同日後批蓋過前批。舊協議與改寫計畫不能反過來限制新規格。

驗收：未裁定的工程預設標明來源；文件查核通過不能寫成運行時功能已完成。

## T-02．node 與角色

〔使用者方向 2026-09-29〕**node 是資料夾那個實體**，具有 inst、任務註冊表及自己的檔案；它的資料夾路徑就是 node id。以下兩者都是概念／角色，由任務註冊表裝了什麼決定：

- **kernel**：管理資源分配與任務排程的 node，**不以有沒有成員判定**。
- **agent**：會自主行動、基本上牽涉 LLM 的 node。

一個 node 可以同時是兩者，也可以都不是，例如只跑收信任務。頂層 node 不因此成為特殊種類；權限由設定授予。「上層 kernel」指註冊關係中負責管理的 node，不是檔案系統的上層目錄。樹與摘要邊界見 [scheduling](scheduling/README.md)。

**兩張註冊表不要混用：**[daemon](daemon.md)的表只在記憶體，記 node 登記、啟動及喚醒所需資料；[tick](tick.md)的表在 node 裡，記順序執行的任務、group 與 needs。資源 module 是後者的普通項目，不另有外掛總表。

daemon 負責程序啟停，不判業務排程；可選 root helper 是 daemon 切出的固定特權步驟，見[身分篇](base/identity-resources.md)。每個 LLM 池的代發服務負責實際請求，見 [LLM](scheduling/llm.md)。身分依 [inst](base/inst.md) 及[額度](base/identity-resources.md)，不由路徑或角色推定。

驗收：同一 node 裝排程及 LLM 自主任務，可以兼任 kernel／agent；空成員表不取消 kernel 角色，只有收信任務也不被強制當 agent。

## T-03．工作識別

〔建議預設，未拍板〕`node_id` 指上述路徑；`request_id` 辨識一次投件，`job_id` 辨識邏輯工作，`attempt_id` 辨識一次實際嘗試。重送同一次結果沿用 attempt ID，真的重新執行才換 ID。`run_id` 只在採用 [run](scheduling/runs.md) 分組時需要，不要求所有 node 都有一輪任務。

路徑識別 node，不代表 UID 或舊工作歸屬。〔使用者方向 2026-09-29〕node id 的唯一性不另防：同一資料夾經 symlink 有兩個路徑、同一路徑先後給不同 node、跨機器重名，都不在考慮範圍，風險由使用者自行承擔；不展開 symlink、不加世代號或跨機檢查。

## T-04．控制狀態與觀測 phase 不混用

（09-29 重寫：已刪；結果定義併入 [C-03](contracts.md)，完成證據見 [agent](agent/README.md)，顯示見 [S-402](scheduling/operations.md)。）

## T-05．一萬份本體與少量活動

〔使用者方向 2026-09-28〕目標是 10,000 個扮演 agent 的 node、每小時活躍不到 100 個、雲端推論，見[負載方向](../notes/2026-09-28-linux-resources-and-task-scheduling.md)。這不是固定併發上限。

〔建議預設，未拍板〕冷 node 保留檔案與登記，不各養常駐程序或空轉 tick；活動量依各 kernel 的資源 module，身分配置依[身分篇](base/identity-resources.md)。

驗收：增加冷 node 不增加逐 node 常駐程序或 history 讀取；啟動時重建樹的成本與平時少量活動成本分開量，見 [V-04](conformance.md)。
