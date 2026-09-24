# 規模：上萬顆時保證什麼、不保證什麼

← [spec 導航](README.md)｜每格：[kernel-tick](kernel-tick.md)｜daemon 一圈：[daemon-reconcile](daemon-reconcile.md)

> 第 1 版，2026-09-24 草稿；未實作。新檔，proto5 沒有對應的節。

下面的 N＝cpu 總數（上萬），「有事的」＝這一格／這一圈真的有變化的東西（新單、回音、死掉的、要拉的、要收的）。

## 1. 保證

| 誰 | 每格／每圈的工作量 |
|---|---|
| kernel 一格 | O(`K/requests/` 項目數＋上一格派的＋`sweep`＋池數＋`skip` 長度＋這格派的×log＋丟掉的舊排隊格＋出貨)，**加上讀、寫整份帳本**（§2） |
| daemon 一圈 | O(新單＋死掉的＋這圈拉的＋階梯到期的＋有變的池)；收屍用 `waitpid(-1)`，不逐顆問 |
| kernel ↔ daemon | 只在池的數字變了（或 boot、halt）才有一張 scale 單，一池一張，跟池大小無關 |
| 回音漏通知 | 最慢 ⌈忙的數 ÷ `sweep`⌉ 格被巡檢撿到（1 萬顆忙、`sweep` 32、一格 1 秒 ≈ 5 分鐘） |

## 2. 還是 O(N)、這一版接受的

| 哪裡 | 多大 | 為什麼先接受 |
|---|---|---|
| **kernel 帳本整份讀、整份寫**（每格讀一次、寫最多四次；閒著的一萬顆也要讀一遍 `free`） | 跟 `procs`＋`busy`＋`free`＋`skip` 成比例；1 萬顆全忙約 3 MB | 拆帳本會動到 [aos-agent.md §10](../../proto5/spec/aos-agent.md) 偷看 `procs` 的做法（那份不改）；先量再說 |
| 池的集合重算 | O(池大小) | 只在 info 的數字變了、在途單結清、縮小中的號**全部**做完時（不是每做完一顆） |
| kernel boot | 建家「缺的補齊」、重建 `free`、`recent`＝全部忙的 | 只在 boot |
| daemon 啟動 | 讀全部 `kids/`、殺上一任的孩子、把全部成員排進 `pending` | 只在啟動；拉回來受 `spawn_per_sec` 節流 |
| `ls --pool`、`cpu ls --pool`、`aos-daemon ls` 數忙 | O(池大小)，逐顆偷看 | 人偶爾打的指令，不在每格裡 |
| `skip` 長度（在 info、帳本、scale 單、`pool.json` 裡） | 退休的號越多越長；每格比對 `want` 要 O(`skip` 長度) | 只有 `cpu rm P/<i>` 會加；CLI 寫入時丟掉超過最大成員號的項目 |

## 3. 不在程式裡、但上萬顆一定會撞到的

這些不是規範能保證的，列出來讓使用者決定要不要處理（見 [README](../README.md) 要使用者拍的）：

1. **每顆 cpu 是一支 Python 行程**：閒著也佔約 10～20 MB 記憶體；1 萬顆≈100～200 GB。使用者說「新建一顆 cpu 成本很低」——以現在的 `aos-cpu` 實作不成立，要改寫（例如一支行程管多個家）或換語言。
2. **每顆 cpu 每 `poll_ms` 掃一次自己的 `requests/`**：1 萬顆、200 ms＝每秒 5 萬次列目錄，機器閒著也在忙。調大 `poll_ms` 就換成派工變慢。
3. **行程數上限**（`ulimit -u`）、**開檔數**（daemon 每個孩子一個 fd，[daemon-reconcile §5](daemon-reconcile.md)）：要系統設定配合。
4. **aos-agent 每格偷看 `K/state.json`**（清檔、`status`）：帳本 3 MB、上萬個 agent 各自每秒讀一次＝每秒讀幾十 GB。這是整個系統最大的 O(N²)。
   可能的方向：kernel 另外維護 `K/procs/<N>` 這種一行程一個空檔，agent 改成看檔在不在（O(1)）。**要改 aos-agent.md，所以不在這份草稿裡動**。
5. **kernel 一條鏈、一格一格跑**：一格的時間隨「有事的數量」變長；同一個反覆行程一格最多派一次。上萬個一秒一次的行程，一格要處理上萬則回音。
6. **磁碟**：每顆一個家、一個 `cpu.log`（不輪替）；家不刪（[kernel-home §4](kernel-home.md)）。`kernel.log` 也不輪替。
7. **`K/requests/` 一個資料夾**：每格列目錄是 O(裡面的項目數)；kernel 落後時通知與 syscall 會堆起來。通知檔名固定、同一則回音不會堆兩張，所以通知數上限＝**還沒被 ack 的回音數**（cpu 開機補丟時也包括 kernel 已結帳、ack 還沒被 cpu 處理的，審查 R22），正常接近忙的 cpu 數。

## 4. 保證外（出事了要人處理）

- 一顆號碼拉不起來（家壞了）而 kernel 已經派單給它：那件工作卡在 `running`。`cpu ls --pool P` 對得出來；**只能把家修好**讓它起來對帳（`rm` 行程、`cpu rm` 都會等它，[kernel-pools §4](kernel-pools.md)，審查 R12）。
- 縮小時被收的號手上那件沒設 `timeout_ms`：縮小一直等。處理：`aos-daemon kill --pool <dpool> <i>`。
- 人用 `aos-daemon scale --force` 改 kernel 的池：兩邊的數字不一致，直到 kernel 下次送單。
- 兩個 boot 同時跑、人手直接跑 `aos-cpu`（同 proto5）。
