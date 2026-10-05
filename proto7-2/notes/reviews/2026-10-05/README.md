# 2026-10-05 astra 審查／調查報告

[proto7-2](../../../README.md)｜[evidence-summary](evidence-summary.md)

10-05 早上開的 15 條 codex astra（xhigh）線，審查與調查 proto7-2，全部唯讀或在 scratchpad 複本內執行，程式未動。code-review 與 model-check 曾被 OpenAI 資安過濾擋下；**play7、deep-play、model-check、code-quality、spec-readability、wf-structure、packs-use、cpp-core 是「收尾版」**（中途叫停後依已做到的寫，不完整）。報告裡原本的絕對路徑連結已改成相對路徑。等使用者挑要修哪些。

| 報告 | 主題 | 一句結論 |
|---|---|---|
| [code-quality](code-quality.md) | 程式品質與正確性（收尾版） | 啟動、回收、中斷恢復有數項缺陷，優先修「kill 過早回成功」與「舊任務未確認收乾淨就起新時間線」 |
| [cpp-core](cpp-core.md) | C++ 核心移植審查（收尾版） | 移植應先重建錯誤判定、程序身分與可恢復的執行交接，再接 agent／LLM；現有 C++ 有漏工作、誤報成功、併發覆寫缺口 |
| [deep-play](deep-play.md) | 長跑與壓力（收尾版） | 確認兩個同族 daemon 回收缺陷（C8-01／02）與任務包暫存檔缺口；長跑與一小時 chaos 未達門檻 |
| [docs-align](docs-align.md) | 文件與程式對齊（spec-readability F01～F34、packs-use 4.1 的落實） | 照程式改 32 條文件說法（F06 只改 README 半條）、三包加「第一次跑」並實跑；F03、F19、F06 spec 半條、4.5 等牽涉 D4～D6 留給使用者 |
| [event-store](event-store.md) | 事件保存候選方案 | 核心零改動可存快照、daemon 追加事件與任務主動發布的事件；要所有底層事件不漏須補來源端交接契約 |
| [fast-tests](fast-tests.md) | 測試加速 | 364 項中位數 190.19 秒降到 65.19 秒（省 65.7%），19 輪全過；原樣複本本身只有 359/364 |
| [k-crosscheck](k-crosscheck.md) | proto7-1 K 系列與第三波需求對照 | 生命週期與 once 去重未完全封閉，另有巨大 interval、巢狀 subd 啟動、子根稽核三項遷移退步 |
| [kernel-pack](kernel-pack.md) | kernel 任務包設計 | 不改核心即可成立；第一版建議可接續的決策骨架加綁定原始 run 的 kill，step／budget／adapt 保持獨立 |
| [llm-author](llm-author.md) | LLM 寫任務與 adapt-llm | 現有核心夠承載第一個原型；需補包層的候選驗證、發布與恢復、單次呼叫回條、token 部分結算 |
| [model-check](model-check.md) | budget／subd 模型檢查（收尾版） | 讀碼找到 subd 合法 stop 後重開可能誤殺保留任務的候選反例；檢查器未完成，不宣稱任何不變條件已驗 |
| [packs-use](packs-use.md) | 只看 README 的新使用者試玩（收尾版） | 能組出實用小程式，但缺設定範本、非同步完成條件不明、各包重試語意不一，評 5.4／10 |
| [play7](play7.md) | 第七輪對抗式回歸（收尾版） | 確認 11 項缺陷或契約缺口；97191272 修了取整但引入兩項回歸；三次全套測試未完成 |
| [prior-art](prior-art.md) | 與成熟系統比較 | 已有小型監督器與調和迴圈骨架；該借的是身分、恢復、停止、證據保存的明確契約，重試與子監督樹留模組層 |
| [spec-readability](spec-readability.md) | 文件可讀性與一致性（收尾版） | 主因是把有條件保證寫成絕對保證、跨包同名術語語義不同；先修診斷手冊回合恢復判準、pause 說明、budget 接 step 的 unknown 處理 |
| [test-review](test-review.md) | 364 項測試審查 | 正常與故障恢復覆蓋扎實，但綠燈仍會漏「沒真的崩潰、故障打錯階段」；先補判定與同步再平行化 |
| [wf-structure](wf-structure.md) | wf 文件結構整理（收尾版） | 排除封存後 150 份 Markdown 超過 8 KiB；先清失效待辦與舊介面說明，再抽資料與拆檔，不以全壓到 8 KiB 為目標 |
| [wsl-3-failures](wsl-3-failures.md) | WSL 上 3 項穩定失敗 | 測試對 dash 不 exec 最後命令、aos7-run 起得比恢復回合快的假設錯；產品無誤，已改測試 |

## 多線交叉撞到的問題

- subd 合法 stop 後重開誤收保留任務：play7 A8-09、model-check MC-01。
- budget unknown 傳到 step 被當一般失敗：play7 A8-10、spec-readability F03、packs-use 4.3／4.4。
- 巨大整數 interval 讓 node 不開回合：play7 A8-11、k-crosscheck N-21。
- 回合已關確認讀不到倒數少扣：code-quality R8-05、k-crosscheck K-02。
- 取消登記／替換後中斷回收義務遺失：code-quality R8-02／R8-03、deep-play C8-01／C8-02。
- adapt 小修 97191272 引入的回歸：play7 A8-01、A8-02。
