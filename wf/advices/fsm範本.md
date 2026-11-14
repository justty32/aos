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
- 狀態：未處理

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
