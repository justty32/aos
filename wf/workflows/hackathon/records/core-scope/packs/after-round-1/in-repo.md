# 下一輪的資料包 — repo 裡已經有答案的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/in-repo.md)

## 2. repo 裡已經有答案的

- `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉：`.temp`／ready／`.runi` 的可見邊界、`.runi` 只代表一回合沒跑完、存在時退出 3、crash 後刻意交人處理。〈八、退出碼〉：子行程非零、signal、timeout 仍可令回合回 0，結果要讀 instruction 的 `exit` 檔。
- `core/inst/docs/handoff.md`〈彙整規則〉＋ `core/inst/src/handoff.cpp` `is_delivery_name()`：只收第一個副檔名起恰好為 `.json` 的 `<name>.json`，`name.part.json` 也略過（錯名 silent stall 的原因）。
- `core/inst/docs/handoff.md`〈取件與釋放〉＋ `claim_instruction()`／`release_instruction()`：只有 batch claim／release，沒有 instruction-level program counter；`core/inst/tests/test_run_handoff.cpp` 的 `exec refuses an existing runi with status three`、`exec claims the complete input before validating or executing it`。
- `core/inst/docs/exec.md`〈逾時與行程群組〉＋ `core/inst/src/exec.cpp` 的 `setpgid()`、group `SIGTERM`／`SIGKILL`：timeout 時管整個 process group；`docs/aos-folder.md`〈十二、留給實作決定的〉：parent 被訊號中止時子行程自成 process group。
- `wf/workflows/common/gotchas.md`〈使用 aos〉：`aos exec` 的退出碼不反映子行程成敗；`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉：0／1／2／3 契約。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉：直接寫 ready 會讓半份 JSON 被隔離；同一 producer 用同一 PID 連投兩次，第二次 rename 靜默覆蓋第一次。
- 同檔〈4. Ctrl-C、`.runi` 與「續跑」〉：背景 `kill -INT` 無效、前景 `timeout` 得到 exit 130、孤兒 child 完成、exit 缺失與 restart 3；`--loop` 的優雅回合邊界。
- 同檔〈7. reliability 題的補充實驗〉：request、effect、result.temp 三時點 × SIGINT／SIGKILL 六格；query-by-key 不重做、blind retry 令 ledger 變兩筆；〈`aos recover [WORLD]`〉：`--replay`、`--abandon`、`--adopt RECEIPT` 與「證據不足就停住」。
- `wf/workflows/workshop/background/reliability.md`〈Effect〉〈idempotency key（冪等鍵）〉〈ledger（耐久帳本／歷史表）〉〈`unknown`（無法判定外部效果）〉：request／key、done、unknown、resolve 的詞義；key 沒有 ledger 就不能跨 aggregate 去重。
- `wf/workflows/workshop/background/delivery-contract.md`〈Publish（發布／commit／bundle）〉〈Deliver（投遞／enqueue／handoff）〉〈correlation ID（串接編號／request ID）〉〈receipt（收據／completion record）〉：原子發布、queue 投遞、只作串接的 ID、單次完成證據與長期 ledger 的分別。
- `wf/workflows/workshop/background/questions-deliver.md`〈沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？〉：發布前、發布後未 aggregate、aggregate 後、重開後四個重叫時點；〈Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？〉：五種預期輸出現場。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉＋ `reliability.md`〈visibility atomicity 與 power-loss durability〉：rename 與 file／directory fsync 是兩層承諾。
- `wf/workflows/workshop/records/agent-loop-architecture.md`〈R2 想法池（收攏成方向）／合併後的功能清單〉〈其實是同一件事的／可以疊在一起的〉：Publish、Deliver、Effect 的責任與分層。
- `docs/inst-directives.md`〈五、適用範圍〉只處理 `$ref`／`$env`／`$opt` 展開，不涵蓋 Publish receipt、Effect unknown 或 recovery。
