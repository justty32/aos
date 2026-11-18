線 eca-lab-1118 在 11-18 16:5x 收手時的交接：小試驗教學 13～19 各題的狀態、檔名，以及明天從哪接著做。

← [2026-11-18](../README.md)｜教學夾：[eca-claude-小試驗教學](../eca-claude-小試驗教學/README.md)

## 13～19 各題狀態

| # | 題目 | 狀態 | 檔名 | 明天從哪續 |
|---|---|---|---|---|
| 13 | 用 aos-loop 控制 eca-claude 的停止與繼續 | 沒交出檔：隊員實跑到一半，被收手打斷 | （沒有）`13-aos-loop控制停止與繼續.md` | 照原任務書重派。已知事實：aos-loop 沒有子指令，只能靠 ctl 窗（`<agent stack>/ctl.json`，內容 `{"cmd":"pause"\|"resume"\|"stop","seq":N}`）和訊號控制，另外有 `aos-agent ctl pause/resume/stop/start/sleep/wake`。隊員的暫存在 WSL 的 `~/.aos/scratch/eca-lab-1118/t13/`（它的筆記沒看過） |
| 14 | agent 停著時對它 say | 沒交出檔：跟 13 同一位隊員，一起被打斷 | （沒有）`14-停著時say.md` | 跟 13 一起重派。已知事實：沒有 `aos-say` 這支，正確是 `aos-agent say`。對象沒在跑或暫停時 say 會照寄，stderr 印 `queued in …; nothing is running …` 或 `… is paused …`（讀 `say.py` 看到的）。試驗 18 實測過：停著時 say、`listen` 報 `AnswerMissing …`，`ctl start` 後信照樣會被回答 |
| 15 | 用 aos-tools 給 eca-claude 加新工具 | 完成 | `15-aos-tools加新工具.md`（約 9 KB） | 不用續。沒驗的：tooldef 寫在 `_metainfo.json` 裡、`tools_sub.json`、`--envs` |
| 16 | 手動讓 eca-claude 當 kernel | 完成 | `16-手動讓eca-claude當kernel.md`（約 12 KB） | 不用續。沒驗的：當 kernel 的 agent 自己下 ctl 時怎麼繞過自己、拒絕 stop 時寄件人看到什麼、`max_running` |
| 17 | 手動看 agent 狀態（aos json view、信箱、queue…） | 沒交出檔：隊員被打斷 | （沒有）`17-手動看agent狀態.md` | 照原任務書重派。18 已經連到這個檔名，連結現在是斷的。暫存在 `t17/` |
| 18 | agent 出錯怎麼手動除錯（大概講） | 完成 | `18-agent出錯怎麼手動除錯.md`（約 5.8 KB） | 不用續。沒實測的：權限提問卡住、沒登入、額度用完 |
| 19 | 手動幫 eca-claude compact | 沒交出檔：隊員被打斷 | （沒有）`19-手動compact.md` | 照原任務書重派。暫存在 `t19/` |

01～12 都已完成，01～11 是這條線做的，12 是 lab12-1118 寫的、已 commit。

## 還沒做的收尾

- **README 的「共同準備」還寫著 `aos-tree-start`**（今天被使用者裁定刪除），要改成 `cd ~/aos-home && source env.sh && aos-exec root`。01、02、03 內文也有 `aos-tree-start`，一起換。
- **沒 commit**：這條線所有教學檔、日索引那一列（`18/README.md`）、這份交接檔都還沒交。
- **WSL 上的殘留**：被打斷的三位隊員（13/14、17、19）的 tmux（`tmux -L ecalab13`／`ecalab17`／`ecalab19`）和它們起的 daemon，收手時還開著，我接著收（見下一節）。暫存夾 `~/.aos/scratch/eca-lab-1118/` 全部留著，沒刪。

## 收手時收掉的行程

已經收完：
- 對 t13、t17、t19 各自的 `.stack` 跑了 `aos-daemon-ctl -d <那個 stack> shutdown`，三台都回「3 procs asleep」。
- 對三個 tmux socket 各跑了 `tmux -L <socket> kill-server`。
- t13 那隻開著的畫面，用 `aos-agent -t ann close` 關掉了。

`/run/user/1000/aos-tty-1000/` 底下還剩一個 socket（`0390c8a5…`），對不上這條線的任何樹，沒去動它。

另外，目錄 README 已經補了 13～19 的列，13、14、17、19 標成未完成。

## 18 的隊員提到的一件事

它想看自己那隻的畫面，對 `/run/user/1000/aos-tty-1000/` 底下所有 socket 都跑了 `capture-pane`，因此讀到一個不是它的畫面（是另一位隊員的 claude 畫面）。只讀，沒有送任何按鍵。
