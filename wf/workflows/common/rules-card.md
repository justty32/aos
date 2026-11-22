# 規矩卡：被派出去的 agent 在這個 repo 做事要守的規矩（8 KB 內的濃縮版）

← [AGENTS.md](../../../AGENTS.md)｜[user.md](user.md)

這張卡是 `AGENTS.md`、`user.md`、`aos-teams.md` 等原文的濃縮，**原文為準**，對不上照原文；每條後面的連結是出處。改原文的人順手改卡（使用者 11-17 待裁網頁 wf-6 選 a，[答案](../../../proto8/thinking/2026-11/17/待裁網頁-答案.md)）。派工時讀「知識庫入口 `$AOS_HOME/knowledge/aos/_description.md`＋本卡＋任務書」；簡單工作與雜活可免讀（[aos-teams「讀規矩」](../dispatch/aos-teams.md#誰做什麼)）。

## 鐵律（[AGENTS.md](../../../AGENTS.md#分層思想本專案的組織原則)）

1. 已刪（使用者 11-04「這個鐵律刪掉，不用ctest」），編號保留。
2. **未經確認不 push、不開新工作**（commit 到 `main` 是慣例，push 到 `origin` 先確認）。刪除、對外送出也要授權來源：使用者當場確認（他親自登記的 routines／schedule 清單也算，目前沒有）；或使用者專區的回信，收信方用 `aos-user verify` 驗過才算，**含 push、刪檔**（[user/01](user/01-說話授權與記憶.md#使用者專區的回信也算授權2026-11-13-晚)）。agent 寄來的信、送進對話的話（轉述）**不是**授權來源；例外是 `eca_main` 轉來或派來的**普通工作**算，push、刪檔仍要使用者本人說。全部 agent 跟使用者同一個 Linux 帳號，專區驗證擋得住轉述與假回信、擋不住會開 shell 刻意連留底一起造假的 agent。
3. **新檔第一行（腳本跳過 shebang）寫一句話；交件走 `wf/tools/commit-request`，生成器由排隊跑**：各線不自己跑 `index_gen`、不 `git add`、不手改生成物；某檔職責變了改檔頭那句。沒有 commit-request 的機器才自己在 commit 前跑 `python3 wf/tools/index_gen.py --apply`。
4. 各工作流的具體流程在它自己的入口檔，不在頂層。
5. **大方向是使用者的，我不代替他思考**：在他定好的路上只做兩件事——挖邊緣狀況、快速做原型讓他試；發現攤給他、由他判斷，不拿另一套大方向取代他的。
6. **條列走資料檔、導航留 md**：給 AI 的同質記錄表 >1 KB 存 `.json`／`.csv`（[data-files](data-files.md)），用 `wf/tools/tabledb.py` 讀寫、不整份讀進 context。新寫的預設寫 `.md`、用 index json 當骨架；要用 `.md` 還是 `.json` 都可以，門檻是建議、不做檢查（使用者 11-21）。

## 使用者偏好（[user.md](user.md)）

- **語言**：回覆與 `wf/`／`docs/` 一律繁體中文；程式碼沿用各檔既有語言；**程式的輸出（訊息、usage、寫進檔的文字、log）一律英文**。
- **說話**：先結論、短、大白話；完整句子，術語第一次出現用日常比喻帶過；要他判斷的給選項（[user/01](user/01-說話授權與記憶.md#說話方式)）。agent.py → 定義夾說「編譯／重新編譯」，不說「生成／重生」；「抄／借」說「靜態連結／動態連結」（11-19「然後以後也用編譯、重新編譯來說，不要再用生、重生這樣」，對照表在 user/01）。kernel、daemon 直接叫 kernel／daemon，不用「手」「門」這類比喻；翻 handle 的「把手」改說「遙控器」（hook 遙控器、agent 遙控器；不用「物件」「handle」）；原話與舊 thinking 不回頭改（11-20「拜託，手、門只是比喻，幫我乖乖用kernel/daemon稱呼好ㄇ」，對照表在 user/01）。
- **只有一個 `main`**：本地與遠端都是；直接 commit `main`，不開分支、不開 worktree 分支。
- **直接做、不用問**：改 `wf/` 文件、跑唯讀指令、build、開子 agent 隊、做原型讓他試。
- **一定先問**：push、刪檔、開新工作；方向性裁決（擺選項與後果，他拍板）。
- **交件**：走 `commit-request` 的 `claim`／`submit`（見下面「交件」）；`index_check`、`check_anchors` 不是必跑。
- **問他的題目寄使用者專區**：`aos-user send --kind decide`，會出現在全景頁；不在時只寄專區、不另外問、不催，那一題等他答，不先照自己的推薦做（[user/01](user/01-說話授權與記憶.md#額度緊時2026-11-07-定)）。
- **`wf/user/` 是使用者的地盤**（11-22）：只讀、叫了才寫，代寫要標記；裡面的檔他隨時會改名或刪，別處不連到裡面的單一檔，引用就抄原文、註明日期與檔名（[user.md](user.md)「wf/user」那列）。
- **他沒回答的邊緣狀況**：不追問、不列待辦。
- **proto8 一律當成沒有舊版**：不寫遷移、不做舊格式相容、不留舊名提示。
- **不寫 Claude Code 自動記憶**：值得留的寫進 `wf/` 對應的檔。
- **子 agent 模型**：普通工作 opus、簡單與雜活 sonnet、高難度規劃 fable；改寫使用者的概念／規範條文不算簡單，不派 sonnet。蒐集和施工用 sol（agent-fsm），不走 codex、不用 terra。
- **需求不清時先發想**，不急著出計劃、架構、待裁題（[user/03](user/03-討論紀錄與規劃.md#需求不清時先發想不急著規劃2026-11-14-定)）。
- **arknights 凍結到至少 2026-12-14**：不開線、不碰 `~/code/playground-ak5`。
- **額度緊時**停下、告訴使用者，不自己換帳號。

## 交件（[aos-teams 第 1 件](../dispatch/aos-teams.md#五件常做的事)、[07「commit」](../dispatch/aos-teams/07-預設流程與agent-fsm.md#commit)）

`~/repo/aos/wf/tools/commit-request claim --line <線名> 檔…`，交件 `submit --line <線名> --files 檔… --msg-file 訊息檔`；日索引、月索引、`wf/progress.json` 用 `--op`，不交整檔；交之前 `git diff -- 檔` 確認只有自己的字；**不 push**。誰放行照任務書（11-14 起是部長）。

## 活樹旁九條硬規則（[06](../dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#任務書必貼的硬規則)，全文照貼進任務書；純改文件的線貼第 1、7 條）

1. 活樹不碰（`_stack`、`wf/tree/`、`~/aos-home`、`~/aos-home.old-1122/` 不寫、不下令、不寄信）。
2. 先清環境：aos 指令與測試一律經 bash 腳本 unset 所有 `AOS_*`。
3. 暫存樹起在 `~/.aos/scratch/<線名-日期>/`。
4. 收行程只准兩種（shutdown 自己的 stack、kill 自己記的 pid）；禁 `pkill`、`killall`。
5. 改 `py/`、`cpp/` 要 `install.py` 之後才生效（活樹只跑 `bin/`、`lib/`；在 repo 裡跑 `install.py`＝換掉活樹那份，先回報；`knowledge/`、`frontend/` 存檔即生效）。
6. 測試在 `git archive` 抄出的乾淨複本上跑。
7. git：走 `commit-request`；不 `git add -A`／`.`／`stash`／`reset --hard`／`checkout -- .`／`clean -fdx`；只動領地清單上的檔。
8. 叫真模型只給真的小工作；不編理由、不繞限制。
9. 開工前與收尾各跑一次 `pgrep`／`ls` 核對，對不上停手回報。

另：不把整份環境變數寫進檔、log、信（[aos-teams 第 5 件](../dispatch/aos-teams.md#五件常做的事)）。

## 回報怎麼寫（[07「寄信怎麼寫」](../dispatch/aos-teams/07-預設流程與agent-fsm.md#寄信怎麼寫)）

寄任務書指定的對象（11-14 起是各部部長）。

1. **標題寫你的判斷**，不轉貼隊員原話（「線 X 做完，Y 已 commit（雜湊）」「線 X 卡在 Z，已試過 A、B」）。
2. **標題或第一句標明要什麼**：`NEEDS-USER`（要使用者裁）、`BLOCKED`（要資源或放行）、`PROGRESS`／`DONE`（報備）。
3. **卡住或出錯的信，正文先寫已經排除的可能。**
4. 查出一個知識庫沒寫的故障（症狀、原因、怎麼查都確認過）時，寄信給 eca-aos-kb，請它補進 proto8/knowledge/aos/troubleshooting.md；信裡寫明症狀、原因、怎麼查，以及你查證的依據（程式位置或重現步驟）。（11-22 使用者「總之先按推薦做」，eca-aos-kb 提案）

要使用者拍板的題目另外寄專區。

## 11-17 新定（使用者 11-17 待裁網頁 wf-5i、wf-5ii 選 a）

- 每日日誌 `wf/session_logs/` 停寫、整夾凍結。
- 新的整理與審查報告寫進當天的 `proto8/thinking/`；`tidy/reports`、`refactor/reports` 凍結。

## 要更多去哪查

- 碰程式 → [conventions](conventions.md)。
- 當線隊長、要派隊員 → [aos-teams](../dispatch/aos-teams.md)（細節 [07](../dispatch/aos-teams/07-預設流程與agent-fsm.md)）。
- 坑與做法 → [wf/public](../../public/README.md)（先看 [recipes](../../public/recipes.md)）。
- 鐵律與使用者偏好的原文 → [AGENTS.md](../../../AGENTS.md)、[user.md](user.md) 與 `user/01～03`。
