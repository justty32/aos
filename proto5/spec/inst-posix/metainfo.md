← [inst-posix](README.md)｜[spec 總導航](../README.md)

# 1. `_metainfo`：這份 inst 是哪一種、第幾版

從 proto5 起，inst.json 頂層**可以**多一個 `_metainfo` 欄位，說明「這份 inst 用的是哪一種格式、
第幾版」：

```json
{
  "_metainfo": {"_type": "posix", "_version": 1},
  "argv": ["sh", "-c", "echo hi"]
}
```

| 鍵 | 型別 | 意思 |
|---|---|---|
| `_type` | 字串 | 格式種類。目前只有一種：`"posix"`＝本文描述的這套 |
| `_version` | 整數 | 該種格式的版本。`posix` 目前是 `1` |

**規則：**

1. **沒寫 `_metainfo`，就等於 `{"_type": "posix", "_version": 1}`**。所以之前寫的所有 inst.json
   都不用動、意思不變。
2. `_metainfo` 本身要是物件；除了 `_type`、`_version`，裡面**其他 key 一律忽略**，不要求「剛好
   只有這兩個 key」。少了 `_type` 或 `_version` → `MetainfoInvalid`。
3. `_type` 只認字面的 `"posix"`；別的字串（例如以後可能的 `"step"`）或非字串 →
   `UnsupportedInstType`。
4. `_version`（`posix`）只認整數 `1`；JSON 的 `true`／`false` 不算數（有些語言把 bool 當
   int 的子類，這裡特地擋掉）→ `UnsupportedInstVersion`。版號大於本文版號的 `posix` inst，
   讀的人**不該假裝看得懂**：要嘛拒絕（同一個代號），要嘛明講降級。
5. `_metainfo` 只描述格式，**不參與執行**——不是環境變數、不是參數、不會傳給子程式；它的值也
   **不吃指示詞**：是從 JSON 直接拿出來驗，不會丟進第 4 節那套 `$env`／`$fmt`／`$ref` 展開。
   所以寫 `{"_metainfo": {"$ref": "x.json"}}`，`$ref` 這個 key 不是 `_type`／`_version`，會被
   忽略——這個例子等於沒寫 `_type`／`_version`，一樣是 `MetainfoInvalid`（原因是缺欄位，不是
   多欄位）。唯一的例外是**頂層整份**是指示詞（例如 `{"$ref": "base.json"}`）：先把頂層解完，
   `_metainfo` 從解出來的那份物件拿。
6. `_type` 不是 `"posix"` 的 inst，本文管不到；那是之後別種 inst（例如以後可能有的
   `"step"`、`"llm"` 之類）各自的規範。
7. 以 `_` 開頭的頂層鍵保留給 metainfo 這類「講格式本身」的東西，**不會**拿來當一般欄位名。

---
