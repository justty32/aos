# 下一輪的資料包 — repo 裡已經有答案的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/in-repo.md)

上面那些卡點，本 repo 的文件、原始碼與既有實驗紀錄裡已經寫過的答案。

## 2. repo 裡已經有答案的

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
