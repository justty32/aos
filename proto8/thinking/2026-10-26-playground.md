# 2026-10-26 playground：先弄一個呼叫 claude code cli 的節點

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[user-advice](../user-advice/README.md)（使用者的初步想法，「第一回合」）｜claude 當工具的先例：[demo agent-fay](../demo/README.md)

## 使用者原文（10-26，逐字）

> 寫好了，都是一些初步想法，很粗糙糢糊。我們得實際來做做看。請你在~/code/try/playground中，agent那邊先弄一個節點，以呼叫claude code cli爲目標。workspace那邊，幫我放一份galtxt的輸入，也就是場景/人物設定...等，一份.md，一份.json

看完第一版後：

> 1 砸掉重來，我們一步一步開始。先弄_entry，然後使其能呼叫claud code cli，並給與初始prompt

> 可以把agent/_entry寫成一行，具體python檔案另外分出來。並且python code寫簡單一下嗎

## 結論（細節在試驗場 `~/code/try/playground/README.md`，不在 git）

- **砸掉重來、一步一步做**：第一版（galtxt 輸入 md／json／schema、`_metainfo`、refs）整個刪掉。現在只有節點 `playground/agent/` 的 `_entry`＋初始 prompt `prompt.txt`，和一個空的 `workspace/`；galtxt 輸入、schema、`_metainfo`、`_improve` 都還沒有，等使用者說下一步。
- **`_entry`** 只有一行 shell（`exec python3 "$(dirname "$0")/main.py"`），python 在同資料夾 `main.py`（約 19 行，沒有多餘錯誤分類）：讀 `prompt.txt`，叫 `claude -p --output-format json`，cwd＝`$AOS_WS`；回答印到 stdout，原樣 JSON 存 `$AOS_STACK/claude.json`；失敗退非 0。模型 haiku、花費上限 $0.2、逾時 300 秒，寫在 `main.py`。照 proto8 慣例 `aos-exec --ws workspace agent` 跑。
- **權限**：`--restricted`（不載使用者／專案設定、沒有 Bash、檔案工具只限工作區）＋只給 `Read,Glob,Grep,Write`＋`--permission-mode dontAsk`＋`--strict-mcp-config`＋`--max-budget-usd`；拿掉 `CLAUDE*`、`AI_AGENT` 環境變數防巢狀。
- **實跑一次**（10-26，haiku，prompt「用一句繁體中文自我介紹…」）：通，整趟 3.6 秒（claude 1.8 秒）、1 回合、$0.0005；回「我是 Claude，由 Anthropic 開發的 AI 助理，目前在 `/home/lorkhan/code/try/playground/workspace` 這個資料夾裡工作。」

## 10-27：接 aos 工具（MCP）

使用者原文（10-26／27，逐字）：

> Hmmm，我稍微看了一下，我在想，他目前只能指定一些固定工具。那我們能不能透過一些方式，比如mcp，或是claude code cli本來就有的東西，把我們的aos體系接入進去呢？

頂層列了 MCP／Bash 白名單／skill 三條，使用者：

> 那就mcp。

> 都做做看，我去洗澡，二十分鐘後回來。

結論：

- **新程式 `aos-mcp`**（`proto8/extras/ai_tools/bin/`，照 [side-mcp](../topdown/galtxt-a/plan/side-mcp.md) 的最小原型）：一個有 `tool.json` 的資料夾程式＝一個 MCP tool；外面叫一次＝`aos-exec --ws WS 該資料夾`，arguments 進 stdin、stdout 回去、退非 0＝錯。說明在 [ai_tools/README](../extras/ai_tools/README.md#aos-mcp10-2710-28-改成包在-aos-tools-上)。這也把 [10-24 ai-tools](2026-10-24-ai-tools.md) 的未決題「要不要另做 MCP server」定成「做」（門檻「外部 agent 不能給 Bash」正好碰到）。
- **試驗場**：`agent/mcp.json` 掛 aos-mcp、只開 lib/base 的 clock、math、read；`main.py` 加 `--mcp-config`、`--allowedTools` 放行 `mcp__aos__*` 三個，其餘安全鎖不拆（`--strict-mcp-config` 留著＝只接 mcp.json 那一支）；aos-mcp 的小格是 `$AOS_STACK/mcp/`（main.py 給，C-70）。
- **實跑一次**（10-27，haiku，題目：現在 UTC 幾點、兩個 18 位數相乘、讀 `note.txt`）：claude 依序叫了 clock、math、read 三個 aos 工具（`$AOS_STACK/mcp/calls.jsonl` 三行，每次約 19 ms），乘積對；整趟 4.3 秒（claude 3.2 秒）、4 回合、$0.0016。

代定（可翻案）：

1. 位置 `proto8/extras/ai_tools/bin/aos-mcp`（side-mcp 寫的 `proto8/ai_tools/` 10-26 已搬進 extras）。
2. 工作區與 stack 走環境變數：aos-mcp 讀 `AOS_WS`／`AOS_STACK`（也收 `--ws`／`--stack`）；main.py 把 claude 的 `AOS_STACK` 換成 `$AOS_STACK/mcp/`，aos-mcp 再給每個工具 `mcp/<名>/`，`mcp.json` 不寫死工作區。
3. 每次呼叫記一行 `calls.jsonl`（名字、arguments、結束碼、毫秒、時間）——不然從 `claude.json` 看不出叫了哪些工具。
4. 逾時照字面取 `_metainfo` 的 `time_ms.max`（clock、math 是 1 秒），沒寫才用 `--timeout-s`（預設 60）。
5. progress 不做（三個工具都不到一秒）；agent 資料夾當 tool、`destructiveHint` 也先不做。
6. 工具 stdout 空又退非 0 時，回 aos-mcp 自己的一行 `aos-mcp: CommandFailed <名> 退 N`，不去讀工具的 stderr（C-52；stderr 照原樣流給 claude 的紀錄）。
