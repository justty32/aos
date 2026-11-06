← [portable-flow README](README.md)｜上一份：[06-實作步驟草稿](06-實作步驟草稿.md)

## 11-05 晚 listen paused bug

寫 aos-agent 用法頁時實跑發現：對一隻 agent `pause → resume → stop → start` 之後，`aos-agent listen` 仍報 paused、等滿逾時。

### 成因

**子 loop 的 ctl 只有一格，`resume` 被 daemon 寫的 `stop` 蓋掉了。** 暫停中的 aos-loop 每秒才讀一次 ctl；`aos-daemon-ctl resume` 寫完就回，緊接著 `ctl stop` 讓 daemon 往同一格寫 `{"cmd": "stop"}`，loop 只讀到 stop——停下時 `state.json` 的 `paused` 還是 true，`start` 照「暫停中被停的，起來先暫停」又暫停。間隔一秒以上手打不會中，連著打（腳本、複製貼上）必中（試驗場 3/3 重現）。

### 修法

1. **`aos-daemon-ctl pause／resume` 等套用才回**（`write_cmd` → `wait_applied`）：寫完等子 loop `state.json` 的 `ctl_seq` 追上 N，最多 5 秒；沒套用＝提醒行、退 0；沒開 state 窗不等。關掉的是根本那扇窗：回來之後才送得出下一道。
2. **aos-agent 的 paused 只認現任行程**（`loop_paused` 拆出 `loop_state`、比 `state.json` 的 `pid` 與表上的 `pid`）：start／wake 剛起、新 loop 還沒寫第一份時，舊行程留下的 paused 不算。
3. **`ctl start`／`ctl wake` 說清楚會不會先暫停**（`comes_back_paused`、`paused_tail`）：暫停中被 stop／sleep 的，輸出尾巴多 `; it was paused when it went down, so it comes back paused: aos-agent ctl resume --target X`。
4. **順手修的相鄰 bug——listen 印成前一題的回答**（`handed_unanswered`）：前一題還在答、這封已收進 history 時，前一題的回答一到，回答數變多，listen 就把它當這封的印出來（試驗場重跑時每次 listen 都慢一題）。改成「history 最後一則 user 在最後一則回答之後＝還在答」也算等。

### 代定（可翻案）

- 等套用的上限 5 秒；等不到只提醒不報錯（身體一步很久時 pause 本來就要等那步做完）。
- 「暫停中被 stop，start 起來先暫停」照舊（11-03 代定，只把它說出來）；沒改成 stop 清掉 paused。
- 不改 daemon（C++）：daemon 寫 stop 時照樣蓋 ctl；沒經 `aos-daemon-ctl`、自己直接寫 ctl 的人仍會撞到同一個競態。

### 驗證（試驗場 scratchpad，假腦 `fake`、信箱模式 daemon＋llm kernel、proto8 impls 全部重建）

- `pause; resume; stop; start; say; listen` 連打 3 輪：3/3 拿到答案（修前 3/3 卡 paused 逾時）。
- 暫停中 stop→start、暫停中 sleep→wake：輸出說會先暫停、`ctl state` 是 paused；resume 後 say／listen 拿到答案。
- pause→resume→sleep→wake：running、拿到答案。
- start 後立刻 pause（3 輪）：都生效。
- 子 loop `SIGSTOP` 時 pause：5 秒後提醒行、退 0；`SIGCONT` 後生效。
- 前一題還在答時 say＋listen：印的是這一封的回答。

### 其他發現（沒修）

- `demo/agent-fsm` 複製到別處就跑不起來：四格用 `__file__/../../bin` 找 `aos_flags`，複製出去找不到（試驗場用捷徑 `bin → proto8/bin` 繞過）。
- 試驗場第一次跑時 impls 的執行檔是 11-04 舊的：重建前 daemon 把退 1 的子項從表上拿掉，跟 docs「出錯結束一律留表」不合；重建後沒再測這條。

### 11-05 晚 邊緣測試

- 上面最後一條重測（impls 18:58 的執行檔）：loop 型退 1 的四種（沒 exec、exec 不在、身體退 1、起來就退）都留表 `stopped`＋`reason`，跟 docs 一致；是舊執行檔的現象，不用改。
- thought 的子（agent-fsm）pause→resume→stop→start→say→listen 連打：拿到答案；pause 本來就暫停的再 pause＝照印 paused、退 0。

### 11-05 夜 第二輪邊緣

照 [demo/docs/02](../../../../templates/docs/02-agent-fsm.md)「複製出 repo」、[03](../../../../kernel/docs/01-llm-kernel.md)「起來」把 llm-kernel、agent-fsm 搬到 repo 外（scratchpad 試驗場，PATH 只放 `install.sh DEST` 裝的捷徑），假腦＋真腦（LM Studio `google/gemma-4-e4b`，試驗場那份 kernel.json 的 `stupid-fast` 改指它）都跑。

- **修了**：`tools/memory/` 的 `_tooldef.json`／`_metainfo.json` 是相對捷徑，`cp -r` 出 repo 就斷 → 第一題 `ToolDefMissing`＋`ToolsBad`、留 `stopped`。文件原本只列三處，改成五處＋一段照抄就對的指令（02）。
- **修了**：`fake_slow` 從自己的位置找 `lib/base/llm_fake`，出 repo＝`EndpointFailed … can't open file`；改成從找到的 `aos_flags.py` 旁找（03、code map 13-demo）。
- **補了**：02 的「掛 daemon」沒寫怎麼起跑 agent 的那台 daemon，補兩行（同 05 件 1）；03 的「改絕對路徑」補 sed 一行與沒改時的錯誤行；`stupid-fast` 註明本機載別的模型就改 `model`。
- `aos-agent` 的 `N queued letters` → `N queued letter(s)`（README 例子同步）。
- 照常：`aos-exec ../agents/bob` 掛上、say／listen、pause→resume→stop→start→say→listen、sleep→wake、暫停中 stop→start（回來仍 paused）、思考中 pause 再 stop 的 listen 提醒、kernel Ctrl-C 重起續答、整包 `cp -a` 搬家再起（表是相對、`def` 指新位置、睡著的那隻開門自己醒、停機時寄的信照答）、直接 `aos-exec --ws W body.json`、沒設 `AOS_LLM_KERNEL`（三層各一行英文）。
- **11-05 晚修了兩件**：`aos-loop` 的 `RunFailed` 原本印 `…/.stack/../../agents/bob/fsm.json` → `Target::label` 照字面整理成最短（`lexically_normal`，只動顯示、不解捷徑）；`aos-agent` 睡著／daemon 沒跑的重起提示原本只寫 `aos-exec <daemon folder>` → 兩種起法都列（`aos-exec <daemon folder> or AOS_STACK=<stack>/ aos-daemon <daemon.json>`；代定、可翻案：stack 看不出當初怎麼起的，所以不猜、兩個都印）。
- **沒修、列給別人**：llm kernel `used.json` 的 `senders` 以寄件人絕對路徑記帳，整包搬家後新舊各一格、`budget.senders` 也是絕對路徑（搬家要人自己改；可翻案：存相對 kernel stack）。劇本假腦 `fake-demo-self`／`spawn`／`memory` 的 `$env AOS_CD`＋`../agent-fsm` 出 repo 不對（03 表上本來就寫「只在 repo 裡對」）。

## 使用者裁定（11-05 夜，排在大重構之後做）

> 剩下都照推薦

- 寄件人額度（`used.json` 的 `senders`、`budget.senders`）**改成相對 kernel stack 記帳**，搬家跟著走。
- repo 的 kernel.json `stupid-fast` **維持 `qwen3-1.7b`**、各台機器自己改；家機正在下載 qwen3-1.7b，下載好後試驗場那份可改回去。
