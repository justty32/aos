# daemon 協議：重讀設定模組

← [daemon 協議](README.md)｜行為：[B-642](../../daemon/reload.md)｜[慣例](../../conventions.md)

## P-122：重讀設定：設定、訊號與輸出

```json
{"modules": {"reload": {}}}
```

`reload` 是物件、沒有鍵（有寫就開）。schema：`daemon-core-config.schema.json` 的 `modules.reload`。程式：`aos_daemon_reload.py`。

**訊號**：SIGHUP 掛了模組時重讀 `--config`（重讀中又來，讀完再重讀一次）；沒掛時 daemon 被 SIGHUP 殺掉。SIGINT／SIGTERM 照 [P-120](core.md)。

**stdout**（格式同 P-120），一次重讀依序：

| 什麼時候 | 內容 |
|---|---|
| 頂層 `cwd`／`modules`／`exec_out_path`／`exec_err_path`／`lock_path` 跟開起來時不同 | `reload: need restart: <欄位名>`（不套用） |
| 拿掉一項 | `inst=<inst> removed` |
| 加了一項 | `inst=<inst> added`；掛 cgroup 時緊接 `inst=<inst> cgroup=i-<h>` |
| 套用完 | `reloaded` |

```text
2026-10-01T16:45:49+08:00 reload: need restart: cwd
2026-10-01T16:45:49+08:00 inst=c.json removed
2026-10-01T16:45:49+08:00 inst=b.json added
2026-10-01T16:45:49+08:00 reloaded
```

設定改了鍵還在的項不另外印；沒變化只印 `reloaded`。

**stderr**：重讀時設定壞了（讀不到、不是 JSON、指示詞錯、缺 `interval_ms`、型別錯、cgroup 建框失敗、某項 `mq` 寫了開起來時沒有的門…），整份不套用，印 `aos-daemon: reload: <說明>`（指示詞錯時說明開頭是代號），不印 `reloaded`、不退出。結束碼不變。
