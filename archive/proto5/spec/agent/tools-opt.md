← [agent](README.md)｜[spec 總導航](../README.md)

# 3.4 `tools` 元素的 `$opt`：改名（`as`）、只挑幾支（`only`）（09-24 access-impl）

`info.json` 裡**只有 `tools` 陣列的元素**吃 `$opt`（[指示詞 §4](../directives/opt.md)）；其他欄位、元素裡面、被 `$ref` 指到的值遇到 `$opt` 照舊是 `UnknownOption`。

```json
"tools": ["tools/base.json",
          {"$opt": {"as": {"bash-edit-a": "edit-a"}}, "$val": "../util-tools/bash-edit-a.json"},
          {"$opt": {"only": ["bash-grep"], "as": {"bash-grep": "grep"}}, "$val": "../util-tools"}]
```

- 元素三種寫法：路徑字串；指示詞（解完要是路徑字串）；選項物件 `{"$opt": {…}, "$val": 路徑}`。
  選項物件要**直接寫在元素位置**（`tools` 本身可以是 `$ref` 到別檔的陣列，陣列元素照樣可以是選項物件）；用 `$ref` 取來一個選項物件＝`UnknownOption`。
- `$val` 必帶，可以再是指示詞，解完是檔或資料夾的路徑（相對 agent 家，照 §3 的 `tools`）。資料夾＝裡面全部 `*.json`，`as`／`only` 套到這些檔合起來的全部工具。
- `$opt` 是字面物件（機制不解裡面的指示詞），鍵只有：

| 鍵 | 型別 | 意思 |
|---|---|---|
| `as` | 非空物件 `{原名: 新名}`，新名是非空字串 | 改名：模型看到、叫的都是新名 |
| `only` | 非空的原名字串陣列、不重複 | 這條只讀這幾支，其餘略過 |

- 順序：**`only` 先挑、`as` 再改名**。`as` 的原名要在挑完的那幾支裡。
- 形狀錯（照指示詞慣例）：

| 情況 | 代號 |
|---|---|
| `$opt` 不是物件 | `FieldTypeMismatch` |
| `$opt` 有 `as`／`only` 以外的鍵 | `UnknownOption` |
| `$opt` 是空物件、或缺 `$val` | `OptionConflict` |
| `as` 不是非空物件、新名不是非空字串；`only` 不是非空字串陣列、有重複 | `FieldTypeMismatch` |
| `$val` 解完不是字串 | `FieldTypeMismatch` |

- 內容錯是 `ToolInvalid`（跟 §3.3 一樣是工具的錯）：`only`／`as` 寫了檔（或資料夾）裡沒有的原名（訊息列出有哪些）；
  改名後跟別條同名（含兩個原名改成同一個新名）——訊息說「改名後工具同名」「是 as 改名造成的」，列兩邊的檔、第幾個、原名。沒改名的同名照 §3.3 的「合併後工具同名」。
- 同一個檔可以出現在兩條（例如兩條各 `only` 一支）；合併後不同名就行。

## 讀出來長什麼樣

- 每條工具的 `function.name` 是**改後的名字**；`aos-agent`（送件找工具）、`aos-llm call`（組 body）、`check` 用同一份讀法（`lib/aos_agent_home.py` 的 `load_llm_view`），看到同一個名字。記憶裡記的也是新名字。
- 每條工具多一個內部鍵 `_source`：`{"file": 工具檔絕對路徑, "index": 檔裡第幾個（從 0）, "name": 原名, "entry": info.tools 第幾個元素}`。
  跟所有 `_` 開頭的鍵一樣**不送模型**（§3.3 最後一條）。工具檔本身不改。
- `_jail`（工具元素頂層，跟 `_timeout_ms` 同層）：可省，只收 `true`／`false`（別的＝`ToolInvalid`）；`false`＝這支不關牢，家裡沒有 `access.json` 也照樣送；沒寫或 `true`＝要關牢，家裡沒有 `access.json` 時這支直接不送（`NoAccess`）。關牢是什麼見 [access.md](access.md)。

## 誰會改這個陣列

手改之外，`aos-agent tools add --as／--only`、`tools rm`、`tools alias`／`unalias` 會改（[aos-agent/tools.md](../aos-agent/tools.md)、[tools-manage.md](../aos-agent/tools-manage.md)）。
它們只改「字面陣列、元素是路徑字串或字面選項物件（`$val` 是字面字串）」的 `tools`；有別的指示詞就拒絕、請人手改。
