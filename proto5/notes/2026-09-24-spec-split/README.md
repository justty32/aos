# 2026-09-24 spec 拆檔

← [notes 索引](../README.md)｜拆完的規範：[spec 總導航](../../spec/README.md)

使用者原話：「proto5 的 spec，每個檔案都好大，麻煩拆檔重構。」

## 做了什麼

- 九份規範各變成一個資料夾 `proto5/spec/<名>/`（先 `git mv <名>.md <名>/README.md` 單獨一個 commit，`git log --follow` 追得到歷史），再依原本的 § 節拆成小檔。
- **內容逐字搬**。只動了四樣：子檔標題降一級（`##`→`#`）、檔間連結改指新位置、每檔頂部一行「← 上層導航」、各 README 的「各節」表（前面加一句說明：原文「檔尾〈沿革〉」「見下」這類方位詞是拆檔前的位置）。
- 唯一新增的標題文字：kernel §6 命令列原本 12 KB、節內沒有小標，在兩個段落處切成 `cli.md`／`boot.md`／`cli-ops.md`，後兩檔補上 `# 6. 命令列（續）：…`。
- 各資料夾 README＝原檔開頭（標題、導航行、版本、一句話）＋「已拍板的前提」＋「這份沒管的」＋各節表。沒有前提節的（directives、inst-posix、aos-exec）就只有開頭＋沒管的／誰用這套＋各節表。
- 節號不變，文中「§4.1」這類純文字引用到該資料夾 README 查。
- aos-exec（8.7 KB）、aos-llm（11.8 KB）也拆，理由是九份結構一致、而且 aos-exec 本來就略超 8 KB。
- 沒照 [STRUCTURE](../../../wf/STRUCTURE.md)「拆資料夾時原路徑保留當入口」：任務書明定舊單檔刪掉，外部連結全改了，所以不留入口檔。

驗證：去掉標題 `#` 數與連結目標後，九份非空行多重集合跟拆前完全相同（腳本比對；astra 另用區塊法驗：159 塊全配上、2083 行恰好各覆蓋一次）。全套測試 1100 條綠。

## 拆前後對照（大小 KB）

| 舊檔 | 檔數 | 拆後（資料夾內） |
|---|---|---|
| `kernel.md` 43.4 | 15 | `README.md` 3.4、`terms.md` 5.9、`home.md` 4.0、`ledger.md` 4.4、`syscall.md` 3.2、`tick.md` 5.8、`echo.md` 1.4、`daemon-link.md` 1.3、`cli.md` 3.4、`boot.md` 3.0、`cli-ops.md` 5.6、`no-overlap.md` 0.7、`choices.md` 1.6、`impl-notes.md` 0.9、`history.md` 1.0 |
| `aos-agent.md` 47.6 | 16 | `README.md` 4.9、`essentials.md` 2.3、`terms.md` 1.6、`cli.md` 2.6、`cli-talk.md` 5.2、`cli-status.md` 5.5、`tick.md` 5.4、`gate.md` 1.6、`send.md` 4.6、`collect.md` 4.5、`settle.md` 2.0、`idle.md` 1.5、`pause-clean.md` 1.6、`register.md` 4.5、`rulings.md` 1.2、`history.md` 1.0 |
| `cpu.md` 25.9 | 10 | `README.md` 2.9、`terms.md` 3.6、`layout.md` 2.9、`messages.md` 3.0、`methods.md` 4.6、`stop.md` 3.3、`lifecycle.md` 4.2、`choices.md` 1.3、`impl-notes.md` 0.7、`history.md` 1.0 |
| `daemon.md` 24.0 | 11 | `README.md` 2.3、`terms.md` 3.8、`home.md` 3.4、`spawn.md` 3.0、`methods.md` 1.3、`loop.md` 1.7、`shutdown.md` 2.3、`lifecycle.md` 3.8、`choices.md` 1.6、`impl-notes.md` 1.1、`history.md` 1.0 |
| `agent.md` 22.9 | 10 | `README.md` 3.3、`essentials.md` 1.7、`terms.md` 1.0、`layout.md` 2.0、`directives.md` 1.6、`info.md` 5.1、`state.md` 7.1、`errors.md` 0.5、`rulings.md` 1.2、`history.md` 0.9 |
| `inst-posix.md` 17.6 | 7 | `README.md` 2.0、`metainfo.md` 2.3、`fields.md` 4.1、`opt.md` 3.2、`directives.md` 2.9、`errors.md` 1.7、`exec.md` 2.4 |
| `directives.md` 15.4 | 6 | `README.md` 1.7、`basics.md` 2.4、`fmt.md` 2.3、`ref.md` 4.9、`opt.md` 1.7、`errors.md` 3.1 |
| `aos-llm.md` 11.8 | 7 | `README.md` 2.3、`usage.md` 2.2、`config.md` 1.7、`request.md` 3.6、`timeouts.md` 1.0、`rulings.md` 1.0、`history.md` 0.9 |
| `aos-exec.md` 8.7 | 4 | `README.md` 1.4、`usage.md` 2.8、`exit.md` 3.2、`api.md` 1.9 |

另加 `spec/README.md` 總導航（1.5 KB）。共 86 檔＋總導航，最大 `agent/state.md` 7.1 KB（7248 bytes，§4 整節，不再切）。表內 README 大小是加方位詞說明前量的，約多 0.2 KB。

## 連結

- repo 裡指進舊九份的 markdown 連結改了 **380 處（27 檔）**：proto5/README 16、lib/README 46、proto5/notes 307、wf/session_logs 10、proto4-3/docs/exec.md 1。另 lib docstring 明寫 `spec/xxx.md` 路徑的 7 處改成 `spec/xxx/`；像「kernel.md §3」這種不帶路徑的節號引用沒動（節號照舊，README 查得到）。
- 改法：帶 `#錨點`→錨點所在小檔；連結字帶 `§n`／「第 n 節」→該節所在檔；帶 `:行號`（舊審查報告，行號是當時版本的）→用 `git blame`（跳過幾個純改路徑的 commit）找寫下那行時的規範版本，看那行落在哪一節、再用節標題對到新檔；當時的節現在已不存在（例如第 1 版 aos-agent 的「3. 走一格到底做什麼」）的 29 處→資料夾 README。舊名 `exec.md`、`aos-llm-call.md` 的連結一併指到 aos-exec／aos-llm。絕對路徑連結改成相對路徑。
- 規範檔之間的連結在拆的時候一起改（不算在 380 內）。
- 檢查：全 repo（不含 `.claude/worktrees/`）指進 `proto5/spec/` 的連結 745 條，檔不在或錨點不在的 **0**。`wf-lint proto5 thinking wf` 的 BROKEN 從 836 降到 559（剩下的是 `lib/x.py:123` 這類跟 spec 無關的行號連結，不在本次範圍）。
- rebase 到 main 時，另一隊的 notes tidy（0235aed）改過其中 8 份筆記：衝突檔一律取 main 的版本、再重跑同一支改連結腳本。tidy 隊留給本隊的 [spec-links.tsv](../2026-09-24-tidy/spec-links.tsv) 是他們的資料檔，沒動；表裡列的連結已全部改好。

## astra 抽查

任務書 [astra-task.md](astra-task.md)，回報全文 [astra-report.md](astra-report.md)（codex gpt-6-astra，`-s read-only`）。

- 結論：**可以收，必修 0**。
- 逐字抽查 20 段（kernel 切點前後、程式碼區塊、表格、README 裡的前提都有抽）：全部只有標題層級與連結目標的差異。
- 完整性：自寫區塊比對，159 塊全配上，原文 2083 行非空行恰好各覆蓋一次。
- 導航試走三題（kernel `ls` 的 health、agent 的 `waits`、aos-exec 退出碼 125）：都是總導航→資料夾 README→小檔，兩下到。
- 連結抽 15 條外部（多數是舊行號連結，逐條對當時版本核過主題）＋3 條錨點連結，全對；全面掃描 743 條、壞 0。
- 建議四條，處理如下：
  1. 原文「檔尾〈沿革〉」拆後已不在檔尾——不改原文（逐字規則），在九份 README 的「各節」表前補一句方位詞說明。
  2. 「見下」跨了檔（例：kernel/cli.md 說 boot 見下，其實在 boot.md）——同上，靠那句說明＋各節表。
  3. proto5 README 的「kernel.md §1.1、§6」一條連結只到得了 §1.1——拆成兩條，各指 home.md、cli.md。
  4. `cli-ops.md`、`no-overlap.md` 要看摘要才懂——摘要已夠，不改。
