# 2026-10-14 函數的統一入口改成 JSON

← [討論紀錄](README.md)｜前一份：[kernel／agent](2026-10-13-kernel-agent.md)

> 10-14 中午（公司 WSL），使用者吃飯時的想法，打字。

<!-- wf-nav -->
| 分檔 | 涵蓋段落 |
|---|---|
| [01-原文-0至1h](2026-10-14-json-entry/01-原文-0至1h.md) | 0. 背景；1～1h 使用者原文（JSON 入口、stdio＝JSON 串流、inst 不動） |
| [02-原文-1i至1q](2026-10-14-json-entry/02-原文-1i至1q.md) | 1i～1q 使用者原文（state／ctl 外顯、函數看法、aos 版 IPC、IPC 研究頁 8 題回答、CtlFile.poll 殘留） |
| [03-決定未決](2026-10-14-json-entry/03-決定未決.md) | 2. 決定（10-14）；3. 未決 |
| [04-argv與七題](2026-10-14-json-entry/04-argv與七題.md) | 4. argv 空出來（下午，D-1～D-6、推翻 10-12 三條）；5. 重做規劃頁七題拍板；6. 新增未決 |
| [05-aos-llm-agent題](2026-10-14-json-entry/05-aos-llm-agent題.md) | 7. N-13 提醒拿掉（推翻縫二）、D-1 放寬；8. 其餘 13 題拍板；9. Q1（已由 06～08 解） |
| [06-fsm](2026-10-14-json-entry/06-fsm.md) | 10. 使用者原話（aos-agent＝查表分派、vtable／interface、可嵌套、一格可指資料夾）；11. aos-fsm 架構：agent＝通用 fsm＋方法表，每格＝aos-inst TARGET，think 同步／非同步可互換 |
| [07-fsm樹與一拍](2026-10-14-json-entry/07-fsm樹與一拍.md) | 12. 資料夾樹、一拍流程、巢狀 fsm 接法（AI 建議）、巢狀三題待拍板 |
| [08-fsm拍板與改寫](2026-10-14-json-entry/08-fsm拍板與改寫.md) | 13. 十題拍板（2、3、4、7 非推薦）；14. 已定事項改寫清單；15. 風險；16. 新增未決 |
| [09-daemon套fsm](2026-10-14-json-entry/09-daemon套fsm.md) | 17～21 daemon 借 fsm 紀律：五題拍板（六態、接回孤兒、child_exit 策略格）、風險、save 與 table 窗合一未決 |
| [10-lisp組合子](2026-10-14-json-entry/10-lisp組合子.md) | 22～25 Lisp／組合子視角：fexpr、tagbody 類比、表上靜態 next、JSON 樹為主、一拍一步、接受重跑、組合子按需表 |
| [11-下班前待辦](2026-10-14-json-entry/11-下班前待辦.md) | 26～30 下班前：憑感覺選題的背景、三份網頁、建議重看 7 題、重寫頁發現的未對齊 a～f、下一步（已結，見 12） |
| [12-七題回覆](2026-10-14-json-entry/12-七題回覆.md) | 31～34 夜：使用者回 7 題（基礎／標準實作兩級 N-18、loop／daemon 窗必填 N-19、巢狀重跑不保證冪等 N-20、think 同步／非同步規範中立、繼承不進規範、agent.json 或資料夾皆可）、a～f 暫定預設、仍待拍板 |
| [13-動工前拍板](2026-10-14-json-entry/13-動工前拍板.md) | 35～38 夜末：fsm state 窗必填（N-19 擴到 fsm）、拍板動工重做 inst／loop／daemon、「daemon.json 放 inst」結論（候選 g，等拍板）、給下一個 agent 的施工清單 |
| [14-h拍板](2026-10-14-json-entry/14-h拍板.md) | 40～41 深夜：動工自定點 h1～h16「全照建議」拍板（h15 add 先驗 inst、h16 tasks 讀 stdout 改）、落點、N-12 措辭的張力（已結：跑完＝stdout 吐出結果＋行程結束，有 exit 檔則出現也算） |
