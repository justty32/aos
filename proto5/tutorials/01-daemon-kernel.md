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

## 2. 模型設定：一次寫好，很久不動

兩份檔：`llm.json` 是「代號 → 哪個端點、哪個模型」的表；`kernel.json` 說要開哪幾顆 cpu，
其中專門問模型的那顆 `llm` 用環境變數 `AOS_LLM_CONFIG` 指到 `llm.json`。

```sh
cat > $W/llm.json <<'EOF'
{"_metainfo": {"_type": "llm_config", "_version": 1},
 "models": {"default": {"endpoint": "http://localhost:4000/v1", "model": "deepseek-chat"}}}
EOF
cat > $W/kernel.json <<EOF
{"cpus": {"0": {}, "1": {},
          "llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": "$W/llm.json"}}}}
EOF
```

- **`llm.json` 的內容隨時能改**（換 port、換模型、加代號），下一次問模型就用新的，不用重開任何東西。
- **`AOS_LLM_CONFIG` 這個路徑**是「設好就很久不動」的：`kernel.json` 只在第 4 步 `init` 讀一次（抄成 `K/info.json`），
  第一次 `boot` 再把它抄進 llm cpu 的家（`K/cpus/llm/inst.json`），之後改 `kernel.json` 都不會生效。真要搬 `llm.json`，見本篇末「常見錯誤」。
- `"0"`、`"1"` 是兩顆一般 cpu（池名 `default`），跑一般工作和 agent；要幾顆之後再加，見 [05](05-many-agents.md)。

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

你會看到：`initialized /home/you/aos-try/K`。`K/info.json` 裡多了一顆 `"k": {"pool": "kernel"}`——那是 kernel 自己用的 cpu，自動加。

## 5. 開機前檢查

```sh
aos-kernel check --probe
```

你會看到（每行 `ok`／`warn`／`bad`）：

```text
ok   info: kernel 設定讀驗通過
ok   dirs: requests/、responses/、cpus/ 都在
ok   daemon: daemon 活著：/home/you/aos-try/D
ok   path: 五支 CLI 都找得到（daemon 的 PATH）
ok   pools: 池：default, kernel, llm
ok   llm/llm: 模型代號：default
ok   probe/default: endpoint 通，模型清單裡有 deepseek-chat（endpoint http://localhost:4000/v1，模型 deepseek-chat）
設定檢查通過；模型連線也測過
```

`--probe` 真的對端點打一次；不帶它只驗設定，最後一行會寫「未測模型連線（--probe 會測）」。有 `bad` 就照那行的提示修好再往下。

## 6. 開 kernel、看它健不健康

```sh
aos-kernel boot
aos-kernel ls
```

你會看到 `booted 4 cpus`（`k` 也算一顆），然後：

```text
health ok
kernel  running  seq 0  daemon alive  tick 1000ms
  kcpu k  正在跑一格  requests 1
cpu     4 顆：忙 0、閒 3、kernel 1
  池       cpu  工作  行程  daemon
  kernel   k    tick  -     running
  default  0    閒    -     running
           1    閒    -     running
  llm      llm  閒    -     running
proc    0 個
queue   -
```

**第一行 `health` 最要緊**：`ok` 就是正常；不是 `ok` 就照括號裡的指令做。
下面依序是 kernel（`seq` 是走到第幾格）、按池分組的 cpu 表、登記的工作（行程）表、排隊的名單。
`aos-kernel ls -v` 多印 `K`、`D` 的完整路徑與不截短的名字；`aos-kernel ls --json` 印欄位固定的 JSON，給程式讀（[ls 規範](../spec/kernel/cli-ls.md)）。

## 7. 關機（順序：kernel → daemon）

```sh
aos-kernel halt
aos-daemon halt
```

各印一行 `stopped`。`aos-kernel halt` 會等排程停、它的 cpu 都退出才回。有 agent 在跑的話，先 `aos-agent stop` 每一個（[03](03-first-agent.md)）。

## 8. 每天重開機

關機、登出之後 daemon 和 cpu 都沒了，但家（`D`、`K`、agent 的家）都還在。新開一個終端：

```sh
. $HOME/aos-try/env.sh
setsid aos-daemon boot >>$W/daemon.log 2>&1 </dev/null &
aos-kernel boot
aos-kernel ls | head -1
```

看到 `booted 4 cpus` 和 `health ok` 就好了。`init` 不用再跑（再跑會被拒絕：`AlreadyExists`）。有 agent 的話接著 `aos-agent start` 每一個（[03](03-first-agent.md)）。

## 底下在幹嘛

- **daemon** 只管 cpu 的生死：誰叫它拉一顆 cpu 它就拉，cpu 死了就重拉，要停就一個個停掉。它不看 cpu 在做什麼。（[daemon 規範](../spec/daemon/README.md)）
- **cpu** 是「一個資料夾＋一個主人程式」：有人往它的 `requests/` 放一張單，它就照單跑一次程式，把結果寫進 `responses/`。一次只跑一件。（[cpu 規範](../spec/cpu/README.md)）
- **kernel 不是一直開著的程式**。它每次只跑「一格」`aos-kernel tick`：先把下一格排進 `k` 那顆 cpu，再替排隊的工作挑空的 cpu 派下去、收結果，然後退出。
  一格接一格，就成了排程。它所有的記憶都在 `K/state.json`（帳本）。（[kernel 名詞](../spec/kernel/terms.md)、[boot 做什麼](../spec/kernel/boot.md)）
- 所以 **daemon 掛了，cpu 全跟著沒了，kernel 的格也斷了**：重開 daemon 之後一定要再 `aos-kernel boot`。
- llm cpu 跟一般 cpu 是同一種程式，差別只在它的環境多了 `AOS_LLM_CONFIG`；問模型的工作都排到 `llm` 池。（[kernel 家與 info.json](../spec/kernel/home.md)、[llm.json 格式](../spec/aos-llm/config.md)）

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `check` 的 `path` 是 `bad` | 開 daemon 時 PATH 還沒含 `proto5/cli`。照第 7 步關掉，`. $W/env.sh` 之後重開 daemon，再 `aos-kernel boot` |
| `boot` 印 `NotRunning: daemon 沒在跑` | 先做第 3 步 |
| `probe/default` 是 `bad`、`Connection refused` | 端點沒開或 `llm.json` 的 port 寫錯。改 `llm.json` 就好，不用重開 |
| `init` 印 `AlreadyExists: 拒絕覆蓋既有的家` | 家已經建過了，直接 `boot`；要重來就 `aos-kernel halt`、`aos-daemon halt`、`rm -rf $W/K` |
| 關掉終端後 daemon 不見了 | 用了 `&` 卻沒加 `setsid`。照第 3 步那行重開，再 `boot` |
| 要把 `llm.json` 搬到別處 | `aos-kernel halt`，改 `K/cpus/llm/inst.json` 裡的 `AOS_LLM_CONFIG`，再 `aos-kernel boot`（[kernel home.md 末段](../spec/kernel/home.md)） |
| `ls` 的 health 不是 `ok` | 照括號做；各種說法見 [kernel 命令列 ls](../spec/kernel/cli-ops.md) |

## 收工

照第 7 步關。要整個重來：關好之後 `rm -rf $HOME/aos-try`。下一篇接著用開好的 kernel，就先別關。
