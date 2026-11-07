# proto8/cmd/aos-agent — aos-agent：統一的 agent 介面

← [cmd](../README.md)｜規劃：[thinking 11-04 aos-agent](../../thinking/2026-11/04/aos-agent/README.md)（[01 子命令](../../thinking/2026-11/04/aos-agent/01-子命令.md)、[02 找 agent](../../thinking/2026-11/04/aos-agent/02-找-agent.md)、[03 介面](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)、[04 邊緣](../../thinking/2026-11/04/aos-agent/04-過渡與邊緣.md)）

使用者 11-03「aos_ws,aos-say/listen,aos-ai這些之後都會整合進aos-agent」、11-04 晚「幫我弄個aos-agent chat指令，ctrl-c退出」「aos-agent add --name bob ../agents/bob這樣」。**一支給人用的指令，每個子命令只管一隻 agent**；agent＝aos-daemon 管的一支 proc。底下只做兩件事：經 daemon（掛、拔、起、停、暫停、找 stack；import aos-daemon-ctl 的本體 [`py/daemon_ctl/`](../../py/README.md)，不另叫行程），與動那隻 stack 裡 P-42 的三樣（`queue/`、`history.jsonl`、ctl／state 窗）。eca（claude／codex）、aos 自己的 loop／fsm agent 都一樣，aos-agent 不看、不猜裡面是什麼。Python 入口與套件、純標準庫。**不碰 pid、不讀 `/proc`**（11-06 [no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）：誰在跑看 daemon 表上那列的 `phase`，daemon 有沒有在聽看寄信有沒有回。

**說明在哪**（11-06 [human-cli](../../thinking/2026-11/06/human-cli/README.md) H6）：`aos-agent --help` 是一屏總覽；每個子命令、每個動作各一屏英文 help——`aos-agent ctl --help`、`aos-agent ctl rm --help`、`aos-agent tools ls --help`……（`-h` 同義）。**長規則**（對象與 daemon 怎麼找、sleep／wake、`AOS_KERNEL`、等回信、介面、錯誤行、代號全表、PATH 上要有誰）不在任何 `--help` 裡，在本檔與下列 docs。

| 檔 | 是什麼 |
|---|---|
| `bin/aos-agent` | 指令入口（薄殼，交給 `aos_agent/`） |
| `aos_agent/` | 本體套件：一個子命令一個模組（`ctl/` 子資料夾放 ctl 的動作），模組頂端的 `HELP` 就是它那一屏 `--help` |
| `using-aos-agent.sh` | `source` 用：帶名字＝`export AOS_AGENT=名字`，定義 `say`／`listen`／`chat`／`status` 四個函數；`AOS_DAEMON` 沒設＝export 成 `$PWD/.stack`（11-05） |
| `stack.gitignore`、`stack.gitattributes` | 搬家範本（11-05）：image（`ws/.stack/`）進 git 時用；用法見下面「搬家」 |

**ctl：掛上與管理**（使用者 11-05「我希望掛上和管理這塊，能夠放到aos-agent ctl這個子命令下。」）

```
aos-agent [--daemon D] ctl add [--name N] [--ws WS] [--stack S] [--limits JSON] [--envs K=V ...] [--timeout-s 秒] [--on-queued fail|ok] XXX     掛一隻；等上表、印 stack
aos-agent [--daemon D] ctl rm [--yes] [--timeout-s 秒] 名字                                拔掉並刪它的 stack（名字要明講；先關畫面，正在答＝SessionBad、什麼都不動；stack 是工作區、定義、daemon 資料夾、目前資料夾、家目錄、表上別隻的 stack 或在它們上層的不刪，11-04 夜；終端裡先問 [y/N]）
aos-agent [--daemon D] ctl ls [--json]                                    列 daemon 表上全部：名字 狀態 工作區 queue 幾封
aos-agent [--daemon D] ctl start|stop|sleep|wake [名字|--target 名字] [--timeout-s 秒]   add／start／wake 另收 --on-queued fail|ok
aos-agent [--daemon D] ctl state|status|pause|resume [--target 名字]
aos-agent [--daemon D] ctl where [--stack|--ws] [--target 名字]            印 stack（預設）／工作區（--ws）
aos-agent [--daemon D] ctl who [--stack S] [--json]                        S（預設 $AOS_STACK）是表上哪一隻的 stack（或在它底下）＝印那隻的名字
```

**跟它說話、畫面、設定**（在頂層）

```
aos-agent [--daemon D] say [--target 名字] [話...|-]                  stdout 印信件名稱；沒給話或 -＝讀 stdin
aos-agent [--daemon D] listen [--target 名字] [--timeout-s 秒 | --timeout-ticks N] | [--last N] [--follow]   stdout 只有回答
aos-agent [--daemon D] chat [--target 名字]                           一行一句；Ctrl-C 退出
aos-agent [--daemon D] open [--detach]|close|watch [--target 名字]    畫面（宣告了 screen 的；入口照收 動作 [--detach]）
aos-agent [--daemon D] tools [--target 名字] [ls [--json]|get 名|add [--override] [--no-cache] 名 路徑|rm 名|reset [--yes]]   定義疊這隻的覆蓋層（只存差異）
aos-agent [--daemon D] llm [--target 名字] [show|set 鍵=值...|reset [--yes]]
```

- **短名與確認**（11-06 human-cli H4、H11，使用者裁「開幾個常用短名」「終端問、非終端不問」「幫我加上--yes跳過」）：長旗標照樣能用；短名是全 aos 共用一張表裡的，同名同義——這支用到 `-h`（`--help`，全部）、`-d`（`--daemon`）、`-t`（`--target`）、`-j`（`--json`：`ctl ls`、`ctl who`、`tools ls`）、`-n -w -s`（`--name --ws --stack`：只在 `ctl add`）、`-f`（`listen --follow`）、`-y`（`--yes`：`ctl rm`、`tools reset`、`llm reset`）。一個槓一個名字，不黏值、不併：`-tann`、`-jf` 都是 `FlagUnknown`。刪了別處沒副本的三個子命令（`ctl rm`、`tools reset`、`llm reset`）**stdin 是終端**時先在 stderr 問一句 `[y/N]`，只有 `y`／`yes` 才做；其他字、空行、Ctrl-D＝印 `aos-agent: warning: nothing done`、退 0（問的時候按 Ctrl-C＝退 130）；`-y` 不問；stdin 不是終端（管線、腳本、agent、`</dev/null`）不問、照做。`tools reset`／`llm reset` 沒東西可刪就不問。例子在 [docs/01](docs/01-用法例子.md#短名與確認11-06)。

- **對象**：`--target 名字` ＞ `$AOS_AGENT`；都沒有＝`TargetMissing`。名字查 daemon 表，沒有＝`InstanceMissing`。`ctl add`（名字＝`--name`，沒給＝資料夾名）、`ctl rm`（位置參數）、`ctl ls` 不吃 `AOS_AGENT`。不再比工作區、沒有用來指對象的 `--stack`。
- **ctl add 的工作區**：`--ws WS` ＞ 非空的 `$AOS_WS` ＞ 呼叫當下的 cwd，轉絕對路徑；選到的路徑不是資料夾＝`WsMissing`、不送信，不退回 cwd（同 aos-exec）。
- **ctl where**：不帶旗標＝`--stack`，印那隻的 stack 一行（同 `aos-daemon-ctl where --stack 名字`）；`--ws` 印它的工作區（表上那列的 `ws`；沒記＝`WsMissing`，那隻是沒給 `--ws` 直接用 aos-daemon-ctl 掛的）；兩個一起給＝`ArgumentsBad`（使用者 11-04 晚「aos agent的where，我希望默認是--stack，有需要再另外指定--ws。」）。
- **ctl who**（11-05 [feat-proto 件 1](../../thinking/2026-11/05/feat-proto/01-self-tools.md) 代定 1，使用者「讓agent給自己改tool」）：拿 `S`（`--stack S` ＞ `$AOS_STACK`；都沒有＝`StackMissing`）在 daemon 表（`aos-daemon-ctl ls --json`）裡找 `stack` 是 S 本身或 S 上層的那列，印名字；好幾列都包住 S＝取最深的；`--json` 印 `{"name", "stack", "ws", "def"}`。沒找到＝`InstanceMissing`；沒 daemon＝`DaemonMissing`。給工具用：工具的小格是 `<agent stack>/tools/<名>/`（P-17），工具裡 `aos-agent ctl who` 就認出「叫我的是哪隻」——只查表、不從路徑往上爬（C-52「經機制看上層」）；工具繼承 daemon 給的 `AOS_DAEMON`。沒掛 daemon 直接 `aos-exec body.json` 跑的不支援（沒有表）。用它的工具：[lib/agent/self_tools](../../lib/docs/03-索引-agent等.md#索引agent)。
- **份額 `limits`**（11-05 [feat-proto 件 5](../../thinking/2026-11/05/feat-proto/05-資源份額.md) 代定 5，使用者「會想要限制特定aos proc所占用的資源」）：定義的宣告可寫 `"limits": {"mem_mb": 512, "cpu_s": 600}`（這隻建議的份額；key 同 aos-sandbox：`mem_mb`、`cpu_s`、`procs`、`file_mb`、`files` 是正整數，`user` 是帳號名字串），`ctl add --limits JSON` 整份蓋過宣告（`'{}'`＝不限）。key 不認、值不對＝`InterfaceBad`（宣告）／`ArgumentsBad`（`--limits`），不送信。真正擋的是 daemon（子行程裡 `setrlimit`／換帳號，等同 s6-softlimit；proc 自己不知道）：**已生效**（11-05 晚）——有宣告或 `--limits` 就原樣轉成 `aos-daemon-ctl add --limits JSON`（`'{}'` 也送＝蓋過 daemon.json 頂層的預設、不限）；比 daemon 自己的 hard 寬、`user` 但 daemon 不是 root＝那隻起不來（`ctl state` 的 `reason` 帶 `LimitBad …`）。`ctl state`：表上那列有 `limits`（daemon 寫的生效那份）就在 `def` 後多一行 `limits  mem_mb=512 cpu_s=600`，沒有不印。規則見 [aos-daemon docs/09](../../impls/aos-daemon/docs/09-份額.md)。
- **啟動環境**（11-06 K-6）：`ctl add --envs K=V` 可重複，透過啟動單子的 `envs` 在起這隻 agent 時帶入環境變數；沒給就不另加。`thought` 用它帶 `AOS_THOUGHT_DEPTH`，不另寫子 stack。
- **ctl state 的 tools 那行**（11-05 feat-proto 件 1）：這隻有覆蓋層時多一行 `tools   overlay: N added, M removed (+名, -名…)`——同一份定義跑久了被這隻自己改過多少，一眼看得到（C-46 定義不變、stack 漂移）；沒覆蓋層不印。
- **哪個 daemon**：`--daemon D` ＞ `$AOS_DAEMON`（那個 daemon 的 `$AOS_STACK`，絕對路徑）＞ **cwd 的 `./.stack`**（11-05 [portable-flow 題 3](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)：daemon 在 ws 裡起，`cd ws` 就找得到，不用設變數；轉絕對、不往上找）；都沒有＝`DaemonMissing`。D 一律轉真實路徑（realpath）。D 已存在但沒有 `procs_state.json`＝立刻 `StateMissing`。不預判 daemon 活不活：`ctl ls`／`state`／`where` 照表印；`ctl add`／`rm`／`start`／`stop`／`sleep`／`wake` 照寄、等回信，`--timeout-s S`（預設 30 秒）內一封都沒有＝`DaemonFailed`（下面「等回信」）；`say` 照寄。
- **表上的路徑**（11-05）：daemon 把每列的 `stack`／`ws`／`def` 存成相對 daemon stack（整份搬家照樣對得上），`aos-daemon-ctl ls --json` 拼回絕對再給這支；`ctl ls`／`state`／`where` 印的都是絕對。列上的 `reason`（出錯結束〔任意 proc 退非 0〕留成 `stopped` 的列，daemon 寫的原因；修好後 `llm reset`／`tools reset` 再 `ctl start`，不要了 `ctl rm`）`ctl ls` 印在最後一欄、`ctl state` 多一行 `reason`。
- **ctl sleep／wake**（11-05 [portable-flow 衝突 1](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)，使用者選「嚴格分」）：`sleep`＝現在就睡（daemon SIGTERM、列 `sleeping`、stack 留；daemon 開門自己醒，或 `wake`）；`stop`＝等這輪做完、要 `start` 才回來。`start` 只起 `stopped`、`wake` 只醒 `sleeping`；跨著用（sleeping 的 `start`／`stop`、stopped 的 `wake`／`sleep`）＝`aos-daemon-ctl` 的 `PhaseBad` 原樣轉（`X is sleeping; use wake …` 之類）；同一狀態再叫（stopped 的 stop、running 的 start、sleeping 的 sleep、running 的 wake）＝印 `already …`、退 0。sleep 不關畫面（跟 daemon 收工一樣）；`stop`、`ctl rm` 先關畫面（正在答＝`SessionBad`、不往下做）。
- **三扇門**（11-05 [stdio-unify](../../thinking/2026-11/05/stdio-unify/README.md) R1、R3、R15）：stdout 只放結果；提醒是 stderr 一行 `aos-agent: warning: 句子`（原本是括號一行）；`chat` 的提示符 `> ` 照舊在 stderr（D5）。`ctl ls` 一行 `名字 TAB 狀態 TAB 工作區 TAB queue 幾封 TAB reason`（沒有＝`-`）。`--help`／`-h`＝**那一層**的英文 help 到 stdout、退 0（頂層一屏總覽、`ctl --help` 列動作、`ctl rm --help` 只講 rm；`tools ls --help` 這種不用先有 target；11-06 起不再每層都印同一份長說明）；不給子命令＝`ArgumentsBad` 退 1（原本印說明退 0）；子命令前不認得的旗標＝`FlagUnknown`、子命令不認得＝`CommandUnknown`。錯誤行括號裡只指**那個子命令**（11-06 H10）：缺參數、參數不對＝`(usage: 那個子命令的 usage 行)`；子命令後不認得的旗標＝`(see aos-agent ctl rm --help)` 這樣指回它自己那份；子命令前的 `FlagUnknown` 指回頂層 `(see aos-agent --help)`。Ctrl-C 退 130（`listen --follow` 用 Ctrl-C 離開是正常離開、退 0）。
- **daemon_ctl 模組的錯**：`ctl` 系列 import `daemon_ctl`（不叫 aos-daemon-ctl 行程、不讀誰的 stderr），模組報的錯換成這支的名字與代號再印（`ProcMissing`→`InstanceMissing`，其他代號照用）。
- **錯**：stderr 一行 `aos-agent: error: 代號 原因`、退 1；`--timeout-s S`（預設 30 秒）內一封回信都沒有＝`DaemonFailed`；回了 `applied: true` 但表上等滿 S 秒還沒變成結果＝`WaitFailed`；`ctl add` 的信被 daemon 拒收（名字像 `a/b`、`..`，或設定不合格；daemon 寫在 `procs_state.json` 的 `mailbox_warning`）＝立刻 `AddRejected`、原因原樣轉，不等滿 S 秒；判官不掛（回信 `applied: false`）＝立刻 `AddRejected`（`add`）／`CtlRejected`（其他 ctl），訊息帶判官的代號與原因（下一條）。子介面入口（screen）與 aos-tools、aos-json 自己報的錯原樣轉。
- **錯誤代號一覽**：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`CommandMissing`（叫不到要的指令，例 `aos-exec`／`aos-json` 不在 PATH）、`DaemonMissing`、`DaemonFailed`、`StateMissing`、`InstanceMissing`、`InstanceExists`、`PathMissing`、`SessionBad`、`SendFailed`、`PostFailed`、`QuestionUnknown`、`AnswerMissing`、`WaitFailed`、`AddRejected`、`CtlRejected`、`TargetMissing`、`WsMissing`、`StackMissing`、`InterfaceMissing`、`InterfaceBad`、`PhaseBad`、`ScreenMissing`、`ScreenBad`、`ToolsMissing`、`LlmMissing`、`LlmBad`；子介面與共用工具另有自己的代號（見上一條）。
- **`AOS_KERNEL`**：非空＝ctl 信照路由寄那個信箱，stderr 印 `aos-agent: warning: routing via AOS_KERNEL=<路徑>`。不從信箱位置辨識 kernel 身份、不查它是否 running、不自動直接寄 daemon；即使對象就是收件者本身也一樣。判官本身睡著或停著＝設計系統的人要管的風險（使用者 11-07），手動用 `aos-daemon-ctl wake NAME`（停著用 `start`）叫醒：aos-daemon-ctl 一律直寄 daemon、不看 `AOS_KERNEL`（11-07「aos-daemon-ctl 永遠直寄」；aos-agent＝經作業系統〔判官〕，aos-daemon-ctl＝人直接敲板子）。
- **等回信**（11-05 [edge-agent 題 2](../../thinking/2026-11/05/edge-agent/README.md)，使用者選「加 --reply-to 等回信」）：`ctl add`／`rm`／`start`／`stop`／`sleep`／`wake` 每封信都帶回信信箱（`reply_to`）寄，最多等 `--timeout-s S`（預設 30 秒）。六個動詞都支援這個旗標，S 必須是有限且大於 0 的秒數，沒有短名；設計見 [寄信者自設逾時](../../thinking/2026-11/06/os-impl/05-寄信者自設逾時.md)。回信信箱是**共用的**（11-06 [no-pid](../../thinking/2026-11/05/no-pid/README.md) P3）：有 `$AOS_STACK`＝`$AOS_STACK/daemon_reply/`；沒有（人殼）＝`<daemon stack>/procs_ctl_mailbox/reply/`；大家共用、靠回信的 `in_reply_to` 認自己那封，沒人領的 10 分鐘後由下一個來拿信箱的人收掉（垃圾回收，不是判死活）。判官不掛＝回信 `applied: false` 一到就退：`aos-agent: error: AddRejected AOS_KERNEL refused the add letter: NameUnknown evil not in allowed`（滿額是 `SlotMissing`；wake／start 超過 `max_running` 是 `CtlRejected`）。放行或沒設 `AOS_KERNEL`＝daemon 回 `applied: true`，照舊等表上變成結果（表先變、回信還沒到＝最多再等 1 秒讓它落地）；回了但表等滿 S 秒沒變＝`WaitFailed`。**S 秒內一封回信都沒有**時按下面的排隊／撤信規則處理，不從 daemon 或判官身份猜原因。被 TERM 退 143、HUP 退 129。
- **排隊與等滿**：add／start／wake 收 `--on-queued fail|ok`，預設 `fail`。`fail` 把 `queue_wait_ms=S×1000` 放進 body；判官按信封 `sent_at`＋毫秒牆鐘到期，回拒信後確定不再轉寄。`ok` 不帶期限；等滿 S 秒，只在公開 `queue.json` 確認自己那封仍在排時印 `queued NAME at position N (letter L; applied when a slot frees)`、退 0，意思是已排隊，尚未掛上。其他沒回信的情況仍失敗。`fail` 在隊裡等滿時多等 1 秒收最後拒信：收到就以拒信為準（add＝`AddRejected`、start／wake＝`CtlRejected`，帶 `SlotMissing`）；仍沒回才是 `DaemonFailed`。未開 queue＝格滿立即拒；有回信一律以回信為準。逾時失敗時盡力 `aos-post regret` 撤仍在原收信箱 `new/` 的信；判官已領進 cur 的由信內期限擋晚套，已轉寄到 daemon ctl 或 daemon 已領走就不能保證取消，可能之後才套。詳見 [已知限制](docs/02-已知限制.md)。

## 介面 `aos-agent`：ctl add 只看宣告

一個資料夾能被 `ctl add`，只看它頂層 `interfaces.json` 有沒有 `aos-agent` 這個 key（沒有＝`InterfaceMissing`、不送信；讀不懂＝`InterfaceBad`）；不驗 `cli.json`、`fsm.json`（宣告了卻沒做到，第一圈就出錯結束、表上留 `stopped`＋原因）。介面六條（資料夾程式、只吃 aos 的環境變數、常駐有窗、`queue/` 收 user message、`history.jsonl` 寫回答、錯在 stderr 一行）與選配子介面見 [03](../../thinking/2026-11/04/aos-agent/03-種類與契約.md)：

```json
{"aos-agent": {"entry": "body.json", "screen": "screen", "tools": "tools.json", "llm": "llm.json"}}
```

- `entry`（選填，11-05 [portable-flow 題 4](../../thinking/2026-11/05/portable-flow/05-衝突與方向題.md)）＝定義裡**身體的入口**（相對路徑，可帶 `#/指標`；不在或寫成絕對／`..`＝`InterfaceBad`）。宣告了＝`ctl add` 掛的是 `<定義>/<entry>`（`aos-daemon-ctl add --def <定義> <定義>/<entry>`，表上的 `def` 照樣是定義資料夾）；沒宣告＝掛定義資料夾本身（照它的 `_entry` 判型，11-04 起的行為）。用處：定義的 `_entry` 空出來寫成「**把自己掛上 daemon**」，`aos-exec 那個資料夾`＝`aos-agent ctl add 那個資料夾`（使用者「介面維持 aos-agent add」、不加 `aos-exec --daemon`；11-05 add 收進 `ctl`）。範例在 [templates/agent-fsm](../../templates/docs/02-agent-fsm.md)：
  `_entry`＝`{"argv": ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}], "cwd": {"$env": "AOS_WS"}}`、`body.json`＝`["aos-loop", "loop.json"]`。aos-exec 跑 `_entry` 時已經 cd 進定義資料夾，所以單子用 `cwd` 換回工作區（`AOS_WS`＝`--ws` ＞ 外面的 `$AOS_WS` ＞ 呼叫當下的 cwd，轉絕對）：`ctl add` 沒給 `--ws` 就沿用這個 `$AOS_WS`，未設或空才用 cwd；`./.stack` 找 daemon 仍從 cwd 找；`AOS_CD`＝定義資料夾的絕對路徑；名字＝資料夾名。不走 `sh -c`。`cd ws && aos-exec ../agents/bob` 就把 bob 掛上 `ws/.stack` 的 daemon（WSL 實測）；要換名字、換 ws 以外的設定就直接打 `aos-agent ctl add …`（`aos-exec 資料夾 參數` 的參數會接在 argv 尾巴、ctl add 不收）。

- `screen`＝定義裡一個資料夾程式，它自己的 `interfaces.json` 宣告 `{"aos-agent/screen": {}}`（沒宣告＝`ScreenBad`）。aos-agent 從 daemon 表那一列的 `def` 欄找回定義（aos-daemon-ctl add 送、daemon 記；使用者 11-04「那就b。」；沒這欄＝`InterfaceMissing`，`ctl rm` 再 `ctl add` 一次），叫 `aos-exec --ws <ws> --stack <stack> <定義>/<入口> 動作…`。沒宣告＝`ScreenMissing`（看回答改用 `listen --follow`）。
- `tools`＝定義裡登記檔的相對路徑（不可絕對、不可含 `..`、不可指資料夾），也決定**這一隻的覆蓋層**位置：`<stack>/<同一相對路徑>`。例如宣告 `"tools": "cfg/my_tools.json"`，就讀 `<定義>/cfg/my_tools.json`、只改 `<stack>/cfg/my_tools.json`（11-06 K-6）；`aos-agent tools` 只寫這個宣告的覆蓋層（11-05 起只存差異 `{"add": {名: 登記}, "rm": [名]}`、不再整份複製定義；身體每次讀「定義疊覆蓋層」、定義改了照疊；`reset` 刪覆蓋層）——存什麼、怎麼合併、定義改了怎麼辦見 **[docs/03 tools 覆蓋層](docs/03-tools覆蓋層.md#tools-覆蓋層)**。改定義用 `aos-tools --file <定義>/<宣告的 tools 路徑> …`。同一份定義掛了好幾隻時，改這隻的會在 stderr 提醒一行 `aos-agent: warning: this definition (/agents/shared) is also used by bob; only ann's own copy (in its stack) changed, theirs did not (to change them all, edit the definition: aos-tools / aos-json)`（例：ann、bob 共用 `/agents/shared`）。
- `llm`＝定義裡那份**腦設定檔**的相對路徑（跟 `tools` 同一種寫法；11-04 晚 [think-as-function 03 § 4](../../thinking/2026-11/04/think-as-function/03-呼叫端.md)：`aos-llm` 是寄請求給 llm kernel 的基礎工具，aos-agent 的 `llm` 只是 aos-json 的語法糖）。這隻改過的鍵＝stack 裡同一個相對路徑（例 `<stack>/llm.json`），**只放改過的鍵**、其他照定義：`show`＝定義那份（沒有＝`{}`）疊改過的、一行一個 `鍵=值`，stderr 一行列哪些鍵是改過的；`set 鍵=值…`＝`aos-json set --str <stack 那份>#/鍵 值`（不在先建 `{}`；值一律字串）；`reset`＝刪掉。鍵由那隻身體認（agent-fsm：只認 `endpoint`＝kernel 的 endpoint 包代號，model 固定在包上；eca：`model`），aos-agent 不認也不擋；身體每題重讀、有的鍵蓋過定義。改定義＝人直接 `aos-json set --str <定義>/llm.json#/endpoint sol`。沒宣告＝`LlmMissing`；宣告的是資料夾或讀不懂＝`LlmBad`。

## 用法例子

11-04 在 WSL 逐條跑過的一整串（ctl add 兩隻、ctl ls、say／listen、ctl state、chat、tools、open、ctl stop／start、ctl rm；11-05 改成 ctl 寫法；tools 那段 11-05 改成覆蓋層的輸出；11-06 加短名與確認）在 [docs/01-用法例子](docs/01-用法例子.md)。

## agent 對話協議（P-42；併自 extras/human）

- **stdin／stdout**（使用者 11-05「aos-say,aos-listen，我希望能支援stdin/out。」）：`say` 沒給話（或只給 `-`）＝整份 stdin 是**一則**訊息（照 UTF-8 原樣讀、不看 locale，去掉尾端一個換行〔`aos_ws.put` 本來就再把結尾的換行全去掉〕）；stdin 是終端又沒給話＝`ArgumentsBad`、立刻退，不卡著等；要寄一個字的 `-` 就 `echo - | aos-agent say`。`listen` 的 stdout **只有回答本文**，提醒、狀態一律 stderr，所以 `echo 題 | aos-agent say && aos-agent listen > 答.txt`、`cat 長題.md | aos-agent say && aos-agent listen | 下一支` 都行（say 的 stdout 是信件名稱，要丟掉就 `> /dev/null`）。`--last N`／`--follow` 一則一段照現行（代定，11-05）：一行 `== #序號`、問的那幾行前面加 `> `、然後回答本文；要純回答就用不帶旗標的 `listen`（一次一則）。WSL 實測在 [docs/01](docs/01-用法例子.md#stdin-與-stdout11-05)。
- **說**：`aos-agent say 話`＝`aos-post send --ordered <stack>/queue`，一封信的 body＝`{"role": "user", "content": 話}`（當 queue 用的信箱：寄的都帶 --ordered（C-54 R14）；queue 還沒有就先建，可以先說、再跑）。印的信件名稱就是 `new/` 裡那封的名字（`<12 位序號>.<尾名>`）。沒人在跑時照表上的 phase 提醒：`stopped`＝`aos-agent ctl start --target 名字`（有 `reason` 一起印）；`sleeping`＝`wake it: aos-agent ctl wake --target 名字 (if the daemon itself is down, restarting it wakes 名字 too: …)`（不判 daemon 在不在跑，兩條路都給）。「有沒有人在跑它」只看表上那列 `phase` 是 `running`／`stopping`。
- **聽**：`aos-agent say 話 && aos-agent listen`——等**最新那封**＝queue 的 `new/`、`cur/` 裡照處理順序排最後的（`aos_ws.letter_key`）：還在就等；不見了就印 history 最新那則沒有 `tool_calls` 的 assistant（先 say 後 listen 不會漏）。交出去還在答（eca 交給 CLI 就收信、fsm 答的途中；history 最後一則 user 在最後一則回答之後也算——前一題的回答在等的途中才到，不會被當成這封的，11-05 晚）照等；都空、history 也沒回答＝`QuestionUnknown`；信不見了、沒回答、也沒人在跑＝`AnswerMissing`；沒人在跑＝提醒一次、繼續等。等的那封滿 10 秒還在 `queue/new/`、表上又是 `running`＝提醒一次 `SIG has not been taken from queue/new/ after 10 s; X may be busy, or its daemon may be down: aos-daemon-ctl --daemon D ls (the last line shows what the daemon's supervisor sees)`，之後照等（11-06 no-pid P3）。`--timeout-s` 秒數到了＝`AnswerMissing`。也可用 `--timeout-ticks N`（signed 64-bit 範圍的正十進位整數），與 `--timeout-s` 擇一；兩者並給或搭 `--last`／`--follow`＝`ArgumentsBad`。tick 期限用 `aos_ws.deadline_after`／`expired`：有 `AOS_TICK` 就只看時鐘、停鐘照等；未設就按 `AOS_TICK_INTERVAL`（預設 1000 毫秒）退牆鐘。未給期限仍無上限，秒數路徑照舊。暫停中＝提醒一次「要 resume」照等；答到一半被 stop／sleep、或出錯結束（表上 stopped／sleeping；出錯的帶原因）＝提醒一次（附 `ctl start`／`ctl wake` 怎麼叫回）照等；等到一半那隻下了表（退 0）＝`AnswerMissing` 說它最後的輸出在哪、同名 `ctl add` 接著用；被 `ctl rm`（stack 刪了）＝`InstanceMissing`（11-05 edge-agent）。`--last N` 印最後 N 段就走；單用 `--follow` 從目前歷史尾端追新回答，搭 `--last N` 則先印最後 N 段再追。數字旗標（11-06 E1）：`--timeout-s` 要有限、不小於 0 的秒數（不設上限＝不給這個旗標），`--last` 要不小於 0 的整數；`inf`、`nan`、`1e999`、`1.5`、`-1`、`abc`、空字串都是 `ArgumentsBad` 一行、退 1。
- **chat**：say＋listen 的迴圈；提示符 `> ` 在 stderr、stdout 只有回答（`chat < 問題.txt > 答案.txt` 也行）；不印信件名稱。等答案時 Ctrl-C＝退 130，那封已寄出、agent 照答，之後用 `listen` 看；stdin 結束退 0；途中 `AnswerMissing` 印一行錯誤行、不退出（stdin 結束時印過錯誤行＝退 1）；每句寄之前重查表，聊到一半被 `ctl rm`＝`InstanceMissing` 退 1（原本照寄、把刪掉的 stack 建回來，11-05 edge-agent）。
- **看**：`aos-agent ctl state`（狀態、工作區、定義、stack、queue 幾封、最新回答前 60 字、`mailbox_warning.txt` 那一行）。
- **停**（都在 `ctl` 下）：`pause`／`resume`＝`aos-daemon-ctl pause／resume`（寫它的 ctl.json、等它套用最多 5 秒才回；停在哪是身體的事：eca 一批信、fsm 一格）；暫停中被 stop／sleep 的，`ctl start`／`wake` 起來照它的 state 先暫停，那行輸出尾巴會說 `it was paused when it went down, so it comes back paused: aos-agent ctl resume …`；`ctl state` 的 paused＝表上那列 `running` 且它自己 state 窗的 `phase` 是 `paused`（11-05 晚 [listen paused bug](../../thinking/2026-11/05/portable-flow/07-listen-paused-bug.md)；不比 pid）；`stop`／`start`＝表上留成 `stopped`、stack 留著、信照收不答；`sleep`／`wake`＝現在就睡、表上留成 `sleeping`、daemon 開門自己醒（搬家前用）。
- 直接 `aos-exec --ws W <agent>` 跑、沒掛 daemon 的，aos-agent 不管：`aos-post send --ordered W/.stack/queue` 寫信、看 `W/.stack/history.jsonl`。

## 搬家

整份 `ws/`（連 `.stack`）和定義保持相對位置 `cp -r` 或 git 來回，到新位置 `aos-exec ../daemon` 就接著跑（11-05）。要點：**先 Ctrl-C 讓 daemon 睡著再存**；`pid`、`boot_id` 那幾欄是上一台的、只有 daemon 自己看；eca 的 claude session 綁那台的 `~/.claude`；git 掉的空資料夾第一圈自己建回；只在 Linux 檔案系統 checkout、別在 Windows checkout 上跑；範本 `cp stack.gitignore ws/.stack/.gitignore`、`cp stack.gitattributes <repo 根>/.gitattributes`。全文與 11-05 實測在 [docs/04-搬家](docs/04-搬家.md#搬家)。

## 已知限制

併自 extras/eca 的那段，在 [docs/02-已知限制](docs/02-已知限制.md)；tools 覆蓋層的邊在 [docs/03](docs/03-tools覆蓋層.md#已知的邊)。

**11-07 裁定 B**：body.json 是陣列或 argv 物件都原樣經 aos-exec 起，不再辨認 aos-loop 來改掛法。任何 body 都可 stop／sleep；stop 寫公開 ctl 並等自行退（不讀 ctl 的就等它自己結束），sleep 送 SIGTERM。非 0 留 stopped＋reason、修好 ctl start；退 0 才下表（adopt 拿不到碼另算），收工一律 sleeping、開門自動 wake。
