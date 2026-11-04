← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 0. 名詞表（代定）、1. 名字總表（改前 → 改後）、2. 看寫法決定怎麼起與每項的 `stack`（代定）｜上一份 [01-使用者原文-11-02-晚起-逐字-依先](01-使用者原文-11-02-晚起-逐字-依先.md)｜下一份 [05-2c-起-停-暫停-代定](05-2c-起-停-暫停-代定.md)

## 規劃（fable，照原則定的細節，可翻案）

### 0. 名詞表（代定）

使用者「名詞表先設計好，一種狀況能符合多個名詞就挑一個統一用」。

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
| 兩次之間睡 `interval_ms` | waiting | running 的細分 |
| 跑完了（滿 `max`、身體退 10） | done | 自己走完；不是 stop 也不是拔 |
| 被訊號收掉、自己出錯退 1 | stopped | 跟 stop 帶到的狀態同一個字（「同一種狀況能符合多個名詞就挑一個」），原因看 `code`／`signal` |

**一種場合挑一個字**：

| 場合 | 用哪些字 |
|---|---|
| daemon 的表（`procs_state` 的列、`ls`） | `running`、`stopping`（收的途中）、`stopped`（11-03 晚加 `sleeping`，見 [§ 8](10-實作時代定-11-03-實作者照原則定的.md#8-收工時改寫成休息中sleepwake11-03-晚)）；**不轉述** paused（子 loop 自己的 state，daemon 不讀，C-52）；自己退了的照 11-02 從表上拿掉，只有 daemon 下的 stop 留 `stopped`（衝突 2「照舊拿掉」） |
| aos-loop 自己的 ctl（daemon 繼承） | `cmd`＝`pause`／`resume`／`stop`（[ctl-commands](../ctl-commands/README.md)）；stop＝跑完這次退 0、留 stack |
| aos-loop 自己的 state `phase` | `running`、`waiting`、`paused`、`done`、`stopped`（不動） |
| aos-daemon-ctl 子命令 | `add`、`rm`、`start`、`stop`、`pause`、`resume`（＋看的 `ls`、`where`） |
| 手把 `procs_ctl.json`／信的 key | `procs`、`procs_added`、`procs_removed`、`procs_stopped`、`procs_started`（名字的陣列；§ 2c） |
| eca | `stop`→daemon 的 stop、`start`→start、`remove`→`rm`（11-04 已改：aos-eca 併進 aos-agent，見 [aos-agent 01](../../04/aos-agent/01-子命令.md)） |

### 1. 名字總表（改前 → 改後）

| 面向 | 改前 | 改後 |
|---|---|---|
| daemon.json 名單 | `loops`＋`execs` | **`procs`**＝`{名字: proc}`；可照舊 `{"$ref": [檔, …]}` 拆檔 |
| 每項怎麼起 | 看在哪份名單 | **看寫法**（§ 2），沒有 `kind` |
| 每項的 stack | 一律小格 | 選填 **`stack`**（§ 2）；沒寫＝`procs/<名字>/` |
| 手把 | `loops_ctl.json` | **`procs_ctl.json`**（key `procs_ctl`；沒寫＝預設名、null＝不開；主題在前 R7） |
| 手把認的 key | `loops`、`*_added`、`*_removed` ×2、`seq` | **`procs`**、**`procs_added`**、**`procs_removed`**、**`procs_stopped`**、**`procs_started`**、`seq`；期望表＝（ctl 的 `procs`，沒寫＝底）＋added－removed，先加後減照 N-54 |
| 狀態窗 | `loops_state.json` | **`procs_state.json`**（key `procs_state`） |
| 狀態窗的表 | 兩張 | **`procs` 一張**，每列 `{pid, started_at_ticks, phase, code, signal, stack, ws?}`；`phase`∈`running`／`stopping`／`stopped`；`stack` 一律寫（絕對路徑，§ 2）（11-04 已改：每列多 `exec`、`def`，見 [aos-agent 05/03 第 2 條](../../04/aos-agent/05-實作步驟/03-實作時改的設計.md#實作時改的設計)） |
| 切檔資料夾 | `loops_state_loops/` | **`procs_state_procs/`** |
| 信箱 | `loops_ctl_mailbox/` | **`procs_ctl_mailbox/`**（key `procs_ctl_mailbox`）；body 認 `procs_added`、`procs_removed`、`procs_stopped`、`procs_started`（11-04 已改：沒寫＝預設開、`null`＝不開，見 [four-elements 06 題 5](../../04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)） |
| 小格 | `loops/<名字>/` | **`procs/<名字>/`**（沒寫 `stack` 時）；loop 型小格有 daemon 寫的 `loop.json`、exec 型沒有（11-04 已改：daemon 寫的三個檔名可用 `procs_loop`／`procs_exec`／`procs_stderr` 設、不再替子 loop 補 `ctl`／`state`，見 [four-elements 08 步 6](../../04/four-elements/08-實作步驟-等aos-agent後.md)） |
| log 行 | 有 `table` | **拿掉 `table`** |
| aos-daemon-ctl | `add`／`rm`／`ls`（兩張表、`loop`／`exec` 欄）、捷徑 | `add [--name N] [--ws WS] [--stack S] XXX [-- 參數...]`、`rm`、**`start`／`stop`／`pause`／`resume`**、`ls`（一張表、沒種類欄：`名字 TAB phase TAB pid TAB code TAB ws`）、`--json` 印 `{"procs": …}`、`where`（只認表上的）；捷徑那套隨 [stack-where](../stack-where.md) 拿掉（11-04 已改：`add` 判型看入口最終指到的 JSON，見 [four-elements 06 題 4](../../04/four-elements/06-要使用者裁的題.md#使用者裁定11-04選項原文或他的話逐字)） |
| 錯誤訊息 | 「loops 的名字 …」 | 「procs 的名字 …」；新代號 `CtlMissing`（§ 2c） |
| 環境變數、旗標 | `AOS_DAEMON_STACK`、`--daemon-stack`、`--enable-logs` | 不動（11-04 已改：`AOS_DAEMON_STACK`→`AOS_DAEMON`、`--daemon-stack`→`--daemon`，見 [aos-agent 02](../../04/aos-agent/02-找-agent.md)） |

### 2. 看寫法決定怎麼起、每項的 `stack`（代定）

現行寫法在 [aos-daemon docs 02](../../../../impls/aos-daemon/docs/02-看寫法決定怎麼起.md)。

- **跑一次（aos-exec）**：字串、陣列（C-55、N-28「字串＝aos-exec 的目標」），或物件只有 `exec`（再加 `ws`／`stack`；11-04 已改：也可加 `def`，見上面 docs 02）。**包成子 aos-loop**：其他物件（多任何一個 key，沒有 `exec` 也算，交給子 loop 退 1）；daemon 只解自己認的格，其餘原樣交給子 loop、不驗。
- **唯一的坑**：`"x": {"exec": "fsm.json"}` 想要一直跑會變跑一次；要 loop 就寫一個 loop 的 key（`"interval_ms": 0`）。
- **同名改寫法**：已在跑的不重起（N-54），等它 stopped／被 rm 再放回才照新寫法；取代 10-30「種類不一樣＝收掉重起」。名字唯一，`check_apart` 退場。
- **`stack`**：物件選填，非空字串；`null`＝當沒寫；其他型別＝寫壞（daemon.json CfgBad、ctl 不採用、信壞信）。相對路徑從 daemon 的 cwd 算（`aos-daemon-ctl add --stack` 從呼叫當下的 cwd）；指示詞照 N-45 解。daemon 設 `AOS_STACK=<S>/`，daemon 寫的檔都寫進 S；**S 不在就建**，建不了＝MkdirFailed。
- **不查、不擋、不用捷徑**（C-52、N-28；「S 裡有別的東西使用者自己承擔」）：兩個 proc 同一個 S、S 指到 daemon 自己的 stack、S 是 symlink 都不管；指定了 `stack` 就不建 `procs/<名字>/`。`ws` 跟 `stack` 各管各的。`rm` 不清 S。
- **列上記 `stack`**：adopt、start 照列上的 `stack`；`where --stack`（[stack-where](../stack-where.md)）只認表上的（running、stopping、stopped；11-03 晚加的 sleeping 也算，[§ 8](10-實作時代定-11-03-實作者照原則定的.md#8-收工時改寫成休息中sleepwake11-03-晚)）、印列上的 `stack`，表上沒有＝錯，不看 `procs/<名字>/` 在不在。要「不跑但查得到」用 stop，不是 rm。
