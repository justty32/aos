# aos-daemon

`aos-daemon - 照一張名單，把幾個 proc 各自起在自己的小格裡、看著它們`（NAME，C-54 R1）

**一句話：`aos-daemon [FLAGS] daemon.json`——一個開了窗的 aos-loop，外加一張 proc 的表：照表把 proc（經 aos-exec）起起來、看著、停掉、收掉。**
一個 lib（`lib/libaos-daemon.a`，沒有公開標頭）加一支薄命令列（`bin/aos-daemon`）。連 [aos-loop](../aos-loop/README.md) 的公開 API
（骨架 `aos::loop::Loop`；它又帶進 aos-exec、aos-inst、aos-util、aos-directive）與 [aos-post](../aos-post/README.md) 的庫（信箱；它再帶進 aos-lock）。全家慣例見 [impls/README.md](../README.md)。
規範（語意以它為準）：[N-28、N-54](../../docs/NORMS/04-基礎設施-loop與daemon.md)；窗 [N-06～N-17](../../docs/NORMS/05-基礎設施-窗.md)；`AOS_DAEMON` [N-63、N-64](../../docs/NORMS/10-基礎設施-定義與工作區.md)。

照「資料夾＝程式」的做法寫（使用者「daemon也用新做法重寫吧」、「照預設」，[ideas § 25](../../thinking/2026-10/19/ideas/README.md)）。名詞見 [thinking procs](../../thinking/2026-11/03/procs/README.md)：
daemon 管的子項不論包在 aos-loop 裡一直跑的（loop 型）還是 aos-exec 跑一次的（exec 型）都叫 **proc**；**一份名單 `procs`**、**看寫法決定怎麼起**（沒有 `kind`）、**每項可寫自己的 `stack`**、
daemon 的 **stop／start**（`procs_stopped`／`procs_started`：列留成 `stopped`、用同一個 stack 再起）、收工時的 **sleep／開門的 wake**（還在跑的 loop 型列留成 `sleeping`、再開自動起，[下「收工與開門」](docs/03-起-停-暫停.md#收工與開門sleepwake)）；11-05 起 **sleep／wake 也是指令**（`procs_slept`／`procs_woken`）、**表上的路徑相對 daemon 的 stack**（整份 `ws/` 搬走照樣醒）、**loop 型出錯結束（退非 0）一律留成 `stopped`＋`reason`**（11-05 晚：原本只留 wake／start 起不來的）、**身體失敗＝記一行、下一圈再跑**（11-05 晚，[docs/06](docs/06-結束碼等.md#結束碼)）、**狀態窗寫不了也是記一行、下一圈再寫**（11-05，同上）、**同一個 stack 已有 daemon 在跑＝`DaemonExists`**（[下「11-05 搬家相關」](docs/03-起-停-暫停.md#11-05-搬家相關)）；11-05 起每列可寫**份額 `limits`**（daemon 在子行程 setrlimit，等同 s6-softlimit；**份額是每個行程各自的上限，不從 daemon 總額扣**，[docs/09](docs/09-份額.md)）；手把 `procs_ctl.json`、窗 `procs_state.json`（一張表）、信箱 `procs_ctl_mailbox/`、小格 `procs/<名字>/`。
11-06 起（no-pid P2，[thinking no-pid](../../thinking/2026-11/05/no-pid/README.md)）兩扇窗多 **`responded_at`**（最近一次有反應的時間：收信、採用新 ctl、起收子項、身體跑完；睡著不動，不是心跳）與 **`daemon`**（管這台的上一層 daemon 的 stack，`null`＝根），[docs/04](docs/04-兩個手把-兩扇狀態窗.md)；信箱認 **`{"ping": true}`**（不改名單、有 `reply_to` 就回 `{"applied": true}`；paused 時不回＝呼叫失敗），[docs/05](docs/05-信箱.md)。
舊名 `loops`、`execs`、`loops_ctl`、`loops_state`、`loops_ctl_mailbox`、`loops_added`……**當沒看到**（C-48，使用者「1. 當沒看到。」）：不報錯、不提醒。

像一個領班：手上一張名單（`procs`），名單上每個人各有一個小隔間（`$AOS_STACK/procs/<名字>/`，或他自己指定的 `stack`）。他每隔一會兒（`interval_ms`）看一眼兩塊佈告欄：
一塊管他自己（ctl 窗：暫停、收工、節奏），一塊管名單（procs_ctl 窗）。名單改了就把多的請走、少的叫來、要停的請他做完手上這件就下班（**留在名單上**，叫得回來）；
誰自己下班了（`done`）或被他請走了（`stopped`）就在工作日誌（stdout 的 log）記一行「誰、結束碼幾」、從名單白板（procs_state 窗）上擦掉，**這一班不會再叫他回來**（做到一半出了錯走的不擦，標「停著」並寫上原因，修好叫得回來，11-05 晚）；
他自己的狀況寫在另一塊白板（state 窗）。他自己收工時（不論為什麼）先把每個人都請走、寫好白板，才走人——還在做事的不擦名字，白板上改寫「休息中」（`sleeping`），他下次開門就把這些人叫回同一個隔間接著做（被他請下班的 `stopped` 不叫）。

```sh
cat daemon.json
# {"max": 10, "interval_ms": 200, "ctl": "ctl.json", "state": "state.json",
#  "procs": {"bob": {"exec": {"argv": ["aos-exec", "--ws", {"$env": "AOS_WS", "$path": "bob"}, "../agents/bob"]}, "max": 1},
#            "tick": "../tick"}}
AOS_STACK=$PWD/.stack/ aos-daemon --enable-logs daemon.json     # 慣例用法是 aos-exec 它（11-04 前的例子 proto8/demo/daemon 刪了）；PATH 上要有 aos-exec、aos-loop
```

**起 daemon 要看 log 就加 `--enable-logs`**（用 aos-exec 起的，旗標寫進定義的 `_entry`、放在設定檔前面：`["aos-daemon", "--enable-logs", "daemon.json"]`；`aos-exec 定義 --enable-logs` 會接在設定檔後面＝`ArgumentsBad`，訊息 `flag --enable-logs must come before the config file…` 會這樣提示）：不加的話 daemon 什麼都不印（stdout、stderr 都安靜，只有出錯時 stderr 一行），看起來像卡住，其實照常在跑；子項起落要看就加它（見下「log」），或看 `aos-daemon-ctl ls`。
**收工：在 daemon 的視窗按 Ctrl-C**（使用者 11-03 晚定）——SIGINT 走正常收工（`finish`），還在跑的 loop 型睡下（`sleeping`），下次開門自己醒（見下「收工與開門」）。

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
| [08-當機復原與已知限制](docs/08-當機復原與已知限制.md) | 11-05 第二輪：daemon 當掉後的接回、小格／信箱出錯不整台停、reason 細節、已知限制 |
| [09-份額](docs/09-份額.md) | 11-05 feat-proto 件 5：份額 `limits`（等同 s6-softlimit／s6-setuidgid） |

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
