← [cpu](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`cpu 範式與 exec cpu（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構的第一份；同日照 astra 三輪審查改過（C／X／R、C2／X2／R2、C3／X3／R3）。
> 2026-09-23 定稿並已實作：[`aos_home.py`](../../lib/aos_home.py)、[`aos_client.py`](../../lib/aos_client.py)、[`aos_exec_cpu.py`](../../lib/aos_exec_cpu.py)（入口 `aos-cpu`）。
> 舊的 run／daemon／kernel／cpu-queue 八份已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）；llm-cpu／tool-cpu 四份等 agent 重寫落地再刪。
> 已拍板的前提在 §9，我自己選的在 §10。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 `aos-cpu [DIR]` 的 DIR 可省略（＝目前資料夾）。
> 2026-09-24 proto5-2 池式納入：§2 `info.json` 多 `notify` 欄位；§6.1 補「fd 1 可以是 `/dev/null`」、啟動多一步補丟通知；§6.3 迴圈多 (4.5) 放通知；新增 §6.4 [notify.md](notify.md)；§5.4 kernel 不再往每顆放 stop。沒寫 `notify` 的 cpu 行為不變。草稿與審查在 proto5-2/spec、proto5-2/notes。
> 2026-09-24 one-boot：kernel cpu 拿掉（tick 改由 daemon 開，[daemon §10](../daemon/ticks.md)）。cpu 範式本身不變，只改 §0「家」、§1 取名、§6.4 通知那幾句提到 kernel cpu／鏈的話。
