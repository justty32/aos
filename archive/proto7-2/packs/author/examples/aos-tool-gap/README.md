# aos-tool-gap

[需求](request.json)｜[參考候選](valid.json)｜[獨立核對](check_answer.py)｜[真資料重造腳本](make_fixture.py)

`make_fixture.py` 先用 `aos7-ctl daemon register`／`add` 啟動真 events 取樣器（`--src absent --segment-bytes 900 --keep 4`），初建後停止 daemon，再用 `aos7-events pub` 寫 obs／must 各 12 筆，`ack 5`。小段選項屬取樣器，pub 本身不接受。

共產生 24 筆真事件；手加 3 處：從 obs 第一封存段刪 seq 2、active 尾加壞 JSON 與半截各一行。fixture 留 23 筆真紀錄＋2 行壞資料，共 8 檔，保留真 state 與鎖。

人工核對：obs 的 seq 是 1、3～12，count 11、缺口 [2,2]；must 是 1～12，count 12，ack 5 後 unacked 7；兩本 next_seq 都是 13。壞行是 obs active 第 3／4 行。

需求明定用 `b'\n'` 分行，state 只取必要欄。checker 另測行中 CR、兩段缺口、重複 seq、bool／null／浮點／缺欄、壞或缺 state、空紀錄。

每檔 ≤4 KiB、fixture ≤60 檔、沒有空目錄，手加壞資料不超過真資料的 1/3。重造腳本只為重現流程；每次時間與 id 不同，checker 不跑腳本，其答案固定對應本次提交的 fixture。執行：`python3 -B make_fixture.py`（會替換本題 fixture，重造後須另行核對與更新固定答案）。

checker 用 lstat 拍輸入及父目錄的型別、大小、權限、mtime_ns、內容與連結目標，不跟隨 symlink，排除 __pycache__；另在去掉所有寫權限的暫存複本執行，再恢復權限清理。單靠 snapshot 不保證偵測所有建立後刪除，因此突變測試也驗建立後刪除的鎖檔在唯讀複本失敗。

[三連題測試](../../tests/test_author_aos_3x.py) 物化 valid、跑候選自己的測試、固定答案與 rules 離線三關，並拒絕多行、bool、反排序、建鎖與短命鎖候選；不發布、不打真 AI。
