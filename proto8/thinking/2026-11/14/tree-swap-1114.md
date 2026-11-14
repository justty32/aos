# 11-14 晚換樹：各線清單整合成一張步驟表＋暫存樹整套預演（ok-kf 整理；換不換、何時換由使用者定）

← [11-14 日索引](README.md)｜規格：[aos-teams/06「停樹換檔的做法」](../../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜腳本：[tree-swap](../../../extras/tree-swap/README.md)、本次另加的 [extras.sh](tree-swap-1114/extras.sh)、[extras-rollback.sh](tree-swap-1114/extras-rollback.sh)｜上一次：[tree-swap-1113](../13/tree-swap-1113.md)

## 結論

- **釘住的 commit：`246d4aa49`**。這個 commit 含線星 ADV `313ce20ec`，是在 repo 外的乾淨複本跑過 proto8 全部 tests 夾的（結果在[預演](#預演暫存樹-codets-1114)一節）。C++ 在 repo 外 `~/code/ts-1114/src2` 編好（`BUILD_REF`＝`246d4aa49`，九支共 2 分 4 秒）。
  - 原本釘的是 `b8ff23ada`，之後 ADV 進來才往後移。這段期間 `proto8/impls` 只改了一份 README，但 check 是整夾比對，所以照樣重編。
  - 舊的 `src`（`d38a0d36f`）作廢，拿它 check 會 RED。
- **換的東西**：
  - `swap.sh` 整夾換掉活樹的 `lib templates knowledge py`，並換 C++ 九支。
  - `extras.sh` 處理 swap.sh 不管的幾件：
    - 五個 eca 定義的 `hooks.json` 補上 screen_linger 兩格；
    - 三個定義的 `.env`；
    - `defs/shared/guard` 換成新版（線星 ADV）：換完對 gpt-lead、gpt-worker 驗退出碼，不對就 RED；
    - gpt 兩個定義的 brain_notify（要等使用者裁）；
    - 兩條連結（建議今晚先不動，見 D1）。
  - 各線清單上的每一項都對到了表裡某一步，見[各線清單怎麼對到](#各線清單怎麼對到步驟)。
- **不刪任何東西**：照使用者「不刪」的規則，tree-swap 三支已經拿掉所有 `rm`（`b8ff23ada`）。暫存的夾和換下來的夾都留在 `~/.aos/saves/tree-swap/`，每次結束都印出 `kept …` 清單。換一次大約留下 65 MB，由使用者收工時決定刪不刪。兩條連結和 aos-llm-kernel 的未進版控檔也一樣，都是「搬進備份夾」，不是刪掉。
- **預演**：暫存樹 `~/code/ts-1114/r1`、`r2` 是從活樹唯讀抄來的，抄了四夾、`agents/` 五個 eca 定義、`defs/gpt-*`、根與領班設定。15 段整套全綠。
  - 換：`swap all` 約 3 秒，`extras` 約 1.6 秒。
  - 退回：`extras-rollback`＋`rollback all` 約 1 秒。退回後程式、權限位、agents/defs、使用者資料都逐位元相同。
- **預演查到的一件事（D1）**：定義夾的 `.env` 寫 `PATH=…` **不會生效**，除非那一列是用 `aos-agent ctl add --dotenv-override` 加的。aos-exec 預設不蓋已經設好的 PATH。預演實測：沒有旗標時 PATH 沒變，加了旗標才有 `~/repo/aos/wf/tools` 在最前面。活樹現在各隻 kernel 都是沒帶旗標加的。所以今晚只寫 `.env` 的話，各 agent 照樣是靠 `~/.local/bin/commit-request` 這條連結找到 commit-request。**先移走連結，各 kernel 就交不了 commit。**

## 要使用者定的

> 換樹前會**再釘一次** pin，把最後進來的項目帶進去（ok-onboard `3ed649b09`、ok-limits `50e7a35bc`、ok-kb 的知識庫批次、之後的 ok-pilot C／D、ok-misc 的 aos-user 等，照收到的先後排）。重釘以後照這頁再跑一次：全套、重編（impls 有變的話）、新暫存樹預演。各段時間預計跟 r4 差不多。


| 題 | 內容 | 推薦 |
|---|---|---|
| D0 | 什麼時候換 | 使用者定。整段停樹約 10～20 分鐘，大部分花在停、關畫面、起樹、重開畫面；換檔本身不到 10 秒 |
| D1 | `~/.local/bin/commit-request` 連結今晚移不移走 | **先不移**。今晚寫 `.env`；等用這三個定義的列改成帶 `--dotenv-override` 重加（線雜換樹後做的 set-def／re-add 那批），在 agent 裡 `which commit-request` 確定找到 `wf/tools` 那支，再跑 `extras.sh links`。另一案：今晚就移，那麼重加之前各 kernel 都交不了 commit |
| D2 | `defs/gpt-lead`、`defs/gpt-worker` 要不要補 `brain_notify` hook（線星 AK17 留的題） | **補**。不補的話，額度被拒時一樣不會停，只是不寄信給 mom。補了，額度被拒時 gpt 隊長會收到 BLOCKED 信。用 `extras.sh brainnotify`，預演過，退回也驗過 |
| D3 | `impls/aos-llm-kernel` 今晚刪不刪（使用者已准刪） | ok-sec 的 Q10「一信一檔」提到要改 aos-llm-kernel 的 C++。**刪之前先問 ok-sec 一句**：它要的話就留到 Q10 再說；不要就照准的刪。刪的做法：已進版控的檔走 `commit-request --rm`；未進版控的 `bin/`、`build/` 搬進 `~/.aos/saves/tree-swap/`，不刪 |

- D0～D3 已寫成一封 decide 信寄進使用者專區（11-14 13:3x，信名 `01794634349835432556.3092424.2293548`，q1～q4），會出現在全景頁；「aos-comm 上 PATH」（可選）另寄一封。

## 步驟表

`PIN=246d4aa49`。下指令的人是**使用者**，在一般終端機下，不要在樹裡 agent 的殼，也不要在 cwd 落在 `~/aos-home` 底下的殼。停樹會把所有 agent 一起停掉，ok-kf 也會停，所以這張表要自己看得懂。時間是暫存樹量的；活樹 agent 多，停和起會久一些。

| # | 做什麼 | 指令 | 暫存樹時間 | 看什麼算過 | 不過怎麼辦 |
|---|---|---|---|---|---|
| 0 | 換前檢查（換的當下再看一次） | `grep -rl aos-llm-kernel ~/aos-home --include=daemon.json --include=_entry --include=loop.json`、`pgrep -af aos-llm-kernel` | — | 第一條只找到 `lib/base/llm_http/_entry` 的註解（11-14 ok-kf 看過），第二條沒有輸出 | 有定義在 exec 它的話，第 10 步刪 aos-llm-kernel 那項不做 |
| 1 | 叫頂層與各線收工交棒，記下有哪些畫面開著 | `ls /run/user/1000/aos-tty-1000/` | — | 各線回覆收工 | — |
| 2 | 停樹 | `aos-daemon-ctl -d ~/aos-home/.stack shutdown` | 0.7 s | 起樹那個視窗的 `aos-exec root` 自己結束 | — |
| 3 | 關畫面，關樹裡其他行程 | 每個 sock 各下一次 `tmux -S /run/user/1000/aos-tty-1000/<sock> kill-server`。`aos-user serve`、全景頁若跑在樹裡，到它們的視窗按 Ctrl-C。cwd 在 `~/aos-home` 的殼要 `cd ~` | — | — | — |
| 4 | **先 check**，看到兩個 green 為止 | `bash ~/repo/aos/proto8/extras/tree-swap/swap.sh --ref $PIN check` 和 `bash ~/repo/aos/proto8/thinking/2026-11/14/tree-swap-1114/extras.sh --ref $PIN check`，都要加 `TS_BUILD=$HOME/code/ts-1114/src2` | 0.7 s | `check: green`（兩支都要） | 出現 `RED: … still running` 就照它列的 pid 關掉再 check。其他 RED 停下，看訊息 |
| 5 | 換四夾＋C++ 九支 | `TS_BUILD=$HOME/code/ts-1114/src2 bash …/swap.sh --ref $PIN all` | 2.8 s | `verify: green (folders and 10 bins)`，最後會印 `kept …` 清單 | 跑到一半紅燈就跑第 R 步 |
| 6 | 換 agents／defs 的幾件 | `bash …/extras.sh --ref $PIN hooks env guard verify`（D2 選補的話，在 `verify` 前面加 `brainnotify`） | 2.4 s | 印出 `guard probe gpt-lead: 0 0 0 0 10 (ok)`、`guard probe gpt-worker: 0 0 10 0 10 (ok)` 和 `verify: green`。記下它印的 `run=…` 夾（退回時要用） | 第 R 步 |
| 7 | 起樹 | 原本起樹的視窗前景跑：`cd ~/aos-home && source env.sh && aos-exec root` | 0.15 s | `aos-daemon-ctl -d ~/aos-home/.stack ls`：`_clock`、`_sweeper`、`foreman` running。`aos-daemon-ctl -d ~/aos-home/ws/.stack ls`：各 agent 與 `llm-gpt` running | 停樹（第 2、3 步）後跑第 R 步 |
| 8 | 重開畫面 | `aos-agent open -t repo-aos`，其他照第 1 步記下的開回來 | — | 畫面出得來 | — |
| 9 | smoke | `ls ~/aos-home/lib/agent/screen_linger ~/aos-home/lib/agent/brain_notify ~/aos-home/lib/agent/mailbox_read`；`cat ~/aos-home/lib/.aos-source.json` | 0.1 s | 三夾都在；章裡 `commit` 是 `$PIN` | — |
| 10 | 換後各線接著做（樹起來以後，各線自己做，不用停樹） | 見[換後清單](#換後清單各線自己做) | — | — | — |
| R | **退回**（要先停樹，做第 2、3 步） | `bash …/extras-rollback.sh <第 6 步的 run 夾>`，再 `bash ~/repo/aos/proto8/extras/tree-swap/rollback.sh all`，然後照第 7 步起樹 | 1.0 s | `extras rollback: done`、`rollback tree: … identical to backup`、`rollback bin: … identical` | 不要再換，叫 ok-kf 來看 |

- **太晚就退回**：停樹後 30 分鐘內第 4～7 步還沒全綠，就走第 R 步，先用舊樹起來，改天再換。
- **換完會留下**（都在 `~/.aos/saves/tree-swap/`，沒有刪）：
  - `<時間>/`：備份，約 38 MB，四夾加九支執行檔。
  - `run-…-swap/`：約 21 MB。裡面有 `old/`（換下來的舊四夾，5.3 MB），以及 check、stamp、verify 三份暫存（共約 15 MB）。
  - 第 4 步單跑 check 時另留一個 `run-…-swap/`，約 5.6 MB。
  - `run-…-extras/`：約 0.1 MB，裡面有 `MANIFEST` 和換下來的 hooks.json 等。
  - 合計約 65 MB，硬碟還有 435 GB。
- **別線的暫存樹**：C++ 是寫到旁邊再改名換上的，正在跑的行程不受影響。暫存樹下一次經 `~/.local/bin` 起程式時，就會用到新版。

## 各線清單怎麼對到步驟

| 來源 | 項目 | 在哪一步 |
|---|---|---|
| [misc-1114 換樹清單](misc-1114.md#換樹清單今晚換樹要帶ok-misc-11-14) | 重編 `aos-daemon`（`80f0c3b1f`）、`aos-exec`、`aos-loop`（T17） | 5（九支一起，同一個 commit 編出） |
| 同上 | 重編 `aos-llm-kernel`（`c966fe52f`、T17） | **不編**：使用者准刪這支（D3）。活樹的 llm-gpt 跑的是 Python 版 `lib/aos/kernel_llm`，沒有定義在 exec 它 |
| 同上 | lib／templates／knowledge／py 的檔案清單（mail_notify、kernel_llm 三檔、runner、subagent、fork、self_hook、agents_cmd、cli_*、mcp_tool、T12～T16 新舊檔、daemon_ctl…） | 5（整夾換，清單上的檔都包含在內；check 會核對「只在樹裡有」的檔是零） |
| 同上 | 順序「先換 daemon、再抄 lib」 | 5 是在停樹時一次換完，之後才起樹，所以起來時 daemon 和 lib 都已經是新版，順序要求自然滿足 |
| 同上 | `cmd/aos-tools`、`cmd/aos-mailbox` | 不用換：repo 存檔就生效。活樹沒有抄本（`~/.local/bin` 指 repo） |
| 線雜 `ace14088d`（ok-misc 11-14 來信） | lib `agent/mailbox_read/`、`agent/user_verify/`；knowledge `mailbox.json`、`user_zone.json`；lib/docs 03 | 5（整夾）；9 會看 `mailbox_read` 在不在 |
| [astra-kernel-1114](astra-kernel-1114.md) AK14 | `agents_cmd.py`、`agents_ctl` | 5 |
| 同上 AK17 | `templates/agent-fsm/{wait.py,hooks.json,README.md}`、`lib/agent/brain_notify/`（新）、`lib/agent/subagent/{_entry,_tooldef.json}`、knowledge `brain.json`、`me/self_hook.json` | 5；舊定義複本補 brain_notify＝6 的 `brainnotify`（D2） |
| 線星 ADV `313ce20ec`（ok-astra 11-14 來信） | lib `aos/kernel/{hooks,letters,procs_rules}.py`、`aos/kernel_llm/{budget,llm_rules}.py`、`agent/cooldown.py`、`agent/brain_notify/`；templates `agent-fsm/{wait.py,README.md}`；knowledge `brain.json` | 5（整夾）。kernel 那幾檔要 llm-gpt 重起才生效，第 7 步起樹時就會重起。agent 和 kernel 先換哪個都相容 |
| 同上 | `defs/shared/guard` 換成 `wf/public/tools/fsm-guard/guard`（唯讀查詢放行） | 6 的 `guard`：寫到旁邊再改名，舊檔搬進備份。換完照 ok-astra 的五條驗：worker 要 `0 0 10 0 10`；lead 要 `0 0 0 0 10`，因為 lead 的 guard.json 本來就沒有 rm 那條，第三條新舊 guard 都放行。guard 每次叫工具都重新執行，不必重起 agent |
| [kernel-limits-1114](kernel-limits-1114.md) B1 | `lib/aos/kernel/limits_rule.py`（新）、`procs_rules.py` | 5 |
| 同上 B4／B5 | 從 repo 原始碼重建 aos-daemon；重抄 knowledge `aos/cli/daemon.json` | 5。已經在跑的列被接回（adopt）時不重新檢查天花板，要等那一列下次重起才套用 |
| [gate-auto-1114](gate-auto-1114.md) | `lib/agent/kernel_gate/triage` | 5。換完以後，gate 的 handler 要不要改指 `$AOS_HOME/lib/…`，由頂層決定（換後清單） |
| 線框 [kernel-framework-1114](kernel-framework-1114.md) C′ A 包（`f23cae72b`） | `lib/agent/cli_linger.py`、`screen_linger/`、範本 hooks.json 兩格 | 5（lib、templates）＋6 的 `hooks`（活樹五個 eca 定義：`eca_main fable-kernel opus-kernel repo-aos xiaosi`。這五份現在跟 `c44dac27c` 那版範本逐位元相同，所以整份換成 PIN 的範本。有人手改過的話會 RED、不動）。stack 層的 `hooks.json`（ok-pilot、ok-skyrim、repo-aos）沒有蓋這兩格 |
| 頂層（使用者准） | `opus-kernel`、`fable-kernel`、`xiaosi` 三個定義加 `.env`：`PATH=${HOME}/repo/aos/wf/tools:${PATH}` | 6 的 `env`；要生效得配 `--dotenv-override`（D1） |
| 頂層（使用者准） | 移掉 `~/.local/bin/commit-request` | `extras.sh links`，建議等 D1 |
| 頂層（使用者准） | 刪 `impls/aos-llm-kernel` 夾與 `~/.local/bin/aos-llm-kernel` 連結 | 夾：換後清單（D3）；連結：`extras.sh links`（搬進備份夾）。這支不在 swap 的九支裡，連結移不移不影響換樹 |
| ok-onboard `3ed649b09`（11-14 來信） | 新增 `templates/kits/`、`templates/tests/kits/`；`templates/agent-fsm/system.txt` 從 3 句改成約 1,257 字元 | 5（整夾）。已經在跑的 agent 不受影響，只有換樹後 `agent_def new` 新建的 agent-fsm 拿到新 system。換完驗：`templates/kits/` 在；`python3 -m unittest discover -s <新樹>/templates/tests/kits` OK。**pin 要重釘到含這個 commit** |
| ok-limits `50e7a35bc`（11-14 來信） | lib `agent/subagent/_tooldef.json`、`agent/agents_ctl/_tooldef.json`；knowledge `agents/subagent.json`（limits 說明，純文字） | 5（整夾）。換完驗：`grep -c '"files": 256' ~/aos-home/lib/agent/subagent/_tooldef.json` 是 1。同 commit 的 `py/daemon_ctl/entry.py` 走 repo，不用換。**pin 要重釘到含這個 commit** |
| ok-kb（11-14 來信，xiaosi 也轉了） | 重抄 `proto8/knowledge`，至少含 `3274da594`（cli、tools 共 35 處），之後還有幾批 | 5（knowledge 整夾）。抄換樹當時的 pin；ok-kb 每交一批都會報，換樹前重釘就會帶到 |
| ok-board `4d207e56c`（11-14 來信，**可選，使用者點頭才做**） | 讓 `proto8/cmd/aos-comm/bin/aos-comm` 上 PATH，`lib/agent/board_*` 五支工具靠它 | 不在 swap／extras 裡，起樹後做。甲（推薦）：照 `install.sh` 現有方式裝 cmd；乙：`~/.local/bin` 加一條連結。不做也不影響別的 |
| ok-limits B7 stop_reason（施工中） | 會動 aos-daemon、aos-loop、hook_fire | **今晚不在 PIN 裡**。進 main 之後要重選 PIN、重編、重新預演 |
| xiaosi 轉 ok-sec | **Q10 一信一檔：今晚不做（佔位）** | 要把所有信箱清空重建，proto8 不遷移，新舊版不能混用。等 ok-sec 給確切步驟。PIN 裡沒有 Q10 的半成品 |

## 換後清單（各線自己做）

1. **線框（ok-kf）**，照 `wf/temp/ok-kf/tree-switch-kf.md`：
   - 在活樹驗 C′ A 包：挑一隻 eca，`ctl sleep`，看到 `screen_close.json` 與 tmux 排程；`ctl wake` 之後單子撤掉。
   - 驗完再交 B 包：先跟 main 三方合併、跑全套對照，問頂層後 commit。
   - 收 sol：`ctl rm` sol-b5、sol-g1、ok-kf-sol-1、ok-kf-sol-2，暫存 daemon `shutdown`。
2. **線雜（ok-misc）**：在新 main 上重套 set-def（T03），在新 daemon 下重驗再 commit，補 `--dotenv-override` 那兩句。這一步做完，各 kernel 列改用 `--dotenv-override` 重加，D1 才走得下去。
3. **D1**：在 agent 裡 `which commit-request` 確認找到 `~/repo/aos/wf/tools/commit-request`，再跑 `bash …/extras.sh --ref $PIN links`（搬進備份夾）。要放回就跑 `extras-rollback.sh <那次 run 夾>`。
4. **D3**：問過 ok-sec 之後，`commit-request submit --rm` 刪 `proto8/impls/aos-llm-kernel` 已進版控的檔。未進版控的 `bin/`、`build/` 搬進 `~/.aos/saves/tree-swap/llm-kernel-<時間>/`。
5. **gate**（頂層）：要不要把 handler 改成 `{"$env": "AOS_HOME", "$path": "/lib/agent/kernel_gate/triage"}`。
6. **線星 AK3 補記**：階段 3 開工前，核對活樹的 `aos-llm` 實際指到哪一支。
7. 備份與 `run-*` 夾留著，使用者收工時決定刪不刪。

## 預演（暫存樹 `~/code/ts-1114`）

- **全套測試**：
  - 釘 commit 前，先在 `d38a0d36f` 的乾淨複本跑 proto8 全部 tests 夾，用的是 repo 外剛編的 C++。`impls/aos-daemon`（112）、`aos-exec`（19）、`aos-loop`（17）這次都綠。上一回 C′ 驗收時這三夾是紅的，原因是 repo 裡的執行檔比原始碼舊；這次改用新編的，就綠了。
  - 紅的只有兩類，main 上本來就紅，跟這次換樹無關：
    - `impls/aos-llm-kernel`：4 項 failures。這次沒重編這支，複本裡是舊執行檔，而這支要刪。
    - `archive/*`：舊檔封存，本來就跑不起來。
  - `b8ff23ada` 的結果：跟 `d38a0d36f` 那次逐夾狀態相同，紅的仍然只有上面兩類。測試數只多不少：`ace14088d` 新加的測試讓 `cmd/aos-mailbox` 從 7 項變 12 項、`mailbox_send` 從 4 變 6、`user_verify` 從 4 變 6。
  - **`246d4aa49`（現行 PIN）的結果**：跟 `b8ff23ada` 逐夾狀態相同，只多了 ADV 和 set-def 共用參數那批新測試：`cmd/aos-agent` 116→119、`lib/aos/kernel_llm` 45→59、`lib/aos/kernel` 106→118。全套約 11 分鐘。另外在同一份複本跑了 `wf/public/tools/fsm-guard/tests`，34 項全綠。全套跑一次約 10 分鐘（`~/code/ts-1114/verify-b8ff23ada-summary.txt`）
- **暫存樹的形狀**（`setup.sh <名>`）：
  - 從活樹唯讀抄：`lib templates knowledge py agents root daemon env.sh`、`defs/{gpt-lead,gpt-worker,shared}`、`kernels/llm-gpt`。
  - 根和領班用活樹自己的設定。
  - 假的 binroot：repo 現在那九支，也就是活樹在用的。
  - 假的連結夾，放 `commit-request` 和 `aos-llm-kernel` 兩條。
  - 全程清掉 `AOS_*`；tmux 只用暫存夾的 socket；停樹只用 `aos-daemon-ctl -d <暫存樹>/.stack shutdown`。
  - 只起了 daemon，沒起任何 agent，也沒起 llm-gpt。

| 段 | 內容 | r1（ref `9360f927e`） | r2（ref `b8ff23ada`） |
|---|---|---|---|
| 1 | 起樹（舊執行檔） | 過 0.15 s | 過 0.15 s |
| 2 | 樹在跑時 `swap.sh check` → RED 退 3 | 過 0.53 s | 過 0.53 s |
| 3 | 樹在跑時 `swap.sh copy` → RED，什麼都沒改 | 過 0.60 s | 過 0.58 s |
| 3b | 樹在跑時 `extras.sh hooks env` → RED，agents/defs 沒改 | 過 0.57 s | 過 0.51 s |
| 4 | 從 agent 的殼（有 `AOS_STACK`）下 → RED | 過 | 過 |
| 5 | 停樹 | 過 0.65 s | 過 0.65 s |
| 6 | check（swap＋extras）green | 過 0.67 s | 過 0.59 s |
| 7 | `swap.sh all` | 過 2.83 s | 過 2.70 s |
| 8 | `extras.sh hooks env brainnotify verify` | 過 1.58 s | 過 1.59 s |
| 9 | 使用者資料沒動、四夾蓋章、五個定義 screen_linger_start 排第一、新 lib 件都在 | 過 | 過 |
| 10 | `extras-rollback`＋`rollback all`：逐位元同（程式、權限位、agents/defs、使用者資料）；`.env` 被搬進備份夾 | 過 1.03 s | 過 1.01 s |
| 11 | 再換一次（swap＋extras） | 過 3.65 s | 過 3.68 s |
| 12 | 起樹（新執行檔） | 過 0.15 s | 過 0.15 s |
| 13 | smoke：`$ref #./`、index_view、ws daemon、screen_linger 對沒畫面的 stack 退 0；`.env` PATH 實驗：沒旗標**不生效**、加 `--dotenv-override` 生效 | 過 0.08 s | 過 0.08 s（同 r1：沒旗標不生效） |
| 14 | `extras.sh links` 搬走兩條連結＋退回放回來 | 過 0.02 s | 過 0.02 s |
| 15 | 停樹 | 過 0.66 s | 過 0.63 s |

- **會換多少**（r4 的 check 量的，等於活樹現況對 `246d4aa49`）：
  - lib：改 75 檔、新 22 項。
  - templates：改 21、新 3。
  - knowledge：改 24。
  - py：改 5、新 1。
  - 每一夾「只在樹裡有」的都是 0。
  - C++：九支裡 5 支不同（`aos-daemon aos-exec aos-fsm aos-llm aos-loop`），其餘 4 支逐位元相同，照樣換。
  - 五個 eca 定義的 hooks.json 都是舊範本原樣，三個 `.env` 都還沒有。
- **r3、r4（ref `246d4aa49`，C++ 用 `src2`，extras 多了 guard 段）**：
  - r3：第 8、11 段紅，紅在 guard 驗法。gpt-lead 的第三條（`cd x && rm y`）退 0，表上寫要 10。
    - 查了：舊 guard 對 lead 也是退 0，lead 的 guard.json 本來就沒有 rm 那條。所以是驗法對 lead 的期望寫錯了，不是 guard 退步。
    - 新舊 guard 實測：lead 舊版 `0 10 0 0 10`、新版 `0 0 0 0 10`；worker 舊版 `10 10 10 0 10`、新版 `0 0 10 0 10`。兩支多放行的，正好是 ADV 要放行的兩條唯讀查詢。
    - 改成每個定義各有自己的期望值。
    - 第 10 段的退回在紅燈後照樣逐位元還原，guard 也還原了。
  - r4：用新的暫存樹重跑，15 段全綠。swap all 3.00 s、extras（含 guard）2.40 s、退回 1.15 s、再換 4.97 s；其他段跟 r1、r2 差不到 0.1 s。
- 一輪預演在暫存樹留下約 129 MB 的 backups，因為換了兩次、退了一次，每次都有備份。這些不刪。
- **暫存樹沒有、活樹才有的**：
  - 二十幾隻 agent 和它們的畫面：停、起都會比較久，第 3 步要逐個 sock 關。
  - cwd 在 `~/aos-home` 的殼：11-14 13:1x 看到兩個 zsh，第 4 步會因此 RED。
  - llm-gpt 正在處理的請求：停樹時中斷，起樹後由各 agent 重問。
  - `ws/.stack/procs/ok-limits-sol-5` 底下另有一台 aos-daemon，屬於 ok-limits 的 sol：它跟著樹停；起樹後要不要再起，由 ok-limits 決定。
  - 這些情況 `check` 都會列出 pid 與指令。

## 檔

| 檔 | 是什麼 |
|---|---|
| [tree-swap-1114/extras.sh](tree-swap-1114/extras.sh) | swap.sh 不管的四件（hooks、env、brainnotify、links）＋check／verify；不含 kill、不刪 |
| [tree-swap-1114/extras-rollback.sh](tree-swap-1114/extras-rollback.sh) | 照 extras 那次的 MANIFEST 倒著退 |
| `~/code/ts-1114/`（repo 外） | `setup.sh`、`rehearse.sh`、`suite.sh`、`log.txt`、`rehearse-r1.log`、`r1/`、`src/`（C++ build）、`verify-*`（全套測試複本與 summary） |
