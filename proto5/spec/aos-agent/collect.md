← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 6. 收回

每次（門開著、`batch` 非 null）：

1. `done` 非 null、`acked` 是 false 的先補 ack → 寫 `acked: true`。
2. `sent` 是 false → 先做 §5.2，退 0。
3. 對每筆 `done` 是 null 的 call：`K/requests/N.json` 在＝還沒；不在再看 `K/responses/N.json`：不在＝還沒（還在 kernel 裡）；
   在＝讀（JSON 壞＝退 1、不動任何東西），照 §6.1／§6.2 算出 `done`——要讀 `work/N.out` 的在這一步讀，讀驗不過照表記成失敗，**不留到結清才發現**。
4. 這次有新算出的 → **寫 state**（這幾筆 `done`，`acked` 仍 false）→ 逐則 ack → **寫 state**（`acked: true`）。
5. 全部 `done` 非 null 且 `acked` → 結清（§7）。否則：這次有寫東西退 0，什麼都沒到退 102（09-24 停車；以前是 101）。

ack 的形狀：`K/requests/ack-<epoch ns>-<pid>-<i>.json`（i 是 call 的序號；每則新取名、用 link 放，EEXIST 就換個 ns 再放），內容
`{"jsonrpc":"2.0","method":"ack","params":{"name":"N.json"}}`。多送一次無害（回音已不在＝kernel 當成功）。
程式上：放單＝`aos_client.submit(K, "add", params, name="N.json")`、ack＝`aos_client.ack(K, "N.json")`（取名要補序號）；**不用** `call()`（它同步等、自動 ack）。

等回音**沒有上限**：`timeout_ms` 只限在 cpu 上跑多久，不含排隊、停機、等 boot；不會因為等太久就判「沒送」重送。

## 6.1 think 的 `done`

照順序第一個命中的列：

| 回音 | `done` |
|---|---|
| `result`、`kind=child`、`code=0`、`timed_out=false`、`stopped=false` | 讀 `work/N.out`：去掉結尾換行後要恰好是一個 JSON 物件，照 [agent.md §3.2](../agent/info.md) 驗成模型回的 assistant → `{"ok": true}`；不合 → `{"fail": "MessageInvalid: …", "count": true}` |
| `result.stopped=true` | `{"fail": "被強制停", "count": false}` |
| `result.timed_out=true` | `{"fail": "逾時（T ms，是 info.llm.timeout_ms…；llm.err 在 <路徑>）", "count": true}`（09-24 試玩 r2 補）：寫明是 `info.llm.timeout_ms` 那格；**不附** llm.err 最後一行（被砍的那次通常沒寫新行，最後一行多半是舊的） |
| `result.kind=aos` | `{"fail": "aos-llm call 沒跑起來（kind=aos），看 <K>/pools/<池>/cpus/*/cpu.log", "count": true}`（09-24 試玩 r1 補；池式納入改）：池名取 agent 的 `llm.pool`，池不在 K 的 `info.pools` 就整段池名也寫 `*` |
| `result`、`code≠0` | `{"fail": "aos-llm call exit <code>，看 <agent 絕對路徑>/log/llm.err：<llm.err 最後一行>", "count": true}`（09-24 試玩 r1 補）：最後一行取非空的、最多 300 字；讀不到就只給路徑 |
| `error.data.code=Stopping` | `{"fail": "kernel 停機時取消，沒跑", "count": false}` |
| `error.data.code=Interrupted`／`Removed` | `{"fail": "結果不明（Interrupted／Removed）", "count": true}` |
| 其他 `error` | `{"fail": "kernel 退件：<data.code，沒有就 code>", "count": true}` |

## 6.2 act 的 `done`

`{"content": …}`，照順序第一個命中的列；「輸出」＝`work/N.out` 以 UTF-8 讀、非法位元組換成 U+FFFD，檔不在＝空字串：

| 回音 | `content` |
|---|---|
| `result`、`kind=child`、`code=0`、`timed_out=false`、`stopped=false` | 輸出原樣 |
| `result.stopped=true` | 固定 `{"ok": false, "error": "結果不明：工具可能已經跑了，也可能沒有"}` 的 JSON 字串 |
| `result.timed_out=true` | 「工具 <名> 逾時（T ms）：」＋輸出 |
| `result.kind=aos` | 「工具 <名> 無法執行（kind=aos），詳情在跑它那顆 cpu 的 cpu.log」 |
| `result`、`code≠0` | 「工具 <名> 失敗（exit <code>）：」＋輸出。（09-24 試玩 r1 補）127／126 補一句：「exit 127：找不到程式 argv[0]=…」／「exit 126：不能執行 argv[0]=…」（argv[0] 從 `work/N.inst.json` 讀；相對路徑再補一句相對哪個 cwd、不含 `/` 的照 cpu 的 PATH 找） |
| `error.data.code=Interrupted`／`Removed` | 同 `stopped` 那列的固定字串（可能已經跑了） |
| `error.data.code=Stopping` | 「工具 <名> 沒跑：kernel 停機時取消」 |
| 其他 `error` | 「工具 <名> 沒跑：kernel 退件（<data.code，沒有就 code>）」 |

四種停：`Stopping`＝排隊時被停機取消，**確定沒跑**；`Removed`＝被 `rm`，**可能正在跑**；`Interrupted`＝cpu 主人死在這件上，**結果不明**；
`stopped:true`＝被強制停砍，**可能跑一半**。只有 `Stopping` 算「沒發生」；刪檔另看 §10，跟是哪一種無關。
