# 02 檔案系統當 lua/lisp 用：`_entry` 與 aos-exec

蒐集隊員交件。只讀。每個說法標「讀到」或「推測」。路徑都從 `/home/lorkhan/repo/aos/` 起算；`proto8/` 簡寫成 `P/`。

名詞先講一句：
- `_entry`：資料夾裡那個「叫這個資料夾時要跑的東西」。
- aos-exec：C++ 寫的一支命令列，負責「走進資料夾、讀 `.env`、挑出 `_entry`、備好環境變數、開跑」。
- 指示詞（directive）：JSON 裡長得像 `{"$ref": ...}` 的小物件，讀的時候會被換成別的值。
- 單子（inst 單子）：JSON 物件，有 `argv` 這個 key，描述「怎麼起一個子程式」。

---

## 一、現況

### 1.1 `_entry` 怎麼認（讀到）

- 資料夾：找 `XXX/$AOS_ENTRY`，沒設就是 `_entry`；沒有再找 `_entry.json`；同名資料夾與 `.json` 並存時資料夾贏。`P/docs/NORMS/10-基礎設施-定義與工作區/05-N-61～N-62.md:5`（N-61 路徑那條）；實作 `P/cpp/aos-exec/src/find/find.cpp:19-21`、`:95-96`、`:179-191`。
- `.env` 可以改 `AOS_ENTRY`，所以入口名可變；`$AOS_ENTRY` 可以多段（`sub/run`），沿路資料夾都走進去。`P/cpp/aos-exec/docs/01-用法.md` 一跳第 5 步。
- 入口本身有四種（種類看內容、不看副檔名）：`P/cpp/aos-exec/docs/02-種類.md:7-21`
  1. 可執行檔：有 `+x` 且開頭是 `#!` 或 ELF，或整份不是 JSON。直接 exec。沒 `#!` 的退給 `/bin/sh`（glibc `execvp` 的行為，`P/cpp/aos-exec/src/launch/launch.cpp:3-8`、`:39`）。
  2. JSON 單子：物件有 `argv`。行程內跑，aos-exec 留著當監工（`02-種類.md:20`）。
  3. JSON argv 陣列：非空陣列，元素是字串或指示詞，解完要全是字串（`02-種類.md:14-19`）。
  4. JSON 字串：路徑轉向，等於全新再跑一次 aos-exec（`02-種類.md:21`）。
  5. 沒 `argv` 的 JSON 物件：當成資料夾，取 `[$AOS_ENTRY]` 往下走（`02-種類.md:9-13`；`P/cpp/aos-exec/src/find/classify.cpp:107`）。這就是「JSON 內部也是一棵檔案系統」。
- 尋址：`檔#/指標`（JSON pointer）。`aos-exec cfg.json#/tools/stamp a b` 可用。`P/docs/NORMS/10-基礎設施-定義與工作區/05-N-61～N-62.md` N-62 段。
- 所以「可以是什麼格式／語言」：任何 exec 得動的東西（shebang 決定語言）、或 JSON 寫的 argv。aos-exec 本身不認語言。讀到的原話在 `P/py/aos/apps/hook/docs/03-寫handler.md:8-12`：「aos-exec 跑得動的都算：可執行檔……任何語言都行」。

### 1.2 aos-exec 解析與呼叫（讀到）

- 命令列：`aos-exec [--ws WS] [--stack S] [--stack-lazy] [--dotenv-override] XXX [ARGS...]`。第一個非旗標參數就是 XXX，後面原樣給入口。`P/cpp/aos-exec/docs/01-用法.md` 開頭。`main.cpp` 只有 14 行，叫 `run_cli`（`P/cpp/aos-exec/src/main.cpp`）。
- aos-exec 的原始碼共約 1528 行（9 個 .cpp 加 main；`wc -l` 我自己算的）。
- 每一跳的順序：定工作區 → 認出 XXX → 建 stack → cd 進去並讀 `.env` → 挑入口 → 判種類 → 重設 `AOS_CF`／`AOS_CD`／`AOS_CO` → 開跑。`01-用法.md`「一跳」一節。
- 環境變數只有六個加 PATH：`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`、`AOS_CF`（實際被執行的檔）、`AOS_CD`（它所在資料夾）、`AOS_CO`（入口在 JSON 裡的位置）。PATH 不動。`P/cpp/aos-exec/docs/03-環境變數.md:5-13`；規範 N-57 `P/docs/NORMS/00-規範-4-資料夾程式與執行.md:11`。
- `.env`：dotenv 的基礎子集，預設不蓋已有的環境變數，加 `--dotenv-override` 才蓋；只展開 `${名字}`；錯誤訊息絕不印值。`P/cpp/aos-exec/docs/02-種類.md` 的 `.env` 一節；實作 `P/cpp/aos-exec/src/env/dotenv.cpp`（260 行）。JSON 物件也能有 `.env` key。

### 1.3 stdin／stdout／stderr 與結束碼（讀到）

- aos-exec 自己：「stdin 不讀，原樣給入口」（`P/cpp/aos-exec/docs/01-用法.md:22`）。可執行檔與 argv 陣列是 exec，自己不留下；結束碼就是入口的。
- 單子的串流欄位：`stdin`／`stdout`／`stderr` 沒寫就「接呼叫者的」（aos-exec 自己的 fd 0／1／2），可改檔、可附加、可 `stderr_merge`。`P/cpp/aos-exec/docs/03-環境變數.md:26-33`。
- 單子認 17 個 key，其餘忽略（`03-環境變數.md:19`；N-04 `P/docs/NORMS/03-基礎設施-inst.md:11`）。
- 單子跑的時候 aos-exec 當監工：訊號轉給整個行程群組；逾時先 SIGTERM 再 SIGKILL；以子程式的碼結束，被訊號停掉是 128＋N。`03-環境變數.md:46`。
- 結束碼（N-43）：`0`＝正常，`10`＝正常停（要求外面 loop 別再跑），其他非 0＝有錯。使用者原話見第二節。`P/docs/NORMS/01-總則/02-N-43.md:3`。
- aos 自己的程式出錯一律退 1，stderr 一行 `程式名: error: 代號 原因`。轉交別人的碼時，靠「stderr 有沒有 `我的名字: error:` 那行」分誰錯。`P/docs/NORMS/01-總則/02-N-43續-11-05-兩種行與碼.md`（「轉交的碼」那條）；aos-exec 的錯誤代號表 `P/cpp/aos-exec/docs/05-錯誤代號等.md`。
- 重要的範圍限定（讀到）：stdin／stdout／stderr／exit「只是每個 proc 都有的檔案，管線、訊號不寫進 aos 標準」；那些 stderr 行、退 1 的規矩只是 aos 自己那幾支程式的行為，「別的 aos 函數要不要照做，自己定」。`P/docs/NORMS/01-總則/02-N-43.md:3`（「適用範圍」那條）。
- 工具這一層（慣例，不是規範）：工具從 stdin 收一份 JSON、結果印 stdout、錯誤是 stdout 與 stderr 各一行 `名: error: 代號 原因`、退 1。`P/py/aos/tool_io.py` 開頭註解；`aos-tools call` 的說明 `P/knowledge/aos/cli/tools.md`（「call」一節：「Every tool gets its JSON input unchanged on stdin」）。工具也可以用旗標填 JSON 輸入（`aos-exec $AOS_HOME/lib/tools/base/math --expr '6*7'`，`P/knowledge/aos/cli/parts/exec.md`）。

### 1.4 指示詞（directive）全列（讀到）

實作在 `P/cpp/aos-directive/src/`（`resolve.cpp:48-102`、`ref.cpp`、`env.cpp`、`md.cpp`）；說明在 `P/cpp/aos-directive/docs/01-用法等.md:11-26`。**解析器認的只有四個 key：`$ref`、`$env`、`$path`、`$prefix`。**

| 寫法 | 換成什麼 |
|---|---|
| `{"$ref": "file.json"}` | 整份檔（第一行 `#!` 跳過），換進來再接著解 |
| `{"$ref": "file.json#/a/b"}` | 檔內那個位置（RFC 6901） |
| `{"$ref": "#/a/b"}`、`#./b`、`#../c` | `#/` 本檔根、`#./` 所在物件、`#../` 上一層；`#` 左邊是檔案系統、右邊是 json 內部 |
| `{"$ref": ["a.json", "b.json#/c"]}` | 陣列＝照順序合成一份（物件合 key、後蓋前；陣列接起來；種類混＝錯） |
| `{"$ref": "x.md#/標題/…"}` | 檔是 `.md`：照標題、清單、表格、json 區塊讀成 json 值（11-21 加的） |
| `{"$env": "NAME"}` | 環境變數的值 |
| 加 `"$path": "子路徑"` | 換出來是字串時照字串接上去 |
| 加 `"$prefix": "--file="` | 換出來是字串時接在前面 |

- 同物件兩個都寫只看 `$ref`（`01-用法等.md:9`）。
- 不認得的 `$xxx` 一律不管、不報錯；`$ref`／`$env` 的值不是非空字串就原封不動留著（`01-用法等.md:25`）。
- 真的解不開＝`DirectiveBad`：`$env` 沒設、檔讀不到、指到資料夾、指標指不到、繞圈（`01-用法等.md:24`）。
- 其他帶 `$` 的 key 不是 aos-exec／aos-directive 的指示詞（讀到）：
  - `$override`：`aos-tools` 的註冊檔用，「只記對 BASE 的差異」，疊法歸 aos-tools，不歸指示詞。`P/py/aos/apps/tools/helps.py:14`、`P/knowledge/aos/cli/tools.md`（「The registry」一節）。我在 `py/`、`cpp/*/src` 全域 grep 這 key 出現約 94 次（含說明文字）。
  - `$schema`／`$defs`／`$id`：JSON schema 自己的，沒讀成指示詞。
  - 公式 key（`cal`、`lua`、`py`、`aos`）：N-68 明說「不是指示詞、只有讀者算」，現在只實作 `cal`。`P/docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md:9`。
- 誰在解（讀到）：aos-exec（入口檔、argv 陣列、JSON `.env`、單子）、aos-loop、aos-fsm、aos-daemon，另有 Python 呼叫者（框架站 kernel、llm kernel）。`01-用法等.md:77`（「現在給了檔的呼叫者」那段）。「使用者『aos 讀的 JSON 全部支援』」見 `P/cpp/aos-directive/README.md:7`。

### 1.5 現在有多少東西靠 `_entry` 跑（讀到；數字是我自己數的）

- `P/` 底下（不含 archive、thinking、build）共 215 個 `_entry*` 檔／資料夾。分布：`py/tools` 91、`lib/tools`（`py/tools` 裝好的複本）91、`templates` 約 31（starts 9、agents 9、kernels 7、tools 2、daemons 2、其餘）、`py/aos` 2、`lib/aos` 2。
- `py/tools` 底下 91 個 `_entry`：其中 90 個是 `#!/usr/bin/env python3`，1 個是 `#!/bin/sh`（`py/tools/agent/hook_noop/_entry`）。`_tooldef.json` 有 81 份。
- 工具例子：`py/tools/base/` 底下有 shell、read、write、grep、json_get、math、llm_http 等；`py/tools/agent/` 底下有 mailbox_send、board_ls、subagent、self_tools 等；`py/tools/aos/` 底下有 jsonx_* 一族、kernel、measure 等。
- 範本（templates）的 `_entry` 多半只有一行 JSON：
  - 範本 agent（`P/templates/agents/agent-python/_entry`）：`{"argv": ["aos-agent","ctl","add",{"$env":"AOS_CD"}], "cwd": {"$env":"AOS_WS"}}`，意思是「跑這個資料夾＝把自己掛上 daemon」。
  - `eca-claude`、`procs-kernel` 的 `_entry`：`["aos-loop", "loop.json"]`（`P/templates/agents/eca-claude/_entry`）。
  - daemon：`["aos-daemon", "--enable-logs", "daemon.json"]`（`P/templates/kernels/llm-kernel/_entry`、`P/templates/daemons/daemon-root/_entry`）。
  - 工具骨架：`P/templates/tools/tool-python/_entry.json` ＝ `{"argv": ["python3", "tool.py"]}`。
- agent 狀態：agent 的 stack 是資料夾（`$AOS_STACK`）。fsm 的每一格、loop 的每一次，都經 aos-exec 或它的庫 `run_cli`（`P/cpp/aos-exec/README.md:7`；`P/cpp/aos-exec/docs/04-元素與實作注意.md` 實作注意第一點）。hook handler 也是 aos-exec 跑的（`P/py/aos/apps/hook/docs/03-寫handler.md:8`）。

### 1.6 有沒有真的接入不同技術棧（讀到）

有的：
- sh：`py/tools/agent/hook_noop/_entry`（`#!/bin/sh`，`cat > /dev/null; exit 0`）。文件說 hook handler「任何語言都行」。
- Python：絕大多數工具與 agent 的格（`idle.py` 等，`P/knowledge/aos/definition.md` 的 agent-fsm 段）。
- C++：`aos-loop`、`aos-daemon`、`aos-fsm`、`aos-post` 等本體是 C++，被範本的 `_entry` 以 argv 叫起來（上面 1.5）。
- 外部 CLI：eca 身的 `cli.json` 指定 claude、codex、pi（`P/knowledge/aos/definition.md`「Only eca-claude」一段）；沙箱範例把 claude、codex、aos-exec 列進 `commands`（`P/py/aos/apps/sandbox/examples/cli-tool.json`）。
- 沙箱包裝：`P/py/aos/apps/sandbox/examples/shell-boxed/_entry` ＝ `["aos-sandbox", "_metainfo.json#/sandbox", "aos-exec", "inner"]`，一層包一層。
- 別的程式語言「編成」aos 資料夾：Janet 與 Lua（`P/archive/langs/README.md`，11-17 封存，不再維護）。注意這是「用語言寫 table、輸出成資料夾」，執行期跟那個語言無關。
- MCP：`aos-mcp` 把 aos 工具給外部 agent；`aos-mcp-import` 把 MCP 工具匯進來（`P/knowledge/aos/cli/mcp.md`）。
- LiteLLM endpoint：一行 `["aos-exec", "$AOS_HOME/lib/tools/base/llm_http", "--key-env", "LITELLM_KEY"]`（`P/templates/kernels/llm-kernel/endpoints/litellm/_entry`）。

沒找到：
- 沒找到「用 Rust／Go／Node／Lua 腳本直接當 `_entry`」的活範例（只有 sh、Python、已封存的 Lua／Janet 編譯器）。**這是我 grep `py/tools`、`templates` 的結果，沒掃整個 repo，也沒掃 `impl_cpp/`。**
- 沒找到「C++ 寫的工具」（`py/tools` 與 `templates/tools` 底下沒有 ELF 的 `_entry`）。

### 1.7 「像 lua／lisp」這個說法在現況文件裡（讀到）

- `P/docs/CONCEPTS.md:17`（C-43）、`:40`（C-71）、`:68`（C-35）、`:38`（C-69）、`:41`（C-72）。引文見第二節。
- 知識庫（給 agent 看的英文那份）裡沒找到 lisp／lua 字樣。我 `rg -il "lisp|lua"` 過 `P/knowledge`，命中的檔都不在 `knowledge/aos/`（只命中 `proto8/README.md`、`docs/`、`thinking/`、`wf/` 這些）。**推測**：agent 看到的世界裡沒有這個比喻，只有「folder is a program／tool」。

---

## 二、以前說過什麼（逐字）

使用者的話（路徑可核對）：

1. 10-19，proto8 的起點：「純粹把資料夾作為lisp的list或lua的table，然後有一個entry，在lisp就是第一個元素，在lua就是metatable裡面定義的那個，而在我們這邊，就是環境變數定義：AOS_ENTRY=.aos/inst，這個定義的目標必須是可執行檔。就這樣，非常簡單。」同段稍前：「我覺得目前這些inst、stdin啥的規矩都太麻煩了，我開proto8就是想試試看另一個更簡單的」。`P/thinking/2026-10/19/ideas/01-原話.md:7`
2. 10-19，aos-exec 的由來（同一段）：「這一套操作會簡化成aos-exec workspace agent-bob，也就是"在workspace這個資料夾，執行agent-bob這個程式"。至於agent-bob如何處理cwd, 目標資料夾的內容，那就是agent-bob內自己的事」。`P/thinking/2026-10/19/ideas/01-原話.md:7`
3. 10-13：「底子其實已經打好了：把檔案系統當 lisp 來做，核心就是 inst 這塊碼在跑；上面包了 loop；loop 上面又有管理多個 inst 在跑的 daemon。」`P/thinking/2026-10/13/kernel-agent/01-使用者原文.md:7`
4. 10-15，同像性：「其實我們這個aos inst也是一個大號的類似感覺，也就是同樣照lisp來：(daemon inst-a), (daemon (fsm inst-b inst-c))，這是同相性」。`P/thinking/2026-10/15/homoiconic.md:7`
5. 10-24 的整理：「10-16『把 JSON＋資料夾當 Lisp 的 list，這就是一個函數啊，何必再造一個體系？』、10-19『資料夾（程式）本身就是函數』」（這是 agent 整理版，引使用者舊話）。`P/thinking/2026-10/24/fn-grow/01-使用者原文.md:9`
6. 10-24：「再來是lisp/lua編譯成我們這套的方式。去看看~/repo/langs/janet-lab，我想試試看janet編譯成這套。但其實lua也不錯」。`P/thinking/2026-10/24/lua-nvim/01-使用者原文.md:6`
7. 10-25：「我們現在用aos體系，等同於把資料夾和json串起來，並且將其視作lua/lisp來使用，基底是posix，配合llm輔助。」`P/thinking/2026-10/25/top-down/01-使用者原文-10-25-逐字.md:6`
8. 11-07，公式語言可替換：「直接寫"lua":"...."或"py":"..."，然後呼叫相應lua.exe/python.exe(這臺是linux，沒有)。或是直接跑aos函數。……其實沒啥規定，就是隨着複雜度增加，可以替換到所需技術棧。搞不好到後面，就是呼叫aos　agent」。`P/docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md:9`
9. 11-13：「在aos體系下開發軟體的體驗有點類似lisp的理想狀況。你先從一個能幫你開發函數的函數開始，然後改進這個函數，使其變得能更好的開發函數」`wf/user/advice/20261113.md:19`；「其實整個aos體系都可以用lisp/lua實現，但linux太香了，有現成的各種東西，所以就先這樣。之後如果有人像在lisp/lua內開發，然後用plan9方式接入aos，那也是好事。」`wf/user/advice/20261113.md:23`
10. 11-24（本題的原話，也在 `wf/user/advice/20261124.md:72`，整理版在 `:16-22`）：「再來是將檔案系統作爲lua/lisp來使用，以posix呼叫爲基礎，善用stdin/out/err等，作爲_entry，這個舉動有好有壞，你要說他降低了agent的認知負擔嗎？倒也沒有，硬要說的話就是讓他能夠適配linux體系，允許接入各種不同技術棧吧，其核心就是一個aos-exec。」

結束碼與串流（使用者）：
- 10-15：「結束碼不要太依賴，我已經決定規範中只定下：0就是通用正常，非0就是有錯，沒了。」`P/docs/NORMS/01-總則/02-N-43.md:3`（後來加了 10＝正常停，同檔）。
- 10-28 對適用範圍：「照你的建議，留著改口，JSONL 那半條刪掉」，結果是「stdin／stdout／stderr／exit 只是每個 proc 都有的檔案，管線、訊號不寫進 aos 標準」。`P/docs/NORMS/01-總則/02-N-43.md:3`（「適用範圍」那條，條文是 agent 整理版）。

已定的條文（CONCEPTS，條文不是使用者逐字，是整理）：
- C-43：「終局：一套 library，用 lua／lisp 一類語言把 aos 程式（整套資料夾布局）生成出來（＝『編譯』），把 aos 當作業系統跑；人和 AI 都要能用。」`P/docs/CONCEPTS.md:17`
- C-69：「aos 只訂環境變數（入口、工作區、stack 等六個）和一支 aos-exec；入口拿到後做什麼不管。」`P/docs/CONCEPTS.md:38`
- C-71：「資料夾的比喻用 lua 的 table、不用 lisp 的 list：本質都是 index＋巢狀分資料；入口之外的就是其他元素。」`P/docs/CONCEPTS.md:40`
- C-72：「JSON＝埋在檔案裡的 table（單檔的微型檔案系統），入口的尋址同樣適用。」`P/docs/CONCEPTS.md:41`
- C-35：「Linux 檔案系統就是一個 LISP（比喻用 table，C-71）。」`P/docs/CONCEPTS.md:68`

觀察：以前的說法大致分三種意思，跟這次的說法不完全一樣：
- A「資料夾＝table／list，入口是第一個元素」（10-13～10-19，講結構）。
- B「用 lua／lisp 寫、編出資料夾」（10-24，C-43，講生成；已做成 Janet／Lua 編譯器、已封存）。
- C「資料夾＝函數、能自我開發」（10-16、11-13，講開發方式）。
- 這次（11-24）強調的是「適配 Linux、接多種技術棧」，並明說「不降低 agent 認知負擔」。以前我沒讀到這個角度被這樣明講；**這是我的觀察，不是定論。**

---

## 三、差距（目標句 vs 現況）

目標句：「以 posix 呼叫為基礎，善用 stdin/out/err，作為 `_entry`……允許接入各種不同技術棧，核心就是一個 aos-exec」。

1. **「核心就是一個 aos-exec」：現況大致符合。** 規範只訂六個環境變數加 aos-exec（C-69、N-57～N-62）。證據：`P/docs/CONCEPTS.md:38`、`P/docs/NORMS/00-規範-4-資料夾程式與執行.md:11-15`。
2. **aos-exec 不止 exec。** 它還有 `.env`、cd、stack 自動建、單子的監工（轉訊號、逾時、群組收屍）、指示詞解析、繞圈偵測。這比「POSIX 呼叫」多一圈。證據：`P/cpp/aos-exec/docs/01-用法.md`、`03-環境變數.md:46-50`。（觀察：這些是 Linux 本來該有的「啟動器」工作，但不是純 exec。）
3. **「善用 stdin/out/err」沒有成為規範。** N-43 明說串流與結束碼的細則「不是 aos 函數都要守的標準」。工具那層的 stdin JSON／stdout 文字／錯誤行是慣例（`tool_io.py`），由 Python 的 `tool_io` 模組強制；不是 Python 寫的工具要自己守。證據：`P/docs/NORMS/01-總則/02-N-43.md:3`、`P/py/aos/tool_io.py` 開頭。
4. **「各種技術棧」：入口這層真的沒鎖語言；實際用的幾乎只有 Python 與 sh。** 91 個 `_entry`：90 Python、1 sh；沒有 C++ 工具、沒有別的語言的活工具。證據見 1.5、1.6。
5. **接入的是「叫外面」多、「外面叫進來」有限。** aos 叫 claude／codex／pi 是以 argv 與外部 CLI 的格式；外面叫 aos 工具要走 `aos-mcp`。「在 lisp/lua 內開發、用 plan9 方式接入 aos」（`wf/user/advice/20261113.md:23`）沒找到實作。**推測**：還沒做。
6. **工具的「介面描述」不在 `_entry` 裡。** `_entry` 只管「怎麼跑」；模型看到的是另一個檔 `_tooldef.json`；性質是 `_metainfo.json`。所以一個不是 Python 寫的工具，要自己手寫 `_tooldef`（Python 的 `@fn.tool` 才能自動生成，`P/knowledge/aos/tools_def.md` 的 fn 一節）。**讀到**；「非 Python 的人要手寫」是我從文件推的。
7. **兩種「入口」概念並存。** 有「資料夾的 `_entry`」與「JSON 內的 `_entry` key」；JSON 沒 `argv` 的物件又當資料夾往下走。語意一致，但讀者要記兩套寫法（資料夾、JSON）加四種種類。證據：`02-種類.md`。
8. **指示詞只有四個 key，但使用者的說法可能期待更像 lisp 的「函數」。** 目前沒有求值、條件、組合子的指示詞；N-68 的公式 key 只實作 `cal`（`lua`／`py`／`aos` 沒實作）。證據：`P/docs/NORMS/10-基礎設施-定義與工作區/10-N-68.md:9`。組合子（fsm、loop、daemon）是各自的 JSON，不在指示詞裡（`P/docs/NORMS/07-基礎設施-組合子.md`）。
9. **「lua／lisp 寫、編成資料夾」已封存。** C-43 還在 CONCEPTS，但 Janet、Lua 實作 11-17 封存（`P/archive/langs/README.md`、`P/README.md:50`）。現況裡沒有「用語言生成」的活工具。
10. **使用者專區那份整理與規範之間：** `wf/user/advice/20261124.md:16-22` 寫「以 POSIX 呼叫爲基礎，善用 stdin/out/err 等」。規範裡與之最接近的是 N-43 的「適用範圍」那條，語氣相反（不寫進標準）。**這可能只是「慣例而非規範」的差別，不是矛盾；我沒替使用者判斷。**

---

## 四、已知的缺點與沒解的問題

文件裡自己承認的（讀到）：

- **起動成本。** 11-24 量過：C++ 小程式起一次約 1 ms，Python 入口是它的 80～200 倍（`aos-eca-turn --help` 123 ms、`idle.py --help` 61 ms、`python3 -c pass` 25 ms）；`lib/` 幾乎沒有 `.pyc`，所有 Python 入口每次都重新編譯，補齊後能省約 31～48%。`P/thinking/2026-11/24/閒置輪詢C++重寫-1124/06-這次補量的數字.md:20-37`（表）、第 3 節。因為 `_entry` 每次呼叫都是起一個新行程，工具與 fsm 每格都繳這筆。（我讀到的是數字；「每格都繳」是從 aos-exec 每次 exec 的設計推的。）
- **沒有 `aos-inst` 命令列。** `#!/usr/bin/env aos-inst` 或小殼 `exec aos-inst _entry.json` 跑不起來；同一檔去掉 `+x` 才能用。`P/cpp/aos-exec/docs/05-錯誤代號等.md`「已知差異」一節。
- **`#!/usr/bin/env aos-exec` 加 `+x` 會無限 exec。** 在 /mnt/c（WSL，每個檔 0777）上等於全部都這樣。文件只能叫人不要寫。`P/cpp/aos-exec/docs/03-環境變數.md:52`。
- **種類看內容、不看副檔名／權限。** 這是為了 /mnt/c 每檔 0777；代價是一個「不是 JSON 的壞檔」會被當成程式去 exec（種類第 1 條「整份不是 JSON」）。這是我從 `02-種類.md:7` 讀出的後果；**推測**，我沒實測。
- **空 stack 留尾巴。** 可執行檔與 argv 陣列 exec 成功就不回來，新建的空 stack 照留；單子把東西丟背景、之後才寫 stack 的，回來那刻是空的會被收掉。`05-錯誤代號等.md`「已知差異」第二點。
- **孫行程收不乾淨。** 正常結束不收背景孫行程；自己換 session 的後代逃出群組；inst 的 `setsid＋killpg` 只管自己起的那群；daemon 表不列孫行程。`03-環境變數.md:50`、`04-元素與實作注意.md` 最後一段。
- **`.env` 外層贏。** 預設不蓋已有的環境變數，所以子資料夾的 `.env` 跟外層同名時看到的是外層的；loop 跑途中改 `.env` 不生效。`P/docs/NORMS/04-基礎設施-loop與daemon.md:13`、`P/docs/NORMS/07-基礎設施-組合子.md`（fsm 不管的第 ⑧ 點）。
- **`run_cli` 動行程全域狀態（chdir、setenv）。** 所以 loop／fsm／daemon 要 fork 後才能呼叫，不能在自己行程裡用。`04-元素與實作注意.md` 實作注意第一點。
- **路徑轉向繞圈偵測是「每層只管自己」的唯一例外**（承認的例外）。N-61 `05-N-61～N-62.md` 繞圈那條。
- **JSON 資料夾一路往下沒深度上限、風險使用者自己承擔**（使用者「2.b，我們就是這樣規定的，具體風險由使用者自己承擔」，`P/docs/NORMS/10-基礎設施-定義與工作區/05-N-61～N-62.md` JSON 內不補那條）。
- **檔名不能含 `#`。** `檔#/指標` 第一個 `#` 就切（N-62）。
- **單子欄位寬容、打錯 key 不報錯。** N-04 讓不認得的 key 一律忽略；單子裡打錯 `timout_ms` 不會有人說。`03-環境變數.md:39`、`P/docs/NORMS/03-基礎設施-inst.md:11`。**這是我從規則推的風險，沒有文件列為「問題」。**
- **規範全是「草稿」。** N-57～N-62 都標草稿（`P/docs/NORMS/00-規範-4-資料夾程式與執行.md:11-15`）。
- **認知負擔的說法：** 使用者自己說「倒也沒有」降低（`wf/user/advice/20261124.md:72`）。我沒找到量化或實驗，也沒找到 agent 在這層出錯的紀錄；**沒找到，不補。**
- **跨語言契約靠人記。** 錯誤行格式、退 1、錯誤兩處印、`HELP` 開關等是 `tool_io.py` 一份 Python 模組在管，別的語言寫工具要自己照抄。證據 `P/py/aos/tool_io.py` 開頭。這是「現況事實＋我推的後果」。

---

## 蒐集時沒做的事（避免誤會）

- 沒讀 `impl_cpp/`（使用者 11-09 起手寫的 C++ 重寫），所以「別的實作怎麼看 `_entry`」沒查。
- 沒實跑 aos-exec，沒起任何行程；所有行為說明都來自文件與原始碼的閱讀。
- `thinking/` 只用 grep 挑著讀；10-19 `ideas/` 底下除了原話外的其他分檔沒逐一讀。
