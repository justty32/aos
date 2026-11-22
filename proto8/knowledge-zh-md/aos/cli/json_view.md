# `knowledge/aos/cli/json_view.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/json_view.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/json_view.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/aos-json-view: print JSON in a layout a person can read`**

# aos-json-view：把 JSON 印成人看得懂的排版

只讀：它印出一個 JSON 檔，或其中一部分，什麼都不改。它是給在終端機前的人用的；在 aos 裡面請用 `json_get` / `json_ls`，它們給的是精確的 JSON。

```sh
aos-json-view cfg.json                      # the whole file
aos-json-view cfg.json#/states/think        # one part; or as a second word: aos-json-view cfg.json '#/states/think'
aos-json-view --depth 1 --no-color cfg.json | less
```

它印出什麼：物件印成 `key: value` 行，鍵對齊；短的物件和陣列印在一行（`{a: 1, b: x}`、`[a, b]`）；較長的陣列每個項目一行，前面加 `- `。每層縮排是 `| `。字串沒有引號（除了空字串，顯示成 `""`，以及在一行的 `{}` / `[]` 裡面含 `,`、`: `、括號或前後空白的字串），字串裡的 `\n` 會換新的一行，較長的字串陣列顯示成一段文字，一個元素一行。`$ref` 值顯示成 `-> target`，不會跟過去。有指標時，第一行是 `# FILE#/POINTER`。輸出不是 JSON：不要解析它，也不要貼回檔案裡。

- `--depth N`：只展開 N 層；更深的顯示成 `{…3 keys}` / `[…5 items]`。字串陣列算文字，永遠不摺。
- `--width N`：換行寬度（小於 20 的數字當成 20）。預設：終端機寬度；stdout 不是終端機時用 `$COLUMNS`，否則 100。
- `--color` / `--no-color`：只有 stdout 是終端機而且沒設 `NO_COLOR` 時，顏色預設開。兩個一起給 = `ArgumentsBad`。
- 旗標可以放在 FILE 前面或後面。真的叫 `x#y` 而且存在的檔案，會當成那個檔案讀，不當成指標。

錯誤（stderr 上的 `aos-json-view: error: CODE reason`，結束碼 1）：`FileBad`（檔案讀不了，也包括不存在，或它不是 JSON）、`PointerBad`（那個指標上沒東西，或它不是以 `#/` 開頭）、`ArgumentsBad`（沒給檔案、多一個字、`--depth` 或 `--width` 不是正數）、`FlagUnknown`。
