# `knowledge/aos/cli/parts/fsm.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/fsm.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-fsm：狀態表的一步

```json
{"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "a", "states": {
 "a": {"exec": {"argv": ["sh", "-c", "echo in a"]}, "next": "b"},
 "b": {"exec": {"argv": ["sh", "-c", "echo in b; exit 3"]}, "next": {"3": "a", "*": "b"}}}}
```

```sh
AOS_STACK=/tmp/st aos-fsm fsm.json      # prints "in a"; /tmp/st/stage.txt is now b
AOS_STACK=/tmp/st aos-loop --max 3 fl.json   # fl.json: {"exec": "fsm.json"}: in a, in b, in a
```

目前的狀態在 `$AOS_STACK/stage.txt`（沒有 = `start`）。`next` 是名字 = 只在 exit 0 時移過去；是物件 = 查結束碼（`*` = 任何碼）。有移動 = exit 0。表沒接住的碼 = 這一步自己的碼，狀態不變。沒有 `AOS_STACK` = `StackMissing`。`stage.txt` 裡的狀態不在表裡 = `StateUnknown`；表壞了 = `CfgBad`（`next` 物件需要 `"0"` 或 `"*"`）。`_entry` 鍵讓 aos-exec 和 aos-loop 能跑這張表。agent-fsm 的 `fsm.json` 就是這樣一張表（idle、think、wait、act）。
