# aos-mcp-import：連一次外部 MCP server，把它的工具凍結進同一份 server 檔，疊進 tools.json 就是一包工具

← [cmd](../README.md)｜圖紙：[external-mcp 07 步 5](../../thinking/2026-11/12/external-mcp/07-fsm施工單.md#步-5cmdaos-mcp-import)｜server 檔：[aos-mcp-launch](../aos-mcp-launch/README.md)

```sh
aos-mcp-import [--only A,B | --except C,D] [--timeout-s N] SERVER_FILE
aos-mcp-import --help
```

- SERVER_FILE 是人先寫好的 server 檔（`description`＋`mcp_server`，跟 eca 原生掛那條同一份，形狀與讀法在 [`lib/mcp_server_file.py`](../../lib/mcp_server_file.py)）。匯入起那台 server、列工具、每支用 [`lib/mcp_freeze.py`](../../lib/mcp_freeze.py) 凍結，原子寫回同一份檔（暫存檔＋rename），多三個頂層鍵：
  - `mcp_import`：`imported_at`、`protocol_version`、`server_tools`（server 當時總共幾支）
  - `mcp_tools`：鍵是外部原名，每格 `_entry`（叫 `lib/base/mcp_tool/_entry --pack <檔名> --tool <原名>`）、`_tooldef`、`_metainfo`
  - `tools`：登記名 `<server 名>_<工具名>` → `"<檔名>#/mcp_tools/<原名>"`（原名的 `~`、`/` 跳脫成 `~0`、`~1`；只寫檔名，整夾 `cp -r` 帶走仍通）
- `description` 與 `mcp_server` 的值不動（整份重新排版成縮排 2 格）；`--only`／`--except` 給了才補寫進 `mcp_server.only`／`except`。之後 `mcp_server_file.load` 照樣讀得過，eca 那條仍能用同一份檔。
- 挑工具：`--only`／`--except` ＞ 檔裡的 `only`／`except` ＞ 全收（超過 20 支印 warning）。檔裡已有另一組＝`ArgumentsBad`（先改檔）。`--only` 有 server 沒有的名字＝`ToolUnknown`；`--except` 的只印 warning。兩支轉成同一個登記名＝`NameBad`（用 `--except` 排掉一支）。
- `--timeout-s N`：起 server 到列完工具的總時限，到了＝`ServerFailed`；沒給＝只靠 mcp_client 自己的 30 秒上限。
- 疊法：定義的 `tools.json` 寫 `{"$override": [<原本的包…>, "mcp/time.json"], "tools": {}}`。匯入不替人改 `tools.json`，只印要加哪一個。
- 已匯入過（檔裡有 `mcp_tools`、`mcp_import` 或 `tools`）＝`PackExists`；重問 server 更新凍結的那批是 `aos-mcp-import sync`（步 7，還沒做；現在打＝`CommandUnknown`）。

輸出（stdout 兩行）：

```text
imported 2 of 7 tools from fake -> mcp/fake.json
add it to tools.json "$override": "mcp/fake.json"
```

錯：stderr 一行 `aos-mcp-import: error: 代號 原因`、退 1，**檔的位元組不變**。代號：`ArgumentsBad`、`FlagUnknown`、`CommandUnknown`、`PackMissing`、`PackBad`（含 http 的檔：http 要等步 6）、`PathMissing`、`DotenvBad`、`PackExists`、`CommandMissing`（server 起不來）、`ServerFailed`、`ServerBad`、`ToolUnknown`、`NameBad`、`WriteFailed`。句子不帶金鑰的值。

測試：`python3 tests/test_import.py`（假 stdio server `lib/tests/fake_mcp_stdio.py`，不用真腦、不用網路）。
