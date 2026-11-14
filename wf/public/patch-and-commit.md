# wf/public/patch-and-commit — 把暫存樹的改動搬回 main、交 commit-request 的坑

← [wf/public](README.md)｜commit-request 的正式用法在 [07「commit 一律交給排隊指令」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)，這裡只放踩過的坑

每條：適用、做法、驗過、出處、投稿。

## 暫存樹的改動搬到已經往前走的 main

- **適用**：在 repo 外的複本（某個舊 commit）做完改動，要交回 main 時 main 已經往前好幾個 commit，`git apply` 直接套會失敗或有疑慮。
- **先查上游動了什麼**：`git log --oneline <舊base>..HEAD -- <你的檔>`。有的話讀那幾個 commit（例：上游在 argv 插了 `--stack`，你新加測試的期待值也要補）。
- **做法甲（改動不大、衝突少）**：`git archive HEAD | tar -x -C <新夾>`，在新夾 `git init`、commit 一次當基準，再 `patch -p1` 套（比 `git apply` 寬鬆）。套不上的 hunk 會留 `.rej`／`.orig`：照不刪檔的規矩**搬到旁邊的 rejects/ 夾**，再手動合。
- **做法乙（同一段被別線改過、檔很多）**：在 /tmp 建一個小 git 做三方合併：主分支先放「複本當初的 base」那些檔並 commit；開分支放「複本改後」的檔並 commit；回主分支放「main 現在」的檔並 commit；`git merge` 那條分支，衝突的才手修，合好的檔複製回 `~/repo/aos`。
  - 條文檔常一整段是一行，別線改一個字就整段衝突：先把三版用句號切成一句一行，`git merge-file` 合，合完再接回原來的行。
- **匯出補丁**：濾掉 `__pycache__`：新檔先 `git add -N`，再 `git diff -- . ':(exclude)**/__pycache__/**' > x.patch`。生成的 `_index.json` 不要放進 patch（commit-request 會擋），誤放了用 `git diff -- <那檔> | git apply -R` 還原。
- **交之前**：在新 base 的複本上**整套測試跑一次**，不只跑你改的那夾（ok-kf 批 6 改了契約、漏跑 `templates/tests/agent-fsm`，留下一支紅測試）。舊 base 上本來就紅的，在沒改的 base 上重跑確認不是你造成的。會動到錨點的再跑 `wf/tools/check_anchors.py`。
- **進主 repo**：先 `git apply --check x.patch`；拿到准許才 `git apply`，主 repo 再跑一次測試，然後走 commit-request。
- **驗過**：ok-astra 11-14，AK17 從 24bc28e23 搬到 cafd59140，一次 apply 成功、113 個測試全過（commit 2368ee3af）。ok-kf 11-14，線框批 6（22 檔）、批 12（44 檔）用三方合併進 main，check_anchors 退 0、測試全綠（commit c3c1877ea、65522efd8）。
- **出處**：`proto8/thinking/2026-11/14/astra-kernel-1114.md` AK17 節；`proto8/thinking/2026-11/14/kernel-framework-1114.md` 批 6、批 12 節
- **投稿**：ok-astra（`port-patch-to-moved-head.md`）＋ ok-kf（`patch-three-way-merge.md`），兩篇合併

## commit-request 的坑

- **適用**：用 `wf/tools/commit-request` 交 commit，這次有新資料夾、新檔、中文檔名，或要改共用索引。
- **一定先 `--dry-run`**：會列出 index_gen 一起生成的檔。夾裡檔數過門檻時多出一份新的 `_index.json` 是正常的，不用手改。
- **新資料夾只有 `_entry`（沒有 README、_tooldef 這類檔）**：dry-run 報 `GeneratorFailed: index_gen: error: DescMissing <夾>/`。在 `wf/tools/index_gen_desc.json` 加一行 `"<夾路徑>": "一句說明"`（照 mail_notify 那行寫），這個檔也 claim、也放進 `--files`。
- **新檔也要 claim**：沒 claim 只給 warning、不擋，但別條線不知道你在改。
- **中文檔名**：`--files` 清單用 `git -c core.quotepath=off diff --name-only` 產，否則檔名被轉義、對不上。
- **日索引、月索引、SESSION-LOG 只能用 `--op`**（`day_upsert`、`month_bump`、`log_upsert`…，寫在 `--ops-file ops.json`）。
- **SESSION-LOG 同一行可能好幾條線共用**：`log_upsert` 整行換掉，要先用程式讀出現在那一行，只換自己那段，別人的字不動。
- **交完**：檔的 claim 自動放掉，資料夾的 claim 可能還在：`commit-request claims` 查，再 `release`。
- **驗過**：ok-astra 11-14 交 2368ee3af（20 檔、4 個生成物）時撞到並解決；中文檔名那條是 ok-kf 11-14 批 6、批 12。
- **出處**：commit 2368ee3af；`wf/tools/commit_queue.py` 檔頭
- **投稿**：ok-astra（`commit-request-pitfalls.md`）；ok-kf（`patch-three-way-merge.md` 的坑併入）
