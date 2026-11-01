# 2026-11-01 試驗場現場：使用者邊說邊做（agents/bob）

← [thinking README](README.md)｜場地 `~/code/playground/`（`ws/` 清空、新建 `agents/`，使用者 `source env.sh && cd ws`）

狀態：進行中。本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-01 下午，逐字）

> 我把ws清空了，並且新建了agents資料夾。接下來就是用這兩個資料夾做事。並且我也source env.sh && cd ws了。好，接下來我會一步一步說我想幹嘛，你就告訴我要下啥指令，並且幫我準備好各種東西。途中我也會說一些想法，也請你幫我記錄下來。

> 好，我要輸入aos-exec ../agents/bob -- "幫我在env:AOS_WS寫一首詩，詠桃花。"。我預期bob他有read/write等基本工具，但是沒有shell。然後bob的system prompt中有說AOS_WS等環境變數分別代表啥，並且bob也知道自己所處的cwd(當然，bob是透過tool知道的)。跑起來之後，就是阻塞，直到bob執行完。bob是一個claude code -p

> 老實說，我覺得我們一直在濫用環境變數。環境變數在我們這個aos體系下，有點類似janet中的dyn，最好要謹慎，只在必要的時候使用。

（11-01 晚，接著玩；話沒說完、「然後...」之後待補）

> 我要繼續playground，我會開兩個視窗，一個跑aos-exec ../agents/amy -- "在env:WS寫一首詩，詠白銀"，他會直接進入claude code cli界面開始跑，就跟我們平時使用一樣，我也可以接着用平時的方法使用，他會一直持續着直到我打/exit。然後我另一個視窗會輸入aos-say "現在狀況" && aos-listen，然後...

> 視窗二這塊，我就是要實現這個效果，你幫我想

頂層攤了組法（cli_session 畫面＋aos-eca-turn＋aos-loop＋aos-say／listen 四個現成零件，缺的只是沒人跑 loop，amy 的 `_entry` 換成二十行小殼）與邊角後，使用者原文：

> 做出來讓我試

（原型見下「做了什麼」amy 那條。）

（11-01 晚收工前）

> 好煩，整個都怪怪

> 算了，今天先這樣，明天再說

頂層問哪裡怪，使用者未答；明天再說。

## 做了什麼（頂層代做，可翻案）

- `agents/bob/`＝兩個檔、沒有程式碼：`_entry.json`（argv 陣列：`claude -p --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits --strict-mcp-config --max-budget-usd 0.3 --add-dir {$env AOS_WS} --append-system-prompt {$env BOB_SYSTEM}`）與 `.env`（一行 `BOB_SYSTEM="…AOS_WS=${AOS_WS}…AOS_CD=${AOS_CD}…"`，值由 aos-exec 讀 `.env` 時用 `${…}` 填進去——所以 bob 不用 shell 也知道各環境變數的值）。
- 題目裡 `env:XXX` 的寫法在 system prompt 裡解釋成「環境變數 XXX 的值」。
- aos-exec 會 cd 進 `agents/bob/`（AOS_CD），所以要 `--add-dir $AOS_WS` 讓 claude 的檔案工具能寫到工作區；system prompt 叫它別往自己的資料夾寫。
- `aos-exec ../agents/bob -- "題"`：`--` 與題目都原樣給入口，claude 認 `--` 當分隔（實測）。
- 實測：`aos-exec ../agents/bob -- "測試：在 env:AOS_WS 建一個 hello.txt，內容只寫 hi。"` 結束碼 0、檔案在 ws；之後清回空的。
- （11-01 晚）`agents/amy/`＝bob 的互動版：`_entry.json` 同 bob 但拿掉 `-p`（進一般 Claude Code 畫面、直到 /exit）、沒有 `--max-budget-usd`；`system.txt` 說明 `env:WS`／`env:AOS_WS` 都指工作區、每做完一件事報一句再等下一句。
- 頂層核過的現況：`aos-say` 只把信寄進 `<ws>/.stack/queue/`，`aos-listen` 不給信號＝跟著看 history（像 tail -f）；但 amy 是直接在使用者終端機裡開的互動 claude，沒有人會把 queue 的信送進她的畫面——現有能做到「畫面開著時 say 打進畫面」的是 aos-eca-hub／aos-eca-turn（畫面跑在 tmux 裡、cli_session 貼進畫面）。使用者的「然後...」還沒說完，頂層先攤這個落差、不代擬做法。
- （11-01 晚，隊長做原型讓使用者試）`agents/amy/` 改成 eca 那種定義，**只組合現成程式、沒加機制、repo 程式碼沒動**：`_entry` 換成一支二十幾行的 Python 小殼，四個動作——① `--` 後那句用 `aos-post init`＋`aos-post send --ordered <stack>/queue`（跟 aos-say 同一條路）寄成第一封，沒給題不寄；② 用 `cli_session.open_cell` 開 claude 畫面（tmux、detached；有 `session.txt` 就 `--resume`）；③ 背景起 `aos-loop loop.json`（`aos-eca-turn --on-empty idle --on-busy answer {$env AOS_CD}`，同 demo/eca-claude）；④ `tmux -S <stack>/claude/tty.sock attach`，回來（Ctrl-] 或 /exit）寫 `<stack>/ctl.json` `{"stopped": true}`、等 loop 收工。`cli.json`＝kind claude、flags 同 bob 拿掉 `-p` 與 `--add-dir`、print_flags `--max-budget-usd 0.3`。
  - 代定 1：**on-busy 改 `answer`（不是原先講的 yield）**。實測 yield 時人接在畫面上，`aos-eca-turn` 每輪都 SessionBad 退讓——連題目那封都不答、視窗二 say 也要等人跳出才答，使用者的兩視窗情境整個不成立；answer＝人看著時也貼進畫面答。翻案改 loop.json 一個字。
  - 代定 2：cli_session 開畫面的 cwd 是工作區，所以拿掉 `--add-dir`、`--append-system-prompt-file` 寫 system.txt 的絕對路徑，system.txt 兩行改成「工作區就是你的 cwd」（原本寫 cwd 是自己的資料夾，會叫它別往工作區寫）。
  - 代定 3：Ctrl-] 只跳出、畫面留著、loop 收工（say 會排著沒人答）；再跑一次 `aos-exec ../agents/amy`（不給題）接回同一個畫面、排著的信接著答。/exit 時畫面跟 claude 一起關，不用另外 close。
  - 邊角：使用者自己在畫面打的話不進 history（不經 queue，同 eca 方向題 2）；say 會打進他正在看的畫面（打到一半沒送出時會接在他的字後面）；`aos-say 話 && aos-listen` 不給信號會一直跟著看、不結束，要 `N=$(aos-say …); aos-listen "$N"`；畫面那條路不走 `-p`，`--max-budget-usd` 不生效；`--strict-mcp-config` 跟 cli_session 自己加的 `--settings` hooks 沒打架。
  - 第一次信任提問：`~/code` 已信任，底下的工作區沒問；換到沒信任過的資料夾，第一次開畫面要按 Yes，題目那句可能先被貼進提問裡。
  - 實測（haiku、另開 `ws-amy-test`、外層 tmux 模擬視窗一真的 attach）：開跑到題目答完 14.7 秒（檔寫進工作區）；畫面開著、人接著時視窗二 say→listen 2.5 秒拿到回答、畫面上看得到那句；人在畫面打的一輪沒進 history；Ctrl-] 後結束碼 0、loop stopped、畫面留著，此時 say 沒人答（`AnswerMissing`），再跑一次接回、2.7 秒答出；/exit 後結束碼 0、沒殘留程序。測完 `ws-amy-test` 刪掉。玩法在 `~/code/playground/agents/amy/README.md`。

## 環境變數要謹慎（11-01 使用者，待展開）

使用者的原則：環境變數像 Janet 的 `dyn`（動態綁定：誰在上面設了，底下所有人都看得到、又看不出是誰設的），**只在必要時用**。

對 bob 的直接影響（頂層照這條改了）：原本把 system prompt 塞進 `.env` 的 `BOB_SYSTEM`、再用 `{"$env": "BOB_SYSTEM"}` 餵給 claude，只是為了借 `${}` 填值——那是把環境變數當傳話筒，不必要。改成 `system.txt` 一個檔＋`--append-system-prompt-file system.txt`，工作區讓 claude 從 `--add-dir` 自己看到；bob 這格現在只剩 aos-exec 本來就給的 `AOS_WS`（`--add-dir {"$env": "AOS_WS"}`）這一處用到環境變數。

待使用者展開：哪些算「必要」（aos-exec 的六個 `AOS_*`？`AOS_BRAIN_URL`、`AOS_DAEMON`？10-31 補了前綴的 49 個名字裡哪些其實該改成 argv 或檔）——清單在 [naming-method § 10-31 已改](2026-10-23-naming-method.md)。

**盤點表已備（11-01 晚，隊長代做、待使用者裁）**：59 個 `AOS_*` 照判準分成必要 5、邊界 11、不必要→改 argv 20、不必要→改檔 22、沒人讀 1，程式沒改。

| 分檔 | 涵蓋 |
|---|---|
| [01-環境變數盤點](2026-11-01-playground-bob/01-環境變數盤點.md) | 怎麼核的、欄位、判準、分類小計、留意的幾點（每個變數一列在 [env-vars.json](2026-11-01-playground-bob/env-vars.json)） |
| [02-環境變數要使用者裁的問題](2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md) | 五題：hub 型算不算必要、腦三個變數、格自己的旋鈕要不要一次性全改、傳話筒要不要加機制、`AOS_ENTRY` 要不要拿掉 |
| [03-旋鈕改-argv-與檔-實作](2026-11-01-playground-bob/03-旋鈕改-argv-與檔-實作.md) | 11-01 晚實作：42 個格旋鈕刪 26、改 argv 11、改檔 3、不動 2；刪掉 aos-round（loop.json 直接叫 aos-fsm、五格改拿 `AOS_CD`）；代定清單、測試增減 |

使用者 11-01 晚裁了 1、2、5 → [02 § 使用者裁定](2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md#使用者裁定11-01-晚)（1 不用、2 到時候再說、5 不拿掉；3 後來裁「改」；4 傳話筒仍待裁，`AOS_ROUND_AGENT` 隨刪 aos-round 消失、剩 `AOS_IVY_BRAIN`、`AOS_IMPROVE_RUN`）。
