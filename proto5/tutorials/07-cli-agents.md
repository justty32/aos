← [教程索引](README.md)｜上一篇 [06 附錄](06-appendix-manual-home.md)｜範本 [templates/cli-agents](../templates/cli-agents/README.md)

# 07 讓 Claude Code 和 Codex 當 cpu 跑單子

**目標**：不寫任何新程式，把 `claude`（Claude Code）和 `codex` 兩支 CLI 當成「一種普通的 cpu」來用：
開一個專門放它們的 kernel 家，丟一張 codex 唯讀審查單、一張 claude 單，收結果，再學會「接著聊」和「取消」。

**前提**：做完 [01](01-daemon-kernel.md) 第 1～6 步（daemon 開著）；新終端先 `cd` 回 **repo 根目錄**再 `. $HOME/aos-try/env.sh`（下面的 `$PWD` 指的是 repo）。
`claude`、`codex` 都登入過（有 `~/.codex/auth.json`），**開 daemon 那時**的 PATH 找得到它們。路徑只用英數與 `/ . _ -`（範本用 `sed` 換字）。
**這篇會花你自己的訂閱額度**：照抄的話 codex 1 次（約十幾萬 input token）、claude 2 次（只回 ok）。

## 0. 先講清楚：三個洞

這篇是「自己手動放單」的版本，沒有牢、沒有額度控制。這三件事擋不住：

1. **搶你自己的訂閱額度**。aos 用你自己的 Claude／ChatGPT 登入，跟你其他在用的 session 共用額度。
   塞十張單子它就照跑十張，前一張失敗也不停；煞車只有池的大小（claude 池 1 顆＝同時最多 1 張）、逾時、和 claude 的 `--max-budget-usd`。
2. **能往 kernel 放單子的程式，都能開 claude 單子**。任何能寫 `K2/requests/` 的程式——包括 agent 的 bash 工具——都能放一張 `--pool claude` 的單，argv 寫什麼都行。
   另開 kernel 家只是**分開管理**，不是上鎖。別讓 agent 知道 K2 在哪。
3. **取消不乾淨，只能砍整顆 cpu**。`aos-kernel rm` 之後回音馬上變成「已移除」，但那顆 cpu 上的 claude 照跑、照改檔。要停只能叫 daemon 砍那顆 cpu（第 6 步），而且要等好幾秒。

## 1. 開第二個 kernel 家 K2

花錢的池放在另一個 kernel 家，跟 01 開的 `K` 共用同一個 daemon。範本在 `proto5/templates/cli-agents/`：

```sh
T=$PWD/proto5/templates/cli-agents
sed "s|@W@|$W|g" $T/kernel2.json > $W/kernel2.json
aos-kernel init --target $W/K2 --config $W/kernel2.json
aos-kernel boot --target $W/K2
aos-kernel ls --target $W/K2
```

你會看到 `booted 3 pools, 4 cpus`；`ls` 的池有三行：`kernel want 1 … daemon k2-kernel: running 1 …`、`claude want 1 …`、`codex want 2 …`。

- **kernel 池在 daemon 那邊叫 `k2-kernel`**（範本的 `"dpool"`）：`K` 已經用掉 daemon 裡 `kernel` 這個池名，同名會被拒（`NameTaken`）。其他池名也不能跟 `K` 的撞。
- 範本讓 claude、codex 兩池 **從空環境開始**，只帶 `PATH`、`HOME`、`LANG`（codex 再多 `CODEX_HOME`）：環境裡的 API 金鑰帶不進去（免得改走付費 API）。要靠代理（`HTTPS_PROXY`）才上得了網，就在 `$W/kernel2.json` 那兩池的 `$val` 補回，再 `init`。
- 多開幾顆照 [05](05-many-agents.md) 的 `cpu add --target $W/K2`；claude 池多開＝同時燒更多額度。

## 2. codex 專用的設定資料夾

不讓 codex 讀你的 `~/.codex/config.toml`（可能開了 `danger-full-access`）和 `AGENTS.md`，給它一個只放登入的資料夾：

```sh
mkdir -p $W/codex-home
ln -s $HOME/.codex/auth.json $W/codex-home/auth.json
```

用**符號連結**，不要複製：登入會換新憑證，複製的那份會失效（偶爾 `ls -l` 看它還是不是 `->`）。
工作區自己的 `AGENTS.md` 它照讀。claude 不用另開資料夾：範本的 `--safe-mode` 讓它不讀你的 CLAUDE.md、記憶、skill 和 hook。

## 3. 丟一張 codex 唯讀審查單

每張單子一個資料夾：任務書 `task.md`、`inst.json`，結果在 `out/`。

```sh
J=$W/cli-jobs/review-ls; mkdir -p $J
echo '唯讀審查 proto5/tools/base/ls，找真的會出錯的地方，每條一句附行號，≤800 字。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$PWD|g" $T/codex-review.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool codex --timeout-ms 600000
```

`add` 印**單名**和回音的路徑，例如 `cli-1790…json /home/you/aos-try/K2/responses/cli-1790…json`。

- **`--pool codex`** 排到 codex 池；**`--timeout-ms`** 一定要給（K2 預設 30 分鐘），到了就砍。
- 範本全用絕對路徑：inst 的 `stdin`、`stdout` 相對的是 `cwd`（你的 repo），不是單子資料夾。
- **不要**帶 `--wait-ms 0`（那是「馬上逾時」）；想等就給夠長，例如 `--wait-ms 700000`。

約一分鐘後回音到：

```sh
cat /home/you/aos-try/K2/responses/cli-…json      # 換成你看到的路徑
aos-kernel ack cli-…json --target $W/K2            # 用單名 ack，不是 --name
cat $J/out/answer.md
```

回音長這樣：`{"code": 0, "kind": "child", "timed_out": false, "stopped": false, "ms": 55918}`。
**成功要兩層都過**：回音 `kind` 是 `child`、`code` 0、`timed_out`／`stopped` 都 `false`；而且 `$J/out/events.jsonl` 有 `"type":"turn.completed"`、沒有 `turn.failed`。

## 4. 丟一張 claude 單

```sh
J=$W/cli-jobs/c1; mkdir -p $J $W/cli-ws
echo '只回 ok 兩個字，不要用任何工具。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$W/cli-ws|g" $T/claude-job.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool claude --timeout-ms 300000 --wait-ms 330000
cat $J/out/result.json
```

`result.json` 要看：`is_error`（`false` 才算成功）、`result`（回答）、`session_id`（接著聊用）、`total_cost_usd`（照定價算，訂閱也印）。

範本的旗標都是保守的：會問人的動作一律拒絕；最多 8 輪；超過 0.5 美元就停（呼叫完才算，擋不住第一次）。
**預設不帶 `--restricted`**（使用者 09-24 裁決）：claude 能跑 `@WS@` 裡的程式（Bash 等）。牢做好前這等於在你的機器上裸跑 shell——只在信得過工作區內容時放單。想更保守、以及「跳過權限」類旗標為什麼一律不加，見[範本說明](../templates/cli-agents/README.md#旗標為什麼這樣選)。

## 5. 接著聊：從上一次成功的那次分岔

每次都從**上一次成功的**對話分岔一條新的（fork），失敗、逾時、被砍的那次不算。
「成功」＝回音那層過（同第 3 步），**而且** `result.json` 的 `is_error` 是 `false`、`subtype` 是 `success`。

```sh
S=0c31125f-…     # c1 的 result.json 裡的 session_id（c1 兩層都過）
J=$W/cli-jobs/c2; mkdir -p $J
echo '剛才你回了什麼？只回那兩個字。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$W/cli-ws|g" -e "s|@SESSION@|$S|g" $T/claude-next.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool claude --timeout-ms 300000 --wait-ms 330000
```

它記得上一次，回 `ok`，`session_id` 是新的。codex 用 `codex-review-next.json`，`@SESSION@` 換成上一次 `events.jsonl` 第一行的 `thread_id`（要有 `turn.completed`）。
哪個 id 是「上一次成功的」要你自己記（例如寫進 `$W/last-ok-session`）。

## 6. 取消

先試免費的：claude 池放一張 `sleep 77` 再撤掉。

```sh
mkdir -p $W/cli-jobs/s; echo '{"argv": ["sleep", "77"]}' > $W/cli-jobs/s/inst.json
aos-kernel add $W/cli-jobs/s/inst.json --target $W/K2 --once --pool claude --name s1
sleep 3; aos-kernel ls --target $W/K2 --pool claude | grep s1
aos-kernel rm s1 --target $W/K2
pgrep -a -f "^sleep 77"
```

`ls` 那行是 `claude/0  busy s1  daemon running gen 1`：s1 在 `claude` 池的 0 號。`rm` 印 `s1`，當初那張單的回音變成 `Removed`。
但 `pgrep` 還看得到 `sleep 77`——**它還在跑**（換成 claude 就是還在花錢、還在改檔）。要真的停，叫 daemon 砍那顆 cpu（池名用 daemon 那邊的，這裡同樣是 `claude`）：

```sh
aos-daemon kill --pool claude 0
```

印 `killed 0`（0 是號碼），只代表「開始停」：daemon 先請 cpu 溫和停，5 秒後送 TERM、cpu 再砍那張單子的程式那一組（不死再過 5 秒 KILL）。這次約 6 秒後 `pgrep` 才看不到；自己脫離那一組的子孫砍不到，要另外查。
砍完 daemon 馬上再拉一顆，`aos-daemon ls --pool claude` 看得到 `0  running … gen 2`（第 2 任）。
**小心砍錯**：從你查到「在 `claude/0` 上」到砍下去之間，它可能已經跑完、換跑下一張了。

## 底下在幹嘛

- **沒有新種類的 cpu**：claude、codex 池的 cpu 跟 01 `default` 池的是同一支 `aos-cpu`，差別只在池名和環境。單子就是普通的 inst.json，argv 是 `claude -p …` 或 `codex exec …`，任務書從 stdin 餵、結果寫進 stdout 指的檔；派單、重拉、逾時砍整組全照 01、02。（[提案 as-cpu](../notes/2026-09-24-cli-agents/as-cpu.md)）
- **不要把 claude／codex 單子登記成反覆的**（不帶 `--once`）：反覆的失敗了會被排回去再跑＝重花一次錢、重改一次檔。
- 旗標與成功怎麼判見 [templates/cli-agents](../templates/cli-agents/README.md)；真跑查到的事在 [stage0 報告](../notes/2026-09-24-cli-agents/stage0.md)。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `boot` 印 `NameTaken` | K2 的池在 daemon 那邊的名字跟 `K` 的撞了（最常見是 kernel 池沒寫 `dpool`）。`halt` K2、`rm -rf $W/K2`、在 `kernel2.json` 補 `dpool` 重來 |
| 回音 `"code": 127` | daemon 開起來時的 PATH 找不到 `claude`／`codex`；開 daemon 前先 `export` 好 |
| `ack` 印 `NotFound` | ack 要用 `add` 印的**單名**（`cli-….json`），不是 `--name` 給的名字 |
| claude 的 `result.json` 是 `"subtype": "error_max_budget_usd"` | 超過 `--max-budget-usd`（回音 `code` 1）。調高範本的數字，或把任務切小 |

## 收工

```sh
aos-kernel halt --target $W/K2
```

印 `stopped` 才算停好；報 `Timeout` 是還有單子在跑（halt 只等 30 秒），等它跑完或照第 6 步砍 cpu，先別刪。K 和 daemon 照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關。
整個重來：停好後 `rm -rf $W/K2 $W/cli-jobs $W/codex-home $W/cli-ws $W/kernel2.json`（只刪這篇建的）。
