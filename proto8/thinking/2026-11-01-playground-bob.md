# 2026-11-01 試驗場現場：使用者邊說邊做（agents/bob）

← [thinking README](README.md)｜場地 `~/code/playground/`（`ws/` 清空、新建 `agents/`，使用者 `source env.sh && cd ws`）

狀態：進行中。本檔只記使用者原文（逐字）、決定、跟 AI 討論後的結論（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。

## 使用者原文（11-01 下午，逐字）

> 我把ws清空了，並且新建了agents資料夾。接下來就是用這兩個資料夾做事。並且我也source env.sh && cd ws了。好，接下來我會一步一步說我想幹嘛，你就告訴我要下啥指令，並且幫我準備好各種東西。途中我也會說一些想法，也請你幫我記錄下來。

> 好，我要輸入aos-exec ../agents/bob -- "幫我在env:AOS_WS寫一首詩，詠桃花。"。我預期bob他有read/write等基本工具，但是沒有shell。然後bob的system prompt中有說AOS_WS等環境變數分別代表啥，並且bob也知道自己所處的cwd(當然，bob是透過tool知道的)。跑起來之後，就是阻塞，直到bob執行完。bob是一個claude code -p

> 老實說，我覺得我們一直在濫用環境變數。環境變數在我們這個aos體系下，有點類似janet中的dyn，最好要謹慎，只在必要的時候使用。

## 做了什麼（頂層代做，可翻案）

- `agents/bob/`＝兩個檔、沒有程式碼：`_entry.json`（argv 陣列：`claude -p --model haiku --tools Read,Write,Edit,Glob,Grep --permission-mode acceptEdits --strict-mcp-config --max-budget-usd 0.3 --add-dir {$env AOS_WS} --append-system-prompt {$env BOB_SYSTEM}`）與 `.env`（一行 `BOB_SYSTEM="…AOS_WS=${AOS_WS}…AOS_CD=${AOS_CD}…"`，值由 aos-exec 讀 `.env` 時用 `${…}` 填進去——所以 bob 不用 shell 也知道各環境變數的值）。
- 題目裡 `env:XXX` 的寫法在 system prompt 裡解釋成「環境變數 XXX 的值」。
- aos-exec 會 cd 進 `agents/bob/`（AOS_CD），所以要 `--add-dir $AOS_WS` 讓 claude 的檔案工具能寫到工作區；system prompt 叫它別往自己的資料夾寫。
- `aos-exec ../agents/bob -- "題"`：`--` 與題目都原樣給入口，claude 認 `--` 當分隔（實測）。
- 實測：`aos-exec ../agents/bob -- "測試：在 env:AOS_WS 建一個 hello.txt，內容只寫 hi。"` 結束碼 0、檔案在 ws；之後清回空的。

## 環境變數要謹慎（11-01 使用者，待展開）

使用者的原則：環境變數像 Janet 的 `dyn`（動態綁定：誰在上面設了，底下所有人都看得到、又看不出是誰設的），**只在必要時用**。

對 bob 的直接影響（頂層照這條改了）：原本把 system prompt 塞進 `.env` 的 `BOB_SYSTEM`、再用 `{"$env": "BOB_SYSTEM"}` 餵給 claude，只是為了借 `${}` 填值——那是把環境變數當傳話筒，不必要。改成 `system.txt` 一個檔＋`--append-system-prompt-file system.txt`，工作區讓 claude 從 `--add-dir` 自己看到；bob 這格現在只剩 aos-exec 本來就給的 `AOS_WS`（`--add-dir {"$env": "AOS_WS"}`）這一處用到環境變數。

待使用者展開：哪些算「必要」（aos-exec 的六個 `AOS_*`？`AOS_BRAIN_URL`、`AOS_DAEMON`？10-31 補了前綴的 49 個名字裡哪些其實該改成 argv 或檔）——清單在 [naming-method § 10-31 已改](2026-10-23-naming-method.md)。

**盤點表已備（11-01 晚，隊長代做、待使用者裁）**：59 個 `AOS_*` 照判準分成必要 5、邊界 11、不必要→改 argv 20、不必要→改檔 22、沒人讀 1，程式沒改。

| 分檔 | 涵蓋 |
|---|---|
| [01-環境變數盤點](2026-11-01-playground-bob/01-環境變數盤點.md) | 怎麼核的、欄位、判準、分類小計、留意的幾點（每個變數一列在 [env-vars.json](2026-11-01-playground-bob/env-vars.json)） |
| [02-環境變數要使用者裁的問題](2026-11-01-playground-bob/02-環境變數要使用者裁的問題.md) | 五題：hub 型算不算必要、腦三個變數、格自己的旋鈕要不要一次性全改、傳話筒要不要加機制、`AOS_ENTRY` 要不要拿掉 |
