# proto8 討論紀錄：2026-11-01

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-11-01 試驗場現場：agents/bob（進行中）](playground-bob/README.md) | 使用者在 `~/code/playground`（`ws/` 清空、新建 `agents/`）邊說邊做、頂層邊備邊記：第一步 `aos-exec ../agents/bob -- "題"`，bob＝`claude -p`（有 Read／Write 等檔案工具、沒 shell、阻塞到做完），做成兩個檔 `_entry.json`＋`system.txt`、實跑過；使用者原則：**環境變數像 Janet 的 `dyn`，只在必要時用**（bob 因此拿掉 `.env` 傳 system prompt 的做法，只剩 aos-exec 給的 `AOS_WS`）；11-01 晚隊長備好盤點表（59 個 `AOS_*`：必要 5、邊界 11、改 argv 20、改檔 22、沒人讀 1），五題待使用者裁；晚上裁 3「改」與刪 aos-round 後實作完（刪 26、argv 11、檔 3，[03](playground-bob/03-旋鈕改-argv-與檔-實作.md)） |
