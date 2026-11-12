# fake-mcp-http：假的 http MCP server（Bearer＋自簽 CA），給外部 MCP 測試用；只聽 127.0.0.1、只用假 token

← [extras](../README.md)｜出處：[external-mcp 05](../../thinking/2026-11/12/external-mcp/05-http-bearer試接.md)、[06](../../thinking/2026-11/12/external-mcp/06-施工結果.md)

`server.py`（標準庫、沒有 `mcp` 套件也能跑）：最小 Streamable HTTP——POST 收 JSON-RPC、回 `application/json`；`initialize` 給 `Mcp-Session-Id`；通知回 202；GET 回 405；DELETE 回 200。工具兩支：`echo`（回 `echo: <text>`）、`list_threads`（兩筆固定假資料）。Authorization 不對＝401＋`WWW-Authenticate: Bearer`。每個請求在 log 記一行 JSON：方法、工具名、`auth` 是 `ok`／`wrong`／`missing`（**不記 token 的值**）。

## 用法（在一個新的暫存資料夾裡，例 `/tmp/fake-mcp`）

```sh
mkdir -p /tmp/fake-mcp && cd /tmp/fake-mcp
# 1. 自簽 CA＋CA 簽的 leaf（不能拿自簽憑證直接當 server 憑證：curl 吃、codex 不吃，05 的坑）
openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem -days 3 -subj "/CN=fake-mcp-ca"
openssl req -newkey rsa:2048 -nodes -keyout key.pem -out leaf.csr -subj "/CN=127.0.0.1"
printf 'subjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n' > leaf.ext
openssl x509 -req -in leaf.csr -CA ca.pem -CAkey ca.key -CAcreateserial -out cert.pem -days 3 -extfile leaf.ext
cat /etc/ssl/certs/ca-certificates.crt ca.pem > ca-bundle.pem     # 系統 CA＋這張 CA（跟真主機的 bundle 同一種合法）
# 2. 假 token：當場產、檔案 600、不要印出來
mkdir -m 700 cfg && (umask 077; echo "TEAMSITE_TOKEN=FAKE-$(openssl rand -hex 12)" > cfg/teamsite.env)
# 3. 起（埠 港號 憑證 金鑰 token檔 log）
setsid -f python3 /path/to/proto8/extras/fake-mcp-http/server.py 18444 cert.pem key.pem cfg/teamsite.env server.log < /dev/null > server.out 2>&1
```

token 檔只認第一行 `名字=值` 的值（`TEAMSITE_TOKEN=` 以外的名字也行）。停＝`pkill -f fake-mcp-http/server.py`。

## 接給一隻 codex 身的 eca

server 檔（例 `<定義>/mcp/teamsite.json`）：

```json
{"description": "Fake teamsite MCP server for tests (http, bearer, private CA).",
 "mcp_server": {"name": "teamsite", "transport": "http", "url": "https://127.0.0.1:18444/mcp",
                "bearer_token_env": "TEAMSITE_TOKEN", "env_file": "/tmp/fake-mcp/cfg/teamsite.env",
                "ca_file": "/tmp/fake-mcp/ca-bundle.pem"}}
```

`cli.json` 加 `"mcp_servers": ["mcp/teamsite.json"]`。問它「call the teamsite MCP tool echo with text hello」，看 `server.log` 有 `"auth": "ok"` 的 `tools/call`。查 token 有沒有漏：用 `sed -n 's/^TEAMSITE_TOKEN=//p' cfg/teamsite.env` 讀進變數（不要 echo），`grep -rlaF -- "$T"` 掃樹與 `~/.codex` 新動到的檔、掃 `/proc/*/cmdline` 與 `/proc/*/environ`。
