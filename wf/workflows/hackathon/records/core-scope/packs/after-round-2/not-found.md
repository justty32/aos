# 第 2 輪之後的資料包 — 還是查不到的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1 後](../after-round-1/not-found.md)

repo 與兄弟專案都翻過、確認沒有現成資料的那幾條。

## 5. 還是查不到的

- 在 `core/inst/`、`docs/`、`wf/workflows/experiments/t5-agent-loop.md`、`wf/workflows/workshop/records/` 與 `wf/workflows/workshop/background/` 中都沒有 consumer acknowledgment 的實作或「target commit → aggregate claim → delivery deletion → ack commit」故障矩陣，**這條沒有現成資料**。
- `core/inst/docs/capi.md`檔頭已明寫 C ABI 不提供 batch／handoff API，而 `core/inst/include/aos/inst.h` 也只有單筆 instruction handle；因此「不改 C++ 卻只用現有 C ABI 驗完 Deliver object／array 全契約」，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/agent-machine/`、`/mnt/c/code/mine/simple_tools/freepy/`、`/mnt/c/code/mine/simple_tools/dcap/` 與 `/mnt/c/code/mine/simple_tools/arc_agi_tweets/` 都沒有 aggregate 取件／刪件與 producer receipt 共享同一份耐久 acknowledgment 的實作，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/core-scope.md`〈第 2 輪紀錄〉〈第 2 輪評分與意見〉仍只能列出 1 份實作／9 個呼叫點／8 或 12 筆 transaction／4 個實作位置，repo 與四個兄弟專案都沒有一張既定的跨實驗統一計數表，**這條沒有現成資料**。
- `docs/aos-folder.md`〈十二、留給實作決定的〉只有殘存檔清理方向，`wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename…〉也只有測試方法；真實 power-cut、NFS、非 Linux no-replace 與孤兒 temp 容量數據，**這條沒有現成資料**。
