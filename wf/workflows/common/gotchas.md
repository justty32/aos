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
> 同樣症狀的人知道它長什麼樣、以及現在靠哪一條條款擋住；第一條（`.runi` 不是鎖）**仍未修**，
> 但它造成重複執行的那一半已經被 M1 審查修補的**排他發布**關掉（見該條末尾）。
> 2026-08-28 的 M1 審查（[report](../build-cycle/archive/m1-loop-side/review/report.md)）
> 又在這一層挖出一批，修掉的收在本節末尾「M1 審查修補」那一條。

- **`.runi` 不是一把鎖，兩支 `aos exec` 可能把同一回合跑兩次**：`claim_instruction` 是
  `lstat(runi)` → `read_file(base)` → `rename(base, runi)`。POSIX `rename()` **靜默覆蓋**
  目的檔（原子但**不互斥**），互斥全靠前面那個 `lstat`，是 check-then-act；而且 read
  在 rename **之前**，所以兩支同時進來會讀到同一份 `inst.json` 再各自 rename。要互斥得
  用 `link()`／`renameat2(RENAME_NOREPLACE)`／`open(O_CREAT|O_EXCL)`。
  **射程已切半（M1 審查修補）**：實測到的重複執行，主因其實不是取件的 TOCTOU，而是
  **兩個彙整者各自發布了一次**（後者在前者寫出 header 之前讀 header，§D-6 的去重比對
  本來就不可能命中）。那一半由**排他發布**（§D-5）**加上發布前的來源查核**（§D-4）
  關掉——**只有排他發布是不夠的**：它只在勝出者那份批還沒被取走時有效，取件把
  `inst.json` 換成 `.runi` 之後槽位就空了，慢半拍的彙整者照樣發布得成。
  （修補期間實測到的反直覺結果：把 #1 的 `swept` 閘門修好之後，原本靠**陳舊 header**
  意外擋住的這條路暴露出來，重複執行率反而由 8.7% 升到 35%；補上來源查核才回到 0–1%。
  **「修好一個 bug 讓另一個 bug 現形」——那個舊行為從來不是保護，只是巧合。**）
  **剩下的 0–1%** 才是這條本體：兩支 exec 在同一瞬間都看到沒有 `.runi`、各自 rename，
  以及來源查核與 rename 之間那幾個 syscall——窗口窄得多，排 M2／M3。

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
  **M1 審查修補再補一刀**：上面那個 header 比對原本**永不失效**，於是「同名同內容的
  全新投遞」會被誤判成殘留而靜默刪除（審查 #1，rc=0、零輸出）。現在 header 多一欄
  `swept`，投遞清乾淨並落盤之後標 `true`，**只有未 swept 的 header 才擋**（§C-8／§D-6）。

- **投遞檔名用 pid 不保證唯一**：pid 會回收、會 wrap，跨 namespace／容器會撞。它要解決
  的「共用檔名互相蓋寫」是結構性問題，pid 只給統計上的保證。
  **已修（M1）**：`aos deliver` 的投遞名是 `<pid>-<seq>`（`seq` 為行程內 atomic 單調
  計數），發布走排他 rename（`renameat2(RENAME_NOREPLACE)`，檔案系統不支援時退階
  `link`＋`unlink`），撞名就換序號重試、**絕不覆蓋**——pid 重用由排他發布兜底。
  條款見 [SPEC §D-2](../../../docs/SPEC.md)。

- **M1 審查修補一次修掉的其餘幾條**（2026-08-28，症狀導向速查；細節看
  [report](../build-cycle/archive/m1-loop-side/review/report.md) 的對應編號）：
  - **收件匣裡放一個 FIFO 就讓整台機器永久卡死**（#3）：`open()` 對沒有寫端的 FIFO
    會無限阻塞，而且發生在取件之前——鎖沒拿到、stderr 一個字都沒有、後續 `aos exec`
    一個個疊上去一起卡。現在讀投遞之前先 `stat` 驗 `S_ISREG`，非普通檔**跳過＋出聲**，
    不隔離（它不是「內容無效」）。
  - **`.aos/inst.json` 是斷掉的 symlink → rc=0、stderr 全空、投遞無限堆積**（#25）：
    彙整用 `lstat`（成功）、取件用 `open`（ENOENT），兩層對「存在」的定義不一致，
    夾出一個規格沒定義的第三態。現在取件拿到 ENOENT 會先 `lstat`，存在但讀不到就回
    `InstructionReadFailed`（rc=1）。
  - **合法但一時讀不到的投遞被貼 `.bad` 永久出局**（#8）：一次暫時性的 EACCES／EIO
    就把有效工作踢出佇列。`.bad` 的定義是「**內容**無效」（§B-1），所以讀取失敗現在
    只記 issue、**留在原地**下一輪再試（ENOENT 靜默跳過）。
  - **第二份同名壞投遞把第一份 `.bad` 的證據無聲蓋掉**（#7）：隔離改走排他 rename，
    撞名就換成符合 §B-1 的唯一名（`x-<pid>-<seq>.json.bad`）。覆寫等同刪除，違反 §D-8。
  - **檔名含第二個點的投遞被永久靜默忽略**（#10）：`a.b.json`、`2026-08-28.report.json`
    這種第三方生產者很自然會產的名字，既不收也不隔離也不警告。收的集合**沒有改**
    （避免行為漂移），但現在會出聲。
  - **去重命中時，一份與這批毫無關係的 `.temp` 殘骸會被扶正並執行**（#21）：
    roll-forward 以前只檢查「解析得出非空批次」。現在**逐位元**比對本輪重算的 canonical
    位元組，而且錨**靠內容認身分、不靠檔名**（§D-6）。
  - **header 寫失敗 ＋ 投遞刪失敗同時發生 → 同一批每回合重跑，永無止境**（#26）：
    兩個「各自可容忍」的降級疊在一起就變成無上限的副作用重播（成因高度相關：同一個
    唯讀／異常的 `.aos`）。同輪同時出現這兩個 issue 現在升級為致命（回非 `Ok`、rc=1）。
  - **`decode_header_id` 會先吃到巢狀物件裡的 `"id"`**（#4）：M2 要把 `result` 填成
    含 `id` 的物件就會拿錯 id 比對。改成只認**頂層**的 key。
  - **取件與釋放沒有耐久性**（#2／#5）：`rename(→.runi)` 與 `unlink(.runi)` 之後都沒有
    目錄 fsync；釋放那邊只是「剛好」被 `advance_turn` 的 `fsync(.aos)` 順帶救到，而
    §B-3 說 turn 在 M2 要搬到 loop 層——**搬走這個巧合就沒了**。兩處都補上（§D-5 的
    射程從「彙整」延伸到「交接」）。
  - **`publish_exclusive` 的 `link+unlink` 退路謊報失敗**（#11）：`link` 成功、收尾
    `unlink` 失敗時回報整體失敗，但目的檔**已經在收件匣裡了**——生產者照著重投就真的
    多一份。改成回成功＋把 errno 放進 `sync_error`（跟目錄 fsync 失敗同一條通道）。

## M1 審查交棒（已知、不修，各自綁在後面的階段）

> 2026-08-28 的 M1 審查（[report](../build-cycle/archive/m1-loop-side/review/report.md)，28 條）
> 有四條**確認存在但刻意不在 M1 修**——它們要的是後面階段才會有的機制，硬在 M1 補會做出
> 一個之後要拆掉的半套。撞到症狀時先查這裡，不要當成新 bug 重查一遍。

- **`.aos/turn` 壞掉之後 aos 自己救不回來**（審查 #9，→ **M3 `aos recover`**）：
  `turn` 的內容不是「十進位整數＋LF」時 `advance_turn` 回 `EINVAL`，於是**每一輪都回 1**，
  而批次其實照跑、`.runi` 照刪、副作用照發生。世界不會停，只是 PC 永遠凍在原地，而且
  沒有任何指令能把它修好（手改檔案除外）。M1 只保證「不猜、不靜默」；「壞掉要怎麼自癒」
  屬於 recover 的語意，跟 `.runi` 殘骸、`.temp` 殘骸、`.bad` 清理是同一批問題，M3 一起裁。
- **`aos exec --loop` 對退出碼 1 不會停手**（審查 #28，→ **M2 loop 的退避／停機政策**）：
  `run_loop.cpp` 只有 `if (result == 3) return 3;`。持續性的狀態損壞（例如上一條）會讓 loop
  一輪一輪回 1、一輪一輪照跑，沒有次數上限也沒有退避。**危險的不是 `--loop` 本身**——rc=3
  會直接收工，所以兩個 loop 打同一個世界很快會退化成一個；真正會疊起來的是被反覆一次性
  叫起來的 `aos exec`（cron／systemd timer／多個 agent 各自呼叫）。
- **退出碼 1 不代表「這一回合沒有發生」**（審查隊補列，→ **M3 recover 語意一起看**）：
  `turn` 的遞增排在 `release_instruction` 成功**之後**（§B-3），所以 `advance_turn` 失敗那一趟，
  `.runi` 已刪、批次已跑完、副作用已落地，只有 PC 沒動。SPEC §D-9 末段已經用文字擋住這個
  誤讀，但**沒有任何機制能把 PC 補回去**。
- **`.runi` 不是一把鎖**（見上一節第一條，→ **M2／M3**）：M1 審查修補把「兩個彙整者各自
  發布一次」那一半用排他發布關掉了（§D-5），但**取件本身**仍是 check-then-act。

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
