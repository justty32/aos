# 05 state 拆分規劃：state.json 只留「我是誰、我在哪個狀態、生效中的設定」，所有「有人敲一下就跟著變」的回音欄（`responded_at`、`ctl_seq`、`ctl_warning`、`mailbox_warning`）搬到同資料夾一扇新的公開窗 `state_flux.json`
← [README](README.md)｜上一份 [04](04-施工結果.md)｜下一份 [05 續：衝突、方向題、施工](05-續-衝突方向題與施工.md)

## 使用者原話（11-09，逐字）

> 然後那個省寫檔，我會希望拉出state單獨放。就是說，state可以拆成不太變動的，和容易變動的，頻繁變動的從state拉出來

（頂層問「容易變動」怎麼定義）

> 容易變動...就是隨便有人敲一下就變動，或是有風吹草動就變動

## 一句話結論

**窗從兩扇變三扇：`ctl.json`（別人寫給我的指令）、`state.json`（我現在是什麼樣，穩定）、`state_flux.json`（我聽到了什麼，易變）。** 易變的欄一律是「回音」——外面敲一下（寄信、寫 ctl、ping、壞信）我回一聲，所以新窗叫 state_flux（aos 條文裡 ctl 的 `seq` 回報本來就叫「回音」，N-14、N-33，一詞一義）。state.json 只在狀態真的轉換時才重寫；寄 30 封 ping、寫一道壞 ctl，state.json 與 procs_state.json 一次都不動。state_flux.json 是公開窗（跟 ctl／state 一樣在 `aos/loop.hpp` 定義、任何程式都能照寫），父判卡住改讀它、aos-daemon-ctl 等回音改讀它；不設旗標、進 image。

## 可執行判準（給一欄，照步驟走）

前提：這欄是程式寫在窗裡給別人看的（不是只給人看的計數器，那種照 [N-09 的 11-09 補](../../../../docs/NORMS/05-基礎設施-窗/02-N-09～N-11.md) 搬 .txt、放旗標後面，跟本條不衝突）。

1. **列出讓它變的事件**：從程式裡找出所有給這欄賦值的地方（grep 欄名）。
2. **敲一下測試**（使用者第 2 句）：對這支程式做三種「不改它狀態的敲」——(a) 寄一封 ping 或任何不改名單的信；(b) 把它正在生效的那道 ctl 原樣再寫一次、只換 `seq`；(c) 寫一道壞 ctl 或一封壞信。做完它的 `phase`、`paused`、`max`、`interval_ms`、`pid`、表上的列都沒變。**這欄變了＝易變→state_flux。**
3. **真的轉換測試**（使用者第 1 句）：敲一下不變、而且只在 phase 改變、起或停（含子項的起落）、設定生效值改變、行程換了、結束時才變的欄＝**穩定→留 state**。
4. **灰色欄**（變的事件既是轉換又很頻繁）：**照字面判，不照頻率判**——事件是「起停」就算穩定，就算一秒起落十次；頻率是工作負載的問題，另題處理（例：llm kernel 每問一次腦起收一個子 loop，表每問都變，那是 kernel「一題一個子 loop」的設計，不是表的欄錯放）。
5. **只有自己讀的欄**不在本條：照 11-09 早的兩條判準（只因時間或每跑一次變＋沒人讀）決定搬不搬 .txt。

一句話版：**敲它、它就回聲的＝回音→state_flux；敲它、它不動的＝它自己的樣子→state。**

## 全欄分類

### `state.json`（aos-loop；aos-daemon 多 `daemon`、有身體再多 `body_code`）

| 欄 | 觸發它變的事件 | 敲一下 | 誰讀 | 分類 | 去處 |
|---|---|---|---|---|---|
| `phase` | 進出 paused／stopping／done／stopped（running⇄waiting 不算） | 不變 | aos-agent hints.py、kernel serve/proc.cpp（done／stopped）、daemon adopt（done）、DaemonExists 鎖不到時看 stopping、人 | 穩定 | 留 |
| `max`、`interval_ms` | ctl 寫了才變（生效值） | 不變 | 人 | 穩定 | 留 |
| `paused` | pause／resume（冪等 resume 不變） | 不變 | loop 起來接舊值、hints.py | 穩定 | 留 |
| `ctl_seq` | 每一道新 ctl（含只換 seq 的同內容） | **變** | aos-daemon-ctl `wait_applied`、loop 起來第一道去重 | 易變 | **state_flux** |
| `ctl_warning` | 壞 ctl 進、好 ctl 清 | **變**（寫壞 ctl） | 人 | 易變 | **state_flux** |
| `daemon` | 起來時定 | 不變 | aos-daemon-ctl `supervisor()`、人 | 穩定 | 留 |
| `body_code`（daemon） | 身體結束碼變了才變 | 不變 | 人 | 穩定（灰：身體壞掉來回跳會頻繁，但那是身體在壞、不是敲） | 留 |
| `code` | 結束 | 不變 | kernel proc.cpp、人 | 穩定 | 留 |
| `pid`、`started_at_ticks`、`boot_id` | 行程換了 | 不變 | daemon adopt、人 | 穩定 | 留 |
| `responded_at` | 新 ctl（好壞）、收到信、起或收子項 | **變** | 父 stuck.cpp、daemon_ctl table.py | 易變 | **state_flux** |
| `updated_at` | 這份寫出去 | 跟著 | 人 | 隨穩定份 | 留（只跟 state） |

### `procs_state.json` 頂層

| 欄 | 觸發 | 敲一下 | 誰讀 | 分類 | 去處 |
|---|---|---|---|---|---|
| `ctl_seq`（procs_ctl 的） | 採用了內容不同的 procs_ctl | **變**（同內容換 seq） | 人 | 易變 | **state_flux 的 `procs_ctl_seq`** |
| `ctl_warning` | 壞 procs_ctl | **變** | 人 | 易變 | **state_flux 的 `procs_ctl_warning`** |
| `mailbox_warning`（開信箱才有） | 壞信 | **變** | table.py→aos-agent add.py（AddRejected）、kernel daemon.cpp（LaunchFailed） | 易變 | **state_flux 的 `mailbox_warning`**（名字不變，N-16） |
| `procs_loop`、`procs_exec`、`procs_stderr`、`procs_ctl_mailbox` | 起來時定 | 不變 | aos-daemon-ctl、aos-agent、kernel | 穩定 | 留 |
| `daemon` | 起來時定 | 不變 | 同 state | 穩定 | 留 |
| `responded_at` | 同 state | **變** | — | 易變 | state_flux（**只放一處**，不再兩扇重複） |
| `procs` 表 | 子項起落、列的 phase（含 stuck）、stop_mode、reason | 不變（ping、壞信、同內容 ctl 都不動表） | aos-daemon-ctl、aos-agent、kernel、adopt | 穩定（灰：問腦子 loop 起落頻繁，照字面是起停） | 留 |
| `pid`、`started_at_ticks`、`boot_id`、`updated_at` | 同 state | 不變 | 人、adopt（boot_id） | 穩定 | 留 |

### `procs` 表每列

`pid`、`started_at_ticks`、`phase`、`code`、`signal`、`stack`、`ws`、`launch`、`stop_mode`、`exec`、`def`、`reason`、`limits`、`auto_restart`、`stuck_after_cycles`、`restart_on_stuck`——**全部穩定、留**。列講的是「我管了誰、怎麼起它、它現在怎樣」，三種敲都不動它；變的只有起停與父對它的看法（stuck／reason）。

### llm kernel 的 `queue.json`、`used.json`、`endpoints.json`

**不套本條。** 它們不是 ctl／state 窗，是 kernel 身體自己的紀錄檔（N-13「身體自己的紀錄檔照舊自訂名」）：一封信進出排隊就是 kernel 的工作本身在變（隊伍變了＝狀態真的轉換，不是敲一下）；`used.json` 是額度帳，kernel 自己每次都要讀回來判份額，不能關也拆不出去；三份都已經有變才寫（11-09 第一段）。要再省（例如 `used.json` 只在換窗或滿額時落檔）是 kernel 的另一題，不在這條原則底下。

### 其他熱檔

aos-fsm `stage.txt`（有變才寫，stage 是 fsm 真的狀態）、agent-fsm `mailbox_warning.txt`（已經是單獨一個小檔，正是本條的先例）、鐘檔 `clock`（時鐘的工作就是每格寫）——都不動。

## 易變的拉去哪（規劃者照原則定的細節，可翻案）

| 題 | 定法 | 依據 |
|---|---|---|
| 檔名、key、旗標（**升成方向題 2**） | 新窗 **`state_flux.json`**；loop.json／daemon.json 選填 key **`state_flux`**（沒寫＝`state_flux.json`、`null`＝不開），旗標 **`--state-flux 檔`** 鏡射 key；共用 stack 時跟 ctl／state 一樣由末端改名（例 `loop_state_flux.json`）。備選名 `responded.json`（只合 `responded_at`、不合 `ctl_seq`）、`ack.json`（縮寫，要進縮寫表）——不採 | C-54（回音＝N-14／N-33 既有用語；一次記住全體系通用）、N-11（旗標鏡射 key）、N-13 11-02 晚補（共用 stack 改名） |
| 格式 | **JSON 一檔多欄**，不是一欄一 .txt。aos-loop：`{"responded_at", "ctl_seq", "ctl_warning"}`；aos-daemon 再加 `{"procs_ctl_seq", "procs_ctl_warning", "mailbox_warning"（開信箱才有）}`，由跟 `info()` 同形的 `flux_more()` 掛進來 | C-48（窗族本來就是 JSON，加一扇不是加一種格式；.txt 會丟掉 null／字串／整數的型別、要人記「空檔＝null」這種暗規則，C-56 不准）、N-14（窗內容是 JSON、只看最新那份） |
| 一扇還是兩扇 | **一個程式一扇 state_flux**，daemon 不另開 `procs_state_flux.json`：回音是「我聽到了」，一個程式一本帳；procs_ctl 的回音進同一扇、key 加 `procs_ctl_` 前綴 | C-56（五個檔不是六個；三個讀者各讀一檔） |
| 寫法 | 照 N-05 先寫 `.state_flux.json` 再改名（父與 aos-daemon-ctl 正在讀）；走現成 `write_window` | N-05、N-14 原子性只靠 rename |
| 什麼時候寫 | **啟動後第一份一定寫**（帶接回的 `ctl_seq`、`responded_at: null`），之後**有變才寫**（整份比），結束不另寫一份。**寫序：state／procs_state 先、state_flux 後**（看到回音時狀態已經落地；`Loop::write_state` 與 `Daemon::flush_table` 都在最後補一次 state_flux 比對） | N-09 11-02 補（第一份一定寫、有變才寫） |
| `updated_at` | **只跟 state／procs_state**，定義不變（這份穩定的寫出去那一刻，現在只有穩定欄變才動）。**state_flux 沒有 `updated_at`**：它每次寫都伴隨 `responded_at` 更新，再加一欄是重複 | C-56 最後一步減法；N-17「不從 updated_at 判」照舊 |
| 有變才寫比什麼 | state.json：`phase`（running\|waiting 合一）、`max`、`interval_ms`、`paused`、`daemon`、`body_code`、`code`、`pid` 三欄；procs_state.json：四個名字欄、`daemon`、`procs` 表；state_flux.json：整份 | 現行 window.cpp／windows.cpp 的比法去掉搬走的欄 |
| 誰讀、怎麼改讀 | **父 stuck.cpp**：讀子 ctl 的 mtime＋子 `state_flux.json` 的 `responded_at`，**不再讀子 `state.json`**（父碰子的東西比現在更少）；state_flux 不在、不是物件、關掉＝這列不判（同今天對 state 的規則）。**aos-daemon-ctl `wait_applied`**：等子 `state_flux.json` 的 `ctl_seq`。**loop 起來**：從舊 `state.json` 接 `paused`、從舊 `state_flux.json` 接 `ctl_seq`（第一道去重）。**table.py `state()`**：`mailbox_warning` 改讀 daemon 的 `state_flux.json`（`responded_at` 回傳若 grep 無人用就拿掉）。**kernel daemon.cpp**：`mailbox_warning` 改讀 `$AOS_DAEMON/state_flux.json`（跟它今天寫死 `procs_state.json` 同一種假設）。hints.py、kernel proc.cpp 讀 `phase`／`paused`／`code`，不動 | C-52 續「可認公開介面」：state_flux 在 `aos/loop.hpp` 公開定義 |
| 讀者怎麼知道檔名 | 跟 state 同一套：父讀小格裡自己寫的 loop 設定的 `state_flux` key、沒寫用 `StateFluxWindow::default_name`；exec 型用預設名。不由 state 窗指、不另加宣告欄 | P7 現行做法（stuck.cpp 已這樣讀 `state`） |
| 撕裂讀 | 沒有讀者需要 state 與 state_flux 同一瞬間的快照：父只讀 state_flux；ctl 工具只讀 state_flux；table.py 的表與警告是兩件獨立的事。寫序 state 先 state_flux 後，保證「看到 `ctl_seq` 追上時 `paused` 已經落地」 | — |
| image／gitignore | **state_flux.json 進 image**（`stack.gitignore` 不擋；補進檔頭「要留」那行）：`ctl_seq` 是 stop→start 不被同一道 stop 再停（11-07 #15-2）要讀的；`responded_at` 搬到別台是舊值，父接回時 `observed_at` 基準擋掉、無害。暫存 `.state_flux.json` 被 `**/.*` 擋 | 11-06 git-image、N-06 11-03 去重 |
| 旗標 | **不設**。state_flux 是窗不是計數器：父要讀、不能關；跟 state 一樣 `null` 才不開 | 03 題 4 的旗標只管沒人讀的計數器 |
| `--enable-logs` | 不變（log 行跟窗無關） | — |
| 範本 | `templates/agent-fsm`、`eca-claude`、`reviewer` 三份 loop.json 已明寫 `ctl`／`state`，順手補 `"state_flux": "state_flux.json"` 寫齊（不補也是預設開） | C-54 一看就懂 |
| 條號 | **不開新條號**：state_flux 的定義寫進 N-09（state 拆成兩扇）、回音欄位寫進 N-33、N-14 族譜加一種 | N-14「每種一條規範」 |

