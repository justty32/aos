← [proto5 README](../README.md)

# proto5 規範總導航

十份規範，一份一個資料夾（2026-09-24 proto5-2 池式納入：kernel、daemon、cpu 三份改成池式；同日 one-boot：daemon 替 kernel 開 tick、kernel 帳本換 sqlite、`aos up`／`aos down`；沿革見各資料夾的 history.md）；每個資料夾的 `README.md` 是入口（一句定位、已拍板的前提、各節一覽），內容依原本的 § 節拆成小檔，節號照舊，文中「§3」「§1.1」這類引用去該資料夾的 README 查在哪個檔。

| 主題 | 一句話 |
|---|---|
| [inst-posix](inst-posix/README.md) | inst.json 規範：一份 inst 就是「叫作業系統跑一個程式」那句話的 JSON 版 |
| [directives](directives/README.md) | 指示詞：讓 JSON 的值從環境變數、字串模板或另一份 JSON 取來的統一寫法 |
| [aos-exec](aos-exec/README.md) | `aos-exec`：把一個目標跑一次，分清楚是自己的失敗還是子程式的碼 |
| [cpu](cpu/README.md) | cpu 範式與 exec cpu：一個資料夾加一個主人行程，逐件照 aos-exec 跑 `requests/` 裡的單，回完音可丟通知 |
| [daemon](daemon/README.md) | daemon：所有 cpu 的父行程，按池照宣告啟動、重拉、停止；也替 kernel 定時開 tick（`aos up`／`aos down` 一條指令開機停機） |
| [kernel](kernel/README.md) | kernel：排程一格一格跑（daemon 替它開 tick），替登記的工作挑空 cpu、收結果、決定要不要再跑；cpu 按池管（`cpu add／rm／ls`）；帳本是 sqlite |
| [agent](agent/README.md) | agent 資料夾：設定、對話記憶與跨次進度 |
| [aos-agent](aos-agent/README.md) | `aos-agent`：走一格、登記、取消登記，以及 init／say／status／listen 等日常指令 |
| [aos-llm](aos-llm/README.md) | `aos-llm call`：讀 agent 的模型輸入與 cpu 的模型表，問一次模型 |
| [team](team/README.md) | 一支 agent 團隊：團隊資料夾、名冊、信與申請、任務單狀態機、問人、成員模板、門房、`aos-team`（09-24 工具大開發時代第一波） |
