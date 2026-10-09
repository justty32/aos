# aos-tool-audit

[需求](request.json)｜[參考候選](valid.json)｜[獨立核對](check_answer.py)｜[真資料重造腳本](make_fixture.py)

`make_fixture.py` 用 `aos7-mail send` 寄 6 個 REQUEST；`read` 建真序號／seen，再用 `done` 辦結 2 個並自動回 2 封 DONE，另用 `send --re` 回 2 封 PROGRESS，其他不回。原始時間、id、reply-to、`inbox/done`、`.handled`、`.seen`、`.numbers.json` 與鎖檔均保留，真模組撞名產生的 `_1` 檔名也保留。

10 封真信＋2 封手加（無 frontmatter、複製既有 id），共 26 檔。人工核對：6 REQUEST 中 2 已結、4 未結；alice inbox=2 DONE＋1 REQUEST，bob inbox=2 REQUEST／done=2，carol inbox=2 PROGRESS＋1 REQUEST。

需求明定 done 在 inbox/done、inbox 不遞迴；to／age 取 frontmatter to／at；frontmatter 恰以 --- 分隔、第一個 ': ' 切分、值不 strip、重複 key 取最後、re 空值無目標；boxes 只收有 inbox 的名字。checker 補重複 key、re: 空值、底線檔名、to 與資料夾名不同、本地 at、負 age 向下取整、缺 to／at、壞日期與 PROGRESS 不結案。

每檔 ≤4 KiB、fixture ≤60 檔、沒有空目錄，手加壞資料不超過真資料的 1/3。重造腳本只為重現流程；每次時間與 id 不同，checker 不跑腳本，其答案固定對應本次提交的 fixture。執行：`python3 -B make_fixture.py`（會替換本題 fixture，重造後須另行核對與更新固定答案）。

checker 用 lstat 拍輸入及父目錄的型別、大小、權限、mtime_ns、內容與連結目標，不跟隨 symlink，排除 __pycache__；另在去掉所有寫權限的暫存複本執行，再恢復權限清理。單靠 snapshot 不保證偵測所有建立後刪除，因此突變測試也驗建立後刪除的鎖檔在唯讀複本失敗。

[三連題測試](../../tests/test_author_aos_3x.py) 物化 valid、跑候選自己的測試、固定答案與 rules 離線三關，並拒絕多行、bool、反排序、建鎖與短命鎖候選；不發布、不打真 AI。
