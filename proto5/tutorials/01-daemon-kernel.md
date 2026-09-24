← [教程索引](README.md)｜[proto5 README](../README.md)｜下一篇 [02 用 kernel 跑工作](02-kernel-jobs.md)

# 01 設定、啟動與關閉 daemon 和 kernel

**目標**：把「很久都不會變的設定」一次寫好（環境檔、模型設定 `llm.json`、kernel 設定 `kernel.json`），
開起 daemon 和 kernel，確認它們健康，再照順序關掉；最後學會每天開機怎麼一次開回來。

**前提**：從 repo 根目錄開始；Python 3.12 以上；一個 OpenAI 相容的模型端點。下面用 LiteLLM 的
`http://localhost:4000/v1`、模型 `deepseek-chat`、不用金鑰（換別的就改 `llm.json` 的 `endpoint`、`model`，要金鑰加 `"api_key"`）。

## 1. 環境檔：放在哪、PATH 怎麼設

工作目錄 `W` 放你的家目錄底下（別放 `/tmp`：很多系統開機會清掉它，第 8 步「每天重開機」就沒東西可開了）。
把 PATH 和兩個「家」的位置寫進一個小檔，之後每開一個新終端只要 `.` 它一次。

```sh
W=$HOME/aos-try; mkdir -p $W
cat > $W/env.sh <<EOF
export PATH=$PWD/proto5/cli:\$PATH
export AOS_DAEMON_HOME=$W/D AOS_KERNEL_HOME=$W/K
W=$W
EOF
. $W/env.sh
```

`AOS_DAEMON_HOME` 是 daemon 的家、`AOS_KERNEL_HOME` 是 kernel 的家。三支指令（`aos-daemon`、`aos-kernel`、`aos-agent`）
都用 `--target DIR` 指家，省略時 daemon、kernel 各找自己的環境變數，再沒有就用目前資料夾。設好之後下面都不寫 `--target`。

## 2. 模型設定與池表：一次寫好

兩份檔：`llm.json` 是「代號 → 哪個端點、哪個模型」的表；`kernel.json` 是**池表**：每個池要幾顆 cpu、帶什麼環境。
cpu 不一顆顆取名字，只說「`default` 池要 2 顆、`llm` 池要 1 顆」。專門問模型的 `llm` 池用環境變數 `AOS_LLM_CONFIG` 指到 `llm.json`。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"pools": {"default": {"count": 2},
           "llm": {"count": 1, "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
```

- **`llm.json` 的內容隨時能改**（換 port、換模型、加代號），下一次問模型就用新的，不用重開任何東西。
- **`kernel.json` 只在第 4 步 `init` 讀一次**（抄成 `K/info.json`）。之後加減 cpu 不用改它，用 `aos-kernel cpu add／rm`（[05](05-many-agents.md)）。
- `default` 池跑一般工作和 agent 的每一格；`llm` 池跑問模型。池可以先寫 `"count": 0`，甚至不給 `--config`（只有 kernel 自己那顆），之後再 `cpu add`。

## 3. 開 daemon

daemon 是前景程式，要自己放背景。用 `setsid` 讓它跟終端脫鉤（關掉終端它也還在），輸出寫進 `daemon.log`：

```sh
setsid aos-daemon boot >>$W/daemon.log 2>&1 </dev/null &
```

**PATH 一定要先設好再開 daemon**：daemon 拉的 cpu、cpu 跑的工作都繼承 daemon 開起來那一刻的環境，之後再 `export` 沒用。

## 4. 建 kernel 的家

```sh
aos-kernel init --config $W/kernel.json
```

你會看到：`initialized /home/you/aos-try/K`。`K/info.json` 的池表多了一個 `"kernel": {"count": 1}`——kernel 自己用的池，只有一顆，自動加；
`daemon` 那格自動填成 `AOS_DAEMON_HOME`。

## 5. 開機前檢查

```sh
aos-kernel check --probe
```

你會看到（每行 `ok`／`warn`／`bad`）：

```text
ok   info: kernel 設定讀驗通過
ok   dirs: requests/、responses/、pools/ 都在
ok   daemon: daemon 活著：/home/you/aos-try/D（kernel 設定的池：default、llm、kernel；daemon 目前有：還沒有）
ok   path: 五支 CLI 都找得到（daemon 的 PATH）
ok   pools: 池：default 2、llm 1、kernel 1
ok   llm/llm: 模型代號：default
ok   probe/default: endpoint 通，模型清單裡有 deepseek-chat（endpoint http://localhost:4000/v1，模型 deepseek-chat）
設定檢查通過；模型連線也測過
```

`--probe` 真的對端點打一次；不帶它只驗設定，最後一行會寫「未測模型連線（--probe 會測）」。有 `bad` 就照那行的提示修好再往下。

## 6. 開 kernel、看它健不健康

```sh
aos-kernel boot
sleep 3
aos-kernel ls
```

`boot` 印 `booted 3 pools, 4 cpus`（kernel 池那顆也算）。`ls` 你會看到：

```text
health ok
kernel  running  seq 4  daemon alive  tick 1000ms
  kcpu kernel/0  正在跑一格  requests 2
pool    2 個工作池：要 3 顆、忙 0、閒 3
  kernel   want 1  sent 1   daemon kernel: running 1 pending 0 dead 0 failed 0
  default  want 2  sent 2  busy 0  idle 2  draining 0   daemon default: running 2 pending 0 dead 0 failed 0
  llm      want 1  sent 1  busy 0  idle 1  draining 0   daemon llm: running 1 pending 0 dead 0 failed 0
proc    0 個
queue   -
```

**第一行 `health` 最要緊**：`ok` 就是正常；不是 `ok` 就照括號裡的指令做。
下面依序是 kernel（`seq` 是走到第幾格）、每池一行、登記的工作（行程）、排隊的名單。池那行怎麼讀：

- `want` 要幾顆（池表寫的）、`sent` kernel 已經跟 daemon 講好幾顆；`busy`／`idle` 忙的、閒的；`draining` 收掉中（做完手上工作就收）。
- `daemon default:` 後面是 daemon 那邊真的看到的：`running` 活著（有死了正在重拉的會寫成 `running 2（含 restarting 1）`，不是另外多的）、`pending` 等著拉、`dead`／`failed` 拉不起來。
- `boot` 完馬上看，工作池可能還寫 `sent 0`、`daemon default: 沒有這池`：kernel 一格才跟 daemon 講一次，等一兩秒就齊。

`aos-kernel ls -v` 多印 `K`、`D` 的完整路徑；`--pool default` 只看那池、一顆一行；`--procs` 列出每個行程（預設只列出事的）；
`--json` 印欄位固定的 JSON，給程式讀（[ls 規範](../spec/kernel/cli-ls.md)）。

## 7. 關機（順序：kernel → daemon）

```sh
aos-kernel halt
aos-daemon halt
```

各印一行 `stopped`。`aos-kernel halt` 會把每個池（含 kernel 池）縮到 0，等 daemon 那邊的 cpu 都退出才回。有 agent 在跑的話，先 `aos-agent stop` 每一個（[03](03-first-agent.md)）。

## 8. 每天重開機

家（`D`、`K`、agent 的家）都還在。新開一個終端，先開 daemon、看 health：

```sh
. $HOME/aos-try/env.sh
setsid aos-daemon boot >>$W/daemon.log 2>&1 </dev/null &
sleep 1
aos-kernel ls | head -1
```

- **昨天是直接關電腦、登出**（沒照第 7 步）：daemon 會照上次的宣告把池全拉回來，kernel 的鏈自己接上，第一行就是 `health ok`，**不用 `aos-kernel boot`**。
- **昨天照第 7 步關過**：池都縮到 0 了，第一行是 `health 停機中（aos-kernel boot --target …）`。照括號補一次 `aos-kernel boot`，印 `booted 3 pools, 4 cpus`（照 `K/info.json` 現在的池表拉）就好了。

一句話：**先開 daemon，health 不是 `ok` 才 `aos-kernel boot`**。
`init` 不用再跑（再跑會被拒絕：`AlreadyExists`）。有 agent 的話接著 `aos-agent start` 每一個（[03](03-first-agent.md)）。

## 底下在幹嘛

- **daemon** 只管 cpu 的生死，而且按池管：kernel 跟它說「池 `default` 要 2 顆」，它就補到 2 顆；死了就重拉（越死越等久，不會狂拉）；多了就收。它不看 cpu 在做什麼。宣告記在 daemon 家裡，所以 daemon 重開會照舊拉回來。（[daemon 的池](../spec/daemon/pools.md)）
- **cpu** 是「一個資料夾＋一個主人程式」：有人往它的 `requests/` 放一張單，它就照單跑一次程式，把結果寫進 `responses/`。一次只跑一件。每顆的家在 `K/pools/<池>/cpus/<號>/`，號碼從 0 起。（[cpu 規範](../spec/cpu/README.md)）
- **kernel 不是一直開著的程式**。它每次只跑「一格」`aos-kernel tick`：先把下一格排進 kernel 池那顆 cpu（`kernel/0`），再替排隊的工作挑空的 cpu 派下去、收結果、照池表跟 daemon 講要幾顆，然後退出。
  一格接一格，就成了排程。它所有的記憶都在 `K/state.json`（帳本）。（[kernel 名詞](../spec/kernel/terms.md)、[boot 做什麼](../spec/kernel/boot.md)）
- llm 池的 cpu 跟一般 cpu 是同一支程式，差別只在環境多了 `AOS_LLM_CONFIG`；問模型的工作都排到 `llm` 池。（[池表 info.json](../spec/kernel/info.md)、[llm.json 格式](../spec/aos-llm/config.md)）

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `check` 的 `path` 是 `bad` | 開 daemon 時 PATH 還沒含 `proto5/cli`。照第 7 步關掉，`. $W/env.sh` 之後重開 daemon，再 `aos-kernel boot` |
| `boot` 印 `NotRunning: daemon 沒在跑` | 先做第 3 步 |
| `ls` 第一行 `daemon 沒在跑：…` | 同上：先 `aos-daemon boot`，health 還不是 `ok` 再 `aos-kernel boot` |
| `probe/default` 是 `bad`、`Connection refused` | 端點沒開或 `llm.json` 的 port 寫錯。改 `llm.json` 就好，不用重開 |
| `init` 印 `AlreadyExists: 拒絕覆蓋既有的家` | 家已經建過了，直接 `boot`；要重來就 `aos-kernel halt`、`aos-daemon halt`、`rm -rf $W/K` |
| `boot` 印 `InfoVersion` | `K/info.json` 還是舊的「一顆顆列 `cpus`」格式。刪掉 `K`，照第 2 步的池表重新 `init` |
| `init` 印 `FieldTypeMismatch: cpus 是 proto5 舊格式…` | `--config` 用了舊的 `{"cpus": {…}}` 格式。照第 2 步改成 `pools` 池表再 `init` |
| 關掉終端後 daemon 不見了 | 用了 `&` 卻沒加 `setsid`。照第 3 步那行重開，health 不是 `ok` 再 `boot` |
| 要把 `llm.json` 搬到別處 | 手改 `K/info.json` 裡 `llm` 池 `envs` 的路徑，下一格生效；已經活著的 cpu 不會變，要現在就全換：`aos-daemon kill --pool llm --all`（[池模板](../spec/kernel/home.md)） |
| `ls` 的 health 不是 `ok` | 照括號做；各種說法見 [health](../spec/kernel/health.md) |

## 收工

照第 7 步關。要整個重來：關好之後 `rm -rf $HOME/aos-try`。下一篇接著用開好的 kernel，就先別關。
