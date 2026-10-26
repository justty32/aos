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
