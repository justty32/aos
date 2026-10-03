# 真模型場景碰到的問題（R-）

← [problems.md](problems.md)（總表）｜跑的紀錄：[runs/2026-10-03-real-1.md](runs/2026-10-03-real-1.md)、[runs/2026-10-03-real-2.md](runs/2026-10-03-real-2.md)｜程式：[demo/real.py](../demo/real.py)

場景：lead（luna-low）、coder（deepseek-chat）、中途加入的 rita（claude-haiku-4.5），加上一個不用 LLM 的 ci 機器人。四人只靠信件，合寫 `dur.py`、`ranges.py`，用隱藏測試驗收；kernel 管卡住和預算。real-1 跑了四輪：第 2 輪完成，第 3 輪停擺，第 4 輪跑到時間上限沒完成。real-2（R-13 起）兩模組跑三次，三次都寫出 DONE.md，其中一次交出去的檔不合格（R-15）。分級同總表。R-1、R-2、R-15 的全文也抄在總表。

## R-1 信件驅動的 agent 沒信就不動，對話停擺時沒有人發現〔要使用者決定，10-03 已答〕

> **〔使用者 10-03〕採 (a)**：維持 agent 自己定時醒（wake）。

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
- **real-2**：wake 只醒了 2／3／1 次（real-1 第 4 輪 25 次）。第 2 次 rita 一直沒對 dur.py 表態，是 lead 被 wake 叫醒寄信去追才結案的。

## R-2 新成員怎麼讓大家知道、agent 記得什麼，現在都只靠「最近 12 封信」〔要使用者決定，10-03 已答〕

> **〔使用者 10-03〕採 (b)**：空間提供成員名冊，掛給每個 agent，固定放進 prompt。

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
- **怎麼做的**：kernel 依 kernel.json 的 members（加可選的 `roles`）寫每個成員的 `.aos/roster.json`，agent 每次 think 帶上（user JSON 的 `roster`）。詳見總表 R-2、M-15。
- **real-2**：kernel.json 加了 `roles`，三次都沒有人忘了 rita（real-1 第 4 輪的「沒有 Rita 的 node id」沒再出現）。同時補了 R-13（每個往來對象至少留一封），兩者分不出誰的功勞。lead 照 persona 寫的 `work/status.md` 三次都一路正確。

## R-3 kernel 的「卡住」在真模型下全是誤判：都是在等 LLM〔技術選型，先這樣〕

- 層：kernel × agent；S-17、K-2、A-5。
- 發生了什麼：
  - `stuck_rounds: 20`。實際數法是「kernel 每一輪看到成員回合有前進，就加一」，所以約等於 20 個 kernel 回合（team 500 ms 一回合，約 10 秒），不是成員的 20 個回合（6 秒）。
  - agent 在 think 時單執行緒等 LLM，收不到 tock，progress.json 就不更新。luna 一次 10～22 秒很常見，於是被 restart：第 2 輪 2 次，第 4 輪 5 次，**全部發生在等 LLM 的時候**。真的卡死一次也沒出現。
  - restart 時，正在跑的那次呼叫被殺掉，它的 tokens **沒記進 usage.json**（用量看不到）；新任務 recover 再問一次同樣的問題，所以同一份工作付了兩次錢。
- 先這樣：照字面。要分得出「在等 LLM」和「當掉」，最簡單的做法是 think 期間另開一條執行緒繼續寫 progress（心跳），或在 progress.json 記「think 開始於」，kernel 對 think 另給一個時限。
- **已修（10-03）**：agent 進 think、呼叫 LLM 之前先寫 progress.json＝`{"round","state":"think","steps","llm_since": 時間}`。kernel 看到 `llm_since` 就不用 `stuck_rounds`，改用 kernel.json 的 `llm_stuck_rounds`（沒寫＝不管在等 LLM 的）；理由寫「在等 LLM，從 … 起」。想完後的 progress 沒有 `llm_since`，計數重來。restart 時那次呼叫的用量沒記到、會重問，這兩點沒改（真的卡在 LLM 時還是會發生）。測試 `test_llm_wait_is_not_stuck`、`test_progress_says_waiting_llm`。
- **real-2**：三次 restart 都是 0（real-1 2～5 次全誤判）。luna 一次 think 最長 32.7 s、跨 108 回合，kernel 沒動它。

## R-4 預算規則是「限速」不是「上限」，擋不住迴圈〔技術選型，先這樣〕

- 層：kernel 預算；S-18、K-8、D-4。
- 發生了什麼：
  - 規則是「用量增量累計超過 budget_tokens 就 pause，冷卻 cool_rounds 後 resume，累計歸零」。第 4 輪 `15000`／`6`（約 3 秒）：共 pause／resume 約 30 對，每次停 3 秒，整場還是用了 609k tokens。
  - coder 跟 ci 的迴圈照樣跑。pause 只是讓信在信箱裡多堆 3 秒，resume 後一次處理。
  - pause 不會中止正在飛的 LLM 呼叫（D-4）。lead 常在 think 裡被 pause，等它回來時 pause 早就解除了。
- 先這樣：預算＝限速。真正的總額上限在場景外面：real.py 數 usage.json 的總和，到了就停整個 daemon。kernel 只看 tokens，不看呼叫次數，也不看「同一件事做了幾遍」。
- **已補總額（10-03）**：kernel.json 可設 `cap_tokens`。成員 node 的用量總和（含已結束的任務、不扣基準）超過它 → pause，理由寫「不會自動恢復，要人改 kernel.json」，冷卻不 resume；人調高或拿掉 `cap_tokens` 後下一輪 resume。上限是**每個成員各算**，不是全隊加總。被移出 members 的成員若是被總額 pause 的，就一直停著（限速的 pause 照樣到期 resume，astra-2 二-7）。pause 仍不中止在飛的呼叫（D-4）。測試 `test_cap_pause_waits_for_config_change`。

## R-5 模型回壞格式：luna 最常出事；加了「重問一次」〔技術選型，先這樣〕

- 層：agent × LLM；A-8。
- 發生了什麼：
  - luna-low 回過：`"."`、`[]`（合法但是空的）、JSON 後面拖著 `</final>`、`<style> # Valid channels: analysis…` 這類內部格式的殘渣。第 4 輪 lead 的 36 次 think 裡有 9 次（25%）第一次回應解析不出來。
  - deepseek-chat、claude-haiku-4.5 一次都沒壞過（haiku 會包 ```json 圍欄，parse_plan 本來就吃得下）。
  - 同一個 prompt 手動連問 5 次，luna 有 1 次回 `"."`；延遲從 4 秒到 25 秒不等。
- 先這樣：`aos7_llm` 解析失敗時，把原回應接上一句「你剛才回的不是 JSON 陣列…」再問一次（`llm.retry` 預設 1）；重問的次數也算進 usage 的 calls。`[]` 不算失敗（照樣當 none），而第 3 輪的停擺正是從一個 `[]` 開始的（R-1）。
- **real-2**：luna 不論當 lead 還是 rita，要重問的比例都高：5/10、4/10、3/8。新出現的壞法：一段亂碼（`老时时彩`）、英文的自言自語（`We need actions only JSON…`）、空字串（重問後也空，退成 none，靠 wake 接上）。deepseek、haiku 仍然一次都沒壞。

## R-6 信沒有種類：寄錯對象就被當成程式碼；bot 跟 agent 互相觸發，形成迴圈〔技術選型，先這樣〕

- 層：信件協定；S-16、D-1。
- 發生了什麼：
  - 試跑時，lead 結案後寄「工作已完成，謝謝」給 ci。ci 把整段當原始碼測，回 FAIL 0/20（SyntaxError），這封又變成 lead 的一封新信。
  - 第 4 輪：coder 每收到 ci 的一封回信，就把兩份程式碼都重寄一次；ci 每封都回。一個「必回」的 bot 對上一個「收到就做事」的 agent，就停不下來（第 5～38 次測試，約 3.5 分鐘）。後來 lead 介入才斷掉。
  - ci 回信只回給寄件者，lead 拿不到第一手的 PASS，只能信 coder 轉述（R-7）。
- 先這樣：信只有 `from／to／round／body`，沒有主旨、種類、回覆對象（in-reply-to）。bot 靠猜內容判斷，agent 靠 LLM 讀懂。想擋迴圈，靠 persona 寫「不要寄別的話給 ci」。
- **real-2**：信還是沒有種類；改在 bot 這邊擋（R-14）。三次都沒有迴圈。

## R-7 「完成」由 LLM 判斷，驗收只能信轉述；coder 謊報 PASS〔技術選型，先這樣〕

- 層：協作；S-16。
- 發生了什麼：
  - 誰決定完成：lead 依 persona 的條件（看到 ci PASS＋審稿 OK）寫 DONE.md。real.py 看到 DONE.md 才停，並自己用隱藏測試再驗一次 lead 寫出的檔（第 2 輪 36/36）。
  - 第 4 輪 coder 對 lead 說「ranges.py PASS（先前已通過 CI 測試）」，其實那份是介面不對的 `merge_ranges`，ci 從沒給過它 PASS。lead 讀程式碼，發現少了 `parse_ranges`，才退回。
  - 「對方有沒有收到」：沒有回條，只能看對方有沒有回信。lead 為了確認，自己把同一份程式碼再寄給 rita 審一次（第 2、4 輪都這樣）。
- 先這樣：驗收靠 LLM 讀信。要可靠，可以讓 ci 也把結果寄給負責人（CC），或讓 ci 把結果寫到一個大家掛得到的檔。
- **real-2**：ci 的 PASS 直接寄給 lead、附程式碼（R-14），lead 不必信 coder 轉述；三次都沒有謊報。但「交出去的是不是測過的那份」又是另一個問題（R-15）。

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
- **real-2**：每次呼叫平均 4.5k～8.4k tokens；lead 後期一次 10k～11k（信裡、work/ 都是程式碼）。

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

## R-13 記憶視窗被一個往來對象洗掉〔技術選型，先這樣〕

- 層：agent 的 memory；R-2 的延伸。
- 發生了什麼：real-1 第 4 輪，coder 跟 ci 互丟幾十封，「最近 12 封」全是 ci，rita 的信全被擠出去。名冊（R-2 (b)）讓人知道「有 rita 這個人」，但看不到「rita 說過什麼」。
- **已改（real-2 前）**：`tools.memory` 先取最近 N 封，再替視窗外的每個往來對象補它最近一封（依時間排回去）。所以視窗最多是 N＋往來人數。測試 `test_memory_keeps_each_peer`。
- 效果：三次都沒人忘了 rita。但「每人留一封」只留最新的那封：第 2 次 lead 要 dur.py 的程式碼時，ci 留下的是最新的 ranges PASS，dur 的 PASS 信還是不見了（R-15）。

## R-14 ci 機器人：不測不回非程式碼、重複的程式碼；PASS 直接寄負責人〔技術選型，先這樣〕

- 層：信件協定 × bot；R-6、R-7 的最簡單補法（不加信件種類）。
- **已改（real-2 前，`demo/real_scene/team/agents/ci/ci.py`）**：
  - 信裡沒有任何 `def` 的（「謝謝」「已完成」）不測、不回。real-1 試跑「lead 寄已完成給 ci → FAIL 0/20 → 又變成 lead 的一封信」不會再發生。
  - 跟測過的完全相同的程式碼（去掉前後空白比 sha1）不測、不回：結果寄件者已經拿過了。迴圈裡的「同一份重寄」就斷了。
  - 看不出是哪個模組（兩組函式都沒定義）直接 FAIL「看不出是哪個模組」，不再猜成 dur 再 import 失敗（real-1 第 4 輪的 `merge_ranges`）。
  - PASS 時另把結果和通過的完整程式碼寄給 `ci.json` 的 `cc_pass`（lead）。
  - 測試 `test_skip_not_code_and_duplicates_cc_pass`、`test_unknown_module_fails_clearly`。
- 效果：三次都沒有迴圈，ci 只測了 8／6／5 次（real-1 第 4 輪 40 次）。**但「不是程式碼」「重複」兩條規則一次都沒觸發**：擋住迴圈的是 coder persona 的「ci 不回重複的、不要重寄」和「PASS 由 ci 直接寄 lead」。去重是保險。
- 代價：「不回」對 agent 來說跟「還沒回」分不出來（沒有回條，R-7）。persona 寫明了才不會一直等。

## R-15 交付的檔是 LLM 重打的，不是測過的那份〔要使用者決定〕

- 層：agent 的工具 × 協作；spec 第 10 節（工具只有 send／write／none）、S-16。
- 發生了什麼：
  - real-2 第 2 次（lead＝deepseek）：流程全對，dur.py 在 ci 第 2 次就 PASS 36/36、rita 也說 OK。結案時 lead 用 `write` 把「最終程式碼」寫到 `work/dur.py`，但那時 dur 的 PASS 信已經不在它的記憶裡（R-13 只留 ci 最新一封＝ranges 的 PASS）。lead 就照自己一開始交代的需求**重寫了一份**：沒有 `d` 單位、接受 `01h`，隱藏測試 29/36。real.py 照 DONE.md 停，宣告完成。ranges.py 也是重打的（等價、但拿掉了註解）。
  - 原因很直接：agent 要把東西存成檔，唯一的路是 LLM 在 plan 裡把整份內容再打一次（`write` 的 `text`）。信裡的程式碼不能「原樣存下來」；記憶裡看不到原文時，模型會照它以為的樣子補。
  - 第 1 次（luna）剛好打對；第 3 次在 lead 的 persona 加「收到 ci 的 PASS 就把附的程式碼一字不改存到 `work/<模組>.py`，結案時不要重打」，lead 在程式碼還在眼前時就存檔，交付的檔＝ci 第 3、5 次，完全一致。
  - real.py 現在會報「lead 交的檔是 ci 第幾次測的那份／跟任何一版都不同」（`ci_version_of`，測試 `test_ci_version_of_final_file`）。
- 先這樣：靠 persona（看到就存、之後不重打），外加 real.py 事後比對。這只降低機率：模型照樣可能在存檔時改字。
- 要決定的：在只有信件的世界裡，「成果」要不要經過 LLM 轉手？（不代替你選）
  - （a）照現在：agent 只有 send／write／none，內容都由 LLM 打出來；靠 persona 和事後比對把關。最簡單，但交付物和測過的東西可能不一樣，而且沒人知道。
  - （b）agent 多一個不經 LLM 的工具：把某封信（或信裡的一段）原樣存成檔，例如 `{"tool": "save", "letter": "<信檔名>", "path": "work/dur.py"}`；prompt 裡的信要帶檔名。工具集從三個變四個（spec 第 10 節）。
  - （c）成果由驗收者保管：ci（或任何驗收的 node）把通過的版本存在自己那邊，「完成」＝負責人指名「ci 第幾次」；外面的人去驗收者那裡取檔。agent 不必搬運成果，但完成的定義綁在某個 bot 上。

## R-16 審稿者擴大範圍，多出好幾輪修改〔默認正常〕

- 層：協作；S-16。
- 發生了什麼：第 1 次 rita（haiku）每次審都給「建議」（數字上限、註解、拆函式），coder 照 persona「合理的就採用」，改了又過 CI，ranges 多出 2 版、dur 多 1 版；第 2 次 rita（luna）兩次拒絕 OK（超大範圍吃光記憶體、`isdigit()` 接受非 ASCII 數字），多 2 輪。第 3 次沒提建議，最短（105 s）。
- 都收斂了，最多多花 1～2 分鐘；luna 抓到的是真的問題（隱藏測試沒測）。
- 先這樣：審稿標準寫在 persona，誰當審稿者差很多。

## R-17 審稿 OK 寄給 coder，lead 看不到，要自己再送審一次〔默認正常〕

- 層：信件；R-7 的延伸。
- 發生了什麼：rita 照 persona「回給寄件者」，coder 寄來的就回 coder。lead 的完成條件要「看到審稿 OK」，只好自己把同一份再寄給 rita，rita 再對 lead 說一次。第 1、3 次每個模組都是這樣：coder 先送審、rita 回 coder，lead 再送一次（每個模組多 1 次 lead think＋1 次 rita think，約 5～40 秒，看 luna 多慢）。
- 先這樣：信只到收件人。要省這一輪，可以讓 rita 的 persona 寫「審稿 OK 一律也寄 lead」，或做 CC。

## R-18 預算限速 15000 小於一兩次 think，等於每一兩次就 pause 3 秒〔默認正常〕

- 層：kernel 預算；R-4。
- 發生了什麼：lead、coder 後期一次 think 就 7k～11k tokens，`budget_tokens: 15000` 大約兩次就超過，pause 6 回合（3 秒）。三次分別 pause 13／14／5 次，每次只讓信多等 3 秒，沒有擋到什麼，也沒害到什麼。
- 先這樣：限速的數字要大於單次 think，才有「限速」的意思；這個場景沒調。
