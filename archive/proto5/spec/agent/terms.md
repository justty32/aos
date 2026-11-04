← [agent](README.md)｜[spec 總導航](../README.md)

# 0. 名詞（白話）

| 詞 | 意思 |
|---|---|
| agent 家 | 這個資料夾。檔案裡寫的相對路徑一律從這裡算 |
| 記憶 | `info.history` 指的那份 OpenAI chat 訊息陣列；問模型時整份送、收回時整份寫 |
| 工具 | OpenAI `tools` 陣列的一個元素，多一格 `_meta`（一份 inst）說被叫到時跑什麼 |
| 門（`waits`） | 外人要 agent 停下來等的表；表裡還有沒到的檔，這一格就不走 |
| 當批（`batch`） | 一次送出去、要一起收回的工作：`think` 是一則問模型，`act` 是同一則 assistant 的全部 tool_calls |
| 工作名 | 一件送去 kernel 的工作的名字，同時是 kernel 行程名、request 檔名（加 `.json`）、`work/` 裡的檔名開頭（[aos-agent.md §0](../aos-agent/terms.md)） |
| 池（`pool`） | kernel 的 cpu 分組標籤；工作派往標籤相同的某顆工作 cpu（[kernel.md §1.1](../kernel/home.md)） |
