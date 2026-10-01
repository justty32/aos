# 基底規格入口

← [規格入口](../README.md)｜[共用契約](../contracts.md)

> **〔2026-10-01 殘留註記〕本篇是 2026-10-01 之前的設計，下列內容現在不是現行的**；原文照留，以這裡指的正本為準（各批裁定見 [verdicts 11 篇末](../../notes/verdicts/11-tick-as-unit.md)）：
> - `aos-as`（任務自己換帳號）：第十三批暫緩（[P-212](../settled/deferred/protocol/tick.md#p-212aos-as切換帳號建議預設未拍板)）；現行切帳號只在 daemon 設定檔做（帳號模組 [B-646](../settled/daemon/account.md)）。
> - `aos-git`（開格、存檔點、收尾）與有 git 版範本：第十七批暫緩（[B-630](../settled/deferred/git.md)）；要提交、還原改用 hook 加普通 git 指令（範例在 [B-635](../settled/tick/hooks.md)）。
> - 標準任務表範本（[B-629](../settled/deferred/template.md)）、`aos-mq get`／`post`（[B-623、B-624](../settled/deferred/mq.md)）、`aos-clean`（[B-404](../base/storage.md) 的系統級任務部分、P-605）：第十八批暫緩，現行沒有系統級任務；kernel／agent 範本裡掛的這些項也跟著不成立。現行收發信是 daemon 訊息模組 `aos-mq send`／`take`／`peek`（[B-645](../settled/daemon/mq.md)）。
> - node：tick 層改稱「工作資料夾」，daemon 只認設定檔 `insts` 的一項；node 模組不做（[名詞](../settled/terms.md)、[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。本篇講的 node、上下層、kernel／agent 角色都是舊設計。
> - 舊 daemon 的通道與憑證（`AOS_TICK_TOKEN`）、登記、runner、`state.json`：整套在暫緩區（[舊 daemon](../settled/deferred/daemon/README.md)）；現行 daemon 只定期叫 `aos-exec` 加各模組（[B-640](../settled/daemon/core.md)）。

| 篇章 | 責任 |
|---|---|
| [工作材料與結果](work.md) | 固定一次工作的輸入、識別與結果 |
| [inst 第 1 版](inst.md) | 跑什麼、用誰、路徑、環境與指示詞 |
| [執行器](execution.md) | 啟動、後代收尾、取消、逾時與失敗 |
| [身分與資源](identity-resources.md) | 身分額度、資源限制的落地；可選 helper 與 `aos-as`（B-303）已搬到[整理區](../settled/deferred/helper.md) |
| [儲存](storage.md) | 收件區、追蹤區、完整發布與清理 |
| [通訊](transport.md) | 投件授權與簡單去重 |
| [daemon](../settled/daemon/README.md)（整理區） | 定期跑 `aos-tick` 的標準程式：登記、喚醒、程序生命週期、重啟與通道 |
| [通用 tick](../settled/tick.md)（整理區） | 核心（互斥鎖、照表跑、上下層、每項結束碼紀錄）與標準任務表範本（系統訊息佇列、發摘要〔2026-10-01 搬暫緩區〕、清理、`aos-git`；git 與 cgroup 有就用） |
| [kernel 樹](../scheduling/README.md) | node 成員關係、排程與資源 module |

<a id="b-000責任與驗收建議預設未拍板"></a>
## B-000：責任與驗收

（09-29 重寫：已刪；角色併入[名詞](../terms.md)，驗收各歸葉篇。）
