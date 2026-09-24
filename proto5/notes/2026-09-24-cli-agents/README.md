← [notes 索引](../README.md)｜[proto5 README](../../README.md)

# 把 Claude Code 與 Codex 兩支 CLI 納進 aos：提案（2026-09-24）

**只是提案**：沒改程式、沒改規範、沒真跑兩支 CLI（只查了 `--help`，見 [cli-facts](cli-facts.md)）。要使用者拍的在[最後](#要使用者拍的)。

## 使用者要的

1. 「再去幫我弄一個提案，關於把 claude code cli 和 codex cli 納進現有體系。」
2. 「也就是拿這兩個很成熟的 cli，來作為 aos-agent 的備用。」
3. 「其實也不用是同一個 agent 家，只是想將其納入 kernel 和 daemon，和 aos-inst 體系。」（**以這句為準**）
4. 「可以多想想怎麼利用啦。」→ [uses.md](uses.md) 列了十五個用法。

## 一句結論

**不用寫新種類的 cpu。** claude-cpu／codex-cpu＝一個池名叫 `claude`／`codex` 的**普通 exec cpu**，環境裡找得到那支 CLI；
一張單子＝一份 inst，argv 就是 `claude -p …`／`codex exec …`，任務書接 stdin、結果接 stdout 檔。kernel 派單、daemon 拉起與重拉、aos-exec 逾時砍，**全照現有的，一行不改**。
這跟 cpu 規範已拍板的「工作單只有 `aos-exec` 一種 method」「cpu 的環境就是工作的環境」完全同一個道理（llm cpu 也是這樣來的）。細節在 [as-cpu.md](as-cpu.md)。
「零程式」只到**人手動放單**為止；安全取消、額度控制、可靠地接著聊都要階 1 以後的程式。

## 五個角色

六軸：**少**用 LLM／**穩**／**省**資源／**快**／人易**懂**／**安**全（第六軸是我補的）。＋好、○普通、－差。

| 角色 | 怎麼接 | 要改什麼 | 少 穩 省 快 懂 安 | 這次 |
|---|---|---|---|---|
| **當一種 cpu／池**（[as-cpu](as-cpu.md)） | 池＋inst 範本；`aos-kernel add --once --pool claude` | 階 0：零程式；階 1：`aos-cli` 三段 | ＋ ＋ ○ ○ ＋ ○ | **主方案** |
| 當 agent 的工具（[others §2](others.md#2-當-agent-的一個工具主方案做完就有)） | `delegate` 當受信任的投遞入口：只收任務書、馬上回單號 | 小工具包約 120 行＋牢 | － ＋ ○ ○ ＋ ○ | 主方案做完順帶 |
| 當 agent 的大腦（[others §3](others.md#3-當一個-agent-的大腦可選)） | llm.json 一筆 `kind: claude-cli`，agent 改代號就換腦；session id 存在記憶那則回話裡 | aos-llm 約 150 行＋check＋aos-agent「結果不明不重問」 | ○ ○ ○ － ＋ ○ | 可選 |
| 當純模型後端（[others §1](others.md#1-當純模型後端先不做)） | `claude -p --tools ""` 逼它回 tool_calls | aos-llm 約 80 行 | － － ○ － ○ ＋ | 先不做 |
| 反過來用 aos（[others §4](others.md#4-反過來讓它們用-aos)） | 一份 skill 教它跑 `aos-kernel`／`aos-cli`；MCP 以後 | skill 零程式 | ＋ ○ ＋ ○ ＋ － | 順帶 |

跟一般 exec 工作最大的不同：**一張單子是分鐘到半小時、要花額度、會自己改檔、重跑不安全、取消現在做不乾淨**（[as-cpu §7、§10](as-cpu.md#7-長任務逾時取消)）。

## 建議：先做什麼

**階 0（零程式，今天就能用）**：kernel.json 多一顆 `{"pool": "claude"}`、兩顆 `{"pool": "codex"}`；寫兩份 inst 範本與一段教程；`aos-kernel add … --once --pool codex` 丟任務書、`aos-kernel ls` 看、讀 `out/`。
先拿 **codex 唯讀審查**（[uses §2](uses.md#2-codex-cpu-當唯讀審查員)）試：`-s read-only` 最安全，而且調度者每輪都在做這件事，最容易比出好壞。
要動的檔：`proto5/tutorials/` 加一篇（約 150 行文字）＋兩份範本 inst（放 `proto5/tools/` 旁或 notes），**不動 `lib/`、`spec/`**。

**階 1（`aos-cli`）**：讓人像 `aos-agent say` 一樣跟它講話，並記住 session。分三段估（審查建議：一口氣估只夠順利路徑）：

| 段 | 內容 | 量 |
|---|---|---|
| 1a 基本投遞 | `init`／`say`／`run`／`listen`／`status`：產 inst、放單、收回音、ack、解析兩種輸出 | 約 250 行程式＋200 行測試，1 天 |
| 1b 可靠 session | 持久單號、「kernel 判成功才推 session」、busy、結果不明不重送、連敗暫停 | 約 150＋150 行，1 天 |
| 1c 取消 | 盡力取消（砍前再確認 cpu 手上的單）、busy 到確認停下 | 約 80＋100 行，半天；乾淨版要 kernel「按單號砍」 |

測試用假的 `claude`／`codex` 腳本放 PATH（不花錢），要測半行 JSON、寫完結果後被砍、取消時 cpu 已換單。放在新 `lib/aos_cli.py`＋`cli/aos-cli`＋`lib/test/test_aos_cli.py`。

| 其他要改的 | 檔 | 量 |
|---|---|---|
| 規範：cli 家、單子範本、session 規則 | 新 `spec/aos-cli/`（3～4 個小檔） | 小 |
| 導航 | `proto5/README.md` 指令表一列、`lib/README.md`、code map | 幾行 |

kernel、daemon、aos-exec、aos-agent、aos-llm **都不動**。

**階 2（牢）**：等 agent-access 的 `aos-jail` 落地，`aos-cli run` 在前面接它：任務書唯讀、輸出另掛、專用設定資料夾、網路只准連 API（約 60 行）；見 [cost-safety §3](cost-safety.md#3-跑在牢裡還是牢外)。

**先不要**：
- 不另寫 claude 專用的 cpu 主人程式（違反 cpu 規範兩條拍板，還得重做 daemon 握手與停機）。
- 不把 claude 單子登記成**反覆**行程（失敗會被 kernel 排回去重跑＝重花錢、重改檔）。
- 不做純模型後端；不做 MCP 伺服器（skill 就夠）；大腦方案等主方案跑過一陣子再說。
- 不把 ff-merge、push 交給任何單子（鐵律 2）。

**做之前一定要實測的五件事**（[cli-facts 末](cli-facts.md#還沒驗做原型第一天要驗的)）：claude 吃不吃 stdin 與 json 欄位名、訂閱下 `--max-budget-usd` 有沒有用、巢狀 claude 會不會被擋、codex `--json` 事件與 `resume` 怎麼指定沙盒、兩支在 bwrap 裡跑不跑得起來。

## 最要注意的三個洞

1. **搶額度**：aos 用的是使用者自己的訂閱登入，跟使用者、跟調度者共用同一份額度。煞車靠池的大小（`claude` 池 1 顆）＋逾時＋連敗暫停（[cost-safety §1](cost-safety.md#1-錢花在哪)）。
2. **誰都能叫**：能往 `K/requests/` 放檔就能開一張 claude 單子、跑任意指令，包括 agent 的 bash 工具。花錢的池放**另一個 kernel 家**只是管理上分區；要讓 agent 用，得配受信任的投遞入口＋牢（[cost-safety §2](cost-safety.md#2-誰能叫它們)）。
3. **取消不乾淨**：`aos-kernel rm` 不會停下正在跑的單子；只能叫 daemon 砍整顆 cpu，而且有砍錯單的競態（[as-cpu §7](as-cpu.md#7-長任務逾時取消)）。

## 要使用者拍的

| # | 題目 | 我的預設 |
|---|---|---|
| 1 | 主方案：「普通 exec cpu 的池＋inst 範本＋`aos-cli` 包裝」，不寫新種 cpu | **是** |
| 2 | 第一版跑在牢外（用你自己的登入），靠保守旗標；牢等 agent-access 落地 | **是**；預設旗標見 [cost-safety §4](cost-safety.md#4-危險動作怎麼擋)，`bypass`／`--dangerously-*` 只准在牢裡 |
| 3 | 花錢的池放另一個 kernel 家（管理分區）、`claude` 池 1 顆、`codex` 池 2 顆；agent 要用得走受信任入口 | **是** |
| 4 | 上下文：一個 cli 家一條 session，每次 `--resume` 都 **fork**，被砍的那次不算數 | **fork** |
| 5 | 要不要讓它讀到你自己的 `~/.claude` CLAUDE.md、記憶與 `~/.codex` 設定 | **不要**（claude `--safe-mode`；codex 用專用的 `CODEX_HOME`——`--ignore-user-config` 只跳過 config.toml，不夠） |

## 檔案

| 檔 | 內容 |
|---|---|
| 本檔 | 結論、角色表、建議、要拍的 |
| [as-cpu.md](as-cpu.md) | 主方案：池、單子怎麼寫、回音、session、`aos-cli`、逾時取消、工具、失敗 |
| [uses.md](uses.md) | 十五個用法，前十一個標角色、牢、花錢、六軸 |
| [others.md](others.md) | 另外四個角色：工具、大腦、純模型後端、反過來 |
| [cost-safety.md](cost-safety.md) | 錢花在哪、誰能叫、牢裡牢外、危險動作 |
| [cli-facts.md](cli-facts.md) | 兩支 CLI 的版本與非互動旗標（只查 help） |
| [review-task.md](review-task.md)／[review-astra.md](review-astra.md) | astra 唯讀審查（必修 11 條已改進，見下） |

## 審查改了什麼

astra 必修 11 條全改：inst 路徑相對解出的 cwd→範例改絕對路徑（1）；砍 cpu 後 kernel 會補拉、取消有競態、`rm` 當下回 `Removed`（2）；`--wait-ms 0` 不是不等、127 屬 `kind=child`、收回音要 ack（3）；池只限同時幾張、預先塞進 kernel 的不會因連敗停、分「手動佇列／受控投遞」、登入來源要明定（4）；另一個 K 只是管理分區、要受信任入口（5）；push 不一定擋得住、任務書唯讀、網路限目的地（6）；`--ignore-user-config` 只跳過 config.toml（7）；`--restricted` 可被 `--tools` 加回、`--bare` 也收 apiKeyHelper、safe-mode 會關 skill／MCP、跑測試要明列 Bash（8）；session 改成「收回音時 kernel 判成功才推」、結果不明保持 busy（9）；大腦方案 `stopped` 也會重問、要改 aos-agent、HTTP 只拿掉 `aos_brain`（10）；試玩員不掛整個 proto5（11）。建議 4 條也照改（codex 事件名、resume 旗標放子命令前、行數分三段、多四個用法）。
