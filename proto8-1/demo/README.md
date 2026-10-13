# proto8-1/demo — 用 daemon 跑一棵 tasks 樹

← [proto8-1](../README.md)｜daemon：[proto8/lib](../../proto8/lib/README.md)｜daemon 自己的 demo：[proto8/demo](../../proto8/demo/README.md)

拿 [aos-seq／aos-par／aos-if／aos-not](../README.md) 組一段像真的的流程，丟給 proto8 的 daemon 跑，目的是看這套原語**實際寫起來缺什麼、哪裡繞**（最後一節）。

```
python3 proto8-1/demo/run.py
```

從哪裡跑都行，約 4.5 秒。只用 Python 標準庫和 `sh`、`cat`、`sleep`；看行程數那段讀 `/proc`，所以要 Linux。

## 分檔目錄

<!-- wf-nav -->
| 分檔 | 涵蓋的段落 |
|---|---|
| [01-場景檔案輸出.md](README/01-場景檔案輸出.md) | 場景、檔案、會看到什麼 |
| [02-寫起來的發現.md](README/02-寫起來的發現.md) | 寫起來的發現 |
