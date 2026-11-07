# 工具權限演進與確定性量測的頂層設計：階段從工具清單推出來、只准機器往緊收、確定性用 measure 的重跑樣本分三層報

← [2026-11-07](../README.md)｜簡報 [01-簡報](01-簡報.md)｜fable 原始輸出 [02-fable規劃](02-fable規劃.md)

## 白話總結

使用者定的路是：agent 剛開始可以隨便用 shell，後來只能用一小撮指令，最後完全不給 shell、只給專屬工具。這份設計回答五件事：一隻 agent 現在走到哪一步怎麼看、怎麼往下一步走、確定性怎麼量、跟沙箱怎麼接、降級試驗扮演什麼角色。

**走到哪一步，不另外寫一格「我在第幾階段」，而是看它手上有哪些工具。**像看一個人的鑰匙圈就知道他進得了哪些房間。手上有一支「什麼都能跑」的 bash，就是開放期；那支 bash 被關進沙箱，只能寫自己的工作區、不能連網，就是謹慎期；手上完全沒有這種工具，就是專屬工具期。這樣不會出現「欄位寫一回事、鑰匙圈又是另一回事」。

**要注意的是，「什麼都能跑」的不只 bash。**現有的 `self_tools`、`agents`、`thought` 都能把 agent 自己寫在工作區裡的資料夾登記成工具或子 agent 的工具，等於繞過去自己做了一把萬能鑰匙。所以這三支也要誠實標成「什麼都能跑」。結果是：會生子 agent、會改自己工具的協調型 agent，永遠停在開放期；真正能走到「全專屬工具」的，是領域很窄的專精 agent，例如只負責裁連結的 linker。這正好吻合使用者說的「領域越窄，能變成工具的地方越多」。

**往下一步走，交給 evolve-design 那隻「審視者」，而且只准它往緊的方向走。**bash 每跑一次指令，就在自己的帳本上記一行：跑了什麼、內層成功沒有。審視者看帳，發現同一種指令用法連續兩個地點都出現，就把它做成專屬工具；指令種類兩個地點都沒有新增，就把 bash 關進沙箱；兩個地點都沒叫 shell，就把 bash 拿掉。改的都是定義的副本，過了考試才換上，退步就自動退回，跟 evolve-design 使用者已裁的「自動換、退步自動退回、容忍短暫退步」同一條路。機器只准收緊；要放寬（把 bash 還回去），只能人來做，或是自動退回時恢復原狀。

**確定性用同一把尺量：同樣的輸入重跑三次，看三次彼此一不一樣。**這把尺就是 evolve-design 的 `measure`，不另做一支。差別只在考題切多大：只考一個腳本步，三次必須一字不差，不一樣就是腳本有 bug；只考一個 LLM 步，看三次的判斷有幾成一樣，而且要按模型分開記，因為換一個模型就是另一個數字；考整個地點，看重跑後有幾個檔一字不差。三個數字分開報，不合成一個分數，因為合起來就看不出是哪一步不穩。這裡要分清兩件事：「三次彼此一樣」叫自洽，是確定性；「跟聰明模型的答案一樣」叫一致，是降級考試的門。今天的 terra 對 sol 是 94%，那是一致，不是確定性。

**沙箱只在謹慎期上場，照原本的規矩：誰叫就誰關。**謹慎期的 bash 是 agent 自己定義裡的一個小包裝，第一個字就是 `aos-sandbox`，設定直接指向自己 `_metainfo.json` 裡的 `sandbox` 那一格，宣告跟強制是同一份資料。核對現有程式時發現一個坑：沙箱預設會把整個 `/usr` 唯讀放進去，用 `commands` 列指令也是整個資料夾放進去，所以「只准 rg、jq」這種白名單現在其實擋不住。要真的只給幾支指令，得把底層縮小、再一支一支放進去；而且 bash 工具本身是 Python 寫的，Python 一定在裡面，agent 還是能用 Python 繞過白名單。謹慎期管得住的是「寫哪裡」和「能不能連網」，「能跑哪些程式」只能做到盡量；真正封死要等到專屬工具期。daemon 的 `--limits` 管的是吃多少記憶體與 CPU，跟階段無關。

**降級試驗是找工具化候選的探測器。**這件事 evolve-design 的審視者已經在做：先換便宜一級的模型考三次，過不了就看這一步能不能寫成腳本，再不行就拆小。本題只補一句：降級失敗的那一步，連同 shell 帳裡反覆出現的用法，就是工具化的兩個來源。

## 設計

### 概念（四條）

1. **任意執行工具**：呼叫者給什麼就跑什麼的工具。包括 `bash`、`run_python`，以及能把呼叫者可寫路徑登記成工具或子 agent 工具的 `self_tools`、`agents`（`new`／`add` 的 `tools`）、`thought`（`tools` 的 `path`）。工具自己在 `_metainfo.json` 宣告 `"arbitrary_exec": true`；不寫就是 `false`。這是 C-14 的附加特性，不是第十軸。
2. **階段是推出來的值，不是欄位**。一隻 agent 的有效工具清單（`aos-tools ls --json`，含覆蓋層）裡：
   - `open`：有任何一支 `arbitrary_exec: true` 且 `_metainfo` 沒有 `sandbox` 的工具；
   - `boxed`：有 `arbitrary_exec: true` 的工具，但每一支都宣告了 `sandbox`；
   - `none`：沒有 `arbitrary_exec: true` 的工具。
   工具本身沒有階段；agent 的階段＝它最鬆的那支工具。推出來的 `boxed` 是「照宣告」，真的有沒有關住，靠下面的「關箱考題」驗（C-56、S4）。
3. **機器只收緊**：審視者能做的階段招式只有三種，方向都是往緊：`extract`（把一種 shell 用法做成專屬工具）、`box`（open→boxed）、`unshell`（boxed→none）。放寬只能人來做，或由 watch 自動退回時恢復前版。
4. **確定性＝自洽，分三層報**：同一份定義、同一個 case 跑 `repeat` 次，樣本彼此比。考題切成腳本步、LLM 步、整體三種大小；LLM 步按 endpoint 分開記（C-22b：節點＝函式＋環境）。跟參考答案比的「一致」是門，不叫確定性。

### shell 帳：bash 在自己的 observed.jsonl 記 `cmd` 行

不用 fable 原稿的 `calls.jsonl`，改用 evolve-design 已定的公開介面 `aos-observed`，讀的人只認這一個介面（C-52 11-06 讀法）。bash 工具的小格就是 `aos-tools call` 給它的 `$AOS_STACK`（＝叫它那隻的 `<stack>/tools/bash/`，N-50）。bash 在裡面的 `observed.jsonl` 每次追加一行：

```json
{"kind": "cmd", "command": "rg -n 煮傘居士 source/", "timeout_s": 30, "exit": 1, "elapsed_ms": 42.0, "out_bytes": 0}
```

- `exit` 是內層指令的結束碼，修不足 #24；agent 那層 `tool` 行的 `code` 仍是工具碼，各歸其層（「工具＝函式庫」條不動）。
- 寫入失敗＝退 `LogFailed`、不跑指令（沿用試驗場 `bash_logged` 的做法，收進 bash 本體；`bash_logged` 退場）。`AOS_STACK` 沒設（人直接跑）＝不記、照跑。
- 小格的 `interfaces.json` 由 `lib/observed.py` 第一次寫檔時一起寫（evolve-design 步 3）；`cmd` 這種行的格式交 evolve-design 收進 observed 的行種。
- measure 翻帳時，agent 的 `tool` 行有 `stack: "tools/bash"`，自然翻得到 bash 的 `cmd` 行，不必另走訪。

### shell_report（lib 工具，唯讀）

stdin：`{"stacks": ["<絕對路徑>", ...], "defs"?: "<定義根>"}`。對每個 stack：用 `aos-tools ls --json` 推階段；照 `aos-observed` 翻到所有 `cmd` 行、歸形狀。審視單位＝case（measure 的 `runs/<i>/stack/` 各是一次），不加新環境變數。

形狀規則（gpt 照做，不另發明）：

- 用 `shlex.shlex(punctuation_chars=True)` 切字；遇到 `|`、`&&`、`||`、`;` 就切成獨立段。
- 每段：第一個字保留；以 `-` 開頭的保留；其餘換成 `<arg>`；重導向符號與它後面那個字換成 `<redir>`。
- 第一個字用 `shutil.which` 在主機上解；解得到的實際路徑進 `binaries`，解不到（shell 內建如 `cd`、`echo`，或根本沒有）不進。

```json
{"agent": "/abs/defs/place_lead", "shell_stage": "open",
 "arbitrary": ["bash", "thought", "agents"],
 "binaries": ["/usr/bin/rg", "/usr/bin/python3"],
 "shapes": [
   {"shape": "rg -n <arg> <arg>", "count": 5, "exit_zero": 3, "cases": ["poshan", "qieernuoboge"]},
   {"shape": "python3 <arg>", "count": 2, "exit_zero": 2, "cases": ["poshan"]}
 ]}
```

`arbitrary` 列出讓它停在 `open`／`boxed` 的工具名，人一眼看得出「卡在 bash」還是「卡在 thought」。

### 謹慎期的包裝（agent 定義裡的 `tools/bash/`）

fable 原稿的範例在現有 `aos-sandbox` 上跑不起來（少了 `aos-exec`、`tool_io.py`、小格），白名單也擋不住。改成：

```
tools/bash/
  _entry          ["aos-sandbox", "_metainfo.json#/sandbox", "aos-exec", "inner"]
  inner     →     <lib>/base/bash（捷徑）
  _tooldef.json → <lib>/base/bash/_tooldef.json（捷徑）
  _metainfo.json
```

```json
{
  "summary": "bash inside a sandbox: workspace-only writes, no network, listed programs only",
  "arbitrary_exec": true,
  "sandbox": {
    "base": ["/usr/lib", "/lib", "/lib64", "/etc"],
    "commands": ["aos-exec"],
    "ro": ["inner", "<lib>/tool_io.py",
           "/usr/bin/env", "/usr/bin/bash", "/usr/bin/python3",
           "/usr/bin/rg", "/usr/bin/jq"],
    "rw": [{"$env": "AOS_WS"}, {"$env": "AOS_STACK"}],
    "net": false,
    "mem_mb": 1024, "cpu_s": 120, "file_mb": 100
  },
  "side_effect": true, "idempotent": false, "deterministic": false, "interrupt": "unsafe", "parallel": true
}
```

gpt 會卡的地方，逐條寫清：

- `aos-exec` 跑 `_entry` 時 cwd 是這個資料夾，所以 `_metainfo.json#/sandbox`、`inner` 都用相對路徑（同現有 `bash-boxed`）。
- 縮小 `base`：只留函式庫與 `/etc`，**不放 `/usr/bin`**；執行檔逐檔放進 `ro`（`bind()` 綁單檔可以）。`/bin` 在 Arch 是指向 `usr/bin` 的連結，不綁就不在。
- `commands` 只放 `aos-exec`（它會綁整個 `impls/aos-exec/bin`，目前那裡只有 aos-exec）。**不要**把 rg、jq 寫進 `commands`，那會綁整個 `/usr/bin`。
- `/usr/bin/env`、`/usr/bin/python3`、`/usr/bin/bash` 是 bash 工具自己跑起來要的（`_entry` 是 `#!/usr/bin/env python3`），一定在白名單裡；這是已知漏洞（agent 可以 `python3 -c` 做任何事，但仍然只能寫工作區與小格、不能連網）。
- `rw` 的 `AOS_STACK` 是**工具自己的小格**，不是 agent 整個 stack；`cmd` 帳寫在這裡。
- 白名單＝shell_report 的 `binaries` 減掉已經做成專屬工具的那些，再加上上面三支執行期必備。
- **daemon 的 stack 不能在工作區裡**：試驗場現在是 `ws/.stack`（`defs/root_daemon/daemon.json`），`rw: $AOS_WS` 會把整台 daemon 的 ctl 信箱綁進去，沙箱形同虛設。試驗場要先把 worker daemon 的 stack 搬到 `ws/` 外面。

### 關箱考題（驗 `boxed` 不是只有宣告）

一個普通的 measure case `cases/box-probe/`：`run.json` 直接跑該 agent 的 `tools/bash`，stdin 依序是逃脫嘗試，**只用 bash 內建**（白名單外的程式本來就叫不到，拿它們試等於沒試）：`echo x > /tmp/box-probe`（之後在主機上查這個檔不存在）、`exec 3<>/dev/tcp/127.0.0.1/4000`（連 LiteLLM，應失敗）、`echo $HOME/*`、`echo /usr/bin/*`（應只列白名單幾支）、`echo x > "$AOS_STACK/../../history.jsonl"`（寫 agent 的 stack，應失敗）。比對器檢查每一條的 `[exit code N]` 或輸出是否符合預期、主機上沒有留下檔案。`box` 招式換上前必須過這一關，跟其他 case 一樣是門。不加新機制。

### 階段招式（審視者的 move，接 evolve-design 的 downgrade／fix／split 之後）

| 招式 | 什麼時候試 | 做什麼（在副本 `reviews/<輪>/defs/` 裡） | 誰寫程式 |
|---|---|---|---|
| `extract` | 同一形狀連續 2 個 case 出現且 `exit_zero == count` | 寫一支專屬工具資料夾（argv 陣列入口、arguments 從 stdin、`_tooldef.json`、`_metainfo.json`），登記進目標的 `tools.json`；若沙箱已開，白名單減掉那支執行檔 | 照使用者裁定：前三個地點只開處方（交 gpt 施工），之後放手 |
| `box` | 已跑 ≥2 個 case，且最近 2 個 case `binaries` 沒有新增 | 依上節寫 `tools/bash/` 包裝，`tools.json` 的 bash 指向它 | 機械動作，第一天就全自動（代定） |
| `unshell` | 最近 2 個 case `cmd` 行為 0，或剩下的形狀都已有專屬工具 | 從副本的 `tools.json` 拿掉 bash（與 run_python） | 機械動作，第一天就全自動（代定） |

- 換上一律走 `promote`，門＝這隻 agent 用到的所有 case（`box` 另加 `box-probe`）全過；之後照 watch 容忍短暫退步、超過才自動退回（evolve-design 使用者已裁）。
- 招式只能讓階段變緊或不變。換上前審視者用 shell_report 對副本推一次階段，比換前鬆＝不准換（代定）。
- `promote` 不碰 git（C-52：它不知道定義根是不是 git）。試驗場每個地點做完照舊 commit 定義根，所以「階段的歷史」＝`git log -- defs/<名>/tools.json defs/<名>/tools/`，加上審視者的 `reviews/watch.json`。
- 降級失敗（review.json 的 `tried` 裡 `downgrade` 的 `pass: false`）在 evolve-design 已接到 `fix`／`split`；本題不另做 ladder 工具，`exp_run_ladder.py` 等審視者上線就退場。

### 確定性的三層量法（都用 measure，不另做 repeat_check）

| 層 | 考題怎麼切 | 比法 | 期望 | 不合時代表 |
|---|---|---|---|---|
| 腳本步 | 單一腳本當 case（`run.json` 的 `exec` 是那支），初始 `ws/` 放好上游產出（含 LLM 步的錄好的輸出） | 內建逐 byte | 100% | 腳本有 bug（時間戳、dict 順序、讀了時鐘） |
| LLM 步 | 單一 LLM 步當 case，輸入固定（例：婆山鎮的 linker 候選） | 逐條比對器，樣本兩兩比 | 記數字，按 endpoint 分 | 用來排「哪步最不穩」 |
| 整體 | 整個地點當 case（`place_run`） | 內建逐 byte，樣本兩兩比 | 不同的檔 ⊆ LLM 產出及其下游 | 腳本步漏了確定性 |

- **自洽與一致分開**：measure 的 `check.scores` 是對 `expect/` 的分數（門，「一致」）；本題要的確定性是樣本之間的分數。建議 measure.json 多一格 `consistency`：用同一支比對器，拿 `samples[1..]` 各自比 `samples[0]`，例 `{"consistency": {"scores": [1.0, 0.94], "compare": "<比對器>"}}`；格式交 evolve-design 收。
- **腳本步要「錄放」**：整體重跑時 LLM 會重問，下游腳本吃到不同輸入，整體不同不代表腳本不穩。所以腳本步的確定性一定用單步 case、上游輸出錄好放進 `ws/`（今天 `place_run --check` 不重問 LLM，就是這個做法）。
- **結果存哪**：只在 measure.json（審視者的 stack／工作區）。不寫回 `_metainfo.json`（待定稿「實測不回寫」）；`deterministic` 布林照舊是作者自稱（C-13）。試驗場的 `_observed.json` 照 evolve-design 退役，fable 原稿「meta_observe 收三樣」那步不做。
- **不做合成分數**：報三樣——腳本步全部 100% 與否、每個 LLM 步每個 endpoint 的自洽分數、整體相同檔比例。
- **量多勤**（代定）：腳本步每個地點都量（零 token）；LLM 步的自洽只在降級試驗時順便算（反正已經跑三次）；整體每輪一次。
- **git 是整體層的現成尺**：知識庫本身是 git，整體重跑後 `git status --porcelain` 為空就是整體一字不差，可以當一支比對器的實作。

### 讀者跑別人寫的公式（evolve-design 衝突 4 交來的）

`_metainfo` 的 `py`／`lua`／`aos` 公式是讀者在跑別人寫的程式。規則（代定）：`lib/metainfo.py` 求這幾種 key 時，argv 前接 `aos-sandbox <lib>/metainfo/formula-sandbox.json`；那份設定 `net: false`、沒有 `rw`、`ro` 只有求值器本身、`cpu_s: 5`、`mem_mb: 256`。`cal`（四則）在行程內算，不用沙箱。

### 各層誰負責

| 層 | 要做什麼 | 不做什麼 |
|---|---|---|
| aos-exec | 不改 | 不讀 `_metainfo`、不認階段 |
| aos-sandbox | 不改（`檔#/指標` 設定、單檔 `ro`、窄 `base` 都已支援） | 不加白名單 key、不認階段 |
| daemon | 不改；`--limits` 照舊管份額 | 不知道工具與階段（不足 #11 另案） |
| aos-tools | 不改；`ls --json` 已帶 `_metainfo` | 不加階段欄位 |
| lib 工具 | `bash`／`run_python` 記 `cmd` 行、宣告 `arbitrary_exec`；`self_tools`、`agents`、`thought` 宣告 `arbitrary_exec`；新增 `shell_report`；`metainfo.py` 的公式沙箱 | 不讀 history；不另做 repeat_check／ladder |
| agent 定義 | 謹慎期放 `tools/bash/` 包裝 | 執行中不被寫（P-15） |
| 審視者（evolve-design 的 `templates/reviewer/`） | 多三招 `extract`／`box`／`unshell`；換前推階段、只准收緊；measure 加 `consistency` | 不放寬權限 |
| 試驗場 | worker daemon stack 搬出 `ws/`；`bash_logged`、`exp_run_ladder.py` 退場；建 `box-probe` 與單步 case | 不自己再寫比對 |
| 隊長／人 | 唯一能放寬權限；語意抽查 | 不再手算階段 |

## 與既有 CONCEPTS／NORMS 的衝突

fable 原稿列了 6 條；核對後第 4 條改照使用者在 evolve-design 的裁定，另補 6 條（7～12）。

1. **C-13 九軸固定 vs 新增 `arbitrary_exec`。**九軸沒有「能不能跑任意程式」這一軸。照 C-14 當附加特性放進 `_metainfo`，不填＝`false`。後果：不動九軸；但「沒填」跟「真的不是」分不出，靠 lib 工具都填來補。是否升成一軸交 evolve-design 定 metainfo 總格式時一併看。
2. **C-52、C-81（stack 對外介面只有四類：命令列參數、環境變數、stdin/out/err/exit、信箱內容格式）vs shell_report 讀別人 stack 裡的帳。**改用 evolve-design 的 `aos-observed` 公開介面後，跟 measure 翻帳是同一件事，衝突併入 evolve-design 衝突 5（「只准這一種帳、宣告成公開輸出」）。後果：不需要第二種可讀的檔；不接受的話，shell 用法只能由 agent 範本在 `tool` 行抄指令內容，等於 agent 層替工具層記帳。
3. **「工具＝函式庫」條：被跑的指令退非 0 不算工具的錯 vs 要量指令成功率（不足 #24）。**不改條文：工具碼照舊，內層結束碼記在 bash 自己的 `cmd` 行。
4. **P-15／C-46「定義資料夾執行中不被寫、改定義是人有意的事」vs 審視者改別人的定義來轉階段。**已交 evolve-design，使用者已裁「自動換、退步自動退回（要容忍短暫退步，像 epoch）」「審視者先處方、三個地點後放手」。本題照這條走：階段招式改副本、經 `promote` 換上、watch 盯著。本題只多加一條限制：機器只准收緊。fable 原稿「審視者手動套用、不自動」的推薦作廢。
5. **待定稿「`_metainfo` 實測不回寫」＋`deterministic` 是布林 vs 使用者要分層的確定性數字。**不衝突：布林是作者自稱，數字只在 measure.json。後果：要看確定性得看審視者的帳，不能只看定義。
6. **沙箱 S6、C-66（工作區靠 `AOS_WS` 指標、能不能寫由 Linux 管）vs daemon stack 放在工作區裡。**不是條文衝突，是現況的坑：試驗場的 worker daemon stack 就在 `ws/.stack`，謹慎期一綁 `AOS_WS` 就把 daemon 一起綁進去。`aos-sandbox` 的 README 已點名。後果：不搬，謹慎期擋不住 agent 去寫 daemon 的 ctl 信箱。
7. **沙箱 S4「宣告放 `_metainfo`、強制只在 argv」、C-56「寫什麼就做什麼」vs 階段從宣告推。**推出來的 `boxed` 只代表 `_metainfo` 寫了 `sandbox`，`_entry` 有沒有真的接 `aos-sandbox`，讀者不看（看 `_entry` 就是認內部檔，C-52）。解法：報告照字面叫「宣告」，真假用關箱考題驗。後果：多一個 case；不驗的話，宣告跟強制可以悄悄脫鉤。
8. **沙箱 S6 的 `base` 預設與 `commands` 綁整個資料夾 vs「謹慎期只給幾支指令」。**照現有程式，`base` 預設含整個 `/usr`，`commands` 綁指令所在的整個資料夾，指令白名單形同沒有。要用窄 `base`＋單檔 `ro`，不必改程式。後果：白名單寫起來囉嗦；而 bash 工具自己要 Python，所以「只能跑哪些程式」永遠有漏洞，見方向題四。
9. **C-42「每樣東西都是工具、自我迴圈改進的閉環」、C-61 vs「全專屬工具」這個終點。**`self_tools add`、`agents new／add` 的 `tools`、`thought` 的 `tools[].path` 都收工作區裡的路徑；agent 用 `write` 在工作區寫一個 `_entry`（JSON argv 不需要 `+x`），再登記成工具，就有了沙箱外的任意執行。後果：照實標成任意執行工具，協調型 agent 就到不了 `none`；不標的話，`none` 是假的。見方向題三。
10. **C-69「aos 只訂六個環境變數」vs fable 原稿新增 `AOS_UNIT`。**改用 measure 的 case 當審視單位（每次跑都有自己的 stack），不加環境變數。
11. **使用者「審」的範圍：冗餘（兩套機制做同一件事）vs fable 原稿的 `repeat_check`、`ladder`、「meta_observe 收三樣」。**它們跟 evolve-design 的 `measure`（重跑＋比對器＋樣本）、審視者的 `downgrade`＋`ladder.json`、`_observed.json` 退役正面重疊。本設計全部併進 evolve-design，只加 `consistency` 一格與三個招式。
12. **N-50（工具的小格是 `$AOS_STACK/tools/<名>/`）vs 沙箱 `rw`。**謹慎期包裝綁的是工具自己的小格（`aos-tools call` 給的 `AOS_STACK`），不是 agent 整個 stack；寫成 agent 的 stack 會讓沙箱裡的 bash 改得到 agent 的 history 與覆蓋層。

## 方向題（使用者出門，全部未裁，暫照推薦）

1. **階段要不要寫成欄位？**
   - (a) 從工具清單推，不寫欄位。只有一個事實來源；但要跑 shell_report 才看得到。
   - (b) 定義裡加 `shell_stage`。一眼看得到；但會跟工具清單不一致，要另做對帳。
   - **推薦 (a)。未裁，暫照推薦。**
2. **shell 的指令紀錄放哪？**
   - (a) bash 自己小格的 `observed.jsonl`，`cmd` 行。跟 measure 同一套翻法、同一個公開介面。
   - (b) 呼叫方用環境變數指一個共用檔（試驗場 `AOS_BASH_LOG` 的做法）。統計只讀一檔；但多一個設定，指到哪都行（C-80）。
   - **推薦 (a)。未裁，暫照推薦。**（fable 原稿推薦的是另開 `calls.jsonl`，跟 evolve-design 對齊後改成這樣。）
3. **`self_tools`／`agents`／`thought` 算不算任意執行工具？**
   - (a) 算。誠實；協調型 agent 永遠是 `open`，只有專精 agent 到得了 `none`。
   - (b) 不算，另給這三支加「只收某幾個根底下的路徑」的限制（例如登記格 `env` 給允許的根）。協調型 agent 也能到 `none`；但多一個機制，三支工具都要改。
   - (c) 不算、也不限制，當已知漏洞。最省事；`none` 名不副實。
   - **推薦 (a)。**使用者說的是「讓 agent 專精特定領域」，終點本來就落在專精 agent 身上。**未裁，暫照推薦。**
4. **謹慎期的 Python 漏洞要不要補？**
   - (a) 不補。謹慎期保證「只寫工作區、不連網」，「只跑哪些程式」盡量；封死靠 `none`。零改程式。
   - (b) 改 bash 工具：在裡面只對使用者那條指令接 `aos-sandbox`，工具自己的 Python 留在外面。白名單變真的；但 bash 要多讀一份沙箱設定，「誰叫誰關」（S5）變成工具替呼叫方關內層。
   - **推薦 (a)。未裁，暫照推薦。**
5. **確定性要不要一個合成分數？**
   - (a) 不要，三樣分開報。看得出哪步不穩。
   - (b) 要一個加權分數。好畫曲線；權重是人訂的，會蓋掉問題在哪。
   - **推薦 (a)。**要畫曲線就畫 LLM 步的自洽分數。**未裁，暫照推薦。**
6. **轉階段的門檻用連續幾個 case？**
   - (a) 2。跟 09「連過兩個地點就降一級」一致；錯了 watch 會退回。
   - (b) 3。跟 watch 的窗一樣大，比較穩；地點少時要等很久才動。
   - **推薦 (a)。未裁，暫照推薦。**

（fable 原稿的「階梯選出的等級誰套用」一題，使用者已在 evolve-design 裁成自動換、退步自動退回，不再問。）

## 代定（使用者出門時替他做的小決定，可翻案）

1. `repeat_check`、`ladder` 不做，併進 evolve-design 的 `measure`／審視者；measure.json 多一格 `consistency`（格式交 evolve-design）。
2. 審視單位＝measure 的 case，不加 `AOS_UNIT`。
3. 機器只收緊：審視者換上前推一次階段，比換前鬆就不准換；放寬只能人做，或 watch 退回時恢復前版。
4. `box`、`unshell` 是改設定、不寫程式，比照「換模型」第一天就全自動；`extract` 要寫程式，比照 `fix` 前三個地點只開處方。
5. `promote` 不呼叫 git；階段歷史看定義根的 git log（試驗場每地點 commit 照舊）加 `reviews/watch.json`。
6. 確定性只叫「自洽」（樣本彼此比）；跟參考答案比叫「一致」、是門。兩個都記。
7. 量多勤：腳本步每地點、LLM 步自洽只在降級試驗、整體每輪一次。
8. bash 在 `AOS_STACK` 沒設時不記帳、照跑；寫帳失敗才 `LogFailed`。
9. shell_report 的切法用 `shlex` 的 `punctuation_chars`，第一個字用 `shutil.which` 解，解不到的不進白名單。
10. `py`／`lua`／`aos` 公式在固定的公式沙箱裡算（斷網、無寫入、5 秒 CPU、256 MB）；`cal` 不用沙箱。
11. `--limits` 跟階段無關；不足 #11（`--limits` 掛的 agent 不能 `ctl stop`）不在本題。

## 落地順序（交 gpt 照圖施工）

依賴 evolve-design 的落地步 3（`lib/observed.py`）、7～8（measure 與門）、11（promote）、12（審視者）、13（watch）。本題的步驟插在它們之後；1、2、3 互不依賴。

1. **bash／run_python 記 `cmd` 行**：用 `lib/observed.py` 在 `$AOS_STACK/observed.jsonl` 追加上面格式；寫失敗退 `LogFailed`、不跑；`AOS_STACK` 沒設不記；`_tooldef.json` 的 `errors` 加 `LogFailed`。完成條件：經 `aos-tools call bash` 叫三次（含一次 `exit 1`），小格的 `observed.jsonl` 剛好三行 `cmd`、`exit` 等於內層結束碼。
2. **宣告 `arbitrary_exec`**：`bash`、`run_python`、`self_tools`、`agents`、`thought` 的 `_metainfo.json` 加 `"arbitrary_exec": true`。完成條件：`aos-tools ls --json` 在 agent-fsm 範本裡看得到 `self_tools`、`agents` 這兩支帶 `true`。
3. **試驗場 worker daemon 的 stack 搬出 `ws/`**：改 `defs/root_daemon/daemon.json`、`env.sh` 的 `AOS_KERNEL`、`defs/worker_daemon/_entry`。完成條件：`ls ~/code/playground-ak/ws` 沒有 `.stack`，婆山鎮 `place_run --check` 照舊通過。
4. **謹慎期包裝範本**：把 `cmd/aos-sandbox/examples/bash-boxed/` 改成上面「謹慎期的包裝」那節的樣子（刪 `sandbox.json`），README 那列跟著改。完成條件：叫它 `rg` 成功、`curl` 得 `command not found`、寫 `/tmp/x` 後主機上沒有這個檔、寫 `$AOS_WS/x` 成功、`echo /usr/bin/*` 只列出白名單幾支。
5. **`lib/agent/shell_report`**：照「shell_report」那節做，翻帳用 `lib/observed.py` 的翻法。完成條件：三份假 `tools.json`（lib bash／包裝 bash／沒 bash 也沒 self_tools 等）分別回 `open`／`boxed`／`none`；只有 `thought` 的那份回 `open` 且 `arbitrary` 是 `["thought"]`；`cd x && rg -n a b | wc -l` 歸成三個形狀。
6. **measure 加 `consistency`**：同一支比對器，`samples[1..]` 各比 `samples[0]`。完成條件：一支輸出帶時間戳的假腳本，`consistency.scores` 小於 1；拿掉時間戳後全是 1.0。
7. **關箱考題 `cases/box-probe/` 與比對器**：照「關箱考題」那節。完成條件：拿第 4 步的包裝跑門過；拿沒包的 lib bash 跑門不過。
8. **單步 case**：試驗場建 `cases/kb_store-poshan/`（上游產出錄好放 `ws/`）與 `cases/linker-poshan/`（固定候選）。完成條件：前者 `repeat: 3` 的 `consistency` 全 1.0；後者在 terra 上有三個分數。
9. **審視者加三招**：`system.txt` 加 `extract`／`box`／`unshell` 的時機與做法、換前推階段只准收緊；`box`／`unshell` 全自動、`extract` 前三地點只開處方。完成條件：對一隻兩個 case 都只用 `rg` 的假 agent 跑一輪，`review.json` 的 `adopted` 是 `box`、副本的 `tools/bash/_metainfo.json` 白名單含 `/usr/bin/rg`、換上後 `box-probe` 門過；故意讓副本變鬆時審視者拒換。
10. **試驗場退場**：`bash_logged`、`exp_run_ladder.py`、`linker-ladder.json` 從試驗場移除（審視者上線之後）。完成條件：`defs/INDEX.md` 沒有這三樣，地點 3 照常跑完。

條文（不交 gpt，由 opus 寫）：四條概念入 CONCEPTS（接 C-21／C-22 與 C-42）；`arbitrary_exec` 與 `cmd` 行併進 evolve-design 的 metainfo／observed 條文；待定之二「Linux 權限與沙箱」補一句「謹慎期包裝＝`_metainfo.json#/sandbox`，`base` 要縮小才有指令白名單」。

## 同批其他題

- 自我改進機制本身、metainfo／observed 的總格式、measure／promote／watch：交給 [evolve-design](../evolve-design/README.md)。
- 本機模型一次只能 load 一個、降級到本機級的排程與跨層記帳：交給 [kernel-nest](../kernel-nest/)。
- 知識庫全庫規模與給人看的那層：交給 [kb-scale](../kb-scale/)。

## opus 註（核對 fable 原稿改了什麼）

- **條文引用**：C-13／C-14／C-21／C-22b／C-52 11-06 讀法／P-15／S4／S6／「實測不回寫」引用都對。原稿說 `aos-sandbox` 設定檔「若尚未實作要補 `檔#/指標`」，其實早就支援（`bin/aos-sandbox` 第 5、49、81 行），那步刪掉。
- **沙箱範例跑不起來**：原稿 `commands` 沒有 `aos-exec`、`ro` 沒有 `tool_io.py`、`rw` 沒有小格（bash 要寫帳），而且照 `commands`／`base` 的實作，白名單擋不住；已改寫並把卡點逐條列出。
- **漏掉的提權路徑**：`self_tools`／`agents`／`thought` 都收工作區路徑，原稿的「`none`＝沒有 bash」是假的（衝突 9、方向題三）。
- **跟 evolve-design 重疊**：原稿的 `repeat_check`、`ladder`、`meta_observe` 收三樣，跟已裁的 measure／審視者／`_observed.json` 退役重複，已併掉（衝突 11）。
- **自洽與一致混用**：原稿把「跟 sol 比 94%」叫確定性，第 5 步完成條件寫「`by_item` 對 linker 回 15/16」——15/16 是隊長的語意抽查，不是比對分數。已分開並改完成條件。
- **腳本步確定性要錄放**：整體重跑會重問 LLM，下游腳本的輸入跟著變，原稿的 `tree` 比法量不出腳本步本身；改成單步 case、上游錄好。
