# 2026-10-28 aos-hub 實作：say／listen 對 claude 說話（agent 對話協議）、每種 CLI 一張適配表、副產物留著

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-28 hub-kernel](2026-10-28-hub-kernel.md)（今天定的 14 條決定）、[10-24 say／listen](2026-10-24-say-listen.md)、[10-24 claude／codex 當工具](2026-10-24-cli-tools.md)｜程式：[extras/cli_hub](../extras/eca_hub/README.md)，測試 `proto8/tests/test_hub.py`

> 10-30 起 aos-hub 改做 aos-eca-hub，見 [eca](2026-10-30-eca.md)。

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。下面「結論」除了標明使用者定的，都是隊長照 CONCEPTS／NORMS 代定、**可翻案**。

## 使用者原文（10-28，逐字）

頂層問了四題（①aos-tools ②要不要讓 aos-say／listen 也能對 claude code 說話：hub 轉一手，畫面開著就打進畫面、沒開就 `--resume` 問一次 ③每接一種現成程式，hub 要知道的事定成每種都要交的一張表 ④回答以外的副產物怎麼辦），他回：

> 2.看看實作的複雜度，如果可以，那就試試看。因為在我的想法中，aos-say/listen是面對aos agent的，或許可以提取出相關協議，然後讓hub實作之類。發揮你的opus神力幫我想想... 3.我沒想好，你幫我想。4.反正就留著，以後總會用到。1.還在想。因為像現在這樣掃tool.json，實在太土太粗暴，不夠靈活

稍後：

> hub也可以開始做。aos-mcp也可以做

（aos-tools／aos-mcp 另一隊做，這份不碰。）

隊長攤了方向題「信箱跟 claude 的工作資料夾要不要分開」（代答實例的工作區＝claude 的 cwd，`new/ cur/ out/ done/` 會長在使用者的專案裡；另一條路是信箱放別處），他回：

> 放Stack比較好。

## 結論一：agent 對話協議（從 aos-say／listen 抽出來的）

**白話**：一個工作區就是一個信箱。說話＝往 `new/` 丟一張紙條；誰來回答都行，回答的人把紙條拿到 `cur/`（認領）、把回答寫成 `out/` 裡同名的一張、紙條收進 `done/`；聽＝等 `out/` 出現那一張。aos-say／listen 只認這個信箱，不管後面是誰。

這就是 [CONVENTION P-11～P-14](../docs/CONVENTION/02-題目stack停錯腦.md) 原樣——aos-say／listen 本來就沒碰 agent 本身，所以「提取協議」不用新發明，只補兩個小地方：

| 部分 | 內容 | 出處 |
|---|---|---|
| 地址 | 工作區（`--ws` ＞ `$AOS_WS` ＞ cwd）；**信箱在 stack 裡的**：沒設 `AOS_STACK`、`<資料夾>/.stack/new/` 在＝信箱是 `<資料夾>/.stack/`（它的 stack 就是它自己） | N-58＋10-28 使用者「放Stack比較好。」 |
| 說 | `new/<題名>`，純文字一題一檔；題名＝UTC 時間到毫秒、排序＝先後；先寫暫存再 link、不重名 | P-11、P-12、N-05 |
| 答（服務者要做的） | 照檔名取最前一題搬 `cur/`（`cur/` 有沒做完的先做）；答案寫 `out/<題名>`；題目搬 `done/`；失敗＝題目留 `cur/`、停下等人 | P-11～P-14、P-20 |
| 聽 | 等 `out/<題名>`；`--last` 照 out/ 的時間 | 10-24 決定 5 |
| 有沒有人在服務 | ① `/proc` 裡 `AOS_WS`＝這裡的 aos-loop／fsm／exec／daemon（原有）② **新增**：stack 裡 `server.txt` 寫「`<pid> <程式名>`」、那個 pid 還活著 | 10-28 代定 |
| 卡在哪 | stack 的 `trace.jsonl` 最後一行；**新增**：常駐服務者每題一行，多 `question`、失敗時多 `error`（一行錯），listen 據此說「誰答哪題失敗、原因」 | P-07＋10-28 代定 |

aos loop／fsm agent 是一種實作（agent-dan、bob）；**aos-hub-kernel 是另一種**：替每個納管的實例收題、交給 claude／codex 工具答。

**複雜度：低，已做成**。協議本來就只是檔案，hub 那邊收題、寫答案約 80 行；真正麻煩的是外圍：誰在服務（`/proc` 猜不到常駐的 Python 程式，所以加 `server.txt`）、人接在畫面上時題目要等（工具回 `SessionBad` 就 5 秒後再試）、新資料夾第一次開畫面 claude 會先問「信任這個資料夾嗎」（見已知限制）。

## 結論二：aos-hub 照 10-28 決定改完

10-27 的 `bin/aos-hub` **從來沒進 git**（根 `.gitignore` 的 `bin/` 擋掉了，只有 Linux 家機上有），這次照 10-28 決定重寫，`.gitignore` 加 `!proto8/extras/*/bin/`。

- **常駐 kernel `aos-hub-kernel`**：`$AOS_HUB/kernel.sock` 一行 JSON 問答；狀態只在記憶體（決定 8；重開就清空，遇到問題再說）；`AOS_HUB` 沒設＝`HubMissing`、kernel 沒跑＝指令 `KernelMissing`（決定 3、10）；不建在 aos-daemon 上（決定 14 自由選，Python 常駐最小）。
- **指令**：`ls`、`state`、`add`、`open [-d]`、`pause [--idle 分]`、`stop`、`watch`（用法在 [README](../extras/eca_hub/README.md)）。10-27 的 `pick`、`attach` 由 `open` 取代；不帶參數＝印說明。
- **pause**＝關畫面、對話 id 留著，題目照樣用 `--resume` 答；**stop**＝關畫面，小格整個搬到 `<stack>/hub_archive/<工具名>-<UTC>/`，CLI 自己存的對話拷一份進 `transcripts/`，從清單拿掉（決定 5、6）。拷不搬：CLI 自己之後還能 resume。
- **Ctrl-]＝只跳出**（決定 7），寫進 cli_session 開畫面的 `tmux.conf`（Ctrl-\ 照舊也跳出）。
- **兩種實例**：`add`／`open` 加的＝代答（kernel 收這個資料夾的題）；agent 叫 claude／codex 工具時 cli_session 送來的 register＝只登記（列得到、接得進，不收題——那個工作區的題是 agent 的）。一個資料夾最多一個代答實例（P-18），小格＝`<資料夾>/.stack/<工具名>/`。
- **信箱放在 stack 裡**（使用者 10-28「放Stack比較好。」，決定）：資料夾＝claude 的 cwd（可以是使用者 cd 過去的程式專案），本身不長任何東西；`new/ cur/ out/ done/`、`trace.jsonl`、`server.txt`、小格、`hub_archive/` 全在 `<資料夾>/.stack/`。aos-say／listen 不用給新旗標：cd 到資料夾（或 `--ws 資料夾`）就認得——沒設 `AOS_STACK`、`.stack/new/` 在，就把 `.stack/` 當信箱。stop 只搬小格，信箱的舊題留著。
- **失敗**：題目留 `cur/`、實例標「出錯」、不再收題；人修好後 `pause` 或 `open` 一次＝重新收（P-20）。限數量不做（決定 4）。
- **自動收起**：`reap.json` 改成 `aos-hub pause --idle 30`（10-27 代定的 30 分沿用）。

## 結論三：每種現成程式一張適配表

hub 要接一種新的 CLI，就交這張表（目前是文件；程式裡 claude、codex 兩欄寫在 [lib/agent/cli_session.py](../lib/agent/cli_session.py)，`cli.json` 的 `kind` 選哪一欄）。pi 這台沒裝，只照官方文件填、**沒實測**。

| 欄 | claude（Claude Code 2.1.312，實測） | codex（0.153.4，實測） | pi coding agent（只查文件） |
|---|---|---|---|
| 開新對話（非互動） | `claude -p --output-format stream-json --verbose --session-id <新 uuid>`，題目從 stdin | `codex exec --json -o last.txt -`；id 從 `thread.started` 拿 | `pi -p` 或 `pi --mode json`；常駐用 `pi --mode rpc`（stdin／stdout 一行一 JSON） |
| 接回（非互動） | `-p --resume <id>` | `codex exec resume <id> -` | `--session <路徑或 id>`；`-c` 接最近一段 |
| 開畫面／叫回 | tmux 裡 `claude --settings <hooks> [--resume <id>]` | tmux 裡 `codex [resume <id>] -c notify=[…]` | `pi --session <id>`（沒試） |
| 對話 id 從哪來 | 自己給 uuid | `thread.started`／notify 的 `thread-id` | session 檔頭（文件說 id 預設是 uuid、可自己給） |
| 送一句（畫面開著） | tmux 貼上＋Enter | 同左 | rpc 模式：`prompt`；跑到一半插話 `steer`、排到後面 `follow_up` |
| 一輪講完的訊號 | `Stop` hook（`last_assistant_message`） | `notify`（`agent-turn-complete`） | rpc 的 `agent_settled` 事件 |
| 正在跑的訊號 | `UserPromptSubmit` hook → `busy.txt` | **沒有**（已知坑） | rpc 事件流（`agent_end`／`agent_settled`） |
| 即時進度 | stream-json → 小格 `live.jsonl` | `--json` 事件 → `live.jsonl`（10-28 起） | `--mode json` 事件 |
| 對話存哪（CLI 自己的） | `~/.claude/projects/<cwd 轉的名>/<id>.jsonl` | `~/.codex/sessions/年/月/日/rollout-*-<id>.jsonl` | `~/.pi/agent/sessions/--<路徑>--/<時間>_<id>.jsonl`；`--session-dir` 可改到別處 |
| 副產物（中間訊息、工具呼叫） | 上面的對話檔全有；非互動另有 `live.jsonl` | 同左（rollout 檔＋`live.jsonl`） | session 檔全有（`message`、`custom` 等條目） |
| pause（關畫面） | `tmux kill-server`（邊講邊存，不會掉） | 同左 | rpc：關 stdin＝有序結束 |
| stop 要拷什麼 | 對話檔一份 | rollout 檔一份 | session 檔一份 |
| 權限／花費 | `--tools`、`--permission-mode dontAsk`、`--strict-mcp-config`、`--max-budget-usd`（只對 `-p`） | `-c sandbox_mode=…`、`-c approval_policy="never"`、非 git 要 `--skip-git-repo-check` | `--tools read,grep,find,ls`、`--no-tools`；花費上限沒查到 |
| 開機會卡的提問 | 新資料夾開畫面先問「信任這個資料夾嗎」（10-28 實跑撞到） | 「Resuming session…」要等、信任提問 | 第一次要 `/login` |
| 怎麼挑模型 | `--model haiku` 等 | `-m`／設定檔 | `--model <名>[:思考級]`、`--provider` |

**pi 的 rpc 模式剛好是決定 11（prompt＝stdin／stdout 當 queue）的現成版**：常駐一支 `pi --mode rpc`、`prompt`／`steer`／`follow_up` 就是 push、事件流就是 pop，不用 tmux、不用 hook。要接 pi 時建議走這條（代定，等真的裝了再試）。

## 結論四：副產物——確定都留著（使用者「反正就留著」）

- **CLI 自己全留**：中間訊息、工具呼叫、工具結果都在各自的對話檔（見上表那一欄）；stop 時拷一份進歸檔，aos 這邊也有。
- **非互動那次**：`live.jsonl` 從「每次重寫」改成**只接不重寫**（claude 的 stream-json、codex 的 `--json` 事件都接），一題不漏。
- **畫面上那幾輪**：只有最後一句進 `turns.jsonl`，其餘在 CLI 自己的對話檔。
- 不設計用途。

## 實跑（WSL，10-28）

`~/code/try/hub-say/`：claude 用 haiku、codex 用預設。`add` → `aos-say`「讀 notes.txt，魔術數字是多少」→ `aos-listen` 4 秒拿到「魔術數字是 42。」→ 乘二「84」（同一段對話 `--resume`）→ `open -d` 開畫面（先像人那樣回答信任提問）→ 再加一「85」（打進畫面）→ `pause` → 「講了幾輪」答「4」（`--resume` 接得上畫面那輪）→ codex 兩題「顏色是藍色。」「Blue」→ 兩個都 `stop`，歸檔裡有 `transcripts/` 各一份；kernel 關掉後 `aos-hub ls` 報 `KernelMissing`。claude 非互動四題合計 **$0.00096**（畫面那輪另計、同量級）；codex 走訂閱。（這段是信箱還在資料夾頂層時跑的。）

信箱改放 stack 之後再跑一次：假專案 `proj/src/calc.py`，`aos-hub add proj`、`cd proj`、不給 `--ws` 直接 `aos-say`／`aos-listen`，兩題答「add」「2」；`proj` 頂層只多一個 `.stack/`，題目與答案都在 `.stack/` 的 new／cur／out／done；兩題 $0.0018。

## 代定（可翻案）

1. 協議＝CONVENTION P-11～P-14 原樣，只補 `server.txt` 與 trace 的 `question`／`error` 兩處；沒升進 CONVENTION 條文，用穩再說。（10-30 刪：`server.txt` 刪掉，見 [eca](2026-10-30-eca/09-方向題.md#決定10-30) 衝突 6）
2. IPC＝`$AOS_HUB/kernel.sock` 一行 JSON；kernel 是獨立 Python 常駐、不建在 daemon 上；狀態只在記憶體。
3. 代答實例 vs 只登記實例（10-30 刪：「只登記的實例」這個分類拿掉，見 [eca](2026-10-30-eca/09-方向題.md#決定10-30) 衝突 6）；一個工作區一個代答實例；小格 `$工作區/.stack/<工具名>/`。
4. 失敗停下等人，`pause`／`open` 一次重收；`SessionBad` 5 秒後再試。
5. 歸檔 `<stack>/hub_archive/<工具名>-<UTC>/`，CLI 對話用拷的。
6. `live.jsonl` 只接不重寫（會一直長，清理是人的事，同 P-14 的 `done/`）。
7. 指令集 `ls／state／add／open／pause／stop／watch`，拿掉 `pick`、`attach`；不帶參數＝印說明。
8. 自動收起沿用閒 30 分、靠 aos-loop 跑 `reap.json`。
9. 適配表先是文件，不做成資料檔；pi 建議走 rpc 模式。

## 跟原則的對照（信箱放 stack，10-28）

使用者已定（「放Stack比較好。」），下面兩處字面上對不上，列給他看、不擋：

- **C-65「工作區只放交辦的東西與成果、執行時的東西落在 stack」**：題目與答案算「交辦的東西與成果」，照 C-65 該在工作區；現在放進 stack。換個看法也通：代答實例的「工作區」（P-11 的 `$AOS_WS`）就是 `.stack/` 這個信箱，claude 工作的資料夾只是 CLI 自己的 cwd、不算 aos 的工作區——這樣 P-11～P-14 照字面成立，只是信箱跟它的 stack 是同一個資料夾。
- **P-11 題目＝`$AOS_WS/new/`**：aos-say／listen 多了一條找信箱的規則（`.stack/new/` 在就改用 `.stack/`）。一個資料夾若同時有 aos agent 用它的 `new/`、又被 aos-hub 納管，say 會丟進 hub 的信箱（P-18 本來就說一個工作區一個 agent）。設了 `AOS_STACK` 時不套這條規則。

## 已知限制

見 [cli_hub/README 已知限制](../extras/eca_hub/README.md#已知限制)。
