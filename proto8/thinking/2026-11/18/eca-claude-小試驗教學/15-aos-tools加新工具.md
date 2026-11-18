這份教你自己寫一支最小的工具，用 aos-tools 這條路加給一隻活著的 eca-claude agent，再試改它、拿掉它、弄壞它，以及在 agent 停著時加工具會怎樣（試驗 15，11-18 在公司 WSL 用 haiku 實跑過）。
← [目錄](README.md)

使用者原話：「再來幾個試驗與教學：eca claude，然後我們用aos-loop方式控制其停止與繼續。然後在他停止的時候我們aos-say，還有用aos-tool給他添加新工具」。停止與繼續見 [13](13-aos-loop控制停止與繼續.md)，停著時 say 見 [14](14-停著時say.md)，這份只講加工具。

## 結論

- 指令名字是 **`aos-tools`**（有 s），沒有 `aos-tool`。它管一份「工具通訊錄」JSON 檔（`tools.json`）。程式在 `py/aos/apps/tools/`，今天拆成 `main`、`common`、`helps`、`registry`、`tooldef` 五個檔，但對外還是同一支指令。
- **`aos-agent tools` 就是包著 `aos-tools` 的殼**：它替你找到「這隻 agent 自己那份」（`<stack>/tools.json`），再叫 `aos-tools --file 那份 …`。旗標跟 `aos-tools add` 一樣。
- 工具夾最小只要兩個檔：**`_entry`**（可執行，從 stdin 讀 JSON、把結果印到 stdout）和 **`_tooldef.json`**（給模型看的說明與參數）。`_metainfo.json` 是選配。
- **不用重起、不用 set-def**。加完下一句就叫得到，工具名是 `mcp__aos__<名>`。改工具的程式或說明也是下一句就生效。
- 兩份 `tools.json`：
  - **定義那份**（`agents/ann/tools.json`）：改了，用這份定義的每一隻都會變。
  - **stack 那份**（`.stack/procs/ann/tools.json`）：只記這一隻自己加的、拿掉的。第一次 `aos-agent tools add` 時才建，裡面用 `"$override"` 指回定義那份，所以定義那份之後改的也看得到。
- **停著時加**（`ctl stop` → `tools add` → `ctl start`）也行，起來第一句就叫得到。

## 一步一步

前提：樹照 [README 的「共同準備」](README.md#共同準備)起好、ann 掛著。下面都在視窗 C 的 `~/aos-home` 打。範例工具是 `linecount`，作用是數一個檔有幾行。

**1. 做工具夾**

```sh
mkdir -p ~/my-tools/linecount && cd ~/my-tools/linecount
```

`_entry`（用編輯器建，存好後 `chmod +x _entry`）：

```python
#!/usr/bin/env python3
# linecount - count the lines of one file (a minimal aos tool)
import json, os, sys
args = json.load(sys.stdin)
path = os.path.join(os.environ.get("AOS_WS", "."), args["path"])
with open(path) as f:
    n = sum(1 for _ in f)
print(json.dumps({"path": args["path"], "lines": n, "by": "linecount v1"}))
```

`_tooldef.json`：

```json
{"description": "Count the lines of one file. Returns JSON {path, lines, by}.",
 "parameters": {"type": "object",
                "properties": {"path": {"type": "string", "description": "file path relative to your workspace"}},
                "required": ["path"]}}
```

`AOS_WS` 是 agent 的工作區，相對路徑從那裡算。`"by"` 那格只是為了證明「真的是這支工具回的」。

**2. 先自己跑一次**

```sh
cd ~/aos-home && seq 1 37 > notes.txt && echo '{"path":"notes.txt"}' | AOS_WS=$PWD aos-exec ~/my-tools/linecount
```

會看到 `{"path": "notes.txt", "lines": 37, "by": "linecount v1"}`。這步不過，後面就不用試了。

**3. 加給 ann（只給這一隻）**

```sh
aos-agent -t ann tools add ~/my-tools/linecount
```

```
added linecount -> /home/你/my-tools/linecount (/home/你/aos-home/.stack/procs/ann/tools.json: "/home/你/my-tools/linecount")
aos-agent: warning: created /home/你/aos-home/.stack/procs/ann/tools.json (it records only what this agent added or removed; later changes to the definition still show through; tools reset deletes it)
```

名字預設就是夾名。給絕對路徑就存絕對路徑，給相對路徑就存成「相對那份 tools.json」的寫法。`cat .stack/procs/ann/tools.json` 會看到：

```json
{"$override": "../../../agents/ann/tools.json",
 "tools": {"linecount": {"path": "…/my-tools/linecount"}}}
```

**4. 確認有列出來**

```sh
aos-agent -t ann tools ls | grep linecount
```

會看到 `linecount	Count the lines of one file.`，stderr 另外有一行 `using this agent's …/tools.json`。要看路徑、寫在哪份，用 `ls -l`：`linecount	dir	/home/你/my-tools/linecount	…/.stack/procs/ann/tools.json#/tools/linecount	…`。

直接用 aos-tools 看要自己指檔：`aos-tools --file .stack/procs/ann/tools.json ls`。不給 `--file` 就讀現在資料夾的 `./tools.json`，在樹根打會說找不到。

**5. 讓 agent 真的叫它**

```sh
aos-agent -t ann ask --timeout-s 180 "Use your linecount tool on notes.txt and tell me exactly what it returned."
```

約 12 秒，回 `{"path": "notes.txt", "lines": 37, "by": "linecount v1"}`。`grep -o '"name":"mcp__aos__linecount"[^}]*}' .stack/procs/ann/claude/live.jsonl` 會看到 `"name":"mcp__aos__linecount","input":{"path":"notes.txt"}`。**沒有重起 agent**。

## 改、拿掉、弄壞

**改工具**：把 `_entry` 的 `v1` 改成 `v2`、說明改成 `(version 2)`，直接再問。回答變成 `"by": "linecount v2"`，它看到的說明也是新的。不用重載，因為每次叫工具都重新執行 `_entry`，工具清單也是每一輪重讀。

**拿掉**：

```sh
aos-agent -t ann tools rm linecount
```

會看到 `removed linecount (…/.stack/procs/ann/tools.json: key deleted)`。再問它有沒有 `mcp__aos__linecount`，回 `No.`。拿掉定義那份也有的工具，會在 stack 那份寫成 `"名": null`，定義那份不動。`aos-agent -t ann tools reset -y` 會整份刪掉 stack 那份，回到只用定義那份。

**加在定義那份**：

```sh
aos-tools --file agents/ann/tools.json add ~/my-tools/linecount
```

會看到 `added linecount -> … (agents/ann/tools.json: …)`。ann 有自己那份也看得到，因為它的 `$override` 指回這裡。

**`_entry` 沒有 +x**（`chmod -x _entry`）：`tools ls` 照樣列出，叫的時候才失敗。agent 看到的是：

```
aos-mcp: error: CommandFailed linecount exited 1 with empty stdout
[aos] tool: linecount stderr (last 2048 bytes at most):
aos-exec: error: EntryBad bad entry: not executable (+x) and not JSON: /home/你/my-tools/linecount/_entry
```

**輸出不是 JSON**：沒關係。印 `notes has 37 lines` 這種純文字，照樣原文交給 agent。

**工具自己報錯**（印 `linecount: error: FileMissing …`、退 1）：agent 收到那行錯，後面再附一段 `[aos] tool: linecount stderr …`。

**`_tooldef.json` 壞掉**（不是 JSON）：

```
linecount	broken: ToolDefBad (its tool definition is broken); correct its path or take it off the list with rm linecount (get linecount shows the full error)
```

還會多一行 `aos-tools: warning: tool linecount skipped: …`，退出碼還是 0。agent 那邊這支直接消失，其他工具照常。

## agent 停著時加工具

```sh
aos-agent -t ann ctl stop
aos-agent -t ann tools add ~/my-tools/motto
aos-agent -t ann ctl start
```

`motto` 是另一支只印一句固定話的工具（`_entry` 是 `#!/bin/sh`、`cat >/dev/null`、`echo "The owl flies at noon."`）。停著時 `tools add` 照樣成功，`tools ls` 也列得到。`ctl start` 會看到 `started (same stack); 0 queued letter(s) will be answered next`。之後問 `Call the motto tool`，回 `The owl flies at noon.`。

## 讓 agent 自己加

agent 手上有 `self_tools`。叫它「用 self_tools 加 `/home/你/my-tools/linecount`，同一輪接著叫它」，它加完就在同一輪叫成功了。加進的也是 stack 那份，存的是絕對路徑。

## 常見卡點

- 打成 `aos-tool`，找不到指令。要打 `aos-tools`。
- 在樹根打 `aos-tools ls` 看不到 agent 的工具：它只讀 `./tools.json`。要用 `aos-agent -t ann tools ls`。
- 同一段對話裡先答過「沒有這支」，之後工具加回去了，haiku 還是照前面的回答說沒有。其實那一輪的清單裡有（`live.jsonl` 的 `system/init` 列得到 `mcp__aos__linecount`）。跟它說一句「工具清單變了，再看一次」就會叫。

## 發現的問題

1. 資料夾工具的 `_entry` 沒有 +x，`tools ls` 不會標 broken，叫了才報 `EntryBad`。`_tooldef.json` 壞掉就會標 broken，兩種處理不一致。
2. `aos-agent tools` 每個子指令都在 stderr 印一行 `using this agent's …` 或 `using the definition's …`，連單純 `ls` 也印。
3. 工具照慣例把錯誤行同時印到 stdout 和 stderr，aos-mcp 兩段都交給 agent，所以 agent 看到同一行錯兩次。
4. `EntryBad` 那段把工具夾的絕對路徑整條給了模型。
5. 改了 `tools.json`、但不是 agent 自己用 `self_tools` 改的，這時不會通知 claude 清單變了。eca-claude 每一輪都重新列清單，所以下一輪就看得到。只是模型會被同一段對話裡自己先前的回答帶偏（見上面「常見卡點」最後一條）。
