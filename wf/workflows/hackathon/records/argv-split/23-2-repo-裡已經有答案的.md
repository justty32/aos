← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 23/29）｜所在：下一輪的資料包｜[上一份](22-下一輪的資料包.md)｜[下一份](24-給-p2refenvopt-的往.md)

### 2. repo 裡已經有答案的

#### 給「乙在今天的二進位上不可表達」——規格自己已經寫出根因

- `docs/aos-folder.md`〈十二、留給實作決定的／仍然開著的〉最後一條：「**『世界』本身沒有抽象。**」——「`.aos` 在不在」「`version` 認不認得」「`chdir` 到哪」三件事寫死在 `aos exec` 的實作裡。
- 同檔〈十二／已經被實作決定的〉：「**一支 `aos exec` 一次只推進一個世界。**」用 `chdir` 到 `<folder>` 達成第四節的基準，cwd 是整個行程共用的。影子世界打壞路徑基準是它的實測後果。
- 原始碼：`core/inst/src/run_exec.cpp` 第 95–135 行（`chdir`、`stat .aos`、比對 `.aos/version` 的 `"1\n"`）。
- 回合順序：`run_exec.cpp` 第 137–176 行——`aggregate_instructions`（137）→ `claim_instruction`（150，`Busy` 直接 `return 3`）→ `execute_batch`（171）→ `release_instruction`（173）。`--loop` 停止條件在 `core/inst/src/run_loop.cpp` 第 64–82 行（`if (result == 3) return 3;`）。
- 彙整應與 `aos exec` 解耦是規格寫下的意圖：`docs/aos-folder.md`〈六、交接協定／彙整跑在哪裡〉——「它應該是一個**以 instruction 檔路徑為參數的獨立單元**，`aos exec` 只是它的第一個呼叫者，不是它的擁有者」。
- 別場撞過同一件事：`wf/workflows/experiments/t5-agent-loop/record.md`〈4. Ctrl-C、`.runi` 與「續跑」〉、〈規格與實作對不上的地方〉；`docs/roadmap/stages.md`〈T5 — agent loop〉的 ⚠ 區塊（T5 驗收「中途 `Ctrl-C` 後再跑能續」與 `docs/roadmap/decisions.md`〈D6 — `.runi` 存在時代表什麼？〉矛盾，「**在拍板之前，不要照這條驗收去實作**」）。

#### 給 p1：aggregate race、`inst.json.temp` 交錯寫入、修 vs 外放

- race 機制：`core/inst/src/handoff.cpp` 的 `aggregate_instructions()`（第 49 行起）——守衛只有 `lstat(paths.base)`（第 57 行一帶，不看 `.runi`）；讀投遞進記憶體、字典序；`write_file(paths.temp, ...)` → `rename`；**`remove_accepted_deliveries()` 在 `rename` 之後**（第 143 行一帶，本體第 37 行）。
- 固定檔名與非原子寫入：`core/inst/src/handoff_fs.cpp` 的 `derive_paths()`（第 34 行）——`paths.temp = base + ".temp"`、`paths.runi = base + ".runi"`，不帶 pid、不帶批次身分；同檔 `write_file()`（第 73 行）用 `O_WRONLY | O_CREAT | O_TRUNC`（不是 `O_EXCL`）分段 `write`。
- 規格同一張表的兩列互相矛盾：`docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉——投遞「檔名帶 pid，因為 `rename` 原子但**寫入不是**」，彙整卻是固定 `inst.json.temp`。
- 「所以不會重複執行」那句在 `docs/aos-folder.md`〈十二／仍然開著的〉，今天是假的；修法的兩個候選（`renameat2(RENAME_NOREPLACE)`、`link`＋`unlink`）寫在同一句。
- `O_EXCL` 的現成用例：`core/inst/src/run_init.cpp` 第 77 行 `O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC`。
- 同類坑的別場現場：`wf/workflows/hackathon/records/core-scope/verdicts/round-2.md`〈路線判斷〉（雙 producer 同名競爭）；`wf/workflows/workshop/background/delivery-contract.md`〈TOCTOU（先檢查、後使用的競爭窗）〉。
- 「發布後直接刪 delivery、沒有 ack」已記成缺口：`delivery-contract.md`〈consumer acknowledgment（收件者確認）〉；推導在 `core-scope/rounds/round-3.md`〈2. 坑的總表〉〈4. 三個數字〉，路線判斷在 `core-scope/verdicts/round-3.md`〈路線判斷〉。
- 退出碼 3 之下 aggregate 照樣搬空 inbox 的現場：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／一、退出碼 3 的「拒絕啟動」不是 no-op——它會先把 inbox 搬空〉。
