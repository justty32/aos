# 任務書：daemon／kernel 規範草稿（2026-09-22）

使用者一句話：「開 agent 去看看 proto4 的 daemon 和 kernel，然後一樣在 spec 寫規範，我要審閱。」

## 要做什麼

把 proto4-3 的 **aos-daemon**（管一堆 daemon 行程、家目錄、ctl）與 **aos-kernel**（排程：tick、module、
syscall、add／status）**現在真正的行為**整理成 proto5 的規範草稿，讓使用者逐條審。**不是重新發明**：照
proto4-3 現況寫、跟 proto5 已定的東西對齊、差異標出來。

**規範分兩種（使用者定的）**：**JSON 格式（協議）** 一份、**程式** 一份，跟現有的分法一樣——
`inst-posix.md`（格式）↔ `exec.md`（程式 aos-exec）、`agent.md`（格式）↔ `aos-agent.md`／`aos-llm-ask.md`（程式）。
格式那份講「檔案長什麼樣、欄位、選項、錯誤代號」，程式那份講「命令列、做什麼、狀態轉換、退出碼」。

產出：

| 檔 | 內容 |
|---|---|
| `proto5/spec/<daemon 的格式>.md` | daemon 家目錄與裡面的檔（請求檔、狀態檔、記錄…）長什麼樣：欄位、型別、預設、解不解指示詞、錯誤代號。檔名你照內容取（例如 `daemon-home.md`），回報說明 |
| `proto5/spec/aos-daemon.md` | 程式：aos-daemon 與 aos-daemon-ctl 的命令列、生命週期、做什麼、退出碼 |
| `proto5/spec/<kernel 的格式>.md` | kernel 家目錄與檔（行程表、module 的形狀、syscall 的請求／回應格式…）：同上。檔名你照內容取（例如 `kernel-home.md`；syscall 若夠大可以自己一份） |
| `proto5/spec/aos-kernel.md` | 程式：boot／init／tick／add／status 等子命令、一格 tick 做什麼、排程怎麼選、module 怎麼被叫、退出碼 |
| `proto5/spec/aos-run.md` | **只有在** proto4-3 的 aos-run 真的是獨立一層、值得單獨一份時才寫（不然併進 aos-kernel.md 一節，回報說明） |
| （`proto5/README.md` **不要改**：另一個 agent 也會動它。把要加的規範表列子寫在回報裡，我來貼） |

格式那份跟程式那份互相連結；同一件事只寫在一邊（格式那邊講形狀、程式那邊講行為），別兩邊重複。

## 先讀什麼

1. proto5 的風格與已定的概念（**先讀，術語要跟它們一致**）：`proto5/README.md`、`proto5/spec/exec.md`（**這份就是「照 proto4-3 現況整理」的範本**，開頭那段提醒、一句話、表格、退出碼、末尾「我自己選的」清單，照這個樣子寫）、`proto5/spec/inst-posix.md`、`proto5/spec/directives.md`、`proto5/spec/agent.md`、`proto5/spec/aos-agent.md`（aos-agent 退 101＝在等，kernel 之後要靠這個排程）。
2. proto4-3：`README.md`、`docs/daemon.md`、`docs/kernel.md`、`docs/run.md`、`docs/files.md`，再對程式碼確認文件沒漏的行為：`aos_daemon*.py`、`aos_kernel*.py`、`aos_run*.py`、`aos_home.py`，測試 `test/` 裡跟 daemon／kernel／run 有關的。
3. 後面幾輪怎麼用 kernel（只看用到的部分、不要寫進規範主體，只當「kernel 要撐得起這些」的參考）：`proto4-5/README.md`（llm-cpu 掛成 kernel module）、`proto4-7/README.md`（agent 交給 kernel 的 LLM 排程、101 讓出 CPU）。

## 規則

1. **規範只講現在**：不記修訂記錄、不講 proto4-1／4-2 怎麼演變。但每份末尾加一節「跟 proto4-3 差在哪」，
   列出你為了對齊 proto5 而改的地方（例如：逾時是 aos-run／kernel 的事而不是 inst 的、`.json` 不存在＝125、
   `run_target()` 回 `(code, kind)`、家目錄的環境變數名）——每條一行，讓使用者審的時候有得對。
2. **不要寫太瑣碎的東西**、KISS：命令列、檔案形狀、狀態轉換、退出碼、錯誤代號這些要；實作細節（用哪個
   Python 函式、鎖怎麼拿）不要。每份規範目標 150～250 行。大白話、中文、跟現有規範一樣用表格。
3. 拿不定的地方**不要自己拍板後不說**：照 proto4-3 的做法寫進主體，然後放進末尾「我自己選的、使用者可以
   推翻的」清單；真的沒依據的就在該處標「（待使用者定）」。
4. 只動上表列的新規範檔。**不要碰** `proto5/README.md`、
   `proto5/lib/`、`proto5/cli/`、`proto5/spec/agent.md`／`aos-agent.md`／`aos-llm-ask.md`（另一個 agent 正在那邊寫程式）。
5. 連結用相對路徑（參考 exec.md 開頭那行 `← [proto5 README](../../README.md)｜…`）。
6. 不 commit。
7. 回報用中文、條列：寫了哪幾份、各幾行；「跟 proto4-3 差在哪」那些條；「我自己選的」那些條；proto4-3 文件跟程式
   碼對不上的地方（如果有）；你覺得使用者最該先看的三個問題。
