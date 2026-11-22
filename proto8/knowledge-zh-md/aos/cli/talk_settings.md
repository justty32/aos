# `knowledge/aos/cli/talk_settings.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/cli/talk_settings.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/cli/talk_settings.md#/…` 對的就是它。改請改正本，再照 [README](../../README.md) 的做法跟上這份。

---

**`#/Messages, screens and agent settings`**

# 訊息、畫面與 agent 設定

送訊息，以及改某個 agent 的疊加設定（overlay），不動它的定義。改動存在 agent 的 stack 裡；定義不會被改。

**`#/say and listen`**

# say 與 listen

```sh
aos-agent say -t bob "what time is it"     # prints the letter name
aos-agent listen -t bob --timeout-s 60     # waits for the answer, prints its text
aos-agent listen -t bob --letter NAME      # waits for the answer to that letter
aos-agent listen -t bob --last 3           # blocks: == #N, > question, answer
aos-agent listen -t bob --follow           # new exchanges as they come
```

say：字詞用空格接起來；沒有字詞或給 `-` 就讀 stdin；stdin 是終端機又沒有字詞 = `ArgumentsBad`。暫停或睡著的 agent 仍會把訊息排進佇列。`--from WHO`（say 和 chat）指定寄件人；沒給時，寄件人是 stack 裡有 `$AOS_STACK` 的那個 agent，不然就是你的登入名。只有 eca agent（有 `cli.json` 的定義）會拿到這個名字；畫面開著的 claude 身體會顯示它，並把這則訊息當成不是它的使用者打的（要以它的使用者身分講話，就打開畫面直接打字）。名字必須是一行、最多 64 個字元、不含 `" < > &`，不然 `ArgumentsBad`。沒設時限的 listen 可能永遠等下去；`--timeout-s S`（`0` = 不限）或 `--timeout-cycles N` 時間到就放棄，回 `AnswerMissing`。`--follow`（`-f`）有沒有 `--last` 都能用。不要把時限跟 `--last` 或 `--follow` 一起用。follow 中按 Ctrl-C 會 exit 0；等待中按則 exit 130。`aos-agent ask -t bob "what time is it"` 是一步做完 say 再 listen（像 subagent 工具的 op ask）：stdout 只有回覆，預設不限時（`--timeout-s S`，`0` = 不限，或 `--timeout-cycles N`），放棄時回 `AnswerMissing`。ask 等的是它自己那封信的回覆，所以同時跟同一個 agent 講話的其他人各拿各的回覆；一則回覆對應好幾封信時，會印給每個發問的人。ask 等待中按 Ctrl-C 會 exit 130；信已經寄出，stderr 會寫出信名：之後用 `aos-agent listen -t bob --letter NAME` 讀回覆。

`listen --letter NAME` 等那封信（say 印出的名字）的回覆。沒給 `--letter`：等佇列裡還在的最新那封信，沒有就等 agent 拿走了還沒回覆的最後一封，再沒有就給最新的回覆。`LetterDropped`（ask、chat、listen）：agent 丟掉了那封信（不是有效訊息、被 `before_queue` hook 擋下，或 eca agent 的 CLI 在拿走信之後失敗），不會回覆；再說一次。身體還不會記錄信名的 agent（對話歷史裡沒有 `aos` 鍵）用舊方式對應，也就是最新的回覆，並在 stderr 印一則警告。

**`#/chat and screens`**

# chat 與畫面

`printf 'hello\n' | aos-agent chat -t bob` 一次送一行，每行都等回覆（像 ask 一樣對應到它自己那封信）（`> ` 提示印到 stderr）。空行會被略過；Ctrl-C 離開。

`aos-agent open -t bob` 接上它的畫面（`--detach`：只打開）；`close` 關掉畫面、保留對話；`watch` 跟著畫面直到一則回覆結束。它們需要宣告過的畫面介面（`ScreenMissing`）；沒有畫面就用 listen。較底層的指令：`aos/cli/eca.md#/aos-eca-screen: the screen`。

**`#/One agent's tools`**

# 一個 agent 的工具

```sh
aos-agent tools -t bob                 # = ls
aos-agent tools -t bob add --name now2 $AOS_HOME/lib/tools/base/peek_now_time
aos-agent tools -t bob rm shell
aos-agent tools -t bob reset -y
```

選一個動作：`ls [-l | --json]`、`get NAME_OR_PATH`、`add [--name N] [--replace] [--no-cache] [--envs K=V]... [--env-file FILE] (PATH | --path-json JSON)`、`rm NAME_OR_PATH`、`reset`。`--no-cache`：每次都去檢查可執行工具的定義；`--path-json` 存一個指示詞（directive）而不是路徑。改動寫進這個 agent 在 stack 裡自己的 `tools.json`，裡面只放跟定義那份的差異（`"$override"`；移除的工具是 `null`）。第一次改動會印一則警告，說檔案已建立。add/rm 印出跟 aos-tools 一樣的結果行（`removed shell (...: set to null over ...)`）。Hub 變數：`aos/cli/tool_env.md`。

**`#/One agent's brain settings`**

# 一個 agent 的腦設定

```sh
aos-agent llm -t bob set model=fake temperature=0.3
aos-agent llm -t bob ls -l      # model=fake<TAB>agent: which keys this agent changed
aos-agent llm -t bob rm temperature
```

沒給動作就是 ls。`model` 選腦的包（brain pack）；`reasoning_effort` 說腦要想多用力（agent-fsm 把它送給 llm kernel，aos/brain.md；eca 把它轉成它 CLI 的旗標，claude `--effort`、pi `--thinking`；能收哪些等級要看身體）；`temperature`、`top_p`、`max_tokens`、`seed`、`presence_penalty`、`frequency_penalty`、`stop` 用來微調。只存改過的鍵（stack 裡的 `llm.json`）；其他鍵跟著定義。值都是字串。身體不讀的鍵（定義的 `interfaces.json` 裡的 `llm_keys`）照樣存，但會警告。reset 移除所有改動。`llm set system=...` 會被拒絕（ArgumentsBad，什麼都沒存）：用 `system`。

直接問腦服務是 `aos-llm`（`aos/cli/parts/llm.md`）。

**`#/One agent's system text`**

# 一個 agent 的系統文字

```sh
echo "Be short." | aos-agent system -t bob set   # or: set FILE
aos-agent system -t bob get -l                   # where it comes from, then the text
aos-agent system -t bob reset -y
```

沒給動作就是 get。set 讀 FILE，FILE 是 `-` 或沒給時讀 stdin；文字整份寫進 `<stack>/system.txt`，取代定義那份（agent-fsm 把它當系統訊息送出；eca 把它接在 CLI 自己的後面）。什麼時候生效：agent-fsm，下一次呼叫腦；eca claude，下一回合；eca codex，下一段新對話（set 和 reset 會印警告）；開著的 eca 畫面，重新打開之後。原因：`aos/body.md#/System text, history`。定義必須宣告 `{"aos-agent": {"system": "system.txt"}}`，不然 `SystemMissing`。reset 刪掉這份複本。
