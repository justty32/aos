# proto8/extras/agent — aos-agent：統一的 agent 介面

← [extras](../README.md)｜規劃：[thinking 11-04 aos-agent](../../thinking/2026-11/04/aos-agent/README.md)（[01 子命令](../../thinking/2026-11/04/aos-agent/01-子命令.md)、[02 找 agent](../../thinking/2026-11/04/aos-agent/02-找-agent.md)、[03 介面](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)、[04 邊緣](../../thinking/2026-11/04/aos-agent/04-過渡與邊緣.md)）

使用者 11-03「aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent」、11-04 晚「幫我弄個aos-agent chat指令，ctrl-c退出」「aos-agent add --name bob ../agents/bob這樣」。**一支給人用的指令，每個子命令只管一隻 agent**；agent＝aos-daemon 管的一支 proc。底下只做兩件事：叫 `aos-daemon-ctl`（掛、拔、起、停、暫停、找 stack），與動那隻 stack 裡 P-42 的三樣（`queue/`、`history.jsonl`、ctl／state 窗）。eca（claude／codex）、aos 自己的 loop／fsm agent 都一樣，aos-agent 不看、不猜裡面是什麼。Python 單檔、純標準庫、只在 Linux（讀 `/proc`）。

| 檔 | 是什麼 |
|---|---|
| `bin/aos-agent` | 指令本體；開頭的說明寫了全部規則與錯誤代號 |
| `using-aos-agent.sh` | `source` 用：帶名字＝`export AOS_AGENT=名字`，定義 `say`／`listen`／`chat`／`status` 四個函數；`AOS_DAEMON` 沒設＝export 成 `$PWD/.stack`（11-05） |
| `stack.gitignore`、`stack.gitattributes` | 搬家範本（11-05）：image（`ws/.stack/`）進 git 時用；用法見下面「搬家」 |

**ctl：掛上與管理**（使用者 11-05「我希望掛上和管理這塊，能夠放到aos-agent ctl這個子命令下。」）

```
aos-agent [--daemon D] ctl add [--name N] [--ws WS] [--stack S] XXX     掛一隻；等上表、印 stack
aos-agent [--daemon D] ctl rm 名字                                        拔掉並刪它的 stack（名字要明講；stack 是工作區、定義、daemon 資料夾、目前資料夾、家目錄、表上別隻的 stack 或在它們上層的不刪，11-04 夜）
aos-agent [--daemon D] ctl ls [--json]                                    列 daemon 表上全部：名字 狀態 工作區 queue 幾封
aos-agent [--daemon D] ctl state|status|start|stop|sleep|wake|pause|resume [--target 名字]
aos-agent [--daemon D] ctl where [--stack|--ws] [--target 名字]            印 stack（預設）／工作區（--ws）
```

**跟它說話、畫面、設定**（在頂層）

```
aos-agent [--daemon D] say [--target 名字] [話...]                    stdout 印信件名稱
aos-agent [--daemon D] listen [--target 名字] [--timeout-s 秒] | [--last N] [--follow]
aos-agent [--daemon D] chat [--target 名字]                           一行一句；Ctrl-C 退出
aos-agent [--daemon D] open [-d]|close|watch [--target 名字]          畫面（宣告了 screen 的）
aos-agent [--daemon D] tools [--target 名字] [ls|get 名|add [--override] [--no-cache] 名 路徑|rm 名|reset]   定義疊這隻的覆蓋層（只存差異）
aos-agent [--daemon D] llm [--target 名字] [show|set 鍵=值...|reset]
```

- **對象**：`--target 名字` ＞ `$AOS_AGENT`；都沒有＝`TargetMissing`。名字查 daemon 表，沒有＝`InstanceMissing`。`ctl add`（名字＝`--name`，沒給＝資料夾名）、`ctl rm`（位置參數）、`ctl ls` 不吃 `AOS_AGENT`。不再比工作區、沒有用來指對象的 `--stack`。
- **ctl where**：不帶旗標＝`--stack`，印那隻的 stack 一行（`aos-daemon-ctl where --stack 名字` 轉述）；`--ws` 印它的工作區（表上那列的 `ws`；沒記＝`WsMissing`，那隻是沒給 `--ws` 直接用 aos-daemon-ctl 掛的）；兩個一起給＝`ArgumentsBad`（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。
- **哪個 daemon**：`--daemon D` ＞ `$AOS_DAEMON`（那個 daemon 的 `$AOS_STACK`，絕對路徑）＞ **cwd 的 `./.stack`**（11-05 [portable-flow 題 3](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)：daemon 在 ws 裡起，`cd ws` 就找得到，不用設變數；轉絕對、不往上找）；都沒有＝`DaemonMissing`。daemon 沒在跑：`ctl ls`／`state`／`where` 照表印＋注意；`ctl add`／`rm`／`start`／`stop`／`sleep`／`wake`＝`DaemonMissing`；`say` 照寄＋提醒。
- **表上的路徑**（11-05）：daemon 把每列的 `stack`／`ws`／`def` 存成相對 daemon stack（整份搬家照樣對得上），`aos-daemon-ctl ls --json` 拼回絕對再給這支；`ctl ls`／`state`／`where` 印的都是絕對。列上的 `reason`（出錯結束〔loop 型退非 0〕留成 `stopped` 的列，daemon 寫的原因；修好後 `llm reset`／`tools reset` 再 `ctl start`，不要了 `ctl rm`）`ctl ls` 印在行尾 `reason …`、`ctl state` 多一行 `reason`。
- **ctl sleep／wake**（11-05 [portable-flow 衝突 1](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)，使用者選「嚴格分」）：`sleep`＝現在就睡（daemon SIGTERM、列 `sleeping`、stack 留；daemon 開門自己醒，或 `wake`）；`stop`＝等這輪做完、要 `start` 才回來。`start` 只起 `stopped`、`wake` 只醒 `sleeping`；跨著用（sleeping 的 `start`／`stop`、stopped 的 `wake`／`sleep`）＝`aos-daemon-ctl` 的 `PhaseBad` 原樣轉（`X is sleeping; use wake …` 之類）；同一狀態再叫（stopped 的 stop、running 的 start、sleeping 的 sleep、running 的 wake）＝印 `already …`、退 0。sleep 不關畫面（跟 daemon 收工一樣）。
- **錯**：stderr 一行 `aos-agent: 代號 原因`、退 1；等 daemon 逾時＝`WaitFailed`；`ctl add` 的信被 daemon 拒收（名字像 `a/b`、`..`，或設定不合格；daemon 寫在 `procs_state.json` 的 `mailbox_warning`）＝立刻 `AddRejected`、原因原樣轉，不等滿 30 秒；判官不掛（回信 `applied: false`）＝立刻 `AddRejected`（`add`）／`CtlRejected`（其他 ctl），訊息帶判官的代號與原因（下一條）。子介面入口（screen）與 aos-tools、aos-json 自己報的錯原樣轉。
- **`AOS_KERNEL`**（11-05 [edge-agent](../../thinking/2026-11/05/edge-agent/README.md)）：有設＝ctl 的信先寄判官（[demo/docs/04](../../demo/docs/04-kernel-modes.md)）。對象就是那個 kernel 本身（模式 2 的 0 號，`AOS_KERNEL` 在它的 stack 裡）＝`start`／`stop`／`sleep`／`wake`／`rm` 直接寄 daemon（不然 kernel 睡著時給它自己的 `wake` 沒人收、永遠叫不醒）；寄出之後 kernel 不是 running＝立刻 `WaitFailed`（信排在它信箱裡、它回來才判）。
- **等回信**（11-05 [edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`ctl add`／`rm`／`start`／`stop`／`sleep`／`wake` 每封信都開一個暫時回信信箱（系統暫存資料夾〔`$TMPDIR`，沒設＝`/tmp`〕底下 `aos-agent-reply-XXXX`）、經 `aos-daemon-ctl --reply-to` 寄。判官不掛＝回信 `applied: false` 一到就退：`aos-agent: AddRejected AOS_KERNEL refused the add letter: NameUnknown evil not in allowed`（滿額是 `SlotMissing`；wake／start 超過 `max_running` 是 `CtlRejected`）。放行或沒設 `AOS_KERNEL`＝daemon 回 `applied: true`，照舊等表上變成結果（表先變、回信還沒到＝最多再等 1 秒讓它落地）。暫時信箱用完一律刪（成功、錯、逾時、Ctrl-C）。判官也沒回信（卡住、寫不進暫時信箱）＝照舊等滿 30 秒 `WaitFailed`，訊息說去哪看判官的 stderr。

## 介面 `aos-agent`：ctl add 只看宣告

一個資料夾能被 `ctl add`，只看它頂層 `interfaces.json` 有沒有 `aos-agent` 這個 key（沒有＝`InterfaceMissing`、不送信；讀不懂＝`InterfaceBad`）；不驗 `cli.json`、`fsm.json`（宣告了卻沒做到，第一圈就出錯結束、表上留 `stopped`＋原因）。介面六條（資料夾程式、只吃 aos 的環境變數、常駐有窗、`queue/` 收 user message、`history.jsonl` 寫回答、錯在 stderr 一行）與選配子介面見 [03](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)：

```json
{"aos-agent": {"entry": "body.json", "screen": "screen", "tools": "tools.json", "llm": "llm.json"}}
```

- `entry`（選填，11-05 [portable-flow 題 4](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)）＝定義裡**身體的入口**（相對路徑，可帶 `#/指標`；不在或寫成絕對／`..`＝`InterfaceBad`）。宣告了＝`ctl add` 掛的是 `<定義>/<entry>`（`aos-daemon-ctl add --def <定義> <定義>/<entry>`，表上的 `def` 照樣是定義資料夾）；沒宣告＝掛定義資料夾本身（照它的 `_entry` 判型，11-04 起的行為）。用處：定義的 `_entry` 空出來寫成「**把自己掛上 daemon**」，`aos-exec 那個資料夾`＝`aos-agent ctl add 那個資料夾`（使用者「介面維持 aos-agent add」、不加 `aos-exec --daemon`；11-05 add 收進 `ctl`）。範例在 [demo/agent-fsm](../../demo/docs/02-agent-fsm.md)：
  `_entry`＝`{"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}`、`body.json`＝`["aos-loop", "loop.json"]`。aos-exec 跑 `_entry` 時已經 cd 進定義資料夾，所以單子用 `cwd` 換回工作區（`AOS_WS`＝`--ws` ＞ 外面的 `$AOS_WS` ＞ 呼叫當下的 cwd，轉絕對）：`--ws` 預設 `.`＝那個工作區、`./.stack` 找 daemon 也從那裡找；`AOS_CD`＝定義資料夾的絕對路徑；名字＝資料夾名。不走 `sh -c`。`cd ws && aos-exec ../agents/bob` 就把 bob 掛上 `ws/.stack` 的 daemon（WSL 實測）；要換名字、換 ws 以外的設定就直接打 `aos-agent ctl add …`（`aos-exec 資料夾 參數` 的參數會接在 argv 尾巴、ctl add 不收）。

- `screen`＝定義裡一個資料夾程式，它自己的 `interfaces.json` 宣告 `{"aos-agent/screen": {}}`（沒宣告＝`ScreenBad`）。aos-agent 從 daemon 表那一列的 `def` 欄找回定義（aos-daemon-ctl add 送、daemon 記；使用者 11-04「那就b。」；沒這欄＝`InterfaceMissing`，`ctl rm` 再 `ctl add` 一次），叫 `aos-exec --ws <ws> --stack <stack> <定義>/<入口> 動作…`。沒宣告＝`ScreenMissing`（看回答改用 `listen --follow`）。
- `tools`＝登記檔。`aos-agent tools` 改的是**這一隻的覆蓋層** `<stack>/tools.json`（11-05 起只存差異 `{"add": {名: 登記}, "rm": [名]}`、不再整份複製定義；身體每次讀「定義疊覆蓋層」、定義改了照疊；`reset` 刪覆蓋層）——存什麼、怎麼合併、定義改了怎麼辦見 **[docs/03 tools 覆蓋層](docs/03-tools覆蓋層.md#tools-覆蓋層)**。改定義用 `aos-tools --file <定義>/tools.json …`。同一份定義掛了好幾隻時，改這隻的會在 stderr 提醒一行 `note: this definition (…) is also used by X; …`。
- `llm`＝定義裡那份**腦設定檔**的相對路徑（跟 `tools` 同一種寫法；11-04 晚 [think-as-function 03 § 4](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)：`aos-llm` 是寄請求給 llm kernel 的基礎工具，aos-agent 的 `llm` 只是 aos-json 的語法糖）。這隻改過的鍵＝stack 裡同一個相對路徑（例 `<stack>/llm.json`），**只放改過的鍵**、其他照定義：`show`＝定義那份（沒有＝`{}`）疊改過的、一行一個 `鍵=值`，stderr 一行列哪些鍵是改過的；`set 鍵=值…`＝`aos-json set --str <stack 那份>#/鍵 值`（不在先建 `{}`；值一律字串）；`reset`＝刪掉。鍵由那隻身體認（agent-fsm：`endpoint`＝kernel 的代號、`model`；eca：`model`），aos-agent 不認也不擋；身體每題重讀、有的鍵蓋過定義。改定義＝人直接 `aos-json set --str <定義>/llm.json#/endpoint sol`。沒宣告＝`LlmMissing`；宣告的是資料夾或讀不懂＝`LlmBad`。

## 用法例子

11-04 在 WSL 逐條跑過的一整串（ctl add 兩隻、ctl ls、say／listen、ctl state、chat、tools、open、ctl stop／start、ctl rm；11-05 改成 ctl 寫法；tools 那段 11-05 改成覆蓋層的輸出）在 [docs/01-用法例子](docs/01-用法例子.md)。

## agent 對話協議（P-42；併自 extras/human）

- **說**：`aos-agent say 話`＝`aos-post send --ordered <stack>/queue`，一封信的 body＝`{"role": "user", "content": 話}`（N-16 有順序的信箱；queue 還沒有就先建，可以先說、再跑）。印的信件名稱就是 `new/` 裡那封的名字（`<12 位序號>.<尾名>`）。沒人在跑時照表上的 phase 提醒：`stopped`＝`aos-agent ctl start --target 名字`（有 `reason` 一起印）；`sleeping`＝daemon 在跑就 `aos-agent ctl wake --target 名字`、沒在跑就重開 daemon 它會自己醒。
- **聽**：`aos-agent say 話 && aos-agent listen`——等**最新那封**＝queue 的 `new/`、`cur/` 裡照處理順序排最後的（`aos_ws.letter_key`）：還在就等；不見了就印 history 最新那則沒有 `tool_calls` 的 assistant（先 say 後 listen 不會漏）。交出去還在答（eca 交給 CLI 就收信、fsm 答的途中）照等；都空、history 也沒回答＝`QuestionUnknown`；信不見了、沒回答、也沒人在跑＝`AnswerMissing`；沒人在跑＝提醒一次、繼續等。`--timeout-s` 秒數到了＝`AnswerMissing`。暫停中＝提醒一次「要 resume」照等；答到一半被 stop／sleep、或出錯結束（表上 stopped／sleeping；出錯的帶原因）＝提醒一次（附 `ctl start`／`ctl wake` 怎麼叫回）照等；等到一半那隻下了表（退 0）＝`AnswerMissing` 說它最後的輸出在哪、同名 `ctl add` 接著用；被 `ctl rm`（stack 刪了）＝`InstanceMissing`（11-05 edge-agent）。`--last N` 印最後 N 段就走、`--follow` 接著跟著看。
- **chat**：say＋listen 的迴圈；提示符 `> ` 在 stderr、stdout 只有回答（`chat < 問題.txt > 答案.txt` 也行）；不印信件名稱。等答案時 Ctrl-C＝退 130，那封已寄出、agent 照答，之後用 `listen` 看；stdin 結束退 0；途中 `AnswerMissing` 印一行、不退出；每句寄之前重查表，聊到一半被 `ctl rm`＝`InstanceMissing` 退 1（原本照寄、把刪掉的 stack 建回來，11-05 edge-agent）。
- **看**：`aos-agent ctl state`（狀態、工作區、定義、stack、queue 幾封、最新回答前 60 字、`mailbox_warning.txt` 那一行）。
- **停**（都在 `ctl` 下）：`pause`／`resume`＝`aos-daemon-ctl pause／resume`（寫它的 ctl.json；停在哪是身體的事：eca 一批信、fsm 一格）；`stop`／`start`＝表上留成 `stopped`、stack 留著、信照收不答；`sleep`／`wake`＝現在就睡、表上留成 `sleeping`、daemon 開門自己醒（搬家前用）。
- 直接 `aos-exec --ws W <agent>` 跑、沒掛 daemon 的，aos-agent 不管：`aos-post send --ordered W/.stack/queue` 寫信、看 `W/.stack/history.jsonl`。

## 搬家

整份 `ws/`（連 `.stack`）和定義保持相對位置 `cp -r` 或 git 來回，到新位置 `aos-exec ../daemon` 就接著跑（11-05）。要點：**先 Ctrl-C 讓 daemon 睡著再存**；`pid`、`boot_id` 那幾欄是上一台的、別信；eca 的 claude session 綁那台的 `~/.claude`；git 掉的空資料夾第一圈自己建回；只在 Linux 檔案系統 checkout、別在 Windows checkout 上跑；範本 `cp stack.gitignore ws/.stack/.gitignore`、`cp stack.gitattributes <repo 根>/.gitattributes`。全文與 11-05 實測在 [docs/04-搬家](docs/04-搬家.md#搬家)。

## 已知限制

併自 extras/eca 的那段，在 [docs/02-已知限制](docs/02-已知限制.md)；tools 覆蓋層的邊在 [docs/03](docs/03-tools覆蓋層.md#已知的邊)。
