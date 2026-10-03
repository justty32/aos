# nest3：路一三層巢狀 daemon

**是什麼**：根 daemon D0 的 node `L0` 有一個 keep 任務 `aos7-daemon $AOS7_TASK/mnt/d1`，用來開子 daemon D1，根在 `L0/d1root`。D1 的 `L1` 再用同樣的方式開 D2（`L1/d2root`），D2 的 `L2` 跑普通任務（`q` 每回合跑一次、`s` 常駐 sleep）。分三場：

1. **主場**：子根先建好 `.aosd/`。
2. **頑固場**：L2 多一個不理 SIGTERM 的任務。
3. **P-11 場**：不先建 `.aosd/`。

**想逼出的**：三層起不起得來；pause、kill、stop 會不會往下傳；上層看不看得到下層；kill 的 1 秒寬限（P-04）在三層時夠不夠。

**結果**（跑 3 次都綠，約 9 秒）

| 量 | 數字 |
|---|---|
| 起 D0 到 L1／L2 第 1 回合 | 0.10／0.15～0.21 秒 |
| 同一瞬間的回合數 L0／L1／L2 | 3／3／3（interval 都 100 ms） |
| pause L0 的 0.6 秒內各層回合增加 | 0／6／6（pause 不往下傳） |
| ctl kill D1（SIGTERM）到拿到回條 | 0.15 秒，`killed`，D1 結束碼 0 |
| ctl kill D1 到 L2 再前進 2 回合 | 0.41～0.52 秒（keep 起回 D1，D1 再起 D2） |
| kill -9 D1 到新的 D1 寫出 status | 0.10～0.15 秒 |
| 主場最上層 stop --kill 到 D0 退出 | 0.11 秒，0 個孤兒 |
| 頑固場 stop --kill 到 D0 退出 | 1.11～1.19 秒，D1 結束碼 -9。**大約一半的次數**剩 2 個孤兒（頑固任務的 aos7-run 和 sleep） |

**發現**

- **上層看不到下層**：D0 的 status 對下層只有一個活任務名 `d1-r1`。要看 D1、D2 的健康和回合，只能自己去翻 `L0/d1root/.aosd/status.json` 這類路徑，沒有任何彙整。下層的 `status.root` 是任務掛載點路徑，每多一層就多一段 `.aos/tasks/<tid>/mnt/<名>`（D2 長 88 字）。D1 一重啟，這個字串就換了。
- **kill 子 daemon 會順手殺掉它正在跑的 tick／tock**：kill 是對程序群組送 SIGTERM，tick、tock 也在這個群組裡，會一起被殺（rc -15）。tock 被殺，那一回合就沒有總結（跳號）。tick 被殺後，daemon 收尾時會對**上一個已經關掉的回合**再 tock 一次，rounds.jsonl 就出現**兩行同一個回合**（實測 `[…, 9, 10, 10, 11]`）。中間層每被 kill 一次，大約有一半的機會碰到其中一種。
- **kill -9 中間層**：D2 不會死（P-04），變成沒有 daemon 管的程序。好在新的 D1 照 pid.json 把它當成「活著的 d2 任務」，不會再起第二個 D2，最上層 stop 時也收得到它。孤兒 D2 的 root 仍指向已經死掉的 D1 任務的掛載點，只要那個任務資料夾沒被刪就還能用。kill -9 那一回合 L1 沒有 tock，總結會跳號。
- **1 秒寬限不夠三層用**：D0 等 D1 1 秒、D1 等 D2 1 秒、D2 收頑固任務也要 1 秒，三個 1 秒幾乎同時到期。D1 一定會被 SIGKILL；D2 是被 SIGKILL 還是自己收完，看誰先到。被 SIGKILL 的話，頑固任務就成了孤兒。
- **P-11 三層更糟**：D0 第一次掃描就把 `L0/d1root/L1` 和 `…/d2root/L2` 當成自己的 node，替 L1 起了 d2。L1 的 `mounts: {"d2": "L1/d2root"}` 是相對**空間根**，被 D0 照 D0 的根解讀，結果在 D0 根底下多出 `L1/d2root`，D2 就起在這個空的錯誤位置。D1 起來後接手 L1，看到 d2 這個名字還活著，就不再起 D2，結果 **L2 改由 D1 管，三層悄悄塌成兩層**。D0 當初起的 `s-r1`（birth.json 的 node id 是 `L0/d1root/L1/d2root/L2`，AOS7_ROOT 是 D0 的根）仍被當成活任務繼續用。
