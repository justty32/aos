# 方案 (b) 停車＋喚醒：規則與不漏喚醒的時序

← [本題 README](README.md)｜審查：[review-astra.md](review-astra.md)（第 1～6、14 條都改進這份）

**還是提案，沒改規範。** 這裡把 (b) 寫到「照著能改規範」的程度，讓使用者看得出 kernel 到底多了什麼。

## 1. kernel 多的東西

| 哪裡 | 多什麼 |
|---|---|
| `add` 的 params | 可省的 `wake: NAME`（要叫醒的反覆行程名）。舊 kernel 看不懂的欄位本來就忽略，所以不會退件 |
| 登記這張單時 | kernel 自己順手記下「喚醒對象的那一代」：`wake_gen`＝當下 `procs.NAME.request`（NAME 登記那張 add 的檔名）；NAME 不在就不記、之後不叫 |
| 回音待辦（`replies` 的每一筆） | 多帶 `wake`、`wake_gen`。**這張 add 的最後一則回音不管怎麼來都要帶**：正常跑完、失敗、`Removed`（被 rm）、`Stopping`（停機取消）、收單時就退件（審查第 2 條） |
| 反覆行程紀錄 | 多一個 `woken`（布林）與政策 `park_ms`（add 時給，沒給用 info 的預設，例如 300000） |
| 回音判定（proto5 kernel echo.md 那張表） | 多一列：`code = 102` → `runs+1`、`fails` 歸 0、`not_before = 現在 + park_ms`（**停車**）；但 `woken` 是真的 → 當成 101（照普通 `interval_ms`）。判完這格，`woken` 清掉，**跟判定同一次存帳本** |
| 出貨（寫回音檔那一步） | 放好回音檔（EEXIST 當已放）之後、**跟「把這筆從 `replies` 拿掉」同一次存帳本**，照第 2 節叫醒 |

## 2. 叫醒一個行程

先找 `procs.wake`：不在、`request` ≠ `wake_gen`（同名重登記的是新的一代）、`status` 是 `bad`／`done`、或它正跑的那格標了 `discard`（被 stop 了）→ **什麼都不做**（審查第 4 條）。否則：

- `running`（正在跑）→ `woken = true`，不另排。
- `queued` 而且 `not_before` 還在未來（停著）→ `not_before = 現在`。proto5 它本來就在 `queue` 裡，下一次派工就撿得到；
  proto5-2 推一筆新的進它池的 `ready`，`delayed` 裡那筆因為「時間對不上」變舊格丟掉（舊格計數照 kernel-ledger §2 攤還）。
- `queued` 而且 `not_before` 已經到了（本來就能派、proto5-2 已在 `ready`）→ **什麼都不做**，免得 `ready` 裡疊兩筆（審查第 3 條）。

**叫醒只代表「最早下一次派工就能派」**，池滿了照樣排隊（審查第 14 條）。

## 3. 為什麼不漏（逐個時序）

| 情況 | 結果 |
|---|---|
| 回音檔還沒落地 agent 就先看了（proto5 一格裡派工在出貨之前） | 叫醒放在出貨、回音檔放好之後，agent 不會在「被叫醒」之後還看不到檔 |
| agent 正在跑、它看的時候回音還沒到，跑完退 102 | 出貨時它是 `running` → `woken`；判定時 102＋`woken` → 當 101，下一格再看 |
| 崩在放好回音檔之後、存帳本之前 | 下一格第 4 步重做出貨：回音檔 EEXIST 當已放、叫醒再做一次；叫醒本身重做無害 |
| 崩在收回音（寫進 `replies`）之後、出貨之前 | `wake` 跟著回音待辦存在帳本裡（審查第 1 條），下一格出貨照樣叫 |
| agent 收批、ack、清檔（sweep） | 都在 agent 自己那格；先存 `done` 再 ack、結清後才清檔的順序不變，不會讓已叫醒的事消失（審查第 6 條確認） |
| act 批有好幾個工具 | 每件回來各叫一次；第 2 節的規則讓它們合併成「最多再排一格」，收批會逐件查 |
| once 被 `rm` 或停機取消 | 取消的回音也帶 `wake`，一樣叫醒；agent 收到 `Removed`／`Stopping` 照 collect.md 記失敗 |
| agent 被 stop 再 start（同名新一代） | `wake_gen` 對不上，舊單回來不會叫醒新的；新的一代剛 start 本來就會跑 |

**只有 agent 自己能退 102 的地方要守住**：只在「批在途、這格什麼都沒收到、什麼都沒寫」（現在 `collect` 回 101 的那個出口）改退 102。
門關著（`gate` 回 101）即使有在途批也照舊退 101——門是外人開的，kernel 叫不到（審查第 6 條）。

## 4. 保底 `park_ms` 補的是什麼

- 程式錯。
- 第 2 步的 idle 停車：`aos-agent say` 放好輸入、還沒投 `wake` 就被殺——這**是正常的崩潰窗口**，不是程式錯（審查第 5 條）。
  接受「最慢 `park_ms` 才發現」就不用多做；要崩了也準，得把「輸入＋喚醒」做成可恢復的待辦，這版不提。
- 外人直接丟檔進 input、touch 門檔，沒投 `wake`。

## 5. 改多少（重估）

第一次估「20～30 行」太樂觀（審查第 14 條）。算上待辦帶欄位、取消與退件路徑、`woken`、102 那列、能力標記、`ls` 顯示，
**proto5 kernel 估 50～80 行＋崩潰測試（每個「崩在哪兩步之間」一條）**；規範動 kernel 的 syscall、echo、tick、ledger 四檔。
agent 那邊：send.md（帶 `wake`）、tick.md 退出碼表（102）、register.md（`start` 要確認 kernel 認得停車——舊 kernel 把 102 當失敗，十次就 bad；
`done_exit` 也要擋 102），程式十幾行。
