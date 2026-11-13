# aos-daemon

`aos-daemon - 照一張名單，把幾個 proc 各自起在自己的 stack 裡、看著它們`（NAME，C-54 R1）

**一句話：`aos-daemon [FLAGS] daemon.json`——一個開了窗的 aos-loop，外加一張 proc 的表：照表把 proc（經 aos-exec）起起來、看著、停掉、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`、`CtlWindow`／`StateWindow`／`StateFluxWindow` 的公開窗協議；它又帶進 aos-exec、aos-inst、aos-util、aos-directive）與 [aos-post](../aos-post/README.md) 的庫（信箱；它再帶進 aos-lock）。全家慣例見 [impls/README.md](../README.md)。
**透出**：proc 失敗時，將這次執行寫進 `stderr.txt` 的最後非空行接進表上 `reason`，給看表的人與 `aos-daemon-ctl`；不依下層程式名或錯誤字句挑行（K-2；細節見 [08](docs/08-當機復原與已知限制.md#reason-的細節接-03出錯結束一律留)）。
規範（語意以它為準）：[N-28、N-54](../../docs/NORMS/04-基礎設施-loop與daemon.md)；窗 [N-06～N-17](../../docs/NORMS/05-基礎設施-窗.md)；`AOS_DAEMON` [N-63、N-64](../../docs/NORMS/10-基礎設施-定義與工作區.md)。

開門接回 `procs_state.json` 時，整份壞會改名留證、壞列會備份後跳過，好列照接；警告同步進 stderr、log 與 `state_flux.json` 的 `adopt_warning`，見 [狀態窗](docs/04-兩個手把-兩扇狀態窗.md)。

照「資料夾＝程式」的做法寫（使用者「daemon也用新做法重寫吧」、「照預設」，[ideas § 25](../../thinking/2026-10/19/ideas/README.md)）。名詞見 [thinking procs](../../thinking/2026-11/03/procs/README.md)：
daemon 管的子項不論包在 aos-loop 裡一直跑的（loop 型）還是 aos-exec 跑一次的（exec 型）都叫 **proc**；**一份名單 `procs`**、**看寫法決定怎麼起**（沒有 `kind`）、**每項可寫自己的 `stack`**、
daemon 的 **stop／start**（`procs_stopped`／`procs_started`：列留成 `stopped`、用同一個 stack 再起）、收工時的 **sleep／開門的 wake**（收工時 running 的睡下（sleeping），stop 途中的留 stopped，sleep 途中的睡下，rm 途中的拿掉；收工途中被 kill -9，重開時照表上的 `stop_mode` 做，結果一樣。睡下的再開自動起，[下「收工與開門」](docs/03-起-停-暫停.md#收工與開門sleepwake)）；**sleep／wake 也是指令**（`procs_slept`／`procs_woken`）、**表上的路徑相對 daemon 的 stack**（整份 `ws/` 搬走照樣醒）、**所有 proc 出錯結束（退非 0）一律留成 `stopped`＋`reason`**、**身體失敗＝記一行、下一圈再跑**（[docs/06](docs/06-結束碼等.md#結束碼)）、**狀態窗寫不了也是記一行、下一圈再寫**（同上）、**同一個 stack 已有 daemon 在跑＝`DaemonExists`**（[下「11-05 搬家相關」](docs/03-起-停-暫停.md#11-05-搬家相關)）；每列可寫**份額 `limits`**（daemon 在子行程 setrlimit，等同 s6-softlimit；**份額是每個行程各自的上限，不從 daemon 總額扣**，[docs/09](docs/09-份額.md)）；手把 `procs_ctl.json`、窗 `procs_state.json`（一張表）、信箱 `procs_requests/`、proc 的 stack `procs/<名字>/`。
（no-pid P2，[thinking no-pid](../../thinking/2026-11/05/no-pid/README.md)）回音窗 `state_flux.json` 記 **`responded_at`**（最近一次有反應的時間：收信、採用新 ctl、起收子項；身體跑完不算；閒著、睡著不動，不是心跳）；穩定的 state／procs_state 保留 **`daemon`**（管這台的上一層 daemon 的 stack，`null`＝根），[docs/04](docs/04-兩個手把-兩扇狀態窗.md)；信箱認 **`{"ping": true}`**（不改名單、有 `reply_to` 就回 `{"applied": true}`；paused 時不回＝呼叫失敗）與 **`{"procs_state_path": true}`**（11-13：回信多帶 `procs_state.json` 的絕對路徑，沒開那扇窗＝`null`；不是 `true`＝`BodyBad`），[docs/05](docs/05-信箱.md)。
（no-pid P6）任何 proc 可寫通用布林 **`auto_restart`**（常駐：退了同一拍重起、連 3 次在 3 秒內退才留 `stopped`＋reason）與 **`restart_on_stuck`**（卡住才重起）；子 daemon 就是普通 proc（使用者「不要耦合」），整棵樹睡醒是每層自己做的，[docs/02](docs/02-看寫法決定怎麼起.md)、[docs/03](docs/03-起-停-暫停.md#auto_restart常駐11-06)。
（no-pid P7）父只看公開 ctl／state_flux 窗判卡住，任何有窗的 proc 都能用；每列 **`stuck_after_cycles`** 預設 10，沒刺激不判、預設只標 `stuck`，回應後回 `running`；寫 `restart_on_stuck: true` 才收掉再起，父 paused 時只標，[docs/04](docs/04-兩個手把-兩扇狀態窗.md#判卡住-stuck11-06-p7)。
（clock-decouple）daemon 程式**不認時鐘**——沒有 `clock` key（寫了當沒看到），不設 `AOS_CLOCK`；時鐘＝**根** daemon.json `procs` 裡一列普通 proc（範本慣例名 `_clock`）＋根定義資料夾 `.env` 一行 `AOS_CLOCK=${AOS_STACK}/clock`，子 daemon 預設聽外層的鐘；列欄 **`stuck_after_ms`**（跟 `stuck_after_cycles` 擇一，用牆鐘判卡住，給鐘列用），[docs/02](docs/02-看寫法決定怎麼起.md#時鐘普通一列)、[thinking clock-decouple](../../thinking/2026-11/09/clock-decouple/README.md)。想看時鐘走不走就 `cat "$AOS_CLOCK"` 或看跑鐘那列是不是 `running`。kernel 範本不帶鐘列，出廠開 log。
state 沒有 `counter_runs`；給 **`--enable-counters`** 而且有 state 窗時，每一圈開跑時把這個行程起來後跑到第幾圈寫進 state 窗同資料夾的 `counter_runs.txt`（同 aos-loop 的次數；沒有身體也照數；預設不寫），[docs/04](docs/04-兩個手把-兩扇狀態窗.md)、[N-09「計數器」](../../docs/NORMS/05-基礎設施-窗/02-N-09～N-11.md)。
**poke（門鈴）**：`aos-daemon-ctl poke [--ctl|--mail|--all]` 叫 daemon 不等下一圈、立刻看一次檔——`SIGRTMIN+1`＝讀 ctl＋procs_ctl、對表（不收信、不跑身體）、`+2`＝再加信箱、`+3`＝提前一整圈（含身體，`max` 照算）；號碼寫在 state 的穩定欄 **`poke`**，連 poke 幾下合併成最強的那種跑一次，身體跑到一半不打斷、跑完立刻補看。**SIGUSR1／SIGUSR2 一律擋住**（不會把 daemon 打死），子項照常收得到。平常的圈不變，[docs/04](docs/04-兩個手把-兩扇狀態窗.md#poke-門鈴11-09)、[N-17「例外一：poke」](../../docs/NORMS/05-基礎設施-窗/06-N-17.md)、[thinking daemon-interrupt](../../thinking/2026-11/09/daemon-interrupt/README.md)。
舊名 `loops`、`execs`、`loops_ctl`、`loops_state`、`loops_ctl_mailbox`、`loops_added`……**當沒看到**（C-48，使用者「1. 當沒看到。」）：不報錯、不提醒。

像一個領班：手上一張名單（`procs`），名單上每個人各有一個小隔間（`$AOS_STACK/procs/<名字>/`，或他自己指定的 `stack`）。他每隔一會兒（`interval_ms`）看一眼兩塊佈告欄：
一塊管他自己（ctl 窗：暫停、收工、節奏），一塊管名單（procs_ctl 窗）。名單改了就把多的請走、少的叫來、要停的請他做完手上這件就下班（**留在名單上**，叫得回來）；
誰自己下班了（`done`）或被他請走了（`stopped`）就在工作日誌（stdout 的 log）記一行「誰、結束碼幾」、從名單白板（procs_state 窗）上擦掉，**這一班不會再叫他回來**（做到一半出了錯走的不擦，標「停著」並寫上原因，修好叫得回來）；
他自己的狀況寫在另一塊白板（state 窗）。他自己收工時（不論為什麼）先把每個人都請走、寫好白板，才走人——還在做事的不擦名字，白板上改寫「休息中」（`sleeping`），他下次開門就把這些人叫回同一個隔間接著做（被他請下班的 `stopped` 不叫）。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json",
#  "procs": {"bob": {"exec": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agents/bob"]}, "max": 1}}}
AOS_STACK=$PWD/.stack/ aos-daemon --enable-logs daemon.json     # 慣例用法是 aos-exec 它；PATH 上要有 aos-exec、aos-loop（帶鐘列才要 aos-clock）
```

**起 daemon 要看 log 就加 `--enable-logs`**（用 aos-exec 起的，旗標寫進定義的 `_entry`：`["aos-daemon", "--enable-logs", "daemon.json"]`；也可以臨時 `aos-exec 定義 --enable-logs`——旗標接在設定檔後面也收（11-11 起，同 aos-loop）；設定檔後面多給的位置參數才是 `ArgumentsBad`，要傳給 daemon 自己身體的參數寫在 `--` 後面）：不加的話 daemon 什麼都不印（stdout、stderr 都安靜，只有出錯時 stderr 一行），看起來像卡住，其實照常在跑；子項起落要看就加它（見下「log」），或看 `aos-daemon-ctl ls`。
**收工：在 daemon 的視窗按 Ctrl-C**（使用者定）——SIGINT 走正常收工（`finish`），所有仍活著的 proc 睡下（`sleeping`），下次開門自己醒（見下「收工與開門」）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭 |
| [02-看寫法決定怎麼起](docs/02-看寫法決定怎麼起.md) | 用法（續）：看寫法決定怎麼起、每個 proc 自己的 stack |
| [03-起-停-暫停](docs/03-起-停-暫停.md) | 用法（續）：起、停、暫停、收工與開門：sleep／wake、log |
| [04-兩個手把-兩扇狀態窗](docs/04-兩個手把-兩扇狀態窗.md) | 用法（續）：兩個手把、兩扇狀態窗、procs_ctl 只寫變動（N-54） |
| [05-信箱](docs/05-信箱.md) | 用法（續）：信箱（N-28、N-16）、子項的工作區 ws、子項的 AOS_DAEMON、指示詞與切檔（N-28、N-45） |
| [06-結束碼等](docs/06-結束碼等.md) | 用法（續）：結束碼；元素；實作注意 |
| [07-建置與測試](docs/07-建置與測試.md) | 建置與測試 |
| [08-當機復原與已知限制](docs/08-當機復原與已知限制.md) | daemon 當掉後的接回、proc 的 stack／信箱出錯不整台停、reason 細節、已知限制 |
| [10-根daemon](docs/10-根daemon.md) | 根是普通 daemon、ready／target 食譜、選用 systemd／s6 範例 |
| [09-份額](docs/09-份額.md) | 份額 `limits`（等同 s6-softlimit／s6-setuidgid） |

<a id="用法"></a>
<a id="看寫法決定怎麼起"></a>
<a id="每個-proc-自己的-stack"></a>
<a id="起停暫停"></a>
<a id="收工與開門sleepwake"></a>
<a id="log"></a>
<a id="兩個手把兩扇狀態窗"></a>
<a id="procs_ctl-只寫變動n-54"></a>
<a id="信箱n-28n-16"></a>
<a id="子項的工作區-ws"></a>
<a id="子項的-aos_daemon_stack11-02thinking-11-02-resident-bob-衝突-2"></a>
<a id="子項的-aos_daemon_stack"></a>
<a id="指示詞與切檔n-28n-45"></a>
<a id="結束碼"></a>
<a id="元素"></a>
<a id="實作注意"></a>
<a id="建置與測試"></a>

**daemon 不分類**（使用者裁定 B）：起法看寫法，之後 stop 一律寫公開 ctl（父寫的 loop 設定有非空 ctl 才用它，否則 ctl.json）；沒人讀或寫不了就等自行退，不改送 SIGTERM。sleep／收工才送 SIGTERM；running 留 sleeping，stop 中收到 sleep 則保留 stopped 與 launch，用 start 再起；已知非 0 留 stopped＋reason，退 0 下表，auto_restart 照 [03](docs/03-起-停-暫停.md#auto_restart常駐11-06)。adopt 以 launch 保留完整入口與參數，不看小格有沒有 loop.json 猜型別。
