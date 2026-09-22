# llm CPU 家、請求與結果（格式規範）

← [proto5.1 README](../README.md)｜共用格式：[cpu-queue](cpu-queue.md)｜程式：[aos-llm-cpu](aos-llm-cpu.md)

## 1. info.json

```json
{
  "_metainfo": {"_type": "llm_cpu", "_version": 1},
  "models": {
    "small": {
      "endpoint": "http://127.0.0.1:1234/v1",
      "model": "qwen/qwen3-1.7b",
      "api_key": null,
      "timeout_ms": 120000
    }
  }
}
```

身分與資料夾見 [cpu-queue](cpu-queue.md)。models 必填且是物件；每個 key 是非空模型代號、值是物件。
值裡 endpoint／model 必填且是非空字串；api_key 可省、字串或 null，預設 null；timeout_ms 可省、
正整數且 bool 不算，預設 120000。模型設定不合法為 `EngineInvalid`。

info 在 CPU 讀取時解指示詞，中心是 CPU 家；models 整格、每筆與各值都可解，api_key 可用
`{"$env":"LMSTUDIO_KEY"}`，環境來自 CPU，變數不存在就讀驗失敗。代號是表的 key，不另做替換。

## 2. 請求 payload

```json
{
  "model": "small",
  "body": {"messages": [{"role": "user", "content": "你好"}], "temperature": 0.2},
  "result": "/absolute/agent/ask-result.json"
}
```

model 是非空代號字串，缺失或型別不對為 `EngineInvalid`；body 是已組好的 chat/completions 物件，
缺失或不是物件為 `FieldTypeMismatch`；result 照共用格式為絕對路徑。
agent 不填 body.model，CPU 查表後填真名；請求不帶 endpoint、api_key 或 timeout_ms。
CPU 不讀 agent、不重驗 body 裡訊息與工具、不解請求指示詞，未知請求欄位忽略。

壞 payload 在認領前退 1、原檔保留。格式合法但代號不在 models 表裡，認領後寫
`{"ok":false,"error":"不認識的模型代號"}` 並搬 done，不送 HTTP。

## 3. 結果

成功：`{"ok":true,"message":{"role":"assistant","content":"你好"}}`，message 是
`choices[0].message` 原樣。失敗：`{"ok":false,"error":"原因"}`，包含未知模型代號、HTTP／網路／
模型錯誤、建立 Request 時的 ValueError，以及共用層收屍。結果沒有 name／id。
