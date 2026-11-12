# json 工具第三輪：aos-json 加 add／ls／search（Python 搬下去）、新工具 json_len、複雜組 jsonx_multi_get／set、json_ls 的 depth

← [json-tools](README.md)｜前一份：[03](03-multi與複雜組補齊.md)｜圖紙 [01-規劃](01-規劃.md) §6「之後」

## 根據（使用者原話，出處在前幾份）

- 「建議做成一個aos_json工具(順便把原本的aos-json也一起更新一下？)」（11-12，[README](README.md)）——圖紙 01 §6「之後」排成「aos-json 加 add、機器可讀的 ls、search，把 Python 這邊的搬下去」。
- 「json_len」（11-11，[11-11 json-tools](../../11/json-tools.md)）——01 D11 曾代定不做，本輪照原話做出來（D11 作廢，見下方 D40）。
- 「一次讀寫多格、複雜組的json工具可以做。」（11-12，[03](03-multi與複雜組補齊.md)）——03 D35 把複雜組 multi 列「以後」，本輪做。

## 結論（做了什麼）

- **aos-json 三個新子命令**（`b9c334ec1`）：
  - `add [--follow|--raw] [--parents] [--check] FILE#/PTR [VALUE]`：物件已有這個 key＝新代號 `KeyExists`；陣列 `/N` 插在第 N 項前面（0..長度）、`/-` 接尾；整份檔已在＝`KeyExists`。成功印實際位置（`-` 換成真索引）。插陣列中間時 splice 只插新成員那一段，其他原文不動。
  - `ls [--follow] [--resolve] [--long] [--offset N] [--limit N]`、`search [--follow] [--resolve] [--key K] [--value JSON] [--contains] [--up] [--limit N]`：輸出跟原本 Python 的 json_ls／json_search 逐字一樣（`[more]` 行改說 `--offset`／`--limit`）。
- **Python 改叫它們**（`b50686a2c`）：`lib/aos_json.py` 只留參數檢查、上限、組旗標、把 aos-json 的話說成工具參數名；385 → 301 行。`test_json_tools` 原有期望一條沒改全過。
- **json_len**（`06cdefa89`）：`{"path"}` → 一行整數；物件＝key 數、陣列＝項數、字串＝字元數（code point）；數字、布林、null＝`TargetBad`。進 json 包：agent-fsm 47 支、eca-claude 26 支；eca 子 agent 那台（tools_sub）疊整個 json 包、只關會寫的幾支，所以自動多這支，九支。
- **json_ls／jsonx_ls 加 `depth`**（`131381bb2`；aos-json `ls --depth N`）：預設 1＝原行為；>1＝照檔裡順序列出 N 層內的子孫，每行是相對 path 的指標段（例 `states/think/next`），`long` 欄照舊，`offset`／`limit` 算在攤平後的行上。
- **jsonx_multi_get／jsonx_multi_set**（`06cdefa89`）：逐格照 jsonx_get／jsonx_set，其餘同 json_multi（D31～D34）。進 jsonx 包，範本照舊不掛。

例：

```text
json_add {"path":"cfg.json#/tags/1","value":"x"}   → ok cfg.json#/tags/1   （檔裡只多 "x", 那一行）
json_len {"path":"cfg.json#/name"}                 → 3
jsonx_multi_get {"paths":["cfg.json#/r/y"],"follow":true} → cfg.json#/r/y<TAB>1
```

## 代定（接 D39，可翻案）

- **D40 json_len 做出來，D11 作廢**：使用者 11-11 原話列了它。形狀照 json_ls 第一行的「長度」：物件 key 數、陣列項數、字串字元數；純值沒有長度＝`TargetBad`（不回 0、不回型別，免得腦以為是空的）。只有簡單組一支，不做 jsonx_len（`jsonx_ls` 第一行就有）。
- **D41 json_len 進子 agent 那台**：照 templates/docs/01 的原則（不改東西、不是講這隻 agent 自己＝放）。
- **D42 jsonx_multi 的選項**：`follow`、`resolve`、`check`、`parents`、`max_bytes`、`full` 整批一個；值來源 `value`／`text`／`from` 每格各自剛好一個，不是＝那格 `[error] ArgumentsBad`；item 裡放選項（例 `follow`）＝那格 `unknown key in item`。
- **D43 aos-json add 印實際位置、其他寫入子命令照舊不印**：Python 拿它接 `ok `；`set`／`append`／`del` 不改，免得動到別的呼叫者。
- **D44 aos-json ls／search 不給 `--limit`＝全列**：上限是工具（給腦）那層的事，Python 一律明給。
- **D45 下沉後幾句錯誤句變了**（都只在錯的時候）：add 中間層不在改帶 `"parents": true` 提示；add 帶指標而檔不在帶 `json_set FILE {}` 提示（同 json_set）；簡單組 add 碰到 `$ref` 物件照原文說「沒有這個 key」，不再叫腦改用 jsonx；json_ls 的 `offset`／`limit` 給錯型別一律先報 `ArgumentsBad`；json_search 的 `key` 不是字串報 `ArgumentsBad`（以前當成沒中）。
- **D47 depth 的形狀**：子孫一行一個、寫成相對路徑（同 search 命中行一樣能直接接在 path 後面），不做縮排樹；不設上限（`limit` 擋著、`[more]` 給下一頁）；`depth` < 1＝`ArgumentsBad`。
- **D46 數字比對照 Python**：search 的 `value` 比對 `1` 等於 `1.0`（同原本 Python），`1` 不等於 `"1"`、`true` 不等於 `1`。

## 驗證

- `impls/aos-json/tests/test_add_ls_search.py` 22 支（對舊 binary 全紅、新的全綠）；`lib/tests` 139、`lib/agent` 64、`templates` 20＋agent-fsm 91、`cmd/aos-tools` 120、`cmd/aos-mcp` 15 全過。aos-json 已重 build（家機）。
- 新舊 Python 逐案比對：ls／search 各種路徑與參數（含 `-` 開頭檔名、follow、resolve、up、中文、emoji、`~`／`/` key）輸出一樣；add 寫出的檔一樣。
- 沒跑真腦（工具說明句型照前兩輪，新工具只有 json_len 一支是腦會常看到的）。

## 要重建什麼

- 沒改持久格式。裝過的機器要重 build `impls/aos-json`（PATH 上的 `aos-json` 要有 add／ls／search，不然 json_ls／json_search／json_add 會報 `CommandUnknown`）；不用重跑 install.sh（沒有新指令）。

## 以後

- 01 §6「之後」列的都做完了。
