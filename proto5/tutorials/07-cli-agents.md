← [教程索引](README.md)｜上一篇 [06 附錄](06-appendix-manual-home.md)｜範本 [templates/cli-agents](../templates/cli-agents/README.md)

# 07 讓 Claude Code 和 Codex 當 cpu 跑單子

**目標**：不寫任何新程式，把 `claude`（Claude Code）和 `codex` 兩支 CLI 當成「一種普通的 cpu」來用：
開一個專門放它們的 kernel 家，丟一張 codex 唯讀審查單、一張 claude 單，收結果，再學會「接著聊」和「取消」。

**前提**：做完 [01](01-daemon-kernel.md) 第 1～6 步（daemon 開著）；新終端先 `cd` 回 **repo 根目錄**再 `. $HOME/aos-try/env.sh`（下面的 `$PWD` 指的是 repo）。
`claude` 和 `codex` 都已經在這台機器登入過（有 `~/.codex/auth.json`）、而且**開 daemon 那時**的 PATH 找得到它們。路徑只用英數與 `/ . _ -`（範本用 `sed` 換字，`&`、`|`、引號、空白會弄壞）。
**這篇會花你自己的訂閱額度**：每張單子都是一次真的 claude／codex 對話。照抄的話 codex 1 次（它會自己讀好幾個檔，一次約十幾萬 input token）、claude 2 次（只回 ok）。

## 0. 先講清楚：三個洞

照這篇做，你得到的是「自己手動放單」的版本，沒有牢、沒有額度控制。這三件事現在擋不住：

1. **搶你自己的訂閱額度**。aos 用的是你自己的 Claude／ChatGPT 登入，跟你自己開 Claude Code、跟其他在用的 session 共用同一份額度。
   一次塞十張單子進 kernel，它就照跑十張；前一張失敗了後面的也不會停。唯一的煞車是池的大小（claude 池只有 1 顆＝同時最多 1 張）、每張的逾時、和 claude 的 `--max-budget-usd`。
2. **能往 kernel 放單子的程式，都能開 claude 單子**。kernel 不問是誰放的：任何能寫 `K2/requests/` 的程式——包括 agent 的 bash 工具——都能放一張 `--pool claude` 的單，而且單子裡的 argv 寫什麼都行。
   另開一個 kernel 家只是**分開管理**，不是上鎖。別讓 agent 知道 K2 在哪；要讓 agent 叫它們，得等以後的「受信任入口＋牢」。
3. **取消不乾淨，只能砍整顆 cpu**。`aos-kernel rm` 之後，那張單子的回音馬上變成「已移除」，但那顆 cpu 上的 claude 照跑、照改檔。要停只能叫 daemon 砍那顆 cpu（第 6 步）：它先請 cpu 溫和停、5 秒後才砍那張單子的程式那一組，自己脫離那一組的子孫砍不到；砍完 kernel 會馬上再拉一顆新的。

## 1. 開第二個 kernel 家 K2

花錢的池放在另一個 kernel 家，跟 01 開的 `K` 共用同一個 daemon。範本在 `proto5/templates/cli-agents/`：

```sh
T=$PWD/proto5/templates/cli-agents
sed "s|@W@|$W|g" $T/kernel2.json > $W/kernel2.json
aos-kernel init --target $W/K2 --config $W/kernel2.json
aos-kernel boot --target $W/K2
aos-kernel ls --target $W/K2
```

你會看到 `booted 4 cpus`，`ls` 的 cpu 表是 `kernel k2`、`claude cc`、`codex cx0 cx1`。

- **kernel 池那顆叫 `k2`，不能叫 `k`**：`K` 已經有一顆 `k` 掛在同一個 daemon 上，同名會被 daemon 拒絕（`NameTaken`）。其他 cpu 名也不能跟 `K` 的撞。
- 範本讓 `cc`、`cx0`、`cx1` 三顆 **從空環境開始**，只帶 `PATH`、`HOME`、`LANG`（codex 再多 `CODEX_HOME`）：環境裡剛好有 API 金鑰也帶不進去（免得改走付費 API）。你要靠代理（`HTTPS_PROXY`）之類才連得上網，就在 `$W/kernel2.json` 那幾顆的 `$val` 裡逐項補回，再 `init`。
- `aos-kernel check --target $W/K2` 會報 `bad pools: llm 池沒有 cpu`：K2 本來就不放 llm cpu，這條忽略。

## 2. codex 專用的設定資料夾

不讓 codex 讀你自己的 `~/.codex/config.toml`（你那份可能開了 `danger-full-access`）和 `AGENTS.md`，給它一個只放登入的資料夾：

```sh
mkdir -p $W/codex-home
ln -s $HOME/.codex/auth.json $W/codex-home/auth.json
```

用**符號連結**，不要複製：登入過一陣子會換新的憑證，複製一份的話兩邊可能有一邊失效。（連結也不是萬無一失：codex 換憑證時若是「寫新檔再改名」，連結會變成一般檔。偶爾 `ls -l $W/codex-home/auth.json` 看它還是不是 `->`。）
這只隔開你家目錄那份設定；工作區自己的 `AGENTS.md` 它照讀。claude 這邊不用另開資料夾，單子範本裡的 `--safe-mode` 讓它不讀你的 CLAUDE.md、記憶、skill 和 hook。

## 3. 丟一張 codex 唯讀審查單

每張單子一個資料夾，放任務書 `task.md` 和 `inst.json`；結果寫在它底下的 `out/`。

```sh
J=$W/cli-jobs/review-ls; mkdir -p $J
echo '唯讀審查 proto5/tools/base/ls，找真的會出錯的地方，每條一句附行號，≤800 字。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$PWD|g" $T/codex-review.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool codex --timeout-ms 600000
```

`add` 印兩樣：**單名**和回音會出現的路徑，例如 `cli-1790…-1081994.json /home/you/aos-try/K2/responses/cli-1790…-1081994.json`。

- **`--pool codex`** 讓它排到 codex 的 cpu；**`--timeout-ms`** 一定要給（範本 K2 預設 30 分鐘），到了就砍。
- 路徑一律絕對：inst 裡的 `stdin`、`stdout` 是相對 `cwd`（這裡是你的 repo），不是單子資料夾，所以範本全用 `@JOB@` 換成絕對路徑。
- **不要**帶 `--wait-ms 0`，那是「馬上逾時」不是「不等」；想等就給夠長，例如 `--wait-ms 700000`。

約一分鐘後回音到了：

```sh
cat /home/you/aos-try/K2/responses/cli-…json      # 換成你看到的路徑
aos-kernel ack cli-…json --target $W/K2            # 用單名 ack，不是 --name
cat $J/out/answer.md
```

回音長這樣：`{"code": 0, "kind": "child", "timed_out": false, "stopped": false, "ms": 55918}`。
**成功要兩層都過**：回音的 `kind` 是 `child`、`code` 0、`timed_out` 和 `stopped` 都是 `false`；再看 `$J/out/events.jsonl` 有 `"type":"turn.completed"`、沒有 `turn.failed`。答案在 `out/answer.md`。

## 4. 丟一張 claude 單

```sh
J=$W/cli-jobs/c1; mkdir -p $J $W/cli-ws
echo '只回 ok 兩個字，不要用任何工具。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$W/cli-ws|g" $T/claude-job.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool claude --timeout-ms 300000 --wait-ms 330000
cat $J/out/result.json
```

`result.json` 是一個 JSON，要看的欄位：`is_error`（`false` 才算成功）、`result`（它的回答）、`session_id`（接著聊要用）、`total_cost_usd`（照定價算的花費，訂閱也會印）。

範本的旗標都是保守的：`--restricted` 拿掉會跑程式的工具（Bash 等），檔案工具只能碰 `@WS@`；會問人的動作沒人回答就一律拒絕；最多 8 輪；超過 0.5 美元就停（訂閱登入也有效；它是呼叫完才算，所以擋不住第一次呼叫）。
要它跑測試得拿掉 `--restricted`、加 `--allowedTools "Bash(make test)"`——**這等於准它跑工作區裡的任意程式**（它可以先改 Makefile 再跑），只在你信得過工作區時這樣做。「跳過權限」那類旗標**不要加**，牢做好之前都不用。

## 5. 接著聊：從上一次成功的那次分岔

每次都從**上一次成功的**對話分岔一條新的（fork），失敗、逾時、被砍的那次不算：

「成功」照第 3 步的兩層：回音 `kind` child、`code` 0、沒逾時沒被停，**而且** `result.json` 的 `is_error` 是 `false`、`subtype` 是 `success`。

```sh
S=0c31125f-…     # c1 的 result.json 裡的 session_id（c1 兩層都過）
J=$W/cli-jobs/c2; mkdir -p $J
echo '剛才你回了什麼？只回那兩個字。' > $J/task.md
sed -e "s|@JOB@|$J|g" -e "s|@WS@|$W/cli-ws|g" -e "s|@SESSION@|$S|g" $T/claude-next.json > $J/inst.json
aos-kernel add $J/inst.json --target $W/K2 --once --pool claude --timeout-ms 300000 --wait-ms 330000
```

它記得上一次，回 `ok`，`session_id` 是一個新的。codex 用 `codex-review-next.json`，`@SESSION@` 換成上一次 `events.jsonl` 第一行的 `thread_id`（那次要有 `turn.completed`）。
哪個 id 是「上一次成功的」要你自己記（例如寫進 `$W/last-ok-session`）；以後的 `aos-cli` 會替你記。

## 6. 取消

先試免費的：在 claude 池放一張 `sleep 77`，再撤掉它。

```sh
mkdir -p $W/cli-jobs/s; echo '{"argv": ["sleep", "77"]}' > $W/cli-jobs/s/inst.json
aos-kernel add $W/cli-jobs/s/inst.json --target $W/K2 --once --pool claude --name s1
sleep 3; aos-kernel rm s1 --target $W/K2
pgrep -a -f "^sleep 77"
```

`rm` 自己印 `s1`；當初 `add` 那張單的回音（`K2/responses/cli-….json`）變成 `Removed`。但 `pgrep` 還看得到 `sleep 77`——**它還在跑**（換成 claude 就是還在花錢、還在改檔）。要真的停，叫 daemon 砍那顆 cpu：

```sh
D=$AOS_DAEMON_HOME
printf '{"jsonrpc":"2.0","id":"kill-cc","method":"kill","params":{"name":"cc"}}\n' > $D/requests/.kill-cc.tmp
ln $D/requests/.kill-cc.tmp $D/requests/kill-cc.json; rm $D/requests/.kill-cc.tmp
```

daemon 的回音只代表「收到、開始停」，不代表已經停了。它先請 cpu 溫和停，5 秒後對 cpu 送 TERM、cpu 再砍那張單子的程式那一組（還不死再過 5 秒 KILL）。用 `pgrep` 確認：這次約 5 秒後 `sleep 77` 才不見；程式自己脫離那一組的子孫砍不到，要另外查。之後 kernel 馬上再拉一顆新的 `cc`。
回音在 `$D/responses/kill-cc.json`（`{"result": {"pid": …}}`）；不簽收也只是留著一個檔，要簽就往 `$D/requests/` 放一張 `ack-kill-cc.json`，內容 `{"jsonrpc":"2.0","method":"ack","params":{"name":"kill-cc.json"}}`（放法同上，先寫 `.tmp` 再 `ln`）。
**小心砍錯**：從你查到「單子在 cc 上」到真的砍下去之間，它可能已經跑完、換跑下一張了。

## 底下在幹嘛

- **沒有新種類的 cpu**：`cc`、`cx0`、`cx1` 跟 01 的 `0`、`1` 是同一支 `aos-cpu`，差別只在池名和環境。單子就是一份普通的 inst.json，argv 是 `claude -p …` 或 `codex exec …`，任務書從 stdin 餵、結果寫進 stdout 指的檔。（[提案 as-cpu](../notes/2026-09-24-cli-agents/as-cpu.md)）
- 所以 kernel 派單、daemon 拉起與重拉、逾時砍整組，全照 01、02 學到的走。
- **不要把 claude／codex 單子登記成反覆的**（不帶 `--once`）：反覆的失敗了會被排回去再跑＝重花一次錢、重改一次檔。
- 範本的旗標與成功怎麼判，整理在 [templates/cli-agents](../templates/cli-agents/README.md)；這次真跑查到的事在 [stage0 報告](../notes/2026-09-24-cli-agents/stage0.md)。

## 常見錯誤

| 看到 | 原因與怎麼辦 |
|---|---|
| `boot` 印 `NameTaken` | K2 的 cpu 名跟 `K` 撞了（最常見是 kernel 池那顆也叫 `k`）。`halt` K2、`rm -rf $W/K2`、改名重來 |
| 回音 `"code": 127` | daemon 開起來時的 PATH 找不到 `claude`／`codex`。它們在 `~/.local/bin` 之類的地方時，開 daemon 前先 `export` 好 |
| `ack` 印 `NotFound` | ack 要用 `add` 印的**單名**（`cli-….json`），不是 `--name` 給的名字 |
| codex 的 `err.log` 有 `Refusing to create helper binaries under temporary dir "/tmp"` | `codex-home` 放在 `/tmp` 底下；只是警告，照跑。放家目錄底下就沒有 |
| claude 的 `result.json` 是 `"subtype": "error_max_budget_usd"` | 超過 `--max-budget-usd`，回音 `code` 是 1。調高範本的數字，或把任務切小 |
| `aos-kernel halt --target $W/K2` 報 `Timeout` | 有單子還在跑（halt 只等 30 秒）。等它跑完，或照第 6 步砍 cpu |

## 收工

```sh
aos-kernel halt --target $W/K2
```

印 `stopped` 才算停好（報 `Timeout` 就是還有單子在跑，先別刪）。K 和 daemon 照 [01 第 7 步](01-daemon-kernel.md#7-關機順序kernel--daemon)關。
整個重來：確認停好後 `rm -rf $W/K2 $W/cli-jobs $W/codex-home $W/cli-ws $W/kernel2.json`——只刪這篇建的，`$W` 裡其他教程的東西別動。
