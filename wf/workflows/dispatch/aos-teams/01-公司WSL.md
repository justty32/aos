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

## 沙箱

`~/.codex/config.toml` 沒設 `danger-full-access`，codex 隊員寫檔用 `-s workspace-write`（它自己的沙箱）。09-22 那條「公司那台用 `--dangerously-bypass-approvals-and-sandbox`」11-06 作廢。

## 監看門檻

頂層開一個背景監看，每 30 秒看一次，**超過任一門檻才通知**：load average＞6.5（8 核）、`MemAvailable`＜3 GiB、`codex exec`／`claude -p` 程序＞5。通知了就叫各隊收斂子 agent 或輪流跑。三個數字的取法：

```
cat /proc/loadavg; grep MemAvailable /proc/meminfo; pgrep -fc '[c]odex exec|[c]laude -p'
```

（pattern 寫成 `[c]odex` 是為了不把包這行指令的 `bash -lc` 自己算進去。）門檻是頂層 11-06 代定、可翻案。codex 現在是原生執行檔、不吃 node，但「每隊兩個 CLI 程序」照舊算它一個。
