# 別人怎麼做（下）：在 REPL 裡除錯，以及「程式邊跑邊改、邊跑邊長」——跟使用者想像最近的幾家

← [README](README.md)｜上一份：[03-別人怎麼做](03-別人怎麼做.md)｜下一份：[04-邊緣狀況](04-邊緣狀況.md)

使用者的想像：「接近python repl + shell指令……用aos-gdb庫，下斷點……然後跑」，以及「執行途中，發現有問題，那就把他停下來(或是不停)，在他的指令中央插入新指令，我們的程式碼是持續在增長的」（[00](00-使用者原話.md)）。11-19 子 agent 上網查證；網址都實際打開過，沒打開的標「沒查到」。

## 先講結論

- **REPL 跟被除錯的東西是不是同一個行程，是第一個分岔**：pdb、IPython、Pharo 是同一個；gdb、SLIME、Erlang remote shell、debugpy 是「在被除錯的那邊留一個小門，REPL 從外面連進去」。aos 只能走後者（agent 是別的行程），而且 aos 已經有小門：hook。
- **最貼使用者想像的是 Common Lisp 的 SLIME＋condition／restart**：出錯時**不拆現場**，停在原地，列出「可以怎麼接下去」（重試、略過、換個值、中止）讓人選；人可以在現場求值、重新定義函式，再選一條接著跑。
- **「邊跑邊改」各家最大的坑都是同一個：拿在手上的舊東西不會自己變新**（Python reload 的舊物件、Clojure 傳值、Erlang 第二版之前的行程、LangGraph 的舊 checkpoint）。aos 實測：疊層與 `fsm.json` 每輪重讀、會跟上；`loop.json` 只讀一次、跟不上（[02-續](02-續-插入與Python.md)）。
- **除錯資訊要跟著「版本」走**：SBCL 的除錯等級是**編譯時**對單一函式宣告的；Pharo 用 `.changes` 記每個方法的每一版；Jupyter 沒記，所以畫面跟真實狀態常常對不上（大規模研究只有約 4% 的 notebook 重跑結果相同，數字來自搜尋摘要）。

## 一、REPL 式除錯

**Python pdb 與 `breakpoint()`**：程式裡寫 `breakpoint()` 就停在那行進 pdb。環境變數 `PYTHONBREAKPOINT=0` 整個關掉、設成別的函式就換除錯器，而且**每次碰到斷點才讀**——一個開關、程式不用改。`pdb.pm()` 事後看上一個例外；`interact` 開完整直譯器，但在裡面重新指派變數**不會寫回**原本的 frame。3.14 起 `python -m pdb -p PID` 可以接上別的 Python 行程。<https://docs.python.org/3/library/pdb.html>、<https://peps.python.org/pep-0553/>（ipdb 官方頁沒查到。）

**IPython**：`%debug` 事後進例外現場；`%pdb on` 每次例外自動進；`embed()` 在程式任何位置開一個 IPython；`embed_kernel()` 讓外部前端連進來。<https://ipython.readthedocs.io/en/stable/interactive/magics.html>、<https://ipython.readthedocs.io/en/stable/interactive/reference.html>

**gdb 的 Python API**：繼承 `gdb.Breakpoint`、寫 `stop()`，回 True 才真的停、回 False 放行——條件複雜的斷點、或「只記一筆不停」的記錄點都這樣寫。`gdb.events.stop.connect(…)` 在每次停住時叫你。官方規矩：`stop()` 裡**只准看、決定停不停**，不准 step、不准改狀態；要動手等真的停下來。<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Breakpoints-In-Python.html>、<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Events-In-Python.html>

**Common Lisp：SLIME／condition／restart**：被除錯的 Lisp 行程裡起一個 swank 小伺服器，Emacs 連進去，之後打的東西都在那個活行程裡求值（官方警告：不要不經 SSH 通道直連，否則誰都能控制整個 Lisp）。出錯時 SLIME 接手、彈出 sldb：顯示錯誤、**restart 清單**、堆疊，堆疊原地不動；可以上下移 frame、在 frame 裡求值、按數字選一個 restart 接著跑。condition system 的關鍵是 `handler-bind` **不先拆堆疊**，在出錯點原地處理，所以底層定義的「怎麼接下去」（restart）不會弄丟。<https://slime.common-lisp.dev/doc/html/Debugger.html>、<https://slime.common-lisp.dev/doc/html/Restarts.html>、<https://gigamonkeys.com/book/beyond-exception-handling-conditions-and-restarts.html>（「改函式重編再選 restart」的官方逐字說明沒查到，是 Lisp 的一般作法；SLY 沒查。）

**Smalltalk（Pharo）**：IDE 與程式在同一個 image 裡；在除錯器裡直接改方法、再繼續單步；可以存下除錯中途的整個系統，之後還原走另一條路。<https://pharo.org/features>（Restart／Proceed 按鈕的語意只查到非官方郵件列表。）

**Erlang shell 與 Elixir IEx**：`erl -remsh 節點` 開一個連到活節點的 shell，在裡面用 `sys:get_state`、`sys:suspend`、`dbg`。Elixir 的 `IEx.pry()` 在程式碼裡停住開 IEx（只能看、不能改流程）；`IEx.break!(Mod.fun/arity)` **不改原始碼**就下斷點；`iex --remsh` 連活節點。<https://www.erlang.org/doc/apps/erts/erl_cmd.html>、<https://iex.hexdocs.pm/IEx.html>

**加分**：Clojure 的 nREPL（編輯器連到跑著的程式求值，REPL-driven development 的底盤）<https://docs.nrepl.org/nrepl/index.html>；Python 的 debugpy（注入到指定 PID）<https://github.com/microsoft/debugpy>、remote-pdb（pdb 掛在 TCP 埠上）<https://github.com/ionelmc/python-remote-pdb>。都警告別把埠開到外面。

## 二、程式邊跑邊改、邊跑邊長

**Common Lisp／SBCL（image 式）**：跑著時重新 `defun`，之後的呼叫就用新的；被內嵌（inline）的舊呼叫可能還是舊的。`save-lisp-and-die` 把整個狀態存成 core 檔，下次從那裡接著跑（存完原行程報廢）。**除錯程度是編譯時宣告的品質等級**：`(declaim (optimize (debug 3)))` 可以只放在某個函式前面——2 以上留區域變數與原始碼位置，3 讓變數隨時可看、關掉尾呼叫最佳化，代價是變慢、堆疊變深。<https://www.sbcl.org/manual/index.html>、<https://www.lispworks.com/documentation/HyperSpec/Body/m_defun.htm>

**Pharo 的 `.changes`**：image 只存編譯後的方法，原始碼的每次修改記在 `.changes` 檔，支援每個方法的歷史、比較、還原；當機忘了存 image，還能從它救回程式。坑：記得不完整，image 與 `.changes` 必須成對。<https://github.com/pharo-open-documentation/pharo-wiki/blob/master/General/Glossary.md>

**Erlang 熱更新**：同一模組最多同時有「現行」「舊」兩版。完整寫出模組名的呼叫（`m:loop()`）永遠走現行版；正在跑舊版的行程**要自己再做一次這種呼叫**才換過去。載入第三版時還停在最舊版的行程會被殺掉。OTP 的正式升級：先 `sys:suspend` 受影響的行程、`sys:change_code`（觸發 `code_change` 回呼轉換狀態）、再 `sys:resume`。<https://www.erlang.org/doc/system/code_loading.html>、<https://www.erlang.org/doc/system/release_handling.html>

**Notebook（Jupyter）**：格子可以亂序改、亂序跑，狀態留在 kernel，畫面上的程式碼不一定是產生目前狀態的那些。Pimentel 等人的大規模研究（約 86 萬份）指出隱藏狀態與亂序執行是重跑失敗的常見原因（數字只讀到搜尋摘要）。<https://leomurta.github.io/papers/pimentel2019a.pdf>

**LLM agent 框架中途改**：LangGraph 用 `interrupt`／`update_state` 中途改**狀態**；動態挑工具是「依狀態從事先註冊好的工具裡過濾」，官方明寫「All available tools need to be registered upfront」——**跑著時憑空加新工具，官方頁沒說可以**。<https://docs.langchain.com/oss/python/langchain/middleware/custom>。OpenAI Agents SDK 的 `is_enabled` 動態開關已註冊的工具，沒有「跑著時新增」的說法。<https://openai.github.io/openai-agents-python/tools/>。對照：**aos 今天就能跑著時加新工具**（`tools add`、`self_tools`，下一輪生效，[02-續](02-續-插入與Python.md) 實測），這點比這兩家走得前面。

**Python `importlib.reload`、Clojure**：reload 後，別處拿著的舊物件、`from m import f` 拿到的 `f`、舊實例的類別都不會更新。Clojure 經 Var 呼叫的才跟上新版，傳函式值的凍在舊版；狀態要另外轉換。<https://docs.python.org/3/library/importlib.html>、<https://clojure.org/guides/repl/enhancing_your_repl_workflow>

## 總表：REPL 與邊跑邊改

| 誰 | REPL 跟被除錯的同一行程？ | 怎麼下斷點 | 停住時能做什麼 | 改了再續 | 除錯資訊怎麼跟上新版 |
|---|---|---|---|---|---|
| pdb／`breakpoint()` | 同（3.14 可 `-p`） | 程式裡一行；環境變數換掉或關掉 | 看變數、開直譯器 | 能；重新指派不寫回 | 行號跟著原始碼 |
| gdb Python API | 不同（掛在外面） | `Breakpoint.stop()` 回 True／False | 停住後才准改 | 能 | 靠 `-g` 重編 |
| SLIME／condition | 不同（連 swank） | 出錯自動停；`break` | 現場求值、選 restart | 能 | 重新編譯該函式；`debug` 等級逐函式宣告 |
| Pharo | 同一個 image | 除錯器本身 | 改方法、改物件 | 能 | `.changes` 記每版 |
| Erlang／IEx | 不同（連活節點） | `sys:suspend`；`IEx.break!` 不改原始碼 | 看、改狀態、追訊息 | 能（`replace_state`） | 新舊兩版模組並存 |
| Jupyter | 不同（kernel） | `%debug`、`%pdb` | kernel 裡全部 | 能（重跑那格） | 不跟上（隱藏狀態） |
| LangGraph | 同（Python） | `interrupt`、`interrupt_before` | 整份狀態 | 能（分岔） | checkpoint 分支 |
| **aos 今天** | 不同（樹是別的行程） | hook（任何可執行檔，下一個事件生效） | 讀 stack、`ctl state`、回話改參數 | 能（分散） | **沒有**：疊層與 `fsm.json` 只有現在的樣子 |

## 對 aos-gdb 最值得記的四點

1. **在被除錯那邊留小門、REPL 從外面連**是跨行程的標準解；aos 的 hook 就是小門，缺的是「門後面接到 REPL」那條線。
2. **停住前只准看、停住後才准改**（gdb `stop()` 的規矩）；改了要有明確的寫回路徑（pdb `interact` 不寫回的坑）。
3. **出錯時停在原地、列出可以怎麼接下去**（Lisp 的 restart）——aos 的錯誤行 `toolname: error: Code` 就是 condition 的種類，`before_tool`／`after_tool` 就是不拆現場的那個位置。
4. **每一步帶著「當時是哪一版」**：程式邊跑邊長，沒有版本，事後的 backtrace 就對不回當時的程式。
