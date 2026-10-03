# 做 agent 遇到的問題

← [proto7-1 spec](../spec.md) 第 10 節｜核心 spec：[core.md](../../proto7/spec/core.md)（條號 S-）

照核心 spec 做 `aos7-agent`（`lib/aos7_agent.py`、`lib/aos7_agent_tools.py`）與 LLM 後端（`lib/aos7_llm.py`）時碰到的問題。分級：〔要使用者決定〕＝方向、核心 spec 說不清或互相衝突；〔技術選型，先這樣〕；〔默認正常〕。

## A-1 寄信就得寫到別的 node，超出 tick 給的資料夾〔要使用者決定〕

- 層：agent ↔ aos 時空；S-10、S-13。
- 發生：`send` 要寫 `<root>/<to>/inbox/`。amy 的任務 birth.json `dirs` 只有自己的 node，寫 bob 的 inbox 就是碰了 tick 沒給的資料夾。兩個 agent 是兩個 node、兩條時間線，「互傳信」本身就是跨 node 的動作，S-10 的限制在這裡一定被打破。
- 繞過：不檢查 dirs，只擋「寫出空間根」與「`to` 不是存在的資料夾」（`aos7_agent_tools.inside`）。`write` 則限制在自己 node 內。
- 待答：跨 node 的信要怎麼合 S-10？（a）tasks.json 用 `dirs` 宣告對方 inbox；（b）信一律寫自己的 outbox、由 tick／tock 或 daemon 遞送（郵差歸時空層）；（c）共用一個 mail 資料夾當作兩條時間線重疊的部分（S-15）。核心 spec 把「任務與 tick、tock、daemon 之間的訊息交流」列在之後再說，但 agent 之間的訊息是 agent 層一開始就要的。跟 kernel 的 K-1 同一類。

## A-2 「每個 tock 換一次狀態」與 LLM 呼叫時間對不上〔要使用者決定〕

- 層：agent ↔ tick-tock；S-19、S-08、S-11。
- 發生：
  - 一封信至少要 2 個 tock 才回得出去（收件者 idle→think 問 LLM，think→act 寄出），寄件者 act→idle 還要再一個 tock 才回頭看信箱。假後端互傳 6 封信實測要 11 回合；接 LM Studio（gemma-4-e4b）互傳 4 封要 10 回合（每跳 2～4 回合，看同一回合裡誰先讀信箱、誰先寄出，是競態）。
  - 真 LLM 一次 0.5～0.8 秒（gemma-4-e4b），thinking 模型（qwen3.5-9b）一次 119 秒。timeline 預設 interval 100 ms，一次呼叫就跨 5～1000 多個回合。agent 是單執行緒，呼叫期間來的 tock 沒人讀，回來時 `wait_tock` 只看到最新的那個，中間的回合等於被併掉；「think 狀態」實際上持續到 LLM 回來為止，而不是一回合。
  - 收到 tock 先存 state.json（round 已更新）再去問 LLM，所以外面看 state.json 分不出「收到 tock 了」與「事情做完了」。
- 繞過：照字面「一個 tock 換一次」，但做事放在換完之後、做到完為止；被併掉的回合不補。progress.json 只在處理完 tock 後寫，所以卡在 LLM 裡的 agent 對 kernel 來說就是「卡住」。
- 待答：S-19「依託 tick-tock 換狀態」是指（a）每個 tock 都必須換一格（那 LLM 要在一回合內回來，或 think 要拆成「送出／等結果」兩個子狀態在背景跑）；還是（b）tock 只是「可以換狀態的時機」，事情沒做完就留在原狀態？回合的長度（interval）要遷就 LLM，還是讓 LLM 跨回合（S-11 允許任務跨回合）？

## A-3 重啟換了 tid，state.json 就找不到〔技術選型，先這樣〕

- 層：agent ↔ 任務；S-11、S-17（restart）。
- 發生：spec.md 把 state.json 放在 `$AOS7_TASK`，但 restart（`spawn/restart-<tid>.json`）與 `keep` 任務死後補起，都會開新 tid、新資料夾，原本的狀態留在舊資料夾。「存檔好讓被 restart 後接著跑」照字面做不到。
- 繞過：啟動時自己的 state.json 沒有，就掃同 node `.aos/tasks/*/`，挑 birth.json `name` 相同、state.json 回合最新的那份接著跑（不靠 `restart_of`，keep 補起也接得到）。usage.json 不接，每個任務從 0 算。
- 副作用：kernel 因「卡住」而 restart 的 agent，接到的是同一份停在 think 的狀態，會原樣再問一次 LLM；若卡住的原因就是這次呼叫（例如 prompt 讓模型一直想），restart 只會重演。要「重來」得手動刪舊 state.json 或改 agent 的狀態。

## A-4 死在 think／act 中途〔默認正常〕

- 層：agent；S-17、S-19。
- 發生：
  - think 中途被 kill（已實測：卡住的 HTTP 呼叫中送 SIGTERM，0.01 秒內結束、exit 0，state.json 停在 `think`、`plan: null`）：重啟後再問一次 LLM。前一次呼叫若其實已在模型端算完，那份用量沒記到、錢白花。
  - act 中途被 kill：每做完一步存 `pc`，重啟從 `pc` 接著做；但「做完那步、還沒存 pc」之間被殺，那一步會重做一次（例如同一封信寄兩次）。搬信、改名 goal 都是冪等的。
- 繞過：默認重做與重複寄信是正常的。

## A-5 progress.json 照「每次換狀態更新」會讓 idle 的 agent 被當成卡住〔技術選型，先這樣〕

- 層：agent ↔ kernel；S-17、S-19。
- 發生：原 spec 第 10 節寫「每次換狀態更新 progress.json」。沒信時 agent 一直留在 idle、不換狀態，progress.json 連續好幾輪不變，kernel 的「卡住」規則（第 9 節）就會一直 restart 閒著的 agent。
- 繞過：改成**每處理完一個 tock 就寫** `{"round","state","steps"}`（含 round，所以一定會變）。只有收不到 tock（卡在 LLM 呼叫、程序掛住）才會連續不變。spec.md 第 10 節已照改，kernel 組要知道 progress.json 現在是「心跳」，不是「進度」。
- 註：真正「原地打轉」（每回合都換狀態但沒做成事，例如 plan 一直解析失敗）這樣偵測不到。

## A-6 goal 用掉就沒了，失敗也一樣〔技術選型，先這樣〕

- 層：agent；S-19。
- 發生：goal.json 一用就改名 goal.done.json（不然重啟或下一輪又會開口一次）。接 qwen3.5-9b 實測：amy 第一次 think 的 plan 解析失敗、退成 none，goal 照樣被用掉——之後兩個 agent 永遠 idle，世界安靜下來，沒有任何人會發現（progress.json 照常每回合在動，kernel 也看不出來）。
- 另外：agent 去改人寫的輸入檔（goal.json），跟「人寫、程式讀」的習慣相反。
- 繞過：先這樣；失敗原因看 state.json 的 `last` 與 out.log。

## A-7 pause、回合不同步〔默認正常〕

- 層：agent ↔ daemon；S-08、S-18。
- 發生：
  - node 被 pause 就沒有 tock，agent 停在原狀態；信照樣被別人寫進 inbox 堆著。已經在跑的 LLM 呼叫不會停，還是會花 token——kernel 因「預算」pause 一個 node，擋不住正在燒的那一次。
  - amy、bob 是兩條時間線，回合數各數各的。信裡的 `round` 是寄件者的回合，對收件者沒意義，只給人看。兩邊 interval 不同時，快的一方會一直等慢的回信，屬正常。
- 繞過：都默認正常。

## A-8 真 LLM 回的東西不一定是 plan〔技術選型，先這樣〕

- 層：agent ↔ LLM；S-01、S-19。
- 發生（LM Studio 實測）：
  - google/gemma-4-e4b：prompt 要求只回 JSON 陣列，四次呼叫全部解析成功，正確互傳 ping 1～4，最後 `write work/done.txt`（內容 "Number is 4."）。每次 250～300 tokens、0.5～0.8 秒。
  - qwen/qwen3.5-9b（thinking 模型）：一次呼叫 119 秒、用掉 8192 tokens，`content` 是空字串（想法都在 reasoning 裡、輸出被長度上限截掉），plan 解析失敗 → none。
- 繞過：`parse_plan` 容忍 ```json 圍欄、`<think>` 段、前後廢話、單一物件；解不出就 `[{"tool":"none"}]`，原文前 200 字寫進 state.last。agent.json 可設 `max_tokens`、`timeout_s`。不重試。

## A-9 LM Studio 的開關會留下背景服務〔默認正常〕

- 層：環境（不在 aos 裡）。
- 發生：本機原本 LM Studio 完全沒開。光是跑 `lms status`／`lms ls` 就會把 LM Studio 背景服務（`lm-studio --run-as-service`，一串 Electron 程序）叫起來；`lms server start`、`lms load` 9 秒可用。做完 `lms unload --all`、`lms server stop` 後，背景服務仍然在，`lms` 沒有關它的子命令，最後是 SIGTERM 它的主程序才回到原狀。
- 意思：如果 agent 要靠 `lms` 自己把模型叫起來，「誰負責收掉它」又是一件 daemon 外面的事（S-03：Linux 那側的資源）。
