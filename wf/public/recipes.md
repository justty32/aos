# wf/public/recipes — 要做某件事時該用哪支、照哪一節（任務類型→做法，各線摸出來的）

← [wf/public](README.md)

寫任務書時從這裡抄「必用做法」；自己動手前也先查。每列一行做法，細節在連到的那一節。標「聽說」的是文件有寫、還沒人回報照做過。投稿只追加列。

## 隊員

<!-- wf-nav -->
| 要做的事 | 做法（一行）與細節 |
|---|---|
| 掛一隻 gpt 的 agent-fsm 隊員 | `agent_def new` 範本 agent-fsm（`llm.json` 是 `{"model":"sol","reasoning_effort":"high"}`；`AOS_LLM_KERNEL` 由上層 daemon 那一列傳下來，只有還沒改成 `~/aos-home` 一套的機器才用 `.env` 或 `envs` 帶）→ `subagent add` 帶 `limits`。[aos-teams 第 3 件](../workflows/dispatch/aos-teams.md)、[skyrim-agentctl 03](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) |
| 派蒐集員或審稿員 | 範本 agent-fsm 蓋上 `kits/gather/` 的 system、tools、llm（`.env` 不用抄）；沒有 shell；任務書寫知識庫的絕對路徑、不附必讀清單（聽說）。[kits](../workflows/dispatch/kits/README.md)、[card](../workflows/dispatch/kits/card.md) |
| 命名、資源上限 | `<eca名>-<角色>-<編號>`；add 帶 `limits`，sol 預設 `{"mem_mb":1024,"files":256}`、`procs` 別設。[07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[sol-crew「rlimit」](sol-crew.md#rlimit-實測與腦額度) |
| 讓隊員一路做到完 | 定義掛 `goal`；任務書寫「第一步 goal set；輸出檔寫完才可以用純文字回答」。skyrim-agentctl 03「摩擦」 |
| 唯讀蒐集的隊員擋寫檔 | 不給 shell 與刪除包；`write`／`edit` 加 `before_tool` hook 只准寫指定夾（exit 10＝擋）。skyrim-agentctl 03「實際的隊形」 |
| 等隊員做完 | `say` 完就結束這一輪；clock 叫醒自己再 `listen` 帶 `last: 1`，或背景跑 [waitdone](tools/waitdone/README.md)；`listen` 帶 `timeout_s` 60 以內。[等隊員與讀信](等隊員與讀信.md) |
| 看隊員在寫、等腦、還是停了 | `<stack>/stage.txt`、`history.jsonl` 修改時間、`llm-gpt/requests/cur` 與 `new` 有沒有它的信。skyrim-agentctl 03「摩擦」 |
| 看誰用了多少腦 | 讀 `llm-gpt/ledger.jsonl`，照 `sender` 加總 `usage` 與 `elapsed_ms`。skyrim-agentctl 03「數字」 |
| 收隊 | `subagent rm <名>`（stack 留著）；開過 gate 就 `kernel_gate off`；核對記的 pid 都不在 |
| 給 sol 寫任務書 | 一張單一件事、寫明可改的檔；事實與設計分開；「讀完同一回合就動手」；施工員寫死五句。[sol-crew](sol-crew.md) |
| 施工的 sol 要不要給必讀清單 | system 放清單、末行自報；蒐集員、審稿員不用給（使用者 11-14 裁按角色分）。[sol-crew「必讀清單」](sol-crew.md) |
| sol 被 guard 擋了唯讀查詢 | 不叫它改字面繞；隊長代跑、結果寫成檔叫它讀。[sol-crew「guard」](sol-crew.md) |
| sol 開工半小時幾乎沒動 | history 只有十幾行＝在排隊；小題自己讀，大題經 eca-aos 同意改派 Claude 子 agent。[sol-crew「排隊」](sol-crew.md) |
| 派 Claude 子 agent 做長事 | 前景跑、寫 `progress.md`、可寫路徑只一個絕對路徑（/tmp 也不行）、結果放最後一則回答。[claude子agent](claude子agent.md) |

## 交件與驗收

<!-- wf-nav -->
| 要做的事 | 做法（一行）與細節 |
|---|---|
| 交 commit | `commit-request claim`／`submit --files … --msg-file …`，共用索引用 `--op`；不 `git add`。[aos-teams 第 1 件](../workflows/dispatch/aos-teams.md)、[07「commit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#commit) |
| `DescMissing`、中文檔名、claim | `index_gen_desc.json` 加一行；清單用 `git -c core.quotepath=off`；claim 檔不 claim 夾。[patch-and-commit「commit-request 的坑」](patch-and-commit.md) |
| 回報 | `mailbox_send` 寄任務書指定的對象；status 用 `NEEDS-USER`／`BLOCKED`／`PROGRESS`／`DONE`。[07「寄信怎麼寫」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#寄信怎麼寫) |
| 暫存樹改了 C++ 要跑測試 | `python3 install.py`（或 `make -C proto8/cpp BINDIR=$AOS_HOME/bin aos-<名字>`）；跑前看 `proto8/bin` 修改時間。[pitfalls](pitfalls.md) |
| 殺自己起的行程 | 只 kill 自己記下的 pid；不 `pkill -f`。[pitfalls「隊長的 shell」](pitfalls.md#隊長的-shellbash-工具)、[行程與環境](行程與環境.md) |
| 暫存樹的改動交回 main | 先 `git log <舊base>..HEAD -- <檔>`；衝突少 `patch -p1`，多就小 git 三方合併；整套測試再交。[patch-and-commit](patch-and-commit.md) |
| 改了共用契約要驗收 | 每個 `tests` 夾都跑，改前改後各一次只看新紅；經 clean.sh 跑免得假綠。[patch-and-commit「驗收跑全套」](patch-and-commit.md) |
| 在乾淨複本驗改動 | `git archive HEAD proto8` 再疊檔；`env -i …` 或 clean.sh；bin 用複本自己的原始碼編。[pitfalls「標準跑法」](pitfalls.md) |
| 改活樹當下就吃到的檔（knowledge、frontend；在 repo 跑 install.py） | 備份 → 暫存檔再 `mv` → 被 import 的先換、每換一檔就 import → 先在乾淨複本預演。[活樹旁邊](活樹旁邊.md) |
| 放行別人的 commit | 自己看實際 diff、測試結果行、備份等於 HEAD；放行信寫明看過哪一版。[patch-and-commit「放行」](patch-and-commit.md) |
| 改到每隻 agent 都走的路 | 另派全新的審稿員：只給 diff、規格、邊界問題，只讀不跑。[審查與實測](審查與實測.md) |
| 寫讀 daemon 表的程式 | 至少一條測試用真 daemon `ctl add` 掛出一列再讀；交件附那一列原樣。[審查與實測](審查與實測.md) |
| 決定 commit 要不要隨當晚換樹 | submit 前決定：pin 跳不過中間某筆；不想進就等 pin 釘完再交。[活樹旁邊「換樹當晚」](活樹旁邊.md) |
| 封存或搬檔 | 預設留指標頁、不帶 `--rm`；要移除舊路徑得使用者明說。[STRUCTURE](../STRUCTURE.md#archive-規則) |
| 改有合計數字的共用檔 | 先 claim；以交件當下的 HEAD 重算。[patch-and-commit](patch-and-commit.md) |

## 其他

<!-- wf-nav -->
| 要做的事 | 做法（一行）與細節 |
|---|---|
| 請 Argon 當第二意見 | /tmp 跑 `agy -p … --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，內容貼進提示、第一行寫不准用工具。[model-notes](model-notes.md) |
| 通知太多想清淨一段 | `wf/tools/quiet.py install`，再 `quiet.py 30m`。[tools/quiet](tools/quiet/README.md) |
| 寄信問使用者、讀回信 | `aos-user send --kind …`，每寄件人每小時 10 封；回信 `mailbox_read` 後 `aos-user verify` 見 `ok: matches` 才算。[user-zone-mail](user-zone-mail.md) |
| 大批舊帳逐筆清 | 切 4 份派 opus 子 agent 唯讀並行，每筆歸 A 結案／B decide／C verify·chore。[team-patterns](team-patterns.md) |
| 換 uid、sudo、cgroup 的測法 | `aos-asuser sub:N`；`sudo -n -k … true` 看退 0；`systemd-run --user --scope`。[權限與沙箱](權限與沙箱.md) |
| 改寫全場必讀的規矩檔 | 草稿夾 → 全文先進 archive → 對照表請沒看過的人對 → 一口氣換上。[改文件與知識庫](改文件與知識庫.md) |
| 量文件好不好查 | 請沒看過的 agent 從入口只跟連結走十來題，記走不走得到與讀了多少。[改文件與知識庫](改文件與知識庫.md) |
| 給外人看的文件、要公開的檔 | doc-run 照字實跑、scan 掃個人值、截圖加 `--virtual-time-budget`。[發佈前檢查](發佈前檢查.md) |
| 派小修、蓋到舊裁定 | 先 `git log <基底>..HEAD -- <檔>`；會蓋掉使用者舊裁定先找原文，找不到寄 decide。[設計與查證](設計與查證.md) |
| 看活樹、查祕密 | 路徑先列給 eca-aos 點名；值不落地、只印檔名。[活樹旁邊](活樹旁邊.md) |
| 寫紀錄或訂截止時刻 | `peek_now_time {"local": true}`；信的 `sent_at` 是 UTC。[等隊員與讀信](等隊員與讀信.md) |
| 寫定義、換定義 | eca 關自動記憶；換定義用 `ctl set-def`（subagent 掛的不行）。[定義與換定義](定義與換定義.md) |
| 帶 gate 的樹、獨佔資源上鎖 | 主導每輪做短、下屬 `KernelFailed` 等十幾秒重試；遊戲、桌面由主導點名給鎖。[gate與鎖](gate與鎖.md) |
