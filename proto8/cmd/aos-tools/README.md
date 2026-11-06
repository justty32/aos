# aos-tools — 一個 agent 資料夾一份工具註冊檔

← [cmd](../README.md)

`bin/aos-tools`（Python）管 tools.json：登記這隻 agent 能叫哪些工具、`call` 叫它們。`add` 成功印一行 `added NAME -> PATH`、`rm` 每拿掉一個印一行 `removed NAME`；`aos-tools --help` 印頂層、`aos-tools 子命令 --help` 印那個子命令的英文說明。說明在 [cmd/docs/01](../docs/01-逐支說明.md#逐支說明)；覆蓋層見 [aos-agent docs/03](../aos-agent/docs/03-tools覆蓋層.md)。
