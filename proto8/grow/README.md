# grow — aos-grow（原型）

← [proto8](../README.md)｜設計：[thinking 2026-10-24 函數成長](../thinking/2026-10-24-fn-grow.md)｜測試：`proto8/tests/test_grow.py`

`aos-grow - 把一個函數往上長一級或縮回一級，呼叫方跟著改、跑起來一樣`

10-24 嘗試性質（使用者「我隨便說，你隨便做，反正只是嘗試」）。Python、只用標準庫，不進 impls。

```
aos-grow [--dry-run] up   設定檔#/指標 --to file|dir [--name NAME] [--take PATH]...
aos-grow [--dry-run] down 設定檔#/指標
```

`設定檔#/指標` 指到呼叫方「寫著要跑什麼」的那一格（fsm 格的 `exec`、loop.json 的 `exec`…）。

| 做什麼 | 那格原本 | 之後 |
|---|---|---|
| `up --to file` | 內嵌單子 | 那格寫 `"NAME"`；旁邊多一份 `NAME.json`（就是那張單子） |
| `up --to dir` | 內嵌單子，或 `"NAME"`＋`NAME.json` | 那格寫 `"NAME"`；`NAME/_entry`（同一張單子）；`NAME.json` 刪掉 |
| `--take PATH` | 只有它用的檔 | 搬進 `NAME/`，單子 argv 裡那一項改成 `{"$env": "AOS_CD", "$path": "/檔名"}` |
| `down` | `"NAME"` | 資料夾（只剩 `_entry`）→ `NAME.json`；`NAME.json` → 內嵌回那格（還有別格或別份 JSON 叫它就不縮） |

NAME 沒給＝那格的名字（`…/states/think/exec` → `think`）。那格寫不帶 `.json` 的名字，所以從檔長成資料夾時呼叫方不用再改（aos-exec 找不到 `NAME` 會補 `.json`，`NAME` 是資料夾就走進去，N-61）。

**怎麼做到「跑起來一樣」**：只改位置相關的值，讓它們指回原來的地方——單子的 `cwd`（沒寫＝入口所在的資料夾，搬進資料夾就補 `".."`）、相對的 `$ref` 檔名（`"#/…"` 補上原檔名）、`{"$env": "AOS_CD", "$path": …}`。單子裡用了 `$env AOS_CF`／`AOS_CO` 就不搬（搬了值會變）。`--dry-run` 印出新檔全文、改的檔 diff、搬／刪哪些，什麼都不寫。真的做時先寫新檔，最後才改呼叫方（先寫 `.名字` 暫存檔再改名，N-05）。

**錯**：stderr 一行 `aos-grow: 代號 原因`、退 1、什麼都不寫。代號：`ArgumentsBad`、`FlagUnknown`、`CfgMissing`（檔或指標指不到）、`CfgBad`（JSON 壞）、`TargetBad`（那格不是能搬的東西、或搬了會改行為）、`NameBad`（名字被佔、名字不合、縮回時別處還在叫）、`WriteFailed`。

**不保證一樣的地方**（細節在 thinking）：錯誤訊息的「誰」會從 `loop.json#/exec` 變成 `NAME`；單子被 `timeout_ms` 收掉時 fsm 的 trace `signal` 從 15 變 null（`code` 都是 143）；程式自己讀 `AOS_CF`／`AOS_CD`／`AOS_CO` 環境變數的話值會變（工具看不到程式碼裡面）；假設呼叫方跑字串目標時 cwd＝設定檔的資料夾（慣例下成立；daemon.json 的子項沒試過）；呼叫方那份 JSON 的排版會換成工具的排版（內容不變）。
