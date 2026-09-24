← [教程索引](README.md)｜上一篇 [02 用 kernel 跑工作](02-kernel-jobs.md)｜下一篇 [04 加工具、暫停](04-tools-and-pause.md)

# 03 從零開始第一個 agent，以及關掉它

**目標**：生一個 agent 的家、檢查、登記給 kernel、跟它說話、看回話、看它現在怎樣，最後撤掉。

**前提**：做完 [01](01-daemon-kernel.md)，kernel 開著、`health ok`；`llm.json` 裡有代號 `default`。新終端先 `. $HOME/aos-try/env.sh`。

## 1. 生一個家

```sh
aos-agent init --target $W/bob
```

你會看到 `initialized /home/you/aos-try/bob`，外加一行提醒：它的模型寫的是**代號** `default`，要在 `llm.json` 裡有（01 已經寫了）。
家裡長這樣：

| 東西 | 是什麼 |
|---|---|
| `info.json` | 設定：模型代號、工具在哪、多久走一格 |
| `prompts/system.json` | 人格：`{"content": "你是繁體中文助理，回答簡短。…"}`，想改就改 |
| `tools/date.json` | 一個現成的工具：查現在時間 |
| `input/` | 別人對它說的話，一則一個檔（用 `say` 投就不用管格式） |
| `state.json`、`log/` | 程式自己的進度與錯誤紀錄；出事看 `log/agent.err`、`log/llm.err` |

`--target` 省略＝目前資料夾，所以 `cd $W/bob` 之後下面的指令都能不寫 `--target`。

## 2. 檢查

```sh
aos-agent check --target $W/bob --probe
```

你會看到（先把 kernel 整段查一遍，再查這個家）：

```text
ok   kernel: K＝/home/you/aos-try/K（取自 AOS_KERNEL_HOME）
ok   info: kernel 設定讀驗通過
…（跟 01 第 5 步一樣的 kernel 項目）
ok   agent: agent 設定讀驗通過
ok   agent/tick.pool: 池 default 存在
ok   agent/llm.pool: 池 llm 存在
ok   agent/llm.model: 模型 default 存在
ok   agent/tool/date: 可執行 date
ok   probe/default: endpoint 通，模型清單裡有 deepseek-chat（endpoint http://localhost:4000/v1，模型 deepseek-chat）
設定檢查通過；模型連線也測過
```

它查：設定讀不讀得懂、它要的池（`default`、`llm`）kernel 有沒有、模型代號在不在 `llm.json`、工具找不找得到；`--probe` 真的問一次模型端點。
有 `bad` 就照提示修，最後一行會說「修好再 aos-agent start」。K 從 `AOS_KERNEL_HOME` 找（沒設就用上次 `start` 記在家裡的）。（[check 規範](../spec/aos-agent/cli-check.md)）

## 3. 登記、說一句、等回話

```sh
aos-agent start --target $W/bob
aos-agent say "現在幾點？請用工具查。" --target $W/bob --wait
```

`start` 印 `started agent-bob`。`say --wait` 把話投進去、等回話印出來，你會看到（約 10～20 秒）：

```text
現在是 2026年9月24日 下午3點16分。
```

`--wait` 不帶數字最多等 300 秒，`--wait 60` 就是 60 秒；等不到退 101。

## 4. 看回話的三種方法

```sh
aos-agent listen --target $W/bob                 # 印最後一則就退（同 --last）
aos-agent say "再說一次現在幾點。" --target $W/bob
aos-agent listen --target $W/bob --wait 60       # 等「下一則新的」回話，印出就退
aos-agent listen --target $W/bob --follow        # 每來一則印一則，看夠了按 Ctrl-C
```

`listen` 會在 stderr 多印一行時間（`aos-agent: time: 09-24 15:16:48`）。
如果印的是它中途叫工具的那句、或你剛說的話還沒處理，stderr 會多一行「還在處理中」——那不是最後答案，用 `--wait` 等。

## 5. 它現在怎樣

```sh
aos-agent status --target $W/bob
```

```text
health ok
agent  /home/you/aos-try/bob
state  idle  errors 0
batch  -
input  -
error  （無）
kernel agent-bob  running  runs 7  fails 0
```

**看第一行 `health`**：`ok` 就沒事；不是 `ok` 就照括號裡的指令做（還沒 `start` 時是 `沒登記（aos-agent start …）`）。
`error` 是**這次**卡住的原因，已經好了的舊錯另起一行、開頭標「（已恢復）」。各種說法與怎麼救見 [aos-agent 使用者只需要懂的](../spec/aos-agent/essentials.md)。

## 6. 撤掉

```sh
aos-agent stop --target $W/bob
```

印 `stopped agent-bob`。家、記憶都還在，之後 `start` 就接著用。**每天關機前**先 stop 每個 agent 再照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關；
沒 stop 就關機也沒關係，登記留在 kernel 帳本裡，開機後 `start` 印 `already started agent-bob`、退 0。

## 底下在幹嘛

- **agent 就是一個資料夾**，沒有常駐程式。`start` 替你 `aos-kernel add` 一份叫 `agent-bob` 的反覆工作，
  內容是「跑一次 `aos-agent tick`」，每秒一次，派到 `default` 池。所以 `aos-kernel ls` 會看到 `proc agent-bob`。（[登記](../spec/aos-agent/register.md)）
- 每走一格只做一小步然後退出，進度記在 `state.json`：**idle** 收輸入 → **think** 問模型 → 模型要用工具就 **act** 跑工具 → 再 think → 回到 idle。
  問模型和跑工具都不是它自己做的：它往 kernel `add --once` 兩種工作——問模型那件派到 `llm` 池、跑 `aos-llm call`；工具派到 `default` 池。
  下一格再去收結果。（[一格做什麼](../spec/aos-agent/tick.md)）
- 所以一句話的回覆要好幾格：純聊天約 5 秒，要跑工具約 10～20 秒，看模型快慢。
- `say` 只是往 `input/` 放一個檔；還沒收的話有好幾則，下一格會合成一輪一起問模型。收過的搬到 `input/done/`。
- 記憶在 `prompts/history.json`（每則 user／assistant／tool 訊息），`listen` 只印 assistant 的話。（[agent 家](../spec/agent/essentials.md)）

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| 沒 `start` 就 `say`，stdout 說「已投入，start 後會處理，不要再說一次」 | 話已經進去了。`start` 之後它自己會回，別再說一次（不然同一句進記憶兩次）；`--wait` 會立刻退 101 |
| `listen --wait` 等到逾時，可是 `status` 一切正常 | 回話在你開始 `listen --wait` 之前就到了——它只等**下一則新的**。改用 `listen`（最後一則），或下次用 `say --wait` |
| `start` 說要 `AOS_KERNEL_HOME` | 這個終端沒 `. $W/env.sh` |
| `say --wait` 立刻退 101 並印原因 | 它先看了一次：沒登記、手動暫停、連敗暫停、daemon 沒在跑、kernel 家壞了，都不乾等。照印的原因做 |
| `init` 退 1、`NotEmpty` | 資料夾裡已有別的檔；確定要在那裡生就加 `--force` |

不用 `init`、自己手寫一個家的做法見 [附錄 06](06-appendix-manual-home.md)。

## 收工

`aos-agent stop --target $W/bob`。下一篇要給 bob 加工具，要接著做就先別 stop（stop 了之後再 `start` 也行）。
