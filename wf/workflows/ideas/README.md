# ideas — 構想記錄入口

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)

記錄尚未進入 spec／plan／feature-dev 的產品構想。這裡保存的是**方向、心智模型與待釐清
問題**，不是已實作行為；構想準備落地時，再轉交對應工作流。

## 目前構想

| 檔案 | 內容 |
|------|------|
| [turn-based-folder](turn-based-folder.md) | 指定資料夾的回合制演化模型、`core/daemon`、`.aos/next/` 與 agent loop |
| [llm-cpu](llm-cpu.md) | LLM CPU、單一 exec 入口或分離 daemon 的取捨、跨資料夾排程與 I/O 交換區 |
| [inst-execution](inst-execution.md) | `inst` 的 env 繼承開關與非阻塞／背景執行策略 |

新增內容優先歸入既有主題；出現獨立方向時才新增內容檔。構想被正式 spec／plan 取代後，
在這裡改留指標，不讓 idea 文件與已拍板規格形成兩份真相。
