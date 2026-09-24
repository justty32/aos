← [daemon](README.md)｜[spec 總導航](../README.md)

# 3. method（`D/requests/`）

| method | params | 回音 |
|---|---|---|
| `spawn` | `name` 必填（合法檔名）；`target` 必填（絕對路徑）；`dir_target` 可省；`restart` 布林，預設 false | `{"pid"}`。看同名的那筆：**沒有**＝拉、登記、回新 pid。**有、`target`＋`dir_target` 都一樣**：`running`＝什麼都不做、回它的 pid（`restart` 不同就更新成新的）；`dead`＝取消等待、現在拉、回新 pid；`killing`＝`-32000`／`Killing`。**有、目標不一樣**＝`-32000`／`NameTaken`（不管活不活）。起不來＝`SpawnFailed` |
| `kill` | `name` 必填 | `{"pid"}`，立刻回。`running`＝`state=killing`、走 §5 的階梯；`dead`＝取消重拉、直接從表拿掉；`killing`＝已經在走，不重設期限。死透了從表裡拿掉、**不重拉**。不在＝`NotFound` |
| `stop` | notification | 整個 daemon 停機（§5） |
| `ack` | 範式 §3.3 | 別人收了 `D/responses/` 的回音要放 ack |

沒有 `ls`：偷看 `state.json`。`stopping` 期間 `spawn` 一律回 `-32000`／`Stopping`；`kill` 照常。
params 形狀不合＝`-32602`。回音、原單、ack 的處理照範式 §6.3；daemon 自己崩在中間，重啟照範式 §6.2 對帳
（`current` 那格就是為這個）。
