# proto8 — 重新想過一遍

← [AGENTS.md](../AGENTS.md)｜上一代 proto7、proto7-2

2026-10-11 開：使用者看完 proto7-2 之後說「整個都不對，太繁複」，從概念重新想過一遍；之前的程式當探針有價值，但不是成品。

## 頂層一覽

頂層八夾（11-17 使用者裁「八夾-0 A」，同天下午加 `frontend`；11-18 S3 `lib` 原始碼改名 `py`）：`cpp frontend py templates knowledge docs thinking archive`（11-18 S5 `cmd` 收掉，Python 指令的本體進 `py/aos/apps/`），另有 `README.md`、`_index.json`、`env.sh`、`install.py` 四個檔；`bin/`、`lib/`、`include/` 是 `python3 install.py` 產的、不進 git，**執行期只認這三夾**（改了 `py/` 要重跑 `install.py` 才生效）。程式按角色分夾：

- **cpp**＝aos-exec 跑得動的基礎與標準庫（C／C++）。
- **Python 指令**＝人在終端打的指令：本體一支一夾在 `py/aos/apps/<名>/`（夾名＝指令名去掉 `aos-`、`-` 換 `_`；aos-eca 兩支同夾），入口由 `install.py` 照 `py/entries.json` 生進 `bin/`，跟 C++ 的執行檔同一夾。
- **frontend**＝選配的網頁外掛：全景頁 `aos-frontend`（看整棵樹、回使用者專區的信、給 agent 寫一行），執行檔在 `frontend/bin/aos-frontend`；不用它，aos 照樣跑。後端只要 Python，網頁 v2 的 `dist/` 不進 git，要在有 Node 的機器自己建（11-17 下午使用者「aos-view確實應該是選配的網頁外掛」「那就改名為aos-frontend吧」，從 `cmd/aos-view` 搬來）。
- **py**＝Python 原始碼：指令（`aos/apps/`）、工具與範本共用的模組收成一個套件 `py/aos/`（`from aos import flags, tool_io`、`aos.daemon_ctl`；agent 共用的 `cli_*.py`、`hooks.py`… 在 `aos.agentlib`），腦叫的工具（三件套）在 `py/tools/{base,aos,agent}`；`install.py` 把它抄成 `lib/`（不含測試與 `py/docs`），定義的指示詞寫 `/lib/tools/…`。
- **templates**＝複製出去用的 agent 範本，與掛在 daemon 上的 kernel 範本（`templates/kernels/`，11-17 從頂層 `kernel/` 併進來）。
- **archive**＝不再維護、留著參考的東西（11-17 extras 解散時建）。

**路徑規則一**（11-17 使用者裁「路徑-1 A」）：aos 的程式全住在 `AOS_HOME` 指的那個 proto8 裡；家裡的用自己的位置找鄰居，家外的（抄出去的範本格、工具、定義）只經 `AOS_HOME` 找進來，沒設就報 `HomeMissing`、不猜。`AOS_HOME` 由人一台設一次（`env.sh` 不替你設，11-18 S6）；每個視窗先 `source $AOS_HOME/env.sh`，或在樹裡 `source env.sh`（起手範本帶的薄的那份，轉去家裡這份）。新使用者的安裝六步與更新五步在[重建步驟單](thinking/2026-11/17/重建步驟單.md)。

| 資料夾 | 收什麼 |
|---|---|
| [docs/](docs/README.md) | 使用者條文：[CONCEPTS](docs/CONCEPTS.md)（概念）、[NORMS](docs/NORMS.md)（規範）、[CONVENTION](docs/CONVENTION.md)（agent 慣例）；另有 [notes/](docs/notes/README.md)＝AI 寫的參考筆記（不算數） |
| [cpp/](cpp/README.md) | aos-exec、aos-loop、aos-fsm、aos-daemon 等 C++ 專案（`cpp/Makefile` 一份編全家，nlohmann json 是收進 repo 的單檔 `cpp/third_party/nlohmann/json.hpp`；中間檔在 `cpp/build/`、`.a`／`.so` 裝進 `lib/`，都不進 git） |
| [install.py](install.py) | 安裝：在 proto8 跑 `python3 install.py`（只用標準庫、Python ≥ 3.11）：先查相依（必需 g++ ≥ 10、gcc、make、ar；選配工具只列表不擋），清空再填 `bin/`（9 支 C++ 執行檔）、`lib/`（`py/` 的抄本加 C++ 函式庫）與 `include/`（公開標頭），log 在 `cpp/build/build.log`，另產 `cpp/compile_commands.json` 給 clangd；`--check` 只查相依。重跑＝全新安裝，C++ 沒改時幾秒 |
| [py/aos/apps/](py/docs/05-commands.md) | Python 指令的本體（入口照 `py/entries.json` 裝進 `bin/`）：aos-agent、aos-daemon-ctl、aos-tools、aos-clock、aos-clock-register、aos-mailbox、aos-sweeper、aos-feedback、aos-eca（turn、screen）、aos-mcp、aos-mcp-launch（起外部 stdio MCP server）、aos-mcp-import（把外部 MCP 的工具凍結成一包）、aos-sandbox、aos-grow |
| [env.sh](env.sh) | 每個視窗先 `source $AOS_HOME/env.sh`（或樹裡那份薄的）：`AOS_HOME` 沒設就報一行 `EnvBad`、什麼都不改；清掉 `AOS_HOME` 以外的 `AOS_*`、把 `$AOS_HOME/bin`（第一）、`frontend/bin`（夾在才放）放到 PATH 最前；`aos-exec` 不在時提示先跑 `python3 $AOS_HOME/install.py` |
| [frontend/](frontend/API.md) | 選配的網頁外掛：全景頁 `aos-frontend`（後端 Python 標準庫；v2 網頁原始碼在 `ui/v2/`，`dist/` 不進 git，要 Node 才建得出來，見 [ui/v2/README](frontend/ui/v2/README.md)）；aide 定義的差異檔 `aide-def/`、systemd 範例、測試也在這夾 |
| [py/](py/README.md) | Python 原始碼（11-18 S3 前叫 `lib/`）：agent 用的工具在 `py/tools/`（底層原語 → 動 aos 的 → 整隻 agent）；機讀的協議定義在 [py/schema/](py/schema/README.md)；共用模組在一個套件 [py/aos/](py/aos/)（`aos.flags`、`aos.ws`、`aos.daemon_ctl` 等，說明在 [py/docs/04](py/docs/04-共用模組.md)）。安裝後的抄本在 `lib/`（不進 git，執行期認它） |
| [templates/](templates/README.md) | 起手範本 [start-api](templates/starts/start-api/README.md)、[start-eca](templates/starts/start-eca/README.md)（一包抄好一棵樹：根＋一隻 agent＋樹裡的 `env.sh`，`cp -r` 一行；11-18 S6）；agent 範本：`eca-claude`（外部 coding agent）、`agent-fsm`（aos 自己的 loop／fsm agent）等；kernel 範本在 [templates/kernels/](templates/kernels/README.md)：llm-kernel（問腦的那台）、daemon-kernel、procs-kernel（通用 kernel 的站的兩種掛法） |
| [kernels/](kernels/README.md) | proto9 `mini-sandbox` 照名字找的 kernel 設定（`--kernels aos/base-low,aos/llm/fake`；一個名字＝一份 `<名字>.json`；使用者 11-27 定放 `$AOS_HOME/kernels/`）。跟上一列 `templates/kernels/`（proto8 掛在 daemon 上的 llm-kernel 等範本）是兩回事 |
| [knowledge/](knowledge/README.md) | 出廠內容樹：普通資料夾＋`.json`，用一般檔案／json 工具讀；第一本是 `aos/`——給小模型的 aos 體系說明（英文） |
| [archive/](archive/README.md) | 封存（11-17 重建：langs、tree-swap、aos-home；清單在它的 README） |
| [thinking/](thinking/README.md) | 討論紀錄（使用者原文、決定、結論）；使用者自己的意見稿 11-22 搬到 repo 根的 [`wf/user/advice/`](../wf/user/advice/) |

**以 [CONCEPTS.md](docs/CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-92，作廢的號只留在表上；只收使用者說過的）。圖解兩頁（10-20 的狀態）：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。實作上的想法在 [restart §3g](thinking/2026-10/11/restart/README.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環）。

## 現況

- **資料夾＝程式**（使用者 10-19 定）：aos 只訂六個環境變數和一支 `aos-exec [--ws WS] XXX [args...]`；入口四種、`XXX` 的找法、`#/` 尋址、`+x` 但沒 `#!` 的檔用 `/bin/sh` 跑（§ 21「不擋」、§ 22「乙」）都在 [NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62）。巢狀由程式自己訂子 stack；這次要做啥隨意。10-16 那套作廢；原話與裁定在 [thinking/2026-10/19/ideas/README.md](thinking/2026-10/19/ideas/README.md)（使用者：「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」）。
- **實作**：[cpp/](cpp/README.md) 是唯一實作（C／C++；使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也用 C++、時鐘先留 Python，[py/aos/apps/](py/docs/05-commands.md) 是 Python 的 aos-clock 等），命令列有 aos-exec、aos-loop、aos-fsm、aos-daemon 等（全表見它的 README）；刻意沒有 aos-inst 命令列。loop／daemon／fsm 格「要跑什麼」那一格叫 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」，[thinking](thinking/2026-10/23/naming.md)）。
- **kernel** 已有 [templates/kernels/](templates/kernels/README.md) 的 llm-kernel（問腦）、daemon-kernel 與 procs-kernel（通用 kernel 的站的兩種掛法）；底層用 cpp 的 `aos-daemon`／`aos-loop`。tasks 仍無實作，待照新做法重寫（[NORMS 待定](docs/NORMS/08-待定.md)）；時鐘是 `py/aos/apps/clock`，腦的工具呼叫範本是 `templates/agents/agent-fsm`、慣例 [P-41](docs/CONVENTION.md)。

## 入口

- **[docs/tutorial/](docs/tutorial/README.md)**：教學——從一個空資料夾架 daemon、灌 kernel、寫一份 `agent.py`、接著開發（工具、庫、連結、衍生、aos-gdb、Python 腳本），假腦、照著打就能走完（使用者 11-19「幫我弄一份教學吧」）。
- **[CONCEPTS.md](docs/CONCEPTS.md)**：概念——aos 怎麼看世界（C-01～C-92）。
- **[NORMS.md](docs/NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；程式符合規範但不強制。底在 [NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62：六個環境變數、`aos-exec XXX`、找入口、`#/` 尋址）。
- **[CONVENTION.md](docs/CONVENTION.md)**：aos agent 慣例（P-05～P-48）——我們自己人寫 agent 時照抄的標準形狀，不要求別人守。
- **[templates/](templates/README.md)**：`eca-claude`（外部 coding agent 範本）與 `agent-fsm`（aos 自己的 loop／fsm agent 範本，idle／think／wait／act 四格；格的程式在 `py/aos/apps/agent_fsm/`，裝好在 `lib/`，範本只是給人抄的定義），都用 `aos-agent ctl add` 掛（宣告在 `interfaces.json`）；`agent-fsm` 的 think 組請求、wait 經 [templates/kernels/](templates/kernels/README.md) 的 llm-kernel 寄信與收回信。
- **[templates/kernels/](templates/kernels/README.md)**：llm-kernel 的啟動與問腦用法、daemon-kernel／procs-kernel 的框架站接法。
- **10-24 一天的嘗試**（使用者「我隨便說，你隨便做，反正只是嘗試」；代定都可翻案，一覽在 [session log 10-24](../wf/session_logs/2026-10-parts/12-10-24.md#2026-10-24)）：[lib/](py/README.md)（工具＝函式庫）、給人用的 say／listen（在 [aos-agent](py/aos/apps/agent/README.md) 裡）、[aos-mcp](py/aos/apps/mcp/README.md)、[aos-grow](py/aos/apps/grow/README.md)（函數成長）、[langs/](archive/langs/README.md)（Janet、Lua 寫 aos；11-17 封存）、[aos-sandbox](py/aos/apps/sandbox/README.md)（Linux 權限與沙箱）。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- **[docs/notes/](docs/notes/README.md)**：AI 寫的參考筆記（不是規範、不算數）：拿外面現成的東西跟 aos 對照，例如 [跟 s6、runit 的對照](docs/notes/s6-runit.md)。
- 之前乾淨的兩個時刻，要回頭看的：九月初 ideas 13 章（舊入口已封存，看 git 歷史）、十月初 proto7 核心 spec 與 設計原則。
- 使用者自己的草稿與意見稿：[`wf/user/advice/`](../wf/user/advice/)（9 月草稿 2026-09-19～24 與之後一天一份；11-22 從 `thinking/user-advice/` 搬過去，那夾是使用者的地盤，檔名可能會變）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10/11/restart/README.md](thinking/2026-10/11/restart/README.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS、NORMS 與 CONVENTION 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 C-48（指示詞有 $env、$ref 兩個）、C-68～C-70（資料夾＝程式、aos 只訂環境變數）、KISS、層徹底切割、少用 sh，不合的打回；跟原則相撞的帶著衝突來問使用者（wf user.md「規劃交給 fable、只把衝突帶給他」），不原樣端給使用者。
