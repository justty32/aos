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

## fable 走 WSL claude：使用者說了才走

使用者 11-06 先說：「這次fable好了之後，下次開fable，請走wsl claude。額度消耗的有一點快，我稍微有點憂心...不過重點在於只要不開fable，只靠opus那其實還是很充裕」「這只是在公司這邊才這樣做。」接著改口：「喔不，呃，不要"一律"，就，依據實際情況吧，我說走wsl claude 才走。因為wsl claude是公司帳號的。」

所以：**預設照舊開 Claude Code 自家的 fable subagent**（盡量少開，fable 吃額度快、opus 很充裕）；**使用者明說「走 wsl claude」那次才改走 WSL**——WSL 的 claude 是公司帳號。走法：`claude -p '<提示>' --model claude-fable-5-1 --permission-mode acceptEdits --allowedTools '<工具,逗號連>' </dev/null`（11-06 實測可用），提示裡照樣要它先通讀 wf/ 規矩、可再用自己的 Agent 工具派 fable 子 agent；超過 10 分鐘的在 WSL 內 `setsid nohup … > log 2>&1 &` 脫離、等 log。

## 沙箱

`~/.codex/config.toml` 沒設 `danger-full-access`，codex 隊員寫檔用 `-s workspace-write`（它自己的沙箱）。09-22 那條「公司那台用 `--dangerously-bypass-approvals-and-sandbox`」11-06 作廢。

## 監看門檻

每 30 秒看一次，超門檻才通知；程序數依下段情境判定。load 指 `/proc/loadavg` 第一欄（1 分鐘平均），記憶體同看 WSL `MemAvailable` 與 Windows `Available MBytes`。WSL 取法：

```
cat /proc/loadavg; grep MemAvailable /proc/meminfo; pgrep -fc '(^|/)codex exec'; pgrep -fc '(^|/)claude -p'
```

`pgrep -f` 仍可能算到帶相同字串的 wrapper；數字異常時核對實際程序，不直接按計數砍程序。只算 agent 的非互動 CLI，不動使用者自己的程序；每隊規則仍照[入口](../aos-teams.md)。

## 效能上限（11-06 實測）

使用者原話（11-06；上午一句一併保留，提醒公司工作優先）：

> 13:40：「分不乾淨沒關係，我在公司就是一邊做我的事情，你這邊就是附帶」
>
> 14:30：「我現在沒在處理別的事。都用cli吧」
>
> 15:55：「沒關係的，可以加開，我現在沒在幹嘛。」
>
> 上午：「那幾個高loading是我在處理公司的事情，很重要，別動。」

**以下是全機 agent CLI 合計，不是每隊額度；codex／claude 合併算。**

- **使用者在做事：最多 3 個；不確定有沒有在忙，也用 3 個。**依 09:48～14:30 混合工作窗：3～4 個的 79 筆樣本，load p95 7.93、Windows CPU p95 87.91%；0 個時 load 也曾 11.15。3 是保守暫定，不能把公司工作的高載怪給 agent。
- **使用者明說閒著：常態最多 6 個；只做文字／等 API 時，暫定可加到 8 個。**15:48:25～15:54:34 的 6 個共 7 筆，load 最高 2.44；15:49:57～15:58:40 的 7～8 個共 14 筆，load 中位／p95／最高 2.52／2.98／3.02、Windows CPU 最高 56.90%，WSL／Windows 可用最低 11.80／3.42 GiB。14 筆全是 codex，其中 15:55 後只有 8 筆；長時間與 claude 大量並開未驗證。**超過 8 個資料不足，不訂更高上限**。每 CLI 約 300 MiB 是中午粗估，不能用記憶體除法推上限。
- **有 C++ 建置：CLI 暫定最多 2 個，建置一次一個、`-j2`。**用 `flock /tmp/aos-build.lock nice -n 15 cmake --build … -j2`。11:23～11:28、11:32～11:37 疑似建置窗共 20 筆，load p95／最高 8.55／8.71、Windows CPU p95／最高 93.44／98.35%。CSV 沒有命令起迄，2 個加建置的餘裕未獨立驗證，不能當作保證。
- **`git gc`、全庫大正則搜尋也當重操作：`nice -n 15`、一次一個，與建置共用同一把鎖，不能重疊；搜尋先限路徑、範圍。**14:33～14:44 只有 2～4 個 CLI，load 仍曾 9.34、Windows CPU 在 14:30～15:55 最高 98.52%；只能確認有高載，無法由 CSV 認定是哪個命令。重操作併發上限資料不足，暫定 1。

**警報與處理（保守暫定，不是實測失速點）：**

- **load：做事／狀態未知時＞6.5，閒著時＞8，就停止加開、延後 agent 重操作。**前者沿用留餘裕門檻；後者沿用 14:30 放寬值（這台 WSL 8 核），今天 7～8 個輕工作最高僅 3.02。高 load 可能是公司工作，**不停止、不調整使用者程序**。
- **記憶體：WSL 或 Windows 任一可用＜3 GiB 就警報、停止加開。**Windows 換算為＜3072 MiB；今天 WSL 最低仍有 11.60 GiB，Windows 卻到 1.24 GiB（10:33:56），不能只看 WSL。Windows 3 GiB 是保守餘裕；WSL 3 GiB 今天沒碰到，資料不足，沿用暫定。
- **Windows CPU＞95% 連續 3 筆也停止加開；CLI 超過當時 3／6／8（建置時 2）的上限就收斂。**警報後等 3 筆都回到當時 load 門檻內、兩邊可用≥4 GiB、Windows CPU≤95%，再逐個恢復；加到第 7、8 個前另確認 load＜3、兩邊可用≥4 GiB、沒有重操作。4 GiB／3 筆是避免反覆開關的暫定緩衝，未驗證；不自動砍程序。

資料：`/mnt/c/Users/WG-Guanyu/aos-perf/{wsl,win}-2026-11-06.csv`；排除早期計數異常，取 08:39:16～16:25（WSL 918 筆、Windows 933 筆）。09:48～14:30 是混合窗，午間狀態未知；閒著依 14:30／15:55 原話判定。CPU 用 Windows 整機值，WSL 的 CLI CPU 是生命週期平均加總，不能當瞬時 CPU。完整切法、分佈與限制在本機 `/tmp/teamPerf/analysis.md`；repo 只留本段結論。

**保險絲：之後跑高佔用工作時再做。**使用者 11-06 原話「除此之外你看看要不要設立一個保險絲，在佔用達到95%的時候砍掉東西。現在先不用，因為老實說單跑agent做文字處理，不太可能達到這種狀況。等之後我們有要跑高占用的東西的時候再來做」。

**兩個坑（11-06 實測）**：
- `claude -p` 的 `--allowedTools` 會吃掉後面所有參數：提示要放在 `-p` 後第一個，工具清單用逗號串成一個參數。
- codex 的 `-s workspace-write` 沙箱寫不了 `~/dev/vcpkg` 的鎖，`cmake -B build` 會失敗：讓 codex 只改檔，configure／build 由隊長在沙箱外跑（P2 時 codex 自己帶了 `-DVCPKG_MANIFEST_INSTALL=OFF`，隊長之後已改回 `=ON` 重新 configure）。
