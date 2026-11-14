# commit 排隊：fable 設計稿（原文照錄）

← [commit-queue-1114](../commit-queue-1114.md)｜涵蓋：fable 只讀備料寫的設計稿——形式 (c) 申請者自己拿 flock 當場做、repo 外乾淨副本組 commit、共用索引檔收操作、claim 擋衝突、邊緣狀況表

## 結論

- **形式選 (c)，不要常駐者**：申請指令自己拿 `flock` 當場做完，結果直接印在申請者的 Bash 裡。理由是一天十幾件不需要背景行程，也不會被頂層的長 turn 拖住。
- **commit 在 repo 外的乾淨副本上組**，用 `commit-tree` 加 `update-ref` CAS 推進 main，再把結果補回共用工作樹。理由是只有「HEAD＋這次的檔」的樹，才能讓 index_gen 的生成物只反映這一次。
- **三份共用索引檔只收「操作」不收檔**；衝突靠「開工先 claim」預防，申請時再用快照核對。
- 這份只讀了備料，沒看 repo，也沒跑任何東西；下面的假設要在施工第一步驗掉。

## 假設（施工前先驗）

- A1：`index_gen.py` 以自己所在位置或 cwd 找 repo 根，只讀進版控的檔；設了 `GIT_DIR`／`GIT_WORK_TREE`／`GIT_INDEX_FILE` 後，在副本裡跑的結果與在乾淨共用樹跑一致。驗法：副本對到 HEAD 後跑檢查模式，應回報無差異。
- A2：生成物路徑只有兩類：`**/_index.json` 與 `wf/knowledge/code-map/**`。
- A3：新檔缺第一行一句話時，index_gen 檢查模式會報錯或可辨識；不會的話，排隊自己只檢查「第一行非空」。
- A4：repo 沒有必跑的 commit hook，也沒開 gpg 簽章（`commit-tree` 不跑 hook）。
- A5：月索引的「份數」等於日索引表的列數；不成立就改成單純加一。
- A6：SESSION-LOG 新行加在「## 最新進度」段尾；月索引表按日期遞增排列。
- A7：「不刪檔」指的是 repo 與活樹；排隊自己的快取夾 `~/.cache/aos-commit-queue/` 可以自由清理重建。
- A8：各線都能執行 `~/repo/aos/wf/tools/` 下的指令，家機有 `flock(2)`。

## 題 1：誰來跑

- 一支程式 `wf/tools/commit_queue.py`，加薄殼 `wf/tools/commit-request`；沒有 daemon、hook、agent-fsm。
- 鎖是 `~/.cache/aos-commit-queue/lock` 上的 `flock`。行程死掉核心自動放鎖，沒有殘留鎖問題。
- 鎖檔內容寫持有者的線名、pid、時間，只供顯示。
- 等鎖預設 120 秒，逾時回「忙碌，目前是誰」。
- 結果以最後一行 JSON 印在 stdout，STATUS 沿用信的用詞（DONE、BLOCKED、FAILED），加上 exit code。
- 回信不是必要；之後可加 `--notify <收件者>` 讓指令順手寄一封。
- 不選 (a)：頂層 turn 長時 hook 不跑。不選 (b)：這件事不需要腦，常駐一隻只多一個會壞的東西。

## 題 2：commit 在哪裡組、怎麼寫回、怎麼退

**副本**：`~/.cache/aos-commit-queue/tree`，配自己的 index 檔 `~/.cache/aos-commit-queue/index`。用 `GIT_DIR=~/repo/aos/.git`、`GIT_WORK_TREE`、`GIT_INDEX_FILE` 三個環境變數操作，不留 worktree 中繼資料、不開分支。

**流程**（全程持鎖）：

1. 若有未完成的日誌（見步驟 9），先把上一件補完。
2. 檢查 repo 狀態：HEAD 是指向 `refs/heads/main` 的符號參照；沒有進行中的 merge、rebase、cherry-pick。不符就拒絕。記下 `OLD`。
3. 驗申請（規則見題 4 與題 6）。
4. 副本對齊 `OLD`：`read-tree --reset -u OLD`，並清掉副本裡的多餘檔（增量，很快）。
5. 把清單檔從共用工作樹**照位元組與權限**複製進副本，刪除項則在副本刪掉；同時記下每檔的 blob 雜湊（快照）。
6. 在副本的三份共用檔上套操作（此時是 HEAD 版）。
7. 生成物：先在副本 index `add` 清單檔與共用檔，新檔才會進 `ls-files`；在副本跑 `index_gen.py --apply`；把有變的生成物 `add` 進來，只收 A2 白名單內的路徑；白名單外有檔被改就中止。
8. `write-tree`，再 `commit-tree -p OLD -F <訊息檔>` 得到 `NEW`。訊息原樣不動。
9. 寫日誌 `journal.json`（OLD、NEW、路徑與 blob 清單、階段），然後 `git update-ref -m "commit-queue <線名>" refs/heads/main NEW OLD`。
10. 補共用 `.git/index`：只動這次 commit 的路徑，用 `update-index --add --cacheinfo`，刪除用 `--force-remove`。別人 staged 的別的路徑原封不動。
11. 補共用工作樹：清單檔不動（複製後又被改也不動，只提醒）；生成物一律覆寫成 NEW 版；三份共用檔等於 OLD 版就直接換成 NEW 版，否則在工作樹那份上再套一次同樣的操作（操作可重複套用），套不上就不動、只回警告。
12. 刪日誌，寫一筆稽核紀錄到 `log.jsonl`，印結果。

**怎麼退**：

- 步驟 9 的 `update-ref` 之前失敗或被殺：共用樹、共用 index、main 都沒動過，只留下無主物件；下次開頭重新對齊副本即可。
- `update-ref` CAS 失敗（有人手動 commit 把 HEAD 推前）：從步驟 2 整個重做，最多 3 次。
- `update-ref` 之後失敗或被殺：只往前補、不回退。下一次任何人呼叫（或 `commit-request doctor --repair`）照日誌重做步驟 10、11，這兩步都可重複執行。
- 步驟 10 遇到 `index.lock`：重試約 10 秒；仍不行就回 DONE 加警告「共用 index 待補」，日誌留著。

## 題 3：申請格式與操作

**指令**：`commit-request submit --line ok-kf --files a b --rm c --msg-file m --op '<json>' …`（等效 `--request req.json`；`--dry-run` 做到步驟 8 之前、印 diffstat 與生成物清單）；`claim`／`release`／`claims`／`doctor [--repair]`。

**申請欄位**：`line`、`files[]`（逐檔點名，不收資料夾）、`rm[]`（改名＝rm 舊＋files 新）、`msg_file`（trailer 申請者自己寫）、`ops[]`（可以只有 ops）、`keep_claim`（選填）。

**操作**（以「鍵」認列，重複套用結果不變）：

- `day_upsert {date, link, title, summary}`：日索引表，以 `link` 為鍵；沒有就表尾加 `| [title](link) | summary |`，有就換。
- `month_bump {date, segment}`：月索引那天的列；摘要沒有這段就用分號接在尾端；份數依 A5 重算；那天沒有列就按日期順序新增；寫回工作樹時該列被別人改過，只補缺的摘要段、份數取較大者。
- `log_upsert {topic, text}`：SESSION-LOG「## 最新進度」段，以 `- **<狀態>｜<topic>**` 認行；有就整行換、沒有加段尾。
- `log_delete {topic}`：刪那一行；找不到只回警告。

**規矩**：三份共用檔與生成物不准出現在 `files`（出現就拒絕、提示改用 ops）；各線不再手改這三份、不再自己跑 `index_gen --apply`、不再 `git add`；舊習慣手改了的，排隊從不取工作樹上這三份的內容，對不上的殘留由 `doctor` 列出。

## 題 4：衝突規則

- **claim 為主，管開工時**：紀錄 `~/.cache/aos-commit-queue/claims.json`（同一把鎖）；檔已被別條線 claim 時 claim 失敗、回誰何時；submit 成功後自動放掉已 commit 的檔；不自動過期，頂層可 `release --force`。
- **submit 硬擋**（BLOCKED，exit 2）：清單檔被別條線 claim 著；清單檔相對 HEAD 沒有改動。
- **快照**：持鎖後複製時取；補回時檔又變了，commit 仍有效、只警告。
- **沒 claim 的檔**：第一階段放行但警告「未 claim」；習慣養成後開 `--strict` 硬擋；混寫機器分不出，靠 `--dry-run` 的 diffstat 讓申請者自己看。
- **擋下時回**：一行 JSON，含 `status`、`reason` 代碼、`files`、`holder`、`hint`。

## 題 5：有沒有比排隊更好的整體做法

- 沒有。「排隊＋乾淨副本」已是不開分支前提下最小的做法。各自 clone 當預設不採（`proto8/cmd`、`proto8/py` 存檔即生效，要改在真 repo）；detached worktree 不需要（`GIT_DIR` 加快取夾效果相同、不留中繼資料）。
- 便宜的擴充：`--from-tree <夾>`，步驟 5 改從該夾複製清單檔。
- 建議護欄（需使用者或頂層點頭）：`.git/hooks/pre-commit` 一律拒絕、提示用 commit-request；排隊走 `commit-tree` 不受影響；人要手動 commit 用 `--no-verify`。

## 題 6：邊緣狀況

| 狀況 | 處理 |
|---|---|
| 半途被殺 | `update-ref` 前無副作用；之後照日誌往前補 |
| 鎖殘留 | 用 `flock`，不會殘留；逾時回忙碌（exit 5） |
| HEAD 被手動 commit 推前 | CAS 失敗後重做，最多 3 次；仍失敗回 FAILED |
| HEAD 不在 main、或 merge／rebase 進行中 | 拒絕（exit 6） |
| index_gen 報錯 | 中止，stderr 原文回傳（exit 4）；main 與共用樹未動 |
| index_gen 改到白名單外的檔 | 中止，列出檔名 |
| HEAD 上的生成物本來就過期 | 照樣一起帶進這次 commit，在結果列出 |
| 新檔沒寫一句話 | 拒絕（exit 3） |
| 清單含資料夾、repo 外路徑、被 gitignore 的檔、符號連結 | 拒絕 |
| 訊息檔空或不存在 | 拒絕 |
| 有人在共用 index 留了 staged | 不影響（用自己的 index）；`doctor` 列出，不代為 unstage |
| 共用 `index.lock` 被佔 | 重試；不行就 DONE 加警告，下次補 |
| 刪檔後資料夾空了，舊 `_index.json` 留著 | 施工時實測 index_gen 行為 |
| 副本壞了或被清 | 整個重建 |
| 可執行權限 | 以工作樹為準 |
| 排隊程式自己正被修改 | 跑共用樹上的版本；改它的線先 claim |

**exit code**：0 DONE、1 內部錯誤、2 BLOCKED、3 申請不合格、4 生成器失敗、5 忙碌、6 repo 狀態異常。

## 建議施工分批

1. 核心：鎖、副本、files／rm、`commit-tree`、CAS、補回 index 與生成物、日誌往前補、`--dry-run`。先驗 A1～A4。
2. 三份共用檔的四個操作與工作樹重套。驗 A5、A6。
3. claim／release／claims、`doctor`、`log.jsonl`。
4. 選配：pre-commit 護欄、`--from-tree`、`--notify`、`--strict`。

（原稿的條列表格依 opus 收錄時排版略併，字句未改意思。）
