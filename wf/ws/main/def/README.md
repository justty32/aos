main（這個 repo 的主線 agent）專用的定義：照 [eca-claude 範本](../../../../proto8/templates/agents/eca-claude/README.md) 原樣複製，只改 `cli.json` 兩格，讓使用者在手機上（`/remote-control`）好用。

# main 的定義（手機用）

← [main 筆記](../notes.md)｜範本說明：[eca-claude](../../../../proto8/templates/agents/eca-claude/README.md)

使用者 2026-11-27 11:51（家機，要出門、下午只用手機）：「我想請你修改一下自身設定，讓你自己可以發artifact，可以跳選項給我，一些基礎的功能都要有，這樣我在手機上比較好使用。好了之後跟我說，我重開session。然後我會用/remote-control啓用遠端」

## 跟範本差在哪

`cli.json`（11-27 午最後的版本）：

| 改了什麼 | 為什麼 |
|---|---|
| `--tools`、`--allowedTools` 多加 `AskUserQuestion`、`Artifact`、`ArtifactComments`、`ArtifactData`、`ArtifactCheck`、`WebSearch`、`WebFetch`、`ToolSearch`、`Monitor`（`--allowedTools` 另多加 `Agent,Skill`） | 在手機上跳選項給使用者點、用 artifact 給他看結果、上網找輪子 |
| `--permission-mode` 改成 `default` | 11-27 實測：在 dontAsk 下，`AskUserQuestion` 就算列進放行清單也一律被拒。改成 default 後，放行清單裡的工具不問就做；清單外的工具在畫面上（含 remote control）問人，沒有畫面的 `claude -p` 照舊拒絕 |

經過：公司帳號（`~/.claude-alt`）的政策是 `allow_remote_control: false`。中間試過接 Discord：官方外掛、`--channels`、拿掉 `--strict-mcp-config`，後來使用者改成「main 用個人帳號 `~/.claude` 開畫面、走 remote control；工作交給 main-alt（`eca-claude-alt`）」，Discord 那套就全拿掉了。紀錄在 git 歷史與 `wf/HANDOFF.md`。這份定義不寫死帳號，帳號由開畫面那個殼的 `CLAUDE_CONFIG_DIR` 決定。

只給 main 用，不改共用範本：範本也給 eca-aos-* 這些沒人盯的 agent 用，它們跳選項會一直卡著等人。

## 換上與換回

main 不能替自己換定義，要從外面跑：

```
aos-agent --daemon ~/aos-home/.stack/procs/repo-aos ctl set-def main ~/repo/aos/wf/ws/main/def
```

換回範本：同一行，最後換成 `~/repo/aos/proto8/templates/agents/eca-claude`。stack（對話、信箱）與工作區不動。

範本之後有改的話，這份不會跟著改，要手動對照 `cli.json` 以外的檔。
