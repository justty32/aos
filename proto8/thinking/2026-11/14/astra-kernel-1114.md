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
