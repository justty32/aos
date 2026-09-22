# llm cpu payload 與結果（第 1 版）

← [proto5.1 README](../README.md)｜共用格式：[cpu-queue](cpu-queue.md)｜程式：[aos-llm-cpu](aos-llm-cpu.md)

CPU 身分 `_type`＝`llm_cpu`。資料夾、info 讀驗、共同 result 欄位、短鎖、認領與收屍均見共用規範。

## 1. 請求 payload

```json
{
  "engine": {"endpoint":"http://127.0.0.1:1234/v1","model":"qwen/qwen3-1.7b",
             "params":{},"api_key":null,"timeout_ms":120000,"cpu":"/absolute/cpu"},
  "body": {"model":"qwen/qwen3-1.7b","messages":[{"role":"user","content":"你好"}]},
  "result": "/absolute/agent/ask-result.json"
}
```

- engine 是 agent 已解好的物件，含 api_key；endpoint／model 必須是非空字串，params 若有必須是
  物件，api_key 允許字串或 null，timeout_ms 若有必須是正整數、預設 120000。不合為 `EngineInvalid`。
- body 是已組好的 chat/completions 物件；非物件為 `FieldTypeMismatch`。CPU 原樣交給
  `aos_llm_ask.call(engine, body)`，不重驗訊息與工具、不讀 agent、不解指示詞。
- engine 的 cpu 與額外欄位不加進 HTTP body。未知請求欄位忽略。
- 壞 payload 在認領前退 1、原檔留在原位；不猜 result 或自行刪除。原始請求含 api_key 保留於 done，
  本階段不遮罩、不加密、不清理。

## 2. 結果

成功：`{"ok":true,"message":{"role":"assistant","content":"你好"}}`，message 是
`choices[0].message` 原樣。失敗：`{"ok":false,"error":"原因"}`，包含 HTTP／網路／模型錯誤、
urllib 建 Request 時的 ValueError，以及共用層收屍。結果沒有 name／id。
