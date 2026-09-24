← [daemon](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`daemon：所有 cpu 的父行程（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構第三份；同日照 astra 第二輪 D 清單（18 題）與第三輪（D3／X3／C3）改過。
> 2026-09-23 定稿並已實作：[`aos_daemon.py`](../../lib/aos_daemon.py)（入口 `aos-daemon`）。舊 daemon-home.md／aos-daemon.md 已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）。
> 已拍板的前提在 §8，我自己選的在 §9。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 命令列改成 `aos-daemon boot`／`halt [--target D]`（裸 `aos-daemon` 退 2、`--home` 拿掉），家的預設從 `~/.aos-daemon` 改成 `AOS_DAEMON_HOME`→目前資料夾。
