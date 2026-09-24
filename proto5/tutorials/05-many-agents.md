← [教程索引](README.md)｜上一篇 [04 加工具、暫停](04-tools-and-pause.md)

# 05 管一大堆 agent

**目標**：好幾個 agent 共用一個 kernel：cpu 要開幾顆、一次生／登記／說話／看狀態／撤掉一批、用 `aos-kernel ls` 看全局、共用的模型設定壞了怎麼一次救回來。

**前提**：做完 [01](01-daemon-kernel.md)、[03](03-first-agent.md)；kernel 開著、`health ok`。新終端先 `. $HOME/aos-try/env.sh`。
這篇只用現在就有的指令，批次操作就是 shell 的 `for` 迴圈。

## 1. cpu 要開幾顆

每個 agent 每走一格都要佔一顆 `default` 池的 cpu 一下，它叫的工具也在 `default` 池跑；問模型則全排到 `llm` 池。
**經驗值：`default` 池的 cpu 數 ≥ agent 數**，工具多、工具慢的再多開；`llm` 池一顆就夠（它一次只問一件，agent 多了問模型會排隊，要更快就多開幾顆 `llm` 池的）。

加 cpu＝在 `K/info.json` 的 `cpus` 多寫幾顆。kernel 每格都重讀它，**不用 halt、不用 boot**，下一格就拉起來：

```sh
python3 - $AOS_KERNEL_HOME/info.json <<'EOF'
import json, os, sys
path = sys.argv[1]
info = json.load(open(path))
for name in ["2", "3", "4", "5"]:
    info["cpus"].setdefault(name, {})
json.dump(info, open(path + ".tmp", "w"), ensure_ascii=False)
os.replace(path + ".tmp", path)
EOF
sleep 3
aos-kernel ls | grep -c '^cpu'
```

<!-- TODO A隊合併後補實際輸出（aos-kernel ls 改成對齊表格；上面的 grep 也要跟著改） -->
數到 8 行 cpu（`k`、`0`～`5`、`llm`）就好了。新的一顆要加 `envs`（例如第二顆 llm cpu）就照 [01](01-daemon-kernel.md) 的 `llm` 那顆寫。
（先寫暫存檔再 `mv` 過去，是為了別讓 kernel 讀到寫到一半的檔。）

## 2. 一次生一批、各給人格

```sh
for a in alice carol dave; do aos-agent init --target $W/$a; done
echo '{"content": "你是圖書館員，回答簡短，每次結尾附一句五言詩。"}' > $W/alice/prompts/system.json
echo '{"content": "你是會計師，回答只有數字。"}'                        > $W/carol/prompts/system.json
echo '{"content": "你是海盜船長，口氣粗魯，回答一句話。"}'              > $W/dave/prompts/system.json
for a in alice carol dave; do echo "== $a"; aos-agent check --target $W/$a | grep -v '^ok'; done
for a in alice carol dave; do aos-agent start --target $W/$a; done
```

`check` 那行只印不是 `ok` 的，什麼都沒印就是全過。<!-- TODO A隊合併後補實際輸出（aos-agent check 新指令） -->
`start` 各印 `started agent-alice` 等。要各自不同的工具，就照 [04](04-tools-and-pause.md) 放進各自的 `tools/`。

## 3. 一次對一批說話、收回話

同時問、同時等：每個 `say --wait` 放背景，回話各寫進一個檔，`wait` 等全部回來再印：

```sh
for a in alice carol dave; do
  aos-agent say "用一句話自我介紹。" --target $W/$a --wait 120 > $W/$a.reply 2>&1 &
done
wait
for a in alice carol dave; do echo "== $a"; cat $W/$a.reply; done
```

你會看到（約 10～20 秒，內容看模型）：

```text
== alice
我是圖書館員，為你找書、指路、解疑惑。

書海無涯勤作舟。
== carol
我是會計師。
== dave
哼！老子是這片海上最兇的船長，少廢話！
```

**別寫成「先全部 `say`，再一個個 `listen --wait`」**：`listen --wait` 只等**下一則新的**回話，
輪到 carol 時她的回話可能早就到了，於是白等到逾時。已經說完了才想看，用 `listen`（最後一則）：

```sh
for a in alice carol dave; do echo "== $a"; aos-agent listen --target $W/$a; done
```

## 4. 看全局

一個一個看第一行：

```sh
for a in alice carol dave; do echo "$a: $(aos-agent status --target $W/$a | head -1)"; done
```

一次看全部（kernel、每顆 cpu、每個 agent 的反覆工作）：

```sh
aos-kernel ls
```

<!-- TODO A隊合併後補實際輸出（aos-kernel ls 改成對齊表格） -->
```text
health ok
…
cpu 0  pool default  busy agent-alice (k-…-11-0.json)  running
cpu 1  pool default  busy agent-dave (k-…-11-1.json)  running
cpu 2  pool default  busy agent-bob (k-…-11-2.json)  running
cpu 3  pool default  busy agent-carol (k-…-11-3.json)  running
…
proc agent-alice  repeat  running  runs 119  fails 0  pending -
proc agent-carol  repeat  queued  runs 119  fails 0  pending -
queue agent-carol
```

`queue` 裡的是在等下一次輪到它（每格之間隔 1 秒，本來就會排一下），不一定是 cpu 不夠；`queue` 一直很長、cpu 行全是 `busy` 才是該加 cpu。

## 5. health 怎麼讀

`aos-kernel ls` 第一行先講 **kernel 自己**，由重到輕：`K 家缺目錄`、`停機中`、`daemon 沒在跑`、`cpu missing`、`恢復中（… cpu dead，daemon 重拉中）`、`tick 停住`。
kernel 沒事時才講 **agent**，這三個階段依序出現：

| 第一行 | 意思 | 要做什麼 |
|---|---|---|
| `重試中：agent-bob（連敗 1/3）` | 問模型失敗了 1、2 次，還會自己再試 | 先別動；原因沒好第 3 次就暫停 |
| `agent 暫停中：agent-alice（連敗）、agent-bob（手動）（… aos-agent continue --all）` | 有人停手了：連敗暫停或手動 `pause` | 修好原因，`continue`（一個）或 `continue --all`（全部） |
| `已解除暫停，等下一次成功：agent-bob` | 剛 `continue`，還沒問成功過 | 等；下一次問成功就變 `ok` |

每個 agent 那行 `proc agent-…` 的尾巴也標同樣的字（`連敗暫停中`、`手動暫停中`、`重試中（連敗 N/3）`）。

## 6. 共用的模型設定壞了：一次救全部

`llm.json` 是所有 agent 共用的，一壞就是一片：

```sh
sed -i 's/4000/4999/' $W/llm.json
for a in alice carol dave; do aos-agent say "還在嗎？" --target $W/$a; done
sleep 25
aos-kernel ls | head -1
```

你會看到 `health agent 暫停中：agent-alice（連敗）、agent-carol（連敗）、agent-dave（連敗）（修好原因後 aos-agent continue --all）`。修好再一次解開：

```sh
sed -i 's/4999/4000/' $W/llm.json
aos-agent continue --all
```

```text
agent-bob  /home/you/aos-try/bob  沒在暫停
agent-alice  /home/you/aos-try/alice  解除連敗暫停（等下一次成功）
agent-carol  /home/you/aos-try/carol  解除連敗暫停（等下一次成功）
agent-dave  /home/you/aos-try/dave  解除連敗暫停（等下一次成功）
continued 3／4
```

它看的是 kernel 帳本裡登記的所有 agent（用 `AOS_KERNEL_HOME` 找）。過幾秒 `for a in …; do aos-agent listen …; done` 就看得到各自的回話。

## 7. 一次撤掉一批

```sh
for a in alice carol dave bob; do aos-agent stop --target $W/$a; done
```

各印 `stopped agent-…`。全部撤完再照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關 kernel、daemon。
每天開機就是 [01 第 8 步](01-daemon-kernel.md#8-每天重開機)之後 `for a in …; do aos-agent start --target $W/$a; done`（已登記的印 `already started`、退 0）。

## 底下在幹嘛

- 每個 agent 在 kernel 眼裡都只是一份叫 `agent-<資料夾名>` 的反覆工作，跟 [02](02-kernel-jobs.md) 的 `count` 沒兩樣；kernel 不知道誰是 agent。（[登記](../spec/aos-agent/register.md)）
- 同池的工作誰先誰後就是一條佇列，cpu 閒了就拿下一個輪得到的。agent 多、cpu 少，只會變慢，不會出錯。（[一格做什麼](../spec/kernel/tick.md)）
- 同一個家只能有一個 tick 在做事（有鎖）；不同家之間完全獨立，一個壞了不影響別人——除了它們共用的東西：`llm.json`、cpu、daemon。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| 回話越來越慢、`ls` 的 cpu 全 `busy`、`queue` 很長 | cpu 不夠，照第 1 步加 |
| `continue --all` 說 `沒在暫停` | 那個本來就好好的，不用管 |
| 第 1 步之後 `ls` 沒多出 cpu | `K/info.json` 改壞了：`aos-kernel check` 的 `info` 行會指出哪裡錯 |

上千顆 cpu、很多個池的管理（按池宣告「要幾顆」）是下一版的事，見 [proto5-2](../../proto5-2/README.md)。
