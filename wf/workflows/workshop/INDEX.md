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
| [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) | 上面那個資料夾的**原路徑指標檔**：只留一句指向 README 的指標（題號速查在 README 末尾）。 | 拿著舊連結連過來時。 |
| [BACKGROUND.md](BACKGROUND.md) | 祕書寫的白話背景資料的**原路徑指標檔**；〈分檔導航〉（連到 `background/` 十七檔）與〈名詞索引〉已搬到 [background/README.md](background/README.md)。 | 讀紀錄或待答問題時碰到看不懂的詞或編號題目時。 |
| [SESSIONS.md](SESSIONS.md) | 2026-08-25 那天所有 `codex exec` session 的 id 與 resume 方式，含機器限制與已知踩坑。 | 要接續某一場研討會、或重啟 codex 續談 aos 設計時。 |

## records/（研討會紀錄，12 場）

每場一列的總表（談什麼、收攏到什麼程度、哪幾場已拆成資料夾）在 **[records/README.md](records/README.md)**。

## background/（祕書寫的白話背景資料，17 份）

分檔導航與名詞索引在 **[background/README.md](background/README.md)**（原路徑 [BACKGROUND.md](BACKGROUND.md) 只留指標）。

## 建議閱讀路徑

- **想快速掌握結論** → [records/final-summary.md](records/final-summary.md)（七場之後的最終收尾）。
- **想知道還有什麼沒決定** → [OPEN-QUESTIONS/README.md](OPEN-QUESTIONS/README.md)。
- **看不懂名詞或題號** → [background/README.md](background/README.md)，再挑對應的 `background/` 檔。
- **要主持一場新的研討會** → [README.md](README.md) 看流程，[briefs.md](briefs.md) 抄模板，
  [commands.md](commands.md) 打指令，跑完照 [staff.md](staff.md) 收場。
- **要重啟 codex 續場、接回某一批參與者** → [SESSIONS.md](SESSIONS.md)。
- **要看某一場的完整發想過程** → [records/README.md](records/README.md) 挑對應紀錄，先讀開頭的「先讀這段（500 字懶人包）」（多數紀錄有這段）；已拆成資料夾的那七場，懶人包在該場的 README。

## 分層

2026-09-25 整理：本檔原本 12 KB、刻意不拆（理由是「一張總表」）。照 [STRUCTURE](../../STRUCTURE.md)「導航表超 8 KB 就往下一層放」，
records／background 兩張表各搬進自己資料夾的 README，本檔只留頂層檔案表與「進哪個門」的指標。
