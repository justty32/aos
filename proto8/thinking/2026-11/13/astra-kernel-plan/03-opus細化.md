# astra-kernel 的 opus 細化：fable 的待驗讀程式驗掉六項、跟 fable 不同的六處、新舊檔對照、十二條邊緣狀況

← [astra-kernel-plan](../astra-kernel-plan.md)｜上一份 [02-fable設計](02-fable設計.md)｜下一份 [04-施工與驗收](04-施工與驗收.md)

`P/`＝`proto8/`，`H/`＝`~/aos-home/`。「讀」＝opus 讀程式或活樹檔確認；「待驗」＝施工階段 0 乾跑才算數。

## 一、fable 的待驗，讀程式的結果

| # | fable 的待驗 | 結果 | 出處 |
|---|---|---|---|
| V1 | 「定義裡直接列 `kernel_gate`」行不行 | **行**（讀）：活樹有 `H/lib/packs/kernel_gate.json`；定義的 `tools.json` 是 `$override` 一串包，加一行 `{"$env":"AOS_HOME","$path":"/lib/packs/kernel_gate.json"}` 就有，不用 self 包。`kernel_gate on` 掛 hook 是叫 `aos-agent hook --target <自己>`（CLI），不經 `self_hook`、不需要 events 包 | `H/defs/gpt-lead/tools.json`、`P/lib/agent/kernel_gate/_entry:103` |
| V2 | sol 有沒有工具寄「停自己」 | **現在沒有**（讀）：gpt-worker 沒有 subagent 包、shell 守門擋 `aos-*`。要給 sol 一支 `agents_ctl`（它收 `timeout_s`，經 `aos-agent ctl`，有 `AOS_KERNEL` 就寄那裡），守門只放行 `op: stop`、`name`＝自己。tools.json 能不能單列一支工具（不是整包）待驗；不行就照 `kernel_gate.json` 的樣子在定義夾寫一份只有 `agents_ctl` 的小包 | `P/lib/agent/agents_ctl/_tooldef.json`、`_entry:12`、`H/defs/gpt-worker/guard.json` |
| V3 | sol 的沙箱擋不擋得到直寄 daemon、`llm-gpt` 的信箱 | **擋得到**（讀）：sol 的 shell 只寫 `repo/proto8`、`repo/wf` 與自己的 stack；daemon 的 ctl 信箱與 `llm-gpt` 都在 `H/ws/.stack/` 下別的夾。活樹舊執行檔寫沒綁的地方會「成功」寫進 tmpfs（T36），主機上不會有信——一樣到不了 | `H/defs/gpt-worker/guard.json`、[06 T36](../gpt-fsm-team/06-試驗紀錄.md) |
| V4 | 規則站能不能當 loop proc 管掛 proc 的請求（丙案） | **能**（讀）：出廠範本 `P/kernel/procs-kernel/` 就是這個（`lib/aos/kernel` 當 loop proc）；hook 用 `after_verdict` 回 `{"next": astra 的門}` 把例外分流過去，其餘照 `next` 到 daemon | `KB/kernel.json#/templates`、`P/lib/aos/kernel/README.md`「分流」 |
| V5 | 起 sol 時用 `envs` 帶兩個環境值 | **改用定義夾 `.env`**（讀）：gpt 隊 sol 的 `AOS_LLM_KERNEL` 本來就寫在 `H/defs/gpt-worker/.env`；守門也擋 astra 帶 `envs`（擋了才不會被 astra 改指別站）。兩個值都是固定路徑，寫死在新定義的 `.env` 就好 | `H/defs/gpt-worker/.env`、[gpt 03 守門表](../gpt-fsm-team/03-opus細化.md) |
| V6 | `max_running`（＋`count_daemon`）限 sol 數 | **不適用**（讀）：`max_running` 數的是整台 daemon 表上 running 的列（`_sweeper`、`eca_main`、`repo-aos`、`llm-gpt`…全算）；而且 sol 寄的只有「停自己」，`procs_stopped` 不算進名字。sol 數量照舊用 astra 的 `subagents.json` `max_subagents` 管 | `P/lib/aos/kernel/procs_rules.py:165-195` |

## 二、跟 fable 不同的地方

1. **環境值寫在新定義的 `.env`，不用 `envs`**（V5）。astra 的守門照舊擋 `envs`。
2. **門的規則幾乎是空的**：`allowed` 只管 `procs_added` 的名字，sol 不會 add，所以不寫 `allowed`、不寫 `max_running`；站的預設 hold hook 把每封都留給 astra。**「sol 只能停自己」規則擋不了**：ctl 信的寄件人是 `aos-post` 的 `identity()`＝`$AOS_WS` 優先，所有 sol 的 ws 都是 repo（線修只改了問腦那條路，見 [05 AK9](05-試驗紀錄.md)）。所以「停的是不是寄件那隻」只能 astra 看 `request` 那行自己判，system.txt 寫明。
3. **門鈴的工具是 `agents_ctl`（只放行 stop 自己），不是 shell 的 `aos-agent`**（V2）。
4. **門的 `kernel.json` 由 astra 自己 `on` 產生預設那份**，不由隊長預寫——預寫要碰 astra 的 stack，撞「不碰別人 stack」；預設那份（每封都留著）正好是甲案要的。
5. **隊問腦站 `llm-t1` 第一輪只設全隊總額度**，不分每隻 sol：活樹舊執行檔下寄件人都是 repo（AK3），而且 `budget.senders` 只收死路徑、sol 名字每單一換（AK8）。分每隻 sol 放到階段 3（換執行檔後），屆時 sol 的名字改成固定格位（`sol-a`、`sol-b`），每單結束 `rm` 不 purge，下一單換新名字前隊長收舊 stack——這條跟 T26 互卡，列成裁題 Q5。
6. **astra 不改額度**（fable 裁題 4 推薦「能」）：改額度＝改 `llm-t1/kernel.json`，在 `H/kernels/` 底下、不在隊夾，守門得多開一個寫入根，又是一條能自己放大自己的路。第一輪不給，列裁題讓使用者定。

## 三、檔案對照（全部是活樹新增；repo 只有本規劃）

| 檔 | 從哪來 | 改什麼 |
|---|---|---|
| `H/defs/gpt-lead-k/`（整夾） | 抄 `H/defs/gpt-lead/` | `tools.json` 加 `kernel_gate` 包；`system.txt` 加一節「You are the gate」（見下）；`guard.json` 的 `subagent.def` 改指 `gpt-worker-k`；`.env` 不設 `AOS_KERNEL`（直走 daemon，防自己判自己） |
| `H/defs/gpt-worker-k/`（整夾） | 抄 `H/defs/gpt-worker/` | `.env` 兩行：`AOS_LLM_KERNEL=H/ws/.stack/procs/llm-t1`、`AOS_KERNEL=H/ws/.stack/procs/gpt-lead-k/hooks/kernel_gate/requests`；tools 加 `agents_ctl`（單支）；`hooks.json` 守門條件加 `agents_ctl`；`guard.json` 加 `agents_ctl: {"ops": ["stop"], "self_only": true, "max_timeout_s": 600}`；`system.txt` 加「Ring the bell」一節 |
| `H/defs/shared/guard` | 既有 | **不改**；`agents_ctl` 規則另寫 `H/defs/shared-k/guard`（抄一份再加），兩份 `-k` 定義的包裝腳本指它（活樹只新增不改） |
| `H/kernels/llm-t1/`（整夾） | 抄 `P/kernel/llm-team/`，身體換 Python `lib/aos/kernel_llm` loop proc（照 `H/kernels/llm-gpt/loop.json`） | `endpoints` 只留 `sol-high` 一包，`kernel` 指 `H/ws/.stack/procs/llm-gpt`；`budget` 全隊 300 次／天、`spent: refuse` |
| `H/teams/t2/`（整夾） | 新建 | `blueprint.txt`、`orders/`、`mailbox/`、`logs/`、`status.md`；工單格式見 04 |
| `H/kernels/llm-gpt/kernel.json` | 既有 | **不改**；astra 的腦照舊直寄它（寄件人 `teams/t1` 的額度 key 那行：astra 的工作區改 `t2` 後要新增一個 key——這是改既有檔，列裁題 Q6） |

`gpt-lead-k/system.txt` 要加的話（中文意思，施工時寫英文）：你是 sol 們的門；sol 做完會寄「停自己」的請求，你會收到 `kernel_hold`；先讀那張工單的回報欄再驗收，合格就 `pass` 再 `rm`，不合格 `refuse` 並 `say` 原因；`request` 裡要停的名字不是你派過單、而且那張單回報欄已寫好的 sol，就 refuse（`agents_ctl` 帶不了多的鍵，寄件人又分不出是哪隻，只能這樣對）；手上有 sol 時不睡、不用 `listen` 等、不用 `ask`；每 5 分鐘有一次巡邏提醒（`clock_register`）。

`gpt-worker-k/system.txt` 要加的話：做完把結果寫進工單回報欄，然後 `agents_ctl {"op":"stop","name":"<你自己>","timeout_s":600}`；回 `HoldRefused` 就照 astra 接著說的改；回 `SlotMissing` 隔一分鐘再寄，最多兩次，再不行在工單寫「門沒回應」然後停手。

## 四、邊緣狀況

| # | 狀況 | 會怎樣 | 處理 |
|---|---|---|---|
| E1 | sol 按鈴時 astra 正在回合中 | 站不跑，信在信箱等；sol 的 600 秒內 astra 回合結束就會跑到 | 600 秒；astra 短回合規矩；過期照重寄規矩 |
| E2 | 兩隻 sol 同時按鈴 | 一則通知列兩封 | astra 一封一封表態；沒問題 |
| E3 | sol 按鈴時手上的 act 格卡著 600 秒 | sol 自己的 hook、mail 都不跑；但它本來就要停了 | 可接受；記 AK10 |
| E4 | astra pass 了，sol 被停，但 astra 忘了 rm | sol 佔表上一列（stopped） | 隊長收尾 `ctl ls` 看；system 寫 pass 後馬上 rm |
| E5 | astra refuse 後 `say` 退件，sol 還在 act 格（agents_ctl 剛回） | `say` 進 sol 的 queue，下一格讀到 | 沒問題；驗收時看 sol 有沒有讀到 |
| E6 | sol 寄的 stop 名字是別隻（eca_main、另一隻 sol） | 門留給 astra；astra pass 就真的停了別人 | system 規矩＋工單號對照；**這是本設計最大的洞**（AK9）；階段 1 要測 astra 會不會擋 |
| E7 | astra 死掉 | 留著的信沒人表態，sol 都等到 600 秒過期 | 隊長看門腳本每分鐘看 astra phase；死了隊長 `aos-daemon-ctl` 收 sol |
| E8 | astra `kernel_gate off` | 留著的全回 `HoldRefused`；之後寄來的沒人回、等到期 | system 寫「不准 off」；守門擋 `kernel_gate` 的 `off`（守門條件加它） |
| E9 | llm-t1 沒掛或死了 | sol 的 wait 格：信不見了／kernel 夾不在，照 wait.py 的規矩等 | 起 sol 之前先驗 llm-t1 在表上；auto_restart |
| E10 | llm-t1 總額度用完 | sol 拿 `BudgetMissing`，照規矩寫工單、按鈴 | 階段 1 用小額度假腦測 |
| E11 | astra 自己的 `AOS_KERNEL` 被某個上層環境帶進來（daemon 的 `.env`） | astra 的 `subagent add` 寄給自己 → 死鎖、`SlotMissing` | `-k` 定義 `.env` 明寫 `AOS_KERNEL=`（空）？空值的意思待驗；乾跑時 `env` 確認 |
| E12 | 門的通知 `kernel_hold` 跟 `mail_notify` 的新信同時到 | 兩則 user 訊息；`--history task` 會被切（T27） | astra 用完整 history（照 gpt 隊） |
