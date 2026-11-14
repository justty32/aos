# fsm 範本

← [README](README.md)

agent-fsm 範本（templates/agent-fsm）本身與它身上的工具、guard 的意見。

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
- 狀態：已排入（ok-astra）

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
- 狀態：未處理（2368ee3af 的 wait.py 沒有看 deadline）

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
- 狀態：未處理（lib/packs 沒有限路徑的寫檔 pack；aos-agent history 沒有 last）

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
- 狀態：未處理（未重現；idle.py 讀信那條路沒碰 goal）
