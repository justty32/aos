完成 `proto4-5` 第一版，只新增該目錄內容。
正式檔案行數：README 137、llm-cpu 11、llm_cpu.py 62、home 209、tick 239、worker 151。
測試檔案行數：fake server 59、util 89、home 98、schedule 94、worker 69。
測試共 26 條；最後一行原文：`OK`
自行決定：重複 id 拒收；`params` 不能覆蓋固定的 model／stream。
撞到的坑：測試 setup 曾覆蓋 init 範例，已改成獨立家驗證。
沒做到的：定案範圍皆完成；README 明列的延後功能未做。
key grep 只命中既有任務書中的 grep 指令文字；所有程式碼 0 命中，沒有印 key。
repo 其他既有修改均未觸碰；沒有 commit、沒有 push。