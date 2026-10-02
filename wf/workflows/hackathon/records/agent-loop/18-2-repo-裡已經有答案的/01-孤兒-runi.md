← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 1/3）｜[下一份](02-批次不短路-needs.md)

**孤兒 ＋ `.runi`（P0，四位共同）**

- **兩句矛盾的話各自在哪**：不變式在 `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉（「`.runi` 存在 ⟺ 有一回合沒跑完」，以及「行程死掉（crash、被 kill、斷電）`.runi` 就會留著」）；`setpgid` 那句在同檔〈十二、留給實作決定的〉的子節〈已經被實作決定的〉（「子行程各自 `setpgid` 自成一個 process group，所以終端機的 Ctrl-C 打不到它們」）。同節還寫了 `--loop` 的 `SA_RESETHAND`：**第二次信號直接殺掉行程，那時 `.runi` 會留著**。
- **`aggregate` 排在 `claim` 之前，文件層就查得到**：`wf/workflows/common/code-map.md` 的 `run_exec.cpp` 那一列寫著「單回合：進入 world、驗版本、**aggregate → claim → execute batch → release**，並把結果映成診斷與 0／1／3」。配 `core/inst/docs/handoff.md`〈取件與釋放〉：`claim_instruction()` **先拒絕既有 `.runi`，再完整讀取 base**，`release_instruction()` 應在所有子行程（含 parallel thread）結束後才呼叫。
- **同一個孤兒現場上一次就有**：`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉——前景 `timeout -s INT` 得到 `exit=130`／`runi=yes`／`child_exit=missing`，六秒後 `state=completed` 但 `child_exit` 仍 missing，下一次 `aos exec` 回 3。**同節第一段還保留了一個無效的 harness**：背景 job 繼承忽略 SIGINT，`kill -INT` 根本沒打中（Carmack 這輪重踩了一次）。
- **`.runi` 該升級成租約，三位獨立提過，而且已經有一個形狀限制**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 2 條——`.runi` 現在的內容**就是那批 JSON**，`cat` 一下就知道卡的是哪一批，**包一層 header 會毀掉這點**；所以主張 receipt 放旁邊（`inst.json.runi.receipt`），且**先寫 receipt、後 rename `.runi`**。同節第 5 條另問「`.runi` 鎖的是那一批還是那個世界」，並指出上面每一條提案都預設了一個答案卻沒人講明。
- **租約要原子建立，規格已經點名了工具**：`docs/aos-folder.md`〈十二、留給實作決定的〉子節〈仍然開著的〉——「`.runi` 的檢查與 `rename` 之間有 TOCTOU……要真的原子化得用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`」。
- **`timeout_ms` 那條路上孤兒早就有解**：`core/inst/docs/exec.md`〈逾時與行程群組〉——到期先對**整個子行程的行程群組**送 `SIGTERM`、給 2000 ms、仍活著就 `SIGKILL` 整個群組，「打群組是因為忽略 `SIGTERM` 的孫行程才殺得掉」。也就是說機制存在，缺的只是 parent 被外部信號砍掉那一條路徑。
- **崩潰後的架構共識與硬邊界**：`wf/workflows/workshop/records/agent-loop-architecture.md`〈斷點續跑的硬邊界：本機可以原子，遠端付費不能假裝 exactly-once〉——「**rename 保發布，不保任意 LLM CLI 恰好付費一次**」，並列出可安全自動恢復的只有兩種（provider 接受同一 idempotency key／provider 能按 request ID 查回原結果）。同檔〈明顯的坑〉有兩條正中這輪：「**先呼叫 LLM，成功後才開始記 call**」與「**把 `unknown` 自動當失敗重跑**」。

**「不重複付錢的復原」與 recover 的形狀（p1、p3）**

- **policy A／B／C 的對照上一次就跑過**：`wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉——假 provider 在效果已發生、結果未回時斷線，policy A（停）ledger 留 1、**policy B（按 provider key 查回）exit 0 且 ledger 仍是 1**、policy C（盲目 retry）ledger 變 2。Armstrong 這輪用 `codex exec resume <thread_id>` 拿回答案，就是 policy B 的真模型版。同節上半還有 request／effect／result.temp 三個時間點 × SIGINT／SIGKILL 的六格輸出。
- **`aos recover` 的介面已經被寫出來過**：同檔〈痛在哪：可直接寫成子命令的需求〉的 `aos recover [WORLD]` 一節——「命令不能假裝有 program counter；它應先**唯讀列出** `.runi`、每筆 exit/result 證據與**可能仍活著的未知子行程**」，動作分成 `--replay`／`--abandon`／`--adopt RECEIPT`，並明寫「**沒有足夠證據時預設必須停住，而不是自動重播**」。
- **同節的 `aos deliver`／`aos status --json`／`aos agent step`／`aos agent emit-context`** 四支也都有段落，`agent step` 那段列出了要保存的 phase：`request-published → effect-started → result-temp → result-published → next-delivered`。
- **roadmap 自己已經標了矛盾**：`docs/roadmap.md`〈T5 — agent loop：**不需要 `core/llms`**〉底下那個 ⚠ 區塊——驗收的「中途 `Ctrl-C` 之後再 `aos exec` 一次能從斷點繼續」與 D6 互相矛盾，並列出兩條擇一的路（改措辭承認續跑＝回合邊界／長出真正的復原路徑），最後一句是「**在拍板之前，不要照這條驗收去實作**」。

**停止條件與退出碼（p2、p4、`aos status --json`）**

- **`--loop` 其實已經有一個停止條件**：`docs/aos-folder.md`〈十二／已經被實作決定的〉——「**回合失敗時 `--loop` 不停**，繼續下一回合。**只有退出碼 3（`.runi` 已存在）會讓迴圈退出**」。`docs/roadmap.md`〈T4 — 迴圈：`aos exec --loop <毫秒>`，不做 `core/daemon`〉的〈注意〉段也寫著 crash 之後迴圈會永遠拒絕啟動是預期行為。
- **退出碼契約與它的已知缺口**：`docs/aos-folder.md`〈八、退出碼〉四碼表（0／1／2／3），明寫「子行程回非零、被訊號殺掉、逾時——那些都算一次**完成**的執行，回合照樣 0」；`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉是完整契約；`wf/workflows/common/gotchas.md`〈使用 aos〉已經記過「`aos exec` 的退出碼不反映子行程成敗」。
- **「把無事可做從 0 裡拆出來」與「停止條件搬回檔案系統」兩條提案都已成文**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈轉交提案／一、要改 `docs/aos-folder.md` 的〉第 3 條（退出碼只帶四個類別 ok／無事／busy／壞了，細節寫成 receipt）與第 4 條（**`--loop` 的停止條件明文寫成「回合開頭自己 `stat` 一次 `.runi`」**）。
- **上一次實測列的 status 狀態名**：`wf/workflows/experiments/t5-agent-loop.md`〈`aos status --json [WORLD]`〉——`ready`／`running`／`blocked-runi`／`bad-delivery`／`no-work`／`unknown-effect`，並明寫「不要把 prompt 政策塞進 status」。
- **`--loop` 抱著壞世界一直轉的風險已被列為「壞 2」**：`wf/workflows/workshop/records/exec-as-pure-cpu.md`〈壞（六條）〉第 2 條。
