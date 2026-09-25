← [在 `aos exec` 上做一條會動的 agent loop](../agent-loop.md)（分檔 18/24）｜所在：下一輪的資料包｜[上一份](17-下一輪的資料包.md)｜[下一份](19-3-兄弟專案裡可以抄的.md)

### 2. repo 裡已經有答案的

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

**批次不短路 ／ `"needs"`（p2）**

- **這不是實作與規格對不上，規格從沒承諾短路**：`docs/aos-folder.md`〈八、退出碼〉與〈五、回合語意〉；`core/inst/docs/exec.md`〈狀態與失敗〉寫得最白——「非零的子行程狀態、訊號終止、PATH 找不到、設定階段狀態，或逾時，都是一次已完成的執行……**它不會中止後續的記錄**」。
- **真要把 `"needs"` 加進 format，動到哪幾個檔已經列好了**：`wf/workflows/common/code-map.md`〈新增一個 instruction 欄位〉——① `inst.hpp` 的 `inst_t` 加欄位；② `format.cpp` 的 `known_key`／`encode`／`decode` **三處都要加**；③ 需要的話 `inst.h` 加 C ABI 存取子＋`capi_instruction.cpp`；④ `exec.cpp`／`spawn_prep.cpp` 視語意決定。
- **`exit` 欄位是誰在什麼時候寫的**：`core/inst/docs/exec.md` 欄位對應那段——「非空的 `exit` 會由**父行程在等待完成後**建立／截斷，並寫入回報的十進位狀態」；`core/inst/docs/format.md`〈綱要(schema)〉的欄位表是同一件事的格式層說法。

**`$ref` 與重複的批次模板（p2、p4）**

- **規格的原話與那扇留著的門**：`docs/inst-directives.md`〈四、`$ref`〉——「**已定：取回來的值必須是字串。** 指到陣列或物件就是錯誤」，以及括號那段：「考慮過讓 `argv` 的元素可以展開成多個……但那會讓 `$ref` 從『產生一個值』變成『可能改變結構』……**真的需要時，另設一個明確表達「展開」語意的指示詞會更誠實**」。同檔〈五、適用範圍〉是可放指示詞的位置表。
- **新指示詞的硬門檻**：`docs/aos-folder.md`〈七、instruction 的格式〉最後一段——彙整會把每份投遞經格式層完整往返一次，所以「**還沒解析的指示詞必須能原樣寫回 JSON**」，否則會在彙整那一步被無聲吃掉。`core/inst/docs/handoff.md`〈彙整規則〉重述了同一條。
- **要新增哪些錯誤狀態**：`docs/inst-directives.md`〈七、對現有契約的影響〉已列（不認得的 `$xxx`、多於一個鍵、值不是字串、`$ref` 目標不存在或逃出 root……）。

**投遞、檔名與投遞前驗證（p4，以及四位都重寫過的 counter）**

- **檔名規則規格層寫得很精確**：`core/inst/docs/handoff.md`〈彙整規則〉——「只接受**第一個副檔名就是結尾**的 `<name>.json`；`123.json.temp`、`123.json.bad`、`name.part.json` 都會跳過」。這解釋了 Carmack 的 `185452-0.json` 為什麼被正常收走。判定函式是 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`。
- **PID 不夠用，上一次就有現場**：`wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉——同一 shell 連做兩次 temp+rename，`first_exists=no`，第一份靜默遺失；同節還有「直接寫 ready、不經 `.temp`」讓半份 JSON 被 rename 成 `.bad` 的現場。
- **兩個 producer 各投 1,000 件的壓力數據已經有人跑過**：`wf/workflows/hackathon/records/core-scope/rounds.md`〈第 2 輪紀錄〉——共用本地序號時**遺失 1,000 件**，改用全域唯一 ID 時「遺失、重複、覆蓋、明確失敗皆為 0」。
- **投遞前驗證是四位獨立的共識，錯誤該長什麼樣也定了**：`wf/workflows/workshop/records/tool-interop.md`〈誰驗證、驗不過怎麼回〉——「四位獨立地都要求 Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見檔案」，並劃清 `.bad` 的邊界（**它只隔離繞過 Deliver 直接塞檔的壞檔**）。〈給模型看的錯誤訊息〉給了共同的 JSON 欄位：`code`／`record`／`pointer`（JSON Pointer）／`expected`／`actual`／`hint`。
- **`aos deliver` 的形狀、發布五步與退出碼分歧**：同檔〈`aos deliver` 的合成版 `--help`〉、〈寫到哪裡、檔名怎麼配〉（四位獨立地都給出同一個五步發布順序，**四位都沒有只靠 PID 保唯一**）、〈退出碼還沒有共同編號〉（四份不同編號的對照表）。
- **`--key` 目前不能宣稱冪等**：同檔〈`aos deliver` 的合成版 `--help`〉末段——aggregate 會刪除投遞檔，沒有 ledger 就不能承諾跨回合 Already／Conflict。

**tool registry ／ 回程的型別（p2 的第 3 次轉換、p3 的不對稱）**

- **`aos tooljson` 到底解決了多少，有明確答案**：`core/tooljson/docs/format.md`〈CLI〉——S1 只有 `aos tooljson list <spec.json>` 與 `check <spec.json>`，「`run` 尚未存在」。〈`exec` 配方的載入期驗證〉開頭寫著 `ExecBody::run()` **固定回 `Error: exec execution is not implemented in S1`，不會 fork 或 exec**。也就是：**格式與驗證有了，執行沒有。**
- **「對的那一種 registry」的欄位清單**：同檔〈`exec` 配方的載入期驗證〉列出 `exec`／`argv`（binding 只接受 `position`／`flag`／`separate`／`repeat`）／`stdin.param`／`stdout.clip`／`stderr.mode`／`ok_exit`／`timeout`／`cwd`／`limits`／`source`；〈外殼〉列出 schema 形狀的載入期檢查與「同一檔內 `function.name` 不得重複、多檔比照 `PATH` 先出現者獲勝」。
- **展開錯誤就是要餵回模型的那句話**：同檔〈模型參數展開〉——「模型給錯參數時回 `Error: ...` 字串，**呼叫端應把它直接當 tool message 送回模型**，而不是丟例外」，並列出八條展開規則（含「任何單一 argv 項目超過 131072 bytes 都拒絕」）。
- **回程的截斷語意**：同檔〈文字收尾〉——`decode_output()` 遇 NUL 只回 `(binary output, N bytes, not shown)`，`clip_output()` 超過限制保留 head 或 tail 並標明省略的字元數。這是 Armstrong 手寫 `sed -n '1,60p'` 的規格版。
- **具名工具映射的既有詞義**：`wf/workflows/workshop/background/agent-loop.md`〈tool allowlist（具名工具映射）〉與〈driver 與 adapter〉。

**`aos llms`（四位的集體盲點）**

- **子命令形狀與直接打 LM Studio 的現成範例**：`core/llms/README.md`〈子命令〉——`aos llms ask [--model M | --preset P] [--stream] [--system S] [--url U] [--key K] <prompt>` 與 `aos llms models [--url U] [--key K]`；`--url` 預設 `http://localhost:4000`，但**proxy 不是必需品**，README 直接給了 `aos llms models --url http://localhost:1234/v1` 與 `aos llms ask --url http://localhost:1234/v1 --model … "你好"`。**注意 prompt 是位置參數，CLI 這一層沒有 stdin、沒有 `--json`**。
- **能力查詢為什麼要兩個端點**：同檔〈能力、工具與 presets〉——`LLM::models()` 問 `/model/info`（LiteLLM 專屬）與 `/v1/models`（每個 OpenAI 相容端點都有）的聯集，「少了 `/v1/models` 這一半，直接打 LM Studio 之類的端點會得到一片空白」。
- **它掛在哪、tool call 在函式庫層是什麼形狀**：`wf/workflows/common/code-map.md` 的 `aos::llms` 段（`core/llms/` → `libaos_llms.so`，`app/` 掛 `aos llms ask|models`，成功路徑會連網）；`core/llms/README.md`〈串流 Reply〉說明 `Reply` 的 `calls[].args` 是未解析的合法 JSON 字串、參數不合法時 `args` 為空而原文放 `args_raw`。
- **T6 已經把它的位置畫好了**：`docs/roadmap.md`〈T6 — 把 LLM 內化：`aos llm exec <folder>`〉——`["aos","llm","exec","."]` 對 `aos exec` 而言只是普通 POSIX 指令，和 T5 裡那支外部 CLI 站在完全相同的位置。同節也寫著 D4 的「先不動」可能是「永遠不用動」。
- **不要在 T5 就用它的理由，roadmap 自己有寫**：`docs/roadmap.md`〈D4 — llms／tooljson 是原地改造還是重長一次？〉。

**`parallel: true` ／ tool_call_id（p4）**

- **語意在兩個地方各寫了一次**：`core/inst/docs/format.md` 欄位表的 `parallel` 那一列（「為 `true` 時 CLI 以獨立 thread 執行這一筆，不等它完成就啟動下一筆；**整批結束前仍會等待它**」）；`core/inst/docs/exec.md` 開頭第三段（「整批返回前會 join 全部 thread，因此**批次邊界仍然會等待每一筆完成**」）。`docs/roadmap.md`〈D3 — 阻塞還是非阻塞？〉是已定的決策紀錄（回合內並行，回合邊界不變）。
- **correlation ID 與 receipt 是兩件事**：`wf/workflows/workshop/background/delivery-contract.md`〈correlation ID（串接編號／request ID）〉與〈receipt（收據／completion record）〉；同檔〈TOCTOU（先檢查、後使用的競爭窗）〉是 Armstrong 那個窗口的既有詞條。
- **parallel tools 的 join 時機還沒定**：`wf/workflows/workshop/records/agent-loop-architecture.md`〈還在生長的想法〉的「**parallel tools 的 join 時機未定**」一段，以及〈大家問出來的問題〉表格裡研究人員那一列。

**pi 吃不吃 stdin（p1、p4 的分歧）**

- **repo 內第三份與「只能塞 argv」相反的資料**：`wf/workflows/workshop/records/tool-interop.md`〈pi 與本場的已知前提〉——「對行程整合有 `-p/--print`（**可吃 stdin**）」，同段也記了 skill 搜尋路徑與 session／resume／fork 介面。
- **上一次實測時 pi 還沒裝**：`wf/workflows/experiments/t5-agent-loop.md`〈6. 真 agent CLI〉（`pi path=missing command_v_exit=1`）與〈OPEN #6：golden slice 先用哪支真 agent CLI？〉——所以那一輪的排除是**環境可用性**，不是產品選擇。

**codex 的細節（p3 要重寫的那句、以及旗標順序）**

- **`~/.codex/sessions/` 的路徑主辦人自己記過**：`wf/workflows/hackathon/gotchas.md`〈codex〉——「還可以從 `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` 的**檔名**撈回來（UUID 就在檔名裡），但四位平行時無法分辨誰是誰」。同節還寫著 **session id 的 key 是 `thread_id`，不是 `session_id`**，且 `grep` 沒中是**無聲失敗**。
- **`codex exec resume` 的旗標位置**：同節——「`--json` 與 `-o` 有支援，但**要放在 `resume` 前面**」，`-s`／`-C`／`--add-dir` **不吃**（沙盒與工作目錄從原 session 繼承），「所以**場地必須還活著**」。同節另記 arena 不是 git repo，要加 `--skip-git-repo-check`。

**session resume vs 每回合重建（OPEN #19）**

- `wf/workflows/workshop/background/questions-agent-context.md`〈題目：第一版預設 `--no-session` 從 world 重建，還是優先使用 agent session 作續談快取？〉是這一題的原題；同檔第一題是 stdin 要吃 request file 還是 `status --json`（OPEN #18）。
- `wf/workflows/workshop/records/tool-interop.md`〈coding agent 的 session 只可當快取〉——四位都只接受 session 作可丟快取，遺失後必須能從 world 重建。同節也記了 `--session-dir` 這個旗標**未經核對，不可寫進 skill**。

**durability 的分層（四位都沒測，但詞義已經分清楚）**

- `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉把 rename 的可見性原子與 file/directory fsync 的斷電承諾分成兩層；同檔〈Effect（外部效果／capture／invoke）〉〈idempotency key（冪等鍵）〉〈ledger（耐久帳本／歷史表）〉〈`unknown`（無法判定外部效果）〉是 recover 動作命名的既有詞義。
- `wf/workflows/hackathon/records/core-scope/rounds.md`〈第 3 輪紀錄／6. 仍然不知道的〉已明列 power loss、NFS、非 Linux filesystem 與裝置快取都沒測；`verdicts.md`〈第 3 輪／路線判斷〉那段的原話是「**power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability**」。

**同一場黑客松的前例（格式與判準都可以照抄）**

- `wf/workflows/hackathon/records/core-scope/packs.md`〈下一輪的資料包〉是同一份四塊結構的前例，裡面很多條目與這輪重疊（`.runi`、孤兒、delivery 命名、receipt）。
- `wf/workflows/hackathon/records/core-scope/verdicts.md`〈第 2 輪／路線判斷〉與〈第 3 輪／路線判斷〉——那一場的評委也把「無 query／idempotency 的遠端 effect」判為**唯一致命的坑**，其餘（`.runi` 太粗、孤兒 process group、child 失敗但 `aos exec` 回 0）都判為麻煩。

---
