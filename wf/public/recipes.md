# wf/public/recipes — 要做某件事時該用哪支、照哪一節（任務類型→做法，各線摸出來的）

← [wf/public](README.md)

寫任務書時從這張表抄「必用做法」；自己動手前也先查。每列只寫一行做法與出處，細節在出處。投稿：只追加列；做法變了改那一列並在「驗過」欄換日期。狀態：**驗過**＝有人實際照做成功；**聽說**＝文件有寫、還沒人回報照做過。

| 要做的事 | 做法（一行） | 出處／細節 | 驗過 |
|---|---|---|---|
| 掛一隻 gpt 的 agent-fsm 隊員（活樹裡） | `agent_def new` 從 `agent-fsm` 複製 → 改 `llm.json` 為 `{"model":"sol-high"}`（或 `astra-high`）→ `subagent add`，`envs` 帶 `AOS_LLM_KERNEL=<活樹>/ws/.stack/procs/llm-gpt` | [skyrim-agentctl 03「實際的隊形」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 隊員命名 | `<eca名>-<角色>-<編號>`，例 `ok-kf-sol-1` | [07「命名」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 給 fsm 隊員設資源上限 | `subagent add`／`ctl add` 帶 `limits`：sol 預設 `{"mem_mb":1024,"files":256}`；`procs` 別設；對 eca 下 prlimit 傳不到隊員 | [07「rlimit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[sol-crew「rlimit 實測」](sol-crew.md) | 11-14 ok-pilot |
| 讓 gpt 隊員一路做到完、不要只回「我會做」 | 定義掛 `goal` 工具；任務書寫「第一步 goal set；輸出檔寫完才可以用純文字回答」 | [skyrim-agentctl 03 摩擦 1](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 唯讀蒐集的隊員怎麼擋寫檔 | 工具不給 shell 與刪除包；`write`／`edit` 加一個 `before_tool` hook 只准寫指定夾（exit 10＝擋） | 同上「實際的隊形」 | 11-14 ok-skyrim |
| 等隊員做完 | `say` 交代完就結束這一輪，叫隊員做完 `mailbox_send` 給你；真的要當場等，用短迴圈看 `<隊員 stack>/stage.txt` 變 `idle`，每輪三分鐘內；Claude Code 隊長可背景跑 [tools/waitdone](tools/waitdone/README.md)（看 `history.jsonl` 末行是不帶 tool_calls 的 assistant）。**不要用 `subagent listen` 等超過 60 秒的事**（活樹換樹前仍會被砍） | 同上摩擦 2、[07 頂層提醒](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[tools/waitdone](tools/waitdone/README.md) | 11-14 ok-skyrim、ok-llmk2 |
| 看隊員是在寫、在等腦、還是停了 | 看三樣：`<stack>/stage.txt`（idle／think／wait／act）、`history.jsonl` 的修改時間、`llm-gpt/requests/cur` 與 `new` 有沒有它的信 | 同上摩擦 3 | 11-14 ok-skyrim |
| 看誰用了多少腦 | 讀 `<活樹>/ws/.stack/procs/llm-gpt/ledger.jsonl`，照 `sender` 加總 `usage` 與 `elapsed_ms` | 同上「數字」 | 11-14 ok-skyrim |
| 收隊 | `subagent rm <名>`（stack 留著）；自己開過 gate 就 `kernel_gate off`；核對當初記的 pid 都不在 | 同上 | 11-14 ok-skyrim |
| 交 commit | `commit-request claim`／`submit --files … --msg-file …`，索引用 `--op`；不 `git add`、不自己跑 index_gen | [07「commit 一律交給排隊指令」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 回報給頂層 | `mailbox_send` 寄 `xiaosi`；要緊的 status 用 `NEEDS-USER`／`BLOCKED`；標題照三條規矩 | [07「頂層的雜務自動化」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 請 Argon 當第二意見 | 在 /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，內容貼進提示並寫明 `Do not use any tools`（不寫會沒產出）；要它分 (A) 審查 (B) 提案 | [05「Argon 是參與者」](../workflows/dispatch/aos-teams/05-同機session與Argon.md)、[model-notes](model-notes.md) | 11-14 ok-skyrim、ok-astra、ok-kf、ok-llmk2 |
| 通知太多想清淨一段 | `wf/public/tools/quiet`：`quiet.py install` | [tools/quiet](tools/quiet/README.md) | 11-14 repo-aos |
| 給 sol 寫任務書 | 一張單一件事、寫明可改哪些檔；事實（唯讀 sol）與設計分開；寫「讀完必讀，同一回合就動手」；交回的碼隊長自己再讀 | [sol-crew「任務書」](sol-crew.md) | 11-14 ok-astra |
| sol 隊員要不要給必讀清單 | system 放清單、要它末行自報讀了哪幾份；雜活在任務書寫免讀或略讀 | [sol-crew「必讀清單」](sol-crew.md) | 11-14 ok-pilot |
| sol 被 [aos] guard 誤擋唯讀查詢（字面含 rm／kill／aos-） | 不叫它改寫字面繞；隊長代跑搜尋、結果寫成檔叫它讀；行程檢查隊長做 | [sol-crew「guard」](sol-crew.md) | 11-14 ok-misc |
| 暫存樹改了 impls 的 C++ 要跑測試 | `make <名字>_main`（只 `make <名字>` 不會重編 bin）；跑前看 bin 修改時間 | [pitfalls](pitfalls.md) | 11-14 ok-misc |
| 殺自己起的行程 | 只 kill 自己記下的 pid；不 `pkill -f <字串>`（會殺到自己的 shell） | [pitfalls「隊長的 shell」](pitfalls.md) | 11-14 ok-kf |
| 暫存樹的改動交回已往前走的 main | 先 `git log <舊base>..HEAD -- <檔>`；衝突少用新 HEAD 複本 `patch -p1`，衝突多在 /tmp 小 git 三方合併；整套測試、`git apply --check` 再交 | [patch-and-commit](patch-and-commit.md) | 11-14 ok-astra、ok-kf |
| commit-request 報 `DescMissing <夾>/` | 在 `wf/tools/index_gen_desc.json` 加 `"<夾>": "一句說明"`，該檔也 claim、放進 `--files`；中文檔名清單用 `git -c core.quotepath=off` 產 | [patch-and-commit「commit-request 的坑」](patch-and-commit.md) | 11-14 ok-astra、ok-kf |
| 寄信問使用者／要授權 | `aos-user send --kind … --from <線> --reply-to <stack>/mailbox`；拿 send 當檢查；每寄件人每小時 10 封 | [user-zone-mail](user-zone-mail.md) | 11-14 ok-pilot |
| 讀使用者專區的回信、驗授權 | `mailbox_read {"keep": true}`，再對 `mailbox/archive/<信名>` 跑 `aos-user verify`，見 `ok: matches` 才算 | [user-zone-mail「讀回信」](user-zone-mail.md) | 11-14 ok-pilot |
| 大批舊帳逐筆清 | 切 4 份派 opus 子 agent 唯讀並行，每筆歸 A 結案／B decide／C verify·chore，帶隊者核對後給頂層看再寄 | [team-patterns](team-patterns.md) | 11-14 ok-pilot |
| 改了共用程式的契約（函式改名、讀表入口、輸出格式）要驗收 | proto8 底下每個 `tests` 夾都跑，「main 原樣」與「main＋改動」各跑一次只看新紅；改了被 mock 的函式先 grep 出所有 patch 它的測試 | [patch-and-commit「驗收跑全套」](patch-and-commit.md) | 11-14 ok-kf |
| 驗收時有紅的，判斷是不是本來就紅 | 經 clean.sh 跑（別在帶 AOS_* 的隊長 shell 跑，會假綠）；紅的在 `git archive HEAD` 乾淨複本同環境重跑，本來紅的轉給擁有線 | [patch-and-commit「驗收跑全套」](patch-and-commit.md) | 11-14 ok-limits |
| 驗換 uid 後碰不碰得到檔、殺不殺得到行程（不用 root） | `aos-asuser sub:N -- 程式`（真號＝起點＋N－1）；改 subuid 的檔用 `unshare --map-users … --map-root-user`；暫存夾放 /tmp | [權限與沙箱「免 root」](權限與沙箱.md) | 11-14 ok-sec |
| 判斷 sudo NOPASSWD 准不准、換身分 | 不信 `sudo -n -l`；真跑 `sudo -n -k … /usr/bin/true` 看退 0；一律帶 `-k`；共用夾只 mkdir 不 chmod | [權限與沙箱「sudo」](權限與沙箱.md) | 11-14 ok-limits |
| 在家機測 cgroup v2 程式 | `systemd-run --user --scope --collect -p Delegate=yes -p TimeoutStopSec=2s`，收尾 cgroup.kill→stop→reset-failed；有 swap 要 `memory.swap.max=0` | [權限與沙箱「transient scope」](權限與沙箱.md) | 11-14 ok-limits |
| 派蒐集員或審稿員（fsm sol） | `agent_def new` 範本 agent-fsm，蓋上 `wf/workflows/dispatch/kits/gather/` 的 system、tools、llm、.env；工具 24 支，沒有 shell、改不了自己；任務書不用附必讀清單 | [kits](../workflows/dispatch/kits/README.md)、[card](../workflows/dispatch/kits/card.md) | 聽說（11-14 ok-onboard，agent_def check 過，還沒真跑） |
