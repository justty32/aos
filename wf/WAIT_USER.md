# WAIT_USER — 等待使用者的事

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

需要**使用者親自做 / 驗證 / 拍板**才能繼續的事——例如：實機/實環境測試、外部服務登入、環境變數設定、權限操作、需要帳號的下載、**催/開/fork 另一個 agent 處理急件**（見 [inbox](workflows/inbox/README.md)：寄了信但很急、對方可能沒開）。Claude 能做結構性驗證＋打包到極限；跨不過去的那一關記這裡等使用者。

**設計裁決也算**——照 [AGENTS 鐵律 5](../AGENTS.md)「大方向是使用者的」，需要你一句話才動得了工的，
對我來說跟「沒有帳號密碼」是同一種卡住。**本檔只留一行 ＋ 連結**，脈絡在各自的原始文件裡，不在這裡重講。

**只列還沒做的**——做完即移除（不留已完成清單，歷史看 git log）。

> **膨脹就拆**：待使用者項堆多了，就開 **`wait-user/`** 資料夾按類別拆檔，本檔退回只留一張 `| 類別 | open | 清單 |` 導航表（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

## 待使用者項

### A. 等你一句話（其餘我都做得下去，卡的只有這幾條）

> 編號是固定的（別處用「WAIT_USER 第 N 條」引用），拍掉的號碼不回收，所以會跳號（1、2、7 已結；9 移到 C）。**編號固定不回收**——已按類別搬進 [`wait-user/`](wait-user/README.md)，本檔只留導航表。

| 類別 | open | 清單 |
|------|------|------|
| proto2（辯論場／hackathon／proto2 舊題） | 9 | [wait-user/proto2.md](wait-user/proto2.md)（3、4、5、6、8、10、11、12、13） |
| proto5 重架構＋kernel（daemon 崩潰窗口／endpoint 換手／kernel 排隊／once／proto5-2 六題／C-7、C-8） | 7 | [wait-user/proto5-kernel.md](wait-user/proto5-kernel.md)（14～20） |
| 已裁決／代裁紀錄（09-24，只為翻案回頭查，非待答） | 19 | [wait-user/decided-2026-09-24.md](wait-user/decided-2026-09-24.md)（21～39） |
| 公司／市場（財務／製造／圖書館／品管／HR／總裁／組織設計） | 36 | [wait-user/company-market.md](wait-user/company-market.md)（40～75；**74、75 最要緊**：成功率要不要進分數、品質分要不要叫評審） |

### B. 要你親自做的（環境／帳號，我跨不過去）


（目前沒有。）

### C. 你已明說先不決定的（不催，只記「什麼時候會被迫要答」）

放這裡是為了**別再拿它們去煩你**，不是待辦：

- **proto5-2 規模三題**（kernel 帳本仍整份讀寫、aos-agent 每格偷看整份帳本、一顆 cpu＝一支 Python 程序）——09-24 使用者說「規模這塊先不動」；什麼時候會被迫要答：proto5-2 要實作，或 cpu 上千顆時。→ [proto5 納入報告](../proto5/notes/2026-09-24-fold-in/README.md)「沒做的」一節（proto5-2/notes/2026-09-24-impl/decisions.md 的 Q1～Q3）
  - **多一條同類的**：閒著的 agent 每格還是被叫醒看一眼（J 隊 priority-and-shared-cpu 挖到，見 [報告](../proto5/notes/2026-09-24-priority-and-shared-cpu/README.md) §「要使用者拍的」題 2-3）；K 隊正在提案「等模型的 agent 不空轉」，做完再一起拍。

- **pi 當介面層**（2026-08-30「先擱置」）——接法與代價在 [pi-interface](../core/agent/docs/pi-interface.md)，要投資時從那裡起。

- **B12 判準／loop 分支的形式／版面知識放哪**（2026-08-30 三題都「先不決定」）——
  會撞上的時機：要動 `exec_loop` 時（分支）、要寫第一支 CLI 小程式時（版面 lib）。
  → verdicts B12、core-layering
- **workshop 那四個設計選擇**（World 抽象、`kernel.json` 分層合成、子行程拓樸、親緣綁
  路徑還是 UUID）——你明講「窩不想看惹」，方向是**用實測取代拍板**，所以不列 A 區。
- **top-down-cli 的 14 條**——已裁「實作時順便解決」。
- （原 A.9）**proto2：拍板題 T-01～T-77 全照建議做了（使用者 09-06 說「都 OK」）**；要翻案就回編號。→ [notes/tools/README.md](../proto2/notes/tools/README.md)

> 設計上還沒答完、但不卡你的細節不放這裡——記在 [`roadmap`](workflows/roadmap.md) 與各 idea 文件的開放問題。
