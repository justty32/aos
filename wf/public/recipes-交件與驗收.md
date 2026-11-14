# wf/public/recipes-交件與驗收 — 交 commit、回報、搬回 main、驗收、放行、活樹旁邊換檔（任務類型→做法）

← [wf/public](README.md)｜[recipes 總頁](recipes.md)

每列只寫一行做法與出處，細節在出處。投稿：只追加列；做法變了改那一列並在「驗過」欄換日期。狀態：**驗過**＝有人實際照做成功；**聽說**＝文件有寫、還沒人回報照做過。

| 要做的事 | 做法（一行） | 出處／細節 | 驗過 |
|---|---|---|---|
| 交 commit | `commit-request claim`／`submit --files … --msg-file …`，索引用 `--op`；不 `git add`、不自己跑 index_gen | [07「commit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#commit)（兩行指令在 [aos-teams 入口第 1 件](../workflows/dispatch/aos-teams.md)） | 11-14 |
| 回報 | `mailbox_send` 寄任務書指定的對象（11-14 起是各部部長）；要緊的 status 用 `NEEDS-USER`／`BLOCKED`；標題照三條規矩 | [07「回報」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#回報)、三條規矩在 [07「寄信怎麼寫」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#寄信怎麼寫) | 11-14 |
| 暫存樹改了 impls 的 C++ 要跑測試 | `make <名字>_main`（只 `make <名字>` 不會重編 bin）；跑前看 bin 修改時間 | [pitfalls-建置與複本](pitfalls-建置與複本.md) | 11-14 ok-misc |
| 殺自己起的行程 | 只 kill 自己記下的 pid；不 `pkill -f <字串>`（會殺到自己的 shell） | [pitfalls-shell「隊長的 shell」](pitfalls-shell.md) | 11-14 ok-kf |
| 暫存樹的改動交回已往前走的 main | 先 `git log <舊base>..HEAD -- <檔>`；衝突少用新 HEAD 複本 `patch -p1`，衝突多在 /tmp 小 git 三方合併；整套測試、`git apply --check` 再交 | [patch-and-commit](patch-and-commit.md) | 11-14 ok-astra、ok-kf |
| commit-request 報 `DescMissing <夾>/` | 在 `wf/tools/index_gen_desc.json` 加 `"<夾>": "一句說明"`，該檔也 claim、放進 `--files`；中文檔名清單用 `git -c core.quotepath=off` 產 | [patch-and-commit「commit-request 的坑」](patch-and-commit.md) | 11-14 ok-astra、ok-kf |
| 改了共用程式的契約（函式改名、讀表入口、輸出格式）要驗收 | proto8 底下每個 `tests` 夾都跑，「main 原樣」與「main＋改動」各跑一次只看新紅；改了被 mock 的函式先 grep 出所有 patch 它的測試 | [patch-and-commit「驗收跑全套」](patch-and-commit.md) | 11-14 ok-kf |
| 驗收時有紅的，判斷是不是本來就紅 | 經 clean.sh 跑（別在帶 AOS_* 的隊長 shell 跑，會假綠）；紅的在 `git archive HEAD` 乾淨複本同環境重跑，本來紅的轉給擁有線 | [patch-and-commit「驗收跑全套」](patch-and-commit.md) | 11-14 ok-limits |
| 在乾淨複本驗自己的改動 | `git archive HEAD proto8 \| tar -x -C <新夾>` 再疊上要交的檔；`env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONDONTWRITEBYTECODE=1 …` 或經 clean.sh 跑；bin 用複本自己的原始碼編，不從別處抄 | [pitfalls-建置與複本「標準跑法」](pitfalls-建置與複本.md) | 11-14 ok-onboard、ok-astra、ok-limits、ok-sec |
| 改 `proto8/cmd`、`py`、`lib/agent` 的既有檔（存檔活樹就在用） | 備份到 repo 外 → 同夾暫存檔再 `mv` → 多檔照「被 import 的先換」的腳本，每換一檔就 import＋`--help` → 先在乾淨複本預演 | [活樹旁邊「換存檔即生效的檔」](活樹旁邊.md) | 11-14 ok-limits、ok-sec、ok-kmsg |
| 放行別人的 commit | 自己看三樣：`git diff --no-index` 實際差異、測試 log 的結果行、備份等於 HEAD；放行信寫明看過哪一版；hash 回來 `git show --stat` 核 | [交件與放行「放行 commit」](交件與放行.md) | 11-14 head-tools、head-core |
| 改到每隻 agent 都會走的路，要多一層審 | 另派全新的審稿員：只給 diff、規格、一串「成立／不成立＋行號」的邊界問題，只讀不跑 | [審查與實測「另派一隻全新的審稿員」](審查與實測.md) | 11-14 head-core、head-front |
| 寫讀 daemon 表的程式 | 至少一條測試用暫存樹的真 daemon `ctl add` 掛出一列再讀；交件信附那一列的原樣輸出 | [審查與實測「讀 daemon 表的程式」](審查與實測.md) | 11-14 ok-limits、ok-misc |
| 決定一個 commit 要不要隨當晚換樹進活樹 | submit 前決定：pin 是 main 的一個 commit、跳不過中間某筆；不想進就等 pin 釘完再交 | [活樹旁邊「換樹當晚」](活樹旁邊.md) | 11-14 ok-kf、head-tools |
| 封存或搬檔 | 預設留指標頁、不帶 `--rm`；真要移除舊路徑得使用者明說，那種交件排使用者親手跑 | [交件與放行「封存或搬檔」](交件與放行.md) | 11-14 ok-kb |
| 改有合計數字的共用檔（advices README） | 先 claim；數字以交件當下的 HEAD 照各檔實數重算 | [交件與放行「兩線同時改同一份計數」](交件與放行.md) | 11-14 ok-sec、ok-limits |
