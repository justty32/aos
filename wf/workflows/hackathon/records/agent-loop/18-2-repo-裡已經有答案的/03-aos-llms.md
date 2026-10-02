← [2. repo 裡已經有答案的](../18-2-repo-裡已經有答案的.md)（分檔 3/3）｜[上一份](02-批次不短路-needs.md)

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
