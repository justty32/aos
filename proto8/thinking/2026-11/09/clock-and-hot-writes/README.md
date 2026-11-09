# 2026-11-09 時鐘改名＋熱寫檔拉出 json（clock-and-hot-writes，只盤點、未改程式、未改條文）

← [2026-11-09](../README.md)｜細節：[01 想法 1 改名盤點](01-想法1-改名盤點.md)、[02 想法 2 熱寫檔實測](02-想法2-熱寫檔實測.md)、[03 衝突與方向題](03-衝突與方向題.md)

## 使用者原話（11-09 早，整理版）

> 我昨天有稍微玩過，有些想法，今天會繼續玩，但我這邊先把想法提出來讓你看看：
> 1. daemon 的 `_tick` 我覺得應該改名叫 clock，不然有點跟 linux 原生的 tick 混淆。
> 2. 一些 json 檔案變動得太頻繁，如 loop 的 runs 之類，像這類非常頻繁變動的，我覺得可以從 json 中拉出來，改成用 .txt 寫，然後要有 argv 做旗標選擇是否要寫。這應該是原則，不然這種固定的寫檔開銷實在不好。

補充（同早，經頂層轉述，逐字）：

> 我其實會希望大改。除此之外，也有一個備選：改為turn
>
> hmmm，那還是clock好了
>
> 等等，不過感覺turn也還是可以

## 裁定

- **想法 1 範圍＝大改**（使用者「我其實會希望大改」）：proc 名 `_tick`、daemon 設定 `tick` key、`AOS_TICK`／`AOS_TICK_INTERVAL`、`aos-tick` 指令、tick 這個概念在條文裡的用語，一起改。
- **新名字：待使用者在 clock／turn 二選一**（先說 clock、又說 turn 也可以）。
- 想法 2：還沒裁，方向題在 [03](03-衝突與方向題.md)。

## 結論

**想法 1**（細節 [01](01-想法1-改名盤點.md)）：
- 大改不算「歷史」（thinking、日誌）大約 **1,100 處、200 個檔**：程式約 470 處／70 檔，條文與說明約 340 處／80 檔，wf 約 275 處／50 檔（含生成的 code map），再加桌面 7 頁說明約 210 處、試驗場 5 個檔。裡面最大的一塊是單位欄位（`timeout_ticks`、`stuck_after_ticks`、`sent_at_ticks`… 約 290 處／50 檔程式）。
- **`started_at_ticks` 不改**：它是 Linux `/proc/<pid>/stat` 第 22 欄，數的真的是 Linux 的 tick。這正是使用者說的混淆：同一列裡 `started_at_ticks`（Linux）和 `stuck_after_ticks`（aos）兩種 tick 並存。大改以後，這欄就是唯一叫 tick 的東西，意思也對。
- **clock 的問題**：clock 是一個「東西」（時鐘），不能當單位用（寫不出 `timeout_clocks`），所以單位要另外取一個字（推薦 `cycle`，對應 clock cycle，跟板子晶振的比喻一致，repo 裡只有 `lifecycle` 用到這個字）。會撞到的是腦的工具 `lib/base/clock`（印牆上時間，意思剛好相反）和幾個範例 proc 名 `clock`／`clock2`，大約 22 個檔。另一方面，英文輸出早就把這個時鐘叫 clock（`treating the clock as 0`、`its own clock`）。
- **turn 的問題**：turn 一個字就能同時當東西和單位（`AOS_TURN`、`timeout_turns`），中文說明本來也寫「第 n 回合」。但它撞到 `aos-eca-turn`（28 檔、78 處）、`turns.jsonl`、`cli_session` 裡的 turn（26 處），還有「腦答一輪」這個意思。像 agents 的 `ask timeout_turns` 會被讀成「等腦答幾輪」。
- **推薦 clock（時鐘本身）＋cycle（單位）**。可執行判準：改完以後在 proto8（不含 thinking）grep `\btick` 只剩 `started_at_ticks` 一家，grep `turn` 只留 eca 那一族。

**想法 2**（細節 [02](02-想法2-熱寫檔實測.md)，WSL 試驗場三層複本、假腦、inotify 實測）：
- 整棵樹（根、總機、領班＋一隻閒著的 fsm_ann）**閒著也每秒整份重寫約 25 次**；問一題（約 4 秒、問腦兩次）寫約 155 次，其中約 125 次是「時間過去」本來就會寫的，只有約 30 次真的是這題造成的。
- 最常寫的前幾名：總機的 `procs_state.json`（每秒 4.3 次）、總機的 `state.json`、`queue.json`（各 3.3 次）、fsm_ann 的 `state.json`、`stage.txt`（各 3.1 次），再來是三個時鐘的鐘檔、`_tick/state.json`，以及根和領班的表（各每秒 1 次）。
- **使用者看到的 runs 不是元兇**：`counter_runs` 從 11-02 起就不算變動。每跑一次就重寫，是因為 `responded_at` 在「身體跑完一次」時就更新（11-06 no-pid P5b），`counter_runs` 只是跟著一起寫進去；daemon 的表還多了每一格都會變的 `tick` 觀察值。所以光把 `counter_runs` 搬去 .txt，`state.json` 一次都不會少寫。
- 不用新原則就能省的：fsm 的 `stage.txt` 內容沒變也照寫（閒著時每秒 3 次都寫 `idle`），改成有變才寫就好；llm kernel 的 `queue.json` 只因為 `counter_runs` 加一就重寫。
- 大局：閒著的 agent 每 300 毫秒起一次 `aos-fsm`＋`python3 idle.py`，三個時鐘每秒各起一次 Python 的 `aos-tick`。起程序的開銷應該比寫檔大得多（沒量，只是推估）。

**衝突與方向題**（[03](03-衝突與方向題.md)）：碰到的條文 9 條，方向題 5 題，每題都附推薦和判準。

## 跟 open 線的關係

- tick-time／lift-to-norms：想法 1 等於把 tick-time 03～05 的用語整套換掉，裁定內容（兩鐘規則、近的贏、N1／N2）都不動；想法 2 的方向題 3 會改到 N-65 ②「看 `tick` 欄」那句。
- no-pid（P5b／P7）：想法 2 真正省得到寫檔的關鍵是 `responded_at` 的更新時機（方向題 2），碰到 P7 卡住判斷，要跑 P9 的實測回歸。
- apply-ideas／arch-refactor：兩個想法都是新的施工步，不插進現有的 S 步，建議排在 apply-ideas 剩下的步之後，一個 commit 一個名字族（不寫遷移）。
- edge-1107（aos-tick 同檔並寫）、special-cases（`_` 保留字）：只要跟著改名，結論不變。
