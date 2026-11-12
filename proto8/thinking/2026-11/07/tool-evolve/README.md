# 工具權限演進與確定性量測的頂層設計：階段從工具清單推出來、只准機器往緊收、確定性用 measure 的重跑樣本分三層報

← [2026-11-07](../README.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

以 fable 的 02 為底稿、opus 隊長補全。題目是使用者 11-07 上午定的路「shell 先開放 → 再謹慎 → 最後全專屬工具」（原話在 [arknights-kb](../arknights-kb/README.md)），aos 要怎麼支援與管理。六題方向題 11-07 傍晚都選推薦；「代定」是隊長替他做的小決定，可翻案。

## 使用者裁定（11-07 傍晚，40 題選項框）

回覆原文全文在 [kb-ideas](../kb-ideas/README.md#11-07-傍晚-40-題裁定原文)；回覆後補一句「很多東西都可以靈活改進，所以後面我就不寫了」（[想法 15](../kb-ideas/README.md)）：各題的判準、標準、階段、門檻本身都可以再被改進，下面寫的是起步值。

- **te-1**（工具權限走到哪個階段，要另存一個欄位嗎？）：選 A「從工具清單推，不寫欄位」。備註原話：「這個"階段"，本身也可以被改進和變換。」
- **te-2**（shell 跑過哪些指令，要記在哪裡？）：選 A「bash 自己小格的 observed.jsonl，cmd 行」。備註原話：「記得定期清理。還有git ignore也斟酌一下。」
- **te-3**（能登記自製工具的三支工具，也算能任意跑程式嗎？）：選 A「算」。
- **te-4**（謹慎期能用 Python 繞過指令白名單，現在要補嗎？）：選 A「不補」。
- **te-5**（重跑穩不穩，要合成一個分數嗎？）：選 A「不要，三樣分開報」。備註原話：「這套本身也是靈活且可以改進的。有需要的話，metainfo評估中可以加入"人類可理解性"，這需要使用者(也就是我)參與評分。」
- **te-6**（連續幾個考題符合條件，才收緊工具權限？）：選 A「2」。備註原話：「也是靈活且可改進。」

## 設計（結論）

### 概念（四條）

1. **任意執行工具**：呼叫者給什麼就跑什麼的工具——`bash`、`run_python`，以及能把呼叫者可寫路徑登記成工具或子 agent 工具的 `self_tools`、`agents`（`new`／`add` 的 `tools`）、`thought`（`tools` 的 `path`）。工具在 `_metainfo.json` 宣告 `"arbitrary_exec": true`，不寫就是 `false`；這是 C-14 的附加特性，不是第十軸。
2. **階段是推出來的值，不是欄位**：看 agent 的有效工具清單（`aos-tools ls --json`，含覆蓋層）——有任一支 `arbitrary_exec: true` 且沒宣告 `sandbox`＝`open`；有但每支都宣告了 `sandbox`＝`boxed`；沒有＝`none`。agent 的階段＝它最鬆的那支工具。`boxed` 是照宣告，真的關住沒有靠關箱考題驗。協調型 agent（會生子、會改自己工具）停在 `open`；走得到 `none` 的是領域窄的專精 agent。
3. **機器只收緊**：審視者的階段招式只有 `extract`（把一種 shell 用法做成專屬工具）、`box`（open→boxed）、`unshell`（boxed→none）。放寬只能人做，或 watch 自動退回時恢復前版。換上前審視者對副本推一次階段，比換前鬆就不准換。
4. **確定性＝自洽，分三層報**：同一份定義、同一個 case 跑 `repeat` 次，樣本彼此比；跟參考答案比叫「一致」，是門，不叫確定性。LLM 步按 endpoint 分開記（C-22b）。

### shell 帳

- bash／run_python 在自己小格（`aos-tools call` 給的 `$AOS_STACK`＝`<stack>/tools/bash/`，N-50）的 `observed.jsonl` 每次追加一行 `{"kind": "cmd", "command", "timeout_s", "exit", "elapsed_ms", "out_bytes"}`；`exit` 是內層指令的結束碼，`tool` 行的 `code` 仍是工具碼。
- 寫入失敗＝`LogFailed`、不跑指令；`AOS_STACK` 沒設（人直接跑）＝不記、照跑。試驗場 `bash_logged` 收進 bash 本體後退場。
- measure 翻帳經 `stack: "tools/bash"` 自然翻得到 `cmd` 行。
- 定期清理、斟酌 .gitignore（te-2 備註）：清的時機與保留多少跟 kernel ledger「誰清」一起定（代定：審視者讀過、寫進 `review.json` 的那幾輪之前的行可清）；stack 本來就照 `stack.gitignore` 擋只追加的 log（N-67）。

### shell_report（lib 工具，唯讀）

stdin `{"stacks": [...], "defs"?}`；對每個 stack 推階段、翻 `cmd` 行歸形狀；審視單位＝measure 的 case，不加新環境變數。形狀規則：`shlex.shlex(punctuation_chars=True)` 切字，遇 `|`、`&&`、`||`、`;` 切段；每段第一個字與 `-` 開頭的保留、其餘換 `<arg>`、重導向與其後一字換 `<redir>`；第一個字用 `shutil.which` 解，解得到的進 `binaries`。輸出 `{"agent", "shell_stage", "arbitrary", "binaries", "shapes": [{"shape", "count", "exit_zero", "cases"}]}`，`arbitrary` 列出讓它停在 `open`／`boxed` 的工具名。

### 謹慎期的包裝（agent 定義裡的 `tools/bash/`）

- `_entry` `["aos-sandbox", "_metainfo.json#/sandbox", "aos-exec", "inner"]`；`inner`、`_tooldef.json` 捷徑到 `<lib>/base/bash`；`_metainfo.json` 的 `sandbox` 格就是白名單，宣告與強制同一份資料。
- `base` 縮小到 `/usr/lib`、`/lib`、`/lib64`、`/etc`，不放 `/usr/bin`；執行檔逐檔放 `ro`；`commands` 只放 `aos-exec`（rg、jq 寫進 `commands` 會綁整個 `/usr/bin`）；`/usr/bin/env`、`bash`、`python3` 是 bash 工具自己要的，一定在白名單（已知漏洞，te-4 不補）。
- `rw` 是 `AOS_WS` 與**工具自己的小格** `AOS_STACK`，不是 agent 整個 stack；`net: false`。
- 白名單＝shell_report 的 `binaries` 減掉已做成專屬工具的，再加執行期必備三支。
- daemon 的 stack 不能在工作區裡（試驗場 `ws/.stack` 要搬出 `ws/`），否則 `rw: $AOS_WS` 把 daemon 的 ctl 信箱一起綁進去。
- 謹慎期管得住「寫哪裡」「能不能連網」；「能跑哪些程式」盡量，封死靠 `none`。daemon 的 `--limits` 管份額，跟階段無關。

### 關箱考題

普通 measure case `cases/box-probe/`：直接跑該 agent 的 `tools/bash`，只用 bash 內建試逃脫（寫 `/tmp`、`/dev/tcp` 連 LiteLLM、列 `$HOME/*`、列 `/usr/bin/*` 應只剩白名單、寫 agent 的 stack），比對器查結束碼／輸出、主機上沒留檔。`box` 換上前必須過這關。

### 階段招式（接 evolve-design 的 downgrade／fix／split 之後）

| 招式 | 什麼時候試 | 做什麼（在副本裡） | 誰寫程式 |
|---|---|---|---|
| `extract` | 同一形狀連續 2 個 case 出現且 `exit_zero == count` | 寫專屬工具資料夾、登記進 `tools.json`；沙箱已開就白名單減掉那支 | 前三個地點只開處方，之後放手 |
| `box` | 已跑 ≥2 個 case、最近 2 個 case `binaries` 沒新增 | 照上節寫 `tools/bash/` 包裝 | 第一天全自動（代定） |
| `unshell` | 最近 2 個 case `cmd` 行為 0，或剩下的形狀都已有專屬工具 | 從 `tools.json` 拿掉 bash 與 run_python | 第一天全自動（代定） |

換上一律走 `promote`，門＝這隻 agent 用到的所有 case（`box` 另加 `box-probe`）全過，之後照 watch。`promote` 不碰 git；階段歷史＝定義根的 `git log -- defs/<名>/tools.json defs/<名>/tools/` 加 `reviews/watch.json`。降級失敗與 shell 帳裡反覆出現的用法，是工具化的兩個來源；不另做 ladder 工具。

### 確定性的三層量法（都用 measure，不另做 repeat_check）

| 層 | 考題怎麼切 | 比法 | 期望 |
|---|---|---|---|
| 腳本步 | 單一腳本當 case，上游產出（含 LLM 輸出）錄好放 `ws/` | 內建逐 byte | 100%，不合＝腳本有 bug |
| LLM 步 | 單一 LLM 步當 case，輸入固定 | 逐條比對器、樣本兩兩比 | 記數字、按 endpoint 分 |
| 整體 | 整個地點當 case | 內建逐 byte、樣本兩兩比 | 不同的檔 ⊆ LLM 產出及其下游 |

- measure.json 多一格 `consistency`：同一支比對器拿 `samples[1..]` 各比 `samples[0]`。
- 結果只在 measure.json，不寫回 `_metainfo.json`；`deterministic` 布林照舊是作者自稱。
- 不合成分數，三樣分開報；需要時 metainfo 評估可加「人類可理解性」，由使用者本人評分（te-5）。
- 量多勤（代定）：腳本步每個地點、LLM 步自洽只在降級試驗順便算、整體每輪一次。整體層可用 `git status --porcelain` 為空當比對器。

### 讀者跑別人寫的公式

`_metainfo` 的 `py`／`lua`／`aos` 公式由 `lib/metainfo.py` 在固定公式沙箱裡算（`net: false`、無 `rw`、`ro` 只有求值器、`cpu_s: 5`、`mem_mb: 256`，代定）；`cal` 在行程內算。

### 各層誰負責

aos-exec、aos-sandbox、daemon、aos-tools 都不改、不認階段；lib 工具負責記 `cmd` 行、宣告 `arbitrary_exec`、新增 `shell_report`、公式沙箱；agent 定義在謹慎期放 `tools/bash/` 包裝；審視者多三招、換前推階段只准收緊；隊長／人是唯一能放寬權限的。

### 與既有條文的讀法

- `arbitrary_exec` 照 C-14 當附加特性，不動九軸（C-13）。
- shell_report 讀的是 `aos-observed` 公開介面，併入 evolve-design 的「只准這一種帳」。
- 「工具＝函式庫」條不改：內層結束碼記在 bash 自己的 `cmd` 行。
- 審視者改別人的定義照 evolve-design 已裁（副本、`promote`、watch），本題只加「機器只收緊」。
- 推出來的 `boxed` 照字面叫「宣告」，真假用關箱考題驗（S4、C-56）。
- 不加 `AOS_UNIT`（C-69），審視單位＝measure 的 case。
- fable 的 `repeat_check`、`ladder`、`meta_observe` 收三樣併進 evolve-design 的 measure／審視者，不做。

## 落地狀況

- aos 本體已做（[impl-plan 完成總結](../impl-plan/14-完成總結.md)）：批 2 宣告 `arbitrary_exec`；批 3 bash 記 `cmd` 行；批 4 measure 的自洽檢查；批 9 `bash-boxed` 改讀自己的白名單、`shell_report`、關箱考題。arknights 線 bash 指令記帳已上線、附清理腳本。
- 未做：審視者的 `box`／`unshell` 自動收緊（只放成處方，等有真資料）；試驗場側（worker daemon stack 搬出 `ws/`、單步 case、`bash_logged`／`exp_run_ladder.py` 退場）交 arknights 線。
