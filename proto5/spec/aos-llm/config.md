← [aos-llm](README.md)｜[spec 總導航](../README.md)

# 2. llm.json

（09-24 試玩 r3 改）例子用 LiteLLM；任何 OpenAI 相容端點都行。

```json
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"small": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat",
                      "api_key": {"$env": "LITELLM_KEY"}, "timeout_ms": 120000}}}
```

- 整份解指示詞，中心是 llm.json 所在的資料夾；`$env` 讀的是 aos-llm call 自己的環境（＝那顆 cpu 的環境）。頂層整份不能是指示詞。
- 讀不到＝`ReadFailed`；不是 JSON＝`JsonSyntax`；頂層不是物件＝`NotAnObject`；指示詞錯照 [directives.md §6](../directives/errors.md)。

| 鍵 | 型別 | 沒寫時 | 不合 |
|---|---|---|---|
| `_metainfo` | 物件，`_type`＝`"llm_config"`、`_version`＝整數 1（bool 不算） | 必填 | 沒寫、不是物件、缺 `_type` 或缺 `_version`、`_type` 不是 `"llm_config"`＝`ConfigInvalid`；有 `_version` 但不是整數 1（含 bool）＝`UnsupportedVersion`。`_metainfo` 裡其他 key 忽略 |
| `models` | 物件，key 是代號 | 必填 | `ConfigInvalid` |
| `models.<代號>.endpoint` | 非空字串 | 必填 | `ConfigInvalid` |
| `models.<代號>.model` | 非空字串（真名） | 必填 | `ConfigInvalid` |
| `models.<代號>.api_key` | 字串或 `null` | 不帶 | `ConfigInvalid`；空字串＝不帶 |
| `models.<代號>.timeout_ms` | 正整數（bool 不算） | 120000 | `ConfigInvalid` |
| 其他 key | — | — | 忽略 |

整份一起驗：任何一筆形狀不對整份不收，不只看用到的那筆。`info.llm.model` 的代號不在 `models` 裡＝`UnknownModel`。
