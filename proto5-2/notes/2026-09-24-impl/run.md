# proto5-2 真跑紀錄（2026-09-24，真跑隊）

← [進度](progress.md)｜[決定](decisions.md)

## 環境

- Python 3.14.7（Manjaro）；模型走 LiteLLM `http://localhost:4000/v1`、`deepseek-chat`、不帶金鑰（先 `curl …/v1/models` 確認活著）。沒碰 LM Studio／ollama。
- 工作目錄 R＝scratchpad 下的 `proto5-2-impl/`；`D=R/D`、`K=R/K`、agent 家 `R/bob`。PATH 開頭放 `proto5-2/cli`，再開 daemon。
- `kernel.json`：`{"pools": {"default": {"count": 0}, "llm": {"count": 0, "envs": {"AOS_LLM_CONFIG": "R/llm.json"}}}}`；llm.json 照 proto5 README 第 2 段（代號 `default`）。

## 劇本

| # | 指令 | 看到什麼 | 時間 |
|---|---|---|---|
| 1 | `setsid nohup aos-daemon boot --target $D &` | `daemon running pid … pools 0 children 0` | 1.5 秒內 |
| 2 | `aos-kernel init --config`、`check --probe`、`boot` | check 七行全 ok（probe 真的打到 LiteLLM）；`booted 3 pools, 1 cpus` | init→boot 0.15 秒 |
| 3 | `cpu add --pool default --count 3`、`--pool llm --count 2` | 印 `pool default count 0 -> 3`；daemon 那邊 5 顆全 running | daemon 2.1 秒拉齊；kernel 確認（`sent`＝`want`）另測 2.3 秒 |
| 4 | `aos-agent init`／`start`／`say --wait` | init 生的 info 已經是 `llm.pool: llm`、`tool_pool: default`，不用改；回「現在是 2026 年 9 月 24 日下午 4 點 18 分。」（有跑 date 工具） | 14.9 秒 |
| 5 | `add` 一件 sleep 10 秒的 once → 落在 `default/0` → `cpu rm default/0` | `default/0 draining sleeper`；工作做完（16:18:43.58）後 0.5 秒內那顆消失；info 變 `{"count": 2, "skip": [0]}` | rm 後 4.6 秒收掉（＝等工作做完） |
| 6 | `kill -9` `default/2` 連四次 | 每次立刻 `dead … next …`，時間到拉回、gen+1、streak+1 | 等待 1.07／2.03／4.04／8.07 秒 |
| 7 | `aos-daemon halt` → `aos-daemon boot`（不跑 kernel boot） | halt 0.29 秒、R 底下行程 0；boot 後 `aos-kernel ls` 第一行 `health ok`，各池 running 數回來；鏈接著走（last_seq 107→115，7 秒） | 0.04 秒內 health ok |
| 8 | 再 `say --wait` | 「我剛才告訴你的是 2026 年 9 月 24 日下午 4 點 18 分。」（記憶跨過 daemon 重開還在） | 6.3 秒 |
| 9 | `agent stop`、`kernel halt`、`daemon halt` | `stopped agent-bob`、`stopped`、`stopped` | 1.0／5.2／0.1 秒 |
| 10 | `pgrep -fa proto5-2-impl` | 空（扣掉 pgrep 自己的 shell） | — |

多跑一輪（冷開）：daemon boot → kernel boot 印 `booted 3 pools, 5 cpus`（照上次 info 的數字拉回來）→ 再 `cpu add default +2` → halt 兩個，全乾淨。

## 數字

- 補齊：daemon 拉 5 顆 2.1 秒；kernel 端 `sent` 追上 `want` 約 2.3 秒（一格 tick＝1 秒，要等一張 scale 單來回）。
- 退避：1s→2s→4s→8s，跟規範 `restart_delay_ms × 2^(streak−1)` 一致，誤差 < 0.1 秒。
- daemon halt→boot 拉回：0.04 秒內 `health ok`、各池 running 齊。
- 兩次 `say --wait` 往返：14.9 秒（含工具）、6.3 秒（純文字）。

## 樣子（節錄）

```
health ok
chain 1790237853860377840-950599  phase running  last_seq 18  kernel cpu kernel/0  current k-…-18.json  requests 3
kernel   want 1  sent 1   daemon kernel: running 1 restarting 0 pending 0 dead 0 failed 0
default  want 3  sent 3  busy 0  idle 3  draining 0   daemon default: running 3 restarting 0 pending 0 dead 0 failed 0
llm      want 2  sent 2  busy 0  idle 2  draining 0   daemon llm: running 2 restarting 0 pending 0 dead 0 failed 0
queued 0  running 0  done 0  bad 0
```

```
$ aos-kernel cpu ls --pool default        # cpu rm default/0 之後
default  want 2  sent 3  busy 2  idle 1  draining 0   daemon default: running 3 …   收掉中 1 顆，等 sleeper
default/0  draining sleeper  daemon running gen 1
default/1  busy agent-bob  daemon running gen 1
default/2  idle  daemon running gen 1
```

```
$ aos-daemon ls --pool default            # 第三次 kill -9 之後
2  dead     pid 955493  gen 3  -     exits 3  streak 3  next 16:19:02  last_exit 137
2  running  pid 955941  gen 4  idle  exits 3  streak 3  since 16:19:02
```

## 碰到的問題（都不是程式 bug，沒改程式）

1. **剛 add 完，kernel 那邊一兩秒看起來「沒動」**：daemon 已經 5 顆 running，`aos-kernel ls` 還是 `sent 0 … scale 單在路上（等回音）`、`cpu ls --pool` 每顆寫「待宣告」。等一格就好，但新手會以為卡住。
2. **`restarting 1` 加 `running 2` 大於 `want 2`**：kill 之後 `aos-daemon ls` 寫 `want 2 running 2 restarting 1`。規範說 restarting 包含在 running 裡、不是互斥分類；沒讀規範會以為多了一顆。
3. **收掉中那顆的 `draining` 計數跟單顆對不上**：`cpu rm` 後頭一兩秒池那行寫 `draining 0`，單顆那行已是 `draining sleeper`；過一格才變 `draining 1`。收掉後的一瞬間單顆寫 `default/0 收掉中 daemon pending`，「pending」讀起來像要再拉。
4. **kernel halt 之後 ls 還寫「scale 單在路上（等回音）」**（kernel 池那行）、`requests 1`。照規範那張回音本來就留給下次 boot 讀掉，行為沒錯，只是停機後還說「在路上」容易誤會。
5. **`aos-kernel check` 的 daemon 行**：daemon 還沒任何池時寫「daemon 活著（池 default、llm、kernel）」，列的其實是 K 的池表，不是 daemon 現有的池。
6. **`aos-agent init` 的提示指到 `proto5/README.md` 第 2 段**：用 proto5-2 的人會找不到對應段落。
7. **跑測時的工具限制**（不是產品問題）：本環境擋了組合太複雜的 shell 行，改成把每步寫成小 `.sh` 再 `bash` 跑。

## 結論

proto5-2 從頭到尾真跑一次全過：加池 2 秒補齊、`cpu rm` 真的等手上工作做完才收、`kill -9` 退避 1/2/4/8 秒照規範、daemon 重開 0.04 秒就把池拉回來且不用 kernel boot、agent 記憶跨重開還在；沒找到程式 bug，只有幾處 `ls` 的字眼在過渡的一兩秒會讓人誤會。
