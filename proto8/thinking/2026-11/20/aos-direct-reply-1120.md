# 線 aos-direct-reply-1120 紀錄：「問特定的東西、直接回」通用模式的調查——只交 thinking，量測在暫存夾的乾淨複本

← [2026-11-20](README.md)｜成品：[aos-direct-reply-1120/](aos-direct-reply-1120/README.md)

頂層派。依據：使用者 11-20 下午「像這種"問某種特定的東西，然後不需要思考或做其他處理(當然，硬要的話也可以，就是用hook)，就是直接回覆特定的東西"的模式很好用。感覺之後可以特別專門去規劃，我最擔心的就是他每次的回覆都要吃到loop的body的運作時間，會讓整個變慢。」頂層問下一步時他說「這塊就派線去調查一下先前說的那個通用的。」

## 做了什麼

- 讀：`aos-kask-1120/`、`aos-kask-proto-1120/`（含 `07-使用者已答`）；盤點交給一個唯讀子 agent（Explore）掃 daemon 信箱、kernel 骨架與 llm kernel、kernel_gate、agent-fsm、eca slash、`aos-daemon-ctl`、`aos-agent ctl／ask`、`aos-llm ls`，本線抽查 `mailbox.cpp`、`idle.py`、`compact.py`、`round.py` 幾處。
- 量：`git archive HEAD`（`f522b5570`）只抄 `proto8/`、在 `~/.aos/scratch/aos-direct-reply-1120/src/` 裝好。
  - `meter.py`／`meter.sh`：agent-fsm 的 idle 格手跑（空、1／10／30／100 封普通信、一封太短的 `/compact`）；空信箱多看一眼；每答一封（現成小檔／現算／1 MB）×1／10／30／100；讀現成檔與寫的人每輪寫。
  - `kround.sh`、`kmeter.sh`：兩種 kernel 的 body 用 `aos-exec` 手跑一輪；`patch.sh` 把原型線的 `kask.py` 放進**複本裝好的 lib/**、加一支「答案變了才寫檔」，用 `DR_MODE` 切三種比。
  - `dping.sh`：start-api 的根 daemon 單獨起來 ping 20 次，量完 `shutdown`。
- 寫 `aos-direct-reply-1120/` 六份：README、01～05。

## 證據

- 原樣輸出：`~/.aos/scratch/aos-direct-reply-1120/meter.out`；kernel 與 ping 的輸出抄進 [02](aos-direct-reply-1120/02-數字.md)。
- 關鍵數字：空信箱 0.024 ms／次；每封 8～9 ms（kernel body 實跑）、18～24 ms（一般行程含 see＋done）；llm kernel 一輪 0→100 封 83→992 ms、掛 proc 的 63→828 ms，141 封回信全收到、信箱清空；agent idle 空拍 144 ms、100 封普通信 2.43 s；讀現成檔 0.02 ms；daemon ping 整支 202 ms。
- 沒跑測試：本線不改程式；`patch.sh` 只改暫存複本的 `lib/`。

## 沒做的

- aos-loop 代答、daemon 代答、另起一個 proc：沒實作、沒量（daemon 只量了今天的 `ping`）。
- agent 的「直接回」沒實作；灌 N 封對 agent 的拖延是用「每封 22 ms」推的，表上有標。
- 沒在活的 daemon＋aos-loop 底下量 agent 端到端（從寄出到回信）；kernel 端到端沿用原型線的數字。
- 盤點的行號多半是子 agent 讀的，本線只抽查幾處。

## 對不上處

- 原型線說每封約 19 ms，本線 body 實跑 8～9 ms：原型線量的是寄出到收到（含寄信那半），本線只量 body 那一輪。02 有註明。
- 子 agent 發現：經 kernel_gate 的 `{"ping": true}` 會被 hold（只有 `procs_state_path` 被放行），跟 daemon 直接 ping 的行為不同。只記在 01，沒改。

## 替使用者做的選擇

- 盤點的分類（寄信／讀檔／其他）與「九處左右」的算法是本線的，`aos-agent ask` 判成不算（答的是模型）。
- kask 的十四題答案只當「kask 那一個用途」的對照，沒當通用規則（任務書這樣交代）；05 有幾題標了「kask 已選」。
- 05 題目控制在八題；鏈上誰答、權限沒單獨出題，寫進 03、04。

## 跟別線

- 只交本線領地的七個檔加日索引一列；同時在跑的 `aos-hook-k3-1120`、`aos-kllm-round-1120` 改程式，沒碰到同一個檔。量測用 HEAD 複本，沒抄工作樹裡別線的改動。

## 收尾

- 行程：`dping.sh` 起的根 daemon 已 `shutdown`，`pgrep -a aos` 沒有本線的行程。
- 暫存：`~/.aos/scratch/aos-direct-reply-1120/`（`src/` 複本、`kt/` 暫存樹、`w/` 量測信箱），全部留著。
