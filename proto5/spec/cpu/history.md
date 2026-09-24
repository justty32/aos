← [cpu](README.md)｜[spec 總導航](../README.md)

# 沿革

原標題：`cpu 範式與 exec cpu（第 1 版，2026-09-23 定稿）`

> 2026-09-23 重架構的第一份；同日照 astra 三輪審查改過（C／X／R、C2／X2／R2、C3／X3／R3）。
> 2026-09-23 定稿並已實作：[`aos_home.py`](../../lib/aos_home.py)、[`aos_client.py`](../../lib/aos_client.py)、[`aos_exec_cpu.py`](../../lib/aos_exec_cpu.py)（入口 `aos-cpu`）。
> 舊的 run／daemon／kernel／cpu-queue 八份已刪（副本在 [proto5.1/spec/](../../../proto5.1/spec)）；llm-cpu／tool-cpu 四份等 agent 重寫落地再刪。
> 已拍板的前提在 §9，我自己選的在 §10。
> 2026-09-24 實作補記：依實作審查回寫，見 impl-review-report.md；補進的句子標「（09-24 補）」，總表在檔尾〈實作補記〉。（審查與實作紀錄在 [rearch 筆記](../../notes/2026-09-23-rearch/README.md)）
> 2026-09-24 fix-r4：§6 `aos-cpu [DIR]` 的 DIR 可省略（＝目前資料夾）。
