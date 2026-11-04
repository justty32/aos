# backlog — 候選材料池

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

還沒入庫、但值得讀的材料先堆進候選池 `backlog/`：**一批一檔**，整批做完就凍結。它回答「接下來讀什麼」；「庫裡有什麼」是 `index/` 的職責，兩者不互相取代。

**何時用**：掃出一批候選要記下來、使用者說「這些以後要讀」「開新一批」，或要從池子裡挑下一件來做。
**何時不用**：只有一兩件、現在就處理 → 直接走 [source-intake](source-intake.md)。改的是**已入庫**材料的狀態 → 改 `index/`，不改這裡。

## Done when

- `backlog/<批次名>.md` 存在，frontmatter 四欄（`purpose` / `workflow` / `status_legend` / `note`）齊全，候選表每列狀態欄非空。
- `backlog/README.md` 的「現役」表有這一批。
- 整批 ⬜ 歸零後：該檔在 `backlog/archive/`，「現役」表少一列、「已凍結」表多一列。

## 一批一檔

- 一批＝**一次掃描的成果**：一個主題方向、一個時間窗、或使用者一次貼入的清單。檔名 `<批次名>.md`，骨架照 [TEMPLATE.batch](TEMPLATE.batch.md)。
- **不按 bytes 硬切**：一批太大就按**主題方向**拆成兩批，不要切成上下集。
- 狀態圖例與 `index/` 用同一套（見 [common/index-rules](common/index-rules.md)）：`⬜ 待處理`／`🔶 部分完成`／`✅ 完成`。
- **留下的標準**寫進 frontmatter 的 `note`：只留會實際改變既有判斷的，不因為新就收。

## 開新一批（四步）

1. 建 `backlog/<批次名>.md`，frontmatter 照 [TEMPLATE.batch](TEMPLATE.batch.md)。
2. `backlog/README.md` 的「現役」表補一列：檔案 / 批次 / 件數 / 建立日。
3. 逐件處理走 [source-intake](source-intake.md)，做完就改該列狀態。
4. ⬜ 歸零後**整批移進 `backlog/archive/` 凍結**，兩張表各挪一列。

## 凍結後不再維護

凍結檔保留當初的主題分組、★ 優先標記與接點註記，供回溯「當初為什麼選這批」用，**之後不再改它的狀態**。成果只登記在 `index/`——同一件事的狀態不要有兩個真相層。

## 交接

- 挑好下一件 → [source-intake](source-intake.md)。
- 掃候選時就看出跨件的咬合 → 記進該列「接點註記」，成形後走 [survey](survey.md) 或 [collide](collide.md)。
- 這批要不要做、什麼時候做拿不定 → kernel 的 [planning](planning.md)。
- 整批凍結那一刻 → `logs/<當月>.md` 補一句（幾件、何時清空）。
