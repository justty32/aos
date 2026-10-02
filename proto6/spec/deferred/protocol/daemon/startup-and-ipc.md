# daemon 協議：啟動、設定與 IPC

← [舊 daemon 協議（暫緩區）](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[舊 daemon](../../daemon/README.md)、[helper](../../helper.md)、[身分](../../../../notes/archive/spec-2026-10-02/base/identity-resources.md)、[inst](../../../inst.md)｜[裁定](../../../../notes/2026-09-29-verdicts.md)

> **這篇整篇在暫緩區**（2026-10-01）：舊協議的啟動、設定與 IPC。現行格式見 [P-120](../../../protocol/daemon/core.md)、[P-121](../../../protocol/daemon/control.md)。原因：daemon 改成只叫 aos-exec、不認得 node；管 node 之後另做成模組（使用者 2026-10-01），最核心 daemon 第一版不做。每條標題下有一行狀態。

## 分檔目錄

> 本檔只留前言與目錄，內容按標題拆在 `startup-and-ipc/`。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-P-101-指令與結束碼.md](startup-and-ipc/01-P-101-指令與結束碼.md) | P-101．啟動、設定與 socket〔建議預設，未拍板〕 |
| 2 | [02-P-101-設定檔欄位.md](startup-and-ipc/02-P-101-設定檔欄位.md) | 設定檔欄位；部件與核心開關欄位；頂層項；身分額度 `identity_grant`；佈建權 `provision`；socket |
| 3 | [03-P-102-P-103-sudo與IPC.md](startup-and-ipc/03-P-102-P-103-sudo與IPC.md) | P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕；P-103．IPC 封包與授權〔建議預設，未拍板〕 |
