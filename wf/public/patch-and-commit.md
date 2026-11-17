# wf/public/patch-and-commit — 把暫存樹的改動搬回 main、交 commit-request 的坑

← [wf/public](README.md)｜commit-request 的正式用法在 [07「commit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md#commit)（兩行指令在 [aos-teams 入口第 1 件](../workflows/dispatch/aos-teams.md)），這裡只放踩過的坑；先交小修、放回 repo、放行見 [交件與放行](交件與放行.md)

## 暫存樹的改動搬到已經往前走的 main

在 repo 外的複本（某個舊 commit）做完，要交回時 main 已往前走好幾個 commit：

- **先查上游動了什麼**：`git log --oneline <舊base>..HEAD -- <你的檔>`，有就讀那幾個 commit（例：上游在 argv 插了 `--stack`，你新測試的期待值也要補）。
- **衝突少**：`git archive HEAD | tar -x -C <新夾>`，新夾 `git init`、commit 一次當基準，再 `patch -p1` 套（比 `git apply` 寬鬆）。套不上的 `.rej`／`.orig` 搬到旁邊的 `rejects/` 夾（不刪），再手動合。
- **同一段被別線改過、檔很多**：在 /tmp 建一個小 git 三方合併：主分支放「複本當初的 base」並 commit；開分支放「複本改後」並 commit；回主分支放「main 現在」並 commit；`git merge` 那條分支，只手修衝突，合好的檔複製回 repo。
  - 條文檔常一整段一行，別線改一個字就整段衝突：三版先用句號切成一句一行，`git merge-file` 合完再接回原來的行。
- **匯出補丁**濾掉 `__pycache__`：新檔先 `git add -N`，再 `git diff -- . ':(exclude)**/__pycache__/**' > x.patch`。生成的 `_index.json` 不放進 patch（commit-request 會擋），誤放了用 `git diff -- <那檔> | git apply -R` 還原。
- **交之前**：在新 base 的複本上整套測試跑一次（下一節）；舊 base 上本來就紅的，在沒改的 base 重跑確認不是你造成的；會動到錨點的再跑 `wf/tools/check_anchors.py`。
- **進主 repo**：先 `git apply --check x.patch`，拿到准許才 `git apply`，主 repo 再跑一次測試，再走 commit-request。

## 驗收跑全套，不能只跑你改的那幾夾

改了共用程式的契約（函式改名、讀表改走另一個入口、輸出格式變了），紅的常在**別的資料夾**：mock 舊函式或比對舊字串的測試（改 `cmd/aos-agent`，紅在 `impls/aos-daemon/tests`；改 lib 的路徑格式，紅在 `templates/tests`）。

1. 在 repo 外的乾淨複本（`git archive HEAD | tar -x`，impls 的 bin 照 [pitfalls-建置與複本「標準跑法」](pitfalls-建置與複本.md) 用複本自己的原始碼編）把 proto8 底下**每一個** `tests` 夾都跑過（`find proto8 -type d -name tests`），跑前清掉全部 `AOS_*`。
2. 同一支腳本跑兩次：「main 原樣」與「main＋你的改動」，逐夾比對，只看**新出現的紅**；原本就紅的另外列。
3. 改了被 mock 的函式，先 `grep -rn "'舊函式名'" proto8 --include=*.py` 找出所有 patch 它的測試，一起改。
4. 想快可以先跑受影響的幾夾，但**送 commit 前一定全套對照一次**。

**環境沒清會假綠**：隊長的 shell 帶著 `AOS_DAEMON`、`AOS_STACK`、`AOS_KERNEL`，有些 mock 不完整的測試靠它們撐過去，在隊長 shell 裡是綠的、隊員經 clean.sh 跑就紅，看起來像施工弄壞的。

- 驗收也要和隊員一樣經 clean.sh（[06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)：用 bash 逐一 unset 所有 `AOS_*`）。
- 看到紅的，先在乾淨複本（`git archive HEAD proto8 | tar -x -C <自己暫存夾裡的新夾>`）用同樣的環境只跑那幾項，判斷是不是本來就紅。本來就紅的轉給擁有那支程式的線，不在自己的施工裡順手修。
- 回報寫明在什麼環境下綠，例「clean.sh 下 112 項，2 項是 HEAD 既有的紅」。

## commit-request 的坑

用 `wf/tools/commit-request` 交，這次有新資料夾、新檔、中文檔名，或要改共用索引時：

- **一定先 `--dry-run`**：會列出 index_gen 一起生成的檔。夾裡檔數過門檻時多出一份新的 `_index.json` 是正常的，不用手改。
- **新資料夾只有 `_entry`（沒有 README、_tooldef 這類檔）**：dry-run 報 `GeneratorFailed: index_gen: error: DescMissing <夾>/`。在 `wf/tools/index_gen_desc.json` 加一行 `"<夾路徑>": "一句說明"`（照 mail_notify 那行寫），這個檔也 claim、也放進 `--files`；或給新夾一份 README。
- **claim 檔案本身，不要 claim 資料夾**：claim 資料夾 submit 照樣成功，但會出 `not claimed` 警告。submit 後 claim 就用掉了，同一個檔下一批要重新 claim。交完資料夾的 claim 可能還在：`commit-request claims` 查，再 `release`。
- **新檔也要 claim**：沒 claim 只給 warning、不擋，但別條線不知道你在改。
- **中文路徑一律用 `git -c core.quotepath=off` 產**（`status`、`diff --name-only`）：直接從 `git status` 抄的是轉義過的字串，claim 存成那串、蓋不到真檔，`--files` 也對不上。claim 後看一眼 `commit-request claims`。
- **日索引、月索引、SESSION-LOG 只能用 `--op`**（`day_upsert`、`month_bump`、`log_upsert`…，寫在 `--ops-file ops.json`）；日索引的 README 放進 `--files` 會 `RequestBad`。
- **SESSION-LOG 同一行可能好幾條線共用**：`log_upsert` 整行換掉，要先用程式讀出現在那一行，只換自己那段，別人的字不動。
- **檔名叫 `_index.json` 的**：知識庫以外的是生成物，不收、由排隊重生；`proto8/knowledge/` 底下手寫的照一般檔交。
- **設計階段不要先 claim 程式檔**：任務書寫「施工開始才 claim」。設計階段 claim 會擋住同一批檔上正在施工的線。
- **用完沒改就放掉**：claim 著不改，別線就跟著晚交。
- **「會動某檔」不等於「claim 了某檔」**：轉述給別部或使用者之前，自己跑 `commit-request claims` 看；回別部時直接貼線報的 claim 清單。
