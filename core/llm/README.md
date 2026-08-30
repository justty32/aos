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
為 120000 ms，可用 `--timeout-ms` 覆蓋。若端點回應 JSON 的 `model` 與要求的
`--model`／`AOS_LLM_MODEL` 不同，回覆文字仍會照常印到 stdout，但 stderr 會列出要求與
實際模型並回 1。`-h`／`--help` 會把完整用法印到 stdout、回 0，不讀 stdin 或呼叫端點。

函式庫的 `parse_response_model()` 可抽出回應 JSON 的 `model`；`complete()` 最後一個
可省略的 `served_model` 出參會回填端點實際模型，既有呼叫端不必修改。

## 並行上限與排隊

多個行程共用同一顆 LLM 端點時，槽層會保證同時執行的呼叫不超過使用者設定的
數量。使用者層的 `<AOS_HOME>/cpus.json` 是權威設定；未設定 `AOS_HOME` 時，
預設位置是 `~/.aos/cpus.json`。世界層 `<world>/.aos/llm.json` 使用相同格式，
但 `max_inflight` 只能把使用者層的上限往下限（兩者取較小值），無權替使用者層
未設定的 CPU 開啟上限；世界層的 `wait_ms` 則可直接覆蓋使用者層。沒有設定上限
代表不限，呼叫完全不取槽。建議 `lmstudio` 設為 1、`deepseek` 設為 3：

```json
{
  "lmstudio": {"max_inflight": 1, "wait_ms": 60000},
  "deepseek": {"max_inflight": 3, "wait_ms": 60000}
}
```

槽檔位於 `<AOS_HOME>/slots/<cpu>/`，以 `flock` 實作；持有槽的行程死亡時，
核心會自動釋放鎖。`--engine <cpu>` 選擇端點使用的槽名，預設讀
`AOS_LLM_ENGINE`，再否則為 `lmstudio`；`--priority <int>` 設定排隊優先度，
數字越大越優先，預設讀 `AOS_LLM_PRIORITY`，再否則為 0。`--slots` 只顯示各顆
CPU 的目前佔用與等待狀態，不讀 stdin，也不呼叫端點。

等待超過 `wait_ms`（預設 60000）時，stderr 只會印一行 `waiting-llm`，並以
75（`EX_TEMPFAIL`）退出。這不算失敗，呼叫者可在下回合再試。

```bash
mkdir -p ~/.aos
echo '{"lmstudio": {"max_inflight": 1, "wait_ms": 2000}}' > ~/.aos/cpus.json
echo hi | aos llm --engine lmstudio --priority 5
aos llm --slots
```
