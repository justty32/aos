# proto5-2 規範導航

← [proto5-2 README](../README.md)

> 第 1 版，2026-09-24 草稿；未實作。

一個主題一檔、每檔不超過 8 KB。這裡只放**跟 proto5 不一樣的**；沒列的照 [proto5/spec/](../../proto5/spec/)。
每檔開頭都寫了「取代 proto5 哪一節」。

## 先讀

| 檔 | 講什麼 |
|---|---|
| [choices.md](choices.md) | 使用者定的六點各落在哪一檔；我自己選的 22 條；沿用不變的 |
| [scale.md](scale.md) | 上萬顆時保證什麼、還剩哪些 O(N)、哪些撞牆的事要使用者決定 |

## kernel

| 檔 | 講什麼 | 取代 proto5 |
|---|---|---|
| [kernel-info.md](kernel-info.md) | 池表（`info.json` 第 2 版，含範例）；成員編號 `count`＋`skip`；改了什麼時候生效 | kernel.md §1.1 |
| [kernel-home.md](kernel-home.md) | 目錄；池模板 inst、`envs.json`；cpu 的家怎麼建、不刪 | kernel.md §1 目錄、建家 |
| [kernel-ledger.md](kernel-ledger.md) | 帳本第 2 版：`pools`、`busy`、`ready`／`delayed`、`sends`；一格最多寫四次 | kernel.md §1.2、§3 第 4 步的寫法 |
| [kernel-tick.md](kernel-tick.md) | 一格十步；回音通知＋`recent`＋巡檢；派工從閒號堆疊拿 | kernel.md §3 |
| [kernel-pools.md](kernel-pools.md) | info 變了怎麼長大、先做完再收、scale 單的收發與崩潰窗口 | kernel.md §1.1 末、§3 第 7 步 |
| [kernel-cli.md](kernel-cli.md) | `init --config`、`cpu add／rm／ls`、按池的 `ls`、`halt`、`check` | kernel.md §6 |

## daemon

| 檔 | 講什麼 | 取代 proto5 |
|---|---|---|
| [daemon-home.md](daemon-home.md) | `pools/<pool>/pool.json`（宣告）、`kids/<i>.json`（一顆一檔）、`summary.json`；info 新鍵 | daemon.md §1.1、§1.2 |
| [daemon-reconcile.md](daemon-reconcile.md) | 狀態機、一圈、退避與令牌桶節流、只留一條 pipe、批次階梯、`halt` | daemon.md §4、§5 做法、§9 第 1、2 條 |
| [daemon-cli.md](daemon-cli.md) | `boot／halt／ls／scale／kill`，全帶 `--pool` | daemon.md §6、§7 |

## 兩邊之間

| 檔 | 講什麼 | 取代 proto5 |
|---|---|---|
| [protocol.md](protocol.md) | JSON-RPC 方法 `scale`／`kill`／`ls` 的 params 與回音、拿掉 `spawn`、崩潰窗口表、檔名 | daemon.md §3、kernel.md §5 |
| [handoff.md](handoff.md) | kernel boot 怎麼交接 kernel 池、daemon 重開怎麼把池拉回來、兩種停機 | kernel.md §6 boot、daemon.md §6.1 第 5 步 |
| [cpu-notify.md](cpu-notify.md) | cpu 多一個 `notify` 欄位：回完音往 kernel 家丟 `resp-` 通知 | 補充 cpu.md §2、§6.1、§6.3 |

## 跟 proto5 不變那幾份的差句

| 檔 | 講什麼 |
|---|---|
| [proto5-diffs.md](proto5-diffs.md) | 「不變」表列那幾份裡，哪一句話落地時其實要換、換成什麼、依據哪一檔（proto5 那邊的字不動） |
