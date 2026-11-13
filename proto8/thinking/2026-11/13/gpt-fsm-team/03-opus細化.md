# opus 細化：fable 設計對到實際檔案、改了哪幾處、邊緣狀況（線隊 11-13 晚）

← [入口](../gpt-fsm-team.md)｜上一份 [02-fable設計](02-fable設計.md)｜下一份 [04-施工與驗收](04-施工與驗收.md)

> fable 的骨架照收（隊形、兩份定義、拿掉 self／def／events、守門 hook、隊夾、不 commit、BLOCKED 流程）。下面只寫**跟 fable 不同的地方**、**fable 標「待驗」而我讀程式已經驗掉的**、**對到哪些檔**。仍沒驗的標「待驗（乾跑）」。

## 一、fable 的「待驗」讀程式驗掉的

| fable 的待驗 | 讀到的事實 | 出處 | 結論 |
|---|---|---|---|
| `ask` 逾時能不能調 | 能：`timeout_s` 或 `timeout_cycles` | `KB/agents/subagent.json` | 但 `ask` 會卡住 astra 的 act 格，act 格整格上限 30 分（`fsm.json` act `timeout_ms` 1800000），subagent 工具自己沒設 `timeout_ms`。**改用 `say` 交單＋`listen` 每次 `timeout_s: 600`**，沒答完就再 listen |
| 額度能不能對「每隻 sol」設 | `budget.senders` 的 key＝寄件人 stack 相對 kernel stack 的路徑，逐字比對、沒有樣式 | `P/lib/aos/kernel_llm/budget.py:26` | sol 一張單一隻、名字每張不同（見下），**sol 不設每寄件人額度，只靠 `sol-high` 包的總額**；astra 名字固定 `gpt-lead`，可設每寄件人額度 |
| 沙箱在家機起不起得來 | `aos-sandbox` 只有設了 `mem_mb`／`cpu_s`／`procs`／`file_mb`／`files` 才叫 `s6-softlimit`；不設就只用 bwrap（家機有） | `P/cmd/aos-sandbox/bin/aos-sandbox:16,202` | **沙箱設定不寫資源上限**＝家機現在就能用；資源上限改由 `subagent add` 的 `limits`（daemon 的 rlimit）給 |
| rm 母會不會連子一起收 | `ctl rm` 程式裡沒有收子 agent 的邏輯 | `P/cmd/aos-agent/aos_agent/ctl/rm.py` | **不會**。收尾一定要 `ctl ls` 看殘留 |
| hook 程式放哪、相對路徑從哪算 | 定義 `hooks.json` 裡 handler 寫相對路徑＝相對那份 `hooks.json` 所在的夾 | `P/lib/hook_run.py:121` | 守門程式直接放在定義夾裡（`gpt-lead/guard`），handler 寫 `"guard"` |

## 二、跟 fable 不同的地方（opus 改的，理由一句）

1. **sol 不用 `--history task`，用完整 history**：一張單一隻 sol、返工也同一隻，history 本來就短；用 task 模式返工訊息要把線索全帶上，容易漏。fable 的顧慮（history 長）在一單一隻下不存在。
2. **sol 的名字＝`sol-<工單號>`（例 `sol-T03`），rm 不帶 `purge`**：同名同 stack 再 `add` 會**接著舊 history**（`P/cmd/aos-agent/README.md` ctl rm 條），所以名字不能重用；不 purge 是為了留證據給試驗紀錄。代價：每寄件人額度設不了（見上表）。
3. **astra 交單用 `say`＋`listen`，不用 `ask`**（見上表）。
4. **astra 每張工單包在一個 `do_task` 裡**（gadgets 包本來就有）：收完一張就摺成一則摘要，astra 的完整 history 不會隨工單數線性長大；`status.md` 照寫。
5. **astra 的 shell 也進沙箱，而且 repo 唯讀**：fable 只說「astra 的 change 包限寫隊夾」，但 astra 有 shell 就能 `sed -i` 改產品碼，hook 擋不住。沙箱裡 repo 唯讀、只寫得到隊夾，才真的「astra 不寫碼」。連帶：要寫檔的驗收指令（build、會生 `__pycache__` 的測試）astra 跑不了——這題列進待裁（[05](05-待裁與衝突.md) Q3）。
6. **兩份定義都拿掉 `timer` hook；sol 也拿掉 `mail_notify`**（sol 沒有 mailbox 包，提醒只會變成雜訊並把它叫醒）。
7. **守門 hook 預設 `on_error: stop`**（守門程式自己壞了＝agent 停下），寧可停也不要「守門壞了照跑」。
8. **astra 的信寄到隊夾的信箱 `<隊夾>/mailbox/`**，隊長用 `aos-mailbox -s <隊夾> read` 讀；信箱要先建好 `tmp/ new/ cur/`（`mailbox_send` 的 `box` 不替人建）。如果那時頂層就是樹裡的 `repo-aos`，改成 `to: repo-aos`（有 mail_notify 自動提醒）更省事——由施工時看頂層在不在樹裡決定。

## 三、對到實際檔案

**放哪**（[05](05-待裁與衝突.md) Q2 裁）：推薦活樹只做新增——
- 定義：`~/aos-home/defs/gpt-lead/`、`~/aos-home/defs/gpt-worker/`（`agent_def new` 從 `agent-fsm` 複製，或人 `cp -r`）。
- 隊夾：`~/aos-home/teams/<批號>/`（`blueprint.txt`、`tickets/`、`status.md`、`mailbox/{tmp,new,cur}`、`logs/`）。
- llm kernel：活樹 llm kernel 定義的 `kernel.json` `endpoints` 加兩包（活樹 llm kernel 在哪＝`AOS_LLM_KERNEL`，預設 `${AOS_WS}/../llms/stacks/llm`，施工時先 `aos-llm ls` 確認）。

**gpt-worker（sol）定義要改的檔**：

| 檔 | 改成 |
|---|---|
| `tools.json` | `$override` 只留 look、change、delete、shell、gadgets、todo、json、jsonx、index；再加 `"run_python": null`、`"remove": null`、`"do_task": null`、`"shell": {"path": <shell-boxed 那層>}` |
| `llm.json` | `{"model": "sol-high"}` |
| `hooks.json` | 只留一格 `guard`：`{"event": "before_tool", "condition": [寫檔類工具名…, "shell"], "handler": "guard", "on_error": "stop", "timeout_ms": 5000}` |
| `guard`＋`guard.json` | 守門程式與設定：`write_roots: [<repo>]`、`deny_parts: [".git"]`、`shell_deny: [git commit/push/reset/checkout/restore/stash/clean/rebase/merge, sudo, curl, wget]` |
| `fsm.json` | brain argv 加 `--max-tool-calls 80` |
| `subagents.json` | `{"max_subagents": 0}`（沒 subagent 包，雙保險） |
| `system.txt` | 角色、工單怎麼讀、回報格式、「圖紙沒寫就 BLOCKED」、「不 commit」、「只動工單列的檔」（英文，程式輸出規矩） |
| shell 沙箱設定 | 照 `P/cmd/aos-sandbox/examples/shell-boxed/`：`rw: [$AOS_WS, $AOS_STACK]`、`.git` 唯讀（綁定順序待驗）、`net: false`、**不寫** `mem_mb` 等上限 |

**gpt-lead（astra）定義**：同上，差在——

| 檔 | 跟 sol 不同 |
|---|---|
| `tools.json` | 多 mailbox、goal、subagent 包，再加 `"agents_ctl": null`、`"fork": null`；delete 包整包不給；`do_task` 留著 |
| `llm.json` | `{"model": "astra-medium"}` |
| `hooks.json` | `guard`＋`mail_notify` 兩格 |
| `guard.json` | `write_roots: [<隊夾>]`；`subagent` 只放行 `add`（`def` realpath 必須是 gpt-worker、`name` 必須 `sol-` 開頭、不准 `auto_restart`、`envs`、`stack`、`def_json`）、`say`、`listen`、`ls`、`state`、`history`（只准 `ls`）、`stop`、`rm`（不准 `purge`）；其餘 op（`tools`、`llm`、`system`、`hook`、`ask`）攔下 |
| `fsm.json` | `--max-tool-calls 300` |
| `subagents.json` | `{"max_subagents": 1}`（第一輪；Q5 裁開 2 再改） |
| shell 沙箱設定 | `rw: [<隊夾>, $AOS_STACK]`、repo 唯讀 |

**守門程式要擋的寫檔類工具**（參數名施工時逐支對 `_tooldef.json`）：write、edit、copy（目的地）、move（兩端）、mkdir、trash、json_set、json_add、json_del、json_multi_set、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_set、todo 不擋（寫自己 stack）。路徑規則：相對的從 `AOS_WS` 算（hook 的環境有沒有 `AOS_WS` 待驗；沒有就用事件裡的 `stack` 叫 `aos-agent ctl where`）、`realpath` 之後必須在 `write_roots` 底下、路徑元件不能有 `.git`。

**llm kernel 兩包**（放在活樹 llm kernel 的 `kernel.json` `endpoints`）：

```json
"astra-medium": {"exec": "endpoints/litellm", "url": "http://127.0.0.1:4000/v1", "model": "chatgpt-gpt-6-astra-medium", "slots": 1, "cost": "high", "summary": "LiteLLM gpt-6 astra, medium effort: gpt team lead"},
"sol-high":     {"exec": "endpoints/litellm", "url": "http://127.0.0.1:4000/v1", "model": "chatgpt-gpt-6.1-sol-high", "slots": 2, "cost": "high", "summary": "LiteLLM gpt-6.1 sol, high effort: gpt team worker"}
```

不寫 `fixed.temperature`（推理模型可能拒收 temperature，待驗）。`budget`：`packs` 給兩包各自每日 `max_calls`、`senders` 給 `gpt-lead` 的 stack 一條（數字照 fable 第 6 節，Q6 裁）。

## 四、邊緣狀況（fable 沒寫到的）

1. **llm kernel 改了 `kernel.json` 要不要重起才生效**：沒查到「熱讀」，待驗；重起 llm kernel 會讓正在等腦的 agent 的信怎樣，待驗。eca 身（`eca_main`、`repo-aos`）不走 llm kernel，不受影響。
2. **mail_notify 不提醒新起來前就在等的信**（T16）：所以「先起 astra、goal 當第一句」，不要「先寄信再起」。
3. **astra 起來時 history 空、goal 就是題目**：goal 句子要指到 `blueprint.txt`，而且說「工作區乾淨是前提：開工前 `git status` 不乾淨就寄 BLOCKED」。
4. **`git status` 在 `.git` 唯讀時**：它會順手寫 index（refresh），唯讀下可能報錯；system 寫明用 `git --no-optional-locks status`。待驗（乾跑）。
5. **工作區開工前不乾淨**（別條線在改 repo）：gpt 隊的 diff 就混了別人的。開工條件＝`git status` 乾淨，而且這段期間 repo 不讓其他線改（Claude 這邊遵守，資源鎖見 wf resources）。
6. **sol 改了工單外的檔**：守門只限在 repo 裡，擋不住「repo 裡但不在工單清單」；靠 astra 驗收 `git diff --stat` 比對清單，越界退件。fable 想的「每工單檔案擁有權交給 hook 檢查」要 astra 能改 sol 的 hook 設定，等於重開洞，這輪不做。
7. **astra 自己 `goal done` 之後又收到 Claude 的 `say`**（例 BLOCKED 後圖紙改好叫它續做）：goal 已 done 不再提醒，但 `say` 會進 queue 叫醒它；system 寫明「收到續做就 `goal set` 回 active」。
8. **listen 拿到的是 sol 最後一則不帶工具的回答**：sol 途中說了一句沒呼叫工具的話（例「我要開始了」）就會被當成回報、sol 回 idle 空等。system 寫明「中途不要只說話不呼叫工具；回報只在最後一次」；astra 收到不合回報格式的答案時 `say`「繼續」。
9. **astra 被 goal 自動 paused**（連 10 次只動 goal）：表上仍是 running、看門腳本看不出；看門腳本要另看 `aos-agent goal -t gpt-lead get --json` 的 status。
10. **proxy 掛**：wait 格不設期限、只印 stderr 提醒，表上 running。看門腳本除了總時限，加一條「`ctl ls -j` 的 `busy` 連續 15 分鐘是 `think`」就叫醒隊長。
11. **sol 的 history 會進誰的 git**：stack 在 daemon 底下（活樹），不在 repo；不會進 repo 的 git。
12. **哪個 Linux 帳號**：全部同一個使用者跑，沙箱靠 bwrap；不換帳號（換帳號要 root＋s6）。
13. **兩個定義都還留著 `index`、`json` 唯讀工具**：無害、留著。`todo` 寫自己 stack、留著。
14. **astra 叫 `subagent add` 時 `ws` 不給＝跟 astra 同一個（repo）**：守門程式要求 `ws` 不給或等於 repo，免得 astra 把 sol 開在別處。
