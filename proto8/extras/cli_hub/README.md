# cli_hub — aos-hub：一個地方看所有 claude／codex，切換、接入、收起、叫回

← [extras](../README.md)｜設計：[thinking 2026-10-27-claude-switch](../../thinking/2026-10-27-claude-switch.md)｜接的是 [lib/agent/cli_session.py](../../lib/agent/cli_session.py)（10-24 的 attach，[thinking](../../thinking/2026-10-24-cli-tools.md)）｜測試 `proto8/tests/test_hub.py`

使用者 10-27：「往後搞不好會有很多claude code cli在跑……是否有一些方式，可以讓我方便切換瀏覽呢？……我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。」「能不能我輸入指令，就先讓這個已經沒在動作的claude code cli實例結束，下次輸入指令再把他叫回來……接入aos體系，並且統一管理每個實例？」

## 是什麼

agent 用 claude／codex 工具（`lib/agent/claude`、`codex`）時，每個工具在 stack 裡有一格（10-24：`session.txt`、`tty.sock`、`turns.jsonl`…）。10-27 起 `cli_session.py` 用到一格就**登記**：在 `$AOS_HUB/cells/`（沒設＝`~/.local/state/aos-hub/cells/`）放一個指過去的捷徑，格裡另記 `tool.txt`（哪個工具資料夾）、`ws.txt`（哪個工作區）。aos-hub 就是讀這份登記的一支指令。

| 指令 | 做什麼 |
|---|---|
| `aos-hub` | **cd 到工作區打這個**：這裡只有一格＝直接接進去（收起了就叫回）；好幾格＝選；沒有＝列全部選 |
| `aos-hub ls`（`--json`） | 列全部：編號、狀態、閒了幾分、工具、工作區、對話 id 前 8 碼 |
| `aos-hub pick` | 列全部、打編號接進去。**畫面裡按 Ctrl-]** 也是它：跳出這格、選另一格 |
| `aos-hub attach [-d] 編號｜路徑` | 接進那格；`-d` 只開不接 |
| `aos-hub watch [編號]` | 看 agent 那次非互動的 claude **正在做什麼**（讀了哪個檔、說了什麼、花多少）；它跑完就結束 |
| `aos-hub stop 編號...` | 收起：畫面（tmux 和裡面的 claude）關掉，對話 id 留在格裡 |
| `aos-hub stop --idle 30` | 收起所有閒了 30 分以上的 |

狀態：`agent 在叫`（agent 正在用這格）、`有人接著`、`畫面在跑`（畫面上正在跑一輪）、`畫面閒著`、`收起了`（沒畫面、對話留著）、`還沒對話`。前三種**不收**。

**叫回**＝對收起的格 `aos-hub`／`attach`：照 10-24 的 `start` 用 `--resume <session.txt>` 開畫面，接回同一段對話（人在畫面上講的、agent 非互動講的都在）。agent 那邊不用改：畫面沒開就走非互動 `-p --resume`，開著就從畫面送字（10-24 兩條路）。

**自動收起**（代定 30 分，見 thinking）：讓 aos-loop 每分鐘跑一次 `stop --idle 30`——

```sh
cd proto8/extras/cli_hub && aos-loop reap.json      # reap.json：{"exec": ["bin/aos-hub", "stop", "--idle", "30"], "interval_ms": 60000}
```

## 怎麼試

試驗場 `~/code/try/claude-switch/`，haiku、每句約 $0.001。

```sh
cd ~/code/try/claude-switch && . ./env.sh            # 拿掉外層 Claude Code 的環境變數
H=~/repo/simple_tools/aos/proto8/extras/cli_hub/bin/aos-hub
./ask ws-a "讀 notes.txt，一句話說裡面有什麼"         # 像 agent 那樣叫一次（ws-b、ws-c 同樣）
$H ls                                                # 三格都「收起了」（只有非互動用過）
cd ws-a && $H                                        # 接進 ws-a 那格（叫回）：看得到剛才那句；Ctrl-] 換一格、Ctrl-\ 跳出
cd .. && ./ask ws-a "數字乘以二？"                    # 畫面開著：agent 從畫面送字，跳回去看得到
$H stop --idle 0 && $H ls                            # 收起；再 cd ws-a && $H 又叫回
./ask ws-b "用 Glob 找出所有 txt 再一一讀" & (cd ws-b && $H watch)   # 看非互動那次即時在做什麼
```

## 已知限制

- 只管 **cli_session 用過的格**（lib/agent 的 claude／codex 工具、agent-fay 的 attach）。你自己在終端機開的 claude、playground 那種直接 `claude -p` 的節點不在裡面；前者用 Claude Code 內建的 `claude agents`（列出所有互動與背景 session）看。
- `watch` 只有 claude（codex 非互動沒做即時紀錄）。
- 判斷「agent 在叫」要碰一下格的 lock：剛好碰上 agent 開始叫的那一瞬間，agent 那次會 `SessionBad`（機率很小，再跑一次就好）。
- 收起＝`tmux kill-server`（claude 收到 SIGHUP 結束；對話是邊講邊存的，不會掉）。人打到一半沒送出的字會丟。
- 「閒了幾分」看格裡檔案最後被動的時間（hook 寫 turns、非互動寫 live、開畫面寫 tmux.conf）：人只是捲畫面、打字沒送出，不算動作。
- 已經在 tmux 裡也能接（拿掉 `TMUX` 再接，會是巢狀 tmux；外層的 prefix 照舊）。
