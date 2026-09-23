# aos-llm-call：問模型一次（程式規範，**草稿**）

← [proto5 README](../README.md)｜資料夾：[agent.md](agent.md)｜誰叫它：[aos-agent.md](aos-agent.md)｜它跑在哪：[cpu.md §4.1](cpu.md)

> 2026-09-23 草稿。**程式還沒照這份改**：現在的 `aos_llm_ask.py`＋`aos_llm_cpu.py` 仍是舊版（組 body 跟打 HTTP 分兩支、
> 中間隔一個 llm cpu 佇列）。這份把兩件事合成一支普通程式，llm cpu 這種東西就不用存在了。

一句話：**`aos-llm-call AGENT_DIR` 讀 agent 家、組一份 chat 請求、打一次 HTTP、把模型回的那則 message 印成一行 JSON。**
不寫記憶、不碰 `state.json`、不跑工具；像個純函式，跑完就走。它是 kernel 排給某顆 cpu 的一份普通工作，
連線設定跟金鑰從 cpu 的環境來（[cpu.md §4.1](cpu.md)「cpu 的環境就是工作的環境」）。

## 1. 用法

```
aos-llm-call [AGENT_DIR]
```

`AGENT_DIR` 留空＝`.`；必須是 agent 家（[agent.md §1](agent.md)）。沒有別的旗標。

## 2. 讀什麼

照 [agent.md §3](agent.md)：`info.json` 解指示詞；人格、記憶、工具檔原樣讀。再讀 `info.llm.config` 指的 **llm.json**：

```json
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"small": {"endpoint": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3-1.7b",
                      "api_key": {"$env": "LMSTUDIO_KEY"}, "timeout_ms": 120000}}}
```

- 整份解指示詞，中心是 llm.json 所在的資料夾；`$env` 讀的是 aos-llm-call 自己的環境（＝跑它那顆 cpu 的環境）。
- `models` 必填、物件；每筆 `endpoint`／`model` 必填非空字串、`api_key` 可省或 null、`timeout_ms` 可省（預設 120000，正整數）。
  型別不合＝`ConfigInvalid`；`info.llm.model` 的代號不在表裡＝`UnknownModel`。
- 這份檔可以放 agent 家、也可以好幾個 agent 共用一份（`info.llm.config` 隨便指）。

## 3. 組 body

跟舊的 aos-llm-ask 一樣：

- 人格 `content` 非空 → 第一則 `{"role":"system","content":…}`；後面原樣接記憶陣列。
- 工具照檔案順序合併，每個元素拿掉所有 `_` 開頭的頂層 key（`_meta`、`_timeout_ms`…）；空陣列不送 `tools`。
- `info.llm.params` 併進 body（其中 `model`／`messages`／`tools`／`stream` 忽略）。
- `body.model` 填 llm.json 那筆的真名。

## 4. HTTP 與輸出

`POST <endpoint 去掉結尾 />/chat/completions`，JSON body；`api_key` 非空才帶 `Authorization: Bearer`。
不串流、不重試，socket timeout＝`timeout_ms`。

| 結果 | stdout | stderr | 退出碼 |
|---|---|---|---|
| 2xx 且有 `choices[0].message` | 那個 message 物件，**一行** JSON（`ensure_ascii=False`） | 無 | 0 |
| 逾時 | 無 | `aos-llm-call: Timeout: <白話>` | 1 |
| 連不上、非 2xx、回的不是 JSON、缺 message | 無 | `aos-llm-call: EngineFailed: <白話>` | 1 |
| agent 家、llm.json、代號讀驗錯 | 無 | `aos-llm-call: <代號>: <白話>`（代號照 agent.md §5、上面 §2） | 1 |
| 用法錯 | 無 | argparse | 2 |

message 原樣印，只有 `content` 是 null 又沒 `tool_calls` 時補成 `""`（不然接進記憶下次讀驗過不了）。
stdout 只會有這一行，所以 agent 把它指到一個檔就能整份讀回來。

## 5. 給程式用

```python
body = aos_llm_call.build_request(agent_dir)          # 只組、不打
msg  = aos_llm_call.call(agent_dir)                   # 組＋打，回 message dict；失敗丟帶 code／msg 的例外
```

## 6. 我自己選的（等你確認）

1. **連線設定獨立成 llm.json**，`info.llm.config` 指路徑；不塞回 `info.json`，好讓多個 agent 共用一份。
2. **輸出走 stdout 一行 JSON**，不寫檔——寫哪裡由 inst 的 `stdout` 決定，程式本身不知道 agent 家以外的路徑。
3. `Timeout`／`EngineFailed`／`UnknownModel`／`ConfigInvalid` 四個代號沿用舊 llm-cpu 的名字。
