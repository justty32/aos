# astra 當 kernel 施工紀錄（線星 11-14）：階段 0 在暫存樹做到 0.5，門鈴「留著→astra 表態→轉寄」通了，撞到一個新坑：sol 停自己會卡住到期限；11-14 交棒給 ok-astra

← [11-14 日索引](README.md)｜規劃：[astra-kernel-plan](../13/astra-kernel-plan.md)（[04 施工與驗收](../13/astra-kernel-plan/04-施工與驗收.md)、[06 已裁 Q1～Q8](../13/astra-kernel-plan/06-待裁與衝突.md)）

## 白話結論

- 在暫存樹 `~/code/astra-1114/tree` 搭好整套：astra（`gpt-lead-k`）身上掛門、sol（`gpt-worker-k`）的 `AOS_KERNEL` 指那扇門、sol 問腦走隊站 `llm-t1`，再轉 `llm-gpt`。活樹沒碰。
- 腦用的是「照劇本走的假腦」，沒花真腦 token。
- 門鈴這條路走通了：sol 請求停自己，門把信留著，astra 收到 `kernel_hold` 通知，astra pass 以後站把信轉寄給 daemon。
- **新坑（AK14）**：sol 用 `agents_ctl stop` 停自己時，它會等「自己真的停了」才返回，可是 sol 要等這個工具返回才停得了，結果就卡在那裡，一直等到 `timeout_s`（設 600 秒）。`aos-agent ctl stop` 本來有 `--no-wait` 可以解這個，`agents_ctl` 卻沒把它帶出來。
- 階段 1～2、4 沒做。

## 用了哪種隊形

照 07，「astra 帶 sol」要用 aos 樹裡的 agent-fsm 身跑，腦接本地 LiteLLM proxy（使用者 11-14 說不走 codex、不用 terra）。這一輪只做到階段 0，用的是假腦，所以還沒有 gpt 寫碼。蒐集與施工都是我（opus）親手做的，因為階段 0 的工作就是在搭這個隊形本身。

## 階段 0 逐步結果

| 步 | 結果 | 證據 |
|---|---|---|
| 0.1 | **過**。`agent_def check` 兩份定義都 `{"problems": []}`；守門假事件 35/35 過（照舊的 20 則＋門與門鈴的 15 則，包括「停別人擋」「op 不是 stop 擋」「timeout 超過 600 或沒給擋」「多帶鍵擋」「kernel_gate off 擋」） | `~/code/astra-1114/guard_test.py` |
| 0.2 | **過**。`aos-llm ls`（經 `llm-t1`）列出 `fake`、`fake-sol`、`sol-high`；寄一封假腦信，`llm-t1` 與 `llm-gpt` 的 `ledger.jsonl` 各多一行 | `llm-gpt` 帳上這封的 sender 是 `tree/ws`（還是工作區，AK3） |
| 0.3 | **過**。astra 照劇本叫 `kernel_gate on`，印出的信箱路徑跟 `gpt-worker-k/.env` 寫的一字不差；astra 行程的 environ 裡沒有 `AOS_KERNEL`（E11 不成立） | astra 的 `history.jsonl` |
| 0.4 | **過**。astra `subagent add sol-a` 直接寄 daemon，門的 `requests/` 是空的；sol-a 的 environ 兩個值都對 | `/proc/<pid>/environ` |
| 0.5 | **一半過**。sol-a 叫 `agents_ctl stop sol-a timeout_s 600`：門把信留下，astra 收到 `kernel_hold`；由隊長代 astra `pass` 以後，站把信轉寄給 daemon，sol-a 進到 `stopping`。**但它停不下來**：act 那格還在等 `agents_ctl` 返回（AK14）。看了 2 分鐘還卡著；600 秒到期後會怎樣沒看到 | 見下方坑表 |

## 撞到的（接在 05 的 AK1～AK13 後面）

| # | 現象 | 影響 | 可能改法（選項，沒做） |
|---|---|---|---|
| AK14 | **門鈴自鎖**：`agents_ctl stop` 底下跑的是 `aos-agent ctl stop`，它會等那一列變成 `stopped`，可是要停的就是自己，自己的這一輪又要等工具返回才會結束，所以 pass 以後還是卡到 `timeout_s` | 每次門鈴都白等 600 秒，到期後 sol 拿到錯誤（還沒實測是哪個代號） | 甲：`agents_ctl` 的 stop／sleep／pause 補 `no_wait`，跟 `aos-agent ctl` 的 `--no-wait` 一一對應（這支工具的檔頭本來就規定要跟著加，現在等於沒對齊）。`--no-wait` 只等 daemon 收下信，經過門時就是等到 astra pass，正好是門鈴要的；乙：門鈴改用 `mailbox_send`（Q3 的 B 案） |
| AK15 | hook 跑的時候 `AOS_STACK` 指的是 hook 自己的小格（`<stack>/hooks/guard`），不是那隻 agent 的 stack | 守門想認「自己是誰」時，直接取 basename 會拿到 `guard`。已在 `shared-k/guard` 裡往上跳兩層處理 | 甲：hook 另外多給一個 `AOS_AGENT_STACK`；乙：文件寫明 |
| AK16 | 門把 `timeout_s 600` 的停信列成「deadline: none」：`agents_ctl` 的 timeout 只管自己等多久，信本身沒有帶期限 | 階段 1 原本要測的「過期拿 `SlotMissing`」測不到；astra 不表態的話，信會一直留著 | 要測過期的話，得用 `aos-post` 手寫一封帶期限的信 |
| AK9 實測 | 門列出的寄件人是 `from: …/repo`（sol 的工作區），分不出是哪隻 sol | 跟規劃預料的一樣。這一輪改在 sol 那端用守門擋「停別人」（守門從 hook 的 stack 認出自己是誰，見 AK15），所以 sol 經 `agents_ctl` 停不了別人。但從 shell 直接寫信還是可以（已經被 `aos-*` 黑名單和沙箱擋住） | — |

## 交棒給 ok-astra

使用者 11-14 說「多掛幾隻opus eca，把各條線分給他們」，本線交給活樹頂層底下的 opus eca「ok-astra」。

- **做到**：階段 0 的 0.1～0.4 過；0.5 做到 pass＋轉寄，卡在 AK14。階段 1、2、4 沒做；階段 3 本線不換樹。
- **commit**：本檔這一個（見 git log「線星 astra-kernel 階段 0」）。程式一行都沒改，所以 repo 裡沒有別的 commit。
- **暫存樹**：`~/code/astra-1114/`
  - `tree/`：樹本體。五夾用 `copy_tree.py` 從 `a31c00647` 抄來（`TREE_REF`）。`defs/gpt-lead`、`gpt-worker`、`shared` 和 `kernels/llm-gpt` 是從活樹唯讀抄來的，路徑已改寫成暫存樹的路徑。
  - `repo/`：`git archive a31c00647` 解出來的 repo 複本，給 sol 當工作區（sol 寫這裡，不寫真 repo）。
  - 腳本：`setup.sh`（搭樹）、`mkdefs.py`（產生 `-k` 定義與 `llm-t1`，還有 `teams/t1/orders-k` 等夾）、`clean.sh`（清掉 `AOS_*` 再 exec）、`up.sh`（起 root、記 pid）、`t.sh`（在樹的環境裡跑一個指令）、`asagent.sh`（以某隻 agent 的環境跑一支工具，讓隊長代假腦表態）、`guard_test.py`。
  - 狀態：`llm-gpt` 的 `kernel.json` 加了 `fake-lead`、`fake-sol` 兩個劇本包；`llm-t1` 加了 `fake-sol` 轉寄。sol 劇本靠暗號觸發：`#BELL-sol-x#`（停自己）、`#BELL20-sol-x#`（timeout 20）、`#STOP-OTHER#`、`#SHELL-AOS#`、`#SHELL-CTL#`、`#WRITE-CTL#`，其餘都回 STATUS 報告。兩份 `-k` 定義的 `llm.json` 目前指假腦包，進階段 2 要改成 `astra-high`／`sol-high`。
- **程序**：全是我起的，都記在 `~/code/astra-1114/pids.txt`。交棒時用 `aos-daemon-ctl -d ~/code/astra-1114/tree/.stack shutdown` 把整棵暫存樹收掉，收完 `pgrep` 核對一隻不剩（結果寫在下面的「收尾核對」）。要接著做就跑 `./clean.sh ./up.sh` 重起，再照 `t.sh` 掛回 `llm-gpt`、`llm-t1`、astra。stack 都留著，可以接著用。
- **下一步**：
  1. AK14 要先處理。補 `agents_ctl` 的 `no_wait` 是改 aos 程式（`proto8/lib/agent/agents_cmd.py` 的 `LIFE_OPS`／`life_argv`），規劃裡寫的是「不改 aos 程式」。所以先確認這算對齊漏掉的旗標（照工具檔頭的規定），還是要走正統規劃流程。我傾向前者，但沒動手。改的話先只改暫存樹的 `tree/lib/agent/agents_cmd.py` 試，綠了再進 repo（repo 的 `lib/` 要重抄進活樹才會生效）。
  2. 補完 0.5 以後做階段 1（refuse、`#STOP-OTHER#` 用 `aos-agent ctl stop` 從隊長殼寄進門、shell 寫 ctl 信箱、`llm-t1` 額度設 3、gate off 擋）。過期那條看 AK16。
  3. 階段 2 換真腦：兩份 `llm.json` 改 `astra-high`／`sol-high`，`llm-gpt` 的 `budget.senders` 換成暫存樹這一輪的名字（目前是改寫過路徑的舊名 `gpt-lead2`、`sol-T03`、`sol-T04`，沒列到的寄件人怎麼算還沒驗），真腦 token 要記帳。
- **已知的坑**：AK14～AK16（上表）；llm 站改了 `kernel.json`，`aos-llm ls` 要過幾秒才看得到新包；astra 的假腦劇本用完以後，遇到 `kernel_hold` 會叫第一個工具（`clock_register`），會回一行 ArgumentsBad，沒有害處；sol-a 的 history 裡有一次被舊守門誤擋的紀錄（AK15 修之前）。

## 收尾核對

- 08:23 用 `aos-daemon-ctl -d ~/code/astra-1114/tree/.stack shutdown` 收暫存樹，回「daemon … stopped; 3 procs asleep」。`pids.txt` 裡的 pid（root 148380／148383、時鐘 148385、兩個 sweeper 148386／148392、foreman 148387、`llm-gpt` 148997、`llm-t1` 157950、astra 162530、sol-a 164115 和它卡住的 act 177313）都已經不在了。
- 活樹兩台 daemon（37179、37183）還在。表上其他的 daemon 是別條線的暫存樹（`skyrim-1114`、`kf-1114` 等），沒碰。
- 活樹 `repo-aos` 的 stack 比開工時多了 `hooks.json`、`tools.json`（08:19 建的）。我這邊每個 aos 指令都經過 `clean.sh` 清掉環境，指向的是暫存樹，所以推定這兩個檔是頂層同時段掛 eca／當 kernel 時產生的，不是本線造成的。

## ok-astra 接手（11-14 08:25 起）

### 白話結論

- **AK14 解了**：`agents_ctl` 補上 `no_wait`。門鈴改成 `{"op":"stop","name":"<自己>","timeout_s":600,"no_wait":true}`：等到 astra 表態，pass 之後 1 秒內 sol 就停好，工具回「stop accepted」。repo 改的是 lib 四個檔，頂層 11-14 回信同意「補漏，直接 commit」。
- **階段 0 全過、階段 1 全過**（假腦，七條回信都回到寄件人，表上沒多出不該有的列）。
- 新撞到兩件：AK17（問腦被額度拒時 agent-fsm 直接退出，sol 不會按鈴）、AK18（被門拒的錯誤代號外層是 `CtlRejected`）。另外，暫存樹裡 llm-t1 帳上的寄件人已經是 sol 的 stack（AK3 在這棵樹的第一站不成立）。
- 寫碼交給 agent-fsm 的 sol（`astra-sol-1`，LiteLLM `sol-high`，只有讀寫檔工具、沒有 shell），我出圖紙、審 diff、跑測試。sol 有沒有讀必讀規矩的紀錄在 `wf/temp/ok-astra/notes/sol-readcheck.md`（工作區，gitignore）。

### AK14 的改動（repo；換樹時要抄進活樹 lib 的檔）

| 檔 | 改什麼 |
|---|---|
| `proto8/lib/agent/agents_cmd.py` | `life_argv`：`no_wait` 為真就加 `--no-wait`（rm 放在 `rm` 後面，其他放在 `--target NAME` 後面）；`LIFE_OPS` 不動，所以 subagent 不收這個鍵 |
| `proto8/lib/agent/agents_ctl/_entry` | 只有 stop、sleep、pause、rm 收 `no_wait`；檔頭補說明 |
| `proto8/lib/agent/agents_ctl/_tooldef.json` | 加 `no_wait` 參數，說明裡多一行「停自己」的範例 |
| `proto8/lib/agent/agents_ctl/tests/test_agents_ctl.py` | 新增 5 個對應案例、2 個錯誤案例 |

驗證：在 `git archive HEAD` 的乾淨複本上跑，agents_ctl 4、subagent 21（skip 2）、fork 13、self_ctl 全 OK。活樹沒動，要等下次換樹重抄 lib 才會生效。

### 暫存樹這邊跟著改的（`~/code/astra-1114`，不進 repo）

- `patch-ak14.py`：把上面三個 lib 檔抄進 `tree/lib`；`shared-k/guard` 規定門鈴要帶 `no_wait: true`（沒帶或帶 false 就擋）、`no_wait` 算合法鍵；`gpt-worker-k/system.txt` 的門鈴那行加上 `"no_wait": true`；假腦 `fake-sol` 劇本的 15 個門鈴都補上 `no_wait`。
- `guard_test.py` 增為 37 例（多了「沒帶 no_wait」「no_wait false」兩例），37/37 過。
- `as.sh`（以某隻 agent 的身分叫一支工具；subagent 的 `AOS_STACK` 給工具小格 `tools/subagent/`）、`hist.py`（看 history 尾巴）。舊的 `asagent.sh` 叫 subagent 時，`AOS_STACK` 給的是 agent 本身的 stack，記帳檔會寫到 stack 根，蓋到配額設定的位置；我 08:36 撞到，那個檔已改回 `{}`。

### 階段 0.5 重跑與階段 1

| 條 | 結果 | 回信原文（節錄） |
|---|---|---|
| 0.5 門鈴 | **過**。sol-b 按鈴 → 門留著（`deadline: none`）→ pass → 1 秒內 stopped，sol-b 行程已退 | `stop accepted; sol-b stops when this round ends, stack kept (...)` |
| refuse | **過**。sol-c 按鈴，被拒後照常在跑 | `agents_ctl: error: CtlRejected the stop letter was refused: HoldRefused report section is empty; fill it in` |
| 過期 | **過**。用 `aos-post` 手寫一封 `{"procs_stopped":["sol-zz"],"queue_wait_ms":20000}`（AK16：`agents_ctl` 帶不出期限）；門列「the sender waits 17 more seconds」，21 秒後回信 | `{"applied": false, "error": {"code": "SlotMissing", "msg": "held 20965 ms, nobody decided in time (queue_wait_ms 20000)"}}` |
| 停別人 | **過**。從隊長殼設 `AOS_KERNEL`＝門、寄 `ctl stop --target llm-t1`；門留著，由隊長代 astra 拒，llm-t1 照常在跑 | `aos-agent: error: CtlRejected the stop letter was refused: HoldRefused llm-t1 is not one of my workers` |
| sol shell 跑 `aos-*` | **擋**（守門） | `blocked: this command matches a forbidden pattern (\baos-[a-z-]+)` |
| sol shell 寫 ctl 信箱 | **擋**（沙箱） | `mkdir: cannot create directory '.../procs_requests': Read-only file system` |
| sol 用檔案工具寫 ctl 信箱 | **擋**（守門） | `blocked: .../procs_requests/new/x.json is outside the folders you may write` |
| llm-t1 額度 | **擋**。已用 13 次時把 `max_calls` 改成 15，第 16 次被拒；**但 sol 隨後退出了**（AK17） | `aos-llm: error: BudgetMissing budget for this window (day) is used up; not run` → `agent-fsm: error: BrainFailed` → `sol-c stopped ... RunFailed` |
| gate off | 只能靠守門擋（guard_test「gate off blocked」） | — |

### 新撞到的（接在 AK16 後面，只記不改）

| # | 現象 | 影響 | 可能改法（選項，沒做） |
|---|---|---|---|
| AK17 | **問腦被拒時 agent-fsm 直接退出**：`BudgetMissing` 經 `aos-llm recv` 退 1 → `BrainFailed` → fsm 跑失敗 → 那一列變 stopped（failed）。sol 沒機會寫工單、也不會按鈴 | 規劃 03 E10 寫的「sol 拿到 BudgetMissing → 寫工單、按鈴」不成立。astra 收不到門鈴，只看得到表上 sol 那列 failed | 甲：sol 的定義掛一支 `brain_failed` hook，把這件事寫進工單或寄信到隊信箱；乙：astra 的巡邏提醒裡加一句「看 ls 有沒有 failed 的 sol」；丙：agent-fsm 對 `BudgetMissing` 不當致命錯誤（要改 aos，走規劃） |
| AK18 | 被門拒時，sol 拿到的代號是 `CtlRejected`，`HoldRefused` 只出現在訊息裡 | worker 的 system 寫「answers HoldRefused」，sol 要比對的是訊息文字，不是代號 | 甲：system 寫成「error line mentions HoldRefused」；乙：`aos-agent ctl` 把 kernel 回的代號原樣往上傳 |
| AK3 補記 | 暫存樹（repo 那份 `aos-llm`）裡，llm-t1 帳上的寄件人已經是 sol 自己的 stack（`.../procs/sol-c`）；llm-gpt 那邊看到的寄件人是轉寄的那一站 | 「每隻 sol 分開算額度」在隊站這一層已經可以做，不必等換樹；活樹的 `aos-llm` 是不是同一支還沒核 | 階段 3 開工前，核對活樹 `aos-llm` 實際指到哪 |

### 下一步

- 階段 2 換真腦：兩份 `-k` 的 `llm.json` 改成 `astra-high`／`sol-high`，llm-gpt 的 `budget.senders` 換成這一輪的名字，真腦 token 要記帳。開跑前 AK17 先用乙案頂著（巡邏時看有沒有 failed 的 sol）。
- 階段 3 不做，只列 build（見下一次更新）。
- 階段 4 做之前要先問使用者（04 寫明它跟「門鈴叫醒 astra」打架）。
