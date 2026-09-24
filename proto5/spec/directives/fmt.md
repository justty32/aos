← [directives](README.md)｜[spec 總導航](../README.md)

# 3. 三種取值指示詞

| 指示詞 | 解出來是 | 意思 |
|---|---|---|
| `{"$env":"NAME"}` | 字串 | 讀**解析者自己的**環境變數 `NAME`。不存在＝錯誤；存在但是空字串＝解出空字串（這是兩件不同的事） |
| `{"$fmt":{"$val":"模板", "變數名":值, …}}` | 字串 | 字串模板代換：值是物件，`$val` 是模板、其餘 key 是本地變數表，見 3.1 |
| `{"$ref":"file.json"}`（可選 `"$at":"/a/b"`） | 任何 JSON | 讀另一份 JSON 檔（或目前文件）的某個位置，見 3.2 |

## 3.1 `$fmt`：字串模板

外形像 repo 既有那一套（[data-files-fmt](../../../wf/workflows/common/data-files-fmt.md)），但這裡
**沒有 namespace**。只有一種寫法：值是物件，`$val` 是模板，其餘 key 是「本地變數表」：

    {"$fmt": {"$val": "aaa${xxx}, bbb${zzz}", "xxx": {"$env":"yyy"}, "zzz": "haha"}}

要用環境變數，就在變數表裡放一個 `$env`：

    {"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}

**模板本身怎麼展開：**

- 只有 `${…}` 會被代換；單獨的 `$`、或 `$NAME`（沒有大括號）都是**字面**，不展開、不用跳脫。
- `${name}` **只查本地變數表**，沒有任何 namespace、沒有任何特例；表裡沒有這個名字 →
  `UnknownFormatVariable`，不會用猜的。
- **展開一次、不再掃結果**：代換進來的變數值裡如果又出現 `${…}`，就當字面，不會再展開。

**變數表的規則：**

- `$val` **必填**：這是模板本身；它自己可以再是指示詞（`$env`／`$ref`／`$fmt`…），解完
  必須是字串，不是字串 → `DirectiveValueTypeMismatch`。
- `$val` 以外的每個 key 都是**本地變數名**，值可以是字串，也可以是任何指示詞
  （`$env`／`$ref`／`$fmt`…），解完必須是字串，不是字串 → `DirectiveValueTypeMismatch`。
  變數的值跟這份 `$fmt` 用同一個中心路徑／同一條 `$ref` 鏈解，怎麼定中心路徑是宿主規範的事
  （見第 3.2 節、第 5 節）。
- 變數名不能 `$` 開頭、不能是空字串、不能含 `{`、`}` → `FormatVariableInvalid`。
- 定義了但模板沒用到的變數沒關係，不算錯。

`$fmt` 的值不是物件 → `DirectiveValueTypeMismatch`（舊的字串寫法不再認得）。
