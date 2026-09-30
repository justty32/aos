# proto6 規格草案

← [proto6](../README.md)｜[架構方向](../notes/2026-09-29-kernel-tree.md)｜[使用者裁定](../notes/verdicts/README.md)

2026-09-29 重寫，2026-09-30 依第十八、十九、二十批改寫。**node 是資料夾；kernel 與 agent 是它可兼任的角色。** node 靠定期被執行的 tick 推進，tick 也是整個 aos 的衡量基準；daemon 是定期跑 tick 的標準程式，不是 tick 存在的前提。狀態留在各 node 的檔案；任務表掛了 git 開格與收尾任務時，以 git 提交及恢復。這是設計草案，不是已完成的產品。

## 定位：給特殊計算用的 OS

〔使用者方向 2026-09-30，第十八批〕

- **分配單位是一次計算**：一般 OS 分配的是 CPU 指令，aos 分配的是 LLM 呼叫、agent 的一輪任務這類計算；計算要能被 Linux 管制，外部計算當外部函式庫管（[T-06](terms.md)）。
- **多層、多個 kernel**，各 kernel 自訂抽象、資源與隔離，aos 正式開放 kernel 登記自己的任務種類與資源名稱；上下層定義不同時不必對齊（[T-06](terms.md)）。
- **Linux 是基底**：CPU、磁碟交給 Linux kernel；cgroup 與使用者帳號是隔離的基礎。〔使用者方向 2026-09-30，第二十批〕node 框與資源上限歸 daemon 與 helper（[B-605](daemon.md)、[B-301](base/identity-resources.md)），每項任務一框、切換帳號是任務自己包的普通程式 `aos-cg`、`aos-as`（[T-10](terms.md)）。
- 〔使用者方向 2026-09-30，第二十批〕**tick 是衡量基準**：排程以格計（「這個任務要花十個 tick」，算安排它的上層的格），排程本身也是掛在任務表上、每格跑一次的程式；反應最快是下一格。除了 tick–daemon 通道，其他所有事都要在某一格裡做，不准有常駐服務繞過 tick（[T-07](terms.md)）。
- 〔使用者方向 2026-09-30，第二十批〕**tick 核心只做四件事**：同資料夾互斥、照任務表依序跑、上下層判定、每項結束碼紀錄（[T-07](terms.md)）。git 開格與收尾、收件、投件、發摘要、清理都是掛在任務表上、`kind:"system"` 標記的**系統級任務**，標準任務表範本就是預設的一組；`aos-cg`、`aos-as`、`aos-needs` 這類包裝是**普通程式**；其餘是 kernel、agent、clock、自訂任務（[T-10](terms.md)）。**投件權就是執行權，而且會傳遞**（[T-08](terms.md)）。
- **管轄區就是 tick 的 cwd**：上層預設看資料夾包含，在 daemon 底下可登記覆蓋（[T-10](terms.md)）。
- 管理目標之一是降低隨機性，怎麼量延後（[P-008](protocol/README.md#p-008)）。

## 閱讀順序

1. [名詞與責任](terms.md)：node、角色、兩張註冊表與工作識別；定位、tick 核心、投件權、系統級任務與普通程式（T-06～T-10）。
2. [通用 tick](tick.md) → [daemon](daemon.md)：先看核心、結束碼紀錄與標準任務表範本，再看 daemon 的登記、喚醒、重啟與 tick–daemon 通道。
3. [kernel 與資源](scheduling/README.md)：樹上分配、資源 module、LLM 池及待處理事項。
4. [基底](base/README.md) → [inst 第 1 版](base/inst.md)：執行身分、工作材料、runner 與檔案交接。
5. [agent 任務](agent/README.md)：設定、內容、context、工具選擇與完成證據。
6. [共用契約](contracts.md)與[驗收入口](conformance.md)：跨篇最少定義及整合故障場景。
7. [人手操作 CLI](cli.md)：用途分層的指令、底層對應、待補接口與完整操作走查。

[協議篇](protocol/README.md)只定新 node 架構的欄位、JSON、schema、範例、argv 與結束碼；行為一律以主規格為正本。目錄名 `agent/`、`scheduling/` 依領域保留，不代表兩種 node。

## 來源與正本

來源與裁定優先序依 [T-01](terms.md)。

〔使用者方向 2026-09-30，第二十批〕**保證跟著「掛了什麼」走**：tick 核心的四件事不靠任何系統級任務也成立；其餘保證看任務表掛了哪些系統級任務、任務包了哪些普通程式、daemon 有沒有 cgroup，例如整格原子要掛了 git 開格與收尾任務才有（[T-01](terms.md)）。第十九批的全掛前提與兩級保證已撤。沒 helper、沒通道只算功能受限（[T-10](terms.md)）。

名詞放 terms，跨篇共用資料放 contracts，各領域規則放所屬篇，其餘只引用。**inst 欄位與解析以 [base/inst](base/inst.md) 為正本**；run 的軟性分組見 [runs](scheduling/runs.md)。

〔使用者方向 2026-09-30，第十八批〕**主規格是正本**：行為規則只寫在主規格；協議篇只留欄位、JSON、schema、範例，寫到行為時只留一句加主規格條號。同一主題分散兩處的，照 [V-01 的正本表](conformance.md)定哪邊寫全。格式版本怎麼演進、哪些鍵永遠禁止見 [C-07](contracts.md)；延後項集中在 [P-008](protocol/README.md#p-008)。

## 原則：能下指令、能管檔案，就能交給 agent

〔使用者方向 2026-09-29〕凡是下指令或管檔案能做到的事，開放權限後 agent 就能做，頂多包成工具，不另造一套機制。人與 agent 共用檔案、指令入口及授權；開放權限仍須遵守已配置的資源限制。

〔使用者方向 2026-09-29〕**工具就是工具，不另外管它做什麼。** 工具用所屬 node 的身分與資源，aos 不另分「工具做的」與「agent 做的」；風險由設定、開放及使用工具的人承擔。只為區分兩者而存在的規則應刪掉。

## 平台：原生 Linux 與 WSL

〔使用者方向 2026-09-29〕原生 Linux 與 WSL2 都要能跑。以 Linux 為基底的定位見[上面](#定位給特殊計算用的-os)。Windows interop、Windows 掛載的權限與資源管理限制、Windows 磁碟水位等不在保護承諾內，背景見 [WSL 查證](../notes/2026-09-29-wsl-machine-check.md)。VM 關機照 [daemon 重啟](daemon.md)處理；運行中逾時與排隊先後分別依 [C-01](contracts.md)及 [S-204](scheduling/admission.md)。

〔使用者方向 2026-09-29 晚〕**依賴**：少外部依賴；初版 aos 本身不依賴 systemd 服務。〔使用者方向 2026-09-30，第十九批〕tick 核心只要 Python 與 flock。〔使用者方向 2026-09-30，第二十批〕**git 與 cgroup v2 不是跑起來的條件**：git 只有 git 開格與收尾任務用（[B-630](tick.md)），cgroup v2 只有 daemon 的 node 框與普通程式 `aos-cg` 用（[B-605](daemon.md)、[B-202](base/execution.md)）；缺了照樣跑，只是那幾項的保證沒有。cgroup 子樹首推用 **systemd 使用者委派**準備（`systemd-run --user --scope -p Delegate=yes`，不用 sudo），檢查步驟、其他子樹來源及「有就用」的可選功能以 [B-605](daemon.md) 為正本，git 最低版本與檢查以 [B-630](tick.md) 為正本。Python 只用標準庫的唯一例外是 `jsonschema`（[P-702](protocol/agent-tasks.md)）；多帳號交接首版只用群組、不用 ACL（[P-208](protocol/node.md)）。

UID 隔離與可選 helper 見[身分篇](base/identity-resources.md)，同帳號部署的 key 保護限制見 [LLM 池](scheduling/llm.md)。〔使用者方向 2026-09-30，第十八批〕隔離與 key 保護只對整條投件鏈以外的帳號成立：能投件給持 key 的 node，就等於能用它的身分讀 key（[T-08](terms.md)）。同機 node 樹是本輪架構；跨機分散式、FUSE 與外牆方案仍不在本輪交付範圍。LLM 串流只是「呼叫任務邊跑邊寫指定檔案」，見 [S-305](scheduling/llm.md)，不另做產品介面。

## 交付邊界

本輪只改規格。運行時保證須依[驗收入口](conformance.md)在實作後驗證。
