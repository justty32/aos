← [cpu](README.md)｜[spec 總導航](../README.md)

## 6.4 回完音丟一張通知（`notify`）

（2026-09-24 proto5-2 池式納入，新節。）沒寫 `notify` 的 cpu 行為跟以前一模一樣。

為什麼要動 cpu：使用者 09-24 定「cpu 有回音時往 kernel 家丟一個通知檔，kernel 只掃那個目錄」（[kernel §9](../kernel/README.md) 第 f 點）。
cpu 只知道自己的家，要它通知別人，得在它的設定裡寫「通知丟到哪」：`info.json` 的 `notify`（[§2](layout.md)）。
kernel 建工作 cpu 的家時寫成 `K/requests`（[kernel §1](../kernel/home.md)）。（第 2 版的 kernel 池那顆不寫；2026-09-24 one-boot 起沒有那顆了。）通知一丟進 `K/requests/`，daemon 看到新檔就馬上替 kernel 開一格（[daemon §10](../daemon/ticks.md)）。

### 通知長怎樣

照 §3.1 放單（同目錄 `.tmp` → `link` → 刪 `.tmp`），檔名與內容：

```text
resp-<digest>.json
```

```json
{"jsonrpc": "2.0", "method": "responded", "params": {"home": "/abs/K/pools/default/cpus/3", "name": "k-1790000000000000000-4242-41-default-3.json"}}
```

- notification（沒有 `id`），收的人不回音。`home` 是這顆 cpu 家的絕對路徑，`name` 是那則 request 的檔名。
- `digest`＝`home` 絕對路徑＋換行＋`name` 的 SHA-256 前 16 個十六進位字元。同一則回音不管補丟幾次都是同一個檔名，EEXIST＝已經丟過，當成功。
- `resp-` 是規定的前綴（同 `ack-`／`stop-`，收的人只看前綴分類）。
- 只有**有 id 的 request** 才會有回音、才會通知；notification 類的單不通知。

### 什麼時候丟

**迴圈**（§6.3）多一步 (4.5)，**一定在 (4) 刪原單之後**：收件者收回音時先看原單在不在（[kernel §3 第 6 步](../kernel/tick.md)），原單還在就當「在途」跳過；
若通知比刪原單早到，收件者會跳過又把通知刪掉，那則回音就只能等它自己的巡檢。
放失敗只記 stderr 一行 `NotifyFailed`，不退出、不重試。

**啟動**（§6.1 第 5 步，開機對帳之後、進迴圈之前）：對 `responses/` 裡**每一份**回音（只認 `.json` 結尾的檔）補丟一次通知（EEXIST 當成功）。這一步補的是：
- 上一任崩在 (3)～(4.5) 之間：回音在、通知沒丟。
- 開機對帳剛補寫的 `Interrupted` 回音。

`responses/` 裡只有還沒被 ack 的回音，正常是 0～1 份，所以這一步很便宜。

### 通知不是保證

通知只是「提早說一聲」。丟失敗、丟到一半崩掉、這顆 cpu 被收掉不會重生——收件者（kernel）都靠巡檢與 `recent` 補（[kernel §11](../kernel/scale.md)）。
所以 cpu 不為通知重試、不為通知退出，也不在 `state.json` 記通知狀態。

### 沒選的做法

- **inotify／fanotify**：只有 Linux、跨檔案系統行為不一，而且全系統現在只靠「放檔、偷看」兩招，不想多第三招。
- **通知放在 kernel 家以外的專用資料夾**（例如 `K/notify/`）：規則一只准外人往 `requests/` 放檔，另開資料夾等於多一條規矩。
- **把 `notify` 放進每張工作單的 params**：params 規定一對一是 aos-exec 的命令列（§4.1），塞別的東西會破這條。
