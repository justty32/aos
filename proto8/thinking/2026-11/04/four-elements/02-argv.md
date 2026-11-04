← [入口](README.md)｜涵蓋：argv（子命令與旗標）｜上一份 [01-環境變數](01-環境變數.md)｜下一份 [03-json-結構](03-json-結構.md)

# argv：形狀其實已經統一，只是沒寫下來

條文依據：N-58（`aos-exec [旗標] XXX [args]`：旗標在前、`--` 結束、不認得＝`FlagUnknown`）、N-60（錯＝退 1、stderr 一行 `程式名: 代號 原因`）、C-54（指令名底線換連字號、錯誤代號五種結尾）、R6（單位當後綴）、R13（`aos-<領域>-<功能>`）、使用者 10-15「少用 sh」。**NORMS 06 寫「aos 的命令列只有 aos-exec」、NORMS/10 寫「四支」——都過時**；現在有 11 支 C++、4 支 Python、7 支 extras 命令列。

## 解析器：兩套共用、五份自製、一份殭屍

| 解析器 | 用的人 | 判定 |
|---|---|---|
| C++ `parse_cli`（aos-util） | exec、loop、fsm、daemon、post、lock、json、llm-kernel、llm-send | 規則＝N-58 推廣到所有程式：長旗標 `--x V`／`--x=V`、無短旗標、`--`、`FlagUnknown`、缺值 `ArgumentsBad`、**沒有 `--help`**（錯時印 usage） |
| Python `aos_flags.parse` | tick、daemon-ctl、tools、eca-turn、say、listen | 規則同上。docstring「只剩 aos-tick 用」過時（低） |
| C++ `parse_flags`（舊一代，`--key_原名`、值當 JSON、設定從 stdin） | **沒人用**（cli.hpp 自己說） | **冗餘、必修：刪** |
| 自製 ×5 | aos-eca、aos-mcp、aos-grow、aos-sandbox、agent-fsm 的 `flags()` | 各自不同：eca／mcp／grow 旗標與位置參數可交錯；mcp 不認得的旗標回 `ArgumentsBad`（別人是 `FlagUnknown`）；grow 旗標在 CALLER 後；janet `--force` 只認第一個。中；Python 的改用 `aos_flags`，aos-agent 規劃一開始就用 `aos_flags` |
| 舊一代命令列 | aos-schema（`argc!=2`）、aos-directive（stdin 進、**錯誤印 JSON**） | 不合 N-60 一行文字；schema 收到 `--help` 會當檔讀、無 usage。低；改（幾行）或 README 標「舊一代」 |

## 子命令動詞

一致的：`add`／`rm`／`ls`（不是 remove／list）、`start`／`stop`、`pause`／`resume`、`open`／`close`——daemon-ctl、eca、tools、aos-agent 規劃都同。不一致的：

| 事 | 寫法 | 判定 |
|---|---|---|
| 看狀態 | `state`＝`status`（eca、規劃）、`show`（lock）、`get`（tools 取定義；json 取值）、`see`（post） | R4 一詞一義：`get` 在 json 與 tools 意思不同；`see`／`show` 同義。低；post `see`→`show` 一改就齊，`get` 兩義加註 |
| `rm` 的對象 | tools 收名字或路徑；daemon-ctl 收名字；eca 收資料夾或名字；規劃收名字 | 規劃統一成名字，舊的隨刪。不動 |
| aos-lua `ls` | 列「會寫哪些檔」，不是列登記項 | 一詞二義。低；加註 |
| aos-eca-turn `--one` | 一個旗標切換「工具形／平級形」兩種完全不同模式 | 這是子命令的事、不是旗標（C-54 好懂）。低；加註，等 aos-agent 落地再看 |

## 旗標命名

| 旗標 | 問題 | 嚴重度／建議 |
|---|---|---|
| `--stack` | 兩義：stack 路徑（exec、say、mcp、daemon-ctl add、eca、規劃）vs **proc 名字**（`aos-daemon-ctl where --stack 名字`） | 中；違 R4。改 `where 名字`（跟 rm／stop 同形）；規劃 `where --target` 已避開 |
| `--follow` | json＝穿過 `$ref`；listen＝像 `tail -f` | 低；加註（json 的可改 `--deref`，不急） |
| 時間 | `--interval-ms`、`--wait-ms`、`--lease-ms`（合 R6）；`--timeout-s`（mcp）；**`aos-listen --timeout` 無單位**；JSON 用 `timeout_ms`、lib 工具參數用 `timeout_s` | 中；違 R6。listen 改 `--timeout-s`；**aos-agent 規劃抄了 `listen [--timeout 秒]`，先改規劃**。ms／s 哪個當預設單位：程式間 ms、人殼 s 都可以，但後綴一定要有 |
| `--name` | grow＝檔名；其他＝登記名 | 低；不動 |
| 乾跑 | grow／sandbox `--dry-run`（預設做）；setup.sh `--apply`（預設乾跑） | 低；setup.sh 是 root 腳本、保守有理，加註 |
| `--enable-logs`、`--json`、`--ws` | loop／daemon／mcp、三支 ls、全體一致 | 合 |
| 不認得的旗標 | 大多 `FlagUnknown`；mcp、agent-fsm 腳本 `ArgumentsBad` | 低；改 |

## 位置參數、程式名、形狀

- **agent／XXX 都是旗標後第一個位置參數**（exec、daemon-ctl add、eca add、tools add、規劃 add）：一致。aos-eca-turn 的定義資料夾要**絕對路徑**（別人都收相對）：低，加註原因（loop 內嵌單子的 cwd）。
- R13：合的 `aos-llm-kernel`、`aos-llm-send`、`aos-eca-turn`、`aos-daemon-ctl`；單一領域只寫領域的 17 支；**`aos-say`／`aos-listen` 只有功能沒領域**（規劃併進 `aos-agent say／listen`，隨刪）。本機 build 殘留 `aos-kernel-llm`、`aos-gate` 執行檔（不進 git，低）。
- N-58 形狀「旗標在前、唯一設定檔、`--` 後接 args」照的：loop、daemon、fsm、kernel、send、tick、say、sandbox。不照：grow、mcp、eca（可交錯）、schema、directive、janet。→ 這個形狀**該不該升成全體規範**是 [06 題 7](06-要使用者裁的題.md)。
- `--help`：只有 aos-eca 有。其餘靠錯誤時印 usage——KISS 下夠用，但 schema／directive／janet 連 usage 都沒有。低；要不要統一做 `--help` 隨 06 題 7 一起裁。

## 隱性介面與層的越界

- aos-tools 跟可執行工具的契約靠 argv `XXX --tooldef`、`XXX --tool-call 任務檔`（＋`$AOS_STACK/tool_call.json`）：這是 aos 唯一替「別人的程式」訂 argv 的地方，P-41 沒寫。中；加進 P-41（使用者 11-04 晚「對外介面＝命令列參數…」，正好是介面宣告的材料）。
- aos-eca 解析定義的 loop.json、自己認 aos-eca-turn 的 `--prompt`（`TURN_FLAGS`）：上層複製了下層的旗標知識，違 C-52。中；aos-agent 規劃「add 不驗」落地後消失，先加註。
- aos-daemon-ctl `add` 看 `XXX/loop.json` 在不在決定 loop 型／exec 型（`:232`）：用檔名認種類（使用者 11-04「不太喜歡」）。見 [04](04-資料夾與固定名字.md)。

## sh

- 合規的：fixtures 11 個 `#!/bin/sh` 入口與工具（10-19 使用者：入口與格可以是 shell 檔）；aos-exec 對「+x 沒 `#!`」用 `/bin/sh`（N-59 使用者「乙」）；`lib/base/bash` 工具本身就是跑 bash；cli_session 給 claude 的 hook 字串（外部格式要求）。
- 不合：**aos-lua 用 `os.execute("mkdir -p …")`、`chmod` 字串**（`aos-lua:38-50`）——該改 Lua 的檔案 API 或 argv 陣列。低；改。

## 錯誤輸出

- 兩種格式並存：一行 `程式名: 代號 原因`（主流）vs JSON `{"error":…}`（schema、directive；`error.hpp` 檔頭還說 JSON 是規矩）。低；改兩支＋檔頭。
- fixtures ann、bob 的錯沒有代號（`sys.exit("agent-x: 原因")`）：低；改。
- aos-agent 規劃的 `Timeout` 不是五種結尾之一（C-54）：低；改成 `AnswerMissing`（等不到）或 `WaitFailed`。
