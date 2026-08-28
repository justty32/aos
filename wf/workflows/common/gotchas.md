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

## core/inst 的交接協定（handoff）

> 以下四條是讀 `core/inst/src/handoff.cpp` 驗證過的缺陷，詳見
> [ideas/call-format/handoff-and-world](../ideas/call-format/handoff-and-world.md)。
> **後三條已於 M1 修掉**（各條末尾註明改法與對應 SPEC 條款），保留原文是為了讓再度撞到
> 同樣症狀的人知道它長什麼樣、以及現在靠哪一條條款擋住；第一條（`.runi` 不是鎖）**仍未修**。

- **`.runi` 不是一把鎖，兩支 `aos exec` 可能把同一回合跑兩次**：`claim_instruction` 是
  `lstat(runi)` → `read_file(base)` → `rename(base, runi)`。POSIX `rename()` **靜默覆蓋**
  目的檔（原子但**不互斥**），互斥全靠前面那個 `lstat`，是 check-then-act；而且 read
  在 rename **之前**，所以兩支同時進來會讀到同一份 `inst.json` 再各自 rename。要互斥得
  用 `link()`／`renameat2(RENAME_NOREPLACE)`／`open(O_CREAT|O_EXCL)`。

- **整個 `core/inst/src/` 沒有 `fsync`**：`rename` 只保證目錄項原子替換，不保證內容落地。
  崩潰後可能留下一個已改名、內容零長度的 `.runi`——而「`.runi` 保留現場」正是崩潰後的
  全部指望。正確順序是 寫檔 → `fsync(fd)` → `rename` → `fsync(dir_fd)`。
  **已修（M1）**：`handoff_fs` 的 `write_file`／`write_file_exclusive` 在 close 前 `fsync`，
  新增 `fsync_dir` 供每次 rename 後同步目錄項；`exec.cpp` 的 `exit` 檔、`capi_io.cpp` 的
  `write_file`、`run_init.cpp` 的 `version`／`turn` 一併補上。已知豁免兩處：子行程的
  stdout/stderr 重導向檔（內容是子行程寫的）與 `aos_instruction_write_fd`（fd 是呼叫者
  自己的，不代呼叫者落盤）。條款見 [SPEC §D-5](../../../docs/SPEC.md)。

- **彙整有崩潰窗口，同一批可能執行兩次**：`aggregate_instructions` 先 rename 發布
  `inst.json`，**之後**才 `remove_accepted_deliveries()`。在兩者之間崩潰、或 `unlink`
  失敗（只記 issue 就繼續），投遞會留在 inbox；等這批跑完、`.runi` 被 release 掉，下一圈
  aggregate 又看到同一批投遞並再發布一次。不需要 race，一次崩潰或一次 unlink 失敗就夠。
  **已修（M1）**：發布順序改成先 rename header sidecar 當**提交點**、再 rename 批，
  下一圈先拿本輪投遞的批 id（FNV-1a 摘要）比對現任 header——對得上就不重發（批 `.temp`
  還完整躺著就 roll forward）。**覆蓋範圍照實**：只保證「同名同內容、恰好整組」的殘留；
  部分 unlink 失敗的殘留混進新投遞後仍可能重複。條款見
  [SPEC §D-5／§D-6](../../../docs/SPEC.md)。

- **投遞檔名用 pid 不保證唯一**：pid 會回收、會 wrap，跨 namespace／容器會撞。它要解決
  的「共用檔名互相蓋寫」是結構性問題，pid 只給統計上的保證。
  **已修（M1）**：`aos deliver` 的投遞名是 `<pid>-<seq>`（`seq` 為行程內 atomic 單調
  計數），發布走排他 rename（`renameat2(RENAME_NOREPLACE)`，檔案系統不支援時退階
  `link`＋`unlink`），撞名就換序號重試、**絕不覆蓋**——pid 重用由排他發布兜底。
  條款見 [SPEC §D-2](../../../docs/SPEC.md)。

## 使用 aos

- **`aos exec` 的退出碼不反映子行程成敗**：`/bin/false` 回 1，但正常完成該回合的 `aos exec` 回 **0**；`.runi` 已存在則回 3。
  指令不存在、逾時被砍、重導向的檔開不起來也都回 0。要判斷子行程的結果得讀 `exit`
  欄位寫出的那個檔。詳見 [`docs/usage.md`](../../../docs/usage.md)。

## 改文件

- **批次改文件用非貪婪正則可能吃掉整段**：`.*?` 配上 `re.DOTALL`，如果終止字串在檔案
  更後面又出現一次，會從起點一路吃到那裡。這個坑真的發生過——`code-map.md` 被砍掉
  130 行還 commit 進去了，因為當時只 `grep` 關鍵字確認「殘留清乾淨」，沒看檔案剩幾行。
  **批次改完一定要看行數與章節數**，`grep` 只能證明某段不在，不能證明別的還在。

- **`\b` 邊界在 `-Iinst/include` 這種字串上不成立**：`inst` 前面是 `I`（word 字元），
  所以 `\binst/` 匹配不到。批次替換路徑之後，`grep` 一次確認沒有漏網的。
