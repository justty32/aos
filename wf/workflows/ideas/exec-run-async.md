# exec、run 與長任務：`async:true` 要長在哪裡

← [ideas](README.md)｜[nested-eval-car](nested-eval-car.md)｜[nested-eval-sugar](nested-eval-sugar.md)｜[play-watchlist](play-watchlist.md)｜[top-to-bottom/01](top-to-bottom/01-top.md)

**本檔無裁決。** 使用者只是問「你覺得這樣好嗎」，尚未裁；以下 AI 觀察都可以否決。

## 使用者原話（2026-09-04）

> 然後用這種方式思考，aos exec xxx，若xxx是檔案，那就是呼叫該檔案，若xxx是資料夾，那就是跑該資料夾下的.aos/insts.json。而aos run xxx，則是連續執行數次、以特定時間間隔，或是執行到滿足特定條件(這個我還沒想好)。再接著就是aos agent怎麼玩的，他本質上就是aos run，至少執行三次：取指令丟llm、取llm結果、執行tool呼叫，然後連續下去。一個需要考慮的事情是，若取指令丟llm這塊，是直接跑curl呼叫llm，那麼這次aos exec就會跑很久，那其他inst都執行完了，就剩這個任務在卡，所以通常會建議跑這種要很久的inst，通常都是把請求丟到其他資料夾，由其他aos run去執行，然後這邊就不會阻塞。現在我的想法是，像這種狀況，我們都是"建議"inst不要耗太長時間，沒辦法做實際限制，或是不使用其他aos run的方法，那這時候就是語法糖出現的時候了。語法糖在這個時候，就是aos run他本身會去支援一些東西，方便使用，比如在這種情況下，就是aos run會吃inst中的額外key，比如async:true，那aos run就會直接開執行緒去跑這個inst...你覺得這樣好嗎

## AI 觀察（非裁決，可否決）

### a. `exec` 對檔案、對資料夾的意思是接得上的

`aos exec xxx` 遇到**檔案**就是呼叫普通程式；遇到**資料夾**就是跑那台 car，也就是讀
`.aos/insts.json` 來走一步。這跟已裁的「**資料夾＝list、`.aos`＝car**」一致。

### b. `run` 就是反覆 `exec`，直到跑到定點

可以跑固定次數、隔固定時間再跑，或跑到某個停止條件成立。停止條件還沒定。AI 建議它必須是
**看得見的檔案或步數**，例如 `.aos/` 出現某個檔就停，不要把條件藏在 daemon 的記憶體裡。
理由很直接：**可預測性最優先**；行程掛掉再起來，人仍應該看得出它為什麼停、接下來會怎樣。

**2026-09-04 使用者定義**：**這次 exec 沒產出新的 inst 就停**。原句保留為歷史；正式回答見
[agent-loop-answers 第 2 題](agent-loop-answers.md#第-2-題跑到什麼時候)。

### c. `agent` 是一個 `run`，一圈至少三步

最少是：**取指令丟 LLM → 取 LLM 結果 → 執行 tool 呼叫**，然後繼續下一圈。其中「取 LLM
結果」正是 [top-to-bottom/03](top-to-bottom/03-inside-aos.md) 記過的坑：**外面等裡面的值，裡面
沒有人跑就永遠等。** 所以長請求不只是慢，還會碰到到底由哪個 loop 負責往前推的問題。

### d. `async:true`：AI 反對開執行緒，贊成開子資料夾

執行緒住在記憶體裡：父 `run` 一掛，正在跑的東西跟著消失，磁碟上也沒有足夠痕跡讓人看、殺、
重跑。子資料夾住在磁碟上：現在做到哪裡看得到，也能把那一支行程殺掉或重新跑。

AI 提議把這顆糖定成：

1. `async:true` 時，父 `run` 自動開一個子資料夾，把該 inst 寫進去。
2. fork 一支行程跑 `aos run <子資料夾>`。
3. 該 inst 的結果固定落在子資料夾 `out/` 的一條固定路徑。
4. 父每次 `exec` 只看一眼那個檔在不在；不在就繼續做別的，在了才讀結果。

這樣仍然只走已知的**唯一一座橋**：`aos run <child>`，沒有把資料夾層偷偷折進 inst 層。
它也順便替 [play-watchlist 第 1 條](play-watchlist.md#1-父層怎麼拿到子資料夾的結果)提出一個答案：
**父拿子的結果＝讀固定路徑上的一個檔。這只是 AI 提議，未裁。**

### e. 「沒辦法實際限制」其實可以限制，但那是另一顆 key

`run` 可以硬性規定每條 inst 的時間預算，超時就殺。它的意思是「**仍在這裡跑，但不准超過
時間**」；`async` 的意思是「**去別處跑，父不要在這裡等**」。兩者不是同一件事。

時間預算對應 [os-metrics-and-resources](os-metrics-and-resources.md) 的 RTOS 主線：最壞時間要有界。
續篇 [exec-run-async-time](exec-run-async-time.md) 據使用者的新傾向，把 timeout 降為保險絲，主線改成環境限制的事前保證。
**不急，先記。**

## 現有 aos 對照

| 模型名稱 | 程式裡的名字 | 合不合 |
|---|---|---|
| `aos llm` 送出後等 HTTP | `core/llm/src/run.cpp` 的 `aos_llm_cli_main()` → `core/llm/src/llm.cpp` 的 `complete()` → `curl_easy_perform()` | **符合「直接等 curl」**：同步等完整 HTTP 回來，不走 inbox／batch |
| `aos agent` 取指令丟 LLM | `core/agent/src/step.cpp` 的 `step()` → `complete_locally()` → `aos::llm::complete()` | **符合「一步會卡很久」**：同一支 agent inst 裡同步等 LLM；工具呼叫才另投 world inbox，跨回合收結果 |
| 一步內多條 inst | `core/loop/src/turn.cpp` 的 `run_turn()` → `aos::exec::start_all()` → `aos::exec::wait_all()` | **一半符合擔心**：全部先 fork，所以慢的不卡其他 inst 開始；但整個回合要等最慢的收完，才一起寫 out、推下一回合 |
| inst 的時間上限 | `core/loop/src/turn.cpp` 的 `to_spawn()` 傳 `timeout_ms`；`core/exec/src/wait_all.cpp` 的 `wait_all()` 超時 `SIGKILL` process group | **已經能實際限制**，只是 `0` 代表不限；這是 timeout，不是 async |
| tick 派工 | `core/tick/src/tick.cpp` 的 `run_tick()` 呼叫 `loop::deliver()` | **只投 inbox，不在 tick 裡等工作做完**；它不會把同步 LLM 自動變非同步 |

## 相關清單

- `G06`（行程誕生）：`async:true` 若開子資料夾，就是父 `.aos` 生出一個可見行程。
- `G14`（載入器）：對資料夾 `exec`／`run` 必須把原稿載入 `.aos/`，也是自動子資料夾要接上的入口。
- `G10`（排程）：父回合何時再看子結果、多少 async 子行程能同時跑，最後會落到排程。
- `G16`（資源需求與優先級）：長任務移去子資料夾後，仍要說明自己會占多久、排多前面。
- `G18`（資源計量）：timeout 的預算與實際耗時都需要可見紀錄。
- `G19`（資源不可靠）：LLM 會慢、會逾時、會失敗；可預測性優先時不能把等待藏進記憶體。
- [play-watchlist](play-watchlist.md)：尤其第 1 條回傳、第 3 條失敗、第 4 條子資料夾壽命。
