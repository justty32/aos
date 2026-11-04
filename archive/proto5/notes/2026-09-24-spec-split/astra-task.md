# 任務書：proto5 spec 拆檔唯讀審查（astra）

你是審查者，**唯讀**：不改、不建、不刪任何檔，不 commit，不連任何模型端點。工作目錄就是這個 git worktree（分支已 commit 好）。
你的最終回覆就是回報全文（中文），會原樣存成 `proto5/notes/2026-09-24-spec-split/astra-report.md`。

## 背景

使用者說「proto5 的 spec，每個檔案都好大，麻煩拆檔重構」。隊長把 `proto5/spec/` 九份單檔規範
（kernel、daemon、cpu、agent、aos-agent、inst-posix、directives、aos-llm、aos-exec）各變成一個資料夾：

- `proto5/spec/<名>/README.md`：原檔開頭（標題、導航行、版本 blockquote、一句話）＋「已拍板的前提」＋「這份沒管的」＋ `## 各節` 表（每檔一行摘要）。
- 其餘小檔依原本的 § 節拆，一個主題一檔，每檔 ≤ 8 KB；子檔的標題降一級（`##`→`#`、`###`→`##`），頂部一行 `← [名](README.md)｜[spec 總導航](../README.md)`。
- kernel §6 命令列太大（12 KB），在節內兩個段落處切成 `cli.md`／`boot.md`／`cli-ops.md`，後兩檔補了標題 `# 6. 命令列（續）：…`（這是唯一新增的標題文字）。
- `proto5/spec/README.md` 是總導航。
- **規則：內容逐字搬，不改寫、不刪句**；只准動標題層級、檔間連結、頂部導航行、README 的「各節」表。
- repo 裡所有指進 `proto5/spec/<舊名>.md` 的 markdown 連結都改到新位置：帶 `#錨點`→錨點所在小檔；連結字帶 `§n`→該節所在檔；帶 `:行號`（舊審查報告）→用 git blame 找當時版本、看那行在哪一節；對不上→資料夾 README。lib 的 docstring 只改了 7 處明寫 `spec/xxx.md` 路徑的（改成 `spec/xxx/`），像「kernel.md §3」這種不帶路徑的節號引用沒動。

原文用 `git show main:proto5/spec/kernel.md` 之類拿（main 還是拆前的版本）。拆的三個 commit 用 `git log --oneline main..HEAD` 看。

## 要你做的

1. **逐字抽查 20 段**：從九份裡挑（每份至少 1 段，kernel、aos-agent 各至少 3 段；要包含：有程式碼區塊的段、有表格的段、kernel 的 boot.md／cli-ops.md 切點附近、有連結被改過的段、README 裡搬進來的「已拍板的前提」）。每段把新檔的文字跟 `git show main:proto5/spec/<名>.md` 的對應段逐行比，除了允許的差異（標題 `#` 數、連結目標、頂部導航行）以外有沒有任何字不同、少句、多句、順序錯。列表：段落位置（新檔:行）／舊檔行號／結論。
2. **整體完整性**：自己想辦法確認九份的所有內容都有落到某個新檔、沒有重複（例如把新檔去掉允許差異後拼回來跟舊檔比）。說你用什麼方法、結果。
3. **導航夠不夠用**：假裝你是第一次來的人，只從 `proto5/README.md` 的規範表或 `proto5/spec/README.md` 出發，找這三件事，記下你點了幾下、有沒有卡住：(a) kernel 的 `ls` 第一行 `health` 有哪幾種；(b) agent 的 `state.json` 裡 `waits` 是什麼；(c) `aos-exec` 退出碼 125 是什麼意思。再看各資料夾 README 的「各節」摘要有沒有寫錯、漏節、摘要跟內容對不上。文中留著的純文字節號引用（例如「見 §4.1」）靠 README 查得到嗎？
4. **連結**：抽查 15 條被改過的外部連結（`git diff main..HEAD -- proto5/notes proto5/README.md proto5/lib/README.md wf` 裡挑，要含帶 `#錨點` 的、帶 `§` 的、原本帶 `:行號` 的各至少 3 條），確認新目標檔存在、錨點存在、指的是對的主題。再全面掃一次：repo 裡還有沒有指向 `proto5/spec/` 底下不存在的檔或錨點的 markdown 連結（`.claude/worktrees/` 不算）。
5. **其他真問題**：檔名好不好懂、有沒有檔 > 8 KB、有沒有小到該合併的、README 裡「在檔尾〈沿革〉」這種原文措辭拆後會不會誤導（只指出，不建議改原文——規則是逐字）。

## 回報格式

1. 結論一句（能不能收）。
2. 逐字抽查表（20 列）。
3. 完整性檢查方法與結果。
4. 導航試走紀錄＋摘要問題。
5. 連結抽查表（15 列）＋全面掃描結果。
6. 真問題清單：**必修**（違反逐字規則、壞連結、內容遺失）／**建議**（導航、命名）分開列，每條附檔:行。沒有就寫沒有。
