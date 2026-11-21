# `knowledge/aos/cli/parts/directive.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/parts/directive.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**（整份）**

# aos-directive：解開指示詞（directive）

```sh
echo '{"p": {"$env": "HOME", "$path": "/x"}, "r": {"$ref": "other.json#/x"}}' | aos-directive
# {"p": "/home/me/x", "r": {"y": "hi"}}
```

它從 stdin 讀一份 JSON 文件（空的 = `{}`），解開裡面每一個指示詞（directive）（`$ref`、`$env`、`$path`、...；相對路徑從目前資料夾算；`./` 和 `../` 都能用），把結果印成一行。`$ref` 的路徑照一條規則：`#` 左邊是檔案路徑，從放著這個 `$ref` 的檔案所在的資料夾算起（`./`、`../`、絕對路徑；在最上層時，從 `--file FILE` 所在的資料夾算，沒給它就從目前資料夾算）；`#` 右邊是 JSON 裡面的位置。`{"$ref": "x.json#/a/b"}` 是 x.json 的 `/a/b`；`#/a/b`（沒有檔名）是從放著這個 `$ref` 的檔案的根算起的 `/a/b`（在最上層時，是 `--file FILE` 給的那個檔案；沒給 `--file` 就原樣留著）；`#./b` 從放著這個 `$ref` 的物件算起，`#../c` 從那個物件再上一層算起（可以重複；超過根就是 `DirectiveBad`）；`#` 或 `#/` 是整個檔案。`#aaa`、`y.json#aaa`、`y.json#./b` 和 `y.json#../b` 都是 `DirectiveBad`。變數沒設定或 `$ref` 讀不到 = `DirectiveBad`；stdin 不是 JSON = `InputBad`。`--at POINTER` 說明 stdin 的 JSON 是 FILE 的哪個位置（給 `#./` 和 `#../` 用）；它需要 `--file`（`ArgumentsBad`）。其他 aos 程式（aos-exec、clock 的登記、工具登記表）會自己解開同樣的指示詞（directive）；用這個來看一份設定最後會變成什麼。

更多旗標：執行 `aos-directive --help`。
