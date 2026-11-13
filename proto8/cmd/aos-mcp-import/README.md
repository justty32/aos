# aos-mcp-import：連一次外部 MCP server，把它的工具凍結進同一份 server 檔，疊進 tools.json 就是一包工具；sync 重問、印差異、`--yes` 才寫

← [cmd](../README.md)｜圖紙：[external-mcp 07 步 5](../../thinking/2026-11/12/external-mcp/07-fsm施工單.md#步-5cmdaos-mcp-import)、[步 7](../../thinking/2026-11/12/external-mcp/07-fsm施工單.md#步-7aos-mcp-import-sync)｜server 檔：[aos-mcp-launch](../aos-mcp-launch/README.md)

```sh
aos-mcp-import [--only A,B | --except C,D] [--timeout-s N] SERVER_FILE
aos-mcp-import sync [--yes] [--timeout-s N] SERVER_FILE
aos-mcp-import --help
```

- SERVER_FILE 是人先寫好的 server 檔（`description`＋`mcp_server`，跟 eca 原生掛那條同一份，形狀與讀法在 [`lib/mcp_server_file.py`](../../lib/mcp_server_file.py)）。匯入起那台 server、列工具、每支用 [`lib/mcp_freeze.py`](../../lib/mcp_freeze.py) 凍結，原子寫回同一份檔（暫存檔＋rename），多三個頂層鍵：
  - `mcp_import`：`imported_at`、`protocol_version`、`server_tools`（server 當時總共幾支）
  - `mcp_tools`：鍵是外部原名，每格 `_entry`（叫 `lib/base/mcp_tool/_entry --pack <檔名> --tool <原名>`）、`_tooldef`、`_metainfo`
  - `tools`：登記名 `<server 名>_<工具名>` → `"<檔名>#/mcp_tools/<原名>"`（原名的 `~`、`/` 跳脫成 `~0`、`~1`；只寫檔名，整夾 `cp -r` 帶走仍通）
- **改名／抄成別名＝重新匯入**：`tools` 的指標與 `_entry` 的 `--pack` 都寫死匯入當時的檔名，同一夾裡 `cp a.json b.json` 再改 b 的 `command`、把 b 疊進 tools.json，叫起來照樣起 a 那台、叫的那一刻不報錯（工具那邊手上的資訊都指著 a，認不出來）；`aos-mcp-import sync b.json` 會報 `PackBad … was imported as a.json and its tools still run that file`。要讓 b 自己算數：刪掉 b 的 `mcp_import`、`mcp_tools`、`tools` 三鍵（`aos-json del b.json#/mcp_tools`，三鍵各一次；不刪＝`PackExists`），再 `aos-mcp-import b.json`。放進別的資料夾、檔名不變不用重匯。
- `description` 與 `mcp_server` 的值不動（整份重新排版成縮排 2 格）；`--only`／`--except` 給了才補寫進 `mcp_server.only`／`except`。之後 `mcp_server_file.load` 照樣讀得過，eca 那條仍能用同一份檔。
- stdio server 不管誰叫（匯入、`sync`、腦叫工具）都在 server 檔的資料夾起，`command` 與 `args` 的相對路徑都從那裡算（規則同 [aos-mcp-launch](../aos-mcp-launch/README.md)）；它拿到叫它那個行程的全部環境變數（使用者裁不做白名單）。
- 挑工具：`--only`／`--except` ＞ 檔裡的 `only`／`except` ＞ 全收（超過 20 支印 warning）。檔裡已有另一組＝`ArgumentsBad`（先改檔）。`--only` 有 server 沒有的名字＝`ToolUnknown`；`--except` 的只印 warning。兩支轉成同一個登記名＝`NameBad`（用 `--except` 排掉一支）。
- `--timeout-s N`：initialize 與每頁 `tools/list` 各自的上限（不是總時限），到了＝`ServerFailed`；沒給＝30 秒。
- 疊法：定義的 `tools.json` 寫 `{"$override": [<原本的包…>, "mcp/time.json"], "tools": {}}`。匯入不替人改 `tools.json`，只印要加哪一個。
- 已匯入過（檔裡有 `mcp_tools`、`mcp_import` 或 `tools`）＝`PackExists`；重問 server 更新凍結的那批用 `sync`（下一節）。

輸出（stdout 兩行）：

```text
imported 2 of 7 tools from fake -> mcp/fake.json
add it to tools.json "$override": "mcp/fake.json"
```

## sync：重問 server、印差異

- 檔裡沒有 `mcp_tools`＝`PackBad`（先跑匯入）。重連、照**檔裡的** `only`／`except` 重新凍結（F8：人改了檔裡的 `only`，跑 `sync --yes` 才生效；`sync` 不收 `--only`／`--except`），跟檔裡的 `mcp_tools` 比 `description` 與 `parameters`，差異印 stdout：`+ 名`（新的）、`- 名`（server 沒了，`tools` 那條跟著拿掉）、`~ 名: description changed`／`parameters changed` 後面各一行 `before:`、`after:`。
- 沒差＝印 `no changes`、不寫；有差沒 `--yes`＝差異＋`run again with --yes to write`、不寫；`--yes`＝原子寫回 `mcp_import`、`mcp_tools`、`tools`，末行 `synced N of M tools from <名> -> <檔>`。三種都退 0。
- 人手改過的 `_metainfo.timeout_ms` 保留；其他欄位（`side_effect`、`summary`…）照 server 的重算。檔裡 `only` 有、server 已經沒有的名字＝warning、當成拿掉（`only` 本身不替人改）。
- 只有 `side_effect` 這類 `_metainfo` 變了、`description`／`parameters` 沒變＝算 `no changes`（差異只比那兩項）。

```text
~ echo: description changed
    before: [MCP server fake] Return the supplied text.
    after:  [MCP server fake] Echo text with a changed description.
run again with --yes to write
```

## 錯

stderr 一行 `aos-mcp-import: error: 代號 原因`、退 1，**檔的位元組不變**（匯入與 sync 都是）。代號：`ArgumentsBad`、`FlagUnknown`、`PackMissing`、`PackBad`、`PathMissing`、`DotenvBad`、`PackExists`、`CommandMissing`（server 起不來）、`ServerFailed`、`ServerRejected`（http 401／403）、`ServerBad`、`ToolUnknown`、`NameBad`、`WriteFailed`。句子不帶金鑰的值。

測試：`python3 tests/test_import.py`（假 stdio server `lib/tests/fake_mcp_stdio.py`，不用真腦、不用網路）。
