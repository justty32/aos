← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 talk（10-24；self-improve 11-03 封存到 proto8/archive/self-improve/）｜下一份 [05-demo-其他-2](05-demo-其他-2.md)（pi-tools、file-tools 已遷進 lib）

> 2026-10-24 收尾補：這幾個 demo 各作者做的時候沒改 code map。怎麼跑、錯誤代號見 [demo README](../../../../../proto8/demo/README.md) 各節。

### `proto8/demo/talk/`（agent 之間寄信）

幾隻 agent 互相寄信分工：地址＝對方的工作區，信＝`new/<id>.json`，一到就是那隻的一道題。設計在 [thinking 2026-10-24-agent-talk](../../../../../proto8/thinking/2026-10-24-agent-talk.md)。（a080002b 誤刪、be9f6b61 照作者的 9c961194 補回。）

| 哪裡 | 負責什麼 |
|---|---|
| `member/` | 一隻成員，照抄 agent-dan 範本 |
| `member/_entry` | `exec aos-loop loop.json` |
| `member/loop.json` | `{"exec": "fsm.json", "max": 40}` |
| `member/fsm.json` | idle → think（`brain.py`，120 秒）→ act（`act.py`，60 秒） |
| `member/idle/_entry` | `cur/` 或 `new/` 有題目退 0，沒有退 10 |
| `member/.env` | `AOS_BRAIN_MODEL`（預設 `chatgpt-gpt-6-luna-low`）；腦網址註解掉＝假腦 |
| `member/system.txt` | system 訊息：怎麼寄、要回的信直接答、通知不回 |
| `member/brain.py` | think：同 agent-dan，多兩件——信翻成「[來信] …」給腦看；system 加上名冊（我是誰、角色、還有誰、群組）。錯開頭 `talk-member:` |
| `member/act.py` | act：同 agent-dan，多兩件——題目是要回答的信、還沒寄過給寄件人＝答案經 `send_message` 自動寄回（自動回信不再回；寄不成照舊寫在答案後面，環境壞了才停） |
| `member/tools/send_message`、`check_inbox` | 符號連結 → `../../../../lib/aos/<名>`（10-24 遷移；寄信、看信箱的本體見 [06-周邊工具](06-周邊工具.md)） |
| `member/tools/math`、`clock` | 符號連結 → `../../../../lib/base/<名>`（10-24 遷移前是 agent-dan 的複本） |
| `team/` | 整個團隊 |
| `team/_entry` | `exec aos-daemon daemon.json` |
| `team/daemon.json` | 每 500 毫秒：名單 `procs`（11-03 原 `loops`）裡 ann、bob、cat 各一個子 loop（`aos-exec --ws $AOS_WS/<名> ../member`，`AOS_ROSTER` 指 `$AOS_WS/roster.json`）；daemon 本體跑 `quiet.py` |
| `team/quiet.py` | 名冊上非人的成員信箱 `tmp/`、`new/`、`cur/` 都空＝退 10 收工；有成員的 loop 失敗結束（讀 `$AOS_STACK/loops/<名>/state.json`，11-02 改 `loops/<名字>/`，[thinking 11-02 stack-tools](../../../../../proto8/thinking/2026-11-02-stack-tools.md)；11-03 改 `procs/<名字>/`，錯誤訊息指 `.stack/procs/<名>/stderr.txt`）＝`team: MemberFailed <名>` 退 1 |
| `team/roster.json` | 名冊範例（放進團隊工作區）：`members`（`mailbox`、`role`、`human`）、`groups`、`max_hops` 8、`max_sends` 4、`max_body_bytes` 16000 |
