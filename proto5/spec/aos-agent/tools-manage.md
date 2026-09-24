← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 1.8（續）`tools ls`／`rm`／`alias`／`unalias`（09-24 access-impl）

```
aos-agent tools ls      [--target DIR] [--json]
aos-agent tools rm      NAME [--target DIR]
aos-agent tools alias   NAME NEW [--target DIR]
aos-agent tools unalias NEW [--target DIR]
```

一句話：**看 agent 有哪些工具、拿掉一支、幫一支改名——都只改 `info.json` 的 `tools`，不動任何工具檔。**
`tools add` 在 [tools.md](tools.md)；`tools` 元素的 `$opt`（`as`、`only`）在 [agent §3.4](../agent/tools-opt.md)。

## 共通

- 家照 §1（`--target`，省略＝目前資料夾）。參數個數不對、參數是空字串、`--root`／`--force`／`--as`／`--only` 給了 add 以外、`--json` 給了 ls 以外＝用法錯 2。
- 先把整個家讀驗一次（跟 `aos-llm call` 同一份讀法）；讀不過照那個代號退 1。
- 寫入的三個（`rm`、`alias`、`unalias`）：
  1. 持 `<家>/info.json` 的 flock（跟 `tools add`、`access` 的寫入指令同一把；檔被換過就重拿，見 tools.md）。
  2. `info.tools` 要是字面陣列、元素是路徑字串或字面 `$opt` 物件（`$val` 是字面字串）；不是＝`FieldTypeMismatch`，請人直接編 `info.json`。
  3. 在記憶體裡改一份，**整份試算**（照 agent §3.3／§3.4 重讀全部工具）；不過（例如改名撞名＝`ToolInvalid`）就退 1、什麼都不寫。
  4. `.tmp`＋rename 整份重寫 `info.json`（格式同 `aos_home.write_json`：一行、不跳脫中文，保留其他鍵）。
  5. 印做了什麼，最後一行「下一批工具生效，不用重 start」。退 0。
- NAME 是**模型看到的名字**（改過名的就是新名）。找不到＝`NotFound`，訊息列出現有的名字；給的是某支的原名會提示它現在叫什麼。

## `tools ls`

一支一行，欄位：

| 欄 | 內容 |
|---|---|
| 名字 | 模型看到的名字 |
| 原名 | 改過名才印原名，沒改印 `-` |
| 來源檔 | 工具檔路徑（在家裡的相對家，家外的絕對） |
| 關牢 | `jail`＝會關；`no`＝這支 `_jail: false`；`-`＝家裡沒有 access 檔（全部不關）；`?`＝access 設定讀不到（stderr 一行 warn） |
| 池 | `info.tool_pool`（沒寫＝`default`） |

最後一行 `N 個工具；關牢照 <access 檔>` 或 `…；沒有 access 檔：工具不關牢`。沒有工具印一句怎麼裝。

`--json`（穩定格式，第 1 版）：

```json
{"_type": "aos_agent_tools_ls", "_version": 1, "dir": "家的絕對路徑", "access": "access 檔絕對路徑或 null",
 "tools": [{"name": "edit-a", "original": "bash-edit-a", "file": "工具檔絕對路徑", "index": 0,
            "entry": 1, "jail": true, "pool": "default"}]}
```

`index`＝工具檔裡第幾個（從 0）、`entry`＝`info.tools` 第幾個元素；`jail` 是 `true`／`false`／`null`（沒有 access 檔或讀不到）。之後只加鍵、不改既有鍵的意思。

## `tools rm NAME`

找到提供這支的那條 `info.tools`：

- 那條只剩這一支 → 整條拿掉。
- 那條還有別的 → 改成 `only` 其餘幾支（原名，照讀到的順序），`as` 裡這支的改名一併拿掉。那條是整個資料夾時多印一句：之後放進去的新工具要加進 `only`（或 `tools add`）才會出現。

**不刪任何檔**，印「檔還在 <工具檔> （第 i 個，原名 …）」。

## `tools alias NAME NEW`、`tools unalias NEW`

- `alias`：NAME 可以是現在的名字，也可以是原名（原名同時對到好幾支＝用法錯 2，請用現在的名字）。在提供它的那條加（或改）`as`：純路徑字串會變成 `{"$opt": {"as": {原名: NEW}}, "$val": 路徑}`。
  NEW 就是原名＝等於 `unalias`；NEW 跟現在的名字一樣＝印「沒改」、不寫、退 0。改名後撞名＝`ToolInvalid`（試算抓到）。
- `unalias NEW`：NEW 要是改過名的那支（沒改過＝`NotFound`）。拿掉那條 `as` 裡這支；`as` 空了就拿掉 `as`，`$opt` 空了就把整條收回成純路徑字串（印一句）。改回原名撞名＝`ToolInvalid`。

## 這兩節沒管的

- 家裡已有的工具檔壞了（`ToolInvalid`）時 `tools` 的寫入指令都不動它：先手動修好或刪掉那個檔。
- `enable`／`disable`：使用者的構想在 [thinking/aos-agent.md](../../../thinking/aos-agent.md)，這輪不做。`tools rm` 只改 `info.tools`，裝進來的檔要自己刪（`tools/<名>.json`、`tools/<名>/`）。
- `init --tools base`（生家時順便裝）：未來可加，等同 `init` 之後 `tools add`。
- `info.tools` 用了 `$ref`／`$env`／`$fmt` 時不自動改（怕蓋掉手寫的共用設定）。
