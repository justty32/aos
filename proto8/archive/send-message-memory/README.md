> 封存 2026-11-04：沒有取代者。兩個工具的主人（demo/talk、agent-kai）都不在了，環境變數 `AOS_ROSTER`、`AOS_HEAP` 也不合 N-63（四元素審查 08 步 8 列的瘦身候選）；使用者 11-04 晚回「封存」。

# send_message、memory（原 proto8/lib/aos/send_message、proto8/lib/aos/memory）

底下照原本相對 proto8/ 的路徑擺：`lib/aos/send_message/`（寄信給 `$AOS_ROSTER` 名冊上的成員或群組，帶手數上限）、`lib/aos/memory/`（長期記憶庫 save／search／read／forget，庫在 `$AOS_HEAP`，`heap.py` 是讀寫本體）。環境變數 `AOS_ROSTER`、`AOS_HEAP` 只在這兩個工具用，隨之退場。`check_inbox` 沒封存、留在 `lib/aos/`。只作歷史，不測試、內部路徑與連結不維護；要拉回去就照路徑搬回原處。
