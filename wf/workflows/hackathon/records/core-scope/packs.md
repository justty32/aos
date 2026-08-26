# core scope 黑客松 — 資料包（資料員）

← [本場索引](README.md)｜[hackathon](../../README.md)

每輪之後針對卡住的地方找出的可參考資料，每條都有 repo 內路徑。

---

## 下一輪的資料包

### 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在第一個數字沒有唯一口徑：同一份現場同時可數成 1 份 helper、6 個可重跑發布位置或含人工復原的 9 次交易；原始整理在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/report-r1.md` 的〈三個數字〉。
- **p1（Carmack persona）**卡在 SIGINT 後孤兒行程與 `.runi` 並存，且 provider accepted／dropped 的本機 snapshot 相同，復原仍靠人工殺行程、判斷 temp 與外部 oracle；完整現場在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/transcript.txt`。
- **p2（Armstrong persona）**卡在 Publish rename 前中止後仍要人工 `mv`，Ctrl-C 後仍要搬走 `.runi` 並重造只含未啟動 instruction 的半批；整理與各 evidence 路徑在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/ROUND-1.md`。
- **p2（Armstrong persona）**卡在無 query provider 的 effect unknown：盲重試已把 ledger 從 1 筆變 2 筆，現有狀態還沒有可直接操作的 `adopt | retry | abandon` transition；現場在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/evidence/kill-9.log`。
- **p3（Cantrill persona）**卡在 crash harness 沒有為每刀留下獨立的 `aos` exit：PTY 的 `^C` 連 wrapper 一起終止；同一輪也遇到合法性藏在檔名裡、錯名被安靜忽略，以及同 target 重投／雙 producer 尚未測，整理在 `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md`。
- **p4（Thompson persona）**卡在 no-aos 對照只跑 happy path，還沒承受與 aos 版本相同的 SIGINT、SIGKILL、rename 前中止與重開驗收；對照腳本在 `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh`。
- **p4（Thompson persona）**卡在三行 delivery helper 的多 producer 主張尚無壓力資料；目前實作只有 `/home/guanyu/aos-hack/core-scope/p4/round1/deliver.sh`，尚未有兩個 producer 各投 1,000 個唯一 ID 的結果。

### 2. repo 裡已經有答案的

- `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉已寫清 `.temp`／ready／`.runi` 的可見邊界、`.runi` 只代表一回合沒跑完、存在時退出 3，以及 crash 後刻意交人處理；〈八、退出碼〉另明寫子行程非零、signal、timeout 仍可令回合回 0，結果要讀 instruction 的 `exit` 檔。
- `core/inst/docs/handoff.md`〈彙整規則〉已寫出真正的 delivery 名稱規則：只收第一個副檔名起恰好為 `.json` 的 `<name>.json`，`name.part.json` 也會略過；對應判定就在 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`，正好解釋 p3 的多一個點為何 silent stall。
- `core/inst/docs/handoff.md`〈取件與釋放〉與 `core/inst/src/handoff.cpp` 的 `claim_instruction()`／`release_instruction()` 已寫出目前只有 batch claim／release、沒有 instruction-level program counter；`core/inst/tests/test_run_handoff.cpp` 的 `exec refuses an existing runi with status three` 與 `exec claims the complete input before validating or executing it` 已踩過 `.runi` 鎖與整批先取件的邊界。
- `core/inst/docs/exec.md`〈逾時與行程群組〉與 `core/inst/src/exec.cpp` 的 `setpgid()`、group `SIGTERM`／`SIGKILL`、`WIFSIGNALED` 分支已寫出 timeout 時如何管整個 process group；`docs/aos-folder.md`〈十二、留給實作決定的〉則寫明單次 parent 被訊號中止時，子行程自成 process group 的既有語意。
- `wf/workflows/common/gotchas.md`〈使用 aos〉已記過「`aos exec` 的退出碼不反映子行程成敗」；`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉有 0／1／2／3 的完整契約，可直接當 p3 crash matrix 的欄位對照。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉已實測直接寫 ready 會讓半份 JSON 被隔離，且同一 producer 用同一 PID 連投兩次會由第二次 rename 靜默覆蓋第一次；這是 p3／p4 下一輪測命名、同 target 重投前已有的基線。
- `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉已保留一個無效的背景 `kill -INT` harness，再改用前景 `timeout` 得到 exit 130、孤兒 child 完成、exit 缺失與 restart 3；同節也區分 `--loop` 的優雅回合邊界，能供 p3 修 harness 時核對訊號是否真的打中。
- `wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉已有 request、effect、result.temp 三個時間點乘上 SIGINT／SIGKILL 的六格輸出，並有 query-by-key 不重做與 blind retry 令 ledger 變兩筆的對照；〈`aos recover [WORLD]`〉已列 `--replay`、`--abandon`、`--adopt RECEIPT` 三類人工動作及「證據不足就停住」。
- `wf/workflows/workshop/background/reliability.md`〈Effect（外部效果／capture／invoke）〉、〈idempotency key（冪等鍵）〉、〈ledger（耐久帳本／歷史表）〉與〈`unknown`（無法判定外部效果）〉已把 request/key、done、unknown、resolve，以及 key 沒有 ledger 就不能跨 aggregate 去重的差別分開；這些是 p2 下一輪 transition 名稱的既有詞義，不是新資料模型。
- `wf/workflows/workshop/background/delivery-contract.md`〈Publish（發布／commit／bundle）〉、〈Deliver（投遞／enqueue／handoff）〉、〈correlation ID（串接編號／request ID）〉與〈receipt（收據／completion record）〉已區分原子發布、queue 投遞、只作串接的 ID、單次完成證據與長期 ledger，能避免 p1 再把「實作份數／呼叫點／commit／人工 rename」混成同一個數字。
- `wf/workflows/workshop/background/questions-deliver.md`〈沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？〉已列發布前、發布後未 aggregate、aggregate 後與重開後四個重叫時點；〈Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？〉已列五種預期輸出現場。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉與 `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉已明寫 rename 與 file fsync／directory fsync 是兩層承諾；本輪四位「沒測斷電」不需要重新查名詞，但仍沒有實測結果。
- `wf/workflows/workshop/records/agent-loop-architecture.md`〈R2 想法池（收攏成方向）／合併後的功能清單〉已整理 Publish、Deliver、Effect 的責任與既有痛點；〈其實是同一件事的／可以疊在一起的〉記有 Publish 作底座、Effect result／receipt 再交給 Deliver；這是 p1 下一輪三支私有原語可比對的既有分層紀錄。
- `docs/inst-directives.md`〈五、適用範圍〉只處理 instruction 欄位中的 `$ref`／`$env`／`$opt` 展開，沒有 Publish receipt、Effect unknown 或 recovery 契約；下一輪不應把這份文件誤當上述缺口已有答案。

### 3. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉已有「同目錄 temp、write-all、file fsync、atomic rename、directory fsync」及「已有 intent、缺可信結果就停在 unknown、不自動建立新 attempt」的完整文字基線。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()`／`fsync_directory()` 是可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync 實作；它遇到同內容既有 target 直接返回、不同內容則拒絕，正好提供 p2 可重入發布實驗的既有程式樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()` 已實測 effect 落盤後殺 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`，重跑 recover 也不增加 effect；精確涵蓋範圍與限制寫在同目錄 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉與〈明確未驗，不可外推〉。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()`，配上 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()` 與 recovery tests，已有「完整證據才 commit receipt、不完整證據維持 unknown」的三態判讀樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉與〈小原型該回答什麼〉已把「可唯一推導就補回；仍有兩種可能就不猜」及 effect 後殺 manager、重開不得重送的驗收寫成現成文字。
- `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()` 已有同目錄 `NamedTemporaryFile`、完整寫入、`os.replace` 與殘留 temp 清理的輕量版本；它沒有 fsync、no-replace 或 receipt，適合只拿來對照 p4 所稱的三行 helper 到底已涵蓋哪些動作。
- `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉與〈整個實例被強制終止〉已明寫 tool error 不代表外部副作用 rollback、整個 process 被殺時不保收尾；`agentloop/CONTROLLER.md`〈明確不負責〉又明列它不做持久化、Task queue 或副作用 recovery，可作 no-aos 對照的能力邊界資料，不能當成 crash recovery 實作。

### 4. 還是查不到的

- `wf/workflows/hackathon/records/core-scope.md`〈5. 仍然不知道的〉只確認第一個數字口徑不一；在 `docs/`、`wf/workflows/workshop/`、`wf/workflows/experiments/t5-agent-loop.md` 與四個兄弟專案中都沒有一份既定的「實作份數／靜態呼叫點／實際 commit／人工 rename」統一計數表，**這條沒有現成資料**。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉只有同一 producer 連投兩次的覆蓋證據；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也明列未涵蓋 multiwriter，因此兩個 producer 各投 1,000 個 ID 的遺失／重複／覆蓋數，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh` 只有 happy path；repo 的 crash 證據都在 `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉與〈7. reliability 題的補充實驗〉且都包含 aos 或另一套假 loop，沒有 no-aos 三行鏈承受同一組三刀後的重開結果，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md` 記錄 PTY wrapper 與 `aos` 一起被 `^C` 終止；`core/inst/tests/test_run_loop.cpp` 有 loop signal tests，`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉有 `timeout` 現場，但都不是「PTY 真送 `^C` 且 wrapper 存活、獨立取得 aos exit」的 harness，**這條沒有現成資料**。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉只有測試方法與選項；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也排除 power loss，故斷電後 file data／directory entry 是否仍在，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/dcap/README.md`〈唯一指令〉至〈給 agent 用〉與 `/mnt/c/code/mine/simple_tools/dcap/tool/README.md`〈失敗時會怎樣〉只有 scaffold CLI、模板與一般退出碼；`/mnt/c/code/mine/simple_tools/freepy/agentloop/CONTROLLER.md`〈明確不負責〉排除持久化與副作用 recovery，兩者都沒有 Publish receipt、Effect resolve 或多 producer delivery 可抄，**這條沒有現成資料**。

## 第 2 輪之後的資料包

### 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在 Effect response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit 的兩個窗口尚未測重複 resolve；本輪未測範圍寫在 `/tmp/aos-core-scope-p1-r2/round2/report-r2.md`。
- **p2（Armstrong persona）**卡在 target commit 後被 aggregate 取走，receipt 卻尚未 commit，只能人工 `adopt-consumed`；完整現場在 `/tmp/aos-p2-round2.kTrhIV/p2-agent-loop/round2/evidence/delivery-consumed-no-receipt.log`。
- **p3（Cantrill persona）**卡在第一個數仍把 runtime transaction 當成手寫實作份數，且私有 validator 尚未與 canonical parser 做逐案差異對照；來源 inventory、validator 行為與未測項都整理在 `/tmp/p3-core-scope-round2/ROUND2.md`。
- **p4（Thompson persona）**卡在 publish 成功但 receipt 未回傳、以及 consumer 刪除 target 後重試的兩個窗口，沒有 ledger 時尚不能唯一回答 `Already`、`Unknown` 或 `Conflict`；原型與未測項在 `/tmp/p4-round2/ROUND2.md`。

### 2. 上一輪給過的料，有沒有人真的用

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

### 3. repo 裡已經有答案的

- `core/inst/src/handoff.cpp` `aggregate_instructions()` 中「`rename(paths.temp, paths.base)` 成功 → `result.published = true` → `remove_accepted_deliveries()`」是 p2／p4 下一輪四個 kill point 的現行精確順序；這裡沒有 acknowledgment，只有發布後刪來源 delivery。
- `core/inst/docs/handoff.md`〈彙整規則〉與 `docs/roadmap.md`〈T3 — 彙整與發布：接出下一回合〉明寫「發布成功之後才刪投遞」，`core/inst/tests/test_handoff.cpp`〈handoff aggregates deliveries in filename order and flattens batches〉已有發布後 delivery 消失的可直接改造測例。
- `core/inst/docs/capi.md`〈讀取、寫入與執行〉明寫 C ABI 的 `aos_instruction_read_buffer()` 只接受單筆 instruction object、不接受 batch array；`core/inst/docs/capi.md`檔頭又明寫 C ABI 沒有 batch／handoff API，所以 p3 若要驗 Deliver 的 object／array 全契約，不能只呼叫這一支 C API。
- `core/inst/src/format.cpp` `read_all()` 才是 object／array 共用、失敗時整批不交付且回報 one-based `error_record` 的 canonical batch parser；`core/inst/tests/test_format_read.cpp`〈read_all accepts a single instruction object〉〈read_all accepts a formatted array〉〈read_all is atomic and reports a one-based record number〉已是 p3 可照抄的 conformance cases。
- `docs/inst-directives.md`〈六、擺在哪一層？〉與 `core/inst/docs/architecture.md`〈架構〉已定 `format` 是唯一懂 instruction schema 的分層，`resolve`、`handoff`、`exec` 不得重新解讀 schema；這是 p3 對照私有 validator 時的現成分層答案。
- `docs/aos-folder.md`〈十二、留給實作決定的〉子節〈仍然開著的〉已記殘存 `.bad`／`.runi` 清理的容量上限方向與「不能自動清掉 crash 現場」的衝突；可作 p2 的 12 個 transaction 目錄與 p4 孤兒 temp 保留政策的現成邊界資料。

### 4. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`、`_terminal()` 與 `recover()` 已把 receipt JSON、receipt-ready 與 terminal 分成三步；receipt 完整時 recover 只補後續 marker，不再執行 effect。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/test_p0.py` `test_recover_receipt_without_terminal_only_projects_terminal()` 正好是 p1 的 response／receipt 已 commit、done／terminal 未 commit 窗口；`test_invocation_id_table_cannot_escape_root()` 後段還已呼叫同一 invocation 的 `recover()` 驗重複恢復仍 terminal。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/README.md`〈由小到大：一次呼叫〉已寫出「完整 receipt 缺 terminal 時只補 terminal projection」與「dispatch intent 後不自動重跑」，可直接當 p1 兩個 transition 的文字對照。

### 5. 還是查不到的

- 在 `core/inst/`、`docs/`、`wf/workflows/experiments/t5-agent-loop.md`、`wf/workflows/workshop/records/` 與 `wf/workflows/workshop/background/` 中都沒有 consumer acknowledgment 的實作或「target commit → aggregate claim → delivery deletion → ack commit」故障矩陣，**這條沒有現成資料**。
- `core/inst/docs/capi.md`檔頭已明寫 C ABI 不提供 batch／handoff API，而 `core/inst/include/aos/inst.h` 也只有單筆 instruction handle；因此「不改 C++ 卻只用現有 C ABI 驗完 Deliver object／array 全契約」，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/agent-machine/`、`/mnt/c/code/mine/simple_tools/freepy/`、`/mnt/c/code/mine/simple_tools/dcap/` 與 `/mnt/c/code/mine/simple_tools/arc_agi_tweets/` 都沒有 aggregate 取件／刪件與 producer receipt 共享同一份耐久 acknowledgment 的實作，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/core-scope.md`〈第 2 輪紀錄〉〈第 2 輪評分與意見〉仍只能列出 1 份實作／9 個呼叫點／8 或 12 筆 transaction／4 個實作位置，repo 與四個兄弟專案都沒有一張既定的跨實驗統一計數表，**這條沒有現成資料**。
- `docs/aos-folder.md`〈十二、留給實作決定的〉只有殘存檔清理方向，`wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename…〉也只有測試方法；真實 power-cut、NFS、非 Linux no-replace 與孤兒 temp 容量數據，**這條沒有現成資料**。
