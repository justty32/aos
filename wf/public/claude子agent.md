# wf/public/claude子agent — 派 Claude 子 agent（Agent 工具）時的坑

← [wf/public](README.md)｜帶 sol（agent-fsm）見 [sol-crew](sol-crew.md)；派獨立審稿員的問法見 [審查與實測](審查與實測.md)

每條：適用、做法、驗過、出處。11-14 各線收尾稿整理。

## 長任務在前景跑，並要它邊做邊寫進度檔

- **適用**：eca 用 Agent 工具派 Claude 子 agent 做超過幾分鐘的事（修洞、審查、施工）。
- **坑**：背景跑的子 agent 會隨 eca 這一輪結束或 session 重啟被停掉，沒有任何結果留下，或只留半成品。
- **做法**：`run_in_background: false`；任務書叫它每做完一節就追加進一個檔（`notes/progress.md`），被停了下一隻從這裡接；單子切小一點，前景分短段做。
- **驗過**：11-14 四條線各斷兩次、第三次改前景才做完：ok-onboard（修 guard 的洞）、head-front（guard 複審）、ok-board（碼農）、ok-limits（B7，`ws/claude-b7-2/progress.md`）；ok-astra 斷一次、自己補完。
- **出處**：`wf/temp/{ok-onboard,head-front,ok-board,ok-limits,ok-astra}/wrapup-1114/經驗.md`

## 寫最終回答之前，先把背景的東西收齊

- **適用**：eca（claude 身）的隊長，在一輪裡派了背景子 agent 或把長指令丟到背景，然後就寫最終回答。
- **坑**：這一輪寫出 result（success）後，`claude -p` 可能不退出（多半在等背景的東西，例如被額度擋住的背景子 agent）。aos 以為這一輪還沒結束，new_mail 進不來：從外面看是「回合已結束、有新信、卻沒醒」。ok-pilot 15:35 寫出 result 後行程掛著（頂層信裡的數字是 1 小時 33 分），兩封信躺在 `mailbox/new/`，背景的全套測試還在寫 log。最後頂層**得到使用者同意**才 kill 那支 claude；kill 後 aos-loop 把那輪當失敗，整隻停了（state done、code 1），跑到一半的測試沒有結果。
- **做法**：寫最終回答前，子 agent 的回答收回來、背景指令等到結束或明確停掉。跑很久的全套測試不要丟背景後就結束回合：前景等完，或寫成用 clock 叫醒自己再回來看的流程。額度快用完時不要再派背景子 agent。
- **驗過**：一次，11-14，沒有重現實驗（起算點代寫者沒查）。
- **出處**：`wf/temp/ok-pilot/wrapup-1114/經驗.md`（head-tools 代寫）；頂層信 01794642047051578975.2495172.3063270、01794643439561828052.2973611.3202521

## 可寫路徑寫成唯一一個絕對路徑，並寫明 /tmp 也不行

- **適用**：任務書要限制子 agent 寫哪裡。
- **坑**：寫「只寫一個檔」不夠：子 agent 還是把讀檔結果轉存到 `/tmp/`（`/tmp/walk2-k1.txt`），另一隻自己多留了備份檔。
- **做法**：寫成「唯一可寫的是這一個絕對路徑；別處都不行，/tmp、家目錄、轉存的暫存檔都不行」。驗收時看它的報告和實際動作，越界照實報。
- **驗過**：ok-kb 11-14 三隻子 agent，這樣寫的那一隻守住了；ok-onboard 之後每份任務書都寫明。[team-patterns「大批舊帳」](team-patterns.md) 也記過子 agent 順手越界。
- **出處**：`wf/temp/{ok-kb,ok-onboard,head-front}/wrapup-1114/經驗.md`

## 被權限擋住會乾等；Read／Write 常被拒

- **適用**：子 agent 在 don't ask 模式下跑。
- **坑**：子 agent 遇到 Read 或指令被權限擋，有的不回報、就停在那裡（ok-limits 的 B7 因此斷兩次）。Read／Write 被拒時它們會改用 `cat`、heredoc，所以「請把結果寫成檔」不一定寫得出來。
- **做法**：任務書寫明「一件事用 bash 腳本走完、不要用 Read 讀暫存樹」；要結果的寫「最後一則回答裡放全文」；配上面的進度檔。
- **驗過**：ok-limits、ok-kb 11-14。
- **出處**：`wf/temp/{ok-limits,ok-kb}/wrapup-1114/經驗.md`

## 子 agent 寫的日期、hash、行號要回原檔核

- **適用**：收子 agent 交回的稿。
- **坑**：它會補出沒看到的事實（把封存日寫成「2026-08-29」，實際是 2026-10-13）；也會把一句 AI 的轉述當成使用者原話。
- **做法**：日期、hash、行號、引號裡的原話，都回原檔核一次才採用。
- **驗過**：ok-astra（BB2）、ok-kb 11-14。
- **出處**：`wf/temp/{ok-astra,ok-kb}/wrapup-1114/經驗.md`

## subagent 的 system set 是整份取代

- **適用**：用 `subagent` 的 system set 給掛上的隊員加一段 system（含 eca 類隊員）。
- **坑**：set 是整份取代定義的 system，不是附加。
- **做法**：要保留定義原有的，就先 get 再接上自己的字。
- **驗過**：ok-board 11-14，設定 ok-board-fable-1、fable-2 時的回應。
- **出處**：`wf/temp/ok-board/wrapup-1114/經驗.md`
