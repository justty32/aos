main（這個 repo 的主線 agent）專用的定義：照 [eca-claude 範本](../../../../proto8/templates/agents/eca-claude/README.md) 原樣複製，只改 `cli.json` 兩格，讓使用者在手機上（`/remote-control`）好用。

# main 的定義（手機用）

← [main 筆記](../notes.md)｜範本說明：[eca-claude](../../../../proto8/templates/agents/eca-claude/README.md)

使用者 2026-11-27 11:51（家機，要出門、下午只用手機）：「我想請你修改一下自身設定，讓你自己可以發artifact，可以跳選項給我，一些基礎的功能都要有，這樣我在手機上比較好使用。好了之後跟我說，我重開session。然後我會用/remote-control啓用遠端」

## 跟範本差在哪

使用者 11-27 午發現公司帳號開不了 remote control（`policy-limits.json` 的 `allow_remote_control: false`），改用 Discord 跟 main 講話：「你能接入discord或chrome的line extension嗎？」→「弄」；「因爲你要是跳選項，那discord接不到，整個就會卡住」。

`cli.json`：

| 改了什麼 | 為什麼 |
|---|---|
| `--tools`、`--allowedTools` 多加 `Artifact`、`ArtifactComments`、`ArtifactData`、`ArtifactCheck`、`WebSearch`、`WebFetch`、`ToolSearch`、`Monitor`（`--allowedTools` 另多加 `Agent,Skill`） | 用 artifact 給手機看結果；上網找輪子 |
| **不給 `AskUserQuestion`**，權限照範本用 `dontAsk` | 跳選項或跳權限詢問都要人在畫面前按，人在 Discord 上就會卡住。dontAsk 下清單外的工具直接拒絕，不等人。11-27 實測：dontAsk 下 `AskUserQuestion` 就算列進放行清單也會被拒 |
| 拿掉 `--strict-mcp-config` | 實測這個開關會連外掛的 MCP 一起擋掉；repo 沒有 `.mcp.json`，拿掉不會多載入別的 server |
| 加 `--channels plugin:discord@claude-plugins-official`、`settings.enabledPlugins` 開 `discord@claude-plugins-official`、放行 `mcp__plugin_discord_discord` | Anthropic 官方的 Discord 頻道外掛：私訊機器人＝送進這個 session，回覆經它的 `reply` 工具送回去 |

外掛只在 main 這份設定裡開；使用者帳號那層（`~/.claude-alt/settings.json`）設成 `false`，免得一般的 claude 也去連同一隻機器人。外掛的 MCP 由 `bun` 跑：裝在 `~/.bun`，`~/.local/bin/bun` 是連結。機器人 token 放在 `~/.claude/channels/discord/.env`（`DISCORD_BOT_TOKEN=...`，由使用者自己寫，不進 repo，也不貼進對話）；配對狀態也存在同一個夾。

只給 main 用，不改共用範本：範本也給 eca-aos-* 這些沒人盯著的 agent 用。

## 換上與換回

main 不能替自己換定義，要從外面跑：

```
aos-agent --daemon ~/aos-home/.stack/procs/repo-aos ctl set-def main ~/repo/aos/wf/ws/main/def
```

換回範本：同一行，最後換成 `~/repo/aos/proto8/templates/agents/eca-claude`。stack（對話、信箱）與工作區不動。

範本之後有改的話，這份不會跟著改，要手動對照 `cli.json` 以外的檔。
