# `knowledge/aos/cli/parts/exec.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/exec.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-exec：跑一個 entry

一切的基礎：daemon、loop、fsm 格子和工具呼叫全都透過它跑。可以手動用它試跑一個函式或工具一次。

```sh
aos-exec hello a b                        # hello/_entry with args a b
# ws=/tmp/w stack=/tmp/w/.stack/ args=a b
aos-exec --ws /work --stack /tmp/st hello
aos-exec p.json#/x                        # an instruction inside a JSON file
aos-exec $AOS_HOME/lib/tools/base/math --expr '6*7'   # a lib tool; flags fill its JSON input
# 42
```

它設定 `AOS_WS`（`--ws`，否則外層的 `$AOS_WS`，否則目前的資料夾）和 `AOS_STACK`（`--stack`，否則外層的，否則 `WS/.stack/`），讀 `.env`（`--dotenv-override` 讓它蓋過已設定的變數），然後跑那個 entry。`--stack-lazy` 不建立 stack 資料夾。結束碼就是 entry 的。`EntryMissing`：沒有這個路徑。`EntryBad`：不能跑；loop 設定需要 aos-loop，fsm 表需要 `"_entry": ["aos-fsm", {"$env": "AOS_CF"}]`。

更多旗標：跑 `aos-exec --help`。
