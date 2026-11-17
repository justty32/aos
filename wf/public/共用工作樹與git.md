# wf/public/共用工作樹與git — 好幾條線同一棵工作樹：同檔只給一條線、別 autostash、整檔改寫不拆刪加、合併後才刪分支、worktree 起點

← [wf/public](README.md)｜commit-request 的坑與把暫存樹改動搬回 main 見 [patch-and-commit](patch-and-commit.md)；commit 的規矩在 [06 第 7 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)；中文檔名與大小寫見 [Windows與WSL](Windows與WSL.md)

## 同一個檔同一時間只給一條線：點名 commit 擋不住同檔裡別線的字

- **放行前先讓各隊長交領地清單**（獨佔的檔、會跟別線撞的檔），調度者對過、把撞的檔指給唯一一條線再開工。
- **同一個 clone 裡，別人的 `git commit` 會把你已 stage 的檔一起帶走**（隊長 `git add` 完、還沒 commit，同 clone 另一位一跑 `git commit` 就整包收進它的 commit、還推上去了）。有 commit-request 的機器不自己 `git add`／`git commit`（[AGENTS.md](../../AGENTS.md) 鐵律 3）；沒有的機器 stage 跟 commit 寫在同一個指令裡、中間不停，自己 commit 用 `git commit -F 訊息 -- <自己的路徑>`。
- **`git commit -- <點名檔>` 擋不住同一個檔裡別線的字**：那個檔工作樹裡有別線還沒 commit 的改動，會整個一起進你的 commit。commit 前 `git diff -- <那些檔>` 逐段看是不是自己的。照樣絕不 `git add -A`。
- **生成器掃的是整棵工作樹**：`index_gen`（含 `wf/knowledge/code-map/` 逐檔表）會把別線還沒 commit、但已 staged 的檔寫進生成物（別線 staged 的改名也被生成物的 commit 帶走過）；commit 生成物前看 diff，不是自己的列先不收。
- **全套測試跑到一半別線在改檔**，結果反映的是當時的工作樹，不能當基準；當基準的那次在乾淨複本上跑（[testing](../workflows/testing.md#不碰跑著的樹)、[pitfalls「標準跑法」](pitfalls.md)）。
- **工人偶爾漏 stage 改過的 md**：驗收要含 `git status --short | grep -v '^[MADR] '` → 0，並以明確路徑補 `git add`；走 commit-request 的把漏的檔補進 `submit --files`，不 `git add`。

## 多人同一棵工作樹時不要 `git pull --rebase --autostash`

它可能停在半截 rebase，把別人的未提交改動收進 autostash（有 agent 的改動一度消失）。只 `add` 自己的檔。

## 整檔改寫用單一 Update 操作，不要拆成 Delete＋Add

有些 agent 工具的 patch 機制會**拒絕**「同一路徑同時 Delete＋Add」的原子 patch，線收到拒絕後很自然會拆成兩份：先刪、再加。中間**該檔在工作樹上真的不存在**，可能有幾十秒的空窗，會被另一條線掃到並回報成疑似違規刪除；那段空窗內線若崩潰，工作區的主入口就缺檔，留下壞掉的工作樹。這不是線的惡意，下一條線還會這樣做；禁止 shell 的 `rm` 擋不到它。

1. 整檔改寫一律用單一 Update 操作（一次完成、原子）。
2. 每個批次邊界跑 `git status --short | grep -E '^(D |.D)'`，要零命中。

## 合併成功之後才刪分支；主 repo 有未提交改動先比交集

本 repo 只有 `main`、不開分支（[user.md](../workflows/common/user.md)），開分支或 worktree 的專案才用得上：

- `git merge --ff-only … | tail -1 && git worktree remove … && git branch -D …` 這種串法：merge 被未提交的改動擋下時，`| tail` 吃掉了退出碼，鏈會繼續跑把分支刪掉（只能靠 `branch -D` 印出的 hash 救回）。合併指令**單獨跑**、看完整輸出與退出碼，成功後才刪 worktree／分支。
- 主 repo 常有使用者未提交的改動：合併前先比 `git diff --name-only main <分支>` 和 `git status --short` 的交集，重疊檔只 `git stash push -- <那幾個檔>`，合併後 `stash pop`，再確認他的改動還在。

## isolation worktree 的起點可能很舊：第一步先對齊 main

Agent 工具的 isolation worktree 不保證從 main HEAD 開，可能建在落後幾十個 commit 的舊點，照交接書測到已刪掉的舊程式、整輪作廢。worktree 隊的任務書**第一步**：`git merge-base --is-ancestor HEAD main && git reset --hard main`，確認 `git log -1` 跟主 repo 的 main 一致才開工；收線時隊長說「停在舊 commit」就先查產出是不是對著現況做的。
