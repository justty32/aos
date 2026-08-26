# agent loop 的實作架構與基礎 `aos core` 功能
← [workshop](../../README.md)｜前一場：[四個懸而未決的設計選擇](../four-open-choices-tradeoffs.md)

| | |
|---|---|
| **主題** | agent loop 真的要做出來的話，架構長什麼樣、需要哪些基礎 `aos core` 功能 |
| **開場** | 2026-08-25 |
| **已跑輪數** | R1（各自發想）、R2（收攏成方向） |
| **狀態** | 進行中 |
| **參與身份** | 資深工程師 / 資深架構師 / 資深研究人員（作業系統／體系結構） / 要接這個工具的開發者 |
| **缺哪個角度** | 沒有「普通用戶」——使用者先前拿掉了那個身份。所以**沒有「這東西人看不看得懂」的視角** |
| **reasoning effort** | `xhigh` |
| **參與者** | **與〈四個懸而未決的設計選擇〉是同一批人**（同一批 codex session 續下來），所以他們帶著那場的完整脈絡。兩場紀錄互相連結。 |

## 先讀這段（500 字懶人包）

**只能先做三樣時，四位選得完全相同：**

1. `publish`：原子發布檔案／目錄，是底座。
2. `deliver`：驗證、去重後投進 queue，是現有缺口。
3. `effect`（含 resolve）：記外呼的 done／unknown，避免盲目重付費。

三者可以疊起來：`deliver` 是「驗證＋key＋queue」的 publish；`effect` 也用 publish 記狀態，完成後
可再 deliver 下一回合。prompt 組裝、回覆解析、final／budget 仍留給腳本與 adapter，不進 core。

串行 loop 已夠用；還缺的是平行工具的 join，以及 crash 後對齊 event、cursor、receipt 與下一次
投遞的通用 reconcile。這兩項能否不帶 agent 語意，尚未收成 core 功能。

---

## 這場拆成三份，按「內容職責」分

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [R1：想法池](r1-ideas/README.md) | R1 四位各自發想，**已再按主題拆成一個資料夾**：本場任務與 `aos core` 該收掉的原語（deliver／effect／publish／recover 候選表、斷點續跑的硬邊界）、agent loop 的形狀（耐久狀態機、一個完整循環、前一場四題可繼續懸著）、還沒收攏的（還在生長的想法、大家問出來的問題、明顯的坑）。 | 想知道 agent loop 的架構長什麼樣、`unknown` 為什麼不能自動重跑 |
| [R2：收攏成三個原語](r2-three-primitives/README.md) | R2 把 R1 的不同命名收成 Publish／Deliver／Effect 三個功能家族，**已再按主題拆成一個資料夾**：三個功能家族（功能清單、依賴鏈、「只能先做三樣」的一致選擇）、core 的邊界與還缺的一塊、問題與坑。 | 想知道基礎 `aos core` 功能收窄成哪幾項、什麼刻意留在腳本 |
| **[轉交提案](handoff.md)** | **要使用者拍板才足以改規格／roadmap 的六項提案。** | **要拍板時看這份** |

---

## 續場資訊

與[前一場](../four-open-choices-tradeoffs.md)相同的四個 codex session 仍保留 context，後續用同一批
接續。session id **只在 office Windows 那台機器有效**；`codex exec resume <id>` **不吃 `-s`
與 `-C`**。

| 身份 | session id |
|---|---|
| 資深工程師 | `01a03676-8fa3-7622-aee8-05801a7059d3` |
| 資深架構師 | `01a0367b-797f-7403-999e-fe2c685a8c10` |
| 資深研究人員（OS／體系結構） | `01a03683-95cb-7331-8528-d1513a6c806f` |
| 要接這個工具的開發者 | `01a03688-8b4c-70b0-87e3-ea28be9b7f9c` |

