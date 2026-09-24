← [教程索引](README.md)｜上一篇 [04b 權限牆與工具管理](04b-access-and-tool-admin.md)

# 05 管一大堆 agent

**目標**：好幾個 agent 共用一個 kernel：cpu 開幾顆、`cpu add／rm／ls` 加減、一次操作一批、`aos-kernel ls` 看全局、共用的模型設定壞了一次救回來。

**前提**：做完 [01](01-daemon-kernel.md)、[03](03-first-agent.md)；kernel 開著、`health ok`。新終端先 `. $HOME/aos-try/env.sh`。
批次操作就是 shell 的 `for` 迴圈。

## 1. cpu 要開幾顆、怎麼加減

每個 agent 每走一格都要佔一顆 `default` 池的 cpu 一下，它叫的工具也在 `default` 池跑；問模型則全排到 `llm` 池。
**經驗值：`default` 池的 cpu 數 ≥ agent 數**，工具多、工具慢的再多開；`llm` 池一顆就夠（它一次只問一件，agent 多了問模型會排隊，要更快就多開幾顆）。

加 cpu 就是改池的數字，**不用 halt、不用 boot**，下一格就拉起來：

```sh
aos-kernel cpu add --pool default --count 4
aos-kernel cpu add --pool llm --count 1
sleep 3
aos-kernel cpu ls
```

兩行 `add` 各印 `pool default count 2 -> 6`、`pool llm count 1 -> 2`。`cpu ls` 一池一行：

```text
kernel   want 1  sent 1   daemon kernel: running 1 pending 0 dead 0 failed 0
default  want 6  sent 6  busy 1  idle 5  draining 0   daemon default: running 6 pending 0 dead 0 failed 0
llm      want 2  sent 2  busy 0  idle 2  draining 0   daemon llm: running 2 pending 0 dead 0 failed 0
```

**剛 `add` 完一兩秒內，`sent` 還是舊數字、池那行後面可能寫「宣告已送出，下一格確認」，這是正常的**：kernel 一格才收一次 daemon 的回音，等一兩秒就追上 `want`。
`cpu ls --pool default` 一顆一行（`default/0  busy agent-bob  daemon running gen 1`：第 0 號、在跑誰、daemon 那邊活著、第幾任）。

收 cpu 有兩種，**都是手上工作做完才真的收**（沒有「馬上砍」）：

```sh
aos-kernel cpu rm default/2                  # 讓 2 號永久退休，其他號不動
aos-kernel cpu rm --pool default --count 1   # 收最大的 1 號
```

各印 `pool default count 6 -> 5`、`pool default count 5 -> 4`。過一格 `cpu ls --pool default` 會看到要收的那兩顆寫 `收掉中`，做完就從表上消失，剩 `0`、`1`、`3`、`4`。
退休的號記在 `K/info.json` 那池的 `skip`（`{"count": 4, "skip": [2]}`），以後長大也不會再用它；要讓它回來得手改 info 把 2 拿掉。

- 開一個新池：`aos-kernel cpu add --pool gpu --count 2 --env KEY=VALUE`（`--env` 只有新池收）。已經在的池要改環境，直接編 `K/info.json` 那池的 `envs`（改完只影響之後才拉起來的 cpu；要全換 `aos-daemon kill --pool <池> --all`）。
- daemon 那邊自己看：`aos-daemon ls`（每池一行）、`aos-daemon ls --pool default`（一顆一行：pid、第幾任、死過幾次）。
- `aos-daemon scale` 碰 kernel 的池會被拒（`Owned: … 請改用 aos-kernel cpu add／rm`），照它說的做；`--force` 只給救急。

## 2. 一次生一批、各給人格

```sh
for a in alice carol dave; do aos-agent init --target $W/$a; done
echo '{"content": "你是圖書館員，回答簡短，每次結尾附一句五言詩。"}' > $W/alice/prompts/system.json
echo '{"content": "你是會計師，回答只有數字。"}'                        > $W/carol/prompts/system.json
echo '{"content": "你是海盜船長，口氣粗魯，回答一句話。"}'              > $W/dave/prompts/system.json
for a in alice carol dave; do echo "== $a"; aos-agent check --target $W/$a | grep -v '^ok'; done
for a in alice carol dave; do aos-agent start --target $W/$a; done
```

`check` 那行只印不是 `ok` 的：每個剩 `warn access`（工具沒關牢，見 [04b](04b-access-and-tool-admin.md)）和「設定檢查通過；…」就是全過。
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
輪到 carol 時她的回話可能早就到了，於是白等到逾時。已經說完了才想看，用 `listen --last`（最後一則）：

```sh
for a in alice carol dave; do echo "== $a"; aos-agent listen --target $W/$a --last; done
```

## 4. 看全局

一個一個看第一行：

```sh
for a in alice carol dave; do echo "$a: $(aos-agent status --target $W/$a | head -1)"; done
```

一次看全部（kernel、每個池、每個 agent 的反覆工作）：

```sh
aos-kernel ls --procs
```

```text
health ok
kernel  running  seq 99  daemon alive  tick 1000ms
  kcpu kernel/0  正在跑一格  requests 2
pool    2 個工作池：要 6 顆、忙 2、閒 4
  kernel   want 1  sent 1   daemon kernel: running 1 pending 0 dead 0 failed 0
  default  want 4  sent 4  busy 2  idle 2  draining 0   daemon default: running 4 pending 0 dead 0 failed 0
  llm      want 2  sent 2  busy 0  idle 2  draining 0   daemon llm: running 2 pending 0 dead 0 failed 0
proc    4 個（反覆 4、once 0）：queued 2、running 2
  行程         種類  狀態     runs  fails  回音  備註
  agent-alice  反覆  running     2      0  -
  agent-carol  反覆  queued      2      0  -
  agent-dave   反覆  running     1      0  -
  agent-bob    反覆  queued      1      0  -
queue   2：agent-carol agent-bob
```

（bob 是 03、04 留下來的，有 `start` 才會出現。）
不帶 `--procs` 時行程表只列出事的（`bad`、暫停、重試中），其餘只寫「其餘 N 個沒事的沒列」——agent 一多，平常就看這個短的。`--pool default` 只看那池，一顆一行。

`queue` 裡的是在等下一次輪到它（每格隔 1 秒，本來就會排一下）；一直很長、池那行 `idle` 老是 0 才是該加 cpu。

## 5. health 怎麼讀

`aos-kernel ls` 第一行先講 **kernel 自己**，由重到輕：`K 家缺目錄`、`停機中`、`daemon 沒在跑`、`kernel cpu 不在`、`tick 停住`、`池 P：池不見了`（或池出錯）、`搬池中`、`池 P 少 N 顆（daemon 在補…）`。
kernel 沒事時才講 **agent**，這三個階段依序出現：

| 第一行 | 意思 | 要做什麼 |
|---|---|---|
| `重試中：agent-bob（連敗 1/3）` | 問模型失敗了 1、2 次，還會自己再試 | 先別動；原因沒好第 3 次就暫停 |
| `agent 暫停中：agent-alice（連敗）、agent-bob（手動）（… aos-agent continue --all）` | 有人停手了：連敗暫停或手動 `pause` | 修好原因，`continue`（一個）或 `continue --all`（全部） |
| `已解除暫停，等下一次成功：agent-bob` | 剛 `continue`，還沒問成功過 | 等；下一次問成功就變 `ok` |

行程表的「備註」欄也標同樣的字（`連敗暫停中`、`手動暫停中`、`重試中（連敗 N/3）`、`已解除暫停，等下一次成功`）。

## 6. 共用的模型設定壞了：一次救全部

`llm.json` 是所有 agent 共用的，一壞就是一片：

```sh
sed -i 's/4000/4999/' $W/llm.json
for a in alice carol dave; do aos-agent say "還在嗎？" --target $W/$a; done
sleep 25
aos-kernel ls | head -1
```

你會看到 `health agent 暫停中：agent-alice（連敗）、…（修好原因後 aos-agent continue --all）`。修好再一次解開：

```sh
sed -i 's/4999/4000/' $W/llm.json
aos-agent continue --all
```

```text
agent-bob  /home/you/aos-try/bob  沒在暫停
agent-alice  /home/you/aos-try/alice  解除連敗暫停（等下一次成功）
…（carol、dave 同上）
continued 3／4
```

它看的是 kernel 帳本裡登記的所有 agent。過幾秒用 `listen --last` 就看得到各自的回話。

## 7. 一次撤掉一批

```sh
for a in alice carol dave bob; do aos-agent stop --target $W/$a; done
```

各印 `stopped agent-…`。全部撤完再照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關 kernel、daemon。
每天開機就是 [01 第 8 步](01-daemon-kernel.md#8-每天重開機)之後 `for` 迴圈 `aos-agent start` 每一個（已登記的印 `already started`、退 0）。

## 底下在幹嘛

- 每個 agent 在 kernel 眼裡都只是一份叫 `agent-<資料夾名>` 的反覆工作，跟 [02](02-kernel-jobs.md) 的 `count` 沒兩樣；kernel 不知道誰是 agent。（[登記](../spec/aos-agent/register.md)）
- 同池的工作誰先誰後就是一條佇列，cpu 閒了就拿下一個輪得到的。agent 多、cpu 少，只會變慢，不會出錯。（[一格做什麼](../spec/kernel/tick.md)）
- 不同 agent 家之間完全獨立，一個壞了不影響別人——除了共用的 `llm.json`、cpu、daemon。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| 回話越來越慢、`ls` 池那行 `idle 0`、`queue` 很長 | cpu 不夠，照第 1 步 `cpu add` |
| 過了好幾秒 `sent` 還沒追上 `want` | kernel 沒在跑（`ls` 第一行不是 `ok`，照括號做），或手改的 `K/info.json` 壞了（`aos-kernel check` 會指出） |
| `cpu add --pool llm --env …` 印 `PoolExists` | `--env` 只給新池；既有池改環境請直接編 `K/info.json` |
| `health 池 default 少 1 顆（daemon 在補…）` | 有 cpu 死了、daemon 正在重拉。一直不好就看 `aos-daemon ls --pool default` 與那顆家裡的 `cpu.log` |

上千、上萬顆時哪些操作還是會變慢，見 [規模](../spec/kernel/scale.md)。
