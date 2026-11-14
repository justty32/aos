# wf/public/recipes — 要做某件事時該用哪支、照哪一節（任務類型→做法，各線摸出來的）

← [wf/public](README.md)

寫任務書時從這張表抄「必用做法」；自己動手前也先查。每列只寫一行做法與出處，細節在出處。投稿：只追加列；做法變了改那一列並在「驗過」欄換日期。狀態：**驗過**＝有人實際照做成功；**聽說**＝文件有寫、還沒人回報照做過。

| 要做的事 | 做法（一行） | 出處／細節 | 驗過 |
|---|---|---|---|
| 掛一隻 gpt 的 agent-fsm 隊員（活樹裡） | `agent_def new` 從 `agent-fsm` 複製 → 改 `llm.json` 為 `{"model":"sol-high"}`（或 `astra-high`）→ `subagent add`，`envs` 帶 `AOS_LLM_KERNEL=<活樹>/ws/.stack/procs/llm-gpt` | [skyrim-agentctl 03「實際的隊形」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 隊員命名 | `<eca名>-<角色>-<編號>`，例 `ok-kf-sol-1` | [07「命名」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 給 fsm 隊員設資源上限 | `subagent add`／`ctl add` 帶 `limits`：sol 預設 `{"mem_mb":1024,"files":256}`；`procs` 別設 | [07「rlimit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、`wf/temp/ok-pilot/notes.md` | 11-14 ok-pilot |
| 讓 gpt 隊員一路做到完、不要只回「我會做」 | 定義掛 `goal` 工具；任務書寫「第一步 goal set；輸出檔寫完才可以用純文字回答」 | [skyrim-agentctl 03 摩擦 1](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 唯讀蒐集的隊員怎麼擋寫檔 | 工具不給 shell 與刪除包；`write`／`edit` 加一個 `before_tool` hook 只准寫指定夾（exit 10＝擋） | 同上「實際的隊形」 | 11-14 ok-skyrim |
| 等隊員做完 | `say` 交代完就結束這一輪，叫隊員做完 `mailbox_send` 給你；真的要當場等，用短迴圈看 `<隊員 stack>/stage.txt` 變 `idle`，每輪三分鐘內。**不要用 `subagent listen` 等超過 60 秒的事**（會整個被砍） | 同上摩擦 2、[07 頂層提醒](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 ok-skyrim |
| 看隊員是在寫、在等腦、還是停了 | 看三樣：`<stack>/stage.txt`（idle／think／wait／act）、`history.jsonl` 的修改時間、`llm-gpt/requests/cur` 與 `new` 有沒有它的信 | 同上摩擦 3 | 11-14 ok-skyrim |
| 看誰用了多少腦 | 讀 `<活樹>/ws/.stack/procs/llm-gpt/ledger.jsonl`，照 `sender` 加總 `usage` 與 `elapsed_ms` | 同上「數字」 | 11-14 ok-skyrim |
| 收隊 | `subagent rm <名>`（stack 留著）；自己開過 gate 就 `kernel_gate off`；核對當初記的 pid 都不在 | 同上 | 11-14 ok-skyrim |
| 交 commit | `commit-request claim`／`submit --files … --msg-file …`，索引用 `--op`；不 `git add`、不自己跑 index_gen | [07「commit 一律交給排隊指令」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 回報給頂層 | `mailbox_send` 寄 `xiaosi`；要緊的 status 用 `NEEDS-USER`／`BLOCKED`；標題照三條規矩 | [07「頂層的雜務自動化」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 請 Argon 當第二意見 | 在 /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，內容貼進提示；要它分 (A) 審查 (B) 提案 | [05「Argon 是參與者」](../workflows/dispatch/aos-teams/05-同機session與Argon.md) | 11-14 ok-skyrim |
| 通知太多想清淨一段 | `wf/public/tools/quiet`：`quiet.py install` | [tools/quiet](tools/quiet/README.md) | 11-14 repo-aos |
