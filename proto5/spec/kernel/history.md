← [kernel](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`kernel：排程也是一格一格的 aos-exec（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構第二份；同日照 astra 三輪審查改過（K／X／R、K2／X2／R2、K3／X3／R3）。
> 2026-09-23 定稿並已實作：[`aos_kernel.py`](../../lib/aos_kernel.py)（入口 `aos-kernel`）。舊 kernel-home.md／aos-kernel.md 已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）。
> 已拍板的前提在 §9，我自己選的在 §10。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 命令列全改 `--target K`（省略找 `AOS_KERNEL_HOME`→目前資料夾，錯誤行講來源）、`stop` 改名 `halt`、`init` 改讀 `--config FILE`、`--daemon` 改名 `--daemon-target`；§3 tick 的 args 同步。
