# aos-llm-ask：組一份模型請求（程式規範）

← [proto5.1 README](../README.md)｜資料格式：[agent.md](agent.md)｜送件：[aos-agent.md](aos-agent.md)｜HTTP：[aos-llm-cpu.md](aos-llm-cpu.md)

`aos-llm-ask [dir] [--dry-run]` 讀 agent 家、組 body，stdout 印一行 JSON 後退出。
dir 省略是 `.`；`--dry-run` 保留，但有沒有給都只印 body，不打 HTTP、不交 CPU 請求。

## 1. 讀驗與組 body

讀驗 `info.json`、人格、記憶與工具，格式及指示詞規則都在 [agent.md §3](agent.md)。
不讀 state、不寫檔、不跑工具。CPU 家由送件者驗，單純組 body 不需要啟動模型。

```json
{
  "messages": [
    {"role": "system", "content": "你是個簡潔、會用工具的助手。"},
    {"role": "user", "content": "看看資料夾裡有什麼"}
  ],
  "tools": [{"type": "function", "function": {"name": "sh", "parameters": {"type": "object"}}}],
  "temperature": 0.2
}
```

- 人格 content 非空時先加一則 system；後面原樣接記憶陣列。
- 工具照檔案順序合併，每個工具移除所有 `_` 開頭的頂層 key；空陣列不送 tools。
- engine.params 併進 body；其中 model／messages／tools／stream／cpu 忽略。
- body 不含 model。agent 將 engine.model 的代號放在 CPU 請求外層，CPU 查表後填真實 model 名。

## 2. 退出碼

| 碼 | 意思 |
|---|---|
| 0 | body 已印成一行 JSON |
| 1 | 讀驗錯誤；stderr 一行 `aos-llm-ask: <代號>: <白話>` |
| 2 | 用法錯，未知旗標或 dir 不是資料夾 |

## 3. 給程式用

```python
body = aos_llm_ask.build_request(dir_or_info, env=None)
```

可傳 agent 家路徑，或已由 `aos_agent_info.load` 讀驗的 info dict。
回 body dict，不碰網路、不寫 state 或記憶。沒有 `ask` 或 `request_from_info` 的同步呼叫入口。

`call(engine, body)` 留給 llm CPU：engine 是 CPU 已解好的 models 表中一筆，body 已填真名。
HTTP 呼叫、回應與錯誤的行為見 [aos-llm-cpu.md](aos-llm-cpu.md)。
