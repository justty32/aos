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

## 來源、正本與可替換預設

來源標記依 [T-01](terms.md)。每節標记覆蓋該節條款；使用者方向與為閉合契約提出的預設分開。共同欄位以 contracts 為準，領域新增欄位在所屬篇定義；狀態轉移由對應葉條款定義，範例不創造另一套schema。[RPC 操作資料](base/methods.json) 是 B-502 的欄位表，使用 `wf-table/1` 保存。

這版採用單一控制寫入者、不可變blob＋checkpoint提交、claim／generation、有限run預算、普通新訊息排下一run等**建議預設**，並非聲稱每項都是唯一或最簡設計。兩份獨立審查是後續裁定材料：[冗餘審查](../notes/spec-redundancy-review.md)、[遺漏審查](../notes/spec-gaps-review.md)。其中提出的架構精簡選項不因被記錄就自動採納；明確契約衝突則在本稿修正並留審查狀態。

宿主root或namespace內管理、外牆profile、LLM憑證是否集中代理仍未選定。profile缺少所需保護時拒絕啟動工作，不以較弱方式假裝合規。FUSE、分散式kernel、父子demo與串流產品介面延後；stream相關條款僅防止部分輸出被誤當完成。

## 這轮交付的邊界

只建立設計文件與RPC欄位資料，沒有產品程式、測試實作、付費API呼叫或系統設定更動。原有交接快照保留。完成的是概念映射、跨篇欄位與狀態對照、來源／驗收例及本地鏈結查核；所有運行時驗收仍待實作後執行。
