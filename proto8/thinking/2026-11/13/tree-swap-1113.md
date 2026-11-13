# 家機活樹停樹換檔（線換，11-13 晚）：腳本 `proto8/extras/tree-swap/`、暫存樹預演六輪（釘最終 commit `54789088d` 的第六輪全綠）、會換／不會動的清單、換後收尾清單、給使用者的單子

← [11-13 日索引](README.md)｜規格：[aos-teams/06「停樹換檔的做法」](../../../../wf/workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md#停樹換檔的做法)｜腳本：[tree-swap](../../../extras/tree-swap/README.md)｜要換進去的內容：[ref-path-rules](ref-path-rules.md)、[sandbox-sender-fix](sandbox-sender-fix.md)、[wake-timer](wake-timer.md)、[user-zone-plan](user-zone-plan.md)、[gpt-fsm-team](gpt-fsm-team.md)

## 使用者原話（11-13 晚，頂層轉）

> 「目標是今晚就換，但不是一定要，反正就有空的話就可以來換。」

線換只寫腳本、在暫存樹預演、交單子；**沒停活樹、沒換活樹任何檔**，停樹與執行由使用者自己下。

## 結論

- 腳本：`proto8/extras/tree-swap/`（`swap.sh`、`rollback.sh`、`build.sh`、`common.sh`）。不含 kill／shutdown；每段動手前看這棵樹還有沒有行程活著，有就 `RED:` 退 3、什麼都不改。
- C++ 十支：最終 commit `54789088d` 的 `proto8/impls` 跟最早 build 的 `0e62d640e` 不同（只改了 12 個 md 的 code map 連結，程式碼沒變；但 `check` 是整夾比對），所以用 `build.sh --ref 54789088d` 在 repo 外 `~/code/swap-1113/src2` 重編，十支共約 106 秒。換的時候用 `TS_BUILD=~/code/swap-1113/src2`（單子已寫）。
- 頂層轉來另一條線的 `copy_tree.py`（`41f06e9a4`）：選「自己抄、抄完補跑 `--stamp-only`」——備份、退回、紅燈這套已經寫好預演過；`stamp` 段用**釘住 commit 裡的** `copy_tree.py`（解到暫存夾跑，不用工作樹那份），換完每夾都有 `.aos-source.json`（`how: stamp-only`）。`check`／`verify` 比對時略過這個檔，`verify` 另核章裡的 commit。

## 會被換的（盤點：活樹複本 vs 最終 commit `54789088d`，`diff -rq` 唯讀比、略過 `__pycache__`；共 85 檔＋十支）

| 夾 | 不同 | commit 有、樹裡沒有 | 只在樹裡有 |
|---|---|---|---|
| `lib` | 20 | 11（`aos_refpath.py`、`tests/ref_path_cases.json`、`tests/test_ref_path.py`、`base/peek_now_time/tests/`、專區段 2 的 `agent/user_send/`、`agent/user_zone_guard/` 等） | 0 |
| `templates` | 1（`tests/test_daily.py`，別線 22 點後改的） | 0 | 0 |
| `knowledge` | 18 | 32（`aos/user_zone.json`、`wf/` 底下 skeletons、source、workflows 十幾個 json 等） | 0 |
| `py` | 1（`aos_clock_register.py`） | 2（`aos_clock_when.py`、`tests/test_clock_when.py`） | 0 |
| C++ 十支 | `aos-daemon directive exec fsm json llm llm-kernel lock loop post` 全換（同一 commit 編出，一致） | | |

- 一開始對 `0e62d640e` 盤點時那 37 個「不同」的檔，樹裡的內容逐一拿去 `git hash-object` 都在 git 歷史裡找得到——全是舊複本，沒有人在樹裡改過。
- 樹裡沒有 `kernel/`（家機搭樹時代定不抄），腳本只換樹裡已經有的夾，不會多建。
- `~/.local/bin/aos-*` 的 C++ 那十支指到 repo 的 `proto8/impls/<p>/bin/<p>`（gitignore 著），所以換執行檔＝換那十個檔，`git status` 不受影響。`cmd/`、`py` 的 Python 指令本來就從 repo 跑，不在這次範圍。

## 不會被動的

`~/aos-home` 底下：`agents/`（`eca_main`、`repo-aos`）、`defs/`（`shared`、`gpt-lead`、`gpt-worker`）、`teams/t1`、`kernels/llm-gpt`、`ws/`（`public`、`tools`、`.stack` 與各 agent 的 procs）、`.stack/`、`root/`、`daemon/`、`env.sh`；樹外：`~/.aos/user`（使用者專區；備份另寫在 `~/.aos/saves/tree-swap`）、`~/.local/bin` 的連結、repo 工作樹（除了那十個 gitignore 的執行檔）。`check` 段另有一道：四夾裡若有「只在樹裡有」的檔（換了會丟），紅燈不換。

## 預演（暫存樹 `~/code/swap-1113/tree`）

樹的形狀：四夾從活樹唯讀抄（＝現在活樹的舊複本）、根 daemon 與領班照[十七步](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做) ④⑤ 做、`kernels/llm-gpt` 唯讀抄、假的 `defs`／`teams`／`agents`；`TS_BIN_ROOT` 指暫存夾的假 `binroot`（十支現在活樹在用的舊執行檔），起樹時 PATH 先找它。全程經「不是 bash 就拒絕、清掉全部 `AOS_*`、還有殘留就拒絕」的殼跑，tmux 只用暫存夾內的 socket，停樹只用 `aos-daemon-ctl -d ~/code/swap-1113/tree/.stack shutdown`。

| 輪 | ref | 結果 |
|---|---|---|
| 1 | `0e62d640e`（還沒有 stamp 段） | 12 段全綠 |
| 2 | `2b91e9b22`（加了 stamp 段） | **stamp 段紅**：`copy_tree.py` 經 `py/aos_flags` 要 import `lib/tool_io`，我只解了 extras 和 py。順帶驗到「換到一半紅燈→退回」照樣逐位元還原。修：連 `proto8/lib` 一起解 |
| 3 | `85bef94a0` | 12 段全綠 |
| 4 | `9736e54a0`（本線 commit） | 只有預演腳本自己的 7c 紅：拿短 hash 去 grep 章，章裡是完整 hash（swap.sh 的 verify 用完整 hash 核過、是綠的）；預演腳本改成先轉完整 hash |
| 5 | `9736e54a0` | 12 段全綠 |
| 6 | `54789088d`（頂層傳的最終 commit；C++ 用 `src2` 新編的） | 12 段全綠（下表；時間跟第五輪差不到 0.3 秒）。另跑一段：HOME 指暫存夾的假家目錄、不設 `TS_BACKUP_ROOT`，`swap.sh all`＋`rollback.sh` 都綠，備份自己建出 `<假家>/.aos/saves/tree-swap/<時間>/` 與 `LAST`（＝預設位置的建夾邏輯對；真的 `~/.aos/saves` 沒建）；暫存樹換完 `lib/agent/` 有 `user_send`、`user_zone_guard` |

| 段 | 結果 | 時間 |
|---|---|---|
| 1 起樹（舊執行檔）；舊 `aos-json get --follow …#/g/dot/k`（`#./here`）＝`PointerMissing` | 過 | 0.17 s |
| 2 樹在跑時 `swap.sh check`：列出 5 個行程、`RED`、退 3 | 過 | 0.31 s |
| 3 樹在跑時 `swap.sh copy`：`RED`、四夾與十支一個位元都沒變 | 過 | 0.33 s |
| 4 從帶 `AOS_STACK` 的殼下（＝從 agent 裡下）：`RED` | 過 | 0.00 s |
| 5 停樹 | 過 | 0.46 s |
| 6 `swap.sh all`（check、backup、copy、stamp、bin、verify） | 過 | 1.44 s |
| 7 樹裡四夾以外（含使用者資料）雜湊不變；四夾確實換了；四夾 `.aos-source.json` 都是該 commit、`how: stamp-only` | 過 | — |
| 8 `rollback.sh all`：四夾內容＋權限位元、十支，跟換之前逐位元相同 | 過 | 0.26 s |
| 9 再換一次 | 過 | 1.38 s |
| 10 起樹（新執行檔）：根三列、領班 `_sweeper` running | 過 | 0.14 s |
| 11 smoke：`aos-json get`；`$ref` `#./`、`#../` 新規則照新表走到；`aos-directive --help` 有 `--at`；`index_view` 看 `knowledge/aos` 21 項、有 `user_zone`；領班 running | 過 | 0.05 s |
| 12 停樹，樹的行程一個不剩 | 過 | 0.35 s |

另跑一次收尾清單第 1 條的指令（暫存樹起著，`cd tree/ws && aos-daemon-ctl -d .stack add --name llm-gpt --auto-restart ../kernels/llm-gpt`）：0.23 秒、`llm-gpt running`，停樹後收乾淨。備份每份約 42 MB（四夾＋十支）。

## 在活樹上會碰到、暫存樹沒有的

- 活樹除了 daemon 還有 `aos-agent open` 兩個畫面（python3，cwd `~/aos-home/ws`）與它們的 tmux client、**`aos-user serve`（專區網頁，python3，cwd `~/aos-home/ws`）**。前兩者在 agent 停掉後會跟著結束；`aos-user serve` 不屬於任何 daemon，停樹後還活著，`swap.sh` 會因它紅燈（這是對的：它跑在樹裡）。單子寫了要先關它、換完再開。
- 使用者自己在 `~/aos-home` 底下開著的 `claude`（例：十七步 ⑧ 按信任那次）也會讓它紅燈；`check` 會列出 pid 與指令，看了自己關。

## 換後收尾清單

1. **`llm-gpt` 掛回去**（gpt-fsm-team 代定它是永久的 kernel；上一輪收尾時從表上 rm 了）：
   `cd ~/aos-home/ws && aos-daemon-ctl -d .stack add --name llm-gpt --auto-restart ../kernels/llm-gpt`（暫存樹實跑過；`--auto-restart` 要不要，使用者定）。
2. **`~/aos-home/kernels/llm-gpt/kernel.json` 的 `budget.senders`**：換了 aos-llm 之後寄件人＝各 agent 的 stack（[sandbox-sender-fix](sandbox-sender-fix.md)），現在那格 `"../../../../teams/t1"` 永遠對不上。要改成用這個 kernel 的各 agent 的 stack 絕對路徑，例如 `/home/lorkhan/aos-home/ws/.stack/procs/gpt-lead`（sol 們同理，名字以當時掛的為準）；每格上限多少使用者定。`used.json` 舊 key 換窗後自然消失。
3. **5 處 Python 接 `aos-directive --at`**（新執行檔換上後才可以接；這裡只列，不改）：`lib/directive_value.py`、`cmd/aos-agent/aos_agent/tools.py`、`py/aos_clock_register.py`、`lib/mcp_server_file.py`、`lib/hook_run.py`。接完 `lib`、`py` 要再換一次樹才生效（`cmd/` 存檔即生效）。
4. （可選）`proto8/install.sh` 跑一次，把新指令 `aos-tree-start` 連上 PATH，之後起樹改用它（擋殼裡繼承的外來 `AOS_*`）。
5. 換完 repo 的 `impls/*/build` 比 `bin/` 舊；之後在 repo 重 build 會從已 commit 的原始碼編出等價的檔。
6. 備份留在 `~/.aos/saves/tree-swap/<時間>/`（約 42 MB），確定沒事再自己刪。
7. 專區段 2（[08-段2施工](user-zone-plan/08-段2施工.md)「換樹後要做的」）：第 4、5 步（重抄 `user_zone.json`、`user_send`、`user_zone_guard`）已含在這次換樹；建議做：裝計時器 `aos-user-tick.timer`、`door.json` 換新（`init`，出門模式會回 normal）；可選：`notify on`、agent 自己加 `user_send`／守門 hook。指令寫在桌面手冊。

## 給使用者的單子

```sh
# 0. 先叫頂層 repo-aos 收工交棒——停樹會把它（和它的畫面）一起停掉。

# 1. 開一個一般終端機（不是樹裡 agent 的殼），停樹：
aos-daemon-ctl -d ~/aos-home/.stack shutdown
#    起樹那個視窗的 aos-exec root 會自己結束。專區網頁 aos-user serve 若開著，到它的視窗 Ctrl-C。

# 2. 換（約 2 秒）。REF 用下面這個 commit；要用更新的也可以，check 會核 C++ 對不對得上：
TS_BUILD=$HOME/code/swap-1113/src2 bash ~/repo/aos/proto8/extras/tree-swap/swap.sh --ref 54789088d all
#    看到 "verify: green" 就好。出現 RED: 先看它說什麼——樹還有行程活著就照它列的 pid 關掉再跑一次；
#    換到一半紅燈就跑第 5 步退回。

# 3. 起樹（原本起樹的視窗，前景跑）：
cd ~/aos-home && source env.sh && aos-exec root
#    （可選：先跑一次 ~/repo/aos/proto8/install.sh，改打 aos-tree-start root）

# 4. 另一個視窗確認：
aos-daemon-ctl -d ~/aos-home/.stack ls        # _clock、_sweeper、foreman running
aos-daemon-ctl -d ~/aos-home/ws/.stack ls     # _sweeper、eca_main、repo-aos running
#    再把 aos-user serve 開回來、照收尾清單做。

# 5. 出事退回：先停樹（第 1 步），再
bash ~/repo/aos/proto8/extras/tree-swap/rollback.sh
#    然後照第 3 步起樹。
```


## 釘住的 commit

**`54789088d`**（頂層 22:4x 傳的最終 commit，專區段 2 已收線；之後只會有 `proto8/cmd` 的新檢視指令與 wf 記帳，不影響換的四夾）。C++ 十支在 `~/code/swap-1113/src2`（`BUILD_REF`＝`54789088d`）。早先的 `9736e54a0`／`src`（`0e62d640e` 編的）作廢：`check` 會因 `proto8/impls` 不同而紅燈。
