# 名詞與責任

← [規格入口](README.md)｜[共用契約](contracts.md)

## T-01．來源與適用範圍

〔主編補〕來源標記：〔使用者方向 YYYY-MM-DD〕表示已有裁定；〔建議預設，未拍板〕可替換；〔主編補〕只補編輯規則。每節標記涵蓋該節條件，遇不同來源另標。「必須／禁止」不表示未裁預設已獲批准。

依據是 [09-29 架構](../notes/2026-09-29-kernel-tree.md)及[裁定索引](../notes/verdicts/README.md)（至 09-30 [第二十批](../notes/verdicts/11-tick-as-unit.md)），後續使用者裁定優先、同日後批蓋過前批（第二十批與第十九、十八批衝突時以第二十批為準）。舊協議與改寫計畫不能反過來限制新規格。〔使用者方向 2026-09-30，第十八批〕行為規則以主規格為正本，協議篇只定格式，正本表見 [V-01](conformance.md)。

〔使用者方向 2026-09-30，第二十批〕**保證跟著「掛了什麼」走**：tick 核心的三件事（[T-07](settled/terms.md#t-07tick-核心)）不靠任何系統級任務也成立；其餘保證來自任務表上掛的[系統級任務](settled/terms.md#t-10tick-核心系統級任務普通程式與其他任務)、任務包的普通程式與 daemon。例如 tick 本身不保證整格原子；掛了 `aos-git` 三項而且 git 能用，也只保證 aos 自己的東西（`.aos/`、任務表、系統級任務動到的檔）是原子的（[B-630](settled/tick/git.md)）。第十九批的「保證以標準配備全掛為前提」與「完整級／備援級兩級保證」都撤了。

〔使用者方向 2026-09-30，納入 cgroup 與 git〕**git 與 cgroup 是「有就用」**：現行規則在兩者都沒有時也要成立；有的時候多出的保證寫在各條（git：[B-630、B-622](settled/tick/git.md)；cgroup：[B-605](settled/deferred/daemon/cgroup.md)、[B-634](settled/tick/cg.md)）。

〔建議預設，未拍板〕各條的保證寫成「掛了哪一項系統級任務、包了哪個普通程式、daemon 有沒有 cgroup 時成立什麼」；沒掛的後果不逐條寫。

驗收：未裁定的工程預設標明來源；文件查核通過不能寫成運行時功能已完成。

## T-02．node 與角色

〔使用者方向 2026-09-29〕**node 是資料夾那個實體**，具有 inst、任務註冊表及自己的檔案；它的資料夾路徑就是 node id。以下兩者都是概念／角色，由任務註冊表裝了什麼決定：

- **kernel**：管理資源分配與任務排程的 node，**不以有沒有成員判定**。
- **agent**：會自主行動、基本上牽涉 LLM 的 node。

一個 node 可以同時是兩者，也可以都不是，例如只跑收信任務。頂層 node 不因此成為特殊種類；權限由設定授予。〔使用者方向 2026-09-30，第十九批〕「上層」（含上層 kernel）**預設看資料夾包含**：最近一個包含本資料夾、也有 tick 的資料夾；在 daemon 底下可以另外登記覆蓋，覆蓋要新舊兩個上層都同意（〔第十九批疑點裁定 11〕舊上層沒在 daemon 登記時只要新上層同意），覆蓋只改管理關係，管轄權仍跟著資料夾（[T-10](settled/terms.md#t-10tick-核心系統級任務普通程式與其他任務)，判定規則以 [B-628](settled/tick.md) 為正本）。樹與摘要邊界見 [scheduling](scheduling/README.md)。

**兩張註冊表不要混用：**[daemon](settled/daemon/README.md)的表在記憶體使用，停機存入 `state.json`，記登記（含覆蓋上層）、pause 與未處理 wake；[tick](settled/tick.md)的表在 node 裡，是 `.aos/tasks.json` 這張照順序跑的任務表，核心只照順序跑；〔使用者方向 2026-09-30，第二十批疑點裁定 2〕needs 改由普通程式 `aos-needs` 表達（[B-621](settled/tick/needs.md)）；〔暫定〕任務表的 `group`、`needs` 兩欄撤，組改由 `aos-git` 的存檔點劃分（[B-630](settled/tick/git.md)）。資源 module 是後者的普通項目，不另有外掛總表。

〔使用者方向 2026-09-30，第十九批〕daemon 是定期跑 `aos-tick` 的標準程式，不是 tick 存在的前提（cron、人手跑也行）；它負責程序啟停，不判業務排程；可選 root helper 是 daemon 切出的固定特權步驟，見[身分篇](base/identity-resources.md)。每個 LLM 池就是一個 node，由它的代發任務負責實際請求，見 [LLM](scheduling/llm.md)。身分依 [inst](base/inst.md) 及[額度](base/identity-resources.md)，不由路徑或角色推定。

驗收：同一 node 裝排程及 LLM 自主任務，可以兼任 kernel／agent；空成員表不取消 kernel 角色，只有收信任務也不被強制當 agent。

## T-03．工作識別

〔建議預設，未拍板〕`node_id` 指上述路徑；`request_id` 辨識一次投件，`job_id` 辨識邏輯工作，`attempt_id` 辨識一次實際嘗試。重送同一次結果沿用 attempt ID，真的重新執行才換 ID。〔使用者方向 2026-09-29，第十六批〕attempt ID 由發起 node 自己配，不同 node 可能重複；存成工作目錄時名字要加發件者前綴，格式見 [P-402](protocol/work.md)。〔使用者方向 2026-09-30，第十八批〕更精確地說，attempt ID 由**配出它的 node** 配：一般是發起 node；LLM 池限流重試時由池配（P-402）。`run_id` 只在採用 [run](scheduling/runs.md) 分組時需要，不要求所有 node 都有一輪任務。

路徑識別 node，不代表 UID 或舊工作歸屬。〔使用者方向 2026-09-30，第十九批〕**辨識一個 tick** 看資料夾路徑或 inst.json 路徑；給的是 `.aos/inst.json` 或 `inst.json` 時，一律正規化成所在資料夾，所以 tick id 就是 node id。〔使用者方向 2026-09-29〕node id 的唯一性不另防：同一資料夾經 symlink 有兩個路徑、同一路徑先後給不同 node、跨機器重名，都不在考慮範圍，風險由使用者自行承擔；不展開 symlink、不加世代號或跨機檢查。

## T-04．控制狀態與觀測狀態不混用

（09-29 重寫：已刪；結果定義併入 [C-03](contracts.md)，完成證據見 [agent](agent/README.md)，顯示見 [S-402](scheduling/operations.md)。）

## T-05．一萬份本體與少量活動

〔使用者方向 2026-09-28〕目標是 10,000 個扮演 agent 的 node、每小時活躍不到 100 個、雲端推論，見負載方向（已封存檔 2026-09-28-linux-resources-and-task-scheduling.md，索引見 [archive/README.md](../notes/archive/README.md)）。這不是固定併發上限。

〔建議預設，未拍板〕冷 node 保留檔案（在 daemon 底下的也保留登記），不各養常駐程序或空轉 tick；活動量依各 kernel 的資源 module，身分配置依[身分篇](base/identity-resources.md)。

驗收：增加冷 node 不增加逐 node 常駐程序或 history 讀取；啟動時重建樹的成本與平時少量活動成本分開量，見 [V-04](conformance.md)。

## T-06．可排程計算、多層多 kernel

〔使用者方向 2026-09-30，第十八批〕**aos 是給特殊計算用的 OS。** 一般 OS 分配資源的單位是 CPU 指令；aos 分配的單位是一次「計算」，例如一次 LLM 呼叫、agent 的一輪任務。計算必須符合規格，其中一條是能被 Linux 管制（啟動、限制、殺掉）；Linux 管不到的外部計算（例如量子計算）當外部函式庫來管。

- **多層、多個 kernel**：一般 OS 只有一個 kernel；aos 的 kernel 可以有很多個、疊很多層，每個都是 [T-02](#t-02node-與角色) 的 kernel 角色。
- **各 kernel 自訂抽象、資源與隔離**：抽象指任務種類（例如把某種 agent 任務設成需要排程的一種）；資源不限 CPU、記憶體；隔離也可以在不同地方不同。aos **正式開放** kernel 登記自己的任務種類與資源名稱，schema 的列舉跟著放寬；aos 本身只提供 [tick 核心](settled/terms.md#t-07tick-核心)、標準任務表範本裡的系統級任務、普通程式（例如切換帳號的 `aos-as`；每項一框的 `aos-cg`）、daemon（程序收尾；有 cgroup 時 node 框與上限）與登記框架（〔使用者方向 2026-09-30，第二十批〕[T-10](settled/terms.md#t-10tick-核心系統級任務普通程式與其他任務)）。現有寫死的 LLM 三檔、份額、窗口、重試與六類資源，都是「預設 kernel 範本」的規則，不是 aos 對所有 kernel 的要求。
- **上下層不必對齊**：上層只用自己認得的資源與規則管下層，管理要「潤物細無聲」，下層不必知道自己被怎麼管；上下層資源定義不同就不管。kernel 自己定義、Linux 管不到的隔離可以比上層寬；Linux 管的部分（cgroup、帳號）本來就是巢狀，子層只能在已分得範圍內再分。
- **管理目標：隨機性**：用愈多 LLM，隨機性愈高。排程的管理目標之一是隨機性愈低愈好，但要跟任務完成度、資源消耗一起權衡。怎麼量、怎麼權衡，延後（[P-008](protocol/README.md#p-008)）。

〔建議預設，未拍板〕自訂任務種類寫成 `<類別>.<名稱>`，類別只能是 `kernel`、`agent`、`custom`（例如 `agent.review`）；類別怎麼排、誰檢查，以 [B-620](settled/tick.md) 為正本（〔使用者方向 2026-09-30，第十九批〕核心只照陣列順序跑，不看 `kind`），名稱的意思由定義它的 kernel 在自己的設定裡解釋。〔使用者方向 2026-09-30，第二十批〕`kind:"system"` 是[系統級任務](settled/terms.md#t-10tick-核心系統級任務普通程式與其他任務)的標記；〔建議預設，未拍板〕只是標記、核心不看、不授予身分或權限，`system` 不開放自訂子名（`system.x` 拒收）。資源名稱：現有六類（CPU、記憶體、pids、LLM、磁碟、網路）意思固定；其他名稱由定義它的 kernel 自己記帳與解釋，只有 CPU、記憶體、pids 由 aos 寫進 cgroup（下一步納入 cgroup 時）。

〔記錄者理解，不是使用者逐字裁定〕aos 本身只提供讓各 kernel 定義抽象／資源／隔離的框架，加上一個最小的「可排程計算」外殼（能被 Linux 啟動、限制、殺掉，結果交回檔案）。這個外殼（tick 以外的計算單位）怎麼定，延後（P-008）。

驗收：兩個 kernel 各自登記不同的任務種類與資源名稱，互不影響；上層不認得下層的自訂資源時不報錯、不代管。

- T-07．tick 核心：已搬到[整理區](settled/terms.md#t-07tick-核心)，條號不變。

## T-08．投件權就是執行權

〔使用者方向 2026-09-30，第十八批〕能投件給某 node，就等於能用它的身分跑任意程式；這件事**會傳遞**：A 能投給 K、K 能投給池，A 就等於也能用池的身分。隔離與 key 保護只對整條投件鏈以外的帳號成立。行為正本見 [B-501](base/transport.md)。〔使用者方向 2026-09-30，第二十批〕由收件這項系統級任務落實（[B-623](settled/tick/mq.md)）；tick–daemon 通道上的訊息同樣適用（[B-614](settled/deferred/daemon/messaging.md)）。

- T-09．收尾、排空停機、熱重載、逃生口：已搬到[暫緩區](settled/deferred/terms.md#t-09收尾排空停機熱重載逃生口)，條號不變。

- T-10．tick 核心、系統級任務、普通程式與其他任務：已搬到[整理區](settled/terms.md#t-10tick-核心系統級任務普通程式與其他任務)，條號不變。

- T-11．daemon 核心與模組：2026-10-01 新增，在[整理區](settled/terms.md)。
