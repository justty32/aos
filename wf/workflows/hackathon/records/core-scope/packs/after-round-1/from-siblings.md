# 下一輪的資料包 — 兄弟專案裡可以抄的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/from-siblings.md)

repo 之外、同一批 simple_tools 兄弟專案裡可以直接拿來抄的實作與測例。

## 3. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉已有「同目錄 temp、write-all、file fsync、atomic rename、directory fsync」及「已有 intent、缺可信結果就停在 unknown、不自動建立新 attempt」的完整文字基線。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()`／`fsync_directory()` 是可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync 實作；它遇到同內容既有 target 直接返回、不同內容則拒絕，正好提供 p2 可重入發布實驗的既有程式樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()` 已實測 effect 落盤後殺 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`，重跑 recover 也不增加 effect；精確涵蓋範圍與限制寫在同目錄 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉與〈明確未驗，不可外推〉。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()`，配上 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()` 與 recovery tests，已有「完整證據才 commit receipt、不完整證據維持 unknown」的三態判讀樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉與〈小原型該回答什麼〉已把「可唯一推導就補回；仍有兩種可能就不猜」及 effect 後殺 manager、重開不得重送的驗收寫成現成文字。
- `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()` 已有同目錄 `NamedTemporaryFile`、完整寫入、`os.replace` 與殘留 temp 清理的輕量版本；它沒有 fsync、no-replace 或 receipt，適合只拿來對照 p4 所稱的三行 helper 到底已涵蓋哪些動作。
- `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉與〈整個實例被強制終止〉已明寫 tool error 不代表外部副作用 rollback、整個 process 被殺時不保收尾；`agentloop/CONTROLLER.md`〈明確不負責〉又明列它不做持久化、Task queue 或副作用 recovery，可作 no-aos 對照的能力邊界資料，不能當成 crash recovery 實作。
