# Linux 隔離探針

← [實測報告](../2026-09-28-linux-isolation-probes.md)

從 repo 根目錄以普通使用者執行：

```sh
python3 proto5/notes/2026-09-28-linux-probes/run.py
```

`run.py` 在新建的 `/tmp/aos-landlock-probe-*` 裡建立自有 canary，編譯 `landlock-canary.c` 並作為獨立子程序執行。C 程式設置 NNP 與 Landlock，驗證自己和 fork 子程序的讀写限制；Python runner 不施加限制，驗證仍可讀取兩個 canary。scratch 留供檢查，不自動刪除。

需要 Linux、gcc、Python 3、Landlock；拒絕 root 執行。這不是產品啟動器，也不驗證完整沙盒或跨 UID 的控制通道。
