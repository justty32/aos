# research flavor 包 — 文獻／資料庫型專案

← [repo README](../../README.md)（導航中樞）

把**外部材料**（論文、報告、規格書、影片逐字稿、訪談）持續抓進來、摘要、登錄、綜述，長成一座**有索引真相層的累積庫**。搭配 [`template/`](../../template/) 這個共用 kernel 用——kernel 給分層樹骨架與活狀態，本包只提供研究類工作流。

**與 [knowledge 包](../knowledge/README.md)的分工**：knowledge 的 digest / learn 是**一次性讀懂**——材料範圍有限、讀完即止，產物是摘要與筆記樹。research 是**持續累積**——材料一直進來，庫本身需要一層索引才知道有什麼、哪些還沒做。**材料超過 30 件、或「還沒處理的」多到要排隊**時就換到本包；不到這個量用 digest 就夠。兩包可並存：庫外的一次性材料走 digest，進庫的走 [source-intake](workflows/source-intake.md)。

## 真相層 / 衍生層

本包四個工作流都圍著同一條原則轉：**索引真相層**（`index/`，「有什麼、做到哪」只有這裡算數）→ **內容真相層**（摘要／翻譯／筆記的 `.md`）→ **衍生層**（網頁、匯出檔、綜述呈現頁）。三層各管什麼、規矩是什麼在 [workflows/common/index-rules.md](workflows/common/index-rules.md)，本檔不重述。

綜述（[survey](workflows/survey.md) 的產物）也算呈現層：它可以整份重寫，因為每個結論都用 `[[id]]` 連回內容真相層。

## 歷史日誌 `logs/`：累積型庫多出來的一類 durable

kernel 的活狀態（`SESSION-LOG.md` / `WAIT_USER.md`）**只列 open、完成即刪**。累積型的庫另外需要一份**已完成事件的流水帳**：按月一檔 `logs/<YYYY-MM>.md`，一件事一句話，寫**做了什麼＋數字變化**（例：`index 452→464`）。

兩者互補不重疊：活狀態回答「還沒做完什麼」，`logs/` 回答「這個月庫長了多少、動過哪裡」。`logs/` 只追加或修正事實，**不拿來保存目前狀態**——目前狀態在 `index/`。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.research.md](WORKFLOWS.research.md) | 派發表片段（四列＋「分辨」欄），貼進 kernel 的 `WORKFLOWS.md` |
| [INDEX.research.md](INDEX.research.md) | 佈局表片段（`index/`、`backlog/`、`logs/`、內容真相層、衍生層），貼進 `INDEX.md` |
| [COMMON.research.md](COMMON.research.md) | common 表片段（一列），貼進 `workflows/common/README.md` |
| [workflows/source-intake.md](workflows/source-intake.md) | **主線**：一件材料入庫（抓取 → 摘要 →（可選）翻譯 → 登索引 → 補日誌）|
| [workflows/backlog.md](workflows/backlog.md) | 候選池：一批一檔、整批做完凍結 |
| [workflows/survey.md](workflows/survey.md) | 跨件綜述：找咬合與矛盾，每個結論標 `[[id]]` |
| [workflows/collide.md](workflows/collide.md) | 接點筆記：把材料對到自家構想，產物只留本庫 |
| [workflows/TEMPLATE.summary.md](workflows/TEMPLATE.summary.md) | 摘要骨架（固定段落＋作者自報 / 本檔補註的歸屬界線）|
| [workflows/TEMPLATE.batch.md](workflows/TEMPLATE.batch.md) | 候選批次骨架（frontmatter 四欄＋候選表）|
| [workflows/common/index-rules.md](workflows/common/index-rules.md) | 索引真相層維護規則，四個工作流共用 |

## 可選工作流菜單

四個工作流是**菜單、不是套餐**：只抓材料進庫的專案用 source-intake + backlog 就夠；不為任何自家構想服務的庫不需要 collide；材料少到不必排隊的話連 backlog 都可以不要。導入時只複製要的那幾個檔，派發表也只貼對應的列；事後才決定不要 → 照文末「移除某工作流要動的地方」拆乾淨。

想法要不要做、何時做走 kernel 的 `workflows/planning.md`；產出給人讀的文字文風可另外合 knowledge 包的 `common/writing`。

## 怎麼合進 kernel

```
tools/wf-init.sh --target <專案> --flavor research
```

通用步驟見 [IMPORT.md](../../IMPORT.md)。本包特有的三點：

1. `common/index-rules.md` 併入 `workflows/common/`。
2. 三個片段各插到對應標記之前：[WORKFLOWS.research.md](WORKFLOWS.research.md) → `WORKFLOWS.md` 的 `<!-- wf-insert:WORKFLOWS -->`；[INDEX.research.md](INDEX.research.md) → `INDEX.md` 的 `<!-- wf-insert:INDEX -->`；[COMMON.research.md](COMMON.research.md) → `workflows/common/README.md` 的 `<!-- wf-insert:COMMON -->`。
3. 另外建資料層目錄：`index/`（含 `index/README.md`：分類檔表＋狀態圖例＋維護規則指標）、`backlog/`（含 `README.md` 與 `archive/`）、`logs/`、內容真相層目錄（`{{摘要目錄，如 summaries/}}` 等）、抓取暫存 `raw/`（建議加進 `.gitignore`，並記住驗收前不清）。

## 移除某工作流要動的地方

| 移除 | 刪什麼 | 同步改什麼 |
|------|--------|-----------|
| source-intake | `workflows/source-intake.md` | `WORKFLOWS.md` 該列；backlog 的「開新一批」第 3 步與交接、survey / collide 的「何時不用」；`TEMPLATE.summary.md` 的導覽行 |
| backlog | `workflows/backlog.md`、`workflows/TEMPLATE.batch.md`、`backlog/` | `WORKFLOWS.md` 該列；`INDEX.md` 的 `backlog/` 列；source-intake 的「何時用」與交接、collide 流程第 2 步、survey 交接 |
| survey | `workflows/survey.md` | `WORKFLOWS.md` 該列；source-intake / backlog / collide 的「何時不用」與交接 |
| collide | `workflows/collide.md` | `WORKFLOWS.md` 該列；source-intake / backlog / survey 的交接段 |
| （共用）index-rules | `workflows/common/index-rules.md` | `workflows/common/README.md` 該列；四個工作流引用它的那行；README 的「真相層 / 衍生層」段 |

改完跑 `tools/wf-lint.sh`（Claude Code 可用 `/wf-lint`）確認沒有壞連結與孤兒列。
