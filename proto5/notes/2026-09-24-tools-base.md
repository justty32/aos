# base 工具包（2026-09-24）

← [notes 索引](README.md)｜工具說明：[tools/README.md](../tools/README.md)｜裝法規範：[aos-agent.md §1.7](../spec/aos-agent/tools.md)｜審查：[任務書](2026-09-24-tools-base-review-task.md)、[astra 報告](2026-09-24-tools-base-review-astra.md)

使用者原話：「aos-agent 用起來手感不錯，麻煩開一條線，幫我弄一些基礎工具包吧，就是 pi coding agent 的那些。」

## 做了什麼

- **工具包 [`proto5/tools/base/`](../tools/base/)**：read、write、edit、bash、grep、find、ls 七支，純 Python 標準庫。
  給模型看的描述與參數在 `base.json`（英文，措辭參考 pi），共用邏輯在 `_common.py`。
  成功印純文字；失敗退 1、最後一行一個 JSON `{"ok": false, "error": 代號, "message": …}`（代號表在 tools/README）。
- **工作根目錄**：工具的 cwd 照規範是 agent 家，所以根目錄放在工具包自己的 `config.json` 的 `root`（相對 agent 家），沒給＝`<家>/workspace/`。
  read／write／edit／grep／find／ls 關在根目錄裡（解開符號連結再比）；bash 只是從根目錄開始跑，**沒關**。
- **bash**：逾時預設 120 秒、上限 600 秒，砍整個行程群組；stdout＋stderr 合併，邊讀邊丟、只留最後 2000 行／50 KB（`yes` 跑到逾時也只吃幾百 KB 記憶體）；stdin 空；指令結束時把它留下的背景行程一起收掉。kernel 那層 `_timeout_ms` 給 630000，讓 bash 自己的 `Timeout` 先到。
- **裝法 `aos-agent tools add NAME|DIR [--target] [--root DIR] [--force]`**（選了這個、沒做 `init --tools`）：程式複製到 `<家>/tools/<名>/`，工具檔最後寫到 `<家>/tools/<名>.json`；
  `init` 的家 `tools` 本來就是整個資料夾，下一格就吃到，不用重 start；手動家的 `info.tools` 沒涵蓋就自動補一條。同名、壞工具包、`$ref` 的 tools 都擋下、什麼都不寫。
  為什麼選它：舊家（例如使用者已經在用的 bob）也能裝，也對得上使用者 thinking/aos-agent.md 裡 `tools add` 的構想；`init --tools base` 只是 init＋tools add，列為未來可加。

## 實跑（LiteLLM `http://localhost:4000/v1`、`deepseek-chat`，沒碰 LM Studio／ollama）

工作目錄 `scratchpad/tools-base/`；daemon＋kernel（4 顆一般 cpu＋llm）＋一個 agent，人格「你是 coding agent，用工具實際動手，一次只叫一個工具」。

**第一趟**：「在工作目錄建一個 hello.py 印出 hello；跑它；再把 hello 改成 hi（用 edit）；再跑一次。」`say --wait` 43 秒回話，檔案最後是 `print("hi")`。模型叫的工具：

| 順序 | 工具 | arguments | 結果 |
|---|---|---|---|
| 1 | write | `hello.py`、`print("hello")\n` | `created hello.py (15 bytes)` |
| 2 | bash | `python3 hello.py` | `hello` |
| 3 | edit | `print("hello")` → `print("hi")` | `edited hello.py: replaced 1 occurrence (first at line 1)` |
| 4 | bash | `python3 hello.py` | `hi` |

write 1、bash 2、edit 1，共 4 次，順序正是 write→bash→edit→bash。

**第二趟**（七個都用上）：「建 calc/a.py 兩行都是 `x = 1`，只把第二行改成 `x = 2`，再 find／grep／ls／read 確認。」45 秒。
write 1（自動建 `calc/`）→ edit 1（模型自己想到兩行一樣、把兩行一起當 old_string 才唯一）→ find、grep、ls 同一批平行 → read 1，共 6 次，結果全對。
兩趟結束 `pgrep -fa tools-base` 都是空的，`status` 都是 `health ok`、`errors 0`。

**astra 修完後再跑兩趟**：第一趟原題重跑，一樣 write→bash→edit→bash 四次、43 秒、結果對。
第三趟故意犯錯：叫它 edit 時 old_string 只寫 `x = 1`（檔裡有兩行）→ 工具回 `NotUnique`（附 `lines 1, 2` 與「加上下文或 replace_all」），模型下一步自己把兩行一起當 old_string、改對；
接著 read 確認、bash 跑不存在的 `nope.py`（模型自己在指令尾巴加了 `echo exit=$?`，所以沒觸發 `ExitCode`，錯誤訊息照樣看得到）。共 write 1、edit 2（1 錯 1 對）、read 1、bash 1。

## 測試

全測 **1153 → 1292 條**（33 → 37 檔），連跑兩次綠：`cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test`。

| 檔 | 條數 | 內容 |
|---|---:|---|
| [test_tools_base.py](../lib/test/test_tools_base.py) | 85 | 共用參數與 config、OutsideRoot（`..`、絕對路徑、符號連結）、read 截斷與分頁、write 建目錄與權限、edit 唯一／NoMatch／NotUnique／replace_all／CRLF、grep（rg 與強制退回 grep 同格式）、find、ls、base.json 形狀 |
| [test_tools_base_bash.py](../lib/test/test_tools_base_bash.py) | 11 | 輸出合併、cwd、退出碼、逾時、截斷、背景行程、stdin 空 |
| [test_tools_base_fix.py](../lib/test/test_tools_base_fix.py) | 29 | astra 審查後的補強（見下節） |
| [test_agent_tools.py](../lib/test/test_agent_tools.py) | 14 | tools add 的各種家與錯誤；真 daemon＋kernel＋agent＋假模型照劇本 write→bash→edit→bash |

（單元測試由 Sonnet 子隊寫，照實際輸出斷言；它沒找到工具 bug。）

## astra 審查（[原報告](2026-09-24-tools-base-review-astra.md)）

**必修 7 條，全修；建議 9 條，修 7 條（#8 的 edit 同檔併發、#15 對 pi 的能力差距只記下）。**

| # | 題 | 怎麼修 |
|---|---|---|
| 1 必 | write／edit 暫存檔名固定、會踩到預先放好的符號連結 | 改 `mkstemp`（隨機名＋`O_EXCL`），打開後再驗位置；新檔權限照 umask |
| 2 必 | 路徑檢查跟實際打開分開，有 TOCTOU | read／edit 改用 `open_regular`：打開後用 `/proc/self/fd` 再驗在根目錄裡；規範與 README 把承諾講清楚：**防手滑、不是沙盒**（bash 本來就不關，完整 `openat2` 不做） |
| 3 必 | rg 吃 `RIPGREP_CONFIG_PATH`，裡面有 `--follow` 就能走出去 | rg 加 `--no-config --no-follow` |
| 4 必 | grep 的 30 秒只在有輸出時才檢查、stderr 可能死鎖、逾時被報成「沒找到」、外層砍不到搜尋行程 | 重寫：兩條 pipe 各一條執行緒邊讀邊丟、逾時與輸出無關、逾時回 `Timeout`（附已找到的）、任何結束都收整個群組、被 TERM 也收 |
| 5 必 | `--force` 重裝有「工具檔在、程式不在」的空窗，崩潰後狀態不一 | 改成版本資料夾＋符號連結：`tools/base`→`tools/.base-<版>/`，換連結是原子的；工具檔在但 info 沒登記＝修復，不必 `--force`；下次裝順手清殘渣 |
| 6 必 | 輸出有上限、讀取沒有：read 整檔讀進來、edit 無上限、grep 等整行 | read 改逐行讀、長行讀到上限就丟；edit 上限 10 MB（`FileTooLarge`）；FIFO／裝置回 `NotARegularFile`；grep 行緩衝有上限 |
| 7 必 | bash「背景行程都會被殺」講過頭 | 描述改成「`cmd &` 會被收掉、別開伺服器」，README 寫明 `setsid`／`nohup` 逃得掉；wrapper 被 TERM 時收掉子群組 |
| 8 建 | 兩個 `tools add` 同時跑互相蓋 info；同檔兩個 edit 互蓋 | `tools add` 整段持 `info.json` 的 flock；edit 併發不修（人格已叫它一次一個） |
| 9 建 | 「根目錄包含 agent 家」的警告沒解符號連結 | 兩邊都 realpath 再比 |
| 10 建 | grep 退回 `grep -E` 時語法、gitignore 不同，描述卻說 ripgrep | 描述改寫（沒 rg 時語法較窄、別用 `\d`），README 表列出差異 |
| 11 建 | read 2000 行不是硬上限；schema 沒寫上限 | read `limit` 上限 2000；schema 補 `minimum`／`maximum`／`minLength` 與各上限 |
| 12 建 | NUL、孤立 surrogate 會噴 Traceback | `arg()` 擋成 `BadArguments`；`run()` 兜底，沒料到的例外也是最後一行 JSON（`InternalError`） |
| 13 建 | find 讀不到資料夾時靜默 | 結尾加一行 warning（幾個被跳過、第一個是誰） |
| 14 建 | 工具包叫 `foo.json` 會跟別包的工具檔撞名 | 名字只收英數、`_`、`-`（`BadName`） |
| 15 建 | 比 pi 少：多段 edit、長行續讀、完整 bash 輸出存檔、圖片 | 只加了 edit 的 CRLF 提示、read 長行提示改用 bash；其餘列在下面要拍的 |
| 16 建 | 驗證順序跟規範不同；工具檔驗完又重讀 | 順序改成跟規範一致（家→包→root→裝過沒→同名→info）；寫進去的就是驗過的那份 |

補強測試在 [test_tools_base_fix.py](../lib/test/test_tools_base_fix.py)（Sonnet 子隊寫）。

## 要使用者拍的

1. **工作根目錄怎麼定**：現在是「工具包的 `config.json` 的 `root`，預設 `<家>/workspace/`」。另一種是預設就用 agent 家（pi 的做法是用開它的目錄），但那樣模型改得到自己的 info.json、記憶。要不要換、或要不要改成環境變數？
2. **bash 要不要白名單／沙盒**：現在 bash 什麼都能跑、碰得到根目錄外面（跟 pi 一樣）。要不要加：指令白名單、禁網路、或乾脆跑在容器／bubblewrap 裡？
3. **bash 結束時收掉背景行程**：現在一律收（避免模型開的伺服器之類留下來沒人管）。想讓模型能開長駐程式，就要另外設計（例如交給 kernel 登記成反覆工作）。
4. **給模型的描述用英文**（跟 pi 一樣、模型最熟），錯誤訊息也是英文；人格與回話照舊中文。要不要換中文？
5. **跟 pi 還差的**（astra #15）：一次多段 edit、長行分段續讀、bash 完整輸出另存一份檔讓模型事後 read、read 圖片。要哪幾個？
6. **`init --tools base`** 要不要加（等同 init 之後 tools add）；`tools ls／remove` 要不要做（thinking/aos-agent.md 有構想）。

## README／教程該加的（這隊沒改 proto5/README.md）

- 第 6 段「自己寫一支工具」前面加一段：「**想當 coding agent 用**：`aos-agent tools add base --target $W/bob`（要在某個專案裡工作就加 `--root ~/proj`），人格改成 coding agent，說一句『建 hello.py 印 hello 再跑它』。七個工具與錯誤見 [tools/README.md](tools/README.md)。」
- 「程式」表加一列：`[tools/](tools/README.md)｜工具包：base＝read／write／edit／bash／grep／find／ls｜tools add 裝`；lib 那列測試數字 1153 → 1292、33 → 37 檔、二十九支 → 三十支模組。
- 規範表 aos-agent 那列補「`tools add`（§1.7）」。
