← [agent](README.md)｜[spec 總導航](../README.md)

# 2. 指示詞：`info.json`／`state.json` 解，被指到的檔不解

- `info.json` 每次讀都解指示詞（含 `_metainfo`），中心是 agent 家，`$env` 讀跑那支程式自己的環境。**頂層與 `llm` 那格必須是字面物件**（不是＝`FieldTypeMismatch`；各欄位的值可以是指示詞），
  這樣 `aos-llm call` 才能只挑自己要的欄位解。
- `state.json` 只有 `input` 那格解指示詞；`waits` 每條照樣解（中心 agent 家），但 `waits` 本身在原始 JSON 要是字面單條或字面陣列；
  其他格（`state`、`errors`、`batch`、`intake`、`consuming`、`sweep`）必須是字面值，寫了指示詞＝`FieldTypeMismatch`。
  程式改寫 `state.json` 時只改自己那幾格，`input` 原樣抄回；頂層整份不能是指示詞。
- 人格、記憶、工具檔、輸入、回音檔、`work/` 的檔**原樣讀、不解**。
- 工具 `_meta` 裡的指示詞由 aos-agent 送件時解掉（[aos-agent.md §5.3](../aos-agent/send.md)），用的是**跑 aos-agent 那顆 cpu** 的環境。
- **兩邊都讀的欄位**：`aos-llm call` 只解驗 `_metainfo`、`system`、`history`、`tools`、`llm.model`、`llm.params` 這六格（[aos-llm.md §3](../aos-llm/request.md)），
  其他格（`tick`、`tool_pool`、`llm.pool`、`llm.timeout_ms`…）它不碰，用 `$env` 只要 agent 那顆 cpu 有就行。
  這六格若用 `$env`，**兩顆 cpu 都得有那個變數、而且值相同**——少一邊就問不了模型，值不同會記憶寫一份、問模型讀另一份。建議這六格不用 `$env`。
