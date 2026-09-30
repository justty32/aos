# 名詞與責任

← [規格入口](README.md)｜[共用契約](contracts.md)

## T-01．來源與適用範圍

〔主編補〕來源標記：〔使用者方向 YYYY-MM-DD〕表示已有裁定；〔建議預設，未拍板〕可替換；〔主編補〕只補編輯規則。每節標記涵蓋該節條件，遇不同來源另標。「必須／禁止」不表示未裁預設已獲批准。

依據是 [09-29 架構](../notes/2026-09-29-kernel-tree.md)及[裁定索引](../notes/verdicts/README.md)（至 09-30 [第十八批](../notes/verdicts/09-special-computing-os.md)），後續使用者裁定優先、同日後批蓋過前批。舊協議與改寫計畫不能反過來限制新規格。〔使用者方向 2026-09-30，第十八批〕行為規則以主規格為正本，協議篇只定格式，正本表見 [V-01](conformance.md)。

驗收：未裁定的工程預設標明來源；文件查核通過不能寫成運行時功能已完成。

## T-02．node 與角色

〔使用者方向 2026-09-29〕**node 是資料夾那個實體**，具有 inst、任務註冊表及自己的檔案；它的資料夾路徑就是 node id。以下兩者都是概念／角色，由任務註冊表裝了什麼決定：

- **kernel**：管理資源分配與任務排程的 node，**不以有沒有成員判定**。
- **agent**：會自主行動、基本上牽涉 LLM 的 node。

一個 node 可以同時是兩者，也可以都不是，例如只跑收信任務。頂層 node 不因此成為特殊種類；權限由設定授予。「上層 kernel」指註冊關係中負責管理的 node，不是檔案系統的上層目錄。樹與摘要邊界見 [scheduling](scheduling/README.md)。

**兩張註冊表不要混用：**[daemon](daemon.md)的表在記憶體使用，停機存入 `state.json`，記登記、pause 與未處理 wake；[tick](tick.md)的表在 node 裡，記順序執行的任務、group 與 needs。資源 module 是後者的普通項目，不另有外掛總表。

daemon 負責程序啟停，不判業務排程；可選 root helper 是 daemon 切出的固定特權步驟，見[身分篇](base/identity-resources.md)。每個 LLM 池就是一個 node，由它的代發任務負責實際請求，見 [LLM](scheduling/llm.md)。身分依 [inst](base/inst.md) 及[額度](base/identity-resources.md)，不由路徑或角色推定。

驗收：同一 node 裝排程及 LLM 自主任務，可以兼任 kernel／agent；空成員表不取消 kernel 角色，只有收信任務也不被強制當 agent。

## T-03．工作識別

〔建議預設，未拍板〕`node_id` 指上述路徑；`request_id` 辨識一次投件，`job_id` 辨識邏輯工作，`attempt_id` 辨識一次實際嘗試。重送同一次結果沿用 attempt ID，真的重新執行才換 ID。〔使用者方向 2026-09-29，第十六批〕attempt ID 由發起 node 自己配，不同 node 可能重複；存成工作目錄時名字要加發件者前綴，格式見 [P-402](protocol/work.md)。〔使用者方向 2026-09-30，第十八批〕更精確地說，attempt ID 由**配出它的 node** 配：一般是發起 node；LLM 池限流重試時由池配（P-402）。`run_id` 只在採用 [run](scheduling/runs.md) 分組時需要，不要求所有 node 都有一輪任務。

路徑識別 node，不代表 UID 或舊工作歸屬。〔使用者方向 2026-09-29〕node id 的唯一性不另防：同一資料夾經 symlink 有兩個路徑、同一路徑先後給不同 node、跨機器重名，都不在考慮範圍，風險由使用者自行承擔；不展開 symlink、不加世代號或跨機檢查。

## T-04．控制狀態與觀測狀態不混用

（09-29 重寫：已刪；結果定義併入 [C-03](contracts.md)，完成證據見 [agent](agent/README.md)，顯示見 [S-402](scheduling/operations.md)。）

## T-05．一萬份本體與少量活動

〔使用者方向 2026-09-28〕目標是 10,000 個扮演 agent 的 node、每小時活躍不到 100 個、雲端推論，見負載方向（已封存檔 2026-09-28-linux-resources-and-task-scheduling.md，索引見 [archive/README.md](../notes/archive/README.md)）。這不是固定併發上限。

〔建議預設，未拍板〕冷 node 保留檔案與登記，不各養常駐程序或空轉 tick；活動量依各 kernel 的資源 module，身分配置依[身分篇](base/identity-resources.md)。

驗收：增加冷 node 不增加逐 node 常駐程序或 history 讀取；啟動時重建樹的成本與平時少量活動成本分開量，見 [V-04](conformance.md)。

## T-06．可排程計算、多層多 kernel

〔使用者方向 2026-09-30，第十八批〕**aos 是給特殊計算用的 OS。** 一般 OS 分配資源的單位是 CPU 指令；aos 分配的單位是一次「計算」，例如一次 LLM 呼叫、agent 的一輪任務。計算必須符合規格，其中一條是能被 Linux 管制（啟動、限制、殺掉）；Linux 管不到的外部計算（例如量子計算）當外部函式庫來管。

- **多層、多個 kernel**：一般 OS 只有一個 kernel；aos 的 kernel 可以有很多個、疊很多層，每個都是 [T-02](#t-02node-與角色) 的 kernel 角色。
- **各 kernel 自訂抽象、資源與隔離**：抽象指任務種類（例如把某種 agent 任務設成需要排程的一種）；資源不限 CPU、記憶體；隔離也可以在不同地方不同。aos **正式開放** kernel 登記自己的任務種類與資源名稱，schema 的列舉跟著放寬；aos 本身只提供 [tick 基底](#t-07tick-是基底)、Linux 隔離（帳號、cgroup）與登記框架。現有寫死的 LLM 三檔、份額、窗口、重試與六類資源，都是「預設 kernel 範本」的規則，不是 aos 對所有 kernel 的要求。
- **上下層不必對齊**：上層只用自己認得的資源與規則管下層，管理要「潤物細無聲」，下層不必知道自己被怎麼管；上下層資源定義不同就不管。kernel 自己定義、Linux 管不到的隔離可以比上層寬；Linux 管的部分（cgroup、帳號）本來就是巢狀，子層只能在已分得範圍內再分。
- **管理目標：隨機性**：用愈多 LLM，隨機性愈高。排程的管理目標之一是隨機性愈低愈好，但要跟任務完成度、資源消耗一起權衡。怎麼量、怎麼權衡，延後（[P-008](protocol/README.md#p-008)）。

〔建議預設，未拍板〕自訂任務種類寫成 `<類別>.<名稱>`，類別只能是 `kernel`、`agent`、`custom`（例如 `agent.review`）；tick 只看類別決定順序（[B-620](tick.md)），名稱的意思由定義它的 kernel 在自己的設定裡解釋。`system` 屬基底，不開放自訂。資源名稱：現有六類（CPU、記憶體、pids、LLM、磁碟、網路）意思固定；其他名稱由定義它的 kernel 自己記帳與解釋，只有 CPU、記憶體、pids 由 aos 寫進 cgroup。

〔記錄者理解，不是使用者逐字裁定〕aos 本身只提供讓各 kernel 定義抽象／資源／隔離的框架，加上一個最小的「可排程計算」外殼（能被 Linux 啟動、限制、殺掉，結果交回檔案）。這個外殼（tick 以外的計算單位）怎麼定，延後（P-008）。

驗收：兩個 kernel 各自登記不同的任務種類與資源名稱，互不影響；上層不認得下層的自訂資源時不報錯、不代管。

## T-07．tick 是基底

〔使用者方向 2026-09-30，第十八批〕**tick 最特殊，是一切的基底**，不跟其他計算單位（once、LLM 嘗試、agent 一輪等）放進同一個外殼。算在基底裡的有三樣：

1. 任務表裡 `kind:system` 的任務；
2. tick 自己做的事：回 -32601、投件、刪收件原件、鬧鐘、發布摘要、清 `task-*` 框；
3. `aos-clean`。

kernel、agent、custom 類的任務不算基底，歸其餘計算單位，連同它們的逾時與取消一起延後（P-008）。預設範本裡的 kernel 設定檢查改成 kernel 類。行為正本見 [B-626](tick.md)。

## T-08．投件權就是執行權

〔使用者方向 2026-09-30，第十八批〕能投件給某 node，就等於能用它的身分跑任意程式；這件事**會傳遞**：A 能投給 K、K 能投給池，A 就等於也能用池的身分。隔離與 key 保護只對整條投件鏈以外的帳號成立。行為正本見 [B-501](base/transport.md)。

## T-09．收尾、排空停機、熱重載、逃生口

〔使用者方向 2026-09-30，第十八批〕幾個容易混的詞：

| 詞 | 意思 | 正本 |
|---|---|---|
| 收尾 | 對一個框送 SIGTERM，等 `shutdown_grace_ms`，再 `cgroup.kill`，確認全空。重啟、停機、解除登記、取消在跑的工作都用這一套 | [B-604](daemon.md) |
| 排空停機 | daemon 停收新工作，等在途的做完再停；可設上限時間 | [B-604](daemon.md) |
| 熱重載 | 不重開 daemon，重讀設定並套用能即時改的部分 | [B-608](daemon.md) |
| 逃生口 | node 在自己框下另開子框、刻意留住的常駐程序 | [B-605](daemon.md) |

「排空」只指停機；解除登記那套 TERM→寬限→kill 叫「收尾」。
