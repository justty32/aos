# proto8/extras — 還沒定位的嘗試

← [proto8](../README.md)

還沒決定歸哪一夾的嘗試（使用者 10-24「我隨便說，你隨便做，反正只是嘗試」）。

| 資料夾 | 是什麼 |
|---|---|
| [aos-home/](aos-home/README.md) | 一棵樹根上的環境檔 `env.sh` 正本（清掉全部 `AOS_*`、只設 `AOS_HOME`），搭樹時抄過去；附 bash／zsh source 測試 |
| [fake-mcp-http/](fake-mcp-http/README.md) | 假的 http MCP server（Bearer＋自簽 CA、只聽 127.0.0.1），給外部 MCP 測試（`lib/tests/test_mcp_client.py` 起它） |
| `gitignore-check/` | 手跑的開發者回歸檢查：起一棵全假腦 daemon 樹，對 `thinking/2026-11/10/two-machines/gitignore_classes.json` 驗 stack 的 ignore 規則（`python3 check.py --help`）；`templates/tests/test_daily.py` 照它的 pattern 配法 |
| [image-move-check/](image-move-check/README.md) | 自建假腦 daemon 子樹，手跑休眠搬家與醒後問答驗證 |
| [kernel-chain-check/](kernel-chain-check/README.md) | 手跑的假腦劇本：暫存夾起根 daemon、一個 loop proc 式框架站、一個 daemon 身體式框架站（領班），驗兩站鏈的轉寄與代回、排隊、hook 拒信、重起後隊序不變、ping 穿站、hook 照規則把信分到兩個下一站（`python3 check.py`） |
| [langs/](langs/README.md) | 用 Janet、Lua 寫 aos 程式，編成資料夾＋JSON |

逐檔說明在 code map 的 [proto8 生成冊](../../wf/workflows/common/code-map/proto8/README.md)（從檔頭一句話生成）。
