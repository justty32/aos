小助手（aide）的定義範本：一隻 agent-fsm，腦是 `fake`、沒有工具，唯一的事是 on_clock hook 每 60 格跑一次 `aos-frontend aide-tick`（view-1114 第 1 期：只搬事實、不叫模型）。

**這個夾只放 aide 跟 agent-fsm 範本不一樣的檔**（使用者 11-17 裁 Q3「只放差異、其餘從範本抄」；以前整份複製一份範本的格，跟範本走樣了）：`hookeds.json`（被勾清單，只掛 aide_tick；蓋掉範本那份）、`aide_tick.json`（那個 hook 的 handler）、`llm.json`（`fake`）、`tools.json`（沒有工具）、`system.txt`、`_metainfo.json`，還有本檔。其餘（`fsm.json`、`loop.json`、`interfaces.json`、各格的 `.py`…）都在做定義時從 `templates/agent-fsm` 現抄，所以範本改了、下次做的 aide 就跟著新。這個夾本身**不是**一份能跑的定義，不要拿 `agent_def` 的 `from` 直接複製它。

## 它做什麼

每分鐘一次（`hookeds.json` 的 `aide_tick`，`every_cycles: 60`，時鐘 1000 ms 一格）：

1. 隊伍資料夾 `~/.aos/view/teams/<隊>/outbox/` 裡每個還沒搬的決策單 → 一封 `pass` 信寄進中轉信箱 `~/.aos/view/mailbox`，原檔全文放 `payload_text`，寄成才搬到 `outbox/sent/`。
2. 事實（隊長與成員的 state／busy／queued、最新一筆留話、還有幾張單沒搬）變了 → 一封 `report`（`summary_by: "none"`，最多 5 分鐘一封）。
3. 每 15 分鐘一封 `beat`（每隊固定錯開 0～180 秒）。超過 35 分鐘沒 beat，全景頁那隊亮紅燈 `aide silent`。

history 不會多任何一則，也不叫腦。範本刻意拿掉了 `timer` 和 `mail_notify`（後者會把信的通知寫進 queue、叫醒腦），也沒有 `.env`（沒設 `AOS_LLM_KERNEL`：萬一有訊息進了 queue，它會停下來、頁面變紅，而不是去叫模型）。

## 隊長照做的步驟（`<隊>` 換成你在 daemon 表上的名字，例 `ok-kf`）

1. **做定義**（shell；抄 `$AOS_HOME/templates/agent-fsm`，再把本夾的檔蓋上去；相對路徑從 `$AOS_WS` 算，跟 `agent_def` 一樣；`source $AOS_HOME/env.sh` 過的 shell 直接打 `aos-frontend` 也行）：

   ```sh
   $AOS_HOME/frontend/bin/aos-frontend aide-def defs/<隊>-aide
   ```

   印 `wrote aide definition ...` 就成了；路徑已經在＝`DefExists`，沒設 `AOS_HOME`＝`TemplateMissing`（加 `--template <agent-fsm 範本夾>`）。`_metainfo.json` 跟其他檔一樣照抄本夾那份（不記出處）。然後 aos 工具 `agent_def` `{"op": "check", "path": "defs/<隊>-aide"}`，`problems` 是空的才往下。定義裡的檔都不用改。

2. **寫 aide.json**：建 `~/.aos/view/teams/<隊>/aide.json`（資料夾沒有就 `mkdir -p`），內容：

   ```json
   {"team": "<隊>", "parent": "<上層隊長>", "leader": "<隊>", "aide": "<隊>-aide-1", "tags": []}
   ```

   - `team`＝資料夾名；`leader`＝隊長在 daemon 表上的名字（通常跟 `team` 一樣）；`aide`＝下一步的名字，一字不差（中轉信箱只收這個名字寄來的信）；`parent`＝上層隊伍（頂層底下寫頂層 agent 的名字）；只寫進小助手轉出的信，頁上的樹不看它（樹只看 subagent 紀錄）；`tags`＝部門標籤，可空。
   - 這是隊伍資料夾裡唯一要手寫的檔；其他檔都由 `aos-frontend` 指令寫，不要手改。

3. **聘小助手**（aos 工具 `subagent`，這樣它算你的，親子查得到）：

   ```json
   {"op": "add", "def": "defs/<隊>-aide", "name": "<隊>-aide-1", "limits": {"mem_mb": 1024, "files": 256}}
   ```

   沒有 `subagent` 工具時用 shell：`aos-agent ctl add -n <隊>-aide-1 --limits '{"mem_mb":1024,"files":256}' defs/<隊>-aide`（這樣它不算你的 subagent，歸屬只靠 aide.json）。

4. **確認**：一分鐘內 `~/.aos/view/state/teams/<隊>.json` 出現（有 `last_beat`），全景頁你那格多了小助手的名字與最後 beat 時間。沒出現就看小助手 stack 裡的 `stderr.txt`（on_clock 的 hook 失敗只印 warning，不會讓它停）。

## 隊長平常用的三個指令（shell）

```sh
A=$AOS_HOME/frontend/bin/aos-frontend
$A note progress "B2 圖紙改完，等 build"          # 留話：start progress done blocked decision handoff ask；--on NAME 標是哪個成員的事
$A decide letter.json                             # 決策單（專區信的 body，格式同 aos-user send）→ 印出單號；含 key／token 的會被拒（SecretInPayload）
$A match <回信資料夾>                              # 使用者回了之後：印 ok: match 才代表專區那封就是你寫的那張
```

隊名預設取 `$AOS_STACK` 的資料夾名（它在 daemon 表上才算）；不是的話加 `--team <隊>`。

## 收隊

`subagent` `{"op": "rm", "name": "<隊>-aide-1"}`（或 `agents_ctl` stop）。`~/.aos/view/teams/<隊>/` 留著；不想讓頁面再判 `aide silent`，把 `aide.json` 改名（例 `aide.json.off`）。
