# 小念頭：一件事，只拿結論

工具 `thought` 起一隻用完即走的子 agent，交給它一件事，只帶回短結論；子的工具來回不進你的 history。子定義取呼叫參數 `from`，沒填才用工具登記格 `env.AOS_THOUGHT_FROM` 的預設。

怎麼選：

- `thought`：計畫的一步、查完回一句話。答完預設收掉，不用命名、追問或自己移除。
- `agents`：要持續對話的助手。自己命名、問它，也要自己 `rm`。

呼叫：

- 已配預設：`{"goal": "Find what time it is and say whether it is morning"}`。
- 換定義：`{"from": "helpers/reviewer", "goal": "Review the result and return one sentence"}`。
- 借自己的工具：`{"goal": "Read the knowledge base and summarize endpoint packs", "tools": [{"name": "memory"}], "max_chars": 200}`。
- A → B → C：每步叫一次，把前一步結論放 `context`，例如 `"context": ["Step A concluded: the config is in cfg/"]`。

規則：

- 預設放這隻 agent 工具設定的 thought 登記格，例如 `{"path": "../../lib/agent/thought", "env": {"AOS_THOUGHT_FROM": "helpers/basic"}}`。也可在登記工具時用 `--envs AOS_THOUGHT_FROM=helpers/basic`。env 值照字面傳入，不相對登記檔解析；`from` 與這個預設都相對你的工作區 `$AOS_WS` 解析，絕對路徑照用；要能搬家請存相對路徑。定義必須宣告 `aos-agent` 公開介面。兩邊都沒給＝`FromMissing`，不猜範本。明填空白／錯型別＝`ArgumentsBad`，不退回預設。
- 子在定義原有設定之上收到 `goal` 與 `context`。在 `goal` 說清楚要帶回什麼。
- 工具：沒給 `tools`＝保留定義的工具組；`[]`＝清空；列出來＝只留這些。`{"name": "memory"}` 沒給 `path`＝借你自己的同名工具；給了 `path` 就用該路徑。覆蓋層依定義的 `interfaces.json` 宣告。
- 腦：預設同你，`endpoint` 可指定另一包。讀不到你的腦設定（例如沙箱看不到定義）＝報錯，常見 `InterfaceMissing`；可明給 `endpoint`。
- 深度讀啟動環境 `AOS_THOUGHT_DEPTH`（沒設＝0），起子帶父深度＋1。到 2 再叫＝`DepthExceeded`。
- `keep: true`＝答完停住並保留，結論尾加 `details: procs/<name>/`（相對 daemon）。要追問先 `aos-agent ctl start --target <name>`，再 `say`／`listen`。
- `AnswerMissing`＝`timeout_s` 內沒答（預設 600，任何有限正數），錯誤行尾有 `(details: ...)`，stack 留給人查。`DepthExceeded`＝到深度上限，這步自己做。`ToolMissing`＝你沒有要借的同名工具。`ArgumentsBad`＝`goal` 沒給／空白，或參數無效。`DaemonMissing`＝沒 daemon，或它忙、暫停、掛了而沒回；這步自己做或說明暫時不可用，之後最多再試一次，不要迴圈重試。
