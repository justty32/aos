# 照 proto7 核心 spec 做下去遇到的問題（總表）

← [proto7-1](../README.md)｜[spec.md](../spec.md)｜核心 spec：[core.md](../../proto7/spec/core.md)（條號 S-）

proto7-1 從 daemon 一路做到 kernel 與 agent，示範場景（`demo/play.py`）全部跑通。下面是做的過程中碰到的問題。各組的細節在三份分檔：[核心 P-](problems-core.md)（daemon、tick、tock、任務）、[kernel K-](problems-kernel.md)、[agent A-](problems-agent.md)。整合時隊長自己碰到的記在本檔 I-。

分級：**〔要使用者決定〕**＝方向問題，或核心 spec 說不清、互相衝突；〔技術選型，先這樣〕；〔默認正常〕。各組原本列了 8 條要使用者決定，隊長合併、降級後剩下面 4 條（D-1～D-4）。

## 要使用者決定（4 條）

### D-1 任務「只碰 tick 給的資料夾」，但 kernel 和 agent 的本分都是跨資料夾的動作

- 合併 A-1、K-1（K-3 也有關）。碰到 S-10 對上 S-18、S-21，以及 agent 之間的通信。
- 發生了什麼：
  - amy 寄信給 bob，要寫 `team/agents/bob/inbox/`，那是別的 node。
  - kernel 要寫成員 node 底下任務的 `ctl.json`，也要讀成員的 `.aos/tasks/`。
  - kernel 和路二的任務要下 daemon ctl，就得寫 `<root>/.aosd/ctl/`，那是 daemon 自己的地方。
  - 以上都在 tick 給的資料夾（自己的 node）之外。要做 S-18、S-21 和 agent 互傳信，S-10 的限制一定會被打破。
- 先這樣：tasks.json 用 `dirs` 宣告「tick 另外給的資料夾」，寫進 birth.json，但不強制（沒有 FUSE）。daemon ctl 的路徑靠環境變數 `AOS7_ROOT` 找到。實際寫入一律不檢查。
- 要決定的：跨 node 的動作怎麼合 S-10？可能的方向如下（不代替你選）：
  - （a）tick 宣告式地多給資料夾，也就是現在的 `dirs`，daemon ctl 目錄算每個任務都有。
  - （b）任務只寫自己的 outbox 或控制檔，由時空層（tick、tock 或 daemon）遞送。郵差歸時空層，等於把核心 spec「之後再說」的訊息交流提前。
  - （c）共用資料夾，當作兩條時間線重疊的部分（S-15）。

### D-2 回合對「跨回合的常駐任務」幾乎沒有意義；agent「一個 tock 換一格」跟 LLM 的時間對不上

- 合併 P-16、A-2，K-2 是它的分支。碰到 S-08、S-09、S-11、S-19。
- 發生了什麼：
  - daemon 的「提前 tock」只等**本回合 tick 起的**任務。kernel、agent 是第 1 回合起來的常駐任務，之後每回合 tick 什麼都沒起，tock 約 40 ms 後就到，接著是整段空等。示範裡 amy 跑了 54 回合，53 回合「沒有任務起落」。
  - kernel、agent 收到 tock 後才做事，所以它們的事其實都落在「回合之間」。
  - agent 照 S-19 每收一次 tock 換一格（idle→think→act）。一封信要 2～4 回合才回得出去，假後端互傳 6 封信要 11 回合。
  - 真 LLM 一次呼叫就跨過很多回合。gemma-4-e4b 0.5～0.8 秒，約 5～8 回合；thinking 模型一次 119 秒，超過 1000 回合。呼叫期間的 tock 被併掉，「think」實際上持續到 LLM 回來。
  - kernel 管的是別的時間線，「卡住 N 回合」數誰的回合也說不清。現在卡住數成員的回合，冷卻數 kernel 自己的回合，兩種時間並存。
- 先這樣：照字面做，被併掉的回合不補。
- 要決定的：
  - 回合要不要等常駐任務，例如「tock 等所有活任務回報這回合做完」？這需要任務對 daemon 的回報，是核心 spec「之後再說」的訊息交流。
  - S-19 的「依託 tick-tock 換狀態」是指每個 tock **必須**換一格，還是 tock 只是**可以**換的時機（事情沒做完就留在原狀態）？
  - 回合長度要遷就 LLM，還是讓 LLM 自然跨回合？

### D-3 kill 一個常駐（keep）任務，下個 tick 就被任務表起回來，kill 實際上等於 restart

- 即 P-09。碰到 S-17、S-10。
- 發生了什麼：
  - `keep` 的意思是「沒有同名活任務就起一個」。kill 之後沒有活的了，下個 tick 照 tasks.json 再起一個。
  - kernel 的「壽命 kill」和路一的「父時間線 kill 子 daemon」都只是讓它重開一次。core 的測試看得到 subd-r2 又起來。
  - 示範裡 subd 是用一次性的 `spawn/` 起的，所以沒被起回來。
- 先這樣：不改。真的要停，只能改 tasks.json 或 pause 那條時間線。
- 要決定的：kill 的意思是「這一個實例結束」，還是「這個任務別再有了」？如果是後者，就要定「任務表誰能改」（核心 spec 列為之後再說），或在 ctl 加一個「停用」的 op。

### D-4 時間線被 pause 時，對它的任務下的 kill／restart 不會執行

- 合併 P-06、K-4。碰到 S-17 與 S-18。
- 發生了什麼：
  - S-17 說「在 tick-tock 時」做 kill、restart，所以 ctl.json 只在 tick、tock 時執行。
  - pause 的時間線沒有 tick、tock，ctl.json 會一直等到 resume。
  - kernel 想「先 pause 燒錢的時間線，再 kill 裡面的任務」做不到。pause 擋不住正在跑的 LLM 呼叫。
  - 預算 pause 和卡住 restart 落在同一個 node 時，restart 會被延到冷卻結束之後。
- 先這樣：照字面，pause＝凍結一切，控制也一起凍結。
- 要決定的：「在 tick-tock 時」是指控制**只能**落在回合邊界上，還是只是 kernel 判斷的節奏？如果是後者，daemon 在 pause 時也可以照樣執行 ctl.json。

## 其餘問題一覽（技術選型 19 條、默認正常 16 條）

細節點進分檔看。

**技術選型，先這樣**

- [P-01](problems-core.md) daemon 內用 thread 管各時間線的迴圈（S-04）。tick、tock、任務都是程序。
- [P-02](problems-core.md) 任務靠環境變數找到自己的資料夾，`cat` 不到（S-01）。birth.json 有一份可讀的。
- [P-04](problems-core.md) 子 daemon 被 SIGKILL 會留下孤兒任務（實測過）。被 SIGTERM 時，要在父的 1 秒寬限內收完自己的任務。
- [P-05](problems-core.md) 搬來的 aos-exec 把 inst 子程式開在另一個 session，kill 收不到。改成走 `/proc` 把所有後代的群組一起殺。
- [P-08](problems-core.md) daemon 重開時，回合數接著數，pause 存到 `.aosd/paused.json`。
- [P-10](problems-core.md) 兩個 daemon 搶同一個空間。同一個 root 用 flock 擋；不同 root 重疊時沒有鎖，node id 會跟著 daemon 根變。
- [P-11](problems-core.md) 子 daemon 起來之前，父 daemon 會把子 daemon 的 node 當自己的。示範場景預先放了 `team/sub/.aosd/` 當標記。
- [P-14](problems-core.md) stop 時，回合中途的時間線立刻 tock 收掉這個回合。
- [P-22](problems-core.md) 各種小補：round.json 加 `started`、`ctl` 兩欄；`aos7-ctl --kill`；起不來的任務寫結束碼 127。
- [K-2](problems-kernel.md) 「卡住 N 回合」數的是誰的回合（併入 D-2）。
- [K-3](problems-kernel.md) kernel 看別的 node 的任務只能自己掃資料夾，跟 tock 的判斷重複了一份。
- [K-5](problems-kernel.md) kernel 不能 pause 自己的 node，否則一步就鎖死。預算規則跳過自己。
- [K-6](problems-kernel.md) restart 會換一個新的任務資料夾，kernel 要去接前一任的狀態。**「任務還沒準備好時 tock 先到」是常態**，每個收 tock 的任務都要自己處理。
- [K-7](problems-kernel.md) 「進度」「用量」的檔案協議由誰定義。progress.json 實際上變成心跳。
- [A-3](problems-agent.md) agent 重啟換了 tid，state.json 要從舊資料夾接。被 restart 的 agent 會原樣再問一次同樣的 LLM。
- [A-5](problems-agent.md) progress.json 如果「換狀態才更新」，閒著的 agent 會被 kernel 當成卡住，所以改成每個 tock 都寫。
- [A-6](problems-agent.md) goal.json 用一次就沒了，失敗也一樣。實測 thinking 模型失敗後，世界就安靜了，沒有人發現。
- [A-8](problems-agent.md) 真 LLM 回的東西不一定是 plan。gemma-4-e4b 四次全部成功；qwen3.5-9b 一次 119 秒，回應是空的。
- [I-2](#i-2-回合紀錄看不到常駐任務做了什麼技術選型先這樣) 回合紀錄看不到常駐任務做了什麼。

**默認正常**

- [P-03](problems-core.md) 任務被 reparent 給 init，daemon 只能每 20 ms 輪詢檔案和 `/proc`。
- [P-07](problems-core.md) 判斷 lost 有競態（已用 runner_pid 補洞）。pid 會被重用。
- [P-12](problems-core.md) 任務資料夾只增不減，而且每 20 ms 全掃一次。
- [P-15](problems-core.md) node 消失時，那個回合不 tock。搬家改名等於舊 id 消失、新 id 出現。
- [P-17](problems-core.md) kill 很慢，會拖慢 tick（違反「tick 很快結束」）。
- [P-18](problems-core.md) ctl.json 只有一個檔，後寫的蓋掉先寫的。
- [P-19](problems-core.md) 父 kill 子 daemon 時，會打斷子 daemon 正在跑的 tick／tock。
- [K-8](problems-kernel.md) 用量算進已結束的任務；第一次看到某 node 時不算舊帳。
- [K-9](problems-kernel.md) restart 常駐任務時，tick 內的順序如果反過來，會起兩份。
- [K-10](problems-kernel.md) kernel 下完控制不看結果。
- [A-4](problems-agent.md) agent 死在 think 或 act 中途，重啟後重做，可能重複寄信。
- [A-7](problems-agent.md) 兩個 agent 的回合不同步；pause 中信件會堆積。
- [A-9](problems-agent.md) 用過 LM Studio 的 `lms` 之後會留下背景服務，要另外收掉。
- [I-1](#i-1-被-kill-的子-daemon-結束碼是-0默認正常) 被 kill 的子 daemon，結束碼是 0。
- [I-3](#i-3-pause-的回合在時間線紀錄裡不留痕跡默認正常) pause 的期間在時間線紀錄裡不留痕跡。
- [I-4](#i-4-示範的結果依賴牆鐘默認正常) 示範的結果依賴牆鐘。

## 整合時碰到的（I-）

### I-1 被 kill 的子 daemon 結束碼是 0〔默認正常〕

- 層：任務控制 × daemon；S-17、S-21 路一。
- 發生了什麼：
  - 示範裡 kernel 依壽命 kill subd。子 daemon 收到 SIGTERM，照 spec 做「stop＋kill」後正常退出，所以 exit.json 的 code 是 0。
  - team 第 15 回合的紀錄寫的是 `subd-r1(0)`。光看結束碼，分不出「被 kill」和「自己做完」。
- 先這樣：要看被控制過，得看同一回合的 `ctl` 欄，或任務的 ctl-done.json。

### I-2 回合紀錄看不到常駐任務做了什麼〔技術選型，先這樣〕

- 層：aos 時空；S-01、S-08。
- 發生了什麼：
  - `rounds/<N>.json` 只記任務的起落和控制。kernel 的決定、agent 的狀態變化與寄信，都在各自任務資料夾或 node 的檔案裡（decisions.jsonl、state.json、inbox/done/）。
  - 想回答「第 N 回合發生了什麼」，要拼好幾個地方的檔，play.py 就是這樣拼的。
  - 再加上各時間線的回合數不同步，跨時間線只能用牆鐘的 `at` 對照。
- 先這樣：不加統一的事件流水帳。之後若要給 LLM 看「這回合發生了什麼」，可能要一個回合層級的事件檔，由任務回報。這跟 D-2 的訊息交流是同一件事。

### I-3 pause 的回合在時間線紀錄裡不留痕跡〔默認正常〕

- 層：daemon；S-08、S-18。
- 發生了什麼：pause 期間不開回合，`rounds/` 的編號照樣連續，看不出中間停過。要知道停過，得看 daemon 的 `log.jsonl` 或 `ctl-done/`。這合「時間＝回合」的意思（停了就沒有時間），只是讀紀錄的人要知道這一點。

### I-4 示範的結果依賴牆鐘〔默認正常〕

- 層：示範與測試；S-08（不準時無妨）。
- 發生了什麼：
  - 回合由 interval 推動（100～150 ms），6 秒大約跑 40～54 回合。
  - kernel 的壽命規則要 team 跑到第 14 回合，預算規則要兩邊對話燒到 250 tokens，所以檢查項目能不能全部成立，取決於機器快慢。
  - 測試給了 6 秒，在本機有很大的餘裕。機器太慢時，`test_demo` 可能少掉壽命 kill 那一項。
