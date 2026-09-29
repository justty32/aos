# Linux 隔離探針

> 2026-09-28 交接快照；[原始來源](../../../proto5/notes/2026-09-28-linux-probes/README.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

← [實測報告](../archive/import-2026-09-28/2026-09-28-linux-isolation-probes.md)

從 repo 根目錄以普通使用者執行：

```sh
python3 proto6/notes/probes/run.py
```

`run.py` 在新建的 `/tmp/aos-landlock-probe-*` 裡建立自有 canary，編譯 `landlock-canary.c` 並作為獨立子程序執行。C 程式設置 NNP 與 Landlock，驗證自己和 fork 子程序的讀写限制；Python runner 不施加限制，驗證仍可讀取兩個 canary。scratch 留供檢查，不自動刪除。

需要 Linux、gcc、Python 3、Landlock；拒絕 root 執行。這不是產品啟動器，也不驗證完整沙盒或跨 UID 的控制通道。
- [systemd-run-latency.md](systemd-run-latency.md)：實測 `systemd-run --user` 開短命程序（含資源限制、scope、pipe、並發）與 git commit 的延遲，腳本 `systemd-run-latency.py`。
