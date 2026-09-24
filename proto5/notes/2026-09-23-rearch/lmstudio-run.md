# T3：LM Studio 真模型跑新架構一條龍（2026-09-24）

結論：**通**。daemon → kernel（`k`／`0`／`llm` 三顆 cpu）→ `llm` cpu 跑 `llm-call` 打本機 LM Studio，once 出貨、反覆行程 done、先 kernel 後 daemon 停機，連跑兩次都綠，跑完 pgrep 空。程式、規範都沒改。

## ① 模型

`google/gemma-4-e4b`（lms 標 7.5B、6.33 GB，三顆聊天模型裡最小）。端點 `http://localhost:1234/v1`。
它會先「想」（回 `reasoning_content`），`max_tokens` 太小（256）時 `content` 是空字串——`llm-call` 預設 2048。

## ② 指令（可複製重跑）

```sh
lms server start            # 已開可略
lms load google/gemma-4-e4b -y
proto5/notes/2026-09-23-rearch/lmstudio/run.sh /tmp/…/scratchpad/t3   # 第二次原樣再跑一次
```

`run.sh` 做的事（檔在 [lmstudio/](lmstudio/)）：
1. `aos-daemon --home D` 背景起（`setsid`），等 `D/state.json` 的 pid 對上。
2. 第一次：`aos-kernel init K`，再用 [kernel-info.template.json](lmstudio/kernel-info.template.json) 覆寫 `K/info.json`（`llm` 池的 `envs` 把 `llm-call` 那層放進 PATH、帶 `LLM_BASE`／`LLM_MODEL`；`tick_ms` 200）。之後沿用。
3. `aos-kernel boot K --daemon D`，等 `last_seq ≥ 1`，`aos-kernel ls K`。
4. once：工作 inst `{"argv":["llm-call"],"stdin":question.txt,"stdout":answer-*.json,"stderr":…err}`，
   `aos-kernel add K ask.json --once --pool llm --timeout-ms 180000 --wait-ms 200000`，讀 answer 檔。
5. 反覆：`sh -c` 計數、第 3 次 `exit 100`；先 `aos-kernel rm K repeat`（重跑時上一輪的 done 紀錄還在），再 `add --name repeat --interval-ms 2000`，等 `status=done`。
6. `aos-kernel stop K` → 等 `phase=stopped` 且 `D/state.json` 的 `children={}` → 往 `D/requests/` 放 `stop`（tmp＋link）→ `wait` daemon 退 0。
7. pgrep 檢查（見 ⑤ 第 6 條）。

## ③ 回音原文

```text
$ aos-kernel add K work/ask.json --once --pool llm --timeout-ms 180000 --wait-ms 200000
{"code": 0, "kind": "child", "timed_out": false, "stopped": false, "ms": 5960}
$ cat work/answer-1790212622.json          # reasoning_content 截掉
{"role": "assistant", "content": "行程是指一個正在運行的程式實例（或稱程序），它是作業系統進行資源分配與執行的基本單位。",
 "reasoning_content": "Here's a thinking process …", "tool_calls": []}
# 帳本 procs.repeat
{"once": false, "pool": "default", "interval_ms": 2000, "status": "done", "runs": 3, "fails": 0, "pending": null, …}
# 額外試：--timeout-ms 300
{"code": 143, "kind": "child", "timed_out": true, "stopped": false, "ms": 320}
```

## ④ 時間

| | 第一次 | 第二次（boot 接手） |
|---|---|---|
| once 放單→回音 | 6.12 s（cpu 記 5960 ms） | 5.64 s（5438 ms） |
| 整條龍（起 daemon→停完） | 12.46 s | 11.94 s |
| 停機（kernel stop→daemon 退） | 0.29 s | 0.28 s |

once 的時間幾乎全是模型；排程加的延遲在 tick_ms 200 下約 0.2 s。反覆行程三次約 4 s（interval 2000）。

## ⑤ 撞到的問題

1. **daemon 沒有停機的 CLI**：`aos-daemon-ctl` 刪了之後，停 daemon 只能手放 `stop` 檔（tmp＋link）或 `kill -TERM` 它的 pid。規範 `spec/kernel.md:327-328` 叫人「才去停 daemon」，`spec/daemon.md:140` 只有 method；`cli/aos-daemon` 只會跑。
2. **`aos-kernel` 沒有 `ack` 子命令**：`--once` 不等時，`spec/kernel.md:323` 說「自己去讀、自己 ack」，但只能手刻 `ack-*.json`（我試過一次，能用）。不 ack 回音就一直留在 `K/responses/`。
3. **init 之後改 cpu 表只能手編 info.json**：`init` 固定寫 `k＋0、1、2`（`lib/aos_kernel.py:98`、`spec/kernel.md:290`），要 `llm` 池／envs 沒有旗標。`envs` 又只在第一次建 cpu 家時抄一次（`spec/kernel.md:102,117-119`），所以 `run.sh` 的 `MODEL=` 只有第一次有效，之後換模型要 stop→改 `K/cpus/llm/inst.json`→boot。
4. **`kernel.log` 空格也寫**：`lib/aos_kernel.py:446-447` 每格都 append（`"events": []` 也寫）。tick_ms 1000 一天約 8.6 萬行、200 就 43 萬行，沒有輪替。規範 `spec/kernel.md:245` 只說「每格 append」。
5. **沒有 help**：`aos-kernel -h`／`add -h` 只回 `Usage: the following arguments are required…`，看不到有哪些子命令（`lib/aos_kernel.py:537-538` 的 `add_help=False`）。`ls` 印的是一整行原始 JSON（含每顆 cpu 的絕對路徑），不像 `spec/kernel.md:330` 講的「摘要」，要自己用 python 挖欄位。
6. **全域 pgrep 會撈到別人**：這台同時有別的 session 在跑 proto5 測試，`pgrep -fa 'aos-cpu|…'` 第一次撈到對方的 `zsh -c` 命令列。`run.sh` 改成去掉 shell 行、只認含本次 T3 路徑的才算殘留。兩次跑完兩種都空。
7. （小）反覆行程 done 之後永遠留在帳本，同名重加是 `AlreadyExists`；重跑得先 `rm`。照規範是對的，只是重跑腳本要記得。
8. （小）bad pool：`aos-kernel: FieldTypeMismatch: pool 必須是現有的工作池`、退 1，看得懂。立刻 `ls K/responses` 還看得到那則回音，稍後就被 ack 掉了（非 bug，是 ack 要等下一格）。

## ⑥ 要使用者拍板的

1. daemon 要不要補一個停機的 CLI（例如 `aos-daemon stop [--home D]`），還是維持「手放檔／kill」？
2. `aos-kernel` 要不要補 `ack`（給 once 不等的交件者），以及 `init` 要不要能帶 cpu 表（至少能加一顆 `llm` 池）？
3. `kernel.log` 空格要不要不寫、或要不要輪替？
