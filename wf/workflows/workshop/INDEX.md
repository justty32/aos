# workshop — 結構索引

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜[本工作流 README](README.md)

本檔只描述這資料夾裡有什麼、放在哪裡。流程怎麼跑（主持人／參與者／書記怎麼分工、
一場研討會怎麼進行）看 [README.md](README.md)。

## 頂層檔案

`records/` 與 `background/` 兩個資料夾各有一節在下面；`OPEN-QUESTIONS/` 由本表帶過，
不在這裡重列它的十三個題組檔（那張表在它自己的 README，重列會打架）。

| 檔案 | 是什麼 | 什麼時候會想看 |
|---|---|---|
| [README.md](README.md) | 工作流說明：角色分工、身份怎麼挑、一場研討會怎麼跑、紀錄怎麼收。**模板、收場那兩棒、指令形態已從這裡拆出去**，見下面三列。 | 第一次接觸這個工作流，或要主持一場新的研討會時。 |
| [briefs.md](briefs.md) | 發給參與者的兩份模板：議題書（主持人寫的第一塊）與參與者任務書（每輪、每人一份）。 | 要開場、或每一輪要派任務書時。 |
| [staff.md](staff.md) | 收場那兩棒：書記與祕書各自是誰、讀什麼、寫什麼、沙盒怎麼開，含可整段複製的〈書記任務書〉，以及主持人在這兩棒裡只做的那三件事。 | 一場跑完要收攏成紀錄，或要祕書寫背景資料時。 |
| [commands.md](commands.md) | `codex exec` 的指令形態（全部已實測）：家裡與公司兩台機器各自的命令、reasoning effort 與推理摘要的取捨、`--json` 抓 session id、平行與依序、逾時與檔案落點。 | 真的要把參與者叫起來、要打指令時。 |
| [OPEN-QUESTIONS/](OPEN-QUESTIONS/README.md) | 把七場研討會裡「使用者尚未拍板」的問題去重、彙整成一份待答清單，附候選答案。**十三個題組檔＋README**，分「擋住事情的（第 1–24 題）」與「可以慢慢想的（第 25–37 題）」，README 末尾有題號速查。 | 想知道 aos 設計目前卡在哪、還有什麼沒決定時。 |
| [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) | 上面那個資料夾的**原路徑指標檔**：只留導航，並把舊的 `#<題號>-<標題>` 錨點全部重新宣告一次，所以別處既有的連結仍然有效。 | 拿著舊連結連過來、或不確定某題號現在落在哪個檔時。 |
| [BACKGROUND.md](BACKGROUND.md) | 祕書寫的白話背景資料總表：〈分檔導航〉一張表連到 `background/` 十七檔，〈名詞索引〉逐個名詞指到對應的檔。 | 讀紀錄或待答問題時碰到看不懂的詞或編號題目時。 |
| [SESSIONS.md](SESSIONS.md) | 2026-08-25 那天所有 `codex exec` session 的 id 與 resume 方式，含機器限制與已知踩坑。 | 要接續某一場研討會、或重啟 codex 續談 aos 設計時。 |

## records/（研討會紀錄，12 場）

每場一列。「收攏到什麼程度」是誠實現況，不是理想狀態——多數 2026-08-25 這批已經跑完
輪次、收出方向，但紀錄裡各自的「轉交提案」大多**還沒經使用者拍板進規格／roadmap**。

**七場已拆成資料夾**（下表連的就是資料夾的 README，檔頭表格、〈先讀這段（500 字懶人包）〉
與續場資訊都在那裡）；原路徑 `records/<主題>.md` 一律留成指標檔，舊連結仍然有效。
**五場仍是單檔**——連結結尾有沒有 `/` 就是分別。

| 紀錄 | 談什麼 | 收攏到什麼程度 |
|---|---|---|
| [exec-as-pure-cpu.md](records/exec-as-pure-cpu.md) | 假如 `aos exec` 只保持單純的取指令執行指令，彙整／取件／釋放／投遞全部改用 argv 執行、而且都算 core——這個體系的好壞。收出 3 條好、6 條壞與 15 條轉交提案，末尾附〈白話導讀〉。**參與者是 Claude Opus 5 sub agent，不是 codex**（所以不在 SESSIONS.md 裡）。 | 開場 2026-08-26。兩輪已跑完並收場，轉交提案未拍板。 |
| [core-process-and-subprocess/](records/core-process-and-subprocess/README.md) | 核心行程、子行程，與外部處理器的契約——`kernel.json`、`func`／job／lane 拆分、多核心該不該學 Linux root 行程。 | R1＋R2 已跑完；使用者在 R1 後當場拍板三條（`kernel.json` 收、`func` 拆成 job/lane、多核學 Linux），其餘轉交提案未拍板。 |
| [four-open-choices-tradeoffs/](records/four-open-choices-tradeoffs/README.md) | 四個懸而未決的設計選擇（`World` 抽象、`kernel.json` 分層與否、子行程拓樸 A/B、親緣綁路徑或 UUID）各自的優缺點。 | R1＋R2 已跑完；刻意不逼取捨，只把代價攤開給使用者看，轉交提案未拍板。 |
| [agent-loop-architecture/](records/agent-loop-architecture/README.md) | agent loop 真的要做出來的話架構長什麼樣、需要哪些基礎 `aos core` 功能（publish／deliver／effect）。 | R1＋R2 已收攏成方向（三者只能先做三樣時四位選得完全相同），轉交提案未拍板。 |
| [step-back-review/](records/step-back-review/README.md) | 回頭審視前三場研討會的全部產出：哪些該收回、哪條假設從沒被驗證過、東西是不是長歪了。 | 一輪已跑完並收場，轉交提案未拍板。 |
| [free-ideation.md](records/free-ideation.md) | 隨意發想（無題）：aos 也許是郵局不是作業系統、世界快照與分支、人也可以是一顆 CPU。 | 一輪已收場，沒有正式的「轉交提案」小節，但收尾列了「可能真的該做的」清單（四位獨立都選分支世界）。 |
| [workflows-on-aos/](records/workflows-on-aos/README.md) | 怎麼用 aos 實現現有 `wf/workflows` 那套功能：活狀態、安裝升級、tick／schedule 該不該機械化。 | 一輪已收場；除轉交提案未拍板外，另留了一份要拿去問使用者的清單（8 題，含「最近到底卡在哪」）。 |
| [tool-interop/](records/tool-interop/README.md) | aos 如何跟 pi coding agent、skills、MCP 等現有工具協作，含 `aos deliver` 的合成版 `--help` 追問輪。 | 主輪＋追問輪已跑完並收場，轉交提案未拍板。 |
| [final-summary.md](records/final-summary.md) | 前六場研討會結束後，同一批四位參與者的最後發言：不必回答的問題、明天第一步、專案會怎麼死。 | 已結束（狀態欄位明寫「已結束」），是整批研討會的收尾，之後這四個 session 不再續談。 |
| [finite-resource-queue.md](records/finite-resource-queue.md) | 有限資源——`aos exec` 近乎無窮但 LLM endpoint 有限，CPU 該怎麼指揮 GPU、aos 該怎麼做類比設計。 | **更早的一場**（開場 2026-08-24），只跑了 R1，未收攏。 |
| [lisp-in-aos.md](records/lisp-in-aos.md) | lisp 在 `.aos` 裡長什麼樣：控制、環境、frame 堆疊、handler、狀態的共同項。 | **更早的一場**（開場 2026-08-24），R1 只跑了 5 位參與者中的 3 位，中止未收攏。 |
| [pre-agent-loop-core/](records/pre-agent-loop-core/README.md) | agent loop 之前該先做哪些 core 小專案（取指令、快取、`aos wait`、`aos func`）。舊「辯論風格」council 紀錄，角色是立場不是身份，內容仍有效。 | 開場 2026-08-24，R1–R3 已收議，但四件轉交提案**還沒經使用者拍板**。 |

## background/（祕書寫的白話背景資料，17 份）

分兩類：**名詞解釋類**（9 份，查專有名詞用）與**問題導讀類**（8 份，對應
[OPEN-QUESTIONS/](OPEN-QUESTIONS/README.md) 的阻塞題編號）。逐檔一句話說明取自
[BACKGROUND.md](BACKGROUND.md) 自己的〈分檔導航〉，這裡不重複展開內容，避免跟它打架。

其中 `execution-and-turns` 的詞條長大後**另拆成了資料夾**（三份＋README，README 有 12 個詞的
逐詞索引），下表連的是那個 README；原路徑 `background/execution-and-turns.md` 仍在，
它要不要收成指標檔由拆那份的人收尾，不影響本表。

### 名詞解釋類

| 檔案 | 涵蓋什麼 |
|---|---|
| [execution-and-turns/](background/execution-and-turns/README.md) | world、`kernel.json`、`.runi`、tick 與 cursor 等回合執行詞彙。**已拆成資料夾**：回合邊界與崩潰現場／回合開頭的固定步驟與版本／喚醒、進度與短路。 |
| [work-and-lanes.md](background/work-and-lanes.md) | process、lane、job 與 promotion 的分界。 |
| [process-control.md](background/process-control.md) | root、control plane、capability、proc-table、join 與 handle。 |
| [delivery-contract.md](background/delivery-contract.md) | Publish、Deliver、correlation ID 與 receipt。 |
| [reliability.md](background/reliability.md) | Effect、idempotency key、ledger、`unknown`、two-phase commit 與 durability。 |
| [agent-loop.md](background/agent-loop.md) | golden slice、agent loop、driver／adapter、tool allowlist 與 coding agent。 |
| [agent-interop.md](background/agent-interop.md) | skill、MCP、façade、session 與 envelope。 |
| [workflow-state.md](background/workflow-state.md) | front matter、唯一真源、reconcile、ABI／schema 與 template 升級。 |
| [queues-and-resources.md](background/queues-and-resources.md) | Maildir、queue／spool／inbox、jobserver 與 DMA／fence。 |

### 問題導讀類

對應 [OPEN-QUESTIONS/](OPEN-QUESTIONS/README.md) 裡的阻塞題編號（第 1–24 題）。
**第 25–37 題目前沒有導讀。**

| 檔案 | 對應題號 |
|---|---|
| [questions-direction.md](background/questions-direction.md) | 第 1–3 題：痛點、近期範圍與第一個產品體驗。 |
| [questions-host-and-trust.md](background/questions-host-and-trust.md) | 第 4–6 題：執行信任、第一個宿主與第一條可執行路徑。 |
| [questions-deliver.md](background/questions-deliver.md) | 第 7–9 題：命令列形狀、key 與輸出／錯誤契約。 |
| [questions-workflow-state.md](background/questions-workflow-state.md) | 第 10–11 題：狀態放哪裡，以及人如何修改。 |
| [questions-reliability.md](background/questions-reliability.md) | 第 12–14 題：unknown、崩潰保證與斷電持久性。 |
| [questions-workflow-policy.md](background/questions-workflow-policy.md) | 第 15–17 題：完成歷史、template 更新與排程。 |
| [questions-agent-context.md](background/questions-agent-context.md) | 第 18、19、24 題：輸入上下文、續談狀態與公開工具集合。 |
| [questions-child-work.md](background/questions-child-work.md) | 第 20–23 題：子工作提交、等待、失敗與核心步驟失敗。 |

## 建議閱讀路徑

- **想快速掌握結論** → [records/final-summary.md](records/final-summary.md)（七場之後的最終收尾）。
- **想知道還有什麼沒決定** → [OPEN-QUESTIONS/README.md](OPEN-QUESTIONS/README.md)。
- **看不懂名詞或題號** → [BACKGROUND.md](BACKGROUND.md)，再挑對應的 `background/` 檔。
- **要主持一場新的研討會** → [README.md](README.md) 看流程，[briefs.md](briefs.md) 抄模板，
  [commands.md](commands.md) 打指令，跑完照 [staff.md](staff.md) 收場。
- **要重啟 codex 續場、接回某一批參與者** → [SESSIONS.md](SESSIONS.md)。
- **要看某一場的完整發想過程** → 上面 records/ 表挑對應紀錄，先讀開頭的「先讀這段（500 字懶人包）」（多數紀錄有這段）；已拆成資料夾的那七場，懶人包在該場的 README。

## 為什麼這一檔不拆

本檔超過 `wf/STRUCTURE.md` 的 8192 bytes 門檻，但**刻意不拆**。門檻是觸發檢視的訊號、
非硬性上限，而這一檔的職責就是「**一張總表**」——把它按「頂層檔案／records／background」
拆成三張，等於把「我要找的東西在哪一張」變成新問題，而那正是索引該消滅的問題。
內容也已經壓到最薄：每個子資料夾的細目都留在它自己的 README（`OPEN-QUESTIONS/`、
`background/`、七份拆成資料夾的紀錄），本檔只到「進哪個門」為止，不往下展開。
真要再瘦，該先問的是「有沒有哪一節在複述別的檔」，不是切成幾份。
