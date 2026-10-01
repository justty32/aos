# 人手打的操作 CLI：對應與 alias

← [CLI 入口](README.md)｜[規格入口](../README.md)

## H-030．CLI 怎麼變成 method〔第十二批裁定〕

alias 先展開；method 是指令去掉 aos、以點連接。IPC params 沿 schema，檔案 params 是 inst；收件端省目標／--from-node／--file，從 stdin 讀材料，不再投件。

```json
{"jsonrpc":"2.0","id":"m1","method":"agent.say","reply_to":"/srv/aos/top","params":{"argv":["aos","agent","say"],"stdin":"/srv/aos/top/public/m1.json","stdout":{"$opt":"inherit"},"stderr":{"$opt":"inherit"}}}
```

m1.json 內容是 `{"text":"你好"}`；回話用 `{"text":"收到","in_reply_to":"m1"}`。argv 保留 aos；收件 node 開放哪些 method、什麼時候回 -32601，以 [B-501](../base/transport.md)、[B-623](../settled/tick/mq.md) 為準（能投件就能用收件 node 的身分跑，[T-08](../terms.md)）；跨 node inst 的 envs／指示詞／stdin 風險由使用者承擔。tick 提交後投 outbox、刪原件；result 用 work-result，stdout 只給路徑。schedule recheck/quota set 的本地 stdout 為 accepted:true，usage measure 為 res-usage。work submit/llm chat 跨格等業務結果才回，stdout 分別是 work-result/llm-result。

〔第十八批〕例外：`aos node tick` 不對應 `node.tick`，而是送 `node.wake`，以 wake 回應的 `registration_id`、`tick_seq` 為起點，再輪詢 `node.show` 等新的一格做完（[B-607](../settled/deferred/daemon/registration.md)、[H-004](commands.md) 第 17 列）；`aos work trace`、`aos migrate`、`aos node check` 只在本機讀寫，不對應 method；`aos mount clear` 對應 IPC `mount.clear`（原 `once.clear`），`aos mount run`、`aos mount kill` 對應 `node.mount`、`node.kill`（人手沒有憑證，`--parent` 必填，[P-118](../settled/deferred/protocol/daemon/channel.md)）。tick 內的任務走通道時不經 CLI，而是自己帶 `AOS_TICK_TOKEN` 對 `AOS_DAEMON_SOCKET` 送同樣的 method（[B-612](../settled/deferred/daemon/channel.md)）。熱重載沒有 CLI，用 `kill -HUP`。

## H-035．常用 alias〔工程預設〕

| 短形 | 正式命令 |
|---|---|
| `aos daemon --config F` | `aos daemon start --config F` |
| `aos ls`／`aos show`／`aos new` | `aos node ls`／`show`／`new` |
| `aos register`／`aos unregister` | `aos node register`／`unregister` |
| `aos wake`／`aos pause`／`aos resume` | `aos node wake`／`pause`／`resume` |
| `aos tick`／`aos log` | `aos node tick`／`log`（`aos tick` 也是送 `node.wake` 再等 `tick_seq` 前進；想直接跑一格可打 `aos-tick`，風險自負，[B-627](../settled/tick.md)） |
| `aos say`／`aos listen` | `aos agent say`／`listen` |
| `aos run` | `aos inst run` |
| `aos clean N …` | `aos clean run N …` |
