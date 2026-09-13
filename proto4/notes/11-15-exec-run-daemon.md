# proto4 想法筆記 §11–§15：exec、run 與 daemon
← [索引](2026-09-08-ideas.md)｜[README](../README.md)

## 11. 換個思路：inst.json 是「初版指令集」，先做單發的 aos-exec（proto4-3），再做連續版 aos-run

使用者原話（2026-09-09，看過 proto4-2 八欄版之後）：

> 我要換個思路。可能要請你開proto4-3。這次我們慢慢來。其實就如同cpu有不同指令集一樣，其實inst.json只是一種我們規定的，比較通用的初版指令集而已。真要說的話，更簡單的指令集那就是一個inst，所謂的執行就是讀入之後直接system()，只是說我們用inst.json規定了stdin/out/err,cwd,env等，算是在不增加複雜性的情況下，讓他具備基礎的可用性功能。喔不過timeout_ms我打算拿掉，這個時限應該是要由循環執行inst.json的傢伙掌管。對，我的目標是arm架構指令集。x86那樣啥都包，其實不太好。risc-v那樣沒有統一標準也不好。好，總之我們弄了這個inst.json，還有配套的執行這個inst.json的程式，inst.json的格式就是我們說的那樣，遵循posix呼叫的一個json物件，然後是單次執行inst.json的程式aos-exec，用aos-exec xxx去執行的時候，若xxx是檔案，那就是普通的執行，但若xxx是.json，那就是讀入並嘗試解析為inst.json的格式，若xxx是資料夾，那就是去執行xxx/.aos/inst.json（這個可以用--dir-target .aos/inst.json更改），然後若inst.json內的json格式，stdin/out/err/exit沒被指定，那就是指向dev/null，若cwd沒被指定，那就是默認為xxx，envs是json object，默認是增添（原先繼承於aos-exec），然後支援$ref, $env, $opt，其中envs可以吃$opt，用以清空原先繼承於aos-exec的，型式是{"$opt":"clear", "$envs":{...}}。然後aos-exec先實作最簡單的aos-exec xxx，flag就--dir-target, --timeout-ms，後續再做一些方便的，也就是直接把aos-exec的stdin/out/err/exit覆蓋inst.json。對了，inst.json中的stdin/out/err/exit這些path，可以用相對路徑，默認都是以inst.json的cwd為中心，包括$ref也是可以用相對路徑，同樣也是這樣。先這樣把東西弄出來，然後我們再來做aos-run，也就是aos-exec的連續執行版本，程式碼是可以復用的。盡量參考src，他那邊已經很成熟了

我的理解：

### 11.1 inst.json 的定位：像 ARM 那樣「小而統一」的指令集

- inst.json 不是「唯一的指令格式」，是我們規定的**第一版、比較通用的指令集**。最陽春的指令集就是「一個 inst 檔，讀進來 system()」（proto2 那樣）；inst.json 只是在不增加複雜度的前提下多給了 stdin／stdout／stderr／exit／cwd／env，讓它基本可用。
- 目標是 ARM 那種：不像 x86 什麼都包，也不像 RISC-V 沒有統一標準。所以**欄位要少、但每個都有定義**。
- **`timeout_ms` 拿掉**：時限不是指令的事，是「反覆執行 inst.json 的傢伙」（之後的 aos-run）的事。單發的 aos-exec 只用命令列旗標 `--timeout-ms` 自己管。

### 11.2 aos-exec：單發執行器（proto4-3，Python）

`aos-exec xxx [--dir-target REL] [--timeout-ms N]`，看 `xxx` 是什麼決定怎麼跑：

| `xxx` 是 | 做什麼 | cwd 預設 |
|---|---|---|
| 普通檔案（不是 `.json`） | 直接執行它（就是「一個 inst 讀進來就跑」那個最陽春的指令集），stdio 繼承 aos-exec 的 | 檔案所在的資料夾 |
| `.json` 檔 | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改這個相對路徑） | `xxx` |

inst.json 的欄位（七個，只有 `argv` 必填；**沒有 `timeout_ms`**，寫了算未知 key、拒絕）：

| 欄位 | 沒寫時 | 意思 |
|---|---|---|
| `argv` | 必填 | 跑什麼；`argv[0]` 走疊加後 env 的 PATH |
| `stdin` | `/dev/null` | 檔案當標準輸入 |
| `stdout` | `/dev/null` | 標準輸出寫到這個檔（建立並清空） |
| `stderr` | `/dev/null` | 同上；或 `{"$opt":"merge"}`＝跟 stdout 同一條 |
| `exit` | 不寫 | 跑完把結束碼（十進位＋換行；被 signal N 砍＝128+N）寫進去，fsync |
| `cwd` | 上表的預設 | 工作目錄；相對路徑從 `xxx`（資料夾／`.json` 所在資料夾）起算 |
| `envs` | `{}`＝只有繼承的 | 疊在 aos-exec 自己的環境上，只加不減；或 `{"$opt":"clear","$envs":{…}}`＝先清空繼承的，再只放 `$envs` 裡的（`$envs` 可省＝完全空的環境） |

跟凍結版、跟 proto4-2 不同的三件事：

1. **沒指定的串流一律 `/dev/null`**，不是繼承、也不是抓回 last.json。單發執行器不替你收輸出；要就自己寫檔名。
2. **相對路徑的中心是 cwd**（解析完的那個工作目錄），不是 `xxx`。`stdin`／`stdout`／`stderr`／`exit` 和 `$ref` 的相對路徑都一樣。只有 `cwd` 自己的相對路徑是從 `xxx` 起算（不然沒有中心可言）。
3. `envs` 多一個整個物件層級的 `$opt: clear`。這是唯一一個「指示詞物件不只一個 key」的例外（`$opt` ＋ `$envs`），寫在規格裡。

指示詞照 proto4-2／凍結版：`argv` 元素、五個路徑欄位、`envs`（含 `$envs`）的值可以是 `{"$env":"NAME"}`（讀 aos-exec 自己的環境；不存在＝錯誤、空＝空字串）或 `{"$ref":"file.json#/pointer"}`（相對於 cwd、RFC 6901、可巢狀、循環＝錯誤）。未知 key 拒絕。

**第四種指示詞 `$fmt`**（使用者補的：「envs 這塊，剛剛那個 PATH，得要用 `"PATH":{"$fmt":...}`」，然後「我記得以前有實作過 $fmt，去看看吧」）——用來接字串。repo 裡本來就有一套：`wf/tools/tabledb_fmt.py`，規格在 [data-files-fmt](../../wf/workflows/common/data-files-fmt.md)（資料檔的路徑代號）。aos-exec 沿用同一種寫法，只是這一版變數只有 `env:` 這個 namespace：

- `{"$fmt":"${env:PATH}:/opt/bin"}`：只有 `${…}` 會被代換；單獨的 `$`、`$PATH` 都是字面，不用跳脫。
- `${env:NAME}` 讀 aos-exec 自己的環境（不是 inst.json 的 `envs`）；不存在＝錯誤、空＝空字串。未知的 `${xxx}`＝錯誤。
- 展開一次、不再掃結果。
- 能寫 `$env` 的地方都能寫 `$fmt`。tabledb 那些 `${gitRoot}`／`${fileDirname}` 路徑變數這裡先不做，要的話之後加（inst.json 的自然候選是 `${cwd}`／`${target}`）。

所以使用者原本的例子 `"PATH":"$PATH:ahah"` 在這裡要寫成 `"PATH":{"$fmt":"${env:PATH}:ahah"}`。

aos-exec 的退出碼：`xxx` 用法錯／找不到＝2；inst.json 讀不到、不是物件、格式壞、指示詞解不開＝1（原因印 stderr）；其餘**原樣傳回子行程的結束狀態**（被 signal N 砍＝128+N；找不到程式 127、沒執行權 126）。`--timeout-ms` 到了先 SIGTERM 整個 process group、給 2 秒、還活著就 SIGKILL，退出碼就是 143 或 137。

「後續再做的方便功能」（這次不做）：用 aos-exec 自己的 stdin／stdout／stderr／exit 去覆蓋 inst.json 裡寫的；aos-run（連續執行版，時限與 interval 歸它管，程式碼跟 aos-exec 共用）。

### 11.3 我的定案（使用者沒講的）

- 語言 **Python**（問過使用者，他選這個）。直接搬 proto4-2 的 `aos_inst.py`（讀、驗、解指示詞）過來改，那份就是照凍結分支 `core/inst` 的規格寫的；proto4-3 自己一份，不 import proto4-2。
- 欄位名：我原本定 `env`（跟 §7、§10、凍結版一致），使用者隨即拍板改成 **`envs`**（「因為預期是 `"envs":{"PATH":"$PATH:ahah"}`」）。清空型式裡的 key 叫 `$envs`。寫 `env` 算未知 key。
- `envs` 清空之後 PATH 也沒了，找 `argv[0]` 退回 Python 的 `os.defpath`（跟凍結版「PATH 未設定就用 `_CS_PATH`」同一個意思）。
- 普通檔案模式不解析任何東西：`argv=[那個檔]`、stdio 繼承、沒有 exit 檔、env 就是繼承的。它沒執行位就是 126。
- 不注入 `AOS_DIR`／`AOS_TICK` 之類的環境變數——tick 是 aos-run 的事，aos-exec 保持乾淨。要不要有 `AOS_DIR` 之後撞到再說。
- `exit` 檔的父目錄不存在＝aos-exec 自己失敗（退出碼 1），不幫忙 mkdir；`stdout`／`stderr` 開不起來＝126（照凍結版 exec.md）。

還沒定、之後會撞到的：aos-run 要不要把 `--timeout-ms` 之外的停止條件（跑幾次、整體時限）都收進去、以及它怎麼跟 proto4-2 的 cpu／daemon／kernel 接（proto4-2 的 `aos_cpu.py` 的「跑一次」那段理論上就該換成呼叫 aos-exec）；`.json` 模式下 `.aos/` 的紀錄檔（last.json 那些）誰寫；普通檔案模式要不要也吃 `--timeout-ms`（先吃，反正是同一段砍法）。

### 11.4 proto4-3 做完後的補記（隊長撞到、我認可的）

- **`cwd` 最先解**：它自己的 `$ref`／`$fmt` 只能以 `xxx` 為中心，解完之後其他欄位才換成以 cwd 為中心。「`$ref` 相對於 cwd」跟「`$ref` 可以決定 cwd」本來互斥，靠這個順序擋掉。
- `envs` 物件裡只要出現 `$opt` 這個 key 就當清空型式，所以傳不了一個真的叫 `$opt` 的環境變數。
- `exit` 檔的父目錄在**開跑之前**檢查，不存在＝退出碼 1、指令根本不跑。`cwd` 不是資料夾＝126。
- 126／127／逾時的說明印在 aos-exec 自己的 stderr；有 `exit` 欄時這些碼照樣寫進 exit 檔（算跑過一次）。
- 空字串的路徑欄位等同沒寫；`--timeout-ms` 負數＝用法錯 2。
- 測試的坑：unittest 的 TestCase 不能有叫 `run()` 的輔助方法，會蓋掉 `TestCase.run()`，結果「Ran 0 tests / OK」。aos-run 的測試要避開。

proto4-3 落地：`aos-exec`＋`aos_exec.py`（核心 `run_target(xxx, dir_target, timeout_ms) -> 退出碼`，之後 aos-run 直接 import 反覆叫）＋`aos_inst.py`，106 條測試。

## 12. aos-run：aos-exec 的連續執行版（概念驗證，之後整合進 aos-daemon）

使用者原話（2026-09-09，proto4-3 做完之後）：

> aos-run算是概念驗證，之後會再整合進aos-daemon。好，aos-exec的flag，aos-run也有，然後在此之上又添加了你說的那些，interval的算法可以用--fixed-interval去設定（後面不接東西），若fixed-interval是true（有出現），那就是這樣的狀況：interval設置為五秒，於0秒執行一次，執行完之後是1.2秒，那麼仍然是在五秒後執行下次，若沒出現，那就是6.2秒後才執行下次。fixed-interval這個名稱我感覺有更好的選擇，你來做。

### 12.1 定案

`aos-run xxx [aos-exec 的旗標] [--interval-ms N] [--from-start] [--max-runs N] [--time-limit-ms N] [--stop-exit CODE]`

- **aos-exec 有的旗標它都有**：`--dir-target`、`--timeout-ms`（每一次執行的上限）。核心就是反覆呼叫 proto4-3 的 `run_target()`，不重寫。
- **`--interval-ms N`**（預設 1000）：兩次執行之間的間隔。時間旗標統一毫秒整數，跟 `--timeout-ms` 一致（使用者問「加個 --interval-ms 如何」，我選統一）。
- **`--from-start`**（不接值）：間隔**從上一次開始的時刻**算；沒加＝從上一次**結束**算。使用者的例子：interval 5、跑 1.2 秒，加了→第 5 秒跑下一次，沒加→第 6.2 秒。名字是我選的（使用者說 `--fixed-interval` 不好，讓我挑）：「從開始算」比「固定」講得清楚差在哪。
  - `--from-start` 時一次跑超過 interval：下一次**立刻**開始，不補跑錯過的格（下一次的起點＝max(現在, 上次起點＋interval)）。
- **停止條件**（任一成立就停）：
  - `--max-runs N`：跑滿 N 次（0＝不限）。
  - `--time-limit-ms N`：從 aos-run 起跑算的整體時限，**硬時限**：正在睡→醒來就退；正在跑→那次被砍（做法：呼叫 `run_target` 時把 `timeout_ms` 換成 min(原本的, 剩餘時間)，不用另開執行緒）。
  - `--stop-exit CODE`：某一次的退出碼等於 CODE 就停（可以給多次）。
  - SIGTERM／SIGINT：讓正在跑的那次跑完再退；第二次同一個訊號就直接砍正在跑的。
- **紀錄**：不寫檔。每跑完一次在 aos-run 自己的 stderr 印一行 `aos-run: #<第幾次> exit=<碼> <秒數>s`，停下來時再印一行為什麼停（`max_runs`／`time_limit`／`stop_exit`／`signal`）。要不要落檔（proto4-2 那種 last.json／runs.jsonl）等整合進 daemon 時再說。
- **aos-run 自己的退出碼**：用法錯 2；四種停止條件正常停下來都是 0。inst.json 壞掉那種 aos-exec 回 1 的狀況**不停**，照 interval 一直試（跟 proto4-2 的 cpu 一樣，壞了也活著），要停就 `--stop-exit 1`。
- **不注入 `AOS_TICK`／`AOS_DIR`**，跟 aos-exec 一樣乾淨（§8：proc 不需要知道自己被誰、以什麼節奏跑）。

### 12.2 還沒定、之後會撞到的

- 整合進 daemon 時 proto4-2 的 `aos_cpu.py` 那段「跑一次」要換成 `run_target()`，`last.json`／`runs.jsonl`／`cpu.json` 這些紀錄檔歸誰寫（cpu？aos-run？）。
- `--from-start` 累積漂移：現在是「起點＋interval」不是「aos-run 起跑＋n×interval」，長跑會慢慢往後漂；要不要改成對齊格子。
- 每次執行之間 inst.json 被換掉（先寫暫存再 rename）→ 下次自然讀到新的，沒問題；跑到一半被換也沒事（inst.json 只在開跑前讀一次）。

### 12.3 aos-run 做完後的補記

- 停止條件同時成立的優先序：`signal` → `stop_exit` → `max_runs` → `time_limit`。
- 第二次訊號要砍正在跑的那次，得拿到 `run_target()` 裡的 `Popen`，所以 `run_target` 多了一個選用的 `on_spawn` 鉤子（開起來叫一次、收完屍用 `None` 叫一次）。「第二次」是每個訊號各自數。
- `run_loop()` 有 `install_signals` 參數，當函式庫用（之後 daemon）可以不接管訊號。睡覺是 0.05 秒一步，訊號與硬時限最多晚 0.05 秒發現。
- `xxx` 只在起跑前檢查一次；跑到一半被刪，之後每次就是回 2、迴圈照走（跟回 1 一樣不算停止條件）。
- 使用者問「SIGTERM 會直接停掉整個 aos-run 嗎」→ 不會：第一次跑完手上那次再退、第二次砍；他說「這樣就好」。
- 使用者再問三件事（2026-09-09）：① `aos-exec foo/inst.json` 沒指定 cwd 時預設是哪→ **json 所在的資料夾 `foo/`**（資料夾模式也是 `foo/`，兩種寫法只差 json 檔名與位置可以自訂）。② 達到停止條件算不算錯誤→ **不算**，四種停止都是 0，就算是 `--stop-exit 3` 停的也是 0；真正的錯誤只有用法錯 2 和 aos-run 自己炸 1。③ SIGTERM／SIGINT 算不算預期內、灰色地帶怎麼算→ 用「有沒有腰斬工作」分而不是用「是不是訊號」分：**第一次訊號**＝有人客氣地叫停、手上那次跑完才退、退出碼 0（跟 nginx／systemd 服務一樣）；**第二次同一訊號**＝正在跑的被 SIGKILL 腰斬、不乾淨、退出碼 **128+N**（143／130），原因字串 `signal_forced`；SIGKILL 攔不住、系統給 137。使用者：「很好，就是這樣。」

實測（interval 500 ms、inst 睡 0.3 秒）：從結束算兩次起點差 0.80 秒、`--from-start` 差 0.50 秒；SIGTERM 一次→跑完那次、`stop signal`、退出碼 0。proto4-3 落地：`aos-run`＋`aos_run.py`，125 條測試。

## 13. aos-daemon（proto4-3 版）：一個 dict，key＝資料夾、value＝正在跑的 aos-run

使用者原話（2026-09-09，aos-run 做完之後）：

> 好了之後我們來看看aos-daemon，這個程式很簡單，就是維護一個dict，key就是某個資料夾路徑，value就是正在跑的aos-run。key就是aos-run的cwd。對，一個資料夾只允許一個aos-run在跑。然後是一些函數，包括增刪改查，還有暫停/繼續aos-run。

### 13.1 定案

- **daemon＝一個常駐進程，裡面一個 dict**。value 是**一個 `aos-run` 子進程**（`subprocess.Popen`，不是在 daemon 自己進程裡跑 `run_loop`）——這樣暫停／繼續＝SIGSTOP／SIGCONT、刪＝SIGTERM，跟 §7「一顆 cpu＝一個 Linux process」一致，也不用碰執行緒。
  使用者確認：「就是子進程，這樣省事。反正 import 之後還是得開 thread 跑，那樣反而失去了讓 linux 管理進程的方便性。」
- **key＝目標的基準資料夾的 realpath**：`aos-run foo/`→`foo`；`aos-run foo/inst.json`→`foo`；普通檔案→它所在的資料夾。**不拿 inst.json 裡的 `cwd` 欄位當 key**（那個欄位每次執行都可能被改、還可能是 `$ref` 解出來的）。同一個 key 第二次加＝拒絕、舊的不動。
- **增刪改查＋暫停／繼續**，七個動作：

  | 動作 | 做什麼 |
  |---|---|
  | `add` | 開一個 `aos-run <target> <旗標…>` 子進程，記進 dict。旗標＝aos-run 的那些（`--dir-target`／`--timeout-ms`／`--interval-ms`／`--from-start`／`--max-runs`／`--time-limit-ms`／`--stop-exit`）原樣傳 |
  | `remove` | 送 SIGTERM（aos-run 跑完手上那次自己退）、收屍、從 dict 拿掉。`force: true`＝再送第二次（腰斬），等不到就 SIGKILL |
  | `update` | 換旗標＝`remove` 再 `add`（aos-run 開跑後旗標改不了）。舊的跑完手上那次才換 |
  | `get` | 一筆：pid、target、旗標、started_at、paused、alive、runs（跑了幾次）、last_exit、last_line |
  | `ls` | 全部的 `get` |
  | `pause` | 對 aos-run 進程送 SIGSTOP。正在跑的那次會自己跑完（它在別的 session），只是不會開下一次；逾時砍人也跟著停（砍人的是 aos-run）|
  | `resume` | SIGCONT |

- **runs／last_exit 從哪來**：aos-run 不寫檔，但每次在 stderr 印一行 `aos-run: #n exit=c t s`。daemon 把子進程的 stderr 接成 pipe，一條執行緒逐行讀，解析出 `runs`、`last_exit`，整行留在 `last_line`，全部原樣 append 進 `daemon.log`。
- **aos-run 自己退了**（max_runs／time_limit／stop_exit／被別人殺）→ daemon 收屍、從 dict 拿掉、`daemon.log` 記一行（key、pid、退出碼、最後那行 `stop …`）。同一個資料夾之後可以再 `add`。不自動重開。
- **對外介面**：跟 proto4-2 一樣丟 JSON 檔——`<home>/requests/<名字>.json`（先寫 `.tmp` 再 rename），daemon 每 0.2 秒掃一次，處理完搬到 `requests/done/<名字>.json`、內容多 `ok`／`result`。這一版**沒有 kernel**，daemon 自己讀請求（§7.3 那個「kernel 是第一顆 cpu 跑的 proc」等整合時再回來）。`state.json` 每 0.5 秒寫一次＝`ls` 的內容，CLI 的 `ls`／`get` 直接讀它、不用等 daemon 回。
- **CLI** `aos-daemon start|stop|ls|get DIR|add TARGET [aos-run 旗標…]|rm DIR [--force]|update TARGET [旗標…]|pause DIR|resume DIR`，家走 `--home` 或 `AOS_HOME`。`start` 背景化、等 `state.json` 出現才回；`stop`＝對所有 aos-run 送 SIGTERM、等它們退、daemon 自己退。daemon 的生死照 §9：使用者手動管，壞了不歸 aos 管。
- 家目錄：`requests/`、`requests/done/`、`daemon.pid`、`state.json`、`daemon.log`。

### 13.2 還沒定、之後會撞到的

- 暫停中 inst.json 的 `--timeout-ms` 不生效（aos-run 被 STOP 了），要不要讓 daemon 代砍。
- `update` 會有一小段空窗（舊的跑完→新的開起來），中間丟進來的請求怎麼算。
- `.aos/` 紀錄檔（proto4-2 的 last.json／runs.jsonl／cpu.json）這版完全沒有，只剩 daemon.log 一條線；要不要回來、誰寫。
- 跟 §7.3 的 kernel（找 request 掛上去的那顆 cpu）怎麼接回來。

### 13.3 aos-daemon 做完後的補記

- 開子進程用 `sys.executable`；`add` 的 target 不存在＝`ok:false`；`pause`／`resume` 冪等；`update` 對表上沒有的＝`ok:false`。
- `remove` 回的 `exit` 把被訊號砍正規化成 128+N；`force` 的兩次 SIGTERM 中間隔 0.2 秒（連送會被核心併成一次）。暫停中的先 SIGCONT 再 SIGTERM，實測不叫醒會卡滿 5 秒再 SIGKILL。
- `remove`／收工是同步阻塞主迴圈的（每筆最多 5 秒）。
- 我收線時補一條：**請求成功、或收屍拿掉一筆，立刻寫 state.json**，不然 `rm` 後馬上 `ls` 還看得到（原本每 0.5 秒才寫）。
- 撞到的先天空窗：`add` 之後**馬上** `pause`，aos-run 可能還沒裝好訊號處理器就被 SIGSTOP，之後 SIGTERM 走預設處置直接死（143 不是 0）。沒補，測試改成等 `runs ≥ 1` 再 pause。
- `aos_daemon.py` 已經 300 行，再加功能要拆。

proto4-3 落地：`aos-daemon`＋`aos_daemon.py`＋`aos_daemon_cli.py`＋`aos_home.py`，142 條測試。實測 start→add→ls→pause（runs 不動）→resume（又動）→rm（`stop signal`、exit 0）→stop 都對。

### 13.4 翻案：aos-daemon 是普通前台程式，指令走 aos-daemon-ctl

使用者（2026-09-09）：「aos-daemon start 的具體原理是啥？是弄一個子行程掛到 root？然後 update 是啥？然後我預期 aos-daemon 他就是一個普通的程式，需要使用者在某個地方執行他，讓他持續跑著，然後我們再使用 aos-daemon-ctl add xxx 去對他下指令」

答：① `start` 是 Popen 一支 `aos-daemon run`、`start_new_session` 脫離終端、stdio 導 daemon.log、等 state.json 出現就退出——爸爸退了之後被 init 接手，就是「掛到 root」，不用 root 權限。② `update`＝rm 再 add（aos-run 開跑後旗標改不了），名字取壞了，其實是「重開」。③ 使用者要的形態才對，也才符合 §9「daemon 是硬體、生死使用者手動管」。

定案：
- **`aos-daemon [--home H]`**：普通前台程式，跑到 SIGTERM／Ctrl-C／`{"op":"stop"}` 為止。要放背景自己 `&`、tmux、systemd，aos 不管。家裡已有活的 daemon＝拒絕。沒有 `start`／`run`／`stop` 子命令。
- **`aos-daemon-ctl add|rm|restart|get|ls|pause|resume|stop`**：下指令的工具。`update` 改名 **`restart`**。`stop`＝丟請求請它收工（跟 SIGTERM 等價）。daemon 沒在跑：`ls`／`get` 照讀 state.json 但提醒是最後狀態，其他 op 直接拒絕。
- **`--home` 可省略**：`--home H` → `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`（使用者：「預設 ~/.aos-daemon 就好，--home 可省略」「環境變數也用 AOS_DAEMON_HOME」）。家＝daemon 與 ctl 靠檔案講話的那個資料夾（requests/、done/、daemon.pid、state.json、daemon.log），沒有 socket、沒有 port。

§13.4 落地：`aos-daemon`（前台）＋`aos-daemon-ctl`＋`aos_daemon_ctl.py`（原 cli 改名）＋`aos_home.py` 的 `resolve_home()`；142 條測試。實測：第二支同家＝「已經在跑」退出碼 1；`restart` 換 interval 後 pid 換新、表上一筆；`ctl stop` 後 daemon 退出碼 0；daemon 沒跑時 `ctl add`＝「daemon 沒在跑」退出碼 1。

## 14. 睡前一輪拍板（2026-09-09 晚）：還沒定的問題逐條決定

使用者：「紀錄檔先不要，kernel 之後再說。剩下的……跳選項吧。」兩輪選項的結果：

| 問題 | 決定 |
|---|---|
| `--from-start` 長跑漂移 | 先不改 |
| inst.json 壞掉（aos-exec 自己失敗）跟子程式回 1 分不出來 | **分開**：aos-exec 自己失敗退出碼 **125**（用法錯仍 2）；`run_target` 回 `(code, kind)`，kind＝`child`／`aos`／`usage`；aos-run 加 **`--stop-on-error`**（撞到 kind=aos 就停，原因 `error`，退出碼 125） |
| add 後馬上 pause 的訊號處理器空窗 | **補，走專用 fd**（使用者：stdio 以後可能跟 inst.json 共用，不能拿 stderr 當通道） |
| 暫停中逾時砍人不生效 | **補：pause 先等手上那次跑完** |
| restart（rm 再 add）卡住 daemon 主迴圈最多 5 秒 | **改成不卡** |
| `$fmt` 加 `${cwd}`／`${target}` | 先不加 |
| proto4-2 | 留著、README 標作廢 |
| `.aos/` 紀錄檔（last.json 那些） | 先不要 |
| §7 的 kernel 接回來 | 之後再說 |

我把中間三條合成一個設計（比各補各的乾淨）：

- **aos-run 多一條 `--status-fd N`**：往這個 fd 寫事件行 `ready`／`start #n`／`done #n exit=c kind=k t.ts`／`stop 原因`。daemon 開 pipe 交給它、讀這條拿 runs／last_exit／在不在跑，**不再解析 stderr**；stderr 只進 daemon.log 給人看。`ready` 在裝好訊號處理器之後才寫。
- **pause＝等它睡著再凍**：daemon 標 `pause_pending`，主迴圈看到 entry 已 `ready` 且不在跑（上一個事件是 `done`）才送 SIGSTOP、改 `paused`。同時解掉「還沒裝處理器就被凍」與「暫停中沒人砍逾時」兩個問題。interval 極短時 SIGSTOP 可能剛好落在下一次開跑之後，那次會跑完才真的停——不保證零次，寫在文件裡。
- **rm／restart 不卡**：rm 送完 SIGTERM 立刻回 `stopping`，主迴圈收屍、過 5 秒還活著就 SIGKILL；restart 標 `restarting`＋新 args，舊的退了才用新 args 開。entry 多 `state` 欄（`running`／`pause_pending`／`paused`／`stopping`／`restarting`），`ls` 的 PAUSED 欄換成 STATE。**ctl 那邊照舊等到表上真的變了才回**（rm 等 key 消失、restart 等 pid 換新、pause 等 `paused`），使用者用起來還是同步的。

補一條（使用者，我先看反一次再更正）：「envs 也不能有 $ref、$env 等」「我的意思是 envs 也是可以吃 $ref、$fmt 的」→ **envs 這個位置本身也可以放指示詞**：`"envs":{"$ref":"shared.json#/envs"}` 整包從別的檔拿（解出來必須是物件，可再巢狀）；清空型式的 `$envs` 同樣可以是 `$ref`；`$env`／`$fmt` 放在這裡解出來是字串、算型別錯。所以 `$ref`／`$opt` 這些在 envs 這層是指示詞、不是變數名，「傳不了一個叫 `$opt` 的環境變數」是規則不是問題。

再一般化（使用者：「對，可以巢狀，inst.json 中的所有東西都吃這些 $...，並且可以巢狀（要紀錄路徑，避免無限巢狀）」）→ **inst.json 裡任何位置的值都可以是指示詞**：頂層整份（`{"$ref":"base.json"}` 當模板）、每個欄位、`argv` 整個陣列與每個元素、`envs` 整個物件與每個值。做法是「先解、再驗」：解出來的值當那個位置本來就寫的，遞迴解到不是指示詞為止，最後才照該位置的型別驗。`$env`／`$fmt` 出來一定是字串、`$ref` 可以是任何 JSON、`$opt` 只在 stderr（merge）與 envs（clear）合法。循環用 `$ref` 既有的「realpath＋pointer」鏈擋，頂層指回自己也擋。解的順序：頂層→`cwd`（這兩個以 `xxx` 為基準）→其餘欄位（以 cwd 為基準）。

### 14.1 落地補記

- 我自己決定的：`kind=aos` 那次的 `exit=` 一律報 **125**（原本 status 與 stderr 都印 run_target 的 1），跟 aos-exec 命令列同一個號、跟子程式自己回的 1 分得開。
- 跟著改的：`--stop-exit 1` 因此不會再被「aos-exec 自己失敗」誤觸。
- 逐條對過 §14，程式都落地了；沒測試的只有兩條，補上：`ready` 真的在訊號處理器之後（看到 ready 就 SIGTERM，退出碼 0 不是 143）、`restart` 不卡主迴圈（手上那次跑一秒，指令 0.3 秒內回、每圈也 0.3 秒內）。
- 坑：`test_daemon.py` 破 300 行要拆，但子類別繼承基底會把基底的測試再跑一遍——基底改放 `_daemon.py`（底線開頭，`unittest discover` 不撿）。
- 測試 165 → 173 條，全綠。

## 15. 翻案：daemon 的 key 改成 inst.json 的路徑，不收資料夾（2026-09-10）

使用者：「我們現在是用路徑作為一個 aos run 的唯一標示，我要換成用那個 .json 的路徑作為唯一標示，不允許資料夾。」跳選項再補兩條：普通檔案（不是 .json）**也拒絕**；add 時那個 .json **存不存在都收**。

定案：
- **key＝那個 `.json` 檔的 realpath**（symlink、`..`、相對路徑算同一個）。同一個資料夾可以掛好幾個不同的 inst.json，各自一支 aos-run。
- **`add`／`restart` 只收副檔名 `.json` 的路徑**：資料夾、普通檔案一律拒絕（result 說清楚原因）。檔案不存在照收——aos-run 每次跑會回 125（kind=aos），檔案出現了就自然跑起來。
- **`rm`／`get`／`pause`／`resume` 也收 .json 路徑**（ctl 的參數名從 DIR 改 FILE），存不存在都照 realpath 查表。
- **ctl 的 `add`／`restart` 不再有 `--dir-target`**（daemon 開 aos-run 時不會傳這個旗標；aos-run／aos-exec 自己還留著，單獨用時照舊）。
- state.json 與 `ls` 的第一欄就是 .json 路徑。
- §13.1「key＝資料夾」那條作廢，其餘不動。

### 15.1 落地補記

- `base_dir()` 改名 `key_of()`＝`realpath(abspath(target))`；「只收 .json」另外一個 `json_only()`，兩個都在 `aos_daemon_entry.py`。
- 我自己決定的：請求的目標欄位七個動作**統一叫 `target`**（原本 add／restart 是 target、其餘是 dir），舊的 `dir` 直接沒了。
- 我自己決定的：名字叫 `x.json` 的**資料夾**照資料夾拒絕（先看 isdir 再看副檔名），跟 aos-exec 認目標的順序一致。
- 規格沒寫但不做就辦不到的一條：`.json` 路徑不存在時，aos-exec 從「用法錯 2」改成「aos 自己失敗 125」，aos-run 起跑前也不再擋 `.json`——不然「檔案不存在照收」那筆會立刻死掉。
- 我自己決定的：daemon 不擋請求裡自己塞的 `--dir-target`（ctl 擋、退出碼 2 就夠了），目標是 `.json` 時那個旗標本來就沒作用。
- ctl 的表頭與訊息 DIR 全改 FILE；`ls`／`state.json` 第一欄就是那份 `.json` 的路徑。
- 新增的測試：同資料夾兩份各一筆、資料夾拒絕、普通檔案拒絕、不存在的 `.json` 收得下（累積 `exit=125 kind=aos`，檔案出現就變 child）、symlink 算同一筆、ctl 帶 `--dir-target` 退出碼 2、每個 op 都吃 `target`。共 173 條，全綠。

