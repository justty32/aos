# proto6 規格草案

← [proto6](../README.md)｜[架構方向](../notes/2026-09-29-kernel-tree.md)｜[使用者裁定](../notes/verdicts/README.md)

2026-09-29 重寫，2026-09-30 依第十八、十九批改寫。**node 是資料夾；kernel 與 agent 是它可兼任的角色。** node 靠定期被執行的 tick 推進；daemon 是定期跑 tick 的標準程式，不是 tick 存在的前提。狀態留在各 node 的檔案，以 git 提交及恢復。這是設計草案，不是已完成的產品。

## 定位：給特殊計算用的 OS

〔使用者方向 2026-09-30，第十八批〕

- **分配單位是一次計算**：一般 OS 分配的是 CPU 指令，aos 分配的是 LLM 呼叫、agent 的一輪任務這類計算；計算要能被 Linux 管制，外部計算當外部函式庫管（[T-06](terms.md)）。
- **多層、多個 kernel**，各 kernel 自訂抽象、資源與隔離，aos 正式開放 kernel 登記自己的任務種類與資源名稱；上下層定義不同時不必對齊（[T-06](terms.md)）。
- **Linux 是基底**：CPU、磁碟交給 Linux kernel；cgroup 與使用者帳號是隔離的基礎，屬標準配備（[B-605](daemon.md)、[B-301](base/identity-resources.md)）。
- 〔使用者方向 2026-09-30，第十九批〕**tick 分三層**：核心只有同資料夾互斥、照任務表依序跑、上下層判定（[T-07](terms.md)）；**標準配備**是 aos 出廠就附、預設全掛、不能拆的一包（git 提交、needs、收件、切換使用者、cgroup 框、once 等）；其餘是 kernel、agent、clock、自訂任務這類掛載（[T-10](terms.md)）。**投件權就是執行權，而且會傳遞**（[T-08](terms.md)）。
- **管轄區就是 tick 的 cwd**：上層預設看資料夾包含，在 daemon 底下可登記覆蓋（[T-10](terms.md)）。
- 管理目標之一是降低隨機性，怎麼量延後（[P-008](protocol/README.md#p-008)）。

## 閱讀順序

1. [名詞與責任](terms.md)：node、角色、兩張註冊表與工作識別；定位、tick 核心、投件權與三層（T-06～T-10）。
2. [通用 tick](tick.md) → [daemon](daemon.md)：先看核心與標準配備，再看 daemon 的登記、喚醒、重啟與 tick–daemon 通道。
3. [kernel 與資源](scheduling/README.md)：樹上分配、資源 module、LLM 池及待處理事項。
4. [基底](base/README.md) → [inst 第 1 版](base/inst.md)：執行身分、工作材料、runner 與檔案交接。
5. [agent 任務](agent/README.md)：設定、內容、context、工具選擇與完成證據。
6. [共用契約](contracts.md)與[驗收入口](conformance.md)：跨篇最少定義及整合故障場景。
7. [人手操作 CLI](cli.md)：用途分層的指令、底層對應、待補接口與完整操作走查。

[協議篇](protocol/README.md)只定新 node 架構的欄位、JSON、schema、範例、argv 與結束碼；行為一律以主規格為正本。目錄名 `agent/`、`scheduling/` 依領域保留，不代表兩種 node。

## 來源與正本

來源與裁定優先序依 [T-01](terms.md)。

〔使用者方向 2026-09-30，第十九批〕**保證的前提**：本 spec 的保證以標準配備全掛為前提；沒全掛時出現的錯誤不在保證範圍內，各條不逐條寫退化行為。缺 cgroup v2 或 git 才算沒全掛，沒 helper、沒通道只算功能受限（[T-10](terms.md)、[B-630](tick.md)）。

名詞放 terms，跨篇共用資料放 contracts，各領域規則放所屬篇，其餘只引用。**inst 欄位與解析以 [base/inst](base/inst.md) 為正本**；run 的軟性分組見 [runs](scheduling/runs.md)。

〔使用者方向 2026-09-30，第十八批〕**主規格是正本**：行為規則只寫在主規格；協議篇只留欄位、JSON、schema、範例，寫到行為時只留一句加主規格條號。同一主題分散兩處的，照 [V-01 的正本表](conformance.md)定哪邊寫全。格式版本怎麼演進、哪些鍵永遠禁止見 [C-07](contracts.md)；延後項集中在 [P-008](protocol/README.md#p-008)。

## 原則：能下指令、能管檔案，就能交給 agent

〔使用者方向 2026-09-29〕凡是下指令或管檔案能做到的事，開放權限後 agent 就能做，頂多包成工具，不另造一套機制。人與 agent 共用檔案、指令入口及授權；開放權限仍須遵守已配置的資源限制。

〔使用者方向 2026-09-29〕**工具就是工具，不另外管它做什麼。** 工具用所屬 node 的身分與資源，aos 不另分「工具做的」與「agent 做的」；風險由設定、開放及使用工具的人承擔。只為區分兩者而存在的規則應刪掉。

## 平台：原生 Linux 與 WSL

〔使用者方向 2026-09-29〕原生 Linux 與 WSL2 都要能跑。以 Linux 為基底的定位見[上面](#定位給特殊計算用的-os)。Windows interop、Windows 掛載的權限與資源管理限制、Windows 磁碟水位等不在保護承諾內，背景見 [WSL 查證](../notes/2026-09-29-wsl-machine-check.md)。VM 關機照 [daemon 重啟](daemon.md)處理；運行中逾時與排隊先後分別依 [C-01](contracts.md)及 [S-204](scheduling/admission.md)。

〔使用者方向 2026-09-29 晚〕**依賴**：少外部依賴，初版不使用 systemd。〔使用者方向 2026-09-30，第十九批〕tick 核心只要 Python 與 flock；cgroup v2、git 等是**標準配備的必要條件**，拿不到時照[全掛檢查](tick.md)警告、有終端機問 y／n，不再一律拒絕啟動。最低版本、自檢、cgroup 子樹來源與「有就用」的可選功能以 [B-605](daemon.md)、[B-630](tick.md) 為正本。Python 只用標準庫的唯一例外是 `jsonschema`（[P-702](protocol/agent-tasks.md)）；多帳號交接首版只用群組、不用 ACL（[P-208](protocol/node.md)）。

UID 隔離與可選 helper 見[身分篇](base/identity-resources.md)，同帳號部署的 key 保護限制見 [LLM 池](scheduling/llm.md)。〔使用者方向 2026-09-30，第十八批〕隔離與 key 保護只對整條投件鏈以外的帳號成立：能投件給持 key 的 node，就等於能用它的身分讀 key（[T-08](terms.md)）。同機 node 樹是本輪架構；跨機分散式、FUSE 與外牆方案仍不在本輪交付範圍。LLM 串流只是「呼叫任務邊跑邊寫指定檔案」，見 [S-305](scheduling/llm.md)，不另做產品介面。

## 交付邊界

本輪只改規格。運行時保證須依[驗收入口](conformance.md)在實作後驗證。
