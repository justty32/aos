# commit 排隊（commit-queue-1114）：多條線共用一個工作樹時，commit 交給 `commit-request` 一件一件做

← [2026-11-14](README.md)｜[thinking](../../README.md)

## 使用者原話（11-14）

- 「commit這塊，你也可以開始想辦法，同樣，寫程式或派小廝。或是弄個fsm agent掛在你底下」
- 「要想辦法，你可以把你的意見交給fable，讓他幫你規劃」

走了正統流程的精簡版：opus 備料 → fable 設計 → opus 細化計劃 → Argon 審 → 採納表 → 施工。材料都在 [commit-queue-1114/](commit-queue-1114/)：[01 備料](commit-queue-1114/01-備料.md)、[02 fable 稿](commit-queue-1114/02-fable稿.md)、[03 計劃](commit-queue-1114/03-計劃.md)、[04 Argon 原文](commit-queue-1114/04-Argon原文.md)、[05 採納表](commit-queue-1114/05-採納表.md)。

## 結論

- **形式**：不常駐，沒有 hook、沒有 agent-fsm。`wf/tools/commit-request` 是申請指令，申請者自己在 Bash 裡跑。它拿一把 `flock`（同時只做一件），當場做完，最後一行印 JSON 結果（commit 雜湊或錯誤原文）。理由（fable）：一天十幾件不需要背景行程；掛在頂層的 on_clock hook 會被頂層的長 turn 拖住；這件事也不需要腦。
- **在哪裡組 commit**：在 repo 外的快取樹（`~/.cache/aos-commit-queue/<repo 路徑雜湊>/tree`，有自己的 index）。快取樹的內容是 HEAD＋這次點名的檔＋共用索引檔的操作，`index_gen --apply` 在這棵樹上跑，所以生成物只反映這一次。之後 `commit-tree` 出新 commit，`update-ref` 用 CAS 推進 main。用 `GIT_DIR`／`GIT_WORK_TREE`／`GIT_INDEX_FILE` 指過去，不開分支，也沒有 worktree 中繼資料。
- **寫回共用工作樹**：
  - 生成物寫成新版。
  - 三份共用索引檔：工作樹那份若沒被動過就換成新版；有別人沒 commit 的字，就做三方合併，保住那些字。
  - 共用 `.git/index` 只改這次 commit 的路徑，一次寫完。別人 staged 的東西原封不動。
- **共用索引檔不收整檔、只收操作**：`day_upsert`（日索引一列）、`month_bump`（月索引那天：份數加一、摘要接一段）、`log_upsert`／`log_delete`（SESSION-LOG 一行）。全部冪等。
- **衝突**：開工時 `claim`。別條線 claim 著的檔，`claim` 與 `submit` 都會 BLOCKED，並回是誰、claim 了幾分鐘。沒 claim 的檔照樣放行，只回警告。
- **訊息原樣**：trailer 由申請者寫，排隊機制不改。

## 申請者用法（各線照這樣改）

```
CR=~/repo/aos/wf/tools/commit-request          # --files／--rm 的相對路徑一律從 repo 根算，不管 cwd

# 開工時：宣告要改的檔（別條線已 claim 會回 BLOCKED 與對方線名，去信協調）
$CR claim --line ok-kf proto8/py/foo.py proto8/thinking/2026-11/14/kf.md

# 交 commit：訊息檔自己寫好 trailer；共用索引檔用 --op，不要手改、不要放進 --files
$CR submit --line ok-kf --files proto8/py/foo.py proto8/thinking/2026-11/14/kf.md --msg-file /path/msg.txt \
  --op '{"op":"day_upsert","date":"2026-11-14","name":"kf","link":"kf.md","summary":"一句話"}' \
  --op '{"op":"month_bump","date":"2026-11-14","segment":"摘要一段"}' \
  --op '{"op":"log_upsert","key":"- **open｜通用 kernel 框架","text":"- **open｜通用 kernel 框架**：…整行…"}'
# 刪檔：自己先在工作樹刪掉，再 --rm 路徑；改名＝--rm 舊＋--files 新
# 先看會進什麼：加 --dry-run
# 出問題：$CR doctor（--repair 補完被中斷的那件）；$CR claims；$CR release --line ok-kf --all
```

- exit 0＝DONE（JSON 的 `commit` 是雜湊）；2＝BLOCKED（claim 衝突、檔沒改、等鎖時又改了、操作套不上）；3＝申請不合格；4＝`index_gen` 失敗（附原文）；5＝忙（等鎖 120 秒逾時）；6＝repo 狀態不對（HEAD 不在 main、merge 進行中、main 一直被人推）。
- 不要再 `git add`，也不要自己跑 `index_gen --apply` 或手改三份共用索引檔（`proto8/thinking/<月>/README.md`、`<月>/<日>/README.md`、`wf/SESSION-LOG.md`）；生成物也不要放進 `--files`，排隊會自己重生。
- 同一條 submit 重送（例如 Bash 逾時重跑），會回 DONE `AlreadyCommitted` 與原雜湊。

## 測試（`~/code/cq-1114`，每次 `git clone` 真 repo 出一份新的 run 夾，不碰真 repo）

`wf/tools/tests/test_commit_queue.sh <來源 repo> <repo 外的暫存夾>` 跑出 **48/48 綠**。用 `CQ_OVERLAY="wf/tools/index_gen.py"` 把還沒進 main 的 index_gen 修正先 commit 進 clone。

| 案例 | 結果 |
|---|---|
| T1 兩條線同時申請（兩個行程並行） | 兩件都 DONE，main 前進兩格，各自只含自己的檔；日索引列與 SESSION-LOG 行都在；訊息、trailer 原樣 |
| T2 共用 index 裡有別人 staged 的檔 | 沒進 commit，最後仍是 staged |
| T3 索引列合併 | 兩條線的列都進 HEAD；工作樹上有人手加沒交的一列，HEAD 沒有、工作樹保住、也沒被 stage；月索引份數 +1、摘要接一段；同一段再交一次＝沒東西可 commit |
| T4 衝突擋下 | A claim 的檔，B 的 claim 與 submit 都 BLOCKED，回 holder；main 不動；A 自己交得過，claim 自動放掉 |
| T5 新檔沒一句話 | exit 4、附 `DescMissing` 原文；main、共用樹不動 |
| T6 處理中有人手動 commit | CAS 失敗、重做、DONE，兩個 commit 都在 |
| T7 update-ref 之後被殺 | `doctor --repair` 補回共用 index 與工作樹的生成物 |
| T8 生成物 | `wf/tools/_index.json` 有這次的新檔，沒有別條線還沒交的檔 |
| T9 | `--dry-run` 不動 main；檔沒改＝BLOCKED；共用索引檔或生成物放進 `--files` 會被拒 |
| T10（Argon 意見） | 改名不重複列；新的一天用範本開日索引；同一申請重送＝AlreadyCommitted；只改權限也算改動；等鎖時又改＝BLOCKED |

一件約 0.26 秒（第一次要建快取樹，約 120 MB）。

測試中抓到兩個問題，都已修：

1. `update-index --refresh -- <路徑>` 會把工作樹內容 stage 進去。這是 `doctor` 列出來的；改成不帶路徑。
2. HEAD 在**乾淨複本**上跑 `index_gen` 會失敗：`index_gen_desc.json` 有 `wf/temp` 那句，但 `wf/temp` 被 gitignore。修法是 `index_gen.py` 對「不存在但被 `.gitignore` 涵蓋」的手寫路徑不報 `DescMissing`。只放寬，真 repo 上輸出不變。

## 頂層要做的

- **不必掛 hook，也不必掛 agent**；kernel_gate 不用動。
- 選做：
  - 叫起來短一點：`ln -s ~/repo/aos/wf/tools/commit-request ~/.local/bin/commit-request`（repo 外，頂層決定）。
  - 寄信給各 ok-*：照上面「申請者用法」改用 `commit-request`，開工先 claim。
  - 06「任務書必貼的硬規則」第 7 條仍寫 `git commit -F -- 檔`，要不要改成 `commit-request submit`，由頂層決定（那是任務書範本）。
  - 護欄（fable 提，沒裝）：`.git/hooks/pre-commit` 一律拒絕、提示改用 commit-request；排隊走 `commit-tree` 不受影響，人要手動 commit 用 `--no-verify`。要裝由頂層或使用者點頭。

## 沒做／留著的

- `--notify <aos 名>`（順手寄 aos 信）沒做，因為結果已經同步印在申請者的 Bash。
- `--strict`（沒 claim 就擋）沒做，等各線養成習慣再開。
- `--from-tree <夾>`（讓想隔離的線從自己的 clone 交檔）沒做。
- 共用工作樹上的三方合併有衝突時，退回「在工作樹那份上重套操作」並警告，沒有更細的處理。

## 驗收

本機制自己的 commit，是在真 repo 上用 `commit-request submit` 交的第一件（雜湊見 git log 中「commit 排隊」那筆）。
