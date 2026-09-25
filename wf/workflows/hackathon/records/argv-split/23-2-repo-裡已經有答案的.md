← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 23/29）｜所在：下一輪的資料包｜[上一份](22-下一輪的資料包.md)｜[下一份](24-給-p2refenvopt-的往.md)

### 2. repo 裡已經有答案的

#### 給「乙在今天的二進位上不可表達」——規格自己已經寫出這件事的根因

- **規格自陳「世界」沒有抽象，而那正好是乙缺的入口**：`docs/aos-folder.md`〈十二、留給實作決定的／仍然開著的〉最後一條——「**『世界』本身沒有抽象。** 彙整那三支是以 instruction 檔路徑為參數的（所以已經能對 `insts/llm.json` 用），但『`.aos` 在不在』『`version` 認不認得』『`chdir` 到哪』三件事**寫死在 `aos exec` 的實作裡**」。這三句就是四位撞到的那道牆的規格層描述。
- **`chdir` 這件事也已經被寫成決定**：同檔〈十二／已經被實作決定的〉——「**一支 `aos exec` 一次只推進一個世界。** 實作是用 `chdir` 到 `<folder>` 來達成第四節那個『一律以 `<folder>` 為基準』，而 cwd 是整個行程共用的。要同時看多個資料夾就得改成到處傳基準路徑，或是一個世界一支行程」。p2 情境 2 與 p4 的 `B/.cpu/e1.txt` 是這一段的實測後果。
- **原始碼裡的那一段**：`core/inst/src/run_exec.cpp` 第 95–135 行——`chdir` 進 world、`stat .aos`、開讀 `.aos/version` 比對 `"1\n"`，之後才進交接。這三步就是「寫死在 `aos exec` 裡」的那三件事。
- **回合順序**：同檔 `run_exec.cpp` 第 137–176 行——`aggregate_instructions`（137）→ `claim_instruction`（150，`Busy` 直接 `return 3`）→ `execute_batch`（171）→ `release_instruction`（173）。`--loop` 的停止條件在 `core/inst/src/run_loop.cpp` 第 64–82 行（`if (result == 3) return 3;`）。
- **彙整那三支「應該與 `aos exec` 解耦」是規格已經寫下的意圖**：`docs/aos-folder.md`〈六、交接協定／彙整跑在哪裡〉——「它應該是一個**以 instruction 檔路徑為參數的獨立單元**，`aos exec` 只是它的第一個呼叫者，不是它的擁有者」。
- **同一件事在別場已經被獨立撞到過**：`wf/workflows/experiments/t5-agent-loop/record.md`〈4. Ctrl-C、`.runi` 與「續跑」〉、〈規格與實作對不上的地方〉；以及 `docs/roadmap/stages.md`〈T5 — agent loop〉底下那個 ⚠ 區塊，明寫 T5 驗收的「中途 `Ctrl-C` 之後再 `aos exec` 一次能從斷點繼續」與 `docs/roadmap/decisions.md`〈D6 — `.runi` 存在時代表什麼？〉互相矛盾，兩條路擇一、**「在拍板之前，不要照這條驗收去實作」**。

#### 給 p1：aggregate race、`inst.json.temp` 交錯寫入、修 vs 外放

- **race 的機制在原始碼裡逐行對得上**：`core/inst/src/handoff.cpp` 的 `aggregate_instructions()`（第 49 行起）——守衛只有 `lstat(paths.base)`（第 57 行一帶，看的是 `inst.json` 在不在，**完全不看 `.runi`**）；`opendir` 收件匣、`read_file` 每份投遞進記憶體、`std::sort` 檔名字典序；`write_file(paths.temp, ...)` → `rename(paths.temp, paths.base)`；**`remove_accepted_deliveries()` 排在 `rename` 之後**（第 143 行一帶，函式本體在第 37 行）。
- **固定檔名與非原子寫入，兩處都在檔案裡**：`core/inst/src/handoff_fs.cpp` 的 `derive_paths()`（第 34 行）——`paths.temp = base + ".temp"`、`paths.runi = base + ".runi"`，**兩個名字都不帶 pid、不帶批次身分**；同檔 `write_file()`（第 73 行）用的是 `O_WRONLY | O_CREAT | O_TRUNC`（**不是 `O_EXCL`**）加一個 `while` 迴圈分段 `write`——兩個彙整者同時走這一段就是交錯寫入。
- **規格自己在同一節替投遞規定了相反的規則**：`docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉的三步表——投遞那一列寫著「檔名帶 pid，因為 `rename` 原子但**寫入不是**，共用檔名會互相蓋寫」，而彙整那一列給的是固定的 `inst.json.temp`。**這是同一張表裡的兩列。**
- **規格裡那句「所以不會重複執行」**：`docs/aos-folder.md`〈十二／仍然開著的〉——「`.runi` 的檢查與 `rename` 之間有 TOCTOU……第二支的 `rename` 會因為 `inst.json` 已被搬走而失敗，**所以不會重複執行**，只是退出碼與訊息不精確。要真的原子化得用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`。」評委判定這句話今天是假的；**修法的兩個候選就寫在同一句裡**。
- **「修」那一格的現成參考**：`core/inst/src/run_init.cpp` 第 77 行已經在同一個 repo 裡用了 `O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC`——`O_EXCL` 不是新東西，`aos init` 就在用。
- **同一個坑別人踩過的現場**：`wf/workflows/hackathon/records/core-scope/verdicts/round-2.md`〈路線判斷〉記了雙 producer 同名競爭「第一次 race 死在 `mkdir` TOCTOU」與「後寫者無聲覆蓋」兩種結果；`wf/workflows/workshop/background/delivery-contract.md`〈TOCTOU（先檢查、後使用的競爭窗）〉把兩次現場與現況（「現行正式契約尚未補上通用解法」）寫成一條。
- **現行「發布後直接刪 delivery、沒有 ack」已被獨立記成缺口**：`wf/workflows/workshop/background/delivery-contract.md`〈consumer acknowledgment（收件者確認）〉——「現行 `core/inst/src/handoff.cpp` 發布彙整結果後只刪 delivery，沒有 ack」；完整推導與四刀殺法在 `wf/workflows/hackathon/records/core-scope/rounds/round-3.md`〈2. 坑的總表〉與〈4. 三個數字〉，路線判斷在 `core-scope/verdicts/round-3.md`〈路線判斷〉。
- **`aggregate` 在退出碼 3 之下照樣搬空 inbox，已經有完整現場**：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／一、退出碼 3 的「拒絕啟動」不是 no-op——它會先把 inbox 搬空〉，貼了 `.aos/inst.json` 憑空出現、`.aos/inst.tempd` 投遞不見了的前後對照。
