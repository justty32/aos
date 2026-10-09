# aos-tool-mailcount

[需求](request.json)｜[參考候選](valid.json)｜[獨立核對](check_answer.py)｜[真資料重造](make_fixture.py)

四題使用相同真郵局資料的複本，四個人、七個 REQUEST、自動終局回信、進度回信與兩封團隊廣播。保留真信頭、鎖與讀信紀錄；手加一封投遞中斷的半封回信。每檔 ≤4 KiB，沒有空目錄與 .pyc。

checker 的固定答案 MAIN 只對應提交的 fixture，不呼叫重造腳本。先用 reference(fixture) 自檢，與 MAIN 不同就回「檢查器自檢失敗」；reference 只在核對時執行。前三個隔離變體搬移或加入應忽略的資料，語意不變；錯誤標籤提供學徒可記下的線索。第四個變體「增減：加減幾封信、加一個空信箱（答案會變，不能背主樣本）」在 alice/inbox/ 加 NEEDS-USER 回信、bob/inbox/ 加 from erin 的新 REQUEST、carol/inbox/done/ 加 FAILED 回信，兩封回信各指向原本不同的 open id；再刪 dave/inbox/ 頂層一封既有信，加空的 frank/inbox/。期望答案由 reference 算，必須與 MAIN 不同；失敗只報得到的前 300 字，不印期望答案。另驗唯讀複本、不存在、檔案與空郵局。snapshot 的規則沿用 audit。

重造：在本題目錄跑 `python3 -B make_fixture.py`；已有 fixture 時拒絕覆蓋，重造後須核對並更新固定答案，並同步四題複本。

[測試](../../tests/test_author_aos_mail.py) 驗需求、候選自己的兩項測試、reference 自檢與增減答案、五種突變與 rules 離線三關；只印 MAIN 的固定答案候選必須擋在「增減」，且失敗訊息不能洩漏期望 JSON。
