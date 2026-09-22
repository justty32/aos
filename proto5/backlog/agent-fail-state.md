# agent 的 fail 狀態

**問題**：引擎連敗 3 次後 agent 靠 waits 加一條 `continue.json`（consume）暫停。這是借「等檔案」來表達「我壞了、等人處理」，看 state.json 看不出來它是壞了還是在等別的東西。

**使用者提案（2026-09-22）**：考慮在 agent state 加 `fail`，或 state.json 新增一個 key 專門記這種狀況。

**為什麼現在不做**：consume 那條已經夠用；多一個狀態就多一組轉移要定。

**以後從哪下手**：`spec/agent.md` 的 state 三格、`spec/aos-agent.md` 的連敗那段。
