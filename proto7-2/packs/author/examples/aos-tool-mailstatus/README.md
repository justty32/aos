# aos-tool-mailstatus

[需求](request.json)｜[參考候選](valid.json)｜[獨立核對](check_answer.py)｜[真資料重造](make_fixture.py)

四題使用相同真郵局資料的複本，四個人、七個 REQUEST、自動終局回信、進度回信與兩封團隊廣播。保留真信頭、鎖與讀信紀錄；手加一封投遞中斷的半封回信。每檔 ≤4 KiB，沒有空目錄與 .pyc。

checker 的固定答案只對應提交的 fixture，不呼叫重造腳本。三個隔離變體搬移或加入應忽略的資料，語意不變；錯誤標籤提供學徒可記下的線索。另驗唯讀複本、不存在、檔案與空郵局。snapshot 的規則沿用 audit。

重造：在本題目錄跑 `python3 -B make_fixture.py`；已有 fixture 時拒絕覆蓋，重造後須核對並更新固定答案，並同步四題複本。

[測試](../../tests/test_author_aos_mail.py) 驗需求、候選自己的兩項測試、固定答案、五種突變與 rules 離線三關。
