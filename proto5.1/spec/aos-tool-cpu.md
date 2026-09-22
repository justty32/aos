# aos-tool-cpu 程式規範（第 1 版）

← [proto5.1 README](../README.md)｜格式：[tool-cpu](tool-cpu.md)｜佇列：[cpu-queue](cpu-queue.md)

`aos-tool-cpu [dir]`：省略 dir＝`.`。先驗 `tool_cpu` info，透過 `aos_cpu.tick` 收屍、
再執行最多一份請求。execute 只驗解好的 payload，再呼叫
`aos_exec.run_inst(inst, stdin, timeout_ms)`，不解指示詞也不讀 agent 家。

收屍年齡必須大於 `timeout_ms / 1000 + 30` 秒。payload 的 timeout_ms 壞掉且程序又崩在
認領後時，採 60000 ms 預設期限加 30 秒，讓它仍能收屍；正常壞 payload 立即回 ok:false。
收屍使用 [tool-cpu](tool-cpu.md) 的固定「結果不明」文字，不重試；不把失聯猜成已知逾時。
真工具逾時先依 aos_exec 規則 TERM、寬限 2 秒再 KILL 整個 process group；收屍本身不殺進程。

| 退出碼 | 意思 |
|---|---|
| 0 | 已處理請求／收屍，包含非零工具退出與 ok:false |
| 101 | 沒有可做的工作 |
| 1 | info、共同請求欄位、JSON 或 I/O 錯誤，一行 `aos-tool-cpu: <代號>: <白話>` |
| 2 | 未知參數或 dir 不是資料夾 |

CPU 不把捕獲的 stdout 印到命令列；工具的 stderr 照 inst，exec 前置失敗仍沿用 aos_exec
的 stderr 診斷。`load(dir, env=None)` 回 dir／metainfo；`execute(request)` 回結果 dict；
`tick(dir, env=None)` 回 0／101，讀驗錯丟 AgentError；`main(argv=None)` 是 CLI 入口。

原子寫結果、同名保護、同時多進程、遲到回覆與故障窗口均由共用佇列負責。
