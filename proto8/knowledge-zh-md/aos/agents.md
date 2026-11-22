# `knowledge/aos/agents.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/agents.md`，跟到正本 commit `76381cb2a`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/agents.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

**`#/Other agents: which tool`**

# 其他 agent：用哪個工具

- 一個你可以跟它講話、之後改它、移除它的幫手：`subagent`（見 `aos/agents/subagent.md`）。
- 啟動、停止或列出 daemon 上的任何 agent，但不把它變成你的：`agents_ctl`（見 `aos/agents.md#/Any agent on the table: agents_ctl`）。
- 一件需要你已經知道的東西、只要結論回來的旁支工作：`fork`（只限 agent-fsm；見 `aos/agents/fork.md`）。這三個在 `subagent` 工具包裡，而沒有任何內建範本有這個工具包（agent-fsm 或 eca 都沒有）；eca 用它自己 CLI 內建的幫手。定義可以加上這個工具包（見 `aos/packs.md`）；加了之後在 eca 上你就有 subagent 和 agents_ctl（fork 仍然用 `BodyUnsupported` 拒絕 eca 身體）。`self_state` 加上 part `tools` 會顯示你有哪些。
- 一種新的 agent：用 `agent_def` 抄一份範本（工具包 def：沒有任何內建範本有，agent-fsm 或 eca 都沒有；先用 `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/agent_def"}}` 加上它），用你的檔案工具改這份複本，再用 `subagent` 啟動它（見 `aos/agents.md#/New definitions: agent_def`）。

子 agent 跟你跑在同一個 daemon 上。它不繼承你的腦或你的工具：那些來自它自己的定義。

**`#/Any agent on the table: agents_ctl`**

# 表上的任何 agent：agents_ctl

工具 `agents_ctl` 就是 `aos-agent ctl`，可用在你 daemon 表上的任何 agent，不只是你的。它不留紀錄，也沒有配額；一次呼叫成不成，看你的權限和 daemon。它不能跟 agent 講話，也不能改它的工具或腦：要那樣，請用 `subagent` 啟動那個 agent。

一次呼叫一個 op（鍵就是 ctl 的旗標）：

- `{"op": "ls"}`（每個 agent 一行：NAME STATE WORKSPACE QUEUED REASON；`"long": true` 加上健康欄位；`"json": true` = 每個欄位都用 JSON）
- `{"op": "state", "name": "worker"}`
- `{"op": "add", "def": "defs/helper", "name": "worker", "ws": "work"}`（鍵跟 `subagent` add 一樣，`aos/agents/subagent.md#/subagent add: more options`；之後這個 agent 不是你的）
- `{"op": "stop", "name": "worker"}`（這一輪之後；`start` = 再跑）
- `{"op": "sleep", "name": "worker"}`（立刻；`wake` = 回來）；`pause` / `resume` = 暫停 / 繼續
- `{"op": "rm", "name": "worker"}`（保留它的 stack；`"purge": true` 會刪掉）
- `{"op": "stop", "name": "<you>", "no_wait": true}`（停掉你自己：daemon，或它前面的 kernel，一收下請求就回來；你在這一步結束時停。`no_wait` 可用在 `stop`、`sleep`、`pause` 和 `rm`；沒有它的話，停掉你自己會等這一步本身結束，結果撞上 `timeout_s`）
- `{"op": "where", "name": "worker", "what": "ws"}`（它的工作區；預設：它的 stack）
- `{"op": "who"}`（你是哪個 agent）

規則：

- 相對路徑從你的工作區開始。
- 它對不是你的 agent 也有效，包括 `rm`，只要你的權限夠。如果你在這裡移除你自己的某個子 agent，`subagent` 下次被呼叫時會忘掉它，名額也會空出來。
- `InstanceMissing`：表上沒有這個名字；先 `ls`。`InstanceExists`：名字被用掉了；換一個。`AddRejected`：daemon 拒絕了，常常是因為滿了。`InterfaceMissing`：那個資料夾不是 agent 定義（它的 `interfaces.json` 沒有宣告 `aos-agent`）。`PhaseBad`：那個 op 的 phase 不對（例如對睡著的 agent 用 `start`：要用 `wake`）；先跑 `state`。`DaemonMissing`：你不是跑在 daemon 底下；照實說。
- 有設 `$AOS_KERNEL` 時，stop、sleep、start 和 wake 會先經過那個 kernel。如果它拒絕，錯誤行是 `CtlRejected`，kernel 自己的代號和理由接在訊息後面（例如 `CtlRejected the stop letter was refused: HoldRefused <reason>`）。拒絕是一個決定：讀理由，不要只是把同一個請求再送一次。

**`#/New definitions: agent_def`**

# 新的定義：agent_def

工具 `agent_def` 做 agent 定義。定義是一個資料夾（`system.txt`、`tools.json`、`llm.json`、`interfaces.json`，……；每個檔案做什麼：`aos/definition.md`）；一種新的 agent = 一份範本的複本，改過。

一次呼叫一個 op：

- 抄一份內建範本：`{"op": "new", "template": "agent-fsm", "path": "defs/helper"}`（`template` = `$AOS_HOME/templates` 底下某個資料夾的名字；內建的 agent 範本：`agent-fsm`、`eca-claude`、`eca-pi`、`reviewer`；名字錯是 `DefMissing`，理由會列出那裡有的範本）
- 抄任何其他定義夾：`{"op": "new", "from": "defs/helper", "path": "defs/helper2"}`
- 檢查：`{"op": "check", "path": "defs/helper"}`（印出 `{"problems": [...]}`；空清單 = 沒問題。資料夾裡指向不存在東西的連結（被移走或刪掉的 `defs.extern` 目標）算一個問題，那個定義的其他檢查要等它修好才做。除了檔案，它還檢查每個工具路徑、以及 states、loop 和 hooks 要跑的每個程式都存在，還有腦的設定型別對（`temperature: "hot"` 是問題）；它在這裡沒辦法檢查的，像沒設的變數，放在 `"warnings"`。它不檢查模型名稱。用 `agent.py --compile` 編譯完全不做這些檢查：編譯後要跑 check）
- 改它的工具：`{"op": "tools", "path": "defs/helper", "args": {"op": "add", "path": "tools/math"}}`（`args` = `self_tools` 收的東西：ls、get、add、rm）
- 改它的腦設定：`{"op": "llm", "path": "defs/helper", "args": {"op": "set", "settings": {"model": "fake"}}}`（`args` = `self_llm` 收的東西：ls、set、rm）
- 改它的系統文字：`{"op": "system", "path": "defs/helper", "args": {"op": "set", "text": "You are ..."}}`（`args` = `self_system` 收的東西：get、set）

步驟：

1. 從範本 `new`。
2. 用 op `tools` / `llm` / `system` 改這份複本（沒有 reset），或用你平常的檔案工具改：`system.txt`（它是誰）、`tools.json`（它的工具）、`llm.json`（它的腦，像 `{"model": "fake"}`）。
3. `check` 它。
4. 啟動它：`subagent` `{"op": "add", "def": "defs/helper", "name": "helper"}`（你的），或 `agents_ctl` add（不是你的）。

規則：

- `new` 只抄，什麼都不啟動。複本就是資料夾原樣，像 `cp -r`：裡面的路徑一個都不改。`_metainfo.json` 也照抄，不動。所以指向資料夾裡某個檔案的相對路徑（`fn/add.py`）指的是複本自己的檔案；會走出資料夾的（`../shared/x`）現在從新位置算起，可能指到別的地方。
- `path` 必須還不存在；它可以在任何你能寫的地方。相對路徑從你的工作區開始。
- `DefExists`：換一個 `path`。`DefMissing`：那個資料夾（`from`，或 check 的 `path`）不在。`DirectiveBad`：`{"$env": ...}` 解不出來（變數沒設）。`DefBad`：check 找到問題；修好它點名的檔案再檢查一次。
- 改定義會影響每個用它的 agent。只想改一個 agent，就對你的子 agent 用 `subagent` tools / llm，或對你自己用 `self_tools` / `self_llm`。
