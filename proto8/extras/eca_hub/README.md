# eca_hub — aos-eca-hub：把外部 coding agent（claude／codex）掛到 aos-daemon 底下，接進畫面、收起、結束歸檔

← [extras](../README.md)｜設計：[thinking 2026-10-30-eca](../../thinking/2026-10-30-eca.md)（C 結論 7～10、衝突 2～4、6、方向題 3）｜前身：[10-28 hub-adapter](../../thinking/2026-10-28-hub-adapter.md)、[10-28 hub-kernel](../../thinking/2026-10-28-hub-kernel.md)、[10-27 claude-switch](../../thinking/2026-10-27-claude-switch.md)｜接的是 [aos-daemon-ctl](../../bin/README.md)、[lib/agent/cli_session.py](../../lib/agent/cli_session.py)、[lib/eca/turn](../../lib/eca/turn/turn.py)｜測試 `proto8/tests/test_eca_hub.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」10-30：通用的那層摘出來就是 aos-daemon，eca-hub 只做 daemon 做不到、只有外部 CLI 才需要的三件事——**畫面**（tmux 開／接／關、Ctrl-] 只跳出）、**對話接回**（`--resume`／`exec resume`，id 在 `session.txt`）、**CLI 自己的 session 檔**（`transcripts/` symlink、stop 時換成複製）。

## 是什麼

| 檔 | 做什麼 |
|---|---|
| `bin/aos-eca-hub` | 給人用的指令（Python）：每個子命令都是「叫 aos-daemon-ctl ＋ 動小格裡 cli_session 的東西」 |
| `reap.json` | 自動收起：aos-loop 每分鐘跑 `aos-eca-hub close --idle 30` |

**沒有自己的常駐 kernel**（衝突 2）：常駐的是 aos-daemon（信箱模式，`daemon.json` 寫 `"loops_mailbox": "loops_mailbox"`），誰掛著以它的 `loops_state.json` 為準；10-28 的 aos-hub-kernel、`kernel.sock`、`hub_ipc.py` 刪了。**不另設 hub 的環境變數**（10-28 那個退場，衝突 4）：哪個 daemon＝`--daemon` ＞ `$AOS_DAEMON`，跟 aos-daemon-ctl 同一套；沒設、不是資料夾、daemon 沒在跑（`loops_state.json` 的心跳行程不在）＝`DaemonMissing`。

| 指令 | 做什麼 | 底下是 |
|---|---|---|
| `aos-eca-hub add [--kind claude\|codex \| --template 定義] [--name N] [資料夾]` | 把「定義 × 這個資料夾」掛到 daemon，開始替它收 queue；印小格 | `aos-daemon-ctl add --ws 資料夾 --name N 定義`；定義預設 `proto8/demo/eca-<kind>`（`--kind` 沒給＝claude，方向題 3）；名字預設資料夾名 |
| `aos-eca-hub ls [--json]` | 列掛著的：名字、狀態、種類、工作區、對話 id 前 8 碼 | `aos-daemon-ctl ls --json` 的 loops 表，只留小格裡有 `eca.json` 的（turn 每次寫：`kind`、`ws`、`template`） |
| `aos-eca-hub state [資料夾\|名字]` | 這裡是不是掛著的外部 agent；不是＝`InstanceMissing`、退 1 | 同一張表 |
| `aos-eca-hub open [-d] [--kind …\|--template …] [--name N] [資料夾\|名字]` | 接進畫面；沒開就開（有對話就 `--resume` 叫回）；還沒掛就先 add。`-d` 只開不接 | cli_session 的 `open_cell`（agent-fay 的 attach 同一段）；只有人開畫面，turn 從不自己開 |
| `aos-eca-hub close [資料夾\|名字]`／`close --idle 分` | 收起：關畫面、對話留著，turn 照樣用 `--resume` 答；**出錯停了的**（子 loop 以非 0 結束，P-20）close 一次＝拿掉再掛回去、重新收（信還在 `cur/`，turn 接著做） | `tmux kill-server`；正在答題＝`SessionBad` |
| `aos-eca-hub stop [資料夾\|名字]` | 結束：關畫面、從 daemon 拿掉、拿掉工作區的 `.stack` 捷徑、小格搬到 `$AOS_DAEMON/eca_archive/<名字>-<UTC>/`、`transcripts/` 的 symlink 換成真的複製 | `aos-daemon-ctl rm` → 等那列 `done`／`stopped` 或不見 → 捷徑還在就拿掉 → 搬小格 → `freeze_transcripts` |
| `aos-eca-hub watch [資料夾\|名字]` | 跟著看非互動那次在做什麼（讀了哪個檔、說了什麼、花多少），一次回答結束就走 | 讀 CLI 小格的 `live.jsonl` |

- **小格**：daemon 的 `$AOS_DAEMON/<名字>/` 就是這隻的 stack（`queue/`、`history.jsonl`、`ctl.json`、`state.json`、`trace.jsonl`、`eca.json`），CLI 的小格是它底下的 `<kind>/`（`session.txt`、`tty.sock`、`live.jsonl`、`transcripts/`…）。
- **`.stack` symlink**（衝突 3）：add 時工作區沒有 `.stack`，aos-daemon-ctl 就建一個捷徑指到小格，cd 進去 `aos-say`、`aos-listen` 直接接上；已經有（例如直接 `aos-exec` 跑過留下的真 `.stack/`）＝不建、stderr 一句「工作區已有 .stack，沒建捷徑…要接上請先搬開（或用 `--stack $AOS_DAEMON/<名字>`）」，add 照樣退 0。rm／stop 時指到小格的那條會拿掉，工作區不留東西。
- **歸檔放哪**（使用者 10-30「A」，翻 10-28 hub-kernel 決定 6）：放 daemon 小格那邊 `$AOS_DAEMON/eca_archive/<名字>-<UTC>/`；工作區永遠只有 `.stack` 捷徑，stop 時捷徑拿掉就好（aos-daemon-ctl rm 會拿；萬一還指著小格或小格裡面，這支補拿），不在工作區建真的 `.stack/`。之後再 add 同一個資料夾，捷徑照樣建得起來。
- **狀態**：`收起了`、`畫面開著`、`出錯停了`，或 daemon 的 `phase`（`stopping`、`done`…）。「暫停」只有一種：寫小格的 `ctl.json` `{"paused": true}`（aos-loop 的窗，不餵下一則），這裡不另做 pause（10-28 的 `pause` 改名 `close`）。
- 畫面裡 **Ctrl-]（或 Ctrl-\\）＝跳出、實例不結束**。人在畫面上自己打的話不進 history（方向題 2），全貌看 `transcripts/`。
- 定義＝頂層有 `cli.json` 的資料夾（`kind`、`flags`、`print_flags`、`timeout_ms`），要別的模型、權限就複製一份 `demo/eca-claude` 改 `cli.json`，用 `--template` 指。

## 對它說話

```sh
export AOS_DAEMON=~/aos-daemon/.stack            # 一個信箱模式的 aos-daemon 在跑（daemon.json 寫 loops_mailbox）
aos-eca-hub add ~/code/myproj                    # 掛上：~/code/myproj/.stack → $AOS_DAEMON/myproj/
cd ~/code/myproj
N=$(aos-say 讀 src/calc.py 說說裡面有什麼)
aos-listen "$N"                                  # 畫面開著＝打進畫面、沒開＝--resume 問一次
aos-listen --status                              # 「在跑 aos-loop」：daemon 底下的子 loop，經 .stack 捷徑認得
aos-eca-hub open                                 # 接進畫面（第一次會問信任這個資料夾，選 Yes）；Ctrl-] 跳出
aos-eca-hub close && aos-eca-hub ls              # 收起；再問一句照樣答（--resume）
aos-eca-hub stop                                 # 結束：看 $AOS_DAEMON/eca_archive/myproj-<UTC>/
```

不掛 daemon 也行：`aos-exec --ws ~/code/myproj proto8/demo/eca-claude` 直接跑（stack 在 `~/code/myproj/.stack/`，say／listen 一樣），只是沒有 ls、close --idle 這些。

## 已知限制

- **daemon 的 PATH**：子 loop 用 daemon 啟動時的環境叫 claude／codex、aos-parts、aos-post。從沒有 `~/.local/bin` 的 shell 起 daemon，每則都 `CliMissing`。
- **新資料夾第一次開畫面，claude 會先問「信任這個資料夾嗎」**：人 `open` 接進去回答就好；`open -d` 之後馬上 say，那句會被貼進這個提問。非互動（`-p`）沒有這個提問。
- **ls 要等子 loop 跑第一次**：`eca.json` 是 turn 寫的，add 之後一個 `interval_ms` 內才列得到。
- **直接 `aos-exec` 跑過的工作區留著真的 `.stack/`**：之後再 add 這個資料夾，aos-daemon-ctl 看到 `.stack` 已在就不建捷徑、印一行警告（add 照樣退 0），cd 進去 aos-say 接到的是舊的那個；要接上就先搬開（例如 `mv .stack .stack-direct`）再 add，或用 `--stack $AOS_DAEMON/<名字>`。
- codex 沒有「正在跑一輪」的訊號：人在畫面上送出、還沒講完就跳出，turn 這時送字會插進去（10-24 舊坑）。
- `watch` 只讀 `live.jsonl`（非互動那條路）；畫面上那幾輪看不到，要 `open` 進去看。`live.jsonl` 只接不重寫，會一直長。
- 「閒了幾分」看 CLI 小格裡檔案最後被動的時間：人只是捲畫面、打字沒送出，不算動作。收起＝`tmux kill-server`：人打到一半沒送出的字會丟。
- 你自己在終端機開的 claude 不在裡面，用 Claude Code 內建的 `claude agents` 看。
