# astra-6 QA 分工

授權：使用者本輪 QA，最多四條子線；全部禁止修改既有程式、測試與文件，禁止 commit/push、LLM、清理 scratchpad。只寫本 evidence 與指定主報告。

| 線 | 唯一可寫領地 | 驗收 |
|---|---|---|
| regression | regression/ 與自己 /tmp | 全套三次、A4/F47/§4.4、step 450、核心行數與歷史 diff |
| subd | subd/ 與自己 /tmp | A6-01、G3 10/10、TERM/舊 life/倒鐘 |
| budget | budget/ 與自己 /tmp | A6-02、§9/10、clock_hw/掃回條/退役/max_resends、獨立核帳 |
| adapt | adapt/ 與自己 /tmp | 使用者列的邊界矩陣、300+ 回合、門檻公式判讀 |

每線保存可重跑探針、原始結果、summary.md、清理與 ps 證據；大量快照 tar.gz。只殺自己 PID，清自己 /tmp。父線只整理根證據與主報告，收線須核對各項原始結果。
