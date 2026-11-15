小助手（aide）的定義範本：一隻 agent-fsm，腦是 `fake`、沒有工具，唯一的事是 on_clock hook 每 60 格跑一次 `aos-view aide-tick`（view-1114 第 1 期：只搬事實、不叫模型）。

## 它做什麼

每分鐘一次（`hooks.json` 的 `aide_tick`，`every_cycles: 60`，時鐘 1000 ms 一格）：

1. 隊伍資料夾 `~/.aos/view/teams/<隊>/outbox/` 裡每個還沒搬的決策單 → 一封 `pass` 信寄進中轉信箱 `~/.aos/view/mailbox`，原檔全文放 `payload_text`，寄成才搬到 `outbox/sent/`。
2. 事實（隊長與成員的 state／busy／queued、最新一筆留話、還有幾張單沒搬）變了 → 一封 `report`（`summary_by: "none"`，最多 5 分鐘一封）。
3. 每 15 分鐘一封 `beat`（每隊固定錯開 0～180 秒）。超過 35 分鐘沒 beat，全景頁那隊亮紅燈 `aide silent`。

history 不會多任何一則，也不叫腦。範本刻意拿掉了 `timer` 和 `mail_notify`（後者會把信的通知寫進 queue、叫醒腦），也沒有 `.env`（沒設 `AOS_LLM_KERNEL`：萬一有訊息進了 queue，它會停下來、頁面變紅，而不是去叫模型）。

## 隊長照做的步驟（`<隊>` 換成你在 daemon 表上的名字，例 `ok-kf`）

1. **複製定義**（aos 工具 `agent_def`；來源寫本資料夾的絕對路徑，裝好後是 `~/aos-home/ws/tools/aos-view/aide-def`）：

   ```json
   {"op": "new", "from": "/home/lorkhan/aos-home/ws/tools/aos-view/aide-def", "path": "defs/<隊>-aide"}
   ```

   然後 `{"op": "check", "path": "defs/<隊>-aide"}`，`problems` 是空的才往下。定義裡的檔都不用改。

2. **寫 aide.json**：建 `~/.aos/view/teams/<隊>/aide.json`（資料夾沒有就 `mkdir -p`），內容：

   ```json
   {"team": "<隊>", "parent": "repo-aos", "leader": "<隊>", "aide": "<隊>-aide-1", "tags": []}
   ```

   - `team`＝資料夾名；`leader`＝隊長在 daemon 表上的名字（通常跟 `team` 一樣）；`aide`＝下一步的名字，一字不差（中轉信箱只收這個名字寄來的信）；`parent`＝上層隊伍（頂層底下寫 `repo-aos`）；`tags`＝部門標籤，可空。
   - 這是隊伍資料夾裡唯一要手寫的檔；其他檔都由 `aos-view` 指令寫，不要手改。

3. **聘小助手**（aos 工具 `subagent`，這樣它算你的，親子查得到）：

   ```json
   {"op": "add", "def": "defs/<隊>-aide", "name": "<隊>-aide-1", "limits": {"mem_mb": 1024, "files": 256}}
   ```

   沒有 `subagent` 工具時用 shell：`aos-agent ctl add -n <隊>-aide-1 --limits '{"mem_mb":1024,"files":256}' defs/<隊>-aide`（這樣它不算你的 subagent，歸屬只靠 aide.json）。

4. **確認**：一分鐘內 `~/.aos/view/state/teams/<隊>.json` 出現（有 `last_beat`），全景頁你那格多了小助手的名字與最後 beat 時間。沒出現就看小助手 stack 裡的 `stderr.txt`（hook 失敗只印 warning，不會讓它停）。

## 隊長平常用的三個指令（shell）

```sh
A=~/aos-home/ws/tools/aos-view/aos-view
$A note progress "B2 圖紙改完，等 build"          # 留話：start progress done blocked decision handoff ask；--on NAME 標是哪個成員的事
$A decide letter.json                             # 決策單（專區信的 body，格式同 aos-user send）→ 印出單號；含 key／token 的會被拒（SecretInPayload）
$A match <回信資料夾>                              # 使用者回了之後：印 ok: match 才代表專區那封就是你寫的那張
```

隊名預設取 `$AOS_STACK` 的資料夾名（它在 daemon 表上才算）；不是的話加 `--team <隊>`。

## 收隊

`subagent` `{"op": "rm", "name": "<隊>-aide-1"}`（或 `agents_ctl` stop）。`~/.aos/view/teams/<隊>/` 留著；不想讓頁面再判 `aide silent`，把 `aide.json` 改名（例 `aide.json.off`）。
