Claude Code 跑在第二個帳號上的 eca 範本：除了兩份 `.env` 與這份 README，其餘逐字是 `eca-claude`。

# eca-claude-alt

← [templates](../README.md)｜原範本：[eca-claude](../eca-claude/README.md)（各檔用途、工具、hook、畫面都照那份）｜測試：[`tests/test_eca_claude_alt.py`](../tests/test_eca_claude_alt.py)

用這份範本掛的 eca，答話那一輪和開畫面（`aos-agent open`／`close`／`watch`／`peek`）都用另一個 Claude 帳號：帳號資料夾 `CLAUDE_CONFIG_DIR` 預設 `~/.claude-alt`。起根的殼、開畫面的殼都不用另外 export，你在殼裡直接打 `claude` 仍是原本的帳號（使用者 11-23：「喔我覺得很簡單啦，就是proto8/template中提供一個eca-claude-alt就好」）。

## 用法

1. 先登入那個帳號一次：`CLAUDE_CONFIG_DIR=~/.claude-alt claude`，在裡面 `/login`。
2. 掛上去（不用抄，直接指範本；要改設定再 `cp -r` 一份）：
   ```sh
   aos-agent ctl add -n <名> -w . --path-json '{"$env": "AOS_HOME", "$path": "/templates/eca-claude-alt"}'
   ```
3. 開畫面照舊：`aos-agent -t <名> open`。

## 跟 eca-claude 差在哪

- `.env`（定義夾頂層）：`CLAUDE_CONFIG_DIR=${HOME}/.claude-alt`。daemon 用 `aos-exec` 起這份定義時讀它，loop、`aos-eca-turn`、它叫起的 claude、hook 都拿到這個值。
- `screen/.env`：同一行。`aos-agent open` 是用 `aos-exec` 起 `screen/` 這個子入口，讀的是**這一份**，不是頂層那份。少了它，畫面會用開畫面那個殼的帳號；aos 發現帳號資料夾跟上次不一樣，就會清掉 `session.txt`、開一段新對話，原本那段對話就斷了。兩份的值要一樣。
- 這份 README。

**殼裡已經有 `CLAUDE_CONFIG_DIR` 時，殼的值贏**：`.env` 照 aos 的慣例不蓋已經 export 的名字（`proto8/cpp/aos-exec/src/env/dotenv.cpp`）。所以起根的殼和開畫面的殼要嘛都不設，要嘛設成同一個值；兩邊不一樣，就會像上面說的開新對話。要換資料夾，就改兩份 `.env`，或抄一份範本出去改。

**`eca-claude` 改了要同步抄過來**：`tests/test_eca_claude_alt.py` 逐檔比對內容與執行位，沒同步就紅。重抄的方法是 `rsync -a --exclude=.env --exclude=README.md ../eca-claude/ ./`。

## 出處

- 使用者 11-23：先是「我想掛。但是想用另一個帳號掛」；後來說「後續掛agent都用那個」「不用想太多」。
- 為什麼畫面要另一份 `.env`：線 `eca-alt-1123` 在暫存樹用假 claude 驗過。畫面用的是開畫面那個殼的值；`claude/env.json` 只記 `AOS_*`，不記帳號資料夾。
