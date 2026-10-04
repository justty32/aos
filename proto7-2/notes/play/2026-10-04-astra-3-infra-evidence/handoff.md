# astra-3 QA 分工與邊界

四條 subagent 均不得再分線；只可寫下列自己的證據子目錄，主報告由 root 彙整。使用者本輪指示優先：不改既有程式／測試／文件，不 commit、不 push、不打 LLM，不刪 scratchpad 既有內容。

| 線 | 可寫領地 | 驗收 |
|---|---|---|
| core | core/ | 全套三次耗時與結果；精簡 A2/A3、G1/G2、until_round；分類與重現；清理 |
| modules | modules/ | control、once_retry、subd、audit、diag、tools 契約抽查；分類與重現；清理 |
| step | step/ | 中斷、unknown、resend、壞框架、耐性、pause、wake、restart_on_end、close；分類與重現；清理 |
| comparison | comparison/ | CSV 手寫與 step 中斷對照數字；至少400真回合長跑與檔案數取樣；清理 |

共同驗收：腳本可重現、精簡 JSON 或 log 證據及分報告存在；自建 /tmp 測試根清除；追蹤 PID 清理並核對 ps。其他路徑唯讀。主工作樹既有 proto7/user-advice.md 不動。
