# proto8/lib — 函式庫

← [proto8](../README.md)

只用 Python 標準庫，沒有命令列。測試在 [../tests/](../tests/)，跑法：`python3 -B proto8/tests/run.py`（哪裡跑都行）。

## 指示詞 lib（2026-10-12 從 proto7-2 拿來）

讓 JSON 裡某一格的值「從別處來」。這個 lib 只管「這一格是不是指示詞、怎麼解成真的值」；哪些格要解、解完該是什麼型別，由用它的人（宿主，例如 inst）決定。

| 檔 | 管什麼 |
|---|---|
| `aos_directives.py` | 解析本體：`resolve()`、`resolve_located()`；對外只要 import 這一個 |
| `aos_directives_base.py` | 底層型別：`DirectiveError`、`Document`、`Context`、`load_document()` |
| `aos_directives_options.py` | 選項物件 `$opt`：`split_option()`、`option_names()`、`parse_options()` |

四種指示詞（同一個物件裡有好幾個，只看優先最高的那個）：`$opt` > `$ref` > `$fmt` > `$env`。

```jsonc
{"$env": "HOME"}                                   // 讀環境變數
{"$fmt": {"$val": "${who}-log.txt", "who": "bob"}} // 拼字串，${名字} 只查旁邊的表
{"$ref": "other.json#/a/0"}                        // 讀另一份 JSON 的某一格；"" 是自己這份
{"$opt": ["append"], "$val": "out.txt"}            // 選項物件：lib 不解，原樣交給宿主
```

錯了一律丟 `DirectiveError`，帶規範裡的代號（`ReferenceCycle`、`ReferencePointerInvalid`、`UnknownOption`…，共 10 種）。

完整規則在 [proto5/spec/directives/](../../proto5/spec/directives/README.md)（機制本身沒變過）。來源：proto7-2/lib 的最新版，比 proto6 多兩處修正（陣列索引邊緣、`$at` 寫 null）；測試是 proto6 的 101 條＋補那兩處的 4 條（[test_directives_edges.py](../tests/test_directives_edges.py)）。
