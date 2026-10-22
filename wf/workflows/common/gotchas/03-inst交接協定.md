← [入口](../gotchas.md)｜涵蓋：core/inst 的交接協定（handoff）——**已作廢，留作歷史**

## core/inst 的交接協定（handoff）——**已作廢，留作歷史**

> **2026-09-01：`core/inst/` 已不存在**（改名成 `core/exec`，回合機另立 `core/loop`），
> 以下三條指的程式碼都沒了。`.runi` 沒了（取件改成 rename 進 `batch/<turn>/insts/`，
> 互斥靠 `.aos/run.lock` 的 `flock`）、彙整窗口翻面成「漏跑」而非「跑兩次」、投遞 id 已
> 改成 `d-<epoch_ms>-<pid>-<seq>`；**只有沒 `fsync` 這條搬家後仍然成立**（見上一節）。
> 逐條的結案理由在 ideas/verdicts D 區。
>
> 原文（讀 `core/inst/src/handoff.cpp` 驗證過的當時現況）保留在下面，設計脈絡見
> ideas/call-format/handoff-and-world。

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
