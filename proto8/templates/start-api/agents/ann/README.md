Run an aos agent with loop and FSM cells.

用 `cp -r $AOS_HOME/templates/agent-fsm <目的資料夾>` 複製本範本（指回 proto8 的路徑都寫成 `{"$env": "AOS_HOME", …}`、沒有捷徑，抄到哪都能跑，這台要有 `AOS_HOME`），再修改 `llm.json`、`system.txt` 與 `tools.json`，即可建立另一隻 agent；入口、四格運作與完整用法見 [agent-fsm 說明](../docs/02-agent-fsm.md)。

寄之前 `AOS_LLM_KERNEL` 沒設或只有空白＝觸發 `brain_failed` 後以 `LlmKernelMissing` 停下、不記冷卻、保留請求，要帶變數重掛；有設但 kernel 資料夾不在仍照 `SendFailed` 冷卻等待，wait 格等腦回信不設期限：寄出後每滿 10 分鐘在 stderr 印一行 `agent-fsm: warning: no reply from the brain for N minutes to letter <名>: <原因>; still waiting`、照樣等（原因＝信在 kernel 的哪一格：`requests/new/` 還在排隊沒開始、`cur/` kernel 正在跑〔附那封的 `stderr.txt` 路徑〕、或 `AOS_LLM_KERNEL` 沒設／不是資料夾；kernel 沒在跑由同一拍 `aos-llm recv` 那行說，two-machines B10）（提醒到第幾次記在 stack 的 `think/wait_warned.txt`）。

- `think/brain_wait.json`：寄出成功時原子記下信名 `letter` 與 kernel 絕對路徑 `kernel`，供 `listen`／`say` 提示；只採信與 `think/pending.txt` 相同的信，不必刪除。

kernel 回 `BudgetMissing`＝額度拒絕、不停下：先觸發 `brain_failed`（`name = BudgetMissing`、`reason` 原樣帶 kernel 的 `error.msg`，條件只有 `BrainFailed` 的 hook 不再匹配），再記 `cooldown.json`（同代號、30 秒起加倍到 30 分鐘，之後每 30 分鐘）、印一行 `agent-fsm: warning: BudgetMissing <msg>; waiting, the same request is sent again when the cooldown ends`、退 10 留在 wait；冷卻中不寄、到期重寄同一份 `request.json`，不寫 `observed.jsonl`、不加 assistant 訊息。好的回信接進 history 後清冷卻；只有因 endpoint／調整鍵改變而退 11 回 think 重組時，也會先清 `BudgetMissing` 冷卻（清不掉只 warning），其他代號與其他重組原因不清。recv 退非 0 時，其他 kernel 錯誤、stdout 不是 JSON 或沒有 error 物件，仍走原本 `BrainFailed`、退 1；冷卻檢查通過、正要寄出時，若 `priority.deadline` 可解為有限 epoch 秒數或帶時區的 ISO 時間，且已過或 5 秒內到期，wait 只印 warning、不寄出，退 11 回 think 重組，不觸發 `brain_failed`、不改 `request.json`／`cooldown.json`；解不開的 priority 仍交 kernel 判斷（出廠 brain.py 目前不寫 deadline）。
kernel 的 `error` 若多帶結構化欄位（`window`＝`hour`／`day`／`all`、`resets_at`＝下一個視窗起點，ISO 8601 帶時區，`all` 是 null；舊 kernel 只有 `code`／`msg`，行為不變）：`resets_at` 在未來＝冷卻到 `resets_at` ＋ 5 秒（不早於現在＋30 秒，`cooldown.fail_until`，`failures` 照樣加 1）；`resets_at` 剛過不到 60 秒＝現在＋30 秒；解不開、沒帶時區、更舊或沒有＝照上面的間隔表。`window` 是 `all`（永不重置）＝不重試：先觸發 `brain_failed`，再印 `agent-fsm: error: BudgetMissing <msg> (window all: it never resets; raise the budget, then start me again)`、退 1，不記冷卻、`request.json` 留著，加了額度再起＝重寄同一份。`brain_failed` 事件另帶 `error` 欄＝解到的 kernel error 物件（每種 kernel 回錯都有，沒解到就沒有這欄）；範本的 `brain_notify` 讀它：有 `resets_at` 時標題寫「waiting until <本機 HH:MM>」、說明到時自己重試；`all` 時標題寫「stopped」、說明額度不會重置、加額度再起 agent。注意：開了 `auto_restart` 的列碰到 `all` 退 1，daemon 會重起它，重寄的請求立刻又被拒（不耗 token），靠 daemon 的重起退避擋著；subagent 沒有 `auto_restart`。

**預設 11 包、36 支，通用工具四包全開**（tool-packs，使用者「1.預設開到第四包，想要安全就自行限制」；11-14「tools40: a」拿掉四包；11-21 使用者選項框「self 只留兩支」，40 → 36 支，見 [tool-desc-瘦身-1121/04](../../thinking/2026-11/21/tool-desc-瘦身-1121/04-使用者已答.md)）：`tools.json` 的 `"$override"` 疊上 [py/packs](../../py/packs/README.md) 的四份清單——1 看（read、ls、view、stat、grep、glob）、2 改（write、edit、copy、move、mkdir）、3 刪（trash、remove）、4 殼（shell、run_python）——加 json 包（json_get、json_ls、json_search、json_len、json_set、json_add、json_del、json_multi_get、json_multi_set；[json-tools](../../thinking/2026-11/12/json-tools/README.md)），再加五包 agent 工具：小工具 gadgets（peek_clock、peek_now_time、math、do_task）、待辦 todo（todo）、自我管理 self（預設只開 self_tools、self_state；self_llm、self_system、self_history、self_ctl 四支在 `tools.json` 用覆蓋層 `"名": null` 關掉，要用就 `self_tools add`〔path_json 例 `{"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_history"}`〕或改 `tools.json` 把那列拿掉）、信箱 mailbox（mailbox_*）、目標 goal（goal），再加 index 包（index_view：透過 index 看節點、只看不改；[index-tools](../../thinking/2026-11/12/index-tools/README.md)），共 36 支。**選掛四包**（範本不掛）：事件 events（clock_register、self_hook）、子 agent subagent（subagent、agents_ctl、fork）、定義 def（agent_def、tools_def）、jsonx（複雜組 jsonx_get、jsonx_ls、jsonx_search、jsonx_set、jsonx_add、jsonx_del、jsonx_multi_get、jsonx_multi_set，認 `$ref`／`$env`；eca-claude 範本照掛）；要用的定義在做的時候往自己 `tools.json` 的 `"$override"` 加一項（例 `{"$env": "AOS_HOME", "$path": "/lib/packs/subagent.json"}`），不靠 agent 執行中 `self_tools add`（[py/packs](../../py/packs/README.md)）。這些檔案工具不擋工作區外的路徑（相對從 `$AOS_WS` 算、絕對照用），能不能動看 Linux 權限。`aos-tools --file tools.json ls -l` 的 FROM 欄看得出每支來自哪一包。**要收緊**：整包關＝從定義 `tools.json` 的 `$override` 那串拿掉那一包（例四包只留 look 就是唯讀；拿掉 subagent 就不能生子 agent），其他包不受影響；只關這一隻的某幾支＝`aos-agent tools rm shell`、`aos-agent tools rm run_python`（一次一支，寫進這隻自己那份、`"名": null`，定義不動）；`aos-agent tools reset` 回定義。

goal 暫停中來信不自動 resume；只有 agent 自己暫停、history 尾段仍找得到最近的 goal 工具呼叫且之後有新訊息、答完又停下時，idle 才補一次 `[aos] goal: paused …` 提示，讓腦選 resume／done／繼續等，碰到既有 goal 提醒或 summary 就不補，外面或 aos 設的暫停與 goal.json 都不動。

`interfaces.json` 宣告身體、工具與腦設定的位置。`_metainfo.json` 宣告估時 `cost.time_ms` 與 `llm` 資源，未設定逾時。

**context 快滿與 /compact**：新範本預設掛 `context_wrap`（`on_clock`、每 5 秒、`config {"percent": 35, "wrap": false}`），用 `observed.jsonl` 最近一次有效 `think` 的 `usage.prompt_tokens` ÷ kernel 發布的 pack `context` 量用量；hook 的 `config.window` 可蓋過視窗，兩邊都沒有就不觸發。過門檻直接寄 `/compact`，收尾併進摘要；人也能寄 `/compact`：body 先把舊的工具輸出換成一行佔位（最後 3 則、最後一組、短於 300 字的不清，原文進 `history_removed.jsonl`），再叫腦在自己的對話裡寫摘要，那次不帶工具，之前的對話換成一則摘要，沒答的信原文留著，摺掉的原文在 `history_removed.jsonl`，摘要另存 `<stack>/handoff.md`。做到一半也收得到，等工具結果齊了才壓、壓完接著做；可摺的不到 4 則（例：剛壓完又來一封）就不問腦、不摺，當成正常做完：回一句 `compact not needed: …`，信記成答完、不寫警告。改門檻要改 hook 格的 `config.percent`（`self_hook add` 帶不了 config）；關掉用 `self_hook` `{"op":"rm","name":"context_wrap"}`，或 stack 的同名 hook 格寫 `null`（`self_hook` 要選掛 events 包）。`context_wrap --reading <stack>` 可看讀數或讀不到的原因；完整行為、資料格式、限制與舊 agent 換檔順序見 [context 快滿與 /compact](../docs/02-agent-fsm.md#context-快滿與-compact)。


**hook 預設**（[clock-hook](../../thinking/2026-11/11/clock-hook/README.md)）：`loop.json` 的 `on_start`／`on_stop` 叫 `aos-hook fire --agent` 發 `after_start`／`after_stop`（after_stop 帶 `code`、`signal`、`cause`（為什麼停：`stop`／`sleep`／`remove`／`shutdown`／`stuck`／`signal`／`max`／`body_exit`／`error`，舊版 aos-loop 沒給＝null；`cause` 跟表上的 `reason` 不同，`reason` 是給人看的一句話；撞限額沒有獨立的值，看表上的 `limit_hit`；`error` 只是停止的分類，不是錯誤代號；值表見 [aos-loop 01](../../cpp/aos-loop/docs/01-用法.md)））；`hooks.json` 帶一格 `timer`（`on_clock`、每 300000 ms、handler `py/tools/agent/hook_noop` 什麼都不做；每次起來、睡醒會先跑一次，之後每 5 分鐘）；另一格 `mail_notify`（`on_clock`、每 60000 ms＝每 1 分鐘、handler `py/tools/agent/mail_notify`：看自己的信箱，有沒通知過的新信才往 `queue/` 寄一則 `[aos] new_mail: N new letters from A, B. …`、多封合成一句、沒新信不動 history；睡醒時照已通知記錄比：睡前提醒過的不再提、睡著時新到的提醒一次；全新起來（沒有 `notified.json`，且 agent stack 的 `history.jsonl` 不在或是空的）時在等的只記成已知；跑過的 stack（有非空 history）當睡醒，在等的提醒一次；使用者「用on_clock」「預設開」「合成一句」，[mail-notify](../../thinking/2026-11/11/mail-notify.md)；間隔與起來那次：使用者「每 1 分鐘」「只提醒新到的」「睡著時新到的要提」，[backlog-rulings](../../thinking/2026-11/11/backlog-rulings.md)），history 不多任何一則。要定時叫醒腦＝同名換成往 `queue/` 寄信的 handler；不要＝`aos-agent hook -t 名 rm timer`。用法 [aos-agent docs/06](../../py/aos/apps/agent/docs/06-hook.md)。

## 起手範本這一隻：格程式動態連結（11-21）

上面是 agent-fsm 範本的說明原樣；這一隻跟它只差一件事：**四格的程式不在這夾裡，執行時才去 `$AOS_HOME/templates/agent-fsm/` 拿**（動態連結；使用者 11-20 晚「這些範本的.py，感覺都是一些基礎的東西，感覺沒有要覆蓋的話，就應該可以從env:AOS_HOME裏面直接取，這樣ann底下會很乾淨。」、「起手範本確實該改成要借的」）。用的是現成的兩種寫法，跟 `agent.py` 裡 `fsm=std.fsm()` 編出來的一樣：

- `fsm.json`：四格的 `argv` 寫 `["python3", {"$env": "AOS_HOME", "$path": "/templates/agent-fsm/idle.py"}]` 這種（內容跟 `templates/agent-python/fsm.json` 一字不差）。格靠 `AOS_CD` 讀這夾的設定（`interfaces.json`、`llm.json`、`tools.json`、`hooks.json`…），程式放哪不影響。
- `interfaces.json`：`hook_points` 寫 `[{"provider": "aos-loop"}, {"provider": "agent-fsm"}]`，掛得上的點照 aos 帶的那份宣告（`templates/agent-fsm/hook_points.json`），這夾不帶自己的。

所以這夾只剩設定與你會改的東西：`_entry`、`.env`、`body.json`、`loop.json`、`fsm.json`、`interfaces.json`、`llm.json`、`system.txt`、`tools.json`、`hooks.json`、`subagents.json`、`_metainfo.json`、`README.md`。`$AOS_HOME` 那份格程式隨 repo 更新（`templates/` 不經 `install.py`，`git pull` 完就是新的；格 import 的 `$AOS_HOME/lib` 照舊要重跑 `install.py`），這隻下一格就用新的，不用重新複製。

**想改某一格的程式**（例 `wait`）：把那支和它 import 的共用檔一起靜態連結進這夾，再把 `fsm.json` 那一格指過去。

```sh
cp $AOS_HOME/templates/agent-fsm/{wait,atomic_file,cell_common,compact,llm_settings}.py agents/ann/   # 在樹根打
# agents/ann/fsm.json：states.wait.exec.argv 改成 ["python3", "wait.py"]（相對路徑＝這夾），其餘三格不動
```

`fsm.json` 每一格都重讀，存檔後下一格就照新的跑，不用重起（11-21 暫存樹實測：指過去、指回來都不重起就生效）。

- 共用檔要一起靜態連結進來，因為格是照自己所在的資料夾找 `cell_common` 這些：idle 用 `atomic_file`、`cell_common`、`compact`；think（`brain.py`）用 `cell_common`、`compact`、`llm_settings`；wait 用 `atomic_file`、`cell_common`、`compact`、`llm_settings`；act 用 `cell_common`。
- 靜態連結進來的就不再跟著 `$AOS_HOME` 更新；其餘的格照舊用 `$AOS_HOME` 那份。兩邊的共用檔（例 `compact.py`）版本可能岔開，要整套自己管就四格都靜態連結進來、都指過來（＝跟 agent-fsm 範本一樣整份帶著）。
- 改了格、多發了新的 hook 點：把 `$AOS_HOME/templates/agent-fsm/hook_points.json` 也靜態連結進來改，`interfaces.json` 的 `{"provider": "agent-fsm"}` 換成 `"hook_points.json"`。
- 改完在樹根跑 `aos-hook check --agent agents/ann` 看接線對不對（11-21 實測：`ok: 11 points from 2 declarations`）。
