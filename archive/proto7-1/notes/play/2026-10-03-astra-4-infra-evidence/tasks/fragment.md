# 任務型態探針：給總報告合併

從 `proto7-1/README.md`、`spec.md` 進入，再沿入口讀核心 S 條號、實作及 problems-core／problems／前三輪 play 去重。無 kernel／agent／LLM，無修改產品程式。重現：repo 根執行 `python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/tasks/probe.py`；補案例 `.../probe.py deletekeep tockdirpeer`。每例一 daemon、一 node，標準 CLI，預設 interval 200 ms；short 為 100 ms。任務負載上限 12 秒、CPU 1.2 秒、輸出 8 MiB。探針自身設 subreaper，對屬於本例的遺留程序精確清理再回收，最後刪根。各例 JSON 保存 stop 前後檔案快照及獨立 OS 觀察，`cleanup.json` 確認 14 個實驗根與已知程序均不存在。原始 8 MiB out.log 只保留 size，未複製進證據。

## 一、數字與覆蓋

| 案例 | 看見什麼 | 證據 |
|---|---|---|
| 每回合 20 × `/bin/sleep .01`，共 5 個負載回合 | 100/100 任務 code 0 並 ended；tick 寫 round 的間隔 99／101／102／101 ms（設定 100 ms）；tick 本體寫 round 到 daemon 收結果 24～31 ms、中位 27 ms；tick 本體寫 round 到 tock 本體開始 79～85 ms。後續空回合不列入負載數字 | `short.json`、`summary.json` |
| 不理 SIGTERM | ctl 寫入至 done 1,230 ms，exit code -9，stop 無活程序殘留。是 P-17 的量化新證據，不重報「kill 阻塞」 | `ignore.json` |
| fork 後主程序先退出，同 PGID | 主程序 exit 0；task kill 在 121 ms 回 `ok:true / already ended`；正常 daemon stop 後孫程序仍活 | `fork.json` |
| fork 後 setsid，主程序先退出 | 與同 PGID 例相同；stop 後仍留 1 孫程序 | `forksetsid.json` |
| 單 CPU 忙迴圈 | wall 1.200 s、CPU 1.195 s（約一核心 99.6%）；本例 tick 完成間隔中位 200 ms；沒有 tick／tock 失敗。不是整機飽和測試 | `cpu.json` |
| 大量輸出 | 任務 1.025 ms 寫入 8,388,608 bytes，out.log 全量保留，正常 exit；tick 完成間隔中位 200 ms。是 page cache 接收耗時，未測 fsync／持續磁碟吞吐 | `output.json` |
| 改 cwd 到 `/` | 環境變數的絕對 taskdir 仍有效，exit 正常；沒有 tick／tock 失敗 | `chdir.json` |
| 刪自己 taskdir，任務繼續活 | status live 空，stop 正常返回卻留 runner＋任務共 2 程序 | `delete.json` |
| 刪自己 taskdir，保留 keep 表 | 3 回合重新起 3 份，每份又自刪；status live 空，stop 後 3 任務＋3 runner 共 6 活程序 | `deletekeep.json` |
| birth.json 寫成 `[1]` | 第 2～4 回合 tick 皆 rc 1，`list.get` AttributeError；原任務仍活，tock 仍成功，status.last_error 有錯誤 | `birtharray.json` |
| birth.json 寫成 `{broken` | 不報錯，但 keep 名稱失去辨識；3 回合累積 3 份同名活任務。stop 能靠各自 pid.json 殺掉 | `birthsyntax.json` |
| tock.json 寫成 `{broken` | 下一輪 tock 原子覆寫恢復正常，任務控制未受影響 | `tocksyntax.json` |
| tock.json 換成資料夾 | 4 輪 tock 皆 rc 1；負載中 `rounds.jsonl` 不存在；round 持續前進。加一個排序在後的健康 zzhealthy 任務，它連第一份 tock.json 都收不到 | `tockdir.json`、`tockdirpeer.json` |

時間數字用現有毫秒牆鐘欄位相減，這批未改時鐘；「tick 本體」與「tock 本體」不含 Python 啟動前段，不可與總報告完整 subprocess wall-time 混用。短任務實際 payload 是 sleep 要求 10 ms，沒有宣稱 OS 排程精確 10 ms。

## 二、新問題

### T1　任務主程序結束被當成整個工作結束，正常 kill／stop 也遺留孫程序〔技術選型〕

重現：`probe.py fork forksetsid`；task 呼叫 fork，子分支睡 12 秒，主程序 80 ms 後正常 exit。收到 exit.json 後寫 task ctl kill，再 SIGTERM daemon。結果：pid.json 指的主程序不在，exit 0、ended、status live=[]；kill 回 `already ended`，孫程序同 PGID 或新 session 兩種都活到探針清理。這不同於 P-04 的 daemon SIGKILL 孤兒，也不同於 P-05 的「主程序仍活而後代另開 session」：這次全程正常退出、正常 kill，甚至同群組都跳過。

涉及 S-01、S-06、S-10、S-17。合併覆核：細 spec 第 6 節同時規定已結束任務 kill 當成功，故此分支符合現行規則；管理缺口是主程序結束與其餘資源是否清空未分開，不判違反既定 kill 行為。需要持續的工作範圍識別和「主程序退出／整個工作清空」分別記錄；如何定義背景子程序屬任務的生命週期是技術選型。證據 `fork.json`、`forksetsid.json`，盲读檔案視角另放 `*-file-view.json`。

### T2　任務刪自己的任務目錄後，管理權與歷史一起消失，keep 會累積幽靈副本〔bug〕

重現：`probe.py delete deletekeep`；任務啟動 50 ms 後刪 `$AOS7_TASK`，繼續 sleep。單例 daemon 第 4 回合 live=[]，正常 stop 仍留 2 程序；keep 版第 3 回合 live=[]，3 組 runner＋任務仍活，正常 stop 全漏。rounds 的 started 留有 tid，卻没有對應 birth／pid／exit／ended，也沒有「追蹤丟失」錯誤。

涉及 S-01、S-06、S-10、S-17。這不是已知 P-15 的 node 消失：node 及 timeline 一直存在，只有自己的 taskdir 被刪。不是要求加安全沙箱，而是 daemon 不能只靠任務可刪的唯一索引承擔管理保證；至少要保留外置啟動身分、回收依據與缺失事件。證據 `delete.json`、`deletekeep.json`。

### T3　birth.json 型別／語法壞掉導致兩種相反故障：tick 持續失敗或 keep 無限補起〔bug〕

重現：`probe.py birtharray birthsyntax`。前者任務把 birth 寫成合法 JSON `[1]`，之後 tick 在 `live_names` 的 `.get` 崩潰，阻斷後續一般 tasks 啟動；後者寫 `{broken`，read_json 默認 `{}` 導致活名稱變成 None，3 回合起 3 個 birthsyntax。兩者都能 stop 清理，但沒有統一 corrupt 狀態，語法壞例甚至無 last_error。

涉及 S-01、S-06、S-09、S-10。第一輪已修的是 **ctl.json 非物件**，這次是 daemon 自己依賴的 birth，不能重用「控制檔已防錯」的結論。每任務 schema 校驗、隔離與退化狀態應在 tick 執行普通工作前明確，不能讓壞 metadata 被解讀成任務不存在。證據 `birtharray.json`、`birthsyntax.json`。

### T4　單任務通知路徑不可寫，會讓同 node 健康任務與整回合收尾一起失敗〔bug〕

重現：`probe.py tockdirpeer`；兩個長活任務，第一個把自己的 tock.json 建成目錄。4 回合 tock 在 os.replace 丟 IsADirectoryError，後面的 zzhealthy 沒有任何 tock.json，rounds.jsonl 沒有任何完成列；daemon 仍每輪開新 round。stop 時兩任務正常清掉，因此最後可能出現 stop 收尾完成列，不應用 stop 後檔案誤認運作中曾正常通知。

涉及 S-06、S-08、S-11。單純 tock 壞 JSON 可恢復；路徑結構錯誤則無逐任務隔離、無部分通知結果。證據 `tockdirpeer.json` 的 before_stop（非 after_stop）、對照 `tocksyntax.json`。這是新的 task 級寫入故障擴散，與整碟 ENOSPC 的回復語義可合併為一組需求。

## 三、daemon／tick 需求清單（重點）

| 優先度 | 必須提供什麼與證據 | 核心 spec 對應 | proto7-1 現況 |
|---|---|---|---|
| 必要 | 任務啟動時建立可持續回收的程序範圍；主程序已退出仍能辨認孫程序，kill 回條報實際範圍是否清空。T1，兩種 process group 皆失敗 | S-03／S-06／S-10／S-17 有方向；程序族群及完成判準未定 | 只有主 pid、runner、當下 `/proc` 後代快照；exit 檔先短路。未做到 |
| 必要 | 控制面的任務身分不能因 taskdir 被刪就失憶；保留啟動帳與缺失事件、停止時仍可回收，keep 遇不明狀態不得盲目重複補起。T2 | S-01／S-06／S-10 有方向；保存位置未定 | birth.json 同時是列舉唯一索引；未做到 |
| 必要 | 對所有運行 metadata 做型別與語義校驗，明示 corrupt／unknown，而非當不存在；一個壞任務不可讓其他 tasks 無法 tick。T3 | S-01／S-06／S-09，有方向、無 schema 細節 | ctl 已防錯，birth 未防；部分做到 |
| 必要 | tock 逐任務隔離通知失敗，保存成功／失敗清單及本回合終態；單任務路徑錯誤不阻止健康者收通知。T4 | S-06／S-08／S-11 直接相關；部分完成記錄格式未定 | 一次例外退出，沒有逐任務回條；未做到 |
| 應該 | 長控制操作與回合服務的預算可觀察，區分排隊、TERM 寬限、KILL、完成；不能只看到某輪 tick 突然很慢。ignore 的 1,230 ms 是 P-17 新量化 | S-09／S-17 相關；期限、并行方式屬技術選型 | 有固定 1 秒 grace、最終回條，無逐階段耗時；部分做到 |
| 應該 | 輸出 byte 數／保留上限／溢出政策可設定並反映狀態，容量保護不能寄望任務自行節制。單任務 8 MiB 沒節流全寫入，與 P-12 歷史檔不同的是 log 本身可極快長大 | S-06 可歸納，核心沒有 quota／日誌上限；技術選型 | out.log 直接 append、沒有上限、輪替或 bytes 狀態；未做到 |
| 可以 | 留存每階段 monotonic 耗時與 payload 類型，使短命任務量、Python runner 成本與任務 CPU 本身可比較。short 的 10 ms payload 仍需 24～31 ms tick本體起20份 | S-01／S-09 有方向；監測指標未定 | 只記牆鐘 at 和 rc；未做到完整分段 |

不應把「一個 CPU 任務未拖慢 daemon」推論成有 CPU 隔離保證；本次只確認單核心 bounded 忙迴圈。S-04 的逐程序執行有實測成本，但本組並未證明它是規模瓶頸，應以主規模表判斷。
