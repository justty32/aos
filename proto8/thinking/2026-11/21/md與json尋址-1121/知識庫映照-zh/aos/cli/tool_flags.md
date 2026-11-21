# `knowledge/aos/cli/tool_flags.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/tool_flags.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# lib 工具的旗標

lib 工具接受從 schema 推出來的旗標，當作另一種給 JSON 輸入鍵的方式。

例如：

```sh
aos-exec lib/tools/base/read --path a.txt --max-lines 1
```

旗標蓋過 stdin 的鍵。`--a.b V` 只改那一片葉子，a 底下其他鍵保留。旗標裡的 `-` 代表鍵名裡的 `_`（`--max-lines` = `max_lines`）。布林鍵也接受 `--no-KEY` 表示 false。陣列鍵的旗標要重複給，每次一個項目；第一個會取代 stdin 來的陣列。工具定義可以列出 `positional` 鍵：這時一般的字會依序填進它們。stdin 裡最上層的 `description` 鍵可以容忍。stdin 裡不認得的鍵給 `ArgumentsBad`。不認得的旗標給 `FlagUnknown`。stdin 是終端機時，當作 `{}`，不去讀它。用 `fn` 寫的工具（`@fn.tool` 和 `fn.main`，像 tool-python 骨架的 `tool.py`）也接受 `--compile [LOCATION]`（寫出它的 `_tooldef` 和 `_metainfo`）、`--dry-run`（兩個都印出來，什麼都不寫）、`--tooldef` 和 `--metainfo`（印出其中一個），這些都是代替執行。

`--help` 裡的參數、預設值和宣告的錯誤代號來自 `_tooldef.json`；文字說明結果。給人用的指令用 `aos.flags`，它和 `lib/aos/tool_io.py` 共用斷詞器（tokenizer）。這不會把給人用的 CLI 旗標變成 stdin 的 JSON 物件；stdin 仍然帶內容，例如訊息文字或工具參數。
