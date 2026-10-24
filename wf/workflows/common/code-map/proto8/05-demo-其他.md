← [入口](../proto8.md)｜涵蓋：`proto8/demo/` 的 talk、self-improve（10-24）｜下一份 [05-demo-其他-2](05-demo-其他-2.md)（kernel-llm；pi-tools、file-tools 已遷進 lib）

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
| `team/daemon.json` | 每 500 毫秒：ann、bob、cat 各一個子 loop（`aos-exec --ws $AOS_WS/<名> ../member`，`AOS_ROSTER` 指 `$AOS_WS/roster.json`）；daemon 本體跑 `quiet.py` |
| `team/quiet.py` | 名冊上非人的成員信箱 `tmp/`、`new/`、`cur/` 都空＝退 10 收工；有成員的 loop 失敗結束＝`team: MemberFailed <名>` 退 1 |
| `team/roster.json` | 名冊範例（放進團隊工作區）：`members`（`mailbox`、`role`、`human`）、`groups`、`max_hops` 8、`max_sends` 4、`max_body_bytes` 16000 |

### `proto8/demo/self-improve/`（自我改進流程）

給目標和判準，跑函數 → 判定 → 沒達到就讓改進者（一隻 agent）改，直到達成或預算用完。設計在 [thinking 2026-10-24-self-improve](../../../../../proto8/thinking/2026-10-24-self-improve.md)。

| 哪裡 | 負責什麼 |
|---|---|
| `_entry` | `exec aos-loop loop.json` |
| `loop.json` | `{"exec": "fsm.json"}`，不設 max（預算由 judge 管） |
| `fsm.json` | run（15 分）→ judge（1 分）→ improve（30 分）→ run，三格都是內嵌單子 |
| `common.py` | 三格共用：工作區與 stack 佈局、版本（`versions/vNNN/`）、`best`、預算（`budget.json`，預設 5 輪／30 分／50 萬 token）、`run_target`（在暫時複本上跑函數）、`criteria`；10-24 沙箱接線 `sandbox()`（預設用本資料夾的 `sandbox.json` 以 `aos-sandbox` 包著跑；工作區的 `sandbox.json` 優先、`false`＝不關；找不到 aos-sandbox／bwrap＝`SandboxMissing`） |
| `sandbox.json` | 預設的沙箱設定（10-24 真腦實測前定）：`commands` aos-exec、只寫得到 `$IMPROVE_RUN`、斷網、`env` 只帶 `PATH` 與語系幾個 |
| `run.py` | 第一次把 `target/`（或 `target.json`）拍成 v000；跑這一版，結果寫 `runs.jsonl` |
| `judge.py` | 比判準寫 `verdict.json`：達成退 10（放 `out/best/`、寫報告）、預算用完 `BudgetSpent` 退 2、沒達成退 0 |
| `improve.py` | 從最好那版開新一版，工作區只給 `new/task.txt`＋`target/` 叫改進者，改完只收 `target/`；失敗 `ImproverFailed` 退 1；有沙箱就傳 `IMPROVE_SANDBOX` |
| `improver/` | 改進者：從 agent-pip 照抄（工具出錯回給腦、不停） |
| `improver/_entry`、`loop.json`、`fsm.json` | `exec aos-loop loop.json`；max 120；idle → think（180 秒）→ act（120 秒） |
| `improver/idle/_entry` | 同 talk 的 member |
| `improver/.env` | `AOS_BRAIN_MODEL`（`chatgpt-gpt-6-luna-low`）；沒給網址＝假腦，直接答、不改檔 |
| `improver/system.txt` | 改進者的 system：只能改 `target/`、有哪些工具 |
| `improver/brain.py` | 同 agent-pip，多記 usage 到 `$AOS_STACK/usage.jsonl`（給外面算 token 預算）；假腦不叫工具 |
| `improver/act.py` | 同 agent-pip，只改錯誤行的名字（`improver:`） |
| `improver/tools/read`、`write`、`edit` | 符號連結到 `../../../../lib/base/<名>`（10-24 遷移前指 demo/pi-tools） |
| `improver/tools/try_run` | 符號連結 → `../../../../lib/aos/try_run`（10-24 遷移；參數 `timeout` 改名 `timeout_s`、逾時算錯） |
