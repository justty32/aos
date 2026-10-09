# aos-tool-runs

[需求](request.json)｜[參考候選](valid.json)｜[獨立核對](check_answer.py)｜[真資料重造腳本](make_fixture.py)

`make_fixture.py` 用 `aos7-routines add` 建 9 個 routine、3 個 schedule；中途 `ls --run` 真跑 node 內 `ok.sh`／`fail.sh`，分別得到 code 0／7，時間與 code 均由模組寫入。回合型 routine 在手動 run 中不跑。所有真時間原樣保留；本 checkout 寫出含 +08:00 的時間，checker 另測無時區時間。

12 列真資料＋2 列手加（every 壞、重名），共 6 檔，包含真鎖檔與執行程式。人工核對：9 個有效 routine（4 never、1 failed；第一個 now 下 4 ok，第二個 now 下 3 overdue／1 ok）、3 個 schedule（1 due／2 pending）；壞列為 row 9 bad_row、row 10 dup_name。

需求只留 bad_table／bad_row／dup_name；第一列無效仍登記 name，同名第二列優先判 dup_name。資料時間能由 fromisoformat 解析即可，無時區照 --now 解讀。checker 補缺欄首列後重名、every 壞首列後重名、本地時間在兩種 now 時區、fraction 邊界、running、負 code、claimed 與各種壞表／壞列。

每檔 ≤4 KiB、fixture ≤60 檔、沒有空目錄，手加壞資料不超過真資料的 1/3。重造腳本只為重現流程；每次時間與 id 不同，checker 不跑腳本，其答案固定對應本次提交的 fixture。執行：`python3 -B make_fixture.py`（會替換本題 fixture，重造後須另行核對與更新固定答案）。

checker 用 lstat 拍輸入及父目錄的型別、大小、權限、mtime_ns、內容與連結目標，不跟隨 symlink，排除 __pycache__；另在去掉所有寫權限的暫存複本執行，再恢復權限清理。單靠 snapshot 不保證偵測所有建立後刪除，因此突變測試也驗建立後刪除的鎖檔在唯讀複本失敗。

[三連題測試](../../tests/test_author_aos_3x.py) 物化 valid、跑候選自己的測試、固定答案與 rules 離線三關，並拒絕多行、bool、反排序、建鎖與短命鎖候選；不發布、不打真 AI。

**S3b 修題（2026-10-09）**：S3 的 6 次全卡在審查拿需求沒寫的極端邊角退件（4301 位數整數、西元 1／9999 年溢位、年份不補四位、落單 surrogate）與單一測試檔超過 8192 bytes；沒有一次是答案檢查器擋下（能到第三關的候選都過了 fixture 核對），所以 checker 不嚴。work 末加一條「範圍外」（last_code 超過 18 位、時間或 next 超出 1000–9999 年、落單 surrogate：不測、怎麼處理都行），為了守住需求 ≤4 KiB，刪掉 work 裡兩處重複句、縮短唯讀那條措辭，規則不變。A／B 兩組拿到同一份需求。
