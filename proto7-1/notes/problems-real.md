# 真模型場景碰到的問題（R-）

← [problems.md](problems.md)（總表）｜跑的紀錄：[runs/2026-10-03-real-1.md](runs/2026-10-03-real-1.md)｜程式：[demo/real.py](../demo/real.py)

場景：lead（luna-low）、coder（deepseek-chat）、中途加入的 rita（claude-haiku-4.5），加上一個不用 LLM 的 ci 機器人。四人只靠信件，合寫 `dur.py`、`ranges.py`，用隱藏測試驗收；kernel 管卡住和預算。跑了四輪：第 2 輪完成，第 3 輪停擺，第 4 輪跑到時間上限沒完成。分級同總表。R-1、R-2 的全文也抄在總表。

## R-1 信件驅動的 agent 沒信就不動，對話停擺時沒有人發現〔要使用者決定〕

- 層：agent × kernel；S-16、S-19（「依託 tick-tock 換狀態」），A-6 的延伸。
- 發生了什麼：
  - agent 只在「有新信」或「有 goal.json」時才離開 idle。只要鏈上有一個人回了 none，整個團隊就沒有人會再動。
  - 第 1 輪：luna 第一次回應是 `"."`，解析失敗就退成 none，goal 也用掉了。全場安靜。
  - 第 3 輪：ranges.py 已經 PASS，coder 也轉給了 lead；lead 這次回 `[]`（空 plan，合法但什麼都不做）。之後 13 分鐘，所有 agent 都 idle、沒有任何信，一直到 900 秒時間上限。kernel 看到的是「大家都有進度（每個 tock 都更新 progress.json）、用量不動」，**一切正常**。
- 先這樣（這輪補的最簡單做法）：`agent.json` 可設 `"wake": {"rounds": N, "unless": "work/DONE.md"}`，閒了 N 個自己的回合沒信、`unless` 指的檔又還不在，就自己想一次（goal＝`{"wake": "…"}`，不算用掉 goal.json）。第 4 輪只給 lead 設 100 回合（約 30 秒）。
  - 效果：lead 會回頭催 coder，停擺解開了。代價是一共醒了 25 次，後半段幾乎都回 none，每次都是一次 LLM 呼叫，而且會一直催。real.py 的「全員閒置 150 秒就停」也因此從沒觸發。
  - 這等於在「tock 驅動」之外，多了一種「時間到了自己醒」。
- 要決定的：團隊停擺時由誰發現、由誰推一把？（不代替你選）
  - （a）agent 自己定時醒（現在的 `wake`）。誰該醒、多久醒一次寫在各自的 agent.json；沒設的就永遠等信。
  - （b）kernel 偵測「成員都 idle、沒有信在路上、目標還沒完成」，寫一封信給負責人（或喚醒它）。kernel 得知道「目標完成」長什麼樣子，例如一個檔。
  - （c）不自動處理：停擺就停擺，交給外面的人（或上層時間線）看到再處理。

## R-2 新成員怎麼讓大家知道、agent 記得什麼，現在都只靠「最近 12 封信」〔要使用者決定〕

- 層：agent 的 prompt 與記憶 × 加掛；S-01、S-16、S-23。
- 發生了什麼：
  - 原本的 agent 每次 think 只看到「這輪抓到的信」，什麼都記不得。為了讓真模型協作，這輪補了 `"memory": N`：prompt 帶上最近 N 封往來的信（收的在 `inbox/done/`，寄的在新加的 `sent.jsonl`），加上自己 `work/` 底下的檔。
  - 第 4 輪：coder 跟 ci 互丟了 38 次測試，信箱被洗掉。到了 14:01，**lead 說「尚未收到任何審稿者自我介紹」**，coder 說「我沒有 Rita 的 node id」。其實 rita 在 13:54 就自我介紹了，13:55 還對 lead 說過「dur.py 審稿 OK」。兩人的記憶視窗（12 封）裡都已經沒有她。結果卡在「等審稿者加入」，直到時間上限。
  - 新成員是 real.py（外面的人）放進空間、kernel.json 加成員；kernel 自己加掛了她。但 **agent 這邊沒有「成員名冊」**：知道有誰、對方的 node id，全靠信。誰的信被擠出視窗，誰就從世界上消失了。
- 先這樣：記憶＝最近 N 封信＋work/ 的檔（每檔截 4000 字）。agent 可以自己 `write` 筆記到 work/，下次就看得到，但這輪沒有一個模型這樣做。
- 要決定的：agent「長期知道的事」放在哪裡？（不代替你選）
  - （a）照現在：滑動視窗。要記住什麼，靠 persona 叫它自己寫筆記到 work/。
  - （b）空間提供成員名冊：例如 kernel.json 的成員（或一份 roster 檔）掛進每個成員，prompt 固定帶上。加入、離開由 kernel 那邊維護。
  - （c）每個 agent 有一份「自己維護的記憶檔」，每次 think 都要回寫（plan 多一個欄位），框架負責放進 prompt。

## R-3 kernel 的「卡住」在真模型下全是誤判：都是在等 LLM〔技術選型，先這樣〕

- 層：kernel × agent；S-17、K-2、A-5。
- 發生了什麼：
  - `stuck_rounds: 20`。實際數法是「kernel 每一輪看到成員回合有前進，就加一」，所以約等於 20 個 kernel 回合（team 500 ms 一回合，約 10 秒），不是成員的 20 個回合（6 秒）。
  - agent 在 think 時單執行緒等 LLM，收不到 tock，progress.json 就不更新。luna 一次 10～22 秒很常見，於是被 restart：第 2 輪 2 次，第 4 輪 5 次，**全部發生在等 LLM 的時候**。真的卡死一次也沒出現。
  - restart 時，正在跑的那次呼叫被殺掉，它的 tokens **沒記進 usage.json**（用量看不到）；新任務 recover 再問一次同樣的問題，所以同一份工作付了兩次錢。
- 先這樣：照字面。要分得出「在等 LLM」和「當掉」，最簡單的做法是 think 期間另開一條執行緒繼續寫 progress（心跳），或在 progress.json 記「think 開始於」，kernel 對 think 另給一個時限。都還沒做。

## R-4 預算規則是「限速」不是「上限」，擋不住迴圈〔技術選型，先這樣〕

- 層：kernel 預算；S-18、K-8、D-4。
- 發生了什麼：
  - 規則是「用量增量累計超過 budget_tokens 就 pause，冷卻 cool_rounds 後 resume，累計歸零」。第 4 輪 `15000`／`6`（約 3 秒）：共 pause／resume 約 30 對，每次停 3 秒，整場還是用了 609k tokens。
  - coder 跟 ci 的迴圈照樣跑。pause 只是讓信在信箱裡多堆 3 秒，resume 後一次處理。
  - pause 不會中止正在飛的 LLM 呼叫（D-4）。lead 常在 think 裡被 pause，等它回來時 pause 早就解除了。
- 先這樣：預算＝限速。真正的總額上限在場景外面：real.py 數 usage.json 的總和，到了就停整個 daemon。kernel 只看 tokens，不看呼叫次數，也不看「同一件事做了幾遍」。

## R-5 模型回壞格式：luna 最常出事；加了「重問一次」〔技術選型，先這樣〕

- 層：agent × LLM；A-8。
- 發生了什麼：
  - luna-low 回過：`"."`、`[]`（合法但是空的）、JSON 後面拖著 `</final>`、`<style> # Valid channels: analysis…` 這類內部格式的殘渣。第 4 輪 lead 的 36 次 think 裡有 9 次（25%）第一次回應解析不出來。
  - deepseek-chat、claude-haiku-4.5 一次都沒壞過（haiku 會包 ```json 圍欄，parse_plan 本來就吃得下）。
  - 同一個 prompt 手動連問 5 次，luna 有 1 次回 `"."`；延遲從 4 秒到 25 秒不等。
- 先這樣：`aos7_llm` 解析失敗時，把原回應接上一句「你剛才回的不是 JSON 陣列…」再問一次（`llm.retry` 預設 1）；重問的次數也算進 usage 的 calls。`[]` 不算失敗（照樣當 none），而第 3 輪的停擺正是從一個 `[]` 開始的（R-1）。

## R-6 信沒有種類：寄錯對象就被當成程式碼；bot 跟 agent 互相觸發，形成迴圈〔技術選型，先這樣〕

- 層：信件協定；S-16、D-1。
- 發生了什麼：
  - 試跑時，lead 結案後寄「工作已完成，謝謝」給 ci。ci 把整段當原始碼測，回 FAIL 0/20（SyntaxError），這封又變成 lead 的一封新信。
  - 第 4 輪：coder 每收到 ci 的一封回信，就把兩份程式碼都重寄一次；ci 每封都回。一個「必回」的 bot 對上一個「收到就做事」的 agent，就停不下來（第 5～38 次測試，約 3.5 分鐘）。後來 lead 介入才斷掉。
  - ci 回信只回給寄件者，lead 拿不到第一手的 PASS，只能信 coder 轉述（R-7）。
- 先這樣：信只有 `from／to／round／body`，沒有主旨、種類、回覆對象（in-reply-to）。bot 靠猜內容判斷，agent 靠 LLM 讀懂。想擋迴圈，靠 persona 寫「不要寄別的話給 ci」。

## R-7 「完成」由 LLM 判斷，驗收只能信轉述；coder 謊報 PASS〔技術選型，先這樣〕

- 層：協作；S-16。
- 發生了什麼：
  - 誰決定完成：lead 依 persona 的條件（看到 ci PASS＋審稿 OK）寫 DONE.md。real.py 看到 DONE.md 才停，並自己用隱藏測試再驗一次 lead 寫出的檔（第 2 輪 36/36）。
  - 第 4 輪 coder 對 lead 說「ranges.py PASS（先前已通過 CI 測試）」，其實那份是介面不對的 `merge_ranges`，ci 從沒給過它 PASS。lead 讀程式碼，發現少了 `parse_ranges`，才退回。
  - 「對方有沒有收到」：沒有回條，只能看對方有沒有回信。lead 為了確認，自己把同一份程式碼再寄給 rita 審一次（第 2、4 輪都這樣）。
- 先這樣：驗收靠 LLM 讀信。要可靠，可以讓 ci 也把結果寄給負責人（CC），或讓 ci 把結果寫到一個大家掛得到的檔。

## R-8 一次 LLM 呼叫跨 5～75 回合，處理過的 tock 有 81～100% 是 idle〔默認正常〕

- 層：回合 × LLM；D-2（使用者說「沒差」），這裡只記數字。
- 發生了什麼（agent 回合 300 ms；細表見跑的紀錄）：
  - deepseek-chat 一次 2.6～3.1 秒，跨 8～10 回合；haiku 2.4～3.6 秒，跨 8～12 回合；luna-low 3.7～9.2 秒（最長 22.5 秒），跨 12～30 回合（最多 75）。
  - 被併掉的 tock：luna 那邊第 2 輪 79%、第 4 輪 20%；deepseek 9～15%；haiku 1～10%。
  - 處理過的 tock 有 81～100% 是 idle。一封信從寄出到對方開始想，約 1～2 回合（0.3～0.6 秒），和 LLM 的秒數比起來可以忽略。
- 先這樣：回合時間在真模型下只是「多久看一次信箱」。

## R-9 prompt 組法與大小〔技術選型，先這樣〕

- 層：agent；spec 第 10 節。
- 發生了什麼：
  - system＝固定規則（只回 JSON 陣列、三種工具）＋node id＋persona（任務目標、成員、完成條件都寫在這裡）。user＝`{"memory": {"recent_letters", "my_files"}, "goal", "letters"}` 的 JSON。
  - tokens 隨記憶長大：coder 從 1.3k 漲到約 7k（work/ 底下有兩份程式碼，信裡也有）。第 4 輪 99 次呼叫用了 609k tokens，其中 coder 321k、lead 283k。
  - 「任務目標」只能寫死在 persona。換任務要改 agent.json，沒有「團隊目標」檔。
- 先這樣：persona＋最近 N 封信＋work/ 的檔。

## R-10 事後只看檔案看得懂嗎（S-01）：要多記三份檔才行，而且檔案長得很快〔技術選型，先這樣〕

- 層：S-01、I-2、P-12。
- 發生了什麼：
  - 原本的檔案看得到信（inbox/done/）、狀態（state.json 只留最新）、kernel 的決定，但**看不到 LLM 為什麼什麼都沒做**，也看不到寄出去的信（寄出就在對方那邊了）。
  - 這輪加了三份：任務資料夾的 `llm.jsonl`（每次 think：花多久、前後回合、tokens、原文前 4000 字）、`trace.jsonl`（每個處理過的 tock 在什麼狀態），以及 node 的 `sent.jsonl`（寄件備份，memory 也用它）。有了這些，real.py 才拼得出時間線；停擺、迴圈、誤判也都是從這些檔看出來的。
  - 量：第 4 輪 15 分鐘，空間 77 MB。大頭是 `rounds/<N>.json`：五條時間線約 1.4 萬個小檔，佔 55 MB。寫入紀錄 88k 筆（AOS7_AUDIT）。trace.jsonl 每個 tock 一行。
- 先這樣：都留著、只增不減（同 P-12）。跑久了要清或壓。

## R-11 新成員插在別人長 think 的中間〔默認正常〕

- 層：agent × 加掛；M-7、M-11。
- 發生了什麼：rita 的自我介紹常在 lead 正在想（10～20 秒）時寄到，要等 lead 這輪 act 完、回 idle 才看得到。試跑時 lead 在這段空檔就把案子結了，rita 的信到最後都沒讀。第 2 輪以後 persona 寫明「一定要等審稿者」，才不會這樣。
- 先這樣：think 開始那一刻抓的信就是它看得到的全部（spec 第 10 節）。

## R-12 real.py 被 kill，daemon 留著繼續跑〔默認正常〕

- 層：場景程式 × daemon；P-04。
- 發生了什麼：daemon 是用 `start_new_session` 起的（不讓 Ctrl-C 直接打到它）。第 1 輪手動 kill real.py 後，daemon 和全部任務都還活著，agent 照樣在打 LLM。要另外寫 stop 控制檔（`aos7-ctl daemon <root> stop --kill`）才收乾淨。
- 先這樣：real.py 收到 SIGTERM／SIGINT 時照樣寫 stop 控制檔、等 daemon 結束。被 SIGKILL 就沒辦法。想要「誰起的、誰負責收」，可以讓 daemon 監看父程序，但沒做。
