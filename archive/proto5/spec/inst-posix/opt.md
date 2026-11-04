← [inst-posix](README.md)｜[spec 總導航](../README.md)

## 3.3 `$opt` 選項物件

`stdin`／`stdout`／`stderr`／`exit`／`cwd`／`envs` 這幾個位置，除了路徑（或 `envs` 的物件），
還可以放一個「選項物件」，統一長這樣：

```json
{"$opt": "名字"}                         單一選項、不帶值
{"$opt": "名字", "$val": 值}             單一選項、帶值
{"$opt": ["名字1", "名字2"], "$val": 值}  多個選項一起用
```

> 機制層（[directives.md](../directives/README.md) 第 4 節）的 `$opt` 值**任何 JSON 都可以**、不限
> 型別——機制本身不解讀、不驗。「`$opt` 必須是選項名字串或非空字串陣列」是 **inst 這個
> 宿主自己訂的規則**，不是指示詞機制規定的。

- `$opt` 的值是**字串**或**非空字串陣列**；別的型別 → `DirectiveValueTypeMismatch`。
  陣列裡重複同一個名字 → `UnknownOption`（訊息會說「重複」）。
- `$val` 是「本來要直接寫在那一格的值」，型別照那一格的規則驗；`$val` 本身**可以再是
  指示詞**（`$env`／`$fmt`／`$ref`），解完再驗。
- 選項物件只**讀 `$opt`、`$val`** 這兩個 key，其他 key 一律忽略（含 `$ref`／`$fmt`／`$env`），不會報錯。
- 這個位置不認得的選項名 → `UnknownOption`。
- 選項名區分大小寫，只認小寫。

各位置能用的選項：

| 位置 | 選項 | `$val` | 意思 |
|---|---|---|---|
| `stdin` | `inherit` | 不能帶 | 繼承執行者（aos-exec）的標準輸入 |
| `stdout` | `append` | 必帶（路徑） | `>>`：檔案存在就接在後面，不存在就建 |
| `stdout` | `mkdir` | 必帶（路徑） | 父目錄不在就先建（`makedirs`） |
| `stdout` | `inherit` | 不能帶 | 繼承執行者的標準輸出 |
| `stderr` | `append`／`mkdir`／`inherit` | 同 stdout | 同上 |
| `stderr` | `merge` | 不能帶 | 跟 stdout 走同一條（`2>&1`），照 stdout 的設定（含 append／inherit） |
| `exit` | `append` | 必帶（路徑） | `>>`：結束碼一行一行接在後面 |
| `exit` | `mkdir` | 必帶（路徑） | 父目錄不在就先建 |
| `cwd` | `mkdir` | 必帶（路徑） | 目錄不在就先建（`makedirs`） |
| `envs` | `clear` | 可省（物件；省略＝`{}`） | 從空環境開始，只放 `$val` 裡的 |

可以合併的：同一個位置的 `append`＋`mkdir`（`stdout`／`stderr`／`exit`）。

互斥、一起出現就是 `OptionConflict`：

- `inherit` 跟 `append`／`mkdir`／`merge` 任何一個一起出現。
- `merge` 跟 `append`／`mkdir`／`inherit` 任何一個一起出現。
- `inherit`／`merge` 帶了 `$val`（這兩個選項規定不能帶值）。
- 該帶 `$val` 卻沒帶（`append`／`mkdir` 都是必帶）；給了空字串也算沒帶（空路徑的舊意思是 `/dev/null`，跟 append／mkdir 兜不起來，不默默放過）。
- `$opt` 放在不吃選項的位置→ `UnknownOption`。不吃選項的位置：**頂層整份**、**`argv` 整個陣列**、`argv` 的元素、`envs` 的值、以及**選項物件的 `$val` 裡面**（`$val` 解出來又是一個選項物件也算）。

執行時 mkdir／append／inherit／merge 各自實際發生什麼，見第 6 節。
