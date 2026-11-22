# `knowledge/aos/me/self_tools.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/me/self_tools.md`，跟到正本 commit `c7c05017a`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/me/self_tools.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Changing your own toolbox`**

# 改你自己的工具箱

工具 `self_tools` 就是對準你的 `aos-agent tools`。它只改你自己的工具清單；你的定義和其他 agent 都保持原樣。修改立刻生效，就在這一輪：從你的下一個回覆起，你會看到新的清單，並直接用名字呼叫新工具（不能在加上它的同一個回覆裡）。

一次呼叫一個 op（JSON 就是工具的參數）：

- 列出：`{"op": "ls"}`：每個工具一行，它的名字和說明的第一句。`{"op": "ls", "long": true}`：每個工具一行文字，附上它從哪裡來，還有你關掉的工具（kind `null`）。
- 完整顯示一個（整段說明、參數、錯誤）：`{"op": "get", "name": "math"}`。`ls` 的那一句不夠時用這個。
- 加上：`{"op": "add", "path": "tools/math"}`（所有選項：`aos/me/self_tools.md#/self_tools add: options`）
- 移除：`{"op": "rm", "name": "math"}`（名字，不然就給路徑）。這會替你關掉那個工具；它的檔案會留著。
- 撤銷你所有的修改：`{"op": "reset"}`

規則和錯誤：`aos/me/self_tools.md#/self_tools: rules and errors`。

**`#/self_tools add: options`**

# self_tools add：選項

`{"op": "add", "path": "tools/math"}` 加上那個資料夾裡的工具。可選的鍵：

- `"name"`：用來列出它的名字（預設：資料夾名稱）。
- `"replace": true`：取代同名的工具。
- `"envs": {"LANG": "C.UTF-8"}`：每次呼叫都用的固定值，照寫的原樣存起來。不要放祕密。
- `"env_file": "secrets/read.env"`：只存它的位置；每次呼叫時讀它。祕密用這個。
- `"no_cache": true`：給可執行的工具用。
- 不用 `path` 的話：`"path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/base/math"}` 會照寫的原樣保留路徑，每次用的時候再去查。

**`#/self_tools: rules and errors`**

# self_tools：規則和錯誤

- 相對路徑（`path`、`env_file`、`rm`/`get` 裡的路徑）從你的工作區算起：`tools/math` 表示 `$AOS_WS/tools/math`。絕對路徑照原樣用。
- 加上一個工具不會建立它。資料夾必須已經存在（不然就是 `PathMissing`）。先在你的工作區寫好工具檔案，或請人類幫忙。
- `ToolDefMissing`：資料夾裡沒有 `_tooldef.json`，所以它不是工具。`ToolDefBad`：它的 `_tooldef.json` 壞了。用 `tools_def` 建立或修好它（`aos/tools_def.md#/tools_def`）；沒有任何內建範本有 `tools_def`（agent-fsm 或 eca 都沒有）：先用 `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/tools_def"}}` 加上它。
- 路徑不見了或定義壞掉的工具，`ls` 會顯示成 `NAME TAB broken: CODE (...)`（加 `"long": true` 時 kind 是 `broken`）。它不會被提供來呼叫；你其他的工具照常運作。修法是 `{"op": "rm", "name": "NAME"}`，再從它現在的位置重新加上；`get` 會顯示完整的錯誤。
- 搬動一個你加過的工具（例如 `tools/x` 搬到 `new_tools/x`）：先 `rm` 它，搬資料夾，再 `add` 新路徑。在你這樣做之前，清單會一直記著舊路徑。
- `ToolExists`：同名的工具已經在了。只有你真的要取代它時才用 `"replace": true`。
- `ToolMissing`：沒有那個名字的工具（`rm`、`get`）：先 `ls`。`NameBad`：名字是空的，或含有工具名稱不能有的字元。
- 不認得的參數名，或那個 op 不接受的參數，是 `ArgumentsBad`。
- `DaemonMissing`、`DaemonFailed`、`InstanceMissing`：這個功能暫時不能用；要說出來，之後最多再試一次（`aos/errors/common.md`）。

為什麼這樣安全：從同一個定義啟動的其他 agent 看不到你的修改。人類可以用 `aos-agent ctl state --target <you>` 看你改了什麼（那一行 `tools   own: N listed, M set to null (…)`），並用 `aos-agent tools reset` 撤銷。
