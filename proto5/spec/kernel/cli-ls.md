← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：ls

```
aos-kernel ls [--target K] [--pool P] [--procs] [--json] [-v|--verbose]
```

`ls` 不是 syscall：偷看 `K/info.json`、帳本 `K/ledger.sqlite`、各池 daemon 的 `summary.json`（`--pool` 時加 `kids/`）、開 tick 的 daemon 的登記檔 `D/kernels/<id>.json`；不放單、不拿鎖，沒人開 tick 也能看。（2026-09-24 one-boot：kernel cpu 那行換成 tick 行、池表沒有 kernel 池、`--json` 升第 3 版。）
文字版與 `--json` 出自同一份資料（`lib/aos_kernel_ls.py` 的 `ls_data()`），判定一樣。第一行 health 的判定在 [health.md](health.md)。
`--pool P`：只看那池（池在 info 與帳本都沒有＝`NotFound` 退 1）。

## 人看的版本

```
health ok
kernel  running  seq 128  daemon alive  tick 1000ms
  tick 由 daemon 開：上一格 0 秒前
pool    2 個工作池：要 3 顆、忙 2、閒 1
  default  want 2  sent 2  busy 1  idle 1  draining 0   daemon default: running 2 restarting 0 pending 0 dead 0 failed 0
  llm      want 1  sent 1  busy 1  idle 0  draining 0   daemon llm: running 1 restarting 0 pending 0 dead 0 failed 0
proc    3 個（反覆 2、once 1）：queued 1、running 2
  行程       種類  狀態     runs  fails  回音  備註
  agent-bob  反覆  running    40      1  -     重試中（連敗 1/3）
  （其餘 2 個沒事的沒列；--procs 全列）
queue   1：agent-amy
```

- `kernel` 行：`phase`（沒帳本＝`沒 boot 過`）、`seq`（`last_seq`，沒有＝`-`）、daemon `alive`／`dead`（**開 tick 的 daemon**）、`tick_ms`。
  下一行 tick：daemon 登記著這個 kernel＝`  tick 由 daemon 開：上一格 N 秒前`（N 看帳本 `last_tick_at`；沒有＝`-`），連敗時再加 `、連敗 N`；
  沒登記＝`  tick 沒人開（daemon 沒登記這個 kernel；aos up）`。
- `pool` 標題：工作池數、要幾顆（`want` 總和）、忙、閒，有收掉中的再加 `、收掉中 D`。
  下面每池一行（縮排 2 格，格式＝[`cpu ls`](cli-cpu.md) 的池行，含尾註）。
  `--pool P` 時那池下面再縮排 4 格、一顆一行（格式＝`cpu ls --pool`）。
- `proc` 標題：總數、反覆／once 各幾個、各 `status` 幾個（照字母排）。（09-24 停車）有停著的（`parked`）再加 `；停車 N`。沒行程＝只印 `proc    0 個`。
  下面是對齊表（行程、種類 反覆／once、狀態、runs、fails、回音（`pending` 有東西印 `等`）、備註（agent 的暫停／重試標記：`連敗暫停中`、`手動暫停中`、
  `手動暫停中＋連敗暫停中`、`重試中（連敗 N/3）`、`已解除暫停，等下一次成功`））。
  **預設只列 `bad` 與有暫停／重試標記的行程**，其餘印一行 `（其餘 N 個沒事的沒列；--procs 全列）`；`--procs` 全列（上萬個時很長）。
  `--pool P` 時只列那池的行程。表下面每個列出來的 `bad` 行程一行 `  <名字> 壞了，看 <路徑>`（target 的 inst 有字面 `stderr` 就指它，agent 就是 `<家>/log/agent.err`；
  沒有字面 `stderr`（沒寫、寫成指示詞、不是 JSON）就指 target 本身）。
- `queue` 行：排隊中＝`status` 是 `queued` 的行程（照帳本 `procs` 的順序）；個數＋名字，最多列 8 個，多的寫 `…還有 N 個`；空＝`-`。
- **長的東西不進主表**：行程名超過 24 格寬就砍中間（留頭和尾，中間 `…`）；K、D、chain、每個行程的 target 都只在 `-v`。對齊時中日韓字算 2 格。
- `-v`：kernel 行下面多 `K`、`D`、`chain` 三行，再接 tick 那行；表裡的名字不截；列出來的行程下多一行 `  <名字>  target <路徑>`；queue 全列。

**daemon 沒在跑時**（試玩 one-boot 追加）：帳本與 daemon 的摘要都是它死前的樣子，文字版不把它們印得像還活著——
kernel 行的 phase 寫成 `running（帳本這樣寫；daemon 不在，其實沒在跑）`，tick 行寫 `tick 沒人開（daemon 沒在跑；aos up）`，
那個 daemon 的池行把摘要換成 `不明（daemon 沒在跑；摘要是舊的，最後記 running N）`。`--json` 照舊原樣給（看 `kernel.daemon.alive`、`pools.P.daemon_alive` 自己判）。

## `--json`

格式（`aos_kernel_ls` 第 3 版，one-boot 升版）在 [cli-ls-json.md](cli-ls-json.md)。
