← [daemon 協議：啟動、設定與 IPC](../startup-and-ipc.md)（分檔 3/3）｜[上一份](02-P-101-設定檔欄位.md)

## P-102．sudo 與 helper 生死〔使用者方向 2026-09-29〕

> **暫緩**（2026-10-01）：sudo 模式與 helper 生死；最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。〔2026-10-01 第十三批〕**部分已被 [P-126](../../../../protocol/daemon/account.md) 取代**（帳號模組：sudo 開、另開 root 端、主程式永久降權、root 端讀到 EOF 就退出）；其餘暫緩。

啟動模式、`SUDO_UID`、永久降權、kill helper 不重拉、daemon 死了 helper 跟著退出，全部照 [B-303](../../../helper.md)。

**PID 提示檔**（什麼時候寫、刪，舊檔怎麼看，見 [B-603](../../../daemon/lifecycle.md)）：

| 檔 | 內容 |
|---|---|
| `state_dir/helper.pid` | 一行 PID；沒 helper 寫 `none` |
| `state_dir/daemon.pid` | 一行 PID |

helper PID 另照 P-101 印在 stdout。helper 的設定副本、父死監看與失聯見 [B-601](../../../daemon/runtime.md)；熱重載的界線見 [B-608](../../../daemon/reload.md)。

## P-103．IPC 封包與授權〔建議預設，未拍板〕

> **部分已被取代、其餘暫緩**（2026-10-01）：控制用的部分被 [P-121](../../../../protocol/daemon/control.md) 取代：一連線一請求、一行 JSON、指令名當鍵、能連就能用不驗身分、不認得的欄位忽略；`RpcRequest`／`RpcResponse` 封包、附 fd、依 socket 對面帳號授權暫緩，最核心 daemon 第一版不做（使用者 2026-10-01）。條號保留、不重用。

### 封包

- Unix stream；UTF-8 JSON，每行一筆、LF 結尾；含 LF 最多 262144 bytes。
- 不用 batch，也不用 notification。
- 請求與回應沿 [common](../../../../protocol/schemas/common.schema.json) 的 `RpcRequest`／`RpcResponse`；`params` 必填 object。
- 每條連線逐筆處理，回應沿用請求 ID。
- **附 fd**：只有 `node.provision` 的 `spawn_as` 在請求那一行附 SCM_RIGHTS fd（[P-107](../provision-and-runner.md)，第十九批）；其他請求附了 fd，就關掉 fd 並回 `invalid_params`。

### 誰可呼叫

每個 method 誰可呼叫、帶憑證時怎麼讀、授權順序與斷線後不准盲重送，以 [B-601](../../../daemon/runtime.md)「IPC 授權與身分額度」為正本（astra 審整理區必-8 從本條搬上）。
