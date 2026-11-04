# MN2 冒煙第二輪：真 AI（luna）走修過的學徒選單

依序執行 `run_v2.sh 1`、`2`、`3`，三次均是新 node；沒有重跑 rc=3。每個 node 的 `state.json` calls 都低於 40。總 token 98,198，低於 500,000 上限；第 2 次後累積 69,427，低於 350,000，因此照計畫跑了第 3 次。

| node | rc | 選單呼叫 | 重問 | gates 輪數與每輪結果 | 選單 token | 審查 token | 總 token | 秒 |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| v2-luna-1 | 0 | 13 | 0 | 2 輪：第 1 輪 rc=1（第 2 關答案不合）；第 2 輪 rc=0 | 35,636 | 5,122 | 40,758 | 64 |
| v2-luna-2 | 1 | 11 | 0 | 0 輪（在 report 層選出口，未進 gates） | 28,669 | 0 | 28,669 | 25 |
| v2-luna-3 | 1 | 11 | 0 | 0 輪（在 report 層選出口，未進 gates） | 28,771 | 0 | 28,771 | 41 |
| **合計** |  | **35** | **0** | **2 輪** | **93,076** | **5,122** | **98,198** | **130** |

審查 token 以總帳 used 減 `state.json` calls 的 used 加總。prompt_chars（kind=pick 或 bad）平均／最大：v2-luna-1 **1,630.5／3,991**、v2-luna-2 **1,375.7／1,629**、v2-luna-3 **1,375.3／1,664**。

## 未通過與選檔

- **v2-luna-1：**status：`選單 aos-tool：做完，寫了 out/packs/mailcount/README.md、out/packs/mailcount/bin/aos7-mailcount、out/packs/mailcount/aos7_mailcount.py、out/packs/mailcount/tests/test_mailcount.py、out/row、out/report`。第一輪 gates 的 `vars.issues` 為「第2關：answer check_answer.py：主樣本（真郵局）：答案不合；已辦結：把每個人 inbox/ 頂層的信全搬進同一人的 inbox/done/（辦結的信歸檔在 <人>/inbox/done/，仍是那個人的信）：答案不合；暫存：再放一份 <人>/inbox/.tmp/ 寫到一半的信和一個 .draft.md（. 開頭的檔與資料夾都不是信）：答案不合；團隊：再加一個 R/teams/ops/inbox/ 團隊信箱和幾封廣播（teams/ 是團隊資料夾，不是人；團隊信不算）：答案不合；增減：加減幾封信、加一個空信箱（答案會變，不能背主樣本）：答案不合；readonly：答案不合；主樣本：得到 …；應為 …」。AI 在 fix 選主程式 `packs/mailcount/aos7_mailcount.py`；第二輪 gates rc=0，三關全過。候選已複製到 `pass-v2-luna-1.txt`。
- **v2-luna-2：**status：`選單 aos-tool：停下——AI 選了出口：缺少必要資訊，請人補充。請換 --run 重走`。在 `report` 層選「缺少必要資訊，請人補充」出口，rc=1，沒有 gates 輪次；最終 `vars.issues` 不存在，值為 null。未交出 report，也未選修正檔。
- **v2-luna-3：**status：`選單 aos-tool：停下——AI 選了出口：缺少必要資訊，請人補充。請換 --run 重走`。同樣在 `report` 層選「缺少必要資訊，請人補充」出口，rc=1，沒有 gates 輪次；最終 `vars.issues` 不存在，值為 null。未交出 report，也未選修正檔。

死在格式的次數：**0**。三個 node 的 `log.jsonl` 都沒有 `kind=bad`；沒有第一關格式擋下，也沒有回法連續三次不合。K=2、3 的出口選擇不是格式重問。

## Python 檔尾檢查

檢查三個 node `menu/aos-tool/out/` 底下全部 `.py` 檔的最後兩行，並搜尋「限制」「格：」與 ``` 殘字：**未發現殘字**。檢查檔案為三個 node 各自的 `aos7_mailcount.py` 與 `tests/test_mailcount.py`。
