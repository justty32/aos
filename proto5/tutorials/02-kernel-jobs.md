← [教程索引](README.md)｜上一篇 [01 daemon 和 kernel](01-daemon-kernel.md)｜下一篇 [03 第一個 agent](03-first-agent.md)

# 02 用 kernel 跑工作：一次性與反覆

**目標**：不碰 agent，直接叫 kernel 跑程式——跑一次就好的（once）、隔一陣子跑一次直到做完的（反覆），
還有一直失敗會怎樣、怎麼撤掉。看懂這些，後面的 agent 就只是「一份反覆工作」而已。

**前提**：做完 [01](01-daemon-kernel.md) 第 1～6 步，kernel 開著、`aos-kernel ls` 第一行 `health ok`。新終端先 `. $HOME/aos-try/env.sh`。

## 1. 工作單長什麼樣

要 kernel 跑的東西寫成一份 **inst.json**：就是「叫作業系統跑一個程式」那句話的 JSON 版。`argv` 跑什麼，
`stdout`／`stderr` 接到哪個檔（相對這份 json 所在的資料夾），沒有 shell、沒有管線。

```sh
mkdir -p $W/jobs
cat > $W/jobs/hello.json <<'EOF'
{"argv": ["date", "+%H:%M:%S"], "stdout": "hello.out"}
EOF
```

## 2. 跑一次，等它跑完

```sh
aos-kernel add $W/jobs/hello.json --once --wait-ms 10000
cat $W/jobs/hello.out
```

你會看到（約 1～2 秒）：

```text
{"code": 0, "kind": "child", "timed_out": false, "stopped": false, "ms": 200}
17:59:34
```

**第一行是「執行狀態」，不含程式的輸出**：`date` 印的東西在 inst 指的 `hello.out` 裡。
**指令退 0 ≠ 工作成功**：退 0 只代表 kernel 收了單、回了音；工作本身成不成看 `kind`、`code`、`timed_out`、`stopped`。
例如 `argv` 寫一個不存在的程式，指令照樣退 0，回音是 `"code": 127`。

## 3. 跑一次，不等

```sh
aos-kernel add $W/jobs/hello.json --once
```

你會看到單名和回音會出現的位置，指令馬上退 0：

```text
cli-1790243975791616474-1277717.json /home/you/aos-try/K/responses/cli-1790243975791616474-1277717.json
```

過幾秒（等 kernel 走到下一格）回音就在那個檔裡（`cat` 它）。看完要替它「簽收」，不然回音一直留在 `K/responses/`：

```sh
aos-kernel ack cli-1790243975791616474-1277717.json     # 換成你看到的單名
```

帶 `--wait-ms` 等到的回音，指令已經替你簽收了。

## 4. 反覆跑，直到它自己說做完

```sh
cat > $W/jobs/count.json <<'EOF'
{"argv": ["sh", "-c", "echo tick >> count.txt; [ $(wc -l < count.txt) -lt 3 ] || exit 100"]}
EOF
aos-kernel add $W/jobs/count.json --name count --interval-ms 500
sleep 8
aos-kernel ls --procs | grep count
cat $W/jobs/count.txt
```

`add` 印 `count`（行程名）。每 0.5 秒跑一次，第 3 次退出碼 100＝「我做完了」。你會看到：

```text
  count  反覆  done     3      0  -
```

那是行程表裡的一行，欄位依序是：行程、種類、狀態、runs（跑了幾次）、fails（連續失敗幾次）、回音。
`aos-kernel ls` 預設只列出事的行程（`bad`、暫停、重試中），其他只算數量、寫一句「其餘 N 個沒事的沒列」；`--procs` 才每個都列。

`count.txt` 裡三行 `tick`。沒帶 `--interval-ms` 就用 `K/info.json` 的 `interval_ms`（預設 1000）。

## 5. 一直失敗會怎樣

```sh
cat > $W/jobs/boom.json <<'EOF'
{"argv": ["sh", "-c", "echo 壞了 >&2; exit 3"], "stderr": "boom.err"}
EOF
aos-kernel add $W/jobs/boom.json --name boom --interval-ms 200
sleep 20
aos-kernel ls | grep boom
```

連續失敗 10 次就被「退件」，不再排它。`bad` 的不用 `--procs` 也會列出來，表下另起一行告訴你去哪看：

```text
  boom   反覆  bad     10     10  -
  boom 壞了，看 /home/you/aos-try/jobs/boom.err
```

## 6. 撤掉

```sh
aos-kernel rm boom
aos-kernel rm count
```

各印一次行程名。`done`、`bad` 的行程只是留在 `ls` 給你看，`rm` 才真的從帳本拿掉；還在跑的也能 `rm`，它跑完那次的結果會被丟掉。

## 底下在幹嘛

- `aos-kernel add` 只是往 `K/requests/` 放一張單（kernel 的 syscall）。下一格 tick 讀到它，記進帳本 `K/state.json`、排進佇列。（[syscall](../spec/kernel/syscall.md)）
- 每一格，kernel 從佇列挑輪得到的工作，找一顆**同池**又閒著的 cpu（沒寫 `--pool` 就是 `default`），把單放進那顆 cpu 的 `requests/`（`K/pools/<池>/cpus/<號>/requests/`）；
  cpu 照 inst 跑一次程式、回音寫進自己的 `responses/`；下一格 kernel 收回音、判定、簽收。（[一格做什麼](../spec/kernel/tick.md)）
- **判定**（[回音怎麼判](../spec/kernel/echo.md)）：once 的回音原樣轉給當初 `add` 的人（放在 `K/responses/`）；反覆的退出碼 100＝完成，
  0 或 101（「還在等，不算錯」）算成功、失敗計數歸零；102＝「停車」，也不算錯，但下次要等 `park_ms`（預設 5 分鐘）或被叫醒（`aos-kernel wake NAME`，agent 的回音到了或有人 `say` 會自動叫）；其他非 0、逾時、跑不起來都算一次失敗，連續 10 次＝`bad`。`100` 和 `10` 在 `K/info.json` 的 `done_exit`、`bad_after` 改。
- 所以最快也要等一格（`tick_ms`，預設 1 秒）才輪得到；工作之間彼此不等，同池有幾顆閒 cpu 就能同時跑幾件。
- inst.json 還能寫 `cwd`、`envs`、`stdin`、`exit`、逾時等，見 [inst-posix 規範](../spec/inst-posix/README.md)；`add` 的全部旗標見 [kernel 命令列](../spec/kernel/cli.md)。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| 回音 `"code": 127` | `argv[0]` 找不到。它照 **daemon 開起來時的 PATH** 找，不是你現在這個終端的 |
| 找不到 `hello.out` | `stdout` 的相對路徑是相對 **inst.json 所在的資料夾**，不是你的目前資料夾 |
| `add --once` 不帶 `--wait-ms`，`K/responses/` 越堆越多 | 看完用 `aos-kernel ack <單名>` 簽收 |
| 行程一直 `queued` 不跑 | 那個池沒有 cpu（`--pool` 寫錯，或池是 0 顆），或 cpu 全忙；`aos-kernel ls` 看 `pool` 下面那池的 `idle`，不夠就 `aos-kernel cpu add`（[05](05-many-agents.md)） |
| `add` 同名被拒 | 同名行程還在（含 `done`／`bad`），先 `rm` |

## 收工

`rm` 掉自己加的行程就好；kernel 留著給 [03](03-first-agent.md) 用。今天到此為止就照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關機。
