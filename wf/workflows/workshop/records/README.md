# workshop／records — 研討會紀錄索引

← [workshop INDEX](../INDEX.md)｜[workshop README](../README.md)

> 2026-09-25 整理：這張表原本在 [workshop/INDEX.md](../INDEX.md) 的〈records/〉節，INDEX 超過 8 KB，照「導航表超 8 KB 就往下一層放」整節逐字搬來這裡。

## 12 場紀錄

每場一列。「收攏到什麼程度」是誠實現況，不是理想狀態——多數 2026-08-25 這批已經跑完
輪次、收出方向，但紀錄裡各自的「轉交提案」大多**還沒經使用者拍板進規格／roadmap**。

**七場已拆成資料夾**（下表連的就是資料夾的 README，檔頭表格、〈先讀這段（500 字懶人包）〉
與續場資訊都在那裡）；原路徑 `records/<主題>.md` 一律留成指標檔，舊連結仍然有效。
**五場仍是單檔**——連結結尾有沒有 `/` 就是分別。

| 紀錄 | 談什麼 | 收攏到什麼程度 |
|---|---|---|
| [exec-as-pure-cpu.md](exec-as-pure-cpu.md) | 假如 `aos exec` 只保持單純的取指令執行指令，彙整／取件／釋放／投遞全部改用 argv 執行、而且都算 core——這個體系的好壞。收出 3 條好、6 條壞與 15 條轉交提案，末尾附〈白話導讀〉。**參與者是 Claude Opus 5 sub agent，不是 codex**（所以不在 SESSIONS.md 裡）。 | 開場 2026-08-26。兩輪已跑完並收場，轉交提案未拍板。 |
| [core-process-and-subprocess/](core-process-and-subprocess/README.md) | 核心行程、子行程，與外部處理器的契約——`kernel.json`、`func`／job／lane 拆分、多核心該不該學 Linux root 行程。 | R1＋R2 已跑完；使用者在 R1 後當場拍板三條（`kernel.json` 收、`func` 拆成 job/lane、多核學 Linux），其餘轉交提案未拍板。 |
| [four-open-choices-tradeoffs/](four-open-choices-tradeoffs/README.md) | 四個懸而未決的設計選擇（`World` 抽象、`kernel.json` 分層與否、子行程拓樸 A/B、親緣綁路徑或 UUID）各自的優缺點。 | R1＋R2 已跑完；刻意不逼取捨，只把代價攤開給使用者看，轉交提案未拍板。 |
| [agent-loop-architecture/](agent-loop-architecture/README.md) | agent loop 真的要做出來的話架構長什麼樣、需要哪些基礎 `aos core` 功能（publish／deliver／effect）。 | R1＋R2 已收攏成方向（三者只能先做三樣時四位選得完全相同），轉交提案未拍板。 |
| [step-back-review/](step-back-review/README.md) | 回頭審視前三場研討會的全部產出：哪些該收回、哪條假設從沒被驗證過、東西是不是長歪了。 | 一輪已跑完並收場，轉交提案未拍板。 |
| [free-ideation.md](free-ideation.md) | 隨意發想（無題）：aos 也許是郵局不是作業系統、世界快照與分支、人也可以是一顆 CPU。 | 一輪已收場，沒有正式的「轉交提案」小節，但收尾列了「可能真的該做的」清單（四位獨立都選分支世界）。 |
| [workflows-on-aos/](workflows-on-aos/README.md) | 怎麼用 aos 實現現有 `wf/workflows` 那套功能：活狀態、安裝升級、tick／schedule 該不該機械化。 | 一輪已收場；除轉交提案未拍板外，另留了一份要拿去問使用者的清單（8 題，含「最近到底卡在哪」）。 |
| [tool-interop/](tool-interop/README.md) | aos 如何跟 pi coding agent、skills、MCP 等現有工具協作，含 `aos deliver` 的合成版 `--help` 追問輪。 | 主輪＋追問輪已跑完並收場，轉交提案未拍板。 |
| [final-summary.md](final-summary.md) | 前六場研討會結束後，同一批四位參與者的最後發言：不必回答的問題、明天第一步、專案會怎麼死。 | 已結束（狀態欄位明寫「已結束」），是整批研討會的收尾，之後這四個 session 不再續談。 |
| [finite-resource-queue.md](finite-resource-queue.md) | 有限資源——`aos exec` 近乎無窮但 LLM endpoint 有限，CPU 該怎麼指揮 GPU、aos 該怎麼做類比設計。 | **更早的一場**（開場 2026-08-24），只跑了 R1，未收攏。 |
| [lisp-in-aos.md](lisp-in-aos.md) | lisp 在 `.aos` 裡長什麼樣：控制、環境、frame 堆疊、handler、狀態的共同項。 | **更早的一場**（開場 2026-08-24），R1 只跑了 5 位參與者中的 3 位，中止未收攏。 |
| [pre-agent-loop-core/](pre-agent-loop-core/README.md) | agent loop 之前該先做哪些 core 小專案（取指令、快取、`aos wait`、`aos func`）。舊「辯論風格」council 紀錄，角色是立場不是身份，內容仍有效。 | 開場 2026-08-24，R1–R3 已收議，但四件轉交提案**還沒經使用者拍板**。 |
