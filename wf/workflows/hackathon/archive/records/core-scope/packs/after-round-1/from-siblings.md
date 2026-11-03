# 下一輪的資料包 — 兄弟專案裡可以抄的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/from-siblings.md)

## 3. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉〈結果不明不是失敗，也不是重試許可〉：同目錄 temp、write-all、file fsync、atomic rename、directory fsync；已有 intent、缺可信結果就停在 unknown、不自動建立新 attempt。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()`／`fsync_directory()`：可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync；同內容既有 target 直接返回、不同內容拒絕。
- 同目錄 `test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()`：effect 落盤後殺 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`、重跑不增加 effect；涵蓋範圍與限制在 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉〈明確未驗，不可外推〉。
- 同目錄 `p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()`，配 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()`：完整證據才 commit receipt、不完整維持 unknown。
- `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉〈小原型該回答什麼〉：可唯一推導就補回、仍有兩種可能就不猜；effect 後殺 manager、重開不得重送的驗收。
- `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()`：同目錄 `NamedTemporaryFile`、完整寫入、`os.replace`、殘留 temp 清理的輕量版；沒有 fsync、no-replace 或 receipt。
- `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉〈整個實例被強制終止〉：tool error 不代表外部副作用 rollback、process 被殺不保收尾；`agentloop/CONTROLLER.md`〈明確不負責〉：不做持久化、Task queue 或副作用 recovery。可作能力邊界資料，不是 crash recovery 實作。
