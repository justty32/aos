# 共通踩坑（跨工作流）

← [INDEX](../../INDEX.md)

不專屬任一工作流、任何人都可能撞到的坑，記/查這裡。某工作流專屬的坑記在該工作流自己的 `gotchas.md`（長出來後在下表加一列導流）。

## 哪類坑記哪裡

| 坑的性質 | 記/查這裡 |
|---------|----------|
| 不專屬任一工作流的共通坑 | **common/gotchas**（本檔）|
| 從 Windows 驅動 WSL、複製場地、跑 codex 開黑客松 | [hackathon/gotchas](../hackathon/gotchas.md) |

---

## 建置與相依

- **私有相依會偷偷變成使用者的義務**：`target_link_libraries(x PRIVATE dep)` 會在
  `INTERFACE_LINK_LIBRARIES` 留下 `$<LINK_ONLY:dep>`，匯出之後使用者的
  `find_package(aos)` 就得先找得到 `dep`——即使它是 header-only、即使符號全被
  hidden 蓋掉。`aos_add_subproject()` 已經會把它剝掉；**自己手寫 target 時要記得**。
  症狀是使用者在沒有 vcpkg 的環境 configure 直接失敗。

- **外部消費測試沒有 `env -u VCPKG_ROOT` 等於白測**：有 vcpkg 在的話，本來會失敗的
  相依問題會被它悄悄補上，問題留到使用者手上才爆。上面那個坑就是這樣被漏掉的。

- **公開標頭漏標 `AOS_API` 不會在編譯期爆**：編譯過、`#include` 也過，連結時才找不到
  符號——而且通常是**外部使用者先撞到**，自己在 repo 裡跑測試不一定會發現（測試若連的是
  OBJECT library 就繞過了可見度）。

- **`aos_add_subproject()` 的 `EXPORT_NAME` 不能省**：不設的話匯出後外部看到的是
  `aos::aos_inst` 而不是 `aos::inst`，而且 `find_package` 那一步不會報錯，錯誤延到
  `target_link_libraries` 才說「target not found」。

## core/loop 的投遞與回合

- **`aos deliver <file.json>` 撞名直接覆蓋，不查重**（2026-09-01 實測）：這條路的 id 取
  **檔名 stem**（`core/loop/src/deliver_cli.cpp:49`），而 `deliver()` 只是 `write_atomic`
  到 `inbox/<id>.json`（`core/loop/src/deliver.cpp:16`），不檢查檔案在不在。同一個檔名連
  投兩次、或兩個目錄下同名的 `job.json`，**前一份還沒被跑掉就沒了**——`aos deliver` 回
  exit 0，沒有任何警告。`aos deliver -- <argv...>` 那條不受影響，它的 id 是
  `make_delivery_id()` 產的 `d-<epoch_ms>-<pid>-<seq>`。要保證不掉件就自己給獨一無二的
  檔名，或改用 `--` 那條。

- **`core/loop` 全程沒有 `fsync`**：唯一的寫檔入口 `fs::write_atomic()`
  （`core/loop/src/fs.cpp:42`）是 `ofstream` → `close` → `std::rename`——`rename` 只保證
  目錄項原子替換，不保證內容落地。斷電後可能留下已改名、內容零長度的 `state.json` 或
  `turn`。正確順序是 寫檔 → `fsync(fd)` → `rename` → `fsync(dir_fd)`。`core/tick` 同一
  個毛病。

## core/inst 的交接協定（handoff）——**已作廢，留作歷史**

> **2026-09-01：`core/inst/` 已不存在**（改名成 `core/exec`，回合機另立 `core/loop`），
> 以下三條指的程式碼都沒了。`.runi` 沒了（取件改成 rename 進 `batch/<turn>/insts/`，
> 互斥靠 `.aos/run.lock` 的 `flock`）、彙整窗口翻面成「漏跑」而非「跑兩次」、投遞 id 已
> 改成 `d-<epoch_ms>-<pid>-<seq>`；**只有沒 `fsync` 這條搬家後仍然成立**（見上一節）。
> 逐條的結案理由在 [ideas/verdicts D 區](../ideas/verdicts.md)。
>
> 原文（讀 `core/inst/src/handoff.cpp` 驗證過的當時現況）保留在下面，設計脈絡見
> [ideas/call-format/handoff-and-world](../ideas/call-format/handoff-and-world.md)。

- **`.runi` 不是一把鎖，兩支 `aos exec` 可能把同一回合跑兩次**：`claim_instruction` 是
  `lstat(runi)` → `read_file(base)` → `rename(base, runi)`。POSIX `rename()` **靜默覆蓋**
  目的檔（原子但**不互斥**），互斥全靠前面那個 `lstat`，是 check-then-act；而且 read
  在 rename **之前**，所以兩支同時進來會讀到同一份 `inst.json` 再各自 rename。要互斥得
  用 `link()`／`renameat2(RENAME_NOREPLACE)`／`open(O_CREAT|O_EXCL)`。

- **整個 `core/inst/src/` 沒有 `fsync`**：`rename` 只保證目錄項原子替換，不保證內容落地。
  崩潰後可能留下一個已改名、內容零長度的 `.runi`——而「`.runi` 保留現場」正是崩潰後的
  全部指望。正確順序是 寫檔 → `fsync(fd)` → `rename` → `fsync(dir_fd)`。

- **彙整有崩潰窗口，同一批可能執行兩次**：`aggregate_instructions` 先 rename 發布
  `inst.json`，**之後**才 `remove_accepted_deliveries()`。在兩者之間崩潰、或 `unlink`
  失敗（只記 issue 就繼續），投遞會留在 inbox；等這批跑完、`.runi` 被 release 掉，下一圈
  aggregate 又看到同一批投遞並再發布一次。不需要 race，一次崩潰或一次 unlink 失敗就夠。

- **投遞檔名用 pid 不保證唯一**：pid 會回收、會 wrap，跨 namespace／容器會撞。它要解決
  的「共用檔名互相蓋寫」是結構性問題，pid 只給統計上的保證。

## 使用 aos

- ~~**`aos exec` 的退出碼不反映子行程成敗**~~ — **2026-09-01 作廢：沒有 `aos exec` 這支
  子命令了**（`core/exec` 只當函式庫用，`aos --help` 印不出 `exec`）。現在的對應規則是
  **`aos run` 會反映**：任一條 inst 非零 exit／被 signal 中止就回 1（exit 75 當
  `waiting-llm` 回壓、不算失敗），逐條細節照樣讀 `.aos/batch/<turn>/out/<id>.json`。

## 改文件

- **批次改文件用非貪婪正則可能吃掉整段**：`.*?` 配上 `re.DOTALL`，如果終止字串在檔案
  更後面又出現一次，會從起點一路吃到那裡。這個坑真的發生過——`code-map.md` 被砍掉
  130 行還 commit 進去了，因為當時只 `grep` 關鍵字確認「殘留清乾淨」，沒看檔案剩幾行。
  **批次改完一定要看行數與章節數**，`grep` 只能證明某段不在，不能證明別的還在。

- **`\b` 邊界在 `-Iinst/include` 這種字串上不成立**：`inst` 前面是 `I`（word 字元），
  所以 `\binst/` 匹配不到。批次替換路徑之後，`grep` 一次確認沒有漏網的。
