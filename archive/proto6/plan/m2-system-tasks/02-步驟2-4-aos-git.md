← [第二段：不靠 daemon 的系統級任務與普通程式（草稿，部分已裁定）](../m2-system-tasks.md)（分檔 2/5）｜[上一份](01-現況對不上與步驟1.md)｜[下一份](03-步驟5-6-範本驗收與不做的.md)

## 步驟 2：aos-git 的共通部分

- **要做到**：三個子命令共用的東西——找資料夾、判斷 git 能不能用、怎麼呼叫 git、aos 範圍。
- **依據**：[B-622](../../spec/deferred/git.md)、P-205。
- **做法**：
  - **找資料夾**：`AOS_TICK_CWD`，沒有就 cwd（待問 7）。argv 只認 `open`、`mark`、`close`，其他回 1。
  - **能不能用**：`git` 叫得起來，而且在工作資料夾跑 `git rev-parse --absolute-git-dir` 成功，就算能用。不能用（沒裝、不是 repo）：stderr 一行 `no_git: <原因>`、回 0，不寫擋板。不查 git 版本（這台是 2.43）。
  - **呼叫 git**：一律 `cwd=工作資料夾`；先清掉繼承的 `GIT_*` 環境變數；帶 `-c gc.auto=0 -c maintenance.auto=false -c core.hooksPath=/dev/null -c commit.gpgSign=false`（免得背景整理、hook、簽章卡住）。不帶 `core.fsync`、`safe.directory`（待問 8）。repo 與全域都沒設作者時，帶 `-c user.name=aos -c user.email=aos@localhost`。git 回非 0 就丟例外、回 1（待問 5）。
  - **aos 範圍**（待問 1）：狀態資料夾整個（`AOS_DIRNAME` 空字串時＝整個工作資料夾），扣掉 B-622 固定排除的那張表（`tick.lock`、`tick/`、`tick-blocked`、`jobs/`、`attention/`、`runner-stderr.log`、`summary/published.json`、`mq/failed/`，加上 `requests/`、`responses/`、`work/`），不管 `.gitignore` 寫了什麼。做成一組 git pathspec（`.aos` 加一串 `:(exclude)…`），三個子命令都用同一組。`.gitignore` 忽略的檔本來就不碰。
  - **現在第幾格、前面哪幾項失敗**：讀 `current/`（`read_record()` 展開；`tasks` 只列不是 0 的，照 `index` 對表上位置）；上一格讀 `last/`。
- **要使用者裁定的點**：待問 1、5、7、8。
- **驗收**（併在步驟 3、4 一起測）：
  - 資料夾不是 repo、或 PATH 裡沒有 git：三個子命令都 stderr `no_git`、回 0。
  - 使用者全域開了 `commit.gpgSign=true`、repo 有會失敗的 pre-commit hook：照常 commit。
  - 外面設了 `GIT_DIR=/別處`：照樣操作工作資料夾的 repo。

## 步驟 3：aos-git open 與 close

- **要做到**：沒有存檔點也能用的最小一對——開頭還原上一格沒收好的、結尾提交。
- **依據**：[B-630](../../spec/deferred/git.md)「開格」「收尾」、[B-632](../../spec/deferred/git.md)。
- **做法**：
  - **open**：
    1. 不能用 → `no_git`、回 0。
    2. 上一格沒正常收尾（`last/` 是 `ended:false` 或有 `stopped_after`）**而且 HEAD 已經有 commit**：把 aos 範圍還原成 HEAD 的樣子——追蹤的檔改回去、刪掉的補回來；新多出來的檔要不要刪見待問 4。`last/` 不在、上一格正常收尾、或還沒有任何 commit：不還原。
    3. 清掉上一格留下的 `refs/aos/marks/*`。
    4. 打本格第一個存檔點（步驟 4 的做法；步驟 4 還沒做時這步先跳過）。
  - **close**：
    1. 不能用 → `no_git`、回 0。
    2. 處理最後一組（步驟 4；還沒做時跳過）。
    3. 只把 aos 範圍的改動（含新增、刪除）提交一次，訊息 `aos-tick <seq>`；沒變動不 commit。**不能把使用者自己放進正式 index 的其他東西一起帶進去**：建議 `git add -A -- <範圍>` 再 `git commit --only -m … -- <範圍>`，或用暫時 index（AI 隊挑）。還沒有任何 commit 時由它建第一個。
    4. 刪掉本格的 `refs/aos/marks/*`，回 0。
  - 不另加 `aos-failed:` 那行（只給人看，先不做）。
- **要使用者裁定的點**：待問 4。
- **驗收**（每條都用暫存資料夾 `git init`、表 `[git-open, 任務…, git-close]`）：
  - 任務在 `.aos/data.txt` 寫字：跑完一個 commit `aos-tick 1`，含 `.aos/data.txt`、`.aos/tasks.json`，**不含** `.aos/tick/`、`.aos/tick.lock`。再跑一格沒改東西：不多出 commit。
  - 任務改了工作資料夾裡 `.aos/` 以外的檔：不進 commit、不被還原（`AOS_DIRNAME` 沒設時）。
  - `.gitignore` 沒列 `/.aos/tick/`：紀錄還是不進 commit、`seq` 連續。
  - 使用者先 `git add` 了一個 `.aos` 外的檔：close 的 commit 不含它，它仍在 index 裡。
  - 中間一項建停格檔：close 沒跑、沒 commit；下一格 open 把 `.aos/data.txt` 改回 HEAD 的內容。
  - tick 在任務中途被 SIGKILL（`last/` 是 `ended:false`）：下一格 open 一樣還原。
  - `AOS_DIRNAME=` 空字串：任務改的使用者檔也進 commit；`tick.lock`、`tick/` 不進。
  - 每格最多一個 commit，訊息裡的數字等於 `current/record.json` 的 `seq`。

## 步驟 4：aos-git mark（存檔點）

- **要做到**：把剛結束那一組的失敗擋下來——組裡有一項出現在紀錄的失敗清單（不是 0），就把這組在 aos 範圍寫的東西還原到上一個存檔點，然後打點。後面的組看不到失敗組寫的東西，close 只要提交。
- **依據**：[B-630](../../spec/deferred/git.md)「組與存檔點」。
- **做法**：
  - **存檔點名字用位置**（待問 2）：`refs/aos/marks/<AOS_TASK_INDEX>`。open、close 自己也在各自的位置算「點」（close 不留 ref）。
  - **打點**：把「HEAD 的樣子＋此刻 aos 範圍的樣子」做成一個不掛在任何分支上的暫存提交，記在那個 ref。不動 HEAD、分支、正式 index（建議用 `GIT_INDEX_FILE` 指一個暫時 index：`read-tree HEAD` → `add -A -- <範圍>` → `write-tree` → `commit-tree` → `update-ref`）。還沒有任何 commit 時從空樹開始。
  - **哪一組**：上一個存檔點的位置是 p、自己是 i，組＝表上第 p+1 到 i−1 項。上一個點＝`refs/aos/marks/` 底下比 i 小的最大那個；一個都沒有（表上沒放 `git-open`）就把 HEAD 當上一個點、組從第 0 項算。〔第八批改〕原本寫「組＝紀錄 `tasks` 的第 p+1 到 i−1 筆（紀錄第 k 筆就是表上第 k 項）」，紀錄改成只列失敗的以後不成立，改看下一條的 `index`。
  - **有失敗**（紀錄 `tasks` 裡有一筆的 `index` 落在 p+1～i−1，含 `signal`）：把 aos 範圍還原成上一個點的樣子（含新增、刪除），再打點。沒失敗就直接打點。
  - 不收路徑參數（`aos-git mark <路徑…>` 先不做，待問 3）；不看 argv、不看 `kind`。
  - close 處理最後一組：同上，組＝上一個點之後到 close 前一項。
- **要使用者裁定的點**：待問 1、2、3、4。
- **驗收**：
  - 表 `[git-open, a(寫 .aos/a.txt), mark-a, b(寫 .aos/b.txt 後 exit 1), mark-b, git-close]`：commit 裡有 `a.txt`、沒有 `b.txt`；`b.txt` 之後也不在工作樹。
  - 同上但 `b` 是把 `.aos/a.txt` 改壞再 `exit 1`：commit 裡的 `a.txt` 是 `a` 寫的版本。
  - 兩個 mark 項寫了同一個 `id`：各打各的點，結果跟 id 不同時一樣。
  - 存檔點不是分支（`git branch` 看不到）；格結束後 `refs/aos/marks/` 是空的。
  - 做完一格，`git status` 看不到 aos 造成的「已暫存」變化（正式 index 沒被弄亂）。
