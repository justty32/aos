← [入口](README.md)｜涵蓋：規劃 › 4. 資料夾程式長什麼樣、怎麼請 daemon 掛起、5. 使用者在 shell 怎麼用｜上一份 [05-3-loop-那半-控制器](05-3-loop-那半-控制器.md)｜下一份 [07-6-要動的程式與步驟表-不實作](07-6-要動的程式與步驟表-不實作.md)

### 4. 資料夾程式長什麼樣、怎麼請 daemon 掛起

```
agents/resident_bob/            ← C-54：資料夾名小寫加底線
  _entry                        ← install（Python）：建 bob 小格與 FIFO、add bob（有殘留就 --resume）、add bob_ctl
  README.md                     ← 玩法與眉角
  bob/
    _entry.json                 ← 第 2 節那張單子
    system.txt
  ctl/
    _entry.json                 ← {"argv": ["aos-loop", "loop.json"], "stdout": FIFO}
    loop.json                   ← {"exec": "relay", "interval_ms": 300}
    relay/
      _entry                    ← 第 3 節的身體（Python）
```

- **`_entry`（install）做四件事然後結束**——這就是「配合 daemon 進行 exec 和 loop 的掛起」：① 沒有 daemon 的 stack 變數＝退 1 `DaemonMissing`（N-63）；建 bob 小格、`mkfifo in.fifo`（已在就跳過）。② 控制器小格的 `relay_state.json` 有 `session_id`＝`add --name bob <自己>/bob -- --resume <id>`，沒有＝`add --name bob <自己>/bob`。③ `add --name bob_ctl <自己>/ctl/_entry.json`。④ 印一句怎麼對它說話。不留行程；跑第二次＝重掛（表上已有的照 N-54 不重起）。寫 Python 不寫 sh（user/03）；位置用 `__file__`（realpath）算。
  - **先 add bob 再 add bob_ctl**：兩邊開 FIFO 互等、誰先都接得上；但只掛控制器沒掛 bob，控制器會一直卡在 `open`，表上 `running` 卻什麼都沒做。
  - 殘留的 session 接不回：bob 起來就退非 0 → `relay` 退 1；刪掉 `relay_state.json`（或只刪 `session_id`）重跑 install 就是新對話。
  - 工作區：兩個子項都不給 `--ws`＝繼承 daemon 的 `AOS_WS`。
- **daemon 要把自己的 stack 設給子項**：控制器的單子（FIFO 路徑）、`relay`（讀名單窗、叫 `aos-daemon-ctl`）都要知道 daemon 的 stack；兄弟之間沒有父子交代，只有共同的上一代能告訴他們（N-64 ④；[衝突 2](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-2兄弟要共用位置--daemon-得把-aos_daemon_stack-設給子項)）。只設這一個。
- **daemon.json 不用改**：bob 與 bob_ctl 用信掛、不寫進 daemon.json，daemon 重起不會自動回來（[衝突 4](12-要使用者看的衝突與方向題-11-02-晚.md#衝突-4n-28子項結束不重起vs常駐)）；寫死進 daemon.json＝開機掛、新對話（`--resume` 寫不進靜態檔），FIFO 仍要先建。

### 5. 使用者在 shell 怎麼用

- 掛上：daemon 起著、設好 daemon 的 stack 變數後 `aos-exec ../agents/resident_bob`；`aos-daemon-ctl ls` 看到 bob、bob_ctl 兩個都 running 才算掛好。
- 說話：`aos-say --stack <控制器小格> 話`、`aos-listen --stack <控制器小格>`（`--last N`、`--follow` 照用）；連丟幾句忙時會併成一題、一個回答回好幾封（正常）。
- 看：bob 小格的 `out.jsonl`（原汁事件流）與兩邊的 `stderr.txt`；控制器小格的 `relay_state.json`、`mailbox_warning.txt`。
- 停：寫控制器的 `ctl.json` 停（最溫和：bob 答完手上那題退 0）或 `aos-daemon-ctl rm bob_ctl`；急停 `aos-daemon-ctl rm bob`（bob 立刻退 143、丟掉手上那題，控制器下一輪退 1）。
- 再起來＝再跑 install，續接同一段對話；要開新對話先刪 `relay_state.json`。
