> 封存 2026-11-03：沒有取代者（一問一答改用 `aos-say 話 && aos-listen`）。使用者 11-03 晚「瘦身...這些你提到的，其實都是我有一個模糊的概念，然後就交給AI生成了，整個都需要重新手修一遍，所以說瘦身嗎...也不盡然，或者說可以先封存，等之後我們進展到那塊的時候可以拉出來看看。」

# aos-chat（原 proto8/extras/human/bin/aos-chat）

底下照原本相對 proto8/ 的路徑擺：`extras/human/bin/aos-chat`；`tests/test_human_chat.py` 是從 proto8/tests/test_human.py 切出來的 ChatTest。它 import 的 aos_human.py、aos_ws.py 留在原處（aos-say／aos-listen 照用）。只作歷史，不測試、不維護；要拉回去就搬回 extras/human/bin/、案例併回原檔。設計：proto8/thinking/2026-10/24/say-listen.md。
