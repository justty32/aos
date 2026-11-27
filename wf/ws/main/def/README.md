main（這個 repo 的主線 agent）專用的定義：照 [eca-claude 範本](../../../../proto8/templates/agents/eca-claude/README.md) 原樣複製，只改 `cli.json` 兩格，讓使用者在手機上（`/remote-control`）好用。

# main 的定義（手機用）

← [main 筆記](../notes.md)｜範本說明：[eca-claude](../../../../proto8/templates/agents/eca-claude/README.md)

使用者 2026-11-27 11:51（家機，要出門、下午只用手機）：「我想請你修改一下自身設定，讓你自己可以發artifact，可以跳選項給我，一些基礎的功能都要有，這樣我在手機上比較好使用。好了之後跟我說，我重開session。然後我會用/remote-control啓用遠端」

## 跟範本差在哪

`cli.json` 的 `--tools` 與 `--allowedTools` 都多加這幾支（dontAsk 下不列進 `--allowedTools` 就會被拒）：

| 工具 | 用途 |
|---|---|
| `AskUserQuestion` | 跳選項給使用者點 |
| `Artifact`、`ArtifactComments`、`ArtifactData`、`ArtifactCheck` | 發 artifact（手機上看表、圖、報告） |
| `WebSearch`、`WebFetch` | 上網查（使用者 11-27「實作的時候先上網去看看」） |
| `ToolSearch` | 叫得出延後載入的工具 |
| `Monitor` | 等背景工作的條件 |

另外 `--permission-mode` 從 `dontAsk` 改成 `default`，`--allowedTools` 多列 `Agent,Skill`。11-27 午實測：在 dontAsk 下，`AskUserQuestion` 就算列進 `--allowedTools` 也一律被拒；`Artifact` 照樣能發。改成 default 後，列進放行清單的工具不問就做，清單外的工具在畫面上問人，`claude -p` 照樣拒絕。

只給 main 用，不改共用範本：範本也給 eca-aos-* 這類沒人盯的 agent 用，它們跳選項會一直等人。`claude -p` 實測寫錯的工具名會被略過，不會起不來；`AskUserQuestion`、`Artifact*` 在 `-p` 看不到，要互動畫面才驗得到。

## 換上與換回

main 不能替自己換定義，要從外面跑：

```
aos-agent --daemon ~/aos-home/.stack/procs/repo-aos ctl set-def main ~/repo/aos/wf/ws/main/def
```

換回範本：同一行，最後換成 `~/repo/aos/proto8/templates/agents/eca-claude`。stack（對話、信箱）與工作區不動。

範本之後有改的話，這份不會跟著改，要手動對照 `cli.json` 以外的檔。
