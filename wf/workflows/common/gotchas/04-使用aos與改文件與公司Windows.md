← [入口](../gotchas.md)｜涵蓋：使用 aos、改文件、公司 Windows 這台

## 使用 aos

- ~~**`aos exec` 的退出碼不反映子行程成敗**~~ — **2026-09-01 作廢：沒有 `aos exec` 這支
  子命令了**（`core/exec` 只當函式庫用，`aos --help` 印不出 `exec`）。現在的對應規則是
  **`aos run` 會反映**：任一條 inst 非零 exit／被 signal 中止就回 1（exit 75 當
  `waiting-llm` 回壓、不算失敗），逐條細節照樣讀 `.aos/batch/<turn>/out/<id>.json`。

## 改文件

- **批次改文件用非貪婪正則可能吃掉整段**：`.*?` 配上 `re.DOTALL`，如果終止字串在檔案
  更後面又出現一次，會從起點一路吃到那裡。這個坑真的發生過——`code-map.md` 被砍掉
  130 行還 commit 進去了，因為當時只 `grep` 關鍵字確認「殘留清乾淨」，沒看檔案剩幾行。
  **批次改完一定要看行數與章節數**，`grep` 只能證明某段不在，不能證明別的還在。

- **`\b` 邊界在 `-Iinst/include` 這種字串上不成立**：`inst` 前面是 `I`（word 字元），
  所以 `\binst/` 匹配不到。批次替換路徑之後，`grep` 一次確認沒有漏網的。

## 公司 Windows 這台

- **git bash 的 `python3` 是 Microsoft Store 假捷徑**：`command -v python3` 找得到、一執行就失敗，
  `wf-lint.sh` 裡靠 python 的檢查（BIGLIST、錨點）因此**默默沒跑**、照樣印 `biglist=0`。
  跑 python、wf-lint、unittest 一律走 WSL：`wsl -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && …'`
  （2026-10-20 撞到，見 [session log 10-20](../../../session_logs/2026-10/2026-10-20.md)）。
- **Windows 檔案系統不分大小寫**：`wf/WORKFLOWS/` 跟 `wf/workflows/` 會疊成同一個資料夾，
  git 卻當兩條路徑，檔案就被記到錯的大小寫底下（10-20 有 5 個檔這樣，9a62818d 修回）。
  `git add` 一律寫 `git -c core.ignorecase=false add <正確路徑>`，commit 前用
  `git -c core.ignorecase=false status --short` 看路徑大小寫對不對；新資料夾別取只差大小寫的名字
  （[STRUCTURE](../../../STRUCTURE.md) 規定改用 `<名>-parts/`）。
- **`git status` 把中文檔名印成加引號的跳脫字串，照抄去 `git add` 會漏檔**：預設 `core.quotepath=true`，
  中文路徑印成 `"proto8/NORMS/10-\345\237\272…"`，拿這份清單去 add 對不上（10-21 一輪漏了 12 份沒 commit）。
  看清單用 `git -c core.quotepath=false status --short`；add 用
  `git -c core.quotepath=false -c core.ignorecase=false add -- <檔>`，或 `git add -u -- proto8 wf`
  （只加已追蹤的修改；未追蹤的 `proto8/impls/` 本來就不會被加）。**add 完再看一次 `git status --short`，
  確認沒有剩下前面是空格的 ` M`**（＝改了沒 add）。
- **WSL 看 `/mnt/c` 底下的檔全是 `+x`**（沒開 metadata）：aos-exec 會把 repo 裡的 JSON 入口（`loop.json#/body`）當可執行檔，報 `入口壞：可執行檔不能帶 #/`（10-21 撞到）。跑 proto8 測試與 demo 前，先把 `proto8/` 複製到 WSL 自己的檔案系統、全部 `chmod 644`，再照 `git ls-files -s` 的 `100755` 補 `+x`。
- **在 `/mnt/c` 上跑 proto8 tests 有約 12 個假失敗**（10-22）：`/mnt/c` 底下所有檔都被當可執行（同上一條）。先把 repo 複製到 WSL 自己的檔案系統（如 `~/tmp`）再跑。
- **Git Bash 跑 `wsl git -C /mnt/c/...` 會被 MSYS 路徑轉換改寫成 `C:/Program Files/Git/mnt/...` 而失敗**（10-22）：改用 PowerShell 跑，或加 `MSYS_NO_PATHCONV=1`。WSL 的 git 用 https 推會卡在等帳密，改加 `-c 'url.git@github.com:.insteadOf=https://github.com/'` 走 SSH。
- **多 agent 同時在同一工作樹時，不要用 `git pull --rebase --autostash`**（10-22 發生過）：它可能停在半截 rebase，把別人的未提交改動收進 autostash（有 agent 的改動一度消失）。只 `add` 自己的檔。
