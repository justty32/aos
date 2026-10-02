# aos 通用慣例：結束碼、狀態資料夾名、環境變數、設定檔頂層

← [整理區](README.md)｜[名詞](terms.md)｜[通用 tick](tick.md)｜[daemon](daemon/README.md)

這篇放 aos 自己所有程式（`aos-exec`、`aos-tick`、`aos-daemon`、`aos-ctl`，以及之後的系統級任務與普通程式）都要守的三件事（C-08～C-10），加上兩份設定檔頂層 `cwd` 與指示詞展開的對照（C-11）。各程式自己的碼表、旗標寫在各自那條，這裡只講共通的規矩。

依據：[第二十批裁定篇末 2026-10-01 各節](../../notes/verdicts/11-tick-as-unit.md)（結束碼慣例、`AOS_DIRNAME`、第二批的 tasks.json 頂層預設）；現行程式 [proto6/src/py](../../src/py/README.md)。

## 分檔目錄

> 2026-10-02 整理：原檔約 16 KB 超過 8 KB 門檻，按標題逐字拆進 `conventions/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-C-08結束碼與C-09狀態資料夾.md](conventions/01-C-08結束碼與C-09狀態資料夾.md) | C-08．aos 結束碼慣例；C-09．狀態資料夾的名字：`AOS_DIRNAME` |
| 2 | [02-C-10-環境變數總表.md](conventions/02-C-10-環境變數總表.md) | C-10．aos 環境變數總表 |
| 3 | [03-C-11-設定檔頂層與指示詞.md](conventions/03-C-11-設定檔頂層與指示詞.md) | C-11．設定檔頂層 `cwd` 與指示詞展開範圍 |
