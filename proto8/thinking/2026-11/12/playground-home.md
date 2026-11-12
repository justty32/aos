# 家機試驗場整個重建（11-12 晚）：照 main `15e7f8225` 清空重抄四隻（fsm_ann gemma、eca_bob haiku、eca_opus opus、eca_cody gpt-6-luna），假腦整套、gemma／haiku／luna 各一句都過，樹已停

← [11-12 日索引](README.md)｜公司版 [playground](playground.md)｜上一次家機 [11-11 playground 02](../11/playground/02-家機刷新與驗收.md)

## 使用者原文

- 「我沒在跑，試驗場那邊也可以全清空。」（經頂層轉述；只限 `~/code/playground`）

## 結論

- 家機 `~/code/playground` **整個刪掉重建、沒有備份**（`env.sh`、`root/`、`daemon/`、`ws/proj/`、`ws/hooks/` 也不留）。結構照 11-12 公司那份＋[ops-notes-to-aos 從零搭一棵小樹](ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做) 的根與領班寫法；家機特有的照 11-11 家機那份（`stupid-fast`＝LM Studio `google/gemma-4-e4b`、litellm `luna`／`terra`／`sol` 可換）。
- 四隻：`fsm_ann`（agent-fsm，46 支，定義寫 `stupid-fast`）、`eca_bob`（haiku，25 支）、`eca_opus`（opus，25 支）、`eca_cody`（codex `gpt-6-luna`、`workspace-write`、有畫面，25 支）；hooks 都是 `mail_notify`＋`timer`；eca 三隻都不設花費上限。總機多一個劇本假腦 `fake-demo-json`。
- 複製的 `lib py templates knowledge` 跟 git `15e7f8225` 逐檔相同（工作樹裡另一條線還沒 commit 的 `lib/mcp_client.py` 與兩支測試檔抄進來後刪掉；它 19:00 前後以 `847f54433` 進 main，是還沒接上工具的模組，下次重抄才有）。指令是 `~/.local/bin` 的 symlink，指回 `~/repo/simple_tools/aos`；`aos-mcp-launch` 已在、`aos-daemon`／`aos-json` 的 bin 是 11-12 18:49 建的（另一條線建，本次沒 build、沒跑 install.sh）。
- **樹已停**：四隻掛好、對話是空的（stack 裡沒有 history）、根與領班都 `stopped`，掃 `/proc` 沒有試驗場底下的行程。怎麼玩看試驗場 `README.md` 最上面三行（起／講話／停）。

## 驗收（11-12 18:58～19:00，家機）

| 步 | 結果 |
|---|---|
| 開工前 | 舊樹 `state.json` stopped、沒有試驗場底下的行程，不用先停 |
| 起根、三台 ping、掛四隻 | 根表 `_clock _sweeper llm_kernel daemon` running；四隻 running；`tools ls` fsm_ann 46、eca 三隻各 25；`hook ls` 都是 `mail_notify`、`timer` |
| 假腦 `fake`（臨時 fsm_fake） | `FAKE ANSWER to: what time is it? (tool said: 2026-11-12T10:58:45Z)` |
| 劇本 `fake-demo-json`（臨時 fsm_demo） | history 照劇本：json_set `demo.json` → json_get 回 `"world"` → json_set `_index.json` → index_view 回 `[index] ./_index.json, 1 entry` 那一項 |
| gemma（fsm_ann） | 叫 peek_now_time，約 17 秒答 `The current time is 2026-11-12T10:59:18Z.`（LM Studio 伺服器開著、模型 JIT 載入） |
| haiku（eca_bob） | 叫 `mcp__aos__peek_now_time`，答時間；`claude-haiku-5-5`、0.005 美金、`permission_denials` 空 |
| codex luna（eca_cody） | `mcp_tool_call server aos tool peek_now_time`，答時間；codex 紀錄 `model gpt-6-luna`、`cwd …/playground/ws`、`sandbox_policy workspace-write` |
| opus（eca_opus） | 只核到 `llm ls -l` 是 `model=opus definition`（flags 由 stack_copies 換成 `--model opus`），沒實問 |
| 收尾 | 六隻 `ctl rm --purge`、`shutdown`：`4 procs asleep`，沒有殘留行程；清兩層 stack、總機帳本、`ws/` 內容 → 起根、掛四隻（沒有 history）→ `shutdown`，沒有殘留行程 |

沒驗：`aos-agent chat` 與畫面（`aos-agent open`）、eca_opus 實問、新信提醒、litellm `luna`／`terra`／`sol` 經 fsm_ann（proxy `/v1/models` 有這三個名字）、外部 MCP（`cli.json` 沒列 `mcp_servers`）、eca slash。

## 看到的事（沒修）

- **claude 對 `~/code/playground/ws` 沒有信任**（`~/.claude.json` 那個路徑 `hasTrustDialogAccepted: false`）：`say`／`chat` 走 `claude -p` 不受影響；開畫面前要使用者在 `ws/` 手動開一次 `claude` 選信任，不然那隻報 `TrustMissing`、信留著。codex 畫面沒驗。
- **codex 那隻會連使用者全域 `~/.codex/config.toml` 裡的 MCP server**：`eca_cody/stderr.txt` 每輪多兩三行 rmcp `AuthRequired`（context7、githubcopilot 沒登入）。回答不受影響；claude 那邊有 `--strict-mcp-config`、codex 這邊沒有對應的隔離。是不是要擋，沒判斷。

## 代定

- 根照 `templates/daemon-root`（`procs_requests`、`_clock`、`_sweeper`）加 `llm_kernel`、`daemon` 兩列，列名沿用舊試驗場（README、WAIT_USER 的指令不用改）；`root/.env` 只寫 `AOS_CLOCK` 一行（`AOS_LLM_KERNEL`、`AOS_HOME` 由 `env.sh` 給）。
- 領班照 ops-notes 第 ⑤ 步（`interval_ms 200`、`procs_requests`、`_sweeper`）。
- `env.sh` 照舊家機那份（PATH 墊 repo 的 bin、`AOS_LLM_KERNEL`、`AOS_HOME`、清 `CLAUDE*`），沒有 `AOS_KNOWLEDGE`。
- 花費上限：eca_bob、eca_opus 都不設（跟公司 11-12 中午「都先幫我設置無上限吧」一致；11-11 家機是 eca_bob 20 美金）。要回 20 美金照試驗場 README 一行改。
- 四隻都建（照公司 11-12 成員）；11-11 家機的 `ws/hooks` 兩支例子（ping_me、up_down）與 `ws/proj/calc.py` 不再建（公司 12:45 也清空 `ws/`）。
- eca 那幾隻不加 `system.txt`（照公司那份；要讓它知道 knowledge 在哪可照 ops-notes 第 ⑦ 步）。
- 工作樹裡別條線還沒 commit 的檔不抄進試驗場。

<details><summary>照抄（整個重建）：存成檔再 <code>bash 檔名</code></summary>

```sh
# pghome-rebuild.sh - wipe ~/code/playground and rebuild it from this machine's repo main (home Manjaro, 11-12 evening)
set -eu
PG=$HOME/code/playground
R=$HOME/repo/simple_tools/aos/proto8
cd "$HOME"
[ -f "$PG/env.sh" ] && [ -f "$PG/root/daemon.json" ] || { echo "not a playground: $PG"; exit 1; }
# nothing may still run under the playground
for p in /proc/[0-9]*; do n=${p#/proc/}; [ "$n" != "$$" ] || continue
  c=$(readlink "$p/cwd" 2>/dev/null || true); a=$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null || true)
  case "$a" in *"/.vscode-server/"*|*pghome-rebuild*) continue;; esac
  case "$c/ $a" in "$PG"/*|*" $PG"/*|*"=$PG"/*) echo "still running under $PG: $n $a"; exit 1;; esac; done
# 1) wipe (user 11-12: "試驗場那邊也可以全清空"), no backup
rm -rf "$PG"
mkdir -p "$PG"/root "$PG"/daemon "$PG"/agents "$PG"/ws "$PG"/llm_kernel
cd "$PG"
# 2) the four copies
cp -r "$R/lib" "$R/py" "$R/templates" "$R/knowledge" .
find lib py templates knowledge -name __pycache__ -prune -exec rm -rf {} +
find lib py templates knowledge -type d -empty -delete
# 3) env.sh (home: impls/cmd bins of this repo on PATH as fallback; AOS_HOME = the playground; no AOS_KNOWLEDGE)
cat > env.sh <<'EOF'
# env.sh - playground environment (home Manjaro). Usage: cd ~/code/playground && source env.sh
# PATH: the aos-* commands of this machine's repo (impls must be built; proto8/install.sh already links them into ~/.local/bin,
#   this is only a fallback). AOS_LLM_KERNEL = the llm kernel daemon's stack (llm_kernel/), where every brain question is mailed.
# AOS_HOME = this playground (definitions use {"$env": "AOS_HOME", ...}: lib/ py/ templates/ knowledge/ here).
# The root daemon supervises the clock, the llm kernel and the agent daemon; source this file before aos-exec root.
# The agent daemon's stack is ws/.stack (aos-agent finds ./.stack when you are in ws/), so AOS_DAEMON is not set here.
# CLAUDE* variables are removed so the claude started under the daemon does not mix with a Claude Code session.
R=/home/lorkhan/repo/simple_tools/aos/proto8
if [ -n "${BASH_VERSION:-}" ]; then _f=${BASH_SOURCE[0]}; else _f=${(%):-%x}; fi   # this file, in bash or zsh
PG=$(cd "$(dirname "$_f")" && pwd); unset _f   # the playground = where this env.sh is (works after a move)
for p in $R/impls/*/bin $R/cmd/*/bin; do PATH=$p:$PATH; done
export PATH
export AOS_LLM_KERNEL=$PG/llm_kernel
export AOS_HOME=$PG
unset AOS_KERNEL AOS_DAEMON AOS_STACK AOS_WS AOS_AGENT AOS_CLOCK   # AOS_CLOCK comes from root/.env (the root clock)
for v in $(env | grep -oE '^(CLAUDE[A-Z_]*|AI_AGENT)='); do unset "${v%=}"; done
unset v p R
EOF
# 4) root daemon := templates/daemon-root + the llm kernel and the agent daemon as two more rows
cp templates/daemon-root/_entry templates/daemon-root/daemon.json root/
chmod +x root/_entry
printf '%s\n' 'AOS_CLOCK=${AOS_STACK}/clock' > root/.env
aos-json set root/daemon.json#/description '"Playground root: the clock, the sweeper, the llm kernel and the agent daemon (ws/)"'
aos-json set root/daemon.json#/procs/llm_kernel '{"exec": "../llm_kernel/def", "stack": "../llm_kernel", "ws": "../llm_kernel", "auto_restart": true}'
aos-json set root/daemon.json#/procs/daemon '{"exec": "../daemon", "stack": "../ws/.stack", "ws": "../ws", "auto_restart": true}'
# 5) agent daemon (foreman), as in ops-notes-to-aos step 5
cat > daemon/_entry <<'EOF'
#!/bin/sh
# Foreman entry: cd to the workspace the root gave (AOS_WS) and become the agent daemon (exec keeps the pid).
cd "$AOS_WS" && exec aos-daemon --enable-logs "$AOS_CD/daemon.json"
EOF
chmod +x daemon/_entry
echo '{"interval_ms": 200, "procs_requests": "procs_requests", "procs": {"_sweeper": {"exec": {"argv": ["aos-sweeper", "--retention-days", "7", "--report", {"$env": "AOS_STACK", "$path": "sweeper_report.json"}]}, "interval_ms": 600000, "auto_restart": true, "stuck_after_ms": 600000}}}' > daemon/daemon.json
# 6) llm kernel := the repo's; stupid-fast = this machine's LM Studio gemma; one scripted fake brain for the json tools
cp -r "$R/kernel/llm-kernel" llm_kernel/def
find llm_kernel/def -name __pycache__ -prune -exec rm -rf {} +
aos-json set 'llm_kernel/def/kernel.json#/endpoints/stupid-fast/model' '"google/gemma-4-e4b"'
aos-json set 'llm_kernel/def/kernel.json#/endpoints/stupid-fast/summary' '"LM Studio gemma-4-e4b on this machine (home Manjaro): quick and rough, one at a time"'
aos-json set 'llm_kernel/def/kernel.json#/endpoints/fake-demo-json' '{"exec": {"$env": "AOS_HOME", "$path": "/lib/base/llm_fake"}, "speed": "fast", "cost": "free",
 "summary": "playground fake brain for 11-12: writes demo.json with json_set, reads one key back with json_get, writes an index entry for it, looks at it with index_view",
 "script": [{"tool_calls": [{"name": "json_set", "arguments": {"path": "demo.json", "value": {"hello": "world", "n": 1}}}]},
            {"tool_calls": [{"name": "json_get", "arguments": {"path": "demo.json#/hello"}}]},
            {"tool_calls": [{"name": "json_set", "arguments": {"path": "_index.json", "value": {"demo.json": {"description": "a file the fake brain wrote"}}}}]},
            {"tool_calls": [{"name": "index_view", "arguments": {"path": ".", "key": "demo.json"}}]},
            {"content": "I wrote demo.json, read hello back, wrote its index entry into _index.json and looked at it with index_view."}]}'
# 7) four agents := fresh templates
cp -r "$R/templates/agent-fsm" agents/fsm_ann
cp -r "$R/templates/eca-claude" agents/eca_bob
cp -r "$R/templates/eca-claude" agents/eca_opus
cp -r "$R/templates/eca-claude" agents/eca_cody
find agents -mindepth 2 -maxdepth 2 \( -name tests -o -name __pycache__ \) -exec rm -rf {} +
echo '{"model": "stupid-fast"}' > agents/fsm_ann/llm.json      # gemma in the definition; llm set model=luna / terra / sol / fake
echo '{"model": "haiku"}' > agents/eca_bob/llm.json
aos-json set agents/eca_bob/cli.json#/print_flags '[]'          # no spending cap (as the company playground, user 11-12 noon)
echo '{"model": "opus"}' > agents/eca_opus/llm.json
aos-json set agents/eca_opus/cli.json#/print_flags '[]'
echo '{"model": "gpt-6-luna"}' > agents/eca_cody/llm.json
cat > agents/eca_cody/cli.json <<'EOF'
{"kind": "codex",
 "flags": ["-c", "sandbox_mode=\"workspace-write\"", "-c", "approval_policy=\"never\""],
 "print_flags": [],
 "timeout_ms": 600000}
EOF
aos-json set agents/eca_cody/_metainfo.json#/summary '"Run Codex CLI (gpt-6-luna; llm set model=gpt-6.1-terra / gpt-6.1-sol) as an aos agent: one turn per queue batch, answers appended to history; aos-agent open shows its screen."'
echo "rebuilt: $PG (agents: $(ls agents | tr '\n' ' '))"
```

重建後起樹、掛四隻（根放背景）：

```sh
cd ~/code/playground && source env.sh && (setsid nohup aos-exec root > root.log 2>&1 < /dev/null &)
cd ws && aos-daemon-ctl -d ~/code/playground/.stack ping --timeout-s 30 && aos-daemon-ctl ping --timeout-s 30
for a in fsm_ann eca_bob eca_opus eca_cody; do aos-agent ctl add ../agents/$a; done
```

</details>

## 第二次重抄（11-12 19:36～19:40，照 main `8c4d73d15`）

- 同一支腳本再跑一次（成員與代定不變，eca 兩隻 claude 仍不設花費上限），之後多兩步：刪掉 `agents/eca_cody/tools_sub.json`（codex 用不到，`cli.json` 整份蓋掉、沒有 `tools_sub` 鍵）；做外部 MCP 示範（下面）。複製的四夾跟 main 一致（工作樹乾淨），沒跑 install.sh、沒 build。
- **工具支數**：fsm_ann 47（46＋`fake_echo`），eca 三隻各 25；eca_bob、eca_opus 的 `cli.json` 帶 `tools_sub: tools_sub.json`、`--tools …,Agent,Skill`，子 agent 那台 8 支（index_view、json_get、json_ls、json_multi_get、json_search、math、peek_clock、peek_now_time）。
- **子 agent（haiku）**：叫它用 Agent 開一個子 agent 叫 peek_now_time、自己也叫一次——transcript 主 agent `Agent`＋`mcp__aos__peek_now_time`（沒有 parent），子 agent `mcp__aos_sub__peek_now_time`（帶 parent_tool_use_id）；0.010 美金、權限拒絕空。
- **外部 MCP 經 aos（留在試驗場）**：`agents/fsm_ann/mcp/fake.json`＝stdio、`command python3`、`args [{"$env": "AOS_HOME", "$path": "/lib/tests/fake_mcp_stdio.py"}]`（試驗場複製的那份假 server）；`aos-mcp-import --only echo agents/fsm_ann/mcp/fake.json` 匯入 1 of 7；`agents/fsm_ann/tools.json` 的 `$override` 末尾加 `"mcp/fake.json"`（從定義資料夾算）。`aos-tools call fake_echo` 原樣回字；**gemma 叫到 `fake_echo`**、答回傳的字。
- **index 帶 index**：`index_view` `path ../knowledge/aos`、`key cli` 回 `cli … index: ../knowledge/aos/cli/_index.json`。
- **照舊各一句**：假腦 `FAKE ANSWER …`；`fake-demo-json` 劇本走完；codex luna 叫 aos `peek_now_time` 答時間（紀錄 `gpt-6-luna`、`workspace-write`）。
- **樹已停**：臨時兩隻與四隻 purge、shutdown、清兩層 stack／總機帳本／`ws/` → 起根掛四隻（沒有 history）→ shutdown；沒有殘留行程（含假 MCP server）。
- 沒驗：opus 實問、chat 與畫面、litellm 三個、codex 的子 agent（範本沒改、待裁 U1／U2，見 [eca-task-subagent](eca-task-subagent.md)）、`aos-mcp-import sync`。
- 代定：示範的 server 檔放在 `fsm_ann` 定義裡（`mcp/fake.json`）、只匯 `echo` 一支、疊在定義的 `tools.json`（四隻裡只有 fsm_ann 有）；server 路徑用 `$env AOS_HOME` 指試驗場複製的那份假 server。

## 第三次重抄（11-12 21:02～21:06，照 main `415cf6a2c`）

- 同一支腳本＋第二次那兩步（刪 eca_cody 的 `tools_sub.json`、外部 MCP 示範照原樣重做）。腳本本來就是整夾抄 `lib py templates knowledge`，codebase-cleanup 的新檔與搬家的檔都在；複製的四夾跟 git HEAD 逐檔相同（工作樹乾淨）。`cmd/` 不複製，指令經 `~/.local/bin` symlink 指回 repo。沒跑 install.sh、沒 build；impls 的 bin 是 20:06～20:22 建的，樹裡的 `aos-daemon`、`aos-loop` 行程的執行檔就是 repo 那份新的。
- **工具支數**：fsm_ann 48（範本 47＋`fake_echo`），eca 三隻各 26，claude 子 agent 那台 9 支（多 `json_len`）。
- **外部 MCP 示範**：server 檔的 args 用 `$env AOS_HOME` 絕對指試驗場那份假 server，G13（在 server 檔資料夾起）不影響；匯入 1 of 7，`aos-tools call fake_echo` 通。
- **驗收全過**：假腦 `FAKE ANSWER …`；`fake-demo-json` 劇本走完；gemma（帳本 `google/gemma-4-e4b`）叫 `json_len` 答 20、叫 `fake_echo` 回原字；haiku 主 agent `mcp__aos__peek_now_time`、子 agent `mcp__aos_sub__peek_now_time`（0.010 美金、權限拒絕空）；codex luna 叫 aos `peek_now_time`（`gpt-6-luna`、`workspace-write`）；`index_view` 看 `knowledge/aos` 的 `cli` 帶 `index: ../knowledge/aos/cli/_index.json`；小 json `{"b": {"$ref": "#/a"}}` 用 `aos-json get --follow 'reftest.json#/b/y'` 得 `"two"`、不加 `--follow` 回 `{"$ref": "#/a"}`。
- **樹已停**：清乾淨、四隻重掛（沒有 history）、shutdown，沒有殘留行程（含假 MCP server）。
- 沒驗：opus 實問、chat 與畫面、litellm 三個、`jsonx_multi_*`、`json_ls` 的 `depth`、fsm 定義裡用 `#/` 的 `$ref`、`/goal`／`/compact` 卡信的修正。

## 用 eca 唯讀整理 proto8：`eca_tidy`（11-12 21:30～21:34）

使用者原話（11-12 晚）：「然後等等幫我準備好遊樂場。我想試試看用claude eca來初步整理proto8，唯讀的，整理結果放外面。」

**結論**

- 新掛一隻 `eca_tidy`（claude 身，預設 opus、不設花費上限），工作區 `~/code/playground/tidy`：裡面 `proto8/`＝repo `proto8/` 的快照（`git archive HEAD proto8 | tar -x`，`026210d4a`，`chmod -R a-w`，出處寫在 `tidy/SNAPSHOT.txt`），`out/`＝結果夾（試驗場內、repo 外）。試驗場其餘部分沿用 21:04 那份。
- **唯讀有兩層擋**：① 讀的是快照，真 repo 不在工作區；快照檔案系統層唯讀。② claude 工具收成 `--tools Read,Glob,Grep,Write,Edit,Agent,Skill`（沒有 Bash），`--permission-mode dontAsk`，寫入只允許 `--allowedTools "Edit(out/**),Write(out/**)"`（相對工作區）；沒有任何繞過權限的旗標。aos 那台 MCP 給跟子 agent 一樣的唯讀 9 支（定義裡 `tools.json`＝範本 `tools_sub.json` 那份），會寫入的 aos 工具不掛。定義裡加 `system.txt` 說明快照與結果夾。
- **實測（haiku）**：讀 `SNAPSHOT.txt`、`proto8/README.md` 標題、`index_view proto8/knowledge/aos`（20 項）都通；寫 `out/hello.md` 成功；故意寫 `proto8/TEST_FROM_AGENT.md`、寫真 repo `/home/lorkhan/repo/simple_tools/aos/proto8/TEST_FROM_AGENT.md`、Edit `proto8/README.md` 三個都被擋（claude 的 `permission_denials` 三筆：Write、Write、Edit，訊息 "Permission to use Write has been denied because Claude Code is running in don't ask mode"），兩個路徑事後都不存在。子 agent（Agent 工具開 general-purpose）：工具 Agent、Edit、Glob、Grep、Read、Skill、Write＋`mcp__aos_sub__*` 9 支（沒有 Bash、沒有 json_set），寫快照與真 repo 一樣被擋、寫 `out/sub.md` 成功——沒有比主 agent 多。
- **opus 一句**：「列出 proto8 頂層各夾各一句話存成 out/proto8-top-level.md」19 秒、6 輪、opus 0.314 美金（新對話第一題寫快取），結果檔留在 `tidy/out/` 當例子（還順帶指出 `feedback/` 不在 README 的夾表裡）。測試用的檔已刪，`eca_tidy` 重掛成空對話、模型回預設 opus。
- **撞到 build**：21:32 另一條線重 build impls，`aos-fsm` 正在換檔時 fsm_ann 起它＝`LaunchFailed … (Permission denied)`，fsm_ann 停在 `stopped`。停樹、用新的 bin（21:32）重起、`ctl start fsm_ann`，假腦與 eca_tidy 再各驗一次都過。
- **樹留著跑**（五隻都 running），停樹那行在試驗場 README 最上面一節。
- **產出已抽查**（可用，命中約九成；十條發現還沒修）：見 [eca-tidy-review](eca-tidy-review.md)。

**代定**

- 工作區放試驗場內的新資料夾 `tidy/`（不放使用者已信任的 `~/repo` 底下，免得在他的 repo 夾多一個資料夾）：`say`／`chat` 不受影響，開畫面前要手動信任一次，寫在 README。
- 寫入規則寫相對路徑 `out/**`（整個試驗場搬走照樣對）。
- 主 agent 的 aos 工具與子 agent 同一套唯讀 9 支；Agent、Skill 照範本開著。
- `timeout_ms` 拉到 30 分鐘（範本 10 分鐘；整理整份 proto8 一輪可能很久）。
- opus 那句的結果檔留著當例子。

## 要重建什麼

repo 的 `lib／py／templates／knowledge／kernel/llm-kernel` 有改，重跑上面那格就跟上（整個清掉，對話與自己改的設定都會沒）。
