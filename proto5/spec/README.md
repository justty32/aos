← [proto5 README](../README.md)

# proto5 規範總導航

九份規範，一份一個資料夾；每個資料夾的 `README.md` 是入口（一句定位、已拍板的前提、各節一覽），內容依原本的 § 節拆成小檔，節號照舊，文中「§3」「§1.1」這類引用去該資料夾的 README 查在哪個檔。

| 主題 | 一句話 |
|---|---|
| [inst-posix](inst-posix/README.md) | inst.json 規範：一份 inst 就是「叫作業系統跑一個程式」那句話的 JSON 版 |
| [directives](directives/README.md) | 指示詞：讓 JSON 的值從環境變數、字串模板或另一份 JSON 取來的統一寫法 |
| [aos-exec](aos-exec/README.md) | `aos-exec`：把一個目標跑一次，分清楚是自己的失敗還是子程式的碼 |
| [cpu](cpu/README.md) | cpu 範式與 exec cpu：一個資料夾加一個主人行程，逐件照 aos-exec 跑 `requests/` 裡的單 |
| [daemon](daemon/README.md) | daemon：所有 cpu 的父行程，只管啟動、重拉、停止 |
| [kernel](kernel/README.md) | kernel：排程也是一格一格的 aos-exec，替登記的工作挑空 cpu、收結果、決定要不要再跑 |
| [agent](agent/README.md) | agent 資料夾：設定、對話記憶與跨次進度 |
| [aos-agent](aos-agent/README.md) | `aos-agent`：走一格、登記、取消登記，以及 init／say／status／listen 等日常指令 |
| [aos-llm](aos-llm/README.md) | `aos-llm call`：讀 agent 的模型輸入與 cpu 的模型表，問一次模型 |
