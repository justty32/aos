# 量到的數字

← [本題 README](README.md)｜腳本在 [exp/](exp/)

機器：AMD Ryzen 7 9800X3D（16 執行緒）、60 GB、Python 3.14.7；實驗家放 tmpfs（`/tmp`）。帳本存檔另在 ext4 上重量一次，數字一樣（沒有 fsync，花的是 CPU 不是磁碟）。
模型全程**沒接**：實驗 B 的假模型收到就不回（模擬「3 顆 llm cpu 都在等」），其餘不需要模型。跑完 `pgrep -fa idle-wait` 是空的。

## A. 一格「在等模型」的 `aos-agent tick`（[exp/a_agent_tick.py](exp/a_agent_tick.py)，各跑 60 次）

直接跑 kernel 會派的那條命令列；think 單已送出、K 裡沒原單也沒回音 → 退 101。

| 跑什麼 | 牆鐘中位數 | CPU 平均 |
|---|---|---|
| `python3 -c pass` | 5.7 ms | 5.5 ms |
| 只 `import aos_agent` | 20.9 ms | 20.9 ms |
| tick：在等模型 | **26.4 ms** | **26.3 ms** |
| tick：idle 沒輸入（J 隊講的） | 26.4 ms | 26.3 ms |

**八成時間是 Python 起來＋import**，真正「看一眼」只有約 5 ms。檔案（[exp/count_io.py](exp/count_io.py) 用 audit hook 數）：

- 家裡讀 6 個檔：`.tick.lock`、`info.json`、`state.json`、`prompts/system.json`、`prompts/history.json`（整份讀驗）、`tools/date.json`；列 `tools/` 一次；stat `paused` 等。
- K 那邊只 stat 兩次：`K/requests/<單>.json`、`K/responses/<單>.json`。**不讀帳本；除了把自己的 pid 寫進 `.tick.lock`，不寫任何檔**。
- 另有 import 的噪音：開 84 個 `.py/.pyc`、stat 144 次（每起一支 Python 都要）。

## B. 真 daemon＋kernel＋N 個 agent 全在等（[exp/b_e2e.py](exp/b_e2e.py)，[exp/run_all.sh](exp/run_all.sh)）

3 顆 llm cpu 被假模型掛住，其餘 think 單在 kernel 排隊；`tick_ms`＝`interval_ms`＝1000（預設）。
每個 agent 的 `llm.timeout_ms` 拉到一小時（init 預設 125 秒，窗口內會有人逾時結清——第一輪就是這樣，審查挑出來後重跑）；
暖機到每個 agent 都「think 已送出」再等 5 秒才量 **60 秒**；暖機不到、或窗口前後 3 顆 llm cpu 手上的工作換了，腳本直接判失敗。
CPU 秒數＝各行程 `/proc` 的 utime＋stime＋已收孩子的 cutime＋cstime 差，**還活著的 tick 行程也算**（agent tick 歸 default 池、`aos-kernel tick` 歸 kernel cpu）。
快照、`last_seq`、kernel.log 不是同一瞬間讀的，格數少的那組（300／300 只有 8 格）誤差約一格，當粗估看。

| agent 數／default cpu 數 | 100／100 | 300／30 | 300／300 | 0／300（只看 cpu 閒著輪詢，30 秒） |
|---|---|---|---|---|
| kernel 一格實際多長 | 1.43 s | 1.58 s | **約 7.5 s** | 1.03 s |
| kernel 每格 CPU | 424 ms | 551 ms | **約 6.5 s** | 42 ms |
| 60 秒內 agent tick 數 | 2100（全 101） | 1140（全 101） | 2400（12 個退 0） | 0 |
| 每個 agent 多久被看一次 | 2.9 s | **15.8 s** | 7.5 s | — |
| 一次 agent tick 在 default 池花的 CPU（含 cpu 自己的輪詢、起行程、寫回音） | 44.5 ms | 33.4 ms | 47.9 ms | — |
| 整套平均佔幾顆核 | 1.86 | 0.99 | 2.80 | 0.64 |
| 帳本大小 | 116 KB | 326 KB | 410 KB | 17 KB |
| 在排隊的 llm once | 97 | 297 | 297 | 0 |

- 300／300：一格 7 秒多，幾乎全在 kernel——**kernel 單線程是牆**，cpu 再多也沒用。那 12 個退 0 沒追（猜是暖機尾巴的收批）。
- 300／30：kernel 還撐得住，但一顆 cpu 一格只能做一件（做完要等 kernel 下一格收），30 顆輪 300 個 agent＝每個 16 秒才被看一次。模型答案回來後，平均要多等約 8 秒 agent 才發現。
- 0／300：300 顆閒 cpu 每 20 ms 掃一次資料夾，佔 0.57 顆核；1000 顆約 1.9 顆核。
- 第一輪（30 秒窗口、沒修逾時、沒算活著的孩子）數字很接近（300／300 一格 6.0 s、kernel 6.3 s CPU），結果檔留在 scratchpad 沒收進來。

## C. kernel 帳本整份存一次多久（[exp/c_ledger.py](exp/c_ledger.py)）

拿 B 第一輪的 300 agent 帳本照「一個 agent＝一筆 tick 行程＋一筆排隊的 think」放大（只放大 procs／queue，cpu 表和出貨箱照樣本），量 kernel 真的在用的 `aos_home.write_state` 的**牆鐘**時間（單線程、沒 fsync，約等於 CPU）。是序列化樣本估算，不是各種 cpu 數下的完整帳本：

| agent 數 | 帳本 | 存一次 | 讀一次 |
|---|---|---|---|
| 100 | 129 KB | 2.6 ms | 0.35 ms |
| 300 | 328 KB | 6.2 ms | 0.93 ms |
| 1000 | 1023 KB | **18.5 ms** | 3.0 ms |
| 3000 | 3010 KB | 54 ms | 9.3 ms |

**proto5 的 kernel 每收一則回音存一次、每出一則 ack 存一次、每派一件存一次**（`collect`、`flush_outboxes`、`dispatch` 裡各一個 `save()`），
所以**反覆空轉的邊際成本**＝一次 agent tick 存三次整份帳本。對得上 B：300／300 一格處理約 300 則 → 300×3×6.2 ms≈5.6 s，量到約 6.5 s。
一張有 id 的 once（think 或工具）整個生命週期則是**六次**：收 add、刪 add 原單、派工、收結果、出 cpu ack、出回音給送件者；每格另有幾次固定的存檔。

## D. 「喚醒員」掃一輪多久（[exp/d_peek.py](exp/d_peek.py)）

同一支 Python 裡對 B 留下的 300 個家「偷看」：讀 `state.json`、在途的 call 查 K 兩個檔、idle 的列 input 資料夾、看 `paused`。
**每個 agent 19 µs**，1000 個約 19 ms。列一次 `K/responses/` 約 3 µs（**空資料夾**；回音多時還要列舉、對名字）。對照：起一次 agent tick 約 40 ms，差兩千倍。
**這支 `peek` 只拿來量成本，不能直接當「該不該叫醒」**：`sent=false` 還沒送完、全部 done 但還沒 ack、全部 ack 但還沒結清，它都會回「不用」（審查第 13 條）。

## E. 換算到 1000 個 agent、3 顆 llm cpu

公式（從 B、C 來）：kernel 每格 CPU ≈ 40 ms＋E×3×存帳本（1000 agent 時 18.5 ms）；E＝這格收／派的 agent tick 數＝min(default cpu 數, agent 數÷2)
（`interval_ms`＝1000 時同一個 agent 通常隔兩格再派；一格收回音就花超過 1 秒時，早收的那幾個當格就能再派，E 會往 cpu 數靠）；
一格長度≈1 s＋kernel CPU；每個 agent 多久被看一次≈(1000÷E)×一格長度。（astra 照這公式重算過前三列，數字對得上。）

| | E | 一格 | 每個 agent 多久被看一次 | 空轉吃掉 |
|---|---|---|---|---|
| proto5，default 16 顆 | 16 | 1.9 s | **約 2 分鐘** | kernel 0.48 核＋agent 0.3 核 |
| proto5，default 100 顆 | 100 | 6.6 s | **約 66 秒** | kernel 0.85 核＋agent 0.6 核＋輪詢 0.2 核 |
| proto5，default 1000 顆 | 500～1000 | 29～57 s | **約 1 分鐘**（kernel 本身的下限≈3×18.5 ms×1000≈56 s） | kernel 近 1 核＋agent 約 0.7 核＋輪詢 1.9 核 |

default 少於 16 顆會更慢（每格派得更少）。所以 proto5 在 1000 個 agent 時，**開 16 顆以上 cpu，每個 agent 大約一到兩分鐘才被看一次**。

**proto5-2 沒實作、沒量**。它規範「每格最多存 4 次帳本」（1000 agent 約 74 ms），但每則事件另有幾個小檔的讀寫，耗時沒量過，所以格長只能假設。
下表把格長當**假設**（1.2 秒與 2 秒兩種），只算 agent 這邊的空轉（每次 40 ms，實驗 A／B）：

| proto5-2，假設 | default 100 顆 | default 500 顆 |
|---|---|---|
| 一格 1.2 秒 | 每 12 秒看一次；空轉約 3.3 CPU 秒／秒 | 每 2.4 秒看一次；空轉約 **17 CPU 秒／秒**（比 16 執行緒還多，實際會被機器卡住） |
| 一格 2 秒 | 每 20 秒看一次；約 2 CPU 秒／秒 | 每 4 秒看一次；約 10 CPU 秒／秒 |

意思是：proto5-2 拿掉 kernel 那道牆之後，空轉就變成「花一大堆 CPU」或「醒得慢」二選一。
