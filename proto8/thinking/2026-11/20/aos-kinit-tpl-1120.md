# 線 aos-kinit-tpl-1120：把使用者對「初始 kernel」八題的答案落到文件與起手範本（start-api 改成 llm kernel 掛同板、加選裝不開的權限站）

← [11-20 日索引](README.md)｜依據：[aos-init-kernel-1120](aos-init-kernel-1120/README.md)（[06-使用者已答](aos-init-kernel-1120/06-使用者已答.md)）

使用者 11-20 說「開工吧」。八題的答案逐字在 06；這條線照答案改文件、起手範本與重建步驟單，不改 kernel 的程式。

## 做了什麼

### 文件用詞：初始 kernel＝最小核心＋llm 件＋權限件，另有一串可選件

| 檔 | 改了什麼 |
|---|---|
| `templates/kernel/README.md` | 新一節「初始 kernel：買了板子之後灌什麼」：四塊一張表（最小核心／llm 件／權限件／一串可選件）、沒裝權限件時剩什麼、權限件不是牆（明寫）、P4、`AOS_KERNEL` 不寫根的 `.env`、鐘與清道夫「算核心」只是說法、程式沒擋；llm-kernel 那列補「主線是掛成板子上的一列」 |
| `templates/kernel/docs/01-llm-kernel.md` | 「起來」分成主線（掛成板子上一列）與另一種（自己一台）；清道夫那句拿掉「不要就刪」；「llm 件可選只對不會想的 proc 成立」 |
| `templates/kernel/docs/02-kernel-modes.md`、`03-feat-proto.md` | 拿掉「不掛清道夫的調回 4」兩句 |
| `docs/tutorial/03-灌kernel.md` | 開頭補三塊是什麼（權限件教學不裝、指到 start-api）；折疊段改成「主線是掛在板子上，另一種是自己一台」（原本寫 start-api 用另一種） |
| `knowledge/aos/kernel.json` | `what` 補「The initial kernel」一段（英文，給 agent 看）；`_description` 與 `knowledge/aos/_index.json` 那句描述提到它 |
| `templates/start-api/README.md` | 整份改寫：新用法、選裝權限件三步與注意、裡面有什麼 |
| `templates/start-eca/README.md`、`root/.env` | 只改指到 start-api 舊擺法（`llms/def`）的字 |
| `thinking/2026-11/17/重建步驟單.md` | 見下面「影響家裡那台」 |

「一串可選的」使用者只舉了「需要額外依賴的權限那塊，還有一堆比較麻煩的東西」，文件只引他的話，其餘寫「待定」，沒替他列清單。

### 起手範本 start-api

- `llms/def/` 換成 `llm/`（`kernel/llm-kernel` 逐字抄本）；用 `aos-daemon-ctl -d .stack add --auto-restart llm` 掛上根，`root/.env` 的 `AOS_LLM_KERNEL` 改成 `${AOS_STACK}/procs/llm`（跟教學同一個擺法）。
- **刪了** `templates/start-api/llms/def/` 七個檔（`.env`、`_entry`、`daemon.json`、`endpoints/litellm/_entry`、`fake_slow/_entry`、`interfaces.json`、`kernel.json`；跟 `llm/` 逐字一樣，git 歷史裡留著，工作樹那份搬到 `~/.aos/scratch/aos-kinit-tpl-1120/moved-repo/llms/`，沒真的刪）。
- 新 `perm/`：`kernel/procs-kernel` 的抄本，只有 `kernel.json` 改成 `{}`；出廠沒掛。
- 新 `agents/ann/.env`：只有一行註解掉的 `# AOS_KERNEL=${AOS_DAEMON}/procs/perm/requests`。
- `templates/tests/test_start.py` 跟著改：新對照表、允許 `agents/ann` 多一個 `.env`、檢查 `perm/kernel.json` 是 `{}`、ann 的那行是註解、兩包的 `root/.env` 都沒有 `AOS_KERNEL=`。
- 用到 start-api 擺法的兩支實跑測試改成掛同板：`py/tests/test_aos_py_live.py`、`py/tests/apps/gdb/test_gdb_live.py`（後者與 `py/aos/apps/gdb/README.md` 見「跟別線」）。

## 證據

### 實跑（暫存樹、假腦）

`~/.aos/scratch/aos-kinit-tpl-1120/run1/`，照新的 start-api 從零起：

```
$ aos-daemon-ctl -d .stack add --auto-restart llm
$ aos-agent -d .stack ctl add --auto-restart -w . agents/ann
$ aos-daemon-ctl -d .stack ls
_clock	running	818130	-	-	-
_sweeper	running	818132	-	-	-
llm	running	818365	-	-	-
ann	running	818500	-	…/run1/aos-home	-
# daemon: running (pid 818127)
# root daemon (no supervisor)
$ aos-agent -d .stack --target ann say hello && aos-agent -d .stack --target ann listen --timeout-s 20
FAKE ANSWER to: hello (tool said: 2026-11-20T03:49:55Z)
```

開權限件（掛 perm、打開 ann 的那行、重起 ann）：

```
ann's AOS_KERNEL now: AOS_KERNEL=…/aos-home/.stack//procs/perm/requests
$ aos-agent -d .stack --target ann say hello again && … listen --timeout-s 20
FAKE ANSWER to: hello again (tool said: 2026-11-20T03:50:16Z)
$ AOS_KERNEL=…/.stack/procs/perm/requests aos-agent ctl ls     # 經站讀表，五列都 running
$ aos-daemon-ctl -d .stack stop perm; time (AOS_KERNEL=… aos-agent ctl ls)
aos-agent: error: KernelFailed no reply from AOS_KERNEL=… within 3 s (…)
real	0m3.804s
```

一句 `shutdown` 之後根與 llm kernel 的表都是 `sleeping`；只起根，五列全醒，再問一句回 `FAKE ANSWER to: after restart …`。全文：`run1.out`。

反證（`run2/`）：把 `AOS_KERNEL=${AOS_STACK}/procs/perm/requests` 寫進 `root/.env`，ann 問腦失敗（`EndpointFailed … EntryMissing`），根的表上多一列 `llm_<信名> stopped`——llm kernel 繼承到它，問腦 proc 經站掛到根上去了。所以那行放在 ann 的 `.env`。全文：`run2.out`。

最後照 README 逐字在裝好的乾淨複本（`mine/`）再跑一次（`cp -r $AOS_HOME/templates/start-api …` 起、開權限件那三步用 README 上的 `stop ann && start ann` 一句）：預設回 `FAKE ANSWER to: hello …`，開了之後 ann 的環境有 `AOS_KERNEL=…/.stack//procs/perm/requests`、回 `FAKE ANSWER to: hello again …`，`shutdown` 一句收乾淨。全文：`run3.out`。

### 測試

都在 `git archive` 抄出的乾淨複本、自己 `install.py`、清掉 `AOS_*` 跑。

- 全套 79 夾，base（`e1209424b`）與 mine（同一個 commit＋本線的檔）逐夾比：2953 支兩邊一樣多。兩邊都紅的：`py/tests/apps/eca`（TtySocket 四支，socket 路徑長度）、`py/tests/apps/feedback`（1 支，讀不到 wf 那類）、`py/tests/apps/gdb` 的 `test_15_step_goes_one_cell_at_a_time`（base 另多紅 `test_13`）。mine 多紅一支 `py/tools/aos/kernel/tests` 的 `test_06_hook_failures_stop_or_continue`（hook 逾時、時間性），單獨重跑 122 支全綠。
- 交件前 HEAD 走到 `60c0a6d28`（期間 aos-gdb-small-1120 交了 gdb 的改動）：在它上面疊本線的檔再跑 `templates/tests` 29 支 OK、`py/tests/apps/gdb` 66 支 OK、`py/tests` 690 支 OK。
- `templates/kernel/tests` 不是 unittest 夾（discover 0 支，兩邊一樣）；它的 `kernel-chain-check/check.py` base 與新 HEAD＋本線都是 `8/8 ok`。
- `test_start.py` 新加的檢查：改壞沒驗（沒做變異測試）。

## 影響家裡那台之後重建的改動（起手範本、重建步驟單）

1. 樹裡 `llms/def/` 沒了，換成 `llm/`；llm kernel 的 stack 從 `llms/stacks/llm/` 搬到 `.stack/procs/llm/`。
2. 第 6 步：不再另開視窗 `cd llms && aos-exec --stack stacks/llm def`；改成視窗 B `aos-daemon-ctl -d .stack add --auto-restart llm`（只要第一次）。
3. 關樹從兩句變一句 `aos-daemon-ctl -d .stack shutdown`；再起只要視窗 A；更新五步第 1、5 步跟著變。
4. 真模型的金鑰要在**起根的視窗**export（以前是起 llm kernel 的視窗 B）。
5. `setsid` 脫離終端的起法只剩根那一句（llm kernel 不用另起；實跑時它不往 `root.log` 印 `counter_runs`）。
6. `root/.env` 的 `AOS_LLM_KERNEL` 改指 `${AOS_STACK}/procs/llm`。
7. 樹裡多 `perm/`（沒掛）與 `agents/ann/.env`（只有註解）；更新第 4 步 `diff -r agent-fsm` 會多列出這個 `.env`；多一句 `diff -r … llm-kernel … llm`。
8. 照 11-20 以前抄好的樹不寫遷移（proto8 當成沒有舊版）：重建時照新寫法重抄。

## 替使用者做的選擇

- 身分、信箱、daemon 照調查稿 b 列為最小核心：頂層在第 6 題題目裡這樣假設，使用者沒反對、也沒明說同意。
- 權限站那行註解放在 **ann 的 `.env`**，不放 `root/.env`（調查稿 05 第 3 題 b 寫的是「`.env` 留一行註解」，沒說哪份）：放根上會讓 llm kernel 也繼承到、問腦全壞（上面反證實跑）。代價：要經站的每隻 agent 都要在自己的 `.env` 寫這行。
- 權限站的 `kernel.json` 出廠是 `{}`（全放行），沒照抄 `procs-kernel` 的白名單（`peek_now_time` 兩個名字、`max_running` 2）：照抄的話 ann 一開就掛不了任何子；要管什麼由使用者自己加。
- 權限站的資料夾叫 `perm/`，表上那列叫 `perm`。
- 開權限件是三步（掛站、打開那行、重起 ann），不是只打開註解：站沒掛就打開那行，ann 的「我是誰」等 3 秒就 `KernelFailed`。
- llm kernel 資料夾叫 `llm/`（跟教學一樣、表上那列也叫 `llm`），沒留 `llms/def/` 再用 `--name llm` 掛。
- start-eca 沒帶 llm kernel，它 `root/.env` 那行值沒改，只改了註解裡指到 start-api 舊擺法的字。

## 沒做的與原因

- 鐘、清道夫「刪不掉」的程式保護沒做（任務書：另一件事）；文件寫了「算核心只是說法，程式沒擋」。
- kernel 的程式（`round.py`、llm kernel）、guard、sandbox、「寄信問 kernel」協議、排序搬骨架：任務書說不做。
- P4（站 3 秒不回全體 `KernelFailed`）只寫進說明，沒修。
- `docs/CONCEPTS` 的 C-47「daemon 自己就是最簡單的 kernel」沒動：跟「最小核心」並不衝突，要不要另立一條概念是使用者的事。
- `templates/daemon-root/` 的 README 與 `.env` 仍寫「llm kernel 是另一個專案」（預設 `${AOS_WS}/../llms/stacks/llm`）：那是 daemon-root 自己的預設，不在領地；起手範本與教學都改寫了它。

## 跟別線

- `py/tests/apps/gdb/test_gdb_live.py`、`py/aos/apps/gdb/README.md` 不在領地，但 start-api 換擺法後非改不可（測試照舊擺法起 llm kernel）。施工中 aos-gdb-small-1120 正在改這兩檔，等它交了（`b611ae18c`～`82bed567f`）才 claim，在它的版本上只改起 llm kernel 與收樹那幾行。
- `py/tests/test_aos_py_live.py` 同理（沒人在改，claim 後改）。
- `knowledge/aos/_index.json` 只改 kernel.json 那一句描述。
- 其他別線的檔沒碰；工作樹裡別線沒交的改動沒抄進自己的複本。
