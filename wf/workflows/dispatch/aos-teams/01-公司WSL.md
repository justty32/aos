# 公司那台（WSL）的 codex、claude 隊員與監看門檻（2026-11-06）

← [入口](../aos-teams.md)｜下一份 [02-指令沙箱與試玩](02-指令沙箱與試玩.md)

隊形、子 agent 規則、程序數與權限邊界是跨機通用的，在[入口](../aos-teams.md)；這裡只記公司這台特有的。

## codex：直接叫 `codex` 就是新版

- 原本有兩支：舊的 `~/.codex/packages/standalone`（0.153.4，非互動 `bash -lc` 會抓到它，不認得 `gpt-6.1-sol` 等新模型，上午因此誤判「不支援」），**11-06 08:15 經使用者同意刪除**。使用者原話：「gpt-6.1-sol用不了？我直接開wsl ubuntu，跑codex，模型預設就是gpt-6.1-sol」。
- 現在 `~/.local/bin/codex` 是捷徑，指向 nvm 那份 codex（0.166.0）裡**不需要 node 的原生執行檔** `~/.nvm/versions/node/v24.19.0/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex`——nvm 的 `bin/codex` 是 node 腳本，非互動 shell 沒有 node 會失敗。所以 agent **直接叫 `codex`** 即可。
- **nvm 升級 node 或 codex 後這條捷徑要重指**（`ln -sf <新的原生執行檔> ~/.local/bin/codex`），否則會指到不存在的路徑。
- 新版實測可用：`gpt-6.1-sol`、`gpt-6-sol`、`gpt-6-luna`、`gpt-6-astra`、`gpt-5.6-sol`／`-terra`／`-luna`（`gpt-5.5` 只在舊版測過、未重測）。`~/.codex/config.toml` 預設 `gpt-6.1-sol`，但照通則一律明帶 `-m`。

## claude 隊員：另一個帳號

`~/.local/bin/claude`（Claude Code 2.1.318）登入的是**另一個帳號**，跟頂層不同額度。`claude -p --model claude-opus-5-5 '…' </dev/null` 實測可用；權限照入口用 `--permission-mode acceptEdits`＋`--allowedTools`。

## fable 走 WSL claude（只限公司）

使用者 11-06：「這次fable好了之後，下次開fable，請走wsl claude。額度消耗的有一點快，我稍微有點憂心...不過重點在於只要不開fable，只靠opus那其實還是很充裕」，接著補「這只是在公司這邊才這樣做。」

所以**在公司**要 fable 時不開 Claude Code 自家的 fable subagent，改在 WSL 跑 `claude -p '<提示>' --model claude-fable-5-1 --permission-mode acceptEdits --allowedTools '<工具,逗號連>' </dev/null`（11-06 實測可用）；提示裡照樣要它先通讀 wf/ 規矩，它可用自己的 Agent 工具再派 fable 子 agent。超過 10 分鐘的在 WSL 內 `setsid nohup … > log 2>&1 &` 脫離、等 log。自家 subagent（隊長、雜活）照舊 opus／sonnet。**家機不受這條影響**，照舊用自家 fable subagent。

## 沙箱

`~/.codex/config.toml` 沒設 `danger-full-access`，codex 隊員寫檔用 `-s workspace-write`（它自己的沙箱）。09-22 那條「公司那台用 `--dangerously-bypass-approvals-and-sandbox`」11-06 作廢。

## 監看門檻

頂層開一個背景監看，每 30 秒看一次，**超過任一門檻才通知**：load average＞6.5（8 核）、`MemAvailable`＜3 GiB、`codex exec`／`claude -p` 程序＞5。通知了就叫各隊收斂子 agent 或輪流跑。三個數字的取法：

```
cat /proc/loadavg; grep MemAvailable /proc/meminfo; pgrep -fc '(^|/)codex exec'; pgrep -fc '(^|/)claude -p'
```

（pattern 開頭的 `(^|/)` 是為了不把外層 `bash -lc` 算進去。）門檻是頂層 11-06 代定、可翻案。codex 現在是原生執行檔、不吃 node，但「每隊兩個 CLI 程序」照舊算它一個。

**效能標準（11-06 起）**：使用者 11-06 原話「效能監看這塊我們今天測一整天看看狀況，然後訂下一個標準，設定在公司這邊能最多開幾個。」今天整天收數據、收工前依數據訂「公司這台最多同時開幾個 codex／claude」，訂了寫回本段。記錄檔在 Windows `C:\Users\WG-Guanyu\aos-perf\`（WSL `/mnt/c/Users/WG-Guanyu/aos-perf/`）：

- `wsl-2026-11-06.csv`：每 30 秒一列，load、可用記憶體、codex／claude 程序數、這些 CLI 合計 CPU% 與記憶體；腳本 `wsl_perf_log.sh`，WSL 背景 pid 198864。
- `win-2026-11-06.csv`：Windows typeperf，每 30 秒整機 CPU% 與可用 MB，pid 39196，跑 12 小時自停。

**保險絲：之後跑高佔用工作時再做。**使用者 11-06 原話「除此之外你看看要不要設立一個保險絲，在佔用達到95%的時候砍掉東西。現在先不用，因為老實說單跑agent做文字處理，不太可能達到這種狀況。等之後我們有要跑高占用的東西的時候再來做」。

**兩個坑（11-06 實測）**：
- `claude -p` 的 `--allowedTools` 會吃掉後面所有參數：提示要放在 `-p` 後第一個，工具清單用逗號串成一個參數。
- codex 的 `-s workspace-write` 沙箱寫不了 `~/dev/vcpkg` 的鎖，`cmake -B build` 會失敗：讓 codex 只改檔，configure／build 由隊長在沙箱外跑（P2 時 codex 自己帶了 `-DVCPKG_MANIFEST_INSTALL=OFF`，隊長之後已改回 `=ON` 重新 configure）。
