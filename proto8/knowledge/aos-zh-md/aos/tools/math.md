# `knowledge/aos/tools/math.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/tools/math.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 工具 math

精確計算一個算術式子，而不是用心算。什麼都不改。

允許：數字（整數和小數）、`+ - * /`、`//`（向下取整的除法）、`%`（餘數）、`**`（次方；指數最多 1000）、括號、正負號。不允許：函式（`sqrt`、`abs`）、字母或變數、用 `x` 當乘號、單位。

```json
{"expr": "17*23"}
```
-> `391`

- `{"expr": "(2+3)**2 // 4"}` -> `6`
- `{"expr": "7/2"}` -> `3.5`（`/` 給小數；`7//2` -> `3`）
- `{"expr": "2 ** 0.5"}` -> `1.4142135623730951`（平方根）
- `{"expr": "0.1+0.2"}` -> `0.30000000000000004`（小數是浮點數；在你的回覆裡四捨五入）

錯誤：`aos/tools/math.json#/errors`。

---

**`#/errors`**

# math：錯誤

- `ExprBad`：它算不了這個式子。理由會說為什麼：`division by zero`；`unsupported syntax: Call`（像 `sqrt(2)` 這樣的函式）；`unsupported syntax: Name`（字母或變數）；`cannot parse expression: invalid syntax`（像 `17 x 23`）；`exponent too large (limit 1000)`；`unsupported syntax: Constant`（字串、`True` 或其他非數字）；`cannot evaluate: ...`（結果太大）。只用數字和允許的運算子改寫它，然後再呼叫一次。不要重試同一個式子。
- `ArgumentsBad`：`expr` 沒給或不是字串，或你給了別的鍵。呼叫 `{"expr": "17*23"}`。
