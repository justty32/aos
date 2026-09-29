# proto6 規格草案

← [proto6](../README.md)｜[架構方向](../notes/2026-09-29-kernel-tree.md)｜[使用者裁定](../notes/2026-09-29-verdicts.md)

2026-09-29 重寫。**node 是資料夾；kernel 與 agent 是它可兼任的角色。** daemon 管登記與程序，node 透過註冊式 tick 推進；狀態留在各 node 的檔案，以 git 提交及恢復。這是設計草案，不是已完成的產品。

## 閱讀順序

1. [名詞與責任](terms.md)：node、角色、兩張註冊表與工作識別。
2. [daemon](daemon.md) → [通用 tick](tick.md)：登記、喚醒、重啟，再看任務、group 與 git 邊界。
3. [kernel 與資源](scheduling/README.md)：樹上分配、資源 module、LLM 池及待處理事項。
4. [基底](base/README.md) → [inst 第 1 版](base/inst.md)：執行身分、工作材料、runner 與檔案交接。
5. [agent 任務](agent/README.md)：設定、內容、context、工具選擇與完成證據。
6. [共用契約](contracts.md)與[驗收入口](conformance.md)：跨篇最少定義及整合故障場景。
7. [人手操作 CLI](cli.md)：用途分層的指令、底層對應、待補接口與完整操作走查。

[協議篇](protocol/README.md)定義新 node 架構的指令、JSON、schema 與範例；行為仍以主規格和最新裁定為準。目錄名 `agent/`、`scheduling/` 依領域保留，不代表兩種 node。

## 來源與正本

來源與裁定優先序依 [T-01](terms.md)。

名詞放 terms，跨篇共用資料放 contracts，各領域規則放所屬篇，其餘只引用。**inst 欄位與解析以 [base/inst](base/inst.md) 為正本**；run 的軟性分組見 [runs](scheduling/runs.md)。

## 原則：能下指令、能管檔案，就能交給 agent

〔使用者方向 2026-09-29〕凡是下指令或管檔案能做到的事，開放權限後 agent 就能做，頂多包成工具，不另造一套機制。人與 agent 共用檔案、指令入口及授權；開放權限仍須遵守已配置的資源限制。

〔使用者方向 2026-09-29〕**工具就是工具，不另外管它做什麼。** 工具用所屬 node 的身分與資源，aos 不另分「工具做的」與「agent 做的」；風險由設定、開放及使用工具的人承擔。只為區分兩者而存在的規則應刪掉。

## 平台：原生 Linux 與 WSL

〔使用者方向 2026-09-29〕原生 Linux 與 WSL2 都要能跑。Windows interop、Windows 掛載的權限與資源管理限制、Windows 磁碟水位等不在保護承諾內，背景見 [WSL 查證](../notes/2026-09-29-wsl-machine-check.md)。VM 關機照 [daemon 重啟](daemon.md)處理；運行中逾時與排隊先後分別依 [C-01](contracts.md)及 [S-204](scheduling/admission.md)。

〔使用者方向 2026-09-29 晚〕**依賴**：以 Linux 為中心、少外部依賴。cgroup v2 必要、初版不使用 systemd；最低版本、啟動自檢、cgroup 子樹來源與「有就用」的可選功能以 [B-605](daemon.md) 為正本。Python 只用標準庫的唯一例外是 `jsonschema`（[P-702](protocol/agent-tasks.md)）；多帳號交接首版只用群組、不用 ACL（[P-208](protocol/node.md)）。

UID 隔離與可選 helper 見[身分篇](base/identity-resources.md)，同帳號部署的 key 保護限制見 [LLM 池](scheduling/llm.md)。同機 node 樹是本輪架構；跨機分散式、FUSE 與外牆方案仍不在本輪交付範圍。LLM 串流只是「呼叫任務邊跑邊寫指定檔案」，見 [S-305](scheduling/llm.md)，不另做產品介面。

## 交付邊界

本輪只改規格。運行時保證須依[驗收入口](conformance.md)在實作後驗證。
