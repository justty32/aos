# gate-auto-1114：repo-aos 的 kernel_gate 先自動處理一輪請求

使用者 11-14 原話：「太多的請求...你可以派一個claude subagent幫你寫程式，你把需求交給他，讓他幫你弄一些可以自動對請求做初步處理的。」

## 結論

- **不用改站程式**。框架站本來就讓 `after_verdict` hook 回放行、拒或留（`lib/aos/kernel/README.md`「先留著等表態」）。kernel_gate 預設掛的 `hold` 每一封都回 hold，所以每一封都要頂層表態。把它換成一支會判的 hook 就行。
- 新 hook：`proto8/lib/agent/kernel_gate/triage`。它照站旁邊的 `triage.json` 判：日常的請求不出聲（照站的 pass 轉給 daemon），明顯不對的回 `GateRefused` 加一行理由，其他的照舊 hold 給 repo-aos。每一封都記一行到 `triage.jsonl`。
- 活樹 repo-aos 的 gate **已經換上，並實測過一封**（拒掉、沒轉寄）。

## 做法：哪些是設定，哪些是程式

| 東西 | 種類 | 在哪 | 何時生效 |
|---|---|---|---|
| `kernel.json` 改掛 `triage`（取代 `hold`） | 設定 | 活樹 gate 夾 | 現在 |
| `triage.json`（規則：名單、路徑根） | 設定 | 活樹 gate 夾 | 現在，每封重讀，改了就生效 |
| `triage`（hook 程式，純標準庫、單檔） | 程式 | repo `proto8/lib/agent/kernel_gate/triage`；活樹 gate 夾放一份抄本 | 抄本現在就在用；repo 那份要換樹才進 `$AOS_HOME/lib` |
| `tests/test_triage.py` | 測試 | repo | — |

站程式 `proto8/lib/aos/kernel` 一行沒改。

## 規則（活樹 `triage.json`）

```json
{
 "protect": ["eca_main", "repo-aos", "llm-gpt", "_sweeper"],
 "names": ["ok-*", "xiaosi"],
 "defs": ["/home/lorkhan/aos-home/agents/opus-kernel", "/home/lorkhan/aos-home/agents/fable-kernel", "/home/lorkhan/aos-home/agents/xiaosi"],
 "def_roots": ["/home/lorkhan/repo/aos/wf/temp/ok-*", "/home/lorkhan/code/*-1114"],
 "ws_roots": ["/home/lorkhan/repo/aos/wf/temp", "/home/lorkhan/code/*-1114"],
 "deny_roots": ["/home/lorkhan/aos-home/lib", "/home/lorkhan/aos-home/py", "/home/lorkhan/aos-home/knowledge"],
 "home_roots": ["/home/lorkhan/repo/aos", "/home/lorkhan/aos-home", "/home/lorkhan/code"],
 "daemon": "/home/lorkhan/aos-home/ws/.stack",
 "log": "triage.jsonl"
}
```

一封信可能有好幾項。每一項都過才放行；有一項該拒就整封拒；其他情況留著。

- **掛新的**（`procs_added`）：名字在 `protect` 裡就拒。def、exec、ws、stack（含 `as_written`）先解成實際路徑：落在 `deny_roots` 底下或不在 `home_roots` 裡就拒。def 和 exec 都是 `defs` 之一或在 `def_roots` 底下，ws 在 `ws_roots` 底下，stack 沒寫、或在 `ws_roots` 底下、或是 daemon 的 `procs/<同名>`，就放行。其他留著。exec 認得三種寫法：路徑、`{"$env","$path"}` 指示詞、aos-agent 帶 envs 時的 `{"argv": ["aos-exec","--",目標…]}`（只看目標）。別種命令列留著。
- **停、起、睡、醒**：名字在 `protect` 裡就拒。名字符合 `names` 就放行。名字在 daemon 表上，而且那一列的 def 和 ws 也照上面的放行條件過，也放行（這條管 ok-* 掛的子 agent）。其他留著。
- **拔**（`procs_removed`）：在 `protect` 裡就拒，其他一律留著。
- body 不是物件、沒有 `procs_*` 請求、或有不認得的 `procs_*` 鍵：留著。
- 有人表態 pass 之後站會重判一次，這時 triage 不出聲，照表態走，也不多記帳。
- 帳的格式：`triage.jsonl` 一行一封，`{"at","letter","from","verdict","why","what"}`。

## 測試

- 單元與真站：`tests/test_triage.py` 6 題，加上原本的 `test_kernel_gate.py` 9 題，共 15 題全過（清過環境、`KERNEL_TEST_TMP=~/code/gate-1114/tmp`）。
- 暫存樹 `~/code/gate-1114`：一台暫存 daemon（pid 373724，已經用 `aos-daemon-ctl -d …/home/ws/.stack shutdown` 收掉），加一隻假 agent `boss` 的 gate 小格。用 `tick`（真的 on_clock handler）跑站，送 aos-agent 形狀的假信：
  - 放行：add ok-b（opus 定義）、add w（`code/kf-1114`）、add sol-1（ok-a 工作區底下的定義，用 envs 寫法）、sleep 和 wake sol-1（從表上認出是子 agent）、stop ok-b。daemon 都套上了。
  - 拒：def 在 lib、名字 eca_main、stop boss（受保護）、sleep _sweeper。寄件人收到 `GateRefused` 加理由。
  - 留：定義不認得、rm、名字不認得。boss 的 queue 收到 `kernel_hold` 通知；寫表態檔 pass 之後轉出去，refuse 之後寄件人收到 HoldRefused。
  - 抓到一個測試信自己的錯：exec 目標寫成 `../../repo`，實際解到 `home/repo`，跟 def 對不上。triage 把它留著，沒放行。
- 活樹規則的乾跑（`~/code/gate-1114/dry.py`，只讀活樹的 daemon 表）：上一封真的請求「掛 xiaosi」判 pass；stop ok-kf、sleep xiaosi 判 pass；ws 在 `/tmp`、ws 在 knowledge、def 在 lib、掛 repo-aos、停 eca_main、醒 llm-gpt 都判拒；rm ok-kf、名字不認得、ping、def 直接用 `templates/agent-fsm` 都判留。

## 活樹改了什麼

- 備份：`~/.aos/saves/tree-swap/gate-20261114-083348/`（整個 gate 夾，改之前抄的）。
- gate 夾 `~/aos-home/ws/.stack/procs/repo-aos/hooks/kernel_gate/`：
  - `kernel.json`：`{"hooks": {"triage": {"event": "after_verdict", "condition": "pass", "handler": "triage"}}}`（原本是 hold，handler 指向 `$AOS_HOME/lib/agent/kernel_gate/hold`）。
  - 新增 `triage`（repo 那支的抄本）和 `triage.json`。
  - 新增 `triage.jsonl`。第一行是實測信 `gate-1114-live-check`（stop _sweeper，判拒、沒轉寄）。
- 退回的方法：把備份裡的 `kernel.json` 抄回去（先寫暫存檔再改名）。triage 那幾個檔留著不影響。

## 換樹時要帶的檔

- `proto8/lib/agent/kernel_gate/triage`、`proto8/lib/agent/kernel_gate/tests/test_triage.py`（跟著 `lib` 一起抄就會帶到）。
- 換樹後可以把 gate 的 handler 改成 `{"$env": "AOS_HOME", "$path": "/lib/agent/kernel_gate/triage"}`，不再用 gate 夾裡的抄本。抄本要不要刪，由使用者決定。
- `triage.json` 是 repo-aos 自己 stack 裡的設定，換樹不會動到它。

## 留給 repo-aos 看的

- `*-1114` 只認今天的暫存樹，明天的 `-1115` 會被留著。要放寬就改 `triage.json`，例如寫 `~/code/*-11??`，改了立刻生效。
- 子 agent 的 def 直接用 `~/aos-home/templates/agent-fsm`（沒先 `agent_def new` 抄一份）會被留著。要放行就把它加進 `defs`。
- stop、start、sleep、wake 只要名字是 `ok-*` 就放行，不管是誰寄的。aos 本來就不驗寄件人。wf 07 同一天定了掛 agent 的命名規矩 `<eca名>-<角色>-<編號>`，所以 ok-* 掛的子 agent 名字也是 `ok-…` 開頭，靠名字就會放行；不照命名的，再靠 daemon 表上的 def 和 ws 認。
- 留著的信照舊只有 `kernel_hold` 通知。放行和拒掉的不通知，只記在 `triage.jsonl`。
- 沒有用真的 `aos-agent ctl` 從 ok-* 那邊走一遍。測試信是照 `py/daemon_ctl/entry.py` 的 `add_letter` 形狀手寫的。
- 知識庫 `aos/kernel.json#/gate` 還沒提到 triage。repo 裡那個檔別的線還沒 commit，這次沒碰。
