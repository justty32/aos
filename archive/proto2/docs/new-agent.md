# 開一個新 agent

`aos-user new` 會建一個完整世界。預設用 `chat` 模板。本體放在 `agent/`。

## 工具清單

`aos-user templates` 列出模板和一句說明。

`aos-user packs` 列出現在真的裝好的工具包和一句說明。

`aos-user new <資料夾>` 沒有任何旗標時會一題一題問。每題直接按 Enter 就用預設。最後還會問一次才建立。

已經知道要什麼時，可以直接寫：

```sh
aos-user new work/bob --template coder --engine deepseek-flash
aos-user new work/helper --packs mailbox,self --persona "你只整理收到的信。"
```

建好後會印出路徑和下一步指令。

## 三個模板

- `chat`：聊天和看信箱。
- `coder`：先看清楚，再小步改 Python。起手會請它先用 `ls` 看資料夾。
- `manager`：生小孩、拆工作、看進度，自己不動手。

模板放在 `proto2/templates/<名字>/`。每個模板有 `tools.json`、`system-prompt.json`、`prompts.json`、`llm.json`、`README.md`。複製一份資料夾再改，就能加自己的模板。

## 設定

旗標會蓋掉模板：

- `--packs a,b`：整份換成這些工具包。名字打錯會停下來，並列出可用的。
- `--persona "一句人格"`：直接給人格。
- `--persona-file 路徑`：從文字檔讀人格。不能跟 `--persona` 一起用。
- `--prompts 路徑.json`：用一個 OpenAI messages 陣列當起手對話。
- `--engine 名字`：指定 LLM engine。
- `--priority N`：指定 LLM 優先級。
- `--home 子路徑`：本體放哪。預設 `agent`。
- `--clock own`：建好就向 daemon 要鐘。預設 `none`，只建立，不開鐘。

模板先鋪底，旗標再蓋上去。沒指定的設定會保留模板值。

## 建出來有什麼

世界裡有 `.aos/inst` 和 `.gitignore`。home 裡有四個 JSON，加上空的 `inbox/`、`outbox/`。模板的 README 只是說明，不會複製進新世界。

## 坑

- 目標資料夾已經存在時不會蓋掉。
- `--prompts` 要給 JSON 檔，不是直接給一句話。問答模式才是直接輸入一句起手指示。
- `--clock own` 沒設 `AOS_DAEMON_DIR` 時，世界仍會建好，但鐘不會開。
- `new` 只認內建 `proto2/packs/` 裡真的存在的包。agent home 裡的私有包不能在建立時指定。
