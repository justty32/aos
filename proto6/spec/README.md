# proto6 規格草案

← [proto6](../README.md)｜[概念入口](../notes/concepts.md)

2026-09-28，將三大概念繼續拆至可實作、可寫驗收的契約。**這是完成一輪編寫與一致性查核的草案，不是產品已完成，也不是所有預設已獲使用者拍板。** 規格內有資料型別、合法轉移、提交時點、錯誤與恢復；停止在這個粒度，不繼續拆成 syscall 教程。

## 閱讀順序

1. [名詞與責任](terms.md)：哪一層負責什麼，ID 與狀態各代表什麼。
2. [共用資料契約](contracts.md)：Owner、Run、Job、Attempt、BlobRef、Proposal 的唯一共用定義。
3. [基底](base/README.md)：描述與執行、身分資源、持久交接、程序恢復。
4. [agent](agent/README.md)：設定、輸入、記憶、工具、tick。
5. [任務與排程](scheduling/README.md)：輪次與單寫者、ready／due、入場與額度、人工處置。
6. [驗收入口](conformance.md)：主概念到葉條款的對照及整合故障場景；各節另有 Given／When／Then。
7. [協議篇](protocol/README.md)：程式間指令與 JSON／資料夾交接的共用約定、待決事項及五份平行分工；人用 CLI 後續再定。

## 來源、正本與可替換預設

來源標記依 [T-01](terms.md)。每節標记覆蓋該節條款；使用者方向與為閉合契約提出的預設分開。共同欄位以 contracts 為準，領域新增欄位在所屬篇定義；狀態轉移由對應葉條款定義，範例不創造另一套schema。[RPC 操作資料](base/methods.json) 是 B-502 的欄位表，使用 `wf-table/1` 保存。

這版採用單一控制寫入者、不可變blob＋checkpoint提交、claim／generation、有限run預算、普通新訊息排下一run等**建議預設**，並非聲稱每項都是唯一或最簡設計。依 [2026-09-29 裁定](../notes/2026-09-29-verdicts.md) 1，「一輪任務（run）」是後續設計的**軟性原則**：run 相關條文（一則訊息一 run、[A-202](agent/input.md)／[S-101](scheduling/runs.md) 普通新訊息排後續 run）是建議預設，不當硬規定；任務途中新訊息的歸屬暫不定案。兩份獨立審查是後續裁定材料：[冗餘審查](../notes/spec-redundancy-review.md)、[遺漏審查](../notes/spec-gaps-review.md)。其中提出的架構精簡選項不因被記錄就自動採納；明確契約衝突則在本稿修正並留審查狀態。

依 09-29 裁定：日常特權點是極小 root helper、主 daemon 非 root（[B-303](base/identity-resources.md)）；LLM 由控制側代發服務集中持 key、agent 與工具只投請求（延續 proto5）（[S-301](scheduling/llm.md)）；磁碟額度可選且只記帳（[B-304](base/identity-resources.md)）。外牆profile仍未選定。profile缺少所需保護時拒絕啟動工作，不以較弱方式假裝合規。FUSE、分散式kernel、父子demo與串流產品介面延後；stream相關條款僅防止部分輸出被誤當完成。

## 原則：能下指令、能管檔案，就能交給 agent

〔使用者方向 2026-09-29〕凡是「下指令」或「管檔案」就能做到的事（改設定、處理待處理事項、跑清理、投件給別的 agent 等），不為 agent 另做一套機制：人能做的，開放對應的檔案或指令權限後 agent 就能做，頂多另外包成工具。權限一律照 Linux 帳號與檔案權限、以及控制入口對呼叫者身分的授權（[B-501](base/transport.md)）判定；agent 做的事不因為是 agent 做的而多出權限，也不因此繞過排隊、預算或 y/n 確認。

## 平台：原生 Linux 與 WSL

〔使用者方向 2026-09-29，[裁定](../notes/2026-09-29-verdicts.md)附題〕原生 Linux 與 WSL2 都要能跑同一套條款；背景見 [WSL 機器查證](../notes/2026-09-29-wsl-machine-check.md)。

**WSL 接受的限制，不防：**Windows interop（任何 UID 可經 interop 以 Windows 使用者身分執行程式）、`/mnt/c` 等 Windows 掛載沒有 Linux 權限與 quota、Windows 磁碟水位（vhdx 所在磁碟先滿時 distro 可能變唯讀）這類 Windows 造成的權限與資源管理問題，是使用 WSL 必須接受的；B-302 probe 不檢查、驗收不以此判不合格。部署可自行關 interop 或收緊 automount，但不是本規格要求。

**照一般恢復規則處理：**牆鐘跳動與 VM 突然關機不算例外。逾時一律用經過時間（[C-01](contracts.md)）；排隊先後一律以持久遞增序號判定、不靠牆鐘（[S-204](scheduling/admission.md)）；VM 關機等同控制端被殺，在途工作依 [B-603](base/lifecycle.md) 全部變 unknown，停機寬限依 [B-604](base/lifecycle.md) 可設定。

**外牆 profile：**若用 Landlock，profile 必須記錄所需最低 ABI，實際 ABI 不足即依 B-302 拒絕啟動；WSL（6.6 kernel）只有 ABI 3，沒有 ABI 4 以上的網路、ioctl、scope 規則。

## 這轮交付的邊界

只建立設計文件與RPC欄位資料，沒有產品程式、測試實作、付費API呼叫或系統設定更動。原有交接快照保留。完成的是概念映射、跨篇欄位與狀態對照、來源／驗收例及本地鏈結查核；所有運行時驗收仍待實作後執行。
