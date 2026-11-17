# wf/public/Windows與WSL — 公司 Windows 那台的坑：假 python3、不分大小寫、中文檔名、/mnt/c 全 +x、MSYS 路徑轉換

← [wf/public](README.md)｜同一棵工作樹多人 commit 的坑見 [共用工作樹與git](共用工作樹與git.md)；程序群組會弄掛 WSL 見 [行程與環境](行程與環境.md)

公司那台是 Windows 上的工作樹（git bash）加 WSL。

## git bash 的 `python3` 是假捷徑：跑 python 一律走 WSL

`command -v python3` 找得到（Microsoft Store 的假捷徑），一執行就失敗，靠 python 的檢查因此**默默沒跑**。一律走 WSL：`wsl -e bash -lc 'cd /mnt/c/code/mine/simple_tools/aos && …'`。

## Windows 檔案系統不分大小寫：新資料夾別取只差大小寫的名字

`wf/WORKFLOWS/` 跟 `wf/workflows/` 會疊成同一個資料夾，git 卻當兩條路徑，檔案就被記到錯的大小寫底下。新資料夾別取只差大小寫的名字（[STRUCTURE](../STRUCTURE.md) 規定改用 `<名>-parts/`）。要自己 add 的機器寫 `git -c core.ignorecase=false add <正確路徑>`，commit 前用 `git -c core.ignorecase=false status --short` 看路徑大小寫對不對。

## 中文檔名：清單一律用 `git -c core.quotepath=false` 產，照抄跳脫字串會漏檔

預設 `core.quotepath=true`，`git status` 把中文路徑印成 `"proto8/NORMS/10-\345\237\272…"`，拿這份清單去 add（或 claim、`--files`）對不上、漏檔。看清單用 `git -c core.quotepath=false status --short`。沒有 commit-request 的機器 add 用 `git -c core.quotepath=false -c core.ignorecase=false add -- <檔>`，或 `git add -u -- proto8 wf`（只加已追蹤的修改；未追蹤的 `proto8/impls/` 本來就不會被加）；add 完再看一次 `git status --short`，確認沒有剩下前面是空格的 ` M`（＝改了沒 add）。走 commit-request 的見 [patch-and-commit「commit-request 的坑」](patch-and-commit.md#commit-request-的坑)。

## WSL 看 `/mnt/c` 底下全是 `+x`：proto8 的測試與 demo 先抄到 WSL 自己的檔案系統

沒開 metadata 時，aos-exec 會把 repo 裡的 JSON 入口（`loop.json#/body`）當可執行檔，報 `bad entry: an executable cannot take #/`；在 `/mnt/c` 上跑 proto8 tests 約有 12 個假失敗。跑之前先把 `proto8/` 複製到 WSL 自己的檔案系統（如 `~/tmp`）、全部 `chmod 644`，再照 `git ls-files -s` 的 `100755` 補 `+x`。

## Git Bash 叫 `wsl` 帶 `/mnt/...` 路徑：前面加 `MSYS_NO_PATHCONV=1`

`wsl git -C /mnt/c/...` 會被 MSYS 路徑轉換改寫成 `C:/Program Files/Git/mnt/...` 而失敗：加 `MSYS_NO_PATHCONV=1`，或改用 PowerShell 跑。WSL 的 git 用 https 推會卡在等帳密，改加 `-c 'url.git@github.com:.insteadOf=https://github.com/'` 走 SSH（push 照舊要先確認）。
