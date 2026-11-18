這份教你不叫 `aos-tree-start`，手動把一棵「stack 還在、表上掛著 proc、daemon 沒在跑」的樹起回來（試驗 06，11-18 在公司 WSL 實跑過）。
← [目錄](README.md)

# 試驗 06：不用 aos-tree-start 起回停著的 daemon

使用者原話：「6.不使用aos-tree-start，來啟動現有的，已經有掛了proc的，停滯、沒在跑的daemon。」

## 結論

- **`aos-tree-start` 只做兩件事**：① 看殼裡有沒有 `AOS_HOME` 以外的 `AOS_*`，有就拒絕（只印名字）；② 沒有就 `exec aos-exec 你給的參數`（同一個 pid）。所以 `aos-tree-start root`＝檢查＋`aos-exec root`。
- **最少一行**：`cd ~/aos-home && source env.sh && aos-exec root`。起出來的表、子項看到的 `AOS_*` 名字、eca agent 的 `env.json` 跟用 `aos-tree-start` 起的**完全一樣**。
- **少的只有那道檢查**：殼裡帶著別棵樹的 `AOS_STACK`（例如在 agent 的殼裡打），`aos-exec root` 不會擋，會在那個 stack 上起一台空的新 daemon。
- **不要跳過 `aos-exec` 直接打 `aos-daemon`**：`.env` 不會被讀，`AOS_CLOCK`、`AOS_LLM_KERNEL` 不見。eca agent 照答但時鐘 hook 全停；API 版的 agent 直接起不來（`LlmKernelMissing`）。
- **表上原本的 proc**：`running`、`sleeping` 的開門自己醒（跟有沒有 `auto_restart` 無關）；`stopped` 的不醒，要 `aos-daemon-ctl start`。
- 環境只要 `AOS_HOME`（`env.sh` 也要它）和 PATH 上的 `$AOS_HOME/bin`；不用自己設 `AOS_STACK`。eca 版不用 `LITELLM_KEY`（claude 用自己的登入）；假腦也不用。

## 手動起的步驟（eca 樹，`~/aos-home` 從 `templates/start-eca` 抄的，ann 已掛好、daemon 已關）

**1. 進樹、清環境**

```sh
cd ~/aos-home && source env.sh
```

會看到：沒有輸出。卡點：沒設 `AOS_HOME` 會報 `env.sh: error: EnvBad AOS_HOME is not set …`。

**2. 先看表（daemon 沒在跑也看得到）**

```sh
aos-daemon-ctl -d .stack ls
```

會看到：

```
ann       sleeping  -  143  /home/…/aos-home  -
# daemon: not running (pid 1803789 is gone); the table above is what it left
```

**3a. 前景起（等於 aos-tree-start root）**

```sh
aos-exec root
```

會看到每個醒來的 proc 一行 `{"at": …, "name": "ann", "phase": "running", …}`。Ctrl-C＝整棵收工。

**3b. 背景起（關掉視窗也活著）**

```sh
setsid -f aos-exec root > root.log 2>&1 < /dev/null
```

會看到：沒有輸出，log 進 `root.log`。實測關掉那個視窗、甚至從一次性的 `wsl -e bash -c` 起，daemon 都還在。也可以 `nohup aos-exec root > root.log 2>&1 &`（在 tmux 裡實測可用；它是那個殼的子行程）。背景起的要用 `aos-daemon-ctl -d .stack shutdown` 關，沒有 Ctrl-C 可按。

**4. 確認醒了**

```sh
aos-daemon-ctl -d .stack ls
```

會看到 `_clock`、`_sweeper`、`ann` 都是 `running`，最後一行 `# daemon: running (pid …)`。再問一句 `aos-agent -d .stack --target ann say "reply with the single word: ping2" && aos-agent -d .stack --target ann listen --timeout-s 120`，回 `ping2`。

## 表上原本的 proc 會不會自己起來

| 關 daemon 前它是 | 怎麼弄出來的 | 再起之後 |
|---|---|---|
| running（有 `auto_restart` 的 ann） | 直接 `shutdown` | 醒，`running` |
| running（沒 `auto_restart` 的 proc） | 直接 `shutdown` | 醒，`running` |
| sleeping | `aos-daemon-ctl -d .stack sleep 名字`，再 `shutdown` | 醒，`running` |
| stopped | `aos-daemon-ctl -d .stack stop ann`，再 `shutdown` | **不醒**，留 `stopped`；`aos-daemon-ctl -d .stack start ann` 才起 |

`shutdown` 會印 `daemon at …/.stack stopped (ctl seq 2); 3 procs asleep, they wake when it starts again`（stopped 的不算在內）。

## 兩層樹（API 版：根＋llm kernel，`templates/start-api`，假腦）

兩台是分開起的兩個 daemon（llm kernel 不是根的子項），**順序不拘**：

```sh
cd ~/aos-home && source env.sh && aos-exec root                    # 視窗 A
cd ~/aos-home && source env.sh && cd llms && aos-exec --stack stacks/llm def   # 視窗 B
```

實測先起根、llm kernel 晚起：ann 醒了、問題送出去，`listen` 先印 `ann is waiting for its brain, but the llm kernel at …/llms/stacks/llm is not running …`；等 llm kernel 起來，信接著被答，回 `FAKE ANSWER to: …`。在樹頂打 `aos-exec --stack llms/stacks/llm llms/def` 也行。

## 起錯位置、重複起

| 打了什麼 | 結果（原樣） |
|---|---|
| 已有一台在跑，再打 `aos-exec root`（或 `aos-tree-start root`、`aos-exec --stack .stack root`） | `aos-daemon: error: DaemonExists a daemon is already running on this stack (/home/…/aos-home/.stack/); to reuse it, just aos-daemon-ctl add / aos-agent ctl add`，退 1，原本那台不受影響 |
| 在樹的上一層打 `aos-exec aos-home/root` | 不報錯；在**上一層**多一個 `.stack`，起一台只有 `_clock`、`_sweeper` 的空 daemon。原本的表沒人碰 |
| 在上一層打 `aos-exec --stack aos-home/.stack aos-home/root` | 表對、ann 醒，但 `AOS_WS` 是上一層，所以 `.env` 算出的 `AOS_LLM_KERNEL` 多錯一層（`…/llms/stacks/llm` 少了 `aos-home/`）。eca 版用不到所以照答；API 版要再加 `--ws aos-home` |
| `cd llms && aos-exec def`（忘了 `--stack`） | 在 `llms/.stack` 起一台空的 llm kernel；ann 照樣說 llm kernel `is not running` |
| 殼裡有別棵樹的 `AOS_STACK`，打 `aos-tree-start root` | `aos-tree-start: error: EnvBad AOS_STACK set in this shell (inherited from another tree or an agent's shell?): the root would use them; clear every AOS_* except AOS_HOME first (source env.sh, in bash), or pass --force` |
| 同上，改打 `aos-exec root` | 不擋，在那個 `AOS_STACK` 上起一台空 daemon。補救：先 `source env.sh`，或明給 `aos-exec --stack .stack root`（`--stack` 蓋過殼裡的值，實測表對、名字對） |
| `AOS_HOME` 沒設就 `aos-exec root` | `aos-exec: error: DotenvBad bad .env: /home/…/aos-home/root/.env line 7 (variable referenced by ${...} is not set)` |
| 跳過 `aos-exec`：`cd root && aos-daemon --enable-logs daemon.json` | `aos-daemon: error: StackMissing the ctl window needs AOS_STACK, which is not set (write null to turn it off)` |
| 給對 `AOS_STACK`（絕對路徑）直接 `aos-daemon …` | 表對、全醒，但沒讀 `.env`：子項少了 `AOS_CLOCK`、`AOS_LLM_KERNEL`。eca 的 ann 照答，`stderr.txt` 每圈 `aos-eca-turn: warning: hook timer (event on_clock) is not checked: AOS_CLOCK is not set …`（`context_wrap`、`mail_notify` 同）；API 版 ann 連 3 次 3 秒內退、留 `stopped`，原因 `agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set …`。補救：`shutdown`、改用 `aos-exec root`、再 `aos-daemon-ctl -d .stack start ann`，卡著的信接著答 |

## 跟 aos-tree-start 起的比

- 子項看到的 `AOS_*` 名字（掛一支只記名字的 proc 比）：`AOS_CD AOS_CF AOS_CLOCK AOS_CO AOS_DAEMON AOS_HOME AOS_LLM_KERNEL AOS_STACK AOS_WS`，`aos-tree-start root`、`aos-exec root`（前景、`nohup`、`setsid`）、`aos-exec --stack .stack root` 全部一樣；cwd 都是 proc 自己的定義夾。
- eca agent 的 `.stack/procs/ann/claude/env.json`（記 `AOS_CLOCK`、`AOS_DAEMON`、`AOS_HOME`、`AOS_LLM_KERNEL`）：`aos-exec root` 起的跟 `aos-tree-start` 起的逐字一樣（內容沒變就不重寫，檔案時間停在第一次）。直接 `aos-daemon` 起的只剩 `AOS_DAEMON`、`AOS_HOME`。

## 發現的問題（沒修程式）

1. **`aos-agent` 給的重起提示會帶人走錯路**：ann 睡著時它說 `restarting it wakes ann too: the way it was started, aos-exec <daemon folder> or AOS_STACK=…/.stack/ aos-daemon <daemon.json>`。照後半句打不會讀 `.env`，API 版 agent 起不來（見上表最後一列）。
2. **在上一層用 `--stack` 起，`AOS_LLM_KERNEL` 會靜靜錯一層**：表全對、看起來成功，問腦時才發現。要同時給 `--ws`。
3. **`aos-exec root` 不擋殼裡帶著的 `AOS_*`**（照設計，擋在 `aos-tree-start`）。不用 `aos-tree-start` 的人要自己記得先 `source env.sh`。
4. 起錯位置（上一層、`cd root` 後才寫 `AOS_STACK=$PWD/.stack`、`llms/` 忘了 `--stack`）都不報錯，只是多一個空 `.stack`；要靠第 4 步 `ls` 看 ann 在不在才發現。

## 沒驗的

- 重開機後、或 daemon 被 `kill -9` 之後再起（只試了正常 `shutdown`）。
- `--ws` 補上之後的 API 版上一層起法（只從 `.env` 推論）。
- 真模型的 API 版（只用假腦）。
