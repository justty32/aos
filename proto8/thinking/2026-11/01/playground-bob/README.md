# 2026-11-01 試驗場現場：使用者邊說邊做（agents/bob）

← [thinking README](../../../README.md)｜場地 `~/code/playground/`（`ws/` 清空、新建 `agents/`，使用者 `source env.sh && cd ws`）

本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../../../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-01 下午，逐字）

> 我把ws清空了，並且新建了agents資料夾。接下來就是用這兩個資料夾做事。並且我也source env.sh && cd ws了。好，接下來我會一步一步說我想幹嘛，你就告訴我要下啥指令，並且幫我準備好各種東西。途中我也會說一些想法，也請你幫我記錄下來。

> 好，我要輸入aos-exec ../agents/bob -- "幫我在env:AOS_WS寫一首詩，詠桃花。"。我預期bob他有read/write等基本工具，但是沒有shell。然後bob的system prompt中有說AOS_WS等環境變數分別代表啥，並且bob也知道自己所處的cwd(當然，bob是透過tool知道的)。跑起來之後，就是阻塞，直到bob執行完。bob是一個claude code -p

> 老實說，我覺得我們一直在濫用環境變數。環境變數在我們這個aos體系下，有點類似janet中的dyn，最好要謹慎，只在必要的時候使用。

（11-01 晚，接著玩；話沒說完、「然後...」之後待補）

> 我要繼續playground，我會開兩個視窗，一個跑aos-exec ../agents/amy -- "在env:WS寫一首詩，詠白銀"，他會直接進入claude code cli界面開始跑，就跟我們平時使用一樣，我也可以接着用平時的方法使用，他會一直持續着直到我打/exit。然後我另一個視窗會輸入aos-say "現在狀況" && aos-listen，然後...

> 視窗二這塊，我就是要實現這個效果，你幫我想

頂層攤了組法（cli_session 畫面＋aos-eca-turn＋aos-loop＋aos-say／listen 四個現成零件）後，使用者原文：

> 做出來讓我試

（原型見下「做了什麼」amy 那條。）

（11-01 晚收工前）

> 好煩，整個都怪怪

> 算了，今天先這樣，明天再說

頂層問哪裡怪，使用者未答；明天再說。

## 做了什麼（頂層代做，可翻案）

- `agents/bob/`＝沒有程式碼：`_entry.json`（argv 陣列：`claude -p --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits --strict-mcp-config --max-budget-usd 0.3 --add-dir {$env AOS_WS} --append-system-prompt-file system.txt`）與 `system.txt`。
- 題目裡 `env:XXX` 的寫法在 system prompt 裡解釋成「環境變數 XXX 的值」。
- aos-exec 會 cd 進 `agents/bob/`（AOS_CD），所以要 `--add-dir $AOS_WS` 讓 claude 的檔案工具能寫到工作區；system prompt 叫它別往自己的資料夾寫。
- `aos-exec ../agents/bob -- "題"`：`--` 與題目都原樣給入口，claude 認 `--` 當分隔（實測）。
- `agents/amy/`＝bob 的互動版，eca 那種定義，**只組合現成程式、沒加機制**：`_entry` 是一支二十幾行的 Python 小殼，四個動作——① `--` 後那句用 `aos-post init`＋`aos-post send --ordered <stack>/queue`（跟 aos-say 同一條路）寄成第一封，沒給題不寄；② 用 `cli_session.open_cell` 開 claude 畫面（tmux、detached；有 `session.txt` 就 `--resume`）；③ 背景起 `aos-loop loop.json`（`aos-eca-turn --on-empty idle --on-busy answer {$env AOS_CD}`，同 demo/eca-claude）；④ `tmux -S <stack>/claude/tty.sock attach`，回來（Ctrl-] 或 /exit）寫 `<stack>/ctl.json` `{"stopped": true}`、等 loop 收工。`cli.json`＝kind claude、flags 同 bob 拿掉 `-p` 與 `--add-dir`、print_flags `--max-budget-usd 0.3`。玩法在 `~/code/playground/agents/amy/README.md`。
  - 代定 1：**on-busy 用 `answer`（不是 yield）**：yield 時人接在畫面上，`aos-eca-turn` 每輪都退讓，兩視窗情境不成立；answer＝人看著時也貼進畫面答。翻案改 loop.json 一個字。
  - 代定 2：cli_session 開畫面的 cwd 是工作區，所以不用 `--add-dir`、`--append-system-prompt-file` 寫 system.txt 的絕對路徑，system.txt 寫「工作區就是你的 cwd」。
  - 代定 3：Ctrl-] 只跳出、畫面留著、loop 收工（say 會排著沒人答）；再跑一次 `aos-exec ../agents/amy`（不給題）接回同一個畫面、排著的信接著答。/exit 時畫面跟 claude 一起關。
  - 邊角：使用者自己在畫面打的話不進 history（不經 queue）；say 會打進他正在看的畫面（打到一半沒送出時會接在他的字後面）；`aos-say 話 && aos-listen` 不給信號會一直跟著看、不結束，要 `N=$(aos-say …); aos-listen "$N"`；畫面那條路不走 `-p`，`--max-budget-usd` 不生效。
  - 換到沒信任過的資料夾，第一次開畫面要按 Yes，題目那句可能先被貼進提問裡。

## 環境變數要謹慎（11-01 使用者，待展開）

使用者的原則：環境變數像 Janet 的 `dyn`（動態綁定：誰在上面設了，底下所有人都看得到、又看不出是誰設的），**只在必要時用**。

對 bob：system prompt 不經環境變數傳話，用 `system.txt` 一個檔＋`--append-system-prompt-file`；bob 這格只用 aos-exec 本來就給的 `AOS_WS`（`--add-dir {"$env": "AOS_WS"}`）這一處環境變數。

盤點：59 個 `AOS_*` 照判準分成必要 5、邊界 11、不必要→改 argv 20、不必要→改檔 22、沒人讀 1。

| 分檔 | 涵蓋 |
|---|---|
| [01-環境變數盤點](01-環境變數盤點.md) | 怎麼核的、欄位、判準、分類小計、留意的幾點（每個變數一列在 [env-vars.json](env-vars.json)） |
| [02-環境變數要使用者裁的問題](02-環境變數要使用者裁的問題.md) | 五題：hub 型算不算必要、腦三個變數、格自己的旋鈕要不要一次性全改、傳話筒要不要加機制、`AOS_ENTRY` 要不要拿掉 |
| [03-旋鈕改-argv-與檔-實作](03-旋鈕改-argv-與檔-實作.md) | 42 個格旋鈕刪 26、改 argv 11、改檔 3、不動 2；刪掉 aos-round（loop.json 直接叫 aos-fsm、五格改拿 `AOS_CD`）；代定清單 |

使用者裁定 → [02 § 使用者裁定](02-環境變數要使用者裁的問題.md#使用者裁定11-01-晚)（1 不用、2 到時候再說、3 改、4 結案（隨主人退場）、5 不拿掉）。
