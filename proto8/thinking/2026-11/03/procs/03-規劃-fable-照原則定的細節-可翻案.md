← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 0. 名詞表（代定）、1. 名字總表（改前 → 改後）｜上一份 [02-現況-查清的-不是規劃](02-現況-查清的-不是規劃.md)｜下一份 [04-2-看寫法決定怎麼起-代定](04-2-看寫法決定怎麼起-代定.md)

## 規劃（fable，照原則定的細節，可翻案）

### 0. 名詞表（代定）

使用者「名詞表先設計好，一種狀況能符合多個名詞就挑一個統一用」。表分三欄：**動作**（指令、信、ctl 的手）、**它帶到的狀態**、**proc 自己走到的狀態**。字夠一般，以後多一種形式（fsm 一次、常駐 agent……）也套得上。

| 動作（人／daemon 做的） | 帶到的狀態 | 說明 |
|---|---|---|
| `add` | running | 插上＝登記＋起（「add 之後會把它 start」） |
| `rm` | （表上沒有） | 拔掉＝先 stop 再拿掉（「remove 後會先把它 stop 後再移除」）；stack 留著 |
| `start` | running（或 paused，看它自己的 ctl） | 把 stopped 的用**同一個 stack** 再起；「只有指令叫醒」 |
| `stop` | stopped | 行程退了、表上還在、stack 留著（CPU 類比裡的「休眠」；sleep／wake 是這對的同義詞，不當指令——**11-03 晚翻案**，sleep／wake 另成一態，見 [§ 8](10-實作時代定-11-03-實作者照原則定的.md#8-收工時改寫成休息中sleepwake11-03-晚)） |
| `pause` | paused | 活著、不跑下一次（使用者定「pause-paused」） |
| `resume` | running | 解除暫停（使用者定「resume-running」） |

| proc 自己走到的 | 字 | 說明 |
|---|---|---|
| 正在跑一次 | running | — |
| 兩次之間睡 `interval_ms` | waiting | aos-loop 今天就有；是 running 的細分，表上不另列 |
| 跑完了（滿 `max`、身體退 10） | done | 自己走完；不是 stop 也不是拔 |
| 被訊號收掉、自己出錯退 1 | stopped | 行程不在、stack 留著——跟 stop 帶到的狀態是同一個字（「同一種狀況能符合多個名詞就挑一個」：都是 stopped，原因看 `code`／`signal`） |

**一種場合挑一個字**（下面各節都照這張用）：

| 場合 | 用哪些字 |
|---|---|
| daemon 的表（`procs_state` 的列、`ls`） | `running`、`stopping`（收的途中）、`stopped`；**不轉述** paused（那是子 loop 自己的 state，daemon 不讀，C-52）；自己退了的（done、訊號、自己寫 ctl）照 11-02 從表上拿掉，只有 daemon 下的 stop 留 `stopped`（衝突 2「照舊拿掉」） |
| aos-loop 自己的 ctl（daemon 繼承） | `paused`、`cmd`＝`pause`／`resume`／`stop`（11-03 ctl 改成下指令，[ctl-commands](../ctl-commands/README.md)；stop＝它跑完這次退 0 留 stack） |
| aos-loop 自己的 state `phase` | `running`、`waiting`、`paused`、`done`、`stopped`（**今天的字，不動**） |
| aos-daemon-ctl 子命令 | `add`、`rm`、`start`、`stop`、`pause`、`resume`（＋看的 `ls`、`where`） |
| 手把 `procs_ctl.json`／信的 key | `procs`、`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`（名字的陣列；§ 2c） |
| eca（另一批） | `stop`→daemon 的 stop、`start`→start、`remove`→`rm`；字照這張 |

### 1. 名字總表（改前 → 改後）

| 面向 | 改前 | 改後 | 備註 |
|---|---|---|---|
| daemon.json 名單 | `loops`＋`execs` | **`procs`**＝`{名字: proc}` | 可照舊 `{"$ref": [檔, …]}` 拆檔 |
| 每項怎麼起 | 看在哪份名單 | **看寫法**（§ 2）：字串／陣列、或只有 `exec`（＋`ws`、`stack`）的物件＝aos-exec 一次；其他物件＝包成子 aos-loop | 沒有 `kind` |
| 每項的 stack | 一律小格 | 選填 **`stack`**（§ 2b）；沒寫＝`procs/<名字>/` | daemon 的 key，不灌進 `loop.json`，相對路徑從 daemon 的 cwd 算 |
| 手把 | `loops_ctl.json` | **`procs_ctl.json`**（key `procs_ctl`；沒寫＝預設名、null＝不開） | 主題在前（R7） |
| 手把認的 key | `loops`、`*_added`、`*_removed` ×2、`seq` | **`procs`**、**`procs_added`**、**`procs_removed`**、**`procs_stopped`**、**`procs_started`**、`seq` | 期望表＝（ctl 的 `procs`，沒寫＝底）＋added－removed，先加後減照 N-54；stopped 集合同一套（§ 2c） |
| 狀態窗 | `loops_state.json` | **`procs_state.json`**（key `procs_state`） | — |
| 狀態窗的表 | 兩張 | **`procs` 一張**，每列 `{pid, started_at_ticks, phase, code, signal, stack, ws?}`；`phase`∈ `running`／`stopping`／`stopped`；多一欄 **`stack`**（絕對路徑，一律寫） | adopt、`where` 靠它 |
| 切檔資料夾 | `loops_state_loops/` | **`procs_state_procs/`** | 現成規則 |
| 信箱 | `loops_ctl_mailbox/` | **`procs_ctl_mailbox/`**（key `procs_ctl_mailbox`） | body 認 `procs_added`、`procs_removed`、`procs_stopped`、`procs_started` |
| 小格 | `loops/<名字>/` | **`procs/<名字>/`**（沒寫 `stack` 時） | loop 型小格有 daemon 寫的 `loop.json`，exec 型沒有——要分哪種看這個 |
| log 行 | 有 `table` | **拿掉 `table`** | — |
| aos-daemon-ctl | `add`／`rm`／`ls`（兩張表、`loop`／`exec` 欄）、捷徑 | `add [--name N] [--ws WS] [--stack S] XXX [-- 參數...]`、`rm`、**`start`／`stop`／`pause`／`resume`**、`ls`（一張表、沒種類欄：`名字 TAB phase TAB pid TAB code TAB ws`）、`--json` 印 `{"procs": …}`、`where`（只認表上的）；捷徑那套隨另一批拿掉 | § 2c 第 8 條 |
| 錯誤訊息 | 「loops 的名字 …」 | 「procs 的名字 …」 | 代號不變；新代號 `CtlMissing`（§ 2c） |
| 環境變數、旗標 | `AOS_DAEMON_STACK`、`--daemon-stack`、`--enable-logs` | 不動 | — |

一句話：**daemon 管的東西叫 procs；一份名單，寫成「要跑什麼」就跑一次、寫成 loop 設定就包成 loop；每項可用 `stack` 換掉小格；add／rm 插拔、start／stop 起停（stack 留著）、pause／resume 暫停；手把 `procs_ctl.json`、窗 `procs_state.json`、信箱 `procs_ctl_mailbox/`。**
