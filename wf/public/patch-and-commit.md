# wf/public/patch-and-commit — 搬回 main、驗收全套、commit-request 的坑、放行與封存

← [wf/public](README.md)｜commit-request 的正式用法在 [07「commit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#commit)（兩行指令在 [aos-teams 入口第 1 件](../workflows/dispatch/aos-teams.md)），這裡只放踩過的坑

## 暫存樹的改動搬到已經往前走的 main

在 repo 外的複本（某個舊 commit）做完，要交回時 main 已往前走好幾個 commit：

- **先查上游動了什麼**：`git log --oneline <舊base>..HEAD -- <你的檔>`，有就讀那幾個 commit（例：上游在 argv 插了 `--stack`，你新測試的期待值也要補）。
- **衝突少**：`git archive HEAD | tar -x -C <新夾>`，新夾 `git init`、commit 一次當基準，再 `patch -p1` 套（比 `git apply` 寬鬆）。套不上的 `.rej`／`.orig` 搬到旁邊的 `rejects/` 夾（不刪），再手動合。
- **同一段被別線改過、檔很多**：在 /tmp 建小 git 三方合併：主分支放「複本當初的 base」並 commit；開分支放「複本改後」並 commit；回主分支放「main 現在」並 commit；`git merge` 那條分支，只手修衝突，合好的檔複製回 repo。條文檔常一整段一行：三版先用句號切成一句一行，`git merge-file` 合完再接回。
- **單檔落後**：`git merge-file -p <我的> <當時的 base> <現在的 HEAD>`（base 用 `git show <archive 的 commit>:檔`）。
- **匯出補丁**濾掉 `__pycache__`：新檔先 `git add -N`，再 `git diff -- . ':(exclude)**/__pycache__/**' > x.patch`。生成的 `_index.json` 不放進 patch（commit-request 會擋），誤放了用 `git diff -- <那檔> | git apply -R` 還原。
- **交之前**：在新 base 的複本上整套測試跑一次（下一節）；舊 base 本來就紅的，在沒改的 base 重跑確認不是你造成的；動到錨點的再跑 `wf/tools/check_anchors.py`。
- **進主 repo**：先 `git apply --check x.patch`，拿到准許才 `git apply`，主 repo 再跑一次測試，再走 commit-request。

## 驗收跑全套，不能只跑你改的那幾夾

改了共用程式的契約（函式改名、讀表換入口、輸出格式變了），紅的常在**別的資料夾**：mock 舊函式或比對舊字串的測試（改 `py/aos/apps/agent`（aos-agent）紅在 `cpp/aos-daemon/tests`；改 lib 的路徑格式紅在 `templates/tests`）。

1. 在 repo 外的乾淨複本（`git archive HEAD | tar -x`，cpp 的 bin 照 [pitfalls「標準跑法」](pitfalls.md) 用複本自己的原始碼編）把 proto8 底下**每一個** `tests` 夾都跑（`find proto8 -type d -name tests`），跑前清掉全部 `AOS_*`。
2. 同一支腳本跑「main 原樣」與「main＋你的改動」兩次，逐夾比，只看**新出現的紅**；原本就紅的另列。
3. 改了被 mock 的函式，先 `grep -rn "'舊函式名'" proto8 --include=*.py` 找出所有 patch 它的測試一起改。
4. 想快可先跑受影響的幾夾，**送 commit 前一定全套對照一次**。

**環境沒清會假綠**：隊長的 shell 帶著 `AOS_DAEMON`、`AOS_STACK`、`AOS_KERNEL`，有些 mock 不完整的測試靠它們撐過去，在隊長 shell 綠、經 clean.sh 就紅，看起來像施工弄壞的。驗收也要經 clean.sh（[06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)）；看到紅的，先在乾淨複本（`git archive HEAD proto8 | tar -x -C <自己暫存夾裡的新夾>`）同環境只跑那幾項，本來就紅的轉給擁有那支程式的線，不順手修；回報寫明在什麼環境下綠，例「clean.sh 下 112 項，2 項是 HEAD 既有的紅」。

## commit-request 的坑

用 `wf/tools/commit-request` 交，這次有新資料夾、新檔、中文檔名，或要改共用索引時：

- **一定先 `--dry-run`**：會列出 index_gen 一起生成的檔；夾裡檔數過門檻時多一份新的 `_index.json` 是正常的。
- **新資料夾只有 `_entry`（沒有 README、_tooldef 這類檔）**：dry-run 報 `GeneratorFailed: index_gen: error: DescMissing <夾>/`。在 `wf/tools/index_gen_desc.json` 加 `"<夾路徑>": "一句說明"`（照 mail_notify 那行寫），這檔也 claim、也放進 `--files`；或給新夾一份 README。
- **claim 檔案本身，不要 claim 資料夾**：claim 資料夾 submit 照樣成功，但出 `not claimed` 警告。submit 後 claim 就用掉了，同一檔下一批要重新 claim；交完資料夾的 claim 可能還在：`commit-request claims` 查，再 `release`。
- **新檔也要 claim**：沒 claim 只給 warning、不擋，但別條線不知道你在改。
- **中文路徑一律用 `git -c core.quotepath=off` 產**（`status`、`diff --name-only`）：直接從 `git status` 抄的是轉義字串，claim 蓋不到真檔，`--files` 也對不上。claim 後看一眼 `commit-request claims`。
- **日索引、月索引、`wf/progress.json` 只能用 `--op`**（`day_upsert`、`month_bump`、`progress_upsert`…，寫在 `--ops-file ops.json`）；日索引的 README、`progress.json` 放進 `--files` 會 `RequestBad`。progress.json 同一條可能好幾條線共用：`progress_upsert` 整條換掉，先讀出現在那一條（`json_get wf/progress.json#/open/<鍵>`），只換自己那段。
- **檔名叫 `_index.json` 的**：知識庫以外的是生成物，不收、由排隊重生；`proto8/knowledge/` 底下手寫的照一般檔交。
- **設計階段不先 claim 程式檔**：任務書寫「施工開始才 claim」，否則會擋住同一批檔上正在施工的線。claim 著沒改就放掉。
- **「會動某檔」不等於「claim 了某檔」**：轉述給別部或使用者之前，自己跑 `commit-request claims`；回別部時直接貼線報的 claim 清單。

## 工作樹有未交的改動，又要先交一個小修

同一檔上有還不能交的工作版，但有一行小修要先進 main（什麼都不刪）：工作版存到暫存夾 → 用「HEAD 版加小修」蓋上去，只交這一檔 → 再蓋回「工作版加小修」。交完 `git show` 確認只有那幾行。

## 把檔複製進 repo：暫存名再改名，交前確認底之後沒人動

- `cp S/f f.<線>-tmp && mv f.<線>-tmp f && cmp S/f f`。
- 交前 `git log <底>..HEAD -- 檔`，或逐檔跟 HEAD 比、不一樣就擋（別人的 commit 會讓暫存樹落後）；落後的照上面「搬到已經往前走的 main」合。
- 跟別線先講好「你的檔／我的檔」；同時要動同一檔就講好誰先交、誰後疊，不混進同一個 commit。
- 活樹當下就吃到的改動（在 repo 裡跑 `install.py`；活樹直接讀的 `proto8/knowledge`、`frontend`）另有備份與順序的規矩，見 [活樹旁邊](活樹旁邊.md)。

## 放行 commit：看三樣；放行的是看過的那一版

放行的人（任務書沒寫就照 [wf/org「誰交件」](../org/README.md#標準流程)，工作室是 eca-aos；11-23 起沒有部長）收到「請放行」時：

1. 不只讀信裡的摘要，自己看三樣：`git diff --no-index -- <repo 檔> <暫存複本的檔>` 看實際差異；`grep -E '^(Ran|OK|FAILED|FAIL:|ERROR:)' <log>` 看測試結果行；改到即時生效的檔再 `diff <(git show HEAD:檔) 備份` 確認備份等於 HEAD。
2. 放行信寫明版本（哪個暫存夾的哪一份），並寫三樣：看過什麼、沒看過什麼、交完要回什麼（hash、備份路徑、輸出尾段）。hash 回來自己 `git show --stat` 核一次再記帳。
3. 偏好檔、鐵律的改動，先給 eca-aos 逐字看 diff 再交，位子不自己先交後報。

線這邊：放行後還要改，先回一句、把差異再給放行的人看；已經交了就對那個 commit 的 `git archive` 乾淨複本補跑全套。

## 兩線同時改同一份計數：後交的以交件當下的 HEAD 重算

有合計數字的共用檔：先 claim，被佔著就 `clock_register +10m` 叫醒自己再試；拿到後看 `git log -3 -- <那夾>`，數字照各檔實數重算，不照寄信時預先算的數。放行的人事先講明「先 claim 的先交，後交的以當下 HEAD 重算」。

## 封存或搬檔：預設留指標頁，不帶 `--rm`

真的 `mv` 走之後，交件要把舊路徑列進 `submit --rm`；帶 `--rm` 的指令 agent 的權限模式會整條擋下，只能請使用者親手跑，這段時間工作樹是半套狀態。所以預設全文抄進 `archive/`、原路徑改成幾行的指標頁，交件只帶 `--files`，也合使用者「不刪」的偏好；只有使用者明說要移除舊路徑才真的搬走，動手前先問 eca-aos（帶 `--rm` 照 [wf/org](../org/README.md#標準流程) 要先問）、預先排好請使用者親手跑，交之前逐一確認每個舊路徑在 `archive/` 都有對應的檔。規矩全文在 [STRUCTURE「archive 規則」](../STRUCTURE.md#archive-規則)。
