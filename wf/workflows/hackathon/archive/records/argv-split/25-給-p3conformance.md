← [把「exec 只當純 CPU、其餘全外放成 argv」真的做出來，去打研討會的三個主張](../argv-split.md)（分檔 25/29）｜所在：下一輪的資料包 ＞ 2. repo 裡已經有答案的｜[上一份](24-給-p2refenvopt-的往.md)｜[下一份](26-給-p4分母丙的可交付門檻租約影.md)

#### 給 p3：conformance 套件的測項、`lstat(.runi)` 守衛、差分測試

- F 打到的條文：`docs/aos-folder.md`〈六、交接協定〉「**`.runi` 存在 ⟺ 有一回合沒跑完。**」與「**`.runi` 已存在時拒絕啟動**（退出碼 3）……也不會有兩支 `aos exec` 同時跑同一個資料夾」；決策版 `docs/roadmap/decisions.md`〈D6 — `.runi` 存在時代表什麼？　**已定：拒絕啟動**〉。
- A1 的守衛位置：`core/inst/src/handoff.cpp` 第 57 行一帶的 `lstat(paths.base)` 旁邊加 `lstat(paths.runi)`；`paths.runi` 已在 `derive_paths()`（`handoff_fs.cpp` 第 34 行）的同一個 struct 裡，不需新參數。
- A3 的真模型版本：`wf/workflows/hackathon/records/agent-loop.md`〈規格級的發現／一〉與〈二、`.runi` ＋ `mv` 的恢復路徑會靜默吃掉一份已經完成的產出〉。
- `aos recover` 介面草稿：`wf/workflows/experiments/t5-agent-loop/subcommand-specs.md`〈`aos recover [WORLD]`〉——先唯讀列證據，動作分 `--replay`／`--abandon`／`--adopt RECEIPT`，「**沒有足夠證據時預設必須停住，而不是自動重播**」。
- A4 對到的條文：`docs/aos-folder.md`〈八、退出碼〉（`3 = 拒絕啟動：.runi 已存在`）與〈十二／已經被實作決定的〉「**只有退出碼 3（`.runi` 已存在）會讓迴圈退出**」；決策版 `docs/roadmap/decisions.md`〈D10 — 回合的退出碼怎麼算？〉；`wf/workflows/common/gotchas.md`〈使用 aos〉記了「`aos exec` 的退出碼不反映子行程成敗」。
- 缺口所在：`core/inst/tests/test_run_handoff.cpp` 的 `"exec leaves deliveries pending while inst.json already exists"`（第 78 行）測的是 `inst.json` 存在不是 `.runi` 存在；`"exec refuses an existing runi with status three"`（第 97 行）。「`.runi` 存在時 inbox 不得被消耗」就在兩者之間。
- 差分測試的 canonical parser：`core/inst/tests/test_format_read.cpp` 第 25／48／66／83／107 行五個 `read_all` 測試；宣告在 `core/inst/include/aos/inst.hpp`，文件 `core/inst/docs/cxxapi.md`〈函式〉。
- FFI 現況：`core/inst/include/aos/inst.h` 的公開 C ABI 只有單筆 instruction 的讀寫與 `execute`，**沒有 `read_all`、沒有任何 handoff 入口**（`core/inst/docs/capi.md`〈讀取、寫入與執行〉）。mangled 符號那條路有人走通過、標為「證據 shim，不是產品 FFI」：`wf/workflows/hackathon/records/deliver-contract.md`〈第 2 輪紀錄／1. 各人做了什麼〉Hickey persona 段與〈第 2 輪紀錄／3. 好處／壞處／壞處〉（依賴 `libstdc++ vector layout = 24 bytes`、`sizeof(aos::inst_t) = 280`）；C ABI batch 缺口另見同檔〈第 2 輪／5. 仍然不知道的〉與 `core-scope/rounds/round-3.md`〈6. 仍然不知道的〉。
