# 公司試驗場重刷（11-12 上午，公司 WSL）：照 main 重抄三隻，eca 25 支、codex workspace-write，假腦與兩個真腦各一輪都過

← [11-12 日索引](README.md)｜前一版：[11-11 playground 01](../11/playground/01-公司刷新與驗收.md)

## 使用者原文

- 「等index,json工具都好了之後，感覺我就可以來玩eca了，還是說有啥需要處理的？沒有的話就幫我把WSL試驗場弄好吧。」
- 中午：「試驗場我正在玩。proto8/knowledge已經弄好了嗎？然後可以的話幫我準備一個eca opus的。我說說接下來我的打算：用這個eca opus，搭配knowledge，讓他可以開始做各種事情。haiku的智能還是不太夠啦老實說」
- 接著：「都先幫我設置無上限吧」（花費上限）

## 結論

- `~/code/playground`（公司 WSL）照 main `eb43dfeaa` 重刷完，三隻掛好、停著、對話是空的（中午加第四隻 `eca_opus`，見下）；**可以直接玩 eca**。使用說明在試驗場的 `README.md`（起：`cd ~/code/playground && source env.sh && aos-exec root`；講話：`cd ~/code/playground && source env.sh && cd ws && aos-agent chat -t eca_bob`；停：`aos-daemon-ctl -d ~/code/playground/.stack shutdown`）。
- 刷新前樹是停的（`state.json` stopped、沒有試驗場底下的行程），不用先停。備份 `~/code/playground.bak-1112-1046`。
- 三隻：`fsm_ann`（假腦，46 支）、`eca_bob`（haiku，25 支；中午起不設花費上限）、`eca_cody`（codex `gpt-6-luna`、`workspace-write`、沒有畫面，25 支）；hooks 都是 `mail_notify`、`timer`。工作區沿用 `~/code/playground/ws`，claude 沒跳信任提示。
- **哪些是複製、哪些指回 repo**：`lib/ py/ templates/ knowledge/`、總機定義 `llm_kernel/def/`、三隻的定義是**複製**（repo 改了要重刷）；指令（`~/.local/bin/aos-*` symlink）與 Python 共用模組（`aos-proto8.pth` 指 `~/repo/aos-tools/proto8/py`、`lib`）**指回 `~/repo/aos-tools`**——別條線合併進那份 clone 後，指令與 cmd 那邊的 Python 自動跟上（C++ 要重 build），腦叫的工具（`$AOS_HOME/lib`）要重刷才跟上。

## 中午加 eca_opus、拿掉花費上限

- **`eca_opus`**：抄 eca-claude 範本，`llm.json` `{"model": "opus"}`（claude CLI 2.1.322 的 `--model` 認 `opus` 別名，實跑是 `claude-opus-5-5`），`cli.json` 的 flags 跟 eca_bob 一字不差（沒有任何全繞過權限的旗標），工作區同樣 `ws/`。使用者那時已停樹、說可以清，起根後 `aos-agent ctl add ../agents/eca_opus` 掛上：25 支，一題「Reply with the single word: hi」答 `hi`、5 秒、0.18 美金（新對話開場寫快取）、權限拒絕空。
- **不設花費上限**：eca_bob、eca_opus 的 `cli.json` `print_flags` 改 `[]`（不帶 `--max-budget-usd`）；eca_cody（codex）本來就沒有、fsm_ann 是假腦。範本預設 0.5 不動。
- **花費上限是什麼**（程式與實測）：`cli.json` 的 `print_flags` 原樣接在每次 `claude -p` 後面（`lib/agent/cli_session.py` 的 claude 那段），所以 `--max-budget-usd N` 管的是「claude CLI 跑一次」＝aos-eca-turn 的一輪（queue 裡等著的那批訊息，通常是使用者的一句）。實測 `--max-budget-usd 0.000001` 問 haiku 一句：claude 回 `subtype error_max_budget_usd`、`is_error true`、`result null`，已花 0.001 美金照算（花完才檢查）；cli_session 看到 `is_error` 就報 `CliFailed`，那輪沒有回答。
- **knowledge**：試驗場的 `knowledge/` 是 10:46 重刷時抄的，跟 repo `e200fffe2` 的 `proto8/knowledge` 一模一樣（最後一次改是 `c09713572`）。只重抄那一塊、不停樹：`cd ~/code/playground && rm -rf knowledge && cp -r ~/repo/aos-tools/proto8/knowledge . && find knowledge -name __pycache__ -prune -exec rm -rf {} +`。

## 跟 11-11 的腳本差在哪

照 [11-11 01](../11/playground/01-公司刷新與驗收.md) 那格改四處，其餘照舊：

| 項 | 11-11 | 11-12 |
|---|---|---|
| `env.sh` | `AOS_KNOWLEDGE=$PG/knowledge` | 刪掉那行與註解裡的 knowledge 工具字樣（knowledge 工具 11-12 拆了） |
| `knowledge/` | 給 knowledge 工具讀 | 照樣複製一份，當普通 json，用 `json_get`／`index_view` 看 |
| 複製後 | 只刪 `__pycache__` | 再刪空資料夾（repo 工作樹裡已拆工具的夾只剩快取，抄過來會變空殼） |
| 劇本假腦 | `fake-demo-today`（self_system＋subagent＋舊 do_task） | 換 `fake-demo-json`：`json_set` 寫 `demo.json` → `json_get` 讀一格 → `json_set` 寫 `_index.json` 一項 → `index_view`（`path` `.`、`key` `demo.json`）；舊 do_task 的 `goal` 參數已不存在，劇本拿掉 |
| eca_cody `cli.json` | `read-only`、`tools_flags --knowledge` | `workspace-write`、沒有 `tools_flags` |
| eca_bob `cli.json` | 範本舊版（`--tools Read,Glob,Grep`） | 範本新版（`Read,Write,Edit,Glob,Grep,Bash`、`dontAsk`＋`--allowedTools Write,Edit,Bash`）；額度原本從備份讀回 0.3，中午改成不設限（`print_flags` 空） |

<details><summary>照抄（刷新）：整段貼進終端機</summary>

```sh
PG=${PG:-~/code/playground}
( set -eu
R=$HOME/repo/aos-tools/proto8
BAK=$PG.bak-$(date +%m%d-%H%M)
[ -f "$PG/env.sh" ] && [ -f "$PG/root/daemon.json" ] || { echo "not a playground: $PG"; exit 1; }
n=1; while [ -e "$BAK" ]; do n=$((n+1)); BAK=$PG.bak-$(date +%m%d-%H%M)-$n; done
cd "$HOME"
mine() { for p in /proc/[0-9]*; do n=${p#/proc/}; [ "$n" != "$$" ] || continue
  case "$(command cat "$p/comm" 2>/dev/null)" in bash|zsh|sh|dash|fish) continue;; esac
  c=$(readlink "$p/cwd" 2>/dev/null || true); a=$(command cat "$p/cmdline" 2>/dev/null | tr '\0' ' ')
  case "$c/ $a" in "$PG"/*|*" $PG"/*|*"=$PG"/*) echo "$n $a";; esac; done; }
rp=$(sed -n 's/.*"pid": *\([0-9][0-9]*\).*/\1/p' "$PG/.stack/state.json" 2>/dev/null | head -n 1)
if [ -n "$rp" ] && [ "$(readlink "/proc/$rp/cwd" 2>/dev/null || true)" = "$PG/root" ]; then
  i=0; until aos-daemon-ctl -d "$PG/.stack" shutdown; do i=$((i+1)); [ $i -lt 30 ] || exit 1; sleep 2; done
fi
i=0; while [ -n "$(mine)" ]; do i=$((i+1)); [ $i -lt 30 ] || { echo "still running under $PG:"; mine; exit 1; }; sleep 1; done
cp -a "$PG" "$BAK" && echo "backup: $BAK"
cd "$PG"
rm -rf lib py templates knowledge && cp -r "$R/lib" "$R/py" "$R/templates" "$R/knowledge" .
find lib py templates knowledge -name __pycache__ -prune -exec rm -rf {} +
find lib py templates knowledge -type d -empty -delete
sed -i '/^export AOS_KNOWLEDGE=/d; s|^#   AOS_KNOWLEDGE＝知識庫（knowledge_read／knowledge_write 讀它）。|#   |' env.sh
grep -q '^export AOS_HOME=' env.sh || echo 'export AOS_HOME=$PG   # definitions use {"$env": "AOS_HOME", ...}: this playground (lib/ py/ templates/ knowledge/)' >> env.sh
rm -rf llm_kernel/def && cp -r "$R/kernel/llm-kernel" llm_kernel/def
for k in model summary; do aos-json set "llm_kernel/def/kernel.json#/endpoints/stupid-fast/$k" "$(aos-json get "$BAK/llm_kernel/def/kernel.json#/endpoints/stupid-fast/$k")"; done
aos-json set 'llm_kernel/def/kernel.json#/endpoints/fake-demo-json' '{"exec": {"$env": "AOS_HOME", "$path": "/lib/base/llm_fake"}, "speed": "fast", "cost": "free",
 "summary": "playground fake brain for 11-12: writes demo.json with json_set, reads one key back with json_get, writes an index entry for it, looks at it with index_view",
 "script": [{"tool_calls": [{"name": "json_set", "arguments": {"path": "demo.json", "value": {"hello": "world", "n": 1}}}]},
            {"tool_calls": [{"name": "json_get", "arguments": {"path": "demo.json#/hello"}}]},
            {"tool_calls": [{"name": "json_set", "arguments": {"path": "_index.json", "value": {"demo.json": {"description": "a file the fake brain wrote"}}}}]},
            {"tool_calls": [{"name": "index_view", "arguments": {"path": ".", "key": "demo.json"}}]},
            {"content": "I wrote demo.json, read hello back, wrote its index entry into _index.json and looked at it with index_view."}]}'
rm -rf agents/fsm_ann agents/eca_bob agents/eca_cody agents/eca_opus
cp -r "$R/templates/agent-fsm" agents/fsm_ann
cp -r "$R/templates/eca-claude" agents/eca_bob
cp -r "$R/templates/eca-claude" agents/eca_cody
cp -r "$R/templates/eca-claude" agents/eca_opus
find agents -mindepth 2 -maxdepth 2 \( -name tests -o -name __pycache__ \) -exec rm -rf {} +
echo '{"model": "haiku"}' > agents/eca_bob/llm.json
aos-json set agents/eca_bob/cli.json#/print_flags '[]'     # no spending cap (11-12 noon)
echo '{"model": "opus"}' > agents/eca_opus/llm.json
aos-json set agents/eca_opus/cli.json#/print_flags '[]'
echo '{"model": "gpt-6-luna"}' > agents/eca_cody/llm.json
command cat > agents/eca_cody/cli.json <<'EOF'
{"kind": "codex",
 "flags": ["-c", "sandbox_mode=\"workspace-write\"", "-c", "approval_policy=\"never\""],
 "print_flags": [],
 "timeout_ms": 600000}
EOF
rm -rf agents/eca_cody/screen
aos-json del 'agents/eca_cody/interfaces.json#/aos-agent/screen'
aos-json set agents/eca_cody/_metainfo.json#/summary '"Run Codex CLI (gpt-6-luna) as an aos agent: one turn per queue batch, answers appended to history; no screen."'
rm -rf .stack ws/.stack && find llm_kernel -mindepth 1 -maxdepth 1 ! -name def -exec rm -rf {} +
echo "refreshed: $PG (agents: $(command ls agents | tr '\n' ' '))"
)
```

刷新後四隻沒掛在領班上：起根，在 `ws/` 裡 `aos-agent ctl add ../agents/<名>`。

</details>

## 驗證（11-12 10:45～10:50）

| 步 | 結果 |
|---|---|
| 複本 `/tmp/aos-pg-1112/pg` 上先跑腳本 | 過；fsm_ann 假腦答 `FAKE ANSWER`；`fake-demo-json` 第一次 `index_view` 給 `path demo.json` 回 `[no index]`（它找檔案裡的 `_index`，提示改看上一層 `.` 加 `key`），劇本改成 `path .`＋`key` 後回 `[index] ./_index.json, 1 entry` |
| 原件跑腳本、起根、掛三隻 | 根表四台 running；三隻 running；工具支數 fsm 46、eca_bob 25、eca_cody 25；eca 的 25 支裡沒有 read／write／ls／shell／trash／knowledge_* |
| fsm_ann 假腦 | `FAKE ANSWER to: what time is it? (tool said: 2026-11-12T02:47:42Z)` |
| `fake-demo-json`（臨時 fsm_demo） | history 10 行照劇本：json_set → json_get 回 `"world"` → json_set `_index.json` → index_view 回那一項；跑完 `ctl rm --purge`、刪 demo 檔 |
| eca_bob（haiku）一題六步 | 16 秒、0.0033 美金；transcript 依序 `Write`、`mcp__aos__json_set`×2、`mcp__aos__index_view`、`mcp__aos__json_get`、`Read`；`permission_denials` 空；它自己數 aos 工具＝25 |
| eca_cody（gpt-6-luna）同一題 | 29 秒；codex 自己的 `command_execution` 寫檔、讀檔（`note_cody.txt` 內容對），aos 那邊 `json_set`×2、`index_view`、`json_get`（mcp_tool_call）；它自己數 aos 工具＝25 |
| 收尾 | 刪測試檔；shutdown；清兩層 stack 與總機帳本 → 起根、掛三隻（history 都 0 行）→ shutdown；試驗場底下沒有行程 |

沒驗：`aos-agent chat` 這次沒實打（11-11 用過）、eca_bob 的畫面（`aos-agent open`）、`stupid-fast`、新信通知。

## 踩到的坑

- **從 Windows 打 `wsl -d Ubuntu -- bash -lc '…'` 時，迴圈變數 `$a` 之類會被吃掉**（`for a in …; do … $a …` 變成空字串，`ctl add ../agents/` 少了名字）。改成把指令寫進檔、`tr -d '\r' < 檔 | bash` 跑就正常。
- `index_view` 給檔名當 `path`＝看那個檔**裡面**的 `_index`；要看「上一層的 index 怎麼說這個檔」，`path` 給上一層、`key` 給檔名。這是設計（[index-tools](index-tools/README.md)），不是 bug。
- repo 工作樹 `~/repo/aos-tools/proto8/lib/agent/` 底下還有已拆工具（knowledge_*、memory*、thought、agents）的空夾，只剩 `__pycache__`（沒進 git）；腳本多一步刪空夾，免得抄進試驗場。repo 那份沒動。

## 要重建什麼

下次 repo 的 `lib／templates／knowledge／kernel/llm-kernel` 有改，重跑上面那格就跟上（會清掉三隻的對話與自己改過的設定，整份先備份）。
