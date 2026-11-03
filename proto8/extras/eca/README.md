# eca — aos-eca：把外部 coding agent（claude／codex）掛到 aos-daemon 底下；三對指令 open／close、start／stop、add／rm

← [extras](../README.md)｜設計：[thinking 2026-10-30-eca](../../thinking/2026-10-30-eca.md)（C 結論 7～10、衝突 2～4、6、方向題 3）｜前身：[10-28 hub-adapter](../../thinking/2026-10-28-hub-adapter.md)、[10-28 hub-kernel](../../thinking/2026-10-28-hub-kernel.md)、[10-27 claude-switch](../../thinking/2026-10-27-claude-switch.md)｜接的是 [aos-daemon-ctl](../../bin/README.md)、[lib/agent/cli_session.py](../../lib/agent/cli_session.py)、[aos-eca-turn](../../bin/aos-eca-turn)（10-31 前是 `lib/eca/turn` 格）｜測試 `proto8/tests/test_eca_cmd.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」10-30：通用的那層摘出來就是 aos-daemon，aos-eca（11-03 前叫 aos-eca-hub、aos-eca-ctl）只做 daemon 做不到、只有外部 CLI 才需要的三件事——**畫面**（tmux 開／接／關、Ctrl-] 只跳出）、**對話接回**（`--resume`／`exec resume`，id 在 `session.txt`）、**CLI 自己的 session 檔**（`transcripts/` symlink；10-30 起 stop 時換成複製，11-02 晚不再歸檔、一直是 symlink）。

11-02 晚使用者定三對指令（[eca 14 § 決定](../../thinking/2026-10-30-eca/14-11-02-晚使用者想法.md#決定11-02-晚使用者)）：「很好，所以三個對應：open/close, start/stop, add/remove」——`open`／`close`＝開／關畫面，`start`／`stop`＝掛不掛在 daemon 上（stop 留小格），`add`／`remove`＝建立與刪除（remove 刪小格、**不封存**，要留的人 remove 前自己複製）。11-03 `remove` 改名 `rm`（使用者「統一成add/rm吧」，跟 aos-daemon-ctl 一樣，不留別名）。

**11-03 procs**（[thinking 11-03 procs](../../thinking/2026-11-03-procs.md) § 6 eca 那列、[eca 18 § 11-03 procs 實作](../../thinking/2026-10-30-eca/18-11-03-單隻-add-rm.md#11-03-procs-實作stopstart-走-daemonadd---stack)）：daemon 的 loops／execs 統稱 procs，`start`／`stop` 改成 **daemon 的起停**（`aos-daemon-ctl start`／`stop`：停著**還在 daemon 表上**、`phase` `stopped`、stack 留著、`where` 找得到、`aos-say` 照收），`rm`＝`aos-daemon-ctl rm`＋刪它的 stack；每隻的 stack 一律拿 daemon 表上那一列的 `stack`；`add`（和 `open` 新建）多 `--stack S`（使用者「aos-eca add沒辦法指定stack嗎？aos-daemon-ctl add也是？」）。

11-03 使用者（[eca 18](../../thinking/2026-10-30-eca/18-11-03-單隻-add-rm.md)）：**每個子命令只管一隻**——「我預期aos-eca xxx這條指令，就是針對單個eca。如果要影響到所有eca，那得要等之後我們弄出aos-eca-hub這個繼承於daemon的新東西之後再說。」所以 `close --idle`（一次收所有閒著的畫面）與自動掛上的 `eca_reap` 拿掉了；`ls` 暫時留著，以後歸到 aos-eca-hub。`add` 改成跟 `aos-daemon-ctl add XXX` 一樣，XXX 就是 eca 本身（「不應該有定義(template)這東西」），撞名在 add 時就報錯。

**資料夾的兩種意思**：`add XXX`（和 `open` 新建的那條）的資料夾＝**eca 本身**（頂層有 `cli.json` 的那個，例 `proto8/demo/eca-claude`）；其他子命令的 `資料夾`＝**工作區**（或小格裡面）。名字、資料夾都收的地方先比名字；都沒給＝cwd。

## 是什麼

| 檔 | 做什麼 |
|---|---|
| `bin/aos-eca` | 給人用的指令（Python）：每個子命令都是「叫 aos-daemon-ctl ＋ 動它 stack 裡 cli_session 的東西」 |

**沒有自己的常駐 kernel**（衝突 2）：常駐的是 aos-daemon（信箱模式，`daemon.json` 寫 `"procs_ctl_mailbox": "procs_ctl_mailbox"`，11-03 前叫 `loops_ctl_mailbox`、11-02 前 `loops_mailbox`），誰掛著以它的 `procs_state.json` 為準；10-28 的 aos-hub-kernel、`kernel.sock`、`hub_ipc.py` 刪了。**不另設 hub 的環境變數**（10-28 那個退場，衝突 4）：哪個 daemon＝`--daemon-stack` ＞ `$AOS_DAEMON_STACK`（11-02 從 `--daemon`／`$AOS_DAEMON` 改名、不留別名，使用者「就AOS_DAEMON_STACK吧」「最好明講，也就是--daemon-stack」；給 `--daemon`＝`FlagUnknown`，只設舊名＝`DaemonMissing`、訊息提示改設新名），跟 aos-daemon-ctl 同一套；沒設、不是資料夾、daemon 沒在跑（`procs_state.json` 的 `pid`＋`started_at_ticks` 對不上）＝`DaemonMissing`。

| 指令 | 做什麼 | 底下是 |
|---|---|---|
| `aos-eca add [--name N] [--ws WS] [--stack S] XXX` | 建立：XXX＝eca 資料夾（頂層有 `cli.json`），把它掛到 daemon、工作區＝WS，開始替它收 queue；等 daemon 把它放上表才回（11-03，`where` 只認表上的），印它的 stack。**`--stack S`**（11-03）＝這隻的 stack（從呼叫的 cwd 轉絕對、不驗在不在，daemon 起它時建；空＝`ArgumentsBad`；沒給＝daemon 的預設小格 `$AOS_DAEMON_STACK/procs/<名字>/`）。**撞名＝`InstanceExists`、退 1、不送信**：daemon 表上已有這個名字（不論是不是 eca、在跑或停著）——訊息叫你換 `--name` 或先 `rm`，停著的多一句用 `start` | `aos-daemon-ctl add --ws WS --name N [--stack S] XXX`；名字預設 XXX 的資料夾名、`--ws` 預設 cwd（11-03 起沒有 `--kind`／`--template`、沒有預設的 eca，要明給 XXX） |
| `aos-eca rm [資料夾\|名字]` | 刪除：關畫面、從 daemon 拿掉、刪它的 stack（queue、history、session.txt 都沒了；`--stack` 給的那個資料夾也整個刪；**不封存**，要留先自己複製；claude 自己 `~/.claude/projects` 的對話檔不動）。11-03 前叫 `remove` | `aos-daemon-ctl rm` → 等它下表 → `rm -r` 列上的 stack |
| `aos-eca start [資料夾\|名字]` | 再起：停著的用**同一個 stack** 起來（daemon 照原本 add 的設定），接著答 queue 裡排著的信（同一段對話 `--resume`）；本來就在跑＝說一句、退 0 | `aos-daemon-ctl start 名字` → 等列不再是 `stopped`（11-03 前是重新 `add`） |
| `aos-eca stop [資料夾\|名字]` | 停：關畫面、答完手上這題就停；**還在 daemon 表上**（`stopped`）、stack 原樣留，`where` 照找得到，這期間 `aos-say` 的信照收在 queue、沒人答，`start` 才答；本來就停著＝說一句、退 0 | `aos-daemon-ctl stop 名字` → 等列變 `stopped`（11-03 前是 `rm`、下表） |
| `aos-eca ls [--json]` | 列在跑的與停著的：名字、狀態、種類、工作區、對話 id 前 8 碼 | `aos-daemon-ctl ls --json` 的 procs 表，只留列上 `stack` 裡有 `eca.json` 的（aos-eca-turn 每次寫：`kind`、`ws`、`template`）；`--json` 每隻的 `cell`＝那個 stack |
| `aos-eca state [資料夾\|名字]`（或 `status`） | 這裡有沒有外部 agent（掛著或停了）；沒有＝`InstanceMissing`、退 1。`status` 是 `state` 的別名、行為一樣（11-03 使用者「那就兩個都支援，status和state兩個指令都可以，檔案照舊」；小格的 `state.json` 不改名） | 同一張表 |
| `aos-eca open [-d] [--name N] [--ws WS] [--stack S] [名字\|資料夾\|XXX]` | 接進畫面；沒開就開（有對話就 `--resume` 叫回）；停著的只開畫面、不替人 start（stderr 提醒）。先比名字、再比工作區（或在它的 stack 裡）；都認不出而給的是 eca 資料夾（有 `cli.json`）＝先照 add 建（`--name`、`--ws`、`--stack` 照 add）再開；也不是 eca 資料夾＝`InstanceMissing`。已經有的再給 `--name`／`--ws`／`--stack`＝`ArgumentsBad`。`-d` 只開不接 | cli_session 的 `open_cell`（agent-fay 的 attach 同一段）；只有人開畫面，aos-eca-turn 從不自己開 |
| `aos-eca close [資料夾\|名字]` | 收起：關畫面、對話留著，aos-eca-turn 照樣用 `--resume` 答。**只管畫面**（11-02 晚第二輪）：停著的不替它起來，stderr 提醒用 `start` | `tmux kill-server`；正在答題＝`SessionBad` |
| `aos-eca watch [資料夾\|名字]` | 跟著看非互動那次在做什麼（讀了哪個檔、說了什麼、花多少），一次回答結束就走 | 讀 CLI 小格的 `live.jsonl` |

- **它的 stack**：daemon 表上那一列的 `stack`（11-03 procs；預設小格 `$AOS_DAEMON_STACK/procs/<名字>/`，11-03 前 `loops/<名字>/`；`add --stack S` 給的就是 S）——aos-eca 一律從表上拿、不自己拼路徑。裡面是 `queue/`、`history.jsonl`、`ctl.json`、`state.json`、`eca.json`，CLI 的小格是它底下的 `<kind>/`（`session.txt`、`tty.sock`、`live.jsonl`、`transcripts/`…）；`<kind>` 是 eca 的 claude／codex，跟 daemon 的 proc 是哪一型無關（eca 一律是 loop 型）。
- **對它說話＝`--stack $(aos-daemon-ctl where --stack 名字)`**（11-03，[thinking 11-03 stack-where](../../thinking/2026-11-03-stack-where.md)；使用者「那其實.stack根本不需要放到ws那邊」）：工作區**不再**有指到小格的 `.stack` 捷徑（10-30 衝突 3 那套拿掉），add 不碰工作區、原本有的 `.stack/` 也不動不說話。`where` 只認 daemon 表上的；11-03 procs 起 stop 之後還在表上，照樣 `where`。
- **不封存**（使用者 11-02 晚「我覺得不要封存，封存了放在那邊也沒人要用，要用的，結束前自己複製就是了」）：10-30 的 `eca_archive/`（stop 時把小格搬到 `$AOS_DAEMON_STACK/eca_archive/<名字>-<UTC>/`、transcripts 換成複製）拿掉了。stop 的 stack 原樣留，rm 直接刪。
- **狀態**：`收起了`、`畫面開著`、`停了`（daemon 表上 `stopped`）、`停下中`（`stopping`），或 daemon 的其他 `phase`。11-03 前另有「出錯停了」「收工了」（看下了表的小格 `state.json`），**11-03 拿掉**：自己結束的（CLI 出錯退 1、外部直接寫它 `ctl.json` 的 `{"cmd": "stop"}`）daemon 照 11-02 從表上拿掉＝對 daemon、對 aos-eca 都不在了（procs 衝突 2 使用者「照舊拿掉」），`ls` 不列、`state`／`start`／`stop`／`rm`＝`InstanceMissing`；stack 資料夾留著——要接著用就**同名再 add**（同一個 `--stack` 或預設小格：前文、`cur/` 裡沒答完的信都接著），不要了自己 `rm -r`。所以掛在 daemon 下要停就用 `aos-eca stop`。
- **重新掛上前清殘留 `stopped`**（11-02 晚；**11-03 拿掉**：ctl 改成指令後子 loop 起來第一次讀的 ctl 當基準線、不執行，殘留的 `{"cmd": "stop"}` 不用清，[thinking 11-03 ctl-commands](../../thinking/2026-11-03-ctl-commands.md)；下面是原文）：start 走到 aos-daemon-ctl add 之前（11-03 起 add、open 新建時小格一定不在〔在＝撞名〕，只剩 start 會碰到），小格 ctl 窗（eca 資料夾 `loop.json` 的 `ctl`）有 `stopped` 就只拿掉這個 key（沒別的 key＝刪檔），免得新的子 loop 一起來就收工；其他 key（`paused`…）照留。「暫停」只有一種：寫小格的 `ctl.json` `{"paused": true}`（11-03 起 `{"cmd": "pause"}`，用 `aos-daemon-ctl pause 名字`／`resume 名字`）（aos-loop 的窗，不餵下一則），這裡不另做 pause（10-28 的 `pause` 改名 `close`）。
- 畫面裡 **Ctrl-]（或 Ctrl-\\）＝跳出、實例不結束**。人在畫面上自己打的話不進 history（方向題 2），全貌看 `transcripts/`。
- **eca 資料夾**＝頂層有 `cli.json` 的資料夾（`kind`、`flags`、`print_flags`、`timeout_ms`），`add` 的 XXX 就給它；要別的模型、權限就複製一份 `demo/eca-claude` 改 `cli.json`、add 那份。小格 `eca.json` 的 `template` 那格記的就是它（aos-eca-turn 寫的 key，名字沒改）。

## 對它說話

```sh
export AOS_DAEMON_STACK=~/aos-daemon/.stack      # 一個信箱模式的 aos-daemon 在跑（daemon.json 寫 procs_ctl_mailbox）；要絕對路徑，相對路徑 cd 之後就對不上
aos-eca add --ws ~/code/myproj --name myproj proto8/demo/eca-claude   # 掛上（在 repo 根下；XXX＝eca 資料夾）；stack 在 $AOS_DAEMON_STACK/procs/myproj/（--stack S 就在 S）
S=$(aos-daemon-ctl where --stack myproj)       # 它的 stack（11-03 起工作區沒有 .stack 捷徑；where 只認 daemon 表上的）
cd ~/code/myproj
aos-say --stack $S 讀 src/calc.py 說說裡面有什麼 && aos-listen --stack $S   # 畫面開著＝打進畫面、沒開＝--resume 問一次
aos-eca status                                   # 這隻的狀態（11-03 起 aos-listen --status 拿掉了）
aos-eca open                                 # 接進畫面（第一次會問信任這個資料夾：游標預設在 No, exit，先移游標到 Yes 再 Enter）；Ctrl-] 跳出
aos-eca close && aos-eca ls              # 收起；再問一句照樣答（--resume）
aos-eca stop                                 # 停：還在 daemon 表上（stopped）、ls 顯示「停了」，where 照找得到，aos-say --stack $S 的信排著
aos-eca start                                # 再起：同一個 stack，接著答排著的信、記得前文
aos-eca rm                                   # 刪掉：stack 沒了（要留先複製 $S）
```

不掛 daemon 也行：`aos-exec --ws ~/code/myproj proto8/demo/eca-claude` 直接跑（stack 在 `~/code/myproj/.stack/`，say／listen 一樣），只是沒有 ls、start／stop 這些。

## 已知限制

- **`AOS_DAEMON_STACK` 要給絕對路徑**，相對路徑 cd 之後就對不上：在 A 資料夾 add 得上，cd 到工作區後 open／ls／close／stop 都是 `DaemonMissing`（`aos-daemon-ctl where` 也一樣）。使用者 11-02 晚選「3」：維持、只寫清楚（[eca 09 § 決定 11-02 晚](../../thinking/2026-10-30-eca/09-方向題.md#決定11-02-晚使用者)）。
- **短時間多封信**（11-02 晚記；**11-03 改了**：aos-eca-turn 一次把 queue 的信全部、照順序丟進一次 CLI，N 封排著＝一次起退，見 [eca 17](../../thinking/2026-10-30-eca/17-11-03-批次-status.md)；下面是之前的樣子）：子 loop 每 `interval_ms`（300 ms）跑一次 aos-eca-turn、一次只認領一封，所以 N 封＝claude 起退 N 次、每次 `--resume` 重讀整段對話；畫面開著＝逐封貼進畫面；人接在畫面上時信排著等人跳出（`--on-busy yield`）；`aos-listen` 等的是最新那封，前面的要 `--last N` 看。start 之後排著的那些也是這樣一封一封答。
- **daemon 的 PATH**：子 loop 用 daemon 啟動時的環境叫 claude／codex、aos-eca-turn、aos-post。從沒有 `~/.local/bin` 的 shell 起 daemon，每則都 `CliMissing`。
- **新資料夾第一次開畫面，claude 會先問「信任這個資料夾嗎」**：人 `open` 接進去回答就好——游標預設停在「No, exit」，直接按 Enter 會讓 claude 退出，要先用方向鍵移到「Yes」再按 Enter；`open -d` 之後馬上 say，那句會被貼進這個提問。非互動（`-p`）沒有這個提問。
- **ls 要等子 loop 跑第一次**：`eca.json` 是 aos-eca-turn 寫的，add 之後一個 `interval_ms` 內才列得到。
- **自己結束的（CLI 出錯、直接寫它 `ctl.json` 的 `{"cmd": "stop"}`）在 daemon 表上沒有、aos-eca 也找不到**（11-03 procs）：`ls` 不列、`rm` 刪不了（stack 資料夾自己 `rm -r`），要接著用就同名再 `add`。用自訂 `--stack` 的要記得當初給的 S（daemon 不再記得它）。
- codex 沒有「正在跑一輪」的訊號：人在畫面上送出、還沒講完就跳出，aos-eca-turn 這時送字會插進去（10-24 舊坑）。
- `watch` 只讀 `live.jsonl`（非互動那條路）；畫面上那幾輪看不到，要 `open` 進去看。`live.jsonl` 只接不重寫，會一直長。
- 收起＝`tmux kill-server`：人打到一半沒送出的字會丟。
- 你自己在終端機開的 claude 不在裡面，用 Claude Code 內建的 `claude agents` 看。
