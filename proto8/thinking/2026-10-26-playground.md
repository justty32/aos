# 2026-10-26 playground：先弄一個呼叫 claude code cli 的節點

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[user-advice](../user-advice/README.md)（使用者的初步想法，「第一回合」）｜題材：[topdown/galtxt-b](../topdown/galtxt-b/README.md)｜claude 當工具的先例：[demo agent-fay](../demo/README.md)

## 使用者原文（10-26，逐字）

> 寫好了，都是一些初步想法，很粗糙糢糊。我們得實際來做做看。請你在~/code/try/playground中，agent那邊先弄一個節點，以呼叫claude code cli爲目標。workspace那邊，幫我放一份galtxt的輸入，也就是場景/人物設定...等，一份.md，一份.json

## 結論（做了什麼；細節在試驗場 `~/code/try/playground/README.md`，不在 git）

- **節點** `playground/agent/`：`_entry`（python）把 `prompts/system.txt`＋`refs/*.txt` 接在 system prompt 後面、`prompts/task.txt` 當題目，叫 `claude -p --output-format json`，cwd＝`$AOS_WS`；claude 自己用 Write 把台詞寫到 `out/lines.txt`，`_entry` 只檢查有沒有寫出來。結果原樣存 `$AOS_STACK/claude.json`，stderr 印一行花費。照 proto8 慣例能 `aos-exec --ws workspace agent` 跑；模型、花費上限、逾時在 `.env`。
- **`_metainfo`** 照 [10-24 `_metainfo`](2026-10-24-metainfo.md) 的通用 key（`time_ms`、`resource`、`mem_mb`、`llm_calls`、`llm_tokens`、`cost`…），另加 `uncontrolled`：claude code cli 能碰到什麼、用哪些旗標收窄、還沒收住的（工作區裡的檔它都能蓋、它自己連網、token 只能事後看）。
- **權限**：`--restricted`（不載使用者／專案設定、沒有 Bash、檔案工具只限工作區）＋只給 `Read,Glob,Grep,Write`＋`--permission-mode dontAsk`＋`--strict-mcp-config`＋`--max-budget-usd`；拿掉 `CLAUDE*`、`AI_AGENT` 環境變數防巢狀（同 cli-tools/env.sh）。實測讀 `/etc/hostname`、寫工作區外都被擋，寫工作區可以。
- **輸入** `playground/workspace/`：`input.md`（給人看）、`input.json`（claude 讀這份）、`input.schema.json`（JSON Schema）。內容照抄 galtxt-b 訓練題「新書_宮澤_主角先_梅花章」與它的資料表（梅雨傍晚、河鹿堂、進新書日、主角＋宮澤柚葉、稱謂階 1、意圖「鉤」）；地點、季節、時間、意圖、會說話的人、道具、傲嬌的否認／讓步／遮掩／句尾、階 1 稱呼、節拍名都用 enum 收死。
- **實跑一次**（10-26，sonnet）：通，15 秒、4 回合、$0.065（cache 讀 23.6k／寫 12.2k、output 1.4k）；產出 10 行，照節拍演完、用了「才不是要你幫忙，是你手比較長」等輸入給的詞。
- **`_improve` 還沒做**（使用者後來覺得要解耦、還沒定）；要放的話可以是節點裡另一個入口 `agent/_improve`，或照使用者「影子世界」的想法放在節點外、用捷徑指進來。
