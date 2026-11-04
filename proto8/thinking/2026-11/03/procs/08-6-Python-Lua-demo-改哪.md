← [入口](README.md)｜涵蓋：規劃（fable，照原則定的細節，可翻案） › 6. Python、Lua、demo 改哪、7. code map；要使用者看的｜上一份 [07-4-舊名怎麼辦-遷移-當沒看到](07-4-舊名怎麼辦-遷移-當沒看到.md)｜下一份 [09-實作步驟表-不實作-給隊長](09-實作步驟表-不實作-給隊長.md)

### 6. Python、Lua、demo 改哪

| 檔 | 做什麼 |
|---|---|
| `bin/aos-daemon-ctl`、`bin/README.md` | `MAILBOX = "procs_ctl_mailbox"`；`cmd_add` 多 `--stack S`（呼叫 cwd 轉絕對、不驗在不在；空值＝ArgumentsBad），loop 型 `setdefault` `ctl`／`state`、有 `--stack` 多 `stack`；exec 型裸目標或 `{"exec","ws"?,"stack"?}`；`cmd_rm` 送 `{"procs_removed": [名字]}`；新 `cmd_stop`／`cmd_start` 送 `procs_stopped`／`procs_started`、`cmd_pause`／`cmd_resume` 直接改子 loop ctl 的 `paused`（四個先查 stack 有沒有 `loop.json`，沒有＝`CtlMissing`）；`cmd_ls` 一張表、沒種類欄、stopped 的 pid 印 `-`；`--json` 印 `{"procs": …}`；`where` 只認表上的、預設小格 `<D>/procs/<名字>`；捷徑那套隨另一批拿掉；檔頭說明（哪種看 `loop.json`、名詞表、暫停例子） |
| `extras/eca/bin/aos-eca`、README | `procs_state.json`、`.procs`、小格先用列上的 `stack`；`<名字>/<kind>/` 的 `<kind>` 是 eca 的 claude／codex、跟本題無關（README 分清）；**後續（eca 自己一批，本題只點名）**：`stop`＝`aos-daemon-ctl stop`（留表上、`where` 查得到、`aos-say` 投得進）、`start`＝`start`、`remove`→`rm`＝`aos-daemon-ctl rm`＋刪 stack；判子 loop `phase` 的字不變 |
| `extras/ai_tools/bin/aos_ai_base.py`、`aos_ai_daemon.py`、`aos_ai_make.py`、`aos-ai`、README、`concepts.md` | `lctl`／`lstate`→`procs_*`；`read_lstate` 解 `procs` 的 `$ref`；`row` 讀 `procs`；`cell_run` 先用列上的 `stack`；`loops_added`→`procs_added`（spec 已是第 3 種）；status 欄名 `procs_ctl_seq`／`procs_ctl_warning`；`running()`、`daemon down`／`up` 的字不變 |
| `lib/aos/aos_ws.py`、`extras/human/bin/aos_human.py` | 讀 `phase` 的字不變；README 若寫到 daemon 名單名字同步 |
| `demo/talk/team/quiet.py` | `procs/<名字>/state.json`（或讀列上 `stack`）、訊息 |
| `extras/langs/lua/aos.lua`、`examples/clocks.lua`、lua README | `aos.daemon{procs = …}`、已知 key 表加 `procs`／`stack`；`clocks.lua` 路徑 `.stack/procs/clock_<n>/` |
| demo 五份 daemon.json | `loops`→`procs`（每項已有 `max`／`interval_ms`）；`daemon-3` 的 `execs` 併進 `procs`（字串＝跑一次）；`daemon-2` 的 `loops_ctl_mailbox`→`procs_ctl_mailbox`（含 `agent-sam/_entry` 的路徑） |
| `demo/README.md`、`daemon-2`／`daemon-3` README、`impls/aos-post/README.md` | 目錄樹、信的例子、`cat .stack/procs_state.json`；daemon-3 的「兩種寫法對照」改「同一份名單裡兩種寫法」 |
| 測試 16 檔＋`test_aos_daemon_ctl` 新案 | 字串改名；`test_aos_daemon_ctl` 加 rm 一個 key、ls 沒種類欄、loop 型帶 `ctl`／`state`、`--stack` 轉絕對、`where` 表上的／表上沒有＝錯、`stop`→列 `stopped`→`start` 同一 stack、`pause`→子 loop state paused→`resume`、exec 型四個＝`CtlMissing`；`test_ai_tools`／`test_eca` 小格路徑改讀列上的 `stack`；原本 `loops` 裡寫字串的測試子項要它是 loop 就改成物件 |

### 7. code map

`wf/workflows/common/code-map/proto8.md`（aos-daemon-ctl 那行）、`proto8/14-aos-daemon.md`（`read_procs`、`read_procs_ctl`、一張表、`stopped_`、`procs/`、拿掉 `check_apart`／`ctl_note_`）、`02-tests.md`／`02-tests-2.md`、`05-demo-其他.md`、`06-周邊工具-3.md`、`13-demo.md`、`07-aos-json.md`（若提到 `loops`）；commit 前對一遍（鐵律 3）。

## 要使用者看的

第二～五版只有**一條新衝突**（衝突 2，已答「照舊拿掉」），其他都照原文定、沒有跟原則打架的地方（不查不擋＝C-52／N-28；不在就建＝另一批 `aos-exec --stack`；key 形狀＝N-54；daemon 寫子 loop 的 ctl＝N-54 原文；持久化＝N-28；名詞對過之後 aos-loop 不用換字）。舊題與答案留在後面。

### 衝突 2（已答：「照舊拿掉」→ (b)）：loop 型自己退了（跑滿 `max`、身體退 10、或你直接在它的 ctl 寫 `stopped`），表上要留成 `stopped`，還是照 11-02 從表上拿掉

- **大白話**：11-02 你定「子項結束後不留名單」——跑完就從 `ls` 消失。今天的四態說表上的 proc 只有 running／paused／stopped 三種，「停了但還在表上、stack 留著、`start` 叫得回」就是 stopped；像 docker 裡行程退了的 container 會留成 Exited、你 `rm` 它才消失。問題是 daemon **分不出**一支子 loop 是「自己跑完」還是「被誰在 ctl 寫了 stopped」——兩種都退 0，daemon 不讀子項的 state（C-52），只有它自己下的 stop 它知道。
- **選項**：
  - (a) **loop 型只要退了（不論為什麼）就留成 `stopped`，直到 `rm`**（fable 建議）：跟四態完全對上、跟「rm＝先 stop 再移除」對上；`start` 叫得回（它的 stack 都在）；一個 agent 自己 `{"stopped": true}` 收工＝stop，不是消失；`aos-eca-ctl` 的 stop／start 直接用。後果：`max: 1` 的 loop 跑完會留一列 `stopped` 直到你 `rm`（`ls` 會長、`demo/daemon` 跑完兩列都在）；11-02「結束後不留名單」在 loop 型上翻掉，exec 型照舊消失（「停下來就是沒了」）。同名再 add＝設定換掉、照停；要再跑用 `start`。
  - (b) 照 11-02：只有 daemon 自己下的 stop 留成 `stopped`，其他退出（跑滿、退 10、訊號、自己寫 ctl）照舊從表上拿掉。後果：少改一條規矩、`ls` 乾淨；但「表上的狀態」多了一種看不見的區分（同樣退 0，daemon 下的留著、自己退的消失），一個 agent 自己收工就從 daemon 消失、叫不回，eca 的 stop 一定要走 daemon 不能自己停。
- 兩種程式量差不多（都是 `reconcile` 看到子項退了那一段的分岔）。
- **結果**：(b)「照舊拿掉」。只有 daemon 自己下的 stop 留成 `stopped`；其他退出照 11-02 拿掉。§ 2c 第 6 條、§ 3、步驟表、eca 後續已照改。

### 衝突 1（已答：「1. 當沒看到。」→ (b)）：C-48「不認得的 key 一律忽略」vs 舊 key 報錯

- **大白話**：舊 daemon.json 裡還寫 `loops`，照 C-48 忽略＝daemon 默默空跑；10-25 kernel.json 改名時是 CfgBad。兩個先例打架。
- **選項**：(a) 舊 key 報錯；(b) 照 C-48 忽略。**結果**：(b)，§ 4 已照改、C-48 補例子。

### 方向題 1（已答：「2.kind這東西沒用吧，刪掉」→ 兩個選項都不選）：`kind` 以後怎麼長

- **結果**：沒有 `kind`，看寫法（§ 2）；以後多一種形式再看它長什麼樣。
