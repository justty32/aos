# daemon 協議：佈建、私有通道與 runner

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../../base/identity-resources.md)、[inst](../../../../base/inst.md)｜[裁定](../../../../../notes/2026-09-29-verdicts.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的佈建、helper 私有通道與 runner。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## 分檔目錄

> 2026-10-02 整理：原檔約 17 KB 超過 8 KB 門檻，按標題逐字拆進 `provision-and-runner/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-107-P-108-佈建與私有通道.md](provision-and-runner/01-P-107-P-108-佈建與私有通道.md) | P-107．佈建固定動作〔建議預設，未拍板〕；P-108．daemon 與 helper 的私有通道〔建議預設，未拍板〕 |
| 2 | [02-P-109-P-111-runner與錯誤.md](provision-and-runner/02-P-109-P-111-runner與錯誤.md) | P-109．runner argv 與解析〔建議預設，未拍板〕；P-110．runner 結束與 125〔建議預設，未拍板〕；P-111．錯誤〔建議預設，未拍板〕 |
| 3 | [03-P-112-schema與範例.md](provision-and-runner/03-P-112-schema與範例.md) | P-112．schema 與最小範例〔建議預設，未拍板〕 |
