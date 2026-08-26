# 第 2 輪之後的資料包 — 上一輪給過的料，有沒有人真的用

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)

把第 1 輪資料包給過的每一條逐項回查：有用、沒有用，沒用的再判斷是不是不相干。這一塊只有這份資料包有。

## 2. 上一輪給過的料，有沒有人真的用

- **有用。** p3 實測的錯名 silent stall、p1／p2 的 `.runi` 拒絕重開與多人對 visibility-only 的表述，都對上 `docs/aos-folder.md`〈六、交接協定〉與〈八、退出碼〉。
- **有用。** p3 重測 `<name>.json` 與 `name.part.json` 的差別，正面使用了 `core/inst/docs/handoff.md`〈彙整規則〉與 `core/inst/src/handoff.cpp` 的 `is_delivery_name()` 契約。
- **有用。** p1 的 `replay-delivery`、p2 的 `recover-world` 都是針對 `core/inst/docs/handoff.md`〈取件與釋放〉及 `core/inst/tests/test_run_handoff.cpp` 所呈現的整批 `.runi` 邊界，但兩者都明寫沒有變成 instruction program counter。
- **有用。** p1 第一版 recovery 因 dash `kill` 失敗後改用 `/bin/kill` 管 process group，與 `core/inst/docs/exec.md`〈逾時與行程群組〉、`core/inst/src/exec.cpp` 的 group-signal 路徑直接相關。
- **有用。** p3 的 crash matrix 分開 `aos_exit` 與 `fault_instruction_exit`，p1 也抓到三次 exit 0 但 final JSON 已壞，用到 `wf/workflows/common/gotchas.md`〈使用 aos〉與 `docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉的區分。
- **有用。** p3 以合法／非法名稱、same-target race 與錯誤可見性擴充了 `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉的基線。
- **有用。** p3 改用前景 `timeout --preserve-status --signal=INT`、p4 讓 no-aos 鏈接受同樣三刀，明確沿用 `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉的 harness 經驗。
- **有用。** 四人都再測 request／effect／result 窗口，p1／p2 更將 `adopt | retry | abandon` 做成命令，實際用上 `wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉與〈`aos recover [WORLD]`〉。
- **有用。** p1／p2 將 Effect 的 `pending／done／unknown`、stable key、decision 與 ledger 分開，落實了 `wf/workflows/workshop/background/reliability.md`〈Effect〉〈idempotency key〉〈ledger〉與〈`unknown`〉。
- **有用。** 四人都分開 Publish、Deliver、key 與 receipt，並用 Already／Conflict 實測其邊界，直接用到 `wf/workflows/workshop/background/delivery-contract.md`〈Publish〉〈Deliver〉〈correlation ID〉與〈receipt〉。
- **有用。** p1／p3／p4 都實測 aggregate 後同 key 重投，p2 更打出 consumed-before-receipt，正是 `wf/workflows/workshop/background/questions-deliver.md`〈沒有耐久 ledger 時…〉的四個重叫時點。
- **沒有。** `wf/workflows/workshop/background/questions-deliver.md`〈Deliver 要採哪一組成功 JSON、錯誤 JSON…〉沒有被做成共同輸出契約，四份私有原型各用一套欄位；猜是本輪主題是 crash window，這條**不相干**。
- **有用。** p2 跑了 file fsync＋directory fsync 路徑，其餘三人則明寫 visibility-only，對應 `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename…〉與 `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉。
- **有用。** p1 依 Publish → Deliver → Effect 分層，p2 反過來用 consumed-before-receipt 修正它，實際檢驗了 `wf/workflows/workshop/records/agent-loop-architecture.md`〈R2 想法池（收攏成方向）／合併後的功能清單〉與〈其實是同一件事的／可以疊在一起的〉。
- **沒有。** p2／p3 仍寫了只支援窄版 string argv 的 Python validator，沒有使用 `docs/inst-directives.md`〈五、適用範圍〉指向的 canonical schema；猜是第二輪尚未要求 parser conformance，這條**不相干**。
- **有用。** p2 的 stable temp、write-all、file／directory fsync 與 incomplete evidence 保持 unknown，明顯對上 `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉。
- **有用。** p2 的 Publish 與 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` `atomic_publish()`／`fsync_directory()` 具有同目錄 temp、write-all、fsync 與再入判讀的同一組元件。
- **有用。** p1／p2 在 parent 中止後都不重做已有完整證據的 effect，命中 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 kill-parent 後不 respawn 邊界。
- **有用。** p1 的 `adopt-temp`、p2 的 result-ready／unknown 分流，對上 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()` 三態判讀。
- **有用。** p1／p2 都把「可唯一推導就 adopt、仍有兩種真相就 unknown」做成實際恢復分支，對應 `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D〉與〈小原型該回答什麼〉。
- **沒有。** p4 改用 hard link 實作 no-replace，沒有取用 `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` `_atomic_write()` 的 `os.replace` 版；猜是後者可覆蓋 target，與本輪 no-replace 契約**不相干**。
- **有用。** p4 把 no-aos 鏈的能力邊界實測到「中止不代表副作用 rollback」，與 `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉〈整個實例被強制終止〉及 `agentloop/CONTROLLER.md`〈明確不負責〉一致。
