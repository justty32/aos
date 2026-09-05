# 12 指令面
← [入口](README.md)

先定人要打什麼，底層再補上去〔裁決 2026-08-30〕。指令分兩組：一組操作資料夾（一塊地），一組操作住在裡面的 agent。三層各一個名字、核心名冊、正本規範、版本欄與 `init`／`reset`／`migrate` 拆在 [12b](12b-roster-and-canon.md)。

## 全表

「讀」「寫」只列它自己碰的檔，路徑相對於那塊地；歸屬表在 [02](02-layout.md)。

| 子命令 | 引數與旗標 | 退出碼 | 讀 | 寫 |
|---|---|---|---|---|
| `aos init [<地>]` | `--tmpfs`（實驗開關，見 [13](13-doorman-l1.md)）；地省略＝目前資料夾 | 0 2 | 目前資料夾 | `.aos/layout.json`、`.aos/config.json`、`.gitignore` |
| `aos publish <落點> --from <檔>｜--fail <reason>` | `--message <字>` | 0 2 4 | 落點所在目錄 | 落點，或 `<落點>.status.json` |
| `aos exec [<地>]` | `--timeout <ms>`、`--interface <程式>` | 0 2 3 4 75 | 版面、模板、接力棒、收件匣、控制收件匣 | 接力棒、`.aos/ticks/<N>/`、`.aos/frames/`、`.aos/calls/`、`.aos/mail/`、`.aos/lock` |
| `aos run [<地>]` | `--steps N`、`--every <ms>`、`--until idle｜never`、`--budget N`、`--timeout <ms>`、`--register`、`--interface <程式>` | 0 2 3 4 5 75 | exec 讀的全部＋登記表 | exec 寫的全部＋`.aos/stopped.json`＋登記表 |
| `aos deliver <目標地> --inst <json 檔>｜--mail <主旨> [--body <檔>]｜--llm <json 檔>` | 三選一 | 0 2 4 75 | 目標地版面、目標地 `.aos/config.json` 的 `inbox_max` | 目標地 `.aos/inbox/<id>.json` |
| `aos stop <地>` | `--kill`；不帶 `--kill` 最壞等當下那筆指令的 `timeout_ms`；沒人在跑就不投信、退出 0 | 0 2 4 | 登記表、`.aos/lock` | `.aos/control/<id>.json`；`--kill` 改成送訊號＋改登記表 |
| `aos daemon start` | `--home <路徑>`、`--doorman`（同時起門房） | 0 2 | 使用者層 `config.json`、登記表 | `daemon.pid`、登記表 |
| `aos daemon stop` | 無 | 0 2 | 登記表 | 登記表、各地 `.aos/control/` |
| `aos daemon add <地> --steps N｜--every <ms>｜--until idle｜never` | `--budget N`；只登記不開跑 | 0 2 4 | 登記表 | 登記表（一筆 `pending`） |
| `aos daemon exec <地>` | `--id <id>`、`--clock once｜steps N｜every <ms>｜until idle`、`--budget N` | 0 2 4 | 登記表 | 登記表（一筆登記） |
| `aos daemon ls` | `--json` | 0 2 | 登記表 | 不寫 |
| `aos mv <來源地> <目的地>` | 無 | 0 2 4 75 | 登記表 | 登記表、檔案系統 |
| `aos migrate <地>` | 無 | 0 2 4 | `.aos/layout.json` | 不寫（第一版只印訊息） |
| `aos status [<地>]` | `--all`、`--json`、`--request <id>`、`--triple <落點>` | 0 2 4 | 登記表、接力棒、`.aos/stopped.json`、`.aos/calls/`、`.aos/program/` 檔頭、LLM 世界的 `.aos/requests/` | 不寫 |
| `aos fix [<地>]` | `--dry-run`、`--requeue` | 0 2 4 | 登記表、`.aos/lock`、接力棒、`.aos/ticks/`、`.aos/inbox/` | 登記表、`.aos/lock`、接力棒、`.aos/ticks/<N>.crashed/`、`.aos/inbox/` |
| `aos check [<地>]` | `--json` | 0 2 3 4 | 版面全部 json、`schemas/` | 不寫 |
| `aos reset <地>` | `--all` | 0 2 4 75 | 接力棒 | 接力棒（`--all` 直接刪掉它） |
| `aos config get｜set <鍵> [<值>]` | `--home`（改使用者層那份） | 0 2 3 4 | `.aos/config.json` | `.aos/config.json` |
| `aos tool add <名> -- <argv…>｜ls｜rm <名>` | `--description`、`--args`、`--stdin`、`--predictability`、`--slow`、`--example`、`--help-file`、`--cwd`、`--metainfo`／`--metadata`／`--no-probe`、`--json`（11 的 S-11-49） | 0 2 4 | `.aos/tools/` | `.aos/tools/<名>.json` |
| `aos contact add <名> <路徑>｜ls｜rm <名>` | `--note`、`--json` | 0 2 4 | `.aos/contacts.json` | `.aos/contacts.json` |
| `aos llm serve <地>` | `--every <ms>`（預設 200）、`--until idle｜never`（預設 `never`） | 0 2 3 4 5 75 | LLM 世界版面、`.aos/units.json`、`.aos/inbox/`、`.aos/control/` | `.aos/requests/`、結果落點、帳簿、`.aos/lock`、`.aos/stopped.json` |
| `aos llm init` | 無 | 0 2 | 使用者層 `config.json` | `llm_world` 那塊地的 `.aos/`（沒有就 `aos init` 它）、`config.json` 的 `units` 範本 |
| `aos llm ask "<文字>"｜--file <檔>` | `--unit`、`--tier` | 0 2 4 75 | 使用者層 `config.json` | `$AOS_HOME/.aos/ask/<id>.prompt`、LLM 世界收件匣；結果落 `<id>.out` |
| `aos llm` | `--unit <名>`、`--tier <名>`、`--tools <檔>`、`--usage-out <檔>`、`--request-id <id>`；prompt 走 stdin、回話走 stdout | 0 2 75 130 | LLM 世界的 `.aos/units.json` | 帳簿 `ledger.jsonl`、`--usage-out` 指的用量 json |
| `aos doorman [<根>]` | `--watch`、`--once` | 0 2 | 資料夾樹、登記表 | 登記表 |
| `aos agent init [<地>]` | `--tier`、`--system <檔>` | 0 2 | 目前資料夾 | `main.aos.json`、`agent.json`、`.aos/` |
| `aos say <目標 agent 地> <文字>｜<目標 agent 地> --body <檔>` | 寄件人＝cwd 那塊地，不在地裡就是 `~` | 0 2 4 75 | cwd 版面、目標地版面 | 目標地 `.aos/inbox/`（一則 `mail`） |
| `aos listen [<agent 地>]` | `--json`、`--wait <ms>`；地省略＝`~` | 0 2 4 | 那塊地的 `.aos/mail/` | 不寫 |
| `aos talk [<agent 地>]` | `--interface <程式>` | 0 2 4 75 | `say` 與 `listen` 讀的 | `say` 寫的 |
| `aos state [<地>]` | `--json` | 0 2 4 | 接力棒、登記表、`agent.json` | 不寫 |

## 通則

- **S-12-01** 上面每一支必須是同一個 `aos` 執行檔的子命令；禁止裝第二支執行檔。〔主編補〕
- **S-12-02** 退出碼必須照這張表：`0` 正常、`2` 用法錯、`3` 解析或版本拒絕、`4` 不是一塊地、`5` 因失敗或預算停（只有 `run`）、`75` 暫時擋住（鎖被佔、收件匣背壓、後端失敗，可重試）、`130` 被取消。〔主編補〕
- **S-12-03** `--interface <程式>` 必須把這支子命令的 stdin 與 stdout 轉接給指定的程式；aos 禁止自己長一套終端機 UI。〔裁決 2026-08-30〕
- **S-12-04** `aos run` 必須有 `--steps N`（走幾步就停），`aos status` 必須看得到它在幹嘛；這兩樣是使用者親自給的。〔裁決 2026-08-30〕
- **S-12-05** 每支子命令必須有 `--help`，內容從這份 spec 派生。〔主編補〕

## 控制介面

同時跟好幾個慢 REPL 交流、每個跑十幾分鐘，「看得見、停得了、殺得掉」因此是必要的。

- **S-12-18** `aos status` 必須同時讀登記表與各地的接力棒；只讀登記表禁止。〔裁決 2026-09-01〕
- **S-12-19** `aos stop <地>` 必須往那塊地的 `.aos/control/` 投一則 `op: "stop"`，走的是同一套投遞協定。〔預設 2026-09-05，L-05〕
- **S-12-20** `aos stop --kill <地>` 必須直接對登記表上的 pid 送 SIGKILL，再把該筆改成 `stopped`；這是控制面唯一不走投遞協定的一條。〔預設 2026-09-05，L-05〕
- **S-12-21** `aos stop`（不帶 `--kill`）只保證停在格尾；`--every` 睡著的 run 建議等一個間隔再判斷。〔主編補〕
- **S-12-22** `aos mv <來源地> <目的地>` 必須是停時鐘＋搬＋重新登記三步，並且文件必須把它寫成唯一正確的搬法。〔裁決 2026-09-05〕
- **S-12-23** `aos daemon exec <地>` 必須往登記表投一筆一次性登記，當「去跑某資料夾一次」那一格。〔預設 2026-09-05，G-02〕
- **S-12-55** `aos daemon exec` 必須帶 `--id`，同 id 再投必須拒絕。〔主編補〕

## 停得了的上界
- **S-12-44** 控制收件匣必須至少在三個點被讀：每格開頭、每筆指令的逾時輪詢、等待中呼叫的每次輪詢。〔主編補〕
- **S-12-45** `aos stop`（不帶 `--kill`）的上界必須是一筆指令的 `timeout_ms`：最壞情況等當下那筆跑完。〔主編補〕
- **S-12-46** `aos stop --kill` 之後必須由 daemon 代寫一份 `reason: "killed"` 的狀態檔，並把那一格的 `.aos/ticks/<N>/` 原封留作現場。〔主編補〕
- **S-12-47** `aos fix <地>` 預設必須把現場丟棄：`.aos/ticks/<N>/` 改名成 `.aos/ticks/<N>.crashed/`、那條串標成 `stopped`。〔主編補〕
- **S-12-48** `aos fix --requeue` 必須把那一格已經取走的投遞物退回收件匣，然後才丟棄現場。〔主編補〕
- **S-12-61** `aos stop` 必須先查登記表與 `.aos/lock`；兩邊都沒人在跑就不投控制信，印「沒人在跑」並退出 0。〔主編補〕
- **S-12-62** 處理過的控制信必須搬到 `.aos/control/done/`，禁止就地刪掉。〔主編補〕
- **S-12-63** `aos stop --kill` 在登記表查不到 pid 時必須改讀 `.aos/lock` 裡的 pid。〔主編補〕

## 請求、原稿與收件匣
- **S-12-51** `aos status --request <id>` 必須讀 LLM 世界的 `.aos/requests/<id>.json`，印出那筆請求是 `queued`、`sent`、`done` 還是 `failed`。〔主編補〕
- **S-12-52** `aos status` 建議印出頂層原稿的 sha256 跟 `.aos/program/` 檔頭 `source_hash` 一不一樣；不一樣就印「原稿已變更、尚未生效」。〔主編補〕
- **S-12-53** 重載原稿的唯一途徑必須是停掉那塊地再重開；禁止跑中換原稿。〔主編補〕
- **S-12-54** `.aos/inbox/` 與 `.aos/control/` 的 id 去重表必須分開，兩個命名空間互相獨立；禁止實作成同一張表。〔主編補〕
- **S-12-64** `aos status` 至少必須印出：停止原因、收件匣待處理數、在等哪些落點。〔主編補〕
- **S-12-65** `aos status --triple <落點>` 必須印三態之一。〔主編補〕
- **S-12-66** `aos deliver` 拒收時建議指出是哪個欄位壞掉，禁止只叫人去讀 spec。〔主編補〕

## 伺服器型的地與一次性糖

- **S-12-56** `aos llm serve <地>` 必須是 LLM 世界專用的迴圈：預設 `--every 200 --until never`，跟 exec 搶同一把 `.aos/lock`，退出碼同 `aos run`；daemon 對 LLM 世界必須起它，禁止起 `aos run`。〔裁決 2026-09-05〕
- **S-12-57** `--until` 必須收 `idle` 與 `never` 兩個值；`never` 是閒著也不停、只等投遞或控制信。〔主編補〕
- **S-12-58** `aos daemon add <地>` 必須只把那塊地登記成 `pending`，禁止順手開跑；登記與起時鐘是兩個動作。〔主編補〕
- **S-12-59** `aos llm ask` 必須把文字落成 `$AOS_HOME/.aos/ask/<id>.prompt`、投給 LLM 世界，結果落在同目錄的 `<id>.out`。〔主編補〕
- **S-12-60** `aos publish <落點>` 必須照 [07](07-call-and-delivery.md) 的原子發布規矩寫結果檔（`--from`）或狀態檔（`--fail`）；它是給 shell 腳本與工具用的那一支。〔主編補〕

## 待使用者拍板

- S-12-01、02、05 一支執行檔、退出碼共同表、每支都要 `--help`。〔主編補〕
- S-12-19～21 `stop` 走投遞、`--kill` 走訊號、只保證停在格尾。〔預設 L-05／主編補〕
- S-12-23、55 `daemon exec` 是一次性登記、必須帶 `--id` 去重。〔預設 G-02／主編補〕
- S-12-44～45 控制收件匣三個讀取點，`stop` 的上界是一筆指令的逾時。〔主編補〕
- S-12-46～48 `--kill` 留現場、`fix` 丟棄、`--requeue` 退回收件匣。〔主編補〕
- S-12-51～54 `--request <id>` 查請求、原稿雜湊對照、停掉重開才生效、兩個收件匣去重表分開。〔主編補〕
- S-12-57、58 `--until` 收 `idle`／`never`；`aos daemon add` 只登記不開跑。〔主編補〕
- S-12-59～60 `llm ask` 與 `publish` 兩顆糖。〔主編補〕
- S-12-61～63 沒人在跑就不投信、控制信搬 `done/`、`--kill` 第二個 pid 來源。〔主編補〕
- S-12-64～66 `status` 至少印哪三樣、`--triple`、`deliver` 錯誤訊息指到欄位。〔主編補〕
- `deliver` 三選一的引數形狀，與 `75` 用在背壓與拒收。〔主編補〕

## 現況對照

今天只有 `init`／`run`／`deliver`／`agent` 那組／`llm`／`tool`／`contact`，其餘子命令都沒有，`daemon` 只有 `aos run --daemon` 這種單一資料夾一直跑的形式。退出碼沒有共同表，`--until` 沒有 `never`。控制面只有 `aos stop <資料夾>` 停一個，沒有登記表也沒有控制收件匣，`--kill` 之後沒有人代寫狀態檔、也沒有現場可以修。
