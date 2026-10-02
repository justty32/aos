# daemon 協議：註冊、叫醒與查登記

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../../base/identity-resources.md)、[inst](../../../../base/inst.md)｜[裁定](../../../../../notes/2026-09-29-verdicts.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的登記、叫醒與查詢 method。現行的叫醒、暫停、恢復、查詢見 [P-121](../../../protocol/daemon/control.md)。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

本檔只留 method 的 params、result 與錯誤碼（第十八批）。行為去這裡找：

| 要找什麼 | 正本 |
|---|---|
| 登記、解除、換父、額度 | [B-606](../../daemon/registration.md) |
| 叫醒、暫停、故障停格、格次序號 | [B-607](../../daemon/registration.md) |
| 掛載行程的診斷 | [B-610](../../daemon/channel.md) |
| 誰可呼叫 | [P-103](startup-and-ipc.md) |
| 通道憑證 `token` | [P-117](channel.md) |
| 掛行程與砍掉 | [P-118](channel.md) |

## 分檔目錄

> 2026-10-02 整理：原檔約 12 KB 超過 8 KB 門檻，按標題逐字拆進 `registration/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-104-P-105-註冊與叫醒.md](registration/01-P-104-P-105-註冊與叫醒.md) | P-104．註冊〔建議預設，未拍板〕；P-105．解除、叫醒、暫停、恢復與清除掛載診斷〔建議預設，未拍板〕 |
| 2 | [02-P-106-P-115-查登記與啟動ID.md](registration/02-P-106-P-115-查登記與啟動ID.md) | P-106．查登記與最近一格〔使用者方向 2026-09-29，CLI H-034 D1；欄位為工程預設〕；P-115．啟動 ID 與按需重建〔使用者方向 2026-09-29，裁定「kernel 別每格都重新註冊」；欄位為工程預設〕 |
