# 人手打的操作 CLI：對應與 alias

← [CLI 入口](README.md)｜[規格入口](../README.md)

## H-030．CLI 怎麼變成 method〔第十二批裁定〕

alias 先展開；method 是指令去掉 aos、以點連接。IPC params 沿 schema，檔案 params 是 inst；收件端省目標／--from-node／--file，從 stdin 讀材料，不再投件。

```json
{"jsonrpc":"2.0","id":"m1","method":"agent.say","reply_to":"/srv/aos/top","params":{"argv":["aos","agent","say"],"stdin":"/srv/aos/top/public/m1.json","stdout":{"$opt":"inherit"},"stderr":{"$opt":"inherit"}}}
```

m1.json 內容是 `{"text":"你好"}`；回話用 `{"text":"收到","in_reply_to":"m1"}`。argv 保留 aos，method 對應收件 node 開放的命令，否則 -32601；跨 node inst 的 envs／指示詞／stdin 風險由使用者承擔。tick 提交後投 outbox、刪原件；result 用 work-result，stdout 只給路徑。schedule recheck/quota set 的本地 stdout 為 accepted:true，usage measure 為 res-usage。work submit/llm chat 跨格等業務結果才回，stdout 分別是 work-result/llm-result。

## H-035．常用 alias〔工程預設〕

| 短形 | 正式命令 |
|---|---|
| `aos daemon --config F` | `aos daemon start --config F` |
| `aos ls`／`aos show`／`aos new` | `aos node ls`／`show`／`new` |
| `aos register`／`aos unregister` | `aos node register`／`unregister` |
| `aos wake`／`aos pause`／`aos resume` | `aos node wake`／`pause`／`resume` |
| `aos tick`／`aos log` | `aos node tick`／`log` |
| `aos say`／`aos listen` | `aos agent say`／`listen` |
| `aos run` | `aos inst run` |
| `aos clean N …` | `aos clean run N …` |
