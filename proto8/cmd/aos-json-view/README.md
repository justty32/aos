# aos-json-view — 只讀：把 json 印成人好讀的樣子

← [cmd](../README.md)

`bin/aos-json-view`（Python）讀一份 json（可給 `#/指標` 只看一段），印成緊湊好讀的樣子，不改任何檔（11-13 晚使用者「直接看json當然不好讀。建議幫我弄個程式，把json內的換行弄好，格式這塊稍微緊湊些。」）。

```sh
aos-json-view wf/workflows/decisions.json            # 整份
aos-json-view wf/knowledge/code-map.json#/domains/0  # 一段（或第二個參數寫 '#/domains/0'）
aos-json-view --width 80 --no-color FILE | less      # 指定寬度、不上色
aos-json-view --depth 1 wf/knowledge/code-map.json   # 只看第一層，再深的摺成 {…3 keys}／[…5 items]
```

- 給了指標＝開頭先印一行 `# FILE#/指標`，看得出看的是哪一段（11-13 晚使用者「都按照推薦，- 不用加」：字串陣列不加 `- `，照舊接成段落）。

- 物件＝`鍵: 值`，同層鍵名對齊；短的物件／陣列擠成一行（`{a: 1, b: x}`、`[a, b]`）；其餘陣列元素前加 `- `。
- 字串不加引號（空字串、擠在一行裡會混淆的才加）；`\n` 真的換行；字串陣列（非空、全是字串，[認法](../../thinking/2026-11/13/text-as-string-array.md)）當一段文字、一個元素一行。
- 照終端寬度折行（中日文算兩格）；文字段裡折出來的續行多縮兩格，看得出元素邊界。`$ref` 的值印成 `-> 原字串`，不展開。
- 縮排每層兩格，第一格是 `|`（導引線）；上色時 `|` 顏色隨深度 6 色輪換（紅粉、橘、綠、青、淺藍、紫，第 7 層起從頭），折行的續行照畫不斷線；不上色時 `|` 照印（11-13 晚使用者「縮排這塊，不是兩個空格嗎，第一個空格幫我換成|，然後顏色要隨着深度不同而變換」）。
- 顏色對照（上色時；選中亮度的色，深底淺底都看得到，不用深藍）：

  | 東西 | 顏色 | ANSI |
  |---|---|---|
  | 鍵名 | 粗體青 | `1;36` |
  | 字串 | 綠 | `32` |
  | 整數 | 黃 | `33` |
  | 浮點 | 橘 | `38;5;208` |
  | true／false | 洋紅 | `35` |
  | null | 紅 | `31` |
  | `$ref` | 底線天藍 | `4;38;5;75` |
  | `--depth` 摺起來的 | 斜體灰 | `3;38;5;245` |
  | 括號、冒號、逗號、`- ` | 灰 | `38;5;245` |
  | 導引線第 1～6 層 | 紅粉、橘、綠、青、淺藍、紫 | `38;5;203`、`214`、`113`、`80`、`111`、`177` |

- `--color`／`--no-color`：預設 stdout 是終端且沒設 `NO_COLOR` 才上色。`--width N`：預設終端寬，不是終端＝`COLUMNS` 或 100。
- 字串裡換行以外的控制字元印成 `\xNN`。錯：`aos-json-view: error: 代號 原因`、退 1（ArgumentsBad、FlagUnknown、FileBad、PointerBad）。

測試：`python3 -m unittest discover -s proto8/cmd/aos-json-view/tests`。
