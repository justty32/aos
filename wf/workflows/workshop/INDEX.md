# workshop — 結構索引

← [WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜[本工作流 README](README.md)

本檔只描述這資料夾裡有什麼、放在哪裡。流程怎麼跑（主持人／參與者／書記怎麼分工、
一場研討會怎麼進行）看 [README.md](README.md)。

## 頂層檔案

| 檔案 | 是什麼 | 什麼時候會想看 |
|---|---|---|
| [README.md](README.md) | 工作流說明：角色分工、身份怎麼挑、一場研討會怎麼跑、書記／祕書怎麼寫紀錄。 | 第一次接觸這個工作流，或要主持一場新的研討會時。 |
| [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) | 把七場研討會裡「使用者尚未拍板」的問題去重、彙整成一份待答清單，附候選答案。 | 想知道 aos 設計目前卡在哪、還有什麼沒決定時。 |
| [BACKGROUND.md](BACKGROUND.md) | 祕書寫的白話背景資料總表，分「名詞導航」與「題目導讀」兩張表連到 `background/`。 | 讀紀錄或待答問題時碰到看不懂的詞或編號題目時。 |
| [SESSIONS.md](SESSIONS.md) | 2026-08-25 那天所有 `codex exec` session 的 id 與 resume 方式，含機器限制與已知踩坑。 | 要接續某一場研討會、或重啟 codex 續談 aos 設計時。 |

## records/（研討會紀錄，11 檔）

每場一列。「收攏到什麼程度」是誠實現況，不是理想狀態——多數 2026-08-25 這批已經跑完
輪次、收出方向，但紀錄裡各自的「轉交提案」大多**還沒經使用者拍板進規格／roadmap**。

| 紀錄 | 談什麼 | 收攏到什麼程度 |
|---|---|---|
| [core-process-and-subprocess.md](records/core-process-and-subprocess.md) | 核心行程、子行程，與外部處理器的契約——`kernel.json`、`func`／job／lane 拆分、多核心該不該學 Linux root 行程。 | R1＋R2 已跑完；使用者在 R1 後當場拍板三條（`kernel.json` 收、`func` 拆成 job/lane、多核學 Linux），其餘轉交提案未拍板。 |
| [four-open-choices-tradeoffs.md](records/four-open-choices-tradeoffs.md) | 四個懸而未決的設計選擇（`World` 抽象、`kernel.json` 分層與否、子行程拓樸 A/B、親緣綁路徑或 UUID）各自的優缺點。 | R1＋R2 已跑完；刻意不逼取捨，只把代價攤開給使用者看，轉交提案未拍板。 |
| [agent-loop-architecture.md](records/agent-loop-architecture.md) | agent loop 真的要做出來的話架構長什麼樣、需要哪些基礎 `aos core` 功能（publish／deliver／effect）。 | R1＋R2 已收攏成方向（三者只能先做三樣時四位選得完全相同），轉交提案未拍板。 |
| [step-back-review.md](records/step-back-review.md) | 回頭審視前三場研討會的全部產出：哪些該收回、哪條假設從沒被驗證過、東西是不是長歪了。 | 一輪已跑完並收場，轉交提案未拍板。 |
| [free-ideation.md](records/free-ideation.md) | 隨意發想（無題）：aos 也許是郵局不是作業系統、世界快照與分支、人也可以是一顆 CPU。 | 一輪已收場，沒有正式的「轉交提案」小節，但收尾列了「可能真的該做的」清單（四位獨立都選分支世界）。 |
| [workflows-on-aos.md](records/workflows-on-aos.md) | 怎麼用 aos 實現現有 `wf/workflows` 那套功能：活狀態、安裝升級、tick／schedule 該不該機械化。 | 一輪已收場；除轉交提案未拍板外，另留了一份要拿去問使用者的清單（8 題，含「最近到底卡在哪」）。 |
| [tool-interop.md](records/tool-interop.md) | aos 如何跟 pi coding agent、skills、MCP 等現有工具協作，含 `aos deliver` 的合成版 `--help` 追問輪。 | 主輪＋追問輪已跑完並收場，轉交提案未拍板。 |
| [final-summary.md](records/final-summary.md) | 前六場研討會結束後，同一批四位參與者的最後發言：不必回答的問題、明天第一步、專案會怎麼死。 | 已結束（狀態欄位明寫「已結束」），是整批研討會的收尾，之後這四個 session 不再續談。 |
| [finite-resource-queue.md](records/finite-resource-queue.md) | 有限資源——`aos exec` 近乎無窮但 LLM endpoint 有限，CPU 該怎麼指揮 GPU、aos 該怎麼做類比設計。 | **更早的一場**（開場 2026-08-24），只跑了 R1，未收攏。 |
| [lisp-in-aos.md](records/lisp-in-aos.md) | lisp 在 `.aos` 裡長什麼樣：控制、環境、frame 堆疊、handler、狀態的共同項。 | **更早的一場**（開場 2026-08-24），R1 只跑了 5 位參與者中的 3 位，中止未收攏。 |
| [pre-agent-loop-core.md](records/pre-agent-loop-core.md) | agent loop 之前該先做哪些 core 小專案（取指令、快取、`aos wait`、`aos func`）。舊「辯論風格」council 紀錄，角色是立場不是身份，內容仍有效。 | 開場 2026-08-24，R1–R3 已收議，但四件轉交提案**還沒經使用者拍板**。 |

## background/（祕書寫的白話背景資料，17 檔）

分兩類：**名詞解釋類**（9 檔，查專有名詞用）與**問題導讀類**（8 檔，對應
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 的阻塞題編號）。逐檔一句話說明取自
[BACKGROUND.md](BACKGROUND.md) 自己的〈分檔導航〉，這裡不重複展開內容，避免跟它打架。

### 名詞解釋類

| 檔案 | 涵蓋什麼 |
|---|---|
| [execution-and-turns.md](background/execution-and-turns.md) | world、`kernel.json`、`.runi`、tick 與 cursor 等回合執行詞彙。 |
| [work-and-lanes.md](background/work-and-lanes.md) | process、lane、job 與 promotion 的分界。 |
| [process-control.md](background/process-control.md) | root、control plane、capability、proc-table、join 與 handle。 |
| [delivery-contract.md](background/delivery-contract.md) | Publish、Deliver、correlation ID 與 receipt。 |
| [reliability.md](background/reliability.md) | Effect、idempotency key、ledger、`unknown`、two-phase commit 與 durability。 |
| [agent-loop.md](background/agent-loop.md) | golden slice、agent loop、driver／adapter、tool allowlist 與 coding agent。 |
| [agent-interop.md](background/agent-interop.md) | skill、MCP、façade、session 與 envelope。 |
| [workflow-state.md](background/workflow-state.md) | front matter、唯一真源、reconcile、ABI／schema 與 template 升級。 |
| [queues-and-resources.md](background/queues-and-resources.md) | Maildir、queue／spool／inbox、jobserver 與 DMA／fence。 |

### 問題導讀類

對應 [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 裡的阻塞題編號（第 1–24 題）。

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
- **想知道還有什麼沒決定** → [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)。
- **看不懂名詞或題號** → [BACKGROUND.md](BACKGROUND.md)，再挑對應的 `background/` 檔。
- **要重啟 codex 續場、接回某一批參與者** → [SESSIONS.md](SESSIONS.md)。
- **要看某一場的完整發想過程** → 上面 records/ 表挑對應紀錄，先讀開頭的「先讀這段（500 字懶人包）」（多數紀錄有這段）。
