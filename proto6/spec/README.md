# 整理區：tick 與 daemon 的基礎

← [規格入口](../README.md)｜[裁定](../../notes/verdicts/11-tick-as-unit.md)｜[現行程式](../../src/py/README.md)

## 原則：程式本身就是 spec

〔使用者 2026-10-02，第二十六批〕這幾支程式（`proto6/src/py/lib`）加測試（`proto6/src/py/tests`）加 schema 與範例（`proto6/spec/protocol/`），就是行為與格式的正本。整理區只留**程式看不出來的**：做什麼（幾句）、為什麼與原則、邊界，然後指向程式與測試。欄位表、驗收、歷史註記不寫在這裡；條號保留在標題上，讓舊連結與裁定對得上。

## 讀法

| 篇 | 條號 | 內容 |
|---|---|---|
| [conventions.md](conventions.md) | C-08～C-11 | 結束碼、狀態資料夾名、環境變數、設定檔頂層 |
| [terms.md](terms.md) | T-07、T-10、T-11 | 核心、系統級任務、普通程式、daemon 模組這些詞 |
| [tick.md](tick.md) | B-602、B-620、B-626、B-627、B-633 | tick 核心：互斥鎖、照表跑、每項結束碼紀錄 |
| [tick/hooks.md](tick/hooks.md)、[tick/tasks-blocked.md](tick/tasks-blocked.md) | B-635、B-636 | 外掛掛點與擋板模組 |
| [daemon/README.md](daemon/README.md) | B-640～646 | daemon 與各模組：控制、重讀設定、記住狀態、收屍、訊息、帳號 |
| [protocol/tick.md](protocol/tick.md)、[protocol/daemon/README.md](protocol/daemon/README.md) | P-120～126、P-200～214 | 檔案與訊息的 JSON 長相（schema 與範例在 [spec/protocol](../protocol/README.md)） |
| [deferred/](deferred/README.md) | 其餘 | 暫緩區，原文照留；B-625 當機恢復也在這裡 |

## 對外依賴

整理區只靠這幾處區外的篇：[名詞與責任](../terms.md)（T-01～T-08）、[共用契約](../contracts.md)（C-01、C-07）、[inst](../base/inst.md)、[儲存](../base/storage.md)（B-404 清理）、[協議通則](../protocol/README.md)（P-001～008）、[驗收入口](../conformance.md)。schema 與範例仍放在 [spec/protocol](../protocol/README.md)（schema 互相 `$ref`，搬開會斷）。

## 還開著的

- 訊息佇列改成 `aos-mq` 之後，區外舊篇（base 傳輸與儲存、scheduling、agent、CLI、部分協議篇、驗收場景）還寫著舊保證（檔案收件、`.aos/outbox/`、鬧鐘、`-32601`），等其他篇放進來時一起改。
- 舊的待送封套 schema `msg-outbox` 與範例 `examples/messages/outbox.*` 已不適用，先不刪。
