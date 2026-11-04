# proto8/extras/agent — aos-agent：統一的 agent 介面

← [extras](../README.md)｜規劃：[thinking 11-04 aos-agent](../../thinking/2026-11/04/aos-agent/README.md)（[01 子命令](../../thinking/2026-11/04/aos-agent/01-子命令.md)、[02 找 agent](../../thinking/2026-11/04/aos-agent/02-找-agent.md)、[03 介面](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)、[04 邊緣](../../thinking/2026-11/04/aos-agent/04-過渡與邊緣.md)）

使用者 11-03「aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent」、11-04 晚「幫我弄個aos-agent chat指令，ctrl-c退出」「aos-agent add --name bob ../agents/bob這樣」。**一支給人用的指令，每個子命令只管一隻 agent**；agent＝aos-daemon 管的一支 proc。底下只做兩件事：叫 `aos-daemon-ctl`（掛、拔、起、停、暫停、找 stack），與動那隻 stack 裡 P-42 的三樣（`queue/`、`history.jsonl`、ctl／state 窗）。eca（claude／codex）、aos 自己的 loop／fsm agent 都一樣，aos-agent 不看、不猜裡面是什麼。Python 單檔、純標準庫、只在 Linux（讀 `/proc`）。

| 檔 | 是什麼 |
|---|---|
| `bin/aos-agent` | 指令本體；開頭的說明寫了全部規則與錯誤代號 |
| `using-aos-agent.sh` | `source` 用：帶名字＝`export AOS_AGENT=名字`，定義 `say`／`listen`／`chat`／`status` 四個函數 |

```
aos-agent [--daemon D] add [--name N] [--ws WS] [--stack S] XXX     掛一隻；等上表、印 stack
aos-agent [--daemon D] rm 名字                                        拔掉並刪它的 stack（名字要明講；stack 是工作區、定義、daemon 資料夾、目前資料夾、家目錄或在它們上層的不刪，11-04 夜）
aos-agent [--daemon D] ls [--json]                                    列 daemon 表上全部：名字 狀態 工作區 queue 幾封
aos-agent [--daemon D] state|status|start|stop|pause|resume [--target 名字]
aos-agent [--daemon D] where [--stack|--ws] [--target 名字]            印 stack（預設）／工作區（--ws）
aos-agent [--daemon D] say [--target 名字] [話...]                    stdout 印信件名稱
aos-agent [--daemon D] listen [--target 名字] [--timeout-s 秒] | [--last N] [--follow]
aos-agent [--daemon D] chat [--target 名字]                           一行一句；Ctrl-C 退出
aos-agent [--daemon D] open [-d]|close|watch [--target 名字]          畫面（宣告了 screen 的）
aos-agent [--daemon D] tools [--target 名字] [ls|get 名|add 名 路徑|rm 名|reset]
aos-agent [--daemon D] llm [--target 名字] [show|set 鍵=值...|reset]
```

- **對象**：`--target 名字` ＞ `$AOS_AGENT`；都沒有＝`TargetMissing`。名字查 daemon 表，沒有＝`InstanceMissing`。`add`（名字＝`--name`，沒給＝資料夾名）、`rm`（位置參數）、`ls` 不吃 `AOS_AGENT`。不再比工作區、沒有用來指對象的 `--stack`。
- **where**：不帶旗標＝`--stack`，印那隻的 stack 一行（`aos-daemon-ctl where --stack 名字` 轉述）；`--ws` 印它的工作區（表上那列的 `ws`；沒記＝`WsMissing`，那隻是沒給 `--ws` 直接用 aos-daemon-ctl 掛的）；兩個一起給＝`ArgumentsBad`（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。
- **哪個 daemon**：`--daemon D` ＞ `$AOS_DAEMON`（那個 daemon 的 `$AOS_STACK`，絕對路徑）；都沒有＝`DaemonMissing`（只設舊名 `AOS_DAEMON_STACK` 也是，訊息提示新名）。daemon 沒在跑：`ls`／`state`／`where` 照表印＋注意；`add`／`rm`／`start`／`stop`＝`DaemonMissing`；`say` 照寄＋提醒。
- **錯**：stderr 一行 `aos-agent: 代號 原因`、退 1；等 daemon 逾時＝`WaitFailed`。子介面入口（screen）與 aos-tools、aos-json 自己報的錯原樣轉。

## 介面 `aos-agent`：add 只看宣告

一個資料夾能被 `add`，只看它頂層 `interfaces.json` 有沒有 `aos-agent` 這個 key（沒有＝`InterfaceMissing`、不送信；讀不懂＝`InterfaceBad`）；不驗 `cli.json`、`fsm.json`（宣告了卻沒做到，第一圈就下表）。介面六條（資料夾程式、只吃 aos 的環境變數、常駐有窗、`queue/` 收 user message、`history.jsonl` 寫回答、錯在 stderr 一行）與選配子介面見 [03](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)：

```json
{"aos-agent": {"screen": "screen", "tools": "tools.json", "llm": "llm.json"}}
```

- `screen`＝定義裡一個資料夾程式，它自己的 `interfaces.json` 宣告 `{"aos-agent/screen": {}}`（沒宣告＝`ScreenBad`）。aos-agent 從 daemon 表那一列的 `def` 欄找回定義（aos-daemon-ctl add 送、daemon 記；使用者 11-04「那就b。」；沒這欄＝舊 daemon 掛的，`InterfaceMissing`，`rm` 再 `add` 一次），叫 `aos-exec --ws <ws> --stack <stack> <定義>/<入口> 動作…`。沒宣告＝`ScreenMissing`（看回答改用 `listen --follow`）。
- `tools`＝登記檔。`aos-agent tools` 改的是**這一隻 stack 裡的副本** `<stack>/tools.json`：第一次 `add`／`rm` 才從定義複製（`path` 一律改成絕對）、之後**不跟定義變**（使用者 11-04「不跟。風險自行處理。但我們可以給reset。」）、`reset` 刪副本回去用定義的；改定義用 `aos-tools --file <定義>/tools.json …`。同一份定義掛了好幾隻時，改副本會在 stderr 提醒「X 也用這份定義」。
- `llm`＝定義裡那份**腦設定檔**的相對路徑（跟 `tools` 同一種寫法；11-04 晚 [think-as-function 03 § 4](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)：`aos-llm` 是寄請求給 llm kernel 的基礎工具，aos-agent 的 `llm` 只是 aos-json 的語法糖）。副本＝stack 裡同一個相對路徑（例 `<stack>/llm.json`），**只放改過的鍵**、不跟定義：`show`＝定義那份（沒有＝`{}`）疊副本、一行一個 `鍵=值`，stderr 一行列哪些鍵來自副本；`set 鍵=值…`＝`aos-json set --str <副本>#/鍵 值`（副本不在先建 `{}`；值一律字串）；`reset`＝刪副本。鍵由那隻身體認（agent-fsm：`endpoint`＝kernel 的代號、`model`；eca：`model`），aos-agent 不認也不擋；身體每題重讀副本、有的鍵蓋過定義。改定義＝人直接 `aos-json set --str <定義>/llm.json#/endpoint sol`。沒宣告＝`LlmMissing`；宣告的是資料夾（舊的 `"llm": "llm"`）或讀不懂＝`LlmBad`。

## 用法例子

11-04 在 WSL 逐條跑過的一整串（add 兩隻、ls、say／listen、state、chat、tools 副本、open、stop／start、rm）在 [docs/01-用法例子](docs/01-用法例子.md)。

## agent 對話協議（P-42；併自 extras/human）

- **說**：`aos-agent say 話`＝`aos-post send --ordered <stack>/queue`，一封信的 body＝`{"role": "user", "content": 話}`（N-16 有順序的信箱；queue 還沒有就先建，可以先說、再跑）。印的信件名稱就是 `new/` 裡那封的名字（`<12 位序號>.<尾名>`）。沒人在跑時照表上的 phase 提醒：`stopped`＝`aos-agent start --target 名字`；`sleeping`＝重開 daemon 它會自己醒。
- **聽**：`aos-agent say 話 && aos-agent listen`——等**最新那封**＝queue 的 `new/`、`cur/` 裡照處理順序排最後的（`aos_ws.letter_key`）：還在就等；不見了就印 history 最新那則沒有 `tool_calls` 的 assistant（先 say 後 listen 不會漏）。交出去還在答（eca 交給 CLI 就收信、fsm 答的途中）照等；都空、history 也沒回答＝`QuestionUnknown`；信不見了、沒回答、也沒人在跑＝`AnswerMissing`；沒人在跑＝提醒一次、繼續等。`--timeout-s` 秒數到了＝`AnswerMissing`。`--last N` 印最後 N 段就走、`--follow` 接著跟著看。
- **chat**：say＋listen 的迴圈；提示符 `> ` 在 stderr、stdout 只有回答（`chat < 問題.txt > 答案.txt` 也行）；不印信件名稱。等答案時 Ctrl-C＝退 130，那封已寄出、agent 照答，之後用 `listen` 看；stdin 結束退 0；途中 `AnswerMissing` 印一行、不退出。
- **看**：`aos-agent state`（狀態、工作區、定義、stack、queue 幾封、最新回答前 60 字、`mailbox_warning.txt` 那一行）。
- **停**：`pause`／`resume`＝`aos-daemon-ctl pause／resume`（寫它的 ctl.json；停在哪是身體的事：eca 一批信、fsm 一格）；`stop`／`start`＝表上留成 `stopped`、stack 留著、信照收不答。
- 直接 `aos-exec --ws W <agent>` 跑、沒掛 daemon 的，aos-agent 不管：`aos-post send --ordered W/.stack/queue` 寫信、看 `W/.stack/history.jsonl`。

## 已知限制

併自 extras/eca 的那段、加副本不跟定義，在 [docs/02-已知限制](docs/02-已知限制.md)。
