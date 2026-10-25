# 下一輪的資料包 — 還是查不到的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/not-found.md)

## 4. 還是查不到的

- 斷電後 file data／directory entry 是否仍在：`questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉只有測試方法與選項，`PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也排除 power loss，**沒有現成資料**。
- 「PTY 真送 `^C` 且 wrapper 存活、獨立取得 aos exit」的 harness：`core/inst/tests/test_run_loop.cpp` 的 loop signal tests 與 `t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉的 `timeout` 現場都不是，**沒有現成資料**。
- `dcap`、`freepy/agentloop` 沒有 Publish receipt、Effect resolve 或多 producer delivery 可抄。

其餘當時查不到的（統一計數表、雙 producer 1,000 件、no-aos 承受三刀）已由第 2、3 輪實測補上。
