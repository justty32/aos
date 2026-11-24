核心程式位子 11-24 三件只讀調查的報告：fsm 腦失敗的 cooldown、aos 起的 Claude Code 帶不到專案層 mcpServers、閒置輪詢的實際成本（eca-aos 11-24 派，線 eca-aos-core-1124；沒改 proto8）。

# 11-24 三件只讀調查

← [我的地盤](README.md)｜[筆記](notes.md)

看的是 main `2d262f921` 的程式。量測用的腳本、原始數據都在 `~/.aos/scratch/eca-aos-core-1124/`（`sample.py`、`analyze.py`、`names.py`、`startup.sh`、`sample1.json`、`sample2.json`、`mcp/`）。下文的「檔:行」指 proto8 底下。

## 1. fsm 腦失敗的 cooldown

### 現況

- **怎麼長**：`py/aos/agentlib/cooldown.py` 的 `STEPS_S = (30, 60, 120, 240, 480, 900, 1800)`，第 n 次失敗等第 n 格，第 7 次起固定 1800 秒；成功一次就刪檔歸零。ops 說「失敗 6 次後排到 900 秒」，對得上第 6 格。這張表 eca（`aos-eca-turn`）與 fsm（`lib/aos/apps/agent_fsm/wait.py`）共用。
- **上限在哪設**：兩處寫死，沒有設定可調：
  - `cooldown.py` 那張表的最後一格；
  - `wait.py` 約 585 行，BrainFailed 而 `retry: true` 時算 `wait_s = min(1800, max(step_s, retry_after_s))`。
- **端點沒在聽時走哪條**：`py/tools/base/llm_http/_entry` 約 219～227 行。
  - 連線被拒（OSError）回 `EndpointFailed`、`retry: true`，msg 是 `cannot connect to <url>: [Errno 111] Connection refused`。
  - 連線逾時（TimeoutError）同樣是 `EndpointFailed`、`retry: true`，msg 是 `timed out connecting to ...`。
  - llm kernel 把這個錯誤物件整個原樣轉給 agent（`py/tools/aos/kernel_llm/llm_rules.py` 的 `reply_of`）。wait.py 收到時當 BrainFailed 的暫時錯：照階梯冷卻，次數不限，重送同一份請求。
- **能不能分錯誤種類**：現在只能分 `code`（全是 `EndpointFailed`）與有沒有 `status`（有 HTTP 回應才有）。「連不上」與「連線逾時」只差在 msg 文字，沒有結構化的欄位。
  - 好消息：kernel 原樣轉交，llm_http 在 error 裡多加一格（例 `"phase": "connect"`），wait.py 就讀得到，中間不用改。
  - 注意：這台 WSL 是 mirrored 網路，連 127.0.0.1 上沒人聽的 port 不會被拒，要等連線逾時（llm_http 預設 10 秒；dev-env/01 第 19 行，`2d262f921` 剛記的）。所以在這台，「拒絕」跟「逾時」分不開，兩種都要當「端點沒在聽」。
- **現在怎麼清 cooldown**（讀程式得到的，沒實測）：
  - **改腦設定**（`aos-agent llm set`、`self_llm`、`subagent` 的 llm set）：wait.py 約 446～454 行，寄之前發現 `model` 或調整鍵跟 `request.json` 對不上，就清掉 `BudgetMissing`／`BrainFailed` 的冷卻，回 think 重組。**只在值真的變了才清**；設成跟原本一樣的值，`request.json` 對得上，不會清。ops 說「只有 subagent llm set 會清」，大致對，但要加這個條件。
  - **手刪 `$AOS_STACK/cooldown.json`**：wait.py 每拍重讀，刪了下一拍就寄。沒有任何指令做這件事。
  - `SendFailed` 而且當時 kernel 資料夾不在：kernel 一出現就當作冷卻到了（wait.py 約 463 行），這是唯一「提早接回」的路，只適用 kernel 不在、不適用端點不在。
  - **重起不會清**：冷卻檔在 stack 裡，起來先等完（brain_notify 的「stopped」信也這樣寫）。
- **「no action is needed」在哪**：`py/tools/agent/brain_notify/_entry` 約 141～153 行，是 brain_failed 這個 hook 的處理程式。
  - 什麼時候寄：BrainFailed 的事件帶 `retry: true` 時，第 1 次只記一筆，第 3 次寄一封 BLOCKED，同一串只寄一次。
  - 信的內容：寫死「It has tried N times and keeps retrying by itself; no action is needed. To stop it, use stop.」，不分錯誤種類，也不寫下次什麼時候重試。
  - 其實寫得出時刻：wait.py 傳給 hook 的事件已經帶了 `wait_s`（`extra`），brain_notify 沒用它。
  - 知識庫 `knowledge/aos/brain.md` 第 26 行也描述這個行為。

### 改法選項（只列，不推薦）

| 選項 | 做什麼 | 要改的檔 | 牽動的測試 |
|---|---|---|---|
| A 分錯誤種類的上限 | llm_http 的錯多一格（例 `phase`: connect／read／http），wait.py 遇到「連不上」用較短的上限（例 60 秒），其他照舊 | `py/tools/base/llm_http/_entry`（錯誤物件加欄）、`lib/aos/apps/agent_fsm/wait.py`（算 wait_s 那段）、`py/aos/agentlib/cooldown.py`（`fail` 收上限，或表外另給）；kernel 不用改 | `py/tools/base/llm_http/tests/test_llm_http.py`（錯誤形狀）、`templates/tests/agent-fsm/test_cooldown.py`（約 186～191 行的上限案例）、`test_hooks.py`、`test_selfheal.py` |
| B 冷卻中探端點 | 冷卻期間便宜地看端點活了沒，活了就當作到了 | wait.py 不知道端點位址（包在 kernel 那邊），要嘛 kernel 公布端點健康（新檔或新信），wait.py 讀；要嘛加一種「探」的信。動 `py/tools/aos/kernel_llm/`、`py/aos/apps/` 的 aos-llm（若加信種）、wait.py | kernel_llm 的 tests、test_cooldown.py、`py/tests/apps/agent/test_listen_brain_failure.py` |
| C 給上層「立刻重試」 | 一個指令或工具動作，刪掉那隻的 cooldown.json（`cooldown.clear` 已有） | `py/aos/apps/agent/`（新子命令，例 `aos-agent ctl retry`）、`py/tools/agent/subagent`、`agents_ctl`、`self_*`（要不要加 op）、知識庫 | `py/tests/apps/agent/`（新測試）、subagent／agents_ctl 的 tests |
| D 改措辭、附下次重試時刻 | brain_notify 用事件的 `wait_s` 算出本機時刻；`EndpointFailed`（或 A 的 phase＝connect）改寫成「端點沒回應，要人看一下；下次 HH:MM 重試」，拿掉 no action is needed | `py/tools/agent/brain_notify/_entry`；知識庫 `aos/brain.md` 第 26 行 | `templates/tests/agent-fsm/test_brain_notify.py`（有斷言舊句子） |

- **歸誰**：wait.py 與 `templates/tests/` 歸範本位子；llm_http、cooldown.py、brain_notify、aos-agent 歸核心程式；知識庫歸 kb。
- **共用的影響**：cooldown.py 的表 eca 也用，改表會同時改 eca 的重試節奏。

## 2. aos 起的 Claude Code 帶不到 `~/.claude.json` 的專案層 mcpServers

### 原因（暫存設定實測過）

- **主因是 `--strict-mcp-config`**，不是 `--setting-sources project,local`。
  - 範本 `templates/agents/eca-claude/cli.json` 的 flags 兩個都帶；aos 另外經 `py/aos/agentlib/cli_mcp.py`（約 196～200 行）加 `--mcp-config <小格的 mcp.json>`，裡面只有 aos 自己那台。
  - `claude --help` 寫明 `--strict-mcp-config`「Only use MCP servers from --mcp-config, ignoring all other MCP configurations」。
- **專案層 mcpServers 實際存在哪**：`claude mcp add` 預設的 local 範圍，存在**設定資料夾**的 `.claude.json` 的 `projects["<專案的絕對路徑>"].mcpServers`。
  - 設定資料夾＝`$CLAUDE_CONFIG_DIR`，沒設才是 `~`。這棵樹的 eca 帶 `CLAUDE_CONFIG_DIR=~/.claude-alt`。
  - 鍵名查過（只看鍵名）：`~/.claude.json` 有 `projects["/mnt/c/code/guanyu/ops-notes"].mcpServers.teamsite`；`~/.claude-alt/.claude.json` 一個也沒有；兩份頂層的 `mcpServers` 都是空的。
- **實測**：在暫存設定做的，`CLAUDE_CONFIG_DIR` 指暫存夾，假的 `.claude.json` 給暫存專案登記一支探針 MCP。探針起來就留一個記號；MCP 在檢查登入之前就起了，所以沒登入也測得出來，沒叫到模型。
  - 什麼旗標都不帶：local 的探針有起。
  - 只帶 `--setting-sources project,local`：有起。所以這個旗標不擋 local 範圍。
  - 帶 `--strict-mcp-config --mcp-config <檔>`：只有檔裡那支起，local 的沒起。
  - 只帶 `--mcp-config <檔>`、不帶 strict：兩支都起。
  - 帶 strict，再把同一份 server 用第二個 `--mcp-config`（JSON 字串）給：有起。
  - cwd 換成專案的子夾（不是 git repo）：local 的沒起。local 範圍**只認完全相同的 cwd**。
- **還有兩個條件**，就算拿掉 strict 也要對上：
  - aos 起 claude 時的 `CLAUDE_CONFIG_DIR`，要指到有那筆登記的那份 `.claude.json`。
  - claude 的 cwd（agent 的 ws）要等於登記的路徑。ps 上 ops 的 aos-mcp 帶 `--ws /mnt/c/code/guanyu/ops-notes`，跟登記的鍵一樣。
  - ops 那幾支 claude 帶的是哪個 `CLAUDE_CONFIG_DIR`，我沒查（不讀別人的 /proc/*/environ）。

### 能帶進去的辦法（只列，不推薦）

1. **定義的 cli.json 的 flags 多加一組 `"--mcp-config", "<檔>"`**，檔裡放 `{"mcpServers": {...}}`。
   - 跟 strict 並存，實測可行；`cli_cfg.py` 第 13 行寫明 `--mcp-config` 可重複、不擋。
   - 要注意：server 設定若帶 token，抄進檔就是把秘密放進定義夾或 ws。
2. **拿掉那個定義的 `--strict-mcp-config`**：local、project（`.mcp.json`，要先核准）、user 範圍的 server 全會進來，不只想要的那支。還要符合上面兩個條件。
3. **aos 這邊加一鍵**（例 cli.json 的 `mcp_servers`，或 `mcp_config` 指一份檔）：由 `cli_mcp.py` 併進小格的 mcp.json。要改 `py/aos/agentlib/cli_mcp.py`、`cli_cfg.py`，範本文件與測試（`py/tests/test_cli_*`）也要跟。

## 3. 閒置輪詢的實際成本（活樹上只讀量）

### 怎麼量的

- **每隻每秒在格子上花多少 CPU**：讀每支 `aos-loop` 的 `/proc/<pid>/stat` 的 `cutime+cstime`（它收掉的子孫用掉的 CPU 都累加在這裡），頭尾各讀一次。這個數字是準的。
- **起了哪些行程、各活多久**：每 5 ms 掃一次 /proc，抓新出現的行程，沿 ppid 往上歸給起它的 loop。wall＝看得到它的時間，CPU 取最後一次讀到的，都略低估。
- **哪支 loop 是哪隻**：用 daemon 表上每列的 pid 對。
- **全系統**：`/proc/stat` 的 cpu 那行與 `processes`（fork 總數）。
- 兩份各 60 秒（11-24 上午 10:15～10:21 之間，本機時間）。
- 取樣器自己用掉約 0.2 核，已經不算在下面各隻裡，但全系統的數字包含它。
- 只讀 `/proc/<pid>/{stat,cmdline,cwd}`、daemon 表、loop.json，沒讀 history、信箱、environ，沒起停任何東西。
- 這台沒有 perf、pidstat、bpftrace，只有 vmstat。

### 量到的

- **全系統**：8 核在取樣時全滿（忙 7.8～8.0 核），load 15～24。user 77～78%、system 18～19%、softirq 2～3%，閒置 0～3%。整台每秒 fork 74～108 支。當時 eca-aos-templates 在跑 g++（三分切換的建置），mine_arena/dev、mine_mecha/main 在問腦，我自己在跑一輪；這些都算忙，不算進「閒著」。
- **每種 agent 閒著時的一拍**：都是 interval 300 ms，一拍跑完再等 300 ms。

| 種類 | 一拍起什麼 | 每支 CPU | 每支 wall（機器滿載下） | 每隻每秒幾拍 | 每隻佔幾核 |
|---|---|---|---|---|---|
| eca（閒著，8～9 隻） | 1 支 `python3 aos-eca-turn --on-empty idle` | 170～200 ms | 300～600 ms | 1.2～1.7 | 0.23～0.29 |
| agent-fsm（閒在 idle，7 隻） | `aos-fsm`（C++）＋`python3 idle.py`，偶有 `aos-directive` | idle.py 120～140 ms；aos-fsm 不到 1 ms | 250～500 ms | 1.4～1.6 | 0.19～0.24 |
| llm kernel（1 台） | llm daemon 每拍起一支 run-once 的 `python3 kernel_llm/_entry` | 約 190 ms | — | 1.28 | 約 0.24（含少數真的請求） |
| `_clock`（1 隻） | 每秒 1 支 `python3 aos-clock` | 70～80 ms | 150～210 ms | 0.8 | 0.07 |
| `_sweeper`（8 隻） | interval 600 秒 | — | — | — | ≈0 |
| aos-daemon（21 支）、aos-loop 本身 | C++，自己不起 python | — | — | — | 合計約 0.03 |

- **context_wrap**：掛 on_clock 的 hook `python3 lib/tools/agent/context_wrap/_entry`，整棵樹每秒約 2.3 支、每支約 100 ms，約 0.23 核，算在上表 eca／fsm 的數字裡。
- **每隻每秒起幾支行程**：eca 閒著約 1.2～1.7 支，fsm 閒著約 2.4～3.2 支。
- **整棵樹合計**：閒著的 eca 約 9×0.27≈2.4 核，閒著的 fsm 約 7×0.22≈1.6 核，kernel 約 0.25，`_clock` 0.07。**閒置輪詢合計約 4.3 核，是這台 8 核的一半多。**
- **一拍的錢花在哪**：起動與 import。同一台、同一時段量 20 次的平均（`startup.sh`）：

| 指令 | CPU | 其中 sys |
|---|---|---|
| `python3 -c pass` | 41 ms | 7 ms |
| `python3 -I -S -c pass` | 23 ms | — |
| `python3 -c 'import json, subprocess'` | 68 ms | — |
| `aos-eca-turn --help` | 200 ms | 44 ms |
| `idle.py --help` | 146 ms | 34 ms |
| `aos-fsm --help` | 1.2 ms | — |
| `/bin/true` | 0.9 ms | — |

  `--help` 的 CPU 跟閒著一拍幾乎一樣，所以一拍的成本幾乎全是 Python 起動加 import，真的「看 queue 有沒有信」那點事很便宜。
- **sy 的比例**：python 起動裡 sys 約佔 20%，跟全系統 system 18～19% 的比例接近。這支持「system 那份多半來自不停 fork、exec、載入 Python」，但我沒有直接量 sys 的來源，這是推論。

### 估算（照上面的數，只算閒著的那些）

- **interval 拉到 N 秒**：每拍間隔≈N＋一拍的 wall（取 0.3 秒）。每秒拍數與閒置輪詢的合計（現在約 4.3 核）照比例縮：

| N | 每隻每秒拍數 | 是現在的 | 合計約 |
|---|---|---|---|
| 0.3 秒（現在） | 1.67 | 100% | 4.3 核 |
| 1 秒 | 0.77 | 46% | 2.0 核 |
| 2 秒 | 0.43 | 26% | 1.1 核 |
| 5 秒 | 0.19 | 11% | 0.5 核 |
| 10 秒 | 0.10 | 6% | 0.25 核 |

  代價：閒著的 agent 最晚要 N 秒才看到新信。kernel 的 interval 另外算：kernel 慢了，等於每封信都慢。
- **idle 不起 python**：「queue 空就什麼都不做」那一步改在 C++ 判斷（aos-fsm／aos-loop 那層，或 aos-eca-turn 起動前先看 queue），一拍從 120～200 ms 降到約 1～2 ms（量到的 `aos-fsm` 一支約 1 ms）。
  - 閒著的 eca 9 隻：省約 2.4 核。
  - fsm 7 隻：省約 1.5 核。
  - kernel 若也照做（`requests/new` 空就不起 kernel_llm）：再省約 0.24 核。
  - 三樣合計：省約 4 核，剩不到 0.1 核。
  - context_wrap 這類 on_clock 的 hook 另外算，約 0.23 核，它跟著 `_clock` 的節奏走，不受 interval 影響。
- **量法本身的偏差**：
  - 這次機器滿載，一拍的 wall 被拉長，每秒拍數因此變少。機器閒的時候一拍更快，每秒拍數更多，閒置輪詢的成本反而會**更高**。
  - 反過來，滿載時一支行程的 CPU 可能略高於閒時（快取競爭），沒另外量。

### 候選方向（列出來，不推薦）

- 閒著的 agent 拉長 interval（固定值，或閒越久拉越長）。
- idle 判斷搬到 C++，不起 python（aos-fsm 的 idle 格、aos-eca-turn 前面先看 queue、kernel 前面先看 requests）。
- 事件喚醒：daemon 或 loop 用 inotify 之類看 queue／requests，有信才起格，沒信不輪詢。
- 降低每次起 python 的成本：`-S`、少 import、延後 import。量到 `-I -S` 比預設省約 18 ms；離 120～200 ms 還差很遠，主要的錢在 aos 自己的 import。
- on_clock hook（context_wrap）改成不必每次起 python，或拉長 `_clock` 對它的節奏。
