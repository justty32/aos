# fsm 範本

← [README](README.md)

agent-fsm 範本（templates/agent-fsm）本身與它身上的工具、guard 的意見；eca-claude 範本（templates/eca-claude）跟 agent-fsm 對不齊、或範本預設值的意見也放這裡。

## guard 看指令字面，連唯讀查詢也擋

- 主題：fsm 範本
- 哪裡：agent-fsm 的 shell 工具前面的 [aos] guard（擋禁用字樣的指令）。guard 的程式不在 proto8 裡，整理時沒找到出處檔。
- 現象：guard 比對整條指令字面，引號裡的字串、參數也算。實例：`grep "rm accepted"` 中了 `\brm\s`；grep 函式名 `kill_group` 中了 `kill`；`pgrep -u "$USER" -af aos-daemon` 中了 `aos-*`。被擋後 sol 照規矩拒絕改寫繞開，所以這幾類查詢 sol 永遠做不了，要隊長代跑。
- 建議：
  1. 只比對指令詞的位置（管線各段第一個字、`xargs`／`-exec` 後那個），不比引號裡的字串和參數。
  2. 或給唯讀指令（grep、rg、cat、sed -n、pgrep、ps）白名單：整條管線都是它們、沒有重導寫檔就放行。
  3. 擋下的訊息寫明「字面誤判也算數，請把查詢交給隊長代跑」，不要只回 BLOCKED。
- 痛的程度：拖慢（四隻卡住一輪，其中兩隻要隊長代跑）
- 提出者與日期：ok-misc 2026-11-14
- 出處：wf/temp/ok-misc/aos-advice/guard-看字面擋唯讀查詢.md；misc-1114 暫存樹 T11、T14、T15 的 sol 回報
- 狀態：已解（ok-astra，313ce20ec）。guard 實際在活樹 `~/aos-home/defs/shared/guard`（不在 proto8）；新版放 `wf/public/tools/fsm-guard/`：shell 指令整條都是單純唯讀（rg、grep、cat、`sed -n 'N,Mp'`、pgrep…，沒有替換、寫檔重導）就跳過 deny 字樣，其餘照舊；Argon 審三輪、34 個測試。等換樹換掉活樹的 guard 才生效。

## 漏設 AOS_LLM_KERNEL 時 agent-fsm 靜靜卡住

- 主題：fsm 範本
- 哪裡：`subagent add`／`agents_ctl add` 起 agent-fsm（大腦走 LLM kernel）；`templates/agent-fsm/wait.py`；`subagent ls` 的狀態。
- 現象：起 agent-fsm 時忘了在 envs 帶 `AOS_LLM_KERNEL`。say 任務過去約 15 分鐘沒回音，`subagent ls` 一直是 running；翻 stack 的 stderr.txt 才看到每次叫腦都 LlmKernelMissing。
- 建議：add 時偵測到大腦要 kernel 而環境沒有就拒絕或警告；或大腦連續失敗 N 次時在狀態／REASON 欄顯示；至少在知識庫 aos/agents/subagent 寫明要帶 AOS_LLM_KERNEL。
- 痛的程度：拖慢（白等 15 分鐘加排查）
- 提出者與日期：ok-limits 2026-11-14
- 出處：wf/temp/ok-limits/aos-advice/subagent-llm-kernel-missing-silent.md；wf/temp/ok-limits/notes/naming.md
- 狀態：已解（1f61dfbb1：AOS_LLM_KERNEL 沒設或空白時，寄信前就 LlmKernelMissing 退 1、停下，不再空轉；知識庫 aos/agents/subagent 同筆補上「agent-fsm 要 AOS_LLM_KERNEL、沒有就馬上停」）。add 時先擋的做法沒做。活樹的知識庫複本要等換樹。

## 冷卻後重寄的請求可能已過 deadline，agent 還是會停

- 主題：fsm 範本
- 哪裡：`templates/agent-fsm/wait.py`（冷卻到期重寄 `think/request.json`）；llm kernel 的 `DeadlineBad`。
- 現象：AK17 之後，額度被拒的 agent 留在 wait，冷卻完重寄同一份 request.json。冷卻最長 30 分鐘一輪，若請求帶的 deadline 已過，kernel 回 `DeadlineBad`，走一般 BrainFailed：退 1、loop 停下，又回到 AK17 想避免的「停著沒人知道」。
- 建議：擇一。wait.py 重寄前看到 deadline 已過，就退 11 回 think 重組；或 kernel 的 DeadlineBad 也走「警告＋冷卻＋重組」。
- 痛的程度：小不便（要先被拒很久才會撞到）
- 提出者與日期：ok-astra 2026-11-14
- 出處：wf/temp/ok-astra/aos-advice/resend-past-deadline-stops.md；proto8/thinking/2026-11/14/astra-kernel-1114.md AK17 節；Argon 審稿 A6
- 提出者與日期（狀態更新）：ok-fsm 2026-11-14
- 出處（狀態更新）：wf/temp/ok-fsm/aos-advice/已解-冷卻後重寄過deadline.md；proto8/thinking/2026-11/14/ok-fsm-1114.md；ok-fsm 工單 T21
- 狀態：已解（3b02a41c4，ok-fsm 11-14；要換樹才進活樹）。照建議的第一案：wait.py 在冷卻檢查通過之後、寄出之前讀 `request.json` 的 `priority.deadline`（數字＝epoch 秒；字串＝帶時區的 ISO 8601），已過或 5 秒內到期就印一行 warning、退 11 回 think 重組，不寄；不觸發 brain_failed、不寫冷卻、不動 request.json；解不開的 priority 照寄、交 kernel 判。出廠 brain.py 每次重寫 request.json 而且不寫 deadline，重組後的請求不會帶著過期的 deadline 空轉。測試 `templates/tests/agent-fsm/test_cooldown.py` 新增 epoch／ISO 過期、5 秒邊界等案例，agent-fsm 整夾 148 支全過。沒做：第二案（kernel 的 DeadlineBad 也走冷卻重組），DeadlineBad 仍走一般 BrainFailed。整理時查：3b02a41c4 只改 wait.py 與 test_cooldown.py，wait.py 檔頭第 22、34 行寫了這條。

## 蒐集用 sol 的工具包寫不了純文字檔、也沒有 shell，交件卡住

- 主題：fsm 範本
- 哪裡：照 07 掛蒐集用 sol 的工具定義：`tools.json` 用 `$override` 只放 `lib/packs/look.json`、`gadgets.json`、`json.json`、`index.json`。
- 現象：ok-view-sol-6～9 四隻同時蒐集，三隻卡在最後一步：「目前工具只有 JSON 寫入，沒有純文字 write/edit；無法正確建立 Markdown。請提供文字寫入工具。」sol-7 的題目要查版本（`node --version`），沒有 shell，就讀檔一路翻 `~/.npm/_cacache` 和 Node 原始碼，117 步沒停；補的「停下來，直接交」排在 queue 裡讀不到，只好 sleep 收掉。補救是叫它們把全文放進最後回答，再由隊長從 `aos-agent history ls -j` 取出存檔（交出 18～61 KB，品質不錯），代價是多一輪，隊長還要自己寫解析腳本。
- 建議：
  1. `lib/packs/` 加一個只能寫進自己工作區的文字寫檔 pack（例 `ws-write.json`：路徑限 `$AOS_WS` 底下、大小有上限）。現有 `change.json` 的 write 不限路徑，要自己掛 before_tool hook 才能限（見 [wf/public recipes「唯讀蒐集的隊員怎麼擋寫檔」](../public/recipes.md)）。
  2. 07 寫明：蒐集任務書要嘛要求「全文放在回答裡」，要嘛先掛寫檔 pack；並給一個取最後回答存檔的現成指令（例 `aos-agent history -t NAME last --text > FILE`）。
  3. 07 提醒：sol 沒有 shell，查版本、查環境的事派工的人自己跑，或給唯讀指令白名單工具。
- 痛的程度：拖慢（每隻多一輪，sol-7 白跑約 15 分鐘）
- 提出者與日期：ok-view 2026-11-14
- 出處：wf/temp/ok-view/aos-advice/agent-fsm-sol-沒有寫文字檔工具.md；wf/temp/ok-view/sol-{6,8,9}/（交件全文）；stack ok-view-sol-{6,7,8,9}
- 提出者與日期（狀態更新）：ok-fsm 2026-11-14
- 出處（狀態更新）：wf/temp/ok-fsm/aos-advice/已解-蒐集員寫不了純文字檔.md；proto8/thinking/2026-11/14/ok-fsm-1114.md；ok-fsm 工單 T23
- 提出者與日期（剩下那半，第十一批併入）：ok-fsm 2026-11-14
- 出處（剩下那半）：wf/temp/ok-fsm/aos-advice/取隊員最後回答沒有現成指令.md
- 狀態：未處理（部分已解）。
  - 建議 1 已解（38271da3b）：新包 `proto8/lib/packs/ws-write.json`，一支工具 `ws_write {path, content, mode}`（`proto8/lib/base/ws_write/`）。mode 有 create（預設，已有就拒）、append、replace（要已存在）；路徑解完捷徑必須落在 `$AOS_WS` 裡，`$AOS_STACK`、`$AOS_CD` 底下也拒；一次上限 262144 bytes、不刪檔。選掛，兩個範本都不掛，要用的定義在 tools.json 的 `$override` 加 `lib/packs/ws-write.json`。測試 `proto8/lib/tests/test_ws_write.py` 19 支。要換樹才進活樹。後續 c2eced25c（ok-fsm 11-14，head-tools 審稿提出）：ws_write 也擋鄰居的 stack 與任何 `.stack` 夾，兩種都回 PathBad：放 `$AOS_STACK` 的那個夾底下全部（各 agent 的 stack 都在那裡），和路徑裡有一節叫 `.stack` 的。理由是活樹的 `ws/.stack` 就在工作區底下，只擋自己的 stack 仍寫得到鄰居的 queue、tools.json。已知限制：工作區本身在某個 `.stack` 或放 stack 的夾裡時會全部被擋（跟 guard 的 write_guard 同一個限制）。測試增為 20 支。同樣要換樹才進活樹。
  - 建議 2、3 已寫進 [aos-teams/07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)（「蒐集員的交件要先想好怎麼落地」「sol 沒有 shell」兩條；頂層 11-14 加，還沒 commit）。
  - 沒做：取最後回答的現成指令（`aos-agent history last`）。目前用 `subagent listen` 的 `last: 1`（印在工具結果裡，長的會被截、還混著問句），或 `aos-agent history -t <名字> ls -j` 整份拿回來自己寫腳本取（ok-view 就這樣做）。ok-fsm 的建議：`aos-agent history -t NAME last [--text] [--role assistant]`，預設印最後一則沒有 tool_calls 的 assistant，`--text` 只印文字，方便 `> FILE`。痛的程度：小不便。整理時查：`cmd/aos-agent/aos_agent/history.py` 只有 ls、rm、summarize、set，沒有 last。

## agent-fsm 的 system 文字不能分層、不能引用，各線整份抄

- 主題：fsm 範本
- 哪裡：`templates/agent-fsm/brain.py` 讀 system 檔（約 110～113、163 行）；`agent_def`；`subagent add`。
- 現象：system 檔每次問腦整份讀、整份送，不支援 include、`$ref` 或變數；stack 那份在就整份取代定義那份。`ctl add`／`subagent add` 沒有 `--system`（只能事後 `aos-agent system set`）。11-14 各線 `wf/temp/*/defs/*/system.txt` 有 13 份，9 份幾乎逐字相同、從 ok-pilot 抄來；規矩一改，13 份都不會跟著改。
- 建議：interfaces.json 的 `system` 可以是檔案清單、按順序串起來，或支援 `$ref`，讓「通用層＋角色層」共用一份；或讓 `subagent add` 收 `system` 參數。細節等 onboard-1114 計劃定稿。
- 痛的程度：拖慢
- 提出者與日期：ok-onboard 2026-11-14
- 出處：wf/temp/ok-onboard/aos-advice/system-text-no-layers.md；proto8/thinking/2026-11/14/onboard-1114/01-備料.md §1、§2
- 狀態：已排入（ok-onboard，計劃未定稿）

## goal 是 paused 時來了信，agent 忘了 resume 就無聲停住

- 主題：fsm 範本
- 哪裡：`templates/agent-fsm/idle.py` 的 goal_turn（約 201～243 行）、`lib/agent/goal_state.py`。
- 現象：goal 只在 active 時提醒（goal_turn 看到 status 不是 active 就回 False）。agent 等回信時照規矩 `goal pause`；回信來了，idle 收進信，腦回一段純文字但忘了先 `goal resume`。goal 仍是 paused、不再提醒，agent 就停住，外面看不出是做完還是忘了。這是 Argon 審 onboard-1114 時指出的，**還沒實測重現**。
- 建議：idle 收到新信、goal 是 paused 時自動改回 active，並在 history 加一則 `[aos] goal: resumed because a letter came`；或至少在這封信之後提醒一次「goal is paused; resume or done」。
- 痛的程度：小不便（目前沒人踩到，但模板要教 agent pause，之後一定會遇到）
- 提出者與日期：ok-onboard 2026-11-14
- 出處：wf/temp/ok-onboard/aos-advice/goal-paused-letter-resume.md；proto8/thinking/2026-11/14/onboard-1114/05-採納表.md A6
- 提出者與日期（狀態更新）：ok-fsm 2026-11-14
- 出處（狀態更新）：wf/temp/ok-fsm/aos-advice/已解-goal暫停後來信.md；proto8/thinking/2026-11/14/ok-fsm-1114.md；ok-fsm 工單 T22
- 狀態：已解（38271da3b；要換樹才進活樹）。
  - 沒採「自動 resume」，改成「提醒一次」：goal 是 agent 自己暫停的（goal.json 的 updated_by 是 agent），暫停後有新訊息進來、腦回純文字停下時，idle 往 history 接一則 `[aos] goal: paused (理由). A message came after you paused. …`，讓腦自己決定 resume、done 或繼續等。每次暫停只一則，goal.json 不寫（`idle.py` 的 goal_turn()、`goal_state.py` 的 paused_note()／paused_due()）。
  - 為什麼不自動 resume：暫停也可能是外面的人下的（updated_by outside），或到提醒上限被 aos 停的；來一封信就自動恢復，會蓋掉這兩種。11-11 goal 的裁定裡 pause 是 agent 自己的宣告。原本「暫停中來信不 resume、不提醒」是 test_goal.py 斷言過的設計，不是漏掉的 bug。
  - 測試：test_goal.py 原 13 支不改、新增 14 支；agent-fsm 整夾 139 支全過。
  - 沒做：eca（aos-eca-turn）那邊沒有這個提醒；history 被摺疊、找不到暫停那次 goal 呼叫時不提醒（保守）；知識庫 `aos/tools/goal.json` 的 pause 那句（「A letter does not resume it」）還沒補提醒的事。

## agent-fsm 範本預設掛 55 支工具，工具說明是每次問腦最大的固定成本

- 主題：fsm 範本
- 哪裡：`proto8/templates/agent-fsm/tools.json`（`$override` 疊 15 包）、各工具的 `_tooldef.json`。
- 現象：
  - 11-14 照活樹 lib 的 `_tooldef.json` 加總：範本原樣 55 支、90,723 字元；只留蒐集員要的 24 支是 31,215 字元。
  - system 才約 2～3 千字元，所以每次問腦送出去的固定內容，大部分是工具說明。
  - 一隻 sol 一張單約 40 次問腦，光工具說明就約 360 萬字元。
- 建議（擇一或都做）：
  1. 範本預設只掛常用的包，其餘包寫進 README，要的人自己加。
  2. 把 tooldef 的 description 分成短版（送給腦）和長版（給 `self_tools get` 看）。
  3. 至少在知識庫寫明「每多掛一包，每次問腦多送幾千字元」。
- 痛的程度：拖慢（燒額度）
- 提出者與日期：ok-onboard 2026-11-14
- 出處：wf/temp/ok-onboard/aos-advice/fsm-template-tool-descriptions-cost.md；proto8/thinking/2026-11/14/onboard-1114.md「P0 結果」；wf/workflows/dispatch/kits/README.md
- 狀態：未處理（部分已解）。範本 tools.json 仍是 15 包 55 支（最後一次改是 2e1e69de2 加 jsonx 包）。部分已解：產品版 kits 已進 `proto8/templates/kits/`（3ed649b09，含 gather 看包與 review 變體），知識庫新增 `aos/kits.json`（fdfbc5515），要少掛工具的照 kits 蓋就好；範本預設本身沒精簡、tooldef 沒分長短版（第九批整理補，依 ok-kb 清理清單）。繞法：派蒐集員照 [wf/workflows/dispatch/kits](../workflows/dispatch/kits/README.md) 的 gather 只掛 24 支（見 [wf/public recipes「派蒐集員或審稿員」](../public/recipes.md)）。
- 相關：本檔「蒐集用 sol 的工具包寫不了純文字檔」，同樣是「範本該掛哪些包」的問題，精簡時要留文字寫檔。

## sol 的可寫範圍寫在兩份清單裡，換工作區要兩邊都改

- 主題：fsm 範本
- 哪裡：照 07 掛的 agent-fsm sol 定義：`guard.json` 的 `write_roots`（檔案工具的寫檔守門，見 [wf/public/tools/fsm-guard](../public/tools/fsm-guard/README.md)）；`shell-boxed/_metainfo.json` 的 `sandbox.ro`／`sandbox.rw`（shell 的 bwrap 沙箱，決定看得到哪裡、能寫哪裡）。兩份彼此無關。
- 現象：另開一棵新暫存樹（`src2`）派任務，五隻 sol 全部回 BLOCKED：
  - 檔案工具讀得到 src2、寫不進去：「guard 拒絕：src2 不在允許寫入範圍（目前只有 src/proto8、src/wf）」。
  - shell 連看都看不到：`cd …/src2` 回 "No such file or directory"，還待在舊的 src。
  - 隊長手改兩份 JSON、各加一樣的三個路徑，sol 才能做事。
- 建議：
  1. 兩邊讀同一份清單：定義裡放一個 `roots.json {"ro": [...], "rw": [...]}`，guard 和 shell-boxed 都用 `$ref` 指向它。
  2. 或預設「`$AOS_WS` 底下的 proto8、wf 可寫，其餘唯讀」，另加 `extra_roots` 鍵；換工作區（ctl set-def，或 rm 再 add 改 -w）時範圍自己跟著走。
  3. 擋下時的訊息附設定檔路徑（例「not in write_roots of <def>/guard.json」），隊長不用猜要改哪份。
- 痛的程度：拖慢（五隻 sol 同時 BLOCKED 一輪）
- 提出者與日期：ok-misc 2026-11-14
- 出處：wf/temp/ok-misc/aos-advice/sol可寫範圍要改兩份清單.md；misc-1114 暫存樹的 sol 定義 defs/sol-worker
- 狀態：已排入（ok-fsm）。整理時查：還沒改。fsm-guard 擋下的訊息只列 write_roots 的值、沒寫設定檔路徑；repo 裡沒有 roots.json 或 extra_roots。
- 相關：本檔「guard 看指令字面，連唯讀查詢也擋」，同一支 guard。

## before_tool 擋下工具時，tool_result 標 is_error:false，模型分不出是被擋

- 主題：fsm 範本（hook 的行為 eca 和 agent-fsm 都有，建議要兩邊對齊，所以放這裡）
- 哪裡：before_tool hook 退 10 時，aos-mcp 交回 claude CLI 的 tool_result（`proto8/cmd/aos-mcp/bin/aos-mcp` 約 260 行）；agent-fsm `templates/agent-fsm/act.py` 約 190 行；知識庫 `aos/me/self_hook`；`proto8/thinking/2026-11/10/self-family/hook/02-施工結果.md`。
- 現象：ok-pilot 11-14 在暫存樹用真 haiku eca 驗 hook，掛一個 before_tool hook（記一行、印一行、退 10），請模型叫一次 peek_now_time。
  - 工具確實沒跑，after_tool 也沒觸發。模型拿到 hook 的 stdout，照實回「The tool returned exactly: "blocked by ok-pilot acceptance hook" …」。
  - 但小格的 `claude/live.jsonl` 裡，這次 tool_result 是 `"is_error":false`。從 CLI 和模型看，「被擋」和「工具正常回一句話」分不出來，只能靠 hook 自己印清楚。
- 建議：
  1. 推薦：被擋時標 `is_error:true`，內容統一成固定前綴，例如 `HookBlocked <hook 名>: <hook 的 stdout>`。模型和讀紀錄的人一眼看出是被擋，不會把 hook 的字當成工具結果。
  2. 不改的話，至少在知識庫 hooks 頁寫明「被擋時回的是 hook 的 stdout、標為非錯誤；要讓模型知道被擋，hook 自己要印清楚」。
  3. agent-fsm 被擋時怎麼標，一起對齊。
- 痛的程度：小不便（hook 印得清楚就沒事，但模型可能把擋下的訊息當成真結果）
- 提出者與日期：ok-pilot 2026-11-14
- 出處：wf/temp/ok-pilot/aos-advice/before_tool擋下時tool_result標is_error-false.md；wf/temp/ok-pilot/hook-eca/report.md「附帶觀察」、hk-events.jsonl
- 狀態：已解（知識庫，1e67c58ff，ok-kb 11-14）：`aos/me/self_hook.json#/answer` 補一句「被擋的呼叫不標成錯誤，結果看起來像正常回答，hook 要自己印清楚它擋了」（建議 2）。程式不改：建議 1 的 `is_error:true` 沒做，建議 3 的兩邊對齊現況本來就一致。活樹待換樹。整理時查：這是現行設計，不是漏做。aos-mcp 的檔頭、`--help` 和 `cmd/aos-mcp/README.md` 都寫了「攔下＝結果文字是 hook stdout（空就 `[aos] hook: tool NAME blocked by hook HOOK.`），不算 isError」。投稿說「文件沒寫」只對知識庫：`aos/me/self_hook` 只寫「you get the hook's stdout as the result」，沒說算不算錯。agent-fsm act.py 一樣把 hook stdout 當 tool 訊息，沒有錯誤標記。

## sol 讀完必讀後只回一句「我會照做」就結束回合，要催一次才動手

- 主題：fsm 範本
- 哪裡：agent-fsm、腦 sol-high（LiteLLM chatgpt-gpt-6.1-sol）；定義 wf/temp/ok-fsm/defs/sol（look、change、json 三包，沒有 shell）；通用層 system `wf/workflows/dispatch/kits/general.A.txt`（範本複本在 `proto8/templates/kits/general.A.txt`）。
- 現象：
  - ok-fsm 11-14 派兩隻 sol 各做一張工單（T22、T23）。system 和任務信都寫了「讀完必讀，同一回合就動手；沒有工具呼叫的回答會結束回合」。
  - 兩隻都一樣：讀完必讀和工單（約 20 則訊息、5 次問腦）後回一段「已讀完，會照圖紙做 …」，沒有任何寫檔的工具呼叫，回合結束、停在 idle。
  - 各催一句「你只說了要做、還沒改任何檔，現在動手」才開始改檔，之後都正常做完。llm-gpt 排隊久時，這一來一回各多等約 8～10 分鐘。
  - 重複出現：[wf/public/sol-crew.md](../public/sol-crew.md) 已記過 ok-astra 的 sol-3 同樣的事（第一回合只列重點表就結束，催一次才動手）。
- 建議（擇一或都做）：
  1. 範本層：goal 是 active 時，idle 本來就會提醒它繼續。派工時隊長先替它 `goal set`（或在 kits 的隊長卡寫成固定步驟），它說完「我會照做」停下時 aos 自己催，不用隊長盯。不用改程式，只改隊長卡。
  2. 通用層 system（kits 的 general.A.txt）把那句移到最後一段、改成更直接的話，例如「Never end a turn with a plan. Your first reply after reading must contain a tool call that changes a file.」
  3. 知識庫或 sol-crew 寫明：第一輪讀檔多的工單，隊長在 say 之後排一個 5 分鐘的鬧鐘，專門看「有沒有改出第一個檔」。
- 痛的程度：拖慢
- 提出者與日期：ok-fsm 2026-11-14
- 出處：wf/temp/ok-fsm/aos-advice/sol第一輪只回會照做就停.md；proto8/thinking/2026-11/14/ok-fsm-1114.md「13:56 驗收與交件」；stack ok-fsm-sol-1、ok-fsm-sol-2 的 history（第一輪最後一則）
- 狀態：未處理。整理時查：兩份 general.A.txt 都沒有「不要用計畫結束回合」這類句子；sol-crew.md 只寫了「寫明讀完同一回合動手」，這次證明光寫還不夠。
- 相關：本檔「goal 是 paused 時來了信」（同一套 goal 提醒）。

## llm_settings.py 的註解還說 pack 的 fixed 欄位「照舊蓋過」，實際是整個請求被拒

- 主題：fsm 範本
- 哪裡：`proto8/templates/agent-fsm/llm_settings.py` 檔頭註解第 8 行。
- 現象：註解寫「kernel 端 endpoint 包的 fixed 欄位照舊蓋過這裡（llm_http：request 先、fixed 蓋上）」。現在的 llm kernel 不是蓋過：請求帶到被包釘死的鍵，`fixed_clash` 回原因，`pick()` 丟 `RequestBad … is fixed by endpoint <包>`（`proto8/lib/aos/kernel_llm/packs.py` 第 279、313 行）。照註解以為「設了也只是沒作用」的人，會讓那隻 agent 每次問腦都被拒。
- 建議：註解改成「帶到 fixed 的鍵＝kernel 回 RequestBad，別設」。再想一步：agent-fsm 送出前就把跟包的 fixed 相衝的鍵擋下、說清楚，不等 kernel 拒。知識庫 `aos/me/self_llm.json` 已在 f1ef04ba0 改成現況。
- 痛的程度：小不便
- 提出者與日期：ok-kb 2026-11-14（轉 head-front 派的獨立審稿員的發現）
- 出處：wf/temp/ok-kb/aos-advice/llm_settings註解說fixed欄位會蓋過已過時.md；head-front 審稿員 11-14 核 f1ef04ba0 時讀碼發現，沒實跑；proto8/thinking/2026-11/14/kb-1114.md
- 狀態：未處理。整理時查：註解仍是「照舊蓋過」，`packs.py` 的 `fixed_clash` 與 RequestBad 對過。

## eca（aos-eca-turn）沒有「goal 暫停後來信提醒一次」，只有 agent-fsm 有

- 主題：fsm 範本（eca 身；跟本檔「goal 是 paused 時來了信」那條是同一件事的另一半）
- 哪裡：`proto8/cmd/aos-eca/bin/aos-eca-turn` 的 goal 那段（檔頭 ⑬）；agent-fsm 的對應處是 `proto8/templates/agent-fsm/idle.py` 的 goal_turn()；共用判斷在 `proto8/lib/agent/goal_state.py` 的 paused_due()、paused_note()。
- 現象：38271da3b 起，agent-fsm 的 agent 自己暫停 goal、之後來了訊息、答完又停下時，會收到一則 `[aos] goal: paused …`。eca 身沒有這一則，還是「暫停中不再提醒」，忘了 resume 就停住。ok-fsm 這次沒做，是因為不在它的任務書範圍；也還沒實測 eca 會不會真的踩到。
- 建議：aos-eca-turn 在 queue 空、goal 是 agent 自己暫停的時候，用同一對函式判斷、丟同一則提示。注意 eca 的工具來回在 CLI 自己的對話檔裡、history 沒有（goal_state.transcript_calls 那條路），paused_due() 現在只看 history，要補一個看對話檔的版本。
- 痛的程度：小不便（還沒人踩到）
- 提出者與日期：ok-fsm 2026-11-14
- 出處：wf/temp/ok-fsm/aos-advice/eca沒有goal暫停後來信的提醒.md；proto8/thinking/2026-11/14/ok-fsm-1114.md「第 2 條的設計決定」；commit 38271da3b
- 狀態：未處理。整理時查：paused_due／paused_note 只有 goal_state.py、agent-fsm 的 idle.py 和 test_goal.py 在用，aos-eca-turn 沒有。
- 相關：本檔「goal 是 paused 時來了信」（agent-fsm 那半，已解）。

## eca-claude 範本在 dontAsk 下沒放行 Read／Glob／Grep，讀工作區外的檔被拒，Bash cat 卻可以

- 主題：fsm 範本（eca-claude 範本的預設值）
- 哪裡：`proto8/templates/eca-claude/cli.json`：`--tools Read,Write,Edit,Glob,Grep,Bash,Agent,Skill`、`--permission-mode dontAsk`、`--allowedTools Write,Edit,Bash`（e9623e525 定，2ab15e1c7 加 Agent、Skill）。
- 現象：
  - skyrim 那邊的 eca（skyrim-agent-agentctl）照這個範本開的定義，用 Read、Grep 讀工作區外的必讀清單被拒，只能改用 Bash `cat`。
  - 原因：dontAsk 模式下，沒列進 `--allowedTools` 的工具只在 Claude Code 自己的工作資料夾裡自動放行，出了工作區就拒。範本放行了 Write、Edit、Bash（寫檔和 shell 哪裡都行），唯讀的 Read、Glob、Grep 反而出不了工作區，鬆緊顛倒；agent 只好繞去 Bash，結果更難守。
  - 整理時另有一個佐證：本批整理的 Claude 子 agent 也在 don't ask 模式，用 Read 讀 repo 外那份筆記同樣被拒，改用 shell 才讀到。
- 建議：範本 `--allowedTools` 加上 `Read,Glob,Grep`（skyrim 那邊在自己四份 eca 定義這樣改，d98eb1b6，在 skyrim 的 repo；工人實測三支都讀得到）。範本預設要放多寬是使用者的事（11-12「放寬claude」時代定成現在這樣），改之前先問。至少在 eca-claude 範本 README 或知識庫寫明「dontAsk 下 Read／Glob／Grep 只在工作區裡自動放行」。
- 痛的程度：小不便（有 Bash cat 可繞）
- 提出者與日期：skyrim-agent-agentctl 2026-11-14（skyrim-agent 轉來）
- 出處：`~/repo/moddings/skyrim/agentctl/tmp/aos/skyrim-agent-agentctl/notes.md`「等 skyrim-agent 定的 4 件」第 1 件與「第三封信」第 1 項；skyrim repo commit d98eb1b6
- 狀態：未處理。整理時查：aos 這邊的範本 cli.json 仍是 `--allowedTools Write,Edit,Bash`，最後一次改是 2ab15e1c7。

## eca-claude 範本沒關 Claude Code 的自動記憶，工作區在別的 git repo 底下就讀寫那個 repo 的記憶

- 主題：fsm 範本（eca-claude 範本的預設值）
- 哪裡：`proto8/templates/eca-claude/cli.json`（沒有 `settings` 鍵）；`lib/agent/cli_cfg.py` 的 `cli_settings` 與 `cli_mcp.settings_argv`（把 cli.json 的 `settings` 併進 aos 自己那個 `--settings`）。
- 現象：
  - Claude Code 的記憶夾照 cwd 的 `git rev-parse --show-toplevel` 算。
  - eca 的工作區若在某個 repo 的子目錄（skyrim 那邊是 repo 底下的 `tmp/…`），就會載入那個 repo 的主記憶（那次是 129 檔），系統提示也會叫它寫進去：隊員讀到別隊的舊記憶，甚至寫髒它。
  - 工作區在 submodule 根時，另起一份新的空記憶夾。
  - 實測：cli.json 加 `"settings": {"autoMemoryEnabled": false}`，aos 會併進 `--settings`，記憶那段就從系統提示消失（transcript 裡 `persistent file-based memory` 0 筆，對照組 3 筆）。
- 建議：
  1. 範本 cli.json 預設帶 `autoMemoryEnabled: false`，要記憶的隊伍自己打開。
  2. 至少在知識庫的 eca 頁寫一句「記憶夾跟著 git 根走，工作區放哪就吃到誰的記憶」。
- 痛的程度：拖慢（不擋路，但會讀到、寫髒別隊的記憶）
- 提出者與日期：skyrim-agent 2026-11-14（skyrim-agent-opus-1 整理投稿）
- 出處：`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/top/aos-advice/skyrim-1114.md`「eca-claude 範本預設不關 Claude 自動記憶」；`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/opus-3/out/facts.md` 第 5、6 節；`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/p1/entry-check.md`（離線驗證）
- 狀態：未處理。整理時查：範本 cli.json 沒有 `settings` 鍵，proto8 的範本、lib、knowledge 裡都沒有 `autoMemory` 字樣。範本預設放多寬、關不關記憶，跟上一條一樣是使用者的事，改之前先問。
- 相關：本檔「eca-claude 範本在 dontAsk 下沒放行 Read／Glob／Grep」（同一個範本的預設值，同一隊提出；兩件設定不同，分開記）。做法另收在 [wf/public 定義與換定義](../public/定義與換定義.md)。

## fsm 隊員沒有 user_send／user_verify，問使用者只能經主導轉

- 主題：fsm 範本（工具包）
- 哪裡：`proto8/lib/packs/*.json`；agent-fsm 範本與 kits 的 gather。`proto8/lib/agent/user_send`、`user_verify` 兩支工具在，但沒有任何 pack 收它們。
- 現象：fsm 隊員要問使用者，只能用舊式的 `mailbox_send` 寄進專區，或交給 eca 主導寄；用 `mailbox_send` 寄就少了 `user_send` 寄出前照專區規矩的檢查（題數、選項、推薦…），收到回信也沒有 `user_verify` 可驗。
- 建議：做一個 `user` 小包（user_send＋user_verify），範本預設不掛，要的定義在 tools.json 加一行。
- 痛的程度：小不便
- 提出者與日期：skyrim-agent 2026-11-14（skyrim-agent-opus-1 整理投稿）
- 出處：`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/top/aos-advice/skyrim-1114.md`「fsm 隊員沒有 user_send／user_verify」；`~/repo/moddings/skyrim/tmp/aos-skyrim-agent/opus-3/out/facts.md` E8
- 狀態：未處理。整理時查：`lib/packs/` 18 個包都沒列 user_send、user_verify。
