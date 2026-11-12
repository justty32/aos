# proto8 — 重新想過一遍

← [repo INDEX](../wf/INDEX.md)｜上一代 proto7、proto7-2

2026-10-11 開：使用者看完 proto7-2 之後說「整個都不對，太繁複」，從概念重新想過一遍；之前的程式當探針有價值，但不是成品。

## 頂層一覽

程式按角色分夾：

- **impls**＝aos-exec 跑得動的基礎與標準庫（C／C++）。
- **cmd**＝人在終端打的指令：一支一夾、夾名＝指令名、執行檔在 `<名>/bin/<名>`，跟 impls 同形（aos-eca 兩支同夾）。
- **py**＝cmd 共用的 Python 模組。
- **lib**＝腦叫的工具（三件套；lib 自己的 `tool_io.py` 留在 lib）。
- **kernel**＝掛在 daemon 上的管理元件。
- **templates**＝複製出去用的 agent 範本。
- **extras**＝還沒定位的嘗試。

| 資料夾 | 收什麼 |
|---|---|
| [docs/](docs/README.md) | 使用者條文：[CONCEPTS](docs/CONCEPTS.md)（概念）、[NORMS](docs/NORMS.md)（規範）、[CONVENTION](docs/CONVENTION.md)（agent 慣例） |
| [impls/](impls/README.md) | aos-exec、aos-loop、aos-fsm、aos-daemon 等 C++ 專案（各自 CMake；`build/`、`bin/`、`lib/` 是建置產物、不進 git） |
| [cmd/](cmd/README.md) | Python 指令：aos-agent、aos-daemon-ctl、aos-tools、aos-clock、aos-clock-register、aos-mailbox、aos-sweeper、aos-feedback、aos-eca（turn、screen）、aos-mcp、aos-sandbox、aos-grow |
| [py/](py/README.md) | cmd 共用模組：`aos_flags.py`、`aos_ws.py`、`daemon_ctl/`（CLI 對話與介面宣告共用模組在 `lib/agent/`） |
| [install.sh](install.sh) | 把 `impls/*/bin/*` 與 `cmd/*/bin/*` symlink 進 `~/.local/bin`，並在 Python user site 寫兩行 repo `py`／`lib` 絕對路徑的 `aos-proto8.pth`（11-06 晚 K-5；參數換目的地、`--dry-run` 只印、`--uninstall` 拿掉；用法在 [cmd/README](cmd/README.md)） |
| [lib/](lib/README.md) | 工具庫：agent 用的工具（底層原語 → 動 aos 的 → 整隻 agent），templates 用相對捷徑引用 |
| [cases/](cases/README.md) | measure 的共用考題、固定答案與比對器契約；smoke 用 math 的兩題驗門與自洽 |
| [kernel/](kernel/README.md) | llm-kernel（問腦的那台）、daemon-judge、procs-kernel（判官的兩種掛法） |
| [templates/](templates/README.md) | 兩個 agent 範本：`eca-claude`（外部 coding agent）、`agent-fsm`（aos 自己的 loop／fsm agent，11-04） |
| [knowledge/](knowledge/README.md) | 出廠內容樹：普通資料夾＋`.json`，用一般檔案／json 工具讀；第一本是 `aos/`——給小模型的 aos 體系說明（英文） |
| [extras/](extras/README.md) | langs：Janet／Lua 寫 aos |
| [archive/](archive/README.md) | 封存（llm-kernel 示範、self-improve、nvim 外掛、Lua／Janet agent_dan、aos-chat；清單在它的 README） |
| [thinking/](thinking/README.md) | 討論紀錄（使用者原文、決定、結論） |
| [notes/](notes/README.md) | AI 寫的參考筆記（不算數） |
| `user-advice/` | 使用者自己的意見稿 |

**以 [CONCEPTS.md](docs/CONCEPTS.md) 為準**（概念層：名詞、規則 C-01～C-73，作廢的號只留在表上；只收使用者說過的）。圖解兩頁（10-20 的狀態）：概念層 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作想法 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm （HTML 源在 scratchpad/pages/proto8-concepts.html、proto8-impl.html）。實作上的想法在 [restart §3g](thinking/2026-10/11/restart/README.md)（10-11 晚口述：inst→loop→daemon→tick-tock→kernel→agent→閉環）。

## 現況

- **資料夾＝程式**（使用者 10-19 定）：aos 只訂六個環境變數和一支 `aos-exec [--ws WS] XXX [args...]`；入口四種、`XXX` 的找法、`#/` 尋址、`+x` 但沒 `#!` 的檔用 `/bin/sh` 跑（§ 21「不擋」、§ 22「乙」）都在 [NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62）。巢狀由程式自己訂子 stack；這次要做啥隨意。10-16 那套作廢，原話與裁定在 [thinking/2026-10/19/ideas/README.md](thinking/2026-10/19/ideas/README.md)（使用者：「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」）。範例：agent-bob 叫 cathy 叫 stamp 四層、agent-ann 全內嵌對照（11-04 先搬進 tests/fixtures、同天隨 proto8/tests 刪了）。
- **實作**：[impls/](impls/README.md) 是唯一實作（C／C++；使用者 10-23「python版本可以刪掉了。aos-exec/loop/daemon都用C++」，fsm 也用 C++、時鐘先留 Python，[cmd/](cmd/README.md) 是 Python 的 aos-clock 等），命令列有 aos-exec、aos-loop、aos-fsm、aos-daemon 等（全表見它的 README）；刻意沒有 aos-inst 命令列。loop／daemon／fsm 格「要跑什麼」那一格叫 `exec`（使用者「exec，loop／daemon 的 run 也一起改 exec」，[thinking](thinking/2026-10/23/naming.md)）。
- **kernel** 已有 [kernel/](kernel/README.md) 的 llm-kernel（問腦）、daemon-judge 與 procs-kernel（判官的兩種掛法）；底層用 impls 的 `aos-daemon`／`aos-loop`。tasks 仍無實作，待照新做法重寫（[NORMS 待定](docs/NORMS/08-待定.md)）；時鐘是 `cmd/aos-clock`，腦的工具呼叫範本是 `templates/agent-fsm`、慣例 [P-41](docs/CONVENTION.md)。

## 入口

- **[CONCEPTS.md](docs/CONCEPTS.md)**：概念——aos 怎麼看世界（C-01～C-73）。
- **[NORMS.md](docs/NORMS.md)**：規範——從概念推出來、大家都要守的（比實作重要，C-45）；程式符合規範但不強制。底在 [NORMS/10](docs/NORMS/10-基礎設施-定義與工作區.md)（N-57～N-62：六個環境變數、`aos-exec XXX`、找入口、`#/` 尋址）。
- **[CONVENTION.md](docs/CONVENTION.md)**：aos agent 慣例（P-05～P-41）——我們自己人寫 agent 時照抄的標準形狀，不要求別人守。
- **[templates/](templates/README.md)**：`eca-claude`（外部 coding agent 範本）與 `agent-fsm`（aos 自己的 loop／fsm agent 範本，idle／think／wait／act 四格），都用 `aos-agent ctl add` 掛（宣告在 `interfaces.json`）；`agent-fsm` 的 think 組請求、wait 經 [kernel/](kernel/README.md) 的 llm-kernel 寄信與收回信。
- **[kernel/](kernel/README.md)**：llm-kernel 的啟動與問腦用法、daemon-judge／procs-kernel 的判官接法。
- **10-24 一天的嘗試**（使用者「我隨便說，你隨便做，反正只是嘗試」；代定都可翻案，一覽在 [session log 10-24](../wf/session_logs/2026-10-parts/12-10-24.md#2026-10-24)）：[lib/](lib/README.md)（工具＝函式庫）、給人用的 say／listen（11-04 併進 [aos-agent](cmd/aos-agent/README.md)）、[aos-mcp](cmd/aos-mcp/README.md)（同批的 aos-ai 11-03 刪了）、[aos-grow](cmd/aos-grow/README.md)（函數成長）、[langs/](extras/langs/README.md)（Janet、Lua 寫 aos）、[aos-sandbox](cmd/aos-sandbox/README.md)（Linux 權限與沙箱）；當時的十幾隻範例 agent 11-04 刪了（nvim 外掛、self-improve、llm-kernel 示範封存在 proto8/archive/）。
- **[thinking/](thinking/README.md)**：討論紀錄，一天一份，使用者的話照原意記、AI 的話標明是 AI 的。
- **[notes/](notes/README.md)**：AI 寫的參考筆記（不是規範、不算數）：拿外面現成的東西跟 aos 對照，例如 [跟 s6、runit 的對照](notes/s6-runit.md)。
- 之前乾淨的兩個時刻，要回頭看的：九月初 [ideas 13 章](../wf/workflows/ideas/README.md)、十月初 proto7 核心 spec 與 設計原則。
- 使用者自己的草稿：[user-advice/2026-09/](user-advice/2026-09/)（2026-09-19～24；原在 repo 頂層 `thinking/`，11-05 搬來）。
- 這兩個月做過什麼、每一代長什麼樣：[thinking/2026-10/11/restart/README.md](thinking/2026-10/11/restart/README.md) 第一節。

## 規矩（使用者 10-11 定）

- 討論先記下來，再動手；程式等想法穩了才開。
- proto7-2 的東西不搬過來，要用再去拿。
- 派 AI 做設計思考前，先讓它**通讀 CONCEPTS、NORMS 與 CONVENTION 全部**再動手（10-15 使用者：「現在的概念和規範應該都不多吧，後續交給fable思考的時候，讓他們通讀一遍再去做」）；交回的稿先對過 C-48（指示詞有 $env、$ref 兩個）、C-68～C-70（資料夾＝程式、aos 只訂環境變數）、KISS、層徹底切割、少用 sh，不合的打回；跟原則相撞的帶著衝突來問使用者（wf user.md「規劃交給 fable、只把衝突帶給他」），不原樣端給使用者。
