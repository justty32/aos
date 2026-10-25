# 第 2 輪之後的資料包 — 還是查不到的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1 後](../after-round-1/not-found.md)

## 5. 還是查不到的

- 「不改 C++、只用現有 C ABI 驗完 Deliver object／array 全契約」：`core/inst/docs/capi.md` 檔頭明寫 C ABI 不提供 batch／handoff API，`core/inst/include/aos/inst.h` 只有單筆 instruction handle，**沒有現成資料**。
- aggregate 取件／刪件與 producer receipt 共享同一份耐久 acknowledgment 的實作：`agent-machine`、`freepy`、`dcap`、`arc_agi_tweets` 都沒有。
- 真實 power-cut、NFS、非 Linux no-replace 與孤兒 temp 容量數據：`docs/aos-folder.md`〈十二、留給實作決定的〉只有殘存檔清理方向，`questions-reliability.md` 只有測試方法，**沒有現成資料**。

consumer acknowledgment 的故障矩陣已由第 3 輪實測補上。
