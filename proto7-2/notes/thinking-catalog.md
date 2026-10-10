# 思想文件目錄

給頭腦風暴時翻用。這份只是索引，沒有改動任何原文。整理日期 2026-10-10。

## 怎麼篩的

跑 `bash wf/tools/wf-lint.sh wf .claude/commands`，取 `OVERSIZE`（單檔超過 8 KiB）的清單，共 32 份（頂層說的 31 份是前一刻的數字，現在多一份 `common/code-map.md`）。其中 29 份是想法、規格、路線類；3 份（`code-map`、`lessons`、`roadmap`）不太是思想文件但也超標，我全列並在分類上標明。沒有報告、證據、log 類的超標檔，所以沒排除任何一份。
欄位：大小是位元組；日期是 git 最後修改日；路徑都相對於本檔，點得開。

## 先看這三件事

- **ideas 13 章**是「為什麼」，**spec 16 份**是「要做成什麼樣」，兩邊章節大致一一對應，所以每組都把兩邊放在一起。
- **spec 這一疊（09-05 舊版）入口自己標了「歷史」**，現行規格是 `proto6/spec`，再往後是 `proto7`。它們講的概念（一格、接力棒、daemon 對帳）仍有參考價值，但條款編號與細節不要當現行依據。
- ideas 13 章入口仍把它們當現行構想，但寫於 09-05，之後 proto6、proto7 有新想法（時空分層等），翻的時候可對照 `proto7/notes`。

## 已封存

本次沒有封存任何一份。原因見文末「為什麼沒封存」。


## 1. 總綱與判準（4 份）

先弄清楚 aos 為什麼存在、拿什麼尺量好壞、還有哪些洞沒補。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/01-what-and-goals.md](../../wf/workflows/ideas/01-what-and-goals.md) | 12147 | 2026-09-05 | 一個 agent loop 當一顆 CPU，aos 是蓋在上面的作業系統；怎麼量好壞（可預測性第一、邊緣狀況只准從 LLM 來）。 | 總綱、判準、kernel | 現行（構想集，只留脈絡但仍是入口） |
| [ideas/13-holes-and-play.md](../../wf/workflows/ideas/13-holes-and-play.md) | 12308 | 2026-09-05 | 最大的洞、該升格的傾向、已被取代的舊想法、先玩清單。 | 總綱、待決 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/01-terms.md](../../wf/workflows/spec/01-terms.md) | 8336 | 2026-09-05 | 整套 spec 的名詞表：地、頂層、`.aos/`、格、接力棒等一句白話。 | 名詞、總綱 | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [roadmap.md](../../wf/workflows/roadmap.md) | 8715 | 2026-10-03 | 拷問停打後的實作階段表（M0～M5）與決策佇列；10-03 起改開 proto7。 | 路線、tick/daemon | 現行（階段表） |

## 2. 資料夾模型（地、版面、記憶、權限邊界）（4 份）

一個資料夾就是一支程式，也是它跑起來的家；誰能看哪裡、哪些檔歸誰寫。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/02-folders-as-lists.md](../../wf/workflows/ideas/02-folders-as-lists.md) | 11841 | 2026-09-05 | 資料夾就是 list，`.aos` 是第一個元素；子資料夾父點名才開；人寫的放頂層、機器的放 `.aos/`。 | 資料夾模型、時空分層 | 現行（構想集，只留脈絡但仍是入口） |
| [ideas/03-land-and-life.md](../../wf/workflows/ideas/03-land-and-life.md) | 11709 | 2026-09-05 | 一塊地看得到哪裡、身分是路徑、怎麼生怎麼死、存檔回滾交給 git。 | 資料夾模型、記憶、權限 | 現行（構想集，只留脈絡但仍是入口） |
| [ideas/04-inside-aos.md](../../wf/workflows/ideas/04-inside-aos.md) | 10771 | 2026-09-05 | `.aos` 裡是一段命令腳本，最底下是原子指令；腳本層與資料夾層只有單向橋。 | 指令、時空分層 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/02-layout.md](../../wf/workflows/spec/02-layout.md) | 11025 | 2026-09-05 | `.aos/` 底下有哪些路徑、誰能寫、進不進 git、算不算記憶。 | 資料夾模型、記憶、權限 | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 3. 寫、編譯、指令、接力棒（4 份）

人或 LLM 寫原稿，確定性地編譯成指令，進度記在檔案裡；這組講檔案格式。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/05-write-compile-run.md](../../wf/workflows/ideas/05-write-compile-run.md) | 12272 | 2026-09-05 | 寫、編譯、執行三段；亂只准在寫；進度記在接力棒檔；什麼叫跑完。 | 編譯、接力棒、tick | 現行（構想集，只留脈絡但仍是入口） |
| [spec/03-source-and-compile.md](../../wf/workflows/spec/03-source-and-compile.md) | 12250 | 2026-09-05 | 原稿長相、拆平、開子地與「選」、編譯器吐什麼與拒絕什麼。 | 編譯 | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/04-inst-format.md](../../wf/workflows/spec/04-inst-format.md) | 11230 | 2026-09-05 | 一筆指令的 json 欄位、結果檔、環境變數、兩個頻道。 | 指令 | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/05-series-format.md](../../wf/workflows/spec/05-series-format.md) | 12266 | 2026-09-05 | 接力棒 `series.json` 的欄位、四種狀態、游標怎麼推、什麼叫閒著。 | 接力棒、tick | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 4. 時間：一格、時鐘、tick 與 daemon（6 份）

時間以格數算，一次 exec 走一格；daemon 是時鐘總管，登記、看管、對帳。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/06-time-and-clocks.md](../../wf/workflows/ideas/06-time-and-clocks.md) | 11159 | 2026-09-05 | 一次 exec 是一格、一個 run 是一個時鐘；同步子地借父鐘、脫節子地自己走；時間要有界。 | tick/daemon、時空分層 | 現行（構想集，只留脈絡但仍是入口） |
| [ideas/07-daemon.md](../../wf/workflows/ideas/07-daemon.md) | 10867 | 2026-09-05 | daemon 是所有時鐘的總管、REPL 的桌子、慢 LLM 呼叫的管家。 | tick/daemon、LLM | 現行（構想集，只留脈絡但仍是入口） |
| [spec/06-exec-and-run.md](../../wf/workflows/spec/06-exec-and-run.md) | 12288 | 2026-09-05 | 一格內的精確順序、一格長度要有界、子地借鐘。 | tick/daemon、時空分層 | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/06b-run-rules.md](../../wf/workflows/spec/06b-run-rules.md) | 8670 | 2026-09-05 | run 的三種走法、怎麼停、停下留原因、崩了怎麼接。 | tick/daemon | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/08-daemon.md](../../wf/workflows/spec/08-daemon.md) | 12253 | 2026-09-05 | daemon 與登記表：誰起、走時鐘、並行上限、控制收件匣。 | tick/daemon | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/08b-daemon-reconcile.md](../../wf/workflows/spec/08b-daemon-reconcile.md) | 12276 | 2026-09-05 | daemon 起來先對帳、看管巡邏、清理、一次全停、搬家。 | tick/daemon | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 5. 呼叫、失敗與信件（2 份）

父怎麼叫子、結果怎麼回、壞了誰處置、東西怎麼放進別人的收件匣。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/09-call-and-failure.md](../../wf/workflows/ideas/09-call-and-failure.md) | 12218 | 2026-09-05 | 一筆指令是一次 POSIX 呼叫；交接、開子地（等＝呼叫、不等＝傳訊）、失敗語意（當時是空的）。 | 呼叫與失敗、信件 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/07-call-and-delivery.md](../../wf/workflows/spec/07-call-and-delivery.md) | 12288 | 2026-09-05 | 開子地的同步／脫節、三態與狀態檔、失敗歸父、收件匣投遞協定。 | 呼叫與失敗、信件 | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 6. LLM 世界與 agent（4 份）

LLM 是另一塊慢的地，用投請求的方式叫；agent 只是跑著這個循環的普通資料夾。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/08-agent.md](../../wf/workflows/ideas/08-agent.md) | 10538 | 2026-09-05 | agent 就是一塊普通的地，每格「問 LLM、照清單做、再問」；停不是死；使用者也是 agent。 | agent、tick/daemon | 現行（構想集，只留脈絡但仍是入口） |
| [spec/09-llm-world.md](../../wf/workflows/spec/09-llm-world.md) | 12117 | 2026-09-05 | LLM 是另一塊地，投請求、回話落指定落點；單元表與帳簿。 | LLM、agent | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/09b-llm-queue.md](../../wf/workflows/spec/09b-llm-queue.md) | 12078 | 2026-09-05 | LLM 世界一輪做什麼、排隊規則、重啟怎麼算、舊紀錄清理。 | LLM、tick/daemon | 歷史（09-05 舊規格，現行改看 proto6/spec） |
| [spec/10-agent.md](../../wf/workflows/spec/10-agent.md) | 10976 | 2026-09-05 | agent 資料夾有什麼、每圈怎麼走、限制參數、什麼時候停。 | agent | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 7. 工具與通訊錄（2 份）

模型能碰的兩種對象：程式（工具登記表）與別的 agent（通訊錄）。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/11-tools-and-contacts.md](../../wf/workflows/ideas/11-tools-and-contacts.md) | 12241 | 2026-09-05 | 工具登記表與 agent 通訊錄；怎麼講給模型聽、叫完結果怎麼回。 | 工具、通訊錄、信件 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/11-tools-and-contacts.md](../../wf/workflows/spec/11-tools-and-contacts.md) | 11038 | 2026-09-05 | 工具登記表欄位、可預期性、危險工具、通訊錄。 | 工具、通訊錄、權限 | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 8. 指令面與核心分圈（2 份）

人在終端打什麼，以及底層怎麼切成幾圈、規範以哪份為準。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/12-cli-and-layering.md](../../wf/workflows/ideas/12-cli-and-layering.md) | 12161 | 2026-09-05 | 從終端倒推指令面；核心切四圈；規範只能有一份說了算。 | 指令面、kernel 分圈 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/12-cli.md](../../wf/workflows/spec/12-cli.md) | 12203 | 2026-09-05 | 所有子命令的全表（引數、退出碼、讀寫）與通則。 | 指令面 | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 9. 門房與權限（2 份）

檔案系統前的守門層，從只看不擋到真正擋下的三個層級。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [ideas/10-doorman.md](../../wf/workflows/ideas/10-doorman.md) | 11746 | 2026-09-05 | 門房（檔案系統前的守門層）要不要做：tmpfs 先、再 inotify 記帳、真要擋才 FUSE。 | 權限、門房 | 現行（構想集，只留脈絡但仍是入口） |
| [spec/13-doorman-l1.md](../../wf/workflows/spec/13-doorman-l1.md) | 12282 | 2026-09-05 | 門房第一級：只看不擋（inotify），只記帳不做事。 | 權限、門房 | 歷史（09-05 舊規格，現行改看 proto6/spec） |

## 10. 工作流與導航（非思想類，因超標一併列出）（2 份）

這三份不是構想，是找程式、排進度、派工用的，列出來是為了清單完整。

| 文件 | 大小 | 日期 | 在講什麼 | 主題 | 狀態 |
|---|---|---|---|---|---|
| [common/code-map.md](../../wf/workflows/common/code-map.md) | 9790 | 2026-10-10 | 要改程式碼前先看的導航圖：領域對應到檔案、真相層優先序。 | 導航、維運 | 現行（導航，會隨程式更新） |
| [dispatch/lessons.md](../../wf/workflows/dispatch/lessons.md) | 9213 | 2026-10-09 | 派工給多條線踩過的十二個坑（預掃、交接書矛盾、worktree、WSL 資源等）。 | 工作流、維運 | 現行（持續追加） |

## 主題 → 文件 反查表

| 主題 | 文件 |
|---|---|
| LLM | [07-daemon](../../wf/workflows/ideas/07-daemon.md)、[09-llm-world](../../wf/workflows/spec/09-llm-world.md)、[09b-llm-queue](../../wf/workflows/spec/09b-llm-queue.md) |
| agent | [08-agent](../../wf/workflows/ideas/08-agent.md)、[09-llm-world](../../wf/workflows/spec/09-llm-world.md)、[10-agent](../../wf/workflows/spec/10-agent.md) |
| kernel | [01-what-and-goals](../../wf/workflows/ideas/01-what-and-goals.md) |
| kernel 分圈 | [12-cli-and-layering](../../wf/workflows/ideas/12-cli-and-layering.md) |
| tick | [05-write-compile-run](../../wf/workflows/ideas/05-write-compile-run.md)、[05-series-format](../../wf/workflows/spec/05-series-format.md) |
| tick/daemon | [06-time-and-clocks](../../wf/workflows/ideas/06-time-and-clocks.md)、[07-daemon](../../wf/workflows/ideas/07-daemon.md)、[08-agent](../../wf/workflows/ideas/08-agent.md)、[roadmap](../../wf/workflows/roadmap.md)、[06-exec-and-run](../../wf/workflows/spec/06-exec-and-run.md)、[06b-run-rules](../../wf/workflows/spec/06b-run-rules.md)、[08-daemon](../../wf/workflows/spec/08-daemon.md)、[08b-daemon-reconcile](../../wf/workflows/spec/08b-daemon-reconcile.md)、[09b-llm-queue](../../wf/workflows/spec/09b-llm-queue.md) |
| 信件 | [09-call-and-failure](../../wf/workflows/ideas/09-call-and-failure.md)、[11-tools-and-contacts](../../wf/workflows/ideas/11-tools-and-contacts.md)、[07-call-and-delivery](../../wf/workflows/spec/07-call-and-delivery.md) |
| 判準 | [01-what-and-goals](../../wf/workflows/ideas/01-what-and-goals.md) |
| 名詞 | [01-terms](../../wf/workflows/spec/01-terms.md) |
| 呼叫與失敗 | [09-call-and-failure](../../wf/workflows/ideas/09-call-and-failure.md)、[07-call-and-delivery](../../wf/workflows/spec/07-call-and-delivery.md) |
| 導航 | [code-map](../../wf/workflows/common/code-map.md) |
| 工作流 | [lessons](../../wf/workflows/dispatch/lessons.md) |
| 工具 | [11-tools-and-contacts](../../wf/workflows/ideas/11-tools-and-contacts.md)、[11-tools-and-contacts](../../wf/workflows/spec/11-tools-and-contacts.md) |
| 待決 | [13-holes-and-play](../../wf/workflows/ideas/13-holes-and-play.md) |
| 指令 | [04-inside-aos](../../wf/workflows/ideas/04-inside-aos.md)、[04-inst-format](../../wf/workflows/spec/04-inst-format.md) |
| 指令面 | [12-cli-and-layering](../../wf/workflows/ideas/12-cli-and-layering.md)、[12-cli](../../wf/workflows/spec/12-cli.md) |
| 接力棒 | [05-write-compile-run](../../wf/workflows/ideas/05-write-compile-run.md)、[05-series-format](../../wf/workflows/spec/05-series-format.md) |
| 時空分層 | [02-folders-as-lists](../../wf/workflows/ideas/02-folders-as-lists.md)、[04-inside-aos](../../wf/workflows/ideas/04-inside-aos.md)、[06-time-and-clocks](../../wf/workflows/ideas/06-time-and-clocks.md)、[06-exec-and-run](../../wf/workflows/spec/06-exec-and-run.md) |
| 權限 | [03-land-and-life](../../wf/workflows/ideas/03-land-and-life.md)、[10-doorman](../../wf/workflows/ideas/10-doorman.md)、[02-layout](../../wf/workflows/spec/02-layout.md)、[11-tools-and-contacts](../../wf/workflows/spec/11-tools-and-contacts.md)、[13-doorman-l1](../../wf/workflows/spec/13-doorman-l1.md) |
| 維運 | [code-map](../../wf/workflows/common/code-map.md)、[lessons](../../wf/workflows/dispatch/lessons.md) |
| 編譯 | [05-write-compile-run](../../wf/workflows/ideas/05-write-compile-run.md)、[03-source-and-compile](../../wf/workflows/spec/03-source-and-compile.md) |
| 總綱 | [01-what-and-goals](../../wf/workflows/ideas/01-what-and-goals.md)、[13-holes-and-play](../../wf/workflows/ideas/13-holes-and-play.md)、[01-terms](../../wf/workflows/spec/01-terms.md) |
| 記憶 | [03-land-and-life](../../wf/workflows/ideas/03-land-and-life.md)、[02-layout](../../wf/workflows/spec/02-layout.md) |
| 資料夾模型 | [02-folders-as-lists](../../wf/workflows/ideas/02-folders-as-lists.md)、[03-land-and-life](../../wf/workflows/ideas/03-land-and-life.md)、[02-layout](../../wf/workflows/spec/02-layout.md) |
| 路線 | [roadmap](../../wf/workflows/roadmap.md) |
| 通訊錄 | [11-tools-and-contacts](../../wf/workflows/ideas/11-tools-and-contacts.md)、[11-tools-and-contacts](../../wf/workflows/spec/11-tools-and-contacts.md) |
| 門房 | [10-doorman](../../wf/workflows/ideas/10-doorman.md)、[13-doorman-l1](../../wf/workflows/spec/13-doorman-l1.md) |

## 為什麼沒封存

使用者要求過時的就封存，但判定要保守。逐項看下來：

- **ideas 13 章、roadmap、code-map、lessons**：仍是現行入口或現行工具，不封存。
- **spec 16 份（連同沒超標的 02b、05b 等同一疊）**：明確被取代（入口寫「歷史」，現行是 `proto6/spec`），符合封存條件。但整個 repo 有數百個檔連到它：proto5／proto6／proto7 的程式註解、教學、裁決紀錄，加上 `wf/INDEX.md`、`wf/WORKFLOWS.md`。archive 規則要求把活文件裡的連結拿掉，這會改動數百份已凍結的歷史紀錄，而且只封存超標的 16 份會把一疊規格拆成兩半、讓疊內互連全斷。所以我沒動，標「歷史」留著。要不要整疊封存、以及那數百個歷史連結怎麼處理，需要使用者決定。
