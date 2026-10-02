# daemon 協議：重讀設定模組

← [daemon 協議](README.md)｜[共用約定](../../../protocol/README.md)｜行為正本：[B-642](../../daemon/reload.md)｜[慣例](../../conventions.md)

本篇只有 P-122，只寫格式。重讀做什麼、怎麼比對清單，以 [B-642](../../daemon/reload.md) 為正本。

依據：[verdicts 11 篇末「2026-10-01 第十一批：daemon 模組」](../../../../notes/verdicts/11-tick-as-unit/13-1001-第十十一批.md#2026-10-01-第十一批daemon-模組)、[plan m3m 模組一](../../../../plan/m3m-daemon-modules.md#模組一重讀設定modulesreload)；現行程式 [重讀設定](../../../../src/py/README.md#重讀設定與記住狀態m3m)（有出入以程式為準）。

## P-122．重讀設定：設定、訊號與輸出〔使用者 2026-10-01 第十一批；格式照現行程式〕

### 設定

daemon 設定檔（[P-120](core.md)）頂層 `modules` 裡寫：

```json
{"modules": {"reload": {}}}
```

`reload` 是物件，裡面沒有鍵（有寫就開；裡面寫了別的鍵照收不理）。schema 見 [daemon-core-config](../../../protocol/schemas/daemon-core-config.schema.json) 的 `modules.reload`。

### 訊號

| 訊號 | 掛了模組 | 沒掛 |
|---|---|---|
| SIGHUP | 重讀 `--config` 那份設定檔；重讀中又來幾次，讀完再重讀一次 | Python 預設：daemon 被殺（結束狀態是被 SIGHUP 殺掉，不是 0／1） |

SIGINT／SIGTERM 照 [P-120](core.md)。

### stdout

格式同 [P-120](core.md)：每行開頭是本地時間、空一格接內容。一次重讀依序印：

| 什麼時候 | 內容 |
|---|---|
| 頂層 `cwd` 跟開起來時不同（照起點的算法比對） | `reload: need restart: cwd` |
| 頂層 `modules` 跟開起來時不同 | `reload: need restart: modules` |
| 頂層 `exec_out_path` 跟開起來時不同（比設定裡的原字）〔第十二批〕 | `reload: need restart: exec_out_path` |
| 頂層 `exec_err_path` 跟開起來時不同〔第十二批〕 | `reload: need restart: exec_err_path` |
| 鎖檔路徑（`lock_path` 算出來的）跟開起來時不同〔第十九批〕 | `reload: need restart: lock_path` |
| 拿掉一項（每項一行） | `inst=<inst 字面值> removed` |
| 加了一項（每項一行） | `inst=<inst 字面值> added`；掛了 cgroup 模組時緊接著 `inst=<inst 字面值> cgroup=i-<h>`（[P-124](cgroup.md)） |
| 套用完 | `reloaded` |

```text
2026-10-01T16:45:49+08:00 reload: need restart: cwd
2026-10-01T16:45:49+08:00 inst=c.json removed
2026-10-01T16:45:49+08:00 inst=b.json added
2026-10-01T16:45:49+08:00 reloaded
2026-10-01T16:45:49+08:00 inst=b.json exit=0 ms=25
```

- 設定改了、鍵還在的項不另外印（`status` 看得到）。
- 拿掉的項正在跑時，那次的 `exit=` 行照樣印，可能在 `removed` 之後。
- 沒有任何變化時只印 `reloaded`。

### stderr

重讀時設定壞了（讀不到、不是 JSON、指示詞錯、缺 `interval_ms`、型別錯；掛了 cgroup 模組時建框、寫上限失敗……），整份不套用，印一行：

```text
aos-daemon: reload: <說明>
```

指示詞錯時 `<說明>` 開頭是代號（同 [P-120](core.md)「daemon 自己的 stderr」，例如 `ReferenceJsonInvalid: …`）。這時 stdout 不印 `reloaded`。

### 結束碼

不變（[P-120](core.md)）。重讀出錯不退出。

依據：使用者 2026-10-01 第十一批（R1～R4 照 plan 建議，R3 改成 stdout 警告）；第十二批 `exec_out_path`／`exec_err_path` 改了也只警告、不套用。
