# proto7-2 notes — 設計筆記、藍圖、決策與紀錄的索引

← [proto7-2](../README.md)｜結構表 [INDEX](../INDEX.md)

本資料夾放「為什麼這樣做」與「做到哪」：規則本身在 [spec](../spec.md) 與各包 README／ADVANCED，這裡不重抄。狀態欄：**現行**＝仍是依據；**已落地**＝照它做完了，留著看由來；**歷史**＝某天的快照，內容可能已被後來的事蓋過。2026-10-10 整理。

## 先看哪份

<!-- wf-nav -->
- 想知道最近決定了什麼 → [decisions-2026-10-10](decisions-2026-10-10.md)（最新）、[decisions-2026-10-09](decisions-2026-10-09.md)（四份分檔的入口）。
- 想知道某條規則從哪來 → [problems](problems.md)（實作時碰到的問題與各條由來）、[component-contracts](component-contracts.md)（契約卡與錯誤歸屬）。
- 要開新包或改包 → 先看 [intents/](intents/README.md) 的意圖卡，錯誤路徑照 [blueprint-errors](blueprint-errors.md)。
- 頭腦風暴要翻 wf/ 的構想與舊規格 → [thinking-catalog](thinking-catalog.md)（32 份思想文件依主題分組）。

## 現行的設計依據

<!-- wf-nav -->
| 文件 | 在講什麼 | 狀態 |
|---|---|---|
| [problems](problems.md) | 照 spec 實作時的問題、A2／A3 處理、核心精簡刪掉的誤用保護與搬出核心的設計 | 現行 |
| [component-contracts](component-contracts.md) | 每個組件一張契約卡（職責／前置條件／保證／明確不管），錯誤四類 M／X／B／G | 現行 |
| [blueprint-errors](blueprint-errors.md)＋[items](blueprint-errors-items.json)＋[分線](blueprint-simplify-teams.json) | 全 aos 共用的退出碼 0～4、一行錯誤訊息、「不確定」；`tests/error_path.json` 照它驗 | 現行 |
| [core-slimming](core-slimming.md)＋[盤點](core-slimming-inventory.json)＋[astra 分類](core-slimming-astra-triage.json) | 核心精簡方案：核心最小集、錯誤四分支、擴充點與模組包 | 已落地（aos7-pack 還沒做） |
| [changes-from-7-1](changes-from-7-1.md) | proto7-1 → proto7-2 每個改動與理由，W1～W12 | 已落地 |
| [layer-interfaces](layer-interfaces.md)（[分檔](layer-interfaces/01-daemon-ticktock.md)） | 四層（daemon、tick-tock、kernel、agent）交接點調查 | 歷史（10-04 調查，當時還沒有 kernel） |

## 藍圖（每份一輪或一個包的設計）

<!-- wf-nav -->
| 藍圖 | 做什麼 | 狀態 |
|---|---|---|
| [blueprint-loop4](blueprint-loop4.md)、[loop5](blueprint-loop5.md)、[loop6](blueprint-loop6.md) | 10-04 第四～六輪修補：astra-3～5 發現、subd 回收前代、budget、adapt 第一版 | 已落地 |
| [blueprint-loop7](blueprint-loop7.md)＋[items](blueprint-loop7-items.json) | kill／回收時序、budget↔step unknown 交接、假綠測試 | 已落地（10-09） |
| [blueprint-ev1](blueprint-ev1.md)＋[items](blueprint-ev1-items.json) | 事件保存第一版 → `modules/events/` | 已落地 |
| [blueprint-llm1](blueprint-llm1.md)＋[items](blueprint-llm1-items.json) | LLM 作者第一刀（假候選）→ `packs/author/` | 已落地 |
| [blueprint-llm2](blueprint-llm2.md)＋[items](blueprint-llm2-items.json) | 單次呼叫閘道＋token 部分結算 → `packs/llmcall/`、budget | 已落地 |
| [blueprint-wfnode](blueprint-wfnode.md)＋[items](blueprint-wfnode-items.json) | 讓 aos 上的 AI 用 wf 記事 → `modules/wfnode/` 等 | 已落地 |
| [blueprint-firstrun](blueprint-firstrun.md)＋[分線](blueprint-firstrun-teams.json) | 一個指令起一個會做事的 node → `aos7-up`、QUICKSTART | 已落地 |
| [blueprint-simplify-2](blueprint-simplify-2.md)＋[分線](blueprint-simplify-2-teams.json) | 回頭審第二輪：usage 併進 metrics、llmdiag 併進 diag | 已落地 |
| [blueprint-kernel1](blueprint-kernel1.md)＋[分線](blueprint-kernel1-teams.json) | kernel 決策骨架＋監督 brain → `packs/kernel/` | 已落地 |
| [blueprint-scaffold1](blueprint-scaffold1.md)＋[分線](blueprint-scaffold1-teams.json) | 選單包＋學徒一層一層交件的 A／B → `packs/menu/` | 已落地（MN1～MN4；A／B 結論：選單輸給一次交整包，機制收下、不往 brain 推，見 [menu-ab](play/2026-10-10-menu-ab/README.md)；下一步由使用者定） |

## 計畫、報告、決策紀錄

<!-- wf-nav -->
| 文件 | 在講什麼 | 狀態 |
|---|---|---|
| [decisions-2026-10-10](decisions-2026-10-10.md) | 10-10 頂層代定與各隊結果 | 現行（當天持續追加） |
| [decisions-2026-10-09](decisions-2026-10-09.md) | 10-09 使用者出門時的頂層代定清單，拆成四份 | 歷史 |
| [report-2026-10-09](report-2026-10-09.md) | 10-09 白話報告（你出門這段時間） | 歷史 |
| [plan-2026-10-09-next](plan-2026-10-09-next.md)＋[分線](plan-2026-10-09-next-teams.json) | 使用者 14:40 三目標的續推計畫；三目標與門檻仍被 wfnode 與藍圖引用 | 歷史（仍被引用） |
| [catch-up](catch-up.md)＋[名詞表](catch-up-glossary.md) | 10-04 早 → 10-05 下午的追進度導讀 | 歷史（只到 10-05） |
| [next-steps](next-steps.md)＋[落地順序](next-steps-landing.md)＋[修補候選](next-steps-fixes.json) | 10-05 整理的下一步選項；事件保存、LLM 作者、kernel 任務包、loop7 修補後來都做了 | 歷史（10-05） |
| [thinking-catalog](thinking-catalog.md) | wf/ 底下 32 份超標的構想／規格／路線文件的主題目錄 | 現行（索引） |

10-09 當天的上午／下午／第三段／r4 派隊計畫與 worktree 清單已封存到 [archive/](archive/README.md)。

## 子資料夾

<!-- wf-nav -->
| 資料夾 | 放什麼 |
|---|---|
| [intents/](intents/README.md) | 意圖卡：新模組或功能開隊前先寫的一頁卡（解決什麼、必要副作用、不做什麼） |
| [play/](play/README.md) | 試玩與回歸紀錄，一輪一列；證據放同名資料夾 |
| [reviews/2026-10-05/](reviews/2026-10-05/README.md) | 10-05 的 15 份 astra 審查／調查報告與交叉問題 |
| [layer-interfaces/](layer-interfaces/01-daemon-ticktock.md) | 四層交接點調查的五份分檔（入口是 [layer-interfaces.md](layer-interfaces.md)） |
| [decisions-2026-10-09/](decisions-2026-10-09/01-morning.md) | 10-09 代定清單的四份分檔（入口是 [decisions-2026-10-09.md](decisions-2026-10-09.md)） |
| [status/](status/README.md) | 10-09 的三張狀況頁 HTML 快照 |
| [archive/](archive/README.md) | 已結束的計畫與清單 |
