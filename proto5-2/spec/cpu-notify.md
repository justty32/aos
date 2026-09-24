# cpu 回完音丟一張通知（`notify`）

← [spec 導航](README.md)｜kernel 怎麼收：[kernel-tick](kernel-tick.md) 第 5、6 步｜範式本體：[proto5/spec/cpu.md](../../proto5/spec/cpu/README.md)

> 第 1 版，2026-09-24 草稿；未實作。**補充 [proto5/spec/cpu.md](../../proto5/spec/cpu/README.md) §2（多一個 info 欄位）、§6.1（啟動多一步）、§6.3（迴圈多一步）**。
> cpu.md 其他部分不變。沒寫 `notify` 的 cpu 行為跟 proto5 一模一樣。

為什麼要動 cpu：使用者定的第 f 點是「cpu 有回音時往 kernel 家丟一個通知檔，kernel 只掃那個目錄」。
cpu 只知道自己的家，要它通知別人，得在它的設定裡寫「通知丟到哪」。

## 1. `info.json` 多一個欄位

| 鍵 | 型別 | 沒寫時 | 意思 |
|---|---|---|---|
| `notify` | 絕對路徑（資料夾） | 無＝不通知 | 每則回音發出去之後，往這個資料夾放一張通知 |

kernel 建工作 cpu 的家時寫成 `K/requests`（[kernel-home §3](kernel-home.md)）。

## 2. 通知長怎樣

照範式 §3.1 放單（同目錄 `.tmp` → `link` → 刪 `.tmp`），檔名與內容：

```text
resp-<digest>.json
```

```json
{"jsonrpc": "2.0", "method": "responded", "params": {"home": "/abs/K/pools/default/cpus/3", "name": "k-1790000000000000000-4242-41-default-3.json"}}
```

- notification（沒有 `id`），收的人不回音。
- `digest`＝`home` 絕對路徑＋換行＋`name` 的 SHA-256 前 16 個十六進位字元。同一則回音不管補丟幾次都是同一個檔名，
  EEXIST＝已經丟過，當成功。
- `resp-` 是規定的前綴（同 `ack-`／`stop-`，收的人只看前綴分類）。
- 只有**有 id 的 request** 才會有回音、才會通知；notification 類的單不通知。

## 3. 什麼時候丟

**迴圈（取代範式 §6.3 的五步）**：

```text
(1) 寫 state.current
(2) 跑
(3) 原子寫 responses/X
(4) 刪 requests/X
(4.5) 有 notify：放通知（失敗只記 stderr 一行 NotifyFailed，不退出、不重試）
(5) 寫 state.current=null、runs+1
```

**一定在 (4) 之後**：kernel 收回音時先看原單在不在（proto5 kernel §3 第 6 步），原單還在就當「在途」跳過；
若通知比刪原單早到，kernel 會跳過又把通知刪掉，那則回音就只能等巡檢。

**啟動（加在範式 §6.1 第 4 步開機對帳之後、進迴圈之前）**：有 `notify` 就對 `responses/` 裡**每一份**回音補丟一次通知（EEXIST 當成功）。
這一步補的是：
- 上一任崩在 (3)～(4.5) 之間：回音在、通知沒丟。
- 開機對帳剛補寫的 `Interrupted` 回音。
`responses/` 裡只有還沒被 ack 的回音，正常是 0～1 份，所以這一步很便宜。

## 4. 通知不是保證

通知只是「提早說一聲」。丟失敗、丟到一半崩掉、這顆 cpu 被收掉不會重生——kernel 都靠巡檢與 `recent` 補（[kernel-tick](kernel-tick.md)「為什麼通知漏了也不會卡死」）。
所以 cpu 不為通知重試、不為通知退出，也不在 `state.json` 記通知狀態。

## 5. 沒選的做法

- **inotify／fanotify**：只有 Linux、跨檔案系統行為不一，而且全系統現在只靠「放檔、偷看」兩招，不想多第三招。
- **通知放在 kernel 家以外的專用資料夾**（例如 `K/notify/`）：規則一只准外人往 `requests/` 放檔，另開資料夾等於多一條規矩。
- **把 `notify` 放進每張工作單的 params**：params 規定一對一是 aos-exec 的命令列（範式 §4.1），塞別的東西會破這條。
