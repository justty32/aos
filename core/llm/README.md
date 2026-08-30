# llm — OpenAI 相容的文字補全 client

`core/llm` 提供 `aos::llm` 函式庫與 `aos llm` 子命令。它用 libcurl 對 OpenAI 相容
端點送出非串流 `POST <base>/chat/completions`，並印出
`choices[0].message.content`。它不會載入或卸載模型。

預設 endpoint 是 `http://localhost:1234/v1`，預設模型是
`qwen/qwen3.5-9b`。可分別用 `AOS_LLM_URL`、`AOS_LLM_MODEL` 覆蓋；若有
`AOS_LLM_KEY`，請求會帶 `Authorization: Bearer ...`。

## 使用方式

```bash
echo '只回一個字：好' | aos llm
echo 'hello' | aos llm --system 'Answer briefly.'
aos llm --messages messages.json
aos llm --url http://localhost:1234/v1 --model qwen/qwen3.5-9b
```

`--messages` 接受 OpenAI messages 陣列，例如：

```json
[
  {"role": "system", "content": "Answer briefly."},
  {"role": "user", "content": "hello"}
]
```

連線、HTTP、JSON 或回應格式錯誤會在 stderr 印出原因並回傳 exit code 1。預設 timeout
為 120000 ms，可用 `--timeout-ms` 覆蓋。
