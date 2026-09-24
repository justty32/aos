# llm CPU 家、請求與結果（格式規範）

← [proto5 README](../README.md)｜共用格式：[cpu-queue](../../proto5.1/spec/cpu-queue.md)｜程式：[aos-llm-cpu](aos-llm-cpu.md)

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

身分與資料夾見 [cpu-queue](../../proto5.1/spec/cpu-queue.md)。models 必填且是物件；每個 key 是非空模型代號、值是物件。
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

model 是非空代號字串；body 是已組好的 chat/completions 物件；result 照共用格式為絕對路徑。
model／body 缺失或型別不對，在認領後回 BadPayload。
agent 不填 body.model，CPU 查表後填真名；請求不帶 endpoint、api_key 或 timeout_ms。
CPU 不讀 agent、不重驗 body 裡訊息與工具、不解請求指示詞，未知請求欄位忽略。

合法 result 下的壞 payload 認領後寫失敗結果、搬 done，當次 tick 回 0，後面的單可繼續處理。
格式合法但代號不在 models 表裡，回 `{"ok":false,"code":"UnknownModel","msg":"不認識的模型代號"}`，
不送 HTTP。共用欄位壞掉則搬 bad、tick 回 1，詳見 [cpu-queue](../../proto5.1/spec/cpu-queue.md)。

## 3. 結果

成功：`{"ok":true,"message":{"role":"assistant","content":"你好"}}`，message 是
`choices[0].message` 原樣。失敗固定 `{"ok":false,"code":"代號","msg":"白話"}`：

| code | 意思 |
|---|---|
| BadPayload | model／body 形狀不合 |
| UnknownModel | models 沒有這個代號 |
| Timeout | HTTP 逾時 |
| EngineFailed | HTTP／網路／模型回應錯誤，或建立 Request 失敗 |
| Reaped | 共用層收屍，沒有可靠結果 |

結果沒有 name／id。
