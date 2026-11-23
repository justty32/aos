11-23 晚在家機用暫存樹預演改表（06e「今晚要備好的」第 3 項）：做了哪些事、每一步的結果、碰到的坑、明早要注意的地方，以及 06f／06e 跟實際對不上的地方（線 `tri-split-1123-table`）。

# 改表預演（11-23 晚，家機）

← [06f 改表的做法與家機](../06f-改表的做法與家機.md)｜[06e 切換步驟](../06e-切換步驟.md)｜腳本：[stack_paths.py](stack_paths.py)

## 結論

- **停著改檔這條路走得通**。暫存樹（一台根 daemon 加一台子 daemon、5 列 agent）停下 → 搬範本夾 → `stack_paths.py --apply` → 起樹：每一列都照舊起來（停之前 running 的都 running，停之前 stopped 的還是 stopped）；表上的 `def` 都是新路徑，agent 的行程真的是從 `templates/agents/…` 跑起來的；沒有產生 `.bad-*` 檔；daemon 起來重寫表之後，「只列不改」數到 0 處。
- **退回也試過了**：`--restore` → 把範本夾搬回原處 → 起樹，又全部回到舊路徑跑起來。但只要改完之後樹起過一次，daemon 就會重寫表，`--restore` 必須加 `--force`；而且改完之後才掛上的列，退回後會從表上消失（見「明早要注意的」第 4 條）。
- 預演中找到腳本的兩個毛病，都已經修好（見「碰到的坑」第 1、2 條）。06f 的規格有三處跟實際對不上，照實寫在最後一節，腳本照實際做。
- 整個預演沒有叫真模型。eca 那幾列沒問話；agent-fsm 那兩列用假腦問了一句，都答了。

## 預演怎麼搭

全部放在 `~/.aos/scratch/tri-split-1123/rehearsal/`（下面簡寫 `$R`），跟活樹不共用任何東西。

| 東西 | 怎麼做 |
|---|---|
| AOS_HOME | `git archive HEAD`（0f7c19c68）解到 `$R/repo`，在 `$R/repo/proto8` 跑 `install.py`。跑之前先清掉所有 `AOS_*` |
| 乾淨環境 | `$R/clean-env.sh`：清掉所有 `AOS_*`（還有 `CLAUDECODE*`、`LITELLM_KEY`），`AOS_HOME` 設成暫存的那份，`PATH` 拿掉活樹的 `bin`。之後每一道 aos 指令都經過它，也一律帶 `-d <暫存的 stack>` |
| 根 | 定義抄自 `templates/start-api/root`，放在 `$R/home/root`；stack 是 `$R/home/.stack`；起法照 dev-env/03（`cd $R/home && aos-exec --stack .stack root`，用 `setsid nohup` 放在背景跑） |
| 子 daemon | 根表上的一列 `repo-aos`，掛法照活樹：`ctl add --auto-restart -n repo-aos -w $R/repo -s $R/repo/.stack --envs AOS_LLM_KERNEL=$R/home/.stack/procs/llm $R/repo/wf/tree/root` |

用舊路徑掛的列：

| 列 | 掛在哪台 | 掛法 | 想驗的形狀 |
|---|---|---|---|
| `eca-a` | 子 | `--path-json '{"$env":"AOS_HOME","$path":"/templates/eca-claude"}'`；再用 `aos-agent tools add` 加一支工具 | 用 `$AOS_HOME` 指示詞掛的列；agent 自己那份 `tools.json`（`$override` 指回範本），等於 06f 的 `eca-aos` |
| `eca-sub` | 子 | 以 `eca-a` 的身分直接跑 `subagent` 工具（`op: add`，`def_json` 是 `$AOS_HOME` 指示詞，帶 `envs`） | subagent 生的列：`exec` 是 null；`launch.exec` 指 `procs/eca-sub/exec.json#/exec`；`exec.json` 的 argv 裡是 `{"$env":"AOS_DAEMON","$path":"../proto8/templates/eca-claude"}`。**跟 06f 寫的 `-kb` 等三列同一個形狀**，是工具真的生出來的，不是手工造的 |
| `eca-env` | 子 | `ctl add --envs … --parent …`，定義給絕對路徑 | 第三種形狀：`exec.json` 的 argv 是一個**絕對路徑字串**，`as_written.def` 也是絕對路徑字串 |
| `fsm-rel` | 子 | 用相對路徑 `proto8/templates/agent-fsm` 掛 | 用相對路徑掛 `agent-fsm` |
| `fsm-root` | 根 | 用相對路徑 `../repo/proto8/templates/agent-fsm` 掛，停樹之前先 `ctl stop` | 根表上也有要改的列；停之前是 stopped 的列，改完之後要還是 stopped |

不叫真模型：eca 那幾列沒有信就停在 idle，不會叫 Claude；agent-fsm 也只在 idle 等信。驗「答一句」時，另外在根上掛了一台 llm kernel（抄 `templates/kernel/llm-kernel`，它的預設 endpoint 就是假腦 `fake`）。

## 每一步的結果

| # | 步驟 | 結果 |
|---|---|---|
| 1 | 起樹、掛 5 列 | 全部 running。表上的形狀跟 06f 描述的一樣（eca-a 多一處 `as_written.exec`，見最後一節） |
| 2 | 樹還起著時跑「只列不改」 | 兩台 daemon、5 個檔、18 處。結果跟 `grep -rl templates/ 兩個 stack`（排除 history、stderr）找到的 5 個檔完全一樣 |
| 3 | 樹還起著時跑 `--apply` | 拒絕，退出碼 2：`DaemonRunning a daemon is running on …/home/.stack (its stack lock is held)` |
| 4 | 存停之前的 `ls`；`fsm-root` 先 `ctl stop`；`shutdown` | `3 procs asleep`；根與子 daemon 的 pid 都不在了；表上 running 的列變成 sleeping |
| 5 | 照 06a 搬範本夾（只用 `mv`：`agents/`、`kernels`、`daemons/`、`starts/`、`tools/`） | 沒做 06b 的「`.py` 搬進 lib」，`agent-fsm` 整夾原樣搬過去 |
| 6 | 不加旗標跑 `--apply` | 拒絕，退出碼 2：這台機器上有 7 個別的 `aos-daemon` 行程（活樹，以及別條線的測試） |
| 7 | 加 `--allow-other-daemons` 跑 `--apply` | 改了 5 個檔、18 處：根的表 3 處、子的表 12 處、`eca-a/tools.json` 1 處、兩份 `exec.json` 各 1 處。每個檔都先留了 `.bak-trisplit-1124`、記進清冊。改完重新解析 JSON、數命中都是 0。跟備份用 `sed` 換字的結果逐位元組比，完全一樣 |
| 8 | 起樹 | 跟第 4 步存的 `ls` 一樣：列數相同、running 的 running、`fsm-root` 還是 stopped、沒有任何一列寫 `failed to start`、沒有 `.bad-*` 檔 |
| 9 | 驗 | daemon 重寫表之後「只列不改」還是 0 處；兩個 stack 裡（備份除外）grep 不到舊路徑。表上 `def` 與 `as_written.def` 都是新路徑。4 隻 running 的 `aos-loop`，工作目錄都在 `templates/agents/eca-claude` 或 `templates/agents/agent-fsm`。`eca-a` 的 `tools ls` 有 19 支，它自己加的 `self_hook` 還在（`$override` 指到新路徑也讀得到）。`ctl start fsm-root` 也是從新路徑起來的 |
| 10 | 問一句（假腦） | `fsm-rel`、`fsm-root` 都回 `FAKE ANSWER to: 回一個字 …`。eca 三列沒問，問了就會叫 Claude |
| 11 | 停樹 → `--restore` | 不加 `--force` 會拒絕：兩份表在起樹之後被 daemon 重寫過，雜湊對不上；這時一個檔都不還原。加 `--force` 之後 5 個檔都蓋回去了 |
| 12 | 範本夾搬回原處 → 起樹 | 全部照舊路徑起來，狀態跟第 4 步一樣。第 10 步才掛的 `llm` 列從表上消失了（備份裡沒有它，它的 stack 還在） |
| 13 | 第二輪：停 → 搬 → `--apply` → 起 → 驗 | 第一次跑撞到「備份已經在、內容又不一樣」，結果只改了 3 個檔（坑 1）。修好之後重跑，補改了兩份表（新備份叫 `.bak-trisplit-1124-2`），起樹、驗的結果跟第 8、9 步一樣 |
| 14 | `--defs`（在暫存區自己造一份「別的專案」的定義：`fsm.json` 四格、`interfaces.json` 一處 hook） | 列出 5 處，`idle.py` 等改指 `lib/aos/apps/agent_fsm/…`、`hooks.json` 也改指 lib；`--apply` 之後 0 處；`--restore` 之後回到原樣 |
| 15 | 收尾 | `shutdown`；用工作目錄核對，暫存樹的行程是 0 個；活樹那 6 個 `aos-daemon` 從頭到尾都在 |

每一步的輸出留在 `$R/out/`（`list-1.txt`、`apply-1.txt`、`restore-1.txt`、三份清冊、`snapshot-*.txt`）。

## 碰到的坑

1. **先退回、樹又起過，再改一次，會撞到舊備份**（第 13 步）。daemon 起來會重寫表，所以表跟上一輪留下的 `.bak-trisplit-1124` 對不上。第一版的腳本遇到這種情況就跳過那個檔、繼續改別的檔，結果變成改了一半（表沒改、`exec.json` 改了）。**已修**：備份已經在、內容又不一樣時，舊備份留著不動，新的備份取名 `-2`、`-3`……，也記進清冊。重跑是安全的：已經改好的檔命中是 0，不會再碰。
2. **`--restore` 原本會只還原一部分**（第 11 步）。**已修**：先把每個檔都檢查一遍，有任何一個不行，就一個都不還原。
3. **樹起過之後，退回一定要加 `--force`**，因為 daemon 每一輪都會重寫 `procs_state.json`。加了 `--force`，表就回到改之前的樣子，所以改完之後才掛上去的列會從表上消失（stack 還在），列的狀態也回到備份當時的樣子。
4. 這台的殼把 `ls` 換成了 `eza --icons --git`，在 Claude Code 的 shell 裡把它接到管線（`ls | tr`）就卡住，命令跑到逾時被移到背景，最後我把自己那個 `eza` 行程收掉。在樹外視窗代打的 agent 請用 `command ls` 或 `/usr/bin/ls`。
5. 帶 `-s` 掛的列（例如 `repo-aos`），它的 `exec.json` 放在**那一列自己的 stack**（暫存樹是 `$R/repo/.stack/exec.json`；表上的 `launch.exec` 是 `../../repo/.stack/exec.json#/exec`），不在 `<根>/procs/repo-aos/`。dev-env/03 寫的是放在 `~/aos-home/.stack/procs/repo-aos/exec.json`，跟這次看到的不一樣（活樹沒去看）。腳本兩個地方都會找，也會跟著表上的 `…exec.json#…` 去找，所以不影響改表。
6. 根上的 llm kernel 自己也是一台 daemon，腳本會往它底下走。它 stack 裡的 `endpoints.json` 有 4 行舊路徑，腳本把它列成「只列不改」。這份檔是不是 llm kernel 每次起來照定義重寫的，我沒有查。

## 明早要注意的

1. 順序照 06e：第 7 步交了 commit、`shutdown` 之後 `pgrep -af aos-daemon` 確認這棵樹都停了，才跑第 8 步。指令要寫全路徑，用 `python3 -I`：
   `python3 -I ~/repo/aos/proto8/thinking/2026-11/23/org範本與templates分層-1123/06-switch/stack_paths.py --root ~/aos-home/.stack`
2. **`--allow-other-daemons`**：06f 說「有任何 `aos-daemon` 行程就退出」，腳本預設也照這樣做。但這台常常有別條線的測試 daemon（今晚就看到 `/tmp/aos-daemon-b.*`、`/tmp/set-def-*`），明早停了活樹之後，這一條還是可能擋住。腳本另外會對這棵樹走到的每一台 daemon 的 stack 拿 flock，這把鎖跟 `aos-daemon` 起來時拿的是同一把（`daemon.cpp` 的 `check_running`），拿不到就表示那台還在跑、一律拒絕，而且從頭到尾都握著，改的時候這棵樹起不來。所以那些行程確定不是這棵樹的，就可以加這個旗標。**要不要允許這個旗標，請使用者或 eca-aos 決定。**
3. 「只列不改」不拿鎖、也不拒絕，所以 06e 第 12 步可以在樹起著時跑。
4. 退回（06e「出錯怎麼退回」最後一列）：只要改完之後樹起過，`--restore` 就要加 `--force`，代價見「碰到的坑」第 3 條。可以先加 `--dry-run` 看會還原哪些檔。清冊預設寫在 `~/.aos/scratch/tri-split-1123/out/manifest.tsv`，跟 `switch.sh` 的 `out/` 同一個夾。
5. 照 06f 的描述推，這棵樹的 repo 那台大約是：表 1 個檔（`eca-aos` 5 處，三個 subagent 各 2 處）、`eca-aos/tools.json` 1 處、三份 `exec.json` 各 1 處，一共 5 個檔；根的表應該是 0 處。實際數字以「只列不改」的輸出為準，再跟 `rows.tsv` 對。
6. 06f 第 7 條（`~/aos-home/llm/kernel.json`）：照範本抄的那份會命中 6 處，其中 2 處是路徑，4 處是說明文字裡的 `templates/kernel/docs/03`。要順手改就跑 `--defs ~/aos-home/llm`；這份我沒讀，只在暫存區抄的那份上試過。
7. 06e 第 10 步（別的專案的定義）：家機的 `~/repo`、`~/code` 往下 5 層都找不到 `arena_cheater`，也找不到 paper_readings 的 `fsm.json`。家機這一步可能沒有東西要改；公司那台的路徑要另外查。

## 06f／06e 跟實際對不上的地方

| 規格寫的 | 實際 | 腳本怎麼做 |
|---|---|---|
| 06f：有任何 `aos-daemon` 行程就退出（`--defs` 除外） | 06e 第 12 步要在樹起著時跑「只列不改」；而且這台常有別棵樹的 daemon | 只有 `--apply`、`--restore` 會拒絕；判斷靠這棵樹每一台 stack 的 flock（握到結束）。行程檢查預設照 06f，加 `--allow-other-daemons` 才放行 |
| 06f：備份就叫 `<檔>.bak-trisplit-1124` | 退回之後再改一次，會撞到內容不一樣的舊備份 | 舊備份留著不動，新的叫 `-2`、`-3`…… |
| 06f 的表：`eca-aos` 列的路徑在 `exec`、`def`、`as_written` | 用 `$AOS_HOME` 指示詞掛的列，`as_written` 裡 `def` 與 `exec` 兩個都有，再加上 `launch.exec[0]`，一共 5 處 | 照實際換 |
| 06f：`exec.json` 在 `procs/<名>/` | subagent 生的列是這樣；帶 `-s` 掛的列放在它自己的 stack（坑 5） | 兩個地方都找，也會跟著表上的 `…exec.json#…` 去找 |
| 06f：`ctl add --envs` 那種列，argv 裡是 `$env AOS_DAEMON` | `subagent` 工具生的是這樣；直接用 `ctl add --envs` 加絕對路徑，argv 裡是絕對路徑字串 | 兩種都換 |
| 06e 第 3 項：「把暫存樹的 proto8 換成複本 HEAD 裝好的」「三列都各答一句」 | 複本的補丁還沒做完，所以只用 `mv` 搬了夾；`agent-fsm` 還帶著 `.py`，`fsm.json` 沒改。eca 那幾列沒問（問了要叫 Claude） | 「`agent-fsm` 的四格指到 lib」這件事要等補丁好了才驗得到，明早由 06e 第 12 步的第 4 條來驗 |
| 06f：白名單裡有每一列 stack 第一層的 `subagents.json` | `subagent` 工具記帳的地方是 `<上層的 stack>/tools/subagent/subagents.json`，裡面只有名字與 stack，沒有範本路徑 | 不用改；它如果命中，會出現在「只列不改」裡 |

## 沒驗到的

- 活樹的 stack 沒讀，明早的數字以腳本輸出為準。
- 表切成分檔（`$ref`）的情形，沒有讓 daemon 真的切出來（列數要超過一頁）。我照 `windows.cpp` 的寫法手工造了一份（主檔 `{"procs": {"$ref": ["procs_state_procs/a.json"]}}`），只列、改、退回三種都試過：分檔被改到，主檔沒動，旁邊的 `other.json` 列成「只列不改」。
- 改完之後如果有某一列起不來（某一處漏改），會長什麼樣子，這次沒故意造出來看。06f 根據程式寫的是「那一列 stopped，原因寫 `failed to start`」。
