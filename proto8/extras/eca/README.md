# eca — aos-eca：把外部 coding agent（claude／codex）掛到 aos-daemon 底下；三對指令 open／close、start／stop、add／remove

← [extras](../README.md)｜設計：[thinking 2026-10-30-eca](../../thinking/2026-10-30-eca.md)（C 結論 7～10、衝突 2～4、6、方向題 3）｜前身：[10-28 hub-adapter](../../thinking/2026-10-28-hub-adapter.md)、[10-28 hub-kernel](../../thinking/2026-10-28-hub-kernel.md)、[10-27 claude-switch](../../thinking/2026-10-27-claude-switch.md)｜接的是 [aos-daemon-ctl](../../bin/README.md)、[lib/agent/cli_session.py](../../lib/agent/cli_session.py)、[aos-eca-turn](../../bin/aos-eca-turn)（10-31 前是 `lib/eca/turn` 格）｜測試 `proto8/tests/test_eca_cmd.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」10-30：通用的那層摘出來就是 aos-daemon，aos-eca（11-03 前叫 aos-eca-hub、aos-eca-ctl）只做 daemon 做不到、只有外部 CLI 才需要的三件事——**畫面**（tmux 開／接／關、Ctrl-] 只跳出）、**對話接回**（`--resume`／`exec resume`，id 在 `session.txt`）、**CLI 自己的 session 檔**（`transcripts/` symlink；10-30 起 stop 時換成複製，11-02 晚不再歸檔、一直是 symlink）。

11-02 晚使用者定三對指令（[eca 14 § 決定](../../thinking/2026-10-30-eca/14-11-02-晚使用者想法.md#決定11-02-晚使用者)）：「很好，所以三個對應：open/close, start/stop, add/remove」——`open`／`close`＝開／關畫面，`start`／`stop`＝掛不掛在 daemon 上（stop 留小格），`add`／`remove`＝建立與刪除（remove 刪小格、**不封存**，要留的人 remove 前自己複製）。

## 是什麼

| 檔 | 做什麼 |
|---|---|
| `bin/aos-eca` | 給人用的指令（Python）：每個子命令都是「叫 aos-daemon-ctl ＋ 動小格裡 cli_session 的東西」 |
| `reap/loop.json` | 自動收畫面：子 loop 每分鐘跑 `aos-eca close --idle 30`；add／open（還沒掛時）／start 發現 daemon 上沒有 `eca_reap` 就順手掛上（11-02 晚，使用者「reap.json我以爲會自動掛」；11-02 前叫 `reap.json`、沒人起） |

**沒有自己的常駐 kernel**（衝突 2）：常駐的是 aos-daemon（信箱模式，`daemon.json` 寫 `"loops_ctl_mailbox": "loops_ctl_mailbox"`，11-02 前叫 `loops_mailbox`），誰掛著以它的 `loops_state.json` 為準；10-28 的 aos-hub-kernel、`kernel.sock`、`hub_ipc.py` 刪了。**不另設 hub 的環境變數**（10-28 那個退場，衝突 4）：哪個 daemon＝`--daemon-stack` ＞ `$AOS_DAEMON_STACK`（11-02 從 `--daemon`／`$AOS_DAEMON` 改名、不留別名，使用者「就AOS_DAEMON_STACK吧」「最好明講，也就是--daemon-stack」；給 `--daemon`＝`FlagUnknown`，只設舊名＝`DaemonMissing`、訊息提示改設新名），跟 aos-daemon-ctl 同一套；沒設、不是資料夾、daemon 沒在跑（`loops_state.json` 的 `pid`＋`started_at_ticks` 對不上）＝`DaemonMissing`。

| 指令 | 做什麼 | 底下是 |
|---|---|---|
| `aos-eca add [--kind claude\|codex \| --template 定義] [--name N] [資料夾]` | 建立：把「定義 × 這個資料夾」掛到 daemon，開始替它收 queue；印小格。同名小格還在（停了、收工了、出錯停了）＝daemon 用回它、接著前文與 queue，stderr 一句「要從頭來先 remove」 | `aos-daemon-ctl add --ws 資料夾 --name N 定義`；定義預設 `proto8/demo/eca-<kind>`（`--kind` 沒給＝claude，方向題 3）；名字預設資料夾名；之後 `eca_reap` 沒掛就掛上 |
| `aos-eca remove [資料夾\|名字]` | 刪除：關畫面、從 daemon 拿掉、拆工作區的 `.stack` 捷徑、刪小格（queue、history、session.txt 都沒了；**不封存**，要留先自己複製；claude 自己 `~/.claude/projects` 的對話檔不動） | `aos-daemon-ctl rm`（掛著才叫）→ 等它下表 → 捷徑還指著小格就拿掉 → `rm -r` 小格 |
| `aos-eca start [資料夾\|名字]` | 掛回 daemon：停了、收工了、出錯停了的照小格 `eca.json` 記的工作區與定義同名掛回，接著答 queue 裡排著的信（同一段對話 `--resume`）；本來就掛著＝說一句、退 0 | 清殘留 `stopped` → `aos-daemon-ctl add --ws ws --name 名字 定義`（aos-daemon 用回既有小格、只重寫 `loop.json`） |
| `aos-eca stop [資料夾\|名字]` | 從 daemon 拿掉、關畫面；**小格與工作區 `.stack` 捷徑原樣留**，這期間 `aos-say` 的信照收在 queue、沒人答，`start` 才答；本來就沒掛＝說一句、退 0 | `aos-daemon-ctl rm`（它會拆捷徑）→ 等下表 → 捷徑補回來 |
| `aos-eca ls [--json]` | 列掛著的與停了的：名字、狀態、種類、工作區、對話 id 前 8 碼 | `aos-daemon-ctl ls --json` 的 loops 表，只留小格裡有 `eca.json` 的（aos-eca-turn 每次寫：`kind`、`ws`、`template`） |
| `aos-eca state [資料夾\|名字]`（或 `status`） | 這裡有沒有外部 agent（掛著或停了）；沒有＝`InstanceMissing`、退 1。`status` 是 `state` 的別名、行為一樣（11-03 使用者「那就兩個都支援，status和state兩個指令都可以，檔案照舊」；小格的 `state.json` 不改名） | 同一張表 |
| `aos-eca open [-d] [--kind …\|--template …] [--name N] [資料夾\|名字]` | 接進畫面；沒開就開（有對話就 `--resume` 叫回）；還沒掛就先 add；停了的只開畫面、不替人 start（stderr 提醒）。`-d` 只開不接 | cli_session 的 `open_cell`（agent-fay 的 attach 同一段）；只有人開畫面，aos-eca-turn 從不自己開 |
| `aos-eca close [資料夾\|名字]`／`close --idle 分` | 收起：關畫面、對話留著，aos-eca-turn 照樣用 `--resume` 答。**只管畫面**（11-02 晚第二輪）：沒掛在 daemon 上的（停了、收工了、出錯停了）不再替它重新掛上，stderr 提醒用 `start` | `tmux kill-server`；正在答題＝`SessionBad` |
| `aos-eca watch [資料夾\|名字]` | 跟著看非互動那次在做什麼（讀了哪個檔、說了什麼、花多少），一次回答結束就走 | 讀 CLI 小格的 `live.jsonl` |

- **小格**：daemon 的 `$AOS_DAEMON_STACK/loops/<名字>/`（11-02 改 `loops/<名字>/`，[thinking 11-02 stack-tools](../../thinking/2026-11-02-stack-tools.md)）就是這隻的 stack（`queue/`、`history.jsonl`、`ctl.json`、`state.json`、`trace.jsonl`、`eca.json`），CLI 的小格是它底下的 `<kind>/`（`session.txt`、`tty.sock`、`live.jsonl`、`transcripts/`…）。
- **`.stack` symlink**（衝突 3）：add 時工作區沒有 `.stack`，aos-daemon-ctl 就建一個捷徑指到小格，cd 進去 `aos-say`、`aos-listen` 直接接上；已經有（例如直接 `aos-exec` 跑過留下的真 `.stack/`）＝不建、stderr 一句「工作區已有 .stack，沒建捷徑…要接上請先搬開（或用 `--stack $AOS_DAEMON_STACK/loops/<名字>`〔11-02 改〕）」，add 照樣退 0。stop 時留著（cd 進去照樣 aos-say，信排在小格的 queue）；remove 時拿掉，工作區不留東西。
- **不封存**（使用者 11-02 晚「我覺得不要封存，封存了放在那邊也沒人要用，要用的，結束前自己複製就是了」）：10-30 的 `eca_archive/`（stop 時把小格搬到 `$AOS_DAEMON_STACK/eca_archive/<名字>-<UTC>/`、transcripts 換成複製）拿掉了。stop 小格原樣留，remove 直接刪。
- **狀態**：`收起了`、`畫面開著`、`停了`、`出錯停了`、`收工了`，或 daemon 的 `phase`（`stopping`…）。11-02 起 daemon 不留結束的子項，表上沒有、小格還在（有 `eca.json`）的照樣列，看小格的 `state.json`：`done` 而且結束碼非 0＝`出錯停了`；`done`／`stopped` 而且結束碼 0（例如外部寫小格 `ctl.json` `{"stopped": true}` 收工，11-02 晚）＝`收工了`；其他（stop 或直接 `aos-daemon-ctl rm` 拿掉的，`stopped`＋非 0；`state.json` 不在）＝`停了`。這三種都用 `start` 掛回、`remove` 刪掉。
- **重新掛上前清殘留 `stopped`**（11-02 晚）：add、open（還沒掛時）、start 走到 aos-daemon-ctl add 之前，小格 ctl 窗（定義 `loop.json` 的 `ctl`）有 `stopped` 就只拿掉這個 key（沒別的 key＝刪檔），免得新的子 loop 一起來就收工；其他 key（`paused`…）照留。工作區 `.stack` 已經是指到同一小格的捷徑時，aos-daemon-ctl 當作已接上、不警告。「暫停」只有一種：寫小格的 `ctl.json` `{"paused": true}`（aos-loop 的窗，不餵下一則），這裡不另做 pause（10-28 的 `pause` 改名 `close`）。
- 畫面裡 **Ctrl-]（或 Ctrl-\\）＝跳出、實例不結束**。人在畫面上自己打的話不進 history（方向題 2），全貌看 `transcripts/`。
- 定義＝頂層有 `cli.json` 的資料夾（`kind`、`flags`、`print_flags`、`timeout_ms`），要別的模型、權限就複製一份 `demo/eca-claude` 改 `cli.json`，用 `--template` 指。

## 對它說話

```sh
export AOS_DAEMON_STACK=~/aos-daemon/.stack      # 一個信箱模式的 aos-daemon 在跑（daemon.json 寫 loops_ctl_mailbox）；要絕對路徑，相對路徑 cd 之後就對不上
aos-eca add ~/code/myproj                    # 掛上：~/code/myproj/.stack → $AOS_DAEMON_STACK/loops/myproj/
cd ~/code/myproj
aos-say 讀 src/calc.py 說說裡面有什麼 && aos-listen   # 畫面開著＝打進畫面、沒開＝--resume 問一次
aos-listen --status                              # 「在跑 aos-loop」：daemon 底下的子 loop，經 .stack 捷徑認得
aos-eca open                                 # 接進畫面（第一次會問信任這個資料夾，選 Yes）；Ctrl-] 跳出
aos-eca close && aos-eca ls              # 收起；再問一句照樣答（--resume）
aos-eca stop                                 # 從 daemon 拿掉；ls 顯示「停了」，這時 aos-say 的信排著
aos-eca start                                # 掛回：接著答排著的信、記得前文
aos-eca remove                               # 刪掉：小格、.stack 捷徑都沒了（要留先複製 $AOS_DAEMON_STACK/loops/myproj/）
```

不掛 daemon 也行：`aos-exec --ws ~/code/myproj proto8/demo/eca-claude` 直接跑（stack 在 `~/code/myproj/.stack/`，say／listen 一樣），只是沒有 ls、close --idle 這些。

## 已知限制

- **`AOS_DAEMON_STACK` 要給絕對路徑**，相對路徑 cd 之後就對不上：在 A 資料夾 add 得上，cd 到工作區後 open／ls／close／stop 都是 `DaemonMissing`（say／listen 走工作區的 `.stack` 捷徑，不受影響）。使用者 11-02 晚選「3」：維持、只寫清楚（[eca 09 § 決定 11-02 晚](../../thinking/2026-10-30-eca/09-方向題.md#決定11-02-晚使用者)）。
- **`eca_reap` 掛上後不拿下**（11-02 晚代定）：最後一隻 remove 了也留著，閒著只是每分鐘起一次 `aos-eca close --idle 30`；要拿掉 `aos-daemon-ctl rm eca_reap`（下次 add／start 又會掛回）。它的錯（例如 daemon 沒在跑）看 `$AOS_DAEMON_STACK/loops/eca_reap/stderr.txt`；子 loop 出錯停了也會在下次 add／start 時重新掛上。閒置門檻固定 30 分（使用者：以後依資源調）。
- **stop 的那一瞬間捷徑不在**：aos-daemon-ctl rm 會拆 `.stack` 捷徑，aos-eca 等 daemon 收掉後才補回；這中間在工作區 aos-say，會落到新建的真 `.stack/`。stop 期間 aos-say 印的提示是「另開終端機 aos-exec 跑它」（aos-say 不知道 aos-eca），對 eca 要看成 `aos-eca start`。
- **短時間多封信**（11-02 晚記；**11-03 改了**：aos-eca-turn 一次把 queue 的信全部、照順序丟進一次 CLI，N 封排著＝一次起退，見 [eca 17](../../thinking/2026-10-30-eca/17-11-03-批次-status.md)；下面是之前的樣子）：子 loop 每 `interval_ms`（300 ms）跑一次 aos-eca-turn、一次只認領一封，所以 N 封＝claude 起退 N 次、每次 `--resume` 重讀整段對話；畫面開著＝逐封貼進畫面；人接在畫面上時信排著等人跳出（`--on-busy yield`）；`aos-listen` 等的是最新那封，前面的要 `--last N` 看。start 之後排著的那些也是這樣一封一封答。
- **daemon 的 PATH**：子 loop 用 daemon 啟動時的環境叫 claude／codex、aos-eca-turn、aos-post。從沒有 `~/.local/bin` 的 shell 起 daemon，每則都 `CliMissing`。
- **新資料夾第一次開畫面，claude 會先問「信任這個資料夾嗎」**：人 `open` 接進去回答就好；`open -d` 之後馬上 say，那句會被貼進這個提問。非互動（`-p`）沒有這個提問。
- **ls 要等子 loop 跑第一次**：`eca.json` 是 aos-eca-turn 寫的，add 之後一個 `interval_ms` 內才列得到。
- **收工了的（ctl.json `stopped`）在 daemon 表上沒有**：`aos-daemon-ctl rm` 拿不到它的 `ws`，捷徑不會被 ctl 拆；用 `aos-eca remove`（這支補拿）或 start／add 重新掛上。直接寫 `stopped` 又馬上 add，可能把那次收工取消（aos-loop 每 interval 讀一次 ctl），不另處理。
- **直接 `aos-exec` 跑過的工作區留著真的 `.stack/`**：之後再 add 這個資料夾，aos-daemon-ctl 看到 `.stack` 已在就不建捷徑、印一行警告（add 照樣退 0），cd 進去 aos-say 接到的是舊的那個；要接上就先搬開（例如 `mv .stack .stack-direct`）再 add，或用 `--stack $AOS_DAEMON_STACK/loops/<名字>`（11-02 改）。
- codex 沒有「正在跑一輪」的訊號：人在畫面上送出、還沒講完就跳出，aos-eca-turn 這時送字會插進去（10-24 舊坑）。
- `watch` 只讀 `live.jsonl`（非互動那條路）；畫面上那幾輪看不到，要 `open` 進去看。`live.jsonl` 只接不重寫，會一直長。
- 「閒了幾分」看 CLI 小格裡檔案最後被動的時間：人只是捲畫面、打字沒送出，不算動作。收起＝`tmux kill-server`：人打到一半沒送出的字會丟。
- 你自己在終端機開的 claude 不在裡面，用 Claude Code 內建的 `claude agents` 看。
