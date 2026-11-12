# aos-mcp-launch：起一台外部 stdio MCP server——讀 server 檔與它的 env_file（金鑰），exec 成那支 server，金鑰只活在 server 行程

← [proto8](../../README.md)｜設計：[external-mcp 02](../../thinking/2026-11/12/external-mcp/02-設計.md)、施工：[06](../../thinking/2026-11/12/external-mcp/06-施工結果.md)

```sh
aos-mcp-launch SERVER_FILE      # 讀 SERVER_FILE（transport stdio），把 env 與 env_file 放進環境，exec 成 command args…
aos-mcp-launch --help
```

- 平常不用自己打：eca 定義的 `cli.json` 在 `mcp_servers` 列了一份 stdio 的 server 檔，cli_session 就替 claude／codex 寫成 `command＝aos-mcp-launch`（PATH 找到的絕對路徑）、`args＝[server 檔絕對路徑]`。CLI 的設定、命令列、環境都只有路徑，沒有金鑰。
- server 檔形狀（讀與驗在 [`lib/mcp_server_file.py`](../../lib/mcp_server_file.py)）：

  ```json
  {"description": "<一句話>",
   "mcp_server": {"name": "<名字>", "transport": "stdio", "command": "<指令>", "args": ["…"],
                  "env": {"<明文變數>": "<值>"}, "env_file": "<金鑰檔的位置>", "only": ["<工具名>"]}}
  ```

- **相對路徑一律從 server 檔所在的資料夾算**：`aos-mcp-launch` 先 `cd` 到那個資料夾再 exec，所以 `command`（含 `/` 的；不含＝從 PATH 找）與 `args` 裡的相對路徑都從那裡起（例：`mcp/demo.json` 寫 `"command": "bin/run", "args": ["bin/server.py"]`＝`mcp/bin/run mcp/bin/server.py`）。要工作區裡的路徑就寫指示詞：`args` 整個或其中一格都可寫 `$env`／`$ref`（例 `{"$env": "AOS_WS", "$path": "data"}`），每次起才解。經 aos 那條（`mcp_tool`、`aos-mcp-import`）同一條規則（11-12 [08](../../thinking/2026-11/12/external-mcp/08-fsm施工結果.md) 代定 G13）。
- server 拿到**起它的那個行程的全部環境變數**（再加 `env`、`env_file`）：claude 身與經 aos 那條＝起樹那個殼的整份，殼裡放著的 API key 它也看得到（codex 不替 server 帶父行程環境，只有 aos 給的那幾個）。使用者 11-12 裁不做白名單、風險自己承擔；不信任的 server 就別在帶著金鑰的殼裡起。
- `env_file` 一行一個 `KEY=VALUE`（可有 `export`、`#` 註解、成對引號），整份進 server 的環境。
- 錯：stderr 一行 `aos-mcp-launch: error: 代號 原因`、退 1。`ArgumentsBad`（沒給或多給）、`PackMissing`／`PackBad`（檔不在、形狀不對、是 http 的檔）、`PathMissing`（`env_file` 不在、進不了 server 檔的資料夾）、`DotenvBad`、`CommandMissing`。錯誤句只講變數名與檔的位置，不講值。
- 測試在 [`lib/agent/tests/test_cli_external_mcp.py`](../../lib/agent/tests/test_cli_external_mcp.py)。
