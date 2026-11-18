eca-claude 小試驗教學的目錄：使用者 11-18 陸續提的疑問，一題一份，每題都在公司 WSL 實跑過再寫成照打教學；新題往後加編號。

← [2026-11-18](../README.md)｜線 `eca-lab-1118`（隊長自己做 01～05，06～11 派給隊員）；HEAD `71df48e88` 的乾淨 clone，模型用 haiku

使用者原話（11-18）：「對了，幫我再去多做幾個小試驗，就用eca claude，並依此做教學，這樣我之後可以一步一步照著做」「claude額度不用省，反正haiku基本不花錢。然後我接著會說更多，這些都是我的一些有疑問的地方，都麻煩你試驗過，弄成教學」

## 目錄

| # | 題目（使用者原話） | 一句結論 |
|---|---|---|
| [01](01-停daemon複製stack重開.md) | 停掉 daemon（Ctrl+C、daemon-ctl 指令）、複製 stack 過去，重開 | 兩種停法一樣，都是全部 sleeping。整棵樹一起搬就接得上，路徑會自己換好，只是 claude 開新對話、帶著紀錄過去。只搬 `.stack` 會報 `EntryMissing`，把 `agents/` 也抄過去就救得回來 |
| [02](02-預設stack與站在agent夾裡.md) | stack 沒指定就是 `./.stack`？cd 到 agent 的夾直接 say | 找 daemon 的順序是 `-d` ＞ `AOS_DAEMON` ＞ `./.stack`，不看 `AOS_STACK`。站在 agent 的夾裡要打 `-d ../..`，站在樹根不用帶 |
| [03](03-自訂定義掛上去.md) | 自己複製一份 template 設定、改過、掛上去 | 沒有一定要改的檔，常改 `llm.json`、`system.txt`、`cli.json`。改 `system.txt` 下一句就生效。`set-def` 換夾約 1 秒。`cli.json` 寫錯掛的當下不擋，起來才倒 |
| [04](04-aos-post丟信.md) | 用 aos-post 往信箱丟信 | `echo JSON \| aos-post send <信箱>`。往 `procs/<名>/queue` 丟 `{"role":"user","content":…}`，agent 就會答。`say` 就是包了它，再加上檢查與提醒 |
| [05](05-aos-lock鎖信箱.md) | 用 aos-lock 鎖信箱、試 aos-post、解鎖 | 鎖信箱夾本身擋不住。aos-post 只認 `<信箱>/order.lock`，而且只在 `--ordered` 時。鎖住時 say 無聲一直等，解鎖後自己寄進去。命令列拿的鎖不會自己放 |
| [06](06-不用aos-tree-start起daemon.md) | 不用 aos-tree-start 啟動停著、有掛 proc 的 daemon | `aos-tree-start` 只是檢查環境再叫 `aos-exec`。`cd ~/aos-home && source env.sh && aos-exec root` 結果一樣。running／sleeping 的自己醒，stopped 的要 `start`。aos-tree-start 已於 11-18 移除，直接用 aos-exec |
| [07](07-aos-mailbox寄信收信.md) | 用 aos-mailbox 寄信給 agent、收信 | 寄進的是 agent 的 `mailbox/`，不是 `queue/`。agent 要等 `mail_notify` 每分鐘巡一次才看到。回信用 `in_reply_to` 對上，收信要自己輪詢 |
| [08](08-不用aos-kit.md) | 不用 aos-kit 做出 aos-kit 的功能 | aos-kit 只換定義裡的 `system.txt`、`tools.json`，並另存 `.before-kit`。手動 cp 的結果逐檔相同。出廠的 kit 現在裝不起來（`MakeMissing`），也不支援 eca-claude |
| [09](09-aos-sandbox限制資源.md) | 用 aos-sandbox 限制 CPU%、核心數、資料夾、網路、記憶體 | 資料夾、網路由沙箱本身擋。記憶體、CPU 時間這台要走 daemon 的 `--limits`。CPU%、核心數沒有欄位，要在外面包 `systemd-run --user`＋`taskset` |
| [10](10-aos-asuser.md) | 試 aos-asuser（不行就寫缺什麼、模擬假設） | 參數檢查都實跑過了。真換身分缺 `newuidmap`，要使用者自己 `sudo apt install uidmap`。裝好之後的步驟標成「預期，未實測」 |
| [11](11-aos-share.md) | aos-share 也試試看 | 檔案系統支援 ACL，`check` 能用。真的分享、收回缺 `setfacl`，要使用者自己 `sudo apt install acl uidmap`。裝好之後的步驟標成「預期，未實測」 |
| [12](12-沙箱asuser-share要裝什麼與WSL限制.md) | 沙箱、asuser、share 各要額外裝什麼、WSL 上有什麼限制（總覽） | 沒有新實測，整理自 09～11 與實機檢查。bwrap 有；要補 `s6`（沙箱上限、`aos-run`）、`uidmap`（asuser）、`acl`（share），sudo 要自己跑。不裝的替代路是 `--limits`、`systemd-run`＋`taskset` |

## 共同準備

每一題都從這棵樹開始。位置自己挑，下面用 `~/aos-home`。

```sh
cp -r $AOS_HOME/templates/start-eca ~/aos-home && echo '{"model": "haiku"}' > ~/aos-home/agents/ann/llm.json
```

範本的模型是 sonnet，這行把它改成 haiku。視窗 A：

```sh
cd ~/aos-home && source env.sh && aos-tree-start root
```

視窗 C：

```sh
cd ~/aos-home && source env.sh && aos-agent -d .stack ctl add --auto-restart -w . agents/ann
```

先決條件：已經照[重建步驟單](../../17/重建步驟單.md)裝好，`AOS_HOME` 有設、`claude` 指令在 PATH 上、而且登入過。關樹用 `aos-daemon-ctl -d .stack shutdown`。

## 我是怎麼跑的（你不用這樣做）

我是從 Windows 經 `wsl -e bash -c '…'` 進 WSL 的，每次呼叫結束，丟到背景的行程就會死掉。所以視窗 A 放在我自己的 tmux（`tmux -L <名>`）裡，用 send-keys 打指令；視窗 C 的指令一次一次直接跑。樹、定義、stack 都在 `~/.aos/scratch/eca-lab-1118/` 底下，教學裡一律寫成 `~/aos-home` 這種你會用的樣子。輸出裡的 pid、時間、信件編號，你跑的時候會不一樣。

## 加新的一題

新題接著用下一個編號，檔名寫成 `NN-短題目.md`。第一行一句話說這份是什麼，第二行寫 `← [目錄](README.md)`。內容先放「結論」，再一步一步寫：每步一行指令，下面一句會看到什麼，最後一節是「發現的問題」。最後在上面的表補一列。
