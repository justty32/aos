# 第二段：不靠 daemon 的系統級任務與普通程式（草稿，部分已裁定）

← [plan 入口](README.md)｜正本（除 B-621 外都是 tick 大幅簡化**之前**寫的）：[範本 B-629](../spec/settled/tick/template.md)、[aos-tick-check-task B-621](../spec/settled/tick/check-task.md)（2026-10-01 改寫）、[git B-630／B-622／B-632](../spec/settled/tick/git.md)、[恢復與設定 B-625](../spec/settled/tick/recovery.md)、[清理 B-404](../spec/base/storage.md)｜格式：[tick 協議](../spec/settled/protocol/tick.md) P-204、P-205、P-210、P-213（停格檔）；[P-605](../spec/protocol/ops.md)（`aos-clean`）｜已搬暫緩區：[發摘要 `aos-publish`（B-624 部分、P-206 那列）](../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)、`aos-config-add`（B-625 部分、P-207）｜現在的 tick：[核心](../spec/settled/tick.md)、[慣例 C-08～C-11](../spec/settled/conventions.md)

> **狀態：草稿（2026-10-01），還沒開工。** 2026-10-01 使用者已裁定 `aos-publish` 搬暫緩區、`aos-needs` 改寫成 `aos-tick-check-task`（見文末「裁定紀錄」）；其餘文末「待問」裁定後才照做。下面各步寫的是「建議的最單純版本」；舊 spec 跟現在 tick 對不上的地方集中在「舊規定哪裡對不上」一節。

**做完的樣子**（照建議裁定的話）：在沒有 daemon、cgroup、helper 的機器上，直接跑 `aos-tick <資料夾>`：

- 表上可以掛一項 `aos-tick-check-task a b`：本格 `a`、`b` 都沒出現在紀錄的失敗清單就什麼都不做；有出現就建停格檔，本格後面的項都不跑。不寫 id＝失敗清單非空就停（第八批）。
- 資料夾是 git repo、表上掛 `aos-git open`／`mark`／`close`：每格最多一個 commit `aos-tick <seq>`，只含狀態資料夾（預設 `.aos/`）裡的東西；上一格沒正常收尾，下一格開頭把 `.aos/` 還原；某一組任務失敗，那組在 `.aos/` 寫的東西被還原、不提交。不是 repo 時 `aos-git` 只印 `no_git`、回 0。
- 兩份第二段版範本任務表（沒 git、有 git）照常跑完。

> **POC 總原則**（[plan 入口](README.md)）：默認一切正常——git 指令都會成功、紀錄讀得懂、任務表是對的、沒有人在 tick 外亂改、`id` 不重複。不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。
>
> **結束碼**（[C-08](../spec/settled/conventions.md)）：0＝預料之中；1＝通用錯誤（含用法錯）；`aos-tick-check-task` 建了停格檔也回 0（停格是預料之中），自己的錯回 1；原本 `aos-needs` 的 125 隨改寫拿掉。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。放 [src/py](../src/py/README.md)：入口 `bin/aos-tick-check-task`、`bin/aos-git`（薄殼，`.gitignore` 擋 `bin/`，要 `git add -f`）；程式 `lib/aos_tick_check_task.py`、`lib/aos_git.py`（檔案怎麼切 AI 隊自己定）；測試 `tests/test_check_task.py`、`test_git.py`、`test_template.py`，用 `unittest`。狀態資料夾名一律用現成的 `lib/aos_dirname.py`。
- 任務表寫 `aos-git` 這種裸名字時要靠 PATH 找到 `src/py/bin/`；測試裡把 `bin/` 加到 PATH 最前面，不寫絕對路徑（這樣範本才能原樣用）。
- **`aos-publish`（發摘要）不在這段**：使用者 2026-10-01 裁定搬暫緩區（[B-624 部分、P-206 那列](../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)）；「把這一格總結成 JSON」的 `aos-summarize` 也暫時不做。
- **`aos-config-add` 不在這段**：已決定搬去暫緩區（[P-207](../spec/settled/protocol/tick.md)、[B-625](../spec/settled/tick/recovery.md)「改設定」）。**`aos-clean`、恢復前驗證**做不做見待問 9、10；下面的步驟先照「建議不做」排，沒有它們的步驟。
- **`aos-mq get`／`post` 不在這段**（第四段，要 daemon 通道）。

## 現在的 tick 給系統級任務什麼

第二段的程式只能靠這些，別的（鎖 fd、通道、上下層、帳號、`kind` 檢查）都沒有：

| 東西 | 從哪拿 | 說明 |
|---|---|---|
| 工作資料夾 | 環境變數 `AOS_TICK_CWD` | 這一格 tick 的資料夾絕對路徑。**不能用自己的 cwd**：任務表頂層 `cwd` 會把每一項（含系統級任務）的 cwd 帶走（[B-620](../spec/settled/tick.md)「頂層預設」） |
| 狀態資料夾名 | 環境變數 `AOS_DIRNAME` | 沒設＝`.aos`；空字串＝工作資料夾本身（[C-09](../spec/settled/conventions.md)） |
| 本格第幾格、前面哪幾項失敗 | `<狀態資料夾>/tick/current/`（第九批拆檔：`record.json` 用 `$ref` 指 `ran.json`、`task-exits.json`；用 `aos_tick_record.read_record()` 讀展開後的完整紀錄） | `seq`、`ran`（到目前跑完幾項）、`tasks`（**只列結束碼不是 0 的**，照順序；每筆 `id`、`index`＝表上位置、`exit` 或 `signal`；2026-10-01 第八批起，原本「第 i 筆就是表上第 i 項」不再成立，要照 `index` 對） |
| 上一格有沒有正常收尾 | `<狀態資料夾>/tick/last/`（同上結構） | 正常收尾＝`ended:true` 而且沒有 `stopped_after`；資料夾不在＝不知道 |
| 自己是第幾項、叫什麼 | `AOS_TASK_INDEX`、`AOS_TASK_ID` | 位置從 0 起、一定不重複；id 可能重複（核心不查）、可能是位置字串 |
| 叫停本格 | 建 `<狀態資料夾>/tick/stop`（停格檔） | 後面的項不跑，tick 回 0。`aos-tick-check-task` 就靠它 |

## 舊規定哪裡對不上

舊 spec 寫的時候，tick 還有「鎖 fd 傳給任務」「fsync」「上下層判定」「帳號」「任務表完整驗證」。這些拿掉以後，各程式舊規定的狀況：

| 程式 | 舊規定 | 現在 | 建議 |
|---|---|---|---|
| `aos-git` | 「在不在 tick 內」靠繼承的鎖 fd 核對，不在回 125 `not_in_tick`（B-622、P-205） | 鎖 fd 不傳給任務，**沒有判法**；任務自己去取鎖一定拿不到（tick 握著） | 不判斷（待問 6） |
| `aos-git` | 存檔點叫 `refs/aos/marks/<任務 id>`；id 當不了 ref 名（`.lock` 結尾）算故障 `mark_id_invalid` | `id` 可省（變位置字串）、**重複不查**，重複時存檔點互相蓋掉 | 改用 `AOS_TASK_INDEX` 命名（待問 2） |
| `aos-git` | 「兩個存檔點之間全是 `kind:"system"` 的段，所有改動都算 aos 範圍」，`kind` 照紀錄 `id` 回查任務表（B-630） | 核心不看 `kind`；回查要自己照 B-620 把表解一層；id 重複時查錯項；第八批起紀錄只列失敗的項，照紀錄逐項回查本來就不行，要改照表上位置 | 拿掉，aos 範圍只剩狀態資料夾（待問 1） |
| `aos-git` | 巢狀排除下層 tick 資料夾（B-622） | 上下層判定 B-628 在暫緩區，沒有判準 | 不做 |
| `aos-git` | `-c core.fsync=…`、`safe.directory`、git ≥ 2.36、當機後清 git 鎖檔、HEAD 換分支當故障 | tick 自己都不 fsync；沒有多帳號；默認一切正常 | 不做（待問 8） |
| `aos-git` | 故障時寫擋板檔＋建停格檔、回 1（B-622） | 默認 git 不會失敗 | 只回 1（待問 5） |
| `aos-git` | 在工作資料夾（cwd）跑 | 頂層 `cwd` 會帶走 | 用 `AOS_TICK_CWD`（待問 7） |
| `aos-publish` | 發摘要（B-624、P-206、P-307） | — | **已裁定搬暫緩區**（2026-10-01），這段不做 |
| `aos-needs` → `aos-tick-check-task` | 舊：包裝，前置都 `exit:0` 才 exec 原指令、否則 125（B-621 舊版） | **已裁定改寫**（2026-10-01）：自己一項、沒跑好就建停格檔、都回 0（B-621 新版） | 照新版做；id 重複時看最後一筆 |
| `aos-clean` | 只清「預設 agent／kernel 任務產生的」資料；偵測 `AOS_TICK_LOCK_FD`；直接跑時自己取鎖、自己 commit；清理狀態記在 `state/ops/clean.json`（B-404、P-605） | **POC 沒有 kernel、agent 任務，沒有任何它認得的資料**；鎖 fd 沒有；`state/` 不在新的 aos 範圍 | 第二段不做（待問 9） |
| 恢復前驗證 | 持鎖、照完整 schema 驗 inst 與任務表、驗領域設定，過了才送 resume（B-625） | 標準庫沒有 JSON schema 驗證器；沒有領域設定；POC 默認表是對的 | 第二段不做（待問 10） |
| 範本 | 頭一項 `mq-get`、尾巴 `mq-post`、`clean`（B-629；`summary` 已隨 `aos-publish` 拿掉） | `aos-mq` 第四段才有（要通道） | 第二段版範本拿掉（待問 11） |

## 步驟 1：aos-tick-check-task

- **要做到**：`aos-tick-check-task [<任務 id…>]`，自己是任務表上的一項。讀本格紀錄（第八批起 `tasks` 只列結束碼不是 0 的）：指定的 id 有任一個出現在紀錄的 `tasks` 裡 → 建停格檔 `<狀態資料夾>/tick/stop`、回 0；都沒出現 → 當成功、什麼都不做、回 0（不分辨「還沒跑」，照 POC 默認一切正常，使用者把它排在那些項後面）。不寫 id＝`tasks` 非空就建停格檔。
- **依據**：[B-621](../spec/settled/tick/check-task.md)、[P-204](../spec/settled/protocol/tick.md)（2026-10-01 使用者裁定改寫，見文末「裁定紀錄」）；停格檔照現行 [P-213](../spec/settled/protocol/tick.md)。
- **做法**：
  - 紀錄路徑：`$AOS_TICK_CWD/<狀態資料夾>/tick/current/`（狀態資料夾照 `aos_dirname.name()`；第九批拆檔後用 `aos_tick_record.read_record()` 讀，`tasks` 在 `task-exits.json`）；停格檔建在同一個 `tick/` 底下。
  - 沒有 `AOS_TICK_CWD`、紀錄讀不到：自己的錯，回 1（照 POC 總原則讓 Python 自然丟錯即可，不另外處理）。
  - 比對：紀錄裡的 `id` 先 `str()` 再跟參數比（id 寫成數字時紀錄存的是數字）。id 重複時，只要失敗清單裡有一筆是它就算失敗（第八批起成功的不記，原本「看最後一筆」不再適用）；默認不重複，不另外處理。
  - 停格檔內容一行原因，建議 `check_failed: <第一個沒跑好的 id>`（不寫 id 時用失敗清單第一筆的 id）（核心會印在 stderr 的 `stopped:` 後面）。停格檔已經在（同一格前面有人建過）就照樣覆寫，結果一樣。
  - 停格檔擋掉整格剩下的全部項（使用者接受）。有 git 時這格作廢：`git-close` 不跑，下一格 `git-open` 還原。
- **要使用者裁定的點**：無（已裁定）。
- **驗收**：
  - 表 `[a: true, chk: aos-tick-check-task a, b: 建檔]`：`chk` 回 0（不記進 `tasks`）、沒有停格檔，`b` 照跑；紀錄 `ran:3`、`tasks:[]`。
  - `a` 是 `false`：`chk` 回 0；紀錄 `ended:true`、`ran:2`、`tasks` 只有 `{"id":"a","index":0,"exit":1}`、`stopped_after` 是 `chk`；`b` 沒跑（它要建的檔不存在）。
  - 指定一個還沒跑到的 id（排在後面）：不在失敗清單裡，當成功、不停格（第八批）。
  - 不寫 id：前面全是 0 不停；有一項非 0（或被訊號殺）就停。
  - 不在 tick 裡直接跑（沒有 `AOS_TICK_CWD`）：回 1。
  - `AOS_DIRNAME=st` 時讀 `st/tick/current/`、建 `st/tick/stop`。

## 步驟 2：aos-git 的共通部分

- **要做到**：三個子命令共用的東西——找資料夾、判斷 git 能不能用、怎麼呼叫 git、aos 範圍。
- **依據**：[B-622](../spec/settled/tick/git.md)、P-205。
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
- **依據**：[B-630](../spec/settled/tick/git.md)「開格」「收尾」、[B-632](../spec/settled/tick/git.md)。
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
- **依據**：[B-630](../spec/settled/tick/git.md)「組與存檔點」。
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

## 步驟 5：兩份第二段版範本

- **要做到**：寫出兩份任務表，證明前面幾步串得起來（[B-629](../spec/settled/tick/template.md) 的縮小版，見待問 11）。
- **做法**：

  | 版 | 順序（`id`） |
  |---|---|
  | 沒有 git | 使用者任務…（系統級任務一項都沒有；要前置就自己插 `aos-tick-check-task`） |
  | 有 git | `git-open` → 使用者任務… → `mark-user`（`aos-git mark`）→ `git-close` |

  - 系統級任務照 spec 範例寫 `kind:"system"`（沒人讀，只是標記）。
  - 跟 spec 範本比少了：`mq-get`、`mark-get`（前面沒有 `mq-get` 就沒有東西要隔開）、`mq-post`（第四段）、`clean`（待問 9）。`summary`（`aos-publish`）2026-10-01 已從 spec 範本拿掉。
  - 放哪：寫在 [src/py README](../src/py/README.md) 當例子，測試用同一份內容。spec 的 [範本範例檔](../spec/protocol/examples/tick/tasks.template.valid.json) 是完整版（2026-10-01 已跟著拿掉 `summary`、`aos-needs` 改成一項 `aos-tick-check-task`），其餘不改（待問 12）。
- **要使用者裁定的點**：待問 11、12。
- **驗收**：
  - 沒有 git 版在不是 repo 的資料夾跑三格：每格回 0，`seq` 1～3。
  - 有 git 版在 repo 裡跑三格，每格使用者任務改 `.aos/data.txt`：三個 commit `aos-tick 1`～`3`，每個 commit 裡的 `data.txt` 是那一格寫的。
  - 有 git 版放在**不是** repo 的資料夾：`aos-git` 三項都印 `no_git`、回 0（不進紀錄的 `tasks`），其他結果跟沒有 git 版一樣（B-632）。
  - 有 git 版裡使用者任務失敗：它寫進 `.aos/` 的東西被 `mark-user` 還原、不進 commit；`git-close` 照樣提交其他的。
  - 有 git 版裡插一項 `aos-tick-check-task` 而它沒過：建停格檔，`git-close` 沒跑、沒 commit；下一格 `git-open` 還原。

## 步驟 6：整段驗收

- 步驟 1～5 的驗收寫成 `tests/test_check_task.py`、`test_git.py`、`test_template.py`，一條指令跑完；不要 root、網路、daemon，全部暫存資料夾。git 測試在 `HOME` 指到暫存資料夾的環境跑，免得吃到使用者的全域設定（另外單獨測「全域開了簽章」那條）。
- 原有的測試照樣全過；`check_ids.py --strict`、`wf-lint` 照舊。
- 做完補 [src/py README](../src/py/README.md) 的檔案表與用法。

## 這段不做的，先怎麼擋著

| 不做 | 這版的樣子 | 什麼時候 |
|---|---|---|
| `aos-git` 判斷「在不在 tick 內」（`not_in_tick`）、`record_missing` | 不判斷；在 tick 外直接跑風險自負，讀不到紀錄就自然丟錯 | 鎖 fd 傳給任務回來時（暫緩區） |
| 「全是 `kind:"system"` 的段都算 aos 範圍」 | aos 範圍只有狀態資料夾；系統級任務要被提交就把東西寫進狀態資料夾 | 待問 1 |
| `aos-git mark <路徑…>` | 不收路徑；使用者的檔要進 git 就自己 commit，或用 `AOS_DIRNAME=` 空字串 | 待問 3 |
| `aos-git` 故障時寫擋板＋停格檔 | 回 1；後面的項照跑 | 待問 5 |
| git 的 fsync 參數、`safe.directory`、版本檢查、清 git 鎖檔、HEAD 換分支檢查 | 都沒有 | 待問 8 |
| 巢狀排除下層 tick 資料夾 | 沒有；下層資料夾如果放在 `.aos/` 外，本來就不在範圍 | 上下層判定回來時 |
| commit 訊息的 `aos-failed:` 行 | 沒有 | 之後 |
| `aos-publish`（發摘要）、`aos-summarize`（把這一格總結成 JSON） | 都沒有 | 已裁定暫緩（2026-10-01）；之後若要，方向是「總結這一格成 JSON」，名字不用 publish |
| `aos-clean` | 範本沒有這項 | 待問 9 |
| 恢復前驗證 | 沒有工具；`aos-tick` 自己的 `bad_table` 與跑到某項展開失敗就是現有的檢查 | 待問 10 |
| `aos-config-add` | 改 `config/` 就直接改檔 | 已決定暫緩 |
| `aos-mq get`／`post` | 範本沒有這兩項 | 第四段 |

## 待問

下面都還沒裁定（使用者 2026-10-01：git 相關的 1～8 還在想）。每條附建議；建議都是往「最單純」砍。已裁定的見下一節「裁定紀錄」。

1. **git 要提交哪些東西？** 舊規定有三種：狀態資料夾（`.aos/`）、「兩個存檔點之間全是系統級任務時，那段改的所有檔」、任務用 `mark <路徑>` 指名的檔。第二種要回頭查任務表每一項的 `kind`，可是 tick 現在根本不看 `kind`、`id` 也可能重複而查錯。**建議**：只留第一種——git 只管狀態資料夾（`AOS_DIRNAME` 空字串時就是整個資料夾，照之前的裁定）。系統級任務要被提交，就把檔寫在狀態資料夾裡。
2. **存檔點用什麼命名？** 舊規定用任務 `id`，但 `id` 可以重複、可以是 `x.lock` 這種 git 不收的名字，都要另外處理。**建議**：改用任務在表上的位置（`AOS_TASK_INDEX`，0、1、2…），一定不重複、一定合法，`mark_id_invalid` 這個錯就不存在了。
3. **`aos-git mark <路徑…>`（讓使用者任務把自己的檔加進提交範圍）要不要做？** 要做就得找地方記住「這格加了哪些路徑」，跨好幾個程序。**建議**：先不做。使用者的檔要進 git，自己 commit 或用空字串的 `AOS_DIRNAME`。
4. **還原時，新多出來的檔要不要刪？** 例如上一格當機前在 `.aos/` 新建了一個檔，下一格開頭還原時刪不刪；存檔點還原失敗組時也一樣。不刪的話，作廢那格新寫的東西會留下來（例如第四段的待送訊息會被送出）。**建議**：刪（只刪範圍內、沒被 `.gitignore` 忽略的新檔）。代價：`AOS_DIRNAME` 空字串時，使用者在作廢那格新建的檔也會被刪，照「空字串＝全部歸 aos」接受。
5. **`aos-git` 出錯（git 指令失敗）時怎麼辦？** 舊規定：寫擋板檔（之後每格都擋）＋建停格檔（本格後面不跑）＋回 1。**建議**：POC 只回 1、不寫擋板也不建停格檔（默認 git 不會失敗）。代價：close 失敗時後面的項照樣跑（第二段版範本 close 後面已經沒有項；`aos-publish` 已暫緩）；第四段有 `mq-post` 時再看要不要加回停格檔。
6. **`aos-git` 要不要判斷「我是不是在 tick 裡被叫的」？** 舊做法靠繼承 tick 的鎖，現在鎖不傳給任務，判不了。**建議**：不判斷。人手在 tick 外跑 `aos-git close` 就真的會 commit，風險自負。
7. **系統級任務在哪個資料夾做事？** 舊規定寫「在工作資料夾（cwd）跑」，但任務表頂層 `cwd` 現在會改掉每一項的 cwd（含系統級任務）。**建議**：一律看 `AOS_TICK_CWD`；沒有這個變數（人手直接跑）才用自己的 cwd。
8. **git 的保險參數砍到哪？** **建議**：留「清掉 `GIT_*`、關背景整理、關 hook、關簽章、沒設作者就用 `aos <aos@localhost>`」（便宜、而且不留會真的卡住）；拿掉 fsync 參數（tick 自己都不 fsync）、`safe.directory`（沒有多帳號）、git 版本檢查、當機後清 git 鎖檔、「HEAD 被換分支算故障」、巢狀排除（沒有上下層判定）。
9. **`aos-clean` 第二段做不做？** 它照 B-404 只清「kernel、agent 任務產生的、它認得的資料」，POC 現在沒有這些任務，等於沒東西可清；B-404 本身也還寫著舊的鎖 fd 與自己 commit 的規矩（[plan 入口跨段待問 2](README.md)）。**建議**：第二段不做，範本先拿掉 `clean`；等 kernel／agent 任務有了再照那時的 B-404 做。如果想先有個殼：只做「讀間隔、到期就把現在的 `seq` 記進 `.aos/clean.json`、回 0」，記在 `.aos/` 裡才會被 `aos-git` 提交（舊規定的 `state/ops/clean.json` 不在新的 git 範圍）。
10. **恢復前驗證第二段做不做？** 舊規定是一支工具：持鎖、照完整 schema 驗 inst 與任務表、驗 kernel／agent 設定，過了才 resume。現在 Python 標準庫沒有 schema 驗證器、也沒有 kernel／agent 設定，而且 POC 默認表是對的。**建議**：先不做。之後要的話，最小版是 `aos-check <資料夾>`：把 tick 讀表＋每一項合併展開走一遍、不真的跑，過了回 0；用法 `aos-check X && aos-ctl resume X`。（名字要避開已裁定的 `aos-tick-check-task`，免得混；到時再定。）
11. **第二段的範本要長怎樣？** 完整範本頭尾有 `mq-get`、`mq-post`（第四段才有，現在放上去跑到會記 127「找不到程式」）、`clean`（見 9）；`summary` 已隨 `aos-publish` 暫緩拿掉。**建議**：第二段版只放做得出來的——沒 git：只剩使用者任務（等於沒有系統級任務，這版範本只是「使用者任務」本身）；有 git：`git-open` → 使用者任務 → `mark-user` → `git-close`（見步驟 5）。第四段再把 `mq-get`、`mark-get`、`mq-post` 插回去。
12. **spec 的範本範例檔要不要改成第二段版？** 2026-10-01 已跟著裁定改了一點：拿掉 `summary`；`report` 的 `aos-needs` 包裝改成它前面多一項 `check-talk`（`aos-tick-check-task talk`）。**建議**：其餘不改。spec 那兩份是完整版（目標），第二段版只寫在 src/py README 與測試裡，第四段做完時自然跟 spec 對齊。
13. **`aos-config-add`**：已決定搬暫緩區，第二段不做——這條只是確認，不用另外裁定。

## 裁定紀錄

### 2026-10-01（[第五批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第五批aos-publish-搬暫緩區aos-needs-改寫成-aos-tick-check-task)）

只有下面這幾條算裁定；待問 1～12 照舊。

1. **`aos-publish` 搬暫緩區**（原步驟 2 拿掉，後面步驟往前補號）。使用者原話：「aos-publish我覺得要改名，我預期它的作用，就是把這一格的一些狀況總結成json檔案寫好」；討論後「那看來aos-summarize其實是暫時不需要了，拿掉。」所以「總結這一格成 JSON」的程式（暫名 `aos-summarize`）也不做。之後若要，方向是「把這一格的狀況總結成 JSON」，名字不用 publish（publish 會跟傳訊混）。spec：[暫緩區 B-624 部分](../spec/settled/deferred/tick.md#暫緩b-624-發布摘要aos-publish)、[P-206 那列](../spec/settled/deferred/protocol/tick.md#暫緩p-206-aos-publish-那列發摘要)。
2. **`aos-needs` 改寫成 `aos-tick-check-task`**（步驟 1 改寫）。使用者原話：「aos-needs原來是一個程式...，其實可以簡單一些，也就是它會檢查指定的東西是否跑好，沒跑好，就去寫tick stop檔案」「那就aos-tick-check-task」。用法 `aos-tick-check-task [<任務 id…>]`，自己是一項、不包別的指令；指定的都 `exit:0` 就不做事，否則建停格檔；不寫 id＝檢查前面全部；都回 0，自己的錯回 1；停格擋掉整格剩下的全部項，接受。spec：[B-621](../spec/settled/tick/check-task.md)、[P-204](../spec/settled/protocol/tick.md)。
3. **停格檔的未來方向（只記錄，不做）**。使用者原話：「我覺得tick-stop這個檔案會變成特定json格式，存放一些資訊，然後可以用aos-tick-check-task-continue來去檢查其中的一些資訊，滿足後修改stop中的資訊。所以aos-tick仍會執行所有任務，但會變成執行前檢查stop，看看是否滿足特定條件，滿足的話就可以執行該任務。」記在 [B-620「停格檔與擋板檔」](../spec/settled/tick.md)；現在停格檔規定不變。

### 2026-10-01（[第八批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第八批紀錄只記非-0)：紀錄只記非 0）

4. **紀錄只記結束碼不是 0 的項**（B-633、P-213；`aos-tick` 已改）。使用者原話：「記錄這一塊，tasks如果結果是0，那就不用紀錄了。hooks也是。」`tasks`、`hooks.after_all` 每筆 `{"id","index","exit"}`（訊號殺的是 `signal`），另加 `ran`＝本格到目前跑完幾項。跟著改：
   - **`aos-tick-check-task` 的判斷**（步驟 1）：寫了 id＝有出現在失敗清單才停格，沒出現當成功（不分辨「還沒跑」，照 POC 默認一切正常）；不寫 id＝失敗清單非空就停。
   - **`aos-git mark` 的「哪一組有失敗」**（步驟 4）：改照紀錄每筆的 `index` 落在哪一組，不再靠「紀錄第 k 筆就是表上第 k 項」。
