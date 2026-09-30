# Linux 隔離探針

> 2026-09-28 交接快照（09-29 補列 cgroup 成本探針）；[原始來源](../../../proto5/notes/2026-09-28-linux-probes/README.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

← 實測報告（已封存檔 2026-09-28-linux-isolation-probes.md，索引見 [archive/README.md](../archive/README.md)）

從 repo 根目錄以普通使用者執行：

```sh
python3 proto6/notes/probes/run.py
```

`run.py` 在新建的 `/tmp/aos-landlock-probe-*` 裡建立自有 canary，編譯 `landlock-canary.c` 並作為獨立子程序執行。C 程式設置 NNP 與 Landlock，驗證自己和 fork 子程序的讀写限制；Python runner 不施加限制，驗證仍可讀取兩個 canary。scratch 留供檢查，不自動刪除。

需要 Linux、gcc、Python 3、Landlock；拒絕 root 執行。這不是產品啟動器，也不驗證完整沙盒或跨 UID 的控制通道。
- [systemd-run-latency.md](systemd-run-latency.md)：實測 `systemd-run --user` 開短命程序（含資源限制、scope、pipe、並發）與 git commit 的延遲，腳本 `systemd-run-latency.py`。初版不用 systemd（[verdicts/05 追加 1](../verdicts/05-dependencies.md)），此數字僅供日後可選增強參考。
- [per-task-cgroup-cost.md](per-task-cgroup-cost.md)：實測每個任務開一個 cgroup 的成本，腳本 `per-task-cgroup-cost.py`；spec 的 daemon 篇與 [verdicts/08](../verdicts/08-cancel-task-cgroup-and-gaps.md) 引用。
